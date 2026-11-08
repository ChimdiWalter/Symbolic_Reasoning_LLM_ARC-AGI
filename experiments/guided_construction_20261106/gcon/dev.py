"""Development on the source halves (PROTOCOL.md sections 4, 6 and 8).

    python -s -B run.py dev extract_v2                 the stored runs/v2 hole records, reduced (comparison only)
    python -s -B run.py dev pass1 I/K                  shard I of K of the 425 units: per hole the frozen
                                                       hole_candidates live, the test's code in the hand-set order at
                                                       20,000, their comparison (and against runs/v2), the block
                                                       trace and the block features -> dev/pass1/units.I.jsonl

Every process runs with PYTHONHASHSEED=0 through scripts/with_cpu_slot.sh. Source halves only; no test output is
read (the controller's stored holes come from demonstrations; agreement keys use test inputs, as the frozen step).
"""
import json
import os
import sys
import time

from gcon import env as E, engine as EN, features as FT
from objgrow import env as OE, construct as CS, grow as GR
from a2 import arcdsl as D

BENCHES = ("concept_arc", "mini_arc", "1d_arc")
DEV = os.path.join(E.STUDY, "dev")
V2 = os.path.join(E.OG_STUDY, "runs", "v2")


def all_units():
    out = []
    for b in BENCHES:
        W = GR.setup(b)
        out += [(b, t) for t in W["units"]]
    return out


def extract_v2():
    out = {}
    for b in BENCHES:
        done = GR.load_units(os.path.join(V2, b))
        for t, u in done.items():
            out[f"{b}/{t}"] = [{"cands": [[c["sid"], bool(c["loo"]), c["proposing"], c["group"], c.get("view")]
                                          for c in h["candidates"]], "op": h["counts"]["op"]} for h in u["holes"]]
    E.dump(os.path.join(DEV, "v2_holes.json"), out)
    print(json.dumps({"units": len(out)}))


def rnd(xs):
    return [round(x, 5) for x in xs]


def pass1(shard):
    i, k = (int(x) for x in shard.split("/"))
    path = os.path.join(DEV, "pass1", f"units.{i}.jsonl")
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    done.add((r["bench"], r["task"]))
    v2 = E.load(os.path.join(DEV, "v2_holes.json"))
    fns = D.guarded(D.load()[0])
    units = [u for n, u in enumerate(all_units()) if n % k == i]
    setups = {b: GR.setup(b) for b in BENCHES}
    with E.open_write(path, "a") as out:
        for b, tid in units:
            if (b, tid) in done:
                continue
            W = setups[b]
            rec, task = W["recs"][tid]["record"], W["tasks"][tid]
            row = {"bench": b, "task": tid, "family": W["fam"][tid], "n_demos": len(task["train"]), "holes": []}
            for rank, sk in enumerate(rec["sketches"]):
                pairs = [(OE.grid(a), OE.grid(c)) for a, c in sk["pairs"]]
                ti = GR.hole_test_inputs(sk, task, fns)
                t0 = time.process_time()
                ref, rrec = CS.hole_candidates(pairs, ti)
                t1 = time.process_time()
                hs = EN.HoleState(pairs, ti, meta={"rank": rank, "inner": sk.get("inner"), "outer": sk.get("outer")})
                log = []
                top, r = EN.run_hole(hs, EN.hand_sequence(hs), EN.FULL_BUDGET, log)
                t2 = time.process_time()
                tr = EN.trace_hole(hs, log)
                t3 = time.process_time()
                feats = FT.hole_features(hs)
                refc, mine = EN.comparable(ref), EN.comparable(top)
                st = v2.get(f"{b}/{tid}", [])
                st = st[rank] if rank < len(st) else None
                stored_match = None
                if st is not None:
                    stored_match = ([c[:4] + [c[5]] for c in refc] == st["cands"] and rrec["counts"]["op"] == st["op"])
                row["holes"].append({
                    "rank": rank, "form": sk["form"], "inner": sk.get("inner"), "outer": sk.get("outer"),
                    "n_pairs": len(pairs), "n_test": len(ti), "ref": refc, "mine": mine,
                    "ref_ops": rrec["counts"]["op"], "mine_ops": r["counts"]["op"],
                    "ref_counts": rrec["counts"], "mine_counts": r["counts"],
                    "match": refc == mine and rrec["counts"]["op"] == r["counts"]["op"],
                    "stored_match": stored_match, "hand_capped": r["capped"], "why": r["why"],
                    "views": [vs.rec for vs in hs.views],
                    "trace": tr,
                    "blocks": [{"block": list(bl), "key": list(hs.block_key(bl)), "pos": hs.hand_pos[bl],
                                "x": rnd(feats[bl])} for bl in hs.blocks],
                    "cpu": {"frozen": round(t1 - t0, 3), "hand": round(t2 - t1, 3), "trace": round(t3 - t2, 3)}})
            out.write(json.dumps(row, sort_keys=True, default=list) + "\n")
            out.flush()
            print(json.dumps({"unit": tid, "bench": b, "match": [h["match"] for h in row["holes"]],
                              "stored": [h["stored_match"] for h in row["holes"]],
                              "cpu": [h["cpu"] for h in row["holes"]]}), flush=True)


def main(cmd, *args):
    if cmd == "extract_v2":
        return extract_v2()
    if cmd == "pass1":
        return pass1(*args)
    raise SystemExit(f"unknown command {cmd}")
