"""The same-reasoner closed loop on one real task (protocol sections 6 to 8).

Steps B to J for one task under the frozen components only: the v1.8
proposer (failure frontier, proposals, verification, selection), the v1.7
compiler, K*' = K* + K*-4 (cora_v19.v19_repair) as the same reasoner, and
the v1.8 adaptive leave-one-out run under K*' exactly as in the v1.9
prospective test. Nothing here reads a target: the task is the bundle's
demonstrations and unlabelled test inputs. The activation decision uses
training evidence and the test INPUTS only, and every gate is recorded
whether or not an earlier one failed.
"""
from __future__ import annotations

import hashlib
import json
import time

import numpy as np

from cora_arc2026 import v17_compiler as X
from cora_arc2026 import v18_proposer as P
from cora_v19 import v19_repair as R

VERSION = "real-arc-pilot-v1"
MATCHED_MIN_S = 24.0          # the frozen A-leg budget of v1.8 and v1.9 (3 x 8 s)
MATCHED_MAX_S = 240.0
SUPPORT_MIN = 2               # the fitter's own witness standard (MIN_KEY_WITNESSES)
CONTROL_ARMS = ("DEMO_ONLY", "SHUFFLED_FRONTIER")

PATH_CLASSES = ("RUN_ERROR", "LEAKAGE", "RESOURCE_EXHAUSTED", "NO_PROPOSAL", "NO_VERIFIED_PROPOSAL",
                "AMBIGUOUS_CANDIDATES", "COMPILER_FAILURE", "ENGINE_REJECTION", "ROUTING_FAILURE",
                "ABSTAINED", "LOO_FAILURE", "INSUFFICIENT_WITNESSES", "ACTIVATED")
PROPOSER_CLASS = {"K_ALREADY_SOLVES": "NO_PROPOSAL", "NO_PROPOSAL": "NO_PROPOSAL",
                  "PROPOSAL_LIMIT": "NO_VERIFIED_PROPOSAL", "NO_VERIFIABLE_PROPOSAL": "NO_VERIFIED_PROPOSAL",
                  "UNTYPEABLE_PROPOSAL": "COMPILER_FAILURE", "SELECTION_ABSTAINED": "AMBIGUOUS_CANDIDATES",
                  "LEAKAGE_FAILURE": "LEAKAGE", "RESOURCE_EXHAUSTED": "RESOURCE_EXHAUSTED"}
#: the activation gates in their frozen order; the path class is the class
#: of the first gate that fails
GATES = (("compile", "COMPILER_FAILURE"), ("accepted", "ENGINE_REJECTION"), ("uses", "ROUTING_FAILURE"),
         ("replay", "ROUTING_FAILURE"), ("attribution", "ROUTING_FAILURE"), ("prediction", "ROUTING_FAILURE"),
         ("determinism", "ABSTAINED"), ("loo", "LOO_FAILURE"), ("unanimity", "AMBIGUOUS_CANDIDATES"),
         ("support", "INSUFFICIENT_WITNESSES"))


def psha(program) -> str | None:
    """The v1.9 program digest (scripts/v19_repair_dev.psha)."""
    return (hashlib.sha256(json.dumps(program, sort_keys=True, default=str).encode()).hexdigest()[:16]
            if program else None)


def arrays(task):
    train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in task["train"]]
    tests = [np.asarray(p["input"], dtype=int) for p in task["test"]]
    return train, tests


def _grid(x):
    if x is None or not isinstance(x, np.ndarray) or x.ndim != 2 or x.size == 0:
        return None
    return [[int(v) for v in row] for row in x.tolist()]


def predict(run, tests) -> list:
    if not run["accepted"]:
        return [None] * len(tests)
    out = []
    for t in tests:
        try:
            out.append(_grid(np.asarray(run["apply_fn"](t))))
        except Exception:                                       # noqa: BLE001
            out.append(None)
    return out


def summary(run, tests, prod=None, train=None) -> dict:
    out = {"accepted": run["accepted"], "program_sha": psha(run["program"]),
           "seconds": run["seconds"], "events": len(run.get("events") or []),
           "predictions": predict(run, tests), "engine_dir_removed": run.get("engine_dir_removed")}
    if prod is not None:
        out["uses"] = bool(run["accepted"] and X.uses_extension(run["program"], prod))
    if run["accepted"] and train is not None:
        out["replays_training"] = all(X.predict_exact(run, a, b) for a, b in train)
        d = run["program"]
        direct = []
        if d.get("program_class") == "computed_pattern":
            M, MI = X._meta()
            for t, pred in zip(tests, out["predictions"]):
                try:
                    g = _grid(M.evaluate(M.ast_from_json(d["ast"]), np.asarray(t), MI.descriptors))
                    direct.append(g is not None and g == pred)
                except Exception:                               # noqa: BLE001
                    direct.append(False)
        out["direct_equals_engine"] = bool(direct) and all(direct)
    return out


