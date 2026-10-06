# Item-2 v1.8: the one adversarial review (result)

Review of the frozen commit e7afc0f (manifest bd657faa), requested in
`records/ITEM2_V18_REVIEW_REQUEST.md` (eff2e04). The interactive session
restarted once during the review; the same reviewer was resumed from its
saved transcript (it is one review, not two). Received 2026-10-06.

## Access audit (done before acting on any finding)

The reviewer's transcript was scanned tool call by tool call: 89 calls (88
Bash, 1 hand-back; 63 before the restart, 26 after).
- Step B tree, VDCG, E_transfer, Lockbox: no access. The names appear only
  in (a) two scripts that check the file paths of loaded modules against
  those prefixes and (b) two greps that search the allowed trees
  (arc2026 code; tti `cora_tti`, `cora_parent`, `level4_blind_runtime`)
  for references to them.
- Seeds: nothing at or above 860,000,000 and nothing in the 830,000,000
  range; only the 840,000,000 development range, the witness-grid seeds and
  the 810,000,000 v1.7 fixtures (through the test suite).
- `scripts/v18_prospective.py`: read, and `freeze_problems()` called; `main()`
  never called.
- Writes: none in the repository; scratch files only. No git command that
  changes state, no process control, no package installation, no broad
  filesystem search.
- **Deviation, disclosed by the reviewer and confirmed in the transcript:**
  one `find . -type f ! -name "*.py"` inside the repository's `geocat_arc`
  copy printed the names of its first 20 non-Python files, among them a
  diagnostics file `target_outputs.json` under an ARC task id. Names only;
  no contents were opened. Recorded; no effect on any finding.
- **Deviation, minor:** some read-only JSON parsing used system `python3`
  rather than the prescribed environment form; nothing was written.
- Tracked-file sha256 for all 2,206 tracked files, and the full git status
  including ignored files, are identical before and after the review.

## The report, verbatim

## v1.8 no-oracle proposer: adversarial review

**Verdict: not ready for the prospective run.** I found 1 BLOCKING defect, 2 MAJOR findings and 18 MINOR ones. The core boundary holds: no target, digest, seed, family or held-out pair reaches the proposer or the selection, and the folds are rebuilt cleanly. The blocking problem is G1. Both controls are built so they cannot produce a proposal. G1 therefore passes whenever FAILURE_CONDITIONED is useful on 5 of 30 tasks, and the claim that "the task's own failure frontier causes the useful proposals" is never actually tested.

Repo checked read-only at HEAD eff2e04 (clean). All pinned hashes match the manifest, and `freeze_problems()` returns [].

All probes ran on development data only (seeds 840,001,000 to 840,079,800). Results files are in `/tmp/claude-100350790/-deltos/1a86a57b-d764-4f47-a834-c23a0c91436c/scratchpad/v18_reviewer/` (`controls_out.json`, `controls_40.log`, `sel_s6_0_20.json`, `sel_s6_20_40.json` and their logs).

### Items 1 to 16

**1. Hidden target reconstruction: NOT FALSIFIED.**
- `build_input` (`v18_proposer.py` 244-252) uses only the training grids, a frontier computed from them, grammar, limits and the K* id.
- `frontier`, `scan_input`, `propose` and `propose_demo_only` read only that input and the `Semantics` built from the training pairs.
- `solve`, `select`, `real_loo`, `engine_stage` and `compile_selected` receive the training pairs and `rec`. The held-out pair is used only to score afterwards.
- `v18_corpus.tasks` returns the schema in the task dict. `v18_prospective.run_task` uses it only for the target behaviour, the normalized text, the digest and the block count, and never passes it on.
- At runtime, loaded modules came only from pinned trees.
- The only route from the target is corpus selection (see items 3 and M1).

**2. Target-digest leakage: NOT FALSIFIED.**
- The scanner refuses any string outside the vocabulary. The only 64-hex string allowed is the K* id.
- Compiler provenance is the proposer file sha256 plus the sha256 of the proposer input (training pairs plus frontier). It is validated and then not carried into the production (`v17_compiler.py` 297-319).
- The selection reads only verified candidates, witness-grid behaviours, CFR responses, D features from the training pairs, and MDL.

**3. Candidate-space encoding: FALSIFIED (partly).**
- The §15 statement is accurate:
  - On 38 of 38 two-block dev tasks the generator's top block is PARTIAL and its lower block passes the lower-layer rule.
  - On the 2 three-block tasks, top, middle and bottom all pass.
  - By code comparison, no proposer rule is stricter than the fitter.
