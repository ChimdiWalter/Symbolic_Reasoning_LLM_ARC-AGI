"""Evidence-contract tests for the corrected census path (v2c).

Directive sections 6, 7, 8, 11 and 12: data-flow boundaries checked on the
APIs directly; explicit error outcomes; persistent guards; deterministic
instantiation; baseline/TFG configuration identity; typed key codec.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_probes as CP                   # noqa: E402
from cora_tti import constructive_v2c as V2C                     # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

CONFIG = MB.BaselineConfig()
BUDGETS = {"per_target_s": 120.0}


def _demos_for(schema, seed):
    grid_seeds = [seed * 97 + i for i in range(14)]
    concrete = V2C.instantiate_tables(schema, [CD.generate_grid(s) for s in grid_seeds[:6]])
    if concrete is None:
        return None, []
    pairs, _ = CD.render_demonstrations(concrete, grid_seeds, min_demos=3)
    return concrete, pairs


def _first_fittable(family, start=0, limit=400):
    """A generated target of the family whose scoped fit is exact (no hand-written AST)."""
    for attempt in range(start, start + limit):
        seed = 7_000_000 + attempt * 7919 + len(family) * 1013 + sum(family) * 37
        schema = CD.sample_target(seed, family)
        concrete, pairs = _demos_for(schema, seed)
        if len(pairs) < 3:
            continue
        fit = SF.fit_outcome(schema, pairs)
        if fit["status"] == "EXACT_DEMONSTRATION_FIT":
            return seed, schema, concrete, pairs, fit["program"]
    pytest.skip(f"no fittable generated target found for {family}")


def _first_redundant_select_fixture(limit=800):
    """A generated single-block target carrying the identity filter Select("all")
    whose fitted program is defined on at least one frozen probe, so the
    reducibility comparison is non-vacuous."""
    for attempt in range(limit):
        seed = 7_000_000 + attempt * 7919 + 1013
        base = CD.sample_target(seed, (0,))
        partition, _selects, feature = CV.blocks_from_ast(base)[0]
        schema = CV.ast_from_blocks([(partition, ("all",), feature)])
        _concrete, pairs = _demos_for(schema, seed)
        if len(pairs) < 3:
            continue
        fit = SF.fit_outcome(schema, pairs)
        if fit["status"] != "EXACT_DEMONSTRATION_FIT":
            continue
        _fp, status = CP.fingerprint_with_diagnostics(fit["program"], V2C._evaluate)
        if sum(1 for st in status if st == "OK") > 0:
            return schema, pairs, fit
    return None


# ---------------------------------------------------------------- codec ---

def test_key_codec_round_trip_preserves_reference_lookup_semantics():
    values = [3, 0, True, False, None, (2, 3), ((0, 0), (0, 1), (1, 1)), (), (5,), (1, 2, 9)]
    for value in values:
        decoded = SF.decode_key(SF.encode_key(value))
        assert decoded == value
        table = dict([(value, 4)])
        assert decoded in table                      # usable as a Lookup key
    #  a Lookup table survives the meta_ast JSON codec with tuple keys restored
    program = ("Compose", (("Partition", ("colour_components",)),
                           ("Map", (("Key", ("hw",)), ("Lookup", ((((1, 2), 5), ((2, 2), 7)),)))),
                           ("Paint", ())))
    restored = M.ast_from_json(M.ast_to_json(program))
    assert restored == program


def test_no_eval_and_no_salted_hash_on_the_evidence_path():
    fitter = (ROOT / "cora_tti" / "scoped_slot_fitting.py").read_text()
    assert "eval(" not in fitter
    for name in ("constructive_v2c.py", "meta_baseline.py", "constructive_v2c_census.py"):
        source = (ROOT / "cora_tti" / name).read_text()
        assert " hash(" not in source and "(hash(" not in source, name


def test_raw_value_keys_agree_with_v1_1_learner_on_bool_and_none_features():
    """Positive parity on the typed features the codec must handle (is_rect is
    Boolean, sole_neighbour_colour is int-or-None)."""
    for feature in ("is_rect", "sole_neighbour_colour", "hw", "shape"):
        schema = CV.ast_from_blocks([("colour_components", ("all",), feature)])
        seed = 7_100_000 + len(feature)
        concrete, pairs = _demos_for(schema, seed)
        if len(pairs) < 3:
            continue
        new = SF.fit_outcome(schema, pairs)
        old = MI.fit_induced_slots(schema, pairs)
        old_ok = old is not None and MI.observational_signature(old, pairs) is not None
        assert (new["status"] == "EXACT_DEMONSTRATION_FIT") == old_ok, feature
        if old_ok:
            for grid_in, _ in pairs:
                assert np.array_equal(M.evaluate(old, grid_in, MI.descriptors),
                                      M.evaluate(new["program"], grid_in, MI.descriptors))


# ---------------------------------------------------------- fit outcomes ---

def test_fit_outcome_statuses_are_explicit(monkeypatch):
    _seed, schema, _concrete, pairs, _program = _first_fittable((0, 0))
    assert SF.fit_outcome(schema, pairs)["status"] == "EXACT_DEMONSTRATION_FIT"
    late = SF.fit_outcome(schema, pairs, deadline=0.0)
    assert late["status"] == "RESOURCE_EXHAUSTED" and late["program"] is None
    #  conflicting demonstrations: FIT_FAILURE with a code from the fitter
    grid_in, grid_out = pairs[0]
    conflicting = pairs + [(grid_in, np.where(grid_out == grid_out.max(), 0, grid_out))]
    failure = SF.fit_outcome(schema, conflicting)
    assert failure["status"] == "FIT_FAILURE" and failure["code"] in SF.FIT_FAILURES
    #  an evaluator that raises: EXECUTION_ERROR, never a scientific failure
    partition = schema[1][0][1][0]

    def boom(_grid):
        raise RuntimeError("injected")
    monkeypatch.setitem(M.PARTITIONS, partition, boom)
    error = SF.fit_outcome(schema, pairs)
    assert error["status"] == "EXECUTION_ERROR" and error["code"] == "RuntimeError"


# ----------------------------------------------------- data-flow boundary ---

def test_baseline_and_tfg_apis_cannot_receive_target_information():
    """Directive section 12 boundaries, checked on the signatures themselves.

    The fitter MAY receive an open candidate schema and demonstrations. The
    baseline search may receive demonstrations and its fixed language only, and
    the TFG extractor may receive the baseline's own execution evidence only:
    neither takes a schema at all, so no target program can reach them.
    """
    identifying = {"target", "concrete", "digest", "family", "seed", "regime", "split",
                   "episode", "manifest", "state"}
    #  the fitter: an open candidate schema is allowed; target metadata is not
    for fn in (SF.fit_outcome, SF.fit_induced_occurrences):
        params = set(inspect.signature(fn).parameters)
        assert not (params & identifying), (fn.__name__, params & identifying)
        assert "schema" in params and "pairs" in params
    #  the baseline and the TFG builder: no schema parameter exists
    assert set(inspect.signature(MB.run_baseline).parameters) == {"pairs", "config"}
    assert set(inspect.signature(MB.tfg_from_trace).parameters) == {"pairs", "trace", "config"}
    assert set(inspect.signature(MB.hypothesis_space).parameters) == {"config"}
    #  and the baseline module cannot REACH the generator: checked on the import
    #  graph and the call graph, never by banning words in prose
    import ast as pyast
    tree = pyast.parse((ROOT / "cora_tti" / "meta_baseline.py").read_text())
    imported = set()
    for node in pyast.walk(tree):
        if isinstance(node, pyast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, pyast.ImportFrom):
            imported.add(node.module or "")
            imported.update(f"{node.module}.{a.name}" for a in node.names)
    generator_modules = {"cora_tti.constructive_dataset", "cora_tti.constructive_v2c",
                         "cora_tti.constructive_vocabulary", "cora_tti.constructive_v2_dataset"}
    assert not (imported & generator_modules), imported & generator_modules
    assert not any(name.endswith(".constructive_dataset") or name.endswith(".constructive_v2c")
                   for name in imported), imported
    called = {node.func.attr for node in pyast.walk(tree)
              if isinstance(node, pyast.Call) and isinstance(node.func, pyast.Attribute)}
    assert not (called & {"sample_target", "instantiate_tables", "digest_of_target"}), called


def test_admission_hands_the_baseline_only_demonstrations(monkeypatch):
    seen = []
    real = MB.run_baseline

    def spy(pairs, config):
        seen.append((pairs, config))
        return real(pairs, config)
    monkeypatch.setattr(MB, "run_baseline", spy)
    seed, schema, _c, _p, _prog = _first_fittable((0, 0))
    state = V2C.CensusState(v1_exclusion=set())
    V2C.evaluate_target_v2c(schema, seed=seed, split="t", regime="train_pool",
                            allowed_families=[(0, 0)], state=state, config=CONFIG,
                            budgets=BUDGETS, row_index=0)
    assert seen, "baseline was not consulted"
    pairs, config = seen[0]
    assert config is CONFIG
    for a, b in pairs:
        assert isinstance(a, np.ndarray) and isinstance(b, np.ndarray)


# ------------------------------------------------------ persistent guards ---

def test_persistent_state_makes_duplicates_and_exclusion_observable():
    seed, schema, _c, _p, _prog = _first_fittable((0, 0))
    state = V2C.CensusState(v1_exclusion=set())
    first, _, _ = V2C.evaluate_target_v2c(schema, seed=seed, split="t", regime="train_pool",
                                          allowed_families=[(0, 0)], state=state, config=CONFIG,
                                          budgets=BUDGETS, row_index=0)
    second, _, _ = V2C.evaluate_target_v2c(schema, seed=seed, split="t", regime="train_pool",
                                           allowed_families=[(0, 0)], state=state, config=CONFIG,
                                           budgets=BUDGETS, row_index=1)
    assert first != "duplicate_target" and second == "duplicate_target"
    assert state.attempts == 2 and state.units()["unique_schemas"] == 1
    excluded = V2C.CensusState(v1_exclusion={CV.digest(schema)})
    third, _, _ = V2C.evaluate_target_v2c(schema, seed=seed, split="t", regime="train_pool",
                                          allowed_families=[(0, 0)], state=excluded, config=CONFIG,
                                          budgets=BUDGETS, row_index=2)
    assert third == "prior_v1_target_overlap"


def test_census_runner_never_creates_fresh_guards_per_attempt():
    source = (ROOT / "cora_tti" / "constructive_v2c_census.py").read_text()
    loop = source[source.index("for family_index, family in enumerate(families):"):
                  source.index("return finalize(")]
    assert "set()" not in loop and "CensusState(" not in loop
    assert "rebuild_state(" in source


# ----------------------------------------------- deterministic generation ---

def test_v2c_instantiation_is_identical_across_hash_seeds():
    probe = ("import sys, json; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
             "from cora_tti import constructive_dataset as CD, constructive_v2c as V\n"
             "seed = 5_100_000 + 3*7919 + 2*1013\n"
             "schema = CD.sample_target(seed, (0, 0))\n"
             "grids = [CD.generate_grid(seed*97+i) for i in range(6)]\n"
             "c = V.instantiate_tables(schema, grids)\n"
             "print(json.dumps([[repr(k), v] for s in c[1] if s[0]=='Map' "
             "for k, v in s[1][1][1][0]]))\n") % (str(ROOT), str(ROOT / "src"))
    outputs = []
    for hashseed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=hashseed, OMP_NUM_THREADS="1")
        outputs.append(subprocess.run([sys.executable, "-c", probe], env=env,
                                      capture_output=True, text=True, check=True).stdout)
    assert outputs[0] == outputs[1]


# ------------------------------------------------ irreducibility contract ---

def test_direct_ablation_detects_a_provably_redundant_select():
    """Select("all") is the identity filter (proved in the predicate audit), so a
    single-block target carrying it is locally reducible: removing that stage
    must reproduce both the demonstrations and the frozen-probe behaviour."""
    found = _first_redundant_select_fixture()
    if found is None:
        pytest.skip("no probe-defined redundant-Select fixture in the searched range")
    schema, pairs, fit = found
    fp, status = CP.fingerprint_with_diagnostics(fit["program"], V2C._evaluate)
    assert sum(1 for s in status if s == "OK") > 0, "fixture must be probe-defined"
    audit = V2C.irreducibility_audit_v2c(schema, fit["program"], pairs, fp, status)
    assert audit["reducible"], audit["counts"]
    hit = [a for a in audit["ablations"] if a.get("outcome") == "REPRODUCING_ABLATION_FOUND"]
    assert hit and hit[0]["kind"] == "select"
    assert hit[0]["direct"]["demo_behaviour"] == "exact"
    assert hit[0]["direct"]["probe_fingerprint_equal"] is True
    assert hit[0]["direct"]["defined_probes"] >= 0
    assert hit[0]["refitted"]["status"] in ("EXACT_DEMONSTRATION_FIT", "FIT_FAILURE",
                                            "CONSTRAINT_CONSISTENT_BINDING")


def test_duplicate_block_is_unobservable_not_silently_admitted():
    """A block fully overwritten by a later identical block has no visible
    constraining cell, so the fitter refuses it (slot_unobservable) rather than
    fitting an unidentifiable table. Recorded because it means block-level
    redundancy is mostly pre-empted at fitting, before the ablation audit."""
    seed, single, _c, _p, _prog = _first_fittable((0,), limit=600)
    partition, _selects, feature = CV.blocks_from_ast(single)[0]
    schema = CV.ast_from_blocks([(partition, (), feature), (partition, (), feature)])
    _concrete, pairs = _demos_for(schema, seed)
    if len(pairs) < 3:
        pytest.skip("duplicate-block fixture renders no demonstrations")
    fit = SF.fit_outcome(schema, pairs)
    assert fit["status"] == "FIT_FAILURE"
    assert fit["code"] in ("slot_unobservable", "slot_key_unobserved")


def test_injected_exception_is_inconclusive_not_necessity(monkeypatch):
    seed, schema, _c, pairs, program = _first_fittable((0, 0))
    fp, status = CP.fingerprint_with_diagnostics(program, V2C._evaluate)
    calls = {"n": 0}
    real = V2C._compare_program

    def flaky(program_, pairs_, target_fp, target_status):
        calls["n"] += 1
        raise RuntimeError("injected probe failure")
    monkeypatch.setattr(V2C, "_compare_program", flaky)
    audit = V2C.irreducibility_audit_v2c(schema, program, pairs, fp, status)
    assert calls["n"] >= 1
    assert audit["counts"]["INCONCLUSIVE"] >= 1
    assert audit["counts"]["NO_REPRODUCING_ABLATION_FOUND_WITHIN_DECLARED_PROCEDURE"] == 0
    assert audit["inconclusive"] and not audit["reducible"]
    monkeypatch.setattr(V2C, "_compare_program", real)


def test_single_block_block_ablation_is_not_applicable():
    seed, schema, _c, pairs, program = _first_fittable((0,), limit=600)
    fp, status = CP.fingerprint_with_diagnostics(program, V2C._evaluate)
    audit = V2C.irreducibility_audit_v2c(schema, program, pairs, fp, status)
    kinds = {(a["kind"], a.get("outcome")) for a in audit["ablations"]}
    assert ("block", "NOT_APPLICABLE") in kinds


# -------------------------------------------- baseline / TFG identity ---

def test_baseline_hypothesis_space_equals_actual_search_space():
    actual = {(p, q, f) for p in MI.PARTITIONS for q in MI.PREDICATES for f in MI.KEY_FEATURES}
    ours = {MB._triple(s) for s in MB.hypothesis_space(CONFIG)}
    assert ours == actual and len(ours) == 200


def test_tfg_carries_the_baseline_configuration_and_mismatch_is_rejected(monkeypatch):
    seed, schema, _c, pairs, _prog = _first_fittable((0, 0))
    trace = MB.run_baseline(pairs, CONFIG)
    tfg = MB.tfg_from_trace(pairs, trace, CONFIG)
    carried = MB.tfg_configuration(tfg)
    assert carried["baseline_config"] == CONFIG.digest()
    assert carried["trace_config"] == MB.trace_config_digest(CONFIG)
    assert trace.work_done == 200 and not trace.truncated

    other = MB.BaselineConfig(max_frontier_terms=3)
    assert other.digest() != CONFIG.digest()
    real = MB.tfg_from_trace

    def wrong_config(pairs_, trace_, config_):
        return real(pairs_, trace_, other)
    monkeypatch.setattr(MB, "tfg_from_trace", wrong_config)
    state = V2C.CensusState(v1_exclusion=set())
    outcome, episode, evidence = V2C.evaluate_target_v2c(
        schema, seed=seed, split="t", regime="train_pool", allowed_families=[(0, 0)],
        state=state, config=CONFIG, budgets=BUDGETS, row_index=0)
    if "tfg" in evidence["stage_times"]:
        assert outcome == "baseline_tfg_config_mismatch"
    else:
        pytest.skip(f"target rejected before the TFG stage: {outcome}")


def test_admitted_episode_records_units_configs_and_passes_leak_scan():
    found = None
    for start in range(0, 2000, 200):
        seed, schema, _c, pairs, _prog = _first_fittable((0, 0), start=start)
        state = V2C.CensusState(v1_exclusion=set())
        outcome, episode, evidence = V2C.evaluate_target_v2c(
            schema, seed=seed, split="t", regime="train_pool", allowed_families=[(0, 0)],
            state=state, config=CONFIG, budgets=BUDGETS, row_index=0)
        if outcome == V2C.ADMITTED:
            found = episode
            break
    if found is None:
        pytest.skip("no admitted (0,0) target in the searched range")
    assert found["baseline_config_digest"] == CONFIG.digest()
    assert found["trace_config_digest"] == MB.trace_config_digest(CONFIG)
    assert found["units"]["schema_digest"] == found["target_digest"]
    assert found["fitter_options"]["target"] == found["fitter_options"]["baseline_strict"]
    assert found["irreducibility"]["counts"]["INCONCLUSIVE"] == 0
    assert "target_defined_probes" in found["probe_coverage"]
    assert found["environment"]["PYTHONHASHSEED"] is not None


def test_seed_schedule_is_collision_free_for_the_manifest_shape():
    manifest = {"seed_schedule": {"namespace": 5_300_000, "family_stride": 2_000_003,
                                  "attempt_stride": 7919}}
    from cora_tti import constructive_v2c_census as R
    seeds = [R.seed_for(manifest, fi, a) for fi in range(7) for a in range(128)]
    assert len(seeds) == len(set(seeds)) == 896


# --------------------------------- checker failures are never scientific ---

def test_incomplete_baseline_cannot_support_admission(monkeypatch):
    """A truncated or errored baseline is not evidence that the baseline failed."""
    seed, schema, _c, _p, _prog = _first_fittable((0, 0))
    state = V2C.CensusState(v1_exclusion=set())
    cut = MB.BaselineConfig(work_limit_schemas=50)
    outcome, episode, evidence = V2C.evaluate_target_v2c(
        schema, seed=seed, split="t", regime="train_pool", allowed_families=[(0, 0)],
        state=state, config=cut, budgets=BUDGETS, row_index=0)
    assert outcome == "baseline_incomplete", outcome
    assert episode is None
    assert evidence["baseline_incompleteness"]
    assert evidence["baseline"]["complete"] is False

    #  and an erroring baseline likewise
    real = MB.run_baseline

    def erroring(pairs, config):
        trace = real(pairs, config)
        trace.errors = 3
        trace.census["EXECUTION_ERROR"] = 3
        return trace
    monkeypatch.setattr(MB, "run_baseline", erroring)
    state2 = V2C.CensusState(v1_exclusion=set())
    outcome2, _e, ev2 = V2C.evaluate_target_v2c(
        schema, seed=seed, split="t", regime="train_pool", allowed_families=[(0, 0)],
        state=state2, config=CONFIG, budgets=BUDGETS, row_index=0)
    assert outcome2 == "baseline_incomplete", outcome2
    assert any("EXECUTION_ERROR" in reason for reason in ev2["baseline_incompleteness"])


def test_checker_failure_codes_are_disjoint_from_scientific_rejections():
    from cora_tti import constructive_v2c_census as R
    assert set(V2C.CHECKER_FAILURE_CODES) <= set(V2C.REJECTION_CODES_V2C)
    rows = []
    for index, outcome in enumerate(["ADMITTED", "scoped_fit_failed", "baseline_incomplete",
                                     "irreducibility_inconclusive", "probe_execution_error",
                                     "infra_exception:ValueError"]):
        rows.append({"family": [0, 0], "family_text": "(0,0)", "attempt": index,
                     "regime": "train_pool", "outcome": outcome, "schema_digest": f"d{index}",
                     "units": {}, "seconds": 0.1})
    scientific = {r["outcome"] for r in rows
                  if not r["outcome"].startswith(V2C.INFRA_PREFIX)
                  and r["outcome"] not in V2C.CHECKER_FAILURE_CODES}
    assert scientific == {"ADMITTED", "scoped_fit_failed"}
    checker = {r["outcome"] for r in rows if r["outcome"] in V2C.CHECKER_FAILURE_CODES}
    assert checker == {"baseline_incomplete", "irreducibility_inconclusive",
                       "probe_execution_error"}


def test_baseline_work_limit_below_the_space_is_recorded_as_truncation():
    seed, _s, _c, pairs, _p = _first_fittable((0, 0))
    full = MB.run_baseline(pairs, CONFIG)
    assert full.complete() and full.work_done == full.enumerated_total == 200
    cut = MB.run_baseline(pairs, MB.BaselineConfig(work_limit_schemas=50))
    assert not cut.complete() and cut.truncated
    assert cut.exhausted == 150
    assert any("work_limit_schemas" in c for c in cut.truncation_causes)
    assert cut.summary()["search_complete" if "search_complete" in cut.summary() else "complete"] is False


# ----------------------------------------------- restart and provenance ---

def test_restart_restores_the_guard_state_of_an_errored_attempt():
    from cora_tti import constructive_v2c_census as R
    manifest = {"historical_exclusion": {
        "path": "outputs/tti/constructive_v1_1_target_exclusion.json",
        "sha256": __import__("hashlib").sha256(
            (ROOT / "outputs/tti/constructive_v1_1_target_exclusion.json").read_bytes()).hexdigest()}}
    rows = [
        {"family_text": "(0,0)", "attempt": 0, "regime": "train_pool", "outcome": "ADMITTED",
         "schema_digest": "aaa", "units": {"schema_digest": "aaa", "concrete_digest": "c1",
                                           "demo_bundle_digest": "d1"}},
        #  an attempt that raised: units empty, digest only at top level
        {"family_text": "(0,0)", "attempt": 1, "regime": "train_pool",
         "outcome": "infra_exception:ValueError", "schema_digest": "bbb", "units": {}},
    ]
    state = R.rebuild_state(manifest, rows)
    assert "bbb" in state.seen_digests, "restart lost the digest of an errored attempt"
    assert "aaa" in state.seen_train_digests
    assert state.units()["unique_schemas"] == 2


def test_resume_refuses_rows_from_a_different_manifest(tmp_path, monkeypatch):
    from cora_tti import constructive_v2c_census as R
    attempts = tmp_path / "attempts.jsonl"
    attempts.write_text(json.dumps({"manifest_sha256": "OTHER", "family_text": "(0,0)",
                                    "attempt": 0, "regime": "train_pool",
                                    "outcome": "ADMITTED", "schema_digest": "x"}) + "\n")
    monkeypatch.setattr(R, "ATTEMPTS", attempts)
    with pytest.raises(RuntimeError, match="different"):
        R.existing_rows("MINE")
    assert R.existing_rows("OTHER")


def test_every_recorded_setting_the_admission_law_uses_comes_from_its_argument():
    """The demonstration protocol is passed in, not hard-coded on the path."""
    source = (ROOT / "cora_tti" / "constructive_v2c.py").read_text()
    body = source[source.index("def evaluate_target_v2c("):]
    assert "range(14)" not in body and "grid_seeds[:6]" not in body
    assert "min_demos=3" not in body
    assert 'gen["candidate_grids"]' in body and 'gen["min_demos"]' in body


def test_demonstration_only_reproduction_is_recorded_separately():
    """An ablation that replays the demonstrations but differs on the probes does
    not meet the reducibility criterion, and must not vanish silently."""
    found = _first_redundant_select_fixture()
    if found is None:
        pytest.skip("no probe-defined redundant-Select fixture")
    schema, pairs, fit = found
    fp, status = CP.fingerprint_with_diagnostics(fit["program"], V2C._evaluate)
    audit = V2C.irreducibility_audit_v2c(schema, fit["program"], pairs, fp, status)
    assert "demonstration_only_reproducing_ablations" in audit
    assert "demonstrations_do_not_witness_a_stage" in audit
    for entry in audit["ablations"]:
        if entry.get("outcome") != "NOT_APPLICABLE":
            assert "demonstrations_only_reproduced" in entry


def test_code_hash_set_covers_the_graph_builder():
    assert "cora_parent/tfg.py" in V2C.CODE_FILES_V2C
    assert "cora_tti/constructive_v2_dataset.py" in V2C.CODE_FILES_V2C
    hashes = V2C.code_hashes_v2c()
    assert set(hashes) == set(V2C.CODE_FILES_V2C)


def test_episode_ids_are_unique_across_families():
    ids = set()
    for family in ((0, 0), (1, 1)):
        seed, schema, _c, _p, _prog = _first_fittable(family)
        state = V2C.CensusState(v1_exclusion=set())
        outcome, episode, _ev = V2C.evaluate_target_v2c(
            schema, seed=seed, split="census", regime="train_pool",
            allowed_families=[family], state=state, config=CONFIG, budgets=BUDGETS,
            row_index=7)
        if outcome == V2C.ADMITTED:
            assert episode["episode_id"] not in ids, "episode id collision across families"
            ids.add(episode["episode_id"])


def test_all_undefined_fingerprints_collide_and_never_count_as_agreement():
    """Every program undefined on every probe shares one fingerprint, so a
    match there is not evidence of behavioural agreement."""
    def prog(partition, feature, key, colour):
        return ("Compose", (("Partition", (partition,)),
                            ("Map", (("Key", (feature,)), ("Lookup", (((key, colour),),)))),
                            ("Paint", ())))
    a = prog("enclosed_regions", "area", 999_999, 7)
    b = prog("colour_components", "area", 888_888, 3)
    fa, sa = CP.fingerprint_with_diagnostics(a, V2C._evaluate)
    fb, sb = CP.fingerprint_with_diagnostics(b, V2C._evaluate)
    assert sum(1 for s in sa if s == "OK") == 0 and sum(1 for s in sb if s == "OK") == 0
    assert fa == fb, "precondition: all-undefined fingerprints collide"
    vacuous = {"demo_behaviour": "exact", "probe_fingerprint_equal": True,
               "both_defined_probes": 0, "probe_errors": 0}
    real = dict(vacuous, both_defined_probes=4)
    assert not V2C._reproduces(vacuous), "a vacuous match must not establish redundancy"
    assert V2C._vacuous_probe_match(vacuous)
    assert V2C._reproduces(real) and not V2C._vacuous_probe_match(real)


def test_probe_floor_defaults_to_non_vacuous():
    assert inspect.signature(V2C.evaluate_target_v2c).parameters["min_defined_probes"].default == 1
