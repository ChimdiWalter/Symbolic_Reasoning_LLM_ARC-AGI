# Post-score audit: test T3, enzyme reaction rules from three examples

Study: `experiments/transfer_chemistry_20261108/`. Test T3 (chemistry) of the 8 November transfer tests. Study
author: Chimdi Walter Ndubuisi.

An independent auditor, who also wrote the pre-run review (`f879320c`) and the delta review of Amendment 2
(`7f4c0f9d`), wrote this audit on 8 November 2026, about 07:52Z to 08:05Z. The audit was read-only outside this
file.

**Bytes audited**
- the held records `runs/score/` (`families.jsonl`, `run.status`, `summary.json`), committed in `c596902d` and
  unchanged since;
- `RESULT.md` at `2f7236a9`;
- the original GO, commit `190756a6`, whose sha256 (the salt) is
  `8f91d8e54350686fc0ce3ce7da7cb7de5941c911597dc5a0b0955843de9089bf`;
- GO_AMENDMENT2, commit `849c4b50`;
- the Amendment 2 freeze `cdc49358` (`FREEZE.json` sha256 `3935b00a...`);
- `checks/compare_attempt1.json`, `runs/score_attempt1/` and `outputs/detached/transfer_chemistry_held_a2/`.

**Verdict: PASS.**
- Custody holds at every step.
- Every held number in `RESULT.md` recomputes from the records, except one per-family CPU median (correction 2).
- The pre-registered primary is positive.
- Four wording corrections to `RESULT.md` are required before the papers quote it (section 3). None changes a held
  count or the decision.
- Section 4 gives the sentences the papers may use, and section 5 what they must not write.

**What this audit did.**
- **Recomputed every held number** from `runs/score/families.jsonl`, with an independent implementation and with the
  frozen `t3chem/stats.compare`.
- **Re-executed 7 of the 40 families** with the frozen code (without writing bytecode) and compared each rebuilt
  record with the committed one.
- **Recomputed the salted order** from the item cache and the committed GO.
- **Compared the rerun's first 3 records** with attempt 1's.
- **Checked git custody** on HEAD, on all refs and in the reflog.

It read no `*_LOCAL.json` file and nothing under a folder named `private`, and it touched no other job and nothing
in other projects' job folders. It used under 1 CPU-minute.

**Terms used below.**
- An **exact** recovery: the arm's outcome set is exactly {true product}, compared as canonical SMILES (molecule
  strings) with stereochemistry removed.
- **static** is the best of the 1,224 published generalized rules of Ni et al. 2021, chosen on the 3 examples and
  applied one substrate at a time.
- **grown** is the full loop. It keeps a rule cut from the observed reaction centre only if that rule beats static
  on leave-one-out checks over the 3 examples; otherwise it keeps the static rule, if there is one.
- **shuffled** is the loop with the rule built from another family's change.
- **nearest neighbour** is the reference: the rule cut from the most similar example.
- **Attempt 1** is the held run that stopped after 3 of 40 families. The **rerun** is the Amendment 2 run.

## 1. Custody: PASS

**Each GO file was committed once and alone.**
- `runs/GO`: only commit `190756a6` touches it, on HEAD, on all refs and in the reflog. That commit touches nothing
  else, and the file is unchanged since.
- `runs/GO_AMENDMENT2`: only commit `849c4b50` touches it, on HEAD, on all refs and in the reflog. That commit
  touches nothing else.
- Its bytes match the exact pattern of the delta review, section 3:
  - `delta_review: 7f4c0f9d97252ff8c3269899d328a208e3c16b4a`;
  - `original_go_commit: 190756a6fab499af19b762c4d0cb6046abe49152`;
  - `written_utc: 2026-11-08T07:36:27Z`.

**The order.**
- The chain is first freeze `4eae13e5`, pre-run review `f879320c`, GO `190756a6`, freeze `cdc49358`, delta review
  `7f4c0f9d`, GO_AMENDMENT2 `849c4b50`, records `c596902d`, `RESULT.md` `2f7236a9`, then HEAD.
- Each commit is an ancestor of the next.
- `FREEZE.json` last changed at `cdc49358`, and all 18 frozen hashes still match the working tree.

**The salt and the families.**
- sha256(`runs/GO`) equals the salt in the STARTED line of `runs/score/run.status` and in `summary.json`.
- The 40 records are the first 40 families of the salted order of the 681-family scoring pool, in that order.
- In every record, the 3 examples and 5 targets are the first 3 and next 5 items of the salted item order.
- All 40 shuffle partners are as the protocol specifies.

**A single rerun.**
- `outputs/detached/transfer_chemistry_held_a2/run.status` reads `START 2026-11-08T07:36:28Z` then
  `EXIT 0 2026-11-08T07:48:47Z`.
