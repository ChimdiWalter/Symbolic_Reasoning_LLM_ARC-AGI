"""U5 baselines with Cellpose (PROTOCOL.md section 5): one network pass per image at the defaults (NATIVE), masks for
the threshold grid recomputed from the stored network outputs with the model's own `_compute_masks` (checked equal to
eval's masks at the defaults), TUNED = best grid point by pooled calibration F1 (ties: defaults, then lower
thresholds), LOW = TUNED with the cell-probability threshold minus 2.
    seg_cellpose.py DS cal | eval
Cellpose 3 cyto2 (livecell) runs in the cellpose3_u5 venv; Cellpose-SAM v2 (fluoecoli) in <second python environment>. -I."""
import hashlib
import json
import os
import sys
import time

DATA = "/path/to/bio_data"
W = os.path.join(DATA, "work")
SEG = "seg_smoke" if os.environ.get("U5_SMOKE") else "seg"   # smoke tests write elsewhere
os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", os.path.join(DATA, "models", "cellpose"))
os.environ.setdefault("OMP_NUM_THREADS", "4")
FLOW = (0.2, 0.4, 0.6, 0.8, 1.0)
CPROB = (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0)
DEF = (0.4, 0.0)


def f1_counts(ref, lab):
    import numpy as np
    nr, npd = int(ref.max()), int(lab.max())
    if nr == 0 or npd == 0:
        return nr, npd, 0
    both = (ref > 0) & (lab > 0)
    key = ref[both].astype(np.int64) * (npd + 1) + lab[both]
    uk, cnt = np.unique(key, return_counts=True)
    r, p = uk // (npd + 1), uk % (npd + 1)
    ar = np.bincount(ref.ravel(), minlength=nr + 1)
    ap = np.bincount(lab.ravel(), minlength=npd + 1)
    iou = cnt / np.maximum(ar[r] + ap[p] - cnt, 1)
    return nr, npd, int((iou > 0.5).sum())


