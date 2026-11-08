# T3 chemistry: held result (enzyme reaction rules from three examples)

**Label:** held targets; real data (EnzymeMap v2, BRENDA 2023); reconstruction of known enzyme transformations on
held substrates within their families, not discovery. Study author: Chimdi Walter Ndubuisi.

**In one paragraph.** For each of 40 held enzyme families (EC number plus EnzymeMap rule id), the arms saw 3 example
reactions and predicted the exact main product of 5 held substrates.
- **Primary (pre-registered): positive.** The loop (grown arm) gave the exact product, and nothing else, for 76 of
  200 held targets. The best fixed published rule (Ni et al. 2021) did so for 33 of 200. Of the loop's 76:
  - 44 came from rules cut from the examples, kept in 13 of 40 families;
  - 32 came from the best published rule, which the loop kept in the other 27. In 7 of those 27 no published rule
    produced any example's product, so the loop predicted nothing.
  All 43 extra recoveries over static came from those 13 families.
- **Control: not an independent test here.** The shuffled control equalled the static library on every target.
- **Reference: no difference.** The classical nearest-neighbour template rule recovered 75 of 200.

So, on held targets, the grown arm beats the fixed library of published rules (and the shuffled change, which here
is the same comparison). It recovers about as many as the nearest-neighbour template baseline: no detectable
difference, 95% interval -0.110 to 0.115.

## 1. Record and custody

| step | record |
|---|---|
| protocol and first freeze (Amendment 1) | `4eae13e5`, FREEZE.json sha256 `77d2a957...` |
| pre-run review | PASS-WITH-NOTES, `reviews/PRE_RUN_REVIEW.md`, commit `f879320c` |
| GO (coordinator, committed alone) | `runs/GO`, commit `190756a6`; salt = sha256 of its bytes = `8f91d8e54350686fc0ce3ce7da7cb7de5941c911597dc5a0b0955843de9089bf` |
| attempt 1 | launched once 07:11:22Z; RDKit error in rule extraction; exit 1 at 07:11:55Z after 3 of 40 families; records committed `2d9803ef`, then moved to `runs/score_attempt1/` |
| Amendment 2 and re-freeze | `cdc493584b8a8eeffa2d150d33d765c87f00a2b5`, FREEZE.json sha256 `3935b00a67547cd877f5b7857a639236af2713d12a4598156a25d8fc2895e055` |
| delta review | PASS, `reviews/DELTA_CHECK_AMENDMENT2.md`, commit `7f4c0f9d97252ff8c3269899d328a208e3c16b4a` |
| GO_AMENDMENT2 (coordinator, committed alone) | commit `849c4b50` |
| the rerun | launched once 07:36:28Z (`outputs/detached/transfer_chemistry_held_a2/`); exit 0 at 07:48:47Z; 40 of 40 families, 200 held targets; records committed at once (`c596902d`) |

**GO_AMENDMENT2 as adopted** (as in PROTOCOL.md Amendment 2). It has these fields:
- study `transfer_chemistry_20261108`;
- freeze_commit `cdc49358...`;
- freeze_json_sha256 `3935b00a...`;
- delta_review `7f4c0f9d...`;
- original_go_commit `190756a6fab499af19b762c4d0cb6046abe49152`;
- written_utc `2026-11-08T07:36:27Z`.

It carries no nonce. The salt is still the sha256 of the original `runs/GO`, so the held set is attempt 1's. The
proposal paragraph of the earlier RESULT.md had mentioned "a nonce and the sha256 of runs/GO"; the adopted file
follows the protocol instead.

**Attempt 1, disclosed.**
- No held outcome of attempt 1 was opened (displayed).
- Its record file was read by programs only:
  - `wc -l` for the line count, at 07:12:01Z (the read the file system logged);
  - a script that compared each record's family key with the salted order and printed only `True`;
  - after the rerun, the delta reviewer's optional check (`checks/compare_attempt1.py`), which printed only
    counts, true or false flags and its verdict.
- **Determinism check.** The rerun's first 3 family records equal attempt 1's 3 records field by field, ignoring
  `cpu_s`. Verdict MATCH (`checks/compare_attempt1.json`). So the amendment changed nothing for the families that
  ran before the crash.

