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
    for key, t in items:
        assert set(t) == {"train", "test"}
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
