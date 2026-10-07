# Item-2 v1.9: the one adversarial review (result, verbatim)

Request: `records/ITEM2_V19_REVIEW_REQUEST.md` (4a5006f). Frozen commit
276583d, manifest 26e63d79. One reviewer, launched 2026-10-07T00:50Z,
interrupted by an API session limit after about 12 minutes, resumed as the
same agent from its own transcript at 17:25Z, report returned at about
17:30Z.

## Access audit (by the requester, from the reviewer's transcript)

All 90 tool calls (83 Bash, 6 Read, 1 hand-back) were scanned from the
transcript's tool inputs, not from the self-report:
- no access to `pipeline/Reasoning_Project` (Step B), VDCG, E_transfer, a
  Lockbox, `data/arc` or any ARC file (those names occur only in the
  report text);
- no seed at or above 880,000,000 generated (the one match is a `grep`
  for the constant in the code), nothing in the 860M or 830M ranges;
- no execution of `scripts/v19_prospective.py` main, `--worker` or
  `--resume`: the two matching commands import it to call
  `freeze_problems()` and run `tests/test_v19_prospective.py`;
- 20 Python executions: reads of committed JSON, statistics, the two
  `freeze_problems()`, the allowed test suites (8 engine runs on 810M and
  870M fixtures), and the frozen verifier on synthetic rows with the corpus
  stubbed;
- no Write or Edit call, no redirection into the repository, no writing
  git command, no process signal, no crontab use; no repository file
  modified after its launch (tracked hashes equal the pre-review snapshot
  except the requester's own RESUME and ledger commit 1a5c537); scratch
  files only under the session scratchpad `v19_reviewer/`.

## Report (verbatim)

ADVERSARIAL REVIEW OF THE FROZEN v1.9 PACKAGE (frozen commit 276583d, HEAD 1a5c537)

1. VERDICT: BLOCKING_DEFECTS

There is one blocking finding. A text erratum and a re-freeze fix it. Nothing needs redesigning and no development measurement needs repeating. I found no leakage, no bug in the gate arithmetic and no problem with the module move. Both freeze_problems() calls return [].

2. FINDINGS

Finding 1. SEVERITY: BLOCKING. Threshold lowering, and the safety gate (G4) relaxed after the development data came in (targets 5 and 3).

Claims falsified:
- Protocol section 14, lines 302-304: K*-4 is "not ... a lower acceptance threshold".
- Section 17, line 560: the witness rate "clears the frozen threshold without a measured safety cost".
- Section 15a, lines 402-427, as a record of how G4 came to be. It calls a Wilson-bound version "a first draft" (line 414).

Evidence:
(a) The effective acceptance threshold is lower.
- K* needs every key witnessed by 3 of the run's demonstrations to pass its own leave-one-out. K*' needs 2. The review request says this itself (item 5).
- In every v1.9 measurement, K*' accepted every installed extension it was given:
  - FULL runs: 30 of 30.
  - Same-e folds: 210 of 210.
  - Adaptive leave-one-out folds with an installation: 208 of 208 (206 right, 2 wrong).
  - Four-demonstration trials: 43 of 43, including 19 of 19 wrong.
  - Total: 491 of 491. Sources are the records/ITEM2_V19_REPAIR_DEVELOPMENT.md tables and my recount from outputs/tti/v19_repair_dev_rows.jsonl.
- False acceptances rise wherever wrong candidates exist:
  - Four demonstrations: 6 of 19 under K*, 19 of 19 under K*'.
  - Wrong certified adaptive folds: 1 under K*, 2 under K*'. The extra one is task 18 fold 0, a D selection that K* rejected.
(b) The gate history in git.
- Commit 4af2bd1 (18:45:06 -0500) was made before the ablation result. In it, G4 was strict counts at three levels. It included `checks["false_acceptance_folds"] = fold_fa_new <= fold_fa_old` (scripts/v19_prospective.py:316 at that commit). Its inertness check also compared events (line 293).
- The ablation result, af4b7c1 (19:23:45), has 2 wrong certified folds under K*' against 1 under K*, and an event mismatch on task 3. The gate as committed would therefore have returned REPAIR_UNSAFE on the development data.
- Commit df851c7 (19:26:02), 2 min 17 s later, replaced the strict counts with: precision at least 0.95, and at least K* precision minus 0.02. Development reads 236/238 against 159/160, which passes. The same commit dropped events from the inertness check.
- The 15a text describes a Wilson-bound "first draft", which was never committed. It does not say that the committed draft before the result was the strict count, or that the development data failed it.
(c) Tolerance. With K* at 159/160 and about 238 certified outputs under K*', G4 still passes with up to 6 wrong certified outputs. That is six times K*'s count. At the v1.8-like K* rate (2 wrong of about 154), up to 7 pass.
(d) At six or seven demonstrations, wrong verified candidates are essentially absent: 15a.1 found 0 in 30 tasks. So the precision gate measures the proposer, not the engine. A variant that skipped the engine's leave-one-out for installed extensions would pass G2, G3 and G4 in the same way.
(e) Section 16 (line 528) pre-registers, for the reduced control: "K*' accepts at least as many wrong extensions as K*". That is a measured safety cost, which section 17 then says is absent.

Assessment of the three post-development changes:
- Events to decisions in the inertness check: sound. With nothing installed, the patched functions pass straight through (v19_repair.py:84-91, 102-106). Plain K* itself varied 1 time in 3 in logs/v19/inert_probe.log.
- Wilson bound to point estimate: sound for its stated reason, and not needed to pass (the Wilson lower bound for 236/238 is about 0.97).
- Strict counts to precision: answers a real noise problem (1 against 2 events). But it was made right after the committed gate failed on development data, its thresholds were chosen with the development values known, and it is far looser than the noise problem needs.

Smallest fix (erratum before the run, no remeasurement):
1. Section 14: state the real effect. For installed extensions the evidence requirement drops from three witnesses per key to two. The installed concept ranks first in every ranking. In development, K*' accepted 491 of 491 installed extensions.
2. Section 15a: record the G4 history as committed (4af2bd1, then af4b7c1 failing it, then df851c7). Give the tolerance in counts.
3. Section 17: delete "without a measured safety cost". Say that a positive outcome shows the pipeline is stable under held-out checks, not that the engine discriminates installed extensions.
4. Optional, if the directive's rule is meant to be a gate (the user's call): add one pre-specified criterion on added false positives. Example: added wrong certified outputs at most 0.05 times added correct ones. Development has 1 added wrong against 77 added correct, which passes.

