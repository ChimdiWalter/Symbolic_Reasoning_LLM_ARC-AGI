"""Core typed data model for Stage-1 object-level program induction.

This module is the dependency root of ``geocat_arc.object_reasoning``: every
other module in the package imports from here, and this module imports only
from the standard library, numpy, and ``geocat_arc.perception``.

Contract (STAGE1_REQUIREMENTS.md):
- Section 2: hypothesis = (segmentation variant, selector expr, action, param exprs).
- Section 4: accepted solutions serialize to complete, human-inspectable JSON
  (registry names + arguments; no opaque closures in artifacts).
- Section 5: NearSolveRecord / ProgramCertificate schemas.

Serialization convention: every persistent dataclass has ``to_dict()`` /
``from_dict(d)`` producing/consuming plain JSON-able dicts.  Expression nodes
carry an ``"expr_class"`` tag resolved through ``EXPR_CLASS_REGISTRY`` (which
``expressions.py`` populates at import time).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Optional, Union

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject


# ---------------------------------------------------------------------------
# Enums (fixed vocabularies — Sections 2.1, 2.3, 2.4.1, 5.1)
# ---------------------------------------------------------------------------

class SegmentationVariant(Enum):
    """Perception-lattice variants, Section 2.1. Trial order is
    S1,S2,S3,S5,S4,S6,S7 (S7 appended last: coarser proximity grouping is
    only consulted when the connectivity-based variants are incoherent)."""
    S1_SAME_COLOR_4 = "S1"
    S2_SAME_COLOR_8 = "S2"
    S3_MULTICOLOR_4 = "S3"
    S4_MULTICOLOR_8 = "S4"
    S5_BG_ADAPTIVE = "S5"
    S6_COLOR_LAYERS = "S6"
    S7_PROXIMITY_MULTICOLOR = "S7"


#: Fixed trial order per Requirement 2.1.1 (never reordered per task ID).
#: Round-9 lever 5: order refreshed from the certified-corpus win histogram
#: (outputs/corpus_priors.json; v12: S1 23, S2 8, S3 4, S5 4, S6 3, S4 1,
#: S7 1) — a CONSTANT learned between runs, so fold-invariant by
#: construction.  Only change vs the hand-authored order: S6 before S4.
SEGMENTATION_TRIAL_ORDER: tuple[SegmentationVariant, ...] = (
    SegmentationVariant.S1_SAME_COLOR_4,
    SegmentationVariant.S2_SAME_COLOR_8,
    SegmentationVariant.S3_MULTICOLOR_4,
    SegmentationVariant.S5_BG_ADAPTIVE,
    SegmentationVariant.S4_MULTICOLOR_8,
    SegmentationVariant.S6_COLOR_LAYERS,
    SegmentationVariant.S7_PROXIMITY_MULTICOLOR,
)


class DeltaType(Enum):
    """Typed object-delta vocabulary, Sections 2.3 / 3.2.
    FILL_LINE added round 12: axis-aligned line through an object's
    centroid/edge, to grid boundary or until hitting another object."""
    KEEP = "keep"
    DELETE = "delete"
    TRANSLATE = "translate"          # params: dr:int, dc:int
    RECOLOR = "recolor"              # params: color:int (target color)
    COPY = "copy"                    # params: k:int, placements:list[(dr,dc)]
    SCALE = "scale"                  # params: factor:int (negative = shrink /|f|)
    REFLECT = "reflect"              # params: axis:str in AXES (+ optional dr,dc)
    ROTATE = "rotate"                # params: angle:int in ANGLES (+ optional dr,dc)
    MOVE_TO = "move_to"              # params: r0:int, c0:int (absolute bbox origin)
    MOVE_UNTIL_ADJACENT = "move_until_adjacent"  # params: direction:str, target ref
    CROP_TO = "crop_to"              # grid-level (shrink tasks): params: region bbox
    COMPOSITE = "composite"          # params: parts:list[serialized ObjectDelta]
    PAINT = "paint"                  # repaint cells from a same-mask source REF
                                     # (template stamping); params: none raw,
                                     # induced param: source (RefExpr)
    GROW = "grow"                    # output ⊇ input cells (round 2): params:
                                     # mode:str in growth.GROW_MODES + per-mode
                                     # color/direction/length/conn/pattern
    FILL_LINE = "fill_line"          # round 12: draw axis-aligned line
                                     # through object; params: axis
                                     # (DirectionExpr h/v/both), color
                                     # (ColorExpr), extent (to_border /
                                     # to_object / between_peers)
    SYNTH_COPY = "synth_copy"        # AUTONOMOUS M2 (round 7): a LEARNED
                                     # verb from learned_verbs.json — a
                                     # mined+retro-solve-validated chain of
                                     # combinators mapping a source object
                                     # onto an orphan; params {verb,
                                     # placement, color?}
    COPY_PART = "copy_part"          # M2 verb 2 (battery-validated, round 6):
                                     # a subwindow of a source object copied
                                     # elsewhere; raw params {window, placement};
                                     # induced: window RegionExpr-relative +
                                     # placement VecExpr + optional color
    CONNECT = "connect"              # M2 verb 1 (battery-validated, round 6):
                                     # a straight segment drawn between self
                                     # and a target object; raw params
                                     # {axis, color, other_output_id};
                                     # induced: target (RefExpr), color
    EXTRACT_PART = "extract_part"    # Round 15 (battery-validated, M2):
                                     # orphan == sub-region of the INPUT GRID
                                     # (exact or dihedral-transformed);
                                     # raw params {source_bbox, transform_k,
                                     # transform_flip, placement};
                                     # induced: source (RegionExpr relational
                                     # e.g. bbox(unique(PRED))), transform
                                     # (AxisExpr/AngleExpr), placement (VecExpr)


#: Legal symbolic axis / angle / direction constants used in delta params
#: and expression leaves.  Kept as strings so params stay JSON-native.
AXES: tuple[str, ...] = ("horizontal", "vertical", "diag_main", "diag_anti")
ANGLES: tuple[int, ...] = (90, 180, 270)
DIRECTIONS: tuple[str, ...] = ("up", "down", "left", "right")
#: Copy-placement bbox alignment modes (COPY 'targets' mode, Section 2.3):
#: place each copy so its bbox center / origin coincides with the target's.
ALIGNMENTS: tuple[str, ...] = ("bbox_center", "bbox_origin")


class ParameterClass(Enum):
    """Preference lattice for induced parameters, Requirement 2.4.1.

    Order (best -> worst): RELATIONAL > FEATURE > INDUCED_MAP > CONSTANT.
    ``worst()`` over a program's params is recorded in its certificate.
    """
    RELATIONAL = "relational"
    FEATURE = "feature"
    INDUCED_MAP = "induced_map"
    CONSTANT = "constant"

    @property
    def rank(self) -> int:
        """0 = best (relational) ... 3 = worst (constant)."""
        return ("relational", "feature", "induced_map", "constant").index(self.value)

    @staticmethod
    def worst(classes: "list[ParameterClass]") -> "ParameterClass":
        """The lowest-preference class among ``classes`` (CONSTANT if empty)."""
        if not classes:
            return ParameterClass.CONSTANT
        return max(classes, key=lambda c: c.rank)


class FailureStage(Enum):
    """Where induction gave up, Section 5.1 ``failure_stage``."""
    SEGMENTATION = "segmentation"
    MATCHING = "matching"
    SELECTOR = "selector"
    PARAMETER = "parameter"
    LOO = "loo"


class FeatureKind(Enum):
    """Runtime type of a registered feature's value (features.py registry)."""
    SCALAR = "scalar"        # int | float
    BOOL = "bool"
    COLOR = "color"          # int in 0..9
    VECTOR = "vector"        # tuple[int, int]  (dr, dc)
    CATEGORICAL = "categorical"  # hashable (e.g. shape-signature hash string)


