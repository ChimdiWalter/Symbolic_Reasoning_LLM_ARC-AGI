"""The ncv2-g4 synthetic mechanism study on syn-v4 HELDOUT families: ncv2-g3 (frozen) against ncv2-g4 and its
ablations. Protocol: records/NEURAL_CORA_V2G4_PROTOCOL_20261021.md. FROZEN, NOT RUN: `solve` refuses without
`--authorized` and a passing lock check.

    python scripts/neural_cora_v2g4_eval.py prepare             # DEV and HELDOUT inputs, yields per family, parity
    python scripts/neural_cora_v2g4_eval.py freeze              # code, task and protocol hashes; overlap checks
    python scripts/neural_cora_v2g4_eval.py lockcheck           # verify the freeze (read-only)
    python scripts/neural_cora_v2g4_eval.py selftest            # DEV families, small budgets (engineering, never a result)
    python scripts/neural_cora_v2g4_eval.py solve --authorized  # HELDOUT: demonstrations + test inputs only
    python scripts/neural_cora_v2g4_eval.py score               # evaluator: regenerates answers from (family, seed)

**Arms** (paired: the same tasks; each (task, arm) runs in a fresh worker process, so no arm inherits another's
caches). Ablations replace ONE function of the frozen g4 code for the duration of the arm (`unittest.mock.patch`);
the frozen files are never edited:
- `g3`: cora_neural_v2g3.search.search, 3,000 candidates, 120 CPU-s (the control);
- `g4`: cora_neural_v2g4.search.search, 3,000 candidates, 120 CPU-s (the system under test);
- `g4_no_construct`: g4 with construct.programs returning nothing (inversion and geometry head only);
- `g4_no_invert`: g4 with invert.invert returning nothing (construct's rules alone; no partial-program bases);
- `g4_parts_only`: g4 with construct.shapes keeping part and region shapes only (no rays);
- `g4_rays_only`: g4 with construct.shapes keeping ray shapes only (no parts or regions);
- phase 2, paired with the task's g4 row:
  - `g3_cpu`: ncv2-g3 with 9,000 candidates and the CPU g4 used on that task (at most 120 s): matched compute;
  - `g4_random`: g4 with construction and inversion off and, in their place at the head, as many random
    g4-language programs as g4 evaluated from them (seeded by task); the geometry tier stays: the same number of head
    candidates without the evidence.
"""
import argparse
import contextlib
import glob
import hashlib
import json
import multiprocessing as mp
import os
import resource
import subprocess
import sys
import time
import zlib
from collections import defaultdict
from unittest import mock

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
OUT = os.path.join(HERE, "outputs", "neural_cora_v2g4", "synthetic_eval")
PROTOCOL = os.path.join("records", "NEURAL_CORA_V2G4_PROTOCOL_20261021.md")
MANIFEST = os.path.join("records", "NEURAL_CORA_V2G4_FREEZE_MANIFEST.json")
SEEDS = tuple(range(1, 11))
BUDGET = 3000
BUDGETS = (300, 1000, 3000)
CPU_CAP_S = 120.0
G3_CPU_BUDGET = 9000
WORKERS, NICE = 2, 10
RETAIN = 50
ARMS_PHASE1 = ("g3", "g4", "g4_no_construct", "g4_no_invert", "g4_parts_only", "g4_rays_only")
ARMS_PHASE2 = ("g3_cpu", "g4_random")
TARGET = ("part", "region", "ray", "mixed")
MAX_ERROR_TASKS = 5
CODE = ["geocat_arc/**/*.py", "cora_neural_v2/*.py", "cora_neural_v2g2/*.py", "cora_neural_v2g3/*.py",
        "cora_neural_v2g4/*.py", "cora_neural_v2g4_eval/*.py", "scripts/neural_cora_v2g4_eval.py"]
# the frozen decision rule (protocol section 6)
GATES = {"target_coverage_gain": 0.30, "target_pass2_gain": 0.25, "compute_attribution": 0.25,
         "candidate_attribution": 0.25, "max_loss_rate": 0.02, "beyond_wrong_increase": 0.10, "trap_top1_gain": 0.20,
         "max_median_cpu_s": 60.0, "max_peak_rss_mb": 4096.0}


