"""The ncv2-g3 synthetic mechanism study on syn-v3 HELDOUT families: ncv2-g2 (frozen) against ncv2-g3.
Protocol: records/NEURAL_CORA_V2G3_SYNTHETIC_PROTOCOL_20261021.md. NOT RUN until that protocol is committed unchanged
and the user authorizes the run.

    python scripts/neural_cora_v2g3_synthetic_eval.py freeze              # code hashes, HELDOUT task hashes, overlap check
    python scripts/neural_cora_v2g3_synthetic_eval.py selftest            # DEV families only, small budget (engineering)
    python scripts/neural_cora_v2g3_synthetic_eval.py solve --authorized  # HELDOUT: demonstrations + test inputs only
    python scripts/neural_cora_v2g3_synthetic_eval.py score               # evaluator: regenerates answers from (family, seed)

**Arms** (paired: same tasks, same 3000-candidate budget, same 120 s CPU cap):
- `g2`: `cora_neural_v2g2.search.search`, byte-identical to the GO_ENGINEERING version (checked at freeze);
- `g3_find`: ncv2-g3 (joint + g2 streams), the first two distinct fits in find order: construction alone;
- `g3`: the same run, the selection module's attempts: construction + selection;
- `g3_g2stream`: ncv2-g3 with `use_joint=False`, selected attempts: selection alone on the g2 candidate stream.
The solve stage sees only demonstrations and test inputs. Only the score stage regenerates answers and reads the
families' alternative programs.
"""
import argparse
import glob
import hashlib
import json
import multiprocessing as mp
import os
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
OUT = os.path.join(HERE, "outputs", "neural_cora_v2g3", "synthetic_eval")
PROTOCOL = os.path.join("records", "NEURAL_CORA_V2G3_SYNTHETIC_PROTOCOL_20261021.md")
MANIFEST = os.path.join("records", "NEURAL_CORA_V2G3_SYNTHETIC_FREEZE_MANIFEST.json")
G2_MANIFEST = os.path.join("records", "NEURAL_CORA_V2G2_SYNTHETIC_FREEZE_MANIFEST.json")
SEEDS = tuple(range(1, 21))
BUDGETS = (300, 1000, 3000)
CPU_CAP_S = 120.0
WORKERS, NICE = 2, 10
CODE = ["cora_neural_v2/*.py", "cora_neural_v2g2/*.py", "cora_neural_v2g3/*.py", "scripts/neural_cora_v2g3_synthetic_eval.py"]
# the frozen decision rule (protocol section 5)
GATES = {"pooled_pass2_gain": 0.15, "composition_coverage_gain": 0.25, "trap_top1_gain": 0.20, "max_loss_rate": 0.02,
         "max_median_cpu_s": 60.0, "max_peak_rss_mb": 4096.0}


def sha(p):
    return hashlib.sha256(open(os.path.join(HERE, p), "rb").read()).hexdigest()


def code_hashes():
    return {os.path.relpath(f, HERE): sha(os.path.relpath(f, HERE)) for pat in CODE
            for f in sorted(glob.glob(os.path.join(HERE, pat)))}


def tasks(split="heldout", seeds=SEEDS):
    from cora_neural_v2g3 import families_v3 as V
    out, missing = [], []
    for name in V.names(split):
        for s in seeds:
            made = V.make_task(name, s)
            if made is None:
                missing.append(f"{name}#{s}")
                continue
            t, _ = made
            out.append({"task_id": t["task_id"], "family": name, "group": t["group"], "seed": s, "train": t["train"],
                        "test_inputs": t["test_inputs"]})
    return out, missing


def _grid_key(t):
    return hashlib.sha256(json.dumps([t["train"], t["test_inputs"]]).encode()).hexdigest()


