"""Event-log policy learner for reasoning action selection.

Uses the event log as training data to learn which reasoning action
to try next given task signature, failure diagnosis, near-solved state,
JEPA predictions, memory retrievals, and previous failed hypotheses.

Actions:
    try_view, try_concept_family, try_operator_schema,
    generate_counterexample, repair_adapter, resume_task, create_concept
"""
from __future__ import annotations

import json
import math
import os
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from reasoning_project.events import ReasoningEventLog, ReasoningEvent
from reasoning_project.near_solved_memory import NearSolvedTaskState


# ═══════════════════════════════════════════════════════════════════════════
# ACTION SPACE
# ═══════════════════════════════════════════════════════════════════════════

ACTIONS = [
    "try_view",
    "try_concept_family",
    "try_operator_schema",
    "generate_counterexample",
    "repair_adapter",
    "resume_task",
    "create_concept",
]

CONCEPT_FAMILIES = [
    "containment",
    "separator_cell_composition",
    "marker_target",
    "symmetry",
    "repetition",
    "rank_count",
    "spatial_relation",
    "color_binding",
]

VIEWS = ["color_cc", "per_color", "majority_bg", "monochrome"]


@dataclass
class ReasoningState:
    """Observable state for policy decision."""
    task_signature: Dict[str, Any] = field(default_factory=dict)
    failure_type: str = ""
    views_tried: List[str] = field(default_factory=list)
    concepts_tried: List[str] = field(default_factory=list)
    schemas_tried: List[str] = field(default_factory=list)
    n_failed_hypotheses: int = 0
    has_near_solved_state: bool = False
    train_fit: float = 0.0
    jepa_layout: str = ""
    jepa_has_separators: float = 0.0
    jepa_has_containment: float = 0.0
    memory_retrievals: int = 0
    iteration: int = 0

    def to_features(self) -> np.ndarray:
        ft = []
        for v in VIEWS:
            ft.append(1.0 if v in self.views_tried else 0.0)
        for cf in CONCEPT_FAMILIES:
            ft.append(1.0 if cf in self.concepts_tried else 0.0)
        ft.append(float(self.n_failed_hypotheses) / 10.0)
        ft.append(1.0 if self.has_near_solved_state else 0.0)
        ft.append(self.train_fit)
        ft.append(self.jepa_has_separators)
        ft.append(self.jepa_has_containment)
        ft.append(float(self.memory_retrievals) / 10.0)
        ft.append(float(self.iteration) / 10.0)
        failure_types = [
            "no_objects", "wrong_objects", "no_discrimination",
            "wrong_reconstruction", "partial_match",
        ]
        for ftype in failure_types:
            ft.append(1.0 if self.failure_type == ftype else 0.0)
        layouts = ["scattered", "grid_of_cells", "nested", "linear", "single_object"]
        for lay in layouts:
            ft.append(1.0 if self.jepa_layout == lay else 0.0)
        return np.array(ft, dtype=np.float32)


@dataclass
class PolicyAction:
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class PolicyTrainingExample:
    state: ReasoningState
    action: PolicyAction
    reward: float
    task_id: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# POLICY EXTRACTION FROM EVENT LOG
# ═══════════════════════════════════════════════════════════════════════════

