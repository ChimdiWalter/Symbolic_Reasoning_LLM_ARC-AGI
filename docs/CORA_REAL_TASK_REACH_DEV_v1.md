# Real-task proposer reach: development protocol v1

Written 2026-10-07, before any measurement of this block. DEVELOPMENT, not
a prospective test: nothing here is scored against ARC test outputs, and no
result here is a causal witness.

## 0. Binding invariant (user, 2026-10-07): failure-driven semantic invention

A capability is called invented only when all eight hold: (1) an observable
failure of the existing reasoner K; (2) a machine-generated repair derived
from permitted failure evidence and demonstrations, without the answer; (3)
an executable, typed, canonical extension e; (4) a bounded semantic
separation test against K that rules out renaming, caching or composition of
an already expressible program; (5) full adaptive leave-one-out with the
whole construction rerun without the held-out pair; (6) correctness on an
independently scored unseen target; (7) causal necessity: the winner uses e
and the gain disappears without e under matched controls; (8)
failure-conditioning evidence against demonstration-only and
shuffled-failure controls. Human-designed generic construction machinery is
permitted and disclosed; human-supplied task-specific repairs never count.
A change that improves a score without these is reported as engineering or
search improvement, never as capability growth. Task-local invention stays
separate from Step B's durable capability-growth experiment. This block can
establish at most conditions 1 to 5 on development data; 6 to 8 need the
prospective pilot.

## 1. Authorization and data

- Data: the EXISTING 60-task training-development bundle
  `records/pilot_v1/dev_bundle.json` (sha256 `6eb73236...`, opaque keys;
  the first 60 in-scope tasks of the frozen selection 4d3c29b). Not the
  evaluation DEV split. Not regenerated, not filtered, no task replaced.
- The 488 pilot candidates, the evaluation splits, the HOLDOUT, every
  solutions file, the evaluator key maps and Step B are not read.
- Reads allowed to the development solver: demonstration pairs, the
  unlabelled test inputs, its own execution traces and partial programs,
  and leave-one-out errors computed from the demonstrations.
- Every worker runs under the pilot isolation hook (`cora_pilot/isolation.py`).
- Outputs go to `outputs/reach_v1/` and `logs/reach_v1/`. The original
  0 of 60 result (ce123e8) is immutable.
- Development success means verified construction, installation,
  activation and demonstration-level validation. It is not ARC accuracy.

## 2. Step 1: native failure census (before choosing a mechanism)

The full native engine, the sealed per-task entry
(`harness.run_harness.run_one_task`, five chain flags, frozen library,
solution None), on all 60 tasks, with the v1.9 observation-only tracer
(`cora_v19/v19_trace.traced`) recording every object-engine induction, its
ranked candidate pools and its own leave-one-out folds. Per task, where
available: the claiming layer, the object engine's failure stage, train fit
(objects, pixels), hypotheses enumerated and time used against the budget,
the near-solve record (partial program, explained rules with selector,
action and parameter expressions, unexplained deltas, conflicts, failed
leave-one-out pairs), the leave-one-out divergence of every failed fold,
the competing candidates of the top-level pool, and whether any candidate
reaches exact demonstration fit.

Usable native trace: the object engine leaves either a near-solve with at
least one explained rule, or a demonstration-exact program that failed its
leave-one-out.

## 3. Diagnosis (operational; a bounded failure is never a proof)

Per task, from the census, first that applies:

| class | rule |
|---|---|
| NATIVE_CERTIFIED | the object engine accepted a program (no extension needed by this path) |
| A REPRESENTATION | the identity-frame induction failed at segmentation or matching: the representation exposes no usable correspondence |
| D/E LOO | a demonstration-exact program exists and its leave-one-out failed. Sub-classes from the divergence: PARAM (every failed fold re-derives the same rule structure with different values: an unstable literal, a fitting target), STRUCT (a failed fold selects a different structure: the demonstrations do not pin the choice, evidence E), NOFOLD (a fold induces nothing: evidence E) |
| C SEARCH | failed at selector or parameter after using at least 95 percent of the budget |
| B LANGUAGE | failed at selector or parameter within the budget: no candidate in the bounded space explains the change |

A pipeline-layer claim (a train-verified but uncertified program) is
recorded separately and does not change the object-engine class.

## 4. Step 2: one mechanism

