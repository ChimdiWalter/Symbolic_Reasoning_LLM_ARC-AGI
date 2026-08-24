"""Synthetic unit tests for Step-B item 2 (candidate enumerator + runner
helpers). Nothing here reads a pinned cluster, record or corpus file.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V              # noqa: E402
from level4_blind_runtime import env as E                  # noqa: E402
from level4_blind_runtime import search as SEARCH          # noqa: E402
from level4_stepB import candidates as CA                  # noqa: E402
from level4_stepB import install as N                      # noqa: E402
from level4_stepB import k2_inventory as I                 # noqa: E402
from level4_stepB import k1_lattice as L                   # noqa: E402
from level4_stepB import witnesses as W                    # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = _load("stepB_run", ROOT / "scripts" / "cora_level4_stepB_run.py")


@pytest.fixture(scope="module")
def built():
    types, instances = I.build()
    return types, instances


def test_split_roundtrip():
    for text in ("Grid", "Set[Region]", "Expr[Region,Colour]", "Set[Coloured]"):
        assert str(V.T(*CA._split(text))) == text


def test_enumeration_is_deterministic_and_port_bearing(built):
    types, instances = built
    with N.installed(instances):
        a, b = CA.candidates_for(V.SET_REGION, V.GRID, instances)[0], \
            CA.candidates_for(V.SET_REGION, V.GRID, instances)[0]
        assert [c.candidate_id for c in a] == [c.candidate_id for c in b]
        assert len({c.candidate_id for c in a}) == len(a)
        for c in a:
            slots = CA.C.introduced_slots(c.schema)
            assert c.port_slot in slots
            assert c.slot_types[c.port_slot] == V.SET_REGION
            assert c.label == CA.LABELS[c.lane]
            assert c.concept().result_type == V.GRID


def test_interface_is_the_only_input(built):
    """Two calls with the same interface agree; a different interface
    yields a different set: nothing but (a, b) enters."""
    types, instances = built
    with N.installed(instances):
        x, _ = CA.candidates_for(V.GRID, V.GRID, instances)
        y, _ = CA.candidates_for(V.SET_REGION, V.GRID, instances)
        assert {c.candidate_id for c in x}.isdisjoint({c.candidate_id for c in y})
        assert all(c.interface == ("Grid", "Grid") for c in x)


def test_k1_pairs_only_with_the_learner_slot(built):
    types, instances = built
    with N.installed(instances):
        cands, report = CA.candidates_for(V.SET_REGION, V.GRID, instances)
        k1 = [c for c in cands if c.lane == "K1"]
        assert k1 and report["K1"]["paired_with_learners"] == len(k1)
        learner_type = CA._learner_type()
        for c in k1:
            assert any(str(t) == learner_type for t in c.slot_types.values())
            assert c.learner_id.startswith("K1:")
        ids = {c.learner_id for c in k1}
        assert ids == {lid for lid, _, _ in L.lattice()}
        assert report["K2"]["dropped_by_cap"] == 0
        assert report["K1"]["dropped_by_cap"] == 0


def test_candidate_elaborates_and_typechecks(built):
    types, instances = built
    with N.installed(instances):
        cands, _ = CA.candidates_for(V.SET_REGION, V.GRID, instances)
        base = E.LanguageEnv(base=RUN.FROZEN_BASE, label="K")
        checked = 0
        for c in cands[:50]:
            env = E.LanguageEnv(base=base.base, concepts={c.candidate_id: c.concept()})
            args = []
            for slot in CA.C.introduced_slots(c.schema):
                t = c.slot_types[slot]
                if slot == c.port_slot:
                    args.append(("Partition", ("colour_components",)))
                elif str(t) in V.TERMINAL_VALUES:
                    args.append(V.TERMINAL_VALUES[str(t)][0])
                else:
                    args.append(f"?{t}")
            surface = (c.candidate_id, tuple(args))
            assert E.type_of(surface, env) is not None, c.candidate_id
            assert V.type_equal(E.type_of(surface, env), V.GRID)
            checked += 1
        assert checked == 50


def test_fingerprints_are_deterministic(built):
    types, instances = built
    witnesses = W.witness_values(types, I.resolver())
    with N.installed(instances):
        cands, _ = CA.candidates_for(V.GRID, V.GRID, instances)
        fps = [CA.fingerprint(c, witnesses, 6) for c in cands[:10]]
        assert fps == [CA.fingerprint(c, witnesses, 6) for c in cands[:10]]


def test_plug_in_proposal_on_a_extent_task(built):
    """The design's proposal step on manufactured demonstrations: plug a
    failed term into a candidate's port, fit the slots, check exactness."""
    types, instances = built
    gates = _load("stepB_gates", ROOT / "scripts" / "cora_level4_stepB_gates.py")
    demos = gates.extent_demonstrations(0)
    pairs = [(np.array(d["input"]), np.array(d["output"])) for d in demos]
    frozen = dict(V.REGISTRY)                 # captured BEFORE installing
    with N.installed(instances):
        cands, _ = CA.candidates_for(V.SET_REGION, V.GRID, instances)
        base = E.LanguageEnv(base=frozen, label="K")
        assert not SEARCH.search(pairs, env=base)[0], "baseline must fail"
        direct = [c for c in cands if c.lane == "K2"
                  and CA._mdl(c.schema) == 1][0]
        env = E.LanguageEnv(base=base.base,
                            concepts={direct.candidate_id: direct.concept()})
        port = ("Partition", ("colour_components",))
        args = [port if s == direct.port_slot else f"?{direct.slot_types[s]}"
                for s in CA.C.introduced_slots(direct.schema)]
        fitted, evidence = SEARCH.fit_slots((direct.candidate_id, tuple(args)),
                                            pairs, {}, env)
        assert fitted is not None
        assert SEARCH.observational_signature(fitted, pairs, env) is not None
        found, _ = SEARCH.search(pairs, env=env)
        assert found and E.uses_concept(found[0][0], env, direct.candidate_id)
        assert SEARCH.loo_by_rediscovery(pairs, env=env) == (3, 3)


def test_runner_audit_passes():
    audit = _load("runner_audit", ROOT / "scripts" / "cora_level4_stepB_runner_audit.py")
    assert audit.main(write=False) == 0


def test_runner_audit_negative_controls(tmp_path):
    audit = _load("runner_audit", ROOT / "scripts" / "cora_level4_stepB_runner_audit.py")
    item1 = _load("stepB_audit", ROOT / "scripts" / "cora_level4_stepB_audit.py")
    bad = tmp_path / "x.py"
    bad.write_text("def f(row):\n    if row['frontier_type'] == 'Grid':\n"
                   "        return 1\n    return 0\n")
    kinds = {f["kind"] for f in audit.audit_file(bad, item1)}
    assert "FIELD_BRANCH" in kinds
    bad.write_text("import os\nx = os.environ.get('A')\n")
    kinds = {f["kind"] for f in audit.audit_file(bad, item1)}
    assert "ENVIRONMENT" in kinds
    bad.write_text("p = 'data/arc-agi_training_challenges.json'\n")
    kinds = {f["kind"] for f in audit.audit_file(bad, item1)}
    assert "FORBIDDEN_PATH" in kinds
