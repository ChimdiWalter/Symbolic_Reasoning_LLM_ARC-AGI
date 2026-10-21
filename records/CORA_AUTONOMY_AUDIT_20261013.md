# CORA architectural autonomy audit (2026-10-13)

**First deliverable** of the author's directive "Architectural autonomy audit
and failure-driven representation growth".

- **Method.** A read-only code audit of the default native path, delegated;
  only this repository, no outputs, no answers. Load-bearing claims were
  re-checked by hand (marked *verified*).
- **Rule.** Implemented behaviour is judged from executed code. Docstrings
  and module names count for nothing.

## Answer

**On the default native path, CORA selects and recombines predefined
capabilities. It cannot create a new segmentation, perception operator or
action type at run time.**
- The one failure-driven construction mechanism, `cora_reach`, is
  research-only: imported only by `scripts/`.
- It chooses settings from a frozen grammar of 9 families and 210
  settings.
- It has never produced a certified real-ARC solve.

## Native path and flags

- **Path.** `scripts/run_unified_harness.py` →
  `harness/run_harness.py:65-214`. Three layers run per task:
  - pipeline: `reason_unified`, in submission mode;
  - geocat: not audited (UNCERTAIN);
  - object: `engine.py` → `inducer.induce_program`.
- **Sealed flags and where they act:**
  - `ARC_DIHEDRAL_FRAMES` (engine.py:188);
  - `ARC_GENERATIVE` (inducer.py:3426, 3768);
  - `ARC_PATTERN_DERIVE` (growth.py:57);
  - `ARC_RAY_EXT` (growth.py:354);
  - `ARC_VARIANT_BUDGET` (inducer.py:154).
- **Off natively:** CREATE_COHERENCE, OVERLAY, GEN_COMPOSE, ANALOGY,
  META_INDUCTION, GUIDE, RELIFT, GRADUATE, EXPR_GRAMMAR,
  TRANSFER_PROMOTION, LEARNED_GENERATORS_DIR.
- **No `cora_*` package** is imported by geocat_arc/, src/ or harness/.

## Capability verdicts

| # | capability | verdict | evidence |
|---|---|---|---|
| 1 | hard-coded representations | IMPLEMENTED-AND-ACTIVE | Seven segmenters, segmentation.py:167-240 (enum types.py:34-44): S1 same-colour 4-connected; S2 same-colour 8-connected; S3 multicolour 4-connected; S4 multicolour 8-connected; S5 same-colour 4-connected on the most frequent background; S6 one object per colour; S7 a 1-cell dilation then 8-connected. *Verified:* `segment()` returns `SEGMENTERS[variant](grid, background)` (segmentation.py:243-246). Other fixed families: 22 adaptive-reasoner lenses (adaptive_reasoner.py:243-266); grid decomposition (equal splits 2..7, separator splits, 6 sub-grid operators); 17 spatial-reasoner hypotheses; 15 pipeline layers (unified_reasoning_system.py:1277-1299); 7 dihedral frames; 13 GROW modes |
| 2 | dynamic selection per task | IMPLEMENTED-AND-ACTIVE | All 7 views are evaluated. A view is coherent if its count relation is consistent and coverage is at least 0.80 (segmentation.py:450-486). Fixed trial order; *verified:* `MAX_SEG_VARIANTS_TRIED = 4` (inducer.py:166). The variant-budget probe reorders within the kept four (inducer.py:2920-2970). Winner key at 3022-3024. Leave-one-out folds repeat the selection on fewer pairs |
| 3 | parameterized or composed | PARTIAL | The only segmentation parameter is the background (S5). Connectivity and S7's distance are constants. Composition: ComposedProgram re-segments stage outputs up to depth 3; FramedProgram; phase B/C re-searches |
| 4 | new grouping program at run time | **ABSENT** | No synthesis of segmentations. *Verified:* programs reload views by `SegmentationVariant(d["segmentation_variant"])` (types.py:648), which raises on an unknown value |
| 5 | new perception operator | **ABSENT** | Only parameter settings (S5 background, lens choice). Flagged GROW modes are predefined functions |
| 6 | executable operations | closed vocabulary | DeltaType has 19 members (types.py:63-113), dispatched at actions.py:761; 5 SYNTH_COPY combinators. cora_reach grammar (relations.py:131-141; frozen `GRAMMAR` at construct.py:26-27): 9 families, 210 settings. Research-only; nothing generates operations outside it |
| 7 | diagnosis controls change at run time | PARTIAL | Natively: fixed, failure-triggered escalations only (rule ablation, forced composition, phase C, generative fallback, dihedral frames). The pipeline's failure_diagnosis runs only in oracle mode (unified_reasoning_system.py:1527-1536). cora_diag is offline and reads recorded traces |
| 8 | persistence across tasks | PARTIAL | Within a run: process-local memories reorder layers, so the effect depends on order. Across runs: `library.json` (2 operators) and `learned_verbs.json` (1 verb) are read-only, frozen offline assets. *Verified:* the only writer, `promote_and_validate()` (engine.py:331), is never called by the harness (harness/object_layer.py:7) |
| 9 | causal evidence | see the next section | |
| 10 | intention only | listed below | |

