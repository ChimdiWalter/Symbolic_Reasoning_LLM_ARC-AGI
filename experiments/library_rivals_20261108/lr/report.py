"""The scorer and the statistics of the library-rivals test (PROTOCOL.md sections 5 to 7).

Only this module opens test outputs, and only from score(), in this order: the seal verifies; every solution file's
digest equals the one study B's freeze recorded; the one-use claim SCORING_<GO digest> is written (held run: at the
study root, so no second folder can be scored under the same GO; dry run: in its own folder); each requested task's
outputs are decoded in place from the file text, so no other task's outputs are materialised (the dry run requests
source tasks only); scores, RESULTS.json, the per-task table and REPORT.md are written; then SCORED_<GO digest>.

A test output is correct when either of an arm's two attempts reproduces it exactly (pass@2, ngrow.score). An attempt
with a cell that is not an integer from 0 to 9 is a wrong answer: it is counted incorrect whatever Python's equality
says (True equals 1), and such attempts are counted per arm. The unit is the task (its count of correct outputs).
Statistics are study A's frozen functions (ngrow.analysis): exact McNemar (sign) test on the tasks where the arms
differ, family-clustered bootstrap 95% interval of the total difference (clusters: families; Mini-ARC tasks singly;
10,000 draws, random.Random(20261105)), Holm over the fixed family of five secondaries; "A beats B" needs p
(adjusted, for a secondary) below 0.05 and the interval above 0.
"""
import json
import os
import re
import time

from lr import env as E, gate as GT, arms as AR
from ngrow import data as DT, analysis as AN, score as SC

DEC = json.JSONDecoder()
NAMES = {"G0": "G0 alone", "failure_kept": "G0 + failure-kept library", "compression": "G0 + compression library",
         "random_1": "G0 + random library (seed 1)", "random_2": "G0 + random library (seed 2)"}


def decode_ids(path, ids):
    text = open(path, encoding="utf-8").read()
    out = {}
    for t in ids:
        key = json.dumps(t) + ":"
        i = text.find(key)
        if i < 0 or text.find(key, i + 1) >= 0:
            raise GT.GateRefused(f"task {t} not found exactly once in the solution file")
        j = i + len(key)
        while text[j] in " \n\t":
            j += 1
        out[t], _ = DEC.raw_decode(text, j)
    return out


def clean_attempts(preds):
    """(attempts that may score, number of attempts with a cell that is not an integer 0..9)."""
    if not preds:
        return None, 0
    keep, bad = [], 0
    for att in preds:
        ok = all(type(v) is int and 0 <= v <= 9 for gr in att for rw in gr for v in rw)
        if ok:
            keep.append(att)
        else:
            bad += 1
    return (keep or None), bad


def decide(c, p, alpha):
    a, b = c["_a"], c["_b"]
    if c[f"tasks_only_{a}"] == c[f"tasks_only_{b}"]:
        return "tie"
    lo, hi = c["family_cluster_ci95"]
    if p < alpha and lo > 0:
        return f"{a} beats {b}"
    if p < alpha and hi < 0:
        return f"{b} beats {a}"
    return "inconclusive"


def compare(rows, a, b, weight=True):
    c = AN.compare(rows, a, b)
    c["_a"], c["_b"] = a, b
    raw = c.pop("decision")
    if weight:
        c["decision_raw"] = raw
    else:
        c["rule_outcome_no_weight"] = raw
    return c


def fmt_p(p):
    return "< 0.000001" if p == 0 else str(p)


def library_usage(rows_by_arm, b):
    """For each library entry of each arm: the number of tasks whose found program uses it (descriptive)."""
    out = {}
    for a in AR.ARMS:
        if a == "G0":
            continue
        heads = [h[2:] for h, _ in AR.library_ops(a, b)]
        progs = [r.get("program") or "" for r in rows_by_arm[a].values() if r.get("fit")]
        out[a] = {h: sum(1 for p in progs if re.search(r"\b" + re.escape(h) + r"\(", p)) for h in heads}
    return out


