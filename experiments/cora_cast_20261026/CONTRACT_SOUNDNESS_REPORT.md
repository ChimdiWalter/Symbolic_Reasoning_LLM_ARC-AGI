# M3 contract soundness report

**What is claimed.** Each operator's forward contract over-approximates its outputs, and each predecessor relation
over-approximates its inputs, on the declared finite scope (every grid with h, w <= 3 over {0, 1, 2}; every 4 x 4
grid over {0, 1}; random abstract inputs; structured random grids up to 20 x 20 on random backgrounds, with
operator-specific samplers for partial operators). This is finite-model validation plus property testing, NOT a
general proof for arbitrary grids. Pruning uses only these contracts (PROVED_OPERATOR_CONTRACT within that scope);
learned hints only reorder.

## 1. Contract checks (`cast/contract_check.py`; reports in `results/contract_checks/`)

Full level, every parameter of the operator's domain over the palette {0, 1, 2} (L0 operators and symmetry completion,
run 27 Oct in `runs/chain_v1`, code snapshot `runs/chain_v1/code`):

| operator | level | parameters checked | fwd concrete | bwd | fwd abstract | random fwd / bwd / abstract | violations | CPU s | verdict |
|---|---|---|---|---|---|---|---|---|---|
| concat | full | 8 | 694,664 | 694,664 | 17,400 | 223 / 223 / 1706 | 0 | 125.31 | PASS |
| crop | full | 9 | 612,456 | 612,456 | 15,196 | 160 / 160 / 1040 | 0 | 99.51 | PASS |
| down | full | 4 | 24 | 24 | 2 | 40 / 40 / 8 (after samplers) | 0 | 5.61 | PASS |
| fill_enclosed | full | 3 | 11,307 | 11,307 | 987 | 44 / 44 / 342 | 0 | 14.88 | PASS |
| geo | full | 7 | 607,831 | 607,831 | 15,225 | 300 / 300 / 2325 | 0 | 77.0 | PASS |
| gravity | full | 4 | 347,332 | 347,332 | 8,700 | 300 / 300 / 2325 | 0 | 42.09 | PASS |
| outline | full | 6 | 520,824 | 520,824 | 13,038 | 293 / 293 / 2288 | 0 | 81.82 | PASS |
| recolor | full | 6 | 520,998 | 520,998 | 13,050 | 300 / 300 / 2325 | 0 | 69.05 | PASS |
| scale | full | 4 | 347,332 | 347,332 | 8,700 | 69 / 69 / 480 | 0 | 77.88 | PASS |
| symcomplete | full | 6 | 337,900 | 337,900 | 7,398 | 61 / 61 / 66 | 0 | 255.72 | PASS |
| tile | full | 15 | 1,302,495 | 1,302,495 | 32,625 | 112 / 112 / 813 | 0 | 208.75 | PASS |

M1, M2-frame and M6 operators, quick level (every grid up to 2 x 3 and 3 x 2 over {0, 1, 2}; a seeded sample of
at most 40 parameters; run in `runs/chain_v4b`). Random-case coverage is thin for the binding operators because
random grids rarely contain legends; the generated M1 cohorts (all executions checked against their
demonstrations) are the larger behavioural test:

| operator | level | parameters checked | fwd concrete | bwd | fwd abstract | random fwd / bwd / abstract | violations | CPU s | verdict |
|---|---|---|---|---|---|---|---|---|---|
| bind_pairs | quick | 4 of 4 | 1,312 | 1,312 | 76 | 4 / 4 / 16 | 0 | 0.67 | PASS |
| bind_glyphs | quick | 40 of 240 | 18,720 | 18,720 | 1,367 | 7 / 7 / 2 | 0 | 4.19 | PASS |
| crop_entity | quick | 40 of 54 | 19,850 | 19,850 | 1,285 | 30 / 30 / 113 | 0 | 30.49 | PASS |
| local_grow | quick | 40 of 1680 | 32,411 | 32,411 | 2,124 | 10 / 10 / 74 | 0 | 5.77 | PASS |

The checker itself is tested against a deliberately unsound contract (a recolour that claims an unchanged palette):
it returns FAIL with forward violations (`tests/test_contracts_property.py::test_checker_catches_an_unsound_contract`).

## 2. Partial-program over-approximation and the lost-correct audit

- `tests/test_lost_correct.py::test_hole_over_approximates_every_length2_program`: for 25 random grids, EVERY
  program of length <= 2 over the grammar instance (L0 + symmetry completion) has its output inside
  gamma(hole(alpha(z), 2)).
- `test_pruning_loses_no_fitting_program` (12 generated fixtures, observational equivalence off): the sets of fitting
  programs under typed, fwd and fwdbwd pruning equal the exact-execution set; pruned modes never execute more.
