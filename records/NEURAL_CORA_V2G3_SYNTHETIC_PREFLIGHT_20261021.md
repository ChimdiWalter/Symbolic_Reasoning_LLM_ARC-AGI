# syn-v3 study: read-only preflight audit (21 October 2026)

**Verdict: PASS, no defect found that affects validity.** The frozen study (protocol
`records/NEURAL_CORA_V2G3_SYNTHETIC_PROTOCOL_20261021.md`, freeze commit `f2a2ef4`) can run exactly as frozen once
the author authorizes it. Five limitations are documented below. None is repaired here, because a repair would need a
code or protocol change and therefore a new freeze. Nothing was run on HELDOUT tasks, and no source file was
modified.

## 1. Checks

| # | check | result |
|---|---|---|
| 1 | Git HEAD and working tree | `aedd82d` on master; clean apart from two untracked poster crops (not research files) |
| 2 | frozen files and hashes | no frozen file changed since `f2a2ef4`; the runner's lock passes (manifest sha256 `ca22174c…`, 23 code files, protocol `25e4e618…`) |
| 3 | not already run | no `outputs/neural_cora_v2g3/` directory |
| 4 | duplicate processes | none |
| 5 | resources | load about 27–33 on 24 cores; Step B alive (21 processes, 11 on CPU), not touched. The study's 2 workers at nice 10 are the footprint the earlier studies used |
| 6 | full test suite on the frozen code | **234 passed, 1 skipped** (pre-existing: "the shared scene generator never makes touching objects; covered by the parity tests"), 418 s, no source modified |
| 7 | answer separation | see section 2: answers never reach proposals, search, selection or stopping |
| 8 | the four missing tasks | see section 3 |
| 9 | coverage semantics | see section 4: retained-candidate coverage, not exhaustive generator coverage; the cap did not bind on DEV |
| 10 | the real-ARC reference-arm timeouts | preserved as reported (section 5) |

Also checked: regenerating the HELDOUT set now reproduces the freeze exactly (296 tasks, the same `tasks_sha256`, the
same missing list). Task content was not printed or inspected.

## 2. Answer separation (item 7)

- **Static:** the solve stage's `tasks()` calls `families_v3.make_task`, which computes each test answer and the
  task. The runner keeps only `train` and `test_inputs` (`t, _ = made`). `_job` passes the searches a dict with only
  `task_id`, `train` and `test_inputs`. No solver module (`cora_neural_v2*/search`, `joint`, `select`, `scene`,
  `delta`, `neural`, `revision`) imports the generator or reads an answer.
- **Dynamic:** one DEV task went through the frozen `_job` with `make_task` (both generators), `alternative`,
  `certify_alt` and `certify_trap` replaced by functions that raise if called. The worker finished. Each of its three
  searches read only `train` and `test_inputs`, never `task_id`, so the family name inside the task id never reaches
  the solver.
- **Limitation L1:** the runner's docstring says only the score stage regenerates answers. That is not literally
  accurate: solve-time task construction computes and discards them. To correct in the next version.
- **Limitation L2: task selection depends on answers, by design.** Trap tasks are kept only if a memorizer mispredicts
  the answer, and ambiguity tasks only if the alternative program disagrees with it; both are documented in protocol
  section 2. In addition, every pair, including the test pair, is regenerated until its output differs from its
  input. That non-identity filter is not stated in the protocol. Results are conditional on this construction.

## 3. The four missing tasks (item 8)

`v3h_trap_border_relational` seeds 3, 9, 11 and 20: no task passed the trap certification (a memorizer that fits the
demonstrations and mispredicts the test) within the generator's 25 regenerations. They are recorded as missing at
freeze and never replaced. The trap group therefore has 36 tasks (`v3h_trap_ring_most_common` 20,
`v3h_trap_border_relational` 16), and the trap gate's denominator is 36.

## 4. Coverage semantics (item 9)

- **Limitation L3:** the reported "correct-candidate coverage" is RETAINED-candidate coverage: whether a correct
  prediction is among the first 50 distinct fitting predictions each search keeps, in find order, within the budget.
  It is not exhaustive coverage of what the generator can produce, and it is not the structural generator coverage of
  the ncv2-g2 study. Selection, in contrast, ranks every fit, so in principle pass@2 could exceed retained coverage.
- **DEV measurement** at the frozen settings (21 DEV tasks, 3,000 candidates, 120 CPU-s):
  - at most 21 distinct readings, and 0 tasks above 50, for either arm;
  - 0 cases of pass@2 without retained coverage;
  - 0 attempts from outside the retained list.

  The cap did not bind.
- **Limitation L4:** the rows keep the retained predictions, not the total count of distinct readings.
- **Pre-specified post-run check** (descriptive, cannot change the decision): list the tasks whose search kept
  exactly 50 predictions (the cap may have bound), and any task where pass@2 is true while retained coverage is false.

## 5. The real-ARC reference-arm timeouts (item 10)

Unchanged: `records/NEURAL_CORA_V2G2_REALARC_REPORT_20261020.md` stands as frozen. NO_REAL_GAIN is the decision for
the error-free ncv2-g1 vs ncv2-g2 comparison. Native recorded `object_hard_timeout` (its 450 CPU-s cap) on 12 of 44
tasks; its numbers are lower bounds, and the stop rule's wording ("errors") is left for the author's judgement. Native
was not exhaustively evaluated.

## 6. Limitation L5: wall-clock components

Native inducers inside the candidate stream keep a wall-clock deadline (the generative inducer's 20 s), so machine
load can cut class candidates in both arms alike. Budgets and caps of the searches themselves are process CPU time.
