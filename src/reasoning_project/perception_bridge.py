"""Neural Perception Bridge — connects learned representations to symbolic reasoning.

Four components that give the adaptive reasoning loop spatial understanding:

1. JEPAPerceptionGuide   — predicts task layout from JEPA embeddings → guides view selection
2. SpatialRelationLearner — discovers which spatial relations are transformation-relevant
3. SlotPerceptionAdapter  — converts Slot Attention slots into DomainAdapter objects
4. WorldModelSimulator    — forward-simulates hypotheses for scoring

All components degrade gracefully: without a trained checkpoint, they fall back
to the existing rule-based approach. No GPU required at inference if checkpoints
are pre-computed.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from scipy import ndimage

from reasoning_project.reasoning_engine import (
    DomainAdapter,
    GridDomainAdapter,
    _add_relational_properties,
    _classify_kept_removed,
    _match_objects_hungarian,
)

try:
    from reasoning_project.neural.grid_encoder import torch_available
    if torch_available():
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        HAS_TORCH = True
    else:
        HAS_TORCH = False
except ImportError:
    HAS_TORCH = False


# ═══════════════════════════════════════════════════════════════════════════
# 1. JEPA PERCEPTION GUIDE
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TaskPerception:
    """What JEPA predicts about a task's spatial structure."""
    estimated_object_count: float = 0.0
    layout_type: str = "unknown"  # "scattered", "grid_of_cells", "nested", "linear", "single_object"
    bg_is_zero: float = 1.0  # probability that background is color 0
    has_separators: float = 0.0  # probability of separator lines
    has_containment: float = 0.0  # probability of nested objects
    confidence: float = 0.0
    embedding: Optional[np.ndarray] = None


