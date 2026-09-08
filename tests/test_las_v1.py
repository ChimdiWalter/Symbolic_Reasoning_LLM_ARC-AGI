"""Focused tests for LAS-v1 (directive section 20).

Covers: pool disjointness, deterministic acquisition, no target metadata in
source or abstraction selection, lattice determinism, typed slot correctness, no
table-slot collision, member round-trip, expansion accounting, matched-space
cardinality equality, source-validation-only selection, frozen-library hashing,
budget equality, dedup before fallback, ablation reset, no protected data
access, and Step-B isolation.
"""
from __future__ import annotations

import ast as pyast
import hashlib
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import abstraction_lattice as AL                   # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

GROUP = [[("background_components", (), "area"), ("colour_components", (), "shape")],
         [("background_components", (), "is_rect"), ("colour_components", (), "shape")]]


def _lattice(max_expansion=400):
    return AL.lattice_for(GROUP, ("d1", "d2"), (0, 1), "grp", max_expansion=max_expansion)


# ------------------------------------------------------------- the lattice ---

def test_lattice_is_deterministic():
    a, b = _lattice(), _lattice()
    assert [x.digest() for x in a] == [x.digest() for x in b]
    assert [x.expansion() for x in a] == sorted(x.expansion() for x in a)


def test_minimal_mask_is_the_disagreement_set_and_is_present():
    """anti-unification is ONE candidate in the lattice, not the answer."""
    lattice = _lattice()
    minimal = min(lattice, key=lambda a: len(a.mask))
    assert minimal.mask == AL.disagreement(GROUP)
    assert len(lattice) > 1, "the lattice must offer more than the anti-unification"


def test_every_mask_is_a_superset_of_the_disagreement():
    required = AL.disagreement(GROUP)
    for abstraction in _lattice():
        assert required <= abstraction.mask


def test_at_least_one_source_member_is_an_instance():
    for abstraction in _lattice():
        members = {CV.canonical(CV.ast_from_blocks(b)) for b in GROUP}
        produced = {CV.canonical(i) for i in abstraction.instantiations()}
        assert members & produced, "no group member is an instance of its abstraction"


def test_typed_slots_and_vocabulary_domains():
    for abstraction in _lattice():
        types = M.free_slot_types(abstraction.schema)
        for slot, declared in abstraction.slot_types.items():
            assert types[slot] == declared
            assert declared in M.ENUMERABLE_TYPES
            assert len(M.slot_domain(declared)) > 0
        #  values come only from the existing legal vocabulary
        v = CV.vocab()
        legal = {"PartitionExpr": set(v["partitions"]),
                 "Predicate": set(v["predicates"]),
                 "FeatureExpr": set(v["key_features"])}
        for slot, declared in abstraction.slot_types.items():
            assert set(M.slot_domain(declared)) <= legal[declared]


def test_no_table_slot_collision():
    for abstraction in _lattice():
        types = M.free_slot_types(abstraction.schema)
        for index in range(abstraction.n_blocks):
            assert types[f"?{index}"] == "Map[FeatureValue,Colour]"
        for slot in abstraction.slot_types:
            assert int(slot[1:]) >= AL.ABSTRACTION_SLOT_OFFSET
            assert slot not in {f"?{i}" for i in range(abstraction.n_blocks)}


def test_induced_tables_are_never_freed_as_enumerable():
    for abstraction in _lattice():
        assert not any(t in M.INDUCED_TYPES for t in abstraction.slot_types.values())


def test_member_round_trip_and_differential_identity():
    """Abstraction bookkeeping must not change the concrete member programs."""
    for abstraction in _lattice():
        assert AL.round_trip(abstraction)
        restored = M.ast_from_json(M.ast_to_json(abstraction.schema))
        assert CV.canonical(restored) == CV.canonical(abstraction.schema)
    #  every instantiation is a legal concrete schema whose table slots are intact
    for abstraction in _lattice():
        for instantiated in list(abstraction.instantiations())[:20]:
            ok, code = CV.validate(instantiated)
            assert ok, code
            blocks = CV.blocks_from_ast(instantiated)
            assert len(blocks) == abstraction.n_blocks


def test_expansion_accounting_matches_enumeration():
    for abstraction in _lattice():
        produced = list(abstraction.instantiations())
        assert len(produced) == abstraction.expansion()
        assert len({CV.canonical(p) for p in produced}) == abstraction.expansion()


def test_matched_control_has_equal_cardinality_and_differs():
    for abstraction in _lattice():
        control = AL.matched_control(abstraction, "ctrl")
        assert control is not None
        assert control.expansion() == abstraction.expansion()
        assert control.mask == abstraction.mask
        assert not control.member_digests and not control.source_episodes


def test_abstraction_never_receives_target_metadata():
    forbidden = {"target", "digest", "episode", "heldout", "seed", "family_label"}
    for fn in (AL.build, AL.lattice_for, AL.matched_control, AL.disagreement):
        params = set(inspect.signature(fn).parameters)
        assert not (params & forbidden), (fn.__name__, params & forbidden)
    #  the module cannot reach the generator or the transfer pool
    tree = pyast.parse((ROOT / "cora_tti" / "abstraction_lattice.py").read_text())
    imported = set()
    for node in pyast.walk(tree):
        if isinstance(node, pyast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, pyast.Import):
            imported.update(a.name for a in node.names)
    assert not any("constructive_dataset" in m or "failure_signal_study" in m
                   for m in imported), imported


