# ARC-2026 delivery sprint: resume

Last updated 2026-10-20. Read this first.

## State

**NEWEST (2026-10-20 ~15:10Z): G2 RAN ONCE (the user's "authorize G2") — FINAL: NO_GO_STOP. STOPPED. Nothing is running
for v2.**
- **The run:**
  - one detached driver (PID 836449) from HEAD 86bab95; lock verified at solve and at diag;
  - STARTED 14:18:37Z, EXIT 0 at 14:40:54Z;
  - 2 workers at nice 10, CPU only, 0.67 CPU-hours; 0 errors, 0 truncations;
  - logs in `outputs/neural_cora_v2/g2/`.
- **Result:**
  - ncv2-g1 (G1-CH @3000) fits 1/60, correct coverage 1, pass@2 1: the SAME task as g0 (k553a7e98f13d), 0 gains,
    0 losses;
  - native fits 35, correct coverage 8, certified 6;
  - diagnostics on 20 no-fit tasks: 16 NO_SINGLE_RULE in the search's candidate space, 4 inconclusive, 0 search
    misses;
  - forensic: 0 / 0 / 0.
- **Post hoc** (answer-free): of native's 6 certified answers, 4 need unexposed program classes (2 reduction,
  2 generative). kc8866e481747 is expressible in ncv2-g1 and fits every demonstration, but its selector and
  reference are not in G1-CH's candidate set.
- **Record:** `records/NEURAL_CORA_V2_G2_REPORT.md`. Under the frozen rule there is NO neural training; G1b and G1c
  are not opened.
- **Proposed next step** (NOT started; needs a new grammar version, a protocol and authorization): ncv2-g2, "reach
  what native already certifies" (report §6).
- **README** updated: definitions, architecture diagram, status table, G2 FINAL.
- **GitHub push HELD:**
  - the remote repository is PUBLIC (branch arc2026-sprint, 49+ commits behind local master);
  - the outgoing commits contain the user's UNPUBLISHED annotated maize tile (`figures/fig_maize_annotated_DSC_0042_crop_x2.png`
    and the cancer-lesion poster and explainer PDFs), whose provenance record asks for owner (Toni) confirmation
    before public display;
  - everything else passed the audit. The push needs the user's decision.
- `voice_note/` and the research ZIP are excluded locally (`.git/info/exclude`) and never staged.

**EARLIER (2026-10-20 ~15:30Z, before G2 ran): WINNING-PATH ADDENDUM explored, within its authority. G2 is STILL NOT RUN: it needs the
user's explicit authorization. Nothing is running for v2.**
- **Hub record:** `records/NEURAL_CORA_V2_COMPETITIVE_PATH_ADDENDUM_20261020.md` (the ten decisions).
- **New records and docs:**
  - `records/NEURAL_CORA_G2_NATIVE_COVERAGE_INVENTORY.md`;
  - `records/NEURAL_CORA_V2_LICENSE_AND_PRETRAINING_AUDIT.md`;
  - `records/NEURAL_CORA_V2_CONTROLS_AND_GO_GATES.md` (G1b, G1c, G3 and G5 thresholds pre-registered BEFORE G2;
    §0 is the G2 forensic step);
  - `records/NEURAL_CORA_27P64_RISK_AND_RUNTIME_PLAN.md`;
  - `docs/NEURAL_CORA_V2_JOINT_SKETCH_AND_FEEDBACK_SPEC.md`.
- **New code** (outside the frozen G2 files; the G2 lock was re-checked and is valid):
  - `tests/test_neural_cora_v2_parity.py`: 61 pass;
  - `tests/test_neural_cora_v2_forensic.py`: 1 pass;
  - `scripts/neural_cora_v2_parity_bench.py`: 14,200 real-grid executions, 0 mismatches;
  - `scripts/neural_cora_v2_g2_forensic.py`: runs only after the G2 score stage.
- **Verified today:**
  - the tokenizer gives one token per grid cell (300 prompts, 0 misaligned; no BOS; causal-context caveat);
  - ARC-AGI-2 data is Apache-2.0;
  - the 2026 page still says limits "will be announced";
  - the Kaggle rules (12 Oct) say notebooks ≤ 12 h;
  - Kaggle deadlines: code 2 Nov 23:59, paper track 9 Nov 23:59;
  - no peft or bitsandbytes is installed;
  - native occlusion follows object order.