Finding 2. SEVERITY: MAJOR. The corpus law largely fixes the prospective gain in advance (targets 6 and 9).

Claim weakened: that G3 and G2 measure an engine-stability improvement on new data.

Evidence:
- scripts/v18_corpus.py:55-67 admits a task only if the target's scoped fit (two witnesses per key) re-derives every training pair under leave-one-out. That forces every target key to be witnessed by at least 3 of the 7 training pairs.
- A six-pair adaptive fold re-induced by K* needs at least 3 witnesses among those 6, which means at least 4 among the 7 when the fold holds out a witness.
- K*' needs only 2 among 6, that is 3 among 7: exactly what the corpus guarantees.
- My dev probe (census only, no engine) measured the smallest witness count among the selected e's keys over the 7 pairs:

| smallest witness count | tasks | K* leave-one-out passed | K*' leave-one-out passed |
|---|---|---|---|
| 3 | 11 | 0 of 11 | 9 of 11 |
| 4 or more | 19 | 12 of 19 | 17 of 19 |

- The count was never below 3. So most of the fitting-clause rescues follow from arithmetic.

Smallest fix: say this in sections 16-17. Report the witness-count strata as a descriptive split; it can be computed post hoc from the task file with v19_audit.census, no rerun. Limit the LEVEL 2 claim to tasks where each key has at least 2 witnesses in the run.

Finding 3. SEVERITY: MAJOR. The four-demonstration "no discrimination" inference is overstated (target 5).

Claims falsified:
- Section 15a: the old rejections "were indiscriminate: they cost recall without buying safety".
- Section 16 expectation: "neither logic discriminates".

Evidence:
- Under K*, 8 of 24 right against 6 of 19 wrong were accepted. The difference is 0.018, with a Newcombe 95% interval of -0.25 to +0.28; Fisher's two-sided p is 1.0.
- The wrong trials come from only 9 tasks, and K*'s decision was the same for every trial within a task (6 multi-trial groups, 0 mixed). The effective sample is about 9 tasks, not 19 trials.
- Right trials are selections and wrong trials are pool candidates, so the two groups also differ in source.
- In the 6 tasks that had both kinds, K* accepted the right one and rejected the wrong one once (task 1), and never the reverse.

Smallest fix: reword to "no discrimination detected (43 trials, 30 tasks, clustered by task)". Do not cite it as the reason for not gating false acceptances.

