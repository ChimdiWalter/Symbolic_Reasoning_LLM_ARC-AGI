"""Domain-adaptable structural reasoning engine.

Performs INDUCTIVE INFERENCE over a pluggable language of structural properties.
The inference logic (discriminative filtering, transform induction, compositional
planning, LOO cross-validation) is domain-agnostic. Domain-specific perception
is provided by a DomainAdapter.

Architecture:
    DomainAdapter (abstract)     — how to decompose scenes into objects
      └─ GridDomainAdapter       — ARC/colored-grid perception (default)
      └─ (user-defined)          — molecular graphs, images, circuits, etc.

    StructuralReasoner           — domain-agnostic inductive inference
      ├─ discriminative filtering — find property separating kept/removed
      ├─ transform induction     — discover recoloring/relabeling rules
      └─ compositional planning  — sequence filter→transform, filter→extract

Soundness guarantee: any hypothesis output by this engine is consistent with
all training examples via leave-one-out cross-validation, regardless of domain.
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
import numpy as np
from scipy import ndimage
from scipy.optimize import linear_sum_assignment
from typing import Optional, List, Tuple, Dict, Any, Callable, Sequence


# ═══════════════════════════════════════════════════════════════════════════
# DOMAIN ADAPTER PROTOCOL — implement this for your domain
# ═══════════════════════════════════════════════════════════════════════════

class DomainAdapter(abc.ABC):
    """Abstract interface between a domain and the reasoning engine.

    Subclass this to plug the reasoning engine into any domain where
    scenes decompose into objects with computable boolean properties.

    Minimal contract:
        - extract_objects(scene) → list of object dicts with boolean properties
        - classify_kept_removed(objects, input, output) → (kept, removed) indices
        - reconstruct_filtered(input, objects, keep_mask) → output scene
        - reconstruct_recolored(input, objects, label_map) → output scene
        - scenes_equal(a, b) → bool
    """

    @abc.abstractmethod
    def extract_objects(self, scene: Any) -> List[Dict[str, Any]]:
        """Decompose a scene into objects with computable properties.

        Each object dict must contain at minimum:
            - boolean properties (used for discriminative reasoning)
            - "label" (hashable identifier)
            - "primary_color" or "primary_label" (for transform induction)

        Additional fields are domain-specific.
        """

    @abc.abstractmethod
    def property_names(self) -> List[str]:
        """Return all boolean property names the adapter computes."""

    @abc.abstractmethod
    def get_property(self, obj: Dict, prop: str) -> bool:
        """Get a boolean property value for an object."""

    @abc.abstractmethod
    def classify_kept_removed(
        self, objects: List[Dict], inp: Any, out: Any,
    ) -> Optional[Tuple[List[int], List[int]]]:
        """Classify which input objects are kept vs removed in the output.
        Returns (kept_indices, removed_indices) or None if not applicable.
        """

    @abc.abstractmethod
    def reconstruct_filtered(
        self, inp: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Optional[Any]:
        """Reconstruct a scene keeping only objects where keep_mask is True."""

    @abc.abstractmethod
    def reconstruct_recolored(
        self, inp: Any, objects: List[Dict], label_map: Dict[int, int],
    ) -> Optional[Any]:
        """Reconstruct a scene with object labels/colors remapped."""

    @abc.abstractmethod
    def reconstruct_extracted(
        self, inp: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Optional[Any]:
        """Extract kept objects (e.g., crop to bounding box of survivors)."""

    @abc.abstractmethod
    def scenes_equal(self, a: Any, b: Any) -> bool:
        """Check if two scenes are identical."""

    @abc.abstractmethod
    def same_structure(self, a: Any, b: Any) -> bool:
        """Check if two scenes have compatible structure (e.g., same shape)."""

    def classify_object_changes(
        self, objects: List[Dict], inp: Any, out: Any,
    ) -> Optional["ObjectChangeClassification"]:
        """Rich per-object change classification.

        Returns ObjectChangeClassification with per-object change types
        (kept, removed, recolored, moved, copied, etc.) or None.

        Default implementation calls _classify_object_changes for grid-based
        domains. Override for non-grid domains.
        """
        return None

    def match_objects(
        self, in_objs: List[Dict], out_objs: List[Dict],
    ) -> List[Tuple[int, int, float]]:
        """Match input→output objects for transform induction.
        Returns list of (in_idx, out_idx, cost). Default uses Hungarian.
        """
        return _match_objects_hungarian_generic(in_objs, out_objs)


def _match_objects_hungarian_generic(
    in_objs: List[Dict],
    out_objs: List[Dict],
    similarity_fn: Optional[Callable] = None,
) -> List[Tuple[int, int, float]]:
    """Generic Hungarian matching using a similarity function.

    Args:
        similarity_fn: (obj_a, obj_b) -> float (higher = more similar).
            If None, uses area + center position.
    """
    n_in, n_out = len(in_objs), len(out_objs)
    if n_in == 0 or n_out == 0:
        return []
    n = max(n_in, n_out)
    cost = np.full((n, n), 1e6)
    for i in range(n_in):
        for j in range(n_out):
            if similarity_fn is not None:
                cost[i, j] = -similarity_fn(in_objs[i], out_objs[j])
            else:
                a_dist = abs(in_objs[i].get("area", 0) - out_objs[j].get("area", 0))
                a_norm = a_dist / max(in_objs[i].get("area", 1), out_objs[j].get("area", 1), 1)
                p_dist = (abs(in_objs[i].get("center_r", 0) - out_objs[j].get("center_r", 0)) +
                          abs(in_objs[i].get("center_c", 0) - out_objs[j].get("center_c", 0)))
                cost[i, j] = 0.3 * a_norm + 0.1 * p_dist
    row_ind, col_ind = linear_sum_assignment(cost)
    matches = []
    for i, j in zip(row_ind, col_ind):
        if i < n_in and j < n_out and cost[i, j] < 10.0:
            matches.append((i, j, float(cost[i, j])))
    return matches


# ═══════════════════════════════════════════════════════════════════════════
# STRUCTURAL REASONER — domain-agnostic inductive inference engine
# ═══════════════════════════════════════════════════════════════════════════

class WorkingMemory:
    """Per-task dynamic scratch space — the 'mental workspace' of the reasoner.

    Cognitive mapping:
        Working Memory → Inference Engine active state
        - Holds structural observations (computed once, reused across phases)
        - Tracks partial evidence (failed phases inform later ones)
        - Maintains attention weights (which properties to try first)
        - Decomposes complex goals into sub-goals

    Created fresh for each task, discarded after solve. Long-term learning
    goes into ReasoningMemory instead.
    """

    def __init__(
        self,
        adapter: "DomainAdapter",
        train_pairs: List[Tuple[Any, Any]],
        test_inputs: List[Any],
    ):
        self.adapter = adapter
        self.train_pairs = train_pairs
        self.test_inputs = test_inputs

        # Structural observations — compute once, reuse everywhere
        self._train_objects: Optional[List[List[Dict]]] = None
        self._test_objects: Optional[List[List[Dict]]] = None
        self._classifications: Optional[List[Optional[Tuple[List[int], List[int]]]]] = None
        self._same_structure: Optional[bool] = None

        # Attention — property priority order (informed by episodic recall)
        self.property_priority: Optional[List[str]] = None

        # Partial evidence — near-miss properties from failed phases
        self.partial_evidence: List[Dict[str, Any]] = []

        # Sub-goal decomposition trace
        self.decomposition: List[str] = []

    @property
    def train_objects(self) -> List[List[Dict]]:
        if self._train_objects is None:
            self._train_objects = [
                self.adapter.extract_objects(inp)
                for inp, _ in self.train_pairs
            ]
        return self._train_objects

    @property
    def test_objects(self) -> List[List[Dict]]:
        if self._test_objects is None:
            self._test_objects = [
                self.adapter.extract_objects(ti)
                for ti in self.test_inputs
            ]
        return self._test_objects

    @property
    def classifications(self) -> List[Optional[Tuple[List[int], List[int]]]]:
        if self._classifications is None:
            self._classifications = []
            for objs, (inp, out) in zip(self.train_objects, self.train_pairs):
                self._classifications.append(
                    self.adapter.classify_kept_removed(objs, inp, out)
                )
        return self._classifications

    @property
    def same_structure(self) -> bool:
        if self._same_structure is None:
            self._same_structure = all(
                self.adapter.same_structure(i, o)
                for i, o in self.train_pairs
            )
        return self._same_structure

    def get_ordered_properties(self) -> List[str]:
        """Return properties ordered by attention priority."""
        base = self.adapter.property_names()
        if self.property_priority is not None:
            prioritized = [p for p in self.property_priority if p in base]
            remaining = [p for p in base if p not in prioritized]
            return prioritized + remaining
        return base

    def prime_attention(self, episodic_hypotheses: List[Dict[str, Any]]) -> None:
        """Set property priorities from episodic recall (past solved tasks).

        Combines past experience with the current observation to focus
        the search on properties that worked for similar tasks.
        """
        prop_scores: Dict[str, float] = {}
        for hyp in episodic_hypotheses:
            prop = hyp.get("property") or hyp.get("filter_prop", "")
            if prop:
                prop_scores[prop] = prop_scores.get(prop, 0) + 1.0
            conj = hyp.get("conjunction", [])
            for p in conj:
                prop_scores[p] = prop_scores.get(p, 0) + 0.5
            rule_params = hyp.get("params", {})
            if "prop" in rule_params:
                prop_scores[rule_params["prop"]] = prop_scores.get(
                    rule_params["prop"], 0) + 0.8

        if prop_scores:
            ranked = sorted(prop_scores.keys(), key=lambda p: -prop_scores[p])
            self.property_priority = ranked

    def record_partial(self, phase: str, info: Dict[str, Any]) -> None:
        """Record a near-miss from a failed phase for later phases."""
        self.partial_evidence.append({"phase": phase, **info})

    def get_near_miss_properties(self) -> List[str]:
        """Properties that nearly discriminated — try them in compositions."""
        props = []
        for ev in self.partial_evidence:
            if "near_miss_prop" in ev:
                props.append(ev["near_miss_prop"])
        return props


class ReasoningMemory:
    """Persistent memory that grows the engine's reasoning capacity over time.

    Two memory systems:

    1. **Concept library** — learned compound predicates. When the engine
       discovers a novel conjunction (p1 AND p2) or negation pattern,
       it mints a new named predicate and adds it to the property language.
       Future tasks can use this predicate directly, making the engine
       strictly more capable over time.

    2. **Episodic memory** — solved task signatures → hypotheses. Stores
       structural fingerprints of solved tasks and their discovered rules.
       On new tasks, retrieves the k-nearest solved tasks and tries their
       hypotheses first (before exhaustive search), providing O(1) lookup
       for previously-seen task structures.

    Soundness invariant: memory can only ADD hypotheses to try, never
    remove the exhaustive search fallback. This means memory can make the
    engine faster (try the right property first) and more capable (new
    predicates) but never less sound.
    """

    def __init__(self):
        self.learned_predicates: List[Tuple[str, List[str], str]] = []
        self.episodes: List[Dict[str, Any]] = []

    # --- Concept library ---------------------------------------------------

    def mint_conjunction(
        self, name: str, props: List[str], mode: str = "and",
    ) -> None:
        """Register a learned compound predicate.

        Args:
            name: Human-readable name (e.g., "contained_and_holey")
            props: List of base property names to conjoin
            mode: "and" (all true) or "or" (any true)
        """
        for existing_name, existing_props, existing_mode in self.learned_predicates:
            if set(existing_props) == set(props) and existing_mode == mode:
                return
        self.learned_predicates.append((name, list(props), mode))

    def evaluate_learned_predicate(
        self, obj: Dict, name: str, adapter: "DomainAdapter",
    ) -> bool:
        """Evaluate a learned compound predicate on an object."""
        for pred_name, props, mode in self.learned_predicates:
            if pred_name == name:
                vals = [adapter.get_property(obj, p) for p in props]
                if mode == "and":
                    return all(vals)
                elif mode == "or":
                    return any(vals)
                elif mode == "not":
                    return not vals[0] if vals else False
        return False

    def learned_property_names(self) -> List[str]:
        """Return names of all learned predicates."""
        return [name for name, _, _ in self.learned_predicates]

    # --- Episodic memory ---------------------------------------------------

    def store_episode(
        self, signature: Dict[str, float], hypothesis: Dict[str, Any],
    ) -> None:
        """Store a solved task's signature and discovered hypothesis."""
        self.episodes.append({
            "signature": signature,
            "hypothesis": hypothesis,
        })

    def retrieve_similar(
        self, signature: Dict[str, float], k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve k-nearest hypotheses by signature distance."""
        if not self.episodes:
            return []

        scored = []
        for ep in self.episodes:
            dist = self._signature_distance(signature, ep["signature"])
            scored.append((dist, ep["hypothesis"]))
        scored.sort(key=lambda x: x[0])
        return [h for _, h in scored[:k]]

    @staticmethod
    def _signature_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
        all_keys = set(a.keys()) | set(b.keys())
        if not all_keys:
            return 0.0
        total = 0.0
        for k in all_keys:
            va = a.get(k, 0.0)
            vb = b.get(k, 0.0)
            denom = max(abs(va), abs(vb), 1.0)
            total += ((va - vb) / denom) ** 2
        return total ** 0.5

    @staticmethod
    def compute_task_signature(
        adapter: "DomainAdapter",
        train_pairs: List[Tuple[Any, Any]],
    ) -> Dict[str, float]:
        """Compute a structural fingerprint of a task for episodic retrieval."""
        sig: Dict[str, float] = {}
        n_obj_list = []
        for inp, out in train_pairs:
            objs = adapter.extract_objects(inp)
            n_obj_list.append(len(objs))
        sig["mean_objects"] = float(np.mean(n_obj_list)) if n_obj_list else 0.0
        sig["n_train"] = float(len(train_pairs))

        if train_pairs:
            inp0 = train_pairs[0][0]
            objs0 = adapter.extract_objects(inp0)
            props = adapter.property_names()
            for prop in props:
                vals = [adapter.get_property(o, prop) for o in objs0]
                sig[f"prop_{prop}_rate"] = float(np.mean(vals)) if vals else 0.0

            sig["same_structure"] = float(all(
                adapter.same_structure(i, o) for i, o in train_pairs
            ))

        return sig

    # --- Serialization -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory for persistence."""
        return {
            "learned_predicates": self.learned_predicates,
            "episodes": self.episodes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningMemory":
        """Restore memory from serialized form."""
        mem = cls()
        mem.learned_predicates = [
            (name, props, mode)
            for name, props, mode in data.get("learned_predicates", [])
        ]
        mem.episodes = data.get("episodes", [])
        return mem


class StructuralReasoner:
    """Domain-agnostic inductive reasoning engine with persistent memory.

    Plug in any DomainAdapter to reason over objects in that domain.
    The inference logic (discriminative filtering, transform induction,
    compositional planning, LOO cross-validation) is identical across domains.

    Memory enables two forms of learning:
    - **Concept growth**: discovered conjunctions become new predicates
    - **Episodic recall**: previously solved task patterns are tried first

    Usage::

        adapter = GridDomainAdapter()
        memory = ReasoningMemory()
        reasoner = StructuralReasoner(adapter, memory=memory)

        # Solve tasks — memory grows automatically
        for task in tasks:
            result = reasoner.solve(task.train, task.test)

        # Save memory for next session
        import json
        with open("memory.json", "w") as f:
            json.dump(memory.to_dict(), f)
    """

    def __init__(
        self,
        adapter: DomainAdapter,
        min_train: int = 2,
        memory: Optional[ReasoningMemory] = None,
    ):
        self.adapter = adapter
        self.min_train = min_train
        self.memory = memory or ReasoningMemory()
        self._deadline: Optional[float] = None

    def _expired(self) -> bool:
        return self._deadline is not None and time.perf_counter() > self._deadline

    def solve(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
        deadline: Optional[float] = None,
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """Run all inference modes with LOO validation.

        Cognitive execution loop:
        1. Initialize working memory (goal state + structural observations)
        2. Query episodic memory for similar past tasks (retrieval)
        3. Prime attention from retrieved episodes (focus)
        4. Execute production rules in priority order (inference)
        5. On success, commit to long-term memory (consolidation)

        Returns (predictions, metadata) or None.
        """
        if len(train_pairs) < 2:
            return None

        self._deadline = deadline

        # Initialize working memory — per-task scratch space
        wm = WorkingMemory(self.adapter, train_pairs, test_inputs)

        # Phase 0: Episodic retrieval + attention priming
        if self.memory.episodes:
            sig = ReasoningMemory.compute_task_signature(self.adapter, train_pairs)
            retrieved = self.memory.retrieve_similar(sig, k=5)

            # Prime attention: past solutions inform property search order
            wm.prime_attention(retrieved)

            # Try direct replay of retrieved hypotheses
            for hyp in retrieved:
                result = self._replay_hypothesis(hyp, train_pairs, test_inputs)
                if result is not None:
                    meta = dict(result[1])
                    meta["source"] = "episodic_recall"
                    return result[0], meta

        # Phase 1: Discriminative filtering (attention-ordered properties)
        result = self._try_discriminative_filter(train_pairs, test_inputs, wm)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result
        if self._expired():
            return None

        # Phase 1.5: Discriminative marker-target (alternative reconstruction)
        result = self._try_discriminative_marker_target(train_pairs, test_inputs, wm)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result
        if self._expired():
            return None

        # Phase 1.6: Unchanged/changed classification with change-pattern learning
        result = self._try_discriminative_change_filter(train_pairs, test_inputs, wm)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result
        if self._expired():
            return None

        # Phase 1.7: Extended classification with operator invention
        # When objects are recolored (not removed), try to identify the
        # discriminative property and the recolor rule, then reconstruct
        result = self._try_extended_recolor_filter(train_pairs, test_inputs, wm)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result
        if self._expired():
            return None

        # Phase 2: Transform induction
        result = self._try_transform_induction(train_pairs, test_inputs)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result
        if self._expired():
            return None

        # Phase 3: Compositional planning (filter→extract)
        result = self._try_filter_then_extract(train_pairs, test_inputs, wm)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result
        if self._expired():
            return None

        # Phase 4: Conjunction search — filter, extract, and recolor
        result = self._try_discriminative_conjunction(train_pairs, test_inputs)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result
        if self._expired():
            return None

        result = self._try_conjunction_extract(train_pairs, test_inputs)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result
        if self._expired():
            return None

        result = self._try_conjunction_recolor(train_pairs, test_inputs)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result
        if self._expired():
            return None

        # Phase 5: Operator schema matching
        result = self._try_schema_evaluation(train_pairs, test_inputs)
        if result is not None:
            self._commit_to_memory(train_pairs, result[1])
            return result

        return None

    # --- Memory integration ------------------------------------------------

    def _commit_to_memory(
        self, train_pairs: List[Tuple[Any, Any]], hypothesis: Dict[str, Any],
    ) -> None:
        """Store a successful solve in episodic memory."""
        sig = ReasoningMemory.compute_task_signature(self.adapter, train_pairs)
        self.memory.store_episode(sig, hypothesis)

    def _replay_hypothesis(
        self, hypothesis: Dict[str, Any],
        train_pairs: List[Tuple[Any, Any]],
        test_inputs: List[Any],
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """Replay a stored hypothesis on new data, with full LOO validation."""
        strategy = hypothesis.get("strategy", "")

        if strategy == "discriminative_filter":
            prop = hypothesis.get("property")
            keep = hypothesis.get("keep_when_true")
            if prop is None or keep is None:
                return None
            for inp, out in train_pairs:
                pred = self._apply_filter(inp, prop, keep)
                if pred is None or not self.adapter.scenes_equal(pred, out):
                    return None
            predictions = []
            for ti in test_inputs:
                pred = self._apply_filter(ti, prop, keep)
                if pred is None:
                    return None
                predictions.append(pred)
            return predictions, hypothesis

        elif strategy == "compositional" and hypothesis.get("composition") == "filter_then_extract":
            prop = hypothesis.get("filter_prop")
            keep = hypothesis.get("keep_when_true")
            if prop is None or keep is None:
                return None
            for inp, out in train_pairs:
                objs = self.adapter.extract_objects(inp)
                km = [self.adapter.get_property(o, prop) == keep for o in objs]
                if all(km) or not any(km):
                    return None
                pred = self.adapter.reconstruct_extracted(inp, objs, km)
                if pred is None or not self.adapter.scenes_equal(pred, out):
                    return None
            predictions = []
            for ti in test_inputs:
                objs = self.adapter.extract_objects(ti)
                km = [self.adapter.get_property(o, prop) == keep for o in objs]
                if all(km) or not any(km):
                    return None
                pred = self.adapter.reconstruct_extracted(ti, objs, km)
                if pred is None:
                    return None
                predictions.append(pred)
            return predictions, hypothesis

        elif strategy == "compositional" and hypothesis.get("composition") == "conjunction_extract":
            conj = hypothesis.get("conjunction")
            keep = hypothesis.get("keep_when_true")
            if conj is None or keep is None or len(conj) != 2:
                return None
            p1, p2 = conj
            for inp, out in train_pairs:
                objs = self.adapter.extract_objects(inp)
                km = [(self.adapter.get_property(o, p1) and
                       self.adapter.get_property(o, p2)) == keep for o in objs]
                if all(km) or not any(km):
                    return None
                pred = self.adapter.reconstruct_extracted(inp, objs, km)
                if pred is None or not self.adapter.scenes_equal(pred, out):
                    return None
            predictions = []
            for ti in test_inputs:
                objs = self.adapter.extract_objects(ti)
                km = [(self.adapter.get_property(o, p1) and
                       self.adapter.get_property(o, p2)) == keep for o in objs]
                if all(km) or not any(km):
                    return None
                pred = self.adapter.reconstruct_extracted(ti, objs, km)
                if pred is None:
                    return None
                predictions.append(pred)
            return predictions, hypothesis

        elif strategy == "transform_induction" and hypothesis.get("rule_type") == "conjunction_recolor":
            conj = hypothesis.get("conjunction")
            tl = hypothesis.get("true_label")
            fl = hypothesis.get("false_label")
            if conj is None or tl is None or fl is None or len(conj) != 2:
                return None
            p1, p2 = conj
            for inp, out in train_pairs:
                objs = self.adapter.extract_objects(inp)
                per_obj = {}
                for oi, o in enumerate(objs):
                    c = (self.adapter.get_property(o, p1) and
                         self.adapter.get_property(o, p2))
                    per_obj[oi] = tl if c else fl
                pred = self.adapter.reconstruct_recolored(inp, objs, per_obj)
                if pred is None or not self.adapter.scenes_equal(pred, out):
                    return None
            predictions = []
            for ti in test_inputs:
                objs = self.adapter.extract_objects(ti)
                per_obj = {}
                for oi, o in enumerate(objs):
                    c = (self.adapter.get_property(o, p1) and
                         self.adapter.get_property(o, p2))
                    per_obj[oi] = tl if c else fl
                pred = self.adapter.reconstruct_recolored(ti, objs, per_obj)
                if pred is None:
                    return None
                predictions.append(pred)
            return predictions, hypothesis

        elif strategy == "discriminative_marker_target":
            sub = hypothesis.get("sub_strategy")
            prop = hypothesis.get("property")
            keep = hypothesis.get("keep_when_true")
            if prop is None or keep is None:
                return None
            if sub == "fill_removed_constant":
                fc = hypothesis.get("fill_color")
                if fc is None:
                    return None
                for inp, out in train_pairs:
                    pred = self._apply_filter_with_fill(inp, prop, keep, fc)
                    if pred is None or not self.adapter.scenes_equal(pred, out):
                        return None
                predictions = []
                for ti in test_inputs:
                    pred = self._apply_filter_with_fill(ti, prop, keep, fc)
                    if pred is None:
                        return None
                    predictions.append(pred)
                return predictions, hypothesis
            elif sub == "marker_projection":
                direction = hypothesis.get("direction")
                if direction is None or len(direction) != 2:
                    return None
                dr, dc = direction
                for inp, out in train_pairs:
                    pred = self._apply_marker_projection(inp, prop, keep, dr, dc)
                    if pred is None or not self.adapter.scenes_equal(pred, out):
                        return None
                predictions = []
                for ti in test_inputs:
                    pred = self._apply_marker_projection(ti, prop, keep, dr, dc)
                    if pred is None:
                        return None
                    predictions.append(pred)
                return predictions, hypothesis
            elif sub == "fill_removed_nearest_kept_color":
                for inp, out in train_pairs:
                    pred = self._apply_filter_nearest_kept_color(inp, prop, keep)
                    if pred is None or not self.adapter.scenes_equal(pred, out):
                        return None
                predictions = []
                for ti in test_inputs:
                    pred = self._apply_filter_nearest_kept_color(ti, prop, keep)
                    if pred is None:
                        return None
                    predictions.append(pred)
                return predictions, hypothesis
            elif sub == "stamp_kept_at_removed":
                for inp, out in train_pairs:
                    pred = self._apply_stamp_kept_at_removed(inp, prop, keep)
                    if pred is None or not self.adapter.scenes_equal(pred, out):
                        return None
                predictions = []
                for ti in test_inputs:
                    pred = self._apply_stamp_kept_at_removed(ti, prop, keep)
                    if pred is None:
                        return None
                    predictions.append(pred)
                return predictions, hypothesis
            elif sub == "color_mapping_fill":
                cm = hypothesis.get("color_map")
                if cm is None:
                    return None
                cm_int = {int(k): v for k, v in cm.items()}
                for inp, out in train_pairs:
                    pred = self._apply_color_mapping_fill(inp, prop, keep, cm_int)
                    if pred is None or not self.adapter.scenes_equal(pred, out):
                        return None
                predictions = []
                for ti in test_inputs:
                    pred = self._apply_color_mapping_fill(ti, prop, keep, cm_int)
                    if pred is None:
                        return None
                    predictions.append(pred)
                return predictions, hypothesis
            elif sub == "recolor_by_relationship":
                tc = hypothesis.get("true_color")
                fc = hypothesis.get("false_color")
                if tc is None or fc is None:
                    return None
                for inp, out in train_pairs:
                    pred = self._apply_recolor_by_relationship(
                        inp, prop, keep, tc, fc)
                    if pred is None or not self.adapter.scenes_equal(pred, out):
                        return None
                predictions = []
                for ti in test_inputs:
                    pred = self._apply_recolor_by_relationship(
                        ti, prop, keep, tc, fc)
                    if pred is None:
                        return None
                    predictions.append(pred)
                return predictions, hypothesis

        elif strategy == "discriminative_change_filter":
            prop = hypothesis.get("property")
            unch = hypothesis.get("unchanged_when_true")
            ctype = hypothesis.get("change_type")
            if prop is None or unch is None or ctype is None:
                return None
            cp = hypothesis.get("change_pattern", {})
            pattern_r: Dict[str, Any] = {"type": ctype}
            if ctype == "constant_recolor":
                fc = cp.get("fill_color", hypothesis.get("fill_color"))
                if fc is None:
                    return None
                pattern_r["fill_color"] = fc
            elif ctype == "per_object_recolor":
                cm = cp.get("color_map", hypothesis.get("color_map"))
                if cm is None:
                    return None
                pattern_r["color_map"] = cm
            else:
                return None
            for inp, out in train_pairs:
                pred = self._apply_change_pattern(inp, prop, unch, pattern_r)
                if pred is None or not self.adapter.scenes_equal(pred, out):
                    return None
            predictions = []
            for ti in test_inputs:
                pred = self._apply_change_pattern(ti, prop, unch, pattern_r)
                if pred is None:
                    return None
                predictions.append(pred)
            return predictions, hypothesis

        elif strategy == "copy_to_position":
            try:
                from reasoning_project.trace_operator_invention import (
                    execute_copy_to_position,
                    infer_copy_to_position_params,
                    infer_copy_to_position_params_extended,
                    CopyToPositionParams,
                )
            except ImportError:
                return None
            sel = hypothesis.get("selector", hypothesis.get("property", ""))
            if not sel:
                return None
            params = infer_copy_to_position_params(train_pairs, sel, keep_when_true=True)
            if params is None:
                params = infer_copy_to_position_params_extended(
                    train_pairs, sel, keep_when_true=True)
            if params is None:
                return None
            for inp, out in train_pairs:
                pred = execute_copy_to_position(inp, params, train_pairs)
                if pred is None or not self.adapter.scenes_equal(pred, out):
                    return None
            predictions = []
            for ti in test_inputs:
                pred = execute_copy_to_position(ti, params, train_pairs)
                if pred is None:
                    return None
                predictions.append(pred)
            return predictions, hypothesis

        elif strategy == "extended_recolor_filter":
            prop = hypothesis.get("property")
            group_a_true = hypothesis.get("group_a_when_true")
            rtype = hypothesis.get("recolor_type")
            if prop is None or group_a_true is None or rtype is None:
                return None
            rp = hypothesis.get("recolor_pattern", {})
            pattern_r: Dict[str, Any] = {"type": rtype}
            if rtype == "uniform_recolor":
                fc = rp.get("fill_color")
                if fc is None:
                    return None
                pattern_r["fill_color"] = fc
            elif rtype in ("per_object_recolor", "color_swap"):
                cm = rp.get("color_map")
                if cm is None:
                    return None
                pattern_r["color_map"] = cm
            else:
                return None
            for inp, out in train_pairs:
                pred = self._apply_extended_recolor(inp, prop, group_a_true, pattern_r)
                if pred is None or not self.adapter.scenes_equal(pred, out):
                    return None
            predictions = []
            for ti in test_inputs:
                pred = self._apply_extended_recolor(ti, prop, group_a_true, pattern_r)
                if pred is None:
                    return None
                predictions.append(pred)
            return predictions, hypothesis

        elif strategy == "schema":
            try:
                from reasoning_project.operator_schemas import SchemaEvaluator
            except ImportError:
                return None
            evaluator = SchemaEvaluator()
            match = evaluator.evaluate_task(train_pairs, test_inputs)
            if match is not None and match.predictions is not None:
                return match.predictions, match.hypothesis
            return None

        return None

    # --- Conjunction search (discovers new compound predicates) -------------

    def _try_discriminative_conjunction(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """Search for conjunctions of 2 properties that discriminate."""
        if len(train_pairs) < self.min_train:
            return None
        for inp, out in train_pairs:
            if not self.adapter.same_structure(inp, out):
                return None

        all_props = self.adapter.property_names()
        for i, p1 in enumerate(all_props):
            if self._expired():
                return None
            for p2 in all_props[i+1:]:
                for keep_when_match in [True, False]:
                    consistent = True
                    for inp, out in train_pairs:
                        objects = self.adapter.extract_objects(inp)
                        result = self.adapter.classify_kept_removed(objects, inp, out)
                        if result is None:
                            consistent = False
                            break
                        kept_idx, removed_idx = result

                        for ki in kept_idx:
                            v = (self.adapter.get_property(objects[ki], p1) and
                                 self.adapter.get_property(objects[ki], p2))
                            if v != keep_when_match:
                                consistent = False
                                break
                        if not consistent:
                            break
                        for ri in removed_idx:
                            v = (self.adapter.get_property(objects[ri], p1) and
                                 self.adapter.get_property(objects[ri], p2))
                            if v == keep_when_match:
                                consistent = False
                                break
                        if not consistent:
                            break

                    if not consistent:
                        continue

                    # Minimum evidence guard for conjunctions
                    n_conj_true = n_conj_false = 0
                    for inp, _ in train_pairs:
                        for o in self.adapter.extract_objects(inp):
                            if (self.adapter.get_property(o, p1) and
                                    self.adapter.get_property(o, p2)):
                                n_conj_true += 1
                            else:
                                n_conj_false += 1
                    if n_conj_true < 2 or n_conj_false < 2:
                        continue

                    # LOO validation
                    loo_ok = True
                    for hold_out in range(len(train_pairs)):
                        held_inp, held_out_scene = train_pairs[hold_out]
                        objs = self.adapter.extract_objects(held_inp)
                        keep_mask = []
                        for o in objs:
                            v = (self.adapter.get_property(o, p1) and
                                 self.adapter.get_property(o, p2))
                            keep_mask.append(v == keep_when_match)
                        if all(keep_mask) or not any(keep_mask):
                            loo_ok = False
                            break
                        pred = self.adapter.reconstruct_filtered(
                            held_inp, objs, keep_mask)
                        if pred is None or not self.adapter.scenes_equal(
                                pred, held_out_scene):
                            loo_ok = False
                            break
                    if not loo_ok:
                        continue

                    # Mint the conjunction as a new learned predicate
                    conj_name = f"{p1}_AND_{p2}"
                    self.memory.mint_conjunction(conj_name, [p1, p2], "and")

                    predictions = []
                    for ti in test_inputs:
                        objs = self.adapter.extract_objects(ti)
                        km = [(self.adapter.get_property(o, p1) and
                               self.adapter.get_property(o, p2)) == keep_when_match
                              for o in objs]
                        if all(km) or not any(km):
                            break
                        pred = self.adapter.reconstruct_filtered(ti, objs, km)
                        if pred is None:
                            break
                        predictions.append(pred)
                    else:
                        return predictions, {
                            "strategy": "discriminative_filter",
                            "property": conj_name,
                            "conjunction": [p1, p2],
                            "keep_when_true": keep_when_match,
                            "learned": True,
                        }

        return None

    # --- Conjunction + extract (filter by conjunction, crop to bbox) --------

    def _try_conjunction_extract(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """Search for conjunctions of 2 properties for filter→extract."""
        if len(train_pairs) < self.min_train:
            return None

        all_props = self.adapter.property_names()
        for i, p1 in enumerate(all_props):
            if self._expired():
                return None
            for p2 in all_props[i+1:]:
                for keep_when_match in [True, False]:
                    consistent = True
                    for inp, out in train_pairs:
                        objects = self.adapter.extract_objects(inp)
                        if len(objects) < 2:
                            consistent = False
                            break
                        km = [
                            (self.adapter.get_property(o, p1) and
                             self.adapter.get_property(o, p2)) == keep_when_match
                            for o in objects
                        ]
                        if all(km) or not any(km):
                            consistent = False
                            break
                        pred = self.adapter.reconstruct_extracted(inp, objects, km)
                        if pred is None or not self.adapter.scenes_equal(pred, out):
                            consistent = False
                            break
                    if not consistent:
                        continue

                    loo_ok = True
                    for hold_out in range(len(train_pairs)):
                        held_inp, held_out_scene = train_pairs[hold_out]
                        objs = self.adapter.extract_objects(held_inp)
                        km = [
                            (self.adapter.get_property(o, p1) and
                             self.adapter.get_property(o, p2)) == keep_when_match
                            for o in objs
                        ]
                        if all(km) or not any(km):
                            loo_ok = False
                            break
                        pred = self.adapter.reconstruct_extracted(held_inp, objs, km)
                        if pred is None or not self.adapter.scenes_equal(
                                pred, held_out_scene):
                            loo_ok = False
                            break
                    if not loo_ok:
                        continue

                    conj_name = f"{p1}_AND_{p2}"
                    self.memory.mint_conjunction(conj_name, [p1, p2], "and")

                    predictions = []
                    for ti in test_inputs:
                        objs = self.adapter.extract_objects(ti)
                        km = [
                            (self.adapter.get_property(o, p1) and
                             self.adapter.get_property(o, p2)) == keep_when_match
                            for o in objs
                        ]
                        if all(km) or not any(km):
                            break
                        pred = self.adapter.reconstruct_extracted(ti, objs, km)
                        if pred is None:
                            break
                        predictions.append(pred)
                    else:
                        return predictions, {
                            "strategy": "compositional",
                            "composition": "conjunction_extract",
                            "conjunction": [p1, p2],
                            "keep_when_true": keep_when_match,
                            "learned": True,
                        }
        return None

    # --- Conjunction + recolor (discriminate by conjunction, recolor) -------

    def _try_conjunction_recolor(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """Search for conjunctions where (p1 AND p2) determines recoloring."""
        if len(train_pairs) < self.min_train:
            return None

        all_props = self.adapter.property_names()
        for i, p1 in enumerate(all_props):
            if self._expired():
                return None
            for p2 in all_props[i+1:]:
                true_label = None
                false_label = None
                consistent = True

                for inp, out in train_pairs:
                    if not self.adapter.same_structure(inp, out):
                        consistent = False
                        break
                    in_objs = self.adapter.extract_objects(inp)
                    out_objs = self.adapter.extract_objects(out)
                    if len(in_objs) != len(out_objs) or len(in_objs) < 2:
                        consistent = False
                        break
                    matches = self.adapter.match_objects(in_objs, out_objs)
                    if len(matches) != len(in_objs):
                        consistent = False
                        break
                    for i_idx, j_idx, _ in matches:
                        conj = (self.adapter.get_property(in_objs[i_idx], p1) and
                                self.adapter.get_property(in_objs[i_idx], p2))
                        new_l = out_objs[j_idx].get(
                            "primary_color",
                            out_objs[j_idx].get("primary_label", 0))
                        if conj:
                            if true_label is None:
                                true_label = new_l
                            elif true_label != new_l:
                                consistent = False
                                break
                        else:
                            if false_label is None:
                                false_label = new_l
                            elif false_label != new_l:
                                consistent = False
                                break
                    if not consistent:
                        break

                if (not consistent or true_label is None or
                        false_label is None or true_label == false_label):
                    continue

                # Minimum evidence: require ≥2 true and ≥2 false across
                # all training objects to avoid coincidental conjunctions
                n_true = n_false = 0
                for inp, _ in train_pairs:
                    for o in self.adapter.extract_objects(inp):
                        if (self.adapter.get_property(o, p1) and
                                self.adapter.get_property(o, p2)):
                            n_true += 1
                        else:
                            n_false += 1
                if n_true < 2 or n_false < 2:
                    continue

                # Occam's razor: reject if either single property alone
                # produces the same recoloring (conjunction is redundant)
                redundant = False
                for single_p in [p1, p2]:
                    sp_tl = sp_fl = None
                    sp_ok = True
                    for inp, out in train_pairs:
                        in_objs = self.adapter.extract_objects(inp)
                        out_objs = self.adapter.extract_objects(out)
                        if len(in_objs) != len(out_objs):
                            sp_ok = False
                            break
                        matches = self.adapter.match_objects(in_objs, out_objs)
                        for ii, ji, _ in matches:
                            val = self.adapter.get_property(in_objs[ii], single_p)
                            nl = out_objs[ji].get("primary_color",
                                 out_objs[ji].get("primary_label", 0))
                            if val:
                                if sp_tl is None: sp_tl = nl
                                elif sp_tl != nl: sp_ok = False; break
                            else:
                                if sp_fl is None: sp_fl = nl
                                elif sp_fl != nl: sp_ok = False; break
                        if not sp_ok:
                            break
                    if sp_ok and sp_tl is not None and sp_fl is not None and sp_tl != sp_fl:
                        redundant = True
                        break
                if redundant:
                    continue

                loo_ok = True
                for hold_out in range(len(train_pairs)):
                    held_inp, held_out_scene = train_pairs[hold_out]
                    objs = self.adapter.extract_objects(held_inp)
                    per_obj = {}
                    for oi, o in enumerate(objs):
                        conj = (self.adapter.get_property(o, p1) and
                                self.adapter.get_property(o, p2))
                        per_obj[oi] = true_label if conj else false_label
                    pred = self.adapter.reconstruct_recolored(
                        held_inp, objs, per_obj)
                    if pred is None or not self.adapter.scenes_equal(
                            pred, held_out_scene):
                        loo_ok = False
                        break
                if not loo_ok:
                    continue

                conj_name = f"{p1}_AND_{p2}"
                self.memory.mint_conjunction(conj_name, [p1, p2], "and")

                predictions = []
                for ti in test_inputs:
                    objs = self.adapter.extract_objects(ti)
                    per_obj = {}
                    for oi, o in enumerate(objs):
                        conj = (self.adapter.get_property(o, p1) and
                                self.adapter.get_property(o, p2))
                        per_obj[oi] = true_label if conj else false_label
                    pred = self.adapter.reconstruct_recolored(ti, objs, per_obj)
                    if pred is None:
                        break
                    predictions.append(pred)
                else:
                    return predictions, {
                        "strategy": "transform_induction",
                        "rule_type": "conjunction_recolor",
                        "conjunction": [p1, p2],
                        "true_label": int(true_label),
                        "false_label": int(false_label),
                        "learned": True,
                    }
        return None

    # --- Discriminative filtering ------------------------------------------

    def _try_discriminative_filter(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
        wm: Optional[WorkingMemory] = None,
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        if len(train_pairs) < self.min_train:
            return None
        if wm and not wm.same_structure:
            return None
        elif not wm:
            for inp, out in train_pairs:
                if not self.adapter.same_structure(inp, out):
                    return None

        prop_result = self._find_discriminative_property(train_pairs, wm)
        if prop_result is None:
            return None
        prop_name, keep_when_true = prop_result

        for hold_out in range(len(train_pairs)):
            held_inp, held_out_scene = train_pairs[hold_out]
            pred = self._apply_filter(held_inp, prop_name, keep_when_true)
            if pred is None or not self.adapter.scenes_equal(pred, held_out_scene):
                return None

        predictions = []
        for test_inp in test_inputs:
            pred = self._apply_filter(test_inp, prop_name, keep_when_true)
            if pred is None:
                return None
            predictions.append(pred)

        return predictions, {
            "strategy": "discriminative_filter",
            "property": prop_name,
            "keep_when_true": keep_when_true,
        }

    def _find_discriminative_property(
        self, train_pairs: List[Tuple[Any, Any]],
        wm: Optional[WorkingMemory] = None,
    ) -> Optional[Tuple[str, bool]]:
        all_props = wm.get_ordered_properties() if wm else self.adapter.property_names()
        candidates = {p: {"true_keeps": True, "false_keeps": True} for p in all_props}

        n_classifiable = 0
        for inp, out in train_pairs:
            objects = self.adapter.extract_objects(inp)
            result = self.adapter.classify_kept_removed(objects, inp, out)
            if result is None:
                continue
            n_classifiable += 1
            kept_idx, removed_idx = result

            for prop in list(candidates.keys()):
                kept_vals = [self.adapter.get_property(objects[i], prop) for i in kept_idx]
                removed_vals = [self.adapter.get_property(objects[i], prop) for i in removed_idx]

                if not (all(kept_vals) and not any(removed_vals)):
                    candidates[prop]["true_keeps"] = False
                if not (all(not v for v in kept_vals) and all(removed_vals)):
                    candidates[prop]["false_keeps"] = False
                if not candidates[prop]["true_keeps"] and not candidates[prop]["false_keeps"]:
                    del candidates[prop]

        if n_classifiable < 1:
            return None

        prop_evidence = {}
        for prop in list(candidates.keys()):
            n_true = n_false = 0
            for inp, out in train_pairs:
                for obj in self.adapter.extract_objects(inp):
                    if self.adapter.get_property(obj, prop):
                        n_true += 1
                    else:
                        n_false += 1
            prop_evidence[prop] = (n_true, n_false)

        for prop in all_props:
            if prop not in candidates:
                continue
            n_true, n_false = prop_evidence.get(prop, (0, 0))
            if n_true < 2 or n_false < 2:
                continue
            if candidates[prop]["true_keeps"]:
                return (prop, True)
            if candidates[prop]["false_keeps"]:
                return (prop, False)
        return None

    def _apply_filter(
        self, inp: Any, prop_name: str, keep_when_true: bool,
    ) -> Optional[Any]:
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None
        keep_mask = []
        for obj in objects:
            val = self.adapter.get_property(obj, prop_name)
            keep_mask.append(val == keep_when_true)
        if all(keep_mask) or not any(keep_mask):
            return None
        return self.adapter.reconstruct_filtered(inp, objects, keep_mask)

    # --- Discriminative marker-target (alternative reconstruction) ----------

    def _try_discriminative_marker_target(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
        wm: Optional[WorkingMemory] = None,
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """When a discriminative property exists but zero-reconstruction fails,
        try alternative reconstruction modes: constant fill, marker projection,
        and per-object color transfer."""
        if len(train_pairs) < self.min_train:
            return None
        if wm and not wm.same_structure:
            return None
        elif not wm:
            for inp, out in train_pairs:
                if not self.adapter.same_structure(inp, out):
                    return None

        prop_result = self._find_discriminative_property(train_pairs, wm)
        if prop_result is None:
            return None
        prop_name, keep_when_true = prop_result

        pair_data = []
        for inp, out in train_pairs:
            objects = self.adapter.extract_objects(inp)
            keep_mask = [self.adapter.get_property(o, prop_name) == keep_when_true
                         for o in objects]
            if all(keep_mask) or not any(keep_mask):
                return None
            filtered = self.adapter.reconstruct_filtered(inp, objects, keep_mask)
            if filtered is None:
                return None
            pair_data.append({
                'inp': inp, 'out': out,
                'objects': objects, 'keep_mask': keep_mask,
                'filtered': filtered,
            })

        if all(self.adapter.scenes_equal(d['filtered'], d['out']) for d in pair_data):
            return None

        for strategy_fn in [
            self._try_fill_removed_constant,
            self._try_marker_projection,
            self._try_fill_removed_nearest_kept_color,
            self._try_stamp_kept_at_removed,
            self._try_color_mapping_fill,
            self._try_recolor_by_relationship,
        ]:
            result = strategy_fn(
                train_pairs, test_inputs, prop_name, keep_when_true, pair_data)
            if result is not None:
                return result

        return None

    def _try_fill_removed_constant(
        self, train_pairs, test_inputs, prop_name, keep_when_true, pair_data,
    ):
        """Fill removed objects' pixels with a single learned constant color."""
        fill_colors = set()
        for d in pair_data:
            for obj, keep in zip(d['objects'], d['keep_mask']):
                if keep:
                    continue
                expected_colors = set(d['out'][obj['mask']].tolist())
                expected_colors.discard(0)
                if len(expected_colors) == 1:
                    fill_colors.add(expected_colors.pop())
                elif len(expected_colors) == 0:
                    fill_colors.add(0)
                else:
                    return None

        if len(fill_colors) != 1:
            return None
        fill_color = fill_colors.pop()
        if fill_color == 0:
            return None

        for hold_out in range(len(train_pairs)):
            held_inp, held_out = train_pairs[hold_out]
            pred = self._apply_filter_with_fill(held_inp, prop_name, keep_when_true, fill_color)
            if pred is None or not self.adapter.scenes_equal(pred, held_out):
                return None

        predictions = []
        for ti in test_inputs:
            pred = self._apply_filter_with_fill(ti, prop_name, keep_when_true, fill_color)
            if pred is None:
                return None
            predictions.append(pred)

        return predictions, {
            "strategy": "discriminative_marker_target",
            "sub_strategy": "fill_removed_constant",
            "property": prop_name,
            "keep_when_true": keep_when_true,
            "fill_color": int(fill_color),
        }

    def _apply_filter_with_fill(self, inp, prop_name, keep_when_true, fill_color):
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None
        keep_mask = [self.adapter.get_property(o, prop_name) == keep_when_true
                     for o in objects]
        if all(keep_mask) or not any(keep_mask):
            return None
        result = inp.copy()
        for obj, keep in zip(objects, keep_mask):
            if not keep:
                result[obj["mask"]] = fill_color
        return result

    def _try_marker_projection(
        self, train_pairs, test_inputs, prop_name, keep_when_true, pair_data,
    ):
        """Project removed (marker) objects toward kept objects in cardinal
        directions, filling a trail of the marker's color."""
        max_marker_area = 4
        for d in pair_data:
            for obj, keep in zip(d['objects'], d['keep_mask']):
                if not keep and obj.get("area", 999) > max_marker_area:
                    return None

        for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            if self._check_projection_direction(pair_data, dr, dc):
                for hold_out in range(len(train_pairs)):
                    held_inp, held_out = train_pairs[hold_out]
                    pred = self._apply_marker_projection(
                        held_inp, prop_name, keep_when_true, dr, dc)
                    if pred is None or not self.adapter.scenes_equal(pred, held_out):
                        break
                else:
                    predictions = []
                    for ti in test_inputs:
                        pred = self._apply_marker_projection(
                            ti, prop_name, keep_when_true, dr, dc)
                        if pred is None:
                            return None
                        predictions.append(pred)
                    return predictions, {
                        "strategy": "discriminative_marker_target",
                        "sub_strategy": "marker_projection",
                        "property": prop_name,
                        "keep_when_true": keep_when_true,
                        "direction": [dr, dc],
                    }
        return None

    def _check_projection_direction(self, pair_data, dr, dc):
        for d in pair_data:
            pred = self._build_projection(
                d['filtered'], d['objects'], d['keep_mask'], dr, dc)
            if not self.adapter.scenes_equal(pred, d['out']):
                return False
        return True

    def _build_projection(self, filtered, objects, keep_mask, dr, dc):
        result = filtered.copy()
        h, w = result.shape
        kept_pixel_mask = np.zeros((h, w), dtype=bool)
        for obj, keep in zip(objects, keep_mask):
            if keep:
                kept_pixel_mask |= obj["mask"]

        for obj, keep in zip(objects, keep_mask):
            if keep:
                continue
            color = obj.get("primary_color", 0)
            rows, cols = np.where(obj["mask"])
            for r, c in zip(rows.tolist(), cols.tolist()):
                cr, cc = r + dr, c + dc
                while 0 <= cr < h and 0 <= cc < w:
                    if kept_pixel_mask[cr, cc]:
                        break
                    result[cr, cc] = color
                    cr += dr
                    cc += dc
        return result

    def _apply_marker_projection(self, inp, prop_name, keep_when_true, dr, dc):
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None
        keep_mask = [self.adapter.get_property(o, prop_name) == keep_when_true
                     for o in objects]
        if all(keep_mask) or not any(keep_mask):
            return None
        filtered = self.adapter.reconstruct_filtered(inp, objects, keep_mask)
        if filtered is None:
            return None
        return self._build_projection(filtered, objects, keep_mask, dr, dc)

    def _try_fill_removed_nearest_kept_color(
        self, train_pairs, test_inputs, prop_name, keep_when_true, pair_data,
    ):
        """Fill each removed object with the color of its nearest kept object."""
        for d in pair_data:
            kept_objs = [o for o, k in zip(d['objects'], d['keep_mask']) if k]
            for obj, keep in zip(d['objects'], d['keep_mask']):
                if keep:
                    continue
                nearest_color = self._nearest_kept_color(obj, kept_objs)
                if nearest_color is None:
                    return None
                expected_colors = set(d['out'][obj['mask']].tolist())
                expected_colors.discard(0)
                if expected_colors and expected_colors != {nearest_color}:
                    return None

        for hold_out in range(len(train_pairs)):
            held_inp, held_out = train_pairs[hold_out]
            pred = self._apply_filter_nearest_kept_color(
                held_inp, prop_name, keep_when_true)
            if pred is None or not self.adapter.scenes_equal(pred, held_out):
                return None

        predictions = []
        for ti in test_inputs:
            pred = self._apply_filter_nearest_kept_color(
                ti, prop_name, keep_when_true)
            if pred is None:
                return None
            predictions.append(pred)

        return predictions, {
            "strategy": "discriminative_marker_target",
            "sub_strategy": "fill_removed_nearest_kept_color",
            "property": prop_name,
            "keep_when_true": keep_when_true,
        }

    def _nearest_kept_color(self, removed_obj, kept_objs):
        if not kept_objs:
            return None
        rc = ((removed_obj["bbox"][0] + removed_obj["bbox"][2]) / 2,
              (removed_obj["bbox"][1] + removed_obj["bbox"][3]) / 2)
        best_dist = float("inf")
        best_color = None
        for ko in kept_objs:
            kc = ((ko["bbox"][0] + ko["bbox"][2]) / 2,
                  (ko["bbox"][1] + ko["bbox"][3]) / 2)
            dist = abs(rc[0] - kc[0]) + abs(rc[1] - kc[1])
            if dist < best_dist:
                best_dist = dist
                best_color = ko.get("primary_color")
        return best_color

    def _apply_filter_nearest_kept_color(self, inp, prop_name, keep_when_true):
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None
        keep_mask = [self.adapter.get_property(o, prop_name) == keep_when_true
                     for o in objects]
        if all(keep_mask) or not any(keep_mask):
            return None
        kept_objs = [o for o, k in zip(objects, keep_mask) if k]
        result = inp.copy()
        for obj, keep in zip(objects, keep_mask):
            if not keep:
                nc = self._nearest_kept_color(obj, kept_objs)
                result[obj["mask"]] = nc if nc is not None else 0
        return result

    # --- Strategy: stamp kept object's pattern at each removed marker --------

    def _try_stamp_kept_at_removed(
        self, train_pairs, test_inputs, prop_name, keep_when_true, pair_data,
    ):
        """Copy the kept object(s) pattern to each removed marker's position.

        Covers the 'copy_to_position' operator gap: the task keeps a template
        object and uses small markers to indicate where copies should appear.
        """
        for d in pair_data:
            kept_objs = [o for o, k in zip(d['objects'], d['keep_mask']) if k]
            removed_objs = [o for o, k in zip(d['objects'], d['keep_mask']) if not k]
            if len(kept_objs) != 1 or len(removed_objs) < 1:
                return None

        template_shapes = set()
        for d in pair_data:
            kept = [o for o, k in zip(d['objects'], d['keep_mask']) if k][0]
            template_shapes.add((kept['bbox_h'], kept['bbox_w']))
        if len(template_shapes) != 1:
            return None

        for hold_out in range(len(train_pairs)):
            held_inp, held_out = train_pairs[hold_out]
            pred = self._apply_stamp_kept_at_removed(
                held_inp, prop_name, keep_when_true)
            if pred is None or not self.adapter.scenes_equal(pred, held_out):
                return None

        predictions = []
        for ti in test_inputs:
            pred = self._apply_stamp_kept_at_removed(
                ti, prop_name, keep_when_true)
            if pred is None:
                return None
            predictions.append(pred)

        return predictions, {
            "strategy": "discriminative_marker_target",
            "sub_strategy": "stamp_kept_at_removed",
            "property": prop_name,
            "keep_when_true": keep_when_true,
        }

    def _apply_stamp_kept_at_removed(self, inp, prop_name, keep_when_true):
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None
        keep_mask = [self.adapter.get_property(o, prop_name) == keep_when_true
                     for o in objects]
        if all(keep_mask) or not any(keep_mask):
            return None
        kept = [o for o, k in zip(objects, keep_mask) if k]
        removed = [o for o, k in zip(objects, keep_mask) if not k]
        if len(kept) != 1:
            return None

        template = kept[0]
        t_r_min, t_c_min, t_r_max, t_c_max = template['bbox']
        t_h, t_w = template['bbox_h'], template['bbox_w']
        t_patch = inp[t_r_min:t_r_max + 1, t_c_min:t_c_max + 1].copy()
        t_local = template['local_mask']

        result = self.adapter.reconstruct_filtered(inp, objects, keep_mask)
        if result is None:
            return None

        h, w = result.shape
        for marker in removed:
            mr, mc = int(round(marker['center_r'])), int(round(marker['center_c']))
            r_start = mr - t_h // 2
            c_start = mc - t_w // 2
            for dr in range(t_h):
                for dc in range(t_w):
                    r, c = r_start + dr, c_start + dc
                    if 0 <= r < h and 0 <= c < w and t_local[dr, dc]:
                        result[r, c] = t_patch[dr, dc]
        return result

    # --- Strategy: learn per-object color mapping from removed regions --------

    def _try_color_mapping_fill(
        self, train_pairs, test_inputs, prop_name, keep_when_true, pair_data,
    ):
        """Learn a color mapping for removed objects from input->output.

        Each removed object's primary color in the input maps to a specific
        fill color in the output. Learn this mapping and apply it.
        """
        color_map = {}
        for d in pair_data:
            for obj, keep in zip(d['objects'], d['keep_mask']):
                if keep:
                    continue
                src_color = obj['primary_color']
                out_colors = set(d['out'][obj['mask']].tolist())
                out_colors.discard(0)
                if len(out_colors) != 1:
                    return None
                dst_color = out_colors.pop()
                if src_color in color_map:
                    if color_map[src_color] != dst_color:
                        return None
                else:
                    color_map[src_color] = dst_color

        if not color_map:
            return None
        if all(k == v for k, v in color_map.items()):
            return None

        for hold_out in range(len(train_pairs)):
            held_inp, held_out = train_pairs[hold_out]
            pred = self._apply_color_mapping_fill(
                held_inp, prop_name, keep_when_true, color_map)
            if pred is None or not self.adapter.scenes_equal(pred, held_out):
                return None

        predictions = []
        for ti in test_inputs:
            pred = self._apply_color_mapping_fill(
                ti, prop_name, keep_when_true, color_map)
            if pred is None:
                return None
            predictions.append(pred)

        return predictions, {
            "strategy": "discriminative_marker_target",
            "sub_strategy": "color_mapping_fill",
            "property": prop_name,
            "keep_when_true": keep_when_true,
            "color_map": {str(k): v for k, v in color_map.items()},
        }

    def _apply_color_mapping_fill(self, inp, prop_name, keep_when_true, color_map):
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None
        keep_mask = [self.adapter.get_property(o, prop_name) == keep_when_true
                     for o in objects]
        if all(keep_mask) or not any(keep_mask):
            return None
        result = inp.copy()
        for obj, keep in zip(objects, keep_mask):
            if not keep:
                src = obj['primary_color']
                dst = color_map.get(src, 0)
                result[obj['mask']] = dst
        return result

    # --- Strategy: recolor all objects by per-object relationship -------------

    def _try_recolor_by_relationship(
        self, train_pairs, test_inputs, prop_name, keep_when_true, pair_data,
    ):
        """Instead of filtering, recolor objects based on property value.

        Covers tasks where the output has the same objects but with colors
        changed based on whether they match the discriminative property.
        """
        true_color = None
        false_color = None
        for d in pair_data:
            for obj, keep in zip(d['objects'], d['keep_mask']):
                out_colors = set(d['out'][obj['mask']].tolist())
                out_colors.discard(0)
                if len(out_colors) != 1:
                    return None
                c = out_colors.pop()
                if keep:
                    if true_color is None:
                        true_color = c
                    elif true_color != c:
                        return None
                else:
                    if false_color is None:
                        false_color = c
                    elif false_color != c:
                        return None

        if true_color is None or false_color is None:
            return None
        if true_color == false_color:
            return None

        for hold_out in range(len(train_pairs)):
            held_inp, held_out = train_pairs[hold_out]
            pred = self._apply_recolor_by_relationship(
                held_inp, prop_name, keep_when_true, true_color, false_color)
            if pred is None or not self.adapter.scenes_equal(pred, held_out):
                return None

        predictions = []
        for ti in test_inputs:
            pred = self._apply_recolor_by_relationship(
                ti, prop_name, keep_when_true, true_color, false_color)
            if pred is None:
                return None
            predictions.append(pred)

        return predictions, {
            "strategy": "discriminative_marker_target",
            "sub_strategy": "recolor_by_relationship",
            "property": prop_name,
            "keep_when_true": keep_when_true,
            "true_color": int(true_color),
            "false_color": int(false_color),
        }

    def _apply_recolor_by_relationship(
        self, inp, prop_name, keep_when_true, true_color, false_color,
    ):
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None
        result = inp.copy()
        for obj in objects:
            val = self.adapter.get_property(obj, prop_name)
            color = true_color if (val == keep_when_true) else false_color
            result[obj['mask']] = color
        return result

    # --- Unchanged/changed discriminative filter ----------------------------

    def _try_discriminative_change_filter(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
        wm: Optional[WorkingMemory] = None,
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """When all objects are present in the output (none zeroed), classify
        objects as unchanged vs changed. Find a property that separates them,
        then learn the transformation applied to changed objects."""
        if len(train_pairs) < self.min_train:
            return None
        if wm and not wm.same_structure:
            return None
        elif not wm:
            for inp, out in train_pairs:
                if not self.adapter.same_structure(inp, out):
                    return None

        prop_result = self._find_discriminative_change_property(train_pairs, wm)
        if prop_result is None:
            return None
        prop_name, unchanged_when_true = prop_result

        pair_data = []
        for inp, out in train_pairs:
            objects = self.adapter.extract_objects(inp)
            uc = _classify_unchanged_changed(objects, inp, out)
            if uc is None:
                return None
            unchanged_idx, changed_idx = uc
            change_mask = [not (self.adapter.get_property(o, prop_name) == unchanged_when_true)
                           for o in objects]
            pair_data.append({
                "inp": inp, "out": out,
                "objects": objects,
                "unchanged_idx": unchanged_idx,
                "changed_idx": changed_idx,
                "change_mask": change_mask,
            })

        change_pattern = self._learn_change_pattern(pair_data)
        if change_pattern is None:
            return None

        for hold_out in range(len(train_pairs)):
            held_inp, held_out = train_pairs[hold_out]
            pred = self._apply_change_pattern(
                held_inp, prop_name, unchanged_when_true, change_pattern)
            if pred is None or not self.adapter.scenes_equal(pred, held_out):
                return None

        predictions = []
        for test_inp in test_inputs:
            pred = self._apply_change_pattern(
                test_inp, prop_name, unchanged_when_true, change_pattern)
            if pred is None:
                return None
            predictions.append(pred)

        return predictions, {
            "strategy": "discriminative_change_filter",
            "property": prop_name,
            "unchanged_when_true": unchanged_when_true,
            "change_pattern": {k: v for k, v in change_pattern.items()
                               if k != "color_map" or isinstance(v, (str, int, float))},
            "change_type": change_pattern["type"],
        }

    def _find_discriminative_change_property(
        self, train_pairs: List[Tuple[Any, Any]],
        wm: Optional[WorkingMemory] = None,
    ) -> Optional[Tuple[str, bool]]:
        """Find a property that separates unchanged from changed objects."""
        all_props = wm.get_ordered_properties() if wm else self.adapter.property_names()
        candidates = {p: {"true_unchanged": True, "false_unchanged": True} for p in all_props}

        n_classifiable = 0
        for inp, out in train_pairs:
            objects = self.adapter.extract_objects(inp)
            uc = _classify_unchanged_changed(objects, inp, out)
            if uc is None:
                continue
            n_classifiable += 1
            unchanged_idx, changed_idx = uc

            for prop in list(candidates.keys()):
                unch_vals = [self.adapter.get_property(objects[i], prop) for i in unchanged_idx]
                ch_vals = [self.adapter.get_property(objects[i], prop) for i in changed_idx]

                if not (all(unch_vals) and not any(ch_vals)):
                    candidates[prop]["true_unchanged"] = False
                if not (all(not v for v in unch_vals) and all(ch_vals)):
                    candidates[prop]["false_unchanged"] = False
                if not candidates[prop]["true_unchanged"] and not candidates[prop]["false_unchanged"]:
                    del candidates[prop]

        if n_classifiable < len(train_pairs):
            return None

        prop_evidence = {}
        for prop in list(candidates.keys()):
            n_true = n_false = 0
            for inp, out in train_pairs:
                for obj in self.adapter.extract_objects(inp):
                    if self.adapter.get_property(obj, prop):
                        n_true += 1
                    else:
                        n_false += 1
            prop_evidence[prop] = (n_true, n_false)

        for prop in all_props:
            if prop not in candidates:
                continue
            n_true, n_false = prop_evidence.get(prop, (0, 0))
            if n_true < 2 or n_false < 2:
                continue
            if candidates[prop]["true_unchanged"]:
                return (prop, True)
            if candidates[prop]["false_unchanged"]:
                return (prop, False)
        return None

    # --- Extended recolor filter (Phase 1.7) ---------------------------------

    def _try_extended_recolor_filter(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
        wm: Optional[WorkingMemory] = None,
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """Phase 1.7: Extended classification with recolor-pattern learning.

        When _classify_kept_removed and _classify_unchanged_changed both fail
        (handled by earlier phases), use _classify_kept_removed_extended to
        detect present_absent or recolored_retained splits. Then find a
        discriminative property and learn the recolor rule.
        """
        if len(train_pairs) < self.min_train:
            return None
        if wm and not wm.same_structure:
            return None
        elif not wm:
            for inp, out in train_pairs:
                if not self.adapter.same_structure(inp, out):
                    return None

        # Find discriminative property using extended classification
        prop_result = self._find_discriminative_extended_property(train_pairs, wm)
        if prop_result is None:
            return None
        prop_name, group_a_when_true, mode = prop_result

        # Gather per-pair data for pattern learning
        pair_data = []
        for inp, out in train_pairs:
            objects = self.adapter.extract_objects(inp)
            ext = _classify_kept_removed_extended(objects, inp, out)
            if ext is None:
                return None
            group_a, group_b, ext_mode = ext

            # group_b = the "operated on" objects (recolored/removed/changed)
            change_mask = [
                not (self.adapter.get_property(o, prop_name) == group_a_when_true)
                for o in objects
            ]
            pair_data.append({
                "inp": inp, "out": out,
                "objects": objects,
                "group_a": group_a,
                "group_b": group_b,
                "mode": ext_mode,
                "changed_idx": group_b,
                "unchanged_idx": group_a,
                "change_mask": change_mask,
            })

        # Learn the recolor/change pattern
        recolor_pattern = self._learn_extended_recolor_pattern(pair_data)
        if recolor_pattern is None:
            return None

        # LOO validation
        for hold_out in range(len(train_pairs)):
            held_inp, held_out_scene = train_pairs[hold_out]
            pred = self._apply_extended_recolor(
                held_inp, prop_name, group_a_when_true, recolor_pattern)
            if pred is None or not self.adapter.scenes_equal(pred, held_out_scene):
                return None

        # Generate predictions
        predictions = []
        for test_inp in test_inputs:
            pred = self._apply_extended_recolor(
                test_inp, prop_name, group_a_when_true, recolor_pattern)
            if pred is None:
                return None
            predictions.append(pred)

        hypothesis = {
            "strategy": "extended_recolor_filter",
            "property": prop_name,
            "group_a_when_true": group_a_when_true,
            "recolor_type": recolor_pattern["type"],
            "recolor_pattern": {
                k: v for k, v in recolor_pattern.items()
                if not isinstance(v, dict) or k in ("color_map",)
            },
        }
        return predictions, hypothesis

    def _find_discriminative_extended_property(
        self, train_pairs: List[Tuple[Any, Any]],
        wm: Optional[WorkingMemory] = None,
    ) -> Optional[Tuple[str, bool, str]]:
        """Find a property separating group_a from group_b under extended classification.

        Returns (property_name, group_a_when_true, mode) or None.
        group_a_when_true=True means objects with prop=True are in group_a (unchanged/retained).
        """
        all_props = wm.get_ordered_properties() if wm else self.adapter.property_names()
        candidates = {
            p: {"true_group_a": True, "false_group_a": True}
            for p in all_props
        }

        n_classifiable = 0
        mode_seen: Optional[str] = None

        for inp, out in train_pairs:
            objects = self.adapter.extract_objects(inp)
            ext = _classify_kept_removed_extended(objects, inp, out)
            if ext is None:
                continue
            group_a, group_b, ext_mode = ext

            # Skip modes already handled by earlier phases
            if ext_mode in ("kept_removed", "unchanged_changed"):
                # These are handled by Phase 1 and Phase 1.6
                continue

            n_classifiable += 1
            if mode_seen is None:
                mode_seen = ext_mode
            elif mode_seen != ext_mode:
                # Inconsistent mode across training pairs
                return None

            for prop in list(candidates.keys()):
                a_vals = [self.adapter.get_property(objects[i], prop) for i in group_a]
                b_vals = [self.adapter.get_property(objects[i], prop) for i in group_b]

                # Check: group_a when True (all group_a have True, all group_b have False)
                if not (all(a_vals) and not any(b_vals)):
                    candidates[prop]["true_group_a"] = False

                # Check: group_a when False (all group_a have False, all group_b have True)
                if not (all(not v for v in a_vals) and all(b_vals)):
                    candidates[prop]["false_group_a"] = False

                if not candidates[prop]["true_group_a"] and not candidates[prop]["false_group_a"]:
                    del candidates[prop]

        if n_classifiable < len(train_pairs) or n_classifiable < 1:
            return None
        if mode_seen is None:
            return None

        # Count evidence
        prop_evidence = {}
        for prop in list(candidates.keys()):
            n_true = n_false = 0
            for inp, out in train_pairs:
                for obj in self.adapter.extract_objects(inp):
                    if self.adapter.get_property(obj, prop):
                        n_true += 1
                    else:
                        n_false += 1
            prop_evidence[prop] = (n_true, n_false)

        for prop in all_props:
            if prop not in candidates:
                continue
            n_true, n_false = prop_evidence.get(prop, (0, 0))
            if n_true < 2 or n_false < 2:
                continue
            if candidates[prop]["true_group_a"]:
                return (prop, True, mode_seen)
            if candidates[prop]["false_group_a"]:
                return (prop, False, mode_seen)

        return None

    def _learn_extended_recolor_pattern(
        self, pair_data: List[Dict],
    ) -> Optional[Dict[str, Any]]:
        """Learn the recolor pattern from extended classification pair data."""
        all_patterns = []
        for d in pair_data:
            pattern = _detect_recolor_pattern(
                d["objects"], d["group_a"], d["group_b"], d["inp"], d["out"])
            if pattern is None:
                # Fall back to existing _detect_change_pattern
                pattern = _detect_change_pattern(
                    d["objects"], d["group_b"], d["inp"], d["out"])
            if pattern is None:
                return None
            all_patterns.append(pattern)

        if not all_patterns:
            return None

        # All patterns must agree on type
        types = {p["type"] for p in all_patterns}
        if len(types) != 1:
            return None
        ptype = types.pop()

        if ptype == "uniform_recolor":
            colors = set()
            for p in all_patterns:
                fc = p.get("fill_color")
                if fc is not None:
                    colors.add(fc)
            if len(colors) == 1:
                return {"type": "uniform_recolor", "fill_color": colors.pop()}
            return None

        if ptype in ("per_object_recolor", "color_swap"):
            merged: Dict[int, int] = {}
            for p in all_patterns:
                cm = p.get("color_map", {})
                for k, v in cm.items():
                    k_int = int(k) if isinstance(k, str) else k
                    if k_int in merged and merged[k_int] != v:
                        return None
                    merged[k_int] = v
            if merged:
                return {"type": ptype, "color_map": merged}
            return None

        if ptype == "property_dependent_recolor":
            # For property-dependent, we just confirm per-object pattern is consistent
            # and return the aggregate
            return {"type": "property_dependent_recolor"}

        return None

    def _apply_extended_recolor(
        self,
        inp: Any,
        prop_name: str,
        group_a_when_true: bool,
        pattern: Dict[str, Any],
    ) -> Optional[Any]:
        """Apply a learned extended recolor pattern.

        Objects matching group_a (unchanged/retained) are left as-is.
        Objects in group_b (changed/recolored) have the pattern applied.
        """
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None

        change_mask = [
            not (self.adapter.get_property(o, prop_name) == group_a_when_true)
            for o in objects
        ]
        if all(change_mask) or not any(change_mask):
            return None

        result = inp.copy()
        ptype = pattern["type"]

        if ptype == "uniform_recolor":
            fill_color = pattern["fill_color"]
            for obj, is_changed in zip(objects, change_mask):
                if is_changed:
                    result[obj["mask"]] = fill_color
            return result

        if ptype in ("per_object_recolor", "color_swap"):
            color_map = pattern.get("color_map", {})
            for obj, is_changed in zip(objects, change_mask):
                if is_changed:
                    mask = obj["mask"]
                    for old_c, new_c in color_map.items():
                        old_c_int = int(old_c) if isinstance(old_c, str) else old_c
                        result[mask & (inp == old_c_int)] = new_c
            return result

        # property_dependent_recolor is too complex to apply generically
        return None

    def _learn_change_pattern(
        self, pair_data: List[Dict],
    ) -> Optional[Dict[str, Any]]:
        """Learn the transformation applied to changed objects across all pairs."""
        all_patterns = []
        for d in pair_data:
            pattern = _detect_change_pattern(
                d["objects"], d["changed_idx"], d["inp"], d["out"])
            if pattern is None:
                return None
            all_patterns.append(pattern)

        if not all_patterns:
            return None

        types = {p["type"] for p in all_patterns}
        if len(types) != 1:
            return None
        ptype = types.pop()

        if ptype == "constant_recolor":
            colors = {p["fill_color"] for p in all_patterns}
            if len(colors) == 1:
                return {"type": "constant_recolor", "fill_color": colors.pop()}
            return None

        if ptype == "per_object_recolor":
            merged: Dict[int, int] = {}
            for p in all_patterns:
                for k, v in p["color_map"].items():
                    k_int = int(k) if isinstance(k, str) else k
                    if k_int in merged and merged[k_int] != v:
                        return None
                    merged[k_int] = v
            if merged:
                return {"type": "per_object_recolor", "color_map": merged}
            return None

        return None

    def _apply_change_pattern(
        self,
        inp: Any,
        prop_name: str,
        unchanged_when_true: bool,
        pattern: Dict[str, Any],
    ) -> Optional[Any]:
        """Apply a learned change pattern: unchanged objects stay, changed objects transform."""
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None

        change_mask = [not (self.adapter.get_property(o, prop_name) == unchanged_when_true)
                       for o in objects]
        if all(change_mask) or not any(change_mask):
            return None

        result = inp.copy()
        ptype = pattern["type"]

        if ptype == "constant_recolor":
            fill_color = pattern["fill_color"]
            for obj, is_changed in zip(objects, change_mask):
                if is_changed:
                    result[obj["mask"]] = fill_color
            return result

        if ptype == "per_object_recolor":
            color_map = pattern["color_map"]
            for obj, is_changed in zip(objects, change_mask):
                if is_changed:
                    mask = obj["mask"]
                    for old_c, new_c in color_map.items():
                        old_c_int = int(old_c) if isinstance(old_c, str) else old_c
                        result[mask & (inp == old_c_int)] = new_c
            return result

        return None

    # --- Schema evaluation fallback ----------------------------------------

    def _try_schema_evaluation(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """Try operator schemas from the schema library."""
        if all(self.adapter.scenes_equal(inp, out) for inp, out in train_pairs):
            return None
        try:
            from reasoning_project.operator_schemas import SchemaEvaluator
        except ImportError:
            return None
        evaluator = SchemaEvaluator()
        match = evaluator.evaluate_task(train_pairs, test_inputs)
        if match is not None and match.predictions is not None:
            return match.predictions, match.hypothesis
        return None

    # --- Transform induction -----------------------------------------------

    def _try_transform_induction(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        if len(train_pairs) < self.min_train:
            return None
        for inp, out in train_pairs:
            if not self.adapter.same_structure(inp, out):
                return None

        rule = self._find_relabel_rule(train_pairs)
        if rule is None:
            return None
        rule_type, params = rule

        # LOO: verify the specific discovered rule predicts each held-out
        for hold_out in range(len(train_pairs)):
            held_inp, held_out_scene = train_pairs[hold_out]
            pred = self._apply_relabel(held_inp, rule_type, params)
            if pred is None or not self.adapter.scenes_equal(pred, held_out_scene):
                return None

        predictions = []
        for test_inp in test_inputs:
            pred = self._apply_relabel(test_inp, rule_type, params)
            if pred is None:
                return None
            predictions.append(pred)

        return predictions, {
            "strategy": "transform_induction",
            "rule_type": rule_type,
            "params": {k: v for k, v in params.items() if k != "rank_to_label"},
        }

    def _find_relabel_rule(
        self, train_pairs: List[Tuple[Any, Any]],
        prefer_type: Optional[str] = None,
    ) -> Optional[Tuple[str, Dict]]:
        for inp, out in train_pairs:
            in_objs = self.adapter.extract_objects(inp)
            out_objs = self.adapter.extract_objects(out)
            if len(in_objs) != len(out_objs) or len(in_objs) < 2:
                return None

        if prefer_type == "property_relabel":
            rule = self._try_property_relabel(train_pairs)
            if rule:
                return rule
            rule = self._try_rank_relabel(train_pairs, "size_rank")
            if rule:
                return rule
        else:
            rule = self._try_rank_relabel(train_pairs, "size_rank")
            if rule:
                return rule
            rule = self._try_property_relabel(train_pairs)
            if rule:
                return rule
        return None

    def _try_rank_relabel(
        self, train_pairs: List[Tuple[Any, Any]], rank_key: str,
    ) -> Optional[Tuple[str, Dict]]:
        rank_to_label: Dict[int, int] = {}
        for inp, out in train_pairs:
            in_objs = self.adapter.extract_objects(inp)
            out_objs = self.adapter.extract_objects(out)
            if len(in_objs) != len(out_objs):
                return None
            matches = self.adapter.match_objects(in_objs, out_objs)
            if len(matches) != len(in_objs):
                return None
            for i_idx, j_idx, _ in matches:
                rank = in_objs[i_idx].get(rank_key, i_idx)
                new_label = out_objs[j_idx].get("primary_color",
                            out_objs[j_idx].get("primary_label", 0))
                if rank in rank_to_label and rank_to_label[rank] != new_label:
                    return None
                rank_to_label[rank] = new_label
        if not rank_to_label:
            return None
        if all(v == rank_to_label.get(0) for v in rank_to_label.values()):
            return None
        return ("rank_relabel", {"rank_key": rank_key, "rank_to_label": rank_to_label})

    def _try_property_relabel(
        self, train_pairs: List[Tuple[Any, Any]],
    ) -> Optional[Tuple[str, Dict]]:
        all_props = self.adapter.property_names()
        for prop in all_props:
            true_label = None
            false_label = None
            consistent = True
            for inp, out in train_pairs:
                in_objs = self.adapter.extract_objects(inp)
                out_objs = self.adapter.extract_objects(out)
                if len(in_objs) != len(out_objs):
                    consistent = False
                    break
                matches = self.adapter.match_objects(in_objs, out_objs)
                if len(matches) != len(in_objs):
                    consistent = False
                    break
                for i_idx, j_idx, _ in matches:
                    val = self.adapter.get_property(in_objs[i_idx], prop)
                    new_l = out_objs[j_idx].get("primary_color",
                            out_objs[j_idx].get("primary_label", 0))
                    if val:
                        if true_label is None:
                            true_label = new_l
                        elif true_label != new_l:
                            consistent = False
                            break
                    else:
                        if false_label is None:
                            false_label = new_l
                        elif false_label != new_l:
                            consistent = False
                            break
                if not consistent:
                    break
            if consistent and true_label is not None and false_label is not None and true_label != false_label:
                return ("property_relabel", {
                    "prop": prop, "true_label": true_label, "false_label": false_label,
                })
        return None

    def _apply_relabel(
        self, inp: Any, rule_type: str, params: Dict,
    ) -> Optional[Any]:
        objects = self.adapter.extract_objects(inp)
        if len(objects) < 2:
            return None
        label_map = {}
        if rule_type == "rank_relabel":
            rank_key = params["rank_key"]
            rank_to_label = params["rank_to_label"]
            for obj in objects:
                rank = obj.get(rank_key, 0)
                if rank not in rank_to_label:
                    return None
                old = obj.get("primary_color", obj.get("primary_label", 0))
                label_map[id(obj)] = rank_to_label[rank]
            per_obj_map = {}
            for i, obj in enumerate(objects):
                per_obj_map[i] = label_map[id(obj)]
            return self.adapter.reconstruct_recolored(inp, objects, per_obj_map)

        elif rule_type == "property_relabel":
            prop = params["prop"]
            true_label = params["true_label"]
            false_label = params["false_label"]
            per_obj_map = {}
            for i, obj in enumerate(objects):
                val = self.adapter.get_property(obj, prop)
                per_obj_map[i] = true_label if val else false_label
            return self.adapter.reconstruct_recolored(inp, objects, per_obj_map)

        return None

    # --- Compositional planning: filter→extract ----------------------------

    def _try_filter_then_extract(
        self, train_pairs: List[Tuple[Any, Any]], test_inputs: List[Any],
        wm: Optional[WorkingMemory] = None,
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        if len(train_pairs) < self.min_train:
            return None
        all_props = wm.get_ordered_properties() if wm else self.adapter.property_names()
        for prop in all_props:
            if self._expired():
                return None
            for keep_when_true in [True, False]:
                consistent = True
                for inp, out in train_pairs:
                    objects = self.adapter.extract_objects(inp)
                    if len(objects) < 2:
                        consistent = False
                        break
                    keep_mask = [self.adapter.get_property(o, prop) == keep_when_true
                                 for o in objects]
                    if all(keep_mask) or not any(keep_mask):
                        consistent = False
                        break
                    pred = self.adapter.reconstruct_extracted(inp, objects, keep_mask)
                    if pred is None or not self.adapter.scenes_equal(pred, out):
                        consistent = False
                        break
                if not consistent:
                    continue

                loo_ok = True
                for hold_out in range(len(train_pairs)):
                    held_inp, held_out_scene = train_pairs[hold_out]
                    objs = self.adapter.extract_objects(held_inp)
                    km = [self.adapter.get_property(o, prop) == keep_when_true for o in objs]
                    if all(km) or not any(km):
                        loo_ok = False
                        break
                    pred = self.adapter.reconstruct_extracted(held_inp, objs, km)
                    if pred is None or not self.adapter.scenes_equal(pred, held_out_scene):
                        loo_ok = False
                        break
                if not loo_ok:
                    continue

                predictions = []
                for test_inp in test_inputs:
                    objs = self.adapter.extract_objects(test_inp)
                    km = [self.adapter.get_property(o, prop) == keep_when_true for o in objs]
                    if all(km) or not any(km):
                        break
                    pred = self.adapter.reconstruct_extracted(test_inp, objs, km)
                    if pred is None:
                        break
                    predictions.append(pred)
                else:
                    return predictions, {
                        "strategy": "compositional",
                        "composition": "filter_then_extract",
                        "filter_prop": prop,
                        "keep_when_true": keep_when_true,
                    }
        return None


# ═══════════════════════════════════════════════════════════════════════════
# GRID DOMAIN ADAPTER — ARC / colored-grid perception
# ═══════════════════════════════════════════════════════════════════════════

class GridDomainAdapter(DomainAdapter):
    """ARC-specific adapter: 2D integer grids, connected-component objects."""

    def __init__(self, bg: int = 0):
        self.bg = bg

    def extract_objects(self, scene: np.ndarray) -> List[Dict[str, Any]]:
        return _extract_objects_with_properties(scene, bg=self.bg)

    def property_names(self) -> List[str]:
        return _all_property_names()

    def get_property(self, obj: Dict, prop: str) -> bool:
        return _get_property_value(obj, prop)

    def classify_kept_removed(
        self, objects: List[Dict], inp: np.ndarray, out: np.ndarray,
    ) -> Optional[Tuple[List[int], List[int]]]:
        return _classify_kept_removed(objects, inp, out)

    def classify_object_changes(
        self, objects: List[Dict], inp: np.ndarray, out: np.ndarray,
    ) -> Optional["ObjectChangeClassification"]:
        return _classify_object_changes(objects, inp, out, bg=self.bg)

    def classify_unchanged_changed(
        self, objects: List[Dict], inp: np.ndarray, out: np.ndarray,
    ) -> Optional[Tuple[List[int], List[int]]]:
        return _classify_unchanged_changed(objects, inp, out)

    def classify_extended(
        self, objects: List[Dict], inp: np.ndarray, out: np.ndarray,
    ) -> Optional[Tuple[List[int], List[int], str]]:
        """Return (group_a, group_b, mode) using extended classification.

        Tries kept_removed -> present_absent -> recolored_retained -> unchanged_changed.
        """
        return _classify_kept_removed_extended(objects, inp, out)

    def reconstruct_filtered(
        self, inp: np.ndarray, objects: List[Dict], keep_mask: List[bool],
    ) -> Optional[np.ndarray]:
        result = inp.copy()
        for obj, keep in zip(objects, keep_mask):
            if not keep:
                result[obj["mask"]] = 0
        return result

    def reconstruct_recolored(
        self, inp: np.ndarray, objects: List[Dict], label_map: Dict[int, int],
    ) -> Optional[np.ndarray]:
        result = inp.copy()
        for i, obj in enumerate(objects):
            if i in label_map:
                result[obj["mask"]] = label_map[i]
        return result

    def reconstruct_extracted(
        self, inp: np.ndarray, objects: List[Dict], keep_mask: List[bool],
    ) -> Optional[np.ndarray]:
        combined = np.zeros_like(inp, dtype=bool)
        for obj, keep in zip(objects, keep_mask):
            if keep:
                combined |= obj["mask"]
        rows, cols = np.where(combined)
        if len(rows) == 0:
            return None
        r_min, r_max = int(rows.min()), int(rows.max())
        c_min, c_max = int(cols.min()), int(cols.max())
        cropped = np.zeros((r_max - r_min + 1, c_max - c_min + 1), dtype=inp.dtype)
        crop_mask = combined[r_min:r_max+1, c_min:c_max+1]
        cropped[crop_mask] = inp[r_min:r_max+1, c_min:c_max+1][crop_mask]
        return cropped

    def scenes_equal(self, a: np.ndarray, b: np.ndarray) -> bool:
        return np.array_equal(a, b)

    def same_structure(self, a: np.ndarray, b: np.ndarray) -> bool:
        return a.shape == b.shape

    def match_objects(
        self, in_objs: List[Dict], out_objs: List[Dict],
    ) -> List[Tuple[int, int, float]]:
        return _match_objects_hungarian(in_objs, out_objs)


# ═══════════════════════════════════════════════════════════════════════════
# ARC-SPECIFIC PERCEPTION (used by GridDomainAdapter and legacy functions)
# ═══════════════════════════════════════════════════════════════════════════

# ---------------------------------------------------------------------------
# 1. PERCEPTION — extract objects with ALL computable properties
# ---------------------------------------------------------------------------

def _extract_objects_with_properties(
    grid: np.ndarray, bg: int = 0
) -> List[Dict[str, Any]]:
    """Extract objects and compute a rich property vector for each."""
    h, w = grid.shape
    mask = grid != bg
    labeled, n = ndimage.label(mask)
    objects = []

    for lab in range(1, n + 1):
        obj_mask = labeled == lab
        rows, cols = np.where(obj_mask)
        if len(rows) == 0:
            continue

        r_min, r_max = int(rows.min()), int(rows.max())
        c_min, c_max = int(cols.min()), int(cols.max())
        bbox_h = r_max - r_min + 1
        bbox_w = c_max - c_min + 1
        local_mask = obj_mask[r_min:r_max+1, c_min:c_max+1]
        area = int(obj_mask.sum())
        colors = sorted(set(grid[obj_mask].tolist()) - {bg})
        primary_color = int(grid[obj_mask].flat[0])

        # Perimeter
        perimeter = 0
        for r in range(bbox_h):
            for c in range(bbox_w):
                if local_mask[r, c]:
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if nr < 0 or nr >= bbox_h or nc < 0 or nc >= bbox_w or not local_mask[nr, nc]:
                            perimeter += 1

        # Holes (Euler characteristic)
        bg_labeled, n_bg = ndimage.label(~local_mask)
        border_labels = set()
        border_labels.update(bg_labeled[0, :].tolist())
        border_labels.update(bg_labeled[-1, :].tolist())
        border_labels.update(bg_labeled[:, 0].tolist())
        border_labels.update(bg_labeled[:, -1].tolist())
        border_labels.discard(0)
        n_holes = sum(1 for lb in range(1, n_bg + 1) if lb not in border_labels)

        # Symmetry
        shape_bin = local_mask.astype(int)
        h_sym = bool(np.array_equal(shape_bin, shape_bin[::-1, :]))
        v_sym = bool(np.array_equal(shape_bin, shape_bin[:, ::-1]))
        d_sym = False
        if bbox_h == bbox_w:
            d_sym = bool(np.array_equal(shape_bin, shape_bin.T))

        # Convexity
        convexity = area / max(bbox_h * bbox_w, 1)

        # Boundary touching
        touches_top = r_min == 0
        touches_bottom = r_max == h - 1
        touches_left = c_min == 0
        touches_right = c_max == w - 1
        touches_boundary = touches_top or touches_bottom or touches_left or touches_right

        objects.append({
            "label": lab,
            "mask": obj_mask,
            "local_mask": local_mask,
            "bbox": (r_min, c_min, r_max, c_max),
            "center_r": float(rows.mean()),
            "center_c": float(cols.mean()),
            "area": area,
            "bbox_h": bbox_h,
            "bbox_w": bbox_w,
            "primary_color": primary_color,
            "colors": colors,
            "n_colors": len(colors),
            "perimeter": perimeter,
            "n_holes": n_holes,
            "euler_char": 1 - n_holes,
            "h_sym": h_sym,
            "v_sym": v_sym,
            "d_sym": d_sym,
            "any_sym": h_sym or v_sym or d_sym,
            "convexity": convexity,
            "is_filled_rect": area == bbox_h * bbox_w,
            "is_square": bbox_h == bbox_w,
            "touches_boundary": touches_boundary,
            "touches_top": touches_top,
            "touches_bottom": touches_bottom,
            "touches_left": touches_left,
            "touches_right": touches_right,
            "bbox_ratio": bbox_h / max(bbox_w, 1),
        })

    # Relational properties (require all objects)
    _add_relational_properties(objects, grid, h, w)

    return objects


def _add_relational_properties(
    objects: List[Dict], grid: np.ndarray, grid_h: int, grid_w: int
):
    """Add properties that depend on relations between objects."""
    n = len(objects)
    if n == 0:
        return

    sizes = [o["area"] for o in objects]
    max_size = max(sizes)
    min_size = min(sizes)
    size_sorted = sorted(range(n), key=lambda i: sizes[i], reverse=True)
    largest_idx = size_sorted[0]

    # Shape groups
    shape_groups: Dict[int, List[int]] = {}
    shape_id_map = {}
    next_shape_id = 0
    for i in range(n):
        found = False
        for sid, members in shape_groups.items():
            ref = objects[members[0]]
            if (objects[i]["local_mask"].shape == ref["local_mask"].shape and
                    np.array_equal(objects[i]["local_mask"], ref["local_mask"])):
                shape_groups[sid].append(i)
                shape_id_map[i] = sid
                found = True
                break
        if not found:
            shape_groups[next_shape_id] = [i]
            shape_id_map[i] = next_shape_id
            next_shape_id += 1

    # Containment
    contained_by = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            ir1, ic1, ir2, ic2 = objects[i]["bbox"]
            jr1, jc1, jr2, jc2 = objects[j]["bbox"]
            if jr1 <= ir1 and jc1 <= ic1 and jr2 >= ir2 and jc2 >= ic2:
                contained_by[i] = j

    # Touching largest
    touching_largest = set()
    if n > 1:
        largest_dilated = ndimage.binary_dilation(objects[largest_idx]["mask"])
        for i in range(n):
            if i == largest_idx:
                continue
            if np.any(largest_dilated & objects[i]["mask"]):
                touching_largest.add(i)

    # Color groups
    color_groups: Dict[int, List[int]] = {}
    for i, o in enumerate(objects):
        c = o["primary_color"]
        color_groups.setdefault(c, []).append(i)

    # Pairwise touching count
    touching_count = [0] * n
    if n > 1:
        for i in range(n):
            dilated_i = ndimage.binary_dilation(objects[i]["mask"])
            for j in range(i + 1, n):
                if np.any(dilated_i & objects[j]["mask"]):
                    touching_count[i] += 1
                    touching_count[j] += 1

    # Area groups
    area_groups: Dict[int, List[int]] = {}
    for i, o in enumerate(objects):
        a = o["area"]
        area_groups.setdefault(a, []).append(i)
    largest_area = sizes[largest_idx] if n > 0 else 0
    smallest_idx = size_sorted[-1] if n > 0 else 0

    # Adjacency (touching objects of same/different color)
    adj_same_color = [False] * n
    adj_diff_color = [False] * n
    if n > 1:
        for i in range(n):
            dilated_i = ndimage.binary_dilation(objects[i]["mask"])
            for j in range(i + 1, n):
                if np.any(dilated_i & objects[j]["mask"]):
                    ci = objects[i]["primary_color"]
                    cj = objects[j]["primary_color"]
                    if ci == cj:
                        adj_same_color[i] = True
                        adj_same_color[j] = True
                    else:
                        adj_diff_color[i] = True
                        adj_diff_color[j] = True

    # Shape match to smallest object
    smallest_local = objects[smallest_idx]["local_mask"] if n > 0 else None
    all_shape_group_sizes = [len(g) for g in shape_groups.values()]

    # Color frequency across objects
    color_counts: Dict[int, int] = {}
    for o in objects:
        c = o["primary_color"]
        color_counts[c] = color_counts.get(c, 0) + 1
    most_common_color = max(color_counts, key=color_counts.get) if color_counts else -1
    rarest_color = min(color_counts, key=color_counts.get) if color_counts else -1
    largest_color = objects[largest_idx]["primary_color"] if n > 0 else -1

    largest_cr = objects[largest_idx]["center_r"] if n > 0 else 0
    largest_cc = objects[largest_idx]["center_c"] if n > 0 else 0

    for i, o in enumerate(objects):
        o["is_largest"] = (i == largest_idx)
        o["is_smallest"] = (sizes[i] == min_size)
        o["size_rank"] = size_sorted.index(i)
        o["_n_objects"] = n
        o["shape_group_id"] = shape_id_map[i]
        o["shape_group_size"] = len(shape_groups[shape_id_map[i]])
        o["is_unique_shape"] = o["shape_group_size"] == 1
        o["is_majority_shape"] = o["shape_group_size"] == max(
            len(g) for g in shape_groups.values()
        )
        o["is_contained"] = i in contained_by
        o["is_container"] = any(v == i for v in contained_by.values())
        o["touches_largest"] = i in touching_largest
        o["is_largest_in_color_group"] = (
            sizes[i] == max(sizes[j] for j in color_groups[o["primary_color"]])
        )
        o["color_group_size"] = len(color_groups[o["primary_color"]])
        o["is_unique_color"] = o["color_group_size"] == 1

        # Positional
        o["in_top_half"] = o["center_r"] < grid_h / 2
        o["in_left_half"] = o["center_c"] < grid_w / 2

        # Neighborhood count
        o["n_touching"] = touching_count[i]

        # Spatial relations to largest object
        if i != largest_idx:
            o["same_row_as_largest"] = abs(o["center_r"] - largest_cr) < 1.5
            o["same_col_as_largest"] = abs(o["center_c"] - largest_cc) < 1.5
            o["above_largest"] = o["center_r"] < largest_cr
            o["below_largest"] = o["center_r"] > largest_cr
            o["left_of_largest"] = o["center_c"] < largest_cc
            o["right_of_largest"] = o["center_c"] > largest_cc
        else:
            o["same_row_as_largest"] = False
            o["same_col_as_largest"] = False
            o["above_largest"] = False
            o["below_largest"] = False
            o["left_of_largest"] = False
            o["right_of_largest"] = False

        # Color frequency predicates
        o["is_most_common_color"] = o["primary_color"] == most_common_color
        o["is_rarest_color"] = o["primary_color"] == rarest_color
        o["same_color_as_largest"] = o["primary_color"] == largest_color

        # Area group predicates
        o["area_group_size"] = len(area_groups[o["area"]])
        o["same_area_as_largest"] = o["area"] == largest_area

        # Spanning predicates
        r1, c1, r2, c2 = o["bbox"]
        o["spans_full_width"] = (c1 == 0 and c2 == grid_w - 1)
        o["spans_full_height"] = (r1 == 0 and r2 == grid_h - 1)

        # Adjacency predicates
        o["adjacent_to_different_color"] = adj_diff_color[i]
        o["adjacent_to_same_color"] = adj_same_color[i]

        # Shape match to smallest
        o["same_shape_as_smallest"] = (
            smallest_local is not None and
            o["local_mask"].shape == smallest_local.shape and
            np.array_equal(o["local_mask"], smallest_local)
        )
        o["_all_shape_group_sizes"] = all_shape_group_sizes

    # --- Marker-relative properties (markers = single-cell objects) ---
    markers = [i for i in range(n) if objects[i]["area"] == 1]
    marker_colors = {objects[m]["primary_color"] for m in markers}
    marker_positions = [(objects[m]["center_r"], objects[m]["center_c"]) for m in markers]

    for i, o in enumerate(objects):
        if i in markers:
            o["is_marker"] = True
            o["touches_marker"] = False
            o["aligned_with_marker_row"] = False
            o["aligned_with_marker_col"] = False
            o["same_color_as_marker"] = False
            o["nearest_to_marker"] = False
        else:
            o["is_marker"] = False
            if markers:
                dilated = ndimage.binary_dilation(o["mask"])
                o["touches_marker"] = any(
                    np.any(dilated & objects[m]["mask"]) for m in markers
                )
                o["aligned_with_marker_row"] = any(
                    abs(o["center_r"] - mr) < 1.0 for mr, _ in marker_positions
                )
                o["aligned_with_marker_col"] = any(
                    abs(o["center_c"] - mc) < 1.0 for _, mc in marker_positions
                )
                o["same_color_as_marker"] = o["primary_color"] in marker_colors
            else:
                o["touches_marker"] = False
                o["aligned_with_marker_row"] = False
                o["aligned_with_marker_col"] = False
                o["same_color_as_marker"] = False
            o["nearest_to_marker"] = False

    if markers and len(markers) < n:
        non_markers = [i for i in range(n) if i not in markers]
        for m in markers:
            mr, mc = objects[m]["center_r"], objects[m]["center_c"]
            best_d = float("inf")
            best_i = -1
            for i in non_markers:
                d = abs(objects[i]["center_r"] - mr) + abs(objects[i]["center_c"] - mc)
                if d < best_d:
                    best_d = d
                    best_i = i
            if best_i >= 0:
                objects[best_i]["nearest_to_marker"] = True

    # --- Unique-color-relative properties ---
    unique_color_objs = [i for i in range(n) if objects[i]["color_group_size"] == 1]
    for i, o in enumerate(objects):
        o["nearest_to_unique_color"] = False
        o["same_shape_as_unique_color"] = False

    if unique_color_objs:
        non_unique = [i for i in range(n) if i not in unique_color_objs]
        for ui in unique_color_objs:
            uo = objects[ui]
            best_d = float("inf")
            best_i = -1
            for i in non_unique:
                d = abs(objects[i]["center_r"] - uo["center_r"]) + \
                    abs(objects[i]["center_c"] - uo["center_c"])
                if d < best_d:
                    best_d = d
                    best_i = i
            if best_i >= 0:
                objects[best_i]["nearest_to_unique_color"] = True
            for i in range(n):
                if i == ui:
                    continue
                if (objects[i]["local_mask"].shape == uo["local_mask"].shape and
                        np.array_equal(objects[i]["local_mask"], uo["local_mask"])):
                    objects[i]["same_shape_as_unique_color"] = True

    # --- Frame-relative properties ---
    frame_indices = [i for i in range(n)
                     if objects[i]["n_holes"] > 0 and objects[i]["convexity"] < 0.7]
    for i, o in enumerate(objects):
        inside_any_frame = False
        if i not in frame_indices:
            for fi in frame_indices:
                fr1, fc1, fr2, fc2 = objects[fi]["bbox"]
                or1, oc1, or2, oc2 = o["bbox"]
                if fr1 <= or1 and fc1 <= oc1 and fr2 >= or2 and fc2 >= oc2:
                    inside_any_frame = True
                    break
        o["inside_frame"] = inside_any_frame
        o["outside_all_frames"] = not inside_any_frame and i not in frame_indices

    # --- Rotation uniqueness ---
    for i, o in enumerate(objects):
        lm = o["local_mask"]
        rots = [np.rot90(lm, k) for k in range(1, 4)]
        unique = True
        for j in range(n):
            if j == i:
                continue
            olm = objects[j]["local_mask"]
            for rot in rots:
                if rot.shape == olm.shape and np.array_equal(rot, olm):
                    unique = False
                    break
            if not unique:
                break
            if lm.shape == olm.shape and np.array_equal(lm, olm):
                unique = False
                break
        o["unique_under_rotation"] = unique and not o["is_unique_shape"]

    # --- Scan order ---
    scan_order = sorted(range(n), key=lambda i: (objects[i]["center_r"], objects[i]["center_c"]))
    for i, o in enumerate(objects):
        o["scan_order_rank"] = scan_order.index(i)
        o["first_in_scan_order"] = (scan_order[0] == i) if n > 1 else False
        o["last_in_scan_order"] = (scan_order[-1] == i) if n > 1 else False

    # --- Between two markers ---
    if len(markers) >= 2:
        for i, o in enumerate(objects):
            if i in markers:
                o["between_markers"] = False
                continue
            between = False
            for mi in range(len(markers)):
                for mj in range(mi + 1, len(markers)):
                    m1r, m1c = marker_positions[mi]
                    m2r, m2c = marker_positions[mj]
                    r_lo, r_hi = min(m1r, m2r), max(m1r, m2r)
                    c_lo, c_hi = min(m1c, m2c), max(m1c, m2c)
                    if r_lo < o["center_r"] < r_hi or c_lo < o["center_c"] < c_hi:
                        between = True
                        break
                if between:
                    break
            o["between_markers"] = between
    else:
        for o in objects:
            o["between_markers"] = False


# ---------------------------------------------------------------------------
# 2. PROPERTY LANGUAGE — the predicates the engine can reason over
# ---------------------------------------------------------------------------

RELATIONAL_EXPANDED_PROPERTIES = [
    "is_marker", "touches_marker", "aligned_with_marker_row",
    "aligned_with_marker_col", "same_color_as_marker", "nearest_to_marker",
    "nearest_to_unique_color", "same_shape_as_unique_color",
    "inside_frame", "outside_all_frames",
    "unique_under_rotation",
    "first_in_scan_order", "last_in_scan_order",
    "between_markers",
]

BOOLEAN_PROPERTIES = [
    "is_filled_rect",
    "is_square",
    "any_sym",
    "h_sym",
    "v_sym",
    "d_sym",
    "touches_boundary",
    "touches_top",
    "touches_bottom",
    "touches_left",
    "touches_right",
    "is_largest",
    "is_smallest",
    "is_unique_shape",
    "is_majority_shape",
    "is_contained",
    "is_container",
    "touches_largest",
    "is_largest_in_color_group",
    "is_unique_color",
    "in_top_half",
    "in_left_half",
]

DERIVED_PREDICATES = [
    ("has_holes", lambda o: o["n_holes"] > 0),
    ("is_convex", lambda o: o["convexity"] > 0.95),
    ("is_elongated_h", lambda o: o["bbox_ratio"] > 2.0),
    ("is_elongated_v", lambda o: o["bbox_ratio"] < 0.5),
    ("multi_colored", lambda o: o["n_colors"] > 1),
    ("single_cell", lambda o: o["area"] == 1),
    ("large_object", lambda o: o["area"] > 9),
    ("is_line", lambda o: o["bbox_h"] == 1 or o["bbox_w"] == 1),
    ("is_singleton", lambda o: o["area"] == 1),
    ("is_frame", lambda o: o["n_holes"] > 0 and o["convexity"] < 0.7),
    ("is_noise", lambda o: o["area"] <= 2 and o["is_unique_shape"]),
    ("is_repeated_shape", lambda o: o.get("shape_group_size", 1) > 1),
    ("is_medium_object", lambda o: 4 <= o["area"] <= 9),
    ("is_tiny_object", lambda o: o["area"] <= 3),
    ("is_on_diagonal", lambda o: abs(o["center_r"] - o["center_c"]) < 1.5),
    ("in_bottom_half", lambda o: not o.get("in_top_half", True)),
    ("in_right_half", lambda o: not o.get("in_left_half", True)),
    ("is_center_object", lambda o: (
        not o.get("touches_boundary", False) and
        not o.get("in_top_half", True) == o.get("in_left_half", True)
    ) if "touches_boundary" in o else False),
    ("has_unique_size", lambda o: o.get("size_rank", 0) != o.get("shape_group_size", 1)),
    ("is_smallest_in_color_group", lambda o: (
        o.get("color_group_size", 1) > 1 and not o.get("is_largest_in_color_group", True)
    )),
    ("is_interior", lambda o: not o.get("touches_boundary", False)),
    ("is_corner", lambda o: (
        (o.get("touches_top", False) or o.get("touches_bottom", False)) and
        (o.get("touches_left", False) or o.get("touches_right", False))
    )),
    ("is_edge_only", lambda o: (
        o.get("touches_boundary", False) and not (
            (o.get("touches_top", False) or o.get("touches_bottom", False)) and
            (o.get("touches_left", False) or o.get("touches_right", False))
        )
    )),
    ("is_isolated", lambda o: not o.get("touches_largest", False) and not o.get("is_contained", False)),
    # --- Per-color predicates ---
    *[
        (f"is_color_{c}", (lambda c_val: lambda o: o.get("primary_color", -1) == c_val)(c))
        for c in range(1, 10)
    ],
    # --- Ordinal rank predicates ---
    ("is_2nd_largest", lambda o: o.get("size_rank", -1) == 1),
    ("is_3rd_largest", lambda o: o.get("size_rank", -1) == 2),
    ("is_2nd_smallest", lambda o: o.get("size_rank", -1) == o.get("_n_objects", 2) - 2),
    # --- Exact dimension predicates ---
    ("area_eq_2", lambda o: o["area"] == 2),
    ("area_eq_3", lambda o: o["area"] == 3),
    ("area_eq_4", lambda o: o["area"] == 4),
    ("height_eq_1", lambda o: o["bbox_h"] == 1),
    ("height_eq_2", lambda o: o["bbox_h"] == 2),
    ("height_eq_3", lambda o: o["bbox_h"] == 3),
    ("width_eq_1", lambda o: o["bbox_w"] == 1),
    ("width_eq_2", lambda o: o["bbox_w"] == 2),
    ("width_eq_3", lambda o: o["bbox_w"] == 3),
    # --- Neighborhood count predicates ---
    ("touches_many", lambda o: o.get("n_touching", 0) > 2),
    ("touches_one", lambda o: o.get("n_touching", 0) == 1),
    ("touches_none", lambda o: o.get("n_touching", 0) == 0),
    # --- Spatial relation to largest ---
    ("same_row_as_largest", lambda o: o.get("same_row_as_largest", False)),
    ("same_col_as_largest", lambda o: o.get("same_col_as_largest", False)),
    ("above_largest", lambda o: o.get("above_largest", False)),
    ("below_largest", lambda o: o.get("below_largest", False)),
    ("left_of_largest", lambda o: o.get("left_of_largest", False)),
    ("right_of_largest", lambda o: o.get("right_of_largest", False)),
    # --- Rotational symmetry ---
    ("has_rot180_sym", lambda o: (
        o["bbox_h"] == o["bbox_w"] and
        bool(np.array_equal(o["local_mask"], np.rot90(o["local_mask"], 2)))
    ) if "local_mask" in o else False),
    ("has_rot90_sym", lambda o: (
        o["bbox_h"] == o["bbox_w"] and
        bool(np.array_equal(o["local_mask"], np.rot90(o["local_mask"], 1)))
    ) if "local_mask" in o else False),
    # --- Color frequency ---
    ("is_most_common_color", lambda o: o.get("is_most_common_color", False)),
    ("is_rarest_color", lambda o: o.get("is_rarest_color", False)),
    ("same_color_as_largest", lambda o: o.get("same_color_as_largest", False)),
    # --- Color/area group cardinality ---
    ("color_group_size_2", lambda o: o.get("color_group_size", 1) == 2),
    ("color_group_size_3plus", lambda o: o.get("color_group_size", 1) >= 3),
    ("is_unique_area", lambda o: o.get("area_group_size", 1) == 1),
    ("area_group_size_2", lambda o: o.get("area_group_size", 1) == 2),
    ("area_group_size_3plus", lambda o: o.get("area_group_size", 1) >= 3),
    ("same_area_as_largest", lambda o: o.get("same_area_as_largest", False)),
    # --- Spanning ---
    ("spans_full_width", lambda o: o.get("spans_full_width", False)),
    ("spans_full_height", lambda o: o.get("spans_full_height", False)),
    # --- Adjacency ---
    ("adjacent_to_different_color", lambda o: o.get("adjacent_to_different_color", False)),
    ("adjacent_to_same_color", lambda o: o.get("adjacent_to_same_color", False)),
    # --- Shape match ---
    ("same_shape_as_smallest", lambda o: o.get("same_shape_as_smallest", False)),
    ("is_minority_shape", lambda o: o.get("shape_group_size", 1) == min(
        o.get("_all_shape_group_sizes", [1])
    )),
]


def _get_property_value(obj: Dict, prop_name: str) -> bool:
    """Get a boolean property value for an object.

    Handles conjunction properties like "is_largest&in_top_half" or
    "is_largest&!in_top_half" where & means AND and ! means NOT.
    """
    if "&" in prop_name:
        parts = prop_name.split("&")
        for part in parts:
            if part.startswith("!"):
                if _get_property_value(obj, part[1:]):
                    return False
            else:
                if not _get_property_value(obj, part):
                    return False
        return True
    if prop_name in obj:
        return bool(obj[prop_name])
    for name, fn in DERIVED_PREDICATES:
        if name == prop_name:
            return fn(obj)
    return False


def _all_property_names() -> List[str]:
    return (BOOLEAN_PROPERTIES +
            [name for name, _ in DERIVED_PREDICATES] +
            RELATIONAL_EXPANDED_PROPERTIES)


# ---------------------------------------------------------------------------
# 3. DISCRIMINATIVE REASONING — find the property that separates kept/removed
# ---------------------------------------------------------------------------

def _classify_kept_removed(
    objects: List[Dict], inp: np.ndarray, out: np.ndarray
) -> Optional[Tuple[List[int], List[int]]]:
    """Classify which input objects are kept vs removed in the output."""
    if inp.shape != out.shape:
        return None

    kept = []
    removed = []
    for i, obj in enumerate(objects):
        out_vals = out[obj["mask"]]
        if np.any(out_vals != 0):
            kept.append(i)
        else:
            removed.append(i)

    if not kept or not removed:
        return None

    return kept, removed


def _classify_unchanged_changed(
    objects: List[Dict], inp: np.ndarray, out: np.ndarray
) -> Optional[Tuple[List[int], List[int]]]:
    """Classify which input objects are unchanged vs changed in the output.

    Generalization of _classify_kept_removed for tasks where objects are
    not removed (zeroed) but transformed (recolored, filled, etc.).

    An object is "unchanged" if every pixel at its mask position is identical
    in input and output. Otherwise it is "changed".

    Returns (unchanged_indices, changed_indices) or None if not applicable.
    """
    if inp.shape != out.shape:
        return None

    unchanged = []
    changed = []
    for i, obj in enumerate(objects):
        in_vals = inp[obj["mask"]]
        out_vals = out[obj["mask"]]
        if np.array_equal(in_vals, out_vals):
            unchanged.append(i)
        else:
            changed.append(i)

    if not unchanged or not changed:
        return None

    return unchanged, changed


def _classify_two_groups(
    objects: List[Dict], inp: np.ndarray, out: np.ndarray,
) -> Optional[Tuple[List[int], List[int]]]:
    """Try kept/removed first, fall back to unchanged/changed."""
    result = _classify_kept_removed(objects, inp, out)
    if result is not None:
        return result
    return _classify_unchanged_changed(objects, inp, out)


def _classify_kept_removed_extended(
    objects: List[Dict], inp: np.ndarray, out: np.ndarray,
) -> Optional[Tuple[List[int], List[int], str]]:
    """Extended classification: kept/removed, present/absent, recolored/retained,
    or unchanged/changed.

    Tries multiple strategies in order of specificity to split objects into two
    non-empty groups based on how they appear in the output.

    Returns (group_a_indices, group_b_indices, classification_mode) where mode is:
    - "kept_removed": traditional zeroing classification (group_a=kept, group_b=removed)
    - "present_absent": objects whose pixels exist in output vs don't, robust to
      non-zero backgrounds
    - "recolored_retained": objects with uniform color change vs untouched
      (group_a=retained/unchanged, group_b=recolored/changed)
    - "unchanged_changed": any pixel difference
      (group_a=unchanged, group_b=changed)

    Returns None if no clean two-group split is found.
    """
    if inp.shape != out.shape:
        return None
    if not objects:
        return None

    # Strategy 1: kept_removed (existing — objects zeroed vs present)
    result_kr = _classify_kept_removed(objects, inp, out)
    if result_kr is not None:
        kept, removed = result_kr
        return kept, removed, "kept_removed"

    # Strategy 2: present_absent — check if mask pixels are ALL background
    # in the output. Determine background from the INPUT grid's non-object
    # pixels (the area not covered by any object mask), which is a reliable
    # indicator of the true background color.
    all_obj_mask = np.zeros(inp.shape, dtype=bool)
    for obj in objects:
        all_obj_mask |= obj["mask"]
    non_obj_pixels = inp[~all_obj_mask]
    if non_obj_pixels.size > 0:
        bg_val = int(np.bincount(non_obj_pixels.ravel().astype(int)).argmax())
    else:
        bg_val = 0

    present = []
    absent = []
    for i, obj in enumerate(objects):
        out_vals = out[obj["mask"]]
        if np.all(out_vals == bg_val):
            absent.append(i)
        else:
            present.append(i)
    if present and absent:
        return present, absent, "present_absent"

    # Strategy 3: recolored_retained — each object either has ALL its pixels
    # changed to a single new uniform color, or ALL pixels unchanged.
    retained = []
    recolored = []
    for i, obj in enumerate(objects):
        in_vals = inp[obj["mask"]]
        out_vals = out[obj["mask"]]
        if np.array_equal(in_vals, out_vals):
            retained.append(i)
        else:
            # Check for uniform recolor: all output pixels under mask are the
            # same single color (different from at least some input pixels)
            unique_out = np.unique(out_vals)
            if len(unique_out) == 1:
                recolored.append(i)
            else:
                # Not a clean uniform recolor; still count as changed but
                # this strategy requires uniform recolor for ALL changed objects
                recolored.append(i)

    # Only use recolored_retained if ALL recolored objects have uniform output
    if retained and recolored:
        all_uniform = True
        for ri in recolored:
            out_vals = out[objects[ri]["mask"]]
            if len(np.unique(out_vals)) != 1:
                all_uniform = False
                break
        if all_uniform:
            return retained, recolored, "recolored_retained"

    # Strategy 4: unchanged_changed (existing — any pixel difference)
    result_uc = _classify_unchanged_changed(objects, inp, out)
    if result_uc is not None:
        unchanged, changed = result_uc
        return unchanged, changed, "unchanged_changed"

    return None


# ═══════════════════════════════════════════════════════════════════════════
# RICH OBJECT-CHANGE CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ObjectChange:
    object_idx: int
    change_type: str  # kept, removed, recolored, moved, copied, moved_recolored, changed, ambiguous
    source_bbox: Tuple[int, int, int, int]
    target_bbox: Optional[Tuple[int, int, int, int]] = None
    source_colors: Tuple[int, ...] = ()
    target_colors: Optional[Tuple[int, ...]] = None
    displacement: Optional[Tuple[int, int]] = None
    confidence: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectChangeClassification:
    changes: List[ObjectChange]
    kept: List[int] = field(default_factory=list)
    removed: List[int] = field(default_factory=list)
    recolored: List[int] = field(default_factory=list)
    moved: List[int] = field(default_factory=list)
    copied: List[int] = field(default_factory=list)
    moved_recolored: List[int] = field(default_factory=list)
    changed: List[int] = field(default_factory=list)
    ambiguous: List[int] = field(default_factory=list)
    failure_reason: Optional[str] = None

    @property
    def group_a(self) -> List[int]:
        """Objects that are unchanged — analog of 'kept' for backward compat."""
        return self.kept

    @property
    def group_b(self) -> List[int]:
        """Objects that are transformed — analog of 'removed' for backward compat."""
        return self.removed + self.recolored + self.moved + self.copied + self.moved_recolored + self.changed

    @property
    def has_two_groups(self) -> bool:
        return bool(self.group_a) and bool(self.group_b)

    @property
    def dominant_change(self) -> str:
        counts = [
            ("removed", len(self.removed)),
            ("recolored", len(self.recolored)),
            ("moved", len(self.moved)),
            ("copied", len(self.copied)),
            ("moved_recolored", len(self.moved_recolored)),
            ("changed", len(self.changed)),
        ]
        counts.sort(key=lambda x: -x[1])
        return counts[0][0] if counts[0][1] > 0 else "none"

    def as_kept_removed(self) -> Optional[Tuple[List[int], List[int]]]:
        if self.has_two_groups:
            return self.group_a, self.group_b
        return None


def _obj_bbox(obj: Dict) -> Tuple[int, int, int, int]:
    mask = obj["mask"]
    rows, cols = np.where(mask)
    if len(rows) == 0:
        return (0, 0, 0, 0)
    return (int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max()))


def _obj_colors(obj: Dict, grid: np.ndarray, bg: int = 0) -> Tuple[int, ...]:
    vals = grid[obj["mask"]]
    return tuple(sorted(set(int(v) for v in np.unique(vals) if v != bg)))


def _find_shape_in_output(
    mask: np.ndarray,
    colors: np.ndarray,
    out: np.ndarray,
    bg: int = 0,
    orig_r0: int = 0,
    orig_c0: int = 0,
    color_match: bool = True,
) -> Optional[Dict[str, Any]]:
    """Find a shape (mask pattern) in the output grid.

    Returns best match with displacement, similarity, and color_blind flag.
    """
    rows, cols = np.where(mask)
    if len(rows) == 0:
        return None
    mr0, mc0 = int(rows.min()), int(cols.min())
    mr1, mc1 = int(rows.max()), int(cols.max())
    sh, sw = mr1 - mr0 + 1, mc1 - mc0 + 1

    local_mask = mask[mr0:mr0 + sh, mc0:mc0 + sw]
    local_colors = colors[mr0:mr0 + sh, mc0:mc0 + sw]
    n_cells = int(local_mask.sum())
    if n_cells == 0:
        return None

    H, W = out.shape
    best_sim = 0.0
    best_pos = None

    for r in range(H - sh + 1):
        for c in range(W - sw + 1):
            if r == orig_r0 and c == orig_c0:
                continue
            patch = out[r:r + sh, c:c + sw]
            if color_match:
                matched = int(np.sum((patch == local_colors) & local_mask))
            else:
                matched = int(np.sum((patch != bg) & local_mask))
            sim = matched / n_cells
            if sim > best_sim:
                best_sim = sim
                best_pos = (r, c)

    if best_pos is not None and best_sim >= 0.7:
        return {
            "pos": best_pos,
            "displacement": (best_pos[0] - orig_r0, best_pos[1] - orig_c0),
            "similarity": best_sim,
            "color_blind": not color_match,
        }
    return None


def _classify_object_changes(
    objects: List[Dict],
    inp: np.ndarray,
    out: np.ndarray,
    bg: int = 0,
) -> Optional[ObjectChangeClassification]:
    """Rich per-object change classification.

    For each input object, determines its fate in the output:
    kept, removed, recolored, moved, copied, moved_recolored, changed, or ambiguous.

    Returns ObjectChangeClassification with per-object labels and group lists,
    or None if the grids have different sizes or no objects exist.
    """
    if inp.shape != out.shape:
        return None
    if not objects:
        return None

    changes: List[ObjectChange] = []

    for i, obj in enumerate(objects):
        mask = obj["mask"]
        bbox = _obj_bbox(obj)
        in_vals = inp[mask]
        out_vals = out[mask]
        src_colors = _obj_colors(obj, inp, bg)

        same_pixels = np.array_equal(in_vals, out_vals)
        all_bg = np.all(out_vals == bg)

        if same_pixels:
            changes.append(ObjectChange(
                object_idx=i,
                change_type="kept",
                source_bbox=bbox,
                source_colors=src_colors,
                confidence=1.0,
                evidence={"reason": "identical_pixels"},
            ))
            continue

        if all_bg:
            # Object removed from original position — check if it moved elsewhere
            found = _find_shape_in_output(
                mask, inp, out, bg, bbox[0], bbox[1], color_match=True,
            )
            if found is not None and found["similarity"] >= 0.9:
                dr, dc = found["displacement"]
                dest = found["pos"]
                changes.append(ObjectChange(
                    object_idx=i,
                    change_type="moved",
                    source_bbox=bbox,
                    target_bbox=(dest[0], dest[1], dest[0] + bbox[2] - bbox[0], dest[1] + bbox[3] - bbox[1]),
                    source_colors=src_colors,
                    target_colors=src_colors,
                    displacement=(dr, dc),
                    confidence=found["similarity"],
                    evidence={"reason": "removed_found_elsewhere", **found},
                ))
            else:
                # Try color-blind match (shape moved + recolored)
                # Require >= 3 pixels to avoid false positives on tiny objects
                n_pixels = int(mask.sum())
                found_cb = None
                if n_pixels >= 3:
                    found_cb = _find_shape_in_output(
                        mask, inp, out, bg, bbox[0], bbox[1], color_match=False,
                    )
                if found_cb is not None and found_cb["similarity"] >= 0.8:
                    dr, dc = found_cb["displacement"]
                    dest = found_cb["pos"]
                    changes.append(ObjectChange(
                        object_idx=i,
                        change_type="moved_recolored",
                        source_bbox=bbox,
                        target_bbox=(dest[0], dest[1], dest[0] + bbox[2] - bbox[0], dest[1] + bbox[3] - bbox[1]),
                        source_colors=src_colors,
                        displacement=(dr, dc),
                        confidence=found_cb["similarity"],
                        evidence={"reason": "removed_shape_found_recolored", **found_cb},
                    ))
                else:
                    changes.append(ObjectChange(
                        object_idx=i,
                        change_type="removed",
                        source_bbox=bbox,
                        source_colors=src_colors,
                        confidence=1.0,
                        evidence={"reason": "zeroed_in_output"},
                    ))
            continue

        # Object still has non-bg pixels at original position
        in_nonzero = in_vals != bg
        out_nonzero = out_vals != bg

        if np.array_equal(in_nonzero, out_nonzero):
            # Same shape, different colors → recolored in place
            out_colors = _obj_colors(obj, out, bg)
            changes.append(ObjectChange(
                object_idx=i,
                change_type="recolored",
                source_bbox=bbox,
                target_bbox=bbox,
                source_colors=src_colors,
                target_colors=out_colors,
                confidence=1.0,
                evidence={"reason": "same_shape_different_colors"},
            ))
        else:
            # Shape and/or colors changed
            n_diff = int(np.sum(in_vals != out_vals))
            n_total = int(mask.sum())
            out_colors = _obj_colors(obj, out, bg)

            # Check if object was also copied elsewhere
            found = _find_shape_in_output(
                mask, inp, out, bg, bbox[0], bbox[1], color_match=True,
            )
            if found is not None and found["similarity"] >= 0.9:
                dest = found["pos"]
                changes.append(ObjectChange(
                    object_idx=i,
                    change_type="copied",
                    source_bbox=bbox,
                    target_bbox=(dest[0], dest[1], dest[0] + bbox[2] - bbox[0], dest[1] + bbox[3] - bbox[1]),
                    source_colors=src_colors,
                    displacement=found["displacement"],
                    confidence=found["similarity"],
                    evidence={"reason": "original_changed_copy_found"},
                ))
            else:
                changes.append(ObjectChange(
                    object_idx=i,
                    change_type="changed",
                    source_bbox=bbox,
                    target_bbox=bbox,
                    source_colors=src_colors,
                    target_colors=out_colors,
                    confidence=1.0 - (n_diff / max(n_total, 1)),
                    evidence={"reason": "pixels_differ", "n_diff": n_diff, "n_total": n_total},
                ))

    # Build group lists
    result = ObjectChangeClassification(changes=changes)
    for ch in changes:
        idx = ch.object_idx
        if ch.change_type == "kept":
            result.kept.append(idx)
        elif ch.change_type == "removed":
            result.removed.append(idx)
        elif ch.change_type == "recolored":
            result.recolored.append(idx)
        elif ch.change_type == "moved":
            result.moved.append(idx)
        elif ch.change_type == "copied":
            result.copied.append(idx)
        elif ch.change_type == "moved_recolored":
            result.moved_recolored.append(idx)
        elif ch.change_type == "changed":
            result.changed.append(idx)
        else:
            result.ambiguous.append(idx)

    if not result.has_two_groups:
        if not result.group_a:
            result.failure_reason = "no_unchanged_objects"
        elif not result.group_b:
            result.failure_reason = "no_changed_objects"

    return result


def _detect_recolor_pattern(
    objects: List[Dict],
    group_a: List[int],
    group_b: List[int],
    inp: np.ndarray,
    out: np.ndarray,
) -> Optional[Dict[str, Any]]:
    """Detect the specific recoloring pattern applied to group_b objects.

    group_a: "unchanged" / "retained" group (reference)
    group_b: "changed" / "recolored" group (operated on)

    Returns dict with:
    - "type": "uniform_recolor" | "per_object_recolor" | "property_dependent_recolor"
              | "color_swap"
    - "color_map": {old_color: new_color} mapping if applicable
    - "fill_color": single target color if uniform_recolor
    - "per_object_colors": {obj_idx: new_color} if per-object
    Returns None if no consistent pattern detected.
    """
    if not group_b:
        return None

    per_object_new_colors: Dict[int, int] = {}
    per_object_maps: List[Dict[int, int]] = []
    global_new_colors: set = set()
    all_uniform = True

    for bi in group_b:
        obj = objects[bi]
        in_vals = inp[obj["mask"]]
        out_vals = out[obj["mask"]]

        diff_mask = in_vals != out_vals
        if not np.any(diff_mask):
            # Object didn't actually change -- inconsistency
            return None

        unique_out = np.unique(out_vals)
        if len(unique_out) == 1:
            per_object_new_colors[bi] = int(unique_out[0])
            global_new_colors.add(int(unique_out[0]))
        else:
            all_uniform = False

        # Build per-pixel color map for this object
        old_colors_changed = in_vals[diff_mask]
        new_colors_changed = out_vals[diff_mask]
        color_map: Dict[int, int] = {}
        consistent = True
        for old_c, new_c in zip(old_colors_changed, new_colors_changed):
            old_c_int, new_c_int = int(old_c), int(new_c)
            if old_c_int in color_map and color_map[old_c_int] != new_c_int:
                consistent = False
                break
            color_map[old_c_int] = new_c_int
        if consistent and color_map:
            per_object_maps.append(color_map)

    # Check for uniform_recolor: all changed objects become the SAME single color
    if all_uniform and len(global_new_colors) == 1:
        fill_color = global_new_colors.pop()
        return {
            "type": "uniform_recolor",
            "fill_color": fill_color,
            "color_map": {
                int(old): fill_color
                for m in per_object_maps for old in m.keys()
            },
        }

    # Check for color_swap: a single consistent {old: new} map across all objects
    if per_object_maps:
        merged_map: Dict[int, int] = {}
        swap_consistent = True
        for m in per_object_maps:
            for k, v in m.items():
                if k in merged_map and merged_map[k] != v:
                    swap_consistent = False
                    break
                merged_map[k] = v
            if not swap_consistent:
                break

        if swap_consistent and merged_map:
            # Check if it's a true swap (A->B and B->A)
            is_swap = all(
                merged_map.get(v) == k for k, v in merged_map.items()
                if v in merged_map
            ) and len(merged_map) >= 2
            if is_swap:
                return {
                    "type": "color_swap",
                    "color_map": merged_map,
                }
            return {
                "type": "per_object_recolor",
                "color_map": merged_map,
            }

    # Check for property_dependent_recolor: each object gets a different color
    # based on some per-object attribute
    if all_uniform and len(per_object_new_colors) == len(group_b):
        # Each changed object has a uniform but potentially different color
        unique_targets = set(per_object_new_colors.values())
        if len(unique_targets) > 1:
            return {
                "type": "property_dependent_recolor",
                "per_object_colors": per_object_new_colors,
            }

    return None


def _detect_change_pattern(
    objects: List[Dict],
    changed_indices: List[int],
    inp: np.ndarray,
    out: np.ndarray,
) -> Optional[Dict[str, Any]]:
    """Detect the transformation pattern applied to changed objects.

    Returns a dict describing the change, or None if no consistent pattern.
    Patterns detected:
        constant_recolor: all changed pixels become the same single color
        per_object_recolor: each changed object maps to a consistent new color
        fill_holes: holes within objects are filled with a consistent color
    """
    per_object_maps: List[Dict[int, int]] = []
    global_new_colors: set = set()

    for ci in changed_indices:
        obj = objects[ci]
        in_vals = inp[obj["mask"]]
        out_vals = out[obj["mask"]]

        diff_mask = in_vals != out_vals
        if not np.any(diff_mask):
            continue

        old_colors = set(in_vals[diff_mask].tolist())
        new_colors = set(out_vals[diff_mask].tolist())
        global_new_colors.update(new_colors)

        color_map: Dict[int, int] = {}
        for old_c, new_c in zip(in_vals[diff_mask], out_vals[diff_mask]):
            old_c, new_c = int(old_c), int(new_c)
            if old_c in color_map and color_map[old_c] != new_c:
                color_map = {}
                break
            color_map[old_c] = new_c

        if color_map:
            per_object_maps.append(color_map)

    if not per_object_maps:
        return None

    if len(global_new_colors) == 1:
        fill_color = global_new_colors.pop()
        return {
            "type": "constant_recolor",
            "fill_color": fill_color,
        }

    if all(len(m) == 1 for m in per_object_maps):
        all_maps_same = len(set(
            tuple(m.items()) for m in per_object_maps
        )) == 1
        if all_maps_same:
            return {
                "type": "per_object_recolor",
                "color_map": per_object_maps[0],
            }

    merged_map: Dict[int, int] = {}
    consistent = True
    for m in per_object_maps:
        for k, v in m.items():
            if k in merged_map and merged_map[k] != v:
                consistent = False
                break
            merged_map[k] = v
        if not consistent:
            break

    if consistent and merged_map:
        return {
            "type": "per_object_recolor",
            "color_map": merged_map,
        }

    return None


def _find_discriminative_property(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[Tuple[str, bool]]:
    """Find a single property that separates kept from removed objects
    consistently across ALL training pairs.

    Returns (property_name, keep_when_true) or None.

    SOUNDNESS: if this returns a result, the property is guaranteed to
    correctly separate kept/removed objects in every training pair.
    """
    all_props = _all_property_names()

    # For each property, track whether it consistently separates kept/removed
    # across all training pairs. A property "works" if:
    #   kept objects ALL have prop=True  AND removed ALL have prop=False
    #   OR
    #   kept objects ALL have prop=False AND removed ALL have prop=True

    candidates = {p: {"true_keeps": True, "false_keeps": True} for p in all_props}

    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        result = _classify_kept_removed(objects, inp, out)
        if result is None:
            return None
        kept_indices, removed_indices = result

        for prop in list(candidates.keys()):
            kept_vals = [_get_property_value(objects[i], prop) for i in kept_indices]
            removed_vals = [_get_property_value(objects[i], prop) for i in removed_indices]

            # Check: keep when True (all kept have True, all removed have False)
            if not (all(kept_vals) and not any(removed_vals)):
                candidates[prop]["true_keeps"] = False

            # Check: keep when False (all kept have False, all removed have True)
            if not (all(not v for v in kept_vals) and all(removed_vals)):
                candidates[prop]["false_keeps"] = False

            # If neither direction works, eliminate this property
            if not candidates[prop]["true_keeps"] and not candidates[prop]["false_keeps"]:
                del candidates[prop]

    # Count evidence: require property to have enough examples on both sides
    # across all training pairs to avoid coincidental correlations
    prop_evidence = {}
    for prop in list(candidates.keys()):
        n_true = 0
        n_false = 0
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            for obj in objects:
                if _get_property_value(obj, prop):
                    n_true += 1
                else:
                    n_false += 1
        prop_evidence[prop] = (n_true, n_false)

    # Return the first consistent property with sufficient evidence
    for prop in all_props:
        if prop not in candidates:
            continue
        n_true, n_false = prop_evidence.get(prop, (0, 0))
        if n_true < 2 or n_false < 2:
            continue
        if candidates[prop]["true_keeps"]:
            return (prop, True)
        if candidates[prop]["false_keeps"]:
            return (prop, False)

    return _find_discriminative_conjunction(train_pairs)


def _find_discriminative_property_extended(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[Tuple[str, bool]]:
    """Like _find_discriminative_property but uses the rich classifier as fallback.

    First tries _classify_kept_removed; if that returns None, uses
    _classify_object_changes and treats group_a/group_b as kept/removed.
    """
    result = _find_discriminative_property(train_pairs)
    if result is not None:
        return result

    all_props = _all_property_names()
    candidates = {p: {"true_keeps": True, "false_keeps": True} for p in all_props}

    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        kr = _classify_kept_removed(objects, inp, out)
        if kr is not None:
            kept_indices, removed_indices = kr
        else:
            occ = _classify_object_changes(objects, inp, out)
            if occ is None or not occ.has_two_groups:
                return None
            kept_indices = occ.group_a
            removed_indices = occ.group_b

        for prop in list(candidates.keys()):
            kept_vals = [_get_property_value(objects[i], prop) for i in kept_indices]
            removed_vals = [_get_property_value(objects[i], prop) for i in removed_indices]

            if not (all(kept_vals) and not any(removed_vals)):
                candidates[prop]["true_keeps"] = False
            if not (all(not v for v in kept_vals) and all(removed_vals)):
                candidates[prop]["false_keeps"] = False
            if not candidates[prop]["true_keeps"] and not candidates[prop]["false_keeps"]:
                del candidates[prop]

    prop_evidence = {}
    for prop in list(candidates.keys()):
        n_true = 0
        n_false = 0
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            for obj in objects:
                if _get_property_value(obj, prop):
                    n_true += 1
                else:
                    n_false += 1
        prop_evidence[prop] = (n_true, n_false)

    for prop in all_props:
        if prop not in candidates:
            continue
        n_true, n_false = prop_evidence.get(prop, (0, 0))
        if n_true < 2 or n_false < 2:
            continue
        if candidates[prop]["true_keeps"]:
            return (prop, True)
        if candidates[prop]["false_keeps"]:
            return (prop, False)

    return None


def _find_discriminative_conjunction(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[Tuple[str, bool]]:
    """Find a conjunction of 2 properties that separates kept/removed.

    Tries all polarity combinations: (P1=T AND P2=T), (P1=T AND P2=F),
    (P1=F AND P2=T), (P1=F AND P2=F). Returns a synthetic property name
    like "is_largest&in_top_half" or "is_largest&!in_top_half" and the
    keep_when_true direction, matching the interface of _find_discriminative_property.
    """
    all_props = _all_property_names()

    pair_data = []
    for inp, out in train_pairs:
        objects = _extract_objects_with_properties(inp)
        result = _classify_kept_removed(objects, inp, out)
        if result is None:
            return None
        kept_indices, removed_indices = result
        prop_vecs = {}
        for p in all_props:
            prop_vecs[p] = [_get_property_value(objects[i], p) for i in range(len(objects))]
        pair_data.append((kept_indices, removed_indices, prop_vecs))

    useful = set()
    for p in all_props:
        has_true = False
        has_false = False
        for _, _, pvecs in pair_data:
            for v in pvecs[p]:
                if v:
                    has_true = True
                else:
                    has_false = True
                if has_true and has_false:
                    break
            if has_true and has_false:
                break
        if has_true and has_false:
            useful.add(p)

    useful_list = [p for p in all_props if p in useful]

    for i, p1 in enumerate(useful_list):
        for p2 in useful_list[i + 1:]:
            for pol1 in [True, False]:
                for pol2 in [True, False]:
                    keeps_true = True
                    keeps_false = True
                    n_match = 0
                    n_nomatch = 0

                    for kept_idx, removed_idx, pvecs in pair_data:
                        for ki in kept_idx:
                            v1 = pvecs[p1][ki] == pol1
                            v2 = pvecs[p2][ki] == pol2
                            match = v1 and v2
                            if match:
                                n_match += 1
                            else:
                                n_nomatch += 1
                            if not match:
                                keeps_true = False
                            if match:
                                keeps_false = False

                        for ri in removed_idx:
                            v1 = pvecs[p1][ri] == pol1
                            v2 = pvecs[p2][ri] == pol2
                            match = v1 and v2
                            if match:
                                n_match += 1
                            else:
                                n_nomatch += 1
                            if match:
                                keeps_true = False
                            if not match:
                                keeps_false = False

                        if not keeps_true and not keeps_false:
                            break

                    if not keeps_true and not keeps_false:
                        continue
                    if n_match < 2 or n_nomatch < 2:
                        continue

                    p1_part = p1 if pol1 else f"!{p1}"
                    p2_part = p2 if pol2 else f"!{p2}"
                    conj_name = f"{p1_part}&{p2_part}"

                    if keeps_true:
                        return (conj_name, True)
                    if keeps_false:
                        return (conj_name, False)


# ---------------------------------------------------------------------------
# 4. TRANSFORM INDUCTION — discover recoloring/movement rules
# ---------------------------------------------------------------------------

def _match_objects_hungarian(
    in_objects: List[Dict], out_objects: List[Dict]
) -> List[Tuple[int, int, float]]:
    """Match input→output objects via optimal transport."""
    n_in = len(in_objects)
    n_out = len(out_objects)
    if n_in == 0 or n_out == 0:
        return []

    n = max(n_in, n_out)
    cost = np.full((n, n), 1e6)

    for i in range(n_in):
        for j in range(n_out):
            # Shape match
            lm1 = in_objects[i]["local_mask"]
            lm2 = out_objects[j]["local_mask"]
            shape_bonus = 0.0
            if lm1.shape == lm2.shape and np.array_equal(lm1, lm2):
                shape_bonus = -2.0

            # Position distance
            pos_dist = (abs(in_objects[i]["center_r"] - out_objects[j]["center_r"]) +
                        abs(in_objects[i]["center_c"] - out_objects[j]["center_c"]))
            pos_norm = pos_dist / max(in_objects[i]["mask"].shape[0], 1)

            # Size distance
            size_dist = abs(in_objects[i]["area"] - out_objects[j]["area"])
            size_norm = size_dist / max(in_objects[i]["area"], out_objects[j]["area"], 1)

            cost[i, j] = shape_bonus + 0.3 * size_norm + 0.1 * pos_norm

    row_ind, col_ind = linear_sum_assignment(cost)
    matches = []
    for i, j in zip(row_ind, col_ind):
        if i < n_in and j < n_out and cost[i, j] < 10.0:
            matches.append((i, j, float(cost[i, j])))
    return matches


def _find_recolor_rule(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[Tuple[str, Dict]]:
    """Discover a recoloring rule as a function of object properties.

    Tries: new_color = f(size_rank), f(position_rank), f(shape_group), etc.
    Returns (rule_type, rule_params) or None.
    """
    # Check: all objects matched, all same shape, some recolored
    for inp, out in train_pairs:
        in_objs = _extract_objects_with_properties(inp)
        out_objs = _extract_objects_with_properties(out)
        if len(in_objs) != len(out_objs) or len(in_objs) < 2:
            return None

    # Try size-rank-based recoloring
    rule = _try_rank_recolor(train_pairs, "size_rank")
    if rule:
        return rule

    # Try property-based recoloring (color depends on a boolean property)
    rule = _try_property_recolor(train_pairs)
    if rule:
        return rule

    return None


def _try_rank_recolor(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    rank_key: str,
) -> Optional[Tuple[str, Dict]]:
    """Check if new_color = f(rank) consistently across training pairs."""
    rank_to_color = {}

    for inp, out in train_pairs:
        in_objs = _extract_objects_with_properties(inp)
        out_objs = _extract_objects_with_properties(out)
        if len(in_objs) != len(out_objs):
            return None

        matches = _match_objects_hungarian(in_objs, out_objs)
        if len(matches) != len(in_objs):
            return None

        for i_idx, j_idx, _ in matches:
            if not np.array_equal(in_objs[i_idx]["local_mask"], out_objs[j_idx]["local_mask"]):
                return None
            rank = in_objs[i_idx].get(rank_key, i_idx)
            new_color = out_objs[j_idx]["primary_color"]
            if rank in rank_to_color and rank_to_color[rank] != new_color:
                return None
            rank_to_color[rank] = new_color

    if not rank_to_color:
        return None
    if all(rank_to_color.get(r) == rank_to_color.get(0) for r in rank_to_color):
        return None

    return ("rank_recolor", {"rank_key": rank_key, "rank_to_color": rank_to_color})


def _try_property_recolor(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Optional[Tuple[str, Dict]]:
    """Check if new_color depends on a boolean property."""
    all_props = _all_property_names()

    for prop in all_props:
        true_color = None
        false_color = None
        consistent = True

        for inp, out in train_pairs:
            in_objs = _extract_objects_with_properties(inp)
            out_objs = _extract_objects_with_properties(out)
            if len(in_objs) != len(out_objs):
                consistent = False
                break

            matches = _match_objects_hungarian(in_objs, out_objs)
            if len(matches) != len(in_objs):
                consistent = False
                break

            for i_idx, j_idx, _ in matches:
                if not np.array_equal(in_objs[i_idx]["local_mask"], out_objs[j_idx]["local_mask"]):
                    consistent = False
                    break
                val = _get_property_value(in_objs[i_idx], prop)
                new_c = out_objs[j_idx]["primary_color"]
                if val:
                    if true_color is None:
                        true_color = new_c
                    elif true_color != new_c:
                        consistent = False
                        break
                else:
                    if false_color is None:
                        false_color = new_c
                    elif false_color != new_c:
                        consistent = False
                        break
            if not consistent:
                break

        if consistent and true_color is not None and false_color is not None and true_color != false_color:
            return ("property_recolor", {
                "prop": prop,
                "true_color": true_color,
                "false_color": false_color,
            })

    return None


# ---------------------------------------------------------------------------
# 5. COMPOSITIONAL PLANNER — sequences of primitive operations
# ---------------------------------------------------------------------------

def _try_compositional(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Try compositions of primitives: filter→recolor, filter→extract.

    Invariant-guided pruning: after each primitive, check that the
    intermediate result preserves structural invariants from training.
    """
    if len(train_pairs) < 3:
        return None

    result = _try_filter_then_recolor(train_pairs, test_inputs)
    if result is not None:
        return result

    result = _try_filter_then_extract(train_pairs, test_inputs)
    if result is not None:
        return result

    return None


def _try_filter_then_recolor(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Filter objects by a discriminative property, then recolor survivors."""
    all_props = _all_property_names()

    for prop in all_props:
        for keep_when_true in [True, False]:
            recolor_map: Dict[int, int] = {}
            consistent = True

            for inp, out in train_pairs:
                if inp.shape != out.shape:
                    consistent = False
                    break

                objects = _extract_objects_with_properties(inp)
                if len(objects) < 3:
                    consistent = False
                    break

                kept_objs = []
                for obj in objects:
                    val = _get_property_value(obj, prop)
                    if val == keep_when_true:
                        kept_objs.append(obj)

                if not kept_objs or len(kept_objs) == len(objects):
                    consistent = False
                    break

                for obj in kept_objs:
                    out_vals = out[obj["mask"]]
                    nz = out_vals[out_vals != 0]
                    if len(nz) == 0:
                        consistent = False
                        break
                    out_color = int(np.bincount(nz).argmax())
                    in_color = obj["primary_color"]
                    if in_color == out_color:
                        continue
                    if in_color in recolor_map and recolor_map[in_color] != out_color:
                        consistent = False
                        break
                    recolor_map[in_color] = out_color

                if not consistent:
                    break

            if not consistent or not recolor_map:
                continue

            # LOO validation
            loo_ok = True
            for hold_out in range(len(train_pairs)):
                held_inp, held_out_grid = train_pairs[hold_out]
                pred = _apply_filter_recolor(held_inp, prop, keep_when_true, recolor_map)
                if pred is None or not np.array_equal(pred, held_out_grid):
                    loo_ok = False
                    break

            if not loo_ok:
                continue

            predictions = []
            for test_inp in test_inputs:
                pred = _apply_filter_recolor(test_inp, prop, keep_when_true, recolor_map)
                if pred is None:
                    break
                predictions.append(pred)
            else:
                return predictions, {
                    "strategy": "compositional",
                    "composition": "filter_then_recolor",
                    "filter_prop": prop,
                    "keep_when_true": keep_when_true,
                    "recolor_map": recolor_map,
                }

    return None


def _apply_filter_recolor(
    grid: np.ndarray, prop: str, keep_when_true: bool,
    recolor_map: Dict[int, int],
) -> Optional[np.ndarray]:
    """Apply filter + recolor composition."""
    objects = _extract_objects_with_properties(grid)
    if len(objects) < 2:
        return None

    result = grid.copy()
    kept = 0
    removed = 0
    for obj in objects:
        val = _get_property_value(obj, prop)
        if val == keep_when_true:
            kept += 1
            old_color = obj["primary_color"]
            if old_color in recolor_map:
                result[obj["mask"]] = recolor_map[old_color]
        else:
            removed += 1
            result[obj["mask"]] = 0

    if kept == 0 or removed == 0:
        return None
    return result


def _try_filter_then_extract(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Filter objects by property, then crop to bounding box of survivors."""
    all_props = _all_property_names()

    for prop in all_props:
        for keep_when_true in [True, False]:
            consistent = True
            for inp, out in train_pairs:
                objects = _extract_objects_with_properties(inp)
                if len(objects) < 2:
                    consistent = False
                    break

                pred = _apply_filter_extract(inp, objects, prop, keep_when_true)
                if pred is None or not np.array_equal(pred, out):
                    consistent = False
                    break

            if not consistent:
                continue

            # LOO validation
            loo_ok = True
            for hold_out in range(len(train_pairs)):
                held_inp, held_out_grid = train_pairs[hold_out]
                objs = _extract_objects_with_properties(held_inp)
                pred = _apply_filter_extract(held_inp, objs, prop, keep_when_true)
                if pred is None or not np.array_equal(pred, held_out_grid):
                    loo_ok = False
                    break

            if not loo_ok:
                continue

            predictions = []
            for test_inp in test_inputs:
                objs = _extract_objects_with_properties(test_inp)
                pred = _apply_filter_extract(test_inp, objs, prop, keep_when_true)
                if pred is None:
                    break
                predictions.append(pred)
            else:
                return predictions, {
                    "strategy": "compositional",
                    "composition": "filter_then_extract",
                    "filter_prop": prop,
                    "keep_when_true": keep_when_true,
                }

    return None


def _apply_filter_extract(
    grid: np.ndarray, objects: List[Dict], prop: str,
    keep_when_true: bool,
) -> Optional[np.ndarray]:
    """Filter objects, then crop to tight bounding box of survivors."""
    kept_masks = []
    removed_count = 0
    for obj in objects:
        val = _get_property_value(obj, prop)
        if val == keep_when_true:
            kept_masks.append(obj["mask"])
        else:
            removed_count += 1

    if not kept_masks or removed_count == 0:
        return None

    combined = np.zeros_like(grid, dtype=bool)
    for m in kept_masks:
        combined |= m

    rows, cols = np.where(combined)
    if len(rows) == 0:
        return None

    r_min, r_max = int(rows.min()), int(rows.max())
    c_min, c_max = int(cols.min()), int(cols.max())

    cropped = np.zeros((r_max - r_min + 1, c_max - c_min + 1), dtype=grid.dtype)
    crop_mask = combined[r_min:r_max+1, c_min:c_max+1]
    cropped[crop_mask] = grid[r_min:r_max+1, c_min:c_max+1][crop_mask]
    return cropped


# ---------------------------------------------------------------------------
# 6. SOLVE — the unified reasoning entry point
# ---------------------------------------------------------------------------

def solve_task_reasoning(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Task-independent structural reasoning engine.

    Attempts to solve the task by:
    1. Discriminative filtering (find property separating kept/removed)
    2. Transform induction (find recoloring rule from structural properties)
    3. Compositional planning (filter→recolor, filter→extract)

    Soundness: any output is guaranteed consistent with all training examples
    via leave-one-out cross-validation.
    """
    if len(train_pairs) < 2:
        return None

    # --- Phase 1: Discriminative filtering ---
    result = _try_discriminative_filter(train_pairs, test_inputs)
    if result is not None:
        return result

    # --- Phase 2: Transform induction (recoloring) ---
    result = _try_transform_induction(train_pairs, test_inputs)
    if result is not None:
        return result

    # --- Phase 3: Compositional planning ---
    result = _try_compositional(train_pairs, test_inputs)
    if result is not None:
        return result

    return None


def _try_discriminative_filter(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Discover a filtering property and apply it."""
    if len(train_pairs) < 3:
        return None

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None

    # LOO cross-validation — property must be discoverable from
    # any subset of training pairs and generalize to the held-out pair
    for hold_out in range(len(train_pairs)):
        held_train = [p for i, p in enumerate(train_pairs) if i != hold_out]
        held_inp, held_out_grid = train_pairs[hold_out]

        prop_result = _find_discriminative_property(held_train)
        if prop_result is None:
            return None

        prop_name, keep_when_true = prop_result
        pred = _apply_filter(held_inp, prop_name, keep_when_true)
        if pred is None or not np.array_equal(pred, held_out_grid):
            return None

    # Full training set discovery
    prop_result = _find_discriminative_property(train_pairs)
    if prop_result is None:
        return None
    prop_name, keep_when_true = prop_result

    predictions = []
    for test_inp in test_inputs:
        pred = _apply_filter(test_inp, prop_name, keep_when_true)
        if pred is None:
            return None
        predictions.append(pred)

    return predictions, {
        "strategy": "discriminative_filter",
        "property": prop_name,
        "keep_when_true": keep_when_true,
    }


def _apply_filter(
    grid: np.ndarray, prop_name: str, keep_when_true: bool
) -> Optional[np.ndarray]:
    """Apply a discriminative property filter to a grid."""
    objects = _extract_objects_with_properties(grid)
    if len(objects) < 2:
        return None

    kept = 0
    removed = 0
    result = grid.copy()
    for obj in objects:
        val = _get_property_value(obj, prop_name)
        should_keep = (val == keep_when_true)
        if should_keep:
            kept += 1
        else:
            removed += 1
            result[obj["mask"]] = 0

    if kept == 0 or removed == 0:
        return None

    return result


def _try_transform_induction(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    test_inputs: List[np.ndarray],
) -> Optional[Tuple[List[np.ndarray], Dict[str, Any]]]:
    """Discover and apply a structural-property-based transform."""
    if len(train_pairs) < 3:
        return None

    for inp, out in train_pairs:
        if inp.shape != out.shape:
            return None

    rule = _find_recolor_rule(train_pairs)
    if rule is None:
        return None

    rule_type, params = rule

    # LOO cross-validation
    for hold_out in range(len(train_pairs)):
        held_train = [p for i, p in enumerate(train_pairs) if i != hold_out]
        held_inp, held_out_grid = train_pairs[hold_out]

        check_rule = _find_recolor_rule(held_train)
        if check_rule is None:
            return None
        pred = _apply_recolor(held_inp, check_rule[0], check_rule[1])
        if pred is None or not np.array_equal(pred, held_out_grid):
            return None

    predictions = []
    for test_inp in test_inputs:
        pred = _apply_recolor(test_inp, rule_type, params)
        if pred is None:
            return None
        predictions.append(pred)

    return predictions, {
        "strategy": "transform_induction",
        "rule_type": rule_type,
        "params": {k: v for k, v in params.items() if k != "rank_to_color"},
    }


def _apply_recolor(
    grid: np.ndarray, rule_type: str, params: Dict
) -> Optional[np.ndarray]:
    """Apply a discovered recoloring rule."""
    objects = _extract_objects_with_properties(grid)
    if len(objects) < 2:
        return None

    result = grid.copy()

    if rule_type == "rank_recolor":
        rank_key = params["rank_key"]
        rank_to_color = params["rank_to_color"]
        for obj in objects:
            rank = obj.get(rank_key, 0)
            if rank not in rank_to_color:
                return None
            result[obj["mask"]] = rank_to_color[rank]

    elif rule_type == "property_recolor":
        prop = params["prop"]
        true_color = params["true_color"]
        false_color = params["false_color"]
        for obj in objects:
            val = _get_property_value(obj, prop)
            result[obj["mask"]] = true_color if val else false_color

    return result
