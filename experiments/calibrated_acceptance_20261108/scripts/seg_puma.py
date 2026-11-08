"""StarDist 2D_versatile_he on PUMA ROIs at U5's NuInsSeg thresholds, unchanged (no tuning on PUMA). StarDist venv, -I.
The model files are a byte copy of U5's (sha256 in FREEZE.json); the thresholds are read from U5's NuInsSeg
THRESHOLDS.json (tuned prob 0.4562, nms 0.3; low = tuned prob x 0.5). The code follows U5's seg_stardist.py: joint
(1, 99.8) normalization over the three channels, model.predict, then _instances_from_prediction at each threshold.
    seg_puma.py format     the format ROI only (timing; writes nothing that is scored)
    seg_puma.py held       every held ROI (after GO)"""
import hashlib
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "4")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
ROOT = "/path/to/repository/experiments/calibrated_acceptance_20261108"
WORK = os.path.join(ROOT, "data", "work")
MODELS = os.path.join(ROOT, "data", "models", "stardist")
U5_THRESHOLDS = "/path/to/bio_data/work/nuinsseg/seg/THRESHOLDS.json"


def main(mode):
    import numpy as np
    import tensorflow as tf
    from csbdeep.utils import normalize
    from stardist.models import StarDist2D
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    model = StarDist2D(None, name="2D_versatile_he", basedir=MODELS)
    T = json.load(open(U5_THRESHOLDS))
    if mode == "format":
        fc = json.load(open(os.path.join(WORK, "format_check", "FORMAT_CHECK.json")))
        units = {fc["format_roi"]: os.path.join(WORK, "format_check", f"{fc['format_roi']}_raw.npy")}
        out_root = os.path.join(WORK, "format_check", "seg")
    else:
        m = json.load(open(os.path.join(WORK, "puma", "HELD_MANIFEST.json")))
        units = {u: os.path.join(WORK, "puma", "raw", f"{u}.npy") for u in sorted(m["held"])}
        out_root = os.path.join(WORK, "puma", "seg")
    out = {k: os.path.join(out_root, k) for k in ("native", "tuned", "low")}
    for p in out.values():
        os.makedirs(p, exist_ok=True)
    norm = lambda a: normalize(a.astype(np.float32), 1, 99.8, axis=(0, 1, 2))   # noqa: E731
    man_p = os.path.join(out_root, "MANIFEST.json")
    man_out = json.load(open(man_p)) if os.path.exists(man_p) else {"thresholds": T, "units": {}}
    for u, p in units.items():
        if u in man_out["units"] and all(os.path.exists(os.path.join(out[k], f"{u}.npz")) for k in out):
            continue
        t1, w1 = time.process_time(), time.time()
        x = norm(np.load(p))
        prob, dist = model.predict(x)
        rec = {}
        for k in ("native", "tuned", "low"):
            lab, _ = model._instances_from_prediction(x.shape[:2], prob, dist, prob_thresh=T[k]["prob"],
                                                      nms_thresh=T[k]["nms"])
            lab = lab.astype(np.int32)
            np.savez_compressed(os.path.join(out[k], f"{u}.npz"), labels=lab)
            rec[k] = {"objects": int(lab.max()), "sha256": hashlib.sha256(lab.tobytes()).hexdigest()}
        rec["cpu_s"] = round(time.process_time() - t1, 2)
        rec["wall_s"] = round(time.time() - w1, 2)
        man_out["units"][u] = rec
        json.dump(man_out, open(man_p + ".tmp", "w"), indent=1)
        os.replace(man_p + ".tmp", man_p)
    print(mode, len(units), "images", T["tuned"])


if __name__ == "__main__":
    main(sys.argv[1])
