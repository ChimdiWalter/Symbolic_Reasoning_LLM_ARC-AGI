# Review checklist: visual-first poster set (19 October 2026)

## Files (all in `docs/summit_20261023_reframe/`)

| file | what |
|---|---|
| `poster_visual_final_review.tex`, `.pdf` | the A0 review poster. **The PDF is the print master** |
| `poster_visual_final_review.pptx` | editable copy, converted from the PDF by `scripts/poster_visual_to_pptx.py` |
| `explainer_visual_review.tex`, `.pdf` | 12-page speaker explainer aligned to the poster |
| `figures/` with `PROVENANCE.json`, and `POSTER_FIGURE_PROVENANCE.json` (same content) | the five figures and their sources |
| `POSTER_VISUAL_CONTENT.md` | layout and exact text, for editing without LaTeX |
| `POSTER_CLAIM_AUDIT.md` | every number, mapped to the ledger and its source |
| `POSTER_90_SECOND_SCRIPT.md`, `POSTER_3_MINUTE_WALKTHROUGH.md` | spoken scripts |

**Unchanged:**
- the submitted poster `docs/summit_poster/poster.pdf` and the abstract;
- the earlier review set (`poster_review.*`, `explainer_review.*`, `PITCH_90S.md`). `PITCH_90S.md` belongs to the
  earlier draft; for this poster use `POSTER_90_SECOND_SCRIPT.md`.

## Build

```
python scripts/summit_visual_figures.py
cd docs/summit_20261023_reframe
SOURCE_DATE_EPOCH=1791763200 FORCE_SOURCE_DATE=1 pdflatex poster_visual_final_review.tex
SOURCE_DATE_EPOCH=1791763200 FORCE_SOURCE_DATE=1 pdflatex explainer_visual_review.tex    # twice
cd ../.. && python scripts/poster_visual_to_pptx.py
```

- The figure script checks every pinned input's sha256 before drawing.
- `pdflatex` writes into the current folder. The review builds used a temporary output directory; delete any stale
  `figures/` copy there first.

## Layout checks (done 19 October)

- **Page size:** one page, 2383.94 × 3370.39 pt = 84.1 × 118.9 cm, A0 portrait. **An assumption: no organizer poster
  guide is on file.** If the summit specifies another size, the layout must be redone, not scaled.
- **Overflow:** no overfull boxes in the poster or the explainer build logs.
- **Fonts:**
  - body 30 pt, secondary 26 pt;
  - diagram labels 22–26 pt; footer 22 pt; titles 36–100 pt;
  - figure text is at least 20 pt: figures are drawn at the measured block text width (677.3 pt = 9.37 in) and placed
    at 100%.
- **Visual inspection** of the full page at 40 dpi:
  - no clipped text, and nothing touches another column;
  - arrows and boxes in the loop diagram do not overlap;
  - the footer and bottom band are fully on the page.
- **Grids:** the real grids are drawn cell for cell from hash-pinned bundles.
  - 00dbd492: `v2_witness` bc252782.
  - ka95aa62f67d9: `real_task` b06073a7, `real_witness` f0da3a8d.
  - Colours and directions were checked against the data: **colour 1 = blue → up-left; colour 2 = red → down-right**.
    The directive's "red/colour-1" was wrong and is corrected everywhere; no file says otherwise.
  - The one illustrative figure is labelled ILLUSTRATIVE on its face.
- **Words:** about 405 of body prose (target 350–450), excluding the title, block titles, diagram labels and footer.
- **PPTX parity:**
  - 4 original PNGs placed at the PDF positions; 83 editable text lines (Arial in place of Helvetica);
  - diagrams inserted as 300-dpi pictures (19 clusters); the baseline box as an editable outline.
  - LibreOffice in this environment cannot load any PPTX, including the earlier one. Parity was therefore checked by
    rendering the PPTX's own shapes and comparing with the PDF: the layout matches.
  - **Open the PPTX in PowerPoint once before relying on it.** Arial metrics differ slightly from Helvetica.
- **Explainer:** 12 pages, every figure explained, jargon defined at first use. Phase 2a is marked RUNNING, RESULT
  PENDING.
- **Demos:** `sh docs/summit_demo_20261023/run_demo.sh` and `... --real` both exit 0 with numpy available.
  - They are recorded replays that re-execute the constructed operation standalone, not live engine reruns.
  - The system `python3` here lacks numpy, and the demo then prints its own "needs numpy" guard message.

## Integrity gates (see `POSTER_CLAIM_AUDIT.md`)

- Every number is matched to a ledger row. The 60-task numbers come from the asset-loaded object branch (6 and 26),
  never mixed with the whole harness (12/60).
- NVARC 27.64 is attributed as a third-party reproduction, not CORA. Native and CORA-FHR-v1 are both 0.00.
- Step B: 475/497, no verdict, from its counts-only administrative watcher (2026-10-19T16:30Z). No protected output was
  opened, and Step B is not presented as integrated.
- 0/58 negative shown prominently. The ka95aa62f67d9 caveats are present: exposed, chosen in development, failure-blind
  tie, not part of Kaggle.
- Certified and exploratory are kept separate. The 50/5/3 forensic scope is only in the explainer, with its
  restriction.
- Phase 2a is not on the poster. It is added only after completion, integrity checks and ledger reconciliation.

## Needs collaborator or user approval before printing

1. **Toni:** the wording of the central question and of the acknowledgement ("a question shaped in discussions with
   Toni Kazic").
2. **Chris and Pierce:** whether and how to be named. The biology examples are a labelled schematic list, not data.
   Is there an approved biological example?
3. **Authorship, credits and affiliations:** pending; nothing assigned.
4. **Poster size and orientation** from the organizer, if a guide exists.
5. **Phase 2a:** whether to add a one-line result if it completes and passes its checks (default: explainer only).
6. **Promotion to print:** the submitted poster stays unchanged until the user explicitly approves replacing it.

## Not available on Athe

- The 52-page companion and the newer drafts mentioned in the directives were not found. Only the 17 October package
  is in `~/Downloads`.
- The 17 October `Poster_Content_Draft.md` was already reflected in the earlier review draft. Its title is the one
  kept here.
