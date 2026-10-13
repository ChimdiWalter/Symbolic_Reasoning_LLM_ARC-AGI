"""CORA-NVG leakage and determinism tests (no model, no engine search)."""
import copy
import json

import numpy as np

from cora_neural_view import corpus as K
from cora_neural_view import guides as G

CENSUS = {"coherent": ["S1", "S2", "S3", "S5", "S4", "S6"], "kept": ["S1", "S2", "S3", "S5"], "cut": ["S4", "S6"],
          "views": {v: {"coherent": True, "coherence": 0.9, "coverage": 0.85 + 0.01 * i, "relaxed": False,
                        "objects": [3 + i, 4, 2]} for i, v in enumerate(G.ORDER)}}
TRACE = {"accepted": False, "failure_stage": "loo", "train_fit_pixels": 1.0, "train_fit_objects": 1.0,
         "segmentation": "S1", "hypotheses": 9, "events": ["TASK_OBSERVED", "HYPOTHESIS_REJECTED"],
         "loo": {"folds": 3, "passed": 1, "failed_pairs": [0, 2], "divergence": []},
         "near_solve": {"variant": "S1", "fit_pixels": 1.0, "fit_objects": 1.0, "explained_rules": 3, "unexplained": 0,
                        "unexplained_deltas": [], "conflicts": {"selector_conflicts": 2, "parameter_conflicts": 1},
                        "loo_failures": [0, 2], "histogram": {"recolor": 5}, "stage": "loo"}}


def _task():
    return K.task("f_layer_frame", 7100)


def _inp(t, subset=(0, 1, 2)):
    return G.decision_input([t["train"][j] for j in subset], [a for a, _ in t["heldout"]], CENSUS, TRACE)


def test_heldout_outputs_cannot_change_guide_input():
    t = _task()
    a = _inp(t)
    m = copy.deepcopy(t)
    for pair in m["heldout"]:
        pair[1] = (np.asarray(pair[1]) * 0 + 7).tolist()
    assert G.input_sha(_inp(m)) == G.input_sha(a)
    for cond in "CDEF":
        assert G.prompt(_inp(m), cond, 0)[0] == G.prompt(a, cond, 0)[0]


def test_removed_demonstration_output_cannot_change_subset_input():
    t = _task()
    a = _inp(t, (0, 2))
    m = copy.deepcopy(t)
    m["train"][1][1] = (np.asarray(m["train"][1][1]) * 0 + 3).tolist()
    assert G.input_sha(_inp(m, (0, 2))) == G.input_sha(a)


def test_prompts_carry_no_view_name_task_id_or_family():
    t = _task()
    for cond in "CDEF":
        text, lab = G.prompt(_inp(t), cond, 0)
        for v in G.ORDER:
            assert v not in text
        assert t["id"] not in text and t["family"] not in text and "layer" not in text.lower()
        assert sorted(lab.values()) == sorted(CENSUS["cut"])


def test_labels_are_permuted_per_seed_but_deterministic():
    inp = _inp(_task())
    assert G.prompt(inp, "D", 0) == G.prompt(inp, "D", 0)
    labs = {tuple(G.prompt(inp, "D", s)[1].items()) for s in range(8)}
    assert len(labs) > 1


def test_trace_only_in_trace_conditions():
    inp = _inp(_task())
    c, d, f = (G.prompt(inp, x, 0)[0] for x in "CDF")
    assert "failure record" in d and "failure record" not in c and "failure record" not in f
    assert "Diagnosis of the failure" in f and "Diagnosis" not in c


def test_symbolic_guides_deterministic_and_options_only():
    inp = _inp(_task())
    for g in (G.guide_B1, G.guide_B2, G.guide_B3, G.guide_R):
        r1, c1 = g(inp)
        r2, c2 = g(inp)
        assert r1 == r2 and c1 == c2 and set(r1) == set(CENSUS["cut"]) and c1 in CENSUS["cut"]


def test_corpus_deterministic():
    assert json.dumps(K.task("d_cluster_fill8", 7003)) == json.dumps(K.task("d_cluster_fill8", 7003))
