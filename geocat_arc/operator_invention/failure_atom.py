"""Failure atom — stores near-solved failure information."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np


@dataclass
class FailureAtom:
    task_id: str
    candidate_program_repr: str
    predicted_outputs: list[list[list[int]]]
    target_outputs: list[list[list[int]]]
    cell_error_maps: list[np.ndarray] = field(default_factory=list)
    error_rate: float = 0.0
    failure_distribution: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_prediction(
        cls,
        task_id: str,
        program_repr: str,
        predicted: list[list[list[int]]],
        target: list[list[list[int]]],
    ) -> FailureAtom:
        error_maps = []
        total_cells = 0
        total_errors = 0

        for pred, tgt in zip(predicted, target):
            pa = np.array(pred, dtype=np.int32)
            ta = np.array(tgt, dtype=np.int32)
            if pa.shape != ta.shape:
                min_h = min(pa.shape[0], ta.shape[0])
                min_w = min(pa.shape[1], ta.shape[1])
                emap = np.ones(ta.shape, dtype=bool)
                emap[:min_h, :min_w] = pa[:min_h, :min_w] != ta[:min_h, :min_w]
            else:
                emap = pa != ta
            error_maps.append(emap)
            total_cells += ta.size
            total_errors += int(np.sum(emap))

        error_rate = total_errors / total_cells if total_cells > 0 else 1.0

        failure_dist = {
            "missing_operator": 0.5,
            "wrong_parameter": 0.25,
            "wrong_object_binding": 0.15,
            "perception_failure": 0.10,
        }
        if error_rate < 0.2:
            failure_dist["wrong_parameter"] = 0.6
            failure_dist["missing_operator"] = 0.2
        elif error_rate > 0.8:
            failure_dist["missing_operator"] = 0.7

        return cls(
            task_id=task_id,
            candidate_program_repr=program_repr,
            predicted_outputs=predicted,
            target_outputs=target,
            cell_error_maps=error_maps,
            error_rate=error_rate,
            failure_distribution=failure_dist,
        )
