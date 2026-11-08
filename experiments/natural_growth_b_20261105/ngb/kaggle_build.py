"""Build the private Kaggle kernels of phase 2 (after the GO), or check the package (no GO needed).

    python3 -I ngb/kaggle_build.py check                      build the archive in memory, verify, extract, smoke-test
    python3 -I ngb/kaggle_build.py benchmarks                 kernels A (ConceptARC, Mini-ARC) and B (1D-ARC)
    python3 -I ngb/kaggle_build.py arc2 A_OUTPUT B_OUTPUT     kernel C (ARC-AGI-2 check), after A and B finished
    python3 -I ngb/kaggle_build.py rehearsal_data             the rehearsal's source-only inputs (before the freeze)
    python3 -I ngb/kaggle_build.py rehearsal                  rehearsal kernels RA and RB (amendment 3)
    python3 -I ngb/kaggle_build.py rehearsal_arc2 RA_OUT RB_OUT   rehearsal kernel RC

Rehearsal (amendment 3): the same code and archive layout, with the benchmark data replaced by source-half tasks
only (`rehearsal/data/`, made here from the prepared files; no held task, no test output), the ARC-AGI-2 set by a
stand-in file of source tasks (`rehearsal/arc2_standin_challenges.json`, demonstrations and test inputs only),
the GO by `rehearsal/REHEARSAL_GO`, and NGB_REHEARSAL=1 in the kernel, which makes every caller see the source half
in place of the held half. Kernel C (real or rehearsal) is built only from A and B outputs whose OUTPUT_MANIFEST.json
(every digest, no unlisted file) and STAGES.json (this GO, this primary, status complete) verify.

The package list is derived from FREEZE.json: every frozen file that is not Athe-only (code, protocol and
amendments, configuration, the split, the frozen libraries and their records), every object-growth file listed in
the slot, FREEZE.json itself (the kernel's gate loads it; the GO binds its digest), and the benchmark files
(demonstrations and test inputs only; never a test output). `check` verifies that every file the kernel's gate will
require is present with its frozen digest, extracts the archive into a scratch folder and runs the package-mode
smoke test there (import closure, freeze check, refusal without a GO, sorted-tag grammar, library binding, module
provenance, no solution file); it writes checks/PACKAGE_CHECK.json and no kernel. A kernel is built only when the
check passes. The archive is a deterministic .tar.gz embedded in the notebook with its sha256; the notebook checks
the digest, unpacks, runs `python -I run.py phase2 RUN_DIR BENCHES WORKERS` with NG_PACKAGE=1, and packs RUN_DIR
into /kaggle/working/<KERNEL>_outputs.tar.gz. Kernels are private, CPU only, internet off.

WORKERS (amendment 3, the rehearsal's finding): as many processes as the kernel's static children run at once, two in
kernels A and B (two static shards) and one in kernel C (one child at a time), so that the speed factor, measured as
WORKERS benchmark copies at once, and every CPU figure that enters a static allowance are measured at the concurrency
at which the static children spend their allowance.
"""
import base64
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(STUDY))
STUDY_REL = os.path.relpath(STUDY, REPO)
STUDY_A_REL = "experiments/natural_growth_20261105"
OBJ_REL = "experiments/object_growth_20261105"
DATA = "/path/to/benchmark_data/prepared"
BENCH_DATA = [(f"data/prepared/{b}/{f}", os.path.join(DATA, b, f)) for b in ("concept_arc", "mini_arc", "1d_arc")
              for f in ("real.json", "meta.json")]
ARC2_DATA = [("outputs/score_first/data/arc-agi_evaluation_challenges.json",
              os.path.join(REPO, "outputs/score_first/data/arc-agi_evaluation_challenges.json"))]
OWNER = "chimdiwalter"
KERNELS = {"A": "concept_arc,mini_arc", "B": "1d_arc", "C": "arc2",
           "RA": "concept_arc,mini_arc", "RB": "1d_arc", "RC": "arc2"}
