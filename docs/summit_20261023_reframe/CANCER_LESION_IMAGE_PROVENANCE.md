# Provenance: the real images on the V2 cancer-lesion review poster (19 October 2026)

**Used in:**
- `poster_cancer_lesion_review.{org,pdf}`: the top band. Panels A and B are the skin lesion; panel C is the maize leaf
  (section 5);
- `explainer_cancer_lesion_review.{org,pdf}`: figures 1 and 2, and section 2.

**Role:** motivation only. The figure says so on its face: "REAL MEDICAL IMAGE — ILLUSTRATIVE MOTIVATION, NOT CORA DATA".
CORA has never processed this or any other medical image.

## 1. The image and its documented label

| item | value | source |
|---|---|---|
| ID | **ISIC_0000013** | ISIC Archive (International Skin Imaging Collaboration) |
| record | https://api.isic-archive.com/api/v2/images/ISIC_0000013/ | saved verbatim as `figures/ISIC_0000013.isic_metadata.json` |
| image file | https://isic-archive.s3.amazonaws.com/images/ISIC_0000013.jpg | the record's `files.full.url` |
| type and size | dermoscopic JPEG, 1022 × 767 pixels | record `metadata.acquisition` |
| licence | **CC-0** | record `copyright_license` |
| attribution | **"Anonymous"** | record `attribution` |
| documented diagnosis | `diagnosis_1` "Malignant"; `diagnosis_2` "Malignant melanocytic proliferations (Melanoma)"; `diagnosis_3` "Melanoma Invasive" | record `metadata.clinical` |
| how the diagnosis was verified | `diagnosis_confirm_type` "histopathology"; `concomitant_biopsy` true | record `metadata.clinical` |
| label printed on the poster | "ISIC record: invasive melanoma (histopathology-confirmed)" | a quotation of the record |

**About the diagnosis:**
- It is the archive's documented label. It was not re-verified by the author.
- Nothing was inferred from the picture.
- The record also holds de-identified clinical fields (sex, approximate age, body site). They are not shown or used.

## 2. The mask, and proof that it belongs to this image

| item | value |
|---|---|
| mask file | `ISIC2018_Task1_Training_GroundTruth/ISIC_0000013_segmentation.png`, copied to `figures/ISIC_0000013_segmentation.png` |
| archive | https://isic-archive.s3.amazonaws.com/challenges/2018/ISIC2018_Task1_Training_GroundTruth.zip (27,402,895 bytes; 2,597 entries) |
| licence | **CC-0**: the 2018 Task 1 row of https://challenge.isic-archive.com/data/. That row links this zip, and its licence cell reads CC-0 |
| how the masks were made | from https://challenge.isic-archive.com/landing/2018/45/, quoted below |

The Task 1 page says the ground-truth data "were generated using several techniques, but all data were reviewed and
curated by practicing dermatologists with expertise in dermoscopy". It lists three ways a mask was made:
- a "fully-automated algorithm, reviewed and accepted by a human expert";
- "a semi-automated flood-fill algorithm, with parameters chosen by a human expert";
- "manual polygon tracing by a human expert".

The page does not say which method made this mask.

**Pairing checks** (all re-run on 19 October from the files in `figures/`):
1. The mask's file name carries the same ID, `ISIC_0000013`.
2. The image is in the archive's collection 63, "Challenge 2018: Task 1-2: Training": the API search restricted to that
   collection returns it. That is the image set the Task 1 ground truth annotates.
3. The mask is a PNG in mode L, 1022 × 767 pixels, the image's exact size. It is binary (values 0 and 255), and 27.58%
   of its pixels are lesion.
4. The zip member's sha256 equals that of the copy in `figures/`.
5. `scripts/summit_visual_figures.py` asserts that the mask's shape equals the image's before it draws anything.
6. In panel B, the drawn outline follows the lesion's edge.

No unrelated photograph, mask, pathology slide or patient record is paired with this image.

## 3. How it was selected and downloaded (19 October 2026)

1. **Search.**
   `https://api.isic-archive.com/api/v2/images/search/?collections=63&limit=100&query=diagnosis_1:Malignant AND diagnosis_confirm_type:histopathology AND copyright_license:CC-0`
   returned **519** images. Use the `images/search/` endpoint: the plain `images/` endpoint ignores the collection
   filter.
2. **Choice.** I compared 256-pixel thumbnails of 12 first-page matches: ISIC_0000004, 0000013, 0000026, 0000029,
   0000030, 0000031, 0000035, 0000036, 0000040, 0000043, 0000046 and 0000077. The criterion was legibility at poster
   size:
   - the whole lesion is in the frame;
   - the boundary is sharp;
   - there is no dark dermoscope vignette, dense hair, ruler, ink mark or graphic surface;
   - the record gives a specific diagnosis.

   ISIC_0000013 met every criterion. The first match, ISIC_0000004, has a strongly red surface inside a dark vignette,
   and its record says only "Melanoma, NOS". No CORA result played any part in the choice.
