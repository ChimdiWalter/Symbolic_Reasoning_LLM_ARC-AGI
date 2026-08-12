# Data Flow

Traces the data flow through 3 concrete scenarios with exact function call chains and file:line references.

---

## Scenario 1: Task Solved on First Try (Happy Path)

A task arrives, the structural reasoner finds a discriminative property, LOO validates it, the answer is accepted, a certificate is emitted, and the episode is stored in memory.

### Entry Point

The `PortfolioSolver.solve()` is called from a script (e.g., `scripts/run_portfolio_arc.py`).

### Call Chain

```
1. PortfolioSolver.solve(task_id, train_pairs, test_inputs, test_outputs)
   portfolio.py:229
   |
   +-- compute_task_features(train_pairs)
   |   portfolio.py:29
   |   Returns: {size_change, n_colors, max_objects, has_separator, ...}
   |
   +-- heuristic_route(features)
   |   portfolio.py:81
   |   Returns: ordered list of solver names, e.g. ["separator_decompose", "local_rule", "fill_solver", ...]
   |
   +-- For each solver_name in solver_order:
   |   portfolio.py:248
   |
   |   (Assuming "reasoning_engine" solver runs and succeeds)
   |
   +-- solver_fn(train_pairs, test_inputs)
       This calls solve_task_reasoning():
       reasoning_engine.py:2289
       |
       +-- GridDomainAdapter(bg=0)
       |   reasoning_engine.py:1313
       |
       +-- StructuralReasoner(adapter, memory=reasoning_memory)
       |   reasoning_engine.py:447
       |
       +-- StructuralReasoner.solve(train_pairs, test_inputs)
           reasoning_engine.py:457
           |
           +-- WorkingMemory(adapter, train_pairs, test_inputs)
           |   reasoning_engine.py:163
           |   Caches: train_objects, classifications, same_structure
           |
           +-- Phase 0: Episodic retrieval
           |   reasoning_engine.py:478
           |   ReasoningMemory.compute_task_signature(adapter, train_pairs)
           |   reasoning_engine.py:372
           |   ReasoningMemory.retrieve_similar(sig, k=5)
           |   reasoning_engine.py:344
           |   WorkingMemory.prime_attention(retrieved)
           |   reasoning_engine.py:234
           |   (If replay succeeds: return immediately with source="episodic_recall")
           |
           +-- Phase 1: Discriminative filtering
           |   _try_discriminative_filter(train_pairs, test_inputs, wm)
           |   reasoning_engine.py:980
           |   |
           |   +-- _find_discriminative_property(objects_per_pair, classifications)
           |   |   reasoning_engine.py:1021
           |   |   Scans 81 properties, finds one that perfectly separates kept/removed
           |   |   Returns: (property_name, keep_when_true)
           |   |
           |   +-- LOO cross-validation:
           |   |   For each pair i, train on all-but-i, apply to i, check match
           |   |   If any LOO pair fails: return None (not sound)
           |   |
           |   +-- _apply_filter(adapter, test_input, property_name, keep_when_true)
           |       reasoning_engine.py:1069
           |       Returns: predicted output grid
           |
           +-- On success, _commit_to_memory(train_pairs, hypothesis)
               reasoning_engine.py:531
               |
               +-- ReasoningMemory.store_episode(sig, hypothesis)
               |   reasoning_engine.py:335
               |
               +-- If conjunction was used: ReasoningMemory.mint_conjunction(name, predicate_fn)
                   reasoning_engine.py:299
```

### After the solver returns:

```
2. PortfolioSolver._select_best(...)
   portfolio.py:300
   |
   +-- Counts agreement: how many solvers produced identical predictions
   +-- Scores complexity via _complexity_score(meta)
   |   portfolio.py:121
   |   DSL gets bonus (score 5.0), strategies score 10.0
   +-- Returns PortfolioResult with best candidate

3. CertificateBuilder.from_portfolio_result(result, ...)
   certificates.py:46
   |
   +-- _compute_training_fit(result, adapter, train_pairs)
   |   certificates.py:158
   |
   +-- _assess_risk(...)
   |   certificates.py:200
   |   Returns: "low" / "medium" / "high"
   |
   +-- _compute_confidence(...)
   |   certificates.py:213
   |
   +-- Returns: ReasoningCertificate (17 fields)

4. ReasoningEventLog.emit("HYPOTHESIS_ACCEPTED", task_id, {...})
   events.py:106
   |
   +-- ReasoningEventLog.emit("FINAL_PREDICTION_EMITTED", task_id, {...})
       events.py:106
```

