"""Write FREEZE.json (PROTOCOL.md section 10): sha256 of this study's code, configuration, protocol, adapter card and
data manifest; of every reused U5 file (code, data records, model); of the downloaded archives and the format check;
and of the frozen calibration records (STRICT, TOLERANT, CALIBRATED, MATCHED_SEARCH on all 12 calibration organs).
python3 -I -B scripts/make_freeze.py"""
import glob
import hashlib
import json
import os
import time

ROOT = "/path/to/repository/experiments/calibrated_acceptance_20261108"
R = os.path.dirname(os.path.dirname(ROOT))
U5 = os.path.join(R, "experiments/universality_bio_grammar_20261103")
U5D = "/path/to/bio_data"
OWN = ["CONFIG.json", "PROTOCOL.md", "ADAPTER_CARD.md", "DATA_MANIFEST.md"] + \
    sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "tests", "*.py"))) + \
    sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "scripts", "*")) if p.endswith((".py", ".sh")))
U5_CODE = [os.path.join(U5, "scripts", f) for f in ("u5core.py", "u5policy.py", "u5run.py", "u5static.py", "u5induce.py",
                                                    "u5probe.py", "u5eval.py", "u5data.py", "u5tax.py", "seg_stardist.py")] + \
    [os.path.join(U5, "CODE_FREEZE.json"), os.path.join(U5, "PROTOCOL.md"),
     os.path.join(R, "experiments/universality_submitted_pkg_20261101/scripts/adapter.py"),
     os.path.join(R, "experiments/universality_submitted_pkg_20261101/scripts/masks.py"),
     os.path.join(R, "cora_cross_domain_transfer/adapters/bbbc039.py")]
U5_DATA = [os.path.join(U5D, "work/nuinsseg", f) for f in ("DATA_MANIFEST.json", "GATE.json", "seg/THRESHOLDS.json",
                                                           "seg/STRONG_NATIVE_RULE.json", "probes/induction/targets.json")] + \
    [os.path.join(U5D, "work/POLICY_FREEZE.json")] + \
    sorted(glob.glob(os.path.join(U5D, "models/stardist/2D_versatile_he/*")))
RECORDS = ["CALIBRATED.json", "STRICT.json", "TOLERANT.json", "MATCHED_SEARCH.json"]


def sha(p):
    d = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            d.update(b)
    return d.hexdigest()


def tree_sha(folder, pattern="*.json"):
    """One hash over a folder's files: sha256 of the sorted lines '<name> <sha256>'."""
    lines = [f"{os.path.basename(p)} {sha(p)}" for p in sorted(glob.glob(os.path.join(folder, pattern)))]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest(), len(lines)


def main():
    fz = {"study": "calibrated_acceptance_20261108", "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "files": {p: sha(os.path.join(ROOT, p)) for p in OWN}}
    fz["u5_reused"] = {p: sha(p) for p in U5_CODE + U5_DATA}
    runs, n = tree_sha(os.path.join(U5D, "work/nuinsseg/probes/induction/runs"))
    fz["u5_reused_trees"] = {os.path.join(U5D, "work/nuinsseg/probes/induction/runs"): {"sha256_of_listing": runs,
                                                                                         "files": n}}
    cf = json.load(open(os.path.join(U5, "CODE_FREEZE.json")))["files"]
    fz["u5_code_freeze_all_match"] = all(sha(os.path.join(U5, p)) == h for p, h in cf.items())
    raw = os.path.join(ROOT, "data/raw/puma_zenodo_13859989")
    fz["data"] = {"archives": {os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(raw, "*.zip")))},
                  "zenodo_record": sha(os.path.join(raw, "zenodo_record_13859989.json")),
                  "format_check": sha(os.path.join(ROOT, "data/work/format_check/FORMAT_CHECK.json")),
                  "model_copy": {os.path.basename(p): sha(p) for p in
                                 sorted(glob.glob(os.path.join(ROOT, "data/models/stardist/2D_versatile_he/*")))}}
    cal = os.path.join(ROOT, "data/work/cal/final")
    fz["calibration_records"] = {f: sha(os.path.join(cal, f)) for f in RECORDS}
    fz["development"] = {os.path.relpath(p, ROOT): sha(p) for p in
                         sorted(glob.glob(os.path.join(ROOT, "development", "**", "*.json"), recursive=True))}
    fz["held_rule"] = {"salt": "sha256 of the bytes of GO_CAL (written by the coordinator after review)",
                       "selection": "per stratum (primary, metastatic), sha256('<salt>:<roi>') order, first 50",
                       "format_roi_excluded": json.load(open(os.path.join(ROOT, "data/work/format_check/"
                                                                                "FORMAT_CHECK.json")))["format_roi"]}
    p = os.path.join(ROOT, "FREEZE.json")
    json.dump(fz, open(p + ".tmp", "w"), indent=1)
    os.replace(p + ".tmp", p)
    print(sha(p))


if __name__ == "__main__":
    main()
