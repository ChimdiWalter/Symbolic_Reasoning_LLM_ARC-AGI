"""Stage-B constructive AST proposer: (TFG, typed interface) -> new ASTs.

Implements the one missing Item-2 responsibility. It decides WHAT to
construct. It does not compile, install, execute or score anything, and it
never returns a catalogue production name.

Frozen authority, not redefined here: `constructive_vocabulary` is the sole
legality authority, `GrammarState` supplies the decoder masks, and the
manifest supplies the grammar bounds, the beam width, the ranking form and
the MDL definition. See records/ITEM2_PROPOSER_PREFLIGHT.md.

Permitted conditioning evidence is the typed failure graph and the typed
interface only. No task id, no ARC family label, no test output, no
natural-language solution and no manually supplied primitive ever reaches
this module.
"""
from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
for _p in (TTI, HERE):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from cora_tti import constructive_vocabulary as CV                # noqa: E402

#: frozen ranking parameters, read from the manifest rather than restated
_RANK = CV.manifest()["ranking"]
BEAM = int(_RANK["beam"])
LAMBDA_MDL = float(_RANK["lambda_mdl"])
LAMBDA_COST = float(_RANK["lambda_cost"])

#: per-stage cost model for the frozen cost term, deterministic
COST_PER_STAGE_S = 0.004
COST_PER_SELECT_S = 0.002


# --------------------------------------------------------------------------
# what counts as already present in K
# --------------------------------------------------------------------------

def baseline_expressible_digests() -> frozenset:
    """Digests of every AST whose family the protocol bans as already in K.

    The frozen protocol bans families (0,) and (1,) because a single block is
    baseline expressible. Those, enumerated, are exactly the ASTs that are
    not new.
    """
    out = set()
    for ast in CV.enumerate_asts(max_blocks=1):
        if CV.is_banned_target_family(CV.family(ast)):
            out.add(CV.digest(ast))
    return frozenset(out)


_BASELINE_DIGESTS: frozenset | None = None


def is_in_k(ast) -> bool:
    global _BASELINE_DIGESTS
    if _BASELINE_DIGESTS is None:
        _BASELINE_DIGESTS = baseline_expressible_digests()
    return CV.digest(ast) in _BASELINE_DIGESTS


# --------------------------------------------------------------------------
# permitted evidence extracted from a typed failure graph
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    """Domain-general failure signals. Nothing here identifies a task."""
    frontier_terms: int = 0
    slot_failures: int = 0
    executed_not_exact: int = 0
    distinct_frontier_ops: int = 0
    palette_introduced: float = 0.0
    palette_removed: float = 0.0
    shape_preserved: float = 0.0
    shrinks: float = 0.0
    grows: float = 0.0
    fraction_changed: float = 0.0
    fraction_wrong: float = 0.0
    palette_extra: float = 0.0
    shape_mismatch: float = 0.0
    defined_signatures: int = 0
    empty: bool = True

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _mean(values, default=0.0):
    values = [v for v in values if v is not None]
    return float(sum(values) / len(values)) if values else default


def read_evidence(tfg) -> Evidence:
    """Extract permitted conditioning signals from a ConcreteTFG."""
    nodes = list(tfg.nodes())
    by_kind: dict = {}
    for node in nodes:
        by_kind.setdefault(node.kind, []).append(node)

    frontier = by_kind.get("frontier_term", [])
    vsig = by_kind.get("value_signature", [])
    defined = [n for n in vsig if n.attrs.get("defined")]
    delta = by_kind.get("delta_signature", [])
    palette = by_kind.get("palette_change", [])
    shape = by_kind.get("shape_change", [])
    slots = by_kind.get("slot", [])

    return Evidence(
        frontier_terms=len(frontier),
        slot_failures=sum(int(n.attrs.get("failures", 0)) for n in slots)
        or sum(1 for n in frontier
               if n.attrs.get("outcome") == "slot_fit_failed"),
        executed_not_exact=sum(1 for n in frontier
                               if n.attrs.get("outcome") == "executed_not_exact"),
        distinct_frontier_ops=len({n.attrs.get("op") for n in frontier}),
        palette_introduced=_mean([n.attrs.get("introduced") for n in palette]),
        palette_removed=_mean([n.attrs.get("removed") for n in palette]),
        shape_preserved=_mean([1.0 if n.attrs.get("same_shape") else 0.0
                               for n in delta]),
        shrinks=_mean([1.0 if n.attrs.get("shrinks") else 0.0 for n in delta]),
        grows=_mean([1.0 if n.attrs.get("grows") else 0.0 for n in delta]),
        fraction_changed=_mean([n.attrs.get("fraction_changed") for n in shape]),
        fraction_wrong=_mean([n.attrs.get("fraction_wrong") for n in defined]),
        palette_extra=_mean([n.attrs.get("palette_extra") for n in defined]),
        shape_mismatch=_mean([0.0 if n.attrs.get("shape_matches") else 1.0
                              for n in defined]),
        defined_signatures=len(defined),
        empty=not (frontier or delta or palette),
    )


