"""Feasibility of further removed operations (EVALUATOR SIDE; no task, no arm).

    python -I -m cas.feasibility GROUP OUT.json        GROUP: one key of GROUPS below

For every candidate removal R (a set of arc-dsl primitives taken out of A2's grammar, as S1 took out compress,
downscale, trim and upscale) and every operation x in R:
1. membership: the structures of S1's schema language SIGMA (cgrow/schema.py, unchanged) that equal x's arc-dsl
   reference on 40 probe grids (seed 515) and on S1's 40 reference probes (seed 99), at each parameter value of x;
2. novelty, with S1's own gate (s1.Gates.novelty, reimplemented line for line below and checked against S1's
   recorded gate results): for each such structure and each of its parameter values, A2's bottom-up search over
   G0 = A2 grammar minus R on the 12 probe-grid pairs EP.SIG_PROBES[:12], budget 200,000 executions, 10 CPU-s cap;
   the structure is a duplicate (search shortcut) when every defined parameter value is reproduced;
3. expressibility (S1's evaluator-only check, cgrow/expressibility.py): a 3,000,000-execution search on 10 probe
   grids for a G0 program equal to x (finds macros up to about cost 12; informs the matched-search baseline).
A removal is feasible when, for every x in R, at least one structure equals x at every parameter value and is not
a duplicate. Writes one JSON record per group.
"""
import json
import sys
import time

from cas import env as E                                                       # noqa: F401  (paths first)
from cgrow import lang0 as L0, search as S, episode as EP, schema as SG, probes as PR   # noqa: E402
from a2 import arcdsl as D, bus as B                                            # noqa: E402

DIHEDRAL = ("hmirror", "vmirror", "dmirror", "cmirror", "rot90", "rot180", "rot270")
S1_REMOVED = ("compress", "downscale", "trim", "upscale")
PAIRS = tuple((a, b) for a in range(10) for b in range(a + 1, 10))
PARAMS = {"compress": [()], "trim": [()], "downscale": [(2,), (3,)], "upscale": [(2,), (3,)],
          "hupscale": [(2,), (3,)], "vupscale": [(2,), (3,)], "switch": [p for p in PAIRS],
          "replace": [(a, b) for a in range(10) for b in range(10) if a != b]}
for _x in DIHEDRAL:
    PARAMS[_x] = [()]

#: candidate removals (name -> removed primitives); the chosen worlds and the alternatives that document limits
GROUPS = {
    "W1_s1": {"W1": S1_REMOVED},
    "W2_orientation": {"W2": ("hmirror", "vmirror", "dmirror", "cmirror", "rot90", "rot270")},
    "W3_stretch_swap": {"W3": ("hupscale", "vupscale", "switch")},
    "W2_all_dihedral": {"W2": DIHEDRAL},
    # the chosen W2 after the boundary agreed with the companion study (horizontal reflection is never removed, so
    # hmirror and vmirror stay, and with them rot180 = hmirror(vmirror(I))): the other coset of the symmetry group
    "W2_quarter_turn": {"W2": ("dmirror", "cmirror", "rot90", "rot270")},
    "alternatives": {
        "all_dihedral": DIHEDRAL,
        "reflections_only": ("hmirror", "vmirror", "dmirror", "cmirror"),
        "rotations_only": ("rot90", "rot180", "rot270"),
        "rot90_only": ("rot90",),
        "hmirror_only": ("hmirror",),
        "rot180_only": ("rot180",),
        "hupscale_only": ("hupscale",),
        "vupscale_only": ("vupscale",),
        "replace_and_switch": ("replace", "switch"),
        "s1_plus_stretch": S1_REMOVED + ("hupscale", "vupscale"),
    },
}
MEMBER_PROBES = PR.probe_grids(40, seed=515, min_side=1, max_side=10) + PR.probe_grids(40, seed=99, min_side=2,
                                                                                        max_side=10)
SWITCH_SAMPLE = 6      # colour pairs of switch / replace checked in the alternatives group (all 45 in W3)


