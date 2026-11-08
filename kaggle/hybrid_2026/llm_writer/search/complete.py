"""Neural-seeded completion: typed holes opened in recorded programs and filled jointly from all demonstrations.

Two completion mechanisms, both under a CPU-second budget and both ending in the existing executor:
- `relational`: a seed in the object-rule fragment becomes a relational sketch (`relational.py`) at the positions
  chosen by the ordering policy; a backend ("prolog": SWI-Prolog/CLP(FD), or "enum": ordinary enumeration) returns
  the completions consistent with the facts; each is lowered to a CORA program and executed. Seeds outside the
  fragment are counted as UNSUPPORTED_CONSTRUCT, never silently approximated.
- `holes` ("symbolic hole completion"): any seed (CORA or grid functions) gets one or two typed holes at its own
  positions; each hole's finite domain is enumerated in order and every filled program is executed. No fact model:
  the executor decides directly, at a higher cost per candidate.
Orderings (identical candidate spaces; only the order differs): "blind" (seeds in production order, holes in fixed
order), "evidence" (seeds by objective; holes by the seed's derivation trace or CORA's localization), "shuffled"
(seeds by rotated objectives; holes by ANOTHER seed's trace or localization). Expected test outputs never enter.
"""
from cora_neural_v2.rast import N, to_sexpr
from llm_writer.search import localize as LZ
from llm_writer.search import mutate_cora as MC
from llm_writer.search import relational as RL
from llm_writer.search.common import CPUBudget, Runner, behaviour_key, cpu_now
from llm_writer.search.objective import rank_key

ORDERS = ("blind", "evidence", "shuffled")
LOCAL_ACTION_OPS = ("recolor", "delete", "keep", "translate", "move_to", "move_until_adjacent",
                    "move_until_adjacent_to", "paint", "reflect", "rotate", "composite")


# ------------------------------------------------------------------ shared seed handling
def evaluate_seeds(task, seeds, runner, budget, seed_cost=None):
    out = []
    for i, s in enumerate(seeds):
        if budget.exhausted():
            break
        prog = getattr(s, "prog", s)
        res, new = runner.run(prog, origin="seed", op=f"seed:{getattr(s, 'id', i)}")
        if not new:
            budget.charge(seed_cost.get(res.key, res.cpu) if seed_cost else res.cpu)
        out.append((i, res))
    return out


def order_seeds(evaluated, order):
    usable = [(i, r) for i, r in evaluated if r.status != "INVALID"]
    if order == "blind":
        return [r for _, r in usable]
    if order == "evidence":
        return [r for _, r in sorted(usable, key=lambda t: rank_key(t[1].obj) + (t[0],))]
    objs = [r.obj for _, r in usable]
    rot = objs[1:] + objs[:1] if len(objs) > 1 else objs
    return [r for (_, r), o in sorted(zip(usable, rot), key=lambda t: rank_key(t[1]) + (t[0][0],))]


class Fits:
    """Distinct fitting behaviours found by a component (programs agreeing on the demonstrations but not on a test
    input are all kept), with the seeds' own fits kept apart."""

    def __init__(self, keep=16):
        self.keep, self.rows, self.seed = keep, {}, set()
        self.first_cpu = None

    def add_seed(self, res):
        if res.fits:
            self.seed.add(behaviour_key(res.ex.preds))

    def add(self, res, cpu, how):
        if not res.fits:
            return False
        bk = behaviour_key(res.ex.preds)
        if bk in self.rows or bk in self.seed or len(self.rows) >= self.keep:
            return False
        self.rows[bk] = (res, round(cpu, 3), how)
        if self.first_cpu is None:
            self.first_cpu = round(cpu, 3)
        return True

    def table(self, runner):
        out = []
        for bk, (r, cpu, how) in self.rows.items():
            out.append({"key": r.key, "program": runner.L.render(r.prog), "preds": r.preds(), "behaviour": bk,
                        "origin": r.origin, "parent": r.parent, "op": r.op, "cpu_at": cpu, "how": how,
                        "size": runner.L.size(r.prog), "_prog": r.prog})
        return out


