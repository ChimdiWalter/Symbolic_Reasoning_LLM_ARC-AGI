"""Stand-in for arm_worker.py in the synthetic tests: same command line (INPUT RESULT PROGRESS), same answer guard,
and a behaviour chosen by the synthetic task id's first three letters:

  fit  a fit (VERIFIED, or REACHABLE for the no-target arm)
  nof  no fit, with one finished search that hit its execution budget
  brn  burn CPU until the per-arm guard ends it (one finished search written to progress first)
  imp  burn CPU at import time, before main() runs
  slp  sleep until the wall backstop or a kill ends it
  crs  raise an exception (worker error)
  two  the exact-code review's case: start two children that would each burn 0.7 CPU-s under a 1 CPU-s arm limit,
       then try every other route (os.fork, posix_spawn, multiprocessing fork and spawn, a libc fork through
       ctypes, os.system, a thread); record which were refused, then fit
  twb  the same attempts, then burn CPU in-process until the per-arm guard ends it
  ans  try to read answer files (every attempt must be refused), then fit
  kgd  kill its own guard process with SIGKILL, then sleep (the guard dies before writing a receipt)
  str  try to leave a sleeping process behind (a straggler) and exit; the creation fails, so the worker errors

This stand-in sets no process limit of its own: whatever it is refused comes from the per-arm guard.
"""
import os
import signal
import subprocess
import sys
import time

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import common as C              # noqa: E402
from testb import labels as LB             # noqa: E402

C.install_answer_guard([p for p in os.environ.get("TESTB_BLOCKED", "").split(os.pathsep) if p])
signal.signal(signal.SIGXCPU, signal.SIG_DFL)


def burn(seconds):
    t0 = time.process_time()
    x = 0
    while seconds is None or time.process_time() - t0 < seconds:
        x += 1
    return x


if len(sys.argv) > 1 and C.load_json(sys.argv[1])["task"].startswith("imp"):     # before main() is reached
    burn(None)


BURN_CHILD = [sys.executable, "-I", "-c", "import time\nt=time.process_time()\nwhile time.process_time()-t<0.7: pass"]


def child_attempts():
    import ctypes
    import multiprocessing
    import threading
    tried = []

    def t(route, f):
        try:
            f()
            tried.append({"route": route, "refused": False})
        except (OSError, RuntimeError) as e:
            tried.append({"route": route, "refused": True, "error": e.__class__.__name__})

    def fork_burn():
        pid = os.fork()
        if pid == 0:
            burn(0.7)
            os._exit(0)
        os.waitpid(pid, 0)

    def libc_fork():
        pid = ctypes.CDLL(None, use_errno=True).fork()
        if pid == 0:
            burn(0.7)
            os._exit(0)
        if pid < 0:
            raise OSError(ctypes.get_errno(), "fork() through ctypes failed")
        os.waitpid(pid, 0)

    def system():
        if os.system(" ".join(BURN_CHILD[:2]) + " -c pass") != 0:
            raise OSError("os.system could not run a child")

    def mp(method):
        p = multiprocessing.get_context(method).Process(target=burn, args=(0.7,))
        p.start()
        p.join()

    def thread():
        th = threading.Thread(target=burn, args=(0.7,))
        th.start()
        th.join()

    t("subprocess, first child", lambda: subprocess.run(BURN_CHILD, check=True))
    t("subprocess, second child", lambda: subprocess.run(BURN_CHILD, check=True))
    t("os.fork", fork_burn)
    t("os.posix_spawn", lambda: os.waitpid(os.posix_spawn(sys.executable, BURN_CHILD, {}), 0))
    t("multiprocessing fork", lambda: mp("fork"))
    t("multiprocessing spawn", lambda: mp("spawn"))
    t("libc fork through ctypes", libc_fork)
    t("os.system", system)
    t("thread", thread)
    return tried


def main():
    inp, out, prog = sys.argv[1:4]
    spec = C.load_json(inp)
    kind = spec["task"][:3]
    search = {"search": "base", "fit": False, "program": None, "stop": "budget", "stop_reason": "budget",
              "level_complete": 3, "calls": 150000, "closures": 10, "closure_capped": False, "cpu_s": 0.1}
    rec = {"arm": spec["arm"], "target_arm": spec["target"] is not None, "searches": [search], "holes": None,
           "n_hole_matching_operations": 0, "tried_operations": [], "shape_relation": "synthetic"}
    if kind == "brn":
        C.write_json_atomic(prog, {"arm": spec["arm"], "searches": [search]})
        burn(None)
    if kind == "imp":
        burn(None)
    if kind == "slp":
        time.sleep(3600)
    if kind == "crs":
        raise RuntimeError("synthetic worker error")
    if kind == "kgd":
        os.kill(os.getppid(), signal.SIGKILL)
        time.sleep(3600)
    if kind in ("two", "twb"):
        rec["child_attempts"] = child_attempts()
        if kind == "twb":
            C.write_json_atomic(prog, {"arm": spec["arm"], "searches": [search],
                                       "child_attempts": rec["child_attempts"]})
            burn(None)
    if kind == "str":
        subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(3600)"])
    if kind == "ans":
        tried = []
        for p in [q for q in os.environ.get("TESTB_BLOCKED", "").split(os.pathsep) if q] + \
                [os.path.join(os.path.dirname(inp), "x_solutions.json")]:
            try:
                with open(p, "rb") as f:
                    f.read(1)
                tried.append({"path": p, "refused": False})
            except PermissionError:
                tried.append({"path": p, "refused": True})
            except OSError as e:
                tried.append({"path": p, "refused": False, "error": e.__class__.__name__})
        rec["answer_attempts"] = tried
    if kind in ("fit", "two", "ans", "str"):
        search.update(fit=True, program="synthetic", stop="fits", stop_reason="fits")
        pred = spec["target"] if spec["target"] is not None else spec["x"]
        rec.update(fit=True, program="synthetic", level="base grammar", prediction=pred,
                   outcome="VERIFIED" if spec["target"] is not None else "REACHABLE")
    else:
        rec.update(fit=False, program=None, level=None, prediction=None, outcome=LB.NO_FIT,
                   no_fit_flags=LB.no_fit_flags(rec["searches"]))
    rec["input_sha256"] = C.sha_file(inp)
    C.write_json_atomic(out, rec)


if __name__ == "__main__":
    main()
