# Post-score audit: logic recovery transfer study (transfer_logic_20261108)

- **Auditor.** The independent reviewer who wrote `reviews/PRE_RUN_REVIEW.md` (commit 99ec4245) and `reviews/DELTA_CHECK.md` (commit 13e1b506). The auditor is not the study's designer.
- **Audited.**
  - the GO commit `bca541e7`;
  - the results commit `7f7377f5` (`results/held.jsonl`, `results/summary.json` and `results/run.status`);
  - the RESULT.md commit `461b4aba`, which also adds `report_tables.py` and a PROGRESS.md entry;
  - the launcher record in `outputs/detached/transfer_logic_held/`.
- **Date.** 8 November 2026.

## Verdict: PASS

The held result is genuine and correctly analysed.

**Custody is intact.**
- One GO, committed once, right after the delta check.
- One run, which recorded the salt and the freeze commit.
- No change to any hashed file.
- No results before GO.

**The numbers are exact.**
- All 771 rows reproduce identically from the frozen code and the GO salt.
- Every number in `summary.json` and RESULT.md recomputes exactly, both through the frozen statistics module and through an independent implementation.

**The headline claims are in scope.** Four sentences in RESULT.md's lesson and direction lines overreach. They change no number, but they must be corrected before RESULT.md is quoted (section 3). Papers should use only the sentences in section 4.

## Method

**What ran.** Everything ran in a scratch folder outside the repository, with `python -I -B` and a scratch bytecode cache:
- Committed files were read with `git show` at the audited commits.
- The held set was regenerated from the salt with the frozen code.
- The statistics were recomputed twice: through the frozen module, and through an independent implementation of the exact McNemar test, Holm's procedure and the file-clustered bootstrap.
- All 771 rows were reproduced in memory with the frozen code, in 69.4 CPU-seconds at nice 19. This is an audit reproduction: it wrote nothing, and it produces no new result.

**What did not happen.** Nothing was written in the repository except this file.

## 1. Custody: PASS

**GO.**
- Exactly one commit, on any branch, touches GO: `bca541e7`, at 06:43:28Z. Its parent is the delta check, `13e1b506`, at 06:42:44Z, and it changes only GO.
- GO is byte-identical in that commit, at HEAD and in the working tree, with sha256 `41ee77539198dbcc253d486bb4a7078b25a7b9ffde054cc845d05bf4df99ea10`.
- GO has the accepted format: seven fields in order, LF endings, no byte-order mark, a 64-character lowercase nonce, and `pre_run_review: 13e1b506...`.

**Salt and freeze commit.**
- `summary.json` records salt `41ee7753...`, which is the sha256 of the committed GO bytes. It also records freeze commit `73e11d26` and the salt rule "sha256 of the committed GO file".
- `results/run.status` records the same salt and freeze commit on its DONE line.

**Frozen hashes at run time.**
- The run's own checks refuse to start on any hash, GO or version mismatch. It wrote 771 rows and a DONE status, so those checks passed when it started.
- No commit after `73e11d26` touches any hashed file.
- All 19 hashes match today, and FREEZE.json is still `853a603e...`.

**The held set is the right one.** Regenerated from the salt with the frozen code, it equals the row ids exactly:
- 217 circuit items at each of 12.5%, 25% and 50%;
- 120 policy items at 25%.

The 217 circuits come from the 35 held-candidate files and include no development file.

**A single run.**
- `outputs/detached/transfer_logic_held/run.status` reads `START 2026-11-08T06:43:28Z 3283061`, then `EXIT 0 2026-11-08T06:51:51Z`.
- `stdout.log` and `stderr.log` are empty.
- `cmd.txt` is the amended command, and `cwd.txt` is the study folder.
- No other detached run for this study exists.
- `results/` was committed once (`7f7377f5`), and the committed files equal the working tree.
- There is no `results_attempt1/`.

**No results before GO.**
- No commit touches `results/` before `7f7377f5`.
- All three results files were written at 06:51:51Z.
- The run refuses unless GO is committed at HEAD, so GO was committed before the run's checks ran, even though both are timed 06:43:28Z.

**CPU and status.**
- The run used 60.4 CPU-seconds, against a cap of 1,800.
- No fit was exhausted.
- The largest row took 2.1 CPU-seconds.

