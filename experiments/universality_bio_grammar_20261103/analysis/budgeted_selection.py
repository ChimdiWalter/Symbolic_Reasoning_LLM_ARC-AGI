"""U5 budgeted-selection analysis on LIVECell calibration (exploratory, post hoc, calibration only; outside the decision
path). For a budget of k candidate operators, compares CORA's failure-evidence order (the specification order recorded
before admission) with random orders: the probability that the admitted operator is within the first k, the expected
validation F1 change, and the CPU saved. It reads only the two induction records; no evaluation data.

    python -I analysis/budgeted_selection.py
"""
import json
import os
import sys
import time

import numpy as np

E = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(E, "scripts"))
import u5core as C    # noqa: E402

W = "/path/to/bio_data/work"
LABEL = "exploratory, post hoc, calibration only"
KS = (1, 2, 3)


def contexts(d):
    """op -> {admitted-before set: [(admitted, validation F1 change)]} over CORA's run and the ten controls."""
    out = {}
    runs = [d["CORA"]] + list(d["FAILURE_BLIND"].values()) + list(d["SHUFFLED"].values())
    for v in runs:
        adm = []
        for r in v["trail"]:
            if "op" not in r:
                continue
            out.setdefault(r["op"], {}).setdefault(tuple(sorted(adm)), set()).add(
                (bool(r["admitted"]), round(r["val_f1_with"] - r["val_f1_without"], 9)))
            if r["admitted"]:
                adm.append(r["op"])
    return out


def outcome(order, k, ctx):
    """Greedy admission over the first k operators of `order`, read from the recorded outcomes; None if a context
    was never observed (then the outcome is not determined by the records)."""
    adm, df1 = [], 0.0
    for op in order[:k]:
        obs = ctx.get(op, {}).get(tuple(sorted(adm)))
        if not obs or len(obs) != 1:
            return None
        a, g = next(iter(obs))
        if a:
            adm.append(op)
            df1 += g
    return adm, df1


def analyse(rule, name):
    d = json.load(open(os.path.join(W, "livecell", name)))
    ctx = contexts(d)
    spec = d["CORA"]["specified"]
    trail_w = [r for r in d["CORA"]["trail"] if "work" in r][0]["work"]
    cpu10 = trail_w.get("cpu_s_exact", trail_w["cpu_s"])
    n_val = trail_w["candidate_validations"]
    rng = np.random.default_rng(0)
    samples = [list(np.array(C.OPS)[rng.permutation(len(C.OPS))]) for _ in range(10000)]
    rng10 = np.random.default_rng(1)
    samples10 = [list(np.array(spec)[rng10.permutation(len(spec))]) for _ in range(10000)]
    target = d["CORA"]["admitted"]
    res = {"rule": rule, "record": name, "cora_order": spec,
           "failure_evidence": {"class_oracle_gain": d["CORA"]["oracle_gains"],
                                "not_found_within_budget": {c: v.get("not_found_within_budget")
                                                            for c, v in d["CORA"]["failure_records"].items()}},
           "admitted_with_full_ceiling": target, "measured_admission_cpu_s_for_10_candidates": cpu10,
           "candidate_validations_recorded": n_val, "budgets": {}}
    for k in KS:
        co = outcome(spec, k, ctx)
        r = {"cora_order_first_k": spec[:k], "cora_order_admits": co[0] if co else None,
             "cora_order_validation_f1_change": co[1] if co else None}
        for tag, ss, n_ops in (("random_all_11_operators", samples, len(C.OPS)),
                               ("random_10_specified_operators", samples10, len(spec))):
            outs = [outcome(o, k, ctx) for o in ss]
            und = sum(o is None for o in outs)
            got = [o for o in outs if o is not None]
            hit = [bool(target) and all(t in o[0] for t in target) for o in got]
            r[tag] = {"p_admitted_operator_within_k_exact": (k / n_ops) if target else 0.0,
                      "p_admitted_operator_within_k_sampled": float(np.mean(hit)) if got else None,
                      "expected_validation_f1_change": float(np.mean([o[1] for o in got])) if got else None,
                      "orders_sampled": len(ss), "orders_not_determined_by_records": und}
        r["cpu_estimate"] = {"candidates_validated": k, "estimated_cpu_s": cpu10 * k / n_val,
                             "estimated_cpu_saved_s": cpu10 * (n_val - k) / n_val,
                             "basis": "equal cost per candidate; per-candidate CPU was not recorded, and the first "
                                      "candidates of a run pay for unit tables later reused, so the saving is an upper "
                                      "estimate"}
        res["budgets"][str(k)] = r
    if target:
        rank = spec.index(target[0]) + 1
        res["rank_of_admitted_operator"] = {"cora_order": rank,
                                            "p_random_11_at_least_as_early": rank / len(C.OPS),
                                            "p_random_10_specified_at_least_as_early": rank / len(spec),
                                            "expected_rank_random_11": (len(C.OPS) + 1) / 2}
    res["determinism"] = ("every operator's recorded outcome in every reachable admission context is unique, so each "
                          "order's result is read from the records without re-running")
    return res


