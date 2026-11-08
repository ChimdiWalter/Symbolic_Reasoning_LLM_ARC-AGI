"""U5 data access (PROTOCOL.md sections 3 and 4; Amendment 1): archive listings -> parents -> split; inputs, intensity
images; reference masks guarded so that evaluation references are decoded only after DECISIONS_FROZEN.json exists and
the evaluator opens them. Read archives with python3 -I only.
    u5data.py manifest DS     write the grouping and split (file names only)
    u5data.py convert DS      inputs and intensity images of every pooled image; calibration references"""
import hashlib
import io
import json
import os
import re
import sys
import zipfile

import numpy as np

R = "/path/to/repository"
E = os.path.join(R, "experiments/universality_bio_grammar_20261103")
DATA = "/path/to/bio_data"
WORK = os.path.join(DATA, "work")
RAW = os.path.join(DATA, "raw")
FROZEN = os.path.join(WORK, "DECISIONS_FROZEN.json")
PRIVATE = os.path.join(DATA, "private")       # Amendment 8: private targets (mode 0700, outside git)


def private_adapter(ds):
    """Amendment 8: the reader of a private target, kept outside git with its private addendum and frozen by hash
    there; None for the public datasets."""
    if ds in DATASETS:
        return None
    p = os.path.join(PRIVATE, ds, "adapter.py")
    if not os.path.exists(p):
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"u5private_{ds}", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
U1 = os.path.join(R, "experiments/universality_submitted_pkg_20261101/scripts")

DATASETS = {
    "livecell": {"cap": 720, "licence": "CC BY-NC 4.0 (images and annotations; github.com/sartorius-research/LIVECell)",
                 "segmenter": "cellpose3_cyto2"},
    "nuinsseg": {"cap": None, "licence": "CC BY 4.0 (Zenodo 10.5281/zenodo.10518968)",
                 "segmenter": "stardist_2D_versatile_he"},
    "fluoecoli": {"cap": 1500, "licence": "CC BY 4.0 (Zenodo 10.5281/zenodo.23389427)",
                  "segmenter": "cellpose4_cpsam_v2"},
    "fnc": {"cap": None, "licence": "CC BY 4.0 (AMS Acta eprint 7347, Fluorescent Neuronal Cells v2)",
            "segmenter": "stardist_2D_versatile_fluo"},
    "monusac": {"cap": None, "licence": "CC BY-NC-SA 4.0 (monusac-2020.grand-challenge.org/Data)",
                "segmenter": "stardist_2D_versatile_he"},
}
MONUSAC_ZIPS = {"train": "monusac/MoNuSAC_images_and_annotations.zip",
                "test": "monusac/MoNuSAC_Testing_Data_and_Annotations.zip"}
TCGA_PAT = re.compile(r"TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}")


def monuseg_training_patients():
    """Amendment 4, section 3: patient barcodes in the file names of the official MoNuSeg 2018 training archive."""
    z = zipfile.ZipFile(os.path.join(RAW, "monuseg_names", "MoNuSeg_2018_Training_Data.zip"))
    return sorted({m.group(0) for n in z.namelist() for m in [TCGA_PAT.search(n)] if m})
LC_PAT = re.compile(r"([A-Za-z0-9-]+)_Phase_([A-Z]\d+)_(\d+)_(\d+d\d+h\d+m)_(\d+)\.tif$")


def h8(s):
    return hashlib.sha256(s.encode()).hexdigest()


def wdir(ds, *a):
    p = os.path.join(WORK, ds, *a)
    os.makedirs(os.path.dirname(p) if a and "." in a[-1] else p, exist_ok=True)
    return p


def norm01(a, lo=1.0, hi=99.8):
    a = a.astype(np.float32)
    p0, p1 = np.percentile(a, [lo, hi])
    return np.clip((a - p0) / max(p1 - p0, 1e-6), 0, 1).astype(np.float32)


