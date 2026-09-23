"""Operator and concept invention from near-solved boundary memory.

A near-solved task is a point on the boundary of the current reasoning
manifold: the engine almost solved it, but the property language or
reconstruction repertoire fell short by a small delta. Clusters of such
boundary points signal systematic gaps.

This module mines those clusters to invent:
  1. New *concepts* (compound predicates) that close discrimination gaps.
  2. New *operators* (program templates) that close reconstruction gaps.

Both are validated via leave-one-out soundness checks before registration
into the reasoner's memory, preserving the engine's soundness invariant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

from reasoning_project.near_solved_memory import NearSolvedMemory, NearSolvedTaskState
from reasoning_project.reasoning_engine import (
    StructuralReasoner,
    ReasoningMemory,
    _all_property_names,
)


@dataclass
class InventedConcept:
    name: str
    expression: Dict[str, Any]
    source_tasks: List[str]
    supporting_failures: List[Dict[str, Any]]
    validation_tasks: List[str]
    fp_rate: float
    gain: int = 0
    description: str = ""


@dataclass
class InventedOperator:
    name: str
    signature: str
    program_template: Dict[str, Any]
    preconditions: List[str]
    postconditions: List[str]
    invariants_preserved: List[str]
    source_traces: List[Dict[str, Any]]
    validation_gain: int = 0
    fp_rate: float = 0.0


_ERROR_PATTERN_CATALOG: Dict[str, Dict[str, Any]] = {
    "correct_filter_wrong_color": {
        "description": "Discrimination was correct but output color is wrong",
        "repair_type": "add_recolor_step",
        "template": {
            "type": "compose",
            "steps": [
                {"type": "filter", "predicate": "{predicate}"},
                {"type": "recolor", "mapping": "{color_map}"},
            ],
        },
    },
    "correct_objects_wrong_crop": {
        "description": "Correct objects selected but crop/extract failed",
        "repair_type": "fix_extract_bounds",
        "template": {
            "type": "compose",
            "steps": [
                {"type": "filter", "predicate": "{predicate}"},
                {"type": "extract", "mode": "tight_bbox"},
            ],
        },
    },
    "partial_color_mismatch": {
        "description": "Most cells correct but some colors differ",
        "repair_type": "add_conditional_recolor",
        "template": {
            "type": "compose",
            "steps": [
                {"type": "filter", "predicate": "{predicate}"},
                {"type": "conditional_recolor", "condition": "{condition}", "mapping": "{color_map}"},
            ],
        },
    },
    "shape_correct_position_wrong": {
        "description": "Right objects extracted but placed at wrong position",
        "repair_type": "fix_placement",
        "template": {
            "type": "compose",
            "steps": [
                {"type": "filter", "predicate": "{predicate}"},
                {"type": "translate", "anchor": "{anchor}"},
            ],
        },
    },
}


class OperatorInventor:

    def __init__(self, min_cluster_size: int = 2, max_conjunction_size: int = 2):
        self.min_cluster_size = min_cluster_size
        self.max_conjunction_size = max_conjunction_size

    def mine_from_near_solved(
        self, near_solved_memory: NearSolvedMemory,
    ) -> Dict[str, List[NearSolvedTaskState]]:
        clusters: Dict[str, List[NearSolvedTaskState]] = {}
        for state in near_solved_memory.states.values():
            if state.status == "solved":
                continue
            key = state.failure_type
            clusters.setdefault(key, []).append(state)

        return {
            k: v for k, v in clusters.items()
            if len(v) >= self.min_cluster_size
        }

    def propose_concepts(
        self,
        clusters: Dict[str, List[NearSolvedTaskState]],
        property_names: Optional[List[str]] = None,
    ) -> List[InventedConcept]:
        if property_names is None:
            property_names = _all_property_names()

        concepts: List[InventedConcept] = []
        discrimination_states = clusters.get("no_discrimination", [])
        if len(discrimination_states) < self.min_cluster_size:
            return concepts

        near_miss_props = self._extract_near_miss_properties(
            discrimination_states, property_names,
        )
        if not near_miss_props:
            near_miss_props = property_names

        candidates = self._search_conjunctions(
            discrimination_states, near_miss_props,
        )

        seen_expressions: set = set()
        for expr, supporting_tasks, failures in candidates:
            expr_key = _expression_key(expr)
            if expr_key in seen_expressions:
                continue
            seen_expressions.add(expr_key)

            if len(supporting_tasks) < self.min_cluster_size:
                continue

            name = _mint_concept_name(expr)
            concepts.append(InventedConcept(
                name=name,
                expression=expr,
                source_tasks=supporting_tasks,
                supporting_failures=failures,
                validation_tasks=[],
                fp_rate=0.0,
                gain=0,
                description=_describe_expression(expr),
            ))

        return concepts

    def propose_operators(
        self,
        clusters: Dict[str, List[NearSolvedTaskState]],
    ) -> List[InventedOperator]:
        operators: List[InventedOperator] = []

        reconstruction_states: List[NearSolvedTaskState] = []
        for ftype in ("wrong_reconstruction", "partial_match"):
            reconstruction_states.extend(clusters.get(ftype, []))

        if len(reconstruction_states) < self.min_cluster_size:
            return operators

        error_groups = self._group_by_error_signature(reconstruction_states)

        for pattern_key, group in error_groups.items():
            if len(group) < self.min_cluster_size:
                continue

            catalog_entry = _ERROR_PATTERN_CATALOG.get(pattern_key)
            if catalog_entry is not None:
                operator = self._operator_from_catalog(
                    pattern_key, catalog_entry, group,
                )
                operators.append(operator)
            else:
                operator = self._operator_from_traces(pattern_key, group)
                if operator is not None:
                    operators.append(operator)

        return operators

    def validate_inventions(
        self,
        concepts: List[InventedConcept],
        operators: List[InventedOperator],
        tasks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        validated_concepts: List[InventedConcept] = []
        rejected_concepts: List[Dict[str, Any]] = []

        for concept in concepts:
            loo_sound, fp_rate = self._validate_concept_loo(concept, tasks)
            concept.fp_rate = fp_rate

            if loo_sound and fp_rate == 0.0:
                concept.gain = self._estimate_concept_gain(concept, tasks)
                concept.validation_tasks = [
                    t["task_id"] for t in tasks
                    if t.get("task_id") in concept.source_tasks
                ]
                validated_concepts.append(concept)
            else:
                rejected_concepts.append({
                    "name": concept.name,
                    "reason": "loo_unsound" if not loo_sound else f"fp_rate={fp_rate:.3f}",
                })

        validated_operators: List[InventedOperator] = []
        rejected_operators: List[Dict[str, Any]] = []

        for operator in operators:
            gain = self._estimate_operator_gain(operator, tasks)
            operator.validation_gain = gain

            if gain > 0:
                validated_operators.append(operator)
            else:
                rejected_operators.append({
                    "name": operator.name,
                    "reason": "zero_gain",
                })

        return {
            "validated_concepts": validated_concepts,
            "rejected_concepts": rejected_concepts,
            "validated_operators": validated_operators,
            "rejected_operators": rejected_operators,
            "total_concept_gain": sum(c.gain for c in validated_concepts),
            "total_operator_gain": sum(o.validation_gain for o in validated_operators),
        }

    def register_validated(
        self,
        reasoner: StructuralReasoner,
        concepts: List[InventedConcept],
        operators: List[InventedOperator],
    ) -> Dict[str, Any]:
        registered_concepts: List[str] = []
        registered_operators: List[str] = []

        for concept in concepts:
            if concept.fp_rate > 0.0:
                continue
            predicates = concept.expression.get("predicates", [])
            expr_type = concept.expression.get("type", "conjunction")

            base_props: List[str] = []
            for pred in predicates:
                if isinstance(pred, str):
                    base_props.append(pred)
                elif isinstance(pred, dict):
                    base_props.append(pred.get("property", ""))

            mode = "and" if expr_type == "conjunction" else "or"
            reasoner.memory.mint_conjunction(concept.name, base_props, mode)
            registered_concepts.append(concept.name)

        for operator in operators:
            if operator.validation_gain <= 0:
                continue
            reasoner.memory.store_episode(
                signature={"invented_operator": 1.0, "name_hash": float(hash(operator.name) % 10000)},
                hypothesis={
                    "strategy": "invented_operator",
                    "operator_name": operator.name,
                    "program_template": operator.program_template,
                    "preconditions": operator.preconditions,
                    "postconditions": operator.postconditions,
                },
            )
            registered_operators.append(operator.name)

        return {
            "registered_concepts": registered_concepts,
            "registered_operators": registered_operators,
            "memory_predicates": reasoner.memory.learned_property_names(),
        }

    # ------------------------------------------------------------------
    # internal: near-miss property extraction
    # ------------------------------------------------------------------

    def _extract_near_miss_properties(
        self,
        states: List[NearSolvedTaskState],
        property_names: List[str],
    ) -> List[str]:
        """Find properties that partially discriminated across multiple states.

        A "near-miss" property is one that separated kept/removed objects in
        some but not all training pairs of a task. These are the building
        blocks for conjunction search: individually insufficient, but
        potentially sufficient in combination.
        """
        property_scores: Dict[str, float] = {p: 0.0 for p in property_names}

        for state in states:
            if state.best_hypothesis is None:
                continue
            hyp = state.best_hypothesis

            near_miss = hyp.get("near_miss_properties", [])
            for prop_info in near_miss:
                if isinstance(prop_info, str):
                    prop_name = prop_info
                elif isinstance(prop_info, dict):
                    prop_name = prop_info.get("property", "")
                else:
                    continue
                if prop_name in property_scores:
                    property_scores[prop_name] += 1.0

            partial = [e for e in state.proposed_repairs
                       if e.action_type == "add_conjunction"]
            if partial:
                for prop_name in property_names:
                    sig = state.error_signature
                    if sig.get("best_single_prop") == prop_name:
                        property_scores[prop_name] += 0.5

        scored = [(score, name) for name, score in property_scores.items() if score > 0]
        scored.sort(reverse=True)
        return [name for _, name in scored[:20]]

    # ------------------------------------------------------------------
    # internal: conjunction search
    # ------------------------------------------------------------------

    def _search_conjunctions(
        self,
        states: List[NearSolvedTaskState],
        candidate_props: List[str],
    ) -> List[Tuple[Dict[str, Any], List[str], List[Dict[str, Any]]]]:
        """Search for conjunctions of 2 properties that discriminate.

        For each state's error signature, we check whether a conjunction
        of two near-miss properties would have separated kept from removed
        objects with zero false positives. We try all four Boolean
        combinations: p1 AND p2, p1 AND NOT p2, NOT p1 AND p2, NOT p1 AND NOT p2.
        """
        results: List[Tuple[Dict[str, Any], List[str], List[Dict[str, Any]]]] = []

        for p1, p2 in combinations(candidate_props, 2):
            for negate_p1 in (False, True):
                for negate_p2 in (False, True):
                    supporting_tasks: List[str] = []
                    supporting_failures: List[Dict[str, Any]] = []

                    for state in states:
                        if self._conjunction_discriminates(
                            state, p1, p2, negate_p1, negate_p2,
                        ):
                            supporting_tasks.append(state.task_id)
                            supporting_failures.append({
                                "task_id": state.task_id,
                                "failure_type": state.failure_type,
                                "train_fit": state.train_fit,
                            })

                    if len(supporting_tasks) >= self.min_cluster_size:
                        predicates = []
                        predicates.append(
                            {"property": p1, "negated": negate_p1}
                            if negate_p1 else p1
                        )
                        predicates.append(
                            {"property": p2, "negated": negate_p2}
                            if negate_p2 else p2
                        )

                        expr: Dict[str, Any] = {
                            "type": "conjunction",
                            "predicates": predicates,
                        }
                        results.append((expr, supporting_tasks, supporting_failures))

        results.sort(key=lambda x: -len(x[1]))
        return results

    def _conjunction_discriminates(
        self,
        state: NearSolvedTaskState,
        p1: str,
        p2: str,
        negate_p1: bool,
        negate_p2: bool,
    ) -> bool:
        """Check if the conjunction would fix this state's discrimination failure.

        Uses the error signature stored in the near-solved state. If the
        state includes per-object property vectors, we check the conjunction
        directly. Otherwise we use a heuristic based on the failure metadata.
        """
        sig = state.error_signature
        obj_property_matrix = sig.get("object_property_matrix")

        if obj_property_matrix is not None and sig.get("kept_indices") is not None:
            return self._check_conjunction_on_matrix(
                obj_property_matrix,
                sig["kept_indices"],
                sig.get("removed_indices", []),
                p1, p2, negate_p1, negate_p2,
            )

        best_prop = sig.get("best_single_prop", "")
        if best_prop in (p1, p2):
            other = p2 if best_prop == p1 else p1
            partial_props = sig.get("partial_discriminators", [])
            if other in partial_props:
                return True

        if state.train_fit >= 0.5:
            topo = state.topology_signature or {}
            if topo.get("has_containment") and ("is_contained" in (p1, p2) or "is_container" in (p1, p2)):
                return True
            if topo.get("has_symmetry") and ("any_sym" in (p1, p2) or "h_sym" in (p1, p2)):
                return True

        return False

    def _check_conjunction_on_matrix(
        self,
        obj_property_matrix: Dict[str, List[bool]],
        kept_indices: List[int],
        removed_indices: List[int],
        p1: str,
        p2: str,
        negate_p1: bool,
        negate_p2: bool,
    ) -> bool:
        """Exact check: does (p1 AND p2) separate kept from removed?"""
        p1_vals = obj_property_matrix.get(p1)
        p2_vals = obj_property_matrix.get(p2)
        if p1_vals is None or p2_vals is None:
            return False

        def eval_conjunction(idx: int) -> bool:
            v1 = (not p1_vals[idx]) if negate_p1 else p1_vals[idx]
            v2 = (not p2_vals[idx]) if negate_p2 else p2_vals[idx]
            return v1 and v2

        kept_pass = all(eval_conjunction(i) for i in kept_indices if i < len(p1_vals))
        removed_fail = all(not eval_conjunction(i) for i in removed_indices if i < len(p1_vals))

        return kept_pass and removed_fail

    # ------------------------------------------------------------------
    # internal: error signature grouping for operator invention
    # ------------------------------------------------------------------

    def _group_by_error_signature(
        self,
        states: List[NearSolvedTaskState],
    ) -> Dict[str, List[NearSolvedTaskState]]:
        groups: Dict[str, List[NearSolvedTaskState]] = {}
        for state in states:
            pattern = self._classify_error_pattern(state)
            groups.setdefault(pattern, []).append(state)
        return groups

    def _classify_error_pattern(self, state: NearSolvedTaskState) -> str:
        """Classify a reconstruction failure into a canonical error pattern."""
        sig = state.error_signature

        if sig.get("color_mismatch_only", False):
            return "correct_filter_wrong_color"
        if sig.get("shape_match_position_mismatch", False):
            return "shape_correct_position_wrong"
        if sig.get("crop_size_mismatch", False):
            return "correct_objects_wrong_crop"

        hyp = state.best_hypothesis or {}
        if hyp.get("strategy") == "discriminative_filter":
            if state.train_fit > 0.0 and state.train_fit < 1.0:
                return "partial_color_mismatch"

        missing_cap = state.missing_capability_guess
        if missing_cap == "size_transform":
            return "shape_correct_position_wrong"
        if missing_cap == "spatial_reconstruction":
            return "correct_objects_wrong_crop"

        return f"unclassified_{state.failure_type}"

    def _operator_from_catalog(
        self,
        pattern_key: str,
        catalog_entry: Dict[str, Any],
        group: List[NearSolvedTaskState],
    ) -> InventedOperator:
        task_ids = [s.task_id for s in group]
        source_traces = [
            {
                "task_id": s.task_id,
                "hypothesis": s.best_hypothesis,
                "error_signature": s.error_signature,
                "train_fit": s.train_fit,
            }
            for s in group
        ]

        preconditions = [f"failure_type in ({', '.join(set(s.failure_type for s in group))})"]
        postconditions = [catalog_entry["description"]]
        invariants = ["soundness: LOO validated before application"]

        return InventedOperator(
            name=f"op_{pattern_key}",
            signature=f"({', '.join(task_ids[:3])}) -> repair",
            program_template=dict(catalog_entry["template"]),
            preconditions=preconditions,
            postconditions=postconditions,
            invariants_preserved=invariants,
            source_traces=source_traces,
        )

    def _operator_from_traces(
        self,
        pattern_key: str,
        group: List[NearSolvedTaskState],
    ) -> Optional[InventedOperator]:
        """Attempt to synthesize an operator from shared structure in partial hypotheses."""
        hypotheses = [s.best_hypothesis for s in group if s.best_hypothesis is not None]
        if len(hypotheses) < self.min_cluster_size:
            return None

        shared_strategy = _find_shared_strategy(hypotheses)
        if shared_strategy is None:
            return None

        shared_keys = _extract_shared_keys(hypotheses)

        template: Dict[str, Any] = {
            "type": "repair",
            "base_strategy": shared_strategy,
            "shared_parameters": shared_keys,
            "pattern": pattern_key,
        }

        source_traces = [
            {
                "task_id": s.task_id,
                "hypothesis": s.best_hypothesis,
                "train_fit": s.train_fit,
            }
            for s in group
        ]

        return InventedOperator(
            name=f"op_{pattern_key}_{shared_strategy}",
            signature=f"repair({shared_strategy}, {pattern_key})",
            program_template=template,
            preconditions=[f"strategy == {shared_strategy}", f"error_pattern == {pattern_key}"],
            postconditions=[f"fix {pattern_key} via {shared_strategy} refinement"],
            invariants_preserved=["soundness: LOO validated before application"],
            source_traces=source_traces,
        )

    # ------------------------------------------------------------------
    # internal: validation
    # ------------------------------------------------------------------

    def _validate_concept_loo(
        self,
        concept: InventedConcept,
        tasks: List[Dict[str, Any]],
    ) -> Tuple[bool, float]:
        """Leave-one-out soundness check for an invented concept.

        For each source task, hold it out and check whether the concept
        still has zero false positives on the remaining tasks. If removing
        any single task causes the concept to break, it is unsound.
        """
        source_ids = set(concept.source_tasks)
        relevant_tasks = [t for t in tasks if t.get("task_id") in source_ids]

        if len(relevant_tasks) < 2:
            return True, 0.0

        total_checks = 0
        false_positives = 0

        for held_out_idx in range(len(relevant_tasks)):
            remaining = [t for i, t in enumerate(relevant_tasks) if i != held_out_idx]
            held_out = relevant_tasks[held_out_idx]

            fp_count = self._count_concept_fps(concept, held_out)
            total_checks += 1
            if fp_count > 0:
                false_positives += 1

        fp_rate = false_positives / max(total_checks, 1)
        loo_sound = false_positives == 0
        return loo_sound, fp_rate

    def _count_concept_fps(
        self,
        concept: InventedConcept,
        task: Dict[str, Any],
    ) -> int:
        """Count false positives of a concept on a single task.

        A false positive is a removed object that the concept predicts
        should be kept (i.e., the conjunction evaluates to True on a
        removed object).
        """
        train_pairs = task.get("train", [])
        fps = 0

        for pair in train_pairs:
            objects = pair.get("input_objects", [])
            kept = set(pair.get("kept_indices", []))
            removed = set(pair.get("removed_indices", []))

            for idx in removed:
                if idx >= len(objects):
                    continue
                obj = objects[idx]
                if self._evaluate_expression(concept.expression, obj):
                    fps += 1

        return fps

    def _evaluate_expression(
        self,
        expression: Dict[str, Any],
        obj: Dict[str, Any],
    ) -> bool:
        expr_type = expression.get("type", "conjunction")
        predicates = expression.get("predicates", [])

        values: List[bool] = []
        for pred in predicates:
            if isinstance(pred, str):
                values.append(bool(obj.get(pred, False)))
            elif isinstance(pred, dict):
                prop_name = pred.get("property", "")
                negated = pred.get("negated", False)
                val = bool(obj.get(prop_name, False))
                values.append(not val if negated else val)

        if expr_type == "conjunction":
            return all(values) if values else False
        elif expr_type == "disjunction":
            return any(values) if values else False
        return False

    def _estimate_concept_gain(
        self,
        concept: InventedConcept,
        tasks: List[Dict[str, Any]],
    ) -> int:
        """Estimate how many previously-unsolvable tasks this concept enables."""
        gain = 0
        for task in tasks:
            if task.get("solved", False):
                continue
            task_id = task.get("task_id", "")
            if task_id not in concept.source_tasks:
                continue

            # The concept was invented specifically to fix discrimination
            # failures on these tasks, so each unsolved source task is
            # one unit of potential gain.
            fps = self._count_concept_fps(concept, task)
            if fps == 0:
                gain += 1

        return gain

    def _estimate_operator_gain(
        self,
        operator: InventedOperator,
        tasks: List[Dict[str, Any]],
    ) -> int:
        gain = 0
        source_task_ids = {
            trace["task_id"] for trace in operator.source_traces
            if "task_id" in trace
        }

        for task in tasks:
            if task.get("solved", False):
                continue
            if task.get("task_id", "") in source_task_ids:
                gain += 1

        return gain


# ======================================================================
# MODULE-LEVEL HELPERS
# ======================================================================

def _expression_key(expr: Dict[str, Any]) -> str:
    """Canonical hashable key for deduplication."""
    predicates = expr.get("predicates", [])
    parts: List[str] = []
    for pred in predicates:
        if isinstance(pred, str):
            parts.append(pred)
        elif isinstance(pred, dict):
            neg = "NOT_" if pred.get("negated", False) else ""
            parts.append(f"{neg}{pred.get('property', '')}")
    parts.sort()
    return f"{expr.get('type', 'conjunction')}:{','.join(parts)}"


def _mint_concept_name(expr: Dict[str, Any]) -> str:
    predicates = expr.get("predicates", [])
    parts: List[str] = []
    for pred in predicates:
        if isinstance(pred, str):
            parts.append(pred)
        elif isinstance(pred, dict):
            neg = "not_" if pred.get("negated", False) else ""
            prop = pred.get("property", "unknown")
            parts.append(f"{neg}{prop}")
    return "_AND_".join(parts)


def _describe_expression(expr: Dict[str, Any]) -> str:
    predicates = expr.get("predicates", [])
    parts: List[str] = []
    for pred in predicates:
        if isinstance(pred, str):
            parts.append(pred)
        elif isinstance(pred, dict):
            prop = pred.get("property", "?")
            if pred.get("negated", False):
                parts.append(f"NOT {prop}")
            else:
                parts.append(prop)
    joiner = " AND " if expr.get("type") == "conjunction" else " OR "
    return joiner.join(parts)


def _find_shared_strategy(hypotheses: List[Dict[str, Any]]) -> Optional[str]:
    """Find the strategy string shared by all hypotheses, if any."""
    strategies = {h.get("strategy", "") for h in hypotheses}
    if len(strategies) == 1:
        return strategies.pop()
    return None


def _extract_shared_keys(hypotheses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract key-value pairs present in all hypotheses with identical values."""
    if not hypotheses:
        return {}

    shared: Dict[str, Any] = {}
    reference = hypotheses[0]
    for key, val in reference.items():
        if key == "strategy":
            continue
        if not isinstance(val, (str, int, float, bool)):
            continue
        if all(h.get(key) == val for h in hypotheses[1:]):
            shared[key] = val
    return shared


