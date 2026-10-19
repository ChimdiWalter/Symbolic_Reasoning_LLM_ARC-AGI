# ARC-2026 delivery sprint: resume

Last updated 2026-10-19. Read this first.

## State

**NEWEST (2026-10-19 ~18:40Z, session d176233f). THREE NEW USER DIRECTIVES, in this priority order (the user's own):**
1. Finish the authorized Phase 2a untouched. RUNNING: 108/120 rows at ~18:35Z. Evaluate it ONLY with
   `python -m cora_revision_v2.phase2a evaluate`, then `python -m cora_revision_v2.phase2a_report`, and apply the frozen GO
   rule. Then update records/CORA_REASONING_V2_PHASE2A_EXECUTION_20261019.md.
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