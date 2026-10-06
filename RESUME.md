# ARC-2026 delivery sprint: resume

Last updated 2026-09-28. Read this first.

## State

Last updated 2026-10-06. Current: v1.9 engine acceptance stability audit, development diagnosis running (see "Next action"); v1.8 prospective FAILURE_SPECIFIC_BUT_NOT_END_TO_END.

**v1.6 COMPLETE: PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES** (ladder
rule 3; hybrid headline). Record: `records/ITEM2_V16_CFR_RESULT_20261005.md`.
- 201 groups (slot cap), 657 verification-ambiguous queries in 136 groups
  (below the 280 target; a pass stands at the 72 floor), 65 unseen-pair
  ambiguous groups.
- P0_then_D 0.641 against D 0.580: +0.061 (95% CI 0.029 to 0.093, p 3.8e-5);
  over its replaced-failure control +0.037 (p 0.0069); unseen pairs +0.082.
  P0 alone 0.574 (abstains 80 percent; 86.5 percent right when it decides);
  P1 0.597 and P2 0.578 do not pass.
- Terminal verification 71/71; reports byte-identical; dependence-aware C
  UNRESOLVED (supplementary). Compiler LICENSED, not started.

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

**v1.9 ENGINE ACCEPTANCE STABILITY: DIAGNOSIS DONE, REPAIR BUILT, DEV ABLATION RUNNING**
(user directive 2026-10-06; diagnosis -> ONE generic repair -> tests ->
freeze -> ONE review -> errata; STOP before the v1.9 prospective test).
- DIAGNOSIS (d9b4479, `records/ITEM2_V19_AUDIT_DIAGNOSIS.md`): success
  condition PASS (145/145 events mechanistic and reproducing in process and
  in a fresh process; traced == untraced 12/12). Dominant mechanism H1
  re-induction instability 145/145: SLOT_FIT_FAILED:witness 86 (K*-2
  fitter's MIN_KEY_WITNESSES=2 re-applied inside the engine's five-pair
  refits), RANKED_BELOW_COMPETITOR 59 (pixel-rule reductions labelled
  RELATIONAL with unpriced tables outrank e). Load and budget eliminated
  (CPU1 and CPU10: 0/18 decisions changed each); H4 0/30.
- REPAIR K*-4 installed-extension re-induction (`cora_arc2026/v19_repair.py`,
  protocol sections 14-15, 1e5937e): while an extension is installed, the
  installed concept is fitted with every consistent witness and ranks first
  in every ranking; gate unchanged; inert with nothing installed. Tests
  `tests/test_v19_repair.py` 6 fast + 3 engine pass.
- RUNNING (detached, survive session restarts; rows written per task):
  (a) dev ablation pipeline pid 1546874 (4 workers), marker
  `logs/v19/REPAIR_DEV_DONE`, report `outputs/tti/v19_repair_dev_report.json`,
  restart `setsid nohup bash logs/v19/run_repair_dev.sh`;
  (b) reduced-demonstration false-acceptance measurement: DONE (dc9da93);
  clause-level follow-up DONE (6d77189);
  (c) WATCHER `logs/v19/v19_watch.sh` pid 1603534 (lock
  `logs/v19/v19_watch.lock`, log `logs/v19/v19_watch.log`): relaunches (a)
  or (b) if gone before its marker (3 restarts max each), writes
  `logs/v19/V19_DEV_ALL_DONE` when both markers exist, then removes its
  `@reboot` crontab hook (installed 2026-10-06, `sleep 300`; crontab backup
  in the session scratchpad `crontab_before_v19.txt`, 22 lines). No git
  operations in the watcher.
