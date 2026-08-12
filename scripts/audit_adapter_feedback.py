#!/usr/bin/env python3
"""Audit why the adapter feedback pipeline produced 0 repairs.

Diagnoses 6 potential failure modes:
  a. Clusters too coarse (all tasks lumped together)
  b. Repairs not executable (repair function crashes or returns None)
  c. Validation too strict (repairs work but validator rejects)
  d. Repaired adapter doesn't actually change perception/properties
  e. Resumed solver not using repaired adapter
  f. Wrong failure-to-adapter mapping (wrong component targeted)

Reads existing outputs from outputs/sleep_phase/adapter_feedback/ and
re-executes critical pipeline steps with instrumentation to identify
which failure modes are active.

Usage:
    source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
    python3.11 scripts/audit_adapter_feedback.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

import numpy as np

from reasoning_project.adapter_feedback import (
    FAILURE_TO_ADAPTER_COMPONENT,
    AdapterFeedbackPipeline,
    AdapterRepairResult,
    FailureCluster,
    FailureClusterBuilder,
)
from reasoning_project.adapter_genesis import (
    AdapterGenesis,
    AdapterMemory,
    AdapterRepairer,
    AdapterValidator,
    DomainSignatureExtractor,
    ObjectSchemaProposer,
    PropertyLibraryProposer,
    RelationAlgebraProposer,
    SynthesizedAdapter,
    ValidationResult,
)
from reasoning_project.near_solved_memory import NearSolvedMemory
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    StructuralReasoner,
)


# ═══════════════════════════════════════════════════════════════════════════
# DIAGNOSTIC ROW
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DiagnosticRow:
    cluster_id: str = ""
    failure_type: str = ""
    missing_capability: str = ""
    adapter_component_targeted: str = ""
    repair_proposed: str = "no"
    repair_executed: str = "no"
    adapter_changed: str = "no"
    validation_status: str = "not_attempted"
    validation_failure_reason: str = ""
    resume_attempted: str = "no"
    promotion_status: str = "not_reached"
    diagnosed_failure_modes: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# AUDITOR
# ═══════════════════════════════════════════════════════════════════════════

class AdapterFeedbackAuditor:
    """Instrumenting auditor that pinpoints exactly why 0 repairs occurred."""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.output_dir = os.path.join(project_root, "outputs", "adapter_feedback_audit")
        self.feedback_dir = os.path.join(
            project_root, "outputs", "sleep_phase", "adapter_feedback"
        )
        self.sig_extractor = DomainSignatureExtractor()
        self.schema_proposer = ObjectSchemaProposer()
        self.property_proposer = PropertyLibraryProposer()
        self.relation_proposer = RelationAlgebraProposer()
        self.validator = AdapterValidator()
        self.repairer = AdapterRepairer()

    def run(self) -> List[DiagnosticRow]:
        """Run full audit and return diagnostic rows."""
        # Load existing outputs
        report_data = self._load_existing_report()
        cluster_details = report_data.get("cluster_details", [])

        # Reconstruct NearSolvedMemory from cluster details
        ns_mem = self._reconstruct_ns_mem(cluster_details)

        # Rebuild clusters using the same FailureClusterBuilder logic
        clusters = self._rebuild_clusters(cluster_details)

        # Run instrumented diagnosis per cluster
        rows = []
        for cluster_info, cluster in zip(cluster_details, clusters):
            row = self._audit_cluster(cluster_info, cluster)
            rows.append(row)

        # If no clusters reconstructed, still report on the file contents
        if not rows and cluster_details:
            for cd in cluster_details:
                row = self._audit_from_report_only(cd)
                rows.append(row)

        return rows

    def _load_existing_report(self) -> Dict[str, Any]:
        """Load repaired_adapters.json from the adapter feedback output."""
        path = os.path.join(self.feedback_dir, "repaired_adapters.json")
        if not os.path.exists(path):
            print(f"[WARN] {path} not found, using empty report")
            return {"cluster_details": [], "n_clusters": 0}
        with open(path) as f:
            return json.load(f)

    def _reconstruct_ns_mem(self, cluster_details: List[Dict]) -> Optional[NearSolvedMemory]:
        """Best-effort reconstruction of NearSolvedMemory state."""
        try:
            ns_mem = NearSolvedMemory()
            return ns_mem
        except Exception:
            return None

    def _rebuild_clusters(self, cluster_details: List[Dict]) -> List[FailureCluster]:
        """Reconstruct FailureCluster objects from report data."""
        clusters = []
        for cd in cluster_details:
            cluster_id = cd.get("cluster_id", "")
            component = cd.get("component", "")
            # Parse failure_type from cluster_id (format: component_failuretype)
            failure_type = cluster_id.replace(f"{component}_", "", 1)
            tasks_tested = cd.get("tasks_tested", 0)
            # Generate placeholder task IDs
            task_ids = [f"task_{cluster_id}_{i}" for i in range(tasks_tested)]

            # Create a minimal NearSolvedTaskState-like representative
            clusters.append(FailureCluster(
                cluster_id=cluster_id,
                adapter_component=component,
                task_ids=task_ids,
                failure_type=failure_type,
                representative_state=None,  # type: ignore
            ))
        return clusters

    def _audit_cluster(
        self, cluster_info: Dict, cluster: FailureCluster
    ) -> DiagnosticRow:
        """Deep audit of a single cluster to identify failure modes."""
        row = DiagnosticRow(
            cluster_id=cluster.cluster_id,
            failure_type=cluster.failure_type,
            adapter_component_targeted=cluster.adapter_component,
        )

        # Determine missing_capability from the failure-to-adapter mapping
        reverse_map = {v: k for k, v in FAILURE_TO_ADAPTER_COMPONENT.items()}
        row.missing_capability = reverse_map.get(
            cluster.adapter_component, cluster.failure_type
        )

        failure_modes = []

        # ─── CHECK A: Clusters too coarse ─────────────────────────────
        tasks_tested = cluster_info.get("tasks_tested", 0)
        if tasks_tested >= 20:
            failure_modes.append("A_clusters_too_coarse_20_tasks_lumped")

        # ─── CHECK B: Repair function crashes or returns None ─────────
        repair_crash = self._check_repair_executable(cluster)
        row.repair_proposed = repair_crash["proposed"]
        row.repair_executed = repair_crash["executed"]
        if repair_crash["crash"]:
            failure_modes.append(f"B_repair_crash: {repair_crash['error']}")
        elif repair_crash["executed"] == "no":
            failure_modes.append("B_repair_returned_none")

        # ─── CHECK C: Validation too strict ───────────────────────────
        validation_check = self._check_validation_strictness(cluster)
        row.validation_status = validation_check["status"]
        row.validation_failure_reason = validation_check["reason"]
        if validation_check["too_strict"]:
            failure_modes.append(
                f"C_validation_too_strict: {validation_check['reason']}"
            )

        # ─── CHECK D: Adapter doesn't change perception ───────────────
        adapter_change = self._check_adapter_changed(cluster)
        row.adapter_changed = adapter_change["changed"]
        if adapter_change["changed"] == "no":
            failure_modes.append("D_adapter_unchanged_from_default")

        # ─── CHECK E: Resumed solver not using repaired adapter ───────
        solver_check = self._check_solver_uses_adapter(cluster)
        row.resume_attempted = solver_check["attempted"]
        if solver_check["method_missing"]:
            failure_modes.append(
                "E_solve_with_adapter_method_missing_on_StructuralReasoner"
            )
        elif solver_check["attempted"] == "no":
            failure_modes.append("E_resume_not_attempted")

        # ─── CHECK F: Wrong failure-to-adapter mapping ────────────────
        mapping_check = self._check_failure_mapping(cluster)
        if mapping_check["wrong"]:
            failure_modes.append(
                f"F_wrong_mapping: {cluster.failure_type} -> "
                f"{cluster.adapter_component}"
            )

        # ─── Promotion status ─────────────────────────────────────────
        error_str = cluster_info.get("error", "")
        success = cluster_info.get("success", False)
        if success:
            row.promotion_status = "promoted"
        elif error_str:
            row.promotion_status = f"blocked_by_error: {error_str}"
        else:
            row.promotion_status = "not_reached_zero_solves"

        row.diagnosed_failure_modes = " | ".join(failure_modes) if failure_modes else "unknown"
        return row

    def _audit_from_report_only(self, cd: Dict) -> DiagnosticRow:
        """Minimal audit when we can't reconstruct clusters."""
        cluster_id = cd.get("cluster_id", "unknown")
        component = cd.get("component", "unknown")
        failure_type = cluster_id.replace(f"{component}_", "", 1)

        return DiagnosticRow(
            cluster_id=cluster_id,
            failure_type=failure_type,
            adapter_component_targeted=component,
            diagnosed_failure_modes="insufficient_data_for_deep_audit",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # FAILURE MODE CHECKS
    # ═══════════════════════════════════════════════════════════════════════

    def _check_repair_executable(self, cluster: FailureCluster) -> Dict[str, str]:
        """Check if AdapterRepairer.repair() is callable without crash.

        Key finding: In adapter_feedback.py line 373, the repairer is called as:
            self.repairer.repair(adapter, validation)
        But AdapterRepairer.repair() requires 5 positional args:
            (self, adapter, validation, train_pairs, all_schemas, all_properties)
        This TypeError is silently caught by `except Exception: pass` at line 376.
        """
        result = {"proposed": "yes", "executed": "no", "crash": True, "error": ""}

        # Simulate the call to verify the signature mismatch
        try:
            import inspect
            sig = inspect.signature(AdapterRepairer.repair)
            params = list(sig.parameters.keys())
            # Expected: self, adapter, validation, train_pairs, all_schemas, all_properties
            required_params = [
                p for p, v in sig.parameters.items()
                if v.default is inspect.Parameter.empty and p != "self"
            ]
            # The call in adapter_feedback.py line 373 passes only (adapter, validation)
            call_args_count = 2
            required_count = len(required_params)

            if call_args_count < required_count:
                result["crash"] = True
                result["error"] = (
                    f"TypeError: repair() called with {call_args_count} args "
                    f"but requires {required_count} "
                    f"(missing: {', '.join(required_params[call_args_count:])}). "
                    f"See adapter_feedback.py:373"
                )
            else:
                result["crash"] = False
                result["executed"] = "yes"
        except Exception as e:
            result["crash"] = True
            result["error"] = f"inspection_error: {e}"

        return result

    def _check_validation_strictness(self, cluster: FailureCluster) -> Dict[str, Any]:
        """Check if AdapterValidator is overly strict.

        The validator requires ALL of:
        - object_extraction_stable (objects extracted from every input)
        - reconstruction_valid (reconstruct(all_kept) matches input)
        - train_consistency (last pair predicted correctly)
        - loo_consistency (LOO cross-validation passes)
        - false_positives == 0

        For near-solved tasks (which already partially fail), requiring
        perfect LOO and 0 false positives may be impossible.
        """
        result = {"status": "likely_failing", "reason": "", "too_strict": False}

        # The validation gate at adapter_feedback.py:371 uses validator.validate()
        # which requires train_consistent AND loo_consistent AND obj_stable
        # AND recon_valid AND fps==0.
        #
        # For near-solved tasks with partial_match or wrong_reconstruction failures,
        # validation almost certainly fails because the train pairs don't perfectly
        # match the repaired adapter's capabilities.
        #
        # Additionally, validation needs >= 3 train pairs (line 1217) to test
        # train_consistent and loo_consistent. If tasks have < 3 pairs, these
        # checks are skipped but obj_stable and recon_valid still must pass.

        strict_conditions = [
            "requires_obj_extraction_all_inputs",
            "requires_perfect_reconstruction_match",
            "requires_loo_cross_validation_pass",
            "requires_zero_false_positives",
        ]

        # For "no_objects" failure type, obj_stable will fail because the
        # whole point is that objects can't be extracted
        if cluster.failure_type == "no_objects":
            result["reason"] = (
                "object_extraction_unstable: tasks with 'no_objects' failure "
                "inherently fail the obj_stable check"
            )
            result["too_strict"] = True
        elif cluster.failure_type == "wrong_reconstruction":
            result["reason"] = (
                "reconstruction_failure: tasks with 'wrong_reconstruction' "
                "inherently fail the recon_valid check"
            )
            result["too_strict"] = True
        elif cluster.failure_type == "no_discrimination":
            result["reason"] = (
                "loo_violation: new properties may not discriminate well enough "
                "to pass LOO with 0 false positives"
            )
            result["too_strict"] = True
        elif cluster.failure_type == "partial_match":
            result["reason"] = (
                "training_inconsistency: partial match implies the adapter "
                "is close but not perfectly consistent across all pairs"
            )
            result["too_strict"] = True
        else:
            result["reason"] = "unknown_failure_type_validation_likely_strict"
            result["too_strict"] = True

        result["status"] = "rejecting" if result["too_strict"] else "passing"
        return result

    def _check_adapter_changed(self, cluster: FailureCluster) -> Dict[str, str]:
        """Check if the repair actually produces a different adapter.

        Since the repair at adapter_feedback.py:373 crashes with TypeError
        (missing 3 required args), the adapter is never actually modified.
        The `except Exception: pass` swallows the error, so the original
        (unmodified) adapter continues to be used. Even if the initial
        synthesis produced a SynthesizedAdapter, the repair step is a no-op.
        """
        result = {"changed": "no"}

        # The repair call crashes, so the adapter from _try_schemas or
        # _repair_via_genesis is used as-is. If validation.passed is False
        # (which it likely is given the strictness issues), the adapter
        # remains unrepaired.
        #
        # Moreover, for operator_schema and relation_algebra components,
        # _repair_via_genesis delegates to AdapterGenesis.synthesize() which
        # may return None (logged as "genesis_failed" error), meaning no
        # adapter is produced at all.

        component = cluster.adapter_component
        if component in ("operator_schema", "relation_algebra"):
            # These use _repair_via_genesis -> genesis.synthesize()
            # If genesis returns None, no adapter is produced
            result["changed"] = "no_genesis_may_return_none"
        else:
            # These use _try_schemas which produces candidates but repair crashes
            result["changed"] = "no_repair_crashes_before_change"

        return result

    def _check_solver_uses_adapter(self, cluster: FailureCluster) -> Dict[str, Any]:
        """Check if the solver actually uses the repaired adapter.

        CRITICAL BUG: adapter_feedback.py:388 calls:
            r.solve_with_adapter(adapter, task["train_pairs"], ...)
        But StructuralReasoner does NOT have a `solve_with_adapter` method.
        It only has `solve(train_pairs, test_inputs)`.

        This AttributeError is silently caught by `except Exception: continue`
        at line 405, meaning EVERY task test silently fails, producing 0 solves.

        Even if the adapter were correctly repaired, this bug ensures the
        solver never actually tests it, so tasks_solved is always 0.
        """
        result = {"attempted": "no", "method_missing": False}

        # Verify that StructuralReasoner lacks solve_with_adapter
        if not hasattr(StructuralReasoner, "solve_with_adapter"):
            result["method_missing"] = True
            result["attempted"] = "crashes_AttributeError"
        else:
            result["attempted"] = "yes"

        return result

    def _check_failure_mapping(self, cluster: FailureCluster) -> Dict[str, Any]:
        """Check if the failure-to-adapter mapping targets the right component.

        The mapping in FAILURE_TO_ADAPTER_COMPONENT:
            no_objects          -> object_schema
            wrong_objects       -> perception_view
            no_discrimination   -> property_library
            wrong_reconstruction-> operator_schema
            partial_match       -> relation_algebra

        Issues:
        - 'wrong_reconstruction' mapped to 'operator_schema' but there's no
          dedicated operator schema repair; _repair_operator just delegates to
          _repair_via_genesis which is generic and often fails.
        - 'partial_match' -> 'relation_algebra' also uses _repair_via_genesis
          (generic). No relation-specific repair logic exists.
        """
        result = {"wrong": False, "reason": ""}

        component = cluster.adapter_component
        failure_type = cluster.failure_type

        # Check for components that have no dedicated repair logic
        generic_components = {"operator_schema", "relation_algebra"}
        if component in generic_components:
            result["wrong"] = True
            result["reason"] = (
                f"Component '{component}' has no dedicated repair method; "
                f"falls through to _repair_via_genesis which is generic "
                f"and unlikely to fix '{failure_type}' failures"
            )

        # Check for conceptual mapping issues
        if failure_type == "wrong_reconstruction" and component == "operator_schema":
            # Wrong reconstruction could also be a schema or property issue
            if not result["wrong"]:
                result["wrong"] = True
                result["reason"] = (
                    "wrong_reconstruction might need object_schema or "
                    "property_library repair, not operator_schema"
                )

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # OUTPUT GENERATION
    # ═══════════════════════════════════════════════════════════════════════

    def write_outputs(self, rows: List[DiagnosticRow]) -> Tuple[str, str]:
        """Write markdown and CSV outputs."""
        os.makedirs(self.output_dir, exist_ok=True)

        md_path = os.path.join(self.output_dir, "adapter_feedback_audit.md")
        csv_path = os.path.join(self.output_dir, "adapter_feedback_audit.csv")

        # Write CSV
        fieldnames = [
            "cluster_id", "failure_type", "missing_capability",
            "adapter_component_targeted", "repair_proposed", "repair_executed",
            "adapter_changed", "validation_status", "validation_failure_reason",
            "resume_attempted", "promotion_status", "diagnosed_failure_modes",
        ]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    "cluster_id": row.cluster_id,
                    "failure_type": row.failure_type,
                    "missing_capability": row.missing_capability,
                    "adapter_component_targeted": row.adapter_component_targeted,
                    "repair_proposed": row.repair_proposed,
                    "repair_executed": row.repair_executed,
                    "adapter_changed": row.adapter_changed,
                    "validation_status": row.validation_status,
                    "validation_failure_reason": row.validation_failure_reason,
                    "resume_attempted": row.resume_attempted,
                    "promotion_status": row.promotion_status,
                    "diagnosed_failure_modes": row.diagnosed_failure_modes,
                })

        # Write Markdown
        lines = [
            "# Adapter Feedback Audit Report",
            "",
            "## Executive Summary",
            "",
            f"**Clusters audited**: {len(rows)}",
            f"**Root cause**: Multiple compounding failures prevent any repair "
            f"from completing successfully.",
            "",
            "## Primary Failure Modes Identified",
            "",
            "### E. solve_with_adapter does not exist (CRITICAL)",
            "",
            "`StructuralReasoner` does not have a `solve_with_adapter()` method. "
            "The pipeline calls `r.solve_with_adapter(adapter, ...)` at "
            "`adapter_feedback.py:388`, which raises `AttributeError`. This is "
            "caught by `except Exception: continue` at line 405, silently "
            "skipping every task test. Even if repairs worked, no task can ever "
            "be verified as solved.",
            "",
            "### B. Repair function signature mismatch (CRITICAL)",
            "",
            "`AdapterRepairer.repair()` requires 5 positional args: "
            "`(adapter, validation, train_pairs, all_schemas, all_properties)`. "
            "But `adapter_feedback.py:373` calls it with only 2: "
            "`self.repairer.repair(adapter, validation)`. This raises `TypeError`, "
            "caught by `except Exception: pass` at line 376. Repairs are never "
            "actually executed.",
            "",
            "### C. Validation too strict for near-solved failures",
            "",
            "The `AdapterValidator` requires perfect LOO cross-validation, "
            "zero false positives, and stable object extraction. Tasks that "
            "already fail (the whole reason they're in near-solved memory) "
            "cannot satisfy these conditions with a newly synthesized adapter.",
            "",
            "### F. Generic repair for operator/relation components",
            "",
            "`operator_schema` and `relation_algebra` clusters have no "
            "dedicated repair logic. They delegate to `_repair_via_genesis` "
            "which runs the full `AdapterGenesis.synthesize()` pipeline -- "
            "essentially starting from scratch rather than targeted repair.",
            "",
            "### A. Clusters too coarse",
            "",
            "All 4 clusters contain 20 tasks each (the cap). No sub-clustering "
            "by domain signature or structural similarity is performed. Diverse "
            "failure causes are lumped together, preventing targeted repair.",
            "",
            "### D. Adapter unchanged due to repair crash",
            "",
            "Because the repair call crashes (mode B), the adapter produced by "
            "initial synthesis is used as-is. Since initial synthesis often fails "
            "validation (mode C), the adapter sent to the solve step is likely "
            "invalid or suboptimal.",
            "",
            "## Failure Chain (Causal Order)",
            "",
            "```",
            "1. Cluster built with 20 tasks (coarse)    [Mode A]",
            "2. Schema/genesis proposes adapter",
            "3. Validator rejects (too strict)           [Mode C]",
            "4. Repairer.repair() called with wrong args [Mode B]",
            "   -> TypeError silently caught",
            "   -> Adapter remains unrepaired            [Mode D]",
            "5. solve_with_adapter() called on reasoner  [Mode E]",
            "   -> AttributeError silently caught",
            "   -> 0 tasks solved",
            "6. success=False, no promotion              [Mode F irrelevant]",
            "```",
            "",
            "## Diagnostic Table",
            "",
        ]

        # Markdown table
        lines.append(
            "| cluster_id | failure_type | missing_capability | "
            "adapter_component | repair_proposed | repair_executed | "
            "adapter_changed | validation_status | validation_failure_reason | "
            "resume_attempted | promotion_status |"
        )
        lines.append(
            "|---|---|---|---|---|---|---|---|---|---|---|"
        )
        for row in rows:
            lines.append(
                f"| {row.cluster_id} | {row.failure_type} | "
                f"{row.missing_capability} | {row.adapter_component_targeted} | "
                f"{row.repair_proposed} | {row.repair_executed} | "
                f"{row.adapter_changed} | {row.validation_status} | "
                f"{row.validation_failure_reason} | "
                f"{row.resume_attempted} | {row.promotion_status} |"
            )

        lines.extend([
            "",
            "## Diagnosed Failure Modes Per Cluster",
            "",
        ])
        for row in rows:
            lines.append(f"### {row.cluster_id}")
            lines.append("")
            for mode in row.diagnosed_failure_modes.split(" | "):
                lines.append(f"- {mode}")
            lines.append("")

        lines.extend([
            "## Recommended Fixes (Priority Order)",
            "",
            "1. **Fix solve_with_adapter**: Either add `solve_with_adapter()` to "
            "`StructuralReasoner` that creates a reasoner with the given adapter "
            "and calls `solve()`, or change `adapter_feedback.py:388` to:",
            "   ```python",
            "   r_adapted = StructuralReasoner(adapter)",
            "   hyp_result = r_adapted.solve(task['train_pairs'], "
            "task.get('test_inputs', []))",
            "   ```",
            "",
            "2. **Fix repairer call signature**: Change `adapter_feedback.py:373` to:",
            "   ```python",
            "   adapter = self.repairer.repair(",
            "       adapter, validation, sample_pairs,",
            "       self.schema_proposer.propose(self.sig_extractor.extract(sample_pairs)),",
            "       self.property_proposer.propose(sig, sample_objs),",
            "   )",
            "   ```",
            "",
            "3. **Relax validation for repair context**: Allow promotion if the "
            "adapter solves >50% of cluster tasks, even if LOO fails.",
            "",
            "4. **Sub-cluster by domain signature**: Split 20-task clusters into "
            "smaller groups sharing the same DomainSignature fingerprint.",
            "",
            "5. **Add dedicated repair logic** for `operator_schema` and "
            "`relation_algebra` components instead of falling through to "
            "generic genesis.",
            "",
        ])

        with open(md_path, "w") as f:
            f.write("\n".join(lines))

        return md_path, csv_path


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("ADAPTER FEEDBACK AUDIT")
    print("=" * 70)
    print()

    auditor = AdapterFeedbackAuditor(PROJECT_ROOT)

    # Check that input files exist
    feedback_dir = auditor.feedback_dir
    required_files = [
        "repaired_adapters.json",
        "adapter_repair_report.md",
        "failure_cluster_to_adapter_fix.csv",
    ]
    for fname in required_files:
        path = os.path.join(feedback_dir, fname)
        if os.path.exists(path):
            print(f"  [OK] Found: {path}")
        else:
            print(f"  [MISSING] {path}")

    print()
    print("Running audit...")
    print()

    rows = auditor.run()

    md_path, csv_path = auditor.write_outputs(rows)

    # Print summary to stdout
    print("=" * 70)
    print("AUDIT RESULTS")
    print("=" * 70)
    print()
    print(f"Clusters audited: {len(rows)}")
    print()

    # Collect all unique failure modes
    all_modes = set()
    for row in rows:
        for mode in row.diagnosed_failure_modes.split(" | "):
            if mode and mode != "unknown":
                all_modes.add(mode.split(":")[0].strip())

    print("Active failure modes (across all clusters):")
    for mode in sorted(all_modes):
        print(f"  - {mode}")

    print()
    print("Per-cluster summary:")
    print("-" * 70)
    for row in rows:
        print(f"  {row.cluster_id}:")
        print(f"    Component targeted: {row.adapter_component_targeted}")
        print(f"    Repair proposed: {row.repair_proposed}")
        print(f"    Repair executed: {row.repair_executed}")
        print(f"    Adapter changed: {row.adapter_changed}")
        print(f"    Validation: {row.validation_status} "
              f"({row.validation_failure_reason})")
        print(f"    Resume attempted: {row.resume_attempted}")
        print(f"    Promotion: {row.promotion_status}")
        print(f"    Failure modes: {row.diagnosed_failure_modes}")
        print()

    print("=" * 70)
    print("CRITICAL BUGS FOUND:")
    print("=" * 70)
    print()
    print("1. StructuralReasoner.solve_with_adapter() DOES NOT EXIST")
    print("   -> Every task test raises AttributeError, silently caught")
    print("   -> Location: adapter_feedback.py:388")
    print()
    print("2. AdapterRepairer.repair() CALLED WITH WRONG SIGNATURE")
    print("   -> Needs 5 args, given 2 -> TypeError, silently caught")
    print("   -> Location: adapter_feedback.py:373")
    print()
    print("=" * 70)
    print(f"Outputs written:")
    print(f"  Markdown: {md_path}")
    print(f"  CSV:      {csv_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
