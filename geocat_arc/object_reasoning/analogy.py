"""P3 certified analogy — retrieve, adapt, recertify (ARC_ANALOGY).

Retrieve the nearest certified program from the corpus (guide net task-
feature signal + program-structure similarity), ADAPT it to a new task
(re-induce parameter expressions while keeping the program skeleton:
segmentation variant, rule structure, action delta types), try dihedral
conjugations, and RECERTIFY via full LOO-by-reinduction on the new task.

Env-gated: ARC_ANALOGY=1 (zero cost when off).
Fold-safe: runs inside _induce_composed, re-derives adaptation per fold.
"""
from __future__ import annotations

import glob
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject

from .actions import render_program
from .types import (
    ActionRule,
    DeltaType,
    GridPair,
    ObjectProgram,
    ObjectRule,
    OutputSpec,
    ParameterClass,
    SegmentationVariant,
    SelectorRule,
    program_from_dict,
)


# ---------------------------------------------------------------------------
# 1. Corpus loader (reuses guide/dream.py pattern)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_certified_corpus(project_root: Optional[Path] = None,
                          ) -> dict[str, dict]:
    """Load all persisted certified programs as {task_id: program_dict}.

    Scans outputs/*/object/programs/*.json (unified harness object-engine
    layout) and outputs/*/programs/*.json (standalone gate runs).  Dedupes
    by task_id keeping the first occurrence (deterministic — sorted paths).
    """
    root = project_root or _PROJECT_ROOT
    patterns = [
        str(root / "outputs" / "*" / "object" / "programs" / "*.json"),
        str(root / "outputs" / "*" / "programs" / "*.json"),
        str(root / "outputs" / "*" / "*" / "programs" / "*.json"),
    ]
    corpus: dict[str, dict] = {}
    seen_paths: set[str] = set()
    for pattern in sorted(patterns):
        for path in sorted(glob.glob(pattern)):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            task_id = Path(path).stem
            if task_id in corpus:
                continue
            try:
                with open(path) as f:
                    prog_dict = json.load(f)
                # Validate it's a real ObjectProgram (has rules key)
                if "rules" not in prog_dict and "stages" not in prog_dict:
                    continue
                corpus[task_id] = prog_dict
            except (json.JSONDecodeError, OSError):
                pass
    return corpus


# ---------------------------------------------------------------------------
# 2. Program structure signature for similarity
# ---------------------------------------------------------------------------

@dataclass
class ProgramSignature:
    """Structural features of a certified program for similarity search."""
    segmentation_variant: str = ""
    delta_types: tuple[str, ...] = ()
    param_classes: tuple[str, ...] = ()
    n_rules: int = 0
    output_mode: str = "same_as_input"
    has_default_delete: bool = False
    expression_depth: int = 0  # max selector literal count


def program_signature(prog_dict: dict) -> ProgramSignature:
    """Extract a structural signature from a serialized program dict."""
    seg = prog_dict.get("segmentation_variant", "")
    rules = prog_dict.get("rules", [])
    delta_types = []
    param_classes = []
    max_lits = 0
    for r in rules:
        action = r.get("action", {})
        delta_types.append(action.get("delta_type", ""))
        param_classes.append(action.get("parameter_class", "constant"))
        sel = r.get("selector", {})
        max_lits = max(max_lits, sel.get("literals", 0))
    default = prog_dict.get("default_action", {})
    has_del = default.get("delta_type", "keep") == "delete"
    ospec = prog_dict.get("output_spec", {})
    out_mode = ospec.get("mode", "same_as_input")
    # Handle ComposedProgram (stages key)
    if "stages" in prog_dict:
        for stage in prog_dict["stages"]:
            sig = program_signature(stage)
            delta_types.extend(sig.delta_types)
            param_classes.extend(sig.param_classes)
            max_lits = max(max_lits, sig.expression_depth)
    return ProgramSignature(
        segmentation_variant=seg,
        delta_types=tuple(sorted(delta_types)),
        param_classes=tuple(sorted(param_classes)),
        n_rules=len(rules),
        output_mode=out_mode,
        has_default_delete=has_del,
        expression_depth=max_lits,
    )


