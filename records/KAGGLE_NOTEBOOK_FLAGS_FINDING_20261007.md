# Finding: the Kaggle notebook does not run the sealed configuration (2026-10-07)

Found while fixing the pilot's NATIVE_BASELINE (protocol section 6A). Not
part of the pilot; recorded for the ARC Prize 2026 submission.

- The sealed 185 of 1,000 (v23, 2026-08-19) ran the unified harness with
  five engine flags: ARC_DIHEDRAL_FRAMES=45, ARC_GENERATIVE=1,
  ARC_PATTERN_DERIVE=1, ARC_VARIANT_BUDGET=1, ARC_RAY_EXT=1 (RUN_HISTORY
  "CHAIN FLAGS unchanged"; `cora_tti/full_engine_solver.py`; the comment in
  `kaggle/build_dataset.sh`).
- `kaggle/kaggle_notebook.py` sets only PYTHONPATH for the harness
  subprocess. Every one of those flags is read from the environment and is
  off when absent (`geocat_arc/object_reasoning/engine.py`, `inducer.py`,
  `growth.py`, `generative.py`; `harness/run_harness.py` for the frames
  allowance). A notebook built from this file therefore runs the engine
  below its sealed configuration.
- `kaggle/build_dataset.sh` still packages the v22 library path (already
  noted in `records/ASSET_TABLE.md`); the library bytes are identical from
  v20 to v23, so only the path is stale.

Consequence: before the entry deadline (2026-10-26), the notebook must set
the five flags in the harness subprocess environment (and budget the
frames allowance inside the 12 hours), or the submission's measured
configuration must be stated as the flag-free one. No change was made here;
the notebook is outside this block's frozen scope.

## Correction applied and verified (2026-10-07, commits c57f4b3, c407776)

- Found a second gap: the sealed runs also had `learned_verbs.json` in the
  object directory (records/NATIVE_ASSETS_PROVENANCE.md); the package and
  the notebook carried neither it nor a working library path (the package
  shipped the library under a v22 output path the notebook never read, so
  the notebook would have stopped before the harness ran).
- `kaggle/kaggle_notebook.py` now sets the five flags for the harness
  subprocess only, installs both assets with sha256 checks (refusing missing
  or altered files) and logs its configuration; `kaggle/build_dataset.sh`
  builds `arc_certified_solver_v23.tar.gz` (code, library.json,
  learned_verbs.json; no data, no outputs, no research artifacts).
- Tests (`tests/test_kaggle_parity.py`, 5 pass): the native environment has
  exactly the sealed flags; notebook and pilot native baseline agree on
  flags and assets; altered assets are refused; K* refuses the five flags;
  research workers strip them.
- Local notebook run on the built package (one synthetic fixture and two
  development tasks; 2 workers, 1,500 s budget; no answers read): flags
  present in the harness process and both pool workers; imports from the
  staged package; asset hashes correct; valid submission (every id, both
  attempts per output); the fixture's attempt 1 is its correct recolouring.
  No network module is used (one `socket.gethostname()` call).
- Runtime: the frames allowance (+345 s per task) is outside the governor;
  the worst case at 120 tasks on 4 CPUs (about 720 s per task) is about 6 h,
  inside the 11.25 h budget.
- Not measured: the accuracy effect. This is deployment repair, not a
  reasoning contribution; it reproduces no score until a scored run.
