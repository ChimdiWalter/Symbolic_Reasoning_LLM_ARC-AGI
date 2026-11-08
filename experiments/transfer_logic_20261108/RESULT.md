# Result: logic recovery transfer test (T1), held items

T1 is the new-domain test of whether CORA's reasoning loop transfers to recovering Boolean logic exactly from sparse
probes.

**Labels.**
- Every number below is from **held** items.
- Circuit results are **real**: published MCNC benchmark functions from the Espresso example files.
- Policy results are **synthetic from real seeds**: ClassBench seed statistics.
- Every recovery is **reconstruction** of a known function, not discovery.

## Custody record

| Step | Record |
|---|---|
| First freeze | commit cb4369883501797581ff201a102923cefc2f43ef. It failed the independent pre-run review on two custody defects; the design passed (`reviews/PRE_RUN_REVIEW.md`, commit 99ec4245) |
| Amendment 1 and re-freeze | commit 73e11d26f54ac203ce79744cc46e6f1c25257879, FREEZE.json sha256 853a603e91660afaf517f098c08166cc55b813dcbe3ebe0f619824c20d05bc8a |
| Delta check | PASS (`reviews/DELTA_CHECK.md`, commit 13e1b506) |
| GO | written and committed alone by the coordinator: commit bca541e7, written 2026-11-08T06:43:28Z |
| Scored run | launched once by the coordinator at 06:43:28Z through `scripts/run_detached.sh` with a CPU slot. It finished at 06:51:51Z with exit status 0 |
| Results | committed as written in commit 7f7377f5 |

**What the run recorded** (in `summary.json` and `results/run.status`):
- salt `41ee77539198dbcc253d486bb4a7078b25a7b9ffde054cc845d05bf4df99ea10`, which is the sha256 of the committed GO
  file;
- freeze commit `73e11d26f54ac203ce79744cc46e6f1c25257879`;
- 771 item-and-fraction rows: 217 circuits at three fractions and 120 policies at one;
- 60.4 CPU-seconds, against a cap of 1,800.

**Deviations.** None:
- one run, with no rerun;
- no change to code, configuration or data after the re-freeze.

**One stale line.** FREEZE.json's `note` field still says held items are chosen with the freeze commit hash as the
salt. That describes the first freeze. The run does not read the field. The salt in force is the sha256 of the
committed GO file (PROTOCOL.md section 2, Amendment 1), and it is the salt recorded above.

## Primary: real circuits, 25% probes, 217 held items in 35 files

Exact recoveries, out of 217:

| Static (two-input gates) | Grown (the loop) | Shuffled failure description | Grown with active probing | Espresso-style minimiser (reference) | CART decision tree (reference) |
|---|---|---|---|---|---|
| 7 (3.2%) | **45 (20.7%)** | 12 (5.5%) | 63 (29.0%) | 38 (17.5%) | 39 (18.0%) |

The two comparisons in the primary family (Holm over the two):

| Comparison | Recovered only by the first arm | Recovered only by the second arm | Exact McNemar p | Holm p | Difference | 95% interval, clustered by file | Verdict |
|---|---|---|---|---|---|---|---|
| grown against static | 38 | 0 | 7.3e-12 | 1.5e-11 | +0.175 | [+0.091, +0.269] | **supported** |
| grown against shuffled | 34 | 1 | 2.1e-9 | 2.1e-9 | +0.152 | [+0.075, +0.241] | **supported** |

The file-clustered interval is the deciding criterion. The pre-run review showed that it cannot exclude 0 when the
gain sits in 1 to 3 files.

Here the gain is spread out:
- grown beats static in 15 of the 35 held files;
- grown beats shuffled in 13 files, and shuffled beats grown in none;
- 16 files have no recovery by any arm.

- **Result:** on real benchmark functions, the loop with the true failure description recovered 45 of 217 functions
  exactly from a quarter of their truth tables. The same loop fed a shuffled description recovered 12.
