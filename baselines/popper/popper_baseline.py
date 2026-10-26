"""Popper baseline (descriptive, not frozen): inductive logic programming on ARC puzzles, compared with CORA.

Popper (Cropper and Morel, "Learning programs by learning from failures", 2021; MIT licence) learns a logic program
from background facts and positive and negative examples. Here it learns `new_color(Object, Colour)` for puzzles whose
every change is a whole object recoloured or deleted:

- objects: native CORA segmentation, view S1 (same colour, 4-connected), one integer id per object;
- background facts per object, from the native object: has_color/2, has_size/2, has_height/2, has_width/2; the flags
  single, line, rect, hole (native is_line, is_rectangle, has_hole), touches_border, unique_color, largest, smallest,
  each with an explicit negation not_<flag> (Popper's clauses have no negation of their own); the relations above,
  left_of, adjacent, inside (defined in `facts`); one constant predicate per colour and per number seen (c3(3).);
- examples: for every demonstration object with output colour t: pos(new_color(o, t)) when t differs from its colour,
  and neg(new_color(o, c)) for every other colour c of the puzzle's palette;
- prediction: the learned program runs in SWI-Prolog on the test input's facts; an object with exactly one derived
  colour is painted with it (deletion = the background colour); no derived colour leaves it unchanged; several
  different colours leave it unchanged and are counted as ambiguous. The second attempt equals the first.

Puzzles outside that class are counted as not encodable, never forced. The solver step never reads an expected
output: `score` is the only reader. The 34 real puzzles are exposed public training puzzles (development evidence);
the generated puzzles come from CORA's own families.

  nice -n 10 python baselines/popper/popper_baseline.py run real|synv2|synv3 [--same-grid]
  python baselines/popper/popper_baseline.py score

`--same-grid` is a sensitivity variant added after the primary results: it adds same_grid/2, so that a rule can name
another object of the same picture ("the colour of the largest object").
"""
import json
import multiprocessing as mp
import os
import re
import resource
import subprocess
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)

POPPER_ENV = "/home/cnptp/.venvs/popper_env"
POPPER_SRC = "/home/cnptp/downloads_popper_20261025/popper_src"
OUT = os.path.join(HERE, "outputs", "popper_baseline")
REAL_IDS = os.path.join(HERE, "outputs", "neural_cora_realarc_g2g3g4", "eligibility", "eligible_ids_20261021.json")
SYN_SCORES = {"synv2": os.path.join(HERE, "outputs", "neural_cora_v2g2", "synthetic_eval", "score.json"),
              "synv3": os.path.join(HERE, "outputs", "neural_cora_v2g3", "synthetic_eval", "score.json")}
VIEW = "S1"
POPPER_TIMEOUT = 60
SAMPLE_MAX_SEED = 6                     # generated puzzles: Popper runs on seeds 1..6 of every encodable family
FLAGS = ("single", "line", "rect", "hole", "touches_border", "unique_color", "largest", "smallest")
NUMS = ("has_size", "has_height", "has_width")
RELS = ("above", "left_of", "adjacent", "inside")
DECL = [f":- dynamic {p}/1." for f in FLAGS for p in (f, "not_" + f)] + \
       [f":- dynamic {p}/2." for p in ("has_color",) + NUMS + RELS + ("same_grid",)]
# "" = the primary encoding; "_samegrid" = a sensitivity variant chosen after the primary results, adding
# same_grid/2 (two different objects of one grid), so a rule can name another object of the same picture
VARIANT = ""


# ------------------------------------------------------------------ objects and facts
def objects(grid):
    from cora_neural_v2g3 import scene as SC
    objs, bg = SC.native_objects(grid, VIEW)
    out = []
    for o in objs:
        r0, c0, r1, c1 = (int(v) for v in o.bounding_box)                  # half-open box
        out.append({"cells": frozenset(tuple(int(v) for v in x) for x in o.cells), "color": int(o.color),
                    "size": int(o.size), "r0": r0, "c0": c0, "r1": r1 - 1, "c1": c1 - 1,
                    "line": bool(o.is_line), "rect": bool(o.is_rectangle), "hole": bool(o.has_hole)})
    return out, int(bg)


