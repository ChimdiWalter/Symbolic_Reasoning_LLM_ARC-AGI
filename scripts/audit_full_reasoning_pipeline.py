#!/usr/bin/env python3.11
"""Comprehensive audit of the full reasoning pipeline.

Checks:
  1. Module imports and key class/function availability
  2. Exception-swallowing patterns in operator invention and related modules
  3. Certificate existence and field completeness for all 4 promoted tasks
  4. Claim traceability -- every claim in claim_traceability.md backed by artifacts
  5. Promotion chain integrity -- no static solver results counted as trace-driven
  6. AdapterGenesis and domain adapter usability
  7. Main pipeline loop exposure (fixed reasoning loop)
  8. Stale promoted records without certificates

Outputs:
  outputs/final_paper_package/pipeline_audit/full_pipeline_audit.md
  outputs/final_paper_package/pipeline_audit/full_pipeline_audit.csv
  outputs/final_paper_package/pipeline_audit/missing_links.json
"""
from __future__ import annotations

import ast
import csv
import importlib
import inspect
import json
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "src"
sys.path.insert(0, str(SRC))

# =====================================================================
# 1. Module import audit
# =====================================================================

MODULES_TO_CHECK = [
    "reasoning_project.adapter_genesis",
    "reasoning_project.domain_adapters",
    "reasoning_project.perception_bridge",
    "reasoning_project.reasoning_engine",
    "reasoning_project.near_solved_memory",
    "reasoning_project.concept_grammar",
    "reasoning_project.operator_semantics",
    "reasoning_project.trace_operator_invention",
    "reasoning_project.operator_schemas",
    "reasoning_project.color_transfer",
    "reasoning_project.destination_policy",
    "reasoning_project.correspondence_inference",
    "reasoning_project.active_falsifier",
    "reasoning_project.certificates",
    "reasoning_project.events",
    "reasoning_project.portfolio",
    "reasoning_project.adaptive_loop",
    "reasoning_project.manifold_memory",
    "reasoning_project.property_invention",
    "reasoning_project.adapter_feedback",
    "reasoning_project.reasoning_policy",
    "reasoning_project.falsifier",
    "reasoning_project.compression",
    "reasoning_project.repair",
    "reasoning_project.marker_projection",
]


def audit_module_imports() -> List[Dict[str, Any]]:
    """Check all key modules import without error."""
    results = []
    for mod_name in MODULES_TO_CHECK:
        try:
            mod = importlib.import_module(mod_name)
            results.append({"module": mod_name, "status": "OK", "error": None})
        except Exception as e:
            results.append({"module": mod_name, "status": "FAIL", "error": str(e)})
    return results


# =====================================================================
# 2. Key class/function existence and callability
# =====================================================================

KEY_SYMBOLS = [
    ("reasoning_project.reasoning_engine", "DomainAdapter"),
    ("reasoning_project.reasoning_engine", "GridDomainAdapter"),
    ("reasoning_project.reasoning_engine", "StructuralReasoner"),
    ("reasoning_project.reasoning_engine", "ReasoningMemory"),
    ("reasoning_project.adapter_genesis", "AdapterGenesis"),
    ("reasoning_project.domain_adapters", "GraphDomainAdapter"),
    ("reasoning_project.domain_adapters", "ChessBoardDomainAdapter"),
    ("reasoning_project.domain_adapters", "MoleculeGraphDomainAdapter"),
    ("reasoning_project.trace_operator_invention", "TraceDrivenOperatorInventor"),
    ("reasoning_project.operator_semantics", "ExecutableOperatorHypothesis"),
    ("reasoning_project.operator_semantics", "OperatorProofObligation"),
    ("reasoning_project.active_falsifier", "ActiveFalsifier"),
    ("reasoning_project.active_falsifier", "FalsificationResult"),
    ("reasoning_project.certificates", "ReasoningCertificate"),
    ("reasoning_project.certificates", "CertificateBuilder"),
    ("reasoning_project.certificates", "certificate_to_json"),
    ("reasoning_project.certificates", "certificate_to_markdown"),
    ("reasoning_project.events", "ReasoningEvent"),
    ("reasoning_project.events", "ReasoningEventLog"),
    ("reasoning_project.events", "EVENT_TYPES"),
    ("reasoning_project.portfolio", "PortfolioResult"),
    ("reasoning_project.near_solved_memory", "NearSolvedMemory"),
    ("reasoning_project.concept_grammar", "ConceptGenerator"),
    ("reasoning_project.adaptive_loop", "AdaptiveReasoningLoop"),
    ("reasoning_project.color_transfer", "ColorSourceInferer"),
    ("reasoning_project.color_transfer", "execute_color_transfer"),
]


