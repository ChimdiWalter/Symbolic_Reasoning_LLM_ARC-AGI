# Neural-CORA: the single reasoner, as specified and as implemented (v1, 19 October 2026)

**One inference algorithm, owned by CORA.**
- CORA holds the task representation, the typed hypothesis state, the program language, the interpreter, the
  diagnostic record, the search controller, the acceptance rule, the budget and the final two attempts.
- A frozen Qwen3-4B model supplies learned features. Trainable heads turn those features into distributions over
  CORA's own typed components.
- There is no second answer producer: no NVARC lane, router, ensemble or second-attempt filler. The neural network
  never emits a grid.

## 1. The reasoning state S_t = (D, R_t, H_t, K_t, F_t, U_t, B_t)

| part | meaning | v1 implementation |
|---|---|---|
| D | the demonstrations and the query input; never the query target | `task["train"]`, `task["test_inputs"]` (`corpus/*_public.jsonl`) |
| R_t | candidate object decompositions and their evidence | the 7 native segmentation views (`ir.VARIANTS`); `ReasoningState.views` counts the views of consistent hypotheses. No part or relational decomposition yet |
| H_t | the version set of typed executable hypotheses, with provenance | each consistent hypothesis's test prediction and its first order position (`pred_at`), plus the first two programs (`attempt_programs`) with order position and score |
| K_t | the typed operation vocabulary and its provenance | `ncv1-g0`: 31 selectors and 92 actions, all native primitives (`ir.SELECTORS`, `ir.ACTIONS`), pruned per task from the demonstrations (`space.domains`). No language extension in v1 |
| F_t | inference-available execution feedback | for each rejected candidate: the first failing demonstration and how it failed (wrong cells, or no output / size change) (`ReasoningState.fail_demo`, `fail_kind`) |
| U_t | disagreement, fragility, limits and honest uncertainty | the diagnoses NO_FIT_OBSERVED, AMBIGUOUS_PREDICTIONS, UNVERIFIED_QUERY, PROGRAM_REJECTED and TIMEOUT_OR_ERROR (`state.py`). FOLD_FRAGILITY is not computed by the v1 search (CORA-v2 computes it) |
| B_t | the budget and the revision history | candidate budget, candidates spent, CPU seconds; the revision history is empty, because v1 executes no revisions |

The state is updated after **every** candidate execution (`search.search_typed` → `ReasoningState.observe`) and is
written to each task's row (`arms.<arm>.state`).

## 2. The policies

- **q_theta (proposal guide), implemented and trained in the v1 pilot.**
  - `prior.build_heads`: an MLP of 12,800 → 1024 → 512 with five heads (view, number of rules, default, selector bag,
    action bag). It reads frozen Qwen3-4B features (`prior.QwenEncoder.features`).
  - Its log-probabilities become CORA's best-first order (`space.enumerate_programs`).
  - Training: `prior.train_heads`, with extensional, alias-grouped targets from demonstrations only.
  - Controls:
    - L0: untrained;
    - L0s: shuffled targets;
    - L1h: hand features;
    - C+ and C+H: symbolic orders.
- **pi_phi (revision-action policy), not implemented.**
  - It is gated on G1.
  - The permitted actions would be REVISE_OBJECTS, REVISE_PARTS_OR_RELATIONS, REVISE_PROGRAM, REVISE_GUARD,
    REVISE_COLOUR_RULE, ALLOCATE_MORE_SEARCH, KEEP_ALTERNATIVES and ABSTAIN.
  - Each must execute a change and produce traceable feedback.
  - The earlier hand-designed controller (`cora_fhr/revision_controller.py`) was negative: claim ledger row 12e.

## 3. The target diagram, arrow by arrow

An arrow is IMPLEMENTED only if it has a callable function, a test and a measured output.

| arrow | status | function | test | measured output |
|---|---|---|---|---|
| ARC pairs + query → CORA typed state | IMPLEMENTED | `space.domains`, `state.ReasoningState` | `test_reasoning_state_and_diagnoses` | `rows/*.jsonl` `state` |
| state → Qwen feature encoder | IMPLEMENTED (frozen) | `prior.QwenEncoder.features` | encoder probe (finite, 37 layers) | `manifest.json` `features_qwen` (GPU s, tokens, peak memory) |
| encoder → learned proposal guide | IMPLEMENTED, TRAINED in this pilot | `prior.train_heads`, `prior.head_scores` | `test_training_changes_weights_and_logs_steps` | `models/training_log.json` (steps, gradient norms, weight hashes) |
| guide → type-checked hypotheses | IMPLEMENTED | `space.enumerate_programs`, `ir.Hypothesis` type asserts | `test_enumeration_is_best_first_unique_and_valid` | `n_candidates` |
| hypotheses → CORA interpreter | IMPLEMENTED | `interp.run` → native `render_program` | `test_*_full_grid`, `test_purity_and_restoration` | `executions` |
| interpreter → observable fit / conflict / budget | IMPLEMENTED | `interp.fit`, `ReasoningState` | `test_reasoning_state_and_diagnoses` | `state.diagnoses` |
| interpreter → fold fragility | NOT IN v1 (in CORA-v2) | — | — | — |
| observations → revision decision | NOT IMPLEMENTED | — | — | — |
| revision → bounded reversible change → state | NOT IMPLEMENTED in v1. CORA-FHR has reversible operator installation for growth operations | — | — | — |
| final hypotheses → frozen two-attempt rule | IMPLEMENTED | `search_typed`: first distinct, then the next distinct | `test_budget_truncation_is_exact` | `attempts` |
| attempts → blind independent scorer | IMPLEMENTED | `evaluate.py`, the only reader of the answers | `test_evaluator_statistics` | `evaluator/pilot_v1_eval.json` |

**So the v1 pilot tests one closed path.** It runs from the state through learned proposal, execution and the
observable fit check to selection, with blind scoring. It does not test diagnosis-driven revision.

## 4. Planned extensions (each separately gated)

- **Program-conditioned neural residual:** only if fixed-program expressivity and candidate coverage are independently
  shown to be the binding constraints. It would:
  - condition on actual typed programs and execution traces;
  - be ablated with shuffled or removed traces;
  - mark its outputs not executable-certified.

  Not in the first pilot.
- **7A:** a constrained typed-AST decoder.
- **7B:** an execution-feedback revision policy (pi_phi).
- **7C:** task-local adaptation of the guide, with fold-local re-adaptation.

These need G1 and the order in the roadmap (`records/NEURAL_CORA_V1_27P64_COMPETITION_ROADMAP.md`).

## 5. Fold-locality

**v1:** the guide is not adapted per task. Its weights are fixed after training on synthetic data, so a
leave-one-out fold check does not reuse any information from the withheld demonstration.

**Any later per-task adaptation** must be repeated without the withheld demonstration. Otherwise its checks are
labelled neural-assisted.
