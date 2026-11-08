# Library-transfer and object-growth test (study B): results (written by ngb/report.py)

Status: complete. Primary rule applied (from the GO): arm5_vs_arm4. Held tasks: 460; localisable G0 failures: 436. Holm family: 13 secondaries.

| arm | correct outputs | answered | precision | failure rows |
|---|---|---|---|---|
| arm 1: G0 alone | 7 | 9 | 0.7778 | 0 |
| arm 2: G0 plus the promoted library | 45 | 54 | 0.8333 | 0 |
| arm 3: G0 plus a shuffled library | 8 | 12 | 0.6667 | 0 |
| arm 4a: matched static search (library allowance) | 60 | 70 | 0.8571 | 0 |
| arm 5: object-level growth, reuse | 231 | 235 | 0.983 | 0 |
| arm 6: reuse with a shuffled object registry | 7 | 9 | 0.7778 | 0 |
| arm 4b: matched static search (object allowance) | 124 | 146 | 0.8493 | 0 |
| arm 7: task-local object construction | 357 | 385 | 0.9273 | 0 |
| arm 8: construction with donor demonstrations | 9 | 377 | 0.0239 | 0 |
| arm 4c: matched static search (construction allowance) | 124 | 146 | 0.8493 | 0 |

**Primary (obj vs static_obj): obj beats static_obj**; exact p = 0.0, total difference 107, family-clustered 95% interval [4, 202].

Secondary (decisions at the Holm-adjusted p):

- S0_library_vs_G0: lib beats G0; raw p = 0.0, Holm p = 0.0, difference 38, interval [9, 87]
- S1_library_vs_matched_static: inconclusive; raw p = 0.049042, Holm p = 0.294252, difference -15, interval [-33, 0]
- S2_library_vs_shuffled_library: lib beats shuf; raw p = 0.0, Holm p = 0.0, difference 37, interval [7, 86]
- S3_reuse_vs_shuffled_registry: obj beats obj_shuf; raw p = 0.0, Holm p = 0.0, difference 224, interval [140, 304]
- S4_wrong_answers_library_vs_matched_static: inconclusive; raw p = 1.0, Holm p = 1.0, difference -1, interval [-11, 8]
- S5_concept_arc_library_vs_G0: inconclusive; raw p = 0.03125, Holm p = 0.21875, difference 12, interval [3, 22]
- S5_mini_arc_library_vs_G0: tie; raw p = 1.0, Holm p = 1.0, difference 0, interval [0, 0]
- S5_1d_arc_library_vs_G0: inconclusive; raw p = 0.0, Holm p = 0.0, difference 26, interval [0, 72]
- S6_arc_agi_2_library_vs_matched_static: tie; raw p = 1.0, Holm p = 1.0, difference 0, interval [0, 0]
- S7_arc_agi_2_reuse_vs_matched_static: inconclusive; raw p = 1.0, Holm p = 1.0, difference -1, interval [-3, 0]
- S8_construction_vs_matched_static: construct beats static_construct; raw p = 0.0, Holm p = 0.0, difference 233, interval [157, 307]
- S9_construction_vs_donor_demonstrations: construct beats construct_shuf; raw p = 0.0, Holm p = 0.0, difference 348, interval [288, 400]
- S10_arc_agi_2_construction_vs_matched_static: tie; raw p = 1.0, Holm p = 1.0, difference 2, interval [-3, 9]
