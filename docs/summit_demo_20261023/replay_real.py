#!/usr/bin/env python3
"""CORA-FHR REAL-task witness: offline replay of ka95aa62f67d9 (an ARC-AGI-2 training task; numpy only).

  python3 replay_real.py

The task, recorded run, folds and controls come from ./data/, hash-checked against MANIFEST.json. The
guarded operator is re-executed here (guard_standalone.py) on the test input's recorded objects.
- It is not a live engine run.
- It is not part of the CORA_FHR_V1 Kaggle entry; the guard was developed afterwards.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
GLYPH = ".123456789"


def show(grid, title):
    print(f"   {title}")
    for row in grid:
        print("    " + " ".join(GLYPH[v] for v in row))


def main():
    man = json.load(open(os.path.join(HERE, "MANIFEST.json")))
    for f, digest in man["files"].items():
        got = hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest()
        if got != digest:
            sys.exit(f"{f}: sha256 mismatch ({got[:12]} != {digest[:12]}); not replaying an unrecorded file")
    import guard_standalone as GU
    t = json.load(open(os.path.join(HERE, "data", "real_task.json")))
    w = json.load(open(os.path.join(HERE, "data", "real_witness.json")))
    print(f"CORA-FHR REAL-task witness | {t['key']} | {t['tier']} | recorded run, rows {w['sources']['rows_dev60_guard.jsonl'][:10]}")
    print("\n1. THE TASK (training pairs; the solver sees these and the test input only)")
    for i, (a, b) in enumerate(t["train"]):
        show(a, f"demo {i} input"); show(b, f"demo {i} output")
    print("\n2. FROZEN CORA FAILS (recorded)")
    print(f"   frozen native certified: {w['controls']['A_frozen_native_certified']} | "
          f"matched extra search certified: {w['controls']['B_matched_search_certified']}")
    print("\n3. THE CONSTRUCTED RULE, with a typed applicability guard (where it applies, and what it does)")
    print(f"   {w['rule']}   [{w['name']}, {w['novelty']}]")
    print(f"   evidence: the solver's memorized-growth records, views {w['evidence_views']}")
    print("\n4. VERIFIED IN THE UNCHANGED ENGINE (recorded)")
    print(f"   accepted {w['top']['accepted']} | operator used {w['top']['uses']} | engine restored {w['top']['restored']} | "
          f"{w['tie_alternatives_checked']} equally simple alternatives checked, no disagreement")
    for i, f in enumerate(w["folds"]):
        print(f"   fold {i}: {f['class']}, held-out example exact {f['heldout_exact']}, rule rebuilt: {f['rule'] == w['rule']}")
    print("\n5. RE-EXECUTED HERE on the test input's objects (guard_standalone)")
    G = t["test_input"]
    added = set()
    for cells in w["test_objects"]:
        O = {(r, c): v for (r, c), v in cells}
        added |= GU.evaluate(w["expr"], O, G)
    changed = {(r, c) for r in range(len(G)) for c in range(len(G[0])) if w["committed"][r][c] != G[r][c]}
    show(G, "test input"); show(w["committed"], "CORA's committed answer")
    print(f"   the rule's added cells equal every cell the committed answer changes: {added == changed}")
    print("\n6. INDEPENDENT EVALUATOR (training solution)")
    print(f"   correct = {w['committed'] == t['evaluator_answer']}")
    print("\n7. HONEST LIMITS")
    for c in w["caveats"]:
        print(f"   - {c}")
    print(f"   failure-blind constructor: {w['controls']['C2G_failure_blind_outcome']}, same rule "
          f"{w['controls']['C2G_same_rule']}, same evidence {w['controls']['same_evidence_as_failure_blind']}")


if __name__ == "__main__":
    main()
