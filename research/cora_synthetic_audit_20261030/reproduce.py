"""Verify an exact synthetic export, or opt in to one fresh bounded reproduction."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify():
    manifest = json.loads((HERE / 'EXPORT_MANIFEST.json').read_text())
    for name, digest in manifest['files'].items():
        path = HERE / name
        if path.is_symlink() or path.parent != HERE or sha(path) != digest:
            raise ValueError('EXPORT_CHANGED:' + name)
        if path.suffix == '.py': ast.parse(path.read_text(), filename=name)
    return manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--verify-only', action='store_true')
    action.add_argument('--run', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    manifest = verify()
    if args.verify_only:
        if args.output is not None: parser.error('--output requires --run')
        print(json.dumps({'status': 'EXPORT_VERIFIED_STUDY_NOT_EXECUTED', 'files': len(manifest['files'])}))
        return 0
    if args.output is None: parser.error('--run requires a fresh --output directory')
    if os.name != 'posix': parser.error('bounded reproduction currently requires POSIX timers')
    import resource
    out = args.output.resolve()
    if out == HERE or HERE.is_relative_to(out): parser.error('output must not contain package sources')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'INTENT.json').write_text(json.dumps({'started_epoch': time.time(), 'never_reuse': True}) + '\n')
    start_cpu = time.process_time(); start_wall = time.monotonic()
    status = 'STOPPED_UNKNOWN'; error = None
    def check():
        if time.process_time() - start_cpu >= 30: raise TimeoutError('CPU_CAP')
        if time.monotonic() - start_wall >= 60: raise TimeoutError('WALL_CAP')
    def guard(*_): raise TimeoutError('PROCESS_RESOURCE_GUARD')
    old = {s: signal.getsignal(s) for s in (signal.SIGALRM, signal.SIGPROF, signal.SIGXCPU)}
    for s in old: signal.signal(s, guard)
    _, hard = resource.getrlimit(resource.RLIMIT_CPU)
    used = resource.getrusage(resource.RUSAGE_SELF)
    soft = int(used.ru_utime + used.ru_stime) + 32
    if hard != resource.RLIM_INFINITY: soft = min(soft, hard)
    resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    signal.setitimer(signal.ITIMER_REAL, 60)
    signal.setitimer(signal.ITIMER_PROF, 30)
    def save(name, value):
        path = out / name
        if path.parent != out: raise ValueError('OUTPUT_PATH_OUTSIDE_REPRODUCTION')
        tmp = path.with_name(path.name + '.tmp')
        tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n'); tmp.replace(path)
    try:
        import study
        result = study.main(out, save, sha, check)
        check(); status = 'COMPLETE'
    except Exception as caught:
        error = type(caught).__name__ + ':' + str(caught)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.setitimer(signal.ITIMER_PROF, 0)
        for s, prior in old.items(): signal.signal(s, prior)
        receipt = {'status': status, 'error': error, 'CPU_s': time.process_time() - start_cpu,
            'wall_s': time.monotonic() - start_wall, 'classification': 'DEVELOPMENT_SYNTHETIC_REPRODUCTION',
            'reference_run_reopened': False, 'real_ARC_accuracy_measured': False}
        save('REPRODUCTION_RECEIPT.json', receipt)
    print(json.dumps(receipt))
    return 0 if status == 'COMPLETE' else 2

if __name__ == '__main__':
    raise SystemExit(main())
