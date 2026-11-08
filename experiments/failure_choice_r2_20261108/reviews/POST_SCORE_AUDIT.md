# Failure-guided choice test, revision 2: independent post-score audit

Auditor: the independent review session that wrote this revision's pre-run review (cf62f59b) and delta check
(bcacd5f9). Written 8 November 2026, after the single scoring.

**What I audited:**
- `RESULT.md` (9dde551d, sha256 86f06f12...);
- `runs/test/ANALYSIS.json` (3283099f...);
- the sealed predictions (4821a613..., 74c05a55);
- the six-order replay (e736c316, output 5910224e);
- `GO_FGC` (4f88bb15);
- `PROGRESS.md` and every commit touching the study since bcacd5f9, including the autosaves.

**How.** Every rerun used a scratch copy extracted from 9dde551d. I changed no study file and contacted no Kaggle
service.

**Terms used below:**
- **Arms:** A base only, B base plus extra search, C the static full bank in its pre-registered order (construction,
  deeper search, view search), D a random order, E the shuffled diagnosis, F the fixed router, G the learned router, H
  the oracle router (told each task's injected cause).
- **T\*:** the binding budget, 3,000,000 primitive executions.

## Verdict: PASS

- Custody is clean.
- Every number in `RESULT.md` recomputes exactly.
- The pre-registered outcome, selection advantage, is correct, and the three limits are disclosed.

Five wording corrections are required (section 4) before any paper uses the result. They make the post-hoc
comparison prominent and state exactly what evidence the router used. They change no number and no conclusion.

## 1. Custody

- **The GO.** `GO_FGC` is exactly the three lines the delta check specified, with third line
  `pre_run_review bcacd5f9... PASS`; its sha256 is 7e825679....
  - It was committed alone (4f88bb15), 40 seconds before the claim.
  - The claim (1aeb3dfc) names that digest.
  - The salt, fgc2-test-7e8256799c61ea1a, is in the generation notebook.
- **Frozen files are unchanged.** No frozen file or dependency changed after d9b7ffc6. The gate at HEAD prints
  "ok score", and the generate stage refuses because the claim and `runs/test/` exist.
- **Generation ran once.**
  - R2_TEST_GEN's package (65 files) matches the freeze, and it was committed before its single push (version 1,
    09:37:33Z).
  - The downloaded kernel log shows one run: package 8b8d0881, return codes [0, 0, 0], 11,042 seconds, output
    bed4a2bd. The output equals the fetched archive and its printed digest.
- **The login deviation, 09:58 to 10:28Z, left no extra push or run.**
  - The poller logged 15 refused status queries (09:58:12 to 10:26:20Z), then RUNNING again from 10:28:21Z.
  - The poller never pushes. None of the 15 refusal messages contains COMPLETE, ERROR or CANCEL, so the poller read
    each as "not finished" and downloaded once, after COMPLETE.
  - The push log has one line.
  - The kernel log shows a single run of the committed package.
- **The held set is the one generated.**
  - The three parts equal the fetched files.
  - A re-merge in scratch reproduces `TEST_SYSTEM.json`, `TEST_EVAL.json` and `TEST_MANIFEST.json` byte for byte.
  - The isolation check, recomputed, prints "held 84 | reused 0 | duplicates 0 | outside the plan []".
  - The held set holds 32 missing-operation tasks, 24 depth tasks and 28 wrong-view tasks, in 17 families.
  - It was committed (765e7945) before any measurement.
- **Measurement ran once.**
  - R2_TEST_1 to R2_TEST_4 share one archive (22416486), whose 54 files match the freeze (`TEST_SYSTEM.json` matches
    the manifest).
  - The packages were committed (beca8852) before the pushes. Each kernel was pushed once (version 1, 12:45:19Z), and
    each log shows that package and return codes [0, 0, 0].
  - The measurement files equal the fetched outputs, 21 tasks per kernel.
  - The id check holds: measured 84, held 84, missing 0, extra 0.
- **One seal, then one score.**
  - Each file has exactly one commit: `SEALED_PREDICTIONS.json` (74c05a55) before `ANALYSIS.json` (58c750c9).
  - The jobs were `fgc2_seal`, `fgc2_score` and `fgc2_six_orders`, each one start and one exit 0. Revision 1's
    `fgc_seal` and `fgc_score` records are untouched.
- **The autosave commits did not break the stage order.** They carried only logs, status files, `PROGRESS.md`, and
  two kernels' fetched measurements before the seal.
- **The six-order script was fixed before any measurement** (e736c316) and run once after scoring.

## 2. Recomputation