def sha_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def code_hashes(root=HERE):
    out = {}
    for pat in CODE:
        for f in sorted(glob.glob(os.path.join(root, pat), recursive=True)):
            if "__pycache__" not in f:
                out[os.path.relpath(f, root)] = sha_file(f)
    return out


# ------------------------------------------------------------------ tasks
def tasks(split="heldout", seeds=SEEDS):
    """([task inputs], [missing ids]). Inputs only: demonstrations and test inputs, never the expected output."""
    from cora_neural_v2g4_eval import families_v4 as F4
    out, missing = [], []
    for name in F4.names(split):
        for s in seeds:
            made = F4.make_task(name, s)
            if made is None:
                missing.append(f"{F4.VERSION}:{name}#{s}")
                continue
            t, _ = made
            out.append({"task_id": t["task_id"], "family": name, "group": t["group"], "seed": s, "train": t["train"],
                        "test_inputs": t["test_inputs"]})
    return out, missing


def tasks_sha(ts):
    return hashlib.sha256(json.dumps([[t["task_id"], t["train"], t["test_inputs"]] for t in ts]).encode()).hexdigest()


def _grid_key(train, tests):
    return hashlib.sha256(json.dumps([train, tests]).encode()).hexdigest()


def prepare(a=None):
    """Writes the DEV and HELDOUT inputs and the yields; for native families g4 can express, the parity of g4's
    executor with native CORA on the generated pairs. Generation-side only: no solver runs."""
    from cora_neural_v2g4_eval import families_v4 as F4
    os.makedirs(OUT, exist_ok=True)
    report = {"version": F4.VERSION, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "splits": {}}
    for split in ("dev", "heldout"):
        seeds = (1, 2, 3) if split == "dev" else SEEDS
        ts, missing = tasks(split, seeds)
        fam = defaultdict(lambda: {"tasks": 0, "missing": 0})
        for t in ts:
            fam[t["family"]]["tasks"] += 1
        for m in missing:
            fam[m.split(":", 1)[1].split("#")[0]]["missing"] += 1
        par = {}
        for name in F4.PARITY:
            if F4.FAMILIES[name][0] == split:
                res = [F4.parity(name, *F4.make_task(name, t["seed"])) for t in ts if t["family"] == name]
                par[name] = {"reproduced": sum(bool(x) for x in res), "of": len(res)}
        report["splits"][split] = {"n_tasks": len(ts), "missing": missing, "tasks_sha256": tasks_sha(ts),
                                   "per_family": {k: dict(v, group=F4.FAMILIES[k][1]) for k, v in sorted(fam.items())},
                                   "g4_native_parity": par}
        json.dump(ts, open(os.path.join(OUT, f"syn_v4_{split}_inputs.json"), "w"))
    json.dump(report, open(os.path.join(OUT, "prepare_report.json"), "w"), indent=1)
    for split, r in report["splits"].items():
        print(split, r["n_tasks"], "tasks;", len(r["missing"]), "missing;", r["tasks_sha256"][:16], "parity:", r["g4_native_parity"])
    return report


def overlap(ts):
    """Grid-hash overlap with every ncv2-g2 family task and every syn-v3 task (DEV and HELDOUT), seeds 1-20."""
    from cora_neural_v2g2 import families as F2
    from cora_neural_v2g3 import families_v3 as V
    old = set()
    for name in F2.FAMILIES:
        for s in range(1, 21):
            made = F2.make_task(name, s)
            if made is not None:
                old.add(_grid_key(made[0]["train"], made[0]["test_inputs"]))
    n_g2 = sum(_grid_key(t["train"], t["test_inputs"]) in old for t in ts)
    old3 = set()
    for name in V.FAMILIES:
        for s in range(1, 21):
            made = V.make_task(name, s)
            if made is not None:
                old3.add(_grid_key(made[0]["train"], made[0]["test_inputs"]))
    return {"ncv2_g2_pool": n_g2, "syn_v3_pool": sum(_grid_key(t["train"], t["test_inputs"]) in old3 for t in ts),
            "pool_sizes": {"ncv2_g2": len(old), "syn_v3": len(old3)}}


def _git(*args):
    return subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True)


