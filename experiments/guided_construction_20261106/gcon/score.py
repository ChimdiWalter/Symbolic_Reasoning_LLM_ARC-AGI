"""The scorer (PROTOCOL.md section 9; PROTOCOL_AMENDMENT_1.md sections 1 and 2): the only module of this study that
opens test outputs. It runs once.

    python -s -B run.py score RUN_DIR             -> RUN_DIR/RESULTS.json

Before any solution access and before the exclusive marker, in this order: the GO and every frozen digest
(gate.require_go); the row files read once as bytes; the checks of verify.py run again on exactly those bytes, which
must PASS; the receipt RUN_DIR/INVARIANTS.json must say PASS and bind to the same row digest, GO, freeze, protocol,
configuration and mode; the GO and freeze digests are taken again and must be unchanged. Any mismatch refuses
(GateRefused) with nothing taken and nothing opened. Only then the marker `runs/SCORED` (O_EXCL), and only after it
the solution files; the rows scored are the ones checked (they are not read again).

Scoring is study A's (`ngrow.score.score_row`: a test output is correct when either attempt equals it; a task's
score is its number of correct outputs; a search without a fit abstains). Statistics are study A's
(`ngrow.analysis.compare`, `holm`): exact two-sided sign test on the tasks that differ, family-clustered bootstrap 95%
interval of the total difference (ConceptARC concepts, 1D-ARC types, Mini-ARC and ARC-AGI-2 tasks as single-task
clusters; 10,000 draws within benchmark, random.Random(20261105)). Work is reported beside the counted operations
for every arm (constructor CPU, segmentations, edit applications, content comparisons), and the learned arms' feature
work separately.
"""
import json
import os

from gcon import env as E, gate as GT, verify as VF
from ngrow import score as SA, analysis as AN, data as DT

HELD = ("1d_arc", "concept_arc", "mini_arc")
BIND = ("verdict", "rows_sha256", "identity_sha256", "kernel_receipts_sha256", "go_sha256", "freeze_sha256",
        "protocol_sha256", "config_sha256", "mode")


def after_marker():
    """Solution files open only after the GO and the scoring marker (defence in depth for direct calls)."""
    GT.require_go()
    if not os.path.exists(GT.MARKER):
        raise GT.GateRefused("solutions open only after the scoring marker")


def held_solutions(bench, ids):
    """After the marker: the benchmark's scorer-only solution file, parsed whole (study A's prepared data)."""
    after_marker()
    path = os.path.join(E.DATA, bench, "solutions_scorer_only", "solutions.json")
    with open(path, encoding="utf-8") as f:
        sol = json.load(f)
    return {t: [DT.grid(g) for g in sol[t]] for t in ids}


def arc2_solutions():
    """After the marker: the ARC-AGI-2 evaluation solutions (pinned digest)."""
    after_marker()
    if E.sha_file(SA.ARC2_SOLUTIONS) != SA.ARC2_SHA256["arc-agi_evaluation_solutions.json"]:
        raise RuntimeError("ARC-AGI-2 evaluation solutions changed")
    with open(SA.ARC2_SOLUTIONS, encoding="utf-8") as f:
        sol = json.load(f)
    return {t: [DT.grid(g) for g in v] for t, v in sol.items()}


def arm_preds(r, key):
    """The attempts of one arm on one task (shared stages take the reference's answer; abstention is None)."""
    if "ref_error" in r:
        return None
    if r.get("shared"):
        ref = r["ref"]
        return ref["preds"] if ref["fit"] else None
    a = r["arms"][key]
    return a["preds"] if a["fit"] else None


def table(rows, sols, keys, bench_of):
    out = []
    for r in rows:
        outs = sols[r["task"]]
        d = {"task": r["task"], "bench": bench_of(r), "family": r["family"],
             "cluster": r["task"] if r["bench"] in ("mini_arc", "arc2") else r["family"],
             "cpu": task_cpu(r, keys)}
        for k in keys:
            d[k] = SA.score_row(arm_preds(r, k), outs)["correct"]
        d["_preds"] = {k: arm_preds(r, k) for k in keys}
        out.append(d)
    return out


def guard(run_dir):
    """Everything that must hold before the marker and before any solution access; returns (fresh record, rows)."""
    fresh, rows = VF.run_checks(run_dir)
    if fresh["verdict"] != "PASS":
        raise GT.GateRefused(f"the checks fail on the current rows ({fresh['n_failures']} failures); nothing is scored")
    path = os.path.join(run_dir, VF.RECEIPT)
    if not os.path.exists(path):
        raise GT.GateRefused("no invariant receipt (INVARIANTS.json); run verify first")
    with open(path, encoding="utf-8") as f:
        receipt = json.load(f)
    bad = [k for k in BIND if receipt.get(k) != fresh[k]]
    if bad:
        raise GT.GateRefused("the invariant receipt does not bind to the current rows, GO and freeze: " +
                             ", ".join(bad))
    again = VF.context()
    if any(again[k] != fresh[k] for k in ("go_sha256", "freeze_sha256", "protocol_sha256", "config_sha256")):
        raise GT.GateRefused("the GO, freeze, protocol or configuration changed during the checks")
    return fresh, rows