class PolicyDataExtractor:
    """Extract (state, action, reward) tuples from the event log."""

    def extract(self, event_log: ReasoningEventLog) -> List[PolicyTrainingExample]:
        examples = []
        task_events: Dict[str, List[ReasoningEvent]] = defaultdict(list)

        for ev in event_log.events:
            if ev.task_id:
                task_events[ev.task_id].append(ev)

        for task_id, events in task_events.items():
            events_sorted = sorted(events, key=lambda e: e.timestamp)
            solved = any(
                e.event_type in ("TASK_PROMOTED_TO_SOLVED", "HYPOTHESIS_ACCEPTED")
                for e in events_sorted
            )
            reward = 1.0 if solved else 0.0

            state = ReasoningState(task_signature={}, failure_type="")
            for ev in events_sorted:
                action = self._event_to_action(ev)
                if action is not None:
                    examples.append(PolicyTrainingExample(
                        state=ReasoningState(**{
                            k: v for k, v in state.__dict__.items()
                        }),
                        action=action,
                        reward=reward,
                        task_id=task_id,
                    ))
                self._update_state(state, ev)

        return examples

    def _event_to_action(self, ev: ReasoningEvent) -> Optional[PolicyAction]:
        et = ev.event_type
        payload = ev.payload or {}

        if et == "TASK_OBSERVED":
            return PolicyAction("try_view", {"view": "color_cc"})
        elif et == "HYPOTHESIS_PROPOSED":
            view = payload.get("view", "")
            if view:
                return PolicyAction("try_view", {"view": view})
        elif et == "CONCEPT_PROPOSED":
            return PolicyAction("create_concept", payload)
        elif et == "OPERATOR_PROPOSED":
            return PolicyAction("try_operator_schema", payload)
        elif et == "COUNTEREXAMPLE_GENERATED":
            return PolicyAction("generate_counterexample", payload)
        elif et == "TASK_RESUMED":
            return PolicyAction("resume_task", payload)
        elif et == "CHART_PROPOSED":
            return PolicyAction("repair_adapter", payload)
        return None

    def _update_state(self, state: ReasoningState, ev: ReasoningEvent) -> None:
        et = ev.event_type
        payload = ev.payload or {}

        if et == "HYPOTHESIS_PROPOSED":
            state.n_failed_hypotheses += 1
            view = payload.get("view", "")
            if view and view not in state.views_tried:
                state.views_tried.append(view)
        elif et == "HYPOTHESIS_REJECTED":
            state.failure_type = payload.get("failure_type", state.failure_type)
        elif et == "NEAR_SOLVED_STORED":
            state.has_near_solved_state = True
            state.train_fit = payload.get("train_fit", 0.0)
        elif et == "MEMORY_RETRIEVED":
            state.memory_retrievals += 1
        state.iteration += 1


# ═══════════════════════════════════════════════════════════════════════════
# TABULAR POLICY (no neural deps beyond numpy)
# ═══════════════════════════════════════════════════════════════════════════

class TabularReasoningPolicy:
    """Simple feature-weighted policy learned from event log data."""

    def __init__(self, n_actions: int = len(ACTIONS)):
        self.n_actions = n_actions
        feat_dim = ReasoningState().to_features().shape[0]
        self.weights = np.zeros((n_actions, feat_dim), dtype=np.float32)
        self.bias = np.zeros(n_actions, dtype=np.float32)
        self.action_counts = np.zeros(n_actions, dtype=np.float32)

    def predict(self, state: ReasoningState) -> PolicyAction:
        feats = state.to_features()
        scores = self.weights @ feats + self.bias
        probs = _softmax(scores)
        action_idx = int(np.argmax(probs))
        return PolicyAction(
            action=ACTIONS[action_idx],
            score=float(probs[action_idx]),
        )

    def predict_ranked(self, state: ReasoningState, k: int = 3) -> List[PolicyAction]:
        feats = state.to_features()
        scores = self.weights @ feats + self.bias
        probs = _softmax(scores)
        ranked = sorted(range(self.n_actions), key=lambda i: -probs[i])
        return [
            PolicyAction(action=ACTIONS[i], score=float(probs[i]))
            for i in ranked[:k]
        ]

    def train(
        self,
        examples: List[PolicyTrainingExample],
        learning_rate: float = 0.01,
        epochs: int = 50,
    ) -> Dict[str, Any]:
        if not examples:
            return {"status": "no_data"}

        for epoch in range(epochs):
            total_loss = 0.0
            random.shuffle(examples)
            for ex in examples:
                feats = ex.state.to_features()
                action_idx = ACTIONS.index(ex.action.action) if ex.action.action in ACTIONS else 0

                scores = self.weights @ feats + self.bias
                probs = _softmax(scores)
                grad = probs.copy()
                grad[action_idx] -= 1.0
                grad *= -ex.reward

                self.weights -= learning_rate * np.outer(grad, feats)
                self.bias -= learning_rate * grad
                total_loss += -ex.reward * math.log(max(probs[action_idx], 1e-8))

                self.action_counts[action_idx] += 1

        return {
            "status": "trained",
            "n_examples": len(examples),
            "epochs": epochs,
            "action_distribution": {
                ACTIONS[i]: int(self.action_counts[i])
                for i in range(self.n_actions)
            },
        }


# ═══════════════════════════════════════════════════════════════════════════
# RULE-BASED POLICY (fallback)
# ═══════════════════════════════════════════════════════════════════════════

