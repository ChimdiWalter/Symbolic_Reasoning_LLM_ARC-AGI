# ARC-2026 delivery sprint: resume

Last updated 2026-09-28. Read this first.

## State

**RESUME HERE (2026-10-14 ~20:30Z; session ended near the usage limit).** The sprint directive in force is
"OCTOBER 23 SURGICAL BREAKTHROUGH AND MIT DEMO SPRINT" (items A-K).

DONE and committed (latest 2c52517):
- FHR dev v2: records/CORA_FHR_DEV_RESULTS_20261014.md.
  - Witness dev_D3_04 audited (outputs/cora_fhr/witness_dev_D3_04.json): reproduced, replay exact, restored,
    ablation, perturbation novelty (native 7/300, best reach 8/300). E = C = C' all correct.
- C' implemented and the C'-vs-E audit done: E = C' on D1 and D3 by construction, so H3 cannot be tested on C4.
- Demo bundle docs/summit_demo_20261023/ (run_demo.sh, offline hash-checked replay, 90-second script).
- Figure docs/summit_poster/figures/fig_fhr_witness_dev_D3_04.png (built, but NOT yet placed on the poster).
- Kaggle originality audit: records/KAGGLE_NEURAL_V1_ORIGINALITY_AUDIT_20261014.md.
- Transfer documents: docs/CORA_REPAIR_VERIFY_CONTRACT_v1.md, docs/STARTUP_HYPOTHESIS_20261014.md.
- Tests: tests/test_fhr.py, 13 pass.

RUNNING, detached:
- outputs/cora_fhr/gate_queue_v2.sh (log gate_queue_v2.log): B done, then the funnel asset audit (dev60
  native_assets), then the refold what-if (ungated folds).
- outputs/cora_fhr/followup_c2.sh: waits for QUEUE DONE, then runs arm C' on dev v2 (rows_c4_dev_v2_C2.jsonl).

NEXT:
1. Read the queue's outputs:
   - outputs/cora_fhr/eval_v2_B.out;
   - outputs/funnel_v0/eval_assets.out: compare with eval_dev60_native.json; if the funnel numbers change, correct
     the funnel record, paper and poster;
   - outputs/cora_fhr/eval_v2_refold.out;
   - outputs/cora_fhr/eval_v2_C2.out.
   Then run `python -m cora_fhr.dev_table --corpus c4_dev_v2` for the compact per-family table.
2. Write Amendment 2 into the protocol (dated). Decision basis:
   - in v2 the nested native acceptance never failed a fold; the fold-level tie check is the blocker
     (without it: E 4 / C 3 NEW_COMPOSITION correct, 0 wrong);
   - the D-control fixes: cross-family donors, fold-symmetric evidence;
   - C' as the H3 control;
   - H3 needs mixed-coverage families.
   The user decides whether to adopt it.
3. Poster:
   - retitle "When Search Is Not Enough: Diagnosing Reasoning Failures and Constructing Verifiable Executable
     Capabilities";
   - replace the PROPOSED block with "CORA-FHR (implemented; synthetic development)", using the witness figure and
     the honest E = C caveat;
   - rebuild; poster_to_pptx; update abstract, explainer and paper section 8.20; evidence record section 16.
