"""Reach v1 measurement: one development task through the growth-relation
mechanism, its gates and its controls (docs/CORA_REAL_TASK_REACH_DEV_v1.md,
sections 4.1 and 5.1).

DEVELOPMENT. Nothing here reads a target: the task is the bundle's
demonstrations and unlabelled test inputs, and the adaptive leave-one-out
scores a held-out DEMONSTRATION. The reasoner is the harness object layer
(harness.object_layer.run_object_task: budget 90 s, the frozen library and
learned verbs in its directory, the five chain flags in the environment,
solution None) under the harness hard cap. K is that call with nothing
installed; K + e is the same call inside cora_reach.bridge.installed(e).
Every run starts with the engine's memo caches cleared, in its arm's own
engine directory. Every gate is recorded even after an earlier one failed;
the path class is the class of the first failing gate (the pilot's frozen
order, cora_pilot.reasoner.GATES).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import signal
import sys
import time

import numpy as np

from cora_reach import bridge as BR
from cora_reach import construct as CN
from cora_reach import growth_ext as GE
from cora_reach import instances as INST
from cora_reach import relations as REL

VERSION = "reach-v1-measure"
BUDGET_S = 90.0                       # harness/object_layer.DEFAULT_OBJECT_BUDGET_S
CAP_SLACK_S = 15                      # harness: object_hard_cap_s = budget + 15
FRAMES_ALLOWANCE_S = 7 * 45 + 30      # harness: the 7 dihedral frames at ARC_DIHEDRAL_FRAMES 45
EXTRACT_CAP_S = 450
MATCHED_MIN_S, MATCHED_MAX_S = 90.0, 270.0
SUPPORT_MIN = 2                       # construct.SUPPORT_DEMOS, the fitter's own witness standard
MAX_DEMO_OBJECTS = 64                 # construct.MAX_INSTANCES, for the demonstration-only control
ARMS = ("kalone", "fc", "loo", "extract", "demo_only", "shuffled", "removed", "matched")
CONTROL_ARMS = ("DEMO_ONLY", "SHUFFLED_FAILURE")

PATH_CLASSES = ("RUN_ERROR", "NO_PROPOSAL", "COMPILER_FAILURE", "ENGINE_REJECTION", "ROUTING_FAILURE",
                "ABSTAINED", "LOO_FAILURE", "AMBIGUOUS_CANDIDATES", "INSUFFICIENT_WITNESSES", "ACTIVATED")
#: the activation gates in their frozen order (cora_pilot.reasoner.GATES)
GATES = (("compile", "COMPILER_FAILURE"), ("accepted", "ENGINE_REJECTION"), ("uses", "ROUTING_FAILURE"),
         ("replay", "ROUTING_FAILURE"), ("attribution", "ROUTING_FAILURE"), ("prediction", "ROUTING_FAILURE"),
         ("determinism", "ABSTAINED"), ("loo", "LOO_FAILURE"), ("unanimity", "AMBIGUOUS_CANDIDATES"),
         ("support", "INSUFFICIENT_WITNESSES"))
#: the protocol's progression (section 5), in order
PROGRESSION = ("usable_trace", "candidate", "type_check", "exact_demo_fit", "compile", "install",
               "engine_acceptance", "use", "adaptive_loo", "activation")


# ------------------------------------------------------------------ helpers

def arrays(task):
    train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in task["train"]]
    tests = [np.asarray(p["input"], dtype=int) for p in task["test"]]
    return train, tests


def as_task(train, tests) -> dict:
    return {"train": [{"input": a.tolist(), "output": b.tolist()} for a, b in train],
            "test": [{"input": t.tolist()} for t in tests]}


def _grid(x):
    if x is None:
        return None
    try:
        a = np.asarray(x, dtype=int)
    except (TypeError, ValueError):
        return None
    if a.ndim != 2 or a.size == 0:
        return None
    return [[int(v) for v in row] for row in a.tolist()]


def psha(program) -> str | None:
    """The v1.9 program digest (cora_pilot.reasoner.psha)."""
    return (hashlib.sha256(json.dumps(program, sort_keys=True, default=str).encode()).hexdigest()[:16]
            if program else None)


def _load():
    return [round(x, 2) for x in os.getloadavg()]


def clear_engine_caches() -> int:
    """cora_arc2026.v14_loc.clear_engine_caches, restated so that the reach
    worker does not import the frozen v1.4 machinery: reset every memo cache
    of the engine, so that no run starts warm from an earlier one."""
    cleared = 0
    for name, mod in list(sys.modules.items()):
        if name == "geocat_arc" or name.startswith("geocat_arc."):
            for attr in list(vars(mod).values()):
                fn = getattr(attr, "cache_clear", None)
                if callable(fn) and hasattr(attr, "cache_info"):
                    fn()
                    cleared += 1
    return cleared


def _hard_timeout():
    from harness.run_harness import _HardTimeout
    return _HardTimeout


@contextlib.contextmanager
def hard_cap(seconds):
    """The harness hard cap: SIGALRM raising harness.run_harness._HardTimeout,
    a BaseException, so no `except Exception` inside the engine absorbs it."""
    from harness import run_harness as RH
    if signal.getsignal(signal.SIGALRM) is not RH._alarm_handler:
        signal.signal(signal.SIGALRM, RH._alarm_handler)
    signal.alarm(max(1, int(seconds)))
    try:
        yield
    finally:
        signal.alarm(0)


def engine_dirs(root) -> dict:
    """One engine directory per arm, each with the sealed runs' assets."""
    from cora_pilot import native as N
    return {arm: N.prepare_object_dir(os.path.join(root, arm)) for arm in ARMS}


