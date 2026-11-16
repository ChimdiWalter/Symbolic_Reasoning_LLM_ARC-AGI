"""Stage A runner: deterministic, resumable, CPU only. Author: Chimdi Walter Ndubuisi

    env PYTHONHASHSEED=0 python -s -B run_stage_a.py <outdir> --roster dev [--targets a,b] [--B seconds]
    env PYTHONHASHSEED=0 python -s -B run_stage_a.py <outdir> --roster all --freeze <FREEZE.json>
    env PYTHONHASHSEED=0 python -s -B run_stage_a.py --make-freeze <path>        (writes a hash manifest; runs nothing)

--roster dev needs no freeze and every output is labelled development only. --roster all REFUSES unless a freeze
file is given, every hash in it matches the files and covers every stage A file, and no earlier receipt of an
all-roster run exists in the experiment folder for a different output folder; it writes an exclusive receipt before
the first target. Finished targets (targets/<name>.json) are skipped on a resume.
"""
import argparse
import glob
import hashlib
import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frozen                    # noqa: E402  (hash check of the frozen modules happens here)
import presets_vf1 as V          # noqa: E402

OWN_FILES = ("presets_vf1.py", "frozen.py", "vsearch.py", "consumers.py", "gate.py", "library.py", "episode.py",
             "summarize.py", "run_stage_a.py")
ROOT = frozen.ROOT


def exp_dir():
    return os.environ.get("VF1_EXPERIMENT_DIR") or HERE          # the variable is a test hook for the receipt folder


def override():
    return os.environ.get("VF1_EXPERIMENT_DIR") or None


def inside(folder, path):
    folder, path = os.path.realpath(folder), os.path.realpath(path)
    return path == folder or path.startswith(folder + os.sep)


def extra_files(require_protocol=False):
    """Documents and tests covered by a freeze: PROTOCOL.md, README.md and every tests/*.py."""
    names = ["PROTOCOL.md", "README.md"]
    tdir = os.path.join(HERE, "tests")
    names += ["tests/" + f for f in sorted(os.listdir(tdir)) if f.endswith(".py")] if os.path.isdir(tdir) else []
    out = []
    for n in names:
        p = os.path.join(HERE, n)
        if os.path.exists(p):
            out.append(p)
        elif n == "PROTOCOL.md" and require_protocol:
            raise SystemExit("refusing: PROTOCOL.md does not exist (a freeze covers it)")
    return out


def file_hashes(require_protocol=False):
    """{path relative to the repository root: sha256}: stage A files, documents, tests, the frozen modules and the
    study inputs."""
    out = {}
    for n in OWN_FILES:
        p = os.path.join(HERE, n)
        out[os.path.relpath(p, ROOT)] = frozen.sha256_file(p)
    for p in extra_files(require_protocol):
        out[os.path.relpath(p, ROOT)] = frozen.sha256_file(p)
    for n in frozen.REQUIRED + frozen.ALSO:
        p = os.path.join(frozen.CORE_DIR, n)
        out[os.path.relpath(p, ROOT)] = frozen.sha256_file(p)
    with open(os.path.join(frozen.CORE_DIR, "FREEZE.json")) as f:
        for rel in json.load(f)["inputs_sha256"]:
            out[rel] = frozen.sha256_file(os.path.join(ROOT, rel))
    return out


def make_freeze(path):
    body = dict(author="Chimdi Walter Ndubuisi", what="hash manifest of stage A (VF1)", files=file_hashes(True),
                python=platform.python_version(), env="PYTHONHASHSEED=0, python3 -s -B")
    with open(path, "x") as f:
        json.dump(body, f, indent=1, sort_keys=True)
        f.write("\n")


def check_freeze(path, base=None):
    """Return the sha256 of the freeze file, or raise SystemExit when a hash differs or a stage A file, PROTOCOL.md,
    README.md or a test file is not covered."""
    base = base or ROOT
    with open(path, "rb") as f:
        raw = f.read()
    try:
        files = json.loads(raw)["files"]
    except Exception as e:                                        # noqa: BLE001
        raise SystemExit("refusing: freeze file unreadable (%s)" % type(e).__name__)
    need = {os.path.relpath(os.path.join(HERE, n), base) for n in OWN_FILES}
    need |= {os.path.relpath(p, base) for p in extra_files(True)}
    need |= {os.path.relpath(os.path.join(frozen.CORE_DIR, n), base) for n in frozen.REQUIRED + frozen.ALSO}
    missing = sorted(need - set(files))
    if missing:
        raise SystemExit("refusing: freeze does not cover %s" % missing)
    for rel, want in sorted(files.items()):
        p = os.path.join(base, rel)
        if not os.path.exists(p) or frozen.sha256_file(p) != want:
            raise SystemExit("refusing: %s differs from the freeze" % rel)
    return hashlib.sha256(raw).hexdigest()