# ------------------------------------------------------------------------------------------------ listings ---------
def listing(ds):
    """[(uid, member, parent)] from archive names only."""
    out = []
    if ds == "livecell":
        z = zipfile.ZipFile(os.path.join(RAW, "livecell", "images.zip"))
        for n in z.namelist():
            m = LC_PAT.search(n.split("/")[-1])
            if not m or not n.endswith(".tif"):
                continue
            ct, w, loc, ts, cr = m.groups()
            out.append((n.split("/")[-1][:-4], n, f"{ct}|{w}"))        # Amendment 3: (cell line, well)
    elif ds == "nuinsseg":
        z = zipfile.ZipFile(os.path.join(RAW, "nuinsseg", "NuInsSeg.zip"))
        for n in z.namelist():
            parts = n.split("/")
            if len(parts) == 3 and parts[1] == "tissue images" and n.endswith(".png"):
                out.append((parts[2][:-4], n, parts[0]))
    elif ds == "fnc":                                   # Amendment 2: the backup, parents = tissue sections
        import pandas as pd
        z = zipfile.ZipFile(os.path.join(RAW, "fnc_v2", "green.zip"))
        have = set(z.namelist())
        md = pd.read_excel(os.path.join(RAW, "fnc_v2", "metadata_v2.xlsx"))
        md = md[(md.dataset == "green") & (md.partition.isin(["trainval", "test"]))]
        for _, r in md.iterrows():
            mem = f"green/{r.partition}/images/{r.image_name}"
            if mem in have:
                out.append((str(r.image_name)[:-4], mem, f"{r.animal_id}"))   # Amendment 3: the animal
    elif ds == "monusac":                               # Amendment 4: parents = TCGA patients
        excluded = set(monuseg_training_patients())
        for rel, zp in MONUSAC_ZIPS.items():
            z = zipfile.ZipFile(os.path.join(RAW, zp))
            names = set(z.namelist())
            for n in sorted(names):
                if not n.endswith(".xml"):
                    continue
                stem = n[:-4]
                img = stem + ".tif" if stem + ".tif" in names else (stem + ".svs" if stem + ".svs" in names else None)
                m = TCGA_PAT.search(stem.split("/")[-1])
                if img is None or m is None or m.group(0) in excluded:
                    continue
                out.append((stem.split("/")[-1], f"{rel}::{img}", m.group(0)))
    elif ds == "fluoecoli":
        z = zipfile.ZipFile(os.path.join(RAW, "fluoecoli", "FluoEcoli-Instance.zip"))
        stems = [n for n in z.namelist() if "/test/" in n and n.lower().endswith((".tif", ".tiff"))]
        for n in stems:
            stem = n.split("/")[-1].rsplit(".", 1)[0]
            out.append((stem, n, fluo_parent(stem)))
    return sorted(out)


def fluo_parent(stem):
    """Source full-size image of a patch: the stem without its trailing patch index (PROTOCOL.md section 4). The exact
    rule applied is recorded in DATA_MANIFEST.json."""
    return re.sub(r"[_-](?:p|patch|crop|tile)?\d+$", "", stem)


