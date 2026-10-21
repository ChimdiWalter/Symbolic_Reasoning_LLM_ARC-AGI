"""Real-task check: native CORA v23 (A), ncv2-g2 (B), ncv2-g3 (C) and ncv2-g4 (D), with g4 ablations and a CPU-matched
ncv2-g3, on a fresh eligibility-checked cohort of public ARC-AGI-2 training tasks; an optional arm E enters only
through a frozen addendum. Protocol: records/NEURAL_CORA_REALARC_G2G3G4_PROTOCOL_20261021.md. FROZEN, NOT RUN:
`solve` refuses without `--authorized`, a passing lock check and the lead's READY_TO_RUN flag.

    python scripts/neural_cora_realarc_g2g3g4_eval.py prepare             # the next 100 in-scope candidates (no answers)
    python3 -I tools/stepb_eligibility/check_eligibility.py CANDIDATES OUT  # ONE authorized metadata-only run (separate)
    python scripts/neural_cora_realarc_g2g3g4_eval.py freeze              # the manifest, written last
    python scripts/neural_cora_realarc_g2g3g4_eval.py lockcheck           # prints "LOCK OK ..." or exits non-zero
    python scripts/neural_cora_realarc_g2g3g4_eval.py solve --authorized  # every arm on inputs only; native last
    python scripts/neural_cora_realarc_g2g3g4_eval.py score               # evaluator: the sha-pinned solutions file

**Arms** (each (task, arm) runs in a fresh worker process, so no arm inherits another's caches):
- A `native`: native CORA v23 through the unchanged funnel harness (`cora_funnel.run.job`, native mode: sealed v23
  flags, CPU clock, its own hard cap); it submits its certified predictions;
- B `g2`: `cora_neural_v2g2.search.search`, byte-identical to its GO version, 3,000 candidates, 120 CPU-s. It searches
  the first test input; its two attempt programs are then executed on every other test input (solver side);
- C `g3`, D `g4`, and `g4_no_construct`, `g4_no_invert`, then `g3_cpu` (paired with the task's g4 CPU): exactly the
  arm definitions of `scripts/neural_cora_v2g4_eval.py` (`run_arm`, imported unchanged), on every test input;
- E: only if a frozen addendum (`records/NEURAL_CORA_REALARC_G2G3G4_ARM_E_MANIFEST.json`, committed, its code hashes
  matching) exists when `solve` starts; it names a module path and a function `fn(task, budget, cpu_cap_s)` returning
  {"predictions", "attempts_by_test", ...}. Without it, E is not run. Arms A to D never depend on it.
"""
import argparse
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
import re
import resource
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
OUT = os.path.join("outputs", "neural_cora_realarc_g2g3g4")
CAND = os.path.join(OUT, "cohort_candidates_20261021.json")
ELIG = os.path.join(OUT, "eligibility", "eligible_ids_20261021.json")
READY = os.path.join(OUT, "READY_TO_RUN")                         # created by the lead only, never by this script
PROTOCOL = os.path.join("records", "NEURAL_CORA_REALARC_G2G3G4_PROTOCOL_20261021.md")
MANIFEST = os.path.join("records", "NEURAL_CORA_REALARC_G2G3G4_FREEZE_MANIFEST.json")
E_MANIFEST = os.path.join("records", "NEURAL_CORA_REALARC_G2G3G4_ARM_E_MANIFEST.json")
V4E_PATH = os.path.join("scripts", "neural_cora_v2g4_eval.py")
PRIOR = {"g2": os.path.join("records", "NEURAL_CORA_V2G2_SYNTHETIC_FREEZE_MANIFEST.json"),
         "g3": os.path.join("records", "NEURAL_CORA_V2G3_SYNTHETIC_FREEZE_MANIFEST.json"),
         "g4": os.path.join("records", "NEURAL_CORA_V2G4_FREEZE_MANIFEST.json"),
         "native": os.path.join("records", "NEURAL_CORA_V1_FREEZE_MANIFEST.json")}