def ref_out(fn, x, p):
    try:
        y = fn(x, *p)
    except Exception:                                                           # noqa: BLE001
        return None
    return y if D.valid(y) and D.tag(y) == "G" else None


def members(name, params):
    """SIGMA structures equal to the reference at each parameter value: {param: [(sid, theta), ...]}."""
    fn = L0.reference_fn(name)
    out = {}
    for p in params:
        want = [(x, ref_out(fn, x, p)) for x in MEMBER_PROBES]
        defined = [(x, y) for x, y in want if y is not None]
        hits = []
        for st in SG.structures():
            for th in st.thetas():
                ok = True
                for x, y in defined:
                    try:
                        v = st(x, *th)
                    except (IndexError, ValueError, ZeroDivisionError):
                        v = None
                    if v != y:
                        ok = False
                        break
                if ok:
                    hits.append((st.sid, list(th)))
        out[str(list(p))] = {"defined_probes": len(defined), "structures": hits}
    return out


def novelty(st, g0):
    """S1's gate (cgrow/s1.py Gates.novelty), with the grammar passed in."""
    t0 = time.process_time()
    wit, defined, rows = [], 0, []
    for th in st.thetas():
        pairs = [(x, st(x, *th)) for x in EP.SIG_PROBES[:12]]
        pairs = [(x, y) for x, y in pairs if y is not None and D.valid(y)]
        if len(pairs) < 4:
            continue
        defined += 1
        r = S.run(g0(), pairs[:-1], [pairs[-1][0]], budget=EP.DUP_BUDGET, cpu_cap=10.0, want=1)
        hit = bool(r["fit"] and r["preds"] and r["preds"][0][0] == pairs[-1][1])
        rows.append({"theta": list(th), "reproduced": hit, "program": r["program"] if hit else None,
                     "level_complete": r["level_complete"], "stop": r["stop"], "calls": r["calls"],
                     "cpu_s": r["cpu_s"]})
        if hit:
            wit.append({"theta": list(th), "g0_program": r["program"]})
    return {"duplicate": bool(defined) and len(wit) == defined, "witnesses": wit, "defined_thetas": defined,
            "searches": rows, "cpu_s": round(time.process_time() - t0, 3)}


def expressible(name, p, removed, budget=3_000_000, cpu_cap=120.0):
    """S1's evaluator-only expressibility check (cgrow/expressibility.py main), for one operation and parameter."""
    g = L0.build_g0(removed)
    fn = L0.reference_fn(name)
    pairs = []
    for x in PR.probe_grids(10):
        y = ref_out(fn, x, p)
        if y is not None:
            pairs.append((x, y))
    t0 = time.process_time()
    r = B.search(g, pairs[:-1], [pairs[-1][0]], budget=budget, max_size=30, cpu_cap=cpu_cap, want=1)
    ok = bool(r.solved) and bool(r.preds) and tuple(map(tuple, r.preds[0][0])) == pairs[-1][1]
    return {"param": list(p), "n_probes": len(pairs), "found": [str(f) for f in r.fits[:2]], "query_ok": ok,
            "level": r.level, "stop": r.stop, "calls": r.calls, "cpu_s": round(time.process_time() - t0, 1)}


class G0:
    def __init__(self, removed):
        self.g = L0.build_g0(removed)

    def __call__(self):
        import copy
        g = copy.copy(self.g)
        g.prods, g.costs = list(self.g.prods), dict(self.g.costs)
        return g


def deep_expressible(name, p, removed):
    """The same check at about the matched-search depth (no execution budget, 150 CPU-s): evaluator-only."""
    return expressible(name, p, removed, budget=10 ** 9, cpu_cap=150.0)


DEEP = {"W1": S1_REMOVED, "W2": DIHEDRAL, "W3": ("hupscale", "vupscale", "switch"),
        "W2_quarter_turn": ("dmirror", "cmirror", "rot90", "rot270")}
DEEP_PARAMS = {"switch": [(0, 1), (0, 5)]}


