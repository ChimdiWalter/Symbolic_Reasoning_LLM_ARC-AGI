"""One detached run of the library-rivals test: rows, seal, score (PROTOCOL.md sections 5 to 8).

    python3 -I run.py phase all runs/main         after the GO: run every arm on every held task, seal, score
    python3 -I run.py phase score runs/main       recovery only: score from an existing valid seal when the run
                                                  stopped after the seal and before any claim (nothing is re-run)
    python3 -I run.py phase dry OUT_DIR [N]       before the GO: the same path on the first N source tasks of each
                                                  benchmark, scored against source outputs (no held task is searched
                                                  and no held output is decoded)

Rows: OUT_DIR/rows/<bench>/<arm>.jsonl, one per task, durable: a restart of the same command skips tasks already
written (a partial last line left by a crash is removed first). A search that raises gives an "arm_error" row (no
answer), counted per arm. The seal (OUT_DIR/PREDICTIONS_SEAL.json) is written once every arm has exactly one row per
task, before any output is opened. Before scoring, the freeze, the GO and every loaded module are checked again.
"""
import json
import os
import platform
import sys
import time
import traceback

from lr import env as E, gate as GT, arms as AR, report as RP
from ngrow import data as DT

CFG = os.path.join(E.STUDY, "config", "CONFIG.json")
MAIN = os.path.join(E.STUDY, "runs", "main")


def cfg():
    return E.load(CFG)


def task_list(mode, n=None):
    """[(bench, family, task id)]: held halves (mode all) or the first n source tasks of each benchmark (dry)."""
    out = []
    for b in DT.BENCHMARKS:
        half = DT.half("held" if mode == "all" else "source", (b,))
        out += half if mode == "all" else half[:int(n)]
    return out


