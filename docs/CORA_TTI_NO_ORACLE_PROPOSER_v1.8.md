# CORA-TTI Item-2 v1.8: the no-oracle extension proposer

Status: FROZEN at the commit named in
`outputs/tti/no_oracle_proposer_v18_manifest.json`. Written 2026-10-05.
- Starting HEAD 2299c95 (v1.7 COMPILER_ACCEPTED; v1.6
  PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES, LEVEL 1 hybrid).
- Design record `records/ITEM2_V18_PROPOSER_DESIGN.md` (d531141), written
  before any development measurement.
- Development record `records/ITEM2_V18_DEVELOPMENT_RESULT.md` (DEVELOPMENT
  ONLY).
- Nothing changes after the freeze except by a recorded erratum made before
  the prospective test runs. This block runs no prospective test and no
  real ARC experiment.

## 1. Question and hypothesis

Can CORA construct a useful executable semantic extension from its own
failure and its demonstrations, without being handed the target extension or
a correct candidate pair?

**No-oracle hypothesis.** On a task where the frozen reasoner K* fails,
K's own failure frontier on the training demonstrations (which of its blocks
explain part of the change consistently, and what they leave unexplained)
determines, by composition of K's own blocks, a small set of candidate
extensions. Among them the frozen selection hierarchy picks one which,
compiled by the v1.7 compiler and installed in the same reasoner, makes K*
solve the task, is necessary there, and survives leave-one-out with the
proposal rebuilt inside every fold. Replacing the task's own failure
frontier with another task's destroys this.

## 2. Input boundary

The proposer reads one closed object (`cora-proposer-input/1`):

| key | content |
|---|---|
| `format` | `cora-proposer-input/1` |
| `demonstrations` | the training demonstrations only, as integer grids |
| `failure` | `k_class` (K_EXACT, K_CONSISTENT_INEXACT or K_NO_CONSISTENT) and `frontier`: one row per K block in K's order, status FULL, PARTIAL or CONFLICT, the frozen fitter code for a conflict, and for FULL or PARTIAL the covered and changed counts, table entries and the residual cells |
| `grammar` | the frozen limits and vocabulary |
| `limits` | the frozen bounds of section 4 |
| `kstar_identity` | the v1.7 K* identity |

**Leakage scanner** (`scan_input`). Leakage is a blocking failure
(LEAKAGE_FAILURE). It refuses:
- any key outside the closed set, at any depth;
- any key containing target, seed, family, task, label, truth, digest,
  answer, solution, held, test, oracle, schema, token or candidate;
- any string outside the frozen vocabulary, statuses, codes, K classes,
  format and K* identity;
- any grid value outside 0 to 9 or any non-integer;
- any frontier row out of K order or with keys other than its status's.

The target AST, its digest and tokens, the generator seed, the family, the
correct candidate, the held-out pair and the task identity have no field.

## 3. Mechanism: residual peeling over K's own blocks

- **Semantics used.** Every block reads the input grid and only Paint
  writes; later layers overwrite earlier ones. The occurrence-scoped fitter
  (identity 2cc45152) requires the layers to explain the change jointly.
- **Frontier.** For each of K's 200 blocks (4 partitions x 5 predicates x
  10 features, one Select), the fitter's per-block rules on its own
  regions: a touched region changes entirely and to one colour, one colour
  per key, every key in at least two demonstrations, no hidden key, and an
  unchanged region keeps its colour if its key is in the table. A block
  that passes and covers only part of the change is PARTIAL, with its
  residual.
- **Depth 2.** Each PARTIAL block b is a candidate last layer. A K block a
  (a != b) is a candidate lower layer if on the cells b does not own it
  covers exactly b's residual and passes the same rules. Proposal: [a; b].
- **Depth 3**, only if no depth-2 proposal verifies. Top b3 as above; a
  middle block passes the rules outside b3's cells and covers a non-empty,
  incomplete part of b3's residual; a bottom block covers the rest exactly
  outside both. Proposal: [b1; b2; b3].
- Tops and residuals come from the input's frontier; lower layers are
  checked on the demonstrations. Only K's vocabulary and the grammar's own
  composition are used.

## 4. Frozen bounds

