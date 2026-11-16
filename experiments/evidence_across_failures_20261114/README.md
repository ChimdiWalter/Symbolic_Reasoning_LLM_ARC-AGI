# EAF1: evidence across several failures (code, tests, development rehearsal)

Author: Chimdi Walter Ndubuisi. Specification: `PROTOCOL_DRAFT.md` (draft 2; the frozen text will be `PROTOCOL.md`). CPU only,
invented inputs, no model.

**A development comparison on a known benchmark.** Stage A (`experiments/visible_failure_20261113`) and the operations study ran on
these same operations and their outcomes are known. Every number from the development roster is "development only". Method
credit: bottom-up enumerative synthesis with observational equivalence is standard (TRANSIT, 2013; Escher, 2013); completing a
program with a hole is program sketching; constraining a component by several specifications is standard; the library is
arc-dsl by Michael Hodel (MIT). Nothing new is claimed about the method.

## Question in one paragraph
A target operation X is removed with its whole family. A **wrapper** is the one-argument library operation `post` around the
missing call in a consumer `post(X(arguments))`. Five **arms** see different demonstrated outputs over the SAME nine argument
tuples (generator inputs 0 to 8): A1x3 (tuples 0-2 through wrapper 1), A1x6 (0-5, wrapper 1), A1x9 (0-8, wrapper 1), A2x3 (0-2
wrapper 1, 3-5 wrapper 2), A3x3 (0-2 wrapper 1, 3-5 wrapper 2, 6-8 wrapper 3). A candidate for the missing call is accepted in
an arm when every demonstrated output of that arm is reproduced (compared with `dslx.canon`). Each arm is its own search (own
state, size limit 4, caps, CPU allowance B = 10 process-CPU seconds, wrapper evaluation inside it).

## Files
- `eaf_frozen.py`: before importing anything from stage A or the operations study, checks the sha256 of every imported file
  (`presets_vf1, frozen, vsearch, consumers, gate, library, episode`; `dslx, gen, search, presets, core`) against stage A's
  `FREEZE.json`; refuses to run on a difference.
- `presets_eaf.py`: every preset (generator roles 0-8 / 9-20 / 21-23 / 24-35 / 36-65, arms, cohorts, limits).
- `episode_eaf.py`: one target. `Records` opens record roles one at a time; steps `setup`, `step_acquisition`, `step_arms`,
  `step_admission`, `step_libraries`, `step_reuse`, `step_final` raise `OrderError` unless the earlier records are sealed.
  `setup_only(X)` runs the setup step alone.
- `summarize_eaf.py`: `SUMMARY.json` (development block and block outside the development roster apart; primary A3x3 against A1x9,
  secondary A2x3 against A1x6, five arms, admissions, reuse, costs, final panels, held-out names apart, reconciliation).
- `run_eaf.py`: the runner (below). `tests/`: fast tests and fresh-process refusal tests.

## Data roles per target (66 generator examples)
Setup 24-35 (chooses the wrappers; pooled setup slices) -> acquisition 0-8 (the nine tuples; redrawn all nine from pooled slice R at
most 5 times if a trivial repair reproduces wrapper 1 on tuples 0-2) -> five arm searches -> all five first-fit-or-none records
sealed -> admission 9-20 and pooled slice A (stage A's rule unchanged: wrapper 4 exact on 6 generator and 6 pooled inputs, plus the
preservation bank) -> libraries written read-only, one file per (target, arm), all sealed -> reuse support 21-23 and the two reuse
controls (whole-program synthesis of the wrapper-5 consumer, size limit 5; fresh one-wrapper repair) -> final 36-65 and pooled slice B,
opened last. A failed admission ends that arm's candidate; nothing else is tried.
Cohorts are nested: construction needs wrappers 1-3, admission a fourth, reuse a fifth; a missing one makes the role unavailable
(recorded, never padded, never a failure).

## Run (from the repository root)
    env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B -m pytest -q -p no:cacheprovider experiments/evidence_across_failures_20261114/tests
    env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B experiments/evidence_across_failures_20261114/run_eaf.py --setup-only <setup.json> --roster dev|all
    env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B experiments/evidence_across_failures_20261114/run_eaf.py <outdir> --roster dev [--targets a,b] [--B seconds] [--setup-record setup.json]
    ... run_eaf.py --make-freeze <FREEZE.json> --setup-record <setup.json>      (needs PROTOCOL.md; setup record must be of the full roster)
    ... run_eaf.py <outdir> --roster all --freeze <FREEZE.json> --setup-record <setup.json>
`--roster all` refuses without the freeze and the committed setup record, when any hash differs, when the output folder is not new
or empty, or when a receipt of an all-roster run exists (whatever its output folder: the run is launched once and never resumed); it
writes an exclusive receipt first. No variable or flag moves the receipt folder. `--make-freeze` refuses a setup record made by
other code than the files being frozen. `--setup-only` never searches and never opens the final role.

## Seeds of this experiment
The order of a target's wrappers (`presets_eaf.WRAPPER_TAG`) and its pooled inputs (`presets_eaf.SEQ_TAG`) are this experiment's
own. Stage A's are not reused: with them arm A1x3 would be stage A's arm V again. The 66 generator examples of a target are the
same as in stage A.

## Three freezes
`FREEZE.json` with `SETUP_RECORD_ALL.json` (commit 99423f985) was withdrawn before any check or launch: under it the counts of
usable pooled inputs of `combine` changed with the memory layout of the process (a set that holds functions is read in
memory-address order). Pooled tuples in which a container argument holds a function are now dropped.
`FREEZE_2.json` with `SETUP_RECORD_ALL_2.json` (commit f9bc9184d) was withdrawn before the launch: the independent review
found that the timeout of the final check's guard was caught as an ordinary error in `episode_eaf.match_list`. The timeout is
now re-raised to the guard's own handler; fault tests cover it. The freeze in force is `FREEZE_3.json` with
`SETUP_RECORD_ALL_3.json`; the runner refuses the earlier pairs because the code has changed.

## Rehearsals (development only, never results)
- `dev_out/`: first rehearsal, with stage A's order of wrappers (a check of the code: where wrapper and inputs coincide, arm A1x3
  gave stage A's first fits).
- `dev_setup2.json`, `dev_out2/`: the rehearsal with this experiment's own seeds, under the first freeze's code.
- `dev_setup3.json`, `dev_out3/`: the same with the code of the second freeze.
- `dev_setup4.json`, `dev_out4/`: the same with the code of the freeze in force.
- `rehearse_run_once_path.py` and its logs: the exact path of the one launch, end to end in fresh processes on a copy of this
  folder with a small roster of development names. `REHEARSAL_RUN_ONCE_PATH_3.json` is the log for the freeze in force;
  `REHEARSAL_RUN_ONCE_PATH_2.json` and `REHEARSAL_RUN_ONCE_PATH.json` are the logs for the second and first freezes.
- `REHEARSAL_RUN_ONCE_PATH_first_attempt.json`: the first attempt of that rehearsal. Every guard held; a second launch into the
  run's own folder was refused with the less useful of two messages ("folder not empty" before "already launched"). The order of
  the two refusals was changed and the rehearsal repeated.