class ExprType(Enum):
    """Static type of a parameter expression (Section 2.4 grammar)."""
    COLOR = "color"
    VECTOR = "vector"
    SCALAR = "scalar"
    REGION = "region"
    PREDICATE = "predicate"
    REF = "ref"              # object reference (self / nearest / container / ...)
    AXIS = "axis"
    ANGLE = "angle"
    DIRECTION = "direction"
    ALIGN = "align"          # copy-placement alignment mode (ALIGNMENTS)
    GROW_MODE = "grow_mode"  # growth mode symbol (growth.GROW_MODES)
    PATTERN = "pattern"      # constant added-cell pattern (GROW fallback)


#: Value type a feature function may return.
FeatureValue = Union[int, float, bool, str, tuple]


# ---------------------------------------------------------------------------
# Multicolor object extension (Section 2.1 S3/S4)
# ---------------------------------------------------------------------------

@dataclass
class MultiColorObject(ARCObject):
    """ARCObject extended with a per-cell color map for S3/S4 segmentation.

    ``color`` (inherited) holds the majority color; ``cell_colors`` maps every
    cell in ``cells`` to its actual color.  All downstream code must treat a
    plain ARCObject as the ``cell_colors is None`` degenerate case via
    ``cell_colors_of(obj)``.
    """
    cell_colors: dict[tuple[int, int], int] = field(default_factory=dict)

    @property
    def color_multiset(self) -> tuple[int, ...]:
        """Sorted tuple of the distinct colors present in the object."""
        return tuple(sorted(set(self.cell_colors.values()))) if self.cell_colors \
            else (self.color,)


def cell_colors_of(obj: ARCObject) -> dict[tuple[int, int], int]:
    """Per-cell colors of any object (uniform ``obj.color`` for plain objects)."""
    if isinstance(obj, MultiColorObject) and obj.cell_colors:
        return dict(obj.cell_colors)
    return {cell: obj.color for cell in obj.cells}


# ---------------------------------------------------------------------------
# Grid context (shared read-only environment for features & expressions)
# ---------------------------------------------------------------------------

@dataclass
class GridContext:
    """Everything a feature/expression may look at besides the object itself.

    Pure data; built once per (grid, segmentation) and shared by all feature
    computations so rank features (size_rank, is_unique_color, ...) see the
    full object set.
    """
    grid: Grid
    objects: list[ARCObject]
    background: int
    pair_index: int = 0
    role: str = "input"       # "input" | "output"
    variant: Optional[SegmentationVariant] = None


# ---------------------------------------------------------------------------
# Expression base (nodes defined in expressions.py; base lives here so
# SelectorRule/ActionRule can be typed without a circular import)
# ---------------------------------------------------------------------------

#: expr_class tag -> concrete Expr subclass; populated by expressions.py.
EXPR_CLASS_REGISTRY: dict[str, type] = {}


def register_expr_class(cls: type) -> type:
    """Class decorator: make an Expr subclass JSON-round-trippable by name."""
    EXPR_CLASS_REGISTRY[cls.__name__] = cls
    return cls