def work(rows, keys):
    """Per arm: constructor CPU, counted operations, segmentations, edit applications and content comparisons (sums
    over the construction tasks' holes); and the feature work that the learned arms use (once per task)."""
    out = {}
    for k in keys:
        acc = {"constructor_cpu_s": 0.0, "operations": 0, "segmentations": 0, "edit_applications": 0,
               "content_comparisons": 0, "arm_cpu_s_incl_new_retries": 0.0}
        for r in rows:
            a = (r.get("arms") or {}).get(k)
            if not a or "holes" not in a:
                continue
            acc["arm_cpu_s_incl_new_retries"] += a.get("cpu_s", 0.0)
            for h in a["holes"]:
                acc["constructor_cpu_s"] += h["cpu_s"]
                acc["operations"] += h["ops"]
                acc["segmentations"] += h["segment"]
                acc["edit_applications"] += h["edit"]
                acc["content_comparisons"] += h.get("compare", 0)
        out[k] = {x: (round(v, 3) if isinstance(v, float) else v) for x, v in acc.items()}
    feat = {"feature_cpu_s": round(sum(r.get("features_cpu_s", 0.0) for r in rows), 3),
            "feature_content_comparisons": sum(r.get("feature_comparisons", 0) for r in rows),
            "pair_analysis_cpu_s": round(sum(r.get("pair_analysis_cpu_s", 0.0) for r in rows), 3),
            "sketches_cpu_s": round(sum(r.get("sketches_cpu_s", 0.0) for r in rows), 3),
            "holes_setup_cpu_s": round(sum(r.get("holes_setup_cpu_s", 0.0) for r in rows), 3),
            "donor_feature_cpu_s": round(sum(r.get("donor_features_cpu_s", 0.0) for r in rows), 3),
            "donor_feature_comparisons": sum(r.get("donor_feature_comparisons", 0) for r in rows),
            "retry_cpu_s": round(sum(r.get("retry_cpu_s", 0.0) for r in rows), 3),
            "reference_cpu_s": round(sum((r.get("ref") or {}).get("cpu_s") or 0.0 for r in rows), 3),
            "task_total_cpu_s": round(sum(r.get("cpu_s", 0.0) for r in rows), 3)}
    feat["scope"] = {
        "donor_feature_cpu_s": "cache delta: a donor's hole setup (sketches, pair analysis, features) is recorded on "
                               "the task that first computes it, so the sum is the total new donor work",
        "donor_feature_comparisons": "cache delta: the donor's crop-precondition content comparisons, recorded on "
                                     "the task that first computes the donor's holes, so the sum is the total"}
    return out, feat


def task_cpu(r, keys):
    """One task's CPU: its total, the shared hole setup (sketches, pair analysis, features), the reference call, and
    each arm's search CPU (constructor plus the retries it computed first)."""
    return {"task_total_cpu_s": r.get("cpu_s"), "holes_setup_cpu_s": r.get("holes_setup_cpu_s"),
            "features_cpu_s": r.get("features_cpu_s"), "reference_cpu_s": (r.get("ref") or {}).get("cpu_s"),
            "arms_search_cpu_s": {k: ((r.get("arms") or {}).get(k) or {}).get("cpu_s") for k in keys}}


