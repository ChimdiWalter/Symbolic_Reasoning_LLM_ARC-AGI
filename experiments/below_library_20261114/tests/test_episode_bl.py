"""Tests of one target's episode (episode_bl.py), of the guards and of the presets, on development names and
invented candidates. No operation outside the development names is searched. Author: Chimdi Walter Ndubuisi
Run: env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B -m pytest -q -p no:cacheprovider experiments/below_library_20261114/tests
"""
import hashlib
import inspect
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time

import pytest

import bl_frozen
import consumers as frozen_consumers     # stage A's pooled inputs: for comparison only
import dslx
import blocks_c as B
import build_bl as BB
import episode_bl as E
import gen_bl
import guards_bl as G
import presets_bl as P
import search_bl as S

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = dslx.load()
RIGHT_L = ("L", "first", ("L", "first", ("P", "x0")))            # color over the library
RIGHT_C = ("L", "c_item0", ("L", "c_first", ("P", "x0")))        # color over C: the source lowered by hand (the development witness)
WRONG_L = ("L", "size", ("P", "x0"))
WRONG_C = ("L", "c_len", ("P", "x0"))


@pytest.fixture(autouse=True)
def size_of_c(monkeypatch):
    monkeypatch.setattr(P, "SIZE_C", 4)                              # the tests of this file are written for a size limit of 4


# ---------------------------------------------------------------- start-up and presets
def test_imports_verified_and_tamper_refused(tmp_path):
    assert bl_frozen.verify_imports() == bl_frozen.HASHES and len(bl_frozen.HASHES) == 15
    for rel in bl_frozen.IMPORTED + bl_frozen.DATA:
        d = tmp_path / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(bl_frozen.ROOT, rel), d)
    assert bl_frozen.verify_imports(root=str(tmp_path)) == bl_frozen.HASHES
    for rel in (bl_frozen.IMPORTED[3], bl_frozen.IMPORTED[-3], bl_frozen.DATA[0]):       # a stage A module, the enumerator, the library text
        original = (tmp_path / rel).read_bytes()
        with open(tmp_path / rel, "ab") as f:
            f.write(b"\n")
        with pytest.raises(SystemExit):
            bl_frozen.verify_imports(root=str(tmp_path))
        (tmp_path / rel).write_bytes(original)
    os.remove(tmp_path / bl_frozen.IMPORTED[0])
    with pytest.raises(SystemExit):
        bl_frozen.verify_imports(root=str(tmp_path))
    with pytest.raises(SystemExit):
        bl_frozen.verify_imports(names=("experiments/core_operations_20261113/run_all.py",))        # not listed in stage A's freeze
    import sys
    assert sys.path.index(bl_frozen.STAGE_A_DIR) > sys.path.index(HERE) and sys.path.index(bl_frozen.CORE_DIR) > sys.path.index(HERE)


def test_strata_and_control_names_equal_a_recomputation_from_the_census():
    path = os.path.join(HERE, P.CENSUS_FILE)
    raw = open(path, "rb").read()
    assert hashlib.sha256(raw).hexdigest() == P.CENSUS_SHA256
    per = json.loads(raw)["per_operation"]
    roster = E.roster_all()
    assert len(roster) == 145 and set(P.DEV_ROSTER) <= set(roster) and len(P.DEV_ROSTER) == 20
    short = tuple(n for n in roster if per[n]["nodes"] <= P.SHORT_MAX_NODES)
    first_half = tuple(n for n in roster if P.SHORT_MAX_NODES < per[n]["nodes"] <= P.LONGER_SPLIT_NODES)
    second_half = tuple(n for n in roster if per[n]["nodes"] > P.LONGER_SPLIT_NODES)
    assert short == P.STRATUM_SHORT and first_half == P.STRATUM_LONGER_7_TO_15 and second_half == P.STRATUM_LONGER_OVER_15
    assert P.STRATUM_LONGER == first_half + second_half and set(short) | set(P.STRATUM_LONGER) == set(roster)
    outside = lambda names: [n for n in names if n not in P.DEV_ROSTER]         # noqa: E731
    assert (len(outside(short)), len(outside(first_half)), len(outside(second_half))) == (35, 35, 55)
    plain = [n for n in roster if per[n]["one_return_expression"] and per[n]["library_calls"] == 0 and per[n]["lambdas"] == 0
             and per[n]["comprehensions"] == 0 and per[n]["nodes"] <= P.SHORT_MAX_NODES]
    assert tuple(outside(plain)) == P.CONTROL_NAMES and len(P.CONTROL_NAMES) == 28 and [n for n in plain if n in P.DEV_ROSTER] == [P.DEV_CONTROL]
    assert all(P.stratum_of(n) == "short" for n in P.CONTROL_NAMES) and P.stratum_of("rot180") == "longer" and P.half_of("rot180") == "7_to_15"
    assert P.stratum_of("not an operation") is None and P.half_of("color") is None and P.half_of("objects") == "over_15"


def test_presets_are_the_declared_ones():
    assert (P.N_GEN, P.FIT9, P.FIT36, P.FINAL) == (66, (0, 9), (0, 36), (36, 66)) and P.SEQ_TAG == "bl1-seq"
    assert (P.ALLOWANCE, P.MAX_BANK, P.MAX_FN, P.ARITY_RULE) == (60.0, 1_500_000, 16_000, True)
    assert (P.FINAL_GUARD_S, P.MIN_FINAL_POOL, P.SIZE_C_CANDIDATES) == (30.0, 30, (4, 5, 6)) and P.MEMORY_CEILING_BYTES == 32 * 2 ** 30
    assert P.ADDRESS_SPACE_MARGIN_BYTES == 2 ** 30
    assert [(s[0], s[1], s[2]) for s in P.SEARCHES] == [("L4-9", "L", "fit9"), ("LC4-9", "LC", "fit9"), ("L4-36", "L", "fit36"),
                                                         ("L5-36", "L", "fit36"), ("LC4-36", "LC", "fit36"), ("C-36", "C", "fit36")]
    assert [P.size_limit(n) for n in P.SEARCH_NAMES] == [4, 4, 4, 5, 4, 4]
    assert P.SYSTEMS == {"library_only": ("L4-36", "L5-36"), "smaller_blocks": ("LC4-36", "C-36")} and P.SYSTEM_ALLOCATION_S == 120.0
    src = open(os.path.join(HERE, "presets_bl.py")).read()
    assert "\nSIZE_C = 4 " in src and "pilot_s.json by the 80% rule" in src       # the literal of the presets, with where it comes from


def test_the_combination_budget_is_off_or_a_positive_whole_number(monkeypatch):
    assert P.MAX_COMBINATIONS == 1_900_000 == P.combination_budget()          # on, as decided (N_RECORD.json)
    for bad in (0, -3, 2.5, True, "100000"):
        monkeypatch.setattr(P, "MAX_COMBINATIONS", bad)
        with pytest.raises(RuntimeError):
            P.combination_budget()
    monkeypatch.setattr(P, "MAX_COMBINATIONS", 250000)
    assert P.combination_budget() == 250000


def test_the_size_limit_of_c_must_be_set(monkeypatch):
    monkeypatch.setattr(P, "SIZE_C", None)
    with pytest.raises(RuntimeError):
        P.size_limit("C-36")
    monkeypatch.setattr(P, "SIZE_C", 7)
    with pytest.raises(RuntimeError):
        P.size_limit("C-36")
    assert P.size_limit("L5-36") == 5


# ---------------------------------------------------------------- pooled inputs: the local copies give what stage A's give
def test_pooled_inputs_are_those_of_the_frozen_helpers():
    ex1, pl1 = E.pools()
    ex2, pl2 = frozen_consumers.pools()
    assert list(ex1) == list(ex2) == E.roster_all() == frozen_consumers.roster_all() and list(pl1) == list(pl2)
    for ann in pl1:
        assert [E.input_key(v) for v in pl1[ann]] == [dslx.canon(v) for v in pl2[ann]]
    for name in ("color", "mapply", "rot180"):
        own = gen_bl.gen_examples(name, n_total=P.N_GEN)["examples"][:36]
        keys = {E.input_key(tuple(a)) for a, _ in own}
        mine = E.pooled_sequence(name, own, keys, 200, P.SEQ_TAG)
        theirs = frozen_consumers.pooled_sequence(name, own, {dslx.canon(tuple(a)) for a, _ in own}, 200, tag=P.SEQ_TAG)
        assert [E.input_key(t) for t in mine] == [dslx.canon(t) for t in theirs] and len(mine) > 50
        assert not set(E.input_key(t) for t in mine) & keys
        other = E.pooled_sequence(name, own, keys, 200, "seq")       # stage A's tag gives another sequence
        assert [E.input_key(t) for t in other] != [E.input_key(t) for t in mine]


def test_input_keys_are_canonical_text_without_calling_it_on_a_function(monkeypatch):
    plain = [True, 3, (), (1, (2, 3)), frozenset({(1, 2), (3, 4)}), ((1,), frozenset())]
    assert [E.input_key(v) for v in plain] == [dslx.canon(v) for v in plain]
    with_functions = (len, (1, abs), frozenset({(2, len)}))
    want = dslx.canon(with_functions)                                # the frozen keys write a function by its name
    real = dslx.canon

    def canon_never_sees_a_function(v):
        assert not E.has_callable(v)
        return real(v)
    monkeypatch.setattr(dslx, "canon", canon_never_sees_a_function)
    assert E.input_key(with_functions) == want
    assert E.short((1, len)) == "<a value that is or holds a function>" and E.show_args((len, 3)) == ["function len", "i3"]


