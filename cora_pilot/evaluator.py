"""The BLIND EVALUATOR (protocol sections 5, 10 and 11).

Runs in its own process after the reasoner's predictions are committed. It
alone reads the evaluator key map, the sha256-pinned training solutions and
the sha256-pinned sealed v23 records, and it never changes a prediction: it
scores what was committed, classifies every task and computes the frozen
outcome.
"""
from __future__ import annotations

import hashlib
import json

SEALED_V23 = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project/outputs/unified_harness_v23/results.json"
SEALED_V23_SHA256 = "763beefdbb7d2ea4dd4ff02da379fbdbe5800951443422fd3b95d138ccfaf931"
SEALED_ARB = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project/outputs/v23_arbitration/results.json"
SEALED_ARB_SHA256 = "35e8f5c9ca351c0cecdaf1db9ae77ba7c12925f820818c09ab9c6007832b200b"
SEALED_COUNT = 185

OUTCOMES = ("PILOT_LEAKAGE", "NO_VERDICT_DATASET", "NO_VERDICT_RUN_ERROR",
            "REAL_ARC_CAUSAL_WITNESS_ESTABLISHED", "NO_REAL_ARC_WITNESS")
TASK_OUTCOMES = ("WRONG_ACTIVATION", "BASELINE_ALREADY_SOLVES", "CORRECT_CAUSAL_RESCUE", "ABLATION_FAILURE",
                 "INTEGRITY_FAILURE", "HELDOUT_MISMATCH", "MISSED_RESCUE", "NO_CHANGE")
RUN_ERROR_MAX_SHARE = 0.10


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_pinned(path, sha):
    got = sha256_file(path)
    if got != sha:
        raise ValueError(f"{path}: sha256 {got} != pinned {sha}")
    with open(path) as handle:
        return json.load(handle)


def sealed_solved() -> set:
    """The sealed 185: v23 in-run solved set plus the two arbitration
    recoveries (RUN_HISTORY 2026-08-19)."""
    a = load_pinned(SEALED_V23, SEALED_V23_SHA256)
    b = load_pinned(SEALED_ARB, SEALED_ARB_SHA256)
    s = {r["task_id"] for r in a["solved"]} | {r["task_id"] for r in b["solved"]}
    if len(s) != SEALED_COUNT:
        raise ValueError(f"sealed set has {len(s)} tasks, not {SEALED_COUNT}")
    return s


def exact(pred, target) -> bool:
    return pred is not None and pred == target


def all_exact(preds, targets) -> bool:
    return (isinstance(preds, list) and len(preds) == len(targets)
            and all(exact(p, t) for p, t in zip(preds, targets)))


def pass2(attempts, targets) -> bool:
    """attempts[i] = [attempt_1, attempt_2] for test input i; the task is
    solved when every test output is matched by one of its two attempts."""
    return (isinstance(attempts, list) and len(attempts) == len(targets)
            and all(any(exact(a, t) for a in (att or [])) for att, t in zip(attempts, targets)))


def native_attempts(native, n):
    a1 = (native or {}).get("attempt_1") or [None] * n
    a2 = (native or {}).get("attempt_2") or [None] * n
    return [[a1[i], a2[i]] for i in range(n)]


def score_task(key, pred, cora_row, targets, in_sealed) -> dict:
    """Every committed prediction scored; the six legs; the task outcome."""
    n = len(targets)
    native_ok = pass2(native_attempts(pred["native"], n), targets)
    system_ok = pass2(pred["system"], targets)
    s = {"native_solved": native_ok, "system_solved": system_ok, "in_sealed_185": in_sealed,
         "kstar_prime_alone_correct": all_exact(pred["kstar_prime_alone"], targets),
         "cora_with_e_correct": all_exact(pred["cora_with_e"], targets),
         "removed_correct": all_exact(pred["removed"], targets),
         "matched_correct": all_exact(pred["matched"], targets),
         "controls_correct": {a: all_exact(v, targets) for a, v in (pred.get("controls") or {}).items()},
         "activated": bool(pred["activated"])}
    c = cora_row or {}
    g = c.get("gates") or {}
    integrity = {
        "determinism": bool(g.get("determinism")),
        "unchanged_baseline": ((c.get("removed") or {}).get("accepted") == (c.get("kstar_prime_alone") or {}).get("accepted")
                               and (c.get("removed") or {}).get("program_sha") == (c.get("kstar_prime_alone") or {}).get("program_sha")
                               and (c.get("removed") or {}).get("predictions") == (c.get("kstar_prime_alone") or {}).get("predictions")),
        "replay": bool(g.get("replay")), "attribution": bool(g.get("attribution")),
        "restored": bool(c.get("restored")) and bool(c.get("snapshot_equal")),
    }
    legs = {"B": not native_ok and not in_sealed,
            "P": (c.get("fc") or {}).get("class") == "SELECTED" and bool(g.get("compile")),
            "U": bool(g.get("accepted")) and bool(g.get("uses")) and integrity["attribution"],
            "L": bool(g.get("loo")),
            "T": s["activated"] and all_exact(pred["cora_prediction"], targets),
            "A": not s["removed_correct"] and not s["matched_correct"]}
    s["legs"], s["integrity"] = legs, integrity
    s["witness"] = s["activated"] and all(legs.values()) and all(integrity.values())
    if s["activated"] and not legs["T"]:
        out = "WRONG_ACTIVATION"
    elif native_ok or in_sealed:
        out = "BASELINE_ALREADY_SOLVES"
    elif s["activated"] and not legs["A"]:
        out = "ABLATION_FAILURE"
    elif s["activated"] and not all(integrity.values()):
        out = "INTEGRITY_FAILURE"
    elif s["activated"]:
        out = "CORRECT_CAUSAL_RESCUE" if s["witness"] else "INTEGRITY_FAILURE"
    elif pred["cora_with_e"] is not None and any(p is not None for p in pred["cora_with_e"]):
        out = "MISSED_RESCUE" if s["cora_with_e_correct"] else "HELDOUT_MISMATCH"
    else:
        out = "NO_CHANGE"
    s["outcome"] = out
    s["mechanism"] = c.get("path_class", "RUN_ERROR")
    return s


