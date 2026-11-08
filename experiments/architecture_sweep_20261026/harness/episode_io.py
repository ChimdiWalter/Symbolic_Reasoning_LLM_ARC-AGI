"""Loading stored episodes (observations and, for training/evaluation on source splits, outcomes) and labels.

    S = load_stage(EP + "/S_train_syn", "S_train_syn")       # [{"meta","tokens","rel","glob","actions","oc"}]
    half(meta)                                             # "A" (selection/calibration) or "B" (unselected report)
    labels = action_labels(state, mode="revise")           # per action: y2, y1, harm1, harm2, n_exec

S_select is split ONCE into halves by family (synthetic) or linked cluster (real): A selects checkpoints and fits
calibration; B is the unselected source-development cohort that is only reported.
"""
import glob
import json
import os
import zlib

import numpy as np

from harness import core as C
from harness import data as D

_LAB = {}


def load_stage(stage_dir, name, outcomes=True):
    out = []
    for npz in sorted(glob.glob(os.path.join(stage_dir, name + ".*.npz"))):
        k = npz[:-4]
        z = np.load(npz)
        metas = [json.loads(x) for x in open(k + ".jsonl")]
        ocs = [json.loads(x) for x in open(k + ".outcomes.jsonl")] if outcomes else [None] * len(metas)
        n = z["n_hyp"]
        to = np.concatenate([[0], np.cumsum(n)])
        ro = np.concatenate([[0], np.cumsum(n * n)])
        for j, (m, oc) in enumerate(zip(metas, ocs)):
            out.append({"meta": m, "tokens": z["tokens"][to[j]:to[j + 1]],
                        "rel": z["rel"][ro[j]:ro[j + 1]].reshape(int(n[j]), int(n[j]), 2), "glob": z["glob"][j],
                        "actions": [tuple(a) for a in m["actions"]], "oc": oc})
    return out


def half(meta):
    if meta["split"].endswith("_syn"):
        key = meta["family"]
    else:
        key = D.manifest()["cluster_of"].get(meta["task_id"], meta["task_id"])
    return "A" if zlib.crc32(("half:" + key).encode()) % 2 == 0 else "B"


def truths_of(meta):
    if meta["split"].endswith("_syn"):
        fam, seed = meta["task_id"][4:].split("#")
        return D.synthetic_task(fam, int(seed))[1]
    if meta["split"] not in _LAB:
        _LAB[meta["split"]] = D.source_labels(meta["split"])
    return _LAB[meta["split"]][meta["task_id"]]


def action_labels(st, mode="revise"):
    """Arrays over the state's actions: y2, y1, harm1, harm2, gain2, n_exec (labels from withheld source truths).
    mode "preserve": a new behaviour replaces attempt 2 only (derived from the same stored execution)."""
    oc = st["oc"]
    rows = oc["rows"]
    if mode == "revise":
        y2 = np.array([r["y2"] for r in rows], float)
        y1 = np.array([r["y1"] for r in rows], float)
    else:
        tr = truths_of(st["meta"])
        base = oc["base_att"]
        y2, y1 = [], []
        for r in rows:
            att = r["att"]
            if r["new_beh"] and base and att and att[0] != base[0]:
                att = [base[0], att[0]]
            s = C.score([oc["beh"][h] for h in att], tr)
            y2.append(s["all2"]), y1.append(s["all1"])
        y2, y1 = np.array(y2, float), np.array(y1, float)
    b2, b1 = float(oc["base"]["all2"]), float(oc["base"]["all1"])
    return {"y2": y2, "y1": y1, "harm2": (b2 > 0) & (y2 < 1), "harm1": (b1 > 0) & (y1 < 1), "gain2": y2 - b2,
            "n_exec": np.array([r["n_exec"] for r in rows], float), "base2": b2, "base1": b1}


def value(lab, lam=0.02):
    """Training value of each action: exact withheld success (pass@2) + 0.5 pass@1 - a small execution cost."""
    return lab["y2"] + 0.5 * lab["y1"] - lam * lab["n_exec"] / 6.0
