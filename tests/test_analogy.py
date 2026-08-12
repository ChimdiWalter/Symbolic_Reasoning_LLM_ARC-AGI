"""Tests for analogical transfer (H6)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.analogy import (
    TaskSignature,
    compute_task_signature,
    find_analogous_tasks,
    signature_similarity,
    transfer_solution,
)


# ---------------------------------------------------------------------------
# Signature computation
# ---------------------------------------------------------------------------

def test_compute_signature_identity():
    """Identity task: same input/output should give neutral signature."""
    grid = np.array([[1, 2], [3, 0]])
    pairs = [(grid, grid.copy())]
    sig = compute_task_signature(pairs)
    assert sig.size_relation == pytest.approx(1.0)
    assert sig.color_count_change == pytest.approx(0.0)
    assert sig.same_shape is True
    assert sig.color_preservation_rate == pytest.approx(1.0)


def test_compute_signature_color_change():
    """Task that changes colors should reflect in signature."""
    inp = np.array([[1, 1], [2, 2]])
    out = np.array([[3, 3], [4, 4]])
    pairs = [(inp, out)]
    sig = compute_task_signature(pairs)
    assert sig.same_shape is True
    # Colors changed: inp has {1,2}, out has {3,4} -> shared = 0, union = 4
    assert sig.color_preservation_rate < 0.5


def test_compute_signature_size_change():
    """Task that doubles the grid size."""
    inp = np.array([[1, 2], [3, 4]])
    out = np.array([[1, 2, 1, 2], [3, 4, 3, 4], [1, 2, 1, 2], [3, 4, 3, 4]])
    pairs = [(inp, out)]
    sig = compute_task_signature(pairs)
    assert sig.size_relation == pytest.approx(4.0)
    assert sig.same_shape is False


def test_compute_signature_symmetry():
    """Symmetric grid detection."""
    # Horizontally symmetric input
    inp = np.array([[1, 2, 1], [3, 4, 3]])
    out = np.array([[1, 2, 1], [3, 4, 3]])
    pairs = [(inp, out)]
    sig = compute_task_signature(pairs)
    assert sig.symmetry_v_in == pytest.approx(1.0)
    assert sig.symmetry_v_out == pytest.approx(1.0)


def test_compute_signature_empty():
    """Empty pairs should return default signature."""
    sig = compute_task_signature([])
    assert sig.size_relation == pytest.approx(1.0)
    assert sig.same_shape is True


# ---------------------------------------------------------------------------
# Signature similarity
# ---------------------------------------------------------------------------

def test_similarity_identical():
    """Identical signatures should have similarity 1.0."""
    sig = TaskSignature(size_relation=2.0, color_count_change=-1.0)
    assert signature_similarity(sig, sig) == pytest.approx(1.0)


def test_similarity_different():
    """Very different signatures should have low similarity."""
    sig_a = TaskSignature(size_relation=1.0, same_shape=True, color_count_change=0.0)
    sig_b = TaskSignature(size_relation=4.0, same_shape=False, color_count_change=-3.0)
    sim = signature_similarity(sig_a, sig_b)
    assert sim < 0.8  # Should be meaningfully less than 1


def test_similarity_range():
    """Similarity should always be between 0 and 1."""
    sig_a = TaskSignature(size_relation=0.5, color_count_change=3.0,
                          component_count_change=-2.0)
    sig_b = TaskSignature(size_relation=5.0, color_count_change=-1.0,
                          component_count_change=5.0)
    sim = signature_similarity(sig_a, sig_b)
    assert 0.0 <= sim <= 1.0


# ---------------------------------------------------------------------------
# Finding analogous tasks
# ---------------------------------------------------------------------------

def test_find_analogous_tasks_exact_match():
    """Exact same signature should be found."""
    target = TaskSignature(size_relation=1.0, color_count_change=0.0)
    solved = {
        "task_a": TaskSignature(size_relation=1.0, color_count_change=0.0),
        "task_b": TaskSignature(size_relation=4.0, color_count_change=-3.0, same_shape=False),
    }
    matches = find_analogous_tasks(target, solved, threshold=0.9)
    assert len(matches) >= 1
    assert matches[0][0] == "task_a"


def test_find_analogous_tasks_empty():
    """No solved tasks means no matches."""
    target = TaskSignature()
    matches = find_analogous_tasks(target, {}, threshold=0.5)
    assert matches == []


def test_find_analogous_tasks_threshold():
    """Threshold should filter out dissimilar tasks."""
    target = TaskSignature(size_relation=1.0)
    solved = {
        "close": TaskSignature(size_relation=1.1),
        "far": TaskSignature(size_relation=10.0, same_shape=False,
                             color_count_change=5.0),
    }
    # With a high threshold, only the close match should pass
    high = find_analogous_tasks(target, solved, threshold=0.95)
    # With a low threshold, both might pass
    low = find_analogous_tasks(target, solved, threshold=0.3)
    assert len(high) <= len(low)


# ---------------------------------------------------------------------------
# Solution transfer
# ---------------------------------------------------------------------------

def test_transfer_solution_color_remap():
    """Transfer a simple color remapping from one task to another."""
    # Source task: 1->3, 2->4
    src_train = [
        (np.array([[1, 1], [2, 2]]), np.array([[3, 3], [4, 4]])),
    ]
    src_preds = [np.array([[3, 3], [4, 4]])]

    # Target task: 5->7, 6->8 (same structure, different colors)
    tgt_train = [
        (np.array([[5, 5], [6, 6]]), np.array([[7, 7], [8, 8]])),
    ]
    tgt_test = [np.array([[5, 6], [6, 5]])]

    result = transfer_solution(src_train, src_preds, tgt_train, tgt_test)
    assert result is not None
    assert len(result) == 1
    expected = np.array([[7, 8], [8, 7]])
    assert np.array_equal(result[0], expected)


def test_transfer_solution_fails_incompatible():
    """Transfer should fail when tasks have incompatible transformations."""
    src_train = [
        (np.array([[1, 2]]), np.array([[1, 2, 1, 2]])),  # doubles width
    ]
    src_preds = [np.array([[1, 2, 1, 2]])]

    tgt_train = [
        (np.array([[3, 4]]), np.array([[3], [4]])),  # transposes
    ]
    tgt_test = [np.array([[5, 6]])]

    result = transfer_solution(src_train, src_preds, tgt_train, tgt_test)
    assert result is None


def test_transfer_solution_empty_inputs():
    """Transfer with empty inputs should return None."""
    result = transfer_solution([], [], [], [])
    assert result is None
