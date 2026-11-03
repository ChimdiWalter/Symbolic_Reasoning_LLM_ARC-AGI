"""Configuration B: merge CAST answers into configuration A's submission, changing attempt 2 only.

  python -m sfb.merge --sub-a A.json --challenges C --cast-dir DIR --tier 0 --out-b B.json [--report R.json]

Policy (frozen per build; the tier comes from the build, default 0):
- Attempt 1 is never changed. It is always configuration A's neural attempt.
- A CAST answer is used only if:
  - its result file has status "OK" (the package's success status);
  - it has one entry per test input;
  - the grid is valid (rectangular, 1..30 x 1..30, ints 0..9).
- Tier 0 (dominance-safe, the default). For a query whose two A attempts are identical, a CAST grid different from
  them replaces attempt 2. That query keeps its only distinct neural answer as attempt 1, so under the official metric
  (any of the two attempts matching scores the query) the query's score cannot fall. Other queries are untouched.
- Tier 1 (off unless the build enables it). For a query whose two A attempts differ, a CAST grid different from both
  replaces attempt 2. This can lose a correct neural attempt 2. It is the earlier `cast_then_runA` combination.
- Anything unexpected keeps A's entry: a missing or unreadable result file, a wrong count, a malformed grid, a missing
  or malformed A entry.
- Self-check before anything is written. B passes the schema check against the challenge file; B's attempt 1 equals
  A's everywhere; every changed query satisfies the tier rule. If any check fails, B is not written and the caller
  keeps A.
"""
import argparse
import copy
import json
import os

ATTEMPTS = ("attempt_1", "attempt_2")


def valid_grid(g):
    if not isinstance(g, list) or not 1 <= len(g) <= 30:
        return False
    w = None
    for row in g:
        if not isinstance(row, list) or not 1 <= len(row) <= 30:
            return False
        if w is None:
            w = len(row)
        elif len(row) != w:
            return False
        for v in row:
            if type(v) is not int or not 0 <= v <= 9:
                return False
    return True


def schema_problems(sub, challenges):
    """The official format: every task id, one entry per test input in order, both attempts valid grids."""
    problems = []
    if not isinstance(sub, dict):
        return ["submission is not a dict"]
    for tid, t in challenges.items():
        e = sub.get(tid)
        if not isinstance(e, list) or len(e) != len(t["test"]):
            problems.append(f"{tid}: wrong entry count")
            continue
        for j, a in enumerate(e):
            if not isinstance(a, dict) or set(a) != set(ATTEMPTS):
                problems.append(f"{tid}[{j}]: keys")
                continue
            for k in ATTEMPTS:
                if not valid_grid(a[k]):
                    problems.append(f"{tid}[{j}].{k}: invalid grid")
    extra = set(sub) - set(challenges)
    if extra:
        problems.append(f"{len(extra)} unknown task ids")
    return problems


def load_cast(cast_dir, tid):
    p = os.path.join(cast_dir, f"{tid}.json")
    try:
        with open(p) as f:
            r = json.load(f)
    except (OSError, ValueError):
        return None
    return r if isinstance(r, dict) else None