def manifest(ds):
    """Amendment 3: parents at the coarsest encoded independent unit. Images whose references were decoded for
    calibration under an earlier grouping (DATA_MANIFEST_v1.json) never enter evaluation: if their new parent is an
    evaluation parent they are dropped from the study, so every evaluation image is one whose reference was never
    decoded, and every parent lies wholly on one side."""
    v1p = os.path.join(WORK, ds, "DATA_MANIFEST_v1.json")
    decoded = set()
    if os.path.exists(v1p):
        decoded = {u for u, v in json.load(open(v1p))["images"].items() if v["side"] == "calibration"}
    items = listing(ds)
    parents = sorted({p for _, _, p in items}, key=lambda p: h8(f"{ds}:{p}"))
    k = round(0.4 * len(parents))
    cal, ev = parents[:k], parents[k:]
    ind_order = sorted(cal, key=lambda p: h8(f"induct:{p}"))
    ind, val = ind_order[:len(cal) // 2], ind_order[len(cal) // 2:]
    cap = DATASETS[ds]["cap"]
    by_p = {}
    for uid, mem, p in items:
        by_p.setdefault(p, []).append((uid, mem))
    quota = None if cap is None or len(items) <= cap else max(1, cap // len(parents))
    images = {}
    for p, lst in by_p.items():
        lst = sorted(lst, key=lambda x: h8(x[0]))
        if quota is not None:
            lst = lst[:quota]
        side = "calibration" if p in cal else "evaluation"
        role = "induction" if p in ind else ("validation" if p in val else "evaluation")
        for uid, mem in lst:
            if side == "evaluation" and uid in decoded:
                images[uid] = {"member": mem, "parent": p, "side": "dropped", "role": "dropped"}
            else:
                images[uid] = {"member": mem, "parent": p, "side": side, "role": role}
    man = {"dataset": ds, "licence": DATASETS[ds]["licence"], "segmenter": DATASETS[ds]["segmenter"],
           "parent_rule": {"livecell": "(cell line, well) from <type>_Phase_<well>_<loc>_<time>_<crop>.tif (Amendment 3)",
                           "nuinsseg": "organ folder (the archive encodes no slide or patient)",
                           "fluoecoli": "patch stem without its trailing patch index",
                           "fnc": "animal_id of metadata_v2.xlsx (Amendment 3)",
                           "monusac": "TCGA patient barcode (TCGA-XX-XXXX); patients of the MoNuSeg 2018 training "
                                      "archive excluded (Amendment 4)"}[ds],
           "dropped_rule": "evaluation-side images whose references were decoded under DATA_MANIFEST_v1 (Amendment 3)",
           "n_listed": len(items), "n_parents": len(parents), "quota_per_parent": quota,
           "parents": {"calibration": cal, "evaluation": ev, "induction": ind, "validation": val},
           "n_images": {s: sum(1 for v in images.values() if v["side"] == s) for s in ("calibration", "evaluation",
                                                                                         "dropped")},
           "n_evaluation_parents_with_images": len({v["parent"] for v in images.values() if v["side"] == "evaluation"}),
           "images": images}
    p = wdir(ds, "DATA_MANIFEST.json")
    json.dump(man, open(p, "w"), indent=1)
    return man


def load_manifest(ds):
    return json.load(open(os.path.join(WORK, ds, "DATA_MANIFEST.json")))


# ------------------------------------------------------------------------------------------------ decoding ---------
def _poly_labels(shape, anns):
    """Rasterize COCO polygons (skimage.draw.polygon), larger objects first so a smaller one keeps its pixels."""
    from skimage.draw import polygon
    objs = []
    for a in anns:
        m = np.zeros(shape, bool)
        for poly in a["segmentation"]:
            if len(poly) and isinstance(poly[0], (list, tuple)):          # [[x, y], ...]
                xs, ys = np.asarray([q[0] for q in poly], float), np.asarray([q[1] for q in poly], float)
            else:                                                          # [x1, y1, x2, y2, ...]
                xs, ys = np.asarray(poly[0::2], float), np.asarray(poly[1::2], float)
            rr, cc = polygon(ys, xs, shape)
            m[rr, cc] = True
        if m.any():
            objs.append(m)
    objs.sort(key=lambda m: -int(m.sum()))
    lab = np.zeros(shape, np.int32)
    for i, m in enumerate(objs, start=1):
        lab[m] = i
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from u5core import relabel  # noqa: E402
    return relabel(lab)


def decode_mask(a):
    sys.path.insert(0, U1)
    import masks as MK1
    return MK1.decode_mask(a)


class Reader:
    """Inputs and intensity images for every pooled image; references guarded by split."""

    def __init__(self, ds):
        self.ds = ds
        self.man = load_manifest(ds)
        self.img = self.man["images"]
        self._open = False
        self._z = None
        self._coco = None
        self._priv = private_adapter(ds)

    def member(self, uid):
        """(zip file, member name) of an image."""
        mem = self.img[uid]["member"]
        if self.ds == "monusac":
            rel, name = mem.split("::", 1)
            if not hasattr(self, "_zs"):
                self._zs = {}
            if rel not in self._zs:
                self._zs[rel] = zipfile.ZipFile(os.path.join(RAW, MONUSAC_ZIPS[rel]))
            return self._zs[rel], name
        return self.zf(), mem

    def zf(self):
        if self._z is None:
            f = {"livecell": "livecell/images.zip", "nuinsseg": "nuinsseg/NuInsSeg.zip",
                 "fluoecoli": "fluoecoli/FluoEcoli-Instance.zip", "fnc": "fnc_v2/green.zip"}[self.ds]
            self._z = zipfile.ZipFile(os.path.join(RAW, f))
        return self._z

    def raw(self, uid):
        import tifffile
        z, name = self.member(uid)
        b = z.read(name)
        if self.ds == "monusac":                       # .tif, else page 0 of the .svs (Amendment 4)
            a = tifffile.imread(io.BytesIO(b), key=0)
            a = a[..., :3] if a.ndim == 3 else np.stack([a] * 3, -1)
            return np.ascontiguousarray(a)
        if self.ds == "nuinsseg":
            from skimage.io import imread
            a = imread(io.BytesIO(b))
            return a[..., :3] if a.ndim == 3 else np.stack([a] * 3, -1)
        if self.ds == "fnc":
            from skimage.io import imread
            a = imread(io.BytesIO(b))
            return np.ascontiguousarray(a[..., 1]) if a.ndim == 3 else a       # the green channel
        a = tifffile.imread(io.BytesIO(b))
        if a.ndim == 3:
            a = a[0] if a.shape[0] <= 4 else a[..., 0]
        return a

    def intensity(self, uid, raw=None):
        a = self.raw(uid) if raw is None else raw
        if self.ds in ("nuinsseg", "monusac"):
            from skimage.color import rgb2hed
            return norm01(rgb2hed(a[..., :3])[..., 0])
        return norm01(a)

    def _guard(self, uid):
        if self.img[uid]["side"] == "dropped":
            raise PermissionError(f"{uid} was dropped (Amendment 3); its reference is never read again")
        if self.img[uid]["side"] in ("evaluation", "sensitivity") and not self._open:
            raise PermissionError(f"evaluation reference {uid} requested before the evaluator was opened")

    def open_evaluator(self):
        if self._priv is not None:                  # Amendment 8: a private target's own frozen decisions
            if not self._priv.evaluator_ready():
                raise PermissionError("the private target's frozen decisions are missing")
        elif not os.path.exists(FROZEN):
            raise PermissionError("DECISIONS_FROZEN.json missing")
        self._open = True

    def _coco_anns(self, uid):
        if self._coco is None:
            self._coco = {}
            files = {"livecell": [os.path.join(RAW, "livecell", f"livecell_coco_{s}.json") for s in ("train", "val", "test")],
                     "fluoecoli": [], "fnc": []}[self.ds]
            want = {}
            for u, v in self.img.items():
                if v["side"] == "calibration" or (self._open and v["side"] == "evaluation"):
                    want[os.path.basename(v["member"])] = u
            blobs = [json.load(open(f)) for f in files]
            if self.ds == "fnc":
                blobs = [json.loads(self.zf().read(f"green/{s}/ground_truths/COCO/annotations_green_{s}.json"))
                         for s in ("trainval", "test")]
            for d in blobs:
                ims = d["images"].values() if isinstance(d["images"], dict) else d["images"]
                idmap = {im["id"]: want[im["file_name"].split("/")[-1]] for im in ims
                         if im["file_name"].split("/")[-1] in want}
                anns = d["annotations"].values() if isinstance(d["annotations"], dict) else d["annotations"]
                for a in anns:
                    u = idmap.get(a["image_id"])
                    if u is None:
                        continue
                    if self.ds == "fnc":                   # one record per image, one polygon of [x, y] per object
                        for poly in a["segmentation"]:
                            self._coco.setdefault(u, []).append({"segmentation": [poly]})
                    else:
                        self._coco.setdefault(u, []).append(a)
            del blobs
        return self._coco.get(uid, [])

    def _monusac_xml(self, uid):
        import xml.etree.ElementTree as ET
        z, name = self.member(uid)
        root = ET.fromstring(z.read(name.rsplit(".", 1)[0] + ".xml"))
        objs, amb = [], []
        for ann in root.iter("Annotation"):
            names = [a.get("Name", "") for a in ann.iter("Attribute")]
            is_amb = any("ambig" in s.lower() for s in names)
            for reg in ann.iter("Region"):
                pts = [[float(v.get("X")), float(v.get("Y"))] for v in reg.iter("Vertex")]
                if len(pts) >= 3:
                    (amb if is_amb else objs).append({"segmentation": [pts]})
        return objs, amb

    def ref(self, uid, shape):
        self._guard(uid)
        if self._priv is not None:
            return self._priv.ref(self, uid, shape)
        if self.ds == "monusac":
            return _poly_labels(shape, self._monusac_xml(uid)[0])
        if self.ds == "nuinsseg":
            import tifffile
            mem = self.img[uid]["member"].replace("/tissue images/", "/label masks/")[:-4] + ".tif"
            return decode_mask(tifffile.imread(io.BytesIO(self.zf().read(mem))))
        return _poly_labels(shape, self._coco_anns(uid))

    def ignore(self, uid, shape):
        self._guard(uid)
        if self._priv is not None:
            return None
        if self.ds == "monusac":
            amb = self._monusac_xml(uid)[1]
            return _poly_labels(shape, amb) > 0 if amb else np.zeros(shape, bool)
        if self.ds != "nuinsseg":
            return None
        from skimage.io import imread
        mem = self.img[uid]["member"].replace("/tissue images/", "/vague areas/mask binary/")
        try:
            a = imread(io.BytesIO(self.zf().read(mem)))
        except KeyError:
            return np.zeros(shape, bool)
        a = a[..., 0] if a.ndim == 3 else a
        return a > 0


def convert(ds):
    """Inputs (npy) and intensity images (float16 npy) of every pooled image; calibration references and ignore
    masks (npz). Evaluation references are not decoded here. Existing inputs are kept (Amendment 3 regrouping); the
    references of dropped images are moved to ref_cal_dropped/ and never read."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from u5core import drop_ignored
    rd = Reader(ds)
    for uid, v in sorted(rd.img.items()):
        rp = os.path.join(WORK, ds, "ref_cal", f"{uid}.npz")
        if v["side"] != "calibration" and os.path.exists(rp):
            os.makedirs(os.path.join(WORK, ds, "ref_cal_dropped"), exist_ok=True)
            os.replace(rp, os.path.join(WORK, ds, "ref_cal_dropped", f"{uid}.npz"))
        if os.path.exists(os.path.join(WORK, ds, "int", f"{uid}.npy")) and (v["side"] != "calibration" or
                                                                           os.path.exists(rp)):
            continue
        a = rd.raw(uid)
        np.save(wdir(ds, "raw", f"{uid}.npy"), a)
        np.save(wdir(ds, "int", f"{uid}.npy"), rd.intensity(uid, a).astype(np.float16))
        if v["side"] == "calibration":
            shape = a.shape[:2]
            ref = rd.ref(uid, shape)
            ign = rd.ignore(uid, shape)
            if ign is not None:
                ref = drop_ignored(ref, ign)
            np.savez_compressed(wdir(ds, "ref_cal", f"{uid}.npz"), ref=ref.astype(np.int32),
                                ign=np.zeros(shape, bool) if ign is None else ign)
    print(ds, len(rd.img), "images converted")


if __name__ == "__main__":
    cmd, ds = sys.argv[1], sys.argv[2]
    if cmd == "manifest":
        m = manifest(ds)
        print(json.dumps({k: m[k] for k in ("dataset", "n_listed", "n_parents", "quota_per_parent", "n_images")}))
        print({k: len(v) for k, v in m["parents"].items()})
    elif cmd == "convert":
        convert(ds)
