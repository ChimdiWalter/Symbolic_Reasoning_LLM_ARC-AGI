# CORA-FHR guarded-construction generalization test: FROZEN PROTOCOL (2026-10-18; frozen in commit ad4127a before the run started at 17:45:59Z; DEVELOPMENT; authorized by the user 17:40Z)

**Supersedes the proposal.** It replaces `records/CORA_FHR_GUARD_GENERALIZATION_PROPOSAL_20261018.md`.
The only change is the pool size, which follows from the fixed rule: 58, not "≤ 49". Only 4 of the 13
dev60 overlaps are among the eligible tasks.

**Not prospective.** The tasks are exposed ARC-AGI-2 **training** tasks, so a positive result is not a
prospective or generalization claim. No protected split is used (E_transfer, HOLDOUT, ARC-1000, the frozen
120 pilot and the sealed C4 final are excluded).

## Pool (fixed by rule before any guarded run)

- **Rule:** every CORA_FHR_V1 rehearsal task with `fhr == "ran"` (growth-shaped, native-uncertified;
  62), minus dev60 overlaps by training-pair content (4).
- **Result: 58 tasks.** `outputs/cora_fhr/standin58.json` (sha 0386206d), IDs in `standin58_pool.json`,
  builder `cora_fhr/corpus_standin.py`.
- **Not selected by the autopsy:** the autopsy's guard case (ka95aa62f67d9) is a dev60 task, not in this
  pool.

## Arms (same grammar plus guard, same native gate, adaptive LOO, tie rule and commit rule)

| arm | evidence |
|---|---|
| A | frozen native |
| B | matched search (f_B 1.33) |
| EG | authentic failure records + guard |
| C2G | all correspondences + guard: the strong failure-blind control, with the same object information and features |
| DG | shuffled donor (next key in sorted order) + guard. Known limitation: donor evidence is not fold-symmetric |
| **EGC** | contrast. **What** is learned from native's memorized (`pattern`) objects; **where** from a guard separating them from objects native explained, with a null else branch (`cora_fhr/construct.py::propose_contrast`) |

In every omitted-example fold, the guard and the operator are relearned from that fold's evidence alone.

## Colour relabelling (fixed rule)

- **Which tasks:** every pool task where **any** construction arm (EG, C2G, DG or EGC) certified an
  extension in the main run is rerun as its relabelled twin (`standin58_perm.json`, sha 58c7b92f).
- **The twin:** colours 1–9 permuted, background fixed, seed sha256(task ID).
- **Arms:** A, EG, C2G, EGC.
- **Measures:** whether the certified rule is the relabelled image of the original rule, and whether the
  twin is still correct.

## Outcomes

Per task and arm:
- correct, wrong, abstained;
- gained and lost versus A;
- extension accepted and used;
- folds passed;
- restored;
- CPU.

## Primary comparisons (paired sign tests, one-sided, α 0.05)

- EG vs C2G;
- EGC vs C2G;
- EGC vs EG.

The count is discordant pairs, where one arm is correct and the other is not.

## Stop rule (hard)

1. **Safety:** any wrong extension certificate or lost A-correct answer in any construction arm means
   NO-GO for that arm.
2. **Causal:** an authentic arm (EG or EGC) shows a failure-information advantage only if it is
   significant against C2G. Otherwise report "no failure-information advantage" and stop this version.
3. **Engineering:** extension-certified correct answers on the pool are reported per arm, with the
   exposure caveat.
4. No enlargement, retuning, change of pool or change of arms after any result.

## Predictions (recorded now)

- Most pool tasks give NO_PROPOSAL in every arm; the rehearsal had 61 of 62 without guards.
- Few discordant pairs, so a significant result is unlikely; the expected outcome is "no significant
  advantage".
- EGC may beat EG where native explains part of a view, and match it elsewhere.

**Run:** `outputs/cora_fhr/followup_gen.sh`, detached. Completion is validated by return codes and
per-arm coverage.

## Interpretation addendum (2026-10-18T18:06Z, before any informative result: 1 of 58 rows existed, NO_PROPOSAL in every arm; stricter only; the run is unchanged)

1. **Multiplicity.**
   - The three one-sided sign tests (EG vs C2G, EGC vs C2G, EGC vs EG) are reported with raw p-values and
     **Holm-adjusted** p-values over the family of three.
   - A failure-information advantage requires a Holm-adjusted p < 0.05 for an authentic arm against C2G.
2. **Matched-comparison scope.**
   - Any EGC advantage is reported with its mechanism: which object access, candidate set and guard
     produced it.
   - The shuffled control DG is not fold-symmetric (known limitation), so it is not used as the sole
     evidence that the *content* of the failure trace matters.
3. **Exposure.** The tasks are exposed training tasks: no generalization or prospective claim either way.
