from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Iterable
import numpy as np

# Local types
try:
    from components import Grid, Scene, Component, extract_scene
except Exception:
    # light fallback so type hints don't crash before imports are ready
    Grid = Any  # type: ignore
    Scene = Any  # type: ignore
    Component = Any  # type: ignore
    def extract_scene(grid, connectivity=4):  # type: ignore
        raise RuntimeError("extract_scene not available; import components first.")

RC = Tuple[int, int]

@dataclass
class Graph:
    """
    Minimal object graph for ARC scenes.
    - nodes: {id: {color, area, centroid, bbox, holes, perim4, touches_border}}
    - edges: List[(u, v)] undirected (u < v)
    - adj:   {id: [neighbor ids]}
    - meta:  shape, palette, counts
    """
    nodes: Dict[int, Dict[str, Any]]
    edges: List[Tuple[int, int]]
    adj: Dict[int, List[int]]
    meta: Dict[str, Any]

def _bbox_from_pixels(px: np.ndarray) -> Tuple[int,int,int,int]:
    r0 = int(px[:,0].min()); r1 = int(px[:,0].max()) + 1
    c0 = int(px[:,1].min()); c1 = int(px[:,1].max()) + 1
    return (r0, c0, r1, c1)

def _centroid_from_pixels(px: np.ndarray) -> Tuple[float,float]:
    return (float(px[:,0].mean()), float(px[:,1].mean()))

def _label_image_from_scene(scene: Scene, H: int, W: int) -> np.ndarray:
    """Label grid with component indices (>=0), background = -1."""
    lab = -np.full((H, W), fill_value=1, dtype=np.int32)  # temp 1 to avoid overflow
    lab[:] = -1
    for i, comp in enumerate(scene.comps):
        rrcc = comp.pixels  # expected shape (N,2)
        lab[(rrcc[:,0], rrcc[:,1])] = i
    return lab

def _edges_via_grid_contacts(lab: np.ndarray) -> List[Tuple[int,int]]:
    """Edges when two different labels touch in 4-neighborhood somewhere in the grid."""
    H, W = lab.shape
    edges = set()
    # right/down scan is enough to catch each adjacency once
    if W > 1:
        a = lab[:, :-1]
        b = lab[:, 1:]
        mask = (a != b) & (a >= 0) & (b >= 0)
        if mask.any():
            us = a[mask].ravel(); vs = b[mask].ravel()
            for u, v in zip(us.tolist(), vs.tolist()):
                if u != v:
                    e = (u, v) if u < v else (v, u)
                    edges.add(e)
    if H > 1:
        a = lab[:-1, :]
        b = lab[1:, :]
        mask = (a != b) & (a >= 0) & (b >= 0)
        if mask.any():
            us = a[mask].ravel(); vs = b[mask].ravel()
            for u, v in zip(us.tolist(), vs.tolist()):
                if u != v:
                    e = (u, v) if u < v else (v, u)
                    edges.add(e)
    return sorted(edges)

def _palette_counts(arr: np.ndarray) -> Tuple[Tuple[int, ...], Dict[int, int]]:
    vals, cnts = np.unique(arr.astype(np.int16), return_counts=True)
    pal = tuple(int(v) for v in vals)
    counts = {int(v): int(c) for v, c in zip(vals, cnts)}
    return pal, counts

def _comp_features(i: int, comp: Component) -> Dict[str, Any]:
    # Component is expected to expose: color, pixels (Nx2), bbox, holes, perimeter4, centroid, touches_border
    px = comp.pixels if isinstance(comp.pixels, np.ndarray) else np.asarray(comp.pixels, dtype=np.int16)
    area = int(px.shape[0])
    try:
        bbox = comp.bbox
    except Exception:
        bbox = _bbox_from_pixels(px)
    try:
        centroid = tuple(float(x) for x in comp.centroid)
    except Exception:
        centroid = _centroid_from_pixels(px)
    feats = {
        "id": int(i),
        "color": int(comp.color),
        "area": area,
        "bbox": tuple(int(x) for x in bbox),
        "centroid": (float(centroid[0]), float(centroid[1])),
        "holes": int(getattr(comp, "holes", 0)),
        "perim4": int(getattr(comp, "perimeter4", 0)),
        "touches_border": bool(getattr(comp, "touches_border", False)),
    }
    return feats

