"""Phase 2 driver (refused without the GO): the held arms and the ARC-AGI-2 check, in order, resumable, on a Kaggle
kernel or locally. The libraries and registries are frozen phase 1 outputs (no construction of a registry here).

    python -I run.py phase2 RUN_DIR BENCHES WORKERS          BENCHES: comma list of benchmarks, or "arc2"

Speed factor: study A's benchmark run under the stage concurrency (WORKERS copies at once, each five repeats; the
factor is the median over the copies of their medians, divided by the Athe reference, clipped to [0.5, 2]). It is
passed to every child as NGB_CPU_SCALE and scales the Athe-measured source-half costs inside the static allowances.
Stages (benchmarks): G0; the grown arms lib, shuf, obj, obj_shuf; the construction arms construct and construct_shuf;
static_lib, static_obj, static_construct in two shards each (two 12 GB static children at once at most), each
followed by a retry stage that runs every child killed by a signal once more alone. Every stage runs at most WORKERS
processes at once (the grown and construction commands are chunked). "arc2" (after the benchmark kernels; their held/ outputs copied into
this RUN_DIR): G0, lib, obj, construct, static_lib, static_obj, static_construct on the 120 evaluation tasks.
Accounting: every attempt of a stage is kept (CPU and wall time, return codes); a stage's CPU is the sum over its
attempts; a failed attempt is never overwritten. Stop rule: no stage starts once the children's CPU exceeds the
ceiling (config phase2_cpu_ceiling_h); the run is then INCOMPLETE and reported as such. RUN_DIR/STAGES.json records
the GO's sha256 and the applied primary; OUTPUT_MANIFEST.json the sha256 of every output. No test output is in the
package: scoring happens on Athe.
"""
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time

from ngb import env as E, gate as GT, object_arm as OA
from ngrow import data as DT, bench as BN

RUN = os.path.join(E.STUDY, "run.py")
LIB = os.path.join(E.STUDY, "feasibility", "library")
STATIC_SHARDS = 2          # amendment 3: two static children at once (two 12 GB caps fit the kernel's memory)


def child_cpu():
    t = os.times()
    return t.children_user + t.children_system


def launch(cmds, log, env, workers):
    """Run the commands, at most `workers` at once; returns every return code in order."""
    rcs = []
    for i in range(0, len(cmds), workers):
        procs = [subprocess.Popen([sys.executable, "-I", RUN] + c, cwd=E.STUDY, stdout=log, stderr=log, env=env)
                 for c in cmds[i:i + workers]]
        rcs += [p.wait() for p in procs]
    return rcs


def concurrent_bench(run_dir, workers, tag):
    """WORKERS copies of the speed benchmark at once; the median over copies of their medians."""
    outs = [os.path.join(run_dir, f"BENCH_{tag}_{i}.json") for i in range(workers)]
    procs = [subprocess.Popen([sys.executable, "-I", RUN, "bench_probe", o], cwd=E.STUDY, env=dict(os.environ))
             for o in outs]
    for p in procs:
        p.wait()
    meds = [E.load(o)["median_cpu_s"] for o in outs if os.path.exists(o)]
    valid = all(E.load(o).get("valid", False) for o in outs if os.path.exists(o))
    return {"copies": len(meds), "medians": meds, "median_cpu_s": statistics.median(meds), "valid": valid}


