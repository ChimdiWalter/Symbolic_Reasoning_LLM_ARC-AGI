"""Memory atom — stores a solved/failed task's distributional trace."""
from __future__ import annotations
from dataclasses import dataclass, field
from .belief_distribution import BeliefDistribution


@dataclass
class MemoryAtom:
    task_id: str
    status: str  # "solved", "near_solved", "failed"
    program_repr: str = ""
    operator_distribution: BeliefDistribution = field(default_factory=BeliefDistribution)
    predicate_distribution: BeliefDistribution = field(default_factory=BeliefDistribution)
    relation_distribution: BeliefDistribution = field(default_factory=BeliefDistribution)
    importance_weights: dict[str, float] = field(default_factory=dict)
    certificate_path: str | None = None
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "program_repr": self.program_repr,
            "operator_distribution": self.operator_distribution.to_dict(),
            "predicate_distribution": self.predicate_distribution.to_dict(),
            "relation_distribution": self.relation_distribution.to_dict(),
            "importance_weights": dict(self.importance_weights),
            "certificate_path": self.certificate_path,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MemoryAtom:
        return cls(
            task_id=d["task_id"],
            status=d["status"],
            program_repr=d.get("program_repr", ""),
            operator_distribution=BeliefDistribution.from_dict(d.get("operator_distribution", {})),
            predicate_distribution=BeliefDistribution.from_dict(d.get("predicate_distribution", {})),
            relation_distribution=BeliefDistribution.from_dict(d.get("relation_distribution", {})),
            importance_weights=d.get("importance_weights", {}),
            certificate_path=d.get("certificate_path"),
            score=d.get("score", 0.0),
        )
