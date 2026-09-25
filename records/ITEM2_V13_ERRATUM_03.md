# Erratum 3 to Item-2 protocol v1.3

Recorded 2026-09-25, while the full generation was running and **before the
auditor had produced any G1 to G10 value**. It corrects a factual claim I made
in erratum 2 and records a measured property of the generator that affects how
reproducibility may be described. It changes no frozen parameter, no
statistic, no gate, and neither hash.

## The measurement

Pilot and full slots share the same seed schedule, so I claimed in erratum 2
that the pilot is a deterministic prefix of the full run. **That claim is
false, and I measured it.**

Comparing the first 20 slot pairs at identical seeds:

| outcome | count |
|---|---|
| same admission and same attempt count | 18 of 20 |
| **different** | **2 of 20** |

Slots 1 and 19, both FEATURE contrasts on families (0,0) and (1,0), were
rejected after the full 25 attempts in the pilot and admitted in the full run,
at attempts 6 and 13 respectively.

## The cause

Two stages of episode admission are bound by wall-clock budgets rather than by
work: the ordinary baseline search runs against an 8 second deadline, and the
full-engine observation runs against an 8 second deadline. How far each gets
therefore depends on machine load at the moment it runs. The same seed can
yield a different admission outcome on a busier or quieter host. Other work on
this machine varies over time, so the generator is not reproducible even
though its seeds are.

## What this corrects

Erratum 2's finding 1 is **withdrawn**. The seeds are identical; the outcomes
are not. Erratum 2's finding 2 and its fix stand unchanged on independent
grounds: the frozen protocol requires that no pilot group be counted as a
full-run group, so the auditor reads only full-run records regardless of
whether the two phases happen to agree.

## What this means for reproducibility claims

The distinction has to be stated precisely in the result record.

- The **corpus** is not reproducible. Regenerating it under the same seeds can
  admit a different set of groups. No claim of bitwise corpus reproduction may
  be made.
- The **audit** is reproducible, because it is a deterministic computation over
  a stored corpus. Running the sealed auditor twice on the same records must
  give identical values, and the wired chain checks exactly that.

The protocol's reproducibility requirement is therefore satisfied at the audit
level and is explicitly not claimed at the generation level.

## What this does not change

`q` stays frozen at 0.025 and is **not recomputed**. The frozen sizing rule
consumed it once, the unconstrained request of 3,360 exceeded the 1,200 cap,
and the cap binds, so the size actually run does not depend on `q` at all.

An observation worth recording honestly, and not acting on: the full run's
early admission rate is higher than the pilot's, 2 of the first 20 slots
against 1 of 40. If that held it would imply more admitted groups than the
pre-run projection of about 30, and the scale gate might not fail after all.
That is an early-sample observation under different machine load, not a
result. The projection was recorded before the run and may prove wrong in
either direction. **The measurement governs, not the projection**, and nothing
about the run, the cap or any gate is adjusted in response.

## Why this is recorded now

Because it is the kind of claim that would otherwise be inherited as true. I
asserted determinism from reading the seed arithmetic rather than from
comparing outcomes. Comparing outcomes took one command and showed the
opposite.
