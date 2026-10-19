# Neural-CORA v1 pilot protocol: does a learned Qwen-feature guide improve CORA's executable search?

**Status: FROZEN** when this file is committed. Training, the arm runs and the evaluation all come after that
commit. Nothing below may be changed after any answer is read. A change made for any reason creates a new versioned
protocol.

Written 2026-10-19 for the user's directive "NEURAL-CORA: ONE LEARNED EXECUTABLE REASONER" (sections 3 and 9).

## 1. The question, and the claim ceiling

**Question.** Can learned Qwen features change which executable programs CORA proposes, in a way that beats search over
the same typed language with equal or greater compute?

**What a GO would show.** A trained guide, reading frozen Qwen3-4B features of the demonstrations, orders CORA's own
typed program search so that CORA selects more exactly correct test outputs than:
- strong symbolic search (C+, C+H);
- the same guide on hand-crafted features (L1h);
- an untrained guide (L0) and a shuffled-label guide (L0s).

This holds on held-out *compositions* of CORA's own synthetic families.

**What a GO would not show:**
- automatic diagnosis, revision, or learning from failure (no revision action runs in this pilot);
- semantic invention;
- real-ARC generalization;
- a Kaggle-level result.

A G1 GO licenses only the next gated stage.

## 2. The single algorithm under test

**CORA owns the loop.** It holds:
- the task representation: 7 native segmentation views;
- the typed hypothesis language `ncv1-g0`: 31 selectors, 92 actions, at most two first-match rules, and a default of
  keep or delete;
- the fixed native interpreter (`geocat_arc` `render_program`);
- the best-first enumerator;
- the two-attempt selection rule;
- every acceptance decision.

**Qwen's contribution.** The NVARC checkpoint `sorokin/qwen3_4b_grids15_sft139` (Apache-2.0) is a *frozen* encoder.
- It reads the demonstrations and the test input in its own chat format.
- A trainable head (an MLP of 12,800 → 1024 → 512 → five component heads) turns those features into
  log-probabilities over CORA's typed components: view, number of rules, default, selector bag, action bag.
- CORA's enumerator turns these scores into a best-first order.

**What the guide never does:**
- emit a grid;
- see a test output;
- accept a program.

**Excluded:**
- NVARC's own grid outputs;
- NVARC's test-time LoRA;
- any NVARC lane, router, ensemble or second-attempt filler;
- NVARC's synthetic program text, which is unlicensed and contaminated.

**The reasoning state** `S_t` (`cora_neural_v1/state.py`) is updated after every execution and recorded per task:
- the consistent version set;
- the feedback on which demonstration failed;
- the views of the consistent hypotheses;
- the observable diagnoses;
- the budget used.

v1 does not act on the diagnoses. The action policy is a later, separately gated stage.

## 3. Data

**Generator.** `ncv1-gen0` (`cora_neural_v1/generator.py`), CORA's own, with no third-party data.
- Execution-validated: native `render_program` computes every output.
- Scenes are 8–12 × 8–12 grids with 3–6 non-touching single-colour objects.
- Each task has 3 demonstrations and 1 test.

**Families:**
- **TRAIN (11):** single rules (recolour by colour; delete by size; translate by colour; line by colour; recolour the
  largest; slide all; keep only a colour; delete by colour) and three two-rule compositions.
- **HELD-OUT (7):** new pairings of the same component types:
  - line by size; slide by colour; delete the largest;
  - recolour-then-line; slide-then-recolour; delete-then-translate;
  - line with the default delete.

  No held-out family uses a component value class that training lacks.

**Splits** (family set, seeds), fixed before any learned run:

| split | families | seeds | tasks |
|---|---|---|---|
| train | TRAIN | 0–299 | 3300 |
| val | TRAIN | 1000–1029 | 330 |
| eval_iid | TRAIN | 2000–2019 | 220 |
| eval_heldout | HELD-OUT | 3000–3059 | 420 |

**Data audit** (`python -m cora_neural_v1.pilot audit`; `outputs/neural_cora_v1/audit/data_audit.json`, sha256
`075e8b64309e956f86bf888af2560bd7a3bd86fefc8bde5874a2c4f9e054bdb2`). It ran on the generator side before any training or arm run, and read no answers file.
- Execution validity: 0 problems.
- Exact duplicate tasks across splits: 0 (all six split pairs).
- Held-out composition signatures present in training: 0.
- Distinct program instances: train 998, val 200, eval_iid 144, eval_heldout 302 (held-out shares 0 instances with any split).
- Instances shared by train and eval_iid: 105. That is expected in-distribution; the tasks themselves
  differ.

