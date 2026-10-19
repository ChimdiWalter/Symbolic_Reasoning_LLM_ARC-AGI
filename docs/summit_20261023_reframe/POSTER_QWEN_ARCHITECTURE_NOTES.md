# Qwen-architecture review poster: changes, claim audit and reproduction (19 October 2026)

**For:** Toni, Chris and Pierce, reviewing before the 21 October print freeze. This is a REVIEW version. It is not for
print until the user approves.

**What it is:**
- `poster_qwen_architecture_review.{tex,pdf,pptx}`, a separate version made under the user's addendum "ARC SUMMIT POSTER:
  MAKE THE QWEN–CORA IDEA VISIBLE". It also follows the later Neural-CORA v0.1 directive (section 9): "at most one small
  dashed learning loop".
- **Unchanged:** `poster_visual_final_review.*` and the submitted `docs/summit_poster/poster.pdf`.
- **Explainer:** `explainer_qwen_architecture_review.{tex,pdf}` is the companion.

## 1. What changed from `poster_visual_final_review`

| part | change |
|---|---|
| header | The subline now states the broader question: when an explanation is inadequate, how can a reasoner discover what is missing, choose what to revise, and test whether the revision helps? ARC-AGI-2 is the testbed. "A question shaped in discussions with Toni Kazic" is kept. |
| column 1, "Why reasoning fails" | The real 00dbd492 grids are larger (2.75 in, was 2.25 in). There are three illustrated failures with one sentence each: wrong objects, wrong transformation, not enough evidence. The third shows two rules that fit the example and give different answers. The memorization panel stays in the explainer. |
| column 2, "What CORA has demonstrated" | The pipeline diagram is removed; its steps are now the symbolic lane in column 3. The real ka95aa62f67d9 grids are larger (3.15 in, was 2.62 in). The rule is stated in plain words. A four-line checklist: constructed, correct development prediction, rebuilt 3 of 3 with one example left out, and a version blind to failures found the same rule. The note "exposed training task, not an unseen Kaggle success" is kept. 0 / 58 is shown with one square per task. |
| column 3, "How neural learning may help" | Two solid lanes with their official public scores. One small dashed learning loop, worded as in the directive. Then the sentence from the addendum, and the statement that the neural proposal interface is not implemented. The CORA-v2 and "From ARC to science" blocks are kept. Removed: the "Inventing new operations" block (Step B is now explainer section 7, with a footer pointer) and the "Two approaches" box. |
| legend | The [RUNNING] chip is removed, because no block on this poster is running. |

## 2. Claim audit for new or changed statements

| statement on the poster | source | status |
|---|---|---|
| "27.64%; public score; published method, reproduced; not CORA" | ledger rows 13–16; Kaggle submission 57160429 | VERIFIED |
| "0.00%; public score; original CORA research" | native 57144804 and CORA-FHR 57354496, both 0.00 (ledger) | VERIFIED |
| neural lane: Qwen3-4B (NVARC) → adapts to each task → candidate answer grids | `records/KAGGLE_NEURAL_V1_ORIGINALITY_AUDIT_20261014.md`: unchanged checkpoint, per-task LoRA test-time training, decoding | VERIFIED (plain-language description) |
| symbolic lane: CORA → finds objects → builds executable hypotheses → runs them and checks the examples | ledger rows 1–5, 7–8 | VERIFIED (description) |
| dashed loop: "Qwen learns a prior over objects and executable rules → CORA executes and checks them → feedback helps revise the next hypothesis" | Neural-CORA v0.1 directive, section 9 | PROPOSED; labelled "proposed learning loop" and dashed |
| "The neural proposal interface has not yet been implemented or experimentally validated" | No neural proposal of objects or rules exists. The CORA-side grid checker (`cora_neural_fusion/`) is unit-tested only, and it is not this interface. | VERIFIED |
| "the neural model outputs answer grids only" | `records/CORA_QWEN_FUSION_FEASIBILITY_20261019.md` section 3: "The model emits grids only." | VERIFIED |
| ka95aa62f67d9 checklist: constructed; correct; 3 of 3; a version blind to failures found the same rule | ledger 12c and 12d. The figure script asserts `committed == evaluator_answer`, all folds SUCCESS and `C2G_same_rule`. | VERIFIED |
| "0 / 58": 55 no rule proposed, 3 rule proposed but rejected by CORA's checks, 0 new verified solutions | `outputs/cora_fhr/rows_standin58_gen.jsonl` (sha 0ff69e04…), arm EG: NO_PROPOSAL 55, ENGINE_REJECTION 2, LOO_FAILURE 1. Protocol record, FINAL RESULT table. | VERIFIED |
| "Every variant found 0; no wrong answers" | same table: EG, C2G, DG and EGC each certified 0, with 0 wrong. The script asserts no CERTIFIED_WITH_EXTENSION. | VERIFIED |