def facts(grid, obs, base):
    H, W = np.asarray(grid).shape
    sizes = [o["size"] for o in obs]
    F = []
    for j, o in enumerate(obs):
        i = base + j
        h, w = o["r1"] - o["r0"] + 1, o["c1"] - o["c0"] + 1
        F += [f"has_color({i},{o['color']}).", f"has_size({i},{o['size']}).", f"has_height({i},{h}).",
              f"has_width({i},{w})."]
        flag = {"single": o["size"] == 1, "line": o["line"], "rect": o["rect"], "hole": o["hole"],
                "touches_border": o["r0"] == 0 or o["c0"] == 0 or o["r1"] == H - 1 or o["c1"] == W - 1,
                "unique_color": sum(p["color"] == o["color"] for p in obs) == 1,
                "largest": o["size"] == max(sizes), "smallest": o["size"] == min(sizes)}
        F += [f"{f}({i})." if flag[f] else f"not_{f}({i})." for f in FLAGS]
    for a, oa in enumerate(obs):
        nb = {(r + dr, c + dc) for r, c in oa["cells"] for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0))}
        for b, ob in enumerate(obs):
            if a == b:
                continue
            ia, ib = base + a, base + b
            if oa["r1"] < ob["r0"] and oa["c0"] <= ob["c1"] and ob["c0"] <= oa["c1"]:
                F.append(f"above({ia},{ib}).")                             # strictly above, sharing a column
            if oa["c1"] < ob["c0"] and oa["r0"] <= ob["r1"] and ob["r0"] <= oa["r1"]:
                F.append(f"left_of({ia},{ib}).")                           # strictly left, sharing a row
            if nb & ob["cells"]:
                F.append(f"adjacent({ia},{ib}).")                          # a 4-neighbour cell of a belongs to b
            if ob["r0"] < oa["r0"] and oa["r1"] < ob["r1"] and ob["c0"] < oa["c0"] and oa["c1"] < ob["c1"]:
                F.append(f"inside({ia},{ib}).")                            # a's box strictly inside b's box
            if VARIANT == "_samegrid":
                F.append(f"same_grid({ia},{ib}).")
    return F


def encodable(task):
    """(True, '') when every demonstration is same-shape and every change is a whole object recoloured or deleted."""
    changed = False
    for a, b in task["train"]:
        A, B = np.asarray(a), np.asarray(b)
        if A.shape != B.shape:
            return False, "output size differs"
        obs, _ = objects(a)
        covered = np.zeros(A.shape, bool)
        for o in obs:
            if len({int(B[x]) for x in o["cells"]}) != 1:
                return False, "part of an object changes"
            for x in o["cells"]:
                covered[x] = True
        if ((A != B) & ~covered).any():
            return False, "background cells change"
        changed |= bool((A != B).any())
    return (True, "") if changed else (False, "nothing changes")


