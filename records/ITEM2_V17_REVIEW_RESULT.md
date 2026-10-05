# Item-2 v1.7: the one adversarial review (result)

Review of the frozen commit d5b5e1b (manifest 418ee5c2), requested in
`records/ITEM2_V17_REVIEW_REQUEST.md` (646d6d5). Received 2026-10-05.

## Access audit (done before acting on any finding)

The reviewer's transcript was scanned tool call by tool call (88 calls: 75
Bash, 8 Read, 4 Write, 1 hand-back).
- Step B tree, VDCG, E_transfer, Lockbox: 0 references.
- ARC answer, solution or holdout files: 0 (the one word match was the code
  line `sol = res.solution` inside a probe script).
- Reasoning_Project_tti: only `cora_tti/`, `cora_parent/` and
  `level4_blind_runtime/` were read or searched.
- Seeds at or above 830,000,000: 0. `scripts/v17_acceptance.py` was read,
  never run or imported.
- Writes: 4, all in the reviewer's scratch directory. No git command that
  changes state, no process control, no package installation, no broad
  filesystem search. One narrow `/tmp` access counted `v17run_*` names.
- Tracked-file sha256 for all 2,159 tracked files, and the full git status
  including ignored files, are identical before and after the review.

## The report, verbatim

# Adversarial review of CORA-TTI Item-2 v1.7 (frozen commit d5b5e1b, review request 646d6d5)

**Bottom line: two BLOCKING defects.** One affects how the acceptance run is set up. The other breaks the protocol's own law on loading productions. Both have small fixes. Sections 14's S1 to S6 and the outcome rules are computed exactly as written. I found no task or answer channel in the compiler path. K*-2 is inert on K's own behaviour, and I confirmed that empirically.

The acceptance has not been run: `outputs/tti/v17_acceptance_report.json` and `logs/V17_ACCEPTANCE_DONE` do not exist.

## Item by item

**1. Task or answer channel: NOT FALSIFIED (compiler path).**
- `validate_input` accepts exactly the closed key set (v17_compiler.py:255-256).
- Provenance must be exactly two 64-hex values (265-268). It never enters the production, which is built only from the canonical body (284-297).
- `ast_from_json` ignores extra schema keys, so junk in the input never reaches the body.
- The name is a hash of body plus signature (291). `ConceptView` carries only the name and schema.
- `run_reasoner` passes only the training pairs to the engine (540-550). The held-out pair is used only after the run (585-586, 608). `task_id` reaches only `engine.solve`, which uses it for file names.
- Caveat: through the forging path in item 9, arbitrary data (for example a task id) can ride inside a production's body JSON and determine the name it is installed under.

**2. Special branches: NOT FALSIFIED.**
- No test of a production name, task, family or schema identity exists in the compiler, the K* patches or the delegation.
- Delegation depends only on the top-level operator sequence (372).
- Execution goes only through `meta_ast.instantiate` and `meta_ast.evaluate`:
  - `search_with_concepts` (meta_induction.py:404-409);
  - `fit_induced_slots` (370);
  - the scoped fitter's replay (scoped_slot_fitting.py:365-369);
  - `ComputedPatternProgram.render_array` (543-547).
- The only name tests are in attribution (524) and the duplicate-install check (467-469).

**3. K*-2 inertness: NOT FALSIFIED.**
- The learner entry is reachable only through `fit_induced_slots` (meta_induction.py:346-375).
- That is called only by `search_with_concepts` (406), which runs only when concepts are passed (565-566). The engine's one call site passes none (inducer.py:3245-3247).
- `meta_search` and `meta_v21_search` keep separate registries and are not imported by the inducer. `concept_registry.py` is imported nowhere.
- Probe on both development fixtures: K* runs made 0 learner calls (budgets 8, 24 and 48 s). K*+{e} runs made 16 calls, all on e's own shape.
- Zero-Select or multi-Select one-block shapes would be fitted differently: K's learner returns None or uses only the last Select. But K never reaches the learner.
- The 200-schema test is uninformative: all 200 schemas take the delegation branch.

**4. K*-1 and the baseline: NOT FALSIFIED.**
- Both arms run inside `kstar()`. If K*-1's extra time were enough, the K* arm would accept and the verdict would be USED_BUT_BASELINE_ALSO_SOLVES.
- A solve is credited only when the winner is e's computed pattern.
- The ablation establishes necessity under K*, not under K. e's success also depends on K*-2's fitter, which only e's presence makes reachable.