- The statement is incomplete:
  - (a) Every main-arm proposal verifies (38 of 38 tasks), so verification never rejects anything.
  - (b) The corpus law also requires the generator's schema to pass fitter-level leave-one-out on all 7 training pairs (`v18_corpus.py` 54-63). This is not disclosed in §15 (see M1).
  - (c) 145 of 161 distinct verified candidates predict the held-out pair, so "useful" is close to automatic. Together with controls that cannot propose, G1 becomes a foregone conclusion (B1), and S6 does too (M2).
- The MDL tie-break is not a disguised oracle: it matched the generator on 5 of 25 tasks.

**4. Family/task branches: NOT FALSIFIED.**
- No branch on family, seed, digest, task, schema or target anywhere in the proposer or selection. The only branches are on arm, depth and mode.

**5. Post-hoc proposal ordering or tuning: NOT FALSIFIED (with minor issues).**
- The design record (d531141, 16:06) fixes every cap and order; the proposer (bab4b75, 19:03) has the same LIMITS.
- The first development task was generated by the audit launched at 2026-10-06T00:10:21Z, i.e. 19:10 local (`dev_audit.pid` in bd09aa9).
- The diff from bab4b75 to e7afc0f changes only the duplicate-law key, S6 level C and the diagnostics flag.
- The depth-3 middle-layer order was fixed in code before development but is missing from the design record.
- The witness-grid change came after 2 development tasks, prompted by an S6 DUPLICATE reading; the superseded rows are kept. It changes no proposal.
- Selection under the old probe key vs the new witness key, all 40 dev tasks: identical on 38. Tasks 13 and 36 differ, but both picks are useful and behave as the generator's under either key.
- The addendum's reason is contradicted by the data: the witness key merges more, not less (coarser on 23 of 40 tasks; 161 vs 250 representatives).
- The change's real effect is on S6 (see M2).

**6. Leave-one-out leakage: NOT FALSIFIED.**
- Each fold is built without demonstration i before `solve` (`real_loo` 837-840), then re-proposed, re-selected and recompiled from scratch.
- `run_reasoner` uses a fresh temp directory, clears the engine caches, and its `kstar()`/`install()` snapshots are verified.
- The held-out demonstration is used only in `predict_exact`. Tests 12 and 13 pass.

**7. Proposal cache leakage: NOT FALSIFIED.** Every cache that survives between calls, and why none carries task data:
- `witness_grids` lru cache: no arguments, 64 fixed grids.
- `_D_CACHE`: keyed by the content hash of the frozen D file.
- `X._K_IDENTITY`: constant.
- `CV.manifest()` / `CV.vocab()` and `CP.probes()` lru caches: constant data.
- `Semantics._regions`: built and discarded per call.
- Fitter, meta_ast and meta_induction: no caches.
- geocat lru caches: cleared at the start of every engine run.
- Engine `ConceptLibrary`: one per engine instance, in a fresh directory.
- `guide_hook._rank_cache`: only active under ARC_GUIDE, which the environment check refuses.

**8. Compiler bypass: NOT FALSIFIED.**
- Only `paired_ablation` and `run_reasoner` install productions, always via `kstar()` + `install(load(serialize(prod)))`.
- `v17_compiler.py` sha256 is 04c6b3a1; its last change was 6fc3a4d (the v1.7 erratum).
- The fitter-level "useful" check and S6 evaluate fitted programs outside K*. This is declared as a diagnostic, not an installation.

**9. Step-B contamination: NOT FALSIFIED.**
- After solve, compile, S6 and the engine stage on dev task 0, loaded files came only from the pinned trees and site-packages.
- The Step-B path appears only in `cora_tti/freeze_pin.py`, which is never imported.

**10. Nondeterminism: NOT FALSIFIED (minor issue 13).**
- By code reading, the proposer and selection do not depend on the hash seed.
- The corpus generator does depend on it (`instantiate_tables` uses `hash(repr(value))`). This is guarded by `kstar_environment_problems()` in `main()`.
- Development results reproduced: the 40-task corpus, task 0's selection and S6 result, and task 0's engine stage at load about 33 on 24 CPUs (with e: accepted in 15.69 s; K* alone: not accepted in 8.11 s).
- The K* arm always hits its 8-second wall-clock budget, so leg B depends on machine load.
- P0 and D ties are handled deterministically.

**11. Unreachable or misassigned failure classes: FALSIFIED (minor issues 3 to 7, plus the outcome ladder under B1).**

