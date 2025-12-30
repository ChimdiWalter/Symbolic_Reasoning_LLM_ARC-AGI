from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import numpy as np

# Optional torch dependency
try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None  # type: ignore
    nn = object    # type: ignore

# =========================
# Primitive catalog (placeholder)
# =========================
def primitives_catalog() -> List[str]:
    """
    Return the list of DSL primitive names in a fixed order.
    Replace this with your dsl.py registry so indices stay stable.
    """
    return [
        # selection
        "objects", "largest", "with_holes", "touching",
        # transforms
        "translate", "reflect", "rotate",
        # paint/compose
        "paint", "copy_to", "map_colors",
        # morphology
        "dilate", "erode", "fill_holes",
        # counts/stats
        "count", "mode_color", "argmax",
    ]


# =========================
# Object feature tensors
# =========================
def object_feature_matrix(bundle, use_numpy: bool = False):
    """
    Build an (N_objs, D) feature matrix from SceneBundle.rich_components.

    Features: color (one-hot 10), area, bbox_w,h, centroid_r,c, holes, chi,
    border_touch flag, PCA elongation, chain length, thickness, skeleton stats.
    """
    comps = getattr(bundle, "rich_components", [])
    if not comps:
        return np.zeros((0, 0), dtype=np.float32)

    N = len(comps)
    D = 10 + 12  # 10 color one-hot + 12 scalar features below
    X = np.zeros((N, D), dtype=np.float32)

    for i, rc in enumerate(comps):
        # one-hot color 0..9
        color = int(rc.base.color)
        if 0 <= color <= 9:
            X[i, color] = 1.0
        # scalar block
        col = 10
        r0, c0, r1, c1 = rc.base.bbox
        bw = float(c1 - c0)
        bh = float(r1 - r0)
        scalars = [
            float(rc.base.area), bw, bh,
            float(rc.base.centroid[0]), float(rc.base.centroid[1]),
            float(rc.topology.betti1), float(rc.topology.euler),
            1.0 if rc.base.touches_border else 0.0,
            float(rc.pca_elongation),
            float(rc.chain_len),
            float(0.0 if rc.thickness_diam is None else rc.thickness_diam),
            float(0.0 if rc.skel_len is None else rc.skel_len),
        ]
        X[i, col:col+len(scalars)] = np.asarray(scalars, dtype=np.float32)

    if use_numpy or torch is None:
        return X
    else:
        return torch.tensor(X)  # type: ignore


# =========================
# Policy inference → priors
# =========================
def get_policy_priors(bundle, num_primitives: int, policy: Optional[object] = None):
    """
    Return (p_object, p_primitive) as numpy arrays or torch tensors depending on availability.
    If no policy/torch is available, return uniform priors.
    """
    comps = getattr(bundle, "rich_components", [])
    N = len(comps)

    if N == 0:
        # edge case: no components
        if torch is None:
            return np.ones((0,), dtype=np.float32), np.ones((num_primitives,), dtype=np.float32) / max(num_primitives, 1)
        else:
            return torch.ones((0,)), torch.ones((num_primitives,)) / max(num_primitives, 1)

    if torch is None or policy is None:
        # uniform priors (ARC-legal)
        if torch is None:
            p_obj = np.ones((N,), dtype=np.float32) / N
            p_prim = np.ones((num_primitives,), dtype=np.float32) / max(num_primitives, 1)
            return p_obj, p_prim
        else:
            p_obj = torch.ones((N,)) / N  # type: ignore
            p_prim = torch.ones((num_primitives,)) / max(num_primitives, 1)  # type: ignore
            return p_obj, p_prim

    # If a policy is provided, call it. (Policy may optionally use object features; this stub doesn't yet.)
    out = policy.forward()  # expected to return {"p_object": ..., "p_primitive": ...}
    return out["p_object"], out["p_primitive"]


# =========================
# Candidate ranking with priors
# =========================
@dataclass
class Candidate:
    program: object         # your DSL AST or callable
    md_length: float        # MDL length (lower is better)
    invariants_ok: bool     # hard filter
    touched_objects: List[int]  # component ids
    used_primitives: List[int]  # indices into primitives_catalog()


@dataclass
class Ranked:
    program: object
    score: float


def apply_priors_to_candidates(
    cands: List[Candidate],
    p_object,
    p_primitive,
    alpha: float = 0.6,
    beta: float = 0.4,
    mdl_temp: float = 1.0
) -> List[Ranked]:
    """
    Blend symbolic scores (MDL) with neuro priors to rank candidates.

    score = - mdl_temp * md_length  +  alpha * mean(p_object[touched])  +  beta * mean(p_primitive[used])

    Candidates with invariants_ok=False are dropped.
    Works with numpy or torch tensors for p_object/p_primitive.
    """
    ranked: List[Ranked] = []

    # helper to fetch probabilities agnostic to backend
    def mean_prob(vec, idxs: List[int]) -> float:
        if len(idxs) == 0:
            return 0.0
        if torch is not None and isinstance(vec, torch.Tensor):
            return float(vec[idxs].mean().item())
        else:
            v = np.asarray(vec)
            return float(v[idxs].mean())

    for c in cands:
        if not c.invariants_ok:
            continue
        p_obj = mean_prob(p_object, c.touched_objects)
        p_prm = mean_prob(p_primitive, c.used_primitives)
        score = - mdl_temp * float(c.md_length) + alpha * p_obj + beta * p_prm
        ranked.append(Ranked(program=c.program, score=score))

    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked


# =========================
# Smoke test (uniform priors)
# =========================
if __name__ == "__main__":
    class FakeBase: ...
    class FakeComp:
        def __init__(self):
            self.base = type("B", (), {"color": 1, "area": 5, "bbox": (0,0,2,3), "centroid": (0.5,1.0), "touches_border": False})()
            self.topology = type("T", (), {"betti1": 0, "euler": 1})()
            self.pca_elongation = 1.0
            self.chain_len = 6
            self.thickness_diam = 2.0
            self.skel_len = 4
    fake = type("Bundle", (), {"rich_components": [FakeComp(), FakeComp()]})()

    X = object_feature_matrix(fake, use_numpy=True)
    print("X shape:", X.shape)

    p_obj, p_prim = get_policy_priors(fake, num_primitives=len(primitives_catalog()), policy=None)
    cands = [Candidate(program=f"prog{i}", md_length=10+i, invariants_ok=True, touched_objects=[0], used_primitives=[i % 3]) for i in range(5)]
    ranked = apply_priors_to_candidates(cands, p_obj, p_prim)
    print([r.score for r in ranked])
