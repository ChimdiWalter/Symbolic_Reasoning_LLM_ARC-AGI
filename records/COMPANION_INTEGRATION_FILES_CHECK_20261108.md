# Companion integration files: independent correctness check

Prepared 8 November 2026, about 05:30 UTC (7 November, Central time), at the author's request relayed in companion
note 0588 (its task 3: check the companion's integration files against named safe source reports before the paper
uses them). Companion notes 0586 to 0589 were read first.

## Scope

Files checked, in the companion tree `<companion study folder>/` (read only; nothing there was edited):

| file | SHA-256 | bytes |
|---|---|---|
| `cage/coordinator_reconciliation_20261108_v1/EXPOSURE_AND_COMPUTE_CORRECTIONS.md` (below: the exposure file) | `013cce94063194c2be9ac103ec7057640075ce3fc0b16cc9067eac3024297bb3` | 4,395 |
| `cage/study_b_terminal_update_20261108_v1/STATUS_FOR_AUTHOR_AND_PAPER.md` (below: the status file) | `03c845e12fd3b656aeb06d6ae63752121389d648de352db84773fc67440d7b33` | 6,238 |
| `cage/reproducibility_map_20261108_v1/BIOLOGY_AND_SHARED_CORE_MAP.md` (below: the map) | `fdafe51b2c59fe8e70fc9600abb5fbed2a993a19381a970c56eaccb258c31e46`, equal to the hash in 0588 | 23,165 |
| `cage/reproducibility_map_20261108_v1/BIOLOGY_AND_SHARED_CORE_MAP.json` | `7c3df6c2a05b0df4d8da599f992e300a22381f01e853ccd8e347a6fbe9fd25d8`, equal to the hash in 0588 | 136,286 |

Sources they were compared against:
- **Study B (the held grammar transfer study):** the saved safe aggregate snapshot
  `cage/natural_growth_b_local_takeover_20261107_v1/FINAL_AGGREGATE_SNAPSHOT.json` (`6f35dbb0...`; it holds the
  original result `bfccc683...` and report `21070825...` and the original stage records), its completion record
  `COMPLETED.json` (`f15e5eea...`), `PLAN.json` and `LOCAL_EXECUTION_ADDENDUM.md`; the companion's terminal review
  `cage/natural_growth_b_terminal_independent_review_20261108_v1/REPORT.md` (`a61a98b2...`) and its `AUDIT.json`; the
  companion's `cage/natural_growth_b_terminal_interpretation_20261108_v1/AGGREGATE_INTERPRETATION.md` (`bbd3dfcd...`);
  our `experiments/natural_growth_b_20261105/reviews/INDEPENDENT_POST_SCORE_AUDIT.md` (`d5ba17ee...`, last commit
  fb3ae686); Study B's `PROTOCOL.md` and amendments 1 and 2; the universality evaluation of 2 November
  (`records/NOV2_UNIVERSALITY_SIMILAR_PROBLEMS_RESULT.md` and its protocol); companion notes 0455, 0460 and 0470.
- **Construction study (95 constructed tasks):** our `experiments/construction_at_scale_20261105/PROGRESS.md`
  (`1e3eb8ed...`, unchanged since commit 18955f26), its frozen `PROTOCOL.md`, its analysis output
  `runs/analysis/ANALYSIS.json`, the code that writes its CPU fields (`cas/run_world.py`), and the companion closeout
  `cage/construction_scale_independent_closeout_20261107_v1/REPORT.md`.
- **Biology map:** all 91 pinned files (rehashed, bytes and SHA-256), the six result aggregates the JSON names
  (rehashed), the safe report of every one of the 23 rows (read), and our records
  `records/NOV5_BIO_GRAMMAR_TRANSFER_RESULT.md`, `records/OFFICIAL_SCORE_AND_SELECTION_STATUS.md`,
  `records/NOV2_FINAL_SUBMISSION_STATUS.md`, `paper/writeup/RESULTS_TO_SOURCE.md` and
  `records/SPARSE_COFACTOR_NATURAL_INDEPENDENT_AUDIT_20261108.md`.

Not done: no held evaluation was rerun, nothing was scored or rescored, and no program, search or model was run. No
file under a private folder, no `_LOCAL.json` file, no authorization or grant file and no answer file was opened. The
private case bundle named in 0589 was not opened; only the two safe files beside it were hashed.

**Disclosure.** One search in this check was broader than intended: a recursive search of Markdown files under the
companion's `cage/` folder for the phrase "four corrections" (and three variants) ran for about two minutes and was
stopped by this check. It printed no file name and no matching line. It was limited to `.md` files, so no JSON answer
file was read, but it may have opened Markdown files inside private folders while searching; nothing from them was
displayed or used. Every other read was of a named file.

