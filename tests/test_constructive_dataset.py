"""Dataset gates: model-view law, leakage controls, admission accounting."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_tti import constructive_dataset as CD      # noqa: E402
from cora_tti import constructive_vocabulary as CV   # noqa: E402


def _episode() -> CD.TrustedEpisode:
    schema = CV.ast_from_blocks([("colour_components",
                                  ("rectangular", "not_touching_border"), "area")])
    from geocat_arc.object_reasoning import meta_ast as M
    grid = CD.generate_grid(11000).tolist()
    out = [[9 if v else 0 for v in row] for row in grid]
    return CD.TrustedEpisode(
        episode_id="t-0", split="test", regime="structural_holdout",
        generation_seed=1, demonstrations=[{"input": grid, "output": out}] * 3,
        target_schema_json=M.ast_to_json(schema),
        target_concrete_json=M.ast_to_json(schema),
        target_tokens=[list(t) for t in CV.tokens_from_ast(schema)],
        target_digest=CV.digest(schema),
        structural_family=list(CV.family(schema)),
        block_count=1, stage_count=CV.stage_count(schema),
        node_count=CV.mdl(schema), schema_mdl=CV.mdl(schema),
        slot_declarations={"?0": "Map[FeatureValue,Colour]"},
        fitted_slot_values={}, tfg={"interface": ["Grid", "Grid"],
                                    "nodes": [], "edges": []},
        tfg_digest="d" * 64, base_search_evidence={}, baseline_shape_audit={},
        target_fit_evidence={}, probe_fingerprint="f" * 64, diagnostics={},
        protocol_hash="p", code_hash="c")


def test_model_view_allowlist_exact():
    ep = _episode()
    view = CD.to_model_view(ep, 0)
    assert set(view) == CD.MODEL_VIEW_ALLOWLIST
    assert set(view["features"]) <= CD.FEATURE_ALLOWLIST
    assert CD.scan_model_view(view, ep) == []


def test_leak_injection_digest_under_innocent_key():
    ep = _episode()
    view = CD.to_model_view(ep, 0)
    view["note"] = ep.target_digest
    assert CD.scan_model_view(view, ep)


def test_leak_injection_tokens_as_list():
    ep = _episode()
    view = CD.to_model_view(ep, 0)
    view["features"]["search_typed"] = 1
    view["tfg"]["nodes"] = [{"kind": "goal", "attrs":
                             {"x": json.dumps([list(t) for t in ep.target_tokens])}}]
    findings = CD.scan_model_view(view, ep)
    assert any("token" in f for f in findings)


def test_leak_injection_family_in_nested_metadata():
    ep = _episode()
    view = CD.to_model_view(ep, 0)
    view["tfg"]["meta"] = {"deep": {"f": CV.family_text(tuple(ep.structural_family))}}
    assert CD.scan_model_view(view, ep)


def test_leak_injection_schema_via_tfg_node_attribute():
    ep = _episode()
    view = CD.to_model_view(ep, 0)
    view["tfg"]["nodes"] = [{"kind": "goal",
                             "attrs": {"s": json.dumps(ep.target_schema_json,
                                                       sort_keys=True)}}]
    assert CD.scan_model_view(view, ep)


def test_leak_injection_digest_in_filename_like_string():
    ep = _episode()
    view = CD.to_model_view(ep, 0)
    view["tfg"]["src"] = f"/tmp/{ep.target_digest[:16]}.json"
    assert CD.scan_model_view(view, ep)


def test_leak_unapproved_field_rejected():
    ep = _episode()
    view = CD.to_model_view(ep, 0)
    view["structural_family"] = [2]
    findings = CD.scan_model_view(view, ep)
    assert any("undeclared_field" in f or "trusted_key" in f for f in findings)


def test_grid_process_is_common_and_deterministic():
    a = CD.generate_grid(11000)
    b = CD.generate_grid(11000)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, CD.generate_grid(11001))
    from geocat_arc.object_reasoning import meta_ast as M
    for name, builder in M.PARTITIONS.items():
        assert builder(a) is not None


def test_sampler_is_deterministic_and_family_exact():
    for family in [(2,), (1, 1), (0, 0, 0)]:
        first = CD.sample_target(4242, family)
        assert CD.sample_target(4242, family) == first
        assert CV.family(first) == family
        ok, code = CV.validate(first)
        assert ok, code


def test_banned_family_target_is_rejected():
    schema = CV.ast_from_blocks([("colour_components", ("all",), "area")])  # (1,)
    out, ep, ev = CD.evaluate_target(
        schema, seed=1, split="train", regime="train_pool",
        allowed_families=[(1,)], seen_digests=set(), seen_train_digests=set(),
        train_families=set(), budgets={"per_target_s": 30, "base_search_s": 2,
                                       "tfg_s": 1}, row_index=0)
    assert out == "split_collision" and ep is None


def test_duplicate_digest_rejected():
    schema = CD.sample_target(99, (2,))
    out, ep, ev = CD.evaluate_target(
        schema, seed=99, split="test", regime="structural_holdout",
        allowed_families=[(2,)], seen_digests={CV.digest(schema)},
        seen_train_digests=set(), train_families=set(),
        budgets={"per_target_s": 30, "base_search_s": 2, "tfg_s": 1}, row_index=0)
    assert out == "duplicate_target"


def test_holdout_family_cannot_enter_train_pool():
    schema = CD.sample_target(7, (2,))
    out, ep, ev = CD.evaluate_target(
        schema, seed=7, split="train", regime="train_pool",
        allowed_families=[(2,)], seen_digests=set(), seen_train_digests=set(),
        train_families=set(), budgets={"per_target_s": 30, "base_search_s": 2,
                                       "tfg_s": 1}, row_index=0)
    assert out == "split_collision"


def test_every_attempt_yields_exactly_one_terminal_code():
    seen = set()
    for seed in range(6):
        schema = CD.sample_target(500 + seed, (1, 1))
        out, ep, ev = CD.evaluate_target(
            schema, seed=500 + seed, split="train", regime="train_pool",
            allowed_families=[(1, 1)], seen_digests=set(),
            seen_train_digests=set(), train_families={(1, 1)},
            budgets={"per_target_s": 30, "base_search_s": 2, "tfg_s": 1},
            row_index=seed)
        assert out == CD.ADMITTED or out in CD.REJECTION_CODES
        seen.add(out)
    assert seen