# ------------------------------------------------------------------ the reasoner

@contextlib.contextmanager
def grow_observer(name):
    """Observation only: every GROW application in mode `name` while
    rendering, as (identity of the rule's action, cells it added)."""
    import geocat_arc.object_reasoning.actions as AC
    from geocat_arc.object_reasoning.types import DeltaType
    inner = AC.ACTION_DISPATCH[DeltaType.GROW]
    seen = []

    def observed(canvas, obj, action, ectx):
        res = inner(canvas, obj, action, ectx)
        try:
            mode = AC._eval_param(action, "mode", obj, ectx)
        except Exception:                                       # noqa: BLE001
            mode = None
        if mode == name:
            before = set(AC.cell_colors_of(obj))
            after = set()
            for o in res or ():
                after |= set(AC.cell_colors_of(o))
            seen.append((id(action), len(after - before)))
        return res
    AC.ACTION_DISPATCH[DeltaType.GROW] = observed
    try:
        yield seen
    finally:
        AC.ACTION_DISPATCH[DeltaType.GROW] = inner


def inspect_program(program, ext, train, tests, preds) -> dict:
    """Inside the bridge: replay of every demonstration, direct execution of
    the serialized program against the engine's predictions (attribution),
    and the growth support contract (protocol section 5.1): on every test
    input e adds at least one cell, and every rule that applies e on a test
    input applied e (adding cells) in at least SUPPORT_MIN demonstrations."""
    import geocat_arc.object_reasoning.actions as AC
    from geocat_arc.object_reasoning.types import program_from_dict
    fresh = program_from_dict(json.loads(json.dumps(program)))
    fn = AC.program_apply_fn(fresh)
    witness, order, replay, direct, fired_tests = {}, {}, [], [], []
    with grow_observer(ext["name"]) as seen:
        for d, (a, b) in enumerate(train):
            del seen[:]
            try:
                got = _grid(fn(a))
            except Exception:                                   # noqa: BLE001
                got = None
            replay.append(got is not None and got == _grid(b))
            for rid, added in seen:
                order.setdefault(rid, len(order))
                if added > 0:
                    witness.setdefault(rid, set()).add(d)
        for t, p in zip(tests, preds):
            del seen[:]
            try:
                got = _grid(fn(t))
            except Exception:                                   # noqa: BLE001
                got = None
            direct.append(got is not None and got == p)
            fired = {}
            for rid, added in seen:
                order.setdefault(rid, len(order))
                fired[rid] = fired.get(rid, 0) + added
            fired_tests.append(fired)
    low = []
    for ti, fired in enumerate(fired_tests):
        if sum(fired.values()) == 0:
            low.append({"test": ti, "rule": None, "witnesses": 0, "why": "e adds no cell"})
        for rid, added in fired.items():
            n = len(witness.get(rid, ()))
            if n < SUPPORT_MIN:
                low.append({"test": ti, "rule": order[rid], "witnesses": n, "added": added})
    return {"replays_training": bool(replay) and all(replay),
            "direct_equals_engine": bool(direct) and all(direct),
            "support": {"ok": not low, "e_cells_per_test": [sum(f.values()) for f in fired_tests],
                        "e_rules": len(order),
                        "witnessed": {str(order[r]): sorted(s) for r, s in witness.items()},
                        "insufficient": low[:20], "insufficient_count": len(low)}}


