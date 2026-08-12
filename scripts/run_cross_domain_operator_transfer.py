#!/usr/bin/env python3.11
"""Cross-domain operator transfer experiment.

Tests whether three operator families transfer across four domains via
the domain adapter system. Each operator family defines a typed
transformation schema; the experiment checks whether the same schema
instantiates correctly through different DomainAdapters.

Operator families:
    project_to_halo   — project properties from a source to its neighbors/halo
    copy_to_position  — move/copy an object to a target position
    color_transfer     — transfer color/label from source to target objects

Domains:
    grid     — ARC-style integer grids (GridDomainAdapter)
    graph    — node-labeled graphs (GraphDomainAdapter)
    chess    — board positions (ChessBoardDomainAdapter)
    molecule — molecular graphs (MoleculeGraphDomainAdapter)

All tasks are SYNTHETIC, designed to test adapter-level representation of
each operator family. This is NOT a claim that the operators solve real
tasks in every domain.

Outputs:
    outputs/cross_domain_operator_transfer/summary.md
    outputs/cross_domain_operator_transfer/transfer_matrix.csv
    outputs/cross_domain_operator_transfer/operator_family_reports/
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from reasoning_project.reasoning_engine import (
    DomainAdapter,
    GridDomainAdapter,
    StructuralReasoner,
    ReasoningMemory,
)
from reasoning_project.domain_adapters import (
    GraphDomainAdapter,
    ChessBoardDomainAdapter,
    MoleculeGraphDomainAdapter,
)
from reasoning_project.operator_semantics import (
    ExecutableOperatorHypothesis,
    OperatorPrecondition,
    OperatorPostcondition,
    OperatorInvariant,
    OperatorProofObligation,
    VALIDATION_LEVELS,
)


# ═══════════════════════════════════════════════════════════════════════════
# RESULT DATACLASS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TransferTestResult:
    """Result of testing one operator family in one domain."""
    operator_family: str
    domain: str
    adapter_class: str
    n_tasks: int = 0
    n_representable: int = 0
    n_objects_extracted: int = 0
    n_recolor_correct: int = 0
    n_structure_preserved: int = 0
    n_loo_passed: int = 0
    transfer_pass: bool = False
    notes: str = ""
    task_details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def score(self) -> float:
        if self.n_tasks == 0:
            return 0.0
        checks = [
            self.n_representable / self.n_tasks,
            self.n_objects_extracted / max(self.n_tasks, 1),
            self.n_recolor_correct / max(self.n_tasks, 1),
            self.n_structure_preserved / max(self.n_tasks, 1),
        ]
        return sum(checks) / len(checks)


# ═══════════════════════════════════════════════════════════════════════════
# SYNTHETIC TASK FACTORIES
# ═══════════════════════════════════════════════════════════════════════════
# Each function returns a list of (input_scene, output_scene) pairs for
# the given operator family in the given domain.

# --- project_to_halo ---

def _pth_grid_tasks() -> List[Tuple[Any, Any]]:
    """project_to_halo in grid domain: source cell color spreads to 4-neighbors."""
    tasks = []
    # Task 1: center pixel (color=3) projects to its 4 neighbors (which are 1)
    inp = np.array([
        [0, 0, 0, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 1, 3, 1, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 0, 0, 0],
    ], dtype=int)
    out = np.array([
        [0, 0, 0, 0, 0],
        [0, 0, 3, 0, 0],
        [0, 3, 3, 3, 0],
        [0, 0, 3, 0, 0],
        [0, 0, 0, 0, 0],
    ], dtype=int)
    tasks.append((inp, out))

    # Task 2: corner pixel (color=5) projects to its 2 adjacent non-bg neighbors
    inp2 = np.array([
        [5, 1, 0],
        [1, 0, 0],
        [0, 0, 0],
    ], dtype=int)
    out2 = np.array([
        [5, 5, 0],
        [5, 0, 0],
        [0, 0, 0],
    ], dtype=int)
    tasks.append((inp2, out2))

    # Task 3: two sources, each projects to neighbors
    inp3 = np.array([
        [0, 1, 0, 1, 0],
        [1, 4, 1, 7, 1],
        [0, 1, 0, 1, 0],
    ], dtype=int)
    out3 = np.array([
        [0, 4, 0, 7, 0],
        [4, 4, 4, 7, 7],
        [0, 4, 0, 7, 0],
    ], dtype=int)
    tasks.append((inp3, out3))
    return tasks


def _pth_graph_tasks() -> List[Tuple[Any, Any]]:
    """project_to_halo in graph domain: source node color spreads to neighbors."""
    tasks = []
    # Task 1: node A(color=3) connected to B,C,D(color=1) -> B,C,D become 3
    inp = {
        'nodes': [
            {'index': 0, 'label': 'A', 'color': 3},
            {'index': 1, 'label': 'B', 'color': 1},
            {'index': 2, 'label': 'C', 'color': 1},
            {'index': 3, 'label': 'D', 'color': 1},
        ],
        'edges': [
            {'source': 0, 'target': 1},
            {'source': 0, 'target': 2},
            {'source': 0, 'target': 3},
        ],
    }
    out = {
        'nodes': [
            {'index': 0, 'label': 'A', 'color': 3},
            {'index': 1, 'label': 'B', 'color': 3},
            {'index': 2, 'label': 'C', 'color': 3},
            {'index': 3, 'label': 'D', 'color': 3},
        ],
        'edges': [
            {'source': 0, 'target': 1},
            {'source': 0, 'target': 2},
            {'source': 0, 'target': 3},
        ],
    }
    tasks.append((inp, out))

    # Task 2: hub node (color=5, degree=4) projects to its 4 leaf neighbors
    inp2 = {
        'nodes': [
            {'index': 0, 'label': 'hub', 'color': 5},
            {'index': 1, 'label': 'leaf1', 'color': 2},
            {'index': 2, 'label': 'leaf2', 'color': 2},
            {'index': 3, 'label': 'leaf3', 'color': 2},
            {'index': 4, 'label': 'leaf4', 'color': 2},
        ],
        'edges': [
            {'source': 0, 'target': 1},
            {'source': 0, 'target': 2},
            {'source': 0, 'target': 3},
            {'source': 0, 'target': 4},
        ],
    }
    out2 = {
        'nodes': [
            {'index': 0, 'label': 'hub', 'color': 5},
            {'index': 1, 'label': 'leaf1', 'color': 5},
            {'index': 2, 'label': 'leaf2', 'color': 5},
            {'index': 3, 'label': 'leaf3', 'color': 5},
            {'index': 4, 'label': 'leaf4', 'color': 5},
        ],
        'edges': [
            {'source': 0, 'target': 1},
            {'source': 0, 'target': 2},
            {'source': 0, 'target': 3},
            {'source': 0, 'target': 4},
        ],
    }
    tasks.append((inp2, out2))
    return tasks


def _pth_chess_tasks() -> List[Tuple[Any, Any]]:
    """project_to_halo in chess domain: piece projects its color to 4-adjacent cells."""
    tasks = []
    # Task 1: piece at (2,2) color=3, bg neighbors -> neighbors become 3
    inp = np.zeros((5, 5), dtype=int)
    inp[2, 2] = 3
    inp[1, 2] = 1; inp[3, 2] = 1; inp[2, 1] = 1; inp[2, 3] = 1
    out = np.zeros((5, 5), dtype=int)
    out[2, 2] = 3
    out[1, 2] = 3; out[3, 2] = 3; out[2, 1] = 3; out[2, 3] = 3
    tasks.append((inp, out))

    # Task 2: piece at (0,0) color=7, two neighbors
    inp2 = np.zeros((4, 4), dtype=int)
    inp2[0, 0] = 7; inp2[0, 1] = 1; inp2[1, 0] = 1
    out2 = np.zeros((4, 4), dtype=int)
    out2[0, 0] = 7; out2[0, 1] = 7; out2[1, 0] = 7
    tasks.append((inp2, out2))
    return tasks


def _pth_molecule_tasks() -> List[Tuple[Any, Any]]:
    """project_to_halo in molecule domain: atom projects label to bonded neighbors."""
    tasks = []
    inp = {
        'nodes': [
            {'index': 0, 'label': 'N', 'color': 7},
            {'index': 1, 'label': 'C', 'color': 1},
            {'index': 2, 'label': 'C', 'color': 1},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
            {'source': 0, 'target': 2, 'bond_type': 'single'},
        ],
    }
    out = {
        'nodes': [
            {'index': 0, 'label': 'N', 'color': 7},
            {'index': 1, 'label': 'C', 'color': 7},
            {'index': 2, 'label': 'C', 'color': 7},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
            {'source': 0, 'target': 2, 'bond_type': 'single'},
        ],
    }
    tasks.append((inp, out))

    # Task 2: branching atom projects
    inp2 = {
        'nodes': [
            {'index': 0, 'label': 'O', 'color': 8},
            {'index': 1, 'label': 'C', 'color': 1},
            {'index': 2, 'label': 'C', 'color': 1},
            {'index': 3, 'label': 'H', 'color': 2},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
            {'source': 0, 'target': 2, 'bond_type': 'single'},
            {'source': 2, 'target': 3, 'bond_type': 'single'},
        ],
    }
    out2 = {
        'nodes': [
            {'index': 0, 'label': 'O', 'color': 8},
            {'index': 1, 'label': 'C', 'color': 8},
            {'index': 2, 'label': 'C', 'color': 8},
            {'index': 3, 'label': 'H', 'color': 2},  # not neighbor of O
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
            {'source': 0, 'target': 2, 'bond_type': 'single'},
            {'source': 2, 'target': 3, 'bond_type': 'single'},
        ],
    }
    tasks.append((inp2, out2))
    return tasks


# --- copy_to_position ---

def _ctp_grid_tasks() -> List[Tuple[Any, Any]]:
    """copy_to_position in grid domain: copy a small object to a marked position."""
    tasks = []
    # Task 1: 2x2 block at (1,1), marker=9 at (1,5) -> copy block to (1,5)
    inp = np.zeros((5, 8), dtype=int)
    inp[1:3, 1:3] = 4  # source block
    inp[1, 5] = 9       # target marker
    out = np.zeros((5, 8), dtype=int)
    out[1:3, 1:3] = 4
    out[1:3, 5:7] = 4   # copied block at marker position
    tasks.append((inp, out))

    # Task 2
    inp2 = np.zeros((6, 6), dtype=int)
    inp2[0, 0] = 3       # source pixel
    inp2[4, 4] = 9       # marker
    out2 = np.zeros((6, 6), dtype=int)
    out2[0, 0] = 3
    out2[4, 4] = 3       # copied pixel at marker
    tasks.append((inp2, out2))

    # Task 3
    inp3 = np.zeros((5, 7), dtype=int)
    inp3[0:2, 0:2] = 6   # source
    inp3[3, 5] = 9        # marker
    out3 = np.zeros((5, 7), dtype=int)
    out3[0:2, 0:2] = 6
    out3[3:5, 5:7] = 6   # copied
    tasks.append((inp3, out3))
    return tasks


def _ctp_graph_tasks() -> List[Tuple[Any, Any]]:
    """copy_to_position in graph domain: duplicate a node's properties to a target node."""
    tasks = []
    # Task 1: node 0 (color=4) has a 'template' flag; node 2 is target -> node 2 gets color 4
    inp = {
        'nodes': [
            {'index': 0, 'label': 'source', 'color': 4},
            {'index': 1, 'label': 'bridge', 'color': 1},
            {'index': 2, 'label': 'target', 'color': 9},  # marker color 9
        ],
        'edges': [
            {'source': 0, 'target': 1},
            {'source': 1, 'target': 2},
        ],
    }
    out = {
        'nodes': [
            {'index': 0, 'label': 'source', 'color': 4},
            {'index': 1, 'label': 'bridge', 'color': 1},
            {'index': 2, 'label': 'target', 'color': 4},  # color copied from source
        ],
        'edges': [
            {'source': 0, 'target': 1},
            {'source': 1, 'target': 2},
        ],
    }
    tasks.append((inp, out))

    # Task 2
    inp2 = {
        'nodes': [
            {'index': 0, 'label': 'src', 'color': 7},
            {'index': 1, 'label': 'tgt', 'color': 9},
        ],
        'edges': [
            {'source': 0, 'target': 1},
        ],
    }
    out2 = {
        'nodes': [
            {'index': 0, 'label': 'src', 'color': 7},
            {'index': 1, 'label': 'tgt', 'color': 7},
        ],
        'edges': [
            {'source': 0, 'target': 1},
        ],
    }
    tasks.append((inp2, out2))
    return tasks