# ------------------------------------------------------------------ facts per view (cached per task)
class FactsCache:
    """Relational facts of one task per view, with the domains built from CORA's demonstration-derived candidate
    lists and the puzzle's recorded programs. The first build of a view is charged to the arm that needs it; a later
    arm reusing it is charged the recorded cost."""

    def __init__(self, task, library, seed_progs=()):
        self.task, self.lib = task, library
        self.seed_progs = list(seed_progs)
        self.cache, self.cost = {}, {}

    def domains_for(self, view):
        sels = list(self.lib.lib.get("PRED") or [])
        acts = [a for a in (self.lib.pool.get("ACTION") or []) if a.op in LOCAL_ACTION_OPS]
        for p in self.seed_progs:
            try:
                v, rules, _ = RL.seed_parts(p)
            except RL.Unsupported:
                continue
            if v != view:
                continue
            sels += [s for s, _ in rules]
            acts += [a for _, a in rules]
        acts += [a for a in (self.lib.lib.get("ACTION") or []) if a.op in LOCAL_ACTION_OPS][:120]
        return sels, acts

    def get(self, view, budget=None):
        if view in self.cache:
            if budget is not None:
                budget.charge(self.cost[view])
            return self.cache[view]
        t0 = cpu_now()
        try:
            sels, acts = self.domains_for(view)
            f = RL.Facts(self.task, view, sels, acts)
        except RL.Unsupported as e:
            f = e
        except Exception as e:                             # noqa: BLE001 (an observation failure)
            f = RL.Unsupported(f"facts failed: {type(e).__name__}: {str(e)[:120]}")
            f.error = True
        self.cache[view] = f
        self.cost[view] = cpu_now() - t0
        return f


