# Changelog: science-first review → cancer-lesion review V2 (19 October 2026)

**New files:**
- `poster_cancer_lesion_review.{org,tex,pdf}`: 1 page, A0;
- `explainer_cancer_lesion_review.{org,tex,pdf}`: 13 pages, A4.

**Labelled V2:** the poster's review banner and the explainer's date line say "REVIEW DRAFT V2". The file names are the
ones the addendum asked for.

**Derived from:** `poster_science_first_review.org` and `explainer_science_first_review.org`. Those, and their PDFs,
are unchanged.

**Image provenance:** `CANCER_LESION_IMAGE_PROVENANCE.md`.

**Later requests in the same session, all applied:**
1. a magnified, annotated maize tile beside the lesion;
2. a new headline that names learning from failure, with representation and "new data" defined;
3. learning from failure as the central theme;
4. "Supported or failed?" in the loop;
5. every ambiguous term defined or removed;
6. no "AI coding assistance used" or "Authorship pending review" lines.

## Poster

| aspect | science-first review | cancer-lesion review V2 |
|---|---|---|
| subtitle | "From Scientific Observations to Executable Reasoning and Hypothesis Revision" | **"Learning from Failure: Executable Reasoning and Hypothesis Revision"** |
| headline question | "How can a machine learn the objects, relationships and rules in unfamiliar data, and know what to reconsider…" | **"How can a machine learn the representation and rules of new data, learn from failure, and know what to reconsider when its explanation is not enough?"** |
| line under it | none | "Representation: what counts as an object, and which relations matter. Rules: what the objects do. New data: neither is given in advance." |
| biology visual | ILLUSTRATIVE SCHEMATIC of a lesion-mimic leaf | Three **real** panels:<br>**A, B:** ISIC_0000013, a dermoscopic image (CC-0), and the same image with its own expert-reviewed ISIC 2018 Task 1 boundary. Labelled "REAL MEDICAL IMAGE — ILLUSTRATIVE MOTIVATION, NOT CORA DATA", with the ID, licence, attribution and the record's quoted diagnosis.<br>**C:** the author's annotated maize leaf DSC_0042, magnified ×2, labelled "REAL MAIZE LEAF, NOT CORA DATA" |
| question box | none | a dashed "?" box: "What biological process explains this lesion?" |
| layers | none | Observe / Represent / Explain and test |
| take-home line | "Observed pattern ≠ identified mechanism" | **"Finding a lesion is not the same as explaining it."**, then the scope caption: a boundary is not a diagnosis; a mechanism needs further evidence; neither a segmentation nor CORA's checker provides it |
| loop heading | "One reasoning loop." | **"One reasoning loop that learns from failure."**, followed by one-line definitions of ARC and CORA |
| decision node | "Supported, or not?"; arrows "yes" / "no: incomplete, conflicting or fragile" | **"Supported or failed?"** (checks: rival rules; each example hidden in turn); arrows **"supported"** / **"failed: diagnose, then revise"** |
| bottleneck 1 | "measured: CORA often cannot propose a usable rule" | "measured: often no rule fits, within the operations CORA can express and its search limits" |
| bottleneck 2 | "unproven: can it learn which part to revise?" | "unresolved: choosing the revision that helps", with the line "not yet shown to beat a version that ignores the failure, given equal compute" |
| learned component | "Learned priors / Neural-CORA, proposed" | "Learned guide / proposed: ranks what to try first" (column 3: "trained guide") |
| legend | Solid / Dashed / Grey | adds definitions of **Failed** and **Exposed task** |
| column chips and titles | "DONE, NARROW"; "Visible doubt" | "DONE, ONE TASK"; "Thin evidence, flagged", with **Certified** defined |
| column texts | "exposed training task", "Every variant: 0", "trained prior", "27.64% public" | "Correct, and rebuilt 3 of 3 times with one example hidden, on an exposed task. A version that ignored the failure record found it too."; "With or without the failure record: 0; no wrong answers."; "A trained model would only rank what CORA tries first; CORA still checks every answer."; "27.64% on Kaggle's public leaderboard; CORA scores 0.00%." |
| closing line | "If revision selection works on ARC…" | **"If learning from failure works on ARC, test the same revision procedure…"** [UNTESTED] |
| footer | "…AI coding assistance used. Authorship pending review." | **those two sentences removed.** It adds "Images: ISIC_0000013, CC-0; maize leaf DSC_0042, author's study, unpublished." |
| layout | separate question and loop blocks | one block, which saves the padding between them. Bottom margin 1.98 cm |

