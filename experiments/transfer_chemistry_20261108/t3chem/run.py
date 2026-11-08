"""T3 runner. Run with python -I.

  dev:   python -I t3chem/run.py --mode dev --label NAME [--max-families N] [--slice a:b] [--summarise]
         development families only (fixed public salt); output labelled "development".
  score: python -I t3chem/run.py --mode score [--check-only]
         the one scored rerun (PROTOCOL.md, Amendments 1 and 2), launched by launch/run_score.sh. It refuses to
         start unless:
         - runs/score/ does not exist (attempt 1 is kept in runs/score_attempt1/) and no development option is given;
         - runs/GO (the original GO) is plain ASCII, starts with the line GO, has the fields study, freeze_commit,
           freeze_json_sha256, pre_run_review, nonce (64 lowercase hex) and written_utc, is committed at HEAD,
           was committed once and alone, and its freeze_commit holds the FREEZE.json it names;
         - runs/GO_AMENDMENT2 is plain ASCII, starts with the line GO_AMENDMENT2, has the fields study,
           freeze_commit, freeze_json_sha256, delta_review, original_go_commit and written_utc, is committed at
           HEAD, was committed once and alone, and names the commit of runs/GO;
         - GO_AMENDMENT2's freeze_commit is the last commit on HEAD that changed FREEZE.json and holds these exact
           bytes, its freeze_json_sha256 is the sha256 of FREEZE.json, and every file hash in FREEZE.json matches;
         - the commits are in this order: first freeze, pre-run review, GO, new freeze, delta review,
           GO_AMENDMENT2;
         - the Python and RDKit versions match FREEZE.json.
         The salt is the sha256 of the committed bytes of the original runs/GO, so the held set is the one of
         attempt 1. The run records the salt and the commits in runs/score/run.status and runs/score/summary.json.
         --check-only runs the checks, prints the verdict and writes nothing. A refusal in a real launch is
         appended to runs/refusals.log (never inside runs/score/).
"""
import argparse, collections, gzip, hashlib, json, os, platform, re, subprocess, sys, time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDY)
import rdkit  # noqa: E402
from rdkit import Chem  # noqa: E402
from t3chem.arms import Family, exact, grow, nn_predict, static_proposal  # noqa: E402
from t3chem.chem import apply_rules  # noqa: E402
from t3chem.library import load_library  # noqa: E402
from t3chem.stats import compare  # noqa: E402

ARMS = ["static", "grown", "shuffled", "nn", "grown_alt"]
REL = "experiments/transfer_chemistry_20261108/"
GO_PATH = os.path.join(STUDY, "runs", "GO")
AMEND_PATH = os.path.join(STUDY, "runs", "GO_AMENDMENT2")
SCORE_DIR = os.path.join(STUDY, "runs", "score")
REFUSALS = os.path.join(STUDY, "runs", "refusals.log")
GO_FIELDS = ["study", "freeze_commit", "freeze_json_sha256", "pre_run_review", "nonce", "written_utc"]
AMEND_FIELDS = ["study", "freeze_commit", "freeze_json_sha256", "delta_review", "original_go_commit", "written_utc"]
DEV_ONLY = ["label", "max_families", "tie_break", "nn_level", "cpu_budget", "slice", "summarise"]
CHECK_ONLY = [False]


def hx(s):
    return hashlib.sha256(s.encode()).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_families(cfg, dev_mode):
    fams = collections.defaultdict(list)
    with gzip.open(os.path.join(STUDY, "data", "cache", "items.jsonl.gz"), "rt") as fh:
        for line in fh:
            it = json.loads(line)
            if it["dev_family"] != dev_mode:
                continue
            if not dev_mode and it["in_dev_pair_set"]:
                continue
            fams[it["fam"]].append(it)
    return {f: v for f, v in fams.items() if len(v) >= cfg["min_items_per_family"]}


def select(fams, salt, n_fam, k, H):
    order = sorted(fams, key=lambda f: hx(salt + "|family|" + f))[:n_fam]
    split = {}
    for f in order:
        its = sorted(fams[f], key=lambda it: hx(salt + "|item|" + f + "|" + it["pair"]))
        split[f] = (its[:k], its[k:k + H])
    partner = {}
    for p, f in enumerate(order):
        for q in range(1, len(order)):
            g = order[(p + q) % len(order)]
            if g.split("|")[1] != f.split("|")[1]:
                partner[f] = g
                break
    return order, split, partner


