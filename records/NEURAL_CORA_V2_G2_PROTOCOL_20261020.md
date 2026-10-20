# Neural-CORA v2: G2 protocol, the language-ceiling check on dev60 (20 October 2026)

**Status: FROZEN** in the commit that adds this file and `records/NEURAL_CORA_V2_G2_FREEZE_MANIFEST.json`.
**No G2 measurement has been made. The scored run needs the user's explicit authorization.**

Runner: `scripts/neural_cora_v2_g2.py`. Its `solve` and `diag` stages refuse to run unless:
- this file and the manifest are committed unchanged;
- every code and input hash still matches the manifest;
- `--authorized` is given.

## 1. Question

Does the typed relational AST ncv2-g1 raise what CORA can fit and answer on real ARC tasks, compared with v1's
ncv1-g0, under the same kind of symbolic search? If not, what is missing?

This is the directive's ceiling test: "If no 1/60 improvement, don't proceed to larger training." It is
**engineering evidence about expressivity, not a benchmark**.

## 2. What is known before the run

**g0** (rows `outputs/neural_cora_v1/atlas/dev60_solve.jsonl`, sha256 `dba8c99d…`). C+H@3000 over ncv1-g0:
- 1/60 fits;
- 1/60 correct coverage;
- 1/60 pass@2.

All 60 dev60 tasks keep the input's shape (the atlas profile finds no size change). So g1's size-changing renders
(crop, constant shape) cannot help on dev60. **G2 on dev60 measures same-shape expressivity only.** Size changes
need a separate, predeclared cohort.

**Native CORA v23** (rows `outputs/funnel_v0/rows_dev60_native.jsonl` sha256 `db874c54…`; evaluation
`eval_dev60_native.json` `3fb8c0e3…`; run 13–14 October):
- a demonstration-fitting program on 35/60;
- a correct candidate on 8;
- certified and correct on 6.

Of the 35 fits:
- 30 came from ObjectProgram or ComposedProgram, the classes ncv2-g1 compiles to;
- 3 from ReductionProgram;
- 2 from GenerativeProgram.

These counts are read from the rows' search events, which hold no answers.

**What this says, and what is uncertain:**
- The 1/60 measures ncv1-g0 plus C+H. It does not measure CORA's interpreter. The same native object layer fits
  far more.
- Native's search is much larger than either language arm's:
  - a 90-second cooperative budget per frame, over 8 dihedral frames;
  - per-object parameter induction;
  - grow modes and synthesized copies, which g1 does not expose.
- Native is therefore a **reference row**. It is neither a matched arm nor an upper bound for g1.
- **Unknown:** how many of native's 30 object-layer fits need constructs that g1 does not expose, or parameter
  values that g1's candidate generator never proposes. Native saved only its 6 certified programs, so this cannot
  be read off. G2 measures g1 directly.

## 3. Data and arms

**dev60:**
- the 60 authorized pilot development tasks, `records/pilot_v1/dev_bundle.json` (sha256 `6eb73236…`), under opaque
  keys;
- exposed in earlier development (claim ledger rows 1–5 and 11);
- the v2 design (search candidates and order) was written after the g0 atlas summary.

A g1 gain is therefore not a generalization claim.

**Tasks** are loaded by `cora_funnel.run.load`, which strips answers. Only the first test input is used, as in the
g0 atlas.

| arm | what runs | budget |
|---|---|---|
| **g1** (new) | `cora_neural_v2.search.search`: the G1-CH symbolic, pairing-aware order over ncv2-g1; compiled and executed by the unchanged native interpreter | 3000 candidates; capped at 120 process-CPU seconds per task (setup included), any truncation recorded |
| **g0** | the hash-pinned v1 atlas rows, reused, not rerun | 3000 candidates |
| **native** | the hash-pinned native rows and evaluation, reused, not rerun | native defaults (CPU clock) |

No arm has a learned component.

## 4. Measures: coverage first, then score

All measures use the first test input.

1. **fits**: at least one program is consistent with every demonstration within the budget.
2. **correct coverage**: some kept consistent prediction equals the test output. Up to 50 distinct predictions
   are kept.
3. **pass@2**: one of the first two distinct consistent predictions equals the test output.

