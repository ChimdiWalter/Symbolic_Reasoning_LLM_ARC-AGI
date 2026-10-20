"""The ncv2-g2 synthetic coverage study: ncv2-g1 search vs ncv2-g2 search on HELDOUT synthetic semantic families.
Protocol: records/NEURAL_CORA_V2G2_SYNTHETIC_PROTOCOL_20261020.md. Not run until that protocol is committed and the user
authorizes it.

    python scripts/neural_cora_v2g2_synthetic_eval.py freeze              # writes the freeze manifest (code hashes, tasks)
    python scripts/neural_cora_v2g2_synthetic_eval.py selftest            # DEV families only, 1 seed, small budget
    python scripts/neural_cora_v2g2_synthetic_eval.py solve --authorized  # HELDOUT tasks: demonstrations + test inputs only
    python scripts/neural_cora_v2g2_synthetic_eval.py score               # evaluator: regenerates answers from (family, seed)

The solve stage gets only `task` dicts: demonstrations and test inputs. The score stage alone regenerates each test
output and reads each family's generating program, for the generator-coverage check.
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
OUT = os.path.join(HERE, "outputs", "neural_cora_v2g2", "synthetic_eval")
PROTOCOL = os.path.join("records", "NEURAL_CORA_V2G2_SYNTHETIC_PROTOCOL_20261020.md")
MANIFEST = os.path.join("records", "NEURAL_CORA_V2G2_SYNTHETIC_FREEZE_MANIFEST.json")
SEEDS = tuple(range(1, 21))
BUDGETS = (1000, 3000)
CPU_CAP_S = 120.0
WORKERS, NICE = 2, 10
CODE = ["cora_neural_v2/*.py", "cora_neural_v2g2/*.py", "scripts/neural_cora_v2g2_synthetic_eval.py"]


def sha(p):
    return hashlib.sha256(open(os.path.join(HERE, p), "rb").read()).hexdigest()


def code_hashes():
    return {os.path.relpath(f, HERE): sha(os.path.relpath(f, HERE)) for pat in CODE
            for f in sorted(glob.glob(os.path.join(HERE, pat)))}


def heldout_tasks(split="heldout", seeds=SEEDS):
    from cora_neural_v2g2 import families as F
    out = []
    for name in F.names(split):
        for s in seeds:
            made = F.make_task(name, s)
            if made is not None:
                task, _ = made
                out.append({"task_id": task["task_id"], "family": name, "seed": s, "train": task["train"],
                            "test_inputs": task["test_inputs"]})
    return out


def freeze():
    tasks = heldout_tasks()
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "code": code_hashes(),
           "protocol_sha256": sha(PROTOCOL), "n_tasks": len(tasks),
           "tasks_sha256": hashlib.sha256(json.dumps([[t["task_id"], t["train"], t["test_inputs"]] for t in tasks]).encode()).hexdigest(),
           "settings": {"seeds": list(SEEDS), "budgets": list(BUDGETS), "cpu_cap_s": CPU_CAP_S, "workers": WORKERS, "nice": NICE}}
    json.dump(man, open(os.path.join(HERE, MANIFEST), "w"), indent=1)
    print("frozen:", man["n_tasks"], "tasks;", man["tasks_sha256"][:16])


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


def _job(task):
    if os.nice(0) < NICE:
        os.nice(NICE - os.nice(0))
    from cora_neural_v2 import search as S1
    from cora_neural_v2g2 import search as S2
    t = {k: task[k] for k in ("task_id", "train", "test_inputs")}
    r1 = S1.search(t, max(BUDGETS), cpu_cap_s=CPU_CAP_S)
    r2 = S2.search(t, max(BUDGETS), cpu_cap_s=CPU_CAP_S)
    keep = ("predictions", "pred_at", "attempts", "n_candidates", "n_consistent", "cpu_s", "state")
    return {"task_id": task["task_id"], "family": task["family"], "seed": task["seed"],
            "g1": {k: r1[k] for k in keep}, "g2": {**{k: r2[k] for k in keep}, "programs": r2["programs"], "first_fit_at": r2["first_fit_at"]}}


def run_pool(tasks, path):
    done = {json.loads(l)["task_id"] for l in open(path)} if os.path.exists(path) else set()
    todo = [t for t in tasks if t["task_id"] not in done]
    with mp.get_context("fork").Pool(WORKERS, maxtasksperchild=1) as pool, open(path, "a") as fh:
        for i, row in enumerate(pool.imap_unordered(_job, todo), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {row['task_id']} g1={row['g1']['n_consistent']} g2={row['g2']['n_consistent']}", flush=True)


def _at_budget(arm, B):
    """Exact truncation: predictions first seen within the first B candidates; attempts = the first two of them."""
    preds = [p for p, at in zip(arm["predictions"], arm["pred_at"]) if at <= B]
    return preds, preds[:2]


def score_rows(rows, answer_of, gen_cover_of):
    from collections import defaultdict
    eq = lambda p, A: np.asarray(p).shape == A.shape and np.array_equal(np.asarray(p), A)   # noqa: E731
    top = max(BUDGETS)                                      # the decision budget (3000 in the frozen study)
    per, fam = [], defaultdict(lambda: defaultdict(int))
    for r in rows:
        A = answer_of(r)
        rec = {"task_id": r["task_id"], "family": r["family"]}
        for arm in ("g1", "g2"):
            for B in BUDGETS:
                preds, att = _at_budget(r[arm], B)
                rec[f"{arm}@{B}"] = {"correct_coverage": any(eq(p, A) for p in preds), "pass@2": any(eq(p, A) for p in att),
                                     "wrong_attempts": bool(att) and not any(eq(p, A) for p in att)}
            rec[f"{arm}_cpu"] = r[arm]["cpu_s"]
        rec["generator_coverage"] = gen_cover_of(r)
        rec["g2_first_fit_at"] = r["g2"]["first_fit_at"]
        per.append(rec)
        for k in (f"g1@{top}", f"g2@{top}"):
            fam[r["family"]][k] += rec[k]["pass@2"]
        fam[r["family"]]["n"] += 1
    n = len(per)
    pooled = {f"{arm}@{B}": {m: sum(p[f"{arm}@{B}"][m] for p in per) for m in ("correct_coverage", "pass@2", "wrong_attempts")}
              for arm in ("g1", "g2") for B in BUDGETS}
    losses = sum(p[f"g1@{top}"]["pass@2"] and not p[f"g2@{top}"]["pass@2"] for p in per)
    gains = sum(p[f"g2@{top}"]["pass@2"] and not p[f"g1@{top}"]["pass@2"] for p in per)
    fam_better = sum(d[f"g2@{top}"] > d[f"g1@{top}"] for d in fam.values())
    med_cpu = {arm: float(np.median([p[f"{arm}_cpu"] for p in per])) if per else None for arm in ("g1", "g2")}
    gc = {arm: sum(p["generator_coverage"][arm] for p in per) for arm in ("g1", "g2")}
    s = {"n": n, "decision_budget": top, "pooled": pooled, "paired_gains_g2_over_g1": gains, "paired_losses": losses,
         "families_g2_better": fam_better, "n_families": len(fam), "median_cpu_s": med_cpu, "generator_coverage": gc,
         "per_family": {k: dict(v) for k, v in fam.items()}}
    d = (pooled[f"g2@{top}"]["pass@2"] - pooled[f"g1@{top}"]["pass@2"]) / n if n else 0.0
    s["decision"] = "GO_ENGINEERING" if (n and d >= 0.20 and fam_better >= 6 and losses <= 0.02 * n
                                        and med_cpu["g2"] is not None and med_cpu["g2"] <= 60.0) else "NO_GAIN"
    return {"summary": s, "tasks": per}


def generator_coverage(row):
    """Evaluator side: is the family's generating program (or an execution-equivalent class form) in each arm's
    candidate set?"""
    from cora_neural_v2 import bridge as G1B
    from cora_neural_v2 import search as G1S
    from cora_neural_v2.constraints import evidence
    from cora_neural_v2.rast import ASTError, N
    from cora_neural_v2g2 import families as F
    from cora_neural_v2g2 import grammar as G
    from cora_neural_v2g2 import search as S2
    task, answer = F.make_task(row["family"], row["seed"])
    prog = G.parse(F.FAMILIES[row["family"]][1])
    out = {}
    try:
        G1B.compile_program(prog)
        ev = evidence(task["train"])
        rules = {repr(N("rule", (s, a))) for s, _, _ in G1S.selectors(ev) for a, _, _ in G1S.actions(ev)}
        out["g1"] = all(repr(r) in rules for r in prog.args[1])
    except ASTError:
        out["g1"] = False                                   # not representable in ncv2-g1 at all
    if G.is_class(prog):
        cands, _ = S2.class_candidates(task)
        out["g2"] = any(G.fit(c, task["train"])[0] and np.array_equal(G.execute(c, task["test_inputs"][0]), answer) for c in cands)
    else:
        ev = S2.evidence2(task["train"])
        rules = {repr(S2.rule_node(s, a)) for s, _, _ in S2.selectors(ev) for a, _, _ in S2.actions(ev, task["train"])}
        out["g2"] = all(repr(r) in rules for r in prog.args[1])
    return out


def solve(a):
    lock = check_lock() if a.authorized else sys.exit("solve needs --authorized (see the protocol)")
    os.makedirs(OUT, exist_ok=True)
    json.dump({"lock": lock, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
              open(os.path.join(OUT, "run_manifest.json"), "w"), indent=1)
    run_pool(heldout_tasks(), os.path.join(OUT, "rows.jsonl"))
    print("SOLVE_DONE", flush=True)


def score(a, path=None, out=None):
    from cora_neural_v2g2 import families as F
    rows = [json.loads(l) for l in open(path or os.path.join(OUT, "rows.jsonl"))]
    res = score_rows(rows, lambda r: F.make_task(r["family"], r["seed"])[1], generator_coverage)
    json.dump(res, open(out or os.path.join(OUT, "score.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res["summary"].items() if k != "per_family"}, indent=1))
    return res


def selftest(a):
    """DEV families, seed 1, the full pipeline; for engineering only."""
    global BUDGETS
    import tempfile
    d = a.out or tempfile.mkdtemp(prefix="g2x_selftest_")
    os.makedirs(d, exist_ok=True)
    BUDGETS = (300, 1000)
    rows_path = os.path.join(d, "rows.jsonl")
    run_pool(heldout_tasks("dev", (1,)), rows_path)
    res = score(a, rows_path, os.path.join(d, "score.json"))
    ok = res["summary"]["n"] >= 8
    print("SELFTEST", "PASS" if ok else "FAIL", d, flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("freeze", "selftest", "solve", "score"))
    ap.add_argument("--authorized", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    {"freeze": lambda a: freeze(), "selftest": selftest, "solve": solve, "score": score}[args.stage](args)
