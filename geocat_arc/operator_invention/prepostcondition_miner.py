"""Mine pre/postconditions from failure clusters."""
from __future__ import annotations
import numpy as np
from .failure_atom import FailureAtom


def mine_preconditions(cluster: list[FailureAtom]) -> list[str]:
    preconditions = []

    all_have_low_error = all(a.error_rate < 0.5 for a in cluster)
    if all_have_low_error:
        preconditions.append("near_solved_state_reachable")

    preconditions.append("input_grid_valid")
    preconditions.append("objects_extractable")

    return preconditions


def mine_postconditions(cluster: list[FailureAtom]) -> list[str]:
    postconditions = []

    avg_error = sum(a.error_rate for a in cluster) / len(cluster) if cluster else 1.0

    postconditions.append("output_grid_valid")
    postconditions.append("output_shape_matches_target")

    if avg_error < 0.3:
        postconditions.append("most_cells_correct")
        postconditions.append("object_structure_preserved")

    return postconditions
