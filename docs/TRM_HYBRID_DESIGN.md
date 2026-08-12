# Hybrid TRM attempt_2 — design record (2026-07-19, updated 2026-07-21)
User-approved (queue item #4 -> "queue in 1,2 and 3"; GPU launch "go
ahead with trm gpu"; neural-LOO gate "yes"). Source recipe: "Less is
More: Recursive Reasoning with Tiny Networks" (2510.04871, ARC Prize
2025 paper award winner).

## Role in the architecture (the certified/uncertified split)
- attempt_1: UNCHANGED — the certified symbolic inducer (LOO gate, four
  program families). The paper's contribution stays pure.
- attempt_2: TRM render when the symbolic engine has no near-solve (or
  its render is known-worse). Attempt_2 carries NO symbolic certificate
  — but may carry a NEURAL-LOO gate label (see Step 3b), a separate,
  weaker, empirically-calibrated tier.
- No LLM, no pretraining, Kaggle-legal (trained only on the ARC training
  split + augmentations; weights ship in the dataset tarball).

## Novelty position (recorded 2026-07-21, user asked "is my TRM new?")
The TRM block itself is a faithful REIMPLEMENTATION of 2510.04871 —
cite it plainly, claim nothing for it. The novel contributions are:
1. the certified/uncertified hybrid (symbolic gate for precision +
   recursive neural fallback for recall — unpublished combination);
2. the certification framing (engine knows which answers are
   guaranteed; neural component never contaminates certified claims);
3. extending falsifiable acceptance gating across the symbolic-neural
   boundary (neural-LOO, Step 3b) with measured precision.

## Step 1 — data pipeline (DONE, trm/build_dataset.py)
- 190,000 train / 1,000 val examples (task-level 95/5 split, no leakage)
- Example = (up to 3 demo pairs + query input) -> query output
- Canvas 30x30, PAD=10; channels [7, 30, 30] int8
- Augmentation per TRM recipe: dihedral (8 forms) x color permutation
  (bg fixed), 200 augments/task train, 20 val
- Training-task TEST pairs included as supervised examples (standard;
  they belong to the training split). CONSEQUENCE: any gate/metric on
  training tasks is contaminated — measure on eval only.

## Step 2 — model + training (RUNNING since 2026-07-21)
- trm/model.py: TRM, 1.8M params (d=256, 2 blocks, RMSNorm/MHA/SiLU),
  cell+channel+positional embeddings over [B,7,30,30] -> [B,900,256];
  latent recursion n=6 (z <- net(xe+y+z) x6, then y <- net(y+z));
  forward = T-1 no-grad recursions + 1 with grad; out_head (11 logits)
  + halt_head. FIX LEARNED: in_norm (RMSNorm) on the recursion input —
  without it additive drift explodes the loss to ~1e6.
- trm/train.py: deep supervision (N_sup, env TRM_NSUP), EMA 0.999,
  halting BCE, per-epoch checkpoints (latest.pt full state + ema_only.pt)
  -> resumable by relaunching the same command. CPU smoke: --smoke flag.
- SIZING REALITY on RTX 2080 Ti 11GB (measured 2026-07-21, N_sup=6):
  B=24 peak 6.3GB ~10.5h/epoch; B=16 peak 4.2GB ~9.8h/epoch (best
  throughput); B=12 3.2GB. Batch 96/48 OOM beside P01's 2.9GB tail —
  activation memory of the with-grad recursion over 900-token seqs
  dominates and barely shrinks with batch. Paper's 50 epochs = ~3 weeks
  -> INFEASIBLE; but one epoch here = 200 augmented views/task, so
  3-7 epochs (~1.5-3 days) ~ paper-scale coverage.
- LIVE RUN: `TRM_NSUP=6 python trm/train.py 50 16 cuda` detached
  (logs/trm_train.log); 50 is an UPPER BOUND — stop on val_exact
  plateau, judged per-epoch. Loss 0.62 -> 0.377 by step 250 of 11875.
- OPERATIONAL LESSONS: rm stale smoke checkpoints before a real launch
  (a run silently "resumed from epoch 1" off the CPU smoke ckpt); kill
  the GPU watcher once training starts (it double-launched); GPU 1 is
  driver-dead (NVML "Unknown Error", PCI-visible) — needs post-P01
  reboot to recover.

## Step 3a — inference (DONE, trm/infer.py)
- TRMSolver: loads EMA checkpoint, encodes task exactly as
  build_dataset's identity augmentation (3 demo pairs + query, PAD=10),
  runs N_SUP=16 refinement steps (env TRM_INFER_NSUP), decodes by
  trimming the PAD frontier (interior PAD holes -> background).
- `python trm/infer.py [ckpt]` = sample-20 exact-match probe on
  training tasks (fast per-epoch signal; contaminated, so directional
  only). Smoke-tested end-to-end with random weights.

## Step 3b — neural-LOO gate (DONE, trm/certify.py; user-approved)
- Protocol: for a task with N train pairs, N folds; fold i uses the
  OTHER pairs as demos and pair i's input as query, requires EXACT
  match on pair i's output. All folds batched in one forward. Pass-all
  -> the test render is "neural-LOO gated".
- EPISTEMIC STATUS (must appear in the paper): weaker than the
  symbolic gate — weights are frozen, so folds test generalization
  across query slots, NOT re-derivation of the rule. Meaningless on
  training tasks (memorized). Precision is MEASURED on eval:
  `python trm/certify.py <ckpt> eval` -> gated count, gated precision,
  realtime per-task JSONL (trm/outputs/certify_eval.jsonl, resumable).
- Payoff: current attempt_2 partials run ~3% precision; gated TRM
  renders become a calibrated tier in the lattice at whatever
  precision the eval measurement shows.
- Smoke: random weights gate 0/5 eval tasks (correct).

## Step 3c — harness integration + packaging (AFTER first good ckpt)
- Harness: object_layer attempt_2 selection order = neural-LOO-gated
  TRM render, else best uncertified partial (fit >= threshold), else
  ungated TRM render.
- Kaggle: weights (~4MB fp16 at 1.8M params) added to the dataset
  tarball; notebook loads them offline; CPU inference fine for 240
  tasks.

## Per-epoch evaluation loop (the standing routine while training)
1. Monitor pings on "EPOCH k: loss L val_exact V/1000".
2. `python trm/infer.py` — sample-20 directional probe.
3. `python trm/certify.py trm/checkpoints/ema_only.pt eval` — gate
   census + measured precision on eval.
4. Record all three numbers in RUN_HISTORY + RESUME immediately.
5. Stop training on val_exact plateau; take best checkpoint forward.

## Honest framing for the paper
The hybrid demonstrates the graduated-certificate protocol at full
span: attempt_1 certified-symbolic (0.95 precision class), attempt_2
neural with a measured-precision neural-LOO tier and an explicitly
uncertified remainder. Eval-split scores from attempt_2 are reported
with their tier labels throughout; no neural render is ever counted
toward the certified solve rate.
