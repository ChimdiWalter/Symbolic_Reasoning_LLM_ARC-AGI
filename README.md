# CORA ARC-2026 workspace: diagnosing reasoning failures and constructing verifiable executable rules

**Status, 20 October 2026.** This is the delivery workspace for CORA's ARC Prize 2026 (ARC-AGI-2) work and for
the ARC Prize Research Summit (MIT, 23 October 2026). Every number below comes from a retained artifact, listed in
`records/`. Results from different configurations are reported separately and never pooled.

## What this is

- **ARC** (the Abstraction and Reasoning Corpus; here ARC-AGI-2). Each task shows 2–4 demonstration pairs of
  coloured grids and asks for the output grid of a new test input. Two attempts are allowed per test input, and only
  an exact match counts.
- **CORA** is this project's reasoner. It:
  1. segments grids into objects;
  2. explains a task as an executable program in a typed language over those objects;
  3. checks the program on every demonstration and in leave-one-out folds;
  4. records why an explanation fails.
- **The research question:** how can a machine learn the representation and rules of new data, learn from failure,
  and know what to reconsider when its explanation is not enough? In CORA's terms, that question has four parts:
  - *representation*: which objects and views;
  - *executable hypothesis*: which program;
  - *failure diagnosis*: why the program fails on the visible evidence;
  - *revision*: what to change.

## Architecture and status

```
ARC demonstrations + test input (no answers)
   |
   v
objects in 7 native views; features, relations, correspondences ........ implemented
   |
   v
proposals over whole rules: symbolic C+H order (G1-CH) ................. implemented, tested
                            generator completed over compiled constructs  implemented, unit-tested (ncv2-g2)
                            learned joint proposer over Qwen states .... proposed (design only)
native program classes (symmetry, pixel rules, counting, panels,
                        generative) as typed program forms .............. implemented, parity-tested (ncv2-g2)
   |
   v
typed relational program (ncv2-g1: guards, bindings, holes, macros) .... implemented, parity-tested
   |
   v
sound prunes + the unchanged native CORA interpreter ................... implemented, tested
   |
   v
fit on every demonstration; diagnosis labels (no fit / ambiguous) ...... implemented
failure-guided revision (choose an edit, execute it, re-check) ......... specified, NOT implemented
   |
   v
two attempts -> blind evaluator, the only reader of answers ............ implemented
```

