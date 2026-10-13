"""CORA-NVG reference (evaluator side): the frozen native engine on the
synthetic corpus, natively and with each eligible view promoted.

  python -m cora_neural_view.reference [--split dev|final|all] [--workers 6]
      -> outputs/neural_view_v0/reference_rows.jsonl (resumable)

Per task:
- census: for the full training set and each 2-pair subset (the engine's
  leave-one-out folds), every view's coherence, coverage, objects per
  demonstration and relaxed flag, plus the coherent / kept / cut lists,
  computed exactly as the inducer does;
- BASE and BASE_REPEAT: inducer.induce_program on the 3 training
  demonstrations (train-exact plus its own leave-one-out), budget 20 s. The
  repeat measures run-to-run noise under host load;
- PROMOTE_V, only on decision tasks: V searched first at every induction
  call, as in the negative probe. V ranges over the views cut by the cap
  on the full set, the options a guide can choose besides NO_CHANGE.

A decision task needs BASE and BASE_REPEAT both to REJECT and at least one
cut view on the full set. Tasks where the two native runs disagree are
reported as unstable and are not decisions.

Engine configuration: the sealed native chain flags (the Kaggle native_v1
set). No engine file is edited. The overlay is restored after every job.

Outcome uses the held-out outputs and only here:
- CORRECT: accepted, and both held-out demonstrations exact;
- FALSE_ACCEPT: accepted, and a held-out demonstration wrong;
- REJECT: not accepted.

The trace fields come from training demonstrations only. Guides may read
them; they never see the outcome or the prediction hash.
"""
import argparse
import contextlib
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
CHAIN_FLAGS = {"ARC_DIHEDRAL_FRAMES": "45", "ARC_GENERATIVE": "1", "ARC_PATTERN_DERIVE": "1",
               "ARC_VARIANT_BUDGET": "1", "ARC_RAY_EXT": "1"}
for _k in [k for k in os.environ if k.startswith("ARC_")]:
    del os.environ[_k]
os.environ.update(CHAIN_FLAGS)
BUDGET_S = 20.0
OUTDIR = os.path.join(HERE, "outputs", "neural_view_v0")
CORPUS = os.path.join(OUTDIR, "corpus.json")
ROWS = os.path.join(OUTDIR, "reference_rows.jsonl")
SUBSETS = ("012", "01", "02", "12")


def _load_tasks(split):
    c = json.load(open(CORPUS))
    return [t for t in c["tasks"] if split == "all" or t["split"] == split]


def census(train):
    """The inducer's own view admission on each subset, without searching."""
    import geocat_arc.object_reasoning.inducer as I
    import geocat_arc.object_reasoning.segmentation as S
    from geocat_arc.object_reasoning.types import to_grid_pairs
    order = list(I.SEGMENTATION_TRIAL_ORDER)
    out = {}
    for sub in SUBSETS:
        pairs = to_grid_pairs([(np.asarray(train[int(j)][0]), np.asarray(train[int(j)][1])) for j in sub])
        res = {v: S.evaluate_variant(v, pairs) for v in order}
        cands = [v for v in order if res[v].coherent]
        cands.sort(key=lambda v: 1 if res[v].create_orphan_relaxed else 0)
        if I._CREATE_COHERENCE_ON():
            kept = [v for v in cands if not res[v].create_orphan_relaxed][:I.MAX_SEG_VARIANTS_TRIED] + \
                   [v for v in cands if res[v].create_orphan_relaxed][:2]
        else:
            kept = cands[:I.MAX_SEG_VARIANTS_TRIED]
        if not cands:
            kept = [max(order, key=lambda v: (res[v].coherence, res[v].pixel_coverage))]
        out[sub] = {"coherent": [v.value for v in cands], "kept": [v.value for v in kept],
                    "cut": [v.value for v in cands if v not in kept],
                    "views": {v.value: {"coherent": bool(res[v].coherent), "coherence": float(res[v].coherence),
                                        "coverage": float(res[v].pixel_coverage),
                                        "relaxed": bool(res[v].create_orphan_relaxed),
                                        "objects": [len(o) for o in res[v].input_objects]} for v in order}}
    return out


@contextlib.contextmanager
def promote(variant):
    import geocat_arc.object_reasoning.inducer as I
    order0 = I.SEGMENTATION_TRIAL_ORDER
    v = next(x for x in order0 if x.value == variant)
    I.SEGMENTATION_TRIAL_ORDER = (v,) + tuple(x for x in order0 if x is not v)
    try:
        yield
    finally:
        I.SEGMENTATION_TRIAL_ORDER = order0


def _json_safe(x, limit=40):
    if isinstance(x, list):
        return [_json_safe(y) for y in x[:limit]]
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in list(x.items())[:limit]}
    if isinstance(x, (int, float, str, bool)) or x is None:
        return x
    return repr(x)[:200]


