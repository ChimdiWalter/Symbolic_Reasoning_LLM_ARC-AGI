"""Item-2 v1.8: the no-oracle extension proposer.

Builds candidate semantic extensions from three sources only: the training
demonstrations, the frozen reasoner's own failure frontier on them, and K's
frozen semantics. Design: records/ITEM2_V18_PROPOSER_DESIGN.md.

The mechanism is residual peeling over K's own blocks. Every block of a
meta-AST program reads the input grid and only Paint writes, so a program
is a stack of paint layers and a later layer overwrites an earlier one. The
occurrence-scoped fitter demands that the layers jointly explain the
change, so on a task that needs two layers every one of K's 200 programs
fails; but a K block that obeys every fitter rule on its own regions while
covering only part of the change is a partial executable structure. Those
partial blocks are candidate top layers, and a lower K block is proposed
under a top only if it covers the top's residual consistently on the cells
the top does not own. Nothing here reads a target, a candidate pair, a
seed, a family, a task identifier or a held-out output, and nothing is
installed: the selected schema goes to the v1.7 compiler.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from types import SimpleNamespace

from cora_arc2026 import v13_gen as G
from cora_arc2026 import v15_sel as S
from cora_arc2026 import v16_cfr as C
from cora_arc2026 import v17_compiler as X

VERSION = "1.8.0"
FORMAT_INPUT = "cora-proposer-input/1"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FROZEN_D = os.path.join(HERE, "outputs", "tti", "v18_frozen_d.json")

#: frozen bounds (design record section 4)
LIMITS = {"depths": [2, 3], "selects_per_block": 1, "max_top": 32, "max_lower": 16,
          "max_top3": 8, "max_mid": 8, "max_bottom3": 16, "max_proposals": 256,
          "max_probed": 32, "wall_s": 180.0}

FAILURE_CLASSES = (
    "K_ALREADY_SOLVES", "NO_PROPOSAL", "PROPOSAL_LIMIT", "UNTYPEABLE_PROPOSAL",
    "DUPLICATE_EXISTING_SEMANTICS", "NO_VERIFIABLE_PROPOSAL", "SELECTION_ABSTAINED",
    "COMPILE_FAILURE", "ENGINE_REJECTED", "LOO_FAILURE", "LEAKAGE_FAILURE",
    "RESOURCE_EXHAUSTED", "SUCCESS")
INFRASTRUCTURE = frozenset({"RESOURCE_EXHAUSTED", "COMPILE_FAILURE", "UNTYPEABLE_PROPOSAL",
                            "LEAKAGE_FAILURE"})
ARMS = ("FAILURE_CONDITIONED", "DEMO_ONLY", "SHUFFLED_FRONTIER", "NO_RESPONSE", "PURE")
SELECTION_LEVELS = ("VERIFICATION_UNIQUE", "P0", "D", "MDL", "ABSTAINED")
STATUSES = ("FULL", "PARTIAL", "CONFLICT")
K_CLASSES = ("K_EXACT", "K_CONSISTENT_INEXACT", "K_NO_CONSISTENT")


class LeakageError(Exception):
    """A forbidden field or value in the proposer input."""


class ResourceExhausted(Exception):
    """The proposer call ran past its wall-time bound."""


def _sf():
    from cora_tti import scoped_slot_fitting as SF
    return SF


def _meta():
    return X._meta()


def proposer_sha256() -> str:
    with open(__file__, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def codes() -> tuple:
    return tuple(_sf().FIT_FAILURES)


# --------------------------------------------------------------------------
# K's blocks and their semantics on the demonstrations
# --------------------------------------------------------------------------

def k_blocks() -> list:
    """K's 200 blocks (partition, predicate, feature) in K's own order."""
    out = []
    for schema in _sf().baseline_single_block_schemas():
        st = schema[1]
        out.append((st[0][1][0], st[1][1][0], st[2][1][0][1][0]))
    return out


def grammar() -> dict:
    M, _ = _meta()
    return {"max_blocks": 3, "selects_per_block": 1, "partitions": sorted(M.PARTITIONS),
            "predicates": sorted(M.PREDICATES), "features": list(M.KEY_FEATURES)}


def compose(indices, blocks=None):
    """The composition of K blocks, first index painted first."""
    from cora_arc2026 import v15_sel as _S
    blocks = blocks or k_blocks()
    return _S.CV.ast_from_blocks([(blocks[i][0], (blocks[i][1],), blocks[i][2]) for i in indices])


def canonical(schema) -> str:
    M, _ = _meta()
    return X.canonical_json(M.ast_to_json(schema)).decode()


class Semantics:
    """K's semantics on these demonstrations: selected regions with their
    descriptors per (partition, predicate, demonstration). Built per call and
    discarded with it; it holds nothing between calls."""

    def __init__(self, demos):
        import numpy as np
        self.demos = [(np.asarray(a, dtype=int), np.asarray(b, dtype=int)) for a, b in demos]
        self.changed = []
        for a, b in self.demos:
            if a.shape != b.shape:
                raise ValueError("shape change is outside this grammar")
            rows, cols = np.nonzero(a != b)
            self.changed.append(frozenset((int(r), int(c)) for r, c in zip(rows, cols)))
        self._regions = {}

    def regions(self, partition, predicate, d):
        key = (partition, predicate, d)
        if key not in self._regions:
            M, MI = _meta()
            grid = self.demos[d][0]
            builder = M.PARTITIONS.get(partition)
            raw = builder(grid) if builder is not None else None
            if not raw:
                self._regions[key] = None
            else:
                test = M.PREDICATES[predicate]
                out = []
                for cells in raw:
                    desc = MI.descriptors(cells, grid)
                    if test(desc):
                        out.append((frozenset((int(r), int(c)) for r, c in cells), desc))
                self._regions[key] = out
        return self._regions[key]

    def cells(self, block, d):
        regions = self.regions(block[0], block[1], d)
        out = set()
        for cells, _desc in regions or ():
            out |= cells
        return frozenset(out)


def layer(sem, block, owned):
    """One K block as a layer beneath higher layers that own `owned[d]`: the
    occurrence-scoped fitter's per-block rules applied to its visible cells
    (a touched region changes entirely and to one colour, one colour per
    key, every key witnessed in two demonstrations, no hidden key, unchanged
    visible regions keep their colour), without the joint-coverage rule.
    Returns (ok, info); on failure info["code"] is a frozen fitter code."""
    SF = _sf()
    p, q, f = block
    constraints, witnesses, covered, untouched = {}, {}, [], []
    hidden, observed = set(), set()
    for d, (_gin, gout) in enumerate(sem.demos):
        regions = sem.regions(p, q, d)
        if regions is None:
            return False, {"code": "scoped_fit_failed"}
        cov = set()
        for cells, desc in regions:
            visible = cells - owned[d]
            key = desc.get(f)
            if not visible:
                if key is not None:
                    hidden.add(key)
                continue
            touched = visible & sem.changed[d]
            if not touched:
                untouched.append((key, d, visible))
                continue
            if touched != visible:
                return False, {"code": "region_colour_conflict"}
            if key is None:
                return False, {"code": "scoped_fit_failed"}
            colours = {int(gout[r, c]) for r, c in visible}
            if len(colours) != 1:
                return False, {"code": "region_colour_conflict"}
            colour = colours.pop()
            if constraints.get(key, colour) != colour:
                return False, {"code": "slot_nonfunctional"}
            constraints[key] = colour
            witnesses.setdefault(key, set()).add(d)
            observed.add(key)
            cov |= visible
        covered.append(frozenset(cov))
    if not constraints:
        return False, {"code": "slot_unobservable"}
    if hidden - observed:
        return False, {"code": "slot_key_unobserved"}
    if any(len(w) < SF.MIN_KEY_WITNESSES for w in witnesses.values()):
        return False, {"code": "slot_key_unobserved"}
    for key, d, visible in untouched:
        if key in constraints:
            gout = sem.demos[d][1]
            if any(int(gout[r, c]) != constraints[key] for r, c in visible):
                return False, {"code": "final_execution_mismatch"}
    return True, {"covered": covered, "constraints": constraints, "entries": len(constraints)}


def frontier(sem) -> list:
    """K's typed failure frontier: every K block as FULL, PARTIAL (with its
    residual) or CONFLICT (with the fitter code)."""
    n = len(sem.demos)
    none = [frozenset()] * n
    rows = []
    for k, block in enumerate(k_blocks()):
        ok, info = layer(sem, block, none)
        if not ok:
            rows.append({"k": k, "status": "CONFLICT", "code": info["code"]})
            continue
        cov = info["covered"]
        full = all(cov[d] == sem.changed[d] for d in range(n))
        rows.append({"k": k, "status": "FULL" if full else "PARTIAL", "code": None,
                     "covered": [len(c) for c in cov], "changed": [len(c) for c in sem.changed],
                     "entries": info["entries"],
                     "residual": [[[r, c] for r, c in sorted(sem.changed[d] - cov[d])]
                                  for d in range(n)]})
    return rows


# --------------------------------------------------------------------------
# the closed proposer input and the leakage scanner
# --------------------------------------------------------------------------

def k_class(sem) -> str:
    base = _sf().base_search_with_scoped_fitter(sem.demos)
    return "K_EXACT" if base["exact"] else ("K_CONSISTENT_INEXACT" if base["fitted"]
                                            else "K_NO_CONSISTENT")


def build_input(demos, sem=None) -> dict:
    """The only object the proposer reads. Built from the demonstrations by
    K's semantics; nothing else enters."""
    sem = sem or Semantics(demos)
    return {"format": FORMAT_INPUT,
            "demonstrations": [{"input": a.tolist(), "output": b.tolist()} for a, b in sem.demos],
            "failure": {"k_class": k_class(sem), "frontier": frontier(sem)},
            "grammar": grammar(), "limits": json.loads(json.dumps(LIMITS)),
            "kstar_identity": X.k_identity()}