def encode_graph(obj: Any, connectivity: int = 4) -> Graph:
    """
    Build an object-contact graph from:
      - Grid (preferred), or
      - Scene, or
      - np.ndarray (grid of ints 0..9)
    Returns Graph(nodes, edges, adj, meta) with plain Python/NumPy types only.
    """
    # Normalize to (Grid, Scene, arr)
    if hasattr(obj, "data") and hasattr(obj, "__class__") and obj.__class__.__name__ == "Grid":
        grid = obj
        arr = grid.data
        scene = extract_scene(grid, connectivity=connectivity)
    elif hasattr(obj, "comps"):  # looks like Scene
        scene = obj
        # attempt to recover shape
        H = int(max((int(c.bbox[2]) for c in scene.comps), default=0))
        W = int(max((int(c.bbox[3]) for c in scene.comps), default=0))
        arr = np.zeros((H, W), dtype=np.int16)
        for c in scene.comps:
            rrcc = c.pixels
            arr[(rrcc[:,0], rrcc[:,1])] = int(c.color)
    else:
        # assume numpy array
        arr = np.asarray(obj, dtype=np.int16)
        grid = Grid(arr)  # type: ignore
        scene = extract_scene(grid, connectivity=connectivity)

    H, W = arr.shape
    pal, counts = _palette_counts(arr)
    lab = _label_image_from_scene(scene, H, W)
    edges = _edges_via_grid_contacts(lab)

    nodes: Dict[int, Dict[str, Any]] = {}
    for i, comp in enumerate(scene.comps):
        nodes[i] = _comp_features(i, comp)

    adj: Dict[int, List[int]] = {i: [] for i in nodes}
    for u, v in edges:
        adj[u].append(v); adj[v].append(u)
    for i in adj:  # determinism
        adj[i] = sorted(set(adj[i]))

    meta = {
        "shape": (int(H), int(W)),
        "palette": pal,
        "color_counts": counts,
        "num_components": len(nodes),
    }
    return Graph(nodes=nodes, edges=edges, adj=adj, meta=meta)

# (Optional) simple signature for pruning/matching
def graph_signature(g: Graph) -> Dict[str, Any]:
    degs = sorted(len(g.adj[i]) for i in g.nodes)
    areas = sorted(g.nodes[i]["area"] for i in g.nodes)
    colors = sorted(g.nodes[i]["color"] for i in g.nodes)
    return {"deg_seq": degs, "areas": areas, "colors": colors, "num": len(g.nodes)}

__all__ = ["Graph", "encode_graph", "graph_signature"]

# -----------------------------
# Hypergraph encoding
# -----------------------------
from dataclasses import dataclass

@dataclass
class Hypergraph:
    """
    Minimal hypergraph over scene components.
    - nodes: same ids as Graph (component indices)
    - hyperedges: List[Tuple[str, Tuple[int, ...]]] where each hyperedge is
                  (kind, tuple_of_node_ids) with sorted, unique node ids
    - meta: arbitrary small info (palette, counts, shape)
    """
    nodes: Dict[int, Dict[str, Any]]
    hyperedges: List[Tuple[str, Tuple[int, ...]]]
    meta: Dict[str, Any]

def _color_groups_from_graph(g: Graph) -> List[Tuple[str, Tuple[int, ...]]]:
    by_color: Dict[int, List[int]] = {}
    for i, nd in g.nodes.items():
        by_color.setdefault(int(nd["color"]), []).append(int(i))
    edges = []
    for c, ids in by_color.items():
        if not ids: 
            continue
        ids = sorted(set(ids))
        edges.append(("color_group", tuple(ids)))
    return edges

def _contact_groups_from_graph(g: Graph) -> List[Tuple[str, Tuple[int, ...]]]:
    """
    Build hyperedges for each connected component in the contact graph,
    but ONLY across different colors (optional, cheap cue).
    """
    # Union-find over nodes using contact edges where colors differ
    parent = {i: i for i in g.nodes}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[rb] = ra

    for u, v in g.edges:
        if g.nodes[u]["color"] != g.nodes[v]["color"]:
            union(u, v)

    groups: Dict[int, List[int]] = {}
    for i in g.nodes:
        r = find(i)
        groups.setdefault(r, []).append(i)

    edges = []
    for _, ids in groups.items():
        ids = sorted(set(ids))
        if len(ids) >= 2:
            edges.append(("contact_group", tuple(ids)))
    return edges

