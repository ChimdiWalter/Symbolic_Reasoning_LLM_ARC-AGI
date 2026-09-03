# Item-2 protocol: constructive semantic proposer (FROZEN before any training)

Frozen 2026-09-03, before any constructive dataset generation, model training,
or test-family observation. Machine-readable freeze:
outputs/tti/constructive_protocol_manifest.json (+ _hash.txt). Changes after
this point create a NEW protocol version; results under different versions are
never merged.

## 1. Scientific question

Primary: can failure evidence cause the system to construct a typed semantic
production whose complete AST was absent from its training labels?
Downstream (D3): can such a production, installed ephemerally, cause a
previously unsolved real DEV task to be solved through full re-induction with
causal ablation? The two are never conflated; synthetic gates precede D3.

## 2. Constructor language (inventory frozen by source hash)

Ops: Compose, Partition, Select, Map, Key, Lookup, Paint
(geocat_arc/object_reasoning/meta_ast.py; vocabulary registered by
meta_induction.py; both hashed in the manifest).
Terminals: PARTITIONS = {background_components, colour_components,
enclosed_regions, separator_panels}; PREDICATES = {all, not_rectangular,
not_touching_border, rectangular, touching_border}; KEY_FEATURES =
{sole_neighbour_colour, touches_border, is_rect, is_square, area, hw,
neighbour_colours, shape, row_band, col_band}.
Induced slot type (the ONLY one in v1): Map[FeatureValue,Colour], fitted by
the engine's ordinary learners. No ARC-task-specific primitive may be added;
no constructor may be selected by a branch on task id, family, DEV outcome,
delta category, size direction, Step-A frontier type, or any hidden output.

## 3. Grounded types and interfaces

Type universe: Grid, Set[Region], Set[Coloured], FeatureValue, Colour,
PartitionExpr, Predicate, FeatureExpr, Map[FeatureValue,Colour], Function.
Grounded interface: Grid -> Grid. This language has exactly one grounded
interface, so SPLIT C (typed-interface holdout) is DECLARED INFEASIBLE in v1
and is reported as a shortfall, not simulated.

## 4. Composition grammar (the decoder's and the generator's shared law)

    pipeline := block+                       (1 <= blocks <= 3)
    block    := Partition(p) Select(q)* Map(Key(f), Lookup(?slot)) Paint()
                with 0 <= selects-per-block <= 2

Caps: total stages <= 12; AST nodes (meta_ast.ast_nodes, tables cost 1/entry)
<= 48; induced slots = one per block (<= 3). MDL := meta_ast.ast_nodes.
STRUCTURAL FAMILY of a pipeline := the tuple of per-block select counts,
e.g. (0,), (1,), (2,), (0,0), (1,1), (0,0,0).

BASELINE-EXPRESSIBLE SHAPE: the engine's fixed meta-search enumerates exactly
the single-block one-select shape, family (1,). Family (1,) and family (0,)
single-block pipelines are BANNED as targets (requirement 6 rejects them);
family (1,) serves as the accidental-expressibility negative control.

## 5. Target requirements (every episode; failures counted, never silently
resampled)

1. e* typechecks under the grammar above.
2. e* executes on generated inputs (non-None on >= 3 seeded grids).
3. Demonstrations are nontrivial (output differs from input on every pair).
4. K without e* fails: the engine's fixed meta-search (8 s budget, the frozen
   ARC_META_BUDGET_S default) finds nothing on the demonstrations, AND the
   canonical single-block family cannot fit them (structural separation;
   labelled STRUCTURAL, never denotational).
5. K + e* solves: concept-guided instantiation of e*'s schema fits all
   demonstrations exactly.
6. Target behaviour not reproduced by any baseline-shape program on the
   frozen probe set (checked within the same budget; shortfalls reported).
7. The complete canonical target AST is absent from its training partition
   (dedup by canonical digest).
8. The target digest does not appear in its TFG (mechanical leak test).
Rejection rates are reported by family, depth, and block count.

## 6. Splits and seeds (frozen)

