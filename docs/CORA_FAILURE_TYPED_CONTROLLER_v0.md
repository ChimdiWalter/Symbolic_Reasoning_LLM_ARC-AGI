# Failure-typed reasoning controller v0: schema and one proposed experiment (2026-10-12)

**Status: DESIGN.** Nothing here is implemented, frozen or run. The
evidence behind it is `records/CTL0_PHASE1_FEASIBILITY_20261012.md`. The
complete controller does not exist. This file defines its interface and one
small experiment, which needs explicit authorization.

## 1. Interface: observations, hypotheses and decisions are kept apart

- **Observation.** Facts recorded from one attempt; never a conclusion.
  - The attempt: training subset id, permitted unlabelled inputs, budget.
  - Representations: per view, coherent or not, searched or cut, and its
    equivalence class.
  - Candidates: per candidate, its program identity, exact fit, the engine's
    own leave-one-out result, and its predictions on the permitted
    unlabelled inputs.
  - Construction: proposals with their support, plus the controls'
    proposals.
  - Resources: deadline hits, hard caps, CPU.
- **Hypothesis.** A category from the table below, with a status
  (ESTABLISHED or SUSPECTED), the observations behind it, and the observations
  that would refute it.
- **Decision.** One of SEARCH_MORE, CORRECT_REPRESENTATION, CONSTRUCT,
  REPAIR_VERIFICATION, ABSTAIN or NONE, together with the certificates it must
  preserve.

**Domain-neutral wording.** The interface speaks of "units of
representation", "candidate explanations", "permitted unlabelled inputs" and
"independent re-derivation". The ARC adapter maps these to views, programs,
test inputs and leave-one-out. Nothing in the controller names an ARC view or
task.

| category | necessary observation | diagnostic test (reproducible) | refuted by | status reachable now | permitted adaptation | abstain when | certificates preserved |
|---|---|---|---|---|---|---|---|
| SEARCH_TRUNCATED | budget hit before the candidate space is exhausted, with no deadline-free failure | rerun with a matched larger budget and no other change | the same failure without any deadline hit | not separable from resources yet | search more, at matched accounting | the budget is already matched | all |
| REPRESENTATION_EXCLUDED | a coherent unit cut, or not coherent, where a re-derivation fails | static census of the subset | the cut unit's candidates also fail when searched | ESTABLISHED (11 of 14 folds) | representation correction, fold-local only | the correction is not shown safe (P3 was not) | independent re-derivation, native successes |
| REPAIR_NOT_GENERATED | no proposal from the permitted evidence | proposer on the subset | a proposal exists | ESTABLISHED (5 folds) | construct with more evidence, or abstain | support is below the minimum | proposal support |
| MULTIPLE_PLAUSIBLE_REPAIRS | at least 2 candidates fit all permitted evidence and disagree on a permitted unlabelled input | direct execution on the inputs | agreement on every permitted input | ESTABLISHED (kf892487f1049 f1) | abstain, or a preregistered prior | always, unless a prior is preregistered and validated | all |
| INSUFFICIENT_EVIDENCE | the rule's keys or support are seen in fewer than the minimum demonstrations | support count | support reaches the minimum | SUSPECTED (k017955a77fc5) | abstain | always | support gate |
| ENGINE_REJECTED | train-exact, rejected by the engine's own gate | the engine log | acceptance | ESTABLISHED | diagnose further (no relaxation) | | engine gate unchanged |
| CERTIFICATION_UNSTABLE | top-level accept, re-derivation fails | the engine's leave-one-out trace | stable re-derivation | ESTABLISHED | verification repair only if independence is kept | | independence |
| RESOURCE_EXHAUSTED | hard cap or deadline | timing log | the same failure well inside budget | ESTABLISHED (3 folds, 2 full runs) | matched-budget rerun | | matched accounting |
| CAPABILITY_GAP_SUSPECTED | no candidate in the bounded language, and none after construction | a complete bounded absence check, which does not exist | any candidate found | NOT reachable now | construct | | semantic separation |
| UNKNOWN | none of the above holds | | | legitimate | none | | |

**Rules for using the table.**
- A failure of bounded search alone never establishes CAPABILITY_GAP.
- Similar heuristic scores never establish INSUFFICIENT_EVIDENCE.
- A new combination of known operations is never invention.

## 2. Validation boundary (binding)

