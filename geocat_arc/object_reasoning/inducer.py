"""Program induction: the search over (segmentation, selector, action,
parameter-expression) space with zero-conflict acceptance and the blocking
LOO-by-reinduction gate (Section 3).

Lifts the proven geocat_arc/reasoning/rule_inducer.py pattern to object
level: the "cell context" becomes the object feature vector, the "output
color" becomes the typed delta; zero-conflict induce_rule -> selector
induction; majority-vote induce_partial_rule -> near-solve-only fuzzy
selectors; reasoning_engine._loo_reinduce_rule -> loo_validate here.

NO task IDs are visible anywhere in this module (hard constraint 6.1).

Implementation notes (inducer team):
- Selector induction consumes expressions.enumerate_expressions(PREDICATE)
  verbatim (true -> single tests -> relation_exists -> and2) and checks each
  candidate against the labeled feature table with memoized row masks; the
  first zero-conflict predicate in stream order is the smallest (MDL).
- Parameter induction is verified by SIMULATION: each candidate ActionRule
  is applied to every selected object via actions.apply_action and the
  resulting cells must exactly equal the observed output object cells.  This
  makes the check uniform across delta types (translate / recolor / copy /
  scale / reflect / rotate / composite) and lets raw TRANSLATE groups be
  re-expressed as MOVE_UNTIL_ADJACENT(target) — both spellings are legal
  (design decision 4).  Candidate order preserves the 2.4.1 preference
  (relational > feature > induced_map > constant).
- Tier structure (Section 3.5 collect-all): tier 1 = one rule per delta
  type; tier 2 = subgroups by raw parameter signature (still induced
  selectors — never positional lookups); first tier with a train-perfect
  program wins, all programs within the tier are collected and ranked.
- Shrink tasks (Section 3.6): Segment -> Select(induced pred) -> CropTo
  (bbox_self), plus the constant-shape uniform-fill form for
  shrink_const_out.
"""
from __future__ import annotations

import itertools
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject

from .actions import ObjectCanvas, apply_action, render_program
from .correspondence import delta_histogram, match_pair
from .expressions import (
    AlignExpr,
    AngleExpr,
    AxisExpr,
    ColorExpr,
    DirectionExpr,
    EnumerationContext,
    EvalContext,
    EvalError,
    GrowModeExpr,
    PatternExpr,
    PredExpr,
    RefExpr,
    RegionExpr,
    ScalarExpr,
    VecExpr,
    _small_preds,
    enumerate_expressions,
    evaluate,
    make_feature_map,
    parameter_class_of,
    substitute_free_slots,
)
from .features import (
    FEATURE_REGISTRY,
    RELATION_REGISTRY,
    compute_feature_table,
    register_builtin_features,
)
from .segmentation import SEGMENTATION_TRIAL_ORDER, evaluate_variant
from .types import (
    ALIGNMENTS,
    ANGLES,
    AXES,
    ActionRule,
    ComposedProgram,
    DeltaType,
    FailureStage,
    FeatureKind,
    FeatureTable,
    GridContext,
    GridPair,
    InducerFn,
    InductionResult,
    LibraryOperator,
    LOOReport,
    NearSolveRecord,
    ObjectDelta,
    ObjectProgram,
    ObjectRule,
    OutputSpec,
    PairCorrespondence,
    ParameterClass,
    SegmentationResult,
    SelectorRule,
    cell_colors_of,
)
from .guide_hook import kind_priority as _guide_kind_priority


def _guide_sort_keys(keys: list, guide_priority: dict[str, float]) -> list:
    """Stable sort of group keys by descending guide probability.

    Known kinds (present in ``guide_priority``) are sorted by descending
    probability.  Unknown kinds keep their original relative order and
    appear after all known kinds.  When ``guide_priority`` is empty,
    returns ``keys`` unchanged (zero cost when the guide is off).
    """
    if not guide_priority:
        return keys

    def _sort_key(i_gkey: tuple[int, object]) -> tuple[int, float, int]:
        i, gkey = i_gkey
        # gkey is a string (tier 1) or tuple (tier 2); extract delta name
        dt_name = gkey if isinstance(gkey, str) else gkey[0]
        prob = guide_priority.get(dt_name)
        if prob is not None:
            return (0, -prob, i)     # known: group 0, descending prob
        return (1, 0.0, i)           # unknown: group 1, stable order

    return [gkey for _, gkey in sorted(enumerate(keys), key=_sort_key)]


#: Minimum explained-object fraction for a NearSolveRecord (Section 5.1).
NEAR_SOLVE_MIN_FIT: float = 0.5

#: Default per-task wall-clock budget (seconds), compatible with the unified
#: harness timeouts (Section 3.5); callers may lower it.
DEFAULT_BUDGET_S: float = 60.0

def _CREATE_COHERENCE_ON() -> bool:
    """Round-16 env gate (read per call — fold- and test-safe)."""
    import os as _os
    return _os.environ.get("ARC_CREATE_COHERENCE", "") not in ("", "0")


#: Global (never per-task) enumeration caps — budget discipline, Section 3.5.
MAX_SELECTOR_CANDIDATES: int = 60000
MAX_ACTION_CANDIDATES: int = 4000
MAX_SEG_VARIANTS_TRIED: int = 4
MAX_ALTS_PER_PAIR: int = 6
MAX_LIBRARY_COMBOS: int = 128

#: Feature names whose tests would be positional/extensional lookups —
#: the POSITION_DEPENDENT analogue (Section 3.3 step 5).
_POSITIONAL_FEATURES: frozenset = frozenset({"bbox", "centroid"})

#: Symbol-leaf expression classes (axis/angle/direction/align slots):
#: constant by construction, allowed to stay constant per acceptance test A2.
_SYMBOL_EXPRS = (AxisExpr, AngleExpr, DirectionExpr, AlignExpr, GrowModeExpr)


@dataclass
class InductionConfig:
    """Search knobs — fixed defaults, tunable only globally (never per task).

    ``library`` supplies promoted operators (memory.FragmentLibrary
    contents); they are tried BEFORE raw enumeration but re-induce their free
    slots per task and pass the same gates (Section 5.3).  ``use_library``
    is the Requirement 1.2 --no-library ablation switch.
    """
    budget_s: float = DEFAULT_BUDGET_S
    max_selector_literals: int = 2
    max_expr_depth: int = 2
    max_rules: int = 4
    use_library: bool = True
    library: list[LibraryOperator] = field(default_factory=list)
    collect_all_in_tier: bool = True   # collect-all within a cost tier, then rank
    # -- Stage 2 (STAGE2_REQUIREMENTS.md) --
    max_composition_depth: int = 3     # 2.2.2; 1 = the --depth-1 ablation
    max_stage_candidates: int = 4      # 2.2.1: top-K partials expanded per level
    use_ranker: bool = True            # 3.3: --no-ranker ablation switch
    #: PAPER E2 ABLATION ONLY — NEVER a real acceptance path: when True,
    #: train-perfect programs are accepted even if the LOO gate rejects
    #: them (result.accepted set with loo attached for measurement).  The
    #: gate-off run quantifies what raw accuracy hides; certificates from
    #: such runs are meaningless BY DESIGN and stamped gate_off=True.
    accept_train_perfect: bool = False
    force_relational: bool = False     # Phase C: skip const/map params
    w_loo: float = 0.5                 # 3.1 score weights (deterministic, global)
    w_len: float = 0.01


@dataclass
class ConflictReport:
    """Zero-conflict bookkeeping surfaced into NearSolveRecord.residual."""
    selector_conflicts: int = 0
    parameter_conflicts: int = 0
    details: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal plumbing
# ---------------------------------------------------------------------------

class _BudgetExhausted(Exception):
    """Internal: per-task wall-clock budget hit; return best-so-far."""


@dataclass
class _Meta:
    """Per-search counters and event log (feeds the certificate)."""
    hypotheses: int = 0
    events: list[str] = field(default_factory=list)


def _check_deadline(deadline: Optional[float]) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise _BudgetExhausted


@dataclass
class _TableCtx:
    """Non-serialized evaluation context attached to a labeled FeatureTable
    (private extension: expressions need live objects + GridContexts)."""
    grid_ctxs: dict[int, GridContext] = field(default_factory=dict)
    objects: dict[tuple[int, int], ARCObject] = field(default_factory=dict)
    out_objects: dict[int, dict[int, ARCObject]] = field(default_factory=dict)
    orphans: list[ObjectDelta] = field(default_factory=list)
    corrs: dict[int, PairCorrespondence] = field(default_factory=dict)
    lossy: bool = False
    extremes: dict[tuple[int, str], tuple] = field(default_factory=dict)


def _octx(table: FeatureTable) -> _TableCtx:
    return table._octx  # type: ignore[attr-defined]


def _int_native(v: Any) -> Any:
    if isinstance(v, (np.integer,)):
        return int(v)
    return v


def _norm_cells(cell_colors: dict) -> dict:
    return {(int(r), int(c)): int(col) for (r, c), col in cell_colors.items()}


# ---------------------------------------------------------------------------
# Stage functions (each independently testable; induce_program composes them)
# ---------------------------------------------------------------------------

def _build_table(seg: SegmentationResult, train_pairs: list[GridPair],
                 chosen: dict[int, PairCorrespondence]) -> tuple[FeatureTable,
                                                                 ConflictReport]:
    """Feature rows for all input objects + delta labels for one chosen
    correspondence alternative per pair."""
    report = ConflictReport()
    octx = _TableCtx()
    all_rows = []
    feature_names: list[str] = []
    labels: dict[tuple[int, int], ObjectDelta] = {}
    from .correspondence import extract_deltas

    for i, (grid_in, _grid_out) in enumerate(train_pairs):
        in_objs = seg.input_objects[i]
        bg = seg.backgrounds[i]
        pair_table = compute_feature_table(in_objs, grid_in, bg,
                                           pair_index=i, role="input")
        all_rows.extend(pair_table.rows)
        feature_names = pair_table.feature_names
        octx.grid_ctxs[i] = GridContext(grid=grid_in, objects=in_objs,
                                        background=bg, pair_index=i,
                                        role="input", variant=seg.variant)
        for o in in_objs:
            octx.objects[(i, o.id)] = o

        corr = chosen[i]
        octx.corrs[i] = corr
        octx.out_objects[i] = {o.id: o for o in corr.output_objects}
        if not corr.is_object_preserving:
            octx.lossy = True
            report.details.append(f"pair {i}: correspondence lossy "
                                  f"({corr.unreconciled_pixels}px)")
        for delta in extract_deltas(corr,
                                    input_grid=grid_in.to_numpy()):
            if delta.input_object_id is None:
                octx.orphans.append(delta)
                report.details.append(
                    f"pair {i}: orphan output object(s) {delta.output_object_ids}")
            else:
                labels[(i, delta.input_object_id)] = delta

    table = FeatureTable(rows=all_rows, feature_names=feature_names,
                         labels=labels)
    table._octx = octx  # type: ignore[attr-defined]
    return table, report


def build_labeled_table(seg: SegmentationResult,
                        train_pairs: list[GridPair]) -> tuple[FeatureTable, ConflictReport]:
    """Section 3.3 step 1: best correspondence alternative per pair (see
    enumerate_labeled_tables for the generator over alternatives)."""
    for table, report in enumerate_labeled_tables(seg, train_pairs,
                                                  max_alternatives=1):
        return table, report
    raise ValueError("no correspondence alternative for these train pairs")


def enumerate_labeled_tables(seg: SegmentationResult, train_pairs: list[GridPair],
                             max_alternatives: int = 4) -> Iterator[
                                 tuple[FeatureTable, ConflictReport]]:
    """Iterator over (FeatureTable, ConflictReport) for each surviving
    correspondence alternative combination: ``max_alternatives`` best-first
    index combinations, plus at most one profile-diagonal combination per
    weighting profile (the same profile applied to every pair — reference-
    frame profiles like mirror_rows are only meaningful task-wide), deduped
    (budget discipline, Section 3.5)."""
    per_pair: list[list[PairCorrespondence]] = []
    for i, (grid_in, grid_out) in enumerate(train_pairs):
        alts = match_pair(seg.input_objects[i], seg.output_objects[i],
                          grid_in, grid_out, pair_index=i)
        if not alts:
            return
        per_pair.append(alts[:MAX_ALTS_PER_PAIR])

    combos = sorted(itertools.product(*(range(len(a)) for a in per_pair)),
                    key=lambda t: (sum(t), t))[:max_alternatives]
    # Profile-diagonal combos: a weighting/reference-frame profile is a
    # per-TASK correspondence hypothesis, so additionally try, for each
    # profile, the combination that uses THAT profile's alternative on every
    # pair (mirror-frame pairings are only meaningful applied consistently).
    # Appended AFTER the best-first combos, deduplicated — pure addition.
    from .correspondence import WEIGHT_PROFILES
    extras: list[tuple[int, ...]] = []
    for name in WEIGHT_PROFILES:
        combo = []
        for alts in per_pair:
            idx = next((k for k, a in enumerate(alts)
                        if a.weights_profile == name), None)
            if idx is None:
                break
            combo.append(idx)
        else:
            extras.append(tuple(combo))
    for extra in extras:
        if extra not in combos:
            combos.append(extra)
    for combo in combos:
        chosen = {i: per_pair[i][j] for i, j in enumerate(combo)}
        yield _build_table(seg, train_pairs, chosen)


# ---------------------------------------------------------------------------
# Selector induction (Section 3.3 step 2 — the object-level induce_rule)
# ---------------------------------------------------------------------------

def _selector_context(table: FeatureTable) -> EnumerationContext:
    """Enumeration bounds for selector predicates: registered feature names
    by kind (positional features excluded) + train-observed values."""
    bool_feats, scalar_feats, color_feats, cat_feats = [], [], [], []
    for name, spec in sorted(FEATURE_REGISTRY.items()):
        if name in _POSITIONAL_FEATURES:
            continue
        if spec.kind is FeatureKind.BOOL:
            bool_feats.append(name)
        elif spec.kind is FeatureKind.SCALAR:
            scalar_feats.append(name)
        elif spec.kind is FeatureKind.COLOR:
            color_feats.append(name)
        elif spec.kind is FeatureKind.CATEGORICAL:
            cat_feats.append(name)

    int_counts: dict[int, int] = {}
    strs: set[str] = set()
    for row in table.rows:
        for name in scalar_feats:
            try:
                v = row.value(name)
            except KeyError:
                continue
            if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
                v = int(v)
                int_counts[v] = int_counts.get(v, 0) + 1
        for name in cat_feats:
            try:
                v = row.value(name)
            except KeyError:
                continue
            if isinstance(v, str):
                strs.add(v)
    ints = [v for v, _ in sorted(int_counts.items(),
                                 key=lambda kv: (-kv[1], kv[0]))[:16]]

    colors: set[int] = set()
    octx = _octx(table)
    for obj in octx.objects.values():
        colors.add(int(obj.color))
    for out_map in octx.out_objects.values():
        for obj in out_map.values():
            colors.add(int(obj.color))

    return EnumerationContext(
        observed_colors=sorted(colors),
        observed_constants=sorted(ints) + sorted(strs),
        scalar_features=scalar_feats,
        bool_features=bool_feats,
        color_features=color_feats,
        categorical_features=cat_feats,
        relation_names=sorted(RELATION_REGISTRY),
    )


def _is_extensional(pred: PredExpr) -> bool:
    """Reject predicates referencing positional features (Section 3.3/5)."""
    if pred.op == "test":
        return pred.args[0] in _POSITIONAL_FEATURES
    return any(_is_extensional(a) for a in pred.args
               if isinstance(a, PredExpr))


def _pair_extreme(table: FeatureTable, pair: int, name: str) -> Optional[tuple]:
    """(min, max) of a numeric feature over one pair's rows; None if not
    orderable.  Matches expressions._eval_test @rank semantics."""
    octx = _octx(table)
    key = (pair, name)
    if key in octx.extremes:
        return octx.extremes[key]
    values = []
    for row in table.rows_for_pair(pair):
        try:
            values.append(row.value(name))
        except KeyError:
            octx.extremes[key] = None
            return None
    try:
        result = (min(values), max(values)) if values else None
    except TypeError:
        result = None
    octx.extremes[key] = result
    return result


def _eval_test_on_row(table: FeatureTable, row, feature: str, cmp: str,
                      value: Any) -> bool:
    """Table-backed evaluation of a single feature test (same semantics as
    expressions._eval_test; EvalError on undefined cases)."""
    try:
        fval = row.value(feature)
    except KeyError:
        raise EvalError(f"feature {feature!r} missing from table row") from None
    if value in ("@rank_min", "@rank_max"):
        extreme = _pair_extreme(table, row.pair_index, feature)
        if extreme is None:
            raise EvalError(f"@rank test on non-orderable feature {feature!r}")
        target = extreme[0] if value == "@rank_min" else extreme[1]
        is_extreme = fval == target
        if cmp == "==":
            return is_extreme
        if cmp == "!=":
            return not is_extreme
        raise EvalError(f"@rank tests support ==/!= only, got {cmp!r}")
    a, b = fval, value
    if isinstance(a, list):
        a = tuple(a)
    if isinstance(b, list):
        b = tuple(b)
    if cmp == "==":
        return a == b
    if cmp == "!=":
        return a != b
    if not isinstance(a, (int, float, np.integer, np.floating)) \
            or not isinstance(b, (int, float)):
        raise EvalError(f"ordering comparison {cmp!r} on non-numeric values")
    if cmp == "<":
        return a < b
    if cmp == ">":
        return a > b
    if cmp == "<=":
        return a <= b
    if cmp == ">=":
        return a >= b
    raise EvalError(f"unknown comparator: {cmp!r}")


def _pred_mask(pred: PredExpr, table: FeatureTable,
               cache: dict) -> Optional[frozenset]:
    """Set of (pair, object_id) keys the predicate selects, or None when the
    predicate is undefined (EvalError) on some row — a conflict, never a
    crash.  Memoized (Expr nodes are hashable)."""
    if pred in cache:
        return cache[pred]
    result: Optional[frozenset]
    if pred.op == "true":
        result = frozenset((r.pair_index, r.object_id) for r in table.rows)
    elif pred.op == "test":
        feature, cmp, value = pred.args
        selected = set()
        try:
            for row in table.rows:
                if _eval_test_on_row(table, row, feature, cmp, value):
                    selected.add((row.pair_index, row.object_id))
            result = frozenset(selected)
        except EvalError:
            result = None
    elif pred.op == "in_set":
        feature, values = pred.args
        vset = set(values)
        selected = set()
        try:
            for row in table.rows:
                if row.value(feature) in vset:
                    selected.add((row.pair_index, row.object_id))
            result = frozenset(selected)
        except (EvalError, KeyError):
            result = None
    elif pred.op == "and2":
        m1 = _pred_mask(pred.args[0], table, cache)
        m2 = _pred_mask(pred.args[1], table, cache)
        result = None if (m1 is None or m2 is None) else (m1 & m2)
    else:
        # relation_exists (and anything else): full expression evaluation.
        octx = _octx(table)
        selected = set()
        result = frozenset()
        try:
            for row in table.rows:
                key = (row.pair_index, row.object_id)
                obj = octx.objects[key]
                ectx = EvalContext(obj=obj, grid_ctx=octx.grid_ctxs[row.pair_index])
                if evaluate(pred, obj, ectx):
                    selected.add(key)
            result = frozenset(selected)
        except EvalError:
            result = None
    cache[pred] = result
    return result


