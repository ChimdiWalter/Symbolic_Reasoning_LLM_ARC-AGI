# The Learner Must Re-Derive: Procedure-Level Generalization Certificates for Abstract Reasoning

## The Problem: Accuracy Is Unfalsifiable

Benchmark accuracy cannot distinguish reasoning from recall. A system that memorizes coincidences and one that grasps a rule can produce identical scores. On ARC-AGI-2 we demonstrate this concretely: the same search, freed from any generalization requirement, quintuples its claimed solves while hidden-test precision collapses from 0.95 to 0.33. Leaderboard accuracy, reported alone, is unfalsifiable as a reasoning claim.

We propose that a reasoning-benchmark solve should come with a machine-checkable certificate of the process that produced it. We build a complete ARC program-induction system around one such certificate — leave-one-out-by-reinduction — and show it is measurably load-bearing, extends to multiple learner classes, and enables the system to invent its own primitives under the same falsifiability discipline.

## The Certificate: Leave-One-Out by Reinduction

A task counts as solved only if the entire learning procedure, re-run from N-1 of its training examples, independently re-derives a program that solves the held-out example — for every fold. The certificate validates the *learner*, not the artifact: a lucky program cannot pass it, because luck does not re-run.

**The certificate is load-bearing (E1).** Certified programs are correct on hidden tests 95.3% of the time versus 18.4% for the same search's uncertified train-perfect programs — a 5x truth gap.

**Accuracy up, truth down (E2).** Disabling the gate raises claimed solves 5.3x (43 to 229) while collapsing precision from 0.953 to 0.332. Raw accuracy rewards exactly the behavior the certificate exposes.

**Weak gates have zero precision (R2).** A post-hoc relift pass attempted to upgrade 187 constant-parameter programs by substituting relational expressions and verifying only by direct LOO rendering — a weaker standard than full reinduction. 40/187 passed this weak gate. Test-verified precision: 0/40 — 0.00. The weak gate's precision is zero, independently re-validating E1 at a new site.

These three results triangulate the thesis from independent directions. E1 measures the certificate's discrimination. E2 measures the cost of removing it. R2 measures the cost of weakening it. All three converge: without full procedure-level reinduction, acceptance gates are unreliable.

## The Calibration Lattice: Graduated Certificates

A syntactic preference lattice over parameter expressions predicts hidden-test correctness monotonically with zero test access (E4):

| Parameter class | Hidden-test precision |
|---|---|
| Relational | 0.92 |
| Feature | 0.75 |
| Induced-map | 0.40 |
| Constant | 0.09 |

Combined with E1, this yields graduated certificates — calibrated confidence classes rather than a binary verdict. We operationalize this as a two-attempt policy: attempt_1 certified, attempt_2 best-uncertified — measuring a leaderboard cost of certification at +14 task-outputs (19.5% best-of-2 vs 18.1% certified-only).

## Machine-Invented Primitives (E10)

The self-extension discipline enables the system to invent its own content-creating operations from failure data. A mining loop harvests residual paint — exact cells the best composite cannot explain — clusters residuals by geometric relation to source objects, searches a bounded hypothesis language, and admits a mined generator only under the delta-level reinduction gate (fit on N-1 pairs, predict held-out residual exactly, every fold, at least two tasks).

With hand-added generators disabled, the miner ran blind: from 427 residuals over 33 tasks it admitted 44 distinct generators and reinvented both the cross-line structure and the intersection-color rule — re-certifying the same task with no human having named either primitive. A third hand-added mode was not rediscovered; the trace identified why: its direction parameter is relational per pair, structurally outside the per-object hypothesis language — the precise next rung of the ladder, located by the experiment.

The honest statement: the hand-authored layer moved one level down, from generators to the hypothesis language. Each rung is smaller than the one above and validated by the same gate. To our knowledge no published program-induction system invents its own primitives (not compositions of given primitives) under a falsifiable acceptance test.

## The Gate Across Learner Classes (E9)

The certificate protocol is model-agnostic: "predict each held-out training pair from the others, exactly" does not care whether the predictor is a program or a network. We test this with a per-task MDL learner (181K parameters, trained from scratch per task, no pretraining).

Strong-form LOO gate on all 37 train-exact tasks — retrain from scratch on N-1 pairs per fold, require exact held-out prediction: **3/3 test-correct tasks pass at least one fold; 0/34 test-wrong tasks pass any fold — 100% gated precision, zero false positives** (replicating an n=8 pilot at 4.6x the sample size).

The frozen-model variant: a 1.8M-parameter network at 94% per-cell accuracy passed zero of 120 evaluation gates — the gate correctly refused every render of a model that had learned grid statistics but not rules.

## The Honest Map

181/1000 ARC-AGI-2 training tasks solved with certificates (18.1% CSR). 0/120 on the public evaluation split: coverage collapses out of distribution, and with one gate acceptance there (test-wrong), evaluation-split calibration remains undetermined. Training-split calibration is strong (40/42 correct among certified).

The last +4 came from a variant-budget scheduling policy (fold-stable, time-allocation only, zero new vocabulary) that cured a chronically budget-starved task and unlocked 4 others through better search-time allocation, while its one measured harm (a task solving only under the old schedule) is recorded as the intervention's price, alongside the arbitration discipline that separated 3 apparent losses (contention) from the 1 real one.

The last three came from the same discipline turned on a declared plateau (R19): a structural-vocabulary census named a class of *derived* patterns, trace-first falsification accepted 3 modes out of 15 candidate exemplars and recorded the 12 rejections, and the accepted modes store no cell lists at all — `frame_minority` has zero parameters, its thickness being the count of the object's own minority-colour cells. Tellingly, one of the three gains (d037b0a7) lies outside the diagnosed exemplar set entirely: the derived modes generalized past the traces that motivated them, which a stored-exemplar mode cannot do. The evaluation split stayed at 0/120.

Why the gap is structural, not budgetary: a framing census attributes the evaluation collapse to program-family coverage — compositional, generative, and multi-step structures the current four families cannot express. A near-solve graduation experiment (R1) showed 194/269 near-solves blocked on relational parameter expressions the grammar does not yet cover; the relift experiment (R2) confirmed this is a vocabulary-width problem. We regard "honest zero with intact calibration" as the correct behavior of a certified system out of distribution and exactly the information a deployment decision needs.

For the field: if these tasks are supposed to measure reasoning, systems should report what fraction of their claimed solves are falsifiable — and what fraction survive falsification.

## Universality

The certification protocol is domain-general. Any system that induces a predictor from a few-shot task and can re-run that induction on subsets of the evidence can produce the same certificate. For samplers and refinement models, resample-from-N-1 consistency is the natural analogue. E9 demonstrates this concretely on a neural learner. We propose the Certified Solve Rate and its calibration curve as a reporting standard for reasoning benchmarks.

## Limitations

Single benchmark family (ARC). The certificate multiplies induction cost by the fold count. The primitive core — delta vocabulary, feature registry, expression grammar — is hand-authored; E7 and E10 shrink this by one level but the grammar of laws and expressions remains ours. Absolute evaluation-split performance is zero. The neural gate sample (n=37) is small. Transfer rate of the MDL learner is low (7.5%), with the dominant unresolved lever being color equivariance. All negatives are reported as first-class results.

## Reproducibility

All artifacts released. Every table regenerates from disk with one script. The Kaggle notebook (offline, CPU, 12h governed) is attached.