@dataclass(frozen=True)
class Expr:
    """A node in the parameter-expression grammar (Section 2.4).

    ``op``   — production name from the grammar (e.g. "color_of", "vector_to",
               "const", "nearest_object_of_color").
    ``args`` — children: a tuple of Expr nodes and/or JSON-native literals
               (int, str, tuple of ints).  Depth (max nesting of Expr args)
               must be <= 2 in Stage 1.

    Subclasses (ColorExpr, VecExpr, ScalarExpr, RegionExpr, PredExpr, RefExpr)
    fix ``rtype`` and enumerate their legal ``op`` values; see expressions.py.
    Frozen + hashable so expressions can key dedup sets during enumeration.
    """
    op: str
    args: tuple = ()

    #: Static type; overridden by each subclass.
    rtype: "ExprType" = None  # type: ignore[assignment]

    @property
    def depth(self) -> int:
        """1 + max depth of Expr children (leaves have depth 1)."""
        child = [a.depth for a in self.args if isinstance(a, Expr)]
        return 1 + (max(child) if child else 0)

    @property
    def size(self) -> int:
        """Total node count (MDL tiebreaker, Requirement 2.4.1)."""
        return 1 + sum(a.size for a in self.args if isinstance(a, Expr))

    def to_dict(self) -> dict:
        """JSON-able form: {"expr_class", "op", "args"} with nested exprs tagged."""
        def enc(a: Any) -> Any:
            if isinstance(a, Expr):
                return a.to_dict()
            if isinstance(a, tuple):
                return {"__tuple__": [enc(x) for x in a]}
            return a
        return {"expr_class": type(self).__name__, "op": self.op,
                "args": [enc(a) for a in self.args]}

    @staticmethod
    def from_dict(d: dict) -> "Expr":
        """Inverse of to_dict; requires expressions.py to be imported."""
        def dec(a: Any) -> Any:
            if isinstance(a, dict) and "expr_class" in a:
                return Expr.from_dict(a)
            if isinstance(a, dict) and "__tuple__" in a:
                return tuple(dec(x) for x in a["__tuple__"])
            return a
        cls = EXPR_CLASS_REGISTRY.get(d["expr_class"])
        if cls is None:  # ensure node classes are registered, then retry once
            import geocat_arc.object_reasoning.expressions  # noqa: F401
            cls = EXPR_CLASS_REGISTRY[d["expr_class"]]
        return cls(op=d["op"], args=tuple(dec(a) for a in d["args"]))


# ---------------------------------------------------------------------------
# Segmentation result (Section 2.1)
# ---------------------------------------------------------------------------

@dataclass
class SegmentationResult:
    """Per-task outcome of applying one segmentation variant to all train pairs.

    ``input_objects[i]`` / ``output_objects[i]`` are the object lists for
    train pair i.  ``coherence`` is the Requirement 2.1.1 score in [0, 1]
    (>= 0.8 pixel coverage + consistent object-count relation to be eligible);
    ``pixel_coverage`` is the raw covered-fraction over all pairs.
    """
    variant: SegmentationVariant
    input_objects: list[list[ARCObject]]
    output_objects: list[list[ARCObject]]
    backgrounds: list[int]                 # per-pair background color used
    coherence: float
    pixel_coverage: float
    object_counts: list[tuple[int, int]]   # per pair: (n_in, n_out)
    coherent: bool                          # passed the 2.1.1 eligibility test
    #: Round-4 granularity-consistency signal: total merges (one output
    #: object overlapping >1 input objects' cells) + splits (one input
    #: object's cells spread over >1 output objects) across all pairs.
    #: Pure function of the pair set (fold-invariant); 0 = the variant
    #: carves inputs and outputs at the same granularity.
    granularity_mismatch: int = 0
    #: Round-16 create-aware coherence: True when coherence was admitted
    #: via the orphan-output relaxation (ARC_CREATE_COHERENCE=1).  The
    #: preserved core (matched + copy/grow/connect-explained outputs)
    #: satisfies count-consistency, but unexplained orphan outputs exist.
    #: Relaxed variants rank AFTER strictly-coherent variants in the
    #: inducer's trial order (guard c: no ranking perturbation).
    #: Per-pair orphan count (fold-invariant: computed per pair, not
    #: aggregated across pairs in a fold-variable way).
    create_orphan_relaxed: bool = False
    #: Total orphan output objects across all pairs (for diagnostics).
    create_orphan_count: int = 0


# ---------------------------------------------------------------------------
# Feature table (Sections 2.2 / 3.3 step 1)
# ---------------------------------------------------------------------------

@dataclass
class ObjectFeatures:
    """One row of the feature table: all registered feature values of one object.

    ``intrinsic`` and ``relational`` are keyed by FEATURE_REGISTRY names
    (features.py).  Only registered, typed, pure functions may contribute
    (Requirement 2.2.1).
    """
    object_id: int
    pair_index: int
    role: str                               # "input" | "output"
    intrinsic: dict[str, FeatureValue] = field(default_factory=dict)
    relational: dict[str, FeatureValue] = field(default_factory=dict)

    def value(self, name: str) -> FeatureValue:
        """Lookup by feature name across both groups (KeyError if absent)."""
        if name in self.intrinsic:
            return self.intrinsic[name]
        return self.relational[name]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeatureTable:
    """Feature rows for all input objects across all train pairs, plus the
    per-(pair, object) delta label attached by the inducer (Section 3.3).

    ``labels[(pair_index, object_id)]`` is the ObjectDelta assigned by
    correspondence extraction; missing key = unlabeled (residual).
    """
    rows: list[ObjectFeatures] = field(default_factory=list)
    feature_names: list[str] = field(default_factory=list)
    labels: dict[tuple[int, int], "ObjectDelta"] = field(default_factory=dict)

    def rows_for_pair(self, pair_index: int) -> list[ObjectFeatures]:
        return [r for r in self.rows if r.pair_index == pair_index]


# ---------------------------------------------------------------------------
# Correspondence & deltas (Sections 3.1 / 3.2)
# ---------------------------------------------------------------------------

@dataclass
class ObjectDelta:
    """The minimal typed change one input object undergoes in one train pair.

    ``input_object_id`` is None for pure creations; ``output_object_ids`` is
    empty for DELETE, has one element for 1:1 deltas, k elements for COPY.
    ``params`` holds *raw observed* values (JSON-native: ints, strs, tuples
    encoded as lists), e.g. {"dr": 2, "dc": 0} — parameter *expressions* that
    explain these raw values across pairs live in ActionRule, not here.
    ``residual_pixels`` counts pixels the delta fails to account for (0 for a
    perfect account; used by the 3.2 pixel reconciliation cross-check).
    """
    pair_index: int
    delta_type: DeltaType
    input_object_id: Optional[int]
    output_object_ids: list[int] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    residual_pixels: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["delta_type"] = self.delta_type.value
        return d

    @staticmethod
    def from_dict(d: dict) -> "ObjectDelta":
        d = dict(d)
        d["delta_type"] = DeltaType(d["delta_type"])
        return ObjectDelta(**d)


