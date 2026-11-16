"""SUMMARY.json of a BL1 run. Author: Chimdi Walter Ndubuisi

Every output is "development comparison on a known constructed benchmark". Reads targets/<name>.json of an output
folder, the committed setup record and, for the calibration, the evaluator's manifest of witnesses (opened here
and in the witness step of an episode, nowhere else). Nothing is searched or evaluated here.

PRIMARY (protocol section 8, one decision). On the committed eligible targets outside the development names whose
source body has at least seven census nodes, paired by target: rebuilt by the smaller-blocks system against
rebuilt by the library-only system. W: rebuilt by the smaller-blocks system only; L: by the library-only system
only; both and neither are ties. The exact two-sided sign test, p = 1 when W + L = 0. The criterion is met when
W > L, p < 0.05, the calibration is valid and passed, and the cohort is complete. Two states that are not a
reading of the criterion are kept apart, each with its own reasons:
  provisional         the cohort is not complete: a committed eligible target without a complete record (every
                      target the setup record commits as eligible counts, whatever its stratum, the development
                      names included), a target that was run without being committed as eligible, setup decisions
                      in the run that differ from the committed record, or no committed record to compare with;
  not_interpretable   the cohort is complete and the calibration is unavailable, invalid or failed.
When both apply the status is provisional and both sets of reasons are reported. A selected expression whose check
on the final panel ran out of its guard before any counterexample counts as wrong by convention; such targets are
listed and the primary is read again without them; the criterion is met only if both readings meet it.

The development names are summarised apart and never enter the primary. Every other table is secondary:
descriptive, uncorrected, and never a replacement for the primary. A fruitless search is exhaustive only when it
completed its size limit with no cap reached; every other fruitless ending is bounded; an infrastructure stop is
incomplete, never "none".
"""
import json
import math
import os
import statistics

import bl_frozen  # noqa: F401
import presets_bl as P

LABEL = P.LABEL
HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEMS = P.SYSTEM_NAMES
INFRASTRUCTURE = ("hard_stop", "memory_failure", "address_space_near_ceiling", "infrastructure_failure", "time_safety_limit")
BUDGET_ENDINGS = ("allowance_used_up", "combination_budget_used_up")      # the binding budget of either mode


def sign_test_two_sided(w, l):
    """Exact two-sided sign test: p = min(1, 2 * sum of C(w + l, k) for k = 0..min(w, l) / 2 ** (w + l)); 1 when w + l = 0."""
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def lab(d):
    return dict(label=LABEL, **d)


def _count(xs):
    out = {}
    for x in xs:
        out[str(x)] = out.get(str(x), 0) + 1
    return dict(sorted(out.items()))


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


def load_witness_manifest(folder=None):
    """The evaluator's manifest of witnesses, or None when the file does not exist."""
    path = os.path.join(folder or HERE, P.WITNESS_MANIFEST)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def rebuilt(r, system):
    """True / False when the system's selection was made and checked; None otherwise."""
    return ((r.get("selection") or {}).get(system) or {}).get("rebuilt")


def complete(r):
    """A complete record: every search ended without an infrastructure stop, both selections were made and checked."""
    return r.get("status") == "done" and all(rebuilt(r, s) in (True, False) for s in SYSTEMS)


def timed_out_only(r):
    """True when a system's selected expression counts as wrong only because its final check ran out of its guard."""
    return any(((r.get("selection") or {}).get(s) or {}).get("wrong_only_by_guard_timeout") for s in SYSTEMS)


# ---------------------------------------------------------------- the paired reading
def paired(recs, names):
    """Paired table over the complete records among `names`: smaller-blocks against library-only."""
    cells = dict(both=[], smaller_blocks_only=[], library_only_only=[], neither=[])
    for t in sorted(names):
        r = recs[t]
        sb, lo = rebuilt(r, "smaller_blocks"), rebuilt(r, "library_only")
        cells["both" if sb and lo else "smaller_blocks_only" if sb else "library_only_only" if lo else "neither"].append(t)
    w, l = len(cells["smaller_blocks_only"]), len(cells["library_only_only"])
    n = sum(len(v) for v in cells.values())
    p = sign_test_two_sided(w, l)
    return dict(N=n, W=w, L=l, W_minus_L=w - l, both=len(cells["both"]), neither=len(cells["neither"]),
                rebuilt=dict(smaller_blocks=w + len(cells["both"]), library_only=l + len(cells["both"])),
                p_two_sided_sign_test=p, W_greater_than_L=w > l, p_below_0_05=p < 0.05, targets=cells)