def ensure_receipt(folder, outdir, freeze_sha, override_dir=None):
    """Exclusive receipt of an all-roster run. Same output folder: a resume. Another folder: refused. The receipts of
    the real experiment folder are always consulted, even when the receipt folder is overridden."""
    out = os.path.realpath(outdir)
    folders = [folder] if os.path.realpath(folder) == os.path.realpath(HERE) else [HERE, folder]
    for fo in folders:
        for p in sorted(glob.glob(os.path.join(fo, "RECEIPT_ALL_ROSTER*.json"))):
            with open(p) as f:
                r = json.load(f)
            if os.path.realpath(r.get("outdir", "")) != out:
                raise SystemExit("refusing: an all-roster run already has a receipt (%s) for another output folder" % p)
    for p in sorted(glob.glob(os.path.join(folder, "RECEIPT_ALL_ROSTER*.json"))):
        return p
    p = os.path.join(folder, "RECEIPT_ALL_ROSTER.json")
    try:
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError:
        raise SystemExit("refusing: receipt exists")
    with os.fdopen(fd, "w") as f:
        json.dump(dict(outdir=out, freeze_sha256=freeze_sha, pid=os.getpid(), experiment_dir_override=override_dir,
                       time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())), f, indent=1)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--roster", choices=("dev", "all"))
    ap.add_argument("--targets")
    ap.add_argument("--freeze")
    ap.add_argument("--B", type=float, help="development only: CPU allowance override")
    ap.add_argument("--make-freeze")
    a = ap.parse_args(argv)
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("run with PYTHONHASHSEED=0")
    if a.make_freeze:
        make_freeze(a.make_freeze)
        return 0
    if not a.outdir or not a.roster:
        sys.exit("need <outdir> and --roster dev|all")
    freeze_sha = None
    ov = override()
    if ov and not inside(ov, a.outdir):
        raise SystemExit("refusing: VF1_EXPERIMENT_DIR is set and the output folder is outside it")
    if a.roster == "all":
        if not a.freeze:
            raise SystemExit("refusing: --roster all needs --freeze <FREEZE.json>")
        if a.B is not None or a.targets:
            raise SystemExit("refusing: --B and --targets are for the development roster only")
        freeze_sha = check_freeze(a.freeze)
        ensure_receipt(exp_dir(), a.outdir, freeze_sha, ov)
    import consumers as C
    import episode
    import summarize
    roster = list(V.DEV_ROSTER) if a.roster == "dev" else C.roster_all()
    targets = roster
    if a.targets:
        targets = a.targets.split(",")
        bad = [t for t in targets if t not in roster]
        if bad:
            raise SystemExit("refusing: targets outside the %s roster: %s" % (a.roster, bad))
    B = V.B if a.B is None else a.B
    os.makedirs(a.outdir, exist_ok=True)
    mp = os.path.join(a.outdir, "MANIFEST.json")
    if not os.path.exists(mp):
        with open(mp, "w") as f:
            json.dump(dict(roster=a.roster, targets=targets, B=B, development_only=a.roster == "dev", freeze_sha256=freeze_sha,
                           experiment_dir_override=ov, hashes=file_hashes(), python=platform.python_version(), pythonhashseed=os.environ["PYTHONHASHSEED"]), f, indent=1, sort_keys=True)
    for i, X in enumerate(targets):
        t = time.process_time()
        r = episode.run_target(X, a.outdir, B)
        print("[%d/%d] %s %s %s cpu=%.1f" % (i + 1, len(targets), X, r.get("status"), (r.get("reason") or "")[:60], time.process_time() - t), flush=True)
    s = summarize.write_summary(a.outdir)
    print("summary: done=%d excluded=%d incomplete=%d total_cpu_s=%s" % (s["n_done"], s["n_excluded_by_gate"], s["n_incomplete_infrastructure"], s["total_cpu_s"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
