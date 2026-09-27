# Item-2 v1.3 contrastive corpus: result

Full generation completed 2026-09-26 and was audited twice by the sealed
auditor. Recorded 2026-09-27. Nothing was trained, compiled or scored on ARC.
No group was filtered on any frontier property. Step B untouched.

## Official verdict

**V1.3 CONTRASTIVE CORPUS IDENTIFIABILITY GATE FAIL.** Seven of ten gates fail.

## Identities

| item | value |
|---|---|
| protocol sha256 | `66aa1c561ac4fd2a619459f15919282776a5898ab3ae6f36ae6944a5389d8f1e` |
| manifest sha256 | `9492f392d13e95b033b3f6a77d6dd75d27cbb11b6d0ac7dad104901fab56de14` |
| calibration sha256 | `ba82865e52cd9e025442ea73ee7ad83ee894b5ad8610a7753ce37a44051c7c02`, committed `aaa2972` with Phase B groups at zero |
| pilot sha256 | `c578cdf980cf47731c97aa874f504d193f1f8453565d57057a552e815028c1e9` |
| q | 0.025, frozen and committed `e9ba44c` with full-run groups at zero |
| full-run launch | `a020c45` |
| generator | `0146e20`, Phase A ceiling correction `ca033a7` |
| auditor | `4a6efd8`, record-selection correction `94c159a` (erratum 2) |
| audit report sha256 | `263ec77436040499fe2362f844125b1e811c7cafd62270cab367743a91c7809c` |
| errata | 1 constant-field divisors; 2 auditor read pilot records; 3 generator not reproducible |

## Full run

1,200 group slots, exactly as the frozen formula required: `ceil(84/0.025)` is
3,360, capped at 1,200. 29,763 attempts. Wall time 49,814 seconds, about 13.8
hours. Every one of 1,200 records readable, 1,200 distinct slot identifiers,
no duplicate group digest, and every admitted group structurally valid: eight
episodes, two distinct targets, replicates zero to three for each, and a
demonstration distance within 0.5.

| contrast type | slots | admitted | rate |
|---|---|---|---|
| PARTITION | 400 | **0** | 0.000 |
| FEATURE | 400 | 14 | 0.035 |
| SELECT | 400 | 7 | 0.018 |
| total | 1,200 | **21** | 0.0175 |

21 groups, 168 episodes, 41 distinct target digests.

| rejection | count |
|---|---|
| TARGET_NOT_FITTABLE | 24,689 |
| TARGET_EXECUTION_UNDEFINED | 3,560 |
| OTHER_FROZEN_CODE | 1,127 |
| BASELINE_SOLVED | 183 |
| DEMO_NOT_MATCHED | 107 |
| NO_INFORMATIVE_TFG | 76 |

Splits follow the frozen law mechanically: with fewer than 60 admitted groups,
all 21 fall into training, and validation and holdout are empty. No
alternative split was invented.

## Gates

| gate | measured | threshold | result |
|---|---|---|---|
| G1 primary identifiability | hit rate 0.4702, 79 of 168, p = 0.156 | above 3/7 and p < 0.01 | **FAIL** |
| G2 without SELECT | hit rate 0.4732, 53 of 112, p = 0.195 | above 3/7 and p < 0.01 | **FAIL** |
| G3 separation direction | 0.524 of groups with s > 0, p = 0.50 | above 0.5 and p < 0.01 | **FAIL** |
| G4 separation magnitude | mean s 0.188 | at least 0.25 | **FAIL** |
| G5 scale | 21 training groups | at least 60 | **FAIL** |
| G6 coverage | PARTITION 0, FEATURE 14, SELECT 7 | at least 3 each | **FAIL** |
| G7 distinct targets | 41 | at least 100 | **FAIL** |
| G8 splits | disjoint | disjoint | PASS |
| G9 leakage | 0 violations | zero | PASS |
| G10 evidence | every admitted episode informative | all | PASS |

Nearest neighbour against the exact null of 3/7 = 0.428571:

