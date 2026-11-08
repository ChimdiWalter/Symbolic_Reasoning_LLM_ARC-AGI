# T5 data manifest: signalling logic models

All files were downloaded on 8 November 2026 (05:29 to 05:40 UTC) into `data/raw/`. Every file is read with
`python3 -I` (or the project venv with `-I`). No private data and no images are used.

## Used in development

| File | Source | Licence | sha256 |
|---|---|---|---|
| ToyPKNMMB.sif | CellNOptR, `inst/ToyModel/`, GitHub saezlab/CellNOptR at commit b7df141a677aa118be3f351b354a6359b64b29b2 | GPL-3 (package DESCRIPTION) | e564af5dd4fe5f86a4ea2d1f523578d139b6d47baaf8b2c20ba2796e15e87408 |
| ToyDataMMB.csv | same | GPL-3 | e64302578501133d57f97e115be40f5dc2c6f053d7ad336f86de410f952971c5 |
| ToyModelMMB2.sif | same (the toy network with a cJun to Jnk feedback; not used) | GPL-3 | 2ef62f956cb8d25d956add5a4b03f0276792c42e69c72b910428d2efb125f46d |
| LiverPKNDREAM.sif | CellNOptR, `inst/DREAMmodel/`, same commit | GPL-3 | f7008e6d1c7e3d6b99c592c60a0f44cace3111eb2c2745210cc3de5bbb1f707b |
| LiverDataDREAMMIDAS.csv | same | GPL-3 | 00fbe5449729eda3585641418090b51f36a3f7a83df98f20bf8bf7632257a2a1 |
| DESCRIPTION, CITATION | same (licence and citation records) | GPL-3 | 3fb5bf48..., b5a9de7a... |

- **Toy model and data.** This is CellNOpt's teaching example: a 16-edge prior network and 9 perturbation conditions
  with 7 readouts at t = 10. It comes from Morris, Melas and Saez-Rodriguez, *Construction of cell type-specific logic
  models of signalling networks using CellNetOptimizer* (Methods in Molecular Biology), and is shipped with CellNOptR
  (Terfve et al. 2012, BMC Systems Biology 6:133). We treat it as illustrative example data, not as a wet-lab
  measurement.
- **DREAM hepatocyte data.** These are real phosphoproteomics measurements in HepG2 cells, normalised to [0, 1]:
  25 conditions at t = 30 min (no stimulus or one of 4 stimuli, crossed with no inhibitor or one of 4 inhibitors) and
  7 readouts, with the prior network of 58 edges. Sources: Saez-Rodriguez et al. 2009, Molecular Systems Biology
  5:331; Alexopoulos et al. 2010, Molecular and Cellular Proteomics 9:1849; and the DREAM4 predictive signalling
  challenge (Prill et al. 2011, Science Signaling 4:mr7).
- **Development use of the DREAM files.** The development runs use only the DREAM prior network and the experimental
  design (which stimuli and inhibitors each condition applies). The loader strips every measured value
  (`t5.data.design_only`), and the synthetic development data are simulated on that design.

## Downloaded, structure read only (not used in any run)

These come from GitHub cellnopt/cellnopt at commit 319c956e890ed7ae88c8e6e540de7061acfaae00, folder `cno/datasets/`,
under the BSD-2-Clause licence (`cno_datasets/LICENSE`, sha256 9a763312...). Each folder holds README.rst,
PKN-<name>.sif and MD-<name>.csv:
- LiverDREAM: the same content as the CellNOptR copy, apart from line endings;
- ToyMMB: its MIDAS file differs from the CellNOptR copy, so we use the CellNOptR copy;
- ToyMMB_added_link: the toy network plus PI3K to NFkB;
- LiverMSB2009;
- ExtLiverPCB: HepG2, Morris et al. 2011, PLoS Computational Biology. It has 64 conditions and 15 readouts, and it
  probably overlaps the DREAM measurements;
- HepG2CancerRes2011;
- ExtLiverPriHuMCP2010: primary human hepatocytes, Alexopoulos et al. 2010. Its values are not on a [0, 1] scale;
- TCellPCB2007;
- EGFR-ErbB_PCB2009.

For these sets, only structure was read: counts of conditions, readouts and edges, cue names, and whether the values
lie in [0, 1]. No measured value was displayed. They are candidates for a larger held set in a later test (see
PROGRESS.md).

## Exposure note (for any later custody test)

Before any split rule existed, at about 05:31 UTC, the full DREAM MIDAS file and the toy MIDAS file were printed once
to the terminal to check their format (CR line endings). No fit, tuning or development run has used a DREAM measured
value. A later test that holds DREAM conditions must disclose this exposure, or use an unseen set as its held data.
