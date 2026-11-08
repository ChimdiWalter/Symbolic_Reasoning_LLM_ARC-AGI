# Library rivals: independent post-score audit

Audited on 8 Nov 2026, after the single held run. The run used GO digest
`8b8399cb7185984b2b824e688b7f8f78fd88f5245d8815fa0850e06ba303ed68`; its outputs were committed in 6738fc60 and
RESULT.md in ac88c8d7.

Labels, as in the protocol:
- **G0** is the base grammar.
- **The GO** is the coordinator's one-use go-ahead file.
- **S1 to S5** are the five secondary comparisons.
- **The per-task table** is `runs/main/SCORES_PER_TASK.json`.
- **Study B** is the earlier library-transfer test, whose object-reuse arm the failure-kept arm repeats.

## Verdict: PASS WITH NOTES

Custody is intact, every number in RESULTS.json is reproduced exactly from the per-task table, and the agreement with
study B is confirmed. The notes concern the wording of RESULT.md only; none changes a number or a decision.

## How the audit was done

- **Two read-only scripts** (outside the repository), run inside the shared CPU-slot wrapper at nice 19.
- **What they read:**
  - FREEZE.json and the frozen files (digests only), the GO, the split, `meta.json` (number of test outputs only),
    the built libraries and the configuration;
  - in `runs/main`: the rows, the seal, the per-task table and RESULTS.json;
  - study B's object-reuse prediction rows.
- **Statistics:** recomputed from the per-task table alone, with code written for this audit from the protocol's
  description, not imported from the study:
  - the exact two-sided sign test;
  - the family-clustered percentile bootstrap, with benchmarks as strata, families as clusters and Mini-ARC tasks
    singly, random.Random(20261105), 10,000 draws, and study A's percentile positions;
  - Holm's adjustment.
- **Never opened:** no solution or answer file. No task was searched or scored again, and neither `phase all` nor
  `phase score` was run.

## Findings

### 1. Custody: intact

- **Freeze.** FREEZE.json (`0ce26349...`) verifies: 119 files, the 2 launch scripts and the 6 benchmark input files
  all have their frozen digests. PROTOCOL.md is the frozen version (`c26d8ed1...`).
- **The GO.**
  - It has four lines: this protocol's digest, this freeze's digest, the primary, and a 64-hex nonce.
  - Its digest is the one quoted.
  - It was committed at 13:08:07Z (3faf93d6), and the file is read-only.
- **Launch.**
  - The detached record (`outputs/detached/library_rivals_20261108/`) holds the protocol's command, run from the
    repository root. It has one START (13:08:38Z) and one EXIT 0 (13:36:39Z), and stderr is empty.
  - It is the only detached record of this study.
  - The progress log names the frozen launcher `launch/run_main.sh`, which passes the CPU-slot flag. The run record
    cannot show that flag, because `run_detached.sh` records the command after removing it.
  - The evidence is consistent with exactly one launch. The 13:28Z autosave commit holds partial row files for 12 of
    the 15 files, each an exact prefix of the final file, so the run continued without any rewrite.
- **Rows.**
  - There are 2,320 rows: five arms times 464 tasks.
  - Each file's task set is exactly that benchmark's held list, with no duplicates.
  - Every row carries the GO digest, its arm's library digest (recomputed from the frozen libraries), the G0 digest
    and the right benchmark, arm and family.
  - Fits and predictions agree in every row.
  - Stops: no CPU-cap stop and no search error in any arm.
- **Seal.** It names the GO and 464 tasks, and its 15 file digests equal the row files.
- **Times.** The seal (13:36:34Z) precedes the claim (13:36:35Z), which precedes the completion marker (13:36:39Z);
  file times agree.
- **Markers.** There is one claim and one completion marker, both at the study root and both named by the GO digest.
  The only other markers are the dry runs' "dry-run" markers in `checks/` and `runs/review_dry*`. No seal or
  results file outside `runs/main` carries this GO digest, so no other folder was sealed or scored under it.
- **Per-task table.**
  - Its digest equals the one in RESULTS.json.
  - Its 464 rows match the split (family, cluster) and the input metadata (624 outputs).
  - Its answered counts, stops and CPU times match the rows.
  - No correct count exceeds a task's outputs, and none is positive without a fit.
- **Scoring consistency** (no answers needed): in 3,672 task-and-arm-pair cases the two arms made identical attempts,
  and in every one of them their correct counts are equal.

### 2. Statistics: every number reproduced