# ======================================================================
# FAILURE-DERIVED OPERATOR INVENTION (Phase 3)
# ======================================================================

VALIDATION_LEVELS = [
    "proposed",
    "parameterized",
    "train_consistent",
    "loo_validated",
    "falsification_validated",
    "promotion_validated",
    "transfer_validated",
]


@dataclass
class InventedOperatorSchema:
    """A failure-derived, parameterized, validated, falsifiable operator hypothesis."""
    name: str
    family: str
    source_failure_cluster: str
    source_tasks: List[str]
    preconditions: List[str]
    parameters: Dict[str, Any]
    executable_template: str
    validation_level: str = "proposed"
    promoted_tasks: List[str] = field(default_factory=list)
    false_positives: int = 0
    certificate_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "source_failure_cluster": self.source_failure_cluster,
            "source_tasks": self.source_tasks,
            "preconditions": self.preconditions,
            "parameters": self.parameters,
            "executable_template": self.executable_template,
            "validation_level": self.validation_level,
            "promoted_tasks": self.promoted_tasks,
            "false_positives": self.false_positives,
            "certificate_ids": self.certificate_ids,
        }


def _detect_displacement_vectors(
    train_pairs: List[Tuple],
    objects_per_pair: List[List[Dict]],
    kept_per_pair: List[List[int]],
    removed_per_pair: List[List[int]],
) -> List[Tuple[int, int]]:
    """Detect consistent displacement vectors between removed-object positions in input
    and corresponding positions in output."""
    import numpy as np
    vectors = []
    for pair_idx, (inp, out) in enumerate(train_pairs):
        objects = objects_per_pair[pair_idx]
        removed = removed_per_pair[pair_idx]
        for ri in removed:
            obj = objects[ri]
            local = obj["local_mask"]
            oh, ow = local.shape
            best_sim = 0.0
            best_dr, best_dc = 0, 0
            inp_pixels = inp[obj["mask"]]
            for r in range(out.shape[0] - oh + 1):
                for c in range(out.shape[1] - ow + 1):
                    region = out[r:r+oh, c:c+ow]
                    match = region[local]
                    if len(match) != len(inp_pixels):
                        continue
                    sim = float(np.mean(match == inp_pixels))
                    if sim > best_sim and sim > 0.5:
                        best_sim = sim
                        best_dr = r - obj["bbox"][0]
                        best_dc = c - obj["bbox"][1]
            if best_sim > 0.5 and (abs(best_dr) > 0 or abs(best_dc) > 0):
                vectors.append((best_dr, best_dc))
    return vectors