- `runs/score/run.status` has one STARTED line (07:36:28Z) and one DONE line (07:48:46Z: 40 families, 200 held
  targets, 737.4 CPU-seconds).
- `stderr.log` is empty, there is no `runs/refusals.log`, and only two chemistry launcher folders exist (attempt 1
  and the rerun).
- GO_AMENDMENT2 was committed at 07:36:27Z, and the launch followed one second later.
- The records were committed 7 seconds after the exit (`c596902d`, 07:48:54Z) and are unchanged since.

**The command and settings.**
- `cmd.txt` is `python3 -I t3chem/run.py --mode score`: the frozen launcher's
  command, with no option.
- `summary.json` records:
  - tie-break `most_general` and nearest-neighbour level `L4`;
  - salt rule "sha256 of the committed bytes of the original runs/GO";
  - freeze `cdc49358`, GO `190756a6` and GO_AMENDMENT2 `849c4b50`.

**Attempt 1 as disclosed.**
- Its records keep the blob `39abaedc...` they had in `2d9803ef`; the only change since is the rename.
- `checks/compare_attempt1.py` was written at 07:40:25Z, during the rerun. It ran at 07:48:58Z, after the rerun's
  records were written (07:48:46Z) and committed (07:48:54Z). It prints only flags and a verdict.

**The first 3 family records match.**
- An independent comparison finds all 3 of the rerun's first records equal to attempt 1's, field by field,
  ignoring `cpu_s`.
- `checks/compare_attempt1.json` says the same: MATCH.

**Reproduction.**
- Families 3, 7, 10, 12, 14, 21 and 30 of the salted order were re-executed with the frozen code. Counting from 0,
  family 3 is the 4th family, where attempt 1 stopped, so it exercises the Amendment 2 fix. Together the seven
  cover all four loop statuses.
- Every rebuilt record equals the committed record, field by field, ignoring `cpu_s`.

## 2. Recomputation from runs/score: PASS

| arm | exact | contains the true product | families with at least 1 exact |
|---|---|---|---|
| static | 33 / 200 | 132 / 200 | 9 / 40 |
| grown | 76 / 200 | 137 / 200 | 21 / 40 |
| shuffled | 33 / 200 | 132 / 200 | 9 / 40 |
| nearest neighbour | 75 / 200 | 112 / 200 | 27 / 40 |
| grown, other tie-break | 71 / 200 | 130 / 200 | 21 / 40 |

| comparison | only first | only second | difference | 95% family-bootstrap interval | exact McNemar p |
|---|---|---|---|---|---|
| primary: grown minus static | 43 | 0 | +0.215 | [0.115, 0.330] | 2.27e-13 |
| control: grown minus shuffled | 43 | 0 | +0.215 | [0.115, 0.330] | 2.27e-13 |
| reference: grown minus nearest neighbour | 23 | 22 | +0.005 | [-0.110, 0.115] | 1.0 |
| diagnostic: other tie-break minus static | 38 | 0 | +0.190 | [0.100, 0.295] | 7.3e-12 |

**The statistics.**
- The independent implementation and the frozen function agree exactly.
- With other bootstrap seeds (1, 2, 3) the intervals move by at most 0.005; the primary's lower bound stays 0.115.

**The primary.** It is positive as pre-registered: the lower bound is above 0.

**Shuffled equals static on every target.** All 200 targets have the same outcome count, exact flag and contains
flag. The shuffled arm built no piece in 36 families, and the static rule already sufficed in 4.

**The split by loop status** (exact recoveries):

| loop status | families | targets | grown | static | nearest neighbour |
|---|---|---|---|---|---|
| static rule exact on all 3 examples | 4 | 20 | 20 | 20 | 12 |
| cut rule kept | 13 | 65 | 44 | 1 | 36 |
| cut rule not kept | 6 | 30 | 5 | 5 | 8 |
| no level fitted all 3 examples | 17 | 85 | 7 | 7 | 19 |

- **Where the 76 come from.** 44 come from cut rules kept in 13 families. The other 32 come from the static rule,
  which the loop kept in the remaining 27 families. All 43 extra recoveries over static come from the 13 families
  with a kept cut rule.
- **Families without a published rule.** In 10 of the 40 families no published rule produced the true product of
  any example, so static predicted nothing there. The loop kept a cut rule in 3 of them and predicted nothing in the
  other 7.
- **Over-generation.** In 99 targets, static's outcomes contain the true product but also other products. Grown
  recovers 29 of these exactly and nearest neighbour 38. Grown also recovers 14 targets whose product static never
  produced. 29 + 14 = 43.

