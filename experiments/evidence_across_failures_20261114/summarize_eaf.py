"""SUMMARY.json of an EAF1 run. Author: Chimdi Walter Ndubuisi

Every output is "development comparison on a known benchmark". Reads targets/<name>.json of an output folder. The block
for the 20 development roster names and the block outside it are kept apart; only the block outside the development
roster can carry the primary reading. "Incomplete" (infrastructure) is kept apart from complete negatives; a missing
or incomplete eligible target makes the primary reading provisional.
"""
import json
import math
import os
import statistics

import eaf_frozen  # noqa: F401
import dslx
import presets_eaf as P

LABEL = P.LABEL
ARMS = P.ARM_ORDER
OUTCOMES = ("none", "right", "wrong")


def sign_test_two_sided(favourable, unfavourable):
    """Exact two-sided sign test: p = min(1, 2 * P(Bin(n, 1/2) <= min)), ties left out."""
    n = favourable + unfavourable
    if n == 0:
        return 1.0
    k = min(favourable, unfavourable)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def lab(d):
    return dict(label=LABEL, **d)


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


def outcome(r, arm):
    """none / right / wrong, or None when the arm was incomplete (infrastructure) or the record has no such reading."""
    a = (r.get("arms") or {}).get(arm)
    if not a or a.get("stop_class") == "incomplete":
        return None
    return a.get("first_fit")


def terminal(r, arms):
    return r.get("status") == "done" and all(outcome(r, a) in OUTCOMES for a in arms)


def timed_out_wrong(r, arm):
    """True when the arm's first fit counts as wrong only because its check on the final panel ran out of its guard
    before any counterexample was found."""
    a = (r.get("arms") or {}).get(arm) or {}
    return a.get("first_fit") == "wrong" and (a.get("counterexample") or {}).get("note") == "guard timeout"


def tally(term, first, second):
    """Paired table, favourable and unfavourable targets, counts, sign test and the four conditions over `term`."""
    table = {o1: {o2: 0 for o2 in OUTCOMES} for o1 in OUTCOMES}
    fav, unf = [], []
    for t, r in sorted(term.items()):
        o1, o2 = outcome(r, first), outcome(r, second)
        table[o1][o2] += 1
        if o2 == "wrong" and o1 != "wrong":
            fav.append(t)
        if o1 == "wrong" and o2 != "wrong":
            unf.append(t)
    cnt = lambda arm, o: sum(1 for r in term.values() if outcome(r, arm) == o)
    wrong1, wrong2, right1, right2 = cnt(first, "wrong"), cnt(second, "wrong"), cnt(first, "right"), cnt(second, "right")
    p = sign_test_two_sided(len(fav), len(unf))
    cond = {"1_fewer_wrong_in_%s" % first: wrong1 < wrong2, "2_sign_test_below_0.05": p < 0.05,
            "3_right_in_%s_not_fewer_than_in_%s" % (first, second): right1 >= right2, "4_at_least_one_right_in_%s" % first: right1 >= 1}
    return dict(n_targets_terminal=len(term), paired_table_rows_first_arm_columns_second_arm=table,
                wrong_first_fits={first: wrong1, second: wrong2}, right_first_fits={first: right1, second: right2},
                favourable_targets_second_wrong_first_not=fav, unfavourable_targets_first_wrong_second_not=unf,
                n_favourable=len(fav), n_unfavourable=len(unf), p_two_sided_sign_test=p, conditions=cond,
                all_four_conditions_hold=all(cond.values()))


