# An offline competition scaffold for ncv2-g3 (design, 21 October 2026)

**Status:** code and tests only. Nothing has been submitted, and nothing will be submitted without the author's
explicit decision. Code: `kaggle/cora_g3_scaffold/scaffold.py`; tests: `tests/test_cora_g3_scaffold.py` (3 pass).

## 1. Where CORA stands

| entry | public leaderboard | whose |
|---|---|---|
| CORA_FHR_V1 (18 October) | 0.00% | CORA |
| the NVARC reproduction | 27.64% | third party (NVARC); never CORA's |

ncv2-g3 has no evaluation on real tasks yet. Its first real-task number will come from a separately authorized
experiment, not from this scaffold.

## 2. What the scaffold guarantees

| requirement | how |
|---|---|
| offline | ncv2-g3 is symbolic: no model, no network |
| every test input, two attempts | `solve_task` reads ncv2-g3's `attempts_by_test` for every test input |
| never malformed | the submission is pre-filled with the test input as fallback, validated per task (exactly `attempt_1` and `attempt_2`, grids 1–30 × 1–30 of ints 0–9), repaired to the fallback if invalid, and written atomically after every task |
| runtime limits | a per-task CPU cap (the search's own `cpu_cap_s`, process CPU time, robust to machine load) inside a global deadline; the cap shrinks as time runs out; no task starts in the last minute |
| failures | an exception in a task leaves its fallback in place and is recorded |
| provenance | code tree hash, Python and numpy versions, per-output origin (the ncv2-g3 program as an S-expression, or `fallback`), per-task traces; all in `provenance.json`, never in the submission |
| third-party code | none; a checkpoint-assisted arm would list the checkpoint and its licence (Apache-2.0) and attribution (`kaggle/NVARC_NOTICE.md`) in `provenance.json`, and ship no upstream code |

## 3. Budget arithmetic (to be measured before any entry)

- Kaggle limits on record (`records/NEURAL_CORA_V2_COMPETITIVE_PATH_ADDENDUM_20261020.md`): notebooks of at most
  12 h, on L4×4 machines.
- ncv2-g3 at 3,000 candidates on DEV-style tasks: about 10–30 CPU-s per task on Athe (measured under contention;
  unit tests and the smoke check). A hidden set of about 120 tasks would therefore fit easily, but this is not yet
  measured on real tasks or on Kaggle hardware.
- Native CORA's own inducers keep a wall-clock deadline (the generative inducer, 20 s), which is not CPU time.

## 4. Remaining risks

1. **Accuracy.** No real-task evidence yet. The frozen real-ARC check measures ncv2-g2, not ncv2-g3.
2. **Coverage of size-changing tasks.** The joint constructor works only when every demonstration keeps its grid
   shape; size-changing tasks rely on the ncv2-g2 stream.
3. **Packaging.** The `geocat_arc` native engine and its sealed v23 flags must be packaged as before
   (`kaggle/cora_fhr_v1_deploy`, `kaggle/build_dataset.sh`); the scaffold assumes they are importable.
4. **Selection without certificates.** ncv2-g3 ranks fitting programs; it never certifies an answer. Two attempts
   can both be wrong.
5. **Wall-clock components.** Under contention the native inducers' wall deadline can cut candidates (section 3).