def overlap_with_g2_pool(ts):
    """Hash overlap with every ncv2-g2 family task (DEV and the spent HELDOUT), seeds 1-20."""
    from cora_neural_v2g2 import families as F2
    old = set()
    for name in F2.FAMILIES:
        for s in SEEDS:
            made = F2.make_task(name, s)
            if made is not None:
                old.add(_grid_key(made[0]))
    return sum(_grid_key(t) in old for t in ts)


def freeze():
    ts, missing = tasks()
    g2_now = {k: v for k, v in code_hashes().items() if k.startswith("cora_neural_v2g2/") or k.startswith("cora_neural_v2/")}
    g2_then = {k: v for k, v in json.load(open(os.path.join(HERE, G2_MANIFEST)))["code"].items()
               if k.startswith("cora_neural_v2g2/") or k.startswith("cora_neural_v2/")}
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "code": code_hashes(),
           "protocol_sha256": sha(PROTOCOL), "n_tasks": len(ts), "missing": missing,
           "tasks_sha256": hashlib.sha256(json.dumps([[t["task_id"], t["train"], t["test_inputs"]] for t in ts]).encode()).hexdigest(),
           "g2_byte_identical_to_go_version": g2_now == g2_then, "overlap_with_g2_pool": overlap_with_g2_pool(ts),
           "settings": {"seeds": list(SEEDS), "budgets": list(BUDGETS), "cpu_cap_s": CPU_CAP_S, "workers": WORKERS,
                        "nice": NICE, "gates": GATES}}
    if not man["g2_byte_identical_to_go_version"] or man["overlap_with_g2_pool"]:
        sys.exit(f"freeze refused: g2 identical={man['g2_byte_identical_to_go_version']}, overlap={man['overlap_with_g2_pool']}")
    json.dump(man, open(os.path.join(HERE, MANIFEST), "w"), indent=1)
    print("frozen:", man["n_tasks"], "tasks;", man["tasks_sha256"][:16], "missing:", len(missing))


def check_lock():
    man = json.load(open(os.path.join(HERE, MANIFEST)))
    if man["code"] != code_hashes() or man["protocol_sha256"] != sha(PROTOCOL):
        sys.exit("locked: code or protocol differ from the freeze manifest")
    for f in (PROTOCOL, MANIFEST):
        if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", f], cwd=HERE).returncode or \
                subprocess.run(["git", "ls-files", "--error-unmatch", f], cwd=HERE, capture_output=True).returncode:
            sys.exit(f"locked: {f} is not committed unchanged")
    return {"manifest_sha256": sha(MANIFEST),
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()}


KEEP = ("predictions", "pred_at", "attempts", "attempts_by_test", "n_candidates", "n_consistent", "first_fit_at", "cpu_s", "state")


