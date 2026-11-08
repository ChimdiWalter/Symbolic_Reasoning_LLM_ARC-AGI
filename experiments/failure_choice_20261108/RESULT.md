# Failure-guided choice test, revision 1: result

Controlled generated tasks (transformation tasks built from ARC training input grids; not ARC puzzles, not ARC
accuracy). Protocol `PROTOCOL.md` (sha256 ccaa3e7c...), freeze `FREEZE.json` (a38f51ae...), GO `GO_FGC` (5f5916d7...),
pre-run review PASS-WITH-NOTES, post-score audit PASS (`reviews/POST_SCORE_AUDIT.md`; its six text corrections are
applied here). Held set: 50 tasks generated after the GO (32 missing-operation tasks of six held families, 18 depth
tasks; the hupscale family filled only 2 of its 6 slots, and the 4 unfilled slots were recorded, not replaced),
measured once in three private Kaggle kernels, sealed (0937cbac...) and scored once (`runs/test/ANALYSIS.json`).
Every budget is in calls (primitive executions); the binding budget T* is 3,500,000 calls.

**Deviation: the kernels were pushed by hand.** The frozen push script could not push. Kaggle now answers "Cannot
access kernel" for a kernel that does not exist yet, and the script reads that as unclear. Its three processes were
stopped before pushing anything. Each kernel was then pushed once by hand: version 1 each, logged in
`runs/kaggle/push_TEST_1.log`, `push_TEST_2.log` and `push_TEST_3.log`. The poll log (`runs/kaggle/poll.log`) shows
one run per kernel.

## Measured result

**Pre-registered outcome: none** (no selection advantage, no efficiency, capability or coverage effect).

| arm | correct at T* (of 50) |
|---|---|
| H, oracle router (upper bound at T* and above) | 30 |
| C, static full bank (construction, then search) | 30 |
| F, fixed evidence-based router | 30 |
| E, shuffled diagnosis | 29 |
| G, learned router | 27 |
| B, base plus extra search | 22 |
| D, random order | 20 |
| A, base only | 0 |

- **Primary, F against C** (fixed router against the static bank): the same answer on every task, 0 against 0
  discordant, exact McNemar p = 1, family-clustered interval 0 to 0. No selection advantage.
- The static bank equals the oracle on every held task, at every budget of the curve (0.25 to 4 times T*).
- **Small budgets reverse the order.** At 0.25 and 0.5 times T*, extra search alone (B) solves 9 and 19 tasks,
  against 7 and 15 for the static bank, the fixed router and the oracle; the random order (D) solves 9 and 18. The
  gained tasks are missing-operation tasks (two trim, plus two switch at 0.5 times T*). Construction applies to them
  but needs 2.8 to 4.9 million calls, more than the budget, while search finds a correct program in 0.29 to 1.18
  million. So at small budgets the change that the task's cause names is not the best first change, and the oracle
  is an upper bound only from T* up.
- **Secondaries (Holm):** F against D, 10 against 0 tasks, p 0.002, Holm p 0.006, interval +5.6 to +35.7 points:
  holds. F against E, 1 against 0, p = 1, Holm p 1: does not hold. G against C, 0 against 3, p 0.25, Holm p 0.5:
  does not hold (the learned router sent three compress tasks to search first and lost them).
- **Budget curve:** F minus C is 0 at every budget, so the coordinator's prediction (an advantage at binding budgets
  that shrinks as the budget grows) is not supported.
- **Efficiency:** F spends 90 calls less than C per task on average (interval -197 to 0), far below the material
  threshold of 175,000 calls (5% of T*). The threshold was tightened to this value after the preliminary source run,
  using source data only, before the freeze.
- **Capability, C against B at T*:** 10 against 2 tasks, p 0.039, but the family-clustered interval (-2.2 to +34
  points) includes 0, so the rule is not met. **Coverage, at 4T*:** 9 against 3, p 0.15: not met.
- By cause at T*: missing operation, C 14 of 32 (construction solves trim 4, compress 3, cmirror 3, rot270 3,
  switch 1, hupscale 0); depth, C 16 of 18 and B 17 of 18 (inside the bank, search is capped at 2,500,000 calls).

## Lesson

The source set predicted this before the freeze, and the held families are consistent with it: when one change in
the bank can check whether it applies at almost no cost, the best fixed order already matches the oracle at the
binding budget and above. Typed-hole construction stops after about 900 calls when no structure fits the hole, so
trying it first costs a depth task almost nothing, while trying search first would cost a missing-operation task the
whole search cap. Failure evidence then has nothing left to choose: it beats a random order (10 against 0), but not
the best fixed order. Two further lessons: the fixed router reproduced the static bank's answers on the new
families, while the learned router did worse (its depth-like signature caught compress tasks, which crop as depth
programs do); and on these tasks the bank's advantage over spending the budget on more search points the same way as
on the source set but is not established (10 against 2, interval -2.2 to +34 points).

## Direction

Choosing what to change can pay only when a change cannot cheaply check whether it applies, or, as at the smallest
budgets here, cannot finish within the budget when it does. A proposed revision 2 would add a change of the first
kind, a search over alternative object views that runs to its cap when it does not apply, and a third cause (the
wrong object view). Its source data would first have to show that the best fixed order falls short of the oracle;
only then is a selection advantage possible to test. The pre-registered contract (one bank, one meter, order the
only difference, the shuffled diagnosis changing only the descriptor) would carry over unchanged.