def _feature_cardinality(table: FeatureTable, name: str) -> int:
    """Distinct values a feature takes across the table — the generalization
    score of rule_inducer._generalization_score lifted to selectors: a
    zero-conflict test on a high-cardinality feature is far more likely a
    coincidence than one on a low-cardinality (semantic) feature."""
    octx = _octx(table)
    key = (-1, f"__card__{name}")
    if key in octx.extremes:
        return octx.extremes[key]  # type: ignore[return-value]
    values = set()
    for row in table.rows:
        try:
            v = row.value(name)
        except KeyError:
            continue
        values.add(tuple(v) if isinstance(v, (list, tuple)) else v)
    card = max(1, len(values))
    octx.extremes[key] = card  # type: ignore[assignment]
    return card


def _pred_generalization_score(pred: PredExpr, table: FeatureTable) -> int:
    """Lower = more likely to generalize (fewer coincidental fits).

    Fixed vocabulary-kind tiers (the fold-determinism fix — canonical MDL
    ordering over the test's VALUE vocabulary, never per task):

      color-feature tests < bool tests < @rank tests < relation_exists <
      categorical literals < scalar literal thresholds,

    with feature cardinality as the secondary penalty inside a tier.  Color
    and bool tests use small closed vocabularies and @rank tests carry no
    train-bound literal, so N-1-pair reinduction converges on the same
    predicate; scalar thresholds (e.g. ``size < 13``) drift with the
    observed constants — the dominant cause of LOO-reinduction divergence
    in the 2026-07-02 failure analysis (Section 3.3 step 5)."""
    if pred.op == "true":
        return 0
    if pred.op == "test":
        name, _cmp, value = pred.args
        spec = FEATURE_REGISTRY.get(name)
        kind = spec.kind if spec is not None else None
        card = _feature_cardinality(table, name)
        if kind is FeatureKind.COLOR:
            return 10 + min(card, 9)
        if kind is FeatureKind.BOOL:
            return 14
        if value in ("@rank_min", "@rank_max"):
            return 20  # parameter-free rank test: no train-bound literal
        if kind is FeatureKind.CATEGORICAL:
            return 30 + card
        return 40 + card   # scalar literal thresholds: last resort
    if pred.op == "relation_exists":
        inner = pred.args[1]
        base = 25  # relations quantify over object pairs
        return base + (_pred_generalization_score(inner, table)
                       if isinstance(inner, PredExpr) else 0)
    return sum(_pred_generalization_score(a, table) for a in pred.args
               if isinstance(a, PredExpr))


def _induce_selector_for(table: FeatureTable, target: frozenset,
                         sel_ctx: EnumerationContext, cache: dict,
                         max_literals: int, deadline: Optional[float],
                         meta: _Meta) -> Optional[SelectorRule]:
    """Smallest zero-conflict predicate selecting exactly ``target`` across
    all pairs.  Collect-all within the minimal-literal tier, then rank by
    the generalization score (Section 3.3 step 5 / 3.5): fewest literals,
    then lowest feature cardinality, then stream order — this keeps LOO
    reinduction folds convergent on the same semantic predicate."""
    from .types import ExprType
    n = 0
    best: Optional[tuple[int, int, int, PredExpr]] = None
    for pred in enumerate_expressions(ExprType.PREDICATE, sel_ctx):
        n += 1
        meta.hypotheses += 1
        if n % 1024 == 0:
            _check_deadline(deadline)
        if n > MAX_SELECTOR_CANDIDATES:
            break
        lits = pred.literals
        if best is not None and lits > best[0]:
            break  # stream literal count is monotone across stages
        if lits > max_literals:
            continue
        if _is_extensional(pred):
            continue
        mask = _pred_mask(pred, table, cache)
        if mask is not None and mask == target:
            key = (lits, _pred_generalization_score(pred, table), n, pred)
            if best is None or key[:3] < best[:3]:
                best = key
    if best is None:
        # in_set fallback (round 5, from the selector census: ~90% of failed
        # groups are VALUE-SET separable but the grammar had no disjunctive
        # spelling): one candidate per non-positional feature — the members'
        # exact value set.  Induced like color_map keys (fold re-derives the
        # set from ITS members); every element is a bound literal, so any
        # grammar predicate that exists outranks it (this branch only runs
        # when none did).  Deterministic: features in sorted order, first
        # zero-conflict wins by (set size, cardinality, name).
        row_of = {(r.pair_index, r.object_id): r for r in table.rows}
        cands = []
        for name, spec in sorted(FEATURE_REGISTRY.items()):
            if name in _POSITIONAL_FEATURES:
                continue
            try:
                mv = {row_of[k].value(name) for k in target}
            except (KeyError, EvalError):
                continue
            if any(isinstance(v, (list, dict)) for v in mv):
                continue
            try:
                pred = PredExpr(op="in_set",
                                args=(name, tuple(sorted(mv, key=repr))))
            except Exception:
                continue
            mask = _pred_mask(pred, table, cache)
            if mask is not None and mask == target:
                cands.append((len(mv),
                              _pred_generalization_score(pred, table),
                              name, pred))
        if cands:
            cands.sort(key=lambda c: c[:3])
            pred = cands[0][3]
            return SelectorRule(predicate=pred, literals=pred.literals)
        return None
    pred = best[3]
    return SelectorRule(predicate=pred, literals=pred.literals)


def _induce_subset_selector(table: FeatureTable, targets: frozenset,
                            sel_ctx: EnumerationContext, cache: dict,
                            max_literals: int, deadline: Optional[float],
                            meta: _Meta) -> Optional[SelectorRule]:
    """Smallest predicate selecting a NONEMPTY-per-pair SUBSET of ``targets``
    (used by region-crop forms where any one qualifying object determines the
    same output region — e.g. every object inside the answer's partition
    block).  Same deterministic ranking as _induce_selector_for."""
    from .types import ExprType
    pairs = {r.pair_index for r in table.rows}
    n = 0
    best: Optional[tuple[int, int, int, PredExpr]] = None
    for pred in enumerate_expressions(ExprType.PREDICATE, sel_ctx):
        n += 1
        meta.hypotheses += 1
        if n % 1024 == 0:
            _check_deadline(deadline)
        if n > MAX_SELECTOR_CANDIDATES:
            break
        lits = pred.literals
        if best is not None and lits > best[0]:
            break
        if lits > max_literals:
            continue
        if _is_extensional(pred):
            continue
        mask = _pred_mask(pred, table, cache)
        if mask is None or not mask or not mask <= targets:
            continue
        if {k[0] for k in mask} != pairs:
            continue
        key = (lits, _pred_generalization_score(pred, table), n, pred)
        if best is None or key[:3] < best[:3]:
            best = key
    if best is None:
        return None
    pred = best[3]
    return SelectorRule(predicate=pred, literals=pred.literals)


def induce_selector(table: FeatureTable, delta_type: DeltaType,
                    max_literals: int = 2) -> Optional[SelectorRule]:
    """Zero-conflict selector induction (Section 3.3 step 2): the smallest
    predicate selecting EXACTLY the objects labeled ``delta_type`` in every
    train pair.  None if no zero-conflict selector exists."""
    target = frozenset(k for k, d in table.labels.items()
                       if d.delta_type is delta_type)
    if not target:
        return None
    return _induce_selector_for(table, target, _selector_context(table), {},
                                max_literals, None, _Meta())


def _induce_fuzzy_for(table: FeatureTable, target: frozenset,
                      sel_ctx: EnumerationContext,
                      cache: dict) -> Optional[tuple[SelectorRule, float]]:
    total = len(table.rows)
    if total == 0:
        return None
    from .types import ExprType
    best: Optional[tuple[float, int, PredExpr]] = None
    n = 0
    for pred in enumerate_expressions(ExprType.PREDICATE, sel_ctx):
        n += 1
        if pred.op == "and2" or pred.op == "relation_exists":
            break  # fuzzy fallback stays cheap: true + single tests only
        if _is_extensional(pred):
            continue
        mask = _pred_mask(pred, table, cache)
        if mask is None:
            continue
        acc = 1.0 - len(mask.symmetric_difference(target)) / total
        if best is None or acc > best[0]:
            best = (acc, n, pred)
    if best is None or best[0] >= 1.0:
        return None
    acc, _, pred = best
    return SelectorRule(predicate=pred, literals=pred.literals), acc


def induce_fuzzy_selector(table: FeatureTable, delta_type: DeltaType) -> \
        Optional[tuple[SelectorRule, float]]:
    """Majority-vote fallback (induce_partial_rule analogue): best selector
    with accuracy < 1.0.  ONLY feeds NearSolveRecords (Section 3.3 step 4)."""
    target = frozenset(k for k, d in table.labels.items()
                       if d.delta_type is delta_type)
    if not target:
        return None
    return _induce_fuzzy_for(table, target, _selector_context(table), {})


# ---------------------------------------------------------------------------
# Parameter induction (Section 3.3 step 3) — simulation-verified candidates
# ---------------------------------------------------------------------------

def _expected_cells(delta: ObjectDelta, octx: _TableCtx) -> dict:
    """Absolute (r, c) -> color the delta's OUTPUT objects occupy (empty for
    DELETE) — the simulation ground truth."""
    out_map = octx.out_objects.get(delta.pair_index, {})
    cells: dict = {}
    for oid in delta.output_object_ids:
        obj = out_map.get(oid)
        if obj is not None:
            cells.update(cell_colors_of(obj))
    return _norm_cells(cells)


def _action_fits(action: ActionRule, members: dict[tuple[int, int], ObjectDelta],
                 table: FeatureTable) -> bool:
    """Apply ``action`` to every member object; the produced cells must
    exactly equal the observed output cells (zero-conflict on parameters)."""
    octx = _octx(table)
    for key, delta in members.items():
        obj = octx.objects[key]
        gctx = octx.grid_ctxs[key[0]]
        canvas = ObjectCanvas(objects=[], height=gctx.grid.height,
                              width=gctx.grid.width,
                              background=gctx.background,
                              source_grid=gctx.grid)
        ectx = EvalContext(obj=obj, grid_ctx=gctx)
        try:
            produced = apply_action(canvas, obj, action, ectx)
        except EvalError:
            return False
        got: dict = {}
        for o in produced:
            got.update(cell_colors_of(o))
        if _norm_cells(got) != _expected_cells(delta, octx):
            return False
    return True


def _param_context(table: FeatureTable,
                   observed: list[Any]) -> EnumerationContext:
    """Enumeration bounds for parameter expressions: registered feature names
    by kind + the raw parameter values observed for this group (constants are
    proposed ONLY from these — last resort, Requirement 2.4.1)."""
    bool_feats, scalar_feats, color_feats, cat_feats = [], [], [], []
    for name, spec in sorted(FEATURE_REGISTRY.items()):
        if spec.kind is FeatureKind.BOOL:
            bool_feats.append(name)
        elif spec.kind is FeatureKind.SCALAR:
            scalar_feats.append(name)
        elif spec.kind is FeatureKind.COLOR:
            color_feats.append(name)
        elif spec.kind is FeatureKind.CATEGORICAL:
            cat_feats.append(name)
    colors: set[int] = set()
    octx = _octx(table)
    for obj in octx.objects.values():
        colors.add(int(obj.color))
    for out_map in octx.out_objects.values():
        for obj in out_map.values():
            colors.add(int(obj.color))
    for v in observed:
        if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9:
            colors.add(v)
    return EnumerationContext(
        observed_colors=sorted(colors),
        observed_constants=list(observed),
        scalar_features=scalar_feats,
        bool_features=bool_feats,
        color_features=color_feats,
        categorical_features=cat_feats,
        relation_names=sorted(RELATION_REGISTRY),
    )


#: Mode-flag parameter names (fixed vocabulary switches like axis/direction
#: symbols): excluded from the worst-parameter-class computation, A2.
_MODE_FLAG_PARAMS: frozenset = frozenset({"keep_original", "align", "mode",
                                          "conn", "transform_k",
                                          "transform_flip"})


def _rule_parameter_class(params: dict[str, Any]) -> ParameterClass:
    """Worst class over non-symbol, non-mode-flag params (axis/angle/
    direction/align slots are constant by construction and allowed to stay
    constant, A2)."""
    classes = [parameter_class_of(e) for name, e in params.items()
               if not isinstance(e, _SYMBOL_EXPRS)
               and name not in _MODE_FLAG_PARAMS]
    if not classes:
        return ParameterClass.CONSTANT
    return ParameterClass.worst(classes)


def _make_action(delta_type: DeltaType, params: dict[str, Any]) -> ActionRule:
    return ActionRule(delta_type=delta_type, params=params,
                      parameter_class=_rule_parameter_class(params))


def _split_const(exprs: list) -> tuple[list, list]:
    non_const = [e for e in exprs
                 if parameter_class_of(e) is not ParameterClass.CONSTANT]
    const = [e for e in exprs
             if parameter_class_of(e) is ParameterClass.CONSTANT]
    return non_const, const


def _group_observed(delta_type: DeltaType,
                    members: dict[tuple[int, int], ObjectDelta],
                    octx: _TableCtx) -> Optional[list[Any]]:
    """Raw observed parameter values for the group (feeds const proposals and
    induced color maps).  None = group unsupported by the action vocabulary."""
    observed: list[Any] = []
    color_map: dict[int, int] = {}
    map_ok = True
    for key, delta in members.items():
        if delta.residual_pixels > 0 and delta.delta_type in (
                DeltaType.KEEP, DeltaType.TRANSLATE):
            # lossy fallback matches can never be reproduced exactly, but the
            # simulation check will reject candidates anyway; keep going.
            pass
        p = delta.params
        if delta.delta_type is DeltaType.TRANSLATE:
            observed.append((int(p["dr"]), int(p["dc"])))
        elif delta.delta_type is DeltaType.RECOLOR:
            dst = int(p["color"])
            observed.append(dst)
            src = int(octx.objects[key].color)
            if src in color_map and color_map[src] != dst:
                map_ok = False
            color_map[src] = dst
        elif delta.delta_type is DeltaType.SCALE:
            observed.append(int(p["factor"]))
            observed.append((int(p.get("dr", 0)), int(p.get("dc", 0))))
        elif delta.delta_type in (DeltaType.REFLECT, DeltaType.ROTATE):
            observed.append((int(p.get("dr", 0)), int(p.get("dc", 0))))
        elif delta.delta_type is DeltaType.COPY:
            if p.get("colors") and any(c is not None for c in p["colors"]):
                return None  # per-copy recolor: out of Stage-1 scope
            for dr, dc in p.get("placements", []):
                if (int(dr), int(dc)) != (0, 0):
                    observed.append((int(dr), int(dc)))
        elif delta.delta_type is DeltaType.PAINT:
            pass  # no raw constants: the induced parameter is a source REF
        elif delta.delta_type is DeltaType.SYNTH_COPY:
            observed.append(tuple(int(x) for x in p["placement"]))
            if "color" in p:
                observed.append(int(p["color"]))
        elif delta.delta_type is DeltaType.COPY_PART:
            observed.append(tuple(int(x) for x in p["placement"]))
        elif delta.delta_type is DeltaType.EXTRACT_PART:
            observed.append(tuple(int(x) for x in p["placement"]))
            observed.append(tuple(int(x) for x in p["source_bbox"]))
        elif delta.delta_type is DeltaType.CONNECT:
            dst = int(p["color"])
            observed.append(dst)
            src = int(octx.objects[key].color)
            if src in color_map and color_map[src] != dst:
                map_ok = False
            color_map[src] = dst
        elif delta.delta_type is DeltaType.GROW:
            if "color" in p:
                dst = int(p["color"])
                observed.append(dst)
                src = int(octx.objects[key].color)
                if src in color_map and color_map[src] != dst:
                    map_ok = False
                color_map[src] = dst
            if "length" in p:
                observed.append(int(p["length"]))
            if "dr" in p or "dc" in p:   # translate+grow (round 4)
                observed.append((int(p.get("dr", 0)), int(p.get("dc", 0))))
        elif delta.delta_type is DeltaType.COMPOSITE:
            for part in p.get("parts", []):
                pd = ObjectDelta.from_dict(part)
                if pd.delta_type is DeltaType.TRANSLATE:
                    observed.append((int(pd.params["dr"]), int(pd.params["dc"])))
                elif pd.delta_type is DeltaType.RECOLOR:
                    dst = int(pd.params["color"])
                    observed.append(dst)
                    src = int(octx.objects[key].color)
                    if src in color_map and color_map[src] != dst:
                        map_ok = False
                    color_map[src] = dst
    if map_ok and len(color_map) >= 1 and delta_type in (
            DeltaType.RECOLOR, DeltaType.COMPOSITE, DeltaType.GROW,
            DeltaType.CONNECT) \
            and len(set(color_map.values())) >= 2:
        # a map to a SINGLE value is the constant in disguise: it ranks
        # above the constant spelling (induced_map < constant in the
        # lattice) yet generalizes WORSE — an unseen fold key gets
        # EvalError where the constant extends (round-4 regression:
        # fixed-color appendages died at LOO through {3:4,6:4}-style maps).
        observed.append(dict(color_map))
    return observed


def _feature_map_candidates(members: dict[tuple[int, int], ObjectDelta],
                            table: FeatureTable) -> list[ColorExpr]:
    """Induced feature_map ColorExprs for a RECOLOR group: for each
    registered SCALAR feature, the map {feature value -> target color} when
    it is single-valued across ALL members (zero-conflict).  Generic ordinal
    recolors (e.g. size_rank -> color, color_frequency_rank -> color) become
    one INDUCED_MAP rule instead of per-value constant subgroups — the same
    lift color_map provides for source-color keying (Section 2.4)."""
    targets: dict[tuple[int, int], int] = {}
    for key, delta in members.items():
        if delta.delta_type is not DeltaType.RECOLOR:
            return []
        targets[key] = int(delta.params["color"])
    row_of = {(r.pair_index, r.object_id): r for r in table.rows}
    out: list[ColorExpr] = []
    for name, spec in sorted(FEATURE_REGISTRY.items()):
        if spec.kind is not FeatureKind.SCALAR or name in _POSITIONAL_FEATURES:
            continue
        mapping: dict[int, int] = {}
        ok = True
        for key, dst in targets.items():
            row = row_of.get(key)
            if row is None:
                ok = False
                break
            try:
                v = row.value(name)
            except KeyError:
                ok = False
                break
            if isinstance(v, bool) or not isinstance(v, (int, np.integer)):
                ok = False
                break
            v = int(v)
            if mapping.get(v, dst) != dst:
                ok = False
                break
            mapping[v] = dst
        if ok and len(mapping) >= 2:   # len 1 is just a constant in disguise
            # Round-9 lever 1 (mined from LOO fold-divergence): when the map
            # is affine (color = value + offset), emit the ONE-bound-literal
            # relational spelling FIRST — it re-derives on any subset, while
            # the map memorizes one entry per row and drifts under folds.
            offsets = {dst - v for v, dst in mapping.items()}
            if len(offsets) == 1:
                off = offsets.pop()
                if all(0 <= v + off <= 9 for v in mapping):
                    out.append(ColorExpr(op="feature_affine",
                                         args=(str(name), int(off))))
            out.append(make_feature_map(name, mapping))
    return out


