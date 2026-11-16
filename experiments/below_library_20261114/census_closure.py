"""How far could a library be regrown step by step, by the sizes of its own source? An upper bound; nothing is run.

From census_source.json. An operation is "regrowable at step s" when its own definition has at most s nodes (a
called library operation counting as one node) and every library operation it calls is regrowable at step s too.
That is what repeated cycles could reach if every admitted operation became a building block. "In one step" is the
same without cycles: the operation with all its calls inlined has at most s nodes. The difference is what cycles
could add. These are bounds read from the source as written: a search can find other routes, and it can also fail
to find these.

    python3 census_closure.py [out.json]            Author: Chimdi Walter Ndubuisi
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS_RECORD = "/path/to/repository/experiments/evidence_across_failures_20261114/SETUP_RECORD_ALL_3.json"


def main(argv):
    cen = json.load(open(os.path.join(HERE, "census_source.json")))["per_operation"]
    roster = set(json.load(open(TARGETS_RECORD))["targets"])          # the 145 operations searched in the earlier studies
    out = {}
    for s in (3, 4, 5, 6, 7, 8, 10, 12, 15, 20):
        ok, layer, layers = set(), 0, []
        while True:
            new = {t for t, r in cen.items() if t not in ok and r["nodes"] <= s and not r["calls_itself"]
                   and all(c in ok for c in r["library_operations_called"])}
            if not new:
                break
            ok |= new
            layer += 1
            layers.append(len(new))
        one = {t for t, r in cen.items() if r["nodes_inlined"] <= s}
        out[str(s)] = dict(step_nodes=s, regrowable_with_cycles=len(ok), in_one_step=len(one), added_by_cycles=len(ok - one),
                           cycles_needed=layer, new_per_cycle=layers, of_the_145_searched_operations=dict(with_cycles=len(ok & roster), in_one_step=len(one & roster)),
                           added_by_cycles_names=sorted(ok - one))
        print("step of at most %2d nodes: with cycles %3d of %d (%3d of the 145 searched); in one step %3d (%3d); added by cycles %2d; cycles %d %s" % (
            s, len(ok), len(cen), len(ok & roster), len(one), len(one & roster), len(ok - one), layer, layers))
    print("added by cycles at 6 nodes:", out["6"]["added_by_cycles_names"])
    print("added by cycles at 8 nodes:", out["8"]["added_by_cycles_names"])
    if argv:
        with open(argv[0], "x") as fh:
            json.dump(dict(author="Chimdi Walter Ndubuisi", what="upper bounds on stepwise regrowth, read from the source census; nothing run", by_step=out),
                      fh, indent=1, sort_keys=True)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
