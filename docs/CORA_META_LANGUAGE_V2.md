# CORA meta-language V2: frozen specification

Status: **FROZEN 2026-08-20, before implementation.** Every type and combinator below is
justified by a failure family already recorded in `docs/NS_FAILURE_FAMILIES.md` and
`docs/EXPR_ROUND_TRACE.md`. Nothing is added afterwards to make a particular task solvable,
and nothing is added to make unguided search expensive: the space grows because recorded
near-solves demand these reasoning operations, not because a learned shortcut needs a large
space to look necessary. Once implementation begins, this file changes only by a dated
amendment recording what evidence forced the change.

Promotion and Lockbox tasks were not inspected. The families cited are Experience-split
measurements.

## Evidence the expansion answers

| Family (measured) | Size | Reasoning operation it requires |
|---|---|---|
| Template stamping (in-grid template, D4 + colour bijection) | 3 verified, ~11 reachable | select a source entity, transform it, anchor it, copy it |
| Lattice / periodic extension | 2 verified, ~9 reachable | infer a translation orbit, propagate values along it |
| Sequence extension (1D) | 5 characterised | order entities, continue the sequence |
| Relational connect / rays | 17 characterised (shared with families 2-3) | relate two entities, derive a direction, draw between them |
| Size-derived construction | in the same 17 | build an entity whose extent is a function of another |
| Computed-set fills (V1, already working) | 6 verified | partition, select, key, look up, paint |

## Types

```
Grid            Set[Cell]        Region          Entity
Pair[Entity]    Sequence[Entity] Orbit           Lattice
FeatureValue    Colour           Vector          Transform
Anchor          Placement        Predicate[T]    Map[K,V]
Relation[T,T]   Function[T,U]
```

## Combinators (typed productions)

```
Partition   : Grid × PartitionExpr            -> Set[Region]
Entities    : Grid × SegmentationExpr         -> Set[Entity]
Group       : Set[T] × Relation[T,T]          -> Set[Set[T]]
Pairs       : Set[T] × Relation[T,T]          -> Set[Pair[T]]
Orbits      : Grid × Relation                 -> Set[Orbit]
Order       : Set[T] × Feature[T]             -> Sequence[T]

Select      : Set[T] × Predicate[T]           -> Set[T]
Unique      : Set[T]                          -> T
ArgMin      : Set[T] × Feature[T]             -> T
ArgMax      : Set[T] × Feature[T]             -> T

Key         : FeatureExpr                     -> FeatureValue
Lookup      : Map[FeatureValue, Colour]       -> Colour
MapOver     : Set[T] × Function[T,U]          -> Set[U]
Zip         : Set[T] × Set[U]                 -> Set[Pair[T,U]]
Fold        : Set[T] × Function               -> T
Propagate   : Seed × Lattice × Domain         -> Set[Cell]
Repeat      : Function × Bound                -> Function

Transform   : Entity × TransformExpr          -> Entity
Anchor      : Entity × AnchorExpr             -> Placement
Recolour    : Entity × ColourBijection        -> Entity

Paint       : Set[Region] × Colour            -> Grid
Copy        : Entity × Placement              -> Grid
Overlay     : Grid × Grid                     -> Grid
Erase       : Set[Cell]                       -> Grid
Compose     : stage*                          -> Grid
```

Every iteration is bounded by a grid-derived limit (H×W), so every program terminates.

## Induced slot types and their learners

Enumerable slots draw from a vocabulary; induced slots are fitted from the demonstrations by
`SLOT_LEARNERS[slot_type]`, dispatched by type. Adding a learner makes that slot type usable
by every existing and future concept without concept-specific search code.

| Induced type | Learner | Fold requirement |
|---|---|---|
| `Map[FeatureValue,Colour]` | implemented (V1) | every key witnessed by ≥2 demonstrations |
| `ColourBijection` | to implement | bijection consistent on all pairs; no key seen once |
| `Transform` | to implement | one D4 element explains every instance |
| `Anchor` | to implement | placement derivable from a marker or host geometry |
| `Lattice` | to implement | vectors re-derivable per input; orbits conflict-free |
| `SequenceRule` | to implement | step derivable from ≥2 witnessed positions |

## Routing (replaces the single boolean trigger)

The V1 trigger fired on 67.7% of Experience tasks and is not really an additivity test. V2
computes a demonstration-local **failure signature** and routes to sub-grammars:

```
same_shape                      changed_cell_count
changed_on_background_fraction  preserves_nonbackground
deletes_existing_cells          recolours_existing_cells
changed_component_count         repeated_changed_shapes
template_match_evidence         translation_orbit_evidence
pairwise_alignment_evidence     panel_structure_evidence
```

| Signature evidence | Sub-grammar searched |
|---|---|
| changes confined to background regions, components preserved | computed-set |
| repeated changed shapes matching an existing entity | template / placement |
| translation-orbit evidence, periodic residue | orbit / sequence |
| pairwise alignment between entities | relational |

Every fold recomputes the signature from its own N−1 demonstrations, so full-data and fold
runs take identical branches: the property whose absence broke the first two FTES attempts.

## Frozen protocol for the experiments that follow

1. Implement this spec once. Do not alter it between the template, lattice, relational and
   Level-3 experiments.
2. Run the same unguided discovery on each family; let `anti_unify` produce `concept_0002`,
   `concept_0003` automatically. No family-specific meta-solver.
3. Re-run `scripts/cora_level3_transfer.py`, reporting 3A (efficiency on a non-provenance
   task) and 3B (capability) separately.
4. Only then scale across Experience toward 201+.