**Labels used by the companion files, defined once.** "O+" is the CORA-only Kaggle entry (submission 57902131, public
score 0.83%). "H" is the neural-assisted Kaggle entry (submission 57867631, public 24.03%), whose neural attempt is
our re-implementation of NVARC's method. "G0" is the original program grammar alone. "TT2" is the complete language of
Boolean rules with at most two inputs. "R1" is the companion's first related-benchmark evaluation; "R4" its
structural-prior replication on the 595-target cohort. "R29" is the leave-one-out rule component inside O+. "CAST" is
CORA's typed program search component. "MBP" is the myelin basic protein marker gene.

## Verdict

- **Exposure file: every number is correct.** Counts, intervals, the p-value, Holm and decision reproduction
  statements, check counts, hashes and the construction compute figures match our audit, our construction log and
  the saved analysis. Four wording points and one superseded status remain (minor).
- **Status file: every number is correct.** Denominators (464 tasks and 624 query outputs; 120 tasks and 172 query
  outputs), every arm and benchmark count, the primary (+109, interval [7, 204], decision "obj beats static_obj"),
  the public ARC contrast (2 against 0, interval [0, 6], raw and Holm p 1, inconclusive), runtime, CPU, hashes and the
  official scores match. Five wording or status points remain (minor).
- **Map: 91 of 91 pins verify; 6 of 6 named result aggregates verify; every row's numbers match its reports except
  one sentence in the imaging row (the old tolerant result, major).** Seven minor points: the 656-target row is
  resolvable from the companion's own saved reports, one independent review is not pinned, measured costs are missing
  for 22 rows, and four rows need wording fixes.

**Totals: 0 blockers, 1 major, 16 minor, 2 style.** Only the major item puts a wrong number into the paper if copied.

## 1. Discrepancies and exact corrections, most severe first

### Major

**1. Map, row "Original object-guarded imaging transfer" (MD line 99; JSON `studies[14].limitations`).**
- It says: "The old tolerant condition has four corrections and five harms, matched by blind and shuffled controls."
- The row's own pinned report `cage/continuous_adapter_repairs_20261107_v1/bioimages_auxiliary/SOURCE_CLAIM_RECONCILIATION.md`
  (`7d992eae...`) says: "The old tolerant 4/5 versus 4/5 seed comparison refers to matching operator admission in
  calibration, not four successes among five independent biomedical trials. On held LIVECell the tolerant arm made one
  harmful edit, and four of five failure-blind and four of five shuffled arms made the same harmful edit". The
  companion's `cage/continuous_domain_integration_20261108_v1/BIOIMAGE_RELATIONAL_CORRECTION_RESULTS.md`
  (`1d642340...`) says the same. Our pinned record `records/NOV5_BIO_GRAMMAR_TRANSFER_RESULT.md` (`6bd15478...`)
  gives the tolerant arm's held edits: LIVECell 1 accepted edit (0 beneficial, 1 harmful), NuInsSeg 32 accepted
  (10 beneficial, 16 harmful), MoNuSAC none; no target passed the tolerant control gates.
- No source contains "four corrections and five harms". The sentence turns an admission count (4 of 5 seeds) into
  benefit and harm counts, which is the misreading the reconciliation report warns against.
- **Correction (MD and JSON):** "Strict mode made no edit on any held dataset. A calibration-informed tolerant rule
  admitted one operator (a low-threshold object addition) on LIVECell calibration, as did four of five failure-blind
  and four of five shuffled control seeds; this is an admission count, not four biological successes. On held
  LIVECell the tolerant arm made one harmful edit and no beneficial edit, and those control seeds made the same
  harmful edit; on held NuInsSeg it made 32 accepted edits, 10 beneficial and 16 harmful; on MoNuSAC it made none. No
  target passed the tolerant control gates."

### Minor

**2. Map, row "Separate 656-target cohort" (MD lines 39, 131 to 133 and 145; JSON `studies[22]` and
`pending_items[0]`): marked UNRESOLVED, but the companion's own safe reports identify the study.** Our
`paper/writeup/RESULTS_TO_SOURCE.md` already cites the result and the breakdown below (rows 711 and 23) and note 0494
(row 653). Candidate pins, each rehashed now:

| role | path (companion `cage/`) | SHA-256 |
|---|---|---|
| code freeze (binds the protocol below and the code) | `learned_support_large_target_20261106_v1/TARGET_CODE_FREEZE.json` | `29a6ff37de004d8ac23dedae032b73bde8d1a132d2db80449bccd29e9fe8b317` |
| protocol bound by that freeze | `learned_support_large_target_20261106_v1/PROTOCOL_DRAFT.md` | `88c56f5ba9941bbee8cb723c54053b6946f9a32329fa866251b9bf19478e4982` |
| saved-artifact audit protocol and freeze | `learned_support_large_target_postrun_audit_20261106_v1/PROTOCOL.md`; `AUDIT_FREEZE.json` | `a05e5c71e32e3e059388c09580ad93c73db60f8b1a2b829f092aae6fdf33a1e2`; `e7ac73c67068fb9695056cba45c185b20a056653fe2fd2844d0ba579a21dab6e` |
| result | `learned_support_large_target_postrun_audit_20261106_v1/POSTRUN_RESULT.md` (names aggregate `6b0855d9...`) | `07b940b76ecfc01e6226d656523f4be98ca4d0118ee52cfdd10120bfbec6bb3e` |
| post hoc breakdown by number of inputs | `target_readout_posthoc_arity_20261106_v2/FINDINGS.md`; its `PROTOCOL.md` | `a9a24f5f59f4c89104f70d83b5bb457b4d65b244d42fb56b1f87cca29fb8f1a8`; `cc5cfbe983518894218911faff1ed3ea24d76d58831305d05d85b0859dbe4695` |