## Recorded evidence of causal improvement

- **Real ARC (development, reach v1).** Of 60 tasks, 54 failed natively; 31
  had usable evidence; 4 proposals were installed; 1 was accepted with the
  extension; 0 were activated (0 of 14 outer folds passed adaptive
  leave-one-out). No real-ARC causal gain is recorded anywhere.
- **Synthetic.** v19 repair: 27 of 30 witnesses vs 12 of 30, within its
  declared grammar.
- **Negative.**
  - P3 rejected;
  - CORA-NVG H1 rejected;
  - diagnosis v0 is a consistency check (13 of 18) that "improves no
    reasoning outcome";
  - Kaggle native 0.00; 0 of 120 public evaluation; 185 of 1,000 training.

## Intention only

- **The failure-typed controller** (docs/CORA_FAILURE_TYPED_CONTROLLER_v0.md
  is design only), and DCC, which was not executed.
- **Not run:** reach v2, pilot v2, P2.
- **Never loaded:** learned generators.
- **Unused:** the "self-extending vocabulary" and the cumulative engine
  hooks, plus all the off flags.
- **Dead code:** `_structural_memory.store`; every success path returns
  before it.
- **UNCERTAIN:** the src invention modules are not on the path except for a
  lazy import whose reachability is uncertain. `meta_learner` depends on an
  outputs/ file that was not inspected.

## Autonomy levels

| level | definition | status | evidence |
|---|---|---|---|
| L0 | select a predefined representation | **DEMONSTRATED (real)** | coherence filter, trial order, cap of 4 |
| L1 | configure or combine predefined representations | **DEMONSTRATED (real)** | S5 background, composed stages, frames, phases B and C |
| L2 | synthesize a new executable representation expression from existing primitives | **PARTIAL** | typed synthesis of *transformation* programs exists; no synthesis of *segmentation or grouping* expressions |
| L3 | a new typed representational operator not expressible in the old language | **MISSING** | closed enum, the SEGMENTERS table, DeltaType |
| L4 | a new executable transformation capability after diagnosing a failure | **PARTIAL (research only), MISSING natively** | cora_reach picks 1 of 210 settings from failure evidence; 1 real acceptance, 0 certified; synthetic v19 27 of 30 |
| L5 | certify, retain and reuse a capability on future tasks | **PARTIAL** | frozen offline assets (2 operators, 1 verb) are reused; nothing is retained at run time; Step B is separate and untouched |

## Consequence for the next experiment

The decisive gap is **L2 for representations.** No mechanism synthesizes a
grouping or segmentation expression, let alone does so because a failure
indicated the representation language was insufficient. That is what
`cora_rep_growth/` will test (`records/CORA_REP_GROWTH_PLAN_20261013.md`).

**Claim ceiling, fixed now.** Anything such a constructor builds from a
predefined grammar is at most **L2 (composition)**. L3 would need operators
outside a declared grammar and a bounded-language absence test.

**Interface facts for a reversible overlay** (the audit's API notes):
- `segment(grid, variant, background=None)` dispatches through the shared
  `SEGMENTERS` dict.
- `evaluate_variant(variant, train_pairs)` never raises.
- `background_for` returns 0 except for S5.
- `_trial_index` is rebuilt from `inducer.SEGMENTATION_TRIAL_ORDER` at call
  time (inducer.py:2898; *verified*).
- Programs store `.value` and reload through the enum.
- So one constructed view can be injected by:
  1. registering a pseudo-member of the enum (value map only);
  2. adding a `SEGMENTERS` entry;
  3. prepending it to the trial order only for the duration of an induction
     call;
  4. restoring all three afterwards.
- This works in-process (direct `induce_program` calls), not through the
  spawn-based harness.
