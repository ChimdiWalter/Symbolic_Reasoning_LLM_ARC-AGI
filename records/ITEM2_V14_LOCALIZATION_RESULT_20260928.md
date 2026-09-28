# Item-2 v1.4 mechanistic frontier localization: result

Recorded 2026-09-28. Nothing was trained, repaired or scored. Step B
untouched.

## Official v1.4 outcome

**CURRENT_TFG_IDENTIFYING_UNDER_TWINS**, determining stage **S7**, over the
first 42 unique groups (erratum 2), **confirmatory** (42 groups reached),
sealed audit reproduced **byte for byte**.

Two runs make up the experiment and are kept separate:

| | run 1 | erratum-2 continuation |
|---|---|---|
| slots | 0 to 135 | 136 to 140 |
| admissions | 42 (41 unique) | 1 |
| sealed audit | AUDIT_BLOCKED, `duplicate_group_digest`, no statistic | result below, over the first 42 unique groups |
| record | section "Run 1" below, preserved verbatim | this section |

## Identities

| item | value |
|---|---|
| protocol sha256 (erratum 2) | `05e3d96b9f95f288752b8d558b0341e349d53f149d4fcb748efa72b48723a8eb` |
| manifest sha256 (erratum 2) | `1c2202b6dfa2ac94a3e61112705dbbbf379d60a5548753aa79eb3c7e4dbf2aa1` |
| freezes | first 50841e3 (superseded), erratum 1 adecfd2, **erratum 2 5ffa56f** |
| run-1 evidence | fc51275 (blocked audit sha256 `9749e6f4...`, preserved) |
| continuation launch record | b2c08e2 |
| sealed audit sha256 | `1c05140162cb7a0707a34e14e368892683fbadda94f6bfb83ace1f00830ce944` (pass 1, pass 2 and main identical) |
| full-corpus hash list | `outputs/tti/v14_twin_corpus_sha256_erratum2.txt`, sha256 `792a7beb7d67089c99f4fab6c23dab31221bea7292422dbeeab1fe399f3c4fd4` |

## Continuation

- Pre-resume gate PASS at 2026-09-28T14:21:26Z; launched 14:21:37Z from
  5ffa56f; generator PID 2388124 (chain 2388118), sole writer-lock holder,
  nice 19, environment `ARC_META_BUDGET_S=8` and `PYTHONHASHSEED=0` only.
- Cap live at launch: 6.44 h before the 2026-09-28T20:47:49Z deadline.
- Slots 136 to 140 (123 pair attempts, 621 replicate attempts, 436 s);
  **no duplicate encountered** after resume, none skipped, none admitted.
- **42nd unique group**: slot 140, family (0,0), pair seed 101402200, attempt
  22, digest `a6f6d1bb6dae77c674191967c96ecc28e9276d11e74159d6054ebb2e4f124820`,
  started 63,348.7 s after the first start.
- Stop reason `target_groups` at 63,665.5 s from the original first start
  (17 h 41 min, within 86,400 s); generation time over both runs 12,230 s.
- Totals, all 141 slots: 43 admissions, 42 included, 1 excluded duplicate
  (slot 117, first slot 57); 2,922 pair and 14,783 replicate attempts.
- Scientific set: 42 groups, 336 primary episodes, 168 rerun controls, 83
  distinct targets; families (0,0) 17, (1,0) 11, (0,1) 9, (1,1) 3, (0,0,0) 2.
- Engine runs in included groups: 504, wall median 8.035 s (0.153 to
  14.016), CPU median 7.854 s (0.151 to 13.318), CPU/wall median 0.975.
- Rejections, all slots: TARGET_NOT_FITTABLE 7,341; TWIN_OUTPUTS_IDENTICAL
  4,205; PAIR_REPLICATES_SHORT 2,879; TWIN_DEMONSTRATIONS_UNDEFINED 2,022;
  OTHER_FROZEN_CODE 521; TWIN_INPUTS_DIFFER 289; BASELINE_SOLVED 62;
  NO_INFORMATIVE_TFG 20; DUPLICATE_GROUP_DIGEST 0.