# ---------------------------------------------------------------- unsupported values
def test_a_value_that_is_or_holds_a_function():
    for v in (len, (1, len), frozenset({(1, (abs,))}), ((), (frozenset({len}),))):
        assert E.has_callable(v)
    for v in (5, True, (), ((1, 2), frozenset({3}))):
        assert not E.has_callable(v) and not E.holds_function(v)
    assert not E.holds_function(len) and E.holds_function((len,))    # an argument that IS a function is allowed
    assert E.output_kind(5) == "usable" and E.output_kind((1, len)) == "unsupported" and E.output_kind(len) == "unsupported"
    assert E.output_kind(None) == "unsupported" and E.output_kind(tuple(range(3001))) == "too_large" and E.output_kind(tuple(range(3000))) == "usable"


def test_a_target_whose_container_argument_holds_functions_is_excluded():
    v = E.setup_only("rapply")
    assert v["decision"]["status"] == "excluded" and v["decision"]["reason_kind"] == "unsupported_values" and v["opened_roles"] == []
    assert v["counts"]["unusable_generator_examples"] == dict(container_argument_holds_a_function=66, output_is_or_holds_a_function=0)
    assert "66 of 66" in v["counts"]["reason"] and v["counts"]["pooled_sequence"] is None


def test_records_count_unusable_examples_without_handing_out_values():
    good = [((1, (2, 3)), 5)] * 60
    rec = E.Records(good + [(((len, 1),), 5)] * 2 + [((1,), (2, len))] * 3 + [((len,), 3)], {})
    assert rec.unusable() == dict(container_argument_holds_a_function=2, output_is_or_holds_a_function=3)
    assert E.Records(good + [((len,), 3)], {}).unusable() == dict(container_argument_holds_a_function=0, output_is_or_holds_a_function=0)


# ---------------------------------------------------------------- roles
def test_roles_open_only_in_their_order():
    examples = [((i,), i) for i in range(66)]
    sealed = {}
    rec = E.Records(examples, sealed)
    for role in ("fit9", "fit36", "final", "pool_source"):
        with pytest.raises(E.OrderError):
            rec.get(role)                                            # nothing is readable before it is opened
    for role in ("fit9", "fit36", "final"):
        with pytest.raises(E.OrderError):
            rec.open(role)
    rec.open("pool_source")
    assert rec.get("pool_source") == examples[:36] and rec.opened == ["pool_source"]
    sealed["setup_record"] = "x"
    rec.open("fit9")
    assert rec.get("fit9") == examples[:9]
    with pytest.raises(E.OrderError):
        rec.open("fit36")                                            # the nine-example first fits are not sealed
    sealed["first_fits_9"] = "x"
    rec.open("fit36")
    assert rec.get("fit36") == examples[:36]
    sealed["first_fits_36"] = "x"
    with pytest.raises(E.OrderError):
        rec.open("final")                                            # the selections are not sealed
    with pytest.raises(E.OrderError):
        rec.get("final")
    sealed["selections"] = "x"
    rec.open("final")
    assert rec.get("final") == examples[36:] and len(rec.get("final")) == 30 and rec.opened == ["pool_source", "fit9", "fit36", "final"]
    with pytest.raises(KeyError):
        rec.open("validation")
    assert len(rec.keys()) == 66


@pytest.fixture(scope="module")
def color_setup():
    """The setup view of the development control and the calls that formed it."""
    seen = []
    real = E._stream_usable

    def spy(xfn, argsets, seconds):
        seen.append(list(argsets))
        return real(xfn, argsets, seconds)
    E._stream_usable = spy
    try:
        ep = E.Episode("color")
        excluded = ep.setup()
    finally:
        E._stream_usable = real
    return ep, excluded, seen


def test_setup_decides_eligibility_and_reads_no_final_data(color_setup):
    ep, excluded, seen = color_setup
    assert excluded is None and ep.rec.opened == ["pool_source"] and ep.F is None and set(ep.sealed) == {"setup_record"}
    assert len(seen) == 1 and seen[0] == ep.slice_usability           # the true operation ran over the usability slice only
    final_keys = {E.input_key(t) for t in ep.slice_final}
    assert final_keys and not final_keys & {E.input_key(t) for t in ep.slice_usability}        # the two slices are apart
    assert not final_keys & ep.rec.keys() and not {E.input_key(t) for t in ep.slice_usability} & ep.rec.keys()
    v = ep.setup_view()
    d, c = v["decision"], v["counts"]
    assert d["status"] == "eligible" and d["dev"] is True and d["stratum"] == "short" and d["development_control"] is True and d["control"] is False
    assert d["hidden"] == sorted(LIB["fam_of"]["color"]) and d["retained_present"] == ["compose", "chain", "matcher", "rbind", "lbind", "power", "fork"]
    assert d["hidden_unreachable"] == {"L": True, "C": True, "LC": True} and d["usability_guard_timeout"] is False
    assert c["usability"]["usable"] >= P.MIN_FINAL_POOL and c["usability"]["draws"] == len(ep.slice_usability) == c["pooled_sequence"]["usability_slice"]
    assert c["pooled_sequence"]["tag"] == "bl1-seq" and c["generator"]["examples"] == 66
    for step in (ep.step_thirty_six, ep.step_select, ep.open_final, ep.step_final, ep.step_witness, ep.fin):
        with pytest.raises(E.OrderError):
            step()
    with pytest.raises(E.OrderError):
        ep.rec.get("final")
    with pytest.raises(E.OrderError):
        ep.seal("setup_record", {})                                  # a seal is written once


def test_setup_only_opens_no_fit_role_and_no_final_role(monkeypatch):
    def no(*a, **k):
        raise AssertionError("a search or the final panel was touched by the setup-only pass")
    for name in ("open_final", "fin", "step_nine", "step_thirty_six", "step_select", "step_final", "step_witness", "run_search"):
        monkeypatch.setattr(E.Episode, name, no)
    monkeypatch.setattr(S, "search", no)
    monkeypatch.setattr(E, "load_witness_manifest", no)
    v = E.setup_only("color")
    assert v["opened_roles"] == ["pool_source"] and v["decision"]["status"] == "eligible" and v["target"] == "color"
    assert [m["after"] for m in v["memory"]] == ["setup: generator", "setup: generator examples", "setup: pooled sequence",
                                                "setup: usability slice", "setup: hiding"]
    assert all(m["address_space_peak_kb"] > 0 and m["resident_peak_kb"] > 0 for m in v["memory"])


def test_too_few_usable_pooled_inputs_excludes(monkeypatch):
    real = E._stream_usable

    def short_stream(xfn, argsets, seconds):
        out, info = real(xfn, argsets[:29], seconds)
        return out, dict(info, draws=len(argsets))
    monkeypatch.setattr(E, "_stream_usable", short_stream)
    v = E.setup_only("color")
    assert v["decision"]["status"] == "excluded" and v["decision"]["reason_kind"] == "too_few_usable_pooled_inputs"
    assert "need 30" in v["counts"]["reason"] and v["counts"]["usability"]["usable"] == 29


def test_a_reachable_hidden_name_stops_the_setup(monkeypatch):
    monkeypatch.setattr(BB, "retained_present", lambda hidden: ["compose"])
    real = BB.build

    def leaky(block_set, hidden, examples, **kw):
        ops, leaves, Y, op_ns, leaf_ns, consts = real(block_set, hidden, examples, **kw)
        return ops, leaves, Y, dict(op_ns, alias=dslx.full_ns()["color"]), leaf_ns, consts
    monkeypatch.setattr(BB, "build", leaky)
    with pytest.raises(RuntimeError):
        E.setup_only("color")


# ---------------------------------------------------------------- the guard itself
def test_a_guard_refuses_a_duration_that_is_not_a_finite_positive_number():
    before = (signal.getsignal(signal.SIGVTALRM), signal.getitimer(signal.ITIMER_VIRTUAL))
    for bad in (0, -1, 0.0, float("inf"), float("nan"), -float("inf"), True, "3", None, 10 ** 400, [1]):
        with pytest.raises(ValueError):
            G.guard(bad)
        assert (signal.getsignal(signal.SIGVTALRM), signal.getitimer(signal.ITIMER_VIRTUAL)) == before and not G.active()
    assert G.guard(1).seconds == 1.0 and G.guard(0.25).seconds == 0.25


def test_a_guard_restores_the_handler_and_the_timer_on_every_exit():
    def marker(*a):
        raise AssertionError("the earlier handler ran")
    old = signal.signal(signal.SIGVTALRM, marker)
    try:
        for leave in (None, ValueError("ordinary"), G.GuardTimeout(), G.ResourceStop("memory"), KeyboardInterrupt()):
            try:
                with G.guard(50.0):
                    assert G.active() and signal.getsignal(signal.SIGVTALRM) is G._on_timer and signal.getitimer(signal.ITIMER_VIRTUAL)[0] > 0
                    if leave is not None:
                        raise leave
            except (ValueError, G.GuardTimeout, G.ResourceStop, KeyboardInterrupt) as e:
                assert e is leave
            assert not G.active() and signal.getsignal(signal.SIGVTALRM) is marker and signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0)
    finally:
        signal.signal(signal.SIGVTALRM, old)
    assert not issubclass(G.GuardTimeout, Exception) and not issubclass(G.ResourceStop, Exception) and not issubclass(G.NearCeiling, Exception)