| bound | value |
|---|---|
| depths | 2, then 3 only if no 2-layer proposal verifies |
| Select stages per block | 1 |
| tops (depth 2) / lower layers per top | 32 / 16 |
| tops x middles (depth 3) / bottoms per middle | 8 x 8 / 16 |
| proposals per depth | 256 (PROPOSAL_LIMIT when reached without a verified proposal) |
| verified candidates probed | 32 |
| wall time per proposer call | 180 s (RESOURCE_EXHAUSTED) |
| order of tops | covered cells descending, table entries ascending, K index |
| order of lower layers | table entries ascending, K index; middles: covered descending, entries, K index |
| duplicate law | no block composed with itself; equal canonical text once; verified candidates with one probe fingerprint collapse to the first in MDL order |
| MDL order | total table entries, AST nodes, canonical text |

## 5. Output contract

Zero or more schemas, each a composition of 2 or 3 of K's blocks with one
free induced slot per block. Each one:
- satisfies the v1.7 compiler input law and types (checked for every
  proposal; a failure is UNTYPEABLE_PROPOSAL);
- has no literal table, answer or stored output (slots are free);
- contains no task-specific branch;
- is canonicalized by the compiler.

The proposer installs nothing.

## 6. Selection law

1. Verification: exact fit of the proposal on every training demonstration
   by the frozen fitter.
2. Duplicates: one probe fingerprint, one representative (MDL first).
3. P0, unchanged from v1.6: each representative's CandidateFailureResponse
   (v1.6 `probe`: K + {e}, leave-one-out re-derivation; LOO exact, cell
   error, fit failures, table entries); the unique P0-maximal candidate is
   chosen.
4. D, only on a P0 tie: v1.6's D, refit once by v1.6's own path and frozen
   (`outputs/tti/v18_frozen_d.json`, sha256 b0ae3eca; it reproduces all
   five v1.6 D and P0_then_D numbers exactly). D applies only if the tied
   candidates differ in key-feature tokens alone; a candidate scores the sum
   of D's logits at the differing positions, which for one position is
   exactly v1.6's decision.
5. MDL guess: when D does not apply or ties, the first candidate in MDL
   order. This level is new: v1.6 never had N-way ties outside D's domain.
   Every selection records its deciding level (VERIFICATION_UNIQUE, P0, D,
   MDL).

The PURE arm stops after P0 and abstains on a tie. The NO_RESPONSE arm
skips the probe (verification, duplicates, D, MDL).

## 7. Pipeline and provenance

failure evidence -> proposer -> verification and probe -> selection ->
v1.7 compiler -> temporary installation in K* -> rerun.

The compiler input's provenance carries the proposer's code sha256 and
the sha256 of the proposer input. The v1.7 compiler, K* and its environment
law are frozen infrastructure and are used unchanged.

## 8. Real S5: leave-one-out with the proposal inside every fold

For each training demonstration i:
1. remove demonstration i first;
2. rebuild the semantics, the K class and the frontier from the remaining
   demonstrations;
3. propose, verify, probe and select from scratch;
4. compile from scratch;
5. install into a fresh K* and rerun on the fold;
6. predict demonstration i.

Each fold records its proposer input hash, proposals, selection, engine
events, acceptance, attribution and held-out exactness. No object, table,
input or selection from the full-data run enters a fold; the only state
between calls is the content-addressed read of the frozen D file.

## 9. S6 separation law

| level | meaning |
|---|---|
| A, syntactic | the extension is not one of K's 200 programs |
| B, bounded search | K's search has no exact fit on the demonstrations |
| C, behavioural | on the frozen probe grids the fitted extension differs from every relevant existing K program: each PARTIAL block fitted on its own consistent regions, and any loosely fitting K program |

- The comparison set must be non-empty. If it is empty, C is
  C_UNTESTABLE and the claim is downgraded.
- If the fingerprint equals a member's, C is DUPLICATE_EXISTING_SEMANTICS.
- A "new semantic capability" needs A, B and C SEPARATED with a non-empty
  set. An empty set is never called novel.

## 10. Failure classes

| class | stage | kind |
|---|---|---|
| K_ALREADY_SOLVES | K* exact on the demonstrations | not a failure task |
| LEAKAGE_FAILURE | input scan | infrastructure, blocking |
| RESOURCE_EXHAUSTED | wall time | infrastructure |
| UNTYPEABLE_PROPOSAL | a proposal fails the compiler's typing | infrastructure (defect) |
| NO_PROPOSAL | no proposal at any depth | scientific |
| PROPOSAL_LIMIT | the cap was reached and nothing verified | scientific |
| NO_VERIFIABLE_PROPOSAL | proposals, none verified | scientific |
| SELECTION_ABSTAINED | PURE arm on a P0 tie | scientific |
| COMPILE_FAILURE | the compiler rejects the selection | infrastructure (defect) |
| ENGINE_REJECTED | K* + {e} not accepted, e not used, K* also solves, or held-out wrong | scientific |
| LOO_FAILURE | a fold fails | scientific |
| DUPLICATE_EXISTING_SEMANTICS | S6 level C equals an existing K program | claim downgrade |
| SUCCESS | engine stage succeeded (and, for a fold, its held-out pair) | |