**5. Restoration completeness: PARTLY FALSIFIED as a coverage claim.** I found no state that carries e into another run under the K* environment.

What `state_snapshot` misses:
- callables in M, MI and SF other than `induce_computed_candidates` and the learner values. A rebound `M.evaluate`, `MI.fit_induced_slots` or `SF.fit_induced_occurrences` would pass (line 406 skips callables);
- function identity is (module, qualname, `co_code`), with no constants, closures or defaults;
- `correspondence.LEARNED_VERBS` (reset by every engine constructor);
- the contents of the lru_caches in features.py after the last run. They are cleared only at the start of each run;
- dict caches in `guide_hook` and `generative`, which are never cleared but are live only under ARC flags;
- `sys.modules`, `_STATE["installed"]`, and non-ARC environment variables;
- engine directories on disk. They are created by `mkdtemp` and never removed; 31 `v17run_*` directories already sit in /tmp.

The docstring's "everything an installation could leave behind" overstates the coverage.

**6. Attribution soundness: no false positives; false negatives exist (conservative).**
- No false positives: only the overlay creates computed patterns that carry a concept name, and library learning or anti-unification never runs in `solve`.
- False negatives: `uses_extension` unwraps only frames (521-523). e as a stage of a ComposedProgram goes unattributed; that is possible under the default `max_composition_depth=3` through `_expand`, inducer.py:3337-3346. Overlay and erase-patch wrappers behave the same way under flags.
- The residue check `carries_name` looks only at the top-level concept.
- Direct execution re-runs the same `meta_ast.evaluate` that `apply_fn` uses, so it is a consistency check.
- Frame handling matches `render_program`.

**7. Ablation symmetry: NOT FALSIFIED.**
- Same pairs, budget, environment and task id; fresh engine directory and cleared caches for each arm.
- Differences:
  - fixed arm order: the first engine run pays lazy imports (scipy.stats and others) inside its deadline, which favours the K* arm;
  - load drift between the two arms (see MAJOR-3);
  - in the e arm, concept hits short-circuit K's plain meta search (meta_induction.py:565-569). That is how the engine treats concepts, so it belongs to the overlay itself.

**8. Adaptive leave-one-out isolation: NOT FALSIFIED** for objects, tables, disk and caches. But "compile from scratch" is vacuous; see MAJOR-4.

**9. Serialization and tamper detection: FALSIFIED.** See BLOCKING-2.

**10. Typing law: NOT FALSIFIED against the compiler's own section 4 law.** 16 boundary cases were classified as stated. Qualifications:
- a dict literal in a Partition or Select position raises a raw `TypeError` (parse_blocks 160-166);
- the compiler accepts extensions outside the frozen constructive grammar: its limits are 4 blocks / 3 Selects / 64 nodes against the grammar's 3 / 2 / 48;
- the 64-node and 64 KB limits can never bind. The largest legal AST is 33 nodes and 1,953 bytes.

**11. Witness test: NOT FALSIFIED.** The section 12 statement is accurate. But S6 is nearly vacuous given the filter:
- SEPARATED reduces to "the compiled body re-fits the 7 pairs", which the filter already ensures for the input schema;
- `except Exception: continue` (636-637) leans toward SEPARATED;
- a legal extension with enumerable slots gets UNSUPPORTED.

**12. Acceptance test: PARTLY FALSIFIED.**
- Correct:
  - S1 to S6 and the outcome rules match section 14 line by line;
  - the filter reads neither the held-out pair nor the engine;
  - the seed range is new: 830,000,000 appears only in the protocol, freeze_v17.py and v17_acceptance.py, and its grid seeds (8.051e10 to 8.053e10) meet no earlier range;
  - the shortfall path is honest;
  - the fresh-process check is correct.
- Wrong:
  - the script does not refuse on environment problems (BLOCKING-1) or on the unpinned external file (MAJOR-1);
  - a crash is not handled (MAJOR-2).

**13. Freeze completeness: FALSIFIED.**
- Unpinned: the environment (BLOCKING-1), the external constructive manifest (MAJOR-1), and machine load (MAJOR-3).
- The K identity hashes the rule texts, not the code that implements them.
- Packages: only numpy and scipy are on the engine path, and both are pinned.
- Thread counts are set to 1 by the script.

**14. Determinism.**
- Compilation: NOT FALSIFIED. Bytes are identical under PYTHONHASHSEED 0, 1, 12345 and random.
- Fixtures: FALSIFIED. cora_tti/constructive_dataset.py:321 uses Python's salted `hash(repr(value))` to build the fixture colour tables.
- Engine object search: not established.