N_CANDIDATES = 100
MIN_CANDIDATES = 60
CATALOGUE_IDS = 300                    # a file naming >= this many in-scope IDs is a catalogue, not a record of use
BUDGET, CPU_CAP_S, WORKERS, NICE = 3000, 120.0, 2, 10
ARMS_PHASE1 = ("g2", "g3", "g4", "g4_no_construct", "g4_no_invert")
ARMS_PHASE2 = ("g3_cpu",)
LETTER = {"native": "A", "g2": "B", "g3": "C", "g4": "D", "E": "E"}
MAX_ERROR_TASKS = 5
CODE = ["geocat_arc/**/*.py", "harness/*.py", "cora_funnel/*.py", "cora_pilot/*.py", "cora_neural_v2/*.py",
        "cora_neural_v2g2/*.py", "cora_neural_v2g3/*.py", "cora_neural_v2g4/*.py", V4E_PATH,
        "scripts/neural_cora_realarc_g2g3g4_eval.py"]
INPUTS = [CAND, ELIG]
HEX8 = re.compile(r"(?<![0-9a-f])([0-9a-f]{8})(?![0-9a-f])")


def path(p, root=HERE):
    return os.path.join(root, p)


def sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def sha_list(xs):
    return hashlib.sha256(json.dumps(list(xs)).encode()).hexdigest()


def code_hashes(root=HERE):
    import glob
    out = {}
    for pat in CODE:
        for f in sorted(glob.glob(path(pat, root), recursive=True)):
            if "__pycache__" not in f:
                out[os.path.relpath(f, root)] = sha_file(f)
    return out


def native_aggregate(root=HERE):
    import glob
    files = sorted(os.path.relpath(f, root) for f in glob.glob(path("geocat_arc/**/*.py", root), recursive=True)
                   if "__pycache__" not in f)
    return hashlib.sha256("".join(f"{f}:{sha_file(path(f, root))}\n" for f in files).encode()).hexdigest()


def _git(*args):
    return subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True)


# ------------------------------------------------------------------ cohort (no answers are read)
def _used_ids(in_scope, skip):
    """IDs named in any record or output file (a catalogue naming >= CATALOGUE_IDS in-scope IDs is skipped and logged)."""
    used, n_files, catalogues = set(), 0, []
    for top in ("records", "outputs"):
        for dirpath, _dirs, files in os.walk(path(top)):
            if os.path.abspath(dirpath).startswith(os.path.abspath(path(OUT))):
                continue
            for name in files:
                f = os.path.join(dirpath, name)
                rel = os.path.relpath(f, HERE)
                if not name.endswith((".json", ".jsonl", ".md", ".txt", ".csv")) or rel in skip:
                    continue
                try:
                    if os.path.getsize(f) > 50_000_000:
                        continue
                    ids = set(HEX8.findall(open(f, errors="ignore").read())) & in_scope
                except OSError:
                    continue
                n_files += 1
                if len(ids) >= CATALOGUE_IDS:
                    catalogues.append([rel, len(ids)])
                else:
                    used |= ids
    return used, n_files, sorted(catalogues)


