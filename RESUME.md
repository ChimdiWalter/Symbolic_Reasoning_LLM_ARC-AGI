# ARC-2026 delivery sprint: resume

Last updated 2026-09-28. Read this first.

## State

Last updated 2026-10-02.

**v1.5 COMPLETE: FAILURE_ASSOCIATION_NOT_CAUSAL_FOR_SELECTION** (ladder rule 6;
the rule 7 condition also holds), at the full 288 groups.
- Integrity passed; the two sealed evaluator passes are byte-identical; every
  fit converged; no leak, overlap or order dependence.
- D alone 0.591; D+F_ASSOC 0.585 (increment -0.006, 95% CI -0.026 to
  +0.014); against the matched shuffle +0.005 (upper bound 0.025). B and C
  both fail decisively.
- Supplementary: verification UNQUALIFIED (0 errors, 0 mismatches); gate C
  dependence check NOT_SUPPORTED (tier 2 governs).
- Record: `records/ITEM2_V15_SELECTION_RESULT_20261001.md`. Paper sections
  8.10 and 9.3. Ledger: compiler BLOCKED; `v1.5_bounded_repair`
  AUTHORIZED_NOT_DESIGNED.
- Generation: 2,739 slots, ended 2026-10-01T11:57:44Z. Athe rebooted on
  2026-09-30 at slot 2045; the run resumed from its saved records.

**v1.5 frozen with erratum 1** at 216f2c4: protocol
`docs/CORA_TTI_FAILURE_CONDITIONED_SELECTION_v1.5.md` sha256 `e3209c1f...`,
manifest sha256 `0cc4b900...`, 56 tests; records
`records/ITEM2_V15_SELECTION_DESIGN_DECISION.md` (sections 3 to 8 stale, see
addendum) and `records/ITEM2_V15_ERRATUM_01.md`.

**v1.4 COMPLETE: CURRENT_TFG_IDENTIFYING_UNDER_TWINS** (determining stage
S7, confirmatory at 42 unique groups, sealed audit byte-identical, sha256
`1c051401...`). Record: `records/ITEM2_V14_LOCALIZATION_RESULT_20260928.md`.
S7 (42-field descriptor) 190/336 = 0.565 against the exact null 1/2,
binomial p 0.0094, randomization p 0.0017 (Holm 0.0052); S2 0.574, S3 0.592,
S4 0.571 also qualify; S5, S6 do not (90 percent ties); S7a randomization
only; S2 to S5 react far beyond same-input rerun noise; S0 (demonstrations)
0.664 is stronger than every reasoning stage. The erratum-2 continuation
ran slots 136 to 140 (14:21:37Z to 14:29:00Z, PID 2388124), no duplicate
after resume, 42nd group at slot 140. Nothing is running.

**v1.4 ERRATUM 2 FROZEN 2026-09-28 at 5ffa56f.** Record `records/ITEM2_V14_ERRATUM_02.md`;
protocol sha256 `05e3d96b...8723a8eb`, manifest sha256 `1c2202b6...4dbf2aa1`;
58 v1.4 tests pass. Rule: the first admission of a group digest in slot
order is included, later ones are kept but excluded (slot 57 included, slot
117 excluded); the generator skips included pairs before any engine run and
counts unique groups. Resume at slot 136 with 41 included; original caps;
launch deadline 2026-09-28T20:47:49Z. The v1.4 scientific outcome is not
yet measured.

**v1.4 FIRST RUN COMPLETE; SEALED AUDIT = AUDIT_BLOCKED (`duplicate_group_digest`);
NO CLASSIFICATION.** Record: `records/ITEM2_V14_LOCALIZATION_RESULT_20260928.md`.
Generation stopped at 42 admitted groups after 136 slots and 11,791 s with
full freeze, environment, leakage and twin-law integrity, but one target pair
was admitted twice (slots 57 and 117), leaving 41 unique groups, and the
frozen corpus check makes duplicates blocking. The report holds no stage,
sensitivity or classification section: **no v1.4 statistic has been computed
by anyone.** Cause: my erratum-1 defect, a uniqueness check added to the
auditor without the matching skip rule in the generator. Nothing is running.

