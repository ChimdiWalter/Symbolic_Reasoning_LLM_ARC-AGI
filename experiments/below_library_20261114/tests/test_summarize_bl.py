"""Tests of the summary (summarize_bl.py) on hand-made records. Nothing is searched. Author: Chimdi Walter Ndubuisi
Run: env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B -m pytest -q -p no:cacheprovider experiments/below_library_20261114/tests
"""
import json
import math
import os

import pytest

import presets_bl as P
import summarize_bl as SM

LONGER = [t for t in P.STRATUM_LONGER if t not in P.DEV_ROSTER]          # the 90 names of the primary's stratum
SHORT = [t for t in P.STRATUM_SHORT if t not in P.DEV_ROSTER]            # 35 names
CONTROLS = list(P.CONTROL_NAMES)                                         # 28 names, all of the short stratum
WITNESS = dict(state="evaluated", valid=True, agrees_on_all_36=True, agrees_on_the_final_panel=True, unsupported_results=0, guard_timeout=False)
VIEW = dict(decision=dict(status="eligible", reason_kind=None), counts=dict(usable=40))


def search(first_fit, cls=None, coverage=None):
    fit = first_fit in ("right", "wrong")
    cls = cls or ("found" if fit else "size_limit_completed")
    return dict(fit=fit, first_fit=first_fit, stop_class=cls, incomplete=cls in SM.INFRASTRUCTURE, expr="e(x0)" if fit else None, size=3 if fit else None,
                coverage=coverage if coverage is not None else (None if fit else "exhaustive"), cpu_s=2.0, bank=10, function_cap_reached=False,
                function_valued_entries=130, function_making=dict(cap_reached_at=None), refused_by_the_wrappers=dict(function_results_refused=0),
                address_space_peak_kb=50000, resident_peak_kb=40000,
                final=dict(right=first_fit == "right", counterexample=None if first_fit != "wrong" else dict(index=3, note="different value")) if fit else None)


def rec(name, sb, lo, status="done", c36=None, witness=None, **kw):
    """A record. sb, lo: True (selected and right), False (not rebuilt), None (the selection is undetermined)."""
    def selection(v, first):
        return dict(determined=v is not None, expr="e(x0)" if v else None, stage=1 if v else None, search=first if v else None, rebuilt=v,
                    wrong_only_by_guard_timeout=False, oracle_union=bool(v) if v is not None else None, order_of_sets=None, reason="r")
    searches = {n: search("none") for n in P.SEARCH_NAMES}
    searches["LC4-36"], searches["L4-36"] = search("right" if sb else "none"), search("right" if lo else "none")
    if c36 is not None:
        searches["C-36"] = search(c36)
    r = dict(target=name, status=status, dev=name in P.DEV_ROSTER, stratum=P.stratum_of(name), searches=searches,
             selection=dict(smaller_blocks=selection(sb, "LC4-36"), library_only=selection(lo, "L4-36")), setup_view=json.loads(json.dumps(VIEW)),
             cpu_s_total=13.0, cpu=dict(searches_s=12.0, final_checks_s=0.5, other_s=0.5), memory=[dict(after="x", address_space_peak_kb=50000, resident_peak_kb=40000)],
             final_panel=dict(generator=30, pooled=40, pooled_short=False, pooled_discarded=2, pooled_not_evaluated=0))
    if witness is not None:
        r["witness"] = witness
    r.update(kw)
    return r


def committed(names, excluded=()):
    targets = {t: json.loads(json.dumps(VIEW)) for t in names}
    for t in excluded:
        targets[t] = dict(decision=dict(status="excluded", reason_kind="too_few_usable_pooled_inputs"), counts=dict(usable=3))
    return dict(roster="all", targets=targets)


def control_records(n_right, names=None, **kw):
    names = CONTROLS if names is None else names
    return {c: rec(c, True, True, c36="right" if i < n_right else "none", witness=dict(WITNESS), **kw) for i, c in enumerate(names)}


def witnesses(names=None, nodes=3):
    return {c: dict(tree=["L", "c_len", ["P", "x0"]], nodes=nodes, note="") for c in (CONTROLS if names is None else names)}


def read(w, l, both=2, neither=3, cal_right=28, cohort_extra=(), **changes):
    """The primary over a committed cohort of w + l + both + neither longer targets, with a calibration of 28 controls."""
    names = LONGER[:w + l + both + neither]
    recs = {}
    for i, t in enumerate(names):
        sb = i < w or w + l <= i < w + l + both
        lo = w <= i < w + l or w + l <= i < w + l + both
        recs[t] = rec(t, sb, lo)
    recs.update(control_records(cal_right))
    sr = committed(names + CONTROLS + list(cohort_extra))
    for change in changes.values():
        change(recs, sr)
    rc = SM.reconcile(recs, sr)
    cal = SM.calibration({t: r for t, r in recs.items() if t not in P.DEV_ROSTER}, sr, witnesses(), 4)
    return SM.primary(recs, sr, cal, rc), cal, recs, sr


