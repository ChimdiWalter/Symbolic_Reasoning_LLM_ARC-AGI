# Failure-guided choice test, revision 2: result

Controlled generated tasks (transformation tasks built from ARC training input grids; not ARC puzzles, not ARC
accuracy). Protocol `PROTOCOL.md` (sha256 a6496911...), freeze `FREEZE.json` (fae62f88...), GO `GO_FGC` (7e825679...),
pre-run review PASS-WITH-NOTES and delta check PASS. Held set: 84 tasks generated once after the GO in a private
Kaggle kernel: 32 missing-operation tasks of six held families (the hupscale family filled 2 of its 6 slots), 24
depth tasks, and 28 wrong-view tasks (28 of 45 slots, against an expected 24.1; 8 of the 9 view families, since
outbox filled no slot in one world). The isolation check found no reused source, no source used twice and no family
outside the plan. The set was measured once in four private kernels, sealed (4821a613...) and scored once
(`runs/test/ANALYSIS.json`). Every budget is in calls (primitive executions); the binding budget T* is 3,000,000
calls.

**Deviation.** The Kaggle login expired at 09:58Z, 12 hours after it was made, while the generation kernel ran.
Status queries were refused until the author logged in again (10:28Z). The kernel kept running and was never pushed
again; generation ran once, so there is no repeated generation to compare. Every kernel was pushed once (version 1).

## Measured result

**Pre-registered outcome: selection advantage** (the fixed router beats the static full bank at the binding budget).

**Against the best fixed order chosen after the fact, the advantage is not established.** On the held set the order
construction, view search, deeper search solves 44 of 84 at T*. F solves 11 tasks it misses and misses none it
solves (exact p = 0.001), but the family-clustered interval runs from 0.0 to +26.1 points, so by the pre-registered
success rule the comparison does not hold. On this held mix C's pre-registered order did worse than a random order
(29 against 37 of 84).

| arm | correct at T* (of 84) |
|---|---|
| H, oracle router | 55 |
| F, fixed evidence-based router | 55 |
| G, learned router (logistic regression) | 54 |
| D, random order | 37 |
| E, shuffled diagnosis | 37 |
| C, static full bank (construction, then search, then the view search) | 29 |
| B, base plus extra search | 26 |
| A, base only | 0 |

- **Primary, F against C:** 26 against 0 discordant tasks (29 solved by both, 29 by neither), exact McNemar
  p = 3.0e-8, family-clustered interval +11.8 to +55.2 points over 17 families. The success rule is met.
- **Where the gain comes from:** all 26 tasks are wrong-view tasks. C solves 2 of the 28: on 3 its deeper search
  commits a wrong answer first, and on 23 the view search, reached with about 350,000 calls left, does not finish. F
  runs the view search before deeper search whenever every demonstration keeps its size, and solves all 28. On the
  other causes F and C are equal: 10 of 32 missing-operation tasks (all by construction) and 17 of 24 depth tasks.
  F committed no wrong answer.
- **F equals the oracle on every held task at every budget.** The size check separated the causes exactly: all 28
  view tasks keep their size (by construction of the generator), no depth task does, and 7 of the 32
  missing-operation tasks do; on those 7 both orders start with construction, and F and C end equal.
- **Secondaries (Holm):** G against C, 29 against 4, p 1.1e-5, Holm p 2.3e-5, interval +9.8 to +54.4 points: holds.
  F against E, 18 against 0, p 7.6e-6, Holm p 2.3e-5, interval +11.0 to +34.2: holds. F against D, 22 against 4,
  p 0.0005, Holm p 0.0005, interval +9.1 to +33.0: holds.
- **Budget curve,** F minus C: +9.5 points at 0.25 T*, +32.1 at 0.5 T*, +31.0 at T*, and +3.6 at 2 T* and 4 T*
  (3 against 0, p 0.25). The coordinator's prediction, an advantage at binding budgets that shrinks as the budget
  grows, holds.
- **Efficiency** (descriptive; the ladder stopped at its first rung): at T*, F spends about 636,000 calls less than
  C per task on average (interval -1,127,000 to -255,000), and F reaches C's count at T* with half the budget (so
  do the random order, the learned router and the oracle).
- **Below T* the oracle is not an upper bound:** the learned router solves 14 and 45 tasks at 0.25 and 0.5 T*,
  against 12 and 42 for the oracle and F.
- **Every fixed order of the bank at T*** (descriptive, `runs/test/SIX_ORDERS.json`): construction, view, search 44;
  the two orders that start with the view search 38 each; C's order 29; the two that start with search 24 each. The
  best fixed order on the held set is not C's: it solves all 28 view tasks but only 6 of 24 depth tasks, because the
  view search runs to its cap before deeper search starts. F against it: 11 against 0, all depth tasks, exact p 0.001,
  family-clustered interval 0.0 to +26.1 points. The interval's lower end is 0, so by the pre-registered success rule
  this comparison would not count; and that order was picked after seeing the held results.
- **Power:** 28 held view tasks, above the 18 of the planning table, so the amended estimate of 0.982 is the
  relevant upper bound. No held view task needs more than the view search's cap of 2,250,000 calls.

## Lesson

Revision 1 found no selection advantage because construction checks almost for free whether it applies, so one
fixed order already matched the oracle. Revision 2 added a change that cannot check this cheaply: the view search runs
to its cap when no object view fits. With it, no fixed order suits every cause. Putting deeper search first starves
the view tasks (C solves 2 of 28); putting the view search first starves the depth tasks (6 of 24). A router that
reads one fact from the failure record, whether the demonstrations keep their size, tried the right change before the
costly wrong one on every held task and matched the oracle's result on every task at every budget: 55 against the
static bank's 29 of 84, an advantage that appears at the binding budget and nearly vanishes at twice it, as
predicted. The task's own record beat both controls: the same rule on another task's record (18 against 0) and a
random order (22 against 4). The learned router, trained on the source
families only, came within one task (54).

Three limits bound what this shows:
- **The evidence is clean by construction.** The size fact separates the causes because of how these tasks were
  generated, so the result shows that choosing the order pays when the evidence separates the causes. It does not show
  that CORA's failure record does so on natural tasks. The fact is a property of the demonstrations (whether each
  output keeps its input's size), which the failure record stores; nothing from the failed search itself entered the
  router's choice.
- **The static order was set on a different mix.** The pre-registered static order was chosen on a source set with
  fewer view tasks, and on the held mix it did worse than a random order (29 against 37). Against the best fixed order
  picked after the fact on the held set, the router's advantage is not established: 11 against 0, interval 0.0 to
  +26.1 points.
- **Two of the three causes were seen before.** The held missing-operation and depth families are revision 1's held
  families; only the view operations are new to a held test.

## Direction

- Make the strongest fixed order the pre-registered control: choose the static order on a source set whose cause mix
  matches the held plan, or make the best fixed order in hindsight the primary comparison.
- Test the router where its evidence does not separate the causes by construction: view changes that alter the grid's
  size, depth programs that keep it, and natural tasks whose failures are diagnosed rather than injected.
- The learned router came within one task of the hand-written rule (54 against 55). A test where no simple rule
  separates the causes would show whether learning adds anything.

The pre-registered contract (one bank, one meter, order the only difference, the shuffled diagnosis changing only the
descriptor) carries over unchanged.
