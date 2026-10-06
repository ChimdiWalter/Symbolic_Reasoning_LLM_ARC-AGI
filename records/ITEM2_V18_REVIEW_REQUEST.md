# Item-2 v1.8: the one adversarial review (request)

Written 2026-10-06 at the freeze.

**Rules for the reviewer:**
- Work read-only on the frozen commit named below.
- No access to Step B (`pipeline/Reasoning_Project`), VDCG, E_transfer, the
  Lockbox, or any ARC answer, solution or holdout file.
- In Reasoning_Project_tti, read only the frozen dependency source trees
  `cora_tti`, `cora_parent` and `level4_blind_runtime`.
- Do not run `scripts/v18_prospective.py` or call its `main()`, and do not
  run anything over generator seeds at or above 860,000,000; that range is
  reserved for the one prospective run. Calling its `freeze_problems()`
  alone is allowed.
- Do not regenerate or run anything over the v1.7 acceptance seeds
  (830,000,000 range).
- Synthetic probes of your own are allowed on the v1.8 development range
  (840,000,000 + 100k) and the v1.7 development fixtures (810,000,000
  range). So is the test suite `tests/test_v18_proposer.py`.
- Write nothing inside the repository.

Every tool call is scanned afterwards; a self-report of restraint is not
evidence.

## Frozen objects

- Frozen commit `e7afc0f` (Reasoning_Project_arc2026); RESUME and ledger
  updated after it in `1dd953a`.
- Manifest `outputs/tti/no_oracle_proposer_v18_manifest.json`, sha256
  `bd657faa12225d775e028a07e6208345c37b518f6c4c0f07ce518bdc9c8e8f7a`.
- Protocol `docs/CORA_TTI_NO_ORACLE_PROPOSER_v1.8.md`, sha256
  `32395af9647f2b03f51215b8a79fd0a5e01ee27e05af3a6d9ca4abf5991a80aa`.
- Proposer `cora_arc2026/v18_proposer.py`, sha256
  `0b3cb0a6a4f6eb69b671d7b3e68d61e1d9eed0c034c0df829cd56bcebb203b0a`.
- K* identity `b009a9fb13402348a73c3e1ef187a82c2d42fb5175e5fed806e8d33d6b73e729`.
  The v1.7 compiler is pinned unchanged at `04c6b3a1`.
- Frozen D `outputs/tti/v18_frozen_d.json`, sha256 `b0ae3eca`.
- The manifest lists all 28 pinned files and the dependency tree digests.

## What to read, in order

1. `records/ITEM2_V18_PROPOSER_DESIGN.md`. Section 11 is the post-development
   witness-set addendum.
2. `docs/CORA_TTI_NO_ORACLE_PROPOSER_v1.8.md`.
3. `records/ITEM2_V18_DEVELOPMENT_RESULT.md`,
   `records/ITEM2_V18_FEASIBILITY.md`.
4. `outputs/tti/no_oracle_proposer_v18_manifest.json`.
5. `cora_arc2026/v18_proposer.py`.
6. `scripts/v18_corpus.py`, `scripts/v18_dev_audit.py`,
   `scripts/v18_prospective.py`, `scripts/v18_build_exclusion.py`,
   `scripts/v18_freeze_d.py`, `scripts/v18_feasibility.py`,
   `scripts/freeze_v18.py`.