def trace_of(res):
    """Training-only failure trace of an InductionResult."""
    loo = res.loo
    ns = res.near_solve
    return {"accepted": bool(res.accepted), "failure_stage": getattr(res.failure_stage, "value", None),
            "train_fit_pixels": float(res.train_fit_pixels), "train_fit_objects": float(res.train_fit_objects),
            "segmentation": getattr(getattr(res.segmentation, "variant", None), "value", None),
            "hypotheses": int(res.hypotheses_enumerated), "events": list(res.events)[:40],
            "loo": None if loo is None else {"folds": loo.folds, "passed": loo.passed,
                                             "failed_pairs": list(loo.failed_pair_indices),
                                             "divergence": _json_safe(loo.divergence)},
            "near_solve": None if ns is None else {
                "variant": ns.segmentation_variant, "fit_pixels": float(ns.train_fit_pixels),
                "fit_objects": float(ns.train_fit_objects), "explained_rules": len(ns.explained_rules),
                "unexplained": len(ns.residual.get("unexplained_deltas", [])),
                "unexplained_deltas": _json_safe(ns.residual.get("unexplained_deltas", []), 12),
                "conflicts": _json_safe(ns.residual.get("conflict_report", {})),
                "loo_failures": list(ns.residual.get("loo_failures", [])),
                "histogram": _json_safe(getattr(ns, "delta_histogram", {})), "stage": getattr(ns, "failure_stage", None)}}


def program_variant(program):
    p = program
    while hasattr(p, "inner"):
        p = p.inner
    return getattr(getattr(p, "segmentation_variant", None), "value", None)


def job(args):
    tid, condition = args
    os.nice(19) if os.getpid() != os.getppid() and os.nice(0) < 19 else None
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.actions import program_apply_fn
    from geocat_arc.object_reasoning.types import to_grid_pairs
    t = next(x for x in _load_tasks("all") if x["id"] == tid)
    train = [(np.asarray(a), np.asarray(b)) for a, b in t["train"]]
    ctx = promote(condition[len("PROMOTE_"):]) if condition.startswith("PROMOTE_") else contextlib.nullcontext()
    t0 = time.process_time()
    with ctx:
        res = I.induce_program(to_grid_pairs(train), I.InductionConfig(budget_s=BUDGET_S))
        preds = None
        if res.accepted and res.program is not None:
            fn = program_apply_fn(res.program)
            preds = []
            for a, _ in t["heldout"]:
                try:
                    preds.append(np.asarray(fn(np.asarray(a))).tolist())
                except Exception:                                   # noqa: BLE001
                    preds.append(None)
    cpu = time.process_time() - t0
    exact = None if preds is None else [p == b for p, (_, b) in zip(preds, t["heldout"])]
    outcome = "REJECT" if not res.accepted else ("CORRECT" if all(exact) else "FALSE_ACCEPT")
    return {"kind": "run", "task": tid, "condition": condition, "outcome": outcome,
            "program_variant": program_variant(res.program) if res.program is not None else None,
            "prediction_sha": None if preds is None else hashlib.sha256(json.dumps(preds).encode()).hexdigest()[:16],
            "wall_s": round(float(res.induction_time_s), 2), "cpu_s": round(cpu, 2), "trace": trace_of(res)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args(argv)
    tasks = _load_tasks(a.split)
    done = set()
    cens = {}
    if os.path.exists(ROWS):
        for line in open(ROWS):
            r = json.loads(line)
            done.add((r["task"], r.get("condition", "CENSUS")))
            if r["kind"] == "census":
                cens[r["task"]] = r["census"]
    with open(ROWS, "a") as handle:
        for t in tasks:
            if t["id"] not in cens:
                cens[t["id"]] = census(t["train"])
                handle.write(json.dumps({"kind": "census", "task": t["id"], "census": cens[t["id"]]}) + "\n")
                handle.flush()
        base_rows = {}
        for line in open(ROWS):
            r = json.loads(line)
            if r["kind"] == "run":
                base_rows[(r["task"], r["condition"])] = r
        for phase in ("base", "promote"):
            jobs = []
            for t in tasks:
                if phase == "base":
                    conds = ["BASE", "BASE_REPEAT"]
                else:
                    b1, b2 = base_rows.get((t["id"], "BASE")), base_rows.get((t["id"], "BASE_REPEAT"))
                    if not (b1 and b2 and b1["outcome"] == b2["outcome"] == "REJECT"):
                        continue
                    conds = [f"PROMOTE_{v}" for v in cens[t["id"]]["012"]["cut"]]
                jobs += [(t["id"], c) for c in conds if (t["id"], c) not in done]
            print(f"phase {phase}: {len(tasks)} tasks, {len(jobs)} runs to do", flush=True)
            with mp.get_context("fork").Pool(a.workers, maxtasksperchild=20) as pool:
                for k, row in enumerate(pool.imap_unordered(job, jobs), 1):
                    handle.write(json.dumps(row) + "\n")
                    handle.flush()
                    base_rows[(row["task"], row["condition"])] = row
                    if k % 25 == 0:
                        print(f"{phase} {k}/{len(jobs)} runs", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