What those reports say: 656 targets from 82 models in 68 lineages; the primary criterion was not met (neural guide
24/656 exact, tied by the logistic and fixed-guide controls; shuffled 3, random 21); by essential inputs the cohort has 222
one-input, 147 two-input, 92 three-input and 190 more-than-three-input rules, plus 5 with unknown essentiality, which
the map's row omits. The breakdown was chosen after the negative primary. **Correction:** replace UNRESOLVED with these
pins, add the 5 unknown-essentiality targets, and keep the row's ban on mixing it with the 595 cohort. Whether these
are the canonical pins is for the separately requested reproducibility addendum to confirm.

**3. Map, row "Authored operator-class induction" (MD lines 28 and 87 to 89; JSON `studies[11]`): the independent
review is not pinned.** The pinned result report (`b84a99b7...`) states: "Independent replay is required before
citation in a manuscript." That replay exists: `cage/biology_operator_v6_independent_review_20261104/INDEPENDENT_EXACT_REVIEW.md`
(`b777d13b36c4c21439bed4c3e714e8827c6d06a8f65105181c29f86e199525b2`), verdict "PASS with strict claim limits", with
`REPLAY.json` (`7fb7dd47bba0fd6e99e9a32495dfa2420a60f53e8204722d36953679d1ee62e9`); it recomputes all 4,896 case-arm
rows. **Correction:** add both pins and replace "REVIEW SCOPE SEPARATE" with "independent exact replay PASS with
strict claim limits".

**4. Map, all rows except the first: measured compute is missing.** `cost_scope` is null for 22 of 23 studies, and
the MD says only "Use each study's scoped resource receipt". The paper needs measured costs beside the ceilings.
**Correction:** add the measured figures in section 4 below, each taken from the row's own pinned report, keeping
ceilings separate.

**5. Map, row "Submitted components on grid-encoded published Boolean models" (MD line 91; JSON
`studies[12].limitations`): the majority comparison is reversed.** It says "majority adds no useful difference on the
answered subset". The pinned audit (`a0ac71af...`) says the comparison of O+ against the majority baseline on exactly
the outputs O+ answered is 0.00, interval [0, 0], so the declared usefulness label is not shown; across all 1,332
single-gene outputs the majority baseline is correct on 885 and O+ on 150. **Correction:** "On the outputs it
answered, O+ was no better than the majority-class baseline (difference 0.00, interval [0, 0]); across all 1,332
single-gene outputs the majority baseline was correct on 885 and O+ on 150."

**6. Map, row "Continuous bioimage follow-up" (MD line 117; JSON `studies[18].cohort_and_exposure`): not like for
like.** "totaling 129 rather than the original 886" sets calibration plus evaluation images against the original held
evaluation images. The source (`1d642340...`) says 51 calibration and 78 evaluation images, "not the original
886-image held evaluation". **Correction:** "One hash-fixed image per parent: 78 evaluation images rather than the
original 886 held evaluation images, plus 51 calibration images; eight arms."

**7. Map, row "Original object-guarded imaging transfer" (MD line 101; JSON `studies[14].cohort_and_exposure`):
exposure at the time.** "with within-project exposure" reads as a property of the original evaluation, but our record
says "This is a fresh, pre-registered evaluation", with the protocol frozen before any download. **Correction:** "Fresh
to the project at the original pre-registered evaluation (data downloaded after the protocol freeze); exposed within
the project for any later reuse, including the bounded follow-up and the disclosed search incident."

**8. Map, row "Informative observation selection within fixed TT2" (MD lines 51 to 53; JSON `studies[2]`): equal labels
are not equal compute.** The pinned review (`7debbc19...`) says: "Active versus uniform is equal in own oracle-response
count, not CPU; example selection requires additional computation." **Correction:** add that sentence to the row.

**9. Exposure file, line 11 (the sentence to place beside every Study B table): R1 date and the systems run.** As
written, "on November 2" can be read as covering the companion's R1 evaluation too. R1 ran on 5 November 2026 (notes
0455, 0460 and 0470), on a different frozen system, over the full cohorts. The 2 November universality evaluation ran
three systems: the O+ solver (notebook `f683136c...`), H's CORA component without its neural attempt (`0e09afd4...`),
and the plain CAST solver (`f2019b5d...`, a fallback that was never submitted). The cohorts are exactly Study B's
(ConceptARC 160 = 80 + 80, Mini-ARC 149 = 74 + 75, 1D-ARC 615 = 306 + 309; our audit, section 4). **Correction:** "Held out means held
from this study's development only. Every task had already been run and scored on 2 November 2026 in the project's
universality evaluation, by the O+ solver, by H's CORA component without its neural attempt and by the plain CAST
solver, and again on 5 November by the companion study's R1 evaluation of a different frozen system."