def main(ds, mode):
    import numpy as np
    import torch
    torch.set_num_threads(4)
    from cellpose import models
    gpu = os.environ.get("U5_GPU") == "1" and torch.cuda.is_available()
    if ds == "livecell":
        model = models.Cellpose(gpu=gpu, model_type="cyto2")
        cp = model.cp

        def run(x):
            masks, flows, styles, diams = model.eval(x, channels=[0, 0], diameter=None, flow_threshold=DEF[0],
                                                     cellprob_threshold=DEF[1])
            rescale = cp.diam_mean / float(diams)
            return masks, flows, 200.0 / rescale, float(diams)
    else:
        model = models.CellposeModel(gpu=gpu, pretrained_model="cpsam_v2")
        cp = model

        def run(x):
            masks, flows, styles = model.eval(x, diameter=None, flow_threshold=DEF[0], cellprob_threshold=DEF[1])
            return masks, flows, 200, None
    man = json.load(open(os.path.join(W, ds, "DATA_MANIFEST.json")))
    side = "calibration" if mode == "cal" else "evaluation"
    units = sorted(u for u, v in man["images"].items() if v["side"] == side)
    if os.environ.get("U5_SMOKE"):
        units = units[:int(os.environ["U5_SMOKE"])]
    fd = os.path.join(W, ds, SEG, "flows")
    for k in ("native", "tuned", "low", "flows"):
        os.makedirs(os.path.join(W, ds, SEG, k), exist_ok=True)

    def masks_at(dP, cellprob, niter, flow, cprob, shape):
        m = cp._compute_masks((1,) + tuple(shape), dP[:, None], cellprob[None], flow_threshold=flow,
                              cellprob_threshold=cprob, niter=niter)
        return np.asarray(m).squeeze().astype(np.int32)

    def grid_masks(dP, cellprob, niter, shape):
        """The whole threshold grid with one dynamics run per cell-probability threshold: masks before the flow QC
        (compute_masks with flow_threshold 0), per-mask flow errors once, then each flow threshold's removal and
        fill_holes_and_remove_small_masks, in compute_masks' own order (checked equal on the first images)."""
        from cellpose import dynamics, metrics, utils
        out = {}
        if ds != "livecell":
            for fl in FLOW:
                for cpb in CPROB:
                    out[(fl, cpb)] = masks_at(dP, cellprob, niter, fl, cpb, shape)
            return out
        for cpb in CPROB:
            mA = dynamics.compute_masks(dP, cellprob, niter=niter, cellprob_threshold=cpb, flow_threshold=0.0,
                                        interp=True, max_size_fraction=0.4, device=cp.device)
            err = metrics.flow_error(mA, dP, cp.device)[0] if mA.max() > 0 else np.zeros(0)
            for fl in FLOW:
                m = mA.copy()
                if m.max() > 0:
                    m[np.isin(m, 1 + (err > fl).nonzero()[0])] = 0
                    if m.max() < 2 ** 16 and m.dtype != "uint16":
                        m = m.astype("uint16")
                out[(fl, cpb)] = np.asarray(utils.fill_holes_and_remove_small_masks(m, min_size=15)).astype(np.int32)
        return out

    t0 = time.process_time()
    rec, exact = {}, 0
    reused = 0
    for u in units:
        t1 = time.process_time()
        x = np.load(os.path.join(W, ds, "raw", f"{u}.npy"))
        fp, npth = os.path.join(fd, f"{u}.npz"), os.path.join(W, ds, SEG, "native", f"{u}.npz")
        if os.path.exists(fp) and os.path.exists(npth):        # Amendment 3: network outputs computed earlier
            z = np.load(fp)
            m_nat = np.load(npth)["labels"]
            m0 = masks_at(z["dP"], z["cellprob"], float(z["niter"]), DEF[0], DEF[1], x.shape[:2])
            exact += int(np.array_equal(m0, m_nat))
            rec[u] = {"objects": int(m_nat.max()), "niter": float(z["niter"]), "reused_network_outputs": True}
            reused += 1
            continue
        masks, flows, niter, diam = run(x)
        dP, cellprob = np.asarray(flows[1]), np.asarray(flows[2])
        np.savez_compressed(fp, dP=dP.astype(np.float32), cellprob=cellprob.astype(np.float32), niter=niter)
        m0 = masks_at(dP, cellprob, niter, DEF[0], DEF[1], x.shape[:2])
        exact += int(np.array_equal(m0, np.asarray(masks).astype(np.int32)))
        np.savez_compressed(npth, labels=np.asarray(masks).astype(np.int32))
        rec[u] = {"objects": int(np.asarray(masks).max()), "diameter": diam, "niter": niter,
                  "net_cpu_s": round(time.process_time() - t1, 2)}
    tp = os.path.join(W, ds, SEG, "THRESHOLDS.json")
    if mode == "cal":
        grid = {}
        checks = 0
        for n_u, u in enumerate(units):
            z = np.load(os.path.join(fd, f"{u}.npz"))
            ref = np.load(os.path.join(W, ds, "ref_cal", f"{u}.npz"))["ref"]
            labs = grid_masks(z["dP"], z["cellprob"], float(z["niter"]), ref.shape)
            if n_u < 2:                                    # exactness of the factorized grid against _compute_masks
                for (fl, cpb) in ((0.4, 0.0), (0.8, -2.0), (0.2, 1.0)):
                    want = masks_at(z["dP"], z["cellprob"], float(z["niter"]), fl, cpb, ref.shape)
                    if not np.array_equal(labs[(fl, cpb)], want):
                        print("grid recompute mismatch", u, fl, cpb)
                        sys.exit(5)
                    checks += 1
            for (fl, cpb), lab in labs.items():
                c = f1_counts(ref, lab)
                g = grid.setdefault(f"{fl}|{cpb}", [0, 0, 0])
                for i in range(3):
                    g[i] += c[i]
        f1 = {k: 2 * v[2] / max(v[0] + v[1], 1) for k, v in grid.items()}
        keys = sorted(f1, key=lambda k: (-round(f1[k], 12), k != f"{DEF[0]}|{DEF[1]}", float(k.split("|")[0]),
                                          float(k.split("|")[1])))
        best = keys[0]
        fl, cpb = (float(v) for v in best.split("|"))
        json.dump({"native": {"flow": DEF[0], "cellprob": DEF[1]}, "tuned": {"flow": fl, "cellprob": cpb},
                   "low": {"flow": fl, "cellprob": cpb - 2.0}, "grid_pooled_f1": f1,
                   "tune_cpu_s": round(time.process_time() - t0, 1)}, open(tp, "w"), indent=1)
    T = json.load(open(tp))
    for u in units:
        z = np.load(os.path.join(fd, f"{u}.npz"))
        x = np.load(os.path.join(W, ds, "raw", f"{u}.npy"))
        for k in ("tuned", "low"):
            lab = masks_at(z["dP"], z["cellprob"], float(z["niter"]), T[k]["flow"], T[k]["cellprob"], x.shape[:2])
            np.savez_compressed(os.path.join(W, ds, SEG, k, f"{u}.npz"), labels=lab)
            rec[u][k] = {"objects": int(lab.max()), "sha256": hashlib.sha256(lab.tobytes()).hexdigest()}
    json.dump({"thresholds": T, "gpu": gpu, "exact_recompute": f"{exact}/{len(units)}", "reused": reused, "units": rec},
              open(os.path.join(W, ds, SEG, f"MANIFEST_{mode}.json"), "w"), indent=1)
    print(ds, mode, len(units), "images; exact recompute", exact, "/", len(units), T["tuned"])
    if exact != len(units):
        sys.exit(4)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