7. `tests/test_v18_proposer.py`.
8. What it reuses:
   - `cora_arc2026/v16_cfr.py` (probe, P0, fit) and `cora_arc2026/v15_sel.py`
     (D's design);
   - `cora_arc2026/v17_compiler.py` (compile, kstar, install, run_reasoner,
     paired_ablation, uses_extension);
   - `cora_tti/scoped_slot_fitting.py`, `cora_tti/constructive_dataset.py`,
     `cora_tti/constructive_vocabulary.py`, `cora_tti/constructive_probes.py`;
   - `geocat_arc/object_reasoning/meta_ast.py`.
9. The git history of the v1.8 files (`git log --stat d531141^..e7afc0f`),
   to check what was fixed before development measurement.

## Try to falsify each of these

1. **Hidden target reconstruction.** Can any proposer path read or
   reconstruct the generator's target (AST, tokens, digest, seed)? Trace:
   - `build_input`, `frontier`, `scan_input`, `propose`, `propose_demo_only`;
   - `solve`, `select`, `real_loo`, `engine_stage`, `compile_selected`;
   - how `scripts/v18_corpus.py` returns the schema, and where it goes.
2. **Target-digest leakage.** Is any digest or hash of the target or the
   task in the proposer input, the compiler provenance, or anything the
   selection reads?
3. **Candidate-space encoding of the oracle.** The candidate space is
   compositions of K's blocks, and the corpus law conditions on the
   generator's schema fitting exactly. Protocol section 15 states that this
   makes a verifying composition reachable by construction up to the caps.
   - Is that statement complete and accurate?
   - Is anything else in the space, the caps or the orders a disguised
     oracle?
   - Does it make any gate a foregone conclusion?
4. **Family or task branches.** Is there any branch on family, task, seed,
   target or schema identity anywhere in the proposer or the selection?
5. **Post-hoc proposal ordering or tuning.** Were the caps, orders,
   duplicate law and selection levels fixed before any development task
   (design record d531141; check the commit order)?
   - Is the witness-grid change (3f356d0, design record section 11) a
     genuine instrument correction or outcome-driven?
   - Does it change any proposal or any decision beyond the duplicate law
     and S6?
6. **Leave-one-out leakage.** Can a fold see its held-out demonstration
   (input or output), or anything from the full-data run or another fold?
7. **Proposal cache leakage.** List every cache that survives between
   calls:
   - geocat lru caches;
   - `_D_CACHE`;
   - the `witness_grids` lru cache;
   - anything in the fitter or the vocabulary.

   Can any of them carry task information?
8. **Compiler bypass.** Is any production installed or executed without the
   v1.7 compile and install path? Is the v1.7 compiler byte-identical to
   its freeze?
9. **Step-B contamination.** Is there any import, path or data dependency
   on Step B or another forbidden tree?
10. **Nondeterminism.** Check:
    - hash-seed dependence;
    - set or dict iteration order in proposals or selection;
    - wall-time-dependent classification (RESOURCE_EXHAUSTED);
    - load sensitivity of the engine stage;
    - floating-point ties in P0 or D.
11. **Unreachable or misassigned failure classifications.** Walk the class
    assignment in `solve`, `engine_stage` and `real_loo`, and the
    prospective outcome ladder. Is any class unreachable or mislabelled, or
    are infrastructure failures mixed with scientific negatives? Pay
    attention to:
    - DUPLICATE_EXISTING_SEMANTICS;
    - PROPOSAL_LIMIT;
    - ENGINE_REJECTED;
    - K_ALREADY_SOLVES.
12. **Selection-law fidelity.**
    - Is P0 exactly v1.6's rule?
    - Is D exactly v1.6's decision for one differing position?
    - Is the frozen D reproduction genuine?
    - Is the MDL guess declared as new everywhere it matters?
13. **Ablation validity.**
    - Is SHUFFLED_FRONTIER zero for an uninformative reason, for example
      donor residual coordinates that cannot be covered on another grid,
      making G1 against it automatic?
    - Is DEMO_ONLY a fair control or a strawman?
    - With both controls at 0 of 40 on development, is G1 informative?
      State what a stronger control would be.
14. **Prospective script correctness.** Check:
    - freeze and environment checks and the run-once guard;
    - corpus exclusion;
    - the witness definition (B/P/U/L/T/A) against the directive;
    - that gates and outcomes are computed exactly as section 14 says;
    - crash handling;
    - the seen/unseen audit.
15. **S6 law.** Is level C on the witness grids meaningful or near
    automatic? Is the comparison set the relevant one? Is the probe result
    reported honestly?
16. **Claim ceiling.** Is there any overstatement: a LEVEL 2 claim before
    the prospective test, "novel", "invention", "autonomous" beyond what
    is shown?

## Report format

For each item: FALSIFIED (exact file, line and mechanism, with evidence),
NOT FALSIFIED (what was checked), or UNABLE TO CHECK (why). Then a single
verdict with three lists: BLOCKING defects, MAJOR findings and MINOR
findings, with the smallest fix for each BLOCKING or MAJOR one. Finally,
list every command that executed code.
