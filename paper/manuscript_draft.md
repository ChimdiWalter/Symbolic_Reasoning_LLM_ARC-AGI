# Executable Finite Semantics for Scientist-Model Reasoning: Bounded Diagnostics for Falsification, Repair, and Compression in Colored-Grid Tasks

## Abstract

Reasoning systems often receive only a few demonstrations, leaving many candidate rules that fit the observed examples but diverge under perturbations, distractors, or compositional edge cases. We present a bounded scientist-model framework for studying this problem in finite colored-grid worlds. The project combines deterministic object/relation parsing, an explicit transformation DSL, hypothesis generation, compute-matched falsification, MDL-style selection, repair-after-corruption diagnostics, a bounded neural-guided extension with grid encoders and JEPA-style latent prediction, and local ARC-formatted external-validity checks. Its strongest contribution is not an ARC breakthrough or a general mathematical unification claim. Instead, it makes a precise separation between exact finite semantics, proxy metrics, and empirical diagnostics. Within declared finite domains, the code gives exact bounded shortest-program checks in the DSL, exact small-category law checks over enumerated grid states and morphisms, and exact operator-specific topology audits for support, component-count, and hole-count invariants. Empirically, transformation-library models outperform a direct input-output proxy on synthetic structural-transfer diagnostics, falsification improves selection in constructed high-ambiguity/compositional strata under compute-matched budgets, and repair improves a bounded corruption-recovery diagnostic. The neural-guided extension is implemented and reproducible but does not improve exact ARC performance on the current bounded local slice. The integrated system improves some latent/recovery metrics but does not improve task accuracy over the strongest partial stacks, and local ARC exact solve rate remains zero in the current diagnostic. The resulting contribution is a reproducible, artifact-backed framework for evaluating when explicit structural hypotheses help, where falsification helps, and where current mechanisms remain insufficient.

## 1. Introduction

Few-shot abstract reasoning tasks are underdetermined. A model may see several input-output demonstrations, infer a rule that explains them, and still fail because the demonstrations did not expose a decisive counterexample. This setting is common in grid reasoning: one hypothesis may be a geometric transformation, another may be a color heuristic, another may be a relation-specific rule, and all may fit the demonstrations while disagreeing on held-out examples.

This paper studies that regime with a deliberately bounded scientist-model architecture. The system parses colored grids into object and relation descriptions, proposes explicit programs in a finite transformation DSL, executes candidates, optionally falsifies candidates with passive and synthetic probe checks, scores them with MDL-style and intervention-style proxies, and measures whether corrupted intermediate choices can be repaired. A bounded neural-guided extension adds learned visual priors, JEPA-style latent prediction, and neural candidate ranking without replacing exact symbolic verification. The implementation also includes a local ARC adapter, but ARC is treated only as an external-validity diagnostic because ARC tasks do not expose latent generating programs and the current diagnostic solves no labeled evaluation task exactly.

The central thesis is:

> A precise scientist-model benchmark can make abstract-reasoning claims more testable by separating exact finite semantic checks from proxy criteria and empirical hypotheses; in this bounded setting, structural program search and conditional falsification show localized benefits, while integrated-stack and ARC-transfer claims remain weak.

The novelty is intentionally modest and executable. Instead of claiming exact Kolmogorov complexity, full category theory, full HoTT, broad topology theorems, ARC state-of-the-art performance, or a path to AGI, the project asks what can be made exact inside the implemented finite world and how far a bounded neural-guided extension can be layered on top without erasing those boundaries. The answer is useful: bounded DSL minima, finite extensional equality, small-category law checks over enumerated domains, operator-specific topology classifications, and neural-guided but exactly verified candidate search can be computed and tested. Those exact checks then anchor a broader empirical program whose positive, null, and negative findings are kept separate.

## 2. Contributions

1. **Exact finite semantic layer for a reasoning DSL.** The repository implements exact bounded shortest-program search under a declared candidate generator and coding scheme; exact finite small-category checks where objects are enumerated grid states and morphisms are executable programs; and exact operator-specific topology audits over bounded domains. Supporting artifacts are in `outputs/exactness`.

2. **Conditional falsification diagnostics.** The project reframes falsification as a conditional hypothesis: it should help when several candidate rules fit demonstrations but differ under perturbations, held-out cases, distractors, or compositional edge cases. A compute-matched seven-family H2 sweep supports this claim only in constructed ambiguity/composition strata, with one family showing no gain.

3. **Artifact-backed empirical characterization rather than benchmark claims.** Synthetic sweeps show strong structural-transfer advantages over a direct proxy and repair benefits on corruption diagnostics. H4 compression evidence is stronger as bounded exact-minimum alignment than as causal compression, including a five-seed alignment check over the active breadth-validation runs. H5 integrated-stack evidence is weak/inconclusive, and ARC exact solve rate remains zero in the current diagnostic.

4. **Bounded neural-guided executable-reasoning extension.** The repository now includes variable-size grid encoders, a small Grid-JEPA module, neural candidate ranking, bounded refinement with optional task-local adaptation, and a REMA-inspired latent failure diagnostic. These modules are attached to the exact DSL layer rather than replacing it. Current smoke evidence shows implementation readiness but no exact ARC improvement.

