"""Popper-style active falsification: generate targeted counterexamples to
break hypotheses before accepting them."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    _apply_filter,
    _apply_recolor,
    _extract_objects_with_properties,
    _add_relational_properties,
    _get_property_value,
)


@dataclass
class Counterexample:
    input_grid: np.ndarray
    expected_output: Optional[np.ndarray]
    violated_invariant: str
    target_hypothesis: str
    counterexample_type: str
    severity: float


@dataclass
class FalsificationResult:
    hypothesis: Dict[str, Any]
    counterexamples_generated: int
    counterexamples_survived: int
    counterexamples_failed: int
    falsification_score: float
    failed_probes: List[Counterexample] = field(default_factory=list)
    passed: bool = True


class ActiveFalsifier:
    """Generate targeted counterexamples that probe whether a hypothesis
    captures genuine structure or exploits surface-level shortcuts."""

    def __init__(
        self,
        n_color_permutations: int = 4,
        distractor_size: int = 2,
        pass_threshold: float = 0.6,
        rng_seed: Optional[int] = None,
    ) -> None:
        self.n_color_permutations = n_color_permutations
        self.distractor_size = distractor_size
        self.pass_threshold = pass_threshold
        self.rng = random.Random(rng_seed)

    def falsify(
        self,
        task_train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        adapter: GridDomainAdapter,
    ) -> FalsificationResult:
        probe_families = [
            self._probe_color_relabeling,
            self._probe_distractor_insertion,
            self._probe_object_count,
            self._probe_spatial_permutation,
            self._probe_border_interior_swap,
        ]

        all_counterexamples: List[Counterexample] = []
        for probe_fn in probe_families:
            try:
                cxs = probe_fn(task_train_pairs, hypothesis, adapter)
                all_counterexamples.extend(cxs)
            except Exception:
                pass

        generated = len(all_counterexamples)
        failed = [cx for cx in all_counterexamples if cx.severity > 0.0]
        survived = generated - len(failed)

        if generated == 0:
            score = 1.0
        else:
            score = survived / generated

        return FalsificationResult(
            hypothesis=hypothesis,
            counterexamples_generated=generated,
            counterexamples_survived=survived,
            counterexamples_failed=len(failed),
            falsification_score=score,
            failed_probes=failed,
            passed=score >= self.pass_threshold,
        )

    # ------------------------------------------------------------------
    # Probe: color relabeling
    # ------------------------------------------------------------------

    def _probe_color_relabeling(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        adapter: GridDomainAdapter,
    ) -> List[Counterexample]:
        counterexamples: List[Counterexample] = []

        for inp, out in train_pairs:
            non_bg_colors = sorted(set(inp.flatten().tolist()) - {0})
            if len(non_bg_colors) < 2:
                continue

            for _ in range(self.n_color_permutations):
                perm = non_bg_colors.copy()
                self.rng.shuffle(perm)
                if perm == non_bg_colors:
                    continue

                color_map = dict(zip(non_bg_colors, perm))
                permuted_inp = self._remap_colors(inp, color_map)
                permuted_out = self._remap_colors(out, color_map)

                pred = self._apply_hypothesis(permuted_inp, hypothesis, adapter)

                if pred is None:
                    severity = 0.5
                    violated = "hypothesis returned None on permuted input"
                elif not np.array_equal(pred, permuted_out):
                    severity = 1.0
                    violated = "output not equivariant under color permutation"
                else:
                    severity = 0.0
                    violated = ""

                counterexamples.append(Counterexample(
                    input_grid=permuted_inp,
                    expected_output=permuted_out,
                    violated_invariant=violated,
                    target_hypothesis=hypothesis.get("strategy", "unknown"),
                    counterexample_type="color_relabel",
                    severity=severity,
                ))

        return counterexamples

    # ------------------------------------------------------------------
    # Probe: distractor insertion
    # ------------------------------------------------------------------

    def _probe_distractor_insertion(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        adapter: GridDomainAdapter,
    ) -> List[Counterexample]:
        counterexamples: List[Counterexample] = []

        for inp, out in train_pairs:
            h, w = inp.shape
            if h < self.distractor_size + 1 or w < self.distractor_size + 1:
                continue

            slot = self._find_empty_slot(inp, self.distractor_size)
            if slot is None:
                continue

            r, c = slot
            distractor_color = self.rng.randint(1, 9)
            augmented = inp.copy()
            augmented[r:r + self.distractor_size, c:c + self.distractor_size] = distractor_color

            baseline = self._apply_hypothesis(inp, hypothesis, adapter)
            augmented_pred = self._apply_hypothesis(augmented, hypothesis, adapter)

            if baseline is None or augmented_pred is None:
                severity = 0.3
                violated = "hypothesis cannot handle distractor (returned None)"
            elif augmented_pred.shape != baseline.shape:
                severity = 0.8
                violated = "distractor changed output shape"
            else:
                # The distractor region itself might legitimately change the output,
                # but the non-distractor region should be preserved.
                if np.array_equal(augmented_pred, baseline):
                    severity = 0.0
                    violated = ""
                else:
                    diff_ratio = np.count_nonzero(augmented_pred != baseline) / baseline.size
                    severity = min(diff_ratio * 5.0, 1.0)
                    violated = f"distractor altered {diff_ratio:.1%} of non-distractor output"

            counterexamples.append(Counterexample(
                input_grid=augmented,
                expected_output=None,
                violated_invariant=violated,
                target_hypothesis=hypothesis.get("strategy", "unknown"),
                counterexample_type="distractor_insert",
                severity=severity,
            ))

        return counterexamples

    # ------------------------------------------------------------------
    # Probe: object count
    # ------------------------------------------------------------------

    def _probe_object_count(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        adapter: GridDomainAdapter,
    ) -> List[Counterexample]:
        counterexamples: List[Counterexample] = []

        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            if len(objects) < 1:
                continue

            src_obj = self.rng.choice(objects)
            local = src_obj["local_mask"]
            oh, ow = local.shape

            slot = self._find_empty_slot(inp, max(oh, ow))
            if slot is None:
                continue

            r, c = slot
            augmented = inp.copy()
            paste_h = min(oh, inp.shape[0] - r)
            paste_w = min(ow, inp.shape[1] - c)
            sub_mask = local[:paste_h, :paste_w]
            augmented[r:r + paste_h, c:c + paste_w][sub_mask] = src_obj["primary_color"]

            baseline = self._apply_hypothesis(inp, hypothesis, adapter)
            duped_pred = self._apply_hypothesis(augmented, hypothesis, adapter)

            if baseline is None or duped_pred is None:
                severity = 0.4
                violated = "hypothesis cannot handle duplicated object"
            elif duped_pred.shape != baseline.shape:
                severity = 0.7
                violated = "duplicated object changed output shape"
            else:
                severity = 0.0
                violated = ""

            counterexamples.append(Counterexample(
                input_grid=augmented,
                expected_output=None,
                violated_invariant=violated,
                target_hypothesis=hypothesis.get("strategy", "unknown"),
                counterexample_type="object_count",
                severity=severity,
            ))

        return counterexamples

    # ------------------------------------------------------------------
    # Probe: spatial permutation
    # ------------------------------------------------------------------

    def _probe_spatial_permutation(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        adapter: GridDomainAdapter,
    ) -> List[Counterexample]:
        counterexamples: List[Counterexample] = []

        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            if len(objects) < 2:
                continue

            idx_a, idx_b = self.rng.sample(range(len(objects)), 2)
            swapped = self._swap_objects(inp, objects[idx_a], objects[idx_b])
            if swapped is None:
                continue

            baseline = self._apply_hypothesis(inp, hypothesis, adapter)
            swapped_pred = self._apply_hypothesis(swapped, hypothesis, adapter)

            if baseline is None:
                severity = 0.0
                violated = ""
            elif swapped_pred is None:
                severity = 0.6
                violated = "hypothesis broke after spatial swap"
            elif swapped_pred.shape != baseline.shape:
                severity = 0.5
                violated = "spatial swap changed output shape"
            else:
                severity = 0.0
                violated = ""

            counterexamples.append(Counterexample(
                input_grid=swapped,
                expected_output=None,
                violated_invariant=violated,
                target_hypothesis=hypothesis.get("strategy", "unknown"),
                counterexample_type="spatial_permutation",
                severity=severity,
            ))

        return counterexamples

    # ------------------------------------------------------------------
    # Probe: border / interior swap
    # ------------------------------------------------------------------

    def _probe_border_interior_swap(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        adapter: GridDomainAdapter,
    ) -> List[Counterexample]:
        counterexamples: List[Counterexample] = []

        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            border_objs = [o for o in objects if o["touches_boundary"]]
            interior_objs = [o for o in objects if not o["touches_boundary"]]

            if not border_objs or not interior_objs:
                continue

            border_obj = self.rng.choice(border_objs)
            interior_obj = self.rng.choice(interior_objs)

            swapped = self._swap_objects(inp, border_obj, interior_obj)
            if swapped is None:
                continue

            baseline = self._apply_hypothesis(inp, hypothesis, adapter)
            swapped_pred = self._apply_hypothesis(swapped, hypothesis, adapter)

            if baseline is None:
                severity = 0.0
                violated = ""
            elif swapped_pred is None:
                severity = 0.7
                violated = "hypothesis broke after border/interior swap"
            elif np.array_equal(swapped_pred, baseline):
                # If the hypothesis is using touches_boundary as a real predicate,
                # swapping should change the output. Identical output suggests the
                # hypothesis ignores boundary status entirely OR is position-based.
                severity = 0.0
                violated = ""
            else:
                severity = 0.0
                violated = ""

            counterexamples.append(Counterexample(
                input_grid=swapped,
                expected_output=None,
                violated_invariant=violated,
                target_hypothesis=hypothesis.get("strategy", "unknown"),
                counterexample_type="border_interior_swap",
                severity=severity,
            ))

        return counterexamples

    # ------------------------------------------------------------------
    # CopyToPosition-specific probes
    # ------------------------------------------------------------------

    def falsify_copy_to_position(
        self,
        task_train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        execute_fn,
    ) -> FalsificationResult:
        """Falsification probes specific to CopyToPosition operator hypotheses.

        Probes: move source, add distractor, shift marker, duplicate marker,
        remove marker, change target shape, boundary destination, overlapping
        destination, color relabeling."""
        probe_families = [
            self._ctp_probe_move_source,
            self._ctp_probe_add_distractor,
            self._ctp_probe_shift_marker,
            self._ctp_probe_duplicate_marker,
            self._ctp_probe_remove_marker,
            self._ctp_probe_change_target_shape,
            self._ctp_probe_boundary_destination,
            self._ctp_probe_color_relabel,
        ]

        all_counterexamples: List[Counterexample] = []
        for probe_fn in probe_families:
            try:
                cxs = probe_fn(task_train_pairs, hypothesis, execute_fn)
                all_counterexamples.extend(cxs)
            except Exception:
                pass

        generated = len(all_counterexamples)
        failed = [cx for cx in all_counterexamples if cx.severity > 0.0]
        survived = generated - len(failed)
        score = survived / generated if generated > 0 else 1.0

        return FalsificationResult(
            hypothesis=hypothesis,
            counterexamples_generated=generated,
            counterexamples_survived=survived,
            counterexamples_failed=len(failed),
            falsification_score=score,
            failed_probes=failed,
            passed=score >= self.pass_threshold,
        )

    def _ctp_apply(
        self, inp: np.ndarray, hypothesis: Dict[str, Any], execute_fn, train_pairs
    ) -> Optional[np.ndarray]:
        try:
            return execute_fn(inp, hypothesis, train_pairs)
        except Exception:
            return None

    def _ctp_probe_move_source(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        counterexamples = []
        selector = hypothesis.get("selector", "")
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            selected = [o for o in objects if _get_property_value(o, selector)]
            if not selected:
                continue
            obj = self.rng.choice(selected)
            bbox = obj["bbox"]
            r_min, c_min, r_max, c_max = bbox
            h, w = inp.shape
            dr = self.rng.choice([-2, -1, 1, 2])
            dc = self.rng.choice([-2, -1, 1, 2])
            new_r_min, new_r_max = r_min + dr, r_max + dr
            new_c_min, new_c_max = c_min + dc, c_max + dc
            if new_r_min < 0 or new_r_max >= h or new_c_min < 0 or new_c_max >= w:
                continue
            moved = inp.copy()
            moved[obj["mask"]] = 0
            local = obj["local_mask"]
            oh, ow = local.shape
            patch = inp[r_min:r_min + oh, c_min:c_min + ow].copy()
            target = moved[new_r_min:new_r_min + oh, new_c_min:new_c_min + ow]
            target[local] = patch[local]

            pred = self._ctp_apply(moved, hypothesis, execute_fn, train_pairs)
            if pred is None:
                severity = 0.6
                violated = "hypothesis cannot handle moved source object"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=moved, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="copy_to_position",
                counterexample_type="ctp_move_source",
                severity=severity,
            ))
        return counterexamples

    def _ctp_probe_add_distractor(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        counterexamples = []
        for inp, out in train_pairs:
            slot = self._find_empty_slot(inp, 2)
            if slot is None:
                continue
            r, c = slot
            augmented = inp.copy()
            augmented[r:r + 2, c:c + 2] = self.rng.randint(1, 9)

            baseline = self._ctp_apply(inp, hypothesis, execute_fn, train_pairs)
            augmented_pred = self._ctp_apply(augmented, hypothesis, execute_fn, train_pairs)

            if baseline is None or augmented_pred is None:
                severity = 0.4
                violated = "hypothesis cannot handle distractor"
            elif augmented_pred.shape != baseline.shape:
                severity = 0.7
                violated = "distractor changed output shape"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=augmented, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="copy_to_position",
                counterexample_type="ctp_add_distractor",
                severity=severity,
            ))
        return counterexamples

    def _ctp_probe_shift_marker(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        counterexamples = []
        selector = hypothesis.get("selector", "")
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            kept = [o for o in objects if _get_property_value(o, selector)]
            if not kept:
                continue
            marker = kept[0]
            bbox = marker["bbox"]
            r_min, c_min, r_max, c_max = bbox
            h, w = inp.shape
            dr, dc = self.rng.choice([-1, 1]), self.rng.choice([-1, 1])
            new_r = r_min + dr
            new_c = c_min + dc
            oh = r_max - r_min + 1
            ow = c_max - c_min + 1
            if new_r < 0 or new_r + oh > h or new_c < 0 or new_c + ow > w:
                continue
            shifted = inp.copy()
            shifted[marker["mask"]] = 0
            local = marker["local_mask"]
            patch = inp[r_min:r_min + oh, c_min:c_min + ow].copy()
            shifted[new_r:new_r + oh, new_c:new_c + ow][local] = patch[local]

            pred = self._ctp_apply(shifted, hypothesis, execute_fn, train_pairs)
            if pred is None:
                severity = 0.5
                violated = "hypothesis cannot handle shifted marker"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=shifted, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="copy_to_position",
                counterexample_type="ctp_shift_marker",
                severity=severity,
            ))
        return counterexamples

    def _ctp_probe_duplicate_marker(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        counterexamples = []
        selector = hypothesis.get("selector", "")
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            kept = [o for o in objects if _get_property_value(o, selector)]
            if not kept:
                continue
            marker = kept[0]
            local = marker["local_mask"]
            oh, ow = local.shape
            slot = self._find_empty_slot(inp, max(oh, ow))
            if slot is None:
                continue
            r, c = slot
            duped = inp.copy()
            bbox = marker["bbox"]
            r_min, c_min = bbox[0], bbox[1]
            paste_h = min(oh, inp.shape[0] - r)
            paste_w = min(ow, inp.shape[1] - c)
            sub = local[:paste_h, :paste_w]
            patch = inp[r_min:r_min + paste_h, c_min:c_min + paste_w].copy()
            duped[r:r + paste_h, c:c + paste_w][sub] = patch[sub]

            pred = self._ctp_apply(duped, hypothesis, execute_fn, train_pairs)
            if pred is None:
                severity = 0.7
                violated = "hypothesis fails with duplicated marker"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=duped, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="copy_to_position",
                counterexample_type="ctp_duplicate_marker",
                severity=severity,
            ))
        return counterexamples

    def _ctp_probe_remove_marker(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        counterexamples = []
        selector = hypothesis.get("selector", "")
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            removed_objs = [o for o in objects if not _get_property_value(o, selector)]
            if len(removed_objs) < 2:
                continue
            victim = self.rng.choice(removed_objs)
            reduced = inp.copy()
            reduced[victim["mask"]] = 0

            pred = self._ctp_apply(reduced, hypothesis, execute_fn, train_pairs)
            if pred is None:
                severity = 0.6
                violated = "hypothesis fails with removed satellite"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=reduced, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="copy_to_position",
                counterexample_type="ctp_remove_marker",
                severity=severity,
            ))
        return counterexamples

    def _ctp_probe_change_target_shape(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        counterexamples = []
        selector = hypothesis.get("selector", "")
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            kept = [o for o in objects if _get_property_value(o, selector)]
            if not kept:
                continue
            target_obj = kept[0]
            bbox = target_obj["bbox"]
            r_min, c_min, r_max, c_max = bbox
            h, w = inp.shape
            if r_max + 1 < h:
                reshaped = inp.copy()
                color = target_obj["primary_color"]
                reshaped[r_max + 1, c_min:c_max + 1] = color
            elif r_min > 0:
                reshaped = inp.copy()
                color = target_obj["primary_color"]
                reshaped[r_min - 1, c_min:c_max + 1] = color
            else:
                continue

            pred = self._ctp_apply(reshaped, hypothesis, execute_fn, train_pairs)
            if pred is None:
                severity = 0.5
                violated = "hypothesis fails with reshaped target"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=reshaped, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="copy_to_position",
                counterexample_type="ctp_change_target_shape",
                severity=severity,
            ))
        return counterexamples

    def _ctp_probe_boundary_destination(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        counterexamples = []
        selector = hypothesis.get("selector", "")
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            removed_objs = [o for o in objects if not _get_property_value(o, selector)]
            if not removed_objs:
                continue
            h, w = inp.shape
            obj = self.rng.choice(removed_objs)
            local = obj["local_mask"]
            oh, ow = local.shape
            bbox = obj["bbox"]
            r_min, c_min = bbox[0], bbox[1]
            boundary = inp.copy()
            boundary[obj["mask"]] = 0
            nr, nc = 0, 0
            patch = inp[r_min:r_min + oh, c_min:c_min + ow].copy()
            paste_h = min(oh, h)
            paste_w = min(ow, w)
            sub = local[:paste_h, :paste_w]
            boundary[nr:nr + paste_h, nc:nc + paste_w][sub] = patch[:paste_h, :paste_w][sub]

            pred = self._ctp_apply(boundary, hypothesis, execute_fn, train_pairs)
            if pred is None:
                severity = 0.4
                violated = "hypothesis fails with boundary-placed object"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=boundary, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="copy_to_position",
                counterexample_type="ctp_boundary_destination",
                severity=severity,
            ))
        return counterexamples

    def _ctp_probe_color_relabel(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        counterexamples = []
        for inp, out in train_pairs:
            non_bg = sorted(set(inp.flatten().tolist()) - {0})
            if len(non_bg) < 2:
                continue
            perm = non_bg.copy()
            self.rng.shuffle(perm)
            if perm == non_bg:
                continue
            cmap = dict(zip(non_bg, perm))
            permuted = self._remap_colors(inp, cmap)

            baseline = self._ctp_apply(inp, hypothesis, execute_fn, train_pairs)
            permuted_pred = self._ctp_apply(permuted, hypothesis, execute_fn, train_pairs)

            if baseline is None or permuted_pred is None:
                severity = 0.5
                violated = "hypothesis returned None on color-permuted input"
            elif permuted_pred.shape != baseline.shape:
                severity = 0.8
                violated = "color permutation changed output shape"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=permuted, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="copy_to_position",
                counterexample_type="ctp_color_relabel",
                severity=severity,
            ))
        return counterexamples

    # ------------------------------------------------------------------
    # Marker-relative-specific probes
    # ------------------------------------------------------------------

    def falsify_marker_relative(
        self,
        task_train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        execute_fn,
    ) -> FalsificationResult:
        probe_families = [
            self._mr_probe_move_anchor,
            self._mr_probe_duplicate_anchor,
            self._mr_probe_remove_anchor,
            self._mr_probe_recolor_anchor,
            self._mr_probe_move_source_keep_anchor,
            self._mr_probe_add_same_color_distractor_anchor,
            self._mr_probe_change_anchor_shape,
            self._mr_probe_color_relabel,
        ]
        all_counterexamples: List[Counterexample] = []
        for probe_fn in probe_families:
            try:
                cxs = probe_fn(task_train_pairs, hypothesis, execute_fn)
                all_counterexamples.extend(cxs)
            except Exception:
                pass
        generated = len(all_counterexamples)
        failed = [cx for cx in all_counterexamples if cx.severity > 0.0]
        survived = generated - len(failed)
        score = survived / generated if generated > 0 else 1.0
        return FalsificationResult(
            hypothesis=hypothesis,
            counterexamples_generated=generated,
            counterexamples_survived=survived,
            counterexamples_failed=len(failed),
            falsification_score=score,
            failed_probes=failed,
            passed=score >= self.pass_threshold,
        )

    def _mr_get_anchor_objects(self, inp, hypothesis):
        anchor_sel = hypothesis.get("anchor_selector", hypothesis.get("selector", ""))
        objects = _extract_objects_with_properties(inp)
        return [o for o in objects if _get_property_value(o, anchor_sel)], objects

    def _mr_probe_move_anchor(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            anchors, objects = self._mr_get_anchor_objects(inp, hypothesis)
            if not anchors:
                continue
            anchor = anchors[0]
            bbox = anchor["bbox"]
            r_min, c_min, r_max, c_max = bbox
            oh, ow = r_max - r_min + 1, c_max - c_min + 1
            h, w = inp.shape
            dr, dc = self.rng.choice([-2, 2]), self.rng.choice([-2, 2])
            nr, nc = r_min + dr, c_min + dc
            if nr < 0 or nr + oh > h or nc < 0 or nc + ow > w:
                continue
            moved = inp.copy()
            moved[anchor["mask"]] = 0
            local = anchor["local_mask"]
            patch = inp[r_min:r_min + oh, c_min:c_min + ow].copy()
            moved[nr:nr + oh, nc:nc + ow][local] = patch[local]
            pred = self._ctp_apply(moved, hypothesis, execute_fn, train_pairs)
            severity = 0.6 if pred is None else 0.0
            violated = "hypothesis fails when anchor moves" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=moved, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_relative_copy_to_position",
                counterexample_type="mr_move_anchor", severity=severity,
            ))
        return counterexamples

    def _mr_probe_duplicate_anchor(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            anchors, _ = self._mr_get_anchor_objects(inp, hypothesis)
            if not anchors:
                continue
            anchor = anchors[0]
            local = anchor["local_mask"]
            oh, ow = local.shape
            slot = self._find_empty_slot(inp, max(oh, ow))
            if slot is None:
                continue
            r, c = slot
            duped = inp.copy()
            bbox = anchor["bbox"]
            paste_h = min(oh, inp.shape[0] - r)
            paste_w = min(ow, inp.shape[1] - c)
            sub = local[:paste_h, :paste_w]
            patch = inp[bbox[0]:bbox[0] + paste_h, bbox[1]:bbox[1] + paste_w].copy()
            duped[r:r + paste_h, c:c + paste_w][sub] = patch[sub]
            pred = self._ctp_apply(duped, hypothesis, execute_fn, train_pairs)
            severity = 0.7 if pred is None else 0.0
            violated = "hypothesis fails with duplicated anchor" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=duped, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_relative_copy_to_position",
                counterexample_type="mr_duplicate_anchor", severity=severity,
            ))
        return counterexamples

    def _mr_probe_remove_anchor(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            anchors, _ = self._mr_get_anchor_objects(inp, hypothesis)
            if not anchors:
                continue
            reduced = inp.copy()
            reduced[anchors[0]["mask"]] = 0
            pred = self._ctp_apply(reduced, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is None else 0.8
            violated = "" if pred is None else "hypothesis should reject when anchor is removed"
            counterexamples.append(Counterexample(
                input_grid=reduced, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_relative_copy_to_position",
                counterexample_type="mr_remove_anchor", severity=severity,
            ))
        return counterexamples

    def _mr_probe_recolor_anchor(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            anchors, _ = self._mr_get_anchor_objects(inp, hypothesis)
            if not anchors:
                continue
            recolored = inp.copy()
            anchor = anchors[0]
            new_color = (anchor["primary_color"] % 9) + 1
            recolored[anchor["mask"]] = new_color
            pred = self._ctp_apply(recolored, hypothesis, execute_fn, train_pairs)
            severity = 0.5 if pred is None else 0.0
            violated = "hypothesis fails when anchor recolored" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=recolored, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_relative_copy_to_position",
                counterexample_type="mr_recolor_anchor", severity=severity,
            ))
        return counterexamples

    def _mr_probe_move_source_keep_anchor(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        source_sel = hypothesis.get("source_selector", "")
        if not source_sel:
            source_sel = hypothesis.get("selector", "")
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            sources = [o for o in objects if not _get_property_value(o, source_sel)]
            if not sources:
                continue
            obj = self.rng.choice(sources)
            bbox = obj["bbox"]
            r_min, c_min, r_max, c_max = bbox
            oh, ow = r_max - r_min + 1, c_max - c_min + 1
            h, w = inp.shape
            dr = self.rng.choice([-2, -1, 1, 2])
            nr = r_min + dr
            if nr < 0 or nr + oh > h:
                continue
            moved = inp.copy()
            moved[obj["mask"]] = 0
            local = obj["local_mask"]
            patch = inp[r_min:r_min + oh, c_min:c_min + ow].copy()
            moved[nr:nr + oh, c_min:c_min + ow][local] = patch[local]
            pred = self._ctp_apply(moved, hypothesis, execute_fn, train_pairs)
            severity = 0.5 if pred is None else 0.0
            violated = "hypothesis fails when source moves but anchor stays" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=moved, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_relative_copy_to_position",
                counterexample_type="mr_move_source_keep_anchor", severity=severity,
            ))
        return counterexamples

    def _mr_probe_add_same_color_distractor_anchor(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            anchors, _ = self._mr_get_anchor_objects(inp, hypothesis)
            if not anchors:
                continue
            color = anchors[0]["primary_color"]
            slot = self._find_empty_slot(inp, 2)
            if slot is None:
                continue
            r, c = slot
            augmented = inp.copy()
            augmented[r:r + 2, c:c + 2] = color
            pred = self._ctp_apply(augmented, hypothesis, execute_fn, train_pairs)
            severity = 0.6 if pred is None else 0.0
            violated = "hypothesis fails with same-color distractor anchor" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=augmented, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_relative_copy_to_position",
                counterexample_type="mr_add_same_color_distractor", severity=severity,
            ))
        return counterexamples

    def _mr_probe_change_anchor_shape(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            anchors, _ = self._mr_get_anchor_objects(inp, hypothesis)
            if not anchors:
                continue
            anchor = anchors[0]
            bbox = anchor["bbox"]
            r_min, c_min, r_max, c_max = bbox
            h, w = inp.shape
            reshaped = inp.copy()
            color = anchor["primary_color"]
            if r_max + 1 < h:
                reshaped[r_max + 1, c_min:c_max + 1] = color
            elif r_min > 0:
                reshaped[r_min - 1, c_min:c_max + 1] = color
            else:
                continue
            pred = self._ctp_apply(reshaped, hypothesis, execute_fn, train_pairs)
            severity = 0.4 if pred is None else 0.0
            violated = "hypothesis fails with reshaped anchor" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=reshaped, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_relative_copy_to_position",
                counterexample_type="mr_change_anchor_shape", severity=severity,
            ))
        return counterexamples

    def _mr_probe_color_relabel(self, train_pairs, hypothesis, execute_fn):
        return self._ctp_probe_color_relabel(train_pairs, hypothesis, execute_fn)

    # ------------------------------------------------------------------
    # Hypothesis application
    # ------------------------------------------------------------------

    def _apply_hypothesis(
        self,
        inp: np.ndarray,
        hypothesis: Dict[str, Any],
        adapter: GridDomainAdapter,
    ) -> Optional[np.ndarray]:
        if "execute" in hypothesis and callable(hypothesis["execute"]):
            try:
                return hypothesis["execute"](inp)
            except Exception:
                return None

        strategy = hypothesis.get("strategy")

        if strategy == "discriminative_filter":
            prop = hypothesis.get("property", "")
            keep = hypothesis.get("keep_when_true", True)
            return _apply_filter(inp, prop, keep)

        if strategy == "transform_induction":
            rule_type = hypothesis.get("rule_type", "")
            params = hypothesis.get("params", {})
            return _apply_recolor(inp, rule_type, params)

        if strategy == "copy_to_position":
            try:
                from reasoning_project.trace_operator_invention import (
                    execute_copy_to_position,
                    CopyToPositionParams,
                )
                params = CopyToPositionParams(**hypothesis.get("params", {}))
                return execute_copy_to_position(
                    inp, params, [(inp, inp)]
                )
            except Exception:
                return None

        return None

    # ------------------------------------------------------------------
    # Grid manipulation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _remap_colors(grid: np.ndarray, color_map: Dict[int, int]) -> np.ndarray:
        result = grid.copy()
        for old_c, new_c in color_map.items():
            result[grid == old_c] = new_c
        return result

    def _find_empty_slot(
        self, grid: np.ndarray, block_size: int
    ) -> Optional[Tuple[int, int]]:
        h, w = grid.shape
        candidates: List[Tuple[int, int]] = []
        for r in range(h - block_size + 1):
            for c in range(w - block_size + 1):
                if np.all(grid[r:r + block_size, c:c + block_size] == 0):
                    candidates.append((r, c))
        if not candidates:
            return None
        return self.rng.choice(candidates)

    @staticmethod
    def _swap_objects(
        grid: np.ndarray, obj_a: Dict[str, Any], obj_b: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """Swap two objects by exchanging the pixel values in their bounding boxes.
        Returns None if the bounding boxes overlap or don't fit after swap."""
        bbox_a = obj_a["bbox"]
        bbox_b = obj_b["bbox"]
        mask_a = obj_a["mask"]
        mask_b = obj_b["mask"]

        overlap = np.any(mask_a & mask_b)
        if overlap:
            return None

        ra_min, ca_min, ra_max, ca_max = bbox_a
        rb_min, cb_min, rb_max, cb_max = bbox_b
        ah, aw = ra_max - ra_min + 1, ca_max - ca_min + 1
        bh, bw = rb_max - rb_min + 1, cb_max - cb_min + 1

        h, w = grid.shape
        if rb_min + ah > h or cb_min + aw > w:
            return None
        if ra_min + bh > h or ca_min + bw > w:
            return None

        result = grid.copy()

        result[mask_a] = 0
        result[mask_b] = 0

        patch_a = grid[ra_min:ra_min + ah, ca_min:ca_min + aw].copy()
        patch_b = grid[rb_min:rb_min + bh, cb_min:cb_min + bw].copy()
        local_a = obj_a["local_mask"]
        local_b = obj_b["local_mask"]

        # Place object A at position B
        target_a = result[rb_min:rb_min + ah, cb_min:cb_min + aw]
        target_a[local_a] = patch_a[local_a]

        # Place object B at position A
        target_b = result[ra_min:ra_min + bh, ca_min:ca_min + bw]
        target_b[local_b] = patch_b[local_b]

        return result

    # ------------------------------------------------------------------
    # Correspondence-specific probes
    # ------------------------------------------------------------------

    def falsify_correspondence(
        self,
        task_train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        execute_fn,
    ) -> FalsificationResult:
        """Falsification probes for correspondence-based operator hypotheses.

        Probes target the structural matching that correspondence depends on:
        duplicating same-color/shape objects, swapping colors, perturbing order,
        adding distractor anchors, removing matched targets, creating ties.
        """
        probe_families = [
            self._corr_probe_duplicate_same_color,
            self._corr_probe_duplicate_same_shape,
            self._corr_probe_swap_colors,
            self._corr_probe_perturb_row_order,
            self._corr_probe_add_distractor_anchor,
            self._corr_probe_remove_matched_target,
            self._corr_probe_create_nearest_tie,
            self._corr_probe_move_single_source,
            self._corr_probe_add_same_topo_diff_color,
            self._corr_probe_color_relabel,
        ]

        all_counterexamples: List[Counterexample] = []
        for probe_fn in probe_families:
            try:
                cxs = probe_fn(task_train_pairs, hypothesis, execute_fn)
                all_counterexamples.extend(cxs)
            except Exception:
                pass

        generated = len(all_counterexamples)
        failed = [cx for cx in all_counterexamples if cx.severity > 0.0]
        survived = generated - len(failed)
        score = survived / generated if generated > 0 else 1.0

        return FalsificationResult(
            hypothesis=hypothesis,
            counterexamples_generated=generated,
            counterexamples_survived=survived,
            counterexamples_failed=len(failed),
            falsification_score=score,
            failed_probes=failed,
            passed=score >= self.pass_threshold,
        )

    def _corr_get_objects(self, inp, hypothesis):
        selector = hypothesis.get("selector", hypothesis.get("source_selector", ""))
        objects = _extract_objects_with_properties(inp)
        removed = [o for o in objects if not _get_property_value(o, selector)]
        kept = [o for o in objects if _get_property_value(o, selector)]
        return removed, kept, objects

    def _corr_probe_duplicate_same_color(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            removed, kept, _ = self._corr_get_objects(inp, hypothesis)
            if not removed:
                continue
            src = removed[0]
            color = src.get("primary_color", 1)
            slot = self._find_empty_slot(inp, 2)
            if slot is None:
                continue
            r, c = slot
            duped = inp.copy()
            duped[r:r + 2, c:c + 2] = color
            pred = self._ctp_apply(duped, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is not None else 0.5
            violated = "duplicate same-color breaks correspondence" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=duped, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="correspondence_copy_to_position",
                counterexample_type="corr_duplicate_same_color",
                severity=severity,
            ))
        return counterexamples

    def _corr_probe_duplicate_same_shape(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            removed, kept, _ = self._corr_get_objects(inp, hypothesis)
            if not removed:
                continue
            src = removed[0]
            local = src.get("local_mask")
            if local is None:
                continue
            oh, ow = local.shape
            slot = self._find_empty_slot(inp, max(oh, ow))
            if slot is None:
                continue
            r, c = slot
            duped = inp.copy()
            bbox = src["bbox"]
            r_min, c_min = bbox[0], bbox[1]
            paste_h = min(oh, inp.shape[0] - r)
            paste_w = min(ow, inp.shape[1] - c)
            sub = local[:paste_h, :paste_w]
            patch = inp[r_min:r_min + paste_h, c_min:c_min + paste_w].copy()
            duped[r:r + paste_h, c:c + paste_w][sub] = patch[sub]
            pred = self._ctp_apply(duped, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is not None else 0.5
            violated = "duplicate same-shape breaks correspondence" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=duped, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="correspondence_copy_to_position",
                counterexample_type="corr_duplicate_same_shape",
                severity=severity,
            ))
        return counterexamples

    def _corr_probe_swap_colors(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            removed, kept, _ = self._corr_get_objects(inp, hypothesis)
            if len(removed) < 2:
                continue
            c1 = removed[0].get("primary_color", 1)
            c2 = removed[1].get("primary_color", 2)
            if c1 == c2:
                continue
            swapped = self._remap_colors(inp, {c1: c2, c2: c1})
            pred = self._ctp_apply(swapped, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is not None else 0.6
            violated = "color swap breaks correspondence" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=swapped, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="correspondence_copy_to_position",
                counterexample_type="corr_swap_colors",
                severity=severity,
            ))
        return counterexamples

    def _corr_probe_perturb_row_order(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            removed, kept, _ = self._corr_get_objects(inp, hypothesis)
            if len(removed) < 2:
                continue
            o1, o2 = removed[0], removed[1]
            swapped = self._swap_objects(inp, o1, o2)
            if swapped is None:
                continue
            pred = self._ctp_apply(swapped, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is not None else 0.5
            violated = "row/col order perturbation breaks correspondence" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=swapped, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="correspondence_copy_to_position",
                counterexample_type="corr_perturb_row_order",
                severity=severity,
            ))
        return counterexamples

    def _corr_probe_add_distractor_anchor(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            removed, kept, _ = self._corr_get_objects(inp, hypothesis)
            if not kept:
                continue
            anchor = kept[0]
            local = anchor.get("local_mask")
            if local is None:
                continue
            oh, ow = local.shape
            slot = self._find_empty_slot(inp, max(oh, ow))
            if slot is None:
                continue
            r, c = slot
            augmented = inp.copy()
            bbox = anchor["bbox"]
            r_min, c_min = bbox[0], bbox[1]
            paste_h = min(oh, inp.shape[0] - r)
            paste_w = min(ow, inp.shape[1] - c)
            sub = local[:paste_h, :paste_w]
            patch = inp[r_min:r_min + paste_h, c_min:c_min + paste_w].copy()
            augmented[r:r + paste_h, c:c + paste_w][sub] = patch[sub]
            pred = self._ctp_apply(augmented, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is not None else 0.5
            violated = "distractor anchor breaks correspondence" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=augmented, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="correspondence_copy_to_position",
                counterexample_type="corr_add_distractor_anchor",
                severity=severity,
            ))
        return counterexamples

    def _corr_probe_remove_matched_target(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            removed, kept, _ = self._corr_get_objects(inp, hypothesis)
            if not kept:
                continue
            target = kept[0]
            erased = inp.copy()
            erased[target["mask"]] = 0
            pred = self._ctp_apply(erased, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is None else 0.7
            violated = "" if pred is None else "hypothesis still works with removed target"
            counterexamples.append(Counterexample(
                input_grid=erased, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="correspondence_copy_to_position",
                counterexample_type="corr_remove_matched_target",
                severity=severity,
            ))
        return counterexamples

    def _corr_probe_create_nearest_tie(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            removed, kept, _ = self._corr_get_objects(inp, hypothesis)
            if not removed or not kept:
                continue
            src = removed[0]
            tgt = kept[0]
            sr = src.get("center_r", src["bbox"][0])
            sc = src.get("center_c", src["bbox"][1])
            tr = tgt.get("center_r", tgt["bbox"][0])
            tc = tgt.get("center_c", tgt["bbox"][1])
            mirror_r = 2 * sr - tr
            mirror_c = 2 * sc - tc
            if mirror_r < 0 or mirror_r >= inp.shape[0] - 1 or mirror_c < 0 or mirror_c >= inp.shape[1] - 1:
                continue
            tied = inp.copy()
            tied[int(mirror_r), int(mirror_c)] = tgt.get("primary_color", 1)
            pred = self._ctp_apply(tied, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is not None else 0.4
            violated = "nearest-anchor tie breaks correspondence" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=tied, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="correspondence_copy_to_position",
                counterexample_type="corr_create_nearest_tie",
                severity=severity,
            ))
        return counterexamples

    def _corr_probe_move_single_source(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        selector = hypothesis.get("selector", hypothesis.get("source_selector", ""))
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            selected = [o for o in objects if not _get_property_value(o, selector)]
            if not selected:
                continue
            obj = self.rng.choice(selected)
            bbox = obj["bbox"]
            r_min, c_min, r_max, c_max = bbox
            h, w = inp.shape
            dr = self.rng.choice([-2, -1, 1, 2])
            dc = self.rng.choice([-2, -1, 1, 2])
            nr, nc = r_min + dr, c_min + dc
            oh = r_max - r_min + 1
            ow = c_max - c_min + 1
            if nr < 0 or nr + oh > h or nc < 0 or nc + ow > w:
                continue
            moved = inp.copy()
            moved[obj["mask"]] = 0
            local = obj["local_mask"]
            patch = inp[r_min:r_min + oh, c_min:c_min + ow].copy()
            moved[nr:nr + oh, nc:nc + ow][local] = patch[local]
            pred = self._ctp_apply(moved, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is not None else 0.5
            violated = "moving single source breaks correspondence" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=moved, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="correspondence_copy_to_position",
                counterexample_type="corr_move_single_source",
                severity=severity,
            ))
        return counterexamples

    def _corr_probe_add_same_topo_diff_color(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            removed, kept, _ = self._corr_get_objects(inp, hypothesis)
            if not removed:
                continue
            src = removed[0]
            local = src.get("local_mask")
            if local is None:
                continue
            oh, ow = local.shape
            slot = self._find_empty_slot(inp, max(oh, ow))
            if slot is None:
                continue
            r, c = slot
            new_color = (src.get("primary_color", 1) % 9) + 1
            augmented = inp.copy()
            paste_h = min(oh, inp.shape[0] - r)
            paste_w = min(ow, inp.shape[1] - c)
            sub = local[:paste_h, :paste_w]
            augmented[r:r + paste_h, c:c + paste_w][sub] = new_color
            pred = self._ctp_apply(augmented, hypothesis, execute_fn, train_pairs)
            severity = 0.0 if pred is not None else 0.4
            violated = "same topology different color breaks correspondence" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=augmented, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="correspondence_copy_to_position",
                counterexample_type="corr_same_topo_diff_color",
                severity=severity,
            ))
        return counterexamples

    def _corr_probe_color_relabel(self, train_pairs, hypothesis, execute_fn):
        counterexamples = []
        for inp, out in train_pairs:
            colors = sorted(set(int(c) for c in inp.flat if c != 0))
            if len(colors) < 2:
                continue
            for _ in range(self.n_color_permutations):
                perm = list(colors)
                self.rng.shuffle(perm)
                cmap = dict(zip(colors, perm))
                if all(cmap[c] == c for c in colors):
                    continue
                relabeled = self._remap_colors(inp, cmap)
                pred = self._ctp_apply(relabeled, hypothesis, execute_fn, train_pairs)
                severity = 0.0 if pred is not None else 0.3
                violated = "color relabeling breaks correspondence" if pred is None else ""
                counterexamples.append(Counterexample(
                    input_grid=relabeled, expected_output=None,
                    violated_invariant=violated,
                    target_hypothesis="correspondence_copy_to_position",
                    counterexample_type="corr_color_relabel",
                    severity=severity,
                ))
        return counterexamples

    # ═══════════════════════════════════════════════════════════════════════
    # VARIABLE DESTINATION POLICY FALSIFICATION
    # ═══════════════════════════════════════════════════════════════════════

    def falsify_variable_destination(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        adapter: Any,
    ) -> List[Counterexample]:
        """Run falsification probes specific to variable destination policies."""
        counterexamples = []
        selector = hypothesis.get("property", "")
        policy_type = hypothesis.get("parameters", {}).get("policy_type", "")

        from reasoning_project.destination_policy import (
            infer_variable_destination_params,
            execute_variable_destination_copy,
        )

        def _vdp_apply(grid, hyp, fn, tps):
            result = infer_variable_destination_params(tps, selector, keep_when_true=True)
            if result is None:
                return None
            params, _, _ = result
            return execute_variable_destination_copy(grid, params, tps)

        # Probe 1: add distractor anchor object
        for inp, out in train_pairs[:2]:
            perturbed = inp.copy()
            H, W = perturbed.shape
            for r in range(H - 2):
                for c in range(W - 2):
                    if np.all(perturbed[r:r + 2, c:c + 2] == 0):
                        perturbed[r:r + 2, c:c + 2] = 7
                        break
                else:
                    continue
                break
            pred = _vdp_apply(perturbed, hypothesis, None, train_pairs)
            severity = 0.0 if pred is not None else 0.3
            counterexamples.append(Counterexample(
                input_grid=perturbed, expected_output=None,
                violated_invariant="distractor anchor changes destination" if pred is None else "",
                target_hypothesis="variable_destination_copy",
                counterexample_type="vdp_distractor_anchor",
                severity=severity,
            ))

        # Probe 2: move source object to different position
        for inp, out in train_pairs[:2]:
            from reasoning_project.reasoning_engine import (
                _extract_objects_with_properties,
                _get_property_value,
            )
            objects = _extract_objects_with_properties(inp)
            removed = [o for o in objects if not _get_property_value(o, selector)]
            if not removed:
                continue
            perturbed = inp.copy()
            obj = removed[0]
            mask = obj.get("mask")
            if mask is None:
                continue
            rows, cols = np.where(mask)
            if len(rows) == 0:
                continue
            shift_r = min(2, inp.shape[0] - rows.max() - 1)
            if shift_r <= 0:
                shift_r = max(-2, -rows.min())
            perturbed[mask] = 0
            for r, c in zip(rows, cols):
                nr = r + shift_r
                if 0 <= nr < inp.shape[0]:
                    perturbed[nr, c] = inp[r, c]
            pred = _vdp_apply(perturbed, hypothesis, None, train_pairs)
            severity = 0.0 if pred is not None else 0.3
            counterexamples.append(Counterexample(
                input_grid=perturbed, expected_output=None,
                violated_invariant="moved source breaks policy" if pred is None else "",
                target_hypothesis="variable_destination_copy",
                counterexample_type="vdp_move_source",
                severity=severity,
            ))

        # Probe 3: block predicted destination with obstacle
        for inp, out in train_pairs[:2]:
            objects = _extract_objects_with_properties(inp)
            removed = [o for o in objects if not _get_property_value(o, selector)]
            if not removed:
                continue
            result = infer_variable_destination_params(train_pairs, selector, keep_when_true=True)
            if result is None:
                continue
            params, _, _ = result
            from reasoning_project.trace_operator_invention import _extract_object_masks
            masks = _extract_object_masks(inp, removed)
            from reasoning_project.destination_policy import (
                DestinationPolicyInducer,
                build_scene_context,
            )
            inducer = DestinationPolicyInducer()
            kept = [o for o in objects if _get_property_value(o, selector)]
            kept_masks = _extract_object_masks(inp, kept)
            removed_masks = masks
            scene = build_scene_context(
                inp, objects, kept, removed, kept_masks, removed_masks,
            )
            for src_obj, src_mask in zip(removed, masks):
                dest = inducer._select_destination(
                    params.destination_policy, inp, src_obj, src_mask, scene, kept,
                )
                if dest is not None:
                    perturbed = inp.copy()
                    dr, dc = dest
                    if 0 <= dr < inp.shape[0] and 0 <= dc < inp.shape[1]:
                        perturbed[dr, dc] = 9
                    pred = _vdp_apply(perturbed, hypothesis, None, train_pairs)
                    severity = 0.5 if pred is not None else 0.0
                    counterexamples.append(Counterexample(
                        input_grid=perturbed, expected_output=None,
                        violated_invariant="policy ignores blocked destination" if pred is not None else "",
                        target_hypothesis="variable_destination_copy",
                        counterexample_type="vdp_block_destination",
                        severity=severity,
                    ))
                    break

        # Probe 4: remove an anchor object
        for inp, out in train_pairs[:1]:
            objects = _extract_objects_with_properties(inp)
            kept = [o for o in objects if _get_property_value(o, selector)]
            if len(kept) < 2:
                continue
            perturbed = inp.copy()
            mask = kept[0].get("mask")
            if mask is not None:
                perturbed[mask] = 0
            pred = _vdp_apply(perturbed, hypothesis, None, train_pairs)
            severity = 0.0 if pred is not None else 0.3
            counterexamples.append(Counterexample(
                input_grid=perturbed, expected_output=None,
                violated_invariant="anchor removal changes result" if pred is None else "",
                target_hypothesis="variable_destination_copy",
                counterexample_type="vdp_remove_anchor",
                severity=severity,
            ))

        # Probe 5: add extra open slot
        for inp, out in train_pairs[:1]:
            perturbed = inp.copy()
            H, W = perturbed.shape
            for r in range(H - 3):
                for c in range(W - 3):
                    if np.all(perturbed[r:r + 3, c:c + 3] == 0):
                        break
                else:
                    continue
                break
            pred = _vdp_apply(perturbed, hypothesis, None, train_pairs)
            counterexamples.append(Counterexample(
                input_grid=perturbed, expected_output=None,
                violated_invariant="",
                target_hypothesis="variable_destination_copy",
                counterexample_type="vdp_extra_open_slot",
                severity=0.0,
            ))

        # Probe 6: swap two anchor positions
        for inp, out in train_pairs[:1]:
            objects = _extract_objects_with_properties(inp)
            kept = [o for o in objects if _get_property_value(o, selector)]
            if len(kept) < 2:
                continue
            perturbed = inp.copy()
            m0 = kept[0].get("mask")
            m1 = kept[1].get("mask")
            if m0 is None or m1 is None:
                continue
            colors0 = inp[m0].copy()
            colors1 = inp[m1].copy()
            perturbed[m0] = 0
            perturbed[m1] = 0
            r0, c0 = np.where(m0)
            r1, c1 = np.where(m1)
            if len(r0) == len(r1):
                for ri, ci, v in zip(r0, c0, colors1):
                    if 0 <= ri < H and 0 <= ci < W:
                        perturbed[ri, ci] = v
                for ri, ci, v in zip(r1, c1, colors0):
                    if 0 <= ri < H and 0 <= ci < W:
                        perturbed[ri, ci] = v
                pred = _vdp_apply(perturbed, hypothesis, None, train_pairs)
                severity = 0.0 if pred is not None else 0.3
                counterexamples.append(Counterexample(
                    input_grid=perturbed, expected_output=None,
                    violated_invariant="anchor swap breaks policy" if pred is None else "",
                    target_hypothesis="variable_destination_copy",
                    counterexample_type="vdp_swap_anchors",
                    severity=severity,
                ))

        return counterexamples

    # ═══════════════════════════════════════════════════════════════════════
    # MARKER-PROJECTION FALSIFICATION
    # ═══════════════════════════════════════════════════════════════════════

    def falsify_marker_projection(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        execute_fn,
    ) -> FalsificationResult:
        """Falsification probes specific to marker-projection operator hypotheses.

        Probes:
        - mp_move_marker: shift a removed marker object
        - mp_add_marker: add an extra marker (should create extra projection)
        - mp_remove_marker: remove a marker (should remove its projection)
        - mp_change_marker_color: change marker color (projection color should change)
        - mp_move_target: shift a kept object (projection target should move)
        - mp_block_projection_path: place obstacle in projection path
        """
        probe_families = [
            self._mp_probe_move_marker,
            self._mp_probe_add_marker,
            self._mp_probe_remove_marker,
            self._mp_probe_change_marker_color,
            self._mp_probe_move_target,
            self._mp_probe_block_projection_path,
        ]

        all_counterexamples: List[Counterexample] = []
        for probe_fn in probe_families:
            try:
                cxs = probe_fn(train_pairs, hypothesis, execute_fn)
                all_counterexamples.extend(cxs)
            except Exception:
                pass

        generated = len(all_counterexamples)
        failed = [cx for cx in all_counterexamples if cx.severity > 0.0]
        survived = generated - len(failed)
        score = survived / generated if generated > 0 else 1.0

        return FalsificationResult(
            hypothesis=hypothesis,
            counterexamples_generated=generated,
            counterexamples_survived=survived,
            counterexamples_failed=len(failed),
            falsification_score=score,
            failed_probes=failed,
            passed=score >= self.pass_threshold,
        )

    def _mp_get_objects(self, inp, hypothesis):
        """Split objects into kept and removed (markers) using selector."""
        selector = hypothesis.get("selector", hypothesis.get("source_selector", ""))
        keep_when_true = hypothesis.get("keep_when_true", True)
        objects = _extract_objects_with_properties(inp)
        kept = [o for o in objects if _get_property_value(o, selector) == keep_when_true]
        removed = [o for o in objects if _get_property_value(o, selector) != keep_when_true]
        return kept, removed, objects

    def _mp_probe_move_marker(self, train_pairs, hypothesis, execute_fn):
        """Shift a removed marker object; the projection should adapt."""
        counterexamples = []
        for inp, out in train_pairs:
            kept, removed, _ = self._mp_get_objects(inp, hypothesis)
            if not removed:
                continue
            marker = self.rng.choice(removed)
            bbox = marker["bbox"]
            r_min, c_min, r_max, c_max = bbox
            oh, ow = r_max - r_min + 1, c_max - c_min + 1
            h, w = inp.shape
            dr = self.rng.choice([-2, -1, 1, 2])
            dc = self.rng.choice([-2, -1, 1, 2])
            nr, nc = r_min + dr, c_min + dc
            if nr < 0 or nr + oh > h or nc < 0 or nc + ow > w:
                continue
            moved = inp.copy()
            moved[marker["mask"]] = 0
            local = marker["local_mask"]
            patch = inp[r_min:r_min + oh, c_min:c_min + ow].copy()
            moved[nr:nr + oh, nc:nc + ow][local] = patch[local]

            pred = self._ctp_apply(moved, hypothesis, execute_fn, train_pairs)
            severity = 0.5 if pred is None else 0.0
            violated = "hypothesis cannot handle moved marker" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=moved, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_projection",
                counterexample_type="mp_move_marker",
                severity=severity,
            ))
        return counterexamples

    def _mp_probe_add_marker(self, train_pairs, hypothesis, execute_fn):
        """Add an extra marker; should create an extra projection."""
        counterexamples = []
        for inp, out in train_pairs:
            kept, removed, _ = self._mp_get_objects(inp, hypothesis)
            if not removed:
                continue
            marker = removed[0]
            local = marker["local_mask"]
            oh, ow = local.shape
            slot = self._find_empty_slot(inp, max(oh, ow))
            if slot is None:
                continue
            r, c = slot
            augmented = inp.copy()
            bbox = marker["bbox"]
            r_min, c_min = bbox[0], bbox[1]
            paste_h = min(oh, inp.shape[0] - r)
            paste_w = min(ow, inp.shape[1] - c)
            sub = local[:paste_h, :paste_w]
            patch = inp[r_min:r_min + paste_h, c_min:c_min + paste_w].copy()
            augmented[r:r + paste_h, c:c + paste_w][sub] = patch[sub]

            pred = self._ctp_apply(augmented, hypothesis, execute_fn, train_pairs)
            severity = 0.6 if pred is None else 0.0
            violated = "hypothesis fails with extra marker" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=augmented, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_projection",
                counterexample_type="mp_add_marker",
                severity=severity,
            ))
        return counterexamples

    def _mp_probe_remove_marker(self, train_pairs, hypothesis, execute_fn):
        """Remove a marker; its projection should disappear."""
        counterexamples = []
        for inp, out in train_pairs:
            kept, removed, _ = self._mp_get_objects(inp, hypothesis)
            if len(removed) < 2:
                continue
            victim = self.rng.choice(removed)
            reduced = inp.copy()
            reduced[victim["mask"]] = 0

            pred = self._ctp_apply(reduced, hypothesis, execute_fn, train_pairs)
            severity = 0.5 if pred is None else 0.0
            violated = "hypothesis fails with removed marker" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=reduced, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_projection",
                counterexample_type="mp_remove_marker",
                severity=severity,
            ))
        return counterexamples

    def _mp_probe_change_marker_color(self, train_pairs, hypothesis, execute_fn):
        """Change a marker's color; projection color should change accordingly."""
        counterexamples = []
        for inp, out in train_pairs:
            kept, removed, _ = self._mp_get_objects(inp, hypothesis)
            if not removed:
                continue
            marker = self.rng.choice(removed)
            new_color = (marker["primary_color"] % 9) + 1
            recolored = inp.copy()
            recolored[marker["mask"]] = new_color

            pred = self._ctp_apply(recolored, hypothesis, execute_fn, train_pairs)
            severity = 0.5 if pred is None else 0.0
            violated = "hypothesis fails when marker color changes" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=recolored, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_projection",
                counterexample_type="mp_change_marker_color",
                severity=severity,
            ))
        return counterexamples

    def _mp_probe_move_target(self, train_pairs, hypothesis, execute_fn):
        """Shift a kept object; projection should follow."""
        counterexamples = []
        for inp, out in train_pairs:
            kept, removed, _ = self._mp_get_objects(inp, hypothesis)
            if not kept:
                continue
            target = self.rng.choice(kept)
            bbox = target["bbox"]
            r_min, c_min, r_max, c_max = bbox
            oh, ow = r_max - r_min + 1, c_max - c_min + 1
            h, w = inp.shape
            dr = self.rng.choice([-2, -1, 1, 2])
            dc = self.rng.choice([-2, -1, 1, 2])
            nr, nc = r_min + dr, c_min + dc
            if nr < 0 or nr + oh > h or nc < 0 or nc + ow > w:
                continue
            moved = inp.copy()
            moved[target["mask"]] = 0
            local = target["local_mask"]
            patch = inp[r_min:r_min + oh, c_min:c_min + ow].copy()
            moved[nr:nr + oh, nc:nc + ow][local] = patch[local]

            pred = self._ctp_apply(moved, hypothesis, execute_fn, train_pairs)
            severity = 0.5 if pred is None else 0.0
            violated = "hypothesis fails when target moves" if pred is None else ""
            counterexamples.append(Counterexample(
                input_grid=moved, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="marker_projection",
                counterexample_type="mp_move_target",
                severity=severity,
            ))
        return counterexamples

    def _mp_probe_block_projection_path(self, train_pairs, hypothesis, execute_fn):
        """Place an obstacle in the projection path; should block the projection."""
        counterexamples = []
        for inp, out in train_pairs:
            kept, removed, _ = self._mp_get_objects(inp, hypothesis)
            if not removed or not kept:
                continue
            marker = removed[0]
            target = kept[0]
            mr = int(marker.get("center_r", marker["bbox"][0]))
            mc = int(marker.get("center_c", marker["bbox"][1]))
            tr = int(target.get("center_r", target["bbox"][0]))
            tc = int(target.get("center_c", target["bbox"][1]))

            # Place obstacle between marker and target
            mid_r = (mr + tr) // 2
            mid_c = (mc + tc) // 2
            h, w = inp.shape
            if 0 <= mid_r < h and 0 <= mid_c < w and inp[mid_r, mid_c] == 0:
                blocked = inp.copy()
                blocked[mid_r, mid_c] = 9  # obstacle color
                pred = self._ctp_apply(blocked, hypothesis, execute_fn, train_pairs)
                severity = 0.0 if pred is not None else 0.4
                violated = "hypothesis fails with blocked path" if pred is None else ""
                counterexamples.append(Counterexample(
                    input_grid=blocked, expected_output=None,
                    violated_invariant=violated,
                    target_hypothesis="marker_projection",
                    counterexample_type="mp_block_projection_path",
                    severity=severity,
                ))
        return counterexamples

    # ═══════════════════════════════════════════════════════════════════════
    # COLOR-TRANSFER FALSIFICATION
    # ═══════════════════════════════════════════════════════════════════════

    def falsify_color_transfer(
        self,
        task_train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        hypothesis: Dict[str, Any],
        execute_fn,
    ) -> FalsificationResult:
        """Falsification probes for color-transfer recolor hypotheses."""
        probe_families = [
            self._ct_probe_add_same_color_distractor,
            self._ct_probe_add_closer_distractor,
            self._ct_probe_recolor_source,
            self._ct_probe_move_source,
            self._ct_probe_swap_source_target_colors,
            self._ct_probe_duplicate_color_source,
            self._ct_probe_remove_color_source,
            self._ct_probe_change_neighbor_color,
            self._ct_probe_add_competing_same_shape,
            self._ct_probe_background_color_perturbation,
        ]

        all_counterexamples: List[Counterexample] = []
        for probe_fn in probe_families:
            try:
                cxs = probe_fn(task_train_pairs, hypothesis, execute_fn)
                all_counterexamples.extend(cxs)
            except Exception:
                pass

        generated = len(all_counterexamples)
        failed = [cx for cx in all_counterexamples if cx.severity > 0.0]
        survived = generated - len(failed)
        score = survived / generated if generated > 0 else 1.0

        return FalsificationResult(
            hypothesis=hypothesis,
            counterexamples_generated=generated,
            counterexamples_survived=survived,
            counterexamples_failed=len(failed),
            falsification_score=score,
            failed_probes=failed,
            passed=score >= self.pass_threshold,
        )

    # ------------------------------------------------------------------
    # Color-transfer helpers
    # ------------------------------------------------------------------

    def _ct_apply(
        self, inp: np.ndarray, hypothesis: Dict[str, Any], execute_fn, train_pairs
    ) -> Optional[np.ndarray]:
        """Apply the color-transfer hypothesis, returning None on failure."""
        try:
            return execute_fn(inp, hypothesis, train_pairs)
        except Exception:
            return None

    def _ct_get_objects(self, inp: np.ndarray, hypothesis: Dict[str, Any]):
        """Get kept and target objects for color-transfer.

        Returns (kept, targets, all_objects).
        """
        selector = hypothesis.get("selector", "") or hypothesis.get("source_selector", "")
        invert = hypothesis.get("invert_selector", False)
        objects = _extract_objects_with_properties(inp)
        kept: List[Dict[str, Any]] = []
        targets: List[Dict[str, Any]] = []
        for o in objects:
            val = _get_property_value(o, selector)
            is_target = (not val) if not invert else val
            if is_target:
                targets.append(o)
            else:
                kept.append(o)
        return kept, targets, objects

    # ------------------------------------------------------------------
    # Color-transfer probes
    # ------------------------------------------------------------------

    def _ct_probe_add_same_color_distractor(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Add a small object with the same color as the color source.

        The hypothesis should still work (the distractor shouldn't change
        the color-transfer rule).  Severity 0.5 if hypothesis fails.
        """
        counterexamples: List[Counterexample] = []
        for inp, out in train_pairs:
            kept, targets, _ = self._ct_get_objects(inp, hypothesis)
            if not kept:
                continue
            source = kept[0]
            color = source.get("primary_color", 1)
            slot = self._find_empty_slot(inp, 2)
            if slot is None:
                continue
            r, c = slot
            augmented = inp.copy()
            augmented[r:r + 2, c:c + 2] = color

            baseline = self._ct_apply(inp, hypothesis, execute_fn, train_pairs)
            pred = self._ct_apply(augmented, hypothesis, execute_fn, train_pairs)
            if baseline is None:
                continue
            if pred is None:
                severity = 0.5
                violated = "hypothesis fails with same-color distractor added"
            elif pred.shape != baseline.shape or not np.array_equal(pred, baseline):
                severity = 0.5
                violated = "same-color distractor changed color-transfer output"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=augmented, expected_output=baseline,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_add_same_color_distractor",
                severity=severity,
            ))
        return counterexamples

    def _ct_probe_add_closer_distractor(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Add a closer kept object between source and target.

        For 'nearest_kept' rules this should change the outcome (since
        nearest changes).  If the hypothesis still produces the OLD output,
        it is broken.  For non-nearest rules it should still work.
        Severity 0.8 if rule is nearest_kept and prediction unchanged.
        """
        counterexamples: List[Counterexample] = []
        rule_type = hypothesis.get("parameters", hypothesis).get("rule_type", "")
        for inp, out in train_pairs:
            kept, targets, _ = self._ct_get_objects(inp, hypothesis)
            if not kept or not targets:
                continue
            source = kept[0]
            target = targets[0]
            sr = int(source.get("center_r", source["bbox"][0]))
            sc = int(source.get("center_c", source["bbox"][1]))
            tr = int(target.get("center_r", target["bbox"][0]))
            tc = int(target.get("center_c", target["bbox"][1]))

            # Place a new kept-style object midway between source and target
            mid_r = (sr + tr) // 2
            mid_c = (sc + tc) // 2
            h, w = inp.shape
            if mid_r < 0 or mid_r + 2 > h or mid_c < 0 or mid_c + 2 > w:
                continue
            if not np.all(inp[mid_r:mid_r + 2, mid_c:mid_c + 2] == 0):
                continue

            new_color = (source.get("primary_color", 1) % 9) + 1
            augmented = inp.copy()
            augmented[mid_r:mid_r + 2, mid_c:mid_c + 2] = new_color

            baseline = self._ct_apply(inp, hypothesis, execute_fn, train_pairs)
            pred = self._ct_apply(augmented, hypothesis, execute_fn, train_pairs)
            if baseline is None:
                continue

            if rule_type == "nearest_kept":
                # For nearest_kept, the output SHOULD change because a closer
                # kept object now exists.  If the prediction is identical to
                # baseline, the hypothesis is not truly using nearest logic.
                if pred is not None and np.array_equal(pred, baseline):
                    severity = 0.8
                    violated = (
                        "nearest_kept rule ignores closer distractor — "
                        "prediction unchanged despite nearer kept object"
                    )
                else:
                    severity = 0.0
                    violated = ""
            else:
                # For non-nearest rules, the distractor should not matter
                if pred is None:
                    severity = 0.5
                    violated = "hypothesis fails with closer distractor (non-nearest rule)"
                elif not np.array_equal(pred, baseline):
                    severity = 0.5
                    violated = "closer distractor changed output for non-nearest rule"
                else:
                    severity = 0.0
                    violated = ""
            counterexamples.append(Counterexample(
                input_grid=augmented, expected_output=baseline,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_add_closer_distractor",
                severity=severity,
            ))
        return counterexamples

    def _ct_probe_recolor_source(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Change the color of the color-source object.

        The target's output color should change accordingly (since it
        derives from the source).  If the hypothesis gives the old color,
        it is not truly deriving color from context.  Severity 1.0 if old
        output persists.
        """
        counterexamples: List[Counterexample] = []
        for inp, out in train_pairs:
            kept, targets, _ = self._ct_get_objects(inp, hypothesis)
            if not kept:
                continue
            source = kept[0]
            old_color = source.get("primary_color", 1)
            new_color = (old_color % 9) + 1

            recolored = inp.copy()
            recolored[source["mask"]] = new_color

            baseline = self._ct_apply(inp, hypothesis, execute_fn, train_pairs)
            pred = self._ct_apply(recolored, hypothesis, execute_fn, train_pairs)
            if baseline is None:
                continue

            if pred is not None and np.array_equal(pred, baseline):
                severity = 1.0
                violated = (
                    "recoloring source did not change output — "
                    "hypothesis not deriving color from source"
                )
            elif pred is None:
                severity = 0.5
                violated = "hypothesis fails when source is recolored"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=recolored, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_recolor_source",
                severity=severity,
            ))
        return counterexamples

    def _ct_probe_move_source(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Move the color-source object.

        For nearest/neighbor rules, this may change which source is
        closest.  For same-shape/same-size, it shouldn't matter.
        Severity 0.5 if hypothesis fails entirely.
        """
        counterexamples: List[Counterexample] = []
        for inp, out in train_pairs:
            kept, targets, _ = self._ct_get_objects(inp, hypothesis)
            if not kept:
                continue
            source = kept[0]
            bbox = source["bbox"]
            r_min, c_min, r_max, c_max = bbox
            oh, ow = r_max - r_min + 1, c_max - c_min + 1
            h, w = inp.shape
            dr = self.rng.choice([-2, -1, 1, 2])
            dc = self.rng.choice([-2, -1, 1, 2])
            nr, nc = r_min + dr, c_min + dc
            if nr < 0 or nr + oh > h or nc < 0 or nc + ow > w:
                continue

            moved = inp.copy()
            moved[source["mask"]] = 0
            local = source["local_mask"]
            patch = inp[r_min:r_min + oh, c_min:c_min + ow].copy()
            moved[nr:nr + oh, nc:nc + ow][local] = patch[local]

            pred = self._ct_apply(moved, hypothesis, execute_fn, train_pairs)
            if pred is None:
                severity = 0.5
                violated = "hypothesis fails when color source is moved"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=moved, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_move_source",
                severity=severity,
            ))
        return counterexamples

    def _ct_probe_swap_source_target_colors(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Swap the colors of source and target objects in the input.

        The output should reflect the new source color.
        Severity 0.7 if prediction is wrong.
        """
        counterexamples: List[Counterexample] = []
        for inp, out in train_pairs:
            kept, targets, _ = self._ct_get_objects(inp, hypothesis)
            if not kept or not targets:
                continue
            source = kept[0]
            target = targets[0]
            sc = source.get("primary_color", 1)
            tc = target.get("primary_color", 2)
            if sc == tc:
                continue

            swapped = self._remap_colors(inp, {sc: tc, tc: sc})
            baseline = self._ct_apply(inp, hypothesis, execute_fn, train_pairs)
            pred = self._ct_apply(swapped, hypothesis, execute_fn, train_pairs)
            if baseline is None:
                continue

            if pred is None:
                severity = 0.7
                violated = "hypothesis fails when source/target colors are swapped"
            elif np.array_equal(pred, baseline):
                # Output unchanged despite swap — suspicious
                severity = 0.7
                violated = (
                    "swapping source/target colors did not change output — "
                    "hypothesis may not track color provenance"
                )
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=swapped, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_swap_source_target_colors",
                severity=severity,
            ))
        return counterexamples

    def _ct_probe_duplicate_color_source(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Add a duplicate of the color source at a different position.

        For same-shape/same-size rules that require uniqueness, this should
        cause rejection or ambiguity.  For nearest_kept, it should still
        pick the nearest.  Severity 0.5 if unexpected behavior.
        """
        counterexamples: List[Counterexample] = []
        rule_type = hypothesis.get("parameters", hypothesis).get("rule_type", "")
        for inp, out in train_pairs:
            kept, targets, _ = self._ct_get_objects(inp, hypothesis)
            if not kept:
                continue
            source = kept[0]
            local = source.get("local_mask")
            if local is None:
                continue
            oh, ow = local.shape
            slot = self._find_empty_slot(inp, max(oh, ow))
            if slot is None:
                continue
            r, c = slot
            duped = inp.copy()
            bbox = source["bbox"]
            r_min, c_min = bbox[0], bbox[1]
            paste_h = min(oh, inp.shape[0] - r)
            paste_w = min(ow, inp.shape[1] - c)
            sub = local[:paste_h, :paste_w]
            patch = inp[r_min:r_min + paste_h, c_min:c_min + paste_w].copy()
            duped[r:r + paste_h, c:c + paste_w][sub] = patch[sub]

            baseline = self._ct_apply(inp, hypothesis, execute_fn, train_pairs)
            pred = self._ct_apply(duped, hypothesis, execute_fn, train_pairs)
            if baseline is None:
                continue

            if rule_type in ("same_shape", "same_size"):
                # Duplicate creates ambiguity for shape/size matching
                if pred is not None and np.array_equal(pred, baseline):
                    severity = 0.5
                    violated = (
                        "duplicate source ignored by same_shape/same_size rule — "
                        "ambiguity not detected"
                    )
                else:
                    severity = 0.0
                    violated = ""
            elif rule_type == "nearest_kept":
                # Should still pick the nearest one
                if pred is None:
                    severity = 0.5
                    violated = "nearest_kept rule fails with duplicate source"
                else:
                    severity = 0.0
                    violated = ""
            else:
                if pred is None:
                    severity = 0.5
                    violated = "hypothesis fails with duplicate color source"
                else:
                    severity = 0.0
                    violated = ""
            counterexamples.append(Counterexample(
                input_grid=duped, expected_output=baseline,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_duplicate_color_source",
                severity=severity,
            ))
        return counterexamples

    def _ct_probe_remove_color_source(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Remove the color source object.

        The hypothesis should fail (return None) since there is no source
        to derive color from.  Severity 0.3 if it still produces output
        (means it is not really using the source).
        """
        counterexamples: List[Counterexample] = []
        for inp, out in train_pairs:
            kept, targets, _ = self._ct_get_objects(inp, hypothesis)
            if not kept:
                continue
            source = kept[0]
            removed = inp.copy()
            removed[source["mask"]] = 0

            pred = self._ct_apply(removed, hypothesis, execute_fn, train_pairs)
            if pred is not None:
                severity = 0.3
                violated = (
                    "hypothesis still produces output with color source removed — "
                    "may not truly depend on the source"
                )
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=removed, expected_output=None,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_remove_color_source",
                severity=severity,
            ))
        return counterexamples

    def _ct_probe_change_neighbor_color(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Change the color of a neighbor of the target (not the source).

        For neighbor-based rules, this may change the outcome.  For others
        it should not.  Severity 0.4 if unexpected.
        """
        counterexamples: List[Counterexample] = []
        rule_type = hypothesis.get("parameters", hypothesis).get("rule_type", "")
        for inp, out in train_pairs:
            kept, targets, _ = self._ct_get_objects(inp, hypothesis)
            if not targets:
                continue
            target = targets[0]
            bbox = target["bbox"]
            tr = int(target.get("center_r", bbox[0]))
            tc = int(target.get("center_c", bbox[1]))
            h, w = inp.shape

            # Find a non-zero neighbor cell that is NOT part of any kept object
            kept_mask = np.zeros_like(inp, dtype=bool)
            for k in kept:
                kept_mask |= k["mask"]

            changed = False
            perturbed = inp.copy()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = tr + dr, tc + dc
                if 0 <= nr < h and 0 <= nc < w and not kept_mask[nr, nc]:
                    old_val = perturbed[nr, nc]
                    new_val = (old_val % 9) + 1
                    perturbed[nr, nc] = new_val
                    changed = True
                    break
            if not changed:
                continue

            baseline = self._ct_apply(inp, hypothesis, execute_fn, train_pairs)
            pred = self._ct_apply(perturbed, hypothesis, execute_fn, train_pairs)
            if baseline is None:
                continue

            if rule_type == "neighbor":
                # Neighbor rule — changing a neighbor MAY legitimately change output
                if pred is None:
                    severity = 0.4
                    violated = "neighbor rule fails when neighbor color changes"
                else:
                    severity = 0.0
                    violated = ""
            else:
                # Non-neighbor rule — neighbor color change should not matter
                if pred is None:
                    severity = 0.4
                    violated = "non-neighbor rule fails when neighbor color changes"
                elif not np.array_equal(pred, baseline):
                    severity = 0.4
                    violated = "neighbor color change unexpectedly altered output for non-neighbor rule"
                else:
                    severity = 0.0
                    violated = ""
            counterexamples.append(Counterexample(
                input_grid=perturbed, expected_output=baseline,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_change_neighbor_color",
                severity=severity,
            ))
        return counterexamples

    def _ct_probe_add_competing_same_shape(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Add another object with the same shape as the color source but
        different color.

        For same-shape rules, this creates ambiguity.
        Severity 0.6 if hypothesis doesn't handle it.
        """
        counterexamples: List[Counterexample] = []
        rule_type = hypothesis.get("parameters", hypothesis).get("rule_type", "")
        for inp, out in train_pairs:
            kept, targets, _ = self._ct_get_objects(inp, hypothesis)
            if not kept:
                continue
            source = kept[0]
            local = source.get("local_mask")
            if local is None:
                continue
            oh, ow = local.shape
            slot = self._find_empty_slot(inp, max(oh, ow))
            if slot is None:
                continue
            r, c = slot
            new_color = (source.get("primary_color", 1) % 9) + 1

            augmented = inp.copy()
            paste_h = min(oh, inp.shape[0] - r)
            paste_w = min(ow, inp.shape[1] - c)
            sub = local[:paste_h, :paste_w]
            augmented[r:r + paste_h, c:c + paste_w][sub] = new_color

            baseline = self._ct_apply(inp, hypothesis, execute_fn, train_pairs)
            pred = self._ct_apply(augmented, hypothesis, execute_fn, train_pairs)
            if baseline is None:
                continue

            if rule_type == "same_shape":
                # Same-shape rule now has two candidates — ambiguity
                if pred is not None and np.array_equal(pred, baseline):
                    severity = 0.6
                    violated = (
                        "same_shape rule ignores competing same-shape object — "
                        "ambiguity not detected"
                    )
                elif pred is None:
                    severity = 0.0
                    violated = ""
                else:
                    # Output changed, which is a reasonable response
                    severity = 0.0
                    violated = ""
            else:
                # For non-same-shape rules, this extra object should not matter
                if pred is None:
                    severity = 0.6
                    violated = "hypothesis fails with competing same-shape distractor"
                elif not np.array_equal(pred, baseline):
                    severity = 0.6
                    violated = "competing same-shape object changed output for non-same-shape rule"
                else:
                    severity = 0.0
                    violated = ""
            counterexamples.append(Counterexample(
                input_grid=augmented, expected_output=baseline,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_add_competing_same_shape",
                severity=severity,
            ))
        return counterexamples

    def _ct_probe_background_color_perturbation(
        self, train_pairs, hypothesis, execute_fn
    ) -> List[Counterexample]:
        """Change some background (0) cells to a new color.

        Should not affect the color-transfer rule.
        Severity 0.3 if hypothesis fails.
        """
        counterexamples: List[Counterexample] = []
        for inp, out in train_pairs:
            h, w = inp.shape
            bg_cells = list(zip(*np.where(inp == 0)))
            if len(bg_cells) < 2:
                continue
            # Pick a few background cells to perturb
            n_perturb = min(3, len(bg_cells))
            chosen = self.rng.sample(bg_cells, n_perturb)
            # Use a color not present in the grid to avoid interference
            used_colors = set(int(c) for c in inp.flat if c != 0)
            available = [c for c in range(1, 10) if c not in used_colors]
            if not available:
                perturb_color = self.rng.randint(1, 9)
            else:
                perturb_color = self.rng.choice(available)

            perturbed = inp.copy()
            for pr, pc in chosen:
                perturbed[pr, pc] = perturb_color

            baseline = self._ct_apply(inp, hypothesis, execute_fn, train_pairs)
            pred = self._ct_apply(perturbed, hypothesis, execute_fn, train_pairs)
            if baseline is None:
                continue

            if pred is None:
                severity = 0.3
                violated = "hypothesis fails with background color perturbation"
            elif not np.array_equal(pred, baseline):
                severity = 0.3
                violated = "background perturbation changed color-transfer output"
            else:
                severity = 0.0
                violated = ""
            counterexamples.append(Counterexample(
                input_grid=perturbed, expected_output=baseline,
                violated_invariant=violated,
                target_hypothesis="color_transfer",
                counterexample_type="ct_background_color_perturbation",
                severity=severity,
            ))
        return counterexamples
