# Item-2 v1.6: the one adversarial review (request)

Written 2026-10-02 at the freeze. The reviewer works read-only on the frozen
commit named below, with no access to Step B, Reasoning_Project, VDCG,
E_transfer, the Lockbox or any ARC answer file, and must not fit, score or
run anything on real data except the synthetic tests. Every tool call the
reviewer makes is scanned afterwards; a self-report of restraint is not
evidence.

## Frozen objects

- Frozen commit: `4f9c77b` (Reasoning_Project_arc2026)
- Protocol `docs/CORA_TTI_CANDIDATE_FAILURE_RESPONSE_v1.6.md` sha256 `be1b1e54c4cff2dfe0f158979c74096963fa9e887086b8215608ae260a59d25d`
- Manifest `outputs/tti/candidate_failure_response_v16_manifest.json` sha256 `724630194b2709e69c00ba213cff83be3bb738a9555c354d388f0c213ea5d148`
- Probe identity `e7d72f673b89cdb52195569efc7c923ca98dc42f69c76a9cf4776def0b7765c6`; fitter identity `2cc45152c430f8a2f9cfbcfd8c0bd6ad02ca6793819c6fcf16ede2060e6fc9d7`
- P0 keys ['loo_exact', 'loo_cell_error', 'loo_fit_fail', 'table_entries'] with signs [1, -1, -1, -1]; P1 representation R0
- Caps {"floor_ambiguous_groups": 72, "slot_cap": 6000, "target_ambiguous_groups": 280, "test_groups": 440, "wall_clock_s": 432000}; transfer gate {"alpha_above_chance": 0.05, "min_unseen_groups": 30, "unseen": "token pair held out by the frozen hash rule or absent from the training resource"}
- Implementation sha256 (first 16):
  - `cora_arc2026/engine_trace.py` `adda371babb8ebd7`
  - `cora_arc2026/scorer_fit.py` `9123894b7fa9d4d3`
  - `cora_arc2026/v13_gen.py` `1d389abe6ddb70e2`
  - `cora_arc2026/v14_loc.py` `010fe720c6f7c4f1`
  - `cora_arc2026/v15_sel.py` `810dc0a70b33583b`
  - `cora_arc2026/v16_cfr.py` `e7d72f673b89cdb5`
  - `cora_arc2026/vendor/tfg_extractor.py` `268149016febceef`
  - `geocat_arc/object_reasoning/_trace_hook.py` `7c3d5a52e394c422`
  - `outputs/tti/constructive_protocol_v1.3_manifest.json` `9492f392d13e95b0`
  - `outputs/tti/v13_calibration/calibration.json` `ba82865e52cd9e02`
  - `outputs/tti/v15_test_corpus_sha256.txt` `d0620fa4f8dd228b`
  - `outputs/tti/v16_dev_report.json` `d00eca85cc9f7ca3`
  - `outputs/tti/v16_exclusion_digests.json` `e936bc6fe364fba1`
  - `outputs/tti/v16_power.json` `7872637eb5156c43`
  - `records/ITEM2_V16_DEVELOPMENT_PLAN.md` `5af9d9ce2228ece1`
  - `scripts/evaluate_v16_cfr.py` `e8245e90743e1157`
  - `scripts/generate_v16_pairs.py` `c02ade756c04691c`
  - `scripts/run_v16_generation.sh` `9a916c0b8fdc102e`
  - `scripts/run_v16_post_generation.sh` `1de323b06364ad07`
  - `scripts/v16_build_exclusion.py` `0c5617afefd99e15`
  - `scripts/v16_dev_evaluate.py` `77329951adcbe7a1`
  - `scripts/v16_power.py` `22843bf5a2e93624`
  - `scripts/v16_responses.py` `9ae9aa97631b9689`
  - `scripts/v16_supp_dependence.py` `13dd814d35dde6f5`
  - `tests/test_v16_cfr.py` `d0c7d7e0fc94f2fb`
  - `tests/test_v16_prospective.py` `7b202655dde538a5`
- Dependency trees: cora_arc2026 `dd0b09d99ee5d770`, cora_parent `b64b49cf7ec5a678`, cora_tti `fbc73a101c0d74cd`, geocat_arc `4cee35c0048c1552`, level4_blind_runtime `cad36fd5458b97ba`

## What to read, in order

