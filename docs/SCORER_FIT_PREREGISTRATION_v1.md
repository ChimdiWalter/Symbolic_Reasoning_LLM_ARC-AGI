# Stage-B scorer fit: preregistration, version 3

Written and amended 2026-09-24, entirely before any fit was run and before any
score existed. Earlier versions are preserved in git history at commits
41ac7bc and 3955f75. Amending before data is legitimate; nothing here may
change after a score is seen.

Corpus: the v1.2 constructive corpus, 215 admitted episodes, audited PASS on
all eleven frozen criteria. Protocol sha256 `31a74764...bbe6bb98`.

## 1. Anti-reinvention check

| component | status |
|---|---|
| grammar, legality masks, beam, ranking, MDL, cost | EXISTING AND REUSED, untouched |
| `GrammarState`, `tokens_are_valid`, `ast_from_tokens` | EXISTING AND REUSED |
| `propose_ast` decoding | EXISTING AND REUSED, unchanged |
| `EvidenceScorer` with its `weights` mapping | EXISTING, kept as the unfitted baseline |
| the existing prototype proposal network's `fit` | EXISTING BUT INCOMPATIBLE: it fits two heads predicting a production name and a result type, which is the Stage-A contract. It is not a grammar-constrained sequential decoder over token sequences, so it cannot carry the Stage-B contract. Not reused, and not duplicated either. |
| v1.1 model-view leak scanner | EXISTING BUT INCOMPATIBLE: it validates against the twelve-entry v1.1 allowlist and would reject every v1.2 view. A v1.2 equivalent is required. |
| a fitter for the Stage-B sequential decoder | MISSING, implemented here |

## 2. Frozen-model compatibility, verified mechanically

The model fitted here is a log-linear conditional model over grammar-legal
tokens, masked by the existing grammar state machine, decoded sequentially by
the existing proposer. Non-LLM. No hidden layer, which the frozen
specification permits because it sets hidden size at most 256 as a ceiling.
Stopping is the frozen law. Only weights are fitted; no grammar, bound, beam,
ranking term or family set is touched.

**One recorded finding.** The scorer's contract accepts the typed interface,
and the proposer passes it, but it cannot affect scoring in this experiment
because the corpus contains exactly one interface, `Set[Region] -> Grid`, on
all 215 episodes. An interface input would be a constant with zero variance.
This is the already-frozen `INFEASIBLE_SINGLE_INTERFACE` limitation carried
forward from v1.1, not a new defect, and it is not a model mismatch. It is
recorded here so that no reader infers the interface was exercised.

## 3. The holdout decision, taken prospectively

The v1.2 structural holdout admitted 3 episodes of 90 slots. Three episodes
cannot support a structural-family claim. The interpretation is frozen for
this block:

    same-family validation:            measured
    structural-family generalization:  NOT MEASURED

The structural holdout families are not changed, no easier holdout is
generated, the admission law is not relaxed, and v1.3 is not preregistered
now. The three episodes may be run once against the final frozen checkpoint
and reported descriptively, individually, with an explicit statement of
insufficient sample size. They take no part in the pass or fail decision.

## 4. Split

| set | rule | size |
|---|---|---|
| fit | all admitted training episodes | 180 |
| stopping and discrimination | all admitted corpus-validation episodes | 32 |

No episode moves between splits. Validation episodes are never used to fit
weights. Target digests are disjoint between splits, verified in the corpus
audit and re-asserted at run time.

## 5. Order of operations inside validation, and a recorded contamination risk

During training, validation is evaluated under **real associated evidence
only**, with the frozen metric and the frozen stopping law. Control
performance is not computed or inspected during training. The checkpoint is
never chosen by the size of any associated-versus-control gap.

Once the stopping law selects a checkpoint, that checkpoint is frozen. No
further training occurs. Only then are the five evidence conditions run.

**Recorded risk.** The checkpoint is selected on the same 32 episodes that
then carry the discrimination test, and it is selected using associated
evidence. That gives the associated condition an advantage the controls do
not have, and it biases the comparison toward the hypothesis. The instruction
directs this design, and the risk is recorded here rather than discovered
later.

**Preregistered mitigation.** The five conditions are additionally reported at
a second checkpoint chosen without any validation influence, namely the final
epoch reached. Both sets of numbers are reported whatever they show. The
primary verdict uses the selected checkpoint, as instructed; the unselected
checkpoint exists so a reader can see whether the result survives removing
the selection advantage.

## 6. Model and training accounting

Architecture: log-linear conditional model, 21 grammar terminals by 19 inputs,
being a bias plus the 18 frozen features, giving 399 parameters. Features are
standardized to zero mean and unit variance using statistics computed on the
fit set alone, standard deviation floored at 1e-6. Booleans map to 0 and 1.

