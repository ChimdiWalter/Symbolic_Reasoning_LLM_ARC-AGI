"""Bounded failure-signal study: does candidate-associated failure evidence
improve constructive proposal ranking?

Question, as set: does associating failed candidate structures with their
recorded failure evidence improve useful constructive proposal ranking, compared
with the current aggregate TFG and with matched-budget unconditioned search?

Held CONSTANT across every condition: the constructive grammar, the fitter and
its options, the evaluator, the acceptance rule (exact fit on every
demonstration), and the demonstration input the proposer may see. The ONLY thing
that varies is which failure representation the ranking may read.

Conditions
    C1 none        no search-failure information at all
    C2 aggregate   the current TFG's marginal counts by code and by partition
    C3 associated  candidate-associated records (observer v1)
    C4 shuffled    the same kind of associated records, taken from a DIFFERENT
                   episode; a control that pays the same cost and carries the
                   same shape of information, but about the wrong task

Budget. One unit is one candidate fit attempt. The failure-extraction cost is
charged to the conditions that use it: the baseline enumerates 200 hypotheses,
so C2, C3 and C4 begin 200 units in debt while C1 begins at zero. Total budget
is identical for every condition, so a representation that helps must repay its
own cost.

Measures, reported separately and never merged
    useful recovery     a program that fits every demonstration exactly, found
                        within budget (the primary measure)
    held-out output     that program's output on FRESH grids never used for
                        fitting, compared against the target's own output
    exact AST recovery  whether the found schema is the generator's schema;
                        reported separately because several programs can explain
                        the same demonstrations
    cost                units consumed, including extraction

Data access. The proposer receives demonstrations, the grammar, and (per
condition) a failure representation built only from the baseline's own attempts.
It never receives the target schema, the target tables, the target digest, the
family label, or any generator metadata.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import candidate_trace as CT                       # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_v2c as V2C                     # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

STUDY_VERSION = "failure_signal_study:v1"
CONDITIONS = ("none", "aggregate", "associated", "shuffled")

#: the two-block families the corrected census found admissible targets in
STUDY_FAMILIES = ((0, 0), (1, 0), (0, 1), (1, 1))


# --------------------------------------------------------------------------
# the proposal space: two-block schemas over the frozen terminals
# --------------------------------------------------------------------------

def proposal_space(families=STUDY_FAMILIES) -> list:
    """Every two-block schema of the declared families, in a fixed order that
    no condition may change. Ranking reorders this list; it never extends it."""
    v = CV.vocab()
    out = []
    for family in families:
        for first in _blocks_of(v, family[0]):
            for second in _blocks_of(v, family[1]):
                out.append((tuple(family), first, second))
    return out


def _blocks_of(v, n_selects: int) -> list:
    blocks = []
    for partition in v["partitions"]:
        for feature in v["key_features"]:
            if n_selects == 0:
                blocks.append((partition, (), feature))
            else:
                for predicate in v["predicates"]:
                    blocks.append((partition, (predicate,), feature))
    return blocks


def schema_of(candidate) -> tuple:
    _family, first, second = candidate
    return CV.ast_from_blocks([first, second])


# --------------------------------------------------------------------------
# the ranking rule: ONE rule, reading only what its condition exposes
# --------------------------------------------------------------------------

@dataclass
class Evidence:
    """What a condition makes available. Absent fields are UNKNOWN, never 0."""
    condition: str
    per_triple: dict = field(default_factory=dict)   # (p,q,f) -> record
    per_partition: dict = field(default_factory=dict)
    per_code: dict = field(default_factory=dict)
    extraction_units: int = 0
    extraction_seconds: float = 0.0


def build_evidence(condition: str, trace, other_trace=None) -> Evidence:
    if condition == "none":
        return Evidence(condition=condition)
    if condition == "aggregate":
        view = CT.aggregate_view(trace)
        return Evidence(condition=condition,
                        per_partition=dict(view["failures_by_partition"]),
                        per_code=dict(view["failures_by_code"]),
                        extraction_units=int(trace.work_done),
                        extraction_seconds=float(trace.seconds))
    source = other_trace if condition == "shuffled" else trace
    if source is None:
        raise ValueError("the shuffled control needs another episode's trace")
    started = time.perf_counter()
    view = CT.observe(source)
    seconds = float(trace.seconds) + (time.perf_counter() - started)
    per_triple = {(r.partition, r.predicate, r.feature): r for r in view.records}
    return Evidence(condition=condition, per_triple=per_triple,
                    extraction_units=int(trace.work_done), extraction_seconds=seconds)


def _block_score(evidence: Evidence, block) -> float:
    """Promise of one block, from the failure evidence alone.

    The rule is the same in every condition; only its inputs differ.

      * coverage_fraction is the graded signal: a single-block candidate that
        explained 103 of 117 changed cells is closer to explaining the change
        than one that explained none, and a two-block program must jointly cover
        the change. Higher is better.
      * a candidate whose partition produced no sets, or whose feature was
        undefined, is structurally hopeless here. Strongly penalized.
      * a region-conflict or under-witnessed key means the grouping produced
        cells but could not be assigned one colour: weak but not hopeless.
      * with no association available, the only thing a condition can say about
        a block is what its partition's marginal says.
    """
    partition, selects, feature = block
    predicate = selects[0] if selects else "all"
    if evidence.condition == "none":
        return 0.0
    if evidence.condition == "aggregate":
        #  marginal failures for this partition, normalized; nothing candidate
        #  specific exists to read
        total = sum(evidence.per_partition.values()) or 1
        return -float(evidence.per_partition.get(partition, 0)) / total
    record = evidence.per_triple.get((partition, predicate, feature))
    if record is None:
        return 0.0                                    # UNKNOWN: no opinion
    if record.status == "EXACT_DEMONSTRATION_FIT":
        return 1.0
    if record.coverage_fraction is not CT.UNKNOWN:
        return float(record.coverage_fraction)
    if record.detail_class in ("partition_empty", "feature_undefined",
                              "prefix_undefined", "unknown_partition",
                              "shape_change", "demonstration_static"):
        return -1.0
    if record.detail_class in ("region_partially_changed", "region_multicoloured",
                               "key_under_witnessed", "nonfunctional_key",
                               "keys_never_visible", "no_visible_constraint",
                               "no_owned_change"):
        return 0.25
    return 0.0                                        # recognized nothing: UNKNOWN


#: Two DECLARED readings of the candidate-associated evidence. Both are simple
#: and both are stated before the measured run; which one is better is an
#: empirical question this study answers rather than assumes.
#:
#:   individual      a block is promising if it alone explained much of the
#:                   change. Sum the two blocks' scores.
#:   complementary   a two-block program must JOINTLY explain the change, so a
#:                   pair whose coverage fractions sum near 1.0 is promising even
#:                   when neither block is individually strong. A block that
#:                   alone covers almost everything is a near-complete
#:                   single-block explanation, which the baseline has already
#:                   rejected as inexact.
#:
#: Rule `individual` was written first. Rule `complementary` was added after
#: `individual` was seen to rank poorly on a DEVELOPMENT episode (seed namespace
#: 6_100_000); the measured run uses a disjoint evaluation namespace.
RANKING_RULES = ("individual", "complementary")


def candidate_score(evidence: Evidence, candidate, rule: str) -> float:
    _family, first, second = candidate
    a, b = _block_score(evidence, first), _block_score(evidence, second)
    if rule == "individual" or evidence.condition in ("none", "aggregate"):
        return a + b
    if rule != "complementary":
        raise ValueError(f"unknown ranking rule {rule!r}")
    ca = _coverage_of(evidence, first)
    cb = _coverage_of(evidence, second)
    if ca is CT.UNKNOWN or cb is CT.UNKNOWN:
        return a + b                       # no joint evidence: fall back
    #  prefer pairs whose coverage sums toward complete joint explanation
    return 1.0 - abs((ca + cb) - 1.0)


def _coverage_of(evidence: Evidence, block):
    partition, selects, feature = block
    predicate = selects[0] if selects else "all"
    record = evidence.per_triple.get((partition, predicate, feature))
    if record is None:
        return CT.UNKNOWN
    return record.coverage_fraction


def rank(candidates: list, evidence: Evidence, rule: str = "individual") -> list:
    """Order the proposal space. The tiebreak is deterministic and identical in
    every condition, so a condition with no information reproduces the fixed
    enumeration order rather than a random one."""
    def key(item):
        index, candidate = item
        score = candidate_score(evidence, candidate, rule)
        mdl = CV.mdl(CV.ast_from_blocks([candidate[1], candidate[2]]))
        return (-score, mdl, index)
    return [c for _i, c in sorted(enumerate(candidates), key=key)]


# --------------------------------------------------------------------------
# the bounded search
# --------------------------------------------------------------------------

@dataclass
class SearchResult:
    condition: str
    rule: str
    solved: bool
    units_used: int
    extraction_units: int
    total_units: int
    seconds: float
    found_schema_json: Optional[dict] = None
    found_digest: Optional[str] = None
    rank_of_solution: Optional[int] = None
    exact_ast_recovered: Optional[bool] = None
    heldout_correct: Optional[bool] = None
    heldout_defined: Optional[int] = None
    heldout_total: Optional[int] = None


def run_condition(condition: str, pairs, trace, budget_units: int,
                  target_digest: str, heldout, other_trace=None,
                  candidates=None, rule: str = "individual") -> SearchResult:
    """Rank, then fit in rank order until an exact fit or the budget runs out.

    `target_digest` and `heldout` are used ONLY to score the result after the
    search has finished. They are not visible to the ranking or to the fitter.
    """
    started = time.perf_counter()
    evidence = build_evidence(condition, trace, other_trace)
    candidates = candidates if candidates is not None else proposal_space()
    ordered = rank(candidates, evidence, rule)
    remaining = budget_units - evidence.extraction_units
    used, found, found_rank = 0, None, None
    for position, candidate in enumerate(ordered):
        if used >= remaining:
            break
        schema = schema_of(candidate)
        used += 1
        outcome = SF.fit_outcome(schema, pairs, require_exact_replay=True)
        if outcome["status"] == "EXACT_DEMONSTRATION_FIT":
            found, found_rank = (schema, outcome["program"]), position
            break
    result = SearchResult(
        condition=condition, rule=rule, solved=found is not None, units_used=used,
        extraction_units=evidence.extraction_units,
        total_units=used + evidence.extraction_units,
        seconds=time.perf_counter() - started)
    if found is None:
        return result
    schema, program = found
    result.found_schema_json = M.ast_to_json(schema)
    result.found_digest = CV.digest(schema)
    result.rank_of_solution = found_rank
    #  reported SEPARATELY: several programs can explain the same demonstrations
    result.exact_ast_recovered = (result.found_digest == target_digest)
    #  the primary generalization measure: output correctness on fresh grids
    correct, defined = 0, 0
    for grid_in, grid_out in heldout:
        rendered = M.evaluate(program, np.asarray(grid_in), MI.descriptors)
        if rendered is None:
            continue
        defined += 1
        if np.array_equal(rendered, np.asarray(grid_out)):
            correct += 1
    result.heldout_total = len(heldout)
    result.heldout_defined = defined
    result.heldout_correct = (defined == len(heldout) and correct == len(heldout))
    return result


# --------------------------------------------------------------------------
# fresh evaluation episodes, defined before anything is measured
# --------------------------------------------------------------------------

@dataclass
class Episode:
    seed: int
    family: tuple
    target_digest: str
    pairs: list
    heldout: list


def build_episode(seed: int, family: tuple, n_heldout: int = 4) -> Optional[Episode]:
    """One admissible episode: demonstrations for fitting, plus HELD-OUT grids
    that are never used for fitting or ranking."""
    schema = CD.sample_target(seed, family)
    grid_seeds = [seed * 97 + i for i in range(14)]
    concrete = V2C.instantiate_tables(schema, [CD.generate_grid(s) for s in grid_seeds[:6]])
    if concrete is None:
        return None
    pairs, _diag = CD.render_demonstrations(concrete, grid_seeds, min_demos=3)
    if len(pairs) < 3:
        return None
    #  the target must itself be recoverable, or the episode tests nothing
    if SF.fit_outcome(schema, pairs)["status"] != "EXACT_DEMONSTRATION_FIT":
        return None
    #  held-out grids from a disjoint seed range, rendered by the SAME target
    heldout = []
    for offset in range(200, 200 + 40):
        if len(heldout) >= n_heldout:
            break
        grid = CD.generate_grid(seed * 97 + offset)
        rendered = V2C._evaluate(concrete, grid)
        if rendered is None or np.array_equal(rendered, grid):
            continue
        heldout.append((grid, np.asarray(rendered)))
    if len(heldout) < n_heldout:
        return None
    return Episode(seed=seed, family=tuple(family),
                   target_digest=CV.digest(schema), pairs=pairs, heldout=heldout)


def study_code_hash() -> str:
    names = ("cora_tti/candidate_trace.py", "cora_tti/failure_signal_study.py",
             "cora_tti/meta_baseline.py", "cora_tti/scoped_slot_fitting.py")
    parts = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()
