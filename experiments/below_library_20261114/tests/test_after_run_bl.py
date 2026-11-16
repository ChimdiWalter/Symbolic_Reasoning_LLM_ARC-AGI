"""Tests of the checks made after the run (after_run_bl.py) and of the earlier-result check's text rules.
Author: Chimdi Walter Ndubuisi. Invented records only; nothing is searched."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import after_run_bl as A          # noqa: E402
import earlier_result_check as ER  # noqa: E402

SEALS = {n: "%064x" % i for i, n in enumerate(A.SEALS)}


def journal(seals=A.SEALS, tail=("final_opened", "done"), shas=SEALS):
    ev = [dict(event="start"), dict(event="setup_usability")]
    for n in seals:
        if n == "first_fits_9":
            ev += [dict(event="search"), dict(event="search")]
        ev.append(dict(event="seal", name=n, sha256=shas.get(n)))
    return ev + [dict(event=k) for k in tail]


def test_a_complete_done_journal_passes():
    assert A.journal_problem(journal(), dict(status="done", seals=SEALS)) is None


def test_a_witness_event_between_the_opening_and_done_passes():
    assert A.journal_problem(journal(tail=("final_opened", "witness", "done")), dict(status="done", seals=SEALS)) is None


def test_a_missing_seal_fails():
    assert "seals" in A.journal_problem(journal(seals=A.SEALS[:-1]), dict(status="done", seals=SEALS))


def test_seals_out_of_order_fail():
    order = (A.SEALS[0], A.SEALS[2], A.SEALS[1]) + A.SEALS[3:]
    assert "seals" in A.journal_problem(journal(seals=order), dict(status="done", seals=SEALS))


def test_a_seal_that_differs_from_the_record_fails():
    other = dict(SEALS, selections="f" * 64)
    assert "differ" in A.journal_problem(journal(), dict(status="done", seals=other))


def test_opening_the_final_panel_before_the_last_seal_fails():
    ev = journal(tail=("done",))
    ev.insert(len(ev) - 2, dict(event="final_opened"))         # before the seal final_set
    assert A.journal_problem(ev, dict(status="done", seals=SEALS)) is not None


def test_two_starts_fail():
    assert "start" in A.journal_problem([dict(event="start")] + journal(), dict(status="done", seals=SEALS))


def test_an_excluded_journal():
    assert A.journal_problem([dict(event="start"), dict(event="excluded")], dict(status="excluded")) is None
    assert A.journal_problem([dict(event="start"), dict(event="setup_usability"), dict(event="excluded")], dict(status="excluded")) is None
    assert A.journal_problem([dict(event="start"), dict(event="search"), dict(event="excluded")], dict(status="excluded")) is not None
    assert A.journal_problem([dict(event="start"), dict(event="setup_usability"), dict(event="seal", name="setup_record"),
                              dict(event="excluded")], dict(status="excluded")) is not None


def test_guard_marks_lists_timeouts_and_missing_marks():
    rec = dict(searches={"L4-36": dict(fit=True, fit_recheck=dict(guard_timeout=False), final=dict(guard_timeout=True)),
                         "C-36": dict(fit=True, fit_recheck=dict(agree=36), final=dict(guard_timeout=False)),
                         "L5-36": dict(fit=False)},
               setup=dict(usability=dict(guard_timeout=False)), final_panel=dict(pooled_slice=dict(guard_timeout=False)),
               witness=dict(state="evaluated", guard_timeout=True))
    timeouts, missing = A.guard_marks(rec)
    assert timeouts == ["L4-36/final", "witness"]
    assert missing == ["C-36/fit_recheck"]


def test_a_witness_that_failed_its_static_check_ran_no_guard():
    assert A.guard_marks(dict(witness=dict(state="static check failed", valid=False))) == ([], [])


def test_normalize_renames_whole_parameter_names_only():
    assert ER.normalize("first(first(obj))", ["obj"]) == "first(first(x0))"
    assert ER.normalize("objects(obj, a)", ["obj", "a"]) == "objects(x0, x1)"
    assert ER.normalize(None, ["obj"]) is None
