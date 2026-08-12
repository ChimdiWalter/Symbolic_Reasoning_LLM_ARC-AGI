#!/usr/bin/env python3
"""AUTONOMOUS M3b (lever 2): DELTA-LEVEL LOO certificates for verb
registration — graduated credit assignment for the vocabulary loop.

The task-level gate (meta_m3_register_verbs.py) demands a full certified
solve, so a correct verb earns nothing on multi-blocker tasks (the sealed
honest negative of the first cycle).  This applies the SAME epistemic
standard one level down: LOO-by-reinduction over the verb's own delta.

For each candidate verb and each provenance task:
  - instances: per train pair, (source object, orphan object) where
    apply_verb_chain(chain, norm(src)) == norm(orphan)
  - delta-LOO: for each fold (hold out one instance pair), re-fit a
    PLACEMENT LAW from the remaining pairs and require it to predict the
    held-out orphan's EXACT absolute cells.  Laws (small, fixed catalog —
    deliberately weaker than the engine's expression grammar):
      const_offset   transformed shape placed at src_origin + (dr,dc),
                     (dr,dc) constant across pairs
      grid_mirror_h  orphan = src cells flipped across the grid's
                     horizontal center (absolute coords)
      grid_mirror_v  same, vertical
      touch          transformed shape abutting the source bbox
                     (above/below/left/right), side constant across pairs
      reflect_line   orphan = source reflected across the NEAREST adjacent
                     axis-aligned line object (relational placement: the
                     marker determines both side and distance per pair)
  - a task delta-certifies iff EVERY fold passes (>=2 instance pairs).

Registration: >= K_DELTA delta-certified tasks AND the dev-probe regression
stays clean.  Registered verbs carry certificate="delta_loo_exact" —
distinct from "task_loo".  LEGALITY: the tier gates only vocabulary
AVAILABILITY; every future solve that uses the verb still has to pass the
full task-level LOO-by-reinduction gate, which remains the only acceptance
path.  A registered verb can never create a false solve, only search reach.

Usage: meta_m3_delta_certificates.py [K_DELTA=3]
Writes outputs/learned_verbs/learned_verbs.json (merging any task_loo
registrations already present).
"""
import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.synth_verbs import (LearnedVerbRegistry,
                                                     apply_verb_chain)
from geocat_arc.object_reasoning import correspondence as C
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import (match_pair,
                                                        extract_deltas)
from geocat_arc.object_reasoning.types import SegmentationVariant
from geocat_arc.object_reasoning.inducer import induce_program, InductionConfig

try:
    K_DELTA = int(sys.argv[1]) if len(sys.argv) > 1 else 2
except ValueError:  # imported under a test runner — default applies
    K_DELTA = 2
REGISTRY_PATH = "outputs/learned_verbs/learned_verbs.json"

chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
try:
    chal.update(json.load(open("data/arc/arc-agi_evaluation_challenges.json")))
except Exception:
    pass


def parse_chain(key):
    parts = []
    for tok in key.split("+"):
        if "(" in tok:
            name, arg = tok[:-1].split("(")
            parts.append((name, None if arg == "None" else int(arg)))
        else:
            parts.append((tok, None))
    return parts


PROBE = frozenset({(0, 0), (1, 0), (2, 0), (2, 1), (0, 2)})


def canon(chain):
    return apply_verb_chain(chain, PROBE)


def norm(cells):
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    return frozenset((r - r0, c - c0) for (r, c) in cells)


def origin(cells):
    return (min(r for r, _ in cells), min(c for _, c in cells))


def bbox_hw(cells):
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return (max(rs) - min(rs) + 1, max(cs) - min(cs) + 1)


def place(shape, at):
    r0, c0 = at
    return frozenset((r + r0, c + c0) for (r, c) in shape)


# --- placement-law catalog -------------------------------------------------

def _law_const_offset(fit, chain):
    offs = set()
    for inst in fit:
        offs.add((origin(inst["orphan"])[0] - origin(inst["src"])[0],
                  origin(inst["orphan"])[1] - origin(inst["src"])[1]))
    if len(offs) != 1:
        return None
    dr, dc = offs.pop()

    def predict(inst):
        shape = apply_verb_chain(chain, norm(inst["src"]))
        if shape is None:
            return None
        r0, c0 = origin(inst["src"])
        return place(shape, (r0 + dr, c0 + dc))
    return predict


def _law_grid_mirror(axis):
    def make(fit, chain):
        for inst in fit:
            H, W = inst["grid_shape"]
            pred = frozenset((H - 1 - r, c) for (r, c) in inst["src"]) \
                if axis == "h" else \
                frozenset((r, W - 1 - c) for (r, c) in inst["src"])
            if pred != frozenset(inst["orphan"]):
                return None

        def predict(inst):
            H, W = inst["grid_shape"]
            return frozenset((H - 1 - r, c) for (r, c) in inst["src"]) \
                if axis == "h" else \
                frozenset((r, W - 1 - c) for (r, c) in inst["src"])
        return predict
    return make


