"""The BLIND EVALUATOR of the growth-repair pilot v2 (protocol sections 9 to
11).

Runs in its own process after the reasoner's predictions are committed. It
alone reads the evaluator key map, the sha256-pinned training solutions and
the sealed v23 records (through the v1 evaluator's pinned loaders, unchanged),
and it never changes a prediction. The causal witness is pilot v1's
B/P/U/L/T/A with its integrity conditions; the invention witness adds S
(bounded semantic separation, invariant condition 4) and F (neither control
produces the right output, condition 8).
"""
from __future__ import annotations

from cora_pilot import evaluator as EV1

OUTCOMES = ("PILOT_LEAKAGE", "NO_VERDICT_DATASET", "NO_VERDICT_RUN_ERROR",
            "REAL_ARC_INVENTION_WITNESS_ESTABLISHED", "REAL_ARC_CAUSAL_WITNESS_ESTABLISHED",
            "NO_REAL_ARC_WITNESS")
TASK_OUTCOMES = EV1.TASK_OUTCOMES
RUN_ERROR_MAX_SHARE = EV1.RUN_ERROR_MAX_SHARE
CAUSAL_LEGS = ("B", "P", "U", "L", "T", "A")
CONTROL_ARMS = ("DEMO_ONLY", "SHUFFLED_FAILURE")


def score_task(key, pred, cora_row, targets, in_sealed) -> dict:
    """Every committed prediction scored; the eight legs; the task outcome."""
    n = len(targets)
    native_ok = EV1.pass2(EV1.native_attempts(pred["native"], n), targets)
    system_ok = EV1.pass2(pred["system"], targets)
    s = {"native_solved": native_ok, "system_solved": system_ok, "in_sealed_185": in_sealed,
         "kalone_correct": EV1.all_exact(pred["kalone"], targets),
         "cora_with_e_correct": EV1.all_exact(pred["cora_with_e"], targets),
         "removed_correct": EV1.all_exact(pred["removed"], targets),
         "matched_correct": EV1.all_exact(pred["matched"], targets),
         "controls_correct": {a: EV1.all_exact((pred.get("controls") or {}).get(a), targets)
                              for a in CONTROL_ARMS},
         "activated": bool(pred["activated"])}
    c = cora_row or {}
    g = c.get("gates") or {}
    integrity = {"determinism": bool(g.get("determinism")),
                 "unchanged_baseline": bool(c.get("unchanged_baseline")),
                 "replay": bool(g.get("replay")), "attribution": bool(g.get("attribution")),
                 "restored": bool(c.get("restored"))}
    legs = {"B": not native_ok and not in_sealed,
            "P": bool((c.get("fc") or {}).get("proposals")) and bool(g.get("compile")),
            "U": bool(g.get("accepted")) and bool(g.get("uses")) and integrity["attribution"],
            "L": bool(g.get("loo")),
            "T": s["activated"] and EV1.all_exact(pred["cora_prediction"], targets),
            "A": not s["removed_correct"] and not s["matched_correct"],
            "S": bool((c.get("separation") or {}).get("separated")),
            "F": not any(s["controls_correct"].values())}
    s["legs"], s["integrity"] = legs, integrity
    s["witness"] = s["activated"] and all(legs[x] for x in CAUSAL_LEGS) and all(integrity.values())
    s["invention_witness"] = s["witness"] and legs["S"] and legs["F"]
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
    """The full scoring and the frozen ladder (pilot v1 section 11, with the
    invention rung above the causal one)."""
    keys = sorted(keymap["keys"])
    leak = bool(isolation.get("problems"))
    no_verdict = "PILOT_LEAKAGE" if leak else "NO_VERDICT_DATASET"
    if sorted(predictions) != keys:
        return {"outcome": no_verdict, "reason": "predictions do not cover exactly the pilot keys"}
    tasks = {}
    for k in keys:
        tid = keymap["keys"][k]["task_id"]
        targets = solutions[tid]
        if len(targets) != keymap["keys"][k]["n_test"]:
            return {"outcome": no_verdict, "reason": f"{k}: test count"}
        tasks[k] = score_task(k, predictions[k], cora_rows.get(k), targets, tid in sealed)
        tasks[k]["stratum"] = keymap["keys"][k]["stratum"]
    n = len(keys)
    count = lambda f: sum(1 for t in tasks.values() if f(t))              # noqa: E731
    native_solved = count(lambda t: t["native_solved"])
    system_solved = count(lambda t: t["system_solved"])
    wrong_act = count(lambda t: t["activated"] and not t["legs"]["T"])
    right_act = count(lambda t: t["activated"] and t["legs"]["T"])
    witnesses = sorted(k for k, t in tasks.items() if t["witness"])
    inventions = sorted(k for k, t in tasks.items() if t["invention_witness"])
    lost = count(lambda t: t["native_solved"] and not t["system_solved"])
    summary = {
        "tasks": n, "witnesses": len(witnesses), "witness_keys": witnesses,
        "invention_witnesses": len(inventions), "invention_witness_keys": inventions,
        "genuine_rescues": len(witnesses),
        "baseline_solves": native_solved,
        "baseline_solves_retained": count(lambda t: t["native_solved"] and t["system_solved"]),
        "activations": count(lambda t: t["activated"]), "correct_activations": right_act,
        "incorrect_activations": wrong_act,
        "abstentions_with_prediction": count(lambda t: not t["activated"] and t["outcome"] in
                                             ("MISSED_RESCUE", "HELDOUT_MISMATCH")),
        "additional_correct": count(lambda t: t["system_solved"] and not t["native_solved"]),
        "additional_incorrect": wrong_act, "lost_solves": lost,
        "net_score": system_solved - native_solved, "system_solved": system_solved,
        "legs": {x: count(lambda t, x=x: t["legs"][x]) for x in CAUSAL_LEGS + ("S", "F")},
        "task_outcomes": {o: count(lambda t, o=o: t["outcome"] == o) for o in TASK_OUTCOMES},
        "mechanisms": {}, "controls": {}}
    for t in tasks.values():
        summary["mechanisms"][t["mechanism"]] = summary["mechanisms"].get(t["mechanism"], 0) + 1
    for arm in CONTROL_ARMS:
        summary["controls"][arm] = {"correct_with_e": count(lambda t, a=arm: t["controls_correct"][a])}
    summary["controls"]["FAILURE_CONDITIONED"] = {"correct_with_e": count(lambda t: t["cora_with_e_correct"])}
    summary["safety"] = ("SAFE" if lost == 0 and wrong_act <= right_act and system_solved >= native_solved
                         else "UNSAFE")
    run_errors = count(lambda t: t["mechanism"] == "RUN_ERROR") + sum(
        1 for r in native_rows.values() if r.get("path_class") == "RUN_ERROR")
    if leak:
        outcome = "PILOT_LEAKAGE"
    elif not run_ok or run_errors > RUN_ERROR_MAX_SHARE * n:
        outcome = "NO_VERDICT_RUN_ERROR"
    elif inventions:
        outcome = "REAL_ARC_INVENTION_WITNESS_ESTABLISHED"
    elif witnesses:
        outcome = "REAL_ARC_CAUSAL_WITNESS_ESTABLISHED"
    else:
        outcome = "NO_REAL_ARC_WITNESS"
    summary["run_errors"] = run_errors
    return {"outcome": outcome, "safety": summary["safety"], "summary": summary, "tasks": tasks}
