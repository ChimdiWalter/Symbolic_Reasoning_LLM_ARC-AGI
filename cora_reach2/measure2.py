"""Reach v2 measurement: the reach v1 policy (cora_reach.measure, frozen at
c8d8e3a) with the one licensed repair, variant-carrying installation
(cora_reach2.variant): wherever the policy installs an extension that carries
a construction variant (the failure-conditioned proposal, every leave-one-out
fold's proposal, the shuffled-failure donor's proposal), the variant is
searched first while the extension is installed. The demonstration-only
control has no variant and is installed as in v1.

GENERATED from cora_reach/measure.py by targeted edits, each marked `# V2`
(scripts/build_measure2.py records them); every other line of object_run,
loo_fold, run_control and run_task is v1's, and every helper is imported
from v1 unchanged. tests/test_reach2.py checks that removing the V2 edits
gives back v1's source exactly.
"""
from __future__ import annotations

import contextlib
import json
import os
import time

import numpy as np

from cora_reach import bridge as BR
from cora_reach import construct as CN
from cora_reach import growth_ext as GE
from cora_reach import instances as INST
from cora_reach import relations as REL
from cora_reach.measure import (BUDGET_S, CAP_SLACK_S, CONTROL_ARMS, EXTRACT_CAP_S, FRAMES_ALLOWANCE_S,  # noqa: F401
                                GATES, MATCHED_MAX_S, MATCHED_MIN_S, PATH_CLASSES, PROGRESSION, _close, _grid,
                                _hard_timeout, _load, _proposal_summary, arrays, as_task, clear_engine_caches,
                                demo_only_propose, engine_dirs, grow_observer, hard_cap, inspect_program, pool_predictions,
                                psha, read_instances, separation, substituted)
from cora_reach2 import variant as VA

VERSION = "reach-v2-measure"


def object_run(task_id, train, tests, engine_dir, ext=None, budget_s=BUDGET_S, inspect=False, variant=None):  # V2
    """One harness object-layer run with `ext` installed, or nothing.
    Returns (record, accepted program JSON or None)."""
    import geocat_arc.object_reasoning.engine as E
    from harness.object_layer import run_object_task
    HT = _hard_timeout()
    out = {"installed": ext["name"] if ext is not None else None, "budget_s": budget_s, "accepted": False,
           "program_sha": None, "predictions": [None] * len(tests), "timeout": False, "error": None,
           "failure_stage": None, "load_start": _load()}
    seen = []
    orig = E.ObjectReasoningEngine.solve

    def solve(self, tid, pairs):
        r = orig(self, tid, pairs)
        seen.append(r)
        return r
    program = None
    out["caches_cleared"] = clear_engine_caches()
    t0 = time.time()
    E.ObjectReasoningEngine.solve = solve
    try:
        with contextlib.ExitStack() as stack:
            if ext is not None:
                stack.enter_context(BR.installed(ext))
                if variant is not None:  # V2
                    out["variant_first"] = stack.enter_context(VA.variant_first(variant))  # V2
            try:
                with hard_cap(budget_s + CAP_SLACK_S + FRAMES_ALLOWANCE_S):
                    res = run_object_task(task_id, as_task(train, tests), None, out_dir=engine_dir,
                                          budget_s=budget_s)
            except HT:
                res = {"solved": False, "error": "hard_timeout"}
                out["timeout"] = True
            out["engine_seconds"] = round(time.time() - t0, 3)
            sol = seen[-1].solution if seen else None
            accepted = bool(res.get("solved")) and sol is not None
            program = sol.program_json if accepted else None
            out.update(accepted=accepted, program_sha=psha(program), error=res.get("error"),
                       failure_stage=res.get("failure_stage"), best_accuracy=res.get("best_accuracy"))
            if accepted:
                preds = res.get("predictions") or []
                out["predictions"] = [_grid(preds[i]) if i < len(preds) else None for i in range(len(tests))]
            if ext is not None:
                out["uses"] = bool(accepted and BR.uses(program, ext))
                if inspect and accepted:
                    out.update(inspect_program(program, ext, train, tests, out["predictions"]))
    finally:
        E.ObjectReasoningEngine.solve = orig
    if ext is not None:
        out["restored"] = BR.restored()
    out["seconds"] = round(time.time() - t0, 3)
    out["load_end"] = _load()
    return out, program


