"""Kernel-side driver of the held run (also used, in rehearsal mode, by the local smoke test).

    python -s -B launch/kernel_run.py ROOT RUN_DIR WORKERS WALL_LIMIT_S SET [SET ...]

ROOT is the unpacked package (repository layout). For each SET in turn, WORKERS processes of
`run.py held RUN_DIR SET i/WORKERS` run with PYTHONHASHSEED=0 and the package's roots; every worker is stopped once
WALL_LIMIT_S seconds have passed since the start (rows already written stay; a missing row makes the run INVALID).
GC_REHEARSAL is passed through unchanged (set only by the smoke test). Writes RUN_DIR/kernel_run.json.
"""
import json
import os
import subprocess
import sys
import time


def main():
    root, run_dir, workers, limit = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    sets = sys.argv[5:]
    study = os.path.join(root, "experiments", "guided_construction_20261106")
    env = dict(os.environ, PYTHONHASHSEED="0", NG_PACKAGE="1", NG_REPO=root,
               NG_STUDY=os.path.join(root, "experiments", "natural_growth_20261105"),
               NG_DATA=os.path.join(root, "data", "prepared"), OG_REPO=root,
               OG_STUDY=os.path.join(root, "experiments", "object_growth_20261105"), NGB_REPO=root,
               NGB_STUDY=os.path.join(root, "experiments", "natural_growth_b_20261105"), GC_REPO=root, GC_STUDY=study)
    os.makedirs(run_dir, exist_ok=True)
    t0 = time.time()
    rec = {"sets": {}, "workers": workers, "wall_limit_s": limit, "cpus": os.cpu_count(), "python": sys.version,
           "rehearsal": os.environ.get("GC_REHEARSAL") == "1"}
    for s in sets:
        s0 = time.time()
        logs = [open(os.path.join(run_dir, f"{s}.worker{i}.log"), "a", encoding="utf-8") for i in range(workers)]
        procs = [subprocess.Popen([sys.executable, "-s", "-B", os.path.join(study, "run.py"), "held", run_dir, s,
                                   f"{i}/{workers}"], cwd=study, env=env, stdout=logs[i], stderr=subprocess.STDOUT)
                 for i in range(workers)]
        stopped = False
        while any(p.poll() is None for p in procs):
            if time.time() - t0 > limit:
                for p in procs:
                    if p.poll() is None:
                        p.kill()
                stopped = True
                break
            time.sleep(5)
        codes = [p.wait() for p in procs]
        for f in logs:
            f.close()
        rec["sets"][s] = {"return_codes": codes, "stopped_at_limit": stopped, "wall_s": round(time.time() - s0, 1)}
        with open(os.path.join(run_dir, "kernel_run.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1, sort_keys=True)
        print(json.dumps({"set": s, **rec["sets"][s]}), flush=True)
        if stopped:
            break
    rec["wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(run_dir, "kernel_run.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
