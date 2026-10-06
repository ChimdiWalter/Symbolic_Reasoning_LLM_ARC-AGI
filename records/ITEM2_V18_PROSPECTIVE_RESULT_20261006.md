# Item-2 v1.8: prospective no-oracle proposer result

**FAILURE_SPECIFIC_BUT_NOT_END_TO_END** (G1 passes, G2 fails), run once on
2026-10-06. Independent terminal verification: all 31 checks pass, and every
recomputed value equals the report.

The proposer is not accepted. LEVEL 2 is not reached; the claim stays
LEVEL 1 (v1.6 hybrid, v1.7 compiler). The real ARC pilot is NOT licensed.

## Identities

| object | value |
|---|---|
| frozen commit (re-freeze after erratum 01) | b69b770 |
| manifest | `outputs/tti/no_oracle_proposer_v18_manifest.json`, sha256 `d64732cf54f91f70ce6f7be041956850d6cc85ca3986e4e08199401278db8731` |
| protocol | `docs/CORA_TTI_NO_ORACLE_PROPOSER_v1.8.md`, sha256 `59e0889f65b0d2ed743697d0920b48ed121d0d5d031b3d0b8154eb1e36fbeb0f` |
| proposer | `cora_arc2026/v18_proposer.py`, sha256 `8fbb08018814f31bb584b9fb1bf9eff03465bfab1f72bfbcb3a517ef046cdf07` |
| prospective script | `scripts/v18_prospective.py`, sha256 `827cbdaf03e0edf84d06771ae5de6f46d209f261c8d99b4eaaa2a82a142f2188` |
| compiler (v1.7, unchanged) | `cora_arc2026/v17_compiler.py`, sha256 `04c6b3a19b9645cdfd983e2733e377b8b342e11a4c09b209f3dddb5868515152` |
| K* identity | `b009a9fb13402348a73c3e1ef187a82c2d42fb5175e5fed806e8d33d6b73e729` |
| report | `outputs/tti/v18_prospective_report.json`, sha256 `af068bcdc8d3c23c49d8dd2c37c8727f78801b39d1050730f2df9bd222fe77f6` |
| rows | `outputs/tti/v18_prospective_rows.jsonl`, sha256 `ccbc7d5373ec730382dc0c98265fd0e9cd8af44e8bbdf43a21b3065e06dce385` |
| terminal verifier | `logs/v18/verify_prospective.py` (549589e, committed before any result existed); output `logs/v18/verify_prospective.json`, sha256 `26d05abf284ef8b877ca7d953cd55878c9ea80146b51b15c5e7d3e0e925318b8` |
| launch record, watcher | `logs/v18/prospective_launch.json` (fa3163a); `logs/v18/prospective_watch.sh` (0345a23) |
| first freeze, review, erratum | e7afc0f (manifest bd657faa); `records/ITEM2_V18_REVIEW_RESULT.md` (b98bd24); `records/ITEM2_V18_ERRATUM_01.md` (f4d6fab, code c7c8892) |

## Freeze verification before launch

Clean tree at HEAD 9ece482; manifest, protocol, proposer, compiler prefix
and K* identity equal to the values above; status
FROZEN_AFTER_ERRATUM_01_NOT_PROSPECTIVELY_TESTED; `freeze_problems()`
returned []; the four prospective outputs were absent; no writer was running.
The verifier repeated the freeze checks after the run: unchanged.

## Run

- Launched once with `setsid nohup .venv_arc2026/bin/python
  scripts/v18_prospective.py` at 2026-10-06T19:08:11Z (start record
  19:08:14Z). Writer pid 1089796, its own session and process group
  (1089796), launcher 1089794, boot id
  5c543236-c905-416e-9e7f-af441c8fc4b5, one process at default priority.
- Environment: PYTHONHASHSEED=0, PYTHONPATH = the tti tree, no ARC_*
  variable at start or end.
- 5,911.6 s (98.5 minutes). Marker written at 20:46Z; the detached watcher
  ran the verifier (exit 0, 20:48:10Z) and removed its `@reboot` hook. The
  crontab is identical to the pre-v1.8 backup.
