"""Render the below-library results as Markdown tables from the frozen records.

Every number printed is a field of the input files, or a count or sum of such
fields.  Where a number appears both in the summary and can be counted from
the per-operation records, the script counts from the records and checks
agreement.  On any mismatch it names the field on standard error, writes
nothing and exits 1.

Usage:
    python3 -I render_results_tables.py <outdir> \
        --check AFTER_RUN_CHECK.json --earlier EARLIER_RESULT_CHECK.json \
        --time time.txt --out tables.md

Author: Chimdi Walter Ndubuisi
"""
import argparse
import collections
import json
import math
import os
import re
import statistics
import sys

SEARCHES = ["L4-9", "LC4-9", "L4-36", "L5-36", "LC4-36", "C-36"]
SYSTEMS = ["library_only", "smaller_blocks"]
SYS_LABEL = {"library_only": "library only",
             "smaller_blocks": "smaller blocks"}
FITS = ["right", "wrong", "none"]
STOP_ORDER = ["found", "size_limit_completed",
              "combination_budget_used_up"]


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_json(path, label):
    if not os.path.isfile(path):
        die("required file missing (%s): %s" % (label, path))
    with open(path) as f:
        return json.load(f)


def load_records(outdir):
    tdir = os.path.join(outdir, "targets")
    if not os.path.isdir(tdir):
        die("missing targets directory: %s" % tdir)
    recs = {}
    for fn in sorted(os.listdir(tdir)):
        if fn.endswith(".json"):
            recs[fn[:-5]] = load_json(os.path.join(tdir, fn), fn)
    return recs


def xc(label, summary_val, counted_val):
    if summary_val != counted_val:
        die("cross-check failed: %s: summary %r, counted %r"
            % (label, summary_val, counted_val))


def req(d, key, label):
    """Require a key in a dict; die with a clear message if absent."""
    if key not in d:
        die("required field missing: %s" % label)
    return d[key]


def nlist(xs):
    xs = sorted(xs or [])
    return "none" if not xs else ", ".join("`%s`" % x for x in xs)


def esc(s):
    return str(s).replace("|", "\\|") if s is not None else ""


def hum(s):
    """Replace underscores with spaces for display names."""
    return str(s).replace("_", " ")


def fmt_p(p):
    if p == 0:
        return "0"
    return "%.4g" % p


def fmt_s(v):
    return "%.2f" % v


def sign_test_p(w, el):
    n = w + el
    if n == 0:
        return 1.0
    k0 = max(w, el)
    tail = sum(math.comb(n, k) for k in range(k0, n + 1))
    return min(1.0, 2.0 * tail / (2.0 ** n))


def parse_gnu_time(path):
    if not os.path.isfile(path):
        die("required file missing (time): %s" % path)
    txt = open(path).read()
    fields = [
        ("user_s", r"User time \(seconds\): ([0-9.]+)"),
        ("system_s", r"System time \(seconds\): ([0-9.]+)"),
        ("wall", r"Elapsed \(wall clock\) time.*?: ([0-9:.]+)"),
        ("peak_kb", r"Maximum resident set size \(kbytes\): (\d+)"),
        ("exit", r"Exit status: (\d+)")]
    result = {}
    for name, pat in fields:
        m = re.search(pat, txt)
        if not m:
            die("time file missing field: %s" % name)
        result[name] = m.group(1)
    return result


def sel_verdict(sel):
    if sel.get("expr") is None:
        return "selected nothing"
    return "right" if sel.get("rebuilt") else "wrong"


def expr_cell(e):
    if e is None:
        return ""
    return "`%s`" % esc(e)


def yn(val):
    return "yes" if val else "no"


def paired_from_records(cohort):
    both, sb_only, lo_only, neither = [], [], [], []
    for op in sorted(cohort):
        lo = sel_verdict(cohort[op]["selection"]["library_only"]) == "right"
        sb = sel_verdict(cohort[op]["selection"]["smaller_blocks"]) == "right"
        (both if lo and sb else sb_only if sb else
         lo_only if lo else neither).append(op)
    return {"both": both, "smaller_blocks_only": sb_only,
            "library_only_only": lo_only, "neither": neither,
            "N": len(cohort),
            "library_only": len(both) + len(lo_only),
            "smaller_blocks": len(both) + len(sb_only)}


def search_agg(cohort, sname):
    fits = {"right": 0, "wrong": 0, "none": 0}
    stops, cpus, largest = {}, [], (0.0, "")
    for op, rec in sorted(cohort.items()):
        s = rec["searches"][sname]
        ff = s.get("first_fit", "none")
        fits[ff] = fits.get(ff, 0) + 1
        sc = s.get("stop_class", "unknown")
        stops[sc] = stops.get(sc, 0) + 1
        cpu = s.get("cpu_s", 0)
        cpus.append(cpu)
        if cpu > largest[0]:
            largest = (cpu, op)
    return {"n": len(cohort), "fits": fits, "stops": stops,
            "sum": sum(cpus),
            "median": statistics.median(cpus) if cpus else 0,
            "largest": largest[0], "largest_op": largest[1]}


