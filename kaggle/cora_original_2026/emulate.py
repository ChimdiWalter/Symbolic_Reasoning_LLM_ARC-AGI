#!/usr/bin/env python3
"""Offline Kaggle emulation of CORA-ONLY-G3 on Athe (never uploads; small task counts only; run under nice 10).

  python kaggle/cora_original_2026/emulate.py fixtures   synthetic tasks: several test inputs, 1x1, 30x30, a shape change
  python kaggle/cora_original_2026/emulate.py dev3       3 exposed development tasks (inputs only), native + G3
  python kaggle/cora_original_2026/emulate.py failure    the native harness forced to fail: CORA's fallback path
  python kaggle/cora_original_2026/emulate.py devscore   fixtures in dev mode: the separate scoring step

Each builds a fresh Kaggle-style tree under K_EMU_ROOT (default: a new temporary dir): input/<competition>/ with the
chosen challenges (dev mode adds evaluation solutions, which only the scoring step may open), input/<dataset>/ with the
unpacked package (as Kaggle unpacks .tar.gz files), working/. The notebook module runs as on Kaggle, with one worker.
The report (emu_report_<mode>.json in the working dir) validates submission.json independently.
"""
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TAR = os.path.join(REPO, "outputs", "kaggle_deploy", "cora_original_2026", "dataset", "cora_only_g3_solver.tar.gz")
COMP = "arc-prize-2026-arc-agi-2"


def fixtures():
    """Tasks with known answers: a recolour (g3 should fit it), two test inputs, 1x1 and 30x30 grids, a crop."""
    def recolour(g):
        return [[5 if v == 1 else v for v in r] for r in g]
    a = [[0, 1, 0], [1, 1, 0], [0, 0, 1]]
    b = [[1, 0, 0, 1], [0, 0, 1, 0]]
    c = [[0, 0, 1], [0, 1, 1]]
    d = [[1, 1], [0, 1]]
    tasks = {"fx_recolour_2tests": {"train": [{"input": a, "output": recolour(a)}, {"input": b, "output": recolour(b)}],
                                    "test": [{"input": c}, {"input": d}]},
             "fx_1x1": {"train": [{"input": [[3]], "output": [[3]]}, {"input": [[4]], "output": [[4]]}],
                        "test": [{"input": [[7]]}]},
             "fx_30x30": {"train": [{"input": [[(i + j) % 3 for j in range(30)] for i in range(30)],
                                     "output": [[(i + j) % 3 for j in range(30)] for i in range(30)]}],
                          "test": [{"input": [[(i * j) % 4 for j in range(30)] for i in range(30)]}]}}
    sols = {"fx_recolour_2tests": [recolour(c), recolour(d)], "fx_1x1": [[[7]]],
            "fx_30x30": [[[(i * j) % 4 for j in range(30)] for i in range(30)]]}
    return tasks, sols


def build(root, mode):
    comp = os.path.join(root, "input", COMP)
    ds = os.path.join(root, "input", "cora-only-g3-solver-2026")
    work = os.path.join(root, "working")
    for p in (comp, ds, work):
        os.makedirs(p, exist_ok=True)
    with tarfile.open(TAR) as t:
        t.extractall(ds)
    if mode == "dev3":
        ch = json.load(open(os.path.join(REPO, "data", "arc", "dev60_challenges.json")))
        tasks, sols = {k: ch[k] for k in list(ch)[:3]}, None
    else:
        tasks, sols = fixtures()
    name = "arc-agi_evaluation_challenges.json" if mode == "devscore" else "arc-agi_test_challenges.json"
    json.dump(tasks, open(os.path.join(comp, name), "w"))
    if mode == "devscore":
        json.dump(sols, open(os.path.join(comp, "arc-agi_evaluation_solutions.json"), "w"))
    return comp, ds, work, tasks, sols


def main():
    mode = sys.argv[1]
    root = os.environ.get("K_EMU_ROOT") or tempfile.mkdtemp(prefix=f"cora_emu_{mode}_")
    comp, ds, work, tasks, sols = build(root, mode)
    env = dict(os.environ, K_INPUT=os.path.join(root, "input"), K_WORK=work, K_WORKERS="1",
               K_NATIVE_BUDGET_S="0" if mode == "failure" else "900", K_DEADLINE_S="2400",
               K_MODE="dev" if mode == "devscore" else "submit", K_VARIANTS="G3")
    if mode == "failure":
        env["K_FORCE_NATIVE_FAIL"] = "1"
    code = open(os.path.join(HERE, "cora_only.py")).read()
    if mode == "devscore":
        code += "\nscore_dev()\n"
    t = time.time()
    r = subprocess.run(["nice", "-n", "10", sys.executable, "-c", code], env=env, capture_output=True, text=True)
    sub_path = os.path.join(work, "submission.json")
    sub = json.load(open(sub_path)) if os.path.exists(sub_path) else {}
    probs = []
    if list(sub) != list(tasks):
        probs.append("ids/order")
    for tid, task in tasks.items():
        e = sub.get(tid, [])
        if len(e) != len(task["test"]):
            probs.append(f"{tid}: positions")
        for x in e:
            for k in ("attempt_1", "attempt_2"):
                g = x.get(k)
                if not (isinstance(g, list) and g and all(isinstance(row, list) and len(row) == len(g[0]) for row in g)
                        and all(isinstance(v, int) and 0 <= v <= 9 for row in g for v in row)):
                    probs.append(f"{tid}: {k} invalid")
    rep = {"mode": mode, "root": root, "returncode": r.returncode, "wall_s": round(time.time() - t, 1),
           "schema_problems": probs, "tasks": len(tasks), "positions": sum(len(v) for v in sub.values()),
           "stdout_tail": r.stdout[-1500:], "stderr_tail": r.stderr[-1500:]}
    for f in ("execution_manifest.json", "attempt_provenance.json", "dev_score.json"):
        if os.path.exists(os.path.join(work, f)):
            rep[f] = json.load(open(os.path.join(work, f)))
    if sols and mode != "devscore":
        rep["fixture_correct"] = {tid: [any(a == sols[tid][i] for a in (e["attempt_1"], e["attempt_2"]))
                                        for i, e in enumerate(sub.get(tid, []))] for tid in tasks}
    json.dump(rep, open(os.path.join(work, f"emu_report_{mode}.json"), "w"), indent=1)
    print(json.dumps({k: rep[k] for k in ("mode", "returncode", "wall_s", "schema_problems", "positions")}),
          json.dumps(rep.get("fixture_correct")), r.stdout[-800:], r.stderr[-600:], sep="\n")


if __name__ == "__main__":
    main()
