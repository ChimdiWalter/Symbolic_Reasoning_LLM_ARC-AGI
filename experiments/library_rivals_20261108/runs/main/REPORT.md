# Library rivals: results (held halves, previously used)

Tasks 464, outputs 624. GO digest 8b8399cb7185984b2b824e688b7f8f78fd88f5245d8815fa0850e06ba303ed68.

| arm | correct outputs | answered | CPU safety-cap stops | errors | CPU-s total, max |
|---|---|---|---|---|---|
| G0 alone | 6 | 8 | 0 | 0 | 343.5, 2.725 |
| G0 + failure-kept library | 227 | 228 | 0 | 0 | 314.0, 2.862 |
| G0 + compression library | 28 | 30 | 0 | 0 | 324.4, 2.79 |
| G0 + random library (seed 1) | 6 | 8 | 0 | 0 | 322.5, 2.671 |
| G0 + random library (seed 2) | 6 | 8 | 0 | 0 | 335.5, 2.977 |

**Primary (failure-kept against compression): failure_kept beats compression**; correct 227 against 28, difference 199, tasks only failure-kept 218, only compression 22, exact p < 0.000001, family-clustered 95% interval [89, 294].

Secondaries (Holm over five; decisions at the adjusted p):

- S1_failure_kept_vs_random_1: failure_kept beats random_1; difference 221, interval [138, 300], raw p < 0.000001, Holm p < 0.000001
- S2_failure_kept_vs_random_2: failure_kept beats random_2; difference 221, interval [138, 300], raw p < 0.000001, Holm p < 0.000001
- S3_concept_arc_failure_kept_vs_compression: inconclusive; difference 5, interval [0, 15], raw p 0.5, Holm p 1.0
- S4_mini_arc_failure_kept_vs_compression: tie; difference 0, interval [0, 0], raw p 1.0, Holm p 1.0
- S5_1d_arc_failure_kept_vs_compression: failure_kept beats compression; difference 194, interval [83, 289], raw p < 0.000001, Holm p < 0.000001