def test_guards_do_not_nest_and_a_nested_call_never_touches_an_active_deadline():
    with G.guard(50.0):
        handler, left = signal.getsignal(signal.SIGVTALRM), signal.getitimer(signal.ITIMER_VIRTUAL)[0]
        with pytest.raises(RuntimeError):
            with G.guard(1.0):
                raise AssertionError("a second guard started")
        with pytest.raises(RuntimeError):
            G.assert_inactive()                                      # the enumerator and the generator must not run under a guard
        now = signal.getitimer(signal.ITIMER_VIRTUAL)[0]
        assert G.active() and signal.getsignal(signal.SIGVTALRM) is handler and 0 < now <= left      # not reset, not disarmed
    assert not G.active() and signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0)
    G.assert_inactive()
    # a guard does not start while another timer of the same kind is armed (as inside the enumerator or the generator)
    old = signal.signal(signal.SIGVTALRM, lambda *a: None)
    signal.setitimer(signal.ITIMER_VIRTUAL, 100.0)
    try:
        with pytest.raises(RuntimeError):
            with G.guard(1.0):
                raise AssertionError("a guard started over another timer")
        assert signal.getitimer(signal.ITIMER_VIRTUAL)[0] > 90 and not G.active()
    finally:
        signal.setitimer(signal.ITIMER_VIRTUAL, 0)
        signal.signal(signal.SIGVTALRM, old)


def test_the_enumerator_and_the_generator_refuse_to_be_called_under_a_guard(color_setup):
    ep = E.Episode("color")
    with G.guard(50.0):
        with pytest.raises(RuntimeError):
            ep.setup()                                               # the generator is not started under an active guard
    assert not G.active()


def test_call_checked_translates_a_memory_failure_and_nothing_else():
    def hungry(*a, **k):
        raise MemoryError()

    def wrong(*a, **k):
        raise KeyError("k")
    assert G.call_checked(lambda a, b=2: (a, b), 1, b=3) == (1, 3)
    with pytest.raises(G.ResourceStop):
        G.call_checked(hungry, 1)
    with pytest.raises(KeyError):
        G.call_checked(wrong)
    with pytest.raises(G.GuardTimeout):
        G.call_checked(lambda: (_ for _ in ()).throw(G.GuardTimeout()))


def test_the_address_space_reading_and_its_margin(monkeypatch):
    peak, rss = G.address_space_peak_kb(), G.resident_peak_kb()
    assert isinstance(peak, int) and peak > 1000 and isinstance(rss, int) and 1000 < rss <= peak
    ceiling, margin = P.MEMORY_CEILING_BYTES, P.ADDRESS_SPACE_MARGIN_BYTES
    assert G.near_ceiling(None, ceiling, margin) is True             # a reading that cannot be made is a failed check
    assert G.near_ceiling((ceiling - margin) // 1024, ceiling, margin) is True and G.near_ceiling((ceiling - margin) // 1024 - 1, ceiling, margin) is False
    assert G.near_ceiling(peak, ceiling, margin) is False
    real_open = open

    def unreadable(path, *a, **k):
        if path == "/proc/self/status":
            raise OSError("no such file")
        return real_open(path, *a, **k)
    monkeypatch.setattr("builtins.open", unreadable)
    assert G.address_space_peak_kb() is None
    e = G.NearCeiling("search L4-36", 123)
    assert e.unit == "search L4-36" and e.peak_kb == 123 and "near the ceiling" in str(e)


# ---------------------------------------------------------------- a batch of checks under one guard (fault fixtures)
ARGS = [(i,) for i in range(5)]
XOUT = [i * 10 for i in range(5)]


def counted(body):
    """An invented candidate of one argument; body(call number, argument) decides what it does."""
    calls = []

    def f(a):
        calls.append(a)
        return body(len(calls), a)
    return f, calls


def test_a_right_candidate_and_an_ordinary_error_as_the_control():
    fn, calls = counted(lambda n, a: a * 10)
    c = E.check_batch(fn, ARGS, XOUT, 30.0)
    assert c["right"] is True and c["agree"] == c["evaluated"] == c["n"] == 5 and c["counterexample"] is None and c["oks"] == [True] * 5

    def body(n, a):
        if n == 3:
            raise ValueError("an ordinary error")
        return a * 10
    fn, calls = counted(body)
    c = E.check_batch(fn, ARGS, XOUT, 30.0)
    assert c["oks"] == [True, True, False, True, True] and c["errors"] == 1 and len(calls) == 5 and c["right"] is False
    assert c["counterexample"]["index"] == 2 and c["counterexample"]["note"] == "error: ValueError" and c["guard_timeout"] is False
    assert "guard_timeout_after_this" not in c["counterexample"] and c["counterexample"]["got"] is None
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and not G.active()


def test_a_timeout_inside_the_candidate_ends_the_batch_and_is_marked():
    def body(n, a):
        if n == 3:
            raise G.GuardTimeout()
        return a * 10
    fn, calls = counted(body)
    c = E.check_batch(fn, ARGS, XOUT, 30.0)
    assert c["oks"] == [True, True] and c["evaluated"] == 2 and c["counterexample"] == dict(index=-1, note="guard timeout")
    assert c["right"] is False and c["guard_timeout"] is True and c["errors"] == 0 and len(calls) == 3      # nothing ran after the timeout
    assert not G.active() and signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0)


def test_a_counterexample_before_a_timeout_stays_the_counterexample():
    def body(n, a):
        if n == 2:
            return -1                                                # a wrong value: a real counterexample at index 1
        if n == 4:
            raise G.GuardTimeout()
        return a * 10
    fn, calls = counted(body)
    c = E.check_batch(fn, ARGS, XOUT, 30.0)
    assert c["oks"] == [True, False, True] and len(calls) == 4 and c["evaluated"] == 3 and c["right"] is False
    assert c["counterexample"]["index"] == 1 and c["counterexample"]["note"] == "different value" and c["counterexample"]["guard_timeout_after_this"] is True
    assert c["counterexample"]["want"] == "i10" and c["counterexample"]["got"] == "i-1" and c["counterexample"]["args"] == ["i1"]
    assert c["agree"] == 2 and c["n"] == 5                           # an input that was not evaluated is not a counterexample


def test_a_timeout_inside_the_comparison_is_a_timeout_too(monkeypatch):
    n, real = [0], E.same

    def same(x, y):
        n[0] += 1
        if n[0] == 2:
            raise G.GuardTimeout()
        return real(x, y)
    monkeypatch.setattr(E, "same", same)
    c = E.check_batch(lambda a: a * 10, ARGS, XOUT, 30.0)
    assert c["oks"] == [True] and c["counterexample"] == dict(index=-1, note="guard timeout") and c["errors"] == 0 and n[0] == 2


def test_a_timeout_outside_the_inner_handler_is_a_timeout_too(monkeypatch):
    def inputs():
        yield (0,)
        yield (1,)
        raise G.GuardTimeout()                                       # delivered while the next input is taken: no handler of errors around it

    class Stream(list):
        def __iter__(self):
            return inputs()
    c = E.check_batch(lambda a: a * 10, Stream(ARGS), XOUT, 30.0)
    assert c["oks"] == [True, True] and c["counterexample"] == dict(index=-1, note="guard timeout") and c["guard_timeout"] is True
    # while the counterexample is being written down: it exists already and stays
    monkeypatch.setattr(E, "show_args", lambda a, n=160: (_ for _ in ()).throw(G.GuardTimeout()))
    c = E.check_batch(lambda a: -1, ARGS, XOUT, 30.0)
    assert c["counterexample"] == dict(index=0, note="different value", guard_timeout_after_this=True) and c["oks"] == [False]


def test_the_real_timer_delivered_inside_a_spinning_candidate():
    before = signal.getsignal(signal.SIGVTALRM)
    calls = []

    def slow(a):
        calls.append(a)
        if len(calls) == 2:
            t = time.process_time()
            while time.process_time() - t < 20:                      # spins until the timer interrupts it
                pass
        return a * 10
    t0 = time.process_time()
    c = E.check_batch(slow, ARGS, XOUT, 0.2)
    assert c["counterexample"] == dict(index=-1, note="guard timeout") and c["oks"] == [True] and c["errors"] == 0 and len(calls) == 2
    assert time.process_time() - t0 < 5.0
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and signal.getsignal(signal.SIGVTALRM) == before and not G.active()


def test_a_memory_failure_in_a_check_is_a_resource_stop_never_a_wrong_candidate(monkeypatch):
    def hungry(a):
        raise MemoryError()
    with pytest.raises(G.ResourceStop):
        E.check_batch(hungry, ARGS, XOUT, 30.0)
    assert not G.active() and signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0)
    with pytest.raises(G.ResourceStop):
        E.check_batch(lambda a: G.call_checked(hungry, a), ARGS, XOUT, 30.0)
    real = dslx.canon
    monkeypatch.setattr(dslx, "canon", lambda v: (_ for _ in ()).throw(MemoryError()))
    with pytest.raises(G.ResourceStop):
        E.check_batch(lambda a: a * 10, ARGS, XOUT, 30.0)            # canonical text runs out of memory
    monkeypatch.setattr(dslx, "canon", real)
    monkeypatch.setattr(E, "has_callable", lambda v: (_ for _ in ()).throw(MemoryError()))
    with pytest.raises(G.ResourceStop):
        E.check_batch(lambda a: a * 10, ARGS, XOUT, 30.0)
    monkeypatch.undo()
    monkeypatch.setattr(E, "show_args", lambda a, n=160: (_ for _ in ()).throw(MemoryError()))
    with pytest.raises(G.ResourceStop):
        E.check_batch(lambda a: -1, ARGS, XOUT, 30.0)                # while a counterexample is written down