def committed_cohort(setup_record, stratum=None, half=None, dev=False):
    """The committed eligible targets of a stratum (presets literals), outside (or inside) the development names."""
    if setup_record is None:
        return None
    out = []
    for t, v in setup_record.get("targets", {}).items():
        if (t in P.DEV_ROSTER) != dev or (v.get("decision") or {}).get("status") != "eligible":
            continue
        if stratum is not None and P.stratum_of(t) != stratum:
            continue
        if half is not None and P.half_of(t) != half:
            continue
        out.append(t)
    return sorted(out)


def reconcile(recs, setup_record):
    """The run's setup decisions against the committed setup record: decisions and (apart) counts."""
    if setup_record is None:
        return lab(dict(available=False))
    com = setup_record.get("targets", {})
    dec, cnt, missing = [], [], []
    for t, r in sorted(recs.items()):
        c, v = com.get(t), r.get("setup_view")
        if c is None:
            missing.append(t)
            continue
        if v is None:
            dec.append(dict(target=t, note="no setup view in the run record (status %s)" % r.get("status")))
            continue
        if c.get("decision") != v.get("decision"):
            dec.append(dict(target=t, committed=c.get("decision"), run=v.get("decision")))
        if c.get("counts") != v.get("counts"):
            cnt.append(t)
    return lab(dict(available=True, n_compared=len(recs) - len(missing), targets_not_in_the_record=missing, decisions_differ=dec,
                    n_decisions_differ=len(dec), targets_whose_counts_differ=cnt, n_counts_differ=len(cnt),
                    note="decisions: eligible or excluded and its kind, stratum, control, hidden names, retained operations, hiding, the "
                         "usability guard; counts: generator draws, unusable examples, pooled sizes, usability, reason text"))


# ---------------------------------------------------------------- calibration (protocol section 9)
def calibration_set(setup_record, manifest, size_c):
    """The K controls: pinned controls that are eligible in the committed setup record and have a witness of at
    most size_c nodes in the manifest. Recomputed from those two alone; no outcome is read and no control is ever
    dropped because of one."""
    targets = (setup_record or {}).get("targets", {})
    eligible = [c for c in P.CONTROL_NAMES if (targets.get(c) or {}).get("decision", {}).get("status") == "eligible"]
    if setup_record is None or manifest is None or size_c is None:
        why = [w for w, missing in (("no committed setup record", setup_record is None), ("no witness manifest", manifest is None),
                                    ("the size limit of C is not known", size_c is None)) if missing]
        return dict(available=False, unavailable_because=why, K=None, names=None, eligible_controls=eligible)
    names, without = [], {}
    for c in eligible:
        e = manifest.get(c) or {}
        if e.get("tree") and isinstance(e.get("nodes"), int) and e["nodes"] <= size_c:
            names.append(c)
        elif e.get("tree"):
            without[c] = "the witness has more than %d nodes (%s)" % (size_c, e.get("nodes"))
        else:
            without[c] = e.get("note") or "no witness in the manifest"
    return dict(available=True, K=len(names), names=names, eligible_controls=eligible, size_c=size_c,
                eligible_controls_without_a_witness_within_s=without,
                controls_not_eligible=[c for c in P.CONTROL_NAMES if c not in eligible])


def witness_problem(r):
    """None when the record's witness was evaluated and agrees with X on all 36 fit examples and the whole final
    panel; else the reason the validation fails or is missing."""
    w = r.get("witness")
    if not w:
        return "missing validation (no witness entry in the record)"
    if w.get("state") != "evaluated":
        return "missing validation (%s%s)" % (w.get("state"), ": " + str(w.get("error")) if w.get("error") else "")
    if w.get("guard_timeout"):
        return "timeout of the guard while the witness was evaluated"
    if w.get("unsupported_results"):
        return "unsupported result of the witness"
    if not w.get("agrees_on_all_36"):
        return "the witness does not agree with X on all 36 fit examples"
    if not w.get("agrees_on_the_final_panel"):
        return "the witness does not agree with X on the complete final panel"
    return None


