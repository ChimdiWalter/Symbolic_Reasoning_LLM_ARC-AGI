# Neural-CORA v2: joint sketches, one task state, the Qwen interface, and feedback actions (specification, 20 October 2026)

**Status:** a specification. Each element is labelled with one of:
- **EXISTING CODE** (with its file);
- **TO IMPLEMENT**;
- **TESTED BENEFIT** (none yet);
- **NOT ESTABLISHED**.

Nothing here is trained. The full loop is not implemented.

## 1. The loop, labelled box by box

| box or arrow | status | where |
|---|---|---|
| demonstrations + unlabeled query → task state | EXISTING CODE (partial state) | `cora_neural_v2.constraints.evidence`, `search.distinct_views`, the `search.search` record |
| C+H-style symbolic proposal and pruning, always available | EXISTING CODE: G1-CH order, sound prunes P1–P2, Occam firing filter | `cora_neural_v2/search.py`, `constraints.py` |
| Qwen knowledge adapted on visible examples → typed sketches with holes and bindings | TO IMPLEMENT (§4). Holes and bindings exist in the AST | `rast.py` (`hole`, `rule_with`) |
| optional neural perception or parameter proposals | TO IMPLEMENT (§4.2) | — |
| one agenda of typed executable hypotheses, not two answer lanes | PARTIAL: one best-first agenda over whole rules; neural entries TO IMPLEMENT | `search.enumerate_programs` (`rule_scores` hook) |
| constraint propagation / partial evaluation | PARTIAL: P1 and P2; early stop at the first failing demonstration. Partial evaluation of sketches TO IMPLEMENT | `constraints.sound_prunes`, `bridge.fit` |
| native CORA interpreter | EXISTING CODE, unchanged, with parity (`records/NEURAL_CORA_G2_NATIVE_COVERAGE_INVENTORY.md`) | `bridge.execute` → `render_program` |
| mismatches, competing explanations, lack of fit, cost | PARTIAL: the first failing demonstration, NO_FIT / AMBIGUOUS / REJECTED labels, CPU. Mismatch cells, fold fragility and representation sensitivity TO IMPLEMENT | `search.search` `state` |
| a bounded revision decision with a rationale | TO IMPLEMENT (§5) | — |
| execute the revision; update the state | TO IMPLEMENT | — |
| calibrated selection of 2 distinct outputs | PARTIAL: the first two distinct consistent predictions. Calibration TO IMPLEMENT | `search.search` |
| blind scoring after predictions freeze | EXISTING CODE | `cora_funnel.evaluate.answers`, the G2 `score` stage |
| any learned component's benefit | **NOT ESTABLISHED** (v1 G1 NO-GO) | `records/NEURAL_CORA_V1_PILOT_REPORT.md` |

## 2. One CORA task state

One record per task. Every proposer, the checker and the controller read and write it, and it is logged per step.

| field | content | status |
|---|---|---|
| `demos`, `queries` | demonstration pairs; test inputs (all of them, not only the first) | EXISTING (first test input only); all inputs TO IMPLEMENT |
| `views` | exact-equivalence classes of the 7 native views | EXISTING |
| `objects[view][grid]` | native objects, the 36 features, relations | EXISTING (native) |
| `evidence` | matched-object correspondences: recolour pairs, displacements, deletions, copy offsets, lines, shape change | EXISTING (`constraints.evidence`) |
| `constraints` | provable prunes (P1, P2); learned-from-failure constraints, each with a proof obligation (§5.3) | P1 and P2 EXISTING; the rest TO IMPLEMENT |
| `agenda` | scored typed hypotheses (whole programs or sketches), each with provenance (symbolic, neural, revision) | TO IMPLEMENT (today it is a heap of symbolic programs) |
| `version_space` | consistent programs grouped by their test prediction | PARTIAL (distinct predictions and positions) |
| `traces` | per candidate: the failing demonstration, mismatch cells split into missing / extra / wrong-colour, the object each mismatch belongs to, EvalErrors | PARTIAL (failing demonstration only) |
| `uncertainty` | the number of distinct predictions; leave-one-out (LOO) fragility; view sensitivity | TO IMPLEMENT |
| `library` | typed macros with provenance | EXISTING (`macros.py`, researcher macros) |
| `budget` | candidates, CPU-s, GPU-s, wall-clock; charged per proposer | PARTIAL (candidates, CPU) |

