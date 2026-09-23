"""Learned-verb runtime (AUTONOMOUS M2/M3 — the self-extending vocabulary).

A learned verb is a CHAIN of primitive cell-set combinators discovered by
the chain miner (scripts/meta_m2_chain_miner.py), validated by retro-solve
(M3), and registered in a ``learned_verbs.json`` file that the engine loads
per run — the vocabulary extends BETWEEN runs, never within a task
(META_INDUCTION_DESIGN legality constraint 3).

Detection semantics (SYNTH_COPY delta): an orphan output object whose
normalized cells equal ``chain(source.cells)`` for some input object and
some registered verb, with a uniform color or the source's carried colors.
Rendering: apply the chain to self's cells, stamp at ``placement`` with
``color`` (both induced through the normal expression grammar — slots per
D15).  All chain functions are pure and fold-safe.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import numpy as np

#: The combinator catalog shared with the miner.  Names are the canonical
#: vocabulary; every chain is a tuple of (name, slot) pairs.
def _cells_array(cells):
    h = max(r for r, _ in cells) + 1
    w = max(c for _, c in cells) + 1
    a = np.zeros((h, w), dtype=int)
    for r, c in cells:
        a[r, c] = 1
    return a


def _array_cells(a):
    return {(int(r), int(c)) for r, c in zip(*np.nonzero(a))}


def _norm(cells):
    if not cells:
        return frozenset()
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    return frozenset((r - r0, c - c0) for (r, c) in cells)


def _mirror_h(cells, slot=None):
    h = max(r for r, _ in cells)
    return {(h - r, c) for (r, c) in cells}


def _mirror_v(cells, slot=None):
    w = max(c for _, c in cells)
    return {(r, w - c) for (r, c) in cells}


def _rot(cells, k):
    return _array_cells(np.rot90(_cells_array(cells), int(k)))


def _scale_up(cells, k):
    k = int(k)
    return {(r * k + i, c * k + j) for (r, c) in cells
            for i in range(k) for j in range(k)}


def _scale_down(cells, k):
    k = int(k)
    out = {(r // k, c // k) for (r, c) in cells}
    return out if _scale_up(out, k) == set(cells) else None


COMBINATORS = {
    "mirror_h": _mirror_h,
    "mirror_v": _mirror_v,
    "rot": _rot,
    "scale_up": _scale_up,
    "scale_down": _scale_down,
}


def apply_verb_chain(chain, cells) -> Optional[frozenset]:
    """Apply a registered chain to a cell set; None when undefined."""
    cur = set(cells)
    for name, slot in chain:
        fn = COMBINATORS.get(name)
        if fn is None:
            return None
        cur = fn(cur, slot) if slot is not None else fn(cur)
        if not cur:
            return None
        cur = set(_norm(cur))
    return frozenset(cur)


class LearnedVerbRegistry:
    """learned_verbs.json loader (engine-dir scoped, like library.json)."""

    def __init__(self, verbs: list[dict]):
        self.verbs = verbs

    @classmethod
    def load(cls, out_dir: Optional[str]) -> "LearnedVerbRegistry":
        path = os.path.join(out_dir or "", "learned_verbs.json")
        if out_dir and os.path.exists(path):
            try:
                return cls(json.load(open(path)))
            except Exception:
                pass
        return cls([])

    def match_orphan(self, src_cc: dict, orphan_cc: dict) -> Optional[dict]:
        """First registered verb whose chain maps the source's normalized
        mask onto the orphan's.  Returns raw delta params or None.  Colors:
        the orphan must be uniform (color slot) or carry the source's
        colors through the transform (relational carry)."""
        src_norm = _norm(src_cc)
        orph_norm = _norm(orphan_cc)
        if not src_norm or len(src_norm) < 2:
            return None                    # single cells match trivially
        for v in self.verbs:
            chain = [tuple(x) for x in v["chain"]]
            res = apply_verb_chain(chain, src_norm)
            if res != orph_norm:
                continue
            ocolors = set(orphan_cc.values())
            params: dict[str, Any] = {
                "verb": v["name"],
                "placement": (
                    min(r for r, _ in orphan_cc)
                    - min(r for r, _ in src_cc),
                    min(c for _, c in orphan_cc)
                    - min(c for _, c in src_cc)),
            }
            if len(ocolors) == 1:
                params["color"] = int(next(iter(ocolors)))
            return params
        return None

    def chain_of(self, name: str):
        for v in self.verbs:
            if v["name"] == name:
                return [tuple(x) for x in v["chain"]]
        return None