# ---------------------------------------------------------------- the sign test
def test_the_exact_two_sided_sign_test():
    f = SM.sign_test_two_sided
    assert f(0, 0) == 1.0 and f(5, 0) == 0.0625 and f(6, 0) == 0.03125 and f(7, 2) == 0.1796875 and f(3, 3) == 1.0
    assert f(0, 5) == f(5, 0) and f(2, 7) == f(7, 2) and f(1, 0) == 1.0 and f(8, 1) == pytest.approx(2 * 10 / 512)
    for w in range(9):
        for l in range(9):
            n, k = w + l, min(w, l)
            want = 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
            assert f(w, l) == want and 0 < f(w, l) <= 1.0


# ---------------------------------------------------------------- the primary: met and not met
def test_met_needs_all_four_parts():
    p, cal, recs, sr = read(6, 0)
    assert p["status"] == "met" and p["criterion_met"] is True and p["cohort_complete"] is True and p["provisional"] is False and p["not_interpretable"] is False
    assert (p["N"], p["W"], p["L"], p["W_minus_L"], p["both"], p["neither"]) == (11, 6, 0, 6, 2, 3) and p["p_two_sided_sign_test"] == 0.03125
    assert p["rebuilt"] == dict(smaller_blocks=8, library_only=2) and len(p["targets"]["smaller_blocks_only"]) == 6
    assert p["criterion_parts"] == {"1_W_greater_than_L": True, "2_p_below_0_05": True, "3_calibration_valid_and_passed": True, "4_cohort_complete": True}
    assert p["committed_cohort"] == 11 and cal["state"] == "passed" and p["label"] == P.LABEL
    assert p["targets_wrong_only_because_a_final_check_timed_out"] == [] and "reading_without_the_timed_out_targets" not in p


@pytest.mark.parametrize("w,l,p_value", [(5, 0, 0.0625), (7, 2, 0.1796875), (0, 0, 1.0), (2, 2, 1.0), (0, 6, 0.03125), (1, 8, 2 * 10 / 512)])
def test_not_met(w, l, p_value):
    p, cal, recs, sr = read(w, l)
    assert p["status"] == "not_met" and p["criterion_met"] is False and p["p_two_sided_sign_test"] == pytest.approx(p_value)
    assert p["cohort_complete"] is True and p["not_interpretable"] is False and (p["W"], p["L"]) == (w, l)
    assert p["criterion_parts"]["1_W_greater_than_L"] == (w > l) and p["criterion_parts"]["2_p_below_0_05"] == (p_value < 0.05)


def test_only_the_longer_stratum_outside_the_development_names_enters_the_primary():
    def more(recs, sr):
        for t in SHORT[:6]:
            if t not in recs:
                recs[t] = rec(t, False, True)                        # short stratum: the library alone rebuilds them
                sr["targets"][t] = json.loads(json.dumps(VIEW))
        for t in [d for d in P.DEV_ROSTER if P.stratum_of(d) == "longer"][:6]:
            recs[t] = rec(t, False, True)                            # development names
            sr["targets"][t] = json.loads(json.dumps(VIEW))
    p, cal, recs, sr = read(6, 0, more=more)
    assert p["status"] == "met" and (p["N"], p["W"], p["L"]) == (11, 6, 0)
    assert all(P.stratum_of(t) == "longer" and t not in P.DEV_ROSTER for cell in p["targets"].values() for t in cell)


# ---------------------------------------------------------------- provisional, for each cause
def expect_provisional(p, word):
    assert p["status"] == "provisional" and p["provisional"] is True and p["cohort_complete"] is False and p["criterion_met"] is False
    assert any(word in reason for reason in p["provisional_reasons"]), p["provisional_reasons"]
    assert p["criterion_parts"]["4_cohort_complete"] is False


def test_provisional_a_committed_eligible_target_without_a_record():
    p, *_ = read(6, 0, cohort_extra=[LONGER[40], LONGER[41]])
    expect_provisional(p, "have no record")
    assert p["committed_eligible_targets_without_a_record"] == sorted([LONGER[40], LONGER[41]]) and p["W"] == 6 and p["W_greater_than_L"] and p["p_below_0_05"]


