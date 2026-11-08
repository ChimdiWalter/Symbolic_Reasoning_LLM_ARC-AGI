"""Power and the honest expectation, from the phase 1 feasibility numbers (source halves only).

    python -I run.py power FEASIBILITY_JSON GROW_DIR OUT_JSON

Expected held-half quantities are the source-half counts scaled by (held tasks / source tasks) per benchmark:
- primary population size: localisable G0 failures;
- growth's gains over G0: zero when the growth-from-holes registry is empty (its grammar is then G0); otherwise the
  in-sample reuse of the registry on source failures (motivating and validating tasks excluded) is the estimate;
- matched static search's gains over G0 on the primary population: the deeper-search probe's correct answers on
  localisable source failures (4x the base budget; the matched allowance is estimated below, and a larger allowance
  can only add answers);
- matched static allowance T_static from the measured controller CPU, the construction CPU and the base-search CPU.
Power: Poisson draws of the two discordant counts, the pre-registered exact test (analysis.power_sim).
"""
import json
import os
import sys

from ngrow import env as E, data as DT, analysis as AN


def main(feas_path, grow_dir, out_path):
    fe = E.load(feas_path)
    sp = DT.split()
    out = {"benchmarks": {}, "pooled": {}}
    lam_g = lam_s = prim = 0.0
    tot_cpu = tot_held = 0.0
    for b in DT.BENCHMARKS:
        s = fe["benchmarks"][b]["summary"]
        rows = fe["benchmarks"][b]["tasks"]
        n_src, n_held = sp["benchmarks"][b]["n_source"], sp["benchmarks"][b]["n_held"]
        f = n_held / n_src
        loc = [t for t, r in rows.items() if not r["base_fit"] and r["localises"]]
        static_gain_src = sum(rows[t]["x4_correct"] > 0 for t in loc)
        static_gain_out = sum(rows[t]["x4_correct"] for t in loc)
        reg = E.load(os.path.join(grow_dir, b, "registry.json"))["arms"]
        hole_reg = reg.get("S-hole", {}).get("registry") or []
        enum_reg = reg.get("S-enum", {}).get("registry") or []
        base_cpu = s["base_cpu_per_task"]["mean"]
        ctrl_cpu = s["controller_cpu_per_task"]["total"]
        constr = reg.get("S-hole", {}).get("construction_cpu_s") or 0.0
        t_static = (ctrl_cpu + constr + base_cpu * n_held) / n_held
        tot_cpu += ctrl_cpu + constr + base_cpu * n_held
        tot_held += n_held
        g_gain = 0.0 if not hole_reg else None
        out["benchmarks"][b] = {
            "source_tasks": n_src, "held_tasks": n_held, "scale": round(f, 4),
            "source_localisable_failures": len(loc), "expected_primary_held": round(len(loc) * f, 1),
            "source_localisable_solved_by_4x_probe_tasks": static_gain_src,
            "source_localisable_solved_by_4x_probe_outputs": static_gain_out,
            "expected_static_only_tasks_held": round(static_gain_src * f, 2),
            "growth_from_holes_registry": hole_reg, "blind_enumeration_registry_sample": enum_reg,
            "expected_growth_only_tasks_held": g_gain,
            "estimated_t_static_cpu_s": round(t_static, 2),
            "estimated_t_static_over_base_cpu": round(t_static / base_cpu, 2)}
        prim += len(loc) * f
        lam_s += static_gain_src * f
        lam_g += 0.0 if g_gain is None else g_gain
    out["pooled"] = {
        "expected_primary_held": round(prim, 1), "lambda_growth_only": round(lam_g, 2),
        "lambda_static_only": round(lam_s, 2),
        "min_discordant_tasks_for_p_below_0.05": AN.min_discordant_for_significance(),
        "power_growth_beats_static": AN.power_sim(lam_g, lam_s) if lam_g > 0 else 0.0,
        "power_static_beats_growth": AN.power_sim(lam_s, lam_g),
        "pooled_t_static_cpu_s": round(tot_cpu / tot_held, 2),
        "reference_effects": {f"growth_only_{k}": AN.power_sim(k, lam_s) for k in (3, 6, 10, 20)}}
    E.dump(os.path.abspath(out_path), out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
