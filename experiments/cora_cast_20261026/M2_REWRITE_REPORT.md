# M2: typed guarded rewriting and guarded output frames

| field | value |
|---|---|
| mechanism and source revision | `cast/rewrite.py`: grounded scenes (mono-4, mono-8, multi-8; majority background), typed guarded rewrite rules with declared write sets, SYNC writes (overlap undefined) and SEQ moves (nearest to the wall first; until_blocked or to_border), first-match rule lists (<= 2 rules + default), N-guard table rewrites, guarded crop frames; construction from demonstration evidence, verification by exact execution. Run from the snapshot `runs/chain_v2/code` (ledger `cast_chain_v2`); protocol `protocols/M2_REWRITE_PROTOCOL.md` frozen before outcomes. An ordinary guarded graph rewrite, not a double-pushout implementation |
| exposure | CAST_select and CAST_holdout are unselected source cohorts (no M2 choice was made on them). ARC_eval_dev is exposed, and the move constructor is **design-exposed for 62593bfd**: the synthesis review analysed that puzzle (its section 2.3) and recommended "construction of moves by destination, with the movers partitioned by a boolean feature" over background-adaptive views; M2 implements that recommendation generically |
| strongest matched baseline | same cohort: rewrite_true_guard (the same actions with every guard TRUE: ordinary composition without guards or relations), rewrite_fixed_view (one representation), L0_only (CAST's typed L0 grammar, depth 2); ARC_eval_dev also Run A (17/22 of 172; pool 27) |
| new exact outputs and regressions | **ARC_eval_dev: 2 new exact outputs (62593bfd, both queries; 1 task)**: Run A's vote pair, likelihood pair and whole pool are wrong on both queries, every CORA-only configuration scored 0 of 120 before, and L0_only, rewrite_fixed_view and rewrite_true_guard do not fit it. 0 regressions (M2 emitted no wrong evaluation attempt; e3721c99 fits its demonstrations but every query prediction is undefined or vacuous, so nothing is emitted) |
| coverage | unselected source tasks: 10 of 176 answered (CAST_select 4/88 correct plus 1 fitting-but-wrong first attempt; CAST_holdout 6/88); ARC_eval_dev 2 tasks fit, 1 answered |
| CPU and GPU | 0.024 CPU-h for all three cohorts and three arms (88 CPU-s); 0 GPU |
| defects | none found; the review's "pairwise rules with distractors" defect does not apply (guards are per entity) |
| supported claim | on unselected source tasks, typed guards and relations over background-adaptive views construct correct programs that the same actions without guards do not (7 tasks gained, 0 lost; exact McNemar p = 0.016, two-sided, 176 tasks), and a second view adds 3 tasks (0 lost) |
| limitation | small absolute coverage (10 of 176 source tasks, 1 of 120 evaluation tasks); the evaluation hit is design-exposed; one evaluation task is a lead, not a breakthrough (G3's +5 points is not met) |
| verdict | **GO** (as a component): keep M2 and combine it with L0 (they answer different source tasks: M2 9 that L0 misses, L0 2 that M2 misses) |

## The new exact evaluation prediction (G2 feasibility lead, design-exposed)

- Task 62593bfd, both queries, first attempt correct; separate scorer `runs/chain_v2/m2/ARC_eval_dev/score_rewrite_joint.json`;
  independently re-scored by the campaign harness's scoring function (`results/score_crosscheck.json`).
- Program: `(rewrite view=mono8 [size_unique == False -> MOVE up until_blocked] [TRUE -> MOVE down to_border])`.
- What made it possible (the trace): **representation** = 8-connected single-colour objects on the grid's majority
  colour (rewrite_fixed_view, the mono-4 view, finds no fit; background-0 views would merge the background);
  **guard** = the boolean feature size_unique partitions the movers (rewrite_true_guard finds no fit);
  **schedule** = SEQ moves, nearest to the target wall first, with destination modes until_blocked and to_border;
  **verification** = exact execution on both demonstrations.
- Robustness: 8 fitting programs, all with the same query predictions (one behaviour); identical attempts under
  PYTHONHASHSEED 0 and 12345; leave-one-demonstration-out with the whole construction rebuilt from the remaining
  demonstration reproduces each held-out demonstration (2 of 2).
- Exposure statement for any use of this result: development evidence on an exposed public-evaluation task, obtained
  by a constructor that implements a recommendation the synthesis review derived partly from this very puzzle.

## Source cohorts (queries answered / queries)

| arm | CAST_select | CAST_holdout | ARC_eval_dev |
|---|---|---|---|
| rewrite_joint | 4/92 (1 fitting-but-wrong first attempt) | 6/90 | 2/172 |
| rewrite_fixed_view | 3/92 (1 wrong) | 4/90 | 0/172 |
| rewrite_true_guard | 0/92 | 3/90 | 0/172 |
| L0_only (M1 run) | 3/92 | 0/90 (1 wrong) | 0/172 |

Source tasks answered by rewrite_joint: 12eac192 (size table), 23b5c85d (crop to the smallest object), 42a50994
(delete the smallest, mono-8), b2862040 (recolour holed objects), 358ba94e, 88a62173, cd3c21df (crop to the
unique-size or unique-shape entity), 45737921 (recolour from the adjacent object), 5ffb2104 and d282b262 (SEQ moves).
