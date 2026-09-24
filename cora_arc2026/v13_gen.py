"""Core machinery for the frozen v1.3 contrastive corpus.

Thin orchestration around existing components. It creates no new failure
graph, observer, executor, fitter, grammar, AST representation, verifier,
reasoner or proposer.

Reused unchanged:
  constructive_vocabulary   grammar, legality, canonical form, families
  constructive_dataset      target sampling
  constructive_v2_dataset   the admission law, R1 to R11, with the fairness guard
  scoped_slot_fitting       the registered occurrence-scoped fitter
  engine_trace              the repaired full-engine observer and compatibility repair
  leak_scan_v12             the hardened scanner, extended to v1.3 metadata

Protocol: docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL_v1.3.md
sha256 66aa1c561ac4fd2a619459f15919282776a5898ab3ae6f36ae6944a5389d8f1e
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
for _p in (TTI, HERE):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from cora_tti import constructive_dataset as CD                   # noqa: E402
from cora_tti import constructive_v2_dataset as V2                # noqa: E402
from cora_tti import constructive_vocabulary as CV                # noqa: E402
from cora_arc2026 import engine_trace as ET                       # noqa: E402

MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "constructive_protocol_v1.3_manifest.json")

#: v1.2 episode rejection codes, reused unchanged
R_BASELINE = "BASELINE_SOLVED"
R_NO_TFG = "NO_INFORMATIVE_TFG"
R_NOT_FIT = "TARGET_NOT_FITTABLE"
R_UNDEF = "TARGET_EXECUTION_UNDEFINED"
R_WITNESS = "WITNESS_NOT_SEPARATED"
R_TIMEOUT = "TIMEOUT"
R_OTHER = "OTHER_FROZEN_CODE"
#: v1.3 group rejection codes
R_DEMO = "DEMO_NOT_MATCHED"
R_REPLICATE = "REPLICATE_NOT_ADMITTED"
R_CONTRAST_ILLEGAL = "CONTRAST_TARGET_ILLEGAL"

CODE_MAP = {
    "base_search_solved": R_BASELINE, "baseline_shape_fit": R_BASELINE,
    "execution_undefined": R_UNDEF, "trivial_output": R_UNDEF,
    "witness_not_separated": R_WITNESS,
    "scoped_fit_failed": R_NOT_FIT, "slot_unobservable": R_NOT_FIT,
    "slot_key_unobserved": R_NOT_FIT, "slot_nonfunctional": R_NOT_FIT,
    "region_colour_conflict": R_NOT_FIT, "final_execution_mismatch": R_NOT_FIT,
    "generation_timeout": R_TIMEOUT,
}

DEMO_FEATURES = ("n_demonstrations", "mean_cells_changed",
                 "mean_fraction_changed", "same_shape_all",
                 "palette_introduced_mean", "palette_removed_mean")


def manifest() -> dict:
    with open(MANIFEST) as handle:
        return json.load(handle)


def parse_family(text) -> tuple:
    return tuple(int(c) for c in text.strip("()").rstrip(",").split(",")
                 if c.strip())


# --------------------------------------------------------------------------
# the eighteen-feature model view, unchanged from v1.2
# --------------------------------------------------------------------------

def features_v12(tfg) -> dict:
    nodes = list(tfg.nodes())
    kind: dict = {}
    for node in nodes:
        kind.setdefault(node.kind, []).append(node)
    delta = kind.get("delta_signature", [])
    palette = kind.get("palette_change", [])
    shape = kind.get("shape_change", [])
    frontier = kind.get("frontier_term", [])
    vsig = [n for n in kind.get("value_signature", []) if n.attrs.get("defined")]
    execution = kind.get("execution", [])
    attrs = execution[0].attrs if execution else {}
    census = attrs.get("outcome_census", {}) if isinstance(attrs, dict) else {}

    def mean(values):
        values = [v for v in values if v is not None]
        return round(float(sum(values) / len(values)), 5) if values else 0.0

    outcomes = [n.attrs.get("outcome") for n in frontier]
    return {
        "n_demonstrations": len(delta),
        "mean_cells_changed": mean([n.attrs.get("cells_changed") for n in shape]),
        "mean_fraction_changed": mean([n.attrs.get("fraction_changed") for n in shape]),
        "same_shape_all": all(bool(n.attrs.get("same_shape")) for n in delta)
        if delta else False,
        "palette_introduced_mean": mean([n.attrs.get("introduced") for n in palette]),
        "palette_removed_mean": mean([n.attrs.get("removed") for n in palette]),
        "frontier_term_count": len(frontier),
        "distinct_frontier_operator_count": len({n.attrs.get("op") for n in frontier}),
        "slot_fit_failed_count": int(census.get(
            "slot_fit_failed", sum(1 for o in outcomes if o == "slot_fit_failed"))),
        "slot_fit_ok_count": int(census.get("slot_fit_ok", 0)),
        "executed_not_exact_count": int(census.get(
            "executed_not_exact", sum(1 for o in outcomes if o == "executed_not_exact"))),
        "exact_count": int(census.get("exact", 0)),
        "defined_value_signature_count": len(vsig),
        "fraction_wrong_mean": mean([n.attrs.get("fraction_wrong") for n in vsig]),
        "palette_extra_mean": mean([n.attrs.get("palette_extra") for n in vsig]),
        "shape_mismatch_count": sum(1 for n in vsig
                                    if not n.attrs.get("shape_matches")),
        "empty_frontier": not frontier,
        "search_deadline_hit": bool(attrs.get("deadline_hit", False))
        if isinstance(attrs, dict) else False,
    }


def informative(features, gate) -> bool:
    if features["frontier_term_count"] < int(gate["require"].split(">=")[1]):
        return False
    return (features["defined_value_signature_count"] >= 1
            or features["executed_not_exact_count"] >= 1
            or features["slot_fit_failed_count"] >= 1)


# --------------------------------------------------------------------------
# the 42-field target-independent frontier descriptor, as executed in the
# v1.2 diagnosis
# --------------------------------------------------------------------------

def raw_descriptor(tfg_json) -> dict:
    out = {f"op_bucket_{i}": 0 for i in range(16)}
    outcomes: dict = {}
    surfaces, cells, fracs, extras = [], [], [], []
    ops = set()
    shape_mismatch = defined = 0
    execution: dict = {}
    for node in tfg_json.get("nodes", []):
        kind, attrs = node.get("kind"), node.get("attrs", {})
        if kind == "frontier_term":
            op = str(attrs.get("op", ""))
            out[f"op_bucket_{int(hashlib.sha1(op.encode()).hexdigest(), 16) % 16}"] += 1
            outcomes[str(attrs.get("outcome"))] = \
                outcomes.get(str(attrs.get("outcome")), 0) + 1
            surfaces.append(float(attrs.get("surface_nodes", 0)))
            ops.add(op)
        elif kind == "value_signature" and attrs.get("defined"):
            defined += 1
            for seq, key in ((cells, "cells_wrong"), (fracs, "fraction_wrong"),
                             (extras, "palette_extra")):
                if attrs.get(key) is not None:
                    seq.append(float(attrs[key]))
            if not attrs.get("shape_matches"):
                shape_mismatch += 1
        elif kind == "execution":
            execution = attrs
    for name in ("typecheck_failed", "typed", "slot_fit_failed", "slot_fit_ok",
                 "executed_not_exact", "exact"):
        out[f"outcome_{name}"] = outcomes.get(name, 0)
    for label, seq in (("surface", surfaces), ("cells_wrong", cells),
                       ("fraction_wrong", fracs), ("palette_extra", extras)):
        out[f"{label}_min"] = min(seq) if seq else 0.0
        out[f"{label}_mean"] = (sum(seq) / len(seq)) if seq else 0.0
        out[f"{label}_max"] = max(seq) if seq else 0.0
    out["distinct_ops"] = len(ops)
    out["defined_signatures"] = defined
    out["shape_mismatch"] = shape_mismatch
    for key in ("typed", "generated", "rejected", "max_depth", "semantic_classes"):
        out[f"exec_{key}"] = float(execution.get(key, 0) or 0)
    return out


DESCRIPTOR_ORDER = tuple(sorted(raw_descriptor({"nodes": []})))


# --------------------------------------------------------------------------
# one episode, admission law unchanged from v1.2
# --------------------------------------------------------------------------

def make_episode(schema, seed, budgets, gate, label):
    """Return (code, episode dict or None). 'ADMITTED' means all gates passed."""
    family = CV.family(schema)
    try:
        outcome, episode, _evidence = V2.evaluate_target_v2(
            schema, seed=seed, split="train", regime="train_pool",
            allowed_families=[family], seen_digests=set(),
            seen_train_digests=set(), v1_exclusion=set(),
            budgets=budgets, row_index=0)
    except Exception as exc:                                      # noqa: BLE001
        return f"{R_OTHER}:{type(exc).__name__}", None
    if outcome != "ADMITTED":
        return CODE_MAP.get(outcome, R_OTHER), None

    pairs = [(d["input"], d["output"]) for d in episode["demonstrations"]]
    got = ET.extract(label, pairs,
                     budget_s=budgets["full_engine_observation_s"])
    if got["solved"]:
        return R_NO_TFG, None
    features = features_v12(got["tfg"])
    if not informative(features, gate):
        return R_NO_TFG, None
    tfg_json = got["tfg"].to_json()
    return "ADMITTED", {
        "target_digest": episode["target_digest"],
        "target_tokens": episode["target_tokens"],
        "structural_family": episode.get("structural_family"),
        "family_text": CV.family_text(family),
        "seed": seed,
        "model_view": {"features": features, "input_type": "Grid",
                       "output_type": "Grid"},
        "full_engine_tfg": tfg_json,
        "descriptor": raw_descriptor(tfg_json),
        "base_search_evidence": episode.get("base_search_evidence"),
        "fitter_identity": episode.get("fitter_identity"),
    }


# --------------------------------------------------------------------------
# contrast construction, from the frozen grammar only
# --------------------------------------------------------------------------

def contrast_target(anchor, contrast_type, rotation=0):
    """The contrast target, differing in exactly one grammar position."""
    v = CV.vocab()
    blocks = CV.blocks_from_ast(anchor)
    partition, selects, feature = blocks[0]
    if contrast_type == "PARTITION":
        options = [p for p in v["partitions"] if p != partition]
        new = (options[rotation % len(options)], selects, feature)
    elif contrast_type == "FEATURE":
        options = [f for f in v["key_features"] if f != feature]
        new = (partition, selects, options[rotation % len(options)])
    elif contrast_type == "SELECT":
        if len(selects) >= v["max_selects"]:
            return None
        options = list(v["predicates"])
        new = (partition, tuple(selects) + (options[rotation % len(options)],),
               feature)
    else:
        raise ValueError(contrast_type)
    ast = CV.ast_from_blocks([new] + blocks[1:])
    ok, _code = CV.validate(ast)
    if not ok:
        return None
    fam = CV.family(ast)
    if CV.is_banned_target_family(fam) or CV.is_holdout_family(fam):
        return None
    if CV.digest(ast) == CV.digest(anchor):
        return None
    return ast


def group_digest(digest_a, digest_b) -> str:
    return hashlib.sha256("|".join(sorted([digest_a, digest_b])).encode()).hexdigest()
