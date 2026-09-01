"""Tests for the ARC TFG extractor: real trace search -> ConcreteTFG.

Fixture note (learned empirically, kept as documentation): the frozen slot
learner accepts only functional feature->colour evidence covered by regions,
so on genuinely unsolvable tasks the census is typically ALL slot_fit_failed;
executed_not_exact arises when a fitted map renders wrong. The extractor
treats both as frontier terms; the executed_not_exact path is unit-tested with
a hand-built observer so it does not depend on engine learnability quirks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V                # noqa: E402
from level4_blind_runtime import env as E                    # noqa: E402
from level4_blind_runtime import stepA_trace_search as TS    # noqa: E402
from cora_parent.tfg import ConcreteTFG                      # noqa: E402
from cora_tti import dropout_generator as DG                 # noqa: E402
from cora_tti import tfg_extractor as TX                     # noqa: E402


def rng(seed=0):
    return np.random.default_rng(seed)


def area_repaint_pairs():
    """The gates-style area-repaint family, PROVEN solvable by the frozen
    search (single cell -> 6, two-cell component -> 7)."""
    pairs = []
    layouts = [((0, 0), ((2, 2), (2, 3))), ((3, 4), ((0, 1), (1, 1))),
               ((4, 0), ((0, 3), (0, 4)))]
    for single, pair in layouts:
        g = np.zeros((5, 5), dtype=int)
        g[single] = 3
        for c in pair:
            g[c] = 3
        o = g.copy()
        o[single] = 6
        for c in pair:
            o[c] = 7
        pairs.append((g, o))
    return pairs


def unsolvable_pairs(n=3):
    """Constant unrelated output: nothing in the language can produce it."""
    pairs = []
    for i in range(n):
        grid = DG.random_grid(rng(50 + i))
        pairs.append((grid, np.full((2, 2), 9, dtype=int)))
    return pairs


def test_solvable_task_yields_no_tfg():
    report = TX.extract(area_repaint_pairs(), budget_s=6.0)
    assert report["solved"] is True
    assert report["tfg"] is None and report["programs"]


def test_unsolvable_task_yields_structured_tfg_with_frontier():
    report = TX.extract(unsolvable_pairs(), budget_s=2.0)
    assert report["solved"] is False
    tfg = report["tfg"]
    assert isinstance(tfg, ConcreteTFG)
    kinds = {n.kind for n in tfg.nodes()}
    assert {"goal", "delta_signature", "palette_change",
            "execution", "frontier_term", "slot"} <= kinds
    frontier = tfg.nodes_of_kind("frontier_term")
    assert frontier, "an unsolvable task must expose frontier terms"
    for node in frontier:
        assert node.attrs["outcome"] in TX.FRONTIER_OUTCOMES
        assert node.attrs["surface_nodes"] >= 1
        assert node.attrs["op"]
    #  round-trips and self-consistent digest
    again = ConcreteTFG.from_json(json.loads(json.dumps(tfg.to_json())))
    assert again.digest() == tfg.digest()
    execution = tfg.nodes_of_kind("execution")[0]
    assert execution.attrs["outcome_census"].get("slot_fit_failed", 0) > 0


def test_executed_not_exact_path_with_hand_built_observer():
    """Deterministic unit test of the near-miss path: a fitted program that
    renders wrongly must yield a frontier term WITH a value signature."""
    pairs = [(np.asarray(a), np.asarray(b)) for a, b in area_repaint_pairs()]
    #  a real fitted program: repaint every component to colour 5 (wrong)
    wrong = ("PaintEach", (("Map_V1", (("Partition", ("colour_components",)),
             ("Compose_V1", (("Key", ("colour",)), ("Lookup", ({3: 5},)))))),))
    rendered = E.evaluate(wrong, pairs[0][0], E.BASE_ENV)
    assert rendered is not None and not np.array_equal(rendered, pairs[0][1])
    observer = TS.TraceObserver()
    observer.candidates.append((wrong, "typed"))
    observer.candidates.append((wrong, "executed_not_exact"))

    class Stats:
        typed = 1; generated = 4; rejected = 1; max_depth = 4
        semantic_classes = 0; seconds = 0.2
    tfg = TX.build_tfg(pairs, Stats, observer, E.BASE_ENV)
    frontier = tfg.nodes_of_kind("frontier_term")
    assert len(frontier) == 1
    assert frontier[0].attrs["outcome"] == "executed_not_exact"
    signatures = tfg.nodes_of_kind("value_signature")
    assert len(signatures) == 1
    assert signatures[0].attrs["defined"] is True
    assert signatures[0].attrs["cells_wrong"] >= 1
    #  near misses outrank slot failures in the frontier ordering
    observer.candidates.append((("Partition", ("colour_components",)),
                                "slot_fit_failed"))
    tfg2 = TX.build_tfg(pairs, Stats, observer, E.BASE_ENV,
                        max_frontier_terms=1)
    only = tfg2.nodes_of_kind("frontier_term")
    assert len(only) == 1 and only[0].attrs["outcome"] == "executed_not_exact"


def test_observer_always_uninstalled():
    TX.extract(unsolvable_pairs(1), budget_s=0.3)
    assert isinstance(TS._OBS, TS._NullObserver)
    try:
        TX.extract([("not", "grids")], budget_s=0.2)
    except Exception:
        pass
    assert isinstance(TS._OBS, TS._NullObserver)


def test_frontier_capped_and_deduplicated():
    report = TX.extract(unsolvable_pairs(), budget_s=2.0, max_frontier_terms=3)
    tfg = report["tfg"]
    frontier = tfg.nodes_of_kind("frontier_term")
    assert 1 <= len(frontier) <= 3
    asts = [n.attrs["ast"] for n in frontier]
    assert len(set(asts)) == len(asts)


def test_no_identity_content_in_tfg():
    report = TX.extract(unsolvable_pairs(), budget_s=1.0)
    text = report["tfg"].canonical().lower()
    for banned in ("task_id", "source_token", "family"):
        assert banned not in text
