# VF1 stage A: code, tests and development rehearsal

Author: Chimdi Walter Ndubuisi. Specification: `PROTOCOL.md` (the frozen text; `PROTOCOL_DRAFT.md` is the earlier
draft with its amendment block). CPU only, invented inputs, no model.

**This is a development study.** The operations study's outcomes for these same operations were known before this
protocol was frozen, so it is not an untouched confirmation over operations. All numbers from the development roster
are "development only". Arm H's program text names the missing operation, so H is a budget mixture of V and S and not a
clean test of localisation. A consumer whose `post` loses information cannot identify X; that is why "correct" is always
checked directly against X and kept apart from "reused". Method credit: bottom-up enumerative synthesis with
observational equivalence is standard (TRANSIT, 2013; Escher, 2013); completing a program with a hole is program
sketching; the library is arc-dsl by Michael Hodel (MIT). Nothing new is claimed about the method.

## Files
- `presets_vf1.py`: every preset (example counts, record sets, seeds, size limits, CPU allowance B, development roster).
- `frozen.py`: imports the frozen operations-study modules read-only; refuses to run if the sha256 of `dslx.py`, `gen.py`,
  `search.py`, `presets.py` (or `core.py`) differs from its `FREEZE.json`.
- `vsearch.py`: a copy of the frozen enumerator with exactly two changes (acceptance hook, collect up to k fits).
- `consumers.py`: candidate `post` operations (seeded order), pooled sequence and streams, guard, preservation bank.
- `gate.py`: lesioned consumer fails, intact passes, true X passes, trivial repairs fail.
- `episode.py`: one target: setup, observe, decide, propose, verify, admit, reuse, final reading; arms V, S, H, T; controls;
  diagnosis material; JSONL journal (`journal/<target>.jsonl`) and result (`targets/<target>.json`).
- `library.py`: read-only (0444) library files with hash checks.
- `summarize.py`: `SUMMARY.json`. `run_stage_a.py`: deterministic, resumable runner; `--make-freeze` writes a hash manifest
  (it covers the code, the frozen modules and inputs, `PROTOCOL.md`, `README.md` and every `tests/*.py`, and refuses when
  `PROTOCOL.md` does not exist).
- `tests/test_stage_a.py`: fast tests on invented cases and fresh-process refusal tests.
- `dev_out/`, `dev_out2/` and `dev_out3/`: the three development rehearsals (the first two under earlier rules):
  development only.

## Five disjoint record sets per target (66 generator examples; the first 36 are the operations study's)
Each set is sealed (sha256 journalled) before the next step:
1. setup, generator 18-35: used only to choose the three `post` operations (runs on X's result, at least 2 distinct final
   outputs, no trivial repair passes; the first three in the seeded order; fewer than three: the target is excluded,
   never padded);
2. acquisition, generator 0-2: the three shown examples (gate on these; a trivial repair there means a redraw from the
   pooled setup stream, else exclusion; redraws and exclusions happen only at setup, before any search);
3. admission, generator 3-14 and pooled stream A (12 usable): the grid at n = 3, 6, 12 (nested), opened only after the
   candidates are sealed. THE RULE (`adm_both` at n = 6): the admission consumer exact on 6 generator inputs AND on 6
   pooled inputs, plus a preservation bank in which only entries that run and give a value before admission count (at
   least one is required). The other standards (more of the same, admission consumer on generator inputs alone, on pooled
   inputs alone, none) stay in the grid as measurements;
4. reuse support, generator 15-17: the reuse-task examples of the controls, opened only after the libraries are sealed;
5. final, generator 36-65 and pooled stream B (usable for X and for both posts): produced and read only in the last step.
Pooled tuples are unique, disjoint from every generator tuple of the target, and the five pooled slices are disjoint
(setup redraw R, admission A, final B, and two setup-usability slices UA and UB of the same sizes as A and B). Before any
search, UA must give at least 12 usable draws for the admission consumer and UB at least 30 for the acquisition and reuse
consumers together, else the target is excluded at setup ("too few usable pooled inputs"). A shortage that still appears in
A or B is only flagged, never an exclusion.
Tasks are constructed so that the missing operation matters on the setup examples; this uses the evaluator's knowledge of X
to build the task, and nothing of it is shown to the system. Arm T uses generator 0-5 as its six declared examples, so it
shares three inputs (3-5) with the admission grid; T's admission is reported apart.

## Endpoints
- PRIMARY: exact outputs of the acquisition task on its final panel (30 generator plus pooled), same panel for V and S, each at
  allowance B. V: its first fit composed with the retained acquisition `post` (no admission needed). S: its whole program.
  Paired by target outside the development roster; exact two-sided sign test.
- SECONDARY, declared: the reuse task on the same final panel for every arm: retained (V's admitted operation, no search, no
  support examples) against S's fresh synthesis from the three support examples at B and the no-retention control.
  The 10 B search is a conditional comparison (only where V admitted something).
- Capability outcomes (fit, admitted, correct, reused) for V, H, T stay apart. S is not scored on capability; only whether
  its program contains a stand-in for the call is recorded.
- The first fit of an arm is frozen; if it fails the rule, nothing else is tried for that arm.
- Costs: physical CPU per arm and target, and the counterfactual CPU to the first fit, are reported separately; the retained
  lifetime cost lists its parts once.

## Run (from the repository root)
    env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B -m pytest -q -p no:cacheprovider experiments/visible_failure_20261113/tests
    env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B experiments/visible_failure_20261113/run_stage_a.py <outdir> --roster dev [--targets a,b] [--B seconds]
`--roster all` refuses without `--freeze <FREEZE.json>`, and refuses a second output folder once a receipt exists. It is not
to be run before the freeze. Test hook: `VF1_EXPERIMENT_DIR` moves the receipt folder; when set, the output folder must lie
inside it, the override is written into MANIFEST.json and the receipt, and the real experiment folder's receipts are still
consulted.