def merge(sub_a, challenges, cast_results, tier=0):
    """sub_a: A's submission; cast_results: {task_id: result dict from sfb.cast_side}. Returns (sub_b, report)."""
    if tier not in (0, 1):
        raise ValueError("tier must be 0 or 1")
    sub_b = copy.deepcopy(sub_a)
    rep = {"tier": tier, "outputs": 0, "identical_attempt_outputs": 0, "cast_tasks_ok": 0, "cast_answers": 0,
           "replaced_tier0": 0, "replaced_tier1": 0, "tier1_candidates": 0, "same_as_attempt_1": 0,
           "same_as_attempt_2": 0, "skipped_malformed": 0, "skipped_count": 0, "skipped_a_entry": 0,
           "cast_status": {}, "changes": []}
    for tid, t in challenges.items():
        n = len(t["test"])
        rep["outputs"] += n
        entry = sub_b.get(tid)
        a_ok = isinstance(entry, list) and len(entry) == n and all(
            isinstance(x, dict) and set(x) == set(ATTEMPTS) and valid_grid(x["attempt_1"]) and
            valid_grid(x["attempt_2"]) for x in entry)
        if a_ok:
            rep["identical_attempt_outputs"] += sum(x["attempt_1"] == x["attempt_2"] for x in entry)
        r = cast_results.get(tid)
        if r is None:
            continue
        st = str(r.get("status"))
        rep["cast_status"][st] = rep["cast_status"].get(st, 0) + 1
        if st != "OK":
            continue
        grids = r.get("grids")
        if not isinstance(grids, list) or len(grids) != n:
            rep["skipped_count"] += 1
            continue
        rep["cast_tasks_ok"] += 1
        if not a_ok:
            rep["skipped_a_entry"] += 1
            continue
        for j, g in enumerate(grids):
            if g is None:
                continue
            if not valid_grid(g):
                rep["skipped_malformed"] += 1
                continue
            rep["cast_answers"] += 1
            a1, a2 = entry[j]["attempt_1"], entry[j]["attempt_2"]
            if g == a1:
                rep["same_as_attempt_1"] += 1
                continue
            if a1 == a2:                                    # Tier 0: the two neural attempts are one answer
                entry[j] = {"attempt_1": a1, "attempt_2": g}
                rep["replaced_tier0"] += 1
                rep["changes"].append({"task": tid, "query": j, "tier": 0,
                                       "module": (r.get("module") or [None] * n)[j],
                                       "program": (r.get("program") or [None] * n)[j]})
                continue
            if g == a2:
                rep["same_as_attempt_2"] += 1
                continue
            rep["tier1_candidates"] += 1                    # counted whether or not Tier 1 is enabled
            if tier >= 1:
                entry[j] = {"attempt_1": a1, "attempt_2": g}
                rep["replaced_tier1"] += 1
                rep["changes"].append({"task": tid, "query": j, "tier": 1,
                                       "module": (r.get("module") or [None] * n)[j],
                                       "program": (r.get("program") or [None] * n)[j]})
    return sub_b, rep


def self_check(sub_a, sub_b, challenges, tier):
    """Problems that must stop B from being written (an empty list means B may be written)."""
    problems = schema_problems(sub_b, challenges)
    for tid, t in challenges.items():
        ea, eb = sub_a.get(tid), sub_b.get(tid)
        if not isinstance(ea, list) or not isinstance(eb, list) or len(ea) != len(eb):
            if ea != eb:
                problems.append(f"{tid}: entry changed in length or type")
            continue
        for j, (x, y) in enumerate(zip(ea, eb)):
            if not isinstance(x, dict) or not isinstance(y, dict):
                if x != y:
                    problems.append(f"{tid}[{j}]: entry changed")
                continue
            if x.get("attempt_1") != y.get("attempt_1"):
                problems.append(f"{tid}[{j}]: attempt_1 changed")
            if x.get("attempt_2") != y.get("attempt_2"):
                if tier == 0 and x.get("attempt_1") != x.get("attempt_2"):
                    problems.append(f"{tid}[{j}]: tier 0 changed a query with two different neural attempts")
                if y.get("attempt_2") == y.get("attempt_1"):
                    problems.append(f"{tid}[{j}]: replacement equals attempt_1")
    if set(sub_b) != set(sub_a):
        problems.append("task id set changed")
    return problems


def atomic_json(path, obj):
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def merge_files(sub_a_path, challenges_path, cast_dir, tier, out_b, report_path=None):
    """Writes B to out_b only if every self-check passes. Returns the report (report["ok"] says whether B was
    written)."""
    with open(sub_a_path) as f:
        sub_a = json.load(f)
    with open(challenges_path) as f:
        ch = json.load(f)
    cast = {}
    for tid in ch:
        r = load_cast(cast_dir, tid)
        if r is not None:
            cast[tid] = r
    sub_b, rep = merge(sub_a, ch, cast, tier)
    problems = self_check(sub_a, sub_b, ch, tier)
    rep["problems"] = problems[:20]
    rep["ok"] = not problems
    try:
        with open(os.path.join(cast_dir, "status.json")) as f:
            rep["cast_side_status"] = json.load(f)
    except (OSError, ValueError):
        rep["cast_side_status"] = None
    if rep["ok"]:
        atomic_json(out_b, sub_b)
    if report_path:
        atomic_json(report_path, rep)
    return rep


