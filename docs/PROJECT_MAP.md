# Project map: symbolic reasoning for ARC-AGI-2, December 2025 to 7 October 2026

Written 2026-10-07 from the four local project trees, their git histories,
the run history (kept from 18 April 2026), the CORA-TTI evidence documents
and the result records of the delivery workspace. Nothing was run to write
it. Step B outputs, ARC evaluation solutions, the protected HOLDOUT and the
separate VDCG project were not opened.

## 1. The four trees

| tree | what it is | git state | commits | span | on GitHub |
|---|---|---|---|---|---|
| `Reasoning_Project` | main worktree of `Symbolic_Reasoning_LLM_ARC-AGI`: the certified induction engine (v1 to v23), the engine paper, the Kaggle package, the Level 4 Step-B substrate. Step B runs from here. | branch `main` at `53ebae1` | 30 | 2025-12-30 to 2026-09-04 | yes, `main` |
| `Reasoning_Project_tti` | second worktree of the same repository: the CORA-TTI program (certified test-time invention), its gate protocol and field report | branch `cora-tti-dev` at `98d71a7`, split from `main` at `d12b1db` (2026-08-28) | 60 of its own | 2026-08-31 to 2026-09-15 | yes, `cora-tti-dev` |
| `Reasoning_Project_tti_pin_e5ef8b5` | third worktree, detached at `e5ef8b5`: the frozen code snapshot under which the CORA-TTI v2 census was reconstructed four times (`docs/CORA_TTI_V2_EVIDENCE_STATUS.md`) | detached `e5ef8b5` | none of its own | 2026-09-04 | the commit is on `cora-tti-dev` |
| `Reasoning_Project_arc2026` | separate repository: the ARC Prize 2026 delivery workspace. An allowlisted copy of the v23 engine (`geocat_arc/`), the Item-2 experiment chain v1.2 to v1.9, the manuscript, the Kaggle writeup and the real ARC pilot design. Its code imports `cora_tti` and `cora_parent` from `Reasoning_Project_tti` at `98d71a7`. | branch `master` | 191 before this map | 2026-09-23 to 2026-10-07 | from 2026-10-07, branch `arc2026-sprint` |

All commits in all four trees are authored by Chimdi Walter Ndubuisi. None
carries an AI co-author line.

## 2. Timeline

| when | what happened | key number | where |
|---|---|---|---|
| Dec 2025 | First prototype: a small program language with search, hints drafted by a language model, a learned ranking policy, vision-transformer experiments | prototype only | `main` (initial commit) |
| Apr 2026 | Restart as a research program on synthetic worlds; five hypotheses written before any result | active falsification nearly eliminated false rules on all 10 seeds | `RUN_HISTORY.md` |
| May 2026 | Real ARC and ConceptARC; hand-built solver portfolio; neural parts measured | 67 of 1,000 training tasks (12 May); a world-model reranker made it worse (47 against 61) | `RUN_HISTORY.md` |
| Jun 2026 | Module audit; GeoCat-ARC object engine started (30 June) | 480 audit runs, 0 false positives | `RUN_HISTORY.md` |
| Jul 2026 | Sealed full runs with leave-one-out certificates; first ARC Prize submission | 151 (5 July) to 173 (19 July); certified programs right 40 of 42 times, uncertified train-perfect ones 37 of 201; Kaggle 0.0 (12 July), local evaluation 0 of 120 | `main` |
| 1-19 Aug | Generated rules; the miner reinvents deleted primitives from residual pixels (E10); v23 sealed | **185 of 1,000** (19 August) | `main` |
| 18-25 Aug | CORA adopted; Step A frozen (62 failure clusters); Step B built, frozen, launched | Step B still running, no verdict | `main` |
| 31 Aug-15 Sep | CORA-TTI: scaffolding, test-time invention attempts, transfer and abstraction studies, gate protocol frozen | DEV-60 0.0 with and without TTI; 0 of 1,500 targets admitted | `cora-tti-dev` |
| 23 Sep-7 Oct | Delivery sprint: one preregistered, hashed experiment per question, one adversarial review per freeze | v1.9: 27 of 30 synthetic end-to-end witnesses | `arc2026-sprint` |

