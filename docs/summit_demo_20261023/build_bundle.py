"""Build the offline demo bundle from RECORDED repository outputs (run on Athe, inside the repo).

  .venv_arc2026/bin/python docs/summit_demo_20261023/build_bundle.py [--key dev_D3_04]

It writes data/task.json, data/witness.json and MANIFEST.json (sha256 of every bundled file, plus the source
records' hashes). Nothing is re-run: the bundle is a copy of the logged experiment and its audit.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

DEMO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(DEMO))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "outputs", "cora_fhr")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    from cora_funnel import run as FR                                 # noqa: F401  (sealed flags)
    import numpy as np
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import SegmentationVariant, cell_colors_of
    from geocat_arc.perception.grid import Grid
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="dev_D3_04")
    ap.add_argument("--corpus", default="c4_dev_v2")
    a = ap.parse_args()
    corpus_p = os.path.join(OUT, f"{a.corpus}.json")
    rows_p = os.path.join(OUT, f"rows_{a.corpus}.jsonl")
    wit_p = os.path.join(OUT, f"witness_{a.key}.json")
    task = json.load(open(corpus_p))["tasks"][a.key]
    row = next(json.loads(l) for l in open(rows_p) if json.loads(l)["key"] == a.key)
    wit = json.load(open(wit_p))
    E = row["arms"]["E"]
    sel = E["proposals"][0]
    g = Grid(np.asarray(task["test"][0][0]))
    view = SegmentationVariant(sel["view"])
    test_objects = [sorted([[list(c), int(v)] for c, v in cell_colors_of(o).items()]) for o in S.segment(g, view, S.background_for(g, view))]
    os.makedirs(os.path.join(DEMO, "data"), exist_ok=True)
    json.dump({"key": a.key, "train": task["train"], "test": task["test"], "family": task["family"],
               "truth_pretty": task["truth_pretty"], "note": "SYNTHETIC development task; the test output is shown "
               "only at the evaluation step"}, open(os.path.join(DEMO, "data", "task.json"), "w"), indent=1)
    bundle = {"key": a.key, "tier": "DEVELOPMENT, SYNTHETIC (corpus C4 v2)", "provenance": wit["provenance"],
              "logged": {"A": {"certified": row["arms"]["A"]["certified"], "failure_stage": row["arms"]["A"]["run"].get("failure_stage")}},
              "failure_evidence": E["evidence"]["views"],
              "operator": {"pretty": sel["pretty"], "expr": sel["expr"], "name": sel["name"], "view": sel["view"],
                           "novelty": sel["novelty"]["class"]},
              "perturbation_novelty": wit["perturbation_novelty"], "test_objects": test_objects,
              "folds": [{k: f.get(k) for k in ("fold", "class", "same_as_full", "accepted", "uses", "heldout_exact")}
                        | {"selected": (f.get("selected") or {}).get("pretty")} for f in E["folds"]],
              "replay": {k: v for k, v in wit["replay"].items() if k != "program_json"},
              "committed": E["committed"], "evaluator": wit["evaluator"], "ablation": wit["ablation"],
              "controls": {"C": row["arms"]["C"].get("outcome"), "C2": (wit["fresh"].get("C2") or {}).get("outcome"),
                           "D": row["arms"]["D"].get("outcome")},
              "sources": {"corpus": [os.path.relpath(corpus_p, ROOT), sha(corpus_p)], "rows": [os.path.relpath(rows_p, ROOT), sha(rows_p)],
                          "witness": [os.path.relpath(wit_p, ROOT), sha(wit_p)]}}
    json.dump(bundle, open(os.path.join(DEMO, "data", "witness.json"), "w"), indent=1)
    shutil.copy(os.path.join(ROOT, "cora_fhr", "ggrow.py"), os.path.join(DEMO, "ggrow_standalone.py"))
    files = ["data/task.json", "data/witness.json", "ggrow_standalone.py", "replay.py"]
    json.dump({"files": {f: sha(os.path.join(DEMO, f)) for f in files}, "sources": bundle["sources"]},
              open(os.path.join(DEMO, "MANIFEST.json"), "w"), indent=1)
    print("bundle written:", files)


if __name__ == "__main__":
    main()
