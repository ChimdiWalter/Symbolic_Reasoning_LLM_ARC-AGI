"""P3 adversarial corpus (P3 safety directive 2026-10-12, section 5). Generated
and frozen BEFORE any P3 code exists; synthetic only, no ARC data.

  python scripts/p3_adversarial_corpus.py   -> outputs/p3/adversarial_corpus.json

Candidates: 8 rule families x 6 seeds (seeds 500+), each task 3 training and
2 held-out demonstrations from the same rule. Six families reuse the
negative-probe generator with fresh seeds; two are new:
  layer_keep_largest  single cells of 2-3 colours with distinct counts; only the
                      colour with the most cells is kept (a colour-layer rule);
  diag_touch_size     recolour every 4-connected object to its size; held-out
                      inputs add a diagonal pair of one colour (4-connected
                      views see two objects, 8-connected views one).
Fixture selection uses ONLY static segmentation properties (the census code
of scripts/loo_v1_probe_equivalence.py on the training subsets the engine
sees: the full set and each 2-pair fold) and the behaviour of the native
engine (BASE) and of forcing one view first (PROMOTE, the negative-probe
overlay); nothing involving P3. Rules, applied in this order, at most 3
tasks per family, a task taking the first family it meets:
  A  dedup would admit S6 somewhere, PROMOTE S6 is CORRECT, BASE is not:
     removing a duplicate would free a useful slot;
  B  dedup would admit a view V somewhere and PROMOTE V is FALSE_ACCEPT:
     a freed slot could hold a misleading train-exact view;
  C  two views equal at the INDUCTION level on a training subset segment a
     held-out input differently;
  D  BASE is CORRECT and dedup would change at least one subset: a native
     success P3 must not displace;
  F  dedup changes no full-set search but changes a 2-pair fold;
  E  dedup changes nothing: P3 must be a no-op.
Family G (fewer demonstrations, no parent-fold information) is tested by the
mutation tests of the implementation, not by tasks.
"""
import hashlib
import itertools
import json
import multiprocessing as mp
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
import loo_v1_probe_negative as NEG                                   # noqa: E402

BUDGET_S = 20.0
FAMILIES = NEG.FAMILIES + ("layer_keep_largest", "diag_touch_size")
SEEDS = range(500, 506)


def _layer_demo(rng):
    for _ in range(200):
        g = np.zeros((10, 10), int)
        k = int(rng.integers(2, 4))
        colours = rng.choice(np.arange(1, 10), k, replace=False)
        counts = rng.choice([1, 2, 3, 4], k, replace=False)
        ok = True
        for col, cnt in zip(colours, counts):
            for _ in range(int(cnt)):
                if NEG._place(rng, g, {(0, 0)}, int(col)) is None:
                    ok = False
        if not ok:
            continue
        o = g.copy()
        keep = int(colours[int(np.argmax(counts))])
        o[(g != 0) & (g != keep)] = 0
        return g, o
    raise RuntimeError("layer")


def _diag_demo(rng, heldout):
    g, o = NEG._demo(rng, "recolor_by_size")
    if not heldout:
        return g, o
    col = int(rng.integers(1, 8))
    for _ in range(500):
        r, c = int(rng.integers(1, 8)), int(rng.integers(1, 8))
        box = g[r - 1:r + 3, c - 1:c + 3]
        if (box == 0).all():
            g, o = g.copy(), o.copy()
            g[r, c] = g[r + 1, c + 1] = col
            o[r, c] = o[r + 1, c + 1] = 1          # two 4-connected objects of size 1
            return g, o
    raise RuntimeError("diag")


def candidates():
    out = []
    for fi, fam in enumerate(FAMILIES):
        for s in SEEDS:
            rng = np.random.default_rng(10000 * (fi + 1) + s)
            if fam == "layer_keep_largest":
                demos = [_layer_demo(rng) for _ in range(5)]
            elif fam == "diag_touch_size":
                demos = [_diag_demo(rng, i >= 3) for i in range(5)]
            else:
                demos = [NEG._demo(rng, fam) for _ in range(5)]
            out.append({"id": f"{fam}_{s}", "family": fam,
                        "train": [(a.tolist(), b.tolist()) for a, b in demos[:3]],
                        "heldout": [(a.tolist(), b.tolist()) for a, b in demos[3:]]})
    return out


