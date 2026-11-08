"""Phase 2 driver (refused without the GO): every stage, in order, resumable, on a Kaggle kernel or locally.

    python -I run.py phase2 RUN_DIR BENCHES WORKERS          BENCHES: comma list of benchmarks, or "arc2"

Benchmarks (one kernel may take several):
  1 speed factor (bench.py) -> NG_CPU_SCALE for every child;
  2 controller on every source task (WORKERS shards);
  3 growth on the source half, per benchmark: S-hole, S-demo, S-shuffled (one process per benchmark), then S-enum
    (WORKERS shards, each from a copy of the benchmark's gate cache), then the registries (merge, combined
    regression);
  4 held half, per benchmark: G0, then S-hole, S-shuffled, S-demo, S-enum (reuse only), then matched static search
    (WORKERS shards; its allowance needs S-hole's held CPU);
"arc2" (after the benchmark runs; their RUN_DIR outputs copied into this RUN_DIR): G0, growth, static on the 120
ARC-AGI-2 evaluation tasks.
Stop rule: no stage starts once the children's CPU exceeds the ceiling (config phase2_cpu_ceiling_h); the run is then
INCOMPLETE and reported as such. RUN_DIR/STAGES.json records CPU and wall time per stage; OUTPUT_MANIFEST.json the
sha256 of every output. Test outputs are never in the package: scoring happens on Athe after download (report.py).
"""
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

from ngrow import env as E, data as DT, gate as GT, bench as BN

RUN = os.path.join(E.STUDY, "run.py")


def child_cpu():
    t = os.times()
    return t.children_user + t.children_system


def launch(cmds, log, env):
    procs = [subprocess.Popen([sys.executable, "-I", RUN] + c, cwd=E.STUDY, stdout=log, stderr=log, env=env)
             for c in cmds]
    return [p.wait() for p in procs]


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
    go_sha = GT.require_phase2()
    run_dir, w = os.path.realpath(run_dir), int(workers)
    os.makedirs(run_dir, exist_ok=True)
    cfg = E.load(os.path.join(E.STUDY, "config", "STUDY_CONFIG.json"))
    stages_path = os.path.join(run_dir, "STAGES.json")
    rec = E.load(stages_path) if os.path.exists(stages_path) else {"stages": {}, "go_sha256": go_sha}
    rec["cpu_count"] = os.cpu_count()
    if "cpu_scale" not in rec:
        b = BN.run()
        E.dump(os.path.join(run_dir, "BENCH_start.json"), b)
        rec["cpu_scale"] = BN.scale(cfg["cpu_speed"]["bench_reference_cpu_s"], b)
        E.dump(stages_path, rec)
    env = dict(os.environ, NG_CPU_SCALE=str(rec["cpu_scale"]), PYTHONHASHSEED="0")
    ctrl = ",".join(os.path.join(run_dir, "controller", f"shard{i}.jsonl") for i in range(w))
    grow, held = os.path.join(run_dir, "grow"), os.path.join(run_dir, "held")
    plan = []
    if benches == "arc2":
        plan.append(("arc2_G0", [["arc2", grow, held, run_dir, "G0"]]))
        plan.append(("arc2_growth", [["arc2", grow, held, run_dir, "growth"]]))
        plan.append(("arc2_static", [["arc2", grow, held, run_dir, "static"]]))
    else:
        bl = benches.split(",")
        assert all(b in DT.BENCHMARKS for b in bl)
        os.makedirs(os.path.join(run_dir, "controller"), exist_ok=True)
        plan.append(("controller", [["controller_run", os.path.join(run_dir, "controller", f"shard{i}.jsonl"),
                                     "source", *bl, "--shard", f"{i}/{w}"] for i in range(w)]))
        plan.append(("grow_spec", [["grow", ctrl, grow, b, "S-hole", "S-demo", "S-shuffled"] for b in bl]))
        for b in bl:
            plan.append((f"grow_enum_{b}", [["grow", ctrl, grow, b, "S-enum", "--shard", f"{i}/{w}"]
                                            for i in range(w)]))
        plan.append(("registries", [["grow", ctrl, grow, b, "registry"] for b in bl]))
        plan.append(("held_G0", [["held", grow, held, b, "G0"] for b in bl]))
        plan.append(("held_grown", [["held", grow, held, b, a] for b in bl
                                    for a in ("S-hole", "S-shuffled", "S-demo", "S-enum")]))
        for b in bl:
            plan.append((f"held_static_{b}", [["held", grow, held, b, "static", "--shard", f"{i}/{w}",
                                               "--controller", ctrl] for i in range(w)]))
    cap_s = cfg["phase2_cpu_ceiling_h"] * 3600
    with E.open_write(os.path.join(run_dir, "phase2.log"), "a") as log:
        for name, cmds in plan:
            if rec["stages"].get(name, {}).get("status") == "done":
                continue
            spent = sum(v.get("cpu_s", 0) for v in rec["stages"].values())
            if spent > cap_s:
                rec["status"] = f"INCOMPLETE: CPU ceiling {cfg['phase2_cpu_ceiling_h']} h reached before {name}"
                break
            c0, w0 = child_cpu(), time.time()
            rcs = launch(cmds, log, env)
            rec["stages"][name] = {"status": "done" if not any(rcs) else f"failed {rcs}",
                                   "cpu_s": round(child_cpu() - c0, 1), "wall_s": round(time.time() - w0, 1)}
            E.dump(stages_path, rec)
            if any(rcs):
                rec["status"] = f"FAILED at {name}"
                break
        else:
            rec["status"] = "complete"
    b = BN.run()
    E.dump(os.path.join(run_dir, f"BENCH_end_{benches.replace(',', '_')}.json"), b)
    E.dump(stages_path, rec)
    E.dump(os.path.join(run_dir, "OUTPUT_MANIFEST.json"), manifest(run_dir))
    print(json.dumps({"status": rec["status"], "stages": rec["stages"]}), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
