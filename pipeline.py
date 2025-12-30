from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np

# Local modules from Step 1
from components import Grid, Scene, Component, extract_scene
from features import compute_scene_features, compute_pair_features, SceneFeatures, PairFeatures
from topology import euler_betti_from_coords, Topology
from shape_features import (
    pca_from_coords,
    freeman_chain_code,
    thickness_from_mask,
    skeleton_stats,
)
from extras import (
    adjacency8, color_adjacency, detect_periodicity, has_singletons,
    invariants_for_pair, detect_object_transform, Periodicity, Invariants,
)
from neurosym_modules import (
    encode_graph, encode_hypergraph, cell_complex_from_component,
    GraphEncoding, HypergraphEncoding, CellComplex,
)

# =========================
# Rich component augmentation
# =========================
@dataclass
class RichComponent:
    base: Component
    topology: Topology
    cell_complex: CellComplex
    pca_cx: float
    pca_cy: float
    pca_angle_rad: float
    pca_elongation: float
    chain_len: int
    chain_canonical: Tuple[int, ...]
    thickness_diam: Optional[float]
    thickness_mean_r: Optional[float]
    skel_len: Optional[int]
    skel_endpoints: Optional[int]
    skel_junctions: Optional[int]


@dataclass
class SceneBundle:
    scene: Scene
    scene_features: SceneFeatures
    # adjacency supplements
    adj8: Dict[Tuple[int, int], bool]
    color_graph: Dict[Tuple[int, int], bool]
    periodicity: Periodicity
    has_singletons: bool
    rich_components: List[RichComponent]
    graph_encoding: GraphEncoding
    hypergraph_encoding: HypergraphEncoding


@dataclass
class PairBundle:
    pair_features: PairFeatures
    invariants: Invariants
    # mapping per matched input component id → transform flags
    object_transforms: Dict[int, Dict[str, int]]  # {comp_id_in: {"dr":..,"dc":..,"rot90":.., ...}}


# =========================
# Builders
# =========================
def _mask_from_component(grid: Grid, comp: Component) -> np.ndarray:
    r0, c0, r1, c1 = comp.bbox
    box = grid.data[r0:r1, c0:c1]
    mask = np.zeros_like(box, dtype=np.uint8)
    mask[(comp.pixels[:, 0] - r0, comp.pixels[:, 1] - c0)] = 1
    return mask


def build_scene_bundle(grid: Grid, connectivity: int = 4) -> SceneBundle:
    scene = extract_scene(grid, connectivity=connectivity)
    sf = compute_scene_features(grid, scene)

    # adjacency & color graphs
    adj8_map = adjacency8(scene)
    color_graph = color_adjacency(scene, use8=True)

    # periodicity & singletons
    per = detect_periodicity(grid)
    singles = has_singletons(grid)

    # enrich components with topology/PCA/chain/thickness/skeleton
    rich: List[RichComponent] = []
    for c in scene.comps:
        topo = euler_betti_from_coords(c.pixels)
        cell = cell_complex_from_component(grid, c)

        # PCA
        pca = pca_from_coords(c.pixels)

        # boundary chain
        m = _mask_from_component(grid, c)
        ch = freeman_chain_code(m)
        chain_len = 0 if ch is None else ch.length

        # canonicalized chain (rotation/flip invariance) — simple lexicographic min over all cyclic shifts & reversals
        if ch is None:
            canonical: Tuple[int, ...] = tuple()
        else:
            code = [d % 8 for d in ch.code]
            variants: List[Tuple[int, ...]] = []
            for s in range(len(code)):
                sh = code[s:] + code[:s]
                variants.append(tuple(sh))
                rev = tuple(((-d) % 8) for d in reversed(sh))
                variants.append(rev)
            canonical = min(variants) if variants else tuple()

        # thickness & skeleton (optional deps)
        th = thickness_from_mask(m)
        sk = skeleton_stats(m)

        rich.append(
            RichComponent(
                base=c,
                topology=topo,
                cell_complex=cell,
                pca_cx=pca.cx,
                pca_cy=pca.cy,
                pca_angle_rad=pca.angle_rad,
                pca_elongation=pca.elongation,
                chain_len=chain_len,
                chain_canonical=canonical,
                thickness_diam=None if th is None else th.max_diameter,
                thickness_mean_r=None if th is None else th.mean_radius,
                skel_len=None if sk is None else sk.length,
                skel_endpoints=None if sk is None else sk.endpoints,
                skel_junctions=None if sk is None else sk.junctions,
            )
        )

    # Graph & Hypergraph encodings
    ge = encode_graph(scene)
    he = encode_hypergraph(scene, grid)

    return SceneBundle(
        scene=scene,
        scene_features=sf,
        adj8=adj8_map,
        color_graph=color_graph,
        periodicity=per,
        has_singletons=singles,
        rich_components=rich,
        graph_encoding=ge,
        hypergraph_encoding=he,
    )


