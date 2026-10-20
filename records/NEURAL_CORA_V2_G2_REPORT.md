# Neural-CORA v2: G2 report — FINAL: NO_GO_STOP (20 October 2026)

**The frozen decision (protocol `records/NEURAL_CORA_V2_G2_PROTOCOL_20261020.md`, commit `3677d0f`):
`NO_GO_STOP`.**

ncv2-g1, under its symbolic G1-CH search, gets **1/60 pass@2**: the same single task as the v1 language, with 0
gains and 0 losses. By the frozen rule there is **no new neural training**. The G1b/G1c studies in
`records/NEURAL_CORA_V2_CONTROLS_AND_GO_GATES.md` are **not opened**.

**What dev60 is:** 60 **exposed** ARC-AGI-2 public training tasks. They are contaminated for Qwen-derived features
(no Qwen was used here). This is engineering evidence about expressivity, not unseen validation.

## 1. The run

| item | value |
|---|---|
| authorization | the user's message "authorize G2" (20 October), one run |
| commit at start | `86bab95`; freeze manifest sha256 `aee7f1ff…` |
| lock | verified at the start of `solve` and of `diag` (protocol and manifest committed unchanged; code, input and native hashes as frozen) |
| driver | one detached `sh` driver (PID 836449): `solve --authorized` → `diag --authorized` → `score` → the pre-registered forensic step |
| logs | `outputs/neural_cora_v2/g2/{run.status, run.log, score.log, forensic.log}`; `run.status` shows `STARTED 2026-10-20T14:18:37Z`, `EXIT 0 2026-10-20T14:40:54Z` |
| resources | CPU only, 2 workers at nice 10, no GPU; Step B and other projects untouched |
| CPU | solve 205.6 CPU-s (per task: median 2.9, max 11.1); diagnostics 2,191.2 CPU-s; **total 2,396.8 CPU-s (0.67 CPU-hours, against a cap of 3.7)** |
| integrity | 0 exceptions; 0 CPU truncations (every task evaluated all 3,000 candidates); 0 test-input rejections |

## 2. Results: coverage first, then score (first test input)

| arm | demonstration-fitting tasks | correct candidate coverage | pass@2 | fits with no correct candidate |
|---|---|---|---|---|
| **g1** (ncv2-g1, G1-CH @3000) | **1** | **1** | **1** | 0 |
| g0 (ncv1-g0, C+H @3000; reused rows) | 1 | 1 | 1 | 0 |
| native CORA v23 (reused rows; reference) | 35 | 8 | certified correct 6 | — |

**Paired, g1 vs g0:** fits 0 gains / 0 losses; correct coverage 0 / 0; pass@2 0 / 0 (sign test p = 1.0, descriptive).

**The one task:**
- `k553a7e98f13d`, a recolouring task. g0 solves it, and native certifies it.
- g1's attempt 1, at candidate 21, is `(program S1 (list (rule (test color == 6) (recolor (color 2))) (rule (true) (keep))) keep (same_as_input))`.
  It is correct. Its second rule is redundant.
- Attempt 2, at candidate 1,853, adds `(scale (int 2))` as the second rule.
- The programs were reconstructed post hoc by deterministic replay, with no answers
  (`scripts/neural_cora_v2_g2_replay_programs.py`).

**By demonstration-derived profile:**

| profile | tasks | g0 fits | g1 fits | g1 pass@2 | native fits |
|---|---|---|---|---|---|
| adds cells | 38 | 0 | 0 | 0 | 24 |
| object count changes | 48 | 0 | 0 | 0 | 28 |
| removes cells | 14 | 0 | 0 | 0 | 3 |
| recolours cells | 30 | 1 | 1 | 1 | 12 |

## 3. Diagnostics: search miss vs bounded single-rule gap

The exhaustive single-rule check ran on the 20 g1 no-fit tasks chosen by sha256 order, at 300 CPU-s each:

| verdict | tasks | meaning |
|---|---|---|
| SINGLE_RULE_EXISTS | **0** | no single-rule search misses |
| NO_SINGLE_RULE (complete) | **16** | no single-rule program **in g1's candidate space** fits; spaces of 19,242 to 464,840 programs, all checked |
| INCONCLUSIVE (cap hit) | 4 | fractions checked: 0.50, 0.86, 0.28, 0.03 |