| status | components |
|---|---|
| **implemented and tested** | native CORA v23 and its failure funnel; CORA-FHR (construction, reversible bridge, folds); the reasoning v2 version space; Neural-CORA v1 (typed language, generator, learned guide, frozen pilot); Neural-CORA v2: the ncv2-g1 AST, its compiler to native (71 programs; 14,200 real-grid executions, 0 mismatches), macros, sound constraints, pairing-aware search, the locked G2 runner; **ncv2-g2** (after G2): native reduction and generative program classes as typed forms (parity with all 6 saved native certificates), an object decompiler, and a candidate generator completed over compiled constructs (82 unit tests; on DEV synthetic families 10/10 correct within two attempts vs ncv2-g1's 1/10, engineering only) |
| **proposed (designed, not built or trained)** | Qwen interface A (joint proposals of references, parameters and program classes beyond the symbolic candidates) and interface B (Qwen grids as untrusted evidence turned into CORA sketches, with causal ablations); the failure-guided revision controller; library learning; the remaining native exposure (grow, matched templates, framed / overlay classes) |
| **frozen, not run** | the ncv2-g2 synthetic coverage study on held-out families (`records/NEURAL_CORA_V2G2_SYNTHETIC_PROTOCOL_20261020.md`) |
| **failed or NO-GO under frozen rules** | the G1 learned guide (198 vs 358 of 395); the G2 language-ceiling check (ncv2-g1 1 of 60, the same as v1); CORA-FHR on real tasks (+0); guarded construction (0 of 58); reasoning v2 Phase 2a (0 certified); the NVARC + CORA hybrid (+0, −1); official Kaggle scores of native CORA and CORA-FHR (0.00) |
| **not shown** | that failure information beats an equally equipped failure-blind control; autonomous invention of new semantics (ncv2-g1 surfaces existing native operations, and its macros are researcher-written); transfer to biology |

**Two cautions:**
- The Qwen3-4B checkpoint behind the neural features is NVARC's Apache-2.0 checkpoint. It was trained on public
  ARC-AGI-2 data, so any Qwen-derived result on public tasks is contaminated. The licence makes its use legal, not
  clean.
- `outputs/` holds run artifacts locally and is not in this repository. The `records/` files summarize them, with
  hashes.

## Where things stand

| question | result | configuration and data | evidence |
|---|---|---|---|
| Where does native CORA fail on real tasks? | **Memorization.** The object branch certifies 6 correct with 0 wrong. 26 tasks have only demonstration-fitting programs that are all wrong (27 without the frozen library). A correct candidate exists on 8 tasks. With leave-one-out switched off, the first-ranked outputs give 8 correct and 25 wrong | native v23 object branch, frozen library and learned verbs; 60 ARC-AGI-2 **training** development tasks | `records/CORA_FAILURE_FUNNEL_20261014.md` |
| The whole native harness on the same tasks | 12 of 60 exact (two attempts). 29 tasks are claimed, and 18 of those claims are wrong | native v23 unified harness | `records/CORA_SUMMIT_POSTER_EVIDENCE_20261012.md` section 15 (evaluator output pinned by sha256) |
| Can CORA build a missing executable rule? | **Yes, once, on synthetic data.** On dev_D3_04 it constructs the single-step `ring(8)[part_minority]`, installs it reversibly, rebuilds it in 3 of 3 leave-one-out folds, and predicts the held-out test correctly. Removing it removes the gain. The task's planted second step is vacuous on its shapes | CORA-FHR, G-grow grammar; synthetic development corpus | `records/CORA_FHR_DEV_RESULTS_20261014.md`, `records/CORA_FHR_DEGENERACY_AUDIT_20261014.md` |
| Does the failure record cause the gain? | **Not shown.** Failure-blind controls, including the information-matched C′, reproduce every synthetic certificate. 3 extension certificates are correct; 2 of them are already reachable controls, and none is wrong. The mixed-coverage pilot **failed** its frozen stop rule. On the size-only tasks the failure record changed which operator was proposed (3 tasks vs 0 for the blind controls), but native rejected the operator every time | synthetic development | `records/CORA_FHR_MIX_DESIGN_20261014.md` |
| Does CORA-FHR help on real tasks? | **No.** Authentic-failure FHR added 0 extension certificates and failure-blind C′ added 0. Frozen native got 6 correct; matched extra search got 7. There were no wrong certificates and no lost answers | 60 training development tasks | `records/KAGGLE_CORA_FHR_V1_LOG_20261015.md` section 4 |
| Why construction rarely fires (root cause) | Of 62 eligible rehearsal tasks: 20 had no memorized-growth evidence, 39 had evidence but no operator, 2 hit a cap, 1 proposal failed its folds. Of the 25 real cases with evidence: 18 inexpressible in the grammar, 5 unsupported, 2 grouping conflicts | rehearsal and 60 training tasks | `records/CORA_REVISION_ROOT_CAUSE_20261018.md` |
| A constructed rule on a real task | **One ARC-AGI-2 training task solved** (ka95aa62f67d9): CORA built a guarded rule (colour-1 objects ray north-west, others south-east), rebuilt it in 3 of 3 folds and answered correctly; frozen native and extra search fail it. Selected by the autopsy; a failure-blind constructor found the same rule; not part of the Kaggle entry | 1 training task | `records/CORA_FHR_GUARD_PROBE_PROTOCOL_20261018.md`, demo `replay_real.py` |
| Guard pilot (frozen stop rule) | Failure record 2 correct vs failure-blind 1 correct + 1 tie abstention; 0 wrong, 0 lost. One discordant pair is **not** a causal result | 2 real + 8 fresh synthetic | same record |
| Does guarded construction generalize? | **No: 0 of 58** independently selected training tasks were solved by any construction arm (authentic, failure-blind, shuffled, contrast); 0 wrong, 0 lost; frozen native solved 1. No discordant pairs, so the version was stopped | 58 exposed training tasks | `records/CORA_FHR_GUARD_GENERALIZATION_PROTOCOL_20261018.md` |
| Why 0 of 58 (forensic, uses answers) | **50 of 58** cannot be explained by a single uniformly applied G-grow expression in any of 7 segmentation views. Of the other 8, 5 need colour behaviour no single expression gives, and 3 pass. Guarded, deeper or re-represented programs were not tested. This is an expressivity **hypothesis**, not proof of new semantics | 58 pool tasks | `records/CORA_FHR_ORACLE_CEILING_20261019.md` |
| Reasoning v2: keep every consistent hypothesis, diagnose why it is not enough | **Correct but uncertified.** v2 treats a hypothesis as (segmentation, geometry, colour policy), keeps the whole version space, abstains on disagreement and reruns the search in every fold. On 00dbd492 its prediction is correct where frozen native and matched search fail. It is uncertified because the test needs a size-to-colour entry that one demonstration shows; this is insufficient evidence, not ambiguity or a defect. On the 58 pool tasks: 0 certified, 3 correct and 1 wrong exploratory predictions | exposed training tasks, in-sample | `records/CORA_REASONING_V2_FOLD_FRAGILITY_00dbd492_20261019.md`, `records/CORA_REASONING_V2_GAP_AUDIT_20261019.md` |
| A fresh real-task cohort for v2 | **Checked.** 44 of 100 candidates chosen by a declared rule are outside every protected split (one metadata-only eligibility check); the first 40 form the Phase 2a cohort | 1,000 training tasks | `records/CORA_REASONING_V2_COHORT_AUDIT_20261019.md` |
| Reasoning v2 on that fresh cohort (Phase 2a, frozen rule) | **NO-GO.** v2 certified 0 (exploratory 2 correct, 0 wrong); frozen native and matched search each certified 5 correct and **1 wrong**. 33 of 40 tasks had no consistent hypothesis in the language (GEOMETRY_GAP). The bottleneck is coverage | 40 eligible training tasks | `records/CORA_REASONING_V2_PHASE2A_EXECUTION_20261019.md` |
| Neural-CORA v1: does a learned guide improve CORA's search? (frozen pilot, G1) | **NO-GO.** On 395 held-out synthetic compositions (pass@2): hand-designed search C+H 358; hand-feature guide 235; Qwen3-4B-feature guide 198; plain search 104; shuffled labels 51; untrained 30. The guide learned, but not beyond hand features or strong symbolic search. Its heads scored components independently and paired selectors with actions poorly | CORA's own generator; frozen protocol 081c1d3 | `records/NEURAL_CORA_V1_PILOT_REPORT.md`, `records/NEURAL_CORA_V2_G1_FAILURE_ANALYSIS_20261020.md` |
| How much of real ARC can the v1 typed language express? | **1 of 60** exposed development tasks has a demonstration-fitting program under its best search order | 60 training tasks (exposed) | `records/NEURAL_CORA_V1_EXPRESSIVITY_AND_FAILURE_ATLAS.md` |
| Neural-CORA v2: a typed relational program language over native CORA (ncv2-g1) | **Built and parity-tested.** S-expression / JSON programs with relational guards, object references and binding, copies, parts, multicolour paint, composite and staged programs, compiled one-to-one onto the unchanged native interpreter. 71 programs match hand-written native programs; 14,200 executions on real grids give 0 mismatches. Not exposed yet: grow, synthesized copies, matched templates, six native program classes | hand-built grids and 200 dev60 demonstration inputs (no answers) | `records/NEURAL_CORA_G2_NATIVE_COVERAGE_INVENTORY.md`, `docs/NEURAL_CORA_V2_RELATIONAL_AST_AND_LOOP.md` |
| G2: does ncv2-g1 fit and answer more real tasks than the v1 language? (frozen protocol 3677d0f, one authorized run) | **FINAL: NO-GO (NO_GO_STOP).** Under its symbolic search, ncv2-g1 fits 1 of 60 and answers 1 of 60: the same task as the v1 language, with 0 gains and 0 losses. Native CORA fits 35. Of 20 checked no-fit tasks, 16 have no single-rule program in the search's candidate space, and 4 are inconclusive. Of native's 6 certified answers, 4 use program classes ncv2-g1 does not expose (reduction, generative), and 1 is expressible in ncv2-g1 but outside the search's candidates. No neural training follows | 60 exposed dev60 training tasks; CPU only, 0.67 CPU-hours | `records/NEURAL_CORA_V2_G2_REPORT.md` |
| After G2: can CORA's new search generate what native CORA already executes? (ncv2-g2, capability recovery) | **Engineering result, not a score.** ncv2-g2 adds native reduction and generative program classes, and completes the candidate generator over constructs ncv2-g1 already compiled. All 6 saved native certificates round-trip exactly. On 10 DEV synthetic families ncv2-g2 answers 10, ncv2-g1 1 (budget 3000). The frozen held-out study has not run | DEV synthetic families written by the same author; no real ARC | `records/NEURAL_CORA_V2G2_CAPABILITY_RECOVERY_REPORT_20261020.md` |
| Official Kaggle, ARC-AGI-2 public leaderboard | native CORA v23: **0.00** (57144804). NEURAL_TTT_BASELINE: **27.64** (57160429). The latter is a faithful reproduction of the public NVARC Qwen3-4B pipeline, **not CORA**; it equals NVARC's own 2025 public score | Kaggle code competition | `records/KAGGLE_NEURAL_V1_LOG_20261013.md`, `records/KAGGLE_NEURAL_V1_ORIGINALITY_AUDIT_20261014.md` |
| The CORA-FHR research entry on Kaggle | **CORA_FHR_V1 (57354496): official public score 0.00.** Native v23 runs unchanged, then FHR runs on growth-shaped tasks that native did not certify. In the committed run FHR ran on 62 of 240 stand-in tasks and committed 0, and the official score of 0.00 confirms this. The entry documents a runnable implementation, not unseen accuracy | `kaggle/cora_fhr_v1/` | `records/KAGGLE_CORA_FHR_V1_LOG_20261015.md` |
| NVARC plus CORA hybrid | **NO-GO.** On the stand-in tasks CORA solves nothing NVARC misses. Filling NVARC's empty second attempts with CORA adds 0 and loses 1, because a 1×1 `[[0]]` answer was correct | 240 stand-in training tasks (contaminated) | `records/NVARC_CORA_COMPLEMENTARITY_AUDIT_20261014.md` |
| Biological transfer | **Untested.** A domain-neutral contract and a proposed test exist | — | `docs/CORA_REPAIR_VERIFY_CONTRACT_v1.md`, `docs/BIO_TRANSFER_PROPOSAL_20261013.md` |

**The claim this supports.** CORA can locate its own failure on real tasks, and on synthetic tasks it can construct,
install, verify and remove a missing executable operation. Diagnosis-driven construction has not yet solved a real
ARC task, and the failure record has not yet beaten an equally equipped failure-blind control. That gap is the open
research problem.

## Map

| path | contents |
|---|---|
| `cora_funnel/` | the instrumented failure funnel (categories, CPU-clock budgets, evaluator) |
| `cora_fhr/` | CORA-FHR (failure-conditioned hypothesis revision): G-grow grammar (`ggrow.py`), construction, reversible bridge, measurement arms, evaluator, audits |
| `cora_reach/` | the earlier constructor and its instance extraction (the failure evidence) |
| `cora_revision_v2/` | reasoning v2: the version space over (segmentation, geometry, colour policy), diagnoses, the Phase 2a runner and evaluator |
| `cora_neural_v1/` | Neural-CORA v1: the typed language ncv1-g0, its generator, the learned proposal guide, the frozen pilot and its evaluator |
| `cora_neural_v2/` | Neural-CORA v2: the ncv2-g1 typed relational AST (`rast.py`), the compiler to native (`bridge.py`), typed hygienic macros, the native inventory, sound constraints, and the pairing-aware search with an exhaustive single-rule diagnostic |
| `cora_neural_v2g2/` | ncv2-g2: native program classes as typed forms (`classes.py`), the object decompiler, the grammar facade, the completed candidate generator and agenda (`search.py`), and the synthetic families (DEV / HELDOUT) |
| `tools/stepb_eligibility/` | the metadata-only cohort eligibility checker (reads only the split manifest's task ids and splits) |
| `kaggle/` | Kaggle notebooks and builders: `native_v1/`, `neural_v1/` (NVARC reproduction), `cora_fhr_v1/` (research entry), `ops/` (gated pipelines), `neural_cora_v1/` (scaffold only) |
| `records/` | protocols, results, audits, logs and the stage ledger (`STAGE_LEDGER.json`) |
| `docs/summit_20261023_reframe/` | summit poster and explainer review sets (Org sources, PDFs, figures with provenance) |
| `docs/summit_poster/` | summit poster, abstract and explainer (LaTeX sources, PDFs, `figures/` with provenance) |
| `docs/summit_demo_20261023/` | the offline 90-second demo, a hash-checked replay of the recorded witness, and the visual replay of ka95aa62f67d9 |
| `tests/` | e.g. `pytest tests/test_fhr.py`; Neural-CORA v2: `tests/test_neural_cora_v2_{ast,search,parity,forensic}.py` |

## Reproducing

- Explainer, part 5: `docs/summit_poster/explainer.pdf`.
- Demo: `sh docs/summit_demo_20261023/run_demo.sh` (needs numpy).
- Figures: `python scripts/summit_figures.py`, which writes `docs/summit_poster/figures/PROVENANCE.json`.
- Neural-CORA v1 pilot: `sh scripts/reproduce_neural_cora_v1_pilot.sh`.
- Neural-CORA v2 parity: `pytest tests/test_neural_cora_v2_ast.py tests/test_neural_cora_v2_parity.py`; real-grid
  parity: `python scripts/neural_cora_v2_parity_bench.py`.
- Neural-CORA v2 G2: `python scripts/neural_cora_v2_g2.py {freeze,selftest,solve,diag,score}`. The solver stages
  refuse to run unless the frozen protocol and manifest are committed unchanged and `--authorized` is given.
- ncv2-g2: `pytest tests/test_neural_cora_v2g2.py`; the three-space coverage matrix:
  `python scripts/neural_cora_v2g2_coverage_matrix.py`; the synthetic study (frozen, needs authorization):
  `python scripts/neural_cora_v2g2_synthetic_eval.py {selftest,solve,score}`.
- The sealed 80-task prospective final, the frozen 120-task pilot and every protected split stay unopened.

## Authorship and assistance

The research, design decisions, claims and authorship are Chimdi Walter Ndubuisi's. AI coding assistance was
used for parts of the implementation and documentation.
