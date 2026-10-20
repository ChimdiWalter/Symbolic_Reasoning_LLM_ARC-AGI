"""The pre-registered G2 forensic analysis, on synthetic rows (no dev60, no answers file)."""
import importlib.util
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("forensic", os.path.join(HERE, "scripts", "neural_cora_v2_g2_forensic.py"))
F = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F)


def test_forensic_counts_reach_and_wrong_predictions():
    ans = {"a": [[1, 2]], "b": [[3]], "c": [[0]]}
    diag = [{"task_id": "a", "result": {"verdict": "SINGLE_RULE_EXISTS",
                                        "fits": [{"program": "p_wrong", "test_pred": [[9, 9]]},
                                                 {"program": "p_right", "test_pred": [[1, 2]]}]}},
            {"task_id": "b", "result": {"verdict": "SINGLE_RULE_EXISTS", "fits": [{"program": "q", "test_pred": None}]}},
            {"task_id": "c", "result": {"verdict": "NO_SINGLE_RULE", "fits": []}}]
    solve = [{"task_id": "a", "result": {"attempts": [[[9, 9]]], "predictions": [[[9, 9]]], "n_consistent": 1}},
             {"task_id": "b", "result": {"attempts": [[[3]]], "predictions": [[[3]]], "n_consistent": 1}},
             {"task_id": "c", "result": {"attempts": [], "predictions": [], "n_consistent": 0}}]
    r = F.forensic(solve, diag, ans)
    assert r["single_rule_reach"]["n_single_rule_exists"] == 2 and r["single_rule_reach"]["n_correct_among_kept"] == 1
    assert r["single_rule_reach"]["tasks"][0]["a_correct_program"] == "p_right"
    assert r["wrong_attempts"]["tasks"] == ["a"] and r["fits_but_no_correct_candidate"]["tasks"] == ["a"]
