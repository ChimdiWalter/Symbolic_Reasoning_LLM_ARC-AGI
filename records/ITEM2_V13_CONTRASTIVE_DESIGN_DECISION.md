# Item-2 v1.3 contrastive design: decision record

Written 2026-09-24, before any v1.3 episode was generated.

| artifact | identity |
|---|---|
| protocol | `docs/CORA_TTI_CONSTRUCTIVE_PROPOSER_PROTOCOL_v1.3.md` |
| protocol sha256 | `66aa1c561ac4fd2a619459f15919282776a5898ab3ae6f36ae6944a5389d8f1e` |
| manifest | `outputs/tti/constructive_protocol_v1.3_manifest.json` |
| manifest sha256 | `9492f392d13e95b033b3f6a77d6dd75d27cbb11b6d0ac7dad104901fab56de14` |
| superseded draft | commit db6f500, retained, not authoritative |
| v1.1 and v1.2 | preserved unchanged |

## Why v1.2 failed discrimination

Its scorer experiment returned `FAILURE_CONDITIONING_NOT_ESTABLISHED`, and the
preregistered diagnosis ruled out the two obvious causes. Capacity is not it:
a bounded nonlinear readout gave the candidate features a delta of -0.0156
with one fold of five positive. Compression is not it: all 180 episodes had
distinct candidate vectors with zero collisions, and a 42-field descriptor
taken from the stored graph was worse than demonstration statistics, with the
recorded caveat that its width against 144 episodes per fold confounds that
test.

Demonstration statistics do not explain the target either, predicting the
first partition token at 0.383 against a 0.411 majority baseline. No evidence
group recovered the target, and yet 45 of the 45 closest pairs by
demonstration distance had different targets. The opportunity was present and
unused.

The mechanism this points at is a coordinate mismatch. The frontier speaks the
deployed reasoner's language of segmentation variants, correspondences,
selectors and parameter fits. The target speaks the constructive grammar's
language of partitions, selects, key features and paints. v1.2 never required
the two to be related.

## What v1.3 changes

Three things, and nothing else.

**Contrastive groups.** Two targets differing in exactly one grammar position,
so the contrast is controlled rather than incidental.

**Replicates, four per target.** v1.2 had one episode per target digest, which
made it impossible to separate target-specific failure structure from ordinary
instance variation. Four independent renderings per target supply the
within-target null the audit needs.

**A nonlearned gate.** The corpus is judged by a within-group nearest-neighbour
test against an exact chance level of 3/7, before anything is trained. If the
corpus cannot show that the frontier separates minimally different targets
better than chance, no model is fitted to look for a signal the data cannot
demonstrate.

## What v1.3 does not change

The grammar, its bounds, operators, terminals and banned families. The ordinary
baseline and its budget, enumeration, ordering and fitting, so R4 remains a
behavioural baseline-failure requirement. The registered occurrence-scoped
fitter, identity `2cc45152c430f8a2`, and its fairness guard. The deployed
reasoner, the repaired observer and the candidate-executor compatibility
repair. The failure-graph representation. The verifier and leave-one-out
discipline. The eighteen-feature model view, carried forward so results stay
comparable. The prohibition on reading any hidden output.

No solver, no dispatch, no hand-authored operator, no new primitive, no answer
predictor, no lookup, and no new scorer.

## Why normalization is calibrated separately

Distances need a scale, and picking that scale after seeing contrast results
would be tuning. Phase A therefore generates 200 episodes under the v1.2
schedule with no groups, no contrast and no selection, purely to fix the
per-feature means and standard deviations for both distances. Those constants
are published before Phase B starts, are never recomputed, and Phase A
episodes are never audit evidence.

## Why no group is filtered on its frontier

Generating many candidate groups, inspecting their frontiers and keeping the
separable ones would manufacture the very correlation under test. Selection is
permitted on demonstration statistics, which is the stated design intent, and
forbidden on the frontier. The frontier is judged once, at corpus level, after
the scheduled generation has run. A failing audit is preserved, not repaired by
discarding groups.

## The confound we are recording rather than hiding

A SELECT contrast changes the structural family, for instance `(0,0)` to
`(1,0)`, while PARTITION and FEATURE contrasts stay within family. The family
label is never a model input, but a SELECT-driven result could reflect family
difference rather than frontier content. Every statistic is therefore reported
split by contrast type, and gate G2 requires the primary result to hold on
PARTITION and FEATURE pooled, with SELECT excluded.

## Sample size, derived not inherited

The v1.2 figure of 120 training episodes is not reused. The 42-field
descriptor needs about ten observations per feature, so about 420 episodes.
The primary gate needs power against an exact null of 0.428571, and detecting
0.55 one-sided at p below 0.01 with about 90 percent power needs on the order
of 400 instances. Both converge, so the requirement is 60 training groups,
being 480 episodes, with 12 validation and 12 holdout groups on top.

## Stopping law and claim ceiling

Generation, audit and any later fit are separate blocks. This block may claim
only that the protocol is frozen and statically feasible. The extension
compiler stays blocked and is not licensed by any v1.3 outcome alone.