def encode_hypergraph(obj: Any, mode: str = "color+contact", connectivity: int = 4) -> Hypergraph:
    """
    Encode a scene into a simple hypergraph.
      - mode="color":       hyperedges are per-color groups
      - mode="contact":     hyperedges are contact-based groups (different colors connected)
      - mode="color+contact": both
    Accepts Grid, Scene, or numpy array (same as encode_graph).
    """
    g = encode_graph(obj, connectivity=connectivity)
    hedges: List[Tuple[str, Tuple[int, ...]]] = []
    if mode in ("color", "color+contact"):
        hedges.extend(_color_groups_from_graph(g))
    if mode in ("contact", "color+contact"):
        hedges.extend(_contact_groups_from_graph(g))
    meta = dict(g.meta)
    return Hypergraph(nodes=g.nodes, hyperedges=hedges, meta=meta)

def hypergraph_signature(hg: Hypergraph) -> Dict[str, Any]:
    kinds = [k for k, _ in hg.hyperedges]
    sizes = [len(ids) for _, ids in hg.hyperedges]
    return {"kinds": sorted(kinds), "sizes": sorted(sizes), "num_nodes": len(hg.nodes), "num_edges": len(hg.hyperedges)}

# Export new names
__all__ = list(set(globals().get("__all__", []) + ["Hypergraph", "encode_hypergraph", "hypergraph_signature"]))

# -----------------------------
# Cell complex from a component
# -----------------------------
from dataclasses import dataclass
from typing import Set

try:
    import numpy as _np
except Exception:
    import numpy as _np

from topology import euler_betti_from_coords as _betti

@dataclass
class CellComplex:
    """Very lightweight 2D cubical complex for one component."""
    vertices: list[tuple[int,int]]         # lattice points
    edges: list[tuple[tuple[int,int], tuple[int,int]]]  # unit segments
    faces: list[tuple[int,int]]            # pixel faces by (r,c) in local bbox frame
    euler: int
    beta0: int
    beta1: int
    meta: dict

def _component_mask_and_offset(comp) -> tuple[_np.ndarray, tuple[int,int]]:
    # Build a tight mask around the component in its bbox coordinates.
    px = comp.pixels if isinstance(comp.pixels, _np.ndarray) else _np.asarray(comp.pixels, dtype=_np.int16)
    r0, c0, r1, c1 = comp.bbox
    H, W = int(r1 - r0), int(c1 - c0)
    mask = _np.zeros((H, W), dtype=bool)
    mask[(px[:,0] - r0, px[:,1] - c0)] = True
    return mask, (int(r0), int(c0))

def _boundary_edges_from_mask(mask: _np.ndarray) -> set[tuple[tuple[int,int], tuple[int,int]]]:
    """Return set of 4-neighborhood boundary edges as unit lattice segments in local coords."""
    H, W = mask.shape
    E: Set[tuple[tuple[int,int], tuple[int,int]]] = set()
    # Horizontal edges: between (r,c)-(r,c+1) when mask[r-1,c] != mask[r,c]
    # Easier: check four sides of each face and add those with outside neighbor False
    for r in range(H):
        for c in range(W):
            if not mask[r, c]:
                continue
            # top edge
            if r == 0 or not mask[r-1, c]:
                E.add(((r, c), (r, c+1)))
            # bottom
            if r == H-1 or not mask[r+1, c]:
                E.add(((r+1, c), (r+1, c+1)))
            # left
            if c == 0 or not mask[r, c-1]:
                E.add(((r, c), (r+1, c)))
            # right
            if c == W-1 or not mask[r, c+1]:
                E.add(((r, c+1), (r+1, c+1)))
    return E

def cell_complex_from_component(comp) -> CellComplex:
    """
    Build a small cubical complex for a single component:
      - faces = foreground pixels in bbox-local coords
      - edges = boundary unit segments around faces (4-neighborhood)
      - vertices = endpoints of edges
    Also returns Euler characteristic and Betti numbers (β0, β1).
    """
    mask, (r0, c0) = _component_mask_and_offset(comp)
    H, W = mask.shape

    # Faces (local coordinates)
    faces = [(int(r), int(c)) for r, c in zip(*_np.where(mask))]

    # Edges & vertices
    edges = sorted(_boundary_edges_from_mask(mask))
    Vset: Set[tuple[int,int]] = set()
    for a, b in edges:
        Vset.add(a); Vset.add(b)
    vertices = sorted(Vset)

    # Topology (on original coords)
    coords_global = list(map(tuple, comp.pixels.tolist()))
    topo = _betti(coords_global, connectivity=4)

    # Euler from the complex as a sanity cross-check
    euler_complex = len(vertices) - len(edges) + len(faces)

    meta = {
        "bbox_origin": (r0, c0),
        "bbox_shape": (int(H), int(W)),
        "color": int(getattr(comp, "color", 0)),
        "area": int(getattr(comp, "area", len(faces))),
        "perim4": int(getattr(comp, "perimeter4", 0)),
        "touches_border": bool(getattr(comp, "touches_border", False)),
    }
    return CellComplex(
        vertices=vertices,
        edges=edges,
        faces=faces,
        euler=int(euler_complex),
        beta0=int(topo.beta0),
        beta1=int(topo.beta1),
        meta=meta,
    )

