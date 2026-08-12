#!/usr/bin/env python3
"""Helmholtz-style synthetic ARC task generator (DreamCoder, Ellis et al. 2021).

Samples programs from the engine's own ObjectProgram grammar and renders them
into synthetic ARC tasks via the engine's render_program executor.  The output
is training data for a search-guidance network (step 2).

v1 coverage:
  - Grid-level uniform transformations: every object in the scene receives the
    SAME action (selector = PredExpr("true")).  This covers the majority of
    accepted programs in the current corpus (translate, recolor, reflect,
    rotate, scale, delete, keep, grow/fill_interior, grow/halo).
  - NOT yet covered (v2 targets):
    * Selective rules (non-trivial selectors splitting the object set)
    * COMPOSITE actions (multi-step per object)
    * COPY with non-trivial placement lattices
    * CROP_TO / constant_shape output specs
    * MOVE_UNTIL_ADJACENT with RefExpr targets
    * PAINT / SYNTH_COPY / COPY_PART / CONNECT / FILL_LINE
    * Mutation of real accepted programs (implemented but only activates when
      outputs/*/programs/*.json files contain rich enough programs)

Usage:
    python guide/dream.py N seed out.jsonl
    python guide/dream.py --smoke        # 50 tasks, distribution, consistency check

Deterministic per seed.  No LLMs involved.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import glob
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Engine imports (all from the project's own code)
# ---------------------------------------------------------------------------

# Ensure the project root is on sys.path so geocat_arc is importable.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject
from geocat_arc.object_reasoning.types import (
    AXES, ANGLES, DIRECTIONS,
    ActionRule, DeltaType, ObjectProgram, ObjectRule, OutputSpec,
    ParameterClass, SegmentationVariant, SelectorRule,
)
from geocat_arc.object_reasoning.expressions import (
    AxisExpr, AngleExpr, ColorExpr, DirectionExpr, GrowModeExpr,
    PredExpr, ScalarExpr, VecExpr,
)
from geocat_arc.object_reasoning.actions import render_program
from geocat_arc.object_reasoning.expressions import EvalError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARC_COLORS = list(range(10))  # 0..9


# ---------------------------------------------------------------------------
# 1. Scene sampling
# ---------------------------------------------------------------------------

def _bbox_of(cells: frozenset) -> tuple[int, int, int, int]:
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return (min(rows), min(cols), max(rows) + 1, max(cols) + 1)


def _make_rectangle(rng: np.random.Generator, h_max: int, w_max: int,
                    r0: int, c0: int) -> frozenset:
    """Random rectangle of height 1..h_max, width 1..w_max at (r0,c0)."""
    h = rng.integers(1, min(h_max, 5) + 1)
    w = rng.integers(1, min(w_max, 5) + 1)
    return frozenset((r0 + dr, c0 + dc) for dr in range(h) for dc in range(w))


def _make_blob(rng: np.random.Generator, h_max: int, w_max: int,
               r0: int, c0: int) -> frozenset:
    """Random walk blob: start at (r0,c0), add 2-8 neighbors."""
    cells = {(r0, c0)}
    frontier = [(r0, c0)]
    n_target = rng.integers(2, 9)
    for _ in range(n_target * 4):
        if len(cells) >= n_target:
            break
        r, c = frontier[rng.integers(len(frontier))]
        dr, dc = [(0, 1), (0, -1), (1, 0), (-1, 0)][rng.integers(4)]
        nr, nc = r + dr, c + dc
        if 0 <= nr < r0 + h_max and 0 <= nc < c0 + w_max and nr >= r0 and nc >= c0:
            if (nr, nc) not in cells:
                cells.add((nr, nc))
                frontier.append((nr, nc))
    return frozenset(cells)


def _make_line(rng: np.random.Generator, h_max: int, w_max: int,
               r0: int, c0: int) -> frozenset:
    """Random horizontal or vertical line."""
    if rng.random() < 0.5:
        # horizontal
        length = rng.integers(2, min(w_max, 6) + 1)
        return frozenset((r0, c0 + dc) for dc in range(length))
    else:
        length = rng.integers(2, min(h_max, 6) + 1)
        return frozenset((r0 + dr, c0) for dr in range(length))


def _make_single_cell(r0: int, c0: int) -> frozenset:
    return frozenset([(r0, c0)])


def _overlaps(cells: frozenset, occupied: set) -> bool:
    return bool(cells & occupied)


def sample_scene(rng: np.random.Generator) -> tuple[Grid, list[ARCObject]]:
    """Generate a random grid with 1-6 non-overlapping objects.

    Returns (grid, objects) where objects are the foreground ARCObjects
    placed on a solid background.
    """
    height = rng.integers(5, 26)
    width = rng.integers(5, 26)
    bg_color = int(rng.choice(ARC_COLORS))

    n_objects = rng.integers(1, min(7, max(2, (height * width) // 15)))
    occupied: set = set()
    objects: list[ARCObject] = []

    makers = [_make_rectangle, _make_blob, _make_line]
    maker_weights = [0.4, 0.35, 0.15]
    # also allow single cells with remaining weight
    # normalize
    total = sum(maker_weights)
    maker_weights = [w / total for w in maker_weights]

    for obj_id in range(n_objects):
        # pick a random color != background
        fg_colors = [c for c in ARC_COLORS if c != bg_color]
        if not fg_colors:
            fg_colors = [1]
        color = int(rng.choice(fg_colors))

        # try to place an object in an unoccupied region
        placed = False
        for _attempt in range(40):
            r0 = int(rng.integers(0, height - 1))
            c0 = int(rng.integers(0, width - 1))
            h_avail = height - r0
            w_avail = width - c0
            if h_avail < 1 or w_avail < 1:
                continue

            # choose shape maker
            p = rng.random()
            if p < 0.1:
                cells = _make_single_cell(r0, c0)
            elif p < 0.5:
                cells = _make_rectangle(rng, h_avail, w_avail, r0, c0)
            elif p < 0.8:
                cells = _make_blob(rng, h_avail, w_avail, r0, c0)
            else:
                cells = _make_line(rng, h_avail, w_avail, r0, c0)

            # check bounds
            if any(r < 0 or r >= height or c < 0 or c >= width
                   for r, c in cells):
                continue
            if _overlaps(cells, occupied):
                continue

            occupied |= cells
            bbox = _bbox_of(cells)
            obj = ARCObject(id=obj_id, cells=cells, color=color,
                            bounding_box=bbox)
            objects.append(obj)
            placed = True
            break

    if not objects:
        # fallback: place a single cell
        r0, c0 = int(rng.integers(0, height)), int(rng.integers(0, width))
        fg_colors = [c for c in ARC_COLORS if c != bg_color]
        color = int(rng.choice(fg_colors)) if fg_colors else 1
        cells = frozenset([(r0, c0)])
        objects.append(ARCObject(id=0, cells=cells, color=color,
                                 bounding_box=(r0, c0, r0 + 1, c0 + 1)))

    # Build the grid
    data = np.full((height, width), bg_color, dtype=np.int32)
    for obj in objects:
        for r, c in obj.cells:
            data[r, c] = obj.color
    return Grid(data), objects


# ---------------------------------------------------------------------------
# 2. Program sampling
# ---------------------------------------------------------------------------

# v1 action families: uniform, grid-level transformations that can be applied
# to every object with a const-expression parameter.  Each entry:
#   (DeltaType, param_builder_fn(rng, scene_objects, grid) -> dict[str,Expr] | None)
# param_builder returns None when the action cannot be applied to this scene.

def _param_translate(rng: np.random.Generator, objects: list[ARCObject],
                     grid: Grid) -> Optional[dict]:
    """Random constant translation vector."""
    dr = int(rng.integers(-5, 6))
    dc = int(rng.integers(-5, 6))
    if dr == 0 and dc == 0:
        dr = int(rng.choice([-2, -1, 1, 2]))
    return {"vector": VecExpr(op="const", args=(dr, dc))}


def _param_recolor(rng: np.random.Generator, objects: list[ARCObject],
                   grid: Grid) -> Optional[dict]:
    """Random recolor to a constant color."""
    color = int(rng.integers(0, 10))
    return {"color": ColorExpr(op="const", args=(color,))}


def _param_reflect(rng: np.random.Generator, objects: list[ARCObject],
                   grid: Grid) -> Optional[dict]:
    """Random reflect along a random axis (within bbox)."""
    axis = str(rng.choice(["horizontal", "vertical"]))
    return {"axis": AxisExpr(op="const", args=(axis,))}


def _param_rotate(rng: np.random.Generator, objects: list[ARCObject],
                  grid: Grid) -> Optional[dict]:
    """Random rotation by a random angle."""
    angle = int(rng.choice([90, 180, 270]))
    return {"angle": AngleExpr(op="const", args=(angle,))}


def _param_scale(rng: np.random.Generator, objects: list[ARCObject],
                 grid: Grid) -> Optional[dict]:
    """Random integer scale factor 2 or 3 (must fit in grid)."""
    factor = int(rng.choice([2, 3]))
    # Check if any object would overflow the grid
    for obj in objects:
        h = obj.bbox_height * factor
        w = obj.bbox_width * factor
        if (obj.bounding_box[0] + h > grid.height or
                obj.bounding_box[1] + w > grid.width):
            return None
    return {"factor": ScalarExpr(op="const", args=(factor,))}


def _param_delete(rng: np.random.Generator, objects: list[ARCObject],
                  grid: Grid) -> Optional[dict]:
    """Delete (no params)."""
    return {}


def _param_grow_fill(rng: np.random.Generator, objects: list[ARCObject],
                     grid: Grid) -> Optional[dict]:
    """Grow fill_interior mode: fill holes with a random color."""
    # Only works on objects with holes (rectangles >= 3x3 with interior)
    has_holes = any(obj.bbox_height >= 3 and obj.bbox_width >= 3
                    and not obj.is_rectangle for obj in objects)
    if not has_holes:
        return None
    color = int(rng.integers(0, 10))
    return {
        "mode": GrowModeExpr(op="const", args=("fill_interior",)),
        "color": ColorExpr(op="const", args=(color,)),
    }


def _param_grow_halo(rng: np.random.Generator, objects: list[ARCObject],
                     grid: Grid) -> Optional[dict]:
    """Grow halo mode: add a one-cell halo in a random color."""
    color = int(rng.integers(0, 10))
    conn = int(rng.choice([4, 8]))
    return {
        "mode": GrowModeExpr(op="const", args=("halo",)),
        "color": ColorExpr(op="const", args=(color,)),
        "conn": ScalarExpr(op="const", args=(conn,)),
    }


# Action family registry: (DeltaType, builder, weight)
ACTION_FAMILIES: list[tuple[DeltaType, Any, float]] = [
    (DeltaType.TRANSLATE,  _param_translate, 3.0),
    (DeltaType.RECOLOR,    _param_recolor,   3.0),
    (DeltaType.REFLECT,    _param_reflect,   2.0),
    (DeltaType.ROTATE,     _param_rotate,    2.0),
    (DeltaType.SCALE,      _param_scale,     1.5),
    (DeltaType.DELETE,     _param_delete,    1.0),
    (DeltaType.GROW,       _param_grow_halo, 1.5),
    (DeltaType.GROW,       _param_grow_fill, 0.5),
]


def _sample_action(rng: np.random.Generator, objects: list[ARCObject],
                   grid: Grid) -> Optional[tuple[DeltaType, dict, str]]:
    """Sample one action from the v1 families.  Returns (delta_type, params, family_tag)
    or None if no family is applicable.
    """
    # shuffle by weighted priority
    weights = np.array([w for _, _, w in ACTION_FAMILIES])
    order = rng.choice(len(ACTION_FAMILIES), size=len(ACTION_FAMILIES),
                       replace=False, p=weights / weights.sum())
    for idx in order:
        dt, builder, _ = ACTION_FAMILIES[idx]
        params = builder(rng, objects, grid)
        if params is not None:
            family_tag = f"{dt.value}"
            if dt is DeltaType.GROW:
                mode_expr = params.get("mode")
                if mode_expr is not None:
                    family_tag = f"grow_{mode_expr.args[0]}"
            return dt, params, family_tag
    return None


def sample_program(rng: np.random.Generator, objects: list[ARCObject],
                   grid: Grid,
                   accepted_programs: list[dict] | None = None,
                   ) -> Optional[tuple[ObjectProgram, dict]]:
    """Sample a random valid program.

    If accepted_programs is provided and non-empty, with 50% probability
    mutates a real accepted program (parameter perturbation).  Otherwise
    generates from scratch using the v1 action families.

    Returns (program, metadata) or None.
    """
    # Try mutation of a real accepted program
    if accepted_programs and rng.random() < 0.5:
        result = _mutate_accepted(rng, accepted_programs, objects, grid)
        if result is not None:
            return result

    # Sample from scratch: 1 uniform action applied to all objects
    sampled = _sample_action(rng, objects, grid)
    if sampled is None:
        return None
    delta_type, params, family_tag = sampled

    # Build the ObjectProgram: one rule with selector "true" (all objects)
    selector = SelectorRule(
        predicate=PredExpr(op="true", args=()),
        literals=0,
    )
    action = ActionRule(
        delta_type=delta_type,
        params=params,
        parameter_class=ParameterClass.CONSTANT,
    )
    rule = ObjectRule(selector=selector, action=action)
    default_action = ActionRule(delta_type=DeltaType.KEEP)

    program = ObjectProgram(
        segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
        rules=[rule],
        default_action=default_action,
        output_spec=OutputSpec(mode="same_as_input"),
    )

    meta = {
        "source": "v1_scratch",
        "family": family_tag,
        "action_kinds": [delta_type.value],
        "param_classes": ["constant"],
        "n_rules": 1,
        "selector_type": "all",
    }
    return program, meta


def _mutate_accepted(rng: np.random.Generator, accepted: list[dict],
                     objects: list[ARCObject], grid: Grid,
                     ) -> Optional[tuple[ObjectProgram, dict]]:
    """Pick a random accepted program and mutate its constant parameters.

    Only mutates programs whose rules use actions in the v1-covered set
    (translate/recolor/reflect/rotate/scale/delete/grow).
    """
    v1_deltas = {
        "translate", "recolor", "reflect", "rotate", "scale", "delete",
        "keep", "grow",
    }

    # Filter to v1-compatible programs
    candidates = []
    for prog_dict in accepted:
        rules = prog_dict.get("rules", [])
        if not rules:
            continue
        all_v1 = all(r.get("action", {}).get("delta_type", "") in v1_deltas
                     for r in rules)
        if all_v1 and prog_dict.get("output_spec", {}).get("mode") == "same_as_input":
            candidates.append(prog_dict)

    if not candidates:
        return None

    chosen = candidates[int(rng.integers(len(candidates)))]

    try:
        program = ObjectProgram.from_dict(chosen)
    except Exception:
        return None

    # Mutate parameters: for each rule, perturb constants
    mutated_kinds = []
    for rule in program.rules:
        action = rule.action
        mutated_kinds.append(action.delta_type.value)
        new_params = {}
        for pname, expr in action.params.items():
            new_params[pname] = _perturb_expr(rng, expr)
        action.params.clear()
        action.params.update(new_params)

    # Deduplicate the family tag (e.g. grow_grow_grow -> grow_x3)
    kind_counts = Counter(mutated_kinds)
    family_parts = []
    for k, c in sorted(kind_counts.items()):
        family_parts.append(f"{k}_x{c}" if c > 1 else k)
    family_tag = "_".join(family_parts)

    meta = {
        "source": "v1_mutation",
        "family": family_tag,
        "action_kinds": mutated_kinds,
        "param_classes": ["constant"],
        "n_rules": len(program.rules),
        "selector_type": "inherited",
        "mutated_from": chosen.get("segmentation_variant", "?"),
    }
    return program, meta


def _perturb_expr(rng: np.random.Generator, expr) -> Any:
    """Perturb constant-valued expression leaves.  Returns a new Expr."""
    if isinstance(expr, VecExpr) and expr.op == "const":
        dr, dc = expr.args
        dr = int(dr) + int(rng.integers(-2, 3))
        dc = int(dc) + int(rng.integers(-2, 3))
        if dr == 0 and dc == 0:
            dr = int(rng.choice([-1, 1]))
        return VecExpr(op="const", args=(dr, dc))
    if isinstance(expr, ColorExpr) and expr.op == "const":
        return ColorExpr(op="const", args=(int(rng.integers(0, 10)),))
    if isinstance(expr, ScalarExpr) and expr.op == "const":
        v = int(expr.args[0])
        v = max(1, v + int(rng.integers(-1, 2)))
        return ScalarExpr(op="const", args=(v,))
    if isinstance(expr, AxisExpr) and expr.op == "const":
        return AxisExpr(op="const", args=(str(rng.choice(["horizontal", "vertical"])),))
    if isinstance(expr, AngleExpr) and expr.op == "const":
        return AngleExpr(op="const", args=(int(rng.choice([90, 180, 270])),))
    # non-const expressions: return as-is (feature/relational expressions
    # would need scene-aware perturbation, deferred to v2)
    return expr


# ---------------------------------------------------------------------------
# 3. Rendering via the engine
# ---------------------------------------------------------------------------

def render_task_pair(program: ObjectProgram, grid: Grid
                     ) -> Optional[tuple[list[list[int]], list[list[int]]]]:
    """Apply program to grid, return (input_list, output_list) or None on failure."""
    try:
        output_grid = render_program(program, grid)
    except (EvalError, Exception):
        return None

    inp = grid.to_list()
    out = output_grid.to_list()

    # Degenerate filter
    if inp == out:
        return None
    if not out or not out[0]:
        return None
    return inp, out


# ---------------------------------------------------------------------------
# 4. Task assembly
# ---------------------------------------------------------------------------

def _load_accepted_programs(project_root: Path) -> list[dict]:
    """Load all persisted accepted program dicts from outputs/*/programs/*.json."""
    programs = []
    patterns = [
        str(project_root / "outputs" / "*" / "programs" / "*.json"),
        str(project_root / "outputs" / "*" / "*" / "programs" / "*.json"),
    ]
    seen_paths = set()
    for pattern in patterns:
        for path in glob.glob(pattern):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            try:
                with open(path) as f:
                    programs.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
    return programs


def make_task(rng: np.random.Generator,
              accepted_programs: list[dict] | None = None,
              ) -> Optional[tuple[dict, dict]]:
    """One synthetic ARC task: 2-4 train pairs + 1 test pair from one program.

    Returns (task_dict, metadata) or None.
    task_dict has keys "train" and "test", each a list of
    {"input": [[int]], "output": [[int]]}.
    """
    n_train = int(rng.integers(2, 5))
    n_total = n_train + 1

    # Sample a program once, then apply to multiple scenes
    # We need the program to succeed on all scenes, so sample scenes and
    # program together.
    for _global_attempt in range(20):
        # Sample first scene to pick program
        grid0, objects0 = sample_scene(rng)
        result = sample_program(rng, objects0, grid0, accepted_programs)
        if result is None:
            continue
        program, meta = result

        # Render first pair
        pair0 = render_task_pair(program, grid0)
        if pair0 is None:
            continue

        # Render remaining pairs
        pairs = [pair0]
        fail = False
        for _ in range(n_total - 1):
            for _scene_attempt in range(10):
                grid_i, _ = sample_scene(rng)
                pair_i = render_task_pair(program, grid_i)
                if pair_i is not None:
                    pairs.append(pair_i)
                    break
            else:
                fail = True
                break
        if fail or len(pairs) < n_total:
            continue

        # Assemble the task dict
        train = [{"input": p[0], "output": p[1]} for p in pairs[:n_train]]
        test = [{"input": p[0], "output": p[1]} for p in pairs[n_train:]]

        task_dict = {"train": train, "test": test}
        meta["n_train"] = n_train
        meta["program_dict"] = program.to_dict()
        return task_dict, meta

    return None


# ---------------------------------------------------------------------------
# 5. CLI
# ---------------------------------------------------------------------------

def generate_tasks(n: int, seed: int, outpath: str,
                   project_root: Path | None = None) -> list[dict]:
    """Generate N tasks and write to JSONL.  Returns list of metadata dicts."""
    if project_root is None:
        project_root = _PROJECT_ROOT

    accepted = _load_accepted_programs(project_root)
    print(f"[dream] loaded {len(accepted)} accepted programs from disk")

    rng = np.random.default_rng(seed)
    metas = []
    generated = 0
    attempts = 0
    max_attempts = n * 50  # generous budget

    with open(outpath, "w") as f:
        while generated < n and attempts < max_attempts:
            attempts += 1
            result = make_task(rng, accepted)
            if result is None:
                continue
            task_dict, meta = result
            line = json.dumps({"task": task_dict, "meta": meta})
            f.write(line + "\n")
            metas.append(meta)
            generated += 1

    print(f"[dream] generated {generated}/{n} tasks in {attempts} attempts "
          f"(success rate {generated/max(1,attempts)*100:.1f}%)")
    return metas


def smoke_test(project_root: Path | None = None) -> bool:
    """Generate 50 tasks, verify consistency, print diagnostics."""
    import tempfile
    if project_root is None:
        project_root = _PROJECT_ROOT

    print("=" * 60)
    print("SMOKE TEST: generating 50 synthetic ARC tasks")
    print("=" * 60)

    t0 = time.time()
    outpath = str(Path(tempfile.gettempdir()) / "dream_smoke.jsonl")
    metas = generate_tasks(50, seed=42, outpath=outpath, project_root=project_root)
    elapsed = time.time() - t0
    print(f"\nGenerated {len(metas)} tasks in {elapsed:.1f}s")

    if len(metas) == 0:
        print("FAIL: no tasks generated")
        return False

    # Action-kind distribution
    kind_counter: Counter = Counter()
    family_counter: Counter = Counter()
    source_counter: Counter = Counter()
    for m in metas:
        for k in m.get("action_kinds", []):
            kind_counter[k] += 1
        family_counter[m.get("family", "unknown")] += 1
        source_counter[m.get("source", "unknown")] += 1

    print("\n--- Action-kind distribution ---")
    for k, v in kind_counter.most_common():
        print(f"  {k}: {v}")

    print("\n--- Family distribution ---")
    for k, v in family_counter.most_common():
        print(f"  {k}: {v}")

    print("\n--- Source distribution ---")
    for k, v in source_counter.most_common():
        print(f"  {k}: {v}")

    # Consistency check: for each task, verify that rendering the program
    # on each train input reproduces the train output.
    print("\n--- Consistency check ---")
    n_consistent = 0
    n_checked = 0
    with open(outpath) as f:
        for line in f:
            record = json.loads(line)
            task = record["task"]
            meta = record["meta"]
            prog_dict = meta.get("program_dict")
            if prog_dict is None:
                continue
            try:
                program = ObjectProgram.from_dict(prog_dict)
            except Exception as e:
                print(f"  FAIL deserialize: {e}")
                continue

            all_ok = True
            for pair in task["train"]:
                inp = Grid.from_list(pair["input"])
                expected = pair["output"]
                try:
                    actual = render_program(program, inp).to_list()
                except Exception:
                    all_ok = False
                    break
                if actual != expected:
                    all_ok = False
                    break

            # Also check test pairs
            for pair in task["test"]:
                inp = Grid.from_list(pair["input"])
                expected = pair["output"]
                try:
                    actual = render_program(program, inp).to_list()
                except Exception:
                    all_ok = False
                    break
                if actual != expected:
                    all_ok = False
                    break

            n_checked += 1
            if all_ok:
                n_consistent += 1

    print(f"  {n_consistent}/{n_checked} tasks fully consistent")

    # JSON round-trip check
    print("\n--- JSON round-trip check ---")
    n_roundtrip = 0
    with open(outpath) as f:
        for line in f:
            record = json.loads(line)
            prog_dict = record["meta"].get("program_dict")
            if prog_dict is None:
                continue
            try:
                p = ObjectProgram.from_dict(prog_dict)
                rt = p.to_dict()
                p2 = ObjectProgram.from_dict(rt)
                assert p2.to_dict() == rt, "round-trip mismatch"
                n_roundtrip += 1
            except Exception as e:
                print(f"  FAIL: {e}")
    print(f"  {n_roundtrip}/{len(metas)} programs round-trip OK")

    # Grammar coverage
    all_deltas = set(dt.value for dt in DeltaType)
    covered = set(kind_counter.keys())
    uncovered = all_deltas - covered
    coverage = len(covered) / len(all_deltas) * 100

    print(f"\n--- Grammar coverage ---")
    print(f"  DeltaType coverage: {len(covered)}/{len(all_deltas)} "
          f"({coverage:.0f}%)")
    print(f"  Covered: {sorted(covered)}")
    print(f"  Uncovered: {sorted(uncovered)}")

    success = (n_consistent == n_checked and n_checked > 0
               and n_roundtrip == len(metas))
    print(f"\n{'PASS' if success else 'FAIL'}: smoke test "
          f"({'all checks passed' if success else 'some checks failed'})")
    print("=" * 60)
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Helmholtz synthetic ARC task generator")
    parser.add_argument("--smoke", action="store_true",
                        help="Run smoke test (50 tasks)")
    parser.add_argument("n", nargs="?", type=int, default=None,
                        help="Number of tasks to generate")
    parser.add_argument("seed", nargs="?", type=int, default=0,
                        help="Random seed")
    parser.add_argument("outpath", nargs="?", type=str, default="out.jsonl",
                        help="Output JSONL path")
    args = parser.parse_args()

    if args.smoke:
        ok = smoke_test()
        sys.exit(0 if ok else 1)

    if args.n is None:
        parser.error("specify N (number of tasks) or --smoke")

    metas = generate_tasks(args.n, args.seed, args.outpath)
    kind_counter: Counter = Counter()
    for m in metas:
        for k in m.get("action_kinds", []):
            kind_counter[k] += 1
    print("\nAction-kind distribution:")
    for k, v in kind_counter.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
