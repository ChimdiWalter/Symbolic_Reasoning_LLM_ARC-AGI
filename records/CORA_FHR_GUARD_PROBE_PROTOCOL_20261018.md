# CORA-FHR guard probe: typed applicability (frozen 2026-10-18, 13:38Z in commit 445f78e, before the run started at 13:38:20Z; DEVELOPMENT ONLY)

**Why proceed.** The root-cause autopsy (`records/CORA_REVISION_ROOT_CAUSE_20261018.md`) found one
remediable pattern: GROUPING_CONFLICT.
- On ka95aa62f67d9, one colour guard splits every supported view into two jointly expressible operators:
  colour 1 gets `ray(NW,border)[centre]`, otherwise `ray(SE,border)[centre]`.
- The 8-task mixed pilot failed because native rejected the unguarded operator on the size-only tasks.

**Not a rerun of the failed pilot.** The synthetic part uses **8 fresh tasks** (`mix_dev2`, seeds 14000+,
sha eced78b6) that have not been run before. The real part is the 2 dev60 conflict tasks. They are in-sample,
because they motivated the hypothesis.

## Hypothesis

A guarded operator (one object feature selecting between two G-grow v1 expressions; `cora_fhr/ggrow_guard.py`)
lets the unchanged engine accept a constructed rule whose applicability differs across objects.

## Cases (fixed, 10)

| part | tasks |
|---|---|
| dev60 | ka95aa62f67d9, k43df875d143f |
| mix_dev2 | M1_00 to M1_03, M3_00 to M3_03 |

## Arms

All arms share the same grammar plus guard, checker, native gate, adaptive LOO and tie rule:

| arm | evidence |
|---|---|
| A | frozen native |
| B | matched search, f_B 1.33 |
| **EG** | authentic failure records (`pattern` fallbacks) + guard |
| **C2G** | *all* native growth correspondences from the same extraction + guard; the strong failure-blind control, with the same object information and the same size and colour features |
| **DG** | shuffled donor evidence + guard. The dev60 donor is the next key; mix_dev2 donors come from the c4_dev_v2 D1/D2 tasks (other rules) |

A guard is tried only when a supported view has no joint fit; an unguarded fit always wins. In every
omitted-example fold, the guard and both branches are relearned from that fold's evidence. Commitment
happens only where A has no certificate. Answers are read only by the evaluator.

## Outcomes per task and arm

- correct, wrong, abstained;
- gained and lost versus A;
- whether a guarded proposal was made;
- extension installed and used;
- folds passed;
- removal ablation (= A);
- CPU.

## Predictions, recorded now

1. On **M3**, EG's evidence holds only the memorized kind, so it needs no guard. It proposes the unguarded
   operator, which native rejected before. C2G sees both kinds and may learn the size boundary. **C2G may
   beat EG**, which would show that the failure filter removes the contrast the applicability guard needs.
2. On **ka95aa62f67d9**, E's evidence already holds both colour groups. EG and C2G find the same guard:
   a tie is expected.
3. On **k43df875d143f**, no guard was found, so no change.

## Stop rule (hard)

1. **Safety:** any wrong extension certificate or lost A-correct answer in a guard arm means NO-GO for this
   route.
2. **Causal:** if C2G ≥ EG on every case, then "no causal advantage of authentic failure evidence; stop
   this version".
3. **Engineering:** EG or C2G certified-correct on ka95aa62f67d9 would be the first real-ARC (training,
   exposed) task solved by a constructed rule. It is reported, but it is not a generalization claim.
4. No enlargement, no retuning, and no change of cases or arms after any result.

## Run

`outputs/cora_fhr/followup_guard.sh` (detached). Completion is validated by return codes and per-arm row
coverage, not by a DONE line.
