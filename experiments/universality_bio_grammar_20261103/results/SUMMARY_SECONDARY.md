# U5 results (written by u5eval.py evaluate)

Roles: A = livecell, targets = ['nuinsseg', 'monusac']; ineligible = ['fluoecoli', 'fnc']; unsuitable = [].

## livecell: label NON_DEGRADATION_ONLY; growth supported: False

Parents: {'calibration': 12, 'evaluation': 19}; evaluation images 288.

| arm | pooled F1 | mean parent F1 | pooled AP | edits | beneficial | harmful | edit precision [95% CI] | coverage |
|---|---|---|---|---|---|---|---|---|
| NATIVE | 0.5415 | 0.4812 | 0.1869 |  |  |  |  |  |
| TUNED | 0.5628 | 0.5332 | 0.2166 |  |  |  |  |  |
| STRONG_NATIVE | 0.5628 | 0.5332 | 0.2166 |  |  |  |  |  |
| ALL_ON | 0.5410 | 0.5084 | 0.1728 | 124142 | 2492 | 3095 | 0.020 [0.01404680978313517, 0.028930799543800324] | 2.2061 |
| MATCHED_SEARCH | 0.5645 | 0.5334 | 0.2083 | 20144 | 308 | 183 | 0.015 [0.008521192370392953, 0.025107190080700725] | 0.3580 |
| CORA | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_1 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_2 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_3 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_4 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_5 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_1 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_2 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_3 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_4 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_5 | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |
| CORA_FULL | 0.5628 | 0.5332 | 0.2166 | 0 | 0 | 0 | undefined | 0.0000 |

| contrast (per parent) | F1 mean [95% CI] better/worse/equal |
|---|---|
| CORA - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| CORA - NATIVE | +0.0520 [+0.0299, +0.0760] [17, 2, 0] |
| CORA - TUNED | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| CORA - ALL_ON | +0.0248 [+0.0161, +0.0354] [18, 1, 0] |
| CORA - MATCHED_SEARCH | -0.0002 [-0.0029, +0.0024] [10, 8, 1] |
| CORA - FAILURE_BLIND | -0.0000 [-0.0000, +0.0000] [0, 0, 19] |
| CORA - SHUFFLED | -0.0000 [-0.0000, +0.0000] [0, 0, 19] |
| CORA - CORA_FULL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| NATIVE - ABSTAIN_ALL | -0.0520 [-0.0760, -0.0299] [2, 17, 0] |
| TUNED - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| ALL_ON - ABSTAIN_ALL | -0.0248 [-0.0354, -0.0161] [1, 18, 0] |
| MATCHED_SEARCH - ABSTAIN_ALL | +0.0002 [-0.0024, +0.0029] [8, 10, 1] |
| FAILURE_BLIND_1 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND_2 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND_3 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND_4 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND_5 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_1 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_2 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_3 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_4 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_5 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| CORA_FULL - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |

## nuinsseg: label NON_DEGRADATION_ONLY; growth supported: False

Parents: {'calibration': 12, 'evaluation': 19}; evaluation images 429.

| arm | pooled F1 | mean parent F1 | pooled AP | edits | beneficial | harmful | edit precision [95% CI] | coverage |
|---|---|---|---|---|---|---|---|---|
| NATIVE | 0.4615 | 0.4507 | 0.1548 |  |  |  |  |  |
| TUNED | 0.5824 | 0.5653 | 0.1915 |  |  |  |  |  |
| STRONG_NATIVE | 0.5823 | 0.5650 | 0.1915 |  |  |  |  |  |
| ALL_ON | 0.5848 | 0.5647 | 0.1874 | 36055 | 620 | 669 | 0.017 [0.013149828993882624, 0.023024464371293876] | 2.6080 |
| MATCHED_SEARCH | 0.5954 | 0.5744 | 0.1948 | 3963 | 1082 | 842 | 0.273 [0.19845927201887284, 0.3563591964014081] | 0.2867 |
| CORA | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_1 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_2 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_3 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_4 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_5 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_1 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_2 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_3 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_4 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_5 | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| CORA_FULL | 0.5819 | 0.5649 | 0.1914 | 4000 | 1 | 7 | 0.000 [0.0, 0.0007505711412337175] | 0.2893 |
| CORA_INDOMAIN | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |
| PROGRAM_TRANSFER | 0.5823 | 0.5650 | 0.1915 | 0 | 0 | 0 | undefined | 0.0000 |

| contrast (per parent) | F1 mean [95% CI] better/worse/equal |
|---|---|
| CORA - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| CORA - NATIVE | +0.1143 [+0.0784, +0.1499] [18, 1, 0] |
| CORA - TUNED | -0.0003 [-0.0006, -0.0000] [2, 4, 13] |
| CORA - ALL_ON | +0.0003 [-0.0084, +0.0089] [11, 8, 0] |
| CORA - MATCHED_SEARCH | -0.0094 [-0.0225, +0.0063] [5, 14, 0] |
| CORA - FAILURE_BLIND | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| CORA - SHUFFLED | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| CORA - CORA_FULL | +0.0001 [+0.0000, +0.0003] [3, 0, 16] |
| CORA - CORA_INDOMAIN | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| CORA - PROGRAM_TRANSFER | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| NATIVE - ABSTAIN_ALL | -0.1143 [-0.1499, -0.0784] [1, 18, 0] |
| TUNED - ABSTAIN_ALL | +0.0003 [+0.0000, +0.0006] [4, 2, 13] |
| ALL_ON - ABSTAIN_ALL | -0.0003 [-0.0089, +0.0084] [8, 11, 0] |
| MATCHED_SEARCH - ABSTAIN_ALL | +0.0094 [-0.0063, +0.0225] [14, 5, 0] |
| FAILURE_BLIND_1 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND_2 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND_3 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND_4 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND_5 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_1 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_2 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_3 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_4 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED_5 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| CORA_FULL - ABSTAIN_ALL | -0.0001 [-0.0003, +0.0000] [0, 3, 16] |
| CORA_INDOMAIN - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| PROGRAM_TRANSFER - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 19] |
| FAILURE_BLIND - ABSTAIN_ALL | -0.0000 [-0.0000, +0.0000] [0, 0, 19] |
| SHUFFLED - ABSTAIN_ALL | -0.0000 [-0.0000, +0.0000] [0, 0, 19] |