**15. Claim ceiling: NOT FALSIFIED.** There is no LEVEL 2 claim and no "invented" or "discovered". Engineering wording overstates in places:
- "attribution is exact", "the ablation is exact", "nothing persists" (section 15);
- "the same semantic extension" (canonicalization is only slot renaming);
- `install`'s docstring "a mutated or forged object cannot be installed", which is false (BLOCKING-2).

**UNABLE TO CHECK:** whether the tti constructive manifest still matches the v1.5 and v1.6 pins. It lies outside the trees I am allowed to read.

## Verdict

### BLOCKING

**B1. The K* environment is neither enforced nor recorded, and the fixtures depend on it.**
- Protocol section 2 defines K*'s environment as PYTHONHASHSEED=0 and no other ARC_*.
- `freeze_problems()`/`main()` (v17_acceptance.py:44-63, 217-260) check neither. `kstar()` sets only the two K* variables (v17_compiler.py:434), so any other ARC_* passes through.
- Engine flags that would change behaviour if present include ARC_DIHEDRAL_FRAMES, ARC_OVERLAY, ARC_GENERATIVE, ARC_ANALOGY, ARC_GRADUATE and ARC_RELIFT.
- Evidence: development seed 810000100 gives different demonstration bytes under every hash seed tried. Its tables are ((F,9),(T,5)),((F,3),(T,8)) under seed 0 and ((F,8),(T,2)),((F,2),(T,5)) under seed 1.
- v1.6 refused to run without PYTHONHASHSEED=0 (scripts/generate_v16_pairs.py:165-166), and the v1.5 and v1.6 manifests carried an `environment` rule. v1.7 dropped both.
- RESUME.md:233-239, the only re-run recipe, omits PYTHONHASHSEED.
- Consequence: the run can draw an irreproducible fixture set, or run on a reasoner that is not K*, and the report would not show it.
- **Smallest fix:**
  - refuse unless `os.environ.get("PYTHONHASHSEED") == "0"` and `sys.flags.hash_randomization == 0`;
  - refuse if any ARC_* is set other than ARC_META_BUDGET_S=8 or ARC_META_INDUCTION=1;
  - write `L.environment_snapshot()` into the report.

**B2. `load()` and `install()` do not enforce the section 5 law.**
- `load` (307-333) never recomputes `induced_slots` or `enumerable_slots`. It never checks `compiler_version` or `compiler_sha256`, and never requires the body to be in canonical encoding.
- Probe results:
  - tampered slot lists, compiler version, compiler sha, k_identity and `blocks=2.0` all LOADED;
  - a body carrying `{"task_id": "task-0042", ...}`, with name and source hash recomputed, LOADED and INSTALLED as `cx_8fce4b5b…`;
  - a body with a non-canonical `lit` encoding loaded as `cx_69accc90…` and was installed together with its canonical twin `cx_8d1b07d2…`. They are the same AST under two names, because the duplicate check is by name only;
  - a malformed body raises a raw `KeyError`.
- This does not change the acceptance outcome, which loads only fresh compiler output. It is a violation of the protocol's own law, and the test suite claims coverage of it.
- **Smallest fix:**
  - wrap parsing and typing failures as TAMPERED_PRODUCTION;
  - require `prod["body"] == M.ast_to_json(ast)`;
  - compare recomputed slot lists;
  - require `compiler_version == COMPILER_VERSION` and an integer `blocks`;
  - check `compiler_sha256` against the running compiler if it is meant as an identity;
  - add tests for each of these.

### MAJOR

**M1. Unpinned external input.**
- `cora_tti/constructive_vocabulary.py:32-52` reads `Reasoning_Project_tti/outputs/tti/constructive_protocol_manifest.json`. It is checked only against a hash file in the same directory.
- That file supplies the vocabulary order that `sample_target` indexes (so the fixture schemas) and the S6 probe set (constructive_probes.py:41-47).
- The v1.5 and v1.6 manifests pinned both files (`external_file_sha256` 66780880… and c9f7fe31…). The v1.7 manifest does not.
- **Fix:** pin `L.EXTERNAL_FILES` in the manifest and check them in `freeze_problems()`.

