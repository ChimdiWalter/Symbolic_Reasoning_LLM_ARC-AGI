# Protocol amendment 1 (6 Nov 2026): the corrections after the companion study's exact-byte review (HOLD, note 0472)

Made before any held task, held test output or phase 2 run; no GO was written. The first freeze (`FREEZE.json`
sha256 `2e46511e07757ab18086e6654e153cdbbd8059e1794bac1f5d7beec34f55645c`, protocol
`7602387708c3ac3487fa96fde50c25c6b6f1d60fbc193cefc0fe2b9acda1e1ac`) is preserved untouched as `FREEZE_V1.json`.
This amendment is part of the protocol: `PROTOCOL.md` is unchanged in text, and where this file and PROTOCOL.md
differ, this file applies. The new freeze (`FREEZE.json`, version 2) covers both files and the corrected code.

## A. The six blocking findings and their corrections

| finding (review) | correction (file) |
|---|---|
| 1. The gate admitted arm 5 as the primary while the object-growth slot was null. | `ngb/gate.py`: `require_go()` reads the primary from the GO's third line and, when it is arm 5 vs arm 4, refuses unless FREEZE.json's `object_growth.code_sha256` and file digests are filled and the contract (module, function, cost) is set in the configuration. |
| 2. The package list omitted ten files the kernel's own gate requires (`ngb/run.py`, each benchmark's candidates, discovery summary and in-sample records). | `ngb/kaggle_build.py`: the package list is derived from the freeze (every frozen file not marked Athe-only, every object-growth file, the benchmark inputs); a `check` mode, allowed without a GO, builds the archive in memory and verifies every required file is present with its frozen digest (`checks/PACKAGE_CHECK.json`); a kernel is built only when the check passes. The Athe-only set is now explicit (`ngb/freeze.py`). |
| 3. Solutions were opened before completeness and manifest checks, and missing rows were omitted from the denominator. | `ngb/report.py`: before any solution file is opened it verifies each run folder's output manifest (every listed file's digest; no unlisted row file) and STAGES.json (this GO's digest, the same primary, status complete), then collects every expected row: exactly one row per task and arm, with matching bench, task, arm, GO digest, frozen library digest and one registry digest per arm. Any missing row makes the run INCOMPLETE, any duplicate or provenance mismatch INVALID; the report then writes the lists and scores nothing (exit code 2). |
| 4. Secondary decisions used the unadjusted p. | `ngb/report.py`: Holm adjustment over the secondary family is computed first; each secondary's decision applies the pre-registered rule to its adjusted p (adjusted p < 0.05 and the clustered interval off zero). The primary keeps its raw exact p (one test). Descriptive comparisons carry no decision. |
| 5. A request for source outputs parsed the combined source-plus-held solution file before filtering, materialising held values without a GO. | `ngb/score.py`: without a GO the file is read as text, its digest checked against the freeze, and only the requested source ids' values are decoded in place (`raw_decode` at each id's key, which must occur exactly once); held entries stay undecoded text. Any held id requires the GO before the whole file is parsed. The exposure statement is corrected accordingly (section B). The data folder is read-only, so the files are not split on disk; the decode boundary is the enforced one. |
| 6. Static-child time-outs escaped without a row, and duplicate task rows overwrote silently. | `ngb/held.py` (own child search, replacing study A's): a time-out, a failed child, an unreadable result or any exception while a task is processed produces a durable failure row (stop = child_timeout, child_failed, child_unreadable, child_error or arm_error, with the detail); rows carry provenance (bench, family, task, arm, GO digest, registry digest, frozen library digests, G0 digest, CPU scale); readers raise on duplicates, and the report treats a duplicate as INVALID. `ngb/phase2.py` keeps every attempt of a stage (a failed attempt's CPU is never overwritten) and binds the library folder to the frozen library digests at the start, as `held.py` does for every run. |

## B. Statements reconciled or added

- **The protocol opening** said the ARC-AGI-2 evaluation set "has not been used". Corrected: in phase 1 the set's
  inputs were touched once, outcome-free, by the first dry run (95 tasks' demonstrations and test inputs; no solution
  opened; rows deleted unread), as section 8 of PROTOCOL.md discloses. The chronology, including the two relaunches
  that were stopped before any evaluation file was opened, is pinned in the tracked, frozen record
  `records/INCIDENT_20261105_DRY_RUN.md`.
- **Exposure of the ARC-AGI-2 evaluation set:** used in earlier development and gates of the project; touched once by
  this study's phase 1 as above; not a fresh test. A gain on it is reported with that caveat and a zero as a zero.
- **Companion exposure (promised in coordinator note 0152):** a different frozen system of the companion study was
  evaluated once on these cohorts (the three benchmarks and the public evaluation set); no outcome was read by our
  side before the first freeze. After the first freeze, coordinator note 0154 relayed the companion study's summary
  counts to this session; they do not enter this amendment, which changes only what the review required (section A),
  the statements here and the hash-seed mechanism (section C), and no held task was opened.
- **Source outputs:** the scorer reads source test outputs for the phase 1 in-sample estimates by decoding only the
  requested source ids from the combined file (section A, item 5); held outputs are never decoded without the GO.
