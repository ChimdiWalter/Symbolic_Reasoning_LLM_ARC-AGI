"""Generate the frozen Item-2 v1.2 constructive corpus.

Implements the law in docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL_v1.2.md
(sha256 31a74764...) and its manifest, with erratum 1. Nothing here decides
anything: every family, slot count, seed, budget and gate is read from the
frozen manifest.

Admission uses the already-frozen v2 evaluator, which carries the
occurrence-scoped fitter and the fairness guard. This script adds only what
v1.2 changes: the failure graph comes from the repaired full-engine path on
the same demonstrations, and the informative-evidence gate is applied to it.

No training, no compiling, no scoring, no ARC data, no holdout.
"""
import json
import os
import sys
import time

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
                        "constructive_protocol_v1.2_manifest.json")
OUT = os.path.join(HERE, "outputs", "tti", "v12_corpus")

#: v1.2 rejection codes, frozen
R_BASELINE = "BASELINE_SOLVED"
R_NO_TFG = "NO_INFORMATIVE_TFG"
R_NOT_FIT = "TARGET_NOT_FITTABLE"
R_UNDEF = "TARGET_EXECUTION_UNDEFINED"
R_WITNESS = "WITNESS_NOT_SEPARATED"
R_INFEASIBLE = "STRUCTURALLY_INFEASIBLE_FAMILY"
R_TIMEOUT = "TIMEOUT"
R_OTHER = "OTHER_FROZEN_CODE"

#: v2 terminal outcome -> v1.2 code
CODE_MAP = {
    "base_search_solved": R_BASELINE, "baseline_shape_fit": R_BASELINE,
    "execution_undefined": R_UNDEF, "trivial_output": R_UNDEF,
    "witness_not_separated": R_WITNESS,
    "scoped_fit_failed": R_NOT_FIT, "slot_unobservable": R_NOT_FIT,
    "slot_key_unobserved": R_NOT_FIT, "slot_nonfunctional": R_NOT_FIT,
    "region_colour_conflict": R_NOT_FIT, "final_execution_mismatch": R_NOT_FIT,
    "generation_timeout": R_TIMEOUT,
}


def manifest():
    with open(MANIFEST) as handle:
        return json.load(handle)


def parse_family(text):
    return tuple(int(c) for c in text.strip("()").rstrip(",").split(",")
                 if c.strip())


def schedule(man):
    """The frozen deterministic slot schedule."""
    slots, index = [], 0
    train = [parse_family(f) for f in man["train_families"]]
    hold = [parse_family(f) for f in man["structural_holdout_families"]]
    s = man["slots"]
    seeds = man["seeds"]
    for family in train:
        for _ in range(s["train_per_family"]):
            slots.append({"slot": index, "split": "train",
                          "regime": "train_pool", "family": family,
                          "seed_base": seeds["train_from"] + index * 25})
            index += 1
    for family in train:
        for _ in range(s["val_per_family"]):
            slots.append({"slot": index, "split": "val",
                          "regime": "train_pool", "family": family,
                          "seed_base": seeds["val_from"] + index * 25})
            index += 1
    for family in hold:
        for _ in range(s["holdout_per_family"]):
            slots.append({"slot": index, "split": "test",
                          "regime": "structural_holdout", "family": family,
                          "seed_base": seeds["holdout_from"] + index * 25})
            index += 1
    return slots


def features_v12(tfg) -> dict:
    """The eighteen allowlisted features, all from the failure graph."""
    nodes = list(tfg.nodes())
    kind = {}
    for node in nodes:
        kind.setdefault(node.kind, []).append(node)
    delta = kind.get("delta_signature", [])
    palette = kind.get("palette_change", [])
    shape = kind.get("shape_change", [])
    frontier = kind.get("frontier_term", [])
    vsig = [n for n in kind.get("value_signature", []) if n.attrs.get("defined")]
    execution = kind.get("execution", [{}])

    def mean(values):
        values = [v for v in values if v is not None]
        return round(float(sum(values) / len(values)), 5) if values else 0.0

    outcomes = [n.attrs.get("outcome") for n in frontier]
    exec_attrs = execution[0].attrs if execution and hasattr(execution[0], "attrs") else {}
    census = exec_attrs.get("outcome_census", {}) if isinstance(exec_attrs, dict) else {}
    return {
        "n_demonstrations": len(delta),
        "mean_cells_changed": mean([n.attrs.get("cells_changed") for n in shape]),
        "mean_fraction_changed": mean([n.attrs.get("fraction_changed") for n in shape]),
        "same_shape_all": all(bool(n.attrs.get("same_shape")) for n in delta) if delta else False,
        "palette_introduced_mean": mean([n.attrs.get("introduced") for n in palette]),
        "palette_removed_mean": mean([n.attrs.get("removed") for n in palette]),
        "frontier_term_count": len(frontier),
        "distinct_frontier_operator_count": len({n.attrs.get("op") for n in frontier}),
        "slot_fit_failed_count": int(census.get("slot_fit_failed",
                                                sum(1 for o in outcomes if o == "slot_fit_failed"))),
        "slot_fit_ok_count": int(census.get("slot_fit_ok", 0)),
        "executed_not_exact_count": int(census.get("executed_not_exact",
                                                   sum(1 for o in outcomes if o == "executed_not_exact"))),
        "exact_count": int(census.get("exact", 0)),
        "defined_value_signature_count": len(vsig),
        "fraction_wrong_mean": mean([n.attrs.get("fraction_wrong") for n in vsig]),
        "palette_extra_mean": mean([n.attrs.get("palette_extra") for n in vsig]),
        "shape_mismatch_count": sum(1 for n in vsig if not n.attrs.get("shape_matches")),
        "empty_frontier": not frontier,
        "search_deadline_hit": bool(exec_attrs.get("deadline_hit", False)) if isinstance(exec_attrs, dict) else False,
    }


