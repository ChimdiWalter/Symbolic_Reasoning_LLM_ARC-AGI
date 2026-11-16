"""Name the targets behind the counts of an EAF1 summary, as Markdown. Groups records; computes no new measure.

Reads <outdir>/targets/*.json. Every list is a grouping of fields that the frozen code wrote into the records (first
fit, admitted, task exactness, reuse exactness, stops); the counts must equal those of SUMMARY.json, and the script
checks that they do for the five arms. Not part of the freeze. The development names are left out unless --dev.

    python3 results_names_eaf.py <outdir> [--dev]            Author: Chimdi Walter Ndubuisi
"""
import glob
import json
import os
import sys

ARMS = ("A1x3", "A1x6", "A1x9", "A2x3", "A3x3")
DEV = {"add", "backdrop", "box", "color", "hmirror", "lefthalf", "mapply", "mfilter", "numcolors", "objects", "ofcolor", "other",
       "rapply", "righthalf", "rot180", "sign", "switch", "tophalf", "vfrontier", "width"}


def nm(xs):
    xs = sorted(xs)
    return "none" if not xs else "%d: " % len(xs) + ", ".join("`%s`" % x for x in xs)


def main(argv):
    out, dev = argv[0], "--dev" in argv
    recs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(out, "targets", "*.json")))]
    recs = [r for r in recs if (r["target"] in DEV) == dev]
    done = [r for r in recs if r.get("status") == "done"]
    s = json.load(open(os.path.join(out, "SUMMARY.json")))
    b = s["block_development_roster_development_only" if dev else "block_outside_development_roster"]
    L = ["<!-- rendered by results_names_eaf.py from %s; groupings of the records, no new measure -->" % os.path.join(out, "targets"), ""]
    L += ["### Names behind the counts", ""]
    for arm in ARMS:
        g = {o: [r["target"] for r in done if r["arms"][arm].get("first_fit") == o and r["arms"][arm].get("stop_class") != "incomplete"]
             for o in ("right", "wrong", "none")}
        f = b["five_arms_side_by_side"][arm]
        assert (len(g["right"]), len(g["wrong"]), len(g["none"])) == (f["right"], f["wrong"], f["none"]), (arm, "counts differ from the summary")
        L += ["- **%s.** Right first fits %s. Wrong first fits %s." % (arm, nm(g["right"]), nm(g["wrong"]))]
    L += ["", "### Admission, by arm", ""]
    for arm in ARMS:
        adm = [r for r in done if r["arms"][arm].get("admitted")]
        wa = [r["target"] for r in adm if r["arms"][arm].get("first_fit") == "wrong"]
        ra = [r["target"] for r in adm if r["arms"][arm].get("first_fit") == "right"]
        rn = [r["target"] for r in done if r["arms"][arm].get("first_fit") == "right" and r["arms"][arm].get("admitted") is False]
        v = b["admissions_by_arm"]["by_arm"][arm]
        assert (len(ra), len(wa), len(rn)) == (v["right_admissions"], v["wrong_admissions"], v["right_first_fits_not_admitted"]), (arm, "admission counts")
        L += ["- **%s.** Wrong and admitted %s. Right and not admitted %s. Right and admitted %s." % (arm, nm(wa), nm(rn), nm(ra))]
    L += ["", "### Reuse, by source (reuse cohort)", ""]
    ru = [r for r in done if (r.get("cohorts") or {}).get("reuse")]
    for arm in ARMS:
        lib = [r for r in ru if r["arms"][arm].get("library")]
        ex = [r["target"] for r in lib if r["arms"][arm].get("reuse_exact")]
        nx = [r["target"] for r in lib if not r["arms"][arm].get("reuse_exact")]
        v = b["reuse"]["library_" + arm]
        assert (len(lib), len(ex)) == (v["n_with_library"], v["reuse_task_exact"]), (arm, "reuse counts")
        L += ["- **Sealed library of %s.** Reuse task exact %s. With a library and not exact %s." % (arm, nm(ex), nm(nx))]
    for key, lab in (("fresh_synthesis", "Fresh synthesis of the whole program"), ("fresh_repair", "Fresh repair of the missing call")):
        cs = [(r["target"], ((r.get("reuse") or {}).get("controls") or {}).get(key) or {}) for r in ru]
        ex = [t for t, c in cs if c.get("exact_on_final")]
        fits = [t for t, c in cs if c.get("fit")]
        used = [t for t, c in cs if c.get("stop_class") == "allowance_used_up"]
        v = b["reuse"][key]
        assert (len(fits), len(ex)) == (v["fits"], v["reuse_task_exact"]), (key, "control counts")
        L += ["- **%s.** Reuse task exact %s. Fits that are not exact: %d. Searches that used up the allowance: %d." % (
            lab, nm(ex), len(fits) - len(ex), len(used))]
    L += ["", "### Searches that ended at the allowance, by arm", ""]
    for arm in ARMS:
        used = [r["target"] for r in done if r["arms"][arm].get("stop_class") == "allowance_used_up"]
        L += ["- %s: %s." % (arm, nm(used))]
    L += ["", "### Excluded at setup, by kind", ""]
    kinds = {}
    for r in recs:
        if r.get("status") == "excluded":
            kinds.setdefault(r.get("reason_kind"), []).append(r["target"])
    for k in sorted(kinds):
        L += ["- %s %s." % (k, nm(kinds[k]))]
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
