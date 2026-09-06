"""Protocol v2c: the corrected evidence path for the occurrence-scoped census.

Additive to v1.1 (constructive_dataset, immutable) and to v2
(constructive_v2_dataset, retained so the original census stays
re-executable from its pinned snapshot). The semantic constructor inventory,
the scoped-fitting scientific policy, the seven structural families and the
research question are UNCHANGED. What this module corrects is the evidence
path, each item documented before launch in
docs/CORA_TTI_V2C_PRELAUNCH_AMENDMENT.md:

    1. deterministic instantiation   the v1.1 concrete-table colour term used
                                     Python's per-process salted hash; v2c uses
                                     a SHA-256 term, so instantiation is a pure
                                     function of (seed, schema)
    2. persistent guards             seen / train / exclusion sets live in a
                                     CensusState the caller owns; nothing here
                                     creates a fresh guard per attempt
    3. one baseline reasoner         requirement 4, the witness-separation set
                                     and the TFG all come from
                                     meta_baseline.run_baseline under ONE
                                     configuration whose digest is recorded on
                                     the attempt and inside the TFG; a mismatch
                                     rejects the row
    4. irreducibility contract       direct and refitted ablations with the
                                     four declared outcomes; exceptions and
                                     resource exhaustion are INCONCLUSIVE, never
                                     evidence of necessity; probe coverage is
                                     recorded for every comparison
    5. explicit error outcomes       fitter or evaluator exceptions become
                                     fit_execution_error / probe_execution_error,
                                     never a scientific rejection or a pass
    6. separated units               unique schema, concrete instantiation,
                                     demonstration bundle and attempt are
                                     recorded as distinct identities
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_probes as CP                   # noqa: E402
from cora_tti import constructive_v2_dataset as V2               # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

ADMITTED = "ADMITTED"
INFRA_PREFIX = V2.INFRA_PREFIX

#: v2 vocabulary plus the explicit outcomes the corrected contract needs
REJECTION_CODES_V2C = V2.REJECTION_CODES_V2 + (
    "fit_execution_error",            # the fitter raised (target path)
    "probe_execution_error",          # the evaluator raised on a frozen probe
    "irreducibility_inconclusive",    # no ablation reproduced, but a check was incomplete
    "baseline_tfg_config_mismatch",   # failure and TFG from different configurations
    "probe_coverage_vacuous",         # target defined on fewer probes than the manifest floor
    "baseline_incomplete",            # the baseline did not finish, so "it failed" is unsupported
)

#: outcomes that report a failure OF THE CHECKER, never a scientific property of
#: the target. They are counted apart from both scientific rejections and
#: infrastructure exceptions, because a broken check must never read as evidence.
CHECKER_FAILURE_CODES = (
    "fit_execution_error", "probe_execution_error", "irreducibility_inconclusive",
    "baseline_tfg_config_mismatch", "baseline_incomplete", "generation_timeout",
)

#: the demonstration protocol; the runner passes the manifest's copy, and this
#: default exists only so the module is usable in tests without a manifest
DEFAULT_GENERATION = {
    "grid_seed_formula": "seed*97 + i",
    "candidate_grids": 14,
    "table_grids": 6,
    "min_demos": 3,
}

ABLATION_OUTCOMES = (
    "REPRODUCING_ABLATION_FOUND",
    "NO_REPRODUCING_ABLATION_FOUND_WITHIN_DECLARED_PROCEDURE",
    "INCONCLUSIVE",
    "NOT_APPLICABLE",
)


def _evaluate(ast, grid):
    return M.evaluate(ast, np.asarray(grid), MI.descriptors)


# --------------------------------------------------------------------------
# 1. deterministic instantiation (generator side; may know the target)
# --------------------------------------------------------------------------

def colour_term(index: int, value) -> int:
    """v1.1 formula with the salted hash replaced by SHA-256 of the same repr."""
    text = repr(value)
    salt_free = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) % 7
    return 1 + (index * 3 + len(text) + salt_free) % 9


def instantiate_tables(schema, grids: Sequence[np.ndarray]):
    """One functional feature -> colour table per block, derived from the
    generation grids. Pure function of (schema, grids)."""
    blocks = CV.blocks_from_ast(schema)
    concrete = schema
    for index, (partition, selects, feature) in enumerate(blocks):
        values = set()
        for grid in grids:
            builder = M.PARTITIONS.get(partition)
            if builder is None:
                return None
            sets = builder(grid)
            for predicate in selects:
                test = M.PREDICATES[predicate]
                sets = [s for s in sets if test(MI.descriptors(s, grid))]
            for cells in sets:
                value = MI.descriptors(cells, grid).get(feature)
                if value is not None:
                    values.add(value)
        if not values:
            return None
        table = tuple(sorted(((value, colour_term(index, value)) for value in values),
                             key=lambda kv: repr(kv[0])))
        concrete = M.instantiate(concrete, {f"?{index}": table})
    return concrete


def demo_bundle_digest(pairs) -> str:
    payload = json.dumps([[np.asarray(a).tolist(), np.asarray(b).tolist()] for a, b in pairs])
    return hashlib.sha256(payload.encode()).hexdigest()


# --------------------------------------------------------------------------
# 2. persistent run-wide state (owned by the caller, never recreated per attempt)
# --------------------------------------------------------------------------

@dataclass
class CensusState:
    v1_exclusion: set
    seen_digests: set = field(default_factory=set)
    seen_train_digests: set = field(default_factory=set)
    seen_concrete: set = field(default_factory=set)
    seen_demo_bundles: set = field(default_factory=set)
    attempts: int = 0

    def record(self, *, digest: str, regime: str, outcome: str,
               concrete_digest: str | None, demo_digest: str | None) -> None:
        self.attempts += 1
        if digest:
            self.seen_digests.add(digest)
        if outcome == ADMITTED and regime == "train_pool" and digest:
            self.seen_train_digests.add(digest)
        if concrete_digest:
            self.seen_concrete.add(concrete_digest)
        if demo_digest:
            self.seen_demo_bundles.add(demo_digest)

    def units(self) -> dict:
        return {"attempts": self.attempts,
                "unique_schemas": len(self.seen_digests),
                "unique_concrete_instantiations": len(self.seen_concrete),
                "unique_demonstration_bundles": len(self.seen_demo_bundles),
                "historical_exclusion_size": len(self.v1_exclusion)}


# --------------------------------------------------------------------------
# 4. irreducibility contract: direct and refitted ablations, four outcomes
# --------------------------------------------------------------------------

def _concrete_from_blocks(blocks) -> tuple:
    stages = []
    for partition, selects, feature, table in blocks:
        stages.append(("Partition", (partition,)))
        for predicate in selects:
            stages.append(("Select", (predicate,)))
        stages.append(("Map", (("Key", (feature,)), ("Lookup", (table,)))))
        stages.append(("Paint", ()))
    return ("Compose", tuple(stages))


def _ablate(blocks, ablation) -> list:
    kind = ablation[0]
    if kind == "block":
        return [b for i, b in enumerate(blocks) if i != ablation[1]]
    block_index, select_index = ablation[1], ablation[2]
    out = list(blocks)
    b = list(out[block_index])
    b[1] = tuple(s for i, s in enumerate(b[1]) if i != select_index)
    out[block_index] = tuple(b)
    return out


def _compare_program(program, pairs, target_fp: str, target_status: list) -> dict:
    """Demonstration behaviour and frozen-probe behaviour, reported separately,
    with probe coverage. Never raises."""
    result = {"demo_behaviour": None, "probe_fingerprint_equal": None,
              "defined_probes": 0, "both_defined_probes": 0, "probe_errors": 0}
    behaviour = "exact"
    for grid_in, grid_out in pairs:
        try:
            rendered = _evaluate(program, grid_in)
        except Exception as error:                                # noqa: BLE001
            result["demo_behaviour"] = "error"
            result["error"] = type(error).__name__
            return result
        if rendered is None:
            behaviour = "undefined"
            break
        if not np.array_equal(rendered, np.asarray(grid_out)):
            behaviour = "differs"
            break
    result["demo_behaviour"] = behaviour
    fingerprint, status = CP.fingerprint_with_diagnostics(program, _evaluate)
    result["probe_fingerprint_equal"] = fingerprint == target_fp
    result["defined_probes"] = sum(1 for s in status if s == "OK")
    result["both_defined_probes"] = sum(1 for s, t in zip(status, target_status)
                                        if s == "OK" and t == "OK")
    result["probe_errors"] = sum(1 for s in status if s.startswith(CP.ERROR_PREFIX))
    return result


def _reproduces(comparison: dict | None) -> bool:
    """Behavioural agreement, and never a vacuous one.

    Every program that is undefined on every frozen probe has the SAME
    all-undefined fingerprint (measured: three semantically different programs
    collide), so fingerprint equality alone is not evidence of agreement. A
    match counts only when the two programs are jointly defined on at least one
    probe. Under the frozen manifest the target already clears
    admission.min_defined_probes >= 1, so this guard is inert there; it exists so
    the criterion is correct independently of that floor."""
    if not comparison or comparison.get("probe_errors", 1) != 0:
        return False
    if comparison.get("demo_behaviour") != "exact":
        return False
    if comparison.get("probe_fingerprint_equal") is not True:
        return False
    return int(comparison.get("both_defined_probes", 0)) > 0


def _vacuous_probe_match(comparison: dict | None) -> bool:
    """Fingerprints equal only because neither program is defined anywhere."""
    return bool(comparison and comparison.get("probe_fingerprint_equal") is True
                and int(comparison.get("both_defined_probes", 0)) == 0)


def _incomplete(comparison: dict | None, refit_status: str | None = None) -> bool:
    if comparison is None:
        return True
    if comparison.get("demo_behaviour") == "error" or comparison.get("probe_errors", 0) > 0:
        return True
    return refit_status in ("EXECUTION_ERROR", "RESOURCE_EXHAUSTED")


def irreducibility_audit_v2c(schema, fitted_program, pairs, target_fp: str,
                             target_probe_status: list, deadline=None) -> dict:
    """Local structural irreducibility with an explicit evidence contract.

    For every single ablation (one block, or one Select stage):
      DIRECT    remove it from the already fitted program, keep the surviving
                bindings, compare behaviour
      REFITTED  remove it from the open schema, refit the surviving slots under
                the declared fitter, compare behaviour
    Direct reproduction establishes redundancy even if refitting fails; refitted
    reproduction also establishes redundancy. Failure of both establishes only
    that no reproducing ablation was found WITHIN THIS PROCEDURE. Errors and
    resource exhaustion are INCONCLUSIVE. Nothing here is global minimality.
    """
    open_blocks = CV.blocks_from_ast(schema)
    concrete_blocks = SF._blocks(fitted_program)
    ablations = []
    if len(open_blocks) == 1:
        ablations.append({"kind": "block", "index": None, "outcome": "NOT_APPLICABLE",
                          "reason": "single block: nothing to remove"})
    for index in range(len(open_blocks) if len(open_blocks) > 1 else 0):
        ablations.append({"kind": "block", "index": index})
    for block_index, (_p, selects, _f) in enumerate(open_blocks):
        for select_index in range(len(selects)):
            ablations.append({"kind": "select", "index": [block_index, select_index]})
    if not any(a["kind"] == "select" for a in ablations):
        ablations.append({"kind": "select", "index": None, "outcome": "NOT_APPLICABLE",
                          "reason": "no Select stage to remove"})

    counts = {k: 0 for k in ABLATION_OUTCOMES}
    for entry in ablations:
        if entry.get("outcome") == "NOT_APPLICABLE":
            counts["NOT_APPLICABLE"] += 1
            continue
        key = (entry["kind"], entry["index"]) if entry["kind"] == "block" \
            else (entry["kind"], entry["index"][0], entry["index"][1])
        started = time.monotonic()
        #  DIRECT ablation on the fitted program
        try:
            direct_program = _concrete_from_blocks(_ablate(concrete_blocks, key))
            direct = _compare_program(direct_program, pairs, target_fp, target_probe_status)
        except Exception as error:                                # noqa: BLE001
            direct = {"demo_behaviour": "error", "error": type(error).__name__,
                      "probe_errors": 1}
        #  REFITTED ablation on the open schema
        refit = {"status": None, "code": None, "comparison": None, "grammar_valid": None}
        try:
            reduced_open = CV.ast_from_blocks(_ablate(open_blocks, key))
            ok, code = CV.validate(reduced_open)
            refit["grammar_valid"] = bool(ok)
            if not ok:
                refit["status"] = "FIT_FAILURE"
                refit["code"] = f"reduced_schema_invalid:{code}"
            else:
                outcome = SF.fit_outcome(reduced_open, pairs, require_exact_replay=True,
                                         deadline=deadline)
                refit["status"], refit["code"] = outcome["status"], outcome["code"]
                if outcome["status"] == "EXACT_DEMONSTRATION_FIT":
                    refit["comparison"] = _compare_program(
                        outcome["program"], pairs, target_fp, target_probe_status)
        except Exception as error:                                # noqa: BLE001
            refit["status"] = "EXECUTION_ERROR"
            refit["code"] = type(error).__name__
        entry["direct"] = direct
        entry["refitted"] = refit
        entry["seconds"] = round(time.monotonic() - started, 3)
        #  demonstration behaviour and frozen-probe behaviour are reported
        #  separately: an ablation that replays every demonstration but differs
        #  on the probes does NOT meet the declared reducibility criterion, yet
        #  it means the demonstrations never witness the need for the removed
        #  stage. That is recorded, never silently folded into "irreducible".
        entry["vacuous_probe_match"] = bool(
            _vacuous_probe_match(direct) or _vacuous_probe_match(refit["comparison"]))
        entry["demonstrations_only_reproduced"] = bool(
            (direct.get("demo_behaviour") == "exact"
             and direct.get("probe_fingerprint_equal") is False)
            or (refit["comparison"] is not None
                and refit["comparison"].get("demo_behaviour") == "exact"
                and refit["comparison"].get("probe_fingerprint_equal") is False))
        if _reproduces(direct) or _reproduces(refit["comparison"]):
            entry["outcome"] = "REPRODUCING_ABLATION_FOUND"
            entry["reason"] = ("direct" if _reproduces(direct) else "refitted") + \
                " ablation replays every demonstration and matches the frozen-probe fingerprint"
        elif _incomplete(direct) or refit["status"] in ("EXECUTION_ERROR", "RESOURCE_EXHAUSTED") \
                or (refit["comparison"] is not None and _incomplete(refit["comparison"])):
            entry["outcome"] = "INCONCLUSIVE"
            entry["reason"] = "a check raised or ran out of resources; not evidence of necessity"
        else:
            entry["outcome"] = "NO_REPRODUCING_ABLATION_FOUND_WITHIN_DECLARED_PROCEDURE"
            entry["reason"] = (f"direct: demo={direct.get('demo_behaviour')} "
                               f"probe_equal={direct.get('probe_fingerprint_equal')}; "
                               f"refitted: {refit['status']}/{refit['code']}"
                               + (f" demo={refit['comparison'].get('demo_behaviour')} "
                                  f"probe_equal={refit['comparison'].get('probe_fingerprint_equal')}"
                                  if refit["comparison"] else ""))
        counts[entry["outcome"]] += 1
    demo_only = sum(1 for a in ablations if a.get("demonstrations_only_reproduced"))
    vacuous = sum(1 for a in ablations if a.get("vacuous_probe_match"))
    return {"ablations": ablations, "counts": counts,
            "demonstration_only_reproducing_ablations": demo_only,
            "demonstrations_do_not_witness_a_stage": demo_only > 0,
            "vacuous_probe_matches": vacuous,
            "reducible": counts["REPRODUCING_ABLATION_FOUND"] > 0,
            "inconclusive": counts["REPRODUCING_ABLATION_FOUND"] == 0
            and counts["INCONCLUSIVE"] > 0,
            "deadline_exhausted": any(
                a.get("refitted", {}).get("status") == "RESOURCE_EXHAUSTED"
                for a in ablations),
            "target_defined_probes": sum(1 for s in target_probe_status if s == "OK"),
            "probe_count": len(target_probe_status),
            "scope": "local single-ablation search; never global minimality"}


# --------------------------------------------------------------------------
# the corrected admission law
# --------------------------------------------------------------------------

def evaluate_target_v2c(schema, *, seed: int, split: str, regime: str,
                        allowed_families: Sequence[tuple], state: CensusState,
                        config: MB.BaselineConfig, budgets: Mapping[str, float],
                        row_index: int, min_defined_probes: int = 1,
                        generation: Mapping[str, object] | None = None) -> tuple:
    """Returns (outcome, episode|None, evidence). One terminal outcome per
    attempt; the state is updated for EVERY attempt that reached a digest."""
    started = time.monotonic()
    deadline = started + float(budgets["per_target_s"])
    evidence: dict = {"stage_times": {}, "fitter_identity": SF.fitter_identity(),
                      "baseline_config_digest": config.digest(),
                      "trace_config_digest": MB.trace_config_digest(config),
                      "fitter_options_target": SF.fitter_options(True),
                      "units": {}}
    digest = ""
    concrete_digest = demo_digest = None

    def stamp(name):
        evidence["stage_times"][name] = round(time.monotonic() - started, 3)

    def finish(outcome):
        state.record(digest=digest, regime=regime, outcome=outcome,
                     concrete_digest=concrete_digest, demo_digest=demo_digest)
        evidence["units"] = {"schema_digest": digest or None,
                             "concrete_digest": concrete_digest,
                             "demo_bundle_digest": demo_digest,
                             "family": CV.family_text(family) if digest else None}
        return outcome

    #  R1 grammar validity and family law
    ok, code = CV.validate(schema)
    if not ok:
        stamp("r1")
        return finish(code if code in REJECTION_CODES_V2C else "grammar_invalid"), None, evidence
    family = CV.family(schema)
    if CV.is_banned_target_family(family) or \
            tuple(family) not in {tuple(f) for f in allowed_families}:
        stamp("r1")
        return finish("split_collision"), None, evidence
    digest = CV.digest(schema)

    #  R10 historical exclusion and R9 run-wide identity (persistent state)
    if digest in state.v1_exclusion:
        stamp("r10")
        return finish("prior_v1_target_overlap"), None, evidence
    if digest in state.seen_digests:
        stamp("r9")
        return finish("duplicate_target"), None, evidence
    if regime == "ast_holdout" and digest in state.seen_train_digests:
        stamp("r9")
        return finish("split_collision"), None, evidence
    if regime == "train_pool" and CV.is_holdout_family(family):
        stamp("r9")
        return finish("split_collision"), None, evidence

    #  R2 executability and R3 nontriviality (deterministic instantiation).
    #  Every constant of the demonstration protocol comes from the manifest.
    gen = dict(DEFAULT_GENERATION, **(generation or {}))
    if gen["grid_seed_formula"] != DEFAULT_GENERATION["grid_seed_formula"]:
        raise ValueError(f"unknown grid seed formula {gen['grid_seed_formula']!r}")
    evidence["generation"] = gen
    grid_seeds = [seed * 97 + i for i in range(int(gen["candidate_grids"]))]
    concrete = instantiate_tables(schema,
                                  [CD.generate_grid(s) for s in grid_seeds[:int(gen["table_grids"])]])
    if concrete is None:
        stamp("r2")
        evidence["demo_diagnostic"] = {"undefined": "all_generation_grids", "trivial": 0}
        return finish("execution_undefined"), None, evidence
    concrete_digest = CV.digest(concrete)
    pairs, demo_diag = CD.render_demonstrations(concrete, grid_seeds,
                                                min_demos=int(gen["min_demos"]))
    evidence["demo_diagnostic"] = demo_diag
    if len(pairs) < int(gen["min_demos"]):
        stamp("r2")
        return finish("trivial_output" if demo_diag["trivial"] >= demo_diag["undefined"]
                      else "execution_undefined"), None, evidence
    demo_digest = demo_bundle_digest(pairs)
    stamp("r3")
    if time.monotonic() > deadline:
        evidence["truncated_by_wall_clock"] = "after_r3"
        return finish("generation_timeout"), None, evidence

    #  R5 occurrence-scoped recoverability with exact replay (strict options)
    fit = SF.fit_outcome(schema, pairs, require_exact_replay=True, deadline=deadline)
    evidence["scoped_fit"] = {"status": fit["status"], "code": fit["code"],
                              "detail": fit["detail"],
                              "slots": fit["evidence"].get("slots", {})}
    stamp("r5")
    if fit["status"] == "EXECUTION_ERROR":
        return finish("fit_execution_error"), None, evidence
    if fit["status"] == "RESOURCE_EXHAUSTED":
        evidence["truncated_by_wall_clock"] = "before_r5"
        return finish("generation_timeout"), None, evidence
    if fit["status"] != "EXACT_DEMONSTRATION_FIT":
        code = fit["code"] or "scoped_fit_failed"
        return finish(code if code in REJECTION_CODES_V2C else "scoped_fit_failed"), None, evidence
    fitted_target = fit["program"]

    #  R4 / R6 the ONE baseline reasoner (fixed work limit)
    trace = MB.run_baseline(pairs, config)
    evidence["baseline"] = trace.summary()
    evidence["fitter_options_baseline"] = {"strict": dict(config.strict_options),
                                           "inspection": dict(config.inspection_options)}
    stamp("r4")
    if trace.fitter_identity != SF.fitter_identity() or trace.config_digest != config.digest():
        return finish("baseline_tfg_config_mismatch"), None, evidence
    if trace.exact:
        return finish("base_search_solved"), None, evidence
    #  "the baseline failed" is a claim about a search that RAN. A truncated,
    #  errored or partially judged baseline cannot support it, so the attempt is
    #  rejected as a checker failure rather than admitted on absent evidence.
    if not trace.complete():
        evidence["baseline_incompleteness"] = trace.incompleteness_reasons()
        return finish("baseline_incomplete"), None, evidence
    if time.monotonic() > deadline:
        evidence["truncated_by_wall_clock"] = "after_r4"
        return finish("generation_timeout"), None, evidence

    #  R7 frozen-probe witness separation, with coverage accounting
    if time.monotonic() > deadline:
        evidence["truncated_by_wall_clock"] = "before_r7"
        stamp("r7")
        return finish("generation_timeout"), None, evidence
    target_fp, target_status = CP.fingerprint_with_diagnostics(fitted_target, _evaluate)
    target_defined = sum(1 for s in target_status if s == "OK")
    evidence["probe_coverage"] = {"target_defined_probes": target_defined,
                                  "probe_count": len(target_status),
                                  "target_probe_errors": sum(
                                      1 for s in target_status if s.startswith(CP.ERROR_PREFIX))}
    if evidence["probe_coverage"]["target_probe_errors"]:
        stamp("r7")
        return finish("probe_execution_error"), None, evidence
    if target_defined < int(min_defined_probes):
        stamp("r7")
        return finish("probe_coverage_vacuous"), None, evidence
    equivalent, comparison_errors, both_defined = 0, 0, []
    vacuous_matches = 0
    for _schema_b, program_b, _signature in trace.constraint_consistent:
        fp_b, status_b = CP.fingerprint_with_diagnostics(program_b, _evaluate)
        if any(s.startswith(CP.ERROR_PREFIX) for s in status_b):
            comparison_errors += 1
            continue
        joint = sum(1 for s, t in zip(status_b, target_status) if s == "OK" and t == "OK")
        both_defined.append(joint)
        if fp_b == target_fp:
            #  an all-undefined collision is not behavioural equivalence
            if joint > 0:
                equivalent += 1
            else:
                vacuous_matches += 1
    evidence["witness_separation"] = {
        "constraint_consistent_baselines": len(trace.constraint_consistent),
        "comparison_set_empty": len(trace.constraint_consistent) == 0,
        "witness_equivalent": equivalent, "comparison_errors": comparison_errors,
        "vacuous_fingerprint_matches": vacuous_matches,
        "both_defined_probes_min": min(both_defined) if both_defined else None,
        "both_defined_probes_max": max(both_defined) if both_defined else None,
        "note": ("separation established against this set only; an empty set means the "
                 "requirement was satisfied with nothing to compare against")}
    stamp("r7")
    if equivalent:
        return finish("witness_not_separated"), None, evidence
    if comparison_errors:
        return finish("probe_execution_error"), None, evidence

    #  R8 local irreducibility under the explicit contract
    audit = irreducibility_audit_v2c(schema, fitted_target, pairs, target_fp,
                                     target_status, deadline=deadline)
    evidence["irreducibility"] = {
        "counts": audit["counts"], "reducible": audit["reducible"],
        "inconclusive": audit["inconclusive"],
        "deadline_exhausted": audit["deadline_exhausted"],
        "demonstration_only_reproducing_ablations":
            audit["demonstration_only_reproducing_ablations"]}
    if audit["deadline_exhausted"]:
        evidence["truncated_by_wall_clock"] = "during_r8"
    stamp("r8")
    if audit["reducible"]:
        kinds = {a["kind"] for a in audit["ablations"]
                 if a.get("outcome") == "REPRODUCING_ABLATION_FOUND"}
        return finish("locally_reducible_block" if "block" in kinds
                      else "locally_reducible_select"), None, evidence
    if audit["inconclusive"]:
        return finish("irreducibility_inconclusive"), None, evidence

    #  TFG from the SAME baseline trace and configuration
    tfg = MB.tfg_from_trace(pairs, trace, config)
    carried = MB.tfg_configuration(tfg)
    if carried["baseline_config"] != config.digest() or \
            carried["trace_config"] != MB.trace_config_digest(config):
        stamp("tfg")
        return finish("baseline_tfg_config_mismatch"), None, evidence
    stamp("tfg")

    episode = {
        "episode_id": f"v2c-{split}-{CV.family_text(family)}-{row_index:04d}",
        "split": split, "regime": regime, "generation_seed": seed,
        "units": {"schema_digest": digest, "concrete_digest": concrete_digest,
                  "demo_bundle_digest": demo_digest, "attempt_index": row_index,
                  "family": CV.family_text(family)},
        "demonstrations": [{"input": a.tolist(), "output": b.tolist()} for a, b in pairs],
        "target_schema_json": M.ast_to_json(schema),
        "target_concrete_json": M.ast_to_json(concrete),
        "target_fitted_json": M.ast_to_json(fitted_target),
        "target_tokens": [list(t) for t in CV.tokens_from_ast(schema)],
        "target_digest": digest,
        "structural_family": list(family),
        "block_count": CV.block_count(schema), "stage_count": CV.stage_count(schema),
        "node_count": CV.mdl(schema), "schema_mdl": CV.mdl(schema),
        "slot_declarations": M.free_slot_types(schema),
        "slot_occurrences": [
            {"slot": o.slot_name, "block_index": o.block_index, "ast_path": list(o.ast_path),
             "local_prefix": [o.local_prefix[0], list(o.local_prefix[1])],
             "key_expression": o.local_key_expression} for o in SF.occurrences(schema)],
        "tfg": tfg.to_json(), "tfg_digest": tfg.digest(),
        "baseline_config": config.to_json(),
        "baseline_config_digest": config.digest(),
        "trace_config_digest": MB.trace_config_digest(config),
        "baseline_trace": trace.summary(),
        "generation": gen,
        "fitter_identity": SF.fitter_identity(),
        "fitter_options": {"target": SF.fitter_options(True),
                           "baseline_strict": dict(config.strict_options),
                           "baseline_inspection": dict(config.inspection_options)},
        "scoped_fit_evidence": {"exact_replay": True, "slots": fit["evidence"].get("slots", {})},
        "witness_separation": evidence["witness_separation"],
        "probe_coverage": evidence["probe_coverage"],
        "probe_fingerprint": target_fp,
        "irreducibility": audit,
        "environment": {"PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED", "unset")},
        "protocol_hash": _protocol_hash_v2c(),
        "code_hash": code_hash_v2c(),
    }

    #  R11 model-view isolation (v1.1 allowlist and scanner, reused unchanged)
    trusted = CD.TrustedEpisode(
        episode_id=episode["episode_id"], split=split, regime=regime, generation_seed=seed,
        demonstrations=episode["demonstrations"],
        target_schema_json=episode["target_schema_json"],
        target_concrete_json=episode["target_concrete_json"],
        target_tokens=episode["target_tokens"], target_digest=digest,
        structural_family=episode["structural_family"],
        block_count=episode["block_count"], stage_count=episode["stage_count"],
        node_count=episode["node_count"], schema_mdl=episode["schema_mdl"],
        slot_declarations=episode["slot_declarations"], fitted_slot_values={},
        tfg=episode["tfg"], tfg_digest=episode["tfg_digest"],
        base_search_evidence=episode["baseline_trace"],
        baseline_shape_audit=episode["baseline_trace"],
        target_fit_evidence={"fitted": True, "exact_on_all_demos": True},
        probe_fingerprint=target_fp, diagnostics=episode["irreducibility"],
        protocol_hash=episode["protocol_hash"], code_hash=episode["code_hash"])
    view = CD.to_model_view(trusted, row_index)
    findings = CD.scan_model_view(view, trusted)
    if findings:
        evidence["leak_findings"] = findings
        stamp("r11")
        return finish("tfg_leak"), None, evidence
    stamp("r11")

    #  R12 exact final replay from the stored artifacts
    replay_ast = M.ast_from_json(episode["target_fitted_json"])
    for demo in episode["demonstrations"]:
        rendered = _evaluate(replay_ast, np.asarray(demo["input"], dtype=int))
        if rendered is None or not np.array_equal(rendered, np.asarray(demo["output"], dtype=int)):
            stamp("r12")
            return finish("final_execution_mismatch"), None, evidence
    stamp("r12")
    return finish(ADMITTED), episode, evidence


def _protocol_hash_v2c() -> str:
    path = ROOT / "outputs" / "tti" / "constructive_v2_corrected" / "manifest_hash.txt"
    return path.read_text().split()[0] if path.exists() else "UNFROZEN"


#: every module the evidence path executes, including the graph builder whose
#: canonical digest lands on each admitted episode and the v2 module supplying
#: the shared rejection vocabulary
CODE_FILES_V2C = ("cora_tti/constructive_vocabulary.py", "cora_tti/constructive_probes.py",
                  "cora_tti/constructive_dataset.py", "cora_tti/scoped_slot_fitting.py",
                  "cora_tti/meta_baseline.py", "cora_tti/constructive_v2c.py",
                  "cora_tti/constructive_v2c_census.py", "cora_tti/constructive_v2_dataset.py",
                  "cora_parent/tfg.py", "cora_parent/interfaces.py")


def code_hashes_v2c() -> dict:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in CODE_FILES_V2C if (ROOT / name).exists()}


def code_hash_v2c() -> str:
    return hashlib.sha256(json.dumps(code_hashes_v2c(), sort_keys=True).encode()).hexdigest()