Finding 4. SEVERITY: MINOR. The verifier raises a false alarm on a legal row type (target 7).

Evidence:
- probe_verifier.py (synthetic rows, corpus stubbed) includes one COMPILE_FAILURE row.
- The script counts P = 29 in legs_new; the verifier counts 28. The verifier then reports all_checks_pass False on legs_equal, although both give the same outcome.
- Cause: verify_prospective.py:86-88 returns None for rows without "old". The script sets witness_new P True for those rows (v19_prospective.py:227) and counts it at line 497.

Smallest fix: in the verifier, count P from the arm class.

Finding 5. SEVERITY: MINOR. freeze_problems() never checks the protocol hash (targets 7 and 8).

Evidence: v19_prospective.py:87-117 has no protocol_doc_sha256 check; v18_prospective.py:64-65 has one. The verifier relies on this function (verify_prospective.py:34). The protocol currently matches c8afba41.

Smallest fix: add the check.

Finding 6. SEVERITY: MINOR. Controls that are only reported can void the whole run (target 6).

Evidence:
- wrong_extensions() (v19_prospective.py:169-203) and FR.trials() (v19_falseaccept_reduced_dev.py:61-88) call P.propose, verify and dedupe under the 180 s wall-clock limit, and call X.compile_extension.
- Neither catches ResourceExhausted or CompileError. The exception reaches worker() at lines 405-409, which writes an error row, so the one-shot run ends as NO_VERDICT_RUN_ERROR.
- The risk is low: the slowest proposer run in development took 23.4 s (main arm) and 22.2 s (folds).

Smallest fix: catch and record the failure inside these two controls.

Finding 7. SEVERITY: MINOR. Crash and resume (target 6).

Evidence:
- A worker that dies without a Python exception (OOM kill, segfault) leaves a missing row. The coordinator still writes the report and marker (lines 472-519) as NO_VERDICT_RUN_ERROR, after which --resume is refused (line 421).
- Only the final coordinator writes resumes into the report (lines 435-437, 490-492), so an earlier resume is lost. The protocol's "every resume is recorded" is not guaranteed.
- The verifier's check is only `isinstance(..., list)` (line 69).
- Resuming while old workers are still alive produces duplicate rows.
- A truncated last line in the rows file makes read_rows() raise, which blocks the resume. A corrupt claims file (a worker dying mid-write) makes claim() raise in the other workers.

Smallest fix: check worker exit codes and leave the run resumable after an abnormal exit; append each resume to a log file when it happens; refuse to resume while a recorded worker PID is alive; tolerate a truncated last line.

Finding 8. SEVERITY: MINOR. G3's pairing assumption is never checked (target 6).

Evidence: the paired G3 assumes the proposer makes the same selection in each fold under K* and K*'. In development that held in 210 of 210 folds (selected, production and input sha). Neither the script nor the verifier checks it.

Smallest fix: report and verify the number of folds where selected or production differs between loo_old and loo_new.

Finding 9. SEVERITY: MINOR. no_regression_full can call a correct switch unsafe (target 6).

Evidence:
- v19_prospective.py:298-300 requires an identical program whenever K* + e is accepted with an exact held-out pair, even when K*'s winner is a native program.
- K*' ranks the installed concept first in rank_by_score (v19_repair.py:84-99; inducer.py:3630-3633). A correct switch from the native program to the extension would therefore read as REPAIR_UNSAFE.
- None of the 161 accepted K* + e runs in development had a native winner, so this is rare.

Smallest fix: require program identity only when K*'s winner uses e; otherwise require the held-out pair to be exact.

Finding 10. SEVERITY: MINOR. Wording of the repair (target 3).
(a) "One rule". The diagnosis shows two mechanisms in largely separate runs: fitting only 38, ranking only 38, both 3. So section 14's "the clauses are not separable repairs of separate mechanisms" (lines 285-286) is inaccurate. It is a two-clause repair under one principle, and both clauses are disclosed.
(b) The v19_repair.py docstring (lines 37-39) says the repair "Applies to installed productions with two or more blocks". The code has no block-count condition. The ranking clause applies to every installed concept. The fitting clause applies to any production that K*-2 sends to the scoped fitter, including one-block productions with zero or several Selects. This does not matter for the proposer's 2-3 block, one-Select compositions.
(c) Sections 4 and 14 still name cora_arc2026/v19_*.py.

Smallest fix: correct the wording.

