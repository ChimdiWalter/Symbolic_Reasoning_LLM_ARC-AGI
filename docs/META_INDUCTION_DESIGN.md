# Vocabulary Meta-Induction (round 5+ flagship; binding design)

**Thesis:** the cumulative loop, lifted from operators to the LANGUAGE.
The system currently learns programs per task and operators across tasks;
its verbs (delta types) and nouns (selector features) are human-authored.
Meta-induction makes the system extend its own DSL from its failure corpus
— under the same certificates, with the same leak discipline.

## Why (evidence, 2026-07-11)

- Training plateau: 3 hand-authored-primitive rounds bought +1/0/0 solves.
- Eval cliff is a vocabulary cliff: 91/120 eval tasks die at
  matching/selector; median object fit 0.009; render-verified eval CSR 0.
- Selector census (training): failed groups are 20 separable-by-existing-
  feature + 7 by-conjunction, 0 vocab gaps -> on TRAINING the selector
  side is a SEARCH issue; on EVAL (census pending) the concepts are
  expected to be genuinely absent.
- Cross-task skeleton promotion had zero fuel at the PROGRAM level —
  recurrence lives lower, in residual PATTERNS.

## Legality constraints (from the composition-fuel leak analysis)

1. A learned primitive is a GENERIC parameterized transformation/predicate
   — never bound to a task, never carrying literals mined from a specific
   task's full train set into that task's folds.
2. Registration path = the D15 operator path: mined cross-task, validated
   by retro-solve THROUGH normal induction, slots re-filled per fold.
3. LOO folds see the same (frozen) vocabulary as the main search — the
   vocabulary is extended BETWEEN runs, never within a task.
4. Every learned primitive carries provenance (which failure clusters
   proposed it, which retro-solves validated it) in the library file.

## Pipeline (4 stages, each independently testable)

### M1 — Residual mining (data)
For every near-solve row across ALL runs/splits-with-training-pairs:
compute the residual account (unexplained deltas, lossy pixels, failed
group signatures, orphan shapes) in a NORMALIZED form: color-abstracted,
translation-normalized, size-bucketed. Output: a residual-pattern corpus
with per-pattern task lists. (scripts/mine_residual_patterns.py — first
cut below; measurement before machinery.)

### M2 — Primitive synthesis (search, not authorship)
For each recurring pattern (>= K distinct tasks), search for a GENERIC
explanation program in a bounded combinator space over EXISTING geometry
primitives (translate/reflect/rotate/scale/flood/ray/ring/mask ops +
arithmetic on object properties): a candidate VERB is a parameterized
cell-set transformer that zeroes the residual on >= K tasks' instances; a
candidate NOUN (feature) is a boolean/scalar program over the object+grid
that separates observed selector groups on >= K tasks. This is program
synthesis one level down — the primitives are FOUND, not written.

### M3 — Validation gate (same standards as D15)
A synthesized primitive registers only if:
- retro-solve: adding it lets full normal induction CERTIFY (LOO) at least
  R previously-unsolved tasks, zero regressions on a fixed probe set;
- parsimony: it is not expressible as a depth-<=2 composition of existing
  vocabulary (else it is a library operator, not a primitive);
- fold-safety: purely generic (no grid-size/color literals unless slotted).

### M4 — Re-run + re-calibrate
Vocabulary extension -> full gated run -> the calibrated-CSR table
re-measured (new primitives must not degrade class precisions) -> paper
E7: "the system extended its own language N times; each extension is
certificated and calibrated."

## Milestones

- M1 corpus + recurrence report (days) — GO/NO-GO: does any normalized
  residual pattern recur across >= 5 distinct tasks?
- M2 synthesizer for the top verb family + top noun family (1-2 weeks).
- M3/M4 first registered learned primitive end-to-end (the paper moment).

## Honest risks

- Recurrence may be too sparse at 1000 training tasks (like skeletons) —
  the GO/NO-GO exists for exactly this; mitigation is normalization
  aggressiveness (M1 knobs), not lowered validation standards.
- Synthesis space explosion — bounded combinators + recurrence-driven
  targeting only.

## M2 concrete verb specs (from the battery, 2026-07-12 — implement next)

Battery verdict over 166 orphan instances (outputs/meta_m2_orphan_battery.json):
none 112 / input_subshape 21 / line_between 11 / grid_motif 11 / scaled 5 /
pair_union 5 / bbox_outline 1.  Two verbs clear the K>=5 distinct-task bar
with clean semantics; both attach at the ORPHAN pass of extract_deltas
(before absorption), mirroring the ATTACH implementation pattern.

