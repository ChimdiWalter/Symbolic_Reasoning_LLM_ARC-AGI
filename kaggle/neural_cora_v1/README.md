# kaggle/neural_cora_v1: SCAFFOLD ONLY (no notebook, no submission)

This folder will hold a future, versioned Kaggle candidate that runs the **unified Neural-CORA pipeline** from the
demonstrations and test inputs alone. Nothing here is built or runnable yet, and **no submission has been made or is
authorized**.

## Before any notebook is built

All of these must pass first (records/NEURAL_CORA_V1_27P64_COMPETITION_ROADMAP.md):
1. **G1:** the learned guide beats C+, C+H, L1h, L0 and L0s on held-out synthetic compositions
   (records/NEURAL_CORA_V1_PILOT_REPORT.md).
2. **G2:** the expressivity gate. The typed language covers independently held-out transformation families.
3. **G5:** extra exact correct predictions on a predeclared, eligible real ARC development cohort, with no
   unacceptable harmed outputs.
4. **G6:** a full offline rehearsal:
   - no network;
   - complete coverage;
   - the exact two-attempt schema;
   - whole-pipeline runtime, including Qwen feature extraction, with real headroom under the current Kaggle limit
     (last documented: 12 hours);
   - pinned weights and licences;
   - a memory audit.

Then the user is shown the exact frozen model, the notebook hash, the expected contribution and the risk. The user
alone authorizes a submission.

## Fixed constraints

- **Do not overwrite or resubmit the 27.64% NVARC baseline** (`kaggle/neural_v1/`, submission 57160429). It is
  NVARC's method, reproduced, and not CORA.
- **The pipeline's answers must all come from the integrated algorithm.** There must be:
  - no NVARC grid lane;
  - no fallback to NVARC when CORA abstains;
  - no cached or replayed development answers.
- **Assets:** the NVARC Qwen3-4B checkpoint (Apache-2.0) is the only third-party model. NVARC's synthetic program text
  is not used, because its licence is unresolved.