**10. Exposure file, line 15: the primary interval wording.** "reproduced within one unrecorded task ordering
position" can be read as an off-by-one. Our audit: the aggregate does not record which Mini-ARC task the static
search alone solved; over its 75 possible positions the interval is [6, 204], [6, 205], [7, 204] or [7, 205]; the
stored [7, 204] arises at 29 positions; the lower end is at least 6 at every position. **Correction:** "the original
primary interval reproduced up to the unrecorded position of one Mini-ARC task: the four possible intervals are
[6, 204], [6, 205], [7, 204] and [7, 205], the stored [7, 204] is among them, and the lower end is at least 6 in every
case, so the decision does not depend on it."

**11. Exposure file, line 15: Holm values.** **Correction:** add "All 13 Holm values reproduce exactly when Holm is
applied, as the frozen report applies it, to the six-decimal p-values; on unrounded p-values two differ in the sixth
decimal (library against matched static search 0.018038 against 0.018039; library wrong answers 0.231445 against
0.231444), and no decision moves."

**12. Exposure file, line 21: measured and charged compute are mixed.** Both numbers are right (section 3), but
"consumed 2.61 charged CPU hours" calls an accounting charge consumption, and 8.47 covers standing attempts only.
**Correction:** "Matched static search used 8.47 CPU hours of measured kernel CPU on the 95 motivating tasks; this
counts each search's standing attempt, and the CPU of the 16 first attempts that hit the 8 GB memory limit, before
their rerun alone at 20 GB, is extra. The three growth repeats together were charged 2.61 CPU hours under the protocol's complete-cost
rule, which counts cached gate results at their first computation and the shared diagnosis once per unit; their
measured process CPU was about 0.31 CPU hours, with the shared diagnosis measured separately (0.25 CPU hours over all
tasks of the three worlds). Only 2 of the 95 tasks gave the three repeats more charged CPU than the matched search.
Each matched search was allowed 150 reference CPU seconds, scaled to its kernel, or the largest single-repeat charged
growth cost if larger; no task exceeded 150."

**13. Exposure file, line 29, and status file, lines 39 and 54: the case-recovery status is superseded by 0589.**
Both describe the case work as in preparation. Note 0589 reports that the reviewed second version of the projector ran
once and succeeded; its safe files verify (`CASE_EVIDENCE_SAFE_SUMMARY.json` `caa7017eae7ddb5246a712c3edb7f296db587e4f868f5a8a0f3488ea73a12190`,
`EXTRACTION_RECEIPT_SAFE.json` `fed7d97015eee35fd7fed2fed9a01ab6fd9c972c87bcdf54b0ad8999419efed4`). **Correction:**
"A reviewed private projection (note 0589) identified the one task behind the 2 correct ARC outputs without a gold
read, scorer call, model inference or program replay. A complete failure-to-revision case is still not certified: it
lacks a failure-cause certificate, a pre-answer diagnosis timestamp, the second program's text and an independent
replay."

**14. Status file, line 7: "the historical NVARC Step B".** Our records (`records/NEURAL_CORA_SCORING_AUDIT_20261025.md`:
"Step B (`cora_level4_stepB_run.py`, 20 workers)") describe Step B as CORA's long-running Level 4 experiment in
`Reasoning_Project`, and the companion's own `cage/step_b_readonly_status_20261106_v1/REPORT.md` describes the same
process (its proposal phase at 492 of 497 units); no record we hold links it to NVARC. If copied, the phrase
misattributes a CORA experiment.
**Correction:** "This study is different from the separate long-running CORA Level 4 Step B experiment and from the
completed 3 November neural-to-program Test B."

