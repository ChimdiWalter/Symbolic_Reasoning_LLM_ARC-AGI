"""Kernel-side driver of development data generation (development pool and training or validation families only).

    python -s -B launch/devgen_run.py ROOT WALL_LIMIT_S JOB [JOB ...]      JOB = "kind|out|partition|n|seed"

Every job runs as one process `run.py gen KIND OUT PARTITION N SEED WALL_LIMIT_S` with PYTHONHASHSEED=0 and the
package's roots; all are stopped at the wall limit (the generators also stop themselves at it)."""
import json
import os
import subprocess
import sys
import time


def main():
    root, limit = sys.argv[1], int(sys.argv[2])
    jobs = sys.argv[3:]
    study = os.path.join(root, "experiments", "spec_guide_20261108")
    env = dict(os.environ, PYTHONHASHSEED="0", NG_PACKAGE="1", NG_REPO=root,
               NG_STUDY=os.path.join(root, "experiments", "natural_growth_20261105"),
               NG_DATA=os.path.join(root, "data", "prepared"), OG_REPO=root,
               OG_STUDY=os.path.join(root, "experiments", "object_growth_20261105"), GC_REPO=root,
               GC_STUDY=os.path.join(root, "experiments", "guided_construction_20261106"), SG_REPO=root,
               SG_STUDY=study)
    os.makedirs(os.path.join(study, "dev"), exist_ok=True)
    t0 = time.time()
    procs = []
    for k, j in enumerate(jobs):
        kind, out, part, n, seed = j.split("|")
        log = open(os.path.join(study, "dev", f"job{k}.log"), "a")
        procs.append(subprocess.Popen([sys.executable, "-s", "-B", os.path.join(study, "run.py"), "gen", kind,
                                       os.path.join(study, "dev", out), part, n, seed, str(limit - 120)],
                                      cwd=study, env=env, stdout=log, stderr=subprocess.STDOUT))
    while any(p.poll() is None for p in procs):
        if time.time() - t0 > limit:
            for p in procs:
                if p.poll() is None:
                    p.kill()
            break
        time.sleep(10)
    rec = {"jobs": jobs, "codes": [p.wait() for p in procs], "wall_s": round(time.time() - t0, 1),
           "cpus": os.cpu_count(), "python": sys.version}
    with open(os.path.join(study, "dev", "devgen_run.json"), "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