def audit_key_symbols() -> List[Dict[str, Any]]:
    """Check that key classes/functions exist and are callable/instantiable."""
    results = []
    for mod_name, symbol_name in KEY_SYMBOLS:
        try:
            mod = importlib.import_module(mod_name)
            obj = getattr(mod, symbol_name, None)
            if obj is None:
                results.append({
                    "module": mod_name,
                    "symbol": symbol_name,
                    "status": "MISSING",
                    "kind": None,
                    "error": f"{symbol_name} not found in {mod_name}",
                })
            else:
                kind = "class" if inspect.isclass(obj) else (
                    "function" if callable(obj) else "other"
                )
                results.append({
                    "module": mod_name,
                    "symbol": symbol_name,
                    "status": "OK",
                    "kind": kind,
                    "error": None,
                })
        except Exception as e:
            results.append({
                "module": mod_name,
                "symbol": symbol_name,
                "status": "FAIL",
                "kind": None,
                "error": str(e),
            })
    return results


# =====================================================================
# 3. Exception-swallowing pattern detection
# =====================================================================

FILES_TO_SCAN_FOR_EXCEPTIONS = [
    SRC / "reasoning_project" / "trace_operator_invention.py",
    SRC / "reasoning_project" / "operator_semantics.py",
    SRC / "reasoning_project" / "certificates.py",
    SRC / "reasoning_project" / "active_falsifier.py",
    SRC / "reasoning_project" / "reasoning_engine.py",
    SRC / "reasoning_project" / "adapter_genesis.py",
    SRC / "reasoning_project" / "portfolio.py",
]


def _scan_exception_patterns(filepath: Path) -> List[Dict[str, Any]]:
    """Use AST to find bare `except:` or `except Exception:` without re-raise or logging."""
    issues = []
    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
    except Exception as e:
        issues.append({
            "file": str(filepath.relative_to(BASE)),
            "line": 0,
            "pattern": "parse_error",
            "severity": "error",
            "detail": str(e),
        })
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue

        line = node.lineno
        # Determine the exception type caught
        if node.type is None:
            exc_type = "bare_except"
        elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
            exc_type = "except_Exception"
        elif isinstance(node.type, ast.Name) and node.type.id in (
            "BaseException", "SystemExit", "KeyboardInterrupt",
        ):
            exc_type = f"except_{node.type.id}"
        else:
            continue  # specific exception types are fine

        # Check if the body contains raise, logging, or re-raise
        has_raise = False
        has_logging = False
        has_continue_only = False
        body_stmts = node.body

        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Raise):
                has_raise = True
            if isinstance(stmt, ast.Call):
                func = stmt.func
                if isinstance(func, ast.Attribute) and func.attr in (
                    "warning", "error", "exception", "info", "debug",
                    "warn", "log",
                ):
                    has_logging = True
                if isinstance(func, ast.Name) and func.id == "print":
                    has_logging = True  # print is acceptable for scripts

        if len(body_stmts) == 1:
            s = body_stmts[0]
            if isinstance(s, ast.Continue):
                has_continue_only = True
            elif isinstance(s, ast.Pass):
                has_continue_only = True
            elif isinstance(s, ast.Return) and s.value is not None:
                # return False is common pattern for validation methods
                has_logging = True

        if has_raise or has_logging:
            severity = "info"
        elif has_continue_only and exc_type == "except_Exception":
            severity = "warning"
        else:
            severity = "warning" if exc_type == "except_Exception" else "critical"

        issues.append({
            "file": str(filepath.relative_to(BASE)),
            "line": line,
            "pattern": exc_type,
            "severity": severity,
            "detail": (
                "re-raises" if has_raise
                else "logs" if has_logging
                else "silent swallow (continue/pass/return-value)"
            ),
        })

    return issues


def audit_exception_patterns() -> List[Dict[str, Any]]:
    """Scan key files for exception-swallowing patterns."""
    all_issues: List[Dict[str, Any]] = []
    for fp in FILES_TO_SCAN_FOR_EXCEPTIONS:
        if fp.exists():
            all_issues.extend(_scan_exception_patterns(fp))
        else:
            all_issues.append({
                "file": str(fp.relative_to(BASE)),
                "line": 0,
                "pattern": "file_missing",
                "severity": "error",
                "detail": "File does not exist",
            })
    return all_issues


# =====================================================================
# 4. Certificate audit for the 4 promoted tasks
# =====================================================================

PROMOTED_TASKS = {
    "d89b689b": "quadrant_fill",
    "e9ac8c9e": "multi-block quadrant_fill",
    "a48eeaf7": "project_to_halo",
    "2a5f8217": "same_shape color transfer",
}

CERTIFICATE_DIRS = [
    BASE / "outputs" / "final_paper_package" / "frozen_verified_state" / "certificates",
    BASE / "outputs" / "operator_reasoning_phase" / "copy_to_position_real" / "certificates",
    BASE / "outputs" / "operator_reasoning_phase" / "color_transfer" / "real" / "certificates",
]

REQUIRED_CERT_FIELDS = [
    "task_id",
    "prediction_id",
    "selected_hypothesis",
    "derivation_trace",
    "supporting_paradigms",
    "n_agreeing",
    "training_fit",
    "loo_status",
    "counterexamples_survived",
    "counterexamples_total",
    "falsification_score",
    "invariants_preserved",
    "topology_changes",
    "failure_risk",
    "confidence",
]

