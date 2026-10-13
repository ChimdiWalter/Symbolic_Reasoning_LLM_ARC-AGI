"""Detached driver for funnel phase 1. Start it with setsid nohup:

  setsid nohup .venv_arc2026/bin/python -m cora_funnel.driver > outputs/funnel_v0/driver.log 2>&1 < /dev/null &

1. It waits until the C2-dev hybrid ceiling test has exited. Funnel workers
   would otherwise compete with it mid-comparison. Native budgets are
   wall-clock, so adding load during its arm B would bias that arm.
2. Then, for dev60, c2dev and c3dev (real development first), it runs the
   blind runner (4 workers, nice 19, on the cores the ceiling test frees)
   and then the evaluator.

Status: outputs/funnel_v0/driver_status.json. A pid file refuses a second
copy.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "funnel_v0")
PID = os.path.join(OUT, "driver.pid")
STATUS = os.path.join(OUT, "driver_status.json")
CEILING_PID_HINT = int(os.environ.get("CORA_FUNNEL_WAIT_PID", "3683607"))
CORPORA = ("dev60", "c2dev", "c3dev")


def alive(pid):
    try:
        os.kill(pid, 0)
        return open(f"/proc/{pid}/cmdline").read().find("ceiling_dev") >= 0
    except OSError:
        return False


def status(**kw):
    st = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    st.update(kw, updated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(st, open(STATUS, "w"), indent=1)


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(PID):
        try:
            os.kill(int(open(PID).read()), 0)
            sys.exit("another funnel driver is alive: refusing")
        except (OSError, ValueError):
            pass
    open(PID, "w").write(str(os.getpid()))
    status(stage="waiting_for_ceiling_test", wait_pid=CEILING_PID_HINT)
    while alive(CEILING_PID_HINT):
        time.sleep(60)
    from cora_funnel import evaluate, run
    for c in CORPORA:
        status(stage=f"running {c}")
        run.main(["--corpus", c, "--workers", os.environ.get("CORA_FUNNEL_WORKERS", "4")])
        status(stage=f"evaluating {c}")
        evaluate.main(["--corpus", c])
        status(**{f"done_{c}": True})
    status(stage="phase1_done")
    os.remove(PID)


if __name__ == "__main__":
    main()