def check_freeze():
    fz = json.load(open(os.path.join(STUDY, "FREEZE.json")))
    return [p for p, h in sorted(fz["files_sha256"].items())
            if not os.path.exists(os.path.join(STUDY, p)) or sha_file(os.path.join(STUDY, p)) != h]


def git(*args):
    return subprocess.run(["git", "-C", STUDY] + list(args), capture_output=True)


def write_status(msg):
    os.makedirs(SCORE_DIR, exist_ok=True)
    with open(os.path.join(SCORE_DIR, "run.status"), "a") as fh:
        fh.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + msg + "\n")


def refuse(msg):
    if not CHECK_ONLY[0]:
        with open(REFUSALS, "a") as fh:
            fh.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " REFUSED " + msg + "\n")
    sys.exit("refused: " + msg)


def is_hex(s, n):
    return len(s) == n and all(ch in "0123456789abcdef" for ch in s)


def is_commit(h):
    return is_hex(h, 40) and git("cat-file", "-e", h + "^{commit}").returncode == 0


def is_ancestor(a, b):
    return git("merge-base", "--is-ancestor", a, b).returncode == 0


def read_authorization(path, first_line, fields):
    """Bytes, fields and the single commit of a committed authorization file, or a refusal."""
    rel = os.path.relpath(path, STUDY)
    if not os.path.exists(path):
        refuse("no " + rel)
    raw = open(path, "rb").read()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        refuse(rel + " is not plain ASCII")
    lines = text.splitlines()
    if not lines or lines[0] != first_line:
        refuse("%s does not start with the line %s" % (rel, first_line))
    f = dict(line.split(": ", 1) for line in lines[1:] if ": " in line)
    missing = [k for k in fields if k not in f]
    if missing:
        refuse(rel + " lacks " + ", ".join(missing))
    if f["study"] != "transfer_chemistry_20261108":
        refuse(rel + " names another study")
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", f["written_utc"]):
        refuse(rel + " written_utc is not YYYY-MM-DDTHH:MM:SSZ")
    if git("show", "HEAD:%s%s" % (REL, rel)).stdout != raw:
        refuse(rel + " is not committed at HEAD or differs from it")
    # git runs with -C STUDY, so the pathspecs after "--" are absolute
    commits = git("log", "--format=%H", "HEAD", "--", path).stdout.decode().split()
    if len(commits) != 1:
        refuse(rel + " was changed after its first commit: the first committed version is final")
    touched = git("show", "--name-only", "--format=", commits[0]).stdout.decode().split()
    if touched != [REL + rel]:
        refuse(rel + " was not committed alone")
    return raw, f, commits[0]