def freeze(a=None):
    ts, missing = tasks()
    dirty = _git("status", "--porcelain", "--", PROTOCOL, "cora_neural_v2g4", "cora_neural_v2g4_eval",
                 "scripts/neural_cora_v2g4_eval.py", "cora_neural_v2", "cora_neural_v2g2", "cora_neural_v2g3",
                 "geocat_arc").stdout.strip()
    if dirty:
        sys.exit(f"freeze refused: commit the protocol and code first:\n{dirty}")
    prep = os.path.join(OUT, "syn_v4_heldout_inputs.json")
    prepared_sha = tasks_sha(json.load(open(prep))) if os.path.exists(prep) else None
    ov = overlap(ts)
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "code_commit": _git("rev-parse", "HEAD").stdout.strip(), "code": code_hashes(),
           "protocol_sha256": sha_file(os.path.join(HERE, PROTOCOL)), "n_tasks": len(ts), "missing": missing,
           "per_family": {f: sum(t["family"] == f for t in ts) for f in sorted({t["family"] for t in ts})},
           "tasks_sha256": tasks_sha(ts), "prepared_tasks_sha256": prepared_sha,
           "overlap": ov,
           "settings": {"seeds": list(SEEDS), "budget": BUDGET, "budgets": list(BUDGETS), "cpu_cap_s": CPU_CAP_S,
                        "g3_cpu_budget": G3_CPU_BUDGET, "workers": WORKERS, "nice": NICE, "retain": RETAIN,
                        "arms_phase1": list(ARMS_PHASE1), "arms_phase2": list(ARMS_PHASE2), "target_groups": list(TARGET),
                        "gates": GATES, "max_error_tasks": MAX_ERROR_TASKS}}
    if ov["ncv2_g2_pool"] or ov["syn_v3_pool"]:
        sys.exit(f"freeze refused: overlap {ov}")
    if prepared_sha is not None and prepared_sha != man["tasks_sha256"]:
        sys.exit("freeze refused: regenerated tasks differ from the prepared inputs (non-deterministic generator)")
    json.dump(man, open(os.path.join(HERE, MANIFEST), "w"), indent=1)
    print("frozen:", man["n_tasks"], "tasks;", man["tasks_sha256"][:16], "missing:", len(missing), "overlap:", man["overlap"])
    return man


def lock_problems(root=HERE, man=None, check_tasks=True):
    """[problem]: code, protocol or tasks that differ from the freeze manifest (empty when the lock holds)."""
    man = man if man is not None else json.load(open(os.path.join(root, MANIFEST)))
    probs = []
    now = code_hashes(root)
    for f in sorted(set(man["code"]) | set(now)):
        if man["code"].get(f) != now.get(f):
            probs.append(f"code differs: {f}")
    if man["protocol_sha256"] != sha_file(os.path.join(root, PROTOCOL)):
        probs.append(f"protocol differs: {PROTOCOL}")
    if check_tasks and tasks_sha(tasks()[0]) != man["tasks_sha256"]:
        probs.append("tasks differ from the manifest")
    return probs


def check_lock():
    probs = lock_problems()
    for f in (PROTOCOL, MANIFEST):
        if _git("diff", "--quiet", "HEAD", "--", f).returncode or _git("ls-files", "--error-unmatch", f).returncode:
            probs.append(f"{f} is not committed unchanged")
    if probs:
        sys.exit("locked: " + "; ".join(probs))
    return {"manifest_sha256": sha_file(os.path.join(HERE, MANIFEST)), "git_head": _git("rev-parse", "HEAD").stdout.strip()}


# ------------------------------------------------------------------ arms (solver side: inputs only)
KEEP = ("predictions", "pred_at", "attempts", "attempts_by_test", "attempts_found", "attempt_programs", "programs",
        "first_fit_at", "n_candidates", "n_consistent", "n_distinct_predictions", "head", "fit_origins", "selection",
        "origins", "cpu_s")


def _pick(r):
    return {k: r[k] for k in KEEP if k in r}


def _clear_caches():
    from cora_neural_v2g4 import invert as INV
    from cora_neural_v2g4 import program as PG
    PG._picks.cache_clear()
    PG._objects.cache_clear()
    INV._EXISTS_CACHE.clear()


