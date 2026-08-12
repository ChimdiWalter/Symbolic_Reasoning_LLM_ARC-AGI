#!/usr/bin/env python3
"""AUTONOMOUS M2 — the chain miner (GO/NO-GO for the synthesizer runtime).

Searches a bounded combinator space for VERB CANDIDATES: a chain of 1-2
primitive cell-set transforms that maps a SOURCE object's cells onto an
orphan's cells exactly, consistently across >= K distinct tasks.

Combinator catalog (each a pure cell-set -> cell-set function with at most
one integer/symbol slot; chains of depth <= 2; slots re-fit PER INSTANCE
like D15 operator slots — a verb generalizes when the CHAIN is constant
and only slot values vary):

  identity            mirror(axis in 4)        rot(k in 1..3)
  scale_up(k in 2..4) scale_down(k in 2..4)    window(free rect slot)
  ring                interior                 bbox_fill
  extrude(dir, free len slot)                  translate(free vec slot)

The miner reports, per residual family: which chains explain how many
instances/tasks — the evidence a synthesizer runtime would register from.
Output: outputs/meta_m2_chains.json + histogram.  NO engine changes; this
is measurement (the runtime is built only on a GO).
"""
import json
import glob
import os
import sys
from collections import Counter, defaultdict
from itertools import product

import numpy as np

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import match_pair, extract_deltas
from geocat_arc.object_reasoning.types import SegmentationVariant, DeltaType
from geocat_arc.object_reasoning.growth import interior_cells

chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
try:
    chal.update(json.load(open("data/arc/arc-agi_evaluation_challenges.json")))
except Exception:
    pass


# --- combinator catalog: cells (set of (r,c)) -> set, or None if undefined
def _norm(cells):
    if not cells:
        return frozenset()
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    return frozenset((r - r0, c - c0) for (r, c) in cells)


def c_identity(cells, slot=None):
    return cells


def c_mirror_h(cells, slot=None):
    h = max(r for r, _ in cells)
    return {(h - r, c) for (r, c) in cells}


def c_mirror_v(cells, slot=None):
    w = max(c for _, c in cells)
    return {(r, w - c) for (r, c) in cells}


def c_rot(cells, k):
    a = np.zeros((max(r for r, _ in cells) + 1,
                  max(c for _, c in cells) + 1), dtype=int)
    for r, c in cells:
        a[r, c] = 1
    a = np.rot90(a, k)
    return {(r, c) for r, c in zip(*np.nonzero(a))}


def c_scale_up(cells, k):
    return {(r * k + i, c * k + j) for (r, c) in cells
            for i in range(k) for j in range(k)}


