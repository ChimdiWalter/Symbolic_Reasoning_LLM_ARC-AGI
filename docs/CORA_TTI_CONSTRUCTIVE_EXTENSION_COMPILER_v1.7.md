# CORA-TTI Item-2 v1.7: the generic ConstructiveExtensionCompiler

Status: FROZEN at the commit named in
`outputs/tti/constructive_extension_compiler_v17_manifest.json`. Written
2026-10-05.
- Licensed by v1.6 (27078d1, PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES,
  hybrid, LEVEL 1).
- Design and feasibility: `records/ITEM2_V17_COMPILER_DESIGN.md` (fc0e37e).
- Nothing changes after the freeze except by a recorded erratum made before
  the compiler acceptance test is run.

## 1. Question

Can a generic mechanism take a legal semantic extension from the
constructive grammar and turn it into an executable production? The
production must be temporarily insertable into the same reasoner, the real
ARC engine, without task-specific code. Inside that reasoner it is fitted,
executed, verified and attributed by the reasoner's ordinary machinery, and
it is removable without residue.

This stage receives an already-selected extension; the oracle pair stays.
It builds no proposer.

## 2. The reasoner K*

The engine source (`geocat_arc`, the workspace copy) is unchanged; its tree
digest is pinned. K* is that engine run under three rules, identical in
every arm.

| rule | definition | effect without an extension |
|---|---|---|
| K*-1 expression slice | the CORA expression phase is called with `deadline=None`, so each call receives its declared `ARC_META_BUDGET_S` slice instead of only the parent's leftover time | **changes behaviour**: the plain single-block meta search runs on every trigger-firing task. The v23 count (185/1,000) is K's, not K*'s. |
| K*-2 fitting law | the `Map[FeatureValue,Colour]` learner delegates the one shape the engine produces (one block, one Select) to the engine's own learner, unchanged, and every other shape to the frozen occurrence-scoped fitter (`cora_tti.scoped_slot_fitting`) | inert: tested on all 200 K-shaped schemas |
| K*-3 overlay | installed productions are appended to the expression phase's concept list | inert when empty |

Environment: `ARC_META_INDUCTION=1`, `ARC_META_BUDGET_S=8`,
`PYTHONHASHSEED=0`, no other `ARC_*`.

Why K* is needed (design record section 1):
- the engine's concept route was dormant;
- its learner cannot fit multi-block schemas;
- its expression phase received zero time on exactly the tasks where an
  extension is needed.

## 3. Input contract (closed schema; any other key is MALFORMED_INPUT)

| key | content |
|---|---|
| `format` | `cora-extension-input/1` |
| `schema` | meta-AST JSON of the extension |
| `declared_types` | exactly `{"input": "Grid", "output": "Grid"}` |
| `provenance` | exactly `producer_sha256` and `evidence_sha256`, each 64 hex characters |
| `source_sha256` | sha256 of the canonical JSON of `schema` |
| `compiler_version` | `1.7.0` |
| `k_identity` | the identity of K* (section 7) |

Free text, task identifiers, labels, expected outputs and family names have
no field, so they cannot enter.

## 4. Typing law

- **Grammar:** `Compose` over one or more blocks. A block is
  `Partition(p)`, zero or more `Select(q)`, `Map(Key(f), Lookup(s))`,
  `Paint()`.
  - p, q and f are frozen vocabulary terminals (`meta_ast.PARTITIONS`,
    `PREDICATES`, `KEY_FEATURES`) or free slots.
  - s must be a free slot. A literal table is LITERAL_INDUCED_SLOT, because a
    stored table is memorization, not an extension.
- **Slots:** names match `?[A-Za-z0-9_]{1,32}`, and each occurs exactly once.
- **Types** come from the frozen positional signatures
  (`meta_ast.free_slot_types`): PartitionExpr, Predicate and FeatureExpr
  are enumerable; `Map[FeatureValue,Colour]` is induced. The result type is
  Grid.
- **Limits:** at most 4 blocks, at most 3 Select stages per block, at most
  64 nodes, at most 64 KB serialized.

## 5. Output contract and serialization law

- **Canonicalization:** slots are renamed `?s0`, `?s1`, ... in depth-first,
  left-to-right order.
- **Fields:**

  | field | content |
  |---|---|
  | `body` | the canonical meta-AST JSON |
  | `signature` | input, result and the ordered (slot, type) arguments |
  | `induced_slots`, `enumerable_slots` | the slot lists |
  | `blocks` | block count |
  | `source_sha256` | sha256 of the canonical body |
  | `compiler_version`, `compiler_sha256`, `k_identity` | identities |
  | `name` | `cx_` + the first 24 hex characters of sha256 over the canonical body and signature, so it is derived from content, never from a task |

- **Serialization:** JSON with sorted keys, no whitespace, ASCII.
  - Compiling the same semantic extension twice gives identical bytes, as
    does renaming its slots or changing its provenance.
  - Reloading recomputes every content-derived field; any disagreement is
    TAMPERED_PRODUCTION.