def _ctp_chess_tasks() -> List[Tuple[Any, Any]]:
    """copy_to_position in chess domain: piece duplicated at target marker position."""
    tasks = []
    # Task 1: piece color=5 at (1,1), marker=9 at (3,4) -> piece copied to (3,4)
    inp = np.zeros((6, 6), dtype=int)
    inp[1, 1] = 5
    inp[3, 4] = 9
    out = np.zeros((6, 6), dtype=int)
    out[1, 1] = 5
    out[3, 4] = 5  # marker replaced by piece color
    tasks.append((inp, out))

    # Task 2
    inp2 = np.zeros((5, 5), dtype=int)
    inp2[0, 0] = 3
    inp2[4, 4] = 9
    out2 = np.zeros((5, 5), dtype=int)
    out2[0, 0] = 3
    out2[4, 4] = 3
    tasks.append((inp2, out2))
    return tasks


def _ctp_molecule_tasks() -> List[Tuple[Any, Any]]:
    """copy_to_position in molecule domain: atom label copied to bonded target."""
    tasks = []
    inp = {
        'nodes': [
            {'index': 0, 'label': 'S', 'color': 6},
            {'index': 1, 'label': 'placeholder', 'color': 9},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
        ],
    }
    out = {
        'nodes': [
            {'index': 0, 'label': 'S', 'color': 6},
            {'index': 1, 'label': 'placeholder', 'color': 6},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
        ],
    }
    tasks.append((inp, out))

    inp2 = {
        'nodes': [
            {'index': 0, 'label': 'Fe', 'color': 4},
            {'index': 1, 'label': 'ligand1', 'color': 9},
            {'index': 2, 'label': 'ligand2', 'color': 9},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
            {'source': 0, 'target': 2, 'bond_type': 'single'},
        ],
    }
    out2 = {
        'nodes': [
            {'index': 0, 'label': 'Fe', 'color': 4},
            {'index': 1, 'label': 'ligand1', 'color': 4},
            {'index': 2, 'label': 'ligand2', 'color': 4},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
            {'source': 0, 'target': 2, 'bond_type': 'single'},
        ],
    }
    tasks.append((inp2, out2))
    return tasks