def write_task(task, d):
    palette = sorted({int(v) for a, b in task["train"] for g in (a, b) for row in g for v in row} |
                     {int(v) for g in task["test_inputs"] for row in g for v in row})
    bk, exs, nums = [], [], set()
    for i, (a, b) in enumerate(task["train"]):
        obs, _ = objects(a)
        base = 1000 * (i + 1)
        bk += facts(a, obs, base)
        nums |= {v for o in obs for v in (o["size"], o["r1"] - o["r0"] + 1, o["c1"] - o["c0"] + 1)}
        B = np.asarray(b)
        for j, o in enumerate(obs):
            t = int(B[next(iter(o["cells"]))])
            if t != o["color"]:
                exs.append(f"pos(new_color({base + j},{t})).")
            exs += [f"neg(new_color({base + j},{c}))." for c in palette if c != t]
    consts = [(f"c{c}", c, "col") for c in palette] + [(f"n{v}", v, "num") for v in sorted(nums)]
    bias = ["max_vars(5).", "max_body(6).", "head_pred(new_color,2).", "type(new_color,(obj,col)).",
            "body_pred(has_color,2).", "type(has_color,(obj,col))."]
    bias += [x for p in NUMS for x in (f"body_pred({p},2).", f"type({p},(obj,num)).")]
    bias += [x for f in FLAGS for p in (f, "not_" + f) for x in (f"body_pred({p},1).", f"type({p},(obj,)).")]
    rels = RELS + (("same_grid",) if VARIANT == "_samegrid" else ())
    bias += [x for p in rels for x in (f"body_pred({p},2).", f"type({p},(obj,obj)).")]
    bias += [x for n, _, t in consts for x in (f"body_pred({n},1).", f"type({n},({t},)).")]
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "bk.pl"), "w").write("\n".join(DECL + [f"{n}({v})." for n, v, _ in consts] + bk) + "\n")
    open(os.path.join(d, "exs.pl"), "w").write("\n".join(exs) + "\n")
    open(os.path.join(d, "bias.pl"), "w").write("\n".join(bias) + "\n")
    return sum(e.startswith("pos(") for e in exs)


# ------------------------------------------------------------------ Popper and prediction
def run_popper(d):
    """Popper's final program, its training counts, wall and CPU seconds (the process inherits nice 10)."""
    env = dict(os.environ, PATH=os.path.join(POPPER_ENV, "bin") + ":" + os.environ.get("PATH", ""))
    t0, c0 = time.time(), resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        r = subprocess.run([os.path.join(POPPER_ENV, "bin", "python"), os.path.join(POPPER_SRC, "popper.py"), d,
                            "--timeout", str(POPPER_TIMEOUT)], capture_output=True, text=True, env=env,
                           timeout=POPPER_TIMEOUT + 120)
        out, status = r.stdout, ("ok" if r.returncode == 0 else f"exit {r.returncode}: {r.stderr[-300:]}")
    except subprocess.TimeoutExpired:
        out, status = "", "killed after the hard limit"
    c1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (c1.ru_utime - c0.ru_utime) + (c1.ru_stime - c0.ru_stime)
    tail = out.split(" SOLUTION ")[-1] if " SOLUTION " in out else ""
    prog = [l.strip() for l in tail.splitlines() if l.strip().startswith("new_color(")]
    m = re.search(r"TP:(\d+) FN:(\d+) TN:(\d+) FP:(\d+)", tail)
    counts = dict(zip(("tp", "fn", "tn", "fp"), map(int, m.groups()))) if m else None
    return prog, counts, status, round(time.time() - t0, 1), round(cpu, 1)


def predict(prog, grid):
    """The test output: the learned program run in SWI-Prolog on the test input's facts."""
    obs, _ = objects(grid)
    base = 900000
    consts = [f"c{c}({c})." for c in range(10)] + [f"n{v}({v})." for v in range(0, 901)]
    main = [":- initialization(main).",
            "main :- forall(new_color(O,C), (write(O), write(' '), write(C), nl)), halt."]
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "pred.pl")
        open(f, "w").write("\n".join(DECL + consts + facts(grid, obs, base) + prog + main) + "\n")
        try:
            r = subprocess.run([os.path.join(POPPER_ENV, "bin", "swipl"), "-q", f], capture_output=True, text=True,
                               timeout=60)
            lines = r.stdout.splitlines()
        except subprocess.TimeoutExpired:
            lines = []
    derived = {}
    for l in lines:
        p = l.split()
        if len(p) == 2 and p[0].isdigit() and p[1].isdigit():
            derived.setdefault(int(p[0]) - base, set()).add(int(p[1]))
    G = np.array(grid)
    ambiguous = 0
    for j, o in enumerate(obs):
        cs = derived.get(j, set())
        if len(cs) == 1:
            c = next(iter(cs))
            for x in o["cells"]:
                G[x] = c
        elif len(cs) > 1:
            ambiguous += 1
    return G.tolist(), ambiguous


