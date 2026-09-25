# Erratum 2 to Item-2 protocol v1.3

Recorded 2026-09-25, while the full generation was still running and **before
the auditor had been run even once, so before any G1 to G10 value existed**.
It corrects which records the auditor reads. It does not touch the descriptor,
the normalizer, the distance, the tie-break, the null, any statistic, any
p-value law, or any of G1 to G10.

Protocol and manifest hashes unchanged: `66aa1c56...389d8f1e` and
`9492f392...ab56de14`.

## Finding 1: the pilot is a deterministic prefix of the full run

The generator derives every seed as `groups_from + slot*10000 + attempt*100`,
and the slot index restarts at zero for each phase tag. The pilot and the full
run therefore use identical seeds for identical slot indices, so full slots 0
to 39 reproduce the pilot's 40 slots exactly: the same anchors, the same
contrast targets, the same demonstrations and the same admission outcomes.

This is a property of the frozen schedule rather than a defect. The pilot is a
prefix of the full run. Its consequence for the science is small and is stated
plainly: the rate `q` was measured on slots that also appear in the final
corpus. That affects only the sizing decision, and since the unconstrained
request of 3,360 exceeds the 1,200 cap, the cap binds and `q` has no influence
on the size actually run.

## Finding 2: the auditor would have counted one group twice

`load_groups` iterates every JSON file in the corpus directory and skips only
the name `pilot_result`. Pilot slot records therefore fall through and would be
read as full-run groups. Combined with finding 1, the single group admitted at
pilot slot 20 and the identical group at full slot 20 would both be loaded,
giving the same group digest twice, inflating the admitted count, and
double-weighting that group in every statistic.

The frozen protocol already forbids this. Its completion checks require no
duplicate admitted group digest and that no pilot group is counted as a
full-run group.

## The correction

The auditor now reads only records whose name begins with `full`. Pilot
records, the pilot result artifact and the calibration directory are excluded.

This changes record **selection** to match what the protocol already required.
It changes no statistic. The nearest-neighbour rule, the exact null of three
sevenths, the separation statistic, the binomial law and all ten gate
definitions are byte-identical.

## Why this is recorded rather than quietly patched

The correction is made before the auditor has produced a single number, so it
cannot have been chosen to move a result. Recording it now is what makes that
verifiable afterwards. The same discipline caught a constant-divisor defect in
erratum 1 and a state-blind scorer in the version 1.2 block, both before they
touched a result.
