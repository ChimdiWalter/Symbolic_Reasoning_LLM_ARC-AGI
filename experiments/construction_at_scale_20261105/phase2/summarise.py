"""Phase 2: print the numbers the report quotes (read only; standard library).

    python3 -I phase2/summarise.py

Reads runs/analysis/ (the frozen analysis's output), runs/analysis_addendum_1/ (the addendum recomputation),
runs/generated/BUILD_SUMMARY.json, each world's runs/STAGES.json and runs/kaggle/PLACEMENT_<W>.json.
"""
import json
import os

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(*p):
    try:
        with open(os.path.join(STUDY, *p), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    out = {}
    out["build"] = load("runs", "generated", "BUILD_SUMMARY.json")
    cfg = load("config", "STUDY_CONFIG.json") or {}
    out["placement"] = {w: {k: (load("runs", "kaggle", f"PLACEMENT_{w}.json") or {}).get(k)
                            for k in ("custody_ok", "outputs_verified", "archive_sha256", "kernel_status",
                                      "manifest_entries", "problems", "output_problems", "cpu_scale")}
                        for w in cfg.get("world_order", [])}
    out["stages"] = {}
    for w in cfg.get("world_order", []):
        st = load("runs", "generated", w, "runs", "STAGES.json") or {}
        out["stages"][w] = {"status": st.get("status"), "cpu_scale": st.get("cpu_scale"),
                            "stages": {k: (v.get("status"), v.get("cpu_s"), v.get("wall_s"))
                                       for k, v in (st.get("stages") or {}).items()},
                            "cpu_h": round(sum(v.get("cpu_s", 0) for v in (st.get("stages") or {}).values()) / 3600, 2),
                            "wall_h": round(sum(v.get("wall_s", 0) for v in (st.get("stages") or {}).values()) / 3600, 2),
                            "bench_end_median_cpu_s": st.get("bench_end_median_cpu_s")}
    inc = load("runs", "analysis", "INCOMPLETE.json")
    an = load("runs", "analysis", "ANALYSIS.json")
    out["frozen_analysis"] = inc if inc else ("ANALYSIS.json written" if an else None)
    rec = load("runs", "analysis_addendum_1", "ADDENDUM_1_RECOMPUTATION.json") or {}
    out["addendum"] = {k: rec.get(k) for k in ("binding_checked", "script_sha256", "outcome", "frozen_analysis_output",
                                               "committed_predictions_out_of_range",
                                               "endpoints_changed_by_the_colour_rule", "failure_status_disagreements",
                                               "results_failure_flag_mismatches",
                                               "searches_the_kernel_log_does_not_decide",
                                               "primary_without_failed_matched_searches", "c7m_failures",
                                               "matched_searches_on_cpu_cap_above_90pct_of_memory_limit")}
    rep = load("runs", "analysis_addendum_1", "ANALYSIS.json") or an
    if rep:
        p = rep["primary"]
        out["primary"] = {k: p.get(k) for k in ("decision", "units", "both", "only_S-hole", "only_C7m", "neither",
                                                "mean_diff", "mcnemar_p_conditional", "dependence_aware_ci95",
                                                "unit_ci95", "clusters", "family_ci95_11_families",
                                                "source_clustered_ci95", "joint_components",
                                                "joint_source_family_ci95", "denominator")}
        out["per_world"] = {w: v and {k: v.get(k) for k in ("units", "only_S-hole", "only_C7m", "mcnemar_p_conditional",
                                                            "dependence_aware_ci95")} for w, v in p["per_world"].items()}
        out["leave_one_world_out"] = {w: v and {k: v.get(k) for k in ("units", "only_S-hole", "only_C7m",
                                                                      "mcnemar_p_conditional", "dependence_aware_ci95")}
                                      for w, v in p["leave_one_world_out"].items()}
        out["secondary"] = {k: v and {kk: v.get(kk) for kk in ("units", "only_S-hole", "only_C7m", "mcnemar_p_conditional",
                                                               "holm_p", "dependence_aware_ci95", "holds")}
                            for k, v in rep["secondary"].items()}
        d = rep["descriptive"]
        out["descriptive"] = {"counts": d["counts"], "by_world": d["by_world"],
                              "oracle_reach_counts": d["oracle_reach_counts"],
                              "oracle_reach_excluded": d["oracle_reach_excluded"],
                              "not_applicable_units": len(d["not_applicable_units"]),
                              "sources_shared_between_tasks": d["sources_shared_between_tasks"],
                              "excluded_sources_shared_between_worlds": d["excluded_sources_shared_between_worlds"],
                              "c7m_failures_from_results": d["c7m_failures"],
                              "descriptive_contrasts": {k: v and {kk: v.get(kk) for kk in (
                                  "units", "only_" + k.split(" ")[0], "mcnemar_p_conditional",
                                  "dependence_aware_ci95")} for k, v in d["descriptive_contrasts"].items()}}
    print(json.dumps(out, indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