WORKERS = {"A": 2, "B": 2, "C": 1, "RA": 2, "RB": 2, "RC": 1}
REH = os.path.join(STUDY, "rehearsal")
STANDIN_PER_BENCH = 4
PY = sys.executable


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def required_files(fr):
    """Repository paths the kernel's gate will check (frozen, not Athe-only) plus the object-growth files."""
    athe = set(fr.get("athe_only", []))
    req = {p: h for p, h in fr["files_sha256"].items() if p not in athe}
    req.update((fr.get("object_growth") or {}).get("files_sha256") or {})
    return req


def archive(entries):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tf:
            for rel, src in sorted(entries):
                data = open(src, "rb").read()
                ti = tarfile.TarInfo(rel)
                ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = len(data), 0, 0o644, 0, 0, "", ""
                tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def cell(kind, src, n):
    c = {"cell_type": kind, "id": f"cell-{n}", "metadata": {}, "source": src}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


def kernel_env_lines(rehearsal=False):
    return ("env = dict(os.environ, NG_PACKAGE='1', NG_REPO=ROOT, NG_STUDY=STUDY_A,\n"
            "           NGB_REPO=ROOT, NGB_STUDY=STUDY, NG_DATA=os.path.join(ROOT, 'data', 'prepared'),\n"
            f"           OG_REPO=ROOT, OG_STUDY=os.path.join(ROOT, '{OBJ_REL}')" +
            (", NGB_REHEARSAL='1'" if rehearsal else "") + ")\n")


def notebook(kernel, benches, b64, digest):
    rehearsal = kernel.startswith("R")
    head = (f"# CORA library-transfer and object-growth test: {'rehearsal ' if rehearsal else ''}kernel {kernel}\n\n"
            "Private research run of a pre-registered study (protocol `PROTOCOL.md` and its amendments inside the "
            "package). CPU only, internet off. The package holds demonstrations and test inputs only; scoring "
            "happens elsewhere.")
    unpack = ("import base64, hashlib, io, os, subprocess, sys, tarfile\n"
              f"ARCHIVE_SHA256 = '{digest}'\n"
              f"ARCHIVE = base64.b64decode('{b64}')\n"
              "assert hashlib.sha256(ARCHIVE).hexdigest() == ARCHIVE_SHA256, 'package digest mismatch'\n"
              "ROOT = '/kaggle/working/pkg'\n"
              "with tarfile.open(fileobj=io.BytesIO(ARCHIVE), mode='r:gz') as tf:\n"
              "    tf.extractall(ROOT)\n"
              "print('package', ARCHIVE_SHA256, 'cpus', os.cpu_count())\n")
    run = (f"BENCHES = '{benches}'\n"
           f"STUDY = os.path.join(ROOT, '{STUDY_REL}')\n"
           f"STUDY_A = os.path.join(ROOT, '{STUDY_A_REL}')\n"
           f"RUN_DIR = os.path.join(STUDY, 'runs', 'phase2', '{kernel}')\n"
           + kernel_env_lines(rehearsal) +
           f"p = subprocess.run([sys.executable, '-I', os.path.join(STUDY, 'run.py'), 'phase2', RUN_DIR, BENCHES, "
           f"'{WORKERS[kernel]}'],\n"
           "                   cwd=STUDY, env=env)\n"
           "print('return code', p.returncode)\n")
    pack = (f"out = '/kaggle/working/{kernel}_outputs.tar.gz'\n"
            "with tarfile.open(out, 'w:gz') as tf:\n"
            f"    tf.add(RUN_DIR, arcname='{kernel}')\n"
            "print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())\n"
            "print(open(os.path.join(RUN_DIR, 'STAGES.json')).read())\n")
    return {"cells": [cell("markdown", head, 1), cell("code", unpack, 2), cell("code", run, 3), cell("code", pack, 4)],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def run_manifest(run_dir):
    """The digest map phase 2 writes (ngb/phase2.py manifest): every file except logs, temporaries and itself."""
    out = {}
    for d, _, files in os.walk(run_dir):
        for f in sorted(files):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, run_dir)
            if rel.endswith(".tmp") or rel == "OUTPUT_MANIFEST.json" or rel.endswith(".log"):
                continue
            out[rel] = sha_bytes(open(p, "rb").read())
    return out


