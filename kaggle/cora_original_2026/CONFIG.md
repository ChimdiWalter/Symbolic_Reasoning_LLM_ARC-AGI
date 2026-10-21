# CORA-ONLY-G3: configuration (written 21 October 2026, before any evaluation of this configuration)

**Label:** CORA-ONLY-G3. **Package version:** cora_original_2026_v1. **Competition:** ARC Prize 2026, ARC-AGI-2
(`arc-prize-2026-arc-agi-2`), a Kaggle code competition: an offline notebook (internet off), at most 12 h, writing
`submission.json` with `attempt_1` and `attempt_2` for every test input of every task.

**Every prediction comes from CORA's own engine.** No NVARC code, notebook, checkpoint or saved prediction; no Qwen
or any other pretrained model; no external predictor; no network. The packaged code is the sealed native CORA v23
solver (the unchanged `kaggle/native_v1/arc_native_baseline_v1.tar.gz` tree: `geocat_arc/`, `harness/`,
`src/reasoning_project/`, `scripts/`, the sealed `library.json` and `learned_verbs.json`) plus copies of CORA's typed
packages `cora_neural_v2`, `cora_neural_v2g2`, `cora_neural_v2g3`, `cora_neural_v2g4` and the two symbolic modules
`cora_neural_v1/ir.py` and `cora_neural_v1/space.py` (the typed rule language; no learned component), plus
`cora_only.py`. The sealed `geocat_arc` is byte-identical to the repository's (141 of 141 files), which the typed
packages were tested against.

## Terms

- **ARC-AGI-2 task:** a few demonstration input-output grid pairs and one or more test inputs; a prediction is
  correct only if it equals the hidden output exactly. **pass@2:** either of two submitted attempts is correct.
- **Native CORA v23:** CORA's original solver (sealed in August 2026): a fifteen-layer reasoning pipeline, a geocat
  layer and an object layer that segments grids into objects (seven segmentation views) and induces executable
  object programs.
- **Certificate (leave-one-out):** the object layer re-induces its program with each demonstration held out in turn;
  a task is certified only if every such fold reproduces the held-out demonstration exactly.
- **ncv2-g2, ncv2-g3, ncv2-g4:** the second, third and fourth grammars of typed Neural-CORA, CORA's typed relational
  program language over the same native semantics (every typed program compiles to a native program). ncv2-g2 adds
  native reduction and generative program classes and a completed candidate generator; ncv2-g3 adds joint
  selector-action construction from per-object execution differences and evidence-aware selection; ncv2-g4 adds
  rules over parts of objects, regions and lines. No learned component is used here.
- **Phase 2a:** a frozen study of CORA's version-space reasoner on 40 public training tasks (19 October 2026).
- **The 60 development tasks:** 60 public ARC-AGI-2 training tasks used throughout CORA's development (exposed).

## Pipeline, per task

1. **Native CORA v23** (the NATIVE_BASELINE harness, run exactly as `kaggle/native_v1/notebook.py` runs it: the five
   sealed chain flags, the sealed assets, `--emit-predictions`, its own per-task budgets under a global budget). It
   records, per test input, its solving layer's render (attempt material 1, with the layer's name) and the object
   layer's best uncertified partial render (attempt material 2).
2. **ncv2-g3 search** (`cora_neural_v2g3.search.search`, which contains the ncv2-g2 stream and the native-class
   candidates): 3,000 candidate evaluations, a soft CPU cap of 120 s, every test input of the task at once. Each
   task runs in its own child process with a HARD CPU limit of 300 s (RLIMIT_CPU) and a wall-clock kill at 600 s, so
   no task can exceed its budget. Tasks without a native certificate are searched first. ncv2-g4 is an option
   (`search="g4"`), OFF in CORA-ONLY-G3.
3. **Attempts** (policy "precision"): for each test input, in order, the first two DISTINCT valid grids among
   1. `NATIVE_CERTIFIED`: native's render when it is the object layer's own render and the object layer certified
      the task: train-perfect AND leave-one-out-by-reinduction-perfect over at least 2 folds
      (`harness/object_layer.py`; a single demonstration gives no certificate). A research certificate;
   2. `NATIVE_CLAIMED_ON_CERTIFIED_TASK`: native's render when it comes from the pipeline or geocat layer (the harness
      keeps the FIRST solved layer's render: pipeline, geocat, then object) on a task the object layer certified. It
      is ranked high because two native layers explain the demonstrations, but it is never marked certified: the grid
      is not the object layer's;
   3. `G3_FIT_1`: ncv2-g3's first selected attempt (a program that reproduces every demonstration; exploratory);
   4. `NATIVE_CLAIMED`: any other native render (fits the demonstrations under that layer's own check);
   5. `G3_FIT_2`: ncv2-g3's second selected attempt;
   6. `NATIVE_PARTIAL`: native's best uncertified object partial;
   7. `FALLBACK`: the test input itself (a deterministic CORA-owned rule; never empty).
   If only one distinct grid exists, `attempt_2 = attempt_1`. The order follows the recorded precision of each
   source: object certificates 6 of 6 correct on the 60 development tasks (5 of 6 on Phase 2a's 40); ncv2-g2 fits 2
   of 4 correct on the 40-task real check; native whole-harness claims 11 of 29 correct on the 60 development tasks;
   uncertified train-perfect object programs 37 of 201 (the sealed July runs).
   *Revision note (21 October, before any scored evaluation):* the first draft labelled every object-layer render
   certified and every other render claimed. The offline fixture emulation (software verification only) showed that
   the harness keeps the first solved layer's render and that the object layer reports "solved" with 0 folds on a
   single demonstration; the labels above correct both.
4. **Records outside `submission.json`:** `attempt_provenance.json` (per task and test input: the source label of
   each attempt and whether it carries a certificate), `execution_manifest.json` (code tree hash, configuration,
   timings, counts), `run/progress.jsonl` (native rows) and `run/g3/<task>.json` (ncv2-g3 results).
5. **Validation:** every task id and every test position; both attempts always present; rectangular 1 to 30 x 1 to 30
   grids of integers 0 to 9; an invalid entry is replaced by the fallback; the task order of the input file.

## Budgets on Kaggle (4 CPUs, 12 h limit)

Native: global budget 6 h (its governor lowers per-task budgets only when the clock is short; on the 240 stand-in
tasks of the test file it needed 4.03 h). ncv2-g3: 4 parallel children; it stops starting tasks at 11.3 h from the
start; a task it does not reach keeps its native attempts. `submission.json` is always written.

## Pre-written development changes (to be tried, at most three, only if the base configuration scores 0 on the
public evaluation set; each is recorded with its result)

- **C1, search reach:** ncv2-g3 at 10,000 candidates, soft CPU cap 300 s, hard 600 s.
- **C2, representation:** ncv2-g4 search (`cora_neural_v2g4.search.search`: inversion, part, region and ray
  construction, the geometry tier, then ncv2-g3) at 3,000 candidates, soft cap 120 s, hard 300 s.
- **C3, attempt policy "search_first":** the order NATIVE_CERTIFIED, NATIVE_CLAIMED_ON_CERTIFIED_TASK, G3_FIT_1,
  G3_FIT_2, NATIVE_CLAIMED, NATIVE_PARTIAL, FALLBACK (computed from the same run).

## Evidence categories (never mixed)

Software verification (tests); synthetic engineering results; exposed real-task development results (the public
evaluation set is public and has been used in development before, so its score is "exposed public evaluation,
development evidence, not a competition score"); the official Kaggle public score (only after an authorized
submission); unresolved hypotheses.
