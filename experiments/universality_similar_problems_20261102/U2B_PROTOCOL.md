# Protocol U2b: controls for U2 (PRE-REGISTERED before any new arm is run or scored)

Written and committed on 2 Nov 2026, before any new arm was run and before the FIT_ONLY answers were scored. Its sha256
is in `U2B_FREEZE.json`.

U2's protocol (`PROTOCOL.md`, `b7caae6f…`) and U2's frozen results (`results/`, 1a20b6ee) are not changed. Deviations
go in a dated section of the result record.

## 1. Question

U2 lacked a native or matched-search control, and its intervals were unclustered. U2b asks, on the same problems:
- What does CORA's leave-one-out acceptance add over accepting the top program that fits every demonstration?
- What do CAST's search and modules add over blind enumeration in CAST's own grammar, at matched CPU?
- Do U2's precision claims survive uncertainty clustered by task type and by concept?

## 2. Tasks

- The same 924 tasks as U2: 1D-ARC 615 (14 types), Mini-ARC 149, ConceptARC 160 (16 concepts).
- The same exclusions, and the same REAL and SHUFFLED challenge files. Their sha256 are in U2's `DATA_MANIFEST.json`
  (`prepared_sha256`).
- Solutions are read only by the scorer.

## 3. Arms

**Frozen from U2: rescored, never rerun.**
- **O+ v2** (system a);
- **H-CAST:** `cast_selective_v2` under rule B3 (system b);
- **O** (system c);
- the **copy baseline**.

**(A) FIT_ONLY, and the acceptance ladder.**
- These answers are read from the evidence that U2's frozen system-b runs already saved: `side/<task>.json`, written
  by the byte-identical `cast_selective_v2` package through `sfb.cast_side`. No CORA run is needed, and none is made.
- Nobody has scored these fields yet.
- **FIT_ONLY** is the per-query `candidate`: the first module, in the order M4, M2, L0, whose top-ranked group of
  programs reproduces every demonstration and gives a complete, valid prediction. No leave-one-out is applied.
