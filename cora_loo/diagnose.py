"""The diagnosis units (docs/CORA_REAL_TASK_LOO_STABILITY_v1.md section 4).

A unit is one failure-conditioned task's full-data arms, or one outer fold
of it. The full-data extension e_full and the full-data instances are reach
v1's (rows 60ddd04, instances2). Arm C holds e_full fixed on the remaining
demonstrations: it is FORENSIC ONLY and never an adaptive leave-one-out
witness. Nothing here reads a target.
"""
from __future__ import annotations

import json
import os
import time

from cora_loo import instrument as IN
from cora_reach import bridge as BR
from cora_reach import construct as CN
from cora_reach import measure as M

VERSION = IN.VERSION
ARMS = ("a_e", "a_k", "b", "c", "d", "e", "extract")


def engine_dirs(root) -> dict:
    from cora_pilot import native as N
    return {arm: N.prepare_object_dir(os.path.join(root, arm)) for arm in ARMS}


def load_context(here) -> dict:
    """The failure-conditioned tasks of reach v1, with their full-data
    extension, full-data instances and extraction seconds."""
    out = os.path.join(here, "outputs", "reach_v1")
    rows = {}
    with open(os.path.join(out, "measure_rows.jsonl")) as handle:
        for line in handle:
            if line.strip():
                r = json.loads(line)
                rows[r["key"]] = r
    ctx = {}
    for k, r in sorted(rows.items()):
        if not (r.get("fc") or {}).get("proposals"):
            continue
        raw, digest = M.read_instances(os.path.join(out, "instances2"), k)
        ctx[k] = {"ext": r["extension"], "variant": r["fc"]["proposals"][0]["variant"], "raw": raw,
                  "instances_sha256": digest, "n_train": r["n_train"],
                  "reach_v1": {"path_class": r["path_class"], "gates": r["gates"],
                               "folds": [{x: f.get(x) for x in ("fold", "class", "selected", "same_as_full")}
                                         for f in r["loo"]["folds"]]}}
    return ctx


def units(ctx) -> list:
    """Every unit id, the accepted task's first."""
    order = sorted(ctx, key=lambda k: (ctx[k]["reach_v1"]["path_class"] != "LOO_FAILURE", k))
    out = []
    for k in order:
        out.append(f"{k}:full")
        out.extend(f"{k}:f{i}" for i in range(ctx[k]["n_train"]))
    return out


def _exact(run, target):
    return bool(run["accepted"] and run["predictions"] and run["predictions"][0] is not None
                and run["predictions"][0] == M._grid(target))


def full_unit(key, task, c, dirs) -> dict:
    train, _tests = M.arrays(task)
    row = {"unit": f"{key}:full", "key": key, "kind": "full", "version": VERSION, "n_train": len(train),
           "e_full": c["ext"]["name"], "load_start": IN._load()}
    for clock in IN.CLOCKS:
        row[f"A_E_{clock}"], _ = IN.engine_run(f"{key}_AE_{clock}", train, [], dirs["a_e"], ext=c["ext"],
                                               clock=clock)
        row[f"A_K_{clock}"], _ = IN.engine_run(f"{key}_AK_{clock}", train, [], dirs["a_k"], clock=clock)
    return row


def fold_unit(key, task, i, c, dirs) -> dict:
    train, _tests = M.arrays(task)
    rest = [p for j, p in enumerate(train) if j != i]
    held_in, held_out = train[i]
    e_full = c["ext"]
    row = {"unit": f"{key}:f{i}", "key": key, "kind": "fold", "fold": i, "version": VERSION,
           "n_train": len(train), "n_rest": len(rest), "e_full": e_full["name"], "load_start": IN._load(),
           "reach_v1_fold": next((f for f in c["reach_v1"]["folds"] if f["fold"] == i), None)}
    #  evidence analysis without the engine: reach v1's instances, restricted
    keep = set(range(len(train))) - {i}
    restricted = [x for x in c["raw"] if x.get("demo") in keep]
    rprop = CN.propose(restricted)
    row["restricted"] = {"proposals": [{"name": p["ext"]["name"], "family": p["ext"]["family"],
                                        "params": p["ext"]["params"], "variant": p["variant"],
                                        "demos": p["demos"]} for p in rprop["proposals"]],
                         "analysis": IN.variant_analysis(restricted, e_full)}
    for clock in IN.CLOCKS:
        b = {}
        inst, b["extract"] = IN.extract_run(rest, dirs["extract"], clock)
        t1 = time.time()
        prop = CN.propose(inst)
        b["construct_s"] = round(time.time() - t1, 3)
        b["proposals"] = [{"name": p["ext"]["name"], "family": p["ext"]["family"], "params": p["ext"]["params"],
                           "variant": p["variant"], "instances": p["instances"], "demos": p["demos"]}
                          for p in prop["proposals"]]
        b["analysis"] = IN.variant_analysis(inst, e_full)
        b["heldout_distinguish"] = IN.heldout_check(
            c["raw"], i, prop["proposals"] + [{"ext": e_full, "variant": c["variant"]}])
        b["selected"] = prop["proposals"][0]["ext"]["name"] if prop["proposals"] else None
        b["same_as_full"] = b["selected"] == e_full["name"]
        if prop["proposals"]:
            e_i = prop["proposals"][0]["ext"]
            run, _ = IN.engine_run(f"{key}_f{i}_B_{clock}", rest, [held_in], dirs["b"], ext=e_i, clock=clock)
            run["heldout_exact"] = _exact(run, held_out)
            b["engine"] = run
        row[f"B_{clock}"] = b
        if b["same_as_full"]:
            row[f"C_{clock}"] = {"same_as_B": True}
        else:
            run, _ = IN.engine_run(f"{key}_f{i}_C_{clock}", rest, [held_in], dirs["c"], ext=e_full, clock=clock)
            run["heldout_exact"] = _exact(run, held_out)
            row[f"C_{clock}"] = {"same_as_B": False, "forensic_only": True, "engine": run}
    row["D_WALL"], _ = IN.engine_run(f"{key}_f{i}_D", rest, [held_in], dirs["d"])
    row["D_WALL"]["heldout_exact"] = _exact(row["D_WALL"], held_out)
    bw = row["B_WALL"]
    spent = float(bw["extract"]["wall_s"]) + float(bw["construct_s"]) + float(
        (bw.get("engine") or {}).get("wall_s") or 0.0)
    mb = round(min(M.MATCHED_MAX_S, max(M.MATCHED_MIN_S, spent)), 2)
    row["E_WALL"], _ = IN.engine_run(f"{key}_f{i}_E", rest, [held_in], dirs["e"], budget_s=mb)
    row["E_WALL"]["heldout_exact"] = _exact(row["E_WALL"], held_out)
    row["E_WALL"]["spent_s"] = round(spent, 3)
    return row


def run_unit(unit, tasks, ctx, dirs) -> dict:
    key, part = unit.split(":")
    snap = BR.originals()
    t0 = time.time()
    if part == "full":
        row = full_unit(key, tasks[key], ctx[key], dirs)
    else:
        row = fold_unit(key, tasks[key], int(part[1:]), ctx[key], dirs)
    row["key"] = unit                          # the coordinator's row key is the unit id
    row["task"] = key
    row["restored"] = BR.restored(snap)
    row["seconds"] = round(time.time() - t0, 3)
    row["load_end"] = IN._load()
    return row
