# Amendment 4 to Protocol U5 (2 Nov 2026, before any evaluation outcome): a third, pre-registered transfer target

`PROTOCOL.md` and Amendments 1 to 3 are unchanged. This file adds to them and takes precedence where they differ. Its
hash is in `AMENDMENT_4_FREEZE.json`.

**Why.** After Amendment 3, only two datasets remain (LIVECell, NuInsSeg), so the learned-transfer conjunction over two
targets cannot be tested. The coordinator asked for one pre-registered third target, chosen by a rule written before
any of its masks are seen. **This file is written before the candidate is downloaded.** Its archives, file names and
masks have not been opened.

## 1. The selection rule (fixed before any candidate data are seen)

A candidate qualifies only if all of the following hold:
1. **Licence.** The official data page states a licence that permits evaluation.
2. **Independent groups.** At least 10 calibration and 15 evaluation parents (the protocol minimum) at its coarsest
   acquisition unit, provable from file names or released metadata, after the exclusions in section 3.
3. **References.** Manual per-object instance annotations.
4. **Fresh.** No previous use in our records (a search of `records/`, `cross_domain/` and `experiments/` for its name
   finds nothing).
5. **Baseline.** The baseline segmenter's documented training data must not contain it, or any overlap at the group
   level must be removable by a mechanical rule written here.
6. **Modality.** A modality different from phase contrast and H&E if any candidate qualifies; otherwise the first
   qualifying candidate.

**Candidates considered, in order:**
- **Fluorescence candidates, none qualifying:**
  - FluoEcoli-Instance: no source-image information (Amendment 2);
  - FNC v2: only 22 animals (Amendment 3);
  - the EGFP-Galectin-3 set: the same fields as an excluded dataset;
  - NucVerse3D, CellCycleNet FUCCI and BlastoSPIM: 3D volumes without 2D instance references;
  - TissueNet and the multiplex dataset of Aleynick et al.: downloads require an account;
  - the BBBC sets: one plate each, or already used.

  No phase-contrast or other non-H&E candidate with provable independent groups was found.
- **The qualifying candidate: MoNuSAC 2020** (Verma et al., IEEE TMI 2021; monusac-2020.grand-challenge.org).
  - H&E, 40x; lung, prostate, kidney and breast; TCGA diagnostic slides from many hospitals.
  - Training release: 46 patients; testing release: 25 patients.
  - Polygon annotations (XML) of four nucleus classes, plus ambiguous-region masks.
  - Licence CC BY-NC-SA 4.0, stated on the official data page: non-commercial research use, including evaluation;
    nothing is redistributed.
  - The record search finds no earlier use.
  - It is the same modality as NuInsSeg, but a different source, set of organs and annotation protocol. Transfer to it
    therefore tests a new histology source, not a new modality. This limitation is stated with every result.

## 2. MoNuSAC as used

- **Files.** From the official links:
  - `MoNuSAC_images_and_annotations.zip` (545,564,883 bytes);
  - `MoNuSAC Testing Data and Annotations.zip` (202,746,703 bytes);
  - the supplementary organ PDF.
  All are hashed in `DATA_PROVENANCE.json` at download.
- **Pool.** Every annotated sub-image of both releases. No arm trains on it, so the official split plays no role.
- **Parent.** The patient: the 12-character TCGA patient barcode (`TCGA-XX-XXXX`) parsed from folder or file names. If
  the names do not carry barcodes, the candidate is INELIGIBLE.
- **Split.** Patients in sha256 order of `"monusac:<barcode>"`. The first 40% are calibration, the rest evaluation;
  calibration is halved into induction and validation as in section 4.
- **Eligibility.** As section 3.3, after the exclusion in section 3: at least 10 calibration and 15 evaluation
  patients.
- **Objects.** The XML polygons of all four classes, rasterized as for LIVECell (larger first).
- **Ignore regions.** The released ambiguous-region masks, and any XML region labelled ambiguous. An object with at
  least half of its pixels inside them is removed from both sides for every arm, as for NuInsSeg.
- **Input and intensity image.** As NuInsSeg: RGB normalized at (1, 99.8) jointly; haematoxylin optical density.
- **Baseline.** StarDist 0.9.2 `2D_versatile_he`, NATIVE and TUNED as in section 5.
- **Role.** C, the second transfer target. G_A and the policy are applied unchanged, with C's calibration patients as
  demonstrations. C's own in-domain induction is a secondary arm, as for B.

## 3. Exclusion for the baseline's training data

StarDist `2D_versatile_he` was trained on the MoNuSeg 2018 training data (TCGA slides) and TNBC. Every MoNuSAC patient
whose barcode appears among the file names of the official MoNuSeg 2018 training archive is excluded from the pool.
Only the archive's names are read; no MoNuSeg image is used.

## 4. Consequences

- If MoNuSAC is eligible after these steps, the learned-transfer claim is the conjunction over B (NuInsSeg) and C
  (MoNuSAC), as in protocol section 14.5 and Amendment 3, section 6. Otherwise the study keeps two datasets and
  descriptive single-target transfer, and says so.
- C's calibration steps (segmentation, strong native, gate, probes, in-domain induction, static fits) run after the
  calibration chain already running; they do not delay it.
- The data reader for MoNuSAC is code added after this freeze and before any MoNuSAC mask is decoded. Its hash and
  the updated `CODE_FREEZE.json` are recorded in `AMENDMENT_4_FREEZE.json` when the reader is frozen.
