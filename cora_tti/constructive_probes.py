"""Frozen finite probe set and behaviour fingerprints (Item-2 Block B).

The probe set is a pure deterministic function of the frozen v1.1 protocol
configuration (root seed, count, size range, component-count range). It never
sees a target AST, digest, structural family, split, candidate score,
candidate output, model state, DEV task, or hidden output: the probe module
takes no such argument anywhere in its public API.

A behaviour fingerprint is the SHA-256 of the ordered renderings of a
CONCRETE (fully instantiated) program over all frozen probes, with explicit
dimension headers, delimiters, and an explicit UNDEFINED marker so that a
None rendering can never collide with a real grid, and no two differently
shaped grids can collide through flattening.

Candidates equal under this fingerprint are WITNESS-EQUIVALENT (equivalently:
frozen-probe behaviourally equal). That is a bounded finite-probe statement
and never a claim of semantic equivalence.
"""
from __future__ import annotations

import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from cora_tti.constructive_vocabulary import manifest      # noqa: E402

UNDEFINED = b"<UNDEFINED>"
ERROR_PREFIX = "ERROR:"          # audit diagnostics only; never an admission value


def probe_config() -> dict:
    """Consumed from the frozen manifest; never retyped."""
    p = manifest()["probes"]
    return {"count": p["count"], "seed": p["seed"],
            "min_size": p["sizes"][0], "max_size": p["sizes"][1],
            "min_components": p["components"][0],
            "max_components": p["components"][1]}


def _probe_grid(index: int, config: dict) -> np.ndarray:
    """One probe grid: rectangular components on a zero background.

    Deterministic in (root seed, index) alone.
    """
    rng = np.random.default_rng(config["seed"] * 1000 + index)
    size_span = config["max_size"] - config["min_size"] + 1
    height = int(config["min_size"] + rng.integers(0, size_span))
    width = int(config["min_size"] + rng.integers(0, size_span))
    grid = np.zeros((height, width), dtype=int)
    n_components = int(config["min_components"]
                       + rng.integers(0, config["max_components"]
                                      - config["min_components"] + 1))
    for component in range(n_components):
        h = int(1 + rng.integers(0, min(3, height - 1)))
        w = int(1 + rng.integers(0, min(3, width - 1)))
        r0 = int(rng.integers(0, max(1, height - h)))
        c0 = int(rng.integers(0, max(1, width - w)))
        grid[r0:r0 + h, c0:c0 + w] = int(1 + rng.integers(0, 9))
    return grid


@lru_cache(maxsize=1)
def probes() -> tuple:
    config = probe_config()
    return tuple(_probe_grid(i, config) for i in range(config["count"]))


def _grid_digest(grid: np.ndarray) -> str:
    payload = f"{grid.shape[0]}x{grid.shape[1]}:".encode() + grid.astype(int).tobytes()
    return hashlib.sha256(payload).hexdigest()[:16]


def probe_manifest() -> dict:
    """Canonical probe record: index, seed, dimensions, components, digest.
    Carries no target-conditioned information."""
    config = probe_config()
    rows = []
    for index, grid in enumerate(probes()):
        rows.append({"index": index,
                     "seed": config["seed"] * 1000 + index,
                     "height": int(grid.shape[0]), "width": int(grid.shape[1]),
                     "distinct_colours": int(len(np.unique(grid))),
                     "grid_digest": _grid_digest(grid)})
    return {"config": config, "probes": rows,
            "probe_set_digest": hashlib.sha256(
                json.dumps(rows, sort_keys=True).encode()).hexdigest()}


def _serialize_rendering(rendered) -> bytes:
    if rendered is None:
        return UNDEFINED
    array = np.asarray(rendered, dtype=int)
    return (f"{array.shape[0]}x{array.shape[1]}:".encode()
            + b",".join(str(int(v)).encode() for v in array.reshape(-1)))


def fingerprint(concrete_ast, evaluate_fn) -> str:
    """SHA-256 over the ordered renderings of a CONCRETE program.

    evaluate_fn(ast, grid) -> ndarray or None. An exception during
    fingerprinting propagates: an erroring candidate is REJECTED at
    admission, never silently treated as UNDEFINED.
    """
    parts = []
    for grid in probes():
        parts.append(_serialize_rendering(evaluate_fn(concrete_ast, grid)))
    return hashlib.sha256(b"|".join(parts)).hexdigest()


def fingerprint_with_diagnostics(concrete_ast, evaluate_fn) -> tuple:
    """Audit-only variant: returns (fingerprint, per-probe status list) and
    records ERROR:<class> instead of raising. Never used for admission."""
    parts, status = [], []
    for grid in probes():
        try:
            rendered = evaluate_fn(concrete_ast, grid)
            parts.append(_serialize_rendering(rendered))
            status.append("UNDEFINED" if rendered is None else "OK")
        except Exception as error:            # noqa: BLE001 - audit path only
            marker = f"{ERROR_PREFIX}{type(error).__name__}"
            parts.append(marker.encode())
            status.append(marker)
    return hashlib.sha256(b"|".join(parts)).hexdigest(), status


def defined_probe_count(concrete_ast, evaluate_fn) -> int:
    return sum(1 for grid in probes()
               if evaluate_fn(concrete_ast, grid) is not None)
