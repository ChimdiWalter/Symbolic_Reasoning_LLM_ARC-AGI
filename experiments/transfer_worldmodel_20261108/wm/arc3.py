"""ARC-AGI-3 frames as world-model items (development probe on public games; not a score).

The input is data only: npz episodes written by the collection kernel (frames, actions, states, levels). No game
code is read or run here.

Item = (game, episode). The first K transitions are observed and fitted; the following transitions (at most MAXTEST)
are test transitions and are never used for fitting. The rule language runs on the frame reduced by the largest
block size s in {8, 4, 2, 1} at which every observed frame is constant on s-by-s blocks (chosen from observed frames
only); predictions are scored at full 64 x 64 resolution.
"""
import glob
import os
import time

import numpy as np

from wm.induce import colours_of, describe, fit_static, grow
from wm.model import predict

K, MAXTEST = 30, 50
ARMS = ("copy_previous", "tabular", "static", "grown", "shuffled")


def block_scale(frames):
    for s in (8, 4, 2):
        if all((f.reshape(64 // s, s, 64 // s, s) == f.reshape(64 // s, s, 64 // s, s)[:, :1, :, :1]).all()
               for f in frames):
            return s
    return 1


def act_str(a, x, y, s):
    return f"C:{int(y) // s}:{int(x) // s}" if int(a) == 6 else f"A{int(a)}"


def load_items(out_dir):
    items = []
    for p in sorted(glob.glob(os.path.join(out_dir, "*_e*.npz"))):
        name = os.path.basename(p)[:-4]
        game, ep = name.rsplit("_e", 1)
        z = np.load(p, allow_pickle=False)
        F, A = z["frames"].astype(np.int8), z["actions"]
        n = len(A)
        if n < K + 1:
            items.append({"game": game, "episode": int(ep), "excluded": f"only {n} transitions"})
            continue
        s = block_scale(F[:K + 1])
        G = [f[::s, ::s].copy() for f in F]
        acts = [act_str(a, x, y, s) for a, x, y in A]
        items.append({"game": game, "episode": int(ep), "s": s, "F": F, "G": G, "acts": acts, "A": A,
                      "states": z["states"].tolist(), "levels": z["levels"].tolist(),
                      "T": [(G[t], acts[t], G[t + 1]) for t in range(K)],
                      "test": list(range(K, min(n, K + MAXTEST)))})
    return items


def up(g, s):
    return np.repeat(np.repeat(g, s, 0), s, 1) if s > 1 else g


def score(item, fn):
    """fn(t) -> predicted full-resolution next frame for test transition t."""
    F, st, lv = item["F"], item["states"], item["levels"]
    r = {"n": 0, "exact": 0, "changed": 0, "changed_ok": 0, "n_within": 0, "exact_within": 0,
         "changed_within": 0, "changed_ok_within": 0, "flags": []}
    for t in item["test"]:
        pred, true, cur = fn(t), F[t + 1], F[t]
        ch = true != cur
        ok = bool(np.array_equal(pred, true))
        nch, nok = int(ch.sum()), int((pred[ch] == true[ch]).sum())
        r["n"] += 1
        r["exact"] += ok
        r["flags"].append(int(ok))
        r["changed"] += nch
        r["changed_ok"] += nok
        if st[t] == st[t + 1] == "NOT_FINISHED" and lv[t] == lv[t + 1]:
            r["n_within"] += 1
            r["exact_within"] += ok
            r["changed_within"] += nch
            r["changed_ok_within"] += nok
    return r


def rank0_of(it):
    return describe(fit_static(it["T"]), it["T"], colours_of(it["T"]))[0]


def partner_ranking(it, games, rank0):
    gi = games.index(it["game"])
    for j in range(1, len(games)):
        r = rank0.get((games[(gi + j) % len(games)], it["episode"]))
        if r:
            return r
    return []


def item_row(it, partner, B=3, R=4):
    F, G, s, A, acts = it["F"], it["G"], it["s"], it["A"], it["acts"]
    row = {"game": it["game"], "episode": it["episode"], "scale": s, "n_test": len(it["test"]),
           "observed_changes": sum(int((g0 != g1).any()) for g0, _, g1 in it["T"])}
    row["copy_previous"] = score(it, lambda t: F[t])
    table = {}
    for t in range(K):
        table[(F[t].tobytes(), tuple(int(v) for v in A[t]))] = F[t + 1]
    row["tabular"] = score(it, lambda t: table.get((F[t].tobytes(), tuple(int(v) for v in A[t])), F[t]))
    c0 = time.process_time()
    ms = fit_static(it["T"])
    row["static"] = score(it, lambda t: up(predict(ms, G[t], acts[t]), s))
    c1 = time.process_time()
    mg, lg = grow(it["T"], None, B, R)
    row["grown"] = score(it, lambda t: up(predict(mg, G[t], acts[t]), s))
    c2 = time.process_time()
    msh, lsh = grow(it["T"], partner, B, R)
    row["shuffled"] = score(it, lambda t: up(predict(msh, G[t], acts[t]), s))
    c3 = time.process_time()
    row["cpu"] = {"static": round(c1 - c0, 2), "grown": round(c2 - c1, 2), "shuffled": round(c3 - c2, 2)}
    row["grown_log"], row["shuffled_log"] = lg, lsh
    row["grown_model"], row["static_model"] = mg.describe(), ms.describe()
    return row


def run_items(items, B=3, R=4):
    live = [it for it in items if "excluded" not in it]
    rank0 = {(it["game"], it["episode"]): rank0_of(it) for it in live}
    games = sorted({it["game"] for it in live})
    rows = []
    for it in live:
        row = item_row(it, partner_ranking(it, games, rank0), B, R)
        rows.append(row)
        print(it["game"], it["episode"], "s", row["scale"], "test", row["n_test"],
              {a: f'{row[a]["exact"]}/{row[a]["n"]}' for a in ARMS}, [x["accepted"] for x in row["grown_log"]],
              row["cpu"], flush=True)
    return rows
