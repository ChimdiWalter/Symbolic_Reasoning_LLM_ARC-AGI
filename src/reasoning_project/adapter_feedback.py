"""AdapterGenesis feedback from near-solved failure clusters.

Pipeline:
    NearSolvedMemory clusters
    → classify failure as object_schema / relation_algebra / property_library / perception_view
    → ask AdapterGenesis to synthesize/repair the adapter
    → validate repaired adapter with StructuralReasoner + LOO + active falsification
    → store repaired adapter in AdapterMemory

Failure-to-adapter mapping:
    no_objects          → object schema failure
    wrong_objects       → object decomposition / view failure
    no_discrimination   → property library failure
    wrong_reconstruction→ operator / schema failure
    partial_match       → relation / operator failure
"""
from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from reasoning_project.reasoning_engine import (
    DomainAdapter,
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
    _classify_kept_removed,
    _extract_objects_with_properties,
)
from reasoning_project.adapter_genesis import (
    AdapterGenesis,
    AdapterMemory,
    AdapterValidator,
    AdapterRepairer,
    DomainSignatureExtractor,
    ObjectSchemaProposer,
    PropertyLibraryProposer,
    RelationAlgebraProposer,
    SynthesizedAdapter,
    ValidationResult,
)
from reasoning_project.active_falsifier import ActiveFalsifier, FalsificationResult
from reasoning_project.near_solved_memory import NearSolvedMemory, NearSolvedTaskState
from reasoning_project.events import ReasoningEventLog


# ═══════════════════════════════════════════════════════════════════════════
# FAILURE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════

FAILURE_TO_ADAPTER_COMPONENT = {
    "no_objects": "object_schema",
    "wrong_objects": "perception_view",
    "no_discrimination": "property_library",
    "wrong_reconstruction": "operator_schema",
    "partial_match": "relation_algebra",
}


@dataclass
class FailureCluster:
    cluster_id: str
    adapter_component: str
    task_ids: List[str]
    failure_type: str
    representative_state: NearSolvedTaskState
    size: int = 0

    def __post_init__(self):
        self.size = len(self.task_ids)


@dataclass
class AdapterRepairResult:
    cluster_id: str
    adapter_component: str
    success: bool
    adapter: Optional[SynthesizedAdapter] = None
    validation: Optional[ValidationResult] = None
    falsification: Optional[FalsificationResult] = None
    tasks_solved: List[str] = field(default_factory=list)
    tasks_tested: int = 0
    error: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# CLUSTER BUILDER
# ═══════════════════════════════════════════════════════════════════════════

class FailureClusterBuilder:
    """Group near-solved failures by adapter component that needs repair."""

    def build_clusters(
        self, ns_mem: NearSolvedMemory,
    ) -> List[FailureCluster]:
        by_component: Dict[str, List[NearSolvedTaskState]] = {}
        for tid, state in ns_mem.states.items():
            if state.status == "solved":
                continue
            component = FAILURE_TO_ADAPTER_COMPONENT.get(
                state.failure_type, "property_library",
            )
            by_component.setdefault(component, []).append(state)

        clusters = []
        for component, states in by_component.items():
            ft_counter = Counter(s.failure_type for s in states)
            dominant_ft = ft_counter.most_common(1)[0][0]
            clusters.append(FailureCluster(
                cluster_id=f"{component}_{dominant_ft}",
                adapter_component=component,
                task_ids=[s.task_id for s in states],
                failure_type=dominant_ft,
                representative_state=states[0],
            ))
        return clusters


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTER REPAIR PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