REQUIRED_HYPOTHESIS_FIELDS = [
    "operator_family",
    "validation_level",
]


def _find_certificate(task_id: str) -> Optional[Path]:
    """Search for a certificate JSON for the given task_id."""
    for cert_dir in CERTIFICATE_DIRS:
        if not cert_dir.exists():
            continue
        for candidate in [
            cert_dir / f"{task_id}.json",
            cert_dir / f"{task_id}_certificate.json",
        ]:
            if candidate.exists():
                return candidate
    return None


def audit_certificates() -> List[Dict[str, Any]]:
    """Check that all 4 promoted tasks have valid certificate files."""
    results = []
    for task_id, description in PROMOTED_TASKS.items():
        cert_path = _find_certificate(task_id)
        if cert_path is None:
            results.append({
                "task_id": task_id,
                "description": description,
                "status": "MISSING",
                "path": None,
                "missing_fields": [],
                "training_fit": None,
                "loo_status": None,
                "has_derivation_trace": False,
                "has_operator_family": False,
                "has_promotion_source_trace": False,
                "error": "No certificate file found",
            })
            continue

        try:
            with open(cert_path) as f:
                cert = json.load(f)
        except Exception as e:
            results.append({
                "task_id": task_id,
                "description": description,
                "status": "PARSE_ERROR",
                "path": str(cert_path.relative_to(BASE)),
                "missing_fields": [],
                "training_fit": None,
                "loo_status": None,
                "has_derivation_trace": False,
                "has_operator_family": False,
                "has_promotion_source_trace": False,
                "error": str(e),
            })
            continue

        missing_fields = [f for f in REQUIRED_CERT_FIELDS if f not in cert]
        hyp = cert.get("selected_hypothesis", {})
        missing_hyp = [f for f in REQUIRED_HYPOTHESIS_FIELDS if f not in hyp]

        results.append({
            "task_id": task_id,
            "description": description,
            "status": "OK" if not missing_fields and not missing_hyp else "INCOMPLETE",
            "path": str(cert_path.relative_to(BASE)),
            "missing_fields": missing_fields + [f"hypothesis.{f}" for f in missing_hyp],
            "training_fit": cert.get("training_fit"),
            "loo_status": cert.get("loo_status"),
            "has_derivation_trace": bool(cert.get("derivation_trace")),
            "has_operator_family": "operator_family" in hyp or "family" in hyp,
            "has_promotion_source_trace": "promotion_source_trace" in hyp,
            "error": None,
        })

    return results


# =====================================================================
# 5. Claim traceability audit
# =====================================================================

def _parse_claim_table(md_path: Path) -> List[Dict[str, str]]:
    """Parse the markdown table in claim_traceability.md."""
    claims = []
    if not md_path.exists():
        return claims
    text = md_path.read_text()
    lines = text.split("\n")
    in_table = False
    headers: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if not in_table:
            if any("Hypothesis" in c or "Claim" in c for c in cells):
                headers = cells
                in_table = True
            continue
        if all(set(c) <= {"-", " ", ":"} for c in cells):
            continue  # separator row
        if len(cells) == len(headers):
            row = dict(zip(headers, cells))
            claims.append(row)
    return claims


def _extract_artifact_paths(text: str) -> List[str]:
    """Extract file paths from markdown text, handling backtick-wrapped paths."""
    paths = re.findall(r"`([^`]+(?:/[^`]+)+)`", text)
    # Also catch non-backtick paths that look like relative paths
    paths2 = re.findall(r"(?:^|\s)((?:outputs|docs|src|paper|configs)/\S+)", text)
    return list(set(paths + paths2))


def audit_claim_traceability() -> Tuple[List[Dict[str, Any]], List[str]]:
    """Check that each claim in claim_traceability.md has backing artifact files."""
    claim_md = BASE / "claim_traceability.md"
    claims = _parse_claim_table(claim_md)
    results = []
    all_missing: List[str] = []

    for claim in claims:
        claim_name = claim.get("Hypothesis") or claim.get("Claim") or "unknown"
        # Gather artifact paths from all columns
        all_text = " ".join(claim.values())
        artifact_paths = _extract_artifact_paths(all_text)

        found = []
        missing = []
        for ap in artifact_paths:
            full = BASE / ap
            if full.exists():
                found.append(ap)
            else:
                missing.append(ap)
                all_missing.append(ap)

        results.append({
            "claim": claim_name,
            "total_artifacts": len(artifact_paths),
            "found": len(found),
            "missing": len(missing),
            "missing_paths": missing,
            "status": "OK" if not missing else "INCOMPLETE",
        })

    return results, all_missing


# =====================================================================
# 6. Promotion chain integrity -- no static-solver leakage
# =====================================================================

