# The Learner Must Re-Derive
### Procedure-Level Generalization Certificates for Abstract Reasoning (ARC-AGI)

## Summary

This project asks a question most reasoning benchmarks cannot answer:
**when a system "solves" a task, did it grasp the rule: or memorize a
coincidence?** The two are indistinguishable by accuracy alone.

The system built here makes the distinction *measurable*. It is a
program-induction engine for ARC in which a task only counts as solved if
the **entire learning procedure, re-run from N−1 of its training examples,
independently re-derives a program that solves the held-out example: on
every fold.** The certificate validates the *learner*, not the artifact:
a lucky program cannot pass, because luck does not re-run. On top of this
gate the system builds calibrated confidence classes, mines its own
failures for new capabilities, and subjects every extension: operators,
generative primitives, even its own research hypotheses: to the same
falsifiable standard.

**Certified corpus (v23, artifact-backed): 185/1000 ARC-AGI-2 training
tasks solved with certificates (18.5% CSR; 19.9% under the two-attempt
policy), and an honest 0/120 on the public evaluation split.** Every
number regenerates from disk with one script; the paper reports the
calibration evidence in full.

## What is new here

1. **Procedure-level certificates.** Solves are accepted by leave-one-out
   *re-induction*: the full learner re-runs per fold: not by output
   checking. Measured on hidden tests, this single gate separates rule
   from coincidence by a factor of five, and weakened versions of the
   gate collapse to zero precision.
2. **Graduated certificates.** A syntactic lattice over parameter
   expressions (relational > feature > induced-map > constant) predicts
   hidden-test correctness monotonically with *zero test access* -
   confidence classes derived from program syntax alone.
3. **A system that invents its own primitives.** Residual pixels: the
   exact cells its best programs cannot explain: are mined, clustered,
   and fit by candidate cell-set functions; a primitive is admitted only
   if it reproduces *held-out* residuals exactly across tasks. In the
   flagship experiment, hand-added primitives were deleted and the miner
   **reinvented them blind from failure data, re-certifying the same
   task**. Published systems compose given primitives; this one invents
   them under a falsifiable acceptance test.
4. **Zero-parameter derived programs.** New program modes store *no*
   coordinates and no constants: every value (a period, a thickness, a
   colour) is counted off the scene at render time. One derived mode
   certified a task *outside* the exemplar set that motivated it.
5. **The certificate crosses learner classes.** Applied in strong form to
   a per-task neural learner (retrained from scratch per fold), the same
   gate achieved perfect separation of right from wrong answers: the
   protocol is learner-agnostic.
6. **Falsification as the research method itself.** Candidate capability
   classes are named from failure censuses, tested by exact reproduction
   against ground truth, and *refuted rather than built* when the
   evidence fails: one entire candidate family was struck this way, and
   every negative round is recorded with its diagnosis.

![Failure is the fuel](assets/meta_funnel.png)

## Why certificates matter
The same search, freed from the generalization requirement, *quintuples*
its claimed solves while hidden-test precision collapses. Three independent
measurements triangulate the point: remove the gate, precision falls to
0.18; weaken it to render-only verification, precision falls to **zero**.

![Triangulation](assets/triangulation.png)

## The system invents its own primitives
A mining loop harvests the exact pixels its best programs cannot explain,
clusters them by geometric relation to scene objects, and admits new
generative primitives **only if they reproduce held-out residuals exactly,
on every fold, across multiple tasks**: the same certificate, one level
down. In the flagship experiment, hand-added primitives were deleted and
the miner **reinvented them blind from residual data, re-certifying the
same task** with no human having named either primitive.

![Self-extension ladder](assets/ladder.png)

## Certified progress, round by round
Every gain is a *certified* solve; every round that yielded zero is
recorded with its diagnosis. The falsification discipline runs both ways:
one candidate structure (inter-object connectors) was **refuted by direct
trace testing and never built**, while its exemplars were reclassified
into families that do reproduce the evidence.