def informative(features, gate) -> bool:
    if features["frontier_term_count"] < 2:
        return False
    return (features["defined_value_signature_count"] >= 1
            or features["executed_not_exact_count"] >= 1
            or features["slot_fit_failed_count"] >= 1)


def run():
    man = manifest()
    gate = man["informative_tfg_gate"]
    budgets = man["budgets"]
    train_families = [parse_family(f) for f in man["train_families"]]
    hold_families = [parse_family(f) for f in man["structural_holdout_families"]]
    cap = man["slots"]["attempts_per_slot_cap"]
    os.makedirs(OUT, exist_ok=True)

    slots = schedule(man)
    seen_digests, seen_train_digests = set(), set()
    #  v1.1 admitted nothing, so there is no v1 target to exclude
    v1_exclusion = set()

    #  resume from any already-written slot files
    for row in slots:
        path = os.path.join(OUT, f"slot{row['slot']:04d}.json")
        if os.path.exists(path):
            with open(path) as handle:
                done = json.load(handle)
            if done.get("admitted") and done.get("episode"):
                digest = done["episode"]["target_digest"]
                seen_digests.add(digest)
                if done["split"] == "train":
                    seen_train_digests.add(digest)

    started = time.monotonic()
    for row in slots:
        path = os.path.join(OUT, f"slot{row['slot']:04d}.json")
        if os.path.exists(path):
            continue
        allowed = [row["family"]]
        slot_started = time.monotonic()
        outcomes, admitted, episode_out, attempts_used = {}, False, None, 0
        for attempt in range(cap):
            attempts_used = attempt + 1
            seed = row["seed_base"] + attempt
            schema = CD.sample_target(seed, row["family"])
            try:
                outcome, episode, evidence = V2.evaluate_target_v2(
                    schema, seed=seed, split=row["split"],
                    regime=row["regime"], allowed_families=allowed,
                    seen_digests=seen_digests,
                    seen_train_digests=seen_train_digests,
                    v1_exclusion=v1_exclusion, budgets=budgets,
                    row_index=row["slot"])
            except Exception as exc:  # noqa: BLE001
                outcome, episode = R_OTHER, None
                outcomes[f"error:{type(exc).__name__}"] = \
                    outcomes.get(f"error:{type(exc).__name__}", 0) + 1
                continue
            code = CODE_MAP.get(outcome, R_OTHER if outcome != "ADMITTED" else "ADMITTED")
            if outcome != "ADMITTED":
                outcomes[code] = outcomes.get(code, 0) + 1
                continue

            #  v1.2 change: the failure graph comes from the deployed reasoner
            pairs = [(d["input"], d["output"]) for d in episode["demonstrations"]]
            got = ET.extract(f"v12-{row['slot']:04d}-{attempt}", pairs,
                             budget_s=budgets["full_engine_observation_s"])
            if got["solved"]:
                outcomes[R_NO_TFG] = outcomes.get(R_NO_TFG, 0) + 1
                continue
            features = features_v12(got["tfg"])
            if not informative(features, gate):
                outcomes[R_NO_TFG] = outcomes.get(R_NO_TFG, 0) + 1
                continue

            digest = episode["target_digest"]
            seen_digests.add(digest)
            if row["split"] == "train":
                seen_train_digests.add(digest)
            episode_out = {
                "episode_id": f"v12-{row['split']}-{row['slot']:04d}",
                "split": row["split"], "regime": row["regime"],
                "requested_family": list(row["family"]),
                "structural_family": episode.get("structural_family"),
                "target_tokens": episode["target_tokens"],
                "target_digest": digest,
                "target_schema_json": episode["target_schema_json"],
                "interface": ["Set[Region]", "Grid"],
                "seed": seed,
                "model_view": {"features": features,
                               "input_type": "Grid", "output_type": "Grid"},
                "full_engine_tfg": got["tfg"].to_json(),
                "full_engine_census": got["census"],
                "base_search_evidence": episode.get("base_search_evidence"),
                "fitter_identity": episode.get("fitter_identity"),
            }
            admitted = True
            outcomes["ADMITTED"] = outcomes.get("ADMITTED", 0) + 1
            break

        record = {"slot": row["slot"], "split": row["split"],
                  "regime": row["regime"],
                  "requested_family": list(row["family"]),
                  "admitted": admitted, "episode": episode_out,
                  "attempts_used": attempts_used, "max_attempts": cap,
                  "outcome_counts": outcomes,
                  "elapsed_s": round(time.monotonic() - slot_started, 2),
                  "protocol_sha256": man["protocol_doc_sha256"]}
        with open(path, "w") as handle:
            json.dump(record, handle, default=str)
        print(f"slot {row['slot']:04d} {row['split']:5s} "
              f"{CV.family_text(row['family']):8s} "
              f"admitted={admitted} attempts={attempts_used} "
              f"{record['elapsed_s']}s  total={round(time.monotonic()-started,1)}s",
              flush=True)


if __name__ == "__main__":
    run()
