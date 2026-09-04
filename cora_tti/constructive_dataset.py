"""Constructive pilot dataset: records, sampler, generator, requirement law.

Implements Item-2 Block B. Every rule is consumed from the frozen v1.1
protocol manifest through constructive_vocabulary; nothing is retyped here.

The module defines two strictly separated representations:

    TrustedEpisode        everything, including the target and its provenance
    model-visible record  an ALLOWLISTED projection: failure evidence only

`to_model_view` is the only bridge, and `scan_model_view` is a mechanical
leakage gate with structured (not merely substring) comparison against the
trusted target.

Admission law (the eight frozen requirements) is implemented in
`evaluate_target`, which returns exactly one terminal outcome per attempt:
ADMITTED or a single primary rejection code from the frozen vocabulary.
Infrastructure failures use a separate `infra_exception:<class>` namespace
and are never merged with scientific rejection counts.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_probes as CP                   # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import tfg_extractor as TX                         # noqa: E402

ADMITTED = "ADMITTED"

#: frozen scientific rejection vocabulary (v1.1); no new criterion may be added
REJECTION_CODES = (
    "grammar_invalid", "type_invalid", "execution_undefined", "trivial_output",
    "base_search_solved", "baseline_shape_fit", "target_schema_failed",
    "witness_not_separated", "duplicate_target", "split_collision",
    "tfg_leak", "generation_timeout",
)

#: the ONLY fields a model may ever see
MODEL_VIEW_ALLOWLIST = frozenset({
    "row_index", "tfg", "input_type", "output_type", "features",
})
#: the only permitted mechanistic feature keys inside "features"
FEATURE_ALLOWLIST = frozenset({
    "n_demonstrations", "mean_cells_changed", "mean_fraction_changed",
    "same_shape_all", "palette_introduced_mean", "palette_removed_mean",
    "search_typed", "search_rejected", "search_max_depth",
    "search_deadline_hit", "frontier_terms", "slot_failure_ops",
})


def _evaluate(ast, grid):
    return M.evaluate(ast, np.asarray(grid), MI.descriptors)


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TrustedEpisode:
    episode_id: str
    split: str                    # train | val | test
    regime: str                   # train_pool | ast_holdout | structural_holdout
    generation_seed: int
    demonstrations: list          # [{"input": [[...]], "output": [[...]]}]
    target_schema_json: dict      # canonical schema (slots open)
    target_concrete_json: dict    # instantiated program used to render demos
    target_tokens: list
    target_digest: str
    structural_family: list
    block_count: int
    stage_count: int
    node_count: int
    schema_mdl: int
    slot_declarations: dict
    fitted_slot_values: Any
    tfg: dict
    tfg_digest: str
    base_search_evidence: dict
    baseline_shape_audit: dict
    target_fit_evidence: dict
    probe_fingerprint: str
    diagnostics: dict
    protocol_hash: str
    code_hash: str

    def to_json(self) -> dict:
        return asdict(self)


def to_model_view(episode: TrustedEpisode, row_index: int) -> dict:
    """The ONLY bridge from trusted to model-visible. Allowlist construction:
    fields are built explicitly, never copied from the trusted record."""
    demos = episode.demonstrations
    changed, fractions, same_shape = [], [], True
    intro, removed = [], []
    for demo in demos:
        a = np.asarray(demo["input"], dtype=int)
        b = np.asarray(demo["output"], dtype=int)
        if a.shape != b.shape:
            same_shape = False
            continue
        n = int(np.count_nonzero(a != b))
        changed.append(n)
        fractions.append(round(n / a.size, 4))
        pa, pb = set(np.unique(a).tolist()), set(np.unique(b).tolist())
        intro.append(len(pb - pa))
        removed.append(len(pa - pb))
    execution = {}
    for node in episode.tfg.get("nodes", []):
        if node.get("kind") == "execution":
            execution = node.get("attrs", {})
    frontier = sum(1 for n in episode.tfg.get("nodes", [])
                   if n.get("kind") == "frontier_term")
    slot_fail = sum(1 for n in episode.tfg.get("nodes", [])
                    if n.get("kind") == "slot")
    features = {
        "n_demonstrations": len(demos),
        "mean_cells_changed": round(float(np.mean(changed)), 3) if changed else 0.0,
        "mean_fraction_changed": round(float(np.mean(fractions)), 5) if fractions else 0.0,
        "same_shape_all": bool(same_shape),
        "palette_introduced_mean": round(float(np.mean(intro)), 3) if intro else 0.0,
        "palette_removed_mean": round(float(np.mean(removed)), 3) if removed else 0.0,
        "search_typed": int(execution.get("typed", 0)),
        "search_rejected": int(execution.get("rejected", 0)),
        "search_max_depth": int(execution.get("max_depth", 0)),
        "search_deadline_hit": bool(execution.get("deadline_hit", False)),
        "frontier_terms": frontier,
        "slot_failure_ops": slot_fail,
    }
    assert set(features) <= FEATURE_ALLOWLIST
    return {"row_index": row_index, "tfg": episode.tfg,
            "input_type": "Grid", "output_type": "Grid", "features": features}


# --------------------------------------------------------------------------
# leakage gate
# --------------------------------------------------------------------------

def _walk(value, path="$"):
    if isinstance(value, dict):
        for key, sub in value.items():
            yield path, "key", str(key)
            yield from _walk(sub, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, sub in enumerate(value):
            yield from _walk(sub, f"{path}[{index}]")
    else:
        yield path, "value", value


def scan_model_view(view: Mapping[str, Any],
                    episode: TrustedEpisode) -> list:
    """Return a list of leak findings; empty means clean."""
    findings = []
    extra = set(view) - MODEL_VIEW_ALLOWLIST
    if extra:
        findings.append(f"undeclared_field:{sorted(extra)}")
    if set(view.get("features", {})) - FEATURE_ALLOWLIST:
        findings.append("undeclared_feature")
    digest = episode.target_digest
    family_text = CV.family_text(tuple(episode.structural_family))
    canonical_ast = json.dumps(episode.target_schema_json, sort_keys=True)
    token_strings = {str(t) for t in episode.target_tokens}
    token_seq = json.dumps([list(t) if isinstance(t, (list, tuple)) else t
                            for t in episode.target_tokens], sort_keys=True)
    terminals = set()
    for token in episode.target_tokens:
        if isinstance(token, (list, tuple)) and len(token) > 1:
            terminals.add(str(token[1]))
    blob = json.dumps(view, sort_keys=True, default=str)
    #  1. structured / whole-value comparisons
    for path, kind, item in _walk(view):
        text = str(item)
        if kind == "key" and text in ("target_digest", "target_schema_json",
                                      "structural_family", "target_tokens",
                                      "split", "regime", "task_id",
                                      "source_token"):
            findings.append(f"trusted_key:{path}:{text}")
        if len(text) >= 8 and text in digest:
            findings.append(f"digest_fragment:{path}")
        if text == family_text:
            findings.append(f"family_label:{path}")
        if text and text == canonical_ast:
            findings.append(f"canonical_ast:{path}")
        if text and text == token_seq:
            findings.append(f"token_sequence:{path}")
    #  2. substring sweep over the serialized blob (defence in depth)
    for fragment, label in ((digest[:16], "digest_prefix"),
                            (canonical_ast, "canonical_ast_blob"),
                            (token_seq, "token_seq_blob"),
                            (family_text, "family_text_blob")):
        if fragment and fragment in blob:
            findings.append(f"{label}_in_blob")
    #  3. the ordered terminal multiset of the target must not appear verbatim
    if terminals and len(terminals) > 1:
        ordered = [str(t[1]) for t in episode.target_tokens
                   if isinstance(t, (list, tuple)) and len(t) > 1]
        if ordered and json.dumps(ordered) in blob:
            findings.append("terminal_sequence_in_blob")
    return findings


# --------------------------------------------------------------------------
# deterministic target sampling (never hand-written ASTs)
# --------------------------------------------------------------------------

def sample_target(seed: int, family: tuple) -> tuple:
    """A schema of exactly the requested structural family, sampled from the
    frozen terminals through the Block-A constructors."""
    v = CV.vocab()
    rng = np.random.default_rng(seed)
    blocks = []
    for selects_needed in family:
        partition = v["partitions"][int(rng.integers(0, len(v["partitions"])))]
        predicates = tuple(v["predicates"][int(rng.integers(0, len(v["predicates"])))]
                           for _ in range(selects_needed))
        feature = v["key_features"][int(rng.integers(0, len(v["key_features"])))]
        blocks.append((partition, predicates, feature))
    return CV.ast_from_blocks(blocks)


# --------------------------------------------------------------------------
# one common grid process for every split and regime
# --------------------------------------------------------------------------

#: a small fixed shape inventory so feature values RECUR across demonstrations
#: (the ordinary learner refuses tables whose keys are witnessed once)
SHAPE_INVENTORY = ((1, 1), (1, 2), (2, 2), (1, 3), (2, 1), (3, 1))
#: the SAME multiset is placed in every grid, so feature values recur across
#: demonstrations and the learner's two-witness rule can be satisfied
FIXED_SHAPE_MULTISET = ((1, 1), (1, 2), (2, 2))


def generate_grid(seed: int) -> np.ndarray:
    """Identical distribution for train, val, test-A and test-B.

    Structured so that ALL FOUR frozen partitions can return non-empty sets
    and feature values RECUR across demonstrations (the ordinary learner
    refuses a table whose key is witnessed once):
      - coloured rectangles from a fixed shape inventory  -> colour_components
      - a background that stays connected around them     -> background_components
      - a framed hole placed on most grids                -> enclosed_regions
      - full-width/height separator lines on some grids   -> separator_panels
    Nothing here is conditioned on family, split, regime or target.
    """
    rng = np.random.default_rng(seed)
    height = int(9 + rng.integers(0, 3))
    width = int(9 + rng.integers(0, 3))
    grid = np.zeros((height, width), dtype=int)

    #  separator lines on roughly half the grids (feeds separator_panels)
    if rng.random() < 0.5:
        row = int(height // 2)
        grid[row, :] = 1
    #  EVERY grid places the SAME shape multiset, varying only position and
    #  colour, so feature values (area, hw, shape, is_rect, is_square) recur in
    #  every demonstration. The ordinary learner refuses a table whose key is
    #  witnessed once, so a generator whose feature values do not recur cannot
    #  produce a fittable target: recurrence is a competence requirement of the
    #  generator, not a relaxation of the admission law.
    anchors = [(r, c) for r in range(0, height - 2, 3)
               for c in range(0, width - 2, 3)]
    rng.shuffle(anchors)
    placed = 0
    for r0, c0 in anchors:
        if placed >= len(FIXED_SHAPE_MULTISET):
            break
        h, w = FIXED_SHAPE_MULTISET[placed]
        if r0 + h < height and c0 + w < width and int(grid[r0, c0]) == 0:
            if not grid[r0:r0 + h, c0:c0 + w].any():
                grid[r0:r0 + h, c0:c0 + w] = int(2 + rng.integers(0, 7))
                placed += 1
    #  a framed hole on most grids (feeds enclosed_regions)
    if rng.random() < 0.75 and height >= 8 and width >= 8:
        r0, c0 = height - 4, width - 4
        if not grid[r0:r0 + 3, c0:c0 + 3].any():
            grid[r0:r0 + 3, c0:c0 + 3] = int(2 + rng.integers(0, 7))
            grid[r0 + 1, c0 + 1] = 0
    return grid


def instantiate_tables(schema, grids: Sequence[np.ndarray]):
    """Derive one functional feature -> colour table per block from the
    demonstration inputs. Generation may know these; the learner may not."""
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
        table = tuple(sorted(
            ((value, 1 + (index * 3 + len(repr(value)) + abs(hash(repr(value))) % 7) % 9)
             for value in values), key=lambda kv: repr(kv[0])))
        concrete = M.instantiate(concrete, {f"?{index}": table})
    return concrete


def render_demonstrations(concrete, seeds: Sequence[int],
                          min_demos: int) -> tuple:
    """(pairs, diagnostic) with defined, nontrivial outputs only."""
    pairs, undefined, trivial = [], 0, 0
    for seed in seeds:
        grid = generate_grid(seed)
        rendered = _evaluate(concrete, grid)
        if rendered is None:
            undefined += 1
            continue
        if np.array_equal(rendered, grid):
            trivial += 1
            continue
        pairs.append((grid, np.asarray(rendered)))
        if len(pairs) >= min_demos + 2:
            break
    return pairs, {"undefined": undefined, "trivial": trivial}


# --------------------------------------------------------------------------
# exhaustive family-(1,) baseline audit (requirement 4b and 6)
# --------------------------------------------------------------------------

def baseline_shape_audit(pairs, target_fingerprint: str) -> dict:
    """Enumerate the complete frozen family-(1,) product and fit each with the
    ORDINARY learner. Records exact fits and witness-equivalences separately."""
    v = CV.vocab()
    exact_fits, witness_equal, fitted_count = [], [], 0
    total = 0
    for partition in v["partitions"]:
        for predicate in v["predicates"]:
            for feature in v["key_features"]:
                total += 1
                schema = CV.ast_from_blocks([(partition, (predicate,), feature)])
                fitted = MI.fit_induced_slots(schema, pairs)
                if fitted is None:
                    continue
                fitted_count += 1
                if MI.observational_signature(fitted, pairs) is not None:
                    exact_fits.append([partition, predicate, feature])
                    continue
                try:
                    fp = CP.fingerprint(fitted, _evaluate)
                except Exception:                       # noqa: BLE001
                    continue
                if fp == target_fingerprint:
                    witness_equal.append([partition, predicate, feature])
    return {"enumerated": total, "fitted": fitted_count,
            "exact_fits": exact_fits, "witness_equivalent": witness_equal}


# --------------------------------------------------------------------------
# the admission law: exactly one terminal outcome per attempt
# --------------------------------------------------------------------------

def evaluate_target(schema, *, seed: int, split: str, regime: str,
                    allowed_families: Sequence[tuple],
                    seen_digests: set, seen_train_digests: set,
                    train_families: set, budgets: Mapping[str, float],
                    row_index: int) -> tuple:
    """Returns (outcome, TrustedEpisode|None, evidence)."""
    started = time.monotonic()
    evidence: dict = {"stage_times": {}}

    def stamp(name):
        evidence["stage_times"][name] = round(time.monotonic() - started, 3)

    #  R1 grammar and type validity
    ok, code = CV.validate(schema)
    if not ok:
        stamp("r1")
        return (code if code in REJECTION_CODES else "grammar_invalid"), None, evidence
    family = CV.family(schema)
    if CV.is_banned_target_family(family):
        stamp("r1")
        return "split_collision", None, evidence
    if tuple(family) not in {tuple(f) for f in allowed_families}:
        stamp("r1")
        return "split_collision", None, evidence
    digest = CV.digest(schema)
    if digest in seen_digests:
        stamp("r1")
        return "duplicate_target", None, evidence
    #  R7 split law: a test-A target may not be a training label; a holdout
    #  family may not appear in train or val
    if regime == "ast_holdout" and digest in seen_train_digests:
        stamp("r1")
        return "split_collision", None, evidence
    if regime in ("train_pool",) and CV.is_holdout_family(family):
        stamp("r1")
        return "split_collision", None, evidence

    #  R2 / R3 execution and nontriviality
    grid_seeds = [seed * 97 + i for i in range(12)]
    concrete = instantiate_tables(schema, [generate_grid(s) for s in grid_seeds[:6]])
    if concrete is None:
        stamp("r2")
        return "execution_undefined", None, evidence
    pairs, demo_diag = render_demonstrations(concrete, grid_seeds, min_demos=3)
    evidence["demo_diagnostic"] = demo_diag
    if len(pairs) < 3:
        stamp("r2")
        return ("trivial_output" if demo_diag["trivial"] >= demo_diag["undefined"]
                else "execution_undefined"), None, evidence
    stamp("r3")
    if time.monotonic() - started > budgets["per_target_s"]:
        return "generation_timeout", None, evidence

    #  R5 target-supplied recoverability through the ORDINARY learner
    fitted_target = MI.fit_induced_slots(schema, pairs)
    if fitted_target is None or \
            MI.observational_signature(fitted_target, pairs) is None:
        stamp("r5")
        return "target_schema_failed", None, evidence
    stamp("r5")

    #  R4a the engine's own fixed meta-search must fail within the frozen budget
    found, stats = MI.search(pairs, deadline=time.monotonic() + budgets["base_search_s"])
    evidence["base_search"] = {"found": len(found),
                               "hypotheses": int(getattr(stats, "hypotheses", 0)),
                               "seconds": round(getattr(stats, "seconds", 0.0), 3)}
    if found:
        stamp("r4a")
        return "base_search_solved", None, evidence
    stamp("r4a")

    #  R6 / R4b exhaustive family-(1,) audit with bounded witness separation
    target_fp = CP.fingerprint(fitted_target, _evaluate)
    audit = baseline_shape_audit(pairs, target_fp)
    evidence["baseline_shape_audit"] = audit
    stamp("r6")
    if audit["exact_fits"]:
        return "baseline_shape_fit", None, evidence
    if audit["witness_equivalent"]:
        return "witness_not_separated", None, evidence

    #  TFG through the existing real trace-instrumented extractor
    extraction = TX.extract([(a, b) for a, b in pairs],
                            budget_s=budgets["tfg_s"])
    if extraction["solved"]:
        stamp("tfg")
        return "base_search_solved", None, evidence
    tfg = extraction["tfg"]
    stamp("tfg")

    #  diagnostics (recorded, never gates in v1)
    diagnostics = {"redundant_all_selects": sum(
        1 for _, selects, _ in CV.blocks_from_ast(schema)
        for predicate in selects if predicate == "all"),
        "blocks_changing_output": _blocks_changing_output(schema, concrete, pairs),
        "demo_count": len(pairs)}

    episode = TrustedEpisode(
        episode_id=f"{split}-{regime}-{row_index:03d}",
        split=split, regime=regime, generation_seed=seed,
        demonstrations=[{"input": a.tolist(), "output": b.tolist()}
                        for a, b in pairs],
        target_schema_json=M.ast_to_json(schema),
        target_concrete_json=M.ast_to_json(concrete),
        target_tokens=[list(t) for t in CV.tokens_from_ast(schema)],
        target_digest=digest,
        structural_family=list(family),
        block_count=CV.block_count(schema),
        stage_count=CV.stage_count(schema),
        node_count=CV.mdl(schema),
        schema_mdl=CV.mdl(schema),
        slot_declarations=M.free_slot_types(schema),
        fitted_slot_values=json.loads(json.dumps(
            M.bound_values(fitted_target), default=str)),
        tfg=tfg.to_json(), tfg_digest=tfg.digest(),
        base_search_evidence=evidence["base_search"],
        baseline_shape_audit=audit,
        target_fit_evidence={"fitted": True, "exact_on_all_demos": True},
        probe_fingerprint=target_fp,
        diagnostics=diagnostics,
        protocol_hash=_protocol_hash(),
        code_hash=_code_hash())

    #  R8 leakage
    view = to_model_view(episode, row_index)
    findings = scan_model_view(view, episode)
    if findings:
        evidence["leak_findings"] = findings
        stamp("r8")
        return "tfg_leak", None, evidence
    stamp("r8")
    return ADMITTED, episode, evidence


def _blocks_changing_output(schema, concrete, pairs) -> int:
    """Diagnostic: how many blocks demonstrably alter the rendering."""
    blocks = CV.blocks_from_ast(schema)
    if len(blocks) == 1:
        return 1
    changing = 0
    for index in range(len(blocks)):
        reduced_blocks = [b for i, b in enumerate(blocks) if i != index]
        try:
            reduced_schema = CV.ast_from_blocks(reduced_blocks)
            reduced = instantiate_tables(reduced_schema,
                                         [a for a, _ in pairs])
            if reduced is None:
                changing += 1
                continue
            differs = False
            for grid_in, grid_out in pairs:
                rendered = _evaluate(reduced, grid_in)
                if rendered is None or not np.array_equal(rendered, grid_out):
                    differs = True
                    break
            changing += int(differs)
        except Exception:                            # noqa: BLE001
            changing += 1
    return changing


def _protocol_hash() -> str:
    path = ROOT / "outputs" / "tti" / "constructive_protocol_manifest_hash.txt"
    return path.read_text().split()[0]


def _code_hash() -> str:
    parts = []
    for name in ("constructive_vocabulary.py", "constructive_probes.py",
                 "constructive_dataset.py"):
        parts.append(hashlib.sha256(
            (ROOT / "cora_tti" / name).read_bytes()).hexdigest())
    return hashlib.sha256("".join(parts).encode()).hexdigest()