def comparison(done, first, second, expected=None, primary=False, mismatch=()):
    """Paired reading of arm `first` against arm `second` over the done targets (the construction cohort).
    expected: the eligible target names (from the committed setup record) or None when it cannot be checked. When it is
    given, the table is made on the committed cohort only: a done target outside it, and a target whose setup decisions
    in the run differ from the committed ones (`mismatch`), are left out, listed, and make the reading provisional.
    A first fit whose final check timed out counts as wrong; when there is one in either arm, the same reading without
    those targets is given beside it, and the criterion is met only if both readings agree."""
    recs = {r["target"]: r for r in done}
    outside, differs = [], []
    if expected is not None:
        outside = sorted(set(recs) - set(expected))
        differs = sorted(t for t in recs if t in set(mismatch) and t in set(expected))
        recs = {t: r for t, r in recs.items() if t in set(expected) and t not in differs}
    term = {t: r for t, r in recs.items() if terminal(r, (first, second))}
    main = tally(term, first, second)
    timed = sorted(t for t, r in term.items() if timed_out_wrong(r, first) or timed_out_wrong(r, second))
    holds = main["all_four_conditions_hold"]
    incomplete = sorted(t for t, r in recs.items() if t not in term)
    missing = sorted(set(expected) - set(recs) - set(differs)) if expected is not None else None
    complete = expected is not None and not incomplete and not missing and not outside and not differs
    out = lab(dict(first_arm=first, second_arm=second, **main))
    out.update(incomplete_targets=incomplete, missing_eligible_targets=missing,
               done_targets_outside_the_committed_cohort=outside, targets_whose_setup_differs_from_the_committed_record=differs,
               every_eligible_target_terminal=complete, targets_with_a_wrong_only_because_the_final_check_timed_out=timed,
               note="a reduction through wrong becoming none is reduced ambiguity, possibly by abstention; more right construction is "
                    "claimed only if the number of right first fits itself rises")
    if timed:
        without = tally({t: r for t, r in term.items() if t not in timed}, first, second)
        out["reading_without_the_timed_out_targets"] = without
        holds = holds and without["all_four_conditions_hold"]
        out["all_four_conditions_hold_in_both_readings"] = holds
    if primary:
        out["criterion_met"] = bool(holds and complete)
        out["status"] = "provisional" if not complete else ("met" if holds else "not_met")
        if expected is None:
            out["provisional_because"] = "no committed setup record, so completeness of the eligible set cannot be checked"
    return out


def arm_table(done):
    t = {}
    for a in ARMS:
        rs = [r for r in done if r.get("arms", {}).get(a)]
        c = dict(n=len(rs), none=0, right=0, wrong=0, incomplete=0)
        for r in rs:
            o = outcome(r, a)
            c["incomplete" if o is None else o] += 1
        c["task_exact_wrapper_1_2_3"] = {w: sum(bool((r["arms"][a].get("task_exact") or {}).get(w)) for r in rs) for w in ("1", "2", "3")}
        # a first fit whose check on the final panel ran out of its guard with no counterexample found: counted as wrong, listed apart
        c["wrong_only_because_the_final_check_timed_out"] = sorted(
            r["target"] for r in rs if outcome(r, a) == "wrong" and (r["arms"][a].get("counterexample") or {}).get("note") == "guard timeout")
        t[a] = c
    return t


def admissions(done):
    coh = [r for r in done if (r.get("cohorts") or {}).get("admission")]
    out = {}
    for a in ARMS:
        fits = [r for r in coh if r["arms"][a].get("fit")]
        adm = [r for r in coh if r["arms"][a].get("admitted")]
        out[a] = dict(n_admission_cohort=len(coh), n_first_fits=len(fits), admitted=len(adm),
                      wrong_admissions=sum(outcome(r, a) == "wrong" for r in adm), right_admissions=sum(outcome(r, a) == "right" for r in adm),
                      right_first_fits_not_admitted=sum(outcome(r, a) == "right" and not r["arms"][a].get("admitted") for r in coh))
    return lab(dict(by_arm=out, rule="stage A's rule unchanged: wrapper 4 exact on 6 generator and 6 pooled inputs, plus the preservation bank"))


