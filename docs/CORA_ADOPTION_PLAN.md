# CORA Adoption Plan (from The_system_I_would_build.txt)

Date: 2026-08-18. Source: `The_system_I_would_build.txt` (CORA: Certified Ontology-Repairing
Architecture + Near-Solve Compiler + Verified Conceptual Self-Extension). This plan maps every
idea in that document to a disposition (ADOPT-NOW / ADOPT-LATER / ALREADY-HAVE / REJECT) and a
staged build order. Standing protocol applies to every stage: trace-first, env-gated, LOO gate
is the only acceptance path, OFF-controls for search-allocation changes, realtime records.

## Verdict on the document

Accurate about us. Its diagnosis matches our own censuses independently: 194/269 near-solves
blocked by literal/extensional parameters, 75 outside delta vocabulary, E10 rediscovery limits,
R2/analogy zero-yield, fuel-starved composition. Its central claim: the system invents values
inside a human-supplied representation and must learn representations/relations/roles jointly -
is the same conclusion as `docs/V22_CENSUS_CANDIDATES.md` ("expression grammar is the key to
>200"), generalized one level up.

## Idea-by-idea disposition

| # | CORA idea | Disposition | Notes |
|---|-----------|-------------|-------|
| 1 | Near-Solve Compiler: semantic deltas, NS-0..NS-5 ladder, counterfactual repair, cross-task clustering | **ADOPT-NOW (Stage A)** | Analysis-only over existing artifacts; the doc itself says do this BEFORE any big architecture. Produces the failure-family table that dictates the next language primitives. |
| 2 | Independent-transfer promotion (concept from A,B,C accepted only after solving unseen D) | **ADOPT-NOW (Stage B)** | Cheap retrofit to promote_and_validate; upgrades the paper claim from rediscovery to forward transfer. |
| 3 | Certificate vector: metamorphic/intervention tests (D4, color-perm, applied only when candidate semantics claim the invariance) | **ADOPT-NOW (Stage C)** | Directly targets our documented degenerate-geometry false-positive class (M3b). Output-only LOO cannot catch wrong-mechanism passes; interventions can. |
| 4 | Semantic fold stability (canonicalize fold programs; require same mechanism, not same syntax) | ADOPT-LATER (Stage C2) | Needs program canonicalizer/anti-unifier; build after Stage A shows which AST fragments matter. |
| 5 | Version space + principled attempt_2 (second attempt from strongest semantically DIFFERENT equivalence class) | ADOPT-LATER (Stage D) | Kaggle-relevant (2 attempts allowed). Requires keeping multiple survivors through induction: inducer currently collapses early. |
| 6 | Expression grammar upgrade: typed grammar, iterative deepening, e-graph dedup, anti-unification (NOT raising max_expr_depth blindly) | **ADOPT (= our planned expression-grammar round)** | Same round our census already queued; CORA adds the discipline: semantic dedup before depth. |
| 7 | View language (Views as programs: Group, Quotient, NegativeSpace, Panels, Reframe...) | ADOPT-LATER (Stage E) | The big one. Current segmentation variants become seed ViewPrograms. Gate: only build views the Stage-A failure table demands (e.g. CollinearGroup), never speculative ones. |
| 8 | Roles (source/target/instruction/separator...) as first-class latent variables | ADOPT-LATER (Stage E) | Partially present implicitly (path_two_anchor canonical roles); make explicit only when failure table shows role-failures cluster. |
| 9 | Joint view-program search (alternating refinement) | ADOPT-LATER (Stage F) | Depends on E. |
| 10 | Neural proposal model (propose, never certify) | DEFER | Doc itself says: don't train a ranker before there is semantic program diversity. Revisit after E. |
| 11 | Wake-sleep/dream synthetic task generation | DEFER | After concepts exist to dream from. |
| 12 | Experience/Promotion/Lockbox splits + prequential experiment | **ADOPT-NOW (Stage B, design only)** | Costs one script + a frozen manifest; enormously strengthens the paper. Split by structural family, not randomly. |
| 13 | Immutable verifier (system may not weaken its own gate) | ALREADY-HAVE (make explicit) | Already true de facto; state it as an architectural invariant in ARCHITECTURE.md + paper. |
| 14 | Paper reframing: "training-split calibration strong; eval coverage collapsed; eval-split calibration undetermined"; Wilson CI on 40/42 (84.2-98.7%) | **ADOPT-NOW (Stage 0, wording)** | Strictly more defensible; apply to paper/DRAFT.md + writeup. |
| 15 | Failure classifier routing compute (representation-failure -> propose views; parameter-instability -> search relational expressions) | ADOPT-LATER | Natural output of Stage A's structured traces; learnable later from history. |
| 16 | "What not to do": more hand-written generator modes, more search in same space, ranker-first | ALREADY-AGREED | Matches our own ablations; R22-style rounds stay falsification-gated and few. |

## Staged build order

- **Stage 0 (wording, now)**: Paper/writeup claim-hardening per #14. No code.
- **Stage A (now, analysis-only)**: Near-Solve Compiler v0 over existing near_solves.jsonl +
  census artifacts. Output: `outputs/nearsolve_compiler/ns_dataset.jsonl` (one structured record
  per near-solve: NS-level, blocking parameter, required expression class, repair hypothesis,
  DSL-expressible?) + `docs/NS_FAILURE_FAMILIES.md` (the real version of the doc's illustrative
  table). This table then DICTATES the expression-grammar round's primitive list: replacing
  intuition with measurement.
- **Stage B**: independent-transfer promotion rule + experience/promotion/lockbox manifest
  (600/200/200 by structural family; frozen file, hashes recorded).
- **Stage C**: metamorphic certificate component (invariance-claimed interventions only),
  reported as a certificate field; never replaces LOO, only annotates.
- **Stage D**: version-space survivors + semantically-diverse attempt_2.
- **Stage E/F**: view language + roles + joint search, built strictly from Stage-A demand.

## Invariants (unchanged by CORA)

LOO-by-reinduction remains the sole acceptance gate and is immutable; every extension is a
certificate ANNOTATION or a PROPOSAL mechanism. No LLMs at solve time. Submission bar unchanged
(train>200 AND eval>0). All long runs detached with markers.

## Queue integration (how CORA meshes with the pre-existing program)

Order of execution: R22 seal + v23 chain (pre-CORA housekeeping, prospective 183) ->
Stage B engine half (independent-transfer in promote_and_validate) -> expression-grammar
round = CORA invention round 1 (targets from Stage A: pattern-as-function 111 ->
object synthesis 46 -> relational selectors 27; invent from Experience split only, promote
via Promotion split, per docs/LOCKBOX_PROTOCOL.md) -> Stage C metamorphic certificate +
Stage D version-space attempt_2 (certificate/Kaggle strengtheners) -> Stage E view language
= CORA invention round 2 (measured demand: 292 NS-5 tasks, the largest family) -> E3 eval
re-run under full flags -> Kaggle bar check (train>200 AND eval>0).

## Neural proposer: explicit trigger condition (idea #10, expanded)

The neural layer (propose-never-certify search guidance) stays deferred until BOTH:
(1) Stages E/F exist, so there is semantic program diversity worth ranking (the CORA doc's
own warning), and (2) search cost inside the enlarged space is the MEASURED bottleneck
(census evidence today says the hypothesis space, not search allocation, is the blocker -
194/269 language-blocked). Training data accrues as a byproduct meanwhile: certified
programs, fold programs, Stage-A ns_dataset.jsonl (semantic deltas = hard negatives +
repair hypotheses). Acceptance NEVER moves to the network; offline/no-LLM Kaggle
constraints unchanged.