Per fold, the generator and the selector may use:
- the fold's training demonstrations;
- permitted unlabelled inputs (the fold's test input; the task's test
  inputs);
- native traces;
- training-derived candidate evidence;
- frozen priors;
- fixed budgets.

They may NOT use:
- the removed output;
- full-data programs or full-data views;
- target labels;
- task ids;
- protected evaluation;
- pilot v2.

**Cross-fold agreement is excluded as a selector,** because other folds
contain the held-out demonstration.

## 3. Four kinds of progress, never merged

| kind | meaning |
|---|---|
| A | better search |
| B | better selection or abstention |
| C | automatic capability construction |
| D | verified capability growth (the objective) |

The controller chooses among A, B and C, or abstains. Success at A, B or C is
never D.

## 4. The one proposed experiment: DISAGREEMENT-CHECKED CERTIFICATION (DCC) v0, NOT EXECUTED

**Why this one.**
- It is the only candidate indicator with direct support on a real fold:
  in kf892487f1049 f1, two exact-fit repairs disagree on the permitted
  inputs.
- It addresses the documented weakness of the native verifier, which
  false-accepts on synthetic tasks.
- It is generic: "several explanations fit; they disagree on the case to be
  predicted".

**What it cannot do.** It cannot add a verified real reconstruction now:
1 of 14 folds is affected, and that fold also fails verification. Its claim
is therefore kind B only. If the author wants only D-relevant work, the honest
alternative is NONE: no D-relevant intervention is justified by current
evidence.

**Stage 0: candidate-pool recorder, observation only.**
- A versioned overlay with a generated, marked logging line in a copy of
  `inducer._induce_candidate`. At each call it records the `winners` list
  (the train-exact program of each searched view, with its key) and each
  winner's prediction on the permitted unlabelled inputs.
- It changes nothing.
- Gate R0: native and recorder runs are byte-identical in program,
  acceptance and outcome on every task. If not, stop.

**Stage 1: decision rule, computed offline from the Stage 0 logs, so the
engine is never changed.**
- Certify the engine's selected program only if every recorded train-exact
  competitor that also passes the engine's own leave-one-out predicts the same
  grids on every permitted unlabelled input.
- At the CORA level, apply the same rule to the installed proposals: all
  proposals of the fold, each installed alone, at matched accounting.
- Otherwise ABSTAIN, recorded as MULTIPLE_PLAUSIBLE_REPAIRS.

**Data scope.**
- Development synthetic: the 41 preflight tasks. They informed this design,
  so they serve as development only.
- Validation synthetic: a FRESH corpus generated by the frozen generators with
  new seeds, its hash committed before Stage 0 runs.
- Real development: the 60 tasks at full data, plus the adaptive-LOO folds of
  the four failure-conditioned tasks through the reach v1 machinery with the
  recorder.
- Excluded: test outputs, pilot v2, evaluation DEV and HOLDOUT.

**Baselines and controls:**
- the native engine;
- reach v1's first proposal;
- demonstrations-only and shuffled-failure construction, as in reach v1;
- a COUNT-MATCHED control: abstain whenever there are at least 2 candidates,
  regardless of agreement;
- a RATE-MATCHED random abstention control with fixed seeds.

**Metrics, reported per task (runs are correlated within a task):**
- coverage;
- selective accuracy;
- false acceptances removed;
- correct certifications lost;
- the risk-coverage trade-off;
- abstention on native successes;
- CPU against matched budgets.

The input-only out-of-support indicator is a preregistered SECONDARY
analysis on the fresh corpus, never a decision rule here.

**Kill rules:**
- **K1.** Gate R0 fails.
- **K2.** The rule abstains on any of the 6 native development successes.
- **K3.** On the fresh corpus, it removes no more false acceptances than
  both the count-matched and the rate-matched controls.
- **K4.** It loses more than 10% of correct certifications.
- **K5.** Any boundary violation, or any change to the engine or to frozen
  evidence.

**Allowed claim if all gates pass:** "a no-oracle disagreement check improved
the selective reliability of certification on fresh synthetic tasks, at a
measured coverage cost". That is kind B. It is not capability growth, not
D, and not an ARC result.

**Isolation and restoration.**
- Development tasks run through the isolation hook in one process.
- Synthetic tasks run in a pool of 4.
- The overlay restores the engine, and the freeze checks run before and
  after.
- The build `--check` must equal the live engine function.
