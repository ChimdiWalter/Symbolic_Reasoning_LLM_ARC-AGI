# ncv2-g4: Representation-Aware Neural-CORA (proposal, 21 October 2026)

**Status:** a proposal. Nothing is built, trained or scored, and no novelty is claimed until the architecture is
specified and tested. Native CORA and every frozen version (ncv2-g1, ncv2-g2, ncv2-g3) stay unchanged; g4 would live
in a new package, `cora_neural_v2g4/`.

## 1. The question

Can CORA recognize that its present description of a problem is insufficient, construct a better representation,
and use it to discover an executable explanation that was previously unreachable?

## 2. Why representation, from the evidence

From the finished real-ARC cohort (descriptive; `records/NEURAL_CORA_G4_REALARC_FAILURE_ANALYSIS_20261021.md`):
- In 37 of 40 tasks, every group of changing objects is picked exactly by an existing selector. *Which* objects change
  is rarely the problem.
- In 13 tasks the changed objects change only in part, and no segmentation view helps: the change lives below the
  object. Six of them also show grouping.
- In 7 tasks the change is additive, mostly line extension.
- In 12 tasks whole objects change and (in 10) every group is selectable, but no rule was found: an action,
  parameter, composition or search gap.
- 38 of 40 tasks had no correct candidate. Better ranking alone cannot help them.

These are heuristics on an exposed cohort. They justify an investigation, not a claim that these tasks need a new
representation.

## 3. Representation as part of the hypothesis

**A representation** R is:
- a parse: which cells form units;
- the units' features and relations;
- the parent / child / group links between units.

**A hypothesis** is a pair (R, P): a program P over R's units, executed and checked on every demonstration.