All other statements are unchanged from the visual review poster and are audited in `POSTER_CLAIM_AUDIT.md`.

**Wording checks:**
- The poster text (`pdftotext`) has **no** LOO, FHR, K2, OOD, oracle, causal, grammar or semantic self-extension.
- "Certified" appears only in "nothing certified" and in the v2 figure tag "NOT CERTIFIED". Both are unchanged from the visual review poster.
- NVARC is never presented as CORA's work. Phase 2a is not on the poster, because no partial results are shown.

## 3. Figures: new files and provenance

All figures come from `scripts/summit_visual_figures.py`. Every entry is in `figures/PROVENANCE.json`, with sha256, sources and limitations. The previously committed figures are byte-identical.

| file | kind | source |
|---|---|---|
| `fig_arc_intro_00dbd492_large.png` | REAL | `docs/summit_demo_20261023/data/v2_witness_00dbd492.json` (pinned) |
| `fig_three_failures_ILLUSTRATIVE.png` | ILLUSTRATIVE | hand-drawn. It says so on its face; not a CORA result. |
| `fig_real_rule_ka95aa62f67d9_large.png` | REAL | `real_task.json` and `real_witness.json` (pinned) |
| `fig_construction_58_outcomes.png` | REAL | `outputs/cora_fhr/rows_standin58_gen.jsonl` (pinned; outcome labels only) |

## 4. Reproduce

```
cd /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
source ~/.venvs/lesegenv/bin/activate
python scripts/summit_visual_figures.py
cd docs/summit_20261023_reframe
SOURCE_DATE_EPOCH=1791763200 FORCE_SOURCE_DATE=1 pdflatex -interaction=nonstopmode poster_qwen_architecture_review.tex
cd ../..
python scripts/poster_visual_to_pptx.py --pdf docs/summit_20261023_reframe/poster_qwen_architecture_review.pdf \
    --out docs/summit_20261023_reframe/poster_qwen_architecture_review.pptx
```

**PPTX:**
- Text lines are editable. The figures are the original PNGs.
- TikZ diagrams (the lanes, the loop, the science chain) are 300-dpi pictures, so their labels are inside the pictures. This is how the converter works. Change diagram wording in the `.tex`.
- LibreOffice cannot open PPTX here, so the deck was checked by rendering its own shapes. The layout matches the PDF.

**Render checks (40 and 100 dpi):**
- three columns;
- no clipped text;
- no hyphenation (the poster sets `\hyphenpenalty=10000`);
- the bottom band and footer are on the page, with about 2.8 cm margin;
- poster text: about 600 words.

## 5. Open items

- The companion explainer pages: the architecture, training objective, controls and limitations.
- Collaborator review, with Toni's wording and Chris's identity to confirm.
- Print size is assumed A0 portrait; no organizer guide is on file.
- If Phase 2a finishes before the freeze, add its result only after it is evaluated under the frozen rule, and only if the user agrees.