def test_provisional_a_committed_eligible_target_without_a_complete_record():
    def incomplete(recs, sr):
        recs[LONGER[0]] = rec(LONGER[0], None, True, status="incomplete", reason="search L4-36: hard_stop")
    p, *_ = read(7, 0, change=incomplete)
    expect_provisional(p, "no complete record")
    assert p["committed_eligible_targets_without_a_complete_record"] == [LONGER[0]] and p["N"] == 11 and p["W"] == 6      # left out of the table

    def undetermined(recs, sr):
        recs[LONGER[1]] = rec(LONGER[1], True, None)                 # status done but one selection was never checked
    p, *_ = read(7, 0, change=undetermined)
    expect_provisional(p, "no complete record")

    def excluded_in_the_run(recs, sr):
        recs[LONGER[2]] = dict(target=LONGER[2], status="excluded", reason_kind="generator", setup_view=json.loads(json.dumps(VIEW)))
    p, *_ = read(7, 0, change=excluded_in_the_run)
    expect_provisional(p, "no complete record")


def test_provisional_a_target_outside_the_committed_cohort_that_was_run():
    def extra(recs, sr):
        recs[LONGER[50]] = rec(LONGER[50], False, True)              # run, but not committed as eligible
    p, *_ = read(6, 0, change=extra)
    expect_provisional(p, "outside the committed cohort")
    assert p["targets_outside_the_committed_cohort_that_were_run"] == [LONGER[50]] and (p["N"], p["W"], p["L"]) == (11, 6, 0)      # and it is not counted

    def committed_excluded_but_run(recs, sr):
        recs[SHORT[20]] = rec(SHORT[20], True, True)
        sr["targets"][SHORT[20]] = dict(decision=dict(status="excluded", reason_kind="generator"), counts={})
    p, *_ = read(6, 0, change=committed_excluded_but_run)
    expect_provisional(p, "outside the committed cohort")


def test_provisional_setup_decisions_that_differ_from_the_committed_record():
    def differs(recs, sr):
        recs[LONGER[0]]["setup_view"]["decision"] = dict(status="eligible", reason_kind=None, usability_guard_timeout=True)
    p, cal, recs, sr = read(6, 0, change=differs)
    expect_provisional(p, "differ from the committed record")
    assert p["targets_whose_setup_differs_from_the_committed_record"] == [LONGER[0]] and (p["N"], p["W"]) == (10, 5)       # left out

    def counts_only(recs, sr):
        recs[LONGER[0]]["setup_view"]["counts"] = dict(usable=41)    # a count differs: listed apart, not a decision
    p, cal, recs, sr = read(6, 0, change=counts_only)
    assert p["status"] == "met"
    rc = SM.reconcile(recs, sr)
    assert rc["targets_whose_counts_differ"] == [LONGER[0]] and rc["n_decisions_differ"] == 0


def test_provisional_for_a_committed_eligible_target_that_is_not_in_the_primarys_table():
    """The cohort that must be complete is every committed eligible target (protocol sections 4 and 10), whatever
    its stratum, the development names included. Such a target never enters the table; without a complete record,
    run without being committed, or with another setup decision, it still makes the primary provisional."""
    dev = [d for d in P.DEV_ROSTER if d != "rapply"]
    other = [t for t in SHORT if t not in CONTROLS]

    def a_short_target_never_run(recs, sr):
        sr["targets"][other[0]] = json.loads(json.dumps(VIEW))       # committed as eligible; no record
    p, *_ = read(6, 0, change=a_short_target_never_run)
    expect_provisional(p, "not in the primary's table")
    assert p["other_committed_eligible_targets_without_a_record"] == [other[0]] and p["committed_eligible_targets_without_a_record"] == []
    assert (p["N"], p["W"], p["L"]) == (11, 6, 0) and p["W_greater_than_L"] and p["p_below_0_05"]       # the table itself is not touched

    def a_development_name_incomplete(recs, sr):
        sr["targets"][dev[0]] = json.loads(json.dumps(VIEW))
        recs[dev[0]] = rec(dev[0], None, True, status="incomplete", reason="search L5-36: hard_stop")
    p, *_ = read(6, 0, change=a_development_name_incomplete)
    expect_provisional(p, "not in the primary's table")
    assert p["other_committed_eligible_targets_without_a_complete_record"] == [dev[0]] and (p["N"], p["W"]) == (11, 6)
    assert p["committed_eligible_targets_of_every_stratum_and_the_development_names"] == 11 + len(CONTROLS) + 1 and p["committed_cohort"] == 11

    def a_development_name_run_without_being_committed(recs, sr):
        recs[dev[1]] = rec(dev[1], True, False)
    p, *_ = read(6, 0, change=a_development_name_run_without_being_committed)
    expect_provisional(p, "outside the committed cohort")
    assert p["targets_outside_the_committed_cohort_that_were_run"] == [dev[1]] and (p["N"], p["W"]) == (11, 6)

    def the_decision_of_a_short_target_differs(recs, sr):
        sr["targets"][other[1]] = json.loads(json.dumps(VIEW))
        recs[other[1]] = rec(other[1], False, True)
        recs[other[1]]["setup_view"]["decision"] = dict(status="eligible", reason_kind=None, usability_guard_timeout=True)
    p, *_ = read(6, 0, change=the_decision_of_a_short_target_differs)
    expect_provisional(p, "differ from the committed record")
    assert p["targets_whose_setup_differs_from_the_committed_record"] == [other[1]] and (p["N"], p["W"]) == (11, 6)

    def all_of_them_complete(recs, sr):                              # the control: with complete records nothing is provisional
        for t in (other[0], dev[0]):
            sr["targets"][t] = json.loads(json.dumps(VIEW))
            recs[t] = rec(t, False, True)
    p, *_ = read(6, 0, change=all_of_them_complete)
    assert p["status"] == "met" and p["provisional_reasons"] == [] and (p["N"], p["W"], p["L"]) == (11, 6, 0)