## 3. Related Work Positioning

This project sits at the intersection of program synthesis for visual reasoning, ARC-style abstraction, object-centric representation, model selection by description length, adversarial testing, causal representation diagnostics, and repair/self-consistency mechanisms. It borrows several mathematical idioms: composition from category theory, adversarial interaction from game semantics, path/equivalence language from HoTT-inspired reasoning, topological invariants from finite shape analysis, and compression ideas from MDL and algorithmic information theory.

The implementation does not claim equivalence to those full mathematical theories. Instead, each inspiration is translated into a finite executable object:

- composition becomes explicit sequential execution of grid programs;
- category-inspired semantics become exact identity, associativity, closure, and extensional equality checks over finite enumerated domains;
- topology becomes support-mask, 4-connected component-count, and hole-count invariants over finite grids;
- path/equivalence language becomes finite extensional equality and repair-after-corruption diagnostics;
- algorithmic-information language becomes declared DSL code length, exact bounded minimum search, and MDL/intervention proxies.

This positioning is conservative by design. The project is intended to make claims auditable, not to collapse distinct theoretical traditions into one slogan. The same conservatism applies to the new neural-guided extension: JEPA-style latent prediction, neuro-symbolic ARC systems, and REMA-style latent geometry motivate the implementation, but the paper treats them as bounded engineering components plus diagnostics rather than as solved-theory imports.

## 4. Problem Setting

Each task consists of one or more demonstration pairs and held-out test pairs. A grid is a finite integer array where zero is background and nonzero values are colors. Synthetic tasks include known latent programs, making it possible to evaluate both behavioral correctness and latent-rule recovery. ARC-formatted tasks are loaded locally when present, but they are evaluated only by output metrics because the dataset does not provide generating programs.

Let \(x\) be an input grid and \(y\) an output grid. A candidate program \(p\) is an executable composition of DSL operators. A candidate fits the demonstrations if \(p(x_i) = y_i\) for each training pair. It recovers behavior if it also matches held-out examples. It recovers the latent rule only when its signature matches the known synthetic generating program, with separate accounting for behaviorally equivalent or repairable alternatives.

The system evaluates four operational inductive biases:

- compositional transformation bias;
- conditional verification-by-falsification bias;
- repairable/equivalent reasoning trajectory bias;
- causal-compression/description-length bias.

These are hypotheses about finite implemented mechanisms. They are not claims about general intelligence.

## 5. Methods

### 5.1 Synthetic Task Families

The main synthetic world uses colored grids with deterministic latent programs. Task families cover reflection, rotation, translation, recoloring by object predicate, connected-component operations, counting-based rewriting, containment and adjacency, symmetry, topology-preserving color changes, distractor-rich causal/spurious distinctions, and compositions of multiple operators.

The current paper-breadth sweep uses 19 families: the original 11 families plus eight added families:

- `paper_composition_reflect_count`;
- `paper_composition_adjacent_reflect`;
- `paper_copy_corner_distractor`;
- `paper_topology_distractor`;
- `paper_nuisance_marker_recolor`;
- `paper_causal_spurious_largest`;
- `paper_containment_reflect_mark`;
- `paper_symmetry_repair_challenge`.

Each generated task carries metadata used for stratified analysis, including ambiguity level, candidate count, distractor condition, compositional condition, verification budget level, and compute-match condition where applicable.

### 5.2 Object and Relation Parsing

The parser treats non-background same-color connected components as objects. For each object it computes masks, bounding boxes, colors, sizes, and relation summaries. Scene-level relations include adjacency, containment-like bounding relations, symmetry indicators, object counts, and topology summaries. These deterministic features support object-aware candidate generation and evaluation. They are not learned perception claims.

### 5.3 DSL and Operator Library

The transformation DSL contains executable operators such as reflection, rotation, translation, recoloring the largest component, preserving topology while changing color, counting objects into bars, selecting objects by relational predicates, copying objects to a corner, marking contained objects, and removing distractors while preserving symmetric pairs. Programs may be single operators or bounded compositions. Program signatures are logged for synthetic tasks, enabling latent-rule recovery metrics.

### 5.4 Model Variants

The ablation stack includes:

- `direct_io_proxy`: nearest-example input-output proxy baseline;
- `transformation_library`: explicit program search without falsifier or compression selector;
- `proposer_only`: candidate proposal and selection without using falsification outcomes;
- `proposer_falsifier`: candidate proposal plus falsification-based rejection;
- `compression_selector`: MDL/intervention-style selection over train-fitting candidates;
- `path_repair`: repair-aware candidate selection after controlled corruption;
- `integrated_scientist`: parser, generator, executor, falsifier, compression scoring, and repair diagnostics.

The direct baseline is explicitly a proxy, not a trained transformer. This keeps the current package minimal-dependency and reproducible, but it weakens any claim about comparison to modern neural systems.

### 5.5 Falsifier

