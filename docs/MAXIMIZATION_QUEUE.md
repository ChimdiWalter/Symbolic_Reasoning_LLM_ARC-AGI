# Maximization queue — plan of record (2026-08-11, user: "queue all")

Everything measured-but-unmaximized, queued in execution order. Each
item: what, why (measured evidence), acceptance. Standing rules
(engine rules a-f, env-gating, records-at-every-milestone, LOO as sole
gate) apply to every item. Update STATUS stamps here as items seal.

## Q0 — seal v20 (BLOCKED on machine load)
Run when load < 4 (user's ns_pair evals finish):
  cd Reasoning_Project && source ~/.venvs/lesegenv/bin/activate
  export PYTHONPATH=. ARC_GENERATIVE=1 ARC_DIHEDRAL_FRAMES=45
  python3 scripts/run_unified_harness.py --workers 1 \
    --subset-file outputs/v20_repair2/subset.json \
    --out-dir outputs/v20_repair_final --run-id v20_final
Expect 3/3 recover -> SEAL 174/1000. Then verify 8e5c0c38 render vs
eval solutions (expect test-wrong), regen paper tables
(scripts/paper_tables.py), Kaggle tarball rebuild from v20 engine.

## Q1 — competition-budget measurement (pure measurement, no code)
We have NEVER measured score at Kaggle budget (~180s/task with
governor vs our 60-90s). Run the 1000-task chain with the budget
governor at competition settings on a quiet box. Budget-wall class
certifies free. Acceptance: the measured number; expect +5-10.

## Q2 — eval-split censuses with the new engine (cheap, first)
Run the fused-signature census + orphan battery ON THE EVAL SPLIT
(never done). Enumerate eval tasks with the generative signature;
probe them with ARC_GENERATIVE=1 at competition budget. Acceptance:
any certified eval solve = first honest eval point; else the census
tells us which eval classes remain.

## Q3 — ROUND 20: expression-depth on the LOO-death pool (BIGGEST)
~236 tasks train-perfect but fold-rejected (largest measured pool
since round 2; lattice says relational params certify at 0.92).
Census the 236's rejected programs: which parameter slots are
constant-bound that could be relational (functions of object context:
nearest-object features, ranks, counts, distances)? Widen the
expression grammar accordingly (relational-first, MDL-ranked).
Acceptance: conversion rate on the pool; 10% = +20 at scale.

## Q4 — composition done right (the multiplier, 2nd attempt)
Fix Stage 3's three named blockers: (a) seed bases from PERSISTED
near-solve partials (base_hints pattern from overlay-v2); (b)
dedicated budget slice (not last-resort leftovers); (c) erase-capable
patches (patch may claim base-painted cells as background). Then
rerun the 25-task probe. Acceptance: first certified depth-2 with
generative component, else stop again with new blocker.

## Q5 — generator language rung: relational per-pair parameters
Named independently by 05a7bcf2 trace AND E10 miss: direction/params
as expressions of pair context (perpendicular-to-wall etc.). Extend
hypothesis language + generative vocabulary together; rerun E10-style
mining after (does the miner use the new dimension?). Acceptance:
05a7bcf2 certifies; miner admits relational generators.

## Q6 — layout/reshape family (24 census tasks) + counting-driven
output sizing. Planned since round 4. Standard family recipe
(trace-first, env-gated, relational-first, gates).

## Q7 — attempt_2 calibration for Kaggle (free metric points)
Wire the strong-form LOO gate (mdl/loo_gate.py — perfect separation
n=8) into submission attempt_2: gated per-task-MDL renders (or gated
best-partials) above ungated partials. Measure attempt_2 precision
before/after on training. Acceptance: precision >> 3% baseline.

## Q8 — expert iteration (conditional on Q4 success)
The guide's harm verdict was at SHALLOW vocabulary (search not
order-bound). If composition lands, candidate space explodes and
ordering inverts to valuable. Re-run guide ON/OFF at that point;
dream corpus + GuideNet already exist.

## Q9 — learned segmentation (deepest, research-grade)
S1-S7 are hand-fixed; 4 true-gap census tasks + "none" labels point
at perception classes no variant produces. Mine segmentation
hypotheses from failed-task structure (the M2 pattern at the
perception level). Ladder rung below generators.

## STATUS
- Q0: BLOCKED on load (<4). All else queued behind Q0's seal.
- Q1-Q2: next after Q0 (cheap, measurement-only).
- Q3: the big round after Q1/Q2 numbers land.
- Q4-Q9: in order, each gated on its predecessor's records.
