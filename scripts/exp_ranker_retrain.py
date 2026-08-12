#!/usr/bin/env python3
"""Falsifiable ranker experiment (queued after v6).

Question: with today's corpus (all accepted programs + LOO-rejected
train-perfect partials), does a learned ranker separate LOO-pass from
LOO-fail programs better than the Bayesian linear ranker — i.e. is it worth
wiring the neural ranker into search order when search becomes order-bound?

Dataset (built from harness artifacts, no task-ID features):
  positives = accepted programs (LOO-passed) from the given run dirs
  negatives = near-solve partials with failure_stage == 'loo'
              (train-perfect programs the gate rejected)
Features: geocat_arc.bayesian_program_search.program_features.extract_features
          (the SAME featurization the Bayesian ranker sees — apples to apples).
Models:   (a) Bayesian linear ranker (bayes_ranker.py posterior mean)
          (b) small MLP (torch), 2 hidden layers
Protocol: 5-fold cross-validation over tasks (grouped by task id so a task's
          positive and negative rows never straddle a split); metric = AUC.
Output:   outputs/exp_ranker_retrain/report.json + stdout summary.
"""
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, ".")
from geocat_arc.object_reasoning.types import ObjectProgram  # noqa: E402
from geocat_arc.bayesian_program_search.program_features import (  # noqa: E402
    extract_features, object_feature_dim)

RUN_DIRS = [d for d in ("outputs/unified_harness_v6",
                        "outputs/unified_harness_v5") if os.path.isdir(d)]
OUT_DIR = "outputs/exp_ranker_retrain"


def collect():
    rows = []  # (task_id, features, label)
    seen_pos = set()
    for run in RUN_DIRS:
        for f in glob.glob(f"{run}/object/programs/*.json"):
            tid = os.path.basename(f)[:-5]
            if tid in seen_pos:
                continue
            try:
                prog = ObjectProgram.from_dict(json.load(open(f)))
                rows.append((tid, extract_features(prog), 1))
                seen_pos.add(tid)
            except Exception:
                pass
    seen_neg = set()
    for run in RUN_DIRS:
        for f in glob.glob(f"{run}/object/near_solve_parts/*.jsonl"):
            tid = os.path.basename(f)[:-6]
            if tid in seen_neg or tid in seen_pos:
                continue
            try:
                r = json.loads(open(f).readline())
                if r.get("failure_stage") != "loo":
                    continue
                pp = r.get("program_partial")
                if not (isinstance(pp, dict) and pp.get("rules")):
                    continue
                prog = ObjectProgram.from_dict(pp)
                rows.append((tid, extract_features(prog), 0))
                seen_neg.add(tid)
            except Exception:
                pass
    return rows


def auc(scores, labels):
    order = np.argsort(scores)
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    pos = labels == 1
    n_pos, n_neg = pos.sum(), (~pos).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2)
                 / (n_pos * n_neg))


def bayes_scores(Xtr, ytr, Xte, lam=1.0):
    d = Xtr.shape[1]
    A = Xtr.T @ Xtr + lam * np.eye(d)
    w = np.linalg.solve(A, Xtr.T @ ytr)
    return Xte @ w


def mlp_scores(Xtr, ytr, Xte, seed):
    import torch
    torch.manual_seed(seed)
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    Xtr_t = torch.tensor((Xtr - mu) / sd, dtype=torch.float32)
    Xte_t = torch.tensor((Xte - mu) / sd, dtype=torch.float32)
    ytr_t = torch.tensor(ytr, dtype=torch.float32)
    net = torch.nn.Sequential(
        torch.nn.Linear(Xtr.shape[1], 64), torch.nn.ReLU(),
        torch.nn.Linear(64, 32), torch.nn.ReLU(),
        torch.nn.Linear(32, 1))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = torch.nn.BCEWithLogitsLoss()
    for _ in range(400):
        opt.zero_grad()
        loss = loss_fn(net(Xtr_t).squeeze(-1), ytr_t)
        loss.backward()
        opt.step()
    with torch.no_grad():
        return net(Xte_t).squeeze(-1).numpy()


def main():
    rows = collect()
    tids = sorted({t for t, _, _ in rows})
    X = np.array([f for _, f, _ in rows], dtype=float)
    y = np.array([l for _, _, l in rows])
    tid_arr = np.array([t for t, _, _ in rows])
    print(f"dataset: {len(rows)} rows ({int(y.sum())} pos / "
          f"{int((1 - y).sum())} neg), {len(tids)} tasks, "
          f"dim={object_feature_dim()}")
    rng = np.random.RandomState(0)
    folds = np.array_split(rng.permutation(tids), 5)
    res = defaultdict(list)
    for k, hold in enumerate(folds):
        te = np.isin(tid_arr, hold)
        tr = ~te
        if y[te].min() == y[te].max():
            continue  # degenerate fold
        res["bayes"].append(auc(bayes_scores(X[tr], y[tr], X[te]), y[te]))
        res["mlp"].append(auc(mlp_scores(X[tr], y[tr], X[te], seed=k), y[te]))
    report = {
        "n_rows": len(rows), "n_pos": int(y.sum()),
        "n_neg": int((1 - y).sum()), "n_tasks": len(tids),
        "feature_dim": int(object_feature_dim()),
        "auc_bayes_linear": {"folds": res["bayes"],
                             "mean": float(np.nanmean(res["bayes"]))},
        "auc_mlp": {"folds": res["mlp"],
                    "mean": float(np.nanmean(res["mlp"]))},
        "runs_used": RUN_DIRS,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(report, open(f"{OUT_DIR}/report.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in report.items() if k.startswith("auc")},
                     indent=1))
    print(f"report -> {OUT_DIR}/report.json")


if __name__ == "__main__":
    main()