The mechanism is chosen after the census, by this rule: among the classes
with a usable native trace, the one covering the most tasks, with a single
generic operation that acts on the engine's own representation. Native
program grounding is examined first: keep the native partial or
demonstration-exact program, locate the missing or unstable element (a
literal, a selector, a relation, a composition point), generate bounded
alternatives from existing permitted semantics, fit and verify them on
demonstrations only, return one canonical executable proposal. Finite
limits (proposals per task, program size, fitting attempts, execution work,
wall time, deterministic order and duplicate removal) are written into
this file before the mechanism's measurement run. No task-specific branch,
no answer, no task id, no lookup table of outputs, no unrelated operator
families.

### 4.1 Frozen grammar and limits (decided 2026-10-11, before the measurement run)

Evidence. Grammar coverage on the complete tagged extraction (instances2,
60 of 60 rows, 352 instances in 31 tasks; `outputs/reach_v1/grammar_coverage.json`):
5 tasks are explained by one setting under the coverage script's colour
rules (connect 2, bbox_fill 2, window_fill 1, band 1, dilate 1). The
mechanism's own rule (`cora_reach.construct.propose`: one setting
reproduces every memorized instance of one segmentation variant exactly,
one colour per instance, instances from at least two demonstrations)
proposes on 4 tasks, one proposal each: window_fill k=3 on one task,
connect on two (the same extension `gx_b05acfb6c5f87326`), bbox_fill on
one. The 2026-10-07 reading (6 tasks, taken before the extraction
finished) is superseded.

Grammar. The full grammar of `cora_reach.relations` as committed at
c44e6b2: nine families, 210 settings. window_fill k in {2,3,4,5};
empty_square k in {2,3,4,5}; bbox_fill; bbox_ring; band axis in {rows,
cols, cross}; dilate m in {1,2,3,4}; connect; copies_bbox (8 directions x
gap {0,1} x until_border); copies_offset ((dr, dc) in [-4,4]^2 without
(0,0), x until_border). The smallest family set that covers the 4 tasks,
{bbox_fill, connect, window_fill}, gives exactly the same full-task
proposals; restricting the grammar to it would only remove alternatives
inside leave-one-out folds and controls, a choice selected on these 60
tasks, so it is not adopted. No family was added after the coverage
measurement. Disclosed: the families are human-designed generic machinery
written after the census; empty_square was added after a 6-task coverage
smoke (02fbf9f). `construct.GRAMMAR` names the nine families explicitly.

Limits (`cora_reach.construct`, `cora_reach.measure`):
- at most 8 proposals per construction; at most 64 instances per
  segmentation variant; support: instances from at least 2 distinct
  demonstrations; at most 210 settings per variant, variants in order of
  instance count (descending) then name, settings in grammar order;
  duplicates removed by extension name; selection = the first proposal;
  exactly one extension installed per run;
- program size: the extension body is a family and at most 4 scalar
  parameters from the finite domains, no cell literal; copies stop after
  30 steps; background colour 0 (a stated limitation);
- wall time: the identity-frame instance extraction keeps its budget (90 s)
  under a hard cap of 450 s; every object-layer run is the harness object
  layer (`harness.object_layer.run_object_task`, budget 90 s) under the
  harness hard cap budget + 15 + 7 x 45 + 30 = 450 s; the matched-compute
  run uses budget clamp(extraction + construction + with-e seconds, 90,
  270) with hard cap budget + 360 s; phase wall cap 6 h; 4 workers.

## 5. Step 3: bridge and measurement

The compiler contract is checked explicitly; v1.7 is not edited. If the
proposal is a native fragment, it is installed through the engine's own
library-operator route in a new versioned adapter, tested for type
correctness, deterministic serialization, reload agreement, direct versus
engine execution, visibility, attribution, complete removal and
fresh-process reproduction.

The mechanism runs once on all 60 tasks under a fixed policy, reporting the
full progression (usable trace, candidate, type check, exact demonstration
fit, compile, install, engine acceptance, use, adaptive leave-one-out with
the proposal rebuilt from scratch in every fold, activation), every failure
and abstention, against the saved 0 / 0 / 0. Controls: native baseline, the
same backend without the extension, the failure-conditioned path, a bounded
path without task-specific failure conditioning, the extension-removed run,
and a compute-accounted baseline (the full cost of every step is charged;
"bounded" is written where an exact match is impossible).

Support: where the existing region-key support rule applies it is kept; if
the new representation makes it inapplicable, an explicit support contract
is written as a prospective protocol change, never a vacuous pass.

## 6. Readiness recheck

The recorded rule of `docs/CORA_REAL_ARC_CAUSAL_PILOT_v1.md` section 12,
unchanged: no isolation problem, no RUN_ERROR, native readiness tasks
complete, at least one development task at the compiled-and-installed
stage. Reported separately: leave-one-out successes, activations,
abstentions, usable traces, runtime and cost.
