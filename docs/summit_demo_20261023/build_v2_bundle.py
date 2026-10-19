"""Build the reasoning-v2 witness bundle (00dbd492) for the summit supplement figure. Run from the repository.

  python docs/summit_demo_20261023/build_v2_bundle.py   -> data/v2_witness_00dbd492.json

**Sources:**
- the recorded v2 engineering row (`outputs/cora_revision_v2/rows_standin58_eng.jsonl`);
- the frozen generalization-test rows for the native controls (`outputs/cora_fhr/rows_standin58_gen.jsonl`, arms A
  and B);
- the task (`outputs/cora_fhr/standin58.json`);
- the evaluator's answer, used only for the correct/incorrect label.

**Tier.** An exposed ARC-AGI-2 training task, examined during development. It is correct but UNCERTIFIED, and it is
not evidence of generalization.
"""
import hashlib
import json
import os
import sys

DEMO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(DEMO))
sys.path.insert(0, ROOT)
KEY = "00dbd492"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    rows_p = os.path.join(ROOT, "outputs", "cora_revision_v2", "rows_standin58_eng.jsonl")
    gen_p = os.path.join(ROOT, "outputs", "cora_fhr", "rows_standin58_gen.jsonl")
    task_p = os.path.join(ROOT, "outputs", "cora_fhr", "standin58.json")
    row = next(json.loads(l) for l in open(rows_p) if json.loads(l)["key"] == KEY)
    gen = next(json.loads(l) for l in open(gen_p) if json.loads(l)["key"] == KEY)
    task = json.load(open(task_p))["tasks"][KEY]
    truth = [b for _a, b in task["test"]]
    att = row["attempts"]
    correct = len(att) == len(truth) and all(any(x == o for x in a) for a, o in zip(att, truth))
    sys.path.insert(0, ROOT)
    from cora_funnel import run as FR                                  # noqa: F401  (sealed flags)
    from cora_fhr import ggrow as GG
    from cora_revision_v2 import scene_reasoner as SR
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    train = [(a, b) for a, b in task["train"]]
    expr = next(e for e in GG.expressions() if GG.pretty(e) == row["top"]["expr"])
    table = dict(SR.fit_policies(SR._scene(train, V(row["top"]["view"])), expr)[0][1])
    assert row["top"]["policy"] == "TABLE:size"
    out = {"key": KEY, "tier": "REAL ARC-AGI-2 TRAINING task (exposed; examined in development); CORRECT BUT UNCERTIFIED",
           "train": task["train"], "test_input": task["test"][0][0], "v2_prediction": att[0][0],
           "evaluator_correct": correct, "diagnosis": row["diagnosis"], "tier_v2": row["tier"], "top": row["top"],
           "size_to_colour": {str(k): v for k, v in sorted(table.items())},
           "test_table_support": row["test_table_support"], "folds": row["folds"], "fold_detail": row["fold_detail"],
           "n_hypotheses": row["n_hypotheses"], "n_distinct_predictions": len(row["distinct"][0]),
           "controls": {"A_frozen_native_certified": gen["arms"]["A"]["certified"],
                        "B_matched_search_certified": gen["arms"]["B"]["certified"]},
           "sources": {"rows_standin58_eng_row_sha256": hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest(),
                       "rows_standin58_gen_sha256": sha(gen_p), "standin58_sha256": sha(task_p)}}
    assert correct and row["tier"] == "EXPLORATORY" and not row["certified"]
    os.makedirs(os.path.join(DEMO, "data"), exist_ok=True)
    p = os.path.join(DEMO, "data", "v2_witness_00dbd492.json")
    json.dump(out, open(p, "w"))
    print(p, sha(p)[:16])


if __name__ == "__main__":
    main()
