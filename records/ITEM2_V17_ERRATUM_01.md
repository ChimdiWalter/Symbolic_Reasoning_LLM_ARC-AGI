# Item-2 v1.7: erratum 01

Written 2026-10-05, before the compiler acceptance test, in response to the
one adversarial review (`records/ITEM2_V17_REVIEW_RESULT.md`, 9195641) of
the first freeze (d5b5e1b, manifest 418ee5c2). The acceptance seed range
(830,000,000 and up) was not touched by anyone before or during this
erratum. The protocol was rewritten in place with every amended rule marked
"(erratum 01)", then re-frozen.

## Blocking findings

| finding | verified | change |
|---|---|---|
| B1. The K* environment was neither enforced nor recorded, and the fixtures depend on it | yes: `cora_tti/constructive_dataset.py` builds colour tables with `abs(hash(repr(value))) % 7`; v1.6 refused without PYTHONHASHSEED=0 and pinned an environment rule, v1.7 dropped both; the RESUME re-run recipe omitted the hash seed | `kstar()` refuses (new class KSTAR_ENVIRONMENT) unless PYTHONHASHSEED=0 with hash randomization off and no ARC_* variable other than the K* pair. The acceptance script refuses before fixture generation on the same law and records `environment_snapshot()`, the hash flag, thread variables, load and CPU count at start and end. The launcher refuses if any ARC_* is set. The manifest carries the environment rule. RESUME's recipe corrected. |
| B2. `load()` and `install()` did not enforce the section 5 law | yes: run against the frozen `load()`, 8 of the reviewer's 9 forged productions LOADED (slot lists, `blocks=2.0`, compiler version, compiler sha, K identity, a body carrying `task_id`, a non-canonical literal encoding) and the ninth raised a raw `KeyError` | `compile_extension` and `load` share one build path (`_build`). `load` rebuilds the production from its own body and requires identical bytes. Another compiler build is VERSION_MISMATCH, another K* is K_IDENTITY_MISMATCH, everything else (including parse and typing failures) is TAMPERED_PRODUCTION. `install` goes through `load`. New test with all 9 cases and a forged install; all rejected with the stated classes. |

## Major findings

| finding | verified | change |
|---|---|---|
| M1. The external constructive manifest (vocabulary order, probe set) was unpinned | yes: v1.6 pinned both files; their current sha256 still equal the v1.6 pins (66780880..., c9f7fe31...) | Manifest pins `L.EXTERNAL_FILES`; `freeze_problems()` checks them. |
| M2. A crash left nothing, and a second run was not blocked | yes | The script refuses if its report, rows file, start record or marker exists; the launcher refuses on its pid record or the marker. A start record is written first and each task row is appended and synced as it finishes. Any exception that is not a compiler failure class is recorded with its traceback and gives NO_VERDICT_RUN_ERROR. |
| M3. Load was uncontrolled and unrecorded, and it pushes toward NECESSARY | accepted as stated (the K* arm is deadline-bound; e's expression slice keeps its own time) | Per-arm wall seconds and events, programs, and load at task start and end are recorded. A supplementary K* arm at 3x budget (24 s) is run per task and reported, not gating. Runs use default CPU priority, not `nice -n 19`. Load itself cannot be controlled without touching Step B, which is not allowed. |
| M4. S5 is not out-of-sample with the oracle proposer | yes, by construction | Protocol sections 10 and 14 state that S5 tests the L-leg machinery only at this stage; only S4's held-out pair is out of sample. The manifest carries the caveat. |

## Minor findings

| # | finding | disposition |
|---|---|---|
| 1 | attribution false negatives; residue checked only the top-level concept; winners carrying e's name but failing the structure test were not counted | residue now searches the whole program tree, including the 3x arm; a top-level computed pattern carrying e's name that fails the structure test is a label anomaly and fails S3; nested uses are recorded and not credited (conservative); stated in sections 8 and 14 |
| 2 | `state_snapshot` coverage gaps | the snapshot now includes every callable of `meta_ast`, `meta_induction` and the fitter (module, qualified name, bytecode) and the installed list; the docstring and section 6 say exactly what is and is not covered and how run hygiene covers the rest. Engine tests still give equal snapshots. |
| 3 | engine directories never removed | `run_reasoner` removes its directory after the run (`apply_fn` is rebuilt from the serialized program and reads nothing from it) and reports `engine_dir_removed`; the engine ablation test asserts it |
| 4 | raw exceptions (`TypeError` on dict literals, `KeyError` in `load`) | terminals must be vocabulary strings (UNKNOWN_TERMINAL; new test with 4 cases); `load` wraps every failure |
| 5 | compiler limits looser than the constructive grammar; two limits cannot bind | documented in section 4; limits unchanged (they are the compiler's own law) |
| 6 | the K*-2 inertness test is uninformative | new engine test: K* without an overlay makes zero learner calls, and with e every call is on e's shape; the 200-schema test is relabelled weak |
| 7 | S6 nearly vacuous; fingerprint errors lean toward SEPARATED | fingerprint errors are counted and reported (the exclusion follows the frozen probe convention); section 12 and S6 state the weakness |
| 8 | the K identity excluded the K* implementation; `install` ignored `compiler_sha256` | the K identity includes the compiler file's sha256 and the environment rule; `load` checks `compiler_sha256` |
| 9 | "the same semantic extension" wording | section 5 says canonicalization is slot renaming only |
| 10 | fixed arm order with first-run import cost (conservative) | documented in section 9; unchanged |
| 11 | the development fixtures were selected on held-out exactness, so the dry run does not predict S4 | stated in section 13 |
| 12 | engineering overstatements in section 15 | section 15 reworded to what is checked |

## Unchanged

- The fixture law, the seed range, N=6, the 2,000-seed search cap, the S4
  and S5 thresholds, and the outcome mapping, apart from the added
  NO_VERDICT_RUN_ERROR.
- S3 is stricter (label anomalies, whole-tree residue). Nothing was
  loosened.
- No acceptance fixture was generated, inspected or run.

## Verification before the re-freeze

- Fast suite: 36 passed (33 earlier plus 3 new).
- Engine suite: 5 passed in 203.5 s (`logs/v17/engine_tests_erratum01.log`),
  including the new learner-call test and the engine-directory assertions.
  The extended snapshot (callables included) stayed equal through every
  engine run.
- Development dry run of the amended per-task path on fixture 0
  (`logs/v17/acceptance_dryrun_dev_erratum01.log`), 142 s at load about 41
  on 24 CPUs:
  - S1 true, fresh process identical;
  - witness SEPARATED with an empty comparison set (0 fitted, 0 errors);
  - ablation EXTENSION_NECESSARY_AND_USED: K* + {e} 15.4 s, accepted,
    held-out exact; K* 8.1 s, not accepted;
  - 3x K* arm (24 s budget): not accepted, 17.1 s;
  - residue, direct disagreements, label anomalies and nested uses all 0;
  - leave-one-out 7 of 7 folds; engine directories removed; snapshot equal.
- `main()` end to end with mocked fixtures and tasks, outputs in the
  scratch directory only (`logs/v17/main_mock_test.py`, `.log`): all tasks
  good gives COMPILER_ACCEPTED; an unexpected exception gives
  NO_VERDICT_RUN_ERROR with the rows kept; a restoration failure gives
  COMPILER_DEFECTIVE; 4 fixtures give NO_VERDICT_FIXTURE_SHORTFALL; a
  second start and a foreign ARC_* variable are refused.
- The 9 forged productions against the frozen and the amended `load()`, as
  above.
