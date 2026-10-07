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
