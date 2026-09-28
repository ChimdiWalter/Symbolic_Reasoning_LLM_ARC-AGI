# Item-2 v1.4 mechanistic frontier localization: run record

Run completed 2026-09-28T00:04:35Z; recorded 2026-09-28. Nothing was trained,
repaired or scored. Step B untouched.

## Official outcome

**SEALED AUDIT: AUDIT_BLOCKED (`duplicate_group_digest`). NO
CLASSIFICATION.**

The generation ran to its frozen stop under full integrity. The sealed
auditor then refused to compute any statistic, because one target pair was
admitted twice, and the frozen protocol (section 10, as amended by erratum 1)
makes duplicate group digests a blocking corpus problem. The audit report
contains no stage, sensitivity or classification section. No distance,
nearest neighbour, hit rate, separation or classification has been computed
for v1.4 by anyone.

## Identities

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

## Generation

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

## Integrity

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

## Cause: an implementation defect of mine

Erratum 1 added "group digests unique" to the auditor's blocking corpus
checks, responding to the reviewer's point that integrity keyed by group
digest could mask a problem. The generator was never given the matching rule
(skip a pair whose group digest is already admitted, and count only unique
groups toward the target). Each family admits few fittable (anchor,
feature-swap) pairs, so a recurrence across 136 slots was likely. The static
tests covered only the auditor's side, and the 11-slot smoke was too short to
show it.

## What this does and does not mean

It is a procedural block, not a scientific outcome. It says nothing about
where, or whether, target information appears in the trajectory. The
duplicated pair is, statistically, an independent draw with its own inputs,
but the frozen rule makes it blocking and the rule stands: it is not waived
after the fact.

## Claim earned

The frozen v1.4 counterfactual-twin generation ran to its preregistered stop
with full freeze, environment, leakage and twin-law integrity, and the sealed
audit, reproduced byte for byte, blocked on its preregistered
duplicate-group rule. No classification exists.

## Claims not earned

Any v1.4 classification or localization. Any statement about stage
identifiability, reaction beyond timing noise, TFG or aggregation loss, or
search insensitivity. Any constructive selection, reach, extension,
invention, transfer or score.

## Preservation

The 136 slot records, the run-state and run-end files, the corpus hash list
and all three audit reports are committed unmodified. Nothing in the corpus
was edited, removed or regenerated.

## Next action, exactly one

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
