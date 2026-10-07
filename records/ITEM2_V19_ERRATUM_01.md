# Item-2 v1.9: erratum 01 (answer to the one review)

Written 2026-10-07, after the review (`records/ITEM2_V19_REVIEW_RESULT.md`,
BLOCKING_DEFECTS) and before any prospective data. No development
measurement was repeated; no threshold of G1, G2 or G3 changed; the repair
code (`cora_v19/v19_repair.py`) is byte-identical, so K*' keeps the identity
of the development evidence (e4672bfa). The erratum itself is not reviewed
again (one-review rule).

| finding | severity | judged | action |
|---|---|---|---|
| 1 threshold lowering; G4 relaxed after the development data | BLOCKING | genuine | Protocol 14: states that K*-4 lowers the effective threshold (three witnesses per key to two; no native candidate can displace a verified installed concept; 491 of 491 installed extensions accepted in development) and removes the false "not ... a lower acceptance threshold". Protocol 15a: records the G4 history as committed (4af2bd1 strict counts; af4b7c1 would have failed it; df851c7 precision rule chosen with the development values known; the Wilson variant never committed) and the tolerance in counts (up to 6 wrong certified outputs). Protocol 17: deletes "without a measured safety cost". The optional criterion is ADOPTED: G4 now also requires marginal precision, added wrong certified outputs at most 0.05 times added correct ones (development 1 against 77). It only tightens the gate. |
| 2 the corpus law fixes much of the gain | MAJOR | genuine | Protocol 17 states the arithmetic (every target key has at least three witnesses by construction; K*' needs two of six) with the development strata (3 witnesses: K* 0/11, K*' 9/11; 4 or more: 12/19, 17/19) and limits the LEVEL 2 claim to tasks where every key of the extension has at least two witnesses in each run. The prospective script records `min_key_witnesses` per task (census of e on the seven pairs) and reports and verifies the strata. |
| 3 four-pair "no discrimination" overstated | MAJOR | genuine | Protocol 15a, 16, 17 and the diagnosis and development records now say "no discrimination detected (43 trials, 30 tasks, clustered by task)" with the interval, and no longer cite it as the reason for not gating; the reason given is that the control measures the engine's acceptance of deliberately installed wrong extensions, which K*-4 raises by design, while the safety decision rests on the system's own certified outputs. |
| 4 verifier P count on selected-but-uncompiled rows | MINOR | genuine | `logs/v19/verify_prospective.py` counts P for such rows; new `tests/test_v19_verifier.py` runs the verifier end to end on synthetic rows including a COMPILE_FAILURE and a RESOURCE_EXHAUSTED row (all checks pass) and on a tampered report (caught). |
| 5 protocol hash not checked | MINOR | genuine | `freeze_problems()` now checks the protocol hash. |
| 6 reported controls can void the run | MINOR | genuine | `wrong_extensions()` and the four-pair control catch and record failures in the row (`wrong_trials_failure`, `reduced.failure`); counted in `supplementary.control_failures`. |
| 7 crash and resume | MINOR | genuine | Claims written atomically; rows reader skips and counts an unparsable line (its task then counts as missing); each resume appended to `logs/v19/prospective_resumes.jsonl` when it happens and carried in full by the report (the verifier compares them); resume refused while a recorded coordinator or worker PID is alive; worker exit codes recorded, and an abnormal exit with rows missing writes `logs/v19/prospective_interrupted.json` and stops without a report or marker, so the run stays resumable. |
| 8 G3 pairing assumption unchecked | MINOR | genuine | `pairing_mismatches` reported in the G3 gate and recomputed by the verifier. |
| 9 no_regression_full and a correct native-to-e switch | MINOR | genuine | Program identity required only when K*'s winner used e; otherwise K*' must reproduce the held-out pair (script and verifier). |
| 10 wording of the repair | MINOR | genuine | Protocol 14: two clauses under one principle (fitting only 38, ranking only 38, both 3); scope of each clause stated; the module docstring's "two or more blocks" declared inaccurate in the protocol (code unchanged to keep the identity); module paths corrected in section 14 and noted in section 19 for the pre-frozen section 4. |
| 11 label edge cases | MINOR | genuine | Note added to the diagnosis record. |
| 12 launch hygiene | MINOR | genuine | The watcher log and the engine-test runner change are committed before the re-freeze; the tree is clean at the re-freeze commit. |

Tests after the erratum: 37 fast v1.9 tests pass (audit, repair,
prospective, verifier), and the 4 v1.9 engine tests pass. The engine's own
suite (geocat_arc, byte-identical, imports no v1.9 code; minus
`test_segmentation_features.py`, which reads ARC training data, and
`test_round9_delta_certificates.py`, which imports a script absent from
this repository since a44d262): 340 passed, 7 failed, 7 errors; the 7
errors and one failure are `test_correspondence.py` cases that call
`load_task` for ARC training tasks and stop on the missing
`data/arc/arc-agi_training_challenges.json` (no ARC data was read; no test
asks for the evaluation split); the other six failures are
`test_round2_primitives.py::TestEndToEnd::test_mirror_reversal_accepted_with_loo`
(the engine's own leave-one-out rejects the synthetic task),
`test_round5_in_set.py::test_induce_value_set_selector_task`, and four
`test_stage2_composition.py::TestCompositionInduction` cases. These tests run
the plain engine, import no v1.9 code and touch a byte-identical geocat_arc,
so v1.9 cannot have caused them; they were not run before v1.9 in this
repository, so whether they depend on host load (the composition cases have
60 s test budgets) was not established. Log `logs/v19/engine_own_tests.log`
(first run `logs/v19/engine_own_tests_run1.log`).
