"""Tests for library learning module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.library_learning import (
    extract_subsequences,
    mine_fragments,
    anti_unify_programs,
    build_library,
    apply_library_compression,
    evaluate_library_transfer,
)


def test_extract_subsequences():
    subs = extract_subsequences(["a", "b", "c"], min_len=2, max_len=3)
    assert ("a", "b") in subs
    assert ("b", "c") in subs
    assert ("a", "b", "c") in subs
    assert len(subs) == 3


def test_mine_fragments_finds_repeated():
    solutions = {
        "t1": ["rotate_90", "reflect_horizontal"],
        "t2": ["rotate_90", "reflect_horizontal", "identity"],
        "t3": ["translate", "recolor"],
    }
    fragments = mine_fragments(solutions, min_frequency=2)
    names = [f.name for f in fragments]
    assert any("rotate_90_reflect_horizontal" in n for n in names)


def test_mine_fragments_no_singles():
    solutions = {"t1": ["a", "b"], "t2": ["c", "d"]}
    fragments = mine_fragments(solutions, min_frequency=2)
    assert len(fragments) == 0


def test_anti_unify():
    a = ["rotate_90", "reflect_horizontal", "recolor"]
    b = ["rotate_90", "translate", "recolor"]
    common = anti_unify_programs(a, b)
    assert "rotate_90" in common
    assert "recolor" in common
    assert "reflect_horizontal" not in common


def test_build_library():
    solutions = {
        "t1": ["a", "b", "c"],
        "t2": ["a", "b", "d"],
        "t3": ["a", "b", "e"],
    }
    lib = build_library(solutions, min_frequency=2)
    assert lib.size > 0
    assert lib.version == 1


def test_apply_library_compression():
    solutions = {
        "t1": ["a", "b", "c"],
        "t2": ["a", "b", "d"],
    }
    lib = build_library(solutions, min_frequency=2)
    compressed, gain = apply_library_compression(["a", "b", "c"], lib)
    assert len(compressed) <= 3


def test_evaluate_library_transfer():
    solutions = {
        "t1": ["a", "b"],
        "t2": ["a", "b"],
    }
    lib = build_library(solutions, min_frequency=2)
    held_out = {"t3": ["a", "b", "c"]}
    metrics = evaluate_library_transfer(lib, held_out)
    assert "mean_reuse_count" in metrics
    assert "fraction_with_reuse" in metrics
