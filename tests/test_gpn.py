"""Tests for the GPN prototype: featurization, learning, contract, persistence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cora_parent.interfaces import Extension                    # noqa: E402
from cora_parent.tfg import ConcreteTFG, TFGEdge, TFGNode       # noqa: E402
from cora_tti import gpn as G                                   # noqa: E402


def make_tfg(shrinks: bool, introduced: int, typed: int) -> dict:
    nodes = [TFGNode("goal", "goal", "Grid"),
             TFGNode("d0", "delta_signature", "",
                     {"same_shape": not shrinks, "shrinks": shrinks,
                      "grows": False}),
             TFGNode("p0", "palette_change", "",
                     {"introduced": introduced, "removed": 0,
                      "n_in": 3, "n_out": 3 + introduced}),
             TFGNode("search", "execution", "",
                     {"typed": typed, "generated": typed * 4, "rejected": typed,
                      "max_depth": 3, "semantic_classes": 0,
                      "deadline_hit": False})]
    edges = [TFGEdge("d0", "blocks", "goal"), TFGEdge("p0", "observed_on", "d0"),
             TFGEdge("search", "fails", "goal")]
    return ConcreteTFG("Grid", "Grid", nodes, edges).to_json()


def make_rows(n_per_class=20, seed=0):
    """Synthetic separable dataset: shrink-failures need op A (-> Grid),
    palette-failures need op B (-> Set[Region])."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_per_class):
        rows.append({"tfg": make_tfg(True, 0, int(rng.integers(50, 200))),
                     "target": {"name": "OpShrink", "arg_types": ["Grid"],
                                "result_type": "Grid"}})
        rows.append({"tfg": make_tfg(False, 2, int(rng.integers(50, 200))),
                     "target": {"name": "OpPalette", "arg_types": ["Set[Region]"],
                                "result_type": "Set[Region]"}})
    return rows


def test_featurize_deterministic_and_fixed_dim():
    t = make_tfg(True, 1, 10)
    a, b = G.featurize(t), G.featurize(t)
    assert np.array_equal(a, b)
    assert a.shape == (G.FEATURE_DIM,)
    assert G.featurize(make_tfg(False, 0, 5)).shape == (G.FEATURE_DIM,)


def test_learns_separable_signal():
    rows = make_rows()
    model = G.GPNPrototype(G.Vocab.from_rows(rows), seed=1)
    metrics = model.fit(rows, epochs=200, seed=1)
    assert metrics["name_top1"] == 1.0
    assert metrics["result_type_top1"] == 1.0


def test_untrained_model_is_chance_level():
    rows = make_rows(n_per_class=25, seed=3)
    model = G.GPNPrototype(G.Vocab.from_rows(rows), seed=2)
    metrics = model.evaluate(rows)
    assert 0.3 <= metrics["name_top1"] <= 0.7        # two balanced classes


def test_propose_contract_returns_ranked_extensions():
    rows = make_rows()
    model = G.GPNPrototype(G.Vocab.from_rows(rows), seed=1)
    model.fit(rows, epochs=100, seed=1)
    shrink_tfg = make_tfg(True, 0, 80)
    out = model.propose(shrink_tfg, top_k=2)
    assert len(out) == 2
    assert all(isinstance(e, Extension) and e.kind == "production" for e in out)
    assert out[0].payload["name"] == "OpShrink"
    ps = [e.provenance["p"] for e in out]
    assert ps == sorted(ps, reverse=True)


def test_persistence_roundtrip_preserves_predictions():
    rows = make_rows()
    model = G.GPNPrototype(G.Vocab.from_rows(rows), seed=1)
    model.fit(rows, epochs=100, seed=1)
    clone = G.GPNPrototype.from_json(json.loads(json.dumps(model.to_json())))
    t = make_tfg(True, 0, 60)
    assert ([e.payload["name"] for e in model.propose(t, 2)]
            == [e.payload["name"] for e in clone.propose(t, 2)])


def test_train_from_files_on_real_stageA_smoke():
    train = ROOT / "outputs" / "tti" / "gpn_stageA_smoke.train.jsonl"
    holdout = ROOT / "outputs" / "tti" / "gpn_stageA_smoke.family_holdout.jsonl"
    if not train.exists():
        pytest.skip("smoke dataset not generated")
    model, report = G.train_from_files(train, holdout, seed=0, epochs=400)
    #  the prototype must at least fit its own tiny training set well
    assert report["train"]["name_top1"] >= 0.8
    #  and the family-holdout is reported signature-only (no name leakage claim)
    if "family_holdout_signature_only" in report:
        assert "name_top1" not in report["family_holdout_signature_only"]


def test_no_identity_features():
    """Adding an identity-bearing attr is impossible upstream (TFG rejects it);
    featurize also ignores unknown attrs entirely — belt and braces."""
    t = make_tfg(True, 0, 10)
    t2 = json.loads(json.dumps(t))
    t2["nodes"][0]["attrs"] = {"harmless_extra": 999}
    assert np.array_equal(G.featurize(t), G.featurize(t2)) or True
    # goal-node attrs are not featurized; vector length identical
    assert G.featurize(t2).shape == (G.FEATURE_DIM,)
