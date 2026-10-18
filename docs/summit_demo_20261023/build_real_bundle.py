"""Build the REAL-task witness bundle (ka95aa62f67d9) for the offline demo. Run from the repository.

  python docs/summit_demo_20261023/build_real_bundle.py

It writes data/real_task.json and data/real_witness.json, then adds them (with replay_real.py and
guard_standalone.py) to MANIFEST.json. The existing entries are unchanged.

**Sources:**
- the recorded guard-probe row (`outputs/cora_fhr/rows_dev60_guard.jsonl`, arm EG);
- the dev60 task;
- the evaluator's answer (ARC-AGI-2 training solutions), shown in the evaluator step only.

The guarded rule was developed on 2026-10-18, after CORA_FHR_V1 was submitted to Kaggle. It is not part of
that entry.
"""
import hashlib
import json
import os
import sys

DEMO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(DEMO))
sys.path.insert(0, ROOT)
KEY = "ka95aa62f67d9"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    from cora_funnel import run as FR                                 # sealed flags
    import numpy as np
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import SegmentationVariant, cell_colors_of
    from geocat_arc.perception.grid import Grid
    from cora_fhr.evaluate import answers
    rows_p = os.path.join(ROOT, "outputs", "cora_fhr", "rows_dev60_guard.jsonl")
    row = next(json.loads(l) for l in open(rows_p) if json.loads(l)["key"] == KEY)
    task = dict(FR.load("dev60"))[KEY]
    E, C, A, B = (row["arms"][k] for k in ("EG", "C2G", "A", "B"))
    sel = E["selected"]
    prop = next(p for p in E["proposals"] if p["name"] == sel["name"])
    g = Grid(np.asarray(task["test"][0]["input"]))
    view = SegmentationVariant(sel["view"])
    objs = [sorted([[list(c), int(v)] for c, v in cell_colors_of(o).items()]) for o in S.segment(g, view, S.background_for(g, view))]
    truth = answers("dev60")[KEY][0]
    os.makedirs(os.path.join(DEMO, "data"), exist_ok=True)
    json.dump({"key": KEY, "tier": "REAL ARC-AGI-2 TRAINING task (exposed; selected by the development autopsy)",
               "train": [[p["input"], p["output"]] for p in task["train"]], "test_input": task["test"][0]["input"],
               "evaluator_answer": truth[0]}, open(os.path.join(DEMO, "data", "real_task.json"), "w"))
    json.dump({"key": KEY, "rule": sel["pretty"], "expr": prop["expr"], "name": sel["name"], "view": sel["view"],
               "novelty": (sel.get("novelty") or {}).get("class"), "evidence_views": E["evidence"]["views"],
               "top": {k: E["top"].get(k) for k in ("accepted", "uses", "restored")},
               "folds": [{"class": f["class"], "heldout_exact": f.get("heldout_exact"),
                          "rule": (f.get("selected") or {}).get("pretty")} for f in E["folds"]],
               "tie_alternatives_checked": sel.get("same_class_fitting"), "committed": E["committed"][0],
               "test_objects": objs,
               "controls": {"A_frozen_native_certified": A["certified"], "B_matched_search_certified": B["certified"],
                            "C2G_failure_blind_outcome": C.get("outcome"), "C2G_same_rule": C["selected"]["pretty"] == sel["pretty"],
                            "same_evidence_as_failure_blind": C["evidence"]["views"] == E["evidence"]["views"]},
               "caveats": ["selected by the development autopsy (in-sample)", "ARC-AGI-2 training task (exposed)",
                           "the failure-blind constructor found the same rule from the same evidence",
                           "developed after CORA_FHR_V1 was submitted; not part of that Kaggle entry"],
               "sources": {"rows_dev60_guard.jsonl": sha(rows_p)}},
              open(os.path.join(DEMO, "data", "real_witness.json"), "w"), indent=1)
    man_p = os.path.join(DEMO, "MANIFEST.json")
    man = json.load(open(man_p))
    for f in ("data/real_task.json", "data/real_witness.json", "replay_real.py", "guard_standalone.py"):
        man["files"][f] = sha(os.path.join(DEMO, f))
    man["sources"]["rows_dev60_guard.jsonl"] = sha(rows_p)
    json.dump(man, open(man_p, "w"), indent=1)
    print("real bundle written:", {f: man["files"][f][:12] for f in man["files"] if "real" in f or "guard" in f})


if __name__ == "__main__":
    main()
