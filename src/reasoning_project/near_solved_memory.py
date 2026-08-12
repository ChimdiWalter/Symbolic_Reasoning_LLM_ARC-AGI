"""Near-Solution Boundary Memory for adaptive structural reasoning.

A failed task is not discarded. The system stores it as a point on the
boundary of the current reasoning manifold, together with its active
chart, best partial hypothesis, failure diagnosis, and repair frontier.
Future reasoning can resume from this point, retrieve nearby solved and
failed trajectories, and either repair the current hypothesis or create
a new chart/adapter when the failure indicates missing representational
capacity.

Key concept: a nearly solved task lies at distance ε from the solution
region S_solved ⊂ M_mem. It is a *boundary point* — not a failure, but
a partial trajectory that can be resumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.manifold_memory import (
    ManifoldPoint,
    MemoryManifold,
    _signature_to_embedding,
    encode_task_signature,
)


# ═══════════════════════════════════════════════════════════════════════════
# NEAR-SOLVED TASK STATE
# ═══════════════════════════════════════════════════════════════════════════

class NearSolvedStatus:
    PARTIAL = "partial"
    NEAR_SOLVED = "near_solved"
    BLOCKED = "blocked"
    SOLVED = "solved"


@dataclass
class RepairAction:
    """A proposed repair to try on a near-solved task."""
    action_type: str
    description: str
    priority: float = 0.0
    tried: bool = False
    succeeded: bool = False


@dataclass
class NearSolvedTaskState:
    """Checkpointed reasoning state for a nearly solved task.

    In manifold language: z_t ∈ M_mem where d_M(z_t, S_solved) ≈ ε.
    The task has not been solved, but the system has reached the
    boundary of a known solution region.
    """
    task_id: str
    manifold_point: ManifoldPoint
    active_chart: str
    best_hypothesis: Optional[Dict[str, Any]]
    hypothesis_score: float
    train_fit: float
    train_fit_detail: List[bool]
    loo_passed: bool
    failure_type: str
    failed_examples: List[int]
    error_signature: Dict[str, Any]
    retrieved_success_anchors: List[str]
    retrieved_failure_anchors: List[str]
    proposed_repairs: List[RepairAction]
    missing_capability_guess: str
    views_tried: List[str]
    iterations_used: int
    status: str = NearSolvedStatus.PARTIAL
    suspected_next_chart: Optional[str] = None
    topology_signature: Optional[Dict[str, Any]] = None
    jepa_embedding: Optional[List[float]] = None
    jepa_layout_prediction: Optional[Dict[str, Any]] = None
    jepa_perception_flags: Optional[Dict[str, Any]] = None

    @property
    def is_near_solved(self) -> bool:
        return self.train_fit >= 0.5 and len(self.proposed_repairs) > 0

    @property
    def repair_distance(self) -> int:
        return sum(1 for r in self.proposed_repairs if not r.tried)

    def best_untried_repair(self) -> Optional[RepairAction]:
        for r in sorted(self.proposed_repairs, key=lambda x: -x.priority):
            if not r.tried:
                return r
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "active_chart": self.active_chart,
            "hypothesis_score": self.hypothesis_score,
            "train_fit": self.train_fit,
            "loo_passed": self.loo_passed,
            "failure_type": self.failure_type,
            "failed_examples": self.failed_examples,
            "missing_capability_guess": self.missing_capability_guess,
            "views_tried": self.views_tried,
            "iterations_used": self.iterations_used,
            "repair_distance": self.repair_distance,
            "suspected_next_chart": self.suspected_next_chart,
            "jepa_layout_prediction": self.jepa_layout_prediction,
            "jepa_perception_flags": self.jepa_perception_flags,
        }


# ═══════════════════════════════════════════════════════════════════════════
# NEAR-SOLVED MEMORY
# ═══════════════════════════════════════════════════════════════════════════

class NearSolvedMemory:
    """Persistent memory of near-solved task states.

    Stores partial reasoning trajectories as first-class scientific
    artifacts. Tasks are not just solved/unsolved — they exist on a
    spectrum from unknown to near-solved to solved.

    Near-solved tasks are stored as boundary points on the reasoning
    manifold. Future reasoning can:
    1. Resume from the best partial hypothesis
    2. Retrieve similar near-solved and solved trajectories
    3. Repair the current hypothesis using the failure diagnosis
    4. Detect when a cluster of near-solved tasks suggests a missing
       chart/adapter
    """

    def __init__(self, manifold: Optional[MemoryManifold] = None):
        self.states: Dict[str, NearSolvedTaskState] = {}
        self.manifold = manifold

    def store_partial(self, state: NearSolvedTaskState) -> None:
        """Store a near-solved task state."""
        if state.is_near_solved:
            state.status = NearSolvedStatus.NEAR_SOLVED
        self.states[state.task_id] = state

        if self.manifold is not None:
            point = ManifoldPoint(
                embedding=state.manifold_point.embedding.copy(),
                task_signature=state.manifold_point.task_signature.copy(),
                domain=state.manifold_point.domain,
                hypothesis=state.best_hypothesis,
                metadata={
                    "solved": False,
                    "near_solved": state.is_near_solved,
                    "train_fit": state.train_fit,
                    "failure_type": state.failure_type,
                },
            )
            self.manifold.add_point(point)

    def retrieve_similar_partial(
        self,
        task_signature: Dict[str, Any],
        k: int = 5,
    ) -> List[NearSolvedTaskState]:
        """Retrieve near-solved states with similar task signatures."""
        if not self.states:
            return []

        emb = _signature_to_embedding(task_signature)
        scored: List[Tuple[float, NearSolvedTaskState]] = []

        for state in self.states.values():
            state_emb = state.manifold_point.embedding
            if state_emb.shape != emb.shape:
                continue
            dist = float(np.linalg.norm(emb - state_emb))
            scored.append((dist, state))

        scored.sort(key=lambda x: x[0])
        return [s for _, s in scored[:k]]

    def resume_from_state(self, task_id: str) -> Optional[NearSolvedTaskState]:
        """Retrieve the stored state for a task to resume reasoning."""
        return self.states.get(task_id)

    def promote_to_solved(
        self,
        task_id: str,
        hypothesis: Dict[str, Any],
    ) -> bool:
        """Promote a near-solved task to solved."""
        state = self.states.get(task_id)
        if state is None:
            return False
        state.status = NearSolvedStatus.SOLVED
        state.best_hypothesis = hypothesis
        state.train_fit = 1.0
        state.loo_passed = True

        if self.manifold is not None:
            point = ManifoldPoint(
                embedding=state.manifold_point.embedding.copy(),
                task_signature=state.manifold_point.task_signature.copy(),
                domain=state.manifold_point.domain,
                hypothesis=hypothesis,
                metadata={"solved": True, "promoted_from_near_solved": True},
            )
            self.manifold.add_point(point)

        return True

    def detect_missing_charts(
        self, min_cluster_size: int = 3,
    ) -> List[Dict[str, Any]]:
        """Detect clusters of near-solved tasks that suggest a missing chart.

        When multiple near-solved tasks share the same failure type and
        suspected next chart, this signals that the reasoning manifold
        is missing a chart/adapter for that capability.
        """
        clusters: Dict[str, List[NearSolvedTaskState]] = {}

        for state in self.states.values():
            if state.status in (NearSolvedStatus.SOLVED,):
                continue
            key = f"{state.failure_type}:{state.missing_capability_guess}"
            clusters.setdefault(key, []).append(state)

        missing = []
        for key, members in clusters.items():
            if len(members) >= min_cluster_size:
                failure_type, capability = key.split(":", 1)
                missing.append({
                    "failure_type": failure_type,
                    "missing_capability": capability,
                    "n_tasks": len(members),
                    "task_ids": [s.task_id for s in members],
                    "mean_train_fit": float(np.mean([s.train_fit for s in members])),
                    "suspected_charts": list({
                        s.suspected_next_chart for s in members
                        if s.suspected_next_chart is not None
                    }),
                })

        missing.sort(key=lambda x: -x["n_tasks"])
        return missing

    @property
    def summary(self) -> Dict[str, int]:
        counts = {
            NearSolvedStatus.PARTIAL: 0,
            NearSolvedStatus.NEAR_SOLVED: 0,
            NearSolvedStatus.BLOCKED: 0,
            NearSolvedStatus.SOLVED: 0,
        }
        for state in self.states.values():
            counts[state.status] = counts.get(state.status, 0) + 1
        return counts


# ═══════════════════════════════════════════════════════════════════════════
# BUILDERS — construct NearSolvedTaskState from loop results
# ═══════════════════════════════════════════════════════════════════════════

def build_near_solved_state(
    task_id: str,
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    loop_result: Any,
) -> NearSolvedTaskState:
    """Build a NearSolvedTaskState from an AdaptiveReasoningLoop result."""
    sig = encode_task_signature(train_pairs)
    emb = _signature_to_embedding(sig)
    point = ManifoldPoint(embedding=emb, task_signature=sig, domain="grid")

    hypothesis = loop_result.hypothesis if hasattr(loop_result, "hypothesis") else None
    views = loop_result.views_tried if hasattr(loop_result, "views_tried") else []
    iters = loop_result.iterations_used if hasattr(loop_result, "iterations_used") else 0

    diag_trace = loop_result.diagnosis_trace if hasattr(loop_result, "diagnosis_trace") else []
    last_diag = diag_trace[-1] if diag_trace else None
    failure_type = last_diag.failure_type if last_diag and hasattr(last_diag, "failure_type") else "unknown"

    train_fit, fit_detail = _compute_train_fit(train_pairs, hypothesis)

    failed_examples = [i for i, passed in enumerate(fit_detail) if not passed]

    repairs = _propose_repairs(failure_type, hypothesis, views)

    missing_cap = _guess_missing_capability(failure_type, sig)
    suspected_chart = _guess_next_chart(failure_type, missing_cap)

    active_chart = "unknown"
    if hasattr(loop_result, "manifold_chart") and loop_result.manifold_chart:
        active_chart = loop_result.manifold_chart

    success_anchors: List[str] = []
    failure_anchors: List[str] = []

    topo_sig = {
        "n_objects": sig.get("n_objects", 0),
        "has_separators": sig.get("has_separators", False),
        "has_containment": sig.get("has_containment", False),
        "has_holes": sig.get("has_holes", False),
        "has_symmetry": sig.get("has_symmetry", False),
        "color_transform": sig.get("color_transform", "same"),
    }

    return NearSolvedTaskState(
        task_id=task_id,
        manifold_point=point,
        active_chart=active_chart,
        best_hypothesis=hypothesis,
        hypothesis_score=train_fit,
        train_fit=train_fit,
        train_fit_detail=fit_detail,
        loo_passed=False,
        failure_type=failure_type,
        failed_examples=failed_examples,
        error_signature={
            "failure_type": failure_type,
            "views_exhausted": len(views),
            "best_hypothesis": hypothesis,
        },
        retrieved_success_anchors=success_anchors,
        retrieved_failure_anchors=failure_anchors,
        proposed_repairs=repairs,
        missing_capability_guess=missing_cap,
        views_tried=views,
        iterations_used=iters,
        suspected_next_chart=suspected_chart,
        topology_signature=topo_sig,
    )


def _compute_train_fit(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    hypothesis: Optional[Dict[str, Any]],
) -> Tuple[float, List[bool]]:
    """Compute how well the best hypothesis fits the training pairs."""
    if hypothesis is None:
        return 0.0, [False] * len(train_pairs)

    from reasoning_project.reasoning_engine import (
        GridDomainAdapter,
        StructuralReasoner,
    )
    adapter = GridDomainAdapter()
    reasoner = StructuralReasoner(adapter)
    fit_detail = []
    for inp, out in train_pairs:
        replay = reasoner._replay_hypothesis(hypothesis, [(inp, out)], [inp])
        if replay is not None:
            preds, _ = replay
            fit_detail.append(
                len(preds) > 0 and np.array_equal(preds[0], out)
            )
        else:
            fit_detail.append(False)
    n_fit = sum(fit_detail)
    return n_fit / max(len(train_pairs), 1), fit_detail


def _propose_repairs(
    failure_type: str,
    hypothesis: Optional[Dict[str, Any]],
    views_tried: List[str],
) -> List[RepairAction]:
    """Propose concrete repair actions based on failure diagnosis."""
    repairs: List[RepairAction] = []

    if failure_type == "no_discrimination":
        repairs.append(RepairAction(
            action_type="add_conjunction",
            description="Try compound predicate (p1 ∧ p2) search",
            priority=0.9,
        ))
        repairs.append(RepairAction(
            action_type="add_spatial_property",
            description="Add spatial-rank or positional predicates",
            priority=0.7,
        ))
        repairs.append(RepairAction(
            action_type="try_neural_perception",
            description="Use JEPA/Slot Attention for richer features",
            priority=0.5,
        ))

    elif failure_type == "wrong_reconstruction":
        repairs.append(RepairAction(
            action_type="fix_reconstruction",
            description="Refine object placement or color mapping",
            priority=0.8,
        ))
        repairs.append(RepairAction(
            action_type="try_different_decomposition",
            description="Switch to per-color or monochrome view",
            priority=0.6,
        ))

    elif failure_type == "partial_match":
        repairs.append(RepairAction(
            action_type="refine_predicate",
            description="Tighten predicate to handle edge case",
            priority=0.9,
        ))
        repairs.append(RepairAction(
            action_type="add_exception_rule",
            description="Add conditional for mismatched examples",
            priority=0.7,
        ))

    elif failure_type == "no_objects":
        repairs.append(RepairAction(
            action_type="change_decomposition",
            description="Try different object extraction strategy",
            priority=0.9,
        ))
        if "majority_bg" not in views_tried:
            repairs.append(RepairAction(
                action_type="try_majority_bg",
                description="Use majority-color background detection",
                priority=0.8,
            ))

    if not repairs:
        repairs.append(RepairAction(
            action_type="synthesize_adapter",
            description="Use AdapterGenesis to synthesize new adapter",
            priority=0.3,
        ))

    return repairs


def _guess_missing_capability(
    failure_type: str,
    sig: Dict[str, Any],
) -> str:
    """Guess what capability is missing based on failure type and task signature."""
    if failure_type == "no_discrimination":
        if sig.get("has_containment", False):
            return "containment_reasoning"
        if sig.get("has_symmetry", False):
            return "symmetry_detection"
        if sig.get("n_objects", 0) > 6:
            return "counting_or_ranking"
        return "richer_property_language"

    if failure_type == "wrong_reconstruction":
        if sig.get("size_changing", False):
            return "size_transform"
        return "spatial_reconstruction"

    if failure_type == "partial_match":
        return "edge_case_handling"

    if failure_type == "no_objects":
        return "object_decomposition"

    return "unknown"


def _guess_next_chart(failure_type: str, missing_cap: str) -> Optional[str]:
    """Guess which chart transition is needed."""
    chart_map = {
        "containment_reasoning": "containment_chart",
        "symmetry_detection": "symmetry_chart",
        "counting_or_ranking": "ranking_chart",
        "richer_property_language": "conjunction_chart",
        "size_transform": "transform_chart",
        "spatial_reconstruction": "reconstruction_chart",
        "edge_case_handling": "conditional_chart",
        "object_decomposition": "decomposition_chart",
    }
    return chart_map.get(missing_cap)


# ═══════════════════════════════════════════════════════════════════════════
# CACHE I/O — save/load near-solved states to skip Phase 1 rebuilding
# ═══════════════════════════════════════════════════════════════════════════

def _state_to_json(state: NearSolvedTaskState) -> Dict[str, Any]:
    """Serialize a NearSolvedTaskState to JSON-safe dict."""
    return {
        "task_id": state.task_id,
        "status": state.status,
        "active_chart": state.active_chart,
        "best_hypothesis": state.best_hypothesis,
        "hypothesis_score": state.hypothesis_score,
        "train_fit": state.train_fit,
        "train_fit_detail": state.train_fit_detail,
        "loo_passed": state.loo_passed,
        "failure_type": state.failure_type,
        "failed_examples": state.failed_examples,
        "error_signature": state.error_signature,
        "retrieved_success_anchors": state.retrieved_success_anchors,
        "retrieved_failure_anchors": state.retrieved_failure_anchors,
        "proposed_repairs": [
            {"action_type": r.action_type, "description": r.description,
             "priority": r.priority, "tried": r.tried, "succeeded": r.succeeded}
            for r in state.proposed_repairs
        ],
        "missing_capability_guess": state.missing_capability_guess,
        "views_tried": state.views_tried,
        "iterations_used": state.iterations_used,
        "suspected_next_chart": state.suspected_next_chart,
        "topology_signature": state.topology_signature,
        "manifold_embedding": state.manifold_point.embedding.tolist(),
        "manifold_task_signature": state.manifold_point.task_signature,
        "manifold_domain": state.manifold_point.domain,
    }


def _state_from_json(d: Dict[str, Any]) -> NearSolvedTaskState:
    """Deserialize a NearSolvedTaskState from JSON dict."""
    point = ManifoldPoint(
        embedding=np.array(d["manifold_embedding"], dtype=np.float64),
        task_signature=d.get("manifold_task_signature", {}),
        domain=d.get("manifold_domain", "grid"),
    )
    repairs = [
        RepairAction(
            action_type=r["action_type"],
            description=r["description"],
            priority=r.get("priority", 0.0),
            tried=r.get("tried", False),
            succeeded=r.get("succeeded", False),
        )
        for r in d.get("proposed_repairs", [])
    ]
    return NearSolvedTaskState(
        task_id=d["task_id"],
        manifold_point=point,
        active_chart=d.get("active_chart", "unknown"),
        best_hypothesis=d.get("best_hypothesis"),
        hypothesis_score=d.get("hypothesis_score", 0.0),
        train_fit=d.get("train_fit", 0.0),
        train_fit_detail=d.get("train_fit_detail", []),
        loo_passed=d.get("loo_passed", False),
        failure_type=d.get("failure_type", "unknown"),
        failed_examples=d.get("failed_examples", []),
        error_signature=d.get("error_signature", {}),
        retrieved_success_anchors=d.get("retrieved_success_anchors", []),
        retrieved_failure_anchors=d.get("retrieved_failure_anchors", []),
        proposed_repairs=repairs,
        missing_capability_guess=d.get("missing_capability_guess", "unknown"),
        views_tried=d.get("views_tried", []),
        iterations_used=d.get("iterations_used", 0),
        status=d.get("status", "partial"),
        suspected_next_chart=d.get("suspected_next_chart"),
        topology_signature=d.get("topology_signature"),
    )


def save_near_solved_cache(
    cache_dir: str,
    ns_mem: NearSolvedMemory,
    solved_ids: List[str],
    status: Optional[Dict[str, Any]] = None,
) -> None:
    """Write near-solved cache to disk."""
    import json
    from pathlib import Path
    d = Path(cache_dir)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "near_solved_states.jsonl", "w") as f:
        for state in ns_mem.states.values():
            f.write(json.dumps(_state_to_json(state)) + "\n")
    with open(d / "solved_tasks.json", "w") as f:
        json.dump({"solved": sorted(solved_ids)}, f, indent=2)
    if status:
        with open(d / "phase1_status.json", "w") as f:
            json.dump(status, f, indent=2)


def load_near_solved_cache(
    cache_dir: str,
) -> Tuple[NearSolvedMemory, List[str], Dict[str, Any]]:
    """Load near-solved cache from disk.
    Returns (ns_mem, solved_ids, status).
    """
    import json
    from pathlib import Path
    d = Path(cache_dir)
    manifold = MemoryManifold()
    ns_mem = NearSolvedMemory(manifold)

    states_path = d / "near_solved_states.jsonl"
    if states_path.exists():
        with open(states_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    state = _state_from_json(json.loads(line))
                    ns_mem.states[state.task_id] = state

    solved_ids: List[str] = []
    solved_path = d / "solved_tasks.json"
    if solved_path.exists():
        with open(solved_path) as f:
            solved_ids = json.load(f).get("solved", [])

    status: Dict[str, Any] = {}
    status_path = d / "phase1_status.json"
    if status_path.exists():
        with open(status_path) as f:
            status = json.load(f)

    return ns_mem, solved_ids, status
