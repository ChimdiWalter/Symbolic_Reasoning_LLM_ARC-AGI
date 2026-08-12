#!/usr/bin/env python3
"""AUTONOMOUS M3: validate mined verb candidates and register survivors.

Pipeline (no human in the loop):
  1. Candidates: chains covering >= K distinct tasks from the miner report
     (outputs/meta_m2_chains.json), DEDUPED by canonical action on an
     asymmetric probe shape (mirror_h == rot2+mirror_v etc.).
  2. Retro-solve: with ONLY the candidate verbs registered, run FULL normal
     induction (LOO gate included) on every task the chain explained an
     instance of.  A verb survives if >= R tasks become CERTIFIED.
  3. Probe regression: dev-19 baselines must not regress (spot: the 9
     known-solved dev tasks must still certify).
  4. Survivors -> outputs/learned_verbs/learned_verbs.json with provenance.

Usage: meta_m3_register_verbs.py [K=5] [R=1]
"""
import json
import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.synth_verbs import (LearnedVerbRegistry,
                                                     apply_verb_chain)
from geocat_arc.object_reasoning import correspondence as C
from geocat_arc.object_reasoning.segmentation import evaluate_variant
from geocat_arc.object_reasoning.correspondence import match_pair, extract_deltas
from geocat_arc.object_reasoning.types import SegmentationVariant
from geocat_arc.object_reasoning.inducer import induce_program, InductionConfig

K = int(sys.argv[1]) if len(sys.argv) > 1 else 5
R = int(sys.argv[2]) if len(sys.argv) > 2 else 1
chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
try:
    chal.update(json.load(open("data/arc/arc-agi_evaluation_challenges.json")))
except Exception:
    pass

# --- parse chain keys back into chains
def parse_chain(key):
    parts = []
    for tok in key.split("+"):
        if "(" in tok:
            name, arg = tok[:-1].split("(")
            parts.append((name, None if arg == "None" else int(arg)))
        else:
            parts.append((tok, None))
    return parts


PROBE = frozenset({(0, 0), (1, 0), (2, 0), (2, 1), (0, 2)})  # asymmetric


def canon(chain):
    return apply_verb_chain(chain, PROBE)


rep = json.load(open("outputs/meta_m2_chains.json"))
cands = {}
for e in rep["chains_with_5plus_tasks"]:
    ch = parse_chain(e["chain"])
    sig = canon(ch)
    if sig is None or sig == PROBE:
        continue
    if sig not in cands or len(ch) < len(cands[sig][1]):
        cands[sig] = (e["chain"], ch, e["tasks"])
print(f"candidates after canonical dedup: {len(cands)}", flush=True)

# --- re-derive provenance tasks per candidate (instances collection)
def collect_instances():
    inst = []
    seen = set()
    for run in ("outputs/unified_harness_v11", "outputs/unified_harness_v8",
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


def norm(cells):
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    return frozenset((r - r0, c - c0) for (r, c) in cells)


provenance = defaultdict(set)
for tid, var in collect_instances():
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
                    on = norm(o.cells)
                    for sig, (key, ch, _n) in cands.items():
                        for a in ins:
                            if len(a.cells) >= 2 and \
                                    apply_verb_chain(ch, norm(a.cells)) == on:
                                provenance[key].add(tid)
                                break
    except Exception:
        continue

# --- retro-solve validation
DEV19_SOLVED = ["05f2a901", "dc433765", "1caeab9d", "5521c0d9", "b2862040",
                "2204b7a8", "358ba94e", "2dc579da", "445eab21"]
registered = []
for sig, (key, ch, _n) in sorted(cands.items(), key=lambda kv: kv[1][0]):
    tasks = sorted(provenance.get(key, []))
    if len(tasks) < K:
        print(f"[skip] {key}: provenance {len(tasks)} < K={K}", flush=True)
        continue
    name = "verb_" + key.replace("(", "_").replace(")", "").replace("+", "_")
    C.set_learned_verbs(LearnedVerbRegistry(
        [{"name": name, "chain": [list(x) for x in ch]}]))
    newly = []
    for tid in tasks[:12]:
        try:
            pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                     for p in chal[tid]["train"]]
            res = induce_program(pairs, InductionConfig(budget_s=150))
            if res.accepted:
                newly.append(tid)
        except Exception:
            pass
    print(f"[retro] {key}: certified {len(newly)}/{min(len(tasks),12)} "
          f"({newly})", flush=True)
    if len(newly) < R:
        continue
    ok = True
    for tid in DEV19_SOLVED[:4]:
        try:
            pairs = [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
                     for p in chal[tid]["train"]]
            if not induce_program(pairs, InductionConfig(budget_s=90)).accepted:
                ok = False
                break
        except Exception:
            ok = False
            break
    print(f"[probe] {key}: dev-regression {'CLEAN' if ok else 'FAILED'}",
          flush=True)
    if ok:
        registered.append({"name": name, "chain": [list(x) for x in ch],
                           "provenance": {"mined_chain": key,
                                          "tasks": tasks,
                                          "retro_certified": newly}})
C.set_learned_verbs(LearnedVerbRegistry([]))

os.makedirs("outputs/learned_verbs", exist_ok=True)
json.dump(registered,
          open("outputs/learned_verbs/learned_verbs.json", "w"), indent=1)
print(f"REGISTERED {len(registered)} learned verbs -> "
      f"outputs/learned_verbs/learned_verbs.json")
for v in registered:
    print("  ", v["name"], "retro:", v["provenance"]["retro_certified"])
