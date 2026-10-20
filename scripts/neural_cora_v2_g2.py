"""Neural-CORA v2 G2: the language-ceiling check of ncv2-g1 against ncv1-g0 and native CORA on the EXPOSED dev60.
Engineering evidence about expressivity, not a benchmark and not a generalization claim. The protocol is
records/NEURAL_CORA_V2_G2_PROTOCOL_20261020.md; nothing here may run on dev60 before that file is committed.

    python scripts/neural_cora_v2_g2.py freeze               # tests, then the freeze manifest (code and input hashes)
    python scripts/neural_cora_v2_g2.py selftest             # synthetic tasks only, every stage, in the scratch output dir
    python scripts/neural_cora_v2_g2.py solve --authorized   # solver side: demonstrations and test inputs only
    python scripts/neural_cora_v2_g2.py diag --authorized    # solver side: exhaustive single-rule check, <=20 no-fit tasks
    python scripts/neural_cora_v2_g2.py score                # evaluator side: the only stage that reads answers

Arms:
- g1: `cora_neural_v2.search.search`, the G1-CH order over ncv2-g1, 3000 candidates, capped at 120 CPU seconds.
- g0: the hash-pinned v1 atlas rows (C+H@3000 over ncv1-g0), reused, not rerun.
- native: the hash-pinned native CORA v23 rows and evaluation (outputs/funnel_v0, 13-14 October), reused, not rerun.
  It is a reference row. Its search is far larger than either language arm's.

Only the first test input is scored, as in the g0 atlas.
"""
import argparse
import glob
import hashlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
OUT = os.path.join(HERE, "outputs", "neural_cora_v2", "g2")
PROTOCOL = os.path.join("records", "NEURAL_CORA_V2_G2_PROTOCOL_20261020.md")
MANIFEST = os.path.join("records", "NEURAL_CORA_V2_G2_FREEZE_MANIFEST.json")
BUDGET, SEARCH_CPU_S = 3000, 120.0
DIAG_N, DIAG_CPU_S = 20, 300.0
WORKERS, NICE = 2, 10
CODE = ["cora_neural_v2/*.py", "scripts/neural_cora_v2_g2.py", "tests/test_neural_cora_v2_ast.py",
        "tests/test_neural_cora_v2_search.py"]
INPUTS = {"dev_bundle": "records/pilot_v1/dev_bundle.json",
          "g0_rows": "outputs/neural_cora_v1/atlas/dev60_solve.jsonl",
          "native_rows": "outputs/funnel_v0/rows_dev60_native.jsonl",
          "native_eval": "outputs/funnel_v0/eval_dev60_native.json"}
NATIVE_PATTERN = "geocat_arc/**/*.py"


# ------------------------------------------------------------------ hashing and the freeze lock
def sha(path):
    return hashlib.sha256(open(os.path.join(HERE, path), "rb").read()).hexdigest()


def aggregate(pattern):
    files = sorted(os.path.relpath(f, HERE) for f in glob.glob(os.path.join(HERE, pattern), recursive=True)
                   if "__pycache__" not in f)
    return hashlib.sha256("".join(f"{f}:{sha(f)}\n" for f in files).encode()).hexdigest(), files


def current_hashes():
    code = {f: sha(f) for p in CODE for f in aggregate(p)[1]}
    return {"code": code, "inputs": {k: sha(v) for k, v in INPUTS.items()},
            "native_aggregate_sha256": aggregate(NATIVE_PATTERN)[0], "protocol_sha256": sha(PROTOCOL)}


def freeze():
    r = subprocess.run(["nice", "-n", str(NICE), sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "tests/test_neural_cora_v2_ast.py", "tests/test_neural_cora_v2_search.py"],
                       cwd=HERE, capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode != 0:
        sys.exit(f"not frozen: the G2a tests failed: {last}")
    v1 = json.load(open(os.path.join(HERE, "records", "NEURAL_CORA_V1_FREEZE_MANIFEST.json")))["groups"]
    h = current_hashes()
    if h["native_aggregate_sha256"] != v1["native_cora_v23_geocat_arc"]["aggregate_sha256"]:
        sys.exit("not frozen: native CORA differs from the v1 freeze")
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "g2a_tests": last, **h,
           "settings": {"budget": BUDGET, "search_cpu_s": SEARCH_CPU_S, "diag_n": DIAG_N, "diag_cpu_s": DIAG_CPU_S,
                        "workers": WORKERS, "nice": NICE}}
    json.dump(man, open(os.path.join(HERE, MANIFEST), "w"), indent=1)
    print("frozen:", last)


