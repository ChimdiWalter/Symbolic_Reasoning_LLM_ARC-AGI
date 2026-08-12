"""DreamCoder-style library learning: mine repeated program fragments,
anti-unify solutions, and propose new macro-operators.

Uses only training-split solutions for library induction.
"""
from __future__ import annotations

import numpy as np
from typing import Optional, List, Dict, Tuple, Set
from dataclasses import dataclass, field
from collections import Counter


@dataclass
class ProgramFragment:
    """A reusable program fragment (macro-operator)."""
    name: str
    steps: List[str]
    frequency: int
    source_tasks: List[str]
    compression_gain: float = 0.0


@dataclass
class Library:
    """A library of learned macro-operators."""
    fragments: List[ProgramFragment]
    version: int = 0

    def lookup(self, name: str) -> Optional[ProgramFragment]:
        for f in self.fragments:
            if f.name == name:
                return f
        return None

    @property
    def size(self) -> int:
        return len(self.fragments)


def extract_subsequences(steps: List[str], min_len: int = 2, max_len: int = 4) -> List[Tuple[str, ...]]:
    """Extract all subsequences of the given lengths."""
    subs = []
    for length in range(min_len, min(max_len + 1, len(steps) + 1)):
        for i in range(len(steps) - length + 1):
            subs.append(tuple(steps[i:i + length]))
    return subs


def mine_fragments(
    solutions: Dict[str, List[str]],
    min_frequency: int = 2,
    min_len: int = 2,
    max_len: int = 4,
) -> List[ProgramFragment]:
    """Mine repeated program fragments from a set of solutions.

    Args:
        solutions: mapping from task_id to list of operator names
        min_frequency: minimum number of tasks sharing a fragment
        min_len: minimum fragment length
        max_len: maximum fragment length
    """
    fragment_counts: Counter = Counter()
    fragment_sources: Dict[Tuple[str, ...], List[str]] = {}

    for task_id, steps in solutions.items():
        seen_in_task: Set[Tuple[str, ...]] = set()
        for sub in extract_subsequences(steps, min_len, max_len):
            if sub not in seen_in_task:
                fragment_counts[sub] += 1
                fragment_sources.setdefault(sub, []).append(task_id)
                seen_in_task.add(sub)

    fragments = []
    for sub, count in fragment_counts.most_common():
        if count < min_frequency:
            break
        fragment = ProgramFragment(
            name=f"macro_{'_'.join(sub)}",
            steps=list(sub),
            frequency=count,
            source_tasks=fragment_sources[sub],
            compression_gain=len(sub) - 1,
        )
        fragments.append(fragment)

    return fragments


def anti_unify_programs(prog_a: List[str], prog_b: List[str]) -> List[str]:
    """Find the longest common subsequence of two programs (anti-unification)."""
    n, m = len(prog_a), len(prog_b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if prog_a[i - 1] == prog_b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    result = []
    i, j = n, m
    while i > 0 and j > 0:
        if prog_a[i - 1] == prog_b[j - 1]:
            result.append(prog_a[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] > dp[i][j - 1]:
            i -= 1
        else:
            j -= 1

    return list(reversed(result))


def build_library(
    solutions: Dict[str, List[str]],
    min_frequency: int = 2,
    max_fragments: int = 50,
) -> Library:
    """Build a library from solved task solutions."""
    fragments = mine_fragments(solutions, min_frequency=min_frequency)

    # Deduplicate: remove fragments that are strict subsequences of longer ones
    filtered = []
    for f in fragments:
        is_sub = False
        for g in fragments:
            if f is g:
                continue
            if len(f.steps) < len(g.steps) and g.frequency >= f.frequency:
                f_str = " ".join(f.steps)
                g_str = " ".join(g.steps)
                if f_str in g_str:
                    is_sub = True
                    break
        if not is_sub:
            filtered.append(f)

    filtered = filtered[:max_fragments]
    return Library(fragments=filtered, version=1)


def apply_library_compression(
    program: List[str],
    library: Library,
) -> Tuple[List[str], float]:
    """Compress a program using library macros. Returns (compressed, gain)."""
    result = list(program)
    total_gain = 0.0

    for fragment in library.fragments:
        frag_str = " ".join(fragment.steps)
        while True:
            result_str = " ".join(result)
            idx = result_str.find(frag_str)
            if idx < 0:
                break
            prefix_steps = result_str[:idx].strip().split() if idx > 0 else []
            suffix_steps = result_str[idx + len(frag_str):].strip().split()
            prefix_steps = [s for s in prefix_steps if s]
            suffix_steps = [s for s in suffix_steps if s]
            result = prefix_steps + [fragment.name] + suffix_steps
            total_gain += fragment.compression_gain

    return result, total_gain


def evaluate_library_transfer(
    library: Library,
    held_out_solutions: Dict[str, List[str]],
) -> Dict[str, float]:
    """Evaluate how well the library transfers to held-out tasks."""
    reuse_counts = []
    compression_gains = []

    for task_id, steps in held_out_solutions.items():
        compressed, gain = apply_library_compression(steps, library)
        reuse_count = sum(1 for s in compressed if s.startswith("macro_"))
        reuse_counts.append(reuse_count)
        compression_gains.append(gain)

    return {
        "mean_reuse_count": float(np.mean(reuse_counts)) if reuse_counts else 0.0,
        "mean_compression_gain": float(np.mean(compression_gains)) if compression_gains else 0.0,
        "fraction_with_reuse": float(np.mean([r > 0 for r in reuse_counts])) if reuse_counts else 0.0,
        "total_tasks": len(held_out_solutions),
    }