## 3. Typed sketches

**A sketch is an ncv2-g1 program containing `(hole TYPE)` nodes.**
- It typechecks but never compiles (EXISTING, tested).
- **Bindings:** `rule_with ((?t REF) …)` names an object reference once and uses it several times. It compiles by
  substitution (EXISTING).

**Completion** (TO IMPLEMENT): fill each hole by enumeration from the same candidate generators the symbolic search
uses (`search.selectors` and `search.actions`, filtered by the hole's type):
- in C+H order;
- under the sketch's constraints;
- stopping at the first fit per hole assignment, budget-charged.

**Equivalence:**
- views are collapsed exactly (EXISTING);
- programs are deduplicated by their outputs on the demonstrations **and** the test input (TO IMPLEMENT).
- Demonstration-equal, test-different programs are kept as the pass@2 pair.

## 4. The Qwen interface (two low-cost options; neither implemented)

**Verified prerequisite:** one token per grid cell (`records/NEURAL_CORA_V2_LICENSE_AND_PRETRAINING_AUDIT.md` §2).
Object pooling is exact. The model is causal, so the slot context must be chosen: test-input slots, or a re-read
segment.

### 4.1 N2-A: a joint structured head over frozen Qwen states (first)

**Inputs:**
- **Qwen object slots:** token states from 2–3 layers, pooled over each object's cells.
- **Relation and correspondence tokens** from `evidence`.
- **C+H features**, kept as inputs.

**Model** (about 5–10 M parameters):
- cross-attention from a small decoder to the slots;
- the decoder emits either:
  1. a score for each whole candidate rule, conditioned on earlier rules (the residual of
     `records/NEURAL_CORA_V2_CONTROLS_AND_GO_GATES.md`); or
  2. an autoregressive sketch, constrained so that only grammar-valid continuations are allowed. The automaton is
     derived from `rast.SIGNATURES`, and holes are allowed at any typed position.

**Combination with C+H:** `score(h) = C+H(h) + r_theta(h, state) − cost(h)`, with r_theta calibrated on permitted
train/validation episodes only.

**Training:** CORA's own execution-verified ncv2-g1 generator, split by semantic family before augmentation.
- **Positives:** the rules of every demonstration-fitting program, grouped by execution equivalence.
- **Hard negatives:** swapped selector–action pairings, wrong order, near-miss parameters, and superficial cues that
  mislead.

**The causal question it answers:** do Qwen slots add pairing and binding information beyond the hand features and
C+H? That is arms 2–3 of the controls record.

### 4.2 N2-B: neural-to-symbolic decompilation (second, only if N2-A shows value)

1. The checkpoint decodes candidate output grids. It may adapt test-time on the visible demonstrations only, with
   fold-local re-adaptation for any LOO claim.
2. Each candidate grid is **untrusted evidence**. Its diff against the test input yields edit regions, implied
   object correspondences, colour pairs and displacement vectors.
3. These become **sketch constraints or hole proposals**, e.g. "objects in this region are recoloured", "one object
   moves by (0, 3)".
4. CORA fills the sketch and keeps only programs that fit **every demonstration**. The final output is always the
   output of a CORA-executed program.

**Guards against a disguised second solver** (all required, all reported):
- **No fallback.** If no CORA program fits, the system uses its symbolic attempts or abstains. It never submits the
  neural grid.
- **Program dependence.** Replace the program with a shuffled one, or drop its rules: the output must change.
  Otherwise the program carries no information.
- **The neural evidence withheld.** Rerun with the neural grids removed and report both solved sets. Gains are
  attributed only to tasks where the program, not the grid, generalizes across demonstrations (it passes LOO).
- **A rationalization check.** Flag a program that reproduces the neural grid through test-specific constants not
  supported by any demonstration. Check by description length and LOO.
- **Separate reporting.** Neural-assisted selections or proposals are reported apart from purely symbolic ones, and
  results are always labelled as NVARC-model-assisted.

### 4.3 If symbolic coverage remains the blocker (proposal only)

A typed, program-conditioned neural operator: an object-correspondence, mask, part or parameter-field predictor
called from inside a CORA program.
- The interpreter controls its input and output types, context, constraints, budget and tracing.
- Its output must change when the controlling program or constraints change.
- It is compared with an unconditioned Qwen grid generator to expose a disguised answer wrapper.
- It is reported as **neural-assisted**, never as certified.

## 5. Feedback that becomes an action

### 5.1 Observable facts

All of these come from visible demonstrations only:
- which demonstration fails, and which cells (missing, extra, wrong colour);
- which objects the mismatched cells belong to;
- whether a matching conflicts;
- whether a hole has no admissible fill;
- whether two fitting programs disagree on the query;
- whether a LOO fold is fragile;
- how much budget remains.

### 5.2 Actions

Each action is a concrete AST or search edit, followed by re-execution on every demonstration.

| action | trigger | the edit |
|---|---|---|
| REPARSE | mismatches inside multicolour or touching objects | switch the view (e.g. S1 → S3) |
| REBIND | the right action, the wrong target | swap the REF (nearest ↔ unique ↔ container …) |
| FILL / REVISE HOLE | a hole with candidate fills | enumerate under constraints |
| ADD GUARD | over-application: a selected object should have stayed unchanged | conjoin a feature test that separates changed from unchanged selected objects on the demonstrations |
| REMOVE GUARD | under-application | drop one conjunct |
| CHANGE PARAMETER | right objects, wrong colour or vector | induce the parameter from the mismatched cells (e.g. a `color_map` from observed pairs) |
| TARGETED SEARCH | the facts point at one slot | spend budget on that slot only |
| KEEP ALTERNATIVES | two fits disagree on the query | keep both as the 2 attempts |
| ABSTAIN | no admissible edit | output the best symbolic attempts, labelled |

**A worked example (TO IMPLEMENT):**
1. `(rule (test color == 1) (recolor (color 4)))` fails demonstration 2: one blue object of size 3 should have
   stayed blue.
2. On the demonstrations, the recoloured blue objects all have size 1 and the unchanged one has size 3.
3. The edit is `(rule (and (test color == 1) (test size == 1)) (recolor (color 4)))`.
4. Re-execute on every demonstration; keep it only if it fits all of them.

This is counterexample-guided repair with a **lawful** counterexample: a visible demonstration, never the query
target.

### 5.3 Constraints learned from failure (Popper-style)

A constraint enters the pruning set only with a written proof that it removes no program fitting the demonstrations,
plus a zero-false-prune test on known synthetic solutions. First-match rule lists depend on order, so ILP soundness
does not transfer automatically. Constraints that are only plausible may **order** the agenda, never prune it.

### 5.4 The minimal closed-loop test (G3)

The controller passes only if it does all of the following:
1. chooses an action;
2. executes it;
3. observes the program's behaviour change;
4. is scored.

It is compared at matched compute against:
- a failure-blind controller with the same actions;
- shuffled traces;
- C+H-only repairs;
- try-all-actions.

A wrong certificate counts as an error.

## 6. Security and integrity

- No eval and no generated Python. Neural output is parsed token by token through the grammar automaton; invalid
  tokens are masked.
- Only the native interpreter executes. Each execution is CPU-capped, and the search has a total cap
  (`search.search(..., cpu_cap_s)`).
- Hidden or test outputs are never read in solve stages. The evaluator is a separate stage, sha-pinned
  (`cora_funnel.evaluate`).
- Every scored run sits behind a committed protocol and manifest lock, as with the G2 runner.
- Proposed: a hash log of every file the solver opens, to prove that test outputs are never read.