def prepare(a=None):
    if os.path.exists(path(ELIG)):
        sys.exit("refused: the eligibility check has already run on the current candidates")
    from cora_pilot import bundle as B
    ch = B.load_challenges()                                           # sha-pinned; demonstrations and test inputs only
    sel_rel = os.path.join("records", "pilot_v1", "selection.json")
    sel = json.load(open(path(sel_rel)))
    assert sel["challenges_sha256"] == B.CHALLENGES_SHA256
    dev = set(sel["dev"])
    order = [t for t, _s in sel["order"]]
    stratum = dict((t, s) for t, s in sel["order"])
    quota, seen, pilot = {"n3": 60, "n4": 40, "n5p": 20}, {"n3": 0, "n4": 0, "n5p": 0}, set()
    for t in order:
        if t not in dev and seen[stratum[t]] < quota[stratum[t]]:
            pilot.add(t)
            seen[stratum[t]] += 1
    standin_rel = os.path.join("outputs", "kaggle_deploy", "native_v1", "kaggle_run_v1", "comp", "arc-agi_test_challenges.json")
    standin = set(json.load(open(path(standin_rel))))
    c19_rel = os.path.join("outputs", "cora_revision_v2", "cohort_audit_20261019.json")
    c20_rel = os.path.join("outputs", "neural_cora_v2g2", "realarc", "cohort_candidates_20261020.json")
    c19 = set(json.load(open(path(c19_rel)))["candidates_additions_only_ordered"])
    c20 = set(json.load(open(path(c20_rel)))["candidates_additions_only_ordered"])
    in_scope = set(order)
    used, n_files, catalogues = _used_ids(in_scope, {sel_rel, standin_rel, c19_rel, c20_rel})
    excluded = dev | pilot | standin | c19 | c20 | used
    remaining = [t for t in order if t not in excluded]
    cands = remaining[:N_CANDIDATES]                                  # every remaining task when fewer than 100 remain
    assert len(cands) >= MIN_CANDIDATES, f"only {len(cands)} candidates remain"
    res = {"rule": f"the first {N_CANDIDATES} (or all, if fewer remain) remaining in-scope tasks in the pilot's published order (records/pilot_v1/"
                   "selection.json: ascending sha256('cora-real-arc-pilot-v1|' + id)), excluding dev60, the frozen 120 "
                   "pilot, the 240 stand-ins, the 100 candidates of 19 October, the 100 candidates of 20 October, and "
                   "every in-scope ID named in any file under records/ or outputs/ (catalogues listed below excepted)",
           "note": "the key name `candidates_additions_only_ordered` is the one the frozen eligibility checker reads; "
                   "this list is NOT restricted to additions-only tasks",
           "candidates_additions_only_ordered": cands, "candidates_sha256": sha_list(cands),
           "excluded_ids": sorted(excluded & in_scope), "excluded_sha256": sha_list(sorted(excluded & in_scope)),
           "counts": {"in_scope": len(order), "dev60": len(dev & in_scope), "frozen_pilot_120": len(pilot),
                      "standin_in_scope": len(standin & in_scope), "candidates_20261019": len(c19 & in_scope),
                      "candidates_20261020": len(c20 & in_scope), "used_in_records_or_outputs": len(used),
                      "files_scanned": n_files, "excluded_total": len(excluded & in_scope), "remaining": len(remaining),
                      "candidates": len(cands)},
           "catalogue_files_skipped": catalogues,
           "overlap_checks": {k: len(set(cands) & s) for k, s in (("dev60", dev), ("pilot", pilot), ("standin", standin),
                                                                 ("c19", c19), ("c20", c20), ("used", used))},
           "exposure": "public ARC-AGI-2 training tasks: seen by the sealed v23 1000-task baseline run and in NVARC's "
                       "training mix; Step B protected-split membership is checked separately by tools/stepb_eligibility"}
    os.makedirs(path(os.path.dirname(CAND)), exist_ok=True)
    json.dump(res, open(path(CAND), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("counts", "overlap_checks", "candidates_sha256")}, indent=1))


def cohort(root=HERE):
    cand = json.load(open(path(CAND, root)))
    el = json.load(open(path(ELIG, root)))
    assert el["attestation"]["status"] == "PASS" and el["checksums"]["candidates_sha256"] == cand["candidates_sha256"]
    return list(el["eligible_ids"])


def load_inputs(ids):
    """Demonstrations and every test input from the challenges file; the solutions file is never opened here."""
    from cora_pilot import bundle as B
    ch = B.load_challenges()
    return [{"task_id": t, "train": [(p["input"], p["output"]) for p in ch[t]["train"]],
             "test_inputs": [p["input"] for p in ch[t]["test"]]} for t in ids]