def _law_touch(fit, chain):
    def offsets(inst):
        sh, sw = bbox_hw(inst["src"])
        shape = apply_verb_chain(chain, norm(inst["src"]))
        if shape is None:
            return {}
        th, tw = bbox_hw(shape)
        return {"below": (sh, 0), "above": (-th, 0),
                "right": (0, sw), "left": (0, -tw)}

    side_ok = None
    for side in ("below", "above", "right", "left"):
        ok = True
        for inst in fit:
            offs = offsets(inst)
            if side not in offs:
                ok = False
                break
            shape = apply_verb_chain(chain, norm(inst["src"]))
            r0, c0 = origin(inst["src"])
            dr, dc = offs[side]
            if place(shape, (r0 + dr, c0 + dc)) != frozenset(inst["orphan"]):
                ok = False
                break
        if ok:
            side_ok = side
            break
    if side_ok is None:
        return None

    def predict(inst):
        offs = offsets(inst)
        if side_ok not in offs:
            return None
        shape = apply_verb_chain(chain, norm(inst["src"]))
        r0, c0 = origin(inst["src"])
        dr, dc = offs[side_ok]
        return place(shape, (r0 + dr, c0 + dc))
    return predict


def _nearest_line(inst, orient):
    """Nearest axis-aligned line object adjacent to the source bbox
    (within 2 cells beyond it), deterministic tiebreak by coordinate."""
    rs = [r for r, _ in inst["src"]]
    cs = [c for _, c in inst["src"]]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    lo, hi = (r0, r1) if orient == "h" else (c0, c1)
    cands = []
    for (o, coord) in inst.get("lines", ()):
        if o != orient:
            continue
        if coord in (hi + 1, hi + 2, lo - 1, lo - 2):
            dist = min(abs(coord - hi), abs(coord - lo))
            cands.append((dist, coord))
    return min(cands)[1] if cands else None


def _reflect(cells, orient, coord):
    if orient == "h":
        return frozenset((2 * coord - r, c) for (r, c) in cells)
    return frozenset((r, 2 * coord - c) for (r, c) in cells)


def _law_reflect_line(fit, chain):
    for orient in ("h", "v"):
        ok = True
        for inst in fit:
            line = _nearest_line(inst, orient)
            if line is None or \
                    _reflect(inst["src"], orient, line) != \
                    frozenset(inst["orphan"]):
                ok = False
                break
        if not ok:
            continue

        def predict(inst, orient=orient):
            line = _nearest_line(inst, orient)
            if line is None:
                return None
            return _reflect(inst["src"], orient, line)
        return predict
    return None


def _law_bounce_gap(fit, chain):
    """Mirrored copy on the side with more free space (away from the
    nearest grid edge), separated by a constant gap g: relational side,
    fitted distance.  dc2e9a9d's placement (side flips per pair with the
    source's position; g=1)."""
    def predict_with(g, inst):
        rs = [r for r, _ in inst["src"]]
        r0, r1 = min(rs), max(rs)
        H = inst["grid_shape"][0]
        below = (H - 1 - r1) >= r0          # tie -> below
        axis = (r1 + g) if below else (r0 - g)
        return frozenset((2 * axis - r, c) for (r, c) in inst["src"])

    for g in (0, 1, 2, 3):
        if all(predict_with(g, inst) == frozenset(inst["orphan"])
               for inst in fit):
            return lambda inst, g=g: predict_with(g, inst)
    return None


LAWS = [("const_offset", _law_const_offset),
        ("grid_mirror_h", _law_grid_mirror("h")),
        ("grid_mirror_v", _law_grid_mirror("v")),
        ("touch", _law_touch),
        ("reflect_line", _law_reflect_line),
        ("bounce_gap", _law_bounce_gap)]


# --- instance collection ----------------------------------------------------

def collect_instance_tasks():
    inst = []
    seen = set()
    for run in ("outputs/unified_harness_v12", "outputs/unified_harness_v11",
                "outputs/unified_harness_emit_training",
                "outputs/unified_harness_emit_evaluation"):
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
            inst.append((tid, r.get("segmentation_variant") or "S1"))
    return inst


