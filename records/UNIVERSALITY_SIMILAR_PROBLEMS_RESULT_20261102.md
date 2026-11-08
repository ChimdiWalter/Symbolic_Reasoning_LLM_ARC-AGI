# Result U2: the submitted CORA systems on public ARC-style benchmarks (2 Nov 2026)

**Provenance.**
- The protocol `experiments/universality_similar_problems_20261102/PROTOCOL.md` (sha256 `b7caae6f…`) was
  pre-registered in commit 517d0469 at 06:29:08Z, before any download.
- The data were cloned at 06:29:27Z.
- Results were written by the detached chain in commit 1a20b6ee: `results/SUMMARY.md` and `results/RESULTS.json`.
- An independent blind review of the protocol (sha256 `3808c8f3…`) asked only for the limitations below to be
  recorded. Nothing was rerun or tuned.
- Total compute: 1.37 CPU-h, no GPU.

## What ran

**Systems.** All three were byte-identical to their entry notebooks. Every embedded package file matched its frozen
manifest, and every file was re-hashed before and after each of the 18 arms with no mismatch.

| id | system | notebook | what it is |
|---|---|---|---|
| a | O+ v2 | `f683136c…` | CAST v1 at 45/90 s, then R29 |
| b | H's CORA component | `0e09afd4…` | `cast_selective_v2` under rule B3, at 15/30 s. Input-copy stand-ins replace H's neural model C4, which was not run |
| c | O | `f2019b5d…` | `cast_v1` at 15/30 s |

**Benchmarks.** Each came from its authors' repository, and all three are fresh for CORA: no input/output pair
equals one in the ARC-AGI-2 training or evaluation sets, and no task was excluded for overlap.

| benchmark | licence | tasks | test outputs | notes |
|---|---|---|---|---|
| ConceptARC | MIT | 160 | 480 | 16 concepts |
| Mini-ARC | Apache-2.0 | 149 | 149 | 5 x 5 grids |
| 1D-ARC | MIT | 615 | 615 | 14 of 18 types; 286 tasks wider than 30 cells are outside the entries' input domain |

**Control.** In the SHUFFLED arm, each task keeps its own test inputs but receives the demonstrations of a donor task
from another type or concept.

## Results

For each system, the REAL row is followed by its SHUFFLED row.
- **Answered:** non-copy answers.
- **Precision:** correct / answered. All intervals are Wilson 95% over test outputs.
- **pass@2:** includes the input-copy fallback.

| benchmark (copy baseline) | system | answered / outputs (coverage) | correct | precision [95% CI] | pass@2 | label |
|---|---|---|---|---|---|---|
| ConceptARC (0.027) | a O+ v2 | 54 / 480 (0.113) | 44 | 0.815 [0.692, 0.896] | 0.117 | NOT_ESTABLISHED |
| | a, shuffled | 50 / 480 (0.104) | 0 | 0.000 [0, 0.071] | 0.027 | |
| | b H's CORA (B3) | 15 / 480 (0.031) | 14 | 0.933 [0.702, 0.988] | 0.056 | **VERIFIED_TRANSFER** |
| | b, shuffled | 4 / 480 (0.008) | 0 | 0.000 [0, 0.490] | 0.027 | |
| | c O (cast_v1) | 41 / 480 (0.085) | 34 | 0.829 [0.687, 0.915] | 0.098 | NOT_ESTABLISHED |
| | c, shuffled | 44 / 480 (0.092) | 0 | 0.000 [0, 0.080] | 0.027 | |
| Mini-ARC (0.013) | a | 20 / 149 (0.134) | 19 | 0.950 [0.764, 0.991] | 0.141 | **VERIFIED_TRANSFER** |
| | a, shuffled | 7 / 149 | 0 | 0.000 [0, 0.354] | 0.013 | |
| | b | 9 / 149 (0.060) | 9 | 1.000 [0.701, 1.000] | 0.074 | NOT_ESTABLISHED (9 < 10 correct) |
| | b, shuffled | 2 / 149 | 0 | 0.000 [0, 0.658] | 0.013 | |
| | c | 12 / 149 (0.081) | 12 | 1.000 [0.758, 1.000] | 0.094 | NOT_ESTABLISHED |
| | c, shuffled | 7 / 149 | 0 | 0.000 [0, 0.354] | 0.013 | |
| 1D-ARC (0.000) | a | 308 / 615 (0.501) | 295 | 0.958 [0.929, 0.975] | 0.480 | NOT_ESTABLISHED |
| | a, shuffled | 250 / 615 (0.407) | 6 | 0.024 [0.011, 0.051] | 0.010 | |
| | b | 58 / 615 (0.094) | 48 | 0.828 [0.711, 0.904] | 0.078 | NOT_ESTABLISHED |
| | b, shuffled | 33 / 615 | 1 | 0.030 [0.005, 0.153] | 0.002 | |
| | c | 63 / 615 (0.102) | 51 | 0.810 [0.696, 0.888] | 0.083 | NOT_ESTABLISHED |
| | c, shuffled | 55 / 615 | 1 | 0.018 [0.003, 0.096] | 0.002 | |

**Statuses:** every task returned OK, except one TIMEOUT each for b and c on Mini-ARC.

**Where the correct answers fall:**
- **ConceptARC:** system a's 44 correct answers span 9 of the 16 concepts; 7 concepts get none (Center, CleanUp, Count,
  ExtendToBoundary, InsideOutside, Order, TopBottom3D).
