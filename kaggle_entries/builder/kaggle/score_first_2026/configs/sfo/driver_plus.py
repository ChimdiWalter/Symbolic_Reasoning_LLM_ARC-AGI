"""Configuration O+: CORA-only CPU entry with an ordered list of constructor packages (the constructor hook).

  python -m sfo.driver_plus --challenges C --out RUN_DIR --submission SUB --packages JSON
      [--deadline-s 39600] [--reserve-s 600] [--shards N] [--grace-s 10] [--poll-s 20]

`--packages`: a JSON list in priority order, each {"name", "entry", "cpu_s", "wall_s", "details"}. Example: cast_v1
(cast_candidates, 15/30, details 1) then the reviewed R29 package (candidates, 12/24, details 0; its API has no
details argument).

Attempts, per query:
- attempt_1 is the first package's valid answer, in priority order;
- attempt_2 is the next distinct valid answer from another package;
- otherwise each attempt is the fixed fallback, a copy of the test input.

Packages run one after another, each over every task in `--shards` side processes (`sfb.cast_side`). Each puzzle
runs in a fresh forked child, with the package's own caps and process-level backstops. The submission is valid
before any work starts, is rebuilt atomically every poll, and is written once more at the end. Total-time guard: no
task starts after deadline minus reserve, and at the deadline every side process group is killed. A package that
has not finished contributes the results it has. Any failure keeps the last valid file.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time

from sfb.cast_side import atomic_json, valid_grid


def copy_of(g):
    return [[int(v) for v in row] for row in g]


def package_answers(r, n):
    if not isinstance(r, dict) or r.get("status") != "OK":
        return [None] * n
    g = r.get("grids")
    if not isinstance(g, list) or len(g) != n:
        return [None] * n
    return [x if x is not None and valid_grid(x) else None for x in g]


def build_submission(ch, results):
    """results: one {task_id: cast_side result} per package, in priority order."""
    sub, counts = {}, {"outputs": 0, "attempt_1_from_package": 0, "attempt_2_from_package": 0,
                       "per_package_answers": [0] * len(results)}
    for tid, t in ch.items():
        n = len(t["test"])
        per = [package_answers(res.get(tid), n) for res in results]
        entry = []
        for j, x in enumerate(t["test"]):
            fb = copy_of(x["input"])
            got = []
            for k, ans in enumerate(per):
                if ans[j] is not None:
                    counts["per_package_answers"][k] += 1
                    got.append(ans[j])
            a1 = got[0] if got else fb
            a2 = next((g for g in got[1:] if g != a1), None)
            counts["attempt_1_from_package"] += bool(got)
            counts["attempt_2_from_package"] += a2 is not None
            entry.append({"attempt_1": a1, "attempt_2": a2 if a2 is not None else copy_of(x["input"])})
            counts["outputs"] += 1
        sub[tid] = entry
    return sub, counts


def schema_problems(sub, ch):
    problems = []
    for tid, t in ch.items():
        e = sub.get(tid)
        if not isinstance(e, list) or len(e) != len(t["test"]):
            problems.append(f"{tid}: wrong entry count")
            continue
        for j, a in enumerate(e):
            if not isinstance(a, dict) or set(a) != {"attempt_1", "attempt_2"} or \
                    not valid_grid(a["attempt_1"]) or not valid_grid(a["attempt_2"]):
                problems.append(f"{tid}[{j}]: bad entry")
    if set(sub) - set(ch):
        problems.append("unknown task ids")
    return problems


def read_results(dirs, ids):
    res = {}
    for d in dirs:
        for tid in ids:
            p = os.path.join(d, f"{tid}.json")
            if tid in res or not os.path.exists(p):
                continue
            try:
                with open(p) as f:
                    res[tid] = json.load(f)
            except (OSError, ValueError):
                pass
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenges", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--packages", required=True)
    ap.add_argument("--deadline-s", type=float, default=11 * 3600)
    ap.add_argument("--reserve-s", type=float, default=600)
    ap.add_argument("--shards", type=int, default=0)
    ap.add_argument("--grace-s", type=float, default=10.0)
    ap.add_argument("--poll-s", type=float, default=20.0)
    ap.add_argument("--code-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args(argv)
    t0 = time.time()
    pkgs = json.loads(a.packages)
    os.makedirs(a.out, exist_ok=True)
    with open(a.challenges) as f:
        ch = json.load(f)
    ids = list(ch)
    sub, _ = build_submission(ch, [{} for _ in pkgs])
    atomic_json(a.submission, sub)                             # valid before any CORA work
    n = a.shards or min(4, os.cpu_count() or 1)
    n = max(1, min(n, len(ids) or 1))
    shards = [ids[k::n] for k in range(n)]
    deadline = t0 + a.deadline_s
    cast_deadline = deadline - a.reserve_s
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1", PYTHONHASHSEED="0", PYTHONUNBUFFERED="1")
    st = {"t_start": t0, "deadline": deadline, "shards": n, "n_tasks": len(ids), "packages": pkgs,
          "python": sys.version.split()[0], "cpu_count": os.cpu_count(), "per_package": []}
    dirs_per_pkg = []
    stopped = None
    for k, pk in enumerate(pkgs):
        dirs, procs = [], []
        t_pk = time.time()
        for s, part in enumerate(shards):
            d = os.path.join(a.out, f"pkg{k}_{pk['name']}", f"shard_{s}")
            os.makedirs(d, exist_ok=True)
            dirs.append(d)
            cmd = [sys.executable, "-m", "sfb.cast_side", "--challenges", a.challenges, "--out", d,
                   "--package", pk["name"], "--entry", pk["entry"], "--deadline", str(cast_deadline),
                   "--cpu-s", str(pk["cpu_s"]), "--wall-s", str(pk["wall_s"]), "--grace-s", str(a.grace_s),
                   "--details", str(int(pk.get("details", 1))), "--nice", "0", "--task-ids", ",".join(part)]
            log = open(d + ".log", "w")
            procs.append(subprocess.Popen(cmd, cwd=a.code_dir, env=env, stdout=log, stderr=log,
                                          start_new_session=True))
        dirs_per_pkg.append(dirs)
        while True:
            t_poll = time.time() + a.poll_s
            while time.time() < t_poll and any(p.poll() is None for p in procs):
                time.sleep(1.0)
            try:
                sub, counts = build_submission(ch, [read_results(ds, ids) for ds in dirs_per_pkg])
                if not schema_problems(sub, ch):
                    atomic_json(a.submission, sub)
            except Exception as e:                             # noqa: BLE001  keep the last valid file
                st["poll_error"] = repr(e)[:200]
            st.update(t=time.time(), package_running=k, alive=[p.poll() is None for p in procs])
            atomic_json(os.path.join(a.out, "status.json"), st)
            if not any(p.poll() is None for p in procs):
                break
            if time.time() > deadline:
                stopped = "deadline reached; side processes killed"
                break
        for p in procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except OSError:
                    pass
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
        res_k = read_results(dirs, ids)
        statuses = {}
        for r in res_k.values():
            statuses[r.get("status")] = statuses.get(r.get("status"), 0) + 1
        st["per_package"].append({"name": pk["name"], "wall_s": round(time.time() - t_pk, 2),
                                  "tasks_with_result": len(res_k), "statuses": statuses,
                                  "child_cpu_s": round(sum(float((r.get("child") or {}).get("cpu_s") or 0)
                                                           for r in res_k.values()), 2)})
        if stopped:
            st["watchdog"] = stopped
            break
    results = [read_results(ds, ids) for ds in dirs_per_pkg] + [{} for _ in range(len(pkgs) - len(dirs_per_pkg))]
    sub, counts = build_submission(ch, results)
    problems = schema_problems(sub, ch)
    if not problems:
        atomic_json(a.submission, sub)
    st.update(t=time.time(), wall_s=round(time.time() - t0, 2), schema_problems=problems[:20],
              n_schema_problems=len(problems), **counts)
    atomic_json(os.path.join(a.out, "status.json"), st)
    print(json.dumps({k: st.get(k) for k in ("wall_s", "n_tasks", "outputs", "attempt_1_from_package",
                                              "attempt_2_from_package", "per_package_answers",
                                              "n_schema_problems")}), flush=True)


if __name__ == "__main__":
    main()
