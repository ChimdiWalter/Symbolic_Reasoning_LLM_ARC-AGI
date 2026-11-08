# Failure-guided choice test, revision 1: independent post-score audit

Auditor: the independent session that wrote the pre-run review (`reviews/PRE_RUN_REVIEW_R1.md`). Written 8 Nov 2026.

Inputs: the committed tree at 4bc40dc6, extracted with `git archive` into a scratch folder. That tree holds the GO
(87f30e19), the claim and held set (0ac02b92), the kernels (413a6e52), the measurements and seal (6b1337d8), and the
analysis and `RESULT.md` (4bc40dc6). I also read the study's detached-run records.

What I did not do: rescore through the study's code, run or push anything on Kaggle, or create any file other than this
one. My scripts imported nothing from `fgc/` and ran in one shared CPU slot at nice 19.

## Verdict: PASS

Custody holds, and every number in `runs/test/ANALYSIS.json` reproduces exactly: 9 groups of checks, 0 mismatches. The
pre-registered outcome **"none"** stands.

`RESULT.md` (30dc8f09...) needs the six text corrections below before any paper uses it. None of them changes a
number or the outcome.

## 1. Custody

| Check | Evidence | Result |
|---|---|---|
| GO | `GO_FGC` was added only by 87f30e19 (06:12:23Z). It binds protocol ccaa3e7c... and freeze a38f51ae...; sha256 5f5916d7... | holds |
| salt from the GO | The claim names the same GO bytes and was written at 06:29:05Z, after the GO. The generate log prints `ok generate ... go 5f5916d7...`, so the salt is `fgc-test-5f5916d762359879`. Independent check: under this salt, each of the 18 held depth tasks' sources sits at rank 0 to 2 of the main pool's salted order (generation tries the first 2 candidates per template). Under another salt the same sources sit at ranks 7 to 321 | holds |
| held set after the GO, disjoint | Generation ran once (06:14:24Z to 06:43:24Z, exit 0) and was committed with the claim (0ac02b92) before any measurement. 50 tasks: 32 missing-operation and 18 depth. The manifest digests match both files. The 9 families do not overlap the 8 source families. No held source grid is used by any world-copy task or by the source set, and none repeats. W3 hupscale filled 2 of 6 slots; the 4 unfilled slots were recorded, not replaced | holds |
| packages equal the freeze | All three notebooks embed the one archive bebea86b..., which I decoded and hashed. Each package has 53 members, equal to its `PACKAGE.json`. 52 carry exactly the digest in `FREEZE.json`; the 53rd, `runs/test/TEST_SYSTEM.json`, carries the manifest's digest 42f12322.... The gate's measure stage passed before the build (recorded in `PROGRESS.md`). Kernels are private, with no GPU, no TPU and internet off | holds |
| one measurement, three kernels | Each kernel log prints the package digest exactly once and the output digest that `fetch.py` checked. Every placed measurement file equals its archive member. 17 + 17 + 16 tasks were measured, all 50 exactly once, with no duplicate | holds |
| push deviation, no extra push or run | Each frozen `push_when_free.sh` log has one 06:44:13Z entry, "status unclear: Cannot access kernel ...". Kaggle's new wording for a kernel that does not exist yet stopped the script from ever pushing. There is then one hand push per kernel: "Kernel version 1 successfully pushed" at 06:45:09Z, 06:45:11Z and 06:45:14Z. The poll log shows one run per kernel (RUNNING from 06:45Z, COMPLETE once) and one download each. Version 1 means no earlier version existed | holds |
| seal before score, one scoring | Sealing ran at 07:18:04Z through `run_detached.sh` (gate `ok seal ... go 5f5916d7...`). The seal 0937cbac... equals `SEALED_SHA256` and was committed in 6b1337d8 (07:18:18Z). Scoring ran once at 07:18:23Z (gate `ok score`), with one `ANALYSIS.json` committed in 4bc40dc6. No frozen file changed through the scoring commit | holds |

## 2. Recomputation (sealed predictions, evaluator-only labels, measurements; my own replay and statistics)

- **The sealed static-bank arm C equals my own replay** of the frozen contract, at every budget and on every task:
  same predictions and same calls.
- **Correct tasks at T\*** (3,500,000 calls; 50 tasks): H 30, C 30, F 30, E 29, G 27, B 22, D 20, A 0. These match.
- **Primary, F against C:** 0 against 0 discordant, exact McNemar p = 1, family-clustered interval 0 to 0. The decision
  ladder gives **none**:
  - no selection advantage, and no "static bank better";
  - efficiency: -90 calls, interval -197 to 0, against the -175,000 threshold;
  - capability not met;
  - coverage not met.
- **Secondaries (Holm):**
  - F against D: 10 against 0, p 0.00195, Holm p 0.00586, interval +5.6 to +35.7 points. Holds.
  - F against E: 1 against 0 (one W2 cmirror task), p 1, Holm p 1.
  - G against C: 0 against 3, p 0.25, Holm p 0.5. All three are W1 compress tasks that G sent to search first; the
    static bank solves them by construction.
- **Budget curve:** F minus C is 0 at every budget. F's committed predictions equal C's on every task at every budget,
  although F's order differs on 5 held tasks. C equals H on every task at every budget.