def versus_from_records(cohort, first_search, second_search):
    c = {"both": 0, "first_only": 0, "second_only": 0, "neither": 0}
    for rec in cohort.values():
        a = rec["searches"][first_search].get("first_fit") == "right"
        b = rec["searches"][second_search].get("first_fit") == "right"
        if a and b:
            c["both"] += 1
        elif a:
            c["first_only"] += 1
        elif b:
            c["second_only"] += 1
        else:
            c["neither"] += 1
    return c


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--check", required=True)
    ap.add_argument("--earlier", required=True)
    ap.add_argument("--time", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    summ = load_json(os.path.join(a.outdir, "SUMMARY.json"), "SUMMARY.json")
    recs = load_records(a.outdir)
    run_costs = load_json(os.path.join(a.outdir, "RUN_COSTS.json"),
                          "RUN_COSTS.json")
    after = load_json(a.check, "AFTER_RUN_CHECK.json")
    earlier = load_json(a.earlier, "EARLIER_RESULT_CHECK.json")
    gnu = parse_gnu_time(a.time)

    c = summ["counts"]
    done = {k for k, v in recs.items() if v.get("status") == "done"}
    excl = {k for k, v in recs.items() if v.get("status") == "excluded"}
    xc("counts.records", c["records"], len(recs))
    xc("counts.done", c["done"], len(done))
    xc("counts.excluded", c["excluded"], len(excl))
    xc("counts.incomplete", c["incomplete"],
       len(recs) - len(done) - len(excl))
    xc("counts.listed", c["listed"], len(recs))

    size_c = summ["size_c"]
    sec = summ["secondary_outside_the_development_names"]
    dev_blk = summ["development_names_development_only"]
    lo_sec = sec["longer_stratum"]
    oda = sec["outside_development_all_strata"]
    L = []

    pcoh = {k: v for k, v in recs.items()
            if v["status"] == "done" and v["stratum"] == "longer"
            and not v.get("dev")}
    nd_r = {k: v for k, v in recs.items()
            if v["status"] == "done" and not v.get("dev")}
    all_done = {k: v for k, v in recs.items()
                if v["status"] == "done"}

    # ================================================================
    # Names
    # ================================================================
    L += [
        "### Names used in these tables", "",
        "- **Library only**: searches the retained library operations,"
        " first up to %d nodes on 36 examples (L%d-36),"
        " then up to five nodes (L5-36)." % (size_c, size_c),
        "- **Smaller blocks**: searches the library together with the"
        " smaller blocks up to %d nodes on 36 examples (LC%d-36),"
        " then the blocks with the retained operations"
        " alone (C-36)." % (size_c, size_c),
        "- **L%d-9** and **LC%d-9**: the same %d-node searches on"
        " nine examples." % (size_c, size_c, size_c),
        "- **Right** and **wrong**: the record's verdict on the"
        " final panel.",
        "- **Selected nothing**: neither stage of the system found"
        " an expression that fits all 36 examples.", ""]

    # ================================================================
    # Run
    # ================================================================
    L += ["### Run", "",
          "Listed %d, records %d, done %d, excluded %d, incomplete %d."
          % (c["listed"], c["records"], c["done"], c["excluded"],
             c["incomplete"]), ""]
    den = summ["denominators"]["original_outside_development"]
    strata = [("short", "Short"), ("longer", "Longer"),
              ("longer_7_to_15", "Longer, 7 to 15 nodes"),
              ("longer_over_15", "Longer, more than 15 nodes")]
    all_kinds = sorted({k for sk, _ in strata
                        for k in den[sk].get(
                            "committed_excluded_by_kind", {})})
    hdr = ("| stratum | original | eligible | excluded | "
           + " | ".join(hum(k) for k in all_kinds) + " |")
    L += [hdr, "|" + "|".join(["---"] * (4 + len(all_kinds))) + "|"]
    for sk, slabel in strata:
        d = den[sk]
        bk = d.get("committed_excluded_by_kind", {})
        cells = [slabel, str(d["original"]),
                 str(d["committed_eligible"]),
                 str(d["excluded_in_the_run"])]
        cells += [str(bk.get(k, 0)) for k in all_kinds]
        L.append("| " + " | ".join(cells) + " |")
    L.append("")

    dev_n = summ["denominators"]["development_names"]
    dev_done_n = sum(1 for v in recs.values()
                     if v.get("dev") and v.get("status") == "done")
    dev_excl_n = sum(1 for v in recs.values()
                     if v.get("dev") and v.get("status") == "excluded")
    L += ["Development names: %d listed, %d done, %d excluded."
          % (dev_n, dev_done_n, dev_excl_n), ""]

    # excluded records grouped
    excl_longer = {k: v for k, v in recs.items()
                   if v["status"] == "excluded"
                   and v.get("stratum") == "longer"
                   and not v.get("dev")}
    excl_short = {k: v for k, v in recs.items()
                  if v["status"] == "excluded"
                  and v.get("stratum") == "short"
                  and not v.get("dev")}
    excl_dev = {k: v for k, v in recs.items()
                if v["status"] == "excluded" and v.get("dev")}
    for label, group in [
            ("Longer stratum outside development (%d):" % len(excl_longer),
             excl_longer),
            ("Short stratum outside development (%d):" % len(excl_short),
             excl_short),
            ("Development names (%d):" % len(excl_dev), excl_dev)]:
        L += [label, ""]
        for op in sorted(group):
            L.append("- `%s`: %s"
                     % (op, req(group[op], "reason",
                                "%s.reason" % op)))
        L.append("")

    # final panels of the primary cohort
    fp = lo_sec["final_panels"]
    L += [
        "Final panels of the primary cohort (%d done targets):"
        " generator minimum %d, pooled median %s, pooled minimum %d,"
        " pooled discarded sum %d, pooled short: %s,"
        " pooled not evaluated: %s."
        % (fp["n"], fp["generator_min"], fp["pooled_median"],
           fp["pooled_min"], fp["pooled_discarded_sum"],
           nlist(fp.get("pooled_short")),
           nlist(fp.get("pooled_not_evaluated"))), ""]

    L += [
        "- Job costs from %s: user %s s, system %s s, wall clock %s,"
        " peak resident %s kB, exit status %s."
        % (a.time, gnu["user_s"], gnu["system_s"], gnu["wall"],
           gnu["peak_kb"], gnu["exit"]),
        "- From %s: cpu_process_s %s, wall_s %s."
        % (os.path.join(a.outdir, "RUN_COSTS.json"),
           fmt_s(run_costs["cpu_process_s"]),
           fmt_s(run_costs["wall_s"])), ""]

    L.append("After-run checks (passed: %s):" % after["passed"])
    L.append("")
    for ck in after.get("checks", []):
        L.append("- %s: %s" % (ck["check"],
                 "passed" if ck["passed"] else "failed"))
    L.append("")

    info = req(after, "informational",
               "AFTER_RUN_CHECK.informational")
    near = req(info, "searches_within_20_percent_of_the_safety_limit",
               "informational.searches_within_20_percent_of_the_safety_limit")
    gt = req(info, "guard_timeouts", "informational.guard_timeouts")
    gm = req(info, "guarded_steps_without_a_mark",
             "informational.guarded_steps_without_a_mark")
    L += [
        "- Searches within 20%% of the safety limit: %s." % nlist(near),
        "- Guard timeouts: %s." % (
            ", ".join("%s: %s" % kv for kv in sorted(gt.items()))
            if gt else "none"),
        "- Guarded steps without a mark: %s." % (
            ", ".join("%s: %s" % kv for kv in sorted(gm.items()))
            if gm else "none")]

    # guard bound
    gb = req(info, "guard_bound", "informational.guard_bound")
    L.append(
        "- Guard bound: shortest guard %s s, margin %s s,"
        " %d targets below the bound,"
        " not excluded: %s, unknown time: %s."
        % (gb["shortest_guard_s"], gb["margin_s"], gb["below"],
           nlist(gb.get("not_excluded")),
           nlist(gb.get("unknown"))))
    L.append("")

    freeze_h = req(after, "freeze_sha256",
                   "AFTER_RUN_CHECK.freeze_sha256")
    setup_h = req(after, "setup_record_sha256",
                  "AFTER_RUN_CHECK.setup_record_sha256")
    L += ["- Freeze sha256: `%s`." % freeze_h,
          "- Setup record sha256: `%s`." % setup_h, ""]

    # ================================================================
    # Primary comparison
    # ================================================================
    prim = summ["PRIMARY"]
    pc = paired_from_records(pcoh)
    xc("PRIMARY.N", prim["N"], pc["N"])
    xc("PRIMARY.both", prim["both"], len(pc["both"]))
    xc("PRIMARY.neither", prim["neither"], len(pc["neither"]))
    xc("PRIMARY.rebuilt.library_only",
       prim["rebuilt"]["library_only"], pc["library_only"])
    xc("PRIMARY.rebuilt.smaller_blocks",
       prim["rebuilt"]["smaller_blocks"], pc["smaller_blocks"])
    xc("PRIMARY.W", prim["W"],
       len(pc["smaller_blocks_only"]))
    xc("PRIMARY.L", prim["L"],
       len(pc["library_only_only"]))
    for cell in ("both", "smaller_blocks_only",
                 "library_only_only", "neither"):
        xc("PRIMARY.targets.%s" % cell,
           sorted(prim["targets"][cell]), sorted(pc[cell]))

    L += ["### Primary comparison", "",
          "Cohort: done records with stratum longer, outside the"
          " development names (N = %d)." % prim["N"], "",
          "| system | right | selected and wrong"
          " | selected nothing | of |",
          "|---|---|---|---|---|"]
    for sk in SYSTEMS:
        ss = lo_sec["systems"][sk]
        L.append("| %s | %d | %d | %d | %d |"
                 % (SYS_LABEL[sk], ss["rebuilt"],
                    len(ss["selected_and_wrong"]),
                    prim["N"] - ss["selected"], prim["N"]))
    L.append("")

    L += [
        "- Right in both (%d): %s."
        % (len(pc["both"]), nlist(pc["both"])),
        "- Right in smaller blocks only (%d): %s."
        % (len(pc["smaller_blocks_only"]),
           nlist(pc["smaller_blocks_only"])),
        "- Right in library only only (%d): %s."
        % (len(pc["library_only_only"]),
           nlist(pc["library_only_only"])),
        "- Right in neither (%d): %s."
        % (len(pc["neither"]), nlist(pc["neither"])), ""]

    W = len(pc["smaller_blocks_only"])
    Lo = len(pc["library_only_only"])
    my_p = sign_test_p(W, Lo)
    sum_p = prim["p_two_sided_sign_test"]
    if abs(my_p - sum_p) > 1e-12:
        die("cross-check failed: PRIMARY.p_two_sided_sign_test:"
            " summary %r, computed %r" % (sum_p, my_p))

    L += [
        "- Two-sided exact sign test: p = %s." % fmt_p(sum_p),
        "- W (rebuilt by smaller blocks only): %d."
        " L (rebuilt by library only only): %d."
        " W minus L: %d." % (prim["W"], prim["L"],
                              prim["W_minus_L"]),
        "- Concordant: both right %d, neither right %d."
        % (prim["both"], prim["neither"]), ""]

    CRIT_LABELS = {
        "1_W_greater_than_L": "W greater than L",
        "2_p_below_0_05": "p below 0.05",
        "3_calibration_valid_and_passed": "calibration valid and passed",
        "4_cohort_complete": "cohort complete"}
    cp = prim["criterion_parts"]
    L.append("Criterion parts:")
    L.append("")
    for k in sorted(cp):
        L.append("- %s: %s" % (CRIT_LABELS.get(k, hum(k)), cp[k]))
    L += ["",
          "- Status: %s. Provisional: %s."
          % (hum(prim["status"]), prim["provisional"]), ""]

    # ================================================================
    # Calibration
    # ================================================================
    cal = summ["calibration"]
    elig = cal["eligible_controls"]
    L += ["### Calibration", "",
          "- K = %d. Minimum K: %d." % (cal["K"], cal["minimum_K"]),
          "- Minimum K note: %s" % cal["minimum_K_note"],
          "- Share: %s. Threshold (right): %d. Right: %d."
          " Passed: %s. Valid: %s. State: %s."
          % (cal["share"], cal["threshold_right"],
             cal["C36_right"], cal["passed"],
             cal["valid"], cal["state"]), "",
          "| operation | witness | nodes | within limit"
          " | agrees on all 36 | agrees on the final panel"
          " | C-36 expr | C-36 verdict"
          " | smaller blocks expr | smaller blocks verdict"
          " | library only expr | library only search"
          " | library only verdict |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for op in sorted(elig):
        rec = recs[op]
        w = rec.get("witness", {})
        w_expr = expr_cell(w.get("expr"))
        w_n = w.get("nodes", w.get("declared_nodes", ""))
        within = yn(isinstance(w_n, int) and w_n <= size_c)
        a36 = yn(w.get("agrees_on_all_36", False))
        afp = yn(w.get("agrees_on_the_final_panel", False))
        c36 = rec["searches"]["C-36"]
        sel_sb = rec["selection"]["smaller_blocks"]
        sel_lo = rec["selection"]["library_only"]
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s"
                 " | %s | %s | %s | %s | %s |"
                 % (op, w_expr, w_n, within, a36, afp,
                    expr_cell(c36.get("expr")),
                    c36.get("first_fit", "none"),
                    expr_cell(sel_sb.get("expr")),
                    sel_verdict(sel_sb),
                    expr_cell(sel_lo.get("expr")),
                    sel_lo.get("search") or "",
                    sel_verdict(sel_lo)))
    L.append("")

    c36_cnt = sum(1 for op in cal["names"]
                  if recs[op]["searches"]["C-36"].get(
                      "first_fit") == "right")
    xc("calibration.C36_right", cal["C36_right"], c36_cnt)

    # witness vs C-36 expression for calibration names
    c36_match, c36_diff = 0, []
    sb_match, sb_diff = 0, []
    for op in sorted(cal["names"]):
        rec = recs[op]
        w_e = rec["witness"].get("expr")
        c36_e = rec["searches"]["C-36"].get("expr")
        sb_e = rec["selection"]["smaller_blocks"].get("expr")
        if c36_e == w_e:
            c36_match += 1
        else:
            c36_diff.append((op, c36_e, w_e))
        if sb_e == w_e:
            sb_match += 1
        else:
            sb_diff.append((op, sb_e, w_e))
    c36_str = ("all %d match" % c36_match if not c36_diff
               else "%d match, %d differ" % (c36_match, len(c36_diff)))
    sb_str = ("all %d match" % sb_match if not sb_diff
              else "%d match, %d differ" % (sb_match, len(sb_diff)))
    L.append("- Blocks-alone search (C-36) expression equals the"
             " witness expression for the %d calibration names:"
             " %s." % (len(cal["names"]), c36_str))
    for op, found, wit in c36_diff:
        L.append("  - `%s`: found %s, witness %s"
                 % (op, expr_cell(found), expr_cell(wit)))
    L.append("- Smaller-blocks selection expression equals the"
             " witness expression: %s." % sb_str)
    for op, found, wit in sb_diff:
        L.append("  - `%s`: selected %s, witness %s"
                 % (op, expr_cell(found), expr_cell(wit)))
    L.append("")

    # eligible controls without a witness within s
    over_s = cal.get(
        "eligible_controls_without_a_witness_within_s", {})
    if over_s:
        L.append("Eligible controls without a witness within the"
                 " size limit (%d):" % len(over_s))
        L.append("")
        for op in sorted(over_s):
            L.append("- `%s`: %s" % (op, over_s[op]))
        L.append("")

    # controls not eligible
    not_elig = cal.get("controls_not_eligible", [])
    if not_elig:
        L += ["Controls not eligible (%d):" % len(not_elig), ""]
        for op in sorted(not_elig):
            L.append("- `%s`: %s"
                     % (op, req(recs[op], "reason",
                                "%s.reason" % op)))
        L.append("")

    # ================================================================
    # Secondary comparisons
    # ================================================================
    blocks = [
        ("short", "Short stratum", sec["short_stratum"]),
        ("7_15", "Longer, 7 to 15 nodes", sec["longer_7_to_15"]),
        ("o15", "Longer, more than 15 nodes",
         sec["longer_over_15"]),
        ("all", "All strata outside development", oda),
        ("dev", "Development names (development only)", dev_blk)]

    def sec_coh(bk):
        if bk == "short":
            return {k: v for k, v in recs.items()
                    if v["status"] == "done"
                    and v["stratum"] == "short"
                    and not v.get("dev")}
        if bk == "7_15":
            return {k: v for k, v in recs.items()
                    if v["status"] == "done"
                    and v["stratum"] == "longer"
                    and v.get("half") == "7_to_15"
                    and not v.get("dev")}
        if bk == "o15":
            return {k: v for k, v in recs.items()
                    if v["status"] == "done"
                    and v["stratum"] == "longer"
                    and v.get("half") == "over_15"
                    and not v.get("dev")}
        if bk == "all":
            return nd_r
        return {k: v for k, v in recs.items()
                if v["status"] == "done" and v.get("dev")}

    L += ["### Secondary comparisons (descriptive, uncorrected)", "",
          "| block | N | library only right"
          " | smaller blocks right"
          " | both | smaller blocks only | library only only"
          " | neither | p"
          " | library only selected and wrong"
          " | smaller blocks selected and wrong |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for bk, bl, blk in blocks:
        p = blk["paired_smaller_blocks_against_library_only"]
        pr = paired_from_records(sec_coh(bk))
        xc("%s.N" % bk, p["N"], pr["N"])
        xc("%s.both" % bk, p["both"], len(pr["both"]))
        xc("%s.rebuilt.lo" % bk,
           p["rebuilt"]["library_only"], pr["library_only"])
        xc("%s.rebuilt.sb" % bk,
           p["rebuilt"]["smaller_blocks"], pr["smaller_blocks"])
        for cell in ("both", "smaller_blocks_only",
                     "library_only_only", "neither"):
            xc("%s.targets.%s" % (bk, cell),
               sorted(p["targets"][cell]), sorted(pr[cell]))
        lo_sw = nlist(blk["systems"]["library_only"].get(
            "selected_and_wrong", []))
        sb_sw = nlist(blk["systems"]["smaller_blocks"].get(
            "selected_and_wrong", []))
        L.append(
            "| %s | %d | %d | %d | %d | %d | %d | %d"
            " | %s | %s | %s |"
            % (bl, p["N"], pr["library_only"],
               pr["smaller_blocks"], len(pr["both"]),
               len(pr["smaller_blocks_only"]),
               len(pr["library_only_only"]),
               len(pr["neither"]),
               fmt_p(p["p_two_sided_sign_test"]),
               lo_sw, sb_sw))
    L.append("")

    for _, bl, blk in blocks:
        t = blk["paired_smaller_blocks_against_library_only"][
            "targets"]
        sb_o = sorted(t.get("smaller_blocks_only", []))
        lo_o = sorted(t.get("library_only_only", []))
        if sb_o or lo_o:
            L.append("- %s: smaller blocks only: %s."
                     " Library only only: %s."
                     % (bl, nlist(sb_o), nlist(lo_o)))
    L.append("")

    short_nc = {k: v for k, v in recs.items()
                if v["status"] == "done"
                and v["stratum"] == "short"
                and not v.get("dev") and not v.get("control")}
    if short_nc:
        L += ["Short operations outside development that are"
              " not controls (%d):" % len(short_nc), ""]
        for op in sorted(short_nc):
            lo = short_nc[op]["selection"]["library_only"]
            sb = short_nc[op]["selection"]["smaller_blocks"]
            lo_t = (expr_cell(lo["expr"])
                    + " (" + sel_verdict(lo) + ")"
                    if lo.get("expr") else "selected nothing")
            sb_t = (expr_cell(sb["expr"])
                    + " (" + sel_verdict(sb) + ")"
                    if sb.get("expr") else "selected nothing")
            L.append("- `%s`: library only: %s;"
                     " smaller blocks: %s." % (op, lo_t, sb_t))
        L.append("")

    # ================================================================
    # The six searches
    # ================================================================
    def search_table(title, cohort, sum_s, do_xc=True):
        out = [title, ""]
        all_sc = set(STOP_ORDER)
        for sn in SEARCHES:
            all_sc.update(search_agg(cohort, sn)["stops"])
        sc = [s for s in STOP_ORDER if s in all_sc]
        sc += sorted(all_sc - set(STOP_ORDER))
        out += [
            "| search | n | right | wrong | none | "
            + " | ".join(hum(s) for s in sc)
            + " | sum (s) | median (s)"
            " | largest (s) | largest operation |",
            "|" + "|".join(
                ["---"] * (5 + len(sc) + 4)) + "|"]
        for sn in SEARCHES:
            ag = search_agg(cohort, sn)
            if do_xc and sum_s and sn in sum_s:
                sff = sum_s[sn].get("first_fit", {})
                for fk in FITS:
                    xc("search.%s.first_fit.%s" % (sn, fk),
                       sff.get(fk, 0),
                       ag["fits"].get(fk, 0))
                sum_sc = sum_s[sn].get("stop_class", {})
                xc("search.%s.stop_class" % sn,
                   sum_sc, ag["stops"])
            row = ("| %s | %d | %d | %d | %d"
                   % (sn, ag["n"], ag["fits"]["right"],
                      ag["fits"]["wrong"],
                      ag["fits"]["none"]))
            for s in sc:
                row += " | %d" % ag["stops"].get(s, 0)
            row += (" | %s | %s | %s | `%s` |"
                    % (fmt_s(ag["sum"]),
                       fmt_s(ag["median"]),
                       fmt_s(ag["largest"]),
                       ag["largest_op"]))
            out.append(row)
        out.append("")
        return out

    L += ["### The six searches", ""]
    L += search_table(
        "Primary cohort (longer stratum outside development,"
        " N = %d):" % len(pcoh), pcoh,
        lo_sec.get("searches"))
    L += search_table(
        "All done records outside the development names"
        " (N = %d):" % len(nd_r), nd_r,
        oda.get("searches"))
    L += search_table(
        "All done records, development names included"
        " (N = %d):" % len(all_done), all_done, None,
        do_xc=False)
    L.append("Counted from the records; the summary has no block"
             " for this cohort.")
    L.append("")

    # global stats over all done records
    total_searches = len(all_done) * len(SEARCHES)
    g_stops = collections.Counter()
    g_fcap = 0
    g_best_bank = (0, "", "", 0)
    g_best_cpu = (0.0, "", "")
    found_any = 0
    found_none_ct = 0
    for op, rec in sorted(all_done.items()):
        has_found = False
        for sn in SEARCHES:
            s = rec["searches"][sn]
            g_stops[s.get("stop_class", "unknown")] += 1
            if s.get("function_cap_reached"):
                g_fcap += 1
            bk_val = s.get("bank", 0)
            if bk_val > g_best_bank[0]:
                g_best_bank = (bk_val, op, sn,
                               s.get("max_bank", 0))
            cpu = s.get("cpu_s", 0)
            if cpu > g_best_cpu[0]:
                g_best_cpu = (cpu, op, sn)
            if s.get("expr") is not None:
                has_found = True
        if has_found:
            found_any += 1
        else:
            found_none_ct += 1

    L += [
        "- Total searches over all %d done records: %d."
        % (len(all_done), total_searches),
        "- Stop classes: %s." % ", ".join(
            "%s %d" % (hum(k), g_stops[k])
            for k in (STOP_ORDER
                      + sorted(set(g_stops) - set(STOP_ORDER)))),
        "- Searches with function cap reached: %d." % g_fcap,
        "- Largest bank: %d (`%s`, %s) against a cap of %d."
        % g_best_bank,
        "- Largest search processor time: %s s (`%s`, %s)."
        % (fmt_s(g_best_cpu[0]), g_best_cpu[1], g_best_cpu[2]),
        "- Done records with at least one found expression"
        " in any search: %d. With none: %d."
        % (found_any, found_none_ct), ""]

    # ================================================================
    # Stages and candidate sets
    # ================================================================
    L += ["### Stages and candidate sets", ""]

    def stages_block(title, cohort, blk, tag):
        out = [title, ""]
        lc_l = blk["LC4_36_against_L4_36"]
        cnt = versus_from_records(cohort, "LC4-36", "L4-36")
        for k in ("both", "first_only", "second_only", "neither"):
            xc("%s.LC4_L4.%s" % (tag, k),
               lc_l["counts"][k], cnt[k])
        out.append("- LC4-36 against L4-36: both %d, LC4-36 only %d,"
                   " L4-36 only %d, neither %d."
                   % (cnt["both"], cnt["first_only"],
                      cnt["second_only"], cnt["neither"]))
        fo = sorted(lc_l["targets"].get("first_only", []))
        so = sorted(lc_l["targets"].get("second_only", []))
        if fo:
            out.append("  - LC4-36 only: %s." % nlist(fo))
        if so:
            out.append("  - L4-36 only: %s." % nlist(so))

        l5_l = blk["L5_36_against_L4_36"]
        cnt5 = versus_from_records(cohort, "L5-36", "L4-36")
        for k in ("both", "first_only", "second_only", "neither"):
            xc("%s.L5_L4.%s" % (tag, k),
               l5_l["counts"][k], cnt5[k])
        out.append("- L5-36 against L4-36: both %d, L5-36 only %d,"
                   " L4-36 only %d, neither %d."
                   % (cnt5["both"], cnt5["first_only"],
                      cnt5["second_only"], cnt5["neither"]))
        fo5 = sorted(l5_l["targets"].get("first_only", []))
        so5 = sorted(l5_l["targets"].get("second_only", []))
        if fo5:
            out.append("  - L5-36 only: %s." % nlist(fo5))
        if so5:
            out.append("  - L4-36 only: %s." % nlist(so5))

        bud = blk["L4_36_right_while_LC4_36_ended_by_its_budget"]
        out.append("- Operations where the four-node library search"
                   " is right and the search with blocks ended by"
                   " its budget without a right fit: %d%s."
                   % (bud["n"],
                      " (%s)" % nlist(bud["targets"])
                      if bud["targets"] else ""))

        for sk in SYSTEMS:
            sum_stages = blk["systems"][sk].get(
                "selected_by_stage", {})
            cnt_stages = {}
            for op, rec in sorted(cohort.items()):
                sel = rec["selection"][sk]
                if sel.get("expr") is not None:
                    st = str(sel.get("stage", "?"))
                    cnt_stages[st] = cnt_stages.get(st, 0) + 1
            sum_conv = {str(k): v
                        for k, v in sum_stages.items()}
            xc("%s.%s.selected_by_stage" % (tag, sk),
               sum_conv, cnt_stages)
            parts = ", ".join("stage %s: %d" % (k, v)
                              for k, v in sorted(
                                  cnt_stages.items()))
            out.append("- %s selected by stage: %s."
                       % (SYS_LABEL[sk].capitalize(),
                          parts if parts else "none"))

        for sk in SYSTEMS:
            cov = blk["systems"][sk][
                "candidate_set_coverage_oracle_union"
                "_NOT_the_systems_result"]
            out.append(
                "- %s candidate-set coverage (either of the"
                " system's two found expressions right on the"
                " final panel; this is not the system's"
                " result): %d." % (
                    SYS_LABEL[sk].capitalize(), cov))
        out.append("")
        return out

    L += stages_block(
        "Primary cohort (N = %d):" % len(pcoh),
        pcoh, lo_sec, "prim")
    L += stages_block(
        "All done records outside the development names"
        " (N = %d):" % len(nd_r), nd_r, oda, "all")

    # ================================================================
    # Order of sets
    # ================================================================
    L += ["### Order of sets", ""]
    oos_note = req(
        lo_sec["systems"]["library_only"]["order_of_sets"],
        "note", "order_of_sets.note")
    L += ["Note: %s" % oos_note, ""]
    for title, blk, tag in [
            ("Primary cohort:", lo_sec, "prim"),
            ("All done records outside the development names:",
             oda, "all")]:
        L += [title, ""]
        for sk in SYSTEMS:
            oos = blk["systems"][sk]["order_of_sets"]
            same = oos["inputs_with_the_same_order"]
            of = oos["of_inputs_with_at_least_two_elements"]
            L.append("%s: %d of %d inputs with the same order."
                     % (SYS_LABEL[sk].capitalize(), same, of))
            pt = oos.get("per_target", {})
            if pt:
                L += ["",
                      "| operation | same order | of |",
                      "|---|---|---|"]
                for pop in sorted(pt):
                    L.append("| %s | %d | %d |"
                             % (pop, pt[pop]["same_order"],
                                pt[pop]["of"]))
            L.append("")
        L.append("")

    # ================================================================
    # Sizes of found expressions
    # ================================================================
    L += ["### Sizes of found expressions", ""]
    size_range = range(1, 6)
    for title, cohort, sum_s, tag in [
            ("Primary cohort (N = %d):" % len(pcoh),
             pcoh, lo_sec.get("searches", {}), "prim"),
            ("All done records outside the development names"
             " (N = %d):" % len(nd_r),
             nd_r, oda.get("searches", {}), "all")]:
        L += [title, "",
              "| search | "
              + " | ".join(str(s) for s in size_range) + " |",
              "|---|" + "|".join(["---"] * len(size_range)) + "|"]
        for sn in SEARCHES:
            cnt = collections.Counter()
            for rec in cohort.values():
                s = rec["searches"][sn]
                if s.get("expr") is not None:
                    cnt[s.get("size", 0)] += 1
            if sn in sum_s:
                sum_sizes = sum_s[sn].get(
                    "sizes_of_found_expressions", {})
                sum_dict = {int(k): v
                            for k, v in sum_sizes.items()}
                rec_dict = {k: v for k, v in cnt.items()
                            if v > 0}
                xc("sizes.%s.%s" % (tag, sn),
                   sum_dict, rec_dict)
            row = "| %s" % sn
            for s in size_range:
                v = cnt.get(s, 0)
                row += " | %s" % (str(v) if v else "")
            L.append(row + " |")
        L.append("")

    # ================================================================
    # Costs
    # ================================================================
    L += ["### Costs", ""]
    cost_note = lo_sec["cpu"].get("note", "")
    if cost_note:
        L += ["Note: %s" % cost_note, ""]

    SYS_SEARCHES = {"library_only": ["L4-36", "L5-36"],
                     "smaller_blocks": ["LC4-36", "C-36"]}
    cost_blocks = [
        ("Longer stratum outside development", lo_sec,
         lambda r: r["stratum"] == "longer" and not r.get("dev")),
        ("Short stratum outside development",
         sec["short_stratum"],
         lambda r: r["stratum"] == "short" and not r.get("dev")),
        ("All strata outside development", oda,
         lambda r: not r.get("dev")),
        ("Development names (development only)", dev_blk,
         lambda r: r.get("dev"))]
    L += ["| block | listed | done | excluded at setup"
          " | searches (s) | final checks (s)"
          " | other (s) | targets total (s)"
          " | library only (s) | smaller blocks (s) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for bl, blk, filt in cost_blocks:
        cp = blk["cpu"]
        blk_recs = {k: v for k, v in recs.items() if filt(v)}
        blk_done = {k: v for k, v in blk_recs.items()
                    if v["status"] == "done"}
        blk_excl = {k: v for k, v in blk_recs.items()
                    if v["status"] == "excluded"}
        xc("costs.%s.n_records" % bl, blk["n_records"],
           len(blk_recs))
        xc("costs.%s.status" % bl, blk["status"],
           {"done": len(blk_done),
            "excluded": len(blk_excl)})
        # cross-check targets_total_s from records
        rec_total = sum(v["cpu_s_total"] for v in blk_recs.values())
        if abs(rec_total - cp["targets_total_s"]) > 0.06:
            die("cross-check failed: costs.%s.targets_total_s:"
                " summary %s, records %s"
                % (bl, cp["targets_total_s"], rec_total))
        # cross-check system cpu sums
        for sk in SYSTEMS:
            sys_sum = sum(
                blk_done[op]["searches"][sn]["cpu_s"]
                for op in blk_done for sn in SYS_SEARCHES[sk])
            sum_val = blk["systems"][sk]["cpu_s_sum"]
            if abs(sys_sum - sum_val) > 0.06:
                die("cross-check failed:"
                    " costs.%s.%s.cpu_s_sum:"
                    " summary %s, records %s"
                    % (bl, sk, sum_val, sys_sum))
        lo_cpu = blk["systems"]["library_only"]["cpu_s_sum"]
        sb_cpu = blk["systems"]["smaller_blocks"]["cpu_s_sum"]
        L.append(
            "| %s | %d | %d | %d"
            " | %s | %s | %s | %s | %s | %s |"
            % (bl, len(blk_recs), len(blk_done),
               len(blk_excl),
               fmt_s(cp["searches_s"]),
               fmt_s(cp["final_checks_s"]),
               fmt_s(cp["other_s"]),
               fmt_s(cp["targets_total_s"]),
               fmt_s(lo_cpu), fmt_s(sb_cpu)))
    L.append("")

    # first row's two parts for the note
    first_filt = cost_blocks[0][2]
    first_done_cpu = sum(
        v["cpu_s_total"] for v in recs.values()
        if first_filt(v) and v["status"] == "done")
    first_excl_cpu = sum(
        v["cpu_s_total"] for v in recs.values()
        if first_filt(v) and v["status"] == "excluded")
    L += [
        "- Each row covers every listed operation of its block,"
        " including those excluded at setup, whose setup time is"
        " in the total. For the first row: done records %s s,"
        " excluded records %s s."
        % (fmt_s(first_done_cpu), fmt_s(first_excl_cpu)),
        "- The two system columns are the sums of that system's"
        " two 36-example searches only (library only: L4-36 and"
        " L5-36; smaller blocks: LC4-36 and C-36), so the"
        " nine-example searches, the final checks and other work"
        " are not in them.", ""]

    wj = summ["costs_of_the_whole_job"]
    ftp = wj["from_this_process"]
    L += [
        "- Whole job (from the process): cpu_process_s %s,"
        " cpu_user_s %s, cpu_system_s %s, wall_s %s."
        % (fmt_s(ftp["cpu_process_s"]),
           fmt_s(ftp["cpu_user_s"]),
           fmt_s(ftp["cpu_system_s"]),
           fmt_s(ftp["wall_s"])),
        "- Whole job (from %s): user %s s, system %s s,"
        " wall clock %s." % (a.time, gnu["user_s"],
                              gnu["system_s"], gnu["wall"]),
        "- Setup of the pools: %s s. Targets: %s s."
        % (fmt_s(wj["setup_of_the_pools_cpu_s"]),
           fmt_s(wj["targets_cpu_s"])), ""]

    # ================================================================
    # Every selected expression
    # ================================================================
    sel_rows = []
    for op in sorted(all_done):
        rec = all_done[op]
        is_dev = rec.get("dev", False)
        strat = rec.get("stratum", "")
        role = ("control" if rec.get("control") else
                "development" if is_dev else "")
        for sk in SYSTEMS:
            sel = rec["selection"][sk]
            if sel.get("expr") is None:
                continue
            sn = sel["search"]
            fin = rec["searches"][sn].get("final") or {}
            gen = fin.get("generator", [])
            pool = fin.get("pooled", [])
            sel_rows.append((
                (is_dev, strat, op, sk),
                op, strat, role, SYS_LABEL[sk],
                sel["expr"], sel.get("size", ""), sn,
                "right" if sel.get("rebuilt") else "wrong",
                fin.get("agree", ""), fin.get("n", ""),
                ("%d of %d" % (gen[0], gen[1])
                 if len(gen) == 2 else ""),
                ("%d of %d" % (pool[0], pool[1])
                 if len(pool) == 2 else "")))
    sel_rows.sort(key=lambda r: r[0])

    L += ["### Every selected expression", "",
          "| operation | stratum | role | system | expression"
          " | nodes | search | verdict | agree of n"
          " | generator | pooled |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in sel_rows:
        (_, op, strat, role, slab, expr, nodes, sn,
         verdict, agree, n, g_s, p_s) = row
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s"
                 " | %s of %s | %s | %s |"
                 % (op, strat, role, slab, expr_cell(expr),
                    nodes, sn, verdict, agree, n, g_s, p_s))
    L.append("")

    # ================================================================
    # Selected and wrong
    # ================================================================
    wrong = [r for r in sel_rows if r[8] == "wrong"]
    by_op = collections.defaultdict(list)
    for r in wrong:
        by_op[r[1]].append(r)
    L += ["### Selected and wrong", "",
          "| operation | stratum | system | expression | nodes"
          " | search | agree of n | generator | pooled |",
          "|---|---|---|---|---|---|---|---|---|"]
    for op in sorted(by_op):
        rows = by_op[op]
        if len(rows) == 2 and rows[0][5] == rows[1][5]:
            syslab = ", ".join(r[4] for r in rows)
            searches = ", ".join(r[7] for r in rows)
            r = rows[0]
            L.append(
                "| %s | %s | %s | %s | %s | %s"
                " | %s of %s | %s | %s |"
                % (op, r[2], syslab, expr_cell(r[5]),
                   r[6], searches,
                   r[9], r[10], r[11], r[12]))
        else:
            for r in rows:
                L.append(
                    "| %s | %s | %s | %s | %s | %s"
                    " | %s of %s | %s | %s |"
                    % (r[1], r[2], r[4],
                       expr_cell(r[5]), r[6], r[7],
                       r[9], r[10], r[11], r[12]))
    L.append("")

    # ================================================================
    # Nine examples against 36
    # ================================================================
    def nine_block(title, cohort):
        out = [title, ""]
        for p9, p36 in [("L4-9", "L4-36"),
                         ("LC4-9", "LC4-36")]:
            tab = {(a, b): 0 for a in FITS for b in FITS}
            for rec in cohort.values():
                f9 = rec["searches"][p9].get(
                    "first_fit", "none")
                f36 = rec["searches"][p36].get(
                    "first_fit", "none")
                if f9 not in FITS:
                    f9 = "none"
                if f36 not in FITS:
                    f36 = "none"
                tab[(f9, f36)] += 1
            N = len(cohort)
            out += ["%s against %s:" % (p9, p36), "",
                    "| %s \\ %s | right | wrong | none"
                    " | total |" % (p9, p36),
                    "|---|---|---|---|---|"]
            for a in FITS:
                rt = sum(tab[(a, b)] for b in FITS)
                out.append("| %s | %d | %d | %d | %d |" % (
                    a, tab[(a, "right")],
                    tab[(a, "wrong")], tab[(a, "none")], rt))
            ct = [sum(tab[(a, b)] for a in FITS) for b in FITS]
            out.append("| total | %d | %d | %d | %d |"
                       % (ct[0], ct[1], ct[2], N))
            out.append("")
        wrong_9 = []
        for p9, p36 in [("L4-9", "L4-36"),
                         ("LC4-9", "LC4-36")]:
            for op in sorted(cohort):
                s9 = cohort[op]["searches"][p9]
                s36 = cohort[op]["searches"][p36]
                if s9.get("first_fit") == "wrong":
                    wrong_9.append((
                        p9, op, expr_cell(s9.get("expr")),
                        s36.get("first_fit", "none"),
                        expr_cell(s36.get("expr"))))
        if wrong_9:
            out += ["Operations whose nine-example first fit"
                    " was wrong:", ""]
            for p9, op, e9, ff36, e36 in wrong_9:
                out.append(
                    "- `%s` %s: %s; %s: %s%s"
                    % (op, p9, e9,
                       p9.replace("-9", "-36"), ff36,
                       " %s" % e36 if e36 else ""))
            out.append("")
        return out

    L += ["### Nine examples against 36", ""]
    L += nine_block(
        "Primary cohort (N = %d):" % len(pcoh), pcoh)
    L += nine_block(
        "All done records outside development (N = %d):"
        % len(nd_r), nd_r)

    # ================================================================
    # Comparison with the earlier study
    # ================================================================
    ec = earlier["counts"]
    total = sum(ec.values())
    largest_cat = max(ec, key=lambda k: ec[k])
    by_cat = earlier.get("by_category", {})
    L += ["### Comparison with the earlier study", "",
          "Total: %d." % total, "",
          "| category | count |", "|---|---|"]
    for cat in sorted(ec):
        L.append("| %s | %d |" % (cat, ec[cat]))
    L.append("")
    for cat in sorted(by_cat):
        if cat == largest_cat:
            L.append("- %s: %d (names not listed)."
                     % (cat, ec[cat]))
        else:
            L.append("- %s (%d): %s."
                     % (cat, ec[cat], nlist(by_cat[cat])))
    L.append("")

    # ================================================================
    # Write
    # ================================================================
    try:
        with open(a.out, "x") as f:
            f.write("\n".join(L) + "\n")
    except FileExistsError:
        die("output file already exists, refusing to"
            " overwrite: %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
