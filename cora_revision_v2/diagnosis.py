"""CORA reasoning v2: typed diagnoses of why the current hypotheses are not enough (DEVELOPMENT).

A diagnosis records:
- the observed SYMPTOM (its label);
- the COMPETING CAUSES that could produce it;
- the bounded PROBE run to tell them apart, and its RESULT;
- the cause the result SUPPORTS, and what stays UNCERTAIN;
- the NEXT ACTION: a revision to try, an exploratory (uncertified) attempt, or abstention.

Labels (symptoms):
- GEOMETRY_GAP: no single expression reproduces the changed positions in any of the 7 views.
- COLOUR_POLICY_GAP: positions are reproduced, but no colour policy reproduces the outputs.
- REPRESENTATION_AMBIGUITY: consistent hypotheses in different views predict different test outputs.
- MULTIPLE_ACTIONS_NEEDED: the demonstrations change cells in more than one way (adds plus deletes or recolours).
- HYPOTHESIS_DISAGREEMENT: consistent hypotheses within one view predict different test outputs.
- FOLD_FRAGILITY: a unique prediction that the search does not rebuild in every omitted-demonstration fold.
- ENGINE_REJECTION: the native engine refuses an installed hypothesis. Bridge integration only; the standalone
  reasoner never emits it.
- RESOURCE_LIMIT: a search hit its cap or budget, so the version space may be truncated.

Only the training pairs, the test INPUTS and the reasoner's own record are read. No test answer and no forensic
class is read, so a diagnosis may drive a revision. "No program found" is never reported as "needs new semantics":
the strongest conclusion is "not expressible in this hypothesis class".
"""
import collections
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

LABELS = ("GEOMETRY_GAP", "COLOUR_POLICY_GAP", "REPRESENTATION_AMBIGUITY", "MULTIPLE_ACTIONS_NEEDED",
          "HYPOTHESIS_DISAGREEMENT", "FOLD_FRAGILITY", "ENGINE_REJECTION", "RESOURCE_LIMIT")
# revisions a diagnosis may select (the executor is separate; this module only decides)
ACTIONS = ("TYPED_SCENE_TRANSFORM", "GUARDED_GEOMETRY", "EXTEND_COLOUR_FEATURES", "WIDEN_SEARCH",
           "EXPLORATORY_ATTEMPT", "TWO_ATTEMPTS", "ABSTAIN")


def _d(label, observed, causes, probe, result, supports, uncertainty, action):
    assert label in LABELS and action in ACTIONS
    return {"label": label, "observed": observed, "competing_causes": causes, "probe": probe, "result": result,
            "supports": supports, "uncertainty": uncertainty, "next_action": action}


# ---------------------------------------------------------------- probes (training pairs and test inputs only)
def change_profile(train):
    """How the demonstrations change cells: per pair, adds / deletes / recolours, or a size change."""
    from cora_revision_v2.gap_audit import pair_types, label
    types = [pair_types(a, b) for a, b in train]
    return {"label": label(set().union(*types)), "per_pair": [sorted(t) for t in types]}


def colour_probe(train, views=None, k=50):
    """For up to k positional fits per view: do the added cells of each object carry one colour, and does some object
    feature determine that colour consistently across the demonstrations?"""
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    from cora_fhr.oracle_expressibility import _fits
    from cora_revision_v2 import scene_reasoner as SR
    res = {"fits_examined": 0, "multicolour_object": 0, "one_colour_per_object": 0, "feature_determines": 0,
           "origin_explains": 0, "features_conflict_free": collections.Counter()}
    for view in (views or list(V)):
        data = SR._scene(train, view)
        if data is None:
            break
        for expr in _fits(train, view, cap=k):
            res["fits_examined"] += 1
            per_obj, multi, origin_ok = [], False, True
            for A, B, ctxs in data:
                for x in ctxs:
                    add = SR.geometry_prov(expr, x)
                    cs = {int(B[c]) for c in add}
                    multi = multi or len(cs) > 1
                    per_obj.append((x, cs))
                    oc = SR.cell_colours("ORIGIN", x, add)
                    origin_ok = origin_ok and (oc is not None and all(oc[c] == int(B[c]) for c in add))
            res["origin_explains"] += origin_ok
            if multi:
                res["multicolour_object"] += 1
                continue
            res["one_colour_per_object"] += 1
            free = []
            for f in ("size", "colours", "h", "w"):
                table, ok = {}, True
                for x, cs in per_obj:
                    if cs and table.setdefault(SR._feature(x, f), next(iter(cs))) != next(iter(cs)):
                        ok = False
                        break
                if ok:
                    free.append(f)
                    res["features_conflict_free"][f] += 1
            res["feature_determines"] += bool(free)
    res["features_conflict_free"] = dict(res["features_conflict_free"])
    return res