- **Capability, C against B at T\*:** 10 against 2, p 0.0386, interval -2.2 to +34 points. Not met.
- **Coverage, at 4T\*:** 9 against 3, p 0.146, interval -5.6 to +30.4 points. Not met.
- **By cause at T\*:**
  - missing operation: C 14 of 32 (trim 4, compress 3, cmirror 3, rot270 3, switch 1, hupscale 0);
  - depth: C 16 of 18, B 17 of 18.
- **Construction is cheap when it does not apply.** It fitted none of the 18 held depth tasks and stopped after 897 to
  913 calls on each.
- **Not reported in RESULT.md: at the two smallest budgets, extra search beats the bank and the oracle.**

  | budget | B (extra search) | D (random order) | C, F and H |
  |---|---:|---:|---:|
  | 0.25 T\* | 9 | 9 | 7 |
  | 0.5 T\* | 19 | 18 | 15 |

  The tasks are missing-operation tasks (W1 trim twice, W3 switch twice). Construction applies to them but needs 2.8
  to 4.9 million calls, more than the budget, while search finds a correct program in 0.29 to 1.18 million. So at
  small budgets the cause-named first change is not the best one, and H is an upper bound only from T\* up.

## 3. RESULT.md: required corrections

Each correction is a text change; the outcome "none" is unchanged.

1. **Disclose the push deviation**, which is missing. Add:

   > The frozen push script could not push. Kaggle now answers "Cannot access kernel" for a kernel that does not exist
   > yet, and the script reads that as unclear. Its three processes were stopped before pushing anything. Each kernel
   > was then pushed once by hand: version 1 each, logged in `runs/kaggle/push_TEST_k.log`. The poll log shows one run
   > per kernel.

2. **Report the small-budget reversal and limit "upper bound".**
   - Add the section 2 finding: at 0.25 T\* and 0.5 T\*, extra search solves 9 and 19 tasks against 7 and 15 for the
     static bank, the fixed router and the oracle, because construction applies but cannot finish within the budget.
   - In the table, label H "oracle router (upper bound at T\* and above)".
3. **Qualify the lesson and the direction to match the reversal.**
   - Change "the best fixed order already matches the oracle" to "... at the binding budget and above".
   - Change "Choosing what to change can only pay when the changes cannot cheaply check whether they apply" to
     "Choosing what to change can pay only when a change cannot cheaply check whether it applies, or, as at the
     smallest budgets here, cannot finish within the budget when it does".
4. **Remove the overclaim "is real but not established".** Replace it with "points the same way as on the source set
   (10 against 2) but is not established (interval -2.2 to +34 points)".
5. **Give Holm-adjusted p-values beside the raw ones** for the secondaries: G against C, Holm p 0.5; F against E,
   Holm p 1.
6. **Correct two smaller points.**
   - Mention the 4 unfilled slots (W3 hupscale, 2 of 6).
   - Write "A proposed revision 2 would add ..." instead of "Revision 2 adds ...", since revision 2 does not exist yet.
   - "The held families confirm it" is better written as "the held families are consistent with it".

## 4. Sentences the papers may use (exactly as written)

1. "In a pre-registered test on 50 held controlled generated tasks (transformation tasks built from ARC training input
   grids, not ARC puzzles), a router that reads CORA's failure record gave the same answers as a static bank of the
   same two changes in a fixed order on every task: at the binding budget of 3.5 million counted primitive executions
   both solved 30 of 50, as did an oracle told each task's cause (exact McNemar p = 1); the pre-registered outcome was
   none."
2. "Failure evidence beat a random order of the same changes (30 against 20 tasks; 10 gained, none lost; Holm-adjusted
   p = 0.006) but not the best fixed order."
3. "The reason is in the bank: typed-hole construction rejects an inapplicable hole after about 900 calls (897 to 913 on
   all 18 held depth tasks), so trying it first costs almost nothing, and the best fixed order already matches the
   oracle at the binding budget and above."
4. "The bank's advantage over spending the same budget on more search pointed the same way as on the source set (10
   against 2 tasks) but did not meet the pre-registered rule (p = 0.039; family-clustered interval -2.2 to +34
   points)."
5. "At a quarter and a half of the binding budget, extra search alone solved more tasks than the bank and the oracle (9
   against 7, and 19 against 15), because construction applied but could not finish within the budget; no router in
   this test used the budget."
6. "A learned router trained on the source families did worse than the fixed order (27 against 30; three tasks of one
   held family sent to search first and lost; Holm-adjusted p = 0.5)."
7. "Choosing what to change can pay only when a change cannot cheaply check whether it applies, or cannot finish within
   the budget when it does; a proposed second revision would add an object-view search that runs to its cap when it does
   not apply."

## 5. Do not write

- that failure evidence, routing or diagnosis "helps CORA choose", "beats" or "improves on" the static bank, or any
  "selection advantage";
- that the bank "beats" extra search, or has "capability" or "coverage", or that its advantage "is real";
- that the oracle is an upper bound at every budget;
- that the fixed router "generalised" as evidence of routing skill: it reproduced the static bank's answers;
- that the learned router is "neural" (it is logistic regression), or that learning helped it (27 against 30);
- "ARC accuracy" or "ARC puzzles" for these tasks: they are controlled generated tasks;
- secondary p-values without their Holm adjustment;
- that the efficiency threshold was fixed before any source outcome: it was tightened after the preliminary source run,
  using source data only, before the freeze;
- that the kernels were pushed by the frozen script: each was pushed once by hand;
- that revision 2 exists or has results.