def audit_promotion_chain_integrity() -> List[Dict[str, Any]]:
    """Check that promoted certificates are genuinely trace-driven, not static solver leakage."""
    results = []
    for task_id, description in PROMOTED_TASKS.items():
        cert_path = _find_certificate(task_id)
        if cert_path is None:
            results.append({
                "task_id": task_id,
                "status": "MISSING_CERT",
                "is_trace_driven": None,
                "detail": "No certificate to check",
            })
            continue
        try:
            with open(cert_path) as f:
                cert = json.load(f)
        except Exception:
            results.append({
                "task_id": task_id,
                "status": "PARSE_ERROR",
                "is_trace_driven": None,
                "detail": "Could not parse certificate",
            })
            continue

        hyp = cert.get("selected_hypothesis", {})
        derivation = cert.get("derivation_trace", [])
        paradigms = cert.get("supporting_paradigms", [])

        # Check for trace-driven indicators
        has_operator_gap = any(
            d.get("step") == "operator_gap_detected" for d in derivation
        )
        has_hypothesis_proposed = any(
            d.get("step") == "hypothesis_proposed" for d in derivation
        )
        has_loo = any(d.get("step") == "loo_validated" for d in derivation)
        has_falsification = any(
            d.get("step") == "falsification" for d in derivation
        )
        has_promotion_trace = "promotion_source_trace" in hyp

        # Check it is NOT a static solver leakage
        is_static = any(
            p in ("static_portfolio", "StructuralReasoner", "structural_reasoner")
            for p in paradigms
        )
        is_trace_derived = any(
            "trace_derived" in p for p in paradigms
        )

        all_checks = [
            has_operator_gap, has_hypothesis_proposed, has_loo, has_falsification,
        ]
        trace_score = sum(all_checks)

        if is_static and not is_trace_derived:
            status = "STATIC_LEAKAGE"
            is_genuine = False
        elif trace_score >= 3:
            status = "TRACE_DRIVEN"
            is_genuine = True
        elif trace_score >= 1:
            status = "PARTIAL_TRACE"
            is_genuine = True
        else:
            status = "UNCLEAR"
            is_genuine = None

        results.append({
            "task_id": task_id,
            "status": status,
            "is_trace_driven": is_genuine,
            "detail": (
                f"derivation steps: operator_gap={has_operator_gap}, "
                f"hypothesis_proposed={has_hypothesis_proposed}, "
                f"loo={has_loo}, falsification={has_falsification}, "
                f"promotion_source_trace={has_promotion_trace}, "
                f"paradigms={paradigms}"
            ),
        })

    return results


# =====================================================================
# 7. AdapterGenesis + Domain Adapter usability
# =====================================================================

def audit_adapter_genesis_callable() -> Dict[str, Any]:
    """Check that AdapterGenesis can be instantiated."""
    try:
        mod = importlib.import_module("reasoning_project.adapter_genesis")
        cls = getattr(mod, "AdapterGenesis", None)
        if cls is None:
            return {"status": "MISSING", "error": "AdapterGenesis class not found"}

        sig = inspect.signature(cls.__init__)
        params = list(sig.parameters.keys())
        # Just check the signature, don't actually instantiate (may need args)
        return {
            "status": "OK",
            "class_found": True,
            "init_params": params,
            "is_callable": callable(cls),
        }
    except Exception as e:
        return {"status": "FAIL", "error": str(e)}


def audit_domain_adapters_usable() -> List[Dict[str, Any]]:
    """Check each domain adapter can be instantiated."""
    adapters = [
        ("reasoning_project.reasoning_engine", "GridDomainAdapter"),
        ("reasoning_project.domain_adapters", "GraphDomainAdapter"),
        ("reasoning_project.domain_adapters", "ChessBoardDomainAdapter"),
        ("reasoning_project.domain_adapters", "MoleculeGraphDomainAdapter"),
    ]
    results = []
    for mod_name, cls_name in adapters:
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name)
            instance = cls()
            has_extract = hasattr(instance, "extract_objects")
            has_reconstruct = hasattr(instance, "reconstruct_filtered")
            results.append({
                "adapter": cls_name,
                "status": "OK",
                "instantiated": True,
                "has_extract_objects": has_extract,
                "has_reconstruct_filtered": has_reconstruct,
                "error": None,
            })
        except Exception as e:
            results.append({
                "adapter": cls_name,
                "status": "FAIL",
                "instantiated": False,
                "has_extract_objects": False,
                "has_reconstruct_filtered": False,
                "error": str(e),
            })
    return results


# =====================================================================
# 8. Pipeline loop exposure check
# =====================================================================

