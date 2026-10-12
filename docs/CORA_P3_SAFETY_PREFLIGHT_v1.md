# P3 synthetic safety preflight v1: preregistration (2026-10-12)

Written and committed BEFORE any P3 code exists, under the user's P3 safety
directive of 2026-10-12.

| directive authorizes | directive does not authorize |
|---|---|
| this preregistration | the 60-task recheck |
| one versioned P3 implementation | pilot v2 or v3 |
| one frozen synthetic preflight, run once | ARC-1000 |
| a regression check on the 6 native development successes, only if S1 and S2 pass | protected evaluation |
| the kf892487f1049 mechanistic check, only if that also passes | any change to frozen evidence |

P3 is a REPRESENTATION CORRECTION, never semantic invention.

## 1. Mechanism, exactly

**Where it acts.** Inside the native `inducer._induce_candidate`, after the
coherent views have been collected in the fixed trial order and before the
cap `MAX_SEG_VARIANTS_TRIED` is applied.

**What it does.** P3 computes an INDUCTION-level signature for each coherent
view, from the training pairs passed to that call:
- per grid, the background and the ordered typed objects (id, class,
  colour, cell colours, bounding box);
- the engine's correspondence alternatives (`correspondence.match_pair`,
  first `MAX_ALTS_PER_PAIR`);
- the input feature tables (`features.compute_feature_table`).

It keeps the earliest view of each signature class, in trial order, and
then applies the unchanged cap.

**What it leaves alone.**
- When no view is coherent, the fallback is used, with no deduplication.
- The strict cap and the create-relaxed handling (flag off) are unchanged.
- Nothing else changes.

**What it must not do:**
- read any pair other than the call's own training pairs;
- use a parent fold's program;
- name a view;
- reorder views;
- admit an incoherent view;
- change the leave-one-out, budgets, proposer, grammar or evaluator.

Because `_induce_candidate` is also the fold induction inside `loo_validate`,
every inner fold deduplicates from its own pairs only.

**Known limits, recorded in advance** (audit `outputs/p3/audit_equivalence.json`,
c968491):
- INDUCTION-equal views can segment an unseen input differently: 61 of 769
  development pairs, 9 of 231 synthetic pairs. P3 is therefore NOT
  semantics-preserving.
- Natively, the earlier duplicate already wins ties, so P3 keeps the selected
  program among duplicates. The exceptions go through timing: the cheap-first
  probe and the deadline.
- P3's substantive effect is admitting views that the cap used to cut.

## 2. Implementation (after this file is committed)

- **Package.** `cora_p3/`, outside every pinned tree. It contains a
  generated copy of `_induce_candidate` with marked `# P3` lines
  (`scripts/build_p3.py`, `--check` equality against the live engine source),
  installed by a context manager that restores the engine on exit.
- **Mutation and unit tests,** in `tests/test_p3.py`:
  1. the build check;
  2. restoration of the engine;
  3. no duplicates means a candidate list identical to native;
  4. trial order is preserved, no incoherent view is ever added, and the
     cap is unchanged;
  5. (family G) the signature classes of a fold do not change when the
     fold's held-out pair, input or output, is mutated or removed. The
     helper sees only the fold's pairs.
- **Freeze.** A manifest `outputs/p3/p3_manifest.json` records the sha256 of
  the implementation, the tests, this file, the corpus and the runner, and
  the run refuses if any of them differ.

## 3. Corpus

- **Negative controls.** The 24 synthetic tasks of
  `scripts/loo_v1_probe_negative.py` (seeds as committed in 1f03a1c).
- **Adversarial corpus.** `outputs/p3/adversarial_corpus.json`, built by
  `scripts/p3_adversarial_corpus.py` (2f5389d). Its families A to F and the
  selection rules are in that script's docstring; `corpus_sha256` and the
  selected tasks are recorded in section 7 below. Fixtures were chosen only
  by static segmentation properties and by BASE and PROMOTE behaviour.
- Each task has 3 training and 2 held-out demonstrations. There is no ARC
  data.

## 4. Arms and records

Arms:
- BASE: the native engine.
- BASE_REPEAT: the same, run again, to measure native timing noise.
- P3.

Every arm uses `inducer.induce_program` with `budget_s = 20`, the same
flags, and a pool of 4 workers with tasks interleaved.

Per run, the preflight records:
- the outcome on the two held-out demonstrations: CORRECT, FALSE_ACCEPT or
  REJECT;