**Checks from the reviews (post-score audit points), confirmed:**
- `cmd.txt` is the frozen launcher command with no extra option: `.../python -I t3chem/run.py --mode score`.
- `summary.json` records:
  - tie-break `most_general` and nearest-neighbour level `L4`;
  - the salt above, with the rule "sha256 of the committed bytes of the original runs/GO";
  - freeze `cdc49358`, GO commit `190756a6` and GO_AMENDMENT2 commit `849c4b50`.
- `runs/score/run.status` has one STARTED line and one DONE line (40 families, 200 held targets, 737.4
  CPU-seconds).
- The 40 recorded families are the salted order of the 681-family scoring pool (recomputed from the committed GO).
- The commits run in order: first freeze, pre-run review, GO, new freeze, delta review, GO_AMENDMENT2.
- GO_AMENDMENT2's commit touches only that file, and its delta_review field equals `7f4c0f9d`.

## 2. Held results (real data; reconstruction)

**Exact recovery.** A held target is recovered when the arm's outcome set is exactly {true product}: canonical
SMILES, stereochemistry removed.

| arm | exact | contains the true product | families with at least 1 exact |
|---|---|---|---|
| static: best published generalized rule (Ni et al. 2021) | 33 / 200 | 132 / 200 | 9 / 40 |
| grown: rule built from the observed change (the full loop) | **76 / 200** | 137 / 200 | 21 / 40 |
| shuffled control | 33 / 200 | 132 / 200 | 9 / 40 |
| nearest neighbour (reference) | 75 / 200 | 112 / 200 | 27 / 40 |
| grown with the other tie-break (most specific; secondary) | 71 / 200 | 130 / 200 | 21 / 40 |

**Paired comparisons.** Intervals are 95% intervals from resampling the 40 families 10,000 times, seed 20261108; p
is the exact two-sided McNemar test.

| comparison | only first | only second | difference in exact rate | 95% interval | p | reading |
|---|---|---|---|---|---|---|
| **primary: grown minus static** | 43 | 0 | **+0.215** | **[0.115, 0.330]** | 2.3e-13 | **positive** (lower bound above 0) |
| control: grown minus shuffled | 43 | 0 | +0.215 | [0.115, 0.330] | 2.3e-13 | the same comparison as the primary (shuffled = static on all 200) |
| reference: grown minus nearest neighbour | 23 | 22 | +0.005 | [-0.110, 0.115] | 1.0 | no difference |
| diagnostic: other tie-break minus static | 38 | 0 | +0.190 | [0.100, 0.295] | | positive |

**The loop on the 40 families** (exact recoveries per arm within each group):

| loop status | families | held targets | grown | static | nearest neighbour |
|---|---|---|---|---|---|
| static rule already exact on all 3 examples | 4 | 20 | 20 | 20 | 12 |
| piece built and kept | 13 | 65 | 44 | 1 | 36 |
| piece built, not kept (no gain over static) | 6 | 30 | 5 | 5 | 8 |
| no level reproduced all 3 examples | 17 | 85 | 7 | 7 | 19 |

- **Levels of the kept pieces:** L1 3, L2 1, L3 3, L4 2, L5 2, L6 2 (of 13).
- **Static's exact count on the 3 examples:** 0 in 31 families, 1 in 4, 2 in 1, 3 in 4.
- **Families by EC class:** 22 hydrolases, 9 transferases, 5 oxidoreductases, 2 lyases, 2 ligases.
- **CPU:** 737.4 CPU-seconds for the rerun (cap 1,800); per family a median of 3.2 and a maximum of 123.5.

**Development against held** (development families only, then held). Development used the most specific tie-break
(81 of 155 for grown) and the frozen most general one (85 of 155).

| arm | development | held |
|---|---|---|
| static | 27 / 155 (17.4%) | 33 / 200 (16.5%) |
| grown | 85 / 155 (54.8%) | 76 / 200 (38.0%) |
| nearest neighbour | 76 / 155 (49.0%) | 75 / 200 (37.5%) |

The gain over static was smaller on held targets than in development (+0.215 against +0.374 for the frozen
tie-break).

## 3. Result, lesson, direction

