"""Pre-registered descriptive analyses of the ncv2-g2 real-ARC check, as
records/NEURAL_CORA_V2G2_REALARC_PREREG_ADDENDUM_20261020.md section 2 specifies. They run on the evaluator side,
only after `scripts/neural_cora_v2g2_realarc_eval.py score`, and never change the frozen decision.

    python scripts/neural_cora_v2g2_realarc_analysis.py   -> outputs/neural_cora_v2g2/realarc/analysis.json
"""
import glob
import json
import os
import sys
from math import comb

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "neural_cora_v2g2", "realarc")
CERTS = os.path.join(HERE, "outputs", "funnel_v0", "engine_realarc2x_native", "certificates")


def sign_p(k, n):
    return sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1.0


def form_of(src):
    """The program form behind a recorded ncv2-g2 S-expression."""
    from cora_neural_v2g2 import grammar as G
    p = G.parse(src)
    if p.op == "program":
        acts = sorted({(r.args[2] if r.op == "rule_with" else r.args[1]).op for r in p.args[1]})
        return {"form": "object program", "n_rules": len(p.args[1]), "actions": acts, "render": p.args[3].op}
    if p.op == "generative":
        return {"form": "generative", "kinds": sorted({g.args[1].args[0] for g in p.args[1]})}
    return {"form": p.op, "mode": p.args[0] if p.args and isinstance(p.args[0], str) else None}


def main(out_dir=OUT, certs_dir=CERTS, task_map=None):
    from cora_neural_v2g2 import grammar as G
    from cora_neural_v2g2 import search as S2
    from cora_neural_v2.rast import ASTError
    S = json.load(open(os.path.join(out_dir, "score.json")))
    if "decision" not in S["summary"]:
        sys.exit("run only after the frozen score stage")
    rows = {json.loads(l)["task_id"]: json.loads(l) for l in open(os.path.join(out_dir, "rows_g.jsonl"))}
    if task_map is None:                                            # the frozen cohort (demonstrations and test inputs only)
        import importlib.util
        spec = importlib.util.spec_from_file_location("ra", os.path.join(HERE, "scripts", "neural_cora_v2g2_realarc_eval.py"))
        RA = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(RA)
        task_map = {t["task_id"]: t for t in RA.tasks()}
    tasks = task_map
    per = []
    for rec in S["tasks"]:
        t = rec["task_id"]
        a = {"task_id": t, "stratum": rec["stratum"], "n_test": rec["n_test"]}
        a["correct_form"] = form_of(rec["g2"]["correct_program"]) if rec["g2"]["pass@2"] and rec["g2"].get("correct_program") else None
        cert_path = os.path.join(certs_dir, f"{t}.json")
        if os.path.exists(cert_path):
            d = json.load(open(cert_path))["program"]
            try:
                ast = G.decompile(d)
                a["expressivity"] = "expressible"
                task = {"task_id": t, "train": tasks[t]["train"], "test_inputs": tasks[t]["test_inputs"]}
                if G.is_class(ast):
                    cands, _ = S2.class_candidates(task)
                    a["generator_coverage"] = ast in cands
                else:
                    ev = S2.evidence2(task["train"])
                    rules = {repr(S2.rule_node(s, x)) for s, _, _ in S2.selectors(ev) for x, _, _ in S2.actions(ev, task["train"])}
                    a["generator_coverage"] = all(repr(r) in rules for r in ast.args[1])
            except ASTError as e:
                a["expressivity"], a["language_gap"] = "not expressible", str(e)[:160]
        else:
            a["expressivity"] = "unknown (no native certificate)"
        g2 = rec["g2"]
        a["reach"] = {"fits": g2["fits"], "first_fit_at": g2.get("first_fit_at")}
        a["selection"] = {"correct_retained_not_attempted": g2["correct_coverage"] and not g2["pass@2"], "wrong_attempts": g2["wrong_attempts"]}
        a["correct"] = {"g1": rec["g1"]["pass@2"], "g2": g2["pass@2"], "native_first": rec.get("native", {}).get("certified_correct_first")}
        if rec["n_test"] > 1:
            a["native_all_outputs_correct"] = rec.get("native", {}).get("certified_correct_all")
        per.append(a)
    res = {}
    for stratum in ("primary", "leftover"):
        P = [x for x in per if x["stratum"] == stratum]
        gains = sum(x["correct"]["g2"] and not x["correct"]["g1"] for x in P)
        losses = sum(x["correct"]["g1"] and not x["correct"]["g2"] for x in P)
        forms = {}
        for x in P:
            if x["correct_form"]:
                forms[x["correct_form"]["form"]] = forms.get(x["correct_form"]["form"], 0) + 1
        res[stratum] = {"n": len(P), "sign_test_one_sided_p_g2_vs_g1": round(sign_p(gains, gains + losses), 4),
                        "correct_forms_g2": forms,
                        "expressivity": {k: sum(x["expressivity"] == k for x in P) for k in ("expressible", "not expressible", "unknown (no native certificate)")},
                        "generator_covers_expressible_certificate": sum(bool(x.get("generator_coverage")) for x in P),
                        "g2_fits": sum(x["reach"]["fits"] for x in P),
                        "selection_misses": sum(x["selection"]["correct_retained_not_attempted"] for x in P),
                        "g2_wrong_attempts": sum(x["selection"]["wrong_attempts"] for x in P),
                        "g2_vs_native_first": {"g2_only": sum(bool(x["correct"]["g2"]) and not x["correct"]["native_first"] for x in P),
                                               "native_only": sum(bool(x["correct"]["native_first"]) and not x["correct"]["g2"] for x in P)},
                        "multi_test_tasks": [x["task_id"] for x in P if x["n_test"] > 1]}
    json.dump({"note": "pre-registered descriptive analyses; cannot change the frozen decision", "summary": res, "tasks": per},
              open(os.path.join(out_dir, "analysis.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
