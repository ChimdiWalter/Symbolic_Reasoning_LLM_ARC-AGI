# Construction at scale: is construction from failure faster search or a missing operation made available?

Post hoc, descriptive reachability analysis of the construction-at-scale result, 8 Nov 2026. Study:
`experiments/construction_at_scale_20261105/` (frozen protocol revision 4, addendum 1, phase 2 records). Result under
analysis: of 95 motivating tasks, construction from CORA's own failure evidence (S-hole, majority of three seeds)
recovered 64, matched static program search with more CPU (C7m) 38, and construction from shuffled failure evidence
16. The question, from a judge: since new operations come from a fixed space of 211 structures, does the result show
faster search rather than a missing operation becoming available?

Nothing scored was re-run. Read: the protocol, the addendum, the analysis record (`runs/analysis/ANALYSIS.json`),
each world's matched-search records (`runs/generated/W*/runs/cas_c7m/c7m_M.json`), controller records (`prep_v4`),
construction unit records (`cas_arms/units_spec.json`), the feasibility search records
(`feasibility/deep_macro_search*.json`) and the system task files (demonstrations and query inputs). Not read: any
evaluator-only file, any query output, any answer file. One small computation ran in one CPU slot at nice 19, well
under 20 CPU-minutes. It costed 2,280 candidate static programs with A2's prior costs and executed them on the
tasks' demonstrations only.

Terms. G0 is a world's static language: A2's arc-dsl grammar minus that world's removed operations. A2 is the
project's bottom-up program search; its cost of a program is the sum of integer prior costs (1 to 4) over the
program's nodes. "Level L completed" means every G0 program of cost at most L was enumerated. "Executions" are the
candidate programs the search ran. SIGMA is the 211-structure schema language (`cgrow/schema.py`). The worlds are W1,
W2 and W3, with removed sets as in protocol section 3. A task's template is T1, X(I); T2, X(A(I)); or T3, B(X(I)).

## 1. Was the 211-structure space fixed before the removed operations were chosen?

- **For 7 of the 11 families, yes.** SIGMA was committed once, on 1 Nov 2026 (commit 71bc5c6c, with the
  protocol of S1, the project's original construction test), and is unchanged since. W2's four operations and W3's three were chosen on 5 Nov.
- **Membership was a condition for choosing them.** Protocol section 3 admits an operation only if some SIGMA
  structure equals its reference on 80 probe grids.
- **For W1's four, no.** compress, downscale, trim and upscale were fixed for the first capability-growth test (Test I) on
  27 Oct (commit b4e4f600).
  SIGMA was written for S1 afterwards, and S1's claim limit states that all four are SIGMA structures.
- **So in every family the operation is a member of the space by design.** The study tests whether failure evidence
  selects the right member of a known space, as its claim limit says, not open invention. The space alone does not
  produce the result:
  - blind enumeration of the same 211 structures with the same gates recovered 32 by majority;
  - shuffled failure evidence recovered 16;
  - CORA's own failure evidence recovered 64.

## 2. Does static search use the same space and building blocks?

- **No.** C7m searches the world's G0 (136 or 137 arc-dsl productions, with function leaves and constants 290 to 294
  heads) in cost order, at about 3.2 times construction's CPU overall. On these 31 tasks the per-task median is 7.4
  times construction's charged CPU (range 3.7 to 11.3). It never sees SIGMA.
- **SIGMA's building blocks are not G0 productions:** row and column predicates, separable index maps with optional
  transposition, k by k block reductions, and colour replacement and exchange. G0 can express some SIGMA members only
  through longer compositions. These compositions are the protocol's evaluator-only routes, for example
  `apply(merge, hsplit(I, width(I)))` for the main-diagonal reflection in W2.
- **A constructed structure enters the grown grammar as one production of cost 3.** A task that needs it becomes a
  program of cost 4 to about 10, inside the base search.

## 3. Method for the 31 tasks construction solved and static search did not

1. **Construction's operation.** From construction's own saved program for the task (unit records), the operation
   it computes: a removed operation, or a composition with one kept operation.