## Integrity, before any statistic

Post gate PASS (run by hand, then again inside the audit script): freeze;
first run preserved (136 records, run state, run end, archive, four blocked
reports); 141 contiguous readable records, no partial file; original first
start; 42 included and exactly the one excluded duplicate; environment,
versions, `freeze_ok` and engine state clean on every slot; every new slot
under manifest 1c2202b6 and started within the cap; and for all 43 admitted
groups the grammar re-derivation, twin law, one-token difference, seed law,
run-order law, group integrity and leakage. The sealed auditor's freeze,
integrity, leakage, engine-state, corpus and preservation problem lists are
all empty.

## Stage results (exact null 1/2; identifying = hit rate > 1/2, binomial p < 0.01 and randomization p < 0.01)

| stage | hits/n | hit rate | 95% CI | binomial p | randomization p | ties | strict rate | mean s | median s | identifying |
|---|---|---|---|---|---|---|---|---|---|---|
| S0 demonstrations (baseline) | 223/336 | 0.664 | 0.610 to 0.714 | 9.92e-10 | 8.41e-08 | 0.09 | 0.610 | +0.2644 | +0.1468 | **YES** |
| S2 candidate formation | 193/336 | 0.574 | 0.520 to 0.628 | 3.71e-03 | 4.37e-04 | 0.26 | 0.467 | +0.0371 | +0.0044 | **YES** |
| S3 selector induction | 199/336 | 0.592 | 0.538 to 0.645 | 4.25e-04 | 4.47e-07 | 0.24 | 0.512 | +0.0166 | +0.0031 | **YES** |
| S4 parameter fitting | 192/336 | 0.571 | 0.517 to 0.625 | 5.12e-03 | 9.78e-05 | 0.22 | 0.479 | +0.0297 | +0.0082 | **YES** |
| S5 executable candidates | 173/336 | 0.515 | 0.460 to 0.569 | 3.12e-01 | 2.15e-02 | 0.90 | 0.065 | +0.0047 | +0.0000 | no |
| S6 execution x mismatch | 169/336 | 0.503 | 0.448 to 0.558 | 4.78e-01 | 6.25e-02 | 0.90 | 0.062 | +0.0055 | +0.0000 | no |
| S7a TFG graph | 183/336 | 0.545 | 0.490 to 0.599 | 5.67e-02 | 3.20e-04 | 0.58 | 0.274 | +0.0080 | +0.0000 | no |
| S7 42-field TFG descriptor | 190/336 | 0.565 | 0.511 to 0.619 | 9.43e-03 | 1.73e-03 | 0.14 | 0.503 | +0.3148 | +0.0092 | **YES** |

Holm-adjusted randomization p over the seven reasoning stages: S2 1.75e-03, S3 3.13e-06, S4 5.87e-04, S5 4.30e-02, S6 6.25e-02, S7a 1.60e-03, S7 5.18e-03.
S0 is a demonstration baseline and never enters the ladder.

## Reaction beyond timing noise (twin distance d(A,B) against same-input rerun d(A,A'))

