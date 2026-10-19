"""Neural-CORA v1 pilot machinery: exact budget truncation, the reasoning state, the data audit, training evidence
and the evaluator's statistics."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cora_neural_v1 import audit as AU                                 # noqa: E402
from cora_neural_v1 import evaluate as EV                              # noqa: E402
from cora_neural_v1 import generator as G                              # noqa: E402
from cora_neural_v1 import search as S                                 # noqa: E402
from cora_neural_v1 import space as SP                                 # noqa: E402


def _pub(t):
    return {"task_id": t["task_id"], "train": t["train"], "test_inputs": [t["test"][0][0]]}


def test_budget_truncation_is_exact():
    for fam, seed in (("T_recolor_then_delete", 901), ("T_translate_by_colour", 902)):
        t = _pub(G.make_task(fam, seed))
        sc = SP.simplicity_scores(SP.domains(t["train"]))
        big, small = S.search_typed(t, sc, 300), S.search_typed(t, sc, 100)
        att, keep = EV._at_budget(big, 100)
        assert att == small["attempts"] and keep == small["predictions"]
        assert big["n_candidates"] == 300 and small["n_candidates"] == 100


def test_reasoning_state_and_diagnoses():
    t = _pub(G.make_task("T_recolor_by_colour", 903))
    doms = SP.domains(t["train"])
    r = S.search_typed(t, SP.heuristic_scores(doms, t["train"]), 200)
    st = r["state"]
    assert st["n_candidates"] == 200 and st["n_consistent"] == r["n_consistent"] >= 1
    assert sum(st["fail_demo"].values()) == 200 - st["n_consistent"]
    assert ("UNVERIFIED_QUERY" in st["diagnoses"]) or ("AMBIGUOUS_PREDICTIONS" in st["diagnoses"])
    # an impossible task: the outputs are unrelated random grids
    rng = np.random.default_rng(0)
    bad = {"task_id": "x", "train": [(rng.integers(0, 3, (6, 6)).tolist(), rng.integers(0, 9, (6, 6)).tolist())
                                     for _ in range(3)], "test_inputs": [rng.integers(0, 3, (6, 6)).tolist()]}
    rb = S.search_typed(bad, SP.simplicity_scores(SP.domains(bad["train"])), 100)
    assert rb["state"]["diagnoses"] == ["NO_FIT_OBSERVED"] and rb["attempts"] == []


def test_audit_validation_signatures_and_template_alias():
    t = G.make_task("T_recolor_by_colour", 904)
    assert AU._validate(t) == []
    assert "T_recolor_by_colour" in AU.template_aliases(t["train"])      # its own template explains it
    h = G.make_task("H_recolor_then_line", 3001)
    tr_sigs = {AU.signature(G.make_task(f, 0)["program"]) for f in G.TRAIN_FAMILIES if G.make_task(f, 0)}
    assert AU.signature(h["program"]) not in tr_sigs


def test_training_changes_weights_and_logs_steps():
    from cora_neural_v1 import prior as PR
    rng = np.random.default_rng(1)
    n, d = 64, 16
    X, Xv = rng.normal(size=(n, d)).astype(np.float32), rng.normal(size=(16, d)).astype(np.float32)

    def Y(m):
        from cora_neural_v1.ir import ACTIONS, SELECTORS, VARIANTS
        return {"var": (rng.random((m, len(VARIANTS))) < 0.5).astype(np.float32),
                "sel": (rng.random((m, len(SELECTORS))) < 0.1).astype(np.float32),
                "act": (rng.random((m, len(ACTIONS))) < 0.05).astype(np.float32),
                "def": (rng.random((m, 2)) < 0.5).astype(np.float32),
                "n": rng.integers(0, 2, m).astype(np.float32)}
    st = {}
    PR.train_heads(X, Y(n), Xv, Y(16), seed=3, epochs=2, batch=32, stats=st)
    assert st["optimizer_steps"] == 4 and st["trainable_params"] > 0 and st["weight_l2_moved"] > 0
    assert st["initial_weights_sha256"] != st["final_weights_sha256"]


def test_evaluator_statistics():
    assert EV.mcnemar([1, 1, 0, 0], [1, 0, 0, 0]) == (1, 0, 1.0)
    ao, bo, p = EV.mcnemar([1] * 12 + [0] * 8, [0] * 12 + [0] * 8)
    assert (ao, bo) == (12, 0) and p < 0.001
    lo, hi = EV.wilson(50, 100)
    assert lo < 0.5 < hi and EV.wilson(0, 0) == (0.0, 0.0)