The falsifier checks candidate hypotheses by contradiction on demonstrations, perturbation/probe evaluation in synthetic hidden-rule worlds, and logged counterexample traces when available. H2 comparisons are compute-matched: proposer-only controls spend the same logged candidate/probe/check budget but discard probe outcomes for selection. The primary H2 metric is false-rule acceptance, where a train-fitting wrong-signature program is counted as accepted only if it also fails held-out behavior.

### 5.6 Compression and Intervention Proxies

Compression scoring uses practical proxies: program description length, sparsity, nuisance perturbation robustness, intervention stability, and causal-factor recovery on synthetic metadata. The exact bounded DSL-minimum analysis compares selected programs to the shortest fitting program inside the configured finite candidate set. This exact bounded analysis does not compute Kolmogorov complexity and does not establish causal discovery.

### 5.7 Repair Diagnostic

Repair is evaluated by injecting controlled corruption into intermediate program states and measuring whether a repair-aware selection process recovers a behaviorally correct or equivalent candidate. This is a bounded operational repairability diagnostic. It is not a full HoTT formalization of paths or univalence.

### 5.8 ARC Adapter

The ARC adapter loads local ARC-AGI formatted JSON files under `data/arc` and evaluates output grids when solution files exist. ARC evaluation reports exact task accuracy, pixel accuracy, runtime, candidate counts, and qualitative failures. It does not report latent-rule recovery because ARC files do not expose generating programs.

### 5.9 Neural-Guided Executable Reasoning

The upgrade phase adds a bounded neuro-symbolic layer while preserving exact symbolic verification. `src/reasoning_project/neural/grid_encoder.py` implements variable-size grid encoders with color-token embeddings, padding/masking, and an optional small transformer. `src/reasoning_project/neural/grid_jepa.py` implements masked latent prediction and optional input-to-output latent prediction on ARC-style grids. `src/reasoning_project/neural/program_ranker.py` uses those embeddings to score DSL candidates. `src/reasoning_project/refinement.py` adds neural ranking, exact execution, repair, optional task-local adaptation, and top-k output logging. `src/reasoning_project/diagnostics/reasoning_manifold.py` adds a REMA-inspired latent failure diagnostic over bounded candidate/refinement embeddings.

These modules do not move the exactness boundary. Exactness remains confined to the finite DSL, finite category checks, and finite topology audits already declared elsewhere in the paper. The neural modules only guide search or provide diagnostics; they do not certify correctness.

## 6. Exact Finite Semantics

The exact layer is the paper's cleanest mathematical contribution. Every exact claim names a finite domain, candidate set, equality notion, coding scheme, and artifact path.

### Proposition 1: Exact Bounded DSL Minimality

For a finite candidate set \(C = \texttt{candidate\_programs(max\_depth, colors)}\), a finite set of examples \(E\), exact grid equality, and declared integer code length \(L\), exhaustive enumeration returns the exact minimum \(L(p)\) among programs \(p \in C\) that match every example in \(E\).

This is implemented by `src/reasoning_project/formal.py::bounded_exact_dsl_minimum` and tested in `tests/test_formal.py`. In `outputs/exactness/exactness_report.md`, the identity case uses 31 candidates with 7 exact-fitting candidates and a unique minimum `identity` of 4 code units. The `reflect_vertical` case uses 31 candidates with 1 exact-fitting candidate and a unique minimum `reflect_vertical` of 20 code units.

Boundary: this is exact only inside the finite candidate set and declared coding scheme. It is not exact Kolmogorov complexity and not global program minimality.

### Proposition 2: Exact Small-Category Laws on Finite Domains

For a supplied finite grid domain \(D\), supplied executable morphism set \(M\), identity map, sequential composition, and extensional equality over all grids in \(D\), identity, associativity, well-defined composition, and closure are decidable by exhaustive evaluation.

This is implemented by `src/reasoning_project/formal.py::check_finite_category_laws`. In `outputs/exactness/exactness_report.md`, identity, associativity, well-defined composition, and closure hold for four reflection-group morphisms over all binary 2x2 grids.

Boundary: this is an exact small-category check for the supplied finite system. It is not a general categorical semantics of reasoning.

### Proposition 3: Exact Operator-Specific Topology Audit

For supplied operator instances, a finite grid domain, and declared support-mask, 4-connected component-count, and hole-count invariants, exhaustive evaluation exactly classifies whether each operator preserves the invariants on that domain. For failures, the audit stores counterexamples.

This is implemented by `src/reasoning_project/formal.py::audit_operator_topology_suite`. In `outputs/exactness/topology_operator_audit.md`, 31 operator instances are classified over all binary 3x3 grids plus selected colored 3x3 probes. The audit identifies support-mask preserving operators, component/hole-count preserving operators, conditional operators, and operators that fail on the bounded domain.

Boundary: this is not a broad topology theorem. It is an operator/domain-specific finite audit.

## 7. Hypotheses and Current Verdicts

