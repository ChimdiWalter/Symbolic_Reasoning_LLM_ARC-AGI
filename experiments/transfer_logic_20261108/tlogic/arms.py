"""The arms on one item, probe selection, and the exact check.

Probes: a seeded random order of all 2**n inputs; the random condition labels the first B. Held inputs are all the
others. Exact recovery: the arm's program equals the target on every input (it fits every probe and every held input).
Verify flag (the loop's step 6, a secondary): the arm is rebuilt without each of four probe folds (probe position mod
4) and must predict every left-out probe; a program that passes is VERIFIED.
Active probing (pre-registered secondary, grown arm): the first B - 3c probes (c = B // 4) are the random ones; in
each of three rounds a committee (the grown program and K - 1 shuffled-route programs, all fitting every probe so
far) labels the unprobed inputs, and the c inputs where it is most split (ties: random-order position) are probed.
"""
import hashlib
import math
import random
import time

from . import classical, core, policy


def _rng(*parts):
    return random.Random(int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big"))


def probe_order(item_id, n, seed):
    order = list(range(1 << n))
    _rng("probes", seed, item_id).shuffle(order)
    return order


def budget(item, cfg):
    """Probe budget: a fraction of the truth table (rounded up) or a fixed count, leaving at least one held input."""
    d = cfg["budget"][item["domain"]]
    B = math.ceil(d["fraction"] * (1 << item["n"])) if "fraction" in d else int(d["probes"])
    return max(1, min(B, (1 << item["n"]) - 1))


def fit(item, O, Z, mode, key):
    """One CORA-loop or reference learner. Returns (truth table or None, status, size)."""
    n = item["n"]
    if mode == "espresso_like":
        return classical.espresso_like(n, O, Z), "FIT", None
    if mode == "cart":
        return classical.cart(n, O, Z), "FIT", None
    if item["domain"] == "circuit":
        prog, status = core.learn(n, O, Z, mode, key)
        return (None if prog is None else core.vec(prog, n)), status, (None if prog is None else core.size(prog))
    rules, default, status, _ = policy.learn(O, Z, mode, key)
    return (None if rules is None else policy.evaluate(rules, default)), status, (None if rules is None else len(rules))


def outcome(T, pred, P, full):
    if pred is None:
        return {"exact": 0, "fits": 0, "held_errors": None}
    H = full ^ P
    return {"exact": int(pred == T), "fits": int(not ((pred ^ T) & P)),
            "held_errors": ((pred ^ T) & H).bit_count()}


def verify(item, order, B, mode, key):
    T, n = item["T"], item["n"]
    for k in range(4):
        keep = [x for i, x in enumerate(order[:B]) if i % 4 != k]
        out = [x for i, x in enumerate(order[:B]) if i % 4 == k]
        P = sum(1 << x for x in keep)
        pred, _, _ = fit(item, T & P, P & ~T, mode, f"{key}|fold{k}")
        if pred is None or any(((pred >> x) & 1) != ((T >> x) & 1) for x in out):
            return 0
    return 1


def active_probes(item, order, B, K, key):
    import numpy as np
    T, n = item["T"], item["n"]
    c = B // 4
    first = B - 3 * c
    probed = list(order[:first])
    P = sum(1 << x for x in probed)
    pos = {x: i for i, x in enumerate(order)}
    for r in range(3):
        O, Z = T & P, P & ~T
        votes = None
        for k in range(K):
            mode = "grown" if k == 0 else "shuffled"
            pred, _, _ = fit(item, O, Z, mode, f"{key}|committee{k}|round{r}")
            if pred is None:
                continue
            a = classical.to_array(pred, n).astype(np.int16)
            votes = a if votes is None else votes + a
        free = [x for x in order if not (P >> x) & 1]
        if votes is None:
            pick = free[:c]
        else:
            members = K
            score = {x: min(int(votes[x]), members - int(votes[x])) for x in free}
            pick = sorted(free, key=lambda x: (-score[x], pos[x]))[:c]
        for x in pick:
            probed.append(x)
            P |= 1 << x
    return P


def run_item(item, cfg, arms, with_verify=True, with_active=True):
    n, T = item["n"], item["T"]
    full = core.masks(n)[0]
    order = probe_order(item["id"], n, cfg["probe_seed"])
    B = budget(item, cfg)
    P = sum(1 << x for x in order[:B])
    O, Z = T & P, P & ~T
    res = {"id": item["id"], "domain": item["domain"], "cluster": item["cluster"], "n": n, "B": B,
           "held": (1 << n) - B, "arms": {}}
    for mode in arms:
        t0 = time.process_time()
        pred, status, sz = fit(item, O, Z, mode, item["id"])
        r = outcome(T, pred, P, full)
        r.update({"status": status, "size": sz})
        if with_verify and mode in ("static", "grown", "shuffled"):
            r["verified"] = verify(item, order, B, mode, item["id"]) if pred is not None else 0
        r["cpu_s"] = round(time.process_time() - t0, 4)
        res["arms"][mode] = r
    if with_active:
        t0 = time.process_time()
        Pa = active_probes(item, order, B, cfg["active_committee"], item["id"])
        pred, status, sz = fit(item, T & Pa, Pa & ~T, "grown", item["id"])
        r = outcome(T, pred, Pa, full)
        r.update({"status": status, "size": sz, "probes": Pa.bit_count(), "cpu_s": round(time.process_time() - t0, 4)})
        res["arms"]["grown_active"] = r
    return res