def calibration(recs, setup_record, manifest, size_c):
    """Unavailable / invalid / failed / passed. Valid: K is at least the minimum (presets CALIBRATION_MIN_K, with the
    note of its amendment carried into the summary), every one of the K has a complete record,
    and every one of the K witnesses agrees with X on all 36 fit examples and the complete final panel. Passed:
    valid, and C-36 is right on the final panel for at least ceil(0.9 * K) of the K."""
    cs = calibration_set(setup_record, manifest, size_c)
    out = lab(dict(cs, minimum_K=P.CALIBRATION_MIN_K, minimum_K_note=P.CALIBRATION_MIN_K_NOTE, share=P.CALIBRATION_SHARE))
    if not cs["available"]:
        out.update(state="unavailable", valid=False, passed=False, reasons=cs["unavailable_because"])
        return out
    k = cs["K"]
    reasons, right, not_right = [], [], {}
    if k < P.CALIBRATION_MIN_K:
        reasons.append("K is %d, below %d" % (k, P.CALIBRATION_MIN_K))
    for c in cs["names"]:
        r = recs.get(c)
        if r is None:
            reasons.append("%s: no record" % c)
            continue
        if not complete(r):
            reasons.append("%s: no complete record (status %s)" % (c, r.get("status")))
            continue
        problem = witness_problem(r)
        if problem:
            reasons.append("%s: %s" % (c, problem))
        state = ((r.get("searches") or {}).get("C-36") or {}).get("first_fit")
        if state == "right":
            right.append(c)
        else:
            not_right[c] = state
    threshold = math.ceil(P.CALIBRATION_SHARE * k)
    valid = not reasons
    passed = bool(valid and len(right) >= threshold)
    out.update(state="passed" if passed else ("failed" if valid else "invalid"), valid=valid, passed=passed, reasons=reasons,
               threshold_right=threshold, C36_right=len(right), C36_right_targets=right, C36_not_right=not_right,
               note="a witness that agrees shows that the answer is within C at that size; whether the search finds it is what the "
                    "threshold asks. Controls without a witness within s nodes are listed and are not failures")
    return out