**The primary held-out set.** A held-out task is *template-aliased* if a program with a TRAIN family's structure,
under any parameters in its pruned domains, reproduces all of its demonstrations. The check reads demonstrations only.
- Aliased tasks are excluded from the primary set and reported separately.
- Primary set: **395** of 420 tasks (`audit/eval_heldout_primary.json`, sha256 `8f647512d0ecaa72b567d28ae87e3b6ff29a921f4054a2eec73cc4f7433fa6f1`).
- Aliased tasks by family: H_delete_largest 16 of 60 (a delete-by-size template fits; 3 of them also fit recolour-then-delete); H_line_by_size 9 of 60 (a line-by-colour template fits); the other five held-out families 0 of 60 each.

**Exposure log:**
- The engineering checks used TRAIN families only (seeds 10000–12100).
- Before this protocol, held-out families were touched once, in a symbolic-arm smoke test: seeds 5000–5002, 9 tasks
  (C+ 0/9, C+H 1/9). This happened before C+H's change analysis was improved. Those seeds are not used here.
- That exposure can only have favoured the symbolic control C+H, which makes the test conservative for L1.
- No real ARC task and no NVARC program is used.

## 4. Training (the only fitted parameters are the guide's heads)

**Targets are extensional.** For each rule, a component value counts as correct if, swapped into the generating
program, it still reproduces every demonstration. Aliases are grouped, not penalized. Targets are built from
demonstrations only (`prior.targets`).

**Loss (preregistered):** the conditional likelihood of the typed components. It is binary cross-entropy for:
- the view;
- the default;
- the selector bag (weight 4);
- the action bag (weight 4).

Plus cross-entropy for the number of rules.

**Optimizer and selection:**
- AdamW, lr 1e-3, weight decay 1e-4;
- batch 128, 60 epochs;
- dropout 0.2 and 0.1;
- the kept checkpoint is the epoch with the best validation loss;
- seed 20261019.

**The guides:**

| guide | features | targets | trained |
|---|---|---|---|
| **L1** | frozen Qwen3-4B, 12,800 values (`prior.QwenEncoder.features`) | true | yes |
| **L1h** | 103 hand-crafted delta features (`prior.hand_features`) | true | yes |
| **L0s** | Qwen | shuffled across tasks (a fixed permutation) | yes |
| **L0** | — | — | no: the same architecture and seed, untrained |

**Evidence of training, logged in `outputs/neural_cora_v1/models/training_log.json`:**
- trainable parameter counts;
- the number of optimizer steps;
- per-epoch gradient norms;
- the initial and final weight sha256;
- how far the weights moved (L2).

## 5. Arms and budgets

| arm | order of CORA's typed search | candidates run |
|---|---|---|
| C0 | native CORA's own inducer (frozen v23), its own grammar; context only | 5 s process CPU |
| C+ | simplest-first (Occam) | 1000 |
| C+H | C+ plus the researcher-designed delta analysis: the strong symbolic control | 3000 |
| L0, L0s, L1h | guide scores | 1000 |
| L1 | guide scores (trained, Qwen features) | 3000 |

Every typed arm searches the **same pruned candidate space**, with the same interpreter, checker and two-attempt rule.
Only the order differs.

**Smaller budgets are exact truncations.** The search records the order position at which each distinct prediction
first appears. So a result at budget b ∈ {100, 300, 500, 1000, 3000} is exactly what a run stopped at b would give.
No arm is extrapolated past the budget it ran.

**Compute matching for the primary comparisons:**
- The learned arms are scored at 500 candidates; C+ and C+H at 1000.
- The Qwen encoder's GPU time per task (measured and reported, about 0.3 s on a 2080 Ti) is charged by giving the
  symbolic arms twice the candidates. At about 0.55 ms of CPU per candidate, 500 extra candidates cost about 0.3 s.
- Equal-candidate comparisons and the full budget curves are reported as secondary results.

## 6. Metrics

**Primary:** exact pass@2 (either of two attempts equals the test output) on the primary held-out set.