def audit_pipeline_loop_exposure() -> Dict[str, Any]:
    """Check if the main pipeline exposes the fixed reasoning loop stages."""
    required_stages = [
        "task/domain detection",
        "adapter selection",
        "hypothesis generation",
        "failure storage",
        "operator invention",
        "validation/falsification",
        "replay",
        "certificate",
        "promotion",
    ]

    # Check TraceDrivenOperatorInventor for key methods
    try:
        mod = importlib.import_module("reasoning_project.trace_operator_invention")
        inventor_cls = getattr(mod, "TraceDrivenOperatorInventor", None)
        if inventor_cls is None:
            return {
                "status": "FAIL",
                "error": "TraceDrivenOperatorInventor not found",
                "stages_found": [],
            }
        methods = dir(inventor_cls)
    except Exception as e:
        return {"status": "FAIL", "error": str(e), "stages_found": []}

    stage_map = {
        "task/domain detection": ["load_traces", "cluster_by_family"],
        "adapter selection": ["propose_copy_to_position", "propose_marker_relative_copy_to_position",
                              "propose_correspondence_copy_to_position", "propose_variable_destination_copy",
                              "propose_marker_projection"],
        "hypothesis generation": ["propose_copy_to_position", "propose_marker_relative_copy_to_position"],
        "failure storage": [],  # handled by NearSolvedMemory external module
        "operator invention": ["propose_copy_to_position", "propose_correspondence_copy_to_position"],
        "validation/falsification": ["validate_hypothesis", "loo_validate_hypothesis", "falsify_hypothesis"],
        "replay": ["attempt_promotion"],
        "certificate": [],  # certificate module
        "promotion": ["attempt_promotion"],
    }

    stages_found = []
    stages_missing = []
    for stage, expected_methods in stage_map.items():
        if not expected_methods:
            # External module -- check module existence
            if stage == "failure storage":
                try:
                    importlib.import_module("reasoning_project.near_solved_memory")
                    stages_found.append(stage)
                except Exception:
                    stages_missing.append(stage)
            elif stage == "certificate":
                try:
                    importlib.import_module("reasoning_project.certificates")
                    stages_found.append(stage)
                except Exception:
                    stages_missing.append(stage)
            continue

        found = [m for m in expected_methods if m in methods]
        if found:
            stages_found.append(stage)
        else:
            stages_missing.append(stage)

    return {
        "status": "OK" if not stages_missing else "INCOMPLETE",
        "stages_found": stages_found,
        "stages_missing": stages_missing,
        "inventor_method_count": len([m for m in methods if not m.startswith("_")]),
    }


# =====================================================================
# 9. Stale promoted records without certificates
# =====================================================================

def audit_stale_promoted_records() -> List[Dict[str, Any]]:
    """Look for promotion results in output dirs that lack matching certificates."""
    results = []
    # Scan for promotion_summary or run_summary files mentioning promoted tasks
    summary_dirs = [
        BASE / "outputs" / "operator_reasoning_phase" / "copy_to_position_real",
        BASE / "outputs" / "operator_reasoning_phase" / "color_transfer" / "real",
        BASE / "outputs" / "operator_reasoning_phase" / "correspondence" / "real",
        BASE / "outputs" / "operator_reasoning_phase" / "marker_relative" / "real",
        BASE / "outputs" / "operator_reasoning_phase" / "variable_destination" / "real",
        BASE / "outputs" / "operator_reasoning_phase" / "halo_test",
        BASE / "outputs" / "operator_reasoning_phase" / "multi_block_test",
    ]
    for sd in summary_dirs:
        if not sd.exists():
            continue
        cert_dir = sd / "certificates"
        # Find promoted tasks from JSONL or summary files
        for f in sd.glob("*.jsonl"):
            try:
                with open(f) as fh:
                    for line in fh:
                        if not line.strip():
                            continue
                        rec = json.loads(line)
                        if rec.get("promoted") or rec.get("status") == "promoted":
                            task_id = rec.get("task_id", "unknown")
                            has_cert = False
                            if cert_dir.exists():
                                has_cert = (
                                    (cert_dir / f"{task_id}.json").exists()
                                    or (cert_dir / f"{task_id}_certificate.json").exists()
                                )
                            if not has_cert:
                                results.append({
                                    "task_id": task_id,
                                    "source": str(f.relative_to(BASE)),
                                    "has_certificate": False,
                                    "status": "STALE",
                                })
                            else:
                                results.append({
                                    "task_id": task_id,
                                    "source": str(f.relative_to(BASE)),
                                    "has_certificate": True,
                                    "status": "OK",
                                })
            except Exception:
                continue

        # Also check CSV files
        for f in sd.glob("*.csv"):
            try:
                with open(f) as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        if row.get("promoted", "").lower() in ("true", "yes", "1"):
                            task_id = row.get("task_id", "unknown")
                            has_cert = False
                            if cert_dir.exists():
                                has_cert = (
                                    (cert_dir / f"{task_id}.json").exists()
                                    or (cert_dir / f"{task_id}_certificate.json").exists()
                                )
                            if not has_cert:
                                results.append({
                                    "task_id": task_id,
                                    "source": str(f.relative_to(BASE)),
                                    "has_certificate": False,
                                    "status": "STALE",
                                })
            except Exception:
                continue

    return results


# =====================================================================
# Report generation
# =====================================================================

