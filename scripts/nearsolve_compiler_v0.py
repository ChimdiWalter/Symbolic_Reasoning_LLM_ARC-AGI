#!/usr/bin/env python3
"""Near-Solve Compiler v0 (CORA Stage A, analysis-only).

Converts the near-solve corpus from pixel-level residuals into SEMANTIC
failure records (NS-0..NS-5 ladder), then aggregates the measured
failure-family table that dictates which expression-language primitives
to build next.

STRICTLY read-only over engine artifacts. No engine imports, no LLMs,
no per-task solvers: pure deterministic reclassification of stored
artifacts. Every number in docs/NS_FAILURE_FAMILIES.md is reproducible
by rerunning this script.

Corpus choice: outputs/unified_harness_v22 (the most recent full run,
"full_v22", matching the current 181-sealed engine state). The older
v10 corpus (847 records, config full_v6_round6) is superseded; we report
its record count for comparison in the limitations section.

Inputs (all read-only):
  outputs/unified_harness_v22/near_solves.jsonl          -- corpus spine (824)
  outputs/unified_harness_v22/object/near_solve_parts/*  -- rich per-task parts
                                                            (program, residual,
                                                            LOO divergence)
  outputs/blocker_census_v14.json                        -- per-task blockers
                                                            (v14 run; secondary)
  outputs/structural_vocab_census.json                   -- 40-task structural
                                                            tags (primary tags)
  data/arc-agi_training_challenges.json                  -- grid shapes

Outputs:
  outputs/nearsolve_compiler/ns_dataset.jsonl   -- one record per near-solve
  outputs/nearsolve_compiler/family_table.json  -- aggregation (families,
                                                   clusters, recommendation
                                                   inputs)
  stdout: the failure-family table
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "outputs/unified_harness_v22/near_solves.jsonl")
PARTS_DIR = os.path.join(ROOT, "outputs/unified_harness_v22/object/near_solve_parts")
V14_CENSUS = os.path.join(ROOT, "outputs/blocker_census_v14.json")
VOCAB_CENSUS = os.path.join(ROOT, "outputs/structural_vocab_census.json")
TRAIN_CH = os.path.join(ROOT, "data/arc-agi_training_challenges.json")
OUT_DIR = os.path.join(ROOT, "outputs/nearsolve_compiler")
SOURCE_CORPUS = "unified_harness_v22"

# ---------------------------------------------------------------------------
# DSL vocabulary, transcribed READ-ONLY from
# geocat_arc/object_reasoning/expressions.py (op dispatch, lines ~380-780)
# and generative.py (grow generator kinds, lines ~168-430).
# Used to judge dsl_expressible_today. Do NOT import the engine.
# ---------------------------------------------------------------------------
COLOR_OPS = {"const", "color_of", "most_common_color", "least_common_color",
             "color_map", "feature_map", "feature_affine"}
VEC_OPS = {"const", "vector_to", "vector_to_border", "gap_closing_vector",
           "scaled_unit", "step_toward", "align_vector", "mirror_vector",
           "reflect_across", "slide_vector"}
REF_OPS = {"self", "matched_template", "nearest_object",
           "nearest_object_of_color", "nearest_shape_twin", "container",
           "contained", "largest", "unique"}
PRED_OPS = {"true", "test", "in_set", "and2", "relation_exists"}
GROW_KINDS = {"ray", "halo", "fill_interior", "mirror_edge",
              "symmetry_complete", "ray_until_obstacle",
              "ray_through_absorbed", "row_line", "col_line", "cross_line",
              "line_periodic", "cross_center", "cavity_leak", "ray_deflect",
              "ray_relational"}
ALL_KNOWN_OPS = COLOR_OPS | VEC_OPS | REF_OPS | PRED_OPS | {
    "size", "hole_count", "feature", "count", "bbox_self", "bbox",
    "grid_quadrant", "separator_cell", "separator_block_self", "free_slot"}

# Known gaps (judged against the vocab above; see docs/NS_FAILURE_FAMILIES.md):
#  - no per-cell / neighborhood-conditional color expression (ColorExpr ops
#    are object-level only)
#  - no generative derivation of grow 'pattern' literals (PatternExpr = const)
#  - object synthesis ('copy' deltas: new output objects) only via narrow
#    synth_copy
#  - no scene-level control flow across rules

VECTORISH = {"vector", "direction", "offset", "placement", "offset0",
             "offset1", "offset2", "0:translate:vector"}
SCALARISH = {"length", "k", "period", "tile_w", "tile_h", "angle", "count"}


def load_json(path):
    with open(path) as fh:
        return json.load(fh)


def expr_op(v):
    return v.get("op") if isinstance(v, dict) else None


def slot_name(key):
    """Normalize a param key ('1:recolor:color' -> 'color')."""
    base = key.split(":")[-1]
    if base in VECTORISH or key in VECTORISH:
        return "vector"
    if base in SCALARISH:
        return "scalar"
    return base


def diff_programs(main, fold):
    """Deterministic structural diff between the full-train program and one
    LOO fold program. Returns list of tuples:
      ('no_fold_program',) | ('structure_diff',) | ('output_spec_diff',)
      ('selector_diff', rule_idx)
      ('value_diff', slot, op) | ('kind_diff', slot, op_main, op_fold)
      ('param_missing', slot)
    """
    if not fold:
        return [("no_fold_program",)]
    mr = main.get("rules") or []
    fr = fold.get("rules") or []
    if len(mr) != len(fr):
        return [("structure_diff",)]
    m_dts = [((r.get("action") or {}).get("delta_type")) for r in mr]
    f_dts = [((r.get("action") or {}).get("delta_type")) for r in fr]
    if m_dts != f_dts:
        return [("structure_diff",)]
    diffs = []
    if (main.get("output_spec") or {}) != (fold.get("output_spec") or {}):
        diffs.append(("output_spec_diff",))
    for i, (a, b) in enumerate(zip(mr, fr)):
        sa = (a.get("selector") or {}).get("predicate")
        sb = (b.get("selector") or {}).get("predicate")
        if sa != sb:
            diffs.append(("selector_diff", i))
        pa = (a.get("action") or {}).get("params") or {}
        pb = (b.get("action") or {}).get("params") or {}
        for key in sorted(set(pa) | set(pb)):
            if key not in pa or key not in pb:
                diffs.append(("param_missing", slot_name(key)))
                continue
            va, vb = pa[key], pb[key]
            if va == vb:
                continue
            oa, ob = expr_op(va), expr_op(vb)
            if oa == ob:
                diffs.append(("value_diff", slot_name(key), oa))
            else:
                diffs.append(("kind_diff", slot_name(key), oa, ob))
    if (main.get("default_action") or {}) != (fold.get("default_action") or {}):
        diffs.append(("structure_diff",))
    return diffs


def program_summary(prog):
    if not prog:
        return None
    out = []
    for r in prog.get("rules") or []:
        a = r.get("action") or {}
        params = {k: expr_op(v) or "raw" for k, v in (a.get("params") or {}).items()}
        out.append({"delta_type": a.get("delta_type"),
                    "param_ops": params,
                    "parameter_class": a.get("parameter_class")})
    return {"segmentation_variant": prog.get("segmentation_variant"),
            "rules": out,
            "output_mode": (prog.get("output_spec") or {}).get("mode")}


def delta_type_set(prog):
    return {((r.get("action") or {}).get("delta_type"))
            for r in (prog.get("rules") or [])}


def main_extensional(prog):
    """True if the program is dominated by per-object literal grow rules
    (delta_type grow with const 'pattern'), i.e. an extensional pixel
    pattern stored as rules rather than derived generatively."""
    rules = prog.get("rules") or []
    if not rules:
        return False
    n_grow_const = 0
    for r in rules:
        a = r.get("action") or {}
        if a.get("delta_type") != "grow":
            continue
        pat = (a.get("params") or {}).get("pattern")
        if expr_op(pat) == "const" or pat is None:
            n_grow_const += 1
    return n_grow_const >= max(1, len(rules) / 2)


def has_map_slot(prog):
    """Return (slot, op) of first induced-map param in the program, else None."""
    for key_prefix, r in enumerate(prog.get("rules") or []):
        for k, v in ((r.get("action") or {}).get("params") or {}).items():
            if expr_op(v) in ("feature_map", "color_map"):
                return slot_name(k), expr_op(v)
    return None


def train_shapes(task):
    """[(in_shape, out_shape), ...] for train pairs."""
    out = []
    for pair in task.get("train", []):
        i, o = pair["input"], pair["output"]
        out.append(((len(i), len(i[0])), (len(o), len(o[0]))))
    return out


def pixel_residual_from_acc(per_pair_acc, shapes):
    """(n_wrong_cells, n_pairs_failing) from per-pair train pixel acc."""
    if not per_pair_acc:
        return None, None
    wrong, failing = 0, 0
    for idx, acc in enumerate(per_pair_acc):
        if acc is None:
            continue
        if idx < len(shapes):
            h, w = shapes[idx][1]
            wrong += round((1.0 - acc) * h * w)
        if acc < 1.0:
            failing += 1
    return wrong, failing


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_loo(parts, tags, v14):
    """Classify a train-perfect-but-LOO-failing parts record."""
    prog = parts.get("program_partial") or {}
    res = parts.get("residual") or {}
    divs = res.get("loo_divergence") or []
    all_diffs, errors, shape_mismatch, cells_wrong = [], [], False, 0
    for d in divs:
        if d.get("shape_mismatch"):
            shape_mismatch = True
        if d.get("cells_wrong"):
            cells_wrong += d["cells_wrong"]
        if d.get("error"):
            errors.append(d["error"])
        all_diffs.extend(diff_programs(prog, d.get("fold_program")))

    n_pairs_failing = len(res.get("loo_failures") or []) or len(divs) or None

    base = {"pixel_residual": {"n_wrong_cells": cells_wrong or None,
                               "n_pairs_failing": n_pairs_failing}}

    if shape_mismatch:
        return dict(base, ns_level="NS-5", blocking_parameter="output_shape",
                    required_class="view_change", dsl_expressible_today="unknown",
                    repair_hypothesis="output shape: fold programs produce wrong-"
                    "shaped grids -> output-spec/view must be derived, not induced "
                    "per-fold",
                    cluster_key="output_shape|view_change|fold-shape-mismatch",
                    evidence="loo_divergence shape_mismatch")

    kinds = {d[0] for d in all_diffs}
    slot_diffs = [d for d in all_diffs
                  if d[0] in ("value_diff", "kind_diff", "param_missing")]
    slots = {d[1] for d in slot_diffs}
    selector_diff = "selector_diff" in kinds

    # Case: fold reinduction produced structurally different programs.
    if "structure_diff" in kinds or "no_fold_program" in kinds:
        fold_progs = [d.get("fold_program") for d in divs]
        present = [p for p in fold_progs if p]
        same_family = bool(present) and all(
            delta_type_set(p) == delta_type_set(prog) for p in present)
        if main_extensional(prog) and (same_family or not present):
            return dict(base, ns_level="NS-4", blocking_parameter="pattern",
                        required_class="outside_vocabulary",
                        dsl_expressible_today=False,
                        repair_hypothesis="pattern: program stores per-object "
                        "literal grow rules (const pattern); fold reinduction "
                        "yields a different rule set -> pattern must be DERIVED "
                        "generatively (rule from object features/geometry), not "
                        "stored extensionally",
                        cluster_key="pattern|outside_vocabulary|extensional-pattern",
                        evidence="rule-structure fold-unstable; %d/%d rules are "
                        "const-pattern grow; same delta family across folds=%s"
                        % (sum(1 for r in prog.get("rules") or []
                               if (r.get("action") or {}).get("delta_type")
                               == "grow"),
                           len(prog.get("rules") or []), same_family))
        if same_family:
            return dict(base, ns_level="NS-3", blocking_parameter="selector",
                        required_class="relational",
                        dsl_expressible_today="unknown",
                        repair_hypothesis="rule partition: folds keep the same "
                        "delta family but split objects into different rules -> "
                        "selector/grouping predicate unstable, needs relational "
                        "form",
                        cluster_key="selector|relational|rule-partition",
                        evidence="structure_diff with identical delta-type family "
                        "%s across folds" % sorted(
                            x for x in delta_type_set(prog) if x))
        v14_blockers = set((v14 or {}).get("blockers") or [])
        vocab_ev = ({t for t in tags} &
                    {"extensional_pattern", "neighborhood_conditional",
                     "color_function_of_context", "connector_between_objects",
                     "extension_beyond_objects"}) or \
                   {b for b in v14_blockers if b.startswith("vocab:")}
        if vocab_ev:
            return dict(base, ns_level="NS-4",
                        blocking_parameter="program_structure",
                        required_class="outside_vocabulary",
                        dsl_expressible_today=False,
                        repair_hypothesis="structure: fold programs disagree "
                        "structurally; census tags (%s) place the needed rule "
                        "outside the delta/expression vocabulary"
                        % ",".join(sorted(vocab_ev)),
                        cluster_key="structure|outside_vocabulary|fold-unstable",
                        evidence="structure_diff + census tags")
        return dict(base, ns_level="UNDET", blocking_parameter=None,
                    required_class="unknown", dsl_expressible_today="unknown",
                    repair_hypothesis=None,
                    cluster_key="structure|unknown|fold-unstable",
                    evidence="structure_diff, no census tags to decide")

    # Case: single blocking parameter slot.
    if len(slots) == 1 and not selector_diff:
        slot = next(iter(slots))
        kind_pairs = sorted({(d[2], d[3]) for d in slot_diffs
                             if d[0] == "kind_diff"})
        ops = sorted({d[2] for d in slot_diffs if d[0] == "value_diff"})
        if slot == "color":
            if tags & {"color_function_of_context", "neighborhood_conditional"}:
                return dict(base, ns_level="NS-4", blocking_parameter="color",
                            required_class="outside_vocabulary",
                            dsl_expressible_today=False,
                            repair_hypothesis="color: literal/induced-map -> "
                            "context-conditional color (per-cell/neighborhood "
                            "function; ColorExpr vocab is object-level only)",
                            cluster_key="color|outside_vocabulary|context-conditional",
                            evidence="single color slot diff + census tag "
                            "color_function_of_context")
            note = ("novel-output-color; feature_map/feature_affine can emit "
                    "novel colors if a stable driver feature exists"
                    if "novel_color_in_output" in tags else
                    "color_of(ref)/feature_map with stable driver may fix")
            return dict(base, ns_level="NS-3", blocking_parameter="color",
                        required_class="relational",
                        dsl_expressible_today="unknown",
                        repair_hypothesis="color: literal(const/map) -> "
                        "relational derived color (%s)" % note,
                        cluster_key="color|relational|derived-color",
                        evidence="single color slot diff (ops=%s kinds=%s)"
                        % (ops, kind_pairs))
        if slot == "pattern":
            return dict(base, ns_level="NS-4", blocking_parameter="pattern",
                        required_class="outside_vocabulary",
                        dsl_expressible_today=False,
                        repair_hypothesis="pattern: extensional(literal mask) -> "
                        "generative(derive mask from object features/scaling; "
                        "PatternExpr is const-only)",
                        cluster_key="pattern|outside_vocabulary|extensional-pattern",
                        evidence="single pattern slot diff across folds")
        if slot == "mode":
            return dict(base, ns_level="NS-3", blocking_parameter="mode",
                        required_class="relational",
                        dsl_expressible_today="unknown",
                        repair_hypothesis="grow mode: literal(kind) -> conditional"
                        "/derived generator kind (kind varies per fold)",
                        cluster_key="mode|relational|conditional-mode",
                        evidence="single mode slot diff (kinds=%s)" % kind_pairs)
        if slot == "vector":
            exp = True
            return dict(base, ns_level="NS-3", blocking_parameter="vector",
                        required_class="relational",
                        dsl_expressible_today=exp,
                        repair_hypothesis="vector/direction: literal -> relational "
                        "(vector_to/step_toward/align_vector/scaled_unit family "
                        "exists in VecExpr vocab; induction picked a literal)",
                        cluster_key="vector|relational|existing-op",
                        evidence="single vector slot diff (ops=%s kinds=%s)"
                        % (ops, kind_pairs))
        if slot == "scalar":
            return dict(base, ns_level="NS-3", blocking_parameter="scalar",
                        required_class="relational", dsl_expressible_today=True,
                        repair_hypothesis="scalar(length/count): literal -> "
                        "feature-derived scalar (ScalarExpr feature/count ops "
                        "exist)",
                        cluster_key="scalar|relational|existing-op",
                        evidence="single scalar slot diff")
        if slot in ("source", "target"):
            return dict(base, ns_level="NS-3", blocking_parameter="source",
                        required_class="relational", dsl_expressible_today=True,
                        repair_hypothesis="source ref: unstable reference -> "
                        "RefExpr vocabulary (nearest_object/container/unique) "
                        "covers the needed reference",
                        cluster_key="source|relational|reference",
                        evidence="single source slot diff")
        return dict(base, ns_level="NS-3", blocking_parameter=slot,
                    required_class="unknown", dsl_expressible_today="unknown",
                    repair_hypothesis="param '%s': unstable across folds" % slot,
                    cluster_key="%s|unknown|param" % slot,
                    evidence="single %s slot diff" % slot)

    # Case: selector predicate differs (alone or with params).
    if selector_diff and len(slots) == 0:
        return dict(base, ns_level="NS-3", blocking_parameter="selector",
                    required_class="relational", dsl_expressible_today="unknown",
                    repair_hypothesis="selector: fold predicates disagree -> "
                    "relational predicate (relation_exists/feature test) needed",
                    cluster_key="selector|relational|predicate",
                    evidence="selector_diff only")

    # Case: multiple slots differ.
    if slots:
        slot_list = sorted(slots)
        if set(slot_list) <= {"vector", "scalar", "source", "mode", "color"}:
            return dict(base, ns_level="NS-3",
                        blocking_parameter="multi:" + "+".join(slot_list),
                        required_class="relational",
                        dsl_expressible_today="unknown",
                        repair_hypothesis="multiple literal params (%s) unstable "
                        "-> each needs a derived/relational form"
                        % ",".join(slot_list),
                        cluster_key="multi|relational|multi-literal",
                        evidence="multi-slot diff %s" % slot_list)
        return dict(base, ns_level="UNDET",
                    blocking_parameter="multi:" + "+".join(slot_list),
                    required_class="unknown", dsl_expressible_today="unknown",
                    repair_hypothesis=None,
                    cluster_key="multi|unknown|multi-slot",
                    evidence="multi-slot diff incl. pattern/other %s" % slot_list)

    # Case: no program diffs at all.
    if errors:
        m = has_map_slot(prog)
        if m:
            slot, op = m
            return dict(base, ns_level="NS-3", blocking_parameter=slot,
                        required_class="relational",
                        dsl_expressible_today="unknown",
                        repair_hypothesis="map: extensional(%s table misses "
                        "held-out key -> EvalError) -> functional generalization "
                        "(feature_affine or completed family)" % op,
                        cluster_key="map|relational|functional-generalization",
                        evidence="fold EvalError with induced %s" % op)
        return dict(base, ns_level="UNDET", blocking_parameter=None,
                    required_class="unknown", dsl_expressible_today="unknown",
                    repair_hypothesis=None,
                    cluster_key="eval_error|unknown|no-diff",
                    evidence="fold eval errors %s, no program diff"
                    % sorted(set(errors)))
    if divs and not all_diffs:
        return dict(base, ns_level="NS-2", blocking_parameter="correspondence",
                    required_class="relational", dsl_expressible_today="unknown",
                    repair_hypothesis="identical program diverges on fold -> "
                    "segmentation/matching context differs; correspondence must "
                    "be made explicit",
                    cluster_key="correspondence|relational|context-instability",
                    evidence="identical_program_diverged")
    return dict(base, ns_level="UNDET", blocking_parameter=None,
                required_class="unknown", dsl_expressible_today="unknown",
                repair_hypothesis=None, cluster_key="loo|unknown|no-divergence-info",
                evidence="loo stage but empty divergence trace")


def classify_parts(parts, tags, v14):
    stage = parts.get("failure_stage")
    fit = parts.get("train_fit_pixels")
    res = parts.get("residual") or {}
    ud = res.get("unexplained_deltas") or []
    ud_hist = {u["delta_type"]: u["count"] for u in ud}
    n_unexplained = sum(ud_hist.values())

    if stage == "loo":
        rec = classify_loo(parts, tags, v14)
    elif stage == "matching":
        if fit is not None and fit < 0.5:
            rec = {"ns_level": "UNDET", "blocking_parameter": None,
                   "required_class": "unknown", "dsl_expressible_today": "unknown",
                   "repair_hypothesis": None,
                   "cluster_key": "matching|unknown|low-partial-fit",
                   "evidence": "matching stage, train_fit=%.2f < 0.5" % fit,
                   "pixel_residual": {"n_wrong_cells": None,
                                      "n_pairs_failing": None}}
        elif ud_hist and max(ud_hist, key=ud_hist.get) == "copy":
            rec = {"ns_level": "NS-4", "blocking_parameter": "position",
                   "required_class": "outside_vocabulary",
                   "dsl_expressible_today": False,
                   "repair_hypothesis": "object synthesis: output objects with "
                   "no input counterpart ('copy' deltas) -> copy/spawn-at-"
                   "relational-position; only narrow synth_copy exists",
                   "cluster_key": "copy|outside_vocabulary|object-synthesis",
                   "evidence": "matching stage dominated by unexplained copy "
                   "deltas (%d)" % ud_hist["copy"],
                   "pixel_residual": {"n_wrong_cells": None,
                                      "n_pairs_failing": None}}
        else:
            rec = {"ns_level": "NS-2", "blocking_parameter": "correspondence",
                   "required_class": "relational",
                   "dsl_expressible_today": "unknown",
                   "repair_hypothesis": "correspondence: object matching fails "
                   "across pairs/folds -> relational correspondence (role/"
                   "shape-twin/positional) needed",
                   "cluster_key": "correspondence|relational|matching",
                   "evidence": "matching stage, fit=%s, unexplained=%s"
                   % (fit, ud_hist or "none"),
                   "pixel_residual": {"n_wrong_cells": None,
                                      "n_pairs_failing": None}}
    elif stage == "parameter":
        if fit is not None and fit < 0.5:
            rec = {"ns_level": "UNDET", "blocking_parameter": None,
                   "required_class": "unknown", "dsl_expressible_today": "unknown",
                   "repair_hypothesis": None,
                   "cluster_key": "parameter|unknown|low-partial-fit",
                   "evidence": "parameter stage, train_fit=%.2f < 0.5" % fit,
                   "pixel_residual": {"n_wrong_cells": None,
                                      "n_pairs_failing": None}}
        else:
            dom = max(ud_hist, key=ud_hist.get) if ud_hist else None
            rec = {"ns_level": "NS-3",
                   "blocking_parameter": {"translate": "vector",
                                          "grow": "pattern",
                                          "recolor": "color",
                                          "copy": "position",
                                          "paint": "source"}.get(dom, dom),
                   "required_class": ("outside_vocabulary" if dom == "copy"
                                      else "relational"),
                   "dsl_expressible_today": (False if dom == "copy"
                                             else "unknown"),
                   "repair_hypothesis": "parameter search failed for %s deltas "
                   "-> no expression in current vocab fits all pairs" % dom,
                   "cluster_key": "%s|%s|param-search-fail"
                   % (dom or "param",
                      "outside_vocabulary" if dom == "copy" else "relational"),
                   "evidence": "parameter stage, unexplained=%s" % (ud_hist or {}),
                   "pixel_residual": {"n_wrong_cells": None,
                                      "n_pairs_failing": None}}
    elif stage == "selector":
        if fit is not None and fit < 0.5:
            rec = {"ns_level": "UNDET", "blocking_parameter": None,
                   "required_class": "unknown", "dsl_expressible_today": "unknown",
                   "repair_hypothesis": None,
                   "cluster_key": "selector|unknown|low-partial-fit",
                   "evidence": "selector stage, train_fit=%.2f < 0.5" % fit,
                   "pixel_residual": {"n_wrong_cells": None,
                                      "n_pairs_failing": None}}
        else:
            rec = {"ns_level": "NS-3", "blocking_parameter": "selector",
                   "required_class": "relational",
                   "dsl_expressible_today": "unknown",
                   "repair_hypothesis": "selector: no predicate in PredExpr vocab "
                   "separates the acting objects -> relational/feature predicate "
                   "missing",
                   "cluster_key": "selector|relational|predicate",
                   "evidence": "selector stage, fit=%s" % fit,
                   "pixel_residual": {"n_wrong_cells": None,
                                      "n_pairs_failing": None}}
    else:
        rec = {"ns_level": "UNDET", "blocking_parameter": None,
               "required_class": "unknown", "dsl_expressible_today": "unknown",
               "repair_hypothesis": None,
               "cluster_key": "parts|unknown|unknown-stage",
               "evidence": "unknown parts failure_stage %r" % stage,
               "pixel_residual": {"n_wrong_cells": None,
                                  "n_pairs_failing": None}}
    rec["parts_failure_stage"] = stage
    rec["parts_train_fit_pixels"] = fit
    rec["unexplained_delta_hist"] = ud_hist or None
    return rec


def classify_record(nsrec, parts, tags, v14, shapes):
    source = nsrec["source"]
    acc = nsrec.get("best_train_pixel_acc")
    per_pair = nsrec.get("per_pair_acc")

    if parts is not None:
        rec = classify_parts(parts, tags, v14)
        # fill pixel residual from per-pair acc when parts had none
        if rec["pixel_residual"]["n_wrong_cells"] is None and per_pair:
            w, f = pixel_residual_from_acc(per_pair, shapes)
            rec["pixel_residual"] = {"n_wrong_cells": w, "n_pairs_failing": f}
        return rec

    w, f = pixel_residual_from_acc(per_pair, shapes)
    base = {"pixel_residual": {"n_wrong_cells": w, "n_pairs_failing": f},
            "parts_failure_stage": None, "parts_train_fit_pixels": None,
            "unexplained_delta_hist": None}

    if source == "geocat_near_solve":
        fam = nsrec.get("best_family_or_strategy")
        if acc is not None and acc >= 0.6:
            return dict(base, ns_level="NS-1", blocking_parameter=None,
                        required_class="unknown", dsl_expressible_today="unknown",
                        repair_hypothesis="structural strategy '%s' fits %.0f%% "
                        "of pixels -> residual cells need an object-level rule "
                        "the strategy cannot see" % (fam, 100 * acc),
                        cluster_key="structural|partial|%s" % fam,
                        evidence="geocat partial acc=%.3f, no object parts" % acc)
        return dict(base, ns_level="UNDET", blocking_parameter=None,
                    required_class="unknown", dsl_expressible_today="unknown",
                    repair_hypothesis=None,
                    cluster_key="structural|unknown|low-fit",
                    evidence="geocat acc=%.3f < 0.6, no object parts"
                    % (acc or 0.0))

    # identity fallback
    shape_change = any(i != o for i, o in shapes) if shapes else None
    if shape_change:
        return dict(base, ns_level="NS-5", blocking_parameter="view",
                    required_class="view_change", dsl_expressible_today=False,
                    repair_hypothesis="representation: train pairs change grid "
                    "shape and no layer engaged -> needs a different output "
                    "view (crop/tile/panel/quotient), not a delta program",
                    cluster_key="view|view_change|shape-change-no-engagement",
                    evidence="identity fallback + shape-changing pairs")
    if acc is not None and acc >= 0.8:
        return dict(base, ns_level="NS-0", blocking_parameter=None,
                    required_class="unknown", dsl_expressible_today="unknown",
                    repair_hypothesis="output is a near-copy of input (%.0f%% "
                    "pixels) but no segmentation produced a fitting delta "
                    "program -> sparse edit invisible to current views"
                    % (100 * acc),
                    cluster_key="pixel|unknown|near-copy",
                    evidence="identity acc=%.3f >= 0.8, no engagement" % acc)
    return dict(base, ns_level="NS-5", blocking_parameter="view",
                required_class="view_change", dsl_expressible_today=False,
                repair_hypothesis="representation: same-shape task, all "
                "segmentation variants failed to engage -> current object "
                "views do not carve this task correctly",
                cluster_key="view|view_change|same-shape-no-engagement",
                evidence="identity acc=%.3f < 0.8, no engagement, same-shape"
                % (acc or 0.0))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    corpus = [json.loads(l) for l in open(CORPUS)]
    train = load_json(TRAIN_CH)
    v14_pt = load_json(V14_CENSUS).get("per_task", {})
    vc = load_json(VOCAB_CENSUS)
    tags_by_task = {}
    for tr in vc.get("task_results", []):
        tags_by_task[tr["task_id"]] = {t["subcategory"]
                                       for t in tr.get("structural_tags", [])}

    ds_path = os.path.join(OUT_DIR, "ns_dataset.jsonl")
    n_written = 0
    records = []
    with open(ds_path, "w") as out:
        for nsrec in corpus:
            tid = nsrec["task_id"]
            parts = None
            ppath = os.path.join(PARTS_DIR, tid + ".jsonl")
            if os.path.exists(ppath):
                with open(ppath) as fh:
                    lines = fh.read().splitlines()
                if lines:
                    parts = json.loads(lines[0])
            tags = tags_by_task.get(tid, set())
            v14 = v14_pt.get(tid)
            shapes = train_shapes(train[tid]) if tid in train else []
            rec = classify_record(nsrec, parts, tags, v14, shapes)
            rec_out = {
                "task_id": tid,
                "source_corpus": SOURCE_CORPUS,
                "candidate": {
                    "best_layer": nsrec.get("best_layer"),
                    "family_or_strategy": nsrec.get("best_family_or_strategy"),
                    "best_train_pixel_acc": nsrec.get("best_train_pixel_acc"),
                    "program": program_summary(
                        (parts or {}).get("program_partial")),
                },
                "pixel_residual": rec["pixel_residual"],
                "ns_level": rec["ns_level"],
                "blocking_parameter": rec["blocking_parameter"],
                "required_class": rec["required_class"],
                "dsl_expressible_today": rec["dsl_expressible_today"],
                "repair_hypothesis": rec["repair_hypothesis"],
                "cluster_key": rec["cluster_key"],
                "evidence": rec["evidence"],
                "parts_failure_stage": rec.get("parts_failure_stage"),
                "census_v14_blockers": (v14 or {}).get("blockers"),
                "vocab_census_tags": sorted(tags) if tags else None,
            }
            out.write(json.dumps(rec_out) + "\n")
            out.flush()
            n_written += 1
            records.append(rec_out)

    # ---------------- aggregation ----------------
    by_level = Counter(r["ns_level"] for r in records)
    clusters = defaultdict(list)
    for r in records:
        clusters[r["cluster_key"]].append(r["task_id"])
    cluster_rows = sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    fam_rows = []
    for key, tids in cluster_rows:
        sub = [r for r in records if r["cluster_key"] == key]
        exp = Counter(str(r["dsl_expressible_today"]) for r in sub)
        lev = Counter(r["ns_level"] for r in sub)
        fam_rows.append({
            "cluster_key": key,
            "count": len(tids),
            "ns_levels": dict(lev),
            "expressible_today": dict(exp),
            "example_task_ids": sorted(tids)[:5],
        })

    ns34 = [r for r in records if r["ns_level"] in ("NS-3", "NS-4")]
    ns34_by_cluster = Counter(r["cluster_key"] for r in ns34)
    undet = by_level.get("UNDET", 0)

    agg = {
        "source_corpus": SOURCE_CORPUS,
        "corpus_records": len(corpus),
        "records_written": n_written,
        "ns_level_histogram": dict(sorted(by_level.items())),
        "undet_count": undet,
        "families": fam_rows,
        "ns34_clusters": dict(ns34_by_cluster.most_common()),
        "cross_task_clusters_ge3": [f for f in fam_rows if f["count"] >= 3],
    }
    with open(os.path.join(OUT_DIR, "family_table.json"), "w") as fh:
        json.dump(agg, fh, indent=1)

    # ---------------- stdout table ----------------
    print("=" * 78)
    print("NEAR-SOLVE COMPILER v0 -- corpus %s (%d records)"
          % (SOURCE_CORPUS, len(corpus)))
    print("=" * 78)
    print("NS-level histogram:")
    for k in sorted(by_level):
        print("  %-6s %4d" % (k, by_level[k]))
    print("-" * 78)
    print("%-52s %5s  %-8s %s" % ("FAILURE FAMILY (cluster_key)", "count",
                                  "NS", "expressible_today"))
    print("-" * 78)
    for f in fam_rows:
        lev = ",".join("%s:%d" % kv for kv in sorted(f["ns_levels"].items()))
        exp = ",".join("%s:%d" % kv for kv in sorted(
            f["expressible_today"].items()))
        print("%-52s %5d  %-14s %s" % (f["cluster_key"], f["count"], lev, exp))
        print("        e.g. %s" % " ".join(f["example_task_ids"]))
    print("-" * 78)
    print("UNDET: %d / %d" % (undet, n_written))
    print("Aggregation written to %s" % os.path.join(OUT_DIR,
                                                     "family_table.json"))


if __name__ == "__main__":
    main()