def manifest(run_dir):
    out = {}
    for d, _, files in os.walk(run_dir):
        for f in sorted(files):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, run_dir)
            if rel.endswith(".tmp") or rel == "OUTPUT_MANIFEST.json" or rel.endswith(".log"):
                continue
            with open(p, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return dict(sorted(out.items()))


def main(run_dir, benches, workers):
    go_sha = GT.require_go()
    from ngb import held as HB
    for b in DT.BENCHMARKS:
        HB.bind_library(LIB, b)
    run_dir, w = os.path.realpath(run_dir), int(workers)
    os.makedirs(run_dir, exist_ok=True)
    cfg = E.load(os.path.join(E.STUDY, "config", "STUDY_CONFIG.json"))
    stages_path = os.path.join(run_dir, "STAGES.json")
    rec = E.load(stages_path) if os.path.exists(stages_path) else {"stages": {}, "go_sha256": go_sha,
                                                                   "primary": GT.primary(), "workers": w}
    if rec["go_sha256"] != go_sha or rec["primary"] != GT.primary():
        raise SystemExit("STAGES.json belongs to another GO")
    rec["cpu_count"] = os.cpu_count()
    rec["object_growth_available"] = OA.available()
    if "cpu_scale" not in rec:
        b = concurrent_bench(run_dir, w, "start")
        rec["bench_start"] = b
        rec["cpu_scale"] = BN.scale(cfg["cpu_speed"]["bench_reference_cpu_s"], b)
        E.dump(stages_path, rec)
    env = dict(os.environ, NGB_CPU_SCALE=str(rec["cpu_scale"]))
    held = os.path.join(run_dir, "held")
    obj = OA.available()
    plan = []
    if benches == "arc2":
        arms = ("G0", "lib") + (("obj", "construct") if obj else ()) + ("static_lib",) + \
            (("static_obj", "static_construct") if obj else ())
        for arm in arms:
            plan.append((f"arc2_{arm}", [["arc2", LIB, held, run_dir, arm]]))
    else:
        bl = benches.split(",")
        assert all(b in DT.BENCHMARKS for b in bl)
        plan.append(("held_G0", [["held", LIB, held, b, "G0"] for b in bl]))
        plan.append(("held_grown", [["held", LIB, held, b, a] for b in bl for a in ("lib", "shuf", "obj", "obj_shuf")]))
        if obj:
            for b in bl:
                plan.append((f"held_construct_{b}", [["held", LIB, held, b, a] for a in ("construct", "construct_shuf")]))
        ws = min(w, STATIC_SHARDS)
        static_arms = ("static_lib",) + (("static_obj", "static_construct") if obj else ())
        for b in bl:
            for a in static_arms:
                plan.append((f"held_{a}_{b}", [["held", LIB, held, b, a, "--shard", f"{i}/{ws}"] for i in range(ws)]))
                plan.append((f"held_{a}_{b}_retry", [["held", LIB, held, b, a, "--retry-killed"]]))
    cap_s = cfg["phase2_cpu_ceiling_h"] * 3600
    with E.open_write(os.path.join(run_dir, "phase2.log"), "a") as log:
        for name, cmds in plan:
            st = rec["stages"].setdefault(name, {"attempts": [], "cpu_s": 0.0, "status": "pending"})
            if st["status"] == "done":
                continue
            spent = sum(v.get("cpu_s", 0) for v in rec["stages"].values())
            if spent > cap_s:
                rec["status"] = f"INCOMPLETE: CPU ceiling {cfg['phase2_cpu_ceiling_h']} h reached before {name}"
                break
            c0, w0 = child_cpu(), time.time()
            rcs = launch(cmds, log, env, w)
            att = {"returncodes": rcs, "cpu_s": round(child_cpu() - c0, 1), "wall_s": round(time.time() - w0, 1),
                   "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(w0))}
            st["attempts"].append(att)
            st["cpu_s"] = round(sum(a["cpu_s"] for a in st["attempts"]), 1)
            st["status"] = "done" if not any(rcs) else f"failed {rcs}"
            E.dump(stages_path, rec)
            if any(rcs):
                rec["status"] = f"FAILED at {name}"
                break
        else:
            rec["status"] = "complete"
    rec["bench_end"] = concurrent_bench(run_dir, w, f"end_{benches.replace(',', '_')}")
    E.dump(stages_path, rec)
    E.dump(os.path.join(run_dir, "OUTPUT_MANIFEST.json"), manifest(run_dir))
    print(json.dumps({"status": rec["status"], "stages": {k: v["status"] for k, v in rec["stages"].items()}}),
          flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