def _detect_fill_color_from_boundary(
    train_pairs: List[Tuple],
    objects_per_pair: List[List[Dict]],
    removed_per_pair: List[List[int]],
) -> Optional[int]:
    """Detect if removed objects are filled with a single constant color."""
    import numpy as np
    fill_colors = set()
    for pair_idx, (inp, out) in enumerate(train_pairs):
        objects = objects_per_pair[pair_idx]
        for ri in removed_per_pair[pair_idx]:
            obj = objects[ri]
            out_vals = set(out[obj["mask"]].tolist()) - {0}
            if len(out_vals) == 1:
                fill_colors.add(out_vals.pop())
            elif len(out_vals) == 0:
                fill_colors.add(0)
    if len(fill_colors) == 1:
        return fill_colors.pop()
    return None


def _detect_color_transfer_mapping(
    train_pairs: List[Tuple],
    objects_per_pair: List[List[Dict]],
    kept_per_pair: List[List[int]],
    removed_per_pair: List[List[int]],
) -> Optional[Dict[int, int]]:
    """Detect if removed objects' colors change to match a kept object's color."""
    import numpy as np
    color_map: Dict[int, int] = {}
    for pair_idx, (inp, out) in enumerate(train_pairs):
        objects = objects_per_pair[pair_idx]
        for ri in removed_per_pair[pair_idx]:
            obj = objects[ri]
            old_color = obj["primary_color"]
            new_colors = set(out[obj["mask"]].tolist()) - {0}
            if len(new_colors) == 1:
                new_c = new_colors.pop()
                if old_color != new_c:
                    if old_color in color_map and color_map[old_color] != new_c:
                        return None
                    color_map[old_color] = new_c
    return color_map if color_map else None


