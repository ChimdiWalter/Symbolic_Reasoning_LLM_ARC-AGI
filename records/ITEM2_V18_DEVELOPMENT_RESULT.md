# Item-2 v1.8: development audit (DEVELOPMENT ONLY)

Engineering evidence on development data. Not a scientific result: the
same mechanism must pass the frozen prospective test (protocol section 14)
on new tasks before anything is claimed.

- Corpus: the first 40 tasks of `scripts/v18_corpus.py` at seed base
  840,000,000 (the v1.7 acceptance filter unchanged).
- Families: (0,0) 18, (1,1) 8, (1,0) 7, (0,1) 5, (0,0,0) 2. 37 distinct
  target structures, 3 repeated.
- Code: the proposer after the witness-set correction (design record
  section 11). The two rows produced with the probe key are kept,
  superseded, in `logs/v18/`.
- Outputs: `outputs/tti/v18_dev_audit.json`, `outputs/tti/v18_dev_rows.jsonl`,
  log `logs/v18/dev_audit.log`. Run 2026-10-06, 1,954 s, one process at
  default priority beside Step B's workers.
- The generator's schema was used only after each proposer run, to measure
  whether an equivalent extension was proposed, verified and selected.

## Proposer level, 40 tasks

| arm | outcome | equivalent extension verified | selection predicts the held-out pair | selection behaves as the generator's on the witness grids |
|---|---|---|---|---|
| FAILURE_CONDITIONED | 40 SELECTED | 40 | 40 | 19 |
| NO_RESPONSE | 40 SELECTED | 40 | 40 | 19 |
| PURE | 10 SELECTED, 30 SELECTION_ABSTAINED | 40 | 10 | 10 |
| SHUFFLED_FRONTIER as first frozen (now SHUFFLED_COORDINATES) | 40 NO_PROPOSAL | 0 | 0 | 0 |
| DEMO_ONLY | 40 PROPOSAL_LIMIT (512 proposals, none verified) | 0 | 0 | 0 |

- **Coverage.** An extension behaviourally equivalent to the generator's
  was proposed and verified on every task. The generator's own normalized
  text was among the proposals on 24 of 40 (the others reached an
  equivalent through different K blocks).
- **Failure dependence: not shown by these two zeros (erratum 01).** The
  first-frozen shuffled arm applied another task's residual cell
  coordinates to this task's grids, which no lower layer can cover, and
  DEMO_ONLY's ranking mostly selects conflicting blocks; both are zero by
  construction. The controls that keep the mechanism are reported in the
  erratum section below.
- **Depth.** Depth 3 ran on exactly the two three-block tasks (no
  two-layer proposal existed); both selections behave as the generator's
  three-layer program.
- **Candidate counts.** Median 30 proposals and 30 verified candidates per
  task (maximum 256). After the duplicate law, 1 to 18 distinct behaviours,
  median 5. The main arm reached the 256-proposal cap on 2 of 40 tasks
  (indices 37 and 39) and still verified candidates there (corrected by
  erratum 01; an earlier version of this line said the cap was never
  reached).
- **Runtime.** Median 3.4 s per proposer call, maximum 20.9 s, against the
  180 s bound.

## Selection

| deciding level | tasks | selection behaves as the generator's |
|---|---|---|
| VERIFICATION_UNIQUE | 9 | 9 |
| P0 | 1 | 1 |
| D | 5 | 4 |
| MDL guess | 25 | 5 |

- P0 decided one task. The CandidateFailureResponse rarely separates
  verified compositions: they replay every demonstration and usually
  re-derive under leave-one-out alike. NO_RESPONSE therefore matches the
  main arm here.
- **The main risk for the next stage.** Every selection predicted its one
  held-out pair, but only 19 of 40 behave as the generator's on 64 fresh
  task grids, and the MDL guess, which decided 25 tasks, matched on 5. One
  held-out demonstration barely discriminates between verified candidates;
  a single real ARC test input will face the same problem.

## Engine level, the first 8 tasks

| measure | result |
|---|---|
| paired ablation | 8 of 8 EXTENSION_NECESSARY_AND_USED with the held-out pair exact |
| real leave-one-out, proposal rebuilt in every fold | all 7 folds on 6 tasks; 5 of 7 and 1 of 7 on the other two |
| synthetic B/P/U/L/T/A complete | 6 of 8 |
| S6 level C (witness grids) | SEPARATED 8 of 8, comparison sets 18 to 69 |
| S6 on the frozen probes | 3 of 8 would read DUPLICATE_EXISTING_SEMANTICS |

**Why folds fail.** In every failed fold the proposer selected an
extension and the engine proposed it, then rejected it with its own
re-induction gate (`HYPOTHESIS_REJECTED` in the recorded fold events).
With 6 demonstrations the gate refits on 5, and a table key witnessed in
only two demonstrations fails when one of them is held out. This is
evidence sparsity, not leakage: no fold produced a misattributed solve.

