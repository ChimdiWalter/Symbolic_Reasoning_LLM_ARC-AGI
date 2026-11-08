"""U5 calibration-only packet for the independent team's neural proposer (INTERFACE.md; PROTOCOL.md section 15).
    packet.py export DS [DS ...]     write packet_v1/ (calibration parents only) and PACKET_MANIFEST.json
    packet.py freeze                 hash the packet manifest and INTERFACE.md -> PACKET_FREEZE.json (experiment folder)
<python environment>, python -I."""
import hashlib
import json
import os
import shutil
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import u5core as C      # noqa: E402
import u5run as RN      # noqa: E402

DATA = "/path/to/bio_data"
PK = os.path.join(DATA, "packet_v1")
E = "/path/to/repository/experiments/universality_bio_grammar_20261103"
SOURCES = {"add_lowthresh": "hysteresis detection (Canny 1986); StarDist and Cellpose probability thresholds",
           "fill_holes": "Soille 2003; CellProfiler fill holes; Cellpose fill_holes_and_remove_small_masks",
           "split_dt": "Beucher and Lantuejoul 1979; Vincent and Soille 1991; Malpica et al. 1997",
           "split_int": "Wahlby et al. 2004; CellProfiler declump by intensity",
           "merge_pairs": "Wahlby et al. 2004; Lin et al. 2005",
           "close": "Serra 1982; Soille 2003", "open": "Serra 1982; Soille 2003",
           "dilate": "CellProfiler ExpandOrShrinkObjects; skimage expand_labels",
           "erode": "CellProfiler ExpandOrShrinkObjects",
           "delete": "CellProfiler size and FilterObjects filters; ImageJ Analyze Particles; remove_small_objects",
           "clear_border": "CellProfiler discard border objects; skimage clear_border"}
SCHEMA = {"type": "object", "required": ["dataset", "programs"],
          "properties": {"dataset": {"type": "string"}, "proposer": {"type": "string"},
                         "programs": {"type": "array", "items": {
                             "type": "object", "required": ["operator", "theta_index", "guard"],
                             "properties": {"id": {"type": "string"},
                                            "operator": {"enum": list(C.OPS)},
                                            "theta_index": {"type": "integer", "minimum": 0},
                                            "guard": {"type": "array", "maxItems": 2, "items": {
                                                "type": "array", "minItems": 3, "maxItems": 3}}}}}}}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def card():
    return {"version": "v1", "types": {"Img": "intensity image in [0, 1]", "Lab": "instance label image",
                                       "Unit": "object, mutual-best touching pair, or candidate new object",
                                       "Guard": "true, one predicate, or two predicates on different features"},
            "operators": [{"name": op, "effect_class": C.CLASS[op], "theta_grid": list(C.THETA[op]),
                           "features": list(C.FEATS[op]), "source": SOURCES[op]} for op in C.OPS],
            "canonical_order": list(C.OPS),
            "predicate_rule": "f < q or f > q; U5's own enumeration uses q at the deciles of the demonstration units",
            "rule": "PROTOCOL.md section 10 (FIT: no demonstration parent harmed, pooled gain > 0, >= 0.9 of best; "
                    "leave-one-parent-out top program harms no held-out parent; agreement of all fitting programs and "
                    "fold tops; reversed-order restart)"}


def export(dss):
    os.makedirs(PK, exist_ok=True)
    json.dump(card(), open(os.path.join(PK, "grammar_card.json"), "w"), indent=1)
    json.dump(SCHEMA, open(os.path.join(PK, "proposal_schema.json"), "w"), indent=1)
    shutil.copy(os.path.join(HERE, "u5policy.py"), os.path.join(PK, "policy.py"))
    shutil.copy(os.path.join(HERE, "verifier_calibration.py"), os.path.join(PK, "verifier_calibration.py"))
    shutil.copy(os.path.join(E, "INTERFACE.md"), os.path.join(PK, "INTERFACE.md"))
    for ds in dss:
        d = os.path.join(PK, ds)
        os.makedirs(os.path.join(d, "calibration_images"), exist_ok=True)
        cal = sorted(u for u, v in RN.man(ds)["images"].items() if v["side"] == "calibration")
        S = RN.ImgSet(ds, cal, "S", True)
        json.dump({"parents": S.parents, "base_n_ref_n_pred_tp": S.base().tolist(),
                   "images": {u: S.parent[u] for u in cal}}, open(os.path.join(d, "base.json"), "w"), indent=1)
        for op in C.OPS:
            x = RN.set_units(S, op)
            arr = {"parent": x["parent"], "image": np.array([cal.index(u) for u, _ in x["keys"]], int)}
            for t in x["feats"]:
                arr[f"feats_t{t}"] = x["feats"][t]
                arr[f"valid_t{t}"] = x["valid"][t]
                arr[f"cls_t{t}"] = x["cls"][t]
                arr[f"dTP_t{t}"] = x["dTP"][t]
                arr[f"dN_t{t}"] = x["dN"][t]
                arr[f"conflicts_t{t}"] = x["conflicts"][t]
            np.savez_compressed(os.path.join(d, f"units_{op}.npz"), **arr)
        fr = os.path.join(RN.W, ds, "probes", "induction", "FAILURE_RECORDS.json")
        if os.path.exists(fr):
            shutil.copy(fr, os.path.join(d, "failure_records.json"))
        g = json.load(open(os.path.join(RN.W, ds, "GATE.json")))
        json.dump(g, open(os.path.join(d, "gate.json"), "w"), indent=1)
        for u in cal:
            ref, ign = RN.refign(ds, u)
            np.savez_compressed(os.path.join(d, "calibration_images", f"{u}.npz"), S=RN.lab(ds, "S", u),
                                intensity=RN.inten(ds, u).astype(np.float16), reference=ref, ignore=ign)
        assert all(RN.man(ds)["images"][u]["side"] == "calibration" for u in cal)
    files = sorted(os.path.relpath(os.path.join(r, f), PK) for r, _, fs in os.walk(PK) for f in fs
                   if f != "PACKET_MANIFEST.json")
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "datasets": dss,
           "contains_evaluation_data": False, "files": {f: sha(os.path.join(PK, f)) for f in files}}
    json.dump(man, open(os.path.join(PK, "PACKET_MANIFEST.json"), "w"), indent=1)
    print(len(files), "files")


def freeze():
    m = os.path.join(PK, "PACKET_MANIFEST.json")
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "packet_folder": PK,
           "packet_manifest_sha256": sha(m), "interface_sha256": sha(os.path.join(E, "INTERFACE.md")),
           "n_files": len(json.load(open(m))["files"])}
    json.dump(out, open(os.path.join(E, "PACKET_FREEZE.json"), "w"), indent=1)
    print(json.dumps(out))


if __name__ == "__main__":
    if sys.argv[1] == "export":
        export(sys.argv[2:])
    else:
        freeze()