def test_provisional_without_a_committed_setup_record():
    recs = {t: rec(t, True, False) for t in LONGER[:6]}
    recs.update(control_records(28))
    cal = SM.calibration(recs, None, witnesses(), 4)
    p = SM.primary(recs, None, cal, SM.reconcile(recs, None))
    expect_provisional(p, "no committed setup record")
    assert p["N"] == 0 and p["targets_run_without_a_committed_record"] == sorted(LONGER[:6]) and cal["state"] == "unavailable"
    assert p["not_interpretable"] is True                            # both apply: the status is provisional and both sets of reasons are given
    assert p["not_interpretable_reasons"] and "unavailable" in p["not_interpretable_reasons"][0]


# ---------------------------------------------------------------- not interpretable: the calibration
def test_not_interpretable_when_the_calibration_is_unavailable():
    names = LONGER[:11]
    recs = {t: rec(t, i < 6, False) for i, t in enumerate(names)}
    recs.update(control_records(28))
    sr = committed(names + CONTROLS)
    rc = SM.reconcile(recs, sr)
    for manifest, size_c, word in ((None, 4, "no witness manifest"), (witnesses(), None, "size limit of C")):
        cal = SM.calibration(recs, sr, manifest, size_c)
        p = SM.primary(recs, sr, cal, rc)
        assert cal["state"] == "unavailable" and cal["valid"] is False and cal["passed"] is False and any(word in r for r in cal["reasons"])
        assert p["status"] == "not_interpretable" and p["not_interpretable"] is True and p["provisional"] is False and p["cohort_complete"] is True
        assert p["criterion_met"] is False and p["W"] == 6 and p["p_below_0_05"] is True and "unavailable" in p["not_interpretable_reasons"][0]
        assert p["criterion_parts"]["3_calibration_valid_and_passed"] is False


@pytest.mark.parametrize("problem,word", [
    (dict(agrees_on_all_36=False, valid=False), "does not agree with X on all 36 fit examples"),
    (dict(agrees_on_the_final_panel=False, valid=False), "does not agree with X on the complete final panel"),
    (dict(unsupported_results=2, agrees_on_the_final_panel=False, valid=False), "unsupported result"),
    (dict(guard_timeout=True, agrees_on_all_36=False, valid=False), "timeout of the guard"),
    (dict(state="static check failed", error="c_nothing is neither a block", valid=False), "missing validation (static check failed"),
    (dict(state="no manifest entry"), "missing validation (no manifest entry"),
    (dict(state="memory failure", error="x", valid=False), "missing validation (memory failure"),
])
def test_not_interpretable_when_a_witness_does_not_validate(problem, word):
    def spoil(recs, sr):
        recs[CONTROLS[5]]["witness"] = dict(WITNESS, **problem)
    p, cal, recs, sr = read(6, 0, change=spoil)
    assert cal["state"] == "invalid" and cal["valid"] is False and cal["passed"] is False and cal["K"] == 28
    assert len(cal["reasons"]) == 1 and cal["reasons"][0].startswith(CONTROLS[5] + ": ") and word in cal["reasons"][0]
    assert p["status"] == "not_interpretable" and p["cohort_complete"] is True and "invalid" in p["not_interpretable_reasons"][0]
    assert cal["C36_right"] == 28                                   # C-36 was right for all of them, and it is still not valid