2. **The shortest known static program.**
   - Candidates are the protocol's feasibility routes (W2: the reflection route above; W3: colour exchange
     `fill(replace(I, a, b), a, ofcolor(I, b))`, horizontal stretch by 2 `apply(merge, apply(dmirror, pair(I, I)))`,
     vertical stretch by 3 `apply(last, upscale(apply(tojvec, I), THREE))`).
   - Each route is composed with at most one outer and one inner unary grid operation of the world's G0, from 13
     names, each kept only if the world's G0 holds it.
   - Each candidate is costed with that world's A2 prior costs and executed on every demonstration of the task. The
     cheapest candidate that reproduces all of them is kept.
   - This is an upper bound on the shortest static program. The lower bound is static search's own record: no fit
     up to the level it completed on that task.
   - W1 has no route for compress or downscale. W3 has none for horizontal stretch by 3. For these three operations
     the feasibility search on probe grids found no G0 equivalent up to cost 14, after 26 to 32 million executions.
3. **Executions needed** to reach a program of cost L, in static search's own order. This is an estimate from the
   task's own growth per level, taken from the controller's 4x search (four times the base budget; level, executions) and the matched search
   (level completed, executions). The program lies between the completion of level L-1 and of level L. The factor is
   that number over the executions static search actually made.

## 4. Result

| class | tasks | where |
|---|---|---|
| no static program at any depth searched | 13 | W1 compress 5, W1 downscale 7, W3 horizontal stretch by 3, 1 |
| reachable, beyond static search's budget | 17 | W2 12 (all four removed symmetries reach through one reflection route), W3 5 |
| within the budget but missed | 1 | W2 main-diagonal reflection; the static search process failed, so this is not a search miss |

- **The 13:** static search completed levels 14 to 16 on each task, after 17 to 79 million executions, without a fit.
  No G0 equivalent of the operation exists up to cost 14.
- **The 17:** the shortest known static program costs 16 to 19. That is 1 level beyond what static search completed
  for 2 tasks, 2 levels for 8, 3 levels for 4 and 4 levels for 3. Executions grow 2.3 to 3.4 times per level on these
  tasks. Reaching the programs would have needed an estimated 1.0 to 135 times static search's own executions. The
  lower ends run 1.0 to 39.6 (median 2.9) and the upper ends 2.4 to 135 (median 8.4); the per-task geometric middle
  has a median of about 5.
- **Static search's budget was already about 3.2 times construction's overall,** so, measured against construction's
  CPU, these factors are larger again.

