# C2 CORA_ONLY arm: evaluator-side score (2026-10-13)

**Label: SYNTHETIC.** The C2 corpus: 12 families × 10 tasks, seeds
9000–9009, 1 test output per task.

- **Run:** the frozen native v23 harness through the native_v1 notebook,
  unchanged. It finished at rc 0 in 7,559 s on 4 workers.
- **Scorer:** `python -m cora_hybrid.score_c2`, giving
  `outputs/hybrid_c2/cora_only_score.json`.
- **Data:** the committed submission against `outputs/hybrid_c2/solutions.json`,
  which only the evaluator reads. Nothing was rerun or tuned.

Completion is not accuracy. The run completed 120 of 120 tasks.

| measure | count |
|---|---|
| exact under the two-attempt rule | **47 / 120** |
| tasks some layer claimed as solved | 100 |
| claimed and correct | 47 |
| **claimed and wrong** | **53** |
| unclaimed and correct | 0 |
| unclaimed | 20 |

## Where the wrong claims come from

The Kaggle path's answer order (`harness/run_harness.py`, emit_predictions):
- **attempt_1** is the render of the first claiming layer, in the order
  pipeline → geocat → object;
- **attempt_2** is the object layer's best uncertified partial.

| layers claiming (P pipeline, G geocat, O object) | tasks | attempt_1 correct | either attempt correct |
|---|---|---|---|
| P only | 38 | 1 | 9 (8 via attempt_2) |
| P + O | 22 | 14 | 14 |
| P + G | 23 | 10 | 15 |
| P + G + O | 17 | 9 | 9 |
| none | 20 | 0 | 0 |

**Pipeline sub-layer precision, for attempt_1 of every task the pipeline
claimed:**

| sub-layer | correct | wrong |
|---|---|---|
| loo_replace | 11 | 32 |
| adaptive_reasoner | 8 | 30 |
| adaptive_synthesizer | 8 | 3 |
| fill_solver | 6 | 0 |
| composable_reasoner | 1 | 1 |

**Families claimed 10 of 10 and correct 0 of 10:**
- d_layer_size;
- f_diag_mirror.

multicolor_majority was claimed 10 of 10 and was correct in 1.

## Reading

**Observation.**
- On this synthetic corpus the harness claims far more than it gets right:
  53 of 100 claimed tasks are wrong.
- The pipeline layer goes first in the answer order. Its claims come from
  train fit plus layer-specific checks, not from the object layer's adaptive
  leave-one-out by re-induction, and they drive most of the error.
- When only the pipeline claims a task, attempt_1 is right in 1 of 38.

**Not established here.**
- **The object layer's own precision.** Its certified render is not
  submitted when the pipeline claims first. The failure funnel measures it
  directly: `cora_funnel`, corpora c2dev and dev60.
- **Whether the same pattern holds on real ARC.** The funnel's whole-harness
  dev60 step (`cora_funnel/harness_run.py`) measures that on the 60
  authorized development tasks.

**This is not a Kaggle result.** It is a synthetic diagnostic of the frozen
native configuration.
