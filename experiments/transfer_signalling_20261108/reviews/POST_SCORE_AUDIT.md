# Post-score audit: T5 signalling logic models (transfer_signalling_20261108)

- **Date:** 8 November 2026.
- **Auditor:** the pre-run reviewer. This is the reviewer of `reviews/PRE_RUN_REVIEW.md` (commit ddd52d70) and
  `reviews/DELTA_CHECK.md` (commit 154831a3), who is independent of the design.
- **Audited:**
  - GO.json (commit 6ae7f578);
  - `results_held/` (commit 7c343d56);
  - RESULT.md (commit f4a8f63d, sha256 9ee83919...);
  - `outputs/detached/t5_held_score/`.
- **Run during the audit:**
  - a recomputation of every reported statistic from `results_held/tasks.jsonl`, with the frozen `u6.stats`;
  - a re-run, in memory, of 4 already-scored items with the frozen code: primary tasks 0 and 4, secondary-2 task 0
    and secondary-1 fold 0;
  - structural checks on the learner's network after each edge removal.

  Nothing was written to the repository except this file.

## Verdict: FAIL, for RESULT.md only

- **What passes:** custody (check 1) and every number (check 2).
- **What fails:** RESULT.md (check 3) has one wrong explanation and one direction that overstates the evidence.
- **How it turns to PASS:** RESULT.md makes the three edits in check 3, word for word or with the same content. No
  rerun, no rescoring and no further audit are needed; the coordinator only confirms the edits.
- **The sentences the papers may use** are at the end of this file, and they hold in either case.

## 1. Custody: PASS

- **One GO commit.** GO.json has exactly one commit, 6ae7f578 (06:41:36Z). It adds only GO.json, and the delta check
  (154831a3) is an ancestor of it. GO.json holds:
  - freeze commit cdd06c76;
  - FREEZE.json sha256 56640e77...;
  - a 64-hex nonce;
  - the two review hashes, which match `PRE_RUN_REVIEW.md` (3f2a6d0a...) and `DELTA_CHECK.md` (81460c1d...).
- **The salt.** The sha256 of the committed GO.json is ef7c8b8e641d14b36c48b37bf907933f1c835e45de846b0dcab063cb6b3055e3,
  the same at the GO commit, at HEAD and in the working copy. It equals:
  - the `--salt` in `cmd.txt`;
  - `salt` and `provenance.salt` in RESULT.json and P1_RESULT.json;
  - every held label in `tasks.jsonl`.
- **Frozen files at run time.** The script records git HEAD at its start as 413a6e52. That commit descends from the
  GO commit, and at it:
  - all 25 frozen files match FREEZE.json;
  - FREEZE.json is 56640e77... and GO.json is ef7c8b8e...;
  - the last commit that changed FREEZE.json is cdd06c76.

  No commit between GO and the results touches a frozen path. The frozen files still match today.
- **A single run.**
  - `run.status` reads START 06:41:36Z, then EXIT 0 at 06:51:16Z. `stderr.log` is empty.
  - `results_held/status.txt` has one RUNNING line at 06:45:17Z, after the wait for a CPU slot. It then reads
    P1_DONE, S1_DONE, S2_DONE and DONE, with 358.4 CPU-seconds of the 1,800 cap and no secondary failure.
  - No scored launch could pass the GO check before the GO commit at 06:41:36Z, and the refusal on an existing
    `results_held/` blocks any relaunch after it.
  - `tasks.jsonl` holds 305 unique records: 200 primary, 5 secondary 1 and 100 secondary 2. The primary indices run
    0 to 199 and the secondary-2 indices 0 to 99, with no skipped seed.
  - The committed results equal the working copies.
- **Nothing held before GO.**
  - Every held label contains the salt, which depends on a nonce first committed at 06:41:36Z.
  - At the delta check (about 06:40Z), neither `results_held/` nor `outputs/detached/t5_held_score/` existed.
  - The launcher files are dated 06:41Z.

## 2. Recomputation from the result files: PASS

Every value below was recomputed from `tasks.jsonl`. It equals RESULT.json, P1_RESULT.json, stdout.log and RESULT.md,
including:
- the bootstrap intervals (10,000 resamples, default_rng(0));
- the held conditions per task, which are the 5 or 2 smallest sha256("label|condition key");
- the secondary-1 folds, dealt by sha256("salt|LiverDREAM|key");
- the per-edge table;
- the analysis without mek12 to erk12.

The 4 items re-run with the frozen code reproduce their logged held outcomes and final programs exactly.

**Primary: 200 tasks, 1,000 held conditions.**