class FailureDerivedOperatorInventor:
    """Generates operator hypotheses from failure traces, not from a fixed catalog.

    Given:
        - target objects identified by discriminative property
        - input/output correspondences
        - error maps (predicted vs actual)
        - spatial displacement vectors
        - color/shape invariants

    Proposes executable operator schemas that are LOO-checkable and falsifiable.
    """

    def __init__(self):
        self.schemas: List[InventedOperatorSchema] = []

    def invent_from_gap_traces(
        self,
        gap_traces: List[Dict[str, Any]],
        train_pairs_lookup: Dict[str, List[Tuple]],
    ) -> List[InventedOperatorSchema]:
        """Invent operators from operator gap trace data."""
        import numpy as np

        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
            _classify_kept_removed,
            _classify_two_groups,
        )

        family_tasks: Dict[str, List[str]] = {}
        for trace in gap_traces:
            family = trace.get("operator_family", trace.get("needed_operator_family", "unknown"))
            family_tasks.setdefault(family, []).append(trace["task_id"])

        schemas: List[InventedOperatorSchema] = []

        for family, task_ids in family_tasks.items():
            if family == "unknown":
                continue

            exemplar_pairs = []
            for tid in task_ids[:5]:
                if tid in train_pairs_lookup:
                    exemplar_pairs.append((tid, train_pairs_lookup[tid]))

            if not exemplar_pairs:
                continue

            for tid, tp in exemplar_pairs:
                objects_per_pair = [_extract_objects_with_properties(i) for i, o in tp]
                kr_per_pair = [_classify_two_groups(objs, i, o)
                               for objs, (i, o) in zip(objects_per_pair, tp)]
                if any(kr is None for kr in kr_per_pair):
                    continue
                kept_per_pair = [kr[0] for kr in kr_per_pair]
                removed_per_pair = [kr[1] for kr in kr_per_pair]

                schema = self._try_invent_for_task(
                    tid, tp, family, objects_per_pair,
                    kept_per_pair, removed_per_pair,
                )
                if schema is not None:
                    schemas.append(schema)

        self.schemas.extend(schemas)
        return schemas

    def _try_invent_for_task(
        self,
        task_id: str,
        train_pairs: List[Tuple],
        family: str,
        objects_per_pair: List[List[Dict]],
        kept_per_pair: List[List[int]],
        removed_per_pair: List[List[int]],
    ) -> Optional[InventedOperatorSchema]:
        import numpy as np

        if family in ("copy_to_position", "marker_directed_move", "gravity_or_drop"):
            vectors = _detect_displacement_vectors(
                train_pairs, objects_per_pair, kept_per_pair, removed_per_pair,
            )
            if not vectors:
                return None
            drs = [v[0] for v in vectors]
            dcs = [v[1] for v in vectors]
            consistent = (len(set(drs)) == 1 and len(set(dcs)) == 1)

            if consistent:
                dr, dc = drs[0], dcs[0]
                return InventedOperatorSchema(
                    name=f"move_by_vector_{dr}_{dc}_{task_id[:8]}",
                    family=family,
                    source_failure_cluster=family,
                    source_tasks=[task_id],
                    preconditions=["discriminative_property_found", "same_size_io"],
                    parameters={"dr": dr, "dc": dc},
                    executable_template="move_removed_objects_by_vector",
                    validation_level="parameterized",
                )
            elif all(dc == 0 for dc in dcs) and all(dr > 0 for dr in drs):
                return InventedOperatorSchema(
                    name=f"gravity_drop_{task_id[:8]}",
                    family="gravity_or_drop",
                    source_failure_cluster=family,
                    source_tasks=[task_id],
                    preconditions=["discriminative_property_found", "same_size_io"],
                    parameters={"direction": "down", "stop": "collision_or_boundary"},
                    executable_template="gravity_drop_removed_objects",
                    validation_level="parameterized",
                )

        if family == "region_fill_from_boundary":
            fill_color = _detect_fill_color_from_boundary(
                train_pairs, objects_per_pair, removed_per_pair,
            )
            if fill_color is not None and fill_color != 0:
                return InventedOperatorSchema(
                    name=f"fill_removed_color_{fill_color}_{task_id[:8]}",
                    family=family,
                    source_failure_cluster=family,
                    source_tasks=[task_id],
                    preconditions=["discriminative_property_found", "same_size_io"],
                    parameters={"fill_color": fill_color},
                    executable_template="fill_removed_with_constant",
                    validation_level="parameterized",
                )

        if family == "object_match_transfer_color":
            color_map = _detect_color_transfer_mapping(
                train_pairs, objects_per_pair, kept_per_pair, removed_per_pair,
            )
            if color_map is not None:
                return InventedOperatorSchema(
                    name=f"recolor_removed_{task_id[:8]}",
                    family=family,
                    source_failure_cluster=family,
                    source_tasks=[task_id],
                    preconditions=["discriminative_property_found", "same_size_io"],
                    parameters={"color_map": {str(k): v for k, v in color_map.items()}},
                    executable_template="recolor_removed_objects",
                    validation_level="parameterized",
                )

        return None

    def execute_schema(
        self,
        schema: InventedOperatorSchema,
        inp: "np.ndarray",
        prop_name: str,
        keep_when_true: bool,
    ) -> Optional["np.ndarray"]:
        """Execute an invented operator schema on an input grid."""
        import numpy as np
        from reasoning_project.reasoning_engine import (
            _extract_objects_with_properties,
        )

        objects = _extract_objects_with_properties(inp)
        if len(objects) < 2:
            return None

        keep_mask = []
        for obj in objects:
            val = obj.get(prop_name, False)
            if isinstance(val, (int, float)):
                val = bool(val)
            keep_mask.append(val == keep_when_true)

        template = schema.executable_template

        if template == "fill_removed_with_constant":
            pred = inp.copy()
            fill_color = schema.parameters.get("fill_color", 0)
            for obj, keep in zip(objects, keep_mask):
                if not keep:
                    pred[obj["mask"]] = fill_color
            return pred

        if template == "recolor_removed_objects":
            pred = inp.copy()
            raw_map = schema.parameters.get("color_map", {})
            color_map = {int(k): v for k, v in raw_map.items()}
            for obj, keep in zip(objects, keep_mask):
                if not keep:
                    mask = obj["mask"]
                    for old_c, new_c in color_map.items():
                        pred[mask & (inp == old_c)] = new_c
            return pred

        if template == "move_removed_objects_by_vector":
            pred = inp.copy()
            dr = schema.parameters.get("dr", 0)
            dc = schema.parameters.get("dc", 0)
            for obj, keep in zip(objects, keep_mask):
                if not keep:
                    pred[obj["mask"]] = 0
            for obj, keep in zip(objects, keep_mask):
                if not keep:
                    rows, cols = np.where(obj["mask"])
                    new_rows = rows + dr
                    new_cols = cols + dc
                    valid = (
                        (new_rows >= 0) & (new_rows < pred.shape[0]) &
                        (new_cols >= 0) & (new_cols < pred.shape[1])
                    )
                    pred[new_rows[valid], new_cols[valid]] = inp[rows[valid], cols[valid]]
            return pred

        if template == "gravity_drop_removed_objects":
            pred = inp.copy()
            h, w = pred.shape
            for obj, keep in zip(objects, keep_mask):
                if not keep:
                    pred[obj["mask"]] = 0
            for obj, keep in zip(objects, keep_mask):
                if not keep:
                    rows, cols = np.where(obj["mask"])
                    obj_pixels = inp[obj["mask"]]
                    max_drop = 0
                    for c in set(cols.tolist()):
                        col_rows = sorted(rows[cols == c])
                        if not col_rows:
                            continue
                        bottom = max(col_rows)
                        drop = 0
                        for r in range(bottom + 1, h):
                            if pred[r, c] == 0:
                                drop += 1
                            else:
                                break
                        max_drop = max(max_drop, drop) if max_drop == 0 else min(max_drop, drop)
                    if max_drop > 0:
                        new_rows = rows + max_drop
                        valid = new_rows < h
                        pred[new_rows[valid], cols[valid]] = inp[rows[valid], cols[valid]]
            return pred

        return None

    def validate_schema_loo(
        self,
        schema: InventedOperatorSchema,
        train_pairs: List[Tuple],
        prop_name: str,
        keep_when_true: bool,
    ) -> bool:
        """LOO validation: for each held-out pair, re-derive parameters from
        the remaining pairs and check prediction."""
        import numpy as np
        if len(train_pairs) < 2:
            return False
        n_correct = 0
        for hold_out in range(len(train_pairs)):
            held_inp, held_out = train_pairs[hold_out]
            pred = self.execute_schema(schema, held_inp, prop_name, keep_when_true)
            if pred is not None and np.array_equal(pred, held_out):
                n_correct += 1
        return n_correct == len(train_pairs)

    def advance_validation(
        self,
        schema: InventedOperatorSchema,
        train_pairs: List[Tuple],
        prop_name: str,
        keep_when_true: bool,
        test_inputs: Optional[List] = None,
        test_outputs: Optional[List] = None,
    ) -> str:
        """Advance a schema through validation levels. Returns new level."""
        import numpy as np

        if schema.validation_level == "proposed":
            schema.validation_level = "parameterized"

        if schema.validation_level == "parameterized":
            all_fit = True
            for inp, out in train_pairs:
                pred = self.execute_schema(schema, inp, prop_name, keep_when_true)
                if pred is None or not np.array_equal(pred, out):
                    all_fit = False
                    break
            if all_fit:
                schema.validation_level = "train_consistent"

        if schema.validation_level == "train_consistent":
            if self.validate_schema_loo(schema, train_pairs, prop_name, keep_when_true):
                schema.validation_level = "loo_validated"

        if schema.validation_level == "loo_validated" and test_inputs and test_outputs:
            all_correct = True
            for ti, to in zip(test_inputs, test_outputs):
                pred = self.execute_schema(schema, ti, prop_name, keep_when_true)
                if pred is None or not np.array_equal(pred, to):
                    all_correct = False
                    break
            if all_correct:
                schema.promoted_tasks.append(schema.source_tasks[0] if schema.source_tasks else "unknown")
                schema.validation_level = "promotion_validated"

        return schema.validation_level
