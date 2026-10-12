# Real-task adaptive LOO stability v1: Amendment 1

A separate file so that the protocol pinned by the diagnosis manifest
(`docs/CORA_REAL_TASK_LOO_STABILITY_v1.md`, manifest 58de06d5) stays
byte-identical.

## Amendment 1 (2026-10-12, after the diagnosis record, before the recheck): the repair and the recheck

The diagnosis record (`records/LOO_V1_DIAGNOSIS_20261012.md`, c2b8cd4)
establishes one generic defect, a segmentation-variant admission mismatch,
and licenses one repair of the class "fixing a demonstrable
segmentation-variant mismatch".

Repair (reach v2, `cora_reach2/`, outside every pinned tree):
VARIANT-CARRYING INSTALLATION (`cora_reach2/variant.py`). A growth extension
carries the segmentation variant V of the instances it was constructed from
(the proposal's variant). While it is installed, the engine's object-program
search tries V first (`inducer.SEGMENTATION_TRIAL_ORDER` with V moved to the
front) and admits it even when `evaluate_variant` would not (its result
marked coherent); both attributes are restored on exit and checked by
identity. Unchanged: every other variant, their order and the cap, every
other engine phase, the acceptance gate, K alone, the failure-evidence
extraction (K's own), the grammar, construction, selection, controls,
budgets and gates. The demonstration-only control carries no variant and is
installed as in v1. The successor policy `cora_reach2/measure2.py` is
generated from `cora_reach/measure.py` by `scripts/build_measure2.py`: 11
changed lines, each marked `# V2`, all of them passing V to the
installation; every other line and every helper is v1's.

Tests (`tests/test_reach2.py`): the overlay's contract (V first, the others
in order, V admitted, the others' coherence unchanged, restoration, refusal
to nest, restoration after an exception); four mutants (no reorder, no
admission, no restoration, wrong variant) each caught by the contract
checker; the successor equal to its recorded build with every unmarked line
v1's; the engine searching V first on a synthetic task; the successor policy
end to end on a synthetic task.

Recheck (run once, `scripts/loo_v1_recheck_run.py recheck`, frozen by
`outputs/loo_v1/recheck_manifest.json`): the same 60 development tasks, two
arms in one run, ORIGINAL (`cora_reach.measure.run_task`, reach v1 as frozen)
and SUCCESSOR (`cora_reach2.measure2.run_task`); the same evidence (reach
v1's instances2), donors, budgets and isolation hook; one engine directory
per arm; 120 units, the failure-conditioned tasks first; 4 workers; rows
`outputs/loo_v1/recheck_rows.jsonl`; marker `logs/loo_v1/RECHECK_0_DONE`.
Reported per arm (`scripts/loo_v1_recheck_summary.py`): proposals,
installations, acceptances, extension use, replay, adaptive leave-one-out
(folds and tasks), support, path classes (abstentions), false acceptances (a
fold that accepts a program using its extension and is wrong on the held-out
demonstration), restoration, compute, REMOVED and MATCHED, separation at the
section 8 labels, conditions 1 to 5, and K alone across arms (KALONE of
ORIGINAL against SUCCESSOR on every task where both ran).

The SCREEN of section 10 is applied unchanged to the SUCCESSOR arm.
Pre-registered expectation (the diagnosis record): it is not expected to
pass, because the evidence-side cuts, the lost support and the ordering on
kf892487f1049 fold 1 are not addressed by this repair. A pass licenses
designing pilot v3 only; a failure is recorded and the 488 candidates stay
untouched.

## Erratum 1 (2026-10-12T14:09Z): aborted first launch

The first launch of the recheck (start 2026-10-12T14:08:50Z from 6f31817,
manifest d46334d8) stopped before any unit: every worker's freeze check
hashed `records/LOO_V1_DIAGNOSIS_20261012.md`, which the isolation hook
refuses inside the reasoner (every records/ path but the bundle), so all four
workers exited with code 1. No unit was claimed, no row was written, no
outcome exists. Its start record, worker list, record and worker logs (with
the refused read) are kept in `logs/loo_v1/recheck_aborted_launch1/`; its
manifest is withdrawn. Correction: that record is pinned as COORDINATOR_ONLY
(checked by the coordinator, outside the hook); the workers check every
other pinned file and tree; a test now asserts that nothing a worker hashes
is a forbidden path. Nothing else changed; the recheck is re-frozen and
launched once more, as its first run.
