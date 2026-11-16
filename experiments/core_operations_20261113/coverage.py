"""Generator coverage table: which annotations the typed generator covers, and which operations it can serve.
Author: Chimdi Walter Ndubuisi

    env PYTHONHASHSEED=0 python -s -B experiments/core_operations_20261113/coverage.py [outfile.json]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dslx      # noqa: E402
import gen       # noqa: E402


def table():
    L = dslx.load()
    per_ann, ops = {}, {}
    status = {}
    for o in L["lib_order"]:
        g = gen.gen_examples(o)
        status[o] = (g["status"], g["reason"], g["draws"], g["raised"], len({repr(e[1]) for e in g["examples"]}))
        for p, a in L["sigs"][o]:
            d = per_ann.setdefault(a, dict(params=0, ops=set(), ops_ok=set()))
            d["params"] += 1
            d["ops"].add(o)
            if g["status"] == "ok":
                d["ops_ok"].add(o)
    rows = {a: dict(parameters=d["params"], operations=len(d["ops"]), operations_with_valid_examples=len(d["ops_ok"]))
            for a, d in sorted(per_ann.items())}
    reasons = {}
    for o, (st, why, dr, ra, nd) in status.items():
        if st != "ok":
            reasons.setdefault(why, []).append(o)
    return dict(
        operations=len(status), with_valid_examples=sum(1 for v in status.values() if v[0] == "ok"),
        excluded={k: dict(count=len(v), operations=v) for k, v in reasons.items()},
        by_annotation=rows,
        per_operation={o: dict(status=v[0], draws=v[2], rejected_draws=v[3], distinct_outputs=v[4])
                       for o, v in status.items()})


if __name__ == "__main__":
    t = table()
    if len(sys.argv) > 1:
        json.dump(t, open(sys.argv[1], "w"), indent=1, sort_keys=True)
    print("operations:", t["operations"], "with valid examples:", t["with_valid_examples"])
    for k, v in t["excluded"].items():
        print("excluded (%d): %s -- %s" % (v["count"], k, ", ".join(v["operations"])))
    print("%-22s %10s %10s %10s" % ("annotation", "parameters", "operations", "with data"))
    for a, r in t["by_annotation"].items():
        print("%-22s %10d %10d %10d" % (a, r["parameters"], r["operations"], r["operations_with_valid_examples"]))
    dis = sorted(t["per_operation"].items(), key=lambda kv: kv[1]["distinct_outputs"])[:12]
    print("fewest distinct outputs:", ", ".join("%s=%d" % (o, v["distinct_outputs"]) for o, v in dis))