| stage | twin farther | rerun farther | ties | solved reruns excluded | sign p | Holm p (S2 to S5) | REACTS | median d(A,B) / d(A,A') |
|---|---|---|---|---|---|---|---|---|
| S2 | 108 | 15 | 45 | 0 | 7.63e-19 | 7.63e-19 | **REACTS** | 0.27525 / 0.0 |
| S3 | 117 | 13 | 38 | 0 | 2.16e-22 | 4.31e-22 | **REACTS** | 0.54196 / 0.0 |
| S4 | 119 | 10 | 39 | 0 | 3.94e-25 | 1.18e-24 | **REACTS** | 0.5 / 0.0 |
| S5 | 110 | 5 | 53 | 0 | 3.87e-27 | 1.55e-26 | **REACTS** | 1.0 / 0.0 |
| S6 | 121 | 0 | 47 | 0 | 3.76e-37 | not tested (re-scoring stage) | - | 1.0 / 0.0 |
| S7a | 120 | 0 | 48 | 0 | 7.52e-37 | not tested (re-scoring stage) | - | 0.75 / 0.0 |
| S7 | 129 | 9 | 30 | 0 | 1.18e-28 | not tested (re-scoring stage) | - | 2.43847 / 0.0 |

The twin is farther in every time-gap stratum at every stage, so run order
does not explain the reaction.

## Classification, by the frozen ladder

| field | value |
|---|---|
| qualifying stages | S2, S3, S4, S7 |
| randomization-only stages | S7a (after the first qualifying stage, so not blocking) |
| rule applied | groups >= 14; **S7 qualifies** -> CURRENT_TFG_IDENTIFYING_UNDER_TWINS |
| determining stage | S7, survives Holm (5.18e-03) |
| reacting stages | S2, S3, S4, S5 |
| loss point | none for this classification |
| confirmatory | yes, 42 groups |

## Interpretation, kept separate from the classification

1. **The existing failure summary carries target information once scene
   variation is balanced.** v1.3 measured the same 42-field descriptor with
   the same calibration on independently rendered inputs and found no
   identifiability (0.470 against 3/7). Under shared-input twins it
   identifies the target (0.565 against 1/2). The v1.3 negative is therefore
   at least partly an instance-noise and design effect, not an absence of
   target information in the TFG.
2. **The reasoner's own search reacts to the one-feature change.** Candidate
   formation, selector induction and parameter fitting each identify the
   target (0.57 to 0.59), and at S2 to S5 the twin trajectory differs from
   A far more often than a same-input rerun does (median rerun distance 0 at
   every stage). Mechanism B of section 2, a search that does not react, is
   not what happened.
3. **The S7 pass is narrow.** 190 of 336 is exactly the preregistered
   critical count (binomial p 0.0094); the randomization test (0.0017, Holm
   0.0052) is the firmer evidence. Every reasoning-stage effect (0.57 to
   0.59) is below the planned 0.60.
4. **Demonstration statistics identify the target more strongly (S0, 0.664)
   than any reasoning stage.** Under twins the outputs differ by
   construction, so this is expected, but it binds the next step: the v1.2
   scorer fit found candidate features added nothing over demonstration
   statistics, and nothing here shows the TFG adds information beyond S0.
5. **Where the signal thins.** S5 and S6 are 90 percent ties: within the 8 s
   budget the engine forms few executable candidates, so those stages carry
   little information either way. S7a passes only the exact test. S7 mixes
   search-census counts with value signatures scored against each target's
   own outputs; the frozen protocol does not decompose which part carries
   its signal.
6. **The result holds under twins only.** A selection experiment will face
   realistic input variation, the condition under which v1.3 found nothing.

## Claim earned

Under shared-input counterfactual twins (FEATURE contrasts, 42 unique
groups, 336 episodes, 168 rerun controls), the deployed reasoner's existing
42-field failure descriptor identifies which of two minimally different
constructive targets produced a failure above the exact null (0.565 against
1/2; binomial p 0.0094, randomization p 0.0017, Holm 0.0052), and the
reasoner's own candidate formation, selector induction and parameter fitting
both identify the target and react to the one-feature change far beyond
same-input rerun noise.

## Claims not earned

That the signal survives realistic input variation. That it adds information
beyond demonstration statistics. That a scorer or selector can use it. That
S7's identification comes from the search rather than from output
re-scoring. Anything about perception (S1, unobserved). Any constructive
selection, reach, extension, invention, transfer or score.

## Next action, exactly one

**PREREGISTER THE NEXT FAILURE-CONDITIONED SELECTION EXPERIMENT USING THE
TWIN-VALIDATED SIGNAL.** Not designed or implemented here. Two measured facts
bind its design: demonstration statistics (S0) identify the target more
strongly than any reasoning stage, and the signal is established only under
shared inputs. Scorer training, the ConstructiveExtensionCompiler, the 1000
ARC tasks, evaluation DEV and protected HOLDOUT remain blocked.

## Preservation

Unmodified and committed: all 141 slot records including `full00117.json`;
`full_run_state.json`; the first `full_run_end.json`, its archive
`full_run_end_blocked_20260928.json` and `full_run_end_erratum2.json`; the
first hash list (`601ab7c2...`) and the full list (`792a7beb...`); the four
blocked reports (`9749e6f4...`); the three erratum-2 reports
(`1c051401...`); all run, integrity and audit logs.

---

# Run 1 (blocked), preserved as recorded at fc51275

## Item-2 v1.4 mechanistic frontier localization: run record

Run completed 2026-09-28T00:04:35Z; recorded 2026-09-28. Nothing was trained,
repaired or scored. Step B untouched.

### Official outcome

**SEALED AUDIT: AUDIT_BLOCKED (`duplicate_group_digest`). NO
CLASSIFICATION.**

The generation ran to its frozen stop under full integrity. The sealed
auditor then refused to compute any statistic, because one target pair was
admitted twice, and the frozen protocol (section 10, as amended by erratum 1)
makes duplicate group digests a blocking corpus problem. The audit report
contains no stage, sensitivity or classification section. No distance,
nearest neighbour, hit rate, separation or classification has been computed
for v1.4 by anyone.

### Identities

| item | value |
|---|---|
| protocol sha256 | `26e0c60bab43cda44f737c572efcf8ec69fb132d60306d921ac7ddeb88529077` |
| manifest sha256 | `22dccf9a2f3d59dd5805835f9d2e86fd51ac0eb3f9d011e5b8daa4929dd3742e` |
| authoritative freeze | `adecfd2` (erratum 1); first freeze `50841e3` superseded |
| state commits before launch | `0536c69` (resume), launch record `ee3037b`, verification `76d580a` |
| chain | PID 1376598, 2026-09-27T20:47:49Z to 2026-09-28T00:04:35Z |
| generator | PID 1376604, the only writer; `/proc/locks` showed its write lock during the run; single start (seconds this start = seconds since first start) |
| environment, every slot | `ARC_META_BUDGET_S=8`, `PYTHONHASHSEED=0`, no other `ARC_*` |
| runtime, every slot | Python 3.12.3, numpy 2.4.3, scipy 1.16.3 |
| audit report sha256 | `9749e6f42cd19585203b56d9e522cb7828a9b0b948cf5c0908698959bcbcb373` (pass 1, pass 2 and main byte-identical) |
| corpus hash list | `outputs/tti/v14_twin_corpus_sha256.txt`, sha256 `601ab7c2dd9cebbb90f0a8ca333689b1af6c9074b0dd8b89735f349609286e33` |

### Generation

| quantity | value |
|---|---|
| slots | 136 (0 to 135) |
| stop reason | `target_groups`, 42 admitted |
| admitted groups | 42, of which **41 unique** |
| primary episodes | 336 |
| rerun controls | 168 |
| distinct targets | 81 |
| groups by anchor family | (0,0) 16, (1,0) 11, (0,1) 10, (1,1) 3, (0,0,0) 2 |
| pair attempts / replicate attempts | 2,799 / 14,162 |
| wall time | 11,791 s (3 h 17 min), no restart |
| engine runs in admitted groups | 504: wall median 8.035 s (0.153 to 14.016), CPU median 7.854 s (0.151 to 13.318), CPU/wall median 0.975 |

Rejections by frozen reason: TARGET_NOT_FITTABLE 6,992; TWIN_OUTPUTS_IDENTICAL
4,031; PAIR_REPLICATES_SHORT 2,757; TWIN_DEMONSTRATIONS_UNDEFINED 1,972;
OTHER_FROZEN_CODE 507; TWIN_INPUTS_DIFFER 269; BASELINE_SOLVED 58;
NO_INFORMATIVE_TFG 19.

### Integrity

Passed, in the sealed auditor and in independent checks run before the audit
report was opened:

- freeze: verified after every slot (`freeze_ok` true on all 136), by the
  auditor, and again on 2026-09-28 (protocol, manifest, 11 implementation
  files, 5 dependency trees, 2 external grammar files);
- environment, runtime versions and engine state clean on every slot; the
  engine directory holds only its near-solve log (no library, no learned
  verbs, no persisted program);
- leakage: none; per-group integrity: none;
- all 42 target pairs re-derived from the frozen grammar and seed law (slot,
  pair seed, attempt) with matching digests, and the twin law holds for all;
- exactly one token differs in 168 of 168 replicate pairs;
- the run-order hash law holds for 168 of 168 reruns;
- replicate seeds follow the frozen law in 42 of 42 groups.

Failed, blocking:

- **one duplicate group digest**, `b4edae2fce55...`: family (0,1), admitted at
  slot 57 (pair seed 100571900, attempt 19) and again at slot 117 (pair seed
  101170100, attempt 1). The two admissions have disjoint replicate seeds and
  no shared input grids. One further target appears in two different groups,
  which the protocol permits.

### Cause: an implementation defect of mine

Erratum 1 added "group digests unique" to the auditor's blocking corpus
checks, responding to the reviewer's point that integrity keyed by group
digest could mask a problem. The generator was never given the matching rule
(skip a pair whose group digest is already admitted, and count only unique
groups toward the target). Each family admits few fittable (anchor,
feature-swap) pairs, so a recurrence across 136 slots was likely. The static
tests covered only the auditor's side, and the 11-slot smoke was too short to
show it.

### What this does and does not mean

It is a procedural block, not a scientific outcome. It says nothing about
where, or whether, target information appears in the trajectory. The
duplicated pair is, statistically, an independent draw with its own inputs,
but the frozen rule makes it blocking and the rule stands: it is not waived
after the fact.

### Claim earned

The frozen v1.4 counterfactual-twin generation ran to its preregistered stop
with full freeze, environment, leakage and twin-law integrity, and the sealed
audit, reproduced byte for byte, blocked on its preregistered
duplicate-group rule. No classification exists.

### Claims not earned

Any v1.4 classification or localization. Any statement about stage
identifiability, reaction beyond timing noise, TFG or aggregation loss, or
search insensitivity. Any constructive selection, reach, extension,
invention, transfer or score.

### Preservation

The 136 slot records, the run-state and run-end files, the corpus hash list
and all three audit reports are committed unmodified. Nothing in the corpus
was edited, removed or regenerated.

### Next action, exactly one

**Preserve this blocked run and issue erratum 2, a slot-order
duplicate-group rule, before any statistic is computed; then complete the
same run to 42 unique groups under the original caps and re-run the sealed
audit twice.**

What erratum 2 would need, not implemented here: the first admission of a
group digest in slot order counts and later admissions are excluded and
counted (slot 117 today); the generator skips already-admitted digests and
counts unique groups toward 42; generation resumes from slot 136; the blocked
reports and the first run-end record are kept under new names; nothing else
changes. Rejected alternatives: auditing the 41 unique groups now would make
any negative MIXED_OR_INCONCLUSIVE, one group short of the powered target;
waiving the uniqueness rule would change a frozen rule to fit the data
already in hand.

**Timing fact:** the frozen 24 h wall-clock cap counts from the first start
and expires at **2026-09-28T20:47:49Z**. At the run's mean of about 4.7
minutes per admitted group, one more unique group should take minutes, well
within the cap. After that time the resumed run would stop at once, and the
erratum would also have to address the cap.