**Other numbers.**
- Levels of the kept rules: L1 3, L2 1, L3 3, L4 2, L5 2, L6 2.
- Static's exact count on the 3 examples: 0 in 31 families, 1 in 4, 2 in 1, 3 in 4.
- EC classes: 22 hydrolases, 9 transferases, 5 oxidoreductases, 2 lyases, 2 ligases.
- CPU per family: median 3.18 s and maximum 123.52 s, 736.6 s in all.

**Development against held.**
- In development, grown with the frozen tie-break gained +0.374 over static (`runs/dev_c40/summary.json`). On held
  targets the gain is +0.215.
- The development rows of `RESULT.md` are correct: 27, 85 and 76 of 155.

## 3. RESULT.md scope: PASS, after four required wording corrections

**In scope as written.**
- The label "reconstruction of known enzyme transformations on held substrates within their families, not
  discovery".
- Nearest neighbour is reported as a reference, not a gate, with no difference.
- The shuffled control is called not independent.
- The attempt 1 disclosure (crash, amendment, unopened outcomes, programmatic reads, determinism MATCH).
- The "fall back to nearest neighbour" idea is labelled a hypothesis from this held run, to be tested on
  development and then on a fresh held set, never on this one.
- Development against held is reported.

**Required corrections.**
1. **Section 2, after the development table.** Delete "as the pre-run review expected". The pre-run review made no
   prediction about the size of the held gain.
2. **Section 2, CPU line.** Change "a median of 3.3" to "a median of 3.2". It is 3.18: the two middle values of the
   40 are 3.06 and 3.30.
3. **Section 3, lesson 1.** Replace "Fixed general rules usually know the right chemistry but not where it happens:
   they over-generate. Cutting the rule from the observed change, with context chosen by checks, fixes much of
   that." with:

   "The best fixed rule produced the true product among other products for 99 of 200 targets; it contained the
   true product for 132 and gave it alone for 33. The loop recovered 29 of those 99 exactly (nearest neighbour 38),
   plus 14 targets whose product the fixed rule never produced."