| Hypothesis | Active wording | Current verdict | Primary artifact |
| --- | --- | --- | --- |
| H1 Structural transfer | Object/relation and transformation-library models should generalize better than direct input-output proxy and small task-conditioned learned baselines on OOD grid sizes and compositional splits. | Supported in specific synthetic structural-transfer strata only. | `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md` |
| H2 Conditional falsification | Verification by falsification improves hypothesis selection primarily when several candidate rules fit demonstrations but differ under perturbations, held-out cases, distractors, or compositional edge cases. | Supported in specific constructed high-ambiguity/compositional strata only. | `outputs/h2_family_validation_10seed_sweep/family_balanced_h2_analysis.md` |
| H3 Repairability | Repair-aware program search should recover from controlled corruption more often than unrepaired candidate selection. | Supported in specific corruption/recovery diagnostics only; no task-accuracy gain. | `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md` |
| H4 Causal compression | MDL-like and intervention-stability scoring should prefer shorter, more causal rules over spurious surface fits. | Weak/inconclusive as causal compression; stronger as bounded exact-minimum alignment. | `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/h4_sweep_summary.md` |
| H5 Integrated scientist model | The full integrated model should beat partial stacks across multiple families and metrics before being treated as supported. | Weak/inconclusive: latent/recovery gains without task-accuracy or ARC exact-solve gains, unchanged by the current neural-guided extension. | `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md`; `outputs/arc_diagnostic_eval_6task_3seed/arc_evaluation_summary.md`; `outputs/arc_refinement/arc_refinement_smoke/summary.json` |

## 8. Experiments

### 8.1 Exactness Audit

The exactness audit is generated by `scripts/check_exactness.py`. It writes config snapshots, seed lists, command logs, exactness reports, topology audit reports, and manifests under `outputs/exactness`.

### 8.2 Paper-Breadth Synthetic Sweep

The paper-breadth validation sweep is generated from `configs/paper_breadth_validation.json` and aggregated in `outputs/paper_breadth_validation_5seed_sweep`. It evaluates eight model variants across 19 synthetic task families, 2 tasks per family, and 5 seeds. Metrics include test pair accuracy, OOD pair accuracy, latent-rule recovery, held-out behavior recovery, false-rule selection/acceptance, recovery-after-corruption, runtime, and budget fields.

### 8.3 H2 Conditional Ambiguity Sweep

The H2 sweep is generated from `configs/h2_family_validation.json` and aggregated in `outputs/h2_family_validation_10seed_sweep`. It evaluates `proposer_only` versus `proposer_falsifier` across seven ambiguity probes, 3 tasks per family, and 10 paired seeds:

- `h2_noncommuting_composition_probe`;
- `h2_symmetric_reflect_recolor_probe`;
- `h2_symmetric_rotate_recolor_probe`;
- `h2_reflect_select_border_probe`;
- `h2_reflect_mark_contained_probe`;
- `h2_copy_corner_probe`;
- `h2_largest_vs_border_probe`.

The sweep is compute-matched on logged candidate/probe/check budgets.

### 8.4 H4 Bounded Compression Analysis

The single-run H4 analysis is generated by `scripts/analyze_h4_compression.py` over `outputs/paper_breadth_smoke`. It computes exact bounded DSL minima for each task where the finite candidate set is tractable, then compares selected programs to those minima. A five-seed aggregation of completed child runs is generated by `scripts/analyze_h4_sweep.py` and reported in `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment`.

### 8.5 ARC External-Validity Diagnostic

The ARC diagnostic is generated from local ARC files and reported in `outputs/arc_diagnostic_eval_6task_3seed`. It evaluates six labeled ARC evaluation tasks, three seeds, and four models: `direct_io_proxy`, `transformation_library`, `proposer_falsifier`, and `integrated_scientist`.

### 8.6 Neural-Guided Executable-Reasoning Smoke Path

The local ARC-style status audit is generated by `scripts/audit_arc_agi2.py` and reported in `outputs/arc_status/arc_agi2_status.md` and `outputs/arc_status/arc_agi2_status.json`. Grid-JEPA smoke training/evaluation is generated by `scripts/train_grid_jepa.py` and `scripts/eval_grid_jepa.py` under `outputs/neural`. Neural rankers are trained by `scripts/train_program_ranker.py` with both plain grid-encoder and Grid-JEPA-conditioned inputs. The bounded ARC refinement slice is generated by `scripts/run_arc_refinement.py` and summarized in `outputs/arc_refinement/arc_refinement_smoke`, with the REMA-inspired diagnostic added by `scripts/analyze_reasoning_manifold.py`.

## 9. Results

### 9.1 Exact Finite Semantics

The exactness audit supports all three bounded propositions in the specified domains. Exact bounded DSL minima are found for identity and vertical reflection toy cases. The finite small-category check passes identity, associativity, well-defined composition, and closure over all binary 2x2 grids for the supplied reflection morphisms. The topology audit classifies 31 operator instances and records counterexamples for failures.

These results are mathematical checks over finite executable systems. They are the strongest formal part of the project.

### 9.2 H1: Structural Transfer

In `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md`, `transformation_library_minus_direct_io_proxy` has test pair accuracy delta `+0.813` and OOD pair accuracy delta `+0.947` over five seeds. The transformation-library model also has latent-rule recovery delta `+0.847` and held-out behavior recovery delta `+0.989`. Against the learned baseline, `transformation_library_minus_learned_task_mlp` has test/OOD deltas `+0.832/+0.997`.

