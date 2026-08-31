"""Tests for the Stage-A operator-dropout generator. Synthetic only; short budgets."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V          # noqa: E402
from level4_blind_runtime import env as E              # noqa: E402
from cora_tti import dropout_generator as DG           # noqa: E402
from cora_parent.tfg import ConcreteTFG                # noqa: E402


def rng(seed=0):
    return np.random.default_rng(seed)


def test_sampler_produces_typed_executable_programs():
    env = E.LanguageEnv(base=dict(V.REGISTRY), label="full")
    executable = 0
    for i in range(200):
        ast = DG.sample_ast(rng(i), DG.GOAL, V.REGISTRY)
        if ast is None:
            continue
        out = E.evaluate(ast, DG.random_grid(rng(1000 + i)), env)
        executable += out is not None
    assert executable >= 5, "the sampler must yield some executable programs"


def test_uses_detects_production_anywhere():
    inner = ("Partition", ("colour_components",))
    ast = ("PaintEach", (("Map_V1", (inner, ("Compose_V1", (("Key", ("area",)),
           ("Lookup", ({1: 3},)))))),))
    assert DG.uses(ast, "Partition")
    assert DG.uses(ast, "Lookup")
    assert not DG.uses(ast, "Select")
    assert not DG.uses(("Partition", ("colour_components",)), "PaintEach")


def test_render_demos_rejects_identity_programs():
    #  a program that never changes the grid must be rejected as degenerate
    class Stats: pass
    env = E.LanguageEnv(base=dict(V.REGISTRY), label="full")
    identity = ("PaintEach", (("Map_V1", (("Partition", ("colour_components",)),
                ("Compose_V1", (("Key", ("colour",)),
                                ("Lookup", ({},)))))),))
    pairs = DG.render_demos(identity, rng(3), env)
    #  either undefined (None accepted) or, if defined, must show change
    if pairs is not None:
        assert any(not np.array_equal(a, b) for a, b in pairs)


def test_tfg_from_failure_is_anonymous_and_stable():
    pairs = [(np.zeros((4, 4), dtype=int), np.ones((2, 2), dtype=int))]

    class Stats:
        typed = 10; generated = 50; rejected = 40; max_depth = 3
        semantic_classes = 0; seconds = 0.5
    t = DG.tfg_from_failure(pairs, Stats)
    text = t.canonical()
    for name in V.REGISTRY:
        assert name not in text, "no production name may leak into the TFG"
    again = ConcreteTFG.from_json(json.loads(json.dumps(t.to_json())))
    assert again.digest() == t.digest()
    kinds = {n.kind for n in t.nodes()}
    assert {"goal", "delta_signature", "palette_change", "execution"} <= kinds


def test_episode_rejects_when_language_does_not_force_the_op():
    #  ArgMax@Entity is unreachable from goal Grid in this registry subset, so no
    #  sampled Grid program uses it -> episode returns None fast (sampler gives up)
    out = DG.episode(rng(1), "ArgMax@Entity",
                     DG.EpisodeConfig(search_budget_s=0.2, verify_full=False))
    assert out is None


def test_episode_end_to_end_for_a_forced_production():
    #  PaintEach is the ONLY producer of Grid: every program uses it, and without
    #  it the crippled search cannot even type a Grid program -> forced episode
    row = None
    for seed in range(12):
        row = DG.episode(rng(seed), "PaintEach",
                         DG.EpisodeConfig(search_budget_s=0.4, verify_full=False))
        if row is not None:
            break
    assert row is not None, "expected at least one PaintEach episode"
    assert row["target"]["name"] == "PaintEach"
    assert row["target"]["result_type"] == "Grid"
    assert row["flags"]["cause"] == "SEMANTICS"
    assert len(row["demonstrations"]) == DG.DEMOS_PER_EPISODE
    text = json.dumps(row["tfg"], sort_keys=True)
    assert "PaintEach" not in text, "the withheld target must not leak into the TFG"


def test_family_of_strips_grounding():
    assert DG.family_of("ArgMax@Entity") == "ArgMax"
    assert DG.family_of("PaintEach") == "PaintEach"


def test_generate_writes_split_files_and_manifest(tmp_path):
    out = tmp_path / "stageA"
    manifest = DG.generate(out, episodes_per_production=1, seed=7,
                           holdout_families=["Select"],
                           productions=["PaintEach", "Select"],
                           config=DG.EpisodeConfig(search_budget_s=0.3,
                                                   verify_full=False))
    train = (tmp_path / "stageA.train.jsonl").read_text().splitlines()
    manifest_file = json.loads((tmp_path / "stageA.manifest.json").read_text())
    assert manifest["counts"] == manifest_file["counts"]
    assert manifest["seed"] == 7
    #  PaintEach rows (if any) land in train; Select rows (if any) in holdout
    for line in train:
        assert json.loads(line)["target"]["name"] != "Select"
    #  files hashed in the manifest
    assert set(manifest["files"]) == {"stageA.train.jsonl",
                                      "stageA.family_holdout.jsonl"}
