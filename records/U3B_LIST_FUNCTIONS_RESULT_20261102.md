# Result U3b: guided construction against blind enumeration at matched CPU (2 Nov 2026)

## Provenance

**Pre-registration and review:**
- **Protocol:** `experiments/capability_growth_20261027/u3b_list_functions/PROTOCOL.md`, revision 2 (sha256
  `bb17b08e…`). Its freeze manifest `PROTOCOL_FREEZE.json` (`c49dd2df…`) lists 21 files; commit 5b8a36ae.
- **Reviews:**
  - prefreeze review V1 (`98e69a2d…`);
  - exact-byte re-review V2, HOLD on two provenance gates (`e91d0732…`);
  - revision-2 exact-byte re-review, PASS (`df9ce6de…`).

**The run:**
- **Launch.** The coordinator wrote `runs/GO_U3B` at 18:09:37Z with the two reviewed lines. The chain ran once, from
  one start, with no interruption or resume, so no partial checkpoint was ever resumed.
- **Gates.** The provenance gate passed at the start and before the build, arms, evaluation and save.
- **Timeline (UTC):**

  | step | time |
  |---|---|
  | build finished (after waiting for a shared CPU slot) | 18:25:26 |
  | arms finished | 18:50:37 |
  | evaluation, then EXIT 0 | 18:50:38 |

- **Commits.** The chain committed the results in cff6efb4. The two trailing status lines went into the coordinator's
  autosave 996bb481.

**Custody** (all verified after the run):

| object | sha256 |
|---|---|
| build manifest (exactly the seven required outputs) | `9b5c817e…` |
| arms freeze (frozen 18:50:36Z; names the build manifest) | `011927fd…` |
| units.json (named in the arms freeze) | `b4e1649d…` |
| c7m.json (named in the arms freeze) | `4379eecf…` |
| results.json (named in the evaluation freeze) | `fc2eed2d…` |
| evaluation freeze | `3f5e4f26…` |
| report as written, `reports/TEST_U3B_REPORT.md` in cff6efb4 | `dc130a66…` |

**Verification before this record:**
- The gate check for "save" passes, and all 21 frozen files are unchanged.
- **Independent recomputation.** A standard-library script, not the evaluator's code, recomputed from `units.json` and
  `tasks_eval.json`:
  - the primary and both secondary McNemar tests;
  - the anytime sign-flip test and the Holm adjustment;
  - the trial, admitted and promoted counts;
  - the cap invariants: no counted blind row lies beyond its cap.

  Every item agrees with `results.json`.
- **Report check.** The freeze does not verify the report, so it was checked separately:
  - it matches its recorded digest;
  - re-rendered from `results.json` with the frozen writer, it is byte-identical (5,596 bytes).

**Compute.** 0.48 CPU-h (build 0.06, arms 0.42, evaluation under 0.01), CPU only, one shared slot, no GPU.

## Population and construction

**Population.** A conditional follow-up on the same 250 BIG-bench list_functions concepts as U3. Query outputs were
used to select the operations and the tasks.
- The full DSL solves 82 concepts and G0 solves 74.

**Deleted operations.** U3's rule, without U3's four operations, deleted dedup, filter_even, rotate_left and filter_gt:
the four most-used operations with a genuine gap. Tail, init, prepend, append, sort_asc and sort_desc had no gap.

**Tasks:**
- **Families:** 3, 2, 2 and 2 eligible tasks; every one is motivating. No family had validation or excluded tasks.
- **Motivating tasks:** 9.
- **Others:** 14 previously solved tasks and 4 decoys.

## The primary contrast (pre-declared)

**S-hole-ext against S-enum-MATCHED, trial recovery, task level (majority of 3 seeds): 4 against 1 of 9 tasks;
discordant 3 : 0; exact two-sided McNemar p = 0.25. Decision: NOT CONFIRMED.**

- With 9 tasks, the "underpowered" rule (fewer than 6) does not apply. With only 3 discordant tasks, 0.25 is the
  smallest p attainable.
- **The matched blind arm's caps** equal S-hole-ext's charged CPU on each unit, a mean of 2.57 CPU-s.
  - All 27 of its units stopped on the cap.
  - It was charged 2.14 CPU-s per unit. Counting the overshooting stage's work, which was done but never counted,
    it spent 3.68 CPU-s.

## Secondary contrasts (Holm over three)

| contrast | result | raw p | Holm p |
|---|---|---|---|
| S-hole-ext vs S-demo | 4 vs 3 (1 : 0) | 1.0 | 1.0 |
| S-hole-ext vs S-shuffled-ext | 4 vs 0 (4 : 0) | 0.125 | 0.375 |
| anytime AUC, S-hole-ext vs S-enum | 0.321 vs 0.136 (paired difference +0.185) | 0.203 | 0.406 |

None is significant. Under the causal-reading rule fixed in advance, no task-specific demonstration context is
credited.