def agreement_with_study_b(rows_fk, cfgd):
    """Descriptive: the failure-kept rows against study B's object-reuse rows on the same held tasks (predictions
    only; study B ran the same operations with a 20 CPU-s cap)."""
    out = {}
    for b, d in cfgd.get("study_b_object_reuse_rows", {}).items():
        if not os.path.exists(d["path"]) or E.sha_file(d["path"]) != d["sha256"]:
            out[b] = "not available (file missing or digest differs)"
            continue
        old = {}
        for line in open(d["path"], encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                old[r["task"]] = r
        new = rows_fk.get(b, {})
        same_fit = sum(1 for t in new if t in old and bool(new[t]["fit"]) == bool(old[t]["fit"]))
        same_pred = sum(1 for t in new if t in old and bool(new[t]["fit"]) == bool(old[t]["fit"]) and
                        json.loads(json.dumps(new[t]["preds"])) == json.loads(json.dumps(old[t].get("preds"))))
        out[b] = {"tasks": len(new), "in_study_b": sum(1 for t in new if t in old), "same_fit": same_fit,
                  "same_fit_and_predictions": same_pred}
    return out


def score(out_dir, tl, go_sha, dry):
    from lr import phase as PH
    c = PH.cfg()
    seal = E.load(os.path.join(out_dir, "PREDICTIONS_SEAL.json"))
    if seal["go_sha256"] != go_sha or any(E.sha_file(os.path.join(out_dir, r)) != h
                                          for r, h in seal["files_sha256"].items()):
        raise GT.GateRefused("the seal does not verify")
    held = {t for b in DT.BENCHMARKS for _, _, t in DT.half("held", (b,))}
    if dry and any(t in held for _, _, t in tl):
        raise GT.GateRefused("the dry run may score source tasks only")
    mdir = out_dir if dry else E.STUDY
    claim, marker = os.path.join(mdir, f"SCORING_{go_sha}"), os.path.join(mdir, f"SCORED_{go_sha}")
    if os.path.exists(claim) or os.path.exists(marker):
        raise GT.GateRefused("scoring under this GO was already claimed")
    paths = {}
    for b in DT.BENCHMARKS:                      # every digest before the claim
        rel = f"{b}/solutions_scorer_only/solutions.json"
        paths[b] = os.path.join(E.DATA, rel)
        if E.sha_file(paths[b]) != c["scorer_only_sha256_from_study_b_freeze_9d9d2248"][rel]:
            raise GT.GateRefused(f"solution file {rel} differs from the digest study B's freeze recorded")
    with E.open_write(claim) as f:
        f.write(f"claimed {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} for {out_dir}\n")
    tab, bad_cells, rows_all = [], {a: 0 for a in AR.ARMS}, {}
    usage = {}
    for b in DT.BENCHMARKS:
        ids = [(f, t) for bb, f, t in tl if bb == b]
        if not ids:
            continue
        sol = decode_ids(paths[b], [t for _, t in ids])
        rows = {a: PH.read_rows(os.path.join(out_dir, "rows", b, f"{a}.jsonl")) for a in AR.ARMS}
        rows_all[b] = rows
        try:
            usage[b] = library_usage(rows, b)
        except Exception as e:                                          # noqa: BLE001  (descriptive only)
            usage[b] = f"not computed: {type(e).__name__}: {e}"[:300]
        for f, t in ids:
            outs = [DT.grid(g) for g in sol[t]]
            r = {"bench": b, "family": f, "task": t, "cluster": f if b != "mini_arc" else t, "n_outputs": len(outs)}
            for a in AR.ARMS:
                row = rows[a][t]
                att, nbad = clean_attempts(row["preds"] if row["fit"] else None)
                bad_cells[a] += nbad
                sc = SC.score_row(att, outs)
                r[a] = sc["correct"]
                r[a + "_answered"] = len(outs) if row["fit"] and row["preds"] else 0
                r[a + "_stop"] = row["stop"]
                r[a + "_cpu_s"] = row.get("cpu_s")
            tab.append(r)
    E.dump(os.path.join(out_dir, "SCORES_PER_TASK.json"), tab)
    alpha = c["alpha"]
    res = {"status": "complete", "go_sha256": go_sha, "dry_run": dry, "tasks": len(tab),
           "outputs": sum(r["n_outputs"] for r in tab),
           "scores_per_task_sha256": E.sha_file(os.path.join(out_dir, "SCORES_PER_TASK.json")),
           "attempts_with_cells_outside_0_9": bad_cells}
    res["totals"] = {a: {"correct": sum(r[a] for r in tab), "answered": sum(r[a + "_answered"] for r in tab),
                         "cpu_safety_cap_stops": sum(1 for r in tab if r[a + "_stop"] == "cpu_cap"),
                         "arm_errors": sum(1 for r in tab if r[a + "_stop"] == "arm_error"),
                         "cpu_s_total": round(sum(r[a + "_cpu_s"] or 0 for r in tab), 1),
                         "cpu_s_max": max([r[a + "_cpu_s"] or 0 for r in tab] + [0])} for a in AR.ARMS}
    res["totals_by_benchmark"] = {b: {a: sum(r[a] for r in tab if r["bench"] == b) for a in AR.ARMS}
                                  for b in DT.BENCHMARKS}
    prim = compare(tab, "failure_kept", "compression")
    prim["decision"] = decide(prim, prim["exact_mcnemar_p"], alpha)
    res["primary"] = prim
    sec = {}
    for name, a, b, pop in c["secondaries"]:
        rs = tab if pop == "held" else [r for r in tab if r["bench"] == pop]
        sec[name] = compare(rs, a, b) if rs else {"_a": a, "_b": b, "tasks": 0, "exact_mcnemar_p": 1.0,
                                                 f"tasks_only_{a}": 0, f"tasks_only_{b}": 0, "sum_difference": 0,
                                                 "family_cluster_ci95": [0, 0]}
    adj = AN.holm({k: v["exact_mcnemar_p"] for k, v in sec.items()})
    for k, v in sec.items():
        v["holm_p"] = adj[k]
        v["decision"] = decide(v, adj[k], alpha)
    res["secondary"] = sec
    res["descriptive"] = {f"{a}_vs_{b}": compare(tab, a, b, weight=False) for a, b in c["descriptive"]}
    res["by_benchmark_primary"] = {b: compare([r for r in tab if r["bench"] == b], "failure_kept", "compression",
                                              weight=False)
                                   for b in DT.BENCHMARKS if any(r["bench"] == b for r in tab)}
    res["library_usage_tasks_per_entry"] = usage
    try:                                         # descriptive only; it can never stop the scoring
        res["agreement_failure_kept_with_study_b_object_reuse"] = agreement_with_study_b(
            {b: rows_all[b]["failure_kept"] for b in rows_all}, c)
    except Exception as e:                                              # noqa: BLE001
        res["agreement_failure_kept_with_study_b_object_reuse"] = f"not computed: {type(e).__name__}: {e}"[:300]
    worst = max(res["totals"][a]["arm_errors"] for a in AR.ARMS)
    res["label"] = "with defects" if tab and worst > 0.01 * len(tab) else "clean"
    res["label_rule"] = "with defects when any arm has search errors on more than 1% of the tasks"
    E.dump(os.path.join(out_dir, "RESULTS.json"), res)
    lines = [f"# Library rivals: results ({'DRY RUN on source tasks' if dry else 'held halves, previously used'})", "",
             f"Tasks {res['tasks']}, outputs {res['outputs']}. GO digest {go_sha}.", "",
             "| arm | correct outputs | answered | CPU safety-cap stops | errors | CPU-s total, max |",
             "|---|---|---|---|---|---|"]
    for a in AR.ARMS:
        t = res["totals"][a]
        lines.append(f"| {NAMES[a]} | {t['correct']} | {t['answered']} | {t['cpu_safety_cap_stops']} | "
                     f"{t['arm_errors']} | {t['cpu_s_total']}, {t['cpu_s_max']} |")
    lines += ["", f"**Primary (failure-kept against compression): {prim['decision']}**; correct "
              f"{prim['correct_failure_kept']} against {prim['correct_compression']}, difference {prim['sum_difference']}, "
              f"tasks only failure-kept {prim['tasks_only_failure_kept']}, only compression "
              f"{prim['tasks_only_compression']}, exact p {fmt_p(prim['exact_mcnemar_p'])}, family-clustered 95% "
              f"interval {prim['family_cluster_ci95']}.", "", "Secondaries (Holm over five; decisions at the adjusted p):",
              ""]
    for k, v in sec.items():
        lines.append(f"- {k}: {v['decision']}; difference {v['sum_difference']}, interval {v['family_cluster_ci95']}, "
                     f"raw p {fmt_p(v['exact_mcnemar_p'])}, Holm p {fmt_p(v['holm_p'])}")
    with E.open_write(os.path.join(out_dir, "REPORT.md")) as f:
        f.write("\n".join(lines) + "\n")
    with E.open_write(marker) as f:
        f.write(f"scored {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {out_dir}\n")
    print("\n".join(lines), flush=True)
    return res
