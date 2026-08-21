"""Preregistration-conformance audit for CORA V2.

Compares what was frozen (docs/CORA_META_LANGUAGE_V2.md and
outputs/cora_breakthrough/v2_preregistration.json) against what the code
actually does, requirement by requirement, and emits a machine-readable
table with MATCH / MISSING / MISMATCH.

MISSING means the frozen spec has it and the implementation does not: it is
to be implemented, never treated as an amendment.  MISMATCH means the code
does something other than what was frozen: it is returned to the frozen
behaviour unless pre-existing evidence forces a dated amendment.

Reads code by introspection, so the audit cannot drift from the code the
experiments actually run.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_search as S  # noqa: E402
from geocat_arc.object_reasoning import meta_v2 as V  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"

#: Productions named in the frozen specification's combinator table.
SPEC_PRODUCTIONS = [
    "Partition", "Entities", "Group", "Pairs", "Orbits", "Order",
    "Select", "Unique", "ArgMin", "ArgMax",
    "Key", "Lookup", "MapOver", "Zip", "Fold", "Propagate", "Repeat",
    "Transform", "Anchor", "Recolour",
    "Paint", "Copy", "Overlay", "Erase", "Compose",
]

#: Slot types the frozen spec lists as INDUCED (fitted by a learner).
SPEC_INDUCED_TYPES = [
    "Map[FeatureValue,Colour]", "ColourBijection", "Transform", "Anchor",
    "Lattice", "SequenceRule",
]

SPEC_ROUTER_FIELDS = [
    "same_shape", "changed_cell_count", "changed_on_background_fraction",
    "preserves_nonbackground", "deletes_existing_cells",
    "recolours_existing_cells", "changed_component_count",
    "repeated_changed_shapes", "template_match_evidence",
    "translation_orbit_evidence", "pairwise_alignment_evidence",
    "panel_structure_evidence",
]

SPEC_ORDERING = ["result_type", "ast_depth", "mdl", "parameter_class",
                 "value_bound_count", "stable_serialization"]


def row(requirement, preregistered, implemented, status, evidence):
    return {"requirement": requirement, "preregistered": preregistered,
            "implemented": implemented, "status": status, "evidence": evidence}


def audit():
    prereg = json.loads((OUT / "v2_preregistration.json").read_text())
    rows = []

    # -- productions ------------------------------------------------------
    implemented = set(V.PRODUCTIONS)
    for name in SPEC_PRODUCTIONS:
        present = name in implemented
        rows.append(row(f"production:{name}", "present in frozen spec",
                        "present" if present else "absent",
                        "MATCH" if present else "MISSING",
                        "meta_v2.PRODUCTIONS"))
    amended = {a["change"].split(" ")[0] for a in prereg.get("amendments", [])}
    for name in sorted(implemented - set(SPEC_PRODUCTIONS)):
        if name in amended:
            rows.append(row(f"production:{name}", "added by dated amendment",
                            "present", "MATCH",
                            "v2_preregistration.amendments"))
            continue
        rows.append(row(f"production:{name}", "not named in frozen spec",
                        "present", "MISMATCH",
                        "meta_v2.PRODUCTIONS (extra production)"))

    # -- signatures -------------------------------------------------------
    for name, production in sorted(V.PRODUCTIONS.items()):
        ok = bool(production.result_type) and isinstance(production.arg_types,
                                                         tuple)
        rows.append(row(f"signature:{name}", "typed (args, result)",
                        f"{production.arg_types} -> {production.result_type}",
                        "MATCH" if ok else "MISMATCH", "meta_v2.Production"))

    # -- enumerable vs induced -------------------------------------------
    for slot_type in SPEC_INDUCED_TYPES:
        is_induced = slot_type in V.INDUCED_TYPES
        is_terminal = any(slot_type in key for key in V.TERMINAL_VOCAB)
        enum_key = {"Transform": getattr(V, "TRANSFORM_EXPR", None),
                    "Anchor": getattr(V, "ANCHOR_EXPR", None)}.get(slot_type)
        if enum_key and enum_key in V.TERMINAL_VOCAB:
            rows.append(row(f"induced_type:{slot_type}",
                            "induced (fitted by a learner)",
                            f"enumerable terminal {enum_key}", "MISMATCH",
                            "meta_v2.TERMINAL_VOCAB"))
        elif is_induced:
            rows.append(row(f"induced_type:{slot_type}", "induced",
                            "induced", "MATCH", "meta_v2.INDUCED_TYPES"))
        else:
            rows.append(row(f"induced_type:{slot_type}", "induced", "absent",
                            "MISSING", "meta_v2.INDUCED_TYPES"))

    # -- slot learners ----------------------------------------------------
    for slot_type, conditions in prereg["slot_learners"].items():
        learner = S.SLOT_LEARNERS.get(slot_type)
        if learner is None:
            rows.append(row(f"slot_learner:{slot_type}",
                            json.dumps(conditions), "no learner registered",
                            "MISSING", "meta_search.SLOT_LEARNERS"))
            continue
        source = inspect.getsource(learner)
        # fold condition must be visible in the learner itself
        enforces_fold = ("len(seen" in source and ">= 2" in source) or \
                        ("fold" in source and "return None" in source)
        rows.append(row(f"slot_learner:{slot_type}", json.dumps(conditions),
                        f"{learner.__name__} (fold condition "
                        f"{'enforced' if enforces_fold else 'NOT VISIBLE'})",
                        "MATCH" if enforces_fold else "MISMATCH",
                        f"meta_search.{learner.__name__}"))

    # colour-bijection context sensitivity: the frozen spec learns the
    # mapping between a SOURCE entity and its produced instances, not
    # between identical grid coordinates
    bijection = S.SLOT_LEARNERS.get("ColourBijection")
    if bijection is not None:
        source = inspect.getsource(bijection)
        coordinate_wise = "grid_in[r, c]" in source and "grid_out[r, c]" in source
        rows.append(row("slot_learner:ColourBijection/context",
                        "source-entity to produced-instance correspondence",
                        "same-coordinate pixel comparison" if coordinate_wise
                        else "typed correspondence",
                        "MISMATCH" if coordinate_wise else "MATCH",
                        "meta_search.learn_colour_bijection"))

    # -- router -----------------------------------------------------------
    signature_source = inspect.getsource(S.failure_signature)
    for field in SPEC_ROUTER_FIELDS:
        present = f'"{field}"' in signature_source
        rows.append(row(f"router_field:{field}", "computed",
                        "computed" if present else "not computed",
                        "MATCH" if present else "MISSING",
                        "meta_search.failure_signature"))
    for name, productions in prereg["router"]["subgrammars"].items():
        got = set(S.SUBGRAMMARS.get(name, ()))
        missing = [p for p in productions if p not in got]
        rows.append(row(f"subgrammar:{name}", ",".join(productions),
                        ",".join(sorted(got)),
                        "MATCH" if not missing else "MISSING",
                        f"meta_search.SUBGRAMMARS missing {missing}"))

    # -- search parameters ------------------------------------------------
    search_prereg = prereg["search"]
    for key, attribute in (("max_ast_depth", "MAX_DEPTH"),
                           ("max_semantic_classes_per_type",
                            "MAX_SEMANTIC_CLASSES_PER_TYPE"),
                           ("max_candidates_returned", "MAX_CANDIDATES")):
        want = search_prereg[key]
        got = getattr(S, attribute)
        rows.append(row(f"search:{key}", want, got,
                        "MATCH" if want == got else "MISMATCH",
                        f"meta_search.{attribute}"))
    rows.append(row("search:ARC_META_BUDGET_S",
                    search_prereg["ARC_META_BUDGET_S"], S.budget_s(),
                    "MATCH" if S.budget_s() == search_prereg["ARC_META_BUDGET_S"]
                    else "MISMATCH", "meta_search.budget_s"))
    search_source = inspect.getsource(S.search)
    rows.append(row("search:cooperative_deadline",
                    search_prereg["cooperative_deadline"],
                    "min(parent, now+budget)" if "min(deadline, own)" in search_source
                    else "not enforced",
                    "MATCH" if "min(deadline, own)" in search_source else "MISMATCH",
                    "meta_search.search"))

    # -- enumeration ordering --------------------------------------------
    for criterion in SPEC_ORDERING:
        if criterion == "result_type":
            present = "goal_type" in search_source
        elif criterion == "ast_depth":
            present = "for depth in range" in search_source
        elif criterion == "mdl":
            present = "ast_nodes" in search_source
        elif criterion == "value_bound_count":
            present = "value_bound_count" in search_source
        elif criterion == "stable_serialization":
            present = "sort_keys=True" in search_source
        else:                                    # parameter_class
            present = "parameter_class" in search_source
        rows.append(row(f"enumeration_order:{criterion}", "applied",
                        "applied" if present else "absent",
                        "MATCH" if present else "MISSING",
                        "meta_search.search ranking key"))

    # -- semantic dedup ---------------------------------------------------
    # intermediate caching must key on (result type, behaviour) and must be
    # consulted BEFORE a candidate is fitted or extended
    caches_intermediate = ("intermediate_signature" in search_source
                           and "_result_type_of" in search_source
                           and "intermediate[cache_key]" in search_source)
    rows.append(row("semantic_dedup:intermediate_types",
                    "(type, behaviour on demonstrations) -> cheapest AST, "
                    "at intermediate nodes too",
                    "implemented" if caches_intermediate
                    else "final Grid programs only",
                    "MATCH" if caches_intermediate else "MISMATCH",
                    "meta_search.search / intermediate_signature"))
    stats_source = inspect.getsource(S.SearchStats.as_dict)
    # the misleading bare key must be gone; the rejection measure must be
    # named for what it is
    mislabelled = ('"dedup_ratio"' in stats_source
                   or "candidate_rejection_ratio" not in stats_source)
    rows.append(row("semantic_dedup:reported_metric",
                    "equivalent programs eliminated, named honestly",
                    "bare dedup_ratio over rejected candidates" if mislabelled
                    else "candidate_rejection_ratio + intermediate_dedup_ratio",
                    "MISMATCH" if mislabelled else "MATCH",
                    "meta_search.SearchStats.as_dict"))

    # -- serialization ----------------------------------------------------
    ast = ("Paint", (("Colourise", (("Partition", ("background_components",)),
                                    "is_rect", ((True, 3), (False, 4)))),))
    round_trips = V.from_json(json.loads(json.dumps(V.to_json(ast)))) == ast
    rows.append(row("serialization:ast_round_trip", "exact",
                    "exact" if round_trips else "lossy",
                    "MATCH" if round_trips else "MISMATCH",
                    "meta_v2.to_json/from_json"))
    return rows


def main():
    rows = audit()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v2_conformance_audit.json").write_text(json.dumps(rows, indent=1))
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"{'STATUS':10} {'REQUIREMENT':52} IMPLEMENTED")
    for r in rows:
        if r["status"] != "MATCH":
            print(f"{r['status']:10} {r['requirement'][:52]:52} "
                  f"{str(r['implemented'])[:60]}")
    print(f"\ntotals: {counts}")
    print(f"conformant: {counts.get('MATCH', 0)}/{len(rows)}")


if __name__ == "__main__":
    main()