### Verb 1 — CONNECT (line_between; matches round-4 connector census)
Detection: orphan is a straight 1-wide segment; each END cell is 8-adjacent
to a DIFFERENT matched output object.  Delta: CONNECT attributed to the
lexicographically-first host's input object; raw params
{other_output_id, axis, color}; residual 0.
Action apply_connect(self): params target (RefExpr — induced normally:
nearest_object(PRED)/unique(PRED)...), color (ColorExpr — full grammar),
optional align.  Renderer: the orthogonal segment between the facing bbox
edges of self and target (deterministic: choose the axis where bboxes
overlap in projection; cells strictly between the objects).  Detection
must verify the RENDERED segment equals the orphan exactly (same standard
as GROW modes).
MDL/class: fully relational when target is a REF — the generalizing
spelling by construction.

### Verb 2 — EXTRACT_PART (input_subshape)
Detection: orphan mask == a subwindow of some input object's mask (colors
matching on the window).  Delta on the source object: COPY_PART, raw
params {window=(wr,wc,wh,ww) relative to source bbox, placement=(dr,dc)
relative to source}.
Action: params window (RegionExpr relative — needs a small RegionExpr
extension 'subwindow(REF)'-style or constant region + placement VecExpr
with the usual non-const-first ordering).  Constant-prone: expect the
lattice/gate to price it; value comes from tasks where window/placement
are relational (e.g. 'the top row', 'centered').
IMPLEMENTATION ORDER: CONNECT first (cleaner, relational-by-default),
EXTRACT_PART second, then re-run the battery to re-measure the 'none' 112.

### M3 for both: the standard chain (fresh round6_*/v10 names), dev gates,
battery re-measure, full run.  Register in RUN_HISTORY like every round.

## M3b — Delta-level LOO certificates (round 9, lever 2)

Task-level registration (M3) starves correct verbs on multi-blocker tasks:
the verb types the residual, the task still fails elsewhere, credit = 0.
M3b applies the same epistemic standard one level down.

**Certificate.** For a candidate verb V and task T: instances = per train
pair, (source object, orphan) where apply_verb_chain(V, norm(src)) ==
norm(orphan). Delta-LOO: for each fold (hold out one instance pair),
re-fit a placement law from the remaining pairs; the fold passes iff the
law predicts the held-out orphan's exact absolute cells. T delta-certifies
iff every fold passes (>=2 instance pairs). V registers iff >= K_DELTA=2
distinct tasks delta-certify AND the dev-probe regression is clean.

**Placement-law catalog** (fixed, generic; scripts/meta_m3_delta_certificates.py):
const_offset, grid_mirror_h/v, touch, reflect_line (reflection across the
nearest adjacent axis-aligned line OBJECT — relational: the marker sets
side+distance per pair), bounce_gap (mirrored copy at constant gap on the
side away from the nearest grid edge — relational side). Catalog
provenance: 4 laws authored a priori; reflect_line and bounce_gap added
after inspecting the two foldable mined tasks (the next automation level
would search law space too — recorded as future work honestly).

**Legality.** certificate="delta_loo_exact" gates only vocabulary
AVAILABILITY (engine loads the verb; SYNTH_COPY becomes detectable).
Task-level LOO-by-reinduction remains the ONLY acceptance path, so a
registered verb can extend reach but never create a false solve.

**First registration (2026-07-13).** verb_mirror_h: dc2e9a9d 3/3 folds
(bounce_gap), 7ed72f31 2/2 (reflect_line), probe clean. mirror_v: 1 task
< K_DELTA, refused. Registry: outputs/learned_verbs/learned_verbs.json.

## M4 — Machine-curated placement laws (round 9, "level 3")

Closes the rung M3b left human: the placement-law CATALOG itself.

**The automation ladder** (each rung moves content from human to machine;
the certificate never moves):
  L0 fixed core: LOO-by-reinduction certificate + generic primitives
  L1 verbs: mined by combinator search, registered under delta-LOO (M2/M3b)
  L2 placement laws: human-authored catalog validates verb instances (M3b)
  L3 laws mined from a generic LAW GRAMMAR, admitted under the same
     delta-LOO standard (M4) — human contribution shrinks to the grammar
  L4 (future) the expression grammar itself

**Law grammar** (scripts/meta_m4_law_miner.py):
  law := place(transform(src), reference, side, gap)
  reference in {src_bbox_edge, nearest_line_marker, grid_center}
  side in {after, before, away_from_nearest_edge} (relational side legal)
  gap in {0..3} constant
plus translation laws (const_offset, touch). ~50 concrete candidates.

**Admission standard**: a law joins the catalog iff it delta-LOO-certifies
(all folds exact, law re-fit from N-1 pairs) on >= K_LAW=2 distinct tasks
of the verb-instance corpus. Same epistemics as verb registration; a law
can never create a false solve (task-level gate unchanged).

**Output**: outputs/learned_laws.json with per-law certified-task
provenance; the M3b registration script consumes the admitted catalog so
verb registration runs against machine-curated laws end-to-end.