**v1.4 mechanistic frontier localization: FROZEN WITH ERRATUM 1 at
adecfd2.** Protocol
`docs/CORA_TTI_MECHANISTIC_FRONTIER_LOCALIZATION_v1.4.md` sha256
`26e0c60b...88529077`; manifest
`outputs/tti/mechanistic_frontier_v14_manifest.json` sha256
`22dccf9a...dd3742e`; design record `records/ITEM2_V14_DESIGN_DECISION.md`;
erratum `records/ITEM2_V14_ERRATUM_01.md`. First freeze 50841e3 (protocol
43e798fa, manifest dd481b31) is superseded. 48 v1.4 tests pass. No v1.4
experiment episode exists; no stage statistic has been computed on real
data.

Branch B, counterfactual twins: FEATURE contrasts only, both targets of a
replicate see the same input grids, 4 replicates per group, target A also
rerun on the same input as a timing-noise control, run order balanced over
six permutations, engine caches cleared before every run. Stagewise
twin-excluded nearest neighbour against the exact null 1/2 (3/7 is not exact
under shared inputs); hits break ties by a label-independent hash;
qualification needs hit rate > 1/2 and exact binomial and randomization
p < 0.01. Target 42 groups, floor 14, caps 400 slots or 24 h; the smoke
projects about 2.4 h.

The one pre-run adversarial review is DONE. It found one blocking defect
(ties counted as misses meant coarse stages could never qualify, and an
earlier unresolved stage did not stop a later localization), two major (S6,
S7a and S7 re-score against each target's own outputs; 16 of the engine's 18
`ARC_*` switches were unguarded) and several minor, all corrected before any
episode existed, no threshold changed. No second review round.

Freeze checks cover the protocol, manifest, 11 implementation files, two
grammar-manifest files in Reasoning_Project_tti, runtime versions, and tree
digests of cora_arc2026, geocat_arc and the three packages read from
Reasoning_Project_tti; they are re-verified after every slot. **Any edit to
cora_arc2026 or geocat_arc before or during the run makes the generator
refuse to start or the audit block, by design.**

Repo suite: 112 passed, 1 failed, the pre-existing timing-dependent
`test_observer_state_cannot_leak_between_tasks` (see the design record).

**v1.3 contrastive corpus: COMPLETE, audited, official verdict
V1.3 CONTRASTIVE CORPUS IDENTIFIABILITY GATE FAIL.** Full record:
`records/ITEM2_V13_CORPUS_RESULT_20260926.md`, committed e200e5a with the
audit reports and every corpus record.

Protocol sha256 `66aa1c56...389d8f1e`, manifest sha256 `9492f392...ab56de14`,
calibration `ba82865e...51c7c02` (committed aaa2972 before Phase B), q = 0.025
(committed e9ba44c before the full run), generator 0146e20, auditor 4a6efd8
plus erratum-2 correction 94c159a. Three errata, all recorded.

Full run 1,200 of 1,200 slots, 21 groups admitted (FEATURE 14, SELECT 7,
PARTITION 0), 168 episodes, 41 distinct targets. G1 hit rate 0.470 (79 of 168)
against the exact null 3/7, p = 0.156; G2 0.473, p = 0.195; median
separation 0.025. G1 to G7 FAIL, G8 to G10 PASS. The auditor was run twice and
the reports are byte-identical. The one-sided 95 percent upper bound on the
hit rate is 0.537, so the planned effect of 0.55 is excluded; a small effect
is not.

Interpretation, case B: identifiability is not established, and the failure
is primarily identifiability, with scale failing in addition. Do not fit a
scorer. The ConstructiveExtensionCompiler stays BLOCKED.

Standing evidence, unchanged: v1.2 corpus PASSED all 11 gates. v1.2 scorer
FAILURE_CONDITIONING_NOT_ESTABLISHED. Diagnosis
CANDIDATE_SIGNAL_REDUNDANT_ON_V12, with the qualifier that no evidence group
recovered the target. Proposer earns NEW_AST_GENERATION only.

## Do not redo

- The failure-signal study (no evidence / aggregate / associated / shuffled).
  Already run; result recorded and now explained.
- The feature inventory. See `records/IMPLEMENTATION_MATRIX_CORRECTED_20260923.md`.

