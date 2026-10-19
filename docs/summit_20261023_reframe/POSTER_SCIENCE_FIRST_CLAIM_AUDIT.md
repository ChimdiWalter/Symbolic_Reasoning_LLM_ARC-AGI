# Claim audit: science-first review poster (19 October 2026)

**What it covers.** Each claim on `poster_science_first_review.pdf`: its evidence path, denominator, scope,
verification and permitted wording. The ledger is `records/CORA_SUMMIT_CLAIM_LEDGER_20261017.md` (cited by row).
Figures: `figures/PROVENANCE.json`.

| # | poster statement | evidence | denominator and scope | verification | permitted wording |
|---|---|---|---|---|---|
| 1 | the general question and the biology bridge | framing, not a result | — | Attributed to no one on the poster; the explainer (section 11) records the discussion with Toni factually | as written; no quotation marks; no attribution line |
| 2 | leaf schematic; "Observed pattern ≠ identified mechanism" | ILLUSTRATIVE SCHEMATIC drawn in TikZ in the `.org` | — | labelled "ILLUSTRATIVE SCHEMATIC, not data". No photograph, omics plot or pathway | "illustrative"; never "data" or "our maize result" |
| 3 | BOTTLENECK 1 · measured: CORA often cannot propose a usable rule | ledger 12f: arm EG had NO_PROPOSAL on 55/58, the failure-blind arm on 52/58. Ledger 23 (Phase 2a): 33/40 GEOMETRY_GAP for v2. Gap audit: native's correct candidate is absent on 48 or more of 60 | exposed or reused public training tasks; CORA's tested languages | rows `outputs/cora_fhr/rows_standin58_gen.jsonl` (0ff69e04); `phase2a_eval.json` (76783bb8) | "often cannot propose a usable rule". Never "cannot express ARC" or "impossible" |
| 4 | BOTTLENECK 2 · unproven: can it learn which part to revise? | no validated revision choice. The 58-task test had no failure-information advantage (0 discordant pairs; ledger 12f). The failure-blind constructor found the ka95aa62f67d9 rule. Phase 2b not run. The CORA-NVG negative | — | records cited in the explainer, sections 7 and 8 | "unproven" or "open"; never "learned" |
| 5 | SOLID loop nodes: find objects, propose rules, execute and test, supported?, predict and evaluate, test the revision | native v23 views, induction and leave-one-out (ledger 1–5); CORA-FHR construction with reversible install and fold rebuild (ledger 7–8, 12c, 12f: 3 proposals rejected); v2 hypotheses and diagnoses (ledger 21, 23); the separate evaluator (Phase 2a) | implemented, and run on recorded development tasks | code paths in the explainer, section 5 | solid = implemented and tested *under the recorded method*, not "solved" |
| 6 | DASHED: choose what to revise; learned priors; the retry loop | not validated. `cora_neural_v1/` exists with 10 unit tests; dev features only; no training or evaluation result | — | `records/NEURAL_CORA_ARCHITECTURE_AUDIT_20261019.md` | "proposed"; "no result yet" |
| 7 | "visible evidence only: no hidden answer" | solver interfaces read demonstrations and test inputs only. The Phase 2a rows had 0 answer fields. The evaluators are separate programs | design property; checked in Phase 2a | `phase2a_report.json` `rows_with_answer_fields: 0` | as written; never "CORA knows when it is wrong" |
| 8 | 00dbd492 grids; "each frame's fill colour depends on its size" | REAL: `v2_witness_00dbd492.json` (bc252782) | one exposed public training task | figure script asserts the bundle hash; the PDF embeds the pinned PNG pixel-identically | shows what an ARC task is |
| 9 | three causes (wrong objects, wrong rule, not enough evidence); "Memorization: fits the examples, fails the new input" | ILLUSTRATIVE (hand-drawn) | — | labelled ILLUSTRATIVE on its face | never "observed in CORA" |
| 10 | ka95aa62f67d9: "blue objects send a line up-left; red ones, down-right"; rebuilt 3 of 3; correct; exposed; not a competition solve; also found without the failure record | REAL: `real_task.json` (b06073a7), `real_witness.json` (f0da3a8d). The rule is `if colours == (1,): ray(NW,border) else ray(SE,border)`, with colour 1 = blue and 2 = red. Ledger 12c, 12d | 1 autopsy-selected exposed training task | the script asserts `committed == evaluator_answer`, all 3 folds SUCCESS and `C2G_same_rule` | "a development demonstration"; never "learning from failure" or "generalizes" |
| 11 | 0 / 58; 55 no rule proposed; 3 proposed but rejected; 0 verified; "Every variant: 0; no wrong answers" | ledger 12f. Arm EG: NO_PROPOSAL 55, ENGINE_REJECTION 2, LOO_FAILURE 1. Arms EG, C2G, DG and EGC: 0 certified, 0 wrong | 58 separately selected, exposed training tasks | the script asserts the counts from the pinned rows | "0 of 58 new verified solutions from rule construction". Not a Kaggle score |
| 12 | Visible doubt: "One example decides the green fill, so CORA-v2 keeps its correct guess uncertified" | REAL: v2 witness (bc252782); `records/CORA_REASONING_V2_FOLD_FRAGILITY_00dbd492_20261019.md`. The size→colour table support is 16:3, 24:2, 32:1. Fold 0 abstains. Tier EXPLORATORY; the evaluator labels it correct | 1 exposed development task | figure asserts `evaluator_correct` and `tier_v2 == EXPLORATORY` | "uncertified"; never "certified" or "verified" |
| 13 | Next: a trained prior would only order CORA's own search; no result yet | `cora_neural_v1/` (typed IR compiled to native programs; native interpreter; CORA's own generator). Dev-scale features only | — | architecture audit §8 | "proposed"; "no result yet" |
| 14 | NVARC (published Qwen3-4B method), reproduced: 27.64% public; native CORA and CORA with rule construction: 0.00% public | Kaggle 57160429 (27.64), 57144804 (0.00), 57354496 (0.00); ledger 13–16; `records/KAGGLE_NEURAL_V1_ORIGINALITY_AUDIT_20261014.md` | official public leaderboard, semi-private half | Kaggle CLI records | NVARC's score belongs to its published method; never a CORA or Neural-CORA score |
| 15 | "If revision selection works on ARC, test the reasoning procedure… on independently validated biological questions. [UNTESTED]" | proposal only | — | — | "untested"; no pathway, mechanism or omics claim |

**Removed from the poster** (the Qwen-architecture review had them):
- "A question shaped in discussions with Toni Kazic": **0 occurrences** in the built PDF (`pdftotext` grep). No Toni,
  Chris or Pierce credit appears on the poster; authorship is "pending collaborator review".
- The two parallel answer lanes: replaced by one loop with the learned prior inside it.

**Wording checks** (`pdftotext` grep on the built PDF):
- **No jargon:** 0 hits for LOO / leave-one-out, FHR, K2, Step B, oracle, OOD, causal, version space, grammar or
  semantic self-extension.
- **No overclaims:** 0 hits for "real reasoner", "understands", "knows what is wrong", "verified causal",
  "generalizes to science" or "already proposes".

**Figure provenance on the poster.** All five embedded figures are **pixel-identical** to the hash-pinned PNGs
(`pdfimages` vs `figures/*.png`), and each PNG's sha256 matches `figures/PROVENANCE.json`:
- REAL: `fig_arc_intro_00dbd492_large.png`, `fig_real_rule_ka95aa62f67d9_large.png`, `fig_construction_58_outcomes.png`,
  `fig_v2_uncertified_00dbd492_large.png`;
- ILLUSTRATIVE: `fig_three_causes_row_ILLUSTRATIVE.png`.