def reuse(done):
    coh = [r for r in done if (r.get("cohorts") or {}).get("reuse")]
    out = dict(n_reuse_cohort=len(coh))
    for a in ARMS:
        out["library_%s" % a] = dict(n_with_library=sum(bool(r["arms"][a].get("library")) for r in coh),
                                     reuse_task_exact=sum(bool(r["arms"][a].get("reuse_exact")) for r in coh))
    for k in ("fresh_synthesis", "fresh_repair"):
        cs = [(r.get("reuse") or {}).get("controls", {}).get(k, {}) for r in coh]
        out[k] = dict(reuse_task_exact=sum(bool(c.get("exact_on_final")) for c in cs), fits=sum(bool(c.get("fit")) for c in cs),
                      unavailable=sum(c.get("stop_class") == "unavailable" for c in cs),
                      stop_classes=_count(c.get("stop_class", "?") for c in cs))
    out["support_unavailable_targets"] = sorted(r["target"] for r in coh if (r.get("reuse") or {}).get("support_usable", 3) < 3)
    out["note"] = "the final panel is common to every arm and control of a target; an arm without an admitted library counts as not exact"
    return lab(out)


def _count(xs):
    o = {}
    for x in xs:
        o[x] = o.get(x, 0) + 1
    return o


def costs(done):
    out = {}
    for a in ARMS:
        rs = [r["arms"][a] for r in done if r.get("arms", {}).get(a)]
        cpu = [x.get("cpu_s") or 0.0 for x in rs]
        ff = [x["cpu_to_first_fit"] for x in rs if x.get("cpu_to_first_fit") is not None]
        out[a] = dict(n=len(rs), cpu_s_sum=round(sum(cpu), 1), cpu_s_mean=round(sum(cpu) / len(cpu), 2) if cpu else None,
                      cpu_s_max=round(max(cpu), 2) if cpu else None, cpu_to_first_fit_sum=round(sum(ff), 2), n_first_fits=len(ff),
                      candidates_tested_sum=sum(x.get("candidates_tested") or 0 for x in rs),
                      bank_sum=sum(x.get("bank") or 0 for x in rs),
                      level_completed_counts=_count(x.get("level_completed") for x in rs),
                      stop_reasons=_count(x.get("stop") for x in rs), stop_classes=_count(x.get("stop_class") for x in rs),
                      function_cap_reached=sum(bool(x.get("function_cap_reached")) for x in rs))
    ctrl = {}
    for k in ("fresh_synthesis", "fresh_repair"):
        cs = [(r.get("reuse") or {}).get("controls", {}).get(k) for r in done if (r.get("cohorts") or {}).get("reuse")]
        cs = [c for c in cs if c]
        ctrl[k] = dict(n=len(cs), cpu_s_sum=round(sum(c.get("cpu_s") or 0.0 for c in cs), 1), stop_classes=_count(c.get("stop_class") for c in cs))
    return lab(dict(arms=out, reuse_controls=ctrl, total_cpu_s_of_targets=round(sum(r.get("cpu_s_total", 0.0) for r in done), 1),
                    note="equal caps do not mean equal numbers of candidates tried; wrapper evaluation is inside each allowance"))


def panels(done):
    rows = {r["target"]: r.get("final_panel") for r in done if r.get("final_panel")}
    g = [v["generator"] for v in rows.values()]
    p = [v["pooled"] for v in rows.values()]
    return lab(dict(per_target=rows, n=len(rows), generator_min=min(g) if g else None, generator_median=statistics.median(g) if g else None,
                    pooled_min=min(p) if p else None, pooled_median=statistics.median(p) if p else None,
                    pooled_short=sorted(t for t, v in rows.items() if v.get("pooled_short")),
                    note="a shortage is flagged and never used to exclude late"))


