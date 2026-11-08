"""Development analysis on the source halves (PROTOCOL.md sections 5, 6 and 8), from the pass 1 records.

    python -s -B run.py devan check2           equivalence summary over all 1,275 holes -> dev/STEP2_CHECK.json
    python -s -B run.py devan train            cross-fitted, leave-one-benchmark-out and full models -> dev/models/
    python -s -B run.py devan sample I/K       direct execution against simulation and against the frozen function
                                               with its cap set, on the seeded sample (shard I of K)
    python -s -B run.py devan curves           budget curves, the budget rule and the stop rule -> dev/curves.json
"""
import hashlib
import json
import math
import os
import random
import sys
import time

from gcon import env as E, engine as EN, features as FT, model as MD, policy as PO, sim as SM, units as UN
from objgrow import env as OE, construct as CS, grow as GR

DEV = os.path.join(E.STUDY, "dev")
BENCHES = ("concept_arc", "mini_arc", "1d_arc")
CAPS = (100, 200, 500, 1000, 2000, 5000)
FULL = EN.FULL_BUDGET
FOLDS = 5


def load_rows():
    rows = []
    d = os.path.join(DEV, "pass1")
    for fn in sorted(os.listdir(d)):
        if fn.startswith("units.") and fn.endswith(".jsonl"):
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                rows += [json.loads(x) for x in f if x.strip()]
    order = {(b, t): n for n, (b, t) in enumerate((b, t) for b in BENCHES for t in GR.setup(b)["units"])}
    rows.sort(key=lambda r: order[(r["bench"], r["task"])])
    return rows


def folds(rows):
    out = {}
    for b in BENCHES:
        ids = sorted((r["task"] for r in rows if r["bench"] == b),
                     key=lambda t: hashlib.sha256(f"guided-fold:{t}".encode()).hexdigest())
        for n, t in enumerate(ids):
            out[t] = n % FOLDS
    return out


# ------------------------------------------------------------------ step 2
def check2():
    rows = load_rows()
    n = bad = stored_bad = stored_none = sim_bad = capped = 0
    first = []
    for r in rows:
        for h in r["holes"]:
            n += 1
            if not h["match"]:
                bad += 1
                first.append([r["task"], h["rank"], "engine"])
            if h["stored_match"] is None:
                stored_none += 1
            elif not h["stored_match"]:
                stored_bad += 1
                first.append([r["task"], h["rank"], "stored"])
            top, info = SM.simulate(h, [tuple(b["block"]) for b in h["blocks"]], FULL)
            if SM.comparable(top) != h["ref"] or info["ops"] != h["ref_ops"]:
                sim_bad += 1
                first.append([r["task"], h["rank"], "simulation", info["ops"], h["ref_ops"]])
            capped += int(h["hand_capped"])
    cpu = {k: round(sum(h["cpu"][k] for r in rows for h in r["holes"]), 1) for k in ("frozen", "hand", "trace")}
    out = {"units": len(rows), "holes": n, "engine_mismatch": bad, "stored_mismatch": stored_bad,
           "stored_missing": stored_none, "simulation_mismatch": sim_bad, "hand_capped_holes": capped,
           "first_mismatches": first[:20], "cpu_s": cpu,
           "blocks": sum(len(h["blocks"]) for r in rows for h in r["holes"]),
           "trace_blocks": sum(len(h["trace"]["blocks"]) for r in rows for h in r["holes"]),
           "trace_blocks_cut": sum(1 for r in rows for h in r["holes"] for b in h["trace"]["blocks"] if b["cut"])}
    E.dump(os.path.join(DEV, "STEP2_CHECK.json"), out, indent=1)
    print(json.dumps(out))


# ------------------------------------------------------------------ training
def dataset(rows, keep=lambda r: True):
    X, ys, yc, keys = [], [], [], []
    for r in rows:
        if not keep(r):
            continue
        for h in r["holes"]:
            xb = {tuple(b["block"]): b for b in h["blocks"]}
            for t in h["trace"]["blocks"]:
                b = xb[tuple(t["block"])]
                X.append(b["x"])
                ys.append(1 if any(c["loo"] for c in t["cands"]) else 0)
                yc.append(math.log1p(t["n"]))
                keys.append(b["key"])
    return X, ys, yc, keys


