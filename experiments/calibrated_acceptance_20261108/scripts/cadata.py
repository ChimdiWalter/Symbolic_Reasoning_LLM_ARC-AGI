"""Calibrated-acceptance study: fresh held data (PUMA melanoma ROIs, Zenodo 10.5281/zenodo.13859989, CC BY 4.0).
Read archives with python -I only.

Rules this module enforces (PROTOCOL.md sections 3 and 6):
- One FORMAT ROI, fixed by an unsalted hash before anything is opened, may be opened for the format and timing check.
  It is excluded from the held pool and from the reserve.
- HELD ROIs are chosen only after the coordinator's GO file exists: per stratum (primary, metastatic), the ROIs in
  sha256 order of "<salt>:<roi>", where salt = sha256 of the bytes of GO_CAL; the first N_PER_STRATUM are held, the
  rest are the RESERVE and are never opened by this study.
- A held image is opened only after GO. A held reference is decoded only after DECISIONS_FROZEN.json exists and the
  evaluator is opened (the same guard as U5's Reader).
    cadata.py format        open the format ROI only: image format, polygon count, rasterization (no scoring)
    cadata.py select        after GO: write work/puma/HELD_MANIFEST.json
    cadata.py convert       after GO: inputs (npy) and intensity images of the held ROIs"""
import hashlib
import io
import json
import os
import sys
import zipfile

import numpy as np

R = "/path/to/repository"
ROOT = os.path.join(R, "experiments/calibrated_acceptance_20261108")
U5S = os.path.join(R, "experiments/universality_bio_grammar_20261103/scripts")
DATA = os.path.join(ROOT, "data")
RAWD = os.path.join(DATA, "raw", "puma_zenodo_13859989")
WORK = os.path.join(DATA, "work")
PW = os.path.join(WORK, "puma")
GO = os.path.join(ROOT, "GO_CAL")
TIF_ZIP = os.path.join(RAWD, "01_training_dataset_tif_ROIs.zip")
NUC_ZIP = os.path.join(RAWD, "01_training_dataset_geojson_nuclei.zip")
ZIP_MD5 = {"01_training_dataset_tif_ROIs.zip": "0310c5a303b986eb4ff2dba4ddbfb70e",
           "01_training_dataset_geojson_nuclei.zip": "595d8ec2f8bb8e09e1e9fc1df2c4c09e"}
HELD_MANIFEST = os.path.join(PW, "HELD_MANIFEST.json")
DECISIONS_FROZEN = os.path.join(PW, "DECISIONS_FROZEN.json")
N_PER_STRATUM = 50
STRATA = ("primary", "metastatic")
FORMAT_KEY = "calacc_format:"
if U5S not in sys.path:
    sys.path.insert(0, U5S)


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    d = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def rois():
    """ROI ids from the image archive's member names (names only; nothing is decoded)."""
    with zipfile.ZipFile(TIF_ZIP) as z:
        return sorted(n[:-4] for n in z.namelist() if n.endswith(".tif") and "/" not in n)


def stratum(roi):
    s = roi.split("_")[2]
    assert s in STRATA, roi
    return s


def format_roi(all_rois=None):
    """The single ROI that may be opened before GO (format and timing check). Fixed by an unsalted hash."""
    return min(all_rois or rois(), key=lambda r: h(FORMAT_KEY + r))


def held_selection(salt, all_rois=None):
    """(held {roi: stratum}, reserve [roi]) for a salt (the sha256 of GO_CAL). Deterministic; opens nothing."""
    all_rois = all_rois or rois()
    fmt = format_roi(all_rois)
    held, reserve = {}, []
    for s in STRATA:
        pool = sorted((r for r in all_rois if r != fmt and stratum(r) == s), key=lambda r: (h(f"{salt}:{r}"), r))
        for r in pool[:N_PER_STRATUM]:
            held[r] = s
        reserve += pool[N_PER_STRATUM:]
    return held, sorted(reserve)


def go_salt():
    """sha256 of the coordinator's GO file, or None before GO. The file's bytes are hashed, never interpreted."""
    return file_sha(GO) if os.path.exists(GO) else None


def select():
    salt = go_salt()
    if salt is None:
        raise PermissionError("GO_CAL does not exist: the held ROIs cannot be chosen yet")
    if os.path.exists(HELD_MANIFEST):
        m = json.load(open(HELD_MANIFEST))
        assert m["salt"] == salt, "GO_CAL changed after the held ROIs were chosen"
        return m
    all_rois = rois()
    held, reserve = held_selection(salt, all_rois)
    m = {"dataset": "puma", "salt": salt, "salt_rule": "sha256 of the bytes of GO_CAL",
         "selection_rule": f"per stratum, sha256('<salt>:<roi>') order, first {N_PER_STRATUM}",
         "format_roi": format_roi(all_rois), "n_rois": len(all_rois), "held": held, "reserve": reserve,
         "n_held": len(held), "n_reserve": len(reserve)}
    os.makedirs(PW, exist_ok=True)
    tmp = HELD_MANIFEST + ".tmp"
    json.dump(m, open(tmp, "w"), indent=1)
    os.replace(tmp, HELD_MANIFEST)
    print(json.dumps({k: m[k] for k in ("salt", "format_roi", "n_held", "n_reserve")}))
    return m


