# The Generative Ladder — plan of record (2026-08-05)

User-approved plan covering the post-R17 arc: scale verdict, vocabulary
v3, the generator-mining loop (the ladder-downward experiment), the
composition multiplier, and the eval/paper/Kaggle closes. Each stage
has an acceptance criterion and a records rule (update RUN_HISTORY +
RESUME + memory at every milestone — standing directive).

## Context (sealed facts this plan builds on)
- R17 delivered the FIRST certified generative program (178fcbfb,
  LOO 3/3): GenerativeProgram = per-input-object generators, pixel-
  composite verification, NO object correspondence. Gate unchanged.
- Diagnosis chain that produced it (the method): dormant create-verbs
  -> upstream census (83% matching deaths, 85/89 "fixable") ->
  coherence fixes (mechanism proven, zero yield) -> fused-output trace
  (correspondence is the wrong paradigm for draw/extend tasks) -> new
  induction path -> vocabulary gap -> vocabulary v2 -> solve.
- Near-misses recorded: 05a7bcf2 (ray-through-obstacle with color
  absorption), 23581191 (cross-line intersection color).
- Suite 456 green; probe 1/35; dev-19 9/8; s30 4/4.

## Stage 0 — v19 scale verdict (RUNNING)
Full 1000-task chain, ARC_GENERATIVE=1 + ARC_DIHEDRAL_FRAMES=45,
library-seeded -> outputs/unified_harness_v19_generative/.
- Acceptance: solved-set vs v17 (173) after standard contention-flake
  arbitration (solo retries of known flakes; OFF-control any loss).
- Any regression traced to the generative path (not flakes) = STOP and
  diagnose before further stages (less-is-more discipline).

## Stage 1 — R17b: vocabulary v3 hand-additions (cheap, 1 session)
Add to generative.py: (a) ray_until_obstacle with COLOR ABSORPTION
(ray takes the color of the obstacle it stops at / passes through —
05a7bcf2 semantics); (b) cross_line INTERSECTION COLOR (cells where
two generated lines cross take an induced color — 23581191);
(c) any additional mode a failed-composite trace on the remaining 33
fused tasks justifies (trace-first rule: never add a mode without an
exemplar trace naming it).
- Acceptance: 05a7bcf2 AND 23581191 produce train-perfect candidates;
  probe rerun on the 35-task fused class; gates dev-19/s30 zero
  regressions; suite green.
- IMPORTANT: keep a ledger of exactly what was hand-added and from
  which exemplar trace — Stage 2's rediscovery experiment needs it as
  ground truth.

## Stage 2 — R18: the generator-mining loop (the ladder experiment)
The paper's open problem made concrete: machine-INVENTED generative
primitives under the falsifiability gate. Reuses M2/M3b/M4 scaffolding.
1. Residual-paint mining substrate: for every fused-signature task
   where the composite path fails, persist (expected - best_composite)
   residual cells + emitting-object features (the analogue of the
   near-solve store, one level down).
2. Generator hypothesis language (the NEW hand-authored layer, one
   level more primitive than generators): parameterized cell-set
   functions = directional walks x stopping predicates (border, first
   non-bg, first cell of color C, N steps) x color rules (source
   color, obstacle color, induced constant) x thickness/branching.
3. Mining: cluster residuals across tasks by geometric relation to
   source objects; fit hypothesis-language expressions per cluster.
4. Admission = M3b delta-level LOO verbatim: a mined generator must
   reproduce held-out residuals EXACTLY on pairs it never saw;
   M4-style law curation for entry into the composite vocabulary.
5. Dreamability: admitted generators join guide/dream.py's grammar.
- Acceptance experiment (E10, the headline): REMOVE the Stage-1
  hand-added modes from the vocabulary, run the miner blind, and
  measure whether it REDISCOVERS them (ray-until-obstacle-with-
  absorption etc.) from residual data alone + whether rediscovered
  versions re-certify the same tasks. Machine-invented generative
  primitives with certificates = unprecedented per the literature
  sweep (DreamCoder invents compositions of GIVEN primitives; this
  invents primitives).
- Honest framing: the hypothesis language remains hand-authored; the
  ladder moves the hand one level down, never to zero — paper states
  this plainly (it already frames the ladder this way).

## Stage 3 — composition re-test (the multiplier)
Generative programs are the residual-explainers composition was
starved of. Re-run the composition probe set + phase-B traces with
ARC_GENERATIVE on: can stage-1 object programs + generative patches
reach train-perfect where each alone cannot?
- Acceptance: any certified depth-2 program with a generative
  component (first ever); else record the specific residual class
  that still blocks and STOP composing (round-2/v4 lesson: don't
  chase composition without expressible residuals).

## Stage 4 — E3 eval re-run + paper + Kaggle close
- E3 frozen-transfer re-run on ARC eval split with the final flag set
  (generative on): the honest number that replaces "~0/120".
- Paper: E8 gains the R14->R17 onion ledger; new E10 if Stage 2 runs;
  scripts/paper_tables.py regenerated; then LaTeX for venue.
- Kaggle: rebuild tarball from the sealed best version (v19+),
  attempt_1 certified / attempt_2 best-partial policy unchanged;
  user's upload clicks.

## Standing rules for every stage
Engine rules a-f apply unchanged. All new machinery env-gated,
default-off until its round seals. Zero-yield => default-off, kept,
recorded (less-is-more). All long runs detached via setsid + log
files + completion markers. Records at every milestone, never
batched. LOO-by-reinduction remains the only acceptance path.

## STATUS STAMPS (updated 2026-08-09)
- Stage 0: COMPLETE — v19 SEALED 174/1000 (RUN_HISTORY 2026-08-07).
- Stage 1: COMPLETE — R17b sealed; +23581191; ledger written
  (docs/R17B_HAND_ADDED_LEDGER.md); 05a7bcf2 structural gaps deferred.
- Stage 2: COMPLETE — R18 sealed; E10 SUCCEEDS (cross_line +
  intersection_color reinvented blind; 23581191 re-certified by mined
  generators; ray_through_absorbed = honest negative naming the next
  rung: relational per-pair direction). Paper E10 section written.
- Stage 3: NEXT — composition re-test.
- Stage 4: pending — full chain (175 claim), E3 eval re-run, paper
  tables/LaTeX, Kaggle rebuild.
