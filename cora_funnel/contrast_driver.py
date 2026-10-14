"""Follow-on job: structural contrast of the dev60 tasks whose candidates fit.

  setsid nohup .venv_arc2026/bin/python -m cora_funnel.contrast_driver > outputs/funnel_v0/contrast_driver.log 2>&1 < /dev/null &

FHR stage 3 (contrast) needs the structure of three things:
- the spurious train-exact programs;
- the rule each failed LOO fold rebuilt;
- the program that fits once the answer is a demonstration (oracle,
  evaluator-side).

The phase-1 rows record outputs, not structure. For the 29 dev60 tasks
categorized FIT_BUT_ALL_WRONG or REJECTED_BUT_CORRECT this job runs:
1. native_rep: native budgets, CPU clock, structure recorded
   (rows_dev60_native_rep.jsonl). This is also a run-to-run reproducibility
   check against phase 1;
2. the oracle on the same keys (rows_dev60_oracle_rep.jsonl).

It waits for the phase-1 funnel driver to exit, so the 4-worker footprint
never grows. A pid file refuses a second copy.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "funnel_v0")
PID = os.path.join(OUT, "contrast_driver.pid")
STATUS = os.path.join(OUT, "contrast_driver_status.json")


def alive(pid_file):
    try:
        pid = int(open(pid_file).read())
        os.kill(pid, 0)
        return "cora_funnel.driver" in open(f"/proc/{pid}/cmdline").read().replace("\0", " ")
    except (OSError, ValueError):
        return False


def status(**kw):
    st = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    st.update(kw, updated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(st, open(STATUS, "w"), indent=1)


def main():
    if os.path.exists(PID):
        try:
            os.kill(int(open(PID).read()), 0)
            sys.exit("another contrast driver is alive: refusing")
        except (OSError, ValueError):
            pass
    open(PID, "w").write(str(os.getpid()))
    status(stage="waiting_for_phase1_driver")
    while alive(os.path.join(OUT, "driver.pid")):
        time.sleep(120)
    from cora_funnel import oracle, run
    from cora_funnel.evaluate import main as evaluate_main
    evaluate_main(["--corpus", "dev60"])                      # the corrected evaluator, from saved rows only
    ev = json.load(open(os.path.join(OUT, "eval_dev60_native.json")))
    keys = sorted(t["key"] for t in ev["tasks"] if t["category"] in ("FIT_BUT_ALL_WRONG", "REJECTED_BUT_CORRECT"))
    w = os.environ.get("CORA_FUNNEL_WORKERS", "4")
    status(stage="native_rep", keys=len(keys))
    run.main(["--corpus", "dev60", "--mode", "native_rep", "--workers", w, "--keys", ",".join(keys)])
    status(stage="oracle_rep")
    oracle.main(["--corpus", "dev60", "--workers", w, "--keys", ",".join(keys), "--tag", "_rep",
                 "--categories", "FIT_BUT_ALL_WRONG,REJECTED_BUT_CORRECT"])
    status(stage="done")
    os.remove(PID)


if __name__ == "__main__":
    main()