The May and June counts come from different pipelines and counting rules;
only the sealed counts from July on are one series.

## 3. CORA-TTI branch (`cora-tti-dev`, 31 August to 15 September)

| step | result |
|---|---|
| P2 scaffolding | Kaggle runtime emulator, typed failure graph, non-LLM two-head proposal network, batched executor with differential tests, hash-chained ablation ledger |
| first end-to-end loop | 5 of 12 certified reconstructions, all of operators the system already knew |
| S_base on the frozen DEV-60 | 0.0 pass@2 |
| S_base plus TTI (v1 generic schemas) on DEV-60 | 0.0 |
| Item 2 constructive corpus v1.1 | 0 of 1,500 targets admitted, and provably none could be (two admission rules contradict) |
| protocol v2 census | gates 3 and 5 fail; stopped (`e5ef8b5`) |
| evidence closure A to C | 13 supplied candidate structures admitted, every one with an empty failure frontier |
| failure-signal study | real failure trace fit 8 of 24 episodes, a shuffled trace 6, overlapping on one; proposal-network training not justified |
| acquisition and transfer | nothing newly reachable; four targets solved about 17 times more cheaply, but acquiring that ability cost about 50 times the savings |
| abstraction transfer | concrete reuse beat both abstraction rules |
| LAS-v1, then LAS-R1 | learned abstraction selection looked better than concrete reuse, then failed its replication gate (+3, 95 percent interval -1 to 8); every policy reached the same 188 of 256 targets; branch closed (`59f3f60`) |
| Capability-Growth Gate | protocol frozen (`da6c916`), version 2 frozen (`670a7d1`) before any Step-B outcome exists |

## 4. Delivery sprint (`arc2026-sprint`, 23 September to 7 October)

Every step below was preregistered and hashed before its data existed. Each
freeze got one adversarial review, and errata were recorded before any
outcome.

| step | date | question | verdict | key numbers |
|---|---|---|---|---|
| failure-frontier audit | 23 Sep | does the real engine record its own failures? | no, then repaired | no near miss or mismatch evidence on any of 12 tasks (it observed a proxy search); after the observation and compatibility repairs, evidence on 8 of 12, exactly the preregistered threshold |
| constructive proposer | 23 Sep | can a failure record produce new legal rule programs? | generation yes, steering no | |
| v1.2 corpus | 24 Sep | can a failure-to-rule training set be built? | yes | 215 admitted episodes, all 11 gates passed |
| scorer fit | 24 Sep | does failure evidence help choose the rule? | no | beats shuffled evidence, not demonstration statistics |
| scorer diagnosis | 24 Sep | model or data? | data | candidate features hurt; no evidence group recovers the target |
| v1.3 contrastive corpus | 26 Sep | can the failure summary tell two close targets apart? | no | 0.470 against an exact null of 0.429 |
| v1.4 localization | 28 Sep | with identical inputs, where does target information live? | yes, but the demonstrations are stronger | 0.565 against 0.5; demonstrations alone 0.664 |
| v1.5 selection | 2 Oct | does failure evidence add to the demonstrations? | no | 0.585 against 0.591 on 288 groups |
| v1.6 bounded repair | 5 Oct | does a candidate's effect on the failure add to the demonstrations? | yes, hybrid | intervention rule with demonstration fallback 0.641 against 0.580 (p 3.8e-5) on 136 ambiguous groups |
| v1.7 compiler | 5 Oct | can a selected extension become a production of the same engine? | yes | 6 of 6 accepted, used and exact; 3x-budget baseline 0 of 6; independent verification 11 of 11 |
| v1.8 no-oracle proposer | 6 Oct | can the extension come from the engine's own failure? | failure-specific, not end to end | specificity 13 to 0 and 7 to 0; complete witnesses 11 of 30 against 15 required |
| v1.9 engine stability | 7 Oct | why does the engine reject a produced extension on six-pair folds, and can one generic repair fix it? | repair accepted | 27 of 30 complete witnesses against 12; leave-one-out 27 against 12 tasks; precision 237 of 239 against 157 of 157 |
| real ARC pilot v1 | 7 Oct | does the closed loop rescue a real ARC-AGI-2 task? | design in progress, not run | training split verified by checksum; 548 in-scope tasks found from demonstrations only |

