"""Render the tables of an EAF1 summary as Markdown, so that no number of the results record is typed by hand.

Reads <outdir>/SUMMARY.json (written by the frozen summarize_eaf) and, when given, the report of after_run_eaf.py and
the GNU time file of the detached job. Computes nothing new: every number printed is a field of those files or a sum
or count of such fields. Not part of the freeze (it runs after the run and takes no part in it). The protocol requires
that the found expressions are read before any count is reported (read_expressions.py).

    python3 results_tables_eaf.py <outdir> [--block outside|dev] [--check AFTER_RUN_CHECK.json] [--time time.txt]

--block outside (default): the block outside the development roster, which holds the primary reading.
--block dev: the development block (development only, never a result). Author: Chimdi Walter Ndubuisi
"""
import argparse
import json
import os
import re
import sys

ARMS = ("A1x3", "A1x6", "A1x9", "A2x3", "A3x3")
OUT = ("none", "right", "wrong")


def names(xs, cap=40):
    xs = list(xs or [])
    return "none" if not xs else ", ".join("`%s`" % x for x in xs[:cap]) + (" and %d more" % (len(xs) - cap) if len(xs) > cap else "")


def paired(c, title, primary):
    a1, a2 = c["first_arm"], c["second_arm"]
    t = c["paired_table_rows_first_arm_columns_second_arm"]
    L = ["### %s" % title, ""]
    if primary:
        L += ["Status of the declared criterion: **%s** (criterion met: %s)." % (c.get("status"), c.get("criterion_met")), ""]
    L += ["Targets read: %d. Rows are %s, columns are %s." % (c["n_targets_terminal"], a1, a2), "",
          "| %s \\ %s | none | right | wrong |" % (a1, a2), "|---|---|---|---|"]
    for o in OUT:
        L.append("| %s | %d | %d | %d |" % (o, t[o]["none"], t[o]["right"], t[o]["wrong"]))
    L += ["",
          "- Wrong first fits: %s %d, %s %d. Right first fits: %s %d, %s %d." % (
              a1, c["wrong_first_fits"][a1], a2, c["wrong_first_fits"][a2], a1, c["right_first_fits"][a1], a2, c["right_first_fits"][a2]),
          "- Favourable targets (%s wrong, %s not): %d: %s." % (a2, a1, c["n_favourable"], names(c["favourable_targets_second_wrong_first_not"])),
          "- Unfavourable targets (%s wrong, %s not): %d: %s." % (a1, a2, c["n_unfavourable"], names(c["unfavourable_targets_first_wrong_second_not"])),
          "- Exact two-sided sign test over those %d targets: p = %.6g." % (c["n_favourable"] + c["n_unfavourable"], c["p_two_sided_sign_test"]),
          "- The four conditions: " + "; ".join("%s: %s" % (k, v) for k, v in sorted(c["conditions"].items())) + ". All four hold: %s." % c["all_four_conditions_hold"]]
    timed = c.get("targets_with_a_wrong_only_because_the_final_check_timed_out") or []
    L.append("- First fits counted as wrong only because their final check ran out of time: %d: %s." % (len(timed), names(timed)))
    if timed:
        w = c["reading_without_the_timed_out_targets"]
        L.append("  Reading without them: %d targets; wrong %s %d, %s %d; right %s %d, %s %d; favourable %d, unfavourable %d; p = %.6g; all four hold: %s. "
                 "All four hold in both readings: %s." % (w["n_targets_terminal"], a1, w["wrong_first_fits"][a1], a2, w["wrong_first_fits"][a2],
                                                          a1, w["right_first_fits"][a1], a2, w["right_first_fits"][a2], w["n_favourable"],
                                                          w["n_unfavourable"], w["p_two_sided_sign_test"], w["all_four_conditions_hold"],
                                                          c.get("all_four_conditions_hold_in_both_readings")))
    L.append("- Incomplete targets: %s. Missing eligible targets: %s. Done targets outside the committed cohort: %s. Targets whose setup differs "
             "from the committed record: %s." % (names(c.get("incomplete_targets")), names(c.get("missing_eligible_targets")),
                                                 names(c.get("done_targets_outside_the_committed_cohort")),
                                                 names(c.get("targets_whose_setup_differs_from_the_committed_record"))))
    return L + [""]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--block", choices=("outside", "dev"), default="outside")
    ap.add_argument("--check")
    ap.add_argument("--time")
    a = ap.parse_args(argv)
    s = json.load(open(os.path.join(a.outdir, "SUMMARY.json")))
    key = "block_outside_development_roster" if a.block == "outside" else "block_development_roster_development_only"
    b = s[key]
    L = ["<!-- rendered by results_tables_eaf.py from %s (%s); do not edit the numbers by hand -->" % (os.path.join(a.outdir, "SUMMARY.json"), key), ""]
    if a.block == "dev":
        L += ["**DEVELOPMENT ROSTER ONLY: a rehearsal reading, never a result.**", ""]
    # ---- the run
    ex, fp, co = b["exclusions"], b["final_panels"], b["costs"]
    L += ["### The run", "",
          "- Targets listed %s, run %s, not yet run %s (whole roster). In this block: %d ran; construction cohort %d, admission cohort %d, reuse cohort %d; "
          "excluded at setup %d; incomplete %d." % (s.get("n_listed"), s.get("n_run"), s.get("n_not_yet_run"), b["n_targets_run"], b["cohort_sizes"]["construction"],
                                                    b["cohort_sizes"]["admission"], b["cohort_sizes"]["reuse"], ex["n"], b["incomplete_infrastructure"]["n"]),
          "- Exclusions by kind: " + (", ".join("%s %d" % (k, v) for k, v in sorted(ex["by_kind"].items())) or "none") + ".",
          "- Final panels of the %d done targets: generator inputs median %s (least %s); pooled inputs median %s (least %s); short of the declared "
          "number: %s." % (fp["n"], fp["generator_median"], fp["generator_min"], fp["pooled_median"], fp["pooled_min"], names(fp["pooled_short"])),
          "- Roles unavailable for some targets (admission or reuse): %d targets." % len(b.get("unavailable_roles") or {}),
          "- Processor time, sum over the done targets' own intervals: %s seconds." % co["total_cpu_s_of_targets"]]
    if a.time and os.path.exists(a.time):
        txt = open(a.time).read()
        g = lambda pat: (re.search(pat, txt) or [None, "?"])[1]
        L.append("- Whole process (GNU time, outer measurement): user %s s, system %s s, elapsed %s, exit status %s, maximum resident set %s kB." % (
            g(r"User time \(seconds\): ([0-9.]+)"), g(r"System time \(seconds\): ([0-9.]+)"), g(r"Elapsed \(wall clock\) time.*: ([0-9:.]+)"),
            g(r"Exit status: (\d+)"), g(r"Maximum resident set size \(kbytes\): (\d+)")))
    rc = s["reconciliation_with_committed_setup_record"]
    L += ["- Setup of the run against the committed setup record: compared %s targets; decisions differ %s; counts differ %s." % (
        rc.get("n_compared"), rc.get("n_decisions_differ"), rc.get("n_counts_differ")), ""]
    # ---- comparisons
    L += paired(b["PRIMARY_A3x3_against_A1x9"], "Primary: three wrappers with three examples each (A3x3) against one wrapper with nine examples (A1x9)",
                a.block == "outside")
    L += paired(b["secondary_A2x3_against_A1x6"], "Secondary: two wrappers with three examples each (A2x3) against one wrapper with six examples (A1x6)", False)
    # ---- five arms
    f = b["five_arms_side_by_side"]
    L += ["### The five arms side by side", "",
          "| arm | targets | none | right | wrong | incomplete | acquisition task exact through wrapper 1, 2, 3 | search CPU sum (s) | CPU to first fits, sum (s) | stops |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        v, c = f[arm], co["arms"][arm]
        te = v.get("task_exact_wrapper_1_2_3") or {}
        L.append("| %s | %d | %d | %d | %d | %d | %s, %s, %s | %s | %s | %s |" % (
            arm, v["n"], v["none"], v["right"], v["wrong"], v["incomplete"], te.get("1"), te.get("2"), te.get("3"), c["cpu_s_sum"], c["cpu_to_first_fit_sum"],
            ", ".join("%s %d" % (k, n) for k, n in sorted(c["stop_reasons"].items()))))
    L += ["", "Function cap reached (searches): " + ", ".join("%s %d" % (arm, co["arms"][arm]["function_cap_reached"]) for arm in ARMS) + ". "
          "Candidates tested (sum): " + ", ".join("%s %d" % (arm, co["arms"][arm]["candidates_tested_sum"]) for arm in ARMS) + ".", ""]
    # ---- admission
    ad = b["admissions_by_arm"]["by_arm"]
    L += ["### Admission (stage A's rule unchanged; admission cohort)", "",
          "| arm | targets in the admission cohort | first fits | admitted | right and admitted | wrong and admitted | right and not admitted |", "|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        v = ad[arm]
        L.append("| %s | %d | %d | %d | %d | %d | %d |" % (arm, v["n_admission_cohort"], v["n_first_fits"], v["admitted"], v["right_admissions"],
                                                         v["wrong_admissions"], v["right_first_fits_not_admitted"]))
    # ---- reuse
    ru = b["reuse"]
    L += ["", "### Reuse on a different task (reuse cohort: %d targets; declared secondary)" % ru["n_reuse_cohort"], "",
          "| source | available | reuse task exact on the final panel |", "|---|---|---|"]
    for arm in ARMS:
        v = ru["library_" + arm]
        L.append("| sealed library of %s, no search | %d libraries | %d |" % (arm, v["n_with_library"], v["reuse_task_exact"]))
    for k, lab in (("fresh_synthesis", "fresh synthesis of the whole program"), ("fresh_repair", "fresh repair of the missing call")):
        v = ru[k]
        L.append("| %s | %d fits (%s; unavailable %d) | %d |" % (lab, v["fits"], ", ".join("%s %d" % (x, n) for x, n in sorted(v["stop_classes"].items())),
                                                                 v["unavailable"], v["reuse_task_exact"]))
    L += ["", "Targets whose three reuse examples were not all usable: %s." % names(ru.get("support_unavailable_targets")), ""]
    # ---- held-out names apart
    h = b["held_out_names_apart"]
    L += ["### Names held out by the earlier study, read apart (%d names; no separate claim)" % len(h.get("names") or []), "",
          "| arm | targets | none | right | wrong |", "|---|---|---|---|---|"]
    for arm in ARMS:
        v = h["five_arms_side_by_side"][arm]
        L.append("| %s | %d | %d | %d | %d |" % (arm, v["n"], v["none"], v["right"], v["wrong"]))
    hp = h["A3x3_against_A1x9"]
    L += ["", "A3x3 against A1x9 on these names: favourable %d, unfavourable %d, p = %.6g." % (hp["n_favourable"], hp["n_unfavourable"], hp["p_two_sided_sign_test"]), ""]
    # ---- the after-run check
    if a.check and os.path.exists(a.check):
        ck = json.load(open(a.check))
        L += ["### After-run checks (after_run_eaf.py)", "",
              "- All checks passed: %s (%d checks). Checker sha256 %s." % (ck.get("all_passed"), len(ck.get("checks") or []), ck.get("checker_sha256")),
              "- Failed checks: %s." % names([c["check"] for c in ck.get("checks") or [] if not c.get("passed")])]
        na = (ck.get("near_the_allowance") or {}).get("by_arm") or {}
        L.append("- Searches that used up the allowance or found their first fit after 80%% of it, per arm: %s." % (
            ", ".join("%s %d" % (arm, len(na.get(arm) or [])) for arm in ARMS)))
        gb = ck.get("could_a_guard_have_fired") or {}
        top = gb.get("done_largest_time_outside_the_searches") or []
        L.append("- Can a CPU guard have fired? No guard can have fired for any target: %s. Largest processor time outside the searches: %s. "
                 "Not excluded by the bound: %s. Targets without a recorded time: %s." % (
                     gb.get("no_guard_can_have_fired"), ("%s s (`%s`)" % (top[0][0], top[0][1])) if top else "?",
                     "; ".join("%s (%s s): %s" % (n, g["cpu_seconds"], names(g["done_targets_not_excluded"] + g["other_targets_not_excluded"]))
                               for n, g in sorted((gb.get("by_guard") or {}).items())), names(gb.get("targets_without_a_recorded_time"))))
        fm = ck.get("full_out_manifest")
        if fm:
            L.append("- Output folder: %d files, manifest sha256 %s; SUMMARY.json sha256 %s." % (fm["n_files"], fm["sha256"], ck.get("summary_sha256")))
        L.append("")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