TOP_KEYS = frozenset({"format", "demonstrations", "failure", "grammar", "limits", "kstar_identity"})
ROW_KEYS = {"CONFLICT": frozenset({"k", "status", "code"}),
            "PARTIAL": frozenset({"k", "status", "code", "covered", "changed", "entries", "residual"}),
            "FULL": frozenset({"k", "status", "code", "covered", "changed", "entries", "residual"})}
FORBIDDEN_WORDS = ("target", "seed", "family", "task", "label", "truth", "digest", "answer",
                   "solution", "held", "test", "oracle", "schema", "token", "candidate")


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def scan_input(inp) -> None:
    """Refuse the input unless it is exactly the closed object build_input
    makes: the allowed keys, demonstration grids of small integers, frontier
    rows in K order with frozen statuses and codes, the frozen grammar and
    limits, and the K* identity. Any key naming a target, seed, family,
    task, label, truth, digest, answer, solution, held-out pair, test,
    oracle, schema, token or candidate, and any string outside the frozen
    vocabulary, is leakage."""
    problems = []
    if not isinstance(inp, dict) or set(inp) != TOP_KEYS:
        raise LeakageError(f"keys must be exactly {sorted(TOP_KEYS)}")
    if inp["format"] != FORMAT_INPUT:
        problems.append("format")
    if inp["grammar"] != grammar():
        problems.append("grammar")
    if inp["limits"] != json.loads(json.dumps(LIMITS)):
        problems.append("limits")
    if inp["kstar_identity"] != X.k_identity():
        problems.append("kstar_identity")
    demos = inp["demonstrations"]
    if not isinstance(demos, list) or not demos:
        problems.append("demonstrations")
    else:
        for d in demos:
            if not isinstance(d, dict) or set(d) != {"input", "output"}:
                problems.append("demonstration keys")
                continue
            for g in (d["input"], d["output"]):
                if not (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
                        and all(_int(v) and 0 <= v <= 9 for r in g for v in r)):
                    problems.append("demonstration grid")
    fail = inp["failure"]
    if not isinstance(fail, dict) or set(fail) != {"k_class", "frontier"}:
        problems.append("failure keys")
    else:
        if fail["k_class"] not in K_CLASSES:
            problems.append("k_class")
        rows = fail["frontier"]
        if not isinstance(rows, list) or len(rows) != len(k_blocks()):
            problems.append("frontier length")
        else:
            for i, row in enumerate(rows):
                st = row.get("status") if isinstance(row, dict) else None
                if st not in ROW_KEYS or set(row) != ROW_KEYS[st] or row["k"] != i:
                    problems.append(f"frontier row {i}")
                    continue
                if row["code"] is not None and row["code"] not in codes():
                    problems.append(f"frontier code {i}")
                if st != "CONFLICT":
                    if not (_int(row["entries"]) and all(_int(v) for v in row["covered"] + row["changed"])
                            and all(isinstance(cell, list) and len(cell) == 2 and all(_int(v) for v in cell)
                                    for res in row["residual"] for cell in res)):
                        problems.append(f"frontier values {i}")
    allowed = set(K_CLASSES) | set(STATUSES) | set(codes()) | {FORMAT_INPUT, X.k_identity()}
    g = grammar()
    allowed |= set(g["partitions"]) | set(g["predicates"]) | set(g["features"])

    def walk(value, path):
        if isinstance(value, dict):
            for k, v in value.items():
                if not isinstance(k, str) or any(w in k.lower() for w in FORBIDDEN_WORDS):
                    problems.append(f"key {path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(value, list):
            for v in value:
                walk(v, path)
        elif isinstance(value, str):
            if value not in allowed:
                problems.append(f"string at {path}")
        elif not (value is None or isinstance(value, (int, float))):
            problems.append(f"value type at {path}")
    walk(inp, "$")
    if problems:
        raise LeakageError("; ".join(sorted(set(problems))[:10]))


# --------------------------------------------------------------------------
# proposal generation
# --------------------------------------------------------------------------

def _deadline_check(deadline):
    if deadline is not None and time.time() > deadline:
        raise ResourceExhausted("proposer wall time exceeded")


def _covers(sem, block, residual, owned) -> bool:
    for d in range(len(sem.demos)):
        if residual[d] and not residual[d] <= (sem.cells(block, d) - owned[d]):
            return False
    return True


class _Emitter:
    def __init__(self, blocks):
        self.blocks, self.out, self.seen, self.capped = blocks, [], set(), False

    def emit(self, indices, origin) -> bool:
        if len(set(indices)) != len(indices):
            return True
        schema = compose(indices, self.blocks)
        key = canonical(schema)
        if key in self.seen:
            return True
        if len(self.out) >= LIMITS["max_proposals"]:
            self.capped = True
            return False
        self.seen.add(key)
        self.out.append({"layers": list(indices), "schema": schema, "canonical": key,
                         "origin": origin})
        return True


def propose(inp, depth, sem=None, deadline=None) -> dict:
    """FAILURE_CONDITIONED proposals of one depth from the closed input.
    Top layers and residuals come from the input's frontier; lower layers
    are K blocks checked on the demonstrations."""
    scan_input(inp)
    sem = sem or Semantics([(d["input"], d["output"]) for d in inp["demonstrations"]])
    blocks = k_blocks()
    n = len(sem.demos)
    tops = sorted((r for r in inp["failure"]["frontier"] if r["status"] == "PARTIAL"),
                  key=lambda r: (-sum(r["covered"]), r["entries"], r["k"]))
    em = _Emitter(blocks)

    def residual_of(row):
        if len(row["residual"]) != n:
            return None
        return [frozenset((int(r), int(c)) for r, c in row["residual"][d]) for d in range(n)]

    if depth == 2:
        for top in tops[:LIMITS["max_top"]]:
            _deadline_check(deadline)
            b = top["k"]
            res = residual_of(top)
            if res is None:
                continue
            owned = [sem.cells(blocks[b], d) for d in range(n)]
            lowers = []
            for a in range(len(blocks)):
                if a == b or not _covers(sem, blocks[a], res, owned):
                    continue
                ok, info = layer(sem, blocks[a], owned)
                if ok and all(info["covered"][d] == res[d] for d in range(n)):
                    lowers.append((info["entries"], a))
            for _e, a in sorted(lowers)[:LIMITS["max_lower"]]:
                if not em.emit((a, b), "peel2"):
                    return {"proposals": em.out, "capped": True, "tops": len(tops)}
    elif depth == 3:
        for top in tops[:LIMITS["max_top3"]]:
            _deadline_check(deadline)
            b3 = top["k"]
            res3 = residual_of(top)
            if res3 is None:
                continue
            owned3 = [sem.cells(blocks[b3], d) for d in range(n)]
            mids = []
            for m in range(len(blocks)):
                if m == b3:
                    continue
                ok, info = layer(sem, blocks[m], owned3)
                if not ok:
                    continue
                cov = info["covered"]
                if not all(cov[d] <= res3[d] for d in range(n)) or not any(cov):
                    continue
                if all(cov[d] == res3[d] for d in range(n)):
                    continue                      # a two-layer composition, depth 2's job
                mids.append((-sum(len(c) for c in cov), info["entries"], m, cov))
            for _c, _e, m, cov in sorted(mids, key=lambda t: t[:3])[:LIMITS["max_mid"]]:
                _deadline_check(deadline)
                owned2 = [owned3[d] | sem.cells(blocks[m], d) for d in range(n)]
                res2 = [res3[d] - cov[d] for d in range(n)]
                bottoms = []
                for b1 in range(len(blocks)):
                    if b1 in (m, b3) or not _covers(sem, blocks[b1], res2, owned2):
                        continue
                    ok, info = layer(sem, blocks[b1], owned2)
                    if ok and all(info["covered"][d] == res2[d] for d in range(n)):
                        bottoms.append((info["entries"], b1))
                for _e, b1 in sorted(bottoms)[:LIMITS["max_bottom3"]]:
                    if not em.emit((b1, m, b3), "peel3"):
                        return {"proposals": em.out, "capped": True, "tops": len(tops)}
    else:
        raise ValueError("depth must be 2 or 3")
    return {"proposals": em.out, "capped": em.capped, "tops": len(tops)}


def propose_demo_only(sem, depth, deadline=None) -> dict:
    """DEMO_ONLY ablation: K blocks ranked by the share of changed cells
    their selected regions touch (a demonstration statistic; no
    consistency, conflict or residual information), composed in order of
    rank sum, same caps."""
    blocks = k_blocks()
    n = len(sem.demos)
    total = sum(len(c) for c in sem.changed) or 1
    share = []
    for k, block in enumerate(blocks):
        touched = sum(len(sem.cells(block, d) & sem.changed[d]) for d in range(n))
        share.append((-touched / total, k))
    ranked = [k for _s, k in sorted(share)]
    em = _Emitter(blocks)
    size = len(ranked)
    for s in range(3 * size):
        _deadline_check(deadline)
        if depth == 2:
            for i in range(max(0, s - size + 1), min(s, size - 1) + 1):
                top, bottom = ranked[i], ranked[s - i]
                if not em.emit((bottom, top), "demo2"):
                    return {"proposals": em.out, "capped": True, "tops": size}
        else:
            for i in range(max(0, s - 2 * size + 2), min(s, size - 1) + 1):
                for j in range(max(0, s - i - size + 1), min(s - i, size - 1) + 1):
                    top, mid, bottom = ranked[i], ranked[j], ranked[s - i - j]
                    if not em.emit((bottom, mid, top), "demo3"):
                        return {"proposals": em.out, "capped": True, "tops": size}
        if depth == 2 and s >= 2 * size - 2:
            break
    return {"proposals": em.out, "capped": em.capped, "tops": size}


# --------------------------------------------------------------------------
# verification, duplicates and the frozen selection hierarchy
# --------------------------------------------------------------------------

def _evaluate(ast, grid):
    import numpy as np
    M, MI = _meta()
    return M.evaluate(ast, np.asarray(grid), MI.descriptors)


def fingerprint(concrete) -> str:
    from cora_tti import constructive_probes as CP
    return CP.fingerprint(concrete, _evaluate)


def _nodes(ast) -> int:
    if not (isinstance(ast, tuple) and len(ast) == 2 and isinstance(ast[0], str)):
        return 0
    return 1 + sum(_nodes(a) for a in ast[1] if isinstance(a, tuple))


def verify(proposals, sem, deadline=None) -> list:
    """Exact fit of every proposal on every demonstration by the frozen
    occurrence-scoped fitter; the verified ones carry their fitted program
    and MDL key."""
    SF = _sf()
    out = []
    for p in proposals:
        _deadline_check(deadline)
        fitted, ev = SF.fit_induced_occurrences(p["schema"], sem.demos)
        if fitted is None:
            continue
        entries = sum(int(s.get("entries", 0)) for s in ev.get("slots", {}).values())
        out.append(dict(p, fitted=fitted, entries=entries,
                        mdl=(entries, _nodes(p["schema"]), p["canonical"])))
    return out


def dedupe(verified, deadline=None) -> list:
    """Verified candidates with the same probe fingerprint collapse to the
    first in MDL order; representatives come back in MDL order."""
    best = {}
    for c in sorted(verified, key=lambda c: c["mdl"]):
        _deadline_check(deadline)
        fp = fingerprint(c["fitted"])
        if fp not in best:
            best[fp] = dict(c, fingerprint=fp)
    return sorted(best.values(), key=lambda c: c["mdl"])


_D_CACHE = {}


def frozen_d() -> dict:
    """The frozen D artifact, read once per process by content; immutable."""
    with open(FROZEN_D, "rb") as handle:
        raw = handle.read()
    digest = hashlib.sha256(raw).hexdigest()
    if digest not in _D_CACHE:
        _D_CACHE.clear()
        _D_CACHE[digest] = json.loads(raw)
    return _D_CACHE[digest]


def d_rich_row(sem) -> list:
    """D's standardized demonstration row: the six demonstration features
    and the TFG demonstration nodes, both computed from the demonstrations
    by the frozen code, standardized by the frozen D's standardizer."""
    from cora_tti import constructive_dataset as CD
    from cora_arc2026.vendor import tfg_extractor as TE
    demos = [{"input": a.tolist(), "output": b.tolist()} for a, b in sem.demos]
    feats = CD.to_model_view(SimpleNamespace(demonstrations=demos, tfg={"nodes": []}), 0)["features"]
    nodes, _edges = TE._demo_nodes(sem.demos)
    ep = {"demo_features": {k: feats[k] for k in G.DEMO_FEATURES},
          "full_engine_tfg": {"nodes": [{"kind": nd.kind, "attrs": dict(nd.attrs)} for nd in nodes]}}
    rich = S.demo_rich(ep)
    raw = [rich[k] for k in S.D_RICH_FIELDS]
    std = frozen_d()["standardizer"]
    return [((raw[i] - m) / s) for i, m, s in zip(std["index"], std["mean"], std["std"])]


def d_choice(tie, sem):
    """D on a P0 tie set: applicable only if the members differ in
    key-feature tokens alone; each member scores the sum of D's logits at the
    differing positions (exactly v1.6's D for one position)."""
    from cora_arc2026 import scorer_fit as SFIT
    d = frozen_d()
    toks = [S.CV.tokens_from_ast(c["schema"]) for c in tie]
    if len({len(t) for t in toks}) != 1:
        return None, "D_NOT_APPLICABLE"
    diff = [j for j in range(len(toks[0])) if len({tuple(t[j]) for t in toks}) > 1]
    if not diff or any(t[j][0] != "M" for t in toks for j in diff):
        return None, "D_NOT_APPLICABLE"
    row = d_rich_row(sem)
    tix = {tuple(t): i for i, t in enumerate(d["tokens"])}
    scores = []
    for t in toks:
        state, s = S.CV.GrammarState(), 0.0
        for j, tok in enumerate(t):
            if j in diff:
                x = [1.0] + row + SFIT.state_vector(state)
                w = d["W"][tix[tuple(tok)]]
                s += sum(a * b for a, b in zip(w, x))
            state = state.advance(tuple(tok))
        scores.append(s)
    best = max(scores)
    top = [c for c, s in zip(tie, scores) if best - s <= C.TIE_EPS]
    return (top[0], "D") if len(top) == 1 else (top, "D_TIE")


def p0_maximal(cands) -> list:
    """Candidates no other candidate beats under P0's lexicographic rule."""
    idx = {k: i for i, k in enumerate(C.RESPONSE_FIELDS)}

    def vec(c):
        return [c["response"][k] for k in C.RESPONSE_FIELDS]
    out = []
    for c in cands:
        beaten = any(C.p0_choice([a - b for a, b in zip(vec(o), vec(c))]) == 1
                     for o in cands if o is not c)
        if not beaten:
            out.append(c)
    del idx
    return out


def select(verified, sem, mode="HYBRID", deadline=None) -> dict:
    """The frozen hierarchy: verification (already applied), duplicates,
    P0, D on P0 ties, MDL guess. mode PURE abstains on a P0 tie; mode
    NO_RESPONSE skips the probe."""
    reps = dedupe(verified, deadline)
    rec = {"verified": len(verified), "deduped": len(reps), "probed": 0, "tie": 0,
           "level": None, "selected": None}
    if not reps:
        return rec
    if len(reps) == 1:
        rec.update(level="VERIFICATION_UNIQUE", selected=reps[0])
        return rec
    pool = reps[:LIMITS["max_probed"]]
    if mode == "NO_RESPONSE":
        tie = pool
    else:
        for c in pool:
            _deadline_check(deadline)
            c["response"] = C.probe(c["schema"], sem.demos)["response"]
        rec["probed"] = len(pool)
        tie = p0_maximal(pool)
        if len(tie) == 1:
            rec.update(level="P0", selected=tie[0], tie=1)
            return rec
        if mode == "PURE":
            rec.update(level="ABSTAINED", tie=len(tie))
            return rec
    rec["tie"] = len(tie)
    chosen, how = d_choice(tie, sem)
    if how == "D":
        rec.update(level="D", selected=chosen)
        return rec
    rest = chosen if how == "D_TIE" else tie
    rec.update(level="MDL", selected=sorted(rest, key=lambda c: c["mdl"])[0])
    return rec


# --------------------------------------------------------------------------
# the proposer-level pipeline
# --------------------------------------------------------------------------

def solve(demos, arm="FAILURE_CONDITIONED", donor_failure=None, wall_s=None) -> dict:
    """failure evidence -> proposals -> verification and probe -> selection,
    for one arm. Returns a record; nothing is compiled or installed here."""
    t0 = time.time()
    deadline = t0 + (LIMITS["wall_s"] if wall_s is None else wall_s)
    rec = {"arm": arm, "class": None, "proposals": {}, "capped": {}, "selection": None,
           "selected": None, "seconds": None}
    try:
        sem = Semantics(demos)
        inp = build_input(demos, sem)
        own_class = inp["failure"]["k_class"]
        rec["k_class"] = own_class
        rec["partial_tops"] = sum(1 for r in inp["failure"]["frontier"] if r["status"] == "PARTIAL")
        if arm == "SHUFFLED_FRONTIER":
            if donor_failure is None:
                raise ValueError("SHUFFLED_FRONTIER needs a donor failure")
            inp = dict(inp, failure=json.loads(json.dumps(donor_failure)))
        scan_input(inp)
        rec["input_sha256"] = hashlib.sha256(X.canonical_json(inp)).hexdigest()
        if own_class == "K_EXACT":
            rec["class"] = "K_ALREADY_SOLVES"
            return rec
        verified, last_capped = [], False
        for depth in LIMITS["depths"]:
            if arm == "DEMO_ONLY":
                gen = propose_demo_only(sem, depth, deadline)
            else:
                gen = propose(inp, depth, sem, deadline)
            rec["proposals"][str(depth)] = len(gen["proposals"])
            rec["capped"][str(depth)] = gen["capped"]
            last_capped = gen["capped"]
            for p in gen["proposals"]:
                try:
                    X.type_check(p["schema"])
                except X.CompileError as exc:
                    rec["class"] = "UNTYPEABLE_PROPOSAL"
                    rec["detail"] = exc.code
                    return rec
            verified = verify(gen["proposals"], sem, deadline)
            rec.setdefault("verified_by_depth", {})[str(depth)] = len(verified)
            if verified:
                break
        if not verified:
            total = sum(rec["proposals"].values())
            rec["class"] = ("NO_PROPOSAL" if total == 0 else
                            "PROPOSAL_LIMIT" if last_capped else "NO_VERIFIABLE_PROPOSAL")
            return rec
        mode = {"NO_RESPONSE": "NO_RESPONSE", "PURE": "PURE"}.get(arm, "HYBRID")
        sel = select(verified, sem, mode, deadline)
        rec["selection"] = {k: sel[k] for k in ("verified", "deduped", "probed", "tie", "level")}
        if sel["selected"] is None:
            rec["class"] = "SELECTION_ABSTAINED"
            return rec
        c = sel["selected"]
        rec["selected"] = {"layers": c["layers"], "canonical": c["canonical"], "origin": c["origin"],
                           "fingerprint": c["fingerprint"], "entries": c["entries"],
                           "response": c.get("response")}
        rec["selected_schema"] = c["schema"]
        rec["selected_fitted"] = c["fitted"]
        rec["class"] = "SELECTED"
        rec["_input"] = inp
        return rec
    except LeakageError as exc:
        rec["class"] = "LEAKAGE_FAILURE"
        rec["detail"] = str(exc)
        return rec
    except ResourceExhausted:
        rec["class"] = "RESOURCE_EXHAUSTED"
        return rec
    finally:
        rec["seconds"] = round(time.time() - t0, 3)


# --------------------------------------------------------------------------
# S6: the separation law
# --------------------------------------------------------------------------

def separation(rec, demos) -> dict:
    """A: not one of K's programs. B: K's bounded search has no exact fit.
    C: on the frozen probes the fitted extension differs from every relevant
    existing K program: K's PARTIAL blocks fitted on their own consistent
    regions, and any loosely fitting K program. An empty comparison set
    makes C untestable."""
    M, _ = _meta()
    SF = _sf()
    sem = Semantics(demos)
    k_canon = {canonical(s) for s in SF.baseline_single_block_schemas()}
    a = rec["selected"]["canonical"] not in k_canon
    base = SF.base_search_with_scoped_fitter(sem.demos)
    b = base["exact"] == 0
    blocks = k_blocks()
    none = [frozenset()] * len(sem.demos)
    comparison = []
    for row in frontier(sem):
        if row["status"] != "PARTIAL":
            continue
        ok, info = layer(sem, blocks[row["k"]], none)
        table = tuple(sorted(info["constraints"].items(), key=lambda kv: repr(kv[0])))
        program = M.instantiate(compose([row["k"]], blocks), {"?0": table})
        comparison.append(("partial", row["k"], fingerprint(program)))
    for schema, fitted in base["fitted_pairs"]:
        comparison.append(("loose", canonical(schema), fingerprint(fitted)))
    fp = rec["selected"]["fingerprint"]
    if not comparison:
        c = "C_UNTESTABLE"
    elif any(f == fp for _kind, _id, f in comparison):
        c = "DUPLICATE_EXISTING_SEMANTICS"
    else:
        c = "SEPARATED"
    return {"A_syntactic_absent": a, "B_outside_bounded_search": b, "C": c,
            "comparison_set": len(comparison),
            "new_capability": bool(a and b and c == "SEPARATED")}


# --------------------------------------------------------------------------
# the engine stage: compile, install, rerun; real leave-one-out
# --------------------------------------------------------------------------

def compile_selected(rec):
    """The v1.7 compiler on the selected schema, with provenance: this
    proposer's code hash and the hash of the proposer input."""
    inp = rec["_input"]
    return X.compile_extension(X.make_input(
        rec["selected_schema"], producer_sha256=proposer_sha256(),
        evidence_sha256=hashlib.sha256(X.canonical_json(inp)).hexdigest()))


def engine_stage(train, held, rec) -> dict:
    """K* + {e} against K* with the held-out pair (the paired ablation)."""
    try:
        prod = compile_selected(rec)
    except X.CompileError as exc:
        return {"class": "COMPILE_FAILURE", "detail": exc.code}
    ab = X.paired_ablation(train, prod, heldout=held)
    keep = ("accepted", "heldout_exact", "seconds", "events", "program", "engine_dir_removed")
    out = {"verdict": ab["verdict"], "with": {k: ab["with"].get(k) for k in keep},
           "without": {k: ab["without"].get(k) for k in keep},
           "uses": ab["with_uses_extension"], "production": prod["name"]}
    out["class"] = ("SUCCESS" if ab["verdict"] == "EXTENSION_NECESSARY_AND_USED"
                    and ab["with"].get("heldout_exact") else "ENGINE_REJECTED")
    return out


def real_loo(train, arm="FAILURE_CONDITIONED") -> dict:
    """Real S5: each fold removes its held-out demonstration first, rebuilds
    the failure state from the remaining demonstrations, proposes, selects
    and compiles from scratch, installs into a fresh K*, reruns, and
    predicts the held-out demonstration. Fold engine events are kept."""
    folds = []
    for i in range(len(train)):
        fold = [train[j] for j in range(len(train)) if j != i]
        held = train[i]
        rec = solve(fold, arm)
        f = {"fold": i, "proposer_class": rec["class"], "proposals": rec["proposals"],
             "selection": rec["selection"], "input_sha256": rec.get("input_sha256"),
             "selected": rec["selected"]["canonical"] if rec["selected"] else None,
             "proposer_seconds": rec["seconds"]}
        if rec["class"] != "SELECTED":
            f["class"] = rec["class"]
            folds.append(f)
            continue
        try:
            prod = compile_selected(rec)
        except X.CompileError as exc:
            f.update(**{"class": "COMPILE_FAILURE", "detail": exc.code})
            folds.append(f)
            continue
        run = X.run_reasoner(fold, (prod,))
        uses = bool(run["accepted"] and X.uses_extension(run["program"], prod))
        exact = X.predict_exact(run, *held)
        f.update(accepted=run["accepted"], uses=uses, heldout_exact=exact,
                 events=run["events"], engine_seconds=run["seconds"],
                 engine_dir_removed=run["engine_dir_removed"], production=prod["name"])
        f["class"] = "SUCCESS" if (run["accepted"] and uses and exact) else "LOO_FAILURE"
        folds.append(f)
    passed = bool(folds) and all(f["class"] == "SUCCESS" for f in folds)
    return {"folds": folds, "passed": passed,
            "folds_success": sum(1 for f in folds if f["class"] == "SUCCESS")}