def run(args):
    """BASE (variant None) or PROMOTE variant v: the engine's own induction, 20 s."""
    t, v = args
    import contextlib
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.actions import program_apply_fn
    from geocat_arc.object_reasoning.types import to_grid_pairs
    train = [(np.asarray(a), np.asarray(b)) for a, b in t["train"]]
    ctx = NEG.overlay(v, admit=False) if v else contextlib.nullcontext()
    with ctx:
        res = I.induce_program(to_grid_pairs(train), I.InductionConfig(budget_s=BUDGET_S))
        exact = None
        if res.accepted and res.program is not None:
            fn = program_apply_fn(res.program)
            exact = []
            for a, b in t["heldout"]:
                try:
                    exact.append(bool((np.asarray(fn(np.asarray(a))) == np.asarray(b)).all()))
                except Exception:                                   # noqa: BLE001
                    exact.append(False)
    return t["id"], v, "REJECT" if not res.accepted else ("CORRECT" if all(exact) else "FALSE_ACCEPT")


def main():
    import loo_v1_probe_equivalence as EQ
    import p3_audit_equivalence as AU
    import geocat_arc.object_reasoning.inducer as I
    order = [v.value for v in I.SEGMENTATION_TRIAL_ORDER]
    cands = candidates()
    static = {}
    for t in cands:
        train = [(np.asarray(a), np.asarray(b)) for a, b in t["train"]]
        subsets = [(0, 1, 2), (0, 1), (0, 2), (1, 2)]
        _, rec = EQ.task_record((t["id"], train, subsets, False))
        rec = json.loads(json.dumps(rec))
        held = [(np.asarray(a), np.asarray(b)) for a, b in t["heldout"]]
        div = AU.unseen(t["id"], train, held, rec["subsets"], order)
        static[t["id"]] = {"subsets": {k: {x: r[x] for x in ("coherent", "kept", "dedup_kept", "dedup_admits")}
                                       for k, r in rec["subsets"].items()},
                           "heldout_divergent": [d for d in div if any(str(x).startswith("heldout") for x in d["diverges_on"])]}
    jobs = []
    for t in cands:
        jobs.append((t, None))
        full = static[t["id"]]["subsets"]["012"]["coherent"]
        admitted = sorted({v for r in static[t["id"]]["subsets"].values() for v in r["dedup_admits"]})
        for v in sorted(set(admitted) | {"S6"}):
            if v in full:
                jobs.append((t, v))
    with mp.get_context("fork").Pool(4) as pool:
        res = pool.map(run, jobs, chunksize=1)
    pre = {}
    for tid, v, o in res:
        pre.setdefault(tid, {})["BASE" if v is None else f"PROMOTE_{v}"] = o
    chosen, fam_of = {f: [] for f in "ABCDFE"}, {}
    for t in cands:
        st, p = static[t["id"]], pre[t["id"]]
        admits = {v for r in st["subsets"].values() for v in r["dedup_admits"]}
        changed = [k for k, r in st["subsets"].items() if r["dedup_admits"]]
        tests = {"A": "S6" in admits and p.get("PROMOTE_S6") == "CORRECT" and p["BASE"] != "CORRECT",
                 "B": any(p.get(f"PROMOTE_{v}") == "FALSE_ACCEPT" for v in admits),
                 "C": bool(st["heldout_divergent"]),
                 "D": p["BASE"] == "CORRECT" and bool(changed),
                 "F": bool(changed) and "012" not in changed,
                 "E": not changed}
        t["meets"] = [f for f in "ABCDFE" if tests[f]]
        for f in "ABCDFE":
            if tests[f] and len(chosen[f]) < 3:
                chosen[f].append(t["id"])
                fam_of[t["id"]] = f
                break
    corpus = [dict(t, adversarial_family=fam_of[t["id"]], static=static[t["id"]], prerun=pre[t["id"]])
              for t in cands if t["id"] in fam_of]
    digest = hashlib.sha256(json.dumps([[t["id"], t["train"], t["heldout"]] for t in corpus],
                                       sort_keys=True).encode()).hexdigest()
    out = {"budget_s": BUDGET_S, "families": FAMILIES, "seeds": list(SEEDS), "selected": chosen,
           "corpus_sha256": digest, "n_selected": len(corpus), "corpus": corpus,
           "candidates": [{"id": t["id"], "meets": t["meets"], "prerun": pre[t["id"]]} for t in cands]}
    os.makedirs(os.path.join(HERE, "outputs", "p3"), exist_ok=True)
    with open(os.path.join(HERE, "outputs", "p3", "adversarial_corpus.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({"selected": chosen, "n": len(corpus), "corpus_sha256": digest}, indent=1))


if __name__ == "__main__":
    main()
