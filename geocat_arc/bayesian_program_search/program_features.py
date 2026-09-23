"""Extract feature vectors from candidate programs."""
from __future__ import annotations
import numpy as np

FEATURE_NAMES = [
    "operator_count",
    "depth",
    "num_unique_operators",
    "has_spatial_op",
    "has_color_op",
    "has_symmetry_op",
    "has_filter_op",
    "has_pattern_op",
    "has_fill_op",
    "total_cost",
    "complexity_score",
]

SPATIAL_OPS = {"translate", "rotate90", "reflect", "crop", "place",
               "translate_all", "rotate_all", "reflect_all", "extend_line"}
COLOR_OPS = {"recolor", "fill_region", "recolor_all", "conditional_recolor"}
SYMMETRY_OPS = {"complete_symmetry"}
FILTER_OPS = {"select", "filter", "count_based_select"}
PATTERN_OPS = {"repeat_tile_pattern", "extend_line"}
FILL_OPS = {"fill_enclosed_region", "fill_region"}


# --- Stage-2 object-program feature space (STAGE2_REQUIREMENTS 3.2) -------
# Centrally registered, fixed dimension, versioned: the ranker requires a
# fixed dim, so these name lists are literal strings (NOT derived from the
# enums at import time) and must only ever grow by appending + bumping
# OBJECT_FEATURES_VERSION.
OBJECT_FEATURES_VERSION = 1

_OBJECT_DELTA_TYPES = [
    "keep", "delete", "translate", "recolor", "copy", "scale", "reflect",
    "rotate", "move_to", "move_until_adjacent", "crop_to", "composite",
    "paint",
]
_OBJECT_SEG_VARIANTS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]

OBJECT_FEATURE_NAMES = (
    ["bias", "composition_depth", "n_rules", "expression_size",
     "max_selector_literals", "library_op_count", "param_class_rank"]
    + [f"seg_{v}" for v in _OBJECT_SEG_VARIANTS]
    + [f"delta_{t}" for t in _OBJECT_DELTA_TYPES]
)


def object_feature_dim() -> int:
    return len(OBJECT_FEATURE_NAMES)


def _extract_object_features(program) -> np.ndarray:
    """ObjectProgram / ComposedProgram branch: composition depth, rule and
    expression counts, library usage, parameter class, segmentation-variant
    and delta-type one-hots.  Duck-typed on the Stage-1/2 program surface
    (``segmentation_variant`` + ``rules``)."""
    stages = getattr(program, "stages", None) or [program]
    rules = [r for s in stages for r in s.rules]
    deltas = {r.action.delta_type.value for r in rules}
    deltas |= {s.default_action.delta_type.value for s in stages}
    seg = {s.segmentation_variant.value for s in stages}
    vec = [
        1.0,
        float(len(stages)),
        float(len(rules)),
        float(sum(s.expression_size for s in stages)),
        float(max((r.selector.literals for r in rules), default=0)),
        float(len(program.library_operators_used)),
        float(program.worst_parameter_class.rank),
    ]
    vec += [1.0 if v in seg else 0.0 for v in _OBJECT_SEG_VARIANTS]
    vec += [1.0 if t in deltas else 0.0 for t in _OBJECT_DELTA_TYPES]
    return np.array(vec, dtype=np.float64)


def extract_features(program) -> np.ndarray:
    if hasattr(program, 'segmentation_variant') and hasattr(program, 'rules'):
        return _extract_object_features(program)
    if hasattr(program, 'operator_names'):
        ops = program.operator_names
    elif hasattr(program, 'steps'):
        ops = [s.morphism.name for s in program.steps]
    else:
        ops = []

    op_set = set(ops)
    depth = len(ops)
    total_cost = getattr(program, 'total_cost', depth * 1.0)

    features = np.array([
        float(len(ops)),
        float(depth),
        float(len(op_set)),
        float(bool(op_set & SPATIAL_OPS)),
        float(bool(op_set & COLOR_OPS)),
        float(bool(op_set & SYMMETRY_OPS)),
        float(bool(op_set & FILTER_OPS)),
        float(bool(op_set & PATTERN_OPS)),
        float(bool(op_set & FILL_OPS)),
        float(total_cost),
        float(depth * len(op_set)),
    ], dtype=np.float64)

    return features


def feature_dim() -> int:
    return len(FEATURE_NAMES)