# Make sure it’s exported
__all__ = list(set(globals().get("__all__", []) + ["CellComplex", "cell_complex_from_component"]))

# -----------------------------
# GraphEncoding bundle
# -----------------------------
from dataclasses import dataclass

@dataclass
class GraphEncoding:
    """Bundle structural encodings for a scene/object."""
    graph: Graph
    hypergraph: Hypergraph
    complexes: dict[int, CellComplex]   # component_id -> CellComplex
    meta: dict

def build_graph_encoding(obj, connectivity: int = 4, hyper_mode: str = "color+contact") -> GraphEncoding:
    """
    Construct a unified structural encoding from Grid/Scene/np.ndarray:
      - contact graph over components
      - simple hypergraph (color + contact groups)
      - per-component cubical cell complexes
    """
    # Graph + Hypergraph
    g = encode_graph(obj, connectivity=connectivity)
    hg = encode_hypergraph(obj, mode=hyper_mode, connectivity=connectivity)

    # Per-component cell complexes (need a Scene)
    try:
        if hasattr(obj, "comps"):      # already a Scene
            scene = obj
        else:
            # Grid or ndarray
            arr = obj.data if hasattr(obj, "data") else np.asarray(obj, dtype=np.int16)
            grid = obj if hasattr(obj, "data") else Grid(arr)  # type: ignore
            scene = extract_scene(grid, connectivity=connectivity)
    except Exception:
        # Fallback: build from the graph metadata by re-extracting via Grid
        arr = obj.data if hasattr(obj, "data") else np.asarray(obj, dtype=np.int16)
        scene = extract_scene(Grid(arr), connectivity=connectivity)  # type: ignore

    complexes: dict[int, CellComplex] = {}
    for i, comp in enumerate(scene.comps):
        try:
            complexes[i] = cell_complex_from_component(comp)
        except Exception:
            # Keep pipeline robust even if a single component fails
            complexes[i] = CellComplex(vertices=[], edges=[], faces=[], euler=0, beta0=0, beta1=0,
                                       meta={"color": int(getattr(comp, "color", 0)),
                                             "bbox_origin": tuple(int(x) for x in getattr(comp, "bbox", (0,0,0,0))[:2]),
                                             "bbox_shape": (0,0)})

    meta = dict(g.meta)
    meta["num_complexes"] = len(complexes)
    return GraphEncoding(graph=g, hypergraph=hg, complexes=complexes, meta=meta)

# export
__all__ = list(set(globals().get("__all__", []) + ["GraphEncoding", "build_graph_encoding"]))

# -----------------------------
# Back-compat: HypergraphEncoding
# -----------------------------
# Many pipelines used the older name "HypergraphEncoding".
# Make it a direct alias of GraphEncoding so isinstance checks still work.
HypergraphEncoding = GraphEncoding  # runtime class alias

def build_hypergraph_encoding(obj, connectivity: int = 4, hyper_mode: str = "color+contact") -> GraphEncoding:
    """Back-compat wrapper; identical to build_graph_encoding."""
    return build_graph_encoding(obj, connectivity=connectivity, hyper_mode=hyper_mode)

# ensure exported
__all__ = list(set(globals().get("__all__", []) + ["HypergraphEncoding", "build_hypergraph_encoding"]))
# -----------------------------
# Back-compat: cell_complex_from_component(grid, comp)
# -----------------------------
try:
    _cc_core = cell_complex_from_component  # keep existing 1-arg impl
except NameError:  # shouldn't happen
    _cc_core = None

def cell_complex_from_component(*args):
    """
    Accepts:
      - cell_complex_from_component(comp)
      - cell_complex_from_component(grid, comp)   # grid is ignored
    """
    if _cc_core is None:
        raise RuntimeError("cell_complex_from_component core not found")
    if len(args) == 1:
        comp = args[0]
        return _cc_core(comp)
    elif len(args) == 2:
        _grid, comp = args
        return _cc_core(comp)
    else:
        raise TypeError("cell_complex_from_component expects (comp) or (grid, comp)")

# ensure exported
__all__ = list(set(globals().get("__all__", []) + ["cell_complex_from_component"]))