def object_run(task_id, train, tests, engine_dir, ext=None, budget_s=BUDGET_S, inspect=False):
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


# ------------------------------------------------------------------ construction paths

def components(a) -> list:
    """8-connected components of non-background cells (any colours): the
    demonstration-only control's one fixed segmentation."""
    H, W = a.shape
    seen = np.zeros(a.shape, dtype=bool)
    comps = []
    for r in range(H):
        for c in range(W):
            if a[r, c] == REL.BG or seen[r, c]:
                continue
            comp, stack = set(), [(r, c)]
            seen[r, c] = True
            while stack:
                x, y = stack.pop()
                comp.add((x, y))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        u, v = x + dx, y + dy
                        if 0 <= u < H and 0 <= v < W and not seen[u, v] and a[u, v] != REL.BG:
                            seen[u, v] = True
                            stack.append((u, v))
            comps.append(comp)
    return comps


def demo_only_propose(train, grammar=None) -> dict:
    """DEMONSTRATION_ONLY_CONTROL: the same grammar and limits, built from the
    demonstrations alone, with no trace of the reasoner's failure. Objects are
    the 8-connected non-background components of each input. A setting is
    proposed when no input cell changes and, on every demonstration, the
    union of its added cells over all objects equals exactly the cells that
    are background in the input and not in the output, with at least
    SUPPORT_DEMOS demonstrations adding cells."""
    t0 = time.time()

    def done(proposals, why, tried=0):
        return {"proposals": proposals, "why": why, "settings_tried": tried, "seconds": round(time.time() - t0, 3)}
    demos = []
    for a, b in train:
        if a.shape != b.shape:
            return done([], "shape_change")
        if ((a != REL.BG) & (a != b)).any():
            return done([], "input_cell_changes")
        added = {(int(r), int(c)) for r, c in zip(*np.nonzero((a == REL.BG) & (b != REL.BG)))}
        objs = components(a)
        if len(objs) > MAX_DEMO_OBJECTS:
            return done([], "too_many_objects")
        demos.append((a, objs, added))
    if sum(1 for *_x, A in demos if A) < CN.SUPPORT_DEMOS:
        return done([], "support")
    proposals, tried = [], 0
    for fam, params in REL.settings(grammar if grammar is not None else CN.GRAMMAR):
        tried += 1
        ok = True
        for a, objs, A in demos:
            pred = set()
            for O in objs:
                pred |= REL.apply(fam, params, O, a)
            if pred != A:
                ok = False
                break
        if ok:
            proposals.append({"ext": GE.make(fam, params)})
            if len(proposals) >= CN.MAX_PROPOSALS:
                break
    return done(proposals, None if proposals else "no_setting", tried)


def read_instances(instances_dir, key) -> tuple:
    """(instances, sha256 of the file) of a task's memorized-instance file;
    ([], None) when the task has none."""
    path = os.path.join(instances_dir, f"{key}.json")
    if not os.path.exists(path):
        return [], None
    with open(path, "rb") as handle:
        data = handle.read()
    return json.loads(data)["instances"], hashlib.sha256(data).hexdigest()