| Arm | Exact held conditions |
|---|---|
| Grown | 863 |
| Static | 731 |
| Shuffled | 805 |
| CellNOpt-style comparator | 728 |

| Comparison | Tasks won, lost, tied | Sign test p | Holm-adjusted p | Held conditions won and lost, McNemar p | Difference, 95% interval |
|---|---|---|---|---|---|
| H1, grown against shuffled | 50, 11, 139 | 4.6e-7 | 4.6e-7 | 84 and 26, 2.6e-8 | +0.058 [+0.037, +0.079] |
| H2, grown against static | 62, 12, 126 | 2.9e-9 | 5.7e-9 | 158 and 26, 2.9e-24 | +0.132 [+0.095, +0.171] |

- Both hypotheses are supported under the frozen rule: Holm-adjusted p at most 0.05, and more tasks won than lost.
- The comparator against static won 12 tasks and lost 21 (p = 0.16).

**Per removed edge.** Exact held conditions per arm, net gain of grown, and whether the edge was rebuilt:

| Removed edge | Tasks | Static | Grown | Shuffled | Net grown over static, over shuffled | Exact edge rebuilt and kept |
|---|---|---|---|---|---|---|
| mek12 to erk12 | 58 | 128 | 246 | 202 | +118, +44 | 51 of 58 |
| mkk4 to p38 | 44 | 192 | 199 | 192 | +7, +7 | 0 |
| mkk4 to jnk12 | 30 | 131 | 131 | 131 | 0, 0 | 0 |
| map3k1 to mkk4 | 26 | 100 | 105 | 100 | +5, +5 | 0 |
| map3k1 to ikk | 25 | 102 | 105 | 102 | +3, +3 | 0 |
| map3k7 to mkk4 | 17 | 78 | 77 | 78 | -1, -1 | 0 |

So mek12 to erk12 carries 118 of the 132 net held conditions over static, and 44 of the 58 over shuffled.

**Without mek12 to erk12: 142 tasks, 710 held conditions.**
- Exact held conditions: static 603, grown 617, shuffled 603, comparator 601.
- Grown against shuffled: tasks 16, 8, 118 (p = 0.15); held conditions 30 and 16 (McNemar p = 0.054); difference
  +0.020 [+0.003, +0.038].
- Grown against static: tasks 17, 9, 116 (p = 0.17); held conditions 31 and 17 (McNemar p = 0.060); difference
  +0.020 [+0.001, +0.039].

**Secondary 1, the 25 real DREAM conditions.**
- Every arm scored 14 of 25.
- Grown against static won 1 condition (TNFa with the p38 inhibitor) and lost 1 (TNFa with the IKK inhibitor):
  McNemar p = 1.0.
- The grown arm kept pieces in its main growth in all 5 folds and passed acceptance in 4. The shuffled arm kept no
  piece in any fold.
- The training-error table in RESULT.md and its list of kept pieces are correct.

**Secondary 2, the toy family: 100 tasks, 200 held conditions.**
- Exact held conditions: static 104, grown 118, shuffled 121, comparator 104.
- Grown against shuffled: 11 tasks won, 13 lost (p = 0.84).
- Grown against static: 22 won, 9 lost (p = 0.029, no gate).
- Shuffled against static: 18 won, 5 lost (p = 0.011).

## 3. RESULT.md within the frozen scope: FAIL as written

**What is right.**
- The scope box quotes the frozen scope: "reconstruction of one removed prior edge (one of 6)".
- Every number matches the recomputation.
- The labels for the secondaries and the comparator are as frozen.
- The concentration in mek12 to erk12 is stated in sections 1a and 1b and in the first result bullet, together with
  the non-significant analysis without that edge.

**Finding 1: the explanation in the lesson is wrong for two edges.**
- **What RESULT.md says** (section 1, "Lesson"): the loop rebuilds a missing edge well "when that edge leads straight
  into a readout". It then groups mkk4 to p38 and mkk4 to jnk12 with the edges that feed "an intermediate node".
- **What the data show:**
  - Three of the 6 edges lead straight into a readout: mek12 to erk12, mkk4 to p38 and mkk4 to jnk12. Only the first
    shows a large gain. The other two show +7 and 0.
  - The reason is structural. After mkk4 to p38 or mkk4 to jnk12 is removed, preprocessing compresses mkk4 out of the
    learner's network, so neither edge can be rebuilt exactly.
  - Mek12 is a designated node (a readout and an inhibitor target), so preprocessing always keeps it.
  - The grown arm rebuilt mek12 to erk12 exactly and kept it in 51 of 58 tasks. It rebuilt no other removed edge.