- Real tasks, M4: on all 816 source and evaluation tasks the contract-first decision of symmetry completion found
  exactly the fits of exact execution (lost 0) with 260 instead of 9,260 executions (CAST_train 166 vs 5,671;
  CAST_select 36 vs 964; CAST_holdout 22 vs 925; ARC_eval_dev 36 vs 1,700).
- Real and generated tasks, M1: bind_fixed (contract-first) and bind_exact (no contract) have identical fit counts
  and identical attempts on all 416 tasks of the five M1 cohorts, with 8 to 13 times fewer executions (M1 report).
- M3 screen (L0 + symmetry completion, depth 2): M3 screen (`runs/chain_v4b/m3`; L0 + symmetry completion, depth 2, 20,000 executions per task): lost behaviours
  versus exact execution on every completed run = 0 for the typed, fwd, fwdbwd and hint arms on all three cohorts.
  gen_l0 (60 generated programs): exact fits 40 tasks (18 stop at the budget) and answers 29/60 queries; fwd and
  fwdbwd fit 47 (none stops) and answer 37/60 with 31,581 instead of 1,146,377 executions; typed 37/60 with 476,659;
  hint ordering 32/60; at an equal 5 CPU-s per task at depth 3, exact 28/60 and fwdbwd 30/60. CAST_select: 5/92 in
  every depth-2 arm, 44,485 instead of 1,269,443 executions, 116 instead of 181 CPU-s, budget stops 32 -> 0.
  CAST_holdout: 0/90 in every arm (1 fitting-but-wrong first attempt), 40,947 instead of 1,258,828 executions.
  The backward check never pruned beyond the forward check in this grammar.

## 3. Status values and other stress tests (directive section 16)

Covered by tests: separate FIT / NO_FIT_EXHAUSTED / BUDGET_EXHAUSTED statuses (a budget stop is never reported as
unrealizable; failure records refuse that combination); two programs that fit but disagree on a query stay separate
behaviours; rectangular rotations and inverse transport keep frame bookkeeping (`tests/test_topology.py`); a true
rule that changes the hole count is admitted by its contract; foreground/background and diagonal contacts agree
between masks and the closed-square complex (Euler characteristic, 400 random masks); synchronous and asynchronous
schedules are different hypotheses (`tests/test_dynamics.py`); overlapping SYNC writes are undefined unless a
precedence policy is chosen (`tests/test_rewrite.py`); evaluator isolation (`tests/test_boundaries.py`: no solver
module imports a scorer; answer files refused to the solver; an audit hook records every file the M4 stage opens on
three evaluation tasks, no answer file is among them, and decisions are identical with the answer paths removed).

Final suite (`runs/chain_v5`, JUnit `results/test_logs/final_junit.xml`): 87 passed, 1 failed. The failure was the
boundary test's list of evaluation-side modules, which lacked the new `crosscheck.py` (an evaluation-side module that
imports the scorer by design); the list was corrected and the boundary file re-run: 12 passed
(`results/test_logs/boundaries_rerun_junit.xml`). No solver module imports a scorer. The four partial operators were
re-checked at the full level with input samplers: all PASS, random cases down 0 -> 40, scale 69 -> 176,
fill_enclosed 44 -> 168, symcomplete 61 -> 49 (different seeded sample).

## 4. Defects found and fixed during the work (all before the affected result)

1. The first symmetry fixture drew all ten colours, so no free mask colour existed and the test skipped most trials;
   fixed to palette 0-6 with mask colour 9 (operator unchanged). Solve rates after the fix: mirror 27/40 (13 partial:
   masks across the axis), 180-degree 39/40, D4 36/40.
2. A hole-count test used a 3 x 3 ring whose majority colour is the ring itself; replaced by a majority-background grid.
3. The boundary test listed the generated-task scorers as solver modules; evaluation-side modules are now listed.
4. Random-case coverage was thin for partial operators (Downscale 0, symmetry completion 61 random cases); input
   samplers were added and those four reports are re-run in `runs/chain_v5` (previous reports kept in
   `results/contract_checks_v1/`).
5. Contract checks of cheap operators cost about as much CPU as executing them: on M1 bindings the contract-first
   route used 8 times fewer executions but more CPU (M1 report). Pruning pays off in CPU only for expensive
   operators (symmetry completion: 13.8 to 0.94 CPU-s on CAST_train).

## 5. Scope and limitations

Finite-scope validation; abstract inputs in the checker use at most two colours per cell; subtree checks use a cached
shape-and-palette summary of the state (sound, coarser than the per-cell leaf checks); the backward relations of
crop-like operators are weak (shape lower bound, must-palette, count lower bounds). Topology is never used for
pruning.