def _proposal_summary(prop) -> dict:
    return {"proposals": [{"name": p["ext"]["name"], "family": p["ext"]["family"], "params": p["ext"]["params"],
                           "variant": p.get("variant"), "instances": p.get("instances"), "demos": p.get("demos")}
                          for p in prop.get("proposals") or []],
            "why": prop.get("why"), "variants": prop.get("variants"),
            "settings_tried": prop.get("settings_tried"), "seconds": prop.get("seconds")}


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
    f["selected"] = e["name"]
    f["selected_family"] = e["family"]
    f["same_as_full"] = full_ext is not None and e["name"] == full_ext["name"]
    run, _prog = object_run(f"{key}_loo{i}", rest, [a], dirs["loo"], ext=e, budget_s=budget_s)
    exact = bool(run["accepted"] and run["predictions"][0] is not None and run["predictions"][0] == _grid(b))
    f.update(accepted=run["accepted"], uses=bool(run.get("uses")), heldout_exact=exact,
             engine_seconds=run["seconds"], timeout=run["timeout"], program_sha=run["program_sha"],
             restored=run.get("restored"))
    f["class"] = "SUCCESS" if (run["accepted"] and run.get("uses") and exact) else "LOO_FAILURE"
    return f


def substituted(program, old, new):
    """The program with every constant growth mode `old` replaced by `new`."""
    def walk(v):
        if isinstance(v, dict):
            if v.get("expr_class") == "GrowModeExpr" and v.get("op") == "const" and v.get("args") == [old]:
                return {**v, "args": [new]}
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v
    return walk(program)


def pool_predictions(program, selected, pool, tests) -> list:
    """Every other member of the verified pool, executed in the accepted
    program in place of the selected extension (direct execution, each
    member installed alone)."""
    import geocat_arc.object_reasoning.actions as AC
    from geocat_arc.object_reasoning.types import program_from_dict
    members = []
    for p in pool:
        m = p["ext"]
        if m["name"] == selected["name"]:
            continue
        preds = []
        with BR.installed(m):
            try:
                fn = AC.program_apply_fn(program_from_dict(json.loads(json.dumps(
                    substituted(program, selected["name"], m["name"])))))
            except Exception:                                   # noqa: BLE001
                fn = None
            for t in tests:
                try:
                    preds.append(_grid(fn(t)) if fn is not None else None)
                except Exception:                               # noqa: BLE001
                    preds.append(None)
        members.append({"name": m["name"], "family": m["family"], "params": m["params"], "predictions": preds})
    return members


def separation(fc_prop, raw, kalone, matched) -> dict:
    """The bounded semantic separation of e against K (invariant condition
    4): (i) not a renaming: the engine's own detect_grow (nothing installed)
    falls back to the constant `pattern` on every instance e explains; (ii)
    not a cache: e's body holds only scalar parameters from finite domains,
    no cell literal; (iii) not a bounded composition: K, alone and at
    matched compute, accepts no program on the task. Bounded: (iii) is a
    statement about K's search within these budgets, not a proof."""
    import geocat_arc.object_reasoning.correspondence as CO
    e = fc_prop["ext"]
    native, memorized = [], 0
    for i in raw:
        if str(i.get("variant")) != fc_prop["variant"] or i.get("grid") is None:
            continue
        in_cc = {tuple(c): col for c, col in i["in"]}
        out_cc = {tuple(c): col for c, col in i["out"]}
        added = {c: col for c, col in out_cc.items() if c not in in_cc}
        if not added or len(set(added.values())) != 1:
            continue
        res = CO.detect_grow(in_cc, out_cc, tuple(i["bounds"]), np.asarray(i["grid"]))
        native.append((res or {}).get("mode"))
        memorized += len(added)
        if len(native) >= CN.MAX_INSTANCES:
            break
    non_renaming = bool(native) and all(m == "pattern" for m in native)
    non_caching = all(isinstance(v, (bool, int, str)) for v in e["params"].values())
    non_composition = not kalone["accepted"] and not matched["accepted"]
    return {"non_renaming": non_renaming, "native_modes": sorted({str(m) for m in native}),
            "instances_checked": len(native), "non_caching": non_caching,
            "body_bytes": len(GE.serialize(e)), "memorized_cells": memorized,
            "non_composition_bounded": non_composition,
            "separated": non_renaming and non_caching and non_composition}