# ------------------------------------------------------------------ suites (no expected outputs here)
def family_seed(name, task_id):
    fam, seed = task_id.split(":")[-1].split("#") if name == "synv3" else task_id.split("#")
    return fam, int(seed)


def family_module(name):
    if name == "synv3":
        from cora_neural_v2g3 import families_v3 as M
    else:
        from cora_neural_v2g2 import families as M
    return M


def suite(name):
    if name == "real":
        from cora_pilot import bundle as B
        ids = json.load(open(REAL_IDS))["eligible_ids"]
        ch = B.load_challenges()
        return [{"task_id": t, "train": [(p["input"], p["output"]) for p in ch[t]["train"]],
                 "test_inputs": [p["input"] for p in ch[t]["test"]]} for t in ids]
    M = family_module(name)
    out = []
    for row in json.load(open(SYN_SCORES[name]))["tasks"]:                 # the puzzles CORA was scored on
        fam, seed = family_seed(name, row["task_id"])
        made = M.make_task(fam, seed)
        if made is not None:
            t, _ = made                                                      # the expected output is discarded here
            assert t["task_id"] == row["task_id"]
            out.append({"task_id": t["task_id"], "family": fam, "seed": seed, "train": t["train"],
                        "test_inputs": t["test_inputs"]})
    return out


def solve_one(args):
    name, task = args
    ok, why = encodable(task)
    rec = {"suite": name, "task_id": task["task_id"], "family": task.get("family"), "seed": task.get("seed"),
           "encodable": ok, "reason": why, "ran": False}
    if not ok or (name != "real" and task["seed"] > SAMPLE_MAX_SEED):
        return rec
    d = os.path.join(OUT, "tasks", name + VARIANT, re.sub(r"[^A-Za-z0-9_.-]", "_", task["task_id"]))
    npos = write_task(task, d)
    prog, counts, status, secs, cpu = run_popper(d)
    preds, amb = [], 0
    for g in task["test_inputs"]:
        p, a = predict(prog, g) if prog else (g, 0)
        preds.append(p)
        amb += a
    fits = bool(counts) and counts["fn"] == 0 and counts["fp"] == 0
    rec.update({"ran": True, "positives": npos, "program": prog, "train_counts": counts, "fits_train": fits,
                "status": status, "wall_s": secs, "cpu_s": cpu, "ambiguous_objects": amb, "predictions": preds})
    return rec