def test_a_control_without_a_complete_record_is_listed_as_such_never_as_a_failed_witness():
    def no_witness_entry(recs, sr):
        del recs[CONTROLS[3]]["witness"]

    def incomplete(recs, sr):
        recs[CONTROLS[4]] = rec(CONTROLS[4], None, True, status="incomplete", reason="search C-36: hard_stop",
                                witness=dict(state="not evaluated", valid=False, reason="the record is incomplete: search C-36: hard_stop"))

    def missing(recs, sr):
        del recs[CONTROLS[6]]
    p, cal, recs, sr = read(6, 0, a=no_witness_entry, b=incomplete, c=missing)
    assert cal["state"] == "invalid" and len(cal["reasons"]) == 3
    by = {r.split(":")[0]: r for r in cal["reasons"]}
    assert "missing validation (no witness entry in the record)" in by[CONTROLS[3]]
    assert by[CONTROLS[4]] == "%s: no complete record (status incomplete)" % CONTROLS[4] and "witness" not in by[CONTROLS[4]]
    assert by[CONTROLS[6]] == "%s: no record" % CONTROLS[6]
    # the controls are of the short stratum: they are not in the primary's table, and they are committed eligible
    # targets all the same, so the cohort is not complete: provisional, with the reasons of the calibration beside it
    assert p["status"] == "provisional" and p["not_interpretable"] is True and "invalid" in p["not_interpretable_reasons"][0]
    assert p["other_committed_eligible_targets_without_a_record"] == [CONTROLS[6]]
    assert p["other_committed_eligible_targets_without_a_complete_record"] == [CONTROLS[4]]
    assert p["committed_eligible_targets_without_a_record"] == [] and p["committed_eligible_targets_without_a_complete_record"] == []
    assert (p["N"], p["W"], p["L"]) == (11, 6, 0)                    # the table itself is not touched


def test_calibration_K_and_its_threshold():
    assert [math.ceil(P.CALIBRATION_SHARE * k) for k in (19, 20, 21, 25, 28)] == [18, 18, 19, 23, 26] and P.CALIBRATION_MIN_K == 19
    assert "20 in the drafts" in P.CALIBRATION_MIN_K_NOTE and "before any search outside the development names" in P.CALIBRATION_MIN_K_NOTE
    for k, n_right, state in ((28, 26, "passed"), (28, 25, "failed"), (20, 18, "passed"), (20, 17, "failed"), (21, 19, "passed"), (21, 18, "failed"),
                              (19, 18, "passed"), (19, 17, "failed"), (18, 18, "invalid"), (10, 10, "invalid"), (0, 0, "invalid")):
        names = CONTROLS[:k]
        recs = control_records(n_right, names)
        cal = SM.calibration(recs, committed(names), witnesses(names), 4)
        assert cal["K"] == k and cal["state"] == state and cal["C36_right"] == n_right and cal["threshold_right"] == math.ceil(0.9 * k)
        assert cal["valid"] == (k >= 19) and cal["passed"] == (state == "passed") and cal["minimum_K"] == 19
        assert cal["minimum_K_note"] == P.CALIBRATION_MIN_K_NOTE         # the amendment travels with every summary
        if k < 19:
            assert cal["reasons"] == ["K is %d, below 19" % k]
    # failed is a state of its own: valid, and the threshold is not reached
    p, cal, recs, sr = read(6, 0, cal_right=25)
    assert cal["state"] == "failed" and cal["valid"] is True and cal["passed"] is False and cal["C36_not_right"] == {CONTROLS[25]: "none", CONTROLS[26]: "none", CONTROLS[27]: "none"}
    assert p["status"] == "not_interpretable" and "failed (25 of 28 right, 26 needed)" in p["not_interpretable_reasons"][0]


def test_K_is_recomputed_from_the_committed_record_and_the_manifest_and_never_from_an_outcome():
    manifest = witnesses()
    manifest[CONTROLS[0]]["nodes"] = 5                               # more than s = 4 nodes
    manifest[CONTROLS[1]] = dict(tree=None, nodes=None, note="needs a guard")
    del manifest[CONTROLS[2]]
    sr = committed(CONTROLS[:26], excluded=CONTROLS[26:])
    cs = SM.calibration_set(sr, manifest, 4)
    assert cs["K"] == 23 and cs["names"] == CONTROLS[3:26] and cs["controls_not_eligible"] == CONTROLS[26:] and cs["size_c"] == 4
    assert cs["eligible_controls_without_a_witness_within_s"] == {CONTROLS[0]: "the witness has more than 4 nodes (5)", CONTROLS[1]: "needs a guard",
                                                                 CONTROLS[2]: "no witness in the manifest"}
    assert SM.calibration_set(sr, manifest, 5)["K"] == 24 and SM.calibration_set(sr, manifest, 6)["names"][0] == CONTROLS[0]
    # outcomes do not move K: every control wrong, or incomplete, or without a record
    for recs in (control_records(0, CONTROLS[:26]), {}, {c: rec(c, None, None, status="incomplete") for c in CONTROLS[:26]}):
        cal = SM.calibration(recs, sr, manifest, 4)
        assert cal["K"] == 23 and cal["names"] == CONTROLS[3:26] and cal["state"] in ("failed", "invalid")
    assert SM.calibration_set(None, manifest, 4)["available"] is False and SM.calibration_set(sr, None, 4)["K"] is None


