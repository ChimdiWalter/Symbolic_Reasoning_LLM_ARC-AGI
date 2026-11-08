"""Generated tasks from the object step's own language (DESIGN_NOTE.md).

A task applies one operation (a single-rule paint in one of the 12 views, or a crop) to four input grids of one
public training task (three demonstrations and one test input). Its family is "edit type|edit parameters|predicate
kind|view"; the family partition (train, val, held) and the grid pool (dev, held) are fixed by hashes. Held families
and held-pool grids are refused unless the caller passes the GO's seed (the held run only).

    python -s -B run.py gen cheap OUT.jsonl PARTITION N SEED [MAX_S]   tasks only (specification and operation)
    python -s -B run.py gen traced OUT.jsonl PARTITION N SEED [MAX_S]  tasks with the frozen step's trace at 20,000
                                                                       (hand-set order) and their admission
"""
import gzip
import hashlib
import json
import os
import random
import sys
import time

from sgd import env as E
from gcon import engine as EN, features as FT
from objgrow import edits as ED, scene as SC, construct as CS

MAXSIDE = 12
EDIT_TYPES = tuple(e for e in CS.EDIT_ORDER if e != "recolor_table")   # the 18 parameterised single-object edits
PCROP = 0.08
NEG_OK = {k for k in SC.BOOL_ATOMS} | {"colour", "adj_colour", "enc_colour", "enclosing_colour"}