4. **The opening paragraph and lesson 1's result** say "a rule built from the observed reaction centre (the grown
   arm) gave ... 76 of 200". That credits all 76 to cut rules. Say instead:

   "the loop (grown arm) gave the exact product for 76 of 200: 44 from rules cut from the examples, kept in 13 of
   40 families, and 32 from the best published rule, which it kept in the other 27 (in 7 of those no published rule
   produced any example's product, so the loop predicted nothing); all 43 extra recoveries over static came from
   those 13 families."

**Recommended.**
5. Replace "matches the nearest-neighbour template baseline" with "recovers about as many as the nearest-neighbour
   template baseline (no detectable difference; 95% interval -0.110 to 0.115)". The interval allows either to be
   about 11 points better.
6. In lesson 2, label "help when the examples share one rule, and cost recoveries when they do not" as a post hoc
   reading. The groups are defined by the grown arm's own loop status.

## 4. Sentences the papers may use (exact; numbers as recomputed)

Use them as written. Shortening is allowed if every number keeps its denominator and the scope sentence (4.6)
appears nearby.

1. **Setup.** "We applied CORA's learn-from-failure loop to enzyme chemistry through an adapter and ran a
   pre-registered held test on real enzymatic reactions from EnzymeMap (derived from BRENDA): for each of 40 held
   enzyme families, the loop saw 3 example reactions and predicted the exact main product of 5 new substrates of the
   same family."
2. **The loop.** "In each family the loop kept a rule cut from the observed reaction centre only if it beat the best
   published rule on leave-one-out checks over the 3 examples, and otherwise kept that published rule (in 10 of the
   40 families no published rule produced any example's product)."
3. **Primary.** "The loop gave the exact product, and nothing else, for 76 of 200 held substrates, against 33 of 200
   for the best of 1,224 published generalized enzymatic reaction rules (Ni et al. 2021), chosen on the same 3
   examples and applied one substrate at a time (difference +0.215; 95% family-bootstrap interval 0.115 to 0.330;
   exact McNemar p = 2.3e-13, with 43 targets recovered only by the loop and none only by the published rule)."
4. **Where the gain comes from.** "All 43 extra recoveries came from the 13 of 40 families in which the loop kept a
   cut rule (44 of 65 targets, against 1 of 65 for the published rule)."
5. **Over-generation.** "The best published rule produced the true product among its outcomes for 132 of the 200
   substrates but produced it alone for only 33; the kept cut rules recovered 29 of the 99 targets where it also
   produced other products, and 14 targets whose product it never produced."
6. **Scope.** "These results are reconstruction of known enzymatic transformations on held substrates of the same
   families, not discovery of new chemistry and not transfer across families; an exact match means the same
   canonical SMILES with stereochemistry removed."
7. **Reference.** "A classical nearest-neighbour method, which applies the rule cut from the most similar example,
   recovered 75 of 200, about as many as the loop (difference +0.005; 95% interval -0.110 to 0.115); the gain over
   the published rules comes from cutting rules from the observed change, which the classical method also does."
8. **Control.** "A control that built its rule from another family's change never passed the family's own checks
   and fell back to the published rule on all 200 targets; it shows that the gain needs the family's own change,
   but it is not an independent test."
9. **Development against held.** "The gain over the published rules was smaller on held families than in
   development (+0.215 against +0.374)."
10. **The rerun.** "The first held run stopped after 3 of 40 families on an unhandled RDKit error while cutting a
    rule; a dated amendment, made before any held outcome was opened, removed stereochemistry before cutting rules
    and made any remaining failure mean 'no rule', and the rerun on the same held set finished and reproduced the
    first run's 3 completed families exactly."
11. **Post hoc split** (optional; keep the label). "In a post hoc split by the loop's own status, the loop recovered
    44 of 65 targets in the 13 families where it kept a cut rule (nearest neighbour 36 of 65) but 7 of 85 in the 17
    families where no rule level fitted all 3 examples and it fell back to the published rule (nearest neighbour 19
    of 85); using the nearest example's rule as the fallback is a hypothesis for a new pre-registered test, not a
    result."
12. **Short form** (abstract or poster). "On 200 held enzymatic reactions, given 3 examples per family, the loop gave
    the exact product for 76, against 33 for the best fixed published rule and 75 for a classical
    nearest-neighbour template method."

## 5. Do not write

- **Discovery.** Not that the loop discovers or predicts new or novel enzymatic reactions or chemistry. It
  reconstructs known transformations.
- **Transfer.** Not that it transfers across enzyme families, to new reaction types or to new chemistry. The test
  stays within families.
- **Nearest neighbour.** Not that the loop beats, outperforms or adds accuracy beyond nearest neighbour or classical
  template methods.
- **Equivalence.** Not that the loop is "equivalent to" or "as good as" nearest neighbour without the interval
  (-0.110 to 0.115).
- **Credit for the 76.** Not that "rules cut by the loop recovered 76 of 200". 32 of the 76 came from the published
  rule the loop kept.
- **Over-generation.** Not that cutting rules "fixes most" of the published rules' over-generation. It recovered 29
  of 99.
- **The library.** Not that the loop beats "the published rule library" or "published rules" in general. The
  comparison is with the best single rule chosen on the same 3 examples, applied one substrate at a time, as the
  claim limit says.
- **Controls.** Not "two controls" or "the shuffled control confirms" as an independent test. It equalled the
  published rule on all 200 targets.
- **The loop's choices.** Not that the level choice or the keep rule improve accuracy. Development showed no
  measurable effect, and the held split is post hoc.
- **The fallback hypothesis.** No accuracy for "fall back to the nearest example's rule" computed on this held set.
  It is a hypothesis for a new test.
- **Agreement.** Not that development and held agree. The held gain was smaller (+0.215 against +0.374).
- **Bare numbers.** No percentages without denominators (write 76 of 200, not "38%"), and no "accuracy" without the
  definition of an exact match.
- **Stereochemistry.** No claim that the predicted products are stereochemically correct. Stereochemistry was
  removed before comparison.
- **The run history.** Not "a single run" or "no amendments". Disclose the stopped first run, Amendment 2 and the
  rerun.
- **Labels.** No undefined labels, such as "T3", "grown", "static", "shuffled", "L0" to "L6" or "nn".
- **Anthropomorphism.** Not that the system "understands" or "learns" enzyme chemistry.

## 6. Evidence log (commands; outputs summarised above)

- **Custody:**
  - `git log` on HEAD, on all refs (`--all`) and in the reflog (`-g`), limited to `runs/GO` and
    `runs/GO_AMENDMENT2`;
  - `git show --name-only` of `190756a6` and `849c4b50`;
  - `git merge-base --is-ancestor` along the chain;
  - commit times in UTC;
  - a regular-expression match of the GO_AMENDMENT2 bytes;
  - `git rev-parse HEAD:<path>` against `git hash-object` for every record file;
  - modify times of the records and of the comparison files;
  - the hashing script over `FREEZE.json` at `cdc49358`.
- **Recomputation:** a script over `runs/score/families.jsonl` and `summary.json`. It covers the counts, the paired
  comparisons (independent and frozen), seeds 1 to 3, the loop-status split and over-generation. It also rebuilds
  the salted order, examples, targets and partners from the item cache and the committed GO, and compares attempt 1
  field by field.
- **Reproduction:** a script that re-executes families 3, 7, 10, 12, 14, 21 and 30 with the frozen modules
  (`python -I -B`) and compares each record (about 10 CPU-seconds).
