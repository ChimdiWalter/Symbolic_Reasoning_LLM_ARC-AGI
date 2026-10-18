# CORA ARC-2026 workspace: diagnosing reasoning failures and constructing verifiable executable rules

**Status, 18 October 2026 (updated 17:45Z).** This is the delivery workspace for CORA's ARC Prize 2026 (ARC-AGI-2) work and for
the ARC Prize Research Summit (MIT, 23 October 2026). Every number below comes from a retained artifact, listed in
`records/`. Results from different configurations are reported separately and never pooled.

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
| Official Kaggle, ARC-AGI-2 public leaderboard | native CORA v23: **0.00** (57144804). NEURAL_TTT_BASELINE: **27.64** (57160429). The latter is a faithful reproduction of the public NVARC Qwen3-4B pipeline, **not CORA**; it equals NVARC's own 2025 public score | Kaggle code competition | `records/KAGGLE_NEURAL_V1_LOG_20261013.md`, `records/KAGGLE_NEURAL_V1_ORIGINALITY_AUDIT_20261014.md` |
| The CORA-FHR research entry on Kaggle | **CORA_FHR_V1 submitted 18 October (57354496), score pending.** Native v23 runs unchanged, then FHR runs on growth-shaped tasks that native did not certify. In the committed run FHR ran on 62 of 240 stand-in tasks and committed 0, so a score near 0.00 is expected. The entry documents a runnable implementation, not unseen accuracy | `kaggle/cora_fhr_v1/` | `records/KAGGLE_CORA_FHR_V1_LOG_20261015.md` |
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
| `cora_fhr/` | CORA-FHR: G-grow grammar (`ggrow.py`), construction, reversible bridge, measurement arms, evaluator, audits |
| `cora_reach/` | the earlier constructor and its instance extraction (the failure evidence) |
| `kaggle/` | Kaggle notebooks and builders: `native_v1/`, `neural_v1/` (NVARC reproduction), `cora_fhr_v1/` (research entry), `ops/` (gated pipelines) |
| `records/` | protocols, results, audits, logs and the stage ledger (`STAGE_LEDGER.json`) |
| `docs/summit_poster/` | summit poster, abstract and explainer (LaTeX sources, PDFs, `figures/` with provenance) |
| `docs/summit_demo_20261023/` | the offline 90-second demo, a hash-checked replay of the recorded witness |
| `tests/` | `pytest tests/test_fhr.py` (grammar, blindness, fold locality, ties, the sealed final, degeneracy) |

## Reproducing

- Explainer, part 5: `docs/summit_poster/explainer.pdf`.
- Demo: `sh docs/summit_demo_20261023/run_demo.sh` (needs numpy).
- Figures: `python scripts/summit_figures.py`, which writes `docs/summit_poster/figures/PROVENANCE.json`.
- The sealed 80-task prospective final, the frozen 120-task pilot and every protected split stay unopened.

## Authorship and assistance

The research, design decisions, claims and authorship are Chimdi Walter Ndubuisi's. AI coding assistance was
used for parts of the implementation and documentation.
