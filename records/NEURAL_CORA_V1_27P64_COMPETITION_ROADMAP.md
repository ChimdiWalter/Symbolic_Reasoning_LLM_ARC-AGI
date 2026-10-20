# Neural-CORA: the evidence-gated route toward beating 27.64% (19 October 2026)

**Target.** An ORIGINAL, unified Neural-CORA solver whose official ARC-AGI-2 public score exceeds 27.64%. That
27.64% is the separately reproduced NVARC/Qwen3-4B method: NVARC's work, submission 57160429. This is a stretch goal,
not a promised result.

**Today:**
- native CORA and CORA-FHR score 0.00% (57144804, 57354496);
- Neural-CORA has no Kaggle result.

## 1. The evidence tiers (never mixed)

1. **Synthetic.** CORA's own held-out generator families. This tier shows trainability and a learning effect inside
   the language; it says nothing about real ARC. The v1 pilot is here.
2. **Permitted real ARC development.**
   - A fresh cohort is chosen by a predeclared rule before testing, with exposure logs, isolated from earlier
     development and from every protected split.
   - Exposed tasks (dev60, the 58 pool, Phase 2a's 40) are for debugging and expressivity measurement only.
   - Public training tasks may overlap the Qwen checkpoint's pretraining, so they are never "unseen" for NVARC
     comparisons.
3. **Official Kaggle hidden scoring.** The only comparison with 27.64%. It needs a legal, offline, fully rehearsed
   notebook and the user's approval of the exact version.

## 2. The gates (failing one is never repackaged as success at a later one)

| gate | it requires | status |
|---|---|---|
| G1, learning | the trained guide with Qwen features beats C+, C+H, L1h, L0 and L0s on frozen held-out synthetic compositions | **NO-GO** (20 Oct; `LEARNED_OVER_PLAIN_SEARCH_ONLY`; section 5 and the pilot report) |
| G2, expressivity | the typed language covers independently held-out transformation families, without task-specific operators | 20 Oct: ncv2-g1 built and parity-tested; the dev60 G2 protocol is frozen (`records/NEURAL_CORA_V2_G2_PROTOCOL_20261020.md`); **not yet measured** |
| G3, diagnosis | authentic observable traces lead to better revision choices than strong failure-blind and shuffled controls, under equal access and compute | not tested (earlier negatives: L9, L10, L12d, L12e) |
| G4, reusable capability | new abstractions transfer to held-out families and survive the removal, semantic-identity and baseline-reach tests | not tested |
| G5, real ARC | extra exact correct predictions on a predeclared, eligible real development cohort, with no unacceptable harmed outputs | not tested |
| G6, Kaggle candidate | a full offline rehearsal: runtime, integrity, licences, accuracy | not tested. **No submission without the user's approval** |

## 3. Why a ranker alone will not reach 27.64%

A neural ranker cannot discover a program outside the language it ranks.

**The language today.** `ncv1-g0` has:
- 7 views, 31 selectors and 92 actions;
- at most two first-match rules;
- shape-preserving outputs only;
- no copying, no part-level operations, no relational guards, and no multicolour object outputs.

**The real-task evidence:**
- Phase 2a: 33 of 40 tasks had no fitting hypothesis in CORA-v2's richer language (GEOMETRY_GAP).
- dev60: 26 tasks had demonstration-fitting programs that failed the test, i.e. they memorized.
- The dev60 atlas (`records/NEURAL_CORA_V1_EXPRESSIVITY_AND_FAILURE_ATLAS.md`) measures the coverage of `ncv1-g0`
  directly.

**So the route needs all four of these:**
1. Broad object, part and whole-grid transformation coverage: size changes, copying, part-wise and relational rules.
2. Useful learned search over that larger space. This is what G1 tests in the small one.
3. Safe but not over-conservative answer selection. Phase 2a: certification was not correctness, and v2 abstained
   too often.
4. Efficient reuse of pretrained neural capability inside CORA's loop.

## 4. Stage options after G1 (choose one; never all three at once)

| stage | what | trainable parameters (est.) | data and licence | expected failure modes |
|---|---|---|---|---|
| 7A, structured proposal decoder | a small constrained decoder or LoRA that emits typed ASTs or structured edits, compiled and executed by CORA | LoRA on Qwen3-4B, r=16: about 30 M; or a 50–100 M from-scratch decoder | CORA's execution-verified teacher programs (own generator); Apache-2.0 checkpoint | syntactic aliases; programs outside the grammar; coverage still capped by the language |
| 7B, execution-feedback revision policy (pi_phi) | encode demonstration differences, rejection types, competing views and fold fragility; choose a bounded revision | about 1–5 M (heads on the frozen encoder) | generated episodes, disjoint from the held-out families | the generator's "failure types" make the task artificial; controls must match information |
| 7C, task-local adaptation | LoRA-style adaptation of the guide on visible demonstrations, re-adapted per fold | about 30 M per task (transient) | visible demonstrations only | GPU time per task; fold leakage unless re-adapted |

**Runtime facts:**
- NVARC's own rehearsal took about 4.34 h, including test-time training.
- Kaggle's limit was last documented at 12 h. The current rules must be checked before any notebook is engineered.
- v1 measured Qwen features at 0.30 s per task on a 2080 Ti, and typed search at about 0.55 ms of CPU per candidate.

## 5. The decision after the v1 pilot (20 October 2026)

**G1 = NO-GO** (`LEARNED_OVER_PLAIN_SEARCH_ONLY`; `records/NEURAL_CORA_V1_PILOT_REPORT.md`).
- On held-out synthetic compositions, the trained Qwen-feature guide solved 198/395. That beats plain search (104),
  an untrained guide (30) and a shuffled-label guide (51).
- It lost to the hand-feature guide (235, p = 0.0009) and to strong symbolic search (358).
- So training changes CORA's search, but the Qwen features add nothing over hand features here.

**The dev60 atlas** (`records/NEURAL_CORA_V1_EXPRESSIVITY_AND_FAILURE_ATLAS.md`). On 60 exposed, same-shape, real ARC
training tasks, the v1 language admits a fitting program for **1**, even under its best order. On real ARC the binding
constraint is expressivity (G2), not search order.

**So:**
1. **No Kaggle candidate is justified.** G1, G2 and G5 have not passed, and there is no Neural-CORA notebook.
   `kaggle/neural_cora_v1/` stays a scaffold.
2. **The single next justified experiment is G2 (`ncv1-g1`):**
   - Expose native CORA's existing primitives in the typed IR: copy, move_until_adjacent, connect, grow,
     crop_to / extract_part, and relational guards.
   - Measure compile and correct-output coverage on dev60 (expressivity only), then on a fresh, predeclared eligible
     cohort.
   - This is researcher-designed, not invention. It needs the user's approval of a frozen protocol.
3. **Only after G2:**
   - a pairing-aware learned guide over the larger language;
   - then the revision policy pi_phi (G3).
4. **A realistic note.** Reaching 27.64% needs broad coverage of real ARC transformations.
   - The v1 language covers about 2% of a same-shape exposed cohort.
   - Native CORA's richer languages solved 12 of those 60 tasks over two attempts.

   A competitive Neural-CORA by 2 November is **unlikely**. The honest near-term competition outcome is "an original
   CORA-family solver with a non-zero score", if any later stage passes its gates, with 27.64% as the stretch goal.

## 6. Schedule

| date | what |
|---|---|
| 21 Oct | poster print freeze |
| 23 Oct | the summit: only already-audited claims |
| 26 Oct | entry and team-merger deadline |
| 2 Nov, 23:59 UTC | code deadline |
| 8 Nov | paper (plan for the 8th) |

Neural-CORA work proceeds only through the gates. No date is promised for beating 27.64%.