def held():
    if not os.path.exists(HELD_MANIFEST):
        raise PermissionError("no HELD_MANIFEST.json: the held ROIs are chosen only after GO")
    m = json.load(open(HELD_MANIFEST))
    assert m["salt"] == go_salt(), "GO_CAL changed after the held ROIs were chosen"
    return m


def norm01(a, lo=1.0, hi=99.8):
    import u5data as UD                     # U5's normalization, unchanged
    return UD.norm01(a, lo, hi)


def intensity(rgb):
    """U5's H&E intensity image (PROTOCOL U5 section 3.2): haematoxylin optical density, rgb2hed channel 0, normalized
    at (1, 99.8)."""
    from skimage.color import rgb2hed
    return norm01(rgb2hed(rgb[..., :3])[..., 0])


def geojson_labels(shape, feats):
    """Rasterize PUMA's GeoJSON nucleus polygons with U5's rasterizer (`u5data._poly_labels`: skimage polygon fill of
    each exterior ring, larger objects first so a smaller one keeps its pixels). MultiPolygon parts belong to one
    object; interior rings (holes) are not subtracted."""
    import u5data as UD
    anns = []
    for f in feats:
        g = f.get("geometry") or {}
        if g.get("type") == "Polygon":
            rings = [g["coordinates"][0]] if g.get("coordinates") else []
        elif g.get("type") == "MultiPolygon":
            rings = [p[0] for p in g.get("coordinates", []) if p]
        else:
            continue
        rings = [r for r in rings if len(r) >= 3]
        if rings:
            anns.append({"segmentation": rings})
    return UD._poly_labels(shape, anns)


class Reader:
    """Images and references of PUMA ROIs, guarded (module docstring)."""

    def __init__(self):
        self._open = False
        self._fmt = format_roi()
        self._held = None

    def _held_set(self):
        if self._held is None:
            self._held = held()["held"]
        return self._held

    def _guard_image(self, roi):
        if roi == self._fmt:
            return
        if roi not in self._held_set():
            raise PermissionError(f"{roi} is not a held ROI; reserve ROIs are never opened")

    def image(self, roi):
        self._guard_image(roi)
        import tifffile
        with zipfile.ZipFile(TIF_ZIP) as z:
            a = tifffile.imread(io.BytesIO(z.read(roi + ".tif")))
        if a.ndim == 2:
            a = np.stack([a] * 3, -1)
        a = a[..., :3]
        assert a.dtype == np.uint8, a.dtype
        return np.ascontiguousarray(a)

    def open_evaluator(self):
        if not os.path.exists(DECISIONS_FROZEN):
            raise PermissionError("DECISIONS_FROZEN.json missing: references stay closed")
        self._open = True

    def reference(self, roi, shape, format_check=False):
        if format_check:
            if roi != self._fmt:
                raise PermissionError("the format check may decode only the format ROI")
        else:
            if roi not in self._held_set():
                raise PermissionError(f"{roi} is not a held ROI")
            if not self._open:
                raise PermissionError(f"reference {roi} requested before the evaluator was opened")
        with zipfile.ZipFile(NUC_ZIP) as z:
            d = json.loads(z.read(roi + "_nuclei.geojson"))
        feats = d["features"] if isinstance(d, dict) else d
        return geojson_labels(shape, feats), len(feats)


def check_archives():
    out = {}
    for name, md5 in ZIP_MD5.items():
        p = os.path.join(RAWD, name)
        d = hashlib.md5()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                d.update(b)
        out[name] = {"md5_ok": d.hexdigest() == md5, "sha256": file_sha(p), "bytes": os.path.getsize(p)}
    return out


def format_check():
    """Open the format ROI only (never held, never reserve): image dtype and shape, polygon count, rasterization."""
    rd = Reader()
    roi = rd._fmt
    a = rd.image(roi)
    ref, n_feat = rd.reference(roi, a.shape[:2], format_check=True)
    I = intensity(a)
    rec = {"format_roi": roi, "image_shape": list(a.shape), "image_dtype": str(a.dtype), "polygons": n_feat,
           "rasterized_objects": int(ref.max()), "intensity_range": [float(I.min()), float(I.max())],
           "archives": check_archives(), "n_rois": len(rois()),
           "per_stratum": {s: sum(1 for r in rois() if stratum(r) == s) for s in STRATA}}
    os.makedirs(os.path.join(WORK, "format_check"), exist_ok=True)
    np.save(os.path.join(WORK, "format_check", f"{roi}_raw.npy"), a)
    json.dump(rec, open(os.path.join(WORK, "format_check", "FORMAT_CHECK.json"), "w"), indent=1)
    print(json.dumps(rec))
    return rec


def convert():
    """After GO: inputs (npy uint8) and intensity images (float16) of the held ROIs. References are not decoded."""
    m = held()
    rd = Reader()
    for d in ("raw", "int"):
        os.makedirs(os.path.join(PW, d), exist_ok=True)
    for roi in sorted(m["held"]):
        pi = os.path.join(PW, "int", f"{roi}.npy")
        if os.path.exists(pi):
            continue
        a = rd.image(roi)
        np.save(os.path.join(PW, "raw", f"{roi}.npy"), a)
        np.save(pi + ".tmp.npy", intensity(a).astype(np.float16))
        os.replace(pi + ".tmp.npy", pi)
    print("converted", len(m["held"]))


if __name__ == "__main__":
    {"format": format_check, "select": select, "convert": convert}[sys.argv[1]]()
