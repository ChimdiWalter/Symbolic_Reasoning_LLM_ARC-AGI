# Breakthrough literature sweep (2026-07-25) — for genuine ARC-AGI-2 reasoning
User directive: "something outside the box... look through literature...
genuinely a breakthrough of real reasoning model capable of solving arc agi".
10-area sweep; findings recorded as they land. Status: 3/10 streams in
(EBM/diffusion cluster); main synthesis pending.

## HEADLINE FINDINGS SO FAR (ranked by direct actionability)

### 1. DRM — Denoising Recursion Models (arXiv:2604.18839, 2026) ⭐ TOP
Hybrid looped transformer = OUR TRM + diffusion-style corruption.
- Sample corruption level tau, initialize y at the CORRUPTED TARGET,
  unroll k recursive refinement steps to recover the clean output.
- KEY RESULT: 14M params -> 24.9% ARC2-Eval (with NVARC data), BEATING
  a 4B baseline (22.6%). 7M -> 16.7%. ARC-Easy 55% at 14M.
- CRITICAL NEGATIVE: standard discrete diffusion WITHOUT recursion =
  ~0% on ARC even at 70M. Recursion is essential; our TRM already has
  it. Corruption-as-curriculum is the missing training signal.
- Cosine mask schedule; T=16 denoising steps at inference; k=6 loops.
- WHY THIS MATTERS FOR US: our run-1 autopsy showed the TRM learns
  grid statistics but not rule application. DRM's fix: train the model
  to REPAIR partially-corrupted correct answers (easy -> hard
  curriculum over corruption levels) instead of always generating from
  zero. This decomposes the hard task into learnable local repairs.

### 2. FactorDiff (arXiv:2607.11758, 2026) — per-pixel expert routing
- 1M-param models, 95.2% exact on ARC-AGI-1 (IID, RE-ARC augmented).
- Discrete masked diffusion; per-CELL routing to most-confident expert
  (margin between top-2 probs); ~zero routing overhead.
- github.com/markohuang/factordiff. Muon optimizer, 128 denoise steps,
  confidence-ordered decoding (easy cells committed first).

### 3. TTT — test-time training (arXiv:2411.07279, MIT) — proven ceiling
- Per-task LoRA + leave-one-out data gen + D4xcolor augments + voting.
- 8B model: 18.25% -> 47.1% pass@2 on ARC-1 public val (2.6x).
- BARC program synthesis + synthesizer + TTT = 61.875% (~human avg).
- NOTE: their leave-one-out data generation IS our LOO protocol used
  as a training signal — philosophical kinship with our gate.

### 4. MGDM (arXiv:2410.14157, ICLR'25) — subgoal-imbalance fix
- 6M params, 100% Sudoku (vs LLaMA-13B 32.9%); easy-first TopK
  decoding; token reweighting emphasizing hard positions.
- Evidence that parallel/global denoising >> autoregressive for grid
  constraint satisfaction at TINY scale.

### 5. Compositional energy minimization (Oarga & Du, NeurIPS'25)
- Train small energy MLPs per constraint TYPE, SUM them at test time;
  particle-based minimization (PEM). 8-Queens 97/100 trained on ONE
  instance. Composition without retraining = the symbolic engine's
  composability, in neural form.

### 6. Others recorded
- DDReasoner (2508.16524): masked DDPM + RL constraint reward; Sudoku
  97.8%, mazes 100% at 5.3M params.
