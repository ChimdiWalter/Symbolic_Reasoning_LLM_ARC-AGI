# Item-2 v1.4 mechanistic frontier localization: design decision

**STATUS: DRAFT, IN PROGRESS, NOT FROZEN.** Saved 2026-09-27 mid-block at the
user's request. No protocol hash exists yet. No stagewise hit rate, distance
or separation has been computed on any data. No v1.4 experiment episode
exists.

## 1. Binding result that motivates v1.4

v1.3 complete: 1,200 of 1,200 slots, 29,763 attempts, 21 groups (FEATURE 14,
SELECT 7, PARTITION 0), 168 episodes, 41 distinct targets. G1 79/168 = 0.470
against 3/7, p = 0.156; G2 0.473, p = 0.195; G3 0.524; G4 mean 0.188, median
0.025; G5, G6, G7 fail; G8 to G10 pass. Official verdict: IDENTIFIABILITY GATE
FAIL. Identifiability not established; the designed 0.55 effect excluded; a
smaller effect possible. Record: `records/ITEM2_V13_CORPUS_RESULT_20260926.md`.

## 2. Stored-data trajectory inventory (schema only)

Inspected: key names, node kinds, attribute keys and edge relations of the 21
stored v1.3 groups, plus the extractor and observer source. No value was
compared across episodes.

| stage | stored in v1.3 | what exists |
|---|---|---|
| S0 demonstrations | AVAILABLE_PARTIAL | per-demonstration delta, palette and shape summaries; raw grids NOT stored |
| S1 perception / objects | NOT_STORED | never emitted by the observer |
| S2 candidate formation (`typed`) | AVAILABLE_PARTIAL | count only, in the census; group structures discarded |
| S3 selector induction | NOT_STORED | failures never emitted; recoverable only from event ORDER, which was discarded |
| S4 parameter fitting | AVAILABLE_PARTIAL | per-operator failure counts; `slot_fit_ok` structures discarded |
| S5 fitted executable candidates | AVAILABLE_PARTIAL | at most 12 terms, sorted by surface size, order lost |
| S6 near-miss mismatch | AVAILABLE_PARTIAL | one value signature per retained term, first defined demonstration only |
| S7 TFG | AVAILABLE_RAW | the 42-field descriptor and the stored graph |

## 3. Branch selected: B, counterfactual-twin trajectory study

Mechanical reason: everything stored is downstream of the extractor.
`build_tfg` keeps at most `MAX_FRONTIER_TERMS = 12` terms, only
`executed_not_exact` and `slot_fit_failed`, sorted by (class, surface, AST);
`typed` and `slot_fit_ok` structures and the observer's ordered candidate list
were never persisted. A stored-artifact study could only compare two
encodings of the same post-extraction graph, so it cannot distinguish
"trajectory differs, TFG loses it" from "trajectory does not differ", which is
the question. Chosen before any stage outcome was inspected.

## 4. Observability under Branch B, with NO new engine hook

The existing observer already records the ordered list of (AST, outcome).
v1.4 only persists it. Emission sites (`inducer.py` 2189 to 2210): each group
emits `typed`, then `slot_fit_failed` (carrying the induced selector),
`slot_fit_ok` (carrying the full rule), or nothing when
`_induce_selector_for` returned None. So:

| stage | Branch B source |
|---|---|
| S0 | demonstration features, reusing v1.3 Phase-A calibration (baseline, not a reasoning stage) |
| S1 | UNOBSERVABLE without a new hook; not added |
| S2 | multiset of `typed` group structures |
| S3 | per group, from order: selector induced (with its structure) or no fit event |
| S4 | `slot_fit_failed` by operator, `slot_fit_ok` by fitted action structure |
| S5 | every `executed_not_exact` and `exact` program, uncapped |
| S6 | every distinct near miss (cap 64) rendered on EVERY demonstration by the engine's own executor, class per demonstration, associated with its program |
| S7a | stored TFG graph before aggregation (frontier terms and their value-signature classes) |
| S7 | the v1.3 42-field descriptor with v1.3 Phase-A calibration, exactly as audited |

One generic canonicalization everywhere: numeric literals become `#`, names
and structure kept. Set-valued stages use the Ruzicka distance, which needs no
normalization constants. S0 and S7 reuse the committed v1.3 calibration
`ba82865e...51c7c02`.

## 5. Design correction that must be stated to the user

The directive asks to keep the exact 3/7 null. **With shared inputs that null
is no longer exact.** Replicate r of A and replicate r of B see identical
inputs, so under the null the query's own twin is systematically nearest,
the hit rate falls below 3/7, and the test becomes conservative in an unknown
amount. The same null hypothesis (stage descriptor independent of target
given the input) has an exact form under this design:

- twin-excluded nearest neighbour: for query (t, r), companions are the six
  episodes of the other three replicates, 3 same-target and 3 different;