### Data Objects Created

| Object | Created At | Consumed At |
|--------|-----------|-------------|
| `WorkingMemory` | `reasoning_engine.py:163` | `_try_discriminative_filter`, `_try_filter_then_extract` |
| `PortfolioResult` | `portfolio.py:284` | `CertificateBuilder.from_portfolio_result` |
| `ReasoningCertificate` | `certificates.py:46` | Exported to JSON/markdown |
| `ReasoningEvent` (HYPOTHESIS_ACCEPTED) | `events.py:106` | `export_jsonl`, `lineage`, `replay` |

---

## Scenario 2: Task Fails, Becomes Near-Solved, Later Promoted

A task fails all views in the adaptive loop, gets stored as a near-solved state, is clustered with similar failures, new operators are invented, the task is resumed with the inventions, and it is promoted to solved.

### Phase A: Initial Failure

```
1. AdaptiveReasoningLoop.solve(train_pairs, test_inputs, task_id="abc123")
   adaptive_loop.py:590
   |
   +-- ReasoningEventLog.emit("TASK_OBSERVED", task_id, {...})
   |   adaptive_loop.py:607
   |
   +-- encode_task_signature(train_pairs)
   |   (manifold_memory module)
   |
   +-- ManifoldMemory.retrieve_topological(query_point, k=5)
   |   manifold_memory.py:209
   |   Returns: nearby solved points (if any)
   |
   +-- GeodesicSolver.solve_geodesic(query_point)
   |   manifold_memory.py (geodesic analysis)
   |
   +-- Iteration 0: view="color_cc"
   |   PerceptionSelector.next_view(None)
   |   adaptive_loop.py:383
   |   |
   |   +-- _make_adapter("color_cc") -> GridDomainAdapter(bg=0)
   |   |   adaptive_loop.py:364
   |   |
   |   +-- StructuralReasoner(adapter).solve(train_pairs, test_inputs)
   |   |   reasoning_engine.py:457
   |   |   Returns: None (no discriminative property found)
   |   |
   |   +-- FailureDiagnoser.diagnose(adapter, train_pairs, "color_cc")
   |       adaptive_loop.py:410
   |       Returns: Diagnosis(failure_type="no_discrimination", ...)
   |
   +-- Iteration 1: view="per_color"
   |   (PerceptionSelector picks next view based on diagnosis)
   |   PerColorAdapter used, same reasoning, fails again
   |
   +-- Iteration 2: view="monochrome"
   +-- Iteration 3: view="majority_bg"
   |   All views exhausted, all fail
   |
   +-- Build partial hypothesis from best diagnosis
   |   adaptive_loop.py:764-774
   |   best_partial_hyp = {"strategy": "partial_filter", "property": ..., "score": ...}
   |
   +-- LoopResult(solved=False, predictions=None, hypothesis=best_partial_hyp, ...)
   |   adaptive_loop.py:776
   |
   +-- build_near_solved_state(task_id, train_pairs, fail_result)
   |   near_solved_memory.py:262
   |   |
   |   +-- _compute_train_fit(best_hypothesis, adapter, train_pairs)
   |   |   near_solved_memory.py:332
   |   |   Returns: (0.6, [True, True, False]) -- partial match
   |   |
   |   +-- _propose_repairs(failure_type, task_signature, missing_cap)
   |   |   near_solved_memory.py:360
   |   |   Returns: [RepairAction("add_conjunction", ...), RepairAction("add_spatial_property", ...)]
   |   |
   |   +-- Returns: NearSolvedTaskState(
   |       task_id="abc123", train_fit=0.6, is_near_solved=True,
   |       failure_type="no_discrimination", best_hypothesis={...},
   |       repair_frontier=[...], views_tried=["color_cc", "per_color", "monochrome", "majority_bg"]
   |     )
   |
   +-- NearSolvedMemory.store_partial(state)
   |   near_solved_memory.py:136
   |   Stores state, adds point to MemoryManifold
   |
   +-- ReasoningEventLog.emit("NEAR_SOLVED_STORED", task_id, {is_near_solved: True, ...})
       adaptive_loop.py:792
```

### Phase B: Clustering and Invention (run_memory_growth_curriculum.py, Stage 4)

