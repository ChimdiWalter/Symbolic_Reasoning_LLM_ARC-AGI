"""Typed domain morphisms for cross-domain operator transfer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from reasoning_project.reasoning_engine import DomainAdapter, GridDomainAdapter
from reasoning_project.domain_adapters import (
    GraphDomainAdapter,
    ChessBoardDomainAdapter,
    MoleculeGraphDomainAdapter,
)


@dataclass
class DomainObjectType:
    name: str
    properties: List[str]
    spatial: bool
    has_size: bool
    has_color: bool


@dataclass
class DomainRelationType:
    name: str
    arity: int
    symmetric: bool
    locality: str  # "local", "global", "spatial"


@dataclass
class DomainFeatureType:
    name: str
    dtype: str  # "int", "float", "bool", "categorical"
    transferable: bool


@dataclass
class DomainOperatorHook:
    name: str
    input_types: List[str]
    output_types: List[str]
    requires_relation: Optional[str] = None
    requires_feature: Optional[str] = None


@dataclass
class DomainSignatureTyped:
    domain_name: str
    object_types: List[DomainObjectType]
    relation_types: List[DomainRelationType]
    feature_types: List[DomainFeatureType]
    operator_hooks: List[DomainOperatorHook]
    base_signature: Optional[Any] = None


@dataclass
class TypeMapping:
    source_type: str
    target_type: str
    kind: str  # "object", "relation", "feature"
    confidence: float
    justification: str


@dataclass
class DomainMorphism:
    source_domain: str
    target_domain: str
    object_mappings: List[TypeMapping] = field(default_factory=list)
    relation_mappings: List[TypeMapping] = field(default_factory=list)
    feature_mappings: List[TypeMapping] = field(default_factory=list)
    operator_hook_mappings: List[TypeMapping] = field(default_factory=list)
    score: float = 0.0
    validated: bool = False
    rejected: bool = False
    rejection_reason: str = ""


@dataclass
class MorphismValidationResult:
    morphism: DomainMorphism
    valid: bool
    obligations_checked: int
    obligations_passed: int
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ── Domain-specific relation/feature knowledge ─────────────────────────

_DOMAIN_RELATIONS: Dict[str, List[DomainRelationType]] = {
    "grid": [
        DomainRelationType("adjacency", 2, True, "local"),
        DomainRelationType("spatial_neighbor", 2, True, "spatial"),
        DomainRelationType("containment", 2, False, "spatial"),
    ],
    "graph": [
        DomainRelationType("adjacency", 2, True, "local"),
        DomainRelationType("path_connectivity", 2, True, "global"),
    ],
    "chess": [
        DomainRelationType("adjacency", 2, True, "spatial"),
        DomainRelationType("attack", 2, False, "global"),
        DomainRelationType("protection", 2, False, "global"),
    ],
    "molecule": [
        DomainRelationType("bond", 2, True, "local"),
        DomainRelationType("ring_membership", 2, True, "global"),
    ],
}

_DOMAIN_FEATURES: Dict[str, List[DomainFeatureType]] = {
    "grid": [
        DomainFeatureType("color", "int", True),
        DomainFeatureType("size", "int", True),
        DomainFeatureType("position", "int", False),
    ],
    "graph": [
        DomainFeatureType("color", "int", True),
        DomainFeatureType("degree", "int", True),
    ],
    "chess": [
        DomainFeatureType("color", "int", True),
        DomainFeatureType("size", "int", True),
        DomainFeatureType("position", "int", False),
    ],
    "molecule": [
        DomainFeatureType("color", "int", True),
        DomainFeatureType("degree", "int", True),
        DomainFeatureType("bond_type", "categorical", False),
    ],
}

_DOMAIN_HOOKS: Dict[str, List[DomainOperatorHook]] = {
    "grid": [
        DomainOperatorHook("filter_by_property", ["scene_objects"], ["filtered_objects"],
                           requires_relation="membership_predicate",
                           requires_feature="discriminative_property"),
        DomainOperatorHook("project_to_neighbor", ["source_object", "scene_objects"],
                           ["scene_objects"], requires_relation="adjacency",
                           requires_feature="projectable_property"),
    ],
    "graph": [
        DomainOperatorHook("filter_by_property", ["scene_objects"], ["filtered_objects"],
                           requires_relation="membership_predicate",
                           requires_feature="discriminative_property"),
        DomainOperatorHook("project_to_neighbor", ["source_object", "scene_objects"],
                           ["scene_objects"], requires_relation="adjacency",
                           requires_feature="projectable_property"),
    ],
    "chess": [
        DomainOperatorHook("filter_by_property", ["scene_objects"], ["filtered_objects"],
                           requires_relation="membership_predicate",
                           requires_feature="discriminative_property"),
    ],
    "molecule": [
        DomainOperatorHook("filter_by_property", ["scene_objects"], ["filtered_objects"],
                           requires_relation="membership_predicate",
                           requires_feature="discriminative_property"),
    ],
}


def _detect_domain_name(adapter: DomainAdapter) -> str:
    if isinstance(adapter, GridDomainAdapter):
        return "grid"
    if isinstance(adapter, GraphDomainAdapter):
        return "graph"
    if isinstance(adapter, ChessBoardDomainAdapter):
        return "chess"
    if isinstance(adapter, MoleculeGraphDomainAdapter):
        return "molecule"
    return "unknown"


class DomainSignatureExtractorTyped:

    def extract(
        self,
        adapter: DomainAdapter,
        domain_name: Optional[str] = None,
        sample_scenes: Optional[List[Any]] = None,
    ) -> DomainSignatureTyped:
        if domain_name is None:
            domain_name = _detect_domain_name(adapter)

        props = adapter.property_names()

        obj_type = DomainObjectType(
            name=f"{domain_name}_object",
            properties=list(props),
            spatial=domain_name in ("grid", "chess"),
            has_size="is_largest" in props or "is_smallest" in props,
            has_color="is_unique_color" in props or "is_most_common_color" in props,
        )

        relations = _DOMAIN_RELATIONS.get(domain_name, [
            DomainRelationType("adjacency", 2, True, "local"),
        ])
        features = _DOMAIN_FEATURES.get(domain_name, [
            DomainFeatureType("color", "int", True),
        ])
        hooks = _DOMAIN_HOOKS.get(domain_name, [])

        return DomainSignatureTyped(
            domain_name=domain_name,
            object_types=[obj_type],
            relation_types=relations,
            feature_types=features,
            operator_hooks=hooks,
        )


class DomainMorphismLearner:

    def propose_morphisms(
        self,
        source: DomainSignatureTyped,
        target: DomainSignatureTyped,
        max_proposals: int = 10,
    ) -> List[DomainMorphism]:
        proposals = []
        obj_mappings = self._match_object_types(source, target)
        rel_mappings = self._match_relation_types(source, target)
        feat_mappings = self._match_feature_types(source, target)
        hook_mappings = self._match_operator_hooks(source, target)

        morphism = DomainMorphism(
            source_domain=source.domain_name,
            target_domain=target.domain_name,
            object_mappings=obj_mappings,
            relation_mappings=rel_mappings,
            feature_mappings=feat_mappings,
            operator_hook_mappings=hook_mappings,
        )
        morphism.score = self.score_morphism(morphism, source, target)
        proposals.append(morphism)

        if len(rel_mappings) > 1:
            for i, rm in enumerate(rel_mappings):
                alt = DomainMorphism(
                    source_domain=source.domain_name,
                    target_domain=target.domain_name,
                    object_mappings=obj_mappings,
                    relation_mappings=[rm],
                    feature_mappings=feat_mappings,
                    operator_hook_mappings=hook_mappings,
                )
                alt.score = self.score_morphism(alt, source, target)
                proposals.append(alt)

        return proposals[:max_proposals]

    def score_morphism(
        self,
        morphism: DomainMorphism,
        source: DomainSignatureTyped,
        target: DomainSignatureTyped,
    ) -> float:
        total = 0.0
        n = 0

        for m in morphism.object_mappings:
            total += m.confidence
            n += 1
        for m in morphism.relation_mappings:
            total += m.confidence
            n += 1
        for m in morphism.feature_mappings:
            total += m.confidence
            n += 1
        for m in morphism.operator_hook_mappings:
            total += m.confidence
            n += 1

        if n == 0:
            return 0.0

        coverage_src = 0
        coverage_tgt = 0
        src_types = len(source.object_types) + len(source.relation_types) + len(source.feature_types)
        tgt_types = len(target.object_types) + len(target.relation_types) + len(target.feature_types)
        mapped_src = len({m.source_type for m in morphism.object_mappings} |
                         {m.source_type for m in morphism.relation_mappings} |
                         {m.source_type for m in morphism.feature_mappings})
        mapped_tgt = len({m.target_type for m in morphism.object_mappings} |
                         {m.target_type for m in morphism.relation_mappings} |
                         {m.target_type for m in morphism.feature_mappings})

        cov_s = mapped_src / max(src_types, 1)
        cov_t = mapped_tgt / max(tgt_types, 1)

        return (total / n) * 0.6 + (cov_s + cov_t) / 2.0 * 0.4

    def reject_ambiguous(
        self, morphisms: List[DomainMorphism],
    ) -> List[DomainMorphism]:
        accepted = []
        for m in morphisms:
            dup = self._has_duplicate_target(m)
            if dup:
                m.rejected = True
                m.rejection_reason = f"ambiguous duplicate target mapping: {dup}"
            elif not m.object_mappings:
                m.rejected = True
                m.rejection_reason = "no object mappings"
            else:
                accepted.append(m)
        return accepted

    def validate_morphism(
        self,
        morphism: DomainMorphism,
        source: DomainSignatureTyped,
        target: DomainSignatureTyped,
    ) -> MorphismValidationResult:
        failures: List[str] = []
        warnings: List[str] = []
        checked = 0
        passed = 0

        src_obj_names = {ot.name for ot in source.object_types}
        tgt_obj_names = {ot.name for ot in target.object_types}
        for m in morphism.object_mappings:
            checked += 1
            if m.source_type not in src_obj_names:
                failures.append(f"source object type '{m.source_type}' not in source signature")
            elif m.target_type not in tgt_obj_names:
                failures.append(f"target object type '{m.target_type}' not in target signature")
            else:
                passed += 1

        src_rel = {rt.name: rt for rt in source.relation_types}
        tgt_rel = {rt.name: rt for rt in target.relation_types}
        for m in morphism.relation_mappings:
            checked += 1
            sr = src_rel.get(m.source_type)
            tr = tgt_rel.get(m.target_type)
            if sr is None:
                failures.append(f"source relation '{m.source_type}' not in source signature")
            elif tr is None:
                failures.append(f"target relation '{m.target_type}' not in target signature")
            elif sr.arity != tr.arity:
                failures.append(
                    f"arity mismatch: {m.source_type}({sr.arity}) -> {m.target_type}({tr.arity})"
                )
            else:
                passed += 1
                if sr.locality != tr.locality:
                    warnings.append(
                        f"locality change: {m.source_type}({sr.locality}) -> {m.target_type}({tr.locality})"
                    )

        src_feat = {ft.name: ft for ft in source.feature_types}
        tgt_feat = {ft.name: ft for ft in target.feature_types}
        for m in morphism.feature_mappings:
            checked += 1
            sf = src_feat.get(m.source_type)
            tf = tgt_feat.get(m.target_type)
            if sf is None:
                failures.append(f"source feature '{m.source_type}' not in source signature")
            elif tf is None:
                failures.append(f"target feature '{m.target_type}' not in target signature")
            elif not self._dtypes_compatible(sf.dtype, tf.dtype):
                failures.append(
                    f"dtype incompatible: {m.source_type}({sf.dtype}) -> {m.target_type}({tf.dtype})"
                )
            else:
                passed += 1

        dup = self._has_duplicate_target(morphism)
        if dup:
            checked += 1
            failures.append(f"ambiguous duplicate target: {dup}")
        else:
            checked += 1
            passed += 1

        valid = len(failures) == 0
        if valid:
            morphism.validated = True
        return MorphismValidationResult(
            morphism=morphism,
            valid=valid,
            obligations_checked=checked,
            obligations_passed=passed,
            failures=failures,
            warnings=warnings,
        )

    def _match_object_types(
        self, source: DomainSignatureTyped, target: DomainSignatureTyped,
    ) -> List[TypeMapping]:
        mappings = []
        for src_ot in source.object_types:
            best_tgt = None
            best_conf = 0.0
            for tgt_ot in target.object_types:
                shared = set(src_ot.properties) & set(tgt_ot.properties)
                total = set(src_ot.properties) | set(tgt_ot.properties)
                jaccard = len(shared) / max(len(total), 1)
                struct_bonus = 0.0
                if src_ot.has_size == tgt_ot.has_size:
                    struct_bonus += 0.1
                if src_ot.has_color == tgt_ot.has_color:
                    struct_bonus += 0.1
                conf = jaccard * 0.8 + struct_bonus
                if conf > best_conf:
                    best_conf = conf
                    best_tgt = tgt_ot
            if best_tgt is not None and best_conf > 0.0:
                mappings.append(TypeMapping(
                    source_type=src_ot.name,
                    target_type=best_tgt.name,
                    kind="object",
                    confidence=min(best_conf, 1.0),
                    justification=f"property overlap + structural match",
                ))
        return mappings

    def _match_relation_types(
        self, source: DomainSignatureTyped, target: DomainSignatureTyped,
    ) -> List[TypeMapping]:
        candidates = []
        for src_rt in source.relation_types:
            for tgt_rt in target.relation_types:
                conf = 0.0
                if src_rt.arity == tgt_rt.arity:
                    conf += 0.4
                if src_rt.symmetric == tgt_rt.symmetric:
                    conf += 0.2
                if src_rt.locality == tgt_rt.locality:
                    conf += 0.3
                if src_rt.name == tgt_rt.name:
                    conf += 0.1
                if conf >= 0.6:
                    candidates.append((conf, src_rt, tgt_rt))
        candidates.sort(key=lambda x: -x[0])
        used_src: set = set()
        used_tgt: set = set()
        mappings = []
        for conf, src_rt, tgt_rt in candidates:
            if src_rt.name in used_src or tgt_rt.name in used_tgt:
                continue
            used_src.add(src_rt.name)
            used_tgt.add(tgt_rt.name)
            mappings.append(TypeMapping(
                source_type=src_rt.name,
                target_type=tgt_rt.name,
                kind="relation",
                confidence=min(conf, 1.0),
                justification=f"arity={src_rt.arity}=={tgt_rt.arity}, "
                              f"locality={src_rt.locality}->{tgt_rt.locality}",
            ))
        return mappings

    def _match_feature_types(
        self, source: DomainSignatureTyped, target: DomainSignatureTyped,
    ) -> List[TypeMapping]:
        candidates = []
        for src_ft in source.feature_types:
            for tgt_ft in target.feature_types:
                if not self._dtypes_compatible(src_ft.dtype, tgt_ft.dtype):
                    continue
                conf = 0.0
                if src_ft.name == tgt_ft.name:
                    conf = 1.0
                elif src_ft.dtype == tgt_ft.dtype:
                    conf = 0.7
                else:
                    conf = 0.5
                if src_ft.transferable and tgt_ft.transferable:
                    conf = min(conf + 0.1, 1.0)
                candidates.append((conf, src_ft, tgt_ft))
        candidates.sort(key=lambda x: -x[0])
        used_src: set = set()
        used_tgt: set = set()
        mappings = []
        for conf, src_ft, tgt_ft in candidates:
            if src_ft.name in used_src or tgt_ft.name in used_tgt:
                continue
            used_src.add(src_ft.name)
            used_tgt.add(tgt_ft.name)
            mappings.append(TypeMapping(
                source_type=src_ft.name,
                target_type=tgt_ft.name,
                kind="feature",
                confidence=conf,
                justification=f"dtype {src_ft.dtype}->{tgt_ft.dtype}",
            ))
        return mappings

    def _match_operator_hooks(
        self, source: DomainSignatureTyped, target: DomainSignatureTyped,
    ) -> List[TypeMapping]:
        mappings = []
        for src_h in source.operator_hooks:
            for tgt_h in target.operator_hooks:
                if src_h.name == tgt_h.name:
                    mappings.append(TypeMapping(
                        source_type=src_h.name,
                        target_type=tgt_h.name,
                        kind="operator_hook",
                        confidence=1.0,
                        justification="same hook name",
                    ))
        return mappings

    def _has_duplicate_target(self, m: DomainMorphism) -> str:
        for kind, maps in [
            ("object", m.object_mappings),
            ("relation", m.relation_mappings),
            ("feature", m.feature_mappings),
        ]:
            targets = [mp.target_type for mp in maps]
            seen: Dict[str, int] = {}
            for t in targets:
                seen[t] = seen.get(t, 0) + 1
            for t, count in seen.items():
                if count > 1:
                    return f"{kind}:{t} (x{count})"
        return ""

    @staticmethod
    def _dtypes_compatible(src: str, tgt: str) -> bool:
        if src == tgt:
            return True
        compatible = {
            ("int", "float"), ("float", "int"),
            ("bool", "int"), ("int", "bool"),
            ("bool", "float"),
        }
        return (src, tgt) in compatible