class JEPAPerceptionGuide:
    """Uses JEPA latent representations to predict task spatial structure.

    When a JEPA checkpoint is available, encodes the task and runs small
    prediction heads (object count, layout type, bg detection).

    Without a checkpoint, falls back to rule-based analysis that inspects
    the raw grid structure.
    """

    def __init__(self, jepa_checkpoint: Optional[str] = None, device: str = "cpu"):
        self.device = device
        self.jepa = None
        self.perception_heads = None

        if jepa_checkpoint and HAS_TORCH:
            self._load_checkpoint(jepa_checkpoint)

    def _load_checkpoint(self, path: str) -> None:
        try:
            from reasoning_project.neural.grid_jepa import load_grid_jepa_checkpoint
            self.jepa = load_grid_jepa_checkpoint(path, device=self.device)
            self.jepa.eval()

            ckpt = torch.load(path, map_location=self.device, weights_only=False)
            if "perception_heads" in ckpt:
                hidden = self.jepa.hidden_dim
                self.perception_heads = PerceptionHeads(hidden * 4)
                self.perception_heads.load_state_dict(ckpt["perception_heads"])
                self.perception_heads.to(self.device)
                self.perception_heads.eval()
        except Exception:
            self.jepa = None

    def analyze(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> TaskPerception:
        """Analyze a task's spatial structure, using JEPA if available."""
        if self.jepa is not None and self.perception_heads is not None:
            return self._neural_analyze(train_pairs)
        return self._rule_based_analyze(train_pairs)

    def _neural_analyze(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> TaskPerception:
        """JEPA-based spatial analysis."""
        task_embedding = self.jepa.encode_task_context(train_pairs, device=self.device)
        emb_tensor = torch.tensor(task_embedding, dtype=torch.float32, device=self.device).unsqueeze(0)

        with torch.no_grad():
            preds = self.perception_heads(emb_tensor)

        obj_count = float(preds["object_count"][0].item())
        layout_probs = F.softmax(preds["layout_logits"][0], dim=0).cpu().numpy()
        layout_names = ["scattered", "grid_of_cells", "nested", "linear", "single_object"]
        layout_type = layout_names[int(np.argmax(layout_probs))]
        bg_is_zero = float(torch.sigmoid(preds["bg_is_zero"][0]).item())
        has_sep = float(torch.sigmoid(preds["has_separators"][0]).item())
        has_cont = float(torch.sigmoid(preds["has_containment"][0]).item())
        confidence = float(np.max(layout_probs))

        return TaskPerception(
            estimated_object_count=max(0, obj_count),
            layout_type=layout_type,
            bg_is_zero=bg_is_zero,
            has_separators=has_sep,
            has_containment=has_cont,
            confidence=confidence,
            embedding=task_embedding,
        )

    def _rule_based_analyze(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> TaskPerception:
        """Fallback: analyze task structure from raw grid statistics."""
        obj_counts = []
        bg_zero_votes = 0
        sep_votes = 0
        containment_votes = 0
        total = len(train_pairs)

        for inp, out in train_pairs:
            vals, counts = np.unique(inp, return_counts=True)
            bg = int(vals[np.argmax(counts)])
            if bg == 0:
                bg_zero_votes += 1

            mask = inp != bg
            labeled, n = ndimage.label(mask)
            obj_counts.append(n)

            if _detect_separators(inp, bg):
                sep_votes += 1

            if _detect_containment(inp, bg):
                containment_votes += 1

        mean_objects = float(np.mean(obj_counts)) if obj_counts else 0

        if sep_votes > total / 2:
            layout = "grid_of_cells"
        elif containment_votes > total / 2:
            layout = "nested"
        elif mean_objects <= 1.5:
            layout = "single_object"
        elif mean_objects > 6:
            layout = "scattered"
        else:
            layout = "scattered"

        return TaskPerception(
            estimated_object_count=mean_objects,
            layout_type=layout,
            bg_is_zero=bg_zero_votes / max(total, 1),
            has_separators=sep_votes / max(total, 1),
            has_containment=containment_votes / max(total, 1),
            confidence=0.5,
        )

    def suggest_views(self, perception: TaskPerception) -> List[str]:
        """Suggest perception view order based on task analysis."""
        views = []

        if perception.bg_is_zero < 0.5:
            views.append("majority_bg")

        if perception.layout_type == "grid_of_cells":
            views.append("color_cc")
            views.append("per_color")
        elif perception.layout_type == "nested":
            views.append("color_cc")
            views.append("per_color")
        elif perception.layout_type == "single_object":
            views.append("per_color")
            views.append("color_cc")
        elif perception.layout_type == "scattered":
            views.append("color_cc")
            if perception.estimated_object_count < 3:
                views.append("per_color")

        if "slot" not in views:
            views.append("slot")

        for v in ["color_cc", "per_color", "monochrome", "majority_bg"]:
            if v not in views:
                views.append(v)

        return views


def _detect_separators(grid: np.ndarray, bg: int) -> bool:
    """Detect if grid has separator lines (full rows/cols of one color)."""
    h, w = grid.shape
    for r in range(1, h - 1):
        row = grid[r, :]
        vals = set(row.tolist())
        if len(vals) == 1 and vals != {bg}:
            return True
    for c in range(1, w - 1):
        col = grid[:, c]
        vals = set(col.tolist())
        if len(vals) == 1 and vals != {bg}:
            return True
    return False


def _detect_containment(grid: np.ndarray, bg: int) -> bool:
    """Detect if any object's bounding box fully contains another."""
    mask = grid != bg
    labeled, n = ndimage.label(mask)
    if n < 2:
        return False
    bboxes = []
    for lab in range(1, n + 1):
        rows, cols = np.where(labeled == lab)
        if len(rows) == 0:
            continue
        bboxes.append((int(rows.min()), int(cols.min()), int(rows.max()), int(cols.max())))
    for i in range(len(bboxes)):
        for j in range(len(bboxes)):
            if i == j:
                continue
            r1, c1, r2, c2 = bboxes[i]
            jr1, jc1, jr2, jc2 = bboxes[j]
            if jr1 <= r1 and jc1 <= c1 and jr2 >= r2 and jc2 >= c2:
                return True
    return False


# ═══════════════════════════════════════════════════════════════════════════
# PERCEPTION HEADS (trained on top of JEPA)
# ═══════════════════════════════════════════════════════════════════════════

if HAS_TORCH:
    class PerceptionHeads(nn.Module):
        """Small heads trained on JEPA task embeddings to predict spatial structure."""

        def __init__(self, input_dim: int = 256):
            super().__init__()
            self.shared = nn.Sequential(
                nn.Linear(input_dim, 128),
                nn.ReLU(),
                nn.Linear(128, 64),
                nn.ReLU(),
            )
            self.object_count_head = nn.Linear(64, 1)
            self.layout_head = nn.Linear(64, 5)  # 5 layout types
            self.bg_head = nn.Linear(64, 1)
            self.separator_head = nn.Linear(64, 1)
            self.containment_head = nn.Linear(64, 1)

        def forward(self, task_embedding: "torch.Tensor") -> Dict[str, "torch.Tensor"]:
            h = self.shared(task_embedding)
            return {
                "object_count": self.object_count_head(h),
                "layout_logits": self.layout_head(h),
                "bg_is_zero": self.bg_head(h),
                "has_separators": self.separator_head(h),
                "has_containment": self.containment_head(h),
            }
else:
    PerceptionHeads = None  # type: ignore[assignment,misc]


# ═══════════════════════════════════════════════════════════════════════════
# 2. SPATIAL RELATION LEARNER
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SpatialRelation:
    """A spatial relation between two objects."""
    name: str
    obj_a_idx: int
    obj_b_idx: int
    value: float


class SpatialRelationLearner:
    """Discovers which spatial relations are transformation-relevant.

    For each training pair, computes pairwise spatial relations between objects.
    Then identifies which relations are preserved vs changed across pairs.
    This tells the StructuralReasoner which relations matter for this task.
    """

    RELATION_FUNCTIONS = {
        "distance": lambda a, b: np.sqrt(
            (a["center_r"] - b["center_r"])**2 + (a["center_c"] - b["center_c"])**2
        ),
        "relative_size": lambda a, b: a["area"] / max(b["area"], 1),
        "same_color": lambda a, b: float(a["primary_color"] == b["primary_color"]),
        "same_shape": lambda a, b: float(
            a.get("shape_group_id", -1) == b.get("shape_group_id", -2)
        ),
        "horizontally_aligned": lambda a, b: float(
            abs(a["center_r"] - b["center_r"]) < 1.5
        ),
        "vertically_aligned": lambda a, b: float(
            abs(a["center_c"] - b["center_c"]) < 1.5
        ),
        "touching": lambda a, b: float(_objects_adjacent(a, b)),
        "a_contains_b": lambda a, b: float(_bbox_contains(a, b)),
        "a_left_of_b": lambda a, b: float(a["center_c"] < b["center_c"]),
        "a_above_b": lambda a, b: float(a["center_r"] < b["center_r"]),
        "size_ratio": lambda a, b: a["area"] / max(a["area"] + b["area"], 1),
        "diagonal_aligned": lambda a, b: float(
            abs(abs(a["center_r"] - b["center_r"]) -
                abs(a["center_c"] - b["center_c"])) < 1.5
        ),
    }

    def discover_relevant_relations(
        self,
        adapter: DomainAdapter,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> Dict[str, Any]:
        """Find which spatial relations are preserved/changed across pairs."""
        preserved = []
        changed = []

        for rel_name, rel_fn in self.RELATION_FUNCTIONS.items():
            pair_values = []
            for inp, out in train_pairs:
                in_objs = adapter.extract_objects(inp)
                out_objs = adapter.extract_objects(out)
                if len(in_objs) < 2 or len(out_objs) < 2:
                    continue

                in_rels = self._compute_pairwise(in_objs, rel_fn)
                out_rels = self._compute_pairwise(out_objs, rel_fn)
                pair_values.append((in_rels, out_rels))

            if not pair_values:
                continue

            is_preserved = self._check_preservation(pair_values)
            if is_preserved:
                preserved.append(rel_name)
            else:
                changed.append(rel_name)

        return {
            "preserved": preserved,
            "changed": changed,
            "n_pairs_analyzed": len(train_pairs),
        }

    def rank_discriminative_relations(
        self,
        adapter: DomainAdapter,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[Tuple[str, float]]:
        """Rank relations by how well they discriminate kept vs removed objects."""
        scores = []
        for rel_name, rel_fn in self.RELATION_FUNCTIONS.items():
            disc_score = 0.0
            n_classifiable = 0
            for inp, out in train_pairs:
                objects = adapter.extract_objects(inp)
                cls = adapter.classify_kept_removed(objects, inp, out)
                if cls is None or len(objects) < 2:
                    continue
                n_classifiable += 1
                kept, removed = cls

                kept_rel_vals = []
                removed_rel_vals = []
                for ki in kept:
                    for j in range(len(objects)):
                        if j != ki:
                            kept_rel_vals.append(rel_fn(objects[ki], objects[j]))
                for ri in removed:
                    for j in range(len(objects)):
                        if j != ri:
                            removed_rel_vals.append(rel_fn(objects[ri], objects[j]))

                if kept_rel_vals and removed_rel_vals:
                    kept_mean = np.mean(kept_rel_vals)
                    removed_mean = np.mean(removed_rel_vals)
                    disc_score += abs(kept_mean - removed_mean)

            if n_classifiable > 0:
                scores.append((rel_name, disc_score / n_classifiable))

        scores.sort(key=lambda x: -x[1])
        return scores

    @staticmethod
    def _compute_pairwise(objects: List[Dict], rel_fn) -> List[float]:
        vals = []
        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                try:
                    vals.append(rel_fn(objects[i], objects[j]))
                except (KeyError, ZeroDivisionError):
                    pass
        return vals

    @staticmethod
    def _check_preservation(pair_values: List[Tuple[List[float], List[float]]]) -> bool:
        for in_rels, out_rels in pair_values:
            if len(in_rels) != len(out_rels):
                return False
            if not in_rels:
                continue
            in_sorted = sorted(in_rels)
            out_sorted = sorted(out_rels)
            if not np.allclose(in_sorted, out_sorted, atol=0.1):
                return False
        return True


def _objects_adjacent(a: Dict, b: Dict) -> bool:
    """Check if two objects' masks are adjacent (4-connected)."""
    if "mask" not in a or "mask" not in b:
        return False
    dilated = ndimage.binary_dilation(a["mask"])
    return bool(np.any(dilated & b["mask"]))


def _bbox_contains(a: Dict, b: Dict) -> bool:
    """Check if a's bounding box fully contains b."""
    ar1, ac1, ar2, ac2 = a["bbox"]
    br1, bc1, br2, bc2 = b["bbox"]
    return ar1 <= br1 and ac1 <= bc1 and ar2 >= br2 and ac2 >= bc2


# ═══════════════════════════════════════════════════════════════════════════
# 3. SLOT PERCEPTION ADAPTER
# ═══════════════════════════════════════════════════════════════════════════

class SlotPerceptionAdapter(DomainAdapter):
    """DomainAdapter that uses Slot Attention for object discovery.

    Instead of connected components, uses learned slot attention to decompose
    grids into objects. Each slot becomes an object with properties computed
    from its spatial mask and attention weights.

    Falls back to GridDomainAdapter if no slot model is loaded.
    """

    def __init__(
        self,
        slot_model=None,
        device: str = "cpu",
        mask_threshold: float = 0.1,
    ):
        self.slot_model = slot_model
        self.device = device
        self.mask_threshold = mask_threshold
        self._fallback = GridDomainAdapter()

    @classmethod
    def from_checkpoint(cls, path: str, device: str = "cpu") -> "SlotPerceptionAdapter":
        if not HAS_TORCH:
            return cls()
        try:
            from reasoning_project.neural.slot_attention import load_slot_model_checkpoint
            model = load_slot_model_checkpoint(path, device=device)
            return cls(slot_model=model, device=device)
        except Exception:
            return cls()

    @classmethod
    def from_world_model(cls, world_model, device: str = "cpu") -> "SlotPerceptionAdapter":
        """Extract the slot model from a WorldModel."""
        if not HAS_TORCH or world_model is None:
            return cls()
        try:
            slot_model = world_model.slot_model
            return cls(slot_model=slot_model, device=device)
        except AttributeError:
            return cls()

    def extract_objects(self, scene: np.ndarray) -> List[Dict[str, Any]]:
        if self.slot_model is None:
            return self._fallback.extract_objects(scene)
        return self._slot_extract(scene)

    def _slot_extract(self, scene: np.ndarray) -> List[Dict[str, Any]]:
        """Extract objects using Slot Attention."""
        try:
            result = self.slot_model.extract_slots(scene, device=self.device)
        except Exception:
            return self._fallback.extract_objects(scene)

        slot_masks = result["slot_masks"]  # (K, H, W)
        K, H, W = slot_masks.shape
        objects = []
        label_counter = 0

        for k in range(K):
            mask = slot_masks[k] > self.mask_threshold
            if not np.any(mask):
                continue

            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue

            label_counter += 1
            r_min, r_max = int(rows.min()), int(rows.max())
            c_min, c_max = int(cols.min()), int(cols.max())
            bbox_h = r_max - r_min + 1
            bbox_w = c_max - c_min + 1
            local_mask = mask[r_min:r_max + 1, c_min:c_max + 1]
            area = int(mask.sum())

            colors_in_mask = scene[mask]
            color_vals = sorted(set(colors_in_mask.tolist()) - {0})
            primary_color = int(colors_in_mask.flat[0]) if len(colors_in_mask) > 0 else 0

            convexity = area / max(bbox_h * bbox_w, 1)
            shape_bin = local_mask.astype(int)
            h_sym = bool(np.array_equal(shape_bin, shape_bin[::-1, :]))
            v_sym = bool(np.array_equal(shape_bin, shape_bin[:, ::-1]))
            d_sym = bool(np.array_equal(shape_bin, shape_bin.T)) if bbox_h == bbox_w else False

            touches_top = r_min == 0
            touches_bottom = r_max == H - 1
            touches_left = c_min == 0
            touches_right = c_max == W - 1

            bg_labeled, n_bg = ndimage.label(~local_mask)
            border_labels = set()
            border_labels.update(bg_labeled[0, :].tolist())
            border_labels.update(bg_labeled[-1, :].tolist())
            border_labels.update(bg_labeled[:, 0].tolist())
            border_labels.update(bg_labeled[:, -1].tolist())
            border_labels.discard(0)
            n_holes = sum(1 for lb in range(1, n_bg + 1) if lb not in border_labels)

            perimeter = 0
            for r in range(bbox_h):
                for c in range(bbox_w):
                    if local_mask[r, c]:
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nr, nc = r + dr, c + dc
                            if nr < 0 or nr >= bbox_h or nc < 0 or nc >= bbox_w or not local_mask[nr, nc]:
                                perimeter += 1

            slot_embedding = result["slots"][k] if "slots" in result else None

            objects.append({
                "label": label_counter,
                "mask": mask,
                "local_mask": local_mask,
                "bbox": (r_min, c_min, r_max, c_max),
                "center_r": float(rows.mean()),
                "center_c": float(cols.mean()),
                "area": area,
                "bbox_h": bbox_h,
                "bbox_w": bbox_w,
                "primary_color": primary_color,
                "colors": color_vals if color_vals else [primary_color],
                "n_colors": max(len(color_vals), 1),
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
                "touches_boundary": touches_top or touches_bottom or touches_left or touches_right,
                "touches_top": touches_top,
                "touches_bottom": touches_bottom,
                "touches_left": touches_left,
                "touches_right": touches_right,
                "bbox_ratio": bbox_h / max(bbox_w, 1),
                "slot_confidence": float(slot_masks[k].max()),
                "slot_embedding": slot_embedding,
            })

        _add_relational_properties(objects, scene, H, W)
        return objects

    def property_names(self) -> List[str]:
        from reasoning_project.reasoning_engine import _all_property_names
        return _all_property_names()

    def get_property(self, obj: Dict, prop: str) -> bool:
        from reasoning_project.reasoning_engine import _get_property_value
        return _get_property_value(obj, prop)

    def classify_kept_removed(self, objects, inp, out):
        return _classify_kept_removed(objects, inp, out)

    def reconstruct_filtered(self, inp, objects, keep_mask):
        result = inp.copy()
        for obj, keep in zip(objects, keep_mask):
            if not keep:
                result[obj["mask"]] = 0
        return result

    def reconstruct_recolored(self, inp, objects, label_map):
        result = inp.copy()
        for i, obj in enumerate(objects):
            if i in label_map:
                result[obj["mask"]] = label_map[i]
        return result

    def reconstruct_extracted(self, inp, objects, keep_mask):
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
        crop_mask = combined[r_min:r_max + 1, c_min:c_max + 1]
        cropped[crop_mask] = inp[r_min:r_max + 1, c_min:c_max + 1][crop_mask]
        return cropped

    def scenes_equal(self, a, b):
        return np.array_equal(a, b)

    def same_structure(self, a, b):
        return a.shape == b.shape

    def match_objects(self, in_objs, out_objs):
        return _match_objects_hungarian(in_objs, out_objs)


# ═══════════════════════════════════════════════════════════════════════════
# 4. WORLD MODEL SIMULATOR
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SimulationResult:
    """Result of simulating a hypothesis via the world model."""
    hypothesis: Dict[str, Any]
    predicted_output: Optional[np.ndarray]
    agreement_score: float  # pixel-level agreement with actual output
    confidence: float  # world model's own confidence
    pixel_accuracy: float


class WorldModelSimulator:
    """Forward-simulate hypotheses using the world model.

    Instead of just reranking candidates, actively tests hypotheses:
    1. Takes a hypothesis (e.g., "keep largest object")
    2. Applies it to get a candidate output
    3. Asks the world model: "given this input + training context,
       how likely is this output?"
    4. Also generates the world model's own prediction and compares

    This gives two independent scores for each hypothesis.
    """

    def __init__(self, world_model=None, device: str = "cpu"):
        self.world_model = world_model
        self.device = device

    @classmethod
    def from_checkpoint(cls, path: str, device: str = "cpu") -> "WorldModelSimulator":
        if not HAS_TORCH:
            return cls()
        try:
            from reasoning_project.neural.graph_network import WorldModel
            ckpt = torch.load(path, map_location=device, weights_only=False)
            config = ckpt.get("model_config", {})
            model = WorldModel(**config)
            model.load_state_dict(ckpt["model_state"])
            model.eval()
            model.to(device)
            return cls(world_model=model, device=device)
        except Exception:
            return cls()

    def simulate_hypothesis(
        self,
        hypothesis_output: np.ndarray,
        input_grid: np.ndarray,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis_meta: Optional[Dict[str, Any]] = None,
    ) -> SimulationResult:
        """Score a hypothesis output using the world model."""
        if self.world_model is None:
            return SimulationResult(
                hypothesis=hypothesis_meta or {},
                predicted_output=None,
                agreement_score=0.5,
                confidence=0.0,
                pixel_accuracy=0.0,
            )

        try:
            wm_score = self.world_model.score_candidate(
                input_grid, hypothesis_output, self.device,
                train_pairs=train_pairs,
            )

            H_out, W_out = hypothesis_output.shape
            wm_prediction = self.world_model.predict(
                input_grid, (H_out, W_out), self.device,
                train_pairs=train_pairs,
            )

            pixel_acc = float(np.mean(wm_prediction == hypothesis_output))

            return SimulationResult(
                hypothesis=hypothesis_meta or {},
                predicted_output=wm_prediction,
                agreement_score=float(wm_score),
                confidence=float(wm_score),
                pixel_accuracy=pixel_acc,
            )
        except Exception:
            return SimulationResult(
                hypothesis=hypothesis_meta or {},
                predicted_output=None,
                agreement_score=0.5,
                confidence=0.0,
                pixel_accuracy=0.0,
            )

    def rank_hypotheses(
        self,
        candidates: List[Tuple[np.ndarray, Dict[str, Any]]],
        input_grid: np.ndarray,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[SimulationResult]:
        """Score and rank multiple hypothesis outputs."""
        results = []
        for output, meta in candidates:
            result = self.simulate_hypothesis(output, input_grid, train_pairs, meta)
            results.append(result)
        results.sort(key=lambda r: -r.agreement_score)
        return results


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATED PERCEPTION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

class NeuralPerceptionPipeline:
    """Orchestrates all 4 neural perception components.

    Integrates into AdaptiveReasoningLoop by:
    1. JEPA guide suggests initial view order
    2. Slot adapter provides a learned-perception view
    3. Spatial relation learner identifies relevant relations
    4. World model simulator scores hypothesis candidates

    All components are optional — the pipeline works with any subset.
    """

    def __init__(
        self,
        jepa_guide: Optional[JEPAPerceptionGuide] = None,
        slot_adapter: Optional[SlotPerceptionAdapter] = None,
        relation_learner: Optional[SpatialRelationLearner] = None,
        world_simulator: Optional[WorldModelSimulator] = None,
    ):
        self.jepa_guide = jepa_guide or JEPAPerceptionGuide()
        self.slot_adapter = slot_adapter or SlotPerceptionAdapter()
        self.relation_learner = relation_learner or SpatialRelationLearner()
        self.world_simulator = world_simulator or WorldModelSimulator()

    @classmethod
    def from_checkpoints(
        cls,
        jepa_path: Optional[str] = None,
        slot_path: Optional[str] = None,
        world_model_path: Optional[str] = None,
        device: str = "cpu",
    ) -> "NeuralPerceptionPipeline":
        """Load all available checkpoints."""
        jepa = JEPAPerceptionGuide(jepa_path, device=device) if jepa_path else JEPAPerceptionGuide()

        slot = None
        if slot_path:
            slot = SlotPerceptionAdapter.from_checkpoint(slot_path, device=device)
        elif world_model_path and HAS_TORCH:
            try:
                from reasoning_project.neural.graph_network import WorldModel
                ckpt = torch.load(world_model_path, map_location=device, weights_only=False)
                config = ckpt.get("model_config", {})
                model = WorldModel(**config)
                model.load_state_dict(ckpt["model_state"])
                model.eval()
                slot = SlotPerceptionAdapter.from_world_model(model, device=device)
            except Exception:
                slot = SlotPerceptionAdapter()
        else:
            slot = SlotPerceptionAdapter()

        world_sim = WorldModelSimulator.from_checkpoint(world_model_path, device=device) if world_model_path else WorldModelSimulator()

        return cls(
            jepa_guide=jepa,
            slot_adapter=slot,
            relation_learner=SpatialRelationLearner(),
            world_simulator=world_sim,
        )

    def analyze_task(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> Dict[str, Any]:
        """Full neural analysis of a task."""
        perception = self.jepa_guide.analyze(train_pairs)

        adapter = GridDomainAdapter()
        relations = self.relation_learner.discover_relevant_relations(adapter, train_pairs)
        discriminative = self.relation_learner.rank_discriminative_relations(adapter, train_pairs)

        suggested_views = self.jepa_guide.suggest_views(perception)

        return {
            "perception": perception,
            "relations": relations,
            "discriminative_relations": discriminative[:5],
            "suggested_views": suggested_views,
            "has_neural_perception": self.slot_adapter.slot_model is not None,
            "has_world_model": self.world_simulator.world_model is not None,
        }

    def get_slot_adapter(self) -> SlotPerceptionAdapter:
        return self.slot_adapter

    def score_hypothesis(
        self,
        hypothesis_output: np.ndarray,
        input_grid: np.ndarray,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis_meta: Optional[Dict[str, Any]] = None,
    ) -> SimulationResult:
        return self.world_simulator.simulate_hypothesis(
            hypothesis_output, input_grid, train_pairs, hypothesis_meta,
        )
