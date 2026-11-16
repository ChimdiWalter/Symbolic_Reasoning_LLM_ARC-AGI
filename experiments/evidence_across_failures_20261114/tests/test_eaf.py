"""Fast tests of EAF1 on invented cases. Author: Chimdi Walter Ndubuisi
Run: env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python -s -B -m pytest -q -p no:cacheprovider experiments/evidence_across_failures_20261114/tests
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import pytest

import eaf_frozen
import dslx
import search as S
import consumers as C
import presets_eaf as P
import episode_eaf as E
import summarize_eaf as SM
import run_eaf as R

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = [sys.executable, "-s", "-B"]
ENV = dict(os.environ, PYTHONHASHSEED="0")
FIVE = ("ulcorner", "vfrontier", "tophalf", "leastcommon", "totuple")        # five eligible wrappers of rot180


def make_episode(cands, X="rot180", hide="self", outdir=None, B=0.3, monkeypatch=None):
    old, old_order = C.candidate_posts, E.wrapper_order
    C.candidate_posts = lambda X_, outs, closure=None: dict(cands=list(cands), n_raw=len(cands))
    E.wrapper_order = lambda X_, names: list(names)             # the test fixes the order of the wrappers itself
    try:
        ep = E.Episode(X, outdir or tempfile.mkdtemp(), B, None, hide)
        r = ep.setup()
    finally:
        C.candidate_posts, E.wrapper_order = old, old_order
    return ep, r


# ---------------------------------------------------------------- start-up
def test_imports_verified_and_tamper_refused(tmp_path):
    assert eaf_frozen.verify_imports()
    for rel in eaf_frozen.IMPORTED:
        d = tmp_path / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(eaf_frozen.ROOT, rel), d)
    assert eaf_frozen.verify_imports(root=str(tmp_path))
    with open(tmp_path / eaf_frozen.IMPORTED[3], "a") as f:
        f.write("# changed\n")
    with pytest.raises(SystemExit):
        eaf_frozen.verify_imports(root=str(tmp_path))


def test_arm_plans_share_tuples_and_differ_only_in_wrappers():
    A = P.ARMS
    assert [i for i, _ in A["A1x9"]] == [i for i, _ in A["A3x3"]] == list(range(9))
    assert [i for i, _ in A["A1x6"]] == [i for i, _ in A["A2x3"]] == list(range(6))
    assert {w for _, w in A["A1x9"]} == {1} and [w for _, w in A["A3x3"]] == [1] * 3 + [2] * 3 + [3] * 3
    assert [w for _, w in A["A2x3"]] == [1] * 3 + [2] * 3 and [i for i, _ in A["A1x3"]] == [0, 1, 2]
    assert P.ACQ == (0, 9) and P.ADM == (9, 21) and P.SUPPORT == (21, 24) and P.SETUP == (24, 36) and P.FINAL == (36, 66)


def test_generator_roles_are_disjoint_and_cover_66():
    spans = sorted([P.ACQ, P.ADM, P.SUPPORT, P.SETUP, P.FINAL])
    assert spans[0][0] == 0 and spans[-1][1] == 66 and all(a[1] == b[0] for a, b in zip(spans, spans[1:]))


# ---------------------------------------------------------------- an arm sees only its own tuples and wrappers
def test_constructed_case_wrapper_one_fits_nine_but_not_three_wrappers():
    true = [(i, i + 1) for i in range(9)]
    wrong = [(i, 99) for i in range(9)]            # same length, so wrapper 1 (len) cannot tell it from the truth
    w = {1: len, 2: lambda v: v[1], 3: lambda v: v[0] + v[1]}
    want = {k: [dslx.canon(w[k](v)) for v in true] for k in w}

    def arm(plan, posts_override=None):
        posts = [w[k] for _, k in plan]
        return E.make_accept(posts, [want[k][i] for i, k in plan])

    def vals_for(plan, cand):
        return tuple(cand[i] for i, _ in plan)
    for name in ("A1x9", "A3x3"):
        plan = P.ARMS[name]
        assert arm(plan)(vals_for(plan, true))
    assert arm(P.ARMS["A1x9"])(vals_for(P.ARMS["A1x9"], wrong))                 # accepted by A1x9
    assert not arm(P.ARMS["A3x3"])(vals_for(P.ARMS["A3x3"], wrong))             # rejected by A3x3 (wrappers 2 and 3)
    assert not arm(P.ARMS["A2x3"])(vals_for(P.ARMS["A2x3"], wrong))
    assert arm(P.ARMS["A1x6"])(vals_for(P.ARMS["A1x6"], wrong))


def test_a_wrapper_that_raises_rejects():
    acc = E.make_accept([lambda v: 1 / 0], ["1"])
    with pytest.raises(ZeroDivisionError):
        acc((1,))                                                                # the search catches it and rejects


def test_arms_do_not_borrow_from_each_other(monkeypatch):
    ep, r = make_episode(FIVE)
    assert r is None
    ep.step_acquisition()
    calls = []
    real = E.VS.search

    def spy(ops, leaves, accept, n, *a, **k):
        calls.append(dict(n=n, ops=id(ops), leaves=id(leaves), accept=id(accept), accept_obj=accept, leaf0=leaves[0][1]))
        return real(ops, leaves, accept, n, *a, **k)
    monkeypatch.setattr(E.VS, "search", spy)
    ep.step_arms()
    assert [c["n"] for c in calls] == [3, 6, 9, 6, 9]
    for k in ("ops", "leaves", "accept"):
        assert len({c[k] for c in calls}) == 5
    for c, name in zip(calls, P.ARM_ORDER):
        assert c["leaf0"] == tuple(ep.tuples[i][0] for i, _ in P.ARMS[name])
    assert set(ep.res["arms"]) == set(P.ARMS) and all(a["allowance"] == 0.3 for a in ep.res["arms"].values())
    assert ep.res["arms"]["A3x3"]["wrappers"] == [FIVE[0]] * 3 + [FIVE[1]] * 3 + [FIVE[2]] * 3


# ---------------------------------------------------------------- this experiment's own seeds (not stage A's)
def test_wrapper_order_is_this_experiments_own_and_seeded(monkeypatch):
    assert P.WRAPPER_TAG != "vf1-consumer:" and P.SEQ_TAG != "seq"
    names_ = ["w%02d" % i for i in range(12)]
    a = E.wrapper_order("rot180", names_)
    assert sorted(a) == names_ and a != names_ and a == E.wrapper_order("rot180", list(reversed(names_)))   # order of the input is irrelevant
    assert E.wrapper_order("hmirror", names_) != a
    monkeypatch.setattr(P, "WRAPPER_TAG", "another-tag:")
    assert E.wrapper_order("rot180", names_) != a


def test_setup_takes_the_wrappers_in_that_order(monkeypatch):
    monkeypatch.setattr(C, "candidate_posts", lambda X, outs, closure=None: dict(cands=list(FIVE), n_raw=5))
    monkeypatch.setattr(E, "wrapper_order", lambda X, names: list(reversed(names)))
    ep = E.Episode("rot180", tempfile.mkdtemp(), 0.3, None, "self")
    ep.setup()
    assert ep.res["setup"]["wrappers"]["chosen"] == list(reversed(FIVE)) and ep.res["setup"]["wrappers"]["order_tag"] == P.WRAPPER_TAG


def test_pooled_sequence_is_drawn_under_this_experiments_tag(monkeypatch):
    seen = {}
    real = C.pooled_sequence

    def spy(X, own, avoid, total, tag="seq", max_iter=60000):
        seen["tag"] = tag
        return real(X, own, avoid, total, tag=tag, max_iter=max_iter)
    monkeypatch.setattr(C, "pooled_sequence", spy)
    ep, r = make_episode(FIVE)
    assert r is None and seen["tag"] == P.SEQ_TAG and ep.res["setup"]["pooled_sequence"]["tag"] == P.SEQ_TAG


def test_pooled_tuples_whose_containers_hold_functions_are_dropped(monkeypatch):
    assert E.holds_function((1, (2, frozenset({len})))) and E.holds_function(frozenset({(len, 1)})) and E.holds_function((len,))
    assert not E.holds_function(len) and not E.holds_function(frozenset({1, 2})) and not E.holds_function(((1, 2), (3, 4))) and not E.holds_function(5)
    real = C.pooled_sequence

    def with_two_bad(X, own, avoid, total, tag="seq", max_iter=60000):
        seq = real(X, own, avoid, total, tag=tag, max_iter=max_iter)
        return [((len, max),)] + seq[:50] + [(frozenset({abs}),)] + seq[50:]
    monkeypatch.setattr(C, "pooled_sequence", with_two_bad)
    ep, r = make_episode(FIVE)
    assert r is None and ep.res["setup"]["pooled_sequence"]["dropped_holding_functions"] == 2
    assert not any(E.holds_function(v) for t in ep.seq for v in t) and ep.res["setup"]["pooled_sequence"]["own_tuples_holding_functions"] == 0
    monkeypatch.setattr(C, "pooled_sequence", real)
    ep2, _ = make_episode(FIVE)
    assert ep2.res["setup"]["pooled_sequence"]["dropped_holding_functions"] == 0 and len(ep2.seq) == len(ep.seq)


def test_an_unusable_demonstrated_output_excludes(monkeypatch):
    real = E.Episode.post_ok
    monkeypatch.setattr(E.Episode, "post_ok", lambda self, w, xo: False if w == 2 else real(self, w, xo))
    ep, r = make_episode(FIVE)
    assert r["status"] == "excluded" and r["reason_kind"] == "acquisition_check"
    assert "wrapper 2" in r["reason"] and "usable" in r["reason"] and "[3, 4, 5]" in r["reason"]


# ---------------------------------------------------------------- nested cohorts
@pytest.mark.parametrize("n,coh", [(3, (1, 0, 0)), (4, (1, 1, 0)), (5, (1, 1, 1))])
def test_nested_cohorts_with_three_four_and_five_wrappers(n, coh):
    ep, r = make_episode(FIVE[:n])
    assert r is None
    c = ep.res["setup"]["cohorts"]
    assert (int(c["construction"]), int(c["admission"]), int(c["reuse"])) == coh
    assert ep.res["setup"]["wrappers"]["chosen"] == list(FIVE[:n]) and len(ep.wname) == n     # nothing padded
    assert ("admission" in c["unavailable"]) == (n < 4) and ("reuse" in c["unavailable"]) == (n < 5)
    assert ep.F is None and ep.rec.opened == ["setup", "acquisition"]


@pytest.mark.parametrize("cands", [FIVE[:2], ("numcolors",) + FIVE[:2], ()])
def test_fewer_than_three_excludes_never_pads(cands):
    ep, r = make_episode(cands)
    assert r["status"] == "excluded" and r["reason_kind"] == "fewer_than_three_wrappers"


def test_an_ineligible_wrapper_is_skipped_and_the_next_taken():
    ep, r = make_episode(("numcolors",) + FIVE)       # numcolors never changes under rot180: a trivial repair passes
    assert r is None and ep.res["setup"]["wrappers"]["chosen"] == list(FIVE)
    assert ep.res["setup"]["wrappers"]["skipped"][0]["post"] == "numcolors"


def test_usability_thresholds(monkeypatch):
    real = C.stream_usable

    def cut(ka, kb3, kb5):
        def f(X, argsets, post_fns=(), cpu=20):
            out = real(X, argsets, post_fns, cpu)
            return out[:{1: ka, 3: kb3, 4: kb5}[len(post_fns)]]
        return f
    monkeypatch.setattr(C, "stream_usable", cut(99, 29, 99))
    ep, r = make_episode(FIVE)
    assert r["status"] == "excluded" and r["reason_kind"] == "too_few_usable_pooled_inputs"
    monkeypatch.setattr(C, "stream_usable", cut(99, 99, 29))                 # wrapper 5 makes the pool short: reuse unavailable only
    ep, r = make_episode(FIVE)
    assert r is None and ep.coh["admission"] and not ep.coh["reuse"] and "wrapper 5" in ep.res["setup"]["cohorts"]["unavailable"]["reuse"]
    monkeypatch.setattr(C, "stream_usable", cut(11, 99, 99))                 # slice UA short: admission (and so reuse) unavailable
    ep, r = make_episode(FIVE)
    assert r is None and not ep.coh["admission"] and not ep.coh["reuse"]
    monkeypatch.setattr(C, "stream_usable", cut(12, 30, 30))
    ep, r = make_episode(FIVE)
    assert r is None and ep.coh["reuse"]


# ---------------------------------------------------------------- order of seals, controlled searches
WRONG = ("hmirror(grid)", 2, ("L", "hmirror", ("P", "grid")), 0.01, 5)
RIGHT = ("rot90(rot90(grid))", 3, ("L", "rot90", ("L", "rot90", ("P", "grid"))), 0.05, 9)


def fake_arms(table):
    """table: {arm: [hits]}; stands in for the arm searches so that the candidate order is controlled."""
    def search_arm(self, plan):
        name = [k for k, v in P.ARMS.items() if v is plan][0]
        hits = table.get(name, [])
        return dict(found=hits[0][:3] if hits else None, hits=list(hits), stop="found" if hits else "size_exhausted", level=3, bank=10,
                    function_cap_reached=False, cpu_s=0.1, candidates_tested=7)
    return search_arm


def fake_run(monkeypatch, table, cands=FIVE, B=0.3, extra=None):
    monkeypatch.setattr(E.Episode, "search_arm", fake_arms(table))
    monkeypatch.setattr(C, "candidate_posts", lambda X, outs, closure=None: dict(cands=list(cands), n_raw=len(cands)))
    monkeypatch.setattr(E, "wrapper_order", lambda X, names: list(names))
    out = tempfile.mkdtemp()
    return out, E.run_target("rot180", out, B, "self")


def test_order_of_seals_and_guards():
    ep, r = make_episode(FIVE)
    assert r is None and "setup_record" in ep.sealed
    with pytest.raises(E.OrderError):
        ep.step_arms()                                  # acquisition not sealed yet
    ep.step_acquisition()
    with pytest.raises(E.OrderError):
        ep.step_admission()                             # the five first-fit records are not sealed
    with pytest.raises(E.OrderError):
        ep.rec.get("admission")
    ep.search_arm = lambda plan: dict(found=None, hits=[], stop="size_exhausted", level=2, bank=1, function_cap_reached=False,
                                      cpu_s=0.0, candidates_tested=0)
    ep.step_arms()
    assert "first_fit_records" in ep.sealed and "admission_set" not in ep.sealed
    with pytest.raises(E.OrderError):
        ep.step_libraries()                             # admission not done
    with pytest.raises(E.OrderError):
        ep.open_final()
    ep.step_admission()
    with pytest.raises(E.OrderError):
        ep.step_reuse()                                 # libraries not sealed
    with pytest.raises(E.OrderError):
        ep.open_final()                                 # libraries not sealed
    ep.step_libraries()
    with pytest.raises(E.OrderError):
        ep.open_final()                                 # reuse support step not done
    with pytest.raises(E.OrderError):
        ep.fin()
    with pytest.raises(E.OrderError):
        ep.rec.get("final")
    ep.step_reuse()
    assert "reuse_support_set" in ep.sealed and ep.F is None
    ep.open_final()
    assert ep.F is not None


def test_journalled_seal_order_in_a_full_episode(monkeypatch):
    out, r = fake_run(monkeypatch, {"A3x3": [RIGHT], "A1x9": [WRONG]})
    names = [json.loads(x)["name"] for x in open(os.path.join(out, "journal", "rot180.jsonl")) if '"event": "seal"' in x]
    assert names == ["setup_record", "acquisition_record", "first_fit_records", "admission_set", "libraries", "reuse_support_set", "final_set"]
    assert r["status"] == "done" and r["arms"]["A3x3"]["first_fit"] == "right" and r["arms"]["A1x9"]["first_fit"] == "wrong"
    assert r["arms"]["A1x3"]["first_fit"] == "none" and r["arms"]["A3x3"]["task_exact"] == {"1": True, "2": True, "3": True}


def test_failed_admission_is_not_replaced_and_admitted_library_is_read_only(monkeypatch):
    # a wrong first fit whose second candidate (never tried) would have been right
    out, r = fake_run(monkeypatch, {"A1x9": [WRONG, RIGHT], "A3x3": [RIGHT]})
    a = r["arms"]["A1x9"]
    assert a["expr"] == "hmirror(grid)" and a["admitted"] is False and "library" not in a and a["first_fit"] == "wrong"
    assert not os.path.exists(os.path.join(out, "library", "rot180__A1x9.json"))
    b = r["arms"]["A3x3"]
    assert b["admitted"] is True and b["reuse_exact"] is True and os.stat(os.path.join(out, b["library"]["path"])).st_mode & 0o222 == 0
    assert r["reuse"]["controls"]["fresh_repair"]["stop_class"] in ("complete_negative", "allowance_used_up", "fit", "size_limit_with_function_cap")
    assert r["arms"]["A1x3"]["reuse_exact"] is False                                    # no library: counts as not exact


def test_role_unavailable_is_recorded_not_a_failure(monkeypatch):
    out, r = fake_run(monkeypatch, {"A3x3": [RIGHT]}, cands=FIVE[:3])
    assert r["status"] == "done" and r["arms"]["A3x3"]["admitted"] is None and r["arms"]["A3x3"]["reuse_exact"] is None
    assert r["reuse"]["available"] is False and r["admission_evidence"]["available"] is False and "library" not in r["arms"]["A3x3"]


def test_infrastructure_failure_in_an_arm_is_incomplete_not_negative(monkeypatch):
    def boom(self, plan):
        raise RuntimeError("x")
    monkeypatch.setattr(E.Episode, "search_arm", boom)
    monkeypatch.setattr(C, "candidate_posts", lambda X, outs, closure=None: dict(cands=list(FIVE), n_raw=5))
    monkeypatch.setattr(E, "wrapper_order", lambda X, names: list(names))
    r = E.run_target("rot180", tempfile.mkdtemp(), 0.3, "self")
    assert all(a["stop_class"] == "incomplete" for a in r["arms"].values())
    assert SM.outcome(r, "A3x3") is None


# ---------------------------------------------------------------- setup-only opens no final data
def test_setup_only_opens_no_final_data(monkeypatch, tmp_path):
    def no(*a, **k):
        raise AssertionError("final data touched")
    monkeypatch.setattr(E.Episode, "open_final", no)
    monkeypatch.setattr(E.Episode, "fin", no)
    monkeypatch.setattr(E.Episode, "step_arms", no)
    v = E.setup_only("hmirror")
    assert v["opened_roles"] == ["setup", "acquisition"] and v["decision"]["status"] == "eligible"
    monkeypatch.setattr(R, "roster_of", lambda name: ["hmirror", "rot180"])
    out = str(tmp_path / "s.json")
    R.do_setup_only(out, "dev")
    rec = json.load(open(out))
    assert set(rec["targets"]) == {"hmirror", "rot180"} and "final_panel" not in json.dumps(rec)
    assert all(t["opened_roles"] == ["setup", "acquisition"] for t in rec["targets"].values())
    with pytest.raises(SystemExit):
        R.do_setup_only(out, "dev")                                 # never overwrites
    calls = []                                                      # a file that changes during the pass: nothing is written
    monkeypatch.setattr(R, "file_hashes", lambda *a, **k: calls.append(1) or {"x": len(calls)})
    out2 = str(tmp_path / "s2.json")
    with pytest.raises(SystemExit):
        R.do_setup_only(out2, "dev")
    assert not os.path.exists(out2)


# ---------------------------------------------------------------- summary on hand-made records
def rec(name, a3, a1, a2=None, a16=None, **kw):
    def arm(o):
        return dict(first_fit=o, fit=o != "none", stop_class="fit" if o != "none" else "complete_negative", admitted=False, task_exact={},
                    cpu_s=1.0, cpu_to_first_fit=0.5 if o != "none" else None, candidates_tested=5, bank=3, level_completed=2, stop="x")
    arms = {a: arm("none") for a in P.ARM_ORDER}
    arms["A3x3"], arms["A1x9"] = arm(a3), arm(a1)
    if a2:
        arms["A2x3"] = arm(a2)
    if a16:
        arms["A1x6"] = arm(a16)
    r = dict(target=name, status="done", cohorts=dict(construction=True, admission=False, reuse=False), arms=arms,
             setup=dict(cohorts=dict(unavailable={})), cpu_s_total=1.0)
    r.update(kw)
    return r


def primary(rs, expected="auto"):
    done = rs
    exp = [r["target"] for r in rs] if expected == "auto" else expected
    return SM.comparison(done, "A3x3", "A1x9", exp, primary=True)


def names(k, p="t"):
    return ["%s%d" % (p, i) for i in range(k)]


def test_sign_test_exact():
    assert SM.sign_test_two_sided(5, 0) == pytest.approx(0.0625) and SM.sign_test_two_sided(6, 0) == pytest.approx(0.03125)
    assert SM.sign_test_two_sided(0, 0) == 1.0 and SM.sign_test_two_sided(3, 3) == 1.0


def test_five_favourable_cannot_meet_the_test_six_can():
    five = [rec(n, "right", "wrong") for n in names(5)]
    c = primary(five)
    assert c["conditions"]["2_sign_test_below_0.05"] is False and c["criterion_met"] is False and c["status"] == "not_met"
    six = [rec(n, "right", "wrong") for n in names(6)]
    c = primary(six)
    assert all(c["conditions"].values()) and c["criterion_met"] is True and c["status"] == "met"
    assert c["paired_table_rows_first_arm_columns_second_arm"]["right"]["wrong"] == 6
    assert c["wrong_first_fits"] == {"A3x3": 0, "A1x9": 6} and c["right_first_fits"] == {"A3x3": 6, "A1x9": 0}


def test_fewer_wrong_but_zero_right_is_not_met():
    c = primary([rec(n, "none", "wrong") for n in names(8)])
    assert c["conditions"]["1_fewer_wrong_in_A3x3"] and c["conditions"]["2_sign_test_below_0.05"]
    assert c["conditions"]["4_at_least_one_right_in_A3x3"] is False and c["criterion_met"] is False


def test_fewer_wrong_with_fewer_right_is_not_met():
    rs = [rec(n, "none", "wrong") for n in names(7)] + [rec("r%d" % i, "none", "right") for i in range(2)] + [rec("q", "right", "right")]
    c = primary(rs)
    assert c["right_first_fits"] == {"A3x3": 1, "A1x9": 3}
    assert c["conditions"]["3_right_in_A3x3_not_fewer_than_in_A1x9"] is False and c["criterion_met"] is False


def test_unfavourable_targets_count_against_the_sign_test():
    rs = [rec(n, "right", "wrong") for n in names(6)] + [rec("u", "wrong", "right")]
    c = primary(rs)
    assert c["n_favourable"] == 6 and c["n_unfavourable"] == 1 and c["p_two_sided_sign_test"] == pytest.approx(2 * 8 / 128)
    assert c["conditions"]["2_sign_test_below_0.05"] is False


def test_a_missing_or_incomplete_eligible_target_makes_it_provisional():
    rs = [rec(n, "right", "wrong") for n in names(6)]
    c = primary(rs, expected=names(6) + ["absent"])
    assert all(c["conditions"].values()) and c["criterion_met"] is False and c["status"] == "provisional" and c["missing_eligible_targets"] == ["absent"]
    inc = rs[:-1] + [rec("t5", "right", "wrong")]
    inc[-1]["arms"]["A3x3"]["stop_class"] = "incomplete"
    c = primary(inc)
    assert c["status"] == "provisional" and c["incomplete_targets"] == ["t5"] and c["criterion_met"] is False
    assert primary(rs, expected=None)["status"] == "provisional"


def test_only_the_committed_cohort_is_read_and_a_setup_difference_is_provisional():
    rs = [rec(n, "right", "wrong") for n in names(6)]
    c = primary(rs + [rec("extra", "wrong", "right")], expected=names(6))
    assert c["done_targets_outside_the_committed_cohort"] == ["extra"] and c["n_targets_terminal"] == 6 and c["n_unfavourable"] == 0
    assert all(c["conditions"].values()) and c["status"] == "provisional" and c["criterion_met"] is False
    c = SM.comparison(rs, "A3x3", "A1x9", names(6), primary=True, mismatch=["t0", "not_run"])
    assert c["targets_whose_setup_differs_from_the_committed_record"] == ["t0"] and c["n_targets_terminal"] == 5
    assert c["status"] == "provisional" and c["missing_eligible_targets"] == [] and c["criterion_met"] is False
    assert primary(rs)["status"] == "met"


def test_a_timed_out_final_check_is_listed_and_read_both_ways():
    rs = [rec(n, "right", "wrong") for n in names(6)]
    assert primary(rs)["targets_with_a_wrong_only_because_the_final_check_timed_out"] == []
    rs[0]["arms"]["A1x9"]["counterexample"] = dict(index=-1, note="guard timeout")
    c = primary(rs)
    assert c["targets_with_a_wrong_only_because_the_final_check_timed_out"] == ["t0"] and c["all_four_conditions_hold"] is True
    assert c["reading_without_the_timed_out_targets"]["n_favourable"] == 5
    assert c["all_four_conditions_hold_in_both_readings"] is False and c["criterion_met"] is False and c["status"] == "not_met"
    t = SM.arm_table(rs)
    assert t["A1x9"]["wrong_only_because_the_final_check_timed_out"] == ["t0"] and t["A3x3"]["wrong_only_because_the_final_check_timed_out"] == []


# ---------------------------------------------------------------- the final check's guard: fault fixtures, no search (review 0736)
ARGS = [(i,) for i in range(5)]
XOUT = [i * 10 for i in range(5)]


def bare_episode(w_full=None, w_les=None):
    """An Episode with no setup: match_list needs only its arguments and, for a wrapper, the two wrapper tables."""
    ep = E.Episode.__new__(E.Episode)
    ep.w_full, ep.w_les = dict(w_full or {}), dict(w_les or {})
    return ep


def counted(body):
    """A fake candidate of one argument; body(call number, argument) decides what it does."""
    calls = []

    def f(a):
        calls.append(a)
        return body(len(calls), a)
    return f, calls


def test_a_timeout_inside_the_candidate_ends_the_batch_and_is_marked():
    def body(n, a):
        if n == 3:
            raise C.GuardTimeout()
        return a * 10
    fn, calls = counted(body)
    oks, first, err = bare_episode().match_list(fn, ARGS, XOUT, None)
    assert oks == [True, True, False, False, False] and first == dict(index=-1, note="guard timeout") and err == 0
    assert len(calls) == 3                                     # the batch ended at the timeout: nothing ran after it unguarded


def test_an_ordinary_error_is_one_bad_tuple_and_the_batch_goes_on():
    def body(n, a):
        if n == 3:
            raise ValueError("an ordinary error")
        return a * 10
    fn, calls = counted(body)
    oks, first, err = bare_episode().match_list(fn, ARGS, XOUT, None)
    assert oks == [True, True, False, True, True] and err == 1 and len(calls) == 5
    assert first["index"] == 2 and first["got"] == "ERR" and "note" not in first and "guard_timeout_after_this" not in first


def test_a_real_counterexample_before_a_timeout_stays_the_counterexample():
    def body(n, a):
        if n == 2:
            return -1                                          # a wrong value: a real counterexample at index 1
        if n == 4:
            raise C.GuardTimeout()
        return a * 10
    fn, calls = counted(body)
    oks, first, err = bare_episode().match_list(fn, ARGS, XOUT, None)
    assert oks == [True, False, True, False, False] and len(calls) == 4 and err == 0
    assert first["index"] == 1 and first.get("note") is None and first["guard_timeout_after_this"] is True


def test_a_timeout_inside_a_wrapper_or_the_comparison_is_a_timeout_too(monkeypatch):
    def boom(v):
        raise C.GuardTimeout()
    ep = bare_episode(w_full={1: lambda v: v}, w_les={1: boom})
    oks, first, err = ep.match_list(lambda a: a * 10, ARGS, XOUT, 1)
    assert oks == [False] * 5 and first == dict(index=-1, note="guard timeout") and err == 0
    n, real_same = [0], C.same

    def same(x, y):
        n[0] += 1
        if n[0] == 2:
            raise C.GuardTimeout()
        return real_same(x, y)
    monkeypatch.setattr(C, "same", same)
    oks, first, err = bare_episode().match_list(lambda a: a * 10, ARGS, XOUT, None)
    assert oks == [True, False, False, False, False] and first == dict(index=-1, note="guard timeout") and err == 0 and n[0] == 2


def test_the_real_cpu_timer_delivered_inside_the_candidate_is_a_timeout(monkeypatch):
    monkeypatch.setattr(C.V, "GUARD_CPU", 0.2)                 # this test only: the run's guard is 30 CPU seconds
    before = signal.getsignal(signal.SIGVTALRM)
    calls = []

    def slow(a):
        calls.append(a)
        if len(calls) == 2:
            t = time.process_time()
            while time.process_time() - t < 5:                 # spins until the CPU timer interrupts it
                pass
        return a * 10
    oks, first, err = bare_episode().match_list(slow, ARGS, XOUT, None)
    assert first == dict(index=-1, note="guard timeout") and oks == [True, False, False, False, False] and err == 0
    assert len(calls) == 2                                     # before the correction the batch went on: 5 calls, an ordinary error
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and signal.getsignal(signal.SIGVTALRM) == before


def test_a_timed_out_final_check_reaches_the_record_and_the_summary():
    """step_final itself, on an episode with no search and no setup: a first fit whose final check times out before
    any counterexample is recorded as wrong and marked; the summary lists it and gives the reading without it. A first
    fit with a real counterexample before a timeout is wrong, keeps that counterexample and is not listed."""
    ep = E.Episode.__new__(E.Episode)
    ep.X, ep.coh, ep.done = "invented", dict(reuse=False), set()
    ep.w_full = {w: (lambda v: v) for w in (1, 2, 3)}
    ep.w_les = dict(ep.w_full)
    ep.F = dict(gen_args=ARGS[:2], gen_x=XOUT[:2], pool_args=ARGS[2:], pool_x=XOUT[2:], args=list(ARGS), x=list(XOUT))
    ep.open_final = lambda: None                               # the invented panel above stands in for the sealed one
    ep.fit_tree = {a: None for a in P.ARM_ORDER}
    ep.fit_tree.update(A3x3="times out", A1x9="counterexample, then a timeout")

    def times_out(a):
        raise C.GuardTimeout()

    def counterexample_then_timeout(a):
        if a == 0:
            return -1
        if a == 1:
            raise C.GuardTimeout()
        return a * 10
    ep.cand_fn = lambda tree: times_out if tree == "times out" else counterexample_then_timeout
    ep.res = dict(arms={a: {} for a in P.ARM_ORDER})
    ep.step_final()
    a3, a1 = ep.res["arms"]["A3x3"], ep.res["arms"]["A1x9"]
    assert a3["first_fit"] == "wrong" and a3["counterexample"] == dict(index=-1, note="guard timeout") and a3["right_detail"]["gen"] == [0, 2]
    assert a1["first_fit"] == "wrong" and a1["counterexample"]["index"] == 0 and a1["counterexample"]["guard_timeout_after_this"] is True
    assert "note" not in a1["counterexample"] and ep.res["arms"]["A2x3"]["first_fit"] == "none" and "final" in ep.done
    r = rec("t0", "wrong", "wrong")
    r["arms"]["A3x3"].update(a3)
    r["arms"]["A1x9"].update(a1)
    assert SM.timed_out_wrong(r, "A3x3") is True and SM.timed_out_wrong(r, "A1x9") is False
    c = primary([r] + [rec(n, "right", "wrong") for n in names(6, "u")])
    assert c["targets_with_a_wrong_only_because_the_final_check_timed_out"] == ["t0"]
    assert c["reading_without_the_timed_out_targets"]["n_targets_terminal"] == 6 and c["n_targets_terminal"] == 7


def test_blocks_kept_apart_and_labelled(tmp_path):
    out = tmp_path / "o"
    (out / "targets").mkdir(parents=True)
    for r in [rec("rot180", "right", "wrong"), rec("zzz_not_dev", "right", "wrong")]:
        (out / "targets" / (r["target"] + ".json")).write_text(json.dumps(r))
    s = SM.write_summary(str(out))
    dev, outs = s["block_development_roster_development_only"], s["block_outside_development_roster"]
    assert dev["cohort_sizes"]["construction"] == 1 and outs["cohort_sizes"]["construction"] == 1
    assert s["label"] == "development comparison on a known benchmark" and dev["PRIMARY_A3x3_against_A1x9"]["label"] == s["label"]
    assert outs["PRIMARY_A3x3_against_A1x9"]["status"] == "provisional" and "criterion_met" not in dev["PRIMARY_A3x3_against_A1x9"]
    for k in ("five_arms_side_by_side", "admissions_by_arm", "reuse", "costs", "final_panels", "held_out_names_apart", "secondary_A2x3_against_A1x6"):
        assert k in outs


def test_reconciliation_separates_decisions_from_counts():
    r1 = dict(target="a", status="done", setup_view=dict(decision=dict(x=1), counts=dict(n=5)))
    r2 = dict(target="b", status="done", setup_view=dict(decision=dict(x=1), counts=dict(n=5)))
    com = dict(targets=dict(a=dict(decision=dict(x=1), counts=dict(n=6)), b=dict(decision=dict(x=2), counts=dict(n=5))))
    out = SM.reconcile(dict(a=r1, b=r2), com)
    assert out["targets_whose_counts_differ"] == ["a"] and [d["target"] for d in out["decisions_differ"]] == ["b"]


# ---------------------------------------------------------------- guards of the runner, in fresh processes
def copy_exp(tmp_path, protocol=True):
    d = tmp_path / "expcopy"
    shutil.copytree(HERE, d, ignore=shutil.ignore_patterns("dev_out*", "__pycache__", "RECEIPT*", "PROTOCOL.md", "SETUP*"))
    if protocol:
        (d / "PROTOCOL.md").write_text("test protocol\n")
    return d


def run(args, base=None, env=None):
    return subprocess.run(PY + [os.path.join(str(base or HERE), "run_eaf.py")] + args, env=env or ENV, capture_output=True, text=True,
                          cwd=tempfile.gettempdir(), timeout=300)


def text(r):
    return r.stderr + r.stdout


def test_receipt_exclusive_one_launch_only(tmp_path):
    p1 = R.ensure_receipt(str(tmp_path), "/tmp/out_a", "f" * 64)
    assert os.path.exists(p1) and os.stat(p1).st_mode & 0o222 == 0
    for other in ("/tmp/out_a", "/tmp/out_b"):                      # the same folder too: an interrupted run is never resumed
        with pytest.raises(SystemExit):
            R.ensure_receipt(str(tmp_path), other, "f" * 64)


def code_hashes_of(exp):
    h = {os.path.relpath(str(exp / n), eaf_frozen.ROOT): R.sha256_file(str(exp / n)) for n in R.OWN_FILES}
    h[os.path.relpath(eaf_frozen.STAGE_A_FREEZE, eaf_frozen.ROOT)] = R.sha256_file(eaf_frozen.STAGE_A_FREEZE)
    return h


def test_refusals_in_fresh_processes(tmp_path):
    exp = copy_exp(tmp_path, protocol=False)
    out = str(tmp_path / "out")
    sr = tmp_path / "setup.json"
    sr.write_text(json.dumps(dict(roster="all", targets={"x": dict(decision=dict(), counts=dict())}, hashes=code_hashes_of(exp))))
    fz = tmp_path / "fz.json"
    r = run([out, "--roster", "all"], base=exp)
    assert r.returncode != 0 and "freeze" in text(r) and not os.path.exists(out)
    r = run([out, "--roster", "all", "--freeze", str(fz)], base=exp)
    assert r.returncode != 0 and "setup" in text(r) and not os.path.exists(out)                   # no setup record
    r = run(["--make-freeze", str(fz), "--setup-record", str(sr)], base=exp)                       # no PROTOCOL.md
    assert r.returncode != 0 and "PROTOCOL.md" in text(r) and not fz.exists()
    (exp / "PROTOCOL.md").write_text("test protocol\n")
    r = run(["--make-freeze", str(fz)], base=exp)                                                  # no setup record given
    assert r.returncode != 0 and "setup record" in text(r) and not fz.exists()
    r = run(["--make-freeze", str(fz), "--setup-record", str(tmp_path / "nope.json")], base=exp)
    assert r.returncode != 0 and not fz.exists()
    stale = tmp_path / "stale.json"                                                                # made by other code
    stale.write_text(json.dumps(dict(roster="all", targets={"x": {}}, hashes=dict(code_hashes_of(exp), **{sorted(code_hashes_of(exp))[0]: "0" * 64}))))
    r = run(["--make-freeze", str(fz), "--setup-record", str(stale)], base=exp)
    assert r.returncode != 0 and "other code" in text(r) and not fz.exists()
    stale.write_text(json.dumps(dict(roster="all", targets={"x": {}})))                            # no record of its code at all
    r = run(["--make-freeze", str(fz), "--setup-record", str(stale)], base=exp)
    assert r.returncode != 0 and "other code" in text(r) and not fz.exists()
    assert run(["--make-freeze", str(fz), "--setup-record", str(sr)], base=exp).returncode == 0
    first = open(fz).read()
    r = run(["--make-freeze", str(fz), "--setup-record", str(sr)], base=exp)                       # a freeze is written once
    assert r.returncode != 0 and "exists" in text(r) and open(fz).read() == first
    body = json.load(open(fz))
    rels = [k.split("/")[-1] for k in body["files"]]
    for need in ("PROTOCOL.md", "README.md", "test_eaf.py", "conftest.py", "episode_eaf.py", "summarize_eaf.py", "run_eaf.py", "FREEZE.json"):
        assert need in rels, need
    assert any(k.endswith("visible_failure_20261113/episode.py") for k in body["stage_a_files"]) and body["setup_record"]["name"] == "setup.json"
    # a hash in the freeze that is wrong
    bad = tmp_path / "bad.json"
    b2 = json.loads(json.dumps(body))
    k = sorted(b2["files"])[0]
    b2["files"][k] = "0" * 64
    bad.write_text(json.dumps(b2))
    r = run([out, "--roster", "all", "--freeze", str(bad), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "differs from the freeze" in text(r) and not os.path.exists(out)
    b2 = json.loads(json.dumps(body))
    k = sorted(b2["stage_a_files"])[0]
    b2["stage_a_files"][k] = "0" * 64
    bad.write_text(json.dumps(b2))
    r = run([out, "--roster", "all", "--freeze", str(bad), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "differs from the freeze" in text(r)
    for tail in ("README.md", "PROTOCOL.md", "test_eaf.py"):
        b2 = json.loads(json.dumps(body))
        b2["files"].pop([k for k in b2["files"] if k.endswith(tail)][0])
        bad.write_text(json.dumps(b2))
        r = run([out, "--roster", "all", "--freeze", str(bad), "--setup-record", str(sr)], base=exp)
        assert r.returncode != 0 and "does not cover" in text(r)
    # a changed setup record
    sr2 = tmp_path / "setup2.json"
    sr2.write_text(json.dumps(dict(roster="all", targets={"y": {}})))
    r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr2)], base=exp)
    assert r.returncode != 0 and "setup record differs" in text(r) and not os.path.exists(out)
    # --B and --targets with the full roster
    r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr), "--B", "1"], base=exp)
    assert r.returncode != 0 and "development roster only" in text(r)
    # a changed file after the freeze
    (exp / "README.md").write_text("changed after the freeze\n")
    r = run([out, "--roster", "all", "--freeze", str(fz), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "differs from the freeze" in text(r) and not os.path.exists(out)
    (exp / "README.md").write_text(open(os.path.join(HERE, "README.md")).read())
    fz2 = tmp_path / "fz2.json"
    assert run(["--make-freeze", str(fz2), "--setup-record", str(sr)], base=exp).returncode == 0
    # a valid freeze, but the output folder is not new or empty: refused before any receipt is written
    os.makedirs(out)
    open(os.path.join(out, "left_over"), "w").write("x")
    r = run([out, "--roster", "all", "--freeze", str(fz2), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "new or empty" in text(r) and not (exp / "RECEIPT_ALL_ROSTER.json").exists()
    shutil.rmtree(out)
    # a valid freeze, but a receipt of an all-roster run exists: refused for another output folder AND for the same one
    for earlier in (str(tmp_path / "first_out"), out):
        (exp / "RECEIPT_ALL_ROSTER.json").write_text(json.dumps(dict(outdir=earlier)))
        r = run([out, "--roster", "all", "--freeze", str(fz2), "--setup-record", str(sr)], base=exp)
        assert r.returncode != 0 and "receipt" in text(r) and "never resumed" in text(r) and not os.path.exists(out)
    os.makedirs(out)                                                 # the launched run's own folder, with files in it: the same refusal
    open(os.path.join(out, "left_over"), "w").write("x")
    r = run([out, "--roster", "all", "--freeze", str(fz2), "--setup-record", str(sr)], base=exp)
    assert r.returncode != 0 and "never resumed" in text(r) and os.listdir(out) == ["left_over"]
    shutil.rmtree(out)
    # no hash seed; targets outside the roster
    r = run([out, "--roster", "dev"], base=exp, env={k: v for k, v in ENV.items() if k != "PYTHONHASHSEED"})
    assert r.returncode != 0
    r = run([out, "--roster", "dev", "--targets", "hline"], base=exp)
    assert r.returncode != 0 and "outside" in text(r) and not os.path.exists(os.path.join(out, "targets"))


def test_no_environment_variable_moves_the_receipt_folder():
    src = open(os.path.join(HERE, "run_eaf.py")).read()
    assert "environ.get(" not in src.replace('os.environ.get("PYTHONHASHSEED")', "") and "getenv" not in src


def test_setup_only_in_a_fresh_process_refuses_an_existing_file(tmp_path):
    f = tmp_path / "exists.json"
    f.write_text("{}")
    r = run(["--setup-only", str(f), "--roster", "dev"])
    assert r.returncode != 0 and "exists" in text(r) and f.read_text() == "{}"