def check_lock():
    """Refuse a dev60 run unless the protocol and manifest are committed and every hash still matches."""
    man = json.load(open(os.path.join(HERE, MANIFEST)))
    if man["code"] != current_hashes()["code"] or man["inputs"] != current_hashes()["inputs"] or \
            man["protocol_sha256"] != sha(PROTOCOL) or man["native_aggregate_sha256"] != aggregate(NATIVE_PATTERN)[0]:
        sys.exit("locked: code, inputs, protocol or native CORA differ from the freeze manifest")
    for f in (PROTOCOL, MANIFEST):
        if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", f], cwd=HERE).returncode or \
                not subprocess.run(["git", "ls-files", "--error-unmatch", f], cwd=HERE, capture_output=True).returncode == 0:
            sys.exit(f"locked: {f} is not committed unchanged")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    return {"manifest_sha256": sha(MANIFEST), "git_head": head}


# ------------------------------------------------------------------ solver side (no answers anywhere below)
def dev60_tasks():
    from cora_funnel.run import load                                 # strips answers; opaque keys
    return [{"task_id": k, "train": [(p["input"], p["output"]) for p in t["train"]],
             "test_inputs": [t["test"][0]["input"]]} for k, t in load("dev60")]


def _job_solve(task):
    if os.nice(0) < NICE:
        os.nice(NICE - os.nice(0))
    from cora_neural_v2 import search as S
    r = S.search(task, BUDGET, cpu_cap_s=SEARCH_CPU_S)
    return {"task_id": task["task_id"], "result": r, "nice": os.nice(0)}


def _job_diag(task):
    if os.nice(0) < NICE:
        os.nice(NICE - os.nice(0))
    from cora_neural_v2 import search as S
    from cora_neural_v2.rast import to_sexpr
    r = S.exhaustive_single_rule(task, cpu_cap_s=DIAG_CPU_S)
    r["fits"] = [{"program": to_sexpr(f["program"]), "test_pred": f["test_pred"]} for f in r["fits"]]
    r["verdict"] = "SINGLE_RULE_EXISTS" if r["any_fit"] else ("NO_SINGLE_RULE" if r["complete"] else "INCONCLUSIVE")
    return {"task_id": task["task_id"], "result": r, "nice": os.nice(0)}


