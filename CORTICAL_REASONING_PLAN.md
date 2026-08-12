# Cortical Reasoning Model — Implementation Plan

**Date:** 2026-06-28
**Goal:** Close the 95→293 gap in submission mode (no test outputs visible)
**Design philosophy:** Representation-first. Understand the grid before solving it.
**Adaptability:** All mechanisms are task-agnostic — they reason over abstract representations, not ARC-specific heuristics.

## Current State

| Mode | Solved | Iter 1 | Iter 2 | Session Memory |
|------|--------|--------|--------|----------------|
| Oracle | 293/1000 | 122 | 171 | 111 |
| Submission | 95/1000 | 95 | 0 | 0 (BUG) |

## Root Causes

1. **Session memory bug** — submission mode iter1 path never calls `record_success()` (line 1067-1073)
2. **All 8 correction strategies are pixel-level** — they memorize exact color maps from training residuals that don't generalize
3. **No multi-candidate consensus** — only the best partial candidate is tried, all others are discarded
4. **Binary accept/reject** — no confidence gradient; programs failing 1/3 training pairs are fully rejected
5. **No deep representation** — system jumps to solvers without understanding grid structure

## Architecture: 6 Cognitive Mechanisms

### Layer 1: Hierarchical Perception (V1→V4 cortical hierarchy)
**Neuroscience:** Visual cortex processes information in layers — V1 detects edges, V2 textures, V4 shapes, IT objects.
**Implementation:** `CorticalPerception` class extracts multi-level grid representation:
- L1 (pixels): color histogram, grid dimensions, background color
- L2 (objects): connected components, bounding boxes, colors, sizes
- L3 (relations): containment, adjacency, alignment, spacing patterns
- L4 (abstractions): symmetries, repetition, gradients, object groups by property

**Why it matters for generalization:** The same perception module works for ANY grid-based reasoning task, not just ARC. It provides the substrate that all other mechanisms operate on.

### Layer 2: Structural Hypothesis Correction (Predictive Coding — Friston)
**Neuroscience:** The cortex generates top-down predictions from abstract hypotheses. Prediction errors update the hypothesis, not the pixel map.
**Implementation:** When a base program gets close but not exact:
- Instead of learning pixel maps from residuals, try LOW-PARAMETER structural hypotheses:
  - Geometric: rotate, reflect, transpose (1 parameter)
  - Color permutation: deterministic recolor map (≤10 parameters)
  - Geometric + color combined (≤11 parameters)
- Each hypothesis is LOO-validated: learn from N-1 training pairs, verify on held-out
- The hypothesis lives at the ABSTRACTION level, not pixel level → inherently generalizable

**Expected recovery:** 20-40 tasks where the error is a simple structural transform

### Layer 3: Multi-Column Voting (Thousand Brains — Hawkins)
**Neuroscience:** Each cortical column independently models the same object. Columns vote. No single column needs to be perfect.
**Implementation:**
- After iter1, collect ALL partial candidates (not just top 10)
- Group candidates by predicted output shape
- Pixel-wise majority vote within each shape group
- Weight votes by training partial score
- Verify voted output against ALL training pairs
- LOO validate: hold out each training pair, vote on remaining candidates that pass the other pairs

**Expected recovery:** 30-60 tasks where multiple solvers each get different parts right

### Layer 4: Metacognitive Confidence (Flavell, Fleming)
**Neuroscience:** Prefrontal cortex maintains calibrated confidence estimates. "I'm almost certain" vs "I'm guessing."
**Implementation:**
- For candidates that pass N-1 of N training pairs:
  - Compute pixel accuracy on the failing pair
  - If >95% match AND the mismatch is in ≤5 pixels: accept with high confidence
  - LOO validate: hold out each PASSING pair, verify program still generalizes
  - Score: `confidence = (pairs_passed / total_pairs) * pixel_accuracy_on_worst`
- Accept highest-confidence candidate if above threshold

**Expected recovery:** 10-20 tasks (targets the 27 iter1 oracle-only tasks)

### Layer 5: Feature Binding (Cortical Oscillations — Engel, Singer)
**Neuroscience:** Gamma oscillations synchronize neurons representing features of the same object — binding color, shape, and location.
**Implementation:**
- For each task with 2+ high-partial candidates:
  - Identify which DIMENSIONS each candidate handles correctly on training:
    - Shape/geometry accuracy (output shape, object positions)
    - Color accuracy (correct colors, wrong positions vs correct positions, wrong colors)
  - If candidate A has high geometry accuracy and B has high color accuracy:
    - Use A's geometry (object positions, shapes) + B's colors
    - Verify the bound result on training
- This is MORE TARGETED than voting — it combines specific strengths rather than averaging

**Expected recovery:** 10-20 tasks

### Layer 6: Structural Session Memory (Analogical Reasoning — Gentner, Hofstadter)
**Neuroscience:** Analogical retrieval uses structural alignment, not surface similarity.
**Implementation:**
- Fix the `record_success` bug first
- Index solved tasks by STRUCTURAL SIGNATURE:
  - `(shape_change_type, n_objects_in, n_objects_out, color_change_type, symmetry_type)`
- When a new task arrives:
  - Compute its structural signature
  - Retrieve strategies from structurally similar solved tasks
  - Try those strategies first (layer reordering already exists, just needs better features)
- The structural signature is task-domain-agnostic — works for any grid/object reasoning

**Expected recovery:** 10-30 tasks

## Implementation Order

1. **Session memory bug fix** (5 min) — immediate impact, unblocks Layer 6
2. **Hierarchical Perception module** (new file: `cortical_perception.py`)
3. **Multi-column voting** (highest expected impact)
4. **Structural hypothesis corrections**
5. **Metacognitive confidence**
6. **Feature binding**
7. **Structural session memory enhancement**
8. **Integration + evaluation**

## Adaptability Beyond ARC

All mechanisms are designed to be task-agnostic:
- **Perception:** Works on any 2D grid/image — could extend to 3D, graphs, sequences
- **Voting:** Works with any set of candidate solutions — not specific to grid transforms
- **Hypothesis correction:** Works for any compositional program where outputs can be compared
- **Confidence:** Works for any train/test verification setting
- **Feature binding:** Works whenever solutions have decomposable quality dimensions
- **Session memory:** Works whenever tasks share structural properties

The system should be usable for:
- Other program synthesis benchmarks (LARC, 1D-ARC, ConceptARC)
- Visual reasoning tasks (Raven's Progressive Matrices, CLEVR)
- Any hidden-test evaluation setting where train→test generalization matters
