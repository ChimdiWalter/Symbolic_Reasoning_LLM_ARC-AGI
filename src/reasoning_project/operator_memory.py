"""Operator memory: stores verified operator schemas for retrieval and reuse.

Every stored operator has a source task, proof obligations met, certificate path,
parameter template, domain signature, and reusable abstract operator type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StoredOperator:
    task_id: str
    family: str
    selector: Optional[str]
    hypothesis: Any
    certificate_path: Optional[str]
    parameter_template: Dict[str, Any] = field(default_factory=dict)
    domain_signature: Optional[str] = None
    abstract_type: Optional[str] = None
    proof_obligations_met: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None


class OperatorMemory:
    """Store and retrieve verified operator schemas."""

    def __init__(self):
        self._store: List[StoredOperator] = []
        self._by_task: Dict[str, List[StoredOperator]] = {}
        self._by_family: Dict[str, List[StoredOperator]] = {}

    def store(
        self,
        task_id: str,
        family: str,
        selector: Optional[str] = None,
        hypothesis: Any = None,
        certificate_path: Optional[str] = None,
        parameter_template: Optional[Dict[str, Any]] = None,
        domain_signature: Optional[str] = None,
        abstract_type: Optional[str] = None,
        proof_obligations_met: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
    ) -> StoredOperator:
        op = StoredOperator(
            task_id=task_id,
            family=family,
            selector=selector,
            hypothesis=hypothesis,
            certificate_path=certificate_path,
            parameter_template=parameter_template or {},
            domain_signature=domain_signature,
            abstract_type=abstract_type,
            proof_obligations_met=proof_obligations_met or [],
            embedding=embedding,
        )
        self._store.append(op)
        self._by_task.setdefault(task_id, []).append(op)
        self._by_family.setdefault(family, []).append(op)
        return op

    def get_by_task(self, task_id: str) -> List[Dict[str, Any]]:
        ops = self._by_task.get(task_id, [])
        return [self._to_dict(op) for op in ops]

    def get_by_family(self, family: str) -> List[Dict[str, Any]]:
        ops = self._by_family.get(family, [])
        return [self._to_dict(op) for op in ops]

    def get_by_embedding(self, query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        scored = []
        for op in self._store:
            if op.embedding is not None:
                dist = sum((a - b) ** 2 for a, b in zip(query_embedding, op.embedding)) ** 0.5
                scored.append((dist, op))
        scored.sort(key=lambda x: x[0])
        return [self._to_dict(op) for _, op in scored[:k]]

    def get_by_domain_morphism(self, domain_signature: str) -> List[Dict[str, Any]]:
        ops = [op for op in self._store if op.domain_signature == domain_signature]
        return [self._to_dict(op) for op in ops]

    def get_all(self) -> List[Dict[str, Any]]:
        return [self._to_dict(op) for op in self._store]

    def __len__(self) -> int:
        return len(self._store)

    def _to_dict(self, op: StoredOperator) -> Dict[str, Any]:
        return {
            "task_id": op.task_id,
            "family": op.family,
            "selector": op.selector,
            "hypothesis": op.hypothesis,
            "certificate_path": op.certificate_path,
            "parameter_template": op.parameter_template,
            "domain_signature": op.domain_signature,
            "abstract_type": op.abstract_type,
            "proof_obligations_met": op.proof_obligations_met,
        }

    def store_with_schema(
        self,
        task_id: str,
        family: str,
        selector: Optional[str] = None,
        hypothesis: Any = None,
        certificate_path: Optional[str] = None,
        execute_fn_name: Optional[str] = None,
        operator_schema: Optional[Dict[str, Any]] = None,
        parameter_template: Optional[Dict[str, Any]] = None,
        proof_obligations_met: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
    ) -> StoredOperator:
        """Store operator with executable schema for future retrieval."""
        combined_template = parameter_template or {}
        if execute_fn_name:
            combined_template["execute_fn_name"] = execute_fn_name
        if operator_schema:
            combined_template["operator_schema"] = operator_schema
        return self.store(
            task_id=task_id,
            family=family,
            selector=selector,
            hypothesis=hypothesis,
            certificate_path=certificate_path,
            parameter_template=combined_template,
            proof_obligations_met=proof_obligations_met,
            embedding=embedding,
        )
