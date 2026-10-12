"""Automatic failure diagnosis v0 tests (cora_diag/)."""
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def test_core_is_domain_neutral_and_reference_free():
    core = open(os.path.join(HERE, "cora_diag", "diagnose.py")).read()
    assert not re.search(r"\bS[1-7]\b", core) and not re.search(r"\bk[0-9a-f]{12}\b", core)
    for f in ("diagnose.py", "arc_adapter.py"):
        assert "forensic_reference" not in open(os.path.join(HERE, "cora_diag", f)).read()


def test_predicates():
    from cora_diag.diagnose import diagnose
    assert diagnose({"repairs_proposed": 0})["primary"] == "REPAIR_NOT_GENERATED"
    d = diagnose({"repairs_proposed": 1, "hard_cap_hit": True, "accepted": False})
    assert "RESOURCE_EXHAUSTED" in d["established"] and "ENGINE_REJECTED" not in d["established"]
    d = diagnose({"repairs_proposed": 1, "accepted": False, "verdict_reached": True, "top_level_fit": True,
                  "rederivations": 3, "rederivations_failed": 1, "rederivation_changed_program": True,
                  "evidence_unit_excluded_in_failed_rederivation": True})
    assert d["primary"] == "REPRESENTATION_EXCLUDED" and d["decision"] == "NO_ACTION"
    assert {"ENGINE_REJECTED", "CERTIFICATION_UNSTABLE"} <= set(d["established"])
    d = diagnose({"repairs_proposed": 2, "competing_repairs": 2, "competing_repairs_disagree": True, "accepted": False})
    assert d["primary"] == "MULTIPLE_PLAUSIBLE_REPAIRS" and d["decision"] == "ABSTAIN"
    assert diagnose({"accepted": True})["primary"] is None
    assert diagnose({})["primary"] == "UNKNOWN"


def _unit(key="kf892487f1049", fold=1, mutate=False):
    from cora_diag import arc_adapter as AD
    import numpy as np
    rows = {json.loads(x)["key"]: json.loads(x) for x in open(os.path.join(HERE, "outputs", "reach_v1", "measure_rows.jsonl")) if x.strip()}
    diag = {json.loads(x)["key"]: json.loads(x) for x in open(os.path.join(HERE, "outputs", "loo_v1", "diagnose_rows.jsonl")) if x.strip()}
    census = json.load(open(os.path.join(HERE, "outputs", "loo_v1", "probe_equivalence.json")))["development"][key]["subsets"]
    task = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))["tasks"][key]
    mr, dr = copy.deepcopy(rows[key]), copy.deepcopy(diag[f"{key}:f{fold}"])
    if mutate:                                        # every forbidden field changed
        for f in mr["loo"]["folds"]:
            f["heldout_exact"] = not f["heldout_exact"]
            f["same_as_full"] = not f["same_as_full"]
        b = dr["B_WALL"]
        b["heldout_distinguish"] = [{"reproduces": 99}]
        b["engine"]["heldout_exact"] = not b["engine"]["heldout_exact"]
        for v in b["analysis"]["variants"].values():
            v["full_ext_reproduces"] = -1
        b["same_as_full"] = not b["same_as_full"]
        dr["A_E_WALL"] = {"accepted": True}
    unl = [task["train"][fold]["input"]] + [c["input"] for c in task["test"]]
    return AD.unit_observations(key, len(task["train"]), fold, mr, dr, census, unl)


def test_forbidden_fields_cannot_change_a_fold_and_runs_are_deterministic():
    a, b, c = _unit(), _unit(mutate=True), _unit()
    assert a == b == c
    assert a["competing_repairs"] == 2 and a["competing_repairs_disagree"] is True
