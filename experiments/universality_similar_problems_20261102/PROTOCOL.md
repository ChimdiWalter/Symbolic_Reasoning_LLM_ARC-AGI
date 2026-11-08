# Protocol U2: the submitted CORA systems on public ARC-style benchmarks (PRE-REGISTERED before any download)

Written and committed on 2 Nov 2026, before any benchmark was downloaded or any system was run on one. Its sha256 is in
`MANIFEST_FREEZE.json` and is to be recorded in `RESUME.md`. It is not changed after any result. Deviations go in a
dated section of the result record.

## 1. Question

The official Universality criterion asks: "How general and universal is the approach beyond the competition? Does
your method generalize to other similar problems?" On public ARC-style benchmarks that the systems were not developed
on, for each submitted CORA system:
- how often does it answer?
- how often is it right when it answers?
- how much does it solve?
- does its verification depend on the evidence (the shuffled control)?

## 2. Systems

All three are byte-identical to the entry notebooks they were extracted from. The extracted files are in `systems/`,
with hashes in `SYSTEMS_MANIFEST.json`. Every package file matched its frozen manifest at extraction: cast_v1
`acd57e12…`, cast_selective_v2 `aa8551ad…`, R29 `11eb2ee9…`.

| id | system | notebook sha256 | call (from `systems/<id>/`) |
|---|---|---|---|
| a | O+ v2: CAST v1 core at 45/90 s, then R29 | `f683136c…` | `python -m sfo.driver_plus --challenges C --out D --submission S --packages P --deadline-s 39600 --grace-s 10 --shards 1`, with P = the notebook's `SF_OP_PACKAGES` = `[{"name": "cast_v1", "entry": "cast_candidates", "cpu_s": 45, "wall_s": 90, "details": 1}, {"name": "r29_cpu_package_20261101", "entry": "candidates", "cpu_s": 12, "wall_s": 24, "details": 0}]` |
| b | H's CORA component: cast_selective_v2 under rule B3 | `0e09afd4…` | `python -m sfb.cast_side --challenges C --out D/side --package cast_selective_v2 --entry evaluate --mode evidence --deadline T --cpu-s 15 --wall-s 30 --grace-s 10 --nice 10`, then `sfb.merge.merge_files_packages` with `[{"name": "cast_selective_v2", "mode": "evidence", "policy": "tier1:B3", "dir": D/side}]` |
| c | O: cast_v1 alone | `f2019b5d…` | `python -m sfo.driver --challenges C --out D --submission S --package cast_v1 --entry cast_candidates --cpu-s 15 --wall-s 30 --grace-s 10 --shards 1 --deadline-s 39600` |

**System b without C4.** H's neural attempts (C4) are not part of CORA, and running them would need a GPU. They are
replaced by a stand-in submission whose two attempts are both a copy of the test input, the fallback that O also uses.
The merge then puts CORA's B3-accepted grid in attempt 2. The side process gets a deadline of its start plus 6 h.

**Common to all three systems:**
- Python is `python3` (3.12.3, numpy 2.4.3), as in the O+ v2 local checks.
- Every file in `systems/` and every package manifest is re-hashed before and after each arm
  (`scripts/verify_systems.py`). Any mismatch voids the arm.
- No file in `systems/` is edited.

## 3. Benchmarks

Downloaded after this freeze from the authors' public repositories by `git clone --depth 1`, into the new folder
`/path/to/benchmark_data/`, which is outside the code folders.
- The URL, commit, licence and the sha256 of every file are recorded in `DATA_MANIFEST.json`.
- Files are read with `python3 -I` only, for evaluation only.

| benchmark | source | tasks used | groups |
|---|---|---|---|
| 1D-ARC (Xu et al. 2023) | https://github.com/khalil-research/1D-ARC | every task JSON in its dataset folder | task-type folder |
| Mini-ARC (Kim et al. 2022) | https://github.com/KSB21ST/MINI-ARC | every task JSON in its data folder (5 x 5 grids) | none |
| ConceptARC (Moskvichev et al. 2023) | https://github.com/victorvikram/ConceptARC | every task JSON in `corpus/<concept>/` | concept (16) |

- If a repository has moved, the authors' current official repository is used and recorded.
- A dataset whose licence forbids evaluation use, or that has no licence, is not used. It is reported to the
  coordinator and stays NOT RUN until cleared.
