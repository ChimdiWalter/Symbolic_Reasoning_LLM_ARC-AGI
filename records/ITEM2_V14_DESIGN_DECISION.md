# Item-2 v1.4 mechanistic frontier localization: design decision

**STATUS: FROZEN WITH ERRATUM 1 APPLIED, NOT RUN.** Authoritative text:
`docs/CORA_TTI_MECHANISTIC_FRONTIER_LOCALIZATION_v1.4.md`. Identities in
`outputs/tti/mechanistic_frontier_v14_manifest.json` and in section 8 below.
No v1.4 experiment episode exists. No stagewise hit rate, distance or
separation has been computed on any real data.

## 1. Why v1.4 exists

v1.3 is complete and failed its identifiability gate: G1 79/168 = 0.470
against 3/7, p = 0.156; G2 0.473, p = 0.195; median separation 0.025; G1 to G7
FAIL, G8 to G10 PASS; 21 groups, PARTITION 0. The designed 0.55 effect is
excluded; a smaller one is not. Record:
`records/ITEM2_V13_CORPUS_RESULT_20260926.md`.

v1.4 asks where target information disappears from the reasoner's own
trajectory, so that the next repair targets the measured loss point instead
of another scorer or a larger corpus.

## 2. Branch B, selected mechanically

The stored v1.3 artifacts hold only post-extraction evidence: at most 12
frontier terms of two outcome classes, re-sorted, with the observer's ordered
candidate list discarded and selector failures never emitted. Branch A could
only compare two encodings of the same graph, so it cannot separate
"trajectory differs, TFG loses it" from "trajectory does not differ". Branch B
was chosen from the schema inventory alone, before any stage outcome.

## 3. The design in one paragraph

FEATURE contrasts only. Two targets differing in exactly one grammar token,
same family, block count, partition, selects and MDL. Four replicates per
group; within a replicate both targets see the same input grids. The v1.3
admission law is applied to each target unchanged, plus twin integrity. The
existing observer's ordered candidate list is persisted, and every distinct
executed near miss is evaluated on every demonstration after the engine
returns. Stages S2 to S7 get target-independent descriptors from the model
view only; S0 (demonstrations) is a baseline; S1 (perception) is not observed
and no hook is added. Target 42 groups; floor 14; nothing trained.

## 4. Statistics

- Twin-excluded nearest neighbour: six companions from the other replicates,
  three same-target and three other. Exact null expected credit 1/2 for any
  distance matrix. v1.3's 3/7 is not exact under shared inputs.
- Ties share credit; a strict hit needs every tied nearest to agree.
- A stage is TARGET_IDENTIFYING only if hit rate > 1/2, exact binomial
  p < 0.01, and exact within-twin randomization p < 0.01 (the binomial is not
  valid under within-group dependence). A hit breaks ties by a
  label-independent hash; strict hits are descriptive (erratum 1).
- Sample size: p1 = 0.60 against 1/2, alpha 0.01, power 0.90, exact:
  336 instances = 42 groups, critical 190.
- Explanatory only: separation s = B - W across replicates; tie fraction;
  Holm-adjusted p-values; and the self-rerun sign test, which can establish
  a reaction only from S2 to S5.

## 5. Two corrections made during this block, before freeze

1. **Deadline-bound trajectories.** The feasibility smoke showed every
   admitted run lasts the full 8 s budget (8.03 to 8.08 s) and forms 9 to 21
   candidate groups. Each trajectory is a load-dependent prefix, so the
   planned "twins that did not hit the deadline" figure would have been
   empty. Replaced by a self-rerun control: target A is observed twice on the
   same input, and an exact sign test asks whether the twin is farther than
   the rerun. This separates "reacts but not consistently" from "no reaction
   beyond timing noise" under REASONER_TRAJECTORY_INSENSITIVE.
2. **Run-order confound.** As first written, A always ran before B, so any
   run-position effect would have read as target signal. Each replicate now
   uses one of the six orders of (A, B, A'), chosen by a seed hash before any
   outcome. The same ordering existed in v1.3 (anchor episodes first); v1.3
   found no signal, so it cannot have produced that negative.

Also found and handled: the engine rereads its growing near-solve log only
under `ARC_OVERLAY`, and its fragment library changes only through
`promote_and_validate`. The generator refuses to run with either switch set
or with a library or learned-verb file present, and uses a fresh engine
directory. v1.3's nearest-neighbour tie break by episode index favoured
target 0 and could only raise a hit rate, so the v1.3 FAIL stands.

3. **Pre-run adversarial review (erratum 1).** One blocking, two major and
   several minor findings, all corrected before any episode existed:
   label-independent tie breaking for hits and a ladder guard against an
   unresolved earlier stage; reactions only from engine-emitted stages;
   every `ARC_*` switch refused except the budget, with environment and
   versions recorded per slot; engine caches cleared before every run;
   per-slot freeze re-verification, writer lock, persistent wall clock and
   corpus checks. Record: `records/ITEM2_V14_ERRATUM_01.md`.

## 6. Deviations from the directive

Null 1/2 instead of 3/7; randomization test added to the binomial; two
classifications added (CURRENT_TFG_IDENTIFYING_UNDER_TWINS,
TFG_AGGREGATION_LOSS); S5 counted as an execution stage; S1 unobserved;
Branch A not viable; the self-rerun control; balanced run order. Each is
argued in protocol section 13. All are stricter or more exact; none relaxes a
threshold.

## 7. Static feasibility

See protocol section 15 for the smoke and the caps. Disclosure: the smoke
printed per-episode trajectory sizes and candidate counts for smoke episodes
(seeds from 200,000,000, never audited); no distance or neighbour between
any two episodes was computed.

Test status at the first freeze: all 39 v1.4 tests passed; after erratum 1
see RESUME.md for the current count. The full repository suite
gives 103 passed and 1 failed, the pre-existing
`test_engine_trace_repair.py::test_observer_state_cannot_leak_between_tasks`.
Its last assertion expects a deadline-bound DEV task to emit more candidates
than the tile fixture; at load about 42 the DEV task emits 47 to 49 in 8 s and
the fixture 100. No engine, hook or observer file has changed since that
test's commit f54c9bd. Timing-dependent assertion, left unedited, recorded
here.

## 8. Identities

Recorded at the freeze commit: protocol sha256, manifest sha256 and the
implementation and dependency digests are in the manifest. The commit hash is
in `RESUME.md`.

## 9. Next action, exactly one

RUN THE FROZEN v1.4 MECHANISTIC FRONTIER LOCALIZATION EXPERIMENT. The one
adversarial review is done and its corrections are frozen. Then STOP.
