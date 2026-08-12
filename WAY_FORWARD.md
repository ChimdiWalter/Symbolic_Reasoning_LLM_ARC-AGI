# Way Forward: From Solver Collections to a True Reasoning System

Date: 2026-07-02. Evidence: fresh runs on this cluster (`outputs/failure_landscape_2026_07_02.json`,
`outputs/object_level_opportunity_2026_07_02.json`) plus deep architecture reads of both systems.

## 1. Where every system actually stands

| System | Valid solves | What actually produces them |
|---|---|---|
| Unified pipeline (86K lines) | 102/1000 | adaptive_synthesizer 69 (≈30 hand-coded primitives, depth-2, delta-routed), meta_reasoning 19, loo_replace 10, rest 4 |
| GeoCat-ARC (8.9K lines) | 72 train / 63 effective | structural_inference 26 (96% gen), cell-level rule induction ~31 (LOO-gated), grid solvers ~6 |
| Union | **123/1000** | 51 overlap; 51 pipeline-only; 21 GeoCat-only |

Hard truths established by the code reads:

- **Oracle 293 is not latent capability.** `unified_reasoning_system.py` `_diagnose_and_correct()` sets
  `diag_pairs = test outputs` when available — corrections are fit to the test set. The 171
  iteration-2 oracle solves are test leakage, not reasoning headroom.
- **All 102 pipeline solves are iteration-1.** Correction, accumulation, insight memory, cortical
  voting, feature binding, metacognitive accept: zero contribution. Structural reason: the correction
  engine diagnoses residuals, but every accepted base program is already train-perfect, so in
  submission mode there is nothing to diagnose.
- **~5K of 86K lines are load-bearing.** adaptive_synthesizer, delta_engine, meta_reasoning's
  `_discover_*` generators, the orchestration loop, and a few solvers. The rest (falsifier, manifold
  memory, certificates, operator genesis, neural abstraction, concept grammar...) never touches the
  solve path.
- **GeoCat's biggest asset is disconnected.** `geocat_arc/perception/` implements `ARCObject`
  (cells, bbox, centroid, shape signature, holes), relation graphs (left_of/contains/adjacent/
  same_shape), object matching, and change detection — and `reasoning_engine.py` imports none of it.
  Same for `categorical_dsl/` (typed Segment/Select/Filter/Translate/Recolor/Render programs with
  type checking) and `bayesian_program_search/`: fully built, never wired to the solver.
- **What genuinely works and must be kept:** GeoCat's LOO-by-reinduction harness (85% gen on rules,
  96% on structural inference) and the pipeline's delta-guided routing. These are the two proven
  generalization mechanisms in the whole project.

## 2. The failure landscape (877 unsolved, measured today)

| Category | Unsolved | Notes |
|---|---|---|
| Same-shape edits (sparse/moderate/heavy) | **599** | 68% of all unsolved |
| Shrink (output smaller) | 196 | mostly "select the right object/subgrid" |
| Grow (output larger) | 74 | tiling / stamping / construction |
| Mixed shape change | 8 | |

Object-granularity classification of the 599 same-shape unsolved tasks:

| Class | Tasks | Meaning |
|---|---|---|
| object_motion_or_copy | 147 | output objects = input objects, moved/copied |
| object_recolor_or_delete | 53 | same cells, colors change / objects vanish |
| mostly_preserved_some_new | 161 | ≥2/3 of output objects are preserved input shapes |
| **Object-level tractable total** | **409** | |
| object_new_shapes | 214 | drawing / completion / line growth |
| too_many_objects / other | 24 | |

**The single decisive fact: 409 unsolved tasks are object-preserving transformations** — exactly the
class neither system can even *represent*: GeoCat's rules are per-cell functions (`InducedRule.apply`
iterates cells independently — no object identity, no motion); the pipeline's primitives are whole-grid
ops. "Move each object to touch the nearest wall," "recolor the largest object with the color of the
object it contains" — inexpressible in both hypothesis spaces. Add the 196 shrink tasks (object
*selection* by learned predicate) and the object layer addresses ~600 of 877 failures.