@dataclass
class PairCorrespondence:
    """Object-level matching of one train pair (Section 3.1).

    ``matches`` are (input_object_id, output_object_id, similarity) under the
    hypothesis weighting used.  ``copies`` maps an input id to ALL its output
    ids when one input shape appears k>1 times (its primary match, if any,
    also appears in ``matches``).  ``deleted_input_ids`` and
    ``created_output_ids`` are the unmatched leftovers.  ``weights_profile``
    names the similarity re-weighting hypothesis (e.g. "default", "motion",
    "recolor") so ambiguous alternatives are distinguishable downstream.
    ``unreconciled_pixels`` is the pixel-diff residue after the 3.2
    change-detection cross-check; ``is_object_preserving`` is False when that
    residue exceeds tolerance (triggers the next segmentation variant).
    """
    pair_index: int
    input_objects: list[ARCObject]
    output_objects: list[ARCObject]
    matches: list[tuple[int, int, float]] = field(default_factory=list)
    copies: dict[int, list[int]] = field(default_factory=dict)
    deleted_input_ids: list[int] = field(default_factory=list)
    created_output_ids: list[int] = field(default_factory=list)
    weights_profile: str = "default"
    unreconciled_pixels: int = 0
    is_object_preserving: bool = True
    #: (height, width) of the OUTPUT grid — the frame growth modes (GROW
    #: halo/ray, round 2) bound their added cells to; (0, 0) = unknown.
    grid_shape: tuple[int, int] = (0, 0)
    #: Round 20: the INPUT grid as a tuple of tuples of ints.  The grid-aware
    #: GROW modes (cross_center / cavity_leak / ray_deflect, ARC_RAY_EXT) read
    #: obstacles and the background off the scene; every mode before round 20
    #: is a pure function of (cells, bounds) and ignores this.  None = no
    #: scene available, and those modes are then undefined (the zero-cost
    #: path).  Set by match_pair, so it is re-derived per fold like
    #: everything else on the correspondence.
    input_grid_rows: Optional[tuple] = None


# ---------------------------------------------------------------------------
# Rules & programs (Sections 3.3 / 4)
# ---------------------------------------------------------------------------

@dataclass
class SelectorRule:
    """WHICH objects receive an action: a predicate over registered features.

    ``predicate`` is a PredExpr (expressions.py) of depth <= 2 — a single
    feature test or a conjunction of two.  ``literals`` is its literal count
    (certificate field ``selector_literals``); "all objects" is the trivial
    predicate with 0 literals.  Zero-conflict semantics: across every train
    pair the predicate must select exactly the objects labeled with the
    rule's delta type (Section 3.3 step 2).
    """
    predicate: Expr
    literals: int

    def to_dict(self) -> dict:
        return {"predicate": self.predicate.to_dict(), "literals": self.literals}

    @staticmethod
    def from_dict(d: dict) -> "SelectorRule":
        return SelectorRule(predicate=Expr.from_dict(d["predicate"]),
                            literals=int(d["literals"]))


@dataclass
class ActionRule:
    """WHAT happens to selected objects: a delta type + parameter expressions.

    ``params`` maps the delta type's parameter names (see DeltaType comments)
    to Expr nodes evaluated per object at apply time; e.g. TRANSLATE has a
    single "vector" VecExpr, RECOLOR a "color" ColorExpr, COPY a "k"
    ScalarExpr + "placement" VecExpr, CROP_TO a "region" RegionExpr.
    ``parameter_class`` is the worst ParameterClass over ``params``
    (Requirement 2.4.1).
    """
    delta_type: DeltaType
    params: dict[str, Expr] = field(default_factory=dict)
    parameter_class: ParameterClass = ParameterClass.CONSTANT

    def to_dict(self) -> dict:
        return {"delta_type": self.delta_type.value,
                "params": {k: v.to_dict() for k, v in self.params.items()},
                "parameter_class": self.parameter_class.value}

    @staticmethod
    def from_dict(d: dict) -> "ActionRule":
        return ActionRule(
            delta_type=DeltaType(d["delta_type"]),
            params={k: Expr.from_dict(v) for k, v in d["params"].items()},
            parameter_class=ParameterClass(d["parameter_class"]),
        )


@dataclass
class ObjectRule:
    """One (selector -> action) pair; rules apply in list order over the
    canvas, each object receiving the FIRST rule whose selector matches."""
    selector: SelectorRule
    action: ActionRule

    def to_dict(self) -> dict:
        return {"selector": self.selector.to_dict(), "action": self.action.to_dict()}

    @staticmethod
    def from_dict(d: dict) -> "ObjectRule":
        return ObjectRule(selector=SelectorRule.from_dict(d["selector"]),
                          action=ActionRule.from_dict(d["action"]))


@dataclass
class OutputSpec:
    """How the output grid is materialized after object actions.

    mode:
      - "same_as_input": output shape = input shape (motion/recolor tasks).
      - "crop": output = subgrid at ``region`` (RegionExpr) — shrink tasks;
        object rules may be empty in this mode.
      - "constant_shape": fixed (height, width) learned from train pairs,
        painted from the object canvas (with optional ``fill`` ColorExpr for
        shrink_const_out ColorExpr-valued outputs, Section 3.6).
    ``background`` is a ColorExpr (usually const or most_common_color).
    """
    mode: str = "same_as_input"
    region: Optional[Expr] = None
    height: Optional[int] = None
    width: Optional[int] = None
    background: Optional[Expr] = None
    fill: Optional[Expr] = None

    def to_dict(self) -> dict:
        return {"mode": self.mode,
                "region": self.region.to_dict() if self.region else None,
                "height": self.height, "width": self.width,
                "background": self.background.to_dict() if self.background else None,
                "fill": self.fill.to_dict() if self.fill else None}

    @staticmethod
    def from_dict(d: dict) -> "OutputSpec":
        opt = lambda v: Expr.from_dict(v) if v else None  # noqa: E731
        return OutputSpec(mode=d["mode"], region=opt(d.get("region")),
                          height=d.get("height"), width=d.get("width"),
                          background=opt(d.get("background")), fill=opt(d.get("fill")))


