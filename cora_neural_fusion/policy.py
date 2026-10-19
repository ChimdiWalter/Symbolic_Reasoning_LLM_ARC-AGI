"""Fixed two-attempt policies. Each is preregistered by name before it is evaluated; none reads a test output.

- N0: NVARC's attempts, unchanged (the no-op switch).
- FILL_V1: attempt 1 stays NVARC's. Attempt 2 stays NVARC's when it is genuine (not the default [[0]]). When attempt 2 is
  the default [[0]] and CORA has a FOLD_CERTIFIED or EXPLORATORY prediction different from attempt 1, attempt 2
  becomes CORA's. The replaced default is logged: [[0]] can be a correct answer, so this is not risk-free.
- EXPLAIN_V1 (needs NVARC's candidate pool): as FILL_V1. In addition, when attempt 2 is genuine but not explained by
  any CORA hypothesis, and another pool candidate (not attempt 1) is explained, that explained candidate becomes
  attempt 2. It can lose a correct genuine attempt 2, so it is evaluated offline before any use.

Every output is returned with its provenance, so gains and losses can be attributed exactly.
"""
DEFAULT = [[0]]
POLICIES = ("N0", "FILL_V1", "EXPLAIN_V1")


def decide(policy, nvarc_attempts, analysis_output):
    """nvarc_attempts: {"attempt_1": grid, "attempt_2": grid}. analysis_output: one entry of explain_task()["outputs"]
    (or None if CORA did not run). Returns (attempts, provenance)."""
    assert policy in POLICIES
    a1, a2 = nvarc_attempts["attempt_1"], nvarc_attempts["attempt_2"]
    prov = {"attempt_1": "NVARC_BASE", "attempt_2": "NVARC_BASE" if a2 != DEFAULT else "NVARC_DEFAULT"}
    if policy == "N0" or analysis_output is None:
        return {"attempt_1": a1, "attempt_2": a2}, prov
    cora = [p for p in analysis_output["cora"] if p.grid is not None and p.grid != a1]
    if a2 == DEFAULT and cora:
        best = sorted(cora, key=lambda p: (p.verification != "FOLD_CERTIFIED",))[0]
        prov.update(attempt_2=f"CORA_BASE:{best.verification}", replaced_default=True)
        return {"attempt_1": a1, "attempt_2": best.grid}, prov
    if policy == "EXPLAIN_V1" and a2 != DEFAULT:
        cands = analysis_output["candidates"]
        a2_explained = any(c.grid == a2 and c.explained_by for c in cands)
        alt = [c for c in cands if c.explained_by and c.grid not in (a1, a2)]
        if not a2_explained and alt:
            prov.update(attempt_2="QWEN_GUIDED_CORA:explained_pool_candidate", replaced_genuine=True)
            return {"attempt_1": a1, "attempt_2": alt[0].grid}, prov
    return {"attempt_1": a1, "attempt_2": a2}, prov