**12. Selection-law fidelity: NOT FALSIFIED (minor issues 11, 12).**
- P0 reuses `p0_choice` unchanged; the "unique maximal" rule extends it to more than two candidates.
- With one differing position, D is exactly v1.6's margin: same row layout (1 + 19 standardized features + 5 state) and same token weights.
- The frozen D genuinely reproduces v1.6's numbers.
- The MDL guess is declared as new in the design record §5, protocol §6, the manifest and the development record.

**13. Ablation validity: FALSIFIED (this is B1).**
- *SHUFFLED_FRONTIER:* the donor's residuals are cell coordinates on the donor's grids, and a lower layer must cover them exactly (`v18_proposer.py` 391-394 and 403-410).
  - Of 1,092 donor tops considered, 788 have residual cells outside this task's grid.
  - Only 2 of 40 tasks have any donor top whose residual even lies within this task's changed cells.
- *DEMO_ONLY:* ranks blocks by recall of changed cells.
  - 364 of the 400 top-10 blocks are CONFLICT.
  - The generator's blocks rank 29th to 144th; the 256-proposal window reaches only rank sum 22.
  - So it removes the whole mechanism, not just the failure information.
- *Stronger controls* (same rule, same caps, HYBRID selection, my probe):
  - Donor statuses with residuals recomputed on this task's demonstrations: useful on 25 of 40.
  - A fixed task-independent random order of K's blocks: useful on 28 of 40.
  - FAILURE_CONDITIONED: useful on 40 of 40.

**14. Prospective script correctness: FALSIFIED (minor issues 6, 8, 9, 15, 16, 17).**
- Freeze and environment checks and the run-once guard work.
- G1, G2 and the outcomes are computed literally as §14 says.

**15. S6 law: FALSIFIED (this is M2).**

**16. Claim ceiling: FALSIFIED (partly).**
- There is no "novel", "invention" or "autonomous" claim, and no unconditional LEVEL 2 claim.
- But §1 (lines 28-29) and §15 (line 334) claim the frontier causes the useful proposals.
- The development record (lines 34-37) and RESUME present SHUFFLED's mechanical zero as "failure dependence".

### Verdict lists

**BLOCKING**

**B1. G1 cannot test failure specificity.**
- Both controls cannot propose by construction (item 13), and FAILURE_CONDITIONED is useful on nearly every task.
- So G1 passes exactly when FAILURE_CONDITIONED is useful on at least 5 tasks. With b useful tasks and zero for the controls, p = 2^-b; b = 5 gives 0.031.
- PROPOSER_WORKS_BUT_NOT_FAILURE_SPECIFIC and NO_ORACLE_PROPOSER_NOT_ESTABLISHED are therefore effectively unreachable.
- The two reachable outcomes both assert a failure specificity that was never tested.

*Smallest fix:*
1. Redefine SHUFFLED_FRONTIER as a coordinate-free transplant: keep the donor's statuses and codes, and recompute covered, changed, entries and residual on this task's own demonstrations for the donor's PARTIAL and FULL rows.
2. Add a BLIND arm: the same peeling rule and caps, with tops in a frozen task-independent order.
3. Set G1 = FAILURE_CONDITIONED against both new arms; keep the old arms as reported sanity checks.
4. Re-estimate G1 feasibility on development data. On the 40 dev tasks the discordant counts are 15 to 0 and 12 to 0, so G1 stays well powered.
5. Correct §1, §11, §13, §15, the development record and test 14.

**MAJOR**

**M1. Undisclosed leave-one-out conditioning in the corpus.**
- The corpus admits a task only if the generator's schema re-derives every training pair under fitter-level leave-one-out.
- This target-conditioned selection favours leg L and P0's first key for the generator-equivalent candidate. §15 discloses only the exact-fit conditioning.
- *Fix:* add a paragraph to §14/§15 saying L (and P0) are measured on tasks pre-selected for this, so L tests recovery and engine acceptance, not whether the task is identifiable.

**M2. S6 can never fail on this corpus.**
- A is true for any composition by grammar, B is guaranteed by the corpus filter, and C is SEPARATED for 161 of 161 distinct verified dev candidates on the witness grids (127 of 161 on the old probes; 7 of 40 selections would read DUPLICATE there).
- So "new semantic capability" is true by construction for every selected task, and the witness-grid change is what made C unfailable.
- *Fix:* state in §9/§15 that S6 is descriptive only and has no evidential weight here, and drop the "new semantic capability" wording for these counts.

