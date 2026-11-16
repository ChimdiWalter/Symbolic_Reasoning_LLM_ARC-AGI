"""Do the arity rule and the cap of 16,000 make the second stage of the library-only system weaker? A sensitivity
check on development names. Never a result.

If the size limit of C is 4, the arity rule and the cap on function-valued entries change only one of the six
searches: L5-36, the second stage of the library-only system (no function is made at a size limit of 4). This
script runs L5-36 on every eligible development name twice, on the same 36 fit examples, with the same allowance
and the same cap on bank entries:
  A   arity rule on,  cap on function-valued entries 16,000   (the declared setting)
  B   arity rule off, cap on function-valued entries 1,000    (the setting of the first record)
and records for each: how the search ended, the level completed, the bank, the function-valued entries, the
processor time, the first fit if any, and whether that expression agrees with the true operation on every input of
the development final panel. Everything goes through this experiment's own path: episode_bl (setup, the search,
the final panel under its guard, the final check) with the two presets changed in this process only; no file is
changed.

    env PYTHONHASHSEED=0 python -s -B sensitivity_l5_rule.py <out.json> [--targets a,b] [--settings A,B]

Development names only.                                                        Author: Chimdi Walter Ndubuisi
"""
import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bl_frozen                 # noqa: E402,F401
import guards_bl as G            # noqa: E402
import presets_bl as P           # noqa: E402
import run_bl                    # noqa: E402

SETTINGS = {"A": dict(ARITY_RULE=True, MAX_FN=16_000), "B": dict(ARITY_RULE=False, MAX_FN=1_000)}
NOT_RUN = "not part of this sensitivity check"


def one(E, X, setting):
    """L5-36 for one development name under one setting, with the final check of its first fit."""
    P.ARITY_RULE, P.MAX_FN = SETTINGS[setting]["ARITY_RULE"], SETTINGS[setting]["MAX_FN"]       # in this process only
    ep = E.Episode(X)
    if ep.setup() is not None:
        return dict(eligible=False, reason_kind=ep.res.get("reason_kind"))
    ep.seal("first_fits_9", dict(sensitivity=NOT_RUN))
    ep.rec.open("fit36")
    a = ep.run_search("L5-36", "L", "fit36", P.SIZE_L5)
    row = dict(eligible=True, setting=setting, arity_rule=a["arity_rule"], max_fn=a["max_fn"], allowance=a["allowance"], max_bank=a["max_bank"],
               stop_class=a["stop_class"], coverage=a["coverage"], level_completed=a["level_completed"], bank=a["bank"],
               function_valued_entries=a.get("function_valued_entries"), function_cap_reached=a["function_cap_reached"],
               cap_reached_at=a["function_making"]["cap_reached_at"], cpu_s=a["cpu_s"], expr=a["expr"], size=a["size"],
               refused_by_the_wrappers=a["refused_by_the_wrappers"], address_space_peak_kb=a["address_space_peak_kb"],
               resident_peak_kb=a["resident_peak_kb"], error=a["error"], right_on_the_final_panel=None, final=None)
    if a["fit"]:
        ep.seal("first_fits_36", dict(sensitivity=NOT_RUN, L5_36=a["expr"]))
        ep.seal("selections", dict(sensitivity=NOT_RUN))
        if ep.open_final():
            fit = ep.fit["L5-36"]
            c = ep.final_check("the first fit of L5-36", ep.candidate(fit["tree"], fit["op_ns"], fit["leaf_ns"], fit["consts"]))
            row["final"] = c
            row["right_on_the_final_panel"] = None if c["incomplete"] else c["right"]
        row["final_panel"] = ep.res.get("final_panel")
    return row


