# make_curveball_submission.py
# usage:
#   python make_curveball_submission.py data/curveball submission_curveball.json CurveBallSubmission.zip
from __future__ import annotations
import os, sys, json, zipfile

def main(curve_dir, submission_curveball_json, out_zip):
    pred = json.load(open(submission_curveball_json))
    os.makedirs("_curveball_out", exist_ok=True)
    missing=[]
    paths=[]
    for stem in [f"example{str(i).zfill(2)}" for i in range(1,12)]:
        src = os.path.join(curve_dir, f"{stem}.json")
        if not os.path.isfile(src):
            missing.append(stem); continue
        spec = json.load(open(src))
        guess = pred.get(stem)
        if not guess:
            missing.append(stem); continue
        # write <stem>_guess.json beside
        outp = os.path.join("_curveball_out", f"{stem}_guess.json")
        json.dump(guess, open(outp,"w"))
        paths.append(outp)
    if missing:
        print("WARNING: missing predictions for:", missing)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, arcname=os.path.basename(p))
    print("Wrote Curve-Ball ZIP:", out_zip)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: python make_curveball_submission.py data/curveball submission_curveball.json CurveBallSubmission.zip")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])

