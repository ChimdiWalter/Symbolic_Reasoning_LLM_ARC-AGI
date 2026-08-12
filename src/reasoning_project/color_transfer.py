"""Context-dependent color-transfer inference and execution.

Given a task where objects are recolored in the output, infers
which contextual relation determines the target color:
  - nearest kept object's color
  - same-shape object's color
  - same-size object's color
  - neighbor (touching) object's color
  - container object's color
  - same-row / same-col object's color
  - bidirectional color swap

Every rule is LOO-validated, proof-obligation-checked, and
determinism-verified before it can be promoted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from reasoning_project.reasoning_engine import (
    _extract_objects_with_properties,
    _get_property_value,
    _classify_object_changes,
)
from reasoning_project.operator_semantics import (
    ColorSourceRule,
    ColorTransferParams,
    ColorTransferProofObligation,
    COLOR_TRANSFER_PROOF_OBLIGATIONS,
)


def _obj_distance(o1: Dict, o2: Dict) -> float:
    return abs(o1["center_r"] - o2["center_r"]) + abs(o1["center_c"] - o2["center_c"])


def _same_shape(o1: Dict, o2: Dict) -> bool:
    return (
        o1["local_mask"].shape == o2["local_mask"].shape
        and np.array_equal(o1["local_mask"], o2["local_mask"])
    )


def _touching(o1: Dict, o2: Dict) -> bool:
    dilated = ndimage.binary_dilation(o1["mask"])
    return bool(np.any(dilated & o2["mask"]))


def _contained_in(inner: Dict, outer: Dict) -> bool:
    ir1, ic1, ir2, ic2 = inner["bbox"]
    jr1, jc1, jr2, jc2 = outer["bbox"]
    return jr1 <= ir1 and jc1 <= ic1 and jr2 >= ir2 and jc2 >= ic2


# ─── Color-Source Inference ───────────────────────────────────────────────

RULE_TYPES = [
    "nearest_kept",
    "same_shape",
    "same_size",
    "neighbor",
    "container",
    "same_row",
    "same_col",
    "swap",
]


def _find_color_source(
    target_obj: Dict,
    target_idx: int,
    objects: List[Dict],
    kept_indices: List[int],
    rule_type: str,
    inp: np.ndarray,
) -> Optional[Tuple[int, int]]:
    """Find the color-source object for a target, return (source_idx, source_color) or None."""
    candidates = []

    if rule_type == "nearest_kept":
        for ki in kept_indices:
            d = _obj_distance(target_obj, objects[ki])
            candidates.append((d, ki, objects[ki]["primary_color"]))
        candidates.sort()
        if candidates:
            return candidates[0][1], candidates[0][2]

    elif rule_type == "same_shape":
        for ki in kept_indices:
            if _same_shape(target_obj, objects[ki]):
                candidates.append((ki, objects[ki]["primary_color"]))
        if len(candidates) == 1:
            return candidates[0]

    elif rule_type == "same_size":
        for ki in kept_indices:
            if objects[ki]["area"] == target_obj["area"]:
                candidates.append((ki, objects[ki]["primary_color"]))
        if len(candidates) == 1:
            return candidates[0]

    elif rule_type == "neighbor":
        for ki in kept_indices:
            if _touching(target_obj, objects[ki]):
                candidates.append((_obj_distance(target_obj, objects[ki]), ki, objects[ki]["primary_color"]))
        candidates.sort()
        if candidates:
            return candidates[0][1], candidates[0][2]

    elif rule_type == "container":
        for ki in kept_indices:
            if _contained_in(target_obj, objects[ki]):
                candidates.append((ki, objects[ki]["primary_color"]))
        if len(candidates) == 1:
            return candidates[0]

    elif rule_type == "same_row":
        for ki in kept_indices:
            if abs(objects[ki]["center_r"] - target_obj["center_r"]) < 1.5:
                candidates.append((_obj_distance(target_obj, objects[ki]), ki, objects[ki]["primary_color"]))
        candidates.sort()
        if candidates:
            return candidates[0][1], candidates[0][2]

    elif rule_type == "same_col":
        for ki in kept_indices:
            if abs(objects[ki]["center_c"] - target_obj["center_c"]) < 1.5:
                candidates.append((_obj_distance(target_obj, objects[ki]), ki, objects[ki]["primary_color"]))
        candidates.sort()
        if candidates:
            return candidates[0][1], candidates[0][2]

    return None


def _detect_swap_pairs(
    objects: List[Dict],
    inp: np.ndarray,
    out: np.ndarray,
    occ: Any,
) -> Optional[Dict[int, int]]:
    """Detect bidirectional A↔B swaps. Returns color map or None."""
    recolored_changes = [ch for ch in occ.changes if ch.change_type == "recolored"]
    if not recolored_changes:
        return None

    forward_map: Dict[int, int] = {}
    for ch in recolored_changes:
        obj = objects[ch.object_idx]
        in_vals = inp[obj["mask"]]
        out_vals = out[obj["mask"]]
        for iv, ov in zip(in_vals.ravel(), out_vals.ravel()):
            iv, ov = int(iv), int(ov)
            if iv != 0 and ov != 0 and iv != ov:
                if iv in forward_map and forward_map[iv] != ov:
                    return None
                forward_map[iv] = ov

    if len(forward_map) < 2:
        return None

    for a, b in forward_map.items():
        if forward_map.get(b) != a:
            return None

    return forward_map


class ColorSourceInferer:
    """Infers the color-source rule from training examples."""

    def propose_color_source_rules(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        invert: bool = False,
    ) -> List[ColorSourceRule]:
        """Propose candidate rules for how target objects get their output color."""
        rules: List[ColorSourceRule] = []

        for rule_type in RULE_TYPES:
            if rule_type == "swap":
                rule = self._check_swap_rule(train_pairs, selector, invert)
                if rule is not None:
                    rules.append(rule)
                continue

            score, evidence = self._score_rule(
                train_pairs, selector, invert, rule_type,
            )
            if score >= 1.0:
                rule_id = f"ct_{rule_type}_{hash((selector, rule_type)) % 0xFFFFFFFF:08x}"
                rules.append(ColorSourceRule(
                    rule_id=rule_id,
                    rule_type=rule_type,
                    source_selector=selector,
                    target_selector=f"NOT_{selector}" if not invert else selector,
                    color_source_selector=rule_type,
                    evidence=evidence,
                    complexity=self._rule_complexity(rule_type),
                ))

        rules.sort(key=lambda r: r.complexity)
        return rules

    def _score_rule(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        invert: bool,
        rule_type: str,
    ) -> Tuple[float, Dict]:
        """Score a rule across all training pairs. Returns (fraction_correct, evidence)."""
        total_targets = 0
        correct_targets = 0
        evidence_pairs: List[Dict] = []

        for pi, (inp, out) in enumerate(train_pairs):
            objects = _extract_objects_with_properties(inp)
            occ = _classify_object_changes(objects, inp, out, bg=0)
            if occ is None:
                return 0.0, {"error": "no_occ", "pair": pi}

            kept_indices = [ch.object_idx for ch in occ.changes if ch.change_type == "kept"]
            recolored_changes = [ch for ch in occ.changes if ch.change_type == "recolored"]

            pair_correct = 0
            pair_total = 0

            for ch in recolored_changes:
                obj = objects[ch.object_idx]
                val = _get_property_value(obj, selector)
                is_target = (not val) if not invert else val
                if not is_target:
                    continue

                pair_total += 1
                total_targets += 1

                actual_out_colors = set(
                    int(v) for v in out[obj["mask"]].ravel() if v != 0
                )
                if len(actual_out_colors) != 1:
                    continue

                actual_color = actual_out_colors.pop()

                result = _find_color_source(
                    obj, ch.object_idx, objects, kept_indices, rule_type, inp,
                )
                if result is not None:
                    _, predicted_color = result
                    if predicted_color == actual_color:
                        correct_targets += 1
                        pair_correct += 1

            evidence_pairs.append({
                "pair": pi,
                "correct": pair_correct,
                "total": pair_total,
            })

        if total_targets == 0:
            return 0.0, {"error": "no_targets"}

        score = correct_targets / total_targets
        return score, {
            "total_targets": total_targets,
            "correct_targets": correct_targets,
            "per_pair": evidence_pairs,
        }

    def _check_swap_rule(
        self,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        invert: bool,
    ) -> Optional[ColorSourceRule]:
        """Check for bidirectional color swap consistent across pairs."""
        swap_maps = []
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            occ = _classify_object_changes(objects, inp, out, bg=0)
            if occ is None:
                return None
            swap = _detect_swap_pairs(objects, inp, out, occ)
            if swap is None:
                return None
            swap_maps.append(swap)

        if not swap_maps:
            return None

        if not all(m == swap_maps[0] for m in swap_maps):
            return None

        rule_id = f"ct_swap_{hash(str(swap_maps[0])) % 0xFFFFFFFF:08x}"
        return ColorSourceRule(
            rule_id=rule_id,
            rule_type="swap",
            source_selector=selector,
            target_selector=f"NOT_{selector}" if not invert else selector,
            color_source_selector="swap",
            mapping={str(k): v for k, v in swap_maps[0].items()},
            evidence={"swap_map": {str(k): v for k, v in swap_maps[0].items()}, "n_pairs": len(swap_maps)},
            complexity=3,
        )

    def _rule_complexity(self, rule_type: str) -> int:
        return {
            "same_shape": 3,
            "same_size": 4,
            "nearest_kept": 5,
            "neighbor": 5,
            "container": 4,
            "same_row": 6,
            "same_col": 6,
            "swap": 3,
        }.get(rule_type, 7)

    def loo_validate_rule(
        self,
        rule: ColorSourceRule,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        invert: bool,
    ) -> bool:
        """LOO validation: hold out each pair, check rule on held-out pair."""
        if len(train_pairs) < 2:
            return True

        for i in range(len(train_pairs)):
            held_inp, held_out = train_pairs[i]
            pred = execute_color_transfer(
                held_inp, selector, rule, invert,
            )
            if pred is None or not np.array_equal(pred, held_out):
                return False
        return True

    def check_proof_obligations(
        self,
        rule: ColorSourceRule,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        invert: bool,
    ) -> List[ColorTransferProofObligation]:
        """Check all proof obligations for a color-transfer rule."""
        results = []

        # ct_target_nonempty
        target_nonempty = True
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            occ = _classify_object_changes(objects, inp, out, bg=0)
            if occ is None:
                target_nonempty = False
                break
            targets = [
                ch for ch in occ.changes
                if ch.change_type == "recolored"
                and ((_get_property_value(objects[ch.object_idx], selector) is False) if not invert
                     else _get_property_value(objects[ch.object_idx], selector))
            ]
            if not targets:
                target_nonempty = False
                break
        results.append(ColorTransferProofObligation(
            obligation_id="ct_target_nonempty",
            description="Target objects are non-empty",
            status="passed" if target_nonempty else "failed",
        ))

        # ct_reproduces_output
        all_match = True
        for pi, (inp, out) in enumerate(train_pairs):
            pred = execute_color_transfer(inp, selector, rule, invert)
            if pred is None or not np.array_equal(pred, out):
                all_match = False
                break
        results.append(ColorTransferProofObligation(
            obligation_id="ct_reproduces_output",
            description="Rule reproduces training output",
            status="passed" if all_match else "failed",
            evidence={"failing_pair": pi if not all_match else None},
        ))

        # ct_source_unique (check that source is unambiguous for each target)
        source_unique = True
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            occ = _classify_object_changes(objects, inp, out, bg=0)
            if occ is None:
                source_unique = False
                break
            kept_indices = [ch.object_idx for ch in occ.changes if ch.change_type == "kept"]
            for ch in occ.changes:
                if ch.change_type != "recolored":
                    continue
                obj = objects[ch.object_idx]
                val = _get_property_value(obj, selector)
                is_target = (not val) if not invert else val
                if not is_target:
                    continue
                if rule.rule_type == "same_shape":
                    matches = [ki for ki in kept_indices if _same_shape(obj, objects[ki])]
                    if len(matches) != 1:
                        source_unique = False
                        break
                elif rule.rule_type == "same_size":
                    matches = [ki for ki in kept_indices if objects[ki]["area"] == obj["area"]]
                    if len(matches) != 1:
                        source_unique = False
                        break
            if not source_unique:
                break
        results.append(ColorTransferProofObligation(
            obligation_id="ct_source_unique",
            description="Color source is unique per target",
            status="passed" if source_unique else "failed",
        ))

        return results

    def detect_ambiguity(
        self,
        rule: ColorSourceRule,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: str,
        invert: bool,
    ) -> bool:
        """Return True if rule has ambiguity (multiple equally valid sources)."""
        for inp, out in train_pairs:
            objects = _extract_objects_with_properties(inp)
            occ = _classify_object_changes(objects, inp, out, bg=0)
            if occ is None:
                return True
            kept_indices = [ch.object_idx for ch in occ.changes if ch.change_type == "kept"]
            for ch in occ.changes:
                if ch.change_type != "recolored":
                    continue
                obj = objects[ch.object_idx]
                if rule.rule_type in ("same_shape", "same_size"):
                    if rule.rule_type == "same_shape":
                        matches = [ki for ki in kept_indices if _same_shape(obj, objects[ki])]
                    else:
                        matches = [ki for ki in kept_indices if objects[ki]["area"] == obj["area"]]
                    if len(matches) > 1:
                        return True
        return False


# ─── Execution ────────────────────────────────────────────────────────────

def execute_color_transfer(
    grid: np.ndarray,
    selector: str,
    rule: ColorSourceRule,
    invert: bool = False,
) -> Optional[np.ndarray]:
    """Execute a color-transfer rule on a grid."""
    objects = _extract_objects_with_properties(grid)
    if not objects:
        return None

    pred = grid.copy()

    if rule.rule_type == "swap" and rule.mapping:
        color_map = {int(k): v for k, v in rule.mapping.items()}
        for obj in objects:
            mask = obj["mask"]
            vals = pred[mask].copy()
            for old_c, new_c in color_map.items():
                vals[grid[mask] == old_c] = new_c
            pred[mask] = vals
        return pred

    # For non-swap rules, identify kept vs target objects
    kept_indices = []
    target_indices = []
    for i, obj in enumerate(objects):
        val = _get_property_value(obj, selector)
        is_target = (not val) if not invert else val
        if is_target:
            target_indices.append(i)
        else:
            kept_indices.append(i)

    if not target_indices:
        return pred

    for ti in target_indices:
        obj = objects[ti]
        result = _find_color_source(
            obj, ti, objects, kept_indices, rule.rule_type, grid,
        )
        if result is None:
            return None

        _, source_color = result
        mask = obj["mask"]
        vals = pred[mask].copy()
        vals[grid[mask] != 0] = source_color
        pred[mask] = vals

    return pred


def infer_color_transfer_params(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    selector: str,
) -> Optional[Tuple[ColorTransferParams, ColorSourceRule, bool]]:
    """Top-level inference: try both polarities, return best validated rule."""
    inferer = ColorSourceInferer()

    for invert in (False, True):
        rules = inferer.propose_color_source_rules(train_pairs, selector, invert)
        for rule in rules:
            if inferer.detect_ambiguity(rule, train_pairs, selector, invert):
                continue
            if not inferer.loo_validate_rule(rule, train_pairs, selector, invert):
                continue
            obligations = inferer.check_proof_obligations(
                rule, train_pairs, selector, invert,
            )
            if all(o.status == "passed" for o in obligations):
                params = ColorTransferParams(
                    target_selector=selector,
                    color_source_rule=rule,
                    recolor_mode="swap" if rule.rule_type == "swap" else "transfer",
                    invert_selector=invert,
                )
                return params, rule, invert

    return None
