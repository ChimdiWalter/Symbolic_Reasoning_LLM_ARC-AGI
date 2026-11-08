# Amendment 1 to Protocol U5 (2 Nov 2026, before any outcome)

`PROTOCOL.md` (sha256 `7d5ef686c983b8b8c2d92903f72ec8ccdda2cac35c1544bc3c6252ff3c56cd49`) is unchanged; this file adds to
it and takes precedence where the two differ. Its own hash is in `AMENDMENT_1_FREEZE.json`.

**State when written.** Three archives were downloaded after the freeze (LIVECell `images.zip` and
`livecell_coco_test.json`; NuInsSeg, MD5 verified). Only archive listings and file names were read. No image was
decoded, no mask or annotation was decoded or counted, no segmenter or CORA package was run, and no outcome of any
kind exists.

## 1. LIVECell's pool (protocol sections 3.2 and 3.3)

**Finding, from file names only.** The official test subset holds 1,512 images of only 18 fields of view (9 wells;
two fields per well, four for SKOV3), each imaged 76 to 100 times (time points x 4 crops). Under the frozen parent rule
(one field of view per parent) it gives 7 calibration and 11 evaluation parents, so D1 would be ineligible under
section 3.3 (at least 10 and 15).

**Change.** D1's pool becomes all three official subsets (train, validation and test: 5,239 images, 62 fields of view,
31 wells). The test subset's fields and wells are disjoint from those of the other two. Annotations:
`livecell_coco_train.json`, `livecell_coco_val.json` and `livecell_coco_test.json`.

**Why this is sound.** The official split exists to separate training and test images for models trained on
LIVECell. No arm of U5 trains on LIVECell, and the baseline (Cellpose 3 `cyto2`) was trained on no LIVECell image. The
parent rule (field of view), the cap (720 images) and the equal per-parent quota (floor(720 / 62) = 11 images per
field, in sha256 order of file name) are unchanged.

**Added sensitivity analysis (descriptive).** Two fields share each well, so every D1 contrast is also reported with
the bootstrap clustered by well.

The backup dataset is therefore not triggered by D1's eligibility.

## 2. NuInsSeg's files (sections 3.2 and 4), as found

- The archive encodes the organ folder and an image index only (31 folders; `<organ>_NN.png`), so the parent is the
  organ folder, as pre-registered: 31 parents.
- Inputs: `tissue images/*.png`. Reference: `label masks/*.tif` (the instance masks). Ambiguous areas:
  `vague areas/mask binary/*.png` (the raster form of the ambiguous areas). The ImageJ ROI folders and
  `label masks modify` are not used.