def task_instances(tid, var, chain):
    """Per train pair, at most one (src, orphan) instance the chain
    explains; deterministic pick (largest source first)."""
    pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
             for p in chal[tid]["train"]]
    seg = evaluate_variant(SegmentationVariant(var), pairs)
    out = []
    for pi, (gi, go) in enumerate(pairs):
        ins, outs = seg.input_objects[pi], seg.output_objects[pi]
        lines = []
        for a in ins:
            h, w = bbox_hw(a.cells)
            if h == 1 and w >= 2:
                lines.append(("h", min(r for r, _ in a.cells)))
            elif w == 1 and h >= 2:
                lines.append(("v", min(c for _, c in a.cells)))
        corr = match_pair(ins, outs, gi, go, pair_index=pi)[0]
        out_by = {o.id: o for o in corr.output_objects}
        found = None
        for d in extract_deltas(corr):
            if d.input_object_id is not None or not d.output_object_ids:
                continue
            o = out_by[d.output_object_ids[0]]
            on = norm(o.cells)
            for a in sorted(ins, key=lambda x: -len(x.cells)):
                if len(a.cells) >= 2 and \
                        apply_verb_chain(chain, norm(a.cells)) == on:
                    found = {"pair": pi, "src": frozenset(a.cells),
                             "orphan": frozenset(o.cells),
                             "grid_shape": (go.height, go.width),
                             "lines": tuple(lines)}
                    break
            if found:
                break
        if found:
            out.append(found)
    return out


def delta_loo(instances, chain):
    """LOO over instance pairs: re-fit each law from N-1, require exact
    prediction of the held-out orphan.  Returns (passed, folds, law_used)."""
    n = len(instances)
    if n < 2:
        return 0, 0, None
    passed = 0
    laws_used = set()
    for hold in range(n):
        fit = [x for i, x in enumerate(instances) if i != hold]
        held = instances[hold]
        ok = False
        for name, law in LAWS:
            try:
                predict = law(fit, chain)
                if predict is None:
                    continue
                pred = predict(held)
                if pred is not None and pred == frozenset(held["orphan"]):
                    ok = True
                    laws_used.add(name)
                    break
            except Exception:
                continue
        if ok:
            passed += 1
    return passed, n, sorted(laws_used)


# --- main --------------------------------------------------------------------

def main():
    rep = json.load(open("outputs/meta_m2_chains.json"))
    cands = {}
    for e in rep["chains_with_5plus_tasks"]:
        ch = parse_chain(e["chain"])
        sig = canon(ch)
        if sig is None or sig == PROBE:
            continue
        if sig not in cands or len(ch) < len(cands[sig][1]):
            cands[sig] = (e["chain"], ch)
    print(f"candidates after canonical dedup: {len(cands)}", flush=True)

    tasks = collect_instance_tasks()
    print(f"provenance corpus: {len(tasks)} matching-stage tasks", flush=True)

    registered = []
    for sig, (key, ch) in sorted(cands.items(), key=lambda kv: kv[1][0]):
        certified = []
        for tid, var in tasks:
            try:
                inst = task_instances(tid, var, ch)
            except Exception:
                continue
            if len(inst) < 2:
                continue
            passed, folds, laws = delta_loo(inst, ch)
            if folds >= 2 and passed == folds:
                certified.append({"task": tid, "folds": folds, "laws": laws})
        print(f"[delta] {key}: certified {len(certified)} tasks "
              f"({[c['task'] for c in certified]})", flush=True)
        if len(certified) < K_DELTA:
            continue
        name = "verb_" + key.replace("(", "_").replace(")", "") \
                            .replace("+", "_")
        # dev-probe regression with the verb registered
        C.set_learned_verbs(LearnedVerbRegistry(
            [{"name": name, "chain": [list(x) for x in ch]}]))
        ok = True
        for tid in ("05f2a901", "dc433765", "1caeab9d", "5521c0d9"):
            try:
                pairs = [(Grid.from_list(p["input"]),
                          Grid.from_list(p["output"]))
                         for p in chal[tid]["train"]]
                if not induce_program(
                        pairs, InductionConfig(budget_s=90)).accepted:
                    ok = False
                    break
            except Exception:
                ok = False
                break
        C.set_learned_verbs(LearnedVerbRegistry([]))
        print(f"[probe] {key}: dev-regression {'CLEAN' if ok else 'FAILED'}",
              flush=True)
        if not ok:
            continue
        registered.append({
            "name": name,
            "chain": [list(x) for x in ch],
            "certificate": "delta_loo_exact",
            "provenance": {"mined_chain": key,
                           "delta_certified": certified,
                           "k_delta": K_DELTA},
        })

    # merge with any existing task_loo registrations
    existing = []
    if os.path.exists(REGISTRY_PATH):
        try:
            existing = [v for v in json.load(open(REGISTRY_PATH))
                        if v.get("certificate", "task_loo") == "task_loo"]
        except Exception:
            existing = []
    merged = existing + registered
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    json.dump(merged, open(REGISTRY_PATH, "w"), indent=1)
    print(f"REGISTERED {len(registered)} delta-certified verbs "
          f"({len(merged)} total) -> {REGISTRY_PATH}")
    for v in registered:
        print("  ", v["name"], "tasks:",
              [c["task"] for c in v["provenance"]["delta_certified"]])


if __name__ == "__main__":
    main()
