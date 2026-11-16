"""Set the size of each operation's own definition beside what the run of 14 November could rebuild. Groupings only.

Reads census_source.json (this folder) and the per-target records of the evidence-across-failures run
(experiments/evidence_across_failures_20261114/full_out, outside its development names; that run's numbers are not
yet audited). For each group of targets it gives how large the operations' own definitions are. No search, no new
outcome.

    python3 census_against_outcomes.py [out.json]            Author: Chimdi Walter Ndubuisi
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/path/to/repository"
RUN = os.path.join(ROOT, "experiments/evidence_across_failures_20261114/full_out/targets")
ARMS = ("A1x3", "A1x6", "A1x9", "A2x3", "A3x3")
DEV = {"add", "backdrop", "box", "color", "hmirror", "lefthalf", "mapply", "mfilter", "numcolors", "objects", "ofcolor", "other",
       "rapply", "righthalf", "rot180", "sign", "switch", "tophalf", "vfrontier", "width"}


def stats(xs):
    xs = sorted(xs)
    if not xs:
        return None
    q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
    return dict(n=len(xs), least=xs[0], quartile_1=q(0.25), median=q(0.5), quartile_3=q(0.75), most=xs[-1])


def main(argv):
    cen = json.load(open(os.path.join(HERE, "census_source.json")))["per_operation"]
    groups = {"right first fit in the three-wrapper arm": [], "a fit in some arm, none right": [], "no fit in any arm": [],
              "excluded at setup": []}
    for f in sorted(glob.glob(os.path.join(RUN, "*.json"))):
        r = json.load(open(f))
        t = r["target"]
        if t in DEV:
            continue
        if r.get("status") != "done":
            groups["excluded at setup"].append(t)
        elif r["arms"]["A3x3"].get("first_fit") == "right":
            groups["right first fit in the three-wrapper arm"].append(t)
        elif any(r["arms"][a].get("first_fit") in ("right", "wrong") for a in ARMS):
            groups["a fit in some arm, none right"].append(t)
        else:
            groups["no fit in any arm"].append(t)
    out = {}
    for g, ts in groups.items():
        out[g] = dict(targets=len(ts), nodes_of_own_definition=stats([cen[t]["nodes"] for t in ts]),
                      nodes_with_called_operations_inlined=stats([cen[t]["nodes_inlined"] for t in ts]),
                      one_return_expression=sum(cen[t]["one_return_expression"] for t in ts),
                      with_a_loop=sum(cen[t]["loops"] > 0 for t in ts), with_a_type_test=sum(cen[t]["type_tests"] > 0 for t in ts),
                      names_by_size=sorted((cen[t]["nodes"], cen[t]["nodes_inlined"], t) for t in ts))
        print("%-42s %3d targets | own definition, nodes: %s | inlined: %s | one expression %d, loop %d, type test %d" % (
            g, len(ts), {k: v for k, v in (out[g]["nodes_of_own_definition"] or {}).items() if k != "n"},
            {k: v for k, v in (out[g]["nodes_with_called_operations_inlined"] or {}).items() if k != "n"},
            out[g]["one_return_expression"], out[g]["with_a_loop"], out[g]["with_a_type_test"]))
    nofit = out["no fit in any arm"]["names_by_size"]
    print("no fit in any arm, by size of own definition (nodes, inlined, name), smallest first:", nofit[:20])
    print("right in the three-wrapper arm (nodes, inlined, name):", out["right first fit in the three-wrapper arm"]["names_by_size"])
    for n in (6, 8, 10, 12, 15, 20):
        print("no fit in any arm and own definition of at most %d nodes: %d; at most %d nodes inlined: %d" % (
            n, sum(a <= n for a, b, t in nofit), n, sum(b <= n for a, b, t in nofit)))
    if argv:
        with open(argv[0], "x") as fh:
            json.dump(dict(author="Chimdi Walter Ndubuisi", what="sizes of own definitions beside the unaudited outcomes of the run of 14 November; groupings only",
                           groups=out), fh, indent=1, sort_keys=True)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