def build_pair_bundle(inp: Grid, out: Grid) -> PairBundle:
    in_scene = extract_scene(inp, connectivity=4)
    out_scene = extract_scene(out, connectivity=4)
    pair = compute_pair_features(inp, in_scene, out, out_scene)
    inv = invariants_for_pair(inp, out)

    # per-object transforms for matched components in pair_features
    from features import match_components  # local import to avoid cycles
    matches = match_components(in_scene, out_scene)

    transforms: Dict[int, Dict[str, int]] = {}
    for m in matches:
        a = in_scene.comps[m.i_in]
        b = out_scene.comps[m.i_out]
        tr = detect_object_transform(inp, a, out, b)
        transforms[m.i_in] = {
            "dr": tr.dr,
            "dc": tr.dc,
            "translated": int(tr.translated),
            "reflected_h": int(tr.reflected_h),
            "reflected_v": int(tr.reflected_v),
            "rot90": int(tr.rotated_90),
            "rot180": int(tr.rotated_180),
            "rot270": int(tr.rotated_270),
        }

    return PairBundle(pair_features=pair, invariants=inv, object_transforms=transforms)


# =========================
# Convenience end-to-end APIs
# =========================
def analyze_single_grid(grid_array: np.ndarray) -> SceneBundle:
    """Top-level convenience: numpy int8 grid → full scene bundle."""
    g = Grid(grid_array.astype(np.int8))
    return build_scene_bundle(g)


def analyze_pair_grids(inp_array: np.ndarray, out_array: np.ndarray) -> Tuple[SceneBundle, SceneBundle, PairBundle]:
    """Top-level convenience: two numpy int8 grids → their bundles + pair analysis."""
    gi = Grid(inp_array.astype(np.int8))
    go = Grid(out_array.astype(np.int8))
    return build_scene_bundle(gi), build_scene_bundle(go), build_pair_bundle(gi, go)


# =========================
# Policy integration hooks — ARC-legal guidance
# (lazy imports avoid circular dependencies)
# =========================
def build_policy_priors(bundle: SceneBundle, policy=None):
    """
    Return (p_object, p_primitive) priors for the given scene bundle and policy.

    ARC-AGI-2 tip: call this offline and cache outputs; during official evaluation
    you can load cached priors instead of running any neural code.
    """
    from policy_adapter import primitives_catalog, get_policy_priors
    num_primitives = len(primitives_catalog())
    return get_policy_priors(bundle, num_primitives=num_primitives, policy=policy)


def rank_candidates_with_policy(
    bundle: SceneBundle,
    candidates,
    policy=None,
    alpha: float = 0.6,
    beta: float = 0.4,
    mdl_temp: float = 1.0,
):
    """
    Blend MDL/invariant scores with policy priors to rank candidates.
    `candidates` should be a list of policy_adapter.Candidate objects.
    Returns a list of policy_adapter.Ranked objects.
    """
    from policy_adapter import apply_priors_to_candidates
    p_obj, p_prim = build_policy_priors(bundle, policy=policy)
    return apply_priors_to_candidates(candidates, p_obj, p_prim, alpha=alpha, beta=beta, mdl_temp=mdl_temp)


if __name__ == "__main__":
    # Smoke test
    inp = np.array(
        [
            [0, 0, 1, 1, 0],
            [0, 0, 1, 1, 0],
            [2, 0, 0, 0, 0],
            [2, 2, 0, 3, 3],
            [0, 0, 0, 3, 3],
        ],
        dtype=np.int8,
    )
    out = np.array(
        [
            [0, 0, 1, 1, 0],
            [0, 0, 1, 1, 0],
            [0, 0, 0, 0, 2],
            [2, 2, 0, 3, 3],
            [0, 0, 0, 3, 3],
        ],
        dtype=np.int8,
    )
    sb_in = analyze_single_grid(inp)
    sb_out = analyze_single_grid(out)
    _, _, pb = analyze_pair_grids(inp, out)
    print("rich comps (in):", len(sb_in.rich_components))
    print("pair invariants:", pb.invariants)
    print("object transforms:", pb.object_transforms)
