# Item-2 v1.8: erratum 01

Written 2026-10-06, after the one adversarial review
(`records/ITEM2_V18_REVIEW_RESULT.md`, b98bd24) of the freeze e7afc0f
(manifest bd657faa), before any prospective data. No prospective seed (860,000,000
and up) was touched by anyone. The protocol was amended in place, every
amended rule marked "(erratum 01)", then re-frozen.

## Blocking

| finding | verified | change |
|---|---|---|
| B1. G1 cannot test failure specificity: both controls cannot propose by construction | yes: the first-frozen SHUFFLED_FRONTIER applied another task's residual cell coordinates to this task's grids (0 of 40 proposals on development); DEMO_ONLY ranks blocks by recall of changed cells and mostly picks conflicting blocks (0 of 40 verified). G1 would have passed on any 5 useful tasks | Two controls that keep the whole mechanism, caps and selection and remove only the task's failure frontier as the guide to which top layers to try: **SHUFFLED_FRONTIER (transplant)**, the donor's PARTIAL and FULL blocks in the donor's order with residuals recomputed on this task's demonstrations, and **BLIND**, K's 200 blocks in one fixed task-independent order (`BLIND_ORDER`, the review probe's seed 20261006, written as a literal). G1 = FAILURE_CONDITIONED against both. The old arms stay as reported sanity checks (SHUFFLED_COORDINATES, DEMO_ONLY). Development (`outputs/tti/v18_dev_controls.json`): transplant useful 26 of 40, BLIND 30 of 40, main arm 40 of 40; discordant 14 to 0 and 10 to 0. G1 power at N = 30 is 0.99 and 0.90 at those rates, 0.48 if the advantage shrinks to 15 percent of tasks; size 0.016 with no specificity. Protocol sections 1, 11, 13, 14 and 15, the development and feasibility records, and test 14 corrected. The main arm's code path is unchanged: it reproduced every stored development selection (40 of 40). |

## Major

| finding | change |
|---|---|
| M1. Undisclosed leave-one-out conditioning in the corpus | Protocol sections 14 and 15 now state that the corpus law also requires the generator's schema to re-derive every training pair under fitter-level leave-one-out, so leg L and P0's first key are measured on tasks pre-selected for that; L tests recovery and engine acceptance, not identifiability. |
| M2. S6 can never fail on this corpus | Protocol sections 9 and 15 declare S6 descriptive only with no evidential weight here (A by grammar, B by corpus law, C SEPARATED for 161 of 161 verified development candidates on the witness grids, 127 of 161 on the probes); the witness-set change is named as what made C unfailable; "new semantic capability" is not claimed from these counts, and the prospective report lists them under `s6_descriptive`. |

## Minor

| # | finding | disposition |
|---|---|---|
| 1 | development record said the main arm never reached the cap | corrected: tasks 37 and 39 reached 256 and still verified |
| 2 | design record section 11's rationale contradicted by data | corrected in design record section 12: the witness key merges more (161 against 250 representatives); selection identical on 38 of 40; kept for the duplicate law, its real effect is on S6 |
| 3 | PROPOSAL_LIMIT used only the last depth's cap flag | fixed: any depth |
| 4 | PROPOSAL_LIMIT and NO_VERIFIABLE_PROPOSAL cannot occur in the main arm | disclosed in protocol section 10 (they occur in the control arms) |
| 5 | K_ALREADY_SOLVES inside a fold makes L false | kept (conservative) and disclosed in section 8; the count is reported |
| 6 | fold infrastructure failures count as L false; fold leakage not counted; run errors outranked leakage | fold failures kept as L false (disclosed); fold-level LEAKAGE_FAILURE now counts toward PROPOSER_LEAKAGE; leakage now overrides every outcome, as section 14 says |
| 7 | DUPLICATE_EXISTING_SEMANTICS never an outcome | clarified in section 10 as an S6 qualifier only |
| 8 | witness leg A identical to B | A redefined: K* alone at 3x budget (24 s) does not reproduce the held-out output; on the 8 development engine tasks it accepted none |
| 9 | the prospective script fitted the generator's schema before the arms | moved after every arm, as section 14 says |
| 10 | test 6 vacuous; test 14 relied on the mechanical zero; test 15 checked only the Step-B path | test 6 now replaces fold i's held-out output and requires fold i's input unchanged; test 14 replaced by a test that the controls keep the mechanism, differ only in the tops and are not zero by construction (the main arm's order through the new path reproduces its proposals); test 15 also checks VDCG, E_transfer and Lockbox |
| 11 | D's feature path not covered by the reproduction; D runs on 6 or 7 demonstrations against a training mean of 4.96 | disclosed in section 6 |
| 12 | the MDL node key is constant within a depth | disclosed in section 6 |
| 13 | leg B depends on machine load | load averages recorded around the engine stage; leg A at 3x budget guards against a starved K* arm |
| 14 | `scan_input` docstring overstated what it checks | corrected: form and vocabulary only |
| 15 | no policy for an interrupted run | `--resume`: allowed only with a start record and no report or marker; finished tasks kept; every resume recorded in the report |
| 16 | duplicate digests allowed within the prospective corpus; seen/unseen only against development | duplicates now skipped (`distinct=True`, prospective only); seen/unseen stays relative to the 40 development structures, as declared |
| 17 | fold summaries dropped per-fold proposal counts | added |
| 18 | leftover `/tmp/v17run_*` directories | harmless; they predate the v1.7 erratum that removes engine directories; left in place |

The review also noted that the depth-3 middle-layer order was fixed in code
before development but missing from the design record; it is now stated in
design record section 12.

## Access deviations recorded with the review

One `find` by the reviewer printed the names (not the contents) of
non-Python files in the repository's `geocat_arc` copy, among them a
diagnostics `target_outputs.json`; some read-only parsing used system
`python3`. Neither affects any finding.

## Verification before the re-freeze

- Fast suite: 21 passed (`-m "not engine"`), including the three rewritten
  tests.
- Engine test on the erratum code: `logs/v18/engine_tests_erratum01.log`.
- Erratum development run (`scripts/v18_dev_controls.py`, 1,134 s): main
  arm identical to the stored development audit on 40 of 40; the numbers
  above.
- Feasibility regenerated (`outputs/tti/v18_feasibility.json`), N = 30 and
  W = 15 unchanged.