def main():
    out = {"label": LABEL, "dataset": "livecell (calibration parents only)",
           "computed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "rules": {"strict": analyse("strict", "INDUCTION.json"),
                     "tolerant": analyse("tolerant", "INDUCTION_TOLERANT.json")}}
    json.dump(out, open(os.path.join(W, "BUDGETED_SELECTION_livecell.json"), "w"), indent=1)
    json.dump(out, open(os.path.join(E, "analysis", "BUDGETED_SELECTION_livecell.json"), "w"), indent=1)
    L = [f"# Budgeted operator selection on LIVECell ({LABEL})", "",
         "CORA's failure-evidence order (the specification order recorded before admission) against random orders. "
         "Outcomes are read from the recorded admission trails (CORA and the ten controls); every reachable context "
         "was observed, so no run was repeated. No evaluation data were used.", ""]
    for rule, r in out["rules"].items():
        L += [f"## {rule} rule", "", f"CORA's order: {', '.join(r['cora_order'])}. Admitted with the full ceiling: "
              f"{r['admitted_with_full_ceiling'] or 'none'}.", "",
              "| budget k | CORA order admits | CORA ΔF1 (validation) | P(admitted op within k), random 11 | "
              "expected ΔF1, random 11 | P within k, random 10 specified | estimated CPU saved (s) |",
              "|---|---|---|---|---|---|---|"]
        for k, b in r["budgets"].items():
            a, b10 = b["random_all_11_operators"], b["random_10_specified_operators"]
            L.append(f"| {k} | {', '.join(b['cora_order_admits']) or 'none'} | {b['cora_order_validation_f1_change']:+.6f} | "
                     f"{a['p_admitted_operator_within_k_exact']:.3f} (sampled {a['p_admitted_operator_within_k_sampled']:.3f}) | "
                     f"{a['expected_validation_f1_change']:+.6f} | {b10['p_admitted_operator_within_k_exact']:.3f} | "
                     f"{b['cpu_estimate']['estimated_cpu_saved_s']:.0f} of {r['measured_admission_cpu_s_for_10_candidates']:.0f} |")
        if "rank_of_admitted_operator" in r:
            q = r["rank_of_admitted_operator"]
            L += ["", f"The admitted operator is rank {q['cora_order']} in CORA's order; a random order of the 11 "
                      f"operators ranks it at least as early with probability {q['p_random_11_at_least_as_early']:.3f} "
                      f"(expected rank {q['expected_rank_random_11']:.0f})."]
        L.append("")
    L += ["CPU saved is an estimate at equal cost per candidate; per-candidate CPU was not recorded, and early candidates "
          "pay for unit tables that later ones reuse, so the saving is an upper estimate.", ""]
    open(os.path.join(E, "analysis", "BUDGETED_SELECTION_livecell.md"), "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
