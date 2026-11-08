"""Check every hash in FREEZE.json against the files on disk; exit 1 on any difference (the held chain's first step).
python -I -B scripts/verify_freeze.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_freeze as MF  # noqa: E402

ROOT = MF.ROOT


def main():
    fz = json.load(open(os.path.join(ROOT, "FREEZE.json")))
    bad = []
    for p, h in fz["files"].items():
        if MF.sha(os.path.join(ROOT, p)) != h:
            bad.append(p)
    for p, h in fz["u5_reused"].items():
        if MF.sha(p) != h:
            bad.append(p)
    for folder, v in fz["u5_reused_trees"].items():
        if MF.tree_sha(folder)[0] != v["sha256_of_listing"]:
            bad.append(folder)
    raw = os.path.join(ROOT, "data/raw/puma_zenodo_13859989")
    for f, h in fz["data"]["archives"].items():
        if MF.sha(os.path.join(raw, f)) != h:
            bad.append(f)
    for f, h in fz["data"]["model_copy"].items():
        if MF.sha(os.path.join(ROOT, "data/models/stardist/2D_versatile_he", f)) != h:
            bad.append(f)
    for f, h in fz["calibration_records"].items():
        if MF.sha(os.path.join(ROOT, "data/work/cal/final", f)) != h:
            bad.append(f)
        if MF.sha(os.path.join(ROOT, "calibration/final", f)) != h:      # the committed copy
            bad.append("calibration/final/" + f)
    print(json.dumps({"checked": True, "mismatches": bad}))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
