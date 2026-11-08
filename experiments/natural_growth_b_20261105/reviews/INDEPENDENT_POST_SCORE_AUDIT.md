# Independent post-score audit of study B (library transfer and object-level growth), local run of 7 to 8 Nov 2026

Audit by the study B session in the main repository, requested by the coordinator on 8 Nov 2026 after the companion's
local takeover finished (its outbox note 0556). Object audited: the takeover's control folder
`<companion study folder>/natural_growth_b_local_takeover_20261107_v1/` and its runtime
`<companion runtime folder>/experiments/natural_growth_b_20261105/` (stage records, output
manifests, markers, report outputs), with the final aggregate
`FINAL_AGGREGATE_SNAPSHOT.json` (final aggregate `bfccc68321a5bbd25ab8ac3d8b121ab973fb23c4e11d9179bca7465aac14a958`,
report `21070825d5b2738a04e8673cb776fb60b7d4352429741d0d4595d713313f203d`, prediction seal
`c06b0a4876293bba1fb1a4b14fb7817d995c32f6c7288291f13d12474669f610`). Read only. No held task was run or scored, no
solution file was opened, read or hashed, and no prediction row was parsed (prediction files were hashed only, for
the manifest and seal checks). Both scripts ran on a scratch copy, in one CPU slot at nice 19. The custody check
reads the runtime and the takeover folder and writes only to scratch. The recomputation reads only the scratch copy
of the aggregate.

**Verdict: PASS.** Custody holds on every point checked (section 1). The primary, the thirteen secondaries, Holm's
adjustment and every decision are reproduced from the sealed aggregate (section 2). The clustered intervals that the
aggregate determines are reproduced exactly, and the primary's interval is reproduced up to one position that the
aggregate does not record and that cannot change the decision. No discrepancy in custody or statistics. Two things
must go into the paper with the result. First, the execution deviated from PROTOCOL.md in who wrote the GO and where
the run took place; the takeover's addendum discloses both (section 1.7). Second, the 2 Nov exposure of every
benchmark task is not stated in the takeover's documents and must be (section 4).