def _copy_period_candidates(members: dict[tuple[int, int], ObjectDelta],
                            ) -> list[tuple[int, int]]:
    """Candidate period vectors for periodic COPY placement, mined from the
    observed placement lattice: consecutive diffs of the sorted placements
    plus the placement nearest the origin (covers negative directions).
    Simulation rejects wrong candidates; this only bounds the proposal set."""
    periods: set[tuple[int, int]] = set()
    for delta in members.values():
        placements = sorted((int(p[0]), int(p[1]))
                            for p in delta.params.get("placements", [])
                            if (int(p[0]), int(p[1])) != (0, 0))
        if not placements:
            continue
        for a, b in zip(placements, placements[1:]):
            d = (b[0] - a[0], b[1] - a[1])
            if d != (0, 0):
                periods.add(d)
        periods.add(min(placements, key=lambda p: (abs(p[0]) + abs(p[1]), p)))
    return sorted(periods)


#: Bounds for mined COPY placement lattices (global, never per task).
MAX_LATTICE_BASES: int = 4
MAX_LATTICE_RAYS: int = 4
MAX_LATTICE_PERIODS: int = 16


def _copy_lattice_candidates(members: dict[tuple[int, int], ObjectDelta],
                             ) -> list[dict[str, tuple[int, int]]]:
    """Mined multi-vector COPY placement proposals (generalizing the single
    'period' mode), as raw {param_name: (dr, dc)} dicts:

      (a) rays: every observed placement is a positive multiple of one of
          <= MAX_LATTICE_RAYS primitive direction vectors (multi-ray / star
          emission, e.g. all four diagonals from a seed);
      (b) offsets+period: base offsets (the placements not reachable from
          another placement by one period step) repeated with one period
          vector — staggered/zigzag lattices;
      (c) offsets only: one small placement set shared by every member
          (spawn-at-relative-positions).

    Proposals are bounded and verified by simulation like every other
    candidate; wrong lattices die on the exact-cells check."""
    import math

    placement_sets: list[list[tuple[int, int]]] = []
    for _key, delta in sorted(members.items()):
        pl = sorted({(int(p[0]), int(p[1]))
                     for p in delta.params.get("placements", [])
                     if (int(p[0]), int(p[1])) != (0, 0)})
        if pl:
            placement_sets.append(pl)
    if not placement_sets:
        return []
    proposals: list[dict[str, tuple[int, int]]] = []

    # (a) rays: primitive directions of all placements.
    rays: set[tuple[int, int]] = set()
    ok = True
    for pl in placement_sets:
        for (r, c) in pl:
            g = math.gcd(abs(r), abs(c))
            if g == 0:
                ok = False
                break
            rays.add((r // g, c // g))
        if not ok:
            break
    if ok and 2 <= len(rays) <= MAX_LATTICE_RAYS:
        proposals.append({f"ray{i}": v for i, v in enumerate(sorted(rays))})

    # (b) offsets + period: for each candidate period (all pairwise diffs,
    # bounded), the bases are the placements whose predecessor by one period
    # step is neither another placement nor the origin.
    diffs: set[tuple[int, int]] = set()
    for pl in placement_sets:
        for i, a in enumerate(pl):
            for b in pl[i + 1:]:
                d = (b[0] - a[0], b[1] - a[1])
                if d != (0, 0):
                    diffs.add(d)
    for p in sorted(diffs, key=lambda d: (abs(d[0]) + abs(d[1]), d)
                    )[:MAX_LATTICE_PERIODS]:
        bases: set[tuple[int, int]] = set()
        for pl in placement_sets:
            pset = set(pl)
            bases |= {q for q in pl
                      if (q[0] - p[0], q[1] - p[1]) not in pset
                      and (q[0] - p[0], q[1] - p[1]) != (0, 0)}
        if 1 <= len(bases) <= MAX_LATTICE_BASES:
            prop = {f"offset{i}": v for i, v in enumerate(sorted(bases))}
            prop["period"] = p
            proposals.append(prop)

    # (c) offsets only: identical small placement set across members.
    uniq = {tuple(pl) for pl in placement_sets}
    if len(uniq) == 1 and 1 <= len(placement_sets[0]) <= MAX_LATTICE_BASES:
        proposals.append({f"offset{i}": v
                          for i, v in enumerate(placement_sets[0])})
    # MDL / fold-determinism ordering: fewer lattice vectors first (a 1-pair
    # fold must converge on the same minimal decomposition the full train
    # set picks), then smallest total displacement, then stable key.
    def _mdl_key(prop: dict) -> tuple:
        vecs = sorted(prop.items())
        return (len(vecs),
                sum(abs(v[0]) + abs(v[1]) for _n, v in vecs),
                json.dumps(vecs))
    proposals.sort(key=_mdl_key)
    return proposals


def _action_candidates(delta_type: DeltaType,
                       members: dict[tuple[int, int], ObjectDelta],
                       table: FeatureTable,
                       pctx: EnumerationContext) -> Iterator[ActionRule]:
    """Candidate ActionRules in 2.4.1 preference order for one delta group.
    Raw TRANSLATE groups also propose MOVE_UNTIL_ADJACENT(target) between the
    non-constant and constant vector spellings (design decision 4)."""
    from .types import ExprType

    if delta_type is DeltaType.KEEP:
        yield ActionRule(delta_type=DeltaType.KEEP)
        return
    if delta_type is DeltaType.DELETE:
        yield ActionRule(delta_type=DeltaType.DELETE)
        return

    if delta_type is DeltaType.TRANSLATE:
        vecs = list(enumerate_expressions(ExprType.VECTOR, pctx))
        non_const, const = _split_const(vecs)
        # merge the two motion spellings and order by (class, MDL size, key):
        # move_until_adjacent(target) is one node smaller than the equivalent
        # translate(gap_closing_vector(target, axis)) and carries no bound
        # axis literal, so it correctly sorts first (D3/MDL preference —
        # crucial for LOO-fold stability when a subset underdetermines axis).
        merged = [(_make_action(DeltaType.TRANSLATE, {"vector": v}), v)
                  for v in non_const]
        merged += [(_make_action(DeltaType.MOVE_UNTIL_ADJACENT,
                                 {"target": ref}), ref)
                   for ref in enumerate_expressions(ExprType.REF, pctx)
                   if ref.op != "self"]
        merged.sort(key=lambda t: (parameter_class_of(t[1]).rank, t[1].size,
                                   json.dumps(t[1].to_dict(), sort_keys=True,
                                              default=str)))
        for action, _ in merged:
            yield action
        for v in const:
            yield _make_action(DeltaType.TRANSLATE, {"vector": v})
        return

    if delta_type is DeltaType.RECOLOR:
        def _map_entries(c: ColorExpr) -> int:
            # MDL tiebreak for induced maps: fewer entries = smaller program
            # (a low-cardinality key like size_rank beats a raw-value key
            # like bbox_width) — fold-invariant, so LOO reinduction converges.
            if c.op == "color_map":
                return len(c.args[0])
            if c.op == "feature_map":
                return len(c.args[1])
            return 0

        cands = list(enumerate_expressions(ExprType.COLOR, pctx))
        cands += _feature_map_candidates(members, table)
        cands.sort(key=lambda c: (parameter_class_of(c).rank, c.size,
                                  _map_entries(c),
                                  json.dumps(c.to_dict(), sort_keys=True,
                                             default=str)))
        seen: set = set()
        for c in cands:
            if c in seen:
                continue
            seen.add(c)
            yield _make_action(DeltaType.RECOLOR, {"color": c})
        return

    if delta_type is DeltaType.GROW:
        # One action must reproduce EVERY member; candidates are proposed
        # per observed mode in GROW_MODES preference order.  Colors use the
        # full COLOR expression grammar (2.4.1 preference: relational >
        # feature > induced map > constant); ray lengths propose the
        # train-value-free to-border spelling FIRST, then non-constant
        # scalar expressions, then observed constants.
        from .growth import GROW_MODES
        raw = [m.params for m in members.values()]
        modes_present = {p.get("mode") for p in raw}

        def _color_exprs() -> list:
            cands = list(enumerate_expressions(ExprType.COLOR, pctx))
            cands.sort(key=lambda c: (parameter_class_of(c).rank, c.size,
                                      json.dumps(c.to_dict(), sort_keys=True,
                                                 default=str)))
            return cands

        # translate+grow (round 4): when any member MOVED, cross every mode
        # candidate with motion-vector spellings (non-constant relational
        # vectors first, then observed constants) — same preference as
        # TRANSLATE.  Unmoved groups get the plain (no-vector) spelling.
        moved = any("dr" in p or "dc" in p for p in raw)
        vec_variants: list = [None]
        if moved:
            vecs = list(enumerate_expressions(ExprType.VECTOR, pctx))
            non_const_v, const_v = _split_const(vecs)
            non_const_v.sort(key=lambda v: (parameter_class_of(v).rank,
                                            v.size,
                                            json.dumps(v.to_dict(),
                                                       sort_keys=True,
                                                       default=str)))
            # VECTOR-PHASE-MAJOR order (round-4 defect fix, traced): the
            # vector grammar has hundreds of relational spellings; a
            # color-major cross product puts the (simple color, observed
            # constant vector) combo ~16k candidates deep and
            # MAX_ACTION_CANDIDATES starves first.  Phases: no-vector,
            # then OBSERVED constant vectors (the minimal motion
            # hypothesis), then a capped canonical prefix of relational
            # vectors.  Every phase re-iterates all base candidates, so
            # simple colors are reached in each phase.
            vec_variants = [None] + const_v + non_const_v[:12]

        def _emit(params: dict):
            _grow_bases.append(dict(params))
            yield from ()

        _grow_bases: list[dict] = []

        for mode in GROW_MODES:
            if mode not in modes_present:
                continue
            mode_expr = GrowModeExpr(op="const", args=(mode,))
            if mode == "symmetry_complete":
                axes = sorted({p["axis"] for p in raw
                               if p.get("mode") == "symmetry_complete"})
                for ax in axes:
                    yield from _emit({"mode": mode_expr,
                                      "axis": AxisExpr(op="const",
                                                       args=(ax,))})
            elif mode == "mirror_edge":
                dirs = sorted({p["direction"] for p in raw
                               if p.get("mode") == "mirror_edge"})
                for d in dirs:
                    yield from _emit({"mode": mode_expr,
                                      "direction": DirectionExpr(
                                          op="const", args=(d,))})
            elif mode == "fill_interior":
                for c in _color_exprs():
                    yield from _emit({"mode": mode_expr, "color": c})
            elif mode == "halo":
                conns = sorted({int(p.get("conn", 4)) for p in raw
                                if p.get("mode") == "halo"})
                for conn in conns:
                    conn_expr = ScalarExpr(op="const", args=(conn,))
                    for c in _color_exprs():
                        yield from _emit({"mode": mode_expr, "color": c,
                                          "conn": conn_expr})
            elif mode == "ray":
                dirs = sorted({p["direction"] for p in raw
                               if p.get("mode") == "ray"})
                lengths = sorted({int(p["length"]) for p in raw
                                  if p.get("mode") == "ray"
                                  and "length" in p})
                scalars = list(enumerate_expressions(ExprType.SCALAR, pctx))
                non_const_len, _ = _split_const(scalars)
                # canonical prefix cap (round 4): dozens of scalar
                # spellings x 100+ colors explode the base pool and starve
                # MAX_ACTION_CANDIDATES; lengths appear only when a member
                # observed one, and to-border (no length) is emitted first.
                non_const_len.sort(
                    key=lambda e: (parameter_class_of(e).rank, e.size,
                                   json.dumps(e.to_dict(), sort_keys=True,
                                              default=str)))
                if not lengths:
                    non_const_len = []
                non_const_len = non_const_len[:8]
                for d in dirs:
                    d_expr = DirectionExpr(op="const", args=(d,))
                    for c in _color_exprs():
                        base = {"mode": mode_expr, "color": c,
                                "direction": d_expr}
                        yield from _emit(dict(base))
                        for ln in non_const_len:
                            yield from _emit(dict(base, length=ln))
                        for k in lengths:
                            yield from _emit(
                                dict(base,
                                     length=ScalarExpr(op="const",
                                                       args=(k,))))
            else:  # pattern
                # color-abstracted masks (round 4): shared mask + a full
                # COLOR expression slot — relational colors (host color,
                # induced maps) generalize where baked colors memorized.
                masks = {tuple(p["pattern"]) for p in raw
                         if p.get("mode") == "pattern" and "color" in p}
                if len(masks) == 1:
                    mask_expr = PatternExpr(op="const",
                                            args=(next(iter(masks)),))
                    for cexp in _color_exprs():
                        yield from _emit({"mode": mode_expr,
                                          "pattern": mask_expr,
                                          "color": cexp})
                # legacy colored patterns: only when all members agree
                patterns = {tuple(p["pattern"]) for p in raw
                            if p.get("mode") == "pattern"
                            and "color" not in p}
                if len(patterns) == 1 and modes_present == {"pattern"}:
                    yield from _emit(
                        {"mode": mode_expr,
                         "pattern": PatternExpr(op="const",
                                                args=(next(iter(patterns)),))})
        for v in vec_variants:
            for base in _grow_bases:
                yield _make_action(DeltaType.GROW,
                                   dict(base) if v is None
                                   else dict(base, vector=v))
        return

    if delta_type is DeltaType.SYNTH_COPY:
        raw = [m.params for m in members.values()]
        verbs = {p["verb"] for p in raw}
        if len(verbs) == 1:
            verb_expr = PatternExpr(op="const", args=((next(iter(verbs)),),))
            vecs = list(enumerate_expressions(ExprType.VECTOR, pctx))
            non_const_v, const_v = _split_const(vecs)
            non_const_v.sort(key=lambda v: (parameter_class_of(v).rank,
                                            v.size,
                                            json.dumps(v.to_dict(),
                                                       sort_keys=True,
                                                       default=str)))
            colors = list(enumerate_expressions(ExprType.COLOR, pctx)) \
                if any("color" in p for p in raw) else [None]
            for v in non_const_v[:24] + const_v:
                for c in colors[:40]:
                    params = {"verb": verb_expr, "placement": v}
                    if c is not None:
                        params["color"] = c
                    yield _make_action(DeltaType.SYNTH_COPY, params)
        return

    if delta_type is DeltaType.COPY_PART:
        # windows must agree across members (constant region rel. to self);
        # placements get the usual non-const-first vector treatment.
        raw = [m.params for m in members.values()]
        windows = {tuple(p["window"]) for p in raw}
        if len(windows) == 1:
            win = PatternExpr(op="const", args=(next(iter(windows)),))
            vecs = list(enumerate_expressions(ExprType.VECTOR, pctx))
            non_const_v, const_v = _split_const(vecs)
            non_const_v.sort(key=lambda v: (parameter_class_of(v).rank,
                                            v.size,
                                            json.dumps(v.to_dict(),
                                                       sort_keys=True,
                                                       default=str)))
            for v in non_const_v[:24] + const_v:
                yield _make_action(DeltaType.COPY_PART,
                                   {"window": win, "placement": v})
        return

    if delta_type is DeltaType.EXTRACT_PART:
        # Round 15: source (RegionExpr — relational: bbox of an object
        # selected by a predicate) + optional dihedral transform +
        # placement (VecExpr, non-const first per RELATIONAL-FIRST rule).
        raw = [m.params for m in members.values()]
        # Transform params must agree across members.
        transforms_k = {int(p["transform_k"]) for p in raw}
        transforms_flip = {bool(p["transform_flip"]) for p in raw}
        if len(transforms_k) != 1 or len(transforms_flip) != 1:
            return  # transforms must be uniform
        tk = next(iter(transforms_k))
        tf = next(iter(transforms_flip))
        tk_expr = ScalarExpr(op="const", args=(tk,))
        tf_expr = ScalarExpr(op="const", args=(1 if tf else 0,))
        # Source: relational RegionExprs first (bbox of REF), constant last.
        regions = list(enumerate_expressions(ExprType.REGION, pctx))
        non_const_r = [r for r in regions
                       if parameter_class_of(r) != ParameterClass.CONSTANT]
        const_r = [r for r in regions
                   if parameter_class_of(r) == ParameterClass.CONSTANT]
        non_const_r.sort(key=lambda r: (parameter_class_of(r).rank, r.size,
                                        json.dumps(r.to_dict(),
                                                   sort_keys=True,
                                                   default=str)))
        # Placement vectors
        vecs = list(enumerate_expressions(ExprType.VECTOR, pctx))
        non_const_v, const_v = _split_const(vecs)
        non_const_v.sort(key=lambda v: (parameter_class_of(v).rank,
                                        v.size,
                                        json.dumps(v.to_dict(),
                                                   sort_keys=True,
                                                   default=str)))
        params_base: dict = {"transform_k": tk_expr, "transform_flip": tf_expr}
        # RELATIONAL-FIRST: non-const sources x non-const placements first
        for src in non_const_r[:16]:
            for v in non_const_v[:24]:
                yield _make_action(DeltaType.EXTRACT_PART,
                                   dict(params_base, source=src, placement=v))
        # then non-const source x const placement
        for src in non_const_r[:16]:
            for v in const_v:
                yield _make_action(DeltaType.EXTRACT_PART,
                                   dict(params_base, source=src, placement=v))
        # then const source x non-const placement (legally flagged constant)
        for src in const_r:
            for v in non_const_v[:24] + const_v:
                yield _make_action(DeltaType.EXTRACT_PART,
                                   dict(params_base, source=src, placement=v))
        return

    if delta_type is DeltaType.CONNECT:
        # M2 verb 1: target REF (relational by construction) x COLOR grammar.
        refs = [r for r in enumerate_expressions(ExprType.REF, pctx)
                if r.op != "self"]
        refs.sort(key=lambda r: (r.size, json.dumps(r.to_dict(),
                                                    sort_keys=True,
                                                    default=str)))
        cols = list(enumerate_expressions(ExprType.COLOR, pctx))
        cols.sort(key=lambda c: (parameter_class_of(c).rank, c.size,
                                 json.dumps(c.to_dict(), sort_keys=True,
                                            default=str)))
        for ref in refs[:24]:
            for c in cols:
                yield _make_action(DeltaType.CONNECT,
                                   {"target": ref, "color": c})
        return

    if delta_type is DeltaType.COPY:
        keep_false = ScalarExpr(op="const", args=(0,))
        # (a) one copy at an expression displacement (k == 1), non-constant
        #     placements first (2.4.1 preference order).
        vecs = list(enumerate_expressions(ExprType.VECTOR, pctx))
        non_const_vecs, const_vecs = _split_const(vecs)
        k_one = ScalarExpr(op="const", args=(1,))
        for v in non_const_vecs:
            yield _make_action(DeltaType.COPY, {"k": k_one, "placement": v})
        # (b) copy-at-markers: one copy per object matching an induced
        #     predicate, bbox-center/origin aligned.  Train-value-free, so it
        #     ranks before constant placements (fold determinism).
        for pred in _small_preds(pctx):
            for align in ALIGNMENTS:
                base = {"targets": pred,
                        "align": AlignExpr(op="const", args=(align,))}
                yield _make_action(DeltaType.COPY, dict(base))
                yield _make_action(DeltaType.COPY,
                                   dict(base, keep_original=keep_false))
        # (c) constant single placements (last resort).
        for v in const_vecs:
            yield _make_action(DeltaType.COPY, {"k": k_one, "placement": v})
        # (d) periodic repetition until border, periods mined from the
        #     observed placement lattice.
        for dr, dc in _copy_period_candidates(members):
            p = VecExpr(op="const", args=(dr, dc))
            yield _make_action(DeltaType.COPY, {"period": p})
            yield _make_action(DeltaType.COPY,
                               {"period": p, "keep_original": keep_false})
        # (e) mined multi-vector lattices: rays / offsets(+period) — the
        #     multi-ray and zigzag generalizations of (d).
        for prop in _copy_lattice_candidates(members):
            params = {name: VecExpr(op="const", args=(v[0], v[1]))
                      for name, v in sorted(prop.items())}
            yield _make_action(DeltaType.COPY, dict(params))
            yield _make_action(DeltaType.COPY,
                               dict(params, keep_original=keep_false))
        return

    if delta_type is DeltaType.PAINT:
        # Template stamping: the only parameter is the same-mask source REF
        # whose per-cell colors are copied (relational by construction).
        for ref in enumerate_expressions(ExprType.REF, pctx):
            if ref.op == "self":
                continue
            yield _make_action(DeltaType.PAINT, {"source": ref})
        return

    if delta_type is DeltaType.SCALE:
        for s in enumerate_expressions(ExprType.SCALAR, pctx):
            yield _make_action(DeltaType.SCALE, {"factor": s})
        return

    if delta_type is DeltaType.REFLECT:
        needs_vector = any(
            (int(d.params.get("dr", 0)), int(d.params.get("dc", 0))) != (0, 0)
            for d in members.values())
        axes = [AxisExpr(op="const", args=(a,)) for a in AXES]
        if not needs_vector:
            for a in axes:
                yield _make_action(DeltaType.REFLECT, {"axis": a})
            return
        vecs = list(enumerate_expressions(ExprType.VECTOR, pctx))
        for a in axes:
            for v in vecs:
                yield _make_action(DeltaType.REFLECT, {"axis": a, "vector": v})
        return

    if delta_type is DeltaType.ROTATE:
        needs_vector = any(
            (int(d.params.get("dr", 0)), int(d.params.get("dc", 0))) != (0, 0)
            for d in members.values())
        angles = [AngleExpr(op="const", args=(a,)) for a in ANGLES]
        if not needs_vector:
            for a in angles:
                yield _make_action(DeltaType.ROTATE, {"angle": a})
            return
        vecs = list(enumerate_expressions(ExprType.VECTOR, pctx))
        for a in angles:
            for v in vecs:
                yield _make_action(DeltaType.ROTATE, {"angle": a, "vector": v})
        return

    if delta_type is DeltaType.COMPOSITE:
        # translate + recolor: fit the vector on POSITIONS first (colors are
        # changed by the recolor part), then the color; verify composed.
        octx = _octx(table)
        expected_pos = {}
        for key, delta in members.items():
            expected_pos[key] = set(_expected_cells(delta, octx))
        vec_fit = None
        for v in enumerate_expressions(ExprType.VECTOR, pctx):
            ok = True
            for key in members:
                obj = octx.objects[key]
                gctx = octx.grid_ctxs[key[0]]
                try:
                    dr, dc = evaluate(v, obj, EvalContext(obj=obj, grid_ctx=gctx))
                except EvalError:
                    ok = False
                    break
                moved = {(int(r + dr), int(c + dc)) for r, c in obj.cells}
                if moved != expected_pos[key]:
                    ok = False
                    break
            if ok:
                vec_fit = v
                break
        if vec_fit is None:
            return
        for c in enumerate_expressions(ExprType.COLOR, pctx):
            yield _make_action(DeltaType.COMPOSITE,
                               {"0:translate:vector": vec_fit,
                                "1:recolor:color": c})
        return


def _induce_action_for_group(table: FeatureTable, delta_type: DeltaType,
                             members: dict[tuple[int, int], ObjectDelta],
                             config: InductionConfig, deadline: Optional[float],
                             meta: _Meta) -> Optional[ActionRule]:
    """Zero-conflict parameter induction for one group: first candidate (in
    2.4.1 preference order) whose simulation reproduces every member's
    observed output cells exactly."""
    octx = _octx(table)
    observed = _group_observed(delta_type, members, octx)
    if observed is None:
        return None
    pctx = _param_context(table, observed)
    n = 0
    for action in _action_candidates(delta_type, members, table, pctx):
        n += 1
        meta.hypotheses += 1
        if n % 64 == 0:
            _check_deadline(deadline)
        if n > MAX_ACTION_CANDIDATES:
            break
        # Phase C: skip constant/map candidates when force_relational
        if config.force_relational and action.parameter_class.rank >= \
                ParameterClass.INDUCED_MAP.rank:
            continue
        if _action_fits(action, members, table):
            return action
    return None


def induce_parameters(table: FeatureTable, selector: SelectorRule,
                      delta_type: DeltaType,
                      config: InductionConfig) -> Optional[ActionRule]:
    """Section 3.3 step 3 (public contract wrapper): fit parameter
    expressions for the objects labeled ``delta_type``; zero-conflict on
    parameters, preference relational > feature > induced_map > constant."""
    members = {k: d for k, d in table.labels.items()
               if d.delta_type is delta_type}
    if not members:
        return None
    return _induce_action_for_group(table, delta_type, members, config,
                                    None, _Meta())


# ---------------------------------------------------------------------------
# Library-operator instantiation (Section 5.3 — tried before raw enumeration)
# ---------------------------------------------------------------------------

def _slot_contexts(fragment: dict) -> dict[str, str]:
    """slot_name -> 'raw' (a PredExpr test VALUE: literal binding) or 'expr'
    (an expression hole: Expr binding)."""
    contexts: dict[str, str] = {}

    def walk(d: Any, in_test_value: bool) -> None:
        if isinstance(d, dict) and d.get("expr_class") == "FreeSlotExpr":
            args = d.get("args", [])
            if args:
                contexts[str(args[0])] = "raw" if in_test_value else "expr"
            return
        if isinstance(d, dict) and "__tuple__" in d:
            for x in d["__tuple__"]:
                walk(x, False)
            return
        if not isinstance(d, dict) or "expr_class" not in d:
            return
        args = d.get("args", [])
        if d.get("expr_class") == "PredExpr" and d.get("op") == "test" \
                and len(args) == 3:
            walk(args[2], True)
            return
        for a in args:
            walk(a, False)

    walk(fragment.get("selector", {}).get("predicate", {}), False)
    for expr in (fragment.get("action", {}).get("params") or {}).values():
        walk(expr, False)
    return contexts


def _slot_pool(slot_type: str, context_kind: str, pctx: EnumerationContext,
               observed: list[Any]) -> list[Any]:
    """Candidate bindings for one free slot, bounded to observed values."""
    if context_kind == "raw":
        if slot_type == "color":
            return list(pctx.observed_colors)
        if slot_type == "scalar":
            return sorted({int(v) for v in pctx.observed_constants
                           if isinstance(v, int) and not isinstance(v, bool)})
        if slot_type in ("direction", "axis"):
            from .types import AXES as _AXES, DIRECTIONS as _DIRS
            return list(_DIRS if slot_type == "direction" else _AXES)
        return []
    # expression holes: constants of the slot's type (mined fragments free
    # exactly the induced constants) + the induced color map where relevant.
    if slot_type == "color":
        pool: list[Any] = [ColorExpr(op="const", args=(c,))
                           for c in pctx.observed_colors]
        for v in observed:
            if isinstance(v, dict):
                from .expressions import make_color_map
                pool.append(make_color_map(v))
        return pool
    if slot_type == "vector":
        vecs = sorted({(int(v[0]), int(v[1])) for v in observed
                       if isinstance(v, (tuple, list)) and len(v) == 2
                       and all(isinstance(x, int) for x in v)})
        return [VecExpr(op="const", args=(dr, dc)) for dr, dc in vecs]
    if slot_type == "scalar":
        ints = sorted({int(v) for v in observed
                       if isinstance(v, int) and not isinstance(v, bool)})
        return [ScalarExpr(op="const", args=(k,)) for k in ints]
    if slot_type == "direction":
        from .types import DIRECTIONS as _DIRS
        return [DirectionExpr(op="const", args=(d,)) for d in _DIRS]
    if slot_type == "axis":
        return [AxisExpr(op="const", args=(a,)) for a in AXES]
    return []


def _try_library_operator(op: LibraryOperator, table: FeatureTable,
                          groups: dict, sel_ctx: EnumerationContext,
                          mask_cache: dict, config: InductionConfig,
                          deadline: Optional[float],
                          meta: _Meta) -> Optional[tuple[Any, ObjectRule]]:
    """Instantiate a library fragment on this task: re-induce its free slots,
    require the resulting selector to be zero-conflict for a delta group and
    the action to reproduce the group exactly.  Returns (group_key, rule)."""
    try:
        rule = ObjectRule.from_dict(op.fragment)
        frag_dt = DeltaType(op.fragment["action"]["delta_type"])
    except Exception:
        return None
    group_dt = frag_dt
    if frag_dt is DeltaType.MOVE_UNTIL_ADJACENT:
        group_dt = DeltaType.TRANSLATE
    gkey = None
    for key, g in groups.items():
        if g["delta_type"] is group_dt:
            gkey = key
            break
    if gkey is None:
        return None
    members = groups[gkey]["members"]
    target = frozenset(members)
    octx = _octx(table)
    observed = _group_observed(group_dt, members, octx) or []
    pctx = _param_context(table, observed)
    contexts = _slot_contexts(op.fragment)
    slots = [(name, stype) for name, stype in op.free_slots]
    pred_slots = [name for name, stype in slots if stype == "predicate"]
    value_slots = [(name, stype) for name, stype in slots
                   if stype != "predicate"]
    induced_selector: Optional[SelectorRule] = None
    if pred_slots:
        # Action-schema operator (memory._abstract_action_schema): the whole
        # selector is one predicate hole, re-induced per task through the
        # normal zero-conflict path — same gate as raw enumeration.
        sel_frag = op.fragment.get("selector", {}).get("predicate", {})
        if len(pred_slots) != 1 or sel_frag.get("expr_class") != "FreeSlotExpr":
            return None
        induced_selector = _induce_selector_for(table, target, sel_ctx,
                                                mask_cache,
                                                config.max_selector_literals,
                                                deadline, meta)
        if induced_selector is None:
            return None
    pools = [_slot_pool(stype, contexts.get(name, "expr"), pctx, observed)
             for name, stype in value_slots]
    if any(not p for p in pools):
        return None
    n = 0
    for combo in itertools.product(*pools):
        n += 1
        meta.hypotheses += 1
        if n > MAX_LIBRARY_COMBOS:
            break
        if n % 16 == 0:
            _check_deadline(deadline)
        bindings = {name: value for (name, _), value in zip(value_slots, combo)}
        try:
            params = {k: substitute_free_slots(e, bindings)
                      for k, e in rule.action.params.items()}
            if induced_selector is not None:
                pred = induced_selector.predicate
            else:
                pred = substitute_free_slots(rule.selector.predicate, bindings)
        except (KeyError, EvalError):
            continue
        if induced_selector is None:
            # (an induced selector selects exactly ``target`` by construction)
            mask = _pred_mask(pred, table, mask_cache)
            if mask is None or mask != target:
                continue
        action = _make_action(frag_dt, params)
        if not _action_fits(action, members, table):
            continue
        literals = (induced_selector.literals if induced_selector is not None
                    else pred.literals if isinstance(pred, PredExpr) else 0)
        return gkey, ObjectRule(selector=SelectorRule(pred, literals),
                                action=action)
    return None


# ---------------------------------------------------------------------------
# Program assembly & verification (Sections 3.3 / 3.6 / 4.4)
# ---------------------------------------------------------------------------

def _grids_equal(a: Grid, b: Grid) -> bool:
    na, nb = a.to_numpy(), b.to_numpy()
    return na.shape == nb.shape and bool(np.array_equal(na, nb))


def _train_perfect(program: ObjectProgram, train_pairs: list[GridPair]) -> bool:
    for grid_in, grid_out in train_pairs:
        try:
            if not _grids_equal(render_program(program, grid_in), grid_out):
                return False
        except (EvalError, Exception):
            return False
    return True


def _pixel_fit(program: Optional[ObjectProgram],
               train_pairs: list[GridPair]) -> float:
    if program is None or not train_pairs:
        return 0.0
    fits = []
    for grid_in, grid_out in train_pairs:
        try:
            pred = render_program(program, grid_in).to_numpy()
        except Exception:
            fits.append(0.0)
            continue
        out = grid_out.to_numpy()
        if pred.shape != out.shape:
            fits.append(0.0)
        else:
            fits.append(float(np.mean(pred == out)))
    return float(np.mean(fits))


def _dedup_programs(programs: list[ObjectProgram]) -> list[ObjectProgram]:
    seen: set[str] = set()
    out = []
    for p in programs:
        key = json.dumps(p.to_dict(), sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def assemble_programs(seg: SegmentationResult, table: FeatureTable,
                      rules: list[ObjectRule],
                      train_pairs: list[GridPair]) -> list[ObjectProgram]:
    """Combine induced rules with an induced default action and an OutputSpec
    fit from the train pairs; return only train-perfect programs."""
    shapes_same = all((gi.height, gi.width) == (go.height, go.width)
                      for gi, go in train_pairs)
    candidates: list[ObjectProgram] = []

    if any(r.action.delta_type is DeltaType.CROP_TO for r in rules):
        candidates.append(ObjectProgram(
            segmentation_variant=seg.variant,
            rules=[r for r in rules
                   if r.action.delta_type is DeltaType.CROP_TO],
            default_action=ActionRule(delta_type=DeltaType.KEEP),
            output_spec=OutputSpec(mode="crop"),
        ))
    elif shapes_same:
        def _param_free(rule: ObjectRule, dt: DeltaType) -> bool:
            return rule.action.delta_type is dt and not rule.action.params

        # Variant A: default KEEP (parameterless KEEP rules folded in).
        rules_a = [r for r in rules if not _param_free(r, DeltaType.KEEP)]
        candidates.append(ObjectProgram(
            segmentation_variant=seg.variant, rules=rules_a,
            default_action=ActionRule(delta_type=DeltaType.KEEP),
            output_spec=OutputSpec(mode="same_as_input")))
        # Variant B: default DELETE (only when a DELETE group exists).
        if any(r.action.delta_type is DeltaType.DELETE for r in rules):
            rules_b = [r for r in rules if not _param_free(r, DeltaType.DELETE)]
            candidates.append(ObjectProgram(
                segmentation_variant=seg.variant, rules=rules_b,
                default_action=ActionRule(delta_type=DeltaType.DELETE),
                output_spec=OutputSpec(mode="same_as_input")))

    train_ok = _dedup_programs([p for p in candidates
                                if _train_perfect(p, train_pairs)])
    # Rank-order HERE (LOO-free key: literals, parameter class, rules, size)
    # so programs[0] is the same deterministic choice in a LOO reinduction
    # fold as in the full-train run — otherwise a fold could validate the
    # default-KEEP variant while acceptance picks the default-DELETE one,
    # and the accepted program would never have been fold-validated
    # (they differ on unseen objects even when train-equivalent).
    return rank_candidates(train_ok, {})


def _expr_value_bound_count(expr: Any) -> int:
    """Number of train-bound VALUE literals in one expression tree: raw color
    references, non-@rank test literals, const color/vector/scalar leaves,
    and one per induced-map entry.  Closed vocabularies (bool test values,
    @rank sentinels, axis/direction/align/angle symbols) are unbound.  The
    fold-invariant simplicity signal for cross-tier program ranking: a
    program spelled from bound literals drifts under N-1-pair reinduction,
    a relational/rank spelling does not."""
    from .expressions import _walk
    n = 0
    for node in _walk(expr):
        op = node.op
        if isinstance(node, RefExpr) and op == "nearest_object_of_color":
            n += 1
        elif isinstance(node, PredExpr) and op == "test":
            v = node.args[2]
            if not isinstance(v, bool) and isinstance(v, (int, str)) \
                    and v not in ("@rank_min", "@rank_max"):
                n += 1
        elif isinstance(node, PredExpr) and op == "in_set":
            n += len(node.args[1])
        elif op == "color_map":
            n += len(node.args[0])
        elif op == "feature_map":
            n += len(node.args[1])
        elif op == "feature_affine":
            n += 1                      # the offset is the only bound value
        elif op == "const" and isinstance(node, (ColorExpr, VecExpr,
                                                 ScalarExpr)):
            n += 1
        elif op == "const" and isinstance(node, PatternExpr):
            n += len(node.args[0]) if node.args else 0
    return n


def _stages_of(p) -> list[ObjectProgram]:
    """Uniform stage view: a flat ObjectProgram is its own single stage."""
    return list(p.stages) if isinstance(p, ComposedProgram) else [p]


def _program_value_bound_count(p) -> int:
    """Total train-bound value literals over selectors, action params,
    default action, and output-spec expressions.  Composed programs sum
    over their stages; reduction programs count their literal table
    entries (round 10)."""
    if hasattr(p, "value_bound_count"):
        return p.value_bound_count
    if isinstance(p, ComposedProgram):
        return sum(_program_value_bound_count(s) for s in p.stages)
    n = 0
    for r in p.rules:
        n += _expr_value_bound_count(r.selector.predicate)
        n += sum(_expr_value_bound_count(e) for e in r.action.params.values())
    n += sum(_expr_value_bound_count(e)
             for e in p.default_action.params.values())
    for e in (p.output_spec.region, p.output_spec.background,
              p.output_spec.fill):
        if e is not None:
            n += _expr_value_bound_count(e)
    return n


def rank_candidates(programs: list[ObjectProgram],
                    loo_reports: dict[int, LOOReport]) -> list[ObjectProgram]:
    """Generalization ranking (Section 3.3 step 5), canonical and
    fold-invariant (the round-3 cross-tier program-shape canonicalization):
    LOO margin desc, better worst parameter class, fewer train-bound value
    literals, fewer rules, fewer selector literals, smaller expression size,
    stable JSON key.  Semantic simplicity (parameter class + value-literal
    count) dominates structural counts so an N-1-pair reinduction fold
    converges on the same program shape the full train set picks."""
    def key(item: tuple[int, ObjectProgram]):
        i, p = item
        loo = loo_reports.get(i)
        loo_score = loo.score if loo is not None else 0.0
        max_lits = max((r.selector.literals for r in p.rules), default=0)
        return (-loo_score, p.worst_parameter_class.rank,
                _program_value_bound_count(p), len(_stages_of(p)),
                len(p.rules), max_lits, p.expression_size,
                json.dumps(p.to_dict(), sort_keys=True))
    return [p for _, p in sorted(enumerate(programs), key=key)]


def score_program(p, train_fit: float, loo_score: float,
                  config: InductionConfig) -> float:
    """Deterministic acceptance score (STAGE2_REQUIREMENTS 3.1):
    train fit + weighted LOO margin - weighted MDL length (expression size
    + rule count + composition depth, per D3).  Pure function of global
    config weights — never tuned per task."""
    length = p.expression_size + len(p.rules) + len(_stages_of(p))
    return train_fit + config.w_loo * loo_score - config.w_len * length


def rank_by_score(programs: list, loo_reports: dict[int, LOOReport],
                  config: InductionConfig,
                  train_fit: float = 1.0) -> list:
    """FINAL-selection ranking (3.1.1): deterministic score desc, ties
    broken by the same fold-invariant canonical key rank_candidates uses —
    so the accepted program is score-chosen, never discovery-order-chosen,
    and fold reinduction still converges on the same shape."""
    def key(item):
        i, p = item
        loo = loo_reports.get(i)
        loo_score = loo.score if loo is not None else 0.0
        max_lits = max((r.selector.literals for r in p.rules), default=0)
        return (-score_program(p, train_fit, loo_score, config),
                p.worst_parameter_class.rank, _program_value_bound_count(p),
                len(_stages_of(p)), len(p.rules), max_lits,
                p.expression_size, json.dumps(p.to_dict(), sort_keys=True))
    return [p for _, p in sorted(enumerate(programs), key=key)]


# ---------------------------------------------------------------------------
# Per-table induction (tier 1: one rule per delta type; tier 2: subgroups)
# ---------------------------------------------------------------------------

@dataclass
class _Attempt:
    """Diagnostics of one induction attempt (feeds near-solve records)."""
    programs: list[ObjectProgram] = field(default_factory=list)
    seg: Optional[SegmentationResult] = None
    fit_objects: float = 0.0
    fit_pixels: float = 0.0
    stage: FailureStage = FailureStage.SELECTOR
    explained_rules: list[dict] = field(default_factory=list)
    unexplained: list[dict] = field(default_factory=list)
    conflict: ConflictReport = field(default_factory=ConflictReport)
    histogram: dict[str, int] = field(default_factory=dict)
    program_partial: Optional[dict] = None
    library_used: list[str] = field(default_factory=list)


def _tier_groups(table: FeatureTable, split: bool) -> dict:
    """Group labels by delta type (tier 1) or by (delta type, raw parameter
    signature) (tier 2).  Values: {'delta_type', 'members'}."""
    groups: dict = {}
    for key, delta in sorted(table.labels.items()):
        if split:
            sig = json.dumps(
                {k: _int_native(v) for k, v in sorted(delta.params.items())},
                sort_keys=True, default=str)
            gkey = (delta.delta_type.value, sig)
        else:
            gkey = delta.delta_type.value
        g = groups.setdefault(gkey, {"delta_type": delta.delta_type,
                                     "members": {}})
        g["members"][key] = delta
    return groups


def _induce_rules(table: FeatureTable, groups: dict,
                  config: InductionConfig, sel_ctx: EnumerationContext,
                  mask_cache: dict, deadline: Optional[float], meta: _Meta,
                  guide_priority: Optional[dict[str, float]] = None,
                  ) -> tuple[dict, dict, dict]:
    """(rules by group key, failures by group key -> stage,
    library ops used: group key -> operator name).

    ``guide_priority``: when non-empty, group keys are iterated in
    descending guide probability (stable sort; unknown kinds keep their
    original relative order after known ones).  Ordering ONLY -- no
    candidates are added, removed, or rescored."""
    rules: dict = {}
    failures: dict = {}
    library_used: dict = {}

    if config.use_library:
        # Collect ALL operator hits per group, then choose canonically
        # (rule-dict JSON, then operator name) — removes the last library
        # discovery-order dependence (STAGE2_REQUIREMENTS Section 1 / 3.1).
        hits_by_group: dict = {}
        for op in config.library:
            hit = _try_library_operator(op, table, groups, sel_ctx,
                                        mask_cache, config, deadline, meta)
            if hit is not None:
                gkey, rule = hit
                hits_by_group.setdefault(gkey, []).append(
                    (json.dumps(rule.to_dict(), sort_keys=True), op.name,
                     rule))
        for gkey, hits in hits_by_group.items():
            hits.sort(key=lambda h: (h[0], h[1]))
            rules[gkey] = hits[0][2]
            library_used[gkey] = hits[0][1]

    for gkey in _guide_sort_keys(sorted(groups, key=str),
                                guide_priority or {}):
        if gkey in rules:
            continue
        _check_deadline(deadline)
        g = groups[gkey]
        target = frozenset(g["members"])
        selector = _induce_selector_for(table, target, sel_ctx, mask_cache,
                                        config.max_selector_literals,
                                        deadline, meta)
        if selector is None:
            failures[gkey] = "selector"
            continue
        action = _induce_action_for_group(table, g["delta_type"],
                                          g["members"], config, deadline, meta)
        if action is None:
            failures[gkey] = "parameter"
            continue
        rules[gkey] = ObjectRule(selector=selector, action=action)
    return rules, failures, library_used


def _attempt_from_rules(seg: SegmentationResult, table: FeatureTable,
                        groups: dict, rules: dict, failures: dict,
                        library_used: dict, report: ConflictReport,
                        train_pairs: list[GridPair],
                        config: InductionConfig) -> _Attempt:
    attempt = _Attempt(seg=seg, conflict=report,
                       library_used=sorted(set(library_used.values())))
    octx = _octx(table)
    all_deltas = list(table.labels.values()) + octx.orphans
    attempt.histogram = delta_histogram(all_deltas)

    total = len(table.rows)
    total_px = sum(o.size for o in octx.objects.values()) or 1
    explained = explained_px = 0
    ordered_rules: list[ObjectRule] = []
    for gkey in sorted(rules, key=str):
        rule = rules[gkey]
        members = groups[gkey]["members"]
        explained += len(members)
        explained_px += sum(octx.objects[k].size for k in members)
        ordered_rules.append(rule)
        attempt.explained_rules.append({
            "selector_expr": rule.selector.predicate.to_dict(),
            "action": rule.action.delta_type.value,
            "param_exprs": {k: e.to_dict()
                            for k, e in rule.action.params.items()},
            "n_objects_explained": len(members),
        })
    for gkey, stage in sorted(failures.items(), key=lambda kv: str(kv[0])):
        g = groups[gkey]
        example_key = sorted(g["members"])[0]
        example_row = next((r.to_dict() for r in table.rows
                            if (r.pair_index, r.object_id) == example_key), {})
        attempt.unexplained.append({
            "delta_type": g["delta_type"].value,
            "count": len(g["members"]),
            "example_features": example_row,
        })
        if stage == "selector":
            attempt.conflict.selector_conflicts += 1
        else:
            attempt.conflict.parameter_conflicts += 1
    for orphan in octx.orphans:
        attempt.unexplained.append({"delta_type": orphan.delta_type.value,
                                    "count": 1, "example_features": {}})

    attempt.fit_objects = explained / total if total else 0.0

    if len(ordered_rules) > config.max_rules + 2:
        attempt.stage = FailureStage.SELECTOR
        return attempt

    if not failures and ordered_rules is not None:
        non_default = [r for r in ordered_rules
                       if r.action.params
                       or r.action.delta_type not in (DeltaType.KEEP,
                                                      DeltaType.DELETE)]
        if len(non_default) <= config.max_rules:
            attempt.programs = assemble_programs(seg, table, ordered_rules,
                                                 train_pairs)

    if attempt.programs:
        attempt.fit_objects = 1.0
        attempt.fit_pixels = 1.0
        for p in attempt.programs:
            used = sorted({name for gkey, name in library_used.items()
                           if rules[gkey] in p.rules})
            if used:
                p.library_operators_used = used
        attempt.program_partial = attempt.programs[0].to_dict()
        return attempt

    # near-solve payload: partial program from the induced rules.
    if ordered_rules:
        partial = ObjectProgram(
            segmentation_variant=seg.variant, rules=ordered_rules,
            default_action=ActionRule(delta_type=DeltaType.KEEP),
            output_spec=OutputSpec(mode="same_as_input"))
        attempt.program_partial = partial.to_dict()
        attempt.fit_pixels = explained_px / total_px
    if octx.lossy or octx.orphans:
        attempt.stage = FailureStage.MATCHING
    elif any(s == "selector" for s in failures.values()):
        attempt.stage = FailureStage.SELECTOR
    elif failures:
        attempt.stage = FailureStage.PARAMETER
    else:
        attempt.stage = FailureStage.MATCHING  # rules complete, render failed
    return attempt


#: Low-cardinality semantic features used to partition a delta group whose
#: parameters cannot be explained by one expression (tier 2b) — fixed global
#: order, never per task.
_GROUP_SPLIT_FEATURES: tuple[str, ...] = ("color", "size", "hole_count")


def _feature_split_groups(table: FeatureTable, groups: dict, failures: dict,
                          feature: str) -> Optional[dict]:
    """Tier 2b: partition each FAILED group by a feature's observed value
    (successful groups stay whole).  None when the partition is trivial."""
    out: dict = {}
    changed = False
    row_of = {(r.pair_index, r.object_id): r for r in table.rows}
    for gkey, g in groups.items():
        if gkey not in failures:
            out[gkey] = g
            continue
        parts: dict = {}
        try:
            for key, delta in g["members"].items():
                v = row_of[key].value(feature)
                v = tuple(v) if isinstance(v, (list, tuple)) else v
                parts.setdefault(v, {})[key] = delta
        except KeyError:
            return None
        if len(parts) <= 1:
            out[gkey] = g
            continue
        changed = True
        for v in sorted(parts, key=str):
            out[f"{gkey}#{feature}={v}"] = {"delta_type": g["delta_type"],
                                            "members": parts[v]}
    return out if changed else None


def _induce_on_table(seg: SegmentationResult, table: FeatureTable,
                     report: ConflictReport, train_pairs: list[GridPair],
                     config: InductionConfig, deadline: Optional[float],
                     meta: _Meta) -> _Attempt:
    """Tier ladder on one labeled table (Section 3.5): tier 1 = one rule per
    delta type; tier 2a = subgroups by raw parameter signature; tier 2b =
    failed groups partitioned by a low-cardinality feature value.  First
    tier with train-perfect programs wins (collect-all within the tier)."""
    sel_ctx = _selector_context(table)
    mask_cache: dict = {}

    # Guide search-ordering (PLAY B STEP 3): computed ONCE per table from
    # this fold's own train_pairs (fold-safe by construction).  Ordering
    # only — no candidates added, removed, or rescored.
    guide_prio = _guide_kind_priority(train_pairs)

    groups1 = _tier_groups(table, split=False)
    rules1, failures1, lib1 = _induce_rules(table, groups1, config, sel_ctx,
                                            mask_cache, deadline, meta,
                                            guide_priority=guide_prio)
    attempt1 = _attempt_from_rules(seg, table, groups1, rules1, failures1,
                                   lib1, report, train_pairs, config)
    if attempt1.programs:
        return attempt1
    best = attempt1

    later_tiers: list[dict] = []
    # Tier 1b: absorb the KEEP group into one parameterized group at a time.
    # Identity is a member of every delta family (a mirror reversal's center
    # object translates by (0, 0); an already-resting object slides by 0),
    # so when tier 1's selectors cannot separate "unchanged" from "moved"
    # objects, the merged group with one shared parameter expression is the
    # smaller (MDL) and often the only zero-conflict program shape.
    keep_keys = [k for k, g in sorted(groups1.items(), key=lambda kv: str(kv[0]))
                 if g["delta_type"] is DeltaType.KEEP]
    if keep_keys and failures1:
        keep_members = groups1[keep_keys[0]]["members"]
        for gkey in _guide_sort_keys(sorted(groups1, key=str),
                                     guide_prio):
            g = groups1[gkey]
            if g["delta_type"] in (DeltaType.KEEP, DeltaType.DELETE):
                continue
            merged = {k: v for k, v in groups1.items() if k != keep_keys[0]}
            merged[gkey] = {"delta_type": g["delta_type"],
                            "members": {**g["members"], **keep_members}}
            later_tiers.append(merged)

    groups2a = _tier_groups(table, split=True)
    if len(groups2a) != len(groups1) and len(groups2a) <= config.max_rules + 2:
        later_tiers.append(groups2a)
    if failures1:
        for feature in _GROUP_SPLIT_FEATURES:
            split = _feature_split_groups(table, groups1, failures1, feature)
            if split is not None and len(split) <= config.max_rules + 2:
                later_tiers.append(split)

    # Collect-all ACROSS the later tiers, then rank fold-invariantly (the
    # round-3 canonicalization): tier order is a cost order, not a semantic
    # preference, and with N-1 pairs a different tier can fit first — the
    # dominant cause of LOO-reinduction shape divergence.  Ranking the union
    # with rank_candidates' canonical key makes full-train and fold runs
    # converge on the same program whenever both admit it.  (Tier 1 keeps
    # its fast path above: with zero failures the later tiers can only add
    # strictly dominated more-rule variants.)
    collected: list[ObjectProgram] = []
    collected_attempt: Optional[_Attempt] = None
    try:
        for groups_n in later_tiers:
            rules_n, failures_n, lib_n = _induce_rules(table, groups_n, config,
                                                       sel_ctx, mask_cache,
                                                       deadline, meta,
                                                       guide_priority=guide_prio)
            attempt_n = _attempt_from_rules(seg, table, groups_n, rules_n,
                                            failures_n, lib_n, report,
                                            train_pairs, config)
            if attempt_n.programs:
                collected.extend(attempt_n.programs)
                if collected_attempt is None:
                    collected_attempt = attempt_n
            elif attempt_n.fit_objects > best.fit_objects:
                best = attempt_n
    except _BudgetExhausted:
        if not collected:
            raise
    if collected and collected_attempt is not None:
        ranked = rank_candidates(_dedup_programs(collected), {})
        collected_attempt.programs = ranked
        collected_attempt.fit_objects = collected_attempt.fit_pixels = 1.0
        collected_attempt.program_partial = ranked[0].to_dict()
        return collected_attempt

    best = _add_fuzzy(best, table, groups1, failures1, sel_ctx, mask_cache)
    return best


def _add_fuzzy(attempt: _Attempt, table: FeatureTable, groups: dict,
               failures: dict, sel_ctx: EnumerationContext,
               mask_cache: dict) -> _Attempt:
    """Fuzzy (majority-vote) selectors for failed groups — near-solve
    enrichment ONLY (Section 3.3 step 4), never part of a solution."""
    for gkey, stage in failures.items():
        if stage != "selector":
            continue
        target = frozenset(groups[gkey]["members"])
        fuzzy = _induce_fuzzy_for(table, target, sel_ctx, mask_cache)
        if fuzzy is not None:
            rule, acc = fuzzy
            attempt.conflict.details.append(
                f"fuzzy selector for {groups[gkey]['delta_type'].value}: "
                f"accuracy={acc:.2f} predicate="
                f"{json.dumps(rule.predicate.to_dict(), sort_keys=True)}")
    return attempt


# ---------------------------------------------------------------------------
# Shrink flows (Section 3.6)
# ---------------------------------------------------------------------------

def _build_unlabeled_table(seg: SegmentationResult,
                           train_pairs: list[GridPair]) -> FeatureTable:
    octx = _TableCtx()
    all_rows = []
    names: list[str] = []
    for i, (grid_in, _grid_out) in enumerate(train_pairs):
        in_objs = seg.input_objects[i]
        bg = seg.backgrounds[i]
        t = compute_feature_table(in_objs, grid_in, bg, pair_index=i,
                                  role="input")
        all_rows.extend(t.rows)
        names = t.feature_names
        octx.grid_ctxs[i] = GridContext(grid=grid_in, objects=in_objs,
                                        background=bg, pair_index=i,
                                        role="input", variant=seg.variant)
        for o in in_objs:
            octx.objects[(i, o.id)] = o
    table = FeatureTable(rows=all_rows, feature_names=names, labels={})
    table._octx = octx  # type: ignore[attr-defined]
    return table


def _induce_shrink(seg: SegmentationResult, train_pairs: list[GridPair],
                   config: InductionConfig, deadline: Optional[float],
                   meta: _Meta) -> _Attempt:
    """Shrink tasks: Segment -> Select(induced pred) -> CropTo(bbox_self),
    or constant-shape uniform ColorExpr output (shrink_const_out)."""
    table = _build_unlabeled_table(seg, train_pairs)
    octx = _octx(table)
    attempt = _Attempt(seg=seg, stage=FailureStage.SELECTOR)

    # -- crop-to-region forms ---------------------------------------------
    # Canonical form order (deterministic, never per task): the object's own
    # bbox first, then the separator-partition block containing the object.
    # The block form may only displace the bbox form with a STRICTLY simpler
    # (fewer-literal) selector — MDL preference, keeps bbox programs stable.
    def _region_targets(region_fn) -> Optional[set]:
        targets: set[tuple[int, int]] = set()
        for i, (grid_in, grid_out) in enumerate(train_pairs):
            out = grid_out.to_numpy()
            data = grid_in.to_numpy()
            found = False
            for o in seg.input_objects[i]:
                reg = region_fn(grid_in, o)
                if reg is None:
                    continue
                r0, c0, r1, c1 = reg
                sub = data[r0:r1, c0:c1]
                if sub.shape == out.shape and np.array_equal(sub, out):
                    targets.add((i, o.id))
                    found = True
            if not found:
                return None
        return targets

    def _bbox_region(_grid: Grid, o: ARCObject):
        return tuple(int(x) for x in o.bounding_box)

    _blocks_cache: dict[int, tuple] = {}

    def _block_region(grid: Grid, o: ARCObject):
        from .expressions import _separator_blocks
        key = id(grid)
        if key not in _blocks_cache:
            _blocks_cache[key] = _separator_blocks(grid)
        row_runs, col_runs = _blocks_cache[key]
        r0, c0, r1, c1 = o.bounding_box
        row = next(((a, b) for a, b in row_runs if a <= r0 and r1 <= b), None)
        col = next(((a, b) for a, b in col_runs if a <= c0 and c1 <= b), None)
        if row is None or col is None:
            return None
        return (row[0], col[0], row[1], col[1])

    sel_ctx = _selector_context(table)
    mask_cache: dict = {}
    bbox_targets = _region_targets(_bbox_region)
    block_targets = _region_targets(_block_region)

    form_candidates: list[tuple[int, int, SelectorRule, RegionExpr, set]] = []
    if bbox_targets:
        selector = _induce_selector_for(table, frozenset(bbox_targets),
                                        sel_ctx, mask_cache,
                                        config.max_selector_literals,
                                        deadline, meta)
        if selector is not None:
            form_candidates.append((selector.literals, 0, selector,
                                    RegionExpr(op="bbox_self"), bbox_targets))
    if block_targets:
        selector = _induce_subset_selector(table, frozenset(block_targets),
                                           sel_ctx, mask_cache,
                                           config.max_selector_literals,
                                           deadline, meta)
        if selector is not None:
            form_candidates.append((selector.literals, 1, selector,
                                    RegionExpr(op="separator_block_self"),
                                    block_targets))

    if form_candidates:
        form_candidates.sort(key=lambda t: (t[0], t[1]))
        _lits, _prio, selector, region_expr, crop_targets = form_candidates[0]
        # synthetic CROP_TO labels for near-solve bookkeeping
        for key in crop_targets:
            table.labels[key] = ObjectDelta(pair_index=key[0],
                                            delta_type=DeltaType.CROP_TO,
                                            input_object_id=key[1])
        attempt.histogram = delta_histogram(list(table.labels.values()))
        action = _make_action(DeltaType.CROP_TO, {"region": region_expr})
        rule = ObjectRule(selector=selector, action=action)
        programs = assemble_programs(seg, table, [rule], train_pairs)
        if programs:
            attempt.programs = programs
            attempt.fit_objects = attempt.fit_pixels = 1.0
            attempt.program_partial = programs[0].to_dict()
            attempt.explained_rules.append({
                "selector_expr": selector.predicate.to_dict(),
                "action": DeltaType.CROP_TO.value,
                "param_exprs": {"region": action.params["region"].to_dict()},
                "n_objects_explained": len(crop_targets),
            })
            return attempt
        attempt.stage = FailureStage.PARAMETER
    elif bbox_targets:
        # bbox form exists but no zero-conflict selector: fuzzy for memory
        for key in bbox_targets:
            table.labels[key] = ObjectDelta(pair_index=key[0],
                                            delta_type=DeltaType.CROP_TO,
                                            input_object_id=key[1])
        attempt.histogram = delta_histogram(list(table.labels.values()))
        attempt.conflict.selector_conflicts += 1
        fuzzy = _induce_fuzzy_for(table, frozenset(bbox_targets), sel_ctx,
                                  mask_cache)
        if fuzzy is not None:
            rule_f, acc = fuzzy
            attempt.conflict.details.append(
                f"fuzzy crop selector accuracy={acc:.2f}")
        attempt.fit_objects = len(bbox_targets) / max(1, len(table.rows))

    # -- constant-shape uniform-color form (shrink_const_out) ------------
    shapes = {(go.height, go.width) for _gi, go in train_pairs}
    if len(shapes) == 1:
        h, w = next(iter(shapes))
        uniform_colors: list[Optional[int]] = []
        for _gi, go in train_pairs:
            vals = set(go.to_numpy().ravel().tolist())
            uniform_colors.append(int(next(iter(vals))) if len(vals) == 1
                                  else None)
        if all(c is not None for c in uniform_colors):
            pctx = _param_context(table, [c for c in uniform_colors])
            from .types import ExprType
            n = 0
            for cexpr in enumerate_expressions(ExprType.COLOR, pctx):
                n += 1
                meta.hypotheses += 1
                if n % 64 == 0:
                    _check_deadline(deadline)
                if n > MAX_ACTION_CANDIDATES:
                    break
                ok = True
                for i in range(len(train_pairs)):
                    objs = seg.input_objects[i]
                    if not objs:
                        ok = False
                        break
                    anchor = objs[0]
                    gctx = octx.grid_ctxs[i]
                    try:
                        got = int(evaluate(cexpr, anchor,
                                           EvalContext(obj=anchor,
                                                       grid_ctx=gctx)))
                    except EvalError:
                        ok = False
                        break
                    if got != uniform_colors[i]:
                        ok = False
                        break
                if not ok:
                    continue
                program = ObjectProgram(
                    segmentation_variant=seg.variant, rules=[],
                    default_action=ActionRule(delta_type=DeltaType.DELETE),
                    output_spec=OutputSpec(mode="constant_shape", height=h,
                                           width=w, fill=cexpr))
                if _train_perfect(program, train_pairs):
                    attempt.programs = [program]
                    attempt.fit_objects = attempt.fit_pixels = 1.0
                    attempt.program_partial = program.to_dict()
                    return attempt

    # -- tiled bbox crop (output = object crop repeated (th, tw) times, the
    # counts given by induced scalar expressions, e.g. count(color==c)) ----
    tile_targets: dict[tuple[int, int], tuple[int, int]] = {}
    every_tiled, any_multi = True, False
    for i, (grid_in, grid_out) in enumerate(train_pairs):
        out = grid_out.to_numpy()
        data = grid_in.to_numpy()
        found = False
        for o in seg.input_objects[i]:
            r0, c0, r1, c1 = o.bounding_box
            sub = data[r0:r1, c0:c1]
            h, w = sub.shape
            if h == 0 or w == 0 or out.shape[0] % h or out.shape[1] % w:
                continue
            th, tw = out.shape[0] // h, out.shape[1] // w
            if np.array_equal(np.tile(sub, (th, tw)), out):
                tile_targets[(i, o.id)] = (th, tw)
                found = True
                if th * tw > 1:
                    any_multi = True
        if not found:
            every_tiled = False
            break

    if every_tiled and any_multi and tile_targets:
        from .types import ExprType

        def _fit_tile_scalar(vals: dict):
            """ScalarExpr reproducing each target's tile count; the string
            sentinel 'one' when the dimension never tiles (param omitted)."""
            if all(int(v) == 1 for v in vals.values()):
                return "one"
            pctx = _param_context(table, sorted({int(v) for v in vals.values()}))
            n = 0
            for sexpr in enumerate_expressions(ExprType.SCALAR, pctx):
                n += 1
                meta.hypotheses += 1
                if n % 64 == 0:
                    _check_deadline(deadline)
                if n > MAX_ACTION_CANDIDATES:
                    break
                ok = True
                for key, want in vals.items():
                    obj = octx.objects[key]
                    gctx = octx.grid_ctxs[key[0]]
                    try:
                        got = evaluate(sexpr, obj,
                                       EvalContext(obj=obj, grid_ctx=gctx))
                    except EvalError:
                        ok = False
                        break
                    if not isinstance(got, (int, np.integer)) \
                            or int(got) != int(want):
                        ok = False
                        break
                if ok:
                    return sexpr
            return None

        th_expr = _fit_tile_scalar({k: v[0] for k, v in tile_targets.items()})
        tw_expr = _fit_tile_scalar({k: v[1] for k, v in tile_targets.items()})
        if th_expr is not None and tw_expr is not None:
            selector = _induce_selector_for(table, frozenset(tile_targets),
                                            sel_ctx, mask_cache,
                                            config.max_selector_literals,
                                            deadline, meta)
            if selector is not None:
                params: dict = {"region": RegionExpr(op="bbox_self")}
                if th_expr != "one":
                    params["tile_h"] = th_expr
                if tw_expr != "one":
                    params["tile_w"] = tw_expr
                action = _make_action(DeltaType.CROP_TO, params)
                rule = ObjectRule(selector=selector, action=action)
                for key in tile_targets:
                    table.labels[key] = ObjectDelta(
                        pair_index=key[0], delta_type=DeltaType.CROP_TO,
                        input_object_id=key[1])
                attempt.histogram = delta_histogram(list(table.labels.values()))
                programs = assemble_programs(seg, table, [rule], train_pairs)
                if programs:
                    attempt.programs = programs
                    attempt.fit_objects = attempt.fit_pixels = 1.0
                    attempt.program_partial = programs[0].to_dict()
                    attempt.explained_rules.append({
                        "selector_expr": selector.predicate.to_dict(),
                        "action": DeltaType.CROP_TO.value,
                        "param_exprs": {k: e.to_dict()
                                        for k, e in action.params.items()},
                        "n_objects_explained": len(tile_targets),
                    })
                    return attempt
    return attempt


# ---------------------------------------------------------------------------
# LOO-by-reinduction (Section 3.4 — the only blocking acceptance gate)
# ---------------------------------------------------------------------------

def loo_validate(program_inducer_fn: InducerFn,
                 train_pairs: list[GridPair]) -> LOOReport:
    """Exactly the reasoning_engine._loo_reinduce_rule pattern: for each
    held-out pair i, rerun the ENTIRE induction via ``program_inducer_fn`` on
    the remaining pairs, apply the resulting program to the held-out input
    with actions.render_program, require exact grid equality.  Single-pair
    tasks return folds=0 (the caller then requires non-constant parameter
    class to accept, Section 3.4)."""
    n = len(train_pairs)
    if n < 2:
        return LOOReport(folds=0, passed=0)
    passed = 0
    failed: list[int] = []
    divergence: list[dict] = []
    for hold in range(n):
        subset = [p for i, p in enumerate(train_pairs) if i != hold]
        held_in, held_out = train_pairs[hold]
        ok = False
        fold_program = None
        pred = None
        err = None
        try:
            result = program_inducer_fn(subset)
            if result is not None and result.program is not None:
                fold_program = result.program
                pred = render_program(result.program, held_in)
                ok = _grids_equal(pred, held_out)
        except Exception as exc:
            ok = False
            err = type(exc).__name__
        if ok:
            passed += 1
            continue
        failed.append(hold)
        trace = {"fold": hold, "fold_program": None, "cells_wrong": None,
                 "shape_mismatch": False, "pred_shape": None,
                 "expected_shape": [held_out.height, held_out.width],
                 "error": err}
        try:
            if fold_program is not None:
                trace["fold_program"] = fold_program.to_dict()
            if pred is not None:
                trace["pred_shape"] = [pred.height, pred.width]
                pa, ea = pred.to_numpy(), held_out.to_numpy()
                if pa.shape == ea.shape:
                    trace["cells_wrong"] = int((pa != ea).sum())
                else:
                    trace["shape_mismatch"] = True
        except Exception:
            pass  # tracing must never affect the gate verdict
        divergence.append(trace)
    return LOOReport(folds=n, passed=passed, failed_pair_indices=failed,
                     divergence=divergence)


# ---------------------------------------------------------------------------
# Top-level induction
# ---------------------------------------------------------------------------

def _better_attempt(a: Optional[_Attempt], b: _Attempt) -> _Attempt:
    if a is None:
        return b
    return b if b.fit_objects > a.fit_objects else a


def _collect_partial(sink: Optional[list], attempt: _Attempt) -> None:
    """Stage-2 stage-candidate collection (STAGE2 2.2.1): every attempt that
    clears the GENERIC near-solve threshold with an executable partial
    program is a potential composition stage.  No per-task tuning."""
    if sink is None or attempt.programs:
        return
    if attempt.program_partial is None \
            or attempt.fit_objects < NEAR_SOLVE_MIN_FIT:
        return
    sink.append(attempt)


def _induce_candidate(train_pairs: list[GridPair], config: InductionConfig,
                      deadline: Optional[float], meta: _Meta,
                      partial_sink: Optional[list] = None,
                      explore_all: bool = False) -> _Attempt:
    """Full search WITHOUT the LOO gate (used both by induce_program and by
    LOO reinduction folds).  Returns the best attempt (first attempt with
    train-perfect programs wins — cheapest-first, Section 3.5).
    ``partial_sink``, when given, receives near-solve-grade partial attempts
    for Stage-2 composition (2.2.1).  ``explore_all`` (round-2 lever, phase-B
    FORCED re-search only): disable the cross-variant parsimony skip so
    every eligible segmentation variant is searched and its sub-perfect
    partials reach the sink — a fast train-perfect first variant otherwise
    leaves phase B with an empty stage-1 pool."""
    register_builtin_features()
    if not train_pairs:
        return _Attempt(stage=FailureStage.SEGMENTATION)

    seg_candidates: list[SegmentationResult] = []
    fallback: Optional[SegmentationResult] = None
    fallback_key: Optional[tuple] = None
    for variant in SEGMENTATION_TRIAL_ORDER:
        result = evaluate_variant(variant, train_pairs)
        if result.coherent:
            seg_candidates.append(result)
        else:
            key = (result.coherence, result.pixel_coverage)
            if fallback_key is None or key > fallback_key:
                fallback, fallback_key = result, key
    coherent_any = bool(seg_candidates)
    if not seg_candidates and fallback is not None:
        seg_candidates = [fallback]
    # ROUND-4 LESSON (mirror-reversal LOO regression): granularity-mismatch
    # ORDERING is NOT fold-stable — a held-out pair can carry the merge, so
    # candidate order flips between folds and the cross-variant winner
    # diverges.  Ordering stays the fixed TRIAL ORDER; mismatch is used only
    # in eligibility (segmentation.py), never in per-fold selection.
    # ROUND-16 guard (c): create-orphan-relaxed variants rank AFTER
    # strictly-coherent variants within the trial order (no ranking
    # perturbation of existing solves).  Stable sort: trial order preserved
    # within each tier (strict=0, relaxed=1).
    seg_candidates.sort(key=lambda s: (1 if s.create_orphan_relaxed else 0))
    # ROUND-16 fix #3 (census rank 3): the cap truncates relaxed variants
    # (they sort last by guard (c)), so admission alone never got them
    # TRIED.  Under the flag, grant up to 2 extra slots reserved for
    # relaxed variants beyond the strict cap; strict behavior when off.
    strict_kept = [s for s in seg_candidates
                   if not s.create_orphan_relaxed][:MAX_SEG_VARIANTS_TRIED]
    if _CREATE_COHERENCE_ON():
        relaxed_kept = [s for s in seg_candidates
                        if s.create_orphan_relaxed][:2]
        seg_candidates = strict_kept + relaxed_kept
    else:
        seg_candidates = seg_candidates[:MAX_SEG_VARIANTS_TRIED]

    shapes_same = all((gi.height, gi.width) == (go.height, go.width)
                      for gi, go in train_pairs)

    best: Optional[_Attempt] = None

    # Cross-variant canonicalization (round 3): the trial order stays the
    # search order, but after a variant yields train-perfect programs the
    # remaining STRICTLY-COARSER variants (fewer total objects — cheap to
    # search by construction) are still tried, and the winner is chosen by
    # (canonical program key, fewer total objects, trial order).  Object
    # counts compare the same way on any pair subset (a coarser variant's
    # objects are unions of a finer one's), so an N-1-pair reinduction fold
    # converges on the same variant the full train set picks even when the
    # fold's smaller pair set lets a finer variant fit spuriously.
    def _seg_count(s: SegmentationResult) -> int:
        return (sum(len(objs) for objs in s.input_objects)
                + sum(len(objs) for objs in s.output_objects))

    _trial_index = {v: i for i, v in enumerate(SEGMENTATION_TRIAL_ORDER)}

    def _attempt_key(att: _Attempt) -> tuple:
        p = att.programs[0]
        max_lits = max((r.selector.literals for r in p.rules), default=0)
        return (p.worst_parameter_class.rank, _program_value_bound_count(p),
                len(p.rules), max_lits, p.expression_size)

    winners: list[tuple[tuple, int, int, _Attempt]] = []
    try:
        for seg in seg_candidates:
            _check_deadline(deadline)
            if any(len(objs) == 0 for objs in seg.input_objects):
                continue
            if not explore_all \
                    and winners and _seg_count(seg) >= min(w[1] for w in winners):
                continue  # can only lose the parsimony tie-break
            attempt_p: Optional[_Attempt] = None
            if shapes_same:
                # Collect-all ACROSS correspondence alternatives (STAGE2
                # Section 3.1: the former first-train-perfect-alternative
                # break was the last first-match site here); the union is
                # ranked canonically so full-train and fold runs converge.
                alt_programs: list[ObjectProgram] = []
                alt_attempt: Optional[_Attempt] = None
                for table, report in enumerate_labeled_tables(
                        seg, train_pairs, max_alternatives=4):
                    _check_deadline(deadline)
                    attempt = _induce_on_table(seg, table, report,
                                               train_pairs, config,
                                               deadline, meta)
                    best = _better_attempt(best, attempt)
                    _collect_partial(partial_sink, attempt)
                    if attempt.programs:
                        alt_programs.extend(attempt.programs)
                        if alt_attempt is None:
                            alt_attempt = attempt
                        if not config.collect_all_in_tier:
                            break
                if alt_programs and alt_attempt is not None:
                    ranked = rank_candidates(_dedup_programs(alt_programs),
                                             {})
                    alt_attempt.programs = ranked
                    alt_attempt.program_partial = ranked[0].to_dict()
                    attempt_p = alt_attempt
            else:
                attempt = _induce_shrink(seg, train_pairs, config,
                                         deadline, meta)
                best = _better_attempt(best, attempt)
                _collect_partial(partial_sink, attempt)
                if attempt.programs:
                    attempt_p = attempt
            if attempt_p is not None:
                winners.append((_attempt_key(attempt_p), _seg_count(seg),
                                _trial_index[seg.variant], attempt_p))
    except _BudgetExhausted:
        pass
    if winners:
        winners.sort(key=lambda w: (w[0], w[1], w[2]))
        return winners[0][3]

    if best is None:
        best = _Attempt(stage=FailureStage.SEGMENTATION,
                        seg=seg_candidates[0] if seg_candidates else None)
    if not coherent_any and not best.programs \
            and best.fit_objects < NEAR_SOLVE_MIN_FIT:
        best.stage = FailureStage.SEGMENTATION
    return best


def _residual_px(pred: Grid, target: Grid) -> int:
    """Pixel residual of a grid against the FINAL target: mismatched cells,
    or the whole target when shapes differ (a shape-fixing stage therefore
    strictly reduces residual)."""
    na, nb = pred.to_numpy(), target.to_numpy()
    if na.shape != nb.shape:
        return int(nb.size)
    return int(np.sum(na != nb))


def _composed_partial_attempt(cand: _Attempt, sub: _Attempt) -> _Attempt:
    """Near-solve payload for a FAILED composition (STAGE2 2.2.4): the
    stage-1 fragment is recorded alongside the deeper residual partial so
    compositions feed the cumulative loop like everything else."""
    partial = {"program_class": "composed_partial",
               "stage1": cand.program_partial,
               "rest": sub.program_partial}
    return _Attempt(
        programs=[], seg=cand.seg or sub.seg,
        fit_objects=sub.fit_objects, fit_pixels=sub.fit_pixels,
        stage=sub.stage,
        explained_rules=list(cand.explained_rules) + list(sub.explained_rules),
        unexplained=list(sub.unexplained), conflict=sub.conflict,
        histogram=dict(sub.histogram or cand.histogram),
        program_partial=partial,
        library_used=sorted(set(cand.library_used) | set(sub.library_used)))


def _stage_feature_vector(cand: _Attempt):
    """Featurize a stage-1 candidate for the search-order ranker (3.1.2);
    zeros on any failure so ranking degrades, never crashes."""
    import numpy as _np
    from geocat_arc.bayesian_program_search.program_features import (
        extract_features, object_feature_dim)
    try:
        return extract_features(ObjectProgram.from_dict(cand.program_partial))
    except Exception:
        return _np.zeros(object_feature_dim())


def _rule_ablated_candidates(attempt: _Attempt,
                             train_pairs: list[GridPair]) -> list[_Attempt]:
    """Phase-B stage-1 candidates (DECISIONS D16): one-rule-out ablations of
    train-perfect-but-LOO-rejected flat programs.  Dropping a rule exposes
    that rule's group as residual for a fresh stage-2 induction on the
    intermediate table (where its parameters may be relationally
    expressible).  Generic — no task or rule-content branching."""
    out: list[_Attempt] = []
    for prog in attempt.programs[:4]:
        if not isinstance(prog, ObjectProgram):
            continue
        if len(prog.rules) < 2:
            # Round-2 lever: SELECTOR-RESTRICTION ablations for 1-rule
            # programs (one-rule-out yields nothing for them).  The rule is
            # narrowed to a fixed, canonically ordered set of single feature
            # tests; a restricted stage-1 applies the (overfit) action to a
            # SUBSET of its objects, exposing the rest as residual for a
            # fresh stage-2 induction where the parameters may be
            # relationally expressible.  Fixed enumeration — fold-invariant,
            # no train-value peeking beyond the 0..9 color alphabet.
            restrictions: list[PredExpr] = [
                PredExpr(op="test", args=("color", "==", c))
                for c in range(10)
            ] + [
                PredExpr(op="test", args=("size_rank", "==", "@rank_max")),
                PredExpr(op="test", args=("size_rank", "==", "@rank_min")),
            ]
            for rule in prog.rules[:1]:
                for extra in restrictions:
                    narrowed = PredExpr(op="and2",
                                        args=(rule.selector.predicate, extra))
                    ablated = ObjectProgram(
                        segmentation_variant=prog.segmentation_variant,
                        rules=[ObjectRule(
                            selector=SelectorRule(
                                predicate=narrowed,
                                literals=rule.selector.literals + 1),
                            action=rule.action)],
                        default_action=prog.default_action,
                        output_spec=prog.output_spec,
                        library_operators_used=list(
                            prog.library_operators_used))
                    out.append(_Attempt(
                        seg=attempt.seg,
                        fit_objects=0.5,
                        fit_pixels=_pixel_fit(ablated, train_pairs),
                        program_partial=ablated.to_dict(),
                        library_used=list(prog.library_operators_used)))
            continue
        for i in range(len(prog.rules)):
            ablated = ObjectProgram(
                segmentation_variant=prog.segmentation_variant,
                rules=[r for j, r in enumerate(prog.rules) if j != i],
                default_action=prog.default_action,
                output_spec=prog.output_spec,
                library_operators_used=list(prog.library_operators_used))
            out.append(_Attempt(
                seg=attempt.seg,
                fit_objects=(len(prog.rules) - 1) / len(prog.rules),
                fit_pixels=_pixel_fit(ablated, train_pairs),
                program_partial=ablated.to_dict(),
                library_used=list(prog.library_operators_used)))
    return out


def _induce_composed(train_pairs: list[GridPair], config: InductionConfig,
                     deadline: Optional[float], meta: _Meta,
                     depth_left: int, force_compose: bool = False,
                     base_hints: Optional[list[dict]] = None) -> _Attempt:
    """Residual-driven composition search (STAGE2_REQUIREMENTS Section 2.2).

    Depth 1 is exactly the Stage-1 search.  Otherwise the top-K near-solve
    partials become stage-1 candidates: each is rendered per train pair and
    the next stage is induced recursively on the (rendered, target)
    residual pairs, under the SAME cooperative deadline (2.2.3 — no stage
    gets private wall-clock).  A stage must strictly reduce pixel residual
    on at least one pair (2.2.2 — identity stages are never admitted).
    All train-perfect compositions found join one canonically ranked pool
    (3.1); expansion ORDER is UCB-guided by the Bayesian linear ranker when
    config.use_ranker (3.1.2), with a per-call fresh posterior so folds
    stay deterministic.

    ``force_compose`` (phase B, DECISIONS D16): explore composition even
    when flat train-perfect programs exist — invoked by induce_program
    AFTER those programs fail the LOO gate, and re-run identically per LOO
    fold so the gate still validates the entire producing search.  Stage-1
    candidates then also include one-rule-out ablations of the rejected
    flat programs."""
    sink: Optional[list] = [] if depth_left > 1 else None
    attempt = _induce_candidate(train_pairs, config, deadline, meta, sink,
                                explore_all=force_compose)
    # Round-10 panel/reduction family: only fires when EVERY pair strictly
    # shrinks (induce_reduction_candidates returns [] otherwise, so
    # composition-residual recursion — same-shape pairs — never enters).
    # Runs inside _induce_composed so every LOO fold re-derives the whole
    # reduction search; candidates join the SAME canonical ranking pool.
    try:
        from .reduction import induce_reduction_candidates
        red = [p for p in induce_reduction_candidates(train_pairs)
               if _train_perfect(p, train_pairs)]
        meta.hypotheses += len(red)
    except Exception:
        red = []
    # Round-12 counting/summary: tiny-output shrink tasks
    try:
        from .counting import induce_counting_program, render_counting
        from .types import ReductionProgram as _RP
        cnt = induce_counting_program(train_pairs)
        if cnt is not None:
            if all(render_counting(cnt, gi).to_list() == go.to_list()
                   for gi, go in train_pairs):
                red.append(_RP(split={"kind": "counting"},
                               mode=cnt["mode"], params=cnt))
                meta.events.append("COUNTING_PROGRAM_FOUND")
    except Exception:
        pass
    # Round-12 symmetry completion + pixel rules (same-shape, only when the
    # object search found nothing): INSIDE _induce_composed so every LOO
    # fold re-derives them (round-12 lesson: a fallback placed only in
    # induce_program can never pass the gate — folds don't see it).
    if all((gi.height, gi.width) == (go.height, go.width)
           for gi, go in train_pairs):
        # Symmetry joins the pool UNCONDITIONALLY when it verifies: it is
        # RELATIONAL-class and fold-stable, so canonical ranking rightly
        # prefers it over 2-pair memorized object programs (the round-12
        # guard bug: gating on empty object search let fold memorizers
        # bypass a fold-perfect symmetry program).
        try:
            from .symmetry import (induce_symmetry_completion,
                                   render_symmetry_completion)
            from .types import ReductionProgram as _RP
            sym = induce_symmetry_completion(train_pairs)
            if sym is not None and all(
                    render_symmetry_completion(sym, gi).to_list() ==
                    go.to_list() for gi, go in train_pairs):
                red.append(_RP(split={"kind": "symmetry"},
                               mode=sym["symmetry"], params=sym))
                meta.events.append("SYMMETRY_COMPLETION_FOUND")
        except Exception:
            pass
        if not red and not attempt.programs:
            try:
                from .pixel_rules import (induce_pixel_rule,
                                          render_pixel_rule)
                from .types import ReductionProgram as _RP
                pix = induce_pixel_rule(train_pairs)
                if pix is not None and all(
                        render_pixel_rule(pix, gi).to_list() ==
                        go.to_list() for gi, go in train_pairs):
                    red.append(_RP(split={"kind": "pixel_rule"},
                                   mode=pix["mode"], params=pix))
                    meta.events.append("PIXEL_RULE_FOUND")
            except Exception:
                pass
    if red:
        pool = list(attempt.programs) + red
        attempt.programs = rank_candidates(pool, {})
        attempt.fit_objects = 1.0
        attempt.fit_pixels = 1.0
    if depth_left <= 1 or sink is None:
        return attempt
    if attempt.programs and not force_compose:
        return attempt
    if force_compose and attempt.programs:
        sink.extend(_rule_ablated_candidates(attempt, train_pairs))
    if not sink:
        return attempt
    best = attempt

    # Deterministic stage-1 pool: dedup by serialized partial, order by
    # explained fraction then canonical key, cap at K (2.2.1).
    seen: set[str] = set()
    pool: list[_Attempt] = []
    for cand in sorted(sink, key=lambda a: (-a.fit_objects, -a.fit_pixels,
                                            json.dumps(a.program_partial,
                                                       sort_keys=True))):
        key = json.dumps(cand.program_partial, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        pool.append(cand)
    pool = pool[:config.max_stage_candidates]
    if not pool:
        return best

    residual_before = [_residual_px(gi, go) for gi, go in train_pairs]
    overlay_candidates: list = []

    def _OVERLAY_ON() -> bool:
        # env-gated like ARC_DIHEDRAL_FRAMES (round-14 lesson: budget-wall
        # tasks/tests must pay zero cost for a family they don't use)
        import os as _os
        return _os.environ.get("ARC_OVERLAY", "") not in ("", "0")

    def _try_overlay(stage1, rendered) -> Optional["OverlayProgram"]:
        """Round-14 structured composition: when every wrong cell of the
        base render has a NON-BACKGROUND target, induce a PATCH on clean
        residual pairs (original_input, residual_target) and combine as
        OverlayProgram (patch nonbg overwrites base).  Runs inside
        _induce_composed, so LOO folds re-derive base and patch."""
        from .types import OverlayProgram
        residual_pairs: list[GridPair] = []
        for (gi, go), (rend, _) in zip(train_pairs, rendered):
            ra, ga = rend.to_numpy(), go.to_numpy()
            if ra.shape != ga.shape:
                return None
            wrong = ra != ga
            if not wrong.any():
                return None                 # base already perfect here
            if (ga[wrong] == 0).any():
                return None                 # needs clearing: out of scope
            resid = np.zeros_like(ga)
            resid[wrong] = ga[wrong]
            residual_pairs.append((gi, Grid(resid)))
        try:
            patch_attempt = _induce_candidate(residual_pairs, config,
                                              deadline, meta, None)
        except Exception:
            return None
        if not patch_attempt.programs:
            return None
        overlay = OverlayProgram(base=stage1,
                                 patch=patch_attempt.programs[0])
        if _train_perfect(overlay, train_pairs):
            return overlay
        return None

    def _expand(cand: _Attempt) -> tuple[Optional[tuple], float]:
        _check_deadline(deadline)
        try:
            stage1 = ObjectProgram.from_dict(cand.program_partial)
        except Exception:
            return None, 0.0
        rendered: list[GridPair] = []
        for gi, go in train_pairs:
            try:
                rendered.append((render_program(stage1, gi), go))
            except Exception:
                return None, 0.0
        residual_after = [_residual_px(r, go) for r, go in rendered]
        if not any(a < b for a, b in zip(residual_after, residual_before)):
            return None, 0.0  # monotone-progress gate (2.2.2)
        sub = _induce_composed(rendered, config, deadline, meta,
                               depth_left - 1)
        if not sub.programs and _OVERLAY_ON():
            # chain failed on this stage-1: remember it for the DEFERRED
            # overlay pass (never spends budget before the chain finishes)
            overlay_candidates.append((stage1, rendered))
        if sub.programs:
            sub_prog = sub.programs[0]
            stages = [stage1] + _stages_of(sub_prog)
            prov = [{"residual_before_px": int(sum(residual_before)),
                     "residual_after_px": int(sum(residual_after)),
                     "library_operators_used":
                         list(stage1.library_operators_used)}]
            if isinstance(sub_prog, ComposedProgram):
                prov += list(sub_prog.stage_provenance)
            else:
                prov += [{"residual_before_px": int(sum(residual_after)),
                          "residual_after_px": 0,
                          "library_operators_used":
                              list(sub_prog.library_operators_used)}]
            composed = ComposedProgram(stages=stages, stage_provenance=prov)
            if len(composed.stages) <= config.max_composition_depth \
                    and _train_perfect(composed, train_pairs):
                return ("solved", composed, sub), 1.0
        return ("partial", None, sub), float(sub.fit_objects)

    results: list[tuple] = []
    try:
        ordered = pool
        if config.use_ranker and len(pool) > 1:
            try:
                from geocat_arc.bayesian_program_search.search_loop import (
                    bayesian_search_v2)
                results = bayesian_search_v2(pool, _stage_feature_vector,
                                             _expand)
                ordered = []
            except ImportError:
                ordered = pool  # ranker unavailable -> canonical order
        for cand in ordered:
            outcome, score = _expand(cand)
            results.append((cand, outcome, score))
    except _BudgetExhausted as exc:
        got = getattr(exc, "partial_results", None)
        if got:
            results = list(got)

    composed_found: list = []
    for cand, outcome, _score in results:
        if not outcome:
            continue
        kind, composed, sub = outcome
        if kind == "solved" and composed is not None:
            composed_found.append(composed)
        elif sub is not None and sub.fit_objects > best.fit_objects:
            best = _composed_partial_attempt(cand, sub)
    # Overlay is a LAST-RESORT family, run only AFTER the whole chain
    # expansion found nothing (it must neither outrank fold-stable
    # programs nor consume budget ahead of the chain — both failure
    # modes observed in round 14).
    if not composed_found and not attempt.programs and _OVERLAY_ON():
        # hint bases (prior-run near-solve partials for THIS task) join
        # the overlay candidate list — rendered fresh per pair here
        for hint in (base_hints or []):
            try:
                from .types import program_from_dict as _pfd
                h_prog = _pfd(hint)
                h_rendered = [(render_program(h_prog, gi), go)
                              for gi, go in train_pairs]
                overlay_candidates.append((h_prog, h_rendered))
            except Exception:
                continue
        for stage1, rendered in overlay_candidates:
            try:
                _check_deadline(deadline)
            except _BudgetExhausted:
                break
            overlay = _try_overlay(stage1, rendered)
            if overlay is not None:
                meta.events.append("OVERLAY_COMPOSED")
                composed_found.append(overlay)
                break

    # Round-17 generative-composite path: LAST-RESORT after overlay,
    # env-gated ARC_GENERATIVE=1, zero cost when off.  Fold-safe by
    # construction (re-derives from the fold's pairs).
    def _GENERATIVE_ON() -> bool:
        import os as _os
        return _os.environ.get("ARC_GENERATIVE", "") not in ("", "0")

    if not composed_found and not attempt.programs and _GENERATIVE_ON():
        try:
            from .generative import induce_generative_candidates
            gen_candidates = induce_generative_candidates(train_pairs)
            if gen_candidates:
                meta.events.append("GENERATIVE_COMPOSITE_FOUND")
                composed_found.extend(gen_candidates)
        except Exception:
            pass

    # Stage-3 generative-composition path (ARC_GEN_COMPOSE=1):
    # base object-program + generative patch on the residual.
    # Fires AFTER all other paths; env-gated, zero cost when off.
    # The overlay path (ARC_OVERLAY) sealed as honest negative 0/70
    # because the object inducer can't generate content for residuals
    # that need lines/rays/fills — but the generative inducer CAN.
    # Fold-safe: runs inside _induce_composed, so every LOO fold
    # re-derives base and generative patch from the fold's pairs.
    def _GEN_COMPOSE_ON() -> bool:
        import os as _os
        return _os.environ.get("ARC_GEN_COMPOSE", "") not in ("", "0")

    if not composed_found and not attempt.programs and _GEN_COMPOSE_ON():
        from .types import OverlayProgram
        from .generative import induce_gen_compose_patch
        # Collect base candidates: sink pool partials + overlay bases
        # + the attempt's own best partial (even if pool is empty)
        gen_compose_bases: list = []
        for cand in pool[:8]:
            try:
                stage1_prog = ObjectProgram.from_dict(cand.program_partial)
                gen_compose_bases.append(stage1_prog)
            except Exception:
                continue
        for stage1, _rendered in overlay_candidates:
            if stage1 not in gen_compose_bases:
                gen_compose_bases.append(stage1)
        # Fallback: if pool & overlay_candidates are empty but the
        # attempt has a near-solve partial, use IT as a base candidate.
        if not gen_compose_bases and attempt.program_partial:
            try:
                fallback = ObjectProgram.from_dict(attempt.program_partial)
                gen_compose_bases.append(fallback)
            except Exception:
                pass
        for stage1 in gen_compose_bases:
            try:
                _check_deadline(deadline)
            except _BudgetExhausted:
                break
            try:
                overlay = induce_gen_compose_patch(
                    stage1, train_pairs, deadline=deadline)
            except Exception:
                continue
            if overlay is not None:
                meta.events.append("GEN_COMPOSE_FOUND")
                composed_found.append(overlay)
                break

    # P3 certified analogy: LAST RESORT after all other paths.
    # Env-gated ARC_ANALOGY=1, zero cost when off.  Fold-safe by
    # construction: runs inside _induce_composed, so every LOO fold
    # re-derives the adaptation from the fold's pairs.
    def _ANALOGY_ON() -> bool:
        import os as _os
        return _os.environ.get("ARC_ANALOGY", "") not in ("", "0")

    if not composed_found and not attempt.programs and _ANALOGY_ON():
        try:
            from .analogy import induce_by_analogy
            analogy_deadline = min(
                deadline if deadline else time.monotonic() + 15.0,
                time.monotonic() + 15.0)
            analogy_candidates = induce_by_analogy(
                train_pairs, deadline=analogy_deadline)
            if analogy_candidates:
                meta.events.append("ANALOGY_ADAPTED_FOUND")
                composed_found.extend(analogy_candidates)
        except Exception:
            pass

    if composed_found:
        ranked = rank_candidates(_dedup_programs(composed_found), {})
        return _Attempt(programs=ranked, seg=attempt.seg,
                        fit_objects=1.0, fit_pixels=1.0,
                        histogram=dict(attempt.histogram),
                        program_partial=ranked[0].to_dict())
    return best


def _attempt_to_result(attempt: _Attempt, meta: _Meta,
                       started: float) -> InductionResult:
    """Wrap a no-LOO attempt as an InductionResult (used for LOO folds)."""
    program = attempt.programs[0] if attempt.programs else None
    return InductionResult(
        task_id="", accepted=program is not None, program=program,
        train_fit_objects=attempt.fit_objects,
        train_fit_pixels=attempt.fit_pixels,
        segmentation=attempt.seg,
        hypotheses_enumerated=meta.hypotheses,
        induction_time_s=time.monotonic() - started,
        events=list(meta.events),
    )


def _near_solve_from_attempt(attempt: _Attempt,
                             loo_failures: list[int]) -> Optional[NearSolveRecord]:
    if attempt.fit_objects < NEAR_SOLVE_MIN_FIT:
        return None
    seg_value = attempt.seg.variant.value if attempt.seg else ""
    return NearSolveRecord(
        task_id="",
        timestamp=datetime.now(timezone.utc).isoformat(),
        segmentation_variant=seg_value,
        program_partial=attempt.program_partial,
        train_fit_pixels=attempt.fit_pixels,
        train_fit_objects=attempt.fit_objects,
        explained_rules=list(attempt.explained_rules),
        residual={
            "unexplained_deltas": list(attempt.unexplained),
            "conflict_report": {
                "selector_conflicts": attempt.conflict.selector_conflicts,
                "parameter_conflicts": attempt.conflict.parameter_conflicts,
            },
            "loo_failures": list(loo_failures),
        },
        delta_histogram=dict(attempt.histogram),
        failure_stage=attempt.stage.value,
    )


def induce_program(train_pairs: list[GridPair],
                   config: Optional[InductionConfig] = None,
                   base_hints: Optional[list[dict]] = None) -> InductionResult:
    """The full Section-3 procedure for one task (task_id-free; the engine
    stamps InductionResult.task_id afterward).  Never raises.

    ``base_hints``: serialized partial programs from the task's own prior
    near-solve records (the cumulative loop: near-solves are training
    data).  Constant within the task, so every LOO fold sees the same
    hints — used only as overlay-composition bases, never accepted
    without the full gate."""
    cfg = config or InductionConfig()
    started = time.monotonic()
    deadline = started + cfg.budget_s
    meta = _Meta(events=["TASK_OBSERVED"])

    depth = max(1, int(cfg.max_composition_depth))
    hints = list(base_hints or [])
    try:
        attempt = _induce_composed(train_pairs, cfg, deadline, meta, depth,
                                   base_hints=hints)
    except Exception:  # never raise (harness contract)
        attempt = _Attempt(stage=FailureStage.SEGMENTATION)

    if not attempt.programs:
        meta.events.append("HYPOTHESIS_REJECTED")
        near = _near_solve_from_attempt(attempt, [])
        if near is not None:
            meta.events.append("NEAR_SOLVED_STORED")
        return InductionResult(
            task_id="", accepted=False, program=None,
            train_fit_objects=attempt.fit_objects,
            train_fit_pixels=attempt.fit_pixels,
            loo=None, failure_stage=attempt.stage, near_solve=near,
            segmentation=attempt.seg,
            hypotheses_enumerated=meta.hypotheses,
            induction_time_s=time.monotonic() - started,
            events=list(meta.events),
        )

    meta.events.append("HYPOTHESIS_PROPOSED")

    def _fold_inducer(sub_pairs: list[GridPair]) -> InductionResult:
        # LOO-by-reinduction over the WHOLE Stage-2 search (STAGE2 4.1):
        # segmentation trial, tier ladder, residual-driven composition, and
        # ranking all re-run from the N-1 pairs.
        fold_started = time.monotonic()
        remaining = max(1.0, deadline - fold_started)
        fold_deadline = fold_started + min(cfg.budget_s, remaining)
        fold_meta = _Meta()
        fold_attempt = _induce_composed(sub_pairs, cfg, fold_deadline,
                                        fold_meta, depth, base_hints=hints)
        meta.hypotheses += fold_meta.hypotheses
        return _attempt_to_result(fold_attempt, fold_meta, fold_started)

    try:
        loo = loo_validate(_fold_inducer, train_pairs)
    except Exception:
        loo = LOOReport(folds=len(train_pairs), passed=0,
                        failed_pair_indices=list(range(len(train_pairs))))

    # FINAL selection by deterministic score among gate candidates (3.1.1),
    # never by discovery order.
    ranked = rank_by_score(attempt.programs,
                           {i: loo for i in range(len(attempt.programs))},
                           cfg)
    program = ranked[0]

    accepted = loo.all_passed or (
        loo.folds == 0
        and program.worst_parameter_class is not ParameterClass.CONSTANT) \
        or cfg.accept_train_perfect  # PAPER E2 ablation only

    if accepted:
        meta.events.append("HYPOTHESIS_ACCEPTED")
        return InductionResult(
            task_id="", accepted=True, program=program,
            train_fit_objects=1.0, train_fit_pixels=1.0, loo=loo,
            failure_stage=None, near_solve=None, segmentation=attempt.seg,
            hypotheses_enumerated=meta.hypotheses,
            induction_time_s=time.monotonic() - started,
            events=list(meta.events),
        )

    # Phase B (DECISIONS D16): a FLAT train-perfect program failed the LOO
    # gate — the overfit signature composition exists for.  Re-search with
    # forced composition under the SAME deadline; the whole forced search
    # re-runs per fold, so LOO-by-reinduction stays the only gate.
    if depth > 1 and not isinstance(program, ComposedProgram):
        try:
            forced = _induce_composed(train_pairs, cfg, deadline, meta,
                                      depth, force_compose=True)
        except Exception:
            forced = None
        if forced is not None and forced.programs \
                and isinstance(forced.programs[0], ComposedProgram):

            def _fold_inducer_forced(sub_pairs: list[GridPair]
                                     ) -> InductionResult:
                fold_started = time.monotonic()
                remaining = max(1.0, deadline - fold_started)
                fold_deadline = fold_started + min(cfg.budget_s, remaining)
                fold_meta = _Meta()
                fa = _induce_composed(sub_pairs, cfg, fold_deadline,
                                      fold_meta, depth, force_compose=True)
                meta.hypotheses += fold_meta.hypotheses
                return _attempt_to_result(fa, fold_meta, fold_started)

            try:
                loo_b = loo_validate(_fold_inducer_forced, train_pairs)
            except Exception:
                loo_b = LOOReport(folds=len(train_pairs), passed=0,
                                  failed_pair_indices=list(
                                      range(len(train_pairs))))
            ranked_b = rank_by_score(
                forced.programs,
                {i: loo_b for i in range(len(forced.programs))}, cfg)
            program_b = ranked_b[0]
            accepted_b = loo_b.all_passed or (
                loo_b.folds == 0
                and program_b.worst_parameter_class
                is not ParameterClass.CONSTANT)
            if accepted_b:
                meta.events.append("HYPOTHESIS_ACCEPTED")
                return InductionResult(
                    task_id="", accepted=True, program=program_b,
                    train_fit_objects=1.0, train_fit_pixels=1.0, loo=loo_b,
                    failure_stage=None, near_solve=None,
                    segmentation=attempt.seg,
                    hypotheses_enumerated=meta.hypotheses,
                    induction_time_s=time.monotonic() - started,
                    events=list(meta.events),
                )

    # Phase C: LOO-failed flat program with constant/map parameters —
    # the overfit signature the relational preference lattice exists to
    # prevent.  Re-search with force_relational to find a relational
    # spelling that re-derives from any subset.  The whole forced search
    # re-runs per fold, so LOO stays the only gate.
    if not cfg.force_relational \
            and not isinstance(program, ComposedProgram) \
            and program.worst_parameter_class.rank >= \
            ParameterClass.INDUCED_MAP.rank \
            and time.monotonic() < deadline - 5:
        cfg_c = InductionConfig(
            budget_s=max(10.0, deadline - time.monotonic()),
            max_selector_literals=cfg.max_selector_literals,
            max_expr_depth=cfg.max_expr_depth,
            max_rules=cfg.max_rules,
            use_library=cfg.use_library,
            library=list(cfg.library),
            max_composition_depth=1,
            force_relational=True,
            w_loo=cfg.w_loo, w_len=cfg.w_len,
        )
        try:
            forced_c = _induce_composed(train_pairs, cfg_c, deadline,
                                        meta, 1)
        except Exception:
            forced_c = None
        if forced_c is not None and forced_c.programs:
            def _fold_inducer_c(sub_pairs: list[GridPair]
                                ) -> InductionResult:
                fold_started = time.monotonic()
                remaining = max(1.0, deadline - fold_started)
                fold_deadline = fold_started + min(cfg_c.budget_s, remaining)
                fold_meta = _Meta()
                fa = _induce_composed(sub_pairs, cfg_c, fold_deadline,
                                      fold_meta, 1)
                meta.hypotheses += fold_meta.hypotheses
                return _attempt_to_result(fa, fold_meta, fold_started)

            try:
                loo_c = loo_validate(_fold_inducer_c, train_pairs)
            except Exception:
                loo_c = LOOReport(folds=len(train_pairs), passed=0,
                                  failed_pair_indices=list(
                                      range(len(train_pairs))))
            if loo_c.all_passed:
                ranked_c = rank_candidates(forced_c.programs, {})
                program_c = ranked_c[0]
                meta.events.append("HYPOTHESIS_ACCEPTED")
                meta.events.append("PHASE_C_RELATIONAL")
                return InductionResult(
                    task_id="", accepted=True, program=program_c,
                    train_fit_objects=1.0, train_fit_pixels=1.0,
                    loo=loo_c,
                    failure_stage=None, near_solve=None,
                    segmentation=attempt.seg,
                    hypotheses_enumerated=meta.hypotheses,
                    induction_time_s=time.monotonic() - started,
                    events=list(meta.events),
                )

    # Round-17 generative fallback: when the correspondence-based program
    # fails LOO, try the generative-composite path as a LAST RESORT.
    # Fold-safe: _induce_composed already tried generative inside each fold,
    # but only when no correspondence program existed.  Here we try it at
    # the top level AFTER LOO rejection, with its own LOO pass.
    def _GENERATIVE_ON_TOP() -> bool:
        import os as _os
        return _os.environ.get("ARC_GENERATIVE", "") not in ("", "0")

    if _GENERATIVE_ON_TOP():
        try:
            from .generative import induce_generative_candidates
            from .types import GenerativeProgram as _GP
            # Give the generative fallback a fixed 15s budget
            gen_deadline = time.monotonic() + 15.0
            gen_candidates = induce_generative_candidates(
                train_pairs, deadline=gen_deadline)
            if gen_candidates:
                meta.events.append("GENERATIVE_COMPOSITE_FOUND")
                gen_prog = gen_candidates[0]
                # LOO-by-reinduction for generative programs: re-derive
                # from N-1 pairs, verify on the held-out pair.
                def _gen_fold_inducer(sub_pairs):
                    fold_started = time.monotonic()
                    sub_cands = induce_generative_candidates(sub_pairs)
                    if sub_cands:
                        return InductionResult(
                            task_id="", accepted=True,
                            program=sub_cands[0],
                            train_fit_objects=1.0, train_fit_pixels=1.0,
                            loo=None, failure_stage=None, near_solve=None,
                            segmentation=None,
                            hypotheses_enumerated=0,
                            induction_time_s=time.monotonic() - fold_started,
                            events=[],
                        )
                    return InductionResult(
                        task_id="", accepted=False, program=None,
                        train_fit_objects=0.0, train_fit_pixels=0.0,
                        loo=None, failure_stage=FailureStage.MATCHING,
                        near_solve=None, segmentation=None,
                        hypotheses_enumerated=0,
                        induction_time_s=time.monotonic() - fold_started,
                        events=[],
                    )
                gen_loo = loo_validate(_gen_fold_inducer, train_pairs)
                if gen_loo.all_passed:
                    meta.events.append("HYPOTHESIS_ACCEPTED")
                    meta.events.append("GENERATIVE_LOO_PASSED")
                    return InductionResult(
                        task_id="", accepted=True, program=gen_prog,
                        train_fit_objects=1.0, train_fit_pixels=1.0,
                        loo=gen_loo, failure_stage=None, near_solve=None,
                        segmentation=attempt.seg,
                        hypotheses_enumerated=meta.hypotheses,
                        induction_time_s=time.monotonic() - started,
                        events=list(meta.events),
                    )
        except Exception:
            pass

    # Stage-3 gen-compose fallback: when the object program fails LOO,
    # try using it as a BASE for gen-compose overlay with a generative
    # patch. The generative patch explains the residual (lines/rays/fills
    # from input objects). Fold-safe: each LOO fold re-derives base AND
    # patch from the fold's pairs.
    def _GEN_COMPOSE_ON_TOP() -> bool:
        import os as _os
        return _os.environ.get("ARC_GEN_COMPOSE", "") not in ("", "0")

    if _GEN_COMPOSE_ON_TOP() and program is not None:
        try:
            from .generative import induce_gen_compose_patch
            gc_deadline = time.monotonic() + 15.0
            overlay = induce_gen_compose_patch(
                program, train_pairs, deadline=gc_deadline)
            if overlay is not None:
                meta.events.append("GEN_COMPOSE_FOUND")
                # LOO-by-reinduction: re-derive base+patch from N-1 pairs
                def _gc_fold_inducer(sub_pairs):
                    fold_started = time.monotonic()
                    fold_meta_gc = _Meta()
                    fd = fold_started + min(cfg.budget_s,
                                            max(1.0, deadline - fold_started))
                    fold_attempt = _induce_composed(
                        sub_pairs, cfg, fd, fold_meta_gc, depth,
                        base_hints=hints)
                    meta.hypotheses += fold_meta_gc.hypotheses
                    if fold_attempt.programs:
                        base_prog = fold_attempt.programs[0]
                        gc_patch = induce_gen_compose_patch(
                            base_prog, sub_pairs,
                            deadline=time.monotonic() + 10.0)
                        if gc_patch is not None:
                            return InductionResult(
                                task_id="", accepted=True,
                                program=gc_patch,
                                train_fit_objects=1.0,
                                train_fit_pixels=1.0,
                                loo=None, failure_stage=None,
                                near_solve=None, segmentation=None,
                                hypotheses_enumerated=0,
                                induction_time_s=(time.monotonic()
                                                  - fold_started),
                                events=[],
                            )
                    return InductionResult(
                        task_id="", accepted=False, program=None,
                        train_fit_objects=0.0, train_fit_pixels=0.0,
                        loo=None,
                        failure_stage=FailureStage.MATCHING,
                        near_solve=None, segmentation=None,
                        hypotheses_enumerated=0,
                        induction_time_s=(time.monotonic()
                                          - fold_started),
                        events=[],
                    )
                gc_loo = loo_validate(_gc_fold_inducer, train_pairs)
                if gc_loo.all_passed:
                    meta.events.append("HYPOTHESIS_ACCEPTED")
                    meta.events.append("GEN_COMPOSE_LOO_PASSED")
                    return InductionResult(
                        task_id="", accepted=True, program=overlay,
                        train_fit_objects=1.0, train_fit_pixels=1.0,
                        loo=gc_loo, failure_stage=None, near_solve=None,
                        segmentation=attempt.seg,
                        hypotheses_enumerated=meta.hypotheses,
                        induction_time_s=time.monotonic() - started,
                        events=list(meta.events),
                    )
        except Exception:
            pass

    # P3 certified-analogy top-level fallback: when the correspondence-
    # based program fails LOO, try adaptation from the certified corpus.
    # Fold-safe: each LOO fold re-derives the adaptation from the
    # fold's pairs.  Env-gated: ARC_ANALOGY=1, zero cost when off.
    def _ANALOGY_ON_TOP() -> bool:
        import os as _os
        return _os.environ.get("ARC_ANALOGY", "") not in ("", "0")

    if _ANALOGY_ON_TOP():
        try:
            from .analogy import induce_by_analogy
            analogy_deadline = time.monotonic() + 15.0
            analogy_candidates = induce_by_analogy(
                train_pairs, deadline=analogy_deadline)
            if analogy_candidates:
                meta.events.append("ANALOGY_ADAPTED_FOUND")
                analogy_prog = analogy_candidates[0]
                # LOO-by-reinduction for analogy programs
                def _analogy_fold_inducer(sub_pairs):
                    fold_started = time.monotonic()
                    sub_cands = induce_by_analogy(
                        sub_pairs,
                        deadline=time.monotonic() + 10.0)
                    if sub_cands:
                        return InductionResult(
                            task_id="", accepted=True,
                            program=sub_cands[0],
                            train_fit_objects=1.0,
                            train_fit_pixels=1.0,
                            loo=None, failure_stage=None,
                            near_solve=None, segmentation=None,
                            hypotheses_enumerated=0,
                            induction_time_s=(time.monotonic()
                                              - fold_started),
                            events=[],
                        )
                    return InductionResult(
                        task_id="", accepted=False, program=None,
                        train_fit_objects=0.0, train_fit_pixels=0.0,
                        loo=None,
                        failure_stage=FailureStage.MATCHING,
                        near_solve=None, segmentation=None,
                        hypotheses_enumerated=0,
                        induction_time_s=(time.monotonic()
                                          - fold_started),
                        events=[],
                    )
                analogy_loo = loo_validate(
                    _analogy_fold_inducer, train_pairs)
                if analogy_loo.all_passed:
                    meta.events.append("HYPOTHESIS_ACCEPTED")
                    meta.events.append("ANALOGY_LOO_PASSED")
                    return InductionResult(
                        task_id="", accepted=True,
                        program=analogy_prog,
                        train_fit_objects=1.0,
                        train_fit_pixels=1.0,
                        loo=analogy_loo,
                        failure_stage=None, near_solve=None,
                        segmentation=attempt.seg,
                        hypotheses_enumerated=meta.hypotheses,
                        induction_time_s=time.monotonic() - started,
                        events=list(meta.events),
                    )
        except Exception:
            pass

    # train-perfect but LOO-failed (or single-pair constant program):
    meta.events.append("HYPOTHESIS_REJECTED")
    attempt.stage = FailureStage.LOO
    attempt.program_partial = program.to_dict()
    near = _near_solve_from_attempt(attempt, loo.failed_pair_indices)
    if near is not None:
        # Lever-4 instrumentation: the fold programs that diverged, next to
        # the full-data program (program_partial) — miners diff the two.
        near.residual["loo_divergence"] = list(loo.divergence)
        meta.events.append("NEAR_SOLVED_STORED")
    return InductionResult(
        task_id="", accepted=False, program=None,
        train_fit_objects=1.0, train_fit_pixels=1.0, loo=loo,
        failure_stage=FailureStage.LOO, near_solve=near,
        segmentation=attempt.seg,
        hypotheses_enumerated=meta.hypotheses,
        induction_time_s=time.monotonic() - started,
        events=list(meta.events),
    )


def certify(result: InductionResult, task_id: str, run_id: str = "",
            harness_commit: str = "") -> "ProgramCertificate":
    """Glue (implemented): build the Section-5.5 certificate from an ACCEPTED
    InductionResult.  Raises ValueError if result is not accepted or LOO
    folds are missing (acceptance test A5)."""
    from .types import ProgramCertificate
    if not result.accepted or result.program is None:
        raise ValueError("certify() requires an accepted InductionResult")
    if result.loo is None or not result.loo.all_passed:
        raise ValueError("certify() requires a fully passed LOOReport (A5)")
    prog = result.program
    return ProgramCertificate(
        task_id=task_id,
        program=prog.to_dict(),
        segmentation_variant=(prog.segmentation_variant.value
                              if prog.segmentation_variant is not None
                              else "none"),  # reduction programs don't segment
        train_fit=1.0,
        loo_score=1.0,
        loo_folds=result.loo.folds,
        parameter_class=prog.worst_parameter_class.value,
        selector_literals=max((r.selector.literals for r in prog.rules), default=0),
        program_depth=prog.program_depth,
        expression_size=prog.expression_size,
        composition_depth=len(_stages_of(prog)),
        library_operators_used=list(prog.library_operators_used),
        invented_from_cluster=None,
        hypotheses_enumerated=result.hypotheses_enumerated,
        induction_time_s=result.induction_time_s,
        harness_commit=harness_commit,
        run_id=run_id,
    )
