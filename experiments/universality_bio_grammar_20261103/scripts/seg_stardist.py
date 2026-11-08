"""U5 baselines with StarDist (PROTOCOL.md section 5): NATIVE (the model's own thresholds), TUNED (optimize_thresholds on
calibration images, save_to_json=False) and LOW (TUNED prob threshold x 0.5, for add_lowthresh). StarDist venv, -I.
    seg_stardist.py DS MODEL cal    tune on calibration and segment calibration images
    seg_stardist.py DS MODEL eval   segment evaluation images with the frozen thresholds (after the hold is released)"""
import hashlib
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "4")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
DATA = "/path/to/bio_data"
W = os.path.join(DATA, "work")
SEG = "seg_smoke" if os.environ.get("U5_SMOKE") else "seg"   # smoke tests write elsewhere


def main(ds, model_name, mode):
    import numpy as np
    import tensorflow as tf
    from csbdeep.utils import normalize
    from stardist.models import StarDist2D
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    model = StarDist2D(None, name=model_name, basedir=os.path.join(DATA, "models", "stardist"))
    man = json.load(open(os.path.join(W, ds, "DATA_MANIFEST.json")))
    side = "calibration" if mode == "cal" else "evaluation"
    units = sorted(u for u, v in man["images"].items() if v["side"] == side)
    if os.environ.get("U5_SMOKE"):
        units = units[:int(os.environ["U5_SMOKE"])]
    rgb = model.config.n_channel_in == 3
    norm = lambda a: normalize(a.astype(np.float32), 1, 99.8, axis=(0, 1, 2) if rgb else (0, 1))   # noqa: E731
    out = {k: os.path.join(W, ds, SEG, k) for k in ("native", "tuned", "low")}
    for p in out.values():
        os.makedirs(p, exist_ok=True)
    tp = os.path.join(W, ds, SEG, "THRESHOLDS.json")
    t0 = time.process_time()
    native = {k: float(v) for k, v in model.thresholds._asdict().items()}   # before tuning, which overwrites them
    if mode == "cal":
        X = [norm(np.load(os.path.join(W, ds, "raw", f"{u}.npy"))) for u in units]
        Y = [np.load(os.path.join(W, ds, "ref_cal", f"{u}.npz"))["ref"] for u in units]
        th = {k: float(v) for k, v in dict(model.optimize_thresholds(X, Y, save_to_json=False)).items()}
        json.dump({"native": native, "tuned": th,
                   "low": {"prob": 0.5 * th["prob"], "nms": th["nms"]}, "tune_cpu_s": round(time.process_time() - t0, 1)},
                  open(tp, "w"), indent=1)
    T = json.load(open(tp))
    man_out = {"thresholds": T, "units": {}}
    for u in units:
        t1 = time.process_time()
        x = norm(np.load(os.path.join(W, ds, "raw", f"{u}.npy")))
        prob, dist = model.predict(x)
        rec = {}
        for k in ("native", "tuned", "low"):
            lab, _ = model._instances_from_prediction(x.shape[:2], prob, dist, prob_thresh=T[k]["prob"],
                                                      nms_thresh=T[k]["nms"])
            lab = lab.astype(np.int32)
            np.savez_compressed(os.path.join(out[k], f"{u}.npz"), labels=lab)
            rec[k] = {"objects": int(lab.max()), "sha256": hashlib.sha256(lab.tobytes()).hexdigest()}
        rec["cpu_s"] = round(time.process_time() - t1, 2)
        man_out["units"][u] = rec
    json.dump(man_out, open(os.path.join(W, ds, SEG, f"MANIFEST_{mode}.json"), "w"), indent=1)
    print(ds, mode, len(units), "images", T["tuned"])


if __name__ == "__main__":
    main(*sys.argv[1:4])
