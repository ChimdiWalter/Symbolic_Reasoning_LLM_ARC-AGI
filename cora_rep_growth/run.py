"""Run the cora_rep_growth arms on a C3 split (plan section 6).

  python -m cora_rep_growth.run --split dev --arms A,D,E [--workers 3]
      -> outputs/rep_growth_v0/rows_<split>.jsonl (resumable by (task, arm))

Arms (plan amendment 1):
- A FROZEN_NATIVE, budget 20 s;
- B SEARCH_ONLY, budget B_BUDGET_S (matched to F's measured compute; fixed
  in freeze v1);
- C EXISTING_VIEW_CORRECTION;
- D FAILURE_BLIND_CONSTRUCTOR;
- E SHUFFLED_FAILURE_CONSTRUCTOR, using another task's arm-A top-level
  observation;
- F FAILURE_CONDITIONED_CONSTRUCTOR.

All arms run the sealed native chain flags, an induce_program call on the
3 training demonstrations, and the adapter's per-call log. The constructors
and the controller see the held-out INPUTS only, as unlabelled inputs. The
outcome uses the held-out outputs, evaluator side: CORRECT, FALSE_ACCEPT
or REJECT.
"""
import argparse
import contextlib
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
for _k in [k for k in os.environ if k.startswith("ARC_")]:
    del os.environ[_k]
os.environ.update({"ARC_DIHEDRAL_FRAMES": "45", "ARC_GENERATIVE": "1", "ARC_PATTERN_DERIVE": "1",
                   "ARC_VARIANT_BUDGET": "1", "ARC_RAY_EXT": "1"})
OUT = os.path.join(HERE, "outputs", "rep_growth_v0")
CORPUS = os.path.join(OUT, "corpus.json")


def _tasks(split):
    return [t for t in json.load(open(CORPUS))["tasks"] if t["split"] == split]


B_BUDGET_S = float(os.environ.get("CORA_RG_B_BUDGET_S", "40"))


def job(args):
    tid, arm, shuffle, split = args
    if os.nice(0) < 19:
        os.nice(19 - os.nice(0))
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.actions import program_apply_fn
    from geocat_arc.object_reasoning.types import to_grid_pairs
    from cora_rep_growth.adapter import rep_growth
    t = next(x for x in _tasks(split) if x["id"] == tid)
    pairs = to_grid_pairs([(np.asarray(a), np.asarray(b)) for a, b in t["train"]])
    budget = B_BUDGET_S if arm == "B" else 20.0
    unl = [a for a, _ in t["heldout"]]                                 # inputs only
    t0, c0 = time.time(), time.process_time()
    with rep_growth(arm, unlabelled=unl, shuffle=shuffle, n_top=len(t["train"])) as ev:
        res = I.induce_program(pairs, I.InductionConfig(budget_s=budget))
        preds = None
        if res.accepted and res.program is not None:
            fn = program_apply_fn(res.program)
            preds = []
            for a, _ in t["heldout"]:
                try:
                    preds.append(np.asarray(fn(np.asarray(a))).tolist())
                except Exception:                                       # noqa: BLE001
                    preds.append(None)
        cand_exact = None                                              # funnel: the top-level train-exact candidate, scored on held-out (evaluator side)
        if ev["top_candidate"] is not None:
            try:
                cfn = program_apply_fn(ev["top_candidate"])
                cand_exact = all(np.asarray(cfn(np.asarray(a))).tolist() == b for a, b in t["heldout"])
            except Exception:                                           # noqa: BLE001
                cand_exact = False
        p = res.program
        while p is not None and hasattr(p, "inner"):
            p = p.inner
        variant = getattr(getattr(p, "segmentation_variant", None), "value", None) if p is not None else None
    exact = None if preds is None else [x == b for x, (_, b) in zip(preds, t["heldout"])]
    outcome = "REJECT" if not res.accepted else ("CORRECT" if all(exact) else "FALSE_ACCEPT")
    top = next((c for c in ev["calls_log"] if c["pairs"] == len(t["train"])), None)
    return {"task": tid, "family": t["family"], "arm": arm, "outcome": outcome, "program_variant": variant,
            "constructed_view_used": bool(variant and str(variant).startswith("G:")),
            "stage": getattr(res.failure_stage, "value", None), "wall_s": round(time.time() - t0, 1),
            "cpu_s": round(time.process_time() - c0, 1), "calls": ev["calls"], "failed_calls": ev["failed_calls"],
            "decisions": dict(ev["decisions"]), "probe_runs": ev["probe_runs"], "constructed_tried": ev["constructed_tried"],
            "novel_seen": ev["novel_seen"], "wins": ev["wins"][:6], "top_call": top,
            "funnel": {"candidate_generated": ev["top_candidate"] is not None, "verified": bool(res.accepted),
                       "candidate_correct_on_heldout": cand_exact}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--arms", default="A,B,C,D,E,F")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    rows_path = os.path.join(OUT, f"rows_{a.split}.jsonl")
    done = {}
    if os.path.exists(rows_path):
        for line in open(rows_path):
            r = json.loads(line)
            done[(r["task"], r["arm"])] = r
    tasks = _tasks(a.split)
    arms = a.arms.split(",")
    with open(rows_path, "a") as handle:
        for phase in (["A"] if "A" in arms else []) + [x for x in arms if x != "A"]:
            if phase == "E" and not all((t["id"], "A") in done for t in tasks):
                sys.exit("arm E needs arm A rows for every task first")
            shuffle_src = {}
            if phase == "E":
                ids = [t["id"] for t in tasks]
                obs = {}
                for i in ids:
                    tc = (done.get((i, "A")) or {}).get("top_call") or {}
                    obs[i] = None if tc.get("ok", True) else {k: tc.get(k) for k in ("deadline_hit", "fit_objects", "stage", "cut")}
                for j, i in enumerate(ids):
                    for k in range(1, len(ids)):
                        o = ids[(j + k) % len(ids)]
                        if obs[o] is not None and (obs[i] is None or (obs[o]["stage"], bool(obs[o]["cut"])) != (obs[i]["stage"], bool(obs[i]["cut"]))):
                            shuffle_src[i] = obs[o]
                            break
                    else:
                        shuffle_src[i] = {"deadline_hit": False, "fit_objects": 0.0, "stage": None, "cut": []}
            jobs = [(t["id"], phase, shuffle_src.get(t["id"]), a.split) for t in tasks if (t["id"], phase) not in done]
            print(f"arm {phase}: {len(jobs)} runs", flush=True)
            with mp.get_context("fork").Pool(a.workers, maxtasksperchild=10) as pool:
                for row in pool.imap_unordered(job, jobs):
                    handle.write(json.dumps(row) + "\n")
                    handle.flush()
                    done[(row["task"], row["arm"])] = row
    print("done", flush=True)


if __name__ == "__main__":
    main()
