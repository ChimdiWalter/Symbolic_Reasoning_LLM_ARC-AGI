"""Runtime registry versus contract: exact, mechanical correspondence.

Not another semantic audit. Three properties only:

    every runtime signature equals compile(contract signature, policy)
    no runtime rule exists without contract provenance
    no contract-inactive rule is executable
"""
from __future__ import annotations

import json

import pytest

from geocat_arc.object_reasoning import meta_v21 as V


@pytest.fixture(scope="module")
def contract():
    return V.load_contract(verify=True)


def test_contract_hash_is_pinned():
    """The module refuses to run against a drifted contract."""
    assert V.FROZEN_HASH_PATH.exists()
    V.load_contract(verify=True)          # raises ContractDrift on mismatch


def test_every_runtime_signature_comes_from_the_contract(contract):
    rules = V._contract_rules(contract)
    policy = contract["polymorphism_policy"]["instantiations"]
    for name, production in V.REGISTRY.items():
        constrained = policy.get(name, {}).get("implemented_signature")
        form = constrained or rules[name]["form"]
        args, result = V.parse_signature(form, name)
        assert production.arg_types == args, f"{name} argument types drifted"
        assert V.type_equal(production.result_type, result), \
            f"{name} result type drifted"
        assert production.contract_grades["signature_text"] == form


def test_no_runtime_rule_without_contract_provenance(contract):
    named = set(V._contract_rules(contract))
    assert set(V.REGISTRY) <= named


def test_no_contract_inactive_rule_is_executable(contract):
    inactive = set()
    for rule in contract["layer_B_frozen_design"]["rules"]:
        if not rule.get("active", False):
            inactive.add(rule["rule"])
    for rule in contract["inactive_unresolved"]:
        inactive.add(rule["rule"])
    assert not (set(V.REGISTRY) & inactive)
    assert not (set(V.EVALUATORS) & inactive), \
        "an evaluator exists for a contract-inactive rule"


def test_level4_registry_is_contract_active_only(contract):
    """K_L4 must contain no contract-inactive rule, and must NOT be K_3A."""
    inactive = {r["rule"] for r in contract["layer_B_frozen_design"]["rules"]
                if not r.get("active", False)}
    inactive |= {r["rule"] for r in contract["inactive_unresolved"]}
    for name in V.LEVEL4_REGISTRY:
        base = V.LEVEL4_REGISTRY[name].contract_grades.get("instantiated_from",
                                                          name)
        assert base not in inactive, f"K_L4 contains inactive {base}"
    assert set(V.LEVEL4_REGISTRY) != set(V.REGISTRY), \
        "K_L4 must be distinguished from the Level-3A kernel"
    assert len(V.LEVEL4_REGISTRY) > len(V.REGISTRY)


def test_context_implicit_rule_is_restricted(contract):
    """Only audited productions may lose a leading Grid argument."""
    overlay = V.LEVEL4_REGISTRY.get("Overlay")
    assert overlay is not None and len(overlay.arg_types) == 2, \
        "Overlay lost a real Grid argument to the context-implicit rule"


def test_no_bare_type_variable_reaches_the_runtime():
    for registry in (V.REGISTRY, V.LEVEL4_REGISTRY):
        for name, production in registry.items():
            for arg in list(production.arg_types) + [production.result_type]:
                assert not V.is_type_variable(str(arg)), \
                    f"{name} exposes an unbound type variable {arg}"


def test_kernel_is_the_source_program_closure(contract):
    """The executable language is derived, not chosen."""
    kernel = set(contract["v21_kernel"]["rules"])
    assert set(V.REGISTRY) == kernel
    assert "derivation" in contract["v21_kernel"]


def test_evaluators_carry_no_signatures():
    """Python contributes behaviour only."""
    import inspect
    source = inspect.getsource(V)
    assert "_register(" not in source, "a hand-written signature table returned"


def test_type_checker_uses_full_parameterised_types():
    good = ("PaintEach", (("Map_V1", (
        ("Partition", ("background_components",)),
        ("Compose_V1", (("Key", ("is_rect",)), ("Lookup", (((True, 3),),)))))),))
    assert V.type_of(good) is not None
    # Key alone yields Expr[Region,FeatureValue], which is NOT Expr[Region,Colour]
    bad = ("PaintEach", (("Map_V1", (
        ("Partition", ("background_components",)),
        ("Key", ("is_rect",)))),))
    assert V.type_of(bad) is None, "head-type approximation leaked into the runtime"
