#!/usr/bin/env python3
"""Check the byte copy of the frozen C4 build (`configs/h/c4_frozen/`) against the independent team's manifest and
against itself. Writes configs/results/h_c4_copy.json (pass or fail).

  python3 verify_c4_copy.py [--original DIR]      # DIR: their frozen folder (read only), compared byte for byte

Checks:
- notebook sha256 = manifest notebook_sha256 = b571233a...; MANIFEST.json sha256 = ff6b1c38...;
- deployment_guard.py = guard_sha256; every source file = source_files;
- cell 0's embedded files equal the source files, and their combined hash equals the embedded CODE_SHA;
- the guard text written by cell 0 equals deployment_guard.py;
- cell 1's driver string hashed both ways (body alone, and with its two header lines), against driver_sha256;
- if --original is given, every file equals the original.
"""
import argparse
import ast
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
COPY = os.path.join(HERE, "c4_frozen")
EXPECT_NOTEBOOK = "b571233a9afae5a6374cd569d448285e3f6006bddd3e5e9d013f5f8dcb2409bc"
EXPECT_MANIFEST = "ff6b1c3826b5befa61984a5e225ca4b7c95a780fb3964bd8115d977bf1d54e54"


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    with open(p, "rb") as f:
        return sha_bytes(f.read())


def cell_src(nb, i):
    s = nb["cells"][i]["source"]
    return s if isinstance(s, str) else "".join(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", default="")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "results", "h_c4_copy.json"))
    a = ap.parse_args()
    problems, info = [], {}
    man_p = os.path.join(COPY, "MANIFEST.json")
    nb_p = os.path.join(COPY, "notebook", "notebook.ipynb")
    man = json.load(open(man_p))
    info["manifest_sha256"] = sha_file(man_p)
    info["notebook_sha256"] = sha_file(nb_p)
    if info["manifest_sha256"] != EXPECT_MANIFEST:
        problems.append("MANIFEST.json hash differs from ff6b1c38")
    if info["notebook_sha256"] != EXPECT_NOTEBOOK or man["notebook_sha256"] != EXPECT_NOTEBOOK:
        problems.append("notebook hash differs from b571233a or from the manifest")
    if sha_file(os.path.join(COPY, "deployment_guard.py")) != man["guard_sha256"]:
        problems.append("deployment_guard.py differs from guard_sha256")
    src_root = os.path.join(COPY, "source", "kaggle", "score_first_2026")
    for rel, h in man["source_files"].items():
        if sha_file(os.path.join(src_root, rel)) != h:
            problems.append(f"source {rel} differs from the manifest")
    nb = json.load(open(nb_p))
    c0, c1 = cell_src(nb, 0), cell_src(nb, 1)
    m = re.search(r"^FILES = json\.loads\((.*)\)$", c0, re.M)
    files = json.loads(ast.literal_eval(m.group(1)))
    code_sha = re.search(r"^CODE_SHA = '([0-9a-f]{64})'$", c0, re.M).group(1)
    info["embedded_code_sha256"] = code_sha
    if sha_bytes(json.dumps(files, sort_keys=True).encode()) != code_sha:
        problems.append("embedded files do not hash to CODE_SHA")
    for rel, text in files.items():
        if text != open(os.path.join(src_root, rel), encoding="utf-8").read():
            problems.append(f"embedded {rel} differs from the source copy")
    info["embedded_files"] = sorted(files)
    g = re.search(r"^open\(os\.path\.join\(CODE_DIR, 'deployment_guard\.py'\), 'w'\)\.write\((.*)\)$", c0, re.M)
    guard_text = ast.literal_eval(g.group(1))
    if guard_text != open(os.path.join(COPY, "deployment_guard.py"), encoding="utf-8").read():
        problems.append("guard text in cell 0 differs from deployment_guard.py")
    d = re.search(r'^_driver\.write_text\("CODE_DIR=" \+ repr\(CODE_DIR\) \+ "\\nCODE_SHA=" \+ repr\(CODE_SHA\) \+ "\\n" \+ (.*)\)$',
                  c1, re.M)
    if d:
        body = ast.literal_eval(d.group(1))
        info["driver_body_sha256"] = sha_bytes(body.encode())
        info["driver_matches_manifest"] = info["driver_body_sha256"] == man["driver_sha256"]
    else:
        info["driver_matches_manifest"] = None
        problems.append("driver string not found in cell 1")
    info["neural_env_cell0"] = dict(re.findall(r"^os\.environ\['([A-Z_0-9]+)'\] = '([^']*)'$", c0, re.M))
    if any(info["neural_env_cell0"].get(k) != v for k, v in man["neural_env"].items()):
        problems.append("cell 0 environment differs from the manifest's neural_env")
    info["kernel_metadata"] = json.load(open(os.path.join(COPY, "notebook", "kernel-metadata.json")))
    if a.original:
        for root, _, fs in os.walk(COPY):
            for f in fs:
                p = os.path.join(root, f)
                rel = os.path.relpath(p, COPY)
                q = os.path.join(a.original, rel)
                if not os.path.exists(q) or sha_file(p) != sha_file(q):
                    problems.append(f"{rel} differs from the original")
        info["original"] = a.original
    info["files_sha256"] = {os.path.relpath(os.path.join(r, f), COPY): sha_file(os.path.join(r, f))
                            for r, _, fs in os.walk(COPY) for f in sorted(fs)}
    res = {"pass": not problems, "problems": problems, **info}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in ("pass", "problems", "notebook_sha256", "embedded_code_sha256",
                                         "driver_matches_manifest")}, indent=1))


if __name__ == "__main__":
    main()
