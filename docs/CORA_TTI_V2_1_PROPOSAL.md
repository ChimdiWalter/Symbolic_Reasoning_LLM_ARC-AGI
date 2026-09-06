# v2.1 two-block compositional generalization: proposal only

Evidence-closure directive, section 14, Decision B. This is a PROPOSAL. No
corpus is generated, no split is assigned, no model is trained, and nothing here
is launched in this block.

It is a NEW study. It does not cover the families the original R2 question
asked about, and it does not rescue that question's NO-GO.

## 1. What justifies proposing it

The corrected census established 13 distinct generated two-block targets that
fit exactly under occurrence-scoped fitting while a complete, untruncated,
error-free enumeration of all 200 single-block hypotheses fails exactly, with
historical exclusion and run-wide deduplication active, vacuous probe evidence
excluded, and local irreducibility established under a contract that separates
inconclusive checks from evidence. Nine of the thirteen have every stage
witnessed by their demonstrations.

What it does NOT justify: any claim about repeated Select, about three blocks,
about learned proposal quality, or about semantic invention.

## 2. What the study would ask

Can a proposer that never sees the target schema construct a two-block program
that the identified baseline cannot reach, for a task whose whole abstract
syntax tree it has not seen during training?

## 3. Three distinct conditions, never merged

**(a) Complete-AST holdout within the declared two-block scope.** Held-out
targets are whole schemas absent from training, drawn from the same two-block
families. This tests generalization to unseen programs built from seen parts.

**(b) Held-out combinations of already available block components.** Certain
PAIRS of block components are reserved: every constituent occurs in training
inside other combinations, but the reserved pairing never does. This is a
sharper test than (a) and is the study's centre.

**(c) The original repeated-Select and three-block stress tests.** These stay in
the record as unachieved targets. The corrected census found nothing admissible
in (2,), (2,1) or (0,0,0) among 128 attempts each. They are not removed, not
softened, and not counted as covered by (a) or (b). Block-count extrapolation to
three blocks remains a separate unachieved target unless valid three-block
examples actually exist, which at present they do not.

## 4. Rules for the component-combination holdout

These bind before anything is generated.

- **Assign combinations first.** The held-out pairs are chosen and hashed
  BEFORE any target is evaluated, so the split cannot follow the results.
- **Never choose by observed success rate.** The reserved pairs may not be
  picked because they yielded well, or badly, in any prior run. A declared
  mechanical rule fixes them, and the rule is recorded in the manifest.
- **Every constituent must occur in training.** A reserved pair whose parts do
  not both appear elsewhere in training tests availability, not composition, and
  is excluded from the split.
- **Group equivalent and reversed combinations.** Where the semantics make two
  combinations equivalent, including order reversals that the executor treats
  alike, they move together. A reversed pair may not sit on both sides.
- **Prevent canonical-schema overlap.** No held-out schema may share a canonical
  digest with any training schema, and the run-wide identity sets enforce it.
- **Inspect behavioural overlap without over-reading it.** Frozen-probe
  fingerprints are reported for train and holdout, and a coincidence there is
  recorded as a finite observation, never as proof of global equivalence.
- **Use fresh evaluation examples.** Held-out targets are rendered from grid
  seeds disjoint from every training seed.
- **Retain shortfalls.** If the split turns out too thin, that is reported. It
  is never repaired by moving to a more favourable split.

## 5. Feasibility the proposal must respect

The corrected census yielded 13 admissible targets in 896 attempts, about 1.5
per cent. A study needing hundreds of targets needs roughly 100 attempts each,
which is affordable but must be budgeted honestly, and the generator's narrow
yield is itself a finding to state rather than engineer around. Whether 13
distinct targets can support a train and holdout split at all is the first
question a scoping run must answer, before any model exists.

## 6. Baseline the study must beat

A learned proposer must be compared against unlearned search over the same
constructive grammar under matched budgets. Beating the fixed single-block
baseline is the admission criterion for a target, not a result for a proposer.
Without the matched-budget comparison, a proposer that merely enumerates cannot
be distinguished from one that has learned anything.

## 7. Certification requirement recorded for the eventual adaptive learner

For each held-out demonstration, the full data-dependent procedure must be rerun
from the remaining demonstrations: failure extraction, proposal generation or
selection, slot fitting, extension construction and program induction. Selecting
an extension using all demonstrations and then describing program-only
rediscovery under that extension is NOT full-pipeline leave-one-out, and must
never be labelled as such. A schema fixed independently of the task is a
different experimental condition and must be labelled accordingly.

This applies prospectively to new CORA-TTI experiments. The live Step-B verifier
is not changed to implement it.

## 8. What would make this study fail honestly

- Fewer distinct targets than a split requires.
- A proposer no better than matched-budget enumeration.
- Held-out performance explained by behavioural overlap with training.
- Admissions concentrated in targets whose demonstrations do not witness every
  stage, which in the corrected census was 4 of 13.

Each of these is a reportable outcome, not a reason to change the split.