def policy_tier(policy):
    """0 for "tier0", 1 for "tier1" and "tier1:<rule>"."""
    if policy == "tier0":
        return 0
    if policy == "tier1" or str(policy).startswith("tier1:"):
        return 1
    raise ValueError(f"unknown policy {policy!r}")


def merge_packages(sub_a, challenges, packages, results, insert_fns=None):
    """The constructor hook. packages: ordered [{"name", "mode": "grids"|"evidence", "policy"}]; results:
    {name: {task_id: side-process result}}; insert_fns: {name: the package's insert_attempt2} for evidence packages.
    For every query, the first package (in order) that proposes a new attempt 2 under its own policy wins. Attempt 1
    is never changed. An evidence package's proposal comes from its own insert_attempt2(task, neural, policy,
    report=...), computed against the neural attempts. Any failure for a task keeps A's entry for that task.
    Returns (sub_b, report)."""
    insert_fns = insert_fns or {}
    for pk in packages:
        policy_tier(pk["policy"])
    sub_b = copy.deepcopy(sub_a)
    rep = {"packages": [dict(pk) for pk in packages], "outputs": 0, "identical_attempt_outputs": 0,
           "replaced_tier0": 0, "replaced_tier1": 0, "skipped_a_entry": 0, "per_package": {}, "changes": []}
    for pk in packages:
        rep["per_package"][pk["name"]] = {"status": {}, "tasks_ok": 0, "proposals": 0, "applied": 0,
                                          "same_as_attempt_1": 0, "rejected_output": 0, "errors": 0}
    for tid, t in challenges.items():
        n = len(t["test"])
        rep["outputs"] += n
        entry = sub_b.get(tid)
        a_ok = isinstance(entry, list) and len(entry) == n and all(
            isinstance(x, dict) and set(x) == set(ATTEMPTS) and valid_grid(x["attempt_1"]) and
            valid_grid(x["attempt_2"]) for x in entry)
        if not a_ok:
            rep["skipped_a_entry"] += 1
            continue
        neural = [[x["attempt_1"], x["attempt_2"]] for x in entry]
        rep["identical_attempt_outputs"] += sum(a1 == a2 for a1, a2 in neural)
        changed = [False] * n
        for pk in packages:
            pp = rep["per_package"][pk["name"]]
            r = (results.get(pk["name"]) or {}).get(tid)
            if r is None:
                continue
            st = str(r.get("status"))
            pp["status"][st] = pp["status"].get(st, 0) + 1
            if st != "OK":
                continue
            proposals = [None] * n
            try:
                if pk["mode"] == "evidence":
                    ev = r.get("evidence")
                    if not isinstance(ev, dict) or ev.get("status") != "OK" or \
                            not isinstance(ev.get("queries"), list) or len(ev["queries"]) != n:
                        continue
                    task = {"train": t["train"], "test": [{"input": x["input"]} for x in t["test"]]}
                    out = insert_fns[pk["name"]](task, copy.deepcopy(neural), policy=pk["policy"], report=ev)
                    if not isinstance(out, list) or len(out) != n or any(
                            not isinstance(o, (list, tuple)) or len(o) != 2 or o[0] != neural[j][0]
                            for j, o in enumerate(out)):
                        pp["rejected_output"] += 1
                        continue
                    for j, o in enumerate(out):
                        if o[1] is not None and o[1] != neural[j][1]:
                            proposals[j] = o[1]
                else:
                    grids = r.get("grids")
                    if not isinstance(grids, list) or len(grids) != n:
                        continue
                    tier = policy_tier(pk["policy"])
                    for j, g in enumerate(grids):
                        if g is None or g == neural[j][1]:
                            continue
                        if tier == 0 and neural[j][0] != neural[j][1]:
                            continue
                        proposals[j] = g
            except Exception:                              # noqa: BLE001  this package gives nothing for this task
                pp["errors"] += 1
                continue
            pp["tasks_ok"] += 1
            for j, g in enumerate(proposals):
                if g is None:
                    continue
                pp["proposals"] += 1
                if not valid_grid(g):
                    pp["rejected_output"] += 1
                    continue
                if g == neural[j][0]:
                    pp["same_as_attempt_1"] += 1
                    continue
                if changed[j]:
                    continue
                tier_j = 0 if neural[j][0] == neural[j][1] else 1
                if tier_j > policy_tier(pk["policy"]):
                    pp["rejected_output"] += 1
                    continue
                entry[j] = {"attempt_1": neural[j][0], "attempt_2": g}
                changed[j] = True
                pp["applied"] += 1
                rep["replaced_tier0" if tier_j == 0 else "replaced_tier1"] += 1
                rep["changes"].append({"task": tid, "query": j, "package": pk["name"], "tier": tier_j})
    return sub_b, rep