```
2. OperatorInventor.mine_from_near_solved(near_solved_memory)
   operator_invention.py:108
   |
   +-- Groups states by failure_type
   |   operator_invention.py:112-116
   |   Example: {"no_discrimination": [state_abc123, state_def456, ...], "wrong_reconstruction": [...]}
   |
   +-- Filters clusters with size >= min_cluster_size
       Returns: Dict[str, List[NearSolvedTaskState]]

3. OperatorInventor.propose_concepts(clusters, property_names)
   operator_invention.py:123
   |
   +-- _extract_near_miss_properties(discrimination_states, property_names)
   |   operator_invention.py:303
   |   Finds properties that almost discriminate but not quite
   |
   +-- _search_conjunctions(discrimination_states, near_miss_props)
   |   operator_invention.py:349
   |   For each pair (p1, p2):
   |     _conjunction_discriminates(p1, p2, states)
   |     operator_invention.py:400
   |     Check: does (p1 AND p2) perfectly separate kept/removed?
   |
   +-- For valid conjunctions:
       _mint_concept_name(expr) -> e.g. "is_symmetric_AND_touches_border"
       operator_invention.py:728
       |
       Returns: [InventedConcept(name="is_symmetric_AND_touches_border",
                   expression={"op":"and","left":"is_symmetric","right":"touches_border"},
                   source_tasks=["abc123","def456"], ...)]

4. OperatorInventor.validate_inventions(concepts, operators, adapter, tasks)
   operator_invention.py:202
   |
   +-- For each concept:
   |   _validate_concept_loo(concept, adapter, tasks)
   |   operator_invention.py:582
   |   LOO accuracy >= 0.8 required
   |
   +-- _count_concept_fps(concept, adapter, tasks)
   |   operator_invention.py:615
   |   FP rate < 0.1 required
   |
   +-- _estimate_concept_gain(concept, ...)
       operator_invention.py:667
       |
       Returns: {"validated_concepts": [concept1], "validated_operators": [...]}

5. OperatorInventor.register_validated(validated, reasoner, memory)
   operator_invention.py:252
   |
   +-- For each validated concept:
   |   ReasoningMemory.mint_conjunction(name, compute_fn)
       reasoning_engine.py:299
       Concept now available as a learned predicate in the property language
```

### Phase C: Resume and Promotion (run_memory_growth_curriculum.py, Stage 5)

```
6. NearSolvedMemory.resume_from_state("abc123")
   near_solved_memory.py:179
   Returns: NearSolvedTaskState with updated property language

7. AdaptiveReasoningLoop.solve(train_pairs, test_inputs, task_id="abc123",
                               resume_from=near_solved_state)
   adaptive_loop.py:590
   |
   +-- ReasoningEventLog.emit("TASK_RESUMED", task_id, {...})
   |   adaptive_loop.py:619
   |
   +-- Selector reset: all views available for retry
   |   adaptive_loop.py:614 (after bug fix)
   |
   +-- Best partial hypothesis injected as manifold hint
   |   adaptive_loop.py:631-633
   |
   +-- Iteration 0: view="color_cc"
   |   StructuralReasoner(adapter, memory=self.memory).solve(...)
   |   reasoning_engine.py:457
   |   |
   |   +-- Phase 4: Conjunction search now includes invented predicates
   |   |   _try_discriminative_conjunction(train_pairs, test_inputs)
   |   |   reasoning_engine.py:651
   |   |   The invented "is_symmetric_AND_touches_border" predicate
   |   |   is now in ReasoningMemory.learned_property_names()
   |   |   reasoning_engine.py:329
   |   |   It discriminates perfectly -> LOO passes -> prediction made
   |   |
   |   +-- Returns: (predictions, {"strategy": "conjunction_filter",
   |                  "conjunction": "is_symmetric_AND_touches_border"})
   |
   +-- LoopResult(solved=True, predictions=predictions, ...)
       adaptive_loop.py:721

8. NearSolvedMemory.promote_to_solved("abc123", hypothesis)
   near_solved_memory.py:183
   |
   +-- state.status = NearSolvedStatus.SOLVED
   +-- Updates manifold point with solved=True
   +-- Returns: True

9. ReasoningEventLog.emit("TASK_PROMOTED", task_id, {
       "from": "near_solved", "invented_concept": "is_symmetric_AND_touches_border"
   })
   events.py:106

10. CertificateBuilder.from_loop_result(loop_result, ...)
    certificates.py:97
    Returns: ReasoningCertificate with trace showing invention + promotion
```

### Data Objects Created