class AdapterFeedbackPipeline:
    """Use near-solved failure clusters to repair or extend adapters."""

    def __init__(
        self,
        adapter_genesis: Optional[AdapterGenesis] = None,
        adapter_memory: Optional[AdapterMemory] = None,
        falsifier: Optional[ActiveFalsifier] = None,
        event_log: Optional[ReasoningEventLog] = None,
        max_repair_attempts: int = 3,
    ):
        self.adapter_memory = adapter_memory or AdapterMemory()
        self.genesis = adapter_genesis or AdapterGenesis(
            memory=self.adapter_memory, max_repair_attempts=max_repair_attempts,
        )
        self.falsifier = falsifier or ActiveFalsifier()
        self.event_log = event_log
        self.cluster_builder = FailureClusterBuilder()
        self.sig_extractor = DomainSignatureExtractor()
        self.validator = AdapterValidator()
        self.repairer = AdapterRepairer()
        self.schema_proposer = ObjectSchemaProposer()
        self.property_proposer = PropertyLibraryProposer()
        self.relation_proposer = RelationAlgebraProposer()

    def run(
        self,
        ns_mem: NearSolvedMemory,
        tasks: List[Dict],
        reasoner: Optional[StructuralReasoner] = None,
    ) -> Dict[str, Any]:
        task_lookup = {t["task_id"]: t for t in tasks if "task_id" in t}
        clusters = self.cluster_builder.build_clusters(ns_mem)

        if self.event_log is not None:
            self.event_log.emit(
                "FAILURE_CLUSTER_CREATED", None,
                {
                    "n_clusters": len(clusters),
                    "components": [c.adapter_component for c in clusters],
                    "sizes": [c.size for c in clusters],
                },
                module="adapter_feedback",
            )

        repair_results: List[AdapterRepairResult] = []
        for cluster in clusters:
            result = self._repair_cluster(cluster, task_lookup, reasoner)
            repair_results.append(result)

        total_solved = sum(len(r.tasks_solved) for r in repair_results)
        total_tested = sum(r.tasks_tested for r in repair_results)
        n_success = sum(1 for r in repair_results if r.success)

        return {
            "n_clusters": len(clusters),
            "n_repair_attempts": len(repair_results),
            "n_successful_repairs": n_success,
            "total_tasks_tested": total_tested,
            "total_tasks_solved": total_solved,
            "solved_task_ids": [
                tid for r in repair_results for tid in r.tasks_solved
            ],
            "cluster_details": [
                {
                    "cluster_id": r.cluster_id,
                    "component": r.adapter_component,
                    "success": r.success,
                    "tasks_tested": r.tasks_tested,
                    "tasks_solved": len(r.tasks_solved),
                    "error": r.error,
                }
                for r in repair_results
            ],
        }

    def _repair_cluster(
        self,
        cluster: FailureCluster,
        task_lookup: Dict[str, Dict],
        reasoner: Optional[StructuralReasoner],
    ) -> AdapterRepairResult:
        component = cluster.adapter_component
        task_ids = cluster.task_ids[:20]  # cap per cluster

        sample_pairs = []
        for tid in task_ids[:5]:
            task = task_lookup.get(tid)
            if task and "train_pairs" in task:
                sample_pairs.extend(task["train_pairs"][:2])
        if not sample_pairs:
            return AdapterRepairResult(
                cluster_id=cluster.cluster_id,
                adapter_component=component,
                success=False,
                error="no_sample_pairs",
            )

        try:
            if component == "object_schema":
                return self._repair_object_schema(cluster, sample_pairs, task_lookup, task_ids, reasoner)
            elif component == "perception_view":
                return self._repair_perception_view(cluster, sample_pairs, task_lookup, task_ids, reasoner)
            elif component == "property_library":
                return self._repair_property_library(cluster, sample_pairs, task_lookup, task_ids, reasoner)
            elif component == "relation_algebra":
                return self._repair_relation(cluster, sample_pairs, task_lookup, task_ids, reasoner)
            elif component == "operator_schema":
                return self._repair_operator(cluster, sample_pairs, task_lookup, task_ids, reasoner)
            else:
                return self._repair_via_genesis(cluster, sample_pairs, task_lookup, task_ids, reasoner)
        except Exception as e:
            return AdapterRepairResult(
                cluster_id=cluster.cluster_id,
                adapter_component=component,
                success=False,
                error=str(e),
            )

    def _repair_object_schema(
        self, cluster, sample_pairs, task_lookup, task_ids, reasoner,
    ) -> AdapterRepairResult:
        sig = self.sig_extractor.extract(sample_pairs)
        schemas = self.schema_proposer.propose(sig)
        return self._try_schemas(cluster, schemas, sig, sample_pairs, task_lookup, task_ids, reasoner)

    def _repair_perception_view(
        self, cluster, sample_pairs, task_lookup, task_ids, reasoner,
    ) -> AdapterRepairResult:
        sig = self.sig_extractor.extract(sample_pairs)
        schemas = self.schema_proposer.propose(sig)
        return self._try_schemas(cluster, schemas, sig, sample_pairs, task_lookup, task_ids, reasoner)

    def _repair_property_library(
        self, cluster, sample_pairs, task_lookup, task_ids, reasoner,
    ) -> AdapterRepairResult:
        sig = self.sig_extractor.extract(sample_pairs)
        schemas = self.schema_proposer.propose(sig)
        best_result = None
        best_solved = -1

        for schema in schemas[:3]:
            try:
                sample_objs = schema.extractor(sample_pairs[0][0])
            except Exception:
                continue
            if not sample_objs:
                continue
            props = self.property_proposer.propose(sig, sample_objs)
            relations = self.relation_proposer.propose(sig)
            candidate = SynthesizedAdapter(schema, props, relations, sig)
            result = self._validate_and_test(
                cluster, candidate, sample_pairs, task_lookup, task_ids, reasoner,
            )
            if len(result.tasks_solved) > best_solved:
                best_solved = len(result.tasks_solved)
                best_result = result

        if best_result is not None and best_result.success:
            return best_result
        return best_result or AdapterRepairResult(
            cluster_id=cluster.cluster_id,
            adapter_component=cluster.adapter_component,
            success=False,
            error="no_property_repair_found",
        )

    def _repair_relation(
        self, cluster, sample_pairs, task_lookup, task_ids, reasoner,
    ) -> AdapterRepairResult:
        return self._repair_via_genesis(cluster, sample_pairs, task_lookup, task_ids, reasoner)

    def _repair_operator(
        self, cluster, sample_pairs, task_lookup, task_ids, reasoner,
    ) -> AdapterRepairResult:
        return self._repair_via_genesis(cluster, sample_pairs, task_lookup, task_ids, reasoner)

    def _repair_via_genesis(
        self, cluster, sample_pairs, task_lookup, task_ids, reasoner,
    ) -> AdapterRepairResult:
        result = self.genesis.synthesize(sample_pairs)
        if result is None:
            return AdapterRepairResult(
                cluster_id=cluster.cluster_id,
                adapter_component=cluster.adapter_component,
                success=False,
                error="genesis_failed",
            )
        adapter, validation = result
        return self._validate_and_test(
            cluster, adapter, sample_pairs, task_lookup, task_ids, reasoner,
        )

    def _try_schemas(
        self, cluster, schemas, sig, sample_pairs, task_lookup, task_ids, reasoner,
    ) -> AdapterRepairResult:
        best_result = None
        best_solved = -1
        for schema in schemas[:4]:
            try:
                sample_objs = schema.extractor(sample_pairs[0][0])
            except Exception:
                continue
            if not sample_objs:
                continue
            props = self.property_proposer.propose(sig, sample_objs)
            relations = self.relation_proposer.propose(sig)
            candidate = SynthesizedAdapter(schema, props, relations, sig)
            result = self._validate_and_test(
                cluster, candidate, sample_pairs, task_lookup, task_ids, reasoner,
            )
            if len(result.tasks_solved) > best_solved:
                best_solved = len(result.tasks_solved)
                best_result = result
            if best_result is not None and best_result.success:
                return best_result

        return best_result or AdapterRepairResult(
            cluster_id=cluster.cluster_id,
            adapter_component=cluster.adapter_component,
            success=False,
            error="no_schema_worked",
        )

    def _validate_and_test(
        self,
        cluster: FailureCluster,
        adapter: SynthesizedAdapter,
        sample_pairs: List[Tuple[np.ndarray, np.ndarray]],
        task_lookup: Dict[str, Dict],
        task_ids: List[str],
        reasoner: Optional[StructuralReasoner],
    ) -> AdapterRepairResult:
        import logging
        logger = logging.getLogger(__name__)

        try:
            validation = self.validator.validate(adapter, sample_pairs)
        except Exception as e:
            return AdapterRepairResult(
                cluster_id=cluster.cluster_id,
                adapter_component=cluster.adapter_component,
                success=False,
                error=f"validation_error: {e}",
            )

        if not validation.passed:
            try:
                sig = self.sig_extractor.extract(sample_pairs)
                all_schemas = self.schema_proposer.propose(sig)
                sample_objs = adapter.extract_objects(sample_pairs[0][0]) if sample_pairs else []
                all_properties = self.property_proposer.propose(sig, sample_objs) if sample_objs else []
                repaired = self.repairer.repair(
                    adapter, validation, sample_pairs, all_schemas, all_properties,
                )
                if repaired is not None:
                    adapter = repaired
                    validation = self.validator.validate(adapter, sample_pairs)
            except Exception as e:
                logger.warning(f"Repair failed for cluster {cluster.cluster_id}: {e}")

        solved_ids = []
        tested = 0

        for tid in task_ids:
            task = task_lookup.get(tid)
            if task is None or "train_pairs" not in task:
                continue
            tested += 1
            try:
                task_reasoner = StructuralReasoner(adapter)
                result = task_reasoner.solve(
                    task["train_pairs"], task.get("test_inputs", []),
                )
                if result is not None:
                    preds, meta = result
                    test_outputs = task.get("test_outputs", [])
                    if preds and test_outputs:
                        correct = all(
                            np.array_equal(p, e)
                            for p, e in zip(preds, test_outputs)
                        )
                        if correct:
                            hyp = meta if isinstance(meta, dict) else {}
                            falsification = self.falsifier.falsify(
                                task["train_pairs"], hyp, adapter,
                            )
                            if falsification.passed:
                                solved_ids.append(tid)
            except Exception as e:
                logger.warning(f"Solve failed for task {tid}: {e}")
                continue

        success = len(solved_ids) > 0

        if success and self.event_log is not None:
            self.event_log.emit(
                "INVENTION_VALIDATED", None,
                {
                    "cluster_id": cluster.cluster_id,
                    "component": cluster.adapter_component,
                    "tasks_solved": solved_ids,
                },
                module="adapter_feedback",
            )

        return AdapterRepairResult(
            cluster_id=cluster.cluster_id,
            adapter_component=cluster.adapter_component,
            success=success,
            adapter=adapter,
            validation=validation,
            tasks_solved=solved_ids,
            tasks_tested=tested,
        )