**The exact scope, which matters:**
- The check enumerates the **search's candidate space**: the selectors and actions that `search.selectors` and
  `search.actions` derive from the demonstrations. That is smaller than the ncv2-g1 language.
- "NO_SINGLE_RULE" is therefore not a proof that no single-rule ncv2-g1 program exists.
- It says nothing about multi-rule programs, which remain **unknown**.

**The pre-registered forensic step** (`outputs/neural_cora_v2/g2/g2_forensic.json`):
- single-rule correct reach: 0, since there were no SINGLE_RULE_EXISTS tasks;
- tasks with wrong attempts: 0;
- tasks that fit but have no correct candidate: 0.

## 4. Post-hoc analysis (labelled; answer-free; it does not change the decision)

**Where native's certified answers come from.** Native's six certified programs on dev60
(`outputs/funnel_v0/engine_dev60_native/certificates/`):

| task | native program | in ncv2-g1? | g1 result |
|---|---|---|---|
| k553a7e98f13d | object, S2: recolor by `feature_map` | yes | **solved** (another program) |
| kc8866e481747 | object, S1: `(rule (test is_line == #f) (recolor (color_of (nearest (test is_line == #t)))))` | **yes: compiled from ncv2-g1, it fits every demonstration** | no fit: **neither the negated boolean selector nor a feature-keyed `nearest` is in G1-CH's candidate set** |
| k328b173af636 | reduction: symmetry completion (d4) | no (program class not exposed) | no fit |
| kf105d51e18c5 | reduction: neighbour count | no | no fit |
| k68319709c614 | generative | no | no fit (diagnostic: NO_SINGLE_RULE) |
| k781e60eda1b3 | generative | no | no fit (diagnostic: NO_SINGLE_RULE) |

**So the G2 failure has three separable causes:**
1. **Unexposed native program classes** (reduction, generative): 4 of native's 6 certified answers.
2. **The search's candidate space**: an expressible single-rule program with relational, feature-keyed parameters is
   never proposed (`kc8866e481747`).
3. **Unknown**: multi-rule programs, and native's 30 object-layer fits, whose programs native did not save.

## 5. What this does and does not show

**It shows:**
- On these exposed tasks, the larger typed language plus its current symbolic candidate generator reaches no task
  that the v1 language did not.
- Coverage, not ordering, is the binding constraint.
- A learned guide over this candidate space cannot help yet: there is nothing more to order.

**It does not show:**
- that ncv2-g1 cannot express these tasks (kc8866e481747 shows it can express at least one that the search misses);
- anything about multi-rule programs, learned proposers, revision, or unseen tasks.

## 6. The single next step (proposal only; it needs a new grammar version, its own frozen protocol and authorization)

**One versioned increment, ncv2-g2: "reach what native already certifies".**
1. Expose native's ReductionProgram (symmetry completion, neighbour count / pixel rules, counting) and
   GenerativeProgram as typed program forms. They compile to native dicts and are parity-tested by re-executing
   native's own certified programs and synthetic cases.
2. Complete the candidate generator systematically over the constructs already exposed, so that it covers both
   polarities of every boolean feature and references keyed by those features. This adds no new semantics and no
   task-specific primitive.

**Measurement:** first on held-out synthetic families, then on a fresh eligible cohort (needs authorization). dev60
is never used again as evidence.

**Honest ceiling:** even full parity with native gives native's own reach (6/60 certified on these exposed tasks;
0.00% hidden). The increment is necessary before any learned proposer, not sufficient for competitiveness.

## 7. Output hashes (sha256, first 16 hex characters)

| file | sha256 |
|---|---|
| `dev60_g1_solve.jsonl` | `1acdd7822a2b9cfd` |
| `dev60_g1_diag.jsonl` | `0ec49d1a003e7f30` |
| `g2_score.json` | `007863d28de6190a` |
| `g2_forensic.json` | `6198ed6bc7027b29` |
| `g2_attempt_programs.json` (post hoc) | `31acd192d2e492a9` |
| `run_manifest_solve.json` | `a9dea6259e08fb24` |
| `run_manifest_diag.json` | `f96d85af78ce2bdf` |

All files are in `outputs/neural_cora_v2/g2/` (local, not in the repository).
