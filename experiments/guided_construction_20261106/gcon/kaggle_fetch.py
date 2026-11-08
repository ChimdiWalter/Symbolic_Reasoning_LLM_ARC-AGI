"""After the GO only: push the final kernels once, poll them, fetch their outputs (Athe side; standard library plus
the Kaggle command-line tool; never prints a credential).

    python3 -I gcon/kaggle_fetch.py push KERNEL       kaggle kernels push -p runs/kaggle/<KERNEL> (final folders only)
    python3 -I gcon/kaggle_fetch.py status KERNEL     its status (retries transient permission errors)
    python3 -I gcon/kaggle_fetch.py fetch KERNEL      outputs into a new empty folder runs/kaggle_out/<KERNEL>/<UTC>/,
                                                      the archive's sha256, a checked extraction (only run/..., no
                                                      absolute path, no '..', regular files), the kernel's sets
                                                      copied to runs/held_run/<SET>/ and its other files (logs,
                                                      kernel_run.json) to runs/held_run/<KERNEL>_meta/
Refused unless runs/GO exists and the final manifest names KERNEL. A push is refused when the kernel's folder holds a
push record already (runs/kaggle/<KERNEL>/PUSHED.json): the kernels are pushed once. The fetch record
(runs/held_run/<KERNEL>_meta/KAGGLE_FETCH.json) names the kernel, its sets, the archive (path and sha256) and the
sha256 of every file the archive returned; verify.py binds the rows to it.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAGGLE = os.path.expanduser("kaggle")
KDIR = os.path.join(STUDY, "runs", "kaggle")


def manifest():
    if not os.path.exists(os.path.join(STUDY, "runs", "GO")):
        raise SystemExit("no runs/GO: nothing is pushed or fetched")
    return json.load(open(os.path.join(KDIR, "PACKAGE_MANIFEST_final.json"), encoding="utf-8"))


def kernel_id(kernel):
    m = manifest()
    if kernel not in m["kernels"]:
        raise SystemExit(f"unknown kernel {kernel}")
    return m["kernels"][kernel]["id"]


def run(args, tries=6):
    for k in range(tries):
        p = subprocess.run([KAGGLE] + args, capture_output=True, text=True)
        out = (p.stdout + p.stderr).strip()
        if p.returncode == 0 or "Permission" not in out:
            return p.returncode, out
        time.sleep(30 * (k + 1))
    return p.returncode, out


def push(kernel):
    kid = kernel_id(kernel)
    d = os.path.join(KDIR, kernel)
    meta = json.load(open(os.path.join(d, "kernel-metadata.json"), encoding="utf-8"))
    if meta.get("enable_internet") is not False or meta.get("is_private") is not True or meta.get("enable_gpu"):
        raise SystemExit("kernel metadata must be private, CPU only, internet off")
    rec = os.path.join(d, "PUSHED.json")
    if os.path.exists(rec):
        raise SystemExit(f"{kernel} was pushed already ({rec})")
    nb = hashlib.sha256(open(os.path.join(d, "notebook.ipynb"), "rb").read()).hexdigest()
    if nb != manifest()["kernels"][kernel]["notebook_sha256"]:
        raise SystemExit("the notebook differs from the final manifest")
    code, out = run(["kernels", "push", "-p", d])
    json.dump({"kernel": kid, "notebook_sha256": nb, "return_code": code, "output": out[-2000:],
               "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(rec, "w"), indent=1)
    print(json.dumps({"kernel": kid, "return_code": code, "output": out[-500:]}))


def status(kernel):
    code, out = run(["kernels", "status", kernel_id(kernel)])
    print(json.dumps({"kernel": kernel, "return_code": code, "status": out[-500:]}))


def fetch(kernel):
    kid = kernel_id(kernel)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    d = os.path.join(STUDY, "runs", "kaggle_out", kernel, stamp)
    os.makedirs(d)
    code, out = run(["kernels", "output", kid, "-p", d])
    if code != 0:
        raise SystemExit(out[-1000:])
    arc = os.path.join(d, f"{kernel}_outputs.tar.gz")
    digest = hashlib.sha256(open(arc, "rb").read()).hexdigest()
    sets = manifest()["kernels"][kernel]["sets"]
    base = os.path.join(STUDY, "runs", "held_run")
    for s in sets + [kernel + "_meta"]:
        if os.path.exists(os.path.join(base, s)):
            raise SystemExit(f"runs/held_run/{s} exists: fetched already")
    tmp = os.path.join(d, "unpacked")
    with tarfile.open(arc, "r:gz") as tf:
        members = tf.getmembers()
        for m in members:
            n = m.name
            if n.startswith("/") or ".." in n.split("/") or not (n == "run" or n.startswith("run/")) or \
                    not (m.isfile() or m.isdir()):
                raise SystemExit(f"unexpected archive member: {n}")
        tf.extractall(tmp, members=members)
    src = os.path.join(tmp, "run")
    os.makedirs(base, exist_ok=True)
    for s in sets:
        if os.path.isdir(os.path.join(src, s)):
            shutil.copytree(os.path.join(src, s), os.path.join(base, s))
    meta = os.path.join(base, kernel + "_meta")
    os.makedirs(meta)
    for fn in sorted(os.listdir(src)):
        if os.path.isfile(os.path.join(src, fn)):
            shutil.copy(os.path.join(src, fn), os.path.join(meta, fn))
    files = {}
    for r_, _, fs in os.walk(src):
        for f_ in fs:
            q = os.path.join(r_, f_)
            files[os.path.relpath(q, src)] = hashlib.sha256(open(q, "rb").read()).hexdigest()
    rec = {"kernel": kid, "archive_sha256": digest, "archive": os.path.relpath(arc, STUDY), "fetched_utc": stamp,
           "sets": sets, "files_sha256": dict(sorted(files.items()))}
    json.dump(rec, open(os.path.join(meta, "KAGGLE_FETCH.json"), "w"), indent=1)
    print(json.dumps({k: rec[k] for k in ("kernel", "archive_sha256", "sets")}))


if __name__ == "__main__":
    {"push": push, "status": status, "fetch": fetch}[sys.argv[1]](sys.argv[2])