**Unchanged:**
- every ARC figure, pixel-identical to its pinned PNG;
- the loop's structure;
- ka95aa62f67d9, 0 / 58 and the NVARC baseline;
- the author line;
- the A0 review assumption.

**Word counts** (`python -I scripts/count_poster_words.py <poster>.org`):

| | science-first | V2 |
|---|---|---|
| **prose (body sentences)** | 197 | **350** |
| diagram labels | 120 | 119 |
| block titles | 34 | 36 |
| footer | 27 | 20 |
| whole PDF (`pdftotext`, includes title lines) | 426 | 584 |

The V2 prose is at the top of the requested 250–350 words, which exclude short figure labels and references. Text inside
the PNG figures is not counted.

## Explainer

1. **Opening paragraph:** the addendum's exact text, followed by one-line definitions of ARC and CORA.
2. **Section 1:**
   - the new question, with learning from failure named as the central theme;
   - what "representation" means (objects are one part of it) and what "rules" are;
   - why the data is "new" rather than "unfamiliar": the objects and rules are not given in advance;
   - what "failure" means;
   - new 20-second and 90-second scripts: 64 and 232 spoken words.
3. **Section 2:** "A real medical observation". It contains:
   - the four-layer table (seeing, localization, diagnostic pathology, molecular causation);
   - 2.1, the skin image's provenance and the proof that its mask pairs with it;
   - **2.2, new: panel C, the author's annotated maize leaf**, with its files, why this leaf, the fixed crop rule, how it
     is drawn and what it does not show;
   - "Why both a skin lesion and a maize leaf".
4. **Section 3:**
   - "supported or failed?" with "supported" and "failed" arrows;
   - item 7 is named the learning-from-failure step;
   - the bottlenecks are in plain words, with the technical terms in brackets;
   - the loop figure floats to the top of a page and never before its own section (`flafter`).
5. **"Prior" becomes "guide" throughout.** The model is called the "learned guide", Neural-CORA in the records.
6. **Section 9 status:** development smoke tests have run; training has not started.
7. **Section 11:** the images bullet now covers both images, including the maize tile's permission.
8. **Glossary:** adds failed, learned guide, held out, fold, held-out task families, arm, native CORA, dermoscopy,
   segmentation mask and histopathology.
9. **Credits:** "Authorship and credits are pending review…" and "AI coding assistance was used…" are removed. The
   paragraph is now image credits only.
10. **Layout:** 13 pages. The build check for this document accepts 11–13.

## Tooling

- **`scripts/summit_visual_figures.py`:**
  - new `skin_lesion()` and `maize_tile()`;
  - five new hash-pinned sources: `isic_image`, `isic_mask`, `isic_record`, `maize_photo` and `maize_mask`. The maize
    sources are read in place;
  - the other figures regenerate byte-identically.
- **`scripts/build_summit_org.sh`:**
  - new targets `poster_cancer`, `explainer_cancer` and `cancer`;
  - `selftest` now covers all four Org documents.
- **`scripts/count_poster_words.py`:** new; counts a poster `.org` by category.

## Not changed

- the science-first and Qwen-architecture review sets;
- `docs/summit_poster/poster.pdf`;
- the author order;
- every experiment, Step B, VDCG and sealed data;
- Neural-CORA training (still paused);
- Kaggle and GitHub;
- every file in `segmentors_backbones`, which was read only.