**15. Status file, lines 15 to 17 and 21: the static comparators' compute.** "Extra-CPU original-language search" and
"The static competitors receive more computation in G0" state the allocation loosely. The protocol (section 6) gives
each static comparator a per-task CPU cap equal to the growth arm's whole cost (its frozen source-half development,
scaled, plus its held-half search, divided by the held tasks): "Growth pays for all its work." The saved stage records
show the comparators used about that whole cost (section 3). **Correction:** table label "Matched static search in G0
(per-task CPU allowance equal to the growth arm's whole cost)"; line 21: "The static competitors search G0 under a CPU
allowance equal to the growth arm's whole cost, source-half development included; they do not receive the identical
expanded operation bank."

**16. Status file, line 17: "Learned program library".** "Learned" suggests a trained model. The protocol's library
holds "operations promoted from the programs that the system found on the source half with extra budget".
**Correction:** "Promoted program library (operations promoted from programs found on the source half)".

**17. Status file, line 37: the public ARC check's controls.** "the ARC check has no such control" is true but
incomplete: the saved aggregate shows seven ARC arms (G0, the promoted library, reuse, construction and their three
matched static searches) and no donor-demonstration, shuffled-library or shuffled-registry arm. **Correction:** "The
ARC check ran seven arms (G0, the promoted library, reuse, construction and their three matched static searches); it
has no donor-demonstration, shuffled-library, shuffled-registry or shuffled-failure control."

### Style

**18. Map text defects.** Twelve em dashes in MD titles (six more, escaped, in JSON titles); merged words
("Separate656-target", "Sparse60-coordinate"; JSON notes "freeze2487788...", "audit:618 checks", "Do not replace
with595distribution165unary/156binary/90ternary/184fourormore.", "Source-onlypendingrecord,notanempiricalresultentry.");
double spaces after semicolons in every status cell; labels without definitions (TT2, R4, R29, O+, H, CAST, MBP,
V10, meaning the tenth constructor version, and "5P", which the decoder README defines as five times the image pixel
count). **Correction:** define each label at first use or use plain names, replace the dashes with commas or colons,
and restore the spaces before any sentence reaches the paper.

**19. Exposure file, line 5, names an AI assistant.** Harmless in an internal coordination record, but the author's
rule is that no such name appears in anything published; do not copy that line.

## 2. Claims confirmed

### 2.1 Exposure file

| claim | checked against | result |
|---|---|---|
| Held halves held from this study's development only | Study B protocol section 2; our audit section 4 | confirmed |
| Every task run and scored on 2 November by the submitted solver versions | universality cohorts equal Study B's source plus held halves; results committed 1a20b6ee, 2 Nov 07:54 UTC | confirmed (precision: item 9) |
| ... and by the companion's R1 evaluation | note 0470: R1 covered ConceptARC 160 tasks / 480 queries, Mini-ARC 149, 1D-ARC 615, ARC public 120 / 172 | confirmed (date: item 9) |
| Public ARC check keeps its prior-development and dry-run exposure | aggregate exposure field: used in earlier development and gates; touched by this study's first dry run (95 tasks' inputs, no solution opened) | confirmed |
| Our review: 33 passing checks; 14 p-values, 13 Holm values and 14 decisions reproduced | our audit sections 1 and 2 | confirmed (items 10 and 11) |
| Nine secondary intervals not reconstructable from the aggregate | our audit: all thirteen secondary intervals except the pooled library-against-G0 interval and its three per-benchmark versions, which reproduce exactly | confirmed |
| The separate 182-check terminal audit is custody only; not 215 trials | terminal review: 182/182, PASS_TERMINAL_METADATA_ONLY | confirmed |
| Our review's hash `d5ba17ee...` | rehashed | confirmed |
| Construction: 95 tasks, 64 against 38, 31 gains, 5 losses | `ANALYSIS.json` primary: both 33, growth only 31, matched search only 5, neither 26; 99 planned, 98 built, 3 sent elsewhere by the controller | confirmed |
| Bound verification agrees | PROGRESS 04:04Z, step 5: binding checked, frozen output agrees | confirmed |
| Static 8.47 CPU hours on motivating tasks; growth 2.61 charged, three repeats together | recomputed from `ANALYSIS.json` (section 3) | confirmed (wording: item 12) |
| The 857 digest mismatches belong to the separate lineage join | PROGRESS 04:20Z: all 93 output files match their manifests byte for byte | confirmed |
| 51 against 28 same-family reuse is descriptive; 17 sources shared | `ANALYSIS.json`: both 25, grown only 26, matched only 3; 17 excluded sources shared between worlds; one joint component | confirmed |
| Memory-handler deviation kept; memory exclusion post hoc | PROGRESS 04:04Z and 04:20Z (27 against 4 of 84 without the 11 affected searches) | confirmed |
| Construction log hash `1e3eb8ed...` | rehashed; working copy equals commit 18955f26 | confirmed |
| The Boolean loop ties strong fixed search; Study B changes capabilities; neither is the same-capability routing contrast; fixed and trained routers reported apart | paid-loop report `f64bc55e...`; Study B amendment 2 | confirmed |

### 2.2 Status file

| claim | checked against | result |
|---|---|---|
| Completed 7:42 p.m. Central, 7 November; A, B, C, pre-score validation and report exit 0 | `COMPLETED.json`: 2026-11-08 01:42:30 UTC (Central is UTC-6), every phase return code 0 | confirmed |
| 182/182 checks; no visible live workers | terminal review `REPORT.md` and `AUDIT.json` (182 of 182; no live process match) | confirmed |
| 464 tasks / 624 query outputs; a query is one test input | aggregate totals; protocol table (80/240, 75/75, 309/309) | confirmed |
| Reuse 227/624, construction 343/624, static 118/624; library 37/624 against 56/624 | aggregate totals (both static comparators 118, answered 147) | confirmed |
| Primary +109, interval [7, 204], "obj beats static_obj"; stored statistics, not recomputed | aggregate primary (tasks favouring reuse 155, static 36) | confirmed |
| The stored McNemar label is a sign test on per-task differences; "tasks only" means tasks favouring an arm; six-decimal zeros are rounded | protocol section 7; aggregate fields; our audit | confirmed |
| Per benchmark: 46, 9, 27 of 240; 11, 2, 3 of 75; 286, 216, 88 of 309 | aggregate by benchmark; the two static comparators give identical counts in every benchmark, so one column is right | confirmed |
| 57/315 against 30/315 (construction); 11/315 against 30/315 (reuse); not a new endpoint | arithmetic over ConceptARC and Mini-ARC (155 tasks) | confirmed |
| Primary gain concentrated in 1D-ARC | +128 in 1D-ARC, -18 ConceptARC, -1 Mini-ARC (our audit section 3) | confirmed |
| Public ARC: construction 2/172, all other arms 0/172; interval [0, 6]; raw and Holm p 1; inconclusive | aggregate public ARC totals and its secondary (one task favouring construction, sum 2) | confirmed; that the task has two queries comes from the private projection (0589), not the aggregate |
| Not an improvement over O+'s local 3/172 | `records/NOV2_FINAL_SUBMISSION_STATUS.md`: O+ 3/172 on the 120 locally and in its Kaggle CPU rehearsal | confirmed |
| Wall 31,371.14 s (8.71 h) within a 12-hour ceiling | `COMPLETED.json`; `LOCAL_EXECUTION_ADDENDUM.md` (12-hour global wall) | confirmed |
| 48,986.25 s outer CPU plus 67.35 s supervisor, about 13.63 CPU hours | `COMPLETED.json`; the terminal review's 13.607 h is the outer figure alone; both are right | confirmed |
| Hashes `bfccc683...`, `21070825...`, `6f35dbb0...`, `f15e5eea...`, `a61a98b2...` | rehashed or bound in the snapshot | confirmed |
| Official scores O+ 0.83%, H 24.03%, neural core credited to NVARC; Kaggle entries untouched | `records/OFFICIAL_SCORE_AND_SELECTION_STATUS.md`: H is our re-implementation of NVARC's method plus CORA, whose layer changed 0 of 172 public outputs | confirmed |
| Static competitors lack the expanded bank; not the decisive same-capability test | protocol section 6; amendment 2 | confirmed |

### 2.3 Map rows

| row | numbers in the map | checked against | result |
|---|---|---|---|
| Natural sparse reconstruction | 433 against 321 of 595; classical 433; held 2,070 / 1,400 / 1,388 of 2,380; 91 wrong, 71 without a program; 465 and 2,054 at 60 labels; 116.648 CPU s, 140.316 wall s | review `7510eff3...`; our audit `SPARSE_COFACTOR_NATURAL_INDEPENDENT_AUDIT_20261108.md` (PASS) | confirmed |
| Sparse host, authored validation | 17 units, 302 fixture checks, classical ties; 12 invented models, 144 records | `88e909cf...` | confirmed |
| Observation selection | 320 against 291 (+29); held 1,586 against 1,747 (-161); no exact higher-arity rule; shuffled control needs donor labels; 20 own labels | `7debbc19...` | confirmed (item 8) |
| Query completion | 2,200 against 2,153 (+47, 1.97 points); 15 combinations; exact 320 against 291; failed first attempt kept | `aa94a61a...` | confirmed |
| Cofactor policy repair | 148 to 254, 138 to 248, 94 to 188 (310 gains, 0 losses); fixed expressive 256 in each; 768 units | `fcbfc1d0...`; outcome review `d9d80f4d...` | confirmed |
| Sparse 60-coordinate engine | 256/256 at 60 labels in both embeddings; four-input 5/6 and 6/6; classical ties; 1,572 cases | `0af5107f...` | confirmed |
| Structural prior (R4) | 101 against 66 (35 gains, 0 losses); supplied wiring 222; wrong accepts 124 against 112; 33 readmitted models; 4 lineages hold 191 targets | `3843e9e7...`; `7e6e31a0...` | confirmed |
| Supervised ranking | 98 against 95; context controls 97; 59 outside-pool failures; 182 tasks, 25 models, 11 lineages | `a31f18cb...`; its protocol | confirmed |
| Prospective ranker transfer | 121 against 124, 125, 126 and 126; context 122; 176 outside pool; 356 targets, 46 models, 43 lineages | `a5db5f7e...` | confirmed |
| ARC-derived ordering | 177 against 168; permuted 182; static 194 | note 0551 `30c7aa62...`; aggregate `61a930a1...` | confirmed |
| Fixed paid-evidence loop | 219/256 exact, 1,003/1,024 held; baseline 38 exact; 37 wrong fits kept; router fixed; 688 audit checks | `f64bc55e...`; `8b8220d5...` | confirmed |
| Operator-class induction | 48/48 positive families; fixed XOR row-identical; random libraries with XOR tie; 83/96 routed and full | `b84a99b7...` | confirmed (item 3) |
| Submitted components on Boolean models | 150 of 1,332 single-gene outputs (all from R29; CAST none); supplied wiring 148 against 85 of 333; whole-network coverage 0; probes 0/42; 44 models, 440 and 333 tasks; local port | `a0ac71af...`; results `18730c08...` | confirmed (item 5) |
| Perturb-seq construction | 0 of 64 genes; all 256 demonstration labels similar; 45 programs; 448 slots; 715 / 243 / 255 | `8bc69b3a...`; `c9e8c14f...` | confirmed |
| Imaging transfer | strict mode no held edit; static MoNuSAC 33 of 40 better, 7 worse; 19, 19 and 40 parents; 886 images (288 + 429 + 169) | our record `6bd15478...`; `7d992eae...` | confirmed except the tolerant sentence (item 1) and exposure wording (item 7) |
| DLPFC marker rescue | 0.9320277026 against 0.9315545343; 58 corrections, 65 harms; two sections worse; 14,234 spots; one evaluation donor, two source donors | `aeb74a94...`; `78422a10...` | confirmed |
| Spatial follow-up | neighbor-only 0.9349974627, 36 against 12, all four sections better; combined 0.9336118801, one section worse; no matched neighbor-only shuffle; 85,404 predictions | `78422a10...`; `9146881b...` | confirmed |
| Perturb-seq follow-up | no admitted rule; directional F1 0 for every method; 958 training perturbations; 255 x 64 = 16,320 per arm; 20 arms | `8bc69b3a...`; `bf76c0cf...` | confirmed |
| Bioimage follow-up | memory error while decoding references; seal and replay markers reached; split and merge absent; eight arms | `1d642340...`; `6a6bce3d...` | confirmed (item 6) |
| Polygon decoder repair | two-pass decoder; producer and independent tests pass; base-array bound is not a whole-process memory bound | decoder README; `REVIEW.json` `d0f11d16...` (all checks true) | confirmed |
| Shared continuous interface | literal fixtures pass; no trained router, induced grammar or natural result | `86a8f800...`; `2d1c1351...` | confirmed |
| Teaching example | initial rule 1/3; constructed rule 3/3, tied by expressive and classical; 8 consistent completions | `5e89ebc2...`; `8888ebae...` | confirmed |
| 656-target row | 92 three-input and 190 more-than-three-input rules; never mixed with the 595 cohort | note 0201 `384a8cf0...`; companion `FINDINGS.md` `a9a24f5f...` | confirmed (item 2) |
| Map-wide | 23 studies and 91 pins; every study local CPU, none a Kaggle kernel result; official entries unchanged; no release approval | JSON counts; row reports | confirmed |

## 3. Actual against allocated compute

**Study B.** Allocation: each matched static search may use, per held task, the growth arm's frozen source-half cost
(scaled by the kernel speed factor) plus its held-half CPU, divided by the held tasks; amendment 2 estimates about 80,
19 and 33 CPU seconds per held task for ConceptARC, Mini-ARC and 1D-ARC at the object allowance, 20 to 60 times the
base search. Measured CPU seconds from the saved stage records:

| stage group | ConceptARC | Mini-ARC | 1D-ARC | held total | public ARC check |
|---|---:|---:|---:|---:|---:|
| matched static search, object allowance | 5,372.8 | 1,289.3 | 9,111.5 | 15,773.6 | 4,860.4 |
| matched static search, construction allowance | 5,498.4 | 1,338.3 | 9,180.9 | 16,017.6 | 4,915.4 |
| matched static search, library allowance | 714.1 | 320.8 | 1,091.3 | 2,126.2 | 549.7 |
| four grown-language arms together (library, shuffled library, reuse, shuffled registry) | 495.1 (with Mini-ARC) | | 595.8 | 1,090.9 | 544.8 library, 512.6 reuse |
| construction and donor-demonstration construction together | 482.1 | 190.7 | 362.6 | 1,035.4 | 805.4 (construction only) |
| G0 | 158.5 (with Mini-ARC) | | 156.7 | 315.2 | 362.9 |

The growth arms' frozen source-half costs are 18,135.3 workstation CPU seconds for object growth and 1,975.7 for the
library, before speed scaling; they enter the static allowances, not the held-half rows above. Read together, the
matched static searches used roughly the growth arms' whole cost, so "matched" is the accurate word. Against held-half
search alone, the object-allowance searches used about 14 times the CPU of the four grown-language arms together, and
the construction-allowance searches about 15 times that of the two construction arms together. Whole run: 48,986.25
outer CPU seconds (nested phases A 15,861.0, B 20,499.1 and C 12,551.2 overlap it and must not be added), 67.35
supervisor, 31,371.14 wall seconds, against a 12-hour global wall ceiling and a 30 CPU-hour phase ceiling.

**Construction study.** Allocation: each motivating matched search gets 150 reference CPU seconds scaled by its
kernel's factor (2.521, 2.406, 1.456), or growth's largest single-repeat charged cost if larger; no task was larger.
Measured: per-task means of 377.35, 352.5 and 211.77 seconds over 32, 36 and 27 tasks give 30,483 seconds (8.47 CPU
hours), standing attempts only (the rerun stage replaces a memory-stopped record and keeps the first attempt beside
it). Growth charged: 96 x 43.61 + 108 x 27.17 + 81 x 28.04 = 9,392 seconds (2.61 hours). Growth measured process CPU:
96 x 5.88 + 108 x 1.48 + 81 x 4.71 = 1,106 seconds (0.31 hours), plus the shared controller diagnosis (902 seconds over
all tasks of the three worlds). Whole study on Kaggle: 8.41, 8.88 and 3.35 CPU hours in the three kernels (cap 15
each).

## 4. Measured costs to add to the map (item 4)

Each figure is copied from the row's own pinned report; ceilings are given where the report gives them.

| row | measured CPU seconds | measured wall seconds | ceiling or note |
|---|---:|---:|---|
| Natural sparse reconstruction | 116.648187626 | 140.316082462 | 1,200 CPU / 3,600 wall (already in the map) |
| Sparse host, authored validation | 3.045362 (both fixture attempts 6.069959) | 3.278558578 (both 6.575096459) | 60 CPU / 120 wall / 256 MiB |
| Observation selection | 400.536959 | 568.096108667 | outer process family; equal own labels, unequal CPU |
| Query completion | 296.569265 failed attempt + 19.839388 recovery = 316.408653 (329.157131 with monitors) | 737.011812 + 45.111814 = 782.123626 | recovery 120 CPU / 1,200 wall / 2 GiB |
| Cofactor policy repair | 104.980409 | 115.807641 | 300 CPU / 540 wall / 2 GiB |
| Sparse 60-coordinate engine | 27.322110 | 27.430326245 | 60 CPU / 120 wall / 256 MiB |
| Structural prior (R4) | 806.631663 | 823.387913 | includes bookkeeping and prelaunch idle wall |
| Supervised ranking | 323.73 | 329.09 | one CPU, no GPU |
| Prospective ranker transfer | 370.29 (plus 25.93 for the full-source fit) | 441.62 | |
| ARC-derived ordering | 8.914950 for the final score attempt | 10.517026 | note 0551 says the original attempt and the failed 50-minute recovery are recorded separately; add them from those receipts |
| Fixed paid-evidence loop | 5.263553 (watchdog 0.088327 separate) | 5.358481310 | 60 CPU / 120 wall / 256 MiB |
| Operator-class induction | 88.28 seconds for the prediction pass; the report does not say CPU or wall | | 120,000 work-unit cap per task; peak memory 70,980 KB |
| Submitted components on Boolean models | 2,426 child CPU before scoring; scoring extra | 56 min 16 s launch to score | no GPU |
| Spatial follow-up | 2.960167134 | 8.265428225 | includes a declared 5 s startup debit |
| Perturb-seq follow-up | 2.024290522 | 7.311697196 | includes a declared 5 s startup debit |
| Bioimage follow-up (failed) | 140.643107349 | 151.141204925 | exit 1 inside 300 CPU / 600 wall |
| Polygon decoder repair | 0.412356 (independent review's final cold test run; the producer's 25-test run used 0.477146) | 0.421429 (producer 0.482580) | source only; no natural run |
| Shared continuous interface | 0.76 (18 literal tests) | 0.77 | |
| 656-target study (item 2) | 392.065543 child + 42.388895 supervisor = 434.454438 | 480.622864 | |

The Perturb-seq construction, the imaging transfer, the DLPFC rescue and the teaching example keep their costs in
their own records, which this check did not open for cost.

## 5. Notes 0586 to 0589: points that touch the same numbers

- Note 0586's figures for the 595-target study all match (433, 321, 2,070, 1,400, 1,388, 112, 91, 71, the hashes and
  the costs). Note 0586 and the ARC map's correction line say "8.47 CPU hours versus 2.61" without "charged"; keep the
  word (item 12).
- Note 0587 retracts 0586's no-gold sentence. The map's structure review places the incident with the separate ARC
  worker. This check verified pins and claims, not which files a worker read.
- Note 0589's two safe case files verify (item 13).
- Note 0588 asks for the canonical 656-target record; item 2 gives the candidates from the companion's own tree.

## 6. How to repeat this check

Rehash the four files above and the 91 pins listed in the JSON's `source_and_safe_report_pins` (`path`, `sha256` and
`bytes` must all match). Compare section 2's numbers with `FINAL_AGGREGATE_SNAPSHOT.json` fields
`final_aggregate.totals`, `totals_by_benchmark`, `primary`, `secondary` and `arc_agi_2`; with `ANALYSIS.json` fields
`primary`, `secondary` and `descriptive.cpu_accounting`; and with each row's named report. No held answer, prediction
row or scorer is needed.
