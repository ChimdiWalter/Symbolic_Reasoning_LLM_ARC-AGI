"""Test B scorer (PROTOCOL.md sections 6 and 7): the only Test B process that opens the answers file.

    python3 -I scorer.py REVIEW_PATH

Sequence, each step refusing on failure:
1. answer guard: every file named "*solutions*" is unreadable (training answers stay unreadable throughout);
2. release_check.check_chain with runs/GO_SCORE and the review it binds (the full transitive chain);
3. runs/SCORE_CLAIM.json, created with O_CREAT | O_EXCL, holding the GO_SCORE digest and the time, fsynced; if it
   already exists the scorer refuses, and an interrupted or failed attempt leaves it in place (fail closed);
4. only now is the pinned evaluation answers path exempted from the guard; it is read once, its sha256 checked
   against the protocol freeze, and parsed from those same bytes;
5. scoring once: runs/score/SCORE.json and SCORE_REPORT.md.

Statistics (section 7): task-level indicators need every test output of the task (ARC scoring); C1 V_neural
(cohort) vs V_shuffled (cohort) over tasks with a cohort output, C2 V_neural vs V_random and C3 A_neural vs A_cora
over all tasks; exact two-sided McNemar, Holm over the three at alpha 0.05, "underpowered" below 6 discordant
tasks; precision intervals from a cluster bootstrap over tasks (sorted task ids, 10,000 resamples,
numpy.random.default_rng(0), one integers() draw per resample shared by every statistic, percentile 2.5 and 97.5).
"""
import json
import math
import os
import sys
import time

EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, EXP)
from testb import assign as A              # noqa: E402
from testb import common as C              # noqa: E402
from testb import driver as DR             # noqa: E402
from testb import labels as LB             # noqa: E402
from testb import release_check as RC      # noqa: E402

ALPHA = 0.05
MIN_DISCORDANT = 6
BOOT = 10_000


# ---------------------------------------------------------------- statistics (pure functions)

def mcnemar_exact(b, c):
    """Exact two-sided McNemar: binomial(b + c, 1/2) tail, doubled, at most 1."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def holm(pvals):
    """Holm step-down adjusted p-values, in the input order."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj, run = [0.0] * m, 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * pvals[i]))
        adj[i] = run
    return adj


def contrast(name, pairs):
    """pairs: {task: (neural-side indicator, control-side indicator)}."""
    b = sum(1 for x, y in pairs.values() if x and not y)
    c = sum(1 for x, y in pairs.values() if y and not x)
    return {"contrast": name, "tasks": len(pairs), "neural_side": sum(x for x, _ in pairs.values()),
            "control_side": sum(y for _, y in pairs.values()), "neural_only": b, "control_only": c,
            "discordant": b + c, "p": mcnemar_exact(b, c), "underpowered": b + c < MIN_DISCORDANT}


def task_indicators(outs):
    """outs: {task: [per-output dict]} with keys v_neural, v_shuffled (None outside the cohort), v_random,
    v_no_target, a_neural, a_cora. A task counts only when every one of its test outputs counts."""
    ind = {}
    for t, rows in outs.items():
        coh = [r for r in rows if r["v_shuffled"] is not None]
        ind[t] = {"V_neural": all(r["v_neural"] for r in rows), "V_random": all(r["v_random"] for r in rows),
                  "V_no_target": all(r["v_no_target"] for r in rows),
                  "V_neural_cohort": all(r["v_neural"] for r in coh) if coh else None,
                  "V_shuffled_cohort": all(r["v_shuffled"] for r in coh) if coh else None,
                  "A_neural": all(r["a_neural"] for r in rows), "A_cora": all(r["a_cora"] for r in rows)}
    return ind


def contrasts(ind):
    c1 = contrast("C1", {t: (v["V_neural_cohort"], v["V_shuffled_cohort"]) for t, v in ind.items()
                         if v["V_neural_cohort"] is not None})
    c2 = contrast("C2", {t: (v["V_neural"], v["V_random"]) for t, v in ind.items()})
    c3 = contrast("C3", {t: (v["A_neural"], v["A_cora"]) for t, v in ind.items()})
    for c, a in zip((c1, c2, c3), holm([c1["p"], c2["p"], c3["p"]])):
        c["p_holm"] = a
        c["significant"] = a <= ALPHA
    return c1, c2, c3