| subset | hits | instances | rate | one-sided p |
|---|---|---|---|---|
| all | 79 | 168 | 0.4702 | 0.156 |
| FEATURE | 53 | 112 | 0.4732 | 0.195 |
| SELECT | 26 | 56 | 0.4643 | 0.341 |
| PARTITION | none admitted | 0 | undefined | undefined |

Separation `s = B - W` over 21 groups: mean 0.188, **median 0.025**, minimum
-0.868, maximum 2.203. By type, FEATURE 0.230 and SELECT 0.104. The mean is
carried by a few groups; the median separation is essentially zero.

## Reproduction

The sealed auditor was run twice over the same stored corpus. The two reports
are **byte-identical**. Per erratum 3, this is audit reproducibility only: the
generator is not reproducible, because two admission stages are wall-clock
deadline bound, so no claim of corpus reproduction is made.

## Interpretation, kept separate from the official verdict

This is **case B** of the preregistered interpretation matrix: the primary
identifiability gates G1 and G2 fail. The scale gates also fail, but that is
secondary. The failure is not merely that too few groups were admitted to see
an effect. On the groups that were admitted, the effect is not there at the
size the experiment was designed for.

Nearest neighbours in frontier space pick the same-target replicate 47.0
percent of the time against a chance level of 42.9 percent. Within-target and
between-target frontier distances are indistinguishable, with a median
separation of 0.025 and barely more than half of groups separating in the right
direction at all.

**Power, stated so the result is not over-read in either direction.** The
experiment admitted 168 instances against a plan of about 480. The exact
one-sided 95 percent upper bound on the hit rate is 0.537. The protocol was
powered to detect a rate of 0.55, and **0.55 is excluded at 95 percent**. So a
large identifiability effect of the kind that would make the frontier a useful
guide to construction is ruled out. A small effect below roughly 0.54 is not
ruled out at this sample size. The accurate statement is that no evidence of
identifiability was found and a large effect is excluded, not that the
frontier provably carries no information.

**Consistency with v1.2.** v1.2 found that no evidence group recovered the
target in an unmatched corpus. v1.3 removed the confounds v1.2 could not
control, matching demonstrations and holding everything but one grammar
position fixed, with replicates to estimate within-target noise, and the
frontier still does not separate the targets. Two independent designs now
point the same way.

This is what the mechanism named in the v1.3 protocol would predict. The
failure frontier is expressed in the deployed reasoner's vocabulary of
segmentation, correspondence, selection and parameter fitting, while the
target is expressed in the constructive grammar's vocabulary of partitions,
selects and key features. Minimal changes in the second do not produce
systematic changes in the first. That reading is interpretation, not a
measured result, and it is offered as the hypothesis the next preregistration
would have to address.

**On the early projection.** Twenty-six slots into the run I reported an
extrapolation of about 138 admitted groups. It was wrong: the final count is
21, and the pre-run projection of about 30 recorded in the committed pilot
artifact was closer. Nothing was changed in response to either projection,
which is exactly why they were recorded rather than acted on.

**PARTITION admitted nothing.** 400 slots, zero groups. Demonstration
mismatch is not the cause, at 26 rejections; the dominant rejection is target
fittability as for the other two types. The consequence is that the cleanest
within-family contrast type produced no evidence at all, which is why G2 rests
on FEATURE alone.

## Claim earned

A negative. Under a prospectively frozen, demonstration-matched, replicated
contrastive design with an exact nonlearned null, the deployed reasoner's
failure frontier does not measurably identify which of two minimally different
constructive targets produced it, and a large identifiability effect is
excluded at 95 percent.

## Claims not earned

Failure-target identifiability. Learned failure conditioning. Any constructive
selection, reach, extension, invention, transfer or score. Any claim that the
frontier carries no information whatsoever, since a small effect is not
excluded.

## Next action, exactly one

**Preserve the v1.3 failure and preregister only the smallest follow-up needed
to address the recorded failure mode.**

The recorded failure mode is identifiability, with scale failing in addition.
That ordering matters for what a follow-up could usefully be: scaling up a
corpus in which the effect is absent would at best detect a small effect of
limited use for guiding construction. The follow-up is not designed here.

The scorer discrimination experiment is **not** licensed, because the
identifiability gate failed. The ConstructiveExtensionCompiler stays blocked.
