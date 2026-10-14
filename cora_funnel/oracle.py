"""Evaluator-side expressibility probe (Stage 2). ORACLE: it reads answers, so
it is never a prediction and nothing from it reaches the solver.

  python -m cora_funnel.oracle --corpus dev60 [--categories ...] [--workers 4]
      -> outputs/funnel_v0/rows_<corpus>_oracle.jsonl, oracle_<corpus>.json

For each failed task in the chosen categories (from eval_<corpus>_native.json),
it appends every held-out answer pair as an extra demonstration. The same
frozen native object layer then runs through `cora_funnel.run.job`. The
question: can the native language and search fit all the pairs, the answer
included?
- a fit is found: EXPRESSIBLE_WITHIN_BUDGET. A rule consistent with the
  answer exists in the native space and the search reached it;
- no fit, and the identity search ended before its deadline:
  NO_FIT_WITHIN_BOUNDS. This is NOT a claim that the rule is inexpressible.
  The native search is bounded (variant cap, tier ladder, frames, deadline),
  so a failed bounded search cannot prove that no program exists;
- no fit, and the deadline was hit: UNDETERMINED_BUDGET.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "funnel_v0")
DEFAULT_CATS = "NO_FIT_DEADLINE,NO_FIT_EXHAUSTED,FIT_BUT_ALL_WRONG,REJECTED_BUT_CORRECT"


def verdict(row):
    sets = [e for e in row["events"] if e["type"] in ("search", "generative") and e["n_programs"] > 0]
    if sets:
        return "EXPRESSIBLE_WITHIN_BUDGET"
    first = next((e for e in row["events"] if e["type"] == "search" and e["frame"] == 0), None)
    return "UNDETERMINED_BUDGET" if (first is None or first["deadline_hit"]) else "NO_FIT_WITHIN_BOUNDS"


def main(argv=None):
    from cora_funnel import evaluate, run
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--categories", default=DEFAULT_CATS)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--keys", default="", help="comma-separated subset")
    ap.add_argument("--tag", default="", help="suffix for the rows and result files (replicates)")
    a = ap.parse_args(argv)
    cats = set(a.categories.split(","))
    ev = json.load(open(os.path.join(OUT, f"eval_{a.corpus}_native.json")))
    cat_of = {t["key"]: t["category"] for t in ev["tasks"]}
    tasks, ans = dict(run.load(a.corpus)), evaluate.answers(a.corpus)
    path = os.path.join(OUT, f"rows_{a.corpus}_oracle{a.tag}.jsonl")
    want = set(a.keys.split(",")) if a.keys else None
    done = {json.loads(l)["key"] for l in open(path)} if os.path.exists(path) else set()
    todo = []
    for k in sorted(k for k, c in cat_of.items() if c in cats and k not in done and (want is None or k in want)):
        t = tasks[k]
        aug = {"train": t["train"] + [{"input": p["input"], "output": o} for p, o in zip(t["test"], ans[k][0])], "test": t["test"]}
        todo.append((k, aug, a.corpus + "_oracle" + a.tag, "native"))
    print(f"oracle {a.corpus}: {len(todo)} to run", flush=True)
    with mp.get_context("fork").Pool(a.workers, maxtasksperchild=1) as pool, open(path, "a") as fh:
        for i, row in enumerate(pool.imap_unordered(run.job, todo), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {row['key']} {verdict(row)} wall={row['wall_s']}s", flush=True)
    rows = [json.loads(l) for l in open(path)]
    res = {r["key"]: {"native_category": cat_of.get(r["key"]), "oracle": verdict(r), "cpu_share": round(r["cpu_s"] / max(r["wall_s"], 1e-6), 2)}
           for r in rows}
    tab = {}
    for v in res.values():
        tab.setdefault(v["native_category"], {}).setdefault(v["oracle"], 0)
        tab[v["native_category"]][v["oracle"]] += 1
    json.dump({"corpus": a.corpus, "label": "ORACLE (evaluator-side; answers appended as demonstrations; never a prediction)",
               "table": tab, "tasks": res}, open(os.path.join(OUT, f"oracle_{a.corpus}{a.tag}.json"), "w"), indent=1)
    print(json.dumps(tab, indent=1))


if __name__ == "__main__":
    main()
