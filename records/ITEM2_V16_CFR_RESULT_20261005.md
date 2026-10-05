# Item-2 v1.6 bounded repair (candidate-conditioned failure response): prospective result

Recorded 2026-10-05 from the sealed reports of the same day. Nothing was
refitted, rescored or changed after the reports were written. The
development evidence (v1.5 corpus) is in `records/ITEM2_V16_DEVELOPMENT_RESULT.md`
and is not repeated as evidence here. Step B was not read.

## Official outcome

**PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES** (ladder rule 3): the
second gated arm, P0_then_D, passes gates A, B, C, D, H and T. Under the
frozen licence this unlocks the generic ConstructiveExtensionCompiler block.
**The headline is hybrid**: a deterministic intervention rule whose ties
fall back to the learned demonstration-summary selector. The pure arm P0
alone did not pass.

The test reached 136 verification-ambiguous groups, above the 72-group
floor and below the 280-group target (the report's `powered` flag is false).
The frozen ladder states that a positive stands at the floor or above; rule
3 precedes the underpowered rule 7.

## Identities

| item | value |
|---|---|
| freeze | 97d7164 (erratum 1; first freeze 4f9c77b superseded) |
| protocol sha256 | `d5b9358766a92f020f782a53d7517becfc97ce74ec753d1b4ab7699150c052aa` |
| manifest sha256 | `d1890a46ad786d950cf351198749e37565a6169be42ff05e30f3eacf8fd36f93` |
| official report sha256 | `6f795c42eea5902b9e11894cd2ee6d3dba4aa8af0acd006cd85647cf922f5204` (main, pass 1, pass 2 identical) |
| test responses sha256 | `17b2eb9dd131ff6352b0b371d2d2ed82882de50e716b54aad4444ddc6da419a7` |
| supplementary dependence sha256 | `d2090a974a9371765c2cd8b6b01794701792723455f2b0a5982d910a0451b188` |
| terminal verification sha256 | `3f5d3e486f5f1f250026cc0f71276e13ca67aa934969cd1f982ca1cbdcadbb96` |
| test-set hash list | `outputs/tti/v16_test_corpus_sha256.txt` (6,000 records plus run state and run end), sha256 `86df0d20f502077d207b9429e274a6df9e54503f69675531a8cd9af2104baca5` |

## Generation

- Launched 2026-10-02T23:22:39Z (chain 1178785, generator 1178792, nice
  19); ended 2026-10-05T14:40:40Z, exit 0, stop reason `slot_cap`.
- 6,000 slots, 201 admitted groups (201 records, no duplicate), 227,880 s
  (63.3 h) from the first start; 147,268 pair and 1,316,831 replicate
  attempts; median slot 26 s.
- No reboot during the run (boot id 5c543236 throughout); the auto-resume
  hook was never triggered.
- Every record passed its per-slot freeze check; environment only
  `ARC_META_BUDGET_S=8`, `PYTHONHASHSEED=0`.
- Families (admitted / slots): (0,0) 1/1,200, (0,0,0) 27/1,200, (0,1)
  24/1,200, (1,0) 33/1,200, (1,1) 116/1,200.
- Rejections: TARGET_NOT_FITTABLE 1,055,672; TARGET_EXECUTION_UNDEFINED
  186,944; PAIR_REPLICATES_SHORT 130,824; OTHER_FROZEN_CODE 48,081;
  EXCLUDED_TARGET_DIGEST 10,266; BASELINE_SOLVED 7,437;
  EXCLUDED_GROUP_DIGEST 5,439; TARGET_ALREADY_IN_CORPUS 491;
  NO_INFORMATIVE_TFG 308; DUPLICATE_GROUP_DIGEST 47 (skipped before any
  engine run).
- Admission was about 3.4 percent of slots, against the 10.5 percent the
  caps assumed, so the slot cap bound before the 480-group target (recorded
  2026-10-04 before any outcome; caps not changed).

## Post-generation sequence (frozen runner, 2026-10-05)

1. test responses 14:44 to 15:16 UTC: 201 groups, 1,608 episodes, state
   restored on every episode, order recheck on 64 episodes passed;
2. integrity only: PASS;
3. sealed evaluator twice: byte-identical;
4. dependence sensitivity: exit 0 (supplementary, below).

## Terminal verification (supplementary, written before outcomes)

`scripts/v16_terminal_verify.py`: **71 of 71 checks pass**.
- Freeze, protocol, implementation, dependency trees and runtime all match.
- The three reports are byte-identical, and their freeze, integrity,
  leakage and overlap lists are empty.
- Responses are bound to the exact corpus; the corpus audit is clean.
- Independent recomputation of P0 and P0_then_D (its own presentation
  order, P0 rule, D fit, sign-flip tests, intervals and ladder) reproduces
  every reported value and gate, and the class.
- The class does not depend on P1.

## Population

| quantity | value |
|---|---|
| test groups | 201 |
| queries | 1,608 |
| decided by plain verification | 951 |
| verification-ambiguous | 657 queries in 136 groups |
| structurally unseen pairs (held out or absent from training) | 105 groups; 65 ambiguous groups, 291 ambiguous queries |
| training resource | 167 development groups, 1,336 queries |

## Arms (accuracy on ambiguous queries; unseen-pair ambiguous; end-to-end with verification first)

| arm | ambiguous | unseen ambiguous | end-to-end |
|---|---|---|---|
| D (demonstrations) | 0.580 | 0.584 | 0.828 |
| **P0_then_D** | **0.641** | **0.667** | **0.853** |
| P0_then_D, failure replaced (donor) | 0.604 | 0.612 | 0.838 |
| P0_then_D, identity swapped | 0.493 | 0.478 | 0.793 |
| P0 (pure rule; ties half credit) | 0.574 | 0.595 | 0.826 |
| P0, failure replaced | 0.536 | 0.540 | 0.810 |
| P0, identity swapped | 0.426 | 0.405 | 0.766 |
| P1 (hybrid logit, R0) | 0.597 | 0.591 | 0.835 |
| P1, failure replaced | 0.580 | 0.584 | 0.828 |
| P2 (passive, D + F_S7) | 0.578 | 0.570 | 0.828 |
| F_S7 alone | 0.530 | 0.515 | 0.808 |
| R (response alone, logit) | 0.505 | 0.491 | 0.798 |

## Gates (ambiguous population; exact one-sided group sign-flip tests; alpha 0.01; delta_min 0.05)

**P0_then_D (passes every gate):**

| gate | value |
|---|---|
| A above 1/2 | 0.641, p 8.7e-10 |
| B over D | +0.0609 per query (95% CI 0.0287 to 0.0931), p 3.8e-5, groups +27 / -3 |
| C over its replaced-failure control | +0.0365 (95% CI 0.0078 to 0.0652), p 0.0069 |
| D floor | 0.0609 >= 0.05 |
| H | nonnegative |
| T transfer (65 unseen ambiguous groups, minimum 30) | +0.0825 over D (95% CI 0.0336 to 0.1314), above chance p 1.7e-5, groups +14 / -0 |

**P0 (fails B, D, H):**
- A passes: p 1.9e-11.
- B fails decisively: -0.0061 (95% CI -0.0575 to +0.0453), upper bound 0.037, p 0.60.
- C passes: +0.0381 (95% CI 0.0155 to 0.0606), p 0.00035.
- T passes.
- Why: P0 makes no choice on 79.8 percent of ambiguous queries.
  - When it decides (133 queries in 57 groups, coverage 20.2 percent) it
    is right 86.5 percent of the time, against D's 56.4 percent on the
    same queries (+0.30, 95% CI 0.16 to 0.45, p 3.8e-5).
  - `loo_exact` decides 74 queries (85.1 percent right) and
    `table_entries` 59 (88.1 percent right); the two error keys never
    decide.

**P1 (fails B, C, D):** +0.0167 over D (p 0.24); +0.0167 over its control
(p 0.24).

**P2 (passive, the v1.5 channel):** -0.0015 against D (p 0.56). The v1.5
negative replicates on new data.

## Supplementary checks (never change the official result)

- **Dependence-aware gate C: UNRESOLVED for all three gated arms.** Tier 1
  has 9 donor components and tier 2 has 12 usable fixed blocks, both below
  the 30-unit minimum. The pair-first donor matching links groups through
  their shared candidate pairs (same-pair donors 88 percent), and most
  two-group blocks cannot be matched internally. So gate C's group-level
  test is the only resolved test of episode-specificity, and it rests on
  the stated exchangeability assumption.
- **Shuffle fidelity (test):** same token pair 0.88, same family 0.59,
  D_RICH correlation 0.59, same verification status 1.0, same group 0.

## Claim (LEVEL 1 of the frozen ladder; hybrid headline)

On prospectively generated candidate pairs, disjoint from every earlier
corpus, that plain verification cannot settle, a deterministic rule reads
how each proposed extension changes the reasoner's own failure state under
leave-one-out re-derivation. When that rule's ties are resolved by the
learned demonstration-summary selector, it chooses the true extension more
often than the demonstration summary alone:
- +6.1 accuracy points (0.641 against 0.580);
- +8.2 points on candidate pairs absent from training;
- it beats the same rule fed a matched donor episode's failure response;
- it falls to 0.49 when the two candidates' responses are exchanged.

The rule alone abstains on four ambiguous pairs in five; on the fifth it
is right 86.5 percent of the time.

This is not a claim of pure reasoning: the passing arm uses the fitted
demonstration selector on ties. It is not a claim of self-improving
reasoning, invention, a new ARC capability or closed-loop self-extension;
those need the B/P/U/L/T/A witness of a later stage.

## Limitations

- **Below the powered size.** The test has 136 ambiguous groups against the
  280-group target, because admission ran at a third of the planned rate.
  The pass stands under the frozen floor rule, but the estimates are wide.
  - The floor is met on the point estimate (0.061), not with confidence:
    the 95 percent lower bound is 0.029.
- **Gate C is the weakest gate.** It passes at p 0.0069 against alpha 0.01.
  It would not pass a Bonferroni correction across the three gated arms
  (0.0033); the protocol recorded that the family-wise alpha is at most
  0.03 and did not correct it. Its dependence-aware version could not be
  resolved. Gates B (p 3.8e-5) and T (p 1.7e-5 above chance, p 6.1e-5
  over D) would survive any such correction.
- **One structural family dominates.** Family (1,1) supplies 81 of the
  136 ambiguous groups. P0's effect varies by family (it is negative in
  two of them; not gated).