- **Byte-identical reruns.** From the committed files, in scratch, each of these reproduced byte for byte:
  - the development-mode reseal gives `SEALED_PREDICTIONS.json` (4821a613...);
  - the rescore gives `ANALYSIS.json` (3283099f...);
  - `post/six_orders.py` gives `SIX_ORDERS.json`.
- **Independent recomputation.** I then recomputed every reported figure with my own statistics code, working from the
  sealed predictions, the labels and the measurements (with H replayed by the frozen `contract.run_arm`).

| figure | recomputed | `RESULT.md` |
|---|---|---|
| correct at T\*, of 84 | H 55, F 55, G 54, D 37, E 37, C 29, B 26, A 0 | same |
| primary, F against C | 26 against 0, p = 2.98e-8, interval +11.8 to +55.2 points, 17 families | same |
| G against C | 29 against 4, p 1.1e-5, Holm 2.3e-5, +9.8 to +54.4 | same |
| F against E | 18 against 0, p 7.6e-6, Holm 2.3e-5, +11.0 to +34.2 | same |
| F against D | 22 against 4, p 0.0005, Holm 0.0005, +9.1 to +33.0 | same |
| F minus C, 0.25 / 0.5 / 1 / 2 / 4 T\* | +9.5 (8 against 0) / +32.1 / +31.0 / +3.6 (3 against 0, p 0.25) / +3.6 | same |
| F equal to H | the same correct tasks on all 84 tasks at all five budgets | same |
| by cause at T\*, F and C | view 28 and 2; missing operation 10 and 10; depth 17 and 17 | same |
| C on the 28 view tasks | 2 solved by the view search, 3 wrong answers from deeper search, 23 out of budget | same |
| F's wrong answers | none, at any budget | same |
| tasks that keep their size | view 28 of 28, depth 0 of 24, missing operation 7 of 32 | same |
| largest view-search cost on a view task | 1,792,891 calls, under the 2,250,000 cap | same |
| efficiency, F minus C mean calls at T\* | -636,323 (interval -1,126,722 to -255,246) | same |
| first budget reaching C's 29 | F, D, G and H at 0.5 T\*; E at T\* | F's half budget only |
| below T\*, G against H and F | 14 against 12 at 0.25 T\*; 45 against 42 at 0.5 T\* | same |
| six fixed orders at T\* | construction-view-search 44; view first 38 and 38; C's 29; search first 24 and 24 | same |
| F against the best fixed order | 11 against 0, all depth, p 0.001, interval 0.0 to +26.1 | same |

## 3. `RESULT.md`

- **The ladder outcome is right.** It states "selection advantage": the first rung holds and the decision rule stops
  there.
- **The post-hoc comparison is stated, but not prominently.**
  - It appears in the ninth bullet and in the second limit, as "points the same way but has an interval reaching 0".
  - It never uses the plain words "not established".
  - Correction 1 puts the result under the outcome line.
- **All three limits are disclosed:**
  - the size evidence separates the causes by construction;
  - C's order was chosen on the source mix;
  - the held missing-operation and depth families are revision 1's.
- **There are no numerical overclaims.** Four phrases need tightening:
  - "ran the right order on every held task": F's order is not the oracle's, since F always tries construction first.
    It matched the oracle's results.
  - "Failure evidence beat both of its own controls": the deciding fact is a property of the demonstrations, which the
    failure record stores; nothing from the failed search entered F's choice.
  - The efficiency bullet credits F alone with reaching C's count at half the budget, though D, G and H do so too.
  - Nothing says that C's order did worse than a random order on the held mix, 29 against 37. A reader needs that to
    judge the primary's control.

## 4. Required corrections to `RESULT.md` (exact text; ignore line wrapping when matching)

1. **Make the post-hoc result prominent.** After the line "**Pre-registered outcome: selection advantage** (the fixed
   router beats the static full bank at the binding budget).", insert this paragraph:

   > **Against the best fixed order chosen after the fact, the advantage is not established.** On the held set the
   > order construction, view search, deeper search solves 44 of 84 at T*. F solves 11 tasks it misses and misses
   > none it solves (exact p = 0.001), but the family-clustered interval runs from 0.0 to +26.1 points, so by the
   > pre-registered success rule the comparison does not hold. On this held mix C's pre-registered order did worse
   > than a random order (29 against 37 of 84).

