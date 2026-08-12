"""Registry for promoted (verified) operators."""
from __future__ import annotations
import json
from pathlib import Path
from .invented_operator import InventedOperator


class PromotionError(Exception):
    pass


class PromotionRegistry:
    def __init__(self):
        self._promoted: dict[str, tuple[InventedOperator, dict]] = {}

    def register(self, operator: InventedOperator, certificate: dict) -> None:
        if not certificate.get("verified", False):
            raise PromotionError(
                f"Cannot promote operator '{operator.name}': certificate not verified"
            )
        operator.verified = True
        self._promoted[operator.name] = (operator, certificate)

    def is_promoted(self, name: str) -> bool:
        return name in self._promoted

    def get_promoted(self) -> list[InventedOperator]:
        return [op for op, _ in self._promoted.values()]

    def get_certificate(self, name: str) -> dict | None:
        entry = self._promoted.get(name)
        return entry[1] if entry else None

    def save(self, path: str | Path) -> None:
        data = {}
        for name, (op, cert) in self._promoted.items():
            data[name] = {"operator": op.to_dict(), "certificate": cert}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str | Path) -> None:
        with open(path) as f:
            data = json.load(f)
        for name, entry in data.items():
            op_dict = entry["operator"]
            op = InventedOperator(
                name=op_dict["name"],
                input_types=op_dict["input_types"],
                output_type=op_dict["output_type"],
                preconditions=op_dict["preconditions"],
                postconditions=op_dict["postconditions"],
                source_cluster_ids=op_dict.get("source_cluster_ids", []),
                verified=True,
            )
            self._promoted[name] = (op, entry["certificate"])

    def __len__(self) -> int:
        return len(self._promoted)
