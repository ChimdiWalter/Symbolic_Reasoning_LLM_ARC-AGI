# Kaggle manifests: original CORA and competitive hybrid (2026-10-18)

**Authorization state.** No new submission is authorized.
- The user's directives of 2026-10-17 and 2026-10-18 require four things before any further submission:
  - a finished valid rehearsal;
  - clean paired evidence of a CORA-derived benefit;
  - integrity and contamination checks;
  - fresh explicit authorization for that exact method and version.
- Final selections are the user's and are untouched.
- Neither existing submission is overwritten.

## Rules rechecked (2026-10-18; `outputs/kaggle_deploy/rules_20261018/`, beside the 2026-10-12 copy)

- **Code:**
  - notebook submissions;
  - CPU or GPU notebook of at most 12 h;
  - no internet;
  - freely and publicly available external data and pretrained models allowed;
  - `submission.json`;
  - obfuscated runtimes.
  - Note: "exploring options to provide better compute".
- **Limits:** 1 submission per day; 2 final selections.
- **Timeline:** entry and team-merger deadline 26 October; final submission 2 November; winners
  4 December (23:59 UTC).
- **Open source:** prize-eligible solutions must be open-sourced and attached to a solution writeup.
  Winning submissions are licensed CC BY 4.0, and an open-source system, model and weights are required.
- **Paper Prize** (user's note, 2026-10-18): it needs a corresponding code submission, not a high score,
  plus a writeup. Making the notebook public is the user's decision.

## A. Original-CORA manifest

| item | value |
|---|---|
| entry | **CORA_FHR_V1**, submission **57354496** (2026-10-18, 12:40Z), PENDING |
| notebook | `chimdiwalter/cora-fhr-v1-arc-agi-2-research-entry` v1 (private; no internet; CPU) |
| datasets | `chimdiwalter/arc-native-baseline-v1` (native v23, unchanged); `chimdiwalter/arc-cora-fhr-v1` (tarball 9910893f) |
| method | unchanged native v23 harness, then CORA-FHR arm E on growth-shaped, native-uncertified tasks (`kaggle/cora_fhr_v1/`) |
| gates passed | emulation 11/11; committed run 10/10 (5.88 h, native agreement 258/259); dev safety: 0 wrong, 0 lost |
| local evidence | FHR committed **0** of 240 stand-in tasks; on the dev tasks E added 0 |
| expected | near native's 0.00; it documents a runnable implementation, not accuracy |
| next original-CORA version | **not ready.** It needs a mechanism that adds verified correct real-task predictions in development (see `records/CORA_REVISION_ROOT_CAUSE_20261018.md`), then a new rehearsal and fresh authorization |

## B. Competitive-hybrid manifest

| item | value |
|---|---|
| incumbent | NEURAL_TTT_BASELINE, submission **57160429**, public **27.64**: a reproduction of NVARC, not CORA; preserved unchanged |
| rejected hybrid | native CORA filling NVARC's empty second attempts: **NO-GO** (0 gained, 1 lost; `records/NVARC_CORA_COMPLEMENTARITY_AUDIT_20261014.md`) |
| legitimate next experiment (not started) | NVARC proposes relations, views, correspondences or typed programs, and CORA must construct and verify an executable explanation. Predicted test grids are never labels. Adaptation is fold-local, or the neural source is excluded from that fold's certificate. Arms: neural alone, native, blind neural-symbolic, trace-conditioned neural-symbolic; compute matched |
| preconditions | permitted, uncontaminated paired data; measured complementarity (correct answers NVARC misses, with none lost); a full rehearsal under 12 h; licence audit; fresh authorization |
| status | **NO-GO**; no measured complementarity exists |