def random_head(task, n, seed):
    """n distinct random g4-language programs (1 or 2 part or ray rules over the task's own selector vocabulary,
    random kinds, direction sets, stops and colours), deterministic in `seed`."""
    from cora_neural_v2 import search as G1S
    from cora_neural_v2g4 import construct as C
    from cora_neural_v2g4 import invert as INV
    from cora_neural_v2g4 import parts as PT
    from cora_neural_v2g4 import program as PG
    rng = np.random.default_rng(seed)
    views = G1S.distinct_views(task)
    vocab, out, seen = {}, [], set()
    for _ in range(50 * max(n, 1)):
        if len(out) >= n:
            break
        v = views[int(rng.integers(len(views)))]
        if v not in vocab:
            vocab[v] = [INV.TRUE] + list(INV.single_tests(INV.feature_tables(task["train"], v)))
        rules = []
        for _ in range(1 + int(rng.random() < 0.3)):
            sel = vocab[v][int(rng.integers(len(vocab[v])))]
            colour = "own" if rng.random() < 0.15 else int(rng.integers(0, 10))
            if rng.random() < 0.5:
                rules.append(PG.PartRule(sel, PT.KINDS[int(rng.integers(len(PT.KINDS)))], colour))
            else:
                rules.append(PG.RayRule(sel, C.DIR_SETS[int(rng.integers(len(C.DIR_SETS)))], C.STOPS[int(rng.integers(2))], colour))
        p = PG.make(v, None, rules)
        if p not in seen:
            seen.add(p)
            out.append((p, "g4_random"))
    return out


def _only(kind_cls):
    from cora_neural_v2g4 import construct as C
    from cora_neural_v2g4 import invert as INV
    orig = C.shapes

    def shapes(demos):
        return [s for s in orig(demos) if isinstance(s[2](INV.TRUE), kind_cls)]
    return shapes