**M2. A crash leaves nothing, and a second run is not blocked.**
- `main()` catches only CompileError (232-235). Any other exception aborts without a report, a marker or partial rows. Examples: `TimeoutExpired` in the fresh-process check, `OSError`, or an exception in the witness fingerprint at line 629.
- Nothing stops a second run from overwriting the report and marker (253-259).
- **Fix:**
  - refuse to start if the report or marker already exists;
  - write a start record and append each task row as it finishes;
  - record any other exception as an error row.

**M3. Load is uncontrolled and unrecorded, and it pushes toward NECESSARY.**
- The K* arm is deadline-bound: it used its full 8.1 s on both development fixtures, and the full 24 s and 48 s on fixture 1.
- Load average during my probes was about 42-43 on 24 cores.
- Under CPU starvation:
  - the K* arm finds less;
  - the e arm has fewer object competitors;
  - e's own phase keeps its 8 s slice.
  So load can only push toward EXTENSION_NECESSARY_AND_USED.
- Section 14 says load variation "is recorded", but the report keeps only the total seconds, and `run_task` drops each arm's events (185-190).
- Mitigating evidence: tripling the budget for both arms (6× for K* on fixture 1) flipped neither verdict.
- **Fix:**
  - record per-arm wall seconds, events and `os.getloadavg()`;
  - state the CPU condition for the run. RESUME.md:239 runs `nice -n 19` beside Step B's 20 workers.

**M4. S5 is not adaptive leave-one-out.**
- The acceptance proposer (v17_acceptance.py:204) ignores the fold, so every fold recompiles the byte-identical oracle schema, which was admitted using all 7 pairs.
- The filter (85-99) already checked, with the same scoped fitter, that each 6-pair fit reproduces its held-out training pair. So S5's held-out exactness is decided in advance. S5 measures only whether the engine accepts e on 6 pairs and whether e wins.
- **Fix:** an erratum stating this. Only S4's held-out pair (`pairs[7]`) is out of sample.

### MINOR (ranked)
1. Attribution false negatives and a weak residue check (item 6). Winners that carry e's name but fail the structure test are not counted as disagreements.
2. `state_snapshot` coverage gaps (item 5).
3. Engine directories are never removed, each holding a program JSON with e's name.
4. Raw exceptions instead of failure classes (`TypeError` on dict literals, `KeyError` in `load`).
5. Compiler limits are looser than the constructive grammar; two limits can never bind.
6. The K*-2 inertness test is uninformative.
7. S6 is nearly vacuous, and errors lean it toward SEPARATED.
8. The K identity excludes the K* implementation code, and `install` ignores `compiler_sha256`.
9. Canonicalization is only slot renaming ("the same semantic extension" wording).
10. Fixed arm order with first-run import cost (conservative).
11. `test_fixtures_regenerate_exactly` checks schemas only. The development fixtures were selected on held-out exactness (logs/v17/findfix.py:27-28), so the dry run does not predict S4.
12. Engineering overstatements in section 15.

## Commands that executed code
All runs were from the repo root with `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<Reasoning_Project_tti>` and `.venv_arc2026/bin/python`, unless noted.

1. `PYTHONHASHSEED=0 … -m pytest tests/test_v17_compiler.py -q -p no:cacheprovider -m "not engine"`. Result: 33 passed, 4 deselected.
2. `PYTHONHASHSEED=0 timeout 300 … <scratch>/probe_load.py` (no seeds).
3. `probe_hashseed.py`, 4 runs, with PYTHONHASHSEED=0, =1, =12345, and unset via `env -u`. Seeds 810000100 and 810004800.
4. `PYTHONHASHSEED=0 OPENBLAS/OMP/MKL_NUM_THREADS=1 timeout 580 … probe_engine.py 0 8,24 with_e`.
5. Same, `probe_engine.py 1 8,24,48 with_e`.
6. `PYTHONHASHSEED=0 timeout 300 … probe_typing.py` (no seeds).
7. `probe_engine2.py {0,1} none with_e 24`, 2 runs, same environment as 4.
8. System `python3 -c` printing `external_file_sha256` and `environment` from the repo's v1.5 and v1.6 manifests.

Other notes:
- Scripts are in `/tmp/claude-100350790/-deltos/1a86a57b-d764-4f47-a834-c23a0c91436c/scratchpad/v17_reviewer/`. Engine directories went to `…/v17_reviewer/engine_dirs/` (9 directories).
- The only generator seeds used were 810000100 and 810004800. I never ran or imported v17_acceptance.py.
- Nothing was written in the repo: `find -newer` shows only `.git`, from read-only `git status`.
