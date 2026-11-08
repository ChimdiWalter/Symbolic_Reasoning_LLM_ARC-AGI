# Amendment 2 to Protocol U5 (2 Nov 2026, before any evaluation outcome)

`PROTOCOL.md` (sha256 `7d5ef686...c56cd49`) and Amendment 1 (`8e063d54...`) are unchanged; this file adds to them and
takes precedence where they differ. Its hash is in `AMENDMENT_2_FREEZE.json`.

**State when written (10:00Z).** Calibration-side work only: NuInsSeg calibration images segmented and tuned, its
strong native filter chosen, its calibration gate computed (PASS) and its probe tasks run on the frozen package (all
calibration, allowed by protocol section 17). LIVECell calibration segmentation is running. No evaluation image has
been segmented, no evaluation reference has been decoded, and no arm has been applied to any evaluation parent.
None of the changes below was motivated by a calibration result; each comes from an archive's structure or from a
unit test on synthetic images.

## 1. D3 is ineligible; the pre-registered backup replaces it

FluoEcoli-Instance's 4,941 test patches are named by a bare running index (`003579.tiff`), and the COCO image records
carry no source-image field, so the source full-size image of a patch cannot be derived from names or archive
structure (sections 3.3 and 4). D3 is therefore INELIGIBLE, and the backup of section 3.1 replaces it:

- **Fluorescent Neuronal Cells v2, green collection** (AMS Acta eprint 7347, CC BY 4.0; `green.zip`,
  1,334,225,455 bytes, and `metadata_v2.xlsx`, both hashed in the data manifest).
- **Pool:** all 283 labelled green images (`trainval` and `test`). No arm trains on this dataset, so the official split
  plays no role (as for LIVECell in Amendment 1).
- **Parent:** the tissue section, (animal_id, sample_id, sample_row, sample_col) from `metadata_v2.xlsx` (the archive's
  own metadata): 117 sections; the images of one section are its distinct brain regions. This gives 47 calibration and
  70 evaluation parents. A sensitivity analysis clusters the bootstrap by animal (22 animals), descriptive.
- **Input and intensity image:** the green channel (index 1) of the PNG, the collection's stain; normalized at
  (1, 99.8). **Objects:** the released COCO polygons, rasterized as for LIVECell.
- **Baseline:** StarDist 0.9.2 `2D_versatile_fluo`, the weights used by the earlier studies
  (`outputs/universality_v2/models/stardist/2D_versatile_fluo`, copied with their sha256), NATIVE and TUNED as in
  section 5.

The order of section 6 then reads D1 (LIVECell), D2 (NuInsSeg), backup (FNC v2).

## 2. The SPLIT class includes matched merged objects (section 8.1)

A predicted object that covers two reference objects often still matches the larger one at IoU > 0.5 (a unit test on
synthetic touching discs). Under the frozen wording such a merge error is invisible: the object is matched, and the
other reference object is covered, so it is not missed. **SPLIT now applies to any counted object that covers at least
two reference objects, matched or not**; the other classes still apply to unmatched objects only. Every oracle
correction keeps one-to-one matching: a reference object is drawn only if no remaining prediction matches it, and
removing an object frees the reference object it matched.

## 3. h-maxima (section 7, operators 3 and 4)

Markers are the classical h-maxima (regional maxima of the reconstruction of f - h under f), using the earlier CORA
nuclei study's implementation (`cora_cross_domain_transfer.adapters.bbbc039.h_maxima`, unchanged).
`skimage.morphology.h_maxima` marks equal-height peaks separately whatever h is (found in a unit test), so it is not
used.

## 4. ALL_ON's tuning objective (section 12)

Each candidate value of operator k is scored by the exact pooled calibration F1 of the state after operator k, with the
operators before k at their current values and the operators after k not applied. The descent runs in canonical order;
with this objective one sweep is the fixed point. **Reason:** exact scoring of the full downstream pipeline for each of
about 45 candidates per sweep would cost about 15 CPU-minutes per candidate on LIVECell, more than the study's whole
budget.

## 5. Matched compute (section 13)

Applying an arm to evaluation images is counted for no arm, like the shared segmentation. MATCHED_SEARCH's budget is
CORA's measured calibration-side CPU on that dataset: probes, specification, admission and final fitting (on B and C:
the final fitting there plus A's induction).
