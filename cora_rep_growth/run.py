"""Run the cora_rep_growth arms on a C3 split (plan section 6).

  python -m cora_rep_growth.run --split dev --arms A,D,E [--workers 3]
      -> outputs/rep_growth_v0/rows_<split>.jsonl (resumable by (task, arm))

Arms:
- A: native, budget 20 s;
- B: native, budget 40 s;
- C: native with the cap lifted to 7;
- D: failure-blind constructor;
- E: failure-conditioned constructor;
- E-shuf: E with another task's arm-A top-level diagnosis.

All arms run the sealed native chain flags, an induce_program call on the
3 training demonstrations, and the adapter's per-call log ("off" in A, B
and C). The outcome uses the 2 held-out demonstrations, evaluator side:
CORRECT, FALSE_ACCEPT or REJECT. The constructors never see them.
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


@contextlib.contextmanager
def cap(n):
    import geocat_arc.object_reasoning.inducer as I
    old = I.MAX_SEG_VARIANTS_TRIED
    I.MAX_SEG_VARIANTS_TRIED = n
    try:
        yield
    finally:
        I.MAX_SEG_VARIANTS_TRIED = old


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
    budget = 40.0 if arm == "B" else 20.0
    mode = {"A": "off", "B": "off", "C": "off", "D": "D", "E": "E", "E-shuf": "E-shuf"}[arm]
    t0, c0 = time.time(), time.process_time()
    with rep_growth(mode, shuffle=tuple(shuffle) if shuffle else None) as ev, (cap(7) if arm == "C" else contextlib.nullcontext()):
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
            "diagnoses": dict(ev["diagnoses"]), "constructed_calls": ev["constructed_calls"],
            "programs_tried": ev["programs_tried"], "wins": ev["wins"][:6], "top_call": top}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--arms", default="A,B,C,D,E,E-shuf")
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
            shuffle_src = {}
            if phase == "E-shuf":
                ids = [t["id"] for t in tasks]
                top = {i: (done.get((i, "A")) or {}).get("top_call") or {} for i in ids}
                for j, i in enumerate(ids):
                    mine = (top[i].get("diag"), top[i].get("stage"))
                    for k in range(1, len(ids)):
                        o = ids[(j + k) % len(ids)]
                        other = (top[o].get("diag"), top[o].get("stage"))
                        if other != mine and other[0] is not None:
                            shuffle_src[i] = other
                            break
                    else:
                        shuffle_src[i] = ("UNKNOWN", None)
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