def run_control(key, arm, prop, train, tests, dirs, fc_ext, budget_s=BUDGET_S) -> dict:
    """A control's first proposal, installed in the same reasoner (no
    leave-one-out), as the pilot's DEMONSTRATION_ONLY and SHUFFLED arms."""
    if not prop.get("proposals"):
        return {"class": "NO_PROPOSAL", "why": prop.get("why")}
    e = prop["proposals"][0]["ext"]
    run, _prog = object_run(f"{key}_{arm.lower()}", train, tests,
                            dirs["demo_only" if arm == "DEMO_ONLY" else "shuffled"], ext=e, budget_s=budget_s)
    return {"class": "INSTALLED", "selected": e["name"], "family": e["family"], "params": e["params"],
            "same_as_fc": fc_ext is not None and e["name"] == fc_ext["name"], "with_e": run}


# ------------------------------------------------------------------ one task

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
    w1, prog1 = object_run(key, train, tests, dirs["fc"], ext=e, budget_s=budget, inspect=True)
    w2, _ = object_run(key, train, tests, dirs["fc"], ext=e, budget_s=budget)
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


def _close(row, snap, t_start):
    row["restored"] = BR.restored(snap)
    row["seconds"] = round(time.time() - t_start, 3)
    row["load_end"] = _load()
    return row


# ------------------------------------------------------------------ freeze

FROZEN_FILES = ("cora_reach/measure.py", "cora_reach/construct.py", "cora_reach/relations.py",
                "cora_reach/growth_ext.py", "cora_reach/bridge.py", "cora_reach/instances.py",
                "scripts/reach_v1_run.py", "docs/CORA_REAL_TASK_REACH_DEV_v1.md", "harness/object_layer.py",
                "harness/run_harness.py", "cora_pilot/native.py", "cora_pilot/isolation.py",
                "library.json", "learned_verbs.json", "records/pilot_v1/dev_bundle.json")
FROZEN_TREES = ("geocat_arc", "outputs/reach_v1/instances2")


def _file_sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def tree_sha(root) -> str:
    """Digest of a tree's .py and .json files (relative names and bytes),
    __pycache__ excluded."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            if name.endswith((".py", ".json")):
                p = os.path.join(dirpath, name)
                h.update(os.path.relpath(p, root).encode() + b"\0")
                with open(p, "rb") as handle:
                    h.update(handle.read())
                h.update(b"\0")
    return h.hexdigest()


def freeze_state(here) -> dict:
    return {"files": {f: _file_sha(os.path.join(here, f)) for f in FROZEN_FILES},
            "trees": {t: tree_sha(os.path.join(here, t)) for t in FROZEN_TREES},
            "grammar": list(CN.GRAMMAR), "settings": sum(1 for _ in REL.settings(CN.GRAMMAR)),
            "limits": {"max_proposals": CN.MAX_PROPOSALS, "support_demos": CN.SUPPORT_DEMOS,
                       "max_instances": CN.MAX_INSTANCES, "budget_s": BUDGET_S,
                       "object_cap_s": BUDGET_S + CAP_SLACK_S + FRAMES_ALLOWANCE_S,
                       "extract_cap_s": EXTRACT_CAP_S, "matched_s": [MATCHED_MIN_S, MATCHED_MAX_S],
                       "support_min": SUPPORT_MIN, "max_demo_objects": MAX_DEMO_OBJECTS},
            "extension_identity": GE.identity(), "version": VERSION}


def freeze_problems(here, manifest_path) -> list:
    if not os.path.exists(manifest_path):
        return ["no manifest"]
    with open(manifest_path) as handle:
        frozen = json.load(handle)["state"]
    now = freeze_state(here)
    problems = [f"file {f}" for f in FROZEN_FILES if frozen["files"].get(f) != now["files"][f]]
    problems += [f"tree {t}" for t in FROZEN_TREES if frozen["trees"].get(t) != now["trees"][t]]
    problems += [k for k in ("grammar", "settings", "limits", "extension_identity", "version")
                 if frozen.get(k) != now[k]]
    return problems