**Secondary:**
- candidate coverage: the correct output among the distinct demonstration-consistent predictions within budget;
- tasks with any consistent program;
- abstentions;
- wrong first attempts;
- per-family pass@2;
- IID results;
- the aliased held-out subset;
- budget curves;
- the distribution of observable diagnoses;
- CPU per task, Qwen GPU time and peak memory;
- lost answers relative to C+H.

**Uncertainty:** Wilson 95% intervals for each rate, and paired exact McNemar tests (two-sided).

## 7. The preregistered decision G1 (LEARNING GO)

This is computed by `cora_neural_v1/evaluate.py` on the primary held-out set. It is an intersection-union test:
**all** of these must hold.
1. L1@500 > C+@1000, net > 0 and McNemar p < 0.05.
2. L1@500 > C+H@1000, net > 0 and p < 0.05. This is the strong symbolic control.
3. L1@500 > L1h@500, net > 0 and p < 0.05. This shows Qwen-specific value.
4. L1@500 > L0@500 and L1@500 > L0s@500, each with net > 0 and p < 0.05. This shows the learned weights matter.
5. **Harm:** L1@500's wrong first attempts ≤ C+H@1000's + 5% of the primary tasks.
6. **Breadth:** L1@500's net gain over C+H@1000 is positive in at least 3 of the 7 held-out families.

**Outcomes:**
- **G1_GO:** all six hold.
- **LEARNED_OVER_PLAIN_SEARCH_ONLY:** 1 and 4 hold, but 2 or 3 fails. The learned guide beats plain search, but not
  strong symbolic search or hand features. That is **NO-GO** for a Qwen-specific benefit.
- **CANDIDATES_ONLY:** L1@500 covers more correct candidates than C+@1000 without more exact selections. **NO-GO.**
- **NO_LEARNING_GAIN:** otherwise. **NO-GO.**

**If G1 fails, the report must say which of these applies, with evidence:**
- (a) the Qwen features are uninformative: L1 ≈ L0s, or L1 ≈ L1h;
- (b) training was underpowered: the validation loss and component accuracy;
- (c) the labels alias: target alias statistics;
- (d) the data are too narrow;
- (e) the language has no solution: C+H@3000 and L1@3000 coverage, the expressivity ceiling.

No tuning on these evaluation tasks after any answer is read.

**Not tested in this pilot:**
- G2 (expressivity);
- G3 (diagnosis);
- G4 (reusable capability);
- G5 (real ARC);
- G6 (Kaggle candidate).

## 8. Resources and safety stops

**Resource caps:**
- one GPU (GPU 0, RTX 2080 Ti); GPU 1 belongs to another user's process and is not touched;
- at most two CPU processes at a time, at nice 10;
- at most 6 hours of wall time for features, training, the arm runs and the evaluation.

The run is resumable: missing rows are appended.

**Immediate stop if any of these happens:**
- any solver-side code reads an answers file;
- the interpreter fails its purity or restoration test;
- an execution has an unverifiable state;
- the rows are incomplete or duplicated (the evaluator asserts this);
- dataset leakage appears: an exact duplicate across splits, or a held-out signature in training.

## 9. Isolation and integrity

- Solver-facing evaluation files hold only demonstrations and test inputs (`corpus/*_public.jsonl`).
- The answers live in `evaluator/` and are read only by `evaluate.py`.
- No hidden ARC data, and no protected split: not Step B, VDCG, E_transfer, Lockbox, HOLDOUT, ARC-1000, frozen 120 or
  sealed C4.
- The frozen baselines (native CORA, CORA-FHR, CORA-v2, Phase 2a outputs, the NVARC deployment and checkpoint) are
  hashed in `records/NEURAL_CORA_V1_FREEZE_MANIFEST.json` and never modified.

## 10. Reproduction

```
sh scripts/neural_cora_v1_prep.sh                  # freeze, generate, audit, targets, Qwen and hand features
python -m cora_neural_v1.pilot train               # GPU 0
NEURAL_CORA_WORKERS=2 python -m cora_neural_v1.pilot run
python -m cora_neural_v1.evaluate                  # evaluator/pilot_v1_eval.json, evaluator/task_level.jsonl
```

Every output's sha256 is recorded in `outputs/neural_cora_v1/manifest.json`.