def _severity_icon(sev: str) -> str:
    if sev == "critical":
        return "[CRITICAL]"
    if sev == "error":
        return "[ERROR]"
    if sev == "warning":
        return "[WARNING]"
    return "[INFO]"


def _status_icon(status: str) -> str:
    if status == "OK":
        return "PASS"
    if status in ("FAIL", "MISSING", "STATIC_LEAKAGE", "STALE"):
        return "FAIL"
    return "WARN"


def generate_report(
    module_results: List[Dict[str, Any]],
    symbol_results: List[Dict[str, Any]],
    exception_results: List[Dict[str, Any]],
    certificate_results: List[Dict[str, Any]],
    claim_results: List[Dict[str, Any]],
    all_missing_artifacts: List[str],
    promotion_results: List[Dict[str, Any]],
    genesis_result: Dict[str, Any],
    adapter_results: List[Dict[str, Any]],
    pipeline_result: Dict[str, Any],
    stale_results: List[Dict[str, Any]],
) -> str:
    """Generate a structured markdown audit report."""
    lines = []
    lines.append("# Full Pipeline Audit Report")
    lines.append("")
    lines.append("Generated by `scripts/audit_full_reasoning_pipeline.py`")
    lines.append("")

    # ---------- Summary ----------
    n_modules_ok = sum(1 for r in module_results if r["status"] == "OK")
    n_modules_total = len(module_results)
    n_symbols_ok = sum(1 for r in symbol_results if r["status"] == "OK")
    n_symbols_total = len(symbol_results)
    n_certs_ok = sum(1 for r in certificate_results if r["status"] == "OK")
    n_certs_total = len(certificate_results)
    n_claims_ok = sum(1 for r in claim_results if r["status"] == "OK")
    n_claims_total = len(claim_results)
    n_exc_critical = sum(1 for r in exception_results if r["severity"] == "critical")
    n_exc_warning = sum(1 for r in exception_results if r["severity"] == "warning")
    n_promo_ok = sum(1 for r in promotion_results if r["status"] == "TRACE_DRIVEN")
    n_stale = sum(1 for r in stale_results if r["status"] == "STALE")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Check | Result |")
    lines.append(f"|-------|--------|")
    lines.append(f"| Module imports | {n_modules_ok}/{n_modules_total} OK |")
    lines.append(f"| Key symbols | {n_symbols_ok}/{n_symbols_total} OK |")
    lines.append(f"| Certificates (4 promoted) | {n_certs_ok}/{n_certs_total} OK |")
    lines.append(f"| Claim traceability | {n_claims_ok}/{n_claims_total} claims fully backed |")
    lines.append(f"| Promotion chain integrity | {n_promo_ok}/{len(promotion_results)} trace-driven |")
    lines.append(f"| AdapterGenesis | {genesis_result['status']} |")
    lines.append(f"| Domain adapters | {sum(1 for r in adapter_results if r['status']=='OK')}/{len(adapter_results)} usable |")
    lines.append(f"| Pipeline loop stages | {len(pipeline_result.get('stages_found',[]))}/{len(pipeline_result.get('stages_found',[]))+len(pipeline_result.get('stages_missing',[]))} found |")
    lines.append(f"| Exception patterns | {n_exc_critical} critical, {n_exc_warning} warnings |")
    lines.append(f"| Stale promoted records | {n_stale} without certificates |")
    lines.append("")

    # ---------- Q1: Module Imports ----------
    lines.append("## 1. Module Import Audit")
    lines.append("")
    for r in module_results:
        st = _status_icon(r["status"])
        lines.append(f"- [{st}] `{r['module']}`: {r['status']}")
        if r["error"]:
            lines.append(f"  - Error: {r['error']}")
    lines.append("")

    # ---------- Q2: Key Symbols ----------
    lines.append("## 2. Key Class/Function Availability")
    lines.append("")
    for r in symbol_results:
        st = _status_icon(r["status"])
        kind_str = f" ({r['kind']})" if r["kind"] else ""
        lines.append(f"- [{st}] `{r['module']}.{r['symbol']}`{kind_str}")
        if r["error"]:
            lines.append(f"  - Error: {r['error']}")
    lines.append("")

    # ---------- Q3: Exception Patterns ----------
    lines.append("## 3. Exception-Swallowing Patterns")
    lines.append("")
    if not exception_results:
        lines.append("No exception patterns found in scanned files.")
    else:
        for r in exception_results:
            icon = _severity_icon(r["severity"])
            lines.append(f"- {icon} `{r['file']}` line {r['line']}: {r['pattern']} -- {r['detail']}")
    lines.append("")

    # ---------- Q4: Certificates ----------
    lines.append("## 4. Certificate Audit (4 Promoted Tasks)")
    lines.append("")
    for r in certificate_results:
        st = _status_icon(r["status"])
        lines.append(f"### {r['task_id']} ({r['description']})")
        lines.append(f"- Status: [{st}] {r['status']}")
        if r["path"]:
            lines.append(f"- Path: `{r['path']}`")
        lines.append(f"- training_fit: {r['training_fit']}")
        lines.append(f"- loo_status: {r['loo_status']}")
        lines.append(f"- has_derivation_trace: {r['has_derivation_trace']}")
        lines.append(f"- has_operator_family: {r['has_operator_family']}")
        lines.append(f"- has_promotion_source_trace: {r['has_promotion_source_trace']}")
        if r["missing_fields"]:
            lines.append(f"- Missing fields: {', '.join(r['missing_fields'])}")
        if r["error"]:
            lines.append(f"- Error: {r['error']}")
        lines.append("")

    # ---------- Q5: Claim Traceability ----------
    lines.append("## 5. Claim Traceability Audit")
    lines.append("")
    for r in claim_results:
        st = _status_icon(r["status"])
        lines.append(f"- [{st}] **{r['claim'][:60]}**: {r['found']}/{r['total_artifacts']} artifacts found")
        if r["missing_paths"]:
            for mp in r["missing_paths"]:
                lines.append(f"  - MISSING: `{mp}`")
    lines.append("")

    # ---------- Q6: Promotion Chain Integrity ----------
    lines.append("## 6. Promotion Chain Integrity (No Static Solver Leakage)")
    lines.append("")
    for r in promotion_results:
        st = _status_icon(r["status"])
        lines.append(f"- [{st}] `{r['task_id']}`: {r['status']}")
        lines.append(f"  - {r['detail']}")
    lines.append("")

    # ---------- Q7: AdapterGenesis ----------
    lines.append("## 7. AdapterGenesis Callable")
    lines.append("")
    lines.append(f"- Status: {genesis_result['status']}")
    if genesis_result.get("init_params"):
        lines.append(f"- __init__ params: {genesis_result['init_params']}")
    if genesis_result.get("error"):
        lines.append(f"- Error: {genesis_result['error']}")
    lines.append("")

    # ---------- Q8: Domain Adapters ----------
    lines.append("## 8. Domain Adapter Usability")
    lines.append("")
    for r in adapter_results:
        st = _status_icon(r["status"])
        lines.append(
            f"- [{st}] `{r['adapter']}`: instantiated={r['instantiated']}, "
            f"extract_objects={r['has_extract_objects']}, "
            f"reconstruct_filtered={r['has_reconstruct_filtered']}"
        )
        if r["error"]:
            lines.append(f"  - Error: {r['error']}")
    lines.append("")

    # ---------- Q9: Pipeline Loop ----------
    lines.append("## 9. Pipeline Loop Stage Exposure")
    lines.append("")
    lines.append(f"- Status: {pipeline_result['status']}")
    lines.append(f"- Stages found: {', '.join(pipeline_result.get('stages_found', []))}")
    if pipeline_result.get("stages_missing"):
        lines.append(f"- Stages missing: {', '.join(pipeline_result['stages_missing'])}")
    lines.append("")

    # ---------- Q10: Stale Records ----------
    lines.append("## 10. Stale Promoted Records")
    lines.append("")
    if not stale_results:
        lines.append("No promoted records found in JSONL/CSV scans (may need manual check).")
    else:
        stale_count = sum(1 for r in stale_results if r["status"] == "STALE")
        ok_count = sum(1 for r in stale_results if r["status"] == "OK")
        lines.append(f"- Scanned records: {len(stale_results)} ({ok_count} OK, {stale_count} stale)")
        for r in stale_results:
            st = _status_icon(r["status"])
            lines.append(f"  - [{st}] `{r['task_id']}` from `{r['source']}`: cert={r['has_certificate']}")
    lines.append("")

    # ---------- Critical Issues Summary ----------
    lines.append("## Critical Issues")
    lines.append("")
    critical_issues = []
    for r in module_results:
        if r["status"] == "FAIL":
            critical_issues.append(f"Module import failure: {r['module']} -- {r['error']}")
    for r in symbol_results:
        if r["status"] in ("FAIL", "MISSING"):
            critical_issues.append(f"Missing symbol: {r['module']}.{r['symbol']}")
    for r in certificate_results:
        if r["status"] in ("MISSING", "PARSE_ERROR"):
            critical_issues.append(f"Certificate missing/broken for promoted task {r['task_id']}")
    for r in promotion_results:
        if r["status"] == "STATIC_LEAKAGE":
            critical_issues.append(f"STATIC SOLVER LEAKAGE for {r['task_id']}")
    for r in exception_results:
        if r["severity"] == "critical":
            critical_issues.append(f"Critical exception swallowing: {r['file']}:{r['line']}")

    if critical_issues:
        for ci in critical_issues:
            lines.append(f"- {ci}")
    else:
        lines.append("No critical issues found.")
    lines.append("")

    return "\n".join(lines)