2. **Say what the evidence was (first limit).** After "It does not show that CORA's failure record does so on
   natural tasks.", add:

   > The fact is a property of the demonstrations (whether each output keeps its input's size), which the failure
   > record stores; nothing from the failed search itself entered the router's choice.

3. **Name C's weakness (second limit).**
   - Replace: "fewer view tasks. Against the best fixed order picked after the fact on the held set, the router's
     advantage (11 against 0) points the same way but has an interval reaching 0."
   - With: "fewer view tasks, and on the held mix it did worse than a random order (29 against 37). Against the best
     fixed order picked after the fact on the held set, the router's advantage is not established: 11 against 0,
     interval 0.0 to +26.1 points."
4. **Describe the order accurately (Lesson).**
   - Replace "ran the right order on every held task and matched the oracle" with "tried the right change before the
     costly wrong one on every held task and matched the oracle's result on every task at every budget".
   - Replace "Failure evidence beat both of its own controls" with "The task's own record beat both controls".
5. **Do not credit F alone with the half-budget result (efficiency bullet).**
   - Replace "and F reaches C's count at T* with half the budget." with "and F reaches C's count at T* with half the
     budget (so do the random order, the learned router and the oracle)."

## 5. Sentences the papers may use

Use them as written, or shorten them without adding claims. Each one is checked against section 2.

1. "In a pre-registered test on 84 controlled generated tasks (transformation tasks built from ARC training input
   grids, not ARC puzzles), each with one injected cause of failure, a fixed router that reads one fact from CORA's
   failure record, whether every demonstration keeps its grid size, solved 55 tasks at the pre-declared binding
   budget of 3,000,000 primitive executions, against 29 for the static full bank in its pre-registered order (26 tasks
   against 0; exact McNemar p = 3.0e-8; 95% interval over resampled task families, +11.8 to +55.2 points)."
2. "The whole gain came from the 28 wrong-object-view tasks, whose fix, a search over alternative object views,
   cannot cheaply check whether it applies; at every budget the router solved exactly the tasks solved by an oracle
   router told each task's injected cause."
3. "The router also beat its controls: the same rule applied to another task's failure record (18 tasks against 0)
   and a random order of the same bank (22 against 4), both holding after Holm adjustment; a router learned from the
   source families only solved 54 of 84 at the binding budget."
4. "The advantage shrank as the budget grew, from 26 tasks against 0 at the binding budget to 3 against 0 at twice
   it, as predicted before the held tasks existed."
5. "Against the best fixed order chosen after seeing the held results (construction, then the view search, then
   deeper search: 44 of 84), the router's advantage is not established: 11 tasks against 0, with an interval from
   0.0 to +26.1 points."
6. "The size fact separates the causes because of how the tasks were generated, and it comes from the demonstrations
   rather than from the failed search, so the result shows that choosing the order pays when the evidence separates
   the causes, not that CORA's failure record does so on natural tasks."
7. "The pre-registered static order was chosen on a source set with fewer view tasks and scored below a random order
   on the held mix (29 against 37), and two of the three held causes reuse the previous revision's held families with
   fresh input grids."
8. "Where one change can check cheaply whether it applies, the best fixed order matched the oracle and choosing added
   nothing (revision 1); where a change cannot, no fixed order of the bank reached the oracle (best 44 against 55 of
   84), and the pre-registered router did (revision 2)."

## 6. Do not write

1. **No ARC claim.** Do not write that CORA chooses better on ARC puzzles, or quote any figure here as ARC accuracy.
2. **No claim over every fixed order.** Do not write that the router beats every fixed order, or the best fixed
   order. That comparison is post hoc and not established.
3. **No claim about the failed search.** Do not write that the failed search, its closest program, its typed-hole
   sketches or the paid representation probe guided the choice. The router read only whether the demonstrations
   keep their size; it paid for the probe without using it.
4. **No claim about the oracle's order or the cause.** Do not write that the router chose the oracle's order or
   diagnosed the cause. It matched the oracle's results, with a different order.
5. **No strong-baseline claim.** Do not call the static full bank a strong or best baseline on the held set; it
   scored below a random order.
6. **No learning claim.** Do not write that learning helps or that the learned router generalises. The learned
   router against the fixed router was not a pre-registered comparison, and it was trained on the source set where
   the fixed rule was written.
7. **No "beat the oracle".** Do not write that the learned router beat the oracle. Below the binding budget the
   oracle's order is not optimal, so it is not an upper bound there.
8. **No vanishing advantage.** Do not write that the advantage vanishes at twice the budget: it is 3 against 0 there.
9. **No efficiency finding.** Do not present efficiency as a finding. The ladder stopped at its first rung, and a
   random order also reaches the static bank's count at half the budget.
10. **No power figures as evidence.** Do not quote 0.996 or 0.982 as evidence; they were planning upper bounds.
11. **No all-new held set.** Do not call the held set entirely new. Two of the three causes reuse revision 1's held
    families; only the input grids are fresh.
12. **No spin.** Do not write "nearly doubles accuracy" or give percentages without their counts.
13. **No reach beyond these tasks.** Do not extend the result to natural tasks or other domains, or call it confirmed
    or replicated. It is one held set, scored once.
