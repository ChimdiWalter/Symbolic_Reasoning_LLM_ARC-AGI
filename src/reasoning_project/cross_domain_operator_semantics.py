"""Cross-domain operator semantics.

Defines domain-independent abstract operator families that can be
instantiated across grid, graph, chess, and molecule domains.

Families: ProjectToNeighborhood, CopyFeatureToCorrespondent,
FilterByRelation, MoveOrTransferToAnchor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class OperatorFamilyName(Enum):
    PROJECT_TO_NEIGHBORHOOD = auto()
    COPY_FEATURE_TO_CORRESPONDENT = auto()
    FILTER_BY_RELATION = auto()
    MOVE_OR_TRANSFER_TO_ANCHOR = auto()


@dataclass
class AbstractOperatorFamily:
    name: OperatorFamilyName
    description: str
    abstract_preconditions: List[str]
    abstract_postconditions: List[str]
    abstract_invariants: List[str]
    ambiguity_conditions: List[str]
    falsification_probes: List[str]
    certificate_fields: List[str]


@dataclass
class DomainRealization:
    domain: str
    family: OperatorFamilyName
    concrete_preconditions: List[str]
    concrete_postconditions: List[str]
    realize_fn: Optional[Callable] = None
    description: str = ""


@dataclass
class TransferResult:
    source_domain: str
    target_domain: str
    family: OperatorFamilyName
    schema_reuse_success: bool = False
    zero_shot_success: bool = False
    few_shot_success: bool = False
    tasks_attempted: int = 0
    tasks_solved: int = 0
    false_positives: int = 0
    failure_reason: Optional[str] = None


@dataclass
class TransferMatrix:
    entries: List[TransferResult] = field(default_factory=list)

    def add(self, result: TransferResult):
        self.entries.append(result)

    def success_count(self) -> int:
        return sum(1 for e in self.entries if e.tasks_solved > 0)

    def to_rows(self) -> List[Dict]:
        return [
            {
                "family": e.family.name,
                "source": e.source_domain,
                "target": e.target_domain,
                "schema_reuse": e.schema_reuse_success,
                "zero_shot": e.zero_shot_success,
                "few_shot": e.few_shot_success,
                "solved": e.tasks_solved,
                "attempted": e.tasks_attempted,
                "fp": e.false_positives,
                "failure": e.failure_reason or "",
            }
            for e in self.entries
        ]


# ---------------------------------------------------------------------------
# Abstract family definitions
# ---------------------------------------------------------------------------

OPERATOR_FAMILIES = {
    OperatorFamilyName.PROJECT_TO_NEIGHBORHOOD: AbstractOperatorFamily(
        name=OperatorFamilyName.PROJECT_TO_NEIGHBORHOOD,
        description="Project a property/color from an object to its neighborhood",
        abstract_preconditions=[
            "Source object exists",
            "Neighborhood relation defined",
            "Property to project is identified",
        ],
        abstract_postconditions=[
            "All neighbors receive projected property",
            "Source object preserved",
            "Non-neighbor cells unchanged",
        ],
        abstract_invariants=[
            "Grid/graph size unchanged",
            "Source object identity preserved",
            "Projection is deterministic for given neighborhood",
        ],
        ambiguity_conditions=[
            "Multiple candidate source objects",
            "Overlapping neighborhoods",
            "Ambiguous property to project",
        ],
        falsification_probes=[
            "Remove source: neighborhood should not change",
            "Add extra neighbor: should receive projection",
            "Change source property: projection should change",
        ],
        certificate_fields=[
            "source_object", "neighborhood_relation", "projected_property",
            "affected_cells", "invariants_preserved",
        ],
    ),
    OperatorFamilyName.COPY_FEATURE_TO_CORRESPONDENT: AbstractOperatorFamily(
        name=OperatorFamilyName.COPY_FEATURE_TO_CORRESPONDENT,
        description="Copy feature from source to corresponding target object",
        abstract_preconditions=[
            "Source and target objects exist",
            "Correspondence relation defined (shape, position, label)",
            "Feature to copy identified",
        ],
        abstract_postconditions=[
            "Target receives source feature",
            "Non-target objects unchanged",
            "Correspondence is 1-to-1 or explained many-to-1",
        ],
        abstract_invariants=[
            "Structure preserved",
            "Only specified feature changes",
            "Correspondence is deterministic",
        ],
        ambiguity_conditions=[
            "Multiple valid correspondences",
            "Feature ambiguous (color vs shape vs label)",
        ],
        falsification_probes=[
            "Swap source/target: copy direction should reverse",
            "Remove correspondence: target should not change",
            "Change source feature: target should change accordingly",
        ],
        certificate_fields=[
            "source_objects", "target_objects", "correspondence_type",
            "copied_feature", "invariants_preserved",
        ],
    ),
    OperatorFamilyName.FILTER_BY_RELATION: AbstractOperatorFamily(
        name=OperatorFamilyName.FILTER_BY_RELATION,
        description="Keep objects satisfying a relation predicate, remove others",
        abstract_preconditions=[
            "Multiple objects exist",
            "Relation predicate identified",
            "At least one object satisfies predicate",
        ],
        abstract_postconditions=[
            "All kept objects satisfy predicate",
            "No removed object satisfies predicate",
            "Kept objects unchanged (no modification)",
        ],
        abstract_invariants=[
            "Grid/graph size unchanged",
            "Predicate is Boolean and deterministic",
        ],
        ambiguity_conditions=[
            "Multiple predicates give same partition",
            "Predicate is context-dependent",
        ],
        falsification_probes=[
            "Add object satisfying predicate: should be kept",
            "Add object not satisfying: should be removed",
            "Negate predicate: kept/removed should swap",
        ],
        certificate_fields=[
            "predicate", "kept_objects", "removed_objects", "invariants_preserved",
        ],
    ),
    OperatorFamilyName.MOVE_OR_TRANSFER_TO_ANCHOR: AbstractOperatorFamily(
        name=OperatorFamilyName.MOVE_OR_TRANSFER_TO_ANCHOR,
        description="Transfer object or feature to anchor-relative position",
        abstract_preconditions=[
            "Source and anchor objects exist",
            "Anchor position/role identified",
            "Transfer rule defined (copy, move, overlay)",
        ],
        abstract_postconditions=[
            "Source appears at anchor-relative position",
            "Anchor unchanged (unless overlay)",
            "Original source removed (if move) or preserved (if copy)",
        ],
        abstract_invariants=[
            "Transfer is deterministic given anchor",
            "Spatial relationship preserved after transfer",
        ],
        ambiguity_conditions=[
            "Multiple candidate anchors",
            "Ambiguous transfer rule (copy vs move)",
        ],
        falsification_probes=[
            "Move anchor: transferred position should follow",
            "Remove anchor: transfer should fail",
            "Add second anchor: behavior should be defined",
        ],
        certificate_fields=[
            "source_object", "anchor_object", "transfer_rule",
            "new_position", "invariants_preserved",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Domain realizations
# ---------------------------------------------------------------------------

def _grid_project_to_neighborhood(grid, objects, params):
    """Grid realization: fill adjacent cells of source object with its color."""
    from copy import deepcopy
    result = deepcopy(grid)
    rows, cols = len(grid), len(grid[0])
    src = params.get("source_object")
    if src is None or src >= len(objects):
        return None
    obj = objects[src]
    color = obj["color"]
    for r, c in obj["cells"]:
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in obj["cells"]:
                result[nr][nc] = color
    return result


def _grid_filter_by_relation(grid, objects, params):
    """Grid realization: keep objects satisfying a property, remove others."""
    from copy import deepcopy
    result = [[0] * len(grid[0]) for _ in range(len(grid))]
    prop = params.get("property")
    for obj in objects:
        keep = obj.get(prop, False) if prop else False
        if keep:
            for r, c in obj["cells"]:
                result[r][c] = obj["color"]
    return result


def _graph_project_to_neighborhood(graph, objects, params):
    """Graph realization: project label to adjacent nodes."""
    from copy import deepcopy
    result = deepcopy(graph)
    src = params.get("source_node")
    if src is None:
        return None
    if "adjacency" in graph and src in graph["adjacency"]:
        label = graph["nodes"][src].get("label")
        for neighbor in graph["adjacency"][src]:
            result["nodes"][neighbor]["label"] = label
    return result


DOMAIN_REALIZATIONS = {
    ("grid", OperatorFamilyName.PROJECT_TO_NEIGHBORHOOD): DomainRealization(
        domain="grid",
        family=OperatorFamilyName.PROJECT_TO_NEIGHBORHOOD,
        concrete_preconditions=["Source is connected component", "Grid has bg=0"],
        concrete_postconditions=["4-adjacent cells of source filled with source color"],
        realize_fn=_grid_project_to_neighborhood,
        description="Fill 4-adjacent cells around object",
    ),
    ("grid", OperatorFamilyName.FILTER_BY_RELATION): DomainRealization(
        domain="grid",
        family=OperatorFamilyName.FILTER_BY_RELATION,
        concrete_preconditions=["Objects are connected components", "Property is Boolean"],
        concrete_postconditions=["Objects satisfying property preserved, others removed"],
        realize_fn=_grid_filter_by_relation,
        description="Keep objects satisfying property, remove others",
    ),
    ("graph", OperatorFamilyName.PROJECT_TO_NEIGHBORHOOD): DomainRealization(
        domain="graph",
        family=OperatorFamilyName.PROJECT_TO_NEIGHBORHOOD,
        concrete_preconditions=["Source node exists", "Adjacency list defined"],
        concrete_postconditions=["Adjacent nodes receive source label"],
        realize_fn=_graph_project_to_neighborhood,
        description="Project label to adjacent nodes",
    ),
}


# ---------------------------------------------------------------------------
# Transfer logic
# ---------------------------------------------------------------------------

def instantiate_across_domains(
    family_name: OperatorFamilyName,
    source_domain: str,
    target_domain: str,
) -> TransferResult:
    family = OPERATOR_FAMILIES.get(family_name)
    if family is None:
        return TransferResult(source_domain, target_domain, family_name, failure_reason="unknown family")

    src_key = (source_domain, family_name)
    tgt_key = (target_domain, family_name)

    src_real = DOMAIN_REALIZATIONS.get(src_key)
    tgt_real = DOMAIN_REALIZATIONS.get(tgt_key)

    schema_reuse = src_real is not None and tgt_real is not None
    zero_shot = False
    few_shot = False

    if schema_reuse and tgt_real.realize_fn is not None:
        zero_shot = True

    return TransferResult(
        source_domain=source_domain,
        target_domain=target_domain,
        family=family_name,
        schema_reuse_success=schema_reuse,
        zero_shot_success=zero_shot,
        few_shot_success=few_shot,
        failure_reason=None if schema_reuse else f"no realization for {target_domain}",
    )


def validate_transfer(
    family_name: OperatorFamilyName,
    source_real: DomainRealization,
    target_real: DomainRealization,
    test_cases: List[Dict],
) -> Tuple[bool, int, int]:
    """Validate transfer: returns (success, solved, total)."""
    if target_real.realize_fn is None:
        return False, 0, len(test_cases)

    solved = 0
    for tc in test_cases:
        try:
            result = target_real.realize_fn(
                tc.get("input"), tc.get("objects", []), tc.get("params", {})
            )
            if result is not None and result == tc.get("expected_output"):
                solved += 1
        except Exception:
            pass
    return solved > 0, solved, len(test_cases)