Finding 11. SEVERITY: MINOR. Edge cases in the diagnosis labels (target 2).

Evidence:
- census() leaves out the fitter's coverage and hidden-key rules. The fitter checks blocks in order, so a SLOT_FIT_FAILED:witness can hide a later block's hidden-key refusal. permissive_predicts (and so H1) can then be true where the one-witness fitter would still refuse.
- reason_codes would also assign fold-level concept codes in a run where only native programs fit at the top level.
- Neither happened in development: K*' accepted 210 of 210 same-e folds. The H1/H2 split depends on the one-witness standard, as the addendum discloses.

Smallest fix: add a note to the diagnosis record.

Finding 12. SEVERITY: MINOR. Launch hygiene (target 9).

Evidence: the tree at HEAD is not clean.
- logs/v19/v19_watch.log has two lines written at 00:22Z, before the freeze commit, that were never committed.
- logs/v19/run_engine_tests.sh is now modified. That happened during your current test run, not by me.
- Neither file is pinned.

Smallest fix: if the launch needs a clean tree, as v1.8's did, commit or restore both first.

Checked, no defect:
- Target 1 (tracing):
  - The wrappers pass arguments and return values through unchanged and re-raise exceptions; their only effect is timing.
  - K*'s snapshot is consistent inside traced(), and the prospective script does not trace.
  - test_traced_run_equals_untraced_run passes on my re-run.
- Target 3 (the repair is generic and inert):
  - There is no task, family, seed or extension branch.
  - With nothing installed it is inert (test re-run passes).
  - R.restored() is True after my runs.
- Target 4 (leakage):
  - The engine and the proposer see training pairs only.
  - Held-out pairs are used only after acceptance, and to pick wrong candidates for the control.
  - The 880M base appears only as v19_prospective.py's generator base.
- Target 6 (corpus and exclusion):
  - The exclusion set is exactly 3,847 + 54 = 3,901 digests.
  - The run-once refusals are in place.
  - W_MIN 19 and DELTA_MIN 6 follow the rules in v19_feasibility.py, which is unchanged since c2584a2; P(X >= 19 | 0.40) = 0.0083.
- Target 8 (module move):
  - v19_trace.py and v19_repair.py are byte-identical to the evidence versions; v19_audit.py differs only in its import line.
  - The repair identity in all 30 dev rows is e4672bfa, matching the manifest.
  - Protocol sections 1-13 are byte-identical to 81065a3, and sections 14-15 to 1e5937e.
  - v18 freeze_problems() returns [].

3. PROBES RUN AND FILES WRITTEN

Every command that executed project code ran from the repository with: TMPDIR=<scratch>/tmp PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti .venv_arc2026/bin/python. No ARC_* variable was set.

1. probe_freeze.py: v19 and v18 freeze_problems(), k_identity, repair_identity, restored(), protocol hash. Results: [] and [], b009a9fb, e4672bfa, True; the protocol hash matches.
2. `pytest -p no:cacheprovider -q tests/test_v19_prospective.py tests/test_v19_audit.py tests/test_v19_repair.py -m "not engine"`: 27 passed, 4 deselected.
3. `pytest -p no:cacheprovider -q tests/test_v19_audit.py tests/test_v19_repair.py -m engine`: 4 passed in 106.7 s. These are 8 engine runs on v1.7 fixtures (810M) and committed v1.9 dev folds (870M).
4. probe_witness_arith.py: dev corpus and rows, census only, no engine.
5. probe_verifier.py: synthetic rows, v18_corpus stubbed so nothing was generated, frozen verifier run via runpy, no engine.

Totals: 8 engine runs. Nothing at seeds of 880M or above, nothing in the 860M or 830M ranges. Nothing touched Step B, VDCG, E_transfer, the Lockbox or ARC data. Your background pytest run was not touched.

Other commands were read-only: git log, show, diff and status; file reads; and system python3 reading committed JSON for counts and the Fisher and Newcombe statistics, with no project imports.

Files written, all under /tmp/claude-100350790/-deltos/1a86a57b-d764-4f47-a834-c23a0c91436c/scratchpad/v19_reviewer/:
- probe_freeze.py
- probe_witness_arith.py
- probe_verifier.py
- protocol_81065a3.md, protocol_1e5937e.md, protocol_276583d.md (git show copies)
- verifier_case/ (5 synthetic files)
- tmp/ (empty; used as TMPDIR for engine temp dirs)

Nothing was written inside the repository.