def merge_files_packages(sub_a_path, challenges_path, packages, out_b, report_path=None, code_dir=None):
    """packages: [{"name", "mode", "policy", "dir"}]. Imports each evidence package's insert_attempt2 by name.
    Writes B to out_b only if every self-check passes; report["ok"] says whether it was written."""
    import importlib
    import sys
    if code_dir and code_dir not in sys.path:
        sys.path.insert(0, code_dir)
    with open(sub_a_path) as f:
        sub_a = json.load(f)
    with open(challenges_path) as f:
        ch = json.load(f)
    results, insert_fns, side = {}, {}, {}
    for pk in packages:
        res = {}
        for tid in ch:
            r = load_cast(pk["dir"], tid)
            if r is not None:
                res[tid] = r
        results[pk["name"]] = res
        if pk["mode"] == "evidence":
            insert_fns[pk["name"]] = importlib.import_module(pk["name"]).insert_attempt2
        try:
            with open(os.path.join(pk["dir"], "status.json")) as f:
                side[pk["name"]] = json.load(f)
        except (OSError, ValueError):
            side[pk["name"]] = None
    sub_b, rep = merge_packages(sub_a, ch, packages, results, insert_fns)
    tier = max(policy_tier(pk["policy"]) for pk in packages) if packages else 0
    problems = self_check(sub_a, sub_b, ch, tier)
    rep.update(problems=problems[:20], ok=not problems, cast_side_status=side, tier=tier)
    if rep["ok"]:
        atomic_json(out_b, sub_b)
    if report_path:
        atomic_json(report_path, rep)
    return rep


def reconcile_guard_output(sub_path, challenges_path, kroot, code_dir):
    """Entry H only (C4's guard; a no-op without exactly one guarded_run_* folder): correct C4's child-path defect.
    The guard's final salvage reads the public file instead of the driver's private child_submission.json. Here C4's
    own, unchanged salvage() runs with the real child path: precedence completed pools > in-flight progress > child
    file > fallback, each query validated. The result replaces the public file only if it passes the full schema
    check. Otherwise the public file stays. Returns a report."""
    import glob
    import sys
    rep = {"applied": False, "reason": None, "changed_queries": 0}
    runs = sorted(glob.glob(os.path.join(kroot, "working", "guarded_run_*")))
    if len(runs) != 1 or not os.path.isdir(runs[0]):
        rep["reason"] = f"{len(runs)} guarded_run folders"
        return rep
    if code_dir and code_dir not in sys.path:
        sys.path.insert(0, code_dir)
    from deployment_guard import salvage
    with open(challenges_path) as f:
        ch = json.load(f)
    with open(sub_path) as f:
        public = json.load(f)
    fixed, recovered = salvage(ch, os.path.join(runs[0], "child_submission.json"), runs[0])
    problems = schema_problems(fixed, ch)
    rep.update(run_dir=runs[0], recovered_queries=recovered, problems=problems[:10])
    if problems:
        rep["reason"] = "salvaged file failed the schema check; public file kept"
        return rep
    rep["changed_queries"] = sum(1 for tid, t in ch.items() for j in range(len(t["test"]))
                                 if not (isinstance(public.get(tid), list) and j < len(public[tid]) and
                                         public[tid][j] == fixed[tid][j]))
    if rep["changed_queries"]:
        atomic_json(sub_path, fixed)
    rep["applied"] = True
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub-a", required=True)
    ap.add_argument("--challenges", required=True)
    ap.add_argument("--cast-dir", required=True)
    ap.add_argument("--tier", type=int, default=0)
    ap.add_argument("--out-b", required=True)
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    rep = merge_files(a.sub_a, a.challenges, a.cast_dir, a.tier, a.out_b, a.report)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("changes", "cast_side_status")}))


if __name__ == "__main__":
    main()