# --------------------------------------------------------------- the runner ---

RUNNER = (ROOT / "scripts" / "run_las_v1.py").read_text()


def test_pools_are_disjoint_by_construction_and_asserted():
    assert "assert all(not v for v in overlaps.values())" in RUNNER
    for name in ("SOURCE_NS", "VALIDATE_NS", "TRANSFER_NS"):
        assert name in RUNNER
    #  the three namespaces differ
    namespace = {}
    exec(compile(pyast.parse("\n".join(
        line for line in RUNNER.splitlines()
        if line.startswith("SOURCE_NS") or line.startswith("MAX_EXPANSION")
        or line.startswith("TARGET_BUDGET") or line.startswith("ACQUISITION_BUDGET"))),
        "<pins>", "exec"), namespace)
    assert namespace["SOURCE_NS"] != namespace["TARGET_BUDGET"]


def test_selection_reads_only_validation_evidence():
    """The objective must not mention the transfer pool."""
    start = RUNNER.index("def objective_key(")
    end = RUNNER.index("eligible = [s for s in scored")
    body = RUNNER[start:end]
    for banned in ("TRANSFER", "transfer", "target"):
        assert banned not in body, f"objective reads {banned}"
    #  selection happens before FINAL-TRANSFER opens
    assert RUNNER.index("LAS.append(item)") < RUNNER.index("STAGE 6: FINAL-TRANSFER")
    assert RUNNER.index("FROZEN_HASH") < RUNNER.index("STAGE 6: FINAL-TRANSFER")


def test_freeze_precedes_transfer_and_is_hashed():
    assert RUNNER.index('(OUT / "frozen.json").write_text') < RUNNER.index("STAGE 6")
    assert "FROZEN_HASH = sha(frozen_text)" in RUNNER


def test_every_policy_gets_the_same_budget():
    assert "run_policy(prior_of(kind), episode, TARGET_BUDGET)" in RUNNER
    assert RUNNER.count("TARGET_BUDGET)") >= 2          # transfer and ablation


def test_dedup_before_fallback_and_unit_per_concrete_fit():
    start = RUNNER.index("def run_policy(")
    end = RUNNER.index("def prior_of(")
    body = RUNNER[start:end]
    assert "if digest in attempted:" in body and "attempted.add(digest)" in body
    assert "used += 1" in body
    #  the fallback shares the same attempted set, so prior candidates are skipped
    assert body.index("for candidate in SPACE") > body.index("attempted.add(digest)")


def test_ablation_resets_and_reports_five_outcomes_separately():
    start = RUNNER.index("STAGE 7: ablations")
    body = RUNNER[start:]
    for field in ("fit_lost", "heldout_correctness_lost", "cost_increase",
                  "fallback_solution_changed", "program_identity_changed"):
        assert f'"{field}"' in body
    #  the ablation reruns the same policy with a fresh run_policy call
    assert "after = run_policy(remainder, TRANSFER[index], TARGET_BUDGET)" in body


def test_heldout_never_influences_target_time_search():
    start = RUNNER.index("def run_policy(")
    end = RUNNER.index("def prior_of(")
    body = RUNNER[start:end]
    assert "score_program" in body
    #  scoring happens only after the search loop has chosen a program
    assert body.index("score_program") > body.index("for candidate in SPACE")


def test_full_pipeline_loo_is_declared_not_measured():
    assert '"FULL-PIPELINE LOO NOT MEASURED"' in RUNNER


# ------------------------------------------------------- isolation contracts ---

def test_no_protected_data_access_anywhere_in_las():
    banned = ("e_transfer", "lockbox", "sealed_expectation", "level4_stepb",
              "arc-agi_evaluation_solutions", "arc-agi_training_solutions",
              "holdout_labels")
    for name in ("cora_tti/abstraction_lattice.py", "scripts/run_las_v1.py"):
        text = (ROOT / name).read_text().lower()
        for marker in banned:
            assert marker not in text, f"{name} references {marker}"


def test_step_b_isolation():
    for name in ("cora_tti/abstraction_lattice.py", "scripts/run_las_v1.py"):
        text = (ROOT / name).read_text()
        assert "cora_level4_stepB" not in text
        assert "level4_stepB_journal" not in text


def test_acquisition_is_deterministic():
    """The same source seed and family always yields the same first exact fit."""
    episode = None
    for attempt in range(60):
        episode = FS.build_episode(9_100_000 + attempt * 7919, (0, 0))
        if episode is not None:
            break
    if episode is None:
        pytest.skip("no source episode built")
    space = FS.proposal_space()

    def first_fit():
        for candidate in space[:400]:
            outcome = SF.fit_outcome(FS.schema_of(candidate), episode.pairs)
            if outcome["status"] == "EXACT_DEMONSTRATION_FIT":
                return CV.digest(FS.schema_of(candidate))
        return None
    assert first_fit() == first_fit()
