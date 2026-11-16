"""SUMMARY.json of a stage A run. Author: Chimdi Walter Ndubuisi

Reads targets/<name>.json of an output folder. Four outcomes per arm, never merged: fit, admitted (by the rule),
correct, reused. "incomplete" (infrastructure) is kept apart from "allowance used up" and "complete negative".
Development targets are flagged and left out of the primary comparison; their figures are labelled development only.
"""
import json
import math
import os
import statistics

import frozen  # noqa: F401
import presets_vf1 as V

ARMS = ("V", "S", "H", "T")
RULE_TEXT = ("THE ADMISSION RULE: the frozen first fit of an arm is admitted to the library only if the admission consumer is exact on "
             "6 generator inputs AND on 6 pooled inputs (standard adm_both at n = 6) and the preservation bank is unchanged "
             "(only bank entries that run and give a value count). Other standards and other n are measurements.")
GRID_STANDARDS = ("same_kind", "adm_generator", "adm_pooled", "adm_both")


def sign_test_two_sided(wins, losses):
    """Exact two-sided sign test on wins against losses (ties left out): p = min(1, 2 * P(Bin(n, 1/2) <= min))."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def load_records(outdir):
    d = os.path.join(outdir, "targets")
    recs = {}
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".json"):
                with open(os.path.join(d, f)) as fh:
                    r = json.load(fh)
                recs[r["target"]] = r
    return recs


def _outcomes(done, arm):
    """Capability outcomes (V, H, T): fit, admitted, correct, reused, never merged. S: fit and whether its program
    happens to contain a stand-in for the call; S is not scored on capability."""
    n = len(done)
    if arm == "S":
        c = dict(n=n, fit=0, contains_standin=0, task_acq_exact=0, incomplete=0)
        for r in done:
            a = r["arms"]["S"]
            c["fit"] += bool(a.get("fit"))
            c["contains_standin"] += bool((a.get("standin") or {}).get("contains_standin"))
            c["task_acq_exact"] += bool(a.get("task_acq_exact"))
            c["incomplete"] += a.get("stop_class") == "incomplete"
        return c
    c = dict(n=n, fit=0, admitted=0, correct=0, reused=0, task_acq_exact=0, fits_but_wrong=0, false_admissions=0,
             false_rejections=0, incomplete=0)
    for r in done:
        a = r["arms"][arm]
        c["fit"] += bool(a.get("fit"))
        c["admitted"] += bool(a.get("admitted"))
        c["correct"] += bool(a.get("correct"))
        c["reused"] += bool(a.get("reused"))
        c["task_acq_exact"] += bool(a.get("task_acq_exact"))
        c["fits_but_wrong"] += bool(a.get("fit") and not a.get("correct"))
        c["false_admissions"] += bool(a.get("admitted") and not a.get("correct"))
        c["false_rejections"] += bool(a.get("fit") and a.get("correct") and not a.get("admitted"))
        c["incomplete"] += a.get("stop_class") == "incomplete"
    return c


def _paired(done, getv, gets):
    w = l = tb = tn = 0
    wins, losses = [], []
    for r in done:
        v, s = bool(getv(r)), bool(gets(r))
        if v and not s:
            w += 1
            wins.append(r["target"])
        elif s and not v:
            l += 1
            losses.append(r["target"])
        elif v:
            tb += 1
        else:
            tn += 1
    p = sign_test_two_sided(w, l)
    va = sum(bool(getv(r)) for r in done)
    sa = sum(bool(gets(r)) for r in done)
    return dict(n_targets=len(done), first_arm_exact=va, second_arm_exact=sa, wins=w, losses=l, ties=tb + tn, ties_both=tb,
                ties_neither=tn, p_two_sided_sign_test=p, win_targets=wins, loss_targets=losses,
                decision_rule_met=bool(va > sa and w > l and p < 0.05))


def _primary(done):
    """PRIMARY: exact outputs of the acquisition task on its final panel, V against S, paired by target."""
    c = _paired(done, lambda r: r["primary"]["acquisition_task"]["V"], lambda r: r["primary"]["acquisition_task"]["S"])
    c["V_exact"], c["S_exact"] = c.pop("first_arm_exact"), c.pop("second_arm_exact")
    c["cpu_s"] = dict(
        V_physical=round(sum(r["primary"]["acquisition_task"]["V_cpu_physical_s"] for r in done), 2),
        V_counterfactual_to_first_fit=round(sum(r["primary"]["acquisition_task"]["V_cpu_counterfactual_s"] for r in done), 2),
        S_physical=round(sum(r["primary"]["acquisition_task"]["S_cpu_physical_s"] for r in done), 2),
        note="each arm has allowance B on the acquisition task; V searches the missing call only, S the whole program")
    c["targets_where_V_fails_or_S_succeeds"] = sorted(r["target"] for r in done if not r["primary"]["acquisition_task"]["V"] or r["primary"]["acquisition_task"]["S"])
    return c


def _reuse_secondary(done):
    """SECONDARY, declared: the reuse task on its final panel, the same for every arm. Retained (V's admitted operation,
    no search, no support examples) against S's fresh synthesis from the three support examples and against the
    no-retention control. The 10 B search is a conditional comparison (only where V admitted something)."""
    out = dict(n_targets=len(done))
    out["retained_V_exact"] = sum(bool(r["primary"]["reuse_task_secondary"]["retained_V"]) for r in done)
    out["S_fresh_exact"] = sum(bool(r["primary"]["reuse_task_secondary"]["S_fresh"]) for r in done)
    out["no_retention_exact"] = sum(bool(r["primary"]["reuse_task_secondary"]["no_retention"]) for r in done)
    out["V_admitted"] = sum(bool(r["primary"]["reuse_task_secondary"]["V_admitted"]) for r in done)
    out["retained_against_S_fresh_paired"] = _paired(done, lambda r: r["primary"]["reuse_task_secondary"]["retained_V"],
                                                      lambda r: r["primary"]["reuse_task_secondary"]["S_fresh"])
    cond = {r["target"]: dict(exact=bool(r["reuse_controls"]["conditional_comparison_fixed_library_10B"].get("exact_on_final")),
                              cpu_s=r["reuse_controls"]["conditional_comparison_fixed_library_10B"]["cpu_s"])
            for r in done if r["reuse_controls"].get("conditional_comparison_fixed_library_10B")}
    out["conditional_comparison_fixed_library_10B"] = dict(label="conditional comparison: run only where V admitted something",
                                                          n=len(cond), exact=sum(v["exact"] for v in cond.values()), by_target=cond)
    return out


def _admission_table(done):
    """Standard by n, on V's frozen first fit: admitted, false admissions, false rejections. The rule is adm_both at
    n = 6 together with the preservation bank (row "rule")."""
    fits = [r for r in done if r["arms"]["V"].get("fit") and r["arms"]["V"].get("admission")]
    cor = [bool(r["arms"]["V"].get("correct")) for r in fits]

    def row(adm):
        return dict(n_fits=len(fits), admitted=sum(adm), false_admissions=sum(a and not c for a, c in zip(adm, cor)),
                    false_rejections=sum((not a) and c for a, c in zip(adm, cor)), correct_fits=sum(cor))
    rows = {"none": row([True] * len(fits))}
    for st in GRID_STANDARDS:
        for n in V.GRID_NS:
            rows["%s@%d" % (st, n)] = row([bool(r["arms"]["V"]["admission"][st][str(n)]) for r in fits])
    rows["rule"] = row([bool(r["arms"]["V"]["admission"]["rule"]) for r in fits])
    return rows


def _selection(done):
    withfit = [r for r in done if r["selection"].get("n_fits")]
    out = dict(n_targets_with_a_fit=len(withfit))
    ff = [r["selection"]["first_fit"] for r in withfit]
    out["first_fit_rule"] = dict(admitted_and_correct=sum(f["admitted"] and f["correct"] for f in ff),
                                 admitted_not_correct=sum(f["admitted"] and not f["correct"] for f in ff),
                                 correct=sum(f["correct"] for f in ff))
    seeds = []
    for s in range(V.N_SEEDS):
        ch = [r["selection"]["random_seeds"][s] for r in withfit]
        seeds.append(dict(seed=s, admitted_and_correct=sum(c["admitted"] and c["correct"] for c in ch),
                          admitted_not_correct=sum(c["admitted"] and not c["correct"] for c in ch), correct=sum(c["correct"] for c in ch)))
    out["random_among_first_20_fits"] = seeds
    db = [r["selection"]["distinct_behaviours"] for r in withfit]
    out["distinct_behaviours_among_fits"] = dict(per_target={r["target"]: r["selection"]["distinct_behaviours"] for r in withfit},
                                                 targets_with_more_than_one=sum(d > 1 for d in db),
                                                 median=statistics.median(db) if db else None)
    return out


def _repair_choice(done):
    pol = {}
    keys = ["rule", "v_then_s", "s_then_v"] + ["random_%d" % s for s in range(V.N_SEEDS)]
    for k in keys:
        rows = []
        for r in done:
            rc = r["repair_choice"]
            rows.append(rc[k] if not k.startswith("random_") else rc["random"][int(k.split("_")[1])])
        reached = [x for x in rows if x["reached"]]
        pol[k] = dict(n=len(rows), reached=len(reached), cpu_s_sum_all=round(sum(x["cpu_s"] for x in rows), 2),
                      cpu_s_sum_reached=round(sum(x["cpu_s"] for x in reached), 2))
    return pol


def _reuse_costs(done):
    """Physical CPU actually spent per arm and target is in the target records; here, for targets where V admitted
    something, the parts of the retained lifetime cost, listed and never added to their own nested parts."""
    rows = {}
    for r in done:
        va = r["arms"]["V"]
        if not va.get("admitted"):
            continue
        rc = r["reuse_controls"]
        parts = rc["costs"]["retained_parts"]
        fixed = sum((parts.get(k) or 0.0) for k in ("acquisition_to_first_fit_cpu_s", "admission_cpu_s", "library_write_cpu_s", "library_load_cpu_s"))
        dep = parts.get("deployment_at_reuse_cpu_s") or 0.0
        nr = rc["no_retention"]["cost_cpu_s"]
        be = None
        if va.get("reused") and nr > dep:
            be = max(1, math.ceil(fixed / (nr - dep)))
        f10 = rc.get("conditional_comparison_fixed_library_10B")
        rows[r["target"]] = dict(
            retained_parts=parts, retained_fixed_cost_cpu_s=round(fixed, 4), retained_cost_per_reuse_cpu_s=dep,
            no_retention_per_reuse_cpu_s=nr, no_retention_exact=rc["no_retention"].get("exact_on_final"),
            fixed_library_B=dict(cpu_s=rc["fixed_library_B"]["cpu_s"], exact=rc["fixed_library_B"].get("exact_on_final")),
            conditional_comparison_10B=None if f10 is None else dict(cpu_s=f10["cpu_s"], exact=f10.get("exact_on_final")),
            reused=bool(va.get("reused")), break_even_reuses=be,
            break_even_note="fixed cost = acquisition to first fit + admission + library write + load (preservation is nested in admission and "
                            "not added again); smallest n with fixed + n x deployment <= n x no-retention cost; null when not reused or when "
                            "the no-retention cost is not above the deployment cost; a failed no-retention search counts its allowance")
    return rows


def summarize(outdir):
    recs = load_records(outdir)
    manifest = {}
    mp = os.path.join(outdir, "MANIFEST.json")
    if os.path.exists(mp):
        with open(mp) as f:
            manifest = json.load(f)
    listed = manifest.get("targets") or sorted(recs)
    done = [r for r in recs.values() if r.get("status") == "done"]
    excl = {r["target"]: r["reason"] for r in recs.values() if r.get("status") == "excluded"}
    incomplete = {r["target"]: r.get("reason") for r in recs.values() if r.get("status") == "incomplete"}
    nondev = [r for r in done if not r["dev"]]
    dev = [r for r in done if r["dev"]]
    out = dict(**{"0_the_rule": RULE_TEXT}, what="VF1 stage A summary (CPU only, invented inputs, no model). Counts are on this run's targets only.",
               label="development study: the operations study's outcomes for these operations were known before this protocol was frozen, so this is not an untouched confirmation over operations. Arm H's program text names the missing operation, so H is a budget mixture of V and S and not a clean test of localisation. A post that loses information cannot identify X, so correct is always checked directly against X and kept apart from reused.",
               development_only=bool(manifest.get("roster") == "dev"), roster=manifest.get("roster"), B=manifest.get("B"),
               n_listed=len(listed), n_done=len(done), n_excluded_by_gate=len(excl), n_incomplete_infrastructure=len(incomplete),
               n_not_yet_run=len([t for t in listed if t not in recs]))
    out["gate_exclusions"] = dict(by_target=dict(sorted(excl.items())), n=len(excl))
    out["incomplete_infrastructure"] = incomplete
    for label, grp in (("outside_development_roster", nondev), ("development_roster_development_only", dev)):
        out[label] = dict(
            n_targets=len(grp),
            arms={a: _outcomes(grp, a) for a in ARMS},
            PRIMARY_acquisition_task_V_against_S=_primary(grp),
            secondary_reuse_task_declared=_reuse_secondary(grp),
            admission_table_first_fit_of_V=_admission_table(grp),
            selection_controls=_selection(grp),
            repair_choice_controls=_repair_choice(grp),
            reuse_costs_targets_where_V_admitted=_reuse_costs(grp))
    out["primary_comparison_note"] = ("the primary comparison is PRIMARY_acquisition_task_V_against_S in the 'outside_development_roster' block; "
                                      "the development block is labelled development only and is never part of it")
    held = {}
    for r in done:
        if r["held_out_family"]:
            held[r["target"]] = dict(primary_acquisition=r["primary"]["acquisition_task"], V=dict(
                fit=bool(r["arms"]["V"].get("fit")), admitted=bool(r["arms"]["V"].get("admitted")),
                correct=bool(r["arms"]["V"].get("correct")), reused=bool(r["arms"]["V"].get("reused"))))
    out["held_out_names_apart"] = dict(names=sorted(held), outcomes=held,
                                       excluded_by_gate=sorted(t for t in excl if (recs[t].get("held_out_family"))))
    stops = {a: {} for a in ARMS}
    for r in done:
        for a in ARMS:
            k = r["arms"][a].get("stop", "?")
            stops[a][k] = stops[a].get(k, 0) + 1
    classes = {a: {} for a in ARMS}
    for r in done:
        for a in ARMS:
            k = r["arms"][a].get("stop_class", "?")
            classes[a][k] = classes[a].get(k, 0) + 1
    out["stop_reasons"] = stops
    out["stop_classes_incomplete_vs_allowance_vs_complete_negative"] = classes
    out["total_cpu_s_physical"] = round(sum(r.get("cpu_s_total", 0.0) for r in done), 1)
    out["total_cpu_s"] = out["total_cpu_s_physical"]
    out["evidence_flags"] = dict(
        final_pooled_short=sorted(r["target"] for r in done if r.get("final_panel", {}).get("pooled_short")),
        admission_pooled_short=sorted(r["target"] for r in done if r.get("admission_evidence", {}).get("pooled_short")),
        note="such targets are kept (a shortage is found only after the search, and exclusions happen only at setup)")
    out["flags_consumers"] = {r["target"]: r["consumers"]["flags"] for r in recs.values() if r.get("consumers", {}).get("flags")}
    return out


def write_summary(outdir):
    s = summarize(outdir)
    p = os.path.join(outdir, "SUMMARY.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, p)
    return s