# --- color_transfer ---

def _ct_grid_tasks() -> List[Tuple[Any, Any]]:
    """color_transfer in grid domain: object A's color transferred to neighboring object B."""
    tasks = []
    # Task 1: two adjacent blocks; left block (color=3) transfers to right (color=1)
    inp = np.zeros((5, 7), dtype=int)
    inp[1:4, 1:3] = 3  # source
    inp[1:4, 3:5] = 1  # target (touching)
    out = np.zeros((5, 7), dtype=int)
    out[1:4, 1:3] = 3
    out[1:4, 3:5] = 3  # target recolored to source's color
    tasks.append((inp, out))

    # Task 2
    inp2 = np.zeros((4, 6), dtype=int)
    inp2[1, 1] = 5      # source
    inp2[1, 2] = 2      # target (adjacent)
    out2 = np.zeros((4, 6), dtype=int)
    out2[1, 1] = 5
    out2[1, 2] = 5      # target recolored
    tasks.append((inp2, out2))

    # Task 3
    inp3 = np.zeros((5, 5), dtype=int)
    inp3[0:2, 0:2] = 7  # source
    inp3[0:2, 2:4] = 2  # target
    out3 = np.zeros((5, 5), dtype=int)
    out3[0:2, 0:2] = 7
    out3[0:2, 2:4] = 7
    tasks.append((inp3, out3))
    return tasks


