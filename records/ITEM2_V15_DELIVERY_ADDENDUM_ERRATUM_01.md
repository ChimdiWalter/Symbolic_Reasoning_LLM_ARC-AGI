# Item-2 v1.5 delivery addendum, erratum 1: launch path of the verification diagnostic

Recorded 2026-09-28 at about 21:40 UTC, while the frozen v1.5 generator
(PID 2819761, chain 2819666) was running. No v1.5 score, margin or test-set
statistic existed or was read. No test-corpus record was opened for this
erratum.

## Defect

`scripts/v15_supp_verification.py` (delivery addendum (c), commit 5a9077c)
cannot run as frozen:
- `main()` imports `cora_tti.scoped_slot_fitting` before it loads the
  evaluator;
- the tti root (`Reasoning_Project_tti`) reaches `sys.path` only when
  `cora_arc2026.v13_gen` is imported, which happens inside the evaluator
  load;
- the addendum tests exercise `three_valued` and `expected_boolean` only,
  never `main()`, so the tests did not catch it.

Evidence, from a smoke run with the evaluator pointed at an empty
directory (scratch driver, no project file changed):
- plain launch: `ModuleNotFoundError: No module named 'cora_tti'`, exit 1;
- launch with `PYTHONPATH=<tti root>`: exit 0, 0 episodes,
  `verification_conclusions` UNQUALIFIED.

## Correction

The launch path changes; no file changes:
- the diagnostic is run with `PYTHONPATH` set to the tti root;
- the script, its sha256 in `outputs/tti/v15_delivery_addendum.json`, the
  v1.5 manifest and every frozen file are unchanged.

Why this is equivalent: `v13_gen` inserts the same tti root on `sys.path`
one line later, and the working tree stays ahead of it. Checked by
experiment:
- the project modules were loaded in the generator's order
  (`v15_sel` first, then the fitter) and in the corrected verification
  order;
- the two module lists, with their files, are byte-identical: 46
  modules, all 24 `geocat_arc` modules from the arc2026 tree;
- `scripts/` shares no module name with the tti root;
- the fitter's own path entry `<tti root>/src` holds only
  `reasoning_project`.

The other inputs of the recomputation were checked against the generator
source, and match:
- seed arithmetic: `TEST_BASE`, `SLOT_STRIDE`, `ATTEMPT_STRIDE`;
- the anchor and contrast derivation;
- the other-candidate choice;
- the demonstration fields;
- the fitter call.

## Post-generation order

Set by the user on 2026-09-28:
1. integrity only;
2. the three-valued verification diagnostic;
3. the sealed evaluation twice with a byte comparison
   (`scripts/run_v15_evaluation.sh`, unchanged);
4. the dependence sensitivity for gate C.

The official verdict is recorded separately from the supplementary checks.

`scripts/run_v15_post_generation.sh` runs exactly this order after the
generation chain ends:
- it waits on the chain PID and never signals it;
- it gives `PYTHONPATH` to step 2 only;
- it stops at the first failure, writing `logs/V15_POSTGEN_BLOCKED`, so no
  score is computed after a failed earlier step;
- it writes `logs/v15_postgen/STATUS.txt` and, on success,
  `logs/V15_POSTGEN_DONE`;
- it records no verdict, edits no record and makes no commit.

It is not part of the v1.5 manifest and sits outside every digested tree,
so the generator's per-slot freeze check is unaffected.