4. GO/NO-GO = NO-GO. Failing gate: a fair failure-evidence comparison (E = C' by design on C4). The final split
   stays sealed.
5. Kaggle 57160429 was still PENDING; check outputs/kaggle_deploy/neural_v1_official_score.json.

OCTOBER 23 SPRINT (user directive 2026-10-13 "October 23 research breakthrough sprint"; resume here):
- **Kaggle.**
  - **NEURAL SUBMITTED: 57160429** (2026-10-14 00:08Z, NEURAL_TTT_BASELINE), status PENDING. The watcher
    writes the score to outputs/kaggle_deploy/neural_v1_official_score.json.
    Record it in KAGGLE_NEURAL_V1_LOG section 12, then update the paper, poster and abstract (neural label only).
  - The neural run `chimdiwalter/cora-neural-ttt-baseline-v1` v1 is COMPLETE and AUDITED (20:56Z):
    - 240/240 tasks decoded; 259/259 genuine attempt_1; 0 fallback; schema 0; 4.34 h;
    - every gate passes except today's slot, so the watcher submits ONCE after 00:00Z
      (records/KAGGLE_NEURAL_V1_LOG_20261013.md section 10).
  - The watcher was replaced at 19:05Z with the gate fix (25b346e); its pid is in
    outputs/kaggle_deploy/detached_watch.pid.
  - It submits ONCE as NEURAL_TTT_BASELINE, and only if every gate passes. New gates: fallback
    at most 10%; decoded outputs for at least 90% of tasks.
  - The score goes to outputs/kaggle_deploy/neural_v1_official_score.json.
  - Native 57144804 = 0.00. Today's slot was used by native; the next opens after 00:00Z.
- **Failure funnel** (cora_funnel/, ed3d0fd and 7485f00).
  - The detached driver (outputs/funnel_v0/driver.pid; status driver_status.json) waits for the
    ceiling test (pid 3683607).
  - Then it runs: dev60 native, c3dev, the dev60 oracle, dev60 at budget x3, then c2dev and its
    oracle.
  - Outputs: outputs/funnel_v0/eval_*.json and oracle_*.json.
  - It is resumable: if killed, rerun the command in cora_funnel/driver.py.
  - The report to write: records/CORA_FAILURE_FUNNEL_20261014.md.
- **Ceiling test DONE** (records/HYBRID_CEILING_C2DEV_RESULT_20261013.md; SYNTHETIC, oracle-assisted):
  - native 31/60; answer-given 50/60;
  - 19 tasks reached only with the answer; 10 not reached even with it.
- **C2 CORA_ONLY scored** (records/C2_CORA_ONLY_SCORE_20261013.md, c699cb9; SYNTHETIC): 47/120 exact.
  - 53 of the 100 tasks some layer claimed are wrong.
  - attempt_1 = the first claiming layer, pipeline first. Pipeline-only claims are right 1/38.
  - The driver was restarted at 20:52Z (pid in outputs/funnel_v0/driver.pid; 824d89d):
    - object-layer deadlines now run on process CPU time (the host is 2x oversubscribed);
    - order: dev60, dev60 whole harness, dev60 oracle, c3dev, dev60 budget x3 on deadline-hit tasks, c2dev.
- **CORA-RG.** Adapter v1 committed (6271ffe). The C3 v1 corpus and the choice of intervention wait
  for the funnel (Oct 16).
- **Bio one-pager:** docs/BIO_TRANSFER_PROPOSAL_20261013.md (UNTESTED).
- **Native defects masquerade as perception failures.** dev60 task k35aabb2676c4 raises KeyError('window')
  inside native's search in every frame; native reports it as a segmentation failure. The funnel now records
  such exceptions, under category NATIVE_ERROR (0f2d209).
- **FUNNEL dev60 object layer DONE** (records/CORA_FAILURE_FUNNEL_20261014.md, 81ecf25; DEVELOPMENT):
  - 35/60 tasks have train-exact candidates; LOO certified 6, all correct, 0 false acceptances;
  - correct-but-rejected 2; FIT_BUT_ALL_WRONG 27; no fit 22 (17 stop at object matching); 3 native defects;
  - gate-off counterfactual: 8 right, 26 wrong;
  - so certification is NOT the bottleneck; generating a generalizing hypothesis is.
  - The harness, oracle and budget sections are pending; the driver is on the whole harness (22:12Z).
- **CORA-FHR v1 IMPLEMENTED (Step 2 authorized 2026-10-14; development only; final split SEALED):**
  - code cora_fhr/ (ggrow, baseline, construct, bridge, measure, corpus_c4, evaluate); 12 tests pass
    (tests/test_fhr.py); commits d0cdcfb, 128c563.
  - Amendment 1 is in the protocol: fair object access for C, tie abstention after acceptance on grown objects,
    common commit rule, F3 -> F5 by the calibration rule, engine assets, label order, f_B provisional 3.0,
    identifiability of G samples.
  - Dev split C4: 27 tasks, sha 4af56bb2 (outputs/cora_fhr/c4_dev.json).
  - Smoke on 2 tasks:
    - dev_D1_00: native fails, the authentic evidence yields ray(S,border)[edge:S] (NEW_COMPOSITION),
      abstained on a tie;
    - dev_D2_00: native's memorized instances are misattributed (1 of 9 matches the truth), NO_PROPOSAL.
  - DEV RUN v1 DONE (63f33e9; DEVELOPMENT):
    - A certifies 0 of 27: a corpus artifact, since distractors in only some demos break native's LOO;
    - no construction arm certifies;
    - 48 folds ran installed extensions end to end, 17 SUCCESS;
    - failing folds are mostly native non-acceptance on 2 demos (adaptive LOO nests native's own LOO);
    - f_B = 1.55.
    Generator v2 (per-task distractors; Amendment 1 item 10): dev split v2, sha d5bab8e4; A certifies 3 of 3 N0.
    Integrity-gate queue detached (outputs/cora_fhr/gate_queue.log): B on the dev G tasks, the funnel asset audit
    (dev60 native_assets), and a refold what-if with ungated folds (proposed Amendment 2; DEVELOPMENT only).
    NEXT: dev v2 run (A,C,D,E). The user decides the fold semantics (Amendment 2) before any freeze.
  - DEV RUN v1 (arms A,C,D,E; outputs/cora_fhr/rows_c4_dev.jsonl; log outputs/cora_fhr/dev_run.log):
    evaluate with `python -m cora_fhr.evaluate --corpus c4_dev`. Then run B on the dev G tasks, set f_B, freeze.
    The final run needs the user's separate go-ahead.
- **CORA-FHR v1 PROTOCOL FROZEN (specification only; Step 1 authorized by the user 2026-10-14):**
  - files: records/CORA_FHR_PROTOCOL_20261014.md, docs/CORA_FHR_GGROW_v1.md,
    records/cora_fhr_v1_frozen_parameters.json.
  - Capability: a derived growth operator composed from the G-grow grammar (10 sources, 50 transforms,
    depth <= 2 or same-source unions; 37,750 expressions; no cell literals).
  - Trigger: native fails AND detect_grow memorized a constant pattern in >= 2 demonstrations.
  - Arms: A frozen, B matched search, C failure-blind, D shuffled, E authentic. Native acceptance and
    adaptive LOO decide.
  - Final corpus: C4, 80 synthetic tasks; held-out G families F1-F4 rejected if baseline-explainable.
  - Pass rules: P1-P7 (P1 >= 8 NEW_COMPOSITION gains in >= 2 families; P3 E beats C by >= 3; 0 harms).
  - NOT implemented and NOT run. Next: implementation steps 1-8 (Oct 15-16), dev run and freeze (Oct 17),
    final run (Oct 18-19). The final run needs the user's go-ahead.
- **FUNNEL EVIDENCE COMPLETE (Oct 14, 9c58af8): VERDICT** in records/CORA_FAILURE_FUNNEL_20261014.md.
  - Real-ARC failure = rule induction by MEMORIZATION:
    - constant-parameter GROW cell patterns in 19/25 analysable FIT_BUT_ALL_WRONG tasks;
    - failed folds rebuild different constant structures (59/74);
    - native phase C (force_relational) returns 0 programs;
    - budget x3: 0 robust gains;
    - frozen cora_reach growth grammar covers 5/27.
  - The oracle's 'expressible' mostly = memorizing one more case.
  - Recommended ONE intervention (NOT implemented; awaiting the user's go-ahead):
    failure-conditioned construction of a derived GROW pattern operator (CORA-FHR with a bounded typed
    operation extension), with matched-search, failure-blind and shuffled controls.
  - Arbitration replicates on C2-dev: +5/+8, 0 lost (engineering only).
- **ORACLE dev60 COMPLETE** (00:44Z Oct 14; records/CORA_FAILURE_FUNNEL_20261014.md):
  - FIT_BUT_ALL_WRONG: 26/27 expressible with the answer added; 24 of 26 in the SAME frame and view as
    the spurious fit;
  - no-fit tasks: 0/22 helped (10 no fit within bounds, 12 undetermined);
  - this points to rule-level hypothesis revision (CORA-FHR), not new representations.
  - The contrast job (cora_funnel/contrast_driver.py, pid in outputs/funnel_v0/contrast_driver.pid) is
    queued after the phase-1 driver; the driver is now on c3dev, then budget x3, then c2dev.
  - Do NOT implement FHR before the contrast data are in.
- **ARBITRATION SHADOW** (cora_funnel/arbitration_shadow.py, 93a7d10; DEVELOPMENT; saved predictions only):
  - frozen precedence 12/60;
  - object-certificate-first, the conservative attempt_2 override and complementarity: 14/60 each
    (+2, 0 lost);
  - an engineering result, not capability growth; replicate on c2dev when the funnel's c2dev rows exist.
- **NEXT-SESSION CHECKLIST (state at 21:00Z, Oct 13):**
  1. **Neural.** After 00:00Z the watcher submits ONCE, then writes
     outputs/kaggle_deploy/neural_v1_official_score.json. Record the score in
     records/KAGGLE_NEURAL_V1_LOG_20261013.md section 11, labelled NEURAL_TTT_BASELINE (an NVARC reproduction,
     not CORA). Then update the paper, poster and abstract.
  2. **Funnel.** The running driver loaded cora_funnel/evaluate.py BEFORE the NATIVE_ERROR fix. So after each
     driver evaluation, re-run `python -m cora_funnel.evaluate --corpus <c> [--mode budget3]`. Then write
     records/CORA_FAILURE_FUNNEL_20261014.md from eval_dev60_native.json, eval_dev60_harness.json and
     oracle_dev60.json.
  3. **Oct 16.** Choose ONE intervention from the funnel, then freeze one prospective experiment.
- **NEXT.** When phase 1 ends, write the funnel report and choose ONE intervention by Oct 16. Then
  freeze, run one prospective experiment (Oct 17-19), and freeze the summit evidence on Oct 21.

CORA REP GROWTH (user directive 2026-10-13 'architectural autonomy audit and failure-driven representation growth'): phase 1-2 audit COMPLETE (records/CORA_AUTONOMY_AUDIT_20261013.md: native = L0/L1; representation synthesis ABSENT; L3 missing); then records/CORA_AUTONOMY_AUDIT_20261013.md (levels L0-L5), records/CORA_REP_GROWTH_PLAN_20261013.md (cora_rep_growth/: typed representation grammar, failure-conditioned vs failure-blind constructor, arms A-E, fold-local regeneration), one frozen CPU synthetic experiment, decision label. Do not touch native v23, Kaggle, C2, Step B, VDCG.

DETACHED WATCHER (2026-10-13T17:10Z): `kaggle/ops/detached_watch.py` runs under setsid (pid in outputs/kaggle_deploy/detached_watch.pid; log outputs/kaggle_deploy/detached_watch.log; status outputs/kaggle_deploy/detached_status.json; it refuses a second copy). It records the native score (outputs/kaggle_deploy/native_v1/official_score.json); when the full neural run completes it downloads outputs to outputs/kaggle_deploy/neural_v1_full_run1/, runs the coverage audit, and submits ONCE as NEURAL_TTT_BASELINE only if all gates pass (else NEURAL_BLOCKED with reasons), then records that score (outputs/kaggle_deploy/neural_v1_official_score.json); it notes C2 completion. On resume: read the status file first; do not submit by hand if stage is 'submitted' or 'scored'; stop it with `kill $(cat outputs/kaggle_deploy/detached_watch.pid)`. C2 CORA_ONLY runs detached (orphaned to init, own session). HYBRID CEILING TEST queued detached (`pgrep -f cora_hybrid.ceiling_dev`; waits for C2's run_meta.json, then runs the frozen native solver on 60 development tasks (seeds 9100-9104, disjoint from C2 evaluation) with 3 demos vs with the true answer as a 4th demo; result outputs/hybrid_c2_dev/ceiling_summary.json; never launch twice). 

NATIVE OFFICIAL RESULT: 57144804 COMPLETE, public 0.00 (records/KAGGLE_NATIVE_V1_OFFICIAL_RESULT_20261013.md). Last updated 2026-10-13T13:20Z. Current: KAGGLE native_v1 SUBMITTED: submission 57144804 (notebook chimdiwalter/cora-native-v23-arc-agi-2-october-baseline v1, dataset chimdiwalter/arc-native-baseline-v1 v1) at 2026-10-13T13:17:12Z, SCORE PENDING (check `~/.venvs/kaggle-cli/bin/kaggle competitions submissions arc-prize-2026-arc-agi-2`; never resubmit because it is pending). Committed run verified: 240 tasks/259 positions valid, 4.03 h on 4 CPUs, 139/45/120 real a1/a2/fallback. Log: records/KAGGLE_NATIVE_V1_DEPLOYMENT_LOG_20261012.md. When scored: write records/KAGGLE_NATIVE_V1_OFFICIAL_RESULT_20261013.md, then update paper, poster and abstract (OFFICIAL KAGGLE, NATIVE BASELINE). Track C / section 12 (plan records/CORA_NEURAL_CANDIDATE_EVIDENCE_PLAN_20261013.md): corpus C2 generated (outputs/hybrid_c2/, 120 tasks, challenges 4f680ae9, solutions 906e11db, evaluator only); CORA_ONLY arm RUNNING detached on Athe (`pgrep -f cora_hybrid.run_native_c2`; log outputs/hybrid_c2/native_run/notebook.log; never launch twice); NEURAL_ONLY arm on C2 needs a separate private Kaggle kernel after the full run (quota). Leader-method audit COMPLETE: records/CORA_ARC_LEADER_METHOD_AUDIT_20261013.md (+ survey appendix records/CORA_ARC_LEADER_SURVEY_20261013.md): top-10 methods UNKNOWN; documented recipe = NVARC-style 4B grid LLM + synthetic data + per-task LoRA TTT + augmentation voting (24 private / 29-34 public); NVARC sft139 competition-eligible but NOT clean for science; NVARC smoke: v1 ERROR (model path), v2 COMPLETE (compatibility passed; functional 4/4 on trained-on training tasks, not a score), v3 PROBE pushed 2026-10-13T15:54:44Z (multi-output and 30x30 tasks; kernel chimdiwalter/nvarc-qwen3-4b-smoke-v1; never submit it). PROBE v3 PASSED (multi-output and 30x30). FULL PACKAGE PUSHED: kernel chimdiwalter/cora-neural-ttt-baseline-v1 v1 at 2026-10-13T16:22:52Z, committed run on all 240 stand-in tasks (status log outputs/kaggle_deploy/neural_v1_full_status.log; DO NOT push it again while it runs; its 240-task committed run costs ~24 of ~27 quota hours; then submit as NEURAL_TTT_BASELINE under the user's one-entry authorization, at most 1 submission/day; status log outputs/kaggle_deploy/neural_v1_smoke_status.log; record records/KAGGLE_NEURAL_V1_LOG_20261013.md). On completion: `kaggle kernels output chimdiwalter/nvarc-qwen3-4b-smoke-v1 -p <dir>` (log, submission.json, asset_identity.json), classify, then build kaggle/neural_v1/ (full 240-task NEURAL_TTT_BASELINE) only if it passed. CORA-NVG COMPLETE: H1 REJECTED, route closed (records/CORA_NEURAL_VIEW_GUIDANCE_RESULT_20261013.md; final 165 decisions, 35 warranted: B1 fixed-order fallback 35, Qwen demos 19, Qwen authentic trace 1 = shuffled 1, I-JEPA 3 < random 12.6; no guide harms; all warranted from one family). PENDING DELIVERABLES: paper section done; poster and abstract lines to add together with the native Kaggle score. P3_REJECTED; pilot v2 FROZEN_NOT_RUN; Step B untouched.

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

## Standing deliverables (user, 2026-10-12): update after EVERY new result

- Award paper: `docs/PAPER_SKELETON.md` (paper track deadline 2026-11-08).
- Summit poster (ARC Prize Research Summit 2026-10-23): `docs/summit_poster/`
  (poster source + PDF; every PNG it uses in `docs/summit_poster/figures/`).
- Poster abstract as PDF: `docs/summit_poster/`.
- Current files: `docs/summit_poster/poster.tex` -> `poster.pdf` (A0,
  tikzposter), `abstract.tex` -> `abstract.pdf` (one page, 266 words).
  Rebuild: `.venv_arc2026/bin/python scripts/summit_figures.py`, then in
  `docs/summit_poster/`: `pdflatex -output-directory=<scratch> poster.tex`
  and `abstract.tex`, copy the two PDFs back (no aux files in the repo).
  Open QC item: figure text is about 12 to 16 pt at A0 (readable close up);
  a poster-scaled font pass is still to do. `kaggle/writeup.md` (1,500-word
  cap) has not been refreshed since 2026-09-23.
- Figures ONLY from sealed outputs or the real pipeline
  (`scripts/summit_figures.py`); no generated pictures; toy illustrations
  only if labelled as such. Evidence note:
  `records/CORA_SUMMIT_POSTER_EVIDENCE_20261012.md`. VDCG never included.

## Next action, exactly one

**REAL-TASK ADAPTIVE LOO STABILITY v1 (user directive 2026-10-12) IN PROGRESS.**
Data: the 60 development tasks only (demonstrations; leave-one-out scores
held-out demonstrations); never the pilot v2 bundle, the 488 candidates,
evaluation DEV / HOLDOUT, solutions, Step B, VDCG, E_transfer, Lockbox.
Pinned trees (pilot v2 manifest): cora_reach, cora_pilot, cora_pilot2,
harness, geocat_arc, cora_arc2026, src/reasoning_project and three TTI
packages; a new file inside any of them breaks pilot v2's freeze, so new
code lives in `cora_loo/` and new scripts; after every commit re-run
`freeze_pilot_v2.freeze_problems` and the reach v1 manifest check (both
must stay []).
Plan: protocol `docs/CORA_REAL_TASK_LOO_STABILITY_v1.md` -> observation-only
instrument (`cora_loo/`, v1.9 tracer + deadline and substitution spies,
WALL and CPU1 clocks) -> synthetic tests -> diagnosis freeze -> one
detached run (arms A full-data, B adaptive fold, C fixed-extension
FORENSIC, D no extension, E matched) -> H1-H6 classification -> diagnosis
record frozen -> repair decision.
- Instrument committed 0e3d091 (6 tests pass); diagnosis FROZEN 462e8ef
  (`outputs/loo_v1/diagnose_manifest.json` sha256 58de06d5...7a7ede);
  reach v1 and pilot v2 freezes re-checked: 0 problems.
- DIAGNOSIS RUNNING detached since 2026-10-12T00:42:50Z (run ONCE):
  coordinator pid 711041 (pgid 711041, boot 5c543236), workers
  711068-711071 (`logs/loo_v1/diagnose_0_workers.json`), checkpointer pid
  711811 (`scripts/loo_v1_checkpoint.sh diagnose 711041`, commits
  `outputs/loo_v1/diagnose_rows.jsonl` every 15 min and at the end). 18
  units (4 full-data, 14 folds), kf892487f1049 first. Administrative
  monitoring only. If interrupted (no `logs/loo_v1/DIAGNOSE_0_DONE`, no
  live recorded pid): `setsid nohup .venv_arc2026/bin/python
  scripts/loo_v1_run.py diagnose --resume > logs/loo_v1/coordinator_diagnose.log
  2>&1 < /dev/null &` (2 max), then relaunch the checkpointer with the new
  pid. After the marker: `.venv_arc2026/bin/python scripts/loo_v1_classify.py`
  (in the workers' environment), then the diagnosis record.
- DIAGNOSIS COMPLETE 2026-10-12T03:03:29Z (18 of 18, 0 errors, rows
  4c14f9d) and FROZEN as `records/LOO_V1_DIAGNOSIS_20261012.md` before any
  repair code. Frozen classes: H3 3, H1 2, H4 1, H2 1, UNRESOLVED 7 (engine
  LOO with a deadline hit). Forensic probes (89bdb49 + variant probe):
  DOMINANT BLOCKER = SEGMENTATION-VARIANT ADMISSION MISMATCH: the engine
  searches at most 4 coherent variants in a fixed order, coherence depends
  on the demonstration subset, and the extension's construction variant is
  cut (kf892487f1049 inner pairs (0,2), (1,3): G found on the other 4 pairs,
  never on these; k5a49896251a2 subsets) or incoherent (k017955a77fc5 S2,
  k5991e227189e S6): 11 of 14 folds and all 3 full-data rejections. Support
  2 (k017955a77fc5 f0, f1), single-demonstration identifiability 1
  (k017955a77fc5 f2), ordering co-occurs in kf892487f1049 f1. Resources ruled
  out (WALL = CPU1 in 23 of 23 arms; CPU share 0.94-0.997). The parsimony-
  skip hypothesis was refuted. Novelty: GROW_SUBLANGUAGE_ABSENT, NOT_A_CACHE,
  SEARCH_INACCESSIBLE_WITHIN_BUDGET; BOUNDED_SEMANTIC_EXTENSION_CERTIFIED not
  established.
- NEXT: the one licensed repair, VARIANT-CARRYING INSTALLATION (while e is
  installed its construction variant is searched first and admitted;
  everything else unchanged), in a new package outside the pinned trees,
  unit + mutation tests, protocol amendment (section 12), freeze, ONE
  development recheck (original vs successor, same 60 tasks). Pre-registered
  expectation in the record: the screen (conditions 1-5 on one task) is NOT
  expected to pass (evidence-side cuts, support, ordering remain).

- REPAIR BUILT 568af22 (`cora_reach2/`: variant-carrying installation;
  `measure2.py` = reach v1 + 11 `# V2` lines via `scripts/build_measure2.py`;
  10 tests incl. 4 mutants) + Amendment 1
  (`docs/CORA_REAL_TASK_LOO_STABILITY_v1_AMENDMENT_1.md`, separate file so
  the diagnosis-pinned protocol stays byte-identical). Erratum 1 (0feaaeb):
  the first recheck launch stopped before any unit (workers' freeze read a
  records/ file the hook refuses; 0 rows, no outcome; artifacts in
  `logs/loo_v1/recheck_aborted_launch1/`). Re-frozen ad0c4b5
  (`outputs/loo_v1/recheck_manifest.json` sha256 7be92e40...).
- RECHECK RUNNING detached since 2026-10-12T14:10:57Z (run once): coordinator
  pid 1587690, workers 1587758-1587761 (`logs/loo_v1/recheck_0_workers.json`),
  checkpointer pid 1588780 (`scripts/loo_v1_checkpoint.sh recheck 1587690`;
  its commit text says "of 18 units" but counts recheck rows of 120). 120
  units (60 tasks x ORIGINAL, SUCCESSOR), FC tasks first. Resume only after
  a genuine interruption: `setsid nohup .venv_arc2026/bin/python
  scripts/loo_v1_recheck_run.py recheck --resume > logs/loo_v1/coordinator_recheck.log
  2>&1 < /dev/null &` (2 max). After `logs/loo_v1/RECHECK_0_DONE`:
  `.venv_arc2026/bin/python scripts/loo_v1_recheck_summary.py`, record, report.

- RECHECK STOPPED 2026-10-12T14:23:40Z at the user's summit addendum (it
  asks to complete the predicate-level representation-eligibility diagnosis
  and negative synthetic probes BEFORE any new repair or run): all four
  workers stopped by exact pid before any unit finished; 0 rows; the
  coordinator recorded exit -15 x4, 120 missing, resumable
  (`logs/loo_v1/recheck_0_record.json`); checkpointer stopped. No recheck
  outcome exists or was read. Do NOT resume without a new go-ahead: the
  diagnosis addendum may revise the repair (then a new versioned successor
  and a new freeze, not this one).

- DIAGNOSIS ADDENDUM RECORDED 2026-10-12 (`records/LOO_V1_DIAGNOSIS_ADDENDUM_20261012.md`,
  a719383; observation only, nothing launched). Probes: negative synthetic
  controls `scripts/loo_v1_probe_negative.py` (1f03a1c) -> output 70d3ed9
  (sha256 2f100350...); static exposure `scripts/loo_v1_probe_exposure.py`
  -> output 3ba75e5 (794ad70b...). Findings: exact predicate and first
  rejection site per subset; [CORRECTED by Clarification 01: count consistency is deletion-stable, the complete
  eligibility test is not monotone (0/72 synthetic, 0/50 FC-task, 7/724 all-development losses)]; the defect is the
  cap cutting the strictly coarser S6 that the engine's round-3
  fold-convergence rule relies on; H_rep true, H_search variant level only,
  H_rank false, H_budget false, H_evid weak; 7 falsified hypotheses.
  Negative controls: PROMOTE 131 runs and ADMIT 37 runs, paired with the
  task's native outcome: 0 gains, 6 harmful (3 each). So reach v2's
  variant-first repair is NOT recommended and its recheck stays STOPPED
  (retire it only on the user's word). P1 (global coarser completion)
  rejected statically (exposed on 73/96 synthetic subsets). P2
  (LOO-anchored variant completion; inside the engine's own LOO only,
  append the validated program's variant when the fold finds it coherent
  but the cap cuts it) PROPOSED, NOT AUTHORIZED: predictions (kf892487f1049
  3/4 outer folds at best; f1 still refuted after window_fill; screen
  predicted to FAIL), frozen criteria S1-S3 + E1, kill rule, matched
  accounting. It changes the engine's INTERNAL LOO gate: the user decides
  whether that counts as weakening acceptance. All freezes re-checked after
  the commits: reach v1, pilot v2 (reasoner, evaluator), diagnosis, recheck
  (coordinator, worker): 0 problems.
- NEXT: PRESERVE THE FROZEN PILOT AND COMPLETE THE GENERIC
  REPRESENTATION-ELIGIBILITY DIAGNOSIS BEFORE ANY NEW REPAIR OR RUN. Await an
  explicit decision on P2 (authorize as specified, amend, or stay at
  diagnosis). Launch nothing without it.

### P3 safety falsification block (2026-10-12)

Directive text: pasted by the user on 2026-10-12, titled "P3 SAFETY FALSIFICATION AND FOLD-LOCAL REPRESENTATION
AUDIT". Kill rule: any unsafe synthetic outcome, native regression, information transfer, change outside the
declared exposure, or freeze failure rejects P3. If P3 passes everything, label it P3_SYNTHETIC_PREFLIGHT_PASS,
never REAL_ARC_CAPABILITY_GROWTH. End lines: on failure "NEXT: REJECT P3, PRESERVE THE NEGATIVE RESULT AND
REASSESS THE FAILURE-TYPED REASONING CONTROLLER."; on a pass "NEXT: REQUEST AUTHORIZATION FOR A VERSIONED
REAL-DEVELOPMENT COMPARISON." Do not launch that comparison.

- Step 1 DONE. HEAD 3216957 (only deliverable commits since 473a089); all 6 freezes 0 problems.
- Steps 3-4 DONE. Audit `scripts/p3_audit_equivalence.py` (b8bc4c1) -> `outputs/p3/audit_equivalence.json`
  (sha256 b3829334...).
  - Census reproduced exactly (0 mismatches): 571/1849 slots, 277/522 subsets, 4/6 native successes
    (k328b173af636, k553a7e98f13d, kc8866e481747, kf105d51e18c5), kf892487f1049 02 -> +S6, 13 -> +S6, S7.
  - Training equivalence is NOT unseen equivalence: INDUCTION-equal views segment an input outside the
    subset differently in 61 of 769 development pairs (S1~S2 22, S3~S4 11, S4~S7 10, S3~S7 8, S1~S6 5,
    S1~S5 3, S2~S6 2) and in 9 of 231 synthetic pairs.
  - kf892487f1049: on (0,2), S3~S7 diverge on demos 1 and 3; S1~S2, S1~S5 and S3~S4 do not.
  - Structural point for the record: natively, the earlier duplicate already wins ties (key, count,
    trial order), so P3 keeps the selected program among duplicates except through the cheap-first
    probe and deadline timing. P3 is selection-preserving among duplicates, not semantics-preserving. Its
    real effect is admitting new views.
- Steps 5-7 PROGRESS:
  - preregistration `docs/CORA_P3_SAFETY_PREFLIGHT_v1.md` (7997679; section 8 clarification: exposure =
    dedup ADMITS a view);
  - corpus 17 adversarial tasks (`outputs/p3/adversarial_corpus.json`, file sha256 226dc3ba...);
  - P3 implementation `cora_p3/` (884d147; 6 tests pass);
  - runner `scripts/p3_preflight.py` (5818c51);
  - FROZEN b594223 (`outputs/p3/p3_manifest.json`; 41 tasks, 34 exposed);
  - the run launched detached ONCE: rows go to `outputs/p3/preflight_rows.jsonl`, the end marker is
    `outputs/p3/PREFLIGHT_DONE`, the log is `logs/p3_preflight.log`.
  - After the marker: `scripts/p3_preflight.py summarize` (same env as the run), then the gates S1 and S2.
  - If interrupted before the marker: do NOT rerun silently (the runner refuses when rows exist). Record
    the interruption and decide.
- RESULT: P3_REJECTED (98c9bed; record `records/P3_SAFETY_PREFLIGHT_RESULT_20261012.md`). Steps 8 and 9 NOT run.
- (Original step-5 plan, kept for reference:)
  - `docs/CORA_P3_SAFETY_PREFLIGHT_v1.md`;
  - adversarial generator `scripts/p3_adversarial_corpus.py` with families A (duplicate frees a useful
    slot, kf89-like corner pairs), B (a freed slot admits a misleading coarser view), C (train-equal,
    held-out-divergent), D (native successes must stay), E (no duplicates: P3 must be a no-op), F
    (duplicates only in inner folds); G as mutation tests;
  - at least 12 tasks, 3 training and 2 held-out demonstrations each, fixed seeds, fixtures chosen by
    static properties only, corpus hash;
  - arms: BASE, BASE-repeat (native noise) and P3, 20 s budget as in the negative probe;
  - S1: 0 new false acceptances, 0 regressions; S2: byte-identical outside the exposure unless BASE and
    BASE-repeat disagree (then UNSTABLE, reported).
- Step 6 TODO: package `cora_p3/` as an overlay with a generated copy of inducer._induce_candidate. Dedup at
  the INDUCTION level, before the cap, in trial order. A build `--check` and mutation tests.
- Step 7 TODO: freeze manifest `outputs/p3/`, then run the preflight ONCE.
- Step 8 only if S1+S2 pass: the 6 native successes, BASE vs P3, through the isolation hook.
- Step 9 only if that also passes: kf892487f1049 folds under P3.

### Earlier in this section (reach v1 block)


**REAL-TASK REACH v1 BLOCK IN PROGRESS (user directive 2026-10-07 "REAL-TASK
PROPOSER REACH AND BASELINE DELIVERY PARITY" + binding failure-driven
invention invariant).** Development only on the 60-task dev bundle; no
pilot, no ARC-1000, no eval splits, no push.
- Protocol `docs/CORA_REAL_TASK_REACH_DEV_v1.md` (3b638f7; invariant
  section 0; operational A-E diagnosis; one-mechanism rule).
- Native assets: sealed runs also used `learned_verbs.json` (b1f07ba5),
  now vendored and installed (c57f4b3, records/NATIVE_ASSETS_PROVENANCE.md);
  learned generators NOT part of the sealed config.
- Delivery parity DONE (c407776, dd27685): notebook sets the five flags in
  the harness subprocess only, assets hash-checked, v23 tarball; 5 parity
  tests; local notebook smoke valid (flags verified in child processes).
- NATIVE FAILURE CENSUS RUNNING detached since 22:56:35Z: coordinator pid
  3382121 (`setsid nohup .venv_arc2026/bin/python scripts/reach_v1_run.py
  census`), rows outputs/reach_v1/census_rows.jsonl, marker
  logs/reach_v1/CENSUS_0_DONE. If interrupted: `scripts/reach_v1_run.py
  census --resume` (refuses while a recorded worker is alive; 2 resumes max).
  Continual saving: detached checkpointer `scripts/reach_v1_checkpoint.sh`
  (pid in logs/reach_v1/checkpointer_state.json) commits the census rows
  and programs every 15 minutes and at completion, then exits; after a
  resume, relaunch it with `setsid nohup bash scripts/reach_v1_checkpoint.sh`
  (edit the coordinator pid inside first).
  Checkpoint 23:14Z: 11 of 60 rows (about 0.6 per minute, finish near
  00:35Z); rows are appended atomically per task, so nothing is lost on
  interruption.
  Interim reading at 23 of 60 (analysis only, mechanism NOT chosen yet):
  DE_LOO 12, A_REPRESENTATION 7 (matching 6), NATIVE_CERTIFIED 3, B 1.
  The DE_LOO "exact fits" are memorizations: one rule per object, selector
  on an object-specific literal (shape hash, colour), action GROW in the
  constant `pattern` fallback mode (added cells as fixed offsets); folds
  lose the rule witnessed by the held-out pair. Candidate mechanism (to be
  decided on the full census): construct a relational growth form from the
  memorized per-object (object, added cells, scene) examples. Caveat: the
  census STRUCT/PARAM split is wrong for reduction programs (string table
  keys are not masked); recompute that split from census_programs.
- Concurrency note: commit f5edd91 (census.py summaries) came from another
  session (not deltos-e7, e-a7, deltos-e1 or deltos-52; likely deltos-6c);
  kept; sessions asked to stand down.
- CENSUS DONE (records/REACH_V1_CENSUS_20261008.md, 277766e): DE_LOO 27
  (51 of 62 reference rules = constant grow `pattern` memorizations),
  representation 21, certified 6. SELECTED MECHANISM: growth-relation
  construction from the memorized instances (bridge = context-scoped
  overlay on correspondence.detect_grow + actions.apply_grow; geocat_arc
  unchanged).
- Tagged instance extraction (phase instances2) RUNNING since ~00:40Z:
  coordinator pid in logs/reach_v1/instances2_0_start.json, checkpointer
  running; resume `scripts/reach_v1_run.py instances2 --resume`. The
  untagged phase `instances` was stopped by exact pid and superseded (rows
  kept; logs/reach_v1/instances_0_stopped.json).
- instances2 DONE 2026-10-08T01:21Z (60 of 60 rows; 352 instances in 31
  tasks; c0898b8). Bridge DONE (c44e6b2, 8 tests).
- GRAMMAR COVERAGE + DECISION DONE 2026-10-11 (protocol section 4.1): on the
  complete instances2 the coverage script explains 5 tasks (connect 2,
  bbox_fill 2, window_fill 1, band 1, dilate 1); the mechanism's own rule
  (all instances of a variant, one colour, >= 2 demonstrations) proposes on
  4 tasks, one proposal each (window_fill k=3; connect x2, same extension;
  bbox_fill). FROZEN: the full nine-family grammar (210 settings), named in
  `construct.GRAMMAR`; the smallest covering set gives the same full-task
  proposals and is not adopted (it would only ease folds and controls,
  selected on these tasks). Limits written into section 4.1.
- MEASUREMENT BUILT 2026-10-11 (343dcb9): `cora_reach/measure.py` (fixed
  per-task policy, pilot gates in frozen order, adaptive LOO rebuilt from
  scratch per fold, DEMO_ONLY + SHUFFLED_FAILURE controls, REMOVED +
  MATCHED_COMPUTE, bounded separation = condition 4, growth support
  contract), coordinator phase `measure` (refuses unless
  `outputs/reach_v1/measure_manifest.json` matches), summary/verifier
  `scripts/reach_v1_measure_summary.py`, freeze `scripts/freeze_reach_measure.py`,
  protocol section 5.1 + section 6 installed-stage definition, tests
  `tests/test_reach_measure.py` (5 unit pass; 1 synthetic engine test).
- Tests: 15 reach tests pass (4da98f6), incl. the accepted path on the
  synthetic band task (ACTIVATED, 4/4 rebuilt folds) and the rejection
  path on a synthetic copy task. FROZEN c8d8e3a
  (`outputs/reach_v1/measure_manifest.json`, head 4da98f6, 0 problems).
- MEASUREMENT RUNNING detached since 2026-10-11T20:23:11Z (run ONCE):
  coordinator pid 328950 (pgid 328950, boot 5c543236), workers 329132-329135
  (`logs/reach_v1/measure_0_workers.json`), checkpointer pid 329650
  (`scripts/reach_v1_checkpoint.sh measure 328950`, commits
  `outputs/reach_v1/measure_rows.jsonl` every 15 min and at the end). Load
  about 66 on 24 cores at launch. Expected about 2 to 3 h (4 FC tasks:
  k017955a77fc5, k5991e227189e, k5a49896251a2, kf892487f1049).
  Administrative monitoring only (row count, marker, pids).
  If interrupted (no `logs/reach_v1/MEASURE_0_DONE`, no live recorded pid):
  `setsid nohup .venv_arc2026/bin/python scripts/reach_v1_run.py measure
  --resume > logs/reach_v1/coordinator_measure.log 2>&1 < /dev/null &`
  (2 resumes max), then relaunch the checkpointer with the new coordinator
  pid. After the marker: `.venv_arc2026/bin/python
  scripts/reach_v1_measure_summary.py`, record
  `records/REACH_V1_MEASURE_20261011.md`, readiness recheck, return list.
- USER DIRECTIVE 2026-10-11 "REACH v1 MEASUREMENT COMPLETION AND REAL-PILOT
  READINESS" (received at HEAD 5fe9c26): recover and verify, let the run
  finish, verify independently, report the A-N funnel, apply the unchanged
  readiness rule; CASE A (READY) = record + freeze the development result,
  then design AND FREEZE a versioned successor pilot and STOP before running
  it; CASE B = record the blocker, request a development decision. No AI
  co-author trailers; no push.
  - Step 1 verified 20:31Z: manifest 2e567bce (committed c8d8e3a, 0 freeze
    problems), boot id unchanged, coordinator 328950 and the 4 workers alive
    with their recorded start ticks, 45 rows unique, 0 RUN_ERROR, worker
    logs empty, checkpointer alive.
  - Independent terminal verifier `scripts/reach_v1_verify_measure.py`
    (dab575d, dc459f8), written before the outcome was read; dry run on 45
    rows: only the expected in-progress problems. Run it with the workers'
    environment (chain flags, PYTHONHASHSEED=0) after the marker.
  - Successor DRAFTED (9643cd4, NOT FROZEN, before the outcome was read):
    `docs/CORA_REAL_ARC_GROWTH_PILOT_v2.md`, `cora_pilot2/`,
    `scripts/pilot_v2_{select,run,evaluate,verify,watch}`,
    `scripts/freeze_pilot_v2.py`, `tests/test_pilot_v2.py` (6 pass). It
    reuses `cora_reach.measure.run_task` unchanged, pilot v1's selection,
    bundle format, isolation, native entry, deployable rule and ladder, and
    adds the invention rung (S separation + F controls fail). Freeze steps
    if READY: write section 12 (a, N) from the record, `pilot_v2_select.py N`,
    `freeze_pilot_v2.py`, commit; then STOP.
  - Run status 2026-10-11T21:03Z (administrative): 55 of 60 rows (committed
    90c116e at 20:53:49Z), 59 claimed, coordinator and workers alive, worker
    logs empty, no marker yet; load about 58 to 72. The remaining tasks are
    the failure-conditioned ones (full gates, leave-one-out and controls).
- MEASUREMENT COMPLETE 2026-10-11T21:34:26Z (71 min wall; exit 0 x4; no
  resume; rows 60ddd04, sha256 821a6556...). VERIFIED 2026-10-12: summary 0
  problems; independent verifier 0 problems (`logs/reach_v1/verify_measure.json`).
  Funnel A 54, B 31, C 4, D 4, E 4, F 4, G 1, H 1, I 1, J 4, K 0, L 4, M 1,
  N 0; classes NO_PROPOSAL 56, ENGINE_REJECTION 3, LOO_FAILURE 1. The one
  accepted repair: kf892487f1049 bbox_fill (accepted, used, separated,
  supported; KALONE/REMOVED/MATCHED fail) -> fails all 4 rebuilt folds.
  Controls: DEMO_ONLY 1 proposal (other task, rejected); SHUFFLED 4
  installs, 0 accepted with e used. READY = PASS (isolation clean, no
  RUN_ERROR, census complete, 4 installed); a = 0 -> N = 120. Record
  `records/REACH_V1_MEASURE_20261011.md`; stage ledger updated.
  Blockers: coverage 4/60; engine acceptance 1/4 (2 hard caps, 1 engine
  LOO); adaptive LOO 0/4 (binding). The fold records lack the engine's
  failure stage (limitation).
- PILOT v2 FROZEN_NOT_RUN 2026-10-12 (CASE A done): protocol completed
  deca7a3 (section 12: READY, a = 0, N = 120, expected-outcome note);
  sample by `scripts/pilot_v2_select.py 120` (n3 60, n4 40, n5p 20 from the
  untouched v1 candidates; bundle `records/pilot_v2/pilot_bundle.json`
  sha256 8bf9e9de64727adc9968aa72dcde87890aa750198e4c6c0c205abf2c461d2f29;
  evaluator-only key map `records/pilot_v2_evaluator/pilot_keymap.json`);
  frozen c1906ee: `outputs/pilot_v2/pilot_v2_manifest.json` sha256
  c93ec1dbe7ceee72256129ec28c0cde4e366cfc609989b8921f556fa18654748 (39
  files, 10 dependency trees; 0 freeze problems, reasoner and evaluator
  roles). 21 reach + pilot v2 tests pass. NOT RUN.
- STOP. NEXT = USER DECISION. Either (a) run pilot v2 as frozen (about 7 h
  on 4 workers: native, instances, cora phases; consumes 120 of the 488
  untouched candidates; development predicts NO_REAL_ARC_WITNESS most
  likely, the binding blocker being the adaptive LOO), launch:
  `setsid nohup .venv_arc2026/bin/python scripts/pilot_v2_run.py pilot >
  logs/pilot_v2/coordinator.log 2>&1 < /dev/null &` (mkdir logs/pilot_v2
  first) then `setsid nohup bash scripts/pilot_v2_watch.sh <coordinator pid>
  > /dev/null 2>&1 &`; or (b) an explicitly authorized development decision
  on the leave-one-out blocker on the 60 development tasks only (the pilot
  candidates stay untouched; a changed mechanism would need a new pilot
  version). Not authorized now: ARC-1000, the evaluation DEV / HOLDOUT, any
  push.

**STOPPED: REAL ARC CAUSAL PILOT v1 NOT FROZEN. BLOCKER: PROPOSER REACH
ON REAL TASKS** (2026-10-07, record `records/REAL_ARC_PILOT_V1_FEASIBILITY.md`,
commit ce123e8). The feasibility rule fixed before the dry run (protocol
section 12, f47c795) needed at least one of 60 development tasks to reach
the compiled-and-installed stage: 0 of 60 did (path class NO_PROPOSAL 60;
proposer NO_PROPOSAL 59, K_ALREADY_SOLVES 1; consistent single blocks on 13
of 60; fitter rejections over 12,000 block evaluations led by
slot_unobservable 4,280 and region_colour_conflict 3,688). Positive control
on 4 synthetic v1.9 dev tasks: every gate through unanimity passed on all 4,
1 ACTIVATED and correct, 3 abstained at witness support with right
predictions (support gate strict; design note only). Isolation clean on
every log. One native library-install race found and fixed (24fad7e).
- Built and kept for reuse (unchanged once a proposer reaches real tasks):
  selection 4d3c29b (548 in scope; dev 60; pilot candidates n3 356, n4 109,
  n5p 23, untouched), protocol `docs/CORA_REAL_ARC_CAUSAL_PILOT_v1.md`
  (sha256 751e0d41..., status NOT FROZEN), `cora_pilot/`, scripts
  `pilot_v1_{select,run,evaluate,feasibility,dev_frontier,positive_control}.py`,
  `freeze_pilot_v1.py`, `logs/pilot_v1/verify_pilot.py`, 33 tests pass.
- Not done, by the rule: pilot bundle, N, manifest, freeze. The pilot was
  never run; no target was read; the evaluator key map for the pilot was
  never written.
- Separate finding for the Kaggle entry (deadline 2026-10-26):
  `records/KAGGLE_NOTEBOOK_FLAGS_FINDING_20261007.md` (the notebook sets
  none of the five sealed chain flags).
- NEXT: user decision on how the proposer is to reach real tasks (e.g. a
  bounded proposer-reach development block on the 60 development tasks only,
  metric = tasks reaching the installed stage, pilot candidates untouched;
  or a different construction source such as the engine's own leave-one-out
  near-misses). Then re-run the feasibility rule; freeze only if it passes.

**2026-10-07 mapping / manuscript / GitHub request: DONE.** Map of the four
trees in `docs/PROJECT_MAP.md`; `docs/PAPER_SKELETON.md` updated to the v1.9
state (abstract, contributions, 3.2, 4, 5, 9.3, 11, 12, appendices A to C,
Paper Track deadline 11-08); pushed this repository to GitHub as branch
`arc2026-sprint` (push by URL: `git push
git@github.com:ChimdiWalter/Symbolic_Reasoning_LLM_ARC-AGI.git
master:refs/heads/arc2026-sprint`); `main` README rewritten to the latest
evidence (e90f02d, from a scratch clone; the Reasoning_Project worktree was
not touched). No AI co-author anywhere. Still stale: `kaggle/writeup.md`
(2026-09-23 state). The ARC-1000 run has NOT been started (blocked until the
pilot gives a real witness).

**STOPPED: v1.9 PROSPECTIVE = ENGINE_STABILITY_REPAIR_ACCEPTED** (run once
2026-10-07, 3,159.8 s; record `records/ITEM2_V19_PROSPECTIVE_RESULT_20261007.md`;
paper section 8.14). Claim LEVEL 2, SYNTHETIC DOMAIN ONLY, under the
witness-support regime. Real ARC causal pilot LICENSED (not designed).
- Verifier `logs/v19/verify_prospective.json` 28/28; independent
  recomputation `logs/v19/recompute_prospective.json` agrees on every value;
  no resume, workers clean, freeze_problems [] after the run.
- G1 6:0 (p 0.0156) and 8:0 (p 0.0039); G2 27/30 K*' witnesses (K* 12);
  G3 adaptive LOO 27 vs 12 (net 15, p 3.05e-5; folds 207 vs 133; pairing 0);
  G4 all pass (precision 237/239 vs 157/157; added correct 80, wrong 2).
- Disclosed: K*' accepted 5/5 seven-pair and 28/28 four-pair wrong installed
  extensions (K* 1/5 and 9/28); no discrimination; gain partly corpus
  arithmetic (3-witness stratum 0 -> 6).
- The watcher finished and removed its @reboot hook; no v1.9 process runs.

NEXT (fresh session): DESIGN AND FREEZE THE REAL ARC CAUSAL PILOT FOR THE FIRST
GENUINE B/P/U/L/T/A WITNESS. Do not start ARC-1000, the 60 DEV or the 60
HOLDOUT. The pilot must carry the safety burden the engine does not
(selection quality, held-out checks, abstention) on two-to-five-demo tasks.
Pilot brief (from the v1.9 records, user note 2026-10-07):
- Biggest risk = wrong-extension acceptance: K*' accepted 5/5 seven-pair and
  28/28 four-pair deliberately wrong installed extensions. The pilot must
  test whether proposer + verifier + reasoner select correct extensions AND
  abstain when evidence is insufficient; abstention and wrong-certification
  rates are first-class, pre-registered outcomes.
- Real tasks have no completeness by construction: the right extension may
  not be in the proposer's space (compositions of K's blocks; expression
  trigger needs same shape, additive change, every pair changing). Fix the
  scope filter from demonstrations only, before any task is seen.
- Data prerequisite (ledger open item): the authorized ARC training set is
  NOT in this repo (data/arc holds only the 60 DEV evaluation challenges and
  a 3-byte solutions placeholder). Locate it through the project's data
  manifest and verify version, 1000 unique IDs, checksums and exposure, then
  freeze a small fixed pilot set from it, before any run. Never the 60 DEV
  or the 60 HOLDOUT.
- Same reasoner, frozen K*' (e4672bfa) and the frozen v1.8 proposer; L =
  adaptive leave-one-out rebuilding the proposal in every fold; A = remove
  e (and matched compute) destroys the gain.

**v1.9 ENGINE ACCEPTANCE STABILITY: RE-FROZEN AFTER ERRATUM 01 at 44a64f0
(manifest 528981dd, FROZEN_AFTER_ERRATUM_01_NOT_PROSPECTIVELY_TESTED). STOPPED
before the prospective test (directive section 24).**
- Diagnosis (d9b4479, record + addendum): H1 145/145 (86 single-witness
  refits, 59 pixel-rule rankings); load, budget, H4 eliminated.
- Repair K*-4 (`cora_v19/v19_repair.py`, K*' identity e4672bfa): lowers the
  evidence requirement for installed extensions (three witnesses per key to
  two) and lets no native candidate displace a verified installed concept.
- Development (af4b7c1): witnesses 26/30 vs 12; adaptive LOO 26 vs 12;
  K*' accepted every installed extension it was given (491/491, incl. 19/19
  wrong four-pair trials); certified precision 236/238 vs 159/160.
- ONE review (`records/ITEM2_V19_REVIEW_RESULT.md`, access audit clean):
  BLOCKING_DEFECTS (1 blocking, 2 major, 9 minor), all answered by
  `records/ITEM2_V19_ERRATUM_01.md` (e283f8f): threshold lowering and the G4
  history stated; marginal-precision gate added; corpus-arithmetic caveat
  and LEVEL 2 limited to tasks with >= 2 witnesses per key; "no
  discrimination detected" wording; verifier P leg; protocol hash check;
  exception-safe controls; crash/resume; pairing mismatches; native-switch
  no-regression. Not re-reviewed (one-review rule).
- NEXT SESSION, run ONCE: in this repo, with `PYTHONHASHSEED=0
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<Reasoning_Project_tti>` and no ARC_*:
  `setsid nohup .venv_arc2026/bin/python scripts/v19_prospective.py >
  logs/v19/prospective.log 2>&1 &` (4 workers, about 60-75 min); record pid,
  pgid, boot id, load, HEAD; administrative monitoring only; `--resume`
  only after a genuine interruption (start record, no report, no marker, no
  live recorded pid); then `.venv_arc2026/bin/python
  logs/v19/verify_prospective.py` and the result record. Seeds 880M,
  exclusion 3,901 digests, N 30, W 19, DELTA 6.

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
