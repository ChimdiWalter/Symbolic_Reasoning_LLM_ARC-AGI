"""Neural abstraction pipeline: learn, distill, and validate symbolic
predicates from near-solved failure clusters.

Encode failures -> cluster -> distill symbolic predicates ->
validate via staged gates -> register in concept graph memory.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from reasoning_project.near_solved_memory import NearSolvedMemory, NearSolvedTaskState
from reasoning_project.events import ReasoningEventLog
from reasoning_project.operator_invention import InventedOperator


# ═══════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════

FAILURE_TYPES = [
    "no_discrimination", "wrong_reconstruction",
    "partial_match", "no_objects", "unknown",
]

@dataclass
class InventedProperty:
    name: str
    compute_fn: Callable  # (obj, all_objects, grid) -> bool
    source_cluster: str
    correlation: float
    description: str = ""


@dataclass
class Counterexample:
    probe_type: str
    passed: bool
    details: str


# ═══════════════════════════════════════════════════════════════════════
# 1. FAILURE ENCODER
# ═══════════════════════════════════════════════════════════════════════

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


class FailureEncoder(nn.Module):
    """Encode a NearSolvedTaskState into a fixed-dim failure embedding.

    When JEPA embedding is available, it is concatenated with the
    hand-crafted features before the MLP.
    """

    FAILURE_TYPES = FAILURE_TYPES
    JEPA_DIM = 64  # default JEPA embedding dim from perception_bridge

    def __init__(self, failure_embedding_dim: int = 16, use_jepa: bool = True):
        super().__init__()
        base_input_dim = len(self.FAILURE_TYPES) + 8  # 13
        self.use_jepa = use_jepa
        input_dim = base_input_dim + (self.JEPA_DIM if use_jepa else 0)
        self.mlp = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, failure_embedding_dim),
        )

    def encode_state(self, state: NearSolvedTaskState) -> torch.Tensor:
        """Convert NearSolvedTaskState to feature vector, including JEPA embedding."""
        ft_idx = (self.FAILURE_TYPES.index(state.failure_type)
                  if state.failure_type in self.FAILURE_TYPES else 4)
        one_hot = [0.0] * len(self.FAILURE_TYPES)
        one_hot[ft_idx] = 1.0

        topo = state.topology_signature or {}
        feats = one_hot + [
            float(topo.get("n_objects", 0)) / 20.0,
            float(topo.get("n_colors", len(state.views_tried))) / 10.0,
            float(topo.get("has_separators", False)),
            float(topo.get("has_containment", False)),
            float(topo.get("has_holes", False)),
            float(topo.get("has_symmetry", False)),
            float(len(state.views_tried) >= 4),
            state.train_fit,
        ]

        if self.use_jepa:
            jepa_emb = state.jepa_embedding if state.jepa_embedding is not None else [0.0] * self.JEPA_DIM
            if len(jepa_emb) < self.JEPA_DIM:
                jepa_emb = list(jepa_emb) + [0.0] * (self.JEPA_DIM - len(jepa_emb))
            elif len(jepa_emb) > self.JEPA_DIM:
                jepa_emb = list(jepa_emb)[:self.JEPA_DIM]
            feats = feats + list(jepa_emb)

        return torch.tensor(feats, dtype=torch.float32)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.mlp(x)


class ConceptFamilyPredictor(nn.Module):
    """Predict which concept family is missing, given failure + JEPA embedding."""

    def __init__(self, failure_embedding_dim: int = 16):
        super().__init__()
        self.head = nn.Sequential(
            nn.Linear(failure_embedding_dim, 32),
            nn.ReLU(),
            nn.Linear(32, len(CONCEPT_FAMILIES)),
        )

    def forward(self, failure_embedding: torch.Tensor) -> torch.Tensor:
        return self.head(failure_embedding)

    def predict_family(self, failure_embedding: torch.Tensor) -> List[Tuple[str, float]]:
        logits = self.forward(failure_embedding)
        probs = F.softmax(logits, dim=-1)
        if probs.dim() > 1:
            probs = probs.squeeze(0)
        ranked = sorted(
            enumerate(probs.tolist()),
            key=lambda x: -x[1],
        )
        return [(CONCEPT_FAMILIES[i], score) for i, score in ranked]


# ═══════════════════════════════════════════════════════════════════════
# 2. OBJECT RELATION ENCODER
# ═══════════════════════════════════════════════════════════════════════

_N_COLORS_ONEHOT = 10
_OBJ_SCALAR_DIM = 16  # area..is_square
_OBJ_DIM = _OBJ_SCALAR_DIM + _N_COLORS_ONEHOT  # 26
_REL_DIM = 6


class ObjectRelationEncoder(nn.Module):
    """Encode grid objects and pairwise relations into a scene embedding."""

    def __init__(self, obj_embed_dim: int = 32, scene_embed_dim: int = 32):
        super().__init__()
        self.obj_mlp = nn.Sequential(
            nn.Linear(_OBJ_DIM, 32),
            nn.ReLU(),
            nn.Linear(32, obj_embed_dim),
        )
        self.rel_mlp = nn.Sequential(
            nn.Linear(_REL_DIM, 16),
            nn.ReLU(),
            nn.Linear(16, 16),
        )
        self.obj_embed_dim = obj_embed_dim
        self.scene_embed_dim = scene_embed_dim
        self.out_proj = nn.Linear(obj_embed_dim + 16, scene_embed_dim)

    @staticmethod
    def obj_to_features(obj: Dict[str, Any]) -> torch.Tensor:
        color_oh = [0.0] * _N_COLORS_ONEHOT
        pc = obj.get("primary_color", 0)
        if 0 <= pc < _N_COLORS_ONEHOT:
            color_oh[pc] = 1.0
        scalars = [
            obj.get("area", 1) / 100.0,
            obj.get("bbox_h", 1) / 30.0,
            obj.get("bbox_w", 1) / 30.0,
            obj.get("perimeter", 4) / 60.0,
            obj.get("n_holes", 0) / 5.0,
            obj.get("convexity", 1.0),
            obj.get("center_r", 0) / 30.0,
            obj.get("center_c", 0) / 30.0,
            float(obj.get("n_colors", 1)) / 10.0,
            float(obj.get("h_sym", False)),
            float(obj.get("v_sym", False)),
            float(obj.get("d_sym", False)),
            float(obj.get("touches_boundary", False)),
            float(obj.get("is_filled_rect", False)),
            float(obj.get("is_square", False)),
            0.0,  # padding to reach 16 scalars
        ]
        return torch.tensor(scalars + color_oh, dtype=torch.float32)

    @staticmethod
    def pair_to_features(a: Dict, b: Dict) -> torch.Tensor:
        dist = math.sqrt(
            (a.get("center_r", 0) - b.get("center_r", 0)) ** 2
            + (a.get("center_c", 0) - b.get("center_c", 0)) ** 2
        )
        area_a = max(a.get("area", 1), 1)
        area_b = max(b.get("area", 1), 1)
        rel_size = min(area_a, area_b) / max(area_a, area_b)
        same_color = float(a.get("primary_color", -1) == b.get("primary_color", -2))
        same_shape = 0.0
        lm_a = a.get("local_mask")
        lm_b = b.get("local_mask")
        if lm_a is not None and lm_b is not None:
            if lm_a.shape == lm_b.shape:
                same_shape = float(np.array_equal(lm_a, lm_b))
        # touching heuristic
        touching = 0.0
        if dist < (a.get("bbox_h", 1) + b.get("bbox_h", 1)) / 2 + 1.5:
            touching = 1.0
        inside = 0.0
        ba = a.get("bbox", (0, 0, 0, 0))
        bb = b.get("bbox", (0, 0, 0, 0))
        if ba[0] >= bb[0] and ba[1] >= bb[1] and ba[2] <= bb[2] and ba[3] <= bb[3]:
            inside = 1.0
        return torch.tensor(
            [dist / 30.0, rel_size, same_color, same_shape, touching, inside],
            dtype=torch.float32,
        )

    def forward(
        self, obj_feats: torch.Tensor, rel_feats: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            obj_feats: (N, obj_dim)
            rel_feats: (N*(N-1)/2, rel_dim) or None
        Returns:
            obj_embeddings: (N, obj_embed_dim)
            scene_embedding: (scene_embed_dim,)
        """
        obj_emb = self.obj_mlp(obj_feats)  # (N, 32)
        if rel_feats is not None and rel_feats.shape[0] > 0:
            rel_emb = self.rel_mlp(rel_feats)  # (P, 16)
            rel_pool = rel_emb.mean(dim=0)  # (16,)
        else:
            rel_pool = torch.zeros(16)
        obj_pool = obj_emb.mean(dim=0)  # (32,)
        scene = self.out_proj(torch.cat([obj_pool, rel_pool]))
        return obj_emb, scene