def deep(out, only=None):
    res = {"note": "evaluator-only G0 macro search on 10 probe grids, about the matched-search depth", "worlds": {}}
    for w, removed in DEEP.items():
        if (only and w != only) or (not only and w == "W2_quarter_turn"):
            continue
        for x in removed:
            for p in DEEP_PARAMS.get(x, PARAMS[x]):
                r = deep_expressible(x, p, removed)
                res["worlds"].setdefault(w, {}).setdefault(x, []).append(r)
                print(json.dumps({"world": w, "op": x} | r), flush=True)
                E.dump(out, res)


def deep_switch(out):
    """Finding 6 of the independent review: the deep check's probe grids hold no colour 0, so replace(I, b, ZERO)
    passed as switch. Re-run for switch on 10 probe grids that contain both colours of the pair (seed 515 grids),
    under W3's G0, at the matched-search depth."""
    res = {"note": "evaluator-only deep G0 search for switch on probes containing both colours", "rows": []}
    removed = ("hupscale", "vupscale", "switch")
    g = L0.build_g0(removed)
    fn = L0.reference_fn("switch")
    for p in ((0, 1), (0, 5), (1, 2)):
        grids = [x for x in PR.probe_grids(60, seed=515, min_side=2, max_side=10)
                 if any(p[0] in r for r in x) and any(p[1] in r for r in x)][:10]
        pairs = [(x, fn(x, *p)) for x in grids]
        t0 = time.process_time()
        r = B.search(g, pairs[:-1], [pairs[-1][0]], budget=10 ** 9, max_size=30, cpu_cap=150.0, want=1)
        ok = bool(r.solved) and bool(r.preds) and tuple(map(tuple, r.preds[0][0])) == pairs[-1][1]
        row = {"param": list(p), "n_probes": len(pairs), "probes_with_colour_0": sum(any(0 in rr for rr in x) for x in grids),
               "found": [str(f) for f in r.fits[:2]], "query_ok": ok, "level": r.level, "stop": r.stop,
               "calls": r.calls, "cpu_s": round(time.process_time() - t0, 1)}
        res["rows"].append(row)
        print(json.dumps(row), flush=True)
        E.dump(out, res)


def check_world(name, removed, full=True):
    t0 = time.process_time()
    g0 = G0(removed)
    by_sid = SG.by_sid()
    ops = {}
    for x in removed:
        params = PARAMS[x]
        if not full and len(params) > SWITCH_SAMPLE:
            params = params[:SWITCH_SAMPLE]
        mem = members(x, params)
        sids = sorted({sid for v in mem.values() for sid, _ in v["structures"]})
        nov = {sid: novelty(by_sid[sid], g0) for sid in sids}
        # x is re-creatable without a shortcut when, at every parameter value, some non-duplicate structure equals it
        per_param = {p: [sid for sid, _ in v["structures"] if not nov[sid]["duplicate"]] for p, v in mem.items()}
        ok = all(per_param.values())
        rec = {"members": mem, "novelty": nov, "nonduplicate_members_by_param": per_param, "feasible": ok}
        if full and x not in ("switch", "replace"):
            rec["expressibility"] = [expressible(x, p, removed) for p in params]
        ops[x] = rec
        print(json.dumps({"world": name, "op": x, "feasible": ok, "structures": sids,
                          "duplicates": [s for s in sids if nov[s]["duplicate"]]}), flush=True)
    return {"removed": list(removed), "g0_productions": len(g0.g.prods), "ops": ops,
            "feasible": all(v["feasible"] for v in ops.values()), "cpu_s": round(time.process_time() - t0, 1)}


def main(group, out):
    res = {"group": group, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "worlds": {}}
    for name, removed in GROUPS[group].items():
        res["worlds"][name] = check_world(name, removed, full=group != "alternatives")
        E.dump(out, res)
    res["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    E.dump(out, res)


if __name__ == "__main__":
    if sys.argv[1] == "deep":
        deep(sys.argv[2], *(sys.argv[3:4]))
    elif sys.argv[1] == "deep_switch":
        deep_switch(sys.argv[2])
    else:
        main(sys.argv[1], sys.argv[2])