Objective: teacher-forced conditional log-likelihood, normalized at each step
over grammar-legal tokens only. Optimizer: full-batch gradient ascent,
learning rate 0.1, L2 penalty 1e-3, weights initialized to exactly zero.

Determinism and seeds: initialization is zero and the batch is the full fit
set, so training is deterministic and contains no stochastic element. A seed
sweep is therefore not applicable, and none is run. This is a prospective
statement, not a post-hoc excuse.

Stopping: at most 2000 epochs, or 200 epochs without improvement in validation
exact-at-five, evaluated every 25 epochs.

Recorded for the run: architecture, parameter count, optimizer, learning rate,
batch size, epoch count, stopping epoch, best validation exact-at-five, the
validation trajectory, wall time, device, checkpoint hash, code commit, corpus
protocol hash, corpus audit commit, and the digests of every fit and
validation episode.

## 7. Leakage

Before fitting, every fit and validation model view is scanned. The v1.1
scanner is incompatible with the eighteen-entry v1.2 allowlist, so a v1.2
equivalent is used, requiring: view keys within features, input type and
output type; feature keys exactly within the eighteen frozen names; and no
occurrence anywhere in the view of the target digest, the target tokens, the
structural family label, the requested family, the generation seed, the
episode identifier or the admission outcome. **Zero violations are required
before fitting begins.**

The target AST is the supervised label during training only. At inference the
scorer receives the feature vector and the typed interface, and nothing else.

## 8. The five frozen evidence conditions

Evaluated on the same 32 validation episodes, sorted ascending by episode
identifier, index i, count n = 32.

| condition | evidence supplied |
|---|---|
| real associated | episode i's own feature vector |
| shuffled | the feature vector of episode (i+1) mod n |
| irrelevant | the feature vector of fit episode (i times 7) mod 180, sorted by digest |
| aggregate only | episode i's vector with every candidate-associated feature zeroed and empty_frontier set true |
| none | the all-zero vector |

The shuffle is a genuine derangement: rotation by exactly one position over a
sort by immutable episode identifier, wrapping the last to the first, so no
episode can receive its own evidence. The realized mapping is asserted to
contain no fixed point and is stored verbatim in the result artifact. The
earlier defect, where reversing a dictionary failed to permute anything, is
not repeated.

Candidate-associated features zeroed for aggregate only: frontier term count,
distinct frontier operator count, slot fit failed count, slot fit ok count,
executed not exact count, exact count, defined value signature count, fraction
wrong mean, palette extra mean, shape mismatch count. The seven retained are
the demonstration statistics and the deadline flag.

Every condition decodes with the identical checkpoint, beam and ranking rule.
Only the evidence vector differs. No condition may be dropped, and none may be
redefined.

## 9. Primary metric and success rule

Primary metric: exact-at-five recovery of the target AST, reported as
numerator, denominator and proportion for every condition.

**Success requires both, strictly greater, not greater or equal:**

    exact@5(real associated) > exact@5(shuffled)
    exact@5(real associated) > exact@5(aggregate only)

Irrelevant and none are reported and compared, and are explicitly not
converted into additional gates.

A result is not a pass if it is produced by one collapsed proposal repeated
for every episode. The collapse check is section 10.

## 10. Task-conditioning diagnostics, reported whatever they show

On the 32 validation episodes: distinct rank-one ASTs; distinct ordered top
five lists; structural families appearing at rank one; the frequency
distribution of rank-one ASTs and its entropy; the fraction sharing the modal
rank-one AST; episodes whose rank one changes between associated and
shuffled; episodes whose top five set changes; exact-at-one as a secondary
diagnostic.

For reference, the unfitted proposer on five real tasks produced one shared
rank-one AST and four identical top-five lists.

## 11. Required baseline

The unfitted `EvidenceScorer` is run on the same validation episodes under
real associated evidence, and reported at exact-at-one and exact-at-five
beside the fitted model. This answers whether fitting improved anything over
the hand-designed prior, rather than only over zero evidence.

## 12. Result classification

If the success rule holds and the collapse check passes:
`FAILURE_CONDITIONED_AST_SELECTION`. This means failure evidence measurably
improves which new AST is proposed. It does not mean the AST works, that the
language gained reach, that semantics were invented, or that any score moved.

Otherwise: `FAILURE_CONDITIONING_NOT_ESTABLISHED`, with
`NEW_AST_GENERATION` preserved as the standing earned result.

## 13. What follows

On a pass, the single recommended next action is to implement the
already-specified ConstructiveExtensionCompiler, and this block stops before
building it. On a failure, the single recommended next action is to diagnose
the frozen scorer failure without changing the corpus or the controls.

The supplied typed interface means that even a pass does not establish
autonomous gap inference. Supplied-interface constructive selection and
autonomous missing-capability diagnosis are different claims and are not
blurred.
