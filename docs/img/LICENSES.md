# Image sources and licences

Every image in this folder is listed here with its source and licence. Each dataset's licence was checked on its
official page on 2 November 2026. Each image keeps the licence of the data it shows; the root `LICENSE` does not
relicense these images.

| file | what it shows | source | licence |
|---|---|---|---|
| `pipeline.svg` | CORA's pipeline | our own drawing | CC0 1.0 |
| `puzzle_conceptarc_move_to_boundary.svg` | a ConceptARC puzzle, `corpus/MoveToBoundary/MoveToBoundary3.json` (test input 1), with CORA's answer | [ConceptARC](https://github.com/victorvikram/ConceptARC), commit `0e67da6`; Moskvichev, Odouard and Mitchell, "The ConceptARC Benchmark: Evaluating Understanding and Generalization in the ARC Domain", 2023 | MIT, Copyright (c) 2024 Victor Vikram Odouard |
| `puzzle_conceptarc_center_abstains.svg` | a ConceptARC puzzle, `corpus/Center/Center1.json` (test input 1), where CORA abstains | as above | MIT, Copyright (c) 2024 Victor Vikram Odouard |
| `puzzle_1darc_fill.svg` | a 1D-ARC puzzle, `dataset/1d_fill/1d_fill_0.json`, with CORA's answer | [1D-ARC](https://github.com/khalil-research/1D-ARC), commit `1e74dc4`; Xu et al., "LLMs and the Abstraction and Reasoning Corpus: Successes, Failures, and the Importance of Object-based Representations", arXiv:2305.18354 | MIT, Copyright (c) 2023 University of Toronto |
| `bio_livecell_crop.png` | a 256 x 256 crop of LIVECell image `A172_Phase_A7_1_03d00h00m_1` (phase contrast), with the baseline's cell outlines in yellow | [LIVECell](https://github.com/sartorius-research/LIVECell); Edlund et al., "LIVECell: a large-scale dataset for label-free live cell segmentation", Nature Methods, 2021 | CC BY-NC 4.0 (non-commercial use only) |
| `bio_nuinsseg_crop.png` | a 256 x 256 crop of NuInsSeg image `human_kidney_09` (haematoxylin and eosin, H&E), with the baseline's nucleus outlines in green | [NuInsSeg](https://doi.org/10.5281/zenodo.10518968); Mahbod et al., "NuInsSeg: A fully annotated dataset for nuclei instance segmentation in H&E-stained histological images", 2024 | CC BY 4.0 |
| `bio_monusac_crop.png` | a 256 x 256 crop of MoNuSAC image `TCGA-B9-A44B-01Z-00-DX1_1` (H&E), with the baseline's nucleus outlines in green | [MoNuSAC 2020](https://monusac-2020.grand-challenge.org/Data/); Verma et al., "MoNuSAC2020: A Multi-organ Nuclei Segmentation and Classification Challenge", IEEE Transactions on Medical Imaging, 2021 | CC BY-NC-SA 4.0: this adapted image is shared under the same licence (non-commercial use only) |

**What we changed.**
- **Puzzles:** the grids are drawn in the ARC colour palette, as given in the dataset. CORA's answer, or the word
  "abstains", replaces the hidden test output. Each answer shown is CORA's frozen output from our evaluation. It is
  labelled right because the evaluation's scorer found every answered output of that puzzle family right.
- **Biology crops:** each crop comes from a held-out evaluation image. The outlines are the boundaries of the
  baseline segmentation: Cellpose (cyto2 model, tuned) for LIVECell, and StarDist (2D_versatile_he model) with the
  calibration-tuned rule for the two H&E datasets. CORA made no edit on these images, so the outlines are also CORA's
  output.

**MIT licence notice** for the 1D-ARC and ConceptARC material, with the copyright lines above:

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
> documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
> rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
> permit persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of
> the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
> THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
> TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

The Creative Commons licences are at https://creativecommons.org/licenses/by-nc/4.0/,
https://creativecommons.org/licenses/by/4.0/ and https://creativecommons.org/licenses/by-nc-sa/4.0/.
