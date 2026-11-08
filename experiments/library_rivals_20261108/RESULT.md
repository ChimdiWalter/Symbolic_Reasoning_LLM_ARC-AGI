# Library rivals: result, lesson, direction

Pre-registered comparison (`PROTOCOL.md` c26d8ed1..., `FREEZE.json` 0ce26349..., GO digest 8b8399cb..., committed
3faf93d6). One detached run, 8 Nov 2026, 13:08:38Z to 13:36:39Z, in one CPU slot. The seal was written at
13:36:34Z, the one-use claim at 13:36:35Z and the completion marker at 13:36:39Z. Outputs are in `runs/main/`
(rows, seal, `RESULTS.json`, `REPORT.md`, per-task table `SCORES_PER_TASK.json`). Label "clean": no search errors, no
CPU-cap stops, no attempt with a cell outside 0 to 9.

**Read this with the frozen claim limits:**
- the held halves are previously used;
- the design was written knowing study B's held results;
- construction work is not matched (about 9,300 CPU-s for the 1D-ARC failure library against seconds for the
  compression);
- the compression is a single step;
- each comparison mixes operation space, source material and selection, so no credit goes to "kept from failures" as
  such.

This is a descriptive finding about this setting. It is not a fair head-to-head of library-learning methods in
general.

## Result

Correct outputs on the 464 held tasks (624 outputs), each arm using the same base search (A2, 150,000 executions,
two attempts). Each library has the same size per benchmark and enters as one production of cost 3.

| arm | ConceptARC (240) | Mini-ARC (75) | 1D-ARC (309) | all (624) |
|---|---|---|---|---|
| G0 alone | 4 | 2 | 0 | 6 |
| G0 + failure-kept library (2, 0, 19 entries) | 9 | 2 | 216 | 227 |
| G0 + compression library (same sizes) | 4 | 2 | 22 | 28 |
| G0 + random library, seed 1 | 4 | 2 | 0 | 6 |
| G0 + random library, seed 2 | 4 | 2 | 0 | 6 |

- **Primary, failure-kept against compression: "failure_kept beats compression."**
  - Correct outputs 227 against 28, a difference of 199.
  - Tasks where only failure-kept is correct: 218. Tasks where only compression is correct: 22.
  - Exact McNemar p below 0.000001.
  - Family-clustered 95% interval [89, 294].
- **Secondaries (Holm over five):**
  - against random seed 1: failure-kept beats it, +221 [138, 300];
  - against random seed 2: failure-kept beats it, +221 [138, 300];
  - ConceptARC: inconclusive, +5 [0, 15], raw p 0.5, Holm p 1.0;
  - Mini-ARC: tie (every library is empty there);
  - 1D-ARC: failure-kept beats compression, +194 [83, 289].
- **Descriptive:**
  - Compression against G0: +22 on 22 tasks, interval [0, 66], because the gain sits in one family.
  - Both random libraries equal G0's score on every task. One second attempt differs, on ConceptARC task co0040
    (random seed 2), without changing the score.
- **Which entries fired** (tasks whose found program uses the entry):
  - Failure-kept: 12 of the 19 1D-ARC operations, on 1 to 51 tasks each, and both ConceptARC operations (on 2 and 1
    tasks).
  - Compression: 1 of 19 on 1D-ARC (the flip program, on 22 tasks) and none on ConceptARC.
  - Random: none, in either library.
- **The 22 tasks only compression gets right are the 1D-ARC flip tasks.** The failure-kept library does not solve
  that family. The two libraries are complementary there.
- **Fidelity:** the failure-kept rows equal study B's object-reuse rows on all 464 tasks, with the same fits and the
  same predictions. This arm repeats a known result, as the protocol said. The new evidence is the matched rivals.

## Lesson

**In a low-success regime, a library compressed from successes had little to work with, while failures still
supplied specifications.** This describes what happened here. The design cannot separate the failure material from
the object-level operation space the failure library was built in, so it does not show which of the two made the
difference.
- **Few successes on the source halves.** Search solved few source tasks, even at four times the base budget:
  - 1D-ARC: 23 of 306 source tasks, all at four times the base budget, by only 2 distinct programs, 22 of them the
    same flip program;
  - ConceptARC: 5 of 80 (1 at the base budget, 4 at four times it);
  - Mini-ARC: 6 at the base budget, but no entries in any library, because the builder admitted nothing there and
    the sizes are matched.
- **What compression could build from that.** Even with the 194 training solvers added to the corpus, the 1D-ARC
  compression library has one in-domain entry, the flip program. Its seven other positive-utility fragments come from
  ARC training solvers and never fired on these held tasks. Its zero-utility entry and its ten padding entries never
  fired either.
- **What failures supplied.** On the same source half, the builder ran 283 failure units on 1D-ARC and admitted 19
  operations. Twelve of those fired on held tasks. On 1D-ARC, programs using a failure-kept operation were found on
  217 held tasks, and the library made 216 held tasks correct that G0 alone does not solve. Over all benchmarks the
  counts are 219 and 218.

This is a measured, descriptive fact about this regime, within the claim limits above. It does not show that
failure-derived libraries beat success-derived libraries in general.

## Direction

1. **Combine the two libraries.** They are complementary here: the success library's only gain, the 22 flip tasks,
   lies where the failure library fails. Keep both kinds, and test the union at matched size and budget.
2. **Test regimes with more successes.** Use larger source budgets, or domains with richer solved corpora, to measure
   where compression catches up.
3. **Match construction work.** Give the compression side the CPU the failure side spent, for example in repeated
   rounds of search and compression, with abstractions that have holes, closer to DreamCoder and Stitch.
4. **Draw the random control from the builder's own object-level space.** The schema-space draws only show that N
   extra whole-grid operations add nothing.
5. **Use fresh tasks.** Generate tasks from generators fixed before any library is built, so the outcome of no arm is
   known in advance.
