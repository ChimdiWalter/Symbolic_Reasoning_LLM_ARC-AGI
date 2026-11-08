# Data manifest: calibrated acceptance study (8 Nov 2026)

Every download sits in its own folder under `data/raw/` (not in git) and is read with `python -I` only. Derived files
are under `data/work/` (not in git).

## 1. Fresh held data: PUMA (downloaded 8 Nov 2026, 06:33 to 06:35 UTC)

- **Dataset.** "Melanoma Histopathology Dataset with Tissue and Nuclei Annotations" (the PUMA challenge training set).
- **Source.** Zenodo record 13859989, doi:10.5281/zenodo.13859989, published 1 Oct 2024. The record's metadata is
  saved as `data/raw/puma_zenodo_13859989/zenodo_record_13859989.json` (from `https://zenodo.org/api/records/13859989`).
- **Licence.** Creative Commons Attribution 4.0 International. The record's metadata gives the licence id
  `cc-by-4.0`. Use with attribution is allowed, including figures.
- **Citation.** Schuiveling M et al. (2025) A novel dataset for nuclei and tissue segmentation in melanoma with
  baseline nuclei segmentation and tissue segmentation benchmarks. GigaScience 14:giaf011, doi:10.1093/gigascience/giaf011.
- **Content, as the record describes it.** 206 regions of interest (ROIs) of 1024 x 1024 pixels: one per specimen, from
  103 primary and 103 metastatic melanoma specimens. H&E, Hamamatsu scanner, 40x (0.23 micrometres per pixel).
  - Nuclei were first segmented by HoVer-Net pretrained on PanNuke. A trained medical expert then adjusted them in
    QuPath, and a dermatopathologist reviewed and corrected them.
  - On 12 ROIs, inter-observer nucleus F1 was 0.802 and intra-observer F1 0.857.
- **Files used** (two of the record's four files; the 14 GB context ROIs and the tissue annotations are not downloaded):

| file | bytes | MD5 (published = observed) | sha256 |
|---|---|---|---|
| `01_training_dataset_tif_ROIs.zip` | 647,205,575 | `0310c5a303b986eb4ff2dba4ddbfb70e` | `a69fd0d8443da29233df103ece5674fb50e8f0cc4b448dc60508cfe883881993` |
| `01_training_dataset_geojson_nuclei.zip` | 15,958,208 | `595d8ec2f8bb8e09e1e9fc1df2c4c09e` | `17f77ca83fb8fccd918ce723a7b3e5cb5a1730b342ad486628f8885d14a1acbd` |

- **Members.** 206 TIFF images (`training_set_{primary,metastatic}_roi_NNN.tif`, 103 of each) and 206 GeoJSON files
  (`..._nuclei.geojson`), one per ROI. Only the archive listings were read before the format check.
- **Format check, before GO.** One ROI, `training_set_primary_roi_028`, was opened. It is the ROI with the smallest
  sha256 of `"calacc_format:<roi>"`, fixed before anything was opened.
  - Its image is 1024 x 1024 x 3, uint8.
  - Its GeoJSON holds 292 polygons, which rasterize to 292 objects.
  - StarDist was run on it once, to time the run: 5.5 CPU-s per ROI. Its F1 was not computed.
  - It is excluded from both the held set and the reserve (`data/work/format_check/FORMAT_CHECK.json`).
- **Not in the baseline's training data.** StarDist `2D_versatile_he` was trained on the MoNuSeg 2018 training data
  and TNBC. PUMA's slides come from regular diagnostic procedures (the record's words), not from The Cancer Genome Atlas (TCGA).
- **Not used before.** No CORA study has used PUMA: `records/` and the project's study documents contain no mention
  of PUMA or Zenodo record 13859989.

## 2. Calibration data (reused read-only from the bioimage grammar study of 2 Nov 2026, called U5 here, `experiments/universality_bio_grammar_20261103`; not downloaded again)

- **NuInsSeg.** Mahbod et al. 2024, Zenodo 10.5281/zenodo.10518968, CC BY 4.0. Only U5's 12 calibration organs
  (236 images) are used: U5's starting segmentation S, intensity images, low-threshold labels, calibration references
  and failure records, all under `/path/to/bio_data/work/nuinsseg/`.
- **Consumed, not used.** U5's 19 evaluation organs (429 images).
- **Hashes.** Every reused file's sha256 is in `FREEZE.json` (`u5_reused`).

## 3. Baseline model (a byte copy of U5's)

StarDist 0.9.2 `2D_versatile_he` (Schmidt et al. 2018), copied from U5's
`/path/to/bio_data/models/stardist/2D_versatile_he/` to `data/models/stardist/`.
The sha256 of both copies is in `FREEZE.json` (`u5_reused`, `data.model_copy`).

## 4. Candidates checked and not chosen

| candidate | licence, checked at its source on 8 Nov 2026 | decision and reason |
|---|---|---|
| BBBC038 (2018 Data Science Bowl) | "Copyright: CC0" (bbbc.broadinstitute.org/BBBC038) | **Not used.** The author's decision record reserves it for another of the author's papers. Part of it is also StarDist's fluorescence training data, and few of its images are H&E |
| CryoNuSeg (Mahbod et al. 2021) | Kaggle dataset metadata: licence "MIT"; the GitHub repository masih4/CryoNuSeg is MIT | **Not used.** MIT is permissive, but this study requires CC0 or CC BY. It is also small: 30 images from 10 organs |
| MoNuSeg 2018, TNBC | not needed | **Not used.** They are StarDist `2D_versatile_he` training data |
| PanNuke, Lizard | not needed | **Not used.** Both are candidates for that other paper in the same decision record |
| NuInsSeg evaluation organs, MoNuSAC, LIVECell | (U5) | **Not used.** U5 consumed them, and MoNuSAC and LIVECell are non-commercial |

Non-commercial data (LIVECell, MoNuSAC) is never embedded in a figure. PUMA and NuInsSeg are CC BY 4.0, so figures
from them need attribution.