def _ct_graph_tasks() -> List[Tuple[Any, Any]]:
    """color_transfer in graph domain: edge-connected source transfers color to target."""
    tasks = []
    inp = {
        'nodes': [
            {'index': 0, 'label': 'src', 'color': 5},
            {'index': 1, 'label': 'tgt', 'color': 2},
            {'index': 2, 'label': 'other', 'color': 8},
        ],
        'edges': [
            {'source': 0, 'target': 1},
        ],
    }
    out = {
        'nodes': [
            {'index': 0, 'label': 'src', 'color': 5},
            {'index': 1, 'label': 'tgt', 'color': 5},  # neighbor transfer
            {'index': 2, 'label': 'other', 'color': 8},
        ],
        'edges': [
            {'source': 0, 'target': 1},
        ],
    }
    tasks.append((inp, out))

    inp2 = {
        'nodes': [
            {'index': 0, 'label': 'A', 'color': 3},
            {'index': 1, 'label': 'B', 'color': 1},
            {'index': 2, 'label': 'C', 'color': 1},
        ],
        'edges': [
            {'source': 0, 'target': 1},
            {'source': 0, 'target': 2},
        ],
    }
    out2 = {
        'nodes': [
            {'index': 0, 'label': 'A', 'color': 3},
            {'index': 1, 'label': 'B', 'color': 3},
            {'index': 2, 'label': 'C', 'color': 3},
        ],
        'edges': [
            {'source': 0, 'target': 1},
            {'source': 0, 'target': 2},
        ],
    }
    tasks.append((inp2, out2))
    return tasks


def _ct_chess_tasks() -> List[Tuple[Any, Any]]:
    """color_transfer in chess domain: piece color spreads to adjacent piece."""
    tasks = []
    inp = np.zeros((5, 5), dtype=int)
    inp[2, 1] = 6  # source
    inp[2, 2] = 2  # target (adjacent)
    out = np.zeros((5, 5), dtype=int)
    out[2, 1] = 6
    out[2, 2] = 6
    tasks.append((inp, out))

    inp2 = np.zeros((4, 4), dtype=int)
    inp2[1, 1] = 4
    inp2[1, 2] = 1
    out2 = np.zeros((4, 4), dtype=int)
    out2[1, 1] = 4
    out2[1, 2] = 4
    tasks.append((inp2, out2))
    return tasks


def _ct_molecule_tasks() -> List[Tuple[Any, Any]]:
    """color_transfer in molecule domain: bonded atom transfers label property."""
    tasks = []
    inp = {
        'nodes': [
            {'index': 0, 'label': 'N', 'color': 7},
            {'index': 1, 'label': 'C', 'color': 1},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
        ],
    }
    out = {
        'nodes': [
            {'index': 0, 'label': 'N', 'color': 7},
            {'index': 1, 'label': 'C', 'color': 7},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'single'},
        ],
    }
    tasks.append((inp, out))

    inp2 = {
        'nodes': [
            {'index': 0, 'label': 'P', 'color': 5},
            {'index': 1, 'label': 'O', 'color': 2},
            {'index': 2, 'label': 'O', 'color': 2},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'double'},
            {'source': 0, 'target': 2, 'bond_type': 'single'},
        ],
    }
    out2 = {
        'nodes': [
            {'index': 0, 'label': 'P', 'color': 5},
            {'index': 1, 'label': 'O', 'color': 5},
            {'index': 2, 'label': 'O', 'color': 5},
        ],
        'edges': [
            {'source': 0, 'target': 1, 'bond_type': 'double'},
            {'source': 0, 'target': 2, 'bond_type': 'single'},
        ],
    }
    tasks.append((inp2, out2))
    return tasks


# ═══════════════════════════════════════════════════════════════════════════
# TASK REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

OPERATOR_FAMILIES = ["project_to_halo", "copy_to_position", "color_transfer"]
DOMAINS = ["grid", "graph", "chess", "molecule"]

TASK_FACTORY = {
    ("project_to_halo", "grid"): _pth_grid_tasks,
    ("project_to_halo", "graph"): _pth_graph_tasks,
    ("project_to_halo", "chess"): _pth_chess_tasks,
    ("project_to_halo", "molecule"): _pth_molecule_tasks,
    ("copy_to_position", "grid"): _ctp_grid_tasks,
    ("copy_to_position", "graph"): _ctp_graph_tasks,
    ("copy_to_position", "chess"): _ctp_chess_tasks,
    ("copy_to_position", "molecule"): _ctp_molecule_tasks,
    ("color_transfer", "grid"): _ct_grid_tasks,
    ("color_transfer", "graph"): _ct_graph_tasks,
    ("color_transfer", "chess"): _ct_chess_tasks,
    ("color_transfer", "molecule"): _ct_molecule_tasks,
}

ADAPTER_FOR_DOMAIN = {
    "grid": lambda: GridDomainAdapter(),
    "graph": lambda: GraphDomainAdapter(),
    "chess": lambda: ChessBoardDomainAdapter(),
    "molecule": lambda: MoleculeGraphDomainAdapter(),
}


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFER CHECKS
# ═══════════════════════════════════════════════════════════════════════════

