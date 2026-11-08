"""Prediction-free export of the worked example td0c3d452 (world W3) from the construction-at-scale run's own records.

    python3 -I exports/extract_worked_example_td0c3d452.py      (from the study folder or anywhere)

Writes exports/WORKED_EXAMPLE_td0c3d452.json (process fields, each section with its source paths and sha256) and
exports/WORKED_EXAMPLE_td0c3d452_DEMOS.json (the demonstration pairs only: no query input, no other task, no answer).
The two pickles are this run's own files, read with an unpickler that accepts built-in types only. Predictions
(`preds`), structure parameters (`thetas`) and the controller's residual grid are left out. A field missing from the
records is written "not recorded"; nothing is filled in from the implementation's policy. No GO file, *_LOCAL.json
or private/ path is read.
"""
import hashlib
import json
import os
import pickle

ST = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "experiments/construction_at_scale_20261105"
W = "W3"
T = "td0c3d452"
RUN = f"runs/generated/{W}/runs"
FILES = {
    "system": f"runs/generated/{W}/partitions/TASKS_SYSTEM.json",
    "controller_record": f"{RUN}/prep_v4/records.pkl",
    "controller_summary": f"{RUN}/prep_v4/controller_summary.json",
    "hole_units": f"{RUN}/cas_arms/units_spec.json",
    "hole_gates": f"{RUN}/cas_arms/gates_spec.pkl",
    "enum_units_s0": f"{RUN}/cas_arms/units_enum_s0.json",
    "enum_units_s1": f"{RUN}/cas_arms/units_enum_s1.json",
    "enum_units_s2": f"{RUN}/cas_arms/units_enum_s2.json",
    "matched_static": f"{RUN}/cas_c7m/c7m_M.json",
    "evaluation": f"{RUN}/cas_eval/world_results.json",
    "analysis": "runs/analysis/ANALYSIS.json",
}
ARMS = {"S-hole": "the task's own typed holes", "S-demo": "the raw demonstrations as the hole",
        "S-enum": "blind trial of the 211 structures", "S-shuffled": "another task's holes (shuffled specification)",
        "C7m": "matched static search"}
SAFE = {("builtins", n) for n in ("dict", "list", "tuple", "set", "frozenset", "str", "int", "float", "bool", "bytes")}


class Restricted(pickle.Unpickler):
    def find_class(self, mod, name):
        if (mod, name) in SAFE:
            return super().find_class(mod, name)
        raise pickle.UnpicklingError(f"refused {mod}.{name}")


def path(k):
    return os.path.join(ST, FILES[k])


def src(*keys):
    return [{"path": f"{REL}/{FILES[k]}", "sha256": hashlib.sha256(open(path(k), "rb").read()).hexdigest()}
            for k in keys]


def load(k):
    if FILES[k].endswith(".pkl"):
        return Restricted(open(path(k), "rb")).load()
    return json.load(open(path(k)))


def size(g):
    return f"{len(g)}x{len(g[0]) if g else 0}"


def tree(t):
    """A recorded program tree as text (names only)."""
    if isinstance(t, (list, tuple)):
        head = str(t[0]).split(":", 1)[-1]
        return head if len(t) == 1 else f"{head}({', '.join(tree(x) for x in t[1:])})"
    return str(t)


def vmirror(g):
    return [list(r)[::-1] for r in g]


def as_lists(g):
    return [list(r) for r in g]


system = load("system")[T]
rec = load("controller_record")[T]
summ = load("controller_summary")[T]
units = load("hole_units")
gates = load("hole_gates")
enum = {s: load(f"enum_units_s{s}") for s in (0, 1, 2)}
c7m = load("matched_static")[T]
ev = load("evaluation")
unit_ev = next(u for u in ev["units"] if u.get("task") == T)
an_task = next(x for x in load("analysis")["tasks"] if x.get("task") == T)

# demonstrations only
demos = [{"input": as_lists(a), "output": as_lists(b)} for a, b in system["train"]]
with open(os.path.join(ST, "exports", f"WORKED_EXAMPLE_{T}_DEMOS.json"), "w", encoding="utf-8") as f:
    json.dump({"task": T, "world": W, "content": "demonstration pairs only (no query input, no other task, no answer)",
               "source": src("system"), "demonstrations": demos}, f, indent=1)
    f.write("\n")

# per-arm outcomes on each seed
keep = ("promoted", "committed_kind", "committed_structure", "recovered", "reach", "retries", "n_candidates",
        "structures_tried", "charged_total_cpu_s")
arms = {}
for s in ("0", "1", "2"):
    per = {a: {k: unit_ev["seeds"][s][a].get(k, "not recorded") for k in keep} for a in ("S-hole", "S-demo", "S-enum",
                                                                                          "S-shuffled")}
    sh = units[f"S-shuffled|{T}|{s}"]
    per["S-shuffled"]["donor"] = sh.get("donor", "not recorded")
    eu = enum[int(s)][f"S-enum|{T}|{s}"]
    per["S-enum"]["enum_cap_cpu_s"] = eu.get("enum_cap_cpu_s", "not recorded")
    per["S-enum"]["rows_recorded"] = len(eu.get("rows", []))
    per["S-demo"]["rows_recorded"] = len(units[f"S-demo|{T}|{s}"]["rows"])
    arms[s] = per
static = {k: c7m[k] for k in ("fit", "program", "level_complete", "stop", "calls", "cpu_s", "budget_cpu_s",
                              "budget_reference_cpu_s", "closure_capped")}