This supports H1 only in the paper-breadth synthetic structural-transfer strata. The claim does not extend to ARC exact solving, where exact task accuracy remains zero in the current diagnostic.

### 9.3 H2: Conditional Falsification

In `outputs/h2_family_validation_10seed_sweep/family_balanced_h2_analysis.md`, the compute-matched `proposer_falsifier_minus_proposer_only` family-balanced false-rule acceptance delta is `-0.857` across seven H2 families. Held-out behavior recovery and test pair accuracy deltas are both `+0.857`. Six families show false-rule acceptance delta `-1.000`; `h2_largest_vs_border_probe` shows delta `0.000`.

The failure taxonomy in `outputs/h2_family_validation_10seed_sweep/failure_taxonomy.md` reports zero deltas for logged candidate/probe/check budgets and 10/10 paired-seed wins for the left model. Accepted false-rule examples in `outputs/h2_family_validation_10seed_sweep/accepted_false_rule_examples.md` show proposer-only selecting train-fitting rules such as a bare count, recolor, or mark operation when the true program included a composition or selection condition.

This supports H2 only in identifiable ambiguity regimes. It should not be stated as a general claim that falsification improves reasoning.

### 9.4 H3: Repairability

In `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md`, `path_repair_minus_compression_selector` has recovery-after-corruption delta `+0.968`. Test and OOD pair accuracy deltas are `0.000`.

This supports repairability only as a bounded corruption-recovery diagnostic. It does not show task-accuracy gains and does not justify stronger path-equivalence claims.

### 9.5 H4: Compression and Exact Bounded Minima

In `outputs/paper_breadth_smoke/h4_bounded_compression/h4_bounded_compression_summary.md`, exact bounded DSL minima are available for all 19 tasks in the breadth smoke. In the follow-up five-seed aggregation `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/h4_sweep_summary.md`, `compression_selector`, `transformation_library`, `proposer_only`, and `path_repair` all achieve exact-minimum alignment rate `1.000`, while `integrated_scientist` and `proposer_falsifier` reach `0.979`.

Per-task records in `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/per_task_exact_mdl.json` also make one important model split legible: on `paper_causal_spurious_largest`, `transformation_library` often selects the shorter exact bounded minimum `keep_adjacent_to_color(target_color=1)`, while `integrated_scientist` selects the longer latent-correct rule `select_by_relational_predicate(predicate=largest)`. This clarifies why exact bounded minima can explain a model difference without deciding causal truth.

This clarifies the H4 verdict. Exact-minimum alignment is real and repeatable, but it is not unique to the compression selector. The H4 claim therefore remains weak/inconclusive as a causal-compression claim and stronger only as a bounded DSL-minimum alignment diagnostic.

### 9.6 H5: Integrated Scientist Model

In `outputs/paper_breadth_validation_5seed_sweep/paired_contrasts.md`, `integrated_scientist_minus_transformation_library` has latent-rule recovery delta `+0.021` and recovery-after-corruption delta `+0.968`, but test and OOD pair accuracy deltas are both `0.000`. Runtime increases by about `+4.401` seconds in that contrast, with much larger logged falsification/probe/passive-check budgets.

This makes H5 weak/inconclusive. The integrated model improves some diagnostics but does not beat the strongest partial stacks on task accuracy.

### 9.7 ARC External Validity

**Prior diagnostic (core DSL, evaluation split).** In `outputs/arc_diagnostic_eval_6task_3seed/arc_evaluation_summary.md`, exact task accuracy is `0.000` for all tested models on six labeled ARC evaluation tasks using the core DSL (588 programs). Pixel accuracy is `0.432` for `direct_io_proxy` and `0.555` for `transformation_library`, `proposer_falsifier`, and `integrated_scientist`. The core DSL lacked operators needed for any sampled evaluation task.

**Expanded DSL diagnostic (arc_expanded, training split).** The expanded DSL adds 27 operators covering color remapping, transpose, upscale/downscale, gravity, flood fill, tiling, mirroring, hollowing, outlining, denoising, and sorting, producing 4,947 depth-2 candidate programs. Brute-force enumeration identifies 31 solvable tasks out of 1,000 ARC training tasks (3.1%). In `outputs/arc_solvable_diagnostic_cpu/summary.json`, `transformation_library`, `proposer_falsifier`, and `compression_selector` all achieve exact task accuracy `1.000` and pixel accuracy `1.000` on these 31 tasks. `direct_io_proxy` achieves exact task accuracy `0.000` and pixel accuracy `0.359`.

This confirms H1 structural-transfer advantage on real ARC tasks: explicit program search dominates the direct proxy on the DSL-solvable subset. The 31 tasks cover geometric primitives (flips, rotations, translations), color operations (remapping, swapping), spatial operations (gravity, flood fill, cropping), and canvas operations (upscaling, tiling, mirroring). Tasks requiring visual analogy, abstract pattern completion, or multi-step conditional reasoning remain outside the DSL boundary and are not solved.