**Parses** (each must be derivable from the demonstrations' evidence, not chosen blind):

| family | units | example evidence that proposes it |
|---|---|---|
| native views | the 7 segmentation views (kept as they are) | — |
| components | per-colour parts of multicolour objects; border vs interior; line endpoints; holes | changed cells form a strict part of objects (section 2) |
| groups | adjacency clusters; row or column bands; enclosures; same-shape sets | an output object spans several input objects |
| regions | background regions: holes, enclosed areas, gaps between objects (negative space) | added cells fill an enclosed region |

**Execution.** Native's interpreter runs programs over its own views. A program over derived units runs in one of
two ways:
- (a) compiled onto native constructs where one exists (regions, crops, part copies, colour-layer views);
- (b) through a thin g4 layer that runs the native program on each unit's masked sub-grid and writes the result back.

Option (b) is a new interpreter layer. It must match native exactly whenever the derived parse equals a native view
(parity tests, as for ncv2-g1).

**The test of a representation change:** it must change which hypotheses CORA can construct or execute. Adding one
more hand-designed segmentation view does not count as a contribution on its own. The contribution would be the
evidence-driven proposal of parses, joint choice of representation and program, and feedback-driven change of
representation.

## 4. Mechanisms

| # | mechanism | what it does |
|---|---|---|
| C1 | alternative parses | keeps several parses alive per task, each proposed by an evidence test (table above), each with its own scene and change groups |
| C2 | grouping | proposes group units when outputs span inputs or change groups cluster spatially; group-level selectors and actions |
| C3 | splitting | proposes component units when changes are part-level; part predicates (border, interior, colour component, largest part, endpoint) |
| C4 | regions and negative space | background regions as units, for filling and completion |
| C5 | additive transformations | line extension (rays with stop and colour rules), completion (symmetry, pattern continuation), copying to observed targets, growth, region filling, each with parameters derived from the observed added cells |
| C6 | joint (R, P) hypotheses | ncv2-g3's joint construction run per representation; the representation is chosen with the program by execution and description length, never fixed up front |
| C7 | feedback-driven representation edits | the revision controller gains representation actions (split a unit, merge units, switch parse, add a region unit), triggered by its mismatch diagnosis, e.g. wrong cells forming a strict part of an object → split that object |

**Measuring genuinely new coverage:** count correct candidates that become constructible or executable only under
a new representation. Separately count those that more search reaches (the old representation at 3× budget) or new
operations reach (C5 operations without new parses). Only the first count is a representation effect.

## 5. Remedies for the known gaps

This section merges an independent, read-only remedy review (21 October) with the analysis.

**Grounding** (checked in code):
- **Native already has the missing pieces:** `!=`, `<`, `>` and rank tests, and `exists` over all 12 relations
  (`expressions._single_tests`); a growth detector (`growth.detect_grow`: rays, halos, fills, symmetric growth); typed
  per-object deltas (`correspondence.extract_deltas`); zero-conflict parameter fitting (`inducer._action_fits`).
- **ncv2 exposes only part of it:** `==` tests, `exists` over 3 relations with colour tests, no GROW, no `scaled` or
  `!=` generator, and only 3 of the scene's 5 fates are tied to actions.
- **Constraint:** native and the frozen versions stay unchanged. Where the review proposes a new native operation,
  g4 either (i) builds native program dicts from existing native operations and lets native run them, or (ii) uses the
  thin g4 layer of section 3, checked for parity.

| gap (tasks) | remedies, most value per effort first | needs |
|---|---|---|
| whole-object change, no rule found (12) | **group inversion:** for each exactly selected change group, keep only the parameter expressions (colour, vector including `scaled dir (feature f)`, reference) whose native evaluation equals every member's observed delta in every demonstration; probe those first, then let joint construction compose the groups. Also: native per-object deltas as fates; a local forward check of every pooled action on the group's members only | existing operations |
| generator gaps (2) | **selector induction** over native's full predicate grammar (`!=`, `<`, `>`, ranks over scalar, boolean and colour features; `exists` over all relations with boolean or colour inner tests; `and`), smallest zero-conflict predicate first; plus group inversion (finds `scaled up (feature size)`) | existing operations |
| no exact selector (3: `a8d7556c`, `df8cc377`, `dd2401ed`) | selector induction first; unions of separable subgroups that share one inverted action; only then new relational features (between, facing, aligned): *hand-designed, one family at a time* | existing, then new features |
| single wrong reading (2) | **rival generation:** every exact selector and every lifted literal (a constant replaced by an expression equal to it on every demonstration), deduplicated by prediction, so the two attempts can split between readings; **parameter leave-one-out:** re-derive parameters from each n−1 subset and demote readings whose parameters change | existing operations |
| line extension (7) | **GROW through `detect_grow`:** keep (mode, direction, length) shared across a group, lift colour and length literals, exclude `pattern`; built as native program dicts. **Ray-run parse:** split added cells into straight single-colour runs and record start cell, stop (border, obstacle, colour, length = feature), colour source and contact behaviour, by consensus; compile to an existing native form, else the g4 ray layer. **Composite emitters:** one rule that both changes an emitter in part and casts its ray | native GROW (not exposed in ncv2); the g4 layer as fallback |
| part-level change (13) | **cell-mask induction:** from each member's changed cells, induce the smallest zero-conflict cell predicate (border or interior, corner, halves, row or column within the bounding box, cell colour, adjacency to a colour or reference, inside a reference's band or box, `and`); executed by the g4 layer, since no native operation recolours a cell subset. **Induced grouping** (the 6 spanning tasks): link input objects that one output object overlaps, and find the relation whose components equal those links (*still a view, though its parameter is induced*). **Parts as objects:** *another hand-designed view; only if mask induction fails* | the g4 layer |
| search order (1) | **interleaved sizes:** replace ncv2-g2's two-first rule (which demotes single rules by 4 when two kinds of change appear) with a quota of at least a third of evaluations on single rules per view. **Geometry tier:** probe `(true)` × {reflect, rotate, scale} × views first (at most 63 programs) | existing operations |

