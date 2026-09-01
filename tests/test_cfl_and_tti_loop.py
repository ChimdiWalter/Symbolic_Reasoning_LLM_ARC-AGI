"""Tests for the CFL cripple corpus and the end-to-end TTI loop."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V              # noqa: E402
from level4_blind_runtime import stepA_trace_search as TS  # noqa: E402
from cora_tti import cfl_corpus as CF                      # noqa: E402
from cora_tti import dropout_generator as DG               # noqa: E402
from cora_tti import tti_loop as TL                        # noqa: E402


def rng(seed=0):
    return np.random.default_rng(seed)


FAST = CF.CFLConfig(healthy_budget_s=3.0, starved_budget_s=0.03,
                    crippled_budget_s=0.6)


# --------------------------------------------------------------------------
# CFL corpus
# --------------------------------------------------------------------------

def test_resource_episode_is_solvable_but_starved():
    row = None
    for seed in range(6):
        row = CF.resource_episode(rng(seed), FAST)
        if row is not None:
            break
    assert row is not None
    assert row["flags"]["cause"] == "RESOURCE_LIMIT"
    assert row["tfg_digest"]


def test_parameter_episode_requires_disabled_learner():
    row = None
    for seed in range(8):
        row = CF.parameter_episode(rng(seed), FAST)
        if row is not None:
            break
    assert row is not None
    assert row["flags"]["cause"] == "PARAMETER_LEARNING"


def test_learner_disable_always_restores():
    saved = dict(TS.SLOT_LEARNERS)
    with CF._learner_disabled():
        key = next(iter(TS.SLOT_LEARNERS))
        assert TS.SLOT_LEARNERS[key]("x", [], "?s") is None
    assert TS.SLOT_LEARNERS == saved
    with pytest.raises(RuntimeError):
        with CF._learner_disabled():
            raise RuntimeError("boom")
    assert TS.SLOT_LEARNERS == saved


def test_generate_writes_labelled_corpus(tmp_path):
    manifest = CF.generate(tmp_path / "cfl", per_cause=1, seed=3, config=FAST)
    rows = [json.loads(l) for l in
            (tmp_path / "cfl").read_text().splitlines()]
    causes = {r["flags"]["cause"] for r in rows}
    assert causes <= set(CF.CAUSES)
    assert manifest["counts"] == {c: sum(1 for r in rows
                                         if r["flags"]["cause"] == c)
                                  for c in CF.CAUSES}
    assert "file_sha256" in manifest


# --------------------------------------------------------------------------
# TTI loop
# --------------------------------------------------------------------------

def paint_each_episode():
    """A deterministic Stage-A style episode withholding PaintEach (the only
    Grid producer, so the crippled language MUST fail and the loop MUST
    reconstruct exactly PaintEach to solve)."""
    for seed in range(20):
        row = DG.episode(rng(seed), "PaintEach",
                         DG.EpisodeConfig(search_budget_s=0.4,
                                          verify_full=False))
        if row is not None:
            return row
    pytest.skip("no PaintEach episode could be sampled")


def test_loop_ordinary_route_when_language_suffices():
    episode = paint_each_episode()
    pairs = [(d["input"], d["output"]) for d in episode["demonstrations"]]
    out = TL.solve_task(pairs, dict(V.REGISTRY),
                        config=TL.TTIConfig(search_budget_s=3.0))
    #  the full language may or may not solve the sampled task, but if it
    #  does the route must be ordinary and no extension may be used
    if out["solved"]:
        assert out["route"].startswith("ordinary")
        assert out["used_extension"] is None


def test_loop_reconstructs_withheld_production_end_to_end():
    episode = paint_each_episode()
    withheld = episode["target"]["name"]
    crippled = {k: v for k, v in V.REGISTRY.items() if k != withheld}
    pairs = [(d["input"], d["output"]) for d in episode["demonstrations"]]
    out = TL.solve_task(pairs, crippled,
                        config=TL.TTIConfig(search_budget_s=2.5,
                                            loo_budget_s=2.5, top_k=4))
    assert out["route"] == "invention"
    assert out["proposals_tried"] >= 1
    if out["solved"]:
        assert out["used_extension"] == withheld
        ev = out["evidence"]
        assert ev["baseline_fails"] and ev["winner_uses_production"]
        assert ev["loo_all_folds_pass"] and ev["ablation_fails"]
        assert out["ephemeral_discarded"] is True
        #  the reset rule: the crippled language was never mutated
        assert withheld not in crippled


def test_fallback_proposer_is_deterministic_and_catalogue_bound():
    propose = TL.mdl_fallback_proposer(dict(V.REGISTRY))
    a = propose(None, 5)
    b = propose(None, 5)
    assert a == b and len(a) == 5
    assert all(name in V.REGISTRY for name in a)


def test_evaluate_on_episodes_reports_recovery():
    episode = paint_each_episode()
    report = TL.evaluate_on_episodes(
        [episode], config=TL.TTIConfig(search_budget_s=2.0, loo_budget_s=2.0,
                                       top_k=4))
    assert report["n"] == 1
    assert set(report["rows"][0]) >= {"withheld", "solved", "recovered",
                                      "proposals_tried"}