- **ARC-AGI-1 is not run.** It overlaps the ARC-AGI-2 training set used in development.
- **Task format:** ARC JSON (`train` and `test` lists of `{input, output}`).
  - A task that does not parse, has no test output, or has any grid outside 1..30 x 1..30 or with a value outside
    0..9 is excluded as outside the entries' input domain. Excluded tasks are counted.
  - ConceptARC's minimal tasks and any other folders are not used.

## 4. Freshness (after download, before any run)

Every grid (shape and values) of every benchmark task is hashed, and so is every grid of the ARC-AGI-2 training and
evaluation challenges and solutions (`outputs/score_first/data/`, 4 files).

**A task is EXCLUDED if either holds:**
- (i) any of its demonstration or test (input, output) pairs equals an (input, output) pair of an ARC-AGI-2 training
  or evaluation task;
- (ii) any of its test-input grids equals an ARC-AGI-2 grid that has at least 2 colours and at least 10 cells.

**Reported:**
- the tasks excluded by each rule;
- grid-level identities of every kind (descriptive);
- duplicate tasks within each benchmark (descriptive; not excluded).

## 5. Arms

- **REAL:** each task as given.
- **SHUFFLED:** each task keeps its own test inputs and outputs, but its demonstrations come from a donor task of the
  same benchmark.
  - The donor is drawn uniformly from the tasks of a different group (1D-ARC: another type; ConceptARC: another
    concept; Mini-ARC: any other task).
  - The draw uses `numpy.random.default_rng(20261102 + b)`, with b = 0 for 1D-ARC, 1 for Mini-ARC and 2 for
    ConceptARC, taking tasks in sorted id order.

The systems' challenge files contain demonstrations and test inputs only. Solutions are read only by the scorer.

## 6. Metrics

Metrics are reported per system, benchmark and arm, and per 1D-ARC type and ConceptARC concept. The unit is a test
output.

- **answered:** the system gives a CORA package answer:
  - a: a package filled the attempt;
  - b: the merged attempt 2 differs from the stand-in;
  - c: attempt 1 differs from the fallback copy.
- **correct:** an answered output where a package answer equals the solution.
- **precision** = correct / answered; **coverage** = answered / test outputs; **CORA accuracy** = correct / test
  outputs.
- **pass@2 accuracy:** attempt 1 or attempt 2 equals the solution, fallback copies included.
- **ARC task score:** the mean over tasks of the fraction of each task's test outputs that are correct.
- **Copy baseline:** the accuracy of the test-input copy alone.
- **Intervals:** Wilson 95% for every proportion. For the task score, a percentile bootstrap over tasks (10,000
  resamples, `default_rng(0)`).
- **Also reported:** statuses (OK, TIMEOUT, ERROR), CPU and wall time, and answers per module where the system records
  them.

## 7. Decision rule (per system and benchmark)

**VERIFIED_TRANSFER** requires all of the following. Otherwise the label is **NOT_ESTABLISHED**.
- **REAL:** at least 10 correct, and a precision Wilson lower bound of at least 0.5.
- **SHUFFLED collapses:** answered_SHUFFLED ≤ 0.5 x answered_REAL, and either
  - the SHUFFLED precision's Wilson upper bound is below the REAL precision's lower bound, or
  - SHUFFLED gives no answer.

Coverage and accuracy are always reported next to the label. Each system's summary is the number of benchmarks on
which it reaches VERIFIED_TRANSFER.

## 8. Order, compute and budget

- **Two detached chains, one per project CPU slot** (`scripts/with_cpu_slot.sh`, nice 19), with `run.status` files:
  - chain 1 runs systems c and a;
  - chain 2 runs system b.
- **Order:** every REAL arm first (ConceptARC, then Mini-ARC, then 1D-ARC), then the SHUFFLED arms in the same order.
- **CPU budget:**
  - soft cap 24 CPU-h over all arms: no arm starts once the cap is passed, and those arms are reported NOT RUN;
  - hard cap 30 CPU-h: the chains stop;
  - expected about 10 CPU-h, for about 1,200 tasks x 3 systems x 2 arms at a median of 1 to 5 CPU-s per task.
- No GPU. No Step B, VDCG, other projects' job folders or reserved data. No Kaggle action.

## 9. Reporting

- Results go to `results/RESULTS.json` and `results/SUMMARY.md`.
- The record is `records/NOV2_UNIVERSALITY_SIMILAR_PROBLEMS_RESULT.md`, with a "Claim for the paper" section written
  honestly whichever way the result falls.
- Every number is reported, including NOT RUN arms and excluded tasks.