def decision(status, c1, c2, c3):
    shown = (status != "INCOMPLETE" and c1["significant"] and c2["significant"]
             and c1["neural_only"] > c1["control_only"] and c2["neural_only"] > c2["control_only"])
    if c3["significant"] and c3["neural_only"] > c3["control_only"]:
        l3 = "verified guesses add exactly solved tasks beyond CORA alone"
    elif c3["significant"] and c3["control_only"] > c3["neural_only"]:
        l3 = "CORA alone solves more"
    else:
        l3 = "no difference shown"
    return {"primary": ("neural guesses become verified programs more often than control targets" if shown
                        else "not shown"),
            "primary_note": "INCOMPLETE run: no full-population decision" if status == "INCOMPLETE" else None,
            "C3": l3, "underpowered": [c["contrast"] for c in (c1, c2, c3) if c["underpowered"]]}


def bootstrap(per_task, seed=0, n=BOOT):
    """per_task: sorted list of (verified_correct, verified, attempt1_correct, outputs) per task."""
    import numpy as np
    a = np.array(per_task, dtype=float)
    rng = np.random.default_rng(seed)
    ps, qs = np.empty(n), np.empty(n)
    for i in range(n):
        s = a[rng.integers(0, len(a), len(a))].sum(axis=0)
        ps[i] = s[0] / s[1] if s[1] > 0 else np.nan
        qs[i] = s[2] / s[3]
    tot = a.sum(axis=0)
    p = tot[0] / tot[1] if tot[1] > 0 else None
    q = tot[2] / tot[3]

    def ci(x):
        x = x[~np.isnan(x)]
        return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))] if len(x) else None
    return {"precision_with_verification": p, "precision_with_verification_ci95": ci(ps),
            "precision_guesses_alone": q, "precision_guesses_alone_ci95": ci(qs),
            "difference": (p - q) if p is not None else None, "difference_ci95": ci(ps - qs),
            "resamples": n, "resamples_without_a_verified_output": int(np.isnan(ps).sum()), "seed": seed}


# ---------------------------------------------------------------- scoring

def _records(rd, core):
    out = {}
    for arm in core["plan"]:
        st, rec = DR.arm_status(rd, arm)
        res = None
        if rec is not None and rec["outcome"] in LB.FIT | {LB.NO_FIT}:
            res = C.load_json(DR.arm_paths(rd, arm["arm"])["result"])
        out[arm["arm"]] = {"status": st, "record": rec, "result": res}
    return out


def per_output_rows(core, recs, truth, set_name="primary"):
    rows = {}
    for u in core[set_name]["units"]:
        key = u["unit"]
        r = {a: recs.get(f"{key}.{a}") for a in A.ARMS}
        st = {a: (r[a]["status"] if r[a] else None) for a in A.ARMS}
        nt = r["no_target"]["result"] if r["no_target"] and r["no_target"]["result"] else None
        row = {"unit": key, "task": u["task"], "output": u["output"], "cohort": u["cohort"],
               "status": st, "finished": all(s in LB.FINISHED for a, s in st.items() if r[a] is not None),
               "v_neural": st["neural"] == "VERIFIED", "v_random": st["random"] == "VERIFIED",
               "v_shuffled": (st["shuffled"] == "VERIFIED") if u["cohort"] else None,
               "v_no_target": st["no_target"] == "REACHABLE",
               "levels": {a: r[a]["result"]["level"] for a in A.ARMS if r[a] and r[a]["result"]
                          and r[a]["result"]["fit"]},
               "no_fit_flags": {a: (r[a]["result"].get("no_fit_flags") if r[a]["result"] else
                                    (r[a]["record"] or {}).get("guard", {}).get("no_fit_flags"))
                                for a in A.ARMS if r[a]},
               "closest": {a: (r[a]["result"].get("closest") if r[a]["result"] else
                               (r[a]["record"] or {}).get("guard", {}).get("closest")) for a in A.ARMS if r[a]},
               "shape_relation": {a: r[a]["result"]["shape_relation"] for a in A.ARMS if r[a] and r[a]["result"]},
               "cpu_s": {a: r[a]["record"]["receipt"].get("cpu_s") for a in A.ARMS if r[a] and r[a]["record"]}}
        if truth is not None:
            y = truth[u["task"]][u["output"]]
            row["attempt1_correct"] = u["targets"]["neural"] == y
            row["a_neural"] = row["v_neural"] and row["attempt1_correct"]
            row["a_cora"] = row["v_no_target"] and nt is not None and nt["prediction"] == y
        rows[key] = row
    return rows


