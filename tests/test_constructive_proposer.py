"""Frozen synthetic controls for the Stage-B constructive AST proposer.

No ARC data, no compilation, no installation, no scoring. The controls are
the ones named in the frozen protocol; thresholds are not invented here, and
recovery is reported as a measurement rather than asserted against a bar
chosen after seeing it.
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
for _p in (TTI, HERE):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from cora_arc2026 import constructive_proposer as CP              # noqa: E402
from cora_tti import constructive_vocabulary as CV                # noqa: E402
from cora_parent.tfg import ConcreteTFG, TFGEdge, TFGNode         # noqa: E402

IFACE = ("Set[Region]", "Grid")


def make_tfg(frontier_ops=(), palette_introduced=0, same_shape=True,
             fraction_changed=0.1, defined=()):
    """A minimal typed failure graph carrying only permitted evidence."""
    nodes = [TFGNode("goal", "goal", "Grid")]
    edges = []
    nodes.append(TFGNode("delta0", "delta_signature", "",
                         {"same_shape": bool(same_shape),
                          "shrinks": False, "grows": not same_shape}))
    edges.append(TFGEdge("delta0", "blocks", "goal"))
    nodes.append(TFGNode("palette0", "palette_change", "",
                         {"introduced": int(palette_introduced),
                          "removed": 0, "n_in": 3, "n_out": 3}))
    edges.append(TFGEdge("palette0", "observed_on", "delta0"))
    if same_shape:
        nodes.append(TFGNode("shape0", "shape_change", "",
                             {"cells_changed": 9,
                              "fraction_changed": float(fraction_changed)}))
        edges.append(TFGEdge("shape0", "observed_on", "delta0"))
    for index, op in enumerate(frontier_ops):
        nid = f"frontier{index}"
        nodes.append(TFGNode(nid, "frontier_term", "",
                             {"op": op, "outcome": "slot_fit_failed",
                              "surface_nodes": 4, "ast": f"[{op}]"}))
        edges.append(TFGEdge(nid, "fails", "goal"))
    for index, sig in enumerate(defined):
        nid = f"vsig{index}"
        nodes.append(TFGNode(nid, "value_signature", "", dict(sig)))
        edges.append(TFGEdge(nid, "observed_on", "goal"))
    return ConcreteTFG("Grid", "Grid", nodes, edges)


RICH = make_tfg(frontier_ops=("a", "b", "c"), palette_introduced=2,
                same_shape=True, fraction_changed=0.30,
                defined=({"defined": True, "shape_matches": True,
                          "cells_wrong": 40, "fraction_wrong": 0.4,
                          "palette_extra": 2},))
PLAIN = make_tfg(frontier_ops=("a",), palette_introduced=0,
                 same_shape=False, fraction_changed=0.02)
EMPTY = ConcreteTFG("Grid", "Grid", [TFGNode("goal", "goal", "Grid")], [])


# -- A. known reconstruction control ---------------------------------------

def test_stage_a_baselines_return_names_not_asts():
    """The recorded Stage-A behaviour: catalogue names, not constructions."""
    from cora_tti.tti_loop import mdl_fallback_proposer
    from level4_blind_runtime import runtime as V
    catalogue = dict(V.REGISTRY)
    proposed = mdl_fallback_proposer(catalogue)(RICH, 3)
    assert proposed, "baseline must still propose"
    assert all(isinstance(p, str) for p in proposed)
    assert all(p in catalogue for p in proposed)


def test_proposer_returns_asts_absent_from_the_catalogue():
    from level4_blind_runtime import runtime as V
    catalogue = set(dict(V.REGISTRY))
    out = CP.propose_ast(RICH, IFACE, k=5)
    assert out
    for cand in out:
        assert not isinstance(cand.ast, str)
        assert cand.canonical not in catalogue
        assert cand.family_text not in ("(0,)", "(1,)")


# -- B. complete-AST holdout, reported as coverage --------------------------

def test_complete_ast_holdout_recovery_is_measured():
    """Can the decoder reach complete ASTs it was never shown?

    Reported, not asserted against an invented bar. With an evidence prior
    rather than fitted weights, this measures reachability of the frozen
    grammar under the frozen beam.
    """
    targets = []
    for ast in CV.enumerate_asts(max_blocks=2):
        fam = CV.family(ast)
        if CV.is_banned_target_family(fam):
            continue
        targets.append(CV.digest(ast))
        if len(targets) >= 200:
            break
    wide = CP.propose_ast(RICH, IFACE, k=200, beam=CP.BEAM)
    reached = {c.digest for c in wide}
    covered = len(reached & set(targets))
    print(f"\ncomplete-AST holdout: {covered} of {len(targets)} enumerated "
          f"targets reached at beam {CP.BEAM}; {len(reached)} distinct emitted")
    assert wide, "the decoder must emit something"
    assert all(CV.validate(c.ast)[0] for c in wide)


# -- C. structural-family holdout ------------------------------------------

def test_holdout_families_are_flagged_and_can_be_excluded():
    kept = CP.propose_ast(RICH, IFACE, k=50)
    flagged = [c for c in kept if c.holdout_family]
    for cand in flagged:
        assert cand.family_text in ("(2,)", "(2,1)")
    dropped = CP.propose_ast(RICH, IFACE, k=50, exclude_holdout=True)
    assert all(not c.holdout_family for c in dropped)
    assert all(c.family_text not in ("(2,)", "(2,1)") for c in dropped)


def test_banned_baseline_expressible_families_are_never_emitted():
    out = CP.propose_ast(RICH, IFACE, k=100)
    assert out
    assert all(not c.banned_target_family for c in out)
    assert all(c.absent_from_k for c in out)


# -- D. irrelevant-TFG control ---------------------------------------------

def test_irrelevant_evidence_is_recorded_as_empty_and_changes_the_output():
    ev = CP.read_evidence(EMPTY)
    assert ev.empty is True
    assert ev.frontier_terms == 0
    blind = CP.propose_ast(EMPTY, IFACE, k=5)
    informed = CP.propose_ast(RICH, IFACE, k=5)
    assert blind and informed
    assert [c.digest for c in blind] != [c.digest for c in informed]


# -- E. shuffled-TFG control -----------------------------------------------

def test_proposals_depend_on_task_conditioned_evidence():
    """The failure-conditioning test: different failures, different proposals."""
    a = CP.propose_ast(RICH, IFACE, k=5)
    b = CP.propose_ast(PLAIN, IFACE, k=5)
    assert [c.digest for c in a] != [c.digest for c in b]


def test_shuffling_the_evidence_changes_the_proposal():
    """Rotate the numeric signals across field names, keeping the multiset.

    A permutation that preserves every value but reassigns which signal each
    belongs to must change the proposal, or the proposer is not reading the
    evidence.
    """
    real = CP.read_evidence(RICH)
    fields = [k for k, v in real.as_dict().items()
              if isinstance(v, (int, float)) and not isinstance(v, bool)]
    values = [getattr(real, k) for k in fields]
    rotated = values[3:] + values[:3]
    permuted = dict(zip(fields, rotated))
    shuffled = CP.Evidence(**{**real.as_dict(), **permuted})
    assert sorted(permuted.values()) == sorted(values)
    assert permuted != {k: getattr(real, k) for k in fields}
    a = CP.propose_ast(RICH, IFACE, k=5)
    b = CP.propose_ast(RICH, IFACE, k=5, evidence=shuffled)
    assert [c.digest for c in a] != [c.digest for c in b]


# -- F. type invalidity and legality ---------------------------------------

def test_every_emitted_ast_is_legal_under_the_frozen_grammar():
    for tfg in (RICH, PLAIN, EMPTY):
        for cand in CP.propose_ast(tfg, IFACE, k=25):
            ok, code = CV.validate(cand.ast)
            assert ok, code
            assert CV.tokens_are_valid(CV.tokens_from_ast(cand.ast))


def test_illegal_token_sequences_are_rejected_mechanically():
    assert not CV.tokens_are_valid([("S", "all"), ("EOS",)])
    assert not CV.tokens_are_valid([("P", "colour_components"), ("EOS",)])
    assert not CV.tokens_are_valid([("PAINT",)])
    with pytest.raises(CV.GrammarViolation):
        CV.ast_from_tokens([("M", "area"), ("EOS",)])


def test_unknown_terminals_are_rejected_by_validate():
    legal = CP.propose_ast(RICH, IFACE, k=1)[0].ast
    blocks = CV.blocks_from_ast(legal)
    bad = CV.ast_from_blocks([("not_a_partition", blocks[0][1], blocks[0][2])])
    ok, code = CV.validate(bad)
    assert not ok and code == "unknown_terminal"


# -- ordering, determinism, leakage ----------------------------------------

def test_ordering_is_deterministic_and_follows_the_frozen_rule():
    first = CP.propose_ast(RICH, IFACE, k=8)
    second = CP.propose_ast(RICH, IFACE, k=8)
    assert [c.digest for c in first] == [c.digest for c in second]
    assert [c.rank for c in first] == list(range(1, len(first) + 1))
    scores = [c.score for c in first]
    assert scores == sorted(scores, reverse=True)
    for cand in first:
        expected = cand.logp - CP.LAMBDA_MDL * cand.mdl \
            - CP.LAMBDA_COST * cand.estimated_cost_s
        assert abs(cand.score - round(expected, 6)) < 1e-6


def test_frozen_ranking_parameters_are_read_not_restated():
    manifest = CV.manifest()["ranking"]
    assert CP.BEAM == manifest["beam"]
    assert CP.LAMBDA_MDL == manifest["lambda_mdl"]
    assert CP.LAMBDA_COST == manifest["lambda_cost"]


def test_no_forbidden_information_appears_in_the_output_record():
    forbidden = ("task_id", "task", "family_label", "arc_family", "answer",
                 "test_output", "solution", "label")
    for cand in CP.propose_ast(RICH, IFACE, k=5):
        record = cand.to_dict()
        for key in record:
            assert key not in forbidden
        text = repr(record)
        assert "13e47133" not in text and "16b78196" not in text