@dataclass
class ObjectProgram:
    """A complete induced task program (Requirement 4.1/4.2 canonical shape):

        Segment(variant) -> [Select(selector) -> Action(params)]* -> Render(spec)

    Fully serializable: to_dict()/to_json() emit registry names + arguments
    only — sufficient to reconstruct execution via the registries; no
    closures.  ``default_action`` handles unselected objects (KEEP or DELETE,
    induced like any rule).  ``library_operators_used`` lists names of
    memory.py library operators whose fragments were instantiated.
    Execution: actions.render_program(program, grid) is the only execution
    path (Requirement 4.4); to_dsl_program() lowers to a type-checked
    categorical_dsl Program for artifact parity (Requirement 4.3).
    """
    segmentation_variant: SegmentationVariant
    rules: list[ObjectRule] = field(default_factory=list)
    default_action: ActionRule = field(
        default_factory=lambda: ActionRule(delta_type=DeltaType.KEEP))
    output_spec: OutputSpec = field(default_factory=OutputSpec)
    library_operators_used: list[str] = field(default_factory=list)

    # -- derived metrics (certificate fields) --
    @property
    def program_depth(self) -> int:
        """Segment + one step per rule + default + render."""
        return 3 + len(self.rules)

    @property
    def expression_size(self) -> int:
        """Total Expr node count over all selectors, params, and output spec."""
        n = 0
        for r in self.rules:
            n += r.selector.predicate.size
            n += sum(e.size for e in r.action.params.values())
        n += sum(e.size for e in self.default_action.params.values())
        for e in (self.output_spec.region, self.output_spec.background,
                  self.output_spec.fill):
            n += e.size if e is not None else 0
        return n

    @property
    def worst_parameter_class(self) -> ParameterClass:
        """Worst class over all PARAMETERIZED actions (a parameterless KEEP/
        DELETE contributes nothing) AND the output-spec expressions
        (region/background/fill) — a constant-shape program whose only
        learned content is a constant fill must report CONSTANT, both for
        certificate honesty (Section 5.5) and because the single-train-pair
        acceptance gate (Section 3.4) requires a non-constant class.
        RELATIONAL if the program carries no parameter expressions at all
        (its induced content is then entirely in the selectors)."""
        # lazy import: expressions.py imports this module at load time
        from geocat_arc.object_reasoning.expressions import parameter_class_of
        classes = [r.action.parameter_class for r in self.rules if r.action.params]
        if self.default_action.params:
            classes.append(self.default_action.parameter_class)
        for expr in (self.output_spec.region, self.output_spec.background,
                     self.output_spec.fill):
            if expr is not None:
                classes.append(parameter_class_of(expr))
        if not classes:
            return ParameterClass.RELATIONAL
        return ParameterClass.worst(classes)

    def to_dict(self) -> dict:
        return {"segmentation_variant": self.segmentation_variant.value,
                "rules": [r.to_dict() for r in self.rules],
                "default_action": self.default_action.to_dict(),
                "output_spec": self.output_spec.to_dict(),
                "library_operators_used": list(self.library_operators_used)}

    @staticmethod
    def from_dict(d: dict) -> "ObjectProgram":
        return ObjectProgram(
            segmentation_variant=SegmentationVariant(d["segmentation_variant"]),
            rules=[ObjectRule.from_dict(r) for r in d["rules"]],
            default_action=ActionRule.from_dict(d["default_action"]),
            output_spec=OutputSpec.from_dict(d["output_spec"]),
            library_operators_used=list(d.get("library_operators_used", [])),
        )

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_json(s: str) -> "ObjectProgram":
        import json
        return ObjectProgram.from_dict(json.loads(s))

    def to_dsl_program(self):
        """Lower to a categorical_dsl.program.Program of typed Morphisms
        (Requirement 4.3).  Implemented by the actions team; must type-check
        under type_checker.check_composition.

        Returns:
            geocat_arc.categorical_dsl.program.Program
        """
        raise NotImplementedError("actions team: lower ObjectProgram to DSL Program")


@dataclass
class ComposedProgram:
    """Stage-2 typed composition (STAGE2_REQUIREMENTS Section 2.1): an
    ordered chain of ObjectProgram stages; stage k+1 re-segments stage k's
    rendered output grid.  Depth 1 is represented by a bare ObjectProgram
    (so every Stage-1 artifact stays byte-identical); this class only ever
    carries >= 2 stages.  ``stage_provenance`` records per stage which
    residual induced it (Section 2.1.3).

    The mining/ranking surface intentionally mirrors ObjectProgram:
    ``rules`` concatenates stage rules in execution order (a stage IS an
    ObjectProgram, so memory._fragments_with_slots applies unchanged) and
    the derived metrics sum over stages.
    """
    stages: list[ObjectProgram]
    stage_provenance: list[dict] = field(default_factory=list)
    # each: {"residual_before_px": int, "residual_after_px": int,
    #        "library_operators_used": [...]}

    @property
    def composition_depth(self) -> int:
        return len(self.stages)

    @property
    def program_depth(self) -> int:
        return sum(s.program_depth for s in self.stages)

    @property
    def expression_size(self) -> int:
        return sum(s.expression_size for s in self.stages)

    @property
    def rules(self) -> list[ObjectRule]:
        return [r for s in self.stages for r in s.rules]

    @property
    def segmentation_variant(self) -> SegmentationVariant:
        return self.stages[0].segmentation_variant

    @property
    def library_operators_used(self) -> list[str]:
        seen: list[str] = []
        for s in self.stages:
            for name in s.library_operators_used:
                if name not in seen:
                    seen.append(name)
        return seen

    @property
    def worst_parameter_class(self) -> ParameterClass:
        return ParameterClass.worst(
            [s.worst_parameter_class for s in self.stages])

    def to_dict(self) -> dict:
        return {"program_class": "composed",
                "stages": [s.to_dict() for s in self.stages],
                "stage_provenance": list(self.stage_provenance)}

    @staticmethod
    def from_dict(d: dict) -> "ComposedProgram":
        return ComposedProgram(
            stages=[ObjectProgram.from_dict(s) for s in d["stages"]],
            stage_provenance=list(d.get("stage_provenance", [])))

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_json(s: str) -> "ComposedProgram":
        import json
        return ComposedProgram.from_dict(json.loads(s))