## 2. Recomputation from the 771 rows: PASS

The rows are 651 circuit rows (217 items at three fractions) and 120 policy rows. Every row is labelled `held`: circuit rows `real`, policy rows `synthetic from real seeds`.

**Primary: held real circuits at 25% probes, 217 items in 35 files.**

| Comparison | Exact recoveries | Only first : only second | Exact McNemar p | Holm p | Difference | 95% interval, clustered by file | Supported |
|---|---|---|---|---|---|---|---|
| grown against static | 45 against 7 | 38 : 0 | 7.28e-12 | 1.46e-11 | +0.1751 | [+0.0913, +0.2694] | yes |
| grown against shuffled | 45 against 12 | 34 : 1 | 2.10e-9 | 2.10e-9 | +0.1521 | [+0.0751, +0.2406] | yes |

**Secondaries: one Holm family of 8, and all 8 reject at 0.05.** Every value matches `summary.json` exactly.

| Comparison | Exact recoveries | Only first : only second | Holm p | 95% interval, clustered |
|---|---|---|---|---|
| circuits 12.5%: grown against static | 29 against 6 | 23 : 0 | 1.43e-6 | [+0.0418, +0.1830] |
| circuits 12.5%: grown against shuffled | 29 against 9 | 21 : 1 | 5.48e-5 | [+0.0314, +0.1650] |
| circuits 50%: grown against static | 67 against 7 | 60 : 0 | 1.39e-17 | [+0.1626, +0.4000] |
| circuits 50%: grown against shuffled | 67 against 15 | 53 : 1 | 4.27e-14 | [+0.1333, +0.3553] |
| circuits 25%: active against random probing (grown arm) | 63 against 45 | 19 : 1 | 9.16e-5 | [+0.0345, +0.1391] |
| policies 25%: grown against static | 44 against 27 | 17 : 0 | 6.10e-5 | [+0.0750, +0.2167] |
| policies 25%: grown against shuffled | 44 against 28 | 16 : 0 | 9.16e-5 | [+0.0750, +0.2000] |
| policies 25%: active against random probing | 56 against 44 | 14 : 2 | 0.00418 | [+0.0500, +0.1583] |

RESULT.md rounds all of these correctly.

**File and seed spread.**
- Grown beats static in 15 of the 35 held files.
- Grown beats shuffled in **13 of 35 files**, and shuffled beats grown in none.
  - 14 files hold at least one item recovered by grown and not by shuffled.
  - In one of them, newcpla1, the single item recovered only by shuffled (`newcpla1/9`) ties the file at 1 against 1.
- On policies, grown beats shuffled on 9 of the 12 seeds and loses on none.
- The largest files by grown recoveries are sex (7 of 8), newapla1 (6 of 7), newapla (5 of 8), b11 (4 of 8) and t3 (4 of 8). This is as stated.

**References, descriptive.**

| Domain, at 25% | Arm | Exact recoveries | Against grown (only grown : only reference) |
|---|---|---|---|
| Circuits | CART | 39 of 217 | 7 : 1 |
| Circuits | Espresso-style minimiser | 38 of 217 | 8 : 1 |
| Policies | full decision-list learner | 49 of 120 | 3 : 8 |
| Policies | CART | 37 of 120 | |

**Negatives.**
- 16 of the 35 files, holding 81 of the 217 items, have no recovery by any of the six methods. The file list in RESULT.md is right.
- Counted by item, **153 of 217 held circuits are recovered by no method**, and 64 by at least one. This supports RESULT.md's heading "Most held circuits are not recovered by any arm", which currently gives no item count.
- The verify flag passed 54 grown circuit programs, of which 33 are exact, and 42 grown policy programs, of which 31 are exact.
  - For static and shuffled, the counts are 21 and 6 on circuits.
  - On policies, they are 30 and 22 for static, and 31 and 22 for shuffled.

**Other numbers, all correct.**
- Static recovered 7 circuits and 27 policies, and grown recovered every one of them.
- Family counts for grown: newapla 11 of 15, m 1 of 16, max 0 of 13 and br 0 of 8.
- Median held-input errors are correct as stated, with one exception, which is note 3.