def summarize(rows, status, unfinished_tasks, decide=True):
    by_task = {}
    for r in rows.values():
        by_task.setdefault(r["task"], []).append(r)
    done = {t: v for t, v in by_task.items() if t not in unfinished_tasks}
    ind = task_indicators(done)
    c1, c2, c3 = contrasts(ind)
    out_rows = [r for t in done for r in done[t]]
    nf = [r["no_fit_flags"].get("neural") for r in out_rows if not r["v_neural"] and r["no_fit_flags"].get("neural")]
    per_task = [(sum(r["a_neural"] for r in done[t]), sum(r["v_neural"] for r in done[t]),
                 sum(r["attempt1_correct"] for r in done[t]), len(done[t])) for t in sorted(done)]
    return {"slice": "INCOMPLETE descriptive slice (finished tasks only)" if status == "INCOMPLETE" else "all tasks",
            "assigned_tasks": len(by_task), "finished_tasks": len(done), "unfinished_tasks": sorted(unfinished_tasks),
            "outputs": {"finished": len(out_rows), "verified_neural": sum(r["v_neural"] for r in out_rows),
                        "verified_shuffled_cohort": sum(bool(r["v_shuffled"]) for r in out_rows),
                        "cohort_outputs": sum(r["v_shuffled"] is not None for r in out_rows),
                        "verified_random": sum(r["v_random"] for r in out_rows),
                        "reachable_no_target": sum(r["v_no_target"] for r in out_rows),
                        "verified_neural_correct": sum(r["a_neural"] for r in out_rows),
                        "attempt1_correct": sum(r["attempt1_correct"] for r in out_rows),
                        "no_target_correct": sum(r["a_cora"] for r in out_rows)},
            "tasks": {k: sum(1 for v in ind.values() if v[k]) for k in
                      ("V_neural", "V_random", "V_no_target", "V_neural_cohort", "V_shuffled_cohort", "A_neural",
                       "A_cora")},
            "neural_no_fit_outputs": {"outputs": len(nf), **{k: sum(bool(f[k]) for f in nf) for k in (
                "complete_search", "execution_budget_stop", "cpu_limit_stop", "enumeration_capped")}},
            "contrasts": [c1, c2, c3],
            "decision": decision(status, c1, c2, c3) if decide else "none: descriptive slice, no separate decision",
            "precision": bootstrap(per_task) if per_task else None, "task_indicators": ind}