All 16 comparison groups in RESULTS.json match exactly: the primary, the five secondaries with Holm, the five
descriptive comparisons, the three per-benchmark primaries, the totals (including CPU) and the label "clean".

Key values (p before rounding):

| comparison | difference | tasks only A / only B | exact p | Holm p | 95% interval | decision |
|---|---|---|---|---|---|---|
| primary: failure-kept vs compression | +199 (227 vs 28) | 218 / 22 | 9.6e-42 | (primary) | [89, 294] | failure_kept beats compression |
| S1: failure-kept vs random seed 1 | +221 | 218 / 0 | 4.7e-66 | 2.4e-65 | [138, 300] | failure_kept beats random_1 |
| S2: failure-kept vs random seed 2 | +221 | 218 / 0 | 4.7e-66 | 2.4e-65 | [138, 300] | failure_kept beats random_2 |
| S3: ConceptARC | +5 | 2 / 0 | 0.5 | 1.0 | [0, 15] | inconclusive |
| S4: Mini-ARC | 0 | 0 / 0 | 1.0 | 1.0 | [0, 0] | tie |
| S5: 1D-ARC | +194 | 216 / 22 | 3.2e-41 | 9.5e-41 | [83, 289] | failure_kept beats compression |

Descriptive comparisons:
- failure-kept against G0: +221, interval [138, 300];
- compression against G0: +22, interval [0, 66];
- each random library against G0: 0;
- compression against random seed 1: +22, interval [0, 66].

Totals per arm: G0 6, failure-kept 227, compression 28, random 6 and 6. Per benchmark, ConceptARC, Mini-ARC and 1D-ARC
in that order:
- G0: 4, 2, 0;
- failure-kept: 9, 2, 216;
- compression: 4, 2, 22;
- each random library: 4, 2, 0.

The decisions do not hinge on the percentile convention: the primary's lower end is 89, and S3's p is 0.5 before
any interval is consulted.

### 3. Agreement with study B's object-reuse rows: confirmed

The three prediction files have the digests recorded in `config/CONFIG.json`. They hold one row per task, with no
duplicates and no interrupted-child rows. On all 464 tasks the failure-kept rows have the same fit, the same
predictions and the same program text as study B's rows, as RESULTS.json states (464 of 464).

### 4. RESULT.md: numbers correct; six wording notes

**Numbers.** Every number in RESULT.md's header, table, primary, secondaries, descriptive results, entry usage and
fidelity paragraph matches RESULTS.json and the per-task table. In particular:
- the 22 tasks where only compression is right are all in the 1D-ARC flip family;
- failure-kept has no correct output in that family;
- both random libraries score exactly as G0 on every task.

**Claim limits.** The header carries the frozen limits:
- the held halves are previously used;
- the design was not blind to study B;
- construction work is not matched;
- the compression is a single step;
- no credit goes to "kept from failures" as such;
- it is not a head-to-head of library-learning methods in general.

"Held" is used for the held-out halves, with their prior use stated, never as "unopened".

**Notes (recommended edits; none changes a number or a decision):**

1. **"The base search solves few source tasks"** (Lesson) is inaccurate for 1D-ARC and ConceptARC. In study B's
   discovery records, all 23 solved 1D-ARC source tasks were found at four times the base budget, none at the base
   budget. Of ConceptARC's 5, 1 was found at the base budget and 4 at four times it; Mini-ARC's 6 were all at the
   base budget. Suggested wording: "the base search, given up to four times its budget, solves few source tasks".
2. **The 219 and 218 in the 1D-ARC paragraph are totals over all benchmarks.** "Programs using a failure-kept
   operation were found on 219 held tasks, and the library made 218 held tasks correct that G0 alone does not solve"
   sits in a paragraph about the 19 operations for 1D-ARC. For 1D-ARC alone the counts are 217 and 216; ConceptARC
   adds 2 and 2. State the scope.
3. **The ConceptARC secondary quotes "p 0.5" under "Holm over five".** That is the raw p; the Holm p, at which the
   decision is made, is 1.0. Quote both.
4. **The Lesson's headline reads as a cause.** "A library compressed from successes has little to work with, while
   failures still supply specifications" invites a causal reading. The frozen claim limit says the design cannot
   separate the source material from the operation space (object-level edits against arc-dsl fragments), so the gap
   may come from either. One clause would keep the lesson inside the limit: "this design cannot tell how much of the
   gap comes from the failure material and how much from the object-level operation space".
