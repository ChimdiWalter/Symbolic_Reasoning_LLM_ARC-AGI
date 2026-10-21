# ncv2-g2 real-ARC engineering check: FINAL, NO_REAL_GAIN (20 October 2026)

**The frozen decision** (protocol `records/NEURAL_CORA_V2G2_REALARC_PROTOCOL_20261020.md`, frozen at `8bb377d`;
computed by the frozen `score` stage, thresholds unchanged): **NO_REAL_GAIN**. GO_REAL_COVERAGE needed ncv2-g2 −
ncv2-g1 ≥ 3 on both pass@2 and correct-candidate coverage, with at most 1 loss. The gain was +1 on both, with 0
losses.

**What these tasks are:** 40 public ARC-AGI-2 training tasks (plus 4 reported descriptively). The sealed v23 baseline
saw them, and they are in NVARC's training mix. This is development evidence, not unseen generalization.

## 1. The run

| item | value |
|---|---|
| authorization | the author's message "authorize the real-ARC check" (20 October), one run |
| stages | `solve --authorized`, `native --authorized`, `score`, then the pre-registered analysis; one detached driver |
| time | STARTED 21:48:05Z, EXIT 0 at 23:53:52Z |
| lock | manifest sha256 `4160580d…`, verified at both stages (solve at HEAD `9a62ae2`, native at `fc5c448`; neither commit touched frozen code) |
| resources | CPU only, 2 workers at nice 10; Step B untouched |
| CPU, primary 40 | ncv2-g1 308.7 s, ncv2-g2 1,319.7 s (median per task: 3.7 s and 22.3 s); native 12,877 CPU-s over all 44 |
| ncv2 integrity | 0 errors; CPU-cap truncations (120 s): ncv2-g2 4 tasks (`890034e9`, `a096bf4d`, `50a16a69`, `f9d67f8b`), ncv2-g1 1 (`f9d67f8b`) |
| native integrity | **flagged:** 12 of 44 native rows record `error: object_hard_timeout`, the harness's own 450 CPU-s hard cap. They are budget truncations by design, not crashes, and native is a reference arm outside the decision rule. But the protocol's stop rule ("more than 5 tasks raise errors in a stage") is worded on errors, so this is reported for the author's judgement rather than reinterpreted. Native's numbers below are lower bounds under that cap |

## 2. Results, primary 40 (first test output)

| | ncv2-g1 | ncv2-g2 | native v23 (reference) |
|---|---|---|---|
| demonstration-fitting programs (tasks) | 1 | 4 | 10 |
| correct-candidate coverage | 1 | 2 | 4 |
| pass@2 | 1 | 2 | 4 certified correct (all outputs) |
| wrong attempts (fitting but wrong) | 0 | 2 | — |

- **Newly correct:** 1 (`45737921`). **Lost:** 0. One-sided sign test, ncv2-g2 vs ncv2-g1: p = 0.5.
- **Against native (first output):** ncv2-g2 only, `d2abd087`; native only, `63613498`, `74dd1130`, `b2bc3ffd`.
- **First-fit positions (ncv2-g2):** `7f4411dc` 7, `d23f8c26` 12, `d2abd087` 13, `45737921` 230.
- **Wrong demonstration-fitting hypotheses:** `7f4411dc` and `d23f8c26`, each a single fitting reading.
- **Program families behind correct answers:** both are object programs. No class form contributed.
- **Multiple test inputs:** `bda2d7a6`, `b74ca5d1`, `d6542281`; no arm solved any of them.
- **LEFTOVER 4 (descriptive):** ncv2-g1 and ncv2-g2 fit none; native fits 3 and certifies none correctly.

## 3. The five sources, kept apart

| source | evidence |
|---|---|
| semantic expressivity | native certified 4 tasks; all 4 certificates decompile into ncv2-g2 (no language gap among them). 36 tasks have no certificate, so their expressivity is unknown |
| candidate generation | 1 of the 4 certified programs is structurally in ncv2-g2's candidate set (`74dd1130`). For `45737921`, ncv2-g2 found an execution-equivalent object program of its own |
| budgeted search reach | 4 tasks fit within 3,000 candidates; `74dd1130`'s certified program was not reached, and a structural search of ncv2-g2's order did not find it within 40,000 (post hoc) |
| candidate selection | 0 selection misses (no correct candidate left out of the attempts); 2 tasks whose only fitting reading was wrong |
| independent correctness | 2 of 40 by pass@2, on exposed public training tasks |