def score(cfg, review):
    fr = C.load_json(cfg.protocol_freeze)
    answers_path, answers_sha = next(iter(fr["answers_scorer_only"].items()))
    C.install_answer_guard([answers_path])
    bad = RC.check_chain(cfg, review=review, go_score=True)
    if bad:
        raise SystemExit("release check failed; the answers are not opened:\n  " + "\n  ".join(bad))
    gs_sha = C.sha_file(os.path.join(cfg.runs, "GO_SCORE"))
    claim = os.path.join(cfg.runs, "SCORE_CLAIM.json")
    try:
        C.exclusive_claim(claim, {"go_score_sha256": gs_sha, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                  "pid": os.getpid(), "note": "one use; fails closed"})
    except FileExistsError:
        raise SystemExit("runs/SCORE_CLAIM.json exists: scoring is one use and fails closed")
    C.allow_after_claim(answers_path)
    with open(answers_path, "rb") as f:
        raw = f.read()
    if C.sha_bytes(raw) != answers_sha:
        raise SystemExit("the answers file does not match its pinned sha256; the claim stays and scoring stops")
    truth = json.loads(raw.decode("utf-8"))
    rd = cfg.run_dir
    core = C.load_json(os.path.join(rd, "ASSIGNMENT.json"))["core"]
    comp = C.load_json(os.path.join(rd, "COMPLETENESS.json"))
    recs = _records(rd, core)
    status = comp["status"]
    prim = per_output_rows(core, recs, truth)
    unfinished = set(comp["stages"]["primary"]["unfinished_tasks"])
    sub_tasks = set(core["subgroup"]["tasks"])
    sub_rows = {k: r for k, r in prim.items() if f"{r['task']}:{r['output']}" in set(core["subgroup"]["outputs"])}
    dev = per_output_rows(core, recs, None, "development")
    pool = []
    for u in core["pool"]["units"]:
        r = recs.get(f"{u['unit']}.neural")
        st = r["status"] if r else "NOT_STARTED"
        pool.append({"unit": u["unit"], "status": st, "verified": st == "VERIFIED",
                     "correct": u["targets"]["neural"] == truth[u["task"]][u["output"]]})
    rep = {"schema": "TESTB_SCORE_V1", "status": status, "go_score_sha256": gs_sha,
           "outputs_freeze_sha256": C.sha_file(os.path.join(rd, "OUTPUTS_FREEZE.json")),
           "answers_sha256": answers_sha, "primary": summarize(prim, status, unfinished),
           "subgroup": dict(summarize(sub_rows, status, unfinished & sub_tasks, decide=False), label=(
               "outcome-selected descriptive slice: outputs where the CORA-only entry fails or abstains; "
               "no separate decision")),
           "development": {"note": "training tasks: reachability and search outcome only; no accuracy; no "
                                   "training answer is read", "per_output": dev},
           "pool_stage": {"note": "secondary, descriptive, neural arm only", "units": len(pool),
                          "finished": sum(p["status"] in LB.FINISHED for p in pool),
                          "verified": sum(p["verified"] for p in pool),
                          "verified_and_correct": sum(p["verified"] and p["correct"] for p in pool),
                          "contrast": "none: not part of any pre-declared contrast"},
           "denominators": comp["denominators"], "guard_stops": comp["guard_stops"], "cpu": comp["cpu"],
           "per_output": prim,
           "limits": ["public evaluation set examined before: every result is descriptive",
                      "the neural checkpoint may have seen these public puzzles during its training",
                      "verified means consistent with every demonstration within the declared bounded search, "
                      "not correct",
                      "a no-fit label describes only the declared bounded search"]}
    os.makedirs(os.path.join(cfg.runs, "score"), exist_ok=True)
    C.write_json_atomic(os.path.join(cfg.runs, "score", "SCORE.json"), rep)
    with open(os.path.join(cfg.runs, "score", "SCORE_REPORT.md"), "w", encoding="utf-8") as f:
        f.write(report_text(rep))
    return rep


def report_text(rep):
    p = rep["primary"]
    o = p["outputs"]
    lines = [f"# Test B score ({rep['status']})", "",
             f"Outputs freeze {rep['outputs_freeze_sha256']}; GO_SCORE {rep['go_score_sha256']}.", "",
             f"- Slice: {p['slice']}; {p['finished_tasks']} of {p['assigned_tasks']} tasks finished.",
             f"- Verified neural guesses: {o['verified_neural']} of {o['finished']} outputs; "
             f"{p['tasks']['V_neural']} tasks with every output verified.",
             f"- Shuffled cohort: {o['verified_shuffled_cohort']} of {o['cohort_outputs']} outputs verified; "
             f"random: {o['verified_random']}; no target reachable: {o['reachable_no_target']}.",
             f"- Exactly correct among verified guesses: {o['verified_neural_correct']}; attempt 1 alone: "
             f"{o['attempt1_correct']}; no-target answers correct: {o['no_target_correct']}."]
    for c in p["contrasts"]:
        lines.append(f"- {c['contrast']}: {c['neural_only']} against {c['control_only']} discordant tasks, "
                     f"p = {c['p']:.4g}, Holm {c['p_holm']:.4g}" + (", underpowered" if c["underpowered"] else ""))
    d = p["decision"]
    lines += [f"- Decision: {d['primary']}" + (f" ({d['primary_note']})" if d["primary_note"] else ""),
              f"- C3: {d['C3']}", "", "Limits: " + "; ".join(rep["limits"]) + "."]
    return "\n".join(lines) + "\n"


def main(argv):
    if len(argv) != 1:
        raise SystemExit(__doc__)
    rep = score(DR.Config(), argv[0])
    print(json.dumps({"status": rep["status"], "decision": rep["primary"]["decision"]}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