# ------------------------------------------------------------------ relational completion over seeds
def relational(task, seeds, cpu_s=20.0, order="evidence", backend="prolog", runner=None, library=None,
               facts_cache=None, sketches_per_seed=12, batch=12, per_sketch_cpu=2.0, max_sol=16, max_per=4,
               keep_fits=16, seed_cost=None, max_variants=4, suggest=None):
    """Relational completion of the seeds' sketches; returns fits, per-sketch statuses and accounting. `suggest`
    ((weights, focus)) replaces the seeds' own trace suggestions (the controller passes another seed's for the
    shuffled arm)."""
    if order not in ORDERS:
        raise ValueError(order)
    budget = CPUBudget(cpu_s)
    runner = runner or Runner(task, "cora")
    progs = [getattr(s, "prog", s) for s in seeds]
    lib = library or MC.Library(task, progs)
    fc = facts_cache or FactsCache(task, lib, progs)
    evaluated = evaluate_seeds(task, seeds, runner, budget, seed_cost)
    fits = Fits(keep_fits)
    for _, r in evaluated:
        fits.add_seed(r)
    ranked = order_seeds(evaluated, order)
    stats = {"seeds_tried": 0, "unsupported": {}, "sketches": 0, "statuses": {}, "solutions": 0, "lowered": 0,
             "executor_fits": 0, "fact_fits_not_executor_fits": 0, "backend_cpu_s": 0.0, "facts_cpu_s": 0.0,
             "first_fit_cpu": None}
    prepared = []
    it = iter(ranked)

    def prep_next():
        """Prepare the next seed of the ranking that is inside the fragment (lazily); False when none is left."""
        for r in it:
            try:
                parts = RL.seed_parts(r.prog)
            except RL.Unsupported as e:
                k = str(e).split(" (")[0][:60]
                stats["unsupported"][k] = stats["unsupported"].get(k, 0) + 1
                continue
            t0 = cpu_now()
            facts = fc.get(parts[0], budget if parts[0] in fc.cache else None)
            stats["facts_cpu_s"] += cpu_now() - t0
            if isinstance(facts, RL.Unsupported):
                k = str(facts)[:60]
                stats["unsupported"][k] = stats["unsupported"].get(k, 0) + 1
                continue
            try:
                rules, default = RL.term_of_seed(facts, parts)
            except RL.Unsupported as e:
                k = " ".join(str(e).split(" ")[:1] + str(e).split(" ")[-3:])[:60]
                stats["unsupported"][k] = stats["unsupported"].get(k, 0) + 1
                continue
            tr = RL.derivation(facts, rules, default)
            prepared.append((r, facts, rules, default, tr, RL.trace_suggest(tr, len(rules))))
            return True
        return False

    n = 0
    while not budget.exhausted():
        if len(prepared) <= n and not prep_next():
            break
        if order == "shuffled" and len(prepared) <= n + 1:
            prep_next()
        r, facts, rules, default, tr, w = prepared[n]
        n += 1
        # the sketches of the seed just prepared, in the policy's order
        stats["seeds_tried"] += 1
        if order == "blind":
            sks = RL.seed_sketches(facts, rules, default, r.key[:16])
        else:
            if suggest is not None:
                weights, focus = suggest
            elif order == "evidence":
                weights, focus = w, RL.implicated_rules(tr)
            else:
                other = prepared[n % len(prepared)] if len(prepared) > 1 else None
                weights = other[5] if other is not None and other[0].key != r.key else {}
                focus = RL.implicated_rules(other[4]) if weights else []
            sks = RL.order_sketches(RL.seed_sketches(facts, rules, default, r.key[:16], focus), weights)
        sks = sks[:sketches_per_seed]
        for b0 in range(0, len(sks), batch):
            if budget.exhausted():
                break
            chunk = sks[b0:b0 + batch]
            t0 = cpu_now()
            pre = [RL.precheck(facts, s) for s in chunk]
            if all(p is not None for p in pre):
                comps = pre
            elif backend == "prolog":
                from llm_writer.search import prolog as PR
                try:
                    comps, _, _info = PR.solve(facts, chunk, max_sol=max_sol, max_per=max_per,
                                               cpu_s=min(per_sketch_cpu, max(0.2, budget.left())))
                except Exception as e:                     # noqa: BLE001 (no swipl, a crash: an execution error)
                    comps = [RL.Completion("EXECUTION_ERROR", "prolog", reason=f"{type(e).__name__}: {e}"[:160])
                             for _ in chunk]
            else:
                comps = [RL.solve_enum(facts, s, max_sol, max_per, min(per_sketch_cpu, max(0.2, budget.left())))
                         for s in chunk]
            stats["backend_cpu_s"] += cpu_now() - t0
            for s, c in zip(chunk, comps):
                stats["sketches"] += 1
                stats["statuses"][c.status] = stats["statuses"].get(c.status, 0) + 1
                stats["solutions"] += len(c.solutions)
                for sol in c.solutions:
                    if budget.exhausted():
                        break
                    any_fit = False
                    for p in RL.lower(facts, sol, max_variants):
                        res, new = runner.run(p, origin=f"relational:{backend}", parent=r.key, op=s.label)
                        stats["lowered"] += new
                        if res.fits:
                            any_fit = True
                            if fits.add(res, budget.used(), f"relational/{backend}/{s.label}") and \
                                    stats["first_fit_cpu"] is None:
                                stats["first_fit_cpu"] = round(budget.used(), 3)
                    stats["executor_fits"] += any_fit
                    stats["fact_fits_not_executor_fits"] += not any_fit
    stats["cpu_s"] = round(budget.used(), 3)
    stats["budget_s"] = cpu_s
    stats["backend_cpu_s"] = round(stats["backend_cpu_s"], 3)
    stats["facts_cpu_s"] = round(stats["facts_cpu_s"], 3)
    stats["distinct_programs"] = len(runner.cache)
    return {"status": "FIT_FOUND" if fits.rows else ("NO_SEED_IN_FRAGMENT" if not prepared else "NO_NEW_FIT"),
            "order": order, "backend": backend, "fits": fits.table(runner), "stats": stats}


# ------------------------------------------------------------------ symbolic hole completion through the executor
def _uniq(xs, cur=None):
    seen, out = set(), []
    for x in xs:
        k = to_sexpr(x) if isinstance(x, N) else repr(x)
        if k in seen or (cur is not None and x == cur):
            continue
        seen.add(k)
        out.append(x)
    return out