class RuleBasedReasoningPolicy:
    """Handcrafted policy based on failure diagnosis and JEPA predictions."""

    def predict(self, state: ReasoningState) -> PolicyAction:
        untried_views = [v for v in VIEWS if v not in state.views_tried]
        if untried_views:
            best_view = untried_views[0]
            if state.jepa_has_separators > 0.5 and "per_color" in untried_views:
                best_view = "per_color"
            elif state.jepa_has_containment > 0.5 and "color_cc" in untried_views:
                best_view = "color_cc"
            elif state.jepa_layout == "single_object" and "per_color" in untried_views:
                best_view = "per_color"
            return PolicyAction("try_view", {"view": best_view}, score=0.8)

        if state.failure_type == "no_discrimination":
            untried_concepts = [
                cf for cf in CONCEPT_FAMILIES if cf not in state.concepts_tried
            ]
            if untried_concepts:
                best_cf = untried_concepts[0]
                if state.jepa_has_containment > 0.5 and "containment" in untried_concepts:
                    best_cf = "containment"
                elif state.jepa_has_separators > 0.5 and "separator_cell_composition" in untried_concepts:
                    best_cf = "separator_cell_composition"
                return PolicyAction("try_concept_family", {"family": best_cf}, score=0.7)

        if state.failure_type in ("wrong_reconstruction", "partial_match"):
            return PolicyAction("try_operator_schema", {}, score=0.6)

        if state.has_near_solved_state and state.train_fit >= 0.5:
            return PolicyAction("resume_task", {}, score=0.7)

        if state.failure_type in ("no_objects", "wrong_objects"):
            return PolicyAction("repair_adapter", {}, score=0.5)

        return PolicyAction("create_concept", {}, score=0.4)


# ═══════════════════════════════════════════════════════════════════════════
# COMBINED POLICY
# ═══════════════════════════════════════════════════════════════════════════

class ReasoningPolicy:
    """Combined learned + rule-based reasoning policy."""

    def __init__(self):
        self.learned = TabularReasoningPolicy()
        self.rule_based = RuleBasedReasoningPolicy()
        self.trained = False
        self.blend_weight = 0.5

    def train_from_event_log(self, event_log: ReasoningEventLog) -> Dict[str, Any]:
        extractor = PolicyDataExtractor()
        examples = extractor.extract(event_log)
        if not examples:
            return {"status": "no_data", "n_examples": 0}
        result = self.learned.train(examples)
        self.trained = True
        self.blend_weight = 0.7
        return result

    def predict(self, state: ReasoningState) -> PolicyAction:
        rule_action = self.rule_based.predict(state)
        if not self.trained:
            return rule_action

        learned_action = self.learned.predict(state)
        if learned_action.score > rule_action.score * self.blend_weight:
            return learned_action
        return rule_action

    def predict_ranked(self, state: ReasoningState, k: int = 3) -> List[PolicyAction]:
        if self.trained:
            return self.learned.predict_ranked(state, k)
        rule_action = self.rule_based.predict(state)
        return [rule_action]


# ═══════════════════════════════════════════════════════════════════════════
# REPORT / EXPORT
# ═══════════════════════════════════════════════════════════════════════════

def export_policy_training_data(
    event_log: ReasoningEventLog,
    output_path: str,
) -> int:
    extractor = PolicyDataExtractor()
    examples = extractor.extract(event_log)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        for ex in examples:
            record = {
                "task_id": ex.task_id,
                "action": ex.action.action,
                "action_params": ex.action.params,
                "reward": ex.reward,
                "failure_type": ex.state.failure_type,
                "views_tried": ex.state.views_tried,
                "n_failed_hypotheses": ex.state.n_failed_hypotheses,
                "has_near_solved_state": ex.state.has_near_solved_state,
                "train_fit": ex.state.train_fit,
            }
            f.write(json.dumps(record, default=str) + "\n")
    return len(examples)


def write_policy_eval_report(
    policy: ReasoningPolicy,
    event_log: ReasoningEventLog,
    output_dir: str,
) -> None:
    os.makedirs(output_dir, exist_ok=True)

    n_exported = export_policy_training_data(
        event_log, os.path.join(output_dir, "policy_training_data.jsonl"),
    )

    train_result = policy.train_from_event_log(event_log)

    lines = [
        "# Reasoning Policy Evaluation\n",
        f"**Training examples**: {train_result.get('n_examples', 0)}",
        f"**Status**: {train_result.get('status', 'unknown')}",
        "",
        "## Action Distribution\n",
    ]
    dist = train_result.get("action_distribution", {})
    for action, count in sorted(dist.items(), key=lambda x: -x[1]):
        lines.append(f"- {action}: {count}")

    lines.append("\n## Policy Parameters\n")
    lines.append(f"- Trained: {policy.trained}")
    lines.append(f"- Blend weight: {policy.blend_weight}")

    with open(os.path.join(output_dir, "policy_eval_report.md"), "w") as f:
        f.write("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()