- **Lesson:** the failure description does real work in this domain:
  - splitting on the input implicated by the closest conflicting probe pairs generalises;
  - splitting on a random input mostly does not, although both trees fit every probe.

  Because shuffled also contains static, this comparison carries the transfer claim. The comparison with static only
  shows that growth adds recoveries.
- **Direction:** in this domain, the loop and its failure description transferred on held real data.
  Carry the same adapter design (blocks, checker, closest-conflict description) to the next domain.

## Secondaries (one Holm family of 8; all 8 reject at 0.05)

Real circuits, exact recoveries out of 217:

| Comparison | Exact recoveries | Only first / only second | Holm p | 95% interval, clustered by file |
|---|---|---|---|---|
| 12.5% probes: grown against static | 29 against 6 | 23 / 0 | 1.4e-6 | [+0.042, +0.183] |
| 12.5% probes: grown against shuffled | 29 against 9 | 21 / 1 | 5.5e-5 | [+0.031, +0.165] |
| 50% probes: grown against static | 67 against 7 | 60 / 0 | 1.4e-17 | [+0.163, +0.400] |
| 50% probes: grown against shuffled | 67 against 15 | 53 / 1 | 4.3e-14 | [+0.133, +0.355] |
| 25% probes: active against random probing (grown arm) | 63 against 45 | 19 / 1 | 9.2e-5 | [+0.034, +0.139] |

Synthetic policies, 25% probes, exact recoveries out of 120 in 12 seed clusters:

| Comparison | Exact recoveries | Only first / only second | Holm p | 95% interval, clustered by seed |
|---|---|---|---|---|
| grown against static | 44 against 27 | 17 / 0 | 6.1e-5 | [+0.075, +0.217] |
| grown against shuffled | 44 against 28 | 16 / 0 | 9.2e-5 | [+0.075, +0.200] |
| active against random probing (grown arm) | 56 against 44 | 14 / 2 | 0.0042 | [+0.050, +0.158] |

Grown beats shuffled on 9 of the 12 seeds and loses on none.

**Probe fractions.**
- **Result:** grown against shuffled holds at every probe fraction. Exact recoveries by grown rise from 29 to 45 to
  67 as the fraction goes from 12.5% to 25% to 50%. Shuffled stays at 9 to 15.
- **Lesson (a descriptive trend over three fractions, not tested):** the gap between grown and shuffled widens
  with the evidence: 0.092, 0.152 and 0.240 at 12.5%, 25% and 50%.
- **Direction:** none needed; this matches the design.

**Active probing.**
- **Result:** choosing the next probes where the surviving programs disagree raised exact recoveries from 45 to 63
  of 217 circuits and from 44 to 56 of 120 policies, at the same budget.
- **Lesson:** at the same budget, probing where the surviving candidates disagree is worth more than probing at
  random.
- **Direction:** use active probing as the default probe policy wherever the domain lets the learner choose its
  observations.

## References (descriptive, not gates)

The protocol makes no test claim about the references. The McNemar p-values and intervals for them in
`summary.json` are not used for any claim.

- **Circuits at 25%:** grown 45, CART 39, Espresso-style minimiser 38, out of 217. Against CART, grown recovers 7
  items it misses and misses 1 it recovers. Against the minimiser, the split is 8 and 1.
- **Policies at 25%:** grown 44, full decision-list learner 49, CART 37, out of 120.

**Median held-input errors at 25%:**

| Domain | Static | Grown | Shuffled | Active | Minimiser | CART | Full list |
|---|---|---|---|---|---|---|---|
| Circuits | no program for 195 of 217 items | 16 | 28 | 8 | 19 | 16 | |
| Policies | no program for 80 of 120 items | 8 | 24 | 1 | | 14.5 | 4 |

**Verify flag** (step 6 of the loop, a secondary measure; four-fold rebuild):

