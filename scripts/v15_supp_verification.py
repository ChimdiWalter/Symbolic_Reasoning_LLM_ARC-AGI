"""Item-2 v1.5 delivery addendum (c): three-valued verification diagnostic.

Supplementary; never changes the frozen procedure or the official result.
The frozen generator records `other_candidate_fits` as a boolean and maps any
exception from the fitter to False, so False mixes "the other candidate does
not fit" with "the check failed". The occurrence-scoped fitter has no
deadline and no randomness, so its outcome can be recomputed exactly from
each stored episode's demonstrations and the re-derived other candidate.

For every admitted test episode this returns FIT, NO_FIT (with the fitter's
failure code) or ERROR (with the exception type), and compares it with the
recorded boolean. Verification-based conclusions are marked LIMITED if any
ERROR occurs or any recomputation disagrees with the record. It reads no
selection score.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "outputs", "tti", "v15_supp_verification.json")


def _evaluator():
    spec = importlib.util.spec_from_file_location(
        "ev15_supp_ver", os.path.join(HERE, "scripts", "evaluate_v15_selection.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def three_valued(SF, other, pairs):
    try:
        fitted, evidence = SF.fit_induced_occurrences(other, pairs)
    except Exception as exc:                                   # noqa: BLE001
        return "ERROR", type(exc).__name__
    if fitted is not None:
        return "FIT", None
    return "NO_FIT", evidence.get("failure")


def expected_boolean(status):
    return status == "FIT"


def main():
    import numpy as np
    from cora_tti import scoped_slot_fitting as SF
    EV = _evaluator()
    S = EV.S
    records = EV.load(EV.TEST_DIR)
    counts, codes, mismatches = Counter(), Counter(), []
    for r in records:
        if not r.get("admitted"):
            continue
        g, slot = r["group"], r["slot"]
        fam = S.FAMILIES[slot % len(S.FAMILIES)]
        attempt = (g["pair_seed"] - S.TEST_BASE - slot * S.SLOT_STRIDE) // S.ATTEMPT_STRIDE
        anchor = S.CD.sample_target(g["pair_seed"], S.G.parse_family(fam))
        contrast = S.G.contrast_target(anchor, "FEATURE", rotation=attempt)
        for e in g["episodes"]:
            other = contrast if e["target_index"] == 0 else anchor
            pairs = [(np.asarray(d["input"]), np.asarray(d["output"]))
                     for d in e["demonstrations"]]
            status, detail = three_valued(SF, other, pairs)
            counts[status] += 1
            if detail:
                codes[f"{status}:{detail}"] += 1
            if expected_boolean(status) != e.get("other_candidate_fits"):
                mismatches.append([slot, e["target_index"], e["replicate_index"],
                                   status, e.get("other_candidate_fits")])
    limited = bool(counts.get("ERROR") or mismatches)
    report = {"supplementary": True, "episodes": sum(counts.values()),
              "status_counts": dict(sorted(counts.items())),
              "detail_counts": dict(sorted(codes.items())),
              "mismatches_with_record": mismatches[:50],
              "mismatch_count": len(mismatches),
              "verification_conclusions": "LIMITED" if limited else "UNQUALIFIED"}
    with open(sys.argv[1] if len(sys.argv) > 1 else OUT, "w") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("episodes", "status_counts", "mismatch_count",
                                              "verification_conclusions")}))


if __name__ == "__main__":
    main()