# ---------------------------------------------------------------- the primary
def primary(recs, setup_record, cal, rec_check):
    """The one decision of protocol section 8, with its two states that are not a reading of the criterion.

    The paired table is on the primary's own targets: committed eligible, outside the development names, of the
    longer stratum. The cohort that must be complete is wider (protocol sections 4 and 10: the run must leave a
    complete record for every committed eligible target): every target that the setup record commits as eligible,
    whatever its stratum, the development names included. One of them without a complete record, a target that was
    run without being committed as eligible, or a setup decision that differs, makes the primary provisional; the
    targets of the table and the other ones are listed apart."""
    cohort = committed_cohort(setup_record, stratum="longer")
    every = None if setup_record is None else sorted(
        t for t, v in setup_record.get("targets", {}).items() if (v.get("decision") or {}).get("status") == "eligible")
    provisional = []
    out = lab(dict(stratum="longer: the source body has at least seven census nodes", outside_the_development_names=True))
    if cohort is None:
        provisional.append("no committed setup record: the cohort cannot be checked")
        cohort, every = [], []
        searched = sorted(t for t, r in recs.items() if t not in P.DEV_ROSTER and P.stratum_of(t) == "longer" and r.get("status") in ("done", "incomplete"))
        out["targets_run_without_a_committed_record"] = searched
    differs = sorted(d["target"] for d in rec_check.get("decisions_differ", []))
    run_outside = sorted(t for t, r in recs.items() if t not in every and r.get("status") in ("done", "incomplete"))
    missing = sorted(t for t in cohort if t not in recs)
    incomplete = sorted(t for t in cohort if t in recs and not complete(recs[t]))
    others = [t for t in every if t not in cohort]                # committed eligible, not in the table: the short stratum, development names
    missing_other = sorted(t for t in others if t not in recs)
    incomplete_other = sorted(t for t in others if t in recs and not complete(recs[t]))
    if missing:
        provisional.append("%d committed eligible targets have no record" % len(missing))
    if incomplete:
        provisional.append("%d committed eligible targets have no complete record" % len(incomplete))
    if missing_other:
        provisional.append("%d committed eligible targets that are not in the primary's table (the short stratum and the development "
                           "names) have no record" % len(missing_other))
    if incomplete_other:
        provisional.append("%d committed eligible targets that are not in the primary's table (the short stratum and the development "
                           "names) have no complete record" % len(incomplete_other))
    if run_outside:
        provisional.append("%d targets outside the committed cohort were run" % len(run_outside))
    if differs:
        provisional.append("the setup decisions of %d targets differ from the committed record" % len(differs))
    usable = [t for t in cohort if t in recs and complete(recs[t]) and t not in differs]
    main = paired(recs, usable)
    timed = sorted(t for t in usable if timed_out_only(recs[t]))
    holds = main["W_greater_than_L"] and main["p_below_0_05"]
    out.update(main)
    out.update(committed_cohort=len(cohort), committed_eligible_targets_of_every_stratum_and_the_development_names=len(every),
               committed_eligible_targets_without_a_record=missing, committed_eligible_targets_without_a_complete_record=incomplete,
               other_committed_eligible_targets_without_a_record=missing_other,
               other_committed_eligible_targets_without_a_complete_record=incomplete_other,
               targets_outside_the_committed_cohort_that_were_run=run_outside,
               targets_whose_setup_differs_from_the_committed_record=differs,
               targets_wrong_only_because_a_final_check_timed_out=timed)
    if timed:
        without = paired(recs, [t for t in usable if t not in timed])
        out["reading_without_the_timed_out_targets"] = without
        holds = holds and without["W_greater_than_L"] and without["p_below_0_05"]
    cohort_complete = not provisional
    not_interpretable = []
    if not cal["passed"]:
        detail = ""
        if cal["reasons"]:
            detail = ": " + "; ".join(cal["reasons"][:6])
        elif cal["state"] == "failed":
            detail = " (%d of %d right, %d needed)" % (cal.get("C36_right", 0), cal.get("K") or 0, cal.get("threshold_right", 0))
        not_interpretable.append("the calibration is %s%s" % (cal["state"], detail))
    parts = {"1_W_greater_than_L": main["W_greater_than_L"], "2_p_below_0_05": main["p_below_0_05"],
             "3_calibration_valid_and_passed": bool(cal["valid"] and cal["passed"]), "4_cohort_complete": cohort_complete}
    if timed:
        parts["1_and_2_also_without_the_timed_out_targets"] = bool(out["reading_without_the_timed_out_targets"]["W_greater_than_L"]
                                                                   and out["reading_without_the_timed_out_targets"]["p_below_0_05"])
    if not cohort_complete:
        status = "provisional"
    elif not_interpretable:
        status = "not_interpretable"
    else:
        status = "met" if holds else "not_met"
    out.update(criterion_parts=parts, cohort_complete=cohort_complete, provisional=not cohort_complete, provisional_reasons=provisional,
               not_interpretable=bool(not_interpretable), not_interpretable_reasons=not_interpretable,
               criterion_met=bool(status == "met"), status=status,
               wording="met: a net gain of rebuilt operations on this committed known benchmark at these blocks, examples and limits. "
                       "not_met: the prespecified superiority criterion was not met under these blocks, examples and limits; it does not "
                       "mean 'adds little', equivalence or no benefit. provisional and not_interpretable are neither.")
    return out


# ---------------------------------------------------------------- secondary tables (descriptive, uncorrected)
def state_of(r, search):
    """none / right / wrong for a search of a record, or 'incomplete' (an infrastructure stop or a check that was not made)."""
    a = (r.get("searches") or {}).get(search)
    if not a or a.get("incomplete") or a.get("first_fit") is None:
        return "incomplete"
    return a["first_fit"]