- under the null the two members of every twin are exchangeable, so the
  exact null hit rate is **1/2** for every distance matrix (verified
  algebraically in the implementation: averaged over the 16 within-twin
  label swaps, each query's credit is exactly 1/2);
- ties share credit; strict hits (all tied nearest same-target) give an
  integer, conservative binomial test against 1/2;
- an exact within-twin swap randomization test (16 patterns per group,
  convolved across groups) accounts for within-group dependence.

Planned stage qualification: strict rate above 1/2 AND exact binomial
p < 0.01 AND exact randomization p < 0.01. Stricter than the directive, never
looser.

## 6. Sample size, exact

p0 = 1/2, p1 = 0.60, one-sided alpha 0.01, power at least 0.90:
**n = 336 instances = 42 twin groups**, critical value 190 strict hits
(size 0.00943, power 0.9106). The binomial power assumes independent
instances; the true power is lower because instances within a group are
dependent. For reference, 0.60 against 3/7 would need 112.

## 7. Static feasibility smoke, 2026-09-27

`logs/v14_smoke/smoke.py`, seeds from 200,000,000, disjoint from the
experiment and from every earlier corpus. Admission mechanics and parse
checks only; no distance between any two episodes was computed.

221 attempts in 99.7 s, 3 twin replicates admitted:

| code | count |
|---|---|
| TARGET_NOT_FITTABLE | 119 |
| TWIN_OUTPUTS_IDENTICAL | 55 |
| TWIN_DEMONSTRATIONS_UNDEFINED | 28 |
| OTHER_FROZEN_CODE | 9 |
| TWIN_INPUTS_DIFFER | 6 |
| ADMITTED | 3 |
| BASELINE_SOLVED | 1 |

Facts established: shared-input twins are mechanically possible; the
captured trajectory parses into S2 to S7a on real engine output; an admitted
replicate costs about 22 s. Every FEATURE contrast sampled had equal MDL.
**A one-feature swap often yields identical demonstration outputs on the
same inputs (55 of 221 attempts)**, which is why twin integrity requires at
least one differing demonstration output. This is an admission-mechanics
fact and is not used to reinterpret v1.3.

Disclosure: the smoke printed per-twin stage SIZES (event counts) for its
three admitted smoke twins. They are counts, not distances, on seeds that are
not experiment data, and they will not be used.

## 8. Planned classification ladder

Pipeline order S2, S3, S4, S5, S6, S7a, S7; S0 reported separately.

1. achieved instances below the floor of 112 (14 groups): MIXED_OR_INCONCLUSIVE
2. S7 qualifies: CURRENT_TFG_IDENTIFYING_UNDER_TWINS (outcome the directive's
   list did not name; v1.3's negative would then be attributable to instance
   noise)
3. any of S2 to S5 qualifies: RAW_TRAJECTORY_SIGNAL_TFG_LOSS, loss located
   after the last qualifying stage (S7a to S7 = aggregation loss)
4. only S6 qualifies: LATE_EXECUTION_SIGNAL_ONLY
5. only S7a qualifies: MIXED_OR_INCONCLUSIVE
6. nothing qualifies and n reaches 336: REASONER_TRAJECTORY_INSENSITIVE, at
   every OBSERVED stage (S1 unobserved)
7. nothing qualifies and n below 336: MIXED_OR_INCONCLUSIVE

A positive qualification is valid at any n at or above the floor, since power
affects only false negatives.

## 9. Planned group law

FEATURE contrasts only. Slot s cycles the five eligible anchor families. Up
to 25 (anchor, contrast) attempts per slot, seed SEED_BASE + s*10000 +
a*100, SEED_BASE = 100,000,000. Per pair up to 8 replicate seeds; the pair is
admitted when 4 twin replicates are admitted, abandoned once 4 is
unreachable. |MDL difference| = 0 required. Stop at exactly 42 admitted
groups, or at the hard compute cap, whichever first. Cap still to be fixed.

## 10. Done so far, and what remains before freeze

Done: `cora_arc2026/v14_loc.py` (capture, stage descriptors, twin-excluded
NN, exact randomization test, binomial, Clopper-Pearson, Holm,
classification), smoke script and log.

Remaining, in order:
1. fix the hard compute cap (slots and wall clock) and the diagnostic floor;
2. `scripts/generate_v14_twins.py` and `scripts/audit_v14_localization.py`;
3. `tests/test_v14_localization_feasibility.py`: skeleton, Ruzicka, twin
   exclusion, exact 1/2 null identity, randomization p, sample size, ladder,
   leakage (descriptors read only the allowlisted view), noninterference
   (capture equals the observer's list; engine result unchanged), S3
   derivation, FEATURE twin law, seed disjointness;
4. protocol `docs/CORA_TTI_MECHANISTIC_FRONTIER_LOCALIZATION_v1.4.md` and
   manifest `outputs/tti/mechanistic_frontier_v14_manifest.json`, hash both,
   commit (FREEZE);
5. RESUME, manuscript prospective wording, memory; one reviewer after seal.

Then STOP. Next action after freeze: RUN THE FROZEN v1.4 MECHANISTIC FRONTIER
LOCALIZATION EXPERIMENT.
