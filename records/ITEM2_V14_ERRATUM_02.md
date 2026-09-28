# Item-2 v1.4 erratum 2: slot-order duplicate-group handling

Date 2026-09-28. Scope: the generator's group counting and the auditor's
group selection, so that both follow the unique-group rule erratum 1 already
froze. Written, tested, hashed and committed before slot 136 existed. No
v1.4 scientific statistic existed at any point before this erratum.

## The blocked result this erratum addresses

First run, commit fc51275, record
`records/ITEM2_V14_LOCALIZATION_RESULT_20260928.md`:

| quantity | value |
|---|---|
| slots | 136 (0 to 135) |
| admissions | 42 |
| unique group digests | 41 |
| primary episodes / rerun controls | 336 / 168 |
| distinct targets | 81 |
| wall time | 11,791 s |
| sealed audit, twice, byte-identical | AUDIT_BLOCKED, `duplicate_group_digest`, sha256 `9749e6f42cd19585203b56d9e522cb7828a9b0b948cf5c0908698959bcbcb373` |

The blocked report has no stage, sensitivity or classification section. The
auditor stops before any statistic when a corpus check fails, and nothing
else computed one: the pre-audit checks read slot records and recomputed
targets from the grammar only. **The v1.4 scientific outcome is not yet
measured**, so a repair decided now is outcome-blind.

## The duplicate

Group digest
`b4edae2fce55fa3f06f9d4288a7f32093a061fdbe4246936ec218fde31211466`, family
(0,1):

| admission | slot | pair seed | attempt | replicate seeds |
|---|---|---|---|---|
| first | 57 | 100571900 | 19 | 100571900 to 100571903 |
| second | 117 | 101170100 | 1 | 101170100 to 101170103 |

The two admissions share no replicate seed and no input grid. The problem is
not duplicated episode data; it is that one target pair was counted twice.

## Cause

Erratum 1 made "group digests unique" a blocking auditor check. The
generator was never given the matching rule: do not count an
already-admitted group digest again. Families admit few fittable pairs, so a
recurrence was likely. The erratum-1 tests covered only the auditor side.

## The rule

Admissions are ordered by slot. The first admitted occurrence of a group
digest is the scientific occurrence. Any later admission of the same digest
is a DUPLICATE_GROUP_DIGEST: retained in the corpus and in provenance,
counted and reported with its first and excluded slots, never audited, never
counted toward the target. Only the group digest and the slot number enter
the rule. For the first run: **slot 57 included, slot 117 excluded**.
`full00117.json` is kept exactly as generated.

## Generator repair (`scripts/generate_v14_twins.py`)

- On resume, the included digests are rebuilt from the existing records in
  ascending slot order.
- A candidate pair whose group digest is already included is skipped before
  any engine run, recorded in `duplicate_skips` with its slot, attempt, pair
  seed and target digests, and counted as DUPLICATE_GROUP_DIGEST; the next
  attempt follows the unchanged attempt law.
- The target counts unique groups: 41 at resume, so exactly one more is
  needed.
- Each new slot record also stores its start time since the first start and
  the manifest sha256.
- The resume loop moved into a function so tests can drive it; its order of
  checks is unchanged.
- The continuation writes `full_run_end_erratum2.json`; `full_run_end.json`
  is never touched.

## Auditor repair (`scripts/audit_v14_localization.py`, `cora_arc2026/v14_loc.py`)

- Scientific groups are `first_admissions(records)`; later admissions are
  reported as `excluded_duplicates` with digest, first slot and excluded
  slot, plus the raw admission count.
- `corpus_problems` takes the resume slot: an excluded admission before it
  is accounting, an excluded admission at or after it blocks, and only
  included groups count toward the target. Without a resume slot it applies
  the pre-erratum rule unchanged, so the first run's blocked verdict stays
  reproducible.
- Integrity and leakage are still checked on every admitted record,
  excluded ones included.
- New blocking check: the preserved first run (see below) is byte-identical.
- Default output `v14_localization_audit_erratum2.json`.

## Continuation

Resume the same run at **slot 136** with **41** included groups. Stop at the
first of: **42 unique groups**, slot 399 completed, or 86,400 s from the
first start.

| clock | value |
|---|---|
| chain start | 2026-09-27T20:47:49Z |
| recorded first start (the wall-clock origin) | 2026-09-27T20:47:54.95Z, epoch 1790542074.951294 |
| binding launch deadline (earlier time plus 24 h) | **2026-09-28T20:47:49Z** |

If the deadline has passed, the continuation does not launch and
ERRATUM2_ORIGINAL_CAP_EXPIRED is recorded. Nothing resets the clock, raises
the slot cap or changes attempts per slot.

## Preservation

- The 136 first-run records, `full_run_state.json` and `full_run_end.json`
  must match `outputs/tti/v14_twin_corpus_sha256.txt` (sha256
  `601ab7c2dd9cebbb90f0a8ca333689b1af6c9074b0dd8b89735f349609286e33`),
  checked by the gate and by the auditor.
- The first run-end is archived byte-identically as
  `outputs/tti/v14_twin_corpus/full_run_end_blocked_20260928.json`.
- The blocked reports stay in place (`v14_localization_audit.json`,
  `_pass1`, `_pass2`), with a fourth identical copy named
  `v14_localization_audit_BLOCKED_PRE_ERRATUM2.json`; all four must keep
  sha256 `9749e6f4...`.
- New outputs only: `full_run_end_erratum2.json`,
  `v14_localization_audit_erratum2{,_pass1,_pass2}.json`,
  `logs/v14_erratum2_*.log`, `logs/V14_ERRATUM2_*_DONE`. The original chain
  script `scripts/run_v14_chain.sh` is unchanged.

## Integrity gate

`scripts/check_v14_integrity.py pre` before launch and `post` before the
audit; `scripts/run_v14_erratum2_audit.sh` runs the post gate again and
refuses to audit unless it passes. Neither mode computes a distance or opens
an audit report.

## Not changed

No threshold, descriptor, distance, tie law, null, statistical test, reaction
test, Holm rule, classification rule, target law, admission rule, seed,
target group count, floor, slot cap, wall-clock cap, engine, observer,
baseline K or fitter. Every top-level definition of `cora_arc2026/v14_loc.py`
except `corpus_problems` is byte-identical to adecfd2; `v13_gen.py`,
`engine_trace.py`, `tfg_extractor.py`, the trace hook, the calibration, the
original chain script and the geocat_arc and Reasoning_Project_tti trees are
unchanged. Test J asserts all of this.

## Tests

Focused regression tests A to J in
`tests/test_v14_localization_feasibility.py`:

- A: first admission in slot order is included;
- B: a later duplicate never counts;
- C: the generator skips an included pair (on the real slot-117 pair);
- D: resume rebuilds the included set (synthetic and on the real first run);
- E and F: existing slots are never rewritten, and resume starts at the
  first gap;
- G: the wall clock counts from the original first start;
- H: the unique target stops the run;
- I: the blocked run is preserved and never a write target;
- J: the statistic code is byte-identical to the pre-erratum freeze.

No second review round, per the standing one-reviewer rule.

## Claim ceiling

V1.4 ERRATUM 2 FROZEN: GENERATOR ALIGNED WITH THE ALREADY-FROZEN
UNIQUE-GROUP RULE, FIRST RUN PRESERVED. Nothing about any v1.4 scientific
outcome.
