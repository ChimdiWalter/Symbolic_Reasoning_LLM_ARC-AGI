"""CORA's side of the fusion, per task: build the executable hypotheses that reproduce every demonstration; say which
neural candidate grids they predict exactly ("explained"); and give CORA's own predictions with their tier.

Reads only training pairs, test inputs and the neural candidates. It never reads a test output. An "explained"
candidate is demonstration-consistent under an executable CORA hypothesis. That is evidence about the candidate's
form, not proof that it is correct. The NVARC model was adapted on these same demonstrations, so no fold certificate
is claimed for a neural candidate.
"""
import time

from cora_neural_fusion.contract import Proposal

FAMILIES = ("grow", "select")              # the tested CORA-v2 families; "tst" joins after its integration patch


def _summary(h):
    from cora_fhr import ggrow as GG
    out = {"family": h.get("family", "grow"), "view": h.get("view"), "policy": h.get("policy")}
    if h.get("expr") is not None:
        out["expr"] = GG.pretty(h["expr"])
    if h.get("guard") is not None:
        out["guard"] = h["guard"]
    return out


def explain_task(key, train, test_inputs, candidates, families=FAMILIES, select_cpu=60.0, neural_provenance="UNKNOWN"):
    """candidates: per test output, a list of grids in the neural solver's own order (index 0 = its attempt 1).
    Returns {"outputs": [{"candidates": [Proposal], "cora": [Proposal]}], "cora_record": {...}, "cpu_s": ...}."""
    from cora_revision_v2 import diagnosis as DG
    from cora_revision_v2 import scene_reasoner as SR
    t0 = time.process_time()
    hyps, _npos = SR._hypotheses(train, families, select_cpu)
    pred_map = []                                  # per output: str(grid) -> [hypothesis summaries]
    for t in test_inputs:
        m = {}
        for h in hyps:
            p = SR.predict(h, t)
            if p is not None:
                m.setdefault(str(p), []).append(_summary(h))
        pred_map.append(m)
    rec = SR.reason(train, test_inputs, families=families, select_cpu=select_cpu)
    tier = DG.decision(rec, DG.diagnose(train, test_inputs, rec))
    cpu = round(time.process_time() - t0, 2)
    outs = []
    for i, cands in enumerate(candidates):
        cps = []
        for r, g in enumerate(cands):
            ex = pred_map[i].get(str(g), [])[:5] if i < len(pred_map) else []
            cps.append(Proposal(task=key, output_index=i, grid=g, source="NVARC_BASE", rank=r, explained_by=ex,
                                executable=bool(ex), verification="DEMO_CONSISTENT" if ex else "UNVERIFIED",
                                neural_provenance=neural_provenance))
        cora = []
        att = (tier.get("attempts") or [])
        if tier["tier"] in ("CERTIFIED", "EXPLORATORY") and i < len(att):
            for g in att[i]:
                if all(g != c for c in cands):
                    cora.append(Proposal(task=key, output_index=i, grid=g, source="CORA_BASE", executable=True,
                                         explained_by=pred_map[i].get(str(g), [])[:5],
                                         verification="FOLD_CERTIFIED" if tier["tier"] == "CERTIFIED" else "EXPLORATORY",
                                         cpu_s=cpu))
        outs.append({"candidates": cps, "cora": cora})
    return {"key": key, "outputs": outs, "cora_record": {"diagnosis": rec.get("diagnosis"), "tier": tier["tier"],
                                                         "n_hypotheses": len(hyps)}, "cpu_s": cpu}