def checks():
    """The checks of PROTOCOL.md Amendments 1 and 2. Returns (salt, freeze commit, GO commit, GO_AMENDMENT2
    commit) or refuses."""
    if os.path.exists(SCORE_DIR):
        refuse("runs/score/ exists: one scored rerun only (attempt 1 is kept in runs/score_attempt1/)")
    go, g, go_commit = read_authorization(GO_PATH, "GO", GO_FIELDS)
    if not is_hex(g["nonce"], 64):
        refuse("runs/GO nonce is not 64 lowercase hex characters")
    if not is_commit(g["pre_run_review"]):
        refuse("runs/GO pre_run_review is not a 40-character commit of this repository")
    if not is_commit(g["freeze_commit"]) or hashlib.sha256(
            git("show", "%s:%sFREEZE.json" % (g["freeze_commit"], REL)).stdout).hexdigest() != g["freeze_json_sha256"]:
        refuse("runs/GO freeze_commit does not hold the FREEZE.json that runs/GO names")
    am, m, am_commit = read_authorization(AMEND_PATH, "GO_AMENDMENT2", AMEND_FIELDS)
    if m["original_go_commit"] != go_commit:
        refuse("runs/GO_AMENDMENT2 original_go_commit is not the commit of runs/GO")
    fz = open(os.path.join(STUDY, "FREEZE.json"), "rb").read()
    if m["freeze_json_sha256"] != hashlib.sha256(fz).hexdigest():
        refuse("runs/GO_AMENDMENT2 names a different FREEZE.json")
    fc = m["freeze_commit"]
    last = git("log", "-n", "1", "--format=%H", "HEAD", "--", os.path.join(STUDY, "FREEZE.json")).stdout.decode().strip()
    if not is_hex(fc, 40) or fc != last or git("show", "%s:%sFREEZE.json" % (fc, REL)).stdout != fz:
        refuse("runs/GO_AMENDMENT2 freeze_commit is not the last commit on HEAD that changed FREEZE.json")
    if not is_commit(m["delta_review"]):
        refuse("runs/GO_AMENDMENT2 delta_review is not a 40-character commit of this repository")
    chain = [g["freeze_commit"], g["pre_run_review"], go_commit, fc, m["delta_review"], am_commit]
    if not all(is_ancestor(a, b) for a, b in zip(chain, chain[1:])):
        refuse("commit order is not: first freeze, pre-run review, GO, new freeze, delta review, GO_AMENDMENT2")
    bad = check_freeze()
    if bad:
        refuse("hash mismatch: " + ", ".join(bad))
    env = json.loads(fz).get("environment", {})
    have = {"python": platform.python_version(), "rdkit": rdkit.__version__}
    for k, v in have.items():
        if env.get(k) != v:
            refuse("%s version %s differs from FREEZE.json (%s)" % (k, v, env.get(k)))
    return hashlib.sha256(go).hexdigest(), fc, go_commit, am_commit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dev", "score"], required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--check-only", action="store_true", help="score mode: run the checks and stop")
    ap.add_argument("--max-families", type=int, default=0)
    ap.add_argument("--tie-break", default="")
    ap.add_argument("--nn-level", default="")
    ap.add_argument("--cpu-budget", type=float, default=0, help="development only: CPU-seconds cap")
    ap.add_argument("--slice", default="", help="development only: a:b, process families a to b-1 of the order")
    ap.add_argument("--summarise", action="store_true", help="development only: summarise the slices written")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(STUDY, "config", "T3_CONFIG.json")))
    t0 = time.process_time()
    freeze_commit = go_commit = am_commit = None
    if a.mode == "score":
        CHECK_ONLY[0] = a.check_only
        given = [k for k in DEV_ONLY if getattr(a, k)]
        if given:
            refuse("development options in score mode: " + ", ".join(given))
        salt, freeze_commit, go_commit, am_commit = checks()
        if a.check_only:
            print("checks passed: salt %s freeze_commit %s go_commit %s go_amendment2_commit %s"
                  % (salt, freeze_commit, go_commit, am_commit))
            return
        write_status("STARTED salt %s freeze_commit %s go_commit %s go_amendment2_commit %s"
                     % (salt, freeze_commit, go_commit, am_commit))
        n_fam, label = cfg["score"]["n_families"], "held"
        outdir = SCORE_DIR
        budget = 30 * 60
    else:
        salt, n_fam, label = cfg["dev"]["salt"], a.max_families or cfg["dev"]["max_families_per_run"], "development"
        outdir = os.path.join(STUDY, "runs", "dev_" + (a.label or "run"))
        budget = a.cpu_budget or 20 * 60
    tie = a.tie_break or cfg["level_tie_break"]
    nn_level = a.nn_level or cfg["nn"]["level"]
    os.makedirs(outdir, exist_ok=True)
    library, libinfo = load_library(os.path.join(STUDY, cfg["data"]["library_tsv"]))
    fams = load_families(cfg, a.mode == "dev")
    order, split, partner = select(fams, salt, n_fam, cfg["k"], cfg["held_per_family"])
    records, status = [], "DONE"
    if a.mode == "dev" and a.summarise:
        for fn in sorted(os.listdir(outdir)):
            if fn.startswith("families") and fn.endswith(".jsonl"):
                records += [json.loads(x) for x in open(os.path.join(outdir, fn))]
        status = "SUMMARY_OF_SLICES"
        todo = []
    else:
        lo, hi = (0, len(order))
        if a.mode == "dev" and a.slice:
            lo, hi = (int(x) for x in a.slice.split(":"))
        todo = order[lo:hi]
    fobj = {f: Family(f, [dict(e) for e in split[f][0]]) for f in order}
    out = open(os.path.join(outdir, "families%s.jsonl" % ("_%s" % a.slice.replace(":", "_") if a.slice else "")),
               "w") if todo else None
    for n, f in enumerate(todo):
        if time.process_time() - t0 > budget:
            status = "STOPPED_CPU_BUDGET"
            break
        tf = time.process_time()
        fam = fobj[f]
        srule, sex, scov = static_proposal(fam, library)
        g = grow(fam, srule, sex, cfg["levels"], tie)
        sh = grow(fam, srule, sex, cfg["levels"], tie, partner=fobj[partner[f]])
        rules = {"static": [srule] if srule else [], "grown": g["rules"], "shuffled": sh["rules"],
                 "grown_alt": g.get("alt_rules", g["rules"])}
        held = []
        for h in split[f][1]:
            mol = Chem.MolFromSmiles(h["sub"])
            rec = {"pair": h["pair"]}
            for arm in ("static", "grown", "shuffled", "grown_alt"):
                o = apply_rules(rules[arm], mol)
                rec[arm] = {"n": len(o), "exact": exact(o, h["prod_ns"]), "cover": h["prod_ns"] in o}
            o, idx = nn_predict(fam, mol, nn_level)
            rec["nn"] = {"n": len(o), "exact": exact(o, h["prod_ns"]), "cover": h["prod_ns"] in o, "example": idx}
            held.append(rec)
        strip = lambda d: {k: v for k, v in d.items() if k not in ("rules", "alt_rules")}
        fr = {"family": f, "train": [e["pair"] for e in split[f][0]], "n_held": len(held),
              "static": {"rule": srule["name"] if srule else None, "exact_on_k": sex, "cover_on_k": scov},
              "grown": strip(g), "grown_rules": [r["smarts"] for r in g["rules"]],
              "shuffled": strip(sh), "shuffle_partner": partner[f], "held": held,
              "cpu_s": round(time.process_time() - tf, 2)}
        out.write(json.dumps(fr) + "\n")
        out.flush()
        records.append(fr)
    if out:
        out.close()
    if a.mode == "dev" and a.slice:
        print(json.dumps({"label": label, "slice": a.slice, "families": len(records), "status": status,
                          "cpu_seconds": round(time.process_time() - t0, 1)}))
        return
    nh = sum(len(r["held"]) for r in records)
    summ = {"label": label, "status": status, "salt": salt, "families": len(records),
            "families_planned": len(order), "held_items": nh, "k": cfg["k"], "tie_break": tie,
            "nn_level": nn_level, "library": libinfo, "cpu_seconds": round(time.process_time() - t0, 1),
            "family_cpu_seconds_sum": round(sum(r["cpu_s"] for r in records), 1),
            "salt_rule": "sha256 of the committed bytes of the original runs/GO" if a.mode == "score"
            else "fixed development salt",
            "freeze_commit": freeze_commit, "go_commit": go_commit, "go_amendment2_commit": am_commit}
    for arm in ARMS:
        summ[arm] = {"exact": sum(h[arm]["exact"] for r in records for h in r["held"]),
                     "cover": sum(h[arm]["cover"] for r in records for h in r["held"]), "of": nh}
    summ["grown_status"] = dict(collections.Counter(r["grown"]["status"] for r in records))
    summ["grown_levels"] = dict(collections.Counter(r["grown"].get("level", "-") for r in records
                                                    if r["grown"]["status"] == "piece_kept"))
    summ["shuffled_status"] = dict(collections.Counter(r["shuffled"]["status"] for r in records))
    bs = cfg["bootstrap"]
    summ["primary_grown_vs_static"] = compare(records, "grown", "static", bs["resamples"], bs["seed"])
    summ["grown_vs_shuffled"] = compare(records, "grown", "shuffled", bs["resamples"], bs["seed"])
    summ["reference_grown_vs_nn"] = compare(records, "grown", "nn", bs["resamples"], bs["seed"])
    summ["diagnostic_grown_alt_tie_break_vs_static"] = compare(records, "grown_alt", "static", bs["resamples"],
                                                                bs["seed"])
    json.dump(summ, open(os.path.join(outdir, "summary.json"), "w"), indent=1)
    print(json.dumps({k: summ[k] for k in ("label", "status", "families", "held_items", "cpu_seconds")}))
    for arm in ARMS:
        print(arm, summ[arm])
    print("grown status", summ["grown_status"], "levels", summ["grown_levels"])
    p = summ["primary_grown_vs_static"]
    print("grown-static", p["difference_in_exact_rate"], p["bootstrap95"], "p", p["mcnemar_exact_p"])
    if a.mode == "score":
        write_status("%s %d families, %d held targets, %.1f CPU-seconds, salt %s, freeze_commit %s"
                     % (status, len(records), nh, summ["cpu_seconds"], salt, freeze_commit))


if __name__ == "__main__":
    main()