| Object | Created At | Phase | Consumed At |
|--------|-----------|-------|-------------|
| `LoopResult` (failed) | `adaptive_loop.py:776` | A | `build_near_solved_state` |
| `NearSolvedTaskState` | `near_solved_memory.py:262` | A | `store_partial`, `mine_from_near_solved` |
| `ManifoldPoint` (unsolved) | `near_solved_memory.py:143` | A | `MemoryManifold` |
| Failure cluster | `operator_invention.py:108` | B | `propose_concepts` |
| `InventedConcept` | `operator_invention.py:157` | B | `validate_inventions` |
| Validated concept | `operator_invention.py:202` | B | `register_validated` |
| Learned predicate | `reasoning_engine.py:299` | B | `StructuralReasoner.solve` |
| `LoopResult` (solved) | `adaptive_loop.py:721` | C | `promote_to_solved`, `CertificateBuilder` |
| `ManifoldPoint` (solved) | `near_solved_memory.py:198` | C | `MemoryManifold` |
| `ReasoningEvent` (TASK_PROMOTED) | `events.py:106` | C | `promotion_chains` |
| `ReasoningCertificate` | `certificates.py:97` | C | Export |

---

## Scenario 3: Property Invented from Failure Cluster

Multiple tasks fail because no single property discriminates kept from removed objects. The failure cluster triggers property invention, which proposes relational/topological predicates, validates them, and registers them into the property language.

### Phase A: Failures Accumulate

Multiple tasks fail in the adaptive loop with `failure_type="no_discrimination"`. Each produces a `NearSolvedTaskState` stored in `NearSolvedMemory`:

```
Task "t1": fails -- objects have holes but single "has_holes" doesn't discriminate
   (some kept objects have holes, some removed objects have holes)
Task "t2": fails -- same pattern, objects inside frames
Task "t3": fails -- containment-based discrimination needed

All stored via:
   NearSolvedMemory.store_partial(state)
   near_solved_memory.py:136
```

### Phase B: Property Gap Analysis

```
1. PropertyInventor.__init__()
   property_invention.py:508
   Initializes candidate factory functions:
   - 18 relational predicate families
   - Topological predicate families
   - Container predicate families
   - Pattern-membership predicate families

2. PropertyInventor.mine_from_failures(near_solved_memory, adapter)
   property_invention.py:516
   |
   +-- Iterates over near_solved_memory.states
   |   Selects states where failure_type in ("no_discrimination", "wrong_reconstruction")
   |
   +-- Groups failures by task signature similarity
   |   (embedding distance < threshold)
   |
   +-- For each cluster (>= min_cluster_size failures):
       Returns: List of failure clusters with shared failure characteristics
```

### Phase C: Relational Property Proposal

```
3. PropertyInventor.propose_relational_properties(failed_tasks, adapter)
   property_invention.py:569
   |
   +-- For each predicate factory (18 families):
   |   _make_same_shape_as_reference("largest")
   |   property_invention.py:204
   |   Returns: compute_fn that checks if obj has same shape as largest object
   |
   |   _make_inside_largest_frame()
   |   property_invention.py:252
   |   Returns: compute_fn that checks if obj is inside the largest frame
   |
   |   _make_nearest_to_unique_color()
   |   property_invention.py:268
   |   Returns: compute_fn that checks if obj is nearest to unique-colored object
   |
   |   _make_touches_marker_object()
   |   property_invention.py:304
   |   Returns: compute_fn using spatial adjacency
   |
   |   ... (14 more families)
   |
   +-- For each proposed compute_fn:
   |   _inject_scene_context(objects)
   |   property_invention.py:488
   |   (Makes all objects visible to each predicate)
   |
   |   _discrimination_score(compute_fn, obj_lists, kept_lists, removed_lists)
   |   property_invention.py:93
   |   |
   |   +-- For each training pair:
   |   |   Evaluate compute_fn on all objects
   |   |   Count: correctly_classified / total_objects
   |   |
   |   +-- Returns: float in [0, 1]
   |
   +-- Filter: keep only predicates with discrimination_score > 0.5
       Returns: List[InventedProperty] candidates
```

### Phase D: Topological and Container Properties

```
4. PropertyInventor.propose_topological_properties(failed_tasks, adapter)
   property_invention.py:638
   |
   +-- _make_has_exactly_n_holes(n=1), _make_has_exactly_n_holes(n=2)
   |   property_invention.py:355
   |
   +-- _make_is_endpoint()
   |   property_invention.py:361
   |
   +-- _make_is_junction()
   |   property_invention.py:368
   |
   +-- _make_unique_under_rotation()
       property_invention.py:375

5. PropertyInventor.propose_container_properties(failed_tasks, adapter)
   property_invention.py:691
   |
   +-- _make_inside_colored_frame()
   |   property_invention.py:395
   |
   +-- _make_outside_colored_frame()
   |   property_invention.py:410
   |
   +-- _make_contains_color(target_color)
   |   property_invention.py:418
   |
   +-- _make_frame_contains_target()
       property_invention.py:437
```