def test_provisional_and_not_interpretable_together_give_provisional_with_both_reasons():
    def spoil(recs, sr):
        recs[CONTROLS[5]]["witness"] = dict(WITNESS, agrees_on_all_36=False, valid=False)
    p, cal, recs, sr = read(6, 0, cohort_extra=[LONGER[40]], change=spoil)
    assert p["status"] == "provisional" and p["provisional"] is True and p["not_interpretable"] is True and p["criterion_met"] is False
    assert any("have no record" in r for r in p["provisional_reasons"]) and "invalid" in p["not_interpretable_reasons"][0]


# ---------------------------------------------------------------- a final check that ran out of time
def test_a_selection_wrong_only_by_a_timeout_is_listed_and_the_primary_is_read_both_ways():
    def timed_out(recs, sr):
        lo = recs[LONGER[0]]["selection"]["library_only"]             # the library-only expression counts as wrong by the timeout alone
        lo.update(determined=True, expr="e(x0)", stage=1, search="L4-36", rebuilt=False, wrong_only_by_guard_timeout=True)
    p, cal, recs, sr = read(6, 0, change=timed_out)
    assert p["targets_wrong_only_because_a_final_check_timed_out"] == [LONGER[0]] and (p["W"], p["p_below_0_05"]) == (6, True)
    without = p["reading_without_the_timed_out_targets"]
    assert (without["N"], without["W"], without["L"], without["p_two_sided_sign_test"]) == (10, 5, 0, 0.0625)
    assert p["criterion_parts"]["1_and_2_also_without_the_timed_out_targets"] is False and p["status"] == "not_met" and p["criterion_met"] is False
    p, *_ = read(7, 0, change=timed_out)                             # seven: both readings pass
    assert p["reading_without_the_timed_out_targets"]["W"] == 6 and p["status"] == "met"
    assert p["criterion_parts"]["1_and_2_also_without_the_timed_out_targets"] is True


# ---------------------------------------------------------------- the whole summary, from files
def write(tmp_path, recs, sr=None, manifest=None, run_manifest=None, costs=None):
    out = tmp_path / ("out%d" % len(os.listdir(str(tmp_path))))
    (out / "targets").mkdir(parents=True)
    for t, r in recs.items():
        (out / "targets" / (t + ".json")).write_text(json.dumps(r))
    (out / "MANIFEST.json").write_text(json.dumps(run_manifest or dict(roster="all", size_c=4, targets=sorted(recs))))
    if costs:
        (out / "RUN_COSTS.json").write_text(json.dumps(costs))
    folder = tmp_path / ("manifest%d" % len(os.listdir(str(tmp_path))))
    folder.mkdir()
    if manifest is not None:
        (folder / P.WITNESS_MANIFEST).write_text(json.dumps(manifest))
    srp = None
    if sr is not None:
        srp = str(tmp_path / ("setup%d.json" % len(os.listdir(str(tmp_path)))))
        open(srp, "w").write(json.dumps(sr))
    return str(out), srp, str(folder)


