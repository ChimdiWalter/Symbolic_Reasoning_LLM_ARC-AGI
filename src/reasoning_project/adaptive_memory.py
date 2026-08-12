"""Certified package store for adapter/operator combinations.

Stores verified (adapter_type, operator_family, selector) triples with
their proof certificates. Retrieval uses structural signature matching
so that a package proven on one task can be applied to structurally
similar tasks without re-derivation.

Architecture:
    CertifiedPackage  -- immutable record of a verified adapter+operator pair
    AdaptiveMemory    -- store/retrieve packages by signature matching
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class CertifiedPackage:
    """Immutable record of a verified adapter+operator combination."""

    memory_id: str
    source_task_id: str
    adapter_type: str
    adapter_signature: Dict[str, Any]
    operator_family: str
    selector_property: str
    preconditions: List[str]
    proof_obligations: List[str]
    certificate_path: str
    success_trace: Dict[str, Any]
    failure_modes: List[str]
    retrieval_signature: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        d = {}
        for k, v in self.__dict__.items():
            d[k] = v
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CertifiedPackage":
        """Deserialize from dict."""
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


def _compute_task_signature(
    train_pairs: List[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, Any]:
    """Compute a structural signature of a task for retrieval matching."""
    sig: Dict[str, Any] = {}
    sig["n_train"] = len(train_pairs)

    shapes_in = []
    shapes_out = []
    color_counts_in = []
    color_counts_out = []

    for inp, out in train_pairs:
        shapes_in.append(list(inp.shape))
        shapes_out.append(list(out.shape))
        colors_in = len(set(inp.flatten().tolist()) - {0})
        colors_out = len(set(out.flatten().tolist()) - {0})
        color_counts_in.append(colors_in)
        color_counts_out.append(colors_out)

    sig["input_shape_mean"] = [
        float(np.mean([s[0] for s in shapes_in])),
        float(np.mean([s[1] for s in shapes_in])),
    ]
    sig["output_shape_mean"] = [
        float(np.mean([s[0] for s in shapes_out])),
        float(np.mean([s[1] for s in shapes_out])),
    ]
    sig["same_shape"] = all(
        inp.shape == out.shape for inp, out in train_pairs
    )
    sig["mean_colors_in"] = float(np.mean(color_counts_in)) if color_counts_in else 0.0
    sig["mean_colors_out"] = float(np.mean(color_counts_out)) if color_counts_out else 0.0

    # Object count from connected components
    from scipy import ndimage
    obj_counts = []
    for inp, _ in train_pairs:
        _, n = ndimage.label(inp != 0)
        obj_counts.append(n)
    sig["mean_objects"] = float(np.mean(obj_counts)) if obj_counts else 0.0

    return sig


def _signature_distance(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """Compute distance between two task signatures."""
    dist = 0.0
    n_terms = 0

    # Numeric fields
    for key in ["n_train", "mean_colors_in", "mean_colors_out", "mean_objects"]:
        va = a.get(key, 0.0)
        vb = b.get(key, 0.0)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            denom = max(abs(va), abs(vb), 1.0)
            dist += ((va - vb) / denom) ** 2
            n_terms += 1

    # Shape fields
    for key in ["input_shape_mean", "output_shape_mean"]:
        va = a.get(key, [0.0, 0.0])
        vb = b.get(key, [0.0, 0.0])
        if isinstance(va, list) and isinstance(vb, list):
            for x, y in zip(va, vb):
                denom = max(abs(x), abs(y), 1.0)
                dist += ((x - y) / denom) ** 2
                n_terms += 1

    # Boolean fields
    for key in ["same_shape"]:
        va = a.get(key, False)
        vb = b.get(key, False)
        if va != vb:
            dist += 1.0
        n_terms += 1

    return (dist / max(n_terms, 1)) ** 0.5


class AdaptiveMemory:
    """Certified package store with signature-based retrieval.

    Stores adapter+operator packages that have been verified through
    the full ProposalVerifier chain. Retrieval matches task signatures
    so packages from one task can be applied to structurally similar ones.
    """

    def __init__(self):
        self._packages: List[CertifiedPackage] = []
        self._frozen: bool = False

    def store_verified_package(
        self,
        task_id: str,
        adapter: Any,
        operator_family: str,
        selector: str,
        certificate_path: str,
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> str:
        """Store a verified adapter+operator package.

        Returns the memory_id of the stored package.
        Raises RuntimeError if memory is frozen.
        """
        if self._frozen:
            raise RuntimeError("AdaptiveMemory is frozen; cannot store new packages")

        memory_id = str(uuid.uuid4())[:12]

        # Compute signatures
        adapter_sig = adapter.signature() if hasattr(adapter, "signature") else {
            "adapter_type": getattr(adapter, "adapter_type", "unknown")
        }
        task_sig = _compute_task_signature(train_pairs)

        # Derive preconditions from the adapter
        preconditions = []
        adapter_type = getattr(adapter, "adapter_type", "unknown")
        if adapter_type == "frame_interior":
            preconditions = ["has_rectangular_frame", "interior_has_objects"]
        elif adapter_type == "color_layer":
            preconditions = ["has_multiple_colors"]
        elif adapter_type == "object_in_object":
            preconditions = ["has_containment_relationship"]
        elif adapter_type == "symmetry_axis":
            preconditions = ["has_reflection_symmetry"]
        elif adapter_type == "repeated_motif":
            preconditions = ["has_tiled_motif"]

        package = CertifiedPackage(
            memory_id=memory_id,
            source_task_id=task_id,
            adapter_type=adapter_type,
            adapter_signature=adapter_sig,
            operator_family=operator_family,
            selector_property=selector,
            preconditions=preconditions,
            proof_obligations=[
                "train_consistency",
                "loo_validation",
                "falsification_robustness",
            ],
            certificate_path=certificate_path,
            success_trace={
                "task_id": task_id,
                "n_train": len(train_pairs),
            },
            failure_modes=[],
            retrieval_signature=task_sig,
        )
        self._packages.append(package)
        return memory_id

    def retrieve_by_signature(
        self, task_signature: Dict[str, Any], top_k: int = 5
    ) -> List[CertifiedPackage]:
        """Retrieve packages by task signature similarity."""
        if not self._packages:
            return []

        scored = []
        for pkg in self._packages:
            dist = _signature_distance(task_signature, pkg.retrieval_signature)
            scored.append((dist, pkg))
        scored.sort(key=lambda x: x[0])
        return [pkg for _, pkg in scored[:top_k]]

    def retrieve_by_adapter_signature(
        self, adapter_signature: Dict[str, Any], top_k: int = 5
    ) -> List[CertifiedPackage]:
        """Retrieve packages matching a specific adapter signature."""
        matches = []
        for pkg in self._packages:
            if pkg.adapter_type == adapter_signature.get("adapter_type"):
                matches.append(pkg)
        return matches[:top_k]

    def retrieve_by_failure_signature(
        self, failure_signature: Dict[str, Any], top_k: int = 5
    ) -> List[CertifiedPackage]:
        """Retrieve packages that might fix a given failure pattern.

        Matches adapter type from the failure's structural pattern.
        """
        if not self._packages:
            return []

        failure_type = failure_signature.get("failure_type", "")
        results = []

        for pkg in self._packages:
            relevance = 0.0
            if failure_type == "frame_masking" and pkg.adapter_type == "frame_interior":
                relevance = 1.0
            elif failure_type == "color_interference" and pkg.adapter_type == "color_layer":
                relevance = 1.0
            elif failure_type == "containment_invisible" and pkg.adapter_type == "object_in_object":
                relevance = 1.0
            elif failure_type == "symmetry_obscured" and pkg.adapter_type == "symmetry_axis":
                relevance = 1.0
            elif failure_type == "motif_scattered" and pkg.adapter_type == "repeated_motif":
                relevance = 1.0
            else:
                # Generic similarity-based fallback
                relevance = 0.3
            if relevance > 0:
                results.append((relevance, pkg))

        results.sort(key=lambda x: -x[0])
        return [pkg for _, pkg in results[:top_k]]

    def freeze(self) -> None:
        """Freeze memory: no new packages can be stored."""
        self._frozen = True

    def unfreeze(self) -> None:
        """Unfreeze memory."""
        self._frozen = False

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    def get_all(self) -> List[CertifiedPackage]:
        """Return all stored packages."""
        return list(self._packages)

    def to_manifest(self) -> List[Dict[str, Any]]:
        """Serialize all packages to a manifest."""
        return [pkg.to_dict() for pkg in self._packages]

    def save_manifest(self, path: str) -> None:
        """Save manifest to JSONL file."""
        with open(path, "w") as f:
            for pkg in self._packages:
                f.write(json.dumps(pkg.to_dict()) + "\n")

    def load_manifest(self, path: str) -> None:
        """Load packages from JSONL file."""
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    pkg = CertifiedPackage.from_dict(data)
                    self._packages.append(pkg)

    def __len__(self) -> int:
        return len(self._packages)

    # ─── Failure-to-view repair storage ─────────────────────────────────

    def store_failure_repair(
        self,
        source_task_id: str,
        failure_signature: Dict[str, Any],
        view_program_signature: Dict[str, Any],
        operator_family: str,
        selector_property: str,
        projection_rule: str,
        certificate_path: str,
        verification_summary: Dict[str, Any],
        train_pairs: List[Tuple[np.ndarray, np.ndarray]],
    ) -> str:
        """Store a verified failure-to-view repair package.

        A repair package records: this failure signature was fixed by
        this view program + this operator, with full verification.
        """
        if self._frozen:
            raise RuntimeError("AdaptiveMemory is frozen")

        memory_id = f"repair_{uuid.uuid4().hex[:10]}"
        task_sig = _compute_task_signature(train_pairs)

        package = CertifiedPackage(
            memory_id=memory_id,
            source_task_id=source_task_id,
            adapter_type=view_program_signature.get("view_type", "unknown"),
            adapter_signature=view_program_signature,
            operator_family=operator_family,
            selector_property=selector_property,
            preconditions=[
                f"failure_type:{failure_signature.get('dominant_failure', 'unknown')}",
            ],
            proof_obligations=[
                "train_consistency", "loo_validation",
                "proof_obligations", "falsification_or_test_match",
            ],
            certificate_path=certificate_path,
            success_trace={
                "task_id": source_task_id,
                "failure_signature": failure_signature,
                "view_program": view_program_signature,
                "projection_rule": projection_rule,
                "verification": verification_summary,
            },
            failure_modes=view_program_signature.get("failure_modes", []),
            retrieval_signature=task_sig,
        )
        self._packages.append(package)
        return memory_id

    def retrieve_by_view_program_signature(
        self, view_sig: Dict[str, Any], top_k: int = 5
    ) -> List[CertifiedPackage]:
        """Retrieve packages matching a ViewProgram signature."""
        matches = []
        target_type = view_sig.get("view_type", "")
        for pkg in self._packages:
            if pkg.adapter_signature.get("view_type") == target_type:
                matches.append(pkg)
        return matches[:top_k]

    def retrieve_verified_repairs(
        self, failure_sig: Dict[str, Any], top_k: int = 5
    ) -> List[CertifiedPackage]:
        """Retrieve verified repair packages by failure signature match.

        Prioritizes packages whose source failure signature matches the
        query failure signature's dominant_failure type.
        """
        if not self._packages:
            return []

        target_failure = failure_sig.get("dominant_failure", "")
        scored = []

        for pkg in self._packages:
            if not pkg.memory_id.startswith("repair_"):
                continue
            src_failure = pkg.success_trace.get("failure_signature", {})
            src_dominant = src_failure.get("dominant_failure", "")

            score = 0.0
            if src_dominant == target_failure and target_failure:
                score += 2.0
            if pkg.adapter_signature.get("view_type") in str(failure_sig.get("candidate_views", [])):
                score += 1.0

            task_dist = _signature_distance(
                failure_sig, pkg.retrieval_signature
            ) if isinstance(pkg.retrieval_signature, dict) else 10.0
            score += max(0, 1.0 - task_dist)

            if score > 0:
                scored.append((score, pkg))

        scored.sort(key=lambda x: -x[0])
        return [pkg for _, pkg in scored[:top_k]]
