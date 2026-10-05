import os, sys, time, json, tempfile
R = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
sys.path.insert(0, R)
os.environ["ARC_META_INDUCTION"] = "1"
import numpy as np
from cora_arc2026 import v15_sel as S          # puts the tti root on the path
from cora_tti import scoped_slot_fitting as SF
from cora_tti import constructive_dataset as CD
from cora_tti import constructive_vocabulary as CV
from geocat_arc.object_reasoning import meta_induction as MI, meta_ast as M
from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
from geocat_arc.object_reasoning.inducer import InductionConfig

def scoped_learner(orig):
    def learner(ast, pairs, slot):
        stages = list(ast[1]); nblocks = sum(1 for s in stages if s[0] == "Paint")
        nsel = sum(1 for s in stages if s[0] == "Select")
        if nblocks == 1 and nsel == 1:
            return orig(ast, pairs, slot)
        fitted, ev = SF.fit_induced_occurrences(ast, pairs)
        if fitted is None:
            return None
        path = None
        for o in SF.occurrences(ast):
            if o.slot_name == slot: path = o.ast_path
        if path is None: return None
        return fitted[1][path[0]][1][1][1][0]   # Map -> (Key, Lookup) -> Lookup args[0]
    return learner

CALLS = []
class Concept:
    def __init__(self, name, schema): self.name, self.schema = name, schema

def find_episode(seed0, n=200):
    for k in range(n):
        seed = seed0 + k * 100
        fam = CV.parse_family("(0,0)") if hasattr(CV, "parse_family") else None
        fam = S.G.parse_family(S.FAMILIES[k % 5])
        schema = CD.sample_target(seed, fam)
        grid_seeds = [seed * 97 + i for i in range(14)]
        concrete = CD.instantiate_tables(schema, [CD.generate_grid(s) for s in grid_seeds[:6]])
        if concrete is None: continue
        pairs, diag = CD.render_demonstrations(concrete, grid_seeds, min_demos=4)
        if len(pairs) < 4: continue
        fitted, ev = SF.fit_induced_occurrences(schema, pairs)
        if fitted is None: continue
        if SF.base_search_with_scoped_fitter(pairs)["exact"]: continue
        return schema, pairs, seed
    return None

import json as _j
fx = _j.load(open("fixtures.json"))[int(os.environ.get("FIX", "0"))]
seed = fx["seed"]; schema = M.ast_from_json(fx["schema"])
gs = [seed * 97 + i for i in range(30)]
concrete = CD.instantiate_tables(schema, [CD.generate_grid(s) for s in gs[:6]])
pairs, _ = CD.render_demonstrations(concrete, gs, min_demos=6)
print("fixture seed", seed, "demos", len(pairs))
train, held = pairs[:7], pairs[7]
def solve(overlay, tag):
    orig_icc = MI.induce_computed_candidates
    orig_learner = MI.SLOT_LEARNERS["Map[FeatureValue,Colour]"]
    MI.SLOT_LEARNERS["Map[FeatureValue,Colour]"] = scoped_learner(orig_learner)
    if True:
        def wrapped(train_pairs, deadline=None, concepts=(), concepts_only=False):
            left = None if deadline is None else round(deadline - time.monotonic(), 2)
            out = orig_icc(train_pairs, deadline=None, concepts=tuple(concepts) + tuple(overlay), concepts_only=concepts_only)
            CALLS.append((len(train_pairs), left, len(out[0]), out[1].as_dict()))
            return out
        MI.induce_computed_candidates = wrapped
    try:
        d = tempfile.mkdtemp(prefix=f"v17feas_{tag}_")
        eng = ObjectReasoningEngine(d, use_library=True, config=InductionConfig(budget_s=8.0))
        t = time.time(); res = eng.solve("task", [(np.asarray(a), np.asarray(b)) for a, b in train]); dt = time.time() - t
    finally:
        MI.induce_computed_candidates = orig_icc
        MI.SLOT_LEARNERS["Map[FeatureValue,Colour]"] = orig_learner
    sol = res.solution
    out = None
    if sol is not None:
        out = bool(np.array_equal(sol.apply_fn(np.asarray(held[0])), np.asarray(held[1])))
    pj = sol.program_json if sol else {}
    print(tag, "calls", CALLS[:8], "ncalls", len(CALLS)); CALLS.clear()
    print(tag, "all events", (res.induction.events if res.induction else [])[:30])
    print(tag, "accepted", sol is not None, "class", pj.get("program_class"), "concept", pj.get("concept"), "heldout_exact", out, "events", [e for e in (res.induction.events if res.induction else []) if "META" in e or "ACCEPT" in e or "PROMOTED" in e][:6], f"{dt:.1f}s")
    return res

solve((), "K*")
solve((Concept("cx_test", schema),), "K*+e")