1. `records/ITEM2_V16_DEVELOPMENT_PLAN.md` (sections 1 to 14)
2. `records/ITEM2_V16_DEVELOPMENT_RESULT.md`
3. `docs/CORA_TTI_CANDIDATE_FAILURE_RESPONSE_v1.6.md`
4. `outputs/tti/candidate_failure_response_v16_manifest.json`
5. `cora_arc2026/v16_cfr.py`, `scripts/v16_responses.py`,
   `scripts/evaluate_v16_cfr.py`, `scripts/generate_v16_pairs.py`,
   `scripts/v16_supp_dependence.py`, `scripts/v16_power.py`,
   `scripts/freeze_v16.py`, `scripts/run_v16_generation.sh`,
   `scripts/run_v16_post_generation.sh`
6. `tests/test_v16_cfr.py`, `tests/test_v16_prospective.py`
7. For the reused parts: `cora_arc2026/v15_sel.py`,
   `scripts/evaluate_v15_selection.py`, `records/ITEM2_V15_SELECTION_RESULT_20261001.md`

## Try to falsify each of these

1. **Hidden-output leakage.** Does any probe input, response field, view or
   fit touch a test output, a solution file, a target AST, a label, a digest
   or a seed in a way that could reveal the truth? Trace `probe`,
   `episode_responses`, `build_queries`, `design`, `fit`, `score`.
2. **Candidate A/B asymmetry.** Is any computation different for the anchor
   than for the contrast, other than through their semantics? Is the
   presentation order ever a function of the truth?
3. **Candidate-order dependence.** Is P0 exactly antisymmetric? Is the logit
   choice order-invariant, including with the response term and the
   re-oriented donor Delta?
4. **Accidental use of target identity.** Can `target_index`,
   `target_digest`, `truth`, `other_candidate_fits` or the token identity
   reach a P0 decision or a P1 input other than through the five
   grammar-state inputs and the per-token weight rows that v1.5 already used?
5. **Reuse of v1.5 test groups.** Is every v1.5 test target and group digest
   in the v1.6 exclusion set (including skip records)? Does the generator
   skip before any engine run? Does the evaluator's integrity audit catch an
   excluded digest, a repeated digest, a wrong seed base, a wrong family?
6. **Response features reconstructing the truth.** On ambiguous queries both
   candidates fit all N demonstrations by definition. Could `table_entries`
   or the LOO fields encode which candidate generated the episode by
   construction rather than by generalization (for example through the
   generator's own fitting path)? State the mechanism if so.
7. **Matching failure.** Does the donor shuffle ever pair a query with its
   own group, a different verification status, or re-orient wrongly? Is a
   same-pair donor's Delta re-oriented by token identity correctly? Is the
   fidelity reported?
8. **Non-independent CV units.** In development: are the CV-A folds really
   pair-disjoint; is the residualizer ever fitted on evaluation data; does
   any development statistic leak into a frozen threshold other than the
   caps and the representation choice allowed by the plan?
9. **Probe state leakage between A and B.** Does any cache, module table,
   memo or file persist between the two probes of a pair, or between
   episodes? Is `state_snapshot` broad enough? Name what it misses.
10. **Persistent mutation of K.** Does any code path register, install or
    write a production, table or learned value?
11. **Fitter or selector leakage.** Is the same fitter identity used by the
    probe, the admission law and the verification diagnostic? Does the
    evaluator fit anything on test queries?
12. **Threshold ambiguity.** Is every gate, the floor, the target, delta_min,
    the transfer gate and the decisive-failure rule stated once, numerically,
    with no room for an outcome-dependent reading? Is the floor retention
    recorded with its risk?
13. **Unreachable or overlapping ladder branches.** Walk every combination of
    gate outcomes for the three gated arms through `classify`. Is any
    outcome mislabelled (a significant positive called inconclusive, a
    sub-floor positive called a pass, a transfer failure called a pass)?
14. **Restart nondeterminism.** After a reboot mid-generation and a resume,
    is the corpus identical to an uninterrupted run (slot order, seeds, cap
    from the first start)? Are responses a pure function of the records? Is
    the evaluator byte-identical twice?
15. **The pure-reasoning claim.** Is P0 genuinely parameter-free at inference
    time? Name anything in its path that is fitted, tuned on development
    data, or depends on a learned object. Is P0_then_D correctly labelled
    hybrid everywhere?
16. **Power and caps.** Is the power model's discordance and group-size use
    sound for the group-sum sign-flip test? Is the 440-group cap consistent
    with the 280 ambiguous-group target at the development ambiguous share?

## Report format

For each item: FALSIFIED (with the exact file, line and mechanism),
NOT FALSIFIED (with what was checked), or UNABLE TO CHECK (why). Then a
single verdict: BLOCKING defects, MAJOR findings, MINOR findings. Do not
propose redesigns beyond what a finding requires. Do not run the generator,
the response script on real data, or the evaluator on real data.