Precedence: the first failing stage names the outcome.

## 11. Ablations

| arm | change |
|---|---|
| no proposer, compiler ablated, extension removed | K* alone: the paired ablation's K* arm |
| DEMO_ONLY | K blocks ranked by the share of changed cells their regions touch (no consistency, conflict or residual information), composed by rank sum, same caps and selection |
| FAILURE_CONDITIONED | sections 3 to 6 |
| SHUFFLED_FRONTIER | another task's whole `failure` object replaces the task's own (a fixed derangement, never the same target); demonstrations unchanged |
| NO_RESPONSE | selection without the probe |
| PURE | P0 without D or MDL |

## 12. Tests (`tests/test_v18_proposer.py`)

| directive item | test |
|---|---|
| deterministic generation | `test_generation_and_selection_are_deterministic` |
| no task-ID dependence | `test_no_task_channel` |
| demonstration-order invariance | `test_demonstration_order_invariance` |
| frontier perturbation acts only through declared semantics | `test_frontier_perturbation_acts_only_through_declared_semantics` |
| target absent from the input | `test_target_absent_from_input_and_scanner_refuses_forbidden_content` |
| hidden output inaccessible | `test_heldout_output_cannot_reach_the_proposer` |
| no persistent state | `test_no_persistent_state` |
| duplicate elimination | `test_duplicates_are_eliminated` |
| compiler compatibility | `test_every_proposal_types_and_the_selection_compiles` |
| maximum-candidate enforcement | `test_candidate_cap_is_enforced` |
| fresh-process reproduction | `test_fresh_process_reproduces_the_selection` |
| fold-level proposal isolation | `test_each_fold_proposes_from_its_own_demonstrations_only` |
| full-data proposal cannot leak into folds | `test_full_data_proposal_cannot_leak_into_folds` |
| shuffled failure destroys failure-specific proposals | `test_shuffled_frontier_destroys_failure_specific_proposals` |
| no Step-B dependency | `test_no_step_b_dependency` |
| failure classes reachable | `test_proposer_failure_classes_are_reachable`, `test_k_already_solves_on_a_single_layer_task`, `test_compile_failure_is_classified`, `test_s6_separation_law_and_its_downgrades` |
| D domain and v1.6 equivalence | `test_d_applies_only_to_key_feature_ties_and_matches_v16_on_one_position` |
| engine integration | `test_engine_stage_and_real_loo_on_a_fixture` (marked `engine`) |

Tests run with `PYTHONHASHSEED=0` and use the v1.7 development fixtures
(seed range 810,000,000).

## 13. Development audit (DEVELOPMENT ONLY)

DEVELOPMENT_RESULTS_PLACEHOLDER

## 14. Prospective test (frozen here, run once in the next stage)

PROSPECTIVE_PLACEHOLDER

## 15. Claim ceiling

- Before the prospective test: an engineering capability on development
  data only. No scientific claim.
- A prospective NO_ORACLE_PROPOSER_ACCEPTED would show, on synthetic
  constructive tasks only, that extensions built from K's own failure,
  without the target or a candidate pair, are compiled, necessary and
  certified in the same reasoner, with leave-one-out proposals inside every
  fold, and that the task's own failure frontier causes the useful
  proposals. That is LEVEL 2 on the claim ladder for the synthetic domain.
- It is not a real ARC result. LEVEL 3 needs a real ARC B/P/U/L/T/A
  witness from the closed-loop causal pilot. "CORA solved by invention"
  needs a complete real witness.
- The mechanism composes K's existing productions; the extension is new to
  K's search, not new vocabulary.

## 16. Order after the freeze

1. ONE adversarial review; genuine defects fixed by recorded erratum;
   re-freeze.
2. Next stage: the same-reasoner closed-loop causal pilot. Its first
   frozen step is this protocol's prospective test (section 14); the real
   ARC B/P/U/L/T/A witness search follows under its own protocol.
3. The 1,000 and protected 120 remain blocked (directive section 16).