def searches_table(rs):
    out = {}
    for name in P.SEARCH_NAMES:
        rows = [(r.get("searches") or {}).get(name) for r in rs]
        rows = [a for a in rows if a]
        cpu = [a.get("cpu_s") or 0.0 for a in rows]
        entries = [a["function_valued_entries"] for a in rows if a.get("function_valued_entries") is not None]
        refused = {}
        for a in rows:
            for k, v in (a.get("refused_by_the_wrappers") or {}).items():
                refused[k] = refused.get(k, 0) + v
        out[name] = dict(
            n=len(rows), first_fit=_count(state_of(r, name) for r in rs if (r.get("searches") or {}).get(name)),
            stop_class=_count(a.get("stop_class") for a in rows),
            fruitless_exhaustive=sum(a.get("coverage") == "exhaustive" for a in rows), fruitless_bounded=sum(a.get("coverage") == "bounded" for a in rows),
            infrastructure_stops=sum(bool(a.get("incomplete")) for a in rows),
            sizes_of_found_expressions=_count(a.get("size") for a in rows if a.get("fit")),
            cpu_s_sum=round(sum(cpu), 1), cpu_s_median=round(statistics.median(cpu), 2) if cpu else None, cpu_s_largest=round(max(cpu), 2) if cpu else None,
            bank_largest=max([a.get("bank") or 0 for a in rows], default=None),
            function_valued_entries_largest=max(entries, default=None), function_cap_reached=sum(bool(a.get("function_cap_reached")) for a in rows),
            cap_reached_at=_count("%s at size %s" % (a["function_making"]["cap_reached_at"]["operation"], a["function_making"]["cap_reached_at"]["size"])
                                  for a in rows if (a.get("function_making") or {}).get("cap_reached_at")),
            refused_by_the_wrappers=refused,
            address_space_peak_kb_largest=max([a.get("address_space_peak_kb") or 0 for a in rows], default=None),
            resident_peak_kb_largest=max([a.get("resident_peak_kb") or 0 for a in rows], default=None),
            wrong_only_because_the_final_check_timed_out=sorted(
                r["target"] for r in rs if ((((r.get("searches") or {}).get(name) or {}).get("final") or {}).get("counterexample") or {}).get("note") == "guard timeout"))
    return out


def one_against_another(rs, first, second):
    """Paired table of two searches, right on the final panel, over records where both ended on their own."""
    cells = dict(both=[], first_only=[], second_only=[], neither=[], left_out=[])
    for r in sorted(rs, key=lambda r: r["target"]):
        a, b = state_of(r, first), state_of(r, second)
        if "incomplete" in (a, b):
            cells["left_out"].append(r["target"])
            continue
        cells["both" if a == b == "right" else "first_only" if a == "right" else "second_only" if b == "right" else "neither"].append(r["target"])
    return dict(first=first, second=second, counts={k: len(v) for k, v in cells.items()}, targets=cells)


def missed_for_lack_of_time(rs):
    """Where the smaller-blocks system can miss a four-node library expression for lack of time: the targets on which
    L4-36 is right on the final panel while LC4-36, which searches the same library with the blocks of C added, ended
    by its budget (the allowance or the combination budget, whichever is in force) without a right fit. Descriptive;
    it changes no selection and no count of the primary."""
    by = {r["target"]: r for r in rs}
    by_budget = sorted(t for t, r in by.items() if ((r.get("searches") or {}).get("LC4-36") or {}).get("stop_class") in BUDGET_ENDINGS)
    hit = [t for t in by_budget if state_of(by[t], "L4-36") == "right" and state_of(by[t], "LC4-36") != "right"]
    return dict(targets=hit, n=len(hit), LC4_36_ended_by_its_budget=by_budget, n_LC4_36_ended_by_its_budget=len(by_budget),
                note="L4-36 is right on the final panel and LC4-36 ended by its budget without a right fit: the smaller-blocks "
                     "system can miss a four-node library expression for lack of time. Secondary and descriptive")


def systems_table(rs):
    out = {}
    for s in SYSTEMS:
        sel = [(r["target"], (r.get("selection") or {}).get(s) or {}) for r in rs]
        same = sum((v.get("order_of_sets") or {}).get("same_order", 0) for _, v in sel)
        of = sum((v.get("order_of_sets") or {}).get("of", 0) for _, v in sel)
        out[s] = dict(
            n=len(sel), selected=sum(v.get("expr") is not None for _, v in sel), selected_by_stage=_count(v.get("stage") for _, v in sel if v.get("expr") is not None),
            undetermined=sorted(t for t, v in sel if v.get("determined") is False), rebuilt=sum(v.get("rebuilt") is True for _, v in sel),
            selected_and_wrong=sorted(t for t, v in sel if v.get("expr") is not None and v.get("rebuilt") is False),
            wrong_only_because_the_final_check_timed_out=sorted(t for t, v in sel if v.get("wrong_only_by_guard_timeout")),
            candidate_set_coverage_oracle_union_NOT_the_systems_result=sum(v.get("oracle_union") is True for _, v in sel),
            order_of_sets=dict(inputs_with_the_same_order=same, of_inputs_with_at_least_two_elements=of,
                               per_target={t: v["order_of_sets"] for t, v in sel if (v.get("order_of_sets") or {}).get("of")},
                               note="for a selected expression that is right and whose output is a frozenset; nested sets are not compared; "
                                    "it does not change 'right'"),
            cpu_s_sum=round(sum(sum(((r.get("searches") or {}).get(n) or {}).get("cpu_s") or 0.0 for n in P.SYSTEMS[s]) for r in rs), 1),
            allocated_per_target=P.system_allocation())
    return out