# ═══════════════════════════════════════════════════════════════════════════
# REPORT GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def write_adapter_feedback_outputs(
    result: Dict[str, Any],
    output_dir: str,
) -> None:
    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, "repaired_adapters.json"), "w") as f:
        json.dump(result, f, indent=2, default=str)

    lines = [
        "# Adapter Repair Report\n",
        f"**Failure clusters analyzed**: {result['n_clusters']}",
        f"**Repair attempts**: {result['n_repair_attempts']}",
        f"**Successful repairs**: {result['n_successful_repairs']}",
        f"**Tasks tested**: {result['total_tasks_tested']}",
        f"**Tasks solved after repair**: {result['total_tasks_solved']}",
        "",
        "## Cluster Details\n",
        "| Cluster | Component | Success | Tested | Solved |",
        "|---------|-----------|---------|--------|--------|",
    ]
    for d in result.get("cluster_details", []):
        lines.append(
            f"| {d['cluster_id']} | {d['component']} | "
            f"{'yes' if d['success'] else 'no'} | {d['tasks_tested']} | "
            f"{d['tasks_solved']} |"
        )
    if result.get("solved_task_ids"):
        lines.append("\n## Solved Tasks\n")
        for tid in result["solved_task_ids"]:
            lines.append(f"- `{tid}`")

    with open(os.path.join(output_dir, "adapter_repair_report.md"), "w") as f:
        f.write("\n".join(lines))

    csv_lines = ["cluster_id,adapter_component,failure_type,success,tasks_solved"]
    for d in result.get("cluster_details", []):
        csv_lines.append(
            f"{d['cluster_id']},{d['component']},,"
            f"{'true' if d['success'] else 'false'},{d['tasks_solved']}"
        )
    with open(os.path.join(output_dir, "failure_cluster_to_adapter_fix.csv"), "w") as f:
        f.write("\n".join(csv_lines))
