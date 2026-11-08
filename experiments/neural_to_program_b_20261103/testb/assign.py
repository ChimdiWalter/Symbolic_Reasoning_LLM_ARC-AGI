"""Target assignment for Test B (PROTOCOL.md sections 3 and 5), fixed from the frozen non-answer inputs before any
search runs. Standard library only; it never opens an answer file.

Frozen implementation rules (the protocol leaves these to the code; tested in tests/test_adversarial.py):
- Donor order: other tasks of the same set, ascending by sha256("donor:" + task id).
- Rule 1: the first task in that order with an attempt-1 grid of the unit's attempt-1 shape. Within that task the
  lowest output index with that shape is the donor output.
- Rule 2: otherwise the first task in that order with a pool candidate of that shape. Within that task the lowest
  output index, then the lowest position in that output's pool (pool order as saved), is the donor.
- Otherwise the unit has no shuffled arm and is "unmatched".
- Random target: palette = the sorted distinct colours of attempt 1; generator random.Random(seed_of("random:" +
  task id + ":" + str(output index))) (common.seed_of); one draw = a whole grid, cells row by row, each
  rng.choice(palette); at most 100 draws; the first draw that differs from attempt 1 is used; otherwise attempt 1
  with its top-left cell set to (that colour + 1) mod 10, recorded as random_degenerate.
- Run order of tasks: ascending by sha256("taskB:" + task id), for the evaluation and the development sets.
- Pool stage: for each evaluation task in run order, each output, each pool candidate in pool order: every valid
  candidate grid that differs from that output's attempt 1 and from earlier candidates of the same output.
"""
import copy
import os

from testb import common as C

MAX_RANDOM_DRAWS = 100
ARMS = ("neural", "shuffled", "random", "no_target")


def random_target(task, j, a1):
    palette = sorted({v for row in a1 for v in row})
    rng = C.rng_for(f"random:{task}:{j}")
    h, w = C.shape(a1)
    for k in range(MAX_RANDOM_DRAWS):
        g = [[rng.choice(palette) for _ in range(w)] for _ in range(h)]
        if g != a1:
            return g, {"random_degenerate": False, "palette_size": len(palette), "random_draws": k + 1}
    g = copy.deepcopy(a1)
    g[0][0] = (g[0][0] + 1) % 10
    return g, {"random_degenerate": True, "palette_size": len(palette), "random_draws": MAX_RANDOM_DRAWS}


def shuffled_target(task, a1, attempts, pools, donor_order):
    """attempts: {task: [attempt-1 grid per output]}; pools: {task: [[candidate grids] per output]}."""
    want = C.shape(a1)
    others = [t for t in donor_order if t != task]
    for t in others:
        for j2, g in enumerate(attempts[t]):
            if C.grid_ok(g) and C.shape(g) == want:
                return copy.deepcopy(g), {"task": t, "output": j2, "source": "attempt_1", "candidate": None,
                                          "rule": 1}
    for t in others:
        for j2, cands in enumerate(pools.get(t, [])):
            for k, g in enumerate(cands):
                if C.grid_ok(g) and C.shape(g) == want:
                    return copy.deepcopy(g), {"task": t, "output": j2, "source": "pool", "candidate": k, "rule": 2}
    return None, None


def build_set(name, tasks, attempts, pools, subgroup_outputs=None):
    """tasks: {task: challenge}. Returns the units of one set in run order, with the assignment denominator."""
    donor_order = C.hashed_order("donor:", list(tasks))
    run_order = C.hashed_order("taskB:", list(tasks))
    units = []
    for t in run_order:
        if len(attempts[t]) != len(tasks[t]["test"]):
            raise SystemExit(f"{name} task {t}: {len(attempts[t])} attempts for {len(tasks[t]['test'])} test outputs")
        for j, a1 in enumerate(attempts[t]):
            if not C.grid_ok(a1):
                raise SystemExit(f"attempt 1 of {name} {t}:{j} is not a valid grid")
            sh, donor = shuffled_target(t, a1, attempts, pools, donor_order)
            rg, rinfo = random_target(t, j, a1)
            u = {"unit": f"{name}.{t}.{j}", "set": name, "task": t, "output": j,
                 "targets": {"neural": copy.deepcopy(a1), "shuffled": sh, "random": rg}, "shuffled_donor": donor,
                 "cohort": sh is not None, **rinfo}
            if subgroup_outputs is not None:
                u["subgroup"] = f"{t}:{j}" in subgroup_outputs
            units.append(u)
    rule = [u["shuffled_donor"]["rule"] if u["shuffled_donor"] else None for u in units]
    den = {"tasks": len(tasks), "units": len(units), "matched_rule_1": rule.count(1), "matched_rule_2": rule.count(2),
           "unmatched": rule.count(None), "random_degenerate": sum(u["random_degenerate"] for u in units),
           "cohort_tasks": len({u["task"] for u in units if u["cohort"]})}
    return {"order": run_order, "donor_order": donor_order, "units": units, "denominators": den}


def arms_of(unit):
    return [a for a in ARMS if a == "no_target" or unit["targets"][a] is not None]