def panels(rs):
    rows = {r["target"]: r["final_panel"] for r in rs if r.get("final_panel")}
    g = [v["generator"] for v in rows.values()]
    p = [v["pooled"] for v in rows.values()]
    return dict(n=len(rows), generator_min=min(g) if g else None, pooled_min=min(p) if p else None, pooled_median=statistics.median(p) if p else None,
                pooled_short=sorted(t for t, v in rows.items() if v.get("pooled_short")),
                pooled_discarded_sum=sum(v.get("pooled_discarded", 0) for v in rows.values()),
                pooled_not_evaluated=sorted(t for t, v in rows.items() if v.get("pooled_not_evaluated")),
                note="a shortage is flagged and never used to exclude late")


def block(recs, names=None):
    """The secondary tables over some records (all of them, or those named)."""
    rs = [r for t, r in sorted(recs.items()) if names is None or t in names]
    searched = [r for r in rs if r.get("searches")]
    done = [r for r in rs if complete(r)]
    return lab(dict(
        n_records=len(rs), status=_count(r.get("status") for r in rs), complete=len(done),
        exclusions=dict(n=sum(r.get("status") == "excluded" for r in rs), by_kind=_count(r.get("reason_kind") for r in rs if r.get("status") == "excluded"),
                        by_target={r["target"]: r.get("reason") for r in rs if r.get("status") == "excluded"}),
        incomplete_infrastructure={r["target"]: r.get("reason") for r in rs if r.get("status") == "incomplete"},
        paired_smaller_blocks_against_library_only=paired({r["target"]: r for r in done}, [r["target"] for r in done]),
        systems=systems_table(done), searches=searches_table(searched),
        L5_36_against_L4_36=one_against_another(searched, "L5-36", "L4-36"),
        LC4_36_against_L4_36=one_against_another(searched, "LC4-36", "L4-36"),
        L4_36_right_while_LC4_36_ended_by_its_budget=missed_for_lack_of_time(searched),
        nine_example_searches={n: _count(state_of(r, n) for r in searched) for n in P.NINE},
        final_panels=panels(searched),
        cpu=dict(targets_total_s=round(sum(r.get("cpu_s_total") or 0.0 for r in rs), 1),
                 searches_s=round(sum((r.get("cpu") or {}).get("searches_s") or 0.0 for r in rs), 1),
                 final_checks_s=round(sum((r.get("cpu") or {}).get("final_checks_s") or 0.0 for r in rs), 2),
                 other_s=round(sum((r.get("cpu") or {}).get("other_s") or 0.0 for r in rs), 1),
                 note="subtotals of the targets' own records; nested subtotals are never added to the whole job"),
        memory=dict(address_space_peak_kb_largest=max([m.get("address_space_peak_kb") or 0 for r in rs for m in r.get("memory") or []], default=None),
                    resident_peak_kb_largest=max([m.get("resident_peak_kb") or 0 for r in rs for m in r.get("memory") or []], default=None))))


def denominators(recs, setup_record):
    """The original strata, the exclusions by reason and stratum, the committed eligible numbers and the terminal numbers."""
    out = dict(roster=len(P.STRATUM_SHORT) + len(P.STRATUM_LONGER), development_names=len(P.DEV_ROSTER), original_outside_development={})
    for stratum, names in (("short", P.STRATUM_SHORT), ("longer", P.STRATUM_LONGER), ("longer_7_to_15", P.STRATUM_LONGER_7_TO_15),
                           ("longer_over_15", P.STRATUM_LONGER_OVER_15)):
        outside = [t for t in names if t not in P.DEV_ROSTER]
        row = dict(original=len(outside))
        if setup_record is not None:
            dec = {t: (setup_record["targets"].get(t) or {}).get("decision") or {} for t in outside}
            row.update(committed_eligible=sum(d.get("status") == "eligible" for d in dec.values()),
                       committed_excluded_by_kind=_count(d.get("reason_kind") for d in dec.values() if d.get("status") == "excluded"),
                       not_in_the_committed_record=sorted(t for t, d in dec.items() if not d))
        row.update(records=sum(t in recs for t in outside), complete_records=sum(t in recs and complete(recs[t]) for t in outside),
                   excluded_in_the_run=sum(t in recs and recs[t].get("status") == "excluded" for t in outside),
                   incomplete_in_the_run=sorted(t for t in outside if t in recs and recs[t].get("status") == "incomplete"))
        out["original_outside_development"][stratum] = row
    return lab(out)