def verify_kernel_output(kdir, go_path):
    """A or B output folder: every manifest digest, no unlisted file, STAGES.json of this GO and primary, complete."""
    man_p, st_p = os.path.join(kdir, "OUTPUT_MANIFEST.json"), os.path.join(kdir, "STAGES.json")
    if not os.path.exists(man_p) or not os.path.exists(st_p):
        raise SystemExit(f"{kdir}: OUTPUT_MANIFEST.json or STAGES.json missing")
    man = json.load(open(man_p, encoding="utf-8"))
    have = run_manifest(kdir)
    bad = [r for r, h in man.items() if have.get(r) != h]
    extra = [r for r in have if r not in man]
    if bad or extra:
        raise SystemExit(f"{kdir}: manifest mismatch (changed or missing {bad[:5]}; unlisted {extra[:5]})")
    st = json.load(open(st_p, encoding="utf-8"))
    lines = open(go_path, encoding="utf-8").read().splitlines()
    go_sha, primary = sha_bytes(open(go_path, "rb").read()), lines[2].split(" ", 1)[1]
    if st.get("go_sha256") != go_sha or st.get("primary") != primary or st.get("status") != "complete":
        raise SystemExit(f"{kdir}: STAGES.json is not complete under this GO and primary "
                         f"({st.get('status')}, {st.get('go_sha256')}, {st.get('primary')})")
    return sha_bytes(open(man_p, "rb").read())


