# Claim audit: visual-first review poster (`poster_visual_final_review.pdf`, 19 October 2026)

Every number and factual claim on the poster is listed below with its source and status.
- **Ledger:** `records/CORA_SUMMIT_CLAIM_LEDGER_20261017.md`; row numbers refer to it.
- **Hashes:** the first 16 hex digits of sha256.
- **Phase 2a:** a run, not a claim, so it is **not on the poster**. Its result is added only after its integrity
  checks pass and the ledger is reconciled.

## Numbers and claims

| # | poster claim (block) | source | status |
|---|---|---|---|
| 1 | "6 answers accepted, all correct" (Fitting is not enough) | ledger row 2; `outputs/funnel_v0/eval_dev60_native_assets.json` (54d8d744): CERTIFIED_CORRECT 6, incorrect_accepted 0 | VERIFIED |
| 2 | "26 tasks where every rule that fit the examples failed the test" | ledger row 3; same file: FIT_BUT_ALL_WRONG 26 (with the frozen assets; 27 without) | VERIFIED; the asset-loaded configuration is used, as submitted |
| 3 | "60 exposed ARC-AGI-2 training tasks; CORA's object reasoner as submitted" | ledger rows 1–3 | VERIFIED. Object branch only, not the whole harness (12/60, row 4), and the two are not mixed |
| 4 | real task ka95aa62f67d9: the rule, and blue up-left / red down-right | ledger row 12c; `docs/summit_demo_20261023/data/real_witness.json` (f0da3a8d), `real_task.json` (b06073a7) | VERIFIED against the grids: colour **1 = blue** objects send a ray up-left (NW), colour 2 = red down-right (SE), each in the object's own colour. The directive's "red/colour-1" was wrong and is corrected here |
| 5 | "rebuilt 3 of 3 times with one example held out" | `real_witness.json` folds: SUCCESS × 3 | VERIFIED |
| 6 | CORA's output is correct | `real_witness.json` committed == `real_task.json` evaluator_answer | VERIFIED (the evaluator's answer, read only in the evaluator step) |
| 7 | "a constructor that ignored the failure record found the same rule" | `real_witness.json` controls: C2G_same_rule true, C2G CERTIFIED_WITH_EXTENSION | VERIFIED |
| 8 | "an exposed task chosen in development" | ledger row 12c ("selected by the autopsy") | VERIFIED |
| 9 | "0 / 58 new verified solves from rule construction"; no wrong answers; no advantage from the failure record | ledger row 12f; `records/CORA_FHR_GUARD_GENERALIZATION_PROTOCOL_20261018.md` | VERIFIED (all construction arms 0; 0 wrong, 0 lost; no discordant pairs). Frozen native solved 1, which the poster does not claim as a construction result |
| 10 | "58 separately selected, still exposed training tasks" | ledger row 12f | VERIFIED |
| 11 | native CORA 0.00% | ledger row 13; Kaggle 57144804 | VERIFIED |
| 12 | CORA with rule construction 0.00% | ledger row 15; Kaggle 57354496 (CORA_FHR_V1) | VERIFIED |
| 13 | "Two approaches to ARC": NVARC / Qwen3-4B 27.64%, a reproduced third-party method, not CORA, with neural training and per-task adaptation; CORA 0.00% | ledger rows 13–15; Kaggle 57160429 and 57144804; `records/KAGGLE_NEURAL_V1_ORIGINALITY_AUDIT_20261014.md` (checkpoint, per-task LoRA test-time training and selection unchanged; six deployment changes) | VERIFIED; attributed to NVARC, not CORA |
| 13b | "Open question: can learned neural proposals help an executable reasoner find which part of a hypothesis to revise?" | a question, not a result; the earlier answer-combination audit was negative (ledger row 16) | STATED AS A QUESTION |
| 14 | CORA-v2 00dbd492: correct development prediction, not certified; colour support azure 3 / yellow 2 / green 1 example; "hide that example: the check fails" | ledger rows 18–19; `docs/summit_demo_20261023/data/v2_witness_00dbd492.json` (bc252782) | VERIFIED. "The check fails" means that fold abstains (UNSEEN_TABLE_KEY), not that it predicts wrongly |
| 15 | "On 118 exposed development tasks: 4 correct and 1 wrong exploratory guesses; nothing certified" | ledger row 21 (base v2, growth only) | VERIFIED. With object selection added (row 22): 6 correct, 0 wrong, still 0 certified. That variant is reported only in the explainer |
| 16 | "475 of 497 proposal units done (19 October); no verdict" (Inventing new operations) | Step B counts-only administrative watcher, `pipeline/CORA_reports/stepb_watch/stepb_watch.log`, line at 2026-10-19T16:30:15Z: K2 475/497, errors 0, no marker, no hash file | VERIFIED from the administrative counts only; no protected output was opened |
| 17 | "a separate CORA experiment … not part of CORA-v2 or any Kaggle entry" | `Reasoning_Project/RESUME_STAGE1.md` (separate repository and run); arc2026 code | VERIFIED |
| 18 | "Recognizing an inadequate explanation: partly built (CORA-v2)" | `cora_revision_v2/diagnosis.py`; ledger rows 19 and 21 | VERIFIED as engineering; its benefit is not validated |
| 19 | "Knowing which revision helps: not yet shown" | Phase 2b not run; ledger rows 9–12f | VERIFIED |
| 20 | "CORA never sees the hidden answer" | blind runners (`run_v2.py`, `measure.py`); evaluator separation | VERIFIED |
| 21 | the research question was shaped in discussions with Toni Kazic | recorded conversation, `voice_note/arc_conversatn.*` (17 October) | VERIFIED as a recorded discussion. Wording pending Toni's approval |
| 22 | biology: proteins, omics, plant phenotypes, maize lesion-mimic pathways | proposals only (ledger row 17) | labelled FUTURE, NOT TESTED; no biological result is claimed |

## Diagram status: solid means implemented and tested, dashed means proposed

| box | outline | why |
|---|---|---|
| find objects and parts | solid | native's seven segmentation views |
| construct competing hypotheses | solid | CORA-v2's version space |
| test them against the examples | solid | exact demonstration fit; leave-one-out |
| Is the explanation adequate? | solid (bold) | v2 detects no fit, disagreement, fragile folds |
| diagnose why | **dashed** | typed diagnoses exist as engineering; not validated |
| wrong objects: revise the objects | **dashed** | representation revision is not built |
| missing rule: construct a rule | solid | built (CORA-FHR); narrow (one real task) |
| too little evidence: keep alternatives | solid | v2 keeps two attempts or abstains |
| arrows from "diagnose why" to the three revisions | **dashed** | choosing the revision is not validated |
| test the revision: keep or roll back | solid | fold rebuild, reversible install and restore |
| predict; independent evaluation | solid | committed predictions; separate evaluator |
| learning which part to revise; testing on scientific data | **dashed** | research goals |

## Wording checks

- **No overclaims.** None of the following appear: "learns from failure", "generalizes", "certified", "56/58",
  "impossible", "grammar invention achieved", "biology tested".
- **NVARC** is never presented as CORA's.
- **"Exploratory"** is used for the v2 guesses, kept separate from "certified".
- **The 50/5/3 forensic ceiling** is not on the poster; it is in the explainer with its restricted scope.

## Citations (footer)

- **Popper:** Cropper and Morel (2021), learning programs by learning from failures.
- **DreamCoder:** Ellis et al. (2021).
- **LILO:** Grand et al. (2024).
- **Model Discovery Agent:** Murphy (2026).
- Years are as checked in commit e7dc937. The poster cites them by name and year only; the explainer gives the full
  references.
