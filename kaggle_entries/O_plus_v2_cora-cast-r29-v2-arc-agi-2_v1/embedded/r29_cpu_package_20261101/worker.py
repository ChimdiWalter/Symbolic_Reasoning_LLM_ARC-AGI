"""Isolated child entry: install running CPU/wall guards before solver imports."""
import sys
import time
import signal
import resource

# Minimal guard bootstrap CPU is included in process_time(), and parent wall
# deadline covers interpreter startup. No task or heavy dependency is read here.
_boot_cpu = time.process_time()
class GuardTimeout(BaseException):
    pass

def _alarm(*unused):
    raise GuardTimeout('RUNNING_PROCESS_CAP')

signal.signal(signal.SIGPROF, _alarm)
signal.signal(signal.SIGALRM, _alarm)
# Supplied caps are available before JSON/path/solver imports.
_cpu_s, _wall_deadline = float(sys.argv[3]), float(sys.argv[4])
if _cpu_s <= time.process_time() or _wall_deadline <= time.monotonic():
    raise SystemExit(3)
resource.setrlimit(resource.RLIMIT_CPU, (max(1, int(_cpu_s) + 1), max(2, int(_cpu_s) + 2)))
signal.setitimer(signal.ITIMER_PROF, max(.000001, _cpu_s - time.process_time()))
signal.setitimer(signal.ITIMER_REAL, max(.000001, _wall_deadline - time.monotonic()))

import os
import json
import hashlib
from pathlib import Path


def main():
    request, response = map(Path, sys.argv[1:3])
    raw = json.loads(request.read_text())
    cpu_s, deadline = _cpu_s, _wall_deadline
    def check():
        if time.process_time() >= cpu_s or time.monotonic() >= deadline:
            raise GuardTimeout('RUNNING_PROCESS_CAP')
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / 'MANIFEST.json').read_text())
    for relative, expected in manifest['files'].items():
        check()
        path = here / relative
        if path.is_symlink() or not path.resolve().is_relative_to(here) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('PACKAGE_MANIFEST_MISMATCH')
    sys.path.insert(0, str(here / 'vendor'))
    sys.path.insert(0, str(here))
    import solver
    predictions, report = solver.solve(raw['task'], check)
    check()
    result = {'predictions': predictions, 'report': dict(report, worker_process_CPU_s=time.process_time(),
                                                       minimal_guard_bootstrap_CPU_s=_boot_cpu,
                                                       manifest_identity=hashlib.sha256((here / 'MANIFEST.json').read_bytes()).hexdigest())}
    with response.open('x') as stream:
        json.dump(result, stream, separators=(',', ':'), allow_nan=False)
        stream.flush(); os.fsync(stream.fileno())
    check()

if __name__ == '__main__':
    try:
        main()
    except BaseException:
        raise SystemExit(3)