def candidate_pool(train, tests) -> dict:
    """The proposer's verified, behaviour-deduplicated pool, rebuilt with the
    frozen functions exactly as the v1.9 false-acceptance control rebuilt it,
    and each member's fitter prediction of every test input."""
    t0 = time.time()
    sem = P.Semantics(train)
    inp = P.build_input(train, sem)
    deadline = t0 + P.LIMITS["wall_s"]
    verified = []
    for depth in P.LIMITS["depths"]:
        gen = P.propose(inp, depth, sem, deadline)
        verified = P.verify(gen["proposals"], sem, deadline)
        if verified:
            break
    pool = P.dedupe(verified, deadline)
    members = []
    for c in pool:
        preds = []
        for t in tests:
            try:
                preds.append(_grid(P._evaluate(c["fitted"], t)))
            except Exception:                                   # noqa: BLE001
                preds.append(None)
        members.append({"canonical": c["canonical"], "predictions": preds})
    return {"size": len(members), "members": members, "seconds": round(time.time() - t0, 3)}


def key_support(schema, train, tests) -> dict:
    """Witness support of the test inputs: for every block of the extension
    and every region the block selects on a test input, the number of
    demonstrations in which the same block selects a region with the same
    key. Conservative by design: every selected region counts, painted or
    not, owned or overwritten."""
    M, MI = X._meta()
    SF = X._sf()
    blocks = SF._blocks(schema)
    witness = {}
    for d, (a, _b) in enumerate(train):
        for bi, (part, preds, feat, _slot) in enumerate(blocks):
            for cells in SF._selected_sets(part, preds, a) or ():
                k = MI.descriptors(cells, a).get(feat)
                witness.setdefault((bi, repr(k)), set()).add(d)
    need, low = [], []
    for ti, t in enumerate(tests):
        for bi, (part, preds, feat, _slot) in enumerate(blocks):
            sets = SF._selected_sets(part, preds, t)
            if not sets:
                low.append({"test": ti, "block": bi, "key": None, "witnesses": 0, "why": "no region"})
                continue
            for cells in sets:
                k = MI.descriptors(cells, t).get(feat)
                n = len(witness.get((bi, repr(k)), ()))
                need.append(n)
                if k is None or n < SUPPORT_MIN:
                    low.append({"test": ti, "block": bi, "key": repr(k), "witnesses": n})
    return {"ok": not low, "min_witnesses": min(need) if need else 0, "regions": len(need),
            "insufficient": low[:20], "insufficient_count": len(low)}


def _loo_summary(loo) -> dict:
    return {"passed": loo["passed"], "folds_success": loo["folds_success"],
            "folds": [{k: f.get(k) for k in ("fold", "class", "proposer_class", "selected", "accepted",
                                             "uses", "heldout_exact", "production", "proposer_seconds",
                                             "engine_seconds")} for f in loo["folds"]]}


def _control(train, tests, arm, donor_failure) -> dict:
    if arm == "SHUFFLED_FRONTIER" and donor_failure is None:
        return {"class": "NO_DONOR"}
    rec = P.solve(train, arm, donor_failure=donor_failure if arm == "SHUFFLED_FRONTIER" else None)
    out = {"class": rec["class"], "seconds": rec["seconds"],
           "selected": rec["selected"]["canonical"] if rec.get("selected") else None}
    if rec["class"] != "SELECTED":
        return out
    try:
        prod = P.compile_selected(rec)
    except X.CompileError as exc:
        out["compile_error"] = exc.code
        return out
    run = R.run_reasoner(train, (prod,))
    out.update(production=prod["name"], **{"with_e": summary(run, tests, prod, train)})
    return out


