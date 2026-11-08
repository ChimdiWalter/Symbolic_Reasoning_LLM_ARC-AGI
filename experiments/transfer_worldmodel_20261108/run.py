"""T4 world-model induction, DEVELOPMENT runs only (no held items exist yet; seeds 100000 and above are reserved).

    python -I run.py dev OUT_JSON SEED_FROM SEED_TO

Per item (family, seed): 20 observed transitions under random actions from the start grid; 30 check transitions from
an independent random stream (three runs of 10 steps after 0, 5 and 10 burn-in steps). An item is recovered by an arm
when the arm's model predicts all 30 check transitions exactly (every cell).
Arms: identity (predict no change, a floor), static, grown, shuffled, classical (local-patch nearest neighbour).
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np                                                                          # noqa: E402

from wm.classical import LocalNN                                                            # noqa: E402
from wm.envs import FAMILIES, Env, rollout                                                  # noqa: E402
from wm.induce import colours_of, describe, fit_static, grow                                # noqa: E402
from wm.model import predict                                                                # noqa: E402

K, SEG, BURN, B, R = 20, 10, (0, 5, 10), 3, 4
HELD_POOL_START = 100000


def item_data(fam, seed):
    env = Env(fam, seed)
    T = rollout(env, env.g0, K, np.random.default_rng([seed, 1]))
    rng, chk = np.random.default_rng([seed, 2]), []
    for b in BURN:
        g = env.g0
        for _, _, g2 in rollout(env, g, b, rng):
            g = g2
        chk += rollout(env, g, SEG, rng)
    return env, T, chk


def check(fn, chk):
    ok = [bool(np.array_equal(fn(g0, a), g1)) for g0, a, g1 in chk]
    return sum(ok), all(ok)


def exact_mcnemar(b, c):
    """Two-sided exact McNemar p-value from the discordant counts b and c."""
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def dev(out, s0, s1):
    assert s1 < HELD_POOL_START, "development seeds must stay below the reserved pool"
    items = [(f, s) for f in FAMILIES for s in range(s0, s1 + 1)]
    data, rank0 = {}, {}
    for f, s in items:
        env, T, chk = item_data(f, s)
        data[(f, s)] = (T, chk)
        rank0[(f, s)] = describe(fit_static(T), T, colours_of(T))[0]
    rows = []
    for f, s in items:
        T, chk = data[(f, s)]
        row = {"family": f, "seed": s, "observed_changes": sum(int((g0 != g1).any()) for g0, _, g1 in T),
               "check_changes": sum(int((g0 != g1).any()) for g0, _, g1 in chk)}
        row["identity"] = check(lambda g, a: g, chk)
        t = time.process_time()
        ms = fit_static(T)
        row["static"], row["cpu_static"] = check(lambda g, a: predict(ms, g, a), chk), time.process_time() - t
        t = time.process_time()
        mg, lg = grow(T, None, B, R)
        row["grown"], row["cpu_grown"] = check(lambda g, a: predict(mg, g, a), chk), time.process_time() - t
        row["grown_log"], row["grown_model"] = lg, mg.describe()
        fi = FAMILIES.index(f)
        partner = next(((FAMILIES[(fi + j) % len(FAMILIES)], s) for j in range(1, len(FAMILIES))
                        if rank0[(FAMILIES[(fi + j) % len(FAMILIES)], s)]), None)
        t = time.process_time()
        msh, lsh = grow(T, rank0[partner] if partner else [], B, R)
        row["shuffled"], row["cpu_shuffled"] = check(lambda g, a: predict(msh, g, a), chk), time.process_time() - t
        row["shuffled_partner"], row["shuffled_log"] = list(partner) if partner else None, lsh
        t = time.process_time()
        nn = LocalNN(T)
        row["classical"], row["cpu_classical"] = check(nn.predict, chk), time.process_time() - t
        rows.append(row)
        print(f, s, {k: row[k][1] for k in ("identity", "static", "grown", "shuffled", "classical")},
              [x["accepted"] for x in lg], round(row["cpu_grown"], 2), flush=True)
    arms = ("identity", "static", "grown", "shuffled", "classical")
    summ = {"label": "DEVELOPMENT (synthetic instances of public rule sets; reconstruction of known rules)",
            "items": len(rows), "k_observed": K, "check_transitions_per_item": len(BURN) * SEG,
            "recovered": {a: sum(r[a][1] for r in rows) for a in arms},
            "check_transitions_exact": {a: sum(r[a][0] for r in rows) for a in arms},
            "per_family": {f: {a: sum(r[a][1] for r in rows if r["family"] == f) for a in arms} | {
                "n": sum(r["family"] == f for r in rows)} for f in FAMILIES},
            "cpu_seconds": {a: round(sum(r["cpu_" + a] for r in rows), 1)
                            for a in ("static", "grown", "shuffled", "classical")}}
    for x, y in (("grown", "static"), ("grown", "shuffled"), ("grown", "classical")):
        b = sum(r[x][1] and not r[y][1] for r in rows)
        c = sum(r[y][1] and not r[x][1] for r in rows)
        summ[f"{x}_vs_{y}"] = {"only_" + x: b, "only_" + y: c, "exact_mcnemar_p": exact_mcnemar(b, c)}
    with open(out, "w") as fh:
        json.dump({"summary": summ, "rows": rows}, fh, indent=1, default=str)
    print(json.dumps(summ["recovered"]), json.dumps(summ["cpu_seconds"]))


def dev_classical_keep(out, s0, s1):
    """The classical comparator with no-change as the default for unseen keys, on the same development items."""
    assert s1 < HELD_POOL_START
    rows = []
    for f in FAMILIES:
        for s in range(s0, s1 + 1):
            _, T, chk = item_data(f, s)
            t = time.process_time()
            nn = LocalNN(T, fallback="keep")
            r = check(nn.predict, chk)
            rows.append({"family": f, "seed": s, "classical_keep": r, "cpu": time.process_time() - t})
    summ = {"label": "DEVELOPMENT", "items": len(rows), "recovered": sum(r["classical_keep"][1] for r in rows),
            "check_transitions_exact": sum(r["classical_keep"][0] for r in rows),
            "per_family": {f: sum(r["classical_keep"][1] for r in rows if r["family"] == f) for f in FAMILIES},
            "cpu_seconds": round(sum(r["cpu"] for r in rows), 1)}
    with open(out, "w") as fh:
        json.dump({"summary": summ, "rows": rows}, fh, indent=1, default=str)
    print(json.dumps(summ))


def arc3_dev(kernel_out, out, games=None, max_items=None):
    """Development probe on public ARC-AGI-3 games (development games only; data written by the kernel)."""
    from wm import arc3
    items = arc3.load_items(kernel_out)
    if games:
        items = [it for it in items if it["game"] in games]
    if max_items:
        items = items[:max_items]
    t = time.process_time()
    rows = arc3.run_items(items)
    summ = {"label": "development probe on public ARC-AGI-3 games; not a score", "kernel": kernel_out,
            "items": len(rows), "excluded": [(it["game"], it["episode"], it["excluded"]) for it in items
                                             if "excluded" in it], "cpu_seconds": round(time.process_time() - t, 1)}
    for a in arc3.ARMS:
        tot = {k: sum(r[a][k] for r in rows) for k in rows[0][a]} if rows else {}
        summ[a] = tot
    with open(out, "w") as fh:
        json.dump({"summary": summ, "rows": rows}, fh, indent=1, default=str)
    print(json.dumps({a: (summ[a].get("exact"), summ[a].get("n"), summ[a].get("changed_ok"), summ[a].get("changed"))
                      for a in arc3.ARMS}), summ["cpu_seconds"])


if __name__ == "__main__":
    if sys.argv[1] == "arc3-dev":
        arc3_dev(sys.argv[2], sys.argv[3], sys.argv[4].split(",") if len(sys.argv) > 4 and sys.argv[4] else None,
                 int(sys.argv[5]) if len(sys.argv) > 5 else None)
    elif sys.argv[1] == "dev":
        dev(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif sys.argv[1] == "dev-classical-keep":
        dev_classical_keep(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        sys.exit("only the development command exists; no protocol or freeze has been written")
