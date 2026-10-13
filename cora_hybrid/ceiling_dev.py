"""Hybrid ceiling test on a development set (CPU only; never on C2's evaluation tasks).

The question: if a neural proposer were right, could CORA express and certify
a program for that answer? This bounds what "neural proposes, CORA certifies"
can add, before any GPU time is spent.

  python -m cora_hybrid.ceiling_dev   -> outputs/hybrid_c2_dev/

Development set C2-dev:
- C2's 12 generator families, seeds 9100-9104 (5 per family, 60 tasks);
- disjoint from C2's evaluation seeds 9000-9009, and never used to score C2.

The frozen native_v1 notebook runs unchanged, twice:
- arm A, native: the 3 training demonstrations, then the test input;
- arm B, answer-given: the same 3 demonstrations plus the true test pair as
  a 4th demonstration, then the same test input.

The ceiling counts tasks whose test prediction is exact in arm B but not in
arm A. In arm B the answer is a demonstration, so the run says only whether
CORA's language can express and certify the rule. It is never an accuracy
claim.

It waits for the C2 CORA_ONLY run to finish (its run_meta.json), so the two
never compete for the CPU.
"""
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_hybrid import corpus_c2 as C2                               # noqa: E402

OUT = os.path.join(HERE, "outputs", "hybrid_c2_dev")
WAIT_FOR = os.path.join(HERE, "outputs", "hybrid_c2", "native_run", "run_meta.json")
SEEDS = range(9100, 9105)


def build():
    tasks = {}
    for fi, fam in enumerate(C2.FAMILIES):
        for s in SEEDS:
            rng = np.random.default_rng(100_000 * fi + s)
            demos = [C2._demo(rng, fam) for _ in range(4)]
            tid = f"dev{fi:02d}{s - 9100}"
            tasks[tid] = {"family": fam, "train": [[a.tolist(), b.tolist()] for a, b in demos[:3]],
                          "test": [demos[3][0].tolist(), demos[3][1].tolist()]}
    return tasks


def run_arm(name, challenges):
    base = os.path.join(OUT, name)
    shutil.rmtree(base, ignore_errors=True)
    comp = os.path.join(base, "input", "arc-prize-2026-arc-agi-2")
    data = os.path.join(base, "input", "arc-native-baseline")
    work = os.path.join(base, "working")
    for d in (comp, data, work):
        os.makedirs(d)
    json.dump(challenges, open(os.path.join(comp, "arc-agi_test_challenges.json"), "w"))
    json.dump({k: [{"attempt_1": [[0]], "attempt_2": [[0]]}] for k in challenges}, open(os.path.join(comp, "sample_submission.json"), "w"))
    shutil.copy(os.path.join(HERE, "kaggle", "native_v1", "arc_native_baseline_v1.tar.gz"), data)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ARC_", "K_"))}
    env.update(K_INPUT=os.path.join(base, "input"), K_WORK=work, K_WORKERS="4")
    t0 = time.time()
    rc = subprocess.call([sys.executable, os.path.join(HERE, "kaggle", "native_v1", "notebook.py")], env=env, cwd=work,
                         stdout=open(os.path.join(base, "notebook.log"), "w"), stderr=subprocess.STDOUT)
    return rc, round(time.time() - t0, 1), os.path.join(work, "submission.json")


def main():
    while not os.path.exists(WAIT_FOR):
        time.sleep(300)
    os.makedirs(OUT, exist_ok=True)
    tasks = build()
    json.dump(tasks, open(os.path.join(OUT, "dev_tasks.json"), "w"))
    arm_a = {k: {"train": [{"input": a, "output": b} for a, b in t["train"]], "test": [{"input": t["test"][0]}]} for k, t in tasks.items()}
    arm_b = {k: {"train": [{"input": a, "output": b} for a, b in t["train"] + [t["test"]]], "test": [{"input": t["test"][0]}]}
             for k, t in tasks.items()}
    res = {}
    for name, ch in (("A_native", arm_a), ("B_answer_given", arm_b)):
        rc, wall, sub_path = run_arm(name, ch)
        sub = json.load(open(sub_path)) if os.path.exists(sub_path) else {}
        exact = {k: any(sub.get(k, [{}])[0].get(a) == tasks[k]["test"][1] for a in ("attempt_1", "attempt_2")) for k in tasks}
        res[name] = {"returncode": rc, "wall_s": wall, "exact": exact}
    a, b = res["A_native"]["exact"], res["B_answer_given"]["exact"]
    fam = {}
    for k, t in tasks.items():
        f = fam.setdefault(t["family"], {"tasks": 0, "A": 0, "B": 0, "B_only": 0})
        f["tasks"] += 1; f["A"] += a[k]; f["B"] += b[k]; f["B_only"] += b[k] and not a[k]
    summary = {"tasks": len(tasks), "A_native_exact": sum(a.values()), "B_answer_given_exact": sum(b.values()),
               "ceiling_B_only": sum(b[k] and not a[k] for k in tasks), "A_only": sum(a[k] and not b[k] for k in tasks),
               "by_family": fam, "wall_s": {n: r["wall_s"] for n, r in res.items()}, "returncodes": {n: r["returncode"] for n, r in res.items()}}
    json.dump(summary, open(os.path.join(OUT, "ceiling_summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
