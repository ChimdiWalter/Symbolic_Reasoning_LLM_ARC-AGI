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

    #  value-level scan. The earlier substring test could pass a leak: a
    #  feature holding the integer value of a digest prefix, or a token name,
    #  was invisible because list-valued fields serialize whole and short
    #  strings were skipped. Compare against every leaf instead.
    def leaves(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from leaves(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from leaves(item)
        else:
            yield value

    features = view.get("features", {})
    for name, value in features.items():
        if not isinstance(value, (int, float, bool)):
            findings.append(f"non_numeric_feature:{name}")

    view_leaves = {str(v) for v in leaves(view)}
    digest = str(episode.get("target_digest") or "")
    for width in (8, 12, 16, len(digest)):
        if width and digest[:width] and digest[:width] in view_leaves:
            findings.append("leaked:target_digest_prefix")
            break
    try:
        digest_int = int(digest[:8], 16) if digest else None
    except ValueError:
        digest_int = None
    if digest_int is not None and any(
            isinstance(v, (int, float)) and not isinstance(v, bool)
            and float(v) == float(digest_int) for v in leaves(view)):
        findings.append("leaked:target_digest_as_number")

    #  Strings are compared exactly against string leaves, which catches a
    #  token name or a split label echoed into the view. Numbers are compared
    #  only when large enough to be discriminative: a structural family is a
    #  list of small integers, and an integer 0 collides with a legitimate
    #  feature value, so matching those leaf by leaf reports noise, not leaks.
    DISCRIMINATIVE_MIN = 1000
    view_strings = {v for v in leaves(view) if isinstance(v, str)}
    view_numbers = {float(v) for v in leaves(view)
                    if isinstance(v, (int, float)) and not isinstance(v, bool)}

    def flag(name, value):
        for leaf in leaves(value):
            if isinstance(leaf, str) and leaf in view_strings:
                findings.append(f"leaked:{name}")
                return
            if (isinstance(leaf, (int, float)) and not isinstance(leaf, bool)
                    and abs(float(leaf)) >= DISCRIMINATIVE_MIN):
                #  a numeric value can also be echoed as text, so check both
                forms = {float(leaf)}
                texts = {str(leaf), str(int(leaf))} if float(leaf).is_integer() \
                    else {str(leaf)}
                if (forms & view_numbers) or (texts & view_strings):
                    findings.append(f"leaked:{name}")
                    return

    #  extended for v1.3 contrastive metadata, per protocol v1.3 section 15
    for name in ("episode_id", "structural_family", "requested_family",
                 "seed", "split", "regime",
                 "group_id", "contrast_type", "replicate_index",
                 "differing_position", "pair_digest"):
        if episode.get(name) is not None:
            flag(name, episode[name])
    if episode.get("target_tokens"):
        flag("target_token", episode["target_tokens"])
    return findings