- **The scorer verifies** the solution files' digests against the freeze before use (held and source paths alike).
- **Library binding:** every held or ARC-AGI-2 run verifies that the library files it is given have the frozen digests
  before any task is searched.
- **Charged CPU:** the library's construction cost (PROTOCOL.md section 4) is the discovery CPU over every source
  task plus the gates' charged CPU plus the combined check; candidate extraction and the redundancy signatures are
  not charged (their process CPU is recorded as `gates_process` in `library.json`, about 2 CPU-s above the charged
  gates). This convention favours the static arm by that small amount and is stated here.

## C. The hash seed

- `python -I` implies `-E`, which ignores PYTHONHASHSEED, so the first freeze's determinism claim was not implemented.
- A2's enumerator iterates a production's argument type tags when it assembles candidate pools; a plain frozenset's
  iteration order depends on the hash seed, and with a budget-stopped search the order decides which programs are
  reached before the budget ends.
- Correction (`ngb/ops.py`): this study's grammar builder gives every production's argument tags a sorted iteration
  order (`SortedTags`, a frozenset whose iteration is sorted; membership, equality and hashing unchanged). Every
  search this study runs, including the static child searches and the deterministic probes, uses this builder. Study
  A's code is unchanged.
- Verification (`ngb/seed_check.py`, `checks/SEED_CHECK.json`): three probe tasks (Mini-ARC mi0048, where the first
  program's text had been seen to vary between processes; ConceptARC co0126, a base fit; 1D-ARC 1d0053, a 4x fit) are
  searched in child interpreters started with `-s -B` (no `-E`) and PYTHONHASHSEED 0, 1 and 2, under the sorted
  builder and under study A's plain builder. Pass: under the sorted builder every recorded field (fit, program text,
  predictions, executions, completed level, stop, closest program) is identical across the seeds, and the seeds are
  seen to differ. Result: PASS (`checks/SEED_CHECK.json`): the three seeds differ (hash witnesses differ; the probes ran with `ignore_environment` 0); under the sorted builder every field is identical across the seeds; under the plain builder the fits and predictions agree across seeds and with the sorted builder, but the program text and the execution count differ between seeds, which is exactly the order dependence the review pointed at.
- Consequence for the frozen records: stage 1 and stage 2 ran before this correction under process-dependent orders.
  Their fits agree exactly with study A's records, and the probe check shows fits and predictions agree between the
  two orders on the probes; the libraries are kept as frozen. Phase 2 runs under the sorted builder only.

## D. Re-run checks (this amendment)

- **Seed check:** as in section C (pass).
- **Admission tests** (`ngb/admission_tests.py`, `checks/ADMISSION_TESTS.json`, synthetic inputs only, all pass): a GO
  naming arm 5 is refused while the object slot is empty, and a wrong freeze digest is refused; only the requested
  source ids are decoded from a combined solution text (the decoder is never called at the held entry) and a
  duplicated key is refused; six discordant tasks one way give raw p 0.03125, Holm p 0.1875 over six secondaries and
  the decision "inconclusive"; a duplicate row is INVALID and a missing row INCOMPLETE; a run with a missing row is
  reported INCOMPLETE (exit code 2) without the solution loader being called; a static child's time-out and failure
  give durable failure rows.
- **Dry run of the amended phase 2 code paths** (`checks/dry_run_v2/`, two source tasks per benchmark standing in for
  the held half, the ARC-AGI-2 arms on two source stand-ins asserted before any arm runs): every arm, the static child
  searches, STAGES.json and OUTPUT_MANIFEST.json, and the report with its manifest, identity, completeness and
  provenance checks ran end to end with exit code 0; its numbers mean nothing.
- **Package check** (`ngb/kaggle_build.py check`, `checks/PACKAGE_CHECK.json`, run against the version 2 freeze and
  reported in PROGRESS.md; not frozen because it checks the freeze itself): every file the kernel's gate requires is
  present in the archive with its frozen digest.

## E. Change log and hashes

| file | first freeze | this amendment |
|---|---|---|
| PROTOCOL.md | 7602387708c3ac3487fa96fde50c25c6b6f1d60fbc193cefc0fe2b9acda1e1ac | unchanged |
| PROTOCOL_AMENDMENT_1.md | (none) | its digest is recorded in FREEZE.json (`amendments_sha256`); a file cannot carry its own digest |
| FREEZE.json | 2e46511e07757ab18086e6654e153cdbbd8059e1794bac1f5d7beec34f55645c (kept as FREEZE_V1.json) | version 2; its digest is reported in PROGRESS.md and the coordinator's record, and the GO must name it |
| config/STUDY_CONFIG.json | 04afee0f084bb42d991cf680b724dc7dad3109b8f1ee5cd958576413cd9c3057 | unchanged |

Code changed: `ngb/gate.py`, `ngb/score.py`, `ngb/held.py`, `ngb/arc2.py`, `ngb/report.py`, `ngb/phase2.py`,
`ngb/kaggle_build.py`, `ngb/freeze.py`, `ngb/dry_run.py`, `ngb/ops.py` (SortedTags, G0Builder), `ngb/library.py` and
`ngb/discover.py` (the builder), `run.py` (the probe entry); new: `ngb/seed_check.py`,
`records/INCIDENT_20261105_DRY_RUN.md`. The GO format (three lines) is unchanged; it must name the new freeze digest.
