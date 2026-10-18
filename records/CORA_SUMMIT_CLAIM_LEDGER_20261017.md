# CORA summit claim ledger (authoritative; compiled 2026-10-18 from retained artifacts; nothing rerun)

## Rules

- Configurations are never mixed.
- "Training development" means ARC-AGI-2 training tasks. They are exposed tasks, so no row is a
  generalization claim unless it says so.
- Hashes are the first 16 hex digits of sha256.

## Shared identities

| item | identity |
|---|---|
| frozen native v23 library | cdacd018 |
| frozen native v23 learned verbs | b1f07ba5 |
| G-grow v1 grammar | identity 0ec16d1e; 10 sources × 50 transforms; 37,750 expressions = 500 depth-1 + 25,000 depth-2 + 12,250 same-source unions (`cora_fhr/ggrow.py`, 05876835) |
| CORA_FHR_V1 Kaggle package | tarball 9910893f |
| repository commit at compilation | 5162760 |

## Claims

| # | claim | configuration | dataset (denominator) | evidence (hash) | status | permissible wording |
|---|---|---|---|---|---|---|
| 1 | the native object branch's check is precise | native v23 **object branch**, without frozen assets | 60 training development tasks | `outputs/funnel_v0/eval_dev60_native.json` (3fb8c0e3) | DONE | "On 60 exposed training tasks, the object branch's leave-one-out check accepted 6 answers, all correct; with the check off, its first-ranked outputs were 8 correct and 26 wrong." |
| 2 | the same, as submitted | object branch, **with** frozen library and verbs | the same 60 | `eval_dev60_native_assets.json` (54d8d744) | DONE | "6 correct and 0 wrong accepted; with the check off, 8 correct and 25 wrong; a correct candidate existed on 8 tasks." Never pool this with row 1 |
| 3 | the dominant failure is memorization | rows 1 and 2 | the same 60 | as above | DONE | "26 tasks (27 without the frozen assets) had demonstration-fitting programs that were all wrong. With the assets, one task becomes an asset-triggered native error, not a repaired solve." |
| 4 | whole-harness precision | native v23 **whole harness** | the same 60 | `eval_dev60_harness.json` (2d9d5dd0) | DONE | "12 of 60 exact over two attempts; 29 claimed, 18 of those wrong." This is not the object branch |
| 5 | more search does not repair memorization | funnel budget3 (3× search) | the same 60 | funnel record | DONE | "Three times the search budget repaired none of the memorized fits." In the separate FHR comparison (row 11), 1.33× matched search certified one extra task (7 vs 6), which was not a memorized-fit task |
| 6 | selection among supplied candidates | v1.6 CFR, **candidates supplied**, synthetic | 657 queries in 136 verification-ambiguous groups | `records/ITEM2_V16_CFR_RESULT_20261005.md` (85dcf0ef) | DONE | "A candidate's measured effect improved selection among supplied programs: 64.1% vs 58.0% on synthetic queries." Not integrated ARC accuracy, and not construction |
| 7 | executable construction works once | CORA-FHR, arm E, frozen verification | synthetic C4 dev v2 (27 tasks; corpus d5bab8e4) | `witness_dev_D3_04.json` (a83f597a); `degeneracy_audit.json` (482fff83) | DONE, narrow | "On one synthetic task CORA constructed a missing **single-step** operator (ring(8) around the minority cell), installed it reversibly, rebuilt it in 3 of 3 folds, predicted the held-out query correctly, and lost the gain when it was removed." **Not** a two-part union: the planted second step is vacuous |
| 8 | extension certificates | arms C, C′, D, E | C4 dev v2 (27) | `eval_c4_dev_v2.json` (09b85b00) | DONE | "3 correct extension certificates per construction arm, of which 2 are already-reachable control tasks; 0 wrong extension certificates." Native itself made 2 wrong certificates on the ambiguous and wrong-action controls, so the whole system was not error-free |
| 9 | failure evidence causes the gain | E vs information-matched C′ | C4 dev v2 (27) | `rows_c4_dev_v2_C2.jsonl` (1ffbd4d5) | **NOT ESTABLISHED** | "A failure-blind constructor with the same correspondences matched the authentic-failure arm on every synthetic growth task." |
| 10 | failure evidence helps with mixed coverage | 8-task mixed pilot, frozen stop rule | `mix_dev.json` (0a4aabc6) | `rows_mix_dev.jsonl` (c9dace2b) | **NEGATIVE (stop rule failed)** | "When object kinds differed by colour, colour clustering matched it (2 = 2). When they differed by size only, the failure record proposed the right operator (3 vs 0), but native rejected it every time (0 correct)." |
| 11 | FHR on real tasks | arms A, B, C′, E | 60 training development tasks | `rows_dev60.jsonl` (3d0be0de) | **NEGATIVE** | "No extension certificate: E 0 and C′ 0, against frozen native 6 and matched search 7." |
| 12 | why construction yields nothing | log autopsy plus a declared re-extraction | rehearsal 62; dev60 60 | `records/CORA_REVISION_ROOT_CAUSE_20261018.md` | DONE (logs); re-extraction pending | "Of 62 eligible rehearsal tasks: 20 had no memorized-growth evidence, 39 had evidence but no fitting operator, 2 hit the extraction cap, and 1 proposal failed reconstruction." |
| 12b | where the construction evidence fails | declared re-extraction | 25 dev60 evidence/no-operator cases | `outputs/cora_fhr/root_cause_reextract_20261018.json` | DONE | "18 were inexpressible in the declared G-grow grammar (not 'beyond all programs'), 5 lacked support across demonstrations, and 2 were grouping conflicts." |
| 12c | **a constructed rule solves a real ARC task** | guard probe, arm EG with a typed applicability guard (protocol 445f78e) | **1** real ARC-AGI-2 **training** task (ka95aa62f67d9), **selected by the autopsy** | `outputs/cora_fhr/rows_dev60_guard.jsonl` (c7d45ab4); demo `replay_real.py` | DONE, narrow | "On one real training task, which frozen native and extra search both fail, CORA built the rule 'colour-{1} objects shoot a ray north-west from their centre, others south-east', installed it reversibly, rebuilt it in 3 of 3 folds and answered correctly. A failure-blind constructor with the same evidence found the same rule. It was developed after the Kaggle entry and is not part of it." |
| 12d | guard pilot: failure evidence versus the failure-blind control | frozen guard probe (445f78e), 10 cases | 2 real (in-sample) + 8 fresh synthetic | `guard_status.json`; `rows_*_guard.jsonl` | DONE; **no causal claim** | "EG 2 correct, C2G 1 correct + 1 tie abstention, 0 wrong, 0 lost. One discordant pair favoured the failure record, which removed an applicability ambiguity; with one pair this is not evidence (p = 0.5)." |
| 12e | hand-designed revision controller | `cora_fhr/revision_controller.py`, retrospective | 60 dev tasks | root-cause record, section 4 | **NEGATIVE** | "The rules-based controller's retry choices missed the only gain from extra search: 6 correct vs 7 for search everywhere." |
| 12f | **does guarded construction generalize?** | frozen generalization test (ad4127a) with 6 arms | **58 independently selected** exposed training tasks | `gen_status.json`; `rows_standin58_gen.jsonl` | **NEGATIVE** | "On 58 independently selected training tasks, no construction arm (authentic, failure-blind, shuffled or contrast) produced a certified answer: 0 of 58, with 0 wrong and 0 lost. Frozen native solved 1. There were no discordant pairs, so failure information showed no advantage, and the version was stopped." |
| 13 | official Kaggle, native | native v23 | ARC-AGI-2 public board | 57144804 | DONE | "Native CORA: 0.00." |
| 14 | official Kaggle, neural baseline | NVARC Qwen3-4B reproduction, **not CORA** | public board | 57160429; originality audit | DONE | "A faithful reproduction of the public NVARC pipeline scored 27.64. It is not CORA." |
| 15 | official Kaggle, CORA-FHR research entry | CORA_FHR_V1 (native v23 plus the FHR phase) | public board | 57354496; `run_v1/execution_manifest.json` (0b68bf78) | **DONE: public 0.00** (18 October) | "Submitted 18 October. In the committed rehearsal (240 training stand-ins, 5.88 h) FHR ran on 62 tasks and committed no answer." Official public score **0.00**, as predicted by its zero-commit rehearsal; the guarded rule is not part of it |
| 16 | NVARC plus CORA complementarity | native CORA filling empty NVARC second attempts | 240 stand-ins (contaminated) | `standin_paired.json` (d7f2363a) | **NO-GO** | "0 gained, 1 lost (a correct 1×1 [[0]] placeholder); no duplicate genuine attempts existed." |
| 17 | biological transfer | — | — | `docs/BIO_TRANSFER_PROPOSAL_20261013.md` | **PROPOSED / UNTESTED** | "A proposed test. What might transfer is the revision policy and the verification interface, not ARC operators." |

## Not to be said

- "CORA learns from failure"; neither row 9 nor row 10 supports it.
- "Three new inventions"; see row 8.
- "Zero errors", without its scope.
- Any pooled number across rows 1 and 2.
- The NVARC score presented as CORA's.
- That frontier models cannot reason, use tools, or learn grammars.
