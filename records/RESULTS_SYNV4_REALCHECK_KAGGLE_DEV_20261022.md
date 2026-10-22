# Results of 22 October 2026: syn-v4, the real-puzzle check, and the CORA-only Kaggle development runs

Generated from the score files by a script (no hand-copied numbers). Evidence types are kept apart.

## 1. syn-v4 (FROZEN RESULT, synthetic): GO_ENGINEERING

Protocol `records/NEURAL_CORA_V2G4_PROTOCOL_20261021.md` (manifest 39c7ffc1). 210 held-out generated tasks, 110 in the target groups. The protocol's own limit: 9 of the 11 target families are written in version 4's own rule language, so a gain there is expected by construction.

| group (n) | g3 | g4 | g4_no_construct | g4_no_invert | g4_parts_only | g4_rays_only | g3_cpu | g4_random |
|---|---|---|---|---|---|---|---|---|
| ambiguity (20) | 50.0 | 65.0 | 50.0 | 65.0 | 65.0 | 50.0 | 50.0 | 50.0 |
| beyond (40) | 25.0 | 25.0 | 25.0 | 25.0 | 25.0 | 25.0 | 25.0 | 25.0 |
| control (20) | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| mixed (20) | 5.0 | 85.0 | 5.0 | 40.0 | 85.0 | 5.0 | 5.0 | 5.0 |
| part (30) | 6.7 | 100.0 | 6.7 | 100.0 | 100.0 | 6.7 | 6.7 | 6.7 |
| ray (30) | 6.7 | 100.0 | 6.7 | 100.0 | 6.7 | 100.0 | 6.7 | 6.7 |
| region (30) | 40.0 | 100.0 | 40.0 | 100.0 | 100.0 | 40.0 | 40.0 | 40.0 |
| trap (20) | 0.0 | 55.0 | 0.0 | 55.0 | 55.0 | 0.0 | 0.0 | 0.0 |

pass@2 in %. Target groups pooled: g3 15.4, g4 97.3, g4_no_construct 15.4, g4_no_invert 89.1, g4_parts_only 71.8, g4_rays_only 40.9, g3_cpu 15.4, g4_random 15.4.
Paired gains 104, losses 0. Gates: G1_target_coverage pass, G2_target_pass2 pass, G3_compute_attribution pass, G4_candidate_attribution pass, G5_losses pass, G6_control_no_regression pass, G7_beyond_false_fits pass, G8_trap_top1 pass, G9_resources pass.

## 2. Real-puzzle check (FROZEN RESULT, exposed public training puzzles): g3 NO_REAL_GAIN_G3, g4 NO_REAL_GAIN_G4

Protocol `records/NEURAL_CORA_REALARC_G2G3G4_PROTOCOL_20261021.md` (manifest cf8fd6f1); 34 eligible public training puzzles; a puzzle counts only if every test output is correct. public ARC-AGI-2 training tasks (seen by v23; in NVARC's training mix): development evidence, not unseen performance

| arm | fits | coverage | pass@2 (all outputs) | wrong | CPU s (total) | native executions |
|---|---|---|---|---|---|---|
| g2 | 3 | 1 | 1 | 2 | 629.5 | 99000 |
| g3 | 5 | 3 | 3 | 2 | 810.3 | 99039 |
| g4 | 5 | 3 | 3 | 2 | 1610.5 | 1280054 |
| g4_no_construct | 5 | 3 | 3 | 2 | 1266.9 | 680559 |
| g4_no_invert | 5 | 3 | 3 | 2 | 958.2 | 207153 |
| g3_cpu | 5 | 3 | 3 | 2 | 1088.1 | 218732 |

Original CORA (reference): fits 10, coverage 5, certified 3 (all correct: 3; wrong 0), hard timeouts 7.
Paired: g3_vs_g2 +2/-0; g4_vs_g3 +0/-0; g4_vs_g2 +2/-0; g4_vs_g3_cpu +0/-0; g2_vs_native +0/-2; g3_vs_native +0/-0; g4_vs_native +0/-0; g4_no_construct_vs_native +0/-0; g4_no_invert_vs_native +0/-0; g3_cpu_vs_native +0/-0.
Version 4's correct answers by origin: {'g3': 1, 'g4_invert': 2}. Arm E: not run (no frozen addendum before the run).

## 3. CORA-only Kaggle runs (DESCRIPTIVE: exposed public evaluation, development evidence, not a competition score)

Private kernels, internet off, CPU. Public ARC-AGI-2 evaluation set, 120 puzzles (172 test inputs); solutions sha 84be4f4f.

- run A, G3/precision: 0.0% (0 puzzles)
- run A, G3/search_first: 0.0% (0 puzzles)
- run A, NATIVE_ONLY: 0.0% (0 puzzles)
- run B, C2/precision: 0.0% (0 puzzles)
- run B, C2/search_first: 0.0% (0 puzzles)
- run B, C1/precision: 0.0% (0 puzzles)
- run B, C1/search_first: 0.0% (0 puzzles)
- run B, NATIVE_ONLY: 0.0% (0 puzzles)

Attempt sources in run A (submission configuration): FALLBACK 273, NATIVE_CLAIMED 48, NATIVE_PARTIAL 23; the original engine fitted the demonstrations on 33 puzzles and every such attempt was wrong; version 3 found no fitting program on any puzzle; nothing was certified.
Rehearsal (`chimdiwalter/cora-only-g3-arc-agi-2`, competition input file): completed in 16292 s, inside the 12 h limit, with a valid submission file.

## Reading

Synthetic gains inside the designed grammar (syn-v3, syn-v4) again did not carry over to real puzzles: on 34 real puzzles versions 3 and 4 solved only what the original CORA solved, and on the 120 evaluation puzzles no CORA-only configuration solved any. The bottleneck is expressivity and generalization on harder puzzles, not answer selection.