@dataclass
class ReductionProgram:
    """Round-10 grid-synthesis family (the eval framing census: 26/84
    uncovered eval tasks synthesize a small output from panel structure —
    neither subgrid nor downscale).  A reduction program is NOT
    object-preserving: it splits the input into equal panels and computes
    the output grid from them.

        Split(split_spec) -> Combine(mode, params)

    split_spec: {"kind": "separator"|"equal", "color": int|None,
                 "axis": "h"|"v"|"grid", "panels": int}
    mode "cellwise": params["table"] maps a per-cell key — the tuple of
        panel-cell background flags, e.g. "(False, True)" — to either a
        literal output color (train-bound, priced per entry) or the
        pass-through sentinel "@panel<i>" (closed vocabulary, unbound).
    mode "select_panel": params["criterion"] in a CLOSED vocabulary
        (unique_pattern, majority_pattern, most_nonbg, least_nonbg,
        most_colors, least_colors) — pure structural choice, no bound
        values (RELATIONAL).

    Induced per task by reduction.induce_reduction_candidates, ranked in
    the same canonical pool as object programs, accepted only through the
    same LOO-by-reinduction gate.  Serialization follows the
    program_class-tag convention ("reduction")."""
    split: dict
    mode: str
    params: dict = field(default_factory=dict)

    # -- ranking / certificate surface (mirrors ObjectProgram) --
    rules: list = field(default_factory=list, init=False, repr=False)
    segmentation_variant = None          # reduction does not segment
    library_operators_used: list = field(default_factory=list, init=False,
                                         repr=False)

    @property
    def program_depth(self) -> int:
        return 2                          # split + combine

    @property
    def expression_size(self) -> int:
        if self.mode in ("cellwise", "cellwise_color"):
            return 1 + len(self.params.get("table", {}))
        return 2                          # split + criterion/overlay symbol

    @property
    def value_bound_count(self) -> int:
        """Literal color table entries are train-bound; @panel<i>
        pass-throughs, criterion symbols, and overlay modes are
        closed-vocabulary."""
        if self.mode in ("cellwise", "cellwise_color"):
            return sum(1 for v in self.params.get("table", {}).values()
                       if not (isinstance(v, str) and v.startswith("@panel")))
        return 0

    @property
    def worst_parameter_class(self) -> ParameterClass:
        if self.mode in ("cellwise", "cellwise_color"):
            if self.value_bound_count:
                return ParameterClass.INDUCED_MAP
            return ParameterClass.FEATURE
        return ParameterClass.RELATIONAL

    def to_dict(self) -> dict:
        return {"program_class": "reduction", "split": dict(self.split),
                "mode": self.mode, "params": dict(self.params)}

    @staticmethod
    def from_dict(d: dict) -> "ReductionProgram":
        return ReductionProgram(split=dict(d["split"]), mode=d["mode"],
                                params=dict(d.get("params", {})))

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class FramedProgram:
    """Round-13 dihedral-frame wrapper (docs/EXTERNAL_IDEAS_2026_07.md
    idea 1): an inner program certified in a dihedral reframing of the
    task.  frame = (k, flip): the transform T applied to every grid is
    fliplr-then-rot90^k; execution is T_inv(inner(T(input))).  The inner
    certificate transfers losslessly because T is a bijection on grids.
    All ranking/certificate surfaces delegate to the inner program."""
    frame: tuple
    inner: "AnyProgram"

    @property
    def rules(self):
        return self.inner.rules

    @property
    def segmentation_variant(self):
        return self.inner.segmentation_variant

    @property
    def library_operators_used(self):
        return self.inner.library_operators_used

    @property
    def program_depth(self) -> int:
        return self.inner.program_depth + 1     # + the frame transform

    @property
    def expression_size(self) -> int:
        return self.inner.expression_size + 1

    @property
    def worst_parameter_class(self):
        return self.inner.worst_parameter_class

    def to_dict(self) -> dict:
        return {"program_class": "framed",
                "frame": [int(self.frame[0]), bool(self.frame[1])],
                "inner": self.inner.to_dict()}

    @staticmethod
    def from_dict(d: dict) -> "FramedProgram":
        return FramedProgram(frame=(int(d["frame"][0]), bool(d["frame"][1])),
                             inner=program_from_dict(d["inner"]))

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class OverlayProgram:
    """Round-14 structured composition (queue #3): base program + an
    overwrite-only patch induced on CLEAN residual targets.

        render(x) = base(x), then every NON-BACKGROUND cell of patch(x)
                    overwrites the base render.

    The patch is induced on (original_input, residual_target) pairs where
    residual_target keeps the target only at cells the base got wrong
    (background elsewhere) — a sparse, clean second-stage signal instead
    of re-segmenting the noisy base render.  Only overwrite-fixable
    residuals qualify (every wrong cell has a non-background target).
    Both stages re-induce per LOO fold; the gate is unchanged."""
    base: "AnyProgram"
    patch: "AnyProgram"

    @property
    def rules(self):
        return list(self.base.rules) + list(self.patch.rules)

    @property
    def segmentation_variant(self):
        return self.base.segmentation_variant

    @property
    def library_operators_used(self):
        seen = []
        for s in (self.base, self.patch):
            for name in s.library_operators_used:
                if name not in seen:
                    seen.append(name)
        return seen

    @property
    def program_depth(self) -> int:
        return self.base.program_depth + self.patch.program_depth

    @property
    def expression_size(self) -> int:
        return self.base.expression_size + self.patch.expression_size

    @property
    def worst_parameter_class(self):
        return ParameterClass.worst([self.base.worst_parameter_class,
                                     self.patch.worst_parameter_class])

    @property
    def value_bound_count(self) -> int:
        # lazy import: inducer imports this module at load time
        from geocat_arc.object_reasoning.inducer import (
            _program_value_bound_count)
        return (_program_value_bound_count(self.base)
                + _program_value_bound_count(self.patch))

    def to_dict(self) -> dict:
        return {"program_class": "overlay",
                "base": self.base.to_dict(),
                "patch": self.patch.to_dict()}

    @staticmethod
    def from_dict(d: dict) -> "OverlayProgram":
        return OverlayProgram(base=program_from_dict(d["base"]),
                              patch=program_from_dict(d["patch"]))

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Round-17 generative-composite program (ARC_GENERATIVE)
# ---------------------------------------------------------------------------

@dataclass
class GenerativeProgram:
    """Round-17 generative-composite path: bypasses object-to-object
    correspondence entirely.  Each input object emits a GENERATOR (from the
    GROW vocabulary — ray/halo/fill_interior/mirror_edge/symmetry_complete),
    and all generators render onto ONE canvas; the composite must pixel-match
    the output on every train pair.

    Fields:
        seg_variant : segmentation variant used for INPUT segmentation.
        generators  : list of (selector_dict, generator_rule) pairs.
                      selector_dict selects which input objects this
                      generator applies to (empty dict = all objects).
                      generator_rule = {"kind": str, ...params} where kind
                      is one of the growth vocabulary modes.
        canvas_policy : "over_input" (paint generators on a COPY of the
                        input grid) or "blank" (paint on bg-filled canvas).
        background  : background color for blank-canvas policy.
    """
    seg_variant: SegmentationVariant
    generators: list[tuple[dict, dict]]
    canvas_policy: str = "over_input"    # "over_input" | "blank"
    background: int = 0
    delete_source: bool = False          # blank emitting objects' cells
    intersection_color: Optional[int] = None  # R17b: color for cells painted
                                               # by generators from DIFFERENT
                                               # source-object colors

    # -- ranking / certificate surface (mirrors ReductionProgram) --
    rules: list = field(default_factory=list, init=False, repr=False)
    segmentation_variant_prop = None     # use seg_variant directly
    library_operators_used: list = field(default_factory=list, init=False,
                                         repr=False)

    @property
    def segmentation_variant(self):
        return self.seg_variant

    @property
    def program_depth(self) -> int:
        return 1 + len(self.generators)

    @property
    def expression_size(self) -> int:
        # 1 for the seg choice + 1 per generator
        return 1 + len(self.generators)

    @property
    def value_bound_count(self) -> int:
        """Count train-bound literals in generator params.  Direction
        symbols, mode names, and relational direction params
        (direction_mode, target_pred) are closed vocabulary (not bound).
        For ray_relational, only "color" is potentially bound."""
        n = 0
        for _sel, rule in self.generators:
            kind = rule.get("kind", "")
            if kind == "ray_relational":
                # Only "color" is bound when explicitly set and differs
                # from source (which we can't check here, so count it).
                if "color" in rule and isinstance(rule["color"], int):
                    n += 1
            else:
                # "color" param when it's a literal integer is train-bound
                if "color" in rule and isinstance(rule["color"], int):
                    n += 1
                # "length" param when present is train-bound
                if "length" in rule and isinstance(rule["length"], int):
                    n += 1
        if self.canvas_policy == "blank" and self.background != 0:
            n += 1
        if self.intersection_color is not None:
            n += 1
        return n

    @property
    def worst_parameter_class(self) -> ParameterClass:
        if self.value_bound_count == 0:
            # ray_relational with no bound color is RELATIONAL
            return ParameterClass.RELATIONAL
        return ParameterClass.INDUCED_MAP

    def to_dict(self) -> dict:
        d = {
            "program_class": "generative",
            "seg_variant": self.seg_variant.value,
            "generators": [
                {"selector": sel, "rule": dict(rule)}
                for sel, rule in self.generators
            ],
            "canvas_policy": self.canvas_policy,
            "background": self.background,
        }
        if self.delete_source:
            d["delete_source"] = True
        if self.intersection_color is not None:
            d["intersection_color"] = self.intersection_color
        return d

    @staticmethod
    def from_dict(d: dict) -> "GenerativeProgram":
        sv = SegmentationVariant(d["seg_variant"])
        gens = [
            (dict(g["selector"]), dict(g["rule"]))
            for g in d["generators"]
        ]
        ic_raw = d.get("intersection_color")
        ic = int(ic_raw) if ic_raw is not None else None
        return GenerativeProgram(
            seg_variant=sv,
            generators=gens,
            canvas_policy=d.get("canvas_policy", "over_input"),
            background=int(d.get("background", 0)),
            delete_source=bool(d.get("delete_source", False)),
            intersection_color=ic,
        )

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)


#: Any executable induced program (Stage-1 flat, Stage-2 composed,
#: round-10 reduction, round-13 framed, round-14 overlay, or
#: round-17 generative).
AnyProgram = (ObjectProgram | ComposedProgram | ReductionProgram
              | FramedProgram | OverlayProgram | GenerativeProgram)


def program_from_dict(d: dict) -> AnyProgram:
    """Deserialization dispatcher (Section 2.1.1): the ``program_class`` tag
    selects ComposedProgram / ReductionProgram / FramedProgram; its absence
    means a Stage-1 flat ObjectProgram, keeping every artifact loadable."""
    if d.get("program_class") == "composed":
        return ComposedProgram.from_dict(d)
    if d.get("program_class") == "reduction":
        return ReductionProgram.from_dict(d)
    if d.get("program_class") == "framed":
        return FramedProgram.from_dict(d)
    if d.get("program_class") == "overlay":
        return OverlayProgram.from_dict(d)
    if d.get("program_class") == "generative":
        return GenerativeProgram.from_dict(d)
    if d.get("program_class") == "computed_pattern":
        from .meta_induction import ComputedPatternProgram
        return ComputedPatternProgram.from_dict(d)
    if d.get("program_class") == "erase_patch":
        from .graduation import ErasePatchProgram
        return ErasePatchProgram.from_dict(d)
    return ObjectProgram.from_dict(d)