# --------------------------------------------------------------------------
# log-linear, grammar-masked token scorer
# --------------------------------------------------------------------------

def _softmax_logs(weights: Sequence[float]) -> list:
    top = max(weights)
    exps = [math.exp(w - top) for w in weights]
    total = sum(exps)
    return [math.log(e / total) for e in exps]


class EvidenceScorer:
    """Transparent log-linear scorer over grammar-legal tokens.

    Weights are an evidence prior in this version, expressed over generic
    structural properties the grammar itself names: colour, size, shape,
    border and rectangularity. They are not ARC task families and not
    handwritten solutions. ``weights`` is exposed so a later block can fit
    them on the constructive dataset without changing this interface.
    """

    #: how each generic evidence signal pushes each terminal choice
    PARTITION_FEATURES = {
        "colour_components": ("palette_introduced", "palette_removed",
                              "palette_extra"),
        "background_components": ("shape_preserved",),
        "enclosed_regions": ("fraction_changed",),
        "separator_panels": ("shape_mismatch", "shrinks", "grows"),
    }
    PREDICATE_FEATURES = {
        "all": (),
        "rectangular": ("shape_preserved",),
        "not_rectangular": ("fraction_changed",),
        "touching_border": ("grows",),
        "not_touching_border": ("shrinks",),
    }
    FEATURE_FEATURES = {
        "sole_neighbour_colour": ("palette_introduced",),
        "neighbour_colours": ("palette_extra",),
        "touches_border": ("grows",),
        "is_rect": ("shape_preserved",),
        "is_square": ("shape_preserved",),
        "area": ("fraction_changed",),
        "hw": ("shape_mismatch",),
        "shape": ("fraction_wrong",),
        "row_band": ("shrinks",),
        "col_band": ("grows",),
    }

    def __init__(self, weights: Mapping[str, float] | None = None,
                 scale: float = 2.0):
        self.weights = dict(weights or {})
        self.scale = float(scale)

    def _bonus(self, table, name: str, evidence: Evidence) -> float:
        signals = table.get(name, ())
        if not signals:
            return 0.0
        raw = sum(float(getattr(evidence, s, 0.0)) for s in signals)
        raw = raw / len(signals)
        return self.scale * math.tanh(raw) + self.weights.get(name, 0.0)

    def token_logprobs(self, state, legal: Sequence[tuple],
                       evidence: Evidence, interface: tuple) -> list:
        raw = []
        for token in legal:
            kind = token[0]
            if kind == "P":
                raw.append(self._bonus(self.PARTITION_FEATURES, token[1],
                                       evidence))
            elif kind == "S":
                #  discrimination is only warranted when the failure showed
                #  several distinct frontier operators or slot failures
                pressure = math.tanh(0.5 * evidence.distinct_frontier_ops
                                     + 0.05 * evidence.slot_failures)
                raw.append(self._bonus(self.PREDICATE_FEATURES, token[1],
                                       evidence) + self.scale * pressure - 1.0)
            elif kind == "M":
                raw.append(self._bonus(self.FEATURE_FEATURES, token[1],
                                       evidence))
            elif kind == "PAINT":
                raw.append(0.0)
            else:  # EOS
                #  more distinct failing operators argue for more blocks
                raw.append(1.0 - self.scale
                           * math.tanh(0.4 * max(0, evidence.distinct_frontier_ops - 1)))
        return _softmax_logs(raw)