def test_a_value_that_holds_a_function_is_rejected_before_any_canonical_text(monkeypatch):
    """An invented target and candidates: the candidate's value is, or holds, a function. It is unsupported and
    wrong there, counted, and canonical text is never computed for it."""
    real = dslx.canon

    def canon_never_sees_a_function(v):
        assert not E.has_callable(v), "canonical text was asked for a value that holds a function"
        return real(v)
    monkeypatch.setattr(dslx, "canon", canon_never_sees_a_function)
    target = [(i, i) for i in range(5)]
    for candidate in (lambda a: len, lambda a: (a, len), lambda a: (a, (a, frozenset({abs}))), lambda a: (a, a) if a < 3 else (a, len)):
        c = E.check_batch(candidate, ARGS, target, 30.0)
        assert c["right"] is False and c["unsupported"] >= 2 and c["errors"] == 0 and c["agree"] == 5 - c["unsupported"]
        assert c["counterexample"]["note"].startswith("unsupported value") and c["counterexample"]["got"] is None
    c = E.check_batch(lambda a: (a, a), ARGS, target, 30.0)
    assert c["right"] is True and c["unsupported"] == 0


def test_order_of_sets_is_read_apart_and_does_not_change_right():
    a, b = frozenset({1, 9, 17}), frozenset({(1, 2), (3, 4)})
    reordered = frozenset(sorted(a, reverse=True))
    xouts = [a, b, frozenset({5}), (1, 2)]
    args = [(0,), (1,), (2,), (3,)]
    same_objects = E.check_batch(lambda i: xouts[i], args, xouts, 30.0)
    assert same_objects["right"] is True and same_objects["order_of_sets"] == dict(same_order=2, of=2)      # sets of one element and tuples are not counted
    other = [reordered, b, frozenset({5}), (1, 2)]
    c = E.check_batch(lambda i: other[i], args, xouts, 30.0)
    assert c["right"] is True and c["order_of_sets"]["of"] == 2 and c["order_of_sets"]["same_order"] == (2 if list(reordered) == list(a) else 1)


# ---------------------------------------------------------------- the true operation over pooled tuples, under one guard
def test_the_stream_counts_what_it_discards_and_keeps_order():
    def x(a):
        if a == 3:
            raise ValueError("the operation raises here")
        if a == 5:
            return (a, len)
        if a == 7:
            return tuple(range(3001))
        return a * 2
    out, info = E.stream_usable(x, [(i,) for i in range(10)], 20.0)
    assert [a for a, _ in out] == [(0,), (1,), (2,), (4,), (6,), (8,), (9,)] and [y for _, y in out] == [0, 2, 4, 8, 12, 16, 18]
    assert info == dict(draws=10, evaluated=10, usable=7, raised=1, unsupported=1, too_large=1, guard_timeout=False)


def test_a_timeout_or_a_memory_failure_inside_the_true_operation():
    def x(a):
        if a == 4:
            raise G.GuardTimeout()
        return a
    out, info = E.stream_usable(x, [(i,) for i in range(10)], 20.0)
    assert len(out) == 4 and info["guard_timeout"] is True and info["evaluated"] == 4 and info["usable"] == 4 and info["draws"] == 10
    assert not G.active() and signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0)

    def spins(a):
        t = time.process_time()
        while a == 2 and time.process_time() - t < 20:
            pass
        return a
    out, info = E.stream_usable(spins, [(i,) for i in range(10)], 0.2)                   # the real timer
    assert [a for a, _ in out] == [(0,), (1,)] and info["guard_timeout"] is True and info["evaluated"] == 2

    def hungry(a):
        if a == 1:
            raise MemoryError()
        return a
    with pytest.raises(G.ResourceStop):
        E.stream_usable(hungry, [(i,) for i in range(10)], 20.0)                         # never an input on which X "raises"
    assert not G.active() and signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0)


# ---------------------------------------------------------------- how a search ended
def test_stop_classes_keep_every_ending_apart():
    sc = E.stop_class
    assert sc("found", True) == "found" and sc("size_exhausted", False) == "size_limit_completed"
    assert sc("size_exhausted_function_cap", False) == "size_limit_completed_function_cap" and sc("size_exhausted", False, True) == "size_limit_completed_function_cap"
    assert sc("budget_cpu", False) == "allowance_used_up" and sc("budget_bank", False) == "bank_cap_reached" and sc("hard_timeout", False) == "hard_stop"
    # with the combination budget on, processor time is a safety limit: its stop is an infrastructure stop
    assert sc("budget_cpu", False, combination_mode=True) == "time_safety_limit" and E.coverage("time_safety_limit") is None
    assert sc("hard_timeout", False, combination_mode=True) == "hard_stop" and sc("budget_ticks", False, combination_mode=True) == "combination_budget_used_up"
    assert sc("budget_ticks", False) == "combination_budget_used_up" and E.coverage("combination_budget_used_up") == "bounded"
    for infra in E.INFRASTRUCTURE:
        assert sc(infra, False) == infra and sc(infra, True) == infra and E.coverage(infra) is None
    assert sc("something else", False) == "infrastructure_failure"
    assert E.coverage("size_limit_completed") == "exhaustive" and E.coverage("found") is None
    assert [E.coverage(c) for c in E.BOUNDED] == ["bounded"] * 4
    assert set(E.BOUNDED) == {"size_limit_completed_function_cap", "allowance_used_up", "bank_cap_reached", "combination_budget_used_up"}
    assert set(E.INFRASTRUCTURE) == {"hard_stop", "memory_failure", "address_space_near_ceiling", "infrastructure_failure", "time_safety_limit"}
    import summarize_bl
    assert set(summarize_bl.INFRASTRUCTURE) == set(E.INFRASTRUCTURE)
    assert set(E.STOP_CLASSES) == {"found", "size_limit_completed"} | set(E.BOUNDED) | set(E.INFRASTRUCTURE)


# ---------------------------------------------------------------- controlled searches: the selection rule and the record
def fake_searches(table):
    """Stands in for the six searches. table: {search name: a tree (a fit), "none", or an infrastructure class}."""
    def run_search(self, name, block_set, role, size_limit):
        examples = self.rec.get(role)
        kind = table.get(name, "none")
        a = dict(block_set=block_set, role=role, examples=len(examples), size_limit=size_limit, cpu_s=0.01, bank=10, level_completed=size_limit,
                 function_cap_reached=False, error=None, expr=None, size=None, refused_by_the_wrappers=BB.new_counts(),
                 function_making=dict(by_operation={}, admitted=0, cap_reached_at=None, first_refused_by_cap=None),
                 address_space_peak_kb=G.address_space_peak_kb(), resident_peak_kb=G.resident_peak_kb())
        if isinstance(kind, tuple):
            _, _, _, op_ns, leaf_ns, consts = BB.build(block_set, self.hidden, examples)
            self.fit[name] = dict(tree=kind, op_ns=op_ns, leaf_ns=leaf_ns, consts=consts, eval_counts=BB.new_counts())
            a.update(expr=S.render(kind), size=3, stop="found")
        else:
            a["stop"] = "size_exhausted" if kind == "none" else kind
        a["stop_class"] = E.stop_class(a["stop"], isinstance(kind, tuple))
        a["incomplete"] = a["stop_class"] in E.INFRASTRUCTURE
        a["coverage"], a["fit"] = E.coverage(a["stop_class"]), a["stop_class"] == "found"
        if a["incomplete"]:
            self.incomplete.append("search %s: %s" % (name, a["stop_class"]))
        return a
    return run_search


def fake_run(monkeypatch, tmp_path, table, name="color"):
    monkeypatch.setattr(E.Episode, "run_search", fake_searches(table))
    out = str(tmp_path / ("out_%d" % len(os.listdir(str(tmp_path)))))
    return out, E.run_target(name, out)


def test_selection_first_stage_then_second_then_nothing(monkeypatch, tmp_path):
    out, r = fake_run(monkeypatch, tmp_path, {"L4-36": RIGHT_L, "L5-36": WRONG_L, "C-36": RIGHT_C})
    lo, sb = r["selection"]["library_only"], r["selection"]["smaller_blocks"]
    assert r["status"] == "done"
    assert (lo["stage"], lo["search"], lo["expr"], lo["rebuilt"], lo["determined"]) == (1, "L4-36", "first(first(x0))", True, True)
    assert (sb["stage"], sb["search"], sb["expr"], sb["rebuilt"]) == (2, "C-36", "c_item0(c_first(x0))", True)
    assert "found no fit" in sb["reason"] and "found a fit" in lo["reason"]
    assert r["searches"]["L5-36"]["first_fit"] == "wrong" and r["searches"]["LC4-36"]["first_fit"] == "none" and r["searches"]["L4-9"]["first_fit"] == "none"
    out, r = fake_run(monkeypatch, tmp_path, {})
    for system in P.SYSTEM_NAMES:
        s = r["selection"][system]
        assert (s["expr"], s["stage"], s["search"], s["rebuilt"], s["determined"], s["oracle_union"]) == (None, None, None, False, True, False)
        assert "neither stage" in s["reason"]
    assert r["status"] == "done" and all(a["first_fit"] == "none" and a["final"] is None for a in r["searches"].values())


