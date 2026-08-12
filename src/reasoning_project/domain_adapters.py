"""Cross-Domain Adapters for StructuralReasoner.

Each adapter implements the DomainAdapter protocol, allowing the fixed
StructuralReasoner to reason over a new domain by changing only perception.

Adapters:
    GraphDomainAdapter         — abstract graph transformations (node/edge)
    ChessBoardDomainAdapter    — board puzzles with piece-based rules
    MoleculeGraphDomainAdapter — molecular graph reasoning (atoms/bonds/rings)
"""
from __future__ import annotations

import json
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from reasoning_project.reasoning_engine import (
    DomainAdapter, _match_objects_hungarian_generic,
)


# ═══════════════════════════════════════════════════════════════════════════
# GRAPH DOMAIN ADAPTER
# ═══════════════════════════════════════════════════════════════════════════

class GraphDomainAdapter(DomainAdapter):
    """Adapter for abstract graph transformation tasks.

    Scenes are dicts with 'nodes' and 'edges'.
    Objects are individual nodes with computed structural properties.
    """

    def extract_objects(self, scene: Any) -> List[Dict[str, Any]]:
        if not isinstance(scene, dict):
            return []
        nodes = scene.get('nodes', [])
        edges = scene.get('edges', [])

        adj: Dict[int, set] = {}
        for i in range(len(nodes)):
            adj[i] = set()
        for e in edges:
            src = e.get('source', e.get('src', 0))
            dst = e.get('target', e.get('dst', 1))
            if src < len(nodes) and dst < len(nodes):
                adj[src].add(dst)
                adj[dst].add(src)

        objects = []
        for i, n in enumerate(nodes):
            obj = {'index': i, 'size': 1}
            if isinstance(n, dict):
                obj.update(n)
            else:
                obj['label'] = n
            obj['degree'] = len(adj.get(i, set()))
            obj['color'] = obj.get('color', obj.get('label', i))
            obj['_neighbors'] = adj.get(i, set())
            objects.append(obj)

        self._annotate_rank_properties(objects)
        return objects

    def property_names(self) -> List[str]:
        return [
            'is_largest', 'is_smallest', 'is_unique_color', 'is_most_common_color',
            'is_leaf', 'is_hub', 'is_isolated', 'is_bridge',
        ]

    def get_property(self, obj: Dict, prop: str) -> bool:
        if prop == 'is_leaf':
            return obj.get('degree', 0) == 1
        if prop == 'is_hub':
            return obj.get('degree', 0) >= 3
        if prop == 'is_isolated':
            return obj.get('degree', 0) == 0
        if prop == 'is_bridge':
            return obj.get('degree', 0) == 2
        return obj.get(f'_{prop}', obj.get(prop, False))

    def classify_kept_removed(
        self, objects: List[Dict], input_scene: Any, output_scene: Any,
    ) -> Tuple[List[int], List[int]]:
        out_nodes = output_scene.get('nodes', [])
        out_indices = set()
        for n in out_nodes:
            if isinstance(n, dict):
                out_indices.add(n.get('index'))
            else:
                out_indices.add(n)

        kept, removed = [], []
        for i, obj in enumerate(objects):
            if obj.get('index') in out_indices:
                kept.append(i)
            else:
                removed.append(i)
        return kept, removed

    def reconstruct_filtered(
        self, input_scene: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Any:
        kept_indices = set()
        for i, obj in enumerate(objects):
            if keep_mask[i]:
                kept_indices.add(obj.get('index', i))

        in_nodes = input_scene.get('nodes', [])
        in_edges = input_scene.get('edges', [])

        out_nodes = [n for i, n in enumerate(in_nodes) if i in kept_indices]
        out_edges = [e for e in in_edges
                     if e.get('source', e.get('src', -1)) in kept_indices
                     and e.get('target', e.get('dst', -1)) in kept_indices]

        return {'nodes': out_nodes, 'edges': out_edges}

    def reconstruct_recolored(
        self, input_scene: Any, objects: List[Dict], label_map: Dict[int, int],
    ) -> Any:
        result = json.loads(json.dumps(input_scene))
        for obj_idx, new_label in label_map.items():
            if obj_idx < len(result.get('nodes', [])):
                node = result['nodes'][obj_idx]
                if isinstance(node, dict):
                    node['label'] = new_label
                    node['color'] = new_label
                else:
                    result['nodes'][obj_idx] = new_label
        return result

    def reconstruct_extracted(
        self, input_scene: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Any:
        return self.reconstruct_filtered(input_scene, objects, keep_mask)

    def scenes_equal(self, a: Any, b: Any) -> bool:
        if not isinstance(a, dict) or not isinstance(b, dict):
            return a == b
        a_nodes = a.get('nodes', [])
        b_nodes = b.get('nodes', [])
        if len(a_nodes) != len(b_nodes):
            return False

        a_indices = set()
        for n in a_nodes:
            if isinstance(n, dict):
                a_indices.add(n.get('index'))
            else:
                a_indices.add(n)
        b_indices = set()
        for n in b_nodes:
            if isinstance(n, dict):
                b_indices.add(n.get('index'))
            else:
                b_indices.add(n)

        if a_indices != b_indices:
            return False

        a_labels = {}
        for n in a_nodes:
            if isinstance(n, dict):
                a_labels[n.get('index')] = n.get('label', n.get('color'))
        b_labels = {}
        for n in b_nodes:
            if isinstance(n, dict):
                b_labels[n.get('index')] = n.get('label', n.get('color'))

        return a_labels == b_labels

    def same_structure(self, a: Any, b: Any) -> bool:
        if not isinstance(a, dict) or not isinstance(b, dict):
            return True
        return len(a.get('nodes', [])) == len(b.get('nodes', []))

    def match_objects(
        self, objs_a: List[Dict], objs_b: List[Dict],
    ) -> List[Tuple[int, int]]:
        def sim(a, b):
            score = 0.0
            if a.get('index') == b.get('index'):
                score += 5.0
            if a.get('degree') == b.get('degree'):
                score += 1.0
            return score
        return _match_objects_hungarian_generic(objs_a, objs_b, sim)

    def _annotate_rank_properties(self, objects: List[Dict]):
        if not objects:
            return
        degrees = [o.get('degree', 0) for o in objects]
        max_d = max(degrees) if degrees else 0
        min_d = min(degrees) if degrees else 0
        sizes = [o.get('size', 1) for o in objects]
        max_s = max(sizes) if sizes else 0
        min_s = min(sizes) if sizes else 0

        colors = {}
        for o in objects:
            c = o.get('color')
            if c is not None:
                colors[c] = colors.get(c, 0) + 1

        for o in objects:
            o['_is_largest'] = o.get('size', 1) == max_s and max_s > min_s
            o['_is_smallest'] = o.get('size', 1) == min_s and max_s > min_s
            c = o.get('color')
            o['_is_unique_color'] = colors.get(c, 0) == 1
            o['_is_most_common_color'] = (
                c is not None and colors.get(c, 0) == max(colors.values(), default=0)
            )


# ═══════════════════════════════════════════════════════════════════════════
# CHESS BOARD DOMAIN ADAPTER
# ═══════════════════════════════════════════════════════════════════════════

class ChessBoardDomainAdapter(DomainAdapter):
    """Adapter for chess-like board puzzle tasks.

    Scenes are 2D integer arrays where each nonzero cell is a piece.
    Objects are individual pieces with position-based properties.
    """

    def __init__(self, bg: int = 0):
        self.bg = bg

    def extract_objects(self, scene: Any) -> List[Dict[str, Any]]:
        grid = np.asarray(scene)
        objects = []
        h, w = grid.shape
        idx = 0
        for r in range(h):
            for c in range(w):
                if grid[r, c] != self.bg:
                    obj = {
                        'index': idx,
                        'row': r, 'col': c,
                        'color': int(grid[r, c]),
                        'size': 1,
                        '_board_h': h, '_board_w': w,
                    }
                    idx += 1
                    objects.append(obj)

        self._annotate_board_properties(objects, h, w)
        return objects

    def property_names(self) -> List[str]:
        return [
            'is_largest', 'is_smallest', 'is_unique_color', 'is_most_common_color',
            'is_edge', 'is_corner', 'is_center', 'is_top_row', 'is_bottom_row',
            'is_attacked', 'is_protected',
        ]

    def get_property(self, obj: Dict, prop: str) -> bool:
        return obj.get(f'_{prop}', obj.get(prop, False))

    def classify_kept_removed(
        self, objects: List[Dict], input_scene: Any, output_scene: Any,
    ) -> Tuple[List[int], List[int]]:
        out = np.asarray(output_scene)
        kept, removed = [], []
        for i, obj in enumerate(objects):
            r, c = obj['row'], obj['col']
            if r < out.shape[0] and c < out.shape[1] and out[r, c] != self.bg:
                kept.append(i)
            else:
                removed.append(i)
        return kept, removed

    def reconstruct_filtered(
        self, input_scene: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Any:
        grid = np.asarray(input_scene)
        result = np.full_like(grid, self.bg)
        for i, obj in enumerate(objects):
            if keep_mask[i]:
                result[obj['row'], obj['col']] = obj['color']
        return result

    def reconstruct_recolored(
        self, input_scene: Any, objects: List[Dict], label_map: Dict[int, int],
    ) -> Any:
        grid = np.asarray(input_scene).copy()
        for obj_idx, new_color in label_map.items():
            if obj_idx < len(objects):
                obj = objects[obj_idx]
                grid[obj['row'], obj['col']] = new_color
        return grid

    def reconstruct_extracted(
        self, input_scene: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Any:
        return self.reconstruct_filtered(input_scene, objects, keep_mask)

    def scenes_equal(self, a: Any, b: Any) -> bool:
        return bool(np.array_equal(np.asarray(a), np.asarray(b)))

    def same_structure(self, a: Any, b: Any) -> bool:
        return np.asarray(a).shape == np.asarray(b).shape

    def match_objects(
        self, objs_a: List[Dict], objs_b: List[Dict],
    ) -> List[Tuple[int, int]]:
        def sim(a, b):
            if a.get('row') == b.get('row') and a.get('col') == b.get('col'):
                return 10.0
            return 0.0
        return _match_objects_hungarian_generic(objs_a, objs_b, sim)

    def _annotate_board_properties(self, objects: List[Dict], h: int, w: int):
        if not objects:
            return

        positions = {(o['row'], o['col']) for o in objects}

        colors = {}
        for o in objects:
            c = o['color']
            colors[c] = colors.get(c, 0) + 1

        for o in objects:
            r, c = o['row'], o['col']
            o['_is_edge'] = (r == 0 or r == h - 1 or c == 0 or c == w - 1)
            o['_is_corner'] = (r in (0, h - 1)) and (c in (0, w - 1))
            o['_is_center'] = (h // 4 <= r <= 3 * h // 4) and (w // 4 <= c <= 3 * w // 4)
            o['_is_top_row'] = (r == 0)
            o['_is_bottom_row'] = (r == h - 1)

            attacked = False
            protected = False
            for r2, c2 in positions:
                if (r2, c2) == (r, c):
                    continue
                if r2 == r or c2 == c:
                    attacked = True
                    break
            for r2, c2 in positions:
                if (r2, c2) == (r, c):
                    continue
                if abs(r2 - r) <= 1 and abs(c2 - c) <= 1:
                    protected = True
                    break
            o['_is_attacked'] = attacked
            o['_is_protected'] = protected

            col = o['color']
            o['_is_unique_color'] = colors.get(col, 0) == 1
            o['_is_most_common_color'] = (
                colors.get(col, 0) == max(colors.values(), default=0)
            )
            o['_is_largest'] = False
            o['_is_smallest'] = False


# ═══════════════════════════════════════════════════════════════════════════
# MOLECULE GRAPH DOMAIN ADAPTER
# ═══════════════════════════════════════════════════════════════════════════

class MoleculeGraphDomainAdapter(DomainAdapter):
    """Adapter for molecule-like graph reasoning tasks.

    Scenes are dicts with 'nodes' (atoms) and 'edges' (bonds).
    Objects are individual atoms with chemical-like structural properties.
    """

    def extract_objects(self, scene: Any) -> List[Dict[str, Any]]:
        if not isinstance(scene, dict):
            return []
        nodes = scene.get('nodes', scene.get('atoms', []))
        edges = scene.get('edges', scene.get('bonds', []))

        adj: Dict[int, List[Tuple[int, str]]] = {}
        for i in range(len(nodes)):
            adj[i] = []
        for e in edges:
            src = e.get('source', e.get('src', 0))
            dst = e.get('target', e.get('dst', 1))
            btype = e.get('type', e.get('bond_type', 'single'))
            if src < len(nodes) and dst < len(nodes):
                adj[src].append((dst, btype))
                adj[dst].append((src, btype))

        objects = []
        for i, n in enumerate(nodes):
            obj = {'index': i, 'size': 1}
            if isinstance(n, dict):
                obj.update(n)
            else:
                obj['label'] = n
            obj['degree'] = len(adj.get(i, []))
            obj['color'] = obj.get('color', obj.get('label', i))
            obj['bond_types'] = sorted(set(bt for _, bt in adj.get(i, [])))
            obj['_neighbors'] = {nb for nb, _ in adj.get(i, [])}
            objects.append(obj)

        self._annotate_molecule_properties(objects, adj, edges)
        return objects

    def property_names(self) -> List[str]:
        return [
            'is_largest', 'is_smallest', 'is_unique_color', 'is_most_common_color',
            'is_terminal', 'is_branching', 'is_in_ring', 'has_double_bond',
            'is_isolated', 'is_heteroatom',
        ]

    def get_property(self, obj: Dict, prop: str) -> bool:
        return obj.get(f'_{prop}', obj.get(prop, False))

    def classify_kept_removed(
        self, objects: List[Dict], input_scene: Any, output_scene: Any,
    ) -> Tuple[List[int], List[int]]:
        out_nodes = output_scene.get('nodes', output_scene.get('atoms', []))
        out_indices = set()
        for n in out_nodes:
            if isinstance(n, dict):
                out_indices.add(n.get('index'))
            else:
                out_indices.add(n)

        kept, removed = [], []
        for i, obj in enumerate(objects):
            if obj.get('index') in out_indices:
                kept.append(i)
            else:
                removed.append(i)
        return kept, removed

    def reconstruct_filtered(
        self, input_scene: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Any:
        kept_indices = set()
        for i, obj in enumerate(objects):
            if keep_mask[i]:
                kept_indices.add(obj.get('index', i))

        in_nodes = input_scene.get('nodes', input_scene.get('atoms', []))
        in_edges = input_scene.get('edges', input_scene.get('bonds', []))

        out_nodes = [n for i, n in enumerate(in_nodes) if i in kept_indices]
        out_edges = [e for e in in_edges
                     if e.get('source', e.get('src', -1)) in kept_indices
                     and e.get('target', e.get('dst', -1)) in kept_indices]

        return {'nodes': out_nodes, 'edges': out_edges}

    def reconstruct_recolored(
        self, input_scene: Any, objects: List[Dict], label_map: Dict[int, int],
    ) -> Any:
        result = json.loads(json.dumps(input_scene))
        node_key = 'nodes' if 'nodes' in result else 'atoms'
        for obj_idx, new_label in label_map.items():
            if obj_idx < len(result.get(node_key, [])):
                node = result[node_key][obj_idx]
                if isinstance(node, dict):
                    node['label'] = new_label
                    node['color'] = new_label
                else:
                    result[node_key][obj_idx] = new_label
        return result

    def reconstruct_extracted(
        self, input_scene: Any, objects: List[Dict], keep_mask: List[bool],
    ) -> Any:
        return self.reconstruct_filtered(input_scene, objects, keep_mask)

    def scenes_equal(self, a: Any, b: Any) -> bool:
        if not isinstance(a, dict) or not isinstance(b, dict):
            return a == b
        a_nodes = a.get('nodes', a.get('atoms', []))
        b_nodes = b.get('nodes', b.get('atoms', []))
        if len(a_nodes) != len(b_nodes):
            return False

        a_data = {}
        for n in a_nodes:
            if isinstance(n, dict):
                a_data[n.get('index')] = (n.get('label'), n.get('color'))
        b_data = {}
        for n in b_nodes:
            if isinstance(n, dict):
                b_data[n.get('index')] = (n.get('label'), n.get('color'))

        return a_data == b_data

    def same_structure(self, a: Any, b: Any) -> bool:
        if not isinstance(a, dict) or not isinstance(b, dict):
            return True
        return len(a.get('nodes', [])) == len(b.get('nodes', []))

    def match_objects(
        self, objs_a: List[Dict], objs_b: List[Dict],
    ) -> List[Tuple[int, int]]:
        def sim(a, b):
            score = 0.0
            if a.get('index') == b.get('index'):
                score += 5.0
            if a.get('degree') == b.get('degree'):
                score += 1.0
            if a.get('label') == b.get('label'):
                score += 2.0
            return score
        return _match_objects_hungarian_generic(objs_a, objs_b, sim)

    def _annotate_molecule_properties(
        self, objects: List[Dict], adj: Dict, edges: list,
    ):
        if not objects:
            return

        colors = {}
        for o in objects:
            c = o.get('color')
            if c is not None:
                colors[c] = colors.get(c, 0) + 1

        ring_members = self._find_ring_members(objects, adj)

        for o in objects:
            idx = o['index']
            o['_is_terminal'] = o.get('degree', 0) == 1
            o['_is_branching'] = o.get('degree', 0) >= 3
            o['_is_in_ring'] = idx in ring_members
            o['_has_double_bond'] = 'double' in o.get('bond_types', [])
            o['_is_isolated'] = o.get('degree', 0) == 0
            label = o.get('label', '')
            o['_is_heteroatom'] = (
                isinstance(label, str) and label not in ('C', 'H', '')
            )

            c = o.get('color')
            o['_is_unique_color'] = colors.get(c, 0) == 1
            o['_is_most_common_color'] = (
                c is not None and colors.get(c, 0) == max(colors.values(), default=0)
            )
            o['_is_largest'] = False
            o['_is_smallest'] = False

    def _find_ring_members(
        self, objects: List[Dict], adj: Dict,
    ) -> set:
        """Find all atoms that participate in a ring (cycle)."""
        ring_members = set()
        n = len(objects)
        if n < 3:
            return ring_members

        simple_adj = {}
        for i in range(n):
            simple_adj[i] = {nb for nb, _ in adj.get(i, [])}

        for start in range(n):
            visited = set()
            def dfs(current, parent, depth):
                if depth > 8:
                    return False
                visited.add(current)
                for nb in simple_adj.get(current, set()):
                    if nb == parent:
                        continue
                    if nb in visited:
                        if nb == start and depth >= 2:
                            return True
                    elif dfs(nb, current, depth + 1):
                        return True
                visited.discard(current)
                return False

            if dfs(start, -1, 0):
                ring_members.add(start)

        return ring_members