- **The domain is synthetic.** The candidates are given pairs from the
  constructive grammar, and the reasoner probed is the domain's
  single-block base search, not the full ARC engine. No answer-key-free
  proposal, compilation or ARC task is involved.
- **Development was consistent.** P0_then_D was +0.045 on development
  cross-validation and +0.061 prospectively. The arm's place in the ladder
  was fixed after development and before any prospective data, and was
  disclosed.

## Consequence

The frozen licence holds: the next stage is the generic
ConstructiveExtensionCompiler, followed by removal of the oracle pair,
no-oracle proposal, the same-reasoner closed loop and the first real ARC
B/P/U/L/T/A witness. The compiler is not begun in this session.

## Reproduction

    # frozen post-generation sequence (needs the frozen corpus and environment)
    PYTHONPATH=<tti root> V16_WORKERS=4 .venv_arc2026/bin/python scripts/v16_responses.py test
    .venv_arc2026/bin/python scripts/evaluate_v16_cfr.py --integrity-only
    .venv_arc2026/bin/python scripts/evaluate_v16_cfr.py outputs/tti/v16_cfr_report_pass1.json
    .venv_arc2026/bin/python scripts/evaluate_v16_cfr.py outputs/tti/v16_cfr_report_pass2.json
    .venv_arc2026/bin/python scripts/v16_supp_dependence.py
    PYTHONPATH=<tti root> .venv_arc2026/bin/python scripts/v16_terminal_verify.py

Run every command with `PYTHONDONTWRITEBYTECODE=1`, `PYTHONHASHSEED=0` and
single-threaded BLAS.