def test_a_first_stage_fit_that_is_wrong_on_the_final_panel_is_still_the_systems_answer(monkeypatch, tmp_path):
    """Selected on fit alone: the final panel never changes a selection, and no other stage or expression replaces
    a selected expression that turns out wrong, even when the second stage's fit would have been right."""
    out, r = fake_run(monkeypatch, tmp_path, {"L4-36": WRONG_L, "L5-36": RIGHT_L, "LC4-36": WRONG_C, "C-36": RIGHT_C})
    for system, first, second in (("library_only", "L4-36", "L5-36"), ("smaller_blocks", "LC4-36", "C-36")):
        s = r["selection"][system]
        assert (s["stage"], s["search"], s["rebuilt"]) == (1, first, False) and s["wrong_only_by_guard_timeout"] is False
        assert s["oracle_union"] is True                             # candidate-set coverage, never the system's result
        assert r["searches"][first]["first_fit"] == "wrong" and r["searches"][second]["first_fit"] == "right"
        assert r["searches"][first]["final"]["counterexample"]["index"] >= 0 and r["searches"][first]["final"]["right"] is False
    assert r["status"] == "done"
    names = [json.loads(x)["name"] for x in open(os.path.join(out, "journal", "color.jsonl")) if '"event": "seal"' in x]
    assert names == ["setup_record", "first_fits_9", "first_fits_36", "selections", "final_set"] == list(r["seals"])
    assert r["opened_roles"] == ["pool_source", "fit9", "fit36", "final"]
    fp = r["final_panel"]
    assert fp["generator"] == 30 and fp["pooled"] >= 30 and fp["inputs"] == fp["generator"] + fp["pooled"]
    assert fp["pooled_slice"]["draws"] == fp["pooled"] + fp["pooled_discarded"] + fp["pooled_not_evaluated"]
    final = r["searches"]["L5-36"]["final"]
    assert final["n"] == fp["inputs"] == final["evaluated"] == final["agree"] and final["generator"] == [30, 30] and final["pooled"] == [fp["pooled"]] * 2


def test_the_selection_is_sealed_before_the_final_panel_exists(monkeypatch, tmp_path):
    order = []
    real_seal, real_open = E.Episode.seal, E.Episode.open_final
    monkeypatch.setattr(E.Episode, "seal", lambda self, name, obj: order.append(("seal", name, self.F is None, "final" in self.rec.opened)) or real_seal(self, name, obj))
    monkeypatch.setattr(E.Episode, "open_final", lambda self: order.append(("open_final", dict(self.sealed))) or real_open(self))
    out, r = fake_run(monkeypatch, tmp_path, {"L4-36": RIGHT_L})
    seals = [o for o in order if o[0] == "seal"]
    assert [o[1] for o in seals] == ["setup_record", "first_fits_9", "first_fits_36", "selections", "final_set"]
    assert all(o[2] is True and o[3] is False for o in seals[:4])     # no final panel and no final role before the selections are sealed
    opened = [o for o in order if o[0] == "open_final"]
    assert len(opened) == 1 and "selections" in opened[0][1] and "final_set" not in opened[0][1]


def test_an_infrastructure_stop_in_a_search_is_incomplete_never_none(monkeypatch, tmp_path):
    for infra in ("hard_timeout", "memory_failure", "infrastructure_failure"):
        out, r = fake_run(monkeypatch, tmp_path, {"L4-36": infra, "LC4-36": RIGHT_C, "C-36": infra, "L4-9": infra})
        assert r["status"] == "incomplete" and "search L4-36" in r["reason"]
        lo, sb = r["selection"]["library_only"], r["selection"]["smaller_blocks"]
        assert lo["determined"] is False and lo["rebuilt"] is None and lo["expr"] is None and "infrastructure stop" in lo["reason"]
        assert sb["determined"] is True and sb["stage"] == 1 and sb["rebuilt"] is True and sb["oracle_union"] is None
        assert r["searches"]["L4-36"]["first_fit"] is None and r["searches"]["L4-36"]["incomplete"] is True and r["searches"]["L4-9"]["first_fit"] is None
    out, r = fake_run(monkeypatch, tmp_path, {"L5-36": "hard_timeout", "C-36": "hard_timeout"})
    assert r["status"] == "incomplete" and r["selection"]["library_only"]["determined"] is False and r["selection"]["smaller_blocks"]["rebuilt"] is None
    assert "second" in r["selection"]["library_only"]["reason"]


# ---------------------------------------------------------------- the real search path
def test_each_search_is_built_from_its_own_examples_and_nothing_is_shared(monkeypatch, tmp_path):
    builds, searches = [], []
    real_build, real_search = BB.build, S.search

    def spy_build(block_set, hidden, examples, **kw):
        out = real_build(block_set, hidden, examples, **kw)
        builds.append(dict(block_set=block_set, examples=examples, n=len(examples), ops=out[0], leaves=out[1], Y=out[2], counts=kw.get("counts")))
        return out

    def spy_search(ops, leaves, Y, cpu_budget, max_size, max_fn, max_bank, **kw):
        searches.append(dict(ops=ops, leaves=leaves, Y=Y, allowance=cpu_budget, size=max_size, max_fn=max_fn, max_bank=max_bank, kw=kw))
        return real_search(ops, leaves, Y, cpu_budget, max_size, max_fn, max_bank, **kw)
    monkeypatch.setattr(BB, "build", spy_build)
    monkeypatch.setattr(S, "search", spy_search)
    out = str(tmp_path / "o")
    r = E.run_target("color", out)
    assert r["status"] == "done" and len(searches) == 6
    built = [b for b in builds if b["counts"] is not None]          # the six builds of the six searches (the setup's three have no counters)
    assert [(b["block_set"], b["n"]) for b in built] == [("L", 9), ("LC", 9), ("L", 36), ("L", 36), ("LC", 36), ("C", 36)]
    assert [s["size"] for s in searches] == [4, 4, 4, 5, 4, 4] and {(s["allowance"], s["max_fn"], s["max_bank"]) for s in searches} == {(600.0, 16000, 1500000)}
    assert all(s["kw"] == dict(max_ticks=1_900_000) for s in searches)      # the combination budget reaches all six searches
    for b, s in zip(built, searches):
        assert s["ops"] is b["ops"] and s["leaves"] is b["leaves"] and s["Y"] is b["Y"]
        assert all(len(v) == b["n"] for _, v in s["leaves"]) and len(s["Y"]) == b["n"]
    for key in ("ops", "leaves", "Y", "counts"):
        assert len({id(b[key]) for b in built}) == 6                 # every search has its own operations, leaves, target values and counters
    assert len({id(o[1]) for b in built for o in b["ops"] if o[0] == "compose"}) == sum(1 for b in built)       # and its own wrapped operations
    gen = gen_bl.gen_examples("color", n_total=P.N_GEN)["examples"]
    for b in built[:2]:
        assert [E.input_key(a) for a, _ in b["examples"]] == [E.input_key(a) for a, _ in gen[:9]]              # nine examples: 0 to 8 and nothing else
        assert all(len(v) == 9 for _, v in b["leaves"])
    for b in built[2:]:
        assert [E.input_key(a) for a, _ in b["examples"]] == [E.input_key(a) for a, _ in gen[:36]]
    final_keys = {E.input_key(a) for a, _ in gen[36:]}
    assert not any(E.input_key(a) in final_keys for b in builds for a, _ in b["examples"])                        # no build ever saw a final example
    for name, a in r["searches"].items():
        assert a["fit"] and a["first_fit"] == "right" and a["fit_recheck"] == dict(agree=a["examples"], of=a["examples"], guard_timeout=False)
        assert a["coverage"] is None and a["incomplete"] is False and a["address_space_peak_kb"] > 0 and a["resident_peak_kb"] > 0
        assert set(a["refused_by_the_wrappers"]) == set(BB.REFUSAL_COUNTS) and a["function_making"]["cap_reached_at"] is None
        assert a["function_valued_entries"] == a["function_valued_leaves"] + a["function_making"]["admitted"]
        assert a["allowance"] == 60.0 and a["cpu_budget_s"] == 600.0 and a["max_fn"] == 16000 and a["arity_rule"] is True
        assert a["max_combinations"] == 1_900_000 and 0 < a["ticks"] < 1_900_000     # the budget is on and reached no search here
    assert r["selection"]["library_only"]["rebuilt"] is True and r["selection"]["smaller_blocks"]["rebuilt"] is True
    assert r["cpu"]["searches_s"] > 0 and abs(r["cpu"]["searches_s"] + r["cpu"]["final_checks_s"] + r["cpu"]["other_s"] - r["cpu_s_total"]) < 0.05
    # a record that exists is not run again
    monkeypatch.setattr(S, "search", lambda *a, **k: (_ for _ in ()).throw(AssertionError("searched again")))
    assert E.run_target("color", out)["seals"] == r["seals"]


# ---------------------------------------------------------------- the budget counted in candidate combinations
TIMES = ("cpu_s", "enumerator_cpu_s", "address_space_peak_kb", "resident_peak_kb")
NO_REFUSAL = dict(containers_holding_a_function_refused=0, function_making_refused_by_arity=0, function_results_refused=0,
                  power_of_a_function_without_one_parameter=0)
