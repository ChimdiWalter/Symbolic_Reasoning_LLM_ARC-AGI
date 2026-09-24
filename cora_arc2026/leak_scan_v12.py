"""v1.2 model-view leak scan.

The v1.1 scanner validates against the twelve-entry v1.1 allowlist and would
reject every v1.2 view, so this is the v1.2 equivalent, not a second scanner
for the same contract.
"""
from __future__ import annotations

import json

VIEW_KEYS = {"features", "input_type", "output_type"}

FEATURES = {
    "n_demonstrations", "mean_cells_changed", "mean_fraction_changed",
    "same_shape_all", "palette_introduced_mean", "palette_removed_mean",
    "frontier_term_count", "distinct_frontier_operator_count",
    "slot_fit_failed_count", "slot_fit_ok_count", "executed_not_exact_count",
    "exact_count", "defined_value_signature_count", "fraction_wrong_mean",
    "palette_extra_mean", "shape_mismatch_count", "empty_frontier",
    "search_deadline_hit",
}


def scan(view: dict, episode: dict) -> list:
    """Return leak findings; an empty list means clean."""
    findings = []
    extra = set(view) - VIEW_KEYS
    if extra:
        findings.append(f"undeclared_view_field:{sorted(extra)}")
    feat_extra = set(view.get("features", {})) - FEATURES
    if feat_extra:
        findings.append(f"undeclared_feature:{sorted(feat_extra)}")
    missing = FEATURES - set(view.get("features", {}))
    if missing:
        findings.append(f"missing_feature:{sorted(missing)}")

    blob = json.dumps(view, sort_keys=True, default=str)
    forbidden = {
        "target_digest": episode.get("target_digest"),
        "episode_id": episode.get("episode_id"),
        "structural_family": episode.get("structural_family"),
        "requested_family": episode.get("requested_family"),
        "seed": episode.get("seed"),
        "target_tokens": episode.get("target_tokens"),
        "split": episode.get("split"),
        "regime": episode.get("regime"),
    }
    for name, value in forbidden.items():
        if value is None:
            continue
        text = json.dumps(value, sort_keys=True, default=str).strip('"')
        if text and len(text) > 3 and text in blob:
            findings.append(f"leaked:{name}")
    return findings
