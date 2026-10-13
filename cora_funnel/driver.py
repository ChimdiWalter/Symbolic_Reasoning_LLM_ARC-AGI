"""Detached driver for funnel phase 1. Start it with setsid nohup:

  setsid nohup .venv_arc2026/bin/python -m cora_funnel.driver > outputs/funnel_v0/driver.log 2>&1 < /dev/null &

1. It waits until the C2-dev hybrid ceiling test has exited. Funnel workers
   would otherwise compete with it mid-comparison. Native budgets are
   wall-clock, so adding load during its arm B would bias that arm.
2. Then it runs the following steps in order. It uses 4 workers at nice 0,
   the same footprint as the ceiling test's 4 workers it replaces, so the
   load on the other jobs does not change. Object-layer native deadlines run
   on process CPU time (cora_funnel/run.py, CLOCK). Real development comes
   first.
   1. dev60 native (object layer, instrumented), then evaluate.
   2. dev60 on the whole frozen native harness (cora_funnel/harness_run.py),
      then score by claiming layer. The harness's own budgets are
      wall-clock, under shared load, as in the C2 and ceiling runs.
   3. The dev60 oracle expressibility probe (evaluator-side).
   4. c3dev native, then evaluate.
   5. dev60 with budget x3, on every task whose search or a leave-one-out
      fold hit its deadline. This is the matched-search intervention. It
      also counts false acceptances that extra search creates.
   6. c2dev native, then evaluate, then the c2dev oracle.

Every step is resumable: finished rows are skipped.

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
    from cora_funnel import evaluate, oracle, run
    w = os.environ.get("CORA_FUNNEL_WORKERS", "4")

    def native(c):
        status(stage=f"running {c} native")
        run.main(["--corpus", c, "--workers", w])
        evaluate.main(["--corpus", c])
        status(**{f"done_{c}_native": True})

    native("dev60")
    status(stage="dev60 whole harness")
    from cora_funnel import harness_run
    if not os.path.exists(os.path.join(OUT, "harness_dev60", "run_meta.json")):
        harness_run.run()
    harness_run.score()
    status(done_dev60_harness=True)
    status(stage="dev60 oracle")
    oracle.main(["--corpus", "dev60", "--workers", w])
    status(done_dev60_oracle=True)
    native("c3dev")
    status(stage="dev60 budget3")
    ev = json.load(open(os.path.join(OUT, "eval_dev60_native.json")))
    keys = [t["key"] for t in ev["tasks"] if t["category"] == "NO_FIT_DEADLINE" or t["folds_deadline"] > 0]
    status(budget3_keys=len(keys))
    if keys:
        run.main(["--corpus", "dev60", "--mode", "budget3", "--workers", w, "--keys", ",".join(keys)])
        evaluate.main(["--corpus", "dev60", "--mode", "budget3"])
    status(done_dev60_budget3=True)
    native("c2dev")
    status(stage="c2dev oracle")
    oracle.main(["--corpus", "c2dev", "--workers", w])
    status(done_c2dev_oracle=True, stage="phase1_done")
    os.remove(PID)


if __name__ == "__main__":
    main()
