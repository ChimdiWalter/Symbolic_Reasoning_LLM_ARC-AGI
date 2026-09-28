"""Tests of the v1.5 delivery-addendum supplementary procedures, on synthetic
data only. They never touch the frozen v1.5 test corpus or its scores."""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

from cora_arc2026 import v15_sel as S                             # noqa: E402
import test_v15_selection_feasibility as T                        # noqa: E402


def _module(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEP = _module("dep15", "scripts/v15_supp_dependence.py")
VER = _module("ver15", "scripts/v15_supp_verification.py")


def test_donor_components_follow_the_links():
    qs = [{"group": g} for g in (0, 0, 1, 1, 2, 2, 3, 3)]
    pi = [2, 3, 0, 1, 6, 7, 4, 5]          # groups 0-1 linked, 2-3 linked
    assert DEP.donor_components(qs, pi) == [[0, 1], [2, 3]]
    pi = [2, 4, 0, 6, 1, 7, 3, 5]
    assert DEP.donor_components(qs, pi) == [[0, 1, 2, 3]]


def test_fixed_blocks_pair_groups_within_family_by_digest():
    groups = [{"group_digest": f"{i:064x}", "anchor_family": "(0,0)" if i < 5 else "(1,0)"}
              for i in range(8)]
    groups.append({"group_digest": "f" * 64, "anchor_family": "(1,1)"})
    blocks = DEP.fixed_blocks(groups)
    assert blocks == [[0, 1], [2, 3, 4], [5, 6, 7], [8]]
    assert sorted(i for b in blocks for i in b) == list(range(9))


def test_block_shuffle_keeps_donors_inside_the_block():
    q = T.synthetic_queries(12, 3)
    for x in q:
        x["family"] = "(0,0)"
    blocks = [[0, 1], [2, 3], [4, 5, 6], [7, 8], [9, 10], [11]]
    pi, skipped = DEP.block_shuffle(S, q, blocks)
    assert skipped == [[11]]
    where = {g: k for k, b in enumerate(blocks) for g in b}
    for i, x in enumerate(q):
        if x["group"] == 11:
            assert pi[i] is None
            continue
        j = pi[i]
        assert q[j]["group"] != x["group"] and where[q[j]["group"]] == where[x["group"]]
    assert sorted(j for j in pi if j is not None) == sorted(
        i for i, x in enumerate(q) if x["group"] != 11)


def test_the_resolution_rule():
    assert DEP.verdict(S, [1] * 29)["verdict"] == "UNRESOLVED"
    assert DEP.verdict(S, [1] * 30)["verdict"] == "SUPPORTED"
    assert DEP.verdict(S, [1, -1] * 20)["verdict"] == "NOT_SUPPORTED"


class _SF:
    def __init__(self, outcome):
        self.outcome = outcome

    def fit_induced_occurrences(self, other, pairs):
        if self.outcome == "raise":
            raise RuntimeError("boom")
        return (object(), {}) if self.outcome == "fit" else (None, {"failure": "no_table"})


def test_three_valued_verification_separates_errors_from_no_fit():
    assert VER.three_valued(_SF("fit"), None, []) == ("FIT", None)
    assert VER.three_valued(_SF("nofit"), None, []) == ("NO_FIT", "no_table")
    assert VER.three_valued(_SF("raise"), None, []) == ("ERROR", "RuntimeError")
    assert VER.expected_boolean("FIT") is True
    assert VER.expected_boolean("NO_FIT") is False and VER.expected_boolean("ERROR") is False


def test_the_dependence_analysis_reproduces_the_official_accuracies(monkeypatch):
    EV, tmp = T._e2e_corpus(monkeypatch, 80, "ev15supp")
    rep_path = os.path.join(tmp, "report.json")
    monkeypatch.setattr(sys, "argv", ["evaluate", rep_path])
    EV.main()
    official = json.load(open(rep_path))["conditions"]
    monkeypatch.setattr(DEP, "_evaluator", lambda: EV)
    out = os.path.join(tmp, "dep.json")
    monkeypatch.setattr(sys, "argv", ["dep", out])
    DEP.main()
    supp = json.load(open(out))
    for cond in ("D+F_ASSOC", "D+F_SHUFFLED"):
        assert supp["official_accuracy_recomputed"][cond] == official[cond]["accuracy"]
    t2 = supp["tier2_fixed_block_shuffle"]
    assert t2["blocks"] >= 30 and t2["verdict"] in ("SUPPORTED", "NOT_SUPPORTED")
    assert supp["governing_tier"] in ("tier1", "tier2")
    assert supp["mechanism_claim"].startswith("requires")