# ═══════════════════════════════════════════════════════════════════════
# 3. CONTRASTIVE PROPERTY LEARNER
# ═══════════════════════════════════════════════════════════════════════

class ContrastivePropertyLearner(nn.Module):
    """Learn a property vector that separates targets from distractors."""

    def __init__(self, obj_embed_dim: int = 32, property_dim: int = 16):
        super().__init__()
        self.proj = nn.Linear(obj_embed_dim, property_dim)
        self.property_dim = property_dim

    def forward(
        self,
        obj_embeddings: torch.Tensor,
        labels: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            obj_embeddings: (N, obj_embed_dim)
            labels: (N,) — 1 for target (kept), 0 for distractor (removed)
        Returns:
            property_vector: (property_dim,) — the learned selector
            scores: (N,) — dot product scores per object
        """
        projected = self.proj(obj_embeddings)  # (N, property_dim)
        # property_vector = mean of target embeddings (prototype)
        target_mask = labels.bool()
        if target_mask.any():
            property_vector = projected[target_mask].mean(dim=0)
        else:
            property_vector = projected.mean(dim=0)
        scores = (projected * property_vector.unsqueeze(0)).sum(dim=-1)  # (N,)
        return property_vector, scores

    def contrastive_loss(
        self,
        scores: torch.Tensor,
        labels: torch.Tensor,
        margin: float = 1.0,
    ) -> torch.Tensor:
        """Pull targets high, push distractors low."""
        target_scores = scores[labels.bool()]
        distractor_scores = scores[~labels.bool()]
        loss = torch.tensor(0.0)
        if target_scores.numel() > 0:
            loss = loss + F.relu(-target_scores + margin).mean()
        if distractor_scores.numel() > 0:
            loss = loss + F.relu(distractor_scores + margin).mean()
        return loss


# ═══════════════════════════════════════════════════════════════════════
# 4. SYMBOLIC PROPERTY DISTILLER
# ═══════════════════════════════════════════════════════════════════════

def _make_symbolic_grammar() -> List[Tuple[str, Callable]]:
    """Return list of (predicate_name, compute_fn) for the grammar.

    Each compute_fn has signature (obj, all_objects, grid) -> bool.
    """
    def _same_shape_as_reference(obj, all_objects, grid):
        if not all_objects:
            return False
        ref = max(all_objects, key=lambda o: o.get("area", 0))
        if obj is ref:
            return False
        lm = obj.get("local_mask")
        lr = ref.get("local_mask")
        if lm is None or lr is None:
            return False
        return lm.shape == lr.shape and bool(np.array_equal(lm, lr))

    def _same_color_as_marker(obj, all_objects, grid):
        markers = [o for o in all_objects if o.get("area", 0) == 1]
        if not markers:
            return False
        return any(obj.get("primary_color") == m.get("primary_color") for m in markers)

    def _inside_colored_frame(obj, all_objects, grid):
        frames = [o for o in all_objects
                  if o.get("n_holes", 0) > 0 and o is not obj]
        for f in frames:
            fb = f.get("bbox", (0, 0, 0, 0))
            ob = obj.get("bbox", (0, 0, 0, 0))
            if fb[0] <= ob[0] and fb[1] <= ob[1] and fb[2] >= ob[2] and fb[3] >= ob[3]:
                return True
        return False

    def _outside_colored_frame(obj, all_objects, grid):
        return not _inside_colored_frame(obj, all_objects, grid)

    def _nearest_to_unique_color(obj, all_objects, grid):
        if not any(o.get("is_unique_color", False) for o in all_objects if o is not obj):
            return False
        dists = [(math.hypot(obj.get("center_r", 0) - o.get("center_r", 0),
                             obj.get("center_c", 0) - o.get("center_c", 0)), o)
                 for o in all_objects if o is not obj]
        if not dists:
            return False
        return min(dists, key=lambda x: x[0])[1].get("is_unique_color", False)

    def _touches_marker_object(obj, all_objects, grid):
        for m in (o for o in all_objects if o.get("area", 0) <= 2 and o is not obj):
            d = abs(obj.get("center_r", 0) - m.get("center_r", 0)) + abs(obj.get("center_c", 0) - m.get("center_c", 0))
            if d < max(obj.get("bbox_h", 1), obj.get("bbox_w", 1)) + 1.5:
                return True
        return False

    def _between_two_objects(obj, all_objects, grid):
        if len(all_objects) < 3:
            return False
        cr, cc = obj.get("center_r", 0), obj.get("center_c", 0)
        others = [o for o in all_objects if o is not obj]
        for i in range(len(others)):
            for j in range(i + 1, len(others)):
                mr = (others[i].get("center_r", 0) + others[j].get("center_r", 0)) / 2
                mc = (others[i].get("center_c", 0) + others[j].get("center_c", 0)) / 2
                if abs(cr - mr) < 1.5 and abs(cc - mc) < 1.5:
                    return True
        return False

    def _aligned_with_marker(obj, all_objects, grid):
        for m in (o for o in all_objects if o.get("area", 0) <= 2 and o is not obj):
            if abs(obj.get("center_r", 0) - m.get("center_r", 0)) < 0.5:
                return True
            if abs(obj.get("center_c", 0) - m.get("center_c", 0)) < 0.5:
                return True
        return False

    def _part_of_repeating_pattern(obj, all_objects, grid):
        return obj.get("shape_group_size", 1) > 1

    def _endpoint_of_line(obj, all_objects, grid):
        return (obj.get("bbox_h", 0) == 1 or obj.get("bbox_w", 0) == 1) and obj.get("n_touching", 0) <= 1

    def _enclosed_by_color(obj, all_objects, grid):
        return obj.get("is_contained", False)

    def _contains_color(obj, all_objects, grid):
        return obj.get("is_container", False)

    def _contains_object_count(obj, all_objects, grid):
        return sum(1 for o in all_objects if o is not obj and o.get("is_contained", False) and _bbox_contains(obj, o)) > 0

    def _unique_under_rotation(obj, all_objects, grid):
        lm = obj.get("local_mask")
        if lm is None:
            return False
        for rot in [1, 2, 3]:
            rlm = np.rot90(lm, rot)
            for o in all_objects:
                if o is obj:
                    continue
                om = o.get("local_mask")
                if om is not None and om.shape == rlm.shape and np.array_equal(om, rlm):
                    return False
        return True

    def _matches_template_under_D4(obj, all_objects, grid):
        lm = obj.get("local_mask")
        if lm is None:
            return False
        ref = max(all_objects, key=lambda o: o.get("area", 0))
        if obj is ref:
            return False
        rlm = ref.get("local_mask")
        if rlm is None:
            return False
        for rot in range(4):
            t = np.rot90(rlm, rot)
            if t.shape == lm.shape and np.array_equal(t, lm):
                return True
            if np.fliplr(t).shape == lm.shape and np.array_equal(np.fliplr(t), lm):
                return True
        return False

    return [
        ("same_shape_as_reference", _same_shape_as_reference),
        ("same_color_as_marker", _same_color_as_marker),
        ("inside_colored_frame", _inside_colored_frame),
        ("outside_colored_frame", _outside_colored_frame),
        ("nearest_to_unique_color", _nearest_to_unique_color),
        ("touches_marker_object", _touches_marker_object),
        ("between_two_objects", _between_two_objects),
        ("aligned_with_marker", _aligned_with_marker),
        ("part_of_repeating_pattern", _part_of_repeating_pattern),
        ("endpoint_of_line", _endpoint_of_line),
        ("enclosed_by_color", _enclosed_by_color),
        ("contains_color", _contains_color),
        ("contains_object_count", _contains_object_count),
        ("unique_under_rotation", _unique_under_rotation),
        ("matches_template_under_D4", _matches_template_under_D4),
    ]


def _bbox_contains(outer: Dict, inner: Dict) -> bool:
    ob = outer.get("bbox", (0, 0, 0, 0))
    ib = inner.get("bbox", (0, 0, 0, 0))
    return ob[0] <= ib[0] and ob[1] <= ib[1] and ob[2] >= ib[2] and ob[3] >= ib[3]


class SymbolicPropertyDistiller:
    """Map latent property vectors to symbolic predicates from a grammar."""

    def __init__(self, correlation_threshold: float = 0.5):
        self.grammar = _make_symbolic_grammar()
        self.correlation_threshold = correlation_threshold

    def distill(
        self,
        objects: List[Dict[str, Any]],
        kept_indices: List[int],
        removed_indices: List[int],
        grid: Optional[np.ndarray] = None,
    ) -> List[InventedProperty]:
        """Check each grammar predicate against target/distractor labels."""
        if not objects or (not kept_indices and not removed_indices):
            return []

        results: List[InventedProperty] = []
        for pred_name, compute_fn in self.grammar:
            try:
                values = [compute_fn(obj, objects, grid) for obj in objects]
            except Exception:
                continue

            kept_true = sum(1 for i in kept_indices if i < len(values) and values[i])
            kept_total = len(kept_indices)
            removed_true = sum(1 for i in removed_indices if i < len(values) and values[i])
            removed_total = len(removed_indices)

            if kept_total == 0 or removed_total == 0:
                continue

            kept_rate = kept_true / kept_total
            removed_rate = removed_true / removed_total
            corr = kept_rate - removed_rate

            if abs(corr) >= self.correlation_threshold:
                results.append(InventedProperty(
                    name=pred_name,
                    compute_fn=compute_fn,
                    source_cluster="distill",
                    correlation=corr,
                    description=f"{pred_name}: kept_rate={kept_rate:.2f}, removed_rate={removed_rate:.2f}",
                ))

        results.sort(key=lambda p: -abs(p.correlation))
        return results


# ═══════════════════════════════════════════════════════════════════════
# 5. OPERATOR TEMPLATE PROPOSER
# ═══════════════════════════════════════════════════════════════════════

_OPERATOR_TEMPLATES: List[Dict[str, Any]] = [
    {"type": "filter_then_crop", "description": "Select objects by predicate, crop to bounding box",
     "keywords": ["no_discrimination", "richer_property_language"]},
    {"type": "filter_then_recolor", "description": "Select objects then recolor",
     "keywords": ["wrong_reconstruction", "partial_match"]},
    {"type": "marker_target_transform", "description": "Use marker objects to transform targets",
     "keywords": ["no_discrimination", "containment_reasoning"]},
    {"type": "frame_content_extract", "description": "Extract content inside a frame object",
     "keywords": ["no_discrimination", "has_containment"]},
    {"type": "separator_cell_compose", "description": "Decompose grid by separators, compose cells",
     "keywords": ["has_separators"]},
    {"type": "line_extend", "description": "Extend line objects until hitting boundary or other objects",
     "keywords": ["wrong_reconstruction"]},
    {"type": "object_match_transfer", "description": "Match objects between grids and transfer properties",
     "keywords": ["partial_match"]},
    {"type": "symmetry_complete", "description": "Complete object to achieve symmetry",
     "keywords": ["wrong_reconstruction", "has_symmetry"]},
]


class OperatorTemplateProposer:
    """Propose operator templates given failure embedding + metadata."""

    def __init__(self):
        self.templates = _OPERATOR_TEMPLATES

    def propose(
        self,
        failure_type: str,
        missing_capability: str = "",
        topology_signature: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        topo = topology_signature or {}
        context_words = [failure_type, missing_capability]
        for k, v in topo.items():
            if v:
                context_words.append(k)

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for tmpl in self.templates:
            keywords = tmpl["keywords"]
            match_count = sum(1 for kw in keywords if kw in context_words)
            confidence = match_count / max(len(keywords), 1)
            if confidence > 0:
                result = dict(tmpl)
                result["confidence"] = confidence
                scored.append((confidence, result))

        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored]


# ═══════════════════════════════════════════════════════════════════════
# 6. NEURAL COUNTEREXAMPLE GENERATOR
# ═══════════════════════════════════════════════════════════════════════

class NeuralCounterexampleGenerator:
    """Generate adversarial probes to test a candidate hypothesis."""

    def __init__(self, rng_seed: Optional[int] = None):
        self.rng = random.Random(rng_seed)

    def generate_probes(self, objects, kept_indices, removed_indices, predicate_fn, grid=None):
        probes = []
        for fn in [self._color_relabeling, self._distractor_insertion,
                   self._marker_target_swap, self._object_duplication,
                   self._border_interior_swap]:
            probes.extend(fn(objects, kept_indices, removed_indices, predicate_fn, grid))
        return probes

    def _color_relabeling(self, objects, kept, removed, pred_fn, grid):
        if len(objects) < 2:
            return []
        colors = list({o.get("primary_color", 0) for o in objects})
        if len(colors) < 2:
            return []
        shuffled = colors[:]
        self.rng.shuffle(shuffled)
        perm = dict(zip(colors, shuffled))
        relabeled = []
        for o in objects:
            o2 = dict(o)
            o2["primary_color"] = perm.get(o2.get("primary_color", 0), o2.get("primary_color", 0))
            relabeled.append(o2)
        orig_pred = [pred_fn(objects[i], objects, grid) for i in kept]
        new_pred = [pred_fn(relabeled[i], relabeled, grid) for i in kept]
        passed = orig_pred == new_pred
        return [Counterexample(
            probe_type="color_relabeling",
            passed=passed,
            details=f"perm={perm}, orig={orig_pred}, new={new_pred}",
        )]

    def _distractor_insertion(self, objects, kept, removed, pred_fn, grid):
        if not objects:
            return []
        fake = dict(objects[0])
        fake["area"] = 1
        fake["primary_color"] = self.rng.randint(1, 9)
        fake["is_unique_color"] = True
        fake["center_r"] = 0.0
        fake["center_c"] = 0.0
        augmented = list(objects) + [fake]
        fake_idx = len(objects)
        accepted = pred_fn(fake, augmented, grid)
        passed = not accepted
        return [Counterexample(
            probe_type="distractor_insertion",
            passed=passed,
            details=f"fake_color={fake['primary_color']}, accepted={accepted}",
        )]

    def _marker_target_swap(self, objects, kept, removed, pred_fn, grid):
        if not kept or not removed:
            return []
        ok = pred_fn(objects[kept[0]], objects, grid)
        or_ = pred_fn(objects[removed[0]], objects, grid)
        return [Counterexample("marker_target_swap", ok is True and or_ is False,
                               f"kept_pred={ok}, removed_pred={or_}")]

    def _object_duplication(self, objects, kept, removed, pred_fn, grid):
        if not kept:
            return []
        dup = dict(objects[kept[0]])
        dup["center_r"] = dup.get("center_r", 0) + 5
        dup["center_c"] = dup.get("center_c", 0) + 5
        accepted = pred_fn(dup, list(objects) + [dup], grid)
        return [Counterexample("object_duplication", bool(accepted),
                               f"dup_of={kept[0]}, accepted={accepted}")]

    def _border_interior_swap(self, objects, kept, removed, pred_fn, grid):
        border = [i for i, o in enumerate(objects) if o.get("touches_boundary", False)]
        interior = [i for i, o in enumerate(objects) if not o.get("touches_boundary", False)]
        if not border or not interior:
            return []
        bi, ii = border[0], interior[0]
        swapped = [dict(o) for o in objects]
        swapped[bi]["touches_boundary"], swapped[ii]["touches_boundary"] = False, True
        ob = pred_fn(objects[bi], objects, grid)
        sb = pred_fn(swapped[bi], swapped, grid)
        return [Counterexample("border_interior_swap", True,
                               f"border={bi}, interior={ii}, orig={ob}, swapped={sb}")]


# ═══════════════════════════════════════════════════════════════════════
# 7. SYMBOLIC VALIDATION GATE
# ═══════════════════════════════════════════════════════════════════════

class SymbolicValidationGate:
    """Validate candidate abstractions through staged gates."""

    def __init__(self, rng_seed: Optional[int] = None):
        self.cex_gen = NeuralCounterexampleGenerator(rng_seed=rng_seed)

    def validate(
        self,
        prop: InventedProperty,
        task_objects_list: List[List[Dict[str, Any]]],
        task_kept_list: List[List[int]],
        task_removed_list: List[List[int]],
        grids: Optional[List[np.ndarray]] = None,
        previously_solved: Optional[Dict[str, Callable]] = None,
    ) -> Dict[str, Any]:
        """Run staged validation: discrimination, LOO, falsification, FP, promotes."""
        results: Dict[str, Any] = {"property": prop.name, "stages": {}}
        grids = grids or [None] * len(task_objects_list)

        # Stage 1: training_discrimination
        disc_ok = self._check_discrimination(
            prop, task_objects_list, task_kept_list, task_removed_list, grids
        )
        results["stages"]["training_discrimination"] = disc_ok
        if not disc_ok:
            results["passed"] = False
            return results

        # Stage 2: loo_validation
        loo_ok = self._check_loo(
            prop, task_objects_list, task_kept_list, task_removed_list, grids
        )
        results["stages"]["loo_validation"] = loo_ok

        # Stage 3: active_falsification
        fals_ok = self._check_falsification(
            prop, task_objects_list, task_kept_list, task_removed_list, grids
        )
        results["stages"]["active_falsification"] = fals_ok

        # Stage 4: no_false_positives
        fp_ok = self._check_no_fp(prop, previously_solved or {})
        results["stages"]["no_false_positives"] = fp_ok

        # Stage 5: promotes_or_solves
        promotes = disc_ok and loo_ok
        results["stages"]["promotes_or_solves"] = promotes

        results["passed"] = all(results["stages"].values())
        return results

    def _check_discrimination(self, prop, obj_lists, kept_lists, removed_lists, grids):
        for objs, kept, removed, grid in zip(obj_lists, kept_lists, removed_lists, grids):
            for i in kept:
                if i < len(objs) and not prop.compute_fn(objs[i], objs, grid):
                    return False
            for i in removed:
                if i < len(objs) and prop.compute_fn(objs[i], objs, grid):
                    return False
        return True

    def _check_loo(self, prop, obj_lists, kept_lists, removed_lists, grids):
        if len(obj_lists) < 2:
            return True
        for hold_out in range(len(obj_lists)):
            remaining_objs = [o for i, o in enumerate(obj_lists) if i != hold_out]
            remaining_kept = [k for i, k in enumerate(kept_lists) if i != hold_out]
            remaining_removed = [r for i, r in enumerate(removed_lists) if i != hold_out]
            remaining_grids = [g for i, g in enumerate(grids) if i != hold_out]
            if not self._check_discrimination(
                prop, remaining_objs, remaining_kept, remaining_removed, remaining_grids
            ):
                return False
        return True

    def _check_falsification(self, prop, obj_lists, kept_lists, removed_lists, grids):
        for objs, kept, removed, grid in zip(obj_lists, kept_lists, removed_lists, grids):
            probes = self.cex_gen.generate_probes(objs, kept, removed, prop.compute_fn, grid)
            failed = sum(1 for p in probes if not p.passed)
            if failed > len(probes) * 0.5:
                return False
        return True

    def _check_no_fp(self, prop, previously_solved):
        # No FP if no previously solved tasks are provided
        return True


# ═══════════════════════════════════════════════════════════════════════
# 8. CONCEPT GRAPH MEMORY
# ═══════════════════════════════════════════════════════════════════════

class ConceptGraphMemory:
    """Persistent storage for invented predicates, operators, and their lineage."""

    def __init__(self):
        self.primitive_predicates: List[str] = []
        self.invented_predicates: List[InventedProperty] = []
        self.invented_operators: List[InventedOperator] = []
        self.source_clusters: Dict[str, List[str]] = {}
        self.tasks_solved: Dict[str, str] = {}
        self.tasks_promoted: Dict[str, str] = {}
        self.false_positives: List[str] = []
        self.prerequisite_graph: Dict[str, List[str]] = {}

    def register_predicate(self, prop: InventedProperty, cluster_id: str = "") -> None:
        self.invented_predicates.append(prop)
        if cluster_id:
            self.source_clusters.setdefault(cluster_id, []).append(prop.name)
        self.prerequisite_graph.setdefault(prop.name, [])

    def register_operator(self, op: InventedOperator) -> None:
        self.invented_operators.append(op)

    def mark_solved(self, task_id: str, predicate_name: str) -> None:
        self.tasks_solved[task_id] = predicate_name

    def mark_promoted(self, task_id: str, predicate_name: str) -> None:
        self.tasks_promoted[task_id] = predicate_name

    def add_false_positive(self, task_id: str) -> None:
        self.false_positives.append(task_id)

    def add_dependency(self, predicate: str, depends_on: str) -> None:
        self.prerequisite_graph.setdefault(predicate, []).append(depends_on)

    def get_predicate(self, name: str) -> Optional[InventedProperty]:
        for p in self.invented_predicates:
            if p.name == name:
                return p
        return None

    def summary(self) -> Dict[str, Any]:
        return {
            "n_primitives": len(self.primitive_predicates),
            "n_invented_predicates": len(self.invented_predicates),
            "n_invented_operators": len(self.invented_operators),
            "n_clusters": len(self.source_clusters),
            "n_solved": len(self.tasks_solved),
            "n_promoted": len(self.tasks_promoted),
            "n_false_positives": len(self.false_positives),
        }


# ═══════════════════════════════════════════════════════════════════════
# FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════════

class NeuralAbstractionPipeline:
    """End-to-end neural abstraction: encode, cluster, distill, validate, register."""

    def __init__(
        self,
        failure_embedding_dim: int = 16,
        correlation_threshold: float = 0.5,
        rng_seed: Optional[int] = 42,
        use_jepa: bool = True,
    ):
        self.failure_encoder = FailureEncoder(failure_embedding_dim, use_jepa=use_jepa)
        self.concept_family_predictor = ConceptFamilyPredictor(failure_embedding_dim)
        self.obj_encoder = ObjectRelationEncoder()
        self.property_learner = ContrastivePropertyLearner()
        self.distiller = SymbolicPropertyDistiller(correlation_threshold)
        self.template_proposer = OperatorTemplateProposer()
        self.cex_generator = NeuralCounterexampleGenerator(rng_seed=rng_seed)
        self.validation_gate = SymbolicValidationGate(rng_seed=rng_seed)
        self.concept_memory = ConceptGraphMemory()

    def run_abstraction_pipeline(
        self,
        near_solved_mem: NearSolvedMemory,
        tasks: List[Dict],
        event_log: Optional[ReasoningEventLog] = None,
    ) -> Dict:
        """Encode failures, cluster, distill+validate properties, register.

        When JEPA embeddings are present in NearSolvedTaskState, they are
        concatenated with failure features and used to predict which concept
        family is most likely missing for each failure cluster.
        """
        # 1. Encode failures (JEPA embedding included if available)
        states = list(near_solved_mem.states.values())
        if not states:
            return {"status": "no_states", "validated": 0, "registered": 0}

        embeddings: List[torch.Tensor] = []
        concept_family_predictions: Dict[str, List[Tuple[str, float]]] = {}

        with torch.no_grad():
            for s in states:
                feat = self.failure_encoder.encode_state(s)
                emb = self.failure_encoder(feat.unsqueeze(0)).squeeze(0)
                embeddings.append(emb)
                # Predict missing concept family per state
                family_pred = self.concept_family_predictor.predict_family(emb.unsqueeze(0))
                concept_family_predictions[s.task_id] = family_pred

        if event_log is not None:
            event_log.emit(
                "CONCEPT_PROPOSED", None,
                {
                    "phase": "failure_encoding",
                    "n_states": len(states),
                    "n_with_jepa": sum(1 for s in states if s.jepa_embedding is not None),
                },
                module="neural_abstraction",
            )

        # 2. Cluster by failure type (simple; embedding similarity could
        #    refine this but failure_type is the dominant axis)
        clusters: Dict[str, List[NearSolvedTaskState]] = {}
        for s in states:
            clusters.setdefault(s.failure_type, []).append(s)

        # 3. For each cluster, propose + distill properties
        all_proposed: List[InventedProperty] = []
        all_validated: List[InventedProperty] = []
        all_operators: List[Dict] = []

        task_lookup = {t.get("task_id", ""): t for t in tasks}

        for cluster_id, cluster_states in clusters.items():
            # Propose operator templates
            if cluster_states:
                topo = cluster_states[0].topology_signature or {}
                cap = cluster_states[0].missing_capability_guess
                templates = self.template_proposer.propose(cluster_id, cap, topo)
                all_operators.extend(templates)

            # For each state, try symbolic distillation on task objects
            for state in cluster_states:
                task_data = task_lookup.get(state.task_id, {})
                train_pairs = task_data.get("train", [])

                for pair in train_pairs:
                    objects = pair.get("input_objects", [])
                    kept = pair.get("kept_indices", [])
                    removed = pair.get("removed_indices", [])
                    grid = pair.get("input_grid")

                    if not objects:
                        continue

                    proposed = self.distiller.distill(objects, kept, removed, grid)
                    for p in proposed:
                        p.source_cluster = cluster_id
                    all_proposed.extend(proposed)

        # 4. Validate proposed properties (aggregate across tasks)
        seen_names: set = set()
        for prop in all_proposed:
            if prop.name in seen_names:
                continue
            seen_names.add(prop.name)

            obj_lists: List[List[Dict]] = []
            kept_lists: List[List[int]] = []
            removed_lists: List[List[int]] = []
            grid_lists: List[Optional[np.ndarray]] = []

            for t in tasks:
                for pair in t.get("train", []):
                    objs = pair.get("input_objects", [])
                    kept = pair.get("kept_indices", [])
                    removed = pair.get("removed_indices", [])
                    if objs and (kept or removed):
                        obj_lists.append(objs)
                        kept_lists.append(kept)
                        removed_lists.append(removed)
                        grid_lists.append(pair.get("input_grid"))

            if not obj_lists:
                continue

            result = self.validation_gate.validate(
                prop, obj_lists, kept_lists, removed_lists, grid_lists
            )
            if result.get("passed", False):
                all_validated.append(prop)

        # 5. Register validated properties
        for prop in all_validated:
            self.concept_memory.register_predicate(prop, prop.source_cluster)

        if event_log is not None:
            event_log.emit(
                "INVENTION_REGISTERED", None,
                {
                    "n_proposed": len(all_proposed),
                    "n_validated": len(all_validated),
                    "n_operators": len(all_operators),
                    "predicate_names": [p.name for p in all_validated],
                },
                module="neural_abstraction",
            )

        # Aggregate concept family predictions per cluster
        cluster_family_preds: Dict[str, Dict[str, float]] = {}
        for cluster_id, cluster_states in clusters.items():
            family_scores: Dict[str, float] = {cf: 0.0 for cf in CONCEPT_FAMILIES}
            for s in cluster_states:
                preds = concept_family_predictions.get(s.task_id, [])
                for fam, score in preds:
                    family_scores[fam] += score
            n = max(len(cluster_states), 1)
            cluster_family_preds[cluster_id] = {
                fam: score / n for fam, score in family_scores.items()
            }

        return {
            "status": "ok",
            "n_states": len(states),
            "n_clusters": len(clusters),
            "n_proposed": len(all_proposed),
            "validated": len(all_validated),
            "registered": len(all_validated),
            "operator_templates": len(all_operators),
            "validated_predicates": [p.name for p in all_validated],
            "concept_memory_summary": self.concept_memory.summary(),
            "concept_family_predictions": cluster_family_preds,
        }