| world, family, template | task | construction's program (majority) | shortest known static program (cost) | static search: level completed, executions | class | estimated factor |
|---|---|---|---|---|---|---|
| W1 compress T1 | t52073858 | `sig_SEL_fore_multi(I)` | none known | 14, 22.9 M | unreachable at every depth searched |  |
| W1 compress T1 | t5a9d176a | `sig_SEL_fore_multi(I)` | none known | 15, 17.2 M | unreachable at every depth searched |  |
| W1 compress T1 | teeb894c2 | `sig_SEL_multi_multi(I)` | none known | 15, 33.7 M | unreachable at every depth searched |  |
| W1 compress T3 | t28236007 | `dmirror(sig_SEL_fore_multi(I))` | none known | 15, 37.6 M | unreachable at every depth searched |  |
| W1 compress T3 | t7938c115 | `rot180(sig_SEL_fore_multi(I))` | none known | 15, 55.8 M | unreachable at every depth searched |  |
| W1 downscale T1 | t5a67fd5f | `sig_MAP_sample_sample_0(I, THREE)` | none known | 16, 43.4 M | unreachable at every depth searched |  |
| W1 downscale T1 | t71f41e5a | `sig_MAP_sample_sample_0(I, TWO)` | none known | 16, 79.0 M | unreachable at every depth searched |  |
| W1 downscale T1 | td14930cb | `sig_MAP_sample_sample_0(I, TWO)` | none known | 15, 27.5 M | unreachable at every depth searched |  |
| W1 downscale T2 | t389a89ea | `sig_MAP_sample_sample_0(I, THREE)` | none known | 15, 19.8 M | unreachable at every depth searched |  |
| W1 downscale T2 | tb6d36d65 | `sig_MAP_sample_sample_0(rot270(I), TWO)` | none known | 15, 27.9 M | unreachable at every depth searched |  |
| W1 downscale T3 | t934dc2fb | `sig_MAP_sample_sample_0(I, THREE)` | none known | 15, 21.2 M | unreachable at every depth searched |  |
| W1 downscale T3 | t97e5ba7d | `vmirror(sig_MAP_sample_sample_0(I, TWO))` | none known | 15, 19.8 M | unreachable at every depth searched |  |
| W2 cmirror T1 | t128f7f05 | `sig_MAP_flip_flip_1(I)` | `rot180(apply(merge, hsplit(I, width(I))))` (18) | 14, 23.8 M | reachable, beyond the budget | 39.6 to 134.9 |
| W2 cmirror T1 | t66f5ca12 | `rot180(sig_MAP_same_same_1(I))` | `rot180(apply(merge, hsplit(I, width(I))))` (18) | 14, 19.5 M | reachable, beyond the budget | 32.4 to 103.4 |
| W2 cmirror T1 | ta4b5d498 | `rot180(sig_MAP_same_same_1(I))` | `rot180(apply(merge, hsplit(I, width(I))))` (18) | 14, 15.3 M | reachable, beyond the budget | 25.5 to 75.0 |
| W2 cmirror T3 | t0bc689a0 | `vmirror(sig_MAP_flip_flip_1(I))` | `hmirror(apply(merge, hsplit(I, width(I))))` (17) | 15, 31.2 M | reachable, beyond the budget | 2.7 to 7.2 |
| W2 cmirror T3 | tda182dfd | `rot180(sig_MAP_flip_same_1(I))` | `vmirror(apply(merge, hsplit(I, width(I))))` (17) | 15, 42.6 M | reachable, beyond the budget | 2.9 to 8.4 |
| W2 dmirror T1 | tde56ddd7 | `rot180(sig_MAP_flip_flip_1(I))` | `apply(merge, hsplit(I, width(I)))` (14) | process failed | within budget, static search process failed |  |
| W2 dmirror T2 | t0380083c | `sig_MAP_core_core_1(I)` | `trim(apply(merge, hsplit(I, width(I))))` (18) | 15, 30.4 M | reachable, beyond the budget | 7.1 to 19.0 |
| W2 dmirror T3 | t213b57ca | `sig_MAP_flip_flip_1(I)` | `rot180(apply(merge, hsplit(I, width(I))))` (18) | 15, 21.9 M | reachable, beyond the budget | 6.0 to 14.9 |
| W2 rot270 T1 | t5274b615 | `vmirror(sig_MAP_flip_flip_1(I))` | `hmirror(apply(merge, hsplit(I, width(I))))` (17) | 16, 44.8 M | reachable, beyond the budget | 1.0 to 2.4 |
| W2 rot270 T1 | t7a609c08 | `vmirror(sig_MAP_flip_flip_1(I))` | `hmirror(apply(merge, hsplit(I, width(I))))` (17) | 15, 21.1 M | reachable, beyond the budget | 2.4 to 5.9 |
| W2 rot90 T1 | ta2e0710e | `vmirror(sig_MAP_same_same_1(I))` | `vmirror(apply(merge, hsplit(I, width(I))))` (17) | 15, 16.3 M | reachable, beyond the budget | 2.3 to 5.2 |
| W2 rot90 T1 | tc6407f5c | `hmirror(sig_MAP_flip_flip_1(I))` | `vmirror(apply(merge, hsplit(I, width(I))))` (17) | 15, 28.3 M | reachable, beyond the budget | 2.6 to 6.9 |
| W2 rot90 T2 | t7c41a17c | `rot180(sig_MAP_same_same_1(I))` | `rot180(apply(merge, hsplit(I, width(I))))` (18) | 15, 18.5 M | reachable, beyond the budget | 5.5 to 13.1 |
| W3 hupscale T3 | t9e40806c | `rot180(sig_MAP_same_spread_0(I, TWO))` | `rot180(apply(merge, apply(dmirror, pair(I, I))))` (19) | 16, 37.0 M | reachable, beyond the budget | 5.2 to 11.9 |
| W3 hupscale T3 | tb567bf9f | `hmirror(sig_MAP_same_spread_0(I, THREE))` | none known | 15, 52.5 M | unreachable at every depth searched |  |
| W3 switch T2 | t1857f2ae | `hmirror(sig_COLOUR_0_2_1(I))` | `hmirror(fill(replace(I, ZERO, TWO), ZERO, ofcolor(I, TWO)))` (16) | 15, 30.0 M | reachable, beyond the budget | 1.0 to 2.7 |
| W3 switch T3 | td0c3d452 | `vmirror(sig_COLOUR_0_1_1(I))` | `vmirror(fill(replace(I, ZERO, ONE), ZERO, ofcolor(I, ONE)))` (16) | 14, 16.9 M | reachable, beyond the budget | 3.0 to 9.2 |
| W3 vupscale T2 | t46203446 | `vmirror(sig_MAP_spread_same_0(I, THREE))` | `apply(last, upscale(apply(tojvec, vmirror(I)), THREE))` (17) | 15, 40.3 M | reachable, beyond the budget | 2.9 to 8.2 |
| W3 vupscale T2 | tbb93aed4 | `hmirror(sig_MAP_spread_same_0(I, THREE))` | `apply(last, upscale(apply(tojvec, hmirror(I)), THREE))` (17) | 15, 32.2 M | reachable, beyond the budget | 2.7 to 7.3 |

