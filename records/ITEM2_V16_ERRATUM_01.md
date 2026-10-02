# Item-2 v1.6 erratum 1: corrections from the one pre-run adversarial review

Recorded 2026-10-02, about 19:40 UTC. The review ran on the first freeze
4f9c77b (protocol sha256 be1b1e54..., manifest sha256 72463019...). No
prospective data existed; none exists now. No threshold, effect floor, gate
rule, P0 key, order or direction changed.

## Review conduct, checked against the filesystem

- Every tracked file's sha256 before and after the review: identical (2,118
  files); no untracked file; no prospective corpus, engine directory or
  response file created.
- Tool inputs scanned (46 shell commands, 1 Read, 1 Write): the Write went to
  the reviewer's own scratchpad; reads of the generator, freeze and runner
  scripts were reads; one recursive directory listing from the tti root
  never completed and was stopped by exact PID after the review (it reads
  no file content). No forbidden tree was opened. The permitted test suite
  was run (19 passed).

## Findings and dispositions

Blocking: none.

| id | finding | disposition |
|---|---|---|
| M1 | The manifest's `classification_ladder`, `licenses_on_pass_only` and `arms` were the pre-amendment-2 text (two arms, no P0_then_D, no sub-floor class), contradicting protocol section 9 and `classify()`. | `scripts/freeze_v16.py` now writes the 11-rule ladder of section 9, the licence including rule 3, `gated_arms_in_order`, and the P0_then_D controls in `arms`. Re-frozen. |
| M2 | With 440 groups and an ambiguous share of 0.646, P(ambiguous groups < 280) is about 0.32, so one negative in three would fall to the underpowered rule by the stop rule alone. | `target_groups` 480 (about 310 ambiguous, SD about 10.5, P(< 280) about 0.002). Floor, target, slot cap and wall cap unchanged. |
| M3 | Three gated arms, first pass wins, no multiplicity control; the gated-arm set and the sub-floor class were fixed after the development evaluation. | Recorded in the protocol and the manifest: family-wise alpha for a pass of some arm is at most 0.03 (the arms are strongly dependent, so well below that); P0 alone keeps 0.01 exactly. Not corrected; the arm set was fixed before any prospective data (plan amendment 2). |
| M4 | The power simulation draws queries independently within a group, so 0.92 is an upper bound; with the disagreement direction shared within groups it falls to about 0.85 (rho 0.5) and 0.78 (rho 1). | `scripts/v16_power.py` now simulates rho 0, 0.5 and 1 and the record carries all three; the protocol states the upper-bound status. |
| M5 | The evaluator did not bind `v16_test_responses.json` to the corpus. | `response_integrity` now requires `admitted_records_sha256` to equal the binding over the admitted records (the same computation as the response script), for the test and the training responses; a mismatch blocks the audit (tested). |
| minor | Protocol said the state hash is taken around every probe; the run took it per group. | Per episode now, plus an A/B order recheck on the episodes whose group digest starts with hex 0 (one sixteenth); `order_check_passed` false blocks the audit (tested). Protocol section 2 corrected. |
| minor | A convergence failure of a reporting-only arm (R, P2, F_S7) voided the verdict under rule 0 although P0 fits nothing. | Rule 0 now reads the gated-arm fits (D, P1, P1 shuffled); all-arm convergence is reported separately. |
| minor | `v16_supp_dependence.py` omitted P0_then_D. | Added. |
| minor | The evaluator's leak check omitted finiteness. | Added. |
| minor, recorded only | The logit's run-time order check is tautological (invariance is exact by construction); `state_snapshot` does not cover modules the probe never touches (listed by the reviewer); the generation path's engine observation writes side files under the engine directory not covered by `engine_state_problems` (pre-existing v1.5 behaviour); admission is time-budget dependent, so a resumed corpus is a valid draw but not byte-identical to an uninterrupted one (pre-existing v1.5 property). | Recorded. |

## Pure-reasoning statement (reviewer's item 15, accepted)

P0 is parameter-free at inference time: no fitted weight or development-tuned
number enters its decision. It is not pure reasoning in the strictest sense:
it depends on hand-set constants of the frozen reasoner and probe
(MIN_KEY_WITNESSES 2, P0_TOL, ROUND, the per-demonstration normalisation of
`table_entries`) and on the frozen K and fitter that define the ambiguous
population. P0_then_D falls back to the fitted D selector and is labelled
hybrid everywhere.

## Re-freeze

The manifest is rewritten by `scripts/freeze_v16.py outputs/tti/v16_caps.json`
after the power record; the new identities are in the manifest, its hash
file, RESUME.md and the stage ledger. The order after the re-freeze is
unchanged: STOP and return to the user before any prospective data.
