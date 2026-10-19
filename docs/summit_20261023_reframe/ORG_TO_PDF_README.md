# Building the summit review posters and explainers from Org (tested 19 October 2026)

The four Org files are the sources of truth:

| source (edit this) | output | pages |
|---|---|---|
| `poster_science_first_review.org` | `poster_science_first_review.pdf` (also `.tex`, exported by Org) | 1 × A0 portrait, 2383.94 × 3370.39 pt |
| `explainer_science_first_review.org` | `explainer_science_first_review.pdf` (also `.tex`, exported by Org) | 11 × A4, 595.276 × 841.89 pt |
| `poster_cancer_lesion_review.org` (**V2**, real medical image) | `poster_cancer_lesion_review.pdf` (also `.tex`) | 1 × A0 portrait |
| `explainer_cancer_lesion_review.org` (**V2**) | `explainer_cancer_lesion_review.pdf` (also `.tex`) | 13 × A4 |

Each PDF is compiled from the `.tex` that Emacs Org just exported from its `.org`. No hand-maintained `.tex` is used.
The older files are untouched: `poster_qwen_architecture_review.*`, `poster_visual_final_review.*`,
`explainer_qwen_architecture_review.*` (15 pages), `explainer_visual_review.*` and `docs/summit_poster/*`.

## Commands (run from the repository root, offline)

```
sh scripts/build_summit_org.sh poster      # Org -> LaTeX -> PDF for the poster
sh scripts/build_summit_org.sh explainer   # the same for the explainer
sh scripts/build_summit_org.sh all         # both
sh scripts/build_summit_org.sh poster_cancer      # the V2 cancer-lesion poster
sh scripts/build_summit_org.sh explainer_cancer   # the V2 cancer-lesion explainer
sh scripts/build_summit_org.sh cancer             # both V2 documents
sh scripts/build_summit_org.sh selftest    # proves each of the four .org files is the real source
```

**What one build does** (`scripts/build_summit_org.sh`):
1. Makes a fresh, empty temporary directory. It copies in only the `.org` and the `figures/` folder.
2. Exports with Emacs in batch mode, with no user init file:
   `emacs --batch -Q -l scripts/export_summit_org.el --eval '(summit-export "<dir>/<name>.org")'`.
   The repo-local `scripts/export_summit_org.el` registers two LaTeX classes:
   - `summit-tikzposter`: tikzposter, A0, 25 pt;
   - `summit-article`: an A4 article.
   Both start from `[NO-DEFAULT-PACKAGES]`, so every package is declared in the `.org`'s own `#+LATEX_HEADER`
   lines. The time-stamp comment is off, so the exported `.tex` is deterministic.
3. Runs `pdflatex -interaction=nonstopmode -halt-on-error <name>.tex` twice, with `SOURCE_DATE_EPOCH=1791763200
   FORCE_SOURCE_DATE=1` and `\pdftrailerid{}`.
4. Checks the page count (posters 1; science-first explainer 10–12; V2 explainer 11–13) and the page size (A0 or A4). It warns on any overfull box wider
   than 30 pt.
5. Copies `<name>.tex` and `<name>.pdf` next to the `.org`. It records `ORG_BUILD_MANIFEST.json`: the sha256 of the
   `.org`, the exported `.tex`, the PDF and every included figure, plus the tool versions, page count and size.

**How the poster `.org` is laid out.** Ordinary Org text and links, with three conventions:
- **Blocks:** `#+ATTR_LATEX: :options {<block title>}` above `#+BEGIN_posterblock` … `#+END_posterblock`. This is an
  Org special block, mapped to a tikzposter `\block` by one `\NewEnviron` line in the header.
- **Columns:** the one-line `#+LATEX: \begin{columns}`, `\column{0.333}` and `\end{columns}` commands.
- **Figures:** Org links into `figures/`, e.g. `[[file:figures/fig_real_rule_ka95aa62f67d9_large.png]]`, with
  `#+ATTR_LATEX: :width \linewidth :center nil`. The diagrams are TikZ inside `#+BEGIN_EXPORT latex` blocks.

All text, labels and captions are in the `.org`. Edit text where it stands; rebuild; inspect the PDF.

## Tested versions (Athe, 19 October 2026)