Factors are estimated ranges (section 3). Executions are in millions. Costs are A2 prior costs in the world's G0.

## 5. What it means for the judge's question

Both mechanisms are present, and the split can be stated.
- **Missing operations made available.** For 13 of the 31 tasks (42%), static search has no equivalent program at
  any depth it or the feasibility search explored. Construction made an operation available that was not
  practically in reach.
- **Shortcuts to deep compositions.** For 17 (55%), the static language can express the task, but only 1 to 4 cost
  levels deeper than static search reached at its budget, an estimated 1 to 135 times that budget (median about 5).
  Construction replaced a cost-16-to-19 composition with one cost-3 production. That is faster search in the
  literal sense: static search would have needed several times its budget, and some tasks more than a hundred times.
- **One task** is a static-search process failure, not a reachability result.

Caveats:
1. **Shortest known, not proven shortest.** The true shortest static program lies between the level static search
   completed and the cost found here.
2. **Function-valued subprograms.** Every matched search reported its cap on constructed function values (A2 caps
   closures at 400 per search). "Level completed" therefore excludes programs that build more closures than that cap.
   The routes used here build none.
3. **"No static program at any depth searched" is not a proof that none exists** at a greater cost.
4. **The execution factors assume a constant growth per level** taken from two points of the task's own record.
5. **Choosing from a known space.** All 11 operations are members of a space fixed in advance, and four were known
   when that space was written (section 1).

## 6. Sentence for the papers (post hoc, descriptive)

Post hoc and descriptive: of the 31 tasks that construction from failure solved and matched static search did not,
13 have no equivalent program in the static language at any depth searched, and 17 have one 1 to 4 cost levels
deeper than static search reached, which it would have needed an estimated 1 to 135 times its budget (median about
5 times) to find.

## 7. The library loss in the held-back-half test (study B): result, lesson, direction

**Result.** The kept library (programs that search at 4x budget found on the source half, kept as single operations)
answered 37 of 624 held outputs correctly, against G0's 6. Static search given the library's own discovery and use
cost answered 56: a difference of -19, interval [-38, -3], Holm-adjusted p 0.018. Static search reproduced all but 3
of the library's tasks and solved 17 more. Of the library's 37, 22 came from one family, 1D-ARC flip.

**Lesson.** A library of solved programs stores successes. It shortens searches that the same CPU already
completes, so it buys speed, not reach. Operations built from failures added what search did not reach: +109 against
their matched static search.

**Direction.** Admit a library entry only if, on source tasks it was not built from, it solves tasks that static
search given the entry's discovery cost does not; otherwise grow from failures.
