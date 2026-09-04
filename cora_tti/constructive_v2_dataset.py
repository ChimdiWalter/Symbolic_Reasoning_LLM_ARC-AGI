"""Protocol v2 admission law: requirements R1 to R12 (directive section 21).

Additive to the v1.1 modules, which remain untouched so the v1.1 pilot stays
reproducible. The grammar, terminals, grid process, target sampler, model-view
allowlist and leakage scanner are REUSED from constructive_dataset (v1.1); what
changes is how induced slots are fitted (occurrence-scoped) and the addition of
local structural irreducibility, v1.1 target exclusion, and exact final replay.

Fairness invariant: the target path and the fixed base search call the SAME
fitter implementation, and its hash is recorded on every attempt.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_probes as CP                   # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402
from cora_tti import tfg_extractor as TX                         # noqa: E402

ADMITTED = "ADMITTED"

#: frozen v2 primary rejection vocabulary (directive section 22)
REJECTION_CODES_V2 = (
    "grammar_invalid", "type_invalid", "execution_undefined", "trivial_output",
    "base_search_solved", "baseline_shape_fit", "witness_not_separated",
    "slot_unobservable", "slot_key_unobserved", "slot_nonfunctional",
    "region_colour_conflict", "scoped_fit_failed", "final_execution_mismatch",
    "locally_reducible_block", "locally_reducible_select",
    "prior_v1_target_overlap", "duplicate_target", "split_collision",
    "tfg_leak", "generation_timeout",
)

#: infrastructure namespace, never merged with scientific counts
INFRA_PREFIX = "infra_exception:"


def _evaluate(ast, grid):
    return M.evaluate(ast, np.asarray(grid), MI.descriptors)


# --------------------------------------------------------------------------
# local structural irreducibility (directive section 12)
# --------------------------------------------------------------------------

def _ablation_reproduces(blocks, pairs, target_fingerprint: str) -> bool:
    """True when an ablated schema both replays every demonstration exactly
    and is witness-equivalent to the complete target on the frozen probes."""
    if not blocks:
        return False
    try:
        schema = CV.ast_from_blocks(blocks)       # canonical slot renumbering
    except Exception:                             # noqa: BLE001
        return False
    ok, _ = CV.validate(schema)
    if not ok:
        return False
    fitted, _ = SF.fit_induced_occurrences(schema, pairs)
    if fitted is None:
        return False                              # did not reproduce demos
    try:
        fingerprint = CP.fingerprint(fitted, _evaluate)
    except Exception:                             # noqa: BLE001
        return False
    return fingerprint == target_fingerprint


def irreducibility_audit(schema, pairs, target_fingerprint: str) -> dict:
    """Block ablation and Select ablation. A target is locally reducible when
    some single ablation preserves BOTH exact demonstration fit AND frozen
    probe behaviour. This is local irreducibility, never global minimality."""
    blocks = CV.blocks_from_ast(schema)
    reducible_block, reducible_select = [], []
    for index in range(len(blocks)):
        if len(blocks) == 1:
            break
        reduced = [b for i, b in enumerate(blocks) if i != index]
        if _ablation_reproduces(reduced, pairs, target_fingerprint):
            reducible_block.append(index)
    for block_index, (partition, selects, feature) in enumerate(blocks):
        for select_index in range(len(selects)):
            trimmed = tuple(s for i, s in enumerate(selects) if i != select_index)
            reduced = list(blocks)
            reduced[block_index] = (partition, trimmed, feature)
            if _ablation_reproduces(reduced, pairs, target_fingerprint):
                reducible_select.append([block_index, select_index])
    return {"reducible_blocks": reducible_block,
            "reducible_selects": reducible_select,
            "blocks": len(blocks)}


# --------------------------------------------------------------------------
# the v2 admission law
# --------------------------------------------------------------------------

def evaluate_target_v2(schema, *, seed: int, split: str, regime: str,
                       allowed_families: Sequence[tuple],
                       seen_digests: set, seen_train_digests: set,
                       v1_exclusion: set, budgets: Mapping[str, float],
                       row_index: int) -> tuple:
    """Returns (outcome, trusted_episode_dict|None, evidence). Exactly one
    terminal primary outcome per attempt."""
    started = time.monotonic()
    evidence: dict = {"stage_times": {}, "fitter": SF.fitter_identity()[:16]}

    def stamp(name):
        evidence["stage_times"][name] = round(time.monotonic() - started, 3)

    #  R1 grammar validity
    ok, code = CV.validate(schema)
    if not ok:
        stamp("r1")
        return (code if code in REJECTION_CODES_V2 else "grammar_invalid"), None, evidence
    family = CV.family(schema)
    if CV.is_banned_target_family(family):
        stamp("r1")
        return "split_collision", None, evidence
    if tuple(family) not in {tuple(f) for f in allowed_families}:
        stamp("r1")
        return "split_collision", None, evidence
    digest = CV.digest(schema)

    #  R10 v1.1 exclusion, and R9 split integrity
    if digest in v1_exclusion:
        stamp("r10")
        return "prior_v1_target_overlap", None, evidence
    if digest in seen_digests:
        stamp("r9")
        return "duplicate_target", None, evidence
    if regime == "ast_holdout" and digest in seen_train_digests:
        stamp("r9")
        return "split_collision", None, evidence
    if regime == "train_pool" and CV.is_holdout_family(family):
        stamp("r9")
        return "split_collision", None, evidence

    #  R2 executability and R3 nontriviality
    grid_seeds = [seed * 97 + i for i in range(14)]
    concrete = CD.instantiate_tables(
        schema, [CD.generate_grid(s) for s in grid_seeds[:6]])
    if concrete is None:
        stamp("r2")
        return "execution_undefined", None, evidence
    pairs, demo_diag = CD.render_demonstrations(concrete, grid_seeds, min_demos=3)
    evidence["demo_diagnostic"] = demo_diag
    if len(pairs) < 3:
        stamp("r2")
        return ("trivial_output" if demo_diag["trivial"] >= demo_diag["undefined"]
                else "execution_undefined"), None, evidence
    stamp("r3")
    if time.monotonic() - started > budgets["per_target_s"]:
        return "generation_timeout", None, evidence

    #  R5 occurrence-scoped recoverability (also carries R12 exact replay)
    fitted_target, fit_evidence = SF.fit_induced_occurrences(schema, pairs)
    evidence["scoped_fit"] = {k: v for k, v in fit_evidence.items()
                              if k in ("failure", "detail", "exact_replay", "slots")}
    if fitted_target is None:
        stamp("r5")
        failure = fit_evidence.get("failure", "scoped_fit_failed")
        return (failure if failure in REJECTION_CODES_V2 else "scoped_fit_failed"), None, evidence
    stamp("r5")

    #  R4 fixed base failure and R6 baseline-family exclusion, SAME fitter.
    #  One enumeration yields both: `exact` is the requirement-4/6 evidence,
    #  `fitted` (including inexact constraint-only fits) is what requirement 7
    #  compares against on the frozen probes.
    base = SF.base_search_with_scoped_fitter(pairs)
    evidence["base_search"] = {"enumerated": base["enumerated"],
                               "fitted": base["fitted"], "exact": base["exact"],
                               "fitter": base["fitter"]}
    if base["fitter"] != SF.fitter_identity()[:16]:
        stamp("r4")
        return "scoped_fit_failed", None, evidence     # fairness violation
    if base["exact"]:
        stamp("r4")
        return "base_search_solved", None, evidence
    stamp("r6")

    #  R7 frozen-probe witness separation
    try:
        target_fp = CP.fingerprint(fitted_target, _evaluate)
    except Exception:                                   # noqa: BLE001
        stamp("r7")
        return "execution_undefined", None, evidence
    equivalent = []
    for schema_b, fitted_b in base["fitted_pairs"]:
        try:
            if CP.fingerprint(fitted_b, _evaluate) == target_fp:
                equivalent.append(CV.canonical(schema_b))
        except Exception:                               # noqa: BLE001
            continue
    evidence["witness_equivalent_baselines"] = len(equivalent)
    if equivalent:
        stamp("r7")
        return "witness_not_separated", None, evidence
    stamp("r7")

    #  R8 local structural irreducibility
    audit = irreducibility_audit(schema, pairs, target_fp)
    evidence["irreducibility"] = audit
    if audit["reducible_blocks"]:
        stamp("r8")
        return "locally_reducible_block", None, evidence
    if audit["reducible_selects"]:
        stamp("r8")
        return "locally_reducible_select", None, evidence
    stamp("r8")

    #  TFG through the existing real trace-instrumented extractor
    extraction = TX.extract([(a, b) for a, b in pairs], budget_s=budgets["tfg_s"])
    if extraction["solved"]:
        stamp("tfg")
        return "base_search_solved", None, evidence
    tfg = extraction["tfg"]
    stamp("tfg")

    episode = {
        "episode_id": f"v2-{split}-{regime}-{row_index:03d}",
        "split": split, "regime": regime, "generation_seed": seed,
        "demonstrations": [{"input": a.tolist(), "output": b.tolist()}
                           for a, b in pairs],
        "target_schema_json": M.ast_to_json(schema),
        "target_concrete_json": M.ast_to_json(concrete),
        "target_fitted_json": M.ast_to_json(fitted_target),
        "target_tokens": [list(t) for t in CV.tokens_from_ast(schema)],
        "target_digest": digest,
        "structural_family": list(family),
        "block_count": CV.block_count(schema),
        "stage_count": CV.stage_count(schema),
        "node_count": CV.mdl(schema), "schema_mdl": CV.mdl(schema),
        "slot_declarations": M.free_slot_types(schema),
        "slot_occurrences": [
            {"slot": o.slot_name, "block_index": o.block_index,
             "ast_path": list(o.ast_path),
             "local_prefix": [o.local_prefix[0], list(o.local_prefix[1])],
             "key_expression": o.local_key_expression}
            for o in SF.occurrences(schema)],
        "tfg": tfg.to_json(), "tfg_digest": tfg.digest(),
        "base_search_evidence": evidence["base_search"],
        "scoped_fit_evidence": {"exact_replay": True,
                                "slots": fit_evidence.get("slots", {})},
        "irreducibility": audit,
        "probe_fingerprint": target_fp,
        "fitter_identity": SF.fitter_identity(),
        "protocol_v2_hash": _protocol_v2_hash(),
        "code_hash": _code_hash_v2(),
    }

    #  R11 model-view isolation, reusing the v1.1 allowlist and scanner
    trusted = CD.TrustedEpisode(
        episode_id=episode["episode_id"], split=split, regime=regime,
        generation_seed=seed, demonstrations=episode["demonstrations"],
        target_schema_json=episode["target_schema_json"],
        target_concrete_json=episode["target_concrete_json"],
        target_tokens=episode["target_tokens"], target_digest=digest,
        structural_family=episode["structural_family"],
        block_count=episode["block_count"], stage_count=episode["stage_count"],
        node_count=episode["node_count"], schema_mdl=episode["schema_mdl"],
        slot_declarations=episode["slot_declarations"], fitted_slot_values={},
        tfg=episode["tfg"], tfg_digest=episode["tfg_digest"],
        base_search_evidence=episode["base_search_evidence"],
        baseline_shape_audit=evidence["base_search"],
        target_fit_evidence={"fitted": True, "exact_on_all_demos": True},
        probe_fingerprint=target_fp, diagnostics=audit,
        protocol_hash=episode["protocol_v2_hash"], code_hash=episode["code_hash"])
    view = CD.to_model_view(trusted, row_index)
    findings = CD.scan_model_view(view, trusted)
    if findings:
        evidence["leak_findings"] = findings
        stamp("r11")
        return "tfg_leak", None, evidence
    stamp("r11")

    #  R12 exact final replay from stored artifacts
    replay_ast = M.ast_from_json(episode["target_fitted_json"])
    for demo in episode["demonstrations"]:
        rendered = _evaluate(replay_ast, np.asarray(demo["input"], dtype=int))
        if rendered is None or not np.array_equal(
                rendered, np.asarray(demo["output"], dtype=int)):
            stamp("r12")
            return "final_execution_mismatch", None, evidence
    stamp("r12")
    return ADMITTED, episode, evidence


def _protocol_v2_hash() -> str:
    path = ROOT / "outputs" / "tti" / "constructive_protocol_manifest_v2_hash.txt"
    return path.read_text().split()[0] if path.exists() else "UNFROZEN"


def _code_hash_v2() -> str:
    parts = []
    for name in ("constructive_vocabulary.py", "constructive_probes.py",
                 "constructive_dataset.py", "scoped_slot_fitting.py",
                 "constructive_v2_dataset.py"):
        parts.append(hashlib.sha256(
            (ROOT / "cora_tti" / name).read_bytes()).hexdigest())
    return hashlib.sha256("".join(parts).encode()).hexdigest()