- **Not done, deliberately:** no GPU smoke test; no repair controller; no grammar extension; no installs; poster
  unchanged.
- **After G2 is authorized:** run the G2 command in the block below, then `python scripts/neural_cora_v2_g2_forensic.py`,
  then write the G2 report.

**EARLIER (2026-10-20 13:50Z): NEURAL-CORA V2. The G2 protocol was FROZEN at commit 3677d0f. STOPPED: the scored G2 run
needs the user's authorization. Nothing is running for v2.**
- **Built, in `cora_neural_v2/`:**
  - ncv2-g1, the typed relational AST (`rast.py`);
  - the bridge to native (`bridge.py`);
  - typed hygienic macros;
  - the native inventory check;
  - sound constraints: only P1 and P2, plus the Occam firing filter;
  - the pairing-aware search G1-CH, with a CPU cap and an exhaustive single-rule diagnostic.
- **G2a:** 58 passed, 1 skipped (`tests/test_neural_cora_v2_ast.py`, `tests/test_neural_cora_v2_search.py`). Native
  aggregate sha 18060dbc is unchanged.
- **Runner:** `scripts/neural_cora_v2_g2.py`. Selftest PASS on synthetic tasks only. `solve` and `diag` refuse to run
  without the committed manifest and `--authorized`.
- **Known before the run:**
  - g0 fits 1/60;
  - native fits 35/60 (30 through ObjectProgram or ComposedProgram), has a correct candidate on 8 and is certified
    correct on 6;
  - dev60 has no size-change task.
- **Frozen G2b rule:**
  - NO_GO_STOP if g1 pass@2 ≤ 1;
  - GO if fits ≥ 6, pass@2 ≥ 4, paired gains ≥ 3 and losses ≤ 1;
  - otherwise WEAK.
  - Worst case 3.7 CPU-hours, 2 workers at nice 10.
- **Records:**
  - `records/NEURAL_CORA_V2_{G2_PROTOCOL_20261020, G1_FAILURE_ANALYSIS_20261020, PRIOR_ART_AND_GAP_20261020, QWEN_JOINT_PROGRAM_ADAPTER_DESIGN}.md`;
  - `docs/NEURAL_CORA_V2_{RELATIONAL_AST_AND_LOOP, TO_27P64_DECISION_TREE}.md`.
- **Stale lines corrected:** the roadmap's G1 row (now NO-GO) and its G2 row; the old "PILOT RUNNING" block below.
- **To run, ONLY after authorization** (resumable; it appends missing rows):

  ```
  mkdir -p outputs/neural_cora_v2/g2 && setsid nohup sh -c 'P=$HOME/.venvs/lesegenv/bin/python; $P scripts/neural_cora_v2_g2.py solve --authorized && $P scripts/neural_cora_v2_g2.py diag --authorized && $P scripts/neural_cora_v2_g2.py score' > outputs/neural_cora_v2/g2/run.log 2>&1 &
  ```

  Then write `records/NEURAL_CORA_V2_G2_REPORT.md`, whatever the outcome.
