"""Gated Adaptive Reasoning Orchestrator — the v2 full novel pipeline controller.

Integrates all project modules as gated proposal sources feeding into a single
verified acceptance gate (LOO + falsification + certificate). Every module is a
proposal source, not a final solver.

Core principle: trigger → propose → rank → verify → certify or reject.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from reasoning_project.module_triggers import (
    should_call_adapter_genesis,
    should_call_manifold_memory,
    should_call_near_solved_memory,
    should_call_operator_memory,
    should_call_neural_advisory,
    should_call_domain_morphism,
    should_call_property_expansion,
    should_call_frontier_operators,
)
from reasoning_project.proposal_verifier import ProposalVerifier, VerificationOutcome
from reasoning_project.adapter_signature_interface import (
    AdapterSignature,
    adapter_to_signature,
    validate_signature,
)
from reasoning_project.frontier_operator_registry import FrontierOperatorRegistry
from reasoning_project.neural_proposal_interface import NeuralProposalInterface
from reasoning_project.operator_memory import OperatorMemory
from reasoning_project.property_expansion import PropertyExpansionEngine
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    ReasoningMemory,
    StructuralReasoner,
    _extract_objects_with_properties,
    _add_relational_properties,
    _classify_kept_removed,
    _classify_object_changes,
    _apply_filter,
    _apply_filter_recolor,
    _apply_filter_extract,
    _find_discriminative_property_extended,
)
from reasoning_project.manifold_memory import (
    MemoryManifold,
    ManifoldPoint,
    encode_task_signature,
    _signature_to_embedding,
)
from reasoning_project.near_solved_memory import NearSolvedMemory
from reasoning_project.active_falsifier import ActiveFalsifier
from reasoning_project.certificates import (
    ReasoningCertificate,
    CertificateBuilder,
    certificate_to_json,
)
from reasoning_project.events import ReasoningEvent, ReasoningEventLog
from reasoning_project.trace_operator_invention import (
    TraceDrivenOperatorInventor,
    CopyToPositionParams,
    MarkerRelativeCopyParams,
    execute_copy_to_position,
    execute_marker_relative_copy,
    execute_correspondence_copy,
)
from reasoning_project.color_transfer import (
    ColorSourceRule,
    execute_color_transfer,
)
from reasoning_project.adaptive_loop import AdaptiveReasoningLoop, PERCEPTION_VIEWS
from reasoning_project.operator_genesis import (
    synthesize_operators_from_train,
    _check_train_consistency,
    SynthesizedOperator,
)
from reasoning_project.adaptive_synthesizer import synthesize_adaptive


@dataclass
class TaskAnalysis:
    task_id: str
    domain: str
    adapter_status: Dict[str, Any]
    object_trace: Dict[str, Any]
    property_trace: Dict[str, Any]
    relation_trace: Dict[str, Any]
    failure_trace: Dict[str, Any]
    candidate_operator_families: List[str]
    memory_retrievals: List[Dict[str, Any]]
    neural_advisory: Optional[Dict[str, Any]]
    domain_signature: Optional[Dict[str, Any]]
    morphism_candidates: List[Dict[str, Any]]
    evidence: Dict[str, Any]


@dataclass
class ModuleProposal:
    module_name: str
    proposal_type: str
    operator_family: Optional[str]
    selector: Optional[str]
    hypothesis: Any
    confidence: float
    evidence: Dict[str, Any]
    skip_reason: Optional[str] = None


@dataclass
class OrchestratorTrace:
    task_id: str
    domain: str
    triggered_modules: List[str]
    skipped_modules: Dict[str, str]
    proposals: List[ModuleProposal]
    selected_proposal: Optional[ModuleProposal]
    verification: Optional[VerificationOutcome]
    final_status: str
    runtime_seconds: float


@dataclass
class OrchestratorConfig:
    timeout_per_task: float = 420.0
    max_proposals_per_module: int = 5
    enable_adapter_genesis: bool = True
    enable_manifold_memory: bool = True
    enable_near_solved_memory: bool = True
    enable_operator_memory: bool = True
    enable_neural_advisory: bool = True
    enable_domain_morphism: bool = True
    enable_property_expansion: bool = True
    enable_frontier_operators: bool = True
    enable_trace_invention: bool = True
    enable_static_portfolio: bool = True
    enable_operator_genesis: bool = True
    enable_adaptive_synthesizer: bool = True
    output_dir: str = "outputs/full_novel_reasoning_pipeline_v2"
    domain: str = "arc"
    rng_seed: int = 42


class GatedAdaptiveReasoningOrchestrator:
    """Main v2 pipeline controller.

    Trigger → Propose → Rank → Verify → Certify/Reject.
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self.adapter = GridDomainAdapter()
        self.memory = ReasoningMemory()
        self.manifold = MemoryManifold()
        self.near_solved = NearSolvedMemory(manifold=self.manifold)
        self.operator_memory = OperatorMemory()
        self.property_engine = PropertyExpansionEngine()
        self.frontier_registry = FrontierOperatorRegistry()
        self.neural_interface = NeuralProposalInterface()
        self.verifier = ProposalVerifier()
        self.falsifier = ActiveFalsifier(rng_seed=self.config.rng_seed)
        self.cert_builder = CertificateBuilder()
        self.event_log = ReasoningEventLog()
        self.trace_inventor = TraceDrivenOperatorInventor()
        self.traces: List[OrchestratorTrace] = []
        self._seed_memory_from_certificates()

    def _seed_memory_from_certificates(self) -> None:
        """Pre-seed operator memory and manifold from existing certificates."""
        import csv as _csv
        results_paths = [
            os.path.join(self.config.output_dir,
                         "focused_eval_after_operator_coverage_repair", "results.csv"),
            os.path.join(self.config.output_dir,
                         "focused_eval_after_executable_repair", "results.csv"),
            os.path.join(self.config.output_dir, "focused_eval", "results.csv"),
        ]
        seen = set()
        for rp in results_paths:
            if not os.path.exists(rp):
                continue
            try:
                with open(rp) as f:
                    reader = _csv.DictReader(f)
                    for row in reader:
                        if row.get("config") != "v2_full_gated_orchestrator":
                            continue
                        if row.get("v2_solved") not in ("True", "true"):
                            continue
                        tid = row.get("task_id", "")
                        if tid in seen or not tid:
                            continue
                        seen.add(tid)
                        self.operator_memory.store_with_schema(
                            task_id=tid,
                            family=row.get("operator_family", "unknown"),
                            selector=None,
                            hypothesis={"source": "certificate_seed",
                                        "family": row.get("operator_family")},
                            certificate_path=row.get("certificate", ""),
                            execute_fn_name=row.get("selected_module", ""),
                            operator_schema={"module": row.get("selected_module")},
                            proof_obligations_met=["train_consistent", "loo_passed",
                                                   "falsification_passed"],
                        )
            except Exception:
                continue

    def solve_task(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        test_outputs: Optional[List[np.ndarray]] = None,
        domain: str = "arc",
    ) -> OrchestratorTrace:
        t0 = time.time()
        self.event_log.append(ReasoningEvent(
            event_type="TASK_OBSERVED",
            task_id=task_id,
            payload={"domain": domain},
            module="orchestrator",
        ))

        analysis = self.analyze_task(task_id, train_pairs, domain)
        routed_modules = self.route_modules(analysis)

        triggered = [m for m, triggered in routed_modules.items() if triggered]
        skipped = {m: reason for m, (triggered, reason) in
                   self._route_with_reasons(analysis).items() if not triggered}

        deadline = t0 + self.config.timeout_per_task
        proposals = self.collect_proposals(analysis, triggered, train_pairs, test_inputs, deadline=deadline)
        ranked = self.rank_proposals(proposals)

        verification = None
        selected = None
        final_status = "unsolved"
        proposal_log = []

        for proposal_idx, proposal in enumerate(ranked):
            if time.time() - t0 > self.config.timeout_per_task:
                final_status = "timeout"
                break

            t_prop = time.time()
            outcome = self.verifier.verify(
                proposal, train_pairs, test_inputs, test_outputs
            )
            prop_runtime = time.time() - t_prop

            log_entry = self._build_proposal_log_entry(
                task_id, proposal_idx, proposal, outcome,
                train_pairs, test_inputs, test_outputs, prop_runtime,
            )
            proposal_log.append(log_entry)

            if outcome.accepted:
                selected = proposal
                verification = outcome
                final_status = "solved"
                self._on_promotion(task_id, proposal, outcome, train_pairs)
                break
            elif outcome.false_positive:
                final_status = "false_positive_rejected"

        if final_status == "unsolved" and proposals:
            final_status = "all_proposals_rejected"

        if final_status in ("unsolved", "all_proposals_rejected", "timeout"):
            self._on_failure(task_id, analysis, proposals, train_pairs)

        self._write_proposal_log(proposal_log)

        elapsed = time.time() - t0
        trace = OrchestratorTrace(
            task_id=task_id,
            domain=domain,
            triggered_modules=triggered,
            skipped_modules=skipped,
            proposals=proposals,
            selected_proposal=selected,
            verification=verification,
            final_status=final_status,
            runtime_seconds=elapsed,
        )
        self.traces.append(trace)
        return trace

    def analyze_task(
        self,
        task_id: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        domain: str = "arc",
    ) -> TaskAnalysis:
        adapter_status = self._check_adapter(train_pairs, domain)
        object_trace = self._extract_object_trace(train_pairs)
        property_trace = self._extract_property_trace(object_trace, train_pairs)
        relation_trace = self._extract_relation_trace(object_trace)
        failure_trace = self._build_failure_trace(
            task_id, object_trace, property_trace
        )
        candidate_families = self._infer_candidate_families(
            object_trace, property_trace, relation_trace, train_pairs
        )
        memory_retrievals = self._retrieve_from_memory(task_id, train_pairs)
        neural_advisory = None
        domain_signature = adapter_status.get("signature")
        morphism_candidates = []

        return TaskAnalysis(
            task_id=task_id,
            domain=domain,
            adapter_status=adapter_status,
            object_trace=object_trace,
            property_trace=property_trace,
            relation_trace=relation_trace,
            failure_trace=failure_trace,
            candidate_operator_families=candidate_families,
            memory_retrievals=memory_retrievals,
            neural_advisory=neural_advisory,
            domain_signature=domain_signature,
            morphism_candidates=morphism_candidates,
            evidence={},
        )

    def route_modules(self, analysis: TaskAnalysis) -> Dict[str, bool]:
        return {m: t for m, (t, _) in self._route_with_reasons(analysis).items()}

    def _route_with_reasons(self, analysis: TaskAnalysis) -> Dict[str, Tuple[bool, str]]:
        routes = {}

        if self.config.enable_adapter_genesis:
            triggered, reason = should_call_adapter_genesis(analysis)
            routes["adapter_genesis"] = (triggered, reason)
        else:
            routes["adapter_genesis"] = (False, "disabled_in_config")

        if self.config.enable_manifold_memory:
            triggered, reason = should_call_manifold_memory(analysis)
            routes["manifold_memory"] = (triggered, reason)
        else:
            routes["manifold_memory"] = (False, "disabled_in_config")

        if self.config.enable_near_solved_memory:
            triggered, reason = should_call_near_solved_memory(analysis)
            routes["near_solved_memory"] = (triggered, reason)
        else:
            routes["near_solved_memory"] = (False, "disabled_in_config")

        if self.config.enable_operator_memory:
            triggered, reason = should_call_operator_memory(analysis)
            routes["operator_memory"] = (triggered, reason)
        else:
            routes["operator_memory"] = (False, "disabled_in_config")

        if self.config.enable_neural_advisory:
            triggered, reason = should_call_neural_advisory(analysis)
            routes["neural_advisory"] = (triggered, reason)
        else:
            routes["neural_advisory"] = (False, "disabled_in_config")

        if self.config.enable_domain_morphism:
            triggered, reason = should_call_domain_morphism(analysis)
            routes["domain_morphism"] = (triggered, reason)
        else:
            routes["domain_morphism"] = (False, "disabled_in_config")

        if self.config.enable_property_expansion:
            triggered, reason = should_call_property_expansion(analysis)
            routes["property_expansion"] = (triggered, reason)
        else:
            routes["property_expansion"] = (False, "disabled_in_config")

        if self.config.enable_frontier_operators:
            triggered, reason = should_call_frontier_operators(analysis)
            routes["frontier_operators"] = (triggered, reason)
        else:
            routes["frontier_operators"] = (False, "disabled_in_config")

        if self.config.enable_operator_genesis:
            routes["operator_genesis"] = (True, "always_enabled")
        else:
            routes["operator_genesis"] = (False, "disabled_in_config")

        if self.config.enable_adaptive_synthesizer:
            routes["adaptive_synthesizer"] = (True, "always_enabled")
        else:
            routes["adaptive_synthesizer"] = (False, "disabled_in_config")

        if self.config.enable_trace_invention:
            routes["trace_invention"] = (True, "always_enabled")
        else:
            routes["trace_invention"] = (False, "disabled_in_config")

        if self.config.enable_static_portfolio:
            routes["static_portfolio"] = (True, "always_enabled")
        else:
            routes["static_portfolio"] = (False, "disabled_in_config")

        return routes

    def collect_proposals(
        self,
        analysis: TaskAnalysis,
        routed_modules: List[str],
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        deadline: Optional[float] = None,
    ) -> List[ModuleProposal]:
        proposals = []

        # Fast modules first (memory lookups + ranking, no heavy solve loops)
        if "manifold_memory" in routed_modules:
            proposals.extend(self._propose_manifold_memory(analysis, train_pairs, test_inputs))

        if "near_solved_memory" in routed_modules:
            proposals.extend(self._propose_near_solved(analysis, train_pairs, test_inputs))

        if "operator_memory" in routed_modules:
            proposals.extend(self._propose_operator_memory(analysis, train_pairs, test_inputs))

        if "property_expansion" in routed_modules:
            proposals.extend(self._propose_property_expansion(analysis, train_pairs, test_inputs))

        if "frontier_operators" in routed_modules:
            proposals.extend(self._propose_frontier_operators(analysis, train_pairs, test_inputs))

        if "neural_advisory" in routed_modules:
            proposals.extend(self._propose_neural_advisory(analysis, train_pairs, test_inputs))

        if "domain_morphism" in routed_modules:
            proposals.extend(self._propose_domain_morphism(analysis, train_pairs, test_inputs))

        if "operator_genesis" in routed_modules:
            proposals.extend(self._propose_operator_genesis(analysis, train_pairs, test_inputs))

        if "adaptive_synthesizer" in routed_modules:
            proposals.extend(self._propose_adaptive_synthesizer(analysis, train_pairs, test_inputs))

        if deadline is not None and time.time() > deadline:
            return proposals

        # Expensive modules: each runs a solve loop
        if "trace_invention" in routed_modules:
            proposals.extend(self._propose_trace_invention(analysis, train_pairs, test_inputs))

        if deadline is not None and time.time() > deadline:
            return proposals

        if "static_portfolio" in routed_modules:
            proposals.extend(self._propose_static_portfolio(analysis, train_pairs, test_inputs))

        if deadline is not None and time.time() > deadline:
            return proposals

        if "adapter_genesis" in routed_modules:
            proposals.extend(self._propose_adapter_genesis(analysis, train_pairs, test_inputs))

        return proposals

    def rank_proposals(self, proposals: List[ModuleProposal]) -> List[ModuleProposal]:
        if not proposals:
            return []
        return sorted(proposals, key=lambda p: -p.confidence)

    def emit_trace(self, trace: OrchestratorTrace, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"trace_{trace.task_id}.json")
        data = {
            "task_id": trace.task_id,
            "domain": trace.domain,
            "triggered_modules": trace.triggered_modules,
            "skipped_modules": trace.skipped_modules,
            "n_proposals": len(trace.proposals),
            "proposals": [
                {
                    "module": p.module_name,
                    "type": p.proposal_type,
                    "family": p.operator_family,
                    "selector": p.selector,
                    "confidence": p.confidence,
                }
                for p in trace.proposals
            ],
            "selected": trace.selected_proposal.module_name if trace.selected_proposal else None,
            "verification": {
                "accepted": trace.verification.accepted,
                "loo_passed": trace.verification.loo_passed,
                "falsification_passed": trace.verification.falsification_passed,
                "certificate_path": trace.verification.certificate_path,
            } if trace.verification else None,
            "final_status": trace.final_status,
            "runtime_seconds": trace.runtime_seconds,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # ─── Internal: task analysis helpers ─────────────────────────────────

    def _check_adapter(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]], domain: str
    ) -> Dict[str, Any]:
        status = {"domain": domain, "adapter_ok": True, "confidence": 1.0}
        if domain == "arc":
            try:
                inp, out = train_pairs[0]
                objects = _extract_objects_with_properties(inp)
                status["n_objects"] = len(objects)
                if len(objects) < 2:
                    status["confidence"] = 0.5
            except Exception as e:
                status["adapter_ok"] = False
                status["error"] = str(e)
        else:
            status["adapter_ok"] = False
            status["needs_genesis"] = True
        return status

    def _extract_object_trace(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Dict[str, Any]:
        trace = {"pairs": [], "n_pairs": len(train_pairs)}
        for inp, out in train_pairs:
            inp_objs = _extract_objects_with_properties(inp)
            out_objs = _extract_objects_with_properties(out)
            trace["pairs"].append({
                "n_input_objects": len(inp_objs),
                "n_output_objects": len(out_objs),
                "size_change": out.shape != inp.shape,
                "input_shape": list(inp.shape),
                "output_shape": list(out.shape),
            })
        return trace

    def _extract_property_trace(
        self, object_trace: Dict[str, Any], train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Dict[str, Any]:
        trace = {"has_discriminative_property": False, "best_property": None, "score": 0.0}
        try:
            inp, out = train_pairs[0]
            objects = _extract_objects_with_properties(inp)
            objects = _add_relational_properties(objects)
            classification = _classify_kept_removed(inp, out, objects)
            if classification and classification.get("property"):
                trace["has_discriminative_property"] = True
                trace["best_property"] = classification["property"]
                trace["score"] = classification.get("score", 1.0)
        except Exception:
            pass
        return trace

    def _extract_relation_trace(self, object_trace: Dict[str, Any]) -> Dict[str, Any]:
        return {"relations_extracted": object_trace.get("n_pairs", 0) > 0}

    def _build_failure_trace(
        self, task_id: str, object_trace: Dict[str, Any], property_trace: Dict[str, Any]
    ) -> Dict[str, Any]:
        trace = {"task_id": task_id, "failure_type": "unknown"}
        if not property_trace.get("has_discriminative_property"):
            trace["failure_type"] = "no_discriminative_property"
        elif object_trace.get("pairs") and all(
            p.get("n_input_objects", 0) < 2 for p in object_trace["pairs"]
        ):
            trace["failure_type"] = "perception_failure"
        else:
            trace["failure_type"] = "generation_failure"
        return trace

    def _infer_candidate_families(
        self,
        object_trace: Dict[str, Any],
        property_trace: Dict[str, Any],
        relation_trace: Dict[str, Any],
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> List[str]:
        families = []
        pairs = object_trace.get("pairs", [])

        has_size_change = any(p.get("size_change") for p in pairs)
        has_many_to_few = any(
            p.get("n_input_objects", 0) > p.get("n_output_objects", 1)
            for p in pairs
        )
        has_few_to_many = any(
            p.get("n_input_objects", 0) < p.get("n_output_objects", 0)
            for p in pairs
        )

        if has_size_change:
            families.extend(["crop_extract", "separator_decompose", "shape_completion"])
        if has_many_to_few:
            families.extend(["many_to_few_grouping", "filter_select"])
        if has_few_to_many:
            families.extend(["copy_to_position", "pattern_generation"])
        if property_trace.get("has_discriminative_property"):
            families.extend(["recolor", "color_transfer", "position_recolor"])
        if not property_trace.get("has_discriminative_property") and not has_size_change:
            families.extend(["shape_completion", "position_recolor"])

        families.append("trace_invention")
        return list(dict.fromkeys(families))

    def _retrieve_from_memory(
        self, task_id: str, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> List[Dict[str, Any]]:
        try:
            sig = encode_task_signature(train_pairs)
            embedding = _signature_to_embedding(sig)
            retriever = getattr(self.manifold, "nearest_in_chart", None)
            if retriever and callable(retriever):
                results = retriever(embedding, k=5)
                return [{"task_id": getattr(r, "task_id", "unknown"), "distance": getattr(r, "distance", 1.0)} for r in results]
            return []
        except Exception:
            return []

    # ─── Internal: proposal generators ───────────────────────────────────

    def _propose_adapter_genesis(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        views_to_try = []

        if not analysis.adapter_status.get("adapter_ok", True):
            views_to_try = list(PERCEPTION_VIEWS.keys())
        elif not analysis.property_trace.get("has_discriminative_property"):
            views_to_try = [v for v in PERCEPTION_VIEWS
                            if v != analysis.adapter_status.get("current_view")]

        for view_name in views_to_try:
            try:
                alt_adapter = self._get_adapter_for_view(view_name)
                isolated_memory = ReasoningMemory()
                loop = AdaptiveReasoningLoop(
                    max_iterations=3,
                    timeout_seconds=30.0,
                    memory=isolated_memory,
                    manifold=self.manifold,
                    near_solved_memory=self.near_solved,
                    event_log=self.event_log,
                )
                loop_result = loop.solve(train_pairs, test_inputs,
                                         task_id=analysis.task_id)
                if not loop_result.solved or not loop_result.predictions:
                    continue

                metadata = loop_result.hypothesis or {}
                metadata["view"] = view_name
                execute_fn = self._build_static_execute_fn(metadata, train_pairs)
                if execute_fn is None:
                    continue

                strategy = metadata.get("strategy", "genesis_resolve")
                proposals.append(ModuleProposal(
                    module_name="adapter_genesis",
                    proposal_type=f"genesis_resolve_{view_name}",
                    operator_family=strategy,
                    selector=metadata.get("property") or metadata.get("filter_prop"),
                    hypothesis={"execute": execute_fn, "strategy": strategy,
                                "view": view_name, "source": "adapter_genesis"},
                    confidence=0.65,
                    evidence={"source": "adapter_genesis", "view": view_name,
                              "strategy": strategy},
                ))
                break
            except Exception:
                continue

        # Schema-based proposal: try alternative object schemas with selector invention
        if not proposals:
            try:
                from reasoning_project.adapter_schema_proposals import (
                    AdapterSchemaProposer,
                    SCHEMA_EXTRACTORS,
                    enrich_objects,
                )
                schema_proposer = AdapterSchemaProposer()
                if schema_proposer.should_activate(
                    analysis.property_trace, analysis.failure_trace,
                    analysis.object_trace,
                ):
                    exec_sels = schema_proposer.propose_executable_selectors(train_pairs)
                    for sel in exec_sels[:3]:
                        extractor = SCHEMA_EXTRACTORS.get(sel["extractor_name"])
                        if extractor is None:
                            continue
                        sel_expr = sel["selector_expression"]

                        # Build executable using this schema's extractor
                        execute_fn = self._build_schema_selector_execute(
                            extractor, sel_expr, train_pairs,
                        )
                        if execute_fn is not None:
                            proposals.append(ModuleProposal(
                                module_name="adapter_genesis",
                                proposal_type=f"schema_{sel['schema_name']}_{sel['selector_type']}",
                                operator_family="adapter_genesis_schema",
                                selector=sel_expr,
                                hypothesis={
                                    "execute": execute_fn,
                                    "schema": sel["schema_name"],
                                    "selector": sel_expr,
                                    "source": "adapter_genesis_schema",
                                },
                                confidence=sel.get("train_fit_score", 0.5) * 0.6,
                                evidence=sel.get("evidence", {}),
                            ))
            except Exception:
                pass

        if not proposals and not analysis.adapter_status.get("adapter_ok", True):
            try:
                from reasoning_project.adapter_genesis import AdapterGenesis
                genesis = AdapterGenesis()
                adapter = genesis.synthesize(analysis.domain, train_pairs)
                if adapter:
                    for family in (analysis.candidate_operator_families or [])[:3]:
                        execute_fn = self._build_executable_for_family(
                            family, analysis, train_pairs
                        )
                        if execute_fn is not None:
                            proposals.append(ModuleProposal(
                                module_name="adapter_genesis",
                                proposal_type="genesis_family_dispatch",
                                operator_family=family,
                                selector=None,
                                hypothesis={"execute": execute_fn, "family": family,
                                            "source": "adapter_genesis_dispatch"},
                                confidence=0.4,
                                evidence={"source": "adapter_genesis_synthesis",
                                          "family": family},
                            ))
            except Exception:
                pass

        return proposals

    def _build_schema_selector_execute(self, extractor, selector_expr, train_pairs):
        """Build executable from alternative object schema + selector expression."""
        from reasoning_project.adapter_schema_proposals import enrich_objects
        from reasoning_project.reasoning_engine import _get_property_value

        for keep_val in [True, False]:
            match_all = True
            for inp, out in train_pairs:
                try:
                    objs = extractor(inp)
                    objs = enrich_objects(objs, inp)
                except Exception:
                    match_all = False
                    break
                if len(objs) < 2:
                    match_all = False
                    break
                km = [_get_property_value(o, selector_expr) == keep_val for o in objs]
                if all(km) or not any(km):
                    match_all = False
                    break
                result = inp.copy()
                for obj, k in zip(objs, km):
                    if not k:
                        result[obj["mask"]] = 0
                if not np.array_equal(result, out):
                    match_all = False
                    break
            if match_all:
                def execute_schema_filter(grid, _ext=extractor,
                                           _sel=selector_expr,
                                           _keep=keep_val):
                    from reasoning_project.adapter_schema_proposals import enrich_objects as _enrich
                    from reasoning_project.reasoning_engine import _get_property_value as _gpv
                    objs = _ext(grid)
                    objs = _enrich(objs, grid)
                    km = [_gpv(o, _sel) == _keep for o in objs]
                    if all(km) or not any(km):
                        return None
                    result = grid.copy()
                    for obj, k in zip(objs, km):
                        if not k:
                            result[obj["mask"]] = 0
                    return result
                return execute_schema_filter
        return None

    def _propose_manifold_memory(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        for retrieval in analysis.memory_retrievals:
            stored = self.operator_memory.get_by_task(retrieval.get("task_id", ""))
            if stored:
                for op in stored[:self.config.max_proposals_per_module]:
                    hyp = op.get("hypothesis")
                    family = op.get("family")
                    selector = op.get("selector")
                    execute_fn = None
                    if isinstance(hyp, dict) and callable(hyp.get("execute")):
                        execute_fn = hyp["execute"]
                    elif callable(hyp):
                        execute_fn = hyp
                    else:
                        execute_fn = self._build_executable_for_family(
                            family or "unknown", analysis, train_pairs, selector
                        )
                    dist = max(retrieval.get("distance", 1.0), 0.01)
                    if execute_fn is not None:
                        proposals.append(ModuleProposal(
                            module_name="manifold_memory",
                            proposal_type="memory_retrieved_executable",
                            operator_family=family,
                            selector=selector,
                            hypothesis={"execute": execute_fn, "family": family,
                                        "source": "manifold_memory",
                                        "source_task": retrieval.get("task_id")},
                            confidence=0.6 * (1.0 / dist),
                            evidence={"source_task": retrieval.get("task_id"),
                                      "distance": retrieval.get("distance")},
                        ))
        return proposals

    def _propose_near_solved(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        state = self.near_solved.states.get(analysis.task_id)
        if state and hasattr(state, "best_hypothesis") and state.best_hypothesis:
            proposals.append(ModuleProposal(
                module_name="near_solved_memory",
                proposal_type="resumed_near_solved",
                operator_family=getattr(state, "failure_type", None),
                selector=None,
                hypothesis=state.best_hypothesis,
                confidence=0.5,
                evidence={"source": "near_solved_resume", "task_id": analysis.task_id},
            ))
        return proposals

    def _propose_operator_memory(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        for family in analysis.candidate_operator_families:
            stored = self.operator_memory.get_by_family(family)
            for op in stored[:2]:
                hyp = op.get("hypothesis")
                execute_fn = None
                if isinstance(hyp, dict) and callable(hyp.get("execute")):
                    execute_fn = hyp["execute"]
                elif isinstance(hyp, dict):
                    execute_fn = self._rebuild_execute_from_schema(
                        family, op.get("selector"), op.get("parameter_template", {}),
                        train_pairs,
                    )
                if execute_fn is not None:
                    wrapped_hyp = {"execute": execute_fn, "source": "operator_memory",
                                   "family": family}
                    proposals.append(ModuleProposal(
                        module_name="operator_memory",
                        proposal_type="stored_operator_schema",
                        operator_family=family,
                        selector=op.get("selector"),
                        hypothesis=wrapped_hyp,
                        confidence=0.55,
                        evidence={"family": family, "source": "operator_memory",
                                  "source_task": op.get("task_id")},
                    ))
                else:
                    proposals.append(ModuleProposal(
                        module_name="operator_memory",
                        proposal_type="stored_operator_schema",
                        operator_family=family,
                        selector=op.get("selector"),
                        hypothesis=hyp,
                        confidence=0.3,
                        evidence={"family": family, "source": "operator_memory"},
                    ))
        return proposals

    def _build_executable_for_family(
        self, family: str, analysis: Optional[TaskAnalysis],
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        selector: Optional[str] = None,
    ) -> Optional[Any]:
        """Try all execution paths to build fn(grid)->grid for a given operator family.

        Order: frontier operators → property filter → static strategies → schema.
        Every advisory module should call this instead of constructing metadata-only
        hypotheses.
        """
        fake_analysis = type("_A", (), {
            "candidate_operator_families": [family],
            "object_trace": analysis.object_trace if analysis else {"pairs": []},
            "property_trace": analysis.property_trace if analysis else {},
            "task_id": analysis.task_id if analysis else "",
        })()

        triggered_ops = self.frontier_registry.get_triggered(fake_analysis)
        for _, op in triggered_ops:
            try:
                op_proposals = op.propose(fake_analysis, train_pairs, [])
                for hp in op_proposals:
                    if callable(hp.get("execute")):
                        return hp["execute"]
            except Exception:
                continue

        if selector:
            fn = self._build_property_filter_execute(selector, train_pairs)
            if fn is not None:
                return fn

        if family == "discriminative_filter" and selector:
            return self._build_property_filter_execute(selector, train_pairs)

        for strategy in [family, "discriminative_filter", "extended_recolor",
                         "transform_induction", "discriminative_change_filter"]:
            if strategy == family:
                meta = {"strategy": strategy, "property": selector,
                        "keep_when_true": True}
                fn = self._build_static_execute_fn(meta, train_pairs)
                if fn is not None:
                    return fn
                meta["keep_when_true"] = False
                fn = self._build_static_execute_fn(meta, train_pairs)
                if fn is not None:
                    return fn

        try:
            from reasoning_project.operator_schemas import ALL_SCHEMAS
            for schema in ALL_SCHEMAS:
                if family in schema.name or schema.name in family:
                    for inp, out in train_pairs:
                        result = schema.apply(inp, {})
                        if result is not None and np.array_equal(result, out):
                            def _exec_schema(grid, _s=schema):
                                return _s.apply(grid, {})
                            return _exec_schema
        except Exception:
            pass

        return None

    def _rebuild_execute_from_schema(self, family, selector, param_template, train_pairs):
        """Attempt to rebuild an executable function from stored operator schema."""
        return self._build_executable_for_family(family, None, train_pairs, selector)

    def _propose_property_expansion(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        if not analysis.property_trace.get("has_discriminative_property"):
            # First: try executable selectors (includes conjunctions/negations)
            exec_selectors = self.property_engine.find_executable_selectors(
                train_pairs, analysis.object_trace, analysis.failure_trace
            )
            for sel in exec_selectors[:self.config.max_proposals_per_module]:
                sel_expr = sel["selector_expression"]
                score = sel.get("score", 0.4)

                # Try pairing this selector with multiple operator families
                paired = False
                for builder_name, builder_fn in [
                    ("filter", self._build_property_filter_execute),
                    ("select_recolor", self._build_selector_recolor_execute),
                    ("filter_extract", self._build_selector_extract_execute),
                ]:
                    execute_fn = builder_fn(sel_expr, train_pairs)
                    if execute_fn is not None:
                        proposals.append(ModuleProposal(
                            module_name="property_expansion",
                            proposal_type=f"selector_{builder_name}",
                            operator_family=builder_name,
                            selector=sel_expr,
                            hypothesis={
                                "execute": execute_fn,
                                "property": sel_expr,
                                "selector_type": sel.get("selector_type", "single"),
                                "strategy": builder_name,
                                "score": score,
                            },
                            confidence=score * 0.72,
                            evidence={
                                "property": sel_expr,
                                "selector_type": sel.get("selector_type"),
                                "strategy": builder_name,
                            },
                        ))
                        paired = True

                if paired:
                    continue

                # Fallback: try static strategies
                for strategy in ["filter_then_extract", "extended_recolor",
                                 "discriminative_change_filter"]:
                    meta = {"strategy": ("compositional" if strategy == "filter_then_extract"
                                         else strategy),
                            "property": sel_expr, "filter_prop": sel_expr,
                            "keep_when_true": True}
                    if strategy == "filter_then_extract":
                        meta["composition"] = "filter_then_extract"
                    fn = self._build_static_execute_fn(meta, train_pairs)
                    if fn is None:
                        meta["keep_when_true"] = False
                        fn = self._build_static_execute_fn(meta, train_pairs)
                    if fn is not None:
                        proposals.append(ModuleProposal(
                            module_name="property_expansion",
                            proposal_type=f"expanded_property_{strategy}",
                            operator_family=strategy,
                            selector=sel_expr,
                            hypothesis={"execute": fn, "property": sel_expr,
                                        "strategy": strategy, "score": score},
                            confidence=score * 0.65,
                            evidence={"property": sel_expr, "strategy": strategy},
                        ))
                        break

            # Also try the original single-property path for backward compat
            if not proposals:
                expanded = self.property_engine.find_discriminative_property(
                    train_pairs, analysis.object_trace, analysis.failure_trace
                )
                for prop in expanded[:self.config.max_proposals_per_module]:
                    prop_name = prop.get("name")
                    score = prop.get("score", 0.4)
                    execute_fn = self._build_property_filter_execute(
                        prop_name, train_pairs
                    )
                    if execute_fn is not None:
                        proposals.append(ModuleProposal(
                            module_name="property_expansion",
                            proposal_type="expanded_property_filter",
                            operator_family="discriminative_filter",
                            selector=prop_name,
                            hypothesis={"execute": execute_fn, "property": prop_name,
                                        "family": prop.get("family"), "score": score},
                            confidence=score * 0.7,
                            evidence={"property": prop_name, "family": prop.get("family")},
                        ))
        return proposals

    def _propose_frontier_operators(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        triggered = self.frontier_registry.get_triggered(analysis)
        for op_name, op in triggered:
            try:
                op_proposals = op.propose(analysis, train_pairs, test_inputs)
                for hp in op_proposals[:2]:
                    proposals.append(ModuleProposal(
                        module_name="frontier_operators",
                        proposal_type=f"frontier_{op_name}",
                        operator_family=op_name,
                        selector=hp.get("selector"),
                        hypothesis=hp,
                        confidence=hp.get("confidence", 0.45),
                        evidence={"frontier_op": op_name},
                    ))
            except Exception:
                pass
        return proposals

    def _propose_neural_advisory(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        try:
            advisory = self.neural_interface.propose(analysis, train_pairs)
            if advisory is None:
                return proposals

            # Use neural routing to prioritize selector search
            if advisory.selector_type_ranking and not analysis.property_trace.get("has_discriminative_property"):
                exec_selectors = self.property_engine.find_executable_selectors(
                    train_pairs, analysis.object_trace, analysis.failure_trace,
                )
                for sel in exec_selectors[:2]:
                    sel_expr = sel["selector_expression"]
                    # Try each neural-suggested family with this selector
                    for family, score in advisory.operator_family_ranking[:2]:
                        for builder_name, builder_fn in [
                            ("filter", self._build_property_filter_execute),
                            ("select_recolor", self._build_selector_recolor_execute),
                            ("filter_extract", self._build_selector_extract_execute),
                        ]:
                            execute_fn = builder_fn(sel_expr, train_pairs)
                            if execute_fn is not None:
                                proposals.append(ModuleProposal(
                                    module_name="neural_advisory",
                                    proposal_type=f"neural_routed_{builder_name}",
                                    operator_family=family,
                                    selector=sel_expr,
                                    hypothesis={
                                        "execute": execute_fn,
                                        "family": family,
                                        "source": "neural_advisory",
                                        "neural_helped_routing": True,
                                    },
                                    confidence=score * 0.6,
                                    evidence={
                                        "source": "neural_advisory",
                                        "selector_type": sel.get("selector_type"),
                                        "neural_routing": True,
                                    },
                                ))
                                break  # one builder per family

            # Also try the original family-based approach
            if advisory.operator_family_ranking:
                for family, score in advisory.operator_family_ranking[:3]:
                    selector_hint = None
                    if advisory.selector_candidates:
                        selector_hint = advisory.selector_candidates[0][0]
                    execute_fn = self._build_executable_for_family(
                        family, analysis, train_pairs, selector_hint
                    )
                    if execute_fn is not None:
                        proposals.append(ModuleProposal(
                            module_name="neural_advisory",
                            proposal_type="neural_guided_executable",
                            operator_family=family,
                            selector=selector_hint,
                            hypothesis={"execute": execute_fn, "family": family,
                                        "source": "neural_advisory"},
                            confidence=score * 0.55,
                            evidence={"source": "neural_advisory", "raw_score": score},
                        ))
        except Exception:
            pass
        return proposals

    def _propose_domain_morphism(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        if analysis.domain != "arc" or analysis.morphism_candidates:
            try:
                for morph in analysis.morphism_candidates[:2]:
                    family = morph.get("operator_family")
                    selector = morph.get("selector")
                    if family:
                        execute_fn = self._build_executable_for_family(
                            family, analysis, train_pairs, selector
                        )
                        if execute_fn is not None:
                            proposals.append(ModuleProposal(
                                module_name="domain_morphism",
                                proposal_type="morphism_executable",
                                operator_family=family,
                                selector=selector,
                                hypothesis={"execute": execute_fn, "family": family,
                                            "source": "domain_morphism"},
                                confidence=0.45,
                                evidence={"morphism": morph.get("type"),
                                          "family": family},
                            ))
            except Exception:
                pass
        return proposals

    def _propose_operator_genesis(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        try:
            ops = synthesize_operators_from_train(train_pairs)
            for op in ops:
                tc_ok, _ = _check_train_consistency(op.execute, train_pairs)
                if not tc_ok:
                    continue
                proposals.append(ModuleProposal(
                    module_name="operator_genesis",
                    proposal_type=f"og_{op.operator_family}",
                    operator_family=op.operator_family,
                    selector=op.explanation,
                    hypothesis={"execute": op.execute, "family": op.operator_family,
                                "source": "operator_genesis"},
                    confidence=0.8,
                    evidence={"operator_id": op.operator_id,
                              "parameters": {k: (int(v) if isinstance(v, np.integer) else
                                                 float(v) if isinstance(v, np.floating) else v)
                                              for k, v in op.parameters.items()}},
                ))
        except Exception:
            pass
        return proposals

    def _propose_adaptive_synthesizer(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        proposals = []
        try:
            ops = synthesize_adaptive(train_pairs, max_depth=2, timeout_seconds=30.0)
            for op in ops:
                tc_ok, _ = _check_train_consistency(op.execute, train_pairs)
                if not tc_ok:
                    continue
                proposals.append(ModuleProposal(
                    module_name="adaptive_synthesizer",
                    proposal_type=f"adap_{op.operator_family}",
                    operator_family=op.operator_family,
                    selector=op.explanation,
                    hypothesis={"execute": op.execute, "family": op.operator_family,
                                "source": "adaptive_synthesizer"},
                    confidence=0.85,
                    evidence={"operator_id": op.operator_id,
                              "parameters": {k: (int(v) if isinstance(v, np.integer) else
                                                 float(v) if isinstance(v, np.floating) else v)
                                              for k, v in op.parameters.items()}},
                ))
        except Exception:
            pass
        return proposals

    def _propose_trace_invention(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        """Call TraceDrivenOperatorInventor.run_full_pipeline() — the v1 path.

        If the inventor validates a hypothesis (train_consistent + loo_passed),
        build a callable execute function and wrap it as a verifiable proposal.
        """
        proposals = []

        best_property = analysis.property_trace.get("best_property", "")

        if not best_property:
            ext_result = _find_discriminative_property_extended(train_pairs)
            if ext_result is not None:
                best_property = ext_result[0]

        if not best_property:
            return proposals

        trace = {
            "task_id": analysis.task_id,
            "best_property": best_property,
            "needed_operator_family": (
                analysis.candidate_operator_families[0]
                if analysis.candidate_operator_families
                else "unknown"
            ),
            "failure_type": analysis.failure_trace.get("failure_type", "unknown"),
        }

        try:
            result = self._run_with_timeout(
                self.trace_inventor.run_full_pipeline,
                timeout=300.0,
                task_id=analysis.task_id,
                train_pairs=train_pairs,
                test_inputs=test_inputs,
                trace=trace,
                test_outputs=None,
            )
        except Exception:
            return proposals
        if result is None:
            return proposals

        if not result.get("train_consistent") or not result.get("loo_passed"):
            return proposals

        operator_id = result.get("operator_id")
        if not operator_id:
            return proposals

        hypothesis_obj = self.trace_inventor.hypotheses.get(operator_id)
        if hypothesis_obj is None:
            return proposals

        execute_fn = self._build_execute_fn(hypothesis_obj, train_pairs)
        if execute_fn is None:
            return proposals

        family = hypothesis_obj.family
        proposals.append(ModuleProposal(
            module_name="trace_invention",
            proposal_type="trace_driven_operator",
            operator_family=family,
            selector=hypothesis_obj.selector_expression,
            hypothesis={"execute": execute_fn, "operator_id": operator_id, "family": family},
            confidence=0.8,
            evidence={
                "source": "run_full_pipeline",
                "family": family,
                "loo_passed": True,
                "train_consistent": True,
            },
        ))
        return proposals

    @staticmethod
    def _run_with_timeout(fn, timeout=300.0, **kwargs):
        result_q: queue.Queue = queue.Queue()

        def _worker():
            try:
                result_q.put(("ok", fn(**kwargs)))
            except Exception as exc:
                result_q.put(("err", exc))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=timeout)
        if result_q.empty():
            return None
        tag, value = result_q.get_nowait()
        if tag == "err":
            raise value
        return value

    def _build_execute_fn(self, hypothesis, train_pairs):
        """Build a callable execute(input_grid) -> output_grid from a validated hypothesis."""
        family = hypothesis.family
        params = hypothesis.parameters
        selector = hypothesis.selector_expression

        if family == "copy_to_position":
            try:
                ctp_params = CopyToPositionParams(**{
                    k: tuple(v) if k in ("displacement", "destination_point") and isinstance(v, list) else v
                    for k, v in params.items()
                    if k in CopyToPositionParams.__dataclass_fields__
                })
            except Exception:
                return None

            def execute_ctp(grid, _params=ctp_params, _tp=train_pairs):
                return execute_copy_to_position(grid, _params, _tp)
            return execute_ctp

        elif family == "marker_relative_copy_to_position":
            try:
                mr_params = MarkerRelativeCopyParams(
                    source_selector=params.get("source_selector", ""),
                    anchor_selector=params.get("anchor_selector", ""),
                    anchor_type=params.get("anchor_type", "nearest_kept"),
                    relative_rule=params.get("relative_rule", "offset_from_anchor"),
                    offset=tuple(params["offset"]) if params.get("offset") else None,
                    copy_mode=params.get("copy_mode", "move"),
                    preserve_color=params.get("preserve_color", True),
                    preserve_shape=params.get("preserve_shape", True),
                    background_color=params.get("background_color", 0),
                )
            except Exception:
                return None

            def execute_mr(grid, _params=mr_params, _tp=train_pairs):
                return execute_marker_relative_copy(grid, _params, _tp)
            return execute_mr

        elif family == "correspondence_copy_to_position":
            from reasoning_project.operator_semantics import CorrespondenceCopyParams
            try:
                corr_params = CorrespondenceCopyParams(
                    source_selector=params.get("source_selector", ""),
                    correspondence_rule_type=params.get("correspondence_rule_type", ""),
                    correspondence_rule_id=params.get("correspondence_rule_id", ""),
                    relative_displacement=tuple(params["relative_displacement"]) if params.get("relative_displacement") else None,
                    copy_mode=params.get("copy_mode", "move"),
                    preserve_shape=params.get("preserve_shape", True),
                    preserve_color=params.get("preserve_color", True),
                    allow_overlap=params.get("allow_overlap", False),
                    background_color=params.get("background_color", 0),
                    tie_breaker=params.get("tie_breaker"),
                )
            except Exception:
                return None

            def execute_corr(grid, _params=corr_params, _tp=train_pairs):
                return execute_correspondence_copy(grid, _params, _tp)
            return execute_corr

        elif family == "variable_destination_copy":
            try:
                from reasoning_project.destination_policy import (
                    infer_variable_destination_params,
                    execute_variable_destination_copy,
                )
                vdp_result = infer_variable_destination_params(
                    train_pairs, selector, keep_when_true=True,
                )
                if vdp_result is None:
                    return None
                vdp_params, _, _ = vdp_result
            except Exception:
                return None

            def execute_vdp(grid, _params=vdp_params, _tp=train_pairs):
                return execute_variable_destination_copy(grid, _params, _tp)
            return execute_vdp

        elif family == "marker_projection":
            try:
                from reasoning_project.marker_projection import (
                    infer_marker_projection_params,
                    execute_marker_projection,
                )
                mp_params = infer_marker_projection_params(
                    train_pairs, selector, keep_when_true=True,
                )
                if mp_params is None:
                    return None
            except Exception:
                return None

            def execute_mp(grid, _params=mp_params, _tp=train_pairs):
                return execute_marker_projection(grid, _params, _tp)
            return execute_mp

        elif family == "recolor_in_place":
            recolor_selector = params.get("source_selector", "")
            recolor_type = params.get("recolor_type", "")
            target_color = params.get("target_color")
            color_map = params.get("color_map")
            invert = params.get("invert_selector", False)

            def execute_rcl(grid, _sel=recolor_selector, _rt=recolor_type,
                            _tc=target_color, _cm=color_map, _inv=invert):
                return self.trace_inventor._apply_recolor(
                    grid, _sel, _rt, _tc, _cm, _inv,
                )
            return execute_rcl

        elif family == "color_transfer_recolor":
            rule = ColorSourceRule(
                rule_id=params.get("rule_id", ""),
                rule_type=params.get("rule_type", ""),
                source_selector=params.get("source_selector", ""),
                target_selector="",
                color_source_selector=params.get("rule_type", ""),
                mapping=params.get("mapping"),
            )
            ctr_selector = params.get("source_selector", "")
            invert = params.get("invert_selector", False)

            def execute_ctr(grid, _sel=ctr_selector, _rule=rule, _inv=invert):
                return execute_color_transfer(grid, _sel, _rule, _inv)
            return execute_ctr

        return None

    def _propose_static_portfolio(
        self, analysis: TaskAnalysis, train_pairs, test_inputs
    ) -> List[ModuleProposal]:
        """Run the v1 static portfolio (AdaptiveReasoningLoop) and wrap the result."""
        proposals = []

        try:
            isolated_memory = ReasoningMemory()
            loop = AdaptiveReasoningLoop(
                max_iterations=8,
                timeout_seconds=120.0,
                memory=isolated_memory,
                manifold=self.manifold,
                near_solved_memory=self.near_solved,
                event_log=self.event_log,
            )
            loop_result = loop.solve(train_pairs, test_inputs, task_id=analysis.task_id)
        except Exception:
            return proposals

        if not loop_result.solved or not loop_result.predictions:
            return proposals

        metadata = loop_result.hypothesis or {}
        strategy = metadata.get("strategy", "")
        execute_fn = self._build_static_execute_fn(metadata, train_pairs)
        if execute_fn is None:
            return proposals

        proposals.append(ModuleProposal(
            module_name="static_portfolio",
            proposal_type=f"static_{strategy}",
            operator_family=strategy,
            selector=metadata.get("property") or metadata.get("filter_prop"),
            hypothesis={"execute": execute_fn, "strategy": strategy, "metadata": metadata},
            confidence=0.9,
            evidence={"source": "static_portfolio", "strategy": strategy},
        ))

        if strategy == "compositional" and metadata.get("composition") == "filter_then_extract":
            conj_proposals = self._propose_static_conjunction_fallback(
                train_pairs, test_inputs, metadata.get("view"),
            )
            proposals.extend(conj_proposals)

        return proposals

    def _propose_static_conjunction_fallback(
        self, train_pairs, test_inputs, view,
    ) -> List[ModuleProposal]:
        """Try conjunction_extract as fallback when filter_then_extract found a single property."""
        adapter = self._get_adapter_for_view(view)
        reasoner = StructuralReasoner(adapter, memory=ReasoningMemory())
        result = reasoner._try_conjunction_extract(train_pairs, test_inputs)
        if result is None:
            return []
        predictions, conj_meta = result
        conj_meta = dict(conj_meta)
        conj_meta["view"] = view
        execute_fn = self._build_static_execute_fn(conj_meta, train_pairs)
        if execute_fn is None:
            return []
        return [ModuleProposal(
            module_name="static_portfolio",
            proposal_type="static_compositional_conjunction",
            operator_family="compositional",
            selector=str(conj_meta.get("conjunction")),
            hypothesis={"execute": execute_fn, "strategy": "compositional",
                        "metadata": conj_meta},
            confidence=0.85,
            evidence={"source": "static_portfolio", "strategy": "conjunction_extract"},
        )]

    def _build_static_execute_fn(self, metadata, train_pairs):
        """Build a callable from StructuralReasoner/AdaptiveReasoningLoop metadata."""
        strategy = metadata.get("strategy", "")
        view = metadata.get("view")
        adapter = self._get_adapter_for_view(view)
        reasoner = StructuralReasoner(adapter, memory=ReasoningMemory())

        if strategy == "discriminative_filter":
            prop = metadata.get("property")
            keep = metadata.get("keep_when_true")
            if prop is None or keep is None:
                return None

            def execute_filter(grid, _prop=prop, _keep=keep, _a=adapter):
                objects = _a.extract_objects(grid)
                km = [_a.get_property(o, _prop) == _keep for o in objects]
                if all(km) or not any(km):
                    return None
                result = grid.copy()
                for obj, k in zip(objects, km):
                    if not k:
                        result[obj["mask"]] = 0
                return result
            return execute_filter

        elif strategy == "extended_recolor":
            prop = metadata.get("property")
            keep = metadata.get("keep_when_true")
            recolor_map = metadata.get("recolor_map")
            if prop is None or keep is None or recolor_map is None:
                return None

            def execute_recolor(grid, _prop=prop, _keep=keep, _rm=recolor_map, _a=adapter):
                objects = _a.extract_objects(grid)
                result = grid.copy()
                for obj in objects:
                    val = _a.get_property(obj, _prop)
                    if val == _keep:
                        old_c = obj.get("primary_color", 0)
                        if old_c in _rm:
                            result[obj["mask"]] = _rm[old_c]
                    else:
                        result[obj["mask"]] = 0
                return result
            return execute_recolor

        elif strategy == "compositional" and metadata.get("composition") == "filter_then_extract":
            prop = metadata.get("filter_prop")
            keep = metadata.get("keep_when_true")
            if prop is None or keep is None:
                return None

            def execute_filt_extract(grid, _prop=prop, _keep=keep, _a=adapter):
                objects = _a.extract_objects(grid)
                km = [_a.get_property(o, _prop) == _keep for o in objects]
                if all(km) or not any(km):
                    return None
                return _a.reconstruct_extracted(grid, objects, km)
            return execute_filt_extract

        elif strategy == "compositional" and metadata.get("composition") == "conjunction_extract":
            conj = metadata.get("conjunction")
            keep = metadata.get("keep_when_true")
            if not conj or len(conj) < 2 or keep is None:
                return None
            if isinstance(conj, str):
                conj = [s.strip().strip("'\"") for s in conj.strip("[]").split(",")]
            p1, p2 = conj[0], conj[1]

            def execute_conj_extract(grid, _p1=p1, _p2=p2, _keep=keep, _a=adapter):
                objects = _a.extract_objects(grid)
                km = [(_a.get_property(o, _p1) and _a.get_property(o, _p2)) == _keep
                      for o in objects]
                if all(km) or not any(km):
                    return None
                return _a.reconstruct_extracted(grid, objects, km)
            return execute_conj_extract

        elif strategy == "schema":
            schema_name = metadata.get("schema_name")
            bindings = metadata.get("bindings", {})
            if not schema_name:
                return None
            try:
                from reasoning_project.operator_schemas import ALL_SCHEMAS
                schema = next((s for s in ALL_SCHEMAS if s.name == schema_name), None)
                if schema is None:
                    return None
            except Exception:
                return None

            def execute_schema(grid, _schema=schema, _bindings=bindings):
                return _schema.apply(grid, _bindings)
            return execute_schema

        elif strategy == "transform_induction":
            rule_type = metadata.get("rule_type")
            if not rule_type:
                return None
            full_rule = reasoner._find_relabel_rule(train_pairs)
            if full_rule is None:
                return None
            found_rule_type, full_params = full_rule

            def execute_transform(grid, _rt=found_rule_type, _p=full_params, _r=reasoner):
                return _r._apply_relabel(grid, _rt, _p)
            return execute_transform

        elif strategy == "discriminative_change_filter":
            prop = metadata.get("property")
            unchanged_when_true = metadata.get("unchanged_when_true")
            change_type = metadata.get("change_type")
            change_pattern_raw = metadata.get("change_pattern", {})
            if prop is None or unchanged_when_true is None or not change_type:
                return None
            if isinstance(change_pattern_raw, str):
                import ast
                try:
                    change_pattern_raw = ast.literal_eval(change_pattern_raw)
                except Exception:
                    return None
            change_pattern = change_pattern_raw if isinstance(change_pattern_raw, dict) else {}
            if "type" not in change_pattern:
                change_pattern["type"] = change_type

            def execute_change(grid, _prop=prop, _uwt=unchanged_when_true, _cp=change_pattern, _r=reasoner):
                return _r._apply_change_pattern(grid, _prop, _uwt, _cp)
            return execute_change

        elif strategy == "discriminative_marker_target":
            prop = metadata.get("property")
            keep = metadata.get("keep_when_true")
            if prop is None or keep is None:
                return None

            def execute_marker_target(grid, _prop=prop, _keep=keep, _a=adapter):
                objects = _a.extract_objects(grid)
                km = [_a.get_property(o, _prop) == _keep for o in objects]
                if all(km) or not any(km):
                    return None
                result = grid.copy()
                for obj, k in zip(objects, km):
                    if not k:
                        result[obj["mask"]] = 0
                return result
            return execute_marker_target

        return None

    def _build_property_filter_execute(self, prop_name, train_pairs):
        """Build an executable filter from an expanded property name.

        Tries each perception view. If the property discriminates objects and
        filtering produces the correct output on all train pairs, returns
        a callable execute(grid) -> grid.
        """
        for view_name in [None, "per_color", "monochrome", "majority_bg"]:
            adapter = self._get_adapter_for_view(view_name)
            try:
                for keep_val in [True, False]:
                    match_all = True
                    for inp, out in train_pairs:
                        objects = adapter.extract_objects(inp)
                        if len(objects) < 2:
                            match_all = False
                            break
                        km = [adapter.get_property(o, prop_name) == keep_val for o in objects]
                        if all(km) or not any(km):
                            match_all = False
                            break
                        result = inp.copy()
                        for obj, k in zip(objects, km):
                            if not k:
                                result[obj["mask"]] = 0
                        if not np.array_equal(result, out):
                            match_all = False
                            break
                    if match_all:
                        def execute_prop_filter(grid, _prop=prop_name,
                                                _keep=keep_val, _a=adapter):
                            objects = _a.extract_objects(grid)
                            km = [_a.get_property(o, _prop) == _keep for o in objects]
                            if all(km) or not any(km):
                                return None
                            result = grid.copy()
                            for obj, k in zip(objects, km):
                                if not k:
                                    result[obj["mask"]] = 0
                            return result
                        return execute_prop_filter
            except Exception:
                continue
        return None

    def _build_selector_recolor_execute(self, prop_name, train_pairs):
        """Build an executable that selects objects by property and recolors them.

        Infers a consistent recolor map from training pairs. If no consistent
        map exists, returns None.
        """
        for view_name in [None, "per_color", "monochrome", "majority_bg"]:
            adapter = self._get_adapter_for_view(view_name)
            try:
                for keep_val in [True, False]:
                    recolor_maps = []
                    match_all = True
                    for inp, out in train_pairs:
                        objects = adapter.extract_objects(inp)
                        if len(objects) < 2:
                            match_all = False
                            break
                        km = [adapter.get_property(o, prop_name) == keep_val for o in objects]
                        if all(km) or not any(km):
                            match_all = False
                            break
                        # Infer recolor map: for kept objects, old_color -> new_color
                        pair_map = {}
                        result = inp.copy()
                        for obj, k in zip(objects, km):
                            if not k:
                                result[obj["mask"]] = 0
                            else:
                                old_c = obj.get("primary_color", 0)
                                mask = obj["mask"]
                                out_colors = out[mask]
                                new_c = int(np.bincount(out_colors.flat).argmax()) if out_colors.size else old_c
                                if new_c != old_c:
                                    pair_map[old_c] = new_c
                        recolor_maps.append(pair_map)

                    if not match_all or not recolor_maps:
                        continue

                    # Check consistency of recolor maps
                    merged = {}
                    consistent = True
                    for pm in recolor_maps:
                        for oc, nc in pm.items():
                            if oc in merged and merged[oc] != nc:
                                consistent = False
                                break
                            merged[oc] = nc
                        if not consistent:
                            break
                    if not consistent or not merged:
                        continue

                    # Verify recolored output matches
                    verify_ok = True
                    for inp, out in train_pairs:
                        objects = adapter.extract_objects(inp)
                        km = [adapter.get_property(o, prop_name) == keep_val for o in objects]
                        result = inp.copy()
                        for obj, k in zip(objects, km):
                            if not k:
                                result[obj["mask"]] = 0
                            else:
                                old_c = obj.get("primary_color", 0)
                                if old_c in merged:
                                    result[obj["mask"]] = merged[old_c]
                        if not np.array_equal(result, out):
                            verify_ok = False
                            break
                    if verify_ok:
                        def execute_sel_recolor(grid, _prop=prop_name,
                                                _keep=keep_val, _rm=merged,
                                                _a=adapter):
                            objects = _a.extract_objects(grid)
                            km = [_a.get_property(o, _prop) == _keep for o in objects]
                            if all(km) or not any(km):
                                return None
                            result = grid.copy()
                            for obj, k in zip(objects, km):
                                if not k:
                                    result[obj["mask"]] = 0
                                else:
                                    old_c = obj.get("primary_color", 0)
                                    if old_c in _rm:
                                        result[obj["mask"]] = _rm[old_c]
                            return result
                        return execute_sel_recolor
            except Exception:
                continue
        return None

    def _build_selector_extract_execute(self, prop_name, train_pairs):
        """Build an executable that selects objects by property and crops output."""
        for view_name in [None, "per_color", "monochrome", "majority_bg"]:
            adapter = self._get_adapter_for_view(view_name)
            try:
                for keep_val in [True, False]:
                    match_all = True
                    for inp, out in train_pairs:
                        objects = adapter.extract_objects(inp)
                        if len(objects) < 2:
                            match_all = False
                            break
                        km = [adapter.get_property(o, prop_name) == keep_val for o in objects]
                        if all(km) or not any(km):
                            match_all = False
                            break
                        # Filter then crop
                        result = inp.copy()
                        for obj, k in zip(objects, km):
                            if not k:
                                result[obj["mask"]] = 0
                        # Crop to bounding box of non-zero
                        nz = np.argwhere(result > 0)
                        if nz.size == 0:
                            match_all = False
                            break
                        r_min, c_min = nz.min(axis=0)
                        r_max, c_max = nz.max(axis=0)
                        cropped = result[r_min:r_max+1, c_min:c_max+1]
                        if not np.array_equal(cropped, out):
                            match_all = False
                            break
                    if match_all:
                        def execute_sel_extract(grid, _prop=prop_name,
                                                _keep=keep_val, _a=adapter):
                            objects = _a.extract_objects(grid)
                            km = [_a.get_property(o, _prop) == _keep for o in objects]
                            if all(km) or not any(km):
                                return None
                            result = grid.copy()
                            for obj, k in zip(objects, km):
                                if not k:
                                    result[obj["mask"]] = 0
                            nz = np.argwhere(result > 0)
                            if nz.size == 0:
                                return None
                            r_min, c_min = nz.min(axis=0)
                            r_max, c_max = nz.max(axis=0)
                            return result[r_min:r_max+1, c_min:c_max+1]
                        return execute_sel_extract
            except Exception:
                continue
        return None

    def _get_adapter_for_view(self, view: Optional[str] = None):
        """Get the appropriate domain adapter for a perception view."""
        if view and view in PERCEPTION_VIEWS:
            return PERCEPTION_VIEWS[view]()
        return self.adapter

    # ─── Internal: post-solve/failure hooks ──────────────────────────────

    def _on_promotion(
        self,
        task_id: str,
        proposal: ModuleProposal,
        outcome: VerificationOutcome,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> None:
        self.event_log.append(ReasoningEvent(
            event_type="TASK_PROMOTED_TO_SOLVED",
            task_id=task_id,
            payload={
                "proposal_module": proposal.module_name,
                "family": proposal.operator_family,
                "certificate": outcome.certificate_path,
            },
            module="orchestrator",
        ))
        self.operator_memory.store_with_schema(
            task_id=task_id,
            family=proposal.operator_family or "unknown",
            selector=proposal.selector,
            hypothesis=proposal.hypothesis,
            certificate_path=outcome.certificate_path,
            execute_fn_name=proposal.module_name,
            operator_schema={"module": proposal.module_name,
                             "proposal_type": proposal.proposal_type},
            proof_obligations_met=["train_consistent", "loo_passed",
                                   "falsification_passed"],
        )
        try:
            sig = encode_task_signature(train_pairs)
            embedding = _signature_to_embedding(sig)
            point = ManifoldPoint(
                embedding=embedding,
                task_signature=sig,
                domain="arc",
                hypothesis=proposal.hypothesis if isinstance(proposal.hypothesis, dict) else {},
                metadata={"solved": True, "family": proposal.operator_family},
            )
            self.manifold.add_point(point)
        except Exception:
            pass

    def _on_failure(
        self,
        task_id: str,
        analysis: TaskAnalysis,
        proposals: List[ModuleProposal],
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> None:
        self.event_log.append(ReasoningEvent(
            event_type="NEAR_SOLVED_STORED",
            task_id=task_id,
            payload={
                "failure_type": analysis.failure_trace.get("failure_type"),
                "n_proposals": len(proposals),
            },
            module="orchestrator",
        ))
        try:
            sig = encode_task_signature(train_pairs)
            embedding = _signature_to_embedding(sig)
            point = ManifoldPoint(
                embedding=embedding,
                task_signature=sig,
                domain="arc",
                hypothesis={},
                metadata={
                    "solved": False,
                    "failure_type": analysis.failure_trace.get("failure_type"),
                    "n_proposals_tried": len(proposals),
                },
            )
            self.manifold.add_point(point)
        except Exception:
            pass

    # ─── Proposal-level observational logging ───────────────────────────

    def _build_proposal_log_entry(
        self,
        task_id: str,
        proposal_idx: int,
        proposal: ModuleProposal,
        outcome: VerificationOutcome,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
        test_inputs: List[np.ndarray],
        test_outputs: Optional[List[np.ndarray]],
        runtime_seconds: float,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "task_id": task_id,
            "proposal_idx": proposal_idx,
            "module_source": proposal.module_name,
            "operator_family": proposal.operator_family,
            "selector": proposal.selector,
            "confidence": proposal.confidence,
            "train_consistent": outcome.train_consistent,
            "LOO_passed": outcome.loo_passed,
            "proof_obligations_passed": outcome.proof_obligations_passed,
            "falsification_passed": outcome.falsification_passed,
            "test_output_matches": None,
            "accepted": outcome.accepted,
            "false_positive": outcome.false_positive,
            "rejection_reason": outcome.rejection_reason,
            "runtime_seconds": round(runtime_seconds, 3),
            "train_pixel_error": None,
            "test_pixel_error_if_available": None,
            "wrong_pixels_mask_summary": None,
            "objects_selected": None,
            "objects_expected_if_inferable": None,
        }

        executable = self._extract_log_executable(proposal)
        if executable is not None:
            entry["train_pixel_error"] = self._compute_train_pixel_error(
                executable, train_pairs
            )
            if test_outputs is not None:
                test_err, wrong_summary = self._compute_test_pixel_error(
                    executable, test_inputs, test_outputs
                )
                entry["test_pixel_error_if_available"] = test_err
                entry["wrong_pixels_mask_summary"] = wrong_summary
                entry["test_output_matches"] = (test_err == 0) if test_err is not None else None
            elif outcome.false_positive:
                entry["test_output_matches"] = False
            elif outcome.accepted:
                test_confirmed = outcome.evidence.get("test_confirmed", False)
                entry["test_output_matches"] = True if test_confirmed else None

            entry["objects_selected"] = self._count_objects_selected(
                executable, train_pairs
            )

        entry["objects_expected_if_inferable"] = self._infer_expected_objects(
            train_pairs
        )

        return entry

    def _extract_log_executable(self, proposal: ModuleProposal) -> Any:
        hyp = getattr(proposal, "hypothesis", None)
        if hyp is None:
            return None
        if callable(hyp):
            return hyp
        if isinstance(hyp, dict):
            for key in ("execute", "operator", "prediction_fn"):
                fn = hyp.get(key)
                if callable(fn):
                    return fn
        return None

    def _compute_train_pixel_error(
        self, executable, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Optional[int]:
        total_err = 0
        try:
            for inp, expected in train_pairs:
                pred = executable(inp)
                if pred is None:
                    return None
                if not isinstance(pred, np.ndarray):
                    pred = np.array(pred)
                if pred.shape != expected.shape:
                    return None
                total_err += int(np.sum(pred != expected))
            return total_err
        except Exception:
            return None

    def _compute_test_pixel_error(
        self,
        executable,
        test_inputs: List[np.ndarray],
        test_outputs: List[np.ndarray],
    ) -> Tuple[Optional[int], Optional[str]]:
        total_err = 0
        wrong_summary_parts = []
        try:
            for idx, (inp, expected) in enumerate(zip(test_inputs, test_outputs)):
                pred = executable(inp)
                if pred is None:
                    return None, None
                if not isinstance(pred, np.ndarray):
                    pred = np.array(pred)
                if pred.shape != expected.shape:
                    wrong_summary_parts.append(
                        f"test_{idx}:shape_mismatch({list(pred.shape)}vs{list(expected.shape)})"
                    )
                    return None, ";".join(wrong_summary_parts)
                wrong = pred != expected
                n_wrong = int(wrong.sum())
                total_err += n_wrong
                if n_wrong > 0:
                    rows, cols = np.where(wrong)
                    wrong_summary_parts.append(
                        f"test_{idx}:{n_wrong}px,rows={int(rows.min())}-{int(rows.max())},"
                        f"cols={int(cols.min())}-{int(cols.max())}"
                    )
            return total_err, ";".join(wrong_summary_parts) if wrong_summary_parts else None
        except Exception:
            return None, None

    def _count_objects_selected(
        self, executable, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Optional[str]:
        try:
            counts = []
            for inp, _ in train_pairs:
                pred = executable(inp)
                if pred is None or not isinstance(pred, np.ndarray):
                    return None
                from scipy import ndimage as _ndi
                labeled, n = _ndi.label(pred > 0)
                counts.append(str(n))
            return ",".join(counts)
        except Exception:
            return None

    def _infer_expected_objects(
        self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Optional[str]:
        try:
            counts = []
            for _, out in train_pairs:
                from scipy import ndimage as _ndi
                labeled, n = _ndi.label(out > 0)
                counts.append(str(n))
            return ",".join(counts)
        except Exception:
            return None

    def _write_proposal_log(self, proposal_log: List[Dict[str, Any]]) -> None:
        if not proposal_log or not self.config.output_dir:
            return
        try:
            log_path = os.path.join(self.config.output_dir, "proposals.jsonl")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a") as f:
                for entry in proposal_log:
                    f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass
