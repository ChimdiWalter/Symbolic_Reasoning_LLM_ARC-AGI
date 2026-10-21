# NVARC: attribution and redistribution notice

CORA's `NEURAL_TTT_BASELINE` (Kaggle submission 57160429, public score 27.64) is a faithful reproduction of
**NVARC**, the ARC Prize 2025 winning method by Ivan Sorokin and Jean-François Puget (NVIDIA). **It is NVARC's work,
not CORA's.**

**Original sources:**
- the NVARC repository: https://github.com/1ytic/NVARC
- NVARC's Kaggle notebook: https://www.kaggle.com/code/sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue
- the model checkpoint (Apache 2.0): https://www.kaggle.com/models/sorokin/qwen3_4b_grids15_sft139

**Redistribution:** the NVARC repository declares no licence. The notebook's licence could not be verified on
20 October 2026 (its Kaggle page needs JavaScript, and Kaggle's API metadata carries no licence field). Copies of
NVARC's notebook are therefore **not published** in this repository's public branch from this notice onward. Please
use the originals above.

**What remains:**
- CORA's own builder scripts. They record, as exact-string patches, the compatibility changes applied to the
  notebook, and contain only short upstream excerpts used as patch anchors.
- Local copies kept for reproducibility.

The licence audit is `records/NVARC_LICENSE_AUDIT_20261020.md`.