Recent rounds:
- **Derived-pattern modes**: programs that *derive* their pattern from the
  scene at render time (`periodic_self`: the object's own internal period;
  `frame_minority`: ring thickness = the **count** of the object's
  minority-colour cells: a zero-parameter program). One certified gain
  landed *outside* the diagnosed exemplar set: the modes generalize past
  the traces that motivated them.
- **Obstacle-conditional rays**: the input scene threaded into the growth
  path, enabling stops, deflections and cavity leaks that are undefinable
  as pure functions of an object's own cells.
- **Graduated certificates**: a syntactic preference lattice over
  parameter expressions predicts hidden-test correctness monotonically
  (relational 0.92 → constant 0.09) with zero test access.
- **The gate generalizes across learner classes**: applied in strong form
  to a per-task neural learner (retrain per fold from scratch): 100%
  gated precision, zero false positives, n=37.

## Current research program: can failure grow the language itself?

The evidence ladder above stops where most systems stop: composing and
re-certifying capabilities a designer already named. The active experiment
(Level 4, "Step B") asks the next question: **can certified failures cause
the system to propose new typed semantic productions that were provably
not expressible in its frozen language?** The run is deliberately strict:
task identities are blinded behind one-way tokens, the proposal language
and every input are hash-pinned in a run manifest before launch, every
eligible failure cluster is processed with no early stop, a candidate is
kept only when at least two independent sources certify it through full
leave-one-out re-induction, and nothing is inspected before the output
hash is recorded. A kept candidate still proves nothing by itself: it must
then pass a semantic separation test against the frozen language and
transfer to a held-out split it played no part in creating. A null result
is a publishable finding about the limits of this kind of invention; the
protocol forbids patching it after the fact.

The forward roadmap lives on the `cora-tti-dev` branch: certified
test-time invention (adapting the reasoning language per task at
inference, then discarding the adaptation), a failure-conditioned
proposal model trained by operator dropout with family holdouts, a
semantics-preserving batched executor with differential tests against the
exact interpreter, and a domain-general meta-extension interface. See
`docs/CORA_TTI_MASTER_PLAN.md`, `docs/CORA_PARENT_ARCHITECTURE.md` and
`docs/CORA_FUTURE_EXPERIMENT_LADDER.md` on that branch. Related work in
library learning and predicate invention (DreamCoder, LILO, POPPI,
ADVENT) is acknowledged there explicitly; the claim under test is the
conjunction of blinded failure-triggered proposal, certificate-carrying
acceptance, semantic separation, and held-out transfer, not any single
ingredient.

## Repository map
| Path | Contents |
|---|---|
| `geocat_arc/object_reasoning/` | the certified induction engine (segmentation, correspondence, delta vocabulary, generative programs, derived-pattern + ray modes, generator mining) |
| `level4_blind_runtime/` | the frozen typed runtime + search used by the blind invention experiment |
| `level4_stepB/` | the frozen Step-B substrate: generic constructor inventory, learner lattice, witness generator |
| `docs/` | design documents, frozen experiment designs, roadmaps (see also branch `cora-tti-dev`) |
| `paper/` | full paper (`DRAFT.md`) + LaTeX build (`latex/main.pdf`, 10 pp) |
| `kaggle/` | competition package: writeup, cover image, dataset build, submission checklist |
| `scripts/` | harness runners, diagnosis + trace tooling, Step-B runner/gates/audits, paper table generation |
| `tests/` | per-round regression + certification tests (engine suite 500+) |
| `RUN_HISTORY.md` | the complete experimental chronology, including every negative result |

## Reproducing the numbers
All headline figures regenerate from disk artifacts:
```bash
python3 scripts/paper_tables.py     # -> outputs/paper_tables.json
```
Full 1000-task chain (offline, CPU):
```bash
export ARC_DIHEDRAL_FRAMES=45 ARC_GENERATIVE=1 ARC_PATTERN_DERIVE=1
python3 scripts/run_unified_harness.py --workers 16 --out-dir outputs/run --run-id repro
```