Names used below. Arms: 1, G0 (the full arc-dsl grammar alone); 2, G0 plus the promoted library; 3, a shuffled
library; 4a, 4b and 4c, matched static search with the library's, the object step's and construction's CPU allowance;
5, object-level reuse (the builder's frozen operations); 6, reuse with a shuffled registry; 7, task-local object
construction; 8, construction with demonstrations from another family. The primary compares arm 5 with arm 4b. The
secondaries S0 to S10 are the protocol's fixed list of thirteen, named in words in section 2.

## 1. Custody

Script: `custody.py` in the audit's scratch folder (33 checks, all pass).

1. **The frozen science.** The runtime's `FREEZE.json` is candidate freeze 2,
   `9d9d2248c511ee8b729694e9c25231bdbfe26e0c10d3037f774d745ca83cfa21`, the freeze under which Kaggle rehearsal 2 ran
   (`checks/kaggle_rehearsal/REHEARSAL_2.md`). The main tree's `FREEZE.json` is the same file. All 135 frozen
   scientific files in the runtime have their frozen digests: 110 study, reused and record files plus 25
   object-growth files of the builder's slot. Protocol and amendments are pinned. The takeover restored two files
   from Git commit 5978a879: `ngb/power_object.py` and `power/POWER_OBJECT.json`. These are exactly the two frozen
   files that now differ in the main tree, and both are Athe-only records that no phase reads. This session changed
   them on 6 Nov at 13:00 and 13:14 UTC, after rehearsal 2's report and before the held run, to add an unfrozen
   expectation (section 3). They are uncommitted in the main tree.
2. **GO and authorisation chain.** The GO is `9ca6e0a8db48c9add42c51d7802cb12f9c472ac5d6bb40ce14204edbe491008e`.
   Its first three lines are the protocol `7602387708c3ac3487fa96fde50c25c6b6f1d60fbc193cefc0fe2b9acda1e1ac`, freeze
   `9d9d2248...` and `primary arm5_vs_arm4`. Its fourth line names the local execution freeze
   `085ca9d7449cf6fee349bc8f66e212933fe799176d74aaa3082bd9ce46bea588`; the gate reads only the first three. The same
   GO digest is named by the one-use authorisation, by the run claim, by all three stage records and by the aggregate.
   The authorisation binds the local freeze and the input pins and allows one attempt. The run claim binds the
   authorisation's digest. The five files that the local freeze pins are unchanged.
   The order is: local freeze 7 Nov 16:51:08Z; authorisation 16:58:37Z, with the GO file written in the same second;
   run claim 16:59:39.47Z; launch A 16:59:39.64Z; launch B 19:17:44Z; launch C 22:12:38Z; pre-score validation
   8 Nov 01:42:15Z; seal 01:42:17.975Z; report 01:42:18.393Z.
3. **The three phases.** Every stage of A (ConceptARC and Mini-ARC), B (1D-ARC) and C (the ARC-AGI-2 check) ran once,
   with return code 0, under this GO and primary, with 2, 2 and 1 workers. That makes 16, 9 and 7 stages, every one
   on a single attempt. The speed factors were measured by the frozen benchmark at the stage concurrency (two copies,
   two copies, one copy): 0.863, 0.884 and 0.84, none clipped. Each output manifest verifies, with every digest
   matching and no unlisted file (37, 21 and 61 files). The seal binds each manifest and each stage record. Kernel
   C's 48 copied held-row files equal A's and B's originals byte for byte and are exactly C's held tree.
4. **Seal before scoring; no partial correctness read.** The pre-score validation called only the frozen report's
   verification helpers (`verify_run`, `copies_match`, `collect`), not the scorer, and opened no solution. It passed
   with no problem, and the seal binds its digest. The prediction seal (01:42:17.975Z) precedes the first presence
   of the ARC-AGI-2 solution file in the runtime: that file's modification time is 01:42:18.051Z, and the takeover's runner refuses to copy
   it if it already exists. It also precedes the exclusive claim `SCORING_<GO>` (01:42:18.718Z). No
   phase's code calls the scorer; the ARC-AGI-2 loader reads the challenge file only.
5. **One scoring.** The runtime holds exactly one claim and one completion marker, both named by the GO digest, and
   no other marker anywhere. The report was launched once and returned 0 in 12 s. A and B hold no results file. The
   aggregate is byte for byte the report's `RESULTS.json`, and the report digest is `REPORT.md`'s. The completion
   marker's digest is the one the takeover recorded. The main study tree still has no GO, no run folder and no
   marker (its `runs/` holds only `kaggle/`).
6. **Retries only as declared.** No static child was killed, so no retry row exists. There is no `.retry.jsonl` file;
   the retry stages ran with nothing to do, as declared. The launch records show one launch per phase, one
   pre-score validation and one report. There was no wrapper retry.
7. **Deviations from the protocol's execution plan, disclosed by the takeover's addendum.** None changes the science.
   - The GO was written by the takeover under the author's one-use root authorisation while the coordinator was
     unavailable. PROTOCOL.md section 9 says "written once by the coordinator". The coordinator has since accepted
     the run (this audit's request).
   - The run was local, on Athe CPUs 22 and 23 at nice 19, not on private Kaggle kernels (PROTOCOL.md section 12,
     amendment 3). Allowances were computed by the frozen driver from its own speed factor, at the concurrency
     amendment 3 requires (two workers in A and B, one in C).
   - The frozen amendment 3 inside candidate freeze 2 still has its two result placeholders (rehearsal 2's result
     and the checks), and it lacks the custody section that the coordinator requested on 6 Nov. The final
     version-4 freeze that would have filled them was never written: this session paused before it. The takeover's
     addendum records rehearsal 2's provenance externally.
   - Costs: outer CPU, including all descendants, was 48,986 s; supervisor CPU 67 s; wall 31,371 s (8.7 h). The
     nested stage CPU was A 15,861 s, B 20,499 s and C 12,551 s. The outer and nested figures overlap and must not be
     added. The Athe-measured source-half costs stay separate in the frozen records.

## 2. Recomputation from the sealed aggregate

Script: `recompute.py` in the same scratch folder, my own implementation of the pre-registered statistics:
- an exact two-sided sign test on tasks with a non-zero difference;
- Holm's step-down over the fixed thirteen;
- the decision rule: "A beats B" needs adjusted p below 0.05 and the interval above 0;
- the family-clustered percentile bootstrap. Its strata are the benchmarks; its clusters are families, with each
  Mini-ARC task its own cluster; it uses random.Random(20261105) and 10,000 draws.

The aggregate holds per-family rows for four comparisons (library against G0, reuse against G0, reuse against arm 4b,
construction against G0). For every comparison it holds the counts. It holds no per-task rows.

- **p-values:** all fourteen (the primary and thirteen secondaries) reproduce from the stored counts of tasks on
  which each arm alone did better.
- **Holm:** all thirteen adjusted values reproduce exactly when Holm is applied, as the frozen report applies it, to
  the six-decimal p-values. On unrounded p-values, two differ in the sixth decimal: S1 0.018038 against 0.018039, and
  S4 0.231445 against 0.231444. No decision moves.
- **Decisions:** all fourteen reproduce from the counts, the adjusted p-values and the stored intervals. Every stored
  total difference equals the difference of the stored correct counts. The three benchmarks' primary differences
  sum to the primary's 109.
- **Intervals reproduced exactly:**
  - S0, library against G0: [2, 79].
  - S5 per benchmark: ConceptARC [0, 12], Mini-ARC [0, 0], 1D-ARC [0, 73].
- **Primary interval.** On Mini-ARC, only arm 4b is correct on one task, but the aggregate does not record which
  task. Its place among the 75 sorted Mini-ARC clusters is therefore unknown, so every place was computed. The
  interval is [6, 204], [6, 205], [7, 204] or [7, 205]. The stored [7, 204] arises at 29 of the 75 places. The lower
  end is at least 6 at every place, so the decision does not depend on it.
- **Not recomputable from the aggregate:** the intervals of S1, S2, S3, S4 and S6 to S10, which have no per-family
  rows. Recomputing them would need the per-task table, that is a re-scoring, which this audit does not do. Their
  p-values, adjusted p-values and decisions are reproduced.

| comparison | correct (A against B) | difference | clustered 95% interval | raw p | Holm p | decision |
|---|---|---|---|---|---|---|
| primary: reuse (5) against matched static, object allowance (4b) | 227 against 118 | +109 | [7, 204] | below 0.000001 | (not in the family) | reuse beats matched static |
| S0: library (2) against G0 (1) | 37 against 6 | +31 | [2, 79] | below 0.000001 | below 0.000001 | library beats G0 |
| S1: library against matched static, library allowance (4a) | 37 against 56 | -19 | [-38, -3] | 0.002577 | 0.018039 | matched static beats library |
| S2: library against shuffled library (3) | 37 against 7 | +30 | [1, 78] | below 0.000001 | below 0.000001 | library beats shuffled |
| S3: reuse against shuffled registry (6) | 227 against 6 | +221 | [138, 300] | below 0.000001 | below 0.000001 | reuse beats shuffled |
| S4: wrong answers, library against 4a | 7 against 17 | -10 | [-20, -1] | 0.038574 | 0.231444 | inconclusive |
| S5: library against G0, ConceptARC | 8 against 4 | +4 | [0, 12] | 0.5 | 1.0 | inconclusive |
| S5: library against G0, Mini-ARC | 2 against 2 | 0 | [0, 0] | 1.0 | 1.0 | tie |
| S5: library against G0, 1D-ARC | 27 against 0 | +27 | [0, 73] | below 0.000001 | below 0.000001 | inconclusive (interval reaches 0) |
| S6: ARC-AGI-2, library against 4a | 0 against 0 | 0 | [0, 0] | 1.0 | 1.0 | tie |
| S7: ARC-AGI-2, reuse against 4b | 0 against 0 | 0 | [0, 0] | 1.0 | 1.0 | tie |
| S8: construction (7) against matched static, construction allowance (4c) | 343 against 118 | +225 | [150, 298] | below 0.000001 | below 0.000001 | construction beats matched static |
| S9: construction against donor demonstrations (8) | 343 against 10 | +333 | [276, 381] | below 0.000001 | below 0.000001 | construction beats donor control |
| S10: ARC-AGI-2, construction against 4c | 2 against 0 | +2 | [0, 6] | 1.0 | 1.0 | inconclusive |

Counts are correct outputs: held tasks 464, outputs 624; ARC-AGI-2 120 tasks, 172 outputs. In S4 the counts are
wrong answers.

## 3. Per benchmark: where the gain sits

Correct outputs per arm (the report's totals by benchmark):

| benchmark (tasks / outputs) | 1 G0 | 2 library | 3 shuffled | 4a | 5 reuse | 6 shuffled registry | 4b | 7 construction | 8 donor | 4c |
|---|---|---|---|---|---|---|---|---|---|---|
| ConceptARC (80 / 240) | 4 | 8 | 5 | 17 | 9 | 4 | 27 | 46 | 0 | 27 |
| Mini-ARC (75 / 75) | 2 | 2 | 2 | 3 | 2 | 2 | 3 | 11 | 0 | 3 |
| 1D-ARC (309 / 309) | 0 | 27 | 0 | 36 | 216 | 0 | 88 | 286 | 10 | 88 |
| all (464 / 624) | 6 | 37 | 7 | 56 | 227 | 6 | 118 | 343 | 10 | 118 |

The primary split by benchmark. This is descriptive, with no decision weight; the intervals use the same bootstrap
within the benchmark.

| benchmark | reuse against 4b | tasks only reuse / only 4b | sign-test p | clustered 95% interval |
|---|---|---|---|---|
| ConceptARC | 9 against 27, -18 | 1 / 9 | 0.021 | [-30, -6] |
| Mini-ARC | 2 against 3, -1 | 0 / 1 | 1.0 | [-3, 0] at every place of the one task |
| 1D-ARC | 216 against 88, +128 | 154 / 26 | below 0.000001 | [28, 222] |

- **The primary's +109 is a 1D-ARC result.** On ConceptARC, matched static search does better than reuse (27
  against 9 correct outputs). Reuse beats it only in TopBottom2D (+2) and loses in eight concepts by 2 to 4 outputs
  each. On Mini-ARC the reuse registry is empty, so reuse is G0, and arm 4b is one task ahead.
- **Within 1D-ARC** (reuse against 4b, held tasks):
  - Reuse gains: move_2p_dp +25, scale_dp +25, move_dp +24, hollow +23, move_3p +21, move_2p +19, mirror +5,
    padded_fill +4, recolor_cmp +3, move_1p +1.
  - Equal: fill (24 each), recolor_cnt and recolor_oe (0 each).
  - Opposite way: flip, -22 (matched static search 22, reuse 0).
- **Against G0:**
  - Reuse is correct on 218 held tasks that G0 misses, 216 of them in 1D-ARC. Matched static search with the
    object allowance is correct on 99.
  - Construction is correct on 315 that G0 misses: 1D-ARC 286, ConceptARC 20 tasks (46 outputs against 4), Mini-ARC
    9 (11 against 2). It answers 377 outputs at precision 0.91.
- **Against the expectation.** The frozen expectation (amendment 3, section C, inside candidate freeze 2) said that
  "arm 5 beats arm 4b" needs four 1D-ARC families without an out-of-sample estimate to transfer: fill, move_1p,
  move_2p_dp and move_dp, 99 held tasks. Reuse solved all 99. Matched static search also solved fill (24) and
  move_1p (24), so of those four only move_2p_dp and move_dp add to the margin, with the measured families supplying
  the rest. An expectation computed before the run but never frozen used matched static search's scores on the
  source half in Kaggle rehearsal 2 (`power/POWER_OBJECT.json` in the main tree, written 6 Nov 13:14 UTC and in Git
  since the autosave commit dcdde15b of 6 Nov 13:24 UTC, 27.6 hours before launch A). It predicted
  about 96 held tasks newly correct for arm 4b; the run gave 99. It put "arm 5 beats arm 4b" at 49% if those four
  families transferred. That record may be cited only as unfrozen and pre-outcome.
- **The ARC-AGI-2 check** (exposed set, 172 outputs): construction 2 correct (2 answered); every other arm 0.

## 4. Wording for the paper

- **"Held" means held out from this study's development**: the source half was used for every promotion, registry,
  allowance and expectation, and the held half for nothing before the run. It does not mean unopened or unseen.
  Every task of the three benchmarks, the held halves included, was run and scored once on 2 Nov 2026 by the
  project's submitted entries (the universality evaluation), and once by the companion study's R1 study, its
  evaluation of a different frozen system on these cohorts (disclosed in amendment 1).
- **The takeover's documents do not say this.** Its addendum and note 0556 say "held from this study's development
  split, not unseen", which is correct, but neither names the 2 Nov runs. The frozen report's line "Held tasks: 464"
  carries no exposure statement for the three benchmarks. The paper must carry a sentence such as: "The held halves
  were held out from this study's development only; every task in them had been run and scored once on 2 Nov 2026 by
  the project's submitted entries and once by the companion study's R1 evaluation."
- **The ARC-AGI-2 set** is the exposed public evaluation set: used in earlier development and gates, and touched,
  inputs only, by this study's 5 Nov dry-run incident (`records/INCIDENT_20261105_DRY_RUN.md`). It is not a fresh
  test, as the aggregate states.
- **Never cite rehearsal scores as held results.** The rehearsal reports' "Held tasks: 460" counts source tasks
  standing in for held ones.
- **No word "unopened" or "unseen"** in any statement about these benchmarks.

## 5. Discrepancies

None in custody or in the statistics. Minor points, none of which affects a decision:
- Holm reproduces exactly on six-decimal p-values; on unrounded p-values, two values differ in the sixth decimal.
- The primary's interval can be pinned only to four candidates from the aggregate; the stored one is among them.
- The intervals of nine secondaries are not recomputable from the aggregate.
- The protocol's documentation gaps are listed in section 1.7.
- The exposure wording gap is in section 4.
