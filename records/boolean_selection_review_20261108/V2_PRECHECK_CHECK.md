# Check of the corrected (version 2) development precheck: authored Boolean selection

**Verdict: PASS.** The numbers and costs are as stated in the companion's note 0602. This is an independent check for
the CORA research program (sole author: Chimdi Walter Ndubuisi), 8 November 2026, about 12:15 UTC. The pre-declared
gate returned STOP_NO_HELD, and no held study exists.

Folder: `cage/boolean_learned_selection_20261108_v2/` in the companion tree, read only.

## What was verified

1. **Pins.** All three match:
   - `DEVELOPMENT_SUMMARY.json`: 1c43835122b5c1574ea5bd0aef327a79eef7d2c80bd5a83441ccbc171464f089
   - `DEVELOPMENT_SOURCE_FREEZE.json`: 357b211e3efde120d894ee5f1da2f6137b3da36075d03546e78be4d88c7e0fb6
   - `INDEPENDENT_V2_SOURCE_REVIEW.json`: 1a80f8bb57a33a57a791bf000780330cfcbc5b9825b6d7f9890d76a88dce2e01

   All 10 files the freeze lists still match their bytes. The development configuration was hashed only, not read;
   it matches b4b479d8e73b0ae84a66b658aabad1ab58fe93673dce3ea52a3d66cc0094146d. The terminal receipt shows exit 0, no
   timeout, 15.19 CPU seconds, 28,148 KiB peak memory and no held generation.
2. **Counts match the note.** These are correct tasks out of 96:

   | budget | static | fixed | learned | shuffled | random | oracle |
   |---|---|---|---|---|---|---|
   | 4,400 | 91 | 2 | 0 | 0 | 79 | 91 |
   | 8,800 | 91 | 91 | 91 | 91 | 91 | 91 |
   | 17,600 and 35,200 | 91 | 91 | 91 | 91 | 91 | 91 |

   There were no wrong answers in any arm at any budget. At the budgets where an arm was not capped, it abstained on
   the same 5 tasks, which have no consistent rule in the bank. Total work at 8,800 was:
   - static 263,248
   - oracle 223,563
   - random 341,960
   - fixed 450,614
   - learned 463,027
   - shuffled 521,065

   The gate's three conditions were oracle at least 48, oracle minus static at least 10, and learned above static.
   The first held and the other two failed, so the gate returned STOP_NO_HELD.
3. **Each arm is charged only its own work.** I read `selector.py` (`prepare`, `learned_rank`, `fixed_rank`,
   `run_arm`). Every arm runs and pays for the base search over supports of one or two inputs, which is part of
   every method. After that:
   - Static and oracle compute nothing else.
   - Fixed pays only its own diagnosis and the hand-written score.
   - Learned pays only its own diagnosis and the logistic ranking.
   - Shuffled pays only the donor's diagnosis and the logistic ranking, but fits only the task's own observations.
   - Random pays only its seed hash, order construction and swaps.

   Each arm has one meter, uses the same 57-entry bank and is charged for the final application. The charged phases
   reported per arm in the summary agree with this.
4. **Static was re-optimised under its own cost.** `develop.py` profiles static with `prepare(arm='STATIC')`. It
   searches the 24 size orders times 720 input permutations, asserts that exactly 17,280 were examined, and optimises
   at 8,800: most correct first, then least static work. Its cached projection was checked against live execution
   384 times (96 tasks at 4 budgets). All 2,304 arm, task and budget results come from live runs.
5. **Pre-declared.** The corrected plan, the budgets and the three-condition gate are pinned in the source freeze.
   The plan was saved at 11:58:50 UTC and the launch was at 12:03:20 UTC. The budgets were not re-chosen.
6. **No held family, GO or nonce exists.** Checked by file name only, without opening any file:
   - Neither folder has a held run directory.
   - There is no GO, nonce, authorization, held-task or aggregate file at the top two levels of either folder.
   - There is no supervision root under /tmp.
   - The seed helper `held_seed_policy.py` can only derive seeds from a future GO's nonce, and it never ran.

This agrees with the reviewer's earlier probe on invented tasks for version 1. There, a static schedule charged only
its own work answered 58 of 60 at every budget from 4,400, needing at most 3,483 operations.

## Sentences the papers may use

Label for all of them: **development, in-sample; held study stopped by the pre-declared gate.** "Counted operations"
means a deterministic count of elementary checks, not time.

- **Result.** "On 96 development tasks (in-sample; the held study was stopped by its pre-declared gate), with each
  method charged only for the work it performed, all six methods, from the best of 17,280 declared fixed schedules to
  an oracle given the true inputs, answered 91 of the 96 tasks at the primary budget of 8,800 counted operations with
  no wrong answers; the other 5 tasks had no consistent rule in the bank, and every method abstained on them."
- **Lesson.** "With each method charged only for its own work, a fixed schedule could try the whole bank of 56
  candidate input sets within the budget, so diagnosis had little to save: even an oracle order saved only about 410
  counted operations per task over the fixed schedule, while the learned selector's diagnosis and ranking added about
  2,500, and at half the budget the fixed schedule still answered 91 tasks while the hand-written and learned
  diagnostic policies answered 2 and 0."
- **Direction.** "Choosing what to change can pay for itself only when the bank of options is too large for a fixed
  schedule to cover within the budget; the next test needs such a bank, for example rules over many more candidate
  inputs, with each method charged only for its own work and the stopping gate fixed in advance."
- **Optional, on how the result was reached.** "An earlier accounting that charged every method for the selectors'
  diagnostics had favoured the learned selector; the review traced that difference to the charging rule, and the
  corrected check removed it."

The per-task figures come from the summary's totals: (263,248 minus 223,563) divided by 96 is 413, and (463,027
minus 223,563) divided by 96 is 2,494.

## Do not write

1. Any reuse of version 1's forced-charge counts (learned 61 against static 26, fixed 60, oracle 84) as a selection,
   learning or routing gain. Those counts charged every method for diagnostics only the selectors used.
2. Any efficiency or "selection pays for itself" claim. The learned selector used more counted operations than the
   fixed schedule at every budget.
3. "Held", "fresh", "generalization" or "transfer" for these numbers. No held family was generated. The model was
   trained, and the static schedule chosen, on the same 96 tasks.
4. That training adds value over the hand-written diagnostic policy. They tie at 8,800, and 2 against 0 at 4,400 is
   descriptive.
5. That learned selection is useless in general. The result holds for this six-input, 56-candidate bank only.
6. Any p-value or significance statement. The held statistics never ran.
7. Any budget other than the pre-declared 4,400, 8,800, 17,600 and 35,200, or any after-the-fact budget window
   presented as a primary.
8. The oracle's 91 as a general upper bound. Here it equals the bank's ceiling.
9. Any biology, natural 595-target, ARC accuracy, Kaggle or new grammar-primitive claim from this study.
10. The version 2 engineering fixes (nonce-derived seeds, overlap assertions, output-bound acceptance) described as
    an executed held experiment.

## Scope

The companion tree was read only. I did not read the development configuration, the private development folder,
local-only files or any GO. I created no GO and touched neither CORA Step B nor /tmp/reserved. The check took a few CPU
seconds and no GPU.
