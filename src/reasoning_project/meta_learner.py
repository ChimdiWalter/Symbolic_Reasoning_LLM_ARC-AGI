"""Meta-Learner: self-synthesizing program abstractions from solved tasks.

Observes (delta, program) pairs from solved tasks, extracts abstract
program templates, and applies them to novel tasks via structural
similarity. This is meta-learning without neural networks — the system
learns new reasoning strategies from its own verified solutions.

Architecture:
    Solved tasks → (delta, program) pairs
    → Group by program family
    → Extract template: fixed params + variable params
    → Learn param inference rules: delta features → param values
    → Store templates with delta centroids

    New task → compute delta → find nearest templates
    → infer params from delta → construct executable
    → verify on train pairs → return candidates

The key insight: instead of hardcoding "if delta shows reflection, try
reflection," the system discovers this mapping empirically from its own
solutions. It generalizes to new mappings it has never been explicitly
programmed with.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from reasoning_project.delta_engine import (
    TaskDelta,
    PairDelta,
    compute_task_delta,
    delta_to_embedding,
)
from reasoning_project.operator_genesis import SynthesizedOperator


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ProgramTemplate:
    """Abstract program structure with holes for task-specific parameters."""
    template_id: str
    family: str
    fixed_params: Dict[str, Any]
    variable_params: List[str]
    param_values_seen: Dict[str, List[Any]]
    delta_centroid: np.ndarray
    delta_embeddings: List[np.ndarray]
    exemplar_count: int
    exemplar_task_ids: List[str]
    confidence: float

    def __repr__(self):
        vp = {k: self.param_values_seen.get(k, []) for k in self.variable_params}
        return (f"ProgramTemplate({self.family}, "
                f"fixed={self.fixed_params}, "
                f"variable={vp}, "
                f"exemplars={self.exemplar_count})")


@dataclass
class SolvedExemplar:
    """A solved task with its delta and program."""
    task_id: str
    family: str
    params: Dict[str, Any]
    explanation: str
    delta_type: str
    delta_subtypes: List[str]
    consistency_score: float
    embedding: np.ndarray


# ---------------------------------------------------------------------------
# Parameter inference rules
# ---------------------------------------------------------------------------

def _infer_reflection_axis(delta: TaskDelta) -> List[Any]:
    if delta.consistent_reflection:
        return [delta.consistent_reflection]
    candidates = []
    for pd in delta.pair_deltas:
        if pd.has_reflection and pd.reflection_axis:
            candidates.append(pd.reflection_axis)
    if candidates:
        return list(set(candidates))
    return ["vertical", "horizontal", "both"]


def _infer_rotation_angle(delta: TaskDelta) -> List[Any]:
    if delta.consistent_rotation:
        return [delta.consistent_rotation]
    return [90, 180, 270]


def _infer_gravity_direction(delta: TaskDelta) -> List[Any]:
    if not delta.pair_deltas:
        return ["down", "up", "left", "right"]
    translations = []
    for pd in delta.pair_deltas:
        for c in pd.correspondences:
            if c.translation and c.transform_type in ("moved", "moved_recolored"):
                translations.append(c.translation)
    if not translations:
        return ["down", "up", "left", "right"]
    avg_dr = sum(t[0] for t in translations) / len(translations)
    avg_dc = sum(t[1] for t in translations) / len(translations)
    candidates = []
    if avg_dr > 0.5:
        candidates.append("down")
    elif avg_dr < -0.5:
        candidates.append("up")
    if avg_dc > 0.5:
        candidates.append("right")
    elif avg_dc < -0.5:
        candidates.append("left")
    if not candidates:
        candidates = ["down", "up", "left", "right"]
    return candidates


def _infer_scale_ratio(delta: TaskDelta) -> List[Any]:
    ratios = set()
    for pd in delta.pair_deltas:
        ih, iw = pd.input_shape
        oh, ow = pd.output_shape
        if oh > ih and ow > iw and oh % ih == 0 and ow % iw == 0:
            ratios.add((oh // ih, ow // iw))
        elif ih > oh and iw > ow and ih % oh == 0 and iw % ow == 0:
            ratios.add((ih // oh, iw // ow))
    return list(ratios) if ratios else [(2, 2), (3, 3)]


def _infer_fill_color(delta: TaskDelta) -> List[Any]:
    candidates = set()
    for pd in delta.pair_deltas:
        candidates.update(pd.colors_added)
    if not candidates:
        candidates = set(range(1, 10))
    return list(candidates)


def _infer_color_mapping(delta: TaskDelta) -> List[Any]:
    if delta.consistent_color_map:
        return [delta.consistent_color_map]
    maps = []
    for pd in delta.pair_deltas:
        if pd.color_map:
            maps.append(pd.color_map)
    return maps if maps else []


def _infer_crop_offset(delta: TaskDelta) -> List[Any]:
    return [(0, 0)]


def _infer_crop_size(delta: TaskDelta) -> List[Any]:
    sizes = set()
    for pd in delta.pair_deltas:
        sizes.add(pd.output_shape)
    return list(sizes)


def _infer_border_color(delta: TaskDelta) -> List[Any]:
    return _infer_fill_color(delta)


def _infer_translation(delta: TaskDelta) -> List[Any]:
    if delta.consistent_translation:
        return [delta.consistent_translation]
    candidates = set()
    for pd in delta.pair_deltas:
        if pd.has_consistent_translation and pd.consistent_translation:
            candidates.add(pd.consistent_translation)
    return list(candidates) if candidates else [(0, 1), (1, 0), (0, -1), (-1, 0)]


def _infer_tile_factor(delta: TaskDelta) -> List[Any]:
    factors = set()
    for pd in delta.pair_deltas:
        if pd.is_tile and pd.tile_factor:
            factors.add(pd.tile_factor)
    return list(factors) if factors else [(2, 2), (1, 2), (2, 1)]


def _infer_downscale_mode(delta: TaskDelta) -> List[Any]:
    return ["majority", "top_left"]


def _infer_recolor_params(delta: TaskDelta) -> List[Any]:
    pairs = []
    for pd in delta.pair_deltas:
        for c_removed in pd.colors_removed:
            for c_added in pd.colors_added:
                pairs.append({"src": c_removed, "dst": c_added})
    if not pairs:
        for pd in delta.pair_deltas:
            if pd.color_map:
                for s, d in pd.color_map.items():
                    if s != d:
                        pairs.append({"src": s, "dst": d})
    return pairs if pairs else []


PARAM_INFERENCE_RULES: Dict[str, Dict[str, Callable]] = {
    "reflection": {"axis": _infer_reflection_axis},
    "rotation": {"angle": _infer_rotation_angle},
    "gravity": {"direction": _infer_gravity_direction},
    "upscale": {"ratio": _infer_scale_ratio},
    "downscale": {"ratio": _infer_scale_ratio, "mode": _infer_downscale_mode},
    "flood_fill_enclosed": {"fill_color": _infer_fill_color},
    "color_map": {"mapping": _infer_color_mapping},
    "subgrid_extract": {"offset": _infer_crop_offset, "size": _infer_crop_size},
    "border_fill": {"color": _infer_border_color},
    "translation": {"dr": lambda d: [t[0] for t in _infer_translation(d)],
                     "dc": lambda d: [t[1] for t in _infer_translation(d)]},
    "tile": {"factor": _infer_tile_factor},
    "single_recolor": {"src": lambda d: [p["src"] for p in _infer_recolor_params(d)],
                        "dst": lambda d: [p["dst"] for p in _infer_recolor_params(d)]},
    "remove_color": {"color": lambda d: list(d.pair_deltas[0].colors_removed) if d.pair_deltas and d.pair_deltas[0].colors_removed else list(range(1, 10))},
    "replace_bg": {"fill_value": _infer_fill_color},
}


# ---------------------------------------------------------------------------
# Program executors (construct executable from family + params)
# ---------------------------------------------------------------------------

def _build_executor(family: str, params: Dict[str, Any],
                    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
                    ) -> Optional[Callable[[np.ndarray], np.ndarray]]:
    """Build an executable function from family name and parameters."""

    if family == "reflection":
        axis = params.get("axis", "vertical")
        def fn(grid, _ax=axis):
            if _ax == "vertical":
                return grid[::-1, :].copy()
            elif _ax == "horizontal":
                return grid[:, ::-1].copy()
            elif _ax == "both":
                return grid[::-1, ::-1].copy()
            return grid.copy()
        return fn

    elif family == "rotation":
        angle = params.get("angle", 90)
        def fn(grid, _a=angle):
            return np.rot90(grid, k=_a // 90).copy()
        return fn

    elif family == "transpose":
        return lambda grid: grid.T.copy()

    elif family == "gravity":
        direction = params.get("direction", "down")
        def fn(grid, _d=direction):
            H, W = grid.shape
            out = np.zeros_like(grid)
            if _d == "down":
                for c in range(W):
                    col = [grid[r, c] for r in range(H) if grid[r, c] != 0]
                    for i, v in enumerate(col):
                        out[H - len(col) + i, c] = v
            elif _d == "up":
                for c in range(W):
                    col = [grid[r, c] for r in range(H) if grid[r, c] != 0]
                    for i, v in enumerate(col):
                        out[i, c] = v
            elif _d == "right":
                for r in range(H):
                    row = [grid[r, c] for c in range(W) if grid[r, c] != 0]
                    for i, v in enumerate(row):
                        out[r, W - len(row) + i] = v
            elif _d == "left":
                for r in range(H):
                    row = [grid[r, c] for c in range(W) if grid[r, c] != 0]
                    for i, v in enumerate(row):
                        out[r, i] = v
            return out
        return fn

    elif family == "upscale":
        ratio = params.get("ratio", (2, 2))
        rh, rw = ratio
        def fn(grid, _rh=rh, _rw=rw):
            return np.repeat(np.repeat(grid, _rh, axis=0), _rw, axis=1)
        return fn

    elif family == "downscale":
        ratio = params.get("ratio", (2, 2))
        mode = params.get("mode", "majority")
        rh, rw = ratio
        def fn(grid, _rh=rh, _rw=rw, _m=mode):
            H, W = grid.shape
            oh, ow = H // _rh, W // _rw
            out = np.zeros((oh, ow), dtype=grid.dtype)
            for r in range(oh):
                for c in range(ow):
                    patch = grid[r*_rh:(r+1)*_rh, c*_rw:(c+1)*_rw]
                    if _m == "top_left":
                        out[r, c] = patch[0, 0]
                    else:
                        vals, counts = np.unique(patch, return_counts=True)
                        out[r, c] = vals[counts.argmax()]
            return out
        return fn

    elif family == "color_map":
        mapping = params.get("mapping", {})
        def fn(grid, _m=mapping):
            out = grid.copy()
            for s, d in _m.items():
                out[grid == s] = d
            return out
        return fn

    elif family == "flood_fill_enclosed":
        fill_color = params.get("fill_color", 1)
        bg = params.get("bg", 0)
        def fn(grid, _fc=fill_color, _bg=bg):
            from scipy.ndimage import label as ndlabel
            out = grid.copy()
            mask = grid == _bg
            labeled, n = ndlabel(mask)
            for comp_id in range(1, n + 1):
                comp = labeled == comp_id
                rows, cols = np.where(comp)
                touches_border = (rows.min() == 0 or rows.max() == grid.shape[0]-1 or
                                 cols.min() == 0 or cols.max() == grid.shape[1]-1)
                if not touches_border:
                    out[comp] = _fc
            return out
        return fn

    elif family == "border_fill":
        color = params.get("color", 0)
        def fn(grid, _c=color):
            out = grid.copy()
            out[0, :] = _c
            out[-1, :] = _c
            out[:, 0] = _c
            out[:, -1] = _c
            return out
        return fn

    elif family == "tile":
        factor = params.get("factor", (2, 2))
        th, tw = factor
        def fn(grid, _h=th, _w=tw):
            return np.tile(grid, (_h, _w))
        return fn

    elif family == "crop_to_content":
        bg = params.get("bg", 0)
        def fn(grid, _bg=bg):
            nonbg = np.argwhere(grid != _bg)
            if len(nonbg) == 0:
                return grid.copy()
            r0, c0 = nonbg.min(axis=0)
            r1, c1 = nonbg.max(axis=0)
            return grid[r0:r1+1, c0:c1+1].copy()
        return fn

    elif family == "translation":
        dr = params.get("dr", 0)
        dc = params.get("dc", 0)
        def fn(grid, _dr=dr, _dc=dc):
            H, W = grid.shape
            out = np.zeros_like(grid)
            for r in range(H):
                for c in range(W):
                    nr, nc = r + _dr, c + _dc
                    if 0 <= nr < H and 0 <= nc < W:
                        out[nr, nc] = grid[r, c]
            return out
        return fn

    elif family == "single_recolor":
        src = params.get("src", 0)
        dst = params.get("dst", 0)
        def fn(grid, _s=src, _d=dst):
            out = grid.copy()
            out[grid == _s] = _d
            return out
        return fn

    elif family == "remove_color":
        color = params.get("color", 1)
        def fn(grid, _c=color):
            out = grid.copy()
            out[grid == _c] = 0
            return out
        return fn

    elif family == "replace_bg":
        fill_value = params.get("fill_value", 1)
        def fn(grid, _fv=fill_value):
            out = grid.copy()
            out[grid == 0] = _fv
            return out
        return fn

    elif family == "subgrid_extract":
        r, c = params.get("offset", (0, 0))
        oh, ow = params.get("size", (1, 1))
        def fn(grid, _r=r, _c=c, _h=oh, _w=ow):
            return grid[_r:_r+_h, _c:_c+_w].copy()
        return fn

    elif family.startswith("solver_"):
        solver_name = family.replace("solver_", "")
        try:
            if solver_name == "local_rule":
                from reasoning_project.local_rules import solve_task_local_rules as sf
            elif solver_name == "separator_decompose":
                from reasoning_project.separator_decompose import solve_task_separator_decompose as sf
            elif solver_name == "crop_extract":
                from reasoning_project.crop_extract import solve_task_crop_extract as sf
            elif solver_name == "color_solver":
                from reasoning_project.color_solver import solve_task_color as sf
            else:
                return None
            def fn(grid, _sf=sf, _tp=train_pairs):
                r = _sf(_tp, [grid])
                if r is None:
                    return grid.copy()
                p = r[0][0] if isinstance(r[0], list) else r[0]
                return p
            return fn
        except ImportError:
            return None

    return None


# ---------------------------------------------------------------------------
# Template extraction
# ---------------------------------------------------------------------------

def extract_templates(
    exemplars: List[SolvedExemplar],
) -> List[ProgramTemplate]:
    """Extract abstract program templates from solved exemplars.

    Groups by family, identifies fixed vs variable params, computes
    delta centroids for similarity retrieval.
    """
    from collections import defaultdict

    by_family = defaultdict(list)
    for ex in exemplars:
        by_family[ex.family].append(ex)

    templates = []

    for family, group in by_family.items():
        all_params = [ex.params for ex in group]
        all_keys = set()
        for p in all_params:
            all_keys.update(p.keys())

        fixed_params = {}
        variable_params = []
        param_values_seen = {}

        for key in sorted(all_keys):
            values = [p.get(key) for p in all_params]
            str_values = set(str(v) for v in values)
            if len(str_values) == 1:
                fixed_params[key] = values[0]
            else:
                variable_params.append(key)
                param_values_seen[key] = values

        embeddings = [ex.embedding for ex in group]
        centroid = np.mean(embeddings, axis=0)

        confidence = min(1.0, len(group) / 5.0)

        templates.append(ProgramTemplate(
            template_id=f"tpl_{family}_{uuid.uuid4().hex[:8]}",
            family=family,
            fixed_params=fixed_params,
            variable_params=variable_params,
            param_values_seen=param_values_seen,
            delta_centroid=centroid,
            delta_embeddings=embeddings,
            exemplar_count=len(group),
            exemplar_task_ids=[ex.task_id for ex in group],
            confidence=confidence,
        ))

    templates.sort(key=lambda t: -t.exemplar_count)
    return templates


# ---------------------------------------------------------------------------
# Template instantiation
# ---------------------------------------------------------------------------

def _infer_params(
    template: ProgramTemplate,
    delta: TaskDelta,
) -> List[Dict[str, Any]]:
    """Infer variable parameter values from a new task's delta.

    Returns a list of candidate parameter dictionaries (multiple options
    when inference is uncertain).
    """
    if not template.variable_params:
        return [template.fixed_params.copy()]

    family_rules = PARAM_INFERENCE_RULES.get(template.family, {})

    param_options: Dict[str, List[Any]] = {}
    for vp in template.variable_params:
        if vp in family_rules:
            inferred = family_rules[vp](delta)
            if inferred:
                param_options[vp] = inferred
            else:
                param_options[vp] = template.param_values_seen.get(vp, [])
        else:
            param_options[vp] = template.param_values_seen.get(vp, [])

    candidates = [template.fixed_params.copy()]
    for vp in template.variable_params:
        new_candidates = []
        for base in candidates:
            for val in param_options.get(vp, [None]):
                c = base.copy()
                c[vp] = val
                new_candidates.append(c)
        candidates = new_candidates
        if len(candidates) > 50:
            candidates = candidates[:50]

    return candidates


def instantiate_template(
    template: ProgramTemplate,
    delta: TaskDelta,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> List[SynthesizedOperator]:
    """Instantiate a template for a new task by inferring parameters."""
    param_candidates = _infer_params(template, delta)
    results = []

    for params in param_candidates:
        executor = _build_executor(template.family, params, train_pairs)
        if executor is None:
            continue

        try:
            all_match = True
            for inp, out in train_pairs:
                pred = executor(inp)
                if pred is None or not isinstance(pred, np.ndarray):
                    all_match = False
                    break
                if pred.shape != out.shape or not np.array_equal(pred, out):
                    all_match = False
                    break
            if all_match:
                results.append(SynthesizedOperator(
                    operator_id=f"meta_{template.template_id}_{uuid.uuid4().hex[:8]}",
                    operator_family=f"meta_{template.family}",
                    parameters=params,
                    preconditions=[],
                    execute=executor,
                    explanation=f"Meta-learned: {template.family} (from {template.exemplar_count} exemplars)",
                    source_failure_signature={
                        "template_id": template.template_id,
                        "exemplar_count": template.exemplar_count,
                    },
                ))
        except Exception:
            continue

    return results


# ---------------------------------------------------------------------------
# Compositional template transfer
# ---------------------------------------------------------------------------

def _try_template_compositions(
    templates: List[ProgramTemplate],
    delta: TaskDelta,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    max_depth: int = 2,
) -> List[SynthesizedOperator]:
    """Try composing templates that individually get partial accuracy.

    This is where meta-learning produces genuinely novel compositions:
    if template A gets 60% right and template B fixes the residual,
    compose them — even if this exact composition was never seen before.
    """
    from reasoning_project.delta_engine import score_partial_correctness, compute_residual

    results = []
    partial_candidates = []

    for tpl in templates[:10]:
        ops = instantiate_template(tpl, delta, train_pairs)
        for op in ops:
            total_acc = 0.0
            preds = []
            valid = True
            for inp, out in train_pairs:
                try:
                    pred = op.execute(inp)
                    if pred is None or not isinstance(pred, np.ndarray):
                        valid = False
                        break
                    sc = score_partial_correctness(pred, out)
                    total_acc += sc["score"]
                    preds.append(pred)
                except Exception:
                    valid = False
                    break
            if not valid:
                continue
            avg_acc = total_acc / len(train_pairs)
            if 0.3 <= avg_acc < 1.0 - 1e-9:
                partial_candidates.append((op, avg_acc, preds))

    partial_candidates.sort(key=lambda x: -x[1])

    for base_op, base_acc, base_preds in partial_candidates[:3]:
        residual_pairs = []
        valid = True
        for pred, (_, expected) in zip(base_preds, train_pairs):
            if pred.shape != expected.shape:
                valid = False
                break
            residual_pairs.append((pred, expected))
        if not valid:
            continue

        residual_delta = compute_task_delta(residual_pairs)

        for tpl in templates[:10]:
            corrections = instantiate_template(tpl, residual_delta, residual_pairs)
            for corr_op in corrections:
                def make_composed(base_fn, corr_fn):
                    def fn(grid, _b=base_fn, _c=corr_fn):
                        intermediate = _b(grid)
                        return _c(intermediate)
                    return fn
                composed = make_composed(base_op.execute, corr_op.execute)
                try:
                    all_match = True
                    for inp, out in train_pairs:
                        pred = composed(inp)
                        if pred is None or pred.shape != out.shape or not np.array_equal(pred, out):
                            all_match = False
                            break
                    if all_match:
                        results.append(SynthesizedOperator(
                            operator_id=f"meta_comp_{uuid.uuid4().hex[:8]}",
                            operator_family=f"meta_compose_{base_op.operator_family}_{corr_op.operator_family}",
                            parameters={
                                "base": base_op.operator_family,
                                "correction": corr_op.operator_family,
                            },
                            preconditions=[],
                            execute=composed,
                            explanation=(f"Meta-composed: {base_op.explanation} "
                                       f"→ {corr_op.explanation}"),
                            source_failure_signature={},
                        ))
                except Exception:
                    continue

    return results


# ---------------------------------------------------------------------------
# Main meta-learner class
# ---------------------------------------------------------------------------

class MetaLearner:
    """Self-improving reasoning system that learns from its own solutions.

    Usage:
        learner = MetaLearner()
        learner.learn_from_solved(solved_exemplars)
        candidates = learner.propose(train_pairs)
    """

    def __init__(self):
        self.templates: List[ProgramTemplate] = []
        self.exemplars: List[SolvedExemplar] = []

    def learn_from_solved(self, exemplars: List[SolvedExemplar]) -> None:
        """Extract templates from a set of solved (delta, program) pairs."""
        self.exemplars = exemplars
        self.templates = extract_templates(exemplars)

    def learn_from_records(self, records: List[Dict[str, Any]]) -> None:
        """Learn from serialized records (as saved by the collection script)."""
        exemplars = []
        for r in records:
            exemplars.append(SolvedExemplar(
                task_id=r["task_id"],
                family=r["family"],
                params=r["params"],
                explanation=r["explanation"],
                delta_type=r["delta_type"],
                delta_subtypes=r["delta_subtypes"],
                consistency_score=r["consistency_score"],
                embedding=np.array(r["embedding"], dtype=np.float32),
            ))
        self.learn_from_solved(exemplars)

    def _find_nearest_templates(
        self, delta_embedding: np.ndarray, top_k: int = 5,
    ) -> List[Tuple[ProgramTemplate, float]]:
        """Find templates whose delta centroids are closest to the query."""
        scored = []
        for tpl in self.templates:
            dist = float(np.linalg.norm(delta_embedding - tpl.delta_centroid))
            scored.append((tpl, dist))
        scored.sort(key=lambda x: x[1])
        return scored[:top_k]

    def propose(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        top_k: int = 10,
        try_compositions: bool = True,
    ) -> List[SynthesizedOperator]:
        """Propose candidates for a new task using learned templates.

        1. Compute delta for the new task
        2. Find nearest templates by delta similarity
        3. Instantiate each template with inferred parameters
        4. Try compositional transfer (partial + correction)
        5. Return all train-consistent candidates
        """
        if not self.templates:
            return []

        delta = compute_task_delta(train_pairs)
        embedding = delta_to_embedding(delta)

        candidates = []

        nearest = self._find_nearest_templates(embedding, top_k=top_k)

        for tpl, dist in nearest:
            ops = instantiate_template(tpl, delta, train_pairs)
            candidates.extend(ops)

        for tpl in self.templates:
            if tpl.exemplar_count >= 2:
                ops = instantiate_template(tpl, delta, train_pairs)
                candidates.extend(ops)

        if try_compositions and not candidates:
            comp_ops = _try_template_compositions(
                self.templates, delta, train_pairs, max_depth=2
            )
            candidates.extend(comp_ops)

        seen = set()
        unique = []
        for op in candidates:
            key = (op.operator_family, op.explanation)
            if key not in seen:
                seen.add(key)
                unique.append(op)

        return unique


# ---------------------------------------------------------------------------
# Convenience: build meta-learner from solved task records
# ---------------------------------------------------------------------------

def build_meta_learner_from_file(path: str) -> MetaLearner:
    """Load solved records and build a meta-learner."""
    import json
    with open(path) as f:
        records = json.load(f)
    learner = MetaLearner()
    learner.learn_from_records(records)
    return learner