# --------------------------------------------------------------------------
# candidate record
# --------------------------------------------------------------------------

@dataclass
class Candidate:
    ast: Any
    canonical: str
    digest: str
    interface: tuple
    structural_family: tuple
    family_text: str
    mdl: int
    estimated_cost_s: float
    logp: float
    score: float
    rank: int = 0
    absent_from_k: bool = True
    banned_target_family: bool = False
    holdout_family: bool = False
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        out = {k: getattr(self, k) for k in self.__dataclass_fields__}
        out["ast"] = self.canonical
        out["structural_family"] = list(self.structural_family)
        out["interface"] = list(self.interface)
        return out


def estimated_cost_s(ast) -> float:
    blocks = CV.blocks_from_ast(ast)
    selects = sum(len(s) for _, s, _ in blocks)
    return round(COST_PER_STAGE_S * CV.stage_count(ast)
                 + COST_PER_SELECT_S * selects, 6)


# --------------------------------------------------------------------------
# the proposer
# --------------------------------------------------------------------------

def propose_ast(tfg, interface: tuple, k: int = 5, *,
                beam: int | None = None,
                scorer: EvidenceScorer | None = None,
                allow_banned: bool = False,
                exclude_holdout: bool = False,
                evidence: Evidence | None = None) -> list:
    """Ordered new constructive ASTs for a typed failure graph.

    ``interface`` is the typed pair (source, target), for example
    ("Set[Region]", "Grid"). Candidates whose target family the protocol bans
    as baseline expressible are dropped unless ``allow_banned``. Ordering is
    the frozen rule: logp minus the MDL term minus the cost term.
    """
    started = time.monotonic()
    width = BEAM if beam is None else int(beam)
    scorer = scorer or EvidenceScorer()
    ev = evidence if evidence is not None else read_evidence(tfg)
    source, target = interface

    #  beam over grammar states; the grammar is the only legality authority
    beams = [(0.0, CV.GrammarState(), ())]
    finished: list = []
    while beams:
        nxt = []
        for logp, state, tokens in beams:
            legal = state.legal_tokens()
            if not legal:
                continue
            logs = scorer.token_logprobs(state, legal, ev, interface)
            for token, tlp in zip(legal, logs):
                try:
                    advanced = state.advance(token)
                except CV.GrammarViolation:
                    continue
                total = logp + tlp
                if advanced.finished:
                    finished.append((total, tokens + (token,)))
                else:
                    nxt.append((total, advanced, tokens + (token,)))
        nxt.sort(key=lambda row: -row[0])
        beams = nxt[:width]
        if len(finished) >= width * 4:
            break

    seen, out = set(), []
    for logp, tokens in finished:
        try:
            ast = CV.ast_from_tokens(list(tokens))
        except CV.GrammarViolation:
            continue
        ok, code = CV.validate(ast)
        if not ok:
            continue
        fam = CV.family(ast)
        banned = CV.is_banned_target_family(fam)
        if banned and not allow_banned:
            continue
        hold = CV.is_holdout_family(fam)
        if hold and exclude_holdout:
            continue
        dig = CV.digest(ast)
        if dig in seen:
            continue
        seen.add(dig)
        mdl = CV.mdl(ast)
        cost = estimated_cost_s(ast)
        out.append(Candidate(
            ast=ast, canonical=CV.canonical(ast), digest=dig,
            interface=(str(source), str(target)),
            structural_family=fam, family_text=CV.family_text(fam),
            mdl=mdl, estimated_cost_s=cost, logp=round(logp, 6),
            score=round(logp - LAMBDA_MDL * mdl - LAMBDA_COST * cost, 6),
            absent_from_k=not is_in_k(ast),
            banned_target_family=banned, holdout_family=hold,
            provenance={"protocol": CV.manifest()["protocol"],
                        "beam": width,
                        "evidence": ev.as_dict(),
                        "scorer": type(scorer).__name__}))

    #  frozen ordering, with the canonical form as a deterministic tiebreak
    out.sort(key=lambda c: (-c.score, c.mdl, c.canonical))
    for index, cand in enumerate(out[:k], 1):
        cand.rank = index
        cand.provenance["runtime_s"] = round(time.monotonic() - started, 4)
    return out[:k]