def cora_holes(prog, lib, max_dom=48):
    """[(label, family, rule, [replacement programs])]: one typed hole per position, its finite domain in order."""
    from cora_neural_v2.rast import CMPS, SYMBOL_SETS
    out = []
    for q in MC.positions(prog):
        fam = MC.family_of(q)
        if fam is None:
            continue
        dom = []
        if q.kind in ("PRED", "ACTION", "COLOR", "VEC", "REF", "RENDER", "SCALAR", "REGION") and isinstance(q.value, N):
            dom = _uniq(list(lib.lib.get(q.kind) or []) + list(lib.pool.get(q.kind) or []), q.value)[:max_dom]
        elif q.kind == "int" and q.parent in MC.COLOR_INT_OPS:
            dom = [c for c in lib.colours if c != q.value]
        elif q.kind == "int" and q.parent == "vec":
            dom = [v for v in range(q.value - 3, q.value + 4) if v != q.value and -29 <= v <= 29]
        elif q.kind.startswith("sym:"):
            dom = [v for v in SYMBOL_SETS[q.kind[4:]] if v != q.value]
        elif q.kind == "cmp":
            dom = [c for c in CMPS if c != q.value]
        elif q.kind == "part_kind":
            from cora_neural_v2g4 import parts as PT
            dom = [k for k in PT.KINDS if k != q.value]
        elif q.kind == "part_colour":
            dom = [c for c in list(lib.colours) + ["own"] if c != q.value]
        elif q.kind == "pairs":
            keys = {p[0] for p in q.value}
            dom = [tuple(sorted(tuple(q.value) + ((k, c),))) for k in lib.colours if k not in keys for c in lib.colours]
        if not dom:
            continue
        out.append((f"{q.kind}@{'.'.join(map(str, q.path))}", fam, q.rule, (q.path, dom)))
    return out


def _fill(prog, hole):
    """Programs of one CORA hole (path, domain), in domain order."""
    path, dom = hole
    for v in dom:
        try:
            yield MC.replace(prog, path, v)
        except (IndexError, TypeError, ValueError):
            continue


def _fill_pair(prog, h1, h2, max_pair):
    """Programs of two disjoint CORA holes, both filled (at most max_pair)."""
    (p1, d1), (p2, d2) = h1, h2
    if p1[:len(p2)] == p2 or p2[:len(p1)] == p1:
        return
    n = 0
    for v1 in d1[:20]:
        for v2 in d2[:20]:
            try:
                yield MC.replace(MC.replace(prog, p1, v1), p2, v2)
            except (IndexError, TypeError, ValueError):
                continue
            n += 1
            if n >= max_pair:
                return


def gridfn_holes(prog, lib):
    """[(label, family, None, [programs])] for a grid-function program: every site's alternatives, re-checked."""
    import ast
    import copy
    from llm_writer.gridfn import adapter as GA
    from llm_writer.search import mutate_gridfn as MG
    tree = prog.checked.tree
    sites = MG._sites(tree)
    out = []
    for si, (fam, node, where, idx) in enumerate(sites):
        alts = []
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            alts = [("bool", None)]
        elif isinstance(node, ast.Constant) and isinstance(node.value, int):
            v = node.value
            alts = [("int", c) for c in (lib.colours if 0 <= v <= 9 else range(v - 2, v + 3)) if c != v]
        elif isinstance(node, ast.Compare):
            alts = [("cmp", o) for o in MG.CMP_OPS if not isinstance(node.ops[0], o)]
        elif fam == "TRANSFORM":
            alts = [("prim", n) for n in MG.substitutes(node.func.id)]
        elif fam == "OUTPUT":
            alts = [("wrap", w) for w in MG.WRAPS]
        if not alts:
            continue
        progs = []
        for kind, val in alts:
            t2 = copy.deepcopy(tree)
            f2, n2, w2, i2 = MG._sites(t2)[si]
            try:
                if kind == "bool":
                    n2.value = not n2.value
                elif kind == "int":
                    n2.value = val
                elif kind == "cmp":
                    n2.ops[0] = val()
                elif kind == "prim":
                    n2.func.id = val
                elif kind == "wrap":
                    n2.value = ast.Call(func=ast.Name(id=val, ctx=ast.Load()), args=[n2.value], keywords=[])
                progs.append(GA.parse(ast.unparse(ast.fix_missing_locations(t2))))
            except (ValueError, RecursionError, SyntaxError, AttributeError, IndexError):
                continue
        out.append((f"{fam}:{type(node).__name__}#{si}", fam, None, progs))
    return out