- **Elaboration:** ordinary substitution (`meta_ast.instantiate`) into
  kernel meta-AST semantics, executed by `meta_ast.evaluate`. There is no
  extension-specific evaluator, branch or name test anywhere.

## 6. Installation and restoration law

- **`kstar()` context:** applies K*-1 to K*-3 and the K* environment.
  - On exit it restores the identical objects and environment, then checks a
    state snapshot.
  - The snapshot covers the expression-phase entry point, the slot-learner
    registry, every non-callable module value of the meta modules and of the
    fitter, the `ARC_*` environment and the overlay. Any difference is
    RESTORATION_FAILURE.
- **`install(e, ...)`:** only inside `kstar()`.
  - It reloads each production from its canonical bytes and checks its
    K* identity.
  - It refuses a duplicate or a nested overlay (OVERLAY_CONFLICT).
  - It empties the overlay on exit and checks the snapshot.
- **Run hygiene:** every reasoner run uses a fresh engine directory and
  clears the engine's memo caches, so no cache carries an extension into
  another run.

## 7. K* identity

sha256 over:
- the `geocat_arc` tree digest;
- the occurrence-scoped fitter's identity;
- the K* rule texts;
- the K* environment.

A production compiled for another K* cannot be installed.

## 8. Attribution law

`uses_extension(program, e)` is true only if both hold:
- the winning program, unwrapped from any dihedral frame, is a
  `computed_pattern` carrying e's name;
- its AST instantiates e's body. Every induced slot binds a table, every
  enumerable slot a vocabulary member, and every other node matches
  exactly.

A solve after installation whose winner fails either test is not
extension-caused.

## 9. Ablation law

`paired_ablation` runs K* + {e} and K* on the same pairs, budget,
environment and task identifier, each in a fresh engine directory. Verdicts:

| verdict | meaning |
|---|---|
| EXTENSION_NECESSARY_AND_USED | with e: accepted and uses e; without e: not accepted |
| USED_BUT_BASELINE_ALSO_SOLVES | with e: accepted and uses e; without e: accepted too |
| SOLVED_WITHOUT_USING_EXTENSION | with e: accepted, but the winner does not use e |
| NOT_SOLVED_WITH_EXTENSION | with e: not accepted |

Held-out exactness is reported for both arms.

## 10. Adaptive leave-one-out (the later L leg)

For each held-out demonstration:
1. start from K* with an empty overlay;
2. give the proposer only the remaining demonstrations;
3. compile from scratch;
4. install;
5. solve;
6. predict the held-out demonstration.

No extension object, fitted table or selection from the full-data run is
passed into a fold. This is distinct from the engine's own gate, which
refits the same installed production in each of its folds.

## 11. Failure classes

MALFORMED_INPUT, VERSION_MISMATCH, K_IDENTITY_MISMATCH, SOURCE_HASH_MISMATCH,
DECLARED_TYPE_MISMATCH, UNPARSABLE_SCHEMA, UNTYPEABLE, UNKNOWN_TERMINAL,
LITERAL_INDUCED_SLOT, DUPLICATE_SLOT, LIMIT_EXCEEDED, TAMPERED_PRODUCTION,
OVERLAY_CONFLICT, RESTORATION_FAILURE, KSTAR_NOT_ACTIVE.

## 12. Declared bounded witness test

The production, fitted on the demonstrations with the occurrence-scoped
fitter, is fingerprinted on the frozen probe grids
(`cora_tti.constructive_probes`). It is compared with every single-block
program of K's meta space fitted on the same demonstrations. It is
SEPARATED if no K program has the same fingerprint, otherwise
EQUIVALENT_TO_K.

The comparison set is the K schemas whose occurrence constraints the frozen
fitter can satisfy, with or without exact replay. Its size is reported with
every result.
- When the set is empty, SEPARATED means only this: the frozen fitter
  admits no K single-block program on these demonstrations. The fingerprint
  comparison itself is not exercised. Some fit failures mean missing
  evidence (an unobserved key), not a contradiction, so an empty set is not
  a proof that no K program is consistent with the demonstrations.
- The comparison is exercised non-vacuously by `test_witness_separation`,
  which finds EQUIVALENT_TO_K for a K-shaped target.

## 13. Test suite (`tests/test_v17_compiler.py`)