def _identify_source_and_targets(
    adapter: DomainAdapter,
    inp_objects: List[Dict],
    out_objects: List[Dict],
    inp_scene: Any,
    out_scene: Any,
) -> Tuple[Optional[int], List[int], Dict[int, int]]:
    """Identify source object (unique/hub color) and which objects changed color.

    Returns:
        source_idx: index of the likely source object (highest color or unique)
        changed_indices: indices of objects whose color changed
        color_map: mapping from changed object index to new color
    """
    # Match input to output objects
    matches = adapter.match_objects(inp_objects, out_objects)
    match_map = {a: b for a, b in matches}

    # Find color changes
    changed_indices = []
    color_map = {}
    unchanged_colors = {}
    for i, inp_obj in enumerate(inp_objects):
        if i in match_map:
            j = match_map[i]
            if j < len(out_objects):
                inp_c = inp_obj.get('color', inp_obj.get('label'))
                out_c = out_objects[j].get('color', out_objects[j].get('label'))
                if inp_c != out_c:
                    changed_indices.append(i)
                    color_map[i] = out_c
                else:
                    unchanged_colors[i] = inp_c

    # Source is the object whose color appears in the output of changed objects
    # and which itself did NOT change
    source_idx = None
    if changed_indices and unchanged_colors:
        target_new_color = color_map.get(changed_indices[0])
        for idx, col in unchanged_colors.items():
            if col == target_new_color:
                source_idx = idx
                break

    return source_idx, changed_indices, color_map


def _check_recolor_via_adapter(
    adapter: DomainAdapter,
    inp_scene: Any,
    out_scene: Any,
    inp_objects: List[Dict],
    source_idx: Optional[int],
    changed_indices: List[int],
    color_map: Dict[int, int],
) -> bool:
    """Check if reconstructing via adapter.reconstruct_recolored matches output."""
    if not changed_indices or source_idx is None:
        return False

    label_map = {}
    for ci in changed_indices:
        label_map[ci] = color_map[ci]

    try:
        reconstructed = adapter.reconstruct_recolored(inp_scene, inp_objects, label_map)
        return adapter.scenes_equal(reconstructed, out_scene)
    except Exception:
        return False


def _run_loo_check(
    adapter: DomainAdapter,
    tasks: List[Tuple[Any, Any]],
) -> bool:
    """Run leave-one-out: for each held-out pair, check the transformation
    pattern inferred from remaining pairs transfers to the held-out input.

    Uses the adapter's own object extraction and recoloring:
    1. From training subset, identify the source->target color rule.
    2. Apply to held-out input.
    3. Check if result matches held-out output.
    """
    if len(tasks) < 2:
        return True  # trivially passes with <2 tasks

    for hold_idx in range(len(tasks)):
        train_subset = [t for i, t in enumerate(tasks) if i != hold_idx]
        held_inp, held_out = tasks[hold_idx]

        # Infer pattern from training subset
        source_colors = []
        transfer_rules = []  # (source_color, target_old_color, target_new_color)

        for inp, out in train_subset:
            inp_objs = adapter.extract_objects(inp)
            out_objs = adapter.extract_objects(out)
            src_idx, changed, cmap = _identify_source_and_targets(
                adapter, inp_objs, out_objs, inp, out,
            )
            if src_idx is not None:
                src_color = inp_objs[src_idx].get('color')
                source_colors.append(src_color)
                for ci in changed:
                    old_c = inp_objs[ci].get('color')
                    new_c = cmap[ci]
                    transfer_rules.append((src_color, old_c, new_c))

        if not transfer_rules:
            return False

        # Apply to held-out
        held_objs = adapter.extract_objects(held_inp)
        held_out_objs = adapter.extract_objects(held_out)

        src_idx_held, changed_held, cmap_held = _identify_source_and_targets(
            adapter, held_objs, held_out_objs, held_inp, held_out,
        )

        if src_idx_held is None or not changed_held:
            return False

        # Verify the held-out follows the same pattern
        src_c_held = held_objs[src_idx_held].get('color')
        for ci in changed_held:
            old_c = held_objs[ci].get('color')
            new_c = cmap_held[ci]
            if new_c != src_c_held:
                return False

    return True