def loo_fold(key, train, i, full_ext, dirs, budget_s=BUDGET_S) -> dict:
    """One fold of the adaptive leave-one-out: demonstration i removed first,
    then the failure evidence rebuilt (identity-frame extraction on the
    rest), construction, selection, compilation, installation and the same
    reasoner from scratch; the fold succeeds when the reasoner accepts a
    program that uses the fold's extension and reproduces the held-out
    output exactly (v1.8 real_loo: accepted and uses and exact)."""
    HT = _hard_timeout()
    rest = [p for j, p in enumerate(train) if j != i]
    a, b = train[i]
    f = {"fold": i, "class": None, "selected": None, "same_as_full": False, "accepted": False, "uses": False,
         "heldout_exact": False}
    clear_engine_caches()
    t0 = time.time()
    try:
        with hard_cap(EXTRACT_CAP_S):
            _ind, inst = INST.extract(rest, dirs["extract"], budget_s=budget_s)
    except HT:
        f.update({"class": "RESOURCE_EXHAUSTED", "extract_seconds": round(time.time() - t0, 3)})
        return f
    f["extract_seconds"] = round(time.time() - t0, 3)
    f["instances"] = len(inst)
    prop = CN.propose(inst)
    f["proposals"] = [p["ext"]["name"] for p in prop["proposals"]]
    if not prop["proposals"]:
        f["class"] = "NO_PROPOSAL"
        return f
    e = prop["proposals"][0]["ext"]
    f["selected_variant"] = prop["proposals"][0]["variant"]  # V2
    f["selected"] = e["name"]
    f["selected_family"] = e["family"]
    f["same_as_full"] = full_ext is not None and e["name"] == full_ext["name"]
    run, _prog = object_run(f"{key}_loo{i}", rest, [a], dirs["loo"], ext=e, budget_s=budget_s,  # V2
                            variant=f["selected_variant"])  # V2
    exact = bool(run["accepted"] and run["predictions"][0] is not None and run["predictions"][0] == _grid(b))
    f.update(accepted=run["accepted"], uses=bool(run.get("uses")), heldout_exact=exact,
             engine_seconds=run["seconds"], timeout=run["timeout"], program_sha=run["program_sha"],
             restored=run.get("restored"))
    f["class"] = "SUCCESS" if (run["accepted"] and run.get("uses") and exact) else "LOO_FAILURE"
    return f


def run_control(key, arm, prop, train, tests, dirs, fc_ext, budget_s=BUDGET_S) -> dict:
    """A control's first proposal, installed in the same reasoner (no
    leave-one-out), as the pilot's DEMONSTRATION_ONLY and SHUFFLED arms."""
    if not prop.get("proposals"):
        return {"class": "NO_PROPOSAL", "why": prop.get("why")}
    e = prop["proposals"][0]["ext"]
    run, _prog = object_run(f"{key}_{arm.lower()}", train, tests,
                            dirs["demo_only" if arm == "DEMO_ONLY" else "shuffled"], ext=e, budget_s=budget_s,  # V2
                            variant=prop["proposals"][0].get("variant"))  # V2
    return {"class": "INSTALLED", "selected": e["name"], "family": e["family"], "params": e["params"],
            "same_as_fc": fc_ext is not None and e["name"] == fc_ext["name"], "with_e": run}