NO_FUNCTION_MADE = dict(admitted=0, by_operation={}, calls_outside_the_enumerator=0, cap_reached_at=None, first_refused_by_cap=None)
COMMON = dict(role="fit36", examples=36, size_limit=4, allowance=60.0, max_fn=16000, max_bank=1500000, arity_rule=True, expr=None, size=None,
              stop="size_exhausted", stop_class="size_limit_completed", coverage="exhaustive", level_completed=4, function_cap_reached=False,
              fit=False, incomplete=False, error=None, function_making=NO_FUNCTION_MADE)
# mfilter on its 36 fit examples as the development run of 14 November recorded it (dev_out1), before the budget existed
TODAY = {
    "L4-36": dict(COMMON, block_set="L", bank=20191, function_valued_leaves=124, function_valued_entries=124, operations=150, leaves=153,
                  refused_by_the_wrappers=dict(NO_REFUSAL, containers_holding_a_function_refused=1528)),
    "C-36": dict(COMMON, block_set="C", bank=17875, function_valued_leaves=65, function_valued_entries=65, operations=75, leaves=96,
                 refused_by_the_wrappers=dict(NO_REFUSAL)),
}


def searches_of(name, plan):
    """The records of some 36-example searches of one development name (setup first, as the pilot does)."""
    ep = E.Episode(name)
    assert ep.setup() is None
    ep.seal("first_fits_9", dict(test="the nine-example searches are not run here"))
    ep.rec.open("fit36")
    return {label: ep.run_search(label, block_set, "fit36", size) for label, block_set, size in plan}


def test_with_the_budget_off_a_search_record_is_todays_record_and_the_count_besides(monkeypatch):
    monkeypatch.setattr(P, "MAX_COMBINATIONS", None)
    recs = searches_of("mfilter", (("L4-36", "L", 4), ("C-36", "C", 4)))
    for name, a in recs.items():
        new = ("ticks", "max_combinations", "cpu_budget_s", "cpu_budget_is")
        assert set(a) == set(TODAY[name]) | set(TIMES) | set(new), name                            # four new keys and nothing else
        assert {k: v for k, v in a.items() if k not in TIMES + new} == TODAY[name], name
        assert a["max_combinations"] is None and a["cpu_budget_s"] == P.ALLOWANCE == 60.0 and a["cpu_budget_is"] == "the binding allowance"
    assert (recs["L4-36"]["ticks"], recs["C-36"]["ticks"]) == (277147, 222493)       # every combination of four nodes, counted


def test_a_search_stopped_by_the_budget_is_bounded_and_says_how_far_it_went(monkeypatch):
    monkeypatch.setattr(P, "MAX_COMBINATIONS", 30000)
    a = searches_of("mfilter", (("C-36", "C", 4),))["C-36"]
    assert a["stop"] == "budget_ticks" and a["stop_class"] == "combination_budget_used_up" and a["coverage"] == "bounded"
    assert a["ticks"] == 30000 == a["max_combinations"] and a["fit"] is False and a["incomplete"] is False and a["expr"] is None
    assert a["level_completed"] < 4 and 0 < a["bank"] < TODAY["C-36"]["bank"]


BUDGETED = '''import json, sys
sys.path.insert(0, %r)
junk = [bytearray(1000 * (i %% 97 + 1)) for i in range(int(sys.argv[2]))]       # another memory layout from one process to the next
import presets_bl as P
import run_bl
run_bl.set_memory_ceiling()
import episode_bl as E
P.MAX_COMBINATIONS = int(sys.argv[1])
ep = E.Episode("rot180")
assert ep.setup() is None
ep.seal("first_fits_9", dict(test="the nine-example searches are not run here"))
ep.rec.open("fit36")
out = {}
for label, block_set, size in (("L5-36", "L", P.SIZE_L5), ("LC4-36", "LC", P.SIZE_L4)):
    a = ep.run_search(label, block_set, "fit36", size)
    out[label] = {k: a[k] for k in ("expr", "stop", "stop_class", "coverage", "level_completed", "bank", "ticks", "max_combinations",
                                    "function_valued_entries", "refused_by_the_wrappers")}
print("RECORD " + json.dumps(out, sort_keys=True))
'''


def test_two_fresh_processes_give_the_same_record_for_the_same_budget(tmp_path):
    """L5-36 and LC4-36 of a development name, each stopped by a budget of N combinations, in two fresh processes
    with different memory layouts (the second: the system allocator, other allocations first, and address
    randomization off where the machine has setarch): found, level, bank, count and ending are the same, and the
    count is N."""
    n = 120000
    script = tmp_path / "budgeted.py"
    script.write_text(BUDGETED % HERE)
    setarch = shutil.which("setarch")
    runs = (([], {}, "0"), (([setarch, platform.machine(), "-R"] if setarch else []), {"PYTHONMALLOC": "malloc"}, "4000"))
    records = []
    for prefix, more, junk in runs:
        env = dict(os.environ, PYTHONHASHSEED="0", **more)
        r = subprocess.run(prefix + [sys.executable, "-s", "-B", str(script), str(n), junk], env=env, capture_output=True, text=True,
                           cwd=str(tmp_path), timeout=900)
        assert r.returncode == 0, r.stderr[-800:]
        records.append(json.loads([x for x in r.stdout.splitlines() if x.startswith("RECORD ")][0][len("RECORD "):]))
    first, second = records
    assert first == second
    for label in ("L5-36", "LC4-36"):
        a = first[label]
        assert a["stop"] == "budget_ticks" and a["stop_class"] == "combination_budget_used_up" and a["coverage"] == "bounded"
        assert a["ticks"] == n == a["max_combinations"] and a["expr"] is None and a["level_completed"] in (2, 3) and a["bank"] > 1000
    assert first["L5-36"]["bank"] != first["LC4-36"]["bank"]


def run_real(monkeypatch, tmp_path, search):
    monkeypatch.setattr(S, "search", search)
    return E.run_target("color", str(tmp_path / ("o%d" % len(os.listdir(str(tmp_path))))))


def test_a_failure_of_the_enumerator_is_an_infrastructure_stop(monkeypatch, tmp_path):
    def raising(error):
        def search(*a, **k):
            raise error
        return search
    for error, cls in ((MemoryError(), "memory_failure"), (G.ResourceStop("memory failure in operation x"), "memory_failure"),
                       (RuntimeError("broken"), "infrastructure_failure")):
        r = run_real(monkeypatch, tmp_path, raising(error))
        assert r["status"] == "incomplete" and len(r["incomplete_because"]) == 6
        for a in r["searches"].values():
            assert a["stop_class"] == cls and a["incomplete"] is True and a["fit"] is False and a["first_fit"] is None and a["coverage"] is None
        assert all(s["determined"] is False and s["rebuilt"] is None for s in r["selection"].values())
    r = run_real(monkeypatch, tmp_path, lambda *a, **k: dict(found=None, stop="hard_timeout", level=2, bank=5, function_cap_reached=False, cpu_s=90.0))
    assert r["status"] == "incomplete" and all(a["stop_class"] == "hard_stop" for a in r["searches"].values())
    r = run_real(monkeypatch, tmp_path, lambda *a, **k: dict(found=None, stop="budget_bank", level=3, bank=1500000, function_cap_reached=False, cpu_s=9.0))
    assert r["status"] == "done" and all(a["stop_class"] == "bank_cap_reached" and a["coverage"] == "bounded" for a in r["searches"].values())
    r = run_real(monkeypatch, tmp_path, lambda *a, **k: dict(found=None, stop="size_exhausted", level=4, bank=9, function_cap_reached=False, cpu_s=1.0))
    assert r["status"] == "done" and all(a["stop_class"] == "size_limit_completed" and a["coverage"] == "exhaustive" for a in r["searches"].values())
    r = run_real(monkeypatch, tmp_path, lambda *a, **k: dict(found=None, stop="size_exhausted_function_cap", level=5, bank=9, function_cap_reached=True, cpu_s=1.0))
    assert all(a["stop_class"] == "size_limit_completed_function_cap" and a["coverage"] == "bounded" for a in r["searches"].values())


def test_a_fit_that_the_later_evaluation_does_not_reproduce_is_an_infrastructure_stop(monkeypatch, tmp_path):
    wrong_tree = ("L", "size", ("P", "x0"))
    r = run_real(monkeypatch, tmp_path, lambda ops, leaves, Y, *a, **k: dict(found=("size(x0)", 2, wrong_tree) if any(o[0] == "size" for o in ops) else None,
                                                                         stop="found" if any(o[0] == "size" for o in ops) else "size_exhausted",
                                                                         level=1, bank=5, function_cap_reached=False, cpu_s=0.1))
    assert r["status"] == "incomplete"
    for name in ("L4-9", "LC4-9", "L4-36", "L5-36", "LC4-36"):
        a = r["searches"][name]
        assert a["stop_class"] == "infrastructure_failure" and "does not give the search's own fit again" in a["error"] and a["fit_recheck"]["agree"] < a["examples"]
    assert r["searches"]["C-36"]["stop_class"] == "size_limit_completed"