def test_the_summary_from_files_with_every_table(tmp_path):
    p, cal, recs, sr = read(6, 0)
    dev = [d for d in P.DEV_ROSTER if d != "rapply"][:5]
    excluded = dict(decision=dict(status="excluded", reason_kind="unsupported_values"), counts=dict(usable=0))
    for t in dev:                                                    # the committed record lists the development names too
        recs[t] = rec(t, True, False)
        sr["targets"][t] = json.loads(json.dumps(VIEW))
    recs["rapply"] = dict(target="rapply", status="excluded", reason_kind="unsupported_values", reason="66 of 66", setup_view=json.loads(json.dumps(excluded)))
    sr["targets"]["rapply"] = json.loads(json.dumps(excluded))
    recs[P.DEV_CONTROL] = rec(P.DEV_CONTROL, True, True, witness=dict(WITNESS))
    sr["targets"][P.DEV_CONTROL] = json.loads(json.dumps(VIEW))
    for t in SHORT[:4]:
        if t not in recs:
            recs[t] = rec(t, False, True)
            sr["targets"][t] = json.loads(json.dumps(VIEW))
    recs[LONGER[1]]["searches"]["L5-36"] = search("none", "allowance_used_up", "bounded")
    recs[LONGER[2]]["searches"]["L5-36"] = search("none", "size_limit_completed_function_cap", "bounded")
    recs[LONGER[3]]["searches"]["L5-36"] = search("wrong")
    recs[LONGER[4]]["searches"]["L4-9"] = search("wrong")
    out, srp, folder = write(tmp_path, recs, sr, witnesses(), costs=dict(pools_setup_cpu_s=3.1, wall_s=100.0, resident_peak_kb=900000))
    s = SM.write_summary(out, srp, folder)
    assert json.load(open(os.path.join(out, "SUMMARY.json"))) == s and s["label"] == P.LABEL
    assert s["PRIMARY"]["status"] == "met" and s["calibration"]["state"] == "passed" and s["size_c"] == 4
    assert s["counts"]["records"] == len(recs) and s["counts"]["excluded"] == 1 and s["counts"]["primary_status"] == "met" and s["counts"]["not_yet_run"] == 0
    d = s["denominators"]["original_outside_development"]
    assert (d["short"]["original"], d["longer"]["original"], d["longer_7_to_15"]["original"], d["longer_over_15"]["original"]) == (35, 90, 35, 55)
    assert d["longer"]["committed_eligible"] == 11 == d["longer"]["complete_records"] and s["denominators"]["roster"] == 145
    sec = s["secondary_outside_the_development_names"]
    assert set(sec) == {"outside_development_all_strata", "short_stratum", "longer_stratum", "longer_7_to_15", "longer_over_15"}
    assert sec["longer_stratum"]["paired_on_the_committed_cohort"]["W"] == 6 and sec["short_stratum"]["paired_on_the_committed_cohort"]["committed_cohort"] >= 28
    halves = sec["longer_7_to_15"]["paired_on_the_committed_cohort"]["N"] + sec["longer_over_15"]["paired_on_the_committed_cohort"]["N"]
    assert halves == sec["longer_stratum"]["paired_on_the_committed_cohort"]["N"] == 11
    lg = sec["longer_stratum"]
    assert lg["searches"]["L5-36"]["stop_class"] == {"allowance_used_up": 1, "found": 1, "size_limit_completed": 8, "size_limit_completed_function_cap": 1}
    assert lg["searches"]["L5-36"]["fruitless_exhaustive"] == 8 and lg["searches"]["L5-36"]["fruitless_bounded"] == 2      # exhaustive only without any cap
    assert lg["searches"]["L5-36"]["first_fit"] == {"none": 10, "wrong": 1} and lg["nine_example_searches"]["L4-9"] == {"none": 10, "wrong": 1}
    assert lg["L5_36_against_L4_36"]["counts"] == dict(both=0, first_only=0, second_only=2, neither=9, left_out=0)
    assert lg["systems"]["smaller_blocks"]["rebuilt"] == 8 and lg["systems"]["library_only"]["rebuilt"] == 2
    assert lg["systems"]["smaller_blocks"]["candidate_set_coverage_oracle_union_NOT_the_systems_result"] == 8
    assert lg["searches"]["LC4-36"]["sizes_of_found_expressions"] == {"3": 8} and lg["final_panels"]["pooled_min"] == 40
    block = s["development_names_development_only"]
    assert block["n_records"] == 7 and block["exclusions"]["by_kind"] == {"unsupported_values": 1} and block["development_witness"]["valid"] is True
    assert "never part of the primary" in block["note"] and all(t not in P.DEV_ROSTER for cell in s["PRIMARY"]["targets"].values() for t in cell)
    costs = s["costs_of_the_whole_job"]
    assert costs["setup_of_the_pools_cpu_s"] == 3.1 and costs["from_this_process"]["wall_s"] == 100.0 and "never added" in costs["note"]
    assert s["reconciliation_with_the_committed_setup_record"]["n_decisions_differ"] == 0
    assert lg["cpu"]["targets_total_s"] == 13.0 * 11 and lg["memory"]["address_space_peak_kb_largest"] == 50000


def test_LC4_36_against_L4_36_and_the_targets_missed_for_lack_of_time(tmp_path):
    """Secondary and descriptive: the paired table of LC4-36 against L4-36, and the targets where L4-36 is right while
    LC4-36 ended by the allowance without a right fit (the smaller-blocks system can miss a four-node library
    expression for lack of time)."""
    names = sorted(LONGER[:6])
    a, b, c, d, e, f = names
    recs = {}
    recs[a] = rec(a, False, True)                                    # L4-36 right, LC4-36 ended by the allowance: missed for lack of time
    recs[a]["searches"]["LC4-36"] = search("none", "allowance_used_up", "bounded")
    recs[b] = rec(b, True, True)                                     # both right
    recs[c] = rec(c, False, False)                                   # LC4-36 ended by the allowance and L4-36 found nothing: not listed
    recs[c]["searches"]["LC4-36"] = search("none", "allowance_used_up", "bounded")
    recs[d] = rec(d, False, True)                                    # L4-36 right, LC4-36 completed its level with no fit: not a matter of time
    recs[e] = rec(e, True, False)                                    # LC4-36 right only
    recs[f] = rec(f, False, True)                                    # L4-36 right, LC4-36 found a wrong expression: not listed
    recs[f]["searches"]["LC4-36"] = search("wrong")
    out, srp, folder = write(tmp_path, recs, committed(names))
    s = SM.write_summary(out, srp, folder)
    lg = s["secondary_outside_the_development_names"]["longer_stratum"]
    table = lg["LC4_36_against_L4_36"]
    assert (table["first"], table["second"]) == ("LC4-36", "L4-36")
    assert table["counts"] == dict(both=1, first_only=1, second_only=3, neither=1, left_out=0)
    assert table["targets"]["second_only"] == [a, d, f] and table["targets"]["first_only"] == [e] and table["targets"]["both"] == [b]
    missed = lg["L4_36_right_while_LC4_36_ended_by_its_budget"]
    assert missed["targets"] == [a] and missed["n"] == 1
    assert missed["LC4_36_ended_by_its_budget"] == [a, c] and missed["n_LC4_36_ended_by_its_budget"] == 2
    assert "descriptive" in missed["note"]
    assert (s["PRIMARY"]["W"], s["PRIMARY"]["L"], s["PRIMARY"]["both"]) == (1, 3, 1)  # the primary counts selections; this table changes none
    assert s["development_names_development_only"]["L4_36_right_while_LC4_36_ended_by_its_budget"] == dict(
        missed, targets=[], n=0, LC4_36_ended_by_its_budget=[], n_LC4_36_ended_by_its_budget=0)


