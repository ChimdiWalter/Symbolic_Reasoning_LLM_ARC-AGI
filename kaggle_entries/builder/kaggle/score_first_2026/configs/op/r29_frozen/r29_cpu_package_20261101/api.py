"""Portable, fail-closed R29 candidates API; heavy work is process isolated."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
_LOCAL = threading.local()

class APITimeout(TimeoutError):
    """Owned per-call timeout; external cancellation retains its identity."""
    pass


def _grid(value):
    if (type(value) is not list or not 1 <= len(value) <= 30 or type(value[0]) is not list
            or not 1 <= len(value[0]) <= 30 or any(type(row) is not list or len(row) != len(value[0])
            or any(type(v) is not int or not 0 <= v <= 9 for v in row) for row in value)):
        raise ValueError('GRID_SCHEMA')
    return [row[:] for row in value]


def _arity(task):
    if type(task) is dict and type(task.get('test')) is list and len(task['test']) <= 100:
        return len(task['test'])
    return 0


def _clean_task(task):
    # Optional identity metadata is never read, copied, hashed or passed to code.
    if type(task) is not dict or set(task) - {'train', 'test', 'id', 'task_id'}:
        raise ValueError('TASK_FIELDS')
    train, tests = task.get('train'), task.get('test')
    if type(train) is not list or not 0 <= len(train) <= 10 or type(tests) is not list or not 1 <= len(tests) <= 100:
        raise ValueError('TASK_SCHEMA')
    out = {'train': [], 'test': []}
    for pair in train:
        if type(pair) is not dict or set(pair) != {'input', 'output'}:
            raise ValueError('TRAIN_FIELDS')
        out['train'].append({'input': _grid(pair['input']), 'output': _grid(pair['output'])})
    for pair in tests:
        if type(pair) is not dict or set(pair) != {'input'}:
            raise ValueError('TEST_INPUT_ONLY_REQUIRED')
        out['test'].append({'input': _grid(pair['input'])})
    return out


def _wait(proc, deadline):
    """Wait only this PID, collecting exact child CPU even under concurrent calls."""
    while True:
        pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
        if pid:
            proc.returncode = os.waitstatus_to_exitcode(status)
            return usage.ru_utime + usage.ru_stime
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise APITimeout('CALL_WALL_CAP')
        time.sleep(min(.005, remaining))


def _stop(proc):
    # The isolated worker creates no grandchildren; signal only the owned PID.
    if proc is not None and proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            _, status, usage = os.wait4(proc.pid, 0)
            proc.returncode = os.waitstatus_to_exitcode(status)
            return usage.ru_utime + usage.ru_stime
        except ChildProcessError:
            pass
    return 0.0


def last_report():
    """Per-calling-thread diagnostic copy; candidates() retains its list API."""
    return json.loads(json.dumps(getattr(_LOCAL, 'report', {})))


def candidates_with_report(task: dict, cpu_s: float, wall_s: float):
    started_wall, started_thread = time.monotonic(), time.thread_time()
    none = [None] * _arity(task)
    report = {'schema': 'CORA_R29_PORTABLE_API_V1', 'status': 'ABSTAIN',
              'reason': 'NOT_STARTED', 'outputs': len(none), 'external_answers_received': False,
              'fresh_LOO_required': True, 'selected_arm': None}
    proc = None
    child_cpu = 0.0
    returned, caps_valid = none, False
    try:
        for value in (cpu_s, wall_s):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('FINITE_POSITIVE_CAP_REQUIRED')
        caps_valid = True
        deadline = started_wall + wall_s
        clean = _clean_task(task)
        none = [None] * len(clean['test'])
        returned = none
        if len(clean['train']) < 2:
            report.update(status='INSUFFICIENT_VALIDATION_EVIDENCE', reason='FEWER_THAN_TWO_DEMONSTRATIONS')
            return none, report
        with tempfile.TemporaryDirectory(prefix='cora_r29_') as directory:
            request, response = Path(directory) / 'request.json', Path(directory) / 'response.json'
            # Charge this thread's validation/serialization/spawn work in addition
            # to the exact waited-child CPU. Reserve 10ms for caller finalization.
            remaining = cpu_s - (time.thread_time() - started_thread) - .010
            if remaining <= 0 or time.monotonic() >= deadline:
                raise APITimeout('CALL_SETUP_CAP')
            payload = {'task': clean}
            with request.open('x') as stream:
                json.dump(payload, stream, separators=(',', ':'), allow_nan=False)
            os.chmod(request, 0o600)
            # -I ignores Python environment/user path; -S skips site imports.
            remaining = cpu_s - (time.thread_time() - started_thread) - .010
            if remaining <= 0:
                raise APITimeout('CALL_SETUP_CAP')
            proc = subprocess.Popen([sys.executable, '-I', '-S', '-B', str(HERE / 'worker.py'), str(request), str(response), str(remaining), str(deadline)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    close_fds=True)
            child_cpu = _wait(proc, deadline)
            if proc.returncode != 0:
                raise RuntimeError('WORKER_FAILED_CLOSED')
            if time.monotonic() >= deadline:
                raise APITimeout('CALL_WALL_CAP')
            if response.stat().st_size > 1_000_000:
                raise ValueError('WORKER_RESPONSE_SIZE')
            result = json.loads(response.read_text())
            if type(result) is not dict or set(result) != {'predictions', 'report'}:
                raise ValueError('WORKER_RESPONSE_SCHEMA')
            predictions = result['predictions']
            if type(predictions) is not list or len(predictions) != len(none):
                raise ValueError('WORKER_OUTPUT_ARITY')
            predictions = [None if value is None else _grid(value) for value in predictions]
            if type(result['report']) is not dict:
                raise ValueError('WORKER_REPORT_SCHEMA')
            report.update(result['report'])
            total = child_cpu + time.thread_time() - started_thread
            if total >= cpu_s or time.monotonic() >= deadline:
                raise APITimeout('CALL_THROUGH_RETURN_CAP')
            report.update(caller_thread_CPU_s=time.thread_time() - started_thread,
                          waited_child_CPU_s=child_cpu, combined_CPU_s=total,
                          elapsed_wall_s=time.monotonic() - started_wall,
                          child_waited=True, actual_child_exit_code=proc.returncode)
            returned = predictions
            return returned, report
    except Exception as error:
        if isinstance(error, TimeoutError) and not isinstance(error, APITimeout):
            raise
        report.update(status='ABSTAIN', reason=type(error).__name__ + ':' + str(error), selected_arm=None, selected_arms=[None]*len(none))
        return none, report
    finally:
        child_cpu = max(child_cpu, _stop(proc))
        total = child_cpu + time.thread_time() - started_thread
        elapsed = time.monotonic() - started_wall
        if caps_valid and (total >= cpu_s or elapsed >= wall_s):
            returned[:] = [None] * len(returned)
            report.update(status='ABSTAIN', reason='FINAL_THROUGH_RETURN_CAP', selected_arm=None, selected_arms=[None]*len(returned))
        report.update(caller_thread_CPU_s=time.thread_time() - started_thread,
                      waited_child_CPU_s=child_cpu, combined_CPU_s=total,
                      child_waited=proc is not None and proc.returncode is not None,
                      actual_child_exit_code=None if proc is None else proc.returncode,
                      elapsed_wall_s=elapsed)
        _LOCAL.report = dict(report)


def candidates(task: dict, cpu_s: float, wall_s: float):
    return candidates_with_report(task, cpu_s, wall_s)[0]