def read_rows(path):
    if not os.path.exists(path):
        return {}
    rows = {}
    for line in open(path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            rows[r["task"]] = r
    return rows


def repair(path):
    """Before resuming: drop a partial last line (a crash while writing); never touches a complete line."""
    if not os.path.exists(path):
        return 0
    lines = open(path, encoding="utf-8").read().split("\n")
    keep, dropped = [], 0
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            json.loads(line)
            keep.append(line)
        except ValueError:
            if i < len(lines) - 2:
                raise GT.GateRefused(f"{path}: a malformed line that is not the last one")
            dropped += 1
    if dropped:
        with E.open_write(path) as f:
            f.write("".join(x + "\n" for x in keep))
    return dropped


def run_rows(out_dir, mode, go_sha, n=None):
    c = cfg()
    tl = task_list(mode, n)
    tasks = {b: DT.tasks(b) for b in DT.BENCHMARKS}
    for b in DT.BENCHMARKS:
        ids = [(f, t) for bb, f, t in tl if bb == b]
        for arm in AR.ARMS:
            path = os.path.join(out_dir, "rows", b, f"{arm}.jsonl")
            repair(path)
            done = read_rows(path)
            g = AR.grammar(arm, b)
            lib = AR.library_digest(arm, b)
            for f, t in ids:
                if t in done:
                    continue
                task = tasks[b][t]
                t0 = time.time()
                try:
                    r = AR.run_task(g, {"train": task["train"], "test_inputs": task["test_inputs"]},
                                    c["budget_executions"], c["cpu_safety_cap_s"])
                except Exception as e:                                      # noqa: BLE001
                    r = {"fit": False, "program": None, "level_complete": None, "stop": "arm_error", "calls": None,
                         "cpu_s": None, "closure_capped": None, "preds": None,
                         "error": f"{type(e).__name__}: {e}"[:300] + " | " + traceback.format_exc()[-300:]}
                row = {"bench": b, "family": f, "task": t, "arm": arm, "go_sha256": go_sha, "library_sha256": lib,
                       "g0_sha256": AR.shared()["g0b"].sha, "wall_s": round(time.time() - t0, 3), **r}
                with E.open_write(path, "a") as fh:
                    fh.write(json.dumps(row, default=list) + "\n")
            print(json.dumps({"bench": b, "arm": arm, "rows": len(read_rows(path))}), flush=True)
    return tl


def valid_preds(preds, n_test):
    """At most two attempts, each one rectangular grid of scalar cells per test input. A cell that is not an
    integer from 0 to 9 is a legitimate wrong answer (the scorer counts that attempt incorrect); it never makes the
    row invalid."""
    if preds is None:
        return True
    return isinstance(preds, list) and 1 <= len(preds) <= 2 and all(
        isinstance(a, list) and len(a) == n_test and all(
            isinstance(gr, list) and gr and all(isinstance(rw, list) and rw and len(rw) == len(gr[0]) and
                                                all(not isinstance(v, (list, dict)) for v in rw) for rw in gr)
            for gr in a) for a in preds)


def seal(out_dir, tl, go_sha):
    path = os.path.join(out_dir, "PREDICTIONS_SEAL.json")
    if os.path.exists(path):
        raise GT.GateRefused("a seal already exists")
    tasks = {b: DT.tasks(b) for b in DT.BENCHMARKS}
    problems, files = [], {}
    for b in DT.BENCHMARKS:
        ids = {t for bb, _, t in tl if bb == b}
        for arm in AR.ARMS:
            p = os.path.join(out_dir, "rows", b, f"{arm}.jsonl")
            rows = read_rows(p)
            n_lines = sum(1 for line in open(p, encoding="utf-8") if line.strip()) if os.path.exists(p) else 0
            if set(rows) != ids or n_lines != len(ids):
                problems.append(f"{b}/{arm}: rows do not match the task list ({len(rows)} rows, {n_lines} lines)")
            for t, r in rows.items():
                if r["go_sha256"] != go_sha or not valid_preds(r["preds"], len(tasks[b][t]["test_inputs"])) or \
                        (r["fit"] and not r["preds"]):
                    problems.append(f"{b}/{arm}/{t}: invalid row")
            if os.path.exists(p):
                files[os.path.relpath(p, out_dir)] = E.sha_file(p)
    if problems:
        raise GT.GateRefused("seal refused: " + "; ".join(problems[:10]))
    E.dump(path, {"go_sha256": go_sha, "files_sha256": files, "tasks": len(tl),
                  "python": sys.version, "platform": platform.platform(),
                  "sealed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    return path


def main(cmd, out_dir, n="2"):
    out_dir = os.path.abspath(out_dir)
    E.check_write(out_dir)
    if cmd == "all":
        if os.path.realpath(out_dir) != os.path.realpath(MAIN):
            raise GT.GateRefused("the held run writes only to runs/main")
        go = GT.require_go()
        GT.check_loaded_modules()
        tl = run_rows(out_dir, "all", go)
        seal(out_dir, tl, go)
        if GT.require_go(at_scoring=True) != go:
            raise GT.GateRefused("the GO changed during the run")
        GT.check_loaded_modules()
        RP.score(out_dir, tl, go, dry=False)
    elif cmd == "score":
        # recovery only: the run stopped after a valid seal and before any claim; nothing is searched again
        if os.path.realpath(out_dir) != os.path.realpath(MAIN):
            raise GT.GateRefused("scoring from a seal is allowed for runs/main only")
        go = GT.require_go(at_scoring=True)
        GT.check_loaded_modules()
        if not os.path.exists(os.path.join(out_dir, "PREDICTIONS_SEAL.json")):
            raise GT.GateRefused("no seal: nothing to score")
        RP.score(out_dir, task_list("all"), go, dry=False)
    elif cmd == "dry":
        if os.path.realpath(out_dir) == os.path.realpath(MAIN):
            raise GT.GateRefused("the dry run may not write to runs/main")
        if os.path.exists(GT.FREEZE):
            GT.check_freeze()
        tl = run_rows(out_dir, "dry", "dry-run", n)
        seal(out_dir, tl, "dry-run")
        RP.score(out_dir, tl, "dry-run", dry=True)
    else:
        raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main(*sys.argv[1:])
