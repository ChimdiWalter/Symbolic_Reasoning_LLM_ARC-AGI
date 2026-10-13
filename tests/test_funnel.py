"""Fast checks for cora_funnel. No induction is run.

- The blind loader strips answers and family labels.
- The probe restores every patched native name, including after an
  exception.
- The evaluator's categories follow the funnel definitions.
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


@pytest.mark.parametrize("corpus", ["dev60", "c2dev", "c3dev"])
def test_loader_is_blind(corpus):
    from cora_funnel.run import load
    try:
        items = load(corpus)
    except FileNotFoundError:
        pytest.skip(f"{corpus} corpus file absent")
    assert items
    depth = lambda x: 1 + depth(x[0]) if isinstance(x, list) and x else 0
    from cora_funnel.evaluate import answers
    ans = answers(corpus)
    for key, t in items:
        assert set(t) == {"train", "test"}
        assert all(depth(p["input"]) == 2 for p in t["test"] + t["train"]), key        # real grids, not rows
        assert len(t["test"]) == len(ans[key][0]) and all(depth(g) == 2 for g in ans[key][0]), key
        assert all(set(p) == {"input"} for p in t["test"]), key
        assert all(set(p) == {"input", "output"} for p in t["train"]), key


def test_probe_restores_names():
    import geocat_arc.object_reasoning.engine as E
    import geocat_arc.object_reasoning.generative as GEN
    import geocat_arc.object_reasoning.inducer as I
    from cora_funnel.instrument import probe
    before = (E.induce_program, I._induce_composed, I.loo_validate, I.rank_by_score, GEN.induce_generative_candidates)
    with pytest.raises(RuntimeError):
        with probe(3, [[[0]]]):
            assert I._induce_composed is not before[1]
            raise RuntimeError("boom")
    assert (E.induce_program, I._induce_composed, I.loo_validate, I.rank_by_score, GEN.induce_generative_candidates) == before


def _row(solved, preds, events, n_coh=3):
    return {"key": "k", "solved": solved, "predictions": preds, "partial_predictions": None, "events": events,
            "frames": [{"frame": 0, "hypotheses": 10}], "perception": {"n_coherent": n_coh, "coherent": []},
            "wall_s": 10.0, "cpu_s": 9.0}


def _search(outs, deadline=False, rank=None):
    return {"type": "search", "frame": 0, "n_programs": len(outs), "outputs": outs, "rank": rank, "stage": "selector",
            "fit_objects": 1.0, "fit_pixels": 1.0, "seg": "S1", "deadline_hit": deadline, "s": 1.0}


def test_categories():
    from cora_funnel.evaluate import task_record
    ans = [[[1]]]
    loo = {"type": "loo", "frame": 0, "folds": 3, "passed": 1, "failed": [0, 2], "all_passed": False}
    assert task_record(_row(True, [[[1]]], [_search([[[[1]]]])]), ans)["category"] == "CERTIFIED_CORRECT"
    assert task_record(_row(True, [[[2]]], [_search([[[[2]]]])]), ans)["category"] == "CERTIFIED_WRONG"
    r = task_record(_row(False, None, [_search([[[[2]]], [[[1]]]], rank=[1, 0]), loo]), ans)
    assert r["category"] == "REJECTED_BUT_CORRECT" and r["gate_off_correct"] is True and r["correct_candidates"] == 1
    assert task_record(_row(False, None, [_search([[[[2]]]]), loo]), ans)["category"] == "FIT_BUT_ALL_WRONG"
    assert task_record(_row(False, None, [_search([], deadline=True)]), ans)["category"] == "NO_FIT_DEADLINE"
    assert task_record(_row(False, None, [_search([], deadline=False)]), ans)["category"] == "NO_FIT_EXHAUSTED"
    err = {"type": "error", "where": "_induce_composed", "frame": 0, "n_pairs": 3, "exc": "ValueError()"}
    assert task_record(_row(False, None, [err]), ans)["category"] == "NATIVE_ERROR"
    assert task_record(_row(False, None, []), ans)["category"] == "NO_SEARCH"


@pytest.mark.parametrize("corpus", ["dev60", "c2dev", "c3dev"])
def test_answers_never_reach_solver(corpus):
    """Content-level blindness:
    - the solver receives exactly the source's training pairs and test inputs,
      and nothing else;
    - no held-out answer is ever a test input.

    An answer may coincide with a training output when the task itself repeats
    outputs, as in the dev60 task kb3dbbfa00129. That coincidence is inherent
    to the source demonstrations, which this test proves are passed unchanged."""
    import json
    from cora_funnel.evaluate import answers
    from cora_funnel.run import HERE as R, load
    ans = answers(corpus)
    pair = lambda p: [p["input"], p["output"]] if isinstance(p, dict) else [p[0], p[1]]
    if corpus == "dev60":
        raw = json.load(open(os.path.join(R, "records", "pilot_v1", "dev_bundle.json")))["tasks"]
        src = {k: ([pair(p) for p in t["train"]], [p["input"] for p in t["test"]]) for k, t in raw.items()}
    elif corpus == "c2dev":
        raw = json.load(open(os.path.join(R, "outputs", "hybrid_c2_dev", "dev_tasks.json")))
        src = {k: ([pair(p) for p in t["train"]], [t["test"][0]]) for k, t in raw.items()}
    else:
        raw = json.load(open(os.path.join(R, "outputs", "rep_growth_v0", "corpus.json")))["tasks"]
        src = {t["id"]: ([pair(p) for p in t["train"]], [a for a, _ in t["heldout"]]) for t in raw if t["split"] == "dev"}
    for key, t in load(corpus):
        assert set(t) == {"train", "test"}, key
        assert [pair(p) for p in t["train"]] == src[key][0], key                       # demonstrations unchanged, none added
        assert [p["input"] for p in t["test"]] == src[key][1], key                     # true test inputs only
        assert all(set(p) == {"input"} for p in t["test"]), key
        for a in ans[key][0]:
            assert all(a != p["input"] for p in t["test"]) or a in src[key][1], key