def test_the_summary_without_a_committed_record_or_a_manifest_is_provisional(tmp_path):
    recs = {t: rec(t, True, False) for t in LONGER[:6]}
    out, srp, folder = write(tmp_path, recs)
    s = SM.write_summary(out, None, folder)
    assert s["PRIMARY"]["status"] == "provisional" and s["calibration"]["state"] == "unavailable"
    assert set(s["calibration"]["reasons"]) == {"no committed setup record", "no witness manifest"}
    assert s["reconciliation_with_the_committed_setup_record"]["available"] is False
    assert s["secondary_outside_the_development_names"]["longer_stratum"]["paired_smaller_blocks_against_library_only"]["W"] == 6
    assert SM.load_witness_manifest(folder) is None and SM.load_records(str(tmp_path / "nowhere")) == {}


def test_an_infrastructure_stop_is_incomplete_in_every_table(tmp_path):
    recs = {t: rec(t, True, False) for t in LONGER[:3]}
    bad = rec(LONGER[3], None, False, status="incomplete", reason="search LC4-36: memory_failure")
    bad["searches"]["LC4-36"] = dict(search("none", "memory_failure"), first_fit=None, incomplete=True, coverage=None)
    recs[LONGER[3]] = bad
    out, srp, folder = write(tmp_path, recs, committed(LONGER[:4]))
    s = SM.write_summary(out, srp, folder)
    lg = s["secondary_outside_the_development_names"]["longer_stratum"]
    assert lg["searches"]["LC4-36"]["first_fit"] == {"incomplete": 1, "right": 3} and lg["searches"]["LC4-36"]["infrastructure_stops"] == 1
    assert lg["incomplete_infrastructure"] == {LONGER[3]: "search LC4-36: memory_failure"} and lg["systems"]["smaller_blocks"]["n"] == 3
    assert s["PRIMARY"]["status"] == "provisional" and s["PRIMARY"]["committed_eligible_targets_without_a_complete_record"] == [LONGER[3]]
    assert SM.state_of(bad, "LC4-36") == "incomplete" and SM.complete(bad) is False and SM.rebuilt(bad, "smaller_blocks") is None


def test_a_search_stopped_by_the_time_safety_limit_makes_the_primary_provisional(tmp_path):
    """With the combination budget on, a search stopped by processor time is an infrastructure stop: the record is
    incomplete, the target is listed, and the primary is provisional (never "none" for that search)."""
    recs = {t: rec(t, True, False) for t in LONGER[:3]}
    bad = rec(LONGER[3], None, None, status="incomplete", reason="search L4-36: time_safety_limit")
    bad["searches"]["L4-36"] = dict(search("none", "time_safety_limit"), first_fit=None, incomplete=True, coverage=None)
    assert bad["searches"]["L4-36"]["incomplete"] is True and "time_safety_limit" in SM.INFRASTRUCTURE
    recs[LONGER[3]] = bad
    out, srp, folder = write(tmp_path, recs, committed(LONGER[:4]))
    s = SM.write_summary(out, srp, folder)
    lg = s["secondary_outside_the_development_names"]["longer_stratum"]
    assert lg["searches"]["L4-36"]["first_fit"]["incomplete"] == 1 and lg["searches"]["L4-36"]["infrastructure_stops"] == 1
    assert s["PRIMARY"]["status"] == "provisional" and s["PRIMARY"]["committed_eligible_targets_without_a_complete_record"] == [LONGER[3]]
    assert SM.state_of(bad, "L4-36") == "incomplete" and SM.complete(bad) is False
