# Item-2 v1.7: the one adversarial review (request)

Written 2026-10-05 at the freeze.

**Rules for the reviewer:**
- Work read-only on the frozen commit named below.
- No access to Step B, Reasoning_Project, VDCG, E_transfer, the Lockbox or
  any ARC answer or solution file.
- In Reasoning_Project_tti, read only the frozen dependency source trees
  `cora_tti`, `cora_parent` and `level4_blind_runtime`.
- Do not run `scripts/v17_acceptance.py`, its `fixtures()` or anything else
  over seeds at or above 830,000,000; that range is reserved for the one
  acceptance run.
- Running the synthetic test suite `tests/test_v17_compiler.py` is allowed.
  Its fixtures come from the 810,000,000 development range.
- Write nothing inside the repository.

Every tool call the reviewer makes is scanned afterwards; a self-report of
restraint is not evidence.

## Frozen objects

- Frozen commit: `d5b5e1b` (Reasoning_Project_arc2026)
- Protocol `docs/CORA_TTI_CONSTRUCTIVE_EXTENSION_COMPILER_v1.7.md` sha256 `bcecb81e70dfb4ac9bf9e9fdf9182b435ca57c89d56ed5598b1e5712a80ce8d7`
- Manifest `outputs/tti/constructive_extension_compiler_v17_manifest.json` sha256 `418ee5c2f0e1ae30e43cdcf48de2c9faf1f55a5dfaaa566443f0b7437531bbb3`
- Compiler sha256 `999a0b9d4c58454b8cfcf6a90608c9dde6eea8535e1783b9cccbee6be49a0bae`; K* identity `2fe279a12d21ba3c650d6d8459382496e5d2954408605dd40c569a50213e8bfb`; fitter identity `2cc45152c430f8a2f9cfbcfd8c0bd6ad02ca6793819c6fcf16ede2060e6fc9d7`
- Implementation sha256 (first 16):
  - `cora_arc2026/v13_gen.py` `1d389abe6ddb70e2`
  - `cora_arc2026/v14_loc.py` `010fe720c6f7c4f1`
  - `cora_arc2026/v15_sel.py` `810dc0a70b33583b`
  - `cora_arc2026/v17_compiler.py` `999a0b9d4c58454b`
  - `logs/v17/feas4.py` `aba58f0b881d222a`
  - `logs/v17/findfix.py` `218c555662b62d64`
  - `logs/v17/fixtures.json` `fbebc474c7c21266`
  - `records/ITEM2_V17_COMPILER_DESIGN.md` `dcc5d571cdde5962`
  - `scripts/freeze_v17.py` `4bb9d4a8fe9b3597`
  - `scripts/v17_acceptance.py` `7f9ac2c9c9af5698`
  - `tests/conftest.py` `2deb6c8e8151c3d4`
  - `tests/test_v17_compiler.py` `0a8d195f67d23e79`
- Dependency trees: cora_arc2026 `327699457da617cc`, cora_parent `b64b49cf7ec5a678`, cora_tti `fbc73a101c0d74cd`, geocat_arc `4cee35c0048c1552` (unchanged since v1.6), level4_blind_runtime `cad36fd5458b97ba`
- Tests at freeze: fast 33 passed; engine 4 passed (181.9 s). Development
  dry run of the acceptance path: `logs/v17/acceptance_dryrun_dev.log`.

## What to read, in order

1. `records/ITEM2_V17_COMPILER_DESIGN.md`
2. `docs/CORA_TTI_CONSTRUCTIVE_EXTENSION_COMPILER_v1.7.md`
3. `outputs/tti/constructive_extension_compiler_v17_manifest.json`
4. `cora_arc2026/v17_compiler.py`
5. `tests/test_v17_compiler.py`, `tests/conftest.py`
6. `scripts/v17_acceptance.py`, `scripts/freeze_v17.py`
7. The engine paths the compiler patches or calls:
   - `geocat_arc/object_reasoning/meta_induction.py` (`induce_computed_candidates`, `SLOT_LEARNERS`, `ComputedPatternProgram`);
   - `geocat_arc/object_reasoning/meta_ast.py`;
   - `geocat_arc/object_reasoning/inducer.py`, `engine.py`, `actions.py` (`render_program`), `types.py` (`FramedProgram`);
   - `cora_tti/scoped_slot_fitting.py`, `cora_tti/constructive_probes.py`, `cora_tti/constructive_dataset.py`;
   - `cora_arc2026/v14_loc.py` (`clear_engine_caches`, `tree_digest`, `dependency_roots`).

## Try to falsify each of these

