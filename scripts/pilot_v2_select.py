"""Real ARC growth-repair pilot v2: draw the pilot sample from the frozen
pilot v1 selection and write its bundle (protocol section 4).

  python scripts/pilot_v2_select.py N   -> records/pilot_v2/pilot_bundle.json
                                           records/pilot_v2_evaluator/pilot_keymap.json

N must be the value the protocol's section 12 rule gives (recorded in the
protocol before this runs). Reads the training CHALLENGES file only
(sha256-pinned) and the frozen selection; recomputes the selection and
refuses on any difference; no solutions file is opened, nothing is run on
any task; the pool is the v1 pilot candidates, untouched since 4d3c29b.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_pilot import bundle as B                                  # noqa: E402

SELECTION = os.path.join(HERE, "records", "pilot_v1", "selection.json")
REC = os.path.join(HERE, "records", "pilot_v2")
EVAL = os.path.join(HERE, "records", "pilot_v2_evaluator")
BUNDLE = os.path.join(REC, "pilot_bundle.json")
KEYMAP = os.path.join(EVAL, "pilot_keymap.json")


def main(argv) -> None:
    if len(argv) != 1 or not argv[0].isdigit():
        raise SystemExit(__doc__)
    n = int(argv[0])
    if n not in B.ALLOWED_N:
        raise SystemExit(f"N must be one of {B.ALLOWED_N}")
    if os.path.exists(BUNDLE) or os.path.exists(KEYMAP):
        raise SystemExit("the pilot v2 sample exists: it is frozen")
    ch = B.load_challenges()
    sel = B.selection(ch)
    with open(SELECTION) as handle:
        frozen = json.load(handle)
    for key in ("order", "dev", "pilot_candidates"):
        if frozen[key] != sel[key]:
            raise SystemExit(f"recomputed {key} differs from the frozen selection")
    ids = B.pilot_ids(frozen, n)
    if set(ids) & set(frozen["dev"]):
        raise SystemExit("a development task entered the pilot")
    os.makedirs(REC, exist_ok=True)
    os.makedirs(EVAL, exist_ok=True)
    bundle, keymap = B.make_bundle(ch, ids)
    keymap.update(role="growth-repair pilot v2 (evaluator only)", n=n,
                  selection_sha256=B.sha256_file(SELECTION))
    b_sha = B.write_json(BUNDLE, bundle)
    B.write_json(KEYMAP, keymap)
    print(json.dumps({"n": len(ids), "bundle_sha256": b_sha,
                      "ids_sha256": hashlib.sha256(",".join(ids).encode()).hexdigest(),
                      "strata": {s: sum(1 for t in ids if B.stratum(ch[t]) == s) for s in B.STRATA}}))


if __name__ == "__main__":
    main(sys.argv[1:])