The expanded diagnostic should be read as a bounded external-validity positive: the scientist-model pipeline works on real ARC tasks when the DSL can express the transformation, but the DSL covers only 3.1% of ARC's diversity.

### 9.8 Neural-Guided Executable Reasoning

The new neural-guided extension is currently a systems contribution and a negative transfer result, not a new positive capability claim. The local data audit in `outputs/arc_status/arc_agi2_status.md` shows that the repository contains ARC-AGI-style JSON files with labeled training/evaluation splits and unlabeled test split, but the filenames do not by themselves justify a clean ARC-AGI-2 provenance claim.

The Grid-JEPA smoke run is stable but modest. `outputs/neural/grid_jepa_smoke/metrics.json` reports final train loss `0.9517` and validation loss `0.9677`, while `outputs/neural/grid_jepa_eval_smoke/metrics.json` reports evaluation loss `0.9255` on 8 records. The downstream smoke rankers are now strong on synthetic held-out behavior but still negative on ARC exact transfer. `outputs/neural/program_ranker_smoke/metrics.json` reports synthetic held-out top1/top2 `0.833/1.000` with ARC exact/pass@2 `0.000/0.000` on 6 labeled evaluation tasks and ARC pixel top1 `0.469`. The Grid-JEPA-conditioned ranker in `outputs/neural/program_ranker_jepa_smoke/metrics.json` reports synthetic held-out top1/top2 `1.000/1.000` with ARC exact/pass@2 `0.000/0.000` and ARC pixel top1 `0.324`.

The bounded ARC refinement slice in `outputs/arc_refinement/arc_refinement_smoke/summary.json` leaves the ARC verdict unchanged. Across 2 labeled evaluation tasks, `direct_io_proxy`, `transformation_library`, `compression_selector`, `proposer_falsifier`, `neural_dsl_ranker`, `grid_jepa_dsl_ranker`, `refinement_loop`, `refinement_loop_tta`, and `integrated_scientist_neural_proposer` all remain at exact solve rate `0.000` and pass@2 `0.000`. Mean pixel accuracy is `0.495` for every method because one task is a complete miss and one task is a near-match for all methods. The REMA-inspired analysis in `outputs/arc_refinement/arc_refinement_smoke/reasoning_manifold/reasoning_manifold_summary.json` correspondingly has no solved-task manifold to characterize on this slice.

A larger GPU pipeline has been submitted through `slurm/submit_neural_arc_pipeline.sh` and logged in `outputs/slurm_logs/neural_arc_pipeline_submission.json`. Those queued runs are intended to test whether the stronger proposer path changes the zero-exact ARC verdict on broader labeled slices without changing the local-provenance limitation.

## 10. Discussion

The project makes progress by replacing broad claims with auditable distinctions. The exact layer demonstrates that some mathematical language can be made precise inside finite executable systems. The empirical layer then asks whether those mechanisms matter for model behavior.

The clearest positive result is H1: explicit structural programs dominate a direct proxy on synthetic OOD and compositional diagnostics, and this advantage now extends to real ARC tasks — on the 31-task DSL-solvable subset, structural methods achieve exact solve rate `1.000` while the direct proxy achieves `0.000`. The second positive result is narrower: falsification helps when ambiguity is deliberately present and probes reveal distinctions invisible in demonstrations. The repair result is similarly narrow but clean: repair improves recovery from controlled corruption. H4 is currently supported only as bounded exact-minimum alignment, and the five-seed alignment check shows that this behavior is not unique to the compression selector. The per-task exactness records are also useful because they explain why two models can diverge even when both fit training data: one can take the shorter bounded minimum while another takes a longer latent-correct rule. H5 is not yet supported as a broad integrated-stack claim.

This pattern is scientifically useful. A less careful report could have emphasized only the positive synthetic results or the mere presence of neural modules. Here, the artifact structure makes the failures equally visible: the expanded DSL covers only 3.1% of ARC training tasks, H2 has a zero-gain family, H4 does not isolate causal compression, the neural-guided smoke path shows no exact transfer beyond DSL-solvable tasks, and the integrated model pays substantial compute without task-accuracy gains over simpler partial stacks. The ARC result is honest in both directions: it confirms the pipeline works on real tasks within DSL expressiveness, and it quantifies exactly where DSL expressiveness ends.

## 11. Limitations

The strongest empirical evidence is synthetic. Synthetic tasks are valuable because they expose latent programs and controlled strata, but they do not establish broad external validity.

The direct input-output baseline is a nearest-example proxy, not a trained transformer. This is acceptable for a minimal-dependency reproducibility scaffold, but it limits comparisons to contemporary neural approaches.

H2 evidence is deliberately conditional. The current positive result is concentrated in constructed ambiguity/composition probes. It should be stress-tested with more tasks per family, varied distractor/probe regimes, and more seeds before any stronger claim.

H3 is a recovery-after-corruption diagnostic. It is not a general theory of equivalent reasoning paths.

H4 is not exact algorithmic information dynamics or causal discovery. The exact part is the bounded DSL-minimum computation; the causal/intervention language remains proxy-based, and the multi-seed alignment check shows that exact-minimum agreement alone does not isolate the compression selector.

