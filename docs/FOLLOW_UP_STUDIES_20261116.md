# Four follow-up studies, 13 to 15 November 2026: what is here, what can be checked, and what a rerun needs

Author: Chimdi Walter Ndubuisi. 16 November 2026.

This page belongs to the update of 16 November 2026 on the branch `arc2026-sprint`. Nothing that was submitted on
9 November 2026 was changed; that state is fixed at the tag `arc2026-paper-20261109`.

## The studies

All four ask the same narrow question with no neural model and no GPU: when an operation is removed from a known
library and is known only through examples of its inputs and outputs, can a plain search rebuild it, and what
tells a right rebuild from one that merely fits the examples? They are development comparisons on invented
inputs. None is a result on ARC tasks.

| study | folder | outcome |
|---|---|---|
| Operations from the rest of the library (13 November) | `experiments/core_operations_20261113/` | an expression of at most 4 nodes reproduced 55 of 145 hidden operations on 36 examples (25 of 145 with the whole family hidden; 46 and 21 after a stress check added after the run) |
| Repair at a visible failure (13 November) | `experiments/visible_failure_20261113/` | 9 of 102 tasks exact against 6 for solving from scratch; no benefit shown |
| Evidence through several programs (14 November) | `experiments/evidence_across_failures_20261114/` | wrong first answers 14 against 19 of 95, right ones 11 against 10; p = 0.18; the declared criterion was not met |
| Smaller building blocks (15 November) | `experiments/below_library_20261114/` | 10 of 80 longer operations rebuilt against 7; p = 0.25; the declared criterion was not met |

Each study's `RESULTS.md` gives its numbers in full, with what they do and do not show. "Criterion not met" means
that the advantage stated in advance was not shown under those blocks, examples and limits. It does not mean
that there is no benefit, and it does not mean that the two sides are equivalent.

## What each folder holds

- `PROTOCOL.md`: the protocol, fixed before the run.
- `FREEZE*.json`: the sha256 of every file the run used, recorded before the run.
- The code and its `tests/`.
- `full_out/`: the saved outputs of the one run, with `FULL_OUT_MANIFEST.sha256` beside the folder.
- `RESULTS.md`: the results record.

Left out of this update: development and pilot outputs, rehearsal records, job logs and drafts. Three data files
that the studies read are included under `experiments/proposer_20261109/selflesion/` (the library's text, a
grammar and the families of operations).

## Source from arc-dsl in this update

The operations that these studies hide and rebuild come from arc-dsl by Michael Hodel (MIT licence). Two files of
this update contain source derived from it. `experiments/proposer_20261109/selflesion/library/LIBRARY.json` holds
the extracted and normalized source of the 155 operations. `experiments/below_library_20261114/READING_FULL_OUT.md`
prints the source of each operation beside the expressions that were found for it. That source keeps its MIT
terms; its copyright and permission notice is in
[ARC_DSL_NOTICE.txt](../experiments/proposer_20261109/selflesion/library/ARC_DSL_NOTICE.txt). The complete
upstream runtime files are not bundled.

## Public copies that differ from the originals

Some files are published as copies that differ from the originals in listed places, and only there:

- a private folder path is replaced by `/path/to/repository`;
- a few sentences about unpublished work are withheld, each marked in place;
- a small number of wording changes of the kind this branch applies to its text files.

`releases/stage3/SANITISED_COPIES.md` lists every such file with the sha256 of the original and of the public
copy and says what was replaced. The freeze tables hold the hashes of the originals. A changed copy therefore
does not match its entry in a freeze table, and the map is where the two can be reconciled.

## What can be checked without rerunning anything

- **Every saved output matches its manifest** (1,275 files in the four studies). From the root of the repository:

      (cd experiments/core_operations_20261113/full_out && sha256sum -c ../FULL_OUT_MANIFEST.sha256)
      (cd experiments/visible_failure_20261113/full_out && sha256sum -c ../FULL_OUT_MANIFEST.sha256)
      (cd experiments/evidence_across_failures_20261114/full_out && sha256sum -c ../FULL_OUT_MANIFEST.sha256)
      (cd experiments && sha256sum -c below_library_20261114/FULL_OUT_MANIFEST.sha256)

- **The tables of the fourth study can be regenerated from its saved outputs**, byte for byte, with the standard
  library alone. In `experiments/below_library_20261114/`:

      python3 -I results_tables/render_results_tables.py full_out --check AFTER_RUN_CHECK.json \
          --earlier EARLIER_RESULT_CHECK.json --time detached_job_record/time.txt --out /tmp/tables.md
      cmp /tmp/tables.md RESULTS_TABLES.md

  The appendix of that study's `RESULTS.md` is the same file.

These two checks were run on an exported copy of this update before it was published, and both passed.

## What a rerun needs, and what was not tested

The studies cannot be rerun from this copy as published. A rerun needs:

1. **The repository path.** Four files hold the path of the repository as a constant, published here as
   `/path/to/repository`: `experiments/core_operations_20261113/dslx.py`,
   `experiments/visible_failure_20261113/frozen.py`, `experiments/evidence_across_failures_20261114/eaf_frozen.py`
   and `experiments/below_library_20261114/bl_frozen.py`. Either make `/path/to/repository` a link to your
   checkout, or set the constant in the four files. An edited file no longer matches its hash in a freeze table.
2. **The library of operations.** The complete runtime files of arc-dsl are not bundled, and the extracted
   source in `LIBRARY.json` is not enough to run the studies. Fetch https://github.com/michaelhodel/arc-dsl at
   commit `635de4902a5fb4e376f27333feaa396d3f5dfdcb` and place its files `LICENSE`, `arc_types.py`,
   `constants.py` and `dsl.py` in `outputs/search_components/resources_20261026/github/arc-dsl/`. Their sha256
   are in the freeze tables.
3. **One listed file is absent.** The freeze tables list
   `experiments/proposer_20261109/selflesion/families/FAMILY_RULE.md`, which is not part of this update. The
   studies do not read it, and their own checks of the files they import do not need it; a check of every listed
   file will report it missing.
4. Python 3.12 and `PYTHONHASHSEED=0`; the commands are in each `RESULTS.md`.

A rerun from this public copy was not tested. The checks of the previous section were.

## Words used in the records

- **"The independent review"** is a second, separately run checking process within the project. It read the
  designs before the code was written and recomputed the saved numbers after each run. It is not external peer
  review.
- **"Development names"** are operations set apart for building and tuning. They are never part of a primary
  comparison.
- **"First fit"** is the first expression a search finds that reproduces every example it was shown. Many first
  fits are wrong on fresh inputs, which is one of the things these studies measure.

## Limits

These are measurements on one constructed library of operations with invented inputs. Agreement on a finite set
of examples is not the same as recovering an operation's full meaning, and none of this is evidence about
accuracy on ARC tasks, about transfer to another domain or about a system that grows by itself.