def h8(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


def family_partition(fam):
    r = h8("spec-family:" + fam) % 10
    return "train" if r <= 5 else ("val" if r <= 7 else "held")


def pool_of(tid):
    return "dev" if h8("spec-pool:" + tid) % 2 == 0 else "held"


def grid(g):
    return tuple(tuple(int(v) for v in r) for r in g)


def pools(which, allow_held=False):
    """{task id: [input grids up to MAXSIDE x MAXSIDE]} of one pool (tasks with at least 4 such grids)."""
    if which == "held" and not allow_held:
        raise PermissionError("the held pool opens only in the held run")
    if E.sha_file(E.ARC_TRAIN) != E.ARC_TRAIN_SHA256:
        raise RuntimeError("public training challenges changed")
    with open(E.check_read(E.ARC_TRAIN), encoding="utf-8") as f:
        ch = json.load(f)
    out = {}
    for t in sorted(ch):
        if pool_of(t) != which:
            continue
        gs = [grid(p["input"]) for p in ch[t]["train"]] + [grid(p["input"]) for p in ch[t]["test"]]
        gs = [g for g in gs if len(g) <= MAXSIDE and len(g[0]) <= MAXSIDE]
        if len(gs) >= 4:
            out[t] = gs
    return out


# ------------------------------------------------------------------ the operation sampler
def sample_edit(rng):
    k = rng.choice(EDIT_TYPES)
    c = lambda: rng.randint(1, 9)                                           # noqa: E731
    if k == "delete" or k == "hollow":
        return (k,)
    if k == "recolor":
        return (k, c())
    if k == "recolor_attr":
        return (k, rng.choice(ED.ATTRS))
    if k == "move":
        return (k, rng.choice("UDLR"), rng.choice(("blocked", "border")))
    if k == "gravitate":
        return (k, rng.choice(("nearest", "nearest_diff")))
    if k == "shift":
        while True:
            v = (rng.randint(-2, 2), rng.randint(-2, 2))
            if v != (0, 0):
                return (k,) + v
    if k == "extend":
        return (k, rng.choice(sorted(ED.EXT_DIRS)), rng.choice(ED.STOPS))
    if k == "connect":
        return (k, rng.choice(("same", "any")))
    if k in ("fill_holes", "fill_box"):
        return (k, "self" if rng.random() < 0.3 else c())
    if k in ("outline", "outbox"):
        return (k, c())
    if k == "mirror":
        return (k, rng.choice(("h", "v", "d", "c")))
    if k == "rot":
        return (k, rng.choice((1, 2, 3)))
    if k == "scale":
        return (k, rng.choice((2, 3)))
    if k == "duplicate":
        while True:
            v = (rng.randint(-3, 3), rng.randint(-3, 3))
            if v != (0, 0):
                return (k,) + v
    if k == "mirror_copy":
        return (k, rng.choice(("h", "v")), rng.choice(("+", "-")))
    raise ValueError(k)


def pred_kind(p):
    if p[0] == "not":
        return "not:" + p[1][0]
    return p[0]


def sample_pred(rng, scenes):
    if rng.random() < 0.35:
        return ("true",)
    atoms = [a for a in SC.atom_space(scenes) if a != ("true",)]
    if not atoms:
        return ("true",)
    a = rng.choice(atoms)
    if a[0] in NEG_OK and rng.random() < 0.2:
        return ("not", a)
    return a


def family(spec):
    rules = spec["rules"]
    p, e = rules[0]
    if spec["form"] == "crop":
        return f"crop|()|{pred_kind(p)}|{spec['view']}"
    return f"{e[0]}|{repr(tuple(e[1:]))}|{pred_kind(p)}|{spec['view']}"


def valid_out(g):
    return (g is not None and isinstance(g, tuple) and 0 < len(g) <= 30 and 0 < len(g[0]) <= 30 and
            all(len(r) == len(g[0]) and all(isinstance(v, int) and 0 <= v <= 9 for v in r) for r in g))


def make_task(rng, pool, partition, tries=80):
    """One task of the given family partition from the pool, or None."""
    if partition == "held" and not getattr(rng, "held_ok", False):
        raise PermissionError("held families open only in the held run")
    tid = rng.choice(sorted(pool))
    gs = list(pool[tid])
    rng.shuffle(gs)
    g4 = gs[:4]
    for _ in range(tries):
        view = rng.choice(SC.VIEWS)
        scenes = [ED.scene_of(g, view) for g in g4]
        if any(s is None or not s.objs for s in scenes):
            continue
        if rng.random() < PCROP:
            pred = sample_pred(rng, scenes)
            if any(sum(1 for o in s.objs if SC.holds(o, pred)) != 1 for s in scenes):
                continue
            spec = {"form": "crop", "view": view, "rules": [[pred, ("keep",)]]}
        else:
            spec = {"form": "paint", "view": view, "rules": [[sample_pred(rng, scenes), sample_edit(rng)]]}
        fam = family(spec)
        if family_partition(fam) != partition:
            continue
        op = ED.ObjOp(spec)
        outs = [op(g) for g in g4]
        if not all(valid_out(y) and y != x for x, y in zip(g4, outs)):
            continue
        e = spec["rules"][0][1]
        return {"src": tid, "train": [[x, y] for x, y in zip(g4[:3], outs[:3])], "test_input": g4[3],
                "test_output": outs[3], "op": ED.ObjOp(spec).to_json()["spec"], "family": fam,
                "edit": "crop" if spec["form"] == "crop" else e[0], "view": view,
                "pred_kind": pred_kind(spec["rules"][0][0])}
    return None


# ------------------------------------------------------------------ the frozen step's trace
def answer_from_top(top_pks_loo, pk_true):
    """pass@2: the first two distinct test predictions of the multi-pair candidates, in order."""
    seen = []
    for pk, loo, valid in top_pks_loo:
        if loo and valid and pk not in seen:
            seen.append(pk)
        if len(seen) == 2:
            break
    return pk_true in seen


def trace_task(task):
    pairs = [(grid(x), grid(y)) for x, y in task["train"]]
    ti = [grid(task["test_input"])]
    t0 = time.process_time()
    hs = EN.HoleState(pairs, ti, meta={"rank": 0})
    log = []
    top, rec = EN.run_hole(hs, EN.hand_sequence(hs), EN.FULL_BUDGET, log)
    pk_true = EN.pred_hash((grid(task["test_output"]),))
    top_list = [(EN.pred_hash(c["pred_key"]), bool(c["loo"]),
                 bool(c["pred_key"]) and all(v is not None for v in c["pred_key"])) for c in top]
    correct = answer_from_top(top_list, pk_true)
    if rec["capped"]:
        # not admitted (the cap binds at 20,000): no trace is needed
        return {"capped": True, "correct_20000": correct, "pk_true": pk_true, "trace": None, "blocks": None,
                "views": None, "ops_20000": rec["counts"]["op"], "cpu_s": round(time.process_time() - t0, 3)}
    tr = EN.trace_hole(hs, log)
    feats = FT.hole_features(hs)
    return {"capped": rec["capped"], "correct_20000": correct, "pk_true": pk_true, "trace": tr,
            "blocks": [{"block": list(b), "key": list(hs.block_key(b)), "pos": hs.hand_pos[b],
                        "x": [round(v, 5) for v in feats[b]]} for b in hs.blocks],
            "views": [vs.rec for vs in hs.views], "ops_20000": rec["counts"]["op"],
            "cpu_s": round(time.process_time() - t0, 3)}


# ------------------------------------------------------------------ writers (plain JSON lines, one task per line,
# flushed per line; each writer stops at N tasks or at its wall-clock cap, whichever comes first)
def _open(out):
    E.check_write(out) if not os.environ.get("SG_KAGGLE") else None
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    return open(out, "a", encoding="utf-8")


def write_cheap(out, partition, n, seed, max_s="1e9"):
    rng = random.Random(int(seed))
    pool = pools("dev")
    k = 0
    w0 = time.time()
    with _open(out) as f:
        while k < int(n) and time.time() - w0 < float(max_s):
            t = make_task(rng, pool, partition)
            if t is None:
                continue
            f.write(json.dumps(t, separators=(",", ":")) + "\n")
            f.flush()
            k += 1
    print(json.dumps({"out": out, "tasks": k, "wall_s": round(time.time() - w0, 1)}))


def write_traced(out, partition, n, seed, max_s="1e9"):
    rng = random.Random(int(seed))
    pool = pools("dev")
    k = tried = 0
    t0, w0 = time.process_time(), time.time()
    with _open(out) as f:
        while k < int(n) and time.time() - w0 < float(max_s):
            t = make_task(rng, pool, partition)
            if t is None:
                continue
            tried += 1
            tr = trace_task(t)
            t.update(tr)
            t["admitted"] = (not tr["capped"]) and tr["correct_20000"]
            f.write(json.dumps(t, separators=(",", ":"), default=list) + "\n")
            f.flush()
            k += int(t["admitted"])
            if tried % 100 == 0:
                print(json.dumps({"tried": tried, "admitted": k, "cpu_s": round(time.process_time() - t0, 1)}),
                      flush=True)
    print(json.dumps({"out": out, "tried": tried, "admitted": k, "cpu_s": round(time.process_time() - t0, 1)}))


def main(cmd, *args):
    if cmd == "cheap":
        return write_cheap(*args)
    if cmd == "traced":
        return write_traced(*args)
    raise SystemExit(cmd)
