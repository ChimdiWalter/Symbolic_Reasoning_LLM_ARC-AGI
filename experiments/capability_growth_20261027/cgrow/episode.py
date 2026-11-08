"""One invention episode (SYSTEM SIDE): the controller decided INVENT_NEW_OPERATION for a failed task; K proposals
from the neural proposer are checked, executed, retried, regression-tested, validated and promoted, quarantined,
rejected or rolled back. Inputs: the motivating task (demonstrations, query inputs), G0, the system's other tasks
(previously solved ones for the regression check, other unsolved ones for validation), and probe grids. No
evaluator knowledge.

Per proposal: parse -> allowlist and substrate check -> self-tests -> novelty check (no G0 program of cost <= 7
reproduces it on the probe grids: not a rename or a trivial wrap) -> retry of the motivating task with G1 = G0 +
the operation (same budget as C0). The first two proposals that make the motivating task fit go to promotion:
regression on every previously solved task (lost fit or a changed first prediction -> ROLLED BACK), then
validation on the other unsolved tasks in a fixed hash order (at least one new fit -> PROMOTED, persistent; none ->
QUARANTINED, task-local). Every failed attempt is kept with its stage and reason.
"""
import hashlib
import time

from cgrow import invent as IV, lang0 as L0, search as S, probes as PR

from a2 import arcdsl as D            # noqa: E402

L_DUP = 7
DUP_BUDGET = 200_000
SIG_PROBES = PR.probe_grids(30, seed=7071, min_side=1, max_side=9)


def grid(g):
    return tuple(tuple(r) for r in g)


def task_io(t):
    return [(grid(a), grid(b)) for a, b in t["train"]], [grid(q) for q in t["test_inputs"]]


def g1_with(g0_builder, op, head):
    g = g0_builder()
    L0.add_production(g, head, op, op.n_params)
    return g


def bindings(op):
    if not op.params:
        return [()]
    p = op.params[0]
    return [(k,) for k in range(p["lo"], min(p["hi"], p["lo"] + 8) + 1)]


def novelty(op, g0_builder, probes):
    """Rename / trivial-wrap check: per parameter binding, does a G0 program of cost <= L_DUP reproduce the op on the
    probe grids where it is defined? Returns (is_duplicate, witnesses)."""
    g0 = g0_builder()
    wit = []
    for ints in bindings(op):
        pairs = [(x, op.apply(x, ints)) for x in probes]
        pairs = [(x, y) for x, y in pairs if y is not None]
        if len(pairs) < 4:
            continue
        r = S.run(g0, pairs[:-1], [pairs[-1][0]], budget=DUP_BUDGET, cpu_cap=10.0, want=1)
        if r["fit"] and r["level_complete"] is not None and r["preds"] and r["preds"][0][0] == pairs[-1][1]:
            wit.append({"binding": list(ints), "g0_program": r["program"], "defined_on": len(pairs)})
    # duplicate only if EVERY binding with enough defined probes is reproduced
    defined = [ints for ints in bindings(op) if sum(op.apply(x, ints) is not None for x in probes) >= 4]
    dup = bool(defined) and len(wit) == len(defined)
    return dup, wit, len(defined)


def signature(op):
    """Behaviour hash on 30 seeded probe grids (all bindings): used only to share regression / validation results
    between proposals that behave identically there (stated approximation)."""
    hh = hashlib.sha256()
    for ints in bindings(op):
        for x in SIG_PROBES:
            hh.update(repr((ints, op.apply(x, ints))).encode())
    return hh.hexdigest()[:16]


def retry(task, g0_builder, op, head, cap=6000):
    train, qs = task_io(task)
    op.reset_cap(cap)
    g1 = g1_with(g0_builder, op, head)
    r = S.run(g1, train, qs)
    r["op_calls"], r["op_capped"] = op.calls, op.capped
    r.pop("program_tree", None)
    return r


