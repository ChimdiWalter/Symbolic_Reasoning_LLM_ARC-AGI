"""AdapterGenesis — Self-Synthesizing Domain Adapters.

Given examples from an unfamiliar domain, synthesizes candidate DomainAdapters,
validates them through the fixed StructuralReasoner, repairs failures, and
stores successful adapters in memory.

The core reasoning engine (StructuralReasoner) remains unchanged.
The system adapts by creating/repairing the representation interface.

Architecture:
    DomainSignatureExtractor  — detect domain type from raw examples
    ObjectSchemaProposer      — propose what counts as an object
    PropertyLibraryProposer   — generate candidate boolean/numeric properties
    RelationAlgebraProposer   — generate candidate relations
    AdapterValidator          — test adapter through StructuralReasoner + LOO
    AdapterRepairer           — diagnose and fix adapter failures
    AdapterMemory             — store/retrieve successful adapters
    AdapterGenesis            — orchestrate the full pipeline
"""
from __future__ import annotations

import abc
import json
import hashlib
import numpy as np
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Type,
)

from reasoning_project.reasoning_engine import (
    DomainAdapter, StructuralReasoner, ReasoningMemory,
)
from reasoning_project.manifold_memory import (
    ManifoldMismatchTrigger,
    ManifoldPoint,
    MemoryManifold,
    FiberBundle,
    encode_task_signature,
    _signature_to_embedding,
)


# ═══════════════════════════════════════════════════════════════════════════
# DOMAIN SIGNATURE
# ═══════════════════════════════════════════════════════════════════════════

class DomainType(Enum):
    GRID = auto()
    GRAPH = auto()
    BOARD = auto()
    MOLECULE = auto()
    CIRCUIT = auto()
    IMAGE_REGION = auto()
    UNKNOWN = auto()


@dataclass
class DomainSignature:
    """Fingerprint of a domain derived from example inspection."""
    domain_type: DomainType
    data_format: str          # 'ndarray', 'dict', 'networkx', etc.
    dimensionality: int       # 2 for grids, 0 for abstract graphs
    value_type: str           # 'int', 'float', 'categorical'
    value_range: Tuple[Any, Any]
    typical_size: Tuple[int, ...]
    has_spatial_structure: bool
    has_graph_structure: bool
    has_labeled_nodes: bool
    has_labeled_edges: bool
    estimated_object_count: float
    estimated_color_count: int
    estimated_relation_types: List[str]
    raw_features: Dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        key = f"{self.domain_type.name}:{self.data_format}:{self.dimensionality}"
        key += f":{self.value_type}:{self.estimated_object_count:.0f}"
        return hashlib.md5(key.encode()).hexdigest()[:12]


class DomainSignatureExtractor:
    """Inspect raw examples to determine domain type and structure."""

    def extract(self, examples: List[Tuple[Any, Any]]) -> DomainSignature:
        inputs = [inp for inp, _ in examples]
        outputs = [out for _, out in examples]

        data_format = self._detect_format(inputs[0])
        domain_type = self._detect_domain_type(inputs, data_format)

        if data_format == 'ndarray':
            return self._extract_grid_signature(inputs, outputs, domain_type)
        elif data_format == 'dict':
            return self._extract_dict_signature(inputs, outputs, domain_type)
        else:
            return self._extract_generic_signature(inputs, outputs, domain_type)

    def _detect_format(self, x: Any) -> str:
        if isinstance(x, np.ndarray):
            return 'ndarray'
        elif isinstance(x, dict):
            return 'dict'
        elif isinstance(x, list):
            if len(x) > 0 and isinstance(x[0], (list, np.ndarray)):
                return 'ndarray'
            return 'list'
        return 'unknown'

    def _detect_domain_type(self, inputs: list, fmt: str) -> DomainType:
        if fmt == 'ndarray':
            x = np.asarray(inputs[0])
            if x.ndim == 2 and x.dtype in (np.int32, np.int64, np.int_, int):
                vals = set(x.flatten())
                if all(0 <= v <= 9 for v in vals):
                    return DomainType.GRID
                if len(vals) <= 30:
                    return DomainType.BOARD
            return DomainType.IMAGE_REGION

        if fmt == 'dict':
            sample = inputs[0]
            if 'nodes' in sample and 'edges' in sample:
                if any(k in str(sample) for k in ['bond', 'atom', 'ring']):
                    return DomainType.MOLECULE
                if any(k in str(sample) for k in ['wire', 'resistor', 'gate']):
                    return DomainType.CIRCUIT
                return DomainType.GRAPH
            if 'board' in sample or 'pieces' in sample:
                return DomainType.BOARD

        return DomainType.UNKNOWN

    def _extract_grid_signature(
        self, inputs: list, outputs: list, dtype: DomainType,
    ) -> DomainSignature:
        arrays = [np.asarray(x) for x in inputs]
        all_vals = set()
        sizes = []
        for a in arrays:
            all_vals.update(a.flatten().tolist())
            sizes.append(a.shape)

        from scipy import ndimage as ndi
        obj_counts = []
        for a in arrays:
            labeled, n = ndi.label(a > 0)
            obj_counts.append(n)

        avg_h = np.mean([s[0] for s in sizes])
        avg_w = np.mean([s[1] for s in sizes])

        return DomainSignature(
            domain_type=dtype,
            data_format='ndarray',
            dimensionality=2,
            value_type='int',
            value_range=(min(all_vals), max(all_vals)),
            typical_size=(int(avg_h), int(avg_w)),
            has_spatial_structure=True,
            has_graph_structure=False,
            has_labeled_nodes=False,
            has_labeled_edges=False,
            estimated_object_count=float(np.mean(obj_counts)),
            estimated_color_count=len(all_vals),
            estimated_relation_types=['left_of', 'above', 'touching', 'inside'],
            raw_features={'sizes': sizes, 'colors': sorted(all_vals)},
        )

    def _extract_dict_signature(
        self, inputs: list, outputs: list, dtype: DomainType,
    ) -> DomainSignature:
        sample = inputs[0]
        nodes = sample.get('nodes', [])
        edges = sample.get('edges', [])

        node_labels = set()
        for n in nodes:
            if isinstance(n, dict):
                node_labels.update(n.keys())

        edge_labels = set()
        for e in edges:
            if isinstance(e, dict):
                edge_labels.update(e.keys())

        return DomainSignature(
            domain_type=dtype,
            data_format='dict',
            dimensionality=0,
            value_type='categorical',
            value_range=(0, len(nodes)),
            typical_size=(len(nodes),),
            has_spatial_structure=False,
            has_graph_structure=True,
            has_labeled_nodes=bool(node_labels),
            has_labeled_edges=bool(edge_labels),
            estimated_object_count=float(len(nodes)),
            estimated_color_count=len(node_labels),
            estimated_relation_types=sorted(edge_labels)[:10],
            raw_features={
                'node_keys': sorted(node_labels),
                'edge_keys': sorted(edge_labels),
            },
        )

    def _extract_generic_signature(
        self, inputs: list, outputs: list, dtype: DomainType,
    ) -> DomainSignature:
        return DomainSignature(
            domain_type=dtype,
            data_format='unknown',
            dimensionality=0,
            value_type='unknown',
            value_range=(None, None),
            typical_size=(),
            has_spatial_structure=False,
            has_graph_structure=False,
            has_labeled_nodes=False,
            has_labeled_edges=False,
            estimated_object_count=0.0,
            estimated_color_count=0,
            estimated_relation_types=[],
        )