def make_rehearsal_data():
    """Source-half inputs only (no held task, no test output) and a stand-in evaluation file of source tasks."""
    split = json.load(open(os.path.join(REPO, STUDY_A_REL, "split", "SPLIT.json"), encoding="utf-8"))
    digests, standin = {}, {}
    for b in ("concept_arc", "mini_arc", "1d_arc"):
        src = sorted(t for f in split["benchmarks"][b]["families"].values() for t in f["source"])
        held = {t for f in split["benchmarks"][b]["families"].values() for t in f["held"]}
        real = json.load(open(os.path.join(DATA, b, "real.json"), encoding="utf-8"))
        meta = json.load(open(os.path.join(DATA, b, "meta.json"), encoding="utf-8"))
        r_real, r_meta = {t: real[t] for t in src}, {t: meta[t] for t in src}
        assert not set(r_real) & held and all("output" not in q for v in r_real.values() for q in v["test"])
        os.makedirs(os.path.join(REH, "data", b), exist_ok=True)
        for name, obj in (("real.json", r_real), ("meta.json", r_meta)):
            path = os.path.join(REH, "data", b, name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(obj, f, sort_keys=True)
            digests[f"{b}/{name}"] = sha_bytes(open(path, "rb").read())
        for t in src[:STANDIN_PER_BENCH]:
            standin[t] = r_real[t]
    st_path = os.path.join(REH, "arc2_standin_challenges.json")
    with open(st_path, "w", encoding="utf-8") as f:
        json.dump(standin, f, sort_keys=True)
    rd = {"data_sha256": digests, "arc2_standin_sha256": sha_bytes(open(st_path, "rb").read()),
          "standin_tasks": sorted(standin), "note": "source-half inputs only; no held task; no test output"}
    with open(os.path.join(REH, "REHEARSAL_DATA.json"), "w", encoding="utf-8") as f:
        json.dump(rd, f, indent=1, sort_keys=True)
    return rd


def check_rehearsal_data():
    """The rehearsal data made before the freeze (mode rehearsal_data) must still have their recorded digests."""
    rd = json.load(open(os.path.join(REH, "REHEARSAL_DATA.json"), encoding="utf-8"))
    for rel, h in rd["data_sha256"].items():
        if sha_bytes(open(os.path.join(REH, "data", rel), "rb").read()) != h:
            raise SystemExit(f"rehearsal data changed: {rel}")
    if sha_bytes(open(os.path.join(REH, "arc2_standin_challenges.json"), "rb").read()) != rd["arc2_standin_sha256"]:
        raise SystemExit("rehearsal stand-in changed")
    return rd


def entries_for(mode, fr, extra=()):
    req = required_files(fr)
    rehearsal = mode.startswith("rehearsal")
    entries = [(p, os.path.join(REPO, p)) for p in req]
    entries.append((f"{STUDY_REL}/FREEZE.json", os.path.join(STUDY, "FREEZE.json")))
    if rehearsal:
        entries += [(f"data/prepared/{b}/{f}", os.path.join(REH, "data", b, f))
                    for b in ("concept_arc", "mini_arc", "1d_arc") for f in ("real.json", "meta.json")]
        entries += [(f"{STUDY_REL}/rehearsal/{f}", os.path.join(REH, f))
                    for f in ("REHEARSAL_DATA.json", "arc2_standin_challenges.json", "REHEARSAL_GO")]
    else:
        entries += list(BENCH_DATA)
        if mode != "check":
            entries.append((f"{STUDY_REL}/runs/GO", os.path.join(STUDY, "runs", "GO")))
    if mode in ("arc2", "rehearsal_arc2"):
        if mode == "arc2":
            entries += ARC2_DATA
        kc = "RC" if rehearsal else "C"
        for kdir in extra:                     # outputs of kernels A and B: their held/ trees, after verification
            for d, _, files in os.walk(kdir):
                for f in files:
                    src = os.path.join(d, f)
                    rel = os.path.relpath(src, kdir)
                    if rel.split(os.sep)[0] == "held" and not f.endswith(".pkl"):
                        entries.append((f"{STUDY_REL}/runs/phase2/{kc}/{rel}", src))
    return entries, req


def smoke(data):
    """Extract the archive into a scratch folder and run the package-mode smoke test there."""
    with tempfile.TemporaryDirectory(prefix="ngb_pkg_") as tmp:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            tf.extractall(tmp)
        study = os.path.join(tmp, STUDY_REL)
        out = os.path.join(tmp, "smoke.json")
        env = dict(os.environ, NG_PACKAGE="1", NG_REPO=tmp, NG_STUDY=os.path.join(tmp, STUDY_A_REL), NGB_REPO=tmp,
                   NGB_STUDY=study, NG_DATA=os.path.join(tmp, "data", "prepared"), OG_REPO=tmp,
                   OG_STUDY=os.path.join(tmp, OBJ_REL))
        p = subprocess.run([PY, "-I", os.path.join(study, "run.py"), "package_smoke", out], cwd=study, env=env,
                           capture_output=True, text=True, timeout=900)
        res = json.load(open(out)) if os.path.exists(out) else {"ok": False, "problems": ["smoke test wrote nothing"]}
        res["returncode"] = p.returncode
        if p.returncode != 0:
            res["ok"] = False
            res.setdefault("problems", []).append("smoke test failed: " + p.stderr[-400:])
        return res


def check(fr):
    """Every required file present with its frozen digest; the archive's members cover the requirement; the
    extracted package passes the smoke test."""
    entries, req = entries_for("check", fr)
    problems = []
    for p, h in req.items():
        src = os.path.join(REPO, p)
        if not os.path.exists(src):
            problems.append(f"missing {p}")
        elif sha_bytes(open(src, "rb").read()) != h:
            problems.append(f"digest differs {p}")
    data = archive([(r, s) for r, s in entries if os.path.exists(s)])
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        members = {m.name for m in tf.getmembers()}
    for p in list(req) + [f"{STUDY_REL}/FREEZE.json"] + [rel for rel, _ in BENCH_DATA]:
        if p not in members:
            problems.append(f"not in archive {p}")
    sm = smoke(data) if not problems else {"ok": False, "problems": ["not run: membership problems"]}
    problems += [f"smoke: {x}" for x in sm.get("problems", [])]
    out = {"required_files": len(req), "archive_members": len(members), "archive_bytes": len(data),
           "archive_sha256_without_GO": sha_bytes(data), "problems": problems, "ok": not problems,
           "smoke": {k: v for k, v in sm.items() if k != "module_provenance"},
           "modules_loaded_in_package": len(sm.get("module_provenance", {})),
           "freeze_sha256": sha_bytes(open(os.path.join(STUDY, "FREEZE.json"), "rb").read())}
    os.makedirs(os.path.join(STUDY, "checks"), exist_ok=True)
    with open(os.path.join(STUDY, "checks", "PACKAGE_CHECK.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True, default=str)
    print(json.dumps({k: v for k, v in out.items() if k != "smoke"}, indent=1))
    return out


def build(mode, extra=()):
    if mode == "rehearsal_data":                # before the freeze: the rehearsal's source-only inputs
        rd = make_rehearsal_data()
        print(json.dumps({k: v for k, v in rd.items() if k != "data_sha256"}))
        return rd
    fr = json.load(open(os.path.join(STUDY, "FREEZE.json"), encoding="utf-8"))
    if mode == "check":
        return check(fr)
    rehearsal = mode.startswith("rehearsal")
    go_path = os.path.join(REH, "REHEARSAL_GO") if rehearsal else os.path.join(STUDY, "runs", "GO")
    if not os.path.exists(go_path):
        raise SystemExit(f"no {os.path.relpath(go_path, STUDY)}: no package is built")
    if not check(fr)["ok"]:
        raise SystemExit("package check failed: no package is built")
    if mode.startswith("rehearsal"):
        check_rehearsal_data()
    verified = {}
    if mode in ("arc2", "rehearsal_arc2"):
        for k, kdir in zip(("A", "B"), extra):
            verified[k] = {"dir": kdir, "output_manifest_sha256": verify_kernel_output(kdir, go_path)}
    entries, _ = entries_for(mode, fr, extra)
    kernels = {"benchmarks": ["A", "B"], "arc2": ["C"], "rehearsal": ["RA", "RB"], "rehearsal_arc2": ["RC"]}[mode]
    data = archive(entries)
    digest = sha_bytes(data)
    b64 = base64.b64encode(data).decode()
    man = {"archive_sha256": digest, "archive_bytes": len(data), "verified_kernel_outputs": verified,
           "files_sha256": {rel: sha_bytes(open(src, "rb").read()) for rel, src in sorted(entries)}, "kernels": {}}
    for k in kernels:
        d = os.path.join(STUDY, "runs", "kaggle", k)
        os.makedirs(d, exist_ok=True)
        nb = json.dumps(notebook(k, KERNELS[k], b64, digest), indent=1)
        with open(os.path.join(d, "notebook.ipynb"), "w", encoding="utf-8") as f:
            f.write(nb)
        slug = f"rehearsal-{k[1:].lower()}" if k.startswith("R") else k.lower()
        meta = {"id": f"{OWNER}/cora-library-transfer-{slug}",
                "title": f"CORA Library Transfer {'Rehearsal ' + k[1:] if k.startswith('R') else k}",
                "code_file": "notebook.ipynb", "language": "python", "kernel_type": "notebook", "is_private": True,
                "enable_gpu": False, "enable_tpu": False, "enable_internet": False, "dataset_sources": [],
                "competition_sources": [], "kernel_sources": [], "model_sources": []}
        with open(os.path.join(d, "kernel-metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
        man["kernels"][k] = {"id": meta["id"], "benches": KERNELS[k], "workers": WORKERS[k],
                             "notebook_sha256": sha_bytes(nb.encode())}
    with open(os.path.join(STUDY, "runs", "kaggle", f"PACKAGE_MANIFEST_{mode}.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps({"archive_sha256": digest, "bytes": len(data), "kernels": man["kernels"]}))


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2:])