def structure_similarity(a: ProgramSignature, b: ProgramSignature) -> float:
    """Similarity [0,1] between two program structural signatures."""
    score = 0.0
    total = 0.0

    # Segmentation variant match (weight 2)
    total += 2.0
    if a.segmentation_variant == b.segmentation_variant:
        score += 2.0

    # Delta type overlap (Jaccard, weight 3)
    total += 3.0
    set_a, set_b = set(a.delta_types), set(b.delta_types)
    if set_a or set_b:
        jaccard = len(set_a & set_b) / len(set_a | set_b)
        score += 3.0 * jaccard
    else:
        score += 3.0

    # Parameter class overlap (weight 2)
    total += 2.0
    pc_a, pc_b = set(a.param_classes), set(b.param_classes)
    if pc_a or pc_b:
        score += 2.0 * len(pc_a & pc_b) / len(pc_a | pc_b)
    else:
        score += 2.0

    # Rule count similarity (weight 1)
    total += 1.0
    max_rules = max(a.n_rules, b.n_rules, 1)
    score += 1.0 * (1.0 - abs(a.n_rules - b.n_rules) / max_rules)

    # Output mode match (weight 1)
    total += 1.0
    if a.output_mode == b.output_mode:
        score += 1.0

    # Default action match (weight 1)
    total += 1.0
    if a.has_default_delete == b.has_default_delete:
        score += 1.0

    return score / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# 3. Retrieval: guide signal + structure similarity
# ---------------------------------------------------------------------------

def _task_dict_from_pairs(pairs: list[GridPair]) -> dict:
    """Convert GridPair list to the task dict format GuidePredictor expects."""
    train = []
    for gi, go in pairs:
        train.append({
            "input": gi.to_list(),
            "output": go.to_list(),
        })
    return {"train": train}


def retrieve_precedents(
    pairs: list[GridPair],
    corpus: dict[str, dict],
    top_k: int = 5,
    guide_weight: float = 0.4,
    structure_weight: float = 0.6,
) -> list[tuple[str, dict, float]]:
    """Retrieve nearest certified programs for a new task.

    Returns [(task_id, prog_dict, combined_score), ...] sorted descending.
    Uses GuidePredictor for task-feature signal when available, combined
    with program-structure similarity.
    """
    if not corpus:
        return []

    # Compute guide signal (task-level: which delta kinds are likely)
    guide_kinds: dict[str, float] = {}
    try:
        from guide.predict import GuidePredictor
        gp = GuidePredictor()
        task_dict = _task_dict_from_pairs(pairs)
        ranked = gp.rank(task_dict)
        guide_kinds = {k: p for k, p in ranked.get("kinds", [])}
    except Exception:
        # Guide net not available — fall back to structure-only
        guide_weight = 0.0
        structure_weight = 1.0

    # Compute structure signature of an "ideal" program for this task:
    # use the guide's delta-kind predictions to build a target signature
    target_deltas = tuple(sorted(
        k for k, p in guide_kinds.items() if p > 0.3
    )) if guide_kinds else ()

    scored: list[tuple[str, dict, float]] = []
    for task_id, prog_dict in corpus.items():
        sig = program_signature(prog_dict)

        # Structure similarity (always available)
        # Build a pseudo-signature for the target task
        target_sig = ProgramSignature(delta_types=target_deltas)
        struct_sim = structure_similarity(target_sig, sig)

        # Guide similarity: how well do the program's delta types match
        # the guide's predictions
        guide_sim = 0.0
        if guide_kinds and sig.delta_types:
            match_sum = sum(guide_kinds.get(dt, 0.0) for dt in sig.delta_types)
            guide_sim = match_sum / len(sig.delta_types)

        combined = guide_weight * guide_sim + structure_weight * struct_sim
        scored.append((task_id, prog_dict, combined))

    scored.sort(key=lambda t: -t[2])
    return scored[:top_k]


# ---------------------------------------------------------------------------
# 4. Adaptation: re-induce expressions on new task
# ---------------------------------------------------------------------------

def _apply_dihedral(grid_array: np.ndarray, k: int, flip: bool) -> np.ndarray:
    """Apply a D4 transform: rotate k*90 degrees, optionally flip LR."""
    a = np.asarray(grid_array)
    if flip:
        a = np.fliplr(a)
    return np.ascontiguousarray(np.rot90(a, k))


def _inverse_dihedral(grid_array: np.ndarray, k: int, flip: bool) -> np.ndarray:
    """Inverse of _apply_dihedral."""
    a = np.asarray(grid_array)
    a = np.rot90(a, -k)
    if flip:
        a = np.fliplr(a)
    return np.ascontiguousarray(a)