## 4. Failure taxonomy (Phase 2; descriptive, after the decision)

`scripts/neural_cora_v2g3_realarc_failure_taxonomy.py` → `failure_taxonomy.json`. One primary cause per task:
- the first five classes use the pre-registered analysis and the solver traces;
- tasks with no certificate and no fit are classed by a solver-side change profile of the demonstrations (scene.py,
  the best view): the shares of changed cells that are explained by object fates (recoloured, deleted, or a move's
  source and destination), are new cells, or lie on objects whose fate matches nothing.

| cause | primary 40 | leftover 4 |
|---|---|---|
| solved | 2 | 0 |
| fit_wrong (one fitting reading, wrong) | 2 | 0 |
| C, generator gap (certified, not generated) | 2 | 0 |
| D, beyond budget (certified, generated, not reached) | 1 | 0 |
| objects explain at least half of the change, yet no rule was found | 12 | 0 |
| A, additive (mostly new cells: lines, fills, copies, growth) | 7 | 2 |
| A, object mismatch (the objects change in ways no fate describes) | 13 | 2 |
| A, mixed | 1 | 0 |

Median change profile (primary): 0.40 explained by object fates, 0.10 on objects whose fate matches nothing. No task
changes its grid shape (the cohort's scope excludes them).

## 5. What this means

The directive's reading table: few fitting programs despite expanded generation means representations, missing
transformations and search constraints come first. That is the case here: 4 of 40 fit.
- **Representation and missing transformations: 21 of 40.** These are object mismatch (13), additive change (7) and
  mixed (1). Neither ncv2-g2 nor ncv2-g3 has a mechanism for them yet.
- **Generation and search on object-explainable change: 15 of 40.** These are the 12 unsolved object-explained tasks,
  plus the 2 generator gaps and the 1 task beyond budget. This is what ncv2-g3's joint, execution-guided construction
  targets. It is untested on real tasks.
- **Selection: 2 of 40,** each with a single wrong fitting reading. That is overfitting with no correct rival
  candidate, so a better selector alone cannot fix it.
- Training a learned selector cannot help the 38 tasks with no correct candidate in the set.

## 6. What a future experiment must measure to validate a fix

- **For construction (ncv2-g3):** a fresh, eligible real cohort (for example the next tasks in the published order,
  with the same eligibility check), frozen in advance. Measure, against ncv2-g2 unchanged at equal candidate and CPU
  budgets: fits, correct coverage, pass@2, gains and losses. This 40-task cohort is now exposed and cannot serve.
- **For representation:** a new object or relational representation is needed first. Its test must report coverage
  on tasks whose change profile is mostly unexplained, separately from object-explained tasks.
- **For selection:** count wrong attempts and selection misses at fixed coverage, so that a selection change cannot
  hide a coverage loss.

## 7. Locked outputs (outputs/neural_cora_v2g2/realarc/, local only)

| file | sha256 (first 16) |
|---|---|
| rows_g.jsonl | `a7ae97ed588eb21b` |
| rows_native.jsonl | `166e2de69a3d3a47` |
| score.json | `4c79ec016fe3de5a` |
| analysis.json | `8f9683bf31048034` |
| failure_taxonomy.json | `414b498514413d09` |
| run_manifest_solve.json | `064af7e302d6483e` |
| run_manifest_native.json | `c67797a1144a0b3a` |

## 8. Clarifications (21 October 2026; the frozen result is unchanged)

- **Coverage semantics:** "correct-candidate coverage" means a correct prediction among the fitting programs each
  search kept within its 3,000-candidate budget (at most 50 distinct predictions; no task came near that cap). It is
  not coverage of everything the generator can produce. "38 of 40 tasks have no correct candidate" means no correct
  prediction among those kept fits, not that the language or the generator cannot express one. Structural
  generator coverage is the separate "candidate generation" row of section 3.
- **The reference-arm timeouts** stay as reported in section 1: NO_REAL_GAIN is the decision for the error-free
  ncv2-g1 vs ncv2-g2 comparison. Native's 12 `object_hard_timeout` rows are budget truncations, and native was not
  exhaustively evaluated. Whether they count as "errors" under the stop rule is left to the author, and the protocol
  is not reinterpreted.
- **Follow-up analysis:** `records/NEURAL_CORA_G4_REALARC_FAILURE_ANALYSIS_20261021.md` (descriptive; this cohort is
  now exposed and is not a new evaluation).