1. **Task or answer channel.** Can a task identifier, label, expected
   output, family name, seed or target identity reach the compiler input,
   the production, its name, the overlay, or the K* patches? Trace
   `make_input`, `validate_input`, `compile_extension`, `ConceptView`,
   `kstar`, `install`, `run_reasoner`.
2. **Special branches.** Is there any test of a production name, task id,
   family or schema identity anywhere in the compiler, the K* patches or
   the learner delegation? Is there any extension-specific evaluator, or
   does every production run through `meta_ast.instantiate` and
   `meta_ast.evaluate` only?
3. **K*-2 inertness.** The delegation is decided by shape alone. Can the
   engine call the `Map[FeatureValue,Colour]` learner with a shape it
   produces itself that is not `[Partition, Select, Map, Paint]`, so that
   K*-2 changes K's own behaviour? The inertness test covers the 200
   `baseline_single_block_schemas`. Are those all the shapes the engine
   produces? Check zero-Select and multi-Select one-block schemas, and
   concepts from the engine's own concept registry.
4. **K*-1 and the baseline.** K*-1 is identical in both arms. Could any
   solve credited to e actually come from K*-1 (the extra expression time)
   rather than from e? The ablation's K* arm is meant to answer this; does
   it?
5. **Restoration completeness.** Name any state that `install` or a
   reasoner run can leave behind that `state_snapshot` misses. Candidates
   include:
   - `lru_cache` memos outside `geocat_arc`;
   - files the engine writes;
   - the engine's concept registry or library on disk;
   - `sys.modules`;
   - environment variables outside `ARC_*`;
   - module values in modules other than `meta_ast`, `meta_induction` and
     the fitter.

   Does `clear_engine_caches` plus a fresh engine directory close each
   one?
6. **Attribution soundness.** Can `uses_extension` be true for a winner
   that did not come from the overlay? For example, the engine's own
   library learning a concept with the same name, or a K program that
   matches structurally and carries the name. Can it be false for a winner
   that did use e, for example when e is wrapped in a composed, overlay or
   reduction program? Are the acceptance test's residue and
   direct-execution checks sound, including frames?
7. **Ablation symmetry.** Are the two arms identical except for the overlay
   (budget, environment, task id, cache state, engine directory)? Does
   running the K* + {e} arm first warm anything that changes the K* arm?
8. **Adaptive leave-one-out isolation.** Does any fold receive anything from
   the full-data run or an earlier fold: a production object, fitted
   tables, an engine library on disk, or a cache? Is "compile from scratch"
   real?
9. **Serialization and tamper detection.** Is the serialization canonical?
   Does `load` recompute every content-derived field from the body, so that
   a production with a changed body, name, signature, identity or slot list
   is TAMPERED_PRODUCTION? Can a forged production be installed by any
   path?
10. **Typing law.** Is any legal grammar extension rejected, or any illegal
    one accepted? Check:
    - a literal table in `Lookup`;
    - an enumerable slot in `Lookup`;
    - duplicate slots;
    - unknown terminals;
    - more than 4 blocks, 3 Selects or 64 nodes;
    - non-Grid results.

    Does the typing come only from the frozen signatures?
11. **Witness test.** Is it a meaningful test? Section 12 now states that an
    empty comparison set exercises nothing beyond the fitter. Is that
    statement accurate and sufficient? Is anything else trivial about S6?
12. **Acceptance test.** Check the following:
    - Can the fixture filter read the held-out pair or the engine?
    - Is the seed range new?
    - Are S1 to S6 and the outcomes computed exactly as section 14 states?
    - Is a shortfall or a crash handled honestly?
    - Does the script refuse on every freeze problem?
    - Is the fresh-process check correct?
13. **Freeze completeness.** Does the manifest pin everything the acceptance
    result depends on? Name anything unpinned that can change the outcome:
    - packages beyond numpy and scipy;
    - environment variables;
    - thread counts;
    - machine load, given that the engine is deadline-bound.
14. **Determinism.** Is compilation deterministic across processes and
    `PYTHONHASHSEED` values? Does anything depend on set or dict iteration
    order?
15. **Claim ceiling.** Does any text in the protocol, design record, code
    or tests claim more than an engineering capability? That includes
    LEVEL 2 or higher, or calling an oracle-selected extension invented or
    discovered.

## Report format

For each item: FALSIFIED (with the exact file, line and mechanism), NOT
FALSIFIED (with what was checked), or UNABLE TO CHECK (why). Then a single
verdict listing BLOCKING defects, MAJOR findings and MINOR findings. Do not
propose redesigns beyond what a finding requires.