**Finding 2: direction 3 overstates.**
- **What RESULT.md says:** "the primary supports transfer for reconstructing an edge into a readout".
- **Why that is too broad:** two of the three edges into a readout show little or no gain, so the evidence does not
  support that class of edges.

**Required edits to RESULT.md.**

1. **Replace the "Lesson" bullet in section 1 with:**

   "**Lesson.** The loop's pieces go only into failing readouts, from nodes in the learner's network. Of the 6
   removable edges, only mek12 → erk12 can be rebuilt exactly that way. Erk12 is a readout, and mek12 is a designated
   node (a readout and an inhibitor target), which preprocessing keeps. The grown arm rebuilt it and kept it in 51 of
   58 tasks. For mkk4 → p38 and mkk4 → jnk12, the target is a readout, but removing the edge lets preprocessing
   compress mkk4 out of the learner's network, so the edge cannot be rebuilt exactly. Their gains were +7 of 220 and
   0 of 150 held conditions. The other 3 edges feed intermediate nodes (map3k1 → mkk4, map3k1 → ikk, map3k7 → mkk4),
   with gains of +5, +3 and -1. This reading is descriptive; we did not test it separately."
2. **Replace direction 3 with:**

   "3. Until then, the primary supports transfer for reconstructing a removed prior edge that the pieces can rebuild
   exactly, which here is one of the 6 removable edges (mek12 → erk12). It does not show transfer for edges in
   general."
3. **Add after "Both hold, so within the scope above, the loop transfers and the content of the failure matters.":**

   "Most of this gain comes from the 58 tasks that removed mek12 → erk12. Without them, the gain is 2.0 points over
   both static and shuffled, and it is not significant (sign tests p = 0.15 and 0.17)."

## Sentences the papers may use

Use these as written. A shorter text may drop whole sentences, but never the scope, concentration or control
sentences when it keeps a result sentence.

1. "We tested whether the loop transfers, through an adapter, to signalling logic models. The test used 200 held
   synthetic tasks on the real DREAM hepatocyte prior network and experimental design. In each task, one prior edge
   used by a random true program was removed from the learner's network (one of 6 removable edges)."
2. "On these tasks, the grown program predicted 863 of 1,000 held perturbation conditions exactly. The other arms
   predicted 731 (the static prior-network program), 805 (the same loop fed a shuffled failure description) and 728
   (a CellNOpt-style comparator)."
3. "Both pre-registered hypotheses were supported. The grown program beat the shuffled-failure control in 50 tasks
   and lost 11 (Holm-adjusted sign test p = 4.6 × 10⁻⁷). It beat the static program in 62 tasks and lost 12
   (p = 5.7 × 10⁻⁹)."
4. "Most of the gain came from one of the 6 edges, mek12 to erk12, which the loop rebuilt exactly in 51 of its 58
   tasks. That edge accounted for 118 of the 132 net held conditions gained over the static program and 44 of the
   58 gained over the shuffled control."
5. "In the other 142 tasks, the grown program led both controls by 2.0 percentage points (617 against 603 of 710
   held conditions), which was not significant (sign tests p = 0.15 and 0.17)."
6. "The result is limited to reconstructing one removed prior edge on this network and design. Three conditions
   apply:
   - by construction, the static program cannot represent the truth;
   - the primary replicates a development finding on new draws;
   - the shuffled control moves the failing conditions across time points while keeping the readout and direction,
     which makes it weaker than a shuffle within each time point."
7. "On the 25 real DREAM conditions, every arm predicted 14 exactly (grown against static: 1 condition won, 1 lost;
   McNemar p = 1.0). Growth lowered training errors in 4 of 5 folds but did not change held recovery. These data
   were seen once during development and give low power."
8. "On 100 held synthetic tasks on the 12-node CellNOpt toy network, the shuffled control matched the grown program
   (121 against 118 of 200 held conditions; the shuffled control won 13 tasks and lost 11, p = 0.84), as
   development had predicted."
9. "A Python re-implementation of CellNOpt's objective and genetic algorithm, not checked against R, matched the
   static program (728 against 731 of 1,000). This is consistent with the gain coming from growing the model space
   rather than from a stronger search of the prior space."
10. "The test was frozen and reviewed before any held task existed. The held tasks were drawn from a salt fixed by a
    GO file committed after the review. The single scored run was audited independently."

**Not allowed:**
- "the loop transfers to signalling biology" without sentence 6;
- "the failure's content matters" without sentences 4 and 6;
- any claim that the loop reconstructs edges into readouts, or missing edges, in general;
- any claim of discovery from the real DREAM conditions;
- "beats CellNOpt" (the comparator is a Python re-implementation, not CellNOpt in R);
- describing the 200 tasks as 200 independent structural problems (they cover 6 removable edges).