def train_set(rows, keep):
    X, ys, yc, keys = dataset(rows, keep)
    guide = MD.Model().fit(X, ys, yc)
    lin = MD.Model(hidden=()).fit(X, ys, yc)
    freq = MD.Frequency().fit(keys, ys, yc)
    return {"guide": guide.to_json(), "linear": lin.to_json(), "frequency": freq.to_json(),
            "n_blocks": len(X), "n_success": int(sum(ys))}


def train():
    rows = load_rows()
    fo = folds(rows)
    md = os.path.join(DEV, "models")
    t0 = time.process_time()
    for k in range(FOLDS):
        m = train_set(rows, lambda r, k=k: fo[r["task"]] != k)
        E.dump(os.path.join(md, f"fold{k}.json"), m)
        print(json.dumps({"fold": k, "blocks": m["n_blocks"], "success": m["n_success"]}), flush=True)
    for b in BENCHES:
        X, ys, yc, keys = dataset(rows, lambda r, b=b: r["bench"] != b)
        g = MD.Model().fit(X, ys, yc)
        E.dump(os.path.join(md, f"lobo_{b}.json"), {"guide": g.to_json(), "n_blocks": len(X), "n_success": int(sum(ys))})
        print(json.dumps({"lobo": b, "blocks": len(X)}), flush=True)
    m = train_set(rows, lambda r: True)
    E.dump(os.path.join(md, "full.json"), m)
    hosts = sum(1 for r in rows for h in r["holes"] for t in h["trace"]["blocks"] if any(c["loo"] for c in t["cands"]))
    print(json.dumps({"full": m["n_blocks"], "success": m["n_success"], "check": hosts,
                      "cpu_s": round(time.process_time() - t0, 1)}))


class Models:
    def __init__(self):
        md = os.path.join(DEV, "models")
        self.fold = []
        for k in range(FOLDS):
            d = E.load(os.path.join(md, f"fold{k}.json"))
            self.fold.append({"guide": MD.Model.from_json(d["guide"]), "linear": MD.Model.from_json(d["linear"]),
                              "frequency": MD.Frequency.from_json(d["frequency"])})
        self.lobo = {b: MD.Model.from_json(E.load(os.path.join(md, f"lobo_{b}.json"))["guide"]) for b in BENCHES}


# ------------------------------------------------------------------ orders
class Orders:
    """Sequences of every arm for the development units (cross-fitted where trained)."""

    def __init__(self, rows):
        self.rows = rows
        self.by = {(r["bench"], r["task"]): r for r in rows}
        self.fo = folds(rows)
        self.M = Models()
        self._donor_cache = {}

    def seq(self, arm, r, h):
        blocks = [tuple(b["block"]) for b in h["blocks"]]
        if arm == "hand":
            return PO.hand(blocks)
        if arm == "hand_rule":
            return PO.hand_rule(blocks, h["views"])
        X = [b["x"] for b in h["blocks"]]
        m = self.M.fold[self.fo[r["task"]]]
        if arm == "guide":
            return PO.by_scores(blocks, m["guide"].scores(X))
        if arm == "linear":
            return PO.by_scores(blocks, m["linear"].scores(X))
        if arm == "frequency":
            return PO.by_scores(blocks, m["frequency"].scores_keys([b["key"] for b in h["blocks"]]))
        if arm == "lobo":
            return PO.by_scores(blocks, self.M.lobo[r["bench"]].scores(X))
        if arm == "donor":
            dk = self.donor_hole(r, h["rank"])
            if dk is None:
                return PO.hand(blocks)
            dX, dkeys = dk
            ds = m["guide"].scores(dX) if dX else []
            return PO.by_scores(blocks, PO.donor_scores([b["key"] for b in h["blocks"]], list(zip(dkeys, ds))))
        raise ValueError(arm)

    def donor_hole(self, r, rank):
        from ngb import object_arm as OA
        b = r["bench"]
        d = OA.donor_of(b, r["task"], half="source")
        if d is None:
            return None
        k = (b, d, rank)
        if k in self._donor_cache:
            return self._donor_cache[k]
        res = None
        if (b, d) in self.by:
            hs = self.by[(b, d)]["holes"]
            hh = hs[rank] if rank < len(hs) else (hs[-1] if hs else None)
            if hh is not None:
                res = ([x["x"] for x in hh["blocks"]], [x["key"] for x in hh["blocks"]])
        else:
            recs = OE.controller_records(b)
            sk = (recs.get(d, {}).get("record") or {}).get("sketches") or []
            if sk:
                s = sk[rank] if rank < len(sk) else sk[-1]
                pairs = [(OE.grid(a), OE.grid(c)) for a, c in s["pairs"]]
                hs_ = EN.HoleState(pairs, (), meta={"rank": min(rank, len(sk) - 1), "inner": s.get("inner"),
                                                    "outer": s.get("outer")})
                fe = FT.hole_features(hs_)
                res = ([fe[bl] for bl in hs_.blocks], [list(hs_.block_key(bl)) for bl in hs_.blocks])
        self._donor_cache[k] = res
        return res