def run_arm(task, arm, budget=None, cpu_cap_s=None, paired=None):
    """One arm on one task's inputs ({"task_id", "train", "test_inputs"}); returns the kept record. Defaults are the
    module settings at call time (BUDGET, CPU_CAP_S)."""
    budget = BUDGET if budget is None else budget
    cpu_cap_s = CPU_CAP_S if cpu_cap_s is None else cpu_cap_s
    from cora_neural_v2g3 import search as S3
    from cora_neural_v2g4 import construct as C
    from cora_neural_v2g4 import invert as INV
    from cora_neural_v2g4 import program as PG
    from cora_neural_v2g4 import search as S4
    t = {k: task[k] for k in ("task_id", "train", "test_inputs")}
    _clear_caches()
    if arm == "g3":
        return _pick(S3.search(t, budget, cpu_cap_s=cpu_cap_s))
    if arm == "g3_cpu":
        cap = min(cpu_cap_s, max(1.0, float(paired["g4_cpu_s"])))
        return dict(_pick(S3.search(t, budget * G3_CPU_BUDGET // BUDGET, cpu_cap_s=cap)), cpu_cap_used=cap)
    none_programs = lambda task, stats=None: []                     # noqa: E731
    none_invert = lambda task, views=None: []                       # noqa: E731
    patches = {"g4": [],
               "g4_no_construct": [(C, "programs", none_programs)],
               "g4_no_invert": [(INV, "invert", none_invert)],
               "g4_parts_only": [(C, "shapes", _only(PG.PartRule))],
               "g4_rays_only": [(C, "shapes", _only(PG.RayRule))]}
    if arm == "g4_random":
        rand = random_head(t, int(paired["g4_head_evidence_evaluated"]), zlib.crc32(f"random|{task['task_id']}".encode()))
        frozen_head = S4.head                                       # with construction and inversion off: geometry only
        patches["g4_random"] = [(C, "programs", none_programs), (INV, "invert", none_invert),
                                (S4, "head", lambda task: rand + frozen_head(task))]
    with contextlib.ExitStack() as st:
        for target, attr, fn in patches[arm]:
            st.enter_context(mock.patch.object(target, attr, fn))
        r = S4.search(t, budget, cpu_cap_s=cpu_cap_s)
    return _pick(r)


def _job(args):
    task, arm, paired = args
    if os.nice(0) < NICE:
        os.nice(NICE - os.nice(0))
    w0 = time.time()
    row = {"task_id": task["task_id"], "family": task["family"], "group": task["group"], "seed": task["seed"], "arm": arm}
    try:
        row["rec"] = run_arm(task, arm, paired=paired)
    except Exception as e:                                          # noqa: BLE001 (recorded; the stop rule counts it)
        row["error"] = repr(e)[:500]
    row["wall_s"] = round(time.time() - w0, 2)
    row["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    return row


def _rows(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


def _pool(jobs, path):
    err_tasks = {r["task_id"] for r in _rows(path) if "error" in r}
    with mp.get_context("fork").Pool(WORKERS, maxtasksperchild=1) as pool, open(path, "a") as fh:
        for i, row in enumerate(pool.imap_unordered(_job, jobs), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            if "error" in row:
                err_tasks.add(row["task_id"])
            rec = row.get("rec", {})
            print(f"[{i}/{len(jobs)}] {row['task_id']} {row['arm']} fits={rec.get('n_consistent')} "
                  f"cpu={rec.get('cpu_s')} {'ERROR' if 'error' in row else ''}", flush=True)
            if len(err_tasks) > MAX_ERROR_TASKS:
                pool.terminate()
                sys.exit(f"STOPPED: more than {MAX_ERROR_TASKS} tasks raised errors (protocol section 8)")


def run_pool(ts, path):
    done = {(r["task_id"], r["arm"]) for r in _rows(path)}
    _pool([(t, a, None) for t in ts for a in ARMS_PHASE1 if (t["task_id"], a) not in done], path)
    g4 = {r["task_id"]: r["rec"] for r in _rows(path) if r["arm"] == "g4" and "rec" in r}
    done = {(r["task_id"], r["arm"]) for r in _rows(path)}
    jobs = [(t, a, paired_info(g4[t["task_id"]])) for t in ts for a in ARMS_PHASE2 if t["task_id"] in g4 and (t["task_id"], a) not in done]
    _pool(jobs, path)


def paired_info(g4_rec):
    """What the phase-2 arms take from the task's g4 row: its CPU, and how many evidence-driven head programs
    (inversion and construction, before the geometry tier) it evaluated."""
    h = g4_rec["head"]
    return {"g4_cpu_s": g4_rec["cpu_s"],
            "g4_head_evidence_evaluated": min(h["evaluated"], h["by_origin"]["g4_invert"] + h["by_origin"]["g4_construct"])}


def solve(a):
    lock = check_lock() if a.authorized else sys.exit("solve needs --authorized (see the protocol)")
    os.makedirs(OUT, exist_ok=True)
    json.dump({"lock": lock, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
              open(os.path.join(OUT, "run_manifest.json"), "w"), indent=1)
    run_pool(tasks()[0], os.path.join(OUT, "rows.jsonl"))
    print("SOLVE_DONE", flush=True)


# ------------------------------------------------------------------ evaluator side
def _eq(p, A):
    return p is not None and np.asarray(p).shape == A.shape and np.array_equal(np.asarray(p), A)


def task_metrics(rec, A, alt, arm):
    preds = list(zip(rec.get("predictions", []), rec.get("pred_at", [])))
    att = rec.get("attempts", [])[:2]
    found = rec.get("attempts_found", [])[:2]
    m = {f"coverage@{B}": any(_eq(p, A) for p, at in preds if at <= B) for B in BUDGETS}
    m["coverage_full"] = any(_eq(p, A) for p, _ in preds)
    m["pass2"] = any(_eq(p, A) for p in att)
    m["top1"] = bool(att) and _eq(att[0], A)
    m["wrong"] = bool(att) and not m["pass2"]
    m["find_pass2"] = any(_eq(p, A) for p in found)
    m["both_readings"] = alt is not None and m["pass2"] and any(_eq(p, alt) for p in att)
    m["saturated"] = len(preds) >= RETAIN
    m["cpu_s"] = rec.get("cpu_s")
    if arm.startswith("g4"):
        h = rec.get("head", {})
        m["construct_native_runs"] = h.get("construct_native_runs", 0) + h.get("loo_native_runs", 0)
    return m


def score_rows(rows, answer_of, alt_of):
    from cora_neural_v2g4_eval import families_v4 as F4
    arms = ARMS_PHASE1 + ARMS_PHASE2
    by_task = defaultdict(dict)
    meta = {}
    errors = defaultdict(list)
    for r in rows:
        meta[r["task_id"]] = r
        if "error" in r:
            errors[r["arm"]].append(r["task_id"])
            continue
        by_task[r["task_id"]][r["arm"]] = r
    per = []
    for tid, arm_rows in sorted(by_task.items()):
        r0 = meta[tid]
        A, alt = answer_of(r0), alt_of(r0)
        rec = {"task_id": tid, "family": r0["family"], "group": r0["group"], "arms": {}}
        for arm, row in arm_rows.items():
            rec["arms"][arm] = dict(task_metrics(row["rec"], A, alt, arm), peak_rss_mb=row["peak_rss_mb"])
        per.append(rec)

    def rate(xs, arm, k):
        v = [x["arms"][arm][k] for x in xs if arm in x["arms"]]
        return round(sum(bool(y) for y in v) / len(v), 4) if v else None

    def med(xs, arm, k):
        v = [x["arms"][arm][k] for x in xs if arm in x["arms"] and x["arms"][arm].get(k) is not None]
        return float(np.median(v)) if v else None
    metrics = [f"coverage@{B}" for B in BUDGETS] + ["coverage_full", "pass2", "top1", "wrong", "find_pass2",
                                                   "both_readings", "saturated"]
    groups = defaultdict(list)
    for p in per:
        groups[p["group"]].append(p)
    target = [p for p in per if p["group"] in TARGET]
    summ = {"n": len(per), "n_target": len(target), "decision_budget": BUDGET,
            "errors": {a: len(v) for a, v in errors.items()}, "per_group": {}, "per_family": {}}
    for g, xs in sorted(groups.items()):
        summ["per_group"][g] = {"n": len(xs), **{a: {k: rate(xs, a, k) for k in metrics} for a in arms}}
    fams = defaultdict(list)
    for p in per:
        fams[p["family"]].append(p)
    for f, xs in sorted(fams.items()):
        summ["per_family"][f] = {"n": len(xs), **{a: {k: rate(xs, a, k) for k in ("coverage@3000", "pass2")} for a in arms}}
    summ["target"] = {a: {k: rate(target, a, k) for k in metrics} for a in arms}
    summ["pooled"] = {a: {k: rate(per, a, k) for k in metrics} for a in arms}
    both = [p for p in per if "g3" in p["arms"] and "g4" in p["arms"]]
    summ["paired_gains"] = sum(p["arms"]["g4"]["pass2"] and not p["arms"]["g3"]["pass2"] for p in both)
    summ["paired_losses"] = sum(p["arms"]["g3"]["pass2"] and not p["arms"]["g4"]["pass2"] for p in both)
    summ["selection_gains_vs_find"] = sum(p["arms"]["g4"]["pass2"] and not p["arms"]["g4"]["find_pass2"] for p in both)
    summ["selection_losses_vs_find"] = sum(p["arms"]["g4"]["find_pass2"] and not p["arms"]["g4"]["pass2"] for p in both)
    summ["cpu_s"] = {a: {"median": med(per, a, "cpu_s"),
                         "p95": float(np.percentile([x["arms"][a]["cpu_s"] for x in per if a in x["arms"]], 95))
                         if any(a in x["arms"] for x in per) else None} for a in arms}
    summ["construct_native_runs_median"] = {a: med(per, a, "construct_native_runs") for a in arms if a.startswith("g4")}
    summ["peak_rss_mb_max"] = {a: max((x["arms"][a]["peak_rss_mb"] for x in per if a in x["arms"]), default=None) for a in arms}
    summ["saturated_tasks"] = {a: sum(bool(x["arms"][a]["saturated"]) for x in per if a in x["arms"]) for a in arms}
    tg, pg = summ["target"], summ["per_group"]

    def diff(d, a, b, k):
        return None if d[a][k] is None or d[b][k] is None else d[a][k] - d[b][k]

    def ge(x, thr):
        return x is not None and x >= thr
    trap = pg.get("trap")
    beyond = pg.get("beyond")
    ctrl = pg.get("control")
    crit = {
        "G1_target_coverage": ge(diff(tg, "g4", "g3", "coverage@3000"), GATES["target_coverage_gain"]),
        "G2_target_pass2": ge(diff(tg, "g4", "g3", "pass2"), GATES["target_pass2_gain"]),
        "G3_compute_attribution": tg["g4"]["coverage@3000"] is not None and tg["g3_cpu"]["coverage_full"] is not None and
        tg["g4"]["coverage@3000"] - tg["g3_cpu"]["coverage_full"] >= GATES["compute_attribution"],
        "G4_candidate_attribution": ge(diff(tg, "g4", "g4_random", "coverage@3000"), GATES["candidate_attribution"]),
        "G5_losses": bool(per) and summ["paired_losses"] <= GATES["max_loss_rate"] * len(per),
        "G6_control_no_regression": ctrl is not None and ctrl["g4"]["pass2"] is not None and ctrl["g3"]["pass2"] is not None
        and ctrl["g4"]["pass2"] >= ctrl["g3"]["pass2"],
        "G7_beyond_false_fits": beyond is not None and diff(beyond, "g4", "g3", "wrong") is not None and
        diff(beyond, "g4", "g3", "wrong") <= GATES["beyond_wrong_increase"],
        "G8_trap_top1": trap is not None and ge(diff(trap, "g4", "g3", "top1"), GATES["trap_top1_gain"]),
        "G9_resources": summ["cpu_s"]["g4"]["median"] is not None and summ["cpu_s"]["g4"]["median"] <= GATES["max_median_cpu_s"]
        and summ["peak_rss_mb_max"]["g4"] is not None and summ["peak_rss_mb_max"]["g4"] <= GATES["max_peak_rss_mb"]}
    summ["criteria"] = crit
    if not (crit["G1_target_coverage"] and crit["G2_target_pass2"]):
        dec = "NO_GAIN"
    elif not all(crit[k] for k in ("G5_losses", "G6_control_no_regression", "G7_beyond_false_fits", "G9_resources")):
        dec = "NO_GO_REGRESSION"
    elif not (crit["G3_compute_attribution"] and crit["G4_candidate_attribution"]):
        dec = "GAIN_NOT_ATTRIBUTED"
    elif not crit["G8_trap_top1"]:
        dec = "SELECTION_GAP"
    else:
        dec = "GO_ENGINEERING"
    summ["decision"] = dec
    summ["version"] = F4.VERSION
    return {"summary": summ, "tasks": per}


def _answer(r):
    from cora_neural_v2g4_eval import families_v4 as F4
    return F4.make_task(r["family"], r["seed"])[1]


def _alt(r):
    from cora_neural_v2g4_eval import families_v4 as F4
    alt = F4.alternative(r["family"])
    if alt is None:
        return None
    task, _ = F4.make_task(r["family"], r["seed"])
    return F4.run("g4", alt, task["test_inputs"][0])


def score(a, path=None, out=None):
    rows = _rows(path or os.path.join(OUT, "rows.jsonl"))
    res = score_rows(rows, _answer, _alt)
    json.dump(res, open(out or os.path.join(OUT, "score.json"), "w"), indent=1)
    s = res["summary"]
    print(json.dumps({k: s[k] for k in ("n", "n_target", "errors", "target", "paired_gains", "paired_losses",
                                        "criteria", "decision")}, indent=1))
    return res


def selftest(a):
    """DEV families, seeds 1-2, every arm at small budgets; engineering only, never a result."""
    global BUDGET, BUDGETS, G3_CPU_BUDGET
    import tempfile
    d = a.out or tempfile.mkdtemp(prefix="g4x_selftest_")
    os.makedirs(d, exist_ok=True)
    BUDGET, BUDGETS, G3_CPU_BUDGET = 300, (60, 150, 300), 900
    rows_path = os.path.join(d, "rows.jsonl")
    ts, missing = tasks("dev", (1, 2))
    run_pool(ts, rows_path)
    res = score(a, rows_path, os.path.join(d, "score.json"))
    n_rows = len(_rows(rows_path))
    ok = res["summary"]["n"] == len(ts) and n_rows == len(ts) * (len(ARMS_PHASE1) + len(ARMS_PHASE2)) and not missing
    print("SELFTEST", "PASS" if ok else "FAIL", d, flush=True)
    sys.exit(0 if ok else 1)


def lockcheck(a):
    lock = check_lock()
    print("LOCK OK", json.dumps(lock))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("prepare", "freeze", "lockcheck", "selftest", "solve", "score"))
    ap.add_argument("--authorized", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    {"prepare": prepare, "freeze": freeze, "lockcheck": lockcheck, "selftest": selftest, "solve": solve,
     "score": score}[args.stage](args)