def c_scale_down(cells, k):
    out = {(r // k, c // k) for (r, c) in cells}
    # exact only when the upscale of the result reproduces the input
    return out if c_scale_up(out, k) == set(cells) else None


def c_ring(cells, slot=None):
    return {(r + dr, c + dc) for (r, c) in cells
            for dr in (-1, 0, 1) for dc in (-1, 0, 1)} - set(cells)


def c_interior(cells, slot=None):
    return interior_cells(set(cells)) or None


def c_bbox_fill(cells, slot=None):
    return {(r, c) for r in range(max(x for x, _ in cells) + 1)
            for c in range(max(y for _, y in cells) + 1)}


CHAIN_OPS = (
    [("identity", c_identity, [None])]
    + [("mirror_h", c_mirror_h, [None]), ("mirror_v", c_mirror_v, [None])]
    + [("rot", c_rot, [1, 2, 3])]
    + [("scale_up", c_scale_up, [2, 3, 4])]
    + [("scale_down", c_scale_down, [2, 3, 4])]
    + [("ring", c_ring, [None]), ("interior", c_interior, [None]),
       ("bbox_fill", c_bbox_fill, [None])]
)


def chains():
    units = [(name, fn, s) for name, fn, slots in CHAIN_OPS for s in slots]
    for u in units:
        yield (u,)
    for a, b in product(units, repeat=2):
        if a[0] == "identity" or b[0] == "identity":
            continue
        yield (a, b)


def apply_chain(chain, cells):
    cur = set(cells)
    for name, fn, slot in chain:
        cur = fn(cur, slot) if slot is not None else fn(cur)
        if not cur:
            return None
        cur = set(_norm(cur))
    return frozenset(cur)


def chain_key(chain):
    return "+".join(f"{n}({s})" if s is not None else n
                    for n, _f, s in chain)


# --- collect unexplained orphan instances (source candidates = all inputs)
instances = []          # (task_id, orphan_norm_cells, [input_norm_cells...])
seen = set()
# Run dirs: argv[1:] override (round 10: point at the eval corpus alone
# for eval-targeted vocabulary mining); default = the training-era sweep.
_RUNS = sys.argv[1:] or ["outputs/unified_harness_v11",
                         "outputs/unified_harness_v8",
                         "outputs/unified_harness_emit_training",
                         "outputs/unified_harness_emit_evaluation"]
for run in _RUNS:
    for f in glob.glob(f"{run}/object/near_solve_parts/*.jsonl"):
        tid = os.path.basename(f)[:-6]
        if tid in seen or tid not in chal:
            continue
        try:
            r = json.loads(open(f).readline())
        except Exception:
            continue
        if r.get("failure_stage") != "matching":
            continue
        seen.add(tid)
        var = r.get("segmentation_variant") or "S1"
        try:
            pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                     for p in chal[tid]["train"]]
            seg = evaluate_variant(SegmentationVariant(var), pairs)
            for pi, (gi, go) in enumerate(pairs):
                ins, outs = seg.input_objects[pi], seg.output_objects[pi]
                corr = match_pair(ins, outs, gi, go, pair_index=pi)[0]
                out_by = {o.id: o for o in corr.output_objects}
                for d in extract_deltas(corr):
                    if d.input_object_id is None and d.output_object_ids:
                        o = out_by[d.output_object_ids[0]]
                        instances.append(
                            (tid, _norm(o.cells),
                             [_norm(a.cells) for a in ins]))
        except Exception:
            continue

print(f"unexplained orphan instances: {len(instances)} across "
      f"{len({t for t, _, _ in instances})} tasks", flush=True)

# --- search: which chain explains which instances (any source object)
explained = defaultdict(set)     # chain_key -> set of task ids
inst_hit = Counter()
all_chains = list(chains())
print(f"chains in catalog: {len(all_chains)}", flush=True)
for n, (tid, orphan, sources) in enumerate(instances):
    hit_any = False
    for ch in all_chains:
        for src in sources:
            try:
                res = apply_chain(ch, src)
            except Exception:
                res = None
            if res == orphan:
                explained[chain_key(ch)].add(tid)
                hit_any = True
                break
    inst_hit[bool(hit_any)] += 1
    if (n + 1) % 100 == 0:
        print(f"  {n+1}/{len(instances)}", flush=True)

rank = sorted(((len(v), k) for k, v in explained.items()), reverse=True)
go = [(k, n) for n, k in rank if n >= 5 and k != "identity"]
report = {
    "instances": len(instances),
    "instances_explained_by_some_chain": inst_hit[True],
    "chains_with_5plus_tasks": [{"chain": k, "tasks": n} for k, n in go],
    "top15": [{"chain": k, "tasks": n} for n, k in rank[:15]],
}
json.dump(report, open(os.environ.get("META_M2_OUT", "outputs/meta_m2_chains.json"), "w"), indent=1)
print(f"explained instances: {inst_hit[True]}/{len(instances)}")
for n, k in rank[:12]:
    print(f"  {n:4d} tasks  {k}")
print("GO" if go else "NO-GO", "for the synthesizer runtime at K=5")
print("report -> " + os.environ.get("META_M2_OUT", "outputs/meta_m2_chains.json") + "")