- Load average 82.9 at start and 60.0 at end, 55 to 86 around the engine
  stages, on 24 CPUs: about twice the development load. Step B's workers
  ran throughout and were not touched.
- No resume (the watcher's resume flag was never written), one writer, no
  unexpected exception, no error row, no leakage in any arm or fold.
- Monitoring during the run was administrative only (liveness, row count,
  load, marker, traceback). No partial result was read.

## Corpus

- The first 30 qualifying tasks among the first 908 seeds of
  860,000,000 + 100k (seeds 860002800 to 860090700).
- 30 distinct seeds and 30 distinct target digests, none in the
  3,817-digest exclusion set. The verifier re-derived the corpus law and
  obtained the same 30 (seed, digest) pairs in the same order.
- Families (1,1) 15, (0,1) 8, (1,0) 7. Seen structure (normalized target
  text among the 40 development structures) 4; unseen 26.

## Gate G1, failure specificity: PASS

"Useful" = the arm's selection predicts the held-out pair at fitter level.
One-sided exact sign test on discordant tasks, alpha 0.05 each.

| control | main useful | control useful | both | main only | control only | neither | p (one-sided) | pass |
|---|---|---|---|---|---|---|---|---|
| SHUFFLED_FRONTIER (transplant) | 30 | 17 | 17 | 13 | 0 | 0 | 0.000122 (2^-13) | yes |
| BLIND | 30 | 23 | 23 | 7 | 0 | 0 | 0.0078 (2^-7) | yes |

## Gate G2, end to end: FAIL

11 of 30 tasks give a complete synthetic witness; 15 required.

| leg | meaning | tasks |
|---|---|---|
| B | K* arm not accepted | 30 |
| P | proposer selected an extension | 30 |
| U | the K* + {e} winner uses e | 25 |
| L | every leave-one-out fold succeeds, proposal rebuilt in each fold | 11 |
| T | held-out pair exact under K* + {e} | 25 |
| A | K* alone at 3x budget (24 s) does not reproduce the held-out output | 30 |
| complete | all six | 11 |

## Useful counts and classes by arm

| arm | useful | classes |
|---|---|---|
| FAILURE_CONDITIONED (main) | 30 | SELECTED 30 |
| NO_RESPONSE | 30 | SELECTED 30 |
| BLIND | 23 | SELECTED 23, NO_VERIFIABLE_PROPOSAL 7 |
| SHUFFLED_FRONTIER | 17 | SELECTED 17, NO_VERIFIABLE_PROPOSAL 10, PROPOSAL_LIMIT 3 |
| PURE | 6 | SELECTED 6, SELECTION_ABSTAINED 24 |
| DEMO_ONLY | 1 | SELECTED 1, PROPOSAL_LIMIT 29 |
| SHUFFLED_COORDINATES | 0 | NO_PROPOSAL 30 |

## Engine stage, leave-one-out and the 3x baseline

- Engine with K* + {e}: EXTENSION_NECESSARY_AND_USED with the held-out
  pair exact on 25 tasks; NOT_SOLVED_WITH_EXTENSION on 5 (seeds 860002800,
  860028300, 860046800, 860064200, 860086200), although the selection was
  useful at fitter level on all 30.
- Real leave-one-out: 127 of 210 folds SUCCESS, 81 LOO_FAILURE, 2
  K_ALREADY_SOLVES. Folds succeeding per task: 7 on 11 tasks, 6 on 2, 4 on
  7, 3 on 3, 1 on 1, 0 on 6.
- K* at 3x budget: ran on 30, accepted 0, reproduced no held-out output.
  Runs ended at about 24 s on 20 tasks, about 32 s on 3, and earlier on 7
  (0.3 to 20.9 s).

## Splits

| split | tasks | witnesses |
|---|---|---|
| seen structure | 4 | 2 |
| unseen structure | 26 | 9 |
| family (0,1) | 8 | 5 |
| family (1,0) | 7 | 4 |
| family (1,1) | 15 | 2 |

Deciding selection level of the main arm: MDL 18, D 6, VERIFICATION_UNIQUE
5, P0 1, abstained 0. Witnesses by level: VERIFICATION_UNIQUE 4 of 5, D 2 of
6, MDL 5 of 18, P0 0 of 1.

## Supplementary, not gating

- PURE against the hybrid main arm: main only 24, PURE only 0 (p 6.0e-8).
  PURE abstained on 24 of 30.
- NO_RESPONSE against the main arm: no discordant task (both 30 of 30). The
  candidate-conditioned response probe (P0) decided 1 of 30 selections and
  changed no usefulness outcome.
- Sanity controls against the main arm: SHUFFLED_COORDINATES 30 to 0 (it
  proposes nothing, as in development), DEMO_ONLY 29 to 0.
- K_ALREADY_SOLVES folds: 2 (task 6 fold 5, task 19 fold 3).
- S6, descriptive only on this corpus (erratum 01): new-capability label 30
  of 30, C_probes SEPARATED 23 of 30. Not claimed.

## Per task

| i | seed | family | seen | main level | engine verdict | held-out exact | 3x K* accepted (s) | LOO folds | witness |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 860002800 | (1,1) | no | MDL | NOT_SOLVED_WITH_EXTENSION | no | no (24.0) | 0 of 7 | no |
| 1 | 860003300 | (1,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.4) | 1 of 7 | no |
| 2 | 860007300 | (1,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 7 of 7 | yes |
| 3 | 860009300 | (1,1) | no | VERIFICATION_UNIQUE | EXTENSION_NECESSARY_AND_USED | yes | no (11.3) | 4 of 7 | no |
| 4 | 860015800 | (1,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (14.9) | 4 of 7 | no |
| 5 | 860016600 | (1,0) | no | D | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 7 of 7 | yes |
| 6 | 860016800 | (1,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.2) | 0 of 7 (1 K_ALREADY_SOLVES) | no |
| 7 | 860022100 | (1,0) | yes | D | EXTENSION_NECESSARY_AND_USED | yes | no (24.2) | 3 of 7 | no |
| 8 | 860024700 | (0,1) | no | D | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 4 of 7 | no |
| 9 | 860027300 | (1,1) | no | P0 | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 6 of 7 | no |
| 10 | 860028300 | (1,1) | no | D | NOT_SOLVED_WITH_EXTENSION | no | no (32.2) | 0 of 7 | no |
| 11 | 860029300 | (1,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 6 of 7 | no |
| 12 | 860032200 | (0,1) | no | VERIFICATION_UNIQUE | EXTENSION_NECESSARY_AND_USED | yes | no (14.6) | 7 of 7 | yes |
| 13 | 860033100 | (1,0) | yes | VERIFICATION_UNIQUE | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 7 of 7 | yes |
| 14 | 860033600 | (1,0) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 7 of 7 | yes |
| 15 | 860046800 | (1,1) | no | MDL | NOT_SOLVED_WITH_EXTENSION | no | no (32.1) | 0 of 7 | no |
| 16 | 860051200 | (0,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 7 of 7 | yes |
| 17 | 860051300 | (1,1) | no | VERIFICATION_UNIQUE | EXTENSION_NECESSARY_AND_USED | yes | no (6.0) | 7 of 7 | yes |
| 18 | 860054700 | (0,1) | no | D | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 7 of 7 | yes |
| 19 | 860059600 | (1,0) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 3 of 7 (1 K_ALREADY_SOLVES) | no |
| 20 | 860064200 | (0,1) | yes | MDL | NOT_SOLVED_WITH_EXTENSION | no | no (32.2) | 0 of 7 | no |
| 21 | 860071300 | (1,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (0.3) | 4 of 7 | no |
| 22 | 860077700 | (0,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.0) | 7 of 7 | yes |
| 23 | 860079600 | (1,0) | yes | VERIFICATION_UNIQUE | EXTENSION_NECESSARY_AND_USED | yes | no (15.7) | 7 of 7 | yes |
| 24 | 860086200 | (0,1) | no | MDL | NOT_SOLVED_WITH_EXTENSION | no | no (24.1) | 0 of 7 | no |
| 25 | 860086800 | (1,1) | no | D | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 3 of 7 | no |
| 26 | 860087100 | (1,0) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 4 of 7 | no |
| 27 | 860088800 | (1,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 4 of 7 | no |
| 28 | 860089300 | (1,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (20.9) | 4 of 7 | no |
| 29 | 860090700 | (0,1) | no | MDL | EXTENSION_NECESSARY_AND_USED | yes | no (24.1) | 7 of 7 | yes |

## The exact blocker

G2 fails: 11 complete witnesses against the 15 required. The binding leg
is L (11 of 30); U and T (25 of 30) fail on the same 5 tasks; B, P and A
hold on all 30.

The proposer itself did not fail. It selected an extension on every task
and in all 208 folds that needed one (the other 2 folds were
K_ALREADY_SOLVES), and its selection was useful at fitter level on 30 of 30
tasks.

Descriptive diagnosis from the rows. This is post-terminal, is not a gate,
reran nothing and changes nothing in the outcome.
1. The losses are engine rejections downstream of the proposer. Of the 81
   failed folds, 79 end with the engine proposing the compiled hypothesis
   and then rejecting it (`HYPOTHESIS_PROPOSED > META_COMPUTED_CANDIDATE_FOUND
   > HYPOTHESIS_REJECTED > NEAR_SOLVED_STORED`); 2 were accepted with a
   wrong held-out output (task 9 fold 6 using e, task 11 fold 5 not using
   e). The 5 full-task rejections show the same event pattern.
2. In 77 of the 81 failed folds the fold rebuilt exactly the same extension
   (same serialized program) as the full task. On the 14 tasks where the
   engine accepted the full-task extension but some folds failed, 43 of the
   46 failed folds carried the same program and were rejected: the same
   program was accepted with seven training pairs and rejected with six.
3. The losses concentrate where several verified extensions survived
   deduplication and selection fell to D or the MDL guess. Fold success:
   31 of 34 when the verified candidate was unique, 6 of 6 under P0, 24 of
   42 under D, 66 of 126 under MDL.
4. Family (1,1) carries most of the loss: 2 witnesses in 15 tasks and 50 of
   105 folds, against 9 witnesses in 15 tasks and 77 of 105 folds for the
   other two families.
5. The same pattern appeared once before: in v1.7 the engine accepted
   nothing on 4 of 7 six-pair folds of seed 830000600, attributed then,
   unverified, to the engine's re-induction gate. The engine-internal reason
   for HYPOTHESIS_REJECTED was not examined here and remains open.
6. Load was about twice the development load. The rows cannot separate a
   load effect: accepted and rejected K* + {e} runs took the same time
   (15.6 to 16.0 s), which suggests a fixed budget either way, and folds
   record no timing. Load is recorded and does not gate under the protocol.
7. The G2 power estimate used the development witness rate, 6 of 8 engine
   tasks (0.75). The prospective rate is 11 of 30 (0.37). The development
   engine subset was 8 tasks.

## What this shows and does not show

- Shown prospectively, on synthetic constructive tasks only: choosing top
  layers from the task's own failure frontier gives useful proposals more
  often than the transplant and BLIND controls under the same mechanism and
  caps (13 to 0 and 7 to 0). Usefulness is measured at fitter level on the
  held-out pair. A verifying extension is in the search space by
  construction on this corpus (protocol section 15).
- Not shown: the end-to-end path. Too few produced extensions survive the
  same reasoner's acceptance under leave-one-out with the proposal rebuilt
  in every fold.
- Not a real ARC result. Nothing here touched real ARC data, Step B, the
  protected holdout, VDCG, E_transfer or the lockbox.

## Boundaries held

No redesign, no threshold change, no control change, no tuning, no rerun,
no second writer, no resume. The generator's schema was used only in the
frozen post-arm diagnostics. The real ARC pilot was not started.

NEXT: STOP AND RECORD THE EXACT v1.8 PROSPECTIVE BLOCKER.