def run_pool(job, tasks, path, workers=WORKERS):
    done = {json.loads(l)["task_id"] for l in open(path)} if os.path.exists(path) else set()
    todo = [t for t in tasks if t["task_id"] not in done]
    print(f"{os.path.basename(path)}: {len(todo)} to run, {len(done)} done", flush=True)
    with mp.get_context("fork").Pool(workers, maxtasksperchild=1) as pool, open(path, "a") as fh:
        for i, row in enumerate(pool.imap_unordered(job, todo), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            r = row["result"]
            print(f"[{i}/{len(todo)}] {row['task_id']} consistent={r.get('n_consistent', r.get('verdict'))} "
                  f"cpu={r['cpu_s']}s", flush=True)


def diag_tasks(tasks, solve_rows):
    """g1 no-fit tasks in sha256(key) order, the first DIAG_N: a fixed, answer-free choice."""
    nofit = {r["task_id"] for r in solve_rows if r["result"]["n_consistent"] == 0}
    pick = sorted(nofit, key=lambda k: hashlib.sha256(k.encode()).hexdigest())[:DIAG_N]
    return [t for t in tasks if t["task_id"] in set(pick)]


def read_rows(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


# ------------------------------------------------------------------ evaluator side
def eq(p, A):
    P = np.asarray(p)
    return P.shape == A.shape and bool((P == A).all())


def binom_one_sided(k, n):
    """P(X >= k), X ~ Binomial(n, 1/2): the exact sign test on discordant pairs. Descriptive only (dev60 is exposed)."""
    from math import comb
    return sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1.0


def decide(s):
    """The frozen G2b rule (protocol section 4)."""
    g1, pp = s["arms"]["g1"], s["paired_g1_vs_g0"]["pass@2"]
    if g1["pass@2"] <= 1:
        return "NO_GO_STOP"
    if g1["fits"] >= 6 and g1["pass@2"] >= 4 and pp["gains"] >= 3 and pp["losses"] <= 1:
        return "GO"
    return "WEAK_EXPRESSIVITY_ONLY"


def score_rows(g1_rows, g0_rows, native_tasks, answers, diag_rows):
    g0 = {r["task_id"]: r for r in g0_rows}
    nat = {t["key"]: t for t in native_tasks}
    per = []
    for r in sorted(g1_rows, key=lambda x: x["task_id"]):
        k, res = r["task_id"], r["result"]
        A = np.asarray(answers[k])
        g0r = g0[k]["result"]
        first_ok = next((at for p, at in zip(res["predictions"], res["pred_at"]) if eq(p, A)), None)
        n = nat.get(k, {})
        per.append({"task_id": k, "kinds": g0[k]["profile"]["kinds"],
                    "g1": {"fits": res["n_consistent"] > 0, "correct_coverage": first_ok is not None,
                           "pass@2": any(eq(p, A) for p in res["attempts"][:2]), "first_correct_at": first_ok,
                           "n_distinct": res["n_distinct_predictions"], "cpu_truncated": res["state"]["cpu_truncated"],
                           "n_candidates": res["n_candidates"], "cpu_s": res["cpu_s"]},
                    "g0": {"fits": g0r.get("n_consistent", 0) > 0,
                           "correct_coverage": any(eq(p, A) for p in g0r.get("predictions", [])),
                           "pass@2": any(eq(p, A) for p in g0r.get("attempts", [])[:2])},
                    "native": {"fits": n.get("train_exact_candidates", 0) > 0, "correct_coverage": bool(n.get("any_candidate_correct")),
                               "certified_correct": n.get("category") == "CERTIFIED_CORRECT", "category": n.get("category")}})
    arms = {a: {m: sum(p[a][m] for p in per) for m in ("fits", "correct_coverage")} for a in ("g1", "g0", "native")}
    for a in ("g1", "g0"):
        arms[a]["pass@2"] = sum(p[a]["pass@2"] for p in per)
        arms[a]["fits_but_no_correct_candidate"] = sum(p[a]["fits"] and not p[a]["correct_coverage"] for p in per)
    arms["native"]["certified_correct"] = sum(p["native"]["certified_correct"] for p in per)
    paired = {}
    for m in ("fits", "correct_coverage", "pass@2"):
        gains = sorted(p["task_id"] for p in per if p["g1"][m] and not p["g0"][m])
        losses = sorted(p["task_id"] for p in per if p["g0"][m] and not p["g1"][m])
        paired[m] = {"gains": len(gains), "losses": len(losses), "gain_ids": gains, "loss_ids": losses,
                     "sign_test_one_sided_p": round(binom_one_sided(len(gains), len(gains) + len(losses)), 4)}
    by_kind = {}
    for p in per:
        for k in p["kinds"] or ["no_change_detected"]:
            d = by_kind.setdefault(k, {"n": 0, "g0_fits": 0, "g1_fits": 0, "g1_pass@2": 0, "native_fits": 0})
            d["n"] += 1
            d["g0_fits"] += p["g0"]["fits"]
            d["g1_fits"] += p["g1"]["fits"]
            d["g1_pass@2"] += p["g1"]["pass@2"]
            d["native_fits"] += p["native"]["fits"]
    verdicts = {}
    for d in diag_rows:
        verdicts[d["result"]["verdict"]] = verdicts.get(d["result"]["verdict"], 0) + 1
    s = {"n": len(per), "arms": arms, "paired_g1_vs_g0": paired, "by_kind": by_kind,
         "g1_cpu_truncated": sum(p["g1"]["cpu_truncated"] for p in per),
         "g1_cpu_s_total": round(sum(p["g1"]["cpu_s"] for p in per), 1),
         "diag": {"n": len(diag_rows), "verdicts": verdicts,
                  "cpu_s_total": round(sum(d["result"]["cpu_s"] for d in diag_rows), 1)},
         "note": "exposed development tasks: engineering evidence about expressivity, not a benchmark"}
    s["decision_G2b"] = decide(s)
    return {"summary": s, "tasks": per}


# ------------------------------------------------------------------ stages
def solve(a):
    lock = check_lock() if a.authorized else sys.exit("solve on dev60 needs --authorized (see the protocol)")
    os.makedirs(OUT, exist_ok=True)
    json.dump({"lock": lock, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
              open(os.path.join(OUT, "run_manifest_solve.json"), "w"), indent=1)
    run_pool(_job_solve, dev60_tasks(), os.path.join(OUT, "dev60_g1_solve.jsonl"))
    print("SOLVE_DONE", flush=True)


def diag(a):
    lock = check_lock() if a.authorized else sys.exit("diag on dev60 needs --authorized (see the protocol)")
    rows = read_rows(os.path.join(OUT, "dev60_g1_solve.jsonl"))
    if len(rows) != 60:
        sys.exit(f"diag needs the complete solve stage ({len(rows)}/60 rows)")
    json.dump({"lock": lock, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
              open(os.path.join(OUT, "run_manifest_diag.json"), "w"), indent=1)
    run_pool(_job_diag, diag_tasks(dev60_tasks(), rows), os.path.join(OUT, "dev60_g1_diag.jsonl"))
    print("DIAG_DONE", flush=True)


def score(a):
    from cora_funnel.evaluate import answers                         # the evaluator-only, sha-pinned key map
    man = json.load(open(os.path.join(HERE, MANIFEST)))
    if {k: sha(v) for k, v in INPUTS.items()} != man["inputs"]:
        sys.exit("the g0 or native rows, or the dev bundle, differ from the freeze manifest")
    ans = {k: v[0][0] for k, v in answers("dev60").items()}          # the first test output, as the g0 atlas
    out = score_rows(read_rows(os.path.join(OUT, "dev60_g1_solve.jsonl")), read_rows(os.path.join(HERE, INPUTS["g0_rows"])),
                     json.load(open(os.path.join(HERE, INPUTS["native_eval"])))["tasks"], ans,
                     read_rows(os.path.join(OUT, "dev60_g1_diag.jsonl")))
    json.dump(out, open(os.path.join(OUT, "g2_score.json"), "w"), indent=1)
    s = dict(out["summary"])
    s.pop("by_kind")
    print(json.dumps(s, indent=1))


def selftest(a):
    """Every stage on synthetic tasks (CORA's scene generator), with answers held apart, in a scratch directory."""
    import tempfile
    from cora_neural_v1.generator import _scene
    from cora_neural_v2 import bridge as BR
    from cora_neural_v2.rast import parse_sexpr
    global OUT, SEARCH_CPU_S, DIAG_CPU_S, DIAG_N
    OUT = a.out or tempfile.mkdtemp(prefix="g2_selftest_")
    os.makedirs(OUT, exist_ok=True)
    SEARCH_CPU_S, DIAG_CPU_S, DIAG_N = 60.0, 60.0, 2
    P = lambda rules: f"(program S1 (list {rules}) keep (same_as_input))"   # noqa: E731
    srcs = [P("(rule (test color == 1) (recolor (color 4)))"),
            P("(rule (test color == 1) (recolor (color 4))) (rule (test color == 3) (delete))"),
            P("(rule (test color == 2) (copy_offsets (list (vec 0 2))))")]
    tasks, answers, g0_rows, native = [], {}, [], []
    for i, src in enumerate(srcs + ["noise"]):
        rng = np.random.default_rng(71000 + i)
        pairs = []
        while len(pairs) < 4:
            G = _scene(rng, [1, 2, 3, 4, 5])
            if G is None:
                continue
            out = rng.integers(0, 6, G.shape) if src == "noise" else BR.execute(parse_sexpr(src), G)
            if out is not None and not np.array_equal(out, G):
                pairs.append((G.tolist(), np.asarray(out).tolist()))
        k = f"syn{i}"
        tasks.append({"task_id": k, "train": pairs[:3], "test_inputs": [pairs[3][0]]})
        answers[k] = pairs[3][1]
        g0_rows.append({"task_id": k, "profile": {"kinds": ["synthetic"]}, "result": {"n_consistent": 0, "predictions": [], "attempts": []}})
        native.append({"key": k, "category": "NO_FIT_EXHAUSTED", "train_exact_candidates": 0, "any_candidate_correct": False})
    sp, dp = os.path.join(OUT, "solve.jsonl"), os.path.join(OUT, "diag.jsonl")
    run_pool(_job_solve, tasks, sp)
    rows = read_rows(sp)
    run_pool(_job_diag, diag_tasks(tasks, rows), dp)
    res = score_rows(rows, g0_rows, native, answers, read_rows(dp))
    json.dump(res, open(os.path.join(OUT, "score.json"), "w"), indent=1)
    s = res["summary"]
    print(json.dumps({k: s[k] for k in ("arms", "diag", "decision_G2b", "g1_cpu_truncated")}, indent=1))
    ok = s["arms"]["g1"]["pass@2"] >= 2 and s["diag"]["n"] >= 1 and all(r["nice"] >= NICE for r in rows)
    print("SELFTEST", "PASS" if ok else "FAIL", OUT, flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("freeze", "selftest", "solve", "diag", "score"))
    ap.add_argument("--authorized", action="store_true", help="the user authorized the dev60 G2 run")
    ap.add_argument("--out", default="", help="selftest output directory")
    args = ap.parse_args()
    {"freeze": lambda a: freeze(), "selftest": selftest, "solve": solve, "diag": diag, "score": score}[args.stage](args)