# ------------------------------------------------------------------ freeze and lock
def freeze(a=None):
    cur = code_hashes()
    for k, pattern in (("g2", ("cora_neural_v2/", "cora_neural_v2g2/")), ("g3", ("cora_neural_v2g3/",)),
                       ("g4", ("cora_neural_v2g4/", V4E_PATH))):
        prior = json.load(open(path(PRIOR[k])))["code"]
        diff = sorted(f for f, h in prior.items() if f.startswith(pattern) and cur.get(f) != h)
        if diff:
            sys.exit(f"not frozen: {k} code differs from its frozen version: {diff}")
    v1 = json.load(open(path(PRIOR["native"])))["groups"]["native_cora_v23_geocat_arc"]
    if native_aggregate() != v1["aggregate_sha256"]:
        sys.exit("not frozen: native CORA differs from the v1 freeze")
    for f in (PROTOCOL, os.path.relpath(__file__, HERE)):
        if _git("diff", "--quiet", "HEAD", "--", f).returncode or _git("ls-files", "--error-unmatch", f).returncode:
            sys.exit(f"not frozen: {f} must be committed unchanged before the freeze")
    ids = cohort()
    T = load_inputs(ids)
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_head": _git("rev-parse", "HEAD").stdout.strip(),
           "code": cur, "native_aggregate_sha256": native_aggregate(), "inputs": {p: sha_file(path(p)) for p in INPUTS},
           "protocol_sha256": sha_file(path(PROTOCOL)), "cohort": ids, "cohort_sha256": sha_list(ids), "n_primary": len(ids),
           "n_multi_test": sum(len(t["test_inputs"]) > 1 for t in T),
           "identity": {"g2": "cora_neural_v2/ and cora_neural_v2g2/ byte-identical to " + PRIOR["g2"],
                        "g3": "cora_neural_v2g3/ byte-identical to " + PRIOR["g3"],
                        "g4": "cora_neural_v2g4/ and " + V4E_PATH + " byte-identical to " + PRIOR["g4"],
                        "native": "geocat_arc aggregate equal to " + PRIOR["native"]},
           "settings": {"budget": BUDGET, "cpu_cap_s": CPU_CAP_S, "workers": WORKERS, "nice": NICE,
                        "arms_phase1": list(ARMS_PHASE1), "arms_phase2": list(ARMS_PHASE2), "native": "cora_funnel.run.job native mode",
                        "arm_E": "only through " + E_MANIFEST + ", frozen before solve starts"}}
    json.dump(man, open(path(MANIFEST), "w"), indent=1)
    print("frozen:", man["n_primary"], "primary tasks;", man["n_multi_test"], "with several test inputs")


def lock_problems(root=HERE, man=None, check_inputs=True, check_native=True):
    man = man or json.load(open(path(MANIFEST, root)))
    probs = []
    cur = code_hashes(root)
    for f in sorted(set(man["code"]) | set(cur)):
        if man["code"].get(f) != cur.get(f):
            probs.append(f"code differs: {f}")
    if man["protocol_sha256"] != sha_file(path(PROTOCOL, root)):
        probs.append("protocol differs")
    if check_inputs and man.get("inputs") != {p: sha_file(path(p, root)) for p in INPUTS}:
        probs.append("cohort inputs differ")
    if check_native and man.get("native_aggregate_sha256") != native_aggregate(root):
        probs.append("native CORA differs")
    return probs


def arm_e_status():
    """None (no addendum), or {"path", "function", "code"} of a valid frozen addendum; exits on an invalid one."""
    if not os.path.exists(path(E_MANIFEST)):
        return None
    m = json.load(open(path(E_MANIFEST)))
    probs = [f"arm E code differs: {f}" for f, h in m["code"].items() if not os.path.exists(path(f)) or sha_file(path(f)) != h]
    if m["entry"]["path"] not in m["code"]:
        probs.append("arm E entry module is not hashed")
    for f in [E_MANIFEST, m.get("addendum", "")]:
        if not f or _git("diff", "--quiet", "HEAD", "--", f).returncode or _git("ls-files", "--error-unmatch", f).returncode:
            probs.append(f"arm E file not committed unchanged: {f}")
    if probs:
        sys.exit("locked: " + "; ".join(probs))
    return m["entry"] | {"code": m["code"]}


