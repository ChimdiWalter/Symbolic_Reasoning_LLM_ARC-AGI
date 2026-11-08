"""Tasks, splits, synthetic generation and the four arms.

A task is one dataset with a training set and a held set of perturbation conditions. Its design has one column per
condition at t1 and one per condition at t0 (stimuli removed, inhibitors kept; CellNOpt's simulatorT0). Fits see only
the training columns (t1 and t0 of the training conditions); the held t1 columns are read only by score_held.

Held split rule (real data): conditions are ranked by sha256(salt + "|" + dataset + "|" + condition key) and dealt
round-robin into n_folds folds; each fold is held once, with the other folds as training.
"""
import hashlib
import time

from .data import preprocess
from .grow import grow, static_fit
from .model import Design, Obs, Space, simulate, simulate_core
from .search import CellNOptScore, ga_cellnopt, rng_for


class Task:
    pass


def make_task(ds, train_idx, held_idx, label, threshold=0.5, max_inputs=2, values=None, pkn=None):
    """values: optional {cond index: (t1 row, t0 row)} replacing the measured values (synthetic data)."""
    t = Task()
    t.label, t.dataset = label, ds.name
    work = ds if pkn is None else _with_pkn(ds, pkn)
    edges, hyper = preprocess(work, max_inputs)
    t.edges = edges
    t.nodes = sorted({u for u, _, _ in edges} | {v for _, _, v in edges})
    t.base_hyper = hyper
    t.stimuli, t.inhibitors, t.readouts = ds.stimuli, ds.inhibitors, [r for r in ds.readouts]
    sp = Space(t.nodes, hyper, t.stimuli, t.inhibitors, t.readouts)
    cols_s, cols_i, rows = [], [], []
    t.t1_bit, t.t0_bit, t.cond_key = {}, {}, {}
    zero = tuple(0 for _ in ds.stimuli)
    for c, cond in enumerate(ds.conditions):
        t1, t0 = (cond["t1"], cond["t0"]) if values is None else values[c]
        t.cond_key[c] = cond["key"]
        t.t1_bit[c] = 1 << len(rows)
        cols_s.append(cond["stim"])
        cols_i.append(cond["inh"])
        rows.append(t1)
        if t0 is not None:
            t.t0_bit[c] = 1 << len(rows)
            cols_s.append(zero)
            cols_i.append(cond["inh"])
            rows.append(t0)
    t.design = Design(sp, cols_s, cols_i, ds.stimuli, ds.inhibitors)
    t.obs = Obs(sp, t.design, rows, threshold)
    t.train_conds, t.held_conds = list(train_idx), list(held_idx)
    t.train_all = 0
    for c in t.train_conds:
        t.train_all |= t.t1_bit[c] | t.t0_bit.get(c, 0)
    t.is_t1 = [False] * t.design.K
    for c in t.t1_bit:
        t.is_t1[t.t1_bit[c].bit_length() - 1] = True
    t.rows = rows
    t.space0 = sp
    return t


def _with_pkn(ds, pkn):
    class W:
        pass
    w = W()
    w.name, w.pkn, w.stimuli, w.inhibitors, w.readouts = ds.name, pkn, ds.stimuli, ds.inhibitors, ds.readouts
    return w


def hash_folds(keys, salt, dataset, n_folds):
    order = sorted(range(len(keys)), key=lambda i: hashlib.sha256(f"{salt}|{dataset}|{keys[i]}".encode()).hexdigest())
    folds = [sorted(order[f::n_folds]) for f in range(n_folds)]
    return folds


# ------------------------------------------------------------------------------------------------------------ arms
def held_outcomes(task, space, x, na):
    """Per held condition: (exact, wrong data points, measured data points)."""
    out = {}
    for c in task.held_conds:
        b = task.t1_bit[c]
        wrong = task.obs.errors(x, na, b)
        meas = sum(1 for j in range(len(task.obs.ro)) if task.obs.meas[j] & b)
        out[task.cond_key[c]] = {"exact": int(wrong == 0), "wrong": wrong, "measured": meas}
    return out


def check_models(task, space, models):
    """The checker: every final model's steady state recomputed with the core evaluator must agree."""
    for m in models:
        a = simulate(space, task.design, m)
        b = simulate_core(space, task.design, m)
        if a[0] != b[0] or (a[1] or None) != (b[1] or None):
            raise AssertionError(f"{task.label}: simulator and core checker disagree")


