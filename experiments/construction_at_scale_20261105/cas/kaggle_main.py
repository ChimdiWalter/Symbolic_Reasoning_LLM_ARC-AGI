"""One world's phase 2 run inside a private Kaggle kernel (CPU only, internet off), or locally.

    python -m cas.kaggle_main WORLD WORLD_DIR [CPU_CAP_H]

Stages, each resumable (finished units are skipped); at most four processes at a time (Kaggle's CPU kernels have
four cores):
  1 controller (one process);
  2 specification methods S-hole, S-demo, S-shuffled (one process) beside matched search on excluded tasks (two
    child processes at a time, 8 GB of address space each);
  3 S-enum, seeds 0, 1 and 2 (three processes), each with its own copy of the stage 2 gate cache, beside the first
    C7M_M_FIRST matched searches on motivating tasks (one child process); these need the finished S-hole units,
    because a motivating task's matched search gets at least S-hole's complete charged CPU on it;
  4 the remaining matched searches on motivating tasks (three child processes at a time);
  5 c7m_rerun: every matched search stopped by memory (a MemoryError, or a child killed with return code -9) runs
    once more, alone, with a 20 GB address-space limit; that result stands;
  6 commit: the committed predictions of every unit, before any label is read (INCOMPLETE if any work is missing);
  7 evaluation (one process).
Before the stages the world's task files are verified against their manifest, and cas/bench.py measures the
kernel's speed alone and with four copies at once (the busiest stage's concurrency); the factor (concurrent median /
Athe's lone reference, clipped to [1, 3]) is passed to every stage as CAS_CPU_SCALE, and the benchmark runs again
at the end.
Stop rule: no new stage starts once the children's CPU time exceeds CPU_CAP_H (default 15 CPU-h for one world);
the run is then INCOMPLETE. A failed stage makes the run FAILED. Either way, no later stage runs and the world is
not analysed. After every stage the outputs are packed to CAS_PACK_DIR (when set) so that a lost session keeps
what finished. Writes WORLD_DIR/runs/STAGES.json (CPU and wall time per stage, os.cpu_count, the benchmarks) and
WORLD_DIR/runs/OUTPUT_MANIFEST.json (sha256 of every output file).
"""
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time

from cas import env as E

C7M_M_FIRST = 12      # matched searches on motivating tasks run beside the S-enum seeds (one worker) before the rest


def child_cpu():
    t = os.times()
    return t.children_user + t.children_system


def run_all(cmds, log):
    procs = [subprocess.Popen([sys.executable, "-m", "cas.run_world"] + c, cwd=E.STUDY, stdout=log, stderr=log)
             for c in cmds]
    return [p.wait() for p in procs]


def manifest(wd):
    out = {}
    root = os.path.join(wd, "runs")
    for d, _, files in os.walk(root):
        for f in sorted(files):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, wd)
            if rel.endswith(".tmp") or rel == os.path.join("runs", "OUTPUT_MANIFEST.json"):
                continue
            with open(p, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return dict(sorted(out.items()))


def pack(world, wd):
    d = os.environ.get("CAS_PACK_DIR")
    if not d:
        return None
    out = os.path.join(d, f"{world}_outputs.tar.gz")
    tmp = out + ".tmp"
    with tarfile.open(tmp, "w:gz") as tf:
        tf.add(os.path.join(wd, "runs"), arcname=f"{world}/runs")
    os.replace(tmp, out)
    return out


def main(world, wd, cap_h=15.0):
    wd = os.path.realpath(wd)
    from cas import run_world as RW
    RW.verify_world(wd)
    os.makedirs(os.path.join(wd, "runs"), exist_ok=True)
    stages_path = os.path.join(wd, "runs", "STAGES.json")
    rec = E.load(stages_path) if os.path.exists(stages_path) else {"world": world, "stages": {}}
    rec["cpu_count"] = os.cpu_count()
    rec["task_manifest_sha256"] = E.sha256(os.path.join(wd, "partitions", "PARTITIONS_MANIFEST.json"))
    rec["archive_sha256"] = os.environ.get("CAS_ARCHIVE_SHA256")
    if "cpu_scale" not in rec:
        bench = os.path.join(wd, "runs", "BENCH_start.json")
        subprocess.run([sys.executable, "-m", "cas.bench", bench, "both"], cwd=E.STUDY, check=True,
                       stdout=subprocess.DEVNULL)
        ref = E.load(os.path.join(E.STUDY, "config", "STUDY_CONFIG.json"))["bench_reference_cpu_s"]
        from cas import bench as BN
        b = E.load(bench)
        rec["cpu_scale"] = BN.scale(ref, b)
        rec["bench_reference_cpu_s"] = ref
        rec["bench_concurrency"] = BN.CONCURRENT_COPIES
        rec["bench_median_cpu_s"] = b["concurrent"]["median_cpu_s"]
        rec["bench_lone_median_cpu_s"] = b["lone"]["median_cpu_s"]
        E.dump(stages_path, rec)
    os.environ["CAS_CPU_SCALE"] = str(rec["cpu_scale"])
    plan = [("controller", [["controller", wd]]),
            ("spec_and_c7m_E", [["spec", wd], ["c7m", wd, "E", "2"]]),
            ("enum_and_c7m_M_first", [["enum", wd, str(s)] for s in (0, 1, 2)] + [["c7m", wd, "M", "1", str(C7M_M_FIRST)]]),
            ("c7m_M_rest", [["c7m", wd, "M", "3"]]),
            ("c7m_rerun", [["c7m_rerun", wd]]),
            ("commit", [["commit", wd]]),
            ("evaluate", [["evaluate", wd]])]
    with E.open_write(os.path.join(wd, "runs", "kaggle_main.log"), "a") as log:
        for name, cmds in plan:
            if rec["stages"].get(name, {}).get("status") == "done":
                continue
            spent = sum(v.get("cpu_s", 0) for v in rec["stages"].values()) / 3600
            if spent > cap_h:
                rec["status"] = f"INCOMPLETE: CPU cap {cap_h} h reached before stage {name}"
                break
            c0, w0 = child_cpu(), time.time()
            rcs = run_all(cmds, log)
            rec["stages"][name] = {"status": "done" if all(r == 0 for r in rcs) else f"failed {rcs}",
                                   "cpu_s": round(child_cpu() - c0, 1), "wall_s": round(time.time() - w0, 1)}
            E.dump(stages_path, rec)
            E.dump(os.path.join(wd, "runs", "OUTPUT_MANIFEST.json"), manifest(wd))
            pack(world, wd)
            if any(rcs):
                rec["status"] = f"FAILED at stage {name}"
                break
        else:
            rec["status"] = "complete"
    bench_end = os.path.join(wd, "runs", "BENCH_end.json")
    rc_end = subprocess.run([sys.executable, "-m", "cas.bench", bench_end, "both"], cwd=E.STUDY,
                            stdout=subprocess.DEVNULL).returncode
    if not os.path.exists(bench_end):                       # always present: a failed end benchmark is recorded
        E.dump(bench_end, {"failed": True, "returncode": rc_end, "concurrent": None, "lone": None})
    b_end = E.load(bench_end)
    rec["bench_end_median_cpu_s"] = (b_end.get("concurrent") or {}).get("median_cpu_s")
    E.dump(stages_path, rec)
    E.dump(os.path.join(wd, "runs", "OUTPUT_MANIFEST.json"), manifest(wd))
    pack(world, wd)
    print(json.dumps({"world": world, "status": rec["status"], "stages": rec["stages"]}), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(float(a) for a in sys.argv[3:4]))