def test_a_memory_failure_anywhere_in_an_episode_is_incomplete_with_its_reason(monkeypatch, tmp_path):
    def hungry(*a, **k):
        raise MemoryError()
    with monkeypatch.context() as m:
        m.setattr(gen_bl, "gen_examples", hungry)                    # in the generator
        r = E.run_target("color", str(tmp_path / "a"))
        assert r["status"] == "incomplete" and r["stop_class"] == "memory_failure" and "memory failure" in r["reason"] and "searches" not in r
    with monkeypatch.context() as m:
        m.setattr(E, "_stream_usable", hungry)                       # while the true operation runs over pooled tuples
        r = E.run_target("color", str(tmp_path / "b"))
        assert r["status"] == "incomplete" and r["stop_class"] == "memory_failure"
    with monkeypatch.context() as m:
        m.setattr(E.Episode, "run_search", fake_searches({"L4-36": RIGHT_L, "C-36": RIGHT_C}))
        m.setattr(BB, "eval_tree_bl", hungry)                        # while a sealed expression is checked on the final panel
        r = E.run_target("color", str(tmp_path / "c"))
        assert r["status"] == "incomplete" and "final check" in r["reason"] and "memory failure" in r["reason"]
        assert r["searches"]["L4-36"]["final"]["incomplete"] is True and r["searches"]["L4-36"]["first_fit"] is None
        assert r["selection"]["library_only"]["rebuilt"] is None
    assert json.load(open(tmp_path / "c" / "targets" / "color.json"))["status"] == "incomplete"
    assert '"event": "incomplete"' in open(tmp_path / "a" / "journal" / "color.jsonl").read()


def test_an_address_space_near_the_ceiling_ends_the_target_and_must_end_the_process(monkeypatch, tmp_path):
    near = (P.MEMORY_CEILING_BYTES - P.ADDRESS_SPACE_MARGIN_BYTES) // 1024 + 5
    readings = iter([50000] * 5 + [near] * 100)                      # clear through the setup, near the ceiling after the first search
    monkeypatch.setattr(G, "address_space_peak_kb", lambda: next(readings))
    with pytest.raises(G.NearCeiling) as e:
        E.run_target("color", str(tmp_path / "o"))
    assert e.value.unit == "search L4-9" and e.value.peak_kb == near
    r = json.load(open(tmp_path / "o" / "targets" / "color.json"))
    assert r["status"] == "incomplete" and r["stop_class"] == "address_space_near_ceiling" and "near the ceiling" in r["reason"]
    assert list(r["searches"]) == ["L4-9"] and r["searches"]["L4-9"]["stop_class"] == "address_space_near_ceiling" and r["searches"]["L4-9"]["incomplete"] is True
    # a reading that cannot be made is a failed check, in the setup as well
    monkeypatch.setattr(G, "address_space_peak_kb", lambda: None)
    with pytest.raises(G.NearCeiling):
        E.setup_only("color")
    with pytest.raises(G.NearCeiling):
        E.run_target("color", str(tmp_path / "p"))
    assert json.load(open(tmp_path / "p" / "targets" / "color.json"))["status"] == "incomplete"


def test_the_ceiling_compared_with_is_the_limit_in_force():
    import resource
    soft, _ = resource.getrlimit(resource.RLIMIT_AS)
    assert E.address_space_ceiling() == (P.MEMORY_CEILING_BYTES if soft == resource.RLIM_INFINITY else soft)


# ---------------------------------------------------------------- the witness of a control
def with_manifest(monkeypatch, manifest):
    seen = []

    def load():
        seen.append(1)
        return manifest
    monkeypatch.setattr(E, "load_witness_manifest", load)
    return seen


def test_the_development_witness_agrees_and_the_manifest_is_read_after_the_selections(monkeypatch, tmp_path):
    tree = ["L", "c_item0", ["L", "c_first", ["P", "x0"]]]
    states = []
    real = E.Episode.step_witness
    monkeypatch.setattr(E.Episode, "step_witness", lambda self: states.append((set(self.sealed), self.F is not None)) or real(self))
    seen = with_manifest(monkeypatch, {"color": {"tree": tree, "nodes": 3, "note": "next(iter(obj))[0]"}})
    out, r = fake_run(monkeypatch, tmp_path, {"L4-36": RIGHT_L, "C-36": RIGHT_C})
    w = r["witness"]
    assert seen == [1] and states == [({"setup_record", "first_fits_9", "first_fits_36", "selections", "final_set"}, True)]
    assert w["state"] == "evaluated" and w["valid"] is True and w["expr"] == "c_item0(c_first(x0))" and w["nodes"] == 3 == w["declared_nodes"]
    assert w["agrees_on_all_36"] is True and w["agrees_on_the_final_panel"] is True and w["first_mismatch"] is None
    assert w["fit36"]["n"] == 36 == w["fit36"]["agree"] and w["final"]["n"] == r["final_panel"]["inputs"] == w["final"]["agree"]
    assert w["unsupported_results"] == 0 and w["guard_timeout"] is False and r["status"] == "done"


@pytest.mark.parametrize("entry,state,word", [
    ({"tree": ["L", "c_len", ["P", "x0"]], "nodes": 2}, "evaluated", "different value"),
    ({"tree": ["L", "c_first", ["P", "x0"]], "nodes": 2}, "evaluated", "different value"),
    ({"tree": ["L", "c_item0", ["L", "c_first", ["P", "x0"]]], "nodes": 4}, "static check failed", "declares 4 nodes"),
    ({"tree": ["L", "c_nothing", ["P", "x0"]], "nodes": 2}, "static check failed", "neither a block"),
    ({"tree": ["L", "first", ["L", "first", ["P", "x0"]]], "nodes": 3}, "static check failed", "neither a block"),
    ({"tree": ["L", "c_add", ["P", "x0"], ["C", "ONE"]], "nodes": 3}, "static check failed", "cannot take"),
    ({"tree": None, "nodes": None, "note": "needs a guard"}, "no manifest entry", None),
])
def test_a_witness_that_does_not_validate_is_recorded_with_its_reason(monkeypatch, tmp_path, entry, state, word):
    with_manifest(monkeypatch, {"color": entry})
    out, r = fake_run(monkeypatch, tmp_path, {"C-36": RIGHT_C})
    w = r["witness"]
    assert w["state"] == state and w.get("valid") is not True
    if state == "evaluated":
        assert w["valid"] is False and w["agrees_on_all_36"] is False and w["first_mismatch"]["note"] == word
    elif state == "static check failed":
        assert word in w["error"]
    else:
        assert w["note"] == "needs a guard"
    assert r["status"] == "done"                                     # a witness that fails is a matter for the calibration, not an infrastructure stop


def test_witness_states_without_an_entry_or_for_a_target_that_is_no_control(monkeypatch, tmp_path):
    with_manifest(monkeypatch, None)
    out, r = fake_run(monkeypatch, tmp_path, {})
    assert r["witness"] == dict(state="no manifest", note=None)
    with_manifest(monkeypatch, {"size": {"tree": ["L", "c_len", ["P", "x0"]], "nodes": 2}})
    out, r = fake_run(monkeypatch, tmp_path, {})
    assert r["witness"]["state"] == "no manifest entry"
    seen = with_manifest(monkeypatch, {"backdrop": {"tree": ["P", "x0"], "nodes": 1}})
    out, r = fake_run(monkeypatch, tmp_path, {}, name="backdrop")
    assert r["witness"] == dict(state="not a control") and seen == []       # the manifest is not even read for a target that is no control


def test_a_timeout_or_a_memory_failure_while_a_witness_is_evaluated(monkeypatch, tmp_path):
    tree = ["L", "c_item0", ["L", "c_first", ["P", "x0"]]]
    with_manifest(monkeypatch, {"color": {"tree": tree, "nodes": 3}})
    real = E._check_batch
    calls = []

    def timing_out(fn, argsets, xouts, seconds):
        calls.append(len(argsets))
        if len(calls) == 1:                                          # the first batch of this episode is the witness on its 36 fit examples
            return real(lambda *a: (_ for _ in ()).throw(G.GuardTimeout()), argsets, xouts, seconds)
        return real(fn, argsets, xouts, seconds)
    monkeypatch.setattr(E, "_check_batch", timing_out)
    out, r = fake_run(monkeypatch, tmp_path, {})
    w = r["witness"]
    assert w["state"] == "evaluated" and w["valid"] is False and w["guard_timeout"] is True and w["first_mismatch"] == dict(index=-1, note="guard timeout")
    monkeypatch.setattr(E, "_check_batch", lambda *a: (_ for _ in ()).throw(MemoryError()))
    out, r = fake_run(monkeypatch, tmp_path, {})
    assert r["witness"]["state"] == "memory failure" and r["witness"]["valid"] is False and r["status"] == "incomplete"


def test_no_search_path_reads_or_names_the_witness_manifest():
    for name in ("build_bl.py", "blocks_c.py", "search_bl.py", "gen_bl.py", "guards_bl.py", "bl_frozen.py"):
        src = open(os.path.join(HERE, name)).read()
        assert "witness" not in src.lower(), name                    # they neither open nor import it, nor name it
    assert P.WITNESS_MANIFEST == "witness_manifest.json"
    for method in ("setup", "setup_view", "run_search", "step_searches", "step_nine", "step_thirty_six", "step_select", "open_final", "final_check",
                   "step_final", "candidate", "memory_check"):
        assert "witness" not in inspect.getsource(getattr(E.Episode, method)).lower(), method
    for fn in (E.stream_usable, E._stream_usable, E.check_batch, E._check_batch, E.pools, E.pooled_sequence, E.pooled_args, E.setup_only):
        assert "witness" not in inspect.getsource(fn).lower()
    src = inspect.getsource(E.Episode.step_witness)
    assert src.index('self.need("the witness", "selections", done=("final",))') < src.index("load_witness_manifest()")
    assert inspect.getsource(E.Episode.run).index("self.step_select()") < inspect.getsource(E.Episode.run).index("self.step_witness()")
    assert E.load_witness_manifest() is None or isinstance(E.load_witness_manifest(), dict)