## Proposer built, and half its claim is earned

`cora_arc2026/constructive_proposer.py` implements
`propose_ast(tfg, interface, k)`. 14 of 14 frozen controls pass. On five
prospectively fixed real failures it emits 25 legal complete ASTs, all absent
from K, in about 0.03 s per task.

EARNED: new-AST generation from a real typed failure graph.
NOT EARNED: failure conditioning on real data. All five tasks share the same
rank-one candidate and four of five produce an identical list, although their
evidence differs substantially. The unfitted evidence prior saturates.
Nothing was tuned after seeing this. Full record:
`records/PROPOSER_BLOCK_20260923.md`.

## The scorer fit is BLOCKED

Attempted and stopped. Full record: `records/SCORER_FIT_BLOCKED_20260923.md`.

There is no corpus of informative-failure-graph to target-AST pairs, and none
can be produced under the frozen v1.1 admission law.

1. The v1.1 pilot generated all 60 slots on 2026-09-04 and admitted ZERO of
   1,500 attempted targets. Its own recorded root cause is structural: R4 and
   R5 are mutually exclusive, because the sole registered slot learner and the
   fixed base search enumerate the same 200-triple product. Of 266 family-(2,)
   targets passing R5, 262 were base-search-solved. A second recorded blocker
   kills families with no Select stage, which includes two frozen train
   families.
2. The only verified admitted episodes, the 13 in the corrected v2 census,
   each contain ZERO frontier_term nodes. They came from the proxy runtime,
   which is the exact defect repaired earlier. They are also protocol v2 with
   no recorded protocol hash, and 13 is far too few. The reconstruction
   directories were audited and downgraded earlier and are not evidence.

Real ARC failures now give informative graphs but carry no target AST, and no
hidden answer may be read to supply one.

## Next action, exactly one

**v1.6 bounded repair: DEVELOPMENT BLOCK IN PROGRESS (2026-10-02).** Plan
and amendment: `records/ITEM2_V16_DEVELOPMENT_PLAN.md` (3bcb8e7, 788cfc3),
both fixed before any response was read.
- Implementation so far: `cora_arc2026/v16_cfr.py` (probe, queries, R0-R2,
  shuffle, conditional logit; its D-only fit reproduces v1.5 `fit_pairs`
  exactly), `scripts/v16_responses.py`, `scripts/v16_dev_evaluate.py`,
  `scripts/v16_build_exclusion.py` (exclusion written: 2,094 targets,
  2,430 groups, sha256 e936bc6f...), `scripts/generate_v16_pairs.py`
  (v1.5 generator with v1.6 paths, seed base 500,000,000).
- Running: `scripts/v16_responses.py dev` (detached, log
  `logs/v16/dev_responses.log`) writes `outputs/tti/v16_dev_responses.json`.
- Then, in order: add P0/P1/P2 arms and controls to the dev evaluator; run
  it (DEVELOPMENT ONLY, v1.5 test corpus); record the development result;
  write the v1.6 protocol, manifest, evaluator, tests, power calculation,
  restart tooling; hash and freeze; ONE adversarial review; errata; STOP
  before generating prospective data.
- Paper track (parallel, safe): `docs/RELATED_WORK_NOVELTY_MATRIX.md`,
  claim ladder and method section in `docs/PAPER_SKELETON.md`.
- Deadlines corrected per the user: Kaggle entry 26 Oct, competition 2 Nov,
  paper 8 Nov 2026.

## How to re-run

    export PYTHONDONTWRITEBYTECODE=1 ARC_META_BUDGET_S=8
    .venv_arc2026/bin/python scripts/audit_failure_frontier_v2.py
    .venv_arc2026/bin/python -m pytest tests/ -q

Single process, `nice -n 19`, so it cannot compete with Step B's 20 workers.

`.venv_arc2026` is this sprint's own interpreter prefix. It reads packages
from the shared environment through a path file and can never install into
it, so the live experiment's environment stays unwritable from here.

## Boundaries held this block

No scoring, no test outputs, no HOLDOUT, no E_transfer, no Lockbox, no
Step-B output, no proposal, no install, no K modification, no GPN training,
no ablation. Step B untouched.