Also reported:
- *fits but no correct candidate*, i.e. underdetermination;
- CPU truncations, candidates evaluated and CPU seconds;
- a per-kind table over the g0 atlas's demonstration-derived profiles;
- paired g1-vs-g0 gains and losses for each measure, with the exact one-sided sign-test p. The p is
  **descriptive only**, because dev60 is exposed.

## 5. Decision rules (frozen)

**G2a, the precondition**, was measured at freeze time and recorded in the manifest:
- the parity suite `tests/test_neural_cora_v2_ast.py` and the search suite `tests/test_neural_cora_v2_search.py`
  pass;
- native CORA's aggregate sha256 equals the v1 freeze manifest.

If G2a fails, there is no run.

**G2b**, on g1 against g0's 1/60, evaluated in this order:

| decision | condition | what follows |
|---|---|---|
| **NO_GO_STOP** | g1 pass@2 ≤ 1 | No training and no G1b. Record the expressivity gaps only. |
| **GO** | all of: g1 fits ≥ 6/60; g1 pass@2 ≥ 4/60; paired pass@2 gains vs g0 ≥ 3; losses ≤ 1 | Licenses **only** writing and freezing a G1b protocol for separate authorization: Stage A of the joint guide, trained on synthetic v2 programs (`records/NEURAL_CORA_V2_QWEN_JOINT_PROGRAM_ADAPTER_DESIGN.md`) |
| **WEAK_EXPRESSIVITY_ONLY** | anything else | Language and search work only. No learned-guide training. |

Whatever the outcome:
- no poster claim (the 21 October print freeze stands);
- no competition claim;
- no Kaggle submission.

## 6. Diagnostics (solver side, after the solve stage)

**The exhaustive single-rule check** (`search.exhaustive_single_rule`):
- **which tasks:** at most 20 of g1's no-fit tasks, chosen in sha256(key) order. The choice reads no answers.
- **what it enumerates:** every program in the bounded g1 single-rule space, with no order and no budget. That is,
  each distinct view × live selector × candidate action × default × allowed render, plus the zero-rule programs.
- **cap:** 300 process-CPU seconds per task. The loop is render-major, cheapest render first, so a capped run has
  covered whole renders. The fraction checked is reported.

**Verdicts:**
- **SINGLE_RULE_EXISTS:** the budgeted search missed it. This is an ordering or budget problem.
- **NO_SINGLE_RULE:** the single-rule space cannot fit the demonstrations. This says nothing about multi-rule
  programs.
- **INCONCLUSIVE:** the cap was hit.

Also reported: g1's first-failing-demonstration counts and its diagnosis labels.

## 7. Resources and stop rules

**Hardware:** CPU only; the GPU is not used. 2 workers at nice 10. Athe's load is 23–55; Step B is not touched.

**Worst case:** solve, 60 × 120 s = 2.0 CPU-hours; diagnostics, 20 × 300 s = 1.7 CPU-hours; **at most 3.7
CPU-hours**. The expected cost is lower.

**One scored run.** `score` is the only stage that reads answers, through the sha-pinned evaluator
`cora_funnel.evaluate.answers("dev60")`. Its first output is the G2 result.

Any later run with changed code, candidates, order or settings:
- needs a new protocol version;
- is labelled post hoc;
- never replaces this result.

If more than 5 tasks raise exceptions in a stage, stop and report, with no silent reruns.

## 8. Not done

- No change to native CORA or its verifier.
- No evaluator-side renderer.
- No answers before `score`.
- No v1 held-out pool (395).
- No protected or sealed split.
- No NVARC synthetic data.
- No poster change.

## 9. Reporting

`records/NEURAL_CORA_V2_G2_REPORT.md` is written after `score`, whatever the outcome. It contains:
- the arms table, the paired table and the per-kind table;
- the diagnostics;
- the frozen decision;
- what the result does **not** show.

## 10. Commands

```
python scripts/neural_cora_v2_g2.py freeze                  # G2a tests + manifest (done at freeze)
python scripts/neural_cora_v2_g2.py selftest --out <dir>    # synthetic only (done at freeze)
python scripts/neural_cora_v2_g2.py solve --authorized      # AFTER authorization
python scripts/neural_cora_v2_g2.py diag --authorized
python scripts/neural_cora_v2_g2.py score
```

The outputs go to `outputs/neural_cora_v2/g2/`: `dev60_g1_solve.jsonl`, `dev60_g1_diag.jsonl`, `g2_score.json` and
the run manifests, each holding the git HEAD and the manifest sha256.
