# Failure-frontier audit: prospective selection rule

Written and committed BEFORE any TFG result was computed or inspected.

## Rule

Task set = the FIRST 12 task ids, in ascending lexicographic order, of the
keys of `data/arc/dev60_challenges.json`.

Baseline-failure filter: the frozen v23 baseline records 0/120 solved on the
protected evaluation set, of which these 60 dev tasks are half. Every dev
task is therefore a recorded baseline failure, so the filter admits all 60
and the ordering rule alone selects the 12. No task was chosen because it
looked promising; no TFG output was read before this file was written.

## What is measured

Only the existing failure path, unmodified:

    ordinary search -> TraceObserver -> tfg_extractor.extract -> ConcreteTFG

## What is NOT done

No scoring. No test outputs are read (the challenge file contains none).
No proposal, no install, no K modification, no GPN training, no ablation.
No HOLDOUT, no E_transfer, no Lockbox, no Step-B output.

## Fixed parameters

Search budget per task: 8.0 s (the runtime default, ARC_META_BUDGET_S).
Goal type: Grid. max_frontier_terms: 12 (module default).
Env: the blind-runtime BASE_ENV, unmodified.

## Classification thresholds, fixed in advance

INFORMATIVE       >= 8 of 12 tasks each have >= 2 frontier_term nodes AND
                  a non-empty candidate-associated value/mismatch signature.
PARTIAL           frontier_term nodes present on most tasks but a whole
                  evidence class is systematically absent.
EMPTY_OR_UNUSABLE most tasks carry no candidate-associated frontier evidence.