1. **The primary is positive.**
   - **Result.** From 3 examples, the loop (grown arm) recovered 76 of 200 held products exactly. 44 came from
     rules cut from the examples, kept in 13 of 40 families; 32 came from the best published rule, which it kept in
     the other 27. The best fixed published rule alone recovered 33 of 200.
   - **Lesson.** The loop's adapter (building blocks, checker, failure description) carries over to enzyme
     chemistry.
     - The best fixed rule produced the true product among other products for 99 of 200 targets. It contained the
       true product for 132 and gave it alone for 33.
     - The loop recovered 29 of those 99 exactly (nearest neighbour 38), plus 14 targets whose product the fixed
       rule never produced.
   - **Direction.** Report T3 as a positive transfer result against fixed published rules, within families, as
     reconstruction.
2. **No gain over nearest neighbour.**
   - **Result.** Grown 76 of 200 against 75 of 200 (+0.005, interval -0.110 to 0.115). A post hoc split by the
     loop's own status:
     - where the loop kept a family-wide piece: grown 44 of 65, nearest neighbour 36 of 65;
     - where the static rule sufficed: 20 of 20 against 12 of 20;
     - where no level reproduced all 3 examples, the loop fell back to the static rule: grown 7 of 85, nearest
       neighbour 19 of 85;
     - where the piece was not kept: 5 of 30 against 8 of 30.
   - **Lesson.** The gain comes from cutting rules from the examples, which a classical template method also does.
     A post hoc reading follows; the groups are defined by the grown arm's own loop status. The loop's family-wide
     consistency and keep rule help when the examples share one rule, and cost recoveries when they do not.
   - **Direction (a hypothesis from this held run, not a claim).** When no family piece is kept, fall back to the
     example rule of the most similar example instead of the static rule. This must be tested on development
     families and then on a fresh held set, never on this one.
3. **The shuffled control repeated the primary.**
   - **Result.** It equalled static on all 200 targets. A piece built from another family's change never passed the
     family's own checks: 36 families had no piece, and in 4 the static rule sufficed.
   - **Lesson.** With the keep check in place, this control can only fall back to static. It shows that the gain
     needs the family's own change, but it is not an independent test.
   - **Direction.** Future controls should apply the foreign piece without the keep check, or swap changes between
     families of the same reaction type.
4. **Attempt 1 crashed, and the rerun matched it.**
   - **Result.**
     - Attempt 1 stopped after 3 families on an unhandled RDKit error in rule extraction.
     - Amendment 2 fixed the extractor. On development items it gave identical rules on all 10,473 working
       extractions and rules for all 27 failing ones.
     - The rerun with the same held set finished, and its first 3 family records equal attempt 1's.
   - **Lesson.** Development touched only 31 families, and the pre-run checks sampled the extractor. Before a freeze,
     every per-item code path must run over the whole development pool, and every library call made per item needs
     an explicit failure meaning.
   - **Direction.** Adopted in Amendment 2. Future pre-run reviews run every per-item library call over the whole
     development pool (delta review, note 5).

## 4. Notes from the reviews, applied

- **Scope.** The protocol's scope sentence was a development statement and was to become a held claim only if the
  held primary was positive. It is: the lower bound is 0.115. Grown against nearest neighbour is reported as
  measured (no difference), and nearest neighbour stays a reference, not a gate.
- **Shuffled.** It equalled static on every held target, so grown against shuffled repeats the primary and is not
  an independent test.
- **L0** fixes the element **and the aromatic flag** of the changed atoms (`LEVELS["L0"] = (0, "ea", {})`).
  - The frozen docstring of `t3chem/arms.py` says "element only"; it is wrong, and the code is right.
  - `ADAPTER_CARD.md` is corrected.
- **Shared reaction types.**
  - The held families are new EC-number families. Most of them share an EnzymeMap rule id (a coarse reaction type)
    with some development family: 651 of the 681 pool families do.
  - The result is therefore reconstruction within familiar reaction types, as the claim limit says.
  - The per-class counts above are descriptive.
- **Pairs across families.** Grown, static and nearest neighbour see only their own family's examples. A pair shared
  across families could only have helped the shuffled control, which still recovered nothing beyond static.
- **For the audit:**
  - the nonce of `runs/GO` is the one point of trust (reflog, commit times);
  - the autosave runs every 30 minutes;
  - the rerun did not crash; a native RDKit crash, the residual risk, did not occur.

## 5. CPU

| stage | CPU |
|---|---|
| development, checks and amendment checks | about 24 CPU-minutes |
| attempt 1 | at most 0.6 CPU-minutes |
| the scored rerun | 12.3 CPU-minutes (cap 30) |