- FALSE-ACCEPTANCE FINDING (dev; dc9da93, 6d77189; protocol section 15a,
  4af2bd1): with seven demonstrations no wrong verified extension exists
  (0/30 tasks, both rules). With four demonstrations (train 0-3, evaluate
  4-6 + held-out): K* accepts 8/24 right and 6/19 wrong installed
  extensions, K*' 24/24 and 19/19; fit-only 13/24 and 9/19; rank-only
  17/24 and 10/19. The engine's internal gate does NOT discriminate right
  from wrong installed extensions under scarce demonstrations in any
  variant; old rejections were indiscriminate. Decision: keep K*-4 (both
  clauses); prospective G4 gates wrong certified outputs at three system
  levels (selected FULL, adaptive-LOO folds, seven-pair wrong trials,
  strict K*' <= K*); the four-demonstration control is run and REPORTED
  with a pre-registered expectation, not gated; claim ceiling carries the
  real-ARC caveat (correctness rests on the proposer's selection and the
  held-out / adaptive-LOO checks). The 86 fitting events are H1 only under
  the one-witness standard (H2 under the fitter's two-witness standard):
  state this in the diagnosis record.
- Early ablation rows (dev): 57/57 old-accepted runs keep the identical
  program under K*'; 0 residual K*' rejections; category-A adaptive LOO
  3/7 and 2/7 -> 7/7.
- AFTER both markers, in order: (1) commit all v1.9 dev outputs (force-add
  outputs/ and logs/); (2) MOVE cora_arc2026/v19_{trace,audit,repair}.py to
  a new package cora_v19/ (they broke v1.8's pinned cora_arc2026 tree
  digest; without them it matches 9032ec17 exactly), fix imports in
  cora_v19/v19_audit.py, scripts/v19_audit_dev.py, scripts/v19_repair_dev.py,
  tests/test_v19_audit.py, tests/test_v19_repair.py; rerun all v1.9 tests;
  (3) decide the prospective false-acceptance control from (b); (4)
  `scripts/v19_feasibility.py` -> N/W/DELTA into `scripts/v19_prospective.py`;
  (5) records ITEM2_V19_REPAIR_DEVELOPMENT.md + ITEM2_V19_FEASIBILITY.md;
  (6) `scripts/freeze_v19.py`; commit; (7) ONE adversarial review (request
  record, tracked-hash snapshot, scan its tool inputs); errata; re-freeze;
  STOP before the prospective test.
- Development range 870M + 100k; prospective 880M + 100k RESERVED.

**STOPPED: v1.8 PROSPECTIVE = FAILURE_SPECIFIC_BUT_NOT_END_TO_END** (run once
2026-10-06, 5,911.6 s; record `records/ITEM2_V18_PROSPECTIVE_RESULT_20261006.md`;
paper section 8.13). The exact blocker is recorded there. Nothing further runs
until the user chooses the next block; the closed loop, the real ARC pilot,
the 1000 tasks and the protected 120 stay BLOCKED.
- Terminal verification `logs/v18/verify_prospective.json`: 31/31 checks,
  every recomputed value equals the report; no leakage, no resume, one
  writer; corpus law re-derived (30 distinct tasks, outside the 3,817
  exclusion digests).
- G1 PASS: main 30/30 useful; transplant 17/30 (13:0, p 1.22e-4); BLIND
  23/30 (7:0, p 0.0078).
- G2 FAIL: 11 of 30 complete witnesses (15 required). Legs B 30, P 30,
  U 25, L 11, T 25, A 30 (3x K* accepted 0/30).
- Blocker: leg L, then U/T on 5 tasks. The proposer selected in every task
  and fold; the engine rejected the proposed hypothesis in 79 of 81 failed
  folds; 77 of the 81 carried the same program as the full task, and on 14
  tasks that program was accepted with seven pairs and rejected with six.
  Losses concentrate on D/MDL-decided selections
  and family (1,1). The engine-internal reason is not examined.
- Claim stays LEVEL 1; LEVEL 2 not reached; real ARC pilot NOT licensed.
- The watcher finished and removed its `@reboot` hook; the crontab equals the
  pre-v1.8 backup. No process from this block is running.

NEXT: STOP AND RECORD THE EXACT v1.8 PROSPECTIVE BLOCKER (recorded
2026-10-06).

**v1.8 NO-ORACLE EXTENSION PROPOSER: DONE (design, implementation,
development audit, freeze, ONE review, erratum 01, re-freeze)** (2026-10-06).
- RE-FROZEN at b69b770: manifest `outputs/tti/no_oracle_proposer_v18_manifest.json`
  sha256 d64732cf54f91f70ce6f7be041956850d6cc85ca3986e4e08199401278db8731;
  protocol 59e0889f; proposer 8fbb0801; K* b009a9fb; v1.7 compiler unchanged
  (04c6b3a1); frozen D b0ae3eca; 33 pinned files. First freeze e7afc0f
  (bd657faa) superseded.
- Review `records/ITEM2_V18_REVIEW_RESULT.md` (b98bd24): 1 BLOCKING (both
  G1 controls could not propose), 2 MAJOR (undisclosed leave-one-out
  conditioning; S6 unfailable), 18 MINOR; access clean except a name-only
  `find` in geocat_arc diagnostics (disclosed). Erratum
  `records/ITEM2_V18_ERRATUM_01.md`: transplant and BLIND controls that keep
  the mechanism; witness leg A = K* at 3x budget; leakage overrides; resume
  policy; disclosures. The erratum itself was not re-reviewed (one review).
- Development (DEVELOPMENT ONLY): useful FC 40/40, transplant 26/40, BLIND
  30/40, NO_RESPONSE 40/40, PURE 10/40, old sanity arms 0/40; engine subset
  8/8 necessary and held-out exact, real LOO all folds 6/8, witnesses 6/8
  (3x K* accepted 0/8); selection = generator's behaviour 19/40.
- Prospective test frozen, NOT run: seeds 860M, N=30, W=15, G1 sign tests
  vs transplant and BLIND (power 0.99 and 0.90 at development rates, 0.48
  if the advantage shrinks to 15 percent; size 0.016), G2 15/30 witnesses.
- Claim ceiling: engineering evidence only until the prospective test; a
  prospective acceptance is LEVEL 2 for the synthetic domain, never a real
  ARC result; completeness by construction, corpus leave-one-out
  conditioning and S6-descriptive-only are disclosed.

Earlier: NEXT: DESIGN AND FREEZE THE NO-ORACLE EXTENSION PROPOSER (now
in progress above).

**v1.7 COMPILER: COMPILER_ACCEPTED** (2026-10-05, run once, 882.9 s;
record `records/ITEM2_V17_COMPILER_RESULT_20261005.md`; paper section
8.12).
- S1 to S6 all hold. S4: 6 of 6 tasks EXTENSION_NECESSARY_AND_USED with
  the held-out pair exact. S5: 5 of 6 (seed 830000600: the engine accepted
  nothing on 4 of 7 six-pair folds; no misattribution). S6: 6 of 6 but
  every comparison set empty, so weak.
- K* at 3x budget accepted none of the six. Residue, direct-execution
  disagreements, label anomalies, nested uses: all 0.
- Report sha256 4b356a8d, rows 8d9323fb. Independent verification
  `logs/v17/verify_acceptance.log`: 11 of 11 checks, including the fixture
  set re-derived identically under PYTHONHASHSEED=0.
- Proposer stage notes: the L leg becomes out-of-sample only when the
  proposer chooses inside each fold; record fold events; keep the K*
  environment law; S6 needs non-empty comparison sets to mean more.

History of the block, superseded by the result above:

**v1.7 GENERIC CONSTRUCTIVE EXTENSION COMPILER: REVIEW DONE, ERRATUM 01
APPLIED, RE-FREEZE THEN ACCEPTANCE ONCE** (2026-10-05).
- Review: `records/ITEM2_V17_REVIEW_RESULT.md` (9195641). 2 BLOCKING, 4
  MAJOR, 12 MINOR. Access audit clean; tracked hashes identical before and
  after.
- Erratum: `records/ITEM2_V17_ERRATUM_01.md`. kstar() enforces the K*
  environment; load() rebuilds from the body and requires identical bytes;
  external files pinned; run-once guard, start record, rows,
  NO_VERDICT_RUN_ERROR; per-arm seconds and load; supplementary 3x K* arm;
  S5 caveat; whole-tree residue and label anomalies in S3.
- RE-FROZEN at 4a9f7fa: manifest
  a66e149cf7d971ae4166033c95cfe2567a9be5ea160c792b9abecca9d08b1f29,
  protocol e9bb1acc, compiler 04c6b3a1, K* identity b009a9fb. Fast 36
  passed; engine 5 passed (203.5 s); amended dev dry run passed every path
  (142 s); `main()` mock test passed every outcome path.
- NEXT: launch `scripts/run_v17_acceptance.sh` ONCE (detached; about 20 to
  30 minutes; writes logs/v17/acceptance.pid, logs/v17/acceptance_start.json,
  outputs/tti/v17_acceptance_rows.jsonl, then the report and
  logs/V17_ACCEPTANCE_DONE). If interrupted before the marker: do NOT
  relaunch silently; the guard refuses; record what happened and decide by
  erratum.

First freeze (superseded by the re-freeze) at d5b5e1b:
- manifest `outputs/tti/constructive_extension_compiler_v17_manifest.json`,
  sha256 418ee5c2f0e1ae30e43cdcf48de2c9faf1f55a5dfaaa566443f0b7437531bbb3;
- protocol bcecb81e70dfb4ac9bf9e9fdf9182b435ca57c89d56ed5598b1e5712a80ce8d7;
- compiler 999a0b9d; K* identity 2fe279a1;
- tests at freeze: fast 33 passed; engine 4 passed (181.9 s);
- dry run of the acceptance path on development fixture 0
  (`logs/v17/acceptance_dryrun_dev.log`): every path passed in 126 s; the
  witness comparison set was empty (protocol section 12 says what that
  means).

Steps 1 to 4 below are DONE. Now: step 5 (ONE adversarial review, request
`records/ITEM2_V17_REVIEW_REQUEST.md`), errata before the acceptance test,
then `scripts/v17_acceptance.py` once (seed range 830,000,000, never used
before), then the result record.

Design record: `records/ITEM2_V17_COMPILER_DESIGN.md` (fc0e37e).

Findings from the engine source:
- the engine's concept route is dormant (the inducer passes no concepts);
- its slot learner fits single-block, single-Select schemas only;
- its expression phase is starved: zero hypotheses on tasks where the
  object search uses the whole budget.

K* (both arms) = the unchanged engine plus:
- K*-1: expression phase gets its declared 8 s slice. This changes the
  baseline relative to v23.
- K*-2: occurrence-scoped fitting for non-engine shapes (inert for K).
- K*-3: context-scoped overlay of installed productions (inert when empty).

Feasibility on fixtures (seeds 810000100 and 810004800; prototype
`logs/v17/feas4.py`): K* alone fails; K* + extension is accepted by the
unchanged gate, the winner carries the extension, and the held-out
demonstration is exact.

Remaining in this block:
1. `cora_arc2026/v17_compiler.py` (closed input schema, typing law,
   canonical serialization, `kstar()` and `install()` overlays with state
   snapshots, `uses_extension`, `run_reasoner`, `paired_ablation`,
   `adaptive_loo`, `witness_separation`);
2. `tests/test_v17_compiler.py` (the 15 required properties plus
   metamorphic tests and real-engine integration on the fixtures);
3. protocol `docs/CORA_TTI_CONSTRUCTIVE_EXTENSION_COMPILER_v1.7.md`;
4. manifest and freeze;
5. ONE adversarial review, errata, re-freeze;
6. then return with: NEXT: DESIGN AND FREEZE THE NO-ORACLE EXTENSION
   PROPOSER.

Do not begin the proposer in this block.

## How to re-run

v1.7 compiler. Every engine run and the synthetic fixtures need the K*
environment: PYTHONHASHSEED=0 and no ARC_* variable (`kstar()` sets its own
pair and refuses otherwise; the fixture colour tables use Python's salted
string hash).

    export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
    export PYTHONPATH=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
    .venv_arc2026/bin/python -m pytest tests/test_v17_compiler.py -q -p no:cacheprovider -m "not engine"
    .venv_arc2026/bin/python -m pytest tests/test_v17_compiler.py -q -p no:cacheprovider -m engine
    scripts/run_v17_acceptance.sh      # once only; refuses a second start

The engine is deadline-bound, so engine runs are a single process at
default priority (not `nice -n 19`, which would starve the K* arm and bias
the ablation toward EXTENSION_NECESSARY_AND_USED); load is recorded.

Older blocks:

    export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 ARC_META_BUDGET_S=8
    .venv_arc2026/bin/python scripts/audit_failure_frontier_v2.py
    .venv_arc2026/bin/python -m pytest tests/ -q

Those were single-process `nice -n 19` runs beside Step B's 20 workers.

`.venv_arc2026` is this sprint's own interpreter prefix. It reads packages
from the shared environment through a path file and can never install into
it, so the live experiment's environment stays unwritable from here.

## Boundaries held this block

No scoring, no test outputs, no HOLDOUT, no E_transfer, no Lockbox, no
Step-B output, no proposal, no install, no K modification, no GPN training,
no ablation. Step B untouched.