def main(argv):
    out_path = argv[0]
    if os.path.exists(out_path):
        raise SystemExit("refusing: %s exists" % out_path)
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("run with PYTHONHASHSEED=0")
    names = list(P.DEV_ROSTER)
    if "--targets" in argv:
        names = argv[argv.index("--targets") + 1].split(",")
        bad = [t for t in names if t not in P.DEV_ROSTER]
        if bad:
            raise SystemExit("refusing: development names only (%s)" % bad)
    settings = argv[argv.index("--settings") + 1].split(",") if "--settings" in argv else ["B", "A"]
    if any(s not in SETTINGS for s in settings):
        raise SystemExit("refusing: settings are A and B")
    declared = dict(ARITY_RULE=P.ARITY_RULE, MAX_FN=P.MAX_FN)
    ceiling = run_bl.set_memory_ceiling()
    import episode_bl as E
    pools_cpu_s = run_bl.set_up_pools()
    rows, stop = {}, None
    t0, w0 = time.process_time(), time.time()
    try:
        for i, X in enumerate(names):
            rows[X] = {}
            for setting in settings:
                rows[X][setting] = r = one(E, X, setting)
                if not r["eligible"]:
                    print("[%d/%d] %s not eligible (%s)" % (i + 1, len(names), X, r["reason_kind"]), flush=True)
                    break
                print("[%d/%d] %s %s %-34s level %s bank %s fn %s cpu %.1f | %s | right on the final panel: %s" % (
                    i + 1, len(names), X, setting, r["stop_class"], r["level_completed"], r["bank"], r["function_valued_entries"], r["cpu_s"],
                    r["expr"], r["right_on_the_final_panel"]), flush=True)
    except G.NearCeiling as e:
        stop = e
    finally:
        P.ARITY_RULE, P.MAX_FN = declared["ARITY_RULE"], declared["MAX_FN"]
    eligible = [X for X, r in rows.items() if all(v.get("eligible") for v in r.values()) and len(r) == len(settings)]

    def count(setting, pred):
        return sum(1 for X in eligible if pred(rows[X][setting]))
    reading = {}
    for s in settings:
        reading[s] = dict(searches=len(eligible), fits=count(s, lambda r: r["expr"] is not None),
                          first_fit_right_on_the_final_panel=count(s, lambda r: r["right_on_the_final_panel"] is True),
                          first_fit_wrong_on_the_final_panel=count(s, lambda r: r["right_on_the_final_panel"] is False),
                          endings={c: count(s, lambda r, c=c: r["stop_class"] == c) for c in sorted({rows[X][s]["stop_class"] for X in eligible})},
                          cpu_s_sum=round(sum(rows[X][s]["cpu_s"] for X in eligible), 1))
    differences = []
    if set(settings) == {"A", "B"}:
        for X in eligible:
            a, b = rows[X]["A"], rows[X]["B"]
            if (a["expr"], a["right_on_the_final_panel"]) != (b["expr"], b["right_on_the_final_panel"]):
                differences.append(dict(target=X, A=dict(expr=a["expr"], right=a["right_on_the_final_panel"], stop_class=a["stop_class"]),
                                        B=dict(expr=b["expr"], right=b["right_on_the_final_panel"], stop_class=b["stop_class"])))
    body = dict(author="Chimdi Walter Ndubuisi", label="development only: a sensitivity check; never a result",
                what="L5-36 on every eligible development name under two settings of the arity rule and the cap on function-valued entries",
                settings={s: SETTINGS[s] for s in settings}, names=names, eligible=eligible, rows=rows, reading=reading,
                names_whose_first_fit_or_its_final_reading_differs=differences, policy=run_bl.policy(), memory_ceiling=ceiling,
                pools_setup_cpu_s=pools_cpu_s, cpu_s=round(time.process_time() - t0, 1), wall_s=round(time.time() - w0, 1),
                ended_early=None if stop is None else str(stop), resident_peak_kb=G.resident_peak_kb(),
                address_space_peak_kb=G.address_space_peak_kb(), python=platform.python_version())
    with open(out_path, "x") as f:
        json.dump(body, f, indent=1, sort_keys=True, default=str)
        f.write("\n")
    print("reading:", json.dumps(reading, sort_keys=True))
    print("differences:", json.dumps(differences, sort_keys=True))
    return P.EXIT_NEAR_CEILING if stop is not None else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