def block(recs, expected=None, primary=False, mismatch=()):
    done = [r for r in recs.values() if r.get("status") == "done"]
    excl = {r["target"]: dict(reason=r.get("reason"), kind=r.get("reason_kind")) for r in recs.values() if r.get("status") == "excluded"}
    inc = {r["target"]: r.get("reason") for r in recs.values() if r.get("status") == "incomplete"}
    coh = lambda k: sorted(r["target"] for r in done if (r.get("cohorts") or {}).get(k))
    out = lab(dict(
        n_targets_run=len(recs), cohort_sizes=dict(construction=len(done), admission=len(coh("admission")), reuse=len(coh("reuse"))),
        cohorts=dict(admission=coh("admission"), reuse=coh("reuse")),
        exclusions=dict(n=len(excl), by_target=dict(sorted(excl.items())), by_kind=_count(v["kind"] for v in excl.values())),
        incomplete_infrastructure=dict(n=len(inc), by_target=inc),
        unavailable_roles={r["target"]: r["setup"]["cohorts"]["unavailable"] for r in done if r["setup"]["cohorts"].get("unavailable")},
        PRIMARY_A3x3_against_A1x9=comparison(done, "A3x3", "A1x9", expected, primary=primary, mismatch=mismatch),
        secondary_A2x3_against_A1x6=comparison(done, "A2x3", "A1x6", None),
        five_arms_side_by_side=arm_table(done), admissions_by_arm=admissions(done), reuse=reuse(done), costs=costs(done),
        final_panels=panels(done)))
    held = dslx.held_out_names()
    hd = [r for r in done if r["target"] in held]
    out["held_out_names_apart"] = lab(dict(names=sorted(r["target"] for r in hd), A3x3_against_A1x9=comparison(hd, "A3x3", "A1x9", None),
                                           five_arms_side_by_side=arm_table(hd)))
    return out


def reconcile(recs, setup_record):
    """The run's setup decisions against the committed setup record: decisions and (apart) counts."""
    if setup_record is None:
        return lab(dict(available=False))
    com = setup_record.get("targets", {})
    dec, cnt, missing = [], [], []
    for t, r in sorted(recs.items()):
        c = com.get(t)
        v = r.get("setup_view")
        if c is None:
            missing.append(t)
            continue
        if v is None:
            dec.append(dict(target=t, note="no setup view in the run record (status %s)" % r.get("status")))
            continue
        if c["decision"] != v["decision"]:
            dec.append(dict(target=t, committed=c["decision"], run=v["decision"]))
        if c["counts"] != v["counts"]:
            cnt.append(t)
    return lab(dict(available=True, n_compared=len(recs) - len(missing), targets_not_in_the_record=missing, decisions_differ=dec,
                    n_decisions_differ=len(dec), targets_whose_counts_differ=cnt, n_counts_differ=len(cnt),
                    note="decisions: status, wrappers, cohorts, exclusion kind, acquisition source; counts: pooled sizes, usability, bank, reason text"))


def expected_outside(setup_record):
    if setup_record is None:
        return None
    return sorted(t for t, v in setup_record["targets"].items() if t not in P.DEV_ROSTER and v["decision"]["status"] == "eligible"
                  and v["decision"]["cohort_construction"])


def summarize(outdir, setup_record=None):
    recs = load_records(outdir)
    manifest = {}
    mp = os.path.join(outdir, "MANIFEST.json")
    if os.path.exists(mp):
        with open(mp) as f:
            manifest = json.load(f)
    dev = {t: r for t, r in recs.items() if t in P.DEV_ROSTER}
    out_ = {t: r for t, r in recs.items() if t not in P.DEV_ROSTER}
    out = lab(dict(what="EAF1 summary (CPU only, invented inputs, no model); counts are on this run's targets only",
                   roster=manifest.get("roster"), B=manifest.get("B"), n_listed=len(manifest.get("targets") or recs), n_run=len(recs),
                   n_not_yet_run=len([t for t in (manifest.get("targets") or []) if t not in recs]),
                   primary_comparison_note="the primary reading is PRIMARY_A3x3_against_A1x9 in the block outside the development roster; "
                                           "the development block is labelled development only and is never part of it"))
    rc = reconcile(recs, setup_record)
    mismatch = [d["target"] for d in rc.get("decisions_differ", [])]
    out["block_outside_development_roster"] = block(out_, expected_outside(setup_record), primary=True, mismatch=mismatch)
    out["block_development_roster_development_only"] = block(dev)
    out["reconciliation_with_committed_setup_record"] = rc
    return out


def write_summary(outdir, setup_record_path=None):
    sr = None
    if setup_record_path:
        with open(setup_record_path) as f:
            sr = json.load(f)
    s = summarize(outdir, sr)
    p = os.path.join(outdir, "SUMMARY.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, p)
    return s
