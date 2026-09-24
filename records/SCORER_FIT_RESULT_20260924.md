# Stage-B scorer fit: result

Run 2026-09-24 under preregistration version 4, sha256 `14f0bdc7...08be448`,
sealed before the fit. Corpus protocol sha256 `31a74764...bbe6bb98`.
Checkpoint sha256 `22d02bf0643ad2c2`. Nothing was compiled, installed or
scored on ARC. Step B untouched.

## Verdict

**FAILURE_CONDITIONING_NOT_ESTABLISHED.** One of the two preregistered gates
passes and the other fails.

| gate | result |
|---|---|
| associated beats shuffled | **PASS**, by 0.197 nats per token |
| associated beats aggregate only | **FAIL**, aggregate only is better by 0.013 |

## Measured, all five conditions, 32 validation episodes

| condition | mean per-token target logprob | exact@5 | distinct rank-1 | modal share | rank-1 entropy |
|---|---|---|---|---|---|
| real associated | -1.24823 | 0.0 | 22 | 0.125 | 2.946 |
| shuffled | -1.44489 | 0.0 | 22 | 0.125 | 2.946 |
| irrelevant | -1.44200 | 0.0 | 16 | 0.188 | 2.491 |
| aggregate only | **-1.23562** | 0.0 | 15 | 0.312 | 2.367 |
| none | -1.29877 | 0.0 | 1 | 1.000 | 0.000 |

Paired per episode: associated beats shuffled on 23 of 32, and beats
aggregate only on 18 of 32. So a majority of episodes favour the full
evidence, while the mean favours aggregate only, which means the gap is
driven by a minority of episodes where the candidate-associated features hurt
badly.

## What this establishes

**Evidence identity matters.** Real associated evidence beats another
episode's evidence by a wide and consistent margin, on the mean and on 23 of
32 paired episodes, and the rank-one proposal changes on 30 of 32 episodes
when the evidence is swapped. The model is genuinely conditioned on what it
is given. The `none` condition collapses to a single rank-one proposal with
zero entropy, which is the signature the whole exercise was built to detect,
and real evidence produces 22 distinct rank-one proposals instead.

**The candidate-associated failure evidence does not earn its place.**
Neutralizing the ten candidate-associated features, leaving only the
demonstration statistics, does not hurt and very slightly helps. Whatever
useful conditioning exists comes from the demonstration-level statistics,
which are themselves task-specific. The typed failure frontier, the thing the
observation repair and the compatibility repair existed to deliver, adds
nothing measurable to constructive selection here.

That is the honest reading and it is a negative result about the frontier,
not about conditioning in general.

## What this does not establish

No target was recovered in any condition. Exact-at-five is zero across all
five, which the adversarial review predicted before the run and which is why
the gate metric was changed to target log-likelihood in advance. Nothing here
speaks to whether a proposed AST would work, whether the language would gain
reach, or to any ARC score.

## Run facts

Architecture: state-conditional log-linear model over grammar-legal tokens,
21 terminals by 21 inputs, 441 parameters, no hidden layer, non-LLM.
15 live evidence features after three constant ones were dropped
(`empty_frontier`, `same_shape_all`, `shape_mismatch_count`), plus five
structural decoder-state inputs and a bias.

Training: full-batch gradient ascent, learning rate 0.5, L2 1e-3, zero
initialization and therefore deterministic. Ran the full 2000 epochs with no
plateau, so the selected and final checkpoints are identical and the
preregistered checkpoint-selection mitigation is moot here. Wall time 145
seconds.

Leakage: 215 views scanned, 0 violations, using the hardened v1.2 scanner that
was separately verified to catch a digest stored as a number, a token name, a
split echo, a seed echo and an episode identifier echo.

Unfitted baseline, disclosed as structurally handicapped because the old
evidence structure has no field for five features the fitted model receives:
exact-at-five 0.0, 9 distinct rank-one proposals against the fitted model's
22.

Structural holdout, descriptive only, n = 3, insufficient sample size for any
structural-family inference: mean per-token target logprob -1.571,
exact-at-five 0, 3 distinct rank-one proposals.

## Claim earned

None beyond what already stood. `NEW_AST_GENERATION` remains the standing
earned result. Failure conditioning is not established.

## Claims not earned

Learned failure conditioning, autonomous construction, constructive reach,
semantic extension, transfer, and any ARC score movement.

## Next action

Diagnose the frozen scorer failure without changing the corpus or the
controls. The specific question the data poses is why the candidate-associated
features fail to help when the demonstration statistics do, and whether that
is a property of the features, of the log-linear model's capacity, or of the
targets being largely determined by demonstration-level structure.

The ConstructiveExtensionCompiler remains blocked. A failed discrimination
result does not license it.
