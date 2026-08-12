#!/usr/bin/env python3
"""Neural-LOO gate for TRM renders + empirical precision measurement.

Applies the engine's acceptance protocol to the TRM: for a task with N
train pairs, run N folds; in fold i the demos are the OTHER pairs and
the query is pair i's input — require exact match on pair i's output.
Pass all folds -> the task's test render is "neural-LOO gated".

Epistemic status (weaker than the symbolic gate, by design):
  - symbolic gate RE-DERIVES the program per fold; here the weights are
    frozen, so folds test generalization across query slots only.
  - meaningless on ARC training tasks (model trained on them, incl.
    test pairs) — only run on tasks the model never saw (eval/hidden).
  - precision is MEASURED here, never assumed: among gated eval tasks,
    what fraction of test renders are exactly correct?

Usage:
  python trm/certify.py [ckpt] [eval|training] [limit]
Defaults: trm/checkpoints/ema_only.pt, eval, all tasks.
Writes per-task results to trm/outputs/certify_<split>.jsonl (realtime,
resumable reporting) and prints the precision table at the end.
"""
import json
import os
import sys

import numpy as np
import torch

from trm.infer import TRMSolver, encode_task, decode_grid, N_SUP
from trm.model import CANVAS
from trm.build_dataset import PAD

OUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")


def _fits(g):
    return len(g) <= CANVAS and len(g[0]) <= CANVAS


@torch.no_grad()
def loo_folds(solver, pairs):
    """Return (folds_passed, folds_total). Batches all folds together."""
    xs = []
    for i in range(len(pairs)):
        demos = [pairs[j] for j in range(len(pairs)) if j != i]
        xs.append(encode_task(demos, pairs[i][0]))
    x = torch.from_numpy(np.stack(xs).astype(np.int64)).to(solver.device)
    y = z = None
    for _ in range(N_SUP):
        logits, y, z, halt = solver.model(x, y, z)
    preds = logits.argmax(-1).view(-1, CANVAS, CANVAS).cpu().numpy()
    passed = 0
    for i, (_, out) in enumerate(pairs):
        if decode_grid(preds[i]) == [list(map(int, r)) for r in out]:
            passed += 1
    return passed, len(pairs)


def main():
    ckpt = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "checkpoints", "ema_only.pt")
    split = sys.argv[2] if len(sys.argv) > 2 else "eval"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    name = "evaluation" if split == "eval" else "training"
    chal = json.load(open(f"data/arc/arc-agi_{name}_challenges.json"))
    sols = json.load(open(f"data/arc/arc-agi_{name}_solutions.json"))
    solver = TRMSolver(ckpt)
    print(f"ckpt epoch={solver.epoch} split={split} device={solver.device}",
          flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"certify_{split}.jsonl")
    done = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            done = {json.loads(l)["task"] for l in f if l.strip()}

    tids = sorted(chal)[:limit]
    gated = gated_correct = total = ungated_correct = skipped = 0
    with open(out_path, "a") as fout:
        for n, tid in enumerate(tids):
            if tid in done:
                continue
            task = chal[tid]
            pairs = [(p["input"], p["output"]) for p in task["train"]]
            if (len(pairs) < 2
                    or any(not _fits(g) for pr in pairs for g in pr)
                    or any(not _fits(t["input"]) for t in task["test"])):
                skipped += 1
                fout.write(json.dumps({"task": tid, "skip": True}) + "\n")
                fout.flush()
                continue
            passed, folds = loo_folds(solver, pairs)
            preds = solver.solve(task)
            correct = all(
                p is not None and i < len(sols[tid]) and p == sols[tid][i]
                for i, p in enumerate(preds)) and len(preds) > 0
            total += 1
            is_gated = passed == folds
            if is_gated:
                gated += 1
                gated_correct += int(correct)
            else:
                ungated_correct += int(correct)
            fout.write(json.dumps({
                "task": tid, "folds": f"{passed}/{folds}",
                "gated": is_gated, "test_correct": bool(correct)}) + "\n")
            fout.flush()
            if (n + 1) % 25 == 0:
                prec = gated_correct / gated if gated else float("nan")
                print(f"[{n+1}/{len(tids)}] gated={gated} "
                      f"gated_prec={prec:.2f} "
                      f"ungated_correct={ungated_correct}", flush=True)

    print("\n=== NEURAL-LOO GATE REPORT ===", flush=True)
    print(f"tasks evaluated: {total} (skipped {skipped})")
    print(f"gated (all folds pass): {gated}")
    if gated:
        print(f"gated precision: {gated_correct}/{gated} "
              f"= {gated_correct/gated:.3f}")
    print(f"correct but ungated: {ungated_correct}")
    print(f"overall exact: {gated_correct + ungated_correct}/{total}")


if __name__ == "__main__":
    main()
