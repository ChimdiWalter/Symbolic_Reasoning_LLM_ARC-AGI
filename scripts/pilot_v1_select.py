"""Real ARC pilot v1: fix the selection order, the development set and the
pilot candidates, and write the development bundle (protocol section 4).

  python scripts/pilot_v1_select.py selection   -> records/pilot_v1/selection.json
                                                   records/pilot_v1/dev_bundle.json
                                                   records/pilot_v1_evaluator/dev_keymap.json
  python scripts/pilot_v1_select.py pilot N     -> records/pilot_v1/pilot_bundle.json
                                                   records/pilot_v1_evaluator/pilot_keymap.json

Reads the training CHALLENGES file only (sha256-pinned). No solutions file is
opened, nothing is run on any task, and the order is a hash of the task
identifier, so no outcome can influence which task lands where.
"""
from __future__ import annotations

import hashlib
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_pilot import bundle as B                                  # noqa: E402

REC = os.path.join(HERE, "records", "pilot_v1")
EVAL = os.path.join(HERE, "records", "pilot_v1_evaluator")
SELECTION = os.path.join(REC, "selection.json")


def main(argv) -> None:
    os.makedirs(REC, exist_ok=True)
    os.makedirs(EVAL, exist_ok=True)
    ch = B.load_challenges()
    sel = B.selection(ch)
    if argv[:1] == ["selection"]:
        if os.path.exists(SELECTION):
            raise SystemExit("selection.json exists; the order is frozen")
        sel["challenges_sha256"] = B.CHALLENGES_SHA256
        s_sha = B.write_json(SELECTION, sel)
        bundle, keymap = B.make_bundle(ch, sel["dev"])
        b_sha = B.write_json(os.path.join(REC, "dev_bundle.json"), bundle)
        keymap["role"] = "development (reasoner-only dry run; never scored)"
        B.write_json(os.path.join(EVAL, "dev_keymap.json"), keymap)
        print(f"in scope {sel['in_scope']} of {sel['tasks_total']}; strata {sel['strata_counts']}; "
              f"dev {len(sel['dev'])}; candidates "
              f"{ {s: len(v) for s, v in sel['pilot_candidates'].items()} }")
        print(f"selection sha256 {s_sha}\ndev bundle sha256 {b_sha}")
    elif argv[:1] == ["pilot"] and len(argv) == 2:
        import json
        with open(SELECTION) as handle:
            frozen = json.load(handle)
        for key in ("order", "dev", "pilot_candidates"):
            if frozen[key] != sel[key]:
                raise SystemExit(f"recomputed {key} differs from the frozen selection")
        ids = B.pilot_ids(frozen, int(argv[1]))
        path = os.path.join(REC, "pilot_bundle.json")
        if os.path.exists(path):
            raise SystemExit("pilot_bundle.json exists; the pilot sample is frozen")
        bundle, keymap = B.make_bundle(ch, ids)
        keymap["role"] = "pilot (evaluator only)"
        keymap["n"] = int(argv[1])
        b_sha = B.write_json(path, bundle)
        B.write_json(os.path.join(EVAL, "pilot_keymap.json"), keymap)
        print(f"pilot N {len(ids)}; bundle sha256 {b_sha}; "
              f"ids sha256 {hashlib.sha256(','.join(ids).encode()).hexdigest()}")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
