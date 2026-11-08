"""The held run, after the coordinator's GO (PROTOCOL.md sections 3.4, 8 and 9). Light orchestration in Python;
every heavy step runs in a shared CPU slot (scripts/with_cpu_slot.sh). Finished steps are skipped on a restart.
Start it detached, after GO_CAL exists:
    sh scripts/run_detached.sh cal_calacc_held python3 -I -B \
        experiments/calibrated_acceptance_20261108/scripts/run_after_go.py
Status lines: data/work/held_chain.run.status. Exit 2: GO_CAL missing (nothing opened); exit 3: CPU cap reached."""
import json
import os
import resource
import subprocess
import sys
import time

ROOT = "/path/to/repository/experiments/calibrated_acceptance_20261108"
R = os.path.dirname(os.path.dirname(ROOT))
PY = "python3"
SD = os.path.join(R, "outputs/universality_v2/venv_stardist/bin/python")
SLOT = ["sh", os.path.join(R, "scripts/with_cpu_slot.sh")]
S = os.path.join(ROOT, "scripts")
STATUS = os.path.join(ROOT, "data", "work", "held_chain.run.status")
DONE = os.path.join(ROOT, "data", "work", "held_steps")
CFG = json.load(open(os.path.join(ROOT, "CONFIG.json")))
ARMS = ["CALIBRATED", "STRICT", "TOLERANT"] + [f"CAL_BLIND_{r}" for r in range(1, 6)] + \
    [f"CAL_SHUFFLED_{r}" for r in range(1, 6)]
STEPS = [
    ("verify_freeze", False, [PY, "-I", "-B", os.path.join(S, "verify_freeze.py")]),
    ("select", False, [PY, "-I", "-B", os.path.join(S, "cadata.py"), "select"]),
    ("convert", True, [PY, "-I", "-B", os.path.join(S, "cadata.py"), "convert"]),
    ("segment", True, [SD, "-I", "-B", os.path.join(S, "seg_puma.py"), "held"]),
    ("strong_native", True, [PY, "-I", "-B", os.path.join(S, "caharness.py"), "strong_native_held"]),
    ("decide_cora", True, [PY, "-I", "-B", os.path.join(S, "caharness.py"), "pool", "held"] + ARMS),
    ("decide_matched", True, [PY, "-I", "-B", os.path.join(S, "caharness.py"), "matched", "held"]),
    ("decide_matched_u5", True, [PY, "-I", "-B", os.path.join(S, "caharness.py"), "matched_u5"]),
    ("freeze_decisions", False, [PY, "-I", "-B", os.path.join(S, "caharness.py"), "freeze_decisions"]),
    ("evaluate", True, [PY, "-I", "-B", os.path.join(S, "caharness.py"), "evaluate"]),
]


def log(msg):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n")


def child_cpu():
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    return ru.ru_utime + ru.ru_stime


def main():
    if not os.path.exists(os.path.join(ROOT, "GO_CAL")):
        log("EXIT 2 GO_CAL missing: nothing held is opened")
        sys.exit(2)
    os.makedirs(DONE, exist_ok=True)
    prior = json.load(open(os.path.join(DONE, "CPU.json"))) if os.path.exists(os.path.join(DONE, "CPU.json")) else {}
    log(f"START pid={os.getpid()}")
    cap = float(CFG["cpu_cap_after_go_s"])
    for name, heavy, cmd in STEPS:
        if os.path.exists(os.path.join(DONE, name)):
            continue
        used = sum(prior.values())
        if used >= cap:
            log(f"EXIT 3 CPU cap {cap:.0f} s reached before {name} ({used:.0f} s used)")
            sys.exit(3)
        c0 = child_cpu()
        env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        if name == "segment":
            env.update(OMP_NUM_THREADS="4", TF_NUM_INTRAOP_THREADS="4")
        out = open(os.path.join(DONE, f"{name}.log"), "w")
        rc = subprocess.call((SLOT if heavy else []) + cmd, stdout=out, stderr=subprocess.STDOUT, env=env, cwd=ROOT)
        out.close()
        prior[name] = prior.get(name, 0.0) + child_cpu() - c0
        json.dump(prior, open(os.path.join(DONE, "CPU.json"), "w"), indent=1)
        if rc != 0:
            log(f"EXIT 1 step {name} failed (rc {rc}); see data/work/held_steps/{name}.log")
            sys.exit(1)
        open(os.path.join(DONE, name), "w").write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
        log(f"{name.upper()}_DONE cpu_s={prior[name]:.1f}")
    log(f"EXIT 0 total_cpu_s={sum(prior.values()):.1f}")


if __name__ == "__main__":
    main()