def process(ep, replies, task, g0_builder, solved_tasks, unsolved_pool, base_preds, cache, max_candidates=2):
    """Returns the episode record. `solved_tasks`: {id: task} previously solved by G0 (with G0's first prediction in
    base_preds); `unsolved_pool`: [(id, task)] in validation order (motivating task excluded)."""
    t0 = time.process_time()
    rows, fitting = [], []
    for i, rep in enumerate(replies):
        row = {"sample": i, "gen_tokens": rep["gen_tokens"], "finished": rep["finished"]}
        rows.append(row)
        try:
            prop = IV.parse(rep["text"])
        except IV.Rejected as e:
            row.update(stage="parse", outcome=e.kind, message=e.message)
            continue
        row["fields"], row["params"] = prop["fields"], prop["params"]
        row["code_sha256"] = hashlib.sha256(prop["code"].encode()).hexdigest()
        try:
            chk = IV.check(prop)
        except IV.Rejected as e:
            row.update(stage="check", outcome=e.kind, message=e.message)
            continue
        row["check"] = chk
        op = IV.SandboxOp(prop)
        tests = IV.run_tests(op, prop["tests"])
        row["self_tests"] = {"n": len(tests), "passed": sum(t["passed"] is True for t in tests),
                             "failed": sum(t["passed"] is False for t in tests)}
        if not any(op.apply(x, b) is not None for x in SIG_PROBES[:12] for b in bindings(op)[:1]) and \
                not any(op.apply(grid(a), b) is not None for a, _ in task["train"] for b in bindings(op)[:1]):
            row.update(stage="execute", outcome="never_returns_a_grid", errors=op.errors)
            continue
        dup, wit, ndef = novelty(op, g0_builder, SIG_PROBES[:12])
        row["novelty"] = {"duplicate": dup, "witnesses": wit, "bindings_checked": ndef}
        if dup:
            row.update(stage="novelty", outcome="duplicate_of_G0_program")
            continue
        head = "f:inv_" + row["code_sha256"][:10]
        r = retry(task, g0_builder, op, head)
        row["retry"] = {k: r[k] for k in ("fit", "program", "level_complete", "stop", "calls", "cpu_s", "op_calls",
                                          "op_capped", "preds")}
        if not r["fit"]:
            row.update(stage="retry", outcome="no_fit_on_motivating_task")
            continue
        row.update(stage="retry", outcome="fits_motivating_task")
        row["signature"] = signature(op)
        fitting.append((row, prop, chk, tests, op, head))
    promoted = None
    for row, prop, chk, tests, op, head in fitting[:max_candidates]:
        sig = row["signature"]
        if sig in cache:
            dec = dict(cache[sig], shared_from_signature=True)
        else:
            dec = promote_checks(op, head, g0_builder, solved_tasks, unsolved_pool, base_preds)
            cache[sig] = dec
        row["promotion"] = dec
        if dec["decision"] == "promoted":
            promoted = (row, prop, chk, tests, op, head)
            break
    return {"episode": ep, "rows": rows, "n_fitting": len(fitting), "promoted_sample": promoted[0]["sample"]
            if promoted else None, "cpu_s": round(time.process_time() - t0, 2)}, promoted, fitting


def promote_checks(op, head, g0_builder, solved_tasks, unsolved_pool, base_preds):
    lost, changed = [], []
    for tid, t in solved_tasks.items():
        r = retry(t, g0_builder, op, head)
        if not r["fit"]:
            lost.append(tid)
        elif base_preds.get(tid) is not None and (not r["preds"] or base_preds[tid] not in r["preds"]):
            changed.append(tid)
    if lost or changed:
        return {"decision": "rolled_back", "regression": {"checked": len(solved_tasks), "lost_fit": lost,
                                                          "changed_prediction": changed}, "validation": None}
    useful, tried = None, 0
    for tid, t in unsolved_pool:
        tried += 1
        r = retry(t, g0_builder, op, head)
        if r["fit"]:
            useful = {"task": tid, "program": r["program"]}
            break
    return {"decision": "promoted" if useful else "quarantined",
            "regression": {"checked": len(solved_tasks), "lost_fit": [], "changed_prediction": []},
            "validation": {"tried": tried, "first_new_fit": useful}}
