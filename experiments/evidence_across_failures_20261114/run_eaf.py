"""EAF1 runner: deterministic, CPU only. Author: Chimdi Walter Ndubuisi

    env PYTHONHASHSEED=0 python -s -B run_eaf.py <outdir> --roster dev [--targets a,b] [--B seconds] [--setup-record J]
    env PYTHONHASHSEED=0 python -s -B run_eaf.py --setup-only <out.json> --roster dev|all
    env PYTHONHASHSEED=0 python -s -B run_eaf.py --make-freeze <path> --setup-record <J>      (writes a hash manifest; runs nothing)
    env PYTHONHASHSEED=0 python -s -B run_eaf.py <outdir> --roster all --freeze <FREEZE.json> --setup-record <J>

--roster dev needs no freeze and every output is labelled development only. --roster all REFUSES unless a freeze and the
committed setup record are given, every hash in the freeze matches (this experiment's files, PROTOCOL.md, README.md, every
tests/*.py, the setup record, and, through stage A's freeze, the stage A and operations-study files), the output folder is
new or empty, and no receipt of an all-roster run exists; it writes an exclusive receipt before the first target. THE
ALL-ROSTER RUN IS LAUNCHED ONCE: a receipt that exists refuses every later launch, whatever its output folder, so an
interrupted run is not resumed, reset or replayed. There is no environment variable or flag that moves the receipt folder.
A development run (--roster dev) skips finished targets (targets/<name>.json) when it is started again.
--setup-only runs ONLY the setup step (no search; the final role is never opened). --make-freeze refuses a setup record that
was made by other code than the files being frozen.
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
import eaf_frozen                # noqa: E402  (hash check of the imported frozen modules happens here)
import presets_eaf as P          # noqa: E402

OWN_FILES = ("eaf_frozen.py", "presets_eaf.py", "episode_eaf.py", "summarize_eaf.py", "run_eaf.py")
ROOT = eaf_frozen.ROOT
LABEL = P.LABEL


def sha256_file(p):
    return eaf_frozen.sha256_file(p)


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


def rel(p, base=None):
    return os.path.relpath(p, base or ROOT)


def file_hashes(require_protocol=False):
    """{path relative to the repository root: sha256}: this experiment's files, documents, tests and stage A's freeze file."""
    out = {}
    for n in OWN_FILES:
        out[rel(os.path.join(HERE, n))] = sha256_file(os.path.join(HERE, n))
    for p in extra_files(require_protocol):
        out[rel(p)] = sha256_file(p)
    out[rel(eaf_frozen.STAGE_A_FREEZE)] = sha256_file(eaf_frozen.STAGE_A_FREEZE)
    return out


def code_hashes():
    """{path: sha256} of the files that decide a setup record: this experiment's modules and stage A's freeze file."""
    out = {rel(os.path.join(HERE, n)): sha256_file(os.path.join(HERE, n)) for n in OWN_FILES}
    out[rel(eaf_frozen.STAGE_A_FREEZE)] = sha256_file(eaf_frozen.STAGE_A_FREEZE)
    return out


def make_freeze(path, setup_record):
    if os.path.lexists(path):
        raise SystemExit("refusing: %s exists (a freeze is written once)" % path)
    if not setup_record or not os.path.exists(setup_record):
        raise SystemExit("refusing: the setup record does not exist (a freeze covers it)")
    try:
        with open(setup_record) as f:
            sr = json.load(f)
        assert sr["roster"] == "all" and sr["targets"]
    except Exception:                                             # noqa: BLE001
        raise SystemExit("refusing: the setup record is unreadable or is not a setup-only pass over the full roster")
    made_by = sr.get("hashes") or {}
    stale = sorted(k for k, v in code_hashes().items() if made_by.get(k) != v)
    if stale:
        raise SystemExit("refusing: the setup record was made by other code than the files being frozen (%s); make it again"
                         % [os.path.basename(k) for k in stale])
    body = dict(author="Chimdi Walter Ndubuisi", what="hash manifest of EAF1 (evidence across failures)", files=file_hashes(True),
                stage_a_files=eaf_frozen.stage_a_files(), setup_record=dict(name=os.path.basename(setup_record), sha256=sha256_file(setup_record)),
                python=platform.python_version(), env="PYTHONHASHSEED=0, python3 -s -B")
    with open(path, "x") as f:
        json.dump(body, f, indent=1, sort_keys=True)
        f.write("\n")


def check_freeze(path, setup_record, base=None):
    """Return the sha256 of the freeze file, or raise SystemExit when a hash differs, a file is not covered, or the setup record
    is not the committed one."""
    base = base or ROOT
    with open(path, "rb") as f:
        raw = f.read()
    try:
        body = json.loads(raw)
        files, sfiles, srec = body["files"], body["stage_a_files"], body["setup_record"]
    except Exception as e:                                        # noqa: BLE001
        raise SystemExit("refusing: freeze file unreadable (%s)" % type(e).__name__)
    need = {rel(os.path.join(HERE, n), base) for n in OWN_FILES}
    need |= {rel(p, base) for p in extra_files(True)}
    need.add(rel(eaf_frozen.STAGE_A_FREEZE, base))
    missing = sorted(need - set(files))
    if missing:
        raise SystemExit("refusing: freeze does not cover %s" % missing)
    live_a = eaf_frozen.stage_a_files()
    missing = sorted(set(live_a) - set(sfiles))
    if missing:
        raise SystemExit("refusing: freeze does not cover stage A's files %s" % missing)
    for table in (files, sfiles):
        for r, want in sorted(table.items()):
            p = os.path.join(base, r)
            if not os.path.exists(p) or sha256_file(p) != want:
                raise SystemExit("refusing: %s differs from the freeze" % r)
    for r, want in live_a.items():
        if sfiles.get(r) != want:
            raise SystemExit("refusing: stage A's freeze lists a different hash for %s" % r)
    if not setup_record or not os.path.exists(setup_record) or sha256_file(setup_record) != srec["sha256"]:
        raise SystemExit("refusing: the setup record differs from the freeze (or does not exist)")
    return hashlib.sha256(raw).hexdigest()


def refuse_if_launched(folder):
    """A receipt that already exists refuses, whatever its output folder: an interrupted run is not resumed, reset or replayed."""
    existing = sorted(glob.glob(os.path.join(folder, "RECEIPT_ALL_ROSTER*.json")))
    if existing:
        raise SystemExit("refusing: an all-roster run already has a receipt (%s); it is launched once and never resumed" % existing[0])


def ensure_receipt(folder, outdir, freeze_sha, setup_sha=None):
    """Exclusive receipt of THE all-roster run, written before its first target."""
    refuse_if_launched(folder)
    p = os.path.join(folder, "RECEIPT_ALL_ROSTER.json")
    try:
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError:
        raise SystemExit("refusing: receipt exists")
    with os.fdopen(fd, "w") as f:
        json.dump(dict(outdir=os.path.realpath(outdir), freeze_sha256=freeze_sha, setup_record_sha256=setup_sha, pid=os.getpid(),
                       time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())), f, indent=1)
    return p


def roster_of(name):
    import consumers as C
    return list(P.DEV_ROSTER) if name == "dev" else C.roster_all()


def do_setup_only(path, roster_name):
    import episode_eaf as E
    if os.path.exists(path):
        raise SystemExit("refusing: %s exists" % path)
    made_by = file_hashes()                                    # taken BEFORE the pass; the record names the code that made it
    roster = roster_of(roster_name)
    views = {}
    t0 = time.process_time()
    for i, X in enumerate(roster):
        v = E.setup_only(X)
        views[X] = {k: v[k] for k in ("decision", "counts", "dev", "held_out_family", "cpu_s", "opened_roles")}
        views[X]["wrapper_detail"] = (v.get("detail") or {}).get("wrappers")
        views[X]["acquisition_check"] = (v.get("detail") or {}).get("acquisition_check")
        print("[%d/%d] %s %s cohorts=%s%s%s" % (i + 1, len(roster), X, v["decision"]["status"],
              int(v["decision"]["cohort_construction"]), int(v["decision"]["cohort_admission"]), int(v["decision"]["cohort_reuse"])), flush=True)
    dec = [v["decision"] for v in views.values()]
    if file_hashes() != made_by:
        raise SystemExit("refusing: a file of this experiment changed during the setup-only pass; nothing written")
    body = dict(label=LABEL, what="setup-only pass: eligibility record (no search; the final role is never opened)", roster=roster_name,
                development_only=roster_name == "dev", targets=views, hashes=made_by, wrapper_tag=P.WRAPPER_TAG, seq_tag=P.SEQ_TAG,
                python=platform.python_version(),
                counts=dict(n=len(views), eligible=sum(d["status"] == "eligible" for d in dec), excluded=sum(d["status"] == "excluded" for d in dec),
                            construction=sum(d["cohort_construction"] for d in dec), admission=sum(d["cohort_admission"] for d in dec),
                            reuse=sum(d["cohort_reuse"] for d in dec),
                            construction_outside_development_roster=sum(d["cohort_construction"] for X, d in zip(views, dec) if X not in P.DEV_ROSTER),
                            exclusions_by_kind={k: [d["reason_kind"] for d in dec].count(k) for k in {d["reason_kind"] for d in dec if d["status"] == "excluded"}}),
                cpu_s=round(time.process_time() - t0, 1))
    with open(path, "x") as f:
        json.dump(body, f, indent=1, sort_keys=True)
        f.write("\n")
    print("setup-only record written:", path, body["counts"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--roster", choices=("dev", "all"))
    ap.add_argument("--targets")
    ap.add_argument("--freeze")
    ap.add_argument("--setup-record")
    ap.add_argument("--B", type=float, help="development only: CPU allowance override")
    ap.add_argument("--make-freeze")
    ap.add_argument("--setup-only")
    a = ap.parse_args(argv)
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("run with PYTHONHASHSEED=0")
    if a.make_freeze:
        make_freeze(a.make_freeze, a.setup_record)
        return 0
    if a.setup_only:
        if not a.roster:
            sys.exit("--setup-only needs --roster dev|all")
        do_setup_only(a.setup_only, a.roster)
        return 0
    if not a.outdir or not a.roster:
        sys.exit("need <outdir> and --roster dev|all")
    freeze_sha = setup_sha = None
    if a.roster == "all":
        if not a.freeze:
            raise SystemExit("refusing: --roster all needs --freeze <FREEZE.json>")
        if not a.setup_record:
            raise SystemExit("refusing: --roster all needs --setup-record <the committed setup record>")
        if a.B is not None or a.targets:
            raise SystemExit("refusing: --B and --targets are for the development roster only")
        freeze_sha = check_freeze(a.freeze, a.setup_record)
        setup_sha = sha256_file(a.setup_record)
        refuse_if_launched(HERE)                               # first, so that a later launch is told why it is refused
        if os.path.lexists(a.outdir) and (not os.path.isdir(a.outdir) or os.listdir(a.outdir)):
            raise SystemExit("refusing: the output folder of the all-roster run must be new or empty")
        ensure_receipt(HERE, a.outdir, freeze_sha, setup_sha)
    elif a.setup_record and not os.path.exists(a.setup_record):
        raise SystemExit("refusing: setup record does not exist")
    import episode_eaf as E
    import summarize_eaf as SM
    roster = roster_of(a.roster)
    targets = roster
    if a.targets:
        targets = a.targets.split(",")
        bad = [t for t in targets if t not in roster]
        if bad:
            raise SystemExit("refusing: targets outside the %s roster: %s" % (a.roster, bad))
    B = P.B if a.B is None else a.B
    os.makedirs(a.outdir, exist_ok=True)
    mp = os.path.join(a.outdir, "MANIFEST.json")
    if not os.path.exists(mp):
        with open(mp, "w") as f:
            json.dump(dict(label=LABEL, roster=a.roster, targets=targets, B=B, development_only=a.roster == "dev", freeze_sha256=freeze_sha,
                           setup_record=a.setup_record, setup_record_sha256=sha256_file(a.setup_record) if a.setup_record else None,
                           hashes=file_hashes(), python=platform.python_version(), pythonhashseed=os.environ["PYTHONHASHSEED"]),
                      f, indent=1, sort_keys=True)
    for i, X in enumerate(targets):
        t = time.process_time()
        r = E.run_target(X, a.outdir, B)
        print("[%d/%d] %s %s %s cpu=%.1f" % (i + 1, len(targets), X, r.get("status"), (r.get("reason") or "")[:60], time.process_time() - t), flush=True)
    s = SM.write_summary(a.outdir, a.setup_record)
    blk = s["block_outside_development_roster" if a.roster == "all" else "block_development_roster_development_only"]
    print("summary: run=%d construction=%d excluded=%d incomplete=%d total_cpu_s=%s" % (
        s["n_run"], blk["cohort_sizes"]["construction"], blk["exclusions"]["n"], blk["incomplete_infrastructure"]["n"],
        blk["costs"]["total_cpu_s_of_targets"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