| tool | version |
|---|---|
| GNU Emacs | 29.3 |
| Org mode | 9.6.15 (bundled) |
| pdfTeX | 3.141592653-2.6-1.40.25 (TeX Live 2023/Debian) |
| tikzposter | 2014/01/15 v2.0 |
| environ | 2014/05/04 v0.3 |

**Other packages used:** helvet, fix-cm, amssymb, enumitem, tikz (positioning, arrows.meta, fit, calc, backgrounds),
geometry, microtype, float, booktabs, needspace, titlesec, caption, tabularx, newunicodechar and hyperref. All are in
TeX Live.

## Evidence that both builds work

| check | result |
|---|---|
| `build_summit_org.sh all` | exit 0. Poster: 1 page, A0. Explainer: 11 pages, A4 |
| a second rebuild | **byte-identical** `.tex` and `.pdf` for both documents. Hashes are in `ORG_BUILD_MANIFEST.json` |
| `build_summit_org.sh selftest` | **PASS for both.** It inserts a random sentinel line into a COPY of each `.org` (into the first poster block, and at the end of the explainer's section 1). It exports and compiles the copy, finds the sentinel in that copy's PDF with `pdftotext`, then discards the copy |
| poster figures | all 5 embedded images are **pixel-identical** to `figures/*.png` (`pdfimages` vs PNG). Each PNG's sha256 matches `figures/PROVENANCE.json`, which records its hash-pinned source bundle |
| explainer cross-references | no "??" in the PDF text. Org `CUSTOM_ID` and `#+NAME` links become `\ref` with the user's labels |
| hyphenation | `\hyphenpenalty=10000`; ragged-right text; no broken words |
| orphan headings | `titlesec` `nobottomtitles*` |

**V2 cancer-lesion documents (19 October 2026):**
- `build_summit_org.sh cancer`: exit 0. Poster: 1 page, A0. Explainer: 13 pages, A4.
- A second rebuild gave byte-identical `.tex` and `.pdf` for both.
- `selftest`: PASS for all four documents.
- Embedded images are pixel-identical to `figures/`: 7 of 7 in the poster and 8 of 8 in the explainer.
- The explainer's PDF contains no "??".
- Poster prose: 350 words (`python -I scripts/count_poster_words.py docs/summit_20261023_reframe/poster_cancer_lesion_review.org`).
- The image's provenance: `CANCER_LESION_IMAGE_PROVENANCE.md`.
- What changed from the science-first set: `CANCER_LESION_POSTER_CHANGELOG.md`.

## Figures

- **Generated by:** `python scripts/summit_visual_figures.py` (`~/.venvs/lesegenv`). It writes `figures/*.png`,
  `figures/PROVENANCE.json` and `POSTER_FIGURE_PROVENANCE.json`, and stops if any pinned input's sha256 differs.
- **New for this version:** `fig_three_causes_row_ILLUSTRATIVE.png`.
- **New for V2:**
  - `fig_skin_lesion_ISIC_0000013_with_boundary.png`, drawn from three hash-pinned files in `figures/`:
    `ISIC_0000013.jpg`, `ISIC_0000013_segmentation.png` and `ISIC_0000013.isic_metadata.json`, all CC-0;
  - `fig_maize_annotated_DSC_0042_crop_x2.png`, panel C: the author's annotated maize leaf (unpublished). Its
    photograph and annotation are read in place from `segmentors_backbones` and pinned by sha256; they are not copied
    here.
- **The poster also uses** the larger review-set variants `fig_arc_intro_00dbd492_large.png`,
  `fig_real_rule_ka95aa62f67d9_large.png`, `fig_construction_58_outcomes.png` and
  `fig_v2_uncertified_00dbd492_large.png`.

## Optional derivative

`poster_science_first_review.pptx`, from `python scripts/poster_visual_to_pptx.py --pdf
docs/summit_20261023_reframe/poster_science_first_review.pdf --out docs/summit_20261023_reframe/poster_science_first_review.pptx`.

**What is editable:**
- every text line outside the diagrams, as a text box;
- the figures, as the original PNGs.

**What is not:** the TikZ diagrams (the loop, the biology schematic, the small loop) are 300-dpi pictures, so their
labels are not editable there. Edit them in the `.org`.
