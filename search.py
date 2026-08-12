from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np

from components import Grid
from pipeline import build_scene_bundle, build_pair_bundle
from dsl import Program, Apply, Var, CColor, CInt, CVec

# Early prune
try:
    # User may have the file name as 'Prune' (capitalized) or 'prune'
    from Prune import early_prune_candidates, PruneStats  # type: ignore
except Exception:
    from prune import early_prune_candidates, PruneStats  # type: ignore

# -----------------------------
# Config used by solver_plus
# -----------------------------
@dataclass
class GenConfig:
    beam: int = 256
    max_depth: int = 2
    use_policy: bool = False
    max_trans_offset: int = 2  # translation grid for simple generators

# -----------------------------
# Tiny DSL program builders
# -----------------------------
def identity_program() -> Program:
    # Returning Var("grid") is identity under Program.run()
    return Program(Var("grid"), description="identity")

def paint_largest(c_from: int, c_to: int) -> Program:
    term = Apply("paint", [
        Var("grid"),
        Apply("largest", [Apply("objects", [CColor(int(c_from))])]),
        CColor(int(c_to))
    ])
    return Program(term, description=f"paint largest {c_from}->{c_to}")

def translate_color(c: int, dr: int, dc: int) -> Program:
    term = Apply("translate", [
        Apply("objects", [CColor(int(c))]),
        CVec(int(dr), int(dc))
    ])
    return Program(term, description=f"translate {c} by ({dr},{dc})")

def reflect_color(c: int, axis: int) -> Program:
    # axis: 0=horizontal, 1=vertical (consistent with your DSL)
    term = Apply("reflect", [
        Apply("objects", [CColor(int(c))]),
        CInt(int(axis))
    ])
    return Program(term, description=f"reflect {c} axis {axis}")

# -----------------------------
# Candidate generator
# -----------------------------
def _enumerate_candidates(train_pairs: List[Tuple[Grid, Grid]], cfg: GenConfig) -> List[Program]:
    """Generate a small list of plausible candidates quickly."""
    # Look at the first input to restrict colors present
    x0, y0 = train_pairs[0]
    pal_x = sorted(int(x) for x in np.unique(x0.data))
    pal_y = sorted(int(y) for y in np.unique(y0.data))

    progs: List[Program] = []
    # Always include identity (sometimes correct)
    progs.append(identity_program())

    # Paint-largest (from colors in x -> colors in y), limited by beam budget
    for cf in pal_x:
        if cf == 0:  # skip background as "largest color" (usually not an object)
            continue
        for ct in pal_y:
            progs.append(paint_largest(cf, ct))
            if len(progs) >= cfg.beam:
                return progs

    # Small translations of prominent colors present in x0
    maxo = int(cfg.max_trans_offset)
    for c in pal_x:
        if c == 0:
            continue
        for dr in range(-maxo, maxo + 1):
            for dc in range(-maxo, maxo + 1):
                if dr == 0 and dc == 0:
                    continue
                progs.append(translate_color(c, dr, dc))
                if len(progs) >= cfg.beam:
                    return progs

    # Simple reflections
    for c in pal_x:
        if c == 0:
            continue
        for axis in (0, 1):
            progs.append(reflect_color(c, axis))
            if len(progs) >= cfg.beam:
                return progs

    return progs

# -----------------------------
# Public API expected by solver_plus
# -----------------------------
def enumerate_and_rank(
    train_pairs: List[Tuple[Grid, Grid]],
    scene_bundle=None,
    gen_cfg: Optional[GenConfig] = None,
    policy=None,
    k: Optional[int] = None
) -> List[Program]:
    """
    Return a ranked list of Programs for the given training pairs.
    - Generates a small pool
    - Early-prunes by simulating on the first pair
    - Verifies over all pairs
    - Returns up to k (or cfg.beam) programs
    """
    if gen_cfg is None:
        gen_cfg = GenConfig()

    # generate
    pool = _enumerate_candidates(train_pairs, gen_cfg)

    # early prune on first pair only
    x0, y0 = train_pairs[0]
    kept, _stats = early_prune_candidates(x0, y0, pool)

    # verify all train pairs
    verified: List[Program] = []
    for p in kept:
        if verify_on_pairs(p, train_pairs):
            verified.append(p)
            if len(verified) >= (k or gen_cfg.beam):
                break

    # Fallbacks: if nothing verified, still return a few plausible candidates
    if not verified:
        verified = kept[: (k or gen_cfg.beam)]
        if not verified:
            verified = pool[: (k or gen_cfg.beam)]
    return verified

def verify_on_pairs(prog: Program, train_pairs: List[Tuple[Grid, Grid]]) -> bool:
    """Return True iff prog(x)==y for ALL training pairs (exact grid match)."""
    try:
        for x, y in train_pairs:
            bundle = build_scene_bundle(x)
            yhat = prog.run(x, bundle)
            if yhat.data.shape != y.data.shape:
                return False
            if not np.array_equal(yhat.data, y.data):
                return False
        return True
    except Exception:
        return False

# -----------------------------
# Back-compat: accept "beamsize" kw for GenConfig
# -----------------------------
try:
    _OrigGenConfig = GenConfig  # type: ignore[name-defined]
except Exception:
    _OrigGenConfig = None

if _OrigGenConfig is not None:
    # Wrap the existing class to accept beamsize, keep other behavior/attrs
    class _CompatGenConfig(_OrigGenConfig):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            # Alias beamsize -> beam if provided
            if "beamsize" in kwargs and "beam" not in kwargs:
                kwargs["beam"] = kwargs.pop("beamsize")
            super().__init__(*args, **kwargs)
    GenConfig = _CompatGenConfig  # type: ignore[assignment]
else:
    # Define a minimal GenConfig if none exists (future-proof)
    class GenConfig:  # type: ignore[no-redef]
        def __init__(self, max_depth=2, beam=64, beamsize=None, **kwargs):
            if beamsize is not None:
                beam = beamsize
            self.max_depth = max_depth
            self.beam = beam
            # Preserve any extra knobs used by callers
            for k, v in kwargs.items():
                setattr(self, k, v)