- Energy discrepancy on discrete spaces (NeurIPS'24, 2412.01019):
  trains discrete EBMs with NO MCMC (heat-equation perturbations).
- IREM/IRED (Du et al.): reasoning as energy minimization; adaptive
  compute per difficulty; size generalization 10->30 graphs.
- Tree diffusion (2405.20519): grammar-constrained program denoising
  with execute-and-observe loop; value-guided beam search.
- Kona (Logical Intelligence, 200M): energy-landscape reasoner, 96.2%
  Sudoku in 313ms; spatial >> language reasoning.
- Trelis pure discrete diffusion on ARC: 17.5% ARC-1 at 10M — confirms
  diffusion ALONE insufficient (matches DRM's negative).
- Loop-OWM (2606.12316): slot-based composable world models for ARC,
  looped transitions; outperforms baselines on ARC-1+2.
- EnergyARC (github hummosa): EBM+Langevin+RL on ARC (incomplete).

## EMERGING DESIGN IMPLICATION FOR OUR ARCHITECTURE
The convergent evidence (DRM negative result, MGDM, FactorDiff, DRM
scaling) says: tiny models CAN do ARC-grade reasoning when the
training objective is ITERATIVE REPAIR of corrupted solutions rather
than one-shot generation, and when decoding commits easy decisions
first. Our TRM has the recursion machinery but the wrong objective
(always-from-zero generation). The minimal high-value pivot:
  TRM-DRM hybrid: keep our model, change training to (a) corrupt the
  target y_emb at sampled noise level tau, (b) recursively denoise,
  (c) deep supervision at each step, (d) inference = T=16 steps from
  full mask with confidence-ordered commitment.
This is a TRAINING-OBJECTIVE change, not an architecture rewrite:
reuses dataset, model, harness, certify gate unchanged.

## MAIN SYNTHESIS (all 10 areas, landed 2026-07-25)

### ARC Prize 2025 landscape (verified numbers)
- NVARC (1st, 24% ARC-2): Qwen-2-VL 4B + TRM ensemble, 260K synthetic
  puzzles, TTT. ARChitects (2nd, 16.5%): LLaDA-8B masked-diffusion LM,
  2D RoPE, recursive soft-mask refinement. TRM (paper prize, 45%
  ARC-1/8% ARC-2, 7M). CompressARC (3rd paper, 20% ARC-1, 76K params,
  ZERO pretraining, MDL by gradient descent). ARC-VSA (runner-up,
  10.8% ARC-1; 83.1% 1D-ARC beating GPT-4).
- Post-competition: frontier API ~85% ARC-1 (GPT-5.5); NL program
  evolution 79.6% ARC-1 / 29.4% ARC-2 (Berman/Grok-4).
- Meta-theme of 2025: THE REFINEMENT LOOP — per-task iterative
  optimization in some representation space.

### Agent's ranked top-3 for OUR hybrid
1. **AlphaProof-style guided search over our DSL + per-task TTRL**:
   small policy+value net (~5M) guiding search over program space;
   our LOO gate is a PERFECT VERIFIER = "RL dream scenario"; expert
   iteration (solved tasks -> retrain policy -> more solved). The ARC
   Prize organizers' own "most promising untried" pick.
2. **Enhanced CompressARC** (MDL + attention + iteration blocks):
   76K params, zero pretraining => ZERO distribution shift on hidden
   eval (why pretrained approaches drop 2-3x on ARC-2). Failures are
   architectural (no counting/iteration), fixable.
3. **NCA-symbolic hybrid with MDL routing**: neural cellular automata
   (~10K params) solve the local-growth/fill/morphology class 13-17%;
   complementary to symbolic search; MDL arbitrates.

### Meta-insight
Portfolio of complementary refinement loops in different
representation spaces (symbolic programs / neural weights / NCA local
rules), arbitrated by MDL (shortest description wins). Compression-
based arbitration between reasoning strategies.

### Cross-cutting evidence for tiny-model reasoning
- MLC meta-learning: 5.7M transformer 78.26% on compositional
  generalization vs o3-mini 0.53% — small meta-learned >> huge LLM.
- Predictive coding formally = MDL (2025 proof) — unifies the
  neuroscience stream with CompressARC's objective.
- MGDM 6M = 100% Sudoku; DRM 14M = 24.9% ARC2-Eval > 4B baseline.

## DECISION RECORD (pending user confirmation of priority order)
Three integration plays, all compatible with the standing constraints
(no LLM, no task-specific code, LOO gate = only blocking gate):
- PLAY A (cheap, now): retrain our TRM with the DRM corruption
  objective — training-objective change only; reuses everything.
- PLAY B (the deep play): policy+value-guided program search with
  expert iteration on the certified engine (attempt_1 coverage
  expansion with the gate as verifier).
- PLAY C (hidden-eval hedge): CompressARC-style per-task MDL
  compression as attempt_2 alternative; zero pretraining = robust to
  distribution shift; MDL arbitration between renders.

## DEEP-DIVE: DreamCoder / library learning (for PLAY B design)
- Recognition model (their ARC variant): fully-conv + dilated convs,
  variable 1x1-30x30 grids, per-grid 64x3x3 maps, DIFFERENCE feature
  M(out)-M(in), 256-d vector -> GrammarNet that RE-WEIGHTS primitive
  probabilities per task (amortized inference; ~10x search speedup;
  "recognition model alone nearly doubles solved tasks").
- HELMHOLTZ DREAMING (key for us): sample fantasy programs from OWN
  grammar, render on random inputs -> unlimited synthetic (task,
  program) pairs to train the guide. NO LLM NEEDED — fully compliant
  with our constraints. Our program families ARE the grammar.
- Their ARC numbers: PeARL 77 primitives, 70/400 easy 18/400 hard,
  single wake-sleep cycle, 1 CPU-h/task; false-positive rate 1.25%
  (vs our gate's ~5%); class-1 failures = DSL gaps (copy-paste).
- Stitch (POPL'23): library compression 1000-10000x faster than
  DreamCoder's; our D15 promotion machinery is the same idea.
- Induction+transduction (Ellis, ICLR'25 best paper): same model,
  different objectives solve DISJOINT task sets (37% overlap only);
  ensemble 56.75% public val. Confirms our attempt_1/attempt_2 split
  is the right shape.
- PLAY B CONCRETE RECIPE: (1) dream synthetic tasks from our object/
  reduction/framed families; (2) train a small conv guide to predict
  which family/action/selector will certify, from grid-difference
  features; (3) use its output to ORDER our existing induction search
  (variant choice, delta hypotheses, budget allocation); (4) expert
  iteration: each new certified solve joins the training set. LOO
  gate stays the only acceptance path (guide only orders search).
