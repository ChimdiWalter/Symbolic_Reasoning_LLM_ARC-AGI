"""Failure-typed controller v0, phase 1: static feasibility audit (observation
only; no induction, no repair installed, no score run).

  python scripts/ctl0_audit.py   -> outputs/ctl0/audit.json

1. kf892487f1049 fold f1 (demonstration 1 removed): do the two generated
   candidates, window_fill(k=2) and bbox_fill, disagree on the fold's
   permitted unlabelled inputs (demonstration 1's INPUT, which the fold's
   reasoner receives as its test input, and the task's test input)? Each
   relation is applied directly (cora_reach.relations.apply) to every S6
   object of the input grid, the view both proposals were built in. Their
   agreement with the fold's own training outputs is also checked. The
   removed OUTPUT is never read.
2. Unsupported confidence on the P3 preflight rows: for every accepted program
   (BASE and P3 arms) whose view V is recorded, the composition of each
   V-object (how many 4-connected same-colour components it contains, how many
   colours it has) on the training inputs against the held-out INPUTS. A
   program is flagged OUT_OF_SUPPORT if some held-out V-object has a
   composition never seen in its training inputs. The held-out truth
   (CORRECT or FALSE_ACCEPT) is reported beside the flag and never used to
   compute it.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
BUNDLE = os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")


def kf89_f1():
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import SegmentationVariant as SV
    from cora_reach import relations as REL
    from cora_reach import measure as M
    task = json.load(open(BUNDLE))["tasks"]["kf892487f1049"]
    train, tests = M.arrays(task)
    cands = [("window_fill", {"k": 2}), ("bbox_fill", {})]

    def predict(fam, params, grid):
        from geocat_arc.object_reasoning.types import to_grid_pairs
        g = to_grid_pairs([(np.asarray(grid), np.asarray(grid))])[0][0]
        bg = S.background_for(g, SV.S6_COLOR_LAYERS)
        out = np.asarray(grid).copy()
        for o in S.segment(g, SV.S6_COLOR_LAYERS, bg):
            added = REL.apply(fam, params, set(o.cells), np.asarray(grid))
            for (r, c) in (added or ()):
                if 0 <= r < out.shape[0] and 0 <= c < out.shape[1]:
                    out[r, c] = o.color
        return out
    rest = [0, 2, 3]
    fit = {fam: [bool((predict(fam, p, train[i][0]) == train[i][1]).all()) for i in rest] for fam, p in cands}
    unl = {"demo1_input": train[1][0], **{f"test{j}_input": t for j, t in enumerate(tests)}}
    disagree = {}
    for name, grid in unl.items():
        a, b = (predict(f, p, grid) for f, p in cands)
        disagree[name] = {"cells_differ": int((a != b).sum()), "disagree": bool((a != b).any())}
    return {"fold": 1, "removed_demonstration": 1, "fold_training_demonstrations": rest,
            "fit_fold_training_outputs": fit, "unlabelled_inputs": disagree}


def composition(grid, v):
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import SegmentationVariant as SV, cell_colors_of
    from geocat_arc.object_reasoning.types import to_grid_pairs
    g = to_grid_pairs([(np.asarray(grid), np.asarray(grid))])[0][0]
    V = next(x for x in SV if x.value == v)
    bg = S.background_for(g, V)
    fine = S.segment(g, SV.S1_SAME_COLOR_4, S.background_for(g, SV.S1_SAME_COLOR_4))
    sigs = set()
    for o in S.segment(g, V, bg):
        n = sum(1 for f in fine if f.cells & o.cells)
        sigs.add((n, len(set(cell_colors_of(o).values()))))
    return sigs


def unsupported_confidence():
    import p3_preflight as PF
    tasks = {t["id"]: t for t in PF.tasks()}
    rows = [json.loads(x) for x in open(os.path.join(HERE, "outputs", "p3", "preflight_rows.jsonl")) if x.strip()]
    out = []
    for r in rows:
        if r["arm"] not in ("BASE", "P3") or not r["accepted"] or not r["program_variant"]:
            continue
        t = tasks[r["task"]]
        seen = set().union(*(composition(a, r["program_variant"]) for a, _b in t["train"]))
        new = [sorted(composition(a, r["program_variant"]) - seen) for a, _b in t["heldout"]]
        out.append({"task": r["task"], "arm": r["arm"], "view": r["program_variant"],
                    "out_of_support": any(new), "unseen_compositions": new, "truth": r["outcome"]})
    tab = {}
    for x in out:
        k = (x["truth"], x["out_of_support"])
        tab[f"{k[0]}|flagged={k[1]}"] = tab.get(f"{k[0]}|flagged={k[1]}", 0) + 1
    return {"programs": out, "table": tab}


def main():
    from cora_pilot import isolation as ISO
    ISO.install(BUNDLE)
    sys.path.insert(0, os.path.join(HERE, "src"))
    res = {"kf89_f1": kf89_f1(), "unsupported_confidence": unsupported_confidence()}
    os.makedirs(os.path.join(HERE, "outputs", "ctl0"), exist_ok=True)
    with open(os.path.join(HERE, "outputs", "ctl0", "audit.json"), "w") as handle:
        json.dump(res, handle, indent=1, sort_keys=True, default=str)
    print(json.dumps({"kf89_f1": res["kf89_f1"], "table": res["unsupported_confidence"]["table"],
                      "flagged": [(x["task"], x["arm"], x["view"], x["truth"]) for x in res["unsupported_confidence"]["programs"]
                                  if x["out_of_support"]]}, indent=1, default=str))


if __name__ == "__main__":
    main()