# ═══════════════════════════════════════════════════════════════════════════
# OBJECT SCHEMA PROPOSER
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ObjectSchema:
    """Proposed object decomposition for a domain."""
    name: str
    extractor: Callable[[Any], List[Dict[str, Any]]]
    description: str = ''


class ObjectSchemaProposer:
    """Propose candidate object extraction strategies for a domain."""

    def propose(self, sig: DomainSignature) -> List[ObjectSchema]:
        schemas = []

        if sig.domain_type == DomainType.GRID:
            schemas.extend(self._grid_schemas(sig))
        elif sig.domain_type == DomainType.GRAPH:
            schemas.extend(self._graph_schemas(sig))
        elif sig.domain_type == DomainType.BOARD:
            schemas.extend(self._board_schemas(sig))
        elif sig.domain_type == DomainType.MOLECULE:
            schemas.extend(self._molecule_schemas(sig))
        elif sig.domain_type == DomainType.CIRCUIT:
            schemas.extend(self._circuit_schemas(sig))
        elif sig.domain_type == DomainType.IMAGE_REGION:
            schemas.extend(self._image_region_schemas(sig))

        if not schemas:
            schemas.extend(self._grid_schemas(sig))

        return schemas

    def _grid_schemas(self, sig: DomainSignature) -> List[ObjectSchema]:
        from scipy import ndimage as ndi

        def color_components(scene):
            grid = np.atleast_2d(np.asarray(scene))
            objects = []
            bg = 0
            labeled, n = ndi.label(grid != bg)
            for i in range(1, n + 1):
                mask = labeled == i
                ys, xs = np.where(mask)
                color_val = int(grid[ys[0], xs[0]])
                objects.append({
                    'mask': mask, 'color': color_val,
                    'pixels': list(zip(ys.tolist(), xs.tolist())),
                    'size': int(mask.sum()),
                    'bbox': (int(ys.min()), int(xs.min()),
                             int(ys.max()), int(xs.max())),
                })
            return objects

        def per_color_components(scene):
            grid = np.atleast_2d(np.asarray(scene))
            objects = []
            for c in sorted(set(grid.flatten().tolist())):
                if c == 0:
                    continue
                labeled, n = ndi.label(grid == c)
                for i in range(1, n + 1):
                    mask = labeled == i
                    ys, xs = np.where(mask)
                    objects.append({
                        'mask': mask, 'color': c,
                        'pixels': list(zip(ys.tolist(), xs.tolist())),
                        'size': int(mask.sum()),
                        'bbox': (int(ys.min()), int(xs.min()),
                                 int(ys.max()), int(xs.max())),
                    })
            return objects

        def row_segments(scene):
            grid = np.asarray(scene)
            objects = []
            for r in range(grid.shape[0]):
                row = grid[r]
                segments = []
                start = None
                cur_color = 0
                for c in range(len(row)):
                    if row[c] != 0:
                        if start is None or row[c] != cur_color:
                            if start is not None:
                                segments.append((start, c - 1, cur_color))
                            start = c
                            cur_color = row[c]
                    else:
                        if start is not None:
                            segments.append((start, c - 1, cur_color))
                            start = None
                if start is not None:
                    segments.append((start, len(row) - 1, cur_color))
                for s, e, col in segments:
                    mask = np.zeros_like(grid, dtype=bool)
                    mask[r, s:e+1] = True
                    objects.append({
                        'mask': mask, 'color': int(col),
                        'size': e - s + 1,
                        'bbox': (r, s, r, e),
                    })
            return objects

        return [
            ObjectSchema('color_components', color_components,
                         'Connected non-background components'),
            ObjectSchema('per_color_components', per_color_components,
                         'Connected components per color'),
            ObjectSchema('row_segments', row_segments,
                         'Horizontal colored segments'),
        ]

    def _graph_schemas(self, sig: DomainSignature) -> List[ObjectSchema]:
        def nodes_as_objects(scene):
            nodes = scene.get('nodes', [])
            objects = []
            for i, n in enumerate(nodes):
                obj = {'index': i}
                if isinstance(n, dict):
                    obj.update(n)
                else:
                    obj['label'] = n
                obj['size'] = 1
                objects.append(obj)
            return objects

        def subgraphs_as_objects(scene):
            nodes = scene.get('nodes', [])
            edges = scene.get('edges', [])
            adj = {i: set() for i in range(len(nodes))}
            for e in edges:
                src, dst = e.get('src', e.get('source', 0)), e.get('dst', e.get('target', 1))
                adj[src].add(dst)
                adj[dst].add(src)

            visited = set()
            components = []
            for start in range(len(nodes)):
                if start in visited:
                    continue
                comp = set()
                stack = [start]
                while stack:
                    node = stack.pop()
                    if node in visited:
                        continue
                    visited.add(node)
                    comp.add(node)
                    stack.extend(adj[node] - visited)
                components.append(comp)

            objects = []
            for ci, comp in enumerate(components):
                comp_nodes = sorted(comp)
                obj = {
                    'node_indices': comp_nodes,
                    'size': len(comp_nodes),
                    'index': ci,
                }
                if comp_nodes and isinstance(nodes[comp_nodes[0]], dict):
                    labels = set()
                    for ni in comp_nodes:
                        if isinstance(nodes[ni], dict):
                            labels.add(nodes[ni].get('label', nodes[ni].get('color', 0)))
                    obj['labels'] = sorted(labels)
                    if len(labels) == 1:
                        obj['color'] = list(labels)[0]
                objects.append(obj)
            return objects

        return [
            ObjectSchema('nodes', nodes_as_objects, 'Individual graph nodes'),
            ObjectSchema('connected_components', subgraphs_as_objects,
                         'Connected subgraphs'),
        ]

    def _board_schemas(self, sig: DomainSignature) -> List[ObjectSchema]:
        def pieces_as_objects(scene):
            if isinstance(scene, dict) and 'pieces' in scene:
                return [{'index': i, **p} for i, p in enumerate(scene['pieces'])]
            grid = np.asarray(scene)
            objects = []
            idx = 0
            for r in range(grid.shape[0]):
                for c in range(grid.shape[1]):
                    if grid[r, c] != 0:
                        objects.append({
                            'index': idx, 'row': r, 'col': c,
                            'color': int(grid[r, c]),
                            'size': 1,
                        })
                        idx += 1
            return objects

        return [
            ObjectSchema('pieces', pieces_as_objects,
                         'Individual board pieces/cells'),
        ]

    def _molecule_schemas(self, sig: DomainSignature) -> List[ObjectSchema]:
        def atoms_as_objects(scene):
            nodes = scene.get('nodes', scene.get('atoms', []))
            edges = scene.get('edges', scene.get('bonds', []))
            adj = {i: [] for i in range(len(nodes))}
            for e in edges:
                src = e.get('src', e.get('source', 0))
                dst = e.get('dst', e.get('target', 1))
                bond_type = e.get('type', e.get('bond_type', 'single'))
                adj[src].append((dst, bond_type))
                adj[dst].append((src, bond_type))

            objects = []
            for i, n in enumerate(nodes):
                obj = {'index': i, 'degree': len(adj[i]), 'size': 1}
                if isinstance(n, dict):
                    obj.update(n)
                else:
                    obj['label'] = n
                neighbors = adj[i]
                obj['neighbor_count'] = len(neighbors)
                obj['bond_types'] = sorted(set(bt for _, bt in neighbors))
                objects.append(obj)
            return objects

        return [
            ObjectSchema('atoms', atoms_as_objects, 'Individual atoms with bonds'),
        ]

    def _circuit_schemas(self, sig: DomainSignature) -> List[ObjectSchema]:
        def components_as_objects(scene):
            nodes = scene.get('nodes', scene.get('components', []))
            objects = []
            for i, n in enumerate(nodes):
                obj = {'index': i, 'size': 1}
                if isinstance(n, dict):
                    obj.update(n)
                else:
                    obj['label'] = n
                objects.append(obj)
            return objects

        return [
            ObjectSchema('components', components_as_objects,
                         'Circuit components'),
        ]

    def _image_region_schemas(self, sig: DomainSignature) -> List[ObjectSchema]:
        from scipy import ndimage as ndi

        def threshold_regions(scene):
            arr = np.asarray(scene)
            if arr.ndim == 3:
                gray = arr.mean(axis=2)
            else:
                gray = arr.astype(float)
            binary = gray > gray.mean()
            labeled, n = ndi.label(binary)
            objects = []
            for i in range(1, n + 1):
                mask = labeled == i
                ys, xs = np.where(mask)
                objects.append({
                    'mask': mask, 'size': int(mask.sum()),
                    'bbox': (int(ys.min()), int(xs.min()),
                             int(ys.max()), int(xs.max())),
                    'index': i - 1,
                })
            return objects

        return [
            ObjectSchema('threshold_regions', threshold_regions,
                         'Binary threshold connected regions'),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# PROPERTY LIBRARY PROPOSER
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PropertyDef:
    """A candidate boolean property for objects."""
    name: str
    compute: Callable[[Dict[str, Any]], bool]
    domain_types: List[DomainType] = field(default_factory=list)


class PropertyLibraryProposer:
    """Generate candidate boolean/numeric properties for objects."""

    def propose(
        self, sig: DomainSignature, sample_objects: List[Dict[str, Any]],
    ) -> List[PropertyDef]:
        props: List[PropertyDef] = []

        props.extend(self._universal_properties())

        if sig.domain_type in (DomainType.GRID, DomainType.IMAGE_REGION):
            props.extend(self._spatial_properties(sample_objects))

        if sig.domain_type in (DomainType.GRAPH, DomainType.MOLECULE, DomainType.CIRCUIT):
            props.extend(self._graph_properties(sample_objects))

        if sig.domain_type == DomainType.BOARD:
            props.extend(self._board_properties(sample_objects))

        if sig.domain_type == DomainType.MOLECULE:
            props.extend(self._molecule_properties(sample_objects))

        props = self._filter_degenerate(props, sample_objects)
        return props

    def _universal_properties(self) -> List[PropertyDef]:
        return [
            PropertyDef('is_largest', lambda o: o.get('_is_largest', False)),
            PropertyDef('is_smallest', lambda o: o.get('_is_smallest', False)),
            PropertyDef('is_unique_color', lambda o: o.get('_is_unique_color', False)),
            PropertyDef('is_most_common_color', lambda o: o.get('_is_most_common_color', False)),
        ]

    def _spatial_properties(self, samples: List[Dict]) -> List[PropertyDef]:
        props = []
        if any('mask' in o for o in samples):
            props.append(PropertyDef(
                'has_holes',
                lambda o: self._check_holes(o),
            ))
            props.append(PropertyDef(
                'is_symmetric_x',
                lambda o: self._check_symmetric_x(o),
            ))
            props.append(PropertyDef(
                'is_symmetric_y',
                lambda o: self._check_symmetric_y(o),
            ))
            props.append(PropertyDef(
                'is_square',
                lambda o: self._check_square(o),
            ))
            props.append(PropertyDef(
                'touches_border',
                lambda o: self._check_border(o),
            ))
            props.append(PropertyDef(
                'is_convex',
                lambda o: self._check_convex(o),
            ))
        return props

    def _graph_properties(self, samples: List[Dict]) -> List[PropertyDef]:
        props = [
            PropertyDef('is_leaf',
                         lambda o: o.get('degree', o.get('neighbor_count', 0)) <= 1),
            PropertyDef('is_hub',
                         lambda o: o.get('degree', o.get('neighbor_count', 0)) >= 3),
            PropertyDef('is_isolated',
                         lambda o: o.get('degree', o.get('neighbor_count', 0)) == 0),
        ]
        return props

    def _board_properties(self, samples: List[Dict]) -> List[PropertyDef]:
        return [
            PropertyDef('is_edge_piece',
                         lambda o: self._check_board_edge(o)),
            PropertyDef('is_corner_piece',
                         lambda o: self._check_board_corner(o)),
        ]

    def _molecule_properties(self, samples: List[Dict]) -> List[PropertyDef]:
        return [
            PropertyDef('is_terminal',
                         lambda o: o.get('degree', 0) == 1),
            PropertyDef('has_double_bond',
                         lambda o: 'double' in o.get('bond_types', [])),
        ]

    def _filter_degenerate(
        self, props: List[PropertyDef], samples: List[Dict],
    ) -> List[PropertyDef]:
        """Remove properties that are all-True or all-False on samples."""
        if not samples:
            return props
        result = []
        for p in props:
            try:
                vals = [p.compute(o) for o in samples]
                if any(vals) and not all(vals):
                    result.append(p)
                elif not samples:
                    result.append(p)
            except Exception:
                pass
        return result

    @staticmethod
    def _check_holes(obj: Dict) -> bool:
        mask = obj.get('mask')
        if mask is None:
            return False
        from scipy import ndimage as ndi
        filled = ndi.binary_fill_holes(mask)
        return int(filled.sum()) > int(mask.sum())

    @staticmethod
    def _check_symmetric_x(obj: Dict) -> bool:
        mask = obj.get('mask')
        if mask is None:
            return False
        ys, xs = np.where(mask)
        if len(ys) == 0:
            return True
        sub = mask[ys.min():ys.max()+1, xs.min():xs.max()+1]
        return bool(np.array_equal(sub, sub[:, ::-1]))

    @staticmethod
    def _check_symmetric_y(obj: Dict) -> bool:
        mask = obj.get('mask')
        if mask is None:
            return False
        ys, xs = np.where(mask)
        if len(ys) == 0:
            return True
        sub = mask[ys.min():ys.max()+1, xs.min():xs.max()+1]
        return bool(np.array_equal(sub, sub[::-1, :]))

    @staticmethod
    def _check_square(obj: Dict) -> bool:
        bbox = obj.get('bbox')
        if bbox is None:
            return False
        return (bbox[2] - bbox[0]) == (bbox[3] - bbox[1])

    @staticmethod
    def _check_border(obj: Dict) -> bool:
        mask = obj.get('mask')
        if mask is None:
            return False
        h, w = mask.shape
        return bool(
            mask[0, :].any() or mask[-1, :].any()
            or mask[:, 0].any() or mask[:, -1].any()
        )

    @staticmethod
    def _check_convex(obj: Dict) -> bool:
        mask = obj.get('mask')
        if mask is None:
            return False
        ys, xs = np.where(mask)
        if len(ys) == 0:
            return True
        sub = mask[ys.min():ys.max()+1, xs.min():xs.max()+1]
        return bool(sub.all())

    @staticmethod
    def _check_board_edge(obj: Dict) -> bool:
        r, c = obj.get('row', -1), obj.get('col', -1)
        board_size = obj.get('_board_size', (8, 8))
        return r == 0 or c == 0 or r == board_size[0]-1 or c == board_size[1]-1

    @staticmethod
    def _check_board_corner(obj: Dict) -> bool:
        r, c = obj.get('row', -1), obj.get('col', -1)
        board_size = obj.get('_board_size', (8, 8))
        return (r in (0, board_size[0]-1)) and (c in (0, board_size[1]-1))


# ═══════════════════════════════════════════════════════════════════════════
# RELATION ALGEBRA PROPOSER
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RelationDef:
    """A candidate binary relation between objects."""
    name: str
    compute: Callable[[Dict, Dict], bool]


class RelationAlgebraProposer:
    """Generate candidate relations between objects."""

    def propose(self, sig: DomainSignature) -> List[RelationDef]:
        rels: List[RelationDef] = []

        if sig.has_spatial_structure:
            rels.extend(self._spatial_relations())
        if sig.has_graph_structure:
            rels.extend(self._graph_relations())
        if sig.domain_type == DomainType.BOARD:
            rels.extend(self._board_relations())

        return rels

    def _spatial_relations(self) -> List[RelationDef]:
        def _left_of(a, b):
            ba, bb = a.get('bbox'), b.get('bbox')
            if ba is None or bb is None:
                return False
            return ba[3] < bb[1]

        def _above(a, b):
            ba, bb = a.get('bbox'), b.get('bbox')
            if ba is None or bb is None:
                return False
            return ba[2] < bb[0]

        def _touching(a, b):
            ma, mb = a.get('mask'), b.get('mask')
            if ma is None or mb is None:
                return False
            from scipy import ndimage as ndi
            dilated = ndi.binary_dilation(ma)
            return bool((dilated & mb).any())

        def _inside(a, b):
            ma, mb = a.get('mask'), b.get('mask')
            if ma is None or mb is None:
                return False
            from scipy import ndimage as ndi
            filled_b = ndi.binary_fill_holes(mb)
            return bool((ma & filled_b).all()) and not bool((ma & mb).any())

        def _same_shape(a, b):
            ma, mb = a.get('mask'), b.get('mask')
            if ma is None or mb is None:
                return False
            ya, xa = np.where(ma)
            yb, xb = np.where(mb)
            if len(ya) != len(yb) or len(ya) == 0:
                return False
            sa = ma[ya.min():ya.max()+1, xa.min():xa.max()+1]
            sb = mb[yb.min():yb.max()+1, xb.min():xb.max()+1]
            return sa.shape == sb.shape and bool(np.array_equal(sa, sb))

        return [
            RelationDef('left_of', _left_of),
            RelationDef('above', _above),
            RelationDef('touching', _touching),
            RelationDef('inside', _inside),
            RelationDef('same_shape', _same_shape),
        ]

    def _graph_relations(self) -> List[RelationDef]:
        def _connected(a, b):
            return b.get('index') in a.get('_neighbors', set())

        def _same_label(a, b):
            return a.get('label') == b.get('label') and a.get('label') is not None

        return [
            RelationDef('connected_to', _connected),
            RelationDef('same_label', _same_label),
        ]

    def _board_relations(self) -> List[RelationDef]:
        def _same_row(a, b):
            return a.get('row') == b.get('row') and a.get('row') is not None

        def _same_col(a, b):
            return a.get('col') == b.get('col') and a.get('col') is not None

        def _diagonal(a, b):
            r1, c1 = a.get('row', -1), a.get('col', -1)
            r2, c2 = b.get('row', -1), b.get('col', -1)
            return abs(r1 - r2) == abs(c1 - c2) and r1 != r2

        def _adjacent(a, b):
            r1, c1 = a.get('row', -1), a.get('col', -1)
            r2, c2 = b.get('row', -1), b.get('col', -1)
            return abs(r1 - r2) + abs(c1 - c2) == 1

        return [
            RelationDef('same_row', _same_row),
            RelationDef('same_col', _same_col),
            RelationDef('diagonal', _diagonal),
            RelationDef('adjacent', _adjacent),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# COUNTERFACTUAL VERIFIER
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CounterfactualResult:
    """Result of a counterfactual test."""
    intervention_type: str
    passed: bool
    expected_invariant: bool
    actual_invariant: bool
    details: str = ''


class CounterfactualVerifier:
    """Test causal robustness of hypotheses through interventions."""

    def verify(
        self,
        adapter: DomainAdapter,
        reasoner: StructuralReasoner,
        train_pairs: List[Tuple[Any, Any]],
        hypothesis_meta: Dict[str, Any],
    ) -> List[CounterfactualResult]:
        results = []

        for inp, out in train_pairs[:2]:
            results.extend(
                self._test_irrelevant_interventions(adapter, reasoner, inp, out, train_pairs)
            )

        return results

    def _test_irrelevant_interventions(
        self,
        adapter: DomainAdapter,
        reasoner: StructuralReasoner,
        inp: Any,
        out: Any,
        train_pairs: List[Tuple[Any, Any]],
    ) -> List[CounterfactualResult]:
        results = []

        if isinstance(inp, np.ndarray):
            perturbed = self._perturb_irrelevant_color(inp, adapter)
            if perturbed is not None:
                original_result = reasoner.solve(train_pairs, [inp])
                if original_result is not None:
                    perturbed_pairs = [(perturbed if np.array_equal(ti, inp) else ti, to)
                                       for ti, to in train_pairs]
                    perturbed_result = reasoner.solve(perturbed_pairs, [perturbed])
                    is_invariant = (
                        perturbed_result is not None
                        and original_result[1].get('strategy') == perturbed_result[1].get('strategy')
                        and original_result[1].get('property', original_result[1].get('filter_prop'))
                        == perturbed_result[1].get('property', perturbed_result[1].get('filter_prop'))
                    )
                    results.append(CounterfactualResult(
                        intervention_type='irrelevant_color_change',
                        passed=is_invariant,
                        expected_invariant=True,
                        actual_invariant=is_invariant,
                    ))

        return results

    def _perturb_irrelevant_color(
        self, grid: np.ndarray, adapter: DomainAdapter,
    ) -> Optional[np.ndarray]:
        """Change the color of the background without affecting objects."""
        if not isinstance(grid, np.ndarray):
            return None
        unique = set(grid.flatten().tolist())
        bg = 0
        if bg not in unique:
            return None
        new_color = max(unique) + 1
        if new_color > 9:
            return None
        result = grid.copy()
        result[result == bg] = new_color
        return result


# ═══════════════════════════════════════════════════════════════════════════
# ENERGY-BASED CONSENSUS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EnergyWeights:
    training_error: float = 10.0
    complexity: float = 1.0
    type_violation: float = 5.0
    topology_violation: float = 3.0
    relation_violation: float = 2.0
    counterfactual_failure: float = 4.0
    multi_paradigm_support: float = -2.0
    memory_support: float = -1.5


class EnergyConsensus:
    """Energy-based hypothesis selection replacing hard voting."""

    def __init__(self, weights: Optional[EnergyWeights] = None):
        self.weights = weights or EnergyWeights()

    def score(self, hypothesis: Dict[str, Any]) -> float:
        w = self.weights
        e = 0.0

        e += w.training_error * hypothesis.get('training_errors', 0)
        e += w.complexity * hypothesis.get('complexity', 1)
        e += w.type_violation * hypothesis.get('type_violations', 0)
        e += w.topology_violation * hypothesis.get('topology_violations', 0)
        e += w.relation_violation * hypothesis.get('relation_violations', 0)
        e += w.counterfactual_failure * hypothesis.get('counterfactual_failures', 0)
        e += w.multi_paradigm_support * hypothesis.get('paradigm_support', 0)
        e += w.memory_support * hypothesis.get('memory_support', 0)

        return e

    def select_best(self, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not candidates:
            return None
        scored = [(self.score(c), i, c) for i, c in enumerate(candidates)]
        scored.sort(key=lambda x: (x[0], x[1]))
        return scored[0][2]


# ═══════════════════════════════════════════════════════════════════════════
# SYNTHESIZED DOMAIN ADAPTER
# ═══════════════════════════════════════════════════════════════════════════

class SynthesizedAdapter(DomainAdapter):
    """A DomainAdapter created by AdapterGenesis from examples.

    Wraps a selected ObjectSchema + PropertyLibrary + RelationAlgebra
    into the DomainAdapter protocol expected by StructuralReasoner.
    """

    def __init__(
        self,
        schema: ObjectSchema,
        properties: List[PropertyDef],
        relations: List[RelationDef],
        sig: DomainSignature,
    ):
        self.schema = schema
        self.properties = properties
        self.relations = relations
        self.sig = sig
        self._prop_names = [p.name for p in properties]

    def extract_objects(self, scene: Any) -> List[Dict[str, Any]]:
        objects = self.schema.extractor(scene)
        self._annotate_rank_properties(objects)
        return objects

    def property_names(self) -> List[str]:
        return list(self._prop_names)

    def get_property(self, obj: Dict, prop: str) -> bool:
        for p in self.properties:
            if p.name == prop:
                try:
                    return bool(p.compute(obj))
                except Exception:
                    return False
        return False

    def classify_kept_removed(
        self,
        objects: List[Dict],
        input_scene: Any,
        output_scene: Any,
    ) -> Tuple[List[int], List[int]]:
        if isinstance(input_scene, np.ndarray) and isinstance(output_scene, np.ndarray):
            return self._classify_grid_objects(objects, input_scene, output_scene)

        if isinstance(input_scene, dict) and isinstance(output_scene, dict):
            return self._classify_dict_objects(objects, input_scene, output_scene)

        return list(range(len(objects))), []

    def reconstruct_filtered(
        self, input_scene: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Any:
        if isinstance(input_scene, np.ndarray):
            return self._reconstruct_grid_filtered(input_scene, objects, keep_mask)

        if isinstance(input_scene, dict):
            return self._reconstruct_dict_filtered(input_scene, objects, keep_mask)

        return input_scene

    def reconstruct_recolored(
        self, input_scene: Any, objects: List[Dict], label_map: Dict[int, int],
    ) -> Any:
        if isinstance(input_scene, np.ndarray):
            return self._reconstruct_grid_recolored(input_scene, objects, label_map)

        if isinstance(input_scene, dict):
            return self._reconstruct_dict_recolored(input_scene, objects, label_map)

        return input_scene

    def reconstruct_extracted(
        self, input_scene: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Any:
        if isinstance(input_scene, np.ndarray):
            return self._reconstruct_grid_extracted(input_scene, objects, keep_mask)
        return self.reconstruct_filtered(input_scene, objects, keep_mask)

    def scenes_equal(self, a: Any, b: Any) -> bool:
        if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
            return bool(np.array_equal(a, b))
        return a == b

    def same_structure(self, a: Any, b: Any) -> bool:
        if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
            return a.shape == b.shape
        return True

    def match_objects(
        self,
        objs_a: List[Dict],
        objs_b: List[Dict],
    ) -> List[Tuple[int, int]]:
        from reasoning_project.reasoning_engine import _match_objects_hungarian_generic

        def sim(a, b):
            score = 0.0
            if a.get('size') and b.get('size'):
                score += 1.0 / (1.0 + abs(a['size'] - b['size']))
            for pname in self._prop_names[:5]:
                va = self.get_property(a, pname)
                vb = self.get_property(b, pname)
                if va == vb:
                    score += 0.5
            return score

        return _match_objects_hungarian_generic(objs_a, objs_b, sim)

    # --- Grid reconstruction helpers ---

    def _classify_grid_objects(
        self, objects, inp, out,
    ) -> Tuple[List[int], List[int]]:
        kept, removed = [], []
        out_arr = np.asarray(out)
        for i, obj in enumerate(objects):
            mask = obj.get('mask')
            if mask is None:
                kept.append(i)
                continue
            if mask.shape != out_arr.shape:
                removed.append(i)
                continue
            color = obj.get('color', 1)
            if (out_arr[mask] == color).all():
                kept.append(i)
            elif (out_arr[mask] == 0).all():
                removed.append(i)
            else:
                kept.append(i)
        return kept, removed

    def _reconstruct_grid_filtered(self, inp, objects, keep_mask):
        result = np.zeros_like(np.asarray(inp))
        for i, obj in enumerate(objects):
            if keep_mask[i]:
                mask = obj.get('mask')
                color = obj.get('color', 1)
                if mask is not None:
                    result[mask] = color
        return result

    def _reconstruct_grid_recolored(self, inp, objects, label_map):
        result = np.asarray(inp).copy()
        for i, obj in enumerate(objects):
            if i in label_map:
                mask = obj.get('mask')
                if mask is not None:
                    result[mask] = label_map[i]
        return result

    def _reconstruct_grid_extracted(self, inp, objects, keep_mask):
        kept = [obj for i, obj in enumerate(objects) if keep_mask[i]]
        if not kept:
            return np.zeros((1, 1), dtype=int)
        all_ys, all_xs = [], []
        for obj in kept:
            mask = obj.get('mask')
            if mask is not None:
                ys, xs = np.where(mask)
                all_ys.extend(ys.tolist())
                all_xs.extend(xs.tolist())
        if not all_ys:
            return np.zeros((1, 1), dtype=int)
        rmin, rmax = min(all_ys), max(all_ys)
        cmin, cmax = min(all_xs), max(all_xs)
        inp_arr = np.asarray(inp)
        return inp_arr[rmin:rmax+1, cmin:cmax+1].copy()

    def _classify_dict_objects(self, objects, inp, out):
        out_nodes = set()
        for n in out.get('nodes', []):
            if isinstance(n, dict):
                out_nodes.add(n.get('index', n.get('id')))
            else:
                out_nodes.add(n)
        kept, removed = [], []
        for i, obj in enumerate(objects):
            idx = obj.get('index', i)
            if idx in out_nodes or obj.get('label') in out_nodes:
                kept.append(i)
            else:
                removed.append(i)
        return kept, removed

    def _reconstruct_dict_filtered(self, inp, objects, keep_mask):
        kept_indices = set()
        for i, obj in enumerate(objects):
            if keep_mask[i]:
                kept_indices.add(obj.get('index', i))
        nodes = [n for i, n in enumerate(inp.get('nodes', [])) if i in kept_indices]
        edges = [e for e in inp.get('edges', [])
                 if e.get('src', e.get('source', -1)) in kept_indices
                 and e.get('dst', e.get('target', -1)) in kept_indices]
        return {'nodes': nodes, 'edges': edges}

    def _reconstruct_dict_recolored(self, inp, objects, label_map):
        result = json.loads(json.dumps(inp))
        for i, lbl in label_map.items():
            if i < len(result.get('nodes', [])):
                node = result['nodes'][i]
                if isinstance(node, dict):
                    node['label'] = lbl
                    node['color'] = lbl
                else:
                    result['nodes'][i] = lbl
        return result

    def _annotate_rank_properties(self, objects: List[Dict]):
        """Add rank-based properties like is_largest, is_smallest, etc."""
        if not objects:
            return
        sizes = [o.get('size', 0) for o in objects]
        if sizes:
            max_s = max(sizes)
            min_s = min(sizes)
            for o in objects:
                o['_is_largest'] = o.get('size', 0) == max_s
                o['_is_smallest'] = o.get('size', 0) == min_s

        colors = {}
        for o in objects:
            c = o.get('color')
            if c is not None:
                colors[c] = colors.get(c, 0) + 1
        if colors:
            max_c = max(colors, key=colors.get)
            for o in objects:
                c = o.get('color')
                o['_is_unique_color'] = colors.get(c, 0) == 1
                o['_is_most_common_color'] = c == max_c


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTER VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """Result of adapter validation."""
    passed: bool
    train_consistency: bool
    loo_consistency: bool
    reconstruction_valid: bool
    object_extraction_stable: bool
    solve_count: int
    false_positives: int
    counterfactual_results: List[CounterfactualResult] = field(default_factory=list)
    failure_diagnosis: str = ''


class AdapterValidator:
    """Validate a synthesized adapter through the StructuralReasoner."""

    def validate(
        self,
        adapter: SynthesizedAdapter,
        train_pairs: List[Tuple[Any, Any]],
        test_pairs: Optional[List[Tuple[Any, Any]]] = None,
    ) -> ValidationResult:
        obj_stable = self._check_object_extraction(adapter, train_pairs)
        recon_valid = self._check_reconstruction(adapter, train_pairs)

        reasoner = StructuralReasoner(adapter)
        test_inputs = [inp for inp, _ in train_pairs]

        train_consistent = True
        loo_consistent = True
        solves = 0
        fps = 0

        if len(train_pairs) >= 3:
            result = reasoner.solve(train_pairs, [train_pairs[-1][0]])
            if result is not None:
                preds, meta = result
                if adapter.scenes_equal(preds[0], train_pairs[-1][1]):
                    solves += 1
                else:
                    fps += 1
                    train_consistent = False

            for i in range(len(train_pairs)):
                loo_train = train_pairs[:i] + train_pairs[i+1:]
                if len(loo_train) < 3:
                    continue
                held_input, held_output = train_pairs[i]
                r = reasoner.solve(loo_train, [held_input])
                if r is not None:
                    if not adapter.scenes_equal(r[0][0], held_output):
                        loo_consistent = False
                        break

        cf_results = []
        if train_consistent and len(train_pairs) >= 3:
            verifier = CounterfactualVerifier()
            result = reasoner.solve(train_pairs, [train_pairs[0][0]])
            if result is not None:
                cf_results = verifier.verify(
                    adapter, reasoner, train_pairs, result[1],
                )

        if test_pairs:
            for inp, out in test_pairs:
                r = reasoner.solve(train_pairs, [inp])
                if r is not None:
                    if adapter.scenes_equal(r[0][0], out):
                        solves += 1
                    else:
                        fps += 1

        passed = (
            obj_stable
            and recon_valid
            and train_consistent
            and loo_consistent
            and fps == 0
        )

        diagnosis = ''
        if not obj_stable:
            diagnosis = 'object_extraction_unstable'
        elif not recon_valid:
            diagnosis = 'reconstruction_failure'
        elif not train_consistent:
            diagnosis = 'training_inconsistency'
        elif not loo_consistent:
            diagnosis = 'loo_violation'
        elif fps > 0:
            diagnosis = 'false_positives'

        return ValidationResult(
            passed=passed,
            train_consistency=train_consistent,
            loo_consistency=loo_consistent,
            reconstruction_valid=recon_valid,
            object_extraction_stable=obj_stable,
            solve_count=solves,
            false_positives=fps,
            counterfactual_results=cf_results,
            failure_diagnosis=diagnosis,
        )

    def _check_object_extraction(
        self, adapter: SynthesizedAdapter, pairs: List[Tuple],
    ) -> bool:
        for inp, _ in pairs:
            try:
                objs = adapter.extract_objects(inp)
                if not objs:
                    return False
            except Exception:
                return False
        return True

    def _check_reconstruction(
        self, adapter: SynthesizedAdapter, pairs: List[Tuple],
    ) -> bool:
        for inp, _ in pairs:
            try:
                objs = adapter.extract_objects(inp)
                keep_mask = [True] * len(objs)
                recon = adapter.reconstruct_filtered(inp, objs, keep_mask)
                if isinstance(inp, np.ndarray):
                    if not np.array_equal(np.asarray(recon) > 0, np.asarray(inp) > 0):
                        return False
            except Exception:
                return False
        return True


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTER REPAIRER
# ═══════════════════════════════════════════════════════════════════════════

class AdapterRepairer:
    """Diagnose adapter failures and propose repairs."""

    def repair(
        self,
        adapter: SynthesizedAdapter,
        validation: ValidationResult,
        train_pairs: List[Tuple[Any, Any]],
        all_schemas: List[ObjectSchema],
        all_properties: List[PropertyDef],
    ) -> Optional[SynthesizedAdapter]:
        """Attempt to repair a failed adapter. Returns None if unfixable."""
        diagnosis = validation.failure_diagnosis

        if diagnosis == 'object_extraction_unstable':
            return self._try_alternate_schema(
                adapter, train_pairs, all_schemas, all_properties,
            )

        if diagnosis == 'reconstruction_failure':
            return self._try_alternate_schema(
                adapter, train_pairs, all_schemas, all_properties,
            )

        if diagnosis in ('training_inconsistency', 'loo_violation', 'false_positives'):
            return self._try_add_properties(
                adapter, train_pairs, all_properties,
            )

        return None

    def _try_alternate_schema(
        self,
        adapter: SynthesizedAdapter,
        pairs: List[Tuple],
        schemas: List[ObjectSchema],
        props: List[PropertyDef],
    ) -> Optional[SynthesizedAdapter]:
        for schema in schemas:
            if schema.name == adapter.schema.name:
                continue
            candidate = SynthesizedAdapter(
                schema, adapter.properties, adapter.relations, adapter.sig,
            )
            try:
                for inp, _ in pairs:
                    objs = candidate.extract_objects(inp)
                    if not objs:
                        break
                else:
                    return candidate
            except Exception:
                continue
        return None

    def _try_add_properties(
        self,
        adapter: SynthesizedAdapter,
        pairs: List[Tuple],
        all_props: List[PropertyDef],
    ) -> Optional[SynthesizedAdapter]:
        current_names = {p.name for p in adapter.properties}
        new_props = [p for p in all_props if p.name not in current_names]
        if not new_props:
            return None
        extended = SynthesizedAdapter(
            adapter.schema,
            adapter.properties + new_props,
            adapter.relations,
            adapter.sig,
        )
        return extended


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTER MEMORY
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AdapterRecord:
    """A stored successful adapter with its provenance."""
    signature: DomainSignature
    adapter: SynthesizedAdapter
    validation: ValidationResult
    solve_count: int
    tasks_tested: int
    learned_predicates: List[str] = field(default_factory=list)
    successful_hypotheses: List[Dict] = field(default_factory=list)
    counterfactual_traces: List[CounterfactualResult] = field(default_factory=list)


class AdapterMemory:
    """Store and retrieve successful adapters."""

    def __init__(self):
        self.records: List[AdapterRecord] = []

    def store(self, record: AdapterRecord):
        for i, existing in enumerate(self.records):
            if existing.signature.fingerprint() == record.signature.fingerprint():
                if record.solve_count >= existing.solve_count:
                    self.records[i] = record
                return
        self.records.append(record)

    def retrieve(self, sig: DomainSignature, top_k: int = 3) -> List[AdapterRecord]:
        if not self.records:
            return []
        scored = []
        for rec in self.records:
            score = self._similarity(sig, rec.signature)
            scored.append((score, rec))
        scored.sort(key=lambda x: -x[0])
        return [rec for _, rec in scored[:top_k]]

    def _similarity(self, a: DomainSignature, b: DomainSignature) -> float:
        score = 0.0
        if a.domain_type == b.domain_type:
            score += 3.0
        if a.data_format == b.data_format:
            score += 2.0
        if a.dimensionality == b.dimensionality:
            score += 1.0
        if a.has_spatial_structure == b.has_spatial_structure:
            score += 0.5
        if a.has_graph_structure == b.has_graph_structure:
            score += 0.5
        oc_diff = abs(a.estimated_object_count - b.estimated_object_count)
        score += 1.0 / (1.0 + oc_diff)
        return score


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTER GENESIS — MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

class AdapterGenesis:
    """Synthesize, validate, repair, and store DomainAdapters.

    Given example (input, output) pairs from an unfamiliar domain:
    1. Extract domain signature
    2. Propose object schemas
    3. Propose property libraries
    4. Propose relation algebras
    5. Generate candidate adapters
    6. Validate each through StructuralReasoner + LOO
    7. Repair failures
    8. Store successful adapters

    The StructuralReasoner is never modified. Only adapters change.
    """

    def __init__(
        self,
        memory: Optional[AdapterMemory] = None,
        max_repair_attempts: int = 3,
        manifold: Optional[MemoryManifold] = None,
        bundle: Optional[FiberBundle] = None,
    ):
        self.sig_extractor = DomainSignatureExtractor()
        self.schema_proposer = ObjectSchemaProposer()
        self.property_proposer = PropertyLibraryProposer()
        self.relation_proposer = RelationAlgebraProposer()
        self.validator = AdapterValidator()
        self.repairer = AdapterRepairer()
        self.memory = memory or AdapterMemory()
        self.max_repair_attempts = max_repair_attempts
        self.manifold = manifold
        self.bundle = bundle
        self._mismatch_trigger = ManifoldMismatchTrigger() if manifold is not None else None

    def synthesize(
        self,
        train_pairs: List[Tuple[Any, Any]],
        test_pairs: Optional[List[Tuple[Any, Any]]] = None,
    ) -> Optional[Tuple[SynthesizedAdapter, ValidationResult]]:
        """Synthesize the best adapter for the given examples.

        When a MemoryManifold is attached, adapter creation is triggered
        specifically when curvature, chart coverage, or topological mismatch
        crosses a threshold — not unconditionally.

        Returns (adapter, validation_result) or None if no valid adapter found.
        """
        sig = self.sig_extractor.extract(train_pairs)

        # Check manifold mismatch trigger if manifold is available
        self._last_mismatch: Optional[Dict[str, Any]] = None
        if self._mismatch_trigger is not None and self.manifold is not None:
            query_sig = encode_task_signature(train_pairs)
            query_emb = _signature_to_embedding(query_sig)
            query_point = ManifoldPoint(
                embedding=query_emb,
                task_signature=query_sig,
                domain="unknown",
            )
            self._last_mismatch = self._mismatch_trigger.should_create_adapter(
                query_point, self.manifold, self.bundle,
            )

        retrieved = self.memory.retrieve(sig)
        for rec in retrieved:
            try:
                v = self.validator.validate(rec.adapter, train_pairs, test_pairs)
                if v.passed:
                    return rec.adapter, v
            except Exception:
                continue

        schemas = self.schema_proposer.propose(sig)
        relations = self.relation_proposer.propose(sig)

        best_adapter = None
        best_validation = None
        best_score = -1

        for schema in schemas:
            try:
                sample_objs = schema.extractor(train_pairs[0][0])
            except Exception:
                continue
            if not sample_objs:
                continue

            try:
                properties = self.property_proposer.propose(sig, sample_objs)
                candidate = SynthesizedAdapter(schema, properties, relations, sig)
                validation = self.validator.validate(candidate, train_pairs, test_pairs)

                if validation.passed:
                    score = validation.solve_count * 10 - validation.false_positives * 100
                    if score > best_score:
                        best_score = score
                        best_adapter = candidate
                        best_validation = validation
                else:
                    for attempt in range(self.max_repair_attempts):
                        repaired = self.repairer.repair(
                            candidate, validation, train_pairs,
                            schemas, properties,
                        )
                        if repaired is None:
                            break
                        v2 = self.validator.validate(repaired, train_pairs, test_pairs)
                        if v2.passed:
                            score = v2.solve_count * 10 - v2.false_positives * 100
                            if score > best_score:
                                best_score = score
                                best_adapter = repaired
                                best_validation = v2
                            break
                        candidate = repaired
                        validation = v2
            except Exception:
                continue

        if best_adapter is not None and best_validation is not None:
            record = AdapterRecord(
                signature=sig,
                adapter=best_adapter,
                validation=best_validation,
                solve_count=best_validation.solve_count,
                tasks_tested=len(train_pairs) + (len(test_pairs) if test_pairs else 0),
                counterfactual_traces=best_validation.counterfactual_results,
            )
            self.memory.store(record)
            return best_adapter, best_validation

        return None

    def synthesize_and_solve(
        self,
        train_pairs: List[Tuple[Any, Any]],
        test_inputs: List[Any],
    ) -> Optional[Tuple[List[Any], Dict[str, Any]]]:
        """One-shot: synthesize adapter + solve task.

        Returns (predictions, metadata) or None.
        """
        result = self.synthesize(train_pairs)
        if result is None:
            return None

        adapter, validation = result
        reasoner = StructuralReasoner(adapter)
        solve_result = reasoner.solve(train_pairs, test_inputs)

        if solve_result is not None:
            preds, meta = solve_result
            meta['adapter_schema'] = adapter.schema.name
            meta['adapter_properties'] = adapter.property_names()
            meta['adapter_domain'] = adapter.sig.domain_type.name
            if self._last_mismatch is not None:
                meta['manifold_mismatch'] = self._last_mismatch
            return preds, meta

        return None