def pool_units(order, attempts, pools):
    out, skipped = [], []
    for t in order:
        for j, cands in enumerate(pools[t]):
            seen = {C.canon(attempts[t][j])}
            for k, g in enumerate(cands):
                if not C.grid_ok(g):
                    skipped.append({"task": t, "output": j, "candidate": k, "reason": "not a valid grid"})
                    continue
                key = C.canon(g)
                if key in seen:
                    skipped.append({"task": t, "output": j, "candidate": k,
                                    "reason": "equals attempt 1 or an earlier candidate of this output"})
                    continue
                seen.add(key)
                out.append({"unit": f"pool.{t}.{j}.{k}", "set": "pool", "task": t, "output": j, "candidate": k,
                            "targets": {"neural": copy.deepcopy(g)}})
    return out, skipped


def _pool_grids(p):
    return [[c.get("grid") for c in o.get("candidates", [])] for o in p["outputs"]]


def load_inputs(paths):
    """paths: role -> absolute path of a pinned non-answer input. Reads nothing else."""
    ch = C.load_json(paths["eval_challenges"])
    sub = C.load_json(paths["eval_attempts"])
    attempts = {t: [o["attempt_1"] for o in sub[t]] for t in ch}
    pools, mism = {}, []
    for t in ch:
        p = C.load_json(os.path.join(paths["eval_pools"], f"{t}.json"))
        pools[t] = _pool_grids(p)
        if len(pools[t]) != len(ch[t]["test"]):
            raise SystemExit(f"pool of {t} has {len(pools[t])} outputs for {len(ch[t]['test'])} test outputs")
        sel = [s.get("attempt_1") for s in p.get("selected") or []]
        if sel != attempts[t]:
            mism.append(t)
    score = C.load_json(paths["cora_only_score"])
    hits = [r for r in score["results"].values() if r.get("file") == paths["cora_only_submission_rel"]]
    if len(hits) != 1:
        raise SystemExit("the score record has no single result for the pinned CORA-only submission")
    correct = set(hits[0]["correct"])
    outputs = {f"{t}:{j}" for t in ch for j in range(len(ch[t]["test"]))}
    if not correct <= outputs:
        raise SystemExit("the score record names outputs outside the evaluation set")
    subgroup = sorted(outputs - correct)
    dev_ch = C.load_json(paths["dev_challenges"])
    tr = C.load_json(paths["training_challenges"])
    bad = sorted(t for t in dev_ch if tr.get(t) != dev_ch[t])
    if bad:
        raise SystemExit(f"development tasks differ from the training set: {bad}")
    dev_attempts, dev_pools = {}, {}
    for t in dev_ch:
        p = C.load_json(os.path.join(paths["dev_pools"], f"{t}.json"))
        dev_attempts[t] = [s.get("attempt_1") for s in p.get("selected") or []]
        dev_pools[t] = _pool_grids(p)
    return {"eval": (ch, attempts, pools), "subgroup_outputs": subgroup, "cora_only_correct": sorted(correct),
            "dev": (dev_ch, dev_attempts, dev_pools), "attempt_mismatch": mism}


def build(paths):
    """The assignment core: a deterministic function of the pinned inputs and this file."""
    d = load_inputs(paths)
    ch, attempts, pools = d["eval"]
    sub = set(d["subgroup_outputs"])
    primary = build_set("eval", ch, attempts, pools, sub)
    dch, dat, dpo = d["dev"]
    dev = build_set("dev", dch, dat, dpo)
    pool, skipped = pool_units(primary["order"], attempts, pools)
    plan = []
    for stage, units in (("primary", primary["units"]), ("development", dev["units"])):
        for u in units:
            plan += [{"arm": f"{u['unit']}.{a}", "stage": stage, "unit": u["unit"], "name": a} for a in arms_of(u)]
    plan += [{"arm": f"{u['unit']}.neural", "stage": "pool", "unit": u["unit"], "name": "neural"} for u in pool]
    return {"primary": primary, "development": dev, "pool": {"units": pool, "skipped": skipped},
            "subgroup": {"outputs": d["subgroup_outputs"], "tasks": sorted({o.split(":")[0] for o in sub})},
            "cora_only_correct": d["cora_only_correct"], "attempt_mismatch_tasks": d["attempt_mismatch"],
            "plan": plan}


def unit_index(core):
    return {u["unit"]: u for part in ("primary", "development") for u in core[part]["units"]} | \
        {u["unit"]: u for u in core["pool"]["units"]}


def arm_spec(core, challenges, arm):
    """The worker's input for one planned arm: the task's demonstrations, its test input x, and the target."""
    u = unit_index(core)[arm["unit"]]
    t = challenges[u["set"] if u["set"] != "pool" else "eval"][u["task"]]
    target = None if arm["name"] == "no_target" else u["targets"][arm["name"]]
    return {"arm": arm["arm"], "stage": arm["stage"], "name": arm["name"], "unit": u["unit"], "task": u["task"],
            "output": u["output"], "demos": [[p["input"], p["output"]] for p in t["train"]],
            "x": t["test"][u["output"]]["input"], "target": target}