### Phase E: Staged Validation

```
6. For each candidate InventedProperty:

   Stage 1 -- Discrimination check:
   _discrimination_score(compute_fn, obj_lists, kept_lists, removed_lists, grids)
   property_invention.py:93
   Require: score > 0.5

   Stage 2 -- LOO validation:
   _loo_validate(compute_fn, obj_lists, kept_lists, removed_lists, grids)
   property_invention.py:120
   |
   +-- For each training pair i:
   |   Train on all-but-i
   |   Apply to pair i
   |   Check: predicted kept/removed matches actual?
   |
   +-- Require: LOO accuracy >= 0.8

   Stage 3 -- False positive check:
   _false_positive_rate(compute_fn, adapter, held_out_tasks)
   property_invention.py:174
   |
   +-- For tasks with no transformation:
   |   Check: does predicate incorrectly predict a transformation?
   |
   +-- Require: FP rate < 0.1
```

### Phase F: Registration

```
7. PropertyInventor.register_property(validated_prop)
   property_invention.py:852
   |
   +-- Adds compute_fn to the property language
   |   The predicate becomes available in:
   |     GridDomainAdapter.get_property(obj, prop_name)
   |     _all_property_names() -> now includes the invented property
   |
   +-- Optionally mints into ReasoningMemory:
       ReasoningMemory.mint_conjunction(name, compute_fn)
       reasoning_engine.py:299

8. ReasoningEventLog.emit("PROPERTY_REGISTERED", task_id="", {
       "property_name": "inside_largest_frame",
       "discrimination_score": 0.85,
       "loo_accuracy": 0.9,
       "fp_rate": 0.02,
       "source_family": "container",
       "n_source_tasks": 3,
   })
   events.py:106
```

### Phase G: Verification via Active Falsification

```
9. ActiveFalsifier.falsify(hypothesis_using_invented_prop, adapter, train_pairs)
   active_falsifier.py:59
   |
   +-- _probe_color_relabeling(...)
   |   active_falsifier.py:104
   |   Relabel colors in input; if invented property is color-dependent,
   |   relabeled input should produce relabeled output. If not: counterexample.
   |
   +-- _probe_distractor_insertion(...)
   |   active_falsifier.py:154
   |   Add irrelevant objects; if hypothesis changes: not robust.
   |
   +-- _probe_object_count(...)
   |   active_falsifier.py:211
   |
   +-- _probe_spatial_permutation(...)
   |   active_falsifier.py:267
   |
   +-- _probe_border_interior_swap(...)
   |   active_falsifier.py:316
   |
   +-- FalsificationResult(
         hypothesis=..., counterexamples=[...],
         score=survived/generated,  # e.g. 0.85
         probe_counts={"color_relabeling": 5, "distractor": 3, ...}
       )
       active_falsifier.py:33
```

### Data Objects Created

| Object | Created At | Phase | Consumed At |
|--------|-----------|-------|-------------|
| `NearSolvedTaskState` (x3) | `near_solved_memory.py:262` | A | `mine_from_failures` |
| Failure cluster | `property_invention.py:516` | B | `propose_relational_properties` |
| `InventedProperty` candidates | `property_invention.py:569` | C | Staged validation |
| Validated `InventedProperty` | `property_invention.py:852` | F | `_all_property_names`, `StructuralReasoner.solve` |
| `FalsificationResult` | `active_falsifier.py:33` | G | Certificate builder |
| `ReasoningEvent` (PROPERTY_REGISTERED) | `events.py:106` | F | Event log export |

### Effect on Future Solves

After property registration, the property language grows from N to N+1 predicates. The next time `StructuralReasoner.solve()` runs:

1. `_try_discriminative_filter()` (`reasoning_engine.py:980`) now scans N+1 properties including the invented one.
2. If the invented property discriminates, the task that previously failed at "no_discrimination" will now succeed.
3. The solve produces a `ReasoningCertificate` that traces back to the invention event.
4. If this was a near-solved task being resumed, `NearSolvedMemory.promote_to_solved()` records the promotion.

This completes the cumulative reasoning loop: failure -> store -> cluster -> invent -> validate -> resume -> promote.