# ---------------------------------------------------------------- a final panel that cannot be formed; a re-check that runs out
def test_a_final_panel_whose_pass_runs_out_of_its_guard_makes_the_record_incomplete(monkeypatch, tmp_path):
    """A slow invented X: the pass of the true operation over the final slice runs out of its guard. Where the pass
    was cut depends on timing, so there is no final panel: no final check, no witness check, status incomplete."""
    real = E._stream_usable
    passes = []

    def slow_on_the_final_slice(xfn, argsets, seconds):
        passes.append(len(argsets))
        if len(passes) < 2:
            return real(xfn, argsets, seconds)                       # the usability slice at setup: as it is
        seen = []

        def slow_x(*a):
            seen.append(1)
            t = time.process_time()
            while len(seen) > 3 and time.process_time() - t < 20:    # spins from its fourth input on, until the timer interrupts it
                pass
            return xfn(*a)
        return real(slow_x, argsets, 0.2)
    monkeypatch.setattr(E, "_stream_usable", slow_on_the_final_slice)
    with_manifest(monkeypatch, {"color": {"tree": ["L", "c_item0", ["L", "c_first", ["P", "x0"]]], "nodes": 3}})
    out, r = fake_run(monkeypatch, tmp_path, {"L4-36": RIGHT_L, "C-36": RIGHT_C})
    assert r["status"] == "incomplete" and "the final panel could not be formed" in r["reason"] and len(passes) == 2
    fp = r["final_panel"]
    assert fp["formed"] is False and fp["pooled_slice"]["guard_timeout"] is True and fp["pooled"] == 3 and fp["pooled_not_evaluated"] > 0
    assert "final_set" not in r["seals"] and list(r["seals"]) == ["setup_record", "first_fits_9", "first_fits_36", "selections"]
    assert all(a["final"] is None for a in r["searches"].values())
    assert r["searches"]["L4-36"]["first_fit"] is None and r["searches"]["C-36"]["first_fit"] is None and r["searches"]["L5-36"]["first_fit"] == "none"
    lo, sb = r["selection"]["library_only"], r["selection"]["smaller_blocks"]
    assert (lo["expr"], lo["rebuilt"], lo["oracle_union"]) == ("first(first(x0))", None, None) and sb["rebuilt"] is None      # selected, never checked
    assert r["witness"]["state"] == "not evaluated" and "the final panel could not be formed" in r["witness"]["reason"]
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and not G.active()
    del passes[:]
    out, r = fake_run(monkeypatch, tmp_path, {})                     # nothing was selected: still no panel, still incomplete
    assert r["status"] == "incomplete" and r["selection"]["library_only"]["rebuilt"] is False and r["searches"]["L4-36"]["first_fit"] == "none"


def test_the_witness_of_a_control_whose_record_is_incomplete_says_why_it_was_not_evaluated(monkeypatch, tmp_path):
    seen = with_manifest(monkeypatch, {"color": {"tree": ["L", "c_item0", ["L", "c_first", ["P", "x0"]]], "nodes": 3}})
    out, r = fake_run(monkeypatch, tmp_path, {"L4-36": RIGHT_L, "C-36": "hard_timeout"})
    assert r["status"] == "incomplete" and r["witness"] == dict(state="not evaluated", valid=False, reason="the record is incomplete: search C-36: hard_stop")
    assert seen == []                                                # the manifest was not read


def test_a_recheck_of_a_fit_that_runs_out_of_its_guard_says_so(monkeypatch, tmp_path):
    real = E.check_batch

    def recheck_times_out(fn, argsets, xouts, seconds):
        c = real(fn, argsets, xouts, seconds)
        if len(argsets) in (9, 36):                                  # the re-check of a search's own fit on its own examples
            c.update(guard_timeout=True, right=False, counterexample=dict(index=-1, note="guard timeout"))
        return c
    monkeypatch.setattr(E, "check_batch", recheck_times_out)
    r = E.run_target("color", str(tmp_path / "o"))
    assert r["status"] == "incomplete"
    for a in r["searches"].values():
        assert a["stop_class"] == "infrastructure_failure" and a["error"] == "the later evaluation of the search's own fit ran out of its guard"
        assert a["fit_recheck"]["guard_timeout"] is True and a["first_fit"] is None and a["incomplete"] is True


def test_steps_refuse_to_run_out_of_order():
    ep = E.Episode("color")
    for step in (ep.step_nine, ep.step_thirty_six, ep.step_select, ep.open_final, ep.step_final, ep.step_witness):
        with pytest.raises(E.OrderError):
            step()


# ---------------------------------------------------------------- processor time in the two modes (independent review, 0763)
SIX = (("L4-9", "L", "fit9", 4), ("LC4-9", "LC", "fit9", 4), ("L4-36", "L", "fit36", 4), ("L5-36", "L", "fit36", 5),
       ("LC4-36", "LC", "fit36", 4), ("C-36", "C", "fit36", 4))


def six_searches(name):
    """All six searches of one development name through the episode's own path, nine-example ones first."""
    ep = E.Episode(name)
    assert ep.setup() is None
    ep.rec.open("fit9")
    out = {}
    for label, block_set, role, size in SIX[:2]:
        out[label] = ep.run_search(label, block_set, role, size)
    ep.seal("first_fits_9", dict(test="the two nine-example searches ran above"))
    ep.rec.open("fit36")
    for label, block_set, role, size in SIX[2:]:
        out[label] = ep.run_search(label, block_set, role, size)
    return ep, out


@pytest.mark.parametrize("mode", ["budget off: the allowance binds", "budget on: processor time is a safety limit"])
def test_processor_time_in_each_mode_on_all_six_searches(monkeypatch, mode):
    """hmirror has no fit at four nodes in any block set and every search takes more than a second, so a processor
    time of 0.2 s stops all six. With the combination budget off that is the binding allowance (bounded, the record
    stays complete); with it on (a budget no search reaches here) it is the safety limit: every search is an
    infrastructure stop, the record is incomplete and no selection can be made."""
    on = mode.startswith("budget on")
    if on:
        monkeypatch.setattr(P, "MAX_COMBINATIONS", 10 ** 9)
        monkeypatch.setattr(P, "TIME_SAFETY_LIMIT_S", 0.2)
    else:
        monkeypatch.setattr(P, "MAX_COMBINATIONS", None)
        monkeypatch.setattr(P, "ALLOWANCE", 0.2)
    ep, out = six_searches("hmirror")
    assert sorted(out) == sorted(label for label, _, _, _ in SIX)
    for label, a in out.items():
        assert a["stop"] == "budget_cpu" and a["cpu_budget_s"] == 0.2, (label, a["stop"])
        if on:
            assert a["stop_class"] == "time_safety_limit" and a["incomplete"] is True and a["coverage"] is None, label
            assert a["cpu_budget_is"] == "a safety limit" and a["max_combinations"] == 10 ** 9 and 0 < a["ticks"] < 10 ** 9, label
        else:
            assert a["stop_class"] == "allowance_used_up" and a["incomplete"] is False and a["coverage"] == "bounded", label
            assert a["cpu_budget_is"] == "the binding allowance" and a["max_combinations"] is None, label
    assert len(ep.incomplete) == (6 if on else 0)
    ep.step_thirty_six = lambda: None                                # the six searches ran above; the selection reads them
    ep.seal("first_fits_36", {n: dict(stop=a["stop"]) for n, a in out.items() if n in P.THIRTY_SIX})
    ep.done.add("first_fits_36")
    ep.res["searches"] = out
    ep.step_select()
    for system in P.SYSTEM_NAMES:
        s = ep.res["selection"][system]
        assert s["determined"] is (not on) and s["expr"] is None, (system, s)


def test_the_presets_of_the_two_modes():
    assert (P.ALLOWANCE, P.TIME_SAFETY_LIMIT_S) == (60.0, 600.0)
    assert P.cpu_budget() == (P.ALLOWANCE if P.combination_budget() is None else P.TIME_SAFETY_LIMIT_S)
    alloc = P.system_allocation()
    if P.combination_budget() is None:
        assert alloc == dict(unit="processor seconds", per_system=120.0)
    else:
        assert alloc["per_system"] == 2 * P.MAX_COMBINATIONS and alloc["processor_seconds_safety_limit_per_search"] == 600.0


def test_the_combination_budget_is_what_the_declared_rule_gives():
    """presets MAX_COMBINATIONS is N of N_RECORD.json, and derive_n.py gives that record again from ticks_measure.json."""
    import derive_n
    here = os.path.dirname(os.path.abspath(E.__file__))
    raw = open(os.path.join(here, "ticks_measure.json"), "rb").read()
    rec = json.load(open(os.path.join(here, "N_RECORD.json")))
    out = derive_n.derive(raw)
    assert rec["source_sha256"] == hashlib.sha256(raw).hexdigest() == "fecf3500ea7550b68d044beca761d3c2ba8478089e3e5f879b757b647e635bc2"
    assert rec["rule_script_sha256"] == hashlib.sha256(open(os.path.join(here, "derive_n.py"), "rb").read()).hexdigest()
    assert (out["N"], out["median"], out["n_rows"]) == (rec["N"], rec["median"], rec["n_rows"]) == (1_900_000, 1_931_904, 17)
    assert P.MAX_COMBINATIONS == rec["N"]
    assert [derive_n.floor_two_significant(n) for n in (99, 100, 1_931_904, 1_999_999, 2_000_000)] == [99, 100, 1_900_000, 1_900_000, 2_000_000]
