#!/usr/bin/env python3
"""Lever 6: self-play completeness testing — the learner exercised on
tasks its OWN grammar generated.

Sample programs from a curated slice of the engine's program space, render
them into synthetic train pairs + one held-out test pair, then require
induce_program (full gate) to certify a program that renders the held-out
output exactly.  Every failure is an inducer blind spot with the
ground-truth program attached — debugging gold, zero benchmark leakage
(no ARC data involved).

Deterministic: seeded RNG; the same seed always builds the same battery.

Usage: self_play_battery.py [n=40] [seed=9] [budget_s=45]
Writes outputs/self_play_battery.json.
"""
import json
import random
import sys

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.actions import render_program
from geocat_arc.object_reasoning.expressions import (ColorExpr, PredExpr,
                                                     VecExpr)
from geocat_arc.object_reasoning.inducer import induce_program, InductionConfig
from geocat_arc.object_reasoning.types import (ActionRule, DeltaType,
                                               ObjectProgram, ObjectRule,
                                               OutputSpec,
                                               SegmentationVariant,
                                               SelectorRule)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 9
BUDGET = float(sys.argv[3]) if len(sys.argv) > 3 else 45.0
OUT = "outputs/self_play_battery.json"

SHAPES = [
    [(0, 0), (0, 1), (0, 2)],                     # bar3
    [(0, 0), (1, 0), (2, 0), (2, 1)],             # L
    [(0, 0), (0, 1), (1, 0), (1, 1)],             # square
    [(0, 0), (0, 1), (0, 2), (1, 1)],             # T
    [(0, 0), (1, 1), (2, 2)],                     # diag (S2 target)
]


def place_objects(rng, h, w, n_obj):
    """Non-overlapping shapes with distinct colors; returns cell->color."""
    cells = {}
    colors = rng.sample(range(1, 10), n_obj)
    tries = 0
    placed = 0
    while placed < n_obj and tries < 200:
        tries += 1
        shape = rng.choice(SHAPES)
        r0 = rng.randrange(1, h - 4)
        c0 = rng.randrange(1, w - 4)
        abs_cells = [(r + r0, c + c0) for r, c in shape]
        # 1-cell separation so S1 keeps objects distinct
        halo = {(r + dr, c + dc) for r, c in abs_cells
                for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
        if any(x in cells for x in halo):
            continue
        for x in abs_cells:
            cells[x] = colors[placed]
        placed += 1
    return cells if placed == n_obj else None


def sample_program(rng):
    """One rule + KEEP default from a curated action space."""
    kind = rng.choice(["recolor_const", "recolor_affine", "translate",
                       "delete", "recolor_map_like"])
    biggest = PredExpr(op="test", args=("size_rank", "==", "@rank_max"))
    smallest = PredExpr(op="test", args=("size_rank", "==", "@rank_min"))
    everyone = PredExpr(op="true", args=())
    sel = rng.choice([everyone, biggest, smallest])
    if kind == "recolor_const":
        action = ActionRule(delta_type=DeltaType.RECOLOR, params={
            "color": ColorExpr(op="const", args=(rng.randrange(1, 10),))})
    elif kind == "recolor_affine":
        action = ActionRule(delta_type=DeltaType.RECOLOR, params={
            "color": ColorExpr(op="feature_affine",
                               args=("size", rng.choice((-2, -1, 0, 1))))})
    elif kind == "recolor_map_like":
        action = ActionRule(delta_type=DeltaType.RECOLOR, params={
            "color": ColorExpr(op="most_common_color", args=())})
        sel = everyone
    elif kind == "translate":
        action = ActionRule(delta_type=DeltaType.TRANSLATE, params={
            "vector": VecExpr(op="const", args=(rng.choice((-2, -1, 1, 2)),
                                                rng.choice((-1, 0, 1))))})
    else:  # delete
        action = ActionRule(delta_type=DeltaType.DELETE, params={})
        sel = rng.choice([biggest, smallest])   # delete-all is degenerate
    rule = ObjectRule(selector=SelectorRule(predicate=sel,
                                            literals=sel.literals),
                      action=action)
    return kind, ObjectProgram(
        segmentation_variant=SegmentationVariant("S1"), rules=[rule],
        default_action=ActionRule(delta_type=DeltaType.KEEP),
        output_spec=OutputSpec(mode="same_as_input"))


def main():
    rng = random.Random(SEED)
    results = []
    solved = 0
    attempted = 0
    while attempted < N:
        kind, prog = sample_program(rng)
        h, w = rng.choice(((10, 10), (12, 9), (9, 14))), None
        h, w = h
        grids = []
        ok = True
        for _ in range(5):
            cells = place_objects(rng, h, w, rng.choice((2, 3)))
            if cells is None:
                ok = False
                break
            gi = [[0] * w for _ in range(h)]
            for (r, c), col in cells.items():
                gi[r][c] = col
            g_in = Grid.from_list(gi)
            try:
                g_out = render_program(prog, g_in)
            except Exception:
                ok = False
                break
            if g_out.to_list() == g_in.to_list():
                ok = False      # degenerate identity sample; reroll
                break
            grids.append((g_in, g_out))
        if not ok:
            continue
        attempted += 1
        train, test = grids[:4], grids[4]
        res = induce_program(train, InductionConfig(budget_s=BUDGET))
        recovered = False
        if res.accepted:
            try:
                recovered = render_program(res.program,
                                           test[0]).to_list() == \
                    test[1].to_list()
            except Exception:
                recovered = False
        solved += recovered
        results.append({"kind": kind, "accepted": res.accepted,
                        "held_out_correct": recovered,
                        "failure_stage": (res.failure_stage.value
                                          if res.failure_stage else None),
                        "generator": prog.to_dict()})
        print(f"[{attempted}/{N}] {kind}: accepted={res.accepted} "
              f"held_out={recovered}", flush=True)
    by_kind = {}
    for r in results:
        k = r["kind"]
        by_kind.setdefault(k, [0, 0])
        by_kind[k][1] += 1
        by_kind[k][0] += r["held_out_correct"]
    report = {"seed": SEED, "n": N, "budget_s": BUDGET,
              "recovered": solved,
              "by_kind": {k: f"{a}/{b}" for k, (a, b) in
                          sorted(by_kind.items())},
              "results": results}
    json.dump(report, open(OUT, "w"), indent=1)
    print(f"SELF-PLAY BATTERY COMPLETE: {solved}/{N} recovered "
          f"{report['by_kind']} -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
