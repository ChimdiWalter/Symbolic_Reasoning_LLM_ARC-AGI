"""Operator-dropout episode generator — Stage A of the GPN curriculum.

Self-supervised invention data with zero human labels
(docs/CORA_TTI_MASTER_PLAN.md §V, docs/CORA_PARENT_ARCHITECTURE.md idea 1/idea 8):

    1. sample an executable program from the PUBLIC blind-runtime language that
       USES a chosen production e;
    2. render synthetic demonstrations by executing it on random grids;
    3. remove e (K^-e) and run the ordinary search under the crippled language;
    4. keep the episode only if the crippled search FAILS within its budget while
       the full language solves the demos (the task genuinely forces e);
    5. record a Typed Failure Graph built ONLY from mechanistic evidence of the
       crippled failure — the withheld production never appears in the TFG;
    6. the training target is the reconstruction of e (name + typed signature).

Data discipline (docs/CORA_DATA_ACCESS_DAG.md): inputs are synthetic only (D2).
This module reads no corpus file and imports only the public runtime code — never
any sealed artifact. Seeds are explicit; a manifest with counts, flags and the
output hash accompanies every generated file.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from level4_blind_runtime import runtime as V          # noqa: E402
from level4_blind_runtime import env as E              # noqa: E402
from level4_blind_runtime import search as SEARCH      # noqa: E402

from cora_parent.tfg import ConcreteTFG, TFGEdge, TFGNode   # noqa: E402

GOAL = V.GRID
#: sampling caps (frozen for a given dataset by the manifest)
MAX_DEPTH = 6
MAX_PROGRAM_TRIES = 200
MAX_DEMO_TRIES = 60
DEMOS_PER_EPISODE = 3


# --------------------------------------------------------------------------
# typed top-down program sampling over the public registry
# --------------------------------------------------------------------------

def _producers(registry: Mapping[str, Any], wanted) -> list:
    return [p for p in registry.values() if V.type_equal(p.result_type, wanted)]


def _random_map(rng: np.random.Generator) -> dict:
    """A small literal table for the induced Map type (FeatureValue -> Colour)."""
    keys = rng.choice(np.arange(1, 8), size=int(rng.integers(2, 5)), replace=False)
    return {int(k): int(rng.integers(1, 10)) for k in keys}


def sample_ast(rng: np.random.Generator, wanted, registry: Mapping[str, Any],
               depth: int = MAX_DEPTH):
    """One random well-typed AST of type `wanted`, or None on a dead end."""
    text = str(wanted)
    options = []
    if text in V.TERMINAL_VALUES:
        options.append("terminal")
    if text in V.INDUCED_TYPES:
        options.append("induced")
    producers = _producers(registry, wanted) if depth > 0 else []
    options.extend(producers)
    if not options:
        return None
    choice = options[int(rng.integers(0, len(options)))]
    if choice == "terminal":
        values = V.TERMINAL_VALUES[text]
        return values[int(rng.integers(0, len(values)))]
    if choice == "induced":
        return _random_map(rng)
    args = []
    for arg_type in choice.arg_types:
        arg = sample_ast(rng, arg_type, registry, depth - 1)
        if arg is None:
            return None
        args.append(arg)
    return (choice.name, tuple(args))


def uses(ast, name: str) -> bool:
    if not (isinstance(ast, tuple) and len(ast) == 2 and isinstance(ast[0], str)):
        return False
    if ast[0] == name:
        return True
    return any(uses(arg, name) for arg in ast[1]
               if isinstance(arg, tuple))


def sample_program_using(rng: np.random.Generator, name: str,
                         registry: Mapping[str, Any]):
    for _ in range(MAX_PROGRAM_TRIES):
        ast = sample_ast(rng, GOAL, registry)
        if ast is not None and uses(ast, name):
            return ast
    return None


# --------------------------------------------------------------------------
# synthetic grids and demonstrations
# --------------------------------------------------------------------------

def random_grid(rng: np.random.Generator) -> np.ndarray:
    h, w = int(rng.integers(5, 10)), int(rng.integers(5, 10))
    grid = np.zeros((h, w), dtype=int)
    for _ in range(int(rng.integers(1, 4))):
        colour = int(rng.integers(1, 10))
        r0 = int(rng.integers(0, h - 1)); c0 = int(rng.integers(0, w - 1))
        r1 = min(h, r0 + int(rng.integers(1, 4)))
        c1 = min(w, c0 + int(rng.integers(1, 4)))
        grid[r0:r1, c0:c1] = colour
    return grid


def render_demos(ast, rng: np.random.Generator, env,
                 n: int = DEMOS_PER_EPISODE):
    """Demonstration pairs from executing the program; None if the program is
    degenerate (undefined, constant-equal-to-input everywhere, or unstable)."""
    pairs, changed = [], False
    for _ in range(MAX_DEMO_TRIES):
        if len(pairs) == n:
            break
        grid = random_grid(rng)
        out = E.evaluate(ast, grid, env)
        if out is None or out.size == 0:
            continue
        pairs.append((grid, np.asarray(out)))
        if not np.array_equal(grid, out):
            changed = True
    if len(pairs) < n or not changed:
        return None
    return pairs


# --------------------------------------------------------------------------
# failure evidence -> Typed Failure Graph (the withheld op NEVER appears)
# --------------------------------------------------------------------------

def _palette(grid: np.ndarray) -> set:
    return set(int(v) for v in np.unique(grid))


def tfg_from_failure(pairs, stats, goal_type: str = "Grid") -> ConcreteTFG:
    nodes = [TFGNode("goal", "goal", goal_type)]
    edges = []
    for index, (grid_in, grid_out) in enumerate(pairs):
        din = f"delta{index}"
        same_shape = grid_in.shape == grid_out.shape
        nodes.append(TFGNode(din, "delta_signature", "", {
            "same_shape": bool(same_shape),
            "shrinks": bool(grid_out.size < grid_in.size),
            "grows": bool(grid_out.size > grid_in.size)}))
        edges.append(TFGEdge(din, "blocks", "goal"))
        pin, pout = _palette(grid_in), _palette(grid_out)
        nodes.append(TFGNode(f"palette{index}", "palette_change", "", {
            "introduced": len(pout - pin), "removed": len(pin - pout),
            "n_in": len(pin), "n_out": len(pout)}))
        edges.append(TFGEdge(f"palette{index}", "observed_on", din))
        if same_shape:
            changed = int(np.count_nonzero(grid_in != grid_out))
            nodes.append(TFGNode(f"shape{index}", "shape_change", "", {
                "cells_changed": changed,
                "fraction_changed": round(changed / grid_in.size, 4)}))
            edges.append(TFGEdge(f"shape{index}", "observed_on", din))
    nodes.append(TFGNode("search", "execution", "", {
        "typed": int(stats.typed), "generated": int(stats.generated),
        "rejected": int(stats.rejected), "max_depth": int(stats.max_depth),
        "semantic_classes": int(stats.semantic_classes),
        "deadline_hit": bool(stats.seconds >= SEARCH.budget_s() - 0.01)}))
    edges.append(TFGEdge("search", "fails", "goal"))
    return ConcreteTFG(goal_type, goal_type, nodes, edges)


# --------------------------------------------------------------------------
# episodes
# --------------------------------------------------------------------------

@dataclass
class EpisodeConfig:
    #: per-search wall budget, seconds (kept far below the frozen 8 s default)
    search_budget_s: float = 2.0
    #: also verify the FULL language solves the demos within budget
    verify_full: bool = True


def _search(pairs, env, budget_s: float):
    deadline = time.monotonic() + budget_s
    return SEARCH.search(pairs, deadline=deadline, env=env)


def episode(rng: np.random.Generator, withheld: str,
            config: EpisodeConfig = EpisodeConfig()):
    """One dropout episode for production `withheld`; None when rejected."""
    registry = dict(V.REGISTRY)
    if withheld not in registry:
        raise KeyError(withheld)
    env_full = E.LanguageEnv(base=registry, label="full")
    program = sample_program_using(rng, withheld, registry)
    if program is None:
        return None
    pairs = render_demos(program, rng, env_full)
    if pairs is None:
        return None
    crippled = {k: v for k, v in registry.items() if k != withheld}
    env_crippled = E.LanguageEnv(base=crippled, label=f"minus-one")
    found_crippled, stats = _search(pairs, env_crippled, config.search_budget_s)
    if found_crippled:
        return None                      # the task does not force the withheld op
    solved_full = None
    if config.verify_full:
        found_full, _ = _search(pairs, env_full, config.search_budget_s)
        solved_full = bool(found_full)
    target = registry[withheld]
    tfg = tfg_from_failure(pairs, stats)
    return {
        "tfg": tfg.to_json(),
        "tfg_digest": tfg.digest(),
        "target": {
            "name": target.name,
            "arg_types": [str(t) for t in target.arg_types],
            "result_type": str(target.result_type),
            "signature_text": target.contract_grades.get("signature_text", ""),
        },
        "flags": {"cause": "SEMANTICS",           # Stage-A ground truth for CFL
                  "forced_within_budget": True,
                  "full_language_solves": solved_full,
                  "search_budget_s": config.search_budget_s},
        "demonstrations": [{"input": a.tolist(), "output": b.tolist()}
                           for a, b in pairs],
        "generator_program_nodes": _count_nodes(program),   # size only, never the AST
    }


def _count_nodes(ast) -> int:
    if not (isinstance(ast, tuple) and len(ast) == 2):
        return 0
    return 1 + sum(_count_nodes(a) for a in ast[1])


# --------------------------------------------------------------------------
# dataset generation
# --------------------------------------------------------------------------

def family_of(name: str) -> str:
    """Family key for holdout splits: the base name before any '@' grounding."""
    return name.split("@")[0]


def generate(out_path: Path, episodes_per_production: int, seed: int,
             holdout_families: Sequence[str] = (),
             productions: Sequence[str] | None = None,
             config: EpisodeConfig = EpisodeConfig()) -> dict:
    """Write a Stage-A dataset (train + family-holdout files) and its manifest."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    names = sorted(productions if productions is not None else V.REGISTRY)
    rows_train, rows_holdout, skipped = [], [], {}
    for name in names:
        made, attempts = 0, 0
        rng = np.random.default_rng(
            int.from_bytes(hashlib.sha256(f"{seed}:{name}".encode()).digest()[:8],
                           "big"))
        while made < episodes_per_production and attempts < episodes_per_production * 20:
            attempts += 1
            row = episode(rng, name, config)
            if row is None:
                continue
            row["episode_seed"] = f"{seed}:{name}:{made}"
            (rows_holdout if family_of(name) in holdout_families
             else rows_train).append(row)
            made += 1
        if made < episodes_per_production:
            skipped[name] = {"made": made, "attempts": attempts}
    train_path = out_path.with_suffix(".train.jsonl")
    holdout_path = out_path.with_suffix(".family_holdout.jsonl")
    for path, rows in ((train_path, rows_train), (holdout_path, rows_holdout)):
        path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    manifest = {
        "stage": "GPN curriculum Stage A: operator dropout",
        "seed": seed,
        "episodes_per_production": episodes_per_production,
        "productions": names,
        "holdout_families": sorted(holdout_families),
        "search_budget_s": config.search_budget_s,
        "counts": {"train": len(rows_train), "family_holdout": len(rows_holdout)},
        "under_target": skipped,
        "registry_fingerprint": hashlib.sha256(
            json.dumps(sorted(V.REGISTRY), sort_keys=True).encode()).hexdigest(),
        "files": {train_path.name: hashlib.sha256(
                      train_path.read_bytes()).hexdigest(),
                  holdout_path.name: hashlib.sha256(
                      holdout_path.read_bytes()).hexdigest()},
    }
    out_path.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True))
    return manifest
