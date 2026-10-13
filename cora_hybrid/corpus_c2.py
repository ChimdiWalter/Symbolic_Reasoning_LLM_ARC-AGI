"""Corpus C2 for neural-symbolic complementarity
(`records/CORA_NEURAL_CANDIDATE_EVIDENCE_PLAN_20261013.md`). Private and
synthetic, never seen by NVARC or CORA.

  python -m cora_hybrid.corpus_c2
      -> outputs/hybrid_c2/challenges.json   competition format, no test outputs (solvers)
         outputs/hybrid_c2/solutions.json    test outputs (evaluator only)
         outputs/hybrid_c2/manifest.json     sha256s, families, seeds

Twelve families, 10 tasks each, seeds 9000 and up (never used before):
- six reuse the negative-probe generator (rules the native engine solves
  in part);
- four reuse CORA-NVG families (rules it misses);
- two are new global rules.

Each task has 3 training demonstrations and 1 test input. Every
demonstration's output differs from its input.
"""
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))
import loo_v1_probe_negative as NEG                                   # noqa: E402
from cora_neural_view import corpus as NVG                            # noqa: E402

OUT = os.path.join(HERE, "outputs", "hybrid_c2")
NEG_FAMILIES = ("recolor_by_size", "halo", "bbox_fill_L", "translate_down", "multicolor_majority", "same_color_sizes")
NVG_FAMILIES = ("d_diag_drop", "f_diag_mirror", "d_layer_size", "f_layer_frame")
NEW_FAMILIES = ("g_row_extend", "g_mirror_complete")
FAMILIES = NEG_FAMILIES + NVG_FAMILIES + NEW_FAMILIES
SEEDS = range(9000, 9010)


def _new_demo(rng, family):
    for _ in range(200):
        if family == "g_row_extend":
            # each coloured cell in column 0..3 extends rightwards to the edge
            g = np.zeros((8, 10), int)
            rows = rng.choice(np.arange(8), int(rng.integers(2, 4)), replace=False)
            for r in rows:
                g[r, int(rng.integers(0, 4))] = int(rng.integers(1, 9))
            o = g.copy()
            for r in rows:
                c0 = int(np.nonzero(g[r])[0][0])
                o[r, c0:] = g[r, c0]
        else:
            # g_mirror_complete: the right half is the mirror of the left half
            h, w = int(rng.integers(4, 9)), int(rng.integers(2, 6))
            left = (rng.random((h, w)) < 0.45) * rng.integers(1, 9, (h, w))
            g = np.concatenate([left, np.zeros((h, w), int)], axis=1)
            o = np.concatenate([left, left[:, ::-1]], axis=1)
        if not (o == g).all():
            return g.astype(int), o.astype(int)
    raise RuntimeError(family)


def _demo(rng, family):
    if family in NEG_FAMILIES:
        return NEG._demo(rng, family)
    if family in NVG_FAMILIES:
        return NVG._demo(rng, family, None)
    return _new_demo(rng, family)


def build():
    challenges, solutions, meta = {}, {}, {}
    for fi, fam in enumerate(FAMILIES):
        for s in SEEDS:
            rng = np.random.default_rng(100_000 * fi + s)
            demos = [_demo(rng, fam) for _ in range(4)]
            tid = hashlib.sha256(f"c2:{fam}:{s}".encode()).hexdigest()[:8]
            challenges[tid] = {"train": [{"input": a.tolist(), "output": b.tolist()} for a, b in demos[:3]],
                               "test": [{"input": demos[3][0].tolist()}]}
            solutions[tid] = [demos[3][1].tolist()]
            meta[tid] = {"family": fam, "seed": s}
    return challenges, solutions, meta


def main():
    challenges, solutions, meta = build()
    os.makedirs(OUT, exist_ok=True)
    texts = {"challenges.json": json.dumps(challenges, sort_keys=True), "solutions.json": json.dumps(solutions, sort_keys=True)}
    for name, text in texts.items():
        open(os.path.join(OUT, name), "w").write(text)
    man = {"version": "c2_v0", "families": FAMILIES, "seeds": [SEEDS.start, SEEDS.stop], "tasks": len(challenges),
           "sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in texts.items()}, "task_meta": meta}
    json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({"tasks": len(challenges), **man["sha256"]}))


if __name__ == "__main__":
    main()