# ------------------------------------------------------------------ step 2 sample (direct against simulation)
def norm(x):
    return json.loads(json.dumps(x, default=list))


def sample(shard="0/1", out_rel=None):
    """out_rel: the output path relative to the study (default dev/STEP2_SAMPLE.<I>.json). Also checks that the
    features computed now equal the pass 1 records (rounded to 5 decimals), and records the content comparisons."""
    i, k = (int(x) for x in shard.split("/"))
    rows = load_rows()
    O = Orders(rows)
    holes = [(r, h) for r in rows for h in r["holes"]]
    rng = random.Random(20261106)
    pick = sorted(rng.sample(range(len(holes)), 60))
    capped = [n for n, (r, h) in enumerate(holes) if h["hand_capped"]]
    pick = sorted(set(pick) | set(rng.sample(capped, min(12, len(capped)))))
    pick = [p for n, p in enumerate(pick) if n % k == i]
    out_path = os.path.join(E.STUDY, out_rel) if out_rel else os.path.join(DEV, f"STEP2_SAMPLE.{i}.json")
    res = []
    bad = 0
    t0 = time.process_time()
    setups = {}
    from a2 import arcdsl as D
    fns = D.guarded(D.load()[0])
    for n in pick:
        r, h = holes[n]
        b = r["bench"]
        if b not in setups:
            setups[b] = GR.setup(b)
        W = setups[b]
        sk = W["recs"][r["task"]]["record"]["sketches"][h["rank"]]
        pairs = [(OE.grid(a), OE.grid(c)) for a, c in sk["pairs"]]
        ti = GR.hole_test_inputs(sk, W["tasks"][r["task"]], fns)
        hs = EN.HoleState(pairs, ti, meta={"rank": h["rank"], "inner": sk.get("inner"), "outer": sk.get("outer")})
        row = {"task": r["task"], "rank": h["rank"], "hand_capped": h["hand_capped"], "checks": []}
        fe = FT.hole_features(hs)
        same_x = all([round(v, 5) for v in fe[tuple(b["block"])]] == b["x"] for b in h["blocks"])
        row["checks"].append(["features_equal_pass1", None, same_x])
        bad += int(not same_x)
        # hand-set order: frozen function with its cap set, direct execution, simulation
        for B in (100, 500, 2000, 5000):
            old = CS.MAX_OPS_PER_HOLE
            try:
                CS.MAX_OPS_PER_HOLE = B
                ref, rrec = CS.hole_candidates(pairs, ti)
            finally:
                CS.MAX_OPS_PER_HOLE = old
            top, rec = EN.run_hole(hs, EN.hand_sequence(hs), B)
            st, info = SM.simulate(h, O.seq("hand", r, h), B)
            ok = (norm(EN.comparable(ref)) == norm(EN.comparable(top)) == norm(SM.comparable(st)) and
                  rrec["counts"]["op"] == rec["counts"]["op"] == info["ops"])
            row["checks"].append(["hand", B, ok])
            bad += int(not ok)
        for arm in ("guide", "hand_rule"):
            seq = O.seq(arm, r, h)
            for B in (100, 1000, 5000):
                top, rec = EN.run_hole(hs, seq, B)
                st, info = SM.simulate(h, seq, B)
                ok = norm(EN.comparable(top)) == norm(SM.comparable(st)) and rec["counts"]["op"] == info["ops"]
                row["checks"].append([arm, B, ok])
                bad += int(not ok)
        res.append(row)
    out = {"holes": len(res), "checks": sum(len(x["checks"]) for x in res), "failed": bad,
           "rows": res, "cpu_s": round(time.process_time() - t0, 1)}
    E.dump(out_path, out, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}))


# ------------------------------------------------------------------ step 3: curves, budget rule, stop rule
def budget_rule(F):
    """F: {budget: units fitted by the hand-set order}. The largest cap with F(b) <= 0.75 F(20,000), or None."""
    ok = [b for b in CAPS if F[b] <= 0.75 * F[FULL]]
    return max(ok) if ok else None