## Structural audit

37 of 40 development target structures are distinct. For the prospective
test, a task's structure counts as seen if its normalized target text
occurs among these 40; witnesses are reported separately for seen and
unseen structures.

## What this does and does not show

It shows, on development data:
- the proposer constructs verified extensions from the task's own failure
  without the target or a candidate pair;
- they compile and are necessary in the same reasoner;
- leave-one-out with the proposal rebuilt inside every fold mostly
  succeeds;
- without the task's own failure nothing is proposed.

It does not show:
- any prospective or real ARC result;
- good selection among behaviourally different verified candidates (the
  MDL guess is weak);
- three-block competence beyond two tasks.

## Selection against the full candidate set (`logs/v18/dedup_heldout_check.py`)

For every development task, the distinct verified candidates the hierarchy
chooses among (161 in all, 1 to 18 per task, median 5):
- 145 of 161 predict the held-out pair; in 36 of 40 tasks every one of
  them does. One held-out demonstration therefore does not test the
  levels below verification.
- Exactly one candidate per task behaves as the generator's extension on
  the witness grids (40 of 40 tasks). The hierarchy picked it on 19.
- Where a choice existed (31 tasks), P0 made it once, D five times and the
  MDL guess 25 times. The MDL guess matched the generator's extension on 5
  of its 25.

The prospective test counts a task as useful by the held-out pair, and the
engine stage and the fold-level reruns test the selection further; the
witness-grid equivalence is reported but is not a gate, because the
generator's extension is not the only program consistent with the task.

## Corpus notes

- Two pairs of development tasks share a target digest (the same schema
  sampled at two seeds); the donor derangement for SHUFFLED_FRONTIER never
  paired a task with a same-digest donor. The exclusion set carries the 38
  distinct digests.
- The audit ran 2026-10-06 00:20 to 00:55 UTC as one detached process,
  across a restart of the interactive session; no task was rerun.

## Provenance of this record

The first version of this record (through "What this does and does not
show") was written by an earlier instance of the session in the minutes
after the restart, from the finished audit. Every number in it was checked
again against `outputs/tti/v18_dev_rows.jsonl` and
`outputs/tti/v18_dev_audit.json` by the continuing instance before the
sections above were added. The earlier instance's draft prospective
thresholds (30 tasks, 9 witnesses) were replaced before the freeze; see
`records/ITEM2_V18_FEASIBILITY.md`.

## Why the literal generator composition was sometimes not proposed

On the 16 development tasks where the generator's own normalized text was
not among the proposals (checked 2026-10-06 with the frozen code):
- 14 two-block tasks: the generator's top layer is a PARTIAL K block on
  every one, and its lower layer passes the proposer's lower-layer check on
  every one. The literal composition was cut by the frozen caps: the lower
  layer ranked 17th to 25th (cap 16) on 8, the top layer ranked 33rd to
  48th (cap 32) on 5, and the 256-proposal cap on 1.
- 2 three-block tasks: cut by the depth-3 caps (8 tops, 8 middles).
- On all 16 a behaviourally equivalent composition was inside the caps and
  verified.

No proposer rule rejected a composition the fitter accepts. This is the
basis of the completeness-by-construction statement in protocol section 15.

## Erratum 01: controls that keep the mechanism (2026-10-06)

`scripts/v18_dev_controls.py` (output `outputs/tti/v18_dev_controls.json`,
1,134 s) ran every arm with the erratum code on the same 40 tasks. The
main arm reproduced the stored audit exactly on 40 of 40 tasks (proposals
and selection).

| arm | useful | discordant against the main arm (main only, arm only) |
|---|---|---|
| FAILURE_CONDITIONED | 40 | |
| SHUFFLED_FRONTIER (transplant) | 26 | 14, 0 |
| BLIND | 30 | 10, 0 |
| NO_RESPONSE | 40 | 0, 0 |
| PURE | 10 | 30, 0 |
| SHUFFLED_COORDINATES (first-frozen shuffled arm) | 0 | 40, 0 |
| DEMO_ONLY | 0 | 40, 0 |

- The two G1 controls fail on tasks where their tops produce nothing that
  verifies (transplant: 8 NO_VERIFIABLE_PROPOSAL, 5 PROPOSAL_LIMIT,
  1 NO_PROPOSAL; BLIND: 10 NO_VERIFIABLE_PROPOSAL). Wherever a control
  selected, its selection predicted the held-out pair.
- K* alone at 3x budget (the new witness leg A) accepted none of the 8
  engine-subset tasks (24 s budget: five runs ended at about 24 s, one at
  32 s, two early at 4 and 5 s), so the development witness count stays
  6 of 8.