## 3. RESULT.md stays in scope: PASS, with four required wording corrections

**In scope:**
- **Labels.** The labels block says held, real (circuits), synthetic from real seeds (policies) and reconstruction, not discovery.
- **Primary.** It is headed as real circuits, exact recovery, 25% probes, with denominators throughout.
- **References.** They are reported under "descriptive, not gates", and the report says their p-values are not used.
- **Caveats.** All four section 9 caveats are stated and checked on held items.
- **Negatives.** They are written as result, lesson and direction.
- **The two notes from the delta check.** The stale FREEZE.json note is disclosed, and `report_tables.py` is declared descriptive and post-run.

**Required corrections.** Each of these four lesson or direction lines claims more than the data shows. None changes a number.

1. **Primary, "Direction".**
   - Current: "this is the first new domain where the loop and its description transfer on held real data".
   - Problem: "first" cannot be checked from this study.
   - Replace with: "in this domain, the loop and its failure description transferred on held real data." Use "first" only if the program's shared registry confirms it.
2. **Caveat 1, "Lesson".**
   - Current: "the loop is at least level with the classical learners".
   - Problem: on policies the unrestricted decision-list learner recovered more (49 against 44 of 120), and the references were never tested.
   - Replace with: "on held circuits the loop recovered more functions than either reference (45 against 39 and 38 of 217), but this comparison is descriptive and untested; on held policies the unrestricted decision-list learner recovered more than the loop (49 against 44 of 120)."
3. **Active probing, "Lesson".**
   - Current: "separating the surviving candidates is worth more than more random probes".
   - Problem: only the same budget was tested, and random probes at 50% recovered 67, more than active probing's 63 at 25%.
   - Replace with: "at the same budget, probing where the surviving candidates disagree is worth more than probing at random."
4. **Negatives, "Lesson".**
   - Current: "a dense function cannot be pinned down from a quarter of its rows by any of these learners".
   - Problem: "dense" is undefined, and "cannot" generalises beyond the data.
   - Replace with: "none of the six methods recovered any function in these 16 files from a quarter of its rows; whether that reflects the functions' complexity was not measured."

## Non-blocking notes

1. **The CPU slot isn't recorded.** RESULT.md says the run used a CPU slot. The launcher record cannot show it, because `run_detached.sh` writes the command after removing `--slot`. The wall time, 8 min 23 s for 60.4 CPU-seconds, and PROGRESS.md are consistent with a slot wait. This has no effect on results: the learners are deterministic, and the cap is in CPU time.
2. **Only the last status survives.** `results/run.status` keeps only the last status (DONE), so the STARTED line was overwritten by design. The launcher's START and EXIT lines are the start record.
3. **Small wording points in RESULT.md:**
   - the policy CART median held-input error is 14.5 (RESULT.md gives 15, the upper middle value);
   - "ROM-like" should be defined as read-only-memory tables;
   - "the description's value grows with the evidence" is a trend over three fractions (gaps 0.092, 0.152 and 0.240) that was not tested;
   - the negatives could add "153 of 217 held circuits were recovered by no method".

## 4. Sentences the papers may use

These need no internal labels and no other source. Numbers are exact, and each sentence keeps its scope. Use them as written, or shorten them without dropping a denominator or a label.

**Setup and definitions:**
1. "To test whether CORA's learn-from-failure loop transfers to a new domain, we connected it through an adapter (building blocks, a checker and a failure description) to exact recovery of Boolean functions from sparse probes."
2. "The real test items were published two-level benchmark functions with 6 to 12 inputs (the Espresso example files, which include the MCNC benchmarks); the methods in the primary comparison saw the same random 25% of each function's truth table, and a recovery counted only if the returned program matched the function on every input, including the 75% never shown."
3. "When no block of the base language (constants, single inputs and two-input gates) fit the probes, the loop named the input implicated by the closest conflicting probe pairs and split on it; a control ran the same loop with the named input replaced at random."
4. "The protocol, code and data were frozen before any held item was chosen; the held items were selected with a salt taken from a file committed by the coordinator after an independent pre-run review, the single scored run was audited after scoring, and all of its rows were reproduced exactly."

**Primary result:**

