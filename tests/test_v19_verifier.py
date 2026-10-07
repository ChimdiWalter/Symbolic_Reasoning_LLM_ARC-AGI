"""Item-2 v1.9: the terminal verifier agrees with the frozen script's own
aggregation (erratum 01, review finding 4). Synthetic rows only: no engine
run, no corpus generated (v18_corpus is stubbed), files in a temporary
directory."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import runpy
import sys
import time
import types

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

import v19_prospective as PR                                      # noqa: E402

VERIFIER = os.path.join(HERE, "logs", "v19", "verify_prospective.py")


def full_row(i, law):
    run = {"accepted": True, "heldout_exact": True, "program_sha": f"p{i}", "events": [], "uses": True,
           "replays_training": True, "direct_equals_engine": True, "seconds": 1}
    folds_new = [{"fold": k, "class": "SUCCESS", "accepted": True, "uses": True, "heldout_exact": True,
                  "selected": f"s{i}", "production": f"cx{i}"} for k in range(7)]
    folds_old = [{"fold": k, "class": "LOO_FAILURE", "accepted": False, "uses": False, "heldout_exact": False,
                  "selected": f"s{i}", "production": f"cx{i}"} for k in range(7)]
    r = {"i": i, "seed": law[i]["seed"], "family": "(1,1)", "digest": law[i]["digest"], "donor_seed": 0,
         "arms": {"FAILURE_CONDITIONED": {"class": "SELECTED", "useful": True, "selection": {"level": "MDL"}},
                  "SHUFFLED_FRONTIER": {"class": "SELECTED", "useful": False, "selection": None},
                  "BLIND": {"class": "SELECTED", "useful": False, "selection": None}},
         "old": {"verdict": "x", "uses": True,
                 "with": {"accepted": True, "heldout_exact": True, "events": [], "seconds": 1,
                          "program_sha": f"p{i}"},
                 "without": {"accepted": False, "heldout_exact": False, "events": [], "seconds": 1,
                             "program_sha": None}},
         "new_with": run, "new_alone": {"accepted": False, "events": [], "program_sha": None},
         "baseline_3x": {"accepted": False, "heldout_exact": False, "seconds": 24},
         "loo_old": {"passed": False, "folds_success": 0, "folds": folds_old},
         "loo_new": {"passed": True, "folds_success": 7, "folds": folds_new},
         "restored": True, "wrong_trials": [], "reduced": {"trials": []}, "worker": 1,
         "min_key_witnesses": 3 if i % 2 else 4}
    wn = {"B": True, "P": True, "U": True, "L": True, "T": True, "A": True}
    wo = {"B": True, "P": True, "U": True, "L": False, "T": True, "A": True}
    r["witness_new"] = dict(wn, complete=True)
    r["witness_old"] = dict(wo, complete=False)
    return r


def legal_partial_rows(rows):
    cf = rows[5]                                              # the selection does not compile
    for k in ("old", "new_with", "new_alone", "baseline_3x", "loo_old", "loo_new", "restored",
              "wrong_trials", "reduced", "min_key_witnesses"):
        cf.pop(k)
    cf["engine_class"] = "COMPILE_FAILURE"
    cf["witness_new"] = cf["witness_old"] = {"complete": False, "P": True}
    rx = rows[6]                                              # the main arm hits the proposer limit
    for k in ("old", "new_with", "new_alone", "baseline_3x", "loo_old", "loo_new", "restored",
              "wrong_trials", "reduced", "min_key_witnesses"):
        rx.pop(k)
    rx["arms"]["FAILURE_CONDITIONED"] = {"class": "RESOURCE_EXHAUSTED", "useful": False, "selection": None}
    rx["witness_new"] = rx["witness_old"] = {"complete": False, "P": False}


@pytest.fixture
def case(tmp_path, monkeypatch):
    for name in ("OUT", "ROWS", "START", "MARKER", "TASKS", "RESUME_LOG", "WORKERS_FILE", "INTERRUPTED",
                 "CLAIMS"):
        monkeypatch.setattr(PR, name, str(tmp_path / os.path.basename(getattr(PR, name))))
    monkeypatch.setattr(PR, "freeze_problems", lambda: ([], {}))
    law = [{"seed": PR.SEED_BASE + 100 * i, "digest": f"synthetic{i}"} for i in range(PR.N_TASKS)]
    stub = types.ModuleType("v18_corpus")
    stub.MAX_TRIES = 2000
    stub.tasks = lambda *a, **k: [dict(t) for t in law]
    monkeypatch.setitem(sys.modules, "v18_corpus", stub)
    return law


def run(rows, law, tamper=None):
    tasks = [{"i": i, "seed": t["seed"], "digest": t["digest"]} for i, t in enumerate(law)]
    out, gates, report = PR.build_report(rows, tasks, [], [0] * PR.WORKERS, 0, time.time())
    if tamper:
        tamper(report)
    man_sha = hashlib.sha256(open(PR.MANIFEST, "rb").read()).hexdigest()
    json.dump(report, open(PR.OUT, "w"), default=str)
    with open(PR.ROWS, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    json.dump({"manifest_sha256": man_sha}, open(PR.START, "w"))
    open(PR.MARKER, "w").write(report["outcome"] + "\n")
    json.dump({"tasks": tasks}, open(PR.TASKS, "w"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_path(VERIFIER, run_name="__main__")
    return json.loads(buf.getvalue()), report


def test_verifier_agrees_on_legal_partial_rows(case):
    rows = [full_row(i, case) for i in range(PR.N_TASKS)]
    legal_partial_rows(rows)
    v, report = run(rows, case)
    assert v["all_checks_pass"], [k for k, ok in v["checks"].items() if not ok]
    assert v["recomputed"]["outcome"] == report["outcome"] == "ENGINE_STABILITY_REPAIR_ACCEPTED"
    assert v["recomputed"]["legs_new"]["P"] == PR.N_TASKS - 1


def test_resumes_logged_during_the_run_are_carried(case):
    with open(PR.RESUME_LOG, "w") as fh:
        fh.write(json.dumps({"resumed_utc": "x", "pid": 1, "rows_kept": 3, "unparsable_lines": 0}) + "\n")
    rows = [full_row(i, case) for i in range(PR.N_TASKS)]
    v, report = run(rows, case)
    assert len(report["resumes"]) == 1 and v["checks"]["resume_record_consistent"]


def test_tampered_report_is_caught(case):
    rows = [full_row(i, case) for i in range(PR.N_TASKS)]

    def tamper(rep):
        rep["gates"]["G2_witnesses_new"]["complete"] += 1
    v, _ = run(rows, case, tamper)
    assert not v["all_checks_pass"] and not v["checks"]["G2_equal"]
