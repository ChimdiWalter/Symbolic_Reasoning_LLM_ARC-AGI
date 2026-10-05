# CORA-TTI Item-2 v1.7: the generic ConstructiveExtensionCompiler

Status: FROZEN at the commit named in
`outputs/tti/constructive_extension_compiler_v17_manifest.json`. Written
2026-10-05.
- Licensed by v1.6 (27078d1, PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES,
  hybrid, LEVEL 1).
- Design and feasibility: `records/ITEM2_V17_COMPILER_DESIGN.md` (fc0e37e).
- First freeze d5b5e1b (manifest 418ee5c2). One adversarial review:
  `records/ITEM2_V17_REVIEW_RESULT.md` (9195641).
- Amended by erratum 01 (`records/ITEM2_V17_ERRATUM_01.md`) before the
  acceptance test, then re-frozen. Amended rules are marked "(erratum 01)".
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
| K*-2 fitting law | the `Map[FeatureValue,Colour]` learner delegates the engine's own shape (one block, one Select) to the engine's own learner, unchanged, and every other shape to the frozen occurrence-scoped fitter (`cora_tti.scoped_slot_fitting`) | inert for K (erratum 01): without an overlay the concept route is dormant and K never calls the learner (engine test; the review's probe counted 0 calls). With e installed, every call is on e's own shape. |
| K*-3 overlay | installed productions are appended to the expression phase's concept list | inert when empty |

**Environment (erratum 01: enforced).** `PYTHONHASHSEED=0` with hash
randomization off, and no `ARC_*` variable other than the K* pair
`ARC_META_INDUCTION=1`, `ARC_META_BUDGET_S=8`, which `kstar()` sets itself.
`kstar()` refuses otherwise (KSTAR_ENVIRONMENT). The synthetic fixtures
also depend on the hash seed: the frozen generator's colour tables use
Python's salted string hash.

Why K* is needed (design record section 1):
- the engine's concept route was dormant;
- its learner cannot fit multi-block schemas;
- its expression phase received zero time on exactly the tasks where an
  extension is needed.

The ablation (section 9) therefore establishes necessity under K*, not
under K: e's success also uses K*-1's slice and K*-2's fitter, which only
e's presence makes reachable.

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
  - p, q and f are frozen vocabulary strings (`meta_ast.PARTITIONS`,
    `PREDICATES`, `KEY_FEATURES`) or free slots. Any other value, including
    a non-string, is UNKNOWN_TERMINAL (erratum 01).
  - s must be a free slot. A literal table is LITERAL_INDUCED_SLOT, because a
    stored table is memorization, not an extension.
- **Slots:** names match `?[A-Za-z0-9_]{1,32}`, and each occurs exactly once.
- **Types** come from the frozen positional signatures
  (`meta_ast.free_slot_types`): PartitionExpr, Predicate and FeatureExpr
  are enumerable; `Map[FeatureValue,Colour]` is induced. The result type is
  Grid.
- **Limits:** at most 4 blocks, at most 3 Select stages per block, at most
  64 nodes, at most 64 KB serialized.
  - These are the compiler's own limits, wider than the frozen constructive
    grammar's (3 blocks, 2 Selects, 48 nodes).
  - The node and byte limits cannot bind under the block and Select limits
    (the largest legal AST has 33 nodes and about 2 KB). They are kept as
    defensive bounds.

## 5. Output contract and serialization law

- **Canonicalization:** slots are renamed `?s0`, `?s1`, ... in depth-first,
  left-to-right order. This is slot renaming only; structurally different
  extensions that happen to be semantically equivalent get different
  bodies and names.
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
  - Compiling the same extension twice gives identical bytes, as does
    renaming its slots, changing its provenance or reordering the input
    keys.
- **Reload (erratum 01):** `load` rebuilds the production from its own body
  through the compiler's single build path and requires the identical
  bytes: every field, its type and its encoding.
  - A production from another compiler build (version or compiler sha256)
    is VERSION_MISMATCH.
  - A production for another K* is K_IDENTITY_MISMATCH.
  - Any other difference, or a body that does not parse or type, is
    TAMPERED_PRODUCTION.
- **Elaboration:** ordinary substitution (`meta_ast.instantiate`) into
  kernel meta-AST semantics, executed by `meta_ast.evaluate`. There is no
  extension-specific evaluator, branch or name test anywhere.

## 6. Installation and restoration law

- **`kstar()` context:** refuses outside the K* environment (section 2),
  then applies K*-1 to K*-3 and the K* pair of variables.
  - On exit it restores the identical objects and environment, then checks a
    state snapshot. Any difference is RESTORATION_FAILURE.
  - The snapshot (erratum 01: callables included) covers:
    - the expression-phase entry point and the slot-learner registry;
    - every module value of `meta_ast`, `meta_induction` and the fitter,
      callables by module, qualified name and bytecode, other values by
      repr;
    - the `ARC_*` environment and the overlay and installed lists.
- **`install(e, ...)`:** only inside `kstar()`.
  - It reloads each production through `load`, so only the compiler's own
    bytes for a body can be installed, and checks its K* identity.
  - It refuses a duplicate or a nested overlay (OVERLAY_CONFLICT).
  - It empties the overlay on exit and checks the snapshot.
- **Run hygiene:** what the snapshot does not cover is handled per run.
  - Every reasoner run clears the engine's memo caches at its start, so no
    cache carries an extension into another run.
  - Every run uses a fresh engine directory, removed after the run
    (erratum 01).
  - The flag-gated engine caches are unreachable, because foreign `ARC_*`
    variables are refused.
  - `sys.modules` and non-`ARC_*` variables are not covered: lazy imports
    during a first run change them without carrying an extension.

## 7. K* identity

sha256 over:
- the `geocat_arc` tree digest;
- the occurrence-scoped fitter's identity;
- the K* rule texts, including the environment rule;
- the K* environment;
- the compiler file's sha256, because it implements K* (erratum 01).

A production compiled for another K* cannot be loaded or installed.

## 8. Attribution law

`uses_extension(program, e)` is true only if both hold:
- the winning program, unwrapped from dihedral frames, is a
  `computed_pattern` carrying e's name;
- its AST instantiates e's body. Every induced slot binds a table, every
  enumerable slot a vocabulary member, and every other node matches
  exactly.

A solve after installation whose winner fails either test is not
extension-caused. Attribution is conservative: e used as a stage inside a
composed, overlay or other wrapper is not credited, which is possible under
the engine's default composition depth.

## 9. Ablation law

`paired_ablation` runs K* + {e} and K* on the same pairs, budget,
environment and task identifier, each in a fresh engine directory with
cleared caches. Verdicts:

| verdict | meaning |
|---|---|
| EXTENSION_NECESSARY_AND_USED | with e: accepted and uses e; without e: not accepted |
| USED_BUT_BASELINE_ALSO_SOLVES | with e: accepted and uses e; without e: accepted too |
| SOLVED_WITHOUT_USING_EXTENSION | with e: accepted, but the winner does not use e |
| NOT_SOLVED_WITH_EXTENSION | with e: not accepted |

Held-out exactness and wall seconds are reported for both arms. The arm
order is fixed (K* + {e} first), so the first run in a process pays lazy
imports inside its deadline; that cost falls on the extension arm.

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

**Caveat at this stage (erratum 01).** With the oracle proposer every fold
recompiles the same schema, which was selected using all 7 pairs, and the
fixture filter already checked, with the same scoped fitter, that each
6-pair fit reproduces its held-out pair. So here the L leg tests only the
machinery: a fresh compile and install per fold, engine acceptance on 6
pairs, attribution, and agreement of the engine's prediction with the
filter's. It becomes an out-of-sample test only when a proposer chooses the
extension inside each fold.

## 11. Failure classes

MALFORMED_INPUT, VERSION_MISMATCH, K_IDENTITY_MISMATCH, SOURCE_HASH_MISMATCH,
DECLARED_TYPE_MISMATCH, UNPARSABLE_SCHEMA, UNTYPEABLE, UNKNOWN_TERMINAL,
LITERAL_INDUCED_SLOT, DUPLICATE_SLOT, LIMIT_EXCEEDED, TAMPERED_PRODUCTION,
OVERLAY_CONFLICT, RESTORATION_FAILURE, KSTAR_NOT_ACTIVE, KSTAR_ENVIRONMENT
(erratum 01).

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
- A K program whose fingerprint raises is excluded, as in the frozen probe
  convention (an erroring program is rejected, never treated as
  undefined). The number excluded is reported (erratum 01).
- The comparison is exercised non-vacuously by `test_witness_separation`,
  which finds EQUIVALENT_TO_K for a K-shaped target.

## 13. Test suite (`tests/test_v17_compiler.py`)

Run with `PYTHONHASHSEED=0` (section 2).

| required property | test |
|---|---|
| 1 deterministic compilation, 2 canonical serialization | `test_compilation_is_deterministic_and_canonical` |
| 3 identical semantics after reload | `test_reloaded_production_has_identical_semantics` |
| 4 typing | `test_signature_types_follow_the_frozen_positions` |
| 5 malformed rejection | `test_input_contract_rejections` (8 cases), `test_typing_law_rejections` (9 cases), `test_non_string_terminals_are_unknown_terminals` (4 cases), `test_unparsable_schema_and_tampered_production`, `test_load_rejects_every_tampered_field_and_every_forged_body` (9 cases and a forged install) |
| 6 install and restoration | `test_install_and_restoration_leave_no_residue`, `test_install_requires_kstar_and_rejects_conflicts`, `test_kstar_refuses_a_foreign_arc_variable_or_another_hash_seed` |
| 7 no leakage between sequential extensions | `test_sequential_extensions_do_not_leak` |
| 8 usage attribution | `test_uses_extension_requires_both_label_and_structure`, engine ablation |
| 9 ablation restoration | `test_engine_paired_ablation` (snapshot equal after both arms; engine directories removed) |
| 10 task-ID invariance | `test_input_has_no_task_channel_and_renaming_is_invariant`, `test_engine_task_id_invariance` |
| 11 renamed-extension invariance | `test_input_has_no_task_channel_and_renaming_is_invariant` |
| 12 input-order invariance | `test_input_key_order_and_demonstration_order_do_not_matter` |
| 13 fresh-process reproduction | `test_fresh_process_reproduces_the_bytes` |
| 14 leave-one-out isolation | `test_adaptive_loo_gives_each_fold_only_its_own_pairs_and_a_fresh_compile`, `test_engine_adaptive_loo_with_recompilation_in_every_fold` |
| 15 bounded witness separation | `test_witness_separation` |
| K*-2 inertness for K | `test_engine_kstar_without_overlay_never_calls_the_learner` (erratum 01) |

Metamorphic relations:
- slot renaming, provenance change and input key order preserve the bytes;
- demonstration order preserves the fitted tables;
- block order is not a symmetry, so the name must change;
- a forged label or structure fails attribution;
- weak: on the 200 single-block K schemas the two fitters agree for
  fixture 0. Every one of them takes the delegation branch and most fit
  neither way, so this is not the inertness argument (erratum 01).

Fixtures are synthetic constructive tasks from seed range 810,000,000,
regenerated and checked against `logs/v17/fixtures.json`. They were
selected on held-out exactness (`logs/v17/findfix.py`), so the development
dry run does not predict S4.

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

**Run conditions (erratum 01).**
- Launched once by `scripts/run_v17_acceptance.sh`, as a single process at
  default CPU priority. The launcher refuses if its pid record or the
  marker exists, or if any `ARC_*` variable is set.
- The script refuses on any freeze problem (including the two pinned
  external files of the frozen constructive vocabulary and probes), on the
  environment (section 2), and if its report, rows, start record or marker
  exist.
- It writes a start record (environment, load average, CPU count), then one
  line per finished task with per-arm wall seconds, events, programs and
  the load average.

**For each task:** compile the given extension, then run in turn
determinism, reload, witness separation, paired ablation with the held-out
pair, a supplementary K* arm at 3x budget, and adaptive leave-one-out with
recompilation in every fold. Every run is snapshot-checked. The initial
snapshot is taken after fixture selection and before the first compile.

**Attribution checks.** These do not rely on the engine's own labels:
- residue: no run without e installed (the ablation's K* arm and the 3x
  arm) returns a winner carrying e's name anywhere in its program tree
  (erratum 01: the whole tree, not only the top level);
- direct execution: every winner attributed to e (the ablation's K* + {e}
  arm and every adaptive leave-one-out fold) is executed outside the
  engine, through the engine's own dihedral helpers for any frame and then
  `meta_ast.evaluate`. It must reproduce every training output of its run
  and agree with the engine on held-out exactness. This is a consistency
  check: the engine renders a computed pattern by the same function;
- label anomaly (erratum 01): a top-level computed pattern carrying e's
  name whose AST fails the structure test.

A K* + {e} solve whose winner does not use e is correctly not attributed. It
is recorded as SOLVED_WITHOUT_USING_EXTENSION and counts against S4 only.
e nested inside another wrapper is recorded as a nested use and not
credited.

**Success conditions** (all must hold for COMPILER_ACCEPTED):
- S1: every task compiles; bytes are deterministic and reload is identical;
  for the first task a fresh Python process reproduces the bytes;
- S2: no RESTORATION_FAILURE; the final snapshot equals the initial one;
- S3: zero residue, zero direct-execution disagreements and zero label
  anomalies;
- S4: at least 5 of 6 tasks give EXTENSION_NECESSARY_AND_USED with the
  held-out pair exact;
- S5: adaptive leave-one-out passes on at least 5 of 6 tasks (a test of the
  L-leg machinery only at this stage, section 10);
- S6: witness separation is SEPARATED on every task. The comparison-set
  size is reported per task; the filter (no exact K fit) makes an empty set
  likely, and then S6 is weak evidence (section 12). S6 still detects a
  compiled body that has lost its multi-block semantics.

**Supplementary, reported and not gating (erratum 01):**
- necessity against K* at 3x budget (24 s): the number of S4 tasks whose
  3x K* arm is also not accepted. Load can starve the K* arm's object
  search while e's expression slice keeps its own time, which pushes
  toward EXTENSION_NECESSARY_AND_USED; this measures how much of the
  necessity survives a generous baseline;
- nested uses, and the witness comparison-set sizes.

**Outcomes:**
- if S1 to S3 or S6 fail: COMPILER_DEFECTIVE;
- if only S4 or S5 fall short: COMPILER_INTEGRATION_INCOMPLETE. The engine is
  deadline-bound, so a run can vary with machine load, and that is recorded;
- if fewer than 6 tasks pass the filter within 2,000 seeds:
  NO_VERDICT_FIXTURE_SHORTFALL, and no compiler outcome is recorded;
- if any exception other than a compiler failure class occurs:
  NO_VERDICT_RUN_ERROR (erratum 01). The rows written so far, the
  traceback and the conditions over completed tasks are kept.

## 15. Claim ceiling

Passing this stage shows an engineering capability:
- oracle-selected constructive extensions are compiled into canonical
  productions;
- the productions execute inside the real engine through its ordinary
  fitting, rendering, verification and leave-one-out machinery;
- attribution is checked by name, structure, residue, label anomalies and
  direct execution;
- the ablation compares K* + {e} with K* at equal budget, with a 3x
  baseline reported;
- the patches and the overlay are restored and verified by snapshot, and
  engine directories are removed.

It is not LEVEL 2. LEVEL 2 needs an extension produced by the system
without the oracle pair, then compiled and certified. LEVEL 3 is a real ARC
B/P/U/L/T/A witness. The compiler is not the contribution claimed;
failure-conditioned semantic grammar growth in the same reasoner, with
rediscovery and ablation, remains the target.

## 16. Order after the freeze

1. ONE adversarial review (done); defects fixed by recorded erratum (done,
   erratum 01); re-hash and re-freeze.
2. The compiler acceptance test, run once (`scripts/run_v17_acceptance.sh`).
3. Record the result.
4. The next stage is the no-oracle extension proposer. It is not begun in
   this block.