def run_arms(task, cfg, arms=("static", "grown", "shuffled", "classical")):
    res = {"task": task.label, "dataset": task.dataset, "n_train": len(task.train_conds), "n_held": len(task.held_conds),
           "hyperedges": len(task.base_hyper), "arms": {}}
    memo = {}
    for arm in arms:
        t0 = time.process_time()
        if arm == "static":
            st = static_fit(task, cfg, memo)
            sp = Space(task.nodes, task.base_hyper, task.stimuli, task.inhibitors, task.readouts)
            check_models(task, sp, [st["rep"]])
            x, na = simulate(sp, task.design, st["rep"])
            info = {"train_err": st["err"], "n_least": len(st["least"]), "rep": sp.describe(st["rep"]),
                    "evals": st["evals"]}
        elif arm in ("grown", "shuffled"):
            sp, m, info = grow(task, f"{task.label}|{arm}", cfg, shuffled=(arm == "shuffled"), memo=memo)
            check_models(task, sp, [m])
            x, na = simulate(sp, task.design, m)
            info["train_err"] = task.obs.errors(x, na, task.train_all)
            info["rep"] = sp.describe(m)
        elif arm == "classical":
            sp = Space(task.nodes, task.base_hyper, task.stimuli, task.inhibitors, task.readouts)
            tr_cols = [k for k in range(task.design.K) if (task.train_all >> k) & 1]
            sub = _subdesign(task, sp, tr_cols)
            sc = CellNOptScore(sp, sub[0], sub[1], sub[2], len(task.train_conds), cfg["size_fac"], cfg["na_fac"])
            g = ga_cellnopt(sc, sp.H, task.label + "|ga", **cfg["ga"])
            check_models(task, sp, [g["model"]])
            x, na = simulate(sp, task.design, g["model"])
            info = {"score": g["score"], "gens": g["gens"], "evals": g["evals"], "rep": sp.describe(g["model"])}
        else:
            raise ValueError(arm)
        info["held"] = held_outcomes(task, sp, x, na)
        info["cpu_s"] = round(time.process_time() - t0, 3)
        res["arms"][arm] = info
    return res


def _subdesign(task, sp, cols):
    cs, ci, rows, is_t1 = [], [], [], []
    for k in cols:
        cs.append(tuple((task.design.stim_mask[sp.ix[n]] >> k) & 1 if n in sp.ix else 0 for n in task.stimuli))
        ci.append(tuple((task.design.inh_mask[sp.ix[n]] >> k) & 1 if n in sp.ix else 0 for n in task.inhibitors))
        rows.append(task.rows[k])
        is_t1.append(task.is_t1[k])
    d = Design(sp, cs, ci, task.stimuli, task.inhibitors)
    return d, Obs(sp, d, rows), is_t1


# ------------------------------------------------------------------------------------------------------- synthetic
def synthetic_task(ds, label, n_held, flip, cfg_syn):
    """Synthetic-from-real-PKN: a true model drawn from the full PKN space; one PKN edge that the truth uses (and that
    changes at least MIN_EFFECT readout values over the design) is removed from the learner's PKN; data are the truth's
    binarised steady states with each value flipped with probability flip. Held conditions: the n_held smallest by
    sha256(label + condition key). Returns (task, info) or None when no edge qualifies."""
    rng = rng_for("syn|" + label)
    edges, hyper = preprocess(ds, 2)
    nodes = sorted({u for u, _, _ in edges} | {v for _, _, v in edges})
    full_t = make_task(ds, range(len(ds.conditions)), [], label + "|truth",
                       values={c: (tuple(0.0 for _ in ds.readouts), tuple(0.0 for _ in ds.readouts))
                               for c in range(len(ds.conditions))})
    sp = full_t.space0
    for _ in range(200):
        truth = 0
        for h in range(sp.H):
            if rng.random() < cfg_syn["p_edge"]:
                truth |= 1 << h
        x, _ = simulate(sp, full_t.design, truth)
        used_edges = sorted({(u, s, t) for h in sp.active(truth) for (t, lits) in [sp.hyper[h]] for (u, s) in lits
                             if (u, s, t) in set(ds.pkn)})
        rng.shuffle(used_edges)
        for e in used_edges:
            pruned = [h for h in range(sp.H) if any((u, s, sp.hyper[h][0]) == e for u, s in sp.hyper[h][1])]
            t2 = truth
            for h in pruned:
                t2 &= ~(1 << h)
            x2, _ = simulate(sp, full_t.design, t2)
            eff = sum((x[v] ^ x2[v]).bit_count() for v in full_t.obs.ro)
            if eff >= cfg_syn["min_effect"] and _readouts_vary(full_t, x):
                keys = [c["key"] for c in ds.conditions]
                order = sorted(range(len(keys)), key=lambda i: hashlib.sha256(f"{label}|{keys[i]}".encode()).hexdigest())
                held = sorted(order[:n_held])
                train = sorted(order[n_held:])
                vals = {}
                for c in range(len(ds.conditions)):
                    fl = 0.0 if c in held else flip          # training values are noisy; held values are the truth
                    b1, b0 = full_t.t1_bit[c], full_t.t0_bit.get(c)
                    r1 = tuple(_noisy((x[v] & b1) != 0, rng, fl) for v in full_t.obs.ro)
                    r0 = None if b0 is None else tuple(_noisy((x[v] & b0) != 0, rng, fl) for v in full_t.obs.ro)
                    vals[c] = (r1, r0)
                pkn = [p for p in ds.pkn if p != e]
                try:
                    task = make_task(ds, train, held, label, values=vals, pkn=pkn)
                except ValueError:
                    continue
                truth_desc = sp.describe(truth)
                return task, {"removed_edge": f"{e[0]} {e[1]} {e[2]}", "effect": eff, "truth": truth_desc}
    return None


def _readouts_vary(t, x):
    return sum(1 for v in t.obs.ro if 0 < (x[v] & t.design.full).bit_count() < t.design.K) >= 2


def _noisy(bit, rng, flip):
    b = 1 if bit else 0
    if rng.random() < flip:
        b = 1 - b
    return float(b)