def run_task(key, task, ctx) -> dict:
    """The fixed policy on one task. ctx: dirs (engine_dirs), instances_dir,
    donor (the next key in sorted order, cyclic), extract_seconds (the
    instances2 extraction of this task) and, for tests only, budget_s.
    K-alone and the controls run on every task where any arm has a
    proposal; the gates, the leave-one-out, the removed and the matched runs
    on every task where the failure-conditioned path has one."""
    t_start = time.time()
    budget = float(ctx.get("budget_s", BUDGET_S))
    dirs = ctx["dirs"]
    train, tests = arrays(task)
    snap = BR.originals()
    row = {"key": key, "version": VERSION, "n_train": len(train), "n_test": len(tests), "gates": {},
           "progression": {k: False for k in PROGRESSION}, "load_start": _load()}
    raw, digest = read_instances(ctx["instances_dir"], key)
    row["evidence"] = {"instances": len(raw), "with_grid": sum(1 for i in raw if i.get("grid") is not None),
                       "sha256": digest}
    fc = CN.propose(raw)
    demo = demo_only_propose(train)
    donor_raw, donor_digest = read_instances(ctx["instances_dir"], ctx["donor"])
    shuf = CN.propose(donor_raw)
    row["fc"] = _proposal_summary(fc)
    row["control_proposals"] = {"DEMO_ONLY": _proposal_summary(demo),
                                "SHUFFLED_FAILURE": dict(_proposal_summary(shuf), donor=ctx["donor"],
                                                         donor_sha256=donor_digest)}
    pr = row["progression"]
    pr["usable_trace"] = row["evidence"]["with_grid"] > 0
    pr["candidate"] = bool(fc["proposals"])
    e = fc["proposals"][0]["ext"] if fc["proposals"] else None
    if any(p["proposals"] for p in (fc, demo, shuf)):
        row["kalone"], _ = object_run(key, train, tests, dirs["kalone"], budget_s=budget)
        row["controls"] = {"DEMO_ONLY": run_control(key, "DEMO_ONLY", demo, train, tests, dirs, e, budget),
                           "SHUFFLED_FAILURE": run_control(key, "SHUFFLED_FAILURE", shuf, train, tests, dirs, e,
                                                           budget)}
    else:
        row["controls"] = {arm: {"class": "NO_PROPOSAL"} for arm in CONTROL_ARMS}
    if e is None:
        row["path_class"], row["activated"] = "NO_PROPOSAL", False
        return _close(row, snap, t_start)
    g = row["gates"]
    row["extension"] = e
    try:
        loaded = GE.load(GE.serialize(e))
        g["compile"] = loaded == e and GE.serialize(loaded) == GE.serialize(e)
    except GE.ExtensionError as exc:
        g["compile"] = False
        row["compile_error"] = str(exc)
    pr["type_check"] = pr["compile"] = g["compile"]
    pr["exact_demo_fit"] = True          # by construction: e reproduces every memorized instance of its variant
    if not g["compile"]:
        row["path_class"], row["activated"] = "COMPILER_FAILURE", False
        return _close(row, snap, t_start)
    v = fc["proposals"][0]["variant"]  # V2
    w1, prog1 = object_run(key, train, tests, dirs["fc"], ext=e, budget_s=budget, inspect=True, variant=v)  # V2
    w2, _ = object_run(key, train, tests, dirs["fc"], ext=e, budget_s=budget, variant=v)  # V2
    row["with_e"] = w1
    row["with_e_repeat"] = {k: w2.get(k) for k in ("accepted", "program_sha", "predictions", "uses", "seconds",
                                                    "timeout", "restored")}
    pr["install"] = bool(w1.get("restored"))
    g["accepted"] = bool(w1["accepted"])
    g["uses"] = bool(w1.get("uses"))
    g["replay"] = bool(w1.get("replays_training"))
    g["attribution"] = bool(w1.get("direct_equals_engine"))
    g["prediction"] = bool(w1["accepted"]) and all(p is not None for p in w1["predictions"])
    g["determinism"] = (w1["accepted"] == w2["accepted"] and w1["program_sha"] == w2["program_sha"]
                        and w1["predictions"] == w2["predictions"])
    pr["engine_acceptance"], pr["use"] = g["accepted"], g["uses"]
    folds = [loo_fold(key, train, i, e, dirs, budget) for i in range(len(train))]
    row["loo"] = {"passed": bool(folds) and all(f["class"] == "SUCCESS" for f in folds),
                  "folds_success": sum(1 for f in folds if f["class"] == "SUCCESS"), "folds": folds}
    g["loo"] = pr["adaptive_loo"] = row["loo"]["passed"]
    if g["accepted"]:
        others = pool_predictions(prog1, e, fc["proposals"], tests)
        row["pool"] = {"size": len(fc["proposals"]), "others": others}
        g["unanimity"] = g["prediction"] and all(m["predictions"] == w1["predictions"] for m in others)
    else:
        row["pool"] = {"size": len(fc["proposals"]), "others": None}
        g["unanimity"] = False
    g["support"] = bool((w1.get("support") or {}).get("ok"))
    row["removed"], _ = object_run(key, train, tests, dirs["removed"], budget_s=budget)
    spent = float(ctx.get("extract_seconds") or 0.0) + float(fc.get("seconds") or 0.0) + float(w1["seconds"])
    mb = round(min(MATCHED_MAX_S, max(MATCHED_MIN_S, spent)), 2)
    row["matched"], _ = object_run(key, train, tests, dirs["matched"], budget_s=mb)
    row["matched"]["spent_s"] = round(spent, 3)
    k = row["kalone"]
    row["unchanged_baseline"] = (row["removed"]["accepted"] == k["accepted"]
                                 and row["removed"]["program_sha"] == k["program_sha"]
                                 and row["removed"]["predictions"] == k["predictions"])
    row["separation"] = separation(fc["proposals"][0], raw, k, row["matched"])
    failed = [cls for gate, cls in GATES if not g.get(gate)]
    row["path_class"] = failed[0] if failed else "ACTIVATED"
    row["activated"] = pr["activation"] = not failed
    row["cora_prediction"] = w1["predictions"] if row["activated"] else None
    row["invariant"] = {"c1_failure_of_K": not k["accepted"],
                        "c2_machine_generated_from_failure": pr["candidate"],
                        "c3_typed_canonical_executable": bool(g["compile"] and pr["install"]),
                        "c4_bounded_separation": row["separation"]["separated"],
                        "c5_adaptive_loo": g["loo"],
                        "c6_to_c8": "not tested in this block (prospective pilot)"}
    return _close(row, snap, t_start)