Generation root seed 20260903; train seeds 11000+i, val 12000+i, test
13000+i. Regime A (complete-AST holdout): train families {(0,0),(1,0),(0,1),
(1,1),(0,0,0)}; test-A targets drawn from the SAME families with canonical
ASTs absent from all training labels. Regime B (root-family holdout):
families {(2,),(2,1)} NEVER appear as training targets; the grammar still
permits them at decode time. Regime C: infeasible (see section 3).
Dataset targets: pilot 60 episodes (deterministic, validates the whole
pipeline before scale); full run 300 train / 60 val / 90 test (min 30 per
regime + negative controls). Shortfalls reported exactly; difficult targets
are never replaced after observing their outcomes.

## 7. Episode format and leakage law

Model input: TFG (from the real trace-extraction path on the crippled
search) + grounded interface. NEVER in model input: target name, digest, AST
text, task identity, source token, test solution, family label, or any
direct encoding of the withheld root family. The trusted harness alone reads
the target AST as the supervised label. A mechanical leakage test scans every
episode.

## 8. Model (non-LLM) and decoding

TFG feature encoder + interface embedding + grammar-constrained sequential
decoder over the stage grammar of section 4: at each step the decoder may
emit only tokens the grammar permits in that state (stage symbols, terminal
choices, induced-slot marker, block end, pipeline end), so structural type
validity is guaranteed by construction. Hidden size <= 256; torch permitted
(GPU); no natural-language anything; the model never predicts grids and
never certifies. Training stop: max 2000 epochs or 200-epoch val plateau on
exact@5.

## 9. Ranking (frozen coefficients)

    score(e) = model_log_prob(e | TFG, interface)
               - 0.05 * MDL(e)
               - 0.01 * predicted_execution_cost_s(e)

Beam width 16; top-k reported at k in {1,3,5}. Dedup before execution by
(grounded signature, canonical AST, frozen witness fingerprint); candidates
equal on the probe set form one WITNESS-EQUIVALENCE CLASS (finite-probe
equality, never global equivalence). Coefficients are never tuned on DEV.

## 10. Frozen probe set

16 grids from the seeded generator (root seed 20260903, sizes 5-10, 1-4
rectangular components); fingerprint = sha256 over concatenated rendered
outputs with an explicit None marker. Generator code hashed in the manifest.

## 11. Baselines (all under the identical grammar and budget)

U uniform typed enumeration; M MDL-first enumeration (MDL then canonical
id); F constructor-frequency prior from training (no TFG); N GPN-v1 name
head (reconstruction-only baseline, cannot emit unseen labels; reported with
that limitation). Key comparison: TFG-conditioned ranking vs the same
candidate language without TFG conditioning.

## 12. Certification loop and compiler

ConstructiveExtensionCompiler: generated AST -> ConceptRecord schema for the
engine's ephemeral path. Must preserve signatures/semantics/slots, be
deterministic, reject unknown constructors, unbound type variables, cycles,
over-depth, undeclared terminals; never mutate any global registry.
Differential obligation: compiled_semantics(x) == source_semantics(x) on
randomized probes, zero mismatches. The synthetic certification loop follows
directive item 13 verbatim; only the existing verifier certifies; every
episode's evidence enters the hash-chained ledger.

## 13. Metrics

The full directive item-14 list, with exact-AST recovery and
witness-equivalent (behavioural) recovery ALWAYS reported separately, plus
rejection/generation shortfalls and per-family, per-depth, per-MDL breakdowns.

## 14. Negative controls and stopping

(i) an irrelevant well-typed candidate must not certify on any test episode;
(ii) a family-(1,) target must be rejected by requirement 4/6 (accidental
baseline expressibility); (iii) a synthetic positive control must be
recoverable; (iv) a declared-hard negative control episode is expected to
remain unsolved and its failure must not trigger any protocol change.
Item-2 stops after the D3 report (directive items 17-19); the epistemic
controller, multi-operator dropout, HOLDOUT, and Kaggle work stay out of
scope. D3 preserves current base-acceptance behaviour: the 11 false-certified
base accepts remain terminal in D3 by design.

## 15. Claim terminology (binding)

KNOWN-OPERATOR RECONSTRUCTION / CONSTRUCTIVE SEMANTIC RECOVERY / CANDIDATE
SEMANTIC SELF-EXTENSION / SEMANTIC INVENTION / REAL ARC TTI-DEPENDENT SOLVE
exactly as defined in the execution directive. The 5/12 result is and stays
reconstruction; nothing in Item 2 is called invention without the declared
separation test.