5. **Completeness of the "never fired" sentence.** It accounts for 18 of the 19 1D-ARC compression entries. The
   zero-utility entry `vconcat(I, hmirror(I))` also never fired.
6. **Optional precision.** "Both random libraries equal G0 on every task" is true of the scores. On one ConceptARC
   task (co0040), the second attempt of the seed-2 random arm differs from G0's; the first program and the score are
   the same.

## Files

- This audit: `reviews/INDEPENDENT_POST_SCORE_AUDIT.md` (first committed in 3a361e98; the two sections below were added
  afterwards).
- Nothing else in the repository was written.

## Sentences the papers may use (exact)

Each sentence below has been checked against RESULTS.json, the per-task table, the rows and the frozen protocol.
Quote them as written; shorten only by dropping a whole clause in parentheses.

1. On 464 held tasks (624 test outputs) from ConceptARC, Mini-ARC and 1D-ARC, held out from the libraries'
   construction but scored in earlier studies, we added three kinds of library of the same size per benchmark (2, 0
   and 19 entries) to the same base program search: operations kept from failures on the source halves, a
   single-step compression of solved programs, and random whole-grid operations (drawn twice). Each entry entered as
   one operation of equal cost, under the same budget of 150,000 primitive executions and two attempts.
2. The failure-kept library produced 227 correct outputs against 28 for the compression library. 218 tasks were right
   only under failure-kept and 22 only under compression (exact McNemar p < 0.000001; family-clustered 95% interval
   for the difference of 199 outputs: 89 to 294).
3. Both random libraries scored 6, the same as the base search alone on every task, and none of their entries
   appeared in any program the search found.
4. By benchmark, failure-kept scored 9 of 240 outputs on ConceptARC, 2 of 75 on Mini-ARC and 216 of 309 on 1D-ARC,
   against 4, 2 and 22 for compression and 4, 2 and 0 for the base search alone.
5. Failure-kept led compression by 194 outputs on 1D-ARC (interval 83 to 289), and the ConceptARC difference of 5
   outputs was inconclusive (Holm-adjusted p 1.0). Mini-ARC, where no library has entries, is a tie by construction.
6. Compression's only gain over the base search was 22 tasks of the 1D-ARC flip family, where the failure-kept library
   got nothing right, so in this setting the two libraries are complementary.
7. Read descriptively, this is a low-success regime. The source halves offered few solved programs to compress (on
   1D-ARC, 23 of 306 tasks, only 2 distinct programs, all found with four times the base budget), while on the same
   1D-ARC source half the failures still supplied specifications from which the builder admitted 19 operations, 12
   of which fired on held tasks.
8. These results have firm limits:
   - the failure-kept arm repeats an earlier study's object-reuse arm, whose predictions it matches on all 464 tasks;
   - the design was written knowing that study's held results;
   - construction work was not matched (about 9,300 CPU-seconds for the 1D-ARC failure library against seconds for
     the compression);
   - the compression is a single step with no holes;
   - the failure material cannot be separated from the object-level operation space;
   - and this is not a general head-to-head of library-learning methods.
9. Short form for the Writeup (45 words): On 464 previously used held tasks, a same-size failure-kept library gave
   227 correct outputs, a single-step compression of solved programs 28 and random libraries 6, under the same
   matched search; compression's only gain was one family the failure-kept library missed. Not a general method
   comparison.

## Do not write

- "Failure-derived (or failure-kept) libraries beat compression", or "beat success-derived libraries", in general.
- "Beats DreamCoder", "beats Stitch", or any comparison with a library-learning system as such.
- Any wording that credits the gain to "kept from failures" as such, or says the failures caused the gain. The failure
  material and the object-level operation space are not separated.
- "Fresh", "unseen", "new" or "unopened" held tasks. These halves were scored before.
- "Matched construction work", "equal compute" or "equal total cost". Only size, cost and charge per entry, type, and
  search budget were matched.
- "Blind", "confirmatory" or "independent replication". The design knew the earlier held results, and the
  failure-kept arm repeats a known arm.
- "Significant on ConceptARC" (it is inconclusive), or "Mini-ARC shows the libraries are equal" (it is a tie by
  construction, because no library has entries there).
- "The base search solved 23 1D-ARC source tasks". They were found with four times the base budget.
- "Compression never helps" or "random libraries hurt". Compression gained the flip family, and the random libraries
  matched the base search.
- "p = 0". Write p < 0.000001.