H5 remains weak/inconclusive. The full stack improves latent/recovery diagnostics but does not improve task accuracy over the strongest partial stacks in the paper-breadth sweep and does not solve ARC tasks exactly. The added neural-guided extension also does not yet change that verdict.

The new neural-guided modules are implemented only as bounded smoke evidence in this paper version. The Grid-JEPA loss is stable on the smoke mix, and the updated smoke rankers now recover synthetic held-out behavior strongly, but ARC transfer is still negative: the plain ranker reaches synthetic held-out top1/top2 `0.833/1.000`, the Grid-JEPA-conditioned ranker reaches `1.000/1.000`, and both remain at ARC exact/pass@2 `0.000/0.000` on the current 6-task labeled evaluation slice. The REMA-inspired manifold diagnostic is correspondingly limited by having no solved tasks on the ARC refinement slice.

ARC evaluation is small and diagnostic. The current exact solve rate is zero in both the earlier symbolic diagnostic and the new neural-guided refinement slice, so ARC supports a limitation claim rather than a capability claim. Local ARC-style provenance is also ambiguous rather than cleanly established as ARC-AGI-2.

## 12. Conclusion

This paper presents a bounded scientist-model framework for abstract reasoning diagnostics. Its central contribution is not scale or leaderboard performance, but precision: exact finite semantics are separated from proxy metrics, and empirical claims are tied to concrete artifacts. Within finite synthetic colored-grid systems, structural program search and conditional falsification show identifiable benefits. Repair improves a bounded recovery diagnostic. Compression can be compared against exact bounded DSL minima. A bounded neural-guided executable-reasoning extension can be layered onto the exact DSL stack without weakening the formal boundaries, but current transfer results remain negative. The integrated model and ARC transfer remain weak. The result is a reproducible research package for studying when explicit hypotheses help and for preventing mathematical or benchmark language from outrunning the evidence.

## Appendix A. Exact vs Proxy vs Not Claimed

| Contribution area | Status | Implemented as | Artifact path | Boundary |
| --- | --- | --- | --- | --- |
| Bounded DSL shortest program | exact bounded | Exhaustive minimum over `candidate_programs(max_depth, colors)` under exact example equality and declared integer code length. | `outputs/exactness/exactness_report.md`; `outputs/paper_breadth_smoke/h4_bounded_compression/h4_bounded_compression_summary.md` | Not exact Kolmogorov complexity or global program minimality. |
| DSL code length | exact bounded | `operator_base_cost * 20 + 3 per parameter key + parameter-value character count`. | `outputs/exactness/exactness_report.json` | Coding-scheme dependent. |
| Small-category laws | exact bounded | Objects are enumerated grid states; morphisms are executable programs; equality is finite extensional equality. | `outputs/exactness/exactness_report.md` | Not a general categorical semantics of reasoning. |
| Path/equivalence witness | exact bounded | Syntactic identity, finite extensional equivalence, or non-equivalence over supplied domains. | `outputs/formal_boundary/formal_report.json`; `exactness_traceability.md` | Not HoTT identity types or univalence. |
| Operator topology | exact bounded | Exhaustive support-mask, component-count, and hole-count audits over bounded grid domains. | `outputs/exactness/topology_operator_audit.md` | Not a broad topological theorem. |
| H2 falsification | empirical diagnostic | Compute-matched proposer-only versus proposer-falsifier contrasts on constructed ambiguity probes. | `outputs/h2_family_validation_10seed_sweep/family_balanced_h2_analysis.md` | Conditional support only; one H2 family shows no gain. |
| H4 compression | proxy plus bounded comparison | MDL-style selector compared against exact bounded DSL minima where feasible, with a five-seed alignment aggregation over completed breadth runs. | `outputs/paper_breadth_smoke/h4_bounded_compression/h4_bounded_compression_summary.md`; `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment/h4_sweep_summary.md` | Does not establish exact AID or causal discovery. |
| ARC evaluation | external-validity diagnostic | Output accuracy and runtime/budget reporting on local labeled ARC evaluation tasks. | `outputs/arc_diagnostic_eval_6task_3seed/arc_evaluation_summary.md` | No ARC benchmark claim; exact solve rate remains zero. |
| AGI/path-to-AGI | not claimed | Not implemented. | `FORMAL_BOUNDARIES.md` | Out of scope. |

## Appendix B. Claim Traceability