## 5. Tried and dropped

- Language-model hints and learned ranking policies (the December
  prototype).
- A world-model reranker (worse than none), a DINOv2 vision probe (at
  chance), a small recursive network (memorized), a search-guide network
  (no gain, three losses at scale) and a per-task compression solver (fit
  37 of 40 training tasks, right on 2 of 40 tests). Neural parts stayed
  advisory only.
- Generic test-time schemas (DEV-60 0.0) and the first constructive corpus
  law (0 of 1,500).
- Learned abstraction selection and abstraction transfer: selection and
  cost changed, reach never did.
- Passive failure descriptors as a selection signal (scorer fit, v1.3, v1.5,
  the v1.6 passive arm): none added anything beyond the demonstrations.

Each of these is recorded with its diagnosis; none was patched after its
result.

## 6. What is established and what is not

Established:
- 185 of 1,000 ARC-AGI-2 training tasks solved with leave-one-out
  certificates (v23, sealed 19 August 2026).
- The certificate separates rule from coincidence on training tasks (40 of
  42 against 37 of 201).
- On synthetic tasks: an intervention-based selection rule with a
  demonstration fallback (v1.6, hybrid), a working extension compiler
  (v1.7), a failure-specific no-oracle proposer (v1.8) and, after one generic
  engine repair, a complete same-reasoner closed loop on 27 of 30 new tasks
  (v1.9, LEVEL 2, synthetic only, limited to extensions whose keys are
  witnessed at least twice).

Not established:
- Any real ARC task solved by a constructed extension.
- Any training score above 185 of 1,000; no new 1,000-task run has been
  made since v23.
- Any ARC-AGI-2 evaluation success (local 0 of 120; Kaggle 0.0 in July).
- Durable semantic invention (Step B has no verdict).
- That the engine can tell right from wrong installed extensions: under
  v1.9 it accepted every wrong extension it was given, so real-task safety
  has to come from selection, held-out checks and abstention.

## 7. Where things stand (7 October 2026) and what comes next

1. Real ARC causal pilot v1: data audit done
   (`records/REAL_ARC_PILOT_V1_DATA_AUDIT.md`), design and freeze in
   progress, not run. Goal: one complete, independently scored rescue of a
   real training task.
2. If it produces a witness: bounded real-task development, then a frozen
   1,000-task characterization, the 60 DEV, a final freeze, and the protected
   60 HOLDOUT, in that order. The 1,000-task run, the 60 DEV and the 60
   HOLDOUT are blocked until then.
3. Step B keeps running untouched; its gate protocol waits for its freeze.
4. Calendar (`records/KAGGLE_2026_CONSTRAINTS.md`): entry deadline
   2026-10-26, final code 2026-11-02, Paper Award 2026-11-08. The paper's
   results must come from the leaderboard and the public evaluation, not the
   training set.

## 8. Where to find things

| item | location |
|---|---|
| authoritative manuscript | `docs/PAPER_SKELETON.md` (this workspace) |
| Paper Track writeup (1,500 words) | `kaggle/writeup.md` (this workspace; last revised 2026-09-23) |
| engine paper, v23 | `paper/DRAFT.md` and `paper/latex/main.pdf` on `main` |
| full chronology from April 2026 | `RUN_HISTORY.md` on `main` |
| CORA-TTI documents | `docs/` on `cora-tti-dev`, starting with `CORA_EVIDENCE_LADDER.md` |
| protocols and results v1.2 to v1.9 | `docs/` and `records/` here; `records/STAGE_LEDGER.json`; `RESUME.md` |
| ARC data | not in git; ARC-AGI-2 training split pinned by sha256 in `records/REAL_ARC_PILOT_V1_DATA_AUDIT.md` |