| required property | test |
|---|---|
| 1 deterministic compilation, 2 canonical serialization | `test_compilation_is_deterministic_and_canonical` |
| 3 identical semantics after reload | `test_reloaded_production_has_identical_semantics` |
| 4 typing | `test_signature_types_follow_the_frozen_positions` |
| 5 malformed rejection | `test_input_contract_rejections` (8 cases), `test_typing_law_rejections` (9 cases), `test_unparsable_schema_and_tampered_production` |
| 6 install and restoration | `test_install_and_restoration_leave_no_residue`, `test_install_requires_kstar_and_rejects_conflicts` |
| 7 no leakage between sequential extensions | `test_sequential_extensions_do_not_leak` |
| 8 usage attribution | `test_uses_extension_requires_both_label_and_structure`, engine ablation |
| 9 ablation restoration | `test_engine_paired_ablation` (snapshot equal after both arms) |
| 10 task-ID invariance | `test_input_has_no_task_channel_and_renaming_is_invariant`, `test_engine_task_id_invariance` |
| 11 renamed-extension invariance | `test_input_has_no_task_channel_and_renaming_is_invariant` |
| 12 input-order invariance | `test_input_key_order_and_demonstration_order_do_not_matter` |
| 13 fresh-process reproduction | `test_fresh_process_reproduces_the_bytes` |
| 14 leave-one-out isolation | `test_adaptive_loo_gives_each_fold_only_its_own_pairs_and_a_fresh_compile`, `test_engine_adaptive_loo_with_recompilation_in_every_fold` |
| 15 bounded witness separation | `test_witness_separation` |

Metamorphic relations:
- slot renaming, provenance change and input key order preserve the bytes;
- demonstration order preserves the fitted tables;
- block order is not a symmetry, so the name must change;
- a forged label or structure fails attribution;
- K*-2 is inert on all 200 K-shaped schemas.

Fixtures are synthetic constructive tasks from seed range 810,000,000,
regenerated and checked against `logs/v17/fixtures.json`.

## 14. Compiler acceptance test (run once, after the freeze and the review)

**Fixtures:** new synthetic constructive tasks. Seed `830000000 + 100k`,
family `S.FAMILIES[k mod 5]`, k ascending. A task is taken if:
- it has at least 2 blocks and 8 demonstrations (7 for training, 1 held
  out);
- the occurrence-scoped fit is exact on the training pairs;
- K's single-block base search has no exact fit;
- the scoped fit re-derives every training pair under leave-one-out.

The filter reads only the given schema and the 7 training demonstrations,
never the held-out pair and never the engine. The first 6 tasks are used,
searching at most 2,000 seeds. The seed range was never used during
development.

**For each task:** compile the given extension, then run in turn
determinism, reload, witness separation, paired ablation with the held-out
pair, and adaptive leave-one-out with recompilation in every fold. Every
run is snapshot-checked. The initial snapshot is taken after fixture
selection and before the first compile.

**Attribution checks.** Two checks do not rely on the engine's own labels:
- residue: no run without e installed (the ablation's K* arm) returns a
  winner carrying e's name;
- direct execution: every winner attributed to e (the ablation's K* + {e}
  arm and every adaptive leave-one-out fold) is executed outside the
  engine, through the engine's own dihedral helpers for any frame and then
  `meta_ast.evaluate`. It must reproduce every training output of its run
  and agree with the engine on held-out exactness.

A K* + {e} solve whose winner does not use e is correctly not attributed. It
is recorded as SOLVED_WITHOUT_USING_EXTENSION and counts against S4 only.

**Success conditions** (all must hold for COMPILER_ACCEPTED):
- S1: every task compiles; bytes are deterministic and reload is identical;
  for the first task a fresh Python process reproduces the bytes;
- S2: no RESTORATION_FAILURE; the final snapshot equals the initial one;
- S3: zero residue and zero direct-execution disagreements (attribution is
  exact);
- S4: at least 5 of 6 tasks give EXTENSION_NECESSARY_AND_USED with the
  held-out pair exact;
- S5: adaptive leave-one-out passes on at least 5 of 6 tasks;
- S6: witness separation is SEPARATED on every task. The comparison-set
  size is reported per task; the filter (no exact K fit) makes an empty set
  likely, and then S6 is weak evidence (section 12). S6 still detects a
  compiled body that has lost its multi-block semantics.

**Outcomes:**
- if S1 to S3 or S6 fail: COMPILER_DEFECTIVE;
- if only S4 or S5 fall short: COMPILER_INTEGRATION_INCOMPLETE. The engine is
  deadline-bound, so a run can vary with machine load, and that is recorded;
- if fewer than 6 tasks pass the filter within 2,000 seeds:
  NO_VERDICT_FIXTURE_SHORTFALL, and no compiler outcome is recorded.

## 15. Claim ceiling

Passing this stage shows an engineering capability:
- oracle-selected constructive extensions are compiled into canonical
  productions;
- the productions execute inside the real engine through its ordinary
  fitting, rendering, verification and leave-one-out machinery;
- attribution is exact, the ablation is exact, and nothing persists.

It is not LEVEL 2. LEVEL 2 needs an extension produced by the system
without the oracle pair, then compiled and certified. LEVEL 3 is a real ARC
B/P/U/L/T/A witness. The compiler is not the contribution claimed;
failure-conditioned semantic grammar growth in the same reasoner, with
rediscovery and ablation, remains the target.

## 16. Order after the freeze

1. ONE adversarial review; defects fixed by recorded erratum; re-hash and
   re-freeze.
2. The compiler acceptance test, run once (`scripts/v17_acceptance.py`).
3. Record the result.
4. The next stage is the no-oracle extension proposer. It is not begun in
   this block.