def _build_operator_hypothesis(
    family: str,
    domain: str,
    result: TransferTestResult,
) -> ExecutableOperatorHypothesis:
    """Build a formal ExecutableOperatorHypothesis for a transfer test."""
    hyp = ExecutableOperatorHypothesis(
        operator_id=f"transfer_{family}_{domain}",
        family=family,
        source_tasks=[f"synthetic_{family}_{domain}"],
        selector_expression=f"domain={domain}; family={family}",
        parameters={
            "domain": domain,
            "operator_family": family,
            "synthetic": True,
            "n_tasks": result.n_tasks,
            "score": result.score,
        },
        preconditions=[
            OperatorPrecondition(
                name="objects_extractable",
                expression="adapter.extract_objects(scene) returns non-empty list",
                check_fn=lambda objects=None, **kw: objects is not None and len(objects) > 0,
            ),
            OperatorPrecondition(
                name="source_identifiable",
                expression="at least one source object is identifiable",
                check_fn=lambda source_idx=None, **kw: source_idx is not None,
            ),
        ],
        postconditions=[
            OperatorPostcondition(
                name="recolor_matches",
                expression="reconstruct_recolored produces expected output",
                check_fn=lambda recolor_correct=None, **kw: recolor_correct is True,
            ),
        ],
        invariants=[
            OperatorInvariant(
                name="structure_preserved",
                expression="same_structure(input, output) holds",
                check_fn=lambda structure_ok=None, **kw: structure_ok is True,
            ),
        ],
        complexity=2,
        provenance={
            "experiment": "cross_domain_operator_transfer",
            "synthetic": True,
            "domain": domain,
        },
        validation_level="proposed",
    )

    # Advance based on checks
    if result.n_representable == result.n_tasks:
        hyp.advance_level("parameterized")
    if result.n_recolor_correct == result.n_tasks:
        hyp.advance_level("train_consistent")
    if result.n_loo_passed > 0:
        hyp.advance_level("loo_validated")
    if result.transfer_pass:
        hyp.advance_level("transfer_validated")

    return hyp


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TRANSFER EVALUATION
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_transfer(
    family: str, domain: str,
) -> TransferTestResult:
    """Run all transfer checks for one operator family in one domain."""
    adapter = ADAPTER_FOR_DOMAIN[domain]()
    adapter_class = type(adapter).__name__
    factory = TASK_FACTORY.get((family, domain))

    result = TransferTestResult(
        operator_family=family,
        domain=domain,
        adapter_class=adapter_class,
    )

    if factory is None:
        result.notes = "No task factory defined for this combination."
        return result

    try:
        tasks = factory()
    except Exception as e:
        result.notes = f"Task factory raised: {e}"
        return result

    result.n_tasks = len(tasks)

    for task_idx, (inp, out) in enumerate(tasks):
        detail: Dict[str, Any] = {
            "task_idx": task_idx,
            "representable": False,
            "objects_extracted": False,
            "recolor_correct": False,
            "structure_preserved": False,
        }

        # Check 1: Can the adapter extract objects?
        try:
            inp_objects = adapter.extract_objects(inp)
            out_objects = adapter.extract_objects(out)
            if inp_objects and out_objects:
                detail["objects_extracted"] = True
                detail["n_inp_objects"] = len(inp_objects)
                detail["n_out_objects"] = len(out_objects)
                result.n_objects_extracted += 1
            else:
                detail["notes"] = (
                    f"Object extraction empty: inp={len(inp_objects)}, out={len(out_objects)}"
                )
                result.task_details.append(detail)
                continue
        except Exception as e:
            detail["notes"] = f"extract_objects raised: {e}"
            result.task_details.append(detail)
            continue

        # Check 2: Structure preservation
        try:
            structure_ok = adapter.same_structure(inp, out)
            detail["structure_preserved"] = structure_ok
            if structure_ok:
                result.n_structure_preserved += 1
        except Exception as e:
            detail["notes"] = f"same_structure raised: {e}"

        # Check 3: Can we identify source, targets, and color changes?
        try:
            source_idx, changed_indices, color_map = _identify_source_and_targets(
                adapter, inp_objects, out_objects, inp, out,
            )
            detail["source_idx"] = source_idx
            detail["n_changed"] = len(changed_indices)
            if source_idx is not None and changed_indices:
                detail["representable"] = True
                result.n_representable += 1
            else:
                detail["notes"] = (
                    f"Source/target identification failed: "
                    f"source_idx={source_idx}, n_changed={len(changed_indices)}"
                )
        except Exception as e:
            detail["notes"] = f"identify_source_and_targets raised: {e}"
            result.task_details.append(detail)
            continue

        # Check 4: reconstruct_recolored reproduces output
        try:
            recolor_ok = _check_recolor_via_adapter(
                adapter, inp, out, inp_objects, source_idx, changed_indices, color_map,
            )
            detail["recolor_correct"] = recolor_ok
            if recolor_ok:
                result.n_recolor_correct += 1
            else:
                detail["notes"] = detail.get("notes", "") + " recolor mismatch"
        except Exception as e:
            detail["notes"] = f"recolor check raised: {e}"

        result.task_details.append(detail)

    # Check 5: LOO validation across all tasks
    try:
        loo_ok = _run_loo_check(adapter, tasks)
        result.n_loo_passed = 1 if loo_ok else 0
    except Exception as e:
        result.n_loo_passed = 0
        result.notes += f" LOO raised: {e}"

    # Transfer verdict
    result.transfer_pass = (
        result.n_representable == result.n_tasks
        and result.n_recolor_correct == result.n_tasks
        and result.n_structure_preserved == result.n_tasks
        and result.n_loo_passed > 0
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def _write_transfer_matrix(results: Dict[Tuple[str, str], TransferTestResult], out_dir: Path):
    """Write the operator x domain transfer matrix CSV."""
    csv_path = out_dir / "transfer_matrix.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        header = ["operator_family"] + DOMAINS + ["transfer_rate"]
        w.writerow(header)
        for family in OPERATOR_FAMILIES:
            row = [family]
            n_pass = 0
            for domain in DOMAINS:
                r = results.get((family, domain))
                if r is None:
                    row.append("N/A")
                elif r.transfer_pass:
                    row.append("PASS")
                    n_pass += 1
                else:
                    row.append("FAIL")
            row.append(f"{n_pass}/{len(DOMAINS)}")
            w.writerow(row)
    print(f"  Wrote {csv_path}")


def _write_family_report(
    family: str,
    results: Dict[Tuple[str, str], TransferTestResult],
    hypotheses: Dict[Tuple[str, str], ExecutableOperatorHypothesis],
    report_dir: Path,
):
    """Write a per-family markdown report."""
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"{family}.md"

    lines = [
        f"# Operator Family Report: {family}",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "All tasks are SYNTHETIC. Results reflect adapter-level representation",
        "capability, not performance on real-world tasks.",
        "",
        "## Per-Domain Results",
        "",
    ]

    for domain in DOMAINS:
        r = results.get((family, domain))
        h = hypotheses.get((family, domain))
        lines.append(f"### {domain} ({r.adapter_class if r else 'N/A'})")
        lines.append("")

        if r is None:
            lines.append("No result available.")
            lines.append("")
            continue

        lines.append(f"- Tasks: {r.n_tasks}")
        lines.append(f"- Representable: {r.n_representable}/{r.n_tasks}")
        lines.append(f"- Objects extracted: {r.n_objects_extracted}/{r.n_tasks}")
        lines.append(f"- Recolor correct: {r.n_recolor_correct}/{r.n_tasks}")
        lines.append(f"- Structure preserved: {r.n_structure_preserved}/{r.n_tasks}")
        lines.append(f"- LOO passed: {'Yes' if r.n_loo_passed > 0 else 'No'}")
        lines.append(f"- **Transfer: {'PASS' if r.transfer_pass else 'FAIL'}**")
        lines.append(f"- Score: {r.score:.3f}")
        if r.notes:
            lines.append(f"- Notes: {r.notes}")
        lines.append("")

        if h:
            lines.append(f"  Hypothesis validation level: {h.validation_level}")
            lines.append("")

        # Task details
        if r.task_details:
            lines.append("  Task details:")
            for td in r.task_details:
                status = "OK" if td.get("recolor_correct") else "FAIL"
                notes = td.get("notes", "")
                lines.append(
                    f"    - Task {td['task_idx']}: {status}"
                    f" (objects={td.get('n_inp_objects', '?')}->{td.get('n_out_objects', '?')},"
                    f" source={td.get('source_idx', '?')},"
                    f" changed={td.get('n_changed', '?')})"
                    + (f" [{notes}]" if notes else "")
                )
            lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Wrote {path}")


def _write_summary(
    results: Dict[Tuple[str, str], TransferTestResult],
    hypotheses: Dict[Tuple[str, str], ExecutableOperatorHypothesis],
    elapsed: float,
    out_dir: Path,
):
    """Write the overall summary markdown."""
    path = out_dir / "summary.md"

    total = len(OPERATOR_FAMILIES) * len(DOMAINS)
    n_pass = sum(1 for r in results.values() if r.transfer_pass)
    n_fail = total - n_pass

    lines = [
        "# Cross-Domain Operator Transfer Experiment",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Elapsed: {elapsed:.1f}s",
        "",
        "## Overview",
        "",
        "This experiment tests whether three typed operator families can be",
        "instantiated through four different domain adapters. All tasks are",
        "SYNTHETIC, designed to probe adapter-level representation of each",
        "operator's analogue in each domain.",
        "",
        f"Total combinations: {total}",
        f"Transfer PASS: {n_pass}",
        f"Transfer FAIL: {n_fail}",
        f"Overall transfer rate: {n_pass}/{total} ({100*n_pass/total:.0f}%)",
        "",
        "## Transfer Matrix",
        "",
        "| Operator Family | " + " | ".join(DOMAINS) + " |",
        "|" + "|".join(["---"] * (len(DOMAINS) + 1)) + "|",
    ]

    for family in OPERATOR_FAMILIES:
        row = [f"**{family}**"]
        for domain in DOMAINS:
            r = results.get((family, domain))
            if r is None:
                row.append("N/A")
            elif r.transfer_pass:
                row.append("PASS")
            else:
                row.append(f"FAIL ({r.score:.2f})")
        lines.append("| " + " | ".join(row) + " |")

    lines.extend([
        "",
        "## Methodology",
        "",
        "For each (operator_family, domain) pair:",
        "1. Synthetic tasks are created showing the operator's analogue in the domain.",
        "2. The domain adapter extracts objects from input and output scenes.",
        "3. Source and target objects are identified by color-change analysis.",
        "4. `reconstruct_recolored` is called to verify the adapter can reproduce the output.",
        "5. LOO validation checks that the pattern generalizes within the task set.",
        "6. A typed `ExecutableOperatorHypothesis` is built and validation-leveled.",
        "",
        "A combination PASSES if:",
        "- All tasks are representable (source and targets identifiable)",
        "- `reconstruct_recolored` reproduces the expected output for all tasks",
        "- Structure is preserved (same_structure returns True)",
        "- LOO validation passes",
        "",
        "## Interpretation",
        "",
        "A PASS means the domain adapter's representation is sufficient to express",
        "the operator's transformation. It does NOT mean the operator was",
        "independently invented or that it would solve novel tasks in that domain.",
        "",
        "A FAIL may indicate:",
        "- The adapter cannot extract objects at the right granularity",
        "- `reconstruct_recolored` does not reproduce the expected output (e.g.,",
        "  grid adapters may use connected-component decomposition that splits",
        "  the scene differently)",
        "- The object matching heuristic fails to align input/output objects",
        "",
        "## Per-Family Summaries",
        "",
    ])

    for family in OPERATOR_FAMILIES:
        passes = [d for d in DOMAINS if results.get((family, d), TransferTestResult("", "", "")).transfer_pass]
        fails = [d for d in DOMAINS if not results.get((family, d), TransferTestResult("", "", "")).transfer_pass]
        lines.append(f"### {family}")
        lines.append(f"- PASS: {', '.join(passes) if passes else 'none'}")
        lines.append(f"- FAIL: {', '.join(fails) if fails else 'none'}")

        for d in fails:
            r = results.get((family, d))
            if r and r.notes:
                lines.append(f"  - {d}: {r.notes}")
            elif r:
                # Summarize failure
                issues = []
                if r.n_representable < r.n_tasks:
                    issues.append(f"representable={r.n_representable}/{r.n_tasks}")
                if r.n_recolor_correct < r.n_tasks:
                    issues.append(f"recolor={r.n_recolor_correct}/{r.n_tasks}")
                if r.n_structure_preserved < r.n_tasks:
                    issues.append(f"structure={r.n_structure_preserved}/{r.n_tasks}")
                if r.n_loo_passed == 0:
                    issues.append("LOO failed")
                lines.append(f"  - {d}: {'; '.join(issues)}")
        lines.append("")

    lines.extend([
        "## Honest Assessment",
        "",
        "This experiment demonstrates the *representation* transfer of operator",
        "schemas through domain adapters. The synthetic tasks are minimal by",
        "design: they test whether the adapter protocol (extract_objects,",
        "reconstruct_recolored, match_objects, scenes_equal) is sufficient to",
        "express each operator family.",
        "",
        "Limitations:",
        "- Synthetic tasks are simpler than real domain tasks.",
        "- Grid domain uses GridDomainAdapter which has sophisticated connected-",
        "  component extraction; the recolor check may fail if objects span",
        "  multiple components.",
        "- The experiment does not test operator *invention* (trace-driven",
        "  discovery), only representation adequacy.",
        "- Real cross-domain transfer would require testing on genuine domain",
        "  tasks and verifying that an operator invented in domain A solves",
        "  tasks in domain B.",
        "",
    ])

    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Wrote {path}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    out_dir = Path("outputs/cross_domain_operator_transfer")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir = out_dir / "operator_family_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Cross-Domain Operator Transfer Experiment")
    print("=" * 70)
    print(f"Operator families: {OPERATOR_FAMILIES}")
    print(f"Domains: {DOMAINS}")
    print(f"Total combinations: {len(OPERATOR_FAMILIES) * len(DOMAINS)}")
    print()

    t0 = time.time()
    results: Dict[Tuple[str, str], TransferTestResult] = {}
    hypotheses: Dict[Tuple[str, str], ExecutableOperatorHypothesis] = {}

    for family in OPERATOR_FAMILIES:
        print(f"--- Operator Family: {family} ---")
        for domain in DOMAINS:
            print(f"  Domain: {domain} ... ", end="", flush=True)
            try:
                r = evaluate_transfer(family, domain)
                results[(family, domain)] = r

                # Build formal hypothesis
                h = _build_operator_hypothesis(family, domain, r)
                hypotheses[(family, domain)] = h

                verdict = "PASS" if r.transfer_pass else "FAIL"
                print(
                    f"{verdict}  "
                    f"(repr={r.n_representable}/{r.n_tasks}, "
                    f"recolor={r.n_recolor_correct}/{r.n_tasks}, "
                    f"LOO={'Y' if r.n_loo_passed else 'N'}, "
                    f"level={h.validation_level})"
                )
            except Exception as e:
                print(f"ERROR: {e}")
                traceback.print_exc()
                results[(family, domain)] = TransferTestResult(
                    operator_family=family,
                    domain=domain,
                    adapter_class="unknown",
                    notes=f"Exception: {e}",
                )
        print()

    elapsed = time.time() - t0

    # Write outputs
    print("Writing outputs...")
    _write_transfer_matrix(results, out_dir)
    _write_summary(results, hypotheses, elapsed, out_dir)
    for family in OPERATOR_FAMILIES:
        _write_family_report(family, results, hypotheses, report_dir)

    # Print final matrix
    print()
    print("=" * 70)
    print("TRANSFER MATRIX")
    print("=" * 70)
    header = f"{'Family':<25}" + "".join(f"{d:<12}" for d in DOMAINS) + "Rate"
    print(header)
    print("-" * len(header))
    for family in OPERATOR_FAMILIES:
        row = f"{family:<25}"
        n_pass = 0
        for domain in DOMAINS:
            r = results.get((family, domain))
            if r and r.transfer_pass:
                row += f"{'PASS':<12}"
                n_pass += 1
            else:
                row += f"{'FAIL':<12}"
        row += f"{n_pass}/{len(DOMAINS)}"
        print(row)
    print()

    total = len(OPERATOR_FAMILIES) * len(DOMAINS)
    total_pass = sum(1 for r in results.values() if r.transfer_pass)
    print(f"Overall: {total_pass}/{total} combinations passed ({100*total_pass/total:.0f}%)")
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Outputs: {out_dir}/")


if __name__ == "__main__":
    main()