def _cands(prog, hole, language):
    return iter(hole) if language == "gridfn" else _fill(prog, hole)


def holes(task, seeds, language="cora", cpu_s=20.0, order="evidence", runner=None, library=None, pairs=True,
          max_pair=400, keep_fits=16, seed_cost=None, sep="", loc=None):
    """Symbolic hole completion: for each seed in the policy's order, its holes in the policy's order, every filler of
    a hole executed (then pairs of the two first holes, at most `max_pair` combinations)."""
    if order not in ORDERS:
        raise ValueError(order)
    budget = CPUBudget(cpu_s)
    runner = runner or Runner(task, language)
    progs = [getattr(s, "prog", s) for s in seeds]
    if library is None:
        if language == "gridfn":
            from llm_writer.search import mutate_gridfn as MG
            library = MG.Library(task, progs)
        else:
            library = MC.Library(task, progs)
    evaluated = evaluate_seeds(task, seeds, runner, budget, seed_cost)
    fits = Fits(keep_fits)
    for _, r in evaluated:
        fits.add_seed(r)
    ranked = order_seeds(evaluated, order)
    stats = {"seeds_tried": 0, "holes": 0, "candidates": 0, "executed": 0, "localized": 0, "first_fit_cpu": None}
    locs = []
    for n, r in enumerate(ranked):
        if budget.exhausted():
            break
        if r.fits:
            continue
        hs = gridfn_holes(r.prog, library) if language == "gridfn" else cora_holes(r.prog, library)
        if not hs:
            continue
        stats["seeds_tried"] += 1
        if order != "blind":
            if loc is not None:
                use = loc
            else:
                own = LZ.localize(task, r, sep)
                stats["localized"] += 1
                locs.append(own)
                use = own if order == "evidence" else (locs[-2] if len(locs) > 1 else LZ.uniform_loc())
            fw, rw = use["weights"], use["rules"]
            base = {id(h): j for j, h in enumerate(hs)}
            hs = sorted(hs, key=lambda h: (-(fw.get(h[1], 0.0) + (rw.get(h[2], 0.0) if h[2] is not None else 0.0)),
                                           base[id(h)]))
        groups = [(h[0], _cands(r.prog, h[3], language)) for h in hs]
        if pairs and language == "cora" and len(hs) >= 2:
            groups.append((f"{hs[0][0]}+{hs[1][0]}", _fill_pair(r.prog, hs[0][3], hs[1][3], max_pair)))
        for label, cands in groups:
            if budget.exhausted():
                break
            stats["holes"] += 1
            for c in cands:
                if budget.exhausted():
                    break
                stats["candidates"] += 1
                if language == "cora":
                    from cora_neural_hybrid import execute as EX
                    try:
                        if not EX.check(c)[0]:
                            continue
                    except Exception:                      # noqa: BLE001
                        continue
                res, new = runner.run(c, origin="holes", parent=r.key, op=label)
                stats["executed"] += new
                if fits.add(res, budget.used(), f"holes/{label}") and stats["first_fit_cpu"] is None:
                    stats["first_fit_cpu"] = round(budget.used(), 3)
    stats["cpu_s"] = round(budget.used(), 3)
    stats["budget_s"] = cpu_s
    stats["distinct_programs"] = len(runner.cache)
    return {"status": "FIT_FOUND" if fits.rows else "NO_NEW_FIT", "order": order, "language": language,
            "fits": fits.table(runner), "stats": stats}


__all__ = ["relational", "holes", "FactsCache", "Fits", "ORDERS"]