def check_lock():
    probs = lock_problems()
    for f in (PROTOCOL, MANIFEST):
        if _git("diff", "--quiet", "HEAD", "--", f).returncode or _git("ls-files", "--error-unmatch", f).returncode:
            probs.append(f"{f} is not committed unchanged")
    if probs:
        sys.exit("locked: " + "; ".join(probs))
    return {"manifest_sha256": sha_file(path(MANIFEST)), "git_head": _git("rev-parse", "HEAD").stdout.strip(),
            "arm_E": "frozen addendum present" if os.path.exists(path(E_MANIFEST)) else "no addendum: E is not run"}


def lockcheck(a=None):
    lock = check_lock()
    arm_e_status()
    print("LOCK OK", json.dumps(lock))


# ------------------------------------------------------------------ arms (solver side: inputs only)
def _v4e():
    spec = importlib.util.spec_from_file_location("neural_cora_v2g4_eval_frozen", path(V4E_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _g2_arm(task, budget, cpu_cap_s):
    from cora_neural_v2g2 import grammar as G
    from cora_neural_v2g2 import search as S2
    r = S2.search(task, budget, cpu_cap_s=cpu_cap_s)                 # it uses the first test input only
    by_test = [r["attempts"]]
    for x in task["test_inputs"][1:]:                                # the two attempt programs on every other test input
        outs = []
        for s in r["programs"][:len(r["attempts"])]:
            try:
                p = G.execute(G.parse(s), x)
            except Exception:                                        # noqa: BLE001 (no output for this test input)
                p = None
            outs.append(None if p is None else np.asarray(p).tolist())
        by_test.append(outs)
    keep = ("predictions", "pred_at", "attempts", "programs", "first_fit_at", "n_candidates", "n_consistent",
            "n_distinct_predictions", "state", "cpu_s")
    return {**{k: r[k] for k in keep if k in r}, "attempts_by_test": by_test}


def _e_arm(task, budget, cpu_cap_s, entry):
    spec = importlib.util.spec_from_file_location("arm_e_entry", path(entry["path"]))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, entry["function"])(task, budget, cpu_cap_s)


def run_one(task, arm, paired=None, budget=BUDGET, cpu_cap_s=CPU_CAP_S, entry=None):
    """One ncv2 (or E) arm on one task's inputs ({"task_id", "train", "test_inputs"}); returns the kept record."""
    t = {k: task[k] for k in ("task_id", "train", "test_inputs")}
    if arm == "g2":
        return _g2_arm(t, budget, cpu_cap_s)
    if arm == "E":
        return _e_arm(t, budget, cpu_cap_s, entry)
    return _v4e().run_arm(t, arm, budget=budget, cpu_cap_s=cpu_cap_s, paired=paired)


def _job(args):
    task, arm, paired, entry = args
    if os.nice(0) < NICE:
        os.nice(NICE - os.nice(0))
    w0 = time.time()
    row = {"task_id": task["task_id"], "arm": arm}
    try:
        if arm == "native":
            from cora_funnel import run as FR                           # the unchanged native harness
            t = {"train": [{"input": a, "output": b} for a, b in task["train"]], "test": [{"input": x} for x in task["test_inputs"]]}
            row["rec"] = FR.job((task["task_id"], t, "realarc_g2g3g4", "native"))
        else:
            row["rec"] = run_one(task, arm, paired=paired, entry=entry)
    except Exception as e:                                          # noqa: BLE001 (an error: the stop rule counts it)
        row["exception"] = repr(e)[:500]
    row["wall_s"] = round(time.time() - w0, 2)
    row["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    return row


def is_error(row):
    """An exception or crash. A budget truncation or native's own hard timeout is NOT an error (reported separately)."""
    if "exception" in row:
        return True
    err = (row.get("rec") or {}).get("error") if row["arm"] == "native" else None
    return bool(err) and err != "object_hard_timeout"


def _rows(p):
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def _pool(jobs, p, stage):
    err_tasks = {r["task_id"] for r in _rows(p) if is_error(r)}
    with mp.get_context("fork").Pool(WORKERS, maxtasksperchild=1) as pool, open(p, "a") as fh:
        for i, row in enumerate(pool.imap_unordered(_job, jobs), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            if is_error(row):
                err_tasks.add(row["task_id"])
            print(f"[{stage} {i}/{len(jobs)}] {row['task_id']} {row['arm']} {'ERROR' if is_error(row) else ''}", flush=True)
            if len(err_tasks) > MAX_ERROR_TASKS:
                pool.terminate()
                sys.exit(f"STOPPED: more than {MAX_ERROR_TASKS} tasks raised errors in stage {stage} (protocol section 7)")


def solve(a):
    if not a.authorized:
        sys.exit("solve needs --authorized (see the protocol)")
    lock = check_lock()
    if not os.path.exists(path(READY)):
        sys.exit("solve waits for the lead's flag " + READY)
    entry = arm_e_status()
    os.environ["CORA_FUNNEL_NICE"] = str(NICE)                      # read by cora_funnel.run at import: native at nice 10
    os.makedirs(path(OUT), exist_ok=True)
    T = load_inputs(json.load(open(path(MANIFEST)))["cohort"])
    json.dump({"lock": lock, "arm_E": entry, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
              open(path(os.path.join(OUT, "run_manifest.json")), "w"), indent=1)
    rows_p = path(os.path.join(OUT, "rows.jsonl"))
    arms1 = ARMS_PHASE1 + (("E",) if entry else ())
    done = {(r["task_id"], r["arm"]) for r in _rows(rows_p)}
    _pool([(t, arm, None, entry) for t in T for arm in arms1 if (t["task_id"], arm) not in done], rows_p, "phase1")
    v4e = _v4e()
    g4 = {r["task_id"]: r["rec"] for r in _rows(rows_p) if r["arm"] == "g4" and "rec" in r}
    done = {(r["task_id"], r["arm"]) for r in _rows(rows_p)}
    _pool([(t, arm, v4e.paired_info(g4[t["task_id"]]), None) for t in T for arm in ARMS_PHASE2
           if t["task_id"] in g4 and (t["task_id"], arm) not in done], rows_p, "phase2")
    done = {(r["task_id"], r["arm"]) for r in _rows(rows_p)}
    _pool([(t, "native", None, None) for t in T if (t["task_id"], "native") not in done], rows_p, "native")
    print("SOLVE_DONE", flush=True)


# ------------------------------------------------------------------ evaluator side
def _eq(p, A):
    if p is None:
        return False
    P = np.asarray(p)
    return P.shape == A.shape and bool((P == A).all())


def _sign_p(gains, losses):
    """Exact one-sided sign-test p for `gains` successes among the discordant pairs (descriptive only)."""
    from math import comb
    n = gains + losses
    return None if n == 0 else round(sum(comb(n, k) for k in range(gains, n + 1)) / 2 ** n, 4)


def _ncv2_record(r, ans):
    A = [np.asarray(x) for x in ans]
    by = r.get("attempts_by_test") or [r.get("attempts") or []]
    per_test = [k < len(by) and any(_eq(p, A[k]) for p in (by[k] or [])[:2]) for k in range(len(A))]
    head = r.get("head") or {}
    origin = None
    if per_test and all(per_test):
        sel = {s["program"]: s["origin"] for s in r.get("selection", [])}
        progs = r.get("attempt_programs") or []
        for i, p in enumerate((by[0] or [])[:2]):
            if _eq(p, A[0]) and i < len(progs):
                origin = sel.get(progs[i])
                break
    n_cand = r.get("n_candidates") or 0
    cons = head.get("construct_native_runs", 0) + head.get("loo_native_runs", 0)
    return {"fits": (r.get("n_consistent") or 0) > 0, "coverage_first": any(_eq(p, A[0]) for p in r.get("predictions", [])),
            "pass2_first": bool(per_test and per_test[0]), "pass2_all": bool(per_test) and all(per_test), "per_test": per_test,
            "wrong_all": bool(by and by[0]) and not (bool(per_test) and all(per_test)),
            "n_retained": len(r.get("predictions", [])), "n_distinct": r.get("n_distinct_predictions"),
            "n_candidates": n_cand, "construction_native_runs": cons, "native_executions_total": n_cand + cons,
            "cpu_s": r.get("cpu_s"), "correct_origin": origin}


def _native_record(n, ans, train):
    from cora_funnel.evaluate import task_record
    tr = task_record(n, ans, [{"input": x, "output": y} for x, y in train])
    A = [np.asarray(x) for x in ans]
    sets = [e for e in n["events"] if e["type"] in ("search", "generative") and e["n_programs"] > 0]
    preds = n.get("predictions") or []
    per_test = [bool(n["solved"]) and k < len(preds) and _eq(preds[k], A[k]) for k in range(len(A))]
    return {"category": tr["category"], "fits": tr["train_exact_candidates"] > 0,
            "coverage_first": any(o and _eq(o[0], A[0]) for e in sets for o in (e["outputs"] or [])),
            "coverage_all": bool(tr["any_candidate_correct"]), "certified": bool(n["solved"]),
            "certified_correct_all": bool(tr["correct"]), "certified_correct_first": bool(per_test and per_test[0]),
            "certified_wrong": bool(n["solved"]) and not tr["correct"], "per_test": per_test,
            "hard_timeout": n.get("error") == "object_hard_timeout", "cpu_s": n.get("cpu_s")}


def decide(s):
    """The frozen rules (protocol section 6), PRIMARY cohort."""
    B, C, D, Cc = s["arms"]["g2"], s["arms"]["g3"], s["arms"]["g4"], s["arms"]["g3_cpu"]
    g3 = (C["pass2_all"] - B["pass2_all"] >= 3 and C["coverage_first"] - B["coverage_first"] >= 3
          and s["paired"]["g3_vs_g2"]["losses"] <= 1)
    g4 = (D["pass2_all"] - C["pass2_all"] >= 3 and D["coverage_first"] - C["coverage_first"] >= 3
          and s["paired"]["g4_vs_g3"]["losses"] <= 1 and D["coverage_first"] - Cc["coverage_first"] >= 2)
    return {"g3": "GO_REAL_G3" if g3 else "NO_REAL_GAIN_G3", "g4": "GO_REAL_G4" if g4 else "NO_REAL_GAIN_G4"}


def score(a=None):
    from cora_pilot import bundle as B
    from cora_pilot import evaluator as EV
    sol = EV.load_pinned(B.SOLUTIONS, B.SOLUTIONS_SHA256)           # the only reader of test outputs
    man = json.load(open(path(MANIFEST)))
    if man["inputs"] != {p: sha_file(path(p)) for p in INPUTS}:
        sys.exit("the cohort inputs differ from the freeze manifest")
    rows = {(r["task_id"], r["arm"]): r for r in _rows(path(os.path.join(OUT, "rows.jsonl")))}
    trains = {t["task_id"]: t["train"] for t in load_inputs(man["cohort"])}
    arms = [a for a in ARMS_PHASE1 + ARMS_PHASE2 + ("E",) if any(k[1] == a for k in rows)]
    per = []
    for t in man["cohort"]:
        rec = {"task_id": t, "n_test": len(sol[t])}
        for arm in arms + ["native"]:
            r = rows.get((t, arm))
            if r is None or "rec" not in r:
                rec[arm] = {"missing": True, "error": bool(r and is_error(r))}
                continue
            rec[arm] = _native_record(r["rec"], sol[t], trains[t]) if arm == "native" else _ncv2_record(r["rec"], sol[t])
            rec[arm]["error"] = is_error(r)
        per.append(rec)

    def ok(r, arm, m):
        return bool(r.get(arm, {}).get(m))

    def pair(x, mx, y, my):
        g = sorted(r["task_id"] for r in per if ok(r, x, mx) and not ok(r, y, my))
        l = sorted(r["task_id"] for r in per if ok(r, y, my) and not ok(r, x, mx))
        return {"gains": len(g), "losses": len(l), "gain_ids": g, "loss_ids": l, "sign_p": _sign_p(len(g), len(l))}
    ms = ("fits", "coverage_first", "pass2_first", "pass2_all", "wrong_all")
    s = {"n": len(per), "decision_budget": BUDGET,
         "arms": {arm: {**{m: sum(ok(r, arm, m) for r in per) for m in ms},
                        "missing": sum(bool(r[arm].get("missing")) for r in per), "errors": sum(bool(r[arm].get("error")) for r in per),
                        "retained_mean": round(float(np.mean([r[arm].get("n_retained", 0) for r in per])), 2),
                        "native_executions_total": int(sum(r[arm].get("native_executions_total", 0) for r in per)),
                        "construction_native_runs": int(sum(r[arm].get("construction_native_runs", 0) for r in per)),
                        "cpu_s_total": round(float(sum(r[arm].get("cpu_s") or 0 for r in per)), 1),
                        "cpu_s_median": float(np.median([r[arm].get("cpu_s") or 0 for r in per]))} for arm in arms},
         "native": {m: sum(ok(r, "native", m) for r in per) for m in
                    ("fits", "coverage_first", "coverage_all", "certified", "certified_correct_all", "certified_correct_first",
                     "certified_wrong", "hard_timeout")} | {"cpu_s_total": round(float(sum(r["native"].get("cpu_s") or 0 for r in per)), 1)},
         "paired": {"g3_vs_g2": pair("g3", "pass2_all", "g2", "pass2_all"), "g4_vs_g3": pair("g4", "pass2_all", "g3", "pass2_all"),
                    "g4_vs_g2": pair("g4", "pass2_all", "g2", "pass2_all"), "g4_vs_g3_cpu": pair("g4", "pass2_all", "g3_cpu", "pass2_all")}
                   | {f"{arm}_vs_native": pair(arm, "pass2_all", "native", "certified_correct_all") for arm in arms}
                   | ({"E_vs_g3": pair("E", "pass2_all", "g3", "pass2_all")} if "E" in arms else {}),
         "g4_correct_origins": {o: sum(1 for r in per if ok(r, "g4", "pass2_all") and r["g4"].get("correct_origin") == o)
                                for o in sorted({r["g4"].get("correct_origin") for r in per if ok(r, "g4", "pass2_all")}, key=str)},
         "multi_test": [{"task_id": r["task_id"], **{arm: r[arm].get("per_test") for arm in arms + ["native"]}}
                        for r in per if r["n_test"] > 1],
         "arm_E": "run" if "E" in arms else "not run (no frozen addendum before the run)",
         "note": "public ARC-AGI-2 training tasks (seen by v23; in NVARC's training mix): development evidence, not unseen performance"}
    s["decision"] = decide(s)
    json.dump({"summary": s, "tasks": per}, open(path(os.path.join(OUT, "score.json")), "w"), indent=1)
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("prepare", "freeze", "lockcheck", "solve", "score"))
    ap.add_argument("--authorized", action="store_true")
    args = ap.parse_args()
    {"prepare": prepare, "freeze": freeze, "lockcheck": lockcheck, "solve": solve, "score": score}[args.stage](args)
