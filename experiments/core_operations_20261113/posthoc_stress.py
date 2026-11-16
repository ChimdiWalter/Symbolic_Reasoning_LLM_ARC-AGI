"""Post hoc stress check of the rebuilt expressions. Written AFTER the full run; not part of the frozen study.

Why. The full run calls an operation "expressible" when some expression equals it on 36 invented examples. Reading
the expressions showed that a few are artefacts of examples that never exercise the operation (for instance `paint`
"rebuilt" as its own grid argument, because the generator paints an object of the grid onto the same grid). This
check asks, for every expression the oracle-assisted arm found: does it still equal the operation on inputs put
together differently?

How. All argument values of all operations' generated examples are pooled by the annotation of their parameter
(Grid, Patch, Integer and so on). For an operation X, new argument tuples are drawn from those pools (seeded), so
that the arguments of one tuple come from different draws and different operations. Function-typed arguments are
taken only from X's own generated examples, which keeps the frozen rule that a hidden implementation never enters
through an argument. X is run in the full library; a tuple on which X raises, or returns something unusable, is
skipped. The found expression is then evaluated in the namespace of its own hiding condition and compared with X's
output by the canonical typed encoding. An expression that raises where X does not counts as different.

Reading. "survives": at least 30 usable tuples and equal on all of them. "refuted": different on at least one.
"too few": fewer than 30 usable tuples. Surviving is still not a proof of equality.

    env PYTHONHASHSEED=0 python -s -B experiments/core_operations_20261113/posthoc_stress.py <full_out> <out.json>

Author: Chimdi Walter Ndubuisi
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dslx                      # noqa: E402
import gen                       # noqa: E402

N_DRAWS, MIN_VALID, SEED = 400, 30, 20261113


def main(argv):
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("run with PYTHONHASHSEED=0")
    full_out, out_path = argv[0], argv[1]
    L = dslx.load()
    full = dslx.full_ns()
    recs = {}
    for f in sorted(os.listdir(full_out)):
        if "__" in f and f.endswith(".json"):
            with open(os.path.join(full_out, f)) as fh:
                r = json.load(fh)
            recs[(r["op"], r["condition"])] = r
    searched = sorted({o for (o, c), r in recs.items() if r["status"] == "searched"})
    examples, pools, seen = {}, {}, {}
    for op in searched:                                   # the frozen generator, deterministic
        g = gen.gen_examples(op)
        examples[op] = g["examples"]
        for args, _ in g["examples"]:
            for (_, ann), v in zip(L["sigs"][op], args):
                if ann == "Callable" or callable(v):
                    continue
                key = dslx.canon(v)
                if key not in seen.setdefault(ann, set()):
                    seen[ann].add(key)
                    pools.setdefault(ann, []).append(v)
    out = {"what": "post hoc stress check of the oracle-arm expressions; written after the full run; see the docstring",
           "n_draws": N_DRAWS, "min_valid": MIN_VALID, "pool_sizes": {a: len(v) for a, v in sorted(pools.items())},
           "results": {}}
    for (op, cond), r in sorted(recs.items()):
        if r["status"] != "searched" or not r.get("regenerated"):
            continue
        rng = random.Random("%d:%s" % (SEED, op))
        sig = L["sigs"][op]
        own = examples[op]
        ns = dslx.library_namespace(r["hidden"])
        env = dict(ns)
        env.update(L["consts"])
        code = compile(r["expr"], "<expr>", "eval")
        valid = equal = differ = raised = 0
        first_counter = None
        for _ in range(N_DRAWS):
            args = []
            for j, (_, ann) in enumerate(sig):
                if ann == "Callable" or callable(own[0][0][j]) or ann not in pools:
                    args.append(rng.choice(own)[0][j])    # function-typed: only from X's own examples
                else:
                    args.append(rng.choice(pools[ann]))
            try:
                y = full[op](*args)
            except Exception:                             # noqa: BLE001 (outside X's domain: skipped)
                continue
            if not dslx.valid_value(y) or callable(y):
                continue
            valid += 1
            try:
                v = eval(code, env, {p: a for (p, _), a in zip(sig, args)})   # noqa: S307 (trusted library expression)
                same = dslx.canon(v) == dslx.canon(y)
            except Exception:                             # noqa: BLE001
                same = False
                raised += 1
            if same:
                equal += 1
            else:
                differ += 1
                if first_counter is None:
                    first_counter = [dslx.canon(a)[:120] for a in args]
        verdict = "too few" if valid < MIN_VALID else ("survives" if differ == 0 else "refuted")
        out["results"]["%s__%s" % (op, cond)] = dict(
            op=op, condition=cond, expr=r["expr"], size=r["size"], same_as_a="same_as_a" in r, usable=valid,
            equal=equal, different=differ, of_which_raised=raised, verdict=verdict, first_counterexample=first_counter)
    for c in "ab":
        rs = [v for v in out["results"].values() if v["condition"] == c]
        out["condition_" + c] = {k: sorted(v["op"] for v in rs if v["verdict"] == k) for k in ("survives", "refuted", "too few")}
        out["condition_" + c]["counts"] = {k: len(out["condition_" + c][k]) for k in ("survives", "refuted", "too few")}
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    for c in "ab":
        print(c, out["condition_" + c]["counts"], "refuted:", out["condition_" + c]["refuted"], "too few:", out["condition_" + c]["too few"])


if __name__ == "__main__":
    main(sys.argv[1:])