def _job(task):
    if os.nice(0) < NICE:
        os.nice(NICE - os.nice(0))
    from cora_neural_v2g2 import search as S2
    from cora_neural_v2g3 import search as S3
    t = {k: task[k] for k in ("task_id", "train", "test_inputs")}
    budget = max(BUDGETS)
    r2 = S2.search(t, budget, cpu_cap_s=CPU_CAP_S)
    r3 = S3.search(t, budget, cpu_cap_s=CPU_CAP_S)
    r3s = S3.search(t, budget, cpu_cap_s=CPU_CAP_S, use_joint=False)
    pick = lambda r, extra=(): {k: r[k] for k in KEEP + tuple(extra) if k in r}            # noqa: E731
    return {"task_id": task["task_id"], "family": task["family"], "group": task["group"], "seed": task["seed"],
            "g2": pick(r2, ("programs",)),
            "g3": pick(r3, ("attempts_found", "attempt_programs", "origins", "fit_origins", "selection")),
            "g3_g2stream": pick(r3s, ("attempts_found", "attempt_programs", "selection")),
            "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0}


def run_pool(ts, path):
    done = {json.loads(l)["task_id"] for l in open(path)} if os.path.exists(path) else set()
    todo = [t for t in ts if t["task_id"] not in done]
    with mp.get_context("fork").Pool(WORKERS, maxtasksperchild=1) as pool, open(path, "a") as fh:
        for i, row in enumerate(pool.imap_unordered(_job, todo), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {row['task_id']} g2={row['g2']['n_consistent']} g3={row['g3']['n_consistent']}", flush=True)


# ------------------------------------------------------------------ evaluator side
def _eq(p, A):
    return np.asarray(p).shape == A.shape and np.array_equal(np.asarray(p), A)


def score_rows(rows, answer_of, alt_pred_of):
    from collections import defaultdict
    top = max(BUDGETS)
    per = []
    for r in rows:
        A = answer_of(r)
        alt = alt_pred_of(r)
        rec = {"task_id": r["task_id"], "family": r["family"], "group": r["group"], "peak_rss_mb": r["peak_rss_mb"]}
        for arm in ("g2", "g3"):
            for B in BUDGETS:
                preds = [p for p, at in zip(r[arm]["predictions"], r[arm]["pred_at"]) if at <= B]
                rec[f"{arm}_coverage@{B}"] = any(_eq(p, A) for p in preds)
                if arm == "g2" or B == top:
                    att = preds[:2]
                    rec[f"{'g2' if arm == 'g2' else 'g3_find'}_pass2@{B}"] = any(_eq(p, A) for p in att)
            rec[f"{arm}_cpu"] = r[arm]["cpu_s"]
            rec[f"{arm}_first_fit"] = r[arm]["first_fit_at"]
        for arm in ("g3", "g3_g2stream"):
            att = r[arm]["attempts"]
            rec[f"{arm}_pass2"] = any(_eq(p, A) for p in att)
            rec[f"{arm}_top1"] = bool(att) and _eq(att[0], A)
            rec[f"{arm}_wrong"] = bool(att) and not rec[f"{arm}_pass2"]
            rec[f"{arm}_both_readings"] = alt is not None and rec[f"{arm}_pass2"] and any(_eq(p, alt) for p in att)
        g2att = r["g2"]["attempts"]
        rec["g2_pass2"], rec["g2_top1"] = any(_eq(p, A) for p in g2att), bool(g2att) and _eq(g2att[0], A)
        rec["g2_wrong"] = bool(g2att) and not rec["g2_pass2"]
        rec["g2_both_readings"] = alt is not None and rec["g2_pass2"] and any(_eq(p, alt) for p in g2att)
        per.append(rec)
    groups = defaultdict(list)
    for p in per:
        groups[p["group"]].append(p)
    rate = lambda xs, k: (sum(bool(x[k]) for x in xs) / len(xs)) if xs else 0.0            # noqa: E731
    summary = {"n": len(per), "decision_budget": top, "per_group": {}}
    metrics = ["g2_pass2", "g3_pass2", f"g3_find_pass2@{top}", "g3_g2stream_pass2", "g2_top1", "g3_top1", "g2_wrong",
               "g3_wrong", f"g2_coverage@{top}", f"g3_coverage@{top}", "g2_both_readings", "g3_both_readings"] + \
        [f"{a}_coverage@{B}" for a in ("g2", "g3") for B in BUDGETS[:-1]]
    for g, xs in sorted(groups.items()):
        summary["per_group"][g] = {"n": len(xs), **{m: round(rate(xs, m), 4) for m in metrics}}
    summary["pooled"] = {m: round(rate(per, m), 4) for m in metrics}
    summary["paired_gains"] = sum(p["g3_pass2"] and not p["g2_pass2"] for p in per)
    summary["paired_losses"] = sum(p["g2_pass2"] and not p["g3_pass2"] for p in per)
    summary["selection_gains_vs_find"] = sum(p["g3_pass2"] and not p[f"g3_find_pass2@{top}"] for p in per)
    summary["selection_losses_vs_find"] = sum(p[f"g3_find_pass2@{top}"] and not p["g3_pass2"] for p in per)
    cpu3 = [p["g3_cpu"] for p in per]
    summary["cpu_s"] = {a: {"median": float(np.median([p[f"{a}_cpu"] for p in per])) if per else None,
                            "p95": float(np.percentile([p[f"{a}_cpu"] for p in per], 95)) if per else None} for a in ("g2", "g3")}
    summary["peak_rss_mb_max"] = max((p["peak_rss_mb"] for p in per), default=None)
    pg = summary["per_group"]
    crit = {
        "pooled_pass2_gain": summary["pooled"]["g3_pass2"] - summary["pooled"]["g2_pass2"] >= GATES["pooled_pass2_gain"],
        "composition_coverage_gain": "composition" in pg and
        pg["composition"][f"g3_coverage@{top}"] - pg["composition"][f"g2_coverage@{top}"] >= GATES["composition_coverage_gain"],
        "trap_top1_gain": "trap" in pg and pg["trap"]["g3_top1"] - pg["trap"]["g2_top1"] >= GATES["trap_top1_gain"],
        "losses": bool(per) and summary["paired_losses"] <= GATES["max_loss_rate"] * len(per),
        "control_no_regression": "control" in pg and pg["control"]["g3_pass2"] >= pg["control"]["g2_pass2"],
        "cpu": bool(cpu3) and float(np.median(cpu3)) <= GATES["max_median_cpu_s"],
        "memory": summary["peak_rss_mb_max"] is not None and summary["peak_rss_mb_max"] <= GATES["max_peak_rss_mb"]}
    summary["criteria"] = crit
    summary["decision"] = "GO_ENGINEERING" if all(crit.values()) else "NO_GAIN"
    return {"summary": summary, "tasks": per}


def _answer(r):
    from cora_neural_v2g3 import families_v3 as V
    return V.make_task(r["family"], r["seed"])[1]


def _alt_pred(r):
    from cora_neural_v2g2 import grammar as G
    from cora_neural_v2g3 import families_v3 as V
    alt = V.alternative(r["family"])
    if alt is None:
        return None
    task, _ = V.make_task(r["family"], r["seed"])
    return G.execute(alt, task["test_inputs"][0])


def solve(a):
    lock = check_lock() if a.authorized else sys.exit("solve needs --authorized (see the protocol)")
    os.makedirs(OUT, exist_ok=True)
    json.dump({"lock": lock, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
              open(os.path.join(OUT, "run_manifest.json"), "w"), indent=1)
    run_pool(tasks()[0], os.path.join(OUT, "rows.jsonl"))
    print("SOLVE_DONE", flush=True)


def score(a, path=None, out=None):
    rows = [json.loads(l) for l in open(path or os.path.join(OUT, "rows.jsonl"))]
    res = score_rows(rows, _answer, _alt_pred)
    json.dump(res, open(out or os.path.join(OUT, "score.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res["summary"].items() if k != "per_group"}, indent=1))
    return res


def selftest(a):
    """DEV families, seeds 1-2, the full pipeline at small budgets; engineering only, never a result."""
    global BUDGETS
    import tempfile
    d = a.out or tempfile.mkdtemp(prefix="g3x_selftest_")
    os.makedirs(d, exist_ok=True)
    BUDGETS = (100, 300, 600)
    rows_path = os.path.join(d, "rows.jsonl")
    ts, missing = tasks("dev", (1, 2))
    run_pool(ts, rows_path)
    res = score(a, rows_path, os.path.join(d, "score.json"))
    ok = res["summary"]["n"] == len(ts) >= 10 and not missing
    print("SELFTEST", "PASS" if ok else "FAIL", d, flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("freeze", "selftest", "solve", "score"))
    ap.add_argument("--authorized", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    {"freeze": lambda a: freeze(), "selftest": selftest, "solve": solve, "score": score}[args.stage](args)
