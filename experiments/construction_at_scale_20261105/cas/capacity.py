"""Source capacity of the pools under S1's size caps (phase 1; reads input grids only).

    python -m cas.capacity OUT.json

For each pool, the number of source tasks whose generator inputs (up to four demonstration inputs and the first
query input, S1's cgrow/tasks.py inputs_of) all have at most s rows and at most s columns, for several s. S1's caps
admit a task only if every input is at most 12 x 12 and every output at most 16 x 16, so this bounds how many tasks
one world can draw from a pool (each source serves at most one task of a world).
"""
import json
import sys

from cas import env as E
from cgrow import tasks as T                                                    # noqa: E402

SIDES = (5, 8, 10, 12, 15, 20, 30)


def main(out):
    pools = E.load(E.STUDY + "/config/POOLS.json")
    res = {}
    for which in ("pilot", "main"):
        rows = {}
        for t in pools[which]:
            xs = T.inputs_of(t, pools["split_of"][t])
            rows[t] = (max(len(g) for g in xs), max(len(g[0]) for g in xs))
        res[which] = {"n": len(rows)} | {f"rows_and_cols_at_most_{s}": sum(max(r) <= s for r in rows.values())
                                         for s in SIDES} \
            | {"rows_at_most_5_cols_at_most_12": sum(r[0] <= 5 and r[1] <= 12 for r in rows.values()),
               "cols_at_most_5_rows_at_most_12": sum(r[1] <= 5 and r[0] <= 12 for r in rows.values()),
               "cols_at_most_8_rows_at_most_12": sum(r[1] <= 8 and r[0] <= 12 for r in rows.values())}
    E.dump(out, res)
    print(json.dumps(res))


if __name__ == "__main__":
    main(sys.argv[1])
