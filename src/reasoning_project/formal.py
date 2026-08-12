"""Finite operational formalization layer.

This module is deliberately modest. It gives executable finite models for:

- exact bounded DSL code length and shortest-program checks,
- exact small-category checks for supplied grid transformations,
- HoTT-inspired path/equivalence witnesses between programs,
- exact operator-specific topology audits over bounded grid domains,
- algorithmic-information-dynamics-inspired finite-difference profiles.

It does not implement exact Kolmogorov complexity, full category theory, HoTT,
broad topology theorems, or a proof path to AGI. The purpose is to make the
implemented mathematical claims auditable and falsifiable on finite domains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from .compression import grid_error, perturb_grid
from .operators import REGISTRY, apply_program, base_candidate_steps, candidate_programs, program_description_length
from .parsing import parse_objects
from .schemas import Program, ProgramStep, TaskExample, grid_to_list, program_signature
from .utils import stable_hash


GridDomain = Sequence[np.ndarray]
CODE_LENGTH_SCALE = 20
PARAM_KEY_COST_UNITS = 3


def identity_program() -> Program:
    return [ProgramStep("identity")]


def compose_program(first: Program, second: Program) -> Program:
    """Return the executable program for second-after-first."""

    if program_signature(first) == "identity":
        return [ProgramStep(step.name, dict(step.params)) for step in second]
    if program_signature(second) == "identity":
        return [ProgramStep(step.name, dict(step.params)) for step in first]
    return [ProgramStep(step.name, dict(step.params)) for step in first + second]


def finite_domain_hash(domain: GridDomain) -> str:
    return stable_hash([grid_to_list(grid) for grid in domain])


def programs_extensionally_equal(left: Program, right: Program, domain: GridDomain) -> bool:
    for grid in domain:
        left_out = apply_program(grid, left)
        right_out = apply_program(grid, right)
        if left_out.shape != right_out.shape or not np.array_equal(left_out, right_out):
            return False
    return True


def bounded_domain_signature(domain: GridDomain) -> Dict[str, Any]:
    shapes = sorted({tuple(int(v) for v in np.asarray(grid).shape) for grid in domain})
    colors = sorted({int(v) for grid in domain for v in np.asarray(grid, dtype=int).flatten()})
    return {
        "domain_hash": finite_domain_hash(domain),
        "grid_count": len(domain),
        "shapes": [list(shape) for shape in shapes],
        "colors": colors,
    }


def enumerate_binary_grids(shape: Tuple[int, int] = (2, 2)) -> List[np.ndarray]:
    """Enumerate all binary grids for a small finite domain."""

    h, w = int(shape[0]), int(shape[1])
    grids: List[np.ndarray] = []
    for values in product([0, 1], repeat=h * w):
        grids.append(np.asarray(values, dtype=int).reshape((h, w)))
    return grids


def program_code_length_units(program: Program) -> int:
    """Exact integer code length under the project's declared finite DSL scheme.

    The coding scheme is the integer-scaled version of
    `operators.program_description_length`: base operator costs are multiplied
    by `CODE_LENGTH_SCALE`; each parameter key costs `PARAM_KEY_COST_UNITS`;
    each character in a parameter value costs one unit. This is an exact
    bounded DSL code length, not Kolmogorov complexity.
    """

    total = 0
    for step in program:
        spec = REGISTRY[step.name]
        base_units = int(round(float(spec.base_cost) * CODE_LENGTH_SCALE))
        value_units = sum(len(str(value)) for value in step.params.values())
        total += base_units + PARAM_KEY_COST_UNITS * len(step.params) + value_units
    return int(total)


@dataclass
class BoundedDSLMinimumReport:
    examples_hash: str
    max_depth: int
    colors: List[int]
    candidate_count: int
    satisfying_count: int
    minimum_code_length_units: int | None
    minimum_program_signatures: List[str]
    coding_scheme: str
    search_space_definition: str
    equality_notion: str
    claim_scope: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "examples_hash": self.examples_hash,
            "max_depth": self.max_depth,
            "colors": self.colors,
            "candidate_count": self.candidate_count,
            "satisfying_count": self.satisfying_count,
            "minimum_code_length_units": self.minimum_code_length_units,
            "minimum_program_signatures": self.minimum_program_signatures,
            "coding_scheme": self.coding_scheme,
            "search_space_definition": self.search_space_definition,
            "equality_notion": self.equality_notion,
            "claim_scope": self.claim_scope,
        }


def _examples_hash(examples: Sequence[TaskExample]) -> str:
    return stable_hash(
        [
            {
                "input": grid_to_list(example.input_grid),
                "output": grid_to_list(example.output_grid),
            }
            for example in examples
        ]
    )


def bounded_exact_dsl_minimum(
    examples: Iterable[TaskExample],
    max_depth: int,
    colors: Sequence[int],
) -> BoundedDSLMinimumReport:
    """Compute the exact minimum code length over the finite candidate DSL.

    The result is exact only for:
    - the generated candidate set `candidate_programs(max_depth, colors)`,
    - the integer coding scheme in `program_code_length_units`,
    - exact output equality on the supplied examples.
    """

    examples = list(examples)
    colors = [int(color) for color in colors]
    programs = candidate_programs(max_depth=max_depth, colors=colors)
    satisfying: List[Program] = []
    for program in programs:
        if all(np.array_equal(apply_program(example.input_grid, program), example.output_grid) for example in examples):
            satisfying.append(program)
    if satisfying:
        min_units = min(program_code_length_units(program) for program in satisfying)
        signatures = sorted(
            program_signature(program)
            for program in satisfying
            if program_code_length_units(program) == min_units
        )
    else:
        min_units = None
        signatures = []
    return BoundedDSLMinimumReport(
        examples_hash=_examples_hash(examples),
        max_depth=int(max_depth),
        colors=colors,
        candidate_count=len(programs),
        satisfying_count=len(satisfying),
        minimum_code_length_units=min_units,
        minimum_program_signatures=signatures,
        coding_scheme=(
            "integer units: operator_base_cost*20 + 3 per parameter key + "
            "1 per character of each parameter value"
        ),
        search_space_definition="candidate_programs(max_depth, colors) finite generated DSL",
        equality_notion="exact numpy array equality on every supplied input-output example",
        claim_scope="exact bounded DSL minimum; not exact Kolmogorov complexity",
    )


@dataclass
class FiniteMorphism:
    name: str
    program: Program

    def apply(self, grid: np.ndarray) -> np.ndarray:
        return apply_program(grid, self.program)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "program_signature": program_signature(self.program)}


@dataclass
class CategoryLawReport:
    domain_hash: str
    morphism_count: int
    identity_law_holds: bool
    associativity_holds: bool
    composition_well_defined_holds: bool
    closure_holds: bool | None
    checked_identity_cases: int
    checked_associativity_cases: int
    checked_closure_cases: int
    failures: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_hash": self.domain_hash,
            "morphism_count": self.morphism_count,
            "identity_law_holds": self.identity_law_holds,
            "associativity_holds": self.associativity_holds,
            "composition_well_defined_holds": self.composition_well_defined_holds,
            "closure_holds": self.closure_holds,
            "checked_identity_cases": self.checked_identity_cases,
            "checked_associativity_cases": self.checked_associativity_cases,
            "checked_closure_cases": self.checked_closure_cases,
            "failures": self.failures,
            "objects_definition": "finite typed grid states in the supplied enumerated domain",
            "morphisms_definition": "executable grid programs supplied as finite morphisms",
            "identity_definition": "`identity` program",
            "composition_definition": "sequential program execution / program concatenation",
            "equality_notion": "extensional equality over every grid in the supplied finite domain",
            "claim_scope": "exact bounded small-category law checks over provided finite grids and morphisms",
        }


def _program_well_defined(program: Program, domain: GridDomain) -> bool:
    for grid in domain:
        try:
            out = apply_program(grid, program)
        except Exception:
            return False
        if not isinstance(out, np.ndarray) or out.ndim != 2:
            return False
    return True


def check_finite_category_laws(
    morphisms: Sequence[FiniteMorphism],
    domain: GridDomain,
    require_closure: bool = False,
) -> CategoryLawReport:
    failures: List[Dict[str, Any]] = []
    identity = identity_program()
    composition_well_defined = True
    checked_identity = 0
    for morphism in morphisms:
        checked_identity += 2
        left_identity = compose_program(identity, morphism.program)
        right_identity = compose_program(morphism.program, identity)
        composition_well_defined = (
            composition_well_defined
            and _program_well_defined(left_identity, domain)
            and _program_well_defined(right_identity, domain)
        )
        if not programs_extensionally_equal(left_identity, morphism.program, domain):
            failures.append({"law": "left_identity", "morphism": morphism.name})
        if not programs_extensionally_equal(right_identity, morphism.program, domain):
            failures.append({"law": "right_identity", "morphism": morphism.name})

    checked_associativity = 0
    for a, b, c in product(morphisms, repeat=3):
        checked_associativity += 1
        left = compose_program(compose_program(a.program, b.program), c.program)
        right = compose_program(a.program, compose_program(b.program, c.program))
        composition_well_defined = (
            composition_well_defined
            and _program_well_defined(left, domain)
            and _program_well_defined(right, domain)
        )
        if not programs_extensionally_equal(left, right, domain):
            failures.append({"law": "associativity", "a": a.name, "b": b.name, "c": c.name})
            break
    closure_holds: bool | None = None
    checked_closure = 0
    if require_closure:
        closure_holds = True
        for a, b in product(morphisms, repeat=2):
            checked_closure += 1
            composed = compose_program(a.program, b.program)
            if not any(programs_extensionally_equal(composed, m.program, domain) for m in morphisms):
                closure_holds = False
                failures.append({"law": "closure", "a": a.name, "b": b.name})
                break

    return CategoryLawReport(
        domain_hash=finite_domain_hash(domain),
        morphism_count=len(morphisms),
        identity_law_holds=not any(failure["law"] in {"left_identity", "right_identity"} for failure in failures),
        associativity_holds=not any(failure["law"] == "associativity" for failure in failures),
        composition_well_defined_holds=composition_well_defined,
        closure_holds=closure_holds,
        checked_identity_cases=checked_identity,
        checked_associativity_cases=checked_associativity,
        checked_closure_cases=checked_closure,
        failures=failures,
    )


def finite_group_morphisms_for_reflections() -> List[FiniteMorphism]:
    """Closed four-morphism reflection group over rectangular grids."""

    return [
        FiniteMorphism("identity", [ProgramStep("identity")]),
        FiniteMorphism("reflect_horizontal", [ProgramStep("reflect_horizontal")]),
        FiniteMorphism("reflect_vertical", [ProgramStep("reflect_vertical")]),
        FiniteMorphism("rotate_180", [ProgramStep("rotate_180")]),
    ]


@dataclass
class PathWitness:
    left_signature: str
    right_signature: str
    relation: str
    domain_hash: str
    checked_examples: int
    claim_scope: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "left_signature": self.left_signature,
            "right_signature": self.right_signature,
            "relation": self.relation,
            "domain_hash": self.domain_hash,
            "checked_examples": self.checked_examples,
            "claim_scope": self.claim_scope,
        }


def finite_path_witness(left: Program, right: Program, domain: GridDomain) -> PathWitness:
    left_sig = program_signature(left)
    right_sig = program_signature(right)
    if left_sig == right_sig:
        relation = "syntactic_identity"
    elif programs_extensionally_equal(left, right, domain):
        relation = "finite_extensional_equivalence"
    else:
        relation = "not_equivalent_on_domain"
    return PathWitness(
        left_signature=left_sig,
        right_signature=right_sig,
        relation=relation,
        domain_hash=finite_domain_hash(domain),
        checked_examples=len(domain),
        claim_scope="finite HoTT-inspired path witness, not a full identity type",
    )


def binary_topology_signature(grid: np.ndarray) -> Dict[str, Any]:
    arr = np.asarray(grid, dtype=int)
    support = (arr != 0).astype(int)
    objects = parse_objects(support, background=0)
    return {
        "shape": list(arr.shape),
        "support_mask": grid_to_list(support),
        "component_count": len(objects),
        "hole_count": int(sum(obj.holes for obj in objects)),
        "component_sizes": sorted([int(obj.size) for obj in objects], reverse=True),
    }


@dataclass
class OperatorTopologyReport:
    operator_signature: str
    domain: Dict[str, Any]
    support_mask_preserved: bool
    component_count_preserved: bool
    hole_count_preserved: bool
    classification: str
    counterexamples: Dict[str, Any]
    invariant_definition: str
    claim_scope: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator_signature": self.operator_signature,
            "domain": self.domain,
            "support_mask_preserved": self.support_mask_preserved,
            "component_count_preserved": self.component_count_preserved,
            "hole_count_preserved": self.hole_count_preserved,
            "classification": self.classification,
            "counterexamples": self.counterexamples,
            "invariant_definition": self.invariant_definition,
            "claim_scope": self.claim_scope,
        }


def _counterexample_record(step: ProgramStep, grid: np.ndarray) -> Dict[str, Any]:
    out = apply_program(grid, [step])
    return {
        "input": grid_to_list(grid),
        "output": grid_to_list(out),
        "input_signature": binary_topology_signature(grid),
        "output_signature": binary_topology_signature(out),
    }


def audit_operator_topology(
    step: ProgramStep,
    domain: GridDomain,
) -> OperatorTopologyReport:
    support_ok = True
    components_ok = True
    holes_ok = True
    counterexamples: Dict[str, Any] = {}
    for grid in domain:
        out = apply_program(grid, [step])
        before = binary_topology_signature(grid)
        after = binary_topology_signature(out)
        same_shape = before["shape"] == after["shape"]
        if support_ok and (not same_shape or before["support_mask"] != after["support_mask"]):
            support_ok = False
            counterexamples["support_mask"] = _counterexample_record(step, grid)
        if components_ok and before["component_count"] != after["component_count"]:
            components_ok = False
            counterexamples["component_count"] = _counterexample_record(step, grid)
        if holes_ok and before["hole_count"] != after["hole_count"]:
            holes_ok = False
            counterexamples["hole_count"] = _counterexample_record(step, grid)
    if support_ok and components_ok and holes_ok:
        classification = "topology_preserving_under_support_mask_definition"
    elif components_ok and holes_ok:
        classification = "topology_preserving_for_component_and_hole_counts_only"
    elif step.name in {"translate", "copy_to_corner"}:
        classification = "conditionally_topology_preserving_not_on_full_bounded_domain"
    else:
        classification = "not_topology_preserving_on_bounded_domain"
    return OperatorTopologyReport(
        operator_signature=program_signature([step]),
        domain=bounded_domain_signature(domain),
        support_mask_preserved=support_ok,
        component_count_preserved=components_ok,
        hole_count_preserved=holes_ok,
        classification=classification,
        counterexamples=counterexamples,
        invariant_definition=(
            "color-insensitive binary support topology: exact support mask, "
            "4-connected support component count, and support hole count"
        ),
        claim_scope="exact operator-specific invariant check over the supplied finite domain",
    )


def audit_operator_topology_suite(
    domain: GridDomain,
    colors: Sequence[int] = (1, 2),
) -> List[OperatorTopologyReport]:
    return [audit_operator_topology(step, domain) for step in base_candidate_steps(colors)]


def grid_description_proxy(grid: np.ndarray) -> float:
    arr = np.asarray(grid, dtype=int)
    nonzero = float(np.count_nonzero(arr))
    colors = float(len(set(int(v) for v in arr.flatten()) - {0}))
    shape_cost = float(len(arr.shape) + sum(arr.shape) * 0.05)
    return nonzero + colors + shape_cost


@dataclass
class AIDProfile:
    program_signature: str
    description_length_proxy: float
    mean_input_complexity_delta: float
    mean_output_complexity_delta: float
    mean_output_error_under_intervention: float
    intervention_amplification_proxy: float
    examples: int
    claim_scope: str = "finite-difference AID proxy; not exact algorithmic information dynamics"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_signature": self.program_signature,
            "description_length_proxy": self.description_length_proxy,
            "mean_input_complexity_delta": self.mean_input_complexity_delta,
            "mean_output_complexity_delta": self.mean_output_complexity_delta,
            "mean_output_error_under_intervention": self.mean_output_error_under_intervention,
            "intervention_amplification_proxy": self.intervention_amplification_proxy,
            "examples": self.examples,
            "claim_scope": self.claim_scope,
        }


def aid_profile(program: Program, examples: Iterable[TaskExample], seed: int = 0) -> AIDProfile:
    examples = list(examples)
    input_deltas: List[float] = []
    output_deltas: List[float] = []
    output_errors: List[float] = []
    for idx, example in enumerate(examples):
        perturbed_input = perturb_grid(example.input_grid, seed + idx)
        base_output = apply_program(example.input_grid, program)
        perturbed_output = apply_program(perturbed_input, program)
        input_delta = abs(grid_description_proxy(perturbed_input) - grid_description_proxy(example.input_grid))
        output_delta = abs(grid_description_proxy(perturbed_output) - grid_description_proxy(base_output))
        input_deltas.append(input_delta)
        output_deltas.append(output_delta)
        output_errors.append(grid_error(perturbed_output, base_output))
    mean_input = float(np.mean(input_deltas)) if input_deltas else 0.0
    mean_output = float(np.mean(output_deltas)) if output_deltas else 0.0
    return AIDProfile(
        program_signature=program_signature(program),
        description_length_proxy=program_description_length(program),
        mean_input_complexity_delta=mean_input,
        mean_output_complexity_delta=mean_output,
        mean_output_error_under_intervention=float(np.mean(output_errors)) if output_errors else 0.0,
        intervention_amplification_proxy=mean_output / (mean_input + 1e-9),
        examples=len(examples),
    )