def score(run_dir):
    GT.require_go()
    c = E.load(VF.CONFIG)
    B = c["test_budget"]
    fresh, rows_by_set = guard(run_dir)
    fd = GT.take_marker()
    os.write(fd, json.dumps({"run_dir": run_dir, **{k: fresh[k] for k in BIND},
                             "row_files": fresh["row_files"]}, sort_keys=True).encode())
    os.close(fd)
    held_keys = [f"{a}@{b}" for a, b in c["arms_held"]]
    arc2_keys = [f"{a}@{b}" for a, b in c["arms_arc2"]]
    held_rows = []
    sols = {}
    for b in HELD:
        rows = rows_by_set[b]
        held_rows += rows
        sols.update(held_solutions(b, [r["task"] for r in rows]))
    H = table(held_rows, sols, held_keys, lambda r: r["bench"])
    arc2_rows = rows_by_set["arc2"]
    A2 = table(arc2_rows, arc2_solutions(), arc2_keys, lambda r: "arc2")
    g, h = f"guide@{B}", f"hand@{B}"
    res = {"test_budget": B, "n_held": len(H), "n_arc2": len(A2), "receipt": {k: fresh[k] for k in BIND}}
    res["primary"] = AN.compare(H, g, h)
    pairs = [("1_guide_vs_donor", H, g, f"donor@{B}"),
             ("2_guide_vs_frequency", H, g, f"frequency@{B}"),
             ("3_guide_vs_hand_rule", H, g, f"hand_rule@{B}"),
             ("4_guide_vs_linear", H, g, f"linear@{B}"),
             ("5_guide_vs_hand_at_20000", H, "guide@20000", "hand@20000"),
             ("6_arc2_guide_vs_hand_at_20000", A2, "guide@20000", "hand@20000"),
             ("7_lobo_vs_hand", H, f"lobo@{B}", h)]
    sec = {name: dict(AN.compare(rows, a, b), first=a, second=b) for name, rows, a, b in pairs}
    adj = AN.holm({k: v["exact_mcnemar_p"] for k, v in sec.items()})
    for k, v in sec.items():
        v["holm_p"] = adj[k]
        na, nb = v["tasks_only_" + v["first"]], v["tasks_only_" + v["second"]]
        lo, hi = v["family_cluster_ci95"]
        if na == nb:
            v["holm_decision"] = "tie"
        elif adj[k] < 0.05 and lo > 0:
            v["holm_decision"] = f"{v['first']} beats {v['second']}"
        elif adj[k] < 0.05 and hi < 0:
            v["holm_decision"] = f"{v['second']} beats {v['first']}"
        else:
            v["holm_decision"] = "inconclusive"
    res["secondaries"] = sec
    res["neural_wording"] = "network" if sec["4_guide_vs_linear"]["holm_decision"] == f"{g} beats linear@{B}" \
        else "learned guidance"
    # descriptive
    desc = {}
    for k in held_keys:
        desc[k] = {"correct_outputs": sum(d[k] for d in H), "correct_tasks": sum(1 for d in H if d[k] > 0),
                   "by_bench": {b: {"outputs": sum(d[k] for d in H if d["bench"] == b),
                                    "tasks": sum(1 for d in H if d["bench"] == b and d[k] > 0)} for b in HELD}}
    for k in arc2_keys:
        desc["arc2/" + k] = {"correct_outputs": sum(d[k] for d in A2), "correct_tasks": sum(1 for d in A2 if d[k] > 0)}
    res["descriptive"] = desc
    w_held, f_held = work(held_rows, held_keys)
    w_arc2, f_arc2 = work(arc2_rows, arc2_keys)
    res["work"] = {"held": {"arms": w_held, "shared_and_feature_work": f_held},
                   "arc2": {"arms": w_arc2, "shared_and_feature_work": f_arc2},
                   "note": "operations are the step's capped counter (an application is allowed while the counter "
                           "is at most the budget, so a capped hole reaches budget + 1; the symmetry forms and the "
                           "agreement keys on the test inputs add uncapped applications). Constructor CPU, "
                           "segmentations, edit applications and content comparisons are not capped. The shared "
                           "hole setup (sketches, pair analysis, features) runs once per task before any arm; the "
                           "learned arms (guide, linear model, leave-one-benchmark-out guide; donor guidance on the "
                           "donor's features) use the features, which the hand-set order and the hand rule do not. "
                           "The counted-operation budget alone is never a statement about total CPU."}
    # predictions
    p1 = {}
    for bud in (B, 20000):
        same = all(json.dumps(d["_preds"][f"guide@{bud}"], default=list) ==
                   json.dumps(d["_preds"][f"hand@{bud}"], default=list) for d in A2)
        ng = sum(1 for d in A2 if d[f"guide@{bud}"] > 0)
        nh = sum(1 for d in A2 if d[f"hand@{bud}"] > 0)
        p1[str(bud)] = {"identical_attempts": same, "guide_correct_tasks": ng, "hand_correct_tasks": nh,
                        "holds": same and 0 <= ng <= 3 and 0 <= nh <= 3}
    diff_b = {b: sum(1 for d in H if d["bench"] == b and d[g] != d[h]) for b in HELD}
    diff_attempts_full = sum(1 for d in H if json.dumps(d["_preds"]["guide@20000"], default=list) !=
                             json.dumps(d["_preds"]["hand@20000"], default=list))
    res["predictions"] = {
        "guided-1": dict(p1, holds=all(v["holds"] for v in p1.values())),
        "guided-2": {"tasks_differing_by_bench": diff_b,
                     "holds": diff_b["concept_arc"] <= 3 and diff_b["mini_arc"] <= 3},
        "guided-3": {"held_tasks_with_different_attempts_at_20000": diff_attempts_full,
                     "holds": diff_attempts_full <= 4}}
    res["per_task"] = [{k: v for k, v in d.items() if k != "_preds"} for d in H + A2]
    E.dump(os.path.join(run_dir, "RESULTS.json"), res, indent=1)
    print(json.dumps({"primary": res["primary"], "predictions": {k: v["holds"] for k, v in res["predictions"].items()}}))
    return res


def main(run_dir):
    return score(os.path.abspath(run_dir))