## monusac: label NON_DEGRADATION_ONLY; growth supported: False

Parents: {'calibration': 27, 'evaluation': 40}; evaluation images 169.

| arm | pooled F1 | mean parent F1 | pooled AP | edits | beneficial | harmful | edit precision [95% CI] | coverage |
|---|---|---|---|---|---|---|---|---|
| NATIVE | 0.6439 | 0.6549 | 0.2833 |  |  |  |  |  |
| TUNED | 0.6721 | 0.6977 | 0.2891 |  |  |  |  |  |
| STRONG_NATIVE | 0.6745 | 0.6951 | 0.2922 |  |  |  |  |  |
| ALL_ON | 0.6802 | 0.7040 | 0.2837 | 67566 | 1798 | 1906 | 0.027 [0.022036689197413535, 0.03128337535184478] | 2.5993 |
| MATCHED_SEARCH | 0.6843 | 0.7068 | 0.2948 | 2230 | 989 | 1158 | 0.443 [0.38661970507707927, 0.5092412676840156] | 0.0858 |
| CORA | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_1 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_2 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_3 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_4 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| FAILURE_BLIND_5 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_1 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_2 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_3 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_4 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| SHUFFLED_5 | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| CORA_FULL | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| CORA_INDOMAIN | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |
| PROGRAM_TRANSFER | 0.6745 | 0.6951 | 0.2922 | 0 | 0 | 0 | undefined | 0.0000 |

| contrast (per parent) | F1 mean [95% CI] better/worse/equal |
|---|---|
| CORA - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| CORA - NATIVE | +0.0403 [+0.0262, +0.0545] [34, 6, 0] |
| CORA - TUNED | -0.0026 [-0.0083, +0.0024] [18, 20, 2] |
| CORA - ALL_ON | -0.0089 [-0.0148, -0.0031] [11, 29, 0] |
| CORA - MATCHED_SEARCH | -0.0116 [-0.0169, -0.0066] [7, 33, 0] |
| CORA - FAILURE_BLIND | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| CORA - SHUFFLED | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| CORA - CORA_FULL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| CORA - CORA_INDOMAIN | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| CORA - PROGRAM_TRANSFER | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| NATIVE - ABSTAIN_ALL | -0.0403 [-0.0545, -0.0262] [6, 34, 0] |
| TUNED - ABSTAIN_ALL | +0.0026 [-0.0024, +0.0083] [20, 18, 2] |
| ALL_ON - ABSTAIN_ALL | +0.0089 [+0.0031, +0.0148] [29, 11, 0] |
| MATCHED_SEARCH - ABSTAIN_ALL | +0.0116 [+0.0066, +0.0169] [33, 7, 0] |
| FAILURE_BLIND_1 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| FAILURE_BLIND_2 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| FAILURE_BLIND_3 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| FAILURE_BLIND_4 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| FAILURE_BLIND_5 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| SHUFFLED_1 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| SHUFFLED_2 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| SHUFFLED_3 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| SHUFFLED_4 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| SHUFFLED_5 - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| CORA_FULL - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| CORA_INDOMAIN - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| PROGRAM_TRANSFER - ABSTAIN_ALL | +0.0000 [+0.0000, +0.0000] [0, 0, 40] |
| FAILURE_BLIND - ABSTAIN_ALL | -0.0000 [-0.0000, +0.0000] [0, 0, 40] |
| SHUFFLED - ABSTAIN_ALL | -0.0000 [-0.0000, +0.0000] [0, 0, 40] |

## Transfer to the two targets (conjunction; pooled contrasts descriptive)

- CORA - ABSTAIN_ALL (mean of the two targets, stratified): {'mean': 0.0, 'ci95': [0.0, 0.0]}
- CORA - ALL_ON (mean of the two targets, stratified): {'mean': -0.004295349640571466, 'ci95': [-0.009576510264551799, 0.000820387350380749]}
- CORA - MATCHED_SEARCH (mean of the two targets, stratified): {'mean': -0.01052827648704912, 'ci95': [-0.017646197596447206, -0.0023987021228815382]}
- CORA - FAILURE_BLIND (mean of the two targets, stratified): {'mean': 5.624156111587964e-18, 'ci95': [1.3877787807814458e-18, 1.1248312223175928e-17]}
- CORA - SHUFFLED (mean of the two targets, stratified): {'mean': 5.624156111587964e-18, 'ci95': [1.3877787807814458e-18, 1.1321353211638109e-17]}
- status: TWO_TARGETS
- LEARNED_TRANSFER: False