| Claim | Code modules | Tasks/data | Metrics | Artifacts | Verdict |
| --- | --- | --- | --- | --- | --- |
| H1 structural transfer | `operators.py`, `parsing.py`, `models.py`, `evaluation.py` | 19-family synthetic paper-breadth validation sweep with a learned baseline | test/OOD accuracy, latent recovery, held-out recovery | `outputs/paper_breadth_validation_5seed_sweep`; `outputs/submission_package/tables/table_h1_structural_transfer.md` | supported in specific synthetic strata only |
| H2 conditional falsification | `falsifier.py`, `models.py`, `generators.py`, `h2_analysis.py` | seven H2 ambiguity probes | false-rule acceptance, held-out recovery, budget deltas | `outputs/h2_family_validation_10seed_sweep`; `outputs/submission_package/tables/table_h2_family_balanced.md` | supported in specific constructed ambiguity/composition strata only |
| H3 repairability | `repair.py`, `models.py`, `evaluation.py` | synthetic paper-breadth validation sweep | recovery-after-corruption, task accuracy | `outputs/paper_breadth_validation_5seed_sweep`; `outputs/submission_package/tables/table_h3_repairability.md` | supported for recovery diagnostic only |
| H4 compression | `compression.py`, `h4_analysis.py`, `h4_sweep_analysis.py`, `formal.py` | paper-breadth smoke and five-seed breadth alignment | exact minimum gap, nuisance/intervention/causal proxies | `outputs/paper_breadth_smoke/h4_bounded_compression`; `outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment`; `outputs/submission_package/tables/table_h4_alignment.md` | weak as causal compression; stronger as exact bounded-minimum alignment |
| H5 integrated scientist model | `models.py`, `experiment.py`, `arc_diagnostic.py` | synthetic paper-breadth validation sweep and local ARC diagnostic | task accuracy, latent recovery, runtime, ARC exact/pixel accuracy | `outputs/paper_breadth_validation_5seed_sweep`; `outputs/arc_diagnostic_eval_6task_3seed`; `outputs/submission_package/tables/table_h5_integrated_stack.md` | weak/inconclusive |
| Neural-guided executable reasoning | `neural/grid_encoder.py`, `neural/grid_jepa.py`, `neural/program_ranker.py`, `refinement.py`, `diagnostics/reasoning_manifold.py` | local ARC-style audit, neural smoke runs, bounded ARC refinement slice | Grid-JEPA latent loss, synthetic held-out top1/top2, ARC exact/pass@2/pixel accuracy, runtime, manifold summary | `outputs/arc_status/arc_agi2_status.md`; `outputs/neural`; `outputs/arc_refinement/arc_refinement_smoke` | implemented and reproducible, but not supported as an ARC-improvement claim |
| Exact bounded semantics | `formal.py` | enumerated finite domains | DSL minimum, category laws, topology invariants | `outputs/exactness`; `exactness_traceability.md` | implemented and tested within declared bounds |

## Appendix C. Reproducibility

The repository contains fixed configs, seed lists, command logs, run states, JSON summaries, CSV metrics, and markdown summaries. Key restart commands are recorded in `RESUME.md` and process details in `PROCESS_LOG.md`.

Primary commands:

```bash
python3.11 scripts/check_exactness.py --output-dir outputs/exactness
python3.11 scripts/run_experiment.py --config configs/paper_breadth_smoke.json --output-dir outputs --resume
python3.11 scripts/analyze_h4_compression.py --run-dir outputs/paper_breadth_smoke
python3.11 scripts/analyze_h4_sweep.py --sweep-dir outputs/paper_breadth_validation_5seed_sweep
python3.11 scripts/run_seed_sweep.py --config configs/h2_family_validation.json --output-dir outputs --sweep-name h2_family_validation_10seed_sweep --seeds 1300 1301 1302 1303 1304 1305 1306 1307 1308 1309
python3.11 scripts/analyze_h2_family_balance.py --sweep-dir outputs/h2_family_validation_10seed_sweep --max-examples 40
python3.11 scripts/analyze_sweep_failures.py --sweep-dir outputs/h2_family_validation_10seed_sweep --contrast proposer_falsifier_minus_proposer_only --metric false_rule_accepted
python3.11 scripts/run_seed_sweep.py --config configs/paper_breadth_validation.json --output-dir outputs --sweep-name paper_breadth_validation_5seed_sweep --seeds 2030 2031 2032 2033 2034
python3.11 scripts/run_arc_diagnostic.py --config configs/arc_diagnostic_eval.json --output-dir outputs
python3.11 scripts/audit_arc_agi2.py --arc-root data/arc --output-dir outputs/arc_status
python3.11 scripts/train_grid_jepa.py --config configs/grid_jepa_smoke.json --output-dir outputs/neural
python3.11 scripts/eval_grid_jepa.py --config configs/grid_jepa_eval_smoke.json --checkpoint outputs/neural/grid_jepa_smoke/checkpoint.pt --output-dir outputs/neural
python3.11 scripts/train_program_ranker.py --config configs/program_ranker_smoke.json --output-dir outputs/neural
python3.11 scripts/train_program_ranker.py --config configs/program_ranker_jepa_smoke.json --output-dir outputs/neural
python3.11 scripts/run_arc_refinement.py --config configs/arc_refinement_smoke.json --output-dir outputs/arc_refinement
python3.11 scripts/analyze_reasoning_manifold.py --config configs/reasoning_manifold_smoke.json
python3.11 scripts/build_submission_package.py --repo-root /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project --breadth-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep --h2-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/h2_family_validation_10seed_sweep --h4-sweep-dir /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/paper_breadth_validation_5seed_sweep/h4_bounded_alignment
python3.11 -m pytest
```

Latest validation recorded in `RUN_HISTORY.md`: the full test suite passed with 42 tests.