| Domain | Grown | Static | Shuffled |
|---|---|---|---|
| Circuits | 54 verified, 33 of them exact | 21 verified, 6 exact | 21 verified, 6 exact |
| Policies | 42 verified, 31 exact | 30 verified, 22 exact | 31 verified, 22 exact |

## The four caveats in PROTOCOL.md section 9, checked on held items

1. **Grown only tied the decision tree in development (12 against 12 of 84).**
   - **Result:** on held circuits, grown recovered 45 against CART's 39 and the minimiser's 38. These are
     descriptive references with no test.
   - **Lesson:** on held circuits the loop recovered more functions than either reference (45 against 39 and 38 of
     217), but this comparison is descriptive and untested; on held policies the unrestricted decision-list learner
     recovered more than the loop (49 against 44 of 120).
   - **Direction:** a pre-registered comparison against the references would be needed to claim more.
2. **8 of grown's 12 development recoveries came from one file (alu1).**
   - **Result:** no alu file is held. The held gain is spread over 15 files against static and 13 against shuffled.
     The largest single files are sex (7 of 8 items), newapla1 (6 of 7), newapla (5 of 8), b11 (4 of 8) and t3 (4
     of 8).
   - **Lesson:** the development concentration did not carry over.
   - **Direction:** none needed.
3. **Version 2 policy growth fell short of the full decision-list learner in development (15 against 17 of 48).**
   - **Result:** it fell short again on held policies, 44 against 49 of 120. The full learner recovered 8 items that
     grown missed; grown recovered 3 that the full learner missed.
   - **Lesson:** failure-built templates narrow the language. That is what makes the shuffled control lose, but it
     also stops grown from reaching rules that an unrestricted search finds.
   - **Direction:** keep the description as a search order rather than a restriction. Try the described field
     first, then fall back to every field combination of the same size, and test that version on fresh items.
4. **Shuffled also contains static.**
   - **Result:** static recovered 7 circuits and 27 policies, and grown recovered every one of them.
   - **Lesson:** grown against static shows only that growth helps. The transfer claim rests on grown against
     shuffled, which is supported in the primary and in every secondary.
   - **Direction:** none needed.

## Negatives

**Most held circuits are not recovered by any arm.**
- **Result:** at 25% probes, 16 of the 35 held files, holding 81 of the 217 items, have no recovery by any arm,
  including the references. The 16 files are br1, dist, exp, exps, lin.rom, m3, max46, max1024, newtag, newtpla1,
  pope.rom, prom1, prom2, risc, root and sqn. Most are ROM-like (read-only-memory tables) or arithmetic tables.
  In all, 153 of the 217 held circuits were recovered by no method. Grown recovers 20.7% of held circuits; 79.3%
  stay unrecovered by it.
- **Lesson:** none of the six methods recovered any function in these 16 files from a quarter of its rows; whether
  that reflects the functions' complexity was not measured.
- **Direction:** for such functions, report recoverability against function complexity, and spend the budget on
  active probing (which raised grown from 45 to 63).

**The verify flag is a weak filter.**
- **Result:** 33 of the 54 circuits whose grown program passed four-fold rebuilding were exact (61%), and 31 of 42
  policies (74%).
- **Lesson:** agreement between rebuilds is not enough to certify an exact recovery.
- **Direction:** before accepting a program, also probe where the surviving candidates disagree, as active probing
  does.

**Family resemblance across the split (descriptive, as the pre-run review asked).**
- Held recoveries by grown in the name families that straddle the split:
  - newapla family: 11 of 15 (development newapla2 had 0 of 7);
  - m family: 1 of 16;
  - max family: 0 of 13;
  - br family: 0 of 8.
- The circuit arms were fixed before development, so the resemblance can make items correlated but cannot carry
  tuning.

## Files

- `results/held.jsonl`: one row per item and fraction, with every arm's outcome.
- `results/summary.json`: the pre-registered analyses, the salt and the freeze commit.
- `results/run.status`: the run's status.
- `report_tables.py`: descriptive tables only. It was written after the run, is not part of the frozen run, and
  computes no new test.
