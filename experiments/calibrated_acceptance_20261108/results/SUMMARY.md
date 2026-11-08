# Calibrated acceptance on fresh held PUMA ROIs: results

Written by `scripts/caharness.py evaluate` at 2026-11-08T07:57:55Z. Held ROIs: 100 ({'primary': 50, 'metastatic': 50}); reference nuclei: 48013.

## Primary

- Label: **HARMFUL**.
- P1, CALIBRATED minus STRONG_NATIVE, mean per-image F1: -0.0020 [-0.0027, -0.0014] over 100 images; Holm-adjusted one-sided p 1.0000 (level 0.025).
- Harmful-edit rate of CALIBRATED: 0.7107438016528925 (95% CI [0.661970718465612, 0.75712006487945]); calibrated bound 0.6.
- P2, CALIBRATED minus CAL_BLIND: -0.0008152319257949536 (95% CI [-0.0010621611369355417, -0.0005731165915722422]); Holm-adjusted p 1.0000; failure evidence matters: False.

## Arms

| arm | pooled F1 | mean image F1 | accepted edits | beneficial | harmful | harmful rate |
|---|---|---|---|---|---|---|
| CALIBRATED | 0.8912 | 0.8872 | 605 | 175 | 430 | 0.7107438016528925 |
| CAL_BLIND_1 | 0.8912 | 0.8872 | 605 | 175 | 430 | 0.7107438016528925 |
| CAL_BLIND_2 | 0.8931 | 0.8892 | 0 | 0 | 0 | None |
| CAL_BLIND_3 | 0.8912 | 0.8872 | 605 | 175 | 430 | 0.7107438016528925 |
| CAL_BLIND_4 | 0.8931 | 0.8892 | 0 | 0 | 0 | None |
| CAL_BLIND_5 | 0.8912 | 0.8872 | 605 | 175 | 430 | 0.7107438016528925 |
| CAL_SHUFFLED_1 | 0.8931 | 0.8892 | 0 | 0 | 0 | None |
| CAL_SHUFFLED_2 | 0.8931 | 0.8892 | 0 | 0 | 0 | None |
| CAL_SHUFFLED_3 | 0.8931 | 0.8892 | 0 | 0 | 0 | None |
| CAL_SHUFFLED_4 | 0.8931 | 0.8892 | 0 | 0 | 0 | None |
| CAL_SHUFFLED_5 | 0.8931 | 0.8892 | 0 | 0 | 0 | None |
| MATCHED_SEARCH | 0.8789 | 0.8749 | 3271 | 735 | 2536 | 0.7752980739834913 |
| MATCHED_SEARCH_U5 | 0.8744 | 0.8698 | 17694 | 1279 | 3018 | 0.1705662936588674 |
| NATIVE | 0.8669 | 0.8610 |  |  |  |  |
| STRICT | 0.8931 | 0.8892 | 0 | 0 | 0 | None |
| STRONG_NATIVE | 0.8931 | 0.8892 |  |  |  |  |
| TOLERANT | 0.8911 | 0.8869 | 318 | 39 | 279 | 0.8773584905660378 |
| TUNED | 0.8931 | 0.8892 |  |  |  |  |

## Contrasts (per-image F1; 95% bootstrap over images, 10,000 resamples)

| contrast | mean [95% CI] | images better/worse/equal |
|---|---|---|
| CALIBRATED - STRONG_NATIVE | -0.0020 [-0.0027, -0.0014] | 31/69/0 |
| CALIBRATED - CAL_BLIND | -0.0008 [-0.0011, -0.0006] | 31/69/0 |
| CALIBRATED - CAL_SHUFFLED | -0.0020 [-0.0027, -0.0014] | 31/69/0 |
| CALIBRATED - STRICT | -0.0020 [-0.0027, -0.0014] | 31/69/0 |
| CALIBRATED - TOLERANT | +0.0003 [-0.0003, +0.0009] | 50/46/4 |
| CALIBRATED - MATCHED_SEARCH | +0.0123 [+0.0107, +0.0139] | 96/4/0 |
| CALIBRATED - MATCHED_SEARCH_U5 | +0.0173 [+0.0153, +0.0195] | 98/2/0 |
| CALIBRATED - NATIVE | +0.0262 [+0.0211, +0.0314] | 85/15/0 |
| CALIBRATED - TUNED | -0.0020 [-0.0026, -0.0014] | 33/66/1 |
| CAL_BLIND_1 - STRONG_NATIVE | -0.0020 [-0.0027, -0.0014] | 31/69/0 |
| CAL_BLIND_2 - STRONG_NATIVE | +0.0000 [+0.0000, +0.0000] | 0/0/100 |
| CAL_BLIND_3 - STRONG_NATIVE | -0.0020 [-0.0027, -0.0014] | 31/69/0 |
| CAL_BLIND_4 - STRONG_NATIVE | +0.0000 [+0.0000, +0.0000] | 0/0/100 |
| CAL_BLIND_5 - STRONG_NATIVE | -0.0020 [-0.0027, -0.0014] | 31/69/0 |
| CAL_SHUFFLED_1 - STRONG_NATIVE | +0.0000 [+0.0000, +0.0000] | 0/0/100 |
| CAL_SHUFFLED_2 - STRONG_NATIVE | +0.0000 [+0.0000, +0.0000] | 0/0/100 |
| CAL_SHUFFLED_3 - STRONG_NATIVE | +0.0000 [+0.0000, +0.0000] | 0/0/100 |
| CAL_SHUFFLED_4 - STRONG_NATIVE | +0.0000 [+0.0000, +0.0000] | 0/0/100 |
| CAL_SHUFFLED_5 - STRONG_NATIVE | +0.0000 [+0.0000, +0.0000] | 0/0/100 |
| MATCHED_SEARCH - STRONG_NATIVE | -0.0143 [-0.0162, -0.0125] | 6/94/0 |
| MATCHED_SEARCH_U5 - STRONG_NATIVE | -0.0194 [-0.0216, -0.0172] | 1/99/0 |
| STRICT - STRONG_NATIVE | +0.0000 [+0.0000, +0.0000] | 0/0/100 |
| TOLERANT - STRONG_NATIVE | -0.0023 [-0.0029, -0.0018] | 5/83/12 |
| CAL_BLIND - STRONG_NATIVE | -0.0012 [-0.0016, -0.0009] | 31/69/0 |
| CAL_SHUFFLED - STRONG_NATIVE | +0.0000 [-0.0000, +0.0000] | 0/0/100 |