def run_cora(key: str, task: dict, donor_failure=None) -> dict:
    """Steps B to J for one task; returns the committed row."""
    t_start = time.time()
    train, tests = arrays(task)
    row = {"key": key, "version": VERSION, "n_train": len(train), "n_test": len(tests), "gates": {}}
    snap0 = X.state_snapshot()
    #  KSTAR_PRIME_WITHOUT_EXTENSION: the same reasoner with nothing installed
    row["kstar_prime_alone"] = summary(R.run_reasoner(train, ()), tests)
    #  B, C, E: failure analysis, proposal, verification and selection (v1.8)
    fc = P.solve(train, "FAILURE_CONDITIONED")
    row["fc"] = {"class": fc["class"], "k_class": fc.get("k_class"), "partial_tops": fc.get("partial_tops"),
                 "proposals": fc.get("proposals"), "selection": fc.get("selection"),
                 "seconds": fc["seconds"], "input_sha256": fc.get("input_sha256"),
                 "selected": fc["selected"]["canonical"] if fc.get("selected") else None,
                 "level": (fc.get("selection") or {}).get("level")}
    #  controls, run on every task
    row["controls"] = {}
    for arm in CONTROL_ARMS:
        try:
            row["controls"][arm] = _control(train, tests, arm, donor_failure)
        except Exception as exc:                                # noqa: BLE001
            row["controls"][arm] = {"class": "RUN_ERROR", "error": type(exc).__name__}
    if fc["class"] != "SELECTED":
        row["path_class"] = PROPOSER_CLASS.get(fc["class"], "RUN_ERROR")
        row["activated"] = False
        return _close(row, snap0, t_start)
    g = row["gates"]
    #  D: compile with the frozen compiler
    try:
        prod = P.compile_selected(fc)
        g["compile"] = True
        row["production"] = prod["name"]
    except X.CompileError as exc:
        g["compile"] = False
        row["compile_error"] = exc.code
        row["path_class"], row["activated"] = "COMPILER_FAILURE", False
        return _close(row, snap0, t_start)
    #  G, H: install into K*' and rerun the same reasoner, twice (determinism)
    run1 = R.run_reasoner(train, (prod,))
    run2 = R.run_reasoner(train, (prod,))
    w1, w2 = summary(run1, tests, prod, train), summary(run2, tests, prod, train)
    row["with_e"], row["with_e_repeat"] = w1, {k: w2.get(k) for k in ("accepted", "program_sha", "predictions",
                                                                       "uses", "seconds")}
    g["accepted"] = bool(w1["accepted"])
    g["uses"] = bool(w1.get("uses"))
    g["replay"] = bool(w1.get("replays_training"))
    g["attribution"] = bool(w1.get("direct_equals_engine"))
    g["prediction"] = bool(w1["accepted"]) and all(p is not None for p in w1["predictions"])
    g["determinism"] = (w1["accepted"] == w2["accepted"] and w1["program_sha"] == w2["program_sha"]
                        and w1["predictions"] == w2["predictions"])
    #  L: adaptive leave-one-out under K*' (proposal rebuilt in every fold)
    with R.repaired():
        loo = P.real_loo(train)
    row["loo"] = _loo_summary(loo)
    g["loo"] = bool(loo["passed"])
    #  E, F: prediction disagreement across the verified pool, witness support
    try:
        pool = candidate_pool(train, tests)
        row["pool"] = {"size": pool["size"], "seconds": pool["seconds"],
                       "distinct_per_test": [len({json.dumps(m["predictions"][i]) for m in pool["members"]})
                                             for i in range(len(tests))],
                       "canonicals": [m["canonical"] for m in pool["members"]][:32]}
        g["unanimity"] = (pool["size"] >= 1 and g["prediction"] and
                          all(m["predictions"] == w1["predictions"] for m in pool["members"]))
    except P.ResourceExhausted:
        row["pool"] = {"error": "RESOURCE_EXHAUSTED"}
        g["unanimity"] = False
    try:
        row["support"] = key_support(fc["selected_schema"], train, tests)
        g["support"] = bool(row["support"]["ok"])
    except Exception as exc:                                    # noqa: BLE001
        row["support"] = {"error": type(exc).__name__}
        g["support"] = False
    #  A: the extension removed (the same reasoner, nothing installed) and
    #  matched additional compute without the extension
    row["removed"] = summary(R.run_reasoner(train, ()), tests)
    spent = float(fc["seconds"] or 0.0) + float(w1["seconds"] or 0.0)
    budget = round(min(MATCHED_MAX_S, max(MATCHED_MIN_S, spent)), 2)
    row["matched"] = dict(summary(R.run_reasoner(train, (), budget_s=budget), tests), budget_s=budget)
    #  F: the activation decision (train-only)
    failed = [cls for gate, cls in GATES if not g.get(gate)]
    row["path_class"] = failed[0] if failed else "ACTIVATED"
    row["activated"] = not failed
    row["cora_prediction"] = w1["predictions"] if row["activated"] else None
    return _close(row, snap0, t_start)


def _close(row, snap0, t_start):
    #  J: the extension is gone and the state is restored
    row["restored"] = R.restored() and not X._STATE["active"] and not X._STATE["overlay"]
    row["snapshot_equal"] = X.state_snapshot() == snap0
    row["seconds"] = round(time.time() - t_start, 3)
    return row


def donor_failure(bundle_tasks: dict, key: str) -> dict:
    """The fixed derangement of the SHUFFLED_FAILURE_CONTROL: a task's donor
    is the next key in sorted order (cyclic); the donor's failure is built
    from the donor's demonstrations by the frozen proposer input."""
    keys = sorted(bundle_tasks)
    donor = keys[(keys.index(key) + 1) % len(keys)]
    train, _ = arrays(bundle_tasks[donor])
    try:
        return {"donor": donor, "failure": P.build_input(train)["failure"]}
    except Exception as exc:                                    # noqa: BLE001
        return {"donor": donor, "failure": None, "error": type(exc).__name__}
