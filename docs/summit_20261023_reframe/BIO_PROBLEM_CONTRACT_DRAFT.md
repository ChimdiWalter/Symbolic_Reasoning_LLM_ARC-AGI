# Biological bridge: problem-contract DRAFT for Pierce and Toni (2026-10-18)

**Status: SPECIFICATION ONLY. BIOLOGICAL APPLICATION: UNTESTED.**
- No biological data was read.
- No excluded or protected biological repository was accessed.
- Every field below is an open question until the collaborators fill it in.

## What would transfer, and what would not

The candidate for transfer is the **revision policy and the verification interface**. The ARC operators
(for example the ring operator) do not transfer; every biological operator would be domain-specific.

Four claims are kept separate:

| level | meaning | evidence needed |
|---|---|---|
| L1, same code | the same software runs in both domains | it runs; nothing more |
| L2, separately trained | the same method, trained in each domain separately | per-domain results |
| L3, frozen-policy transfer | a revision policy learned on ARC, frozen, improves revision decisions on the biological task | against a randomly initialized policy, a biology-trained policy, and failure-blind and shuffled-trace controls |
| L4, validated biological benefit | the transferred decisions improve independently validated predictions | held-out conditions or a prospective experiment |

Showing that a software component causes a prediction gain is **not** showing that the model found a
biological cause.

## Fields to fill (Pierce and Toni)

| field | question | answer |
|---|---|---|
| scientific question | what is predicted, and why does it matter? | _open_ |
| "displacement versus dispersion" | the operational definition in this study: what is displaced or dispersed, and measured how? | _open_ |
| data units | the observation unit (cell, well, sample, condition) and the measured variables, with units | _open_ |
| permissions | who owns the data, whether it may be used for this test, and where it may be stored | _open_ |
| structure | contexts or conditions, replicates (biological and technical), batches | _open_ |
| allowed observations | what the system may see at inference time | _open_ |
| targets | the exact predictions to be scored | _open_ |
| nuisance variables | batch, plate, timing, instrument | _open_ |
| baselines | the standard analysis; the simplest model that must be beaten | _open_ |
| revision actions | which representation revisions, model revisions and experiment requests are allowed | _open_ |
| independent validation | held-out conditions or replicates, another lab or cohort, a prospective experiment | _open_ |
| tolerance | what counts as a correct prediction (an ARC check is exact match; here it is calibrated error) | _open_ |
| falsification | the result that would show the policy does **not** transfer | _open_ |

## Why the validator differs from ARC

- An ARC answer is checked by exact match on a held-out grid.
- A biological prediction needs:
  - a tolerance and calibration;
  - replicate structure, so that two measurements of one sample are not counted as independent evidence;
  - held-out conditions, not held-out cells;
  - in the end, an experiment.
- Leave-one-out over demonstrations is a consistency check, **not** proof of general validity, in either
  domain.

**No clinical or commercial efficacy claim follows from any of this.**