- **Poster:** unchanged. Open question to the user: keep or revert the column-3 pilot line ("Pilot: beats plain
  search, not hand-designed search.")? The v2 directive says no new scoring claims on the poster.
- **After a reboot:** nothing to restart for v2. If a G2 run was in progress, rerun the same command; `run_pool`
  resumes.

**NEWEST (2026-10-20 01:30Z): NEURAL-CORA V1 PILOT FINISHED. G1 = NO-GO (LEARNED_OVER_PLAIN_SEARCH_ONLY).**
- **Primary held-out synthetic compositions (395 tasks), pass@2:**
  - L1@500 (trained Qwen-feature guide): 198;
  - C+@1000 (plain search): 104;
  - L0 (untrained): 30; L0s (shuffled labels): 51;
  - L1h@500 (hand features): 235 (L1 vs L1h: 41 vs 78, p = 0.0009);
  - C+H@1000 (hand-designed search): 358.

  Training changes CORA's search, but the Qwen features add nothing. The language covers 394/395 here, so the order
  is the binding constraint.
- **dev60 atlas** (exposed, same-shape real ARC tasks): the v1 language fits 1/60. On real tasks the bottleneck is
  expressivity (G2).
- **Records:**
  - NEURAL_CORA_V1_PILOT_REPORT.md;
  - NEURAL_CORA_V1_EXPRESSIVITY_AND_FAILURE_ATLAS.md;
  - NEURAL_CORA_V1_27P64_COMPETITION_ROADMAP.md (section 5 decision);
  - the capability audit (updated);
  - claim ledger row 24.
- **Poster and explainer V2:** "No result yet" became the pilot result (poster prose 349; selftest PASS; pixel-identical).
- **Also updated:** the poster abstract (one sentence, still 1 page) and the paper outline section 6b.
- **STOPPED as the directive requires.** Next justified experiment: G2 `ncv1-g1`, which exposes existing native
  primitives in the typed IR. It needs the user's approval of a frozen protocol. No Kaggle submission.

**EARLIER (2026-10-19 22:40Z; superseded: the pilot FINISHED, G1 = NO-GO, see above): NEURAL-CORA V1 PILOT RUNNING. The protocol was FROZEN at commit 081c1d3 before any
training.**
- **Two detached drivers:**
  - prep: scripts/neural_cora_v1_prep.sh, PID 3709079 (status in outputs/neural_cora_v1/logs/prep.status);
  - scored: scripts/neural_cora_v1_run.sh, PID 3737323 (status in outputs/neural_cora_v1/logs/run.status). It waits for
    PREP_DONE, checks that the protocol is committed, then runs train -> run -> evaluate and writes RUN_DONE. Any
    refusal is logged as "STOP: ...".
  - atlas: scripts/neural_cora_v1_atlas.sh, PID 3744901. It waits for RUN_DONE, then runs the dev60 expressivity
    atlas (exposed tasks; the solve stage reads no answers, the score stage alone does) and writes ATLAS_DONE in
    logs/atlas.status.
- **Single reproduction script:** scripts/reproduce_neural_cora_v1_pilot.sh.
- **Data audit:**
  - 3300 / 330 / 220 / 420 tasks;
  - 0 execution problems, 0 exact duplicates, 0 held-out signatures in train;
  - primary held-out set 395 of 420 (25 template-aliased tasks excluded: 16 delete-largest, 9 line-by-size);
  - audit sha 075e8b64, primary sha 8f647512.
- **Progress, 23:09Z:**
  - PREP_DONE at 23:08:31Z. Qwen features: 0.30 s per task, peak 7.51 GB.
  - Training done. L1: 1560 steps, best val loss 0.540 (epoch 6). L1h: best val loss 0.461 (epoch 28). L0s: 2.233.
    The weight hashes changed; details in models/training_log.json.
  - `pilot run` started 23:09:25Z.
  - Pace: about 21.6 s of wall time per task on 2 workers. ETA RUN_DONE about 02:45Z.
  - The context arm C0 (native inducer) overruns its declared 5 s CPU budget: mean 25 s, max 113 s, because native
    checks its deadlines between phases. The typed arms use about 6 s per task. Report this. Nothing was changed
    mid-run; the protocol is frozen.
- **After a reboot:**
  1. Confirm that no cora_neural_v1.pilot process is alive (exact ps).
  2. If prep.status lacks PREP_DONE, rerun prep.
  3. Then rerun scripts/neural_cora_v1_run.sh. `pilot run` appends missing rows, so it resumes; `train` reruns
     deterministically (the same seed).
- **Earlier block, same pilot:**
- **Running:** `sh scripts/neural_cora_v1_prep.sh`, driver PID 3709079, started 22:24:17Z. Log and status:
  outputs/neural_cora_v1/logs/ (prep.status ends with PREP_DONE when finished).
- **Steps:** freeze -> generate -> audit (CPU), in parallel with Qwen features (GPU 0) -> targets (1 worker) -> hand
  features.
- **Reboot behaviour:** every step is deterministic and overwrites its outputs, so rerun the same script. Check first
  that no `cora_neural_v1.pilot` process is alive (exact `ps`, no pkill -f).
- **Code changes:**
  - cora_neural_v1: audit.py (template-alias primary set), state.py (reasoning state S_t and observable diagnoses);
  - search records pred_at, so budgets are exact truncations;
  - train_heads logs steps, gradient norms and weight hashes;
  - evaluate.py implements the preregistered G1 gate;
  - pilot.py writes outputs/neural_cora_v1;
  - 15 tests pass.
- **Dev smoke test (TRAIN families, 12 IID tasks; engineering only, not a result):**
  - C+@1000, C+H@1000, L1@500, L1h@500 solve 12/12; L0 2/12; L0s 3/12; C0 4/12;
  - L1 training: 420 optimizer steps, and the weights changed.
- **NEXT:**
  1. Write and commit records/NEURAL_CORA_V1_PILOT_PROTOCOL.md (frozen) BEFORE `train`.
  2. Then: `pilot train` (GPU 0), `pilot run` (2 workers, nice 10; about 2.5-3 h), `evaluate`.
  3. Write the records the directive requires (capability audit, data audit, report, atlas, roadmap, spec) and the
     kaggle/neural_cora_v1 scaffold. STOP after the pilot is evaluated.
- **Also done:** docs/summit_demo_20261023/ka95aa62f67d9_visual_replay.html, built by build_visual_replay.py (an
  offline, static, recorded replay).

**NEWEST (2026-10-19, late): CANCER-LESION REVIEW V2 POSTER + EXPLAINER (user addenda; presentation only, no experiment).**
- **Sources of truth:** docs/summit_20261023_reframe/poster_cancer_lesion_review.org and
  explainer_cancer_lesion_review.org (labelled V2).
- **Build:** `sh scripts/build_summit_org.sh cancer`:
  - poster: 1 x A0, bottom margin 1.98 cm;
  - explainer: 13 x A4.
- **Checks:**
  - both rebuild byte-identically;
  - `selftest` PASS for all four Org documents;
  - embedded images pixel-identical to figures/ (poster 7/7, explainer 8/8).
- **Content:**
  - panels A and B: real ISIC_0000013 (CC-0; its record documents a histopathology-confirmed invasive melanoma) and its
    own ISIC 2018 Task 1 mask (CC-0);
  - panel C: the author's annotated maize leaf DSC_0042, crop magnified x2. It is leaf 1 of
    segmentors_backbones/projects/real_leaf_gallery_20261018, read only; unpublished;
  - a new headline on learning from failure, with representation, rules and new data defined;
  - "Supported or failed?";
  - plain terms (failed, exposed task and certified are defined);
  - the "AI coding assistance" and "Authorship pending review" lines removed at the user's request.
- **Words:** poster prose 350 (scripts/count_poster_words.py).
- **Docs:** CANCER_LESION_IMAGE_PROVENANCE.md, CANCER_LESION_POSTER_CHANGELOG.md, ORG_TO_PDF_README.md.
- **Outstanding:**
  - collaborator review (Toni, Chris, Pierce);
  - permission from the data owners to show the maize tile;
  - the organizer's poster format;
  - the user's print approval.
- **Neural-CORA pilot:** still PAUSED (no training).

**NEWEST (2026-10-19 ~21:30Z): SCIENCE-FIRST POSTER + EXPLAINER (user addendum; presentation only, no experiment).**
- **Sources of truth:** docs/summit_20261023_reframe/poster_science_first_review.org and
  explainer_science_first_review.org.
- **Built by** `sh scripts/build_summit_org.sh all` (Org -> LaTeX -> PDF; scripts/export_summit_org.el):
  - poster: 1 x A0;
  - explainer: 11 x A4.
- **Checks:** both rebuild byte-identically; `selftest` PASS for both; the poster's 5 figures are pixel-identical to
  the pinned PNGs.
- **Docs:** ORG_TO_PDF_README.md, POSTER_SCIENCE_FIRST_CONTENT.md (361 body words), POSTER_SCIENCE_FIRST_CLAIM_AUDIT.md,
  POSTER_90S_SCIENCE_FIRST.md, POSTER_3MIN_SCIENCE_FIRST.md, SCIENCE_FIRST_CHANGES.md (+ _comparison.png),
  ORG_BUILD_MANIFEST.json; optional .pptx.
- **The Toni line is removed** from the poster; there is a factual acknowledgment in the explainer, section 11.
- **AWAITING:** collaborator review (Toni, Chris, Pierce), organizer poster format, and the user's print approval.
  Nothing is promoted.
- **Neural-CORA pilot: PAUSED** at the dev engineering check, by this addendum's "do not chase experiments before Oct 21".
  - Done: the dev corpus (880/110/110/11), targets and NVARC-encoder + hand features
    (outputs/neural_cora_v0_dev/).
  - Next: dev head training -> dev check (TRAIN families only) -> freeze records/NEURAL_CORA_PILOT_v0_PROTOCOL.md ->
    the full run.
  - Code: cora_neural_v1/ (10 tests pass). Audit: records/NEURAL_CORA_ARCHITECTURE_AUDIT_20261019.md.

**NEWEST (2026-10-19 ~18:40Z, session d176233f). THREE NEW USER DIRECTIVES, in this priority order (the user's own):**
1. Phase 2a DONE: **NO-GO** under the frozen rule (evaluated ~19:10Z).
   - Coverage 40/40/40 in 3.93 h; hashes ok; 0 errors.
   - A and B each certified 6 (5 correct, 1 WRONG, on p2a_bad364b6c313).
   - V certified 0; exploratory 2/0, 1 of them new (p2a_abf8c09c562e).
   - The GO rule needed 2 new correct answers. The version is closed; it was not retuned.
   - Record: records/CORA_REASONING_V2_PHASE2A_EXECUTION_20261019.md sections 3-4; ledger row 23; both explainers'
     section 10 updated.
2. **Neural-CORA v0.1** ("Learn to propose and revise executable hypotheses"; the full text is in the session transcript).
   - It is ONE CORA-owned architecture: no router, no ensemble, no attempt-2 filler.
   - Phase 0 audit -> records/NEURAL_CORA_ARCHITECTURE_AUDIT_20261019.md.
   - Then cora_neural_v1/ typed IR + tests; a learned proposal prior (LoRA ranker/proposer); a preregistered bounded pilot
     (L0/L1/C+ first; at most 2 CPU workers + 1 GPU, 6 h); classification verdicts.
   - Kaggle: prepare only.
   - Required artefacts: records/NEURAL_CORA_ARCHITECTURE_AUDIT_20261019.md, docs/NEURAL_CORA_SINGLE_ARCHITECTURE_v0.md,
     records/NEURAL_CORA_PILOT_v0_PROTOCOL.md, cora_neural_v1/, outputs/neural_cora_v0/,
     records/NEURAL_CORA_PILOT_v0_REPORT.md, kaggle/neural_cora_v1/ (scaffold).
   - The earlier "ARCHITECTURAL SUBSUMPTION STUDY" paste is folded into Phase 0. A read-only background audit
     (architectures + NVARC synthetic-program availability/licences) writes records/CORA_NVARC_SUBSUMPTION_AUDIT_20261019.md.
     Check it, then merge it into the Phase 0 audit.
   - The user also said: "this doesnt halt cora improvement --- still keep improving CORA to real reasoning model".
3. Summit (print freeze Oct 21):
   - Qwen-architecture review set:
     - DONE: poster_qwen_architecture_review.{tex,pdf,pptx}, with POSTER_QWEN_ARCHITECTURE_NOTES.md (changes, claim
       audit, provenance, reproduction).
     - Its 4 new figures: arc_intro_large, three_failures_ILLUSTRATIVE, real_rule_large, construction_58_outcomes. The
       committed PNGs are byte-identical.
     - Column 3: two solid lanes + ONE small dashed learning loop (directive section 9 wording).
   - DONE: explainer_qwen_architecture_review.{tex,pdf}. It has 15 pages; section 8 is new (about 2.4 pages): the
     addendum's 9 points + Neural-CORA architecture, objective, controls, limitations + an NVARC-first / CORA-first /
     unified comparison. Section 12 defines the terms kept off the poster.
   - Awaiting collaborator review (Toni, Chris, Pierce) and the user's print approval. NOTHING is promoted to
     docs/summit_poster/.
   - Higher-level draft DONE: docs/higher_order_reasoning/Learning_What_to_Change_Discussion_DRAFT.{md,org} (v0.2).

**NEWEST DIRECTIVE (2026-10-19): "CORA | Learning when a hypothesis is not enough"** (Phases 0-4; ONE bounded DEV pilot;
no Kaggle, no push, no protected data, no Step B changes). Progress:
- [x] Phase 0 gap audit records/CORA_REASONING_V2_GAP_AUDIT_20261019.md (9fd65ed): G-grow covers 13% of task types; native's
      correct candidate is absent on >=48 of 60 dev tasks (coverage, not selection, binds)
- [x] Phase 1 cora_revision_v2/scene_reasoner.py (geometry x colour policy version space, ambiguity, fold-local re-search);
      smoke on 8 in-sample tasks: 3 correct unique predictions (1 new: 00dbd492), 0 certified (fold fragility), 0 wrong
- [ ] Phase 2 GO pilot: needs a USER-DESIGNATED fresh non-autopsy real cohort (permitted pools exhausted); not run
- [x] 2026-10-19 (session d176233f, after "CLARIFICATION ON ARC TASKS AND PHASE 2" + "dont block -- use the 1000 training set"):
      COHORT AUDIT records/CORA_REASONING_V2_COHORT_AUDIT_20261019.md (cora_revision_v2/cohort_audit.py; output sha 7c2f807d):
      548 in scope -> exclude dev60/frozen-120-by-rule/stand-ins/used -> 288 -> additions-only (train pairs) 100 -> first 40 in
      the published order; overlaps 0. BUT Step B's LOCKBOX_PROTOCOL.md partitions THIS SAME FILE (Experience 600 / Promotion 200
      / Lockbox 200; E_transfer 150 inside Experience): ~55% of any cohort is expected protected, membership not checkable
      without Step B's manifest/firewall -> cohort UNVERIFIED, Phase 2 NOT launched. Needed: user-authorized membership-only check
      (one clear/not-clear bit per candidate) -> cohort = first 40 clear (declared fallbacks in the record)
- [x] 00dbd492 fold fragility DIAGNOSED records/CORA_REASONING_V2_FOLD_FRAGILITY_00dbd492_20261019.md: the test needs the
      size-32 -> colour 3 table entry that ONE demonstration supports (support 16:3, 24:2, 32:1); fold 0 abstains
      (UNSEEN_TABLE_KEY), folds 1-3 correct; not ambiguity/representation/defect; failure-blind reasoner gives the same answer
      (diagnosis changes explanation + tier, not the answer). Certification unchanged -> EXPLORATORY (uncertified)
- [x] code 4c4c30d: scene_reasoner fold_detail (UNSEEN_TABLE_KEY / POLICY_UNDEFINED / WRONG_UNIQUE / TIE / EMPTY) +
      table_support + per-view cap stats; cora_revision_v2/diagnosis.py (8 labels; causes / probe / result / uncertainty /
      next action; tiers CERTIFIED / EXPLORATORY / DISCOURAGED / NONE); cora_revision_v2/run_v2.py (blind engineering runner,
      RLIMIT_CPU per task, engineering corpora only); tests/test_fhr.py 19 pass
- [x] Phase 2 protocol DESIGN FROZEN, NOT AUTHORIZED: records/CORA_REASONING_V2_PHASE2_PROTOCOL_20261019.md (2a: A native, B
      matched search, V v2; 2b: D diagnosis-selected revision, C strong blind, Cm matched-compute blind, E shuffled; F forensic)
- [x] paper outline docs/PAPER_OUTLINE_REVISION_20261019.md (construct / diagnose / revise)
- [x] ENGINEERING RUN DONE (eng_run.sh; rc 0; coverage 58/58 + 60/60): 0 certified on 118 exposed tasks; exploratory pool 3 correct
      (00dbd492, 22eb0ac0, 3aa6fb7a) + 1 wrong (2546ccf6); dev60 1 correct (kf892487f1049, native already right). Primary diagnoses
      pool: 46 GEOMETRY_GAP->ABSTAIN, 3 ->GUARDED, 5 COLOUR_POLICY_GAP, 3 FOLD_FRAGILITY, 1 DISAGREE; dev60: 25 MULTIPLE_ACTIONS + 7
      non-additive (->TYPED_SCENE_TRANSFORM), 23 ->ABSTAIN, 3 ->GUARDED, 1 colour, 1 disagree.
      TWO-ATTEMPT STUDY (cora_revision_v2/two_attempt_study.py, evaluator-side, NO submission): native attempt 2 duplicates attempt 1
      in 50/58 and 59/60 outputs; pool 7 -> 8 (FILL) / 9 (REPLACE2), 0 lost; dev60 12 -> 12. In-sample only.
- [x] summit supplement docs/summit_20261023_reframe/supplement_v2.{tex,pdf} (1 page) + figure
      docs/summit_poster/figures/fig_v2_uncertified_00dbd492.png (pinned bundle docs/summit_demo_20261023/data/v2_witness_00dbd492.json,
      builder build_v2_bundle.py; scripts/summit_figures.py). Review poster NOT changed (awaiting collaborators; freeze Oct 21).
      Ledger rows 18-21, README rows, paper section 8.21, STAGE_LEDGER entry.
- [x] selection family (typed scene transformation slice 1): cora_revision_v2/selection.py + reason(families=("grow","select")) +
      selection-aware per-demo probe (3e5f1d4; 20 tests pass). NOTE: the union can CREATE disagreement (a base hypothesis that fits
      the demos may predict differently) -> apply revision where diagnosed, not everywhere (Phase 2b D vs C)
- [x] SELECTION RUN DONE (eng_sel_run.sh, rc 0, 58/58 + 60/60, no errors): 0 certified; exploratory pool 4 correct / 0 wrong
      (2546ccf6 wrong->correct, 2nd attempt only, support tie), dev 2 correct (kcc459b523a80 new, native harness already solves);
      0 lost; 2x CPU; 22eb0ac0 unique -> disagreement (union effect). Two-attempt replay unchanged. Ledger row 22.
- [x] 2026-10-19 USER AUTHORIZED ("FINISH ENGINEERING AND TEST REAL-TASK GAINS"): ONE isolated eligibility check + ONE Phase 2a run.
      ELIGIBILITY: tools/stepb_eligibility/check_eligibility.py (5c5401a; python -I; Step B lockbox manifest task_id+split only,
      sha-verified; E_transfer by Step B's frozen public salt rule; firewall NOT opened) -> PASS, 44/100 eligible
      (outputs/cora_revision_v2/eligibility/eligible_ids_20261019.json, sha 8637ac65). Cohort = first 40 eligible.
      PHASE 2a: cora_revision_v2/phase2a.py; bundle built (opaque keys; keymap in phase2a_evaluator/); preflight PASS
      (freeze.json; commit 4b95e86; 21 tests; V + native regressions identical); f_B 1.053.
- [ ] RUNNING (detached, started 15:03Z): python -m cora_revision_v2.phase2a run (log outputs/cora_revision_v2/phase2a/run.log;
      rows phase2a/rows_{V,A,B}.jsonl; 2 workers; 6 h wall cap from phase2a/start_time.txt). Resumable: rerun the same command (skips
      finished arm-task rows; the wall cap counts from the original start). NEVER rebuild the bundle (opaque keys would change).
      WHEN DONE: python -m cora_revision_v2.phase2a evaluate (FIRST read of answers) -> GO/NO-GO -> records (execution record
      section 4, ledger, README, supplement, paper) -> if NO-GO: close this version, propose ONE part-aware intervention; if GO:
      prepare Phase 2b. No retuning on the cohort.
- [x] (superseded) eng_sel_run.sh launch note: grow+select everywhere = blind arm C; rows rows_*_sel.jsonl.
- [ ] 2026-10-19 ~11:45 local: POSTER DIRECTIVES (two pastes: "VISUAL-FIRST ARC SUMMIT POSTER AND CLEAR EXPLAINERS" and the newer
      "FINAL ARC PRIZE RESEARCH SUMMIT POSTER, VISUAL-FIRST REDESIGN"; the newer one governs file names). Presentation work only:
      no new experiments, no Kaggle, no push, original docs/summit_poster/ untouched, no authorship change.
      DELIVERABLES (docs/summit_20261023_reframe/): poster_visual_final_review.{tex,pdf,pptx}; POSTER_VISUAL_CONTENT.md;
      POSTER_CLAIM_AUDIT.md; POSTER_FIGURE_PROVENANCE.json (+ figures/PROVENANCE.json); POSTER_90_SECOND_SCRIPT.md;
      POSTER_3_MINUTE_WALKTHROUGH.md; REVIEW_CHECKLIST.md; explainer_visual_review.{tex,pdf} (8-12 pages, every figure explained,
      demo commands); figures in docs/summit_20261023_reframe/figures/.
      VERIFIED SO FAR: ka95aa62f67d9 bundle (real_task b06073a7, real_witness f0da3a8d): colour 1 = BLUE objects -> ray up-left,
      colour 2 = RED objects -> ray down-right, rays in the object's own colour, 10x10 grids, 3/3 folds, answer == evaluator,
      failure-blind found the same rule. The directive's "red/colour-1" is WRONG (colour 1 is blue): use blue/red.
      dev60 asset-loaded audit = outputs/funnel_v0/eval_dev60_native_assets.json (54d8d744). PPTX converter scripts/poster_to_pptx.py
      (PDF -> editable text boxes + original PNGs; hardcoded to docs/summit_poster; needs a path option). 52-page deep explainer:
      NOT found on Athe (narrow search) -> say so, do not claim access.
      PLAN: col 1 = real 00dbd492 intro grids (from pinned v2_witness bundle) + ILLUSTRATIVE A-D inadequacy panels; col 2 = CORA
      pipeline (solid), 60-task audit (6 / 26, asset-loaded object branch), real ka95aa62f67d9 witness, 0/58 negative, small NVARC box;
      col 3 = proposed revision loop (solid = implemented, dashed = not validated), v2 00dbd492 "CORRECT DEVELOPMENT PREDICTION - NOT
      CERTIFIED", automatic rule-language extension (Step B, 475/497 last recorded, no verdict, not integrated), transfer schematic
      (FUTURE, NOT TESTED), bottom line. Phase 2a only if complete AND validated (otherwise explainer says RUNNING/PENDING).
      Phase 2a at first save: 11:36 local, still running (A/B/V rows growing; ~4.6 h projected, cap 6 h). NEXT: compare eng vs sel per task (gains, losses, new disagreements);
- [x] 2026-10-19 12:30 POSTER SET DONE (73a4b11, 2442498): docs/summit_20261023_reframe/poster_visual_final_review.{tex,pdf,pptx}
      (A0 one page; ~405 body words; figures from pinned bundles via scripts/summit_visual_figures.py at the measured 9.37 in width;
      PPTX via scripts/poster_visual_to_pptx.py, parity checked by a shape render because LibreOffice cannot load PPTX here);
      explainer_visual_review.{tex,pdf} (12 pages); POSTER_CLAIM_AUDIT.md, POSTER_VISUAL_CONTENT.md, POSTER_FIGURE_PROVENANCE.json,
      POSTER_90_SECOND_SCRIPT.md, POSTER_3_MINUTE_WALKTHROUGH.md, REVIEW_CHECKLIST.md. Colour fix: colour 1 = BLUE (up-left).
      Both demos validated (rc 0 with numpy). FHR = failure-conditioned hypothesis revision (user). Original poster untouched.
      WAITING: Toni/Chris/Pierce review (Oct 20); organizer size guide; print approval (Oct 21).
- [x] 2026-10-19 HIGHER-ORDER DISCUSSION DRAFT (5ec7e40): docs/higher_order_reasoning/{Learning_What_to_Change_Discussion_DRAFT.md,.org,
      ARC_2025_CHRIS_SOURCE_NOTES.md, DISCUSSION_SOURCE_AND_ATTRIBUTION_LEDGER.md}. Transcript voice_note/arc_conversatn.md verified
      (start-time segments, no diarization); 2025 hackathon: slides ~/Downloads/MMCV Lab ARC-AGI 2 HACKATHON.pdf (Chimdi Walter
      Ndubuisi + Christian Fluharty) + /home/cnptp/ARC-AGI code; NO scores, NO division of labour recorded; Chris = Christian
      Fluharty TO CONFIRM. Pierce project = pipeline/sb_class_project (user-confirmed), continues in _nature_program (read-only).
      Org export validated with emacs (rc 0). NEXT: user circulates the .org after confirming Chris's identity.
- [x] 12:35 poster neural box = "Two approaches to ARC" (NVARC reproduction 27.64% not CORA | CORA 0.00%) + open neural-symbolic
      question (a3d04b4); explainer p.8 rewritten from the originality audit (5cbda8a). Paths: docs/summit_20261023_reframe/
      poster_visual_final_review.{pdf,pptx}, explainer_visual_review.pdf.
- [ ] PHASE 2a WHEN DONE: python -m cora_revision_v2.phase2a evaluate  ->  python -m cora_revision_v2.phase2a_report  ->
      records (execution record section 3-4; ledger row; README; explainer p.10) -> GO: Phase 2b protocol for approval (do not
      launch) | NO-GO: close version; run the staged residual-geometry probe (scratchpad copy: outputs/cora_revision_v2/
      characterization/ will hold it), compare limitations A part representation / B relational ops / C composition-colour,
      choose ONE intervention, draft its protocol.