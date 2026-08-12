"""Origin-class mapping: is a solve INDUCED from the task's train pairs, a
FIXED_TRANSFORM (hardcoded primitive that fired), or COMPOSED (chain of
mechanisms)?  The induced-fraction is a first-class metric going forward.

Definitions
-----------
  induced         — the solving program was LEARNED from this task's train
                    pairs: rule induction (GeoCat rule:*), local-rule CA
                    lookup tables (solver_local_rule / meta_solver_local_rule*),
                    meta discover_* / meta_auto_* learned rules, learned
                    color/context maps, structural_inference verified-fit,
                    adaptive-reasoner reasoned_* rules.
  fixed_transform — a hardcoded primitive fired (reflection, rotation, tile,
                    crop, gravity, fill, scale, separator decompose, ...);
                    parameters may be fit (e.g. fill color) but the program
                    shape is a library primitive.
  composed        — the solution chains multiple mechanisms (X_then_Y,
                    residual_*, rule+correction, rule+rule2, cortical
                    voting/binding of several candidates).

Everything is data (dicts / pattern lists) so new layers, families and
strategies are added by extending the tables, not by editing logic.
Unmapped names classify as "fixed_transform" and are surfaced in the
results under ``unmapped_origin_names`` so gaps are visible, not silent.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

INDUCED = "induced"
FIXED = "fixed_transform"
COMPOSED = "composed"

# ---------------------------------------------------------------------------
# Layer-level defaults (pipeline).  A layer listed here classifies every
# family it emits UNLESS a family rule below overrides it.
# ---------------------------------------------------------------------------
PIPELINE_LAYER_CLASS: Dict[str, str] = {
    "loo_cortical_vote": COMPOSED,     # multi-candidate voting
    "loo_cortical_bind": COMPOSED,     # feature binding across candidates
    "loo_cortical_structural": COMPOSED,  # correction stacked on a candidate
}

# ---------------------------------------------------------------------------
# Family rules (pipeline).  First match wins:
#   1. exact-match table
#   2. composition markers (substring)
#   3. prefix table
#   4. exact fixed-primitive table
#   5. default FIXED (+ reported as unmapped)
# ---------------------------------------------------------------------------
PIPELINE_FAMILY_EXACT: Dict[str, str] = {
    "solver_local_rule": INDUCED,        # CA lookup table induced from train
    "solver_color_solver": INDUCED,      # per-context color rules induced
    "color_map": INDUCED,                # color->color lookup learned from train
    "object_recolor": INDUCED,           # object-property -> color rule
    "meta_neighbor_rule": INDUCED,
    "meta_row_col_rule": INDUCED,
    "meta_symmetry_completion": FIXED,   # symmetry-completion primitive
    "reasoned_composition": COMPOSED,
    # --- adaptive_reasoner families (audited src/reasoning_project/
    #     adaptive_reasoner.py 2026-07-02): the "reasoned_" prefix covers BOTH
    #     induced context rules and hardcoded global transforms; the fixed
    #     ones are enumerated here so they never inflate the induced count.
    "reasoned_enclosed_fill": FIXED,     # hardcoded flood-fill-enclosed, fitted color
    "reasoned_object_filter": INDUCED,   # property->keep/remove rule searched from train
    "reasoned_object_recolor": INDUCED,  # property->color rule searched from train
    # --- hypothesis_engine families (audited src/reasoning_project/
    #     hypothesis_engine.py 2026-07-02).  Fixed primitives (program shape
    #     hardcoded, at most parameters fitted):
    "hypothesis_symmetry_completion": FIXED,
    "hypothesis_symmetry_force": FIXED,
    "hypothesis_neighbor_fill": FIXED,       # majority-neighbor fill, fixed algorithm
    "hypothesis_row_col_fill": FIXED,
    "hypothesis_overlay": FIXED,
    "hypothesis_cross_intersection": FIXED,
    "hypothesis_quadrant_op": FIXED,
    "hypothesis_separator_copy": FIXED,
    "hypothesis_largest_as_template": FIXED,
    "hypothesis_flood_fill_enclosed_by_color": FIXED,
    "hypothesis_object_count_output": FIXED,
    # Genuinely induced hypothesis types (rule/mapping learned from train):
    "hypothesis_property_to_color": INDUCED,
    "hypothesis_learned_pixel_rule": INDUCED,
    "hypothesis_color_correspondence": INDUCED,  # learned color lookup table
    "hypothesis_conditional_recolor": INDUCED,   # learned property->color rule
    "hypothesis_conditional_filter": INDUCED,
    "hypothesis_conditional_movement": INDUCED,
}

# substring markers meaning "chained mechanisms"
PIPELINE_COMPOSED_MARKERS: Tuple[str, ...] = ("_then_", "residual_", "+")

PIPELINE_FAMILY_PREFIX: List[Tuple[str, str]] = [
    ("meta_solver_local_rule", INDUCED),   # induced CA table via meta layer
    ("meta_color", INDUCED),               # induced color rules via meta layer
    ("meta_auto_", INDUCED),               # auto-discovered relational rules
    ("meta_discover", INDUCED),            # meta discover_* learned rules
    # FIXED overrides must precede the broad "reasoned_" prefix:
    ("reasoned_symmetry_", FIXED),         # hardcoded h/v/hv symmetry completion
    ("reasoned_fill_", FIXED),             # hardcoded unique row/col fill
    ("reasoned_", INDUCED),                # context->value rules induced from train
    # NOTE: no blanket ("hypothesis_", INDUCED) — the hypothesis engine mixes
    # fixed primitives and induced rules; all known types are enumerated in
    # PIPELINE_FAMILY_EXACT above, unknown ones fall through to unmapped FIXED.
    # meta_engine_<engine>_<family> wraps another layer's family; the wrapped
    # family decides (handled in code by stripping the prefix), these are
    # fallbacks when stripping fails:
    ("meta_engine_", FIXED),
    ("meta_solver_", FIXED),               # e.g. meta_solver_crop_extract
    ("solver_", FIXED),                    # e.g. solver_crop_extract / separator
    ("fill_", FIXED),
]

PIPELINE_FIXED_EXACT: Set[str] = {
    "reflection", "rotation", "transpose", "translation", "tile",
    "upscale", "downscale", "gravity", "border_fill", "flood_fill_enclosed",
    "crop_to_content", "subgrid_extract", "shape_construct", "shape_tile",
    "shape_scale", "shape_rearrange", "shape_crop", "shape_separator",
    "identity",
}

# Known engine names that appear inside meta_engine_<engine>_<family>
_META_ENGINE_NAMES: Tuple[str, ...] = (
    "adaptive_synthesizer", "adaptive_reasoner", "hypothesis_engine",
    "composable_reasoner", "object_correspondence", "spatial_reasoner",
    "meta_learner", "fill_solver", "relation_solver", "reasoning_v2",
    "meta_reasoning", "different_shape", "output_shape_predictor",
    "grid_decomposition", "inverse_reasoning",
)

# ---------------------------------------------------------------------------
# GeoCat strategy rules.  First match wins.
# ---------------------------------------------------------------------------
GEOCAT_STRATEGY_EXACT: Dict[str, str] = {}
GEOCAT_COMPOSED_MARKERS: Tuple[str, ...] = ("+correction:", "+rule2:")
GEOCAT_STRATEGY_PREFIX: List[Tuple[str, str]] = [
    ("rule:", INDUCED),   # context-extractor rule induction (LOO-validated)
    ("grid:", FIXED),     # hardcoded grid-level primitives
]

# "inferred_structural" is a MIXED strategy (geocat_arc/reasoning/
# structural_inference.py, audited 2026-07-02): _infer_numpy_transform /
# _infer_shape_relationship / _infer_positional_crop /
# _infer_cell_value_from_structure / _infer_extract_object select hardcoded
# primitives (flip/rot/tile/crop/enclosed-fill) with at most fitted
# parameters -> FIXED; only _infer_color_mapping learns a color lookup table
# from the train pairs -> INDUCED.  We disambiguate at runtime via the
# __qualname__ of the returned apply_fn (recorded by geocat_layer); if the
# qualname is unavailable we classify FIXED (conservative: never inflate the
# induced fraction) and mark the record unmapped so the gap is visible.
GEOCAT_STRUCTURAL_INDUCED_FNS: Tuple[str, ...] = ("_infer_color_mapping",)
GEOCAT_STRUCTURAL_FIXED_FNS: Tuple[str, ...] = (
    "_infer_numpy_transform", "_infer_shape_relationship",
    "_infer_positional_crop", "_infer_cell_value_from_structure",
    "_infer_extract_object",
)


# ---------------------------------------------------------------------------
# Object layer (Stage-1 ObjectReasoningEngine).  Classified from the
# ProgramCertificate CONTENT, not from strategy names: 'induced' ONLY when
# (a) the selector was induced from the feature table — the program carries
# at least one ObjectRule (every rule selector, including the 0-literal
# "all objects" predicate, comes out of the zero-conflict feature-table
# search), OR (for rule-less crop/constant-shape programs) a learned
# selection expression (PredExpr/RefExpr, e.g. largest(has_hole==False))
# appears inside the output spec / action params — AND
# (b) >= 1 parameter expression is non-constant (op != "const": relational /
# feature / induced-map expressions per STAGE1_REQUIREMENTS Section 2.4.1).
# Everything else — including certificate-less solves — is FIXED (conservative:
# never inflate the induced fraction).
# ---------------------------------------------------------------------------

def _object_program_param_exprs(prog: Dict[str, Any]):
    """Yield every parameter-expression dict in a serialized ObjectProgram."""
    for rule in prog.get("rules", []) or []:
        yield from (rule.get("action", {}).get("params", {}) or {}).values()
    yield from (prog.get("default_action", {}).get("params", {}) or {}).values()
    spec = prog.get("output_spec", {}) or {}
    for key in ("region", "fill", "background"):
        if spec.get(key):
            yield spec[key]


def _expr_contains_selection(expr: Any) -> bool:
    """True when a PredExpr/RefExpr node (learned object selection) occurs."""
    if not isinstance(expr, dict):
        return False
    if expr.get("expr_class") in ("PredExpr", "RefExpr"):
        return True
    for a in expr.get("args", []) or []:
        if isinstance(a, dict):
            if "__tuple__" in a:
                if any(_expr_contains_selection(x) for x in a["__tuple__"]):
                    return True
            elif _expr_contains_selection(a):
                return True
    return False


def classify_object(certificate: Optional[Dict[str, Any]]) -> Tuple[str, bool]:
    """Return (origin_class, mapped) for an object-layer solve."""
    if not certificate:
        # accepted without a certificate (single-train-pair path): no evidence
        # of induction class -> FIXED and surfaced as unmapped.
        return FIXED, False
    prog = certificate.get("program") or {}
    selector_induced = bool(prog.get("rules")) or any(
        _expr_contains_selection(e) for e in _object_program_param_exprs(prog))
    has_nonconstant_param = any(
        isinstance(e, dict) and e.get("op") != "const"
        for e in _object_program_param_exprs(prog))
    cls = INDUCED if (selector_induced and has_nonconstant_param) else FIXED
    return cls, True


def classify_pipeline(layer: Optional[str], family: Optional[str]) -> Tuple[str, bool]:
    """Return (origin_class, mapped) for a pipeline solve."""
    fam = family or ""
    if layer in PIPELINE_LAYER_CLASS:
        return PIPELINE_LAYER_CLASS[layer], True
    if fam in PIPELINE_FAMILY_EXACT:
        return PIPELINE_FAMILY_EXACT[fam], True
    if any(m in fam for m in PIPELINE_COMPOSED_MARKERS):
        return COMPOSED, True
    # meta_engine_<engine>_<family>: classify by the wrapped family
    if fam.startswith("meta_engine_"):
        rest = fam[len("meta_engine_"):]
        for eng in _META_ENGINE_NAMES:
            if rest.startswith(eng + "_"):
                return classify_pipeline(None, rest[len(eng) + 1:])
    for prefix, cls in PIPELINE_FAMILY_PREFIX:
        if fam.startswith(prefix):
            return cls, True
    if fam in PIPELINE_FIXED_EXACT:
        return FIXED, True
    return FIXED, False  # default, reported as unmapped


def classify_geocat(strategy: Optional[str],
                    apply_fn_qualname: Optional[str] = None) -> Tuple[str, bool]:
    """Return (origin_class, mapped) for a GeoCat solve."""
    s = strategy or ""
    if s == "inferred_structural":
        q = apply_fn_qualname or ""
        if any(fn in q for fn in GEOCAT_STRUCTURAL_INDUCED_FNS):
            return INDUCED, True
        return FIXED, any(fn in q for fn in GEOCAT_STRUCTURAL_FIXED_FNS)
    if s in GEOCAT_STRATEGY_EXACT:
        return GEOCAT_STRATEGY_EXACT[s], True
    if any(m in s for m in GEOCAT_COMPOSED_MARKERS):
        return COMPOSED, True
    for prefix, cls in GEOCAT_STRATEGY_PREFIX:
        if s.startswith(prefix):
            return cls, True
    return FIXED, False


def classify_record(origin: str, layer: Optional[str], family: Optional[str],
                    geocat_strategy: Optional[str],
                    geocat_apply_fn_qualname: Optional[str] = None,
                    object_certificate: Optional[Dict[str, Any]] = None
                    ) -> Dict[str, Any]:
    """Classify a solved-task record; pipeline provenance wins for origin
    'pipeline'/'both' (continuity with v6b), then geocat, then object."""
    if origin in ("pipeline", "both"):
        cls, mapped = classify_pipeline(layer, family)
        name = f"{layer}/{family}"
    elif origin == "object":
        cls, mapped = classify_object(object_certificate)
        name = "object/object_program"
    else:
        cls, mapped = classify_geocat(geocat_strategy, geocat_apply_fn_qualname)
        name = f"geocat/{geocat_strategy}"
    return {"origin_class": cls, "origin_class_mapped": mapped,
            "origin_class_key": name}
