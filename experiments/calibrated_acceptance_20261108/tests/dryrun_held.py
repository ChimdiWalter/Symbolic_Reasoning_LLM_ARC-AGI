"""Dry run of the held path on 4 NuInsSeg CALIBRATION images posing as held ROIs (no PUMA image is touched).
Everything is written under the folder given as argv[1] (use one under data/work/, which git ignores):
    python -I -B tests/dryrun_held.py data/work/dryrun/out"""
import json
import os
import shutil
import sys

import numpy as np

SCR = sys.argv[1]
ROOT = "/path/to/repository/experiments/calibrated_acceptance_20261108"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import cadata as CD       # noqa: E402
import caharness as H     # noqa: E402
import make_freeze as MF  # noqa: E402
import u5run as RN        # noqa: E402

U5W = "/path/to/bio_data/work/nuinsseg"
m = RN.man("nuinsseg")["images"]
cal = sorted(u for u, v in m.items() if v["side"] == "calibration")
uids = [cal[3], cal[60], cal[120], cal[200]]
PW = os.path.join(SCR, "puma")
for d in ("int", "seg/native", "seg/tuned", "seg/low", "decisions"):
    os.makedirs(os.path.join(PW, d), exist_ok=True)
for u in uids:
    shutil.copy(os.path.join(U5W, "int", f"{u}.npy"), os.path.join(PW, "int", f"{u}.npy"))
    for st in ("native", "tuned", "low"):
        shutil.copy(os.path.join(U5W, "seg", st, f"{u}.npz"), os.path.join(PW, "seg", st, f"{u}.npz"))
manifest = {"salt": "dryrun", "held": {u: ("primary" if i % 2 == 0 else "metastatic") for i, u in enumerate(uids)}}
CD.PW = PW
CD.HELD_MANIFEST = os.path.join(PW, "HELD_MANIFEST.json")
CD.DECISIONS_FROZEN = os.path.join(PW, "DECISIONS_FROZEN.json")
json.dump(manifest, open(CD.HELD_MANIFEST, "w"))
CD.held = lambda: manifest


def fake_reference(self, roi, shape, format_check=False):
    assert self._open
    ref, ign = RN.refign("nuinsseg", roi)
    return ref, int(ref.max())


CD.Reader.reference = fake_reference
CD.Reader.__init__ = lambda self: (setattr(self, "_open", False), setattr(self, "_fmt", "x"), setattr(self, "_held", None))[0]
H.ROOT = SCR
H.CALW = os.path.join(SCR, "cal")
H.DEC = os.path.join(PW, "decisions")
H.RES = os.path.join(SCR, "results")
os.makedirs(os.path.join(H.CALW, "final"), exist_ok=True)
for f in ("CALIBRATED.json", "STRICT.json", "TOLERANT.json", "MATCHED_SEARCH.json"):
    shutil.copy(os.path.join(ROOT, "data/work/cal/final", f), os.path.join(H.CALW, "final", f))
json.dump({"calibration_records": {f: MF.sha(os.path.join(H.CALW, "final", f)) for f in
                                   ("CALIBRATED.json", "STRICT.json", "TOLERANT.json", "MATCHED_SEARCH.json")}},
          open(os.path.join(SCR, "FREEZE.json"), "w"))
H.strong_native_held()
for a in ("CALIBRATED", "STRICT", "TOLERANT", "CAL_BLIND_1", "CAL_SHUFFLED_1"):
    H.run_arm("held", a)
H.matched("held")
H.matched_u5()
H.freeze_decisions()
H.evaluate()
r = json.load(open(os.path.join(H.RES, "RESULTS.json")))
print(json.dumps(r["primary"]))
print({a: (round(s["mean_image_f1"], 4), s.get("accepted_edits"), s.get("harmful")) for a, s in r["arms"].items()})