3. **Record:** `GET https://api.isic-archive.com/api/v2/images/ISIC_0000013/`.
4. **Image:** the record's `files.full.url`.
5. **Mask:** the Task 1 training ground-truth zip; only `ISIC_0000013_segmentation.png` was copied out.
6. **Handling:**
   - every download went into its own new, empty directory;
   - any Python that read a download ran in isolated mode (`python -I`);
   - the three files were then copied into `figures/`, and their sha256 hashes were pinned in
     `scripts/summit_visual_figures.py`.

Equivalent commands for reproduction (the API's JSON may change format over time; the quoted fields are what matter):

```
curl -sf 'https://api.isic-archive.com/api/v2/images/ISIC_0000013/' -o ISIC_0000013.isic_metadata.json
curl -sf 'https://isic-archive.s3.amazonaws.com/images/ISIC_0000013.jpg' -o ISIC_0000013.jpg
curl -sf 'https://isic-archive.s3.amazonaws.com/challenges/2018/ISIC2018_Task1_Training_GroundTruth.zip' -o gt2018.zip
unzip -j gt2018.zip ISIC2018_Task1_Training_GroundTruth/ISIC_0000013_segmentation.png
sha256sum ISIC_0000013.jpg ISIC_0000013_segmentation.png gt2018.zip
```

| file | sha256 |
|---|---|
| `figures/ISIC_0000013.jpg` | `087a955305a31cf5c6d197c9aa8848bb23822201b656d47f89fe4020a4b78650` |
| `figures/ISIC_0000013_segmentation.png` | `79d220455e70bf325e3e19a7e4c029a6fe9133637d8798b864d026bf3706bf9c` |
| `figures/ISIC_0000013.isic_metadata.json` | `e68c4eba323690a73f0f90e96b448204ccb3ee5ab1b4bd81690fe18de2e39cf9` |
| `ISIC2018_Task1_Training_GroundTruth.zip` (not kept in the repository) | `99f8b2bb3c4d6af483362010715f7e7d5d122d9f6c02cac0e0d15bef77c7604c` |
| `figures/fig_skin_lesion_ISIC_0000013_with_boundary.png` (the drawn figure) | `1f077aefa6e406924183c9856e63f76363b309ef0696f54900c0d988df42305e` |

## 4. The drawn figure

**File:** `figures/fig_skin_lesion_ISIC_0000013_with_boundary.png`: 1320 × 1049 pixels, 6.6 × 5.25 in at 200 dpi.

**Made by:** `skin_lesion()` in `scripts/summit_visual_figures.py`. Before drawing, it asserts:
- the ID;
- the CC-0 licence;
- `diagnosis_1`, `diagnosis_3` and `diagnosis_confirm_type`;
- the dermoscopic image type;
- the mask size.

**Transformations:**
- **Panel A:** the original JPEG, resized for display. No crop and no colour change.
- **Panel B:** the same image, plus the contour of the binary mask (pixels > 127), drawn as a 2.6 pt cyan (#00e5ff) line.

**Size on the A0 poster:**
- each panel is 7.2 × 5.4 cm;
- the main ARC grids are about 7.7 cm (00dbd492) and 9.5 cm (ka95aa62f67d9) on a side.

So the medical inset is smaller than the main ARC grids.

**Final text in the figure (verbatim):**

```
REAL MEDICAL IMAGE — ILLUSTRATIVE
MOTIVATION, NOT CORA DATA
A  observation            B  expert boundary
ISIC_0000013 · ISIC Archive · CC-0
attribution: Anonymous
ISIC record: invasive melanoma
(histopathology-confirmed)
B: its own ISIC 2018 Task 1 mask (CC-0)
```

**Poster text around it (verbatim):**
- the question above it: "How can a machine learn the representation and rules of new data, learn from failure, and
  know what to reconsider when its explanation is not enough?"
- the line under the question: "Representation: what counts as an object, and which relations matter. Rules: what the
  objects do. New data: neither is given in advance."
- the box: "?"
- its caption: "What biological process explains this lesion?"
- the three layers:
  - "Observe: what is in the image?"
  - "Represent: where is the lesion, and what are its relevant features?"
  - "Explain and test: what biological explanation fits independent clinical, histological or molecular evidence?"
- "Finding a lesion is not the same as explaining it."
- "A boundary is a spatial annotation, not a diagnosis; even a confirmed diagnosis needs further evidence to establish
  a mechanism. Neither a segmentation nor CORA's ARC checker provides that evidence."

## 5. Panel C: the author's annotated maize leaf

| item | value |
|---|---|
| leaf | `DSC_0042_segment_1_segmented_smoothed`, from the author's maize lesion study (unpublished) |
| photograph | `/deltos/e/lesion_phes/code/python/pipeline/segmentors_backbones/maize_lesion_study_v1/derived/normalized_leaves/DSC_0042_segment_1_segmented_smoothed.png`: RGB, 3900 × 851 pixels. It is the stored file that Project A's loader reads. sha256 `c8d56405812fd9e50f55ae97d0fec8390d8b96df8019aebb406843f8b8b22954` |
| annotation | `…/maize_lesion_study_v1/derived/pseudo_labels/DSC_0042_segment_1_segmented_smoothed_corrected.png`: the expert-corrected lesion mask, mode L, values 0 and 255. sha256 `0f4b4d72ce0651a800c39d434be2bb4489871df0593cf2f6f9e2ba1b52cd381d` |
| why this leaf | leaf 1 (sorted order) of the fixed, ID-gated cohort of `segmentors_backbones/projects/real_leaf_gallery_20261018`. That gate (ALL_PASS) confirms it is a Project A validation leaf. It is not one of the 25 development leaves, not one of the five consumed test leaves, and not from the reserved 26r collection |
| binarisation | Project A's `gt_of`: mask > 0. The leaf has 123 annotated components; 61 of them are at least 500 pixels, which matches the gallery's own count |
| crop rule | fixed before rendering. The window is 360 × 214 pixels and at least 99% on the leaf. It must hold the most complete 8-connected annotated lesions of at least 500 pixels. Ties: more annotated pixels, then the smallest y, then the smallest x. The rule selects rows 280–494 and columns 459–819: 6 complete lesions and 13,247 annotated pixels. `maize_tile()` asserts this result |
| drawing | the crop magnified ×2 by repeating pixels (nearest neighbour: no interpolation, no colour change), with the 2.0 pt cyan (#00e5ff) contour of the annotation |
| file | `figures/fig_maize_annotated_DSC_0042_crop_x2.png`: 779 × 1049 pixels at 200 dpi. Its panel has the same height and baseline as panels A and B |
| handling | read in place and read-only; nothing in `segmentors_backbones` was written. The full-resolution photograph and mask are not copied into this repository; only the drawn crop is |
| rights | unpublished data from the author's study. Public display should be confirmed with the data's owners before print: Toni, if the leaves belong to the lab collection |

**Final text in the figure (verbatim):**

```
REAL MAIZE LEAF,
NOT CORA DATA
C  annotated lesions
maize leaf DSC_0042
author's study
(unpublished data)
cyan: annotation
crop magnified ×2
```

**What the tile does not claim.** An annotation marks where lesions are, not which genes or processes produce them. No
genotype is stated. The tile is not a Project A, Project C or CORA result.

## 6. What the poster does not do

The poster does not:
- infer histopathology, molecular cause, treatment, prognosis, mutation or pathway from how the image looks;
- show patient-identifying features. The image is a close-up of the skin surface: no face, tattoo, jewellery, text or
  ruler;
- use AI-generated, stock or watermarked imagery;
- add a fabricated patient description, diagnosis, pathway chart or "matched" biopsy image;
- present the image as CORA data or as a CORA result.

## 7. Rights and citation

- Both files are CC-0, so attribution is not legally required. The poster still prints the ID, "ISIC Archive", "CC-0"
  and "attribution: Anonymous".
- For a paper, use the citations that the ISIC data page asks for for its 2018 data. Its 2018 citation block lists
  "MSK Dataset: (c) Anonymous", with https://arxiv.org/abs/1710.05006 and https://arxiv.org/abs/1902.03368. The full
  citation it gives is: Codella N., Rotemberg V., Tschandl P., Celebi M. E., Dusza S., Gutman D., Helba B., Kalloo A.,
  Liopyris K., Marchetti M., Kittler H., Halpern A., "Skin Lesion Analysis Toward Melanoma Detection 2018: A Challenge
  Hosted by the International Skin Imaging Collaboration (ISIC)", 2018, arXiv:1902.03368.
- The page also lists HAM10000 (Tschandl et al., Sci. Data 5, 180161, 2018). That citation covers the CC-BY-NC Task 3
  images, not this one.

## 8. Approvals still needed

- Collaborator review: Toni, Chris and Pierce.
- Permission to show the maize tile (unpublished) in public, from the data's owners.
- The author's approval before any print version.
- Recommended, not required: a dermatology or pathology colleague reads the medical wording.
