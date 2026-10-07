"""Real ARC pilot v1: selection, bundle, isolation, placement and blind
scoring, with negative controls. No test reads a solutions file or runs a
pilot task."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_pilot import bundle as B                                  # noqa: E402
from cora_pilot import evaluator as EV                              # noqa: E402
from cora_pilot import isolation as ISO                             # noqa: E402

G1 = [[1, 0], [0, 1]]
G2 = [[2, 0], [0, 2]]
G3 = [[3, 3], [3, 3]]


def toy_challenges():
    def task(n, change=True, same=True):
        tr = []
        for i in range(n):
            a = [[i % 10, 0], [0, 1]]
            b = [[(i + 1) % 10, 0], [0, 1]] if change else a
            if not same:
                b = [[1, 2, 3]]
            tr.append({"input": a, "output": b})
        return {"train": tr, "test": [{"input": G1}]}
    return {"t3": task(3), "t4": task(4), "t5": task(5), "t2": task(2), "tsame": task(3, change=False),
            "tshape": task(3, same=False)}


# ------------------------------------------------------------------ selection

def test_scope_rule():
    ch = toy_challenges()
    assert B.in_scope(ch["t3"]) and B.in_scope(ch["t4"]) and B.in_scope(ch["t5"])
    assert not B.in_scope(ch["t2"])          # fewer than three demonstrations
    assert not B.in_scope(ch["tsame"])       # a demonstration that does not change
    assert not B.in_scope(ch["tshape"])      # a shape change
    assert [B.stratum(ch[t]) for t in ("t3", "t4", "t5")] == ["n3", "n4", "n5p"]


def test_order_is_a_hash_of_the_id_only():
    assert B.order_key("abc") == B.order_key("abc") != B.order_key("abd")
    sel = B.selection(toy_challenges())
    assert sel["in_scope"] == 3 and [t for t, _ in sel["order"]] == sorted(["t3", "t4", "t5"], key=B.order_key)


def test_frozen_selection_reproduces():
    path = os.path.join(HERE, "records", "pilot_v1", "selection.json")
    frozen = json.load(open(path))
    sel = B.selection(B.load_challenges())
    for key in ("order", "dev", "pilot_candidates", "in_scope", "strata_counts"):
        assert frozen[key] == sel[key]
    assert len(sel["dev"]) == 60 and sel["in_scope"] == 548
    assert not set(sel["dev"]) & {t for v in sel["pilot_candidates"].values() for t in v}


def test_pilot_quotas():
    sel = json.load(open(os.path.join(HERE, "records", "pilot_v1", "selection.json")))
    for n in B.ALLOWED_N:
        ids = B.pilot_ids(sel, n)
        assert len(ids) == n and len(set(ids)) == n and not set(ids) & set(sel["dev"])
    with pytest.raises(ValueError):
        B.pilot_ids(sel, 50)


# ------------------------------------------------------------------ bundle

def test_bundle_carries_inputs_only_under_opaque_keys():
    ch = toy_challenges()
    bundle, keymap = B.make_bundle(ch, ["t3", "t4"], salt_hex="00" * 32)
    B.check_bundle(bundle)
    text = json.dumps(bundle)
    assert "t3" not in bundle["tasks"] and "t4" not in bundle["tasks"]
    assert "task_id" not in text and "stratum" not in text and "salt" not in text
    for t in bundle["tasks"].values():
        assert all(set(p) == {"input"} for p in t["test"])
    assert {v["task_id"] for v in keymap["keys"].values()} == {"t3", "t4"}
    #  the key depends on the secret salt
    b2, _ = B.make_bundle(ch, ["t3"], salt_hex="11" * 32)
    assert set(b2["tasks"]) != {k for k, v in keymap["keys"].items() if v["task_id"] == "t3"}


@pytest.mark.parametrize("mutate", ["target", "task_id_key", "extra_field", "bad_grid", "label"])
def test_bundle_negative_controls(mutate):
    bundle, _ = B.make_bundle(toy_challenges(), ["t3"], salt_hex="00" * 32)
    k = next(iter(bundle["tasks"]))
    if mutate == "target":
        bundle["tasks"][k]["test"][0]["output"] = G2
    elif mutate == "task_id_key":
        bundle["tasks"]["0a1b2c3d"] = bundle["tasks"].pop(k)
    elif mutate == "extra_field":
        bundle["tasks"][k]["family"] = "recolour"
    elif mutate == "bad_grid":
        bundle["tasks"][k]["train"][0]["output"] = [[10]]
    elif mutate == "label":
        bundle["labels"] = {k: "solved"}
    with pytest.raises(ValueError):
        B.check_bundle(bundle)


# ------------------------------------------------------------------ isolation

def _child(code, bundle_path):
    prog = (f"import sys, json, os; sys.path.insert(0, {HERE!r});"
            f"from cora_pilot import isolation as ISO; ISO.install({bundle_path!r});" + code)
    return subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("target", [
    B.SOLUTIONS, B.CHALLENGES,
    os.path.join(HERE, "records", "pilot_v1_evaluator", "dev_keymap.json"),
    os.path.join(HERE, "records", "pilot_v1", "selection.json"),
    os.path.join(HERE, "data", "arc", "dev60_challenges.json"),
    "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project/RUN_HISTORY.md",
    os.path.join(HERE, ".git", "HEAD"),
])
def test_isolation_refuses_forbidden_reads(tmp_path, target):
    bundle = tmp_path / "bundle.json"
    bundle.write_text("{}")
    r = _child(f"\ntry:\n    open({target!r}).read(1)\n    print('READ')\nexcept PermissionError:\n    print('REFUSED')\n"
               f"ISO.dump({str(tmp_path / 'iso.json')!r})", str(bundle))
    assert "REFUSED" in r.stdout and "READ" not in r.stdout.replace("REFUSED", ""), r.stderr
    rep = json.load(open(tmp_path / "iso.json"))
    assert rep["denied"] and ISO.audit_log(rep)


def test_isolation_refuses_listing_and_spawning(tmp_path):
    bundle = tmp_path / "bundle.json"
    bundle.write_text("{}")
    code = ("\nout=[]\nfor f in (lambda: os.listdir(" + repr(B.DATA_DIR) + "), "
            "lambda: __import__('subprocess').run(['true'])):\n"
            "    try:\n        f(); out.append('OK')\n    except PermissionError:\n        out.append('REFUSED')\n"
            "print(out)")
    r = _child(code, str(bundle))
    assert "['REFUSED', 'REFUSED']" in r.stdout, r.stdout + r.stderr


def test_isolation_allows_the_bundle_and_code(tmp_path):
    bundle = tmp_path / "bundle.json"
    bundle.write_text('{"format": 1}')
    r = _child(f"\njson.load(open({str(bundle)!r}))\nimport numpy\n"
               f"open({str(tmp_path / 'scratch.txt')!r}, 'w').write('x')\nISO.dump({str(tmp_path / 'iso.json')!r})",
               str(bundle))
    assert r.returncode == 0, r.stderr
    rep = json.load(open(tmp_path / "iso.json"))
    assert rep["bundle_opened"] and not rep["denied"] and ISO.audit_log(rep) == []


def test_audit_flags_missing_hook_and_unopened_bundle():
    assert "hook not installed" in ISO.audit_log({"installed": False, "bundle_opened": True})
    assert "bundle never opened" in ISO.audit_log({"installed": True, "bundle_opened": False})


def test_reasoner_side_sources_never_name_evaluator_inputs():
    for name in ("reasoner.py", "native.py", "isolation.py"):
        text = open(os.path.join(HERE, "cora_pilot", name)).read()
        for word in ("SOLUTIONS", "pilot_keymap", "sealed_solved", "load_pinned"):
            assert word not in text, (name, word)
    text = open(os.path.join(HERE, "scripts", "pilot_v1_run.py")).read()
    assert "SOLUTIONS" not in text and "pilot_keymap" not in text and "evaluator import" not in text


# ------------------------------------------------------------------ placement

def test_system_placement_never_displaces_native_attempt_1():
    import pilot_v1_run as RUN
    nat = {"attempt_1": [G1, None], "attempt_2": [G2, G2]}
    cora = {"activated": True, "cora_prediction": [G3, G3]}
    assert RUN.system_attempts(nat, cora, 2) == [[G1, G3], [G3, G2]]
    assert RUN.system_attempts(nat, {"activated": False, "cora_prediction": None}, 2) == [[G1, G2], [None, G2]]
    assert RUN.system_attempts(None, cora, 2) == [[G3, None], [G3, None]]


# ------------------------------------------------------------------ blind scoring

def pred(native_a1=None, native_a2=None, alone=None, with_e=None, activated=False, removed=None, matched=None):
    cp = with_e if activated else None
    nat = {"attempt_1": [native_a1], "attempt_2": [native_a2]}
    a = [[native_a1, cp[0]] if (cp and native_a1 is not None) else
         ([cp[0], native_a2] if cp else [native_a1, native_a2])]
    return {"native": nat, "kstar_prime_alone": alone, "cora_with_e": with_e, "activated": activated,
            "cora_prediction": cp, "removed": removed, "matched": matched,
            "controls": {"DEMO_ONLY": None, "SHUFFLED_FRONTIER": None}, "system": a}


def cora_row(activated=True, same_removed=True):
    g = {k: True for k in ("compile", "accepted", "uses", "replay", "attribution", "prediction",
                           "determinism", "loo", "unanimity", "support")}
    alone = {"accepted": False, "program_sha": None, "predictions": [None]}
    return {"fc": {"class": "SELECTED"}, "gates": g, "restored": True, "snapshot_equal": True,
            "path_class": "ACTIVATED" if activated else "LOO_FAILURE", "activated": activated,
            "kstar_prime_alone": alone,
            "removed": dict(alone) if same_removed else {"accepted": True, "program_sha": "x", "predictions": [G2]}}


def test_complete_witness():
    s = EV.score_task("k", pred(native_a1=G2, with_e=[G1], activated=True, removed=[None], matched=[None]),
                      cora_row(), [G1], in_sealed=False)
    assert s["witness"] and s["outcome"] == "CORRECT_CAUSAL_RESCUE" and all(s["legs"].values())


def test_wrong_activation_is_never_hidden_by_a_native_solve():
    s = EV.score_task("k", pred(native_a1=G1, with_e=[G2], activated=True), cora_row(), [G1], in_sealed=True)
    assert s["outcome"] == "WRONG_ACTIVATION" and not s["witness"]


def test_b_leg_uses_the_sealed_record():
    s = EV.score_task("k", pred(with_e=[G1], activated=True, removed=[None], matched=[None]), cora_row(), [G1],
                      in_sealed=True)
    assert not s["legs"]["B"] and s["outcome"] == "BASELINE_ALREADY_SOLVES" and not s["witness"]


def test_a_leg_fails_when_matched_compute_reproduces():
    s = EV.score_task("k", pred(with_e=[G1], activated=True, removed=[None], matched=[G1]), cora_row(), [G1],
                      in_sealed=False)
    assert not s["legs"]["A"] and s["outcome"] == "ABLATION_FAILURE"


def test_integrity_failure_when_disabled_baseline_changed():
    s = EV.score_task("k", pred(with_e=[G1], activated=True, removed=[None], matched=[None]),
                      cora_row(same_removed=False), [G1], in_sealed=False)
    assert not s["witness"] and s["outcome"] == "INTEGRITY_FAILURE"


def test_abstention_outcomes():
    right = EV.score_task("k", pred(with_e=[G1]), cora_row(activated=False), [G1], in_sealed=False)
    wrong = EV.score_task("k", pred(with_e=[G2]), cora_row(activated=False), [G1], in_sealed=False)
    none = EV.score_task("k", pred(), {"path_class": "NO_PROPOSAL"}, [G1], in_sealed=False)
    assert (right["outcome"], wrong["outcome"], none["outcome"]) == ("MISSED_RESCUE", "HELDOUT_MISMATCH", "NO_CHANGE")


def _keymap(keys):
    return {"keys": {k: {"task_id": "id" + k, "n_test": 1, "stratum": "n3"} for k in keys}}


def test_ladder():
    keys = ["ka", "kb"]
    preds = {"ka": pred(native_a1=G2, with_e=[G1], activated=True, removed=[None], matched=[None]),
             "kb": pred(native_a1=G1)}
    rows = {"ka": cora_row(), "kb": {"path_class": "NO_PROPOSAL"}}
    sol = {"idka": [G1], "idkb": [G1]}
    ok = EV.evaluate(_keymap(keys), preds, rows, {}, sol, set(), {"problems": {}})
    assert ok["outcome"] == "REAL_ARC_CAUSAL_WITNESS_ESTABLISHED" and ok["safety"] == "SAFE"
    assert ok["summary"]["witnesses"] == 1 and ok["summary"]["net_score"] == 1
    assert ok["summary"]["baseline_solves_retained"] == 1 and ok["summary"]["lost_solves"] == 0
    leak = EV.evaluate(_keymap(keys), preds, rows, {}, sol, set(), {"problems": {"cora_0": ["refused"]}})
    assert leak["outcome"] == "PILOT_LEAKAGE"
    err = EV.evaluate(_keymap(keys), preds, {"ka": {"path_class": "RUN_ERROR"}, "kb": {"path_class": "RUN_ERROR"}},
                      {}, sol, set(), {"problems": {}})
    assert err["outcome"] == "NO_VERDICT_RUN_ERROR"
    cov = EV.evaluate(_keymap(keys + ["kc"]), preds, rows, {}, dict(sol, idkc=[G1]), set(), {"problems": {}})
    assert cov["outcome"] == "NO_VERDICT_DATASET"
    none = EV.evaluate(_keymap(["kb"]), {"kb": preds["kb"]}, rows, {}, sol, set(), {"problems": {}})
    assert none["outcome"] == "NO_REAL_ARC_WITNESS"


def test_unsafe_when_a_native_solve_is_lost():
    keys = ["ka"]
    #  native's correct answer was attempt 2; CORA activated wrong into attempt 2's slot
    p = pred(native_a1=G3, native_a2=G1, with_e=[G2], activated=True)
    res = EV.evaluate(_keymap(keys), {"ka": p}, {"ka": cora_row()}, {}, {"idka": [G1]}, set(), {"problems": {}})
    assert res["summary"]["lost_solves"] == 1 and res["safety"] == "UNSAFE"


# ------------------------------------------------------------------ evaluator and verifier agree

def _verifier():
    import importlib.util
    spec = importlib.util.spec_from_file_location("verify_pilot", os.path.join(HERE, "logs", "pilot_v1", "verify_pilot.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_evaluator_and_independent_verifier_agree_on_random_tasks():
    import random
    V = _verifier()
    rng = random.Random(20261007)
    grids = [G1, G2, G3, None]
    gate_names = [g for g, _c in __import__("cora_pilot.reasoner", fromlist=["GATES"]).GATES]
    for _ in range(400):
        tg = [rng.choice([G1, G2])]
        act = rng.random() < 0.5
        with_e = [rng.choice(grids)] if rng.random() < 0.8 else None
        p = pred(native_a1=rng.choice(grids), native_a2=rng.choice(grids), with_e=with_e,
                 activated=act and with_e is not None, removed=[rng.choice(grids)], matched=[rng.choice(grids)])
        alone = {"accepted": rng.random() < 0.5, "program_sha": rng.choice(["a", "b"]), "predictions": [rng.choice(grids)]}
        rem = dict(alone) if rng.random() < 0.7 else {"accepted": True, "program_sha": "z", "predictions": [G3]}
        r = {"fc": {"class": rng.choice(["SELECTED", "NO_PROPOSAL"])},
             "gates": {g: rng.random() < 0.85 for g in gate_names},
             "restored": rng.random() < 0.9, "snapshot_equal": rng.random() < 0.9,
             "kstar_prime_alone": alone, "removed": rem, "path_class": "ACTIVATED"}
        sealed = rng.random() < 0.2
        s = EV.score_task("k", p, r, tg, sealed)
        native_ok, wit, o = V.independent_outcome(p, r, tg, sealed)
        assert (s["native_solved"], s["witness"], s["outcome"]) == (native_ok, wit, o), (p, r, tg, sealed)


def test_leakage_takes_precedence_over_a_dataset_problem():
    keys = ["ka"]
    res = EV.evaluate(_keymap(keys + ["kz"]), {"ka": pred()}, {"ka": {"path_class": "NO_PROPOSAL"}}, {},
                      {"idka": [G1], "idkz": [G1]}, set(), {"problems": {"cora_1": ["refused open"]}})
    assert res["outcome"] == "PILOT_LEAKAGE"