def per_demo_geometry(train, views=None, budget_s=60.0):
    """Does each demonstration ALONE admit a single expression in some view, acting on a SUBSET of its objects
    (objects whose additions would overreach left out)? A uniform fit is a special case. CPU-time bounded."""
    from geocat_arc.object_reasoning.types import SegmentationVariant as V
    from cora_revision_v2.selection import demo_fits_selectively
    t0, fit, complete = time.process_time(), [], True
    for a, b in train:
        ok = False
        for view in (views or list(V)):
            r = demo_fits_selectively((a, b), view, deadline=t0 + budget_s)
            if r is None:
                complete = False
                break
            if r:
                ok = True
                break
        fit.append(ok if complete or ok else None)
        if not complete:
            break
    return {"demo_fits_selectively": fit, "complete": complete, "cpu_s": round(time.process_time() - t0, 1)}


# ---------------------------------------------------------------- the diagnosis
def diagnose(train, test_inputs, rec, budget_s=60.0):
    """rec: scene_reasoner.reason(train, test_inputs). Returns the list of diagnoses (possibly empty if CERTIFIED)."""
    out = []
    prof = change_profile(train)
    lab = prof["label"]
    additive = lab in ("add_only", "add_only_multicolour")
    diag = rec.get("diagnosis", "")

    if rec.get("cap_hit_views"):
        out.append(_d("RESOURCE_LIMIT", f"positional search reached its cap in views {rec['cap_hit_views']}",
                      ["the version space is truncated and a better hypothesis lies beyond the cap",
                       "the cap only drops redundant equivalents of hypotheses already kept"],
                      "none run here (a rerun at twice the cap is the bounded test)", {"cap_hit_views": rec["cap_hit_views"]},
                      "undetermined", "which cause holds is untested", "WIDEN_SEARCH"))

    if diag == "NO_CONSISTENT_HYPOTHESIS:GEOMETRY_GAP":
        causes = ["the demonstrations also delete or recolour cells, or change size: outside this additive class",
                  "additions only, but only some objects act, or the rule differs across demonstrations "
                  "(needs a selection guard or a composition)",
                  "additions only, and no single expression fits even one demonstration on any subset of its "
                  "objects in these views (geometry or representation outside this class)"]
        if not additive:
            mixed = lab.startswith("mixed:")
            label = "MULTIPLE_ACTIONS_NEEDED" if mixed else "GEOMETRY_GAP"
            out.append(_d(label, "no single expression reproduces the changed positions in any view", causes,
                          "change profile of the training pairs", prof,
                          causes[0] + (f" ({lab}: several actions)" if mixed else f" ({lab})"),
                          "the typed transformation that would fit is not yet known; untested",
                          "TYPED_SCENE_TRANSFORM"))
        else:
            pd = per_demo_geometry(train, budget_s=budget_s)
            if pd["complete"] and all(pd["demo_fits_selectively"]):
                sup, act = causes[1], "GUARDED_GEOMETRY"
                unc = ("a guard over the available features may not exist" + (
                    "; the selection family was searched and found none" if "select" in rec.get("families", []) else ""))
            elif pd["complete"]:
                sup, act = causes[2], "ABSTAIN"
                unc = ("this class does not express it; a guarded, deeper or re-segmented program was not tried. "
                       "This is NOT evidence that new semantics are needed")
            else:
                sup, act = "undetermined (probe budget exhausted)", "ABSTAIN"
                unc = "probe incomplete"
                out.append(_d("RESOURCE_LIMIT", "per-demonstration geometry probe exceeded its CPU budget",
                              ["more budget would separate the causes", "the probe would not separate them"],
                              f"per-demonstration fit, budget {budget_s} s CPU", pd, "undetermined", "untested",
                              "WIDEN_SEARCH"))
            out.append(_d("GEOMETRY_GAP", "no single expression reproduces the added positions in any view", causes,
                          "fit each demonstration alone, on any subset of its objects (first fit per view)", pd, sup,
                          unc, act))

    elif diag == "NO_CONSISTENT_HYPOTHESIS:COLOUR_POLICY_GAP":
        causes = ["an object's added cells carry several colours that its source cells do not explain",
                  "one colour per object, but no available feature (size, colours, h, w) determines it",
                  "the outputs also delete or recolour cells, so no full-grid match is possible",
                  "a feature determines the colour, but objects overlap and disagree on shared cells"]
        cp = colour_probe(train)
        if not additive:
            sup, act = causes[2] + f" ({lab})", "TYPED_SCENE_TRANSFORM"
            label = "MULTIPLE_ACTIONS_NEEDED"
        elif cp["one_colour_per_object"] == 0:
            sup, act, label = causes[0], "ABSTAIN", "COLOUR_POLICY_GAP"
        elif cp["feature_determines"] == 0:
            sup, act, label = causes[1], "EXTEND_COLOUR_FEATURES", "COLOUR_POLICY_GAP"
        else:
            sup, act, label = causes[3], "ABSTAIN", "COLOUR_POLICY_GAP"
        out.append(_d(label, "positions are reproduced but no colour policy reproduces the outputs", causes,
                      "colour multiplicity and feature consistency over up to 50 positional fits per view, "
                      "plus the change profile", {"colour": cp, "profile": prof}, sup,
                      "only the first 50 fits per view are examined; a later fit could behave differently", act))

    elif diag == "NO_CONSISTENT_HYPOTHESIS:UNPREDICTABLE_TEST":
        out.append(_d("FOLD_FRAGILITY", "every consistent hypothesis is undefined on the test input",
                      ["the test needs a table entry that no demonstration shows (evidence)",
                       "a colour policy is undefined there (e.g. a minority colour on a one-colour object)"],
                      "none beyond the reasoner's record", {}, "undetermined",
                      "the demonstrations may simply not determine the test", "ABSTAIN"))

    elif diag == "MANY_CONSISTENT_DISAGREE":
        groups = rec.get("distinct", [[]])
        views_per = [set(d["views"]) for g in groups for d in g]
        shared = set.intersection(*views_per) if views_per else set()
        by_view = collections.Counter(v for s in views_per for v in s)
        within = sorted(v for v, n in by_view.items() if n > 1)
        res = {"n_distinct": [len(g) for g in groups], "views_per_prediction": [sorted(s) for s in views_per],
               "views_with_several_predictions": within}
        causes = ["the object representation is ambiguous: different segmentations support different predictions",
                  "the rule is ambiguous: within one segmentation, different geometries or colour policies fit"]
        if len(views_per) > 1 and not shared and not within:
            out.append(_d("REPRESENTATION_AMBIGUITY", "consistent hypotheses predict different test outputs", causes,
                          "group distinct predictions by the views that produce them", res, causes[0],
                          "the demonstrations do not decide between segmentations", "TWO_ATTEMPTS"))
        else:
            out.append(_d("HYPOTHESIS_DISAGREEMENT", "consistent hypotheses predict different test outputs", causes,
                          "group distinct predictions by the views that produce them", res,
                          causes[1] + (" (and across views)" if not shared else ""),
                          "the demonstrations do not decide; a simplicity order is a preference, not evidence",
                          "TWO_ATTEMPTS"))

    elif diag == "FOLD_FRAGILITY":
        det = rec.get("fold_detail", [])
        kinds = collections.Counter(d["outcome"] if d["outcome"] != "UNPREDICTABLE" else d["cause"] for d in det)
        kinds.pop("SUCCESS", None)
        sup_ = rec.get("test_table_support", {})
        single = sorted(k for k, n in sup_.items() if n <= 1)
        causes = ["evidence: an entry the prediction needs appears in only one demonstration",
                  "procedure: with one demonstration fewer, the search commits to a wrong rule",
                  "evidence: with one demonstration fewer, several rules fit and disagree",
                  "resource or class: with one demonstration fewer, nothing fits"]
        if set(kinds) == {"UNSEEN_TABLE_KEY"}:
            sup, act = causes[0], "EXPLORATORY_ATTEMPT"
            unc = (f"the test needs table entries {single} supported by a single demonstration; the prediction may be "
                   "right, but these demonstrations cannot verify it" if single else
                   "the missing entries are not needed by the test; the fold failure concerns another entry")
        elif "WRONG_UNIQUE" in kinds:
            sup, act, unc = causes[1], "ABSTAIN", "the full-data prediction may still be right"
        elif "TIE" in kinds:
            sup, act, unc = causes[2], "EXPLORATORY_ATTEMPT", "the full-data prediction may still be right"
        else:
            sup, act, unc = causes[3], "ABSTAIN", "mixed fold outcomes"
        out.append(_d("FOLD_FRAGILITY", "a unique prediction that the search does not rebuild in every fold", causes,
                      "rerun the whole search in each omitted-demonstration fold; classify each failure; count how "
                      "many demonstrations support each table entry the test needs",
                      {"fold_outcomes": dict(kinds), "test_table_support": sup_}, sup, unc, act))
    return out


def decision(rec, diags):
    """The prediction tiers, kept separate:
    - CERTIFIED: unique and rebuilt in every fold by the unchanged verifier;
    - EXPLORATORY: executable and consistent with every demonstration, unverified; the diagnosis found no evidence
      against it (single-demonstration support, or a tie the demonstrations cannot break);
    - DISCOURAGED: consistent with the demonstrations, but a fold rebuilt a different unique answer;
    - NONE: no consistent hypothesis."""
    if rec.get("certified"):
        return {"tier": "CERTIFIED", "attempts": rec["attempts"]}
    if not rec.get("attempts"):
        return {"tier": "NONE", "attempts": None}
    acts = {d["next_action"] for d in diags}
    tier = "EXPLORATORY" if acts & {"EXPLORATORY_ATTEMPT", "TWO_ATTEMPTS"} else "DISCOURAGED"
    return {"tier": tier, "attempts": rec["attempts"]}