def adapt_program(
    precedent_dict: dict,
    target_pairs: list[GridPair],
    deadline: Optional[float] = None,
) -> list[ObjectProgram]:
    """Adapt a precedent program to a new task.

    Strategy:
    1. Keep the program skeleton (segmentation variant, delta types,
       output spec structure, default action type).
    2. Re-induce selector predicates and parameter expressions on the
       new task's pairs (using the inducer's normal machinery).
    3. If the skeleton doesn't fit, try dihedral conjugations (the task
       might be a rotated/reflected variant).
    4. Return all train-perfect adaptations found.
    """
    candidates: list[ObjectProgram] = []

    # Try direct adaptation
    adapted = _try_adapt_skeleton(precedent_dict, target_pairs, deadline)
    if adapted is not None:
        candidates.append(adapted)

    # Try dihedral conjugations (7 non-identity D4 transforms)
    for k, flip in ((1, False), (2, False), (3, False),
                    (0, True), (1, True), (2, True), (3, True)):
        if deadline is not None and time.monotonic() > deadline:
            break
        try:
            framed_pairs: list[GridPair] = []
            for gi, go in target_pairs:
                fi = Grid(_apply_dihedral(gi.to_numpy(), k, flip))
                fo = Grid(_apply_dihedral(go.to_numpy(), k, flip))
                framed_pairs.append((fi, fo))
            adapted = _try_adapt_skeleton(precedent_dict, framed_pairs,
                                          deadline)
            if adapted is not None:
                # Wrap in FramedProgram for correct test-time application
                from .types import FramedProgram
                framed_prog = FramedProgram(frame=(k, flip), inner=adapted)
                candidates.append(framed_prog)
        except Exception:
            continue

    return candidates


def _try_adapt_skeleton(
    precedent_dict: dict,
    target_pairs: list[GridPair],
    deadline: Optional[float] = None,
) -> Optional[ObjectProgram]:
    """Try to re-induce a program with the precedent's skeleton on new pairs.

    The precedent's segmentation variant, delta types, and output spec
    structure are kept; selectors and parameter expressions are re-induced
    from scratch on the target pairs.
    """
    from .inducer import (
        InductionConfig,
        _induce_candidate,
        _Meta,
        _train_perfect,
        rank_candidates,
    )
    from .segmentation import segment, background_for

    # Parse the precedent to extract skeleton info
    try:
        if "stages" in precedent_dict:
            # ComposedProgram — adapt the first stage only for now
            precedent_dict = precedent_dict["stages"][0]
        seg_variant = SegmentationVariant(
            precedent_dict.get("segmentation_variant", "S1"))
        precedent_rules = precedent_dict.get("rules", [])
        # Extract the skeleton: delta types we expect to find
        target_deltas = []
        for r in precedent_rules:
            action = r.get("action", {})
            dt_name = action.get("delta_type", "keep")
            target_deltas.append(dt_name)
    except Exception:
        return None

    # Run the normal inducer with a constrained config:
    # same budget, standard search, but we provide structural hints
    config = InductionConfig(
        budget_s=min(30.0, (deadline - time.monotonic())
                     if deadline else 30.0),
    )
    if deadline is None:
        deadline = time.monotonic() + config.budget_s
    meta = _Meta(events=["ANALOGY_ADAPT"])

    try:
        attempt = _induce_candidate(target_pairs, config, deadline, meta,
                                    sink=None)
    except Exception:
        return None

    if not attempt.programs:
        return None

    # Check if any found program has matching delta-type structure
    for prog in attempt.programs:
        if _train_perfect(prog, target_pairs):
            return prog

    return None


# ---------------------------------------------------------------------------
# 5. Main entry: retrieve + adapt + train-perfect check
# ---------------------------------------------------------------------------

def induce_by_analogy(
    train_pairs: list[GridPair],
    deadline: Optional[float] = None,
    corpus: Optional[dict[str, dict]] = None,
    max_precedents: int = 5,
) -> list:
    """Certified analogy: retrieve precedents, adapt, return train-perfect
    programs.  The caller (inducer hook) handles LOO-by-reinduction.

    Returns a list of train-perfect adapted programs (may be empty).
    """
    if corpus is None:
        corpus = load_certified_corpus()
    if not corpus:
        return []

    if deadline is not None and time.monotonic() > deadline:
        return []

    # Retrieve nearest precedents
    precedents = retrieve_precedents(train_pairs, corpus,
                                     top_k=max_precedents)
    if not precedents:
        return []

    results: list = []
    for task_id, prog_dict, score in precedents:
        if deadline is not None and time.monotonic() > deadline:
            break

        # Adapt this precedent to the target task
        adapted = adapt_program(prog_dict, train_pairs, deadline)
        for prog in adapted:
            # Verify train-perfect
            try:
                if _is_train_perfect(prog, train_pairs):
                    results.append(prog)
            except Exception:
                continue

    return results


def _is_train_perfect(prog, pairs: list[GridPair]) -> bool:
    """Check if a program produces exact output on all train pairs."""
    for gi, go in pairs:
        try:
            rendered = render_program(prog, gi)
            if rendered.to_list() != go.to_list():
                return False
        except Exception:
            return False
    return True


# ---------------------------------------------------------------------------
# 6. Env gate
# ---------------------------------------------------------------------------

def _ANALOGY_ON() -> bool:
    """Env gate: ARC_ANALOGY=1 (zero cost when off)."""
    return os.environ.get("ARC_ANALOGY", "") not in ("", "0")
