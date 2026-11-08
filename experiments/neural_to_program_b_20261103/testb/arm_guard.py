"""The per-arm guard (PROTOCOL.md section 5): one process per arm, between the driver and the arm's worker.

    python -I arm_guard.py '<json: arm, driver_pid, cpu_limit_s, wall_limit_s, receipt, lock, log, cmd, poll_s>'

- The worker runs under RLIMIT_CPU: soft limit = the arm's limit (100 CPU-s), whose SIGXCPU ends it, and hard limit
  one second above it, whose SIGKILL ends a worker that somehow survived SIGXCPU. The limit is set in the child
  before exec, so it covers interpreter start, imports, grammar construction, every search and all bookkeeping.
- The worker also runs under RLIMIT_NPROC = 0 (soft and hard, set before exec): the kernel refuses every process
  and thread it tries to create, so the worker is the arm's only process and RLIMIT_CPU bounds the whole arm.
- The worker gets PR_SET_PDEATHSIG = SIGKILL: it cannot outlive this guard. This guard gets PR_SET_PDEATHSIG =
  SIGTERM: if the driver dies, the guard kills the worker, reaps it and still writes its receipt.
- Wall backstop: SIGKILL to the worker after wall_limit_s (400 s). The worker leads its own process group; a stop
  kills the group, and a process left behind by a finished worker is killed and flagged (its CPU would be missing
  from the receipt, so the driver does not count that arm as finished). Core dumps are disabled (RLIMIT_CORE 0).
- The receipt is the reaped worker's user + system CPU from resource.getrusage(RUSAGE_CHILDREN) (child-inclusive:
  it includes any process the worker waited for), cross-checked against os.wait4's rusage, plus this guard's own
  CPU. It is written atomically. The guard holds an exclusive lock on its lock file for its whole life, so a
  recovering driver can wait until the receipt is final.
"""
import ctypes
import fcntl
import json
import os
import resource
import signal
import subprocess
import sys
import time

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import common as C              # noqa: E402

C.install_answer_guard([p for p in os.environ.get("TESTB_BLOCKED", "").split(os.pathsep) if p])
PR_SET_PDEATHSIG = 1
_LIBC = ctypes.CDLL(None, use_errno=True)


def set_pdeathsig(sig):
    if _LIBC.prctl(PR_SET_PDEATHSIG, int(sig), 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_PDEATHSIG) failed")


def _cpu(ru):
    return ru.ru_utime + ru.ru_stime


def main():
    a = json.loads(sys.argv[1])
    set_pdeathsig(signal.SIGTERM)
    stop = []
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, lambda num, _f: stop.append(signal.Signals(num).name))
    base = {"arm": a["arm"], "guard_pid": os.getpid(), "cpu_limit_s": a["cpu_limit_s"],
            "wall_limit_s": a["wall_limit_s"]}
    if os.getppid() != a["driver_pid"]:
        C.write_json_atomic(a["receipt"], dict(base, status="driver_gone_before_start", worker_started=False,
                                               cpu_s=0.0, guard_cpu_s=round(_cpu(resource.getrusage(
                                                   resource.RUSAGE_SELF)), 6)))
        return
    lock = os.open(a["lock"], os.O_WRONLY | os.O_CREAT, 0o644)
    fcntl.flock(lock, fcntl.LOCK_EX)
    me = os.getpid()
    limit = int(a["cpu_limit_s"])

    def pre():
        resource.setrlimit(resource.RLIMIT_CPU, (limit, limit + 1))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))       # the worker can create no process or thread
        set_pdeathsig(signal.SIGKILL)
        if os.getppid() != me:
            os._exit(70)

    t0 = time.monotonic()
    with open(a["log"], "ab") as log:
        proc = subprocess.Popen(a["cmd"], stdin=subprocess.DEVNULL, stdout=log, stderr=log, preexec_fn=pre,
                                close_fds=True, process_group=0)
    trigger = None
    while True:
        pid, status, ru = os.wait4(proc.pid, os.WNOHANG)
        if pid == proc.pid:
            break
        if trigger is None and stop:
            trigger = "interrupted:" + stop[0]
            os.killpg(proc.pid, signal.SIGKILL)
        elif trigger is None and time.monotonic() - t0 > a["wall_limit_s"]:
            trigger = "wall_backstop"
            os.killpg(proc.pid, signal.SIGKILL)
        time.sleep(a["poll_s"])
    wall = time.monotonic() - t0
    proc.returncode = os.waitstatus_to_exitcode(status)
    try:                                        # any process the worker left behind is not covered by the receipt
        os.killpg(proc.pid, 0)
        stragglers = True
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        stragglers = False
    ch = resource.getrusage(resource.RUSAGE_CHILDREN)
    rec = dict(base, status="reaped", worker_started=True, worker_pid=proc.pid, wall_s=round(wall, 3),
               exit_code=proc.returncode if proc.returncode >= 0 else None,
               signal=signal.Signals(-proc.returncode).name if proc.returncode < 0 else None,
               trigger=trigger, stragglers=stragglers, worker_rlimit_nproc=[0, 0], cpu_user_s=round(ch.ru_utime, 6),
               cpu_system_s=round(ch.ru_stime, 6), cpu_s=round(_cpu(ch), 6), wait4_cpu_s=round(_cpu(ru), 6),
               maxrss_kb=ru.ru_maxrss,
               guard_cpu_s=round(_cpu(resource.getrusage(resource.RUSAGE_SELF)), 6))
    C.write_json_atomic(a["receipt"], rec)
    os.close(lock)


if __name__ == "__main__":
    main()
