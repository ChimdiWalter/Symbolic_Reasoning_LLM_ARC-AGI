"""The combination budget N, derived from the measurement by a fixed rule. Reads one record; runs nothing.

Rule (declared on 14 November before the repilot; read by the independent review, notes 0763 and 0764):
  - input: ticks_measure.json, made with the combination budget OFF and the 60-second processor-time allowance;
  - cohort: the development names that its setup decided eligible; exactly one complete L5-36 row for each, none
    missing, none repeated, none for a name outside the cohort, none ended by an infrastructure stop;
  - every such row counts, early fits included: N is the median of the OBSERVED PREFIXES under the 60-second
    policy, not a throughput measured over a full 60 seconds for every target;
  - median of the raw integer counts: the middle value for an odd count, the lower of the two middle values for an
    even count;
  - N is that median floored to two significant digits by integer arithmetic.
The unit is an offered argument tuple: one combination of arguments across the example vector, as the enumerator
counts it (not a unique program, not an evaluation on one example).

    python3 derive_n.py <ticks_measure.json> [<N_RECORD.json>]          Author: Chimdi Walter Ndubuisi
"""
import hashlib
import json
import sys

INFRASTRUCTURE = ("hard_stop", "memory_failure", "address_space_near_ceiling", "infrastructure_failure", "time_safety_limit")


def floor_two_significant(n):
    if n < 100:
        return n
    q = 10 ** (len(str(n)) - 2)
    return (n // q) * q


def derive(raw):
    d = json.loads(raw)
    pol = d["policy"]
    if pol.get("MAX_COMBINATIONS") is not None or pol.get("ALLOWANCE") != 60.0:
        raise SystemExit("refusing: the measurement was not made with the budget off and the 60-second allowance")
    eligible = sorted(d["eligible"])
    decided = sorted(t for t, v in d["setup"].items() if (v.get("decision") or v).get("status") == "eligible")
    if eligible != decided or not eligible:
        raise SystemExit("refusing: the eligible names do not agree with the setup decisions")
    rows = [r for r in d["searches"] if r["search"] == "L5-36"]
    names = [r["target"] for r in rows]
    if sorted(names) != eligible:
        raise SystemExit("refusing: L5-36 rows missing, repeated or outside the cohort (%s)" % sorted(set(names) ^ set(eligible)))
    bad = [r["target"] for r in rows if r.get("incomplete") or r["stop_class"] in INFRASTRUCTURE or not isinstance(r.get("ticks"), int) or r["ticks"] <= 0]
    if bad:
        raise SystemExit("refusing: incomplete or malformed L5-36 rows: %s" % bad)
    counts = sorted((r["ticks"], r["target"]) for r in rows)
    median = counts[(len(counts) - 1) // 2][0]
    return dict(N=floor_two_significant(median), median=median, n_rows=len(counts),
                counts=[dict(target=t, ticks=k, ending=next(r["stop_class"] for r in rows if r["target"] == t)) for k, t in counts])


def main(argv):
    raw = open(argv[0], "rb").read()
    out = derive(raw)
    body = dict(author="Chimdi Walter Ndubuisi", what="the combination budget N by the declared rule (derive_n.py); development names only",
                source=argv[0].split("/")[-1], source_sha256=hashlib.sha256(raw).hexdigest(),
                rule_script_sha256=hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
                name="median of observed prefixes under the 60-second policy, floored to two significant digits",
                unit="offered argument tuples (one combination of arguments across the example vector, as the enumerator counts it)", **out)
    print("N = %d (median %d over %d L5-36 rows)" % (out["N"], out["median"], out["n_rows"]))
    if len(argv) > 1:
        with open(argv[1], "x") as fh:
            json.dump(body, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
