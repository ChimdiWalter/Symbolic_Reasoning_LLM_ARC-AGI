"""List the found expressions of an EAF1 output folder for reading by a person. Author: Chimdi Walter Ndubuisi

Reads targets/<name>.json only; computes nothing new and changes nothing. Not part of the freeze (it runs after the
run and takes no part in it). The protocol requires that the found expressions are read before any count is reported.

    python3 read_expressions.py <outdir> [--dev]        (--dev: the development names instead of the others)
"""
import glob
import json
import os
import sys

ARMS = ("A1x3", "A1x6", "A1x9", "A2x3", "A3x3")
DEV = {"add", "backdrop", "box", "color", "hmirror", "lefthalf", "mapply", "mfilter", "numcolors", "objects", "ofcolor", "other",
       "rapply", "righthalf", "rot180", "sign", "switch", "tophalf", "vfrontier", "width"}


def main(argv):
    out, want_dev = argv[0], "--dev" in argv
    recs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(out, "targets", "*.json")))]
    recs = [r for r in recs if (r["target"] in DEV) == want_dev]
    done = [r for r in recs if r.get("status") == "done"]
    print("targets: %d, done %d, excluded %d, incomplete %d" % (len(recs), len(done), sum(r.get("status") == "excluded" for r in recs),
                                                                 sum(r.get("status") == "incomplete" for r in recs)))
    groups = {}
    for r in done:
        a3, a1 = r["arms"]["A3x3"], r["arms"]["A1x9"]
        key = "A3x3 %s / A1x9 %s" % (a3.get("first_fit") if a3.get("stop_class") != "incomplete" else "INCOMPLETE",
                                     a1.get("first_fit") if a1.get("stop_class") != "incomplete" else "INCOMPLETE")
        groups.setdefault(key, []).append(r)
    for key in sorted(groups):
        rs = groups[key]
        print("\n==== %s: %d targets" % (key, len(rs)))
        if key == "A3x3 none / A1x9 none":
            fits = [r for r in rs if any(r["arms"][a].get("expr") for a in ARMS)]
            print("   (no fit in either; %d of them have a fit in another arm, listed below)" % len(fits))
            rs = fits
        for r in rs:
            w = r["setup"]["wrappers"]["chosen"]
            print("-- %s | wrappers %s | tuples from %s | held-out name: %s" % (r["target"], w[:3], r["setup"].get("acquisition_source"), r.get("held_out_family")))
            last = None
            for a in ARMS:
                v = r["arms"][a]
                if not v.get("expr"):
                    print("     %s: none (%s, level %s, cpu %.1f)" % (a, v.get("stop_class"), v.get("level_completed"), v.get("cpu_s") or 0))
                    continue
                same = " (same as above)" if v["expr"] == last else ""
                last = v["expr"]
                ce = v.get("counterexample") or {}
                det = v.get("right_detail") or {}
                print("     %s: %s  ->  %s%s | final agree gen %s pooled %s | task exact %s | admitted %s%s" % (
                    a, v["expr"], str(v.get("first_fit")).upper(), same, det.get("gen"), det.get("pooled"),
                    "".join("Y" if (v.get("task_exact") or {}).get(k) else "n" for k in ("1", "2", "3")), v.get("admitted"),
                    "" if (not ce or same) else (" | first counterexample: the candidate raised on a final input" if ce.get("got") == "ERR" else
                                                 " | first counterexample: %s" % ce.get("note") if ce.get("note") else
                                                 " | first counterexample: want %s got %s" % (str(ce.get("want"))[:60], str(ce.get("got"))[:60]))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