# ---------------------------------------------------------------------------
# Induction outcome, near-solve memory, certificates (Sections 3-5)
# ---------------------------------------------------------------------------

@dataclass
class LOOReport:
    """Result of LOO-by-reinduction (Section 3.4). Blocking gate: accepted
    programs require ``passed == folds`` AND perfect full-train fit.

    ``divergence`` (Section 5.1 extension, lever-4 instrumentation): one
    entry per FAILED fold with the reinduced fold program and the cell-level
    mismatch on the held-out pair — the raw material for cross-task
    parameter-expression mining.  Entries are plain JSON-able dicts:
    {fold, fold_program: dict|None, cells_wrong: int|None,
     shape_mismatch: bool, pred_shape: [h,w]|None, expected_shape: [h,w]}."""
    folds: int
    passed: int
    failed_pair_indices: list[int] = field(default_factory=list)
    divergence: list[dict] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.passed / self.folds if self.folds else 0.0

    @property
    def all_passed(self) -> bool:
        return self.folds > 0 and self.passed == self.folds


@dataclass
class InductionResult:
    """Everything induce_program() learned about one task.

    ``accepted`` iff ``program`` is train-perfect and LOO-perfect (the only
    acceptance path).  When not accepted but train_fit_objects >= 0.5 with a
    zero-conflict explained part, ``near_solve`` carries the NearSolveRecord
    to store (Section 5.1).  ``hypotheses_enumerated`` / ``induction_time_s``
    feed the certificate.
    """
    task_id: str
    accepted: bool
    program: Optional[ObjectProgram] = None
    train_fit_objects: float = 0.0
    train_fit_pixels: float = 0.0
    loo: Optional[LOOReport] = None
    failure_stage: Optional[FailureStage] = None
    near_solve: Optional["NearSolveRecord"] = None
    segmentation: Optional[SegmentationResult] = None
    hypotheses_enumerated: int = 0
    induction_time_s: float = 0.0
    events: list[str] = field(default_factory=list)  # event-type vocabulary, Req 1.1


@dataclass
class NearSolveRecord:
    """Section 5.1 schema, verbatim fields. Stored append-only by
    memory.NearSolveStore whenever best train_fit_objects >= 0.5 without
    acceptance.  ``program_partial`` is an ALREADY-SERIALIZED ObjectProgram
    dict (keeps this record trivially JSON-able)."""
    task_id: str
    timestamp: str
    segmentation_variant: str                       # SegmentationVariant.value
    program_partial: Optional[dict]
    train_fit_pixels: float
    train_fit_objects: float
    explained_rules: list[dict] = field(default_factory=list)
    # each: {selector_expr: dict, action: str, param_exprs: dict, n_objects_explained: int}
    residual: dict = field(default_factory=dict)
    # {unexplained_deltas: [{delta_type, count, example_features}],
    #  conflict_report: {selector_conflicts: int, parameter_conflicts: int},
    #  loo_failures: [pair_idx]}
    delta_histogram: dict[str, int] = field(default_factory=dict)
    failure_stage: str = FailureStage.SELECTOR.value

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "NearSolveRecord":
        return NearSolveRecord(**d)


@dataclass
class ProgramCertificate:
    """Section 5.5 schema: bounded record of evidence per accepted program.
    Written to outputs/<run>/certificates/<task_id>.json.  Invariant asserted
    by acceptance test A5: loo_folds == n_train_pairs."""
    task_id: str
    program: dict                                    # full ObjectProgram.to_dict()
    segmentation_variant: str
    train_fit: float                                 # must be 1.0
    loo_score: float                                 # must be 1.0
    loo_folds: int
    parameter_class: str                             # worst, ParameterClass.value
    selector_literals: int
    program_depth: int
    expression_size: int
    composition_depth: int = 1                       # Stage 2 (Section 2.1.2)
    library_operators_used: list[str] = field(default_factory=list)
    invented_from_cluster: Optional[str] = None
    hypotheses_enumerated: int = 0
    induction_time_s: float = 0.0
    harness_commit: str = ""
    run_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "ProgramCertificate":
        return ProgramCertificate(**d)


@dataclass
class LibraryOperator:
    """A promoted reusable fragment (Section 5.3): a typed sub-program schema
    with free slots, never a lookup table.  ``fragment`` is a serialized
    ObjectRule dict in which free slots are Expr leaves with
    op == "free_slot" and args == (slot_name, expr_type_value); per-task
    induction re-binds every slot and the result passes the normal LOO gate.
    """
    name: str                                        # e.g. op_move_until_adjacent_by_color
    fragment: dict
    free_slots: list[tuple[str, str]]                # (slot_name, ExprType.value)
    provenance: list[str] = field(default_factory=list)   # task_ids
    created_at: str = ""
    loo_record: dict = field(default_factory=dict)
    falsification_record: dict = field(default_factory=dict)
    # Independent-transfer annotation (lockbox protocol): status is
    # "independent-transfer" only when the operator solved a task outside
    # its provenance; "provisional" otherwise. Never gates registration.
    transfer_record: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "LibraryOperator":
        d = dict(d)
        d["free_slots"] = [tuple(s) for s in d.get("free_slots", [])]
        return LibraryOperator(**d)


# ---------------------------------------------------------------------------
# Shared type aliases (engine boundary)
# ---------------------------------------------------------------------------

#: Train pairs as the harness supplies them (ReasoningEngine.solve contract).
ArrayPair = tuple[np.ndarray, np.ndarray]
#: Train pairs in perception form (internal to this package).
GridPair = tuple[Grid, Grid]
#: An inducer callable, as consumed by inducer.loo_validate.
InducerFn = Callable[[list[GridPair]], InductionResult]


def to_grid_pairs(train_pairs: list[ArrayPair]) -> list[GridPair]:
    """Boundary glue: numpy pairs (harness) -> Grid pairs (internal)."""
    return [(Grid(np.asarray(i)), Grid(np.asarray(o))) for i, o in train_pairs]