5. "On 217 held real benchmark functions in 35 files, the loop recovered 45 exactly (20.7%), against 7 (3.2%) for the base language of two-input gates and 12 (5.5%) for the same loop with a shuffled failure description."
6. "Against the shuffled description, the loop recovered 34 functions the control missed and missed 1 that the control recovered (exact McNemar test, Holm-adjusted p = 2.1e-9); the difference in exact-recovery rate was 0.152, with a 95% bootstrap interval clustered by file of 0.075 to 0.241."
7. "Both pre-registered primary comparisons, against the base language and against the shuffled description, met the support rule: a Holm-adjusted exact McNemar test and a file-clustered 95% interval above zero."
8. "The gain was not concentrated in a few files: the loop beat the shuffled control in 13 of the 35 held files and lost in none."
9. "Because the shuffled control also keeps every program the base language finds, the comparison with the shuffled control is the test that the failure description itself carries the gain; the comparison with the base language shows only that growth adds recoveries."

**Secondaries:**

10. "The advantage over the shuffled control held at 12.5% probes (29 against 9 of 217) and at 50% probes (67 against 15 of 217), and on 120 synthetic access-control policies generated from real ClassBench seed statistics (44 against 28 of 120); all eight pre-registered secondary comparisons rejected after Holm adjustment."
11. "At the same probe budget, choosing three quarters of the probes where the surviving candidate programs disagreed most raised the loop's exact recoveries from 45 to 63 of 217 held circuits and from 44 to 56 of 120 synthetic policies."

**References, which must stay descriptive:**

12. "As descriptive references with no pre-registered test, a CART decision tree recovered 39 and an Espresso-style two-level minimiser 38 of the same 217 held circuits; on the synthetic policies, an unrestricted greedy decision-list learner recovered 49 of 120, more than the loop's 44."

**Limits and lessons (learning from failure):**

13. "The result has clear limits: 153 of the 217 held circuits, including every function in 16 of the 35 files, were recovered by none of the six methods from a quarter of their truth table."
14. "A four-fold rebuild check passed 54 of the loop's circuit programs, but only 33 of them were exact, so agreement between rebuilds does not certify an exact recovery."
15. "On policies, building rule templates from the failure description made the shuffled control lose but also kept the loop below an unrestricted learner (44 against 49 of 120), which points to using the description as a search order rather than a restriction."
16. "In development, 8 of the loop's 12 circuit recoveries came from a single file; on held items no file from that family was present, and the loop's advantage over the shuffled control spread over 13 files."

**Labels**, required wherever the numbers appear:

17. "All numbers are from held items; circuit results are real benchmark functions, policy results are synthetic from real seeds, and every recovery is a reconstruction of a known function, not a discovery."

**Short form** for the condensed papers:

18. "On 217 held real benchmark functions recovered exactly from 25% random probes, CORA's learn-from-failure loop recovered 45 functions against 12 for the same loop with a shuffled failure description (34 to 1 on discordant items; file-clustered 95% interval for the difference 0.075 to 0.241), with the gain spread over 13 of 35 files; these are reconstructions of known functions, and 153 of the 217 were recovered by no method."

## Sentences the papers must not use

- **Precedence claims.** Any claim that this is the "first" domain where the loop transfers, unless the program's shared registry confirms it.
- **Comparisons with the references.** Any claim that the loop beats, outperforms or matches the classical learners. The references are descriptive only, and on policies the decision-list learner recovered more.
- **Discovery.** Any claim that the loop discovers logic or circuits. Every result is reconstruction.
- **Probe budgets.** Any claim that active probing beats more random probes. Only the same budget was tested; random probes at 50% recovered 67, against active probing's 63 at 25%.
- **Unrecoverable functions.** Any claim that "dense" or "complex" functions cannot be recovered. Complexity was not measured.
- **Transfer from the base-language comparison.** Any use of the gain over the base language alone as evidence that the failure description transfers.
- **Policy labels.** Any description of the policy results as real policies. They are synthetic from real seeds.
- **Over-generalising the circuits.** Any statement about "real circuits" in general. The scope is held, completely specified output functions from the Espresso example files (which include the MCNC benchmarks), with 6 to 12 inputs and at most 8 per file.
