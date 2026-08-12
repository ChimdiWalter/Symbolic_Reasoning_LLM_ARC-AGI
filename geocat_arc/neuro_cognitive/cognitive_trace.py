"""Cognitive trace — records observe/predict/compare/update/verify steps."""
from __future__ import annotations
import time
from dataclasses import dataclass, field


@dataclass
class CognitiveStep:
    step_type: str  # observe, predict, compare, update, verify
    data: dict
    timestamp: float = field(default_factory=time.time)


class CognitiveTrace:
    def __init__(self):
        self.steps: list[CognitiveStep] = []

    def add_observe(self, task_id: str, input_grid: list, output_grid: list) -> None:
        self.steps.append(CognitiveStep(
            step_type="observe",
            data={"task_id": task_id, "input_shape": (len(input_grid), len(input_grid[0]) if input_grid else 0),
                  "output_shape": (len(output_grid), len(output_grid[0]) if output_grid else 0)},
        ))

    def add_predict(self, program_repr: str, predicted_grid: list) -> None:
        self.steps.append(CognitiveStep(
            step_type="predict",
            data={"program": program_repr,
                  "predicted_shape": (len(predicted_grid), len(predicted_grid[0]) if predicted_grid else 0)},
        ))

    def add_compare(self, error_rate: float, num_error_regions: int) -> None:
        self.steps.append(CognitiveStep(
            step_type="compare",
            data={"error_rate": error_rate, "num_error_regions": num_error_regions},
        ))

    def add_update(self, hebbian_updates: dict, reward_updates: dict) -> None:
        self.steps.append(CognitiveStep(
            step_type="update",
            data={"hebbian_updates": hebbian_updates, "reward_updates": reward_updates},
        ))

    def add_verify(self, exact_match: bool, score: float) -> None:
        self.steps.append(CognitiveStep(
            step_type="verify",
            data={"exact_match": exact_match, "score": score},
        ))

    def to_dict(self) -> dict:
        return {
            "steps": [
                {"step_type": s.step_type, "data": s.data, "timestamp": s.timestamp}
                for s in self.steps
            ]
        }

    @property
    def num_steps(self) -> int:
        return len(self.steps)