def run(name, variant=""):
    global VARIANT
    VARIANT = variant                                                        # set before the workers fork
    os.makedirs(OUT, exist_ok=True)
    tasks = suite(name)
    with mp.Pool(2) as pool:
        rows = pool.map(solve_one, [(name, t) for t in tasks], chunksize=1)
    with open(os.path.join(OUT, f"rows_{name}{VARIANT}.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(name, "tasks", len(rows), "encodable", sum(r["encodable"] for r in rows), "ran", sum(r["ran"] for r in rows),
          "fits", sum(r.get("fits_train", False) for r in rows), flush=True)


# ------------------------------------------------------------------ evaluator (the only reader of expected outputs)
def answers(name, rows):
    if name == "real":
        from cora_pilot import bundle as B
        from cora_pilot import evaluator as EV
        sol = EV.load_pinned(B.SOLUTIONS, B.SOLUTIONS_SHA256)
        return {r["task_id"]: sol[r["task_id"]] for r in rows}
    M = family_module(name)
    return {r["task_id"]: [np.asarray(M.make_task(r["family"], r["seed"])[1]).tolist()] for r in rows}


def cora_results(name):
    if name == "real":
        s = json.load(open(os.path.join(HERE, "outputs", "neural_cora_realarc_g2g3g4", "score.json")))["tasks"]
        return {t["task_id"]: {"native": all(t["native"]["per_test"]), **{a: bool(t[a]["pass2_all"]) for a in ("g2", "g3", "g4")}}
                for t in s}
    s = json.load(open(SYN_SCORES[name]))["tasks"]
    if name == "synv3":
        return {t["task_id"]: {"g2": bool(t["g2_pass2"]), "g3": bool(t["g3_pass2"])} for t in s}
    return {t["task_id"]: {"g1": bool(t["g1@3000"]["pass@2"]), "g2": bool(t["g2@3000"]["pass@2"])} for t in s}


def cora_cpu(name):
    if name == "real":
        s = json.load(open(os.path.join(HERE, "outputs", "neural_cora_realarc_g2g3g4", "score.json")))["tasks"]
        return {t["task_id"]: {a: t[a]["cpu_s"] for a in ("native", "g2", "g3", "g4")} for t in s}
    arms = ("g2", "g3") if name == "synv3" else ("g1", "g2")
    return {t["task_id"]: {a: t[f"{a}_cpu"] for a in arms} for t in json.load(open(SYN_SCORES[name]))["tasks"]}


def score():
    summary = {}
    for name, variant in [(n, v) for v in ("", "_samegrid") for n in ("real", "synv2", "synv3")]:
        p = os.path.join(OUT, f"rows_{name}{variant}.jsonl")
        if not os.path.exists(p):
            continue
        rows = [json.loads(l) for l in open(p)]
        ran = [r for r in rows if r["ran"]]
        ans = answers(name, ran)
        cora, ccpu = cora_results(name), cora_cpu(name)
        per = []
        for r in ran:
            ok = bool(r["program"]) and len(r["predictions"]) == len(ans[r["task_id"]]) and \
                all(np.array_equal(np.asarray(a), np.asarray(b)) for a, b in zip(r["predictions"], ans[r["task_id"]]))
            per.append({"task_id": r["task_id"], "family": r["family"], "popper_solved": ok, "fits_train": r["fits_train"],
                        "cora": cora.get(r["task_id"], {}), "wall_s": r["wall_s"], "cpu_s": r["cpu_s"],
                        "program": r["program"], "status": r["status"]})
        reasons, fams = {}, {}
        for r in rows:
            if not r["encodable"]:
                reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
            if r["family"]:
                fams.setdefault(r["family"], [0, 0])
                fams[r["family"]][0] += 1
                fams[r["family"]][1] += r["encodable"]
        arms = sorted({a for x in per for a in x["cora"]})
        summary[name + variant] = {
            "tasks": len(rows), "encodable": sum(r["encodable"] for r in rows), "not_encodable": reasons,
            "families_tasks_encodable": fams, "popper_ran": len(ran), "popper_fits_train": sum(x["fits_train"] for x in per),
            "popper_solved": sum(x["popper_solved"] for x in per),
            "cora_solved_same_tasks": {a: sum(bool(x["cora"].get(a)) for x in per) for a in arms},
            "popper_not_cora": [x["task_id"] for x in per if x["popper_solved"] and not any(x["cora"].values())],
            "cora_not_popper": [x["task_id"] for x in per if not x["popper_solved"] and any(x["cora"].values())],
            "wall_s_median": float(np.median([x["wall_s"] for x in per])) if per else None,
            "cpu_s_median": float(np.median([x["cpu_s"] for x in per])) if per else None,
            "cpu_s_total": round(sum(x["cpu_s"] for x in per), 1),
            "cora_cpu_s_median_same_tasks": {a: float(np.median([ccpu[x["task_id"]][a] for x in per])) for a in arms} if per else {},
            "per_task": per}
    json.dump(summary, open(os.path.join(OUT, "score.json"), "w"), indent=1)
    for k, v in summary.items():
        print(k, json.dumps({kk: vv for kk, vv in v.items() if kk not in ("per_task", "families_tasks_encodable")}))


if __name__ == "__main__":
    {"run": lambda: run(sys.argv[2], "_samegrid" if "--same-grid" in sys.argv else ""), "score": score}[sys.argv[1]]()