static["recovered"] = unit_ev["C7m"]["recovered"]
summary = {a: an_task.get(a, "not recorded") for a in ("S-hole", "S-demo", "S-enum", "S-shuffled", "C7m")}

# the typed hole that succeeded
rows = {s: units[f"S-hole|{T}|{s}"]["rows"] for s in ("0", "1", "2")}
r0 = rows["0"][0]
sk = rec["sketches"]
chosen = sk[r0["sketch_rank"]]
mirrored_in = all(as_lists(p[0]) == vmirror(d["input"]) for p, d in zip(chosen["pairs"], demos))
same_out = all(as_lists(p[1]) == d["output"] for p, d in zip(chosen["pairs"], demos))
sid = r0["sid"]
row_fields = ("sid", "sketch_rank", "sketch_form", "duplicate", "fit", "program", "promotion", "validation",
              "regression", "outcome")
hole = {
    "source": src("controller_record", "hole_units", "hole_gates", "system"),
    "ranked_sketches": [{"rank": i, "form": s["form"], "outer": s["outer"], "inner": s["inner"], "score": s["score"],
                         "pairs": len(s["pairs"])} for i, s in enumerate(sk)],
    "succeeded": {"sketch_rank": r0["sketch_rank"], "sketch_form": r0["sketch_form"], "inner": chosen["inner"],
                  "outer": chosen["outer"],
                  "same_on_all_three_seeds": len({(rows[s][0]["sketch_rank"], rows[s][0]["sid"]) for s in rows}) == 1},
    "required_of_the_missing_operation": {
        "pairs": len(chosen["pairs"]),
        "pair_sizes_input_to_output": [f"{size(a)} -> {size(b)}" for a, b in chosen["pairs"]],
        "recorded_pair_inputs_equal_the_mirrored_demonstration_inputs": mirrored_in,
        "recorded_pair_outputs_equal_the_demonstration_outputs": same_out},
    "slot_type": "not recorded",
    "candidates_from_hole_specification": units[f"S-hole|{T}|0"]["n_candidates"],
    "admitted": sid,
    "rows_by_seed": {s: [{k: r.get(k, "not recorded") for k in row_fields} for r in rows[s]] for s in rows},
    "gate_novelty_record": {k: gates["nov"].get(sid, {}).get(k, "not recorded") for k in ("duplicate", "witnesses",
                                                                                         "cpu_s")},
    "gate_regression_record": {k: gates["reg"].get(sid, {}).get(k, "not recorded") for k in ("lost_fit",
                                                                                            "changed_prediction",
                                                                                            "checked", "cpu_s")},
}
raw = {"source": src("hole_units", "evaluation"),
       "recorded": {s: {"n_candidates": arms[s]["S-demo"]["n_candidates"], "retries": arms[s]["S-demo"]["retries"],
                        "rows_recorded": arms[s]["S-demo"]["rows_recorded"]} for s in arms},
       "reason": "not recorded beyond these fields: no candidate structure passed the raw-demonstration "
                 "specification, so nothing reached the gates"}
doc = {
    "task": T, "world": W,
    "content_rule": "process fields only: no predicted grid, no query input, no held query answer and no test output; "
                    "grids appear by size only (the demonstrations are in the separate DEMOS file); a field missing "
                    "from the records is written 'not recorded'",
    "arm_names": ARMS,
    "generator_record": {"source": src("evaluation"), "family": unit_ev["family"], "template": unit_ev["template"],
                         "op": unit_ev["op"], "params": unit_ev["params"],
                         "partition": ev["controller"][T]["partition"]},
    "observe": {"source": src("controller_record"), "n_demos": rec["n_demos"], "shape_relation": rec["shape_relation"],
                "closest_program": tree(rec["closest"]["program_tree"]) if rec.get("closest") else "not recorded",
                "closest_cells_correct": [rec["closest"]["cells_correct"], rec["closest"]["cells_total"]]
                if rec.get("closest") else "not recorded"},
    "represent_and_search": {"source": src("controller_record"),
                             "base_search": {k: rec["base"][k] for k in ("fit", "program", "level_complete", "stop",
                                                                         "calls", "bank", "closures", "cpu_s")}},
    "fail": {"source": src("controller_record", "controller_summary"),
             "deeper_probe": {k: rec["probe_deeper_search"][k] for k in ("fit", "program", "level_complete", "stop",
                                                                         "calls", "cpu_s")},
             "inexpressible_within": rec["inexpressible_within"], "hypotheses": rec["hypotheses"],
             "status": summ["status"], "decision": summ["decision"]},
    "per_arm_outcomes_by_seed": {"source": src("evaluation", "hole_units", "enum_units_s0", "enum_units_s1",
                                               "enum_units_s2"), "seeds": arms},
    "matched_static_search": {"source": src("matched_static", "evaluation"), **static},
    "analysis_summary_by_arm": {"source": src("analysis"), **summary},
    "typed_hole_that_succeeded": hole,
    "why_the_raw_demonstration_hole_failed": raw,
}
out = os.path.join(ST, "exports", f"WORKED_EXAMPLE_{T}.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=1)
    f.write("\n")
txt = open(out).read()
assert '"preds"' not in txt and "thetas" not in txt and "test_input" not in txt and "residual\"" not in txt
print(json.dumps({"written": [out, out.replace(".json", "_DEMOS.json")], "demos": len(demos),
                  "mirrored_inputs": mirrored_in, "same_outputs": same_out, "admitted": sid}))