- the program sha256 (canonical program dict);
- the program's view;
- the failure stage;
- the engine's own leave-one-out report (folds, passed);
- wall and process-CPU seconds;
- whether the budget was exhausted;
- P3 deduplication events.

Audit only: for each BASE-accepted program, the predictions on held-out
inputs when it is re-tagged with each INDUCTION-equivalent view.

**Exposure.** Fixed statically from the census code on the training subsets
the engine sees (the full set and each 2-pair fold). A task is EXPOSED if
deduplication changes the searched views in any of those subsets, and
UNEXPOSED otherwise.

## 5. Gates and failure policy

- **UNSTABLE.** A task where BASE and BASE_REPEAT give different outcomes.
  The reference outcome for that task is the better of its two BASE
  outcomes, which is conservative against P3.
- **S1 (safety, every task).** Zero new false acceptances: P3 is
  FALSE_ACCEPT where the reference is not. Zero regressions: the reference
  is CORRECT and P3 is not.
- **S2 (exposure integrity, UNEXPOSED tasks).** P3's program sha256,
  acceptance and outcome equal BASE's, unless the task is UNSTABLE, in which
  case it is reported and not counted as a violation.
- **Any S1 or S2 violation** rejects P3. Stop, record the negative result, and
  do not tune the mechanism.
- **If S1 and S2 pass**, the label is P3_SYNTHETIC_PREFLIGHT_PASS (never
  REAL_ARC_CAPABILITY_GROWTH). The two development diagnostics follow:
  1. **The 6 native development successes**: BASE against P3 on their full
     training data, through the isolation hook. Each must keep its
     acceptance and program sha256. Representation changes are reported.
     Any regression stops the block.
  2. **The kf892487f1049 mechanistic check**: per outer fold, the views
     searched, the candidate programs, recovery of G, the inner and the outer
     adaptive leave-one-out, and the first failure stage. If fold f1 still
     selects window_fill, that is recorded as a separate PROPOSAL-SELECTION
     blocker; the proposer is not changed.

## 6. Reporting

The preflight reports:
- newly correct predictions;
- newly wrong accepted predictions;
- correct to wrong;
- correct to rejected;
- all rejected cases;
- program-identity changes;
- leave-one-out outcomes;
- CPU and wall time;
- resource exhaustion.

Five claims are reported separately, never merged:
1. representation availability improved;
2. program recovery improved;
3. independent leave-one-out stability improved;
4. unseen correctness improved;
5. automatically constructed semantic capability required.

## 7. Frozen corpus identity

- **File.** `outputs/p3/adversarial_corpus.json`, file sha256 `226dc3ba194ca048ecca4c8ff5f4c0f9b695f8361713dbf6543f312daef4b59f`.
  Its `corpus_sha256` (task ids and grids) is `f584c5e1e98e48371b1f9419b3d8abbad959ea342460c9cbfa17dfa44b26a917`.
- **Selected: 17 tasks.**

  | family | tasks |
  |---|---|
  | A | translate_down_503, translate_down_504 |
  | B | recolor_by_size_501, bbox_fill_L_500, translate_down_505 |
  | C | translate_down_500, translate_down_501, translate_down_502 |
  | D | recolor_by_size_500, recolor_by_size_505, bbox_fill_L_503 |
  | F | multicolor_majority_501, multicolor_majority_502, multicolor_majority_503 |
  | E | halo_500, halo_501, halo_502 |

- **Recorded as found.** The quota of 3 per family, applied in candidate order,
  left out some diag_touch_size and layer_keep_largest candidates that met C or
  D. The rule is not changed after the fact.
- **Preflight corpus.** These 17 tasks plus the 24 negative-control tasks: 41
  tasks, 3 arms each.

## 8. Clarification before any run (2026-10-12)

**Exposure, as frozen in the corpus code.** EXPOSED means deduplication
ADMITS a view the native cap had cut, in some training subset the engine
sees. That is the census field `dedup_admits`, and it is what
`scripts/p3_adversarial_corpus.py` uses.

**Drop-only tasks are UNEXPOSED.** A task where P3 only drops a duplicate and
admits nothing is UNEXPOSED. S2 therefore also tests the claim that dropping
duplicates is neutral to selection: natively, the earlier duplicate wins
ties. A difference there counts as a violation unless BASE and BASE_REPEAT
disagree on that task.
