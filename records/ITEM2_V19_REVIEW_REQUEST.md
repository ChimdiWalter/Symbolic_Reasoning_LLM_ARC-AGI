# Item-2 v1.9: the one adversarial review (request)

Written 2026-10-07 at the freeze.

**Rules for the reviewer:**
- Work read-only on the frozen commit named below. Write nothing inside the
  repository; scratch files only under
  `/tmp/claude-100350790/-deltos/1a86a57b-d764-4f47-a834-c23a0c91436c/scratchpad/v19_reviewer/`.
- No access to Step B (`pipeline/Reasoning_Project`), VDCG, E_transfer, the
  Lockbox, or any ARC answer, solution, challenge or holdout file (this
  includes `data/` directories with ARC JSON and the engine test
  `geocat_arc/object_reasoning/tests/test_segmentation_features.py`).
- In `Reasoning_Project_tti`, read only the frozen dependency source trees
  `cora_tti`, `cora_parent` and `level4_blind_runtime`.
- Do not run `scripts/v19_prospective.py` (no `main()`, no `--worker`, no
  `--resume`) and do not run anything over generator seeds at or above
  880,000,000; that range is reserved for the one prospective run. Calling
  `freeze_problems()` alone is allowed.
- Do not regenerate or run anything over the v1.8 prospective seeds
  (860,000,000 range) or the v1.7 acceptance seeds (830,000,000 range).
- Allowed: synthetic probes of your own on the v1.9 development range
  (870,000,000 + 100k), the v1.8 development range (840,000,000 + 100k) and
  the v1.7 development fixtures (810,000,000 range); the test suites
  `tests/test_v19_audit.py`, `tests/test_v19_repair.py`,
  `tests/test_v19_prospective.py`.
- Use `PYTHONHASHSEED=0`,
  `PYTHONPATH=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti`
  and `.venv_arc2026/bin/python`; do not set any `ARC_*` variable.

Every tool call is scanned afterwards; a self-report of restraint is not
evidence.

## Frozen objects

- Frozen commit `276583d` (Reasoning_Project_arc2026).
- Manifest `outputs/tti/engine_stability_v19_manifest.json`, sha256
  `26e63d798ab21773b14eec7a8f8d0ced56524ce2879617c024db5190ca7c4f24`
  (37 pinned files, 6 dependency trees, K*, K*', exclusion, thresholds).
- Protocol `docs/CORA_TTI_ENGINE_STABILITY_AUDIT_v1.9.md` (sections 1-13
  pre-frozen at 81065a3 before any measurement, byte-identical since;
  14-15 before the ablation at 1e5937e; 15a, 15b, 16-18 afterwards).
- Repair `cora_v19/v19_repair.py`; K* identity `b009a9fb`; K*' identity
  `e4672bfa...` (`v19_repair.repair_identity()`).
- Prospective exclusion `outputs/tti/v19_prospective_exclusion.json` (3,901
  digests).

## What to read, in order

1. `records/ITEM2_V18_PROSPECTIVE_RESULT_20261006.md` (the blocker).
2. `docs/CORA_TTI_ENGINE_STABILITY_AUDIT_v1.9.md`.
3. `records/ITEM2_V19_AUDIT_DIAGNOSIS.md` (with its addendum),
   `records/ITEM2_V19_REPAIR_DEVELOPMENT.md`, `records/ITEM2_V19_FEASIBILITY.md`.
4. `cora_v19/v19_trace.py`, `cora_v19/v19_audit.py`, `cora_v19/v19_repair.py`.
5. `scripts/v19_audit_dev.py`, `scripts/v19_audit_analyze.py`,
   `scripts/v19_repair_dev.py`, `scripts/v19_falseaccept_dev.py`,
   `scripts/v19_falseaccept_reduced_dev.py`, `scripts/v19_clause_safety_dev.py`,
   `scripts/v19_feasibility.py`, `scripts/v19_prospective.py`,
   `scripts/freeze_v19.py`, `logs/v19/verify_prospective.py`.
6. The tests above.
7. What it relies on: `cora_arc2026/v17_compiler.py` (kstar, install,
   run_reasoner, paired_ablation, uses_extension), `cora_arc2026/v18_proposer.py`,
   `scripts/v18_corpus.py`, `geocat_arc/object_reasoning/inducer.py`
   (induce_program, loo_validate, rank_candidates, rank_by_score,
   _induce_composed), `geocat_arc/object_reasoning/meta_induction.py`,
   `cora_tti/scoped_slot_fitting.py`.
8. The git history of the v1.9 files (`git log --stat 3ed21bf..276583d`), to
   check what was fixed before and after each measurement.

## Try to falsify each of these

1. **Observation-only tracing.** Can any wrapper in `v19_trace.py` change a
   decision (timing, arguments, return values, exceptions, K*'s snapshot)?
   Is the decision-identity evidence (12 untraced runs, one engine test)
   adequate?
2. **Reason codes and mechanisms.** Are the codes in `v19_audit.reason_codes`
   correct for every branch of `induce_program`? Is the census faithful to
   the fitter? Is the H1/H2 classification sound, given its dependence on
   the one-witness standard (diagnosis addendum)?
3. **The repair is one, generic, bounded and inert.** Any task, family,
   seed or extension-specific branch? Does it change K* alone in any way
   (decisions, state)? Is calling two clauses "one rule" honest? Does it
   leave the engine's gate unchanged as claimed?
4. **Leakage.** Can the repaired path, the proposer or the harness read the
   generator's target, a held-out output, or a prospective seed? Is the
   held-out pair ever visible to the engine during acceptance?
5. **Threshold lowering.** The repair lowers the effective evidence
   requirement for installed extensions (three witnesses to two). Protocol
   15a reports that under four demonstrations no logic discriminates right
   from wrong installed extensions. Is the resulting choice (precision gate
   over certified outputs; four-pair control reported, not gated)
   defensible against the directive's "do not count a repair that merely
   lowers the acceptance threshold and increases false positives"? Were the
   post-development gate changes (strict counts to precision; Wilson bound
   to point estimate; inertness on events to decisions) made for sound
   reasons or to pass?
6. **Prospective design.** Corpus law, exclusion set, the reserved range,
   run-once and resume, multi-worker claims (duplicates, missing rows,
   crash recovery), determinism under load (the proposer's 180 s
   wall-clock limit), witness legs, G1 to G4, the outcome ladder,
   thresholds fixed by rules written before their inputs.
7. **Verifier independence.** Does `logs/v19/verify_prospective.py`
   recompute every gate itself, or does it trust the report?
8. **The module move.** Does it preserve the code that produced the
   evidence? Is v1.8 untouched (its `freeze_problems()` returns [])?
9. Anything else that would make the prospective result uninterpretable.

## What to return

A verdict (PASS, PASS_WITH_DEFECTS or BLOCKING_DEFECTS) and numbered
findings, each with a severity (BLOCKING, MAJOR or MINOR), the evidence
(file and line, or the probe you ran and its output), and the smallest fix.
List every probe you ran and every file you wrote.