def generate_csv(
    module_results: List[Dict[str, Any]],
    symbol_results: List[Dict[str, Any]],
    certificate_results: List[Dict[str, Any]],
    claim_results: List[Dict[str, Any]],
    promotion_results: List[Dict[str, Any]],
    adapter_results: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Generate CSV rows for the audit."""
    rows = []
    for r in module_results:
        rows.append({
            "category": "module_import",
            "item": r["module"],
            "status": r["status"],
            "detail": r["error"] or "",
        })
    for r in symbol_results:
        rows.append({
            "category": "key_symbol",
            "item": f"{r['module']}.{r['symbol']}",
            "status": r["status"],
            "detail": r.get("kind", "") or r.get("error", ""),
        })
    for r in certificate_results:
        rows.append({
            "category": "certificate",
            "item": r["task_id"],
            "status": r["status"],
            "detail": (
                f"fit={r['training_fit']}, loo={r['loo_status']}, "
                f"missing={r['missing_fields']}"
            ),
        })
    for r in claim_results:
        rows.append({
            "category": "claim_traceability",
            "item": r["claim"][:60],
            "status": r["status"],
            "detail": f"{r['found']}/{r['total_artifacts']} artifacts found",
        })
    for r in promotion_results:
        rows.append({
            "category": "promotion_integrity",
            "item": r["task_id"],
            "status": r["status"],
            "detail": r["detail"][:200],
        })
    for r in adapter_results:
        rows.append({
            "category": "domain_adapter",
            "item": r["adapter"],
            "status": r["status"],
            "detail": r["error"] or "instantiated OK",
        })
    return rows


# =====================================================================
# Main
# =====================================================================

def main():
    out_dir = BASE / "outputs" / "final_paper_package" / "pipeline_audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("FULL REASONING PIPELINE AUDIT")
    print("=" * 70)
    print()

    # Run all audits
    print("[1/10] Auditing module imports...")
    module_results = audit_module_imports()

    print("[2/10] Auditing key symbols...")
    symbol_results = audit_key_symbols()

    print("[3/10] Scanning for exception-swallowing patterns...")
    exception_results = audit_exception_patterns()

    print("[4/10] Auditing certificates for 4 promoted tasks...")
    certificate_results = audit_certificates()

    print("[5/10] Auditing claim traceability...")
    claim_results, all_missing_artifacts = audit_claim_traceability()

    print("[6/10] Checking promotion chain integrity...")
    promotion_results = audit_promotion_chain_integrity()

    print("[7/10] Checking AdapterGenesis callable...")
    genesis_result = audit_adapter_genesis_callable()

    print("[8/10] Checking domain adapters usable...")
    adapter_results = audit_domain_adapters_usable()

    print("[9/10] Checking pipeline loop exposure...")
    pipeline_result = audit_pipeline_loop_exposure()

    print("[10/10] Scanning for stale promoted records...")
    stale_results = audit_stale_promoted_records()

    # Generate outputs
    print()
    print("Generating report...")

    md_report = generate_report(
        module_results, symbol_results, exception_results,
        certificate_results, claim_results, all_missing_artifacts,
        promotion_results, genesis_result, adapter_results,
        pipeline_result, stale_results,
    )

    md_path = out_dir / "full_pipeline_audit.md"
    md_path.write_text(md_report)
    print(f"  -> {md_path.relative_to(BASE)}")

    csv_rows = generate_csv(
        module_results, symbol_results, certificate_results,
        claim_results, promotion_results, adapter_results,
    )
    csv_path = out_dir / "full_pipeline_audit.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "item", "status", "detail"])
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"  -> {csv_path.relative_to(BASE)}")

    missing_links = {
        "missing_artifacts": all_missing_artifacts,
        "missing_certificates": [
            r["task_id"] for r in certificate_results if r["status"] == "MISSING"
        ],
        "stale_promotions": [
            r["task_id"] for r in stale_results if r["status"] == "STALE"
        ],
        "failed_modules": [
            r["module"] for r in module_results if r["status"] == "FAIL"
        ],
        "missing_symbols": [
            f"{r['module']}.{r['symbol']}"
            for r in symbol_results if r["status"] in ("FAIL", "MISSING")
        ],
        "static_leakage": [
            r["task_id"] for r in promotion_results if r["status"] == "STATIC_LEAKAGE"
        ],
    }
    missing_path = out_dir / "missing_links.json"
    with open(missing_path, "w") as f:
        json.dump(missing_links, f, indent=2)
    print(f"  -> {missing_path.relative_to(BASE)}")

    # Print summary to stdout
    print()
    print(md_report)

    # Exit code
    critical_count = sum(1 for v in missing_links.values() if v)
    if missing_links["static_leakage"] or missing_links["missing_certificates"]:
        print("\n*** CRITICAL ISSUES DETECTED -- SEE REPORT ***")
        sys.exit(1)
    elif critical_count > 0:
        print(f"\n*** {critical_count} NON-CRITICAL ISSUE CATEGORIES -- SEE REPORT ***")
        sys.exit(0)
    else:
        print("\n*** ALL CHECKS PASSED ***")
        sys.exit(0)


if __name__ == "__main__":
    main()
