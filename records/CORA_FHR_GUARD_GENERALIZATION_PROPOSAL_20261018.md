# PROPOSED (not frozen, not run): an independently selected generalization test of guarded construction

**Status: PROPOSAL ONLY.** It needs a frozen protocol, a confirmed permitted pool and the user's go-ahead
before any run. No protected split is used (E_transfer, HOLDOUT, ARC-1000, the frozen 120 pilot and the
sealed C4 final are excluded).

**Why.** The only real-task guarded solve (ka95aa62f67d9) was selected by the failure autopsy, and the
failure-blind arm tied it. The open questions are whether guarded construction solves tasks it was not
selected on, and whether the rule reflects a relationship rather than particular colour labels.

## 1. Independent case selection (a fixed rule, decided before any outcome)

**Pool:**
- every stand-in task from the CORA_FHR_V1 rehearsal (ARC-AGI-2 training, already exposed) that FHR
  treated as eligible: growth-shaped and native-uncertified, 62 tasks;
- **minus** the 13 tasks shared with dev60, which leaves at most 49;
- the pool is fixed by task ID from `outputs/kaggle_deploy/cora_fhr_v1/run_v1/fhr_rows.jsonl` before
  anything is run.

**Unit:** the task. The scoring is paired and exact-match.

## 2. Arms (same grammar plus guard, same checker, compute charged)

| arm | role |
|---|---|
| A | frozen native |
| B | matched search |
| EG | authentic + guard |
| C2G | strong failure-blind: all correspondences, same features |
| DG | shuffled donor |
| EG-contrast (new, declared now) | authentic failure objects plus the **native-explained** objects as negative examples, so the guard is learned from the explained/memorized contrast. This tests whether failure information can supply the *applicability* boundary that the blind arm learns from pooled data |

## 3. Colour-permutation test (both directions)

- **Construction.** For each case, take a fixed random permutation σ of colours 1–9 (seed = hash of the task
  ID), apply it consistently to every grid, and rerun EG and C2G.
- **Measures:**
  - whether the re-derived rule is the σ-image of the original (for example `colours == (σ(1),)`);
  - whether correctness is preserved.
- **Reported as:** the invariance rate.
- **What a failure would mean:** dependence on specific colour labels.

## 4. Outcomes and stop rule

- **Outcomes:** correct, wrong, abstained, gained and lost versus A; extension used; folds passed; removal
  ablation; CPU.
- **Safety:** any wrong extension certificate or lost answer means NO-GO.
- **Causal:** EG or EG-contrast must beat C2G on paired tasks; otherwise report "no failure-information
  advantage" and stop.
- **Engineering:** guarded solves on the independent pool are reported with their exposure caveat.
- No enlargement or retuning after results.

**Estimated cost:** about 49 tasks × 6 arms, roughly 8–12 h at 4 workers.