## Stages per arm (tasks, majority of 3 seeds)

| arm | trial recovery | admitted | promoted | charged CPU-s per unit |
|---|---|---|---|---|
| S-hole-ext | 4 | 4 | 3 | 2.57 |
| S-enum-MATCHED | 1 | 1 | 0 | 2.14 (3.68 with overshoot work) |
| S-hole | 3 | 3 | 2 | 2.29 |
| S-demo | 3 | 3 | 2 | 2.28 |
| S-shuffled | 0 | 0 | 0 | 0.82 |
| S-shuffled-ext | 0 | 0 | 0 | 0.82 |
| S-enum (60 CPU-s cap) | 7 | 7 | 5 | 47.49 (48.84 with overshoot work) |
| C7m (G0 search, 150 CPU-s) | 3 | | | 146.05 per task |

- S-enum stopped on its 60 CPU-s cap in 15 of its 27 units.
- **Seed effects.** Results varied by seed for S-enum on 6 of the 9 tasks, for S-enum-MATCHED on 1, and for no other
  arm.

**Anytime trial recovery** (tasks recovered within the CPU-s given per unit, in at least 2 of 3 seeds):

| CPU-s | 0.25 | 0.5 | 1 | 2 | 4 | 8 | 16 | 32 | 60 |
|---|---|---|---|---|---|---|---|---|---|
| S-hole-ext | 0 | 1 | 2 | 3 | 4 | 4 | 4 | 4 | 4 |
| S-enum | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 2 | 7 |

**Per family** (trial recovery, tasks):

| family | tasks | S-hole-ext | S-enum-MATCHED | S-demo | S-enum | C7m |
|---|---|---|---|---|---|---|
| dedup | 3 | 2 | 0 | 1 | 3 | 0 |
| filter_even | 2 | 0 | 0 | 0 | 2 | 2 |
| rotate_left | 2 | 1 | 0 | 1 | 1 | 1 |
| filter_gt | 2 | 1 | 1 | 1 | 1 | 0 |

**Promoted structures and reuse.**
- The three promoted structures each agree exactly with a deleted operation on the probes and test inputs: KEEP:even
  with filter_even, ORDER:dedup with dedup, and ORDER:rotate_left with rotate_left. This is an evaluator diagnostic.
- No structure matching filter_gt was promoted.
- No family had excluded tasks, so reuse on excluded tasks could not be measured.

## Exploratory, post hoc: U3 replayed

U3's 9 tasks were scored under U3b's contrasts by replay from U3's frozen gate cache: S-hole-ext 7 against replayed
S-enum-MATCHED 0, with no unavailable replays.
- This is not confirmatory and is not pooled with the primary.
- U3's outcome motivated U3b's design.
- U3 charged no specification CPU, which favours the guided arm in the replay.

## Reading

**The direction favours guided construction at small budgets, but the pre-declared test fails.**
- All 3 discordant tasks favour S-hole-ext.
- S-hole-ext reached its 4 recoveries by 4 CPU-s per unit, before blind enumeration recovered any (its first came at
  8 CPU-s).
- With 9 tasks and 3 discordant, p = 0.25, so no efficiency claim is made.

**Given about 18 times the CPU, blind enumeration recovers more.**
- At 60 CPU-s per unit, S-enum recovered 7 of 9 tasks, against the guided arm's 4.
- Guided construction recovered neither filter_even task, while blind enumeration and the G0 search recovered both.

**Demonstrations carry most of the specification.**
- The identity sketch alone (S-demo) recovered 3 tasks. The failure-triggered extended sketches added one (1 : 0).
- Sketches taken from another task recovered nothing. Those arms used a third of S-hole-ext's CPU, however, so this
  is not an equal-work comparison.

## Limits

- **Population:** a conditional population on the same 250 concepts as U3, selected using query outputs. It is not
  independent, and its p-values are descriptive.
- **Schema:** the constructed operations are selected from a known 59-structure schema space, not invented.
- **Power:** 9 tasks and 3 discordant. The secondary controls are not matched to S-hole-ext's work unit by unit.
- **Reuse:** no excluded tasks existed, so reuse was not measurable.
- **What U3b does not show:** cross-domain or universal capability growth, invention of new primitives, or that
  failed-program traces supply sketch content. The sketches are built from the demonstrations; the failed G0 search
  only triggers their construction.

## Claim for the paper

> In a pre-registered, conditional follow-up on BIG-bench list functions (nine tasks selected by an operation-removal
> rule), CORA's failure-triggered, demonstration-derived hole specification recovered 4 tasks with the CPU it used.
> Blind enumeration of the same schema space, given the same CPU on every unit, recovered 1 (3 : 0 discordant, exact
> McNemar p = 0.25). The pre-declared test was not met, so we make no efficiency claim. Given about 18 times more CPU
> per unit, blind enumeration recovered 7 of the 9.