## 3. What "true reasoning" means here, operationally

Not more solvers. A reasoning system = (a) an explicit compositional hypothesis space over the right
abstractions, (b) induction that *learns* which hypothesis fits from examples, (c) a validation gate
that certifies generalization, (d) guidance that improves with experience. GeoCat already proves
(b)+(c) work at cell level. The missing abstraction is (a) at **object level**. Every component needed
already exists in this repo, unwired.

## 4. Staged plan

### Stage 0 — Consolidate to one honest harness (days)
- One evaluation entrypoint, submission-mode only; oracle mode kept solely as a clearly-labeled
  diagnostic. One `SynthesizedOperator` interface; GeoCat solvers wrapped as layers → verified 123
  baseline in one results.json format.
- Quarantine dead weight from the solve path (correction loop lines ~1506-1580, insight/structural
  memory, cortical voting/binding/metacognitive paths) — they cost time and prove nothing.

### Stage 1 — The object layer (weeks; targets the 409 + 196)
Wire `perception/` into a new inducer, reusing GeoCat's induction+LOO pattern at object granularity:
1. **Parse**: `extract_objects()` per grid (4- and 8-connectivity, plus multicolor variants).
2. **Correspond**: `match_objects()` input↔output per train pair → each matched pair yields a typed
   **object delta**: translate(dr,dc) | recolor(c→c') | copy(k×) | delete | scale | rotate/reflect.
3. **Induce selector→action rules**: which object *property* (size rank, color, shape signature,
   hole count) or *relation* (nearest-to, contained-in, aligned-with, unique-among) predicts each
   object's action. Same zero-conflict induction + fuzzy fallback + **LOO-by-reinduction** as
   `rule_inducer.py`, over object features instead of cell contexts.
4. **Represent as programs**: emit into `categorical_dsl` (Segment → Select/Filter → action → Render),
   so every solve is an inspectable, typed program — not a closure.
5. **Shrink tasks**: same machinery, program shape `Segment → Select(learned predicate) → Crop/Render`.

Expected: even 25-35% of the 409+196 ⇒ **+150-200 valid solves** (system at ~270-320/1000), each one
LOO-certified.

### Stage 2 — Compositional search, not first-match-wins (weeks)
- Depth-3 typed program search over {structural ops + object ops + cell rules} with candidate
  *ranking* (train fit + LOO margin + program length), replacing first-match early exit.
- `bayesian_program_search/` (already built: features, posterior ranker, UCB/EI acquisition) becomes
  the search guide — its first real job.
- This is also where the 214 `object_new_shapes` tasks (draw/extend/complete) become reachable via
  composition: select anchor objects → generate strokes/completions relative to them.

### Stage 3 — Learning that accumulates (research phase)
Only after Stages 1-2 prove the representation (all past evidence: learning bolted onto a weak
hypothesis space contributes zero):
- **Library learning**: mine solved programs for recurring typed sub-programs → promote to named
  operators (this finally gives `operator_invention/` an executable target: synthesize `apply_fn`
  as a DSL sub-program, not a metadata dict).
- **Learned proposal distribution**: train the ranker on (task delta features → which program families
  solved similar tasks) from the growing solved corpus; neural ranker scaffolding already exists.
- Cross-task transfer then has a medium that can transfer: typed program fragments, not memorized
  lookup tables.

## 5. What to stop doing
- No new theory infrastructure until it produces ≥1 measured solve.
- No oracle-mode numbers in any claim without the "test-leakage" label.
- No new standalone systems — one harness, one hypothesis space, extensions as typed operators.

## 6. Success metrics
- Milestone A (Stage 0): 123/1000 reproduced under a single harness.
- Milestone B (Stage 1): ≥200/1000 submission-valid, ≥80% LOO generalization maintained.
- Milestone C (Stage 2): ≥270/1000, mean accepted-program depth > 1.5 (evidence of composition).
- Milestone D (Stage 3): solve-rate on later tasks measurably higher with library than without
  (the actual "cumulative reasoning" claim, finally testable).
