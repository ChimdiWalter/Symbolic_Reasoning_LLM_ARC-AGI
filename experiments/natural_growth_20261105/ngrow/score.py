"""The scorer (evaluator side). The only module that opens test outputs; nothing it reads flows back to a search.

A test output is CORRECT for an arm when either of the arm's two attempts reproduces it exactly (pass@2; the two
attempts are the first two fitting programs with distinct test predictions). It is ANSWERED when the arm found a
fitting program (a search that finds none abstains). Unit of the primary analysis: the task (its count of correct
test outputs); ConceptARC tasks have three test outputs, the others one.

Held halves and the ARC-AGI-2 evaluation set are refused unless the phase 2 gate passes (gate.py).
"""
import json
import os

from ngrow import env as E, data as DT, gate as GT

ARC2_DIR = os.path.join(E.REPO, "outputs", "score_first", "data")
ARC2_CHALLENGES = os.path.join(ARC2_DIR, "arc-agi_evaluation_challenges.json")
ARC2_SOLUTIONS = os.path.join(ARC2_DIR, "arc-agi_evaluation_solutions.json")
ARC2_SHA256 = {"arc-agi_evaluation_challenges.json": "e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8",
               "arc-agi_evaluation_solutions.json": "84be4f4f39b79e82c36d565fc878830988b094917f052ee7069aef30b33ca8f1"}


def solutions(bench, ids):
    """Test outputs of the given tasks; any held task requires the phase 2 gate."""
    held = {t for b, f, t in DT.half("held", (bench,))}
    if set(ids) & held:
        GT.require_phase2()
    with open(os.path.join(E.DATA, bench, "solutions_scorer_only", "solutions.json"), encoding="utf-8") as f:
        sol = json.load(f)
    return {t: [DT.grid(g) for g in sol[t]] for t in ids}


def arc2_solutions():
    GT.require_phase2()
    if E.sha_file(ARC2_SOLUTIONS) != ARC2_SHA256["arc-agi_evaluation_solutions.json"]:
        raise RuntimeError("ARC-AGI-2 evaluation solutions changed")
    with open(ARC2_SOLUTIONS, encoding="utf-8") as f:
        sol = json.load(f)
    return {t: [DT.grid(g) for g in v] for t, v in sol.items()}


def per_output(preds, outs):
    """[correct per test output] under pass@2. preds: attempts (lists of grids, one per test input) or None."""
    if not preds:
        return [False] * len(outs)
    res = []
    for j, y in enumerate(outs):
        ok = False
        for att in preds:
            if j < len(att) and DT.grid(att[j]) == y:
                ok = True
        res.append(ok)
    return res


def score_row(preds, outs):
    c = per_output(preds, outs)
    return {"n_outputs": len(outs), "correct": sum(c), "answered": len(outs) if preds else 0,
            "correct_per_output": c}