def curves():
    rows = load_rows()
    O = Orders(rows)
    R = UN.Retrier(E.g0_builder(), path=os.path.join(DEV, "retries.jsonl"))
    setups = {b: GR.setup(b) for b in BENCHES}
    out_path = os.path.join(DEV, "curves.json")
    doc = E.load(out_path) if os.path.exists(out_path) else {"arms": {}}
    seqs = {}
    t0 = time.process_time()

    def run_arm(arm, budget):
        key = f"{arm}@{budget}"
        if key in doc["arms"]:
            return doc["arms"][key]
        a0, n0 = time.process_time(), R.new
        per = {}
        for r in rows:
            tops, ops, capped = [], 0, 0
            for h in r["holes"]:
                sk = (arm, r["task"], h["rank"])
                if sk not in seqs:
                    seqs[sk] = O.seq(arm, r, h)
                top, info = SM.simulate(h, seqs[sk], budget)
                tops.append(top)
                ops += info["ops"]
                capped += int(info["capped"])
            a = UN.answer(tops, r["task"], setups[r["bench"]]["tasks"][r["task"]], R)
            per[r["task"]] = {"bench": r["bench"], "fit": a["fit"], "op": a["op"], "retries": len(a["retries"]),
                              "ops": ops, "capped_holes": capped}
        fits = {b: sum(1 for v in per.values() if v["bench"] == b and v["fit"]) for b in BENCHES}
        res = {"arm": arm, "budget": budget, "fits": fits, "fits_all": sum(fits.values()),
               "ops": sum(v["ops"] for v in per.values()), "capped_holes": sum(v["capped_holes"] for v in per.values()),
               "units": per, "new_retries": R.new - n0, "cpu_s": round(time.process_time() - a0, 1)}
        doc["arms"][key] = res
        E.dump(out_path, doc)
        print(json.dumps({k: v for k, v in res.items() if k != "units"}), flush=True)
        return res

    for b in CAPS + (FULL,):
        run_arm("hand", b)
    F = {b: doc["arms"][f"hand@{b}"]["fits_all"] for b in CAPS + (FULL,)}
    B = budget_rule(F)
    doc["budget_rule"] = {"F": {str(k): v for k, v in F.items()}, "threshold": 0.75 * F[FULL], "test_budget": B}
    E.dump(out_path, doc)
    print(json.dumps(doc["budget_rule"]), flush=True)
    if B is None:
        doc["stop_rule"] = {"verdict": "NO-GO", "reason": "the budget does not bind (100 keeps more than 75%)"}
        E.dump(out_path, doc)
        return
    g = run_arm("guide", B)
    hnd = doc["arms"][f"hand@{B}"]
    gains = sorted(t for t, v in g["units"].items() if v["fit"] and not hnd["units"][t]["fit"])
    losses = sorted(t for t, v in g["units"].items() if hnd["units"][t]["fit"] and not v["fit"])
    go = (len(gains) - len(losses) >= 10) and (len(gains) >= 3 * len(losses))
    by = {b: {"gains": sum(1 for t in gains if g["units"][t]["bench"] == b),
              "losses": sum(1 for t in losses if g["units"][t]["bench"] == b)} for b in BENCHES}
    doc["stop_rule"] = {"test_budget": B, "gains": len(gains), "losses": len(losses), "net": len(gains) - len(losses),
                        "by_bench": by, "gain_units": gains, "loss_units": losses, "verdict": "GO" if go else "NO-GO"}
    E.dump(out_path, doc)
    print(json.dumps({k: v for k, v in doc["stop_rule"].items() if not k.endswith("_units")}), flush=True)
    # descriptive arms
    for b in sorted({B // 4, 4 * B}):
        run_arm("hand", b)
    for b in sorted({B // 4, 4 * B, FULL} | set(CAPS)):
        run_arm("guide", b)
    for arm in ("linear", "frequency", "hand_rule", "donor", "lobo"):
        run_arm(arm, B)
    doc["cpu_s"] = round(time.process_time() - t0, 1)
    doc["retry_cache"] = len(R.cache)
    E.dump(out_path, doc)
    print(json.dumps({"done": True, "cpu_s": doc["cpu_s"]}))


def main(cmd, *args):
    return {"check2": check2, "train": train, "sample": sample, "curves": curves}[cmd](*args)