**MINOR**
1. Development record line 43 says the proposal cap was never reached by the main arm. False: tasks 37 and 39 hit 256, and line 152 contradicts it.
2. The design-record §11 rationale for the duplicate law is contradicted by the data (item 5).
3. PROPOSAL_LIMIT uses only the last depth's cap flag (`v18_proposer.py` 713, 727-728).
4. PROPOSAL_LIMIT and NO_VERIFIABLE_PROPOSAL cannot occur in the main arm, because every proposal verifies. This should be disclosed.
5. K_ALREADY_SOLVES inside a fold makes leg L false (845-848), although the protocol calls that class "not a failure task".
6. Fold-level infrastructure failures count as L false. Fold leakage is not counted toward PROPOSER_LEAKAGE (prospective line 209). NO_VERDICT_RUN_ERROR outranks PROPOSER_LEAKAGE (211-216), although §14 says leakage overrides.
7. DUPLICATE_EXISTING_SEMANTICS is never assigned as an outcome.
8. Witness leg A is identical to B, because `predict_exact` returns False whenever the run is not accepted.
9. `run_task` fits the generator's schema before running the arms (lines 99-104); §14 says after. I found no causal channel.
10. Test 6 is vacuous: it compares two identical inputs (lines 120-123). Test 14 passes because of the mechanical failure. Test 15 checks only the Step-B path.
11. D's feature path is not covered by the reproduction check. On 120 stored v1.5 episodes, 3 differ by at most 3.3e-4 (rounding). D also runs on 6 or 7 demonstrations against a training mean of 4.96.
12. MDL's node-count key is constant within a depth, so the MDL guess is really entries followed by alphabetical text.
13. Leg B depends on machine load. *Fix:* record the load average per engine arm.
14. The `scan_input` docstring overstates what it checks: it accepts any well-formed frontier.
15. There is no policy for an interrupted run. START is written first, so a reboot mid-run forfeits the one-shot test.
16. Duplicate digests are allowed within the prospective corpus, and the seen/unseen audit compares only against the 40 dev structures.
17. Fold summaries drop the per-fold proposal counts that §8 says are recorded.
18. 32 leftover `/tmp/v17run_*` directories from earlier killed runs (none from this review). Harmless.

### Commands that executed code
Placeholders: `<venv>` = `cd /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026 && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti [timeout 590|595|600] .venv_arc2026/bin/python`; `<s>` = the scratch directory above.

Before the interruption:
1. `<venv> -m pytest tests/test_v18_proposer.py -q -p no:cacheprovider -m "not engine"`: 21 passed, 1 deselected.
2. `<venv> <s>/gen_dev.py 40`
3. `<venv> <s>/modpaths.py`
4. `<venv> <s>/controls.py 6`
5. `<venv> <s>/controls.py 40`

After the interruption:

6. `<venv> <s>/sel_s6.py 0 3`
7. `<venv> <s>/sel_s6.py 0 20`
8. `<venv> <s>/sel_s6.py 20 40`
9. `<venv> <s>/dpath.py`
10. `<venv> <s>/freeze_check.py` (calls `freeze_problems()` only, never `main()`)
11. `<venv> <s>/engine_mods.py` (two engine runs on dev task 0)
12. `<venv> -c "import tempfile; print(tempfile.gettempdir())"`

System `python3`, not the prescribed form; read-only JSON parsing, nothing written:

13. A `-c` one-liner inspecting `outputs/tti/v18_frozen_d.json`.
14. Heredoc scripts: four over `outputs/tti/v18_dev_rows.jsonl` (one also read `logs/v18/dev_rows_superseded_probe_witness.jsonl`), and two over my scratch outputs.
15. One heredoc over `outputs/tti/v15_test_corpus` that failed with JSONDecodeError.

Everything else was read-only shell: cat, sed, grep, ls, find, od, sha256sum, and git log/show/diff/status. `git status` was clean after every run.

### Access disclosures
- **Seeds:** only 840M dev seeds, the witness-grid seeds (9e12 + i) and the 810M v1.7 fixtures (via the test suite). Nothing at or above 860M; nothing in the 830M range.
- **Possible rule breach:** a `find` for non-Python files in `geocat_arc` printed file names under `geocat_arc/artifacts/geocat_arc/diagnostics/<ARC task id>/`, including `target_outputs.json`. I opened no contents. This may breach the "no listing" rule.
- **External tti manifest:** `freeze_problems()` hashes `Reasoning_Project_tti/outputs/tti/constructive_protocol_manifest*`, and the frozen code reads that manifest on every run.
- **Stored v1.5 records:** `dpath.py` read stored synthetic v1.5 records in `outputs/tti/v15_test_corpus`.
- **Temp directories:** the engine runs created and then removed temporary directories in `/tmp`.
- **Leftover directory metadata:** I listed only the names and times of the leftover `/tmp/v17run_*` directories.