- **1D-ARC:** system a solves almost every task of six types (fill 48/48, move_1p 49/50, move_2p 45/50, move_3p 39/50,
  scale_dp 51/51, recolor_cnt 39/40). It gets none in five (flip, hollow, padded_fill, recolor_cmp, recolor_oe).

## What the labels mean (protocol §7, exactly)

**VERIFIED_TRANSFER requires all four of these, else the label is NOT_ESTABLISHED:**
1. at least 10 correct answers on REAL;
2. a REAL precision whose Wilson lower bound is at least 0.5;
3. SHUFFLED answering at most half as often as REAL;
4. either the SHUFFLED precision's upper bound falls below the REAL precision's lower bound, or SHUFFLED gives no
   answer.

**Why 1D-ARC earns no VERIFIED_TRANSFER.** O+ v2 is correct on 295 of 615 outputs, with precision 0.958. But with
shuffled demonstrations it still answers 250 times, which is more than half of 308, and 244 of those answers are wrong.
- Precision collapses (0.958 to 0.024), but the answer count does not.
- The reason is that a donor task's demonstrations are themselves consistent. CAST and R29 therefore find programs
  that fit them, and apply those programs to test inputs from a different task.
- So verification guards against programs that do not fit the given evidence. It cannot tell that the evidence belongs
  to another task.

**The same reason holds elsewhere:**
- every system on 1D-ARC;
- a and c on ConceptARC;
- c on Mini-ARC, narrowly: 7 shuffled answers against the allowed 6.

**Where the label is reached:**
- b on ConceptARC: 15 answers fall to 4, and 14 correct to 0;
- a on Mini-ARC: 20 answers fall to 7, and 19 correct to 0.

**Where precision collapses:** in every pairing of system and benchmark, from 0.81 to 1.00 on REAL down to 0.00 to
0.03 on SHUFFLED.

## Attribution inside O+ v2

O+ v2 is two packages: CAST v1, then R29. R29 is part of the submitted O+ v2 entry, but it came from the independent
lane, not from CORA-CAST. This breakdown of the REAL arms is descriptive and was made after the fact from the
per-package result files.

| benchmark | CAST v1 answers (correct) | answers from R29 only (correct) | wrong CAST v1 answer, R29 correct | O+ v2 correct |
|---|---|---|---|---|
| ConceptARC | 41 (34) | 13 (10) | 0 | 44 |
| Mini-ARC | 13 (13) | 7 (6) | 0 | 19 |
| 1D-ARC | 63 (51) | 245 (240) | 4 | 295 |

- **On 1D-ARC, most of O+ v2's gain comes from R29:** 244 of its 295 correct answers, against 51 from CAST v1.
- **Under shuffling,** R29 also gives most of the wrong answers (195 of 250).
- **CAST v1 alone** (system c, 15/30 s) gives exactly the same answers as O+ v2's CAST v1 package (45/90 s) on 1D-ARC
  and ConceptARC. On Mini-ARC the longer caps add one answer, the task that timed out for c.
- **H's CORA component** (b, rule B3) answers less often than c, about as precisely, and resists shuffling more.

## Limitations (from the independent review)

- **No native or matched-search control.** The only control is shuffled demonstrations. The protocol was frozen before
  that directive, and was not reopened. Gains are therefore not separated from search compute, nor compared with a
  strong native ARC solver.
- **Unclustered intervals.** Intervals by type and concept use test outputs or tasks as units, without clustering the
  shared 1D-ARC types or ConceptARC concepts.
- **Non-copy answer proxies.** For b and c, "answered" counts only outputs that differ from the input copy. A package
  that certified an unchanged identity output is counted as not answering.
- **Input-size exclusion.** 286 1D-ARC tasks (four types in full) were excluded by the input-size rule.
- **NVARC training data.** NVARC's model, which H's neural part re-implements, was trained on data that includes
  ConceptARC and Mini-ARC. This matters for H's complete entry, not for CAST, which was never trained or tuned on them.
  These results say nothing about H's neural part.
- **Meaning of the label.** VERIFIED_TRANSFER under this rubric means observed portability and performance on these
  benchmarks. It is not learned transfer, nor universal reasoning.

## Claim for the paper

> On three public ARC-style benchmarks unused in development (ConceptARC, Mini-ARC and 1D-ARC; no input/output pair in
> common with ARC-AGI-2), the CORA components of our entries ran byte-identical and were usually right when they
> answered. They answered 3% to 50% of test outputs, with 81% to 100% precision. O+ v2 solved 48% of the 1D-ARC
> outputs within the entries' 30-cell limit, most of them through its second package, R29, which came from the
> independent lane. When we swapped in another task's demonstrations, precision fell to 0% to 3%: answers depend on
> the evidence. But the number of answers fell by more than half in only three of the nine pairings, because
> consistent demonstrations from the wrong task still fit. By our pre-registered rubric, two of nine system-benchmark pairs
> reached verified transfer. This is portability and usefulness on similar problems, without a native or
> matched-compute baseline; it is not learned transfer or universal reasoning.

## Deviations

- None in procedure.
- The finisher's first status line was lost to a race on the runs folder; its later lines are complete.
- Mini-ARC's 10 user-trace files are not tasks and were not used.
- The CAST v1 and R29 breakdown above was not a pre-registered output.