- **The ladder,** from the same evidence: FIT_ONLY, then **B1** (the held-out output among the top two re-derived
  answers; cast_v1's rule), then **B2** (genuine top-1 leave-one-out), then **B3**:
  - B3 adds three checks: no disagreement among fitting programs, fold agreement, and stability under a restart.
  - B3 is the frozen H-CAST arm.

**(B) MATCHED_SEARCH.**
- **What it searches:** blind enumeration in CAST's own typed grammar, `ops.L0` from the frozen `cast_selective_v2`
  package, which is imported unchanged.
- **How:** `search.Searcher` in mode `"exact"` (no contract pruning), with observational equivalence off.
- **Order:** iterative deepening, depth 1, then 2, then 3.
- **Answer:** the predictions of the first program, in enumeration order, that reproduces every demonstration and
  gives a valid grid for every test input.
- **Budget per task:** system b's measured child CPU on the same task and variant in U2, as recorded by `sfb.cast_side`.
  It is enforced by `Searcher`'s CPU budget, with a process-level backstop at budget plus 10 s.
- **Isolation:** one freshly forked child per task.
- No leave-one-out.

**(C) MATCHED_SEARCH_LOO.**
- B's answer is accepted only if genuine top-1 leave-one-out passes, with at least two demonstrations required.
- For each demonstration held out in turn, the same blind search runs on the remaining demonstrations, with the same
  per-task budget per fold. Its first fitting program must predict that demonstration's output exactly.
- The folds' CPU is extra and is reported. It is not matched.

**Common rules:**
- Every new arm runs on REAL and on SHUFFLED.
- **Answer accounting** (as in U2): an answer equal to the copy of the test input is not counted. These are non-copy
  answers.
- **pass@2:** attempt 1 is the arm's answer, else the copy; attempt 2 is the copy. This matches systems b and c.

## 4. Metrics

Per benchmark, arm and variant:
- test outputs;
- answered;
- coverage (answered / outputs);
- correct;
- precision (correct / answered);
- CORA accuracy (correct / outputs);
- pass@2.

## 5. Uncertainty

**Clusters:**
- 1D-ARC: its 14 task types.
- ConceptARC: its 16 concepts.
- Mini-ARC: no groups, so it is resampled by task. This is unclustered, and is stated as such.

**Bootstrap:**
- Pooled quantities resample clusters within each benchmark (stratified).
- 10,000 resamples, `numpy.random.default_rng(0)`, with 95% percentile intervals.
- Ratios are recomputed in each replicate as sum(correct) / sum(answered). Replicates with no answers are excluded, and
  their number is reported.

## 6. Contrasts

**PRIMARY (pre-declared, not adjusted).**
- The contrast: precision of H-CAST under rule B3, minus precision of FIT_ONLY, on REAL, pooled over the three
  benchmarks.
- **LOO_RAISES_PRECISION** if its 95% lower bound is above 0; otherwise **NOT_SHOWN**.
- The one-sided bootstrap p is reported: (1 + #{difference ≤ 0}) / 10,001.

**SECONDARY.** Holm correction over this family of ten at α = 0.05. The two-sided p is twice the smaller one-sided
bootstrap p, capped at 1. Unless a benchmark is named, each contrast is on REAL and pooled.

| id | contrast | benchmark |
|---|---|---|
| S1 | precision(B1) − precision(FIT_ONLY) | pooled |
| S2 | precision(B3) − precision(FIT_ONLY) | ConceptARC |
| S3 | precision(B3) − precision(FIT_ONLY) | Mini-ARC |
| S4 | precision(B3) − precision(FIT_ONLY) | 1D-ARC |
| S5 | coverage(B3) − coverage(FIT_ONLY) | pooled |
| S6 | precision(MATCHED_SEARCH_LOO) − precision(MATCHED_SEARCH) | pooled |
| S7 | CORA accuracy(FIT_ONLY) − CORA accuracy(MATCHED_SEARCH), paired per output | pooled |
| S8 | precision(B3) − precision(MATCHED_SEARCH_LOO) | pooled |
| S9 | CORA accuracy(O+ v2) − CORA accuracy(MATCHED_SEARCH), paired | pooled |
| S10 | CORA accuracy(H-CAST, B3) − CORA accuracy(MATCHED_SEARCH), paired | pooled |

**Descriptive:**
- paired differences of each new arm against the frozen O+ v2 and H-CAST results, in CORA accuracy and pass@2, with
  clustered intervals;
- each new arm's SHUFFLED coverage and precision, set against its REAL values.

## 7. Context only (not an arm)

The ConceptARC paper (Moskvichev, Odouard and Mitchell 2023, Table 1; as recorded in `paper/REFERENCE_CHECK.md`)
reports the first-place ARC-Kaggle program at a mean accuracy of 0.5125 over the same 480 test inputs. That program
had three guesses per input; our systems have two attempts. The figure is cited as context only, never as a run arm.

## 8. Compute, hold and order

- **CPU:** only through `scripts/with_cpu_slot.sh`, nice 19, one slot. No GPU. Nothing is added to Step B.
- **Order:**
  - MATCHED_SEARCH and its leave-one-out folds run together in one pass per benchmark and variant: REAL first
    (ConceptARC, Mini-ARC, 1D-ARC), then SHUFFLED.
  - FIT_ONLY and the ladder are read in the analysis step.
- **Budget:** soft cap 6 CPU-h; no new pass starts beyond it. MATCHED_SEARCH uses about 0.45 CPU-h by construction;
  the folds use at most a few CPU-h.
- **Hold, for the blind review:** the run waits until the flag `GO_U2B` exists in its run folder, or until
  2026-11-02T18:00:00Z passes without a `HOLD_U2B` flag.

## 9. Reporting

- Results go to `results/U2B_RESULTS.json` and `results/U2B_SUMMARY.md`.
- The record is `records/NOV2_U2B_CONTROLS_RESULT.md`, with a "Claim for the paper" section written honestly
  whichever way the result falls.
- **The implementation** (`scripts/u2b_blind.py`, `scripts/u2b_analysis.py`, `scripts/u2b_chain.sh`,
  `tests/test_u2b.py`) is frozen by hash before the run.

## 10. What U2b can and cannot show

**It can show:**
- whether leave-one-out raises precision over fit-only acceptance, on the same candidates;
- whether CAST's modules and pruned search beat blind enumeration in the same grammar at the same per-task CPU;
- whether verification helps blind search.

**It cannot show:**
- learned transfer or universal reasoning;
- anything about the hidden ARC-AGI-2 test.

It also gives no native solver other than blind enumeration in CAST's own grammar. A stronger external DSL solver is
not tested.
