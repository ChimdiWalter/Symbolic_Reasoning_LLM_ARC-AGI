# Contract amendment 1: documented guarantees corrected (documentation only)

Written 6 Nov 2026, 01:35Z, after the companion study's independent review of the frozen object step (its review
note 0480). Its three findings were accepted, and each was re-checked against this study's code and records. Nothing
executable changed: the code, launch scripts, run records, kernel manifests and every count are as frozen in
`FREEZE.json` (version 1, sha256 `7b80302ef502acd795664d39a79781d6a3cdbb9e87a3ad8d4d8f59f630fd3de3`). The report's
wording is corrected (`REPORT_DEV.md`), and `FREEZE_V2.json` pins this amendment together with every file of
version 1.

Terms. G0 is A2's arc-dsl grammar under A2's base search (the bottom-up enumeration of
`experiments/architecture_sweep_20261026/a2/`; 150,000 executions, 20 CPU-s, two attempts). A hole is a set of
input-to-target grid pairs derived from a failed task's demonstrations; a pair is one of them.

## 1. The field `loo` means "multi-pair", not leave-one-out

**Implemented rule** (`objgrow/construct.py`). A candidate is labelled `loo = true` when:
- it is a one-rule paint candidate with edit e, and at least two pairs of the hole contain an input object whose
  bound edits (the edits that reproduce that object's fate in that pair) include e. For a colour-table edit, a pair
  counts when some object in it is bound to any constant recolouring;
- it is a two-rule paint candidate, and each of its two edits meets that count;
- it is a whole-output form (crop to the selected object, token, count strip, symmetry completion): always. These are
  verified on every pair and nothing is withheld.

The label therefore says that the edit was proposed independently by at least two pairs. It is a **multi-pair
proposal criterion**. No candidate is ever rebuilt with a pair withheld and then checked on that pair: the step
performs no withheld-pair re-induction anywhere.

**Withdrawn claim.** The statement "so that its parameters are recoverable with any one pair left out" (the docstring
of `objgrow/construct.py`; `REPORT_DEV.md` section 1, item 4) does not hold. The review's counterexample is accepted:
a colour table keyed by size, {1: 2, 2: 3}, with one supporting pair per key is labelled `loo = true`, yet with either
pair left out one key is missing. The brief asked for leave-one-out verification as in CORA's scored entry (rebuild
without each demonstration; the left-out output must be among the top two predictions). That was not implemented.

**Exposure in the records** (version 2 records, `runs/v2/`, the final constructor). Colour tables are 16 of the 136
gated candidates on ConceptARC, 1 of 54 on Mini-ARC and 321 of 835 on 1D-ARC. Whole-output forms, which carry the
label unconditionally, are 29 of 136 on ConceptARC (28 count strips, 1 crop) and none elsewhere. In the registries,
one of the 19 1D-ARC operations is a colour table (keyed by shape) and one of the two ConceptARC operations is a crop.
Promotion required a new fit on another source task, which is a separate check; the label adds no evidence beyond it.

**Names.** For compatibility the names stay as they are in code and records: the candidate field `loo`; the unit
field `n_candidates_loo`; the funnel keys `units_loo`, `candidates_loo` and the by-family `loo` (`runs/*/FUNNEL.json`);
the printed row "units with a leave-one-out candidate" (`objgrow/funnel.py`); and the word "leave-one-out" in the
docstrings of `construct.py`, `grow.py`, `funnel.py`, `arm.py` and `arctrain.py`. Read all of them as "multi-pair".
`REPORT_DEV.md` now says "multi-pair". The counts are unchanged: 306 units with a multi-pair candidate (24 on
ConceptARC, 9 on Mini-ARC, 273 on 1D-ARC) and 1,025 candidates gated.

The funnel rows "units recovered" are a different quantity and stand. They count motivating tasks whose fitting
candidate predicted every test output, scored after the run on source test outputs.

## 2. Regression accepts the old first prediction in either attempt

**Implemented rule.** The individual check is `Gates.regression` in `cgrow/selfext_core.py`, reused unchanged; the
combined check is `combined_regression` in `objgrow/grow.py`. A benchmark's regression set is its source tasks that
G0 solves at the base budget. A task in that set fails the check in two cases:
- the search with the added operation or operations finds no fit;
- G0's old first prediction is in neither of the two new attempts.

A new first attempt that differs from the old first prediction passes when the second attempt equals it: the
attempts [changed first, old first] pass. This is not a first-slot guarantee. Read `REPORT_DEV.md` and the docstrings
of `objgrow/gates.py` and `objgrow/grow.py` ("a changed first prediction") with this rule.

**In the records.**
- The regression sets have 1 task on ConceptARC, 6 on Mini-ARC and 0 on 1D-ARC.
- The gate caches hold 59 regression searches on ConceptARC and 174 on Mini-ARC. None lost its fit, none lost the
  old prediction, and no pass depended on the second attempt. So no recorded decision turned on the weaker rule.
- On 1D-ARC the check is vacuous, because G0 solves no 1D-ARC source task at the base budget. Its "no roll-back"
  carries no information.
- The combined check records only its lost and changed lists. A pass through the second attempt there cannot be
  told apart from the record.

## 3. Limits

**Colour range.** The production wrapper (`production_fn` in `objgrow/edits.py`) accepts any value that arc-dsl's
`valid()` accepts with the grid tag. `valid()` checks the shape (rectangular, at most 30 x 30) but not the cell
values, so an authored operation that writes colour 11 is accepted. The constructor takes colours only from cells of
the hole's grids, and it bounds attribute colours (size, count, holes) to 0 to 9. No natural emission of a value
outside 0 to 9 was shown. No colour-range guarantee is claimed.

**Execution budget and work counting.** A2's search checks the execution budget once before each vector evaluation,
that is, one candidate program applied to all n inputs of the task (demonstrations, then test inputs). It then
charges the production's charge for every input it executes. An object operation has charge 1 by design. So:
- one vector evaluation on a three-input task performs three macro calls and is charged 3;
- the last evaluation can exceed the budget by up to n x charge - 1. With a budget of 1, one evaluation still
  performs all three calls.

The work inside one macro call (segmentation, predicates, edits) is not charged. It is counted separately, by the
counters of segmentations, edit applications and operation applications in `objgrow/edits.py`; these are recorded
per unit, and for construction only. The work also shows in the process CPU, which is recorded per search, per gate
result and per unit.

No hard cap on the work of one macro call is claimed. The bounds that do exist are:
- the search's CPU cap: 20 CPU-s at the base budget, checked every 256 combinations;
- at most 150 objects per scene;
- the 30 x 30 grid guard;
- during construction, 20,000 operation applications per hole.

A study that uses this step as an arm should match its control on CPU, and report macro invocations, internal
counters and CPU separately.

## 4. What changed, and how version 2 is pinned

- **Changed, wording only (every number unchanged):** `REPORT_DEV.md`; `PROGRESS.md` (one entry appended).
- **New:** this file and `FREEZE_V2.json`.
- **Unchanged:** all code, launch scripts, run records and kernel manifests, and `FREEZE.json` (version 1).
- **`FREEZE_V2.json`** holds the sha256 of this amendment, of `FREEZE.json` and of every file listed in version 1 at
  its current content. A file whose content changed since version 1 is listed with both digests. The benchmark data
  digests were recomputed and equal version 1's.
- **How it was written:** by a short inline command that follows this rule; no code file was added. It can be checked
  by recomputing the digests.