def summarize(outdir, setup_record=None, manifest_folder=None):
    recs = load_records(outdir)
    manifest, costs = {}, None
    mp = os.path.join(outdir, "MANIFEST.json")
    if os.path.exists(mp):
        with open(mp) as f:
            manifest = json.load(f)
    cp = os.path.join(outdir, "RUN_COSTS.json")
    if os.path.exists(cp):
        with open(cp) as f:
            costs = json.load(f)
    size_c = manifest.get("size_c", P.SIZE_C)
    witnesses = load_witness_manifest(manifest_folder)
    dev = {t: r for t, r in recs.items() if t in P.DEV_ROSTER}
    out_ = {t: r for t, r in recs.items() if t not in P.DEV_ROSTER}
    rc = reconcile(recs, setup_record)
    cal = calibration(out_, setup_record, witnesses, size_c)
    prim = primary(recs, setup_record, cal, rc)
    listed = manifest.get("targets") or sorted(recs)
    out = lab(dict(
        what="BL1 summary (CPU only, invented inputs, no model); counts are on this run's targets only; nothing here is an untouched test",
        roster=manifest.get("roster"), size_c=size_c, policy=manifest.get("policy"),
        counts=dict(listed=len(listed), records=len(recs), not_yet_run=len([t for t in listed if t not in recs]),
                    done=sum(r.get("status") == "done" for r in recs.values()), excluded=sum(r.get("status") == "excluded" for r in recs.values()),
                    incomplete=sum(r.get("status") == "incomplete" for r in recs.values()),
                    total_cpu_s_of_targets=round(sum(r.get("cpu_s_total") or 0.0 for r in recs.values()), 1), primary_status=prim["status"]),
        PRIMARY=prim, calibration=cal, denominators=denominators(recs, setup_record),
        primary_note="the one decision is PRIMARY; every other table is secondary, descriptive and uncorrected, and none can replace it"))
    secondary = dict(outside_development_all_strata=block(out_))
    for key, stratum, half in (("short_stratum", "short", None), ("longer_stratum", "longer", None), ("longer_7_to_15", "longer", "7_to_15"),
                               ("longer_over_15", "longer", "over_15")):
        names = [t for t in out_ if P.stratum_of(t) == stratum and (half is None or P.half_of(t) == half)]
        cohort = committed_cohort(setup_record, stratum=stratum, half=half)
        b = block(out_, names)
        if cohort is not None:
            usable = [t for t in cohort if t in out_ and complete(out_[t])]
            b["paired_on_the_committed_cohort"] = dict(paired(out_, usable), committed_cohort=len(cohort),
                                                       without_a_complete_record=sorted(t for t in cohort if t not in usable))
        secondary[key] = b
    out["secondary_outside_the_development_names"] = secondary
    out["development_names_development_only"] = dict(block(dev), development_witness=(dev.get(P.DEV_CONTROL) or {}).get("witness"),
                                                     note="development only: never part of the primary")
    out["costs_of_the_whole_job"] = lab(dict(
        from_this_process=costs, setup_of_the_pools_cpu_s=(costs or {}).get("pools_setup_cpu_s"),
        targets_cpu_s=round(sum(r.get("cpu_s_total") or 0.0 for r in recs.values()), 1),
        note="the outer record of /usr/bin/time is the reference for wall time and peak memory of the whole job; the setup of the pooled "
             "inputs (the generator over every library operation) is done once before the first target and is its own line; nested "
             "subtotals are never added to the whole"))
    out["reconciliation_with_the_committed_setup_record"] = rc
    return out


def write_summary(outdir, setup_record_path=None, manifest_folder=None):
    sr = None
    if setup_record_path:
        with open(setup_record_path) as f:
            sr = json.load(f)
    s = summarize(outdir, sr, manifest_folder)
    p = os.path.join(outdir, "SUMMARY.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, p)
    return s
