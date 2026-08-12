# Ideas mined from TRM (2510.04871) + ARC Prize 2025 results — mapped to OUR architecture
(2026-07-17; sources: "Less is More: Recursive Reasoning with Tiny Networks",
arcprize.org/blog/arc-prize-2025-results-analysis)

## The landscape (calibration for our targets)
- Kaggle ARC-AGI-2 winners: NVARC 24.03% (synthetic-data ensembles +
  test-time training + TRM components), ARChitects 16.53% (2D masked
  diffusion + recursive self-refinement), MindsAI 12.64% (TTT pipelines +
  augmentation ensembles). Commercial: Opus 4.5 37.6%, Gemini3+Poetiq 54%.
- Paper prizes went to TRM (recursion, 7M params, 45% ARC-1 / 7.8% ARC-2)
  and CompressARC (MDL, 76K params, per-puzzle training, NO pretraining).
- HONEST CALIBRATION: no pure symbolic program-induction system has
  demonstrated 40%+ on ARC-AGI-2 eval. The 50/120 eval target requires
  either neural test-time components or a major unprecedented symbolic
  advance. The 2025 theme was "refinement loops: iteratively transforming
  programs through exploration and verification cycles" — our LOO gate IS
  a verification loop; we lack the iterative-refinement half.

## Idea 1 — DIHEDRAL/COLOR AUGMENTATION FOR INDUCTION (cheap, legal, ours)
TRM/MindsAI use ~1000 augmentations per task (dihedral transforms, color
permutations, translations). For US: augmentation is not training data —
it's SEARCH REFRAMING. For each task, run induction on the 8 dihedral
transforms (and canonical color relabeling) of the train pairs; a program
certified in ANY frame solves the task (transform test input in, invert
transform on the prediction out). Costs 8x budget worst case, gains tasks
where segmentation/correspondence align better in a rotated frame.
LEGALITY: pure geometry, no task-specific code, gate unchanged per frame.
STATUS: queued as the cheapest multiplier.

## Idea 2 — REFINEMENT LOOP AS ATTEMPT-2 (the 2025 theme, adapted)
TRM's core: draft an answer y, keep a latent z, iteratively improve
(z given x,y,z; then y given y,z), up to 16 supervised steps. Our analog
WITHOUT neural nets: take the best near-solve program (attempt_2 today =
its render), compute the residual on train pairs, search a REPAIR program
on the residual, apply, recompute, iterate K times. This is "iteratively
transforming programs through verification cycles" in symbolic form —
exactly our structured-composition roadmap item (#13) but framed as an
anytime refinement loop that always outputs its best current render for
attempt_2. Never touches attempt_1 certification.

## Idea 3 — DEEP SUPERVISION ANALOG = CUMULATIVE PER-TASK SEARCH STATE
TRM carries (y, z) across supervision steps: the answer AND the reasoning
state. Our induction restarts search per fold/phase from scratch. Analog:
carry the near-solve PARTIAL (explained rules) into phase B/C searches as
frozen prefix rules and only search the residual — the "z" is the partial
program. This makes composition cheaper and folds re-derive it because the
partial is itself re-induced per fold. (= structured composition, #13,
now with a principled framing.)

## Idea 4 — LESS IS MORE: PRUNE, DON'T GROW
TRM's most surprising result: 2 layers > 4 layers; single network > two;
removing machinery IMPROVED generalization (55.0 -> 87.4 on Sudoku).
We saw the identical phenomenon: reverting group-split GAINED a task
(12eac192). Lesson recorded as a RULE: every added search mechanism must
pay for its hypothesis-budget cost; prefer removing/pruning candidates to
adding them. Audit candidates: ranker (already known ~no-op), phase-B
forced composition (measure its hit rate), MAX_ACTION_CANDIDATES caps.

## Idea 5 — COMPRESSARC KINSHIP: MDL-PER-PUZZLE IS OUR LANE
CompressARC (paper 3rd): 76K params, trained per-puzzle, no pretraining,
pure MDL. Our canonical-MDL ranking + LOO gate is the symbolic sibling.
The PAPER story strengthens: cite TRM + CompressARC; position CSR/
certificates as the missing epistemic layer for BOTH neural and MDL
approaches (resample-consistency ≈ our reinduction gate for samplers —
already sketched in Related Work).

## Idea 6 — ENSEMBLE-OF-FRAMES, NOT ENSEMBLE-OF-MODELS
Winners ensemble augmented predictions by majority vote. Our certified
analog: when multiple frames (Idea 1) or multiple segmentation variants
independently certify programs for the same task, CROSS-CHECK their test
predictions; agreement is additional (measurable) evidence, disagreement
flags the rare certified-but-wrong cases (E1 says ~5%). Free precision.

## Idea 7 — OPTIONAL HYBRID TRACK (user decision required)
A TRM-like tiny recursive model (7M params, trained on ARC training set +
augmentations, no LLM, Kaggle-legal) as the ATTEMPT_2 GENERATOR only:
attempt_1 stays certified-symbolic (the novelty), attempt_2 becomes
TRM-render when no near-solve exists. This is how the eval number moves
per 2025 evidence (TRM alone: 7.8% ARC-2). Preserves the paper story
(graduated certificates: attempt_2 is explicitly uncertified). Cost: a
training-pipeline build + GPU budget. NOT started — needs user sign-off
since it adds a learned component to the submission.

## Priority order (score per unit effort, given our evidence)
1. Idea 1 dihedral-frame induction (multiplier on all 168 + families)
2. Idea 2 symbolic refinement loop for attempt_2 (+ measured best-of-2)
3. Idea 4 pruning audit (free score, proven by 12eac192)
4. Idea 3 partial-carrying composition (deep build, roadmap #13)
5. Idea 6 cross-frame agreement (precision, paper material)
6. Idea 7 hybrid TRM attempt_2 (biggest eval lever, needs user decision)
