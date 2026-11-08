"""Kernel-side driver of the held run (also used, in rehearsal mode, by the local smoke test).

    python -s -B launch/held_kernel.py ROOT WORKERS PER_EDIT GEN_LIMIT_S RUN_LIMIT_S

Phase 1: WORKERS processes `run.py held gen PER_EDIT GEN_LIMIT_S i/WORKERS` (held families on held-pool grids, from
the GO's seed; at most PER_EDIT admitted tasks per edit type in all). Phase 2: WORKERS processes `run.py held run
i/WORKERS` (every arm at every budget), stopped at RUN_LIMIT_S. PYTHONHASHSEED=0 and the package's roots; SG_REHEARSAL
is passed through unchanged. Writes runs/held/kernel_run.json (or runs/rehearsal_held/ in rehearsal mode)."""
import json
import os
import subprocess
import sys
import time


def main():
    root, workers, per_edit, gen_limit, run_limit = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), \
        int(sys.argv[5])
    study = os.path.join(root, "experiments", "spec_guide_20261108")
    env = dict(os.environ, PYTHONHASHSEED="0", NG_PACKAGE="1", NG_REPO=root,
               NG_STUDY=os.path.join(root, "experiments", "natural_growth_20261105"),
               NG_DATA=os.path.join(root, "data", "prepared"), OG_REPO=root,
               OG_STUDY=os.path.join(root, "experiments", "object_growth_20261105"), GC_REPO=root,
               GC_STUDY=os.path.join(root, "experiments", "guided_construction_20261106"), SG_REPO=root,
               SG_STUDY=study, SG_PACKAGE="1")
    out = os.path.join(study, "runs", "rehearsal_held" if os.environ.get("SG_REHEARSAL") == "1" else "held")
    os.makedirs(out, exist_ok=True)
    rec = {"workers": workers, "per_edit": per_edit, "gen_limit_s": gen_limit, "run_limit_s": run_limit,
           "cpus": os.cpu_count(), "python": sys.version, "rehearsal": os.environ.get("SG_REHEARSAL") == "1",
           "phases": {}}
    for phase, args, limit in (("gen", lambda i: ["held", "gen", per_edit, str(gen_limit), f"{i}/{workers}"],
                                gen_limit + 300),
                               ("run", lambda i: ["held", "run", f"{i}/{workers}"], run_limit)):
        t0 = time.time()
        logs = [open(os.path.join(out, f"{phase}.worker{i}.log"), "a") for i in range(workers)]
        procs = [subprocess.Popen([sys.executable, "-s", "-B", os.path.join(study, "run.py")] + args(i), cwd=study,
                                  env=env, stdout=logs[i], stderr=subprocess.STDOUT) for i in range(workers)]
        stopped = False
        while any(p.poll() is None for p in procs):
            if time.time() - t0 > limit:
                for p in procs:
                    if p.poll() is None:
                        p.kill()
                stopped = True
                break
            time.sleep(5)
        rec["phases"][phase] = {"return_codes": [p.wait() for p in procs], "stopped_at_limit": stopped,
                                "wall_s": round(time.time() - t0, 1)}
        for f in logs:
            f.close()
        with open(os.path.join(out, "kernel_run.json"), "w") as f:
            json.dump(rec, f, indent=1)
        print(json.dumps({phase: rec["phases"][phase]}), flush=True)


if __name__ == "__main__":
    main()