**Build first** (the review's ranking, adopted):
1. the inversion engine (group inversion, selector induction, rival generation, parameter leave-one-out), which serves
   17 distinct tasks with existing operations only;
2. GROW through `detect_grow`;
3. cell-mask induction, which targets the largest class and is the one place existing operations cannot express.

The interleaved-sizes fix costs almost nothing.

**Measured the same way for every remedy:** on a fresh frozen real cohort and new synthetic families, ncv2-g3 plus
the remedy against ncv2-g3 unchanged, at equal candidate and CPU budgets, by stratum. Constructed candidates get a
capped share (about 30%) at the head of the agenda, and the unchanged agenda continues behind it, so nothing is
pruned.

## 6. The scientific test (to be frozen later; not run)

**Arms** (matched compute: equal candidate evaluations and the same process-CPU cap):

| arm | what changes | isolates |
|---|---|---|
| G2 | ncv2-g2, frozen | baseline |
| A | better program search, same representation (ncv2-g3 as frozen) | search |
| A+ops | A plus the C5 operations, no new parses | new operations |
| B | new parses (C1–C4), unchanged ncv2-g2 search order | representation alone |
| C | joint representation and program search with feedback-driven representation edits (C1–C7) | the full proposal |
| D | C with the same representation edits applied failure-blind (fixed order, ignoring the diagnosis), at equal compute | whether the feedback matters |

**Measures, in this order:**
1. correct-candidate coverage, retained and by a bounded exhaustive check;
2. new-coverage attribution (section 4);
3. pass@2, top-1, wrong attempts, gains and losses;
4. CPU and memory.

**Data:**
- **real:** a fresh eligible cohort, the next public training tasks after the finished one, under the same eligibility
  check, frozen before any run (development evidence, not unseen performance);
- **synthetic:** a new generator, syn-v4, with families for part-level change, grouping, additive change and negative
  space, split by semantics before augmentation.

**Never reused:** the v1 395, the ncv2-g2 200, syn-v3 (once run), the finished real cohort, and sealed or protected
data.

**Decision rule** (sketch, to be set before any run): a representation GO needs:
- C − A ≥ k on coverage on the fresh real cohort;
- B − A ≥ k′ (representation alone helps);
- C − D ≥ k″ (feedback helps);
- C − A+ops ≥ k‴ (not just the new operations);
- losses within a bound.

## 7. Qwen and learned revision

| what Qwen might propose | how it would be read | how CORA tests it |
|---|---|---|
| object groupings | "same unit" scores between pooled object slots | a group parse, executed and fitted |
| correspondences | input-to-output slot matching across a demonstration | change groups and fates, then rule construction |
| missing parts | cell-level completion masks from the re-read segment | a region or component unit, then additive operations |
| complete conditional rules | the structured decoder (docs/NEURAL_CORA_JOINT_RULE_PROPOSER_SPEC.md) | typecheck, compile, execute, fit |
| representation changes | split, merge or parse choices from slot states | C7 edits, executed and compared |

**Every proposal is untrusted evidence:** it becomes a candidate (R, P) and counts only if native execution fits it.

**Controls** that separate pretrained knowledge from hand-engineered search information:
- the same heads on hand features only;
- shuffled Qwen slots (another task's);
- untrained heads;
- Qwen on colour-permuted grids (does it rely on colour priors?);
- all at matched compute.

A Qwen contribution needs a win over the hand-feature arm on new tasks.

**Learned revision:** no causal claim without a matched experiment against failure-blind, shuffled-trace and
try-all controls (docs/NEURAL_CORA_REVISION_CONTROLLER_SPEC.md). No large neural experiment starts in this stage.

## 8. Resources (estimates, CPU only unless stated)

| step | estimate |
|---|---|
| the g4 representation layer (C1–C5), parity tests, unit tests | engineering; small CPU |
| fresh real cohort, 6 arms × about 40 tasks at 3,000 candidates | about 3–5 CPU-hours (ncv2-g3 measured 7–28 s per search on DEV) |
| syn-v4, about 300 tasks × 6 arms | about 8–10 CPU-hours |
| Qwen slot extraction (later, separately authorized) | about 0.3 s per task on GPU 0; head training a few GPU-hours |

All of it runs at 2 workers, nice 10, beside Step B (untouched).

## 9. Order of work

1. syn-v3, once authorized: does ncv2-g3's construction and selection help at all?
2. Build g4 in the order of section 5:
   - the inversion engine (existing native operations, 17 tasks);
   - GROW through `detect_grow` (7 tasks);
   - cell-mask induction in the g4 layer (13 tasks), with parity tests against native first;
   - a constructed head of single rules and the geometry tier, which replaces the two-first rule's effect.
3. Freeze the fresh-cohort protocol and syn-v4 with the arms above. Do not run them without authorization.
4. Only if symbolic g4 shows new coverage: Qwen proposals, under their own frozen protocol.