def evaluate(keymap, predictions, cora_rows, native_rows, solutions, sealed, isolation, run_ok=True) -> dict:
    """The full scoring and the frozen ladder."""
    keys = sorted(keymap["keys"])
    if sorted(predictions) != keys:
        return {"outcome": "NO_VERDICT_DATASET", "reason": "predictions do not cover exactly the pilot keys"}
    tasks = {}
    for k in keys:
        tid = keymap["keys"][k]["task_id"]
        targets = solutions[tid]
        if len(targets) != keymap["keys"][k]["n_test"]:
            return {"outcome": "NO_VERDICT_DATASET", "reason": f"{k}: test count"}
        tasks[k] = score_task(k, predictions[k], cora_rows.get(k), targets, tid in sealed)
        tasks[k]["stratum"] = keymap["keys"][k]["stratum"]
    n = len(keys)
    count = lambda f: sum(1 for t in tasks.values() if f(t))              # noqa: E731
    native_solved = count(lambda t: t["native_solved"])
    system_solved = count(lambda t: t["system_solved"])
    activated = count(lambda t: t["activated"])
    wrong_act = count(lambda t: t["activated"] and not t["legs"]["T"])
    right_act = count(lambda t: t["activated"] and t["legs"]["T"])
    witnesses = sorted(k for k, t in tasks.items() if t["witness"])
    lost = count(lambda t: t["native_solved"] and not t["system_solved"])
    summary = {
        "tasks": n, "witnesses": len(witnesses), "witness_keys": witnesses,
        "genuine_rescues": len(witnesses),
        "baseline_solves": native_solved,
        "baseline_solves_retained": count(lambda t: t["native_solved"] and t["system_solved"]),
        "activations": activated, "correct_activations": right_act, "incorrect_activations": wrong_act,
        "abstentions_with_prediction": count(lambda t: not t["activated"] and t["outcome"] in
                                             ("MISSED_RESCUE", "HELDOUT_MISMATCH")),
        "additional_correct": count(lambda t: t["system_solved"] and not t["native_solved"]),
        "additional_incorrect": wrong_act, "lost_solves": lost,
        "net_score": system_solved - native_solved,
        "system_solved": system_solved,
        "task_outcomes": {o: count(lambda t, o=o: t["outcome"] == o) for o in TASK_OUTCOMES},
        "mechanisms": {}, "controls": {}}
    for t in tasks.values():
        summary["mechanisms"][t["mechanism"]] = summary["mechanisms"].get(t["mechanism"], 0) + 1
    for arm in ("DEMO_ONLY", "SHUFFLED_FRONTIER"):
        summary["controls"][arm] = {"correct_with_e": count(lambda t, a=arm: t["controls_correct"].get(a)),
                                    "fc_correct_with_e": count(lambda t: t["cora_with_e_correct"])}
    summary["safety"] = ("SAFE" if lost == 0 and wrong_act <= right_act and system_solved >= native_solved
                         else "UNSAFE")
    leak = bool(isolation.get("problems")) or any(
        (r.get("path_class") == "LEAKAGE") for r in cora_rows.values())
    run_errors = count(lambda t: t["mechanism"] == "RUN_ERROR") + sum(
        1 for r in native_rows.values() if r.get("path_class") == "RUN_ERROR")
    if leak:
        outcome = "PILOT_LEAKAGE"
    elif not run_ok or run_errors > RUN_ERROR_MAX_SHARE * n:
        outcome = "NO_VERDICT_RUN_ERROR"
    elif witnesses:
        outcome = "REAL_ARC_CAUSAL_WITNESS_ESTABLISHED"
    else:
        outcome = "NO_REAL_ARC_WITNESS"
    summary["run_errors"] = run_errors
    return {"outcome": outcome, "safety": summary["safety"], "summary": summary, "tasks": tasks}
