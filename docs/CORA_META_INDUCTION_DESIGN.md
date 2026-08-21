# CORA Meta-Induction Layer: design

Governing rule (2026-08-20, supersedes the production-by-production plan): **no further
hand-encoded grammar productions until the shared invention mechanism exists.** REGION_FILL,
TEMPLATE_STAMP and PERIODIC_EXTEND are three independent TEST CASES for one mechanism, not
three things to type into the DSL.

## What the corpus already proves

- 69/69 Experience members of the pattern-as-function family are train-perfect and fail LOO,
  carrying 196 constant-pattern rules over 7,629 stored literal cells.
- The keyed-lookup alternative is falsified: 44 apparent fits collapse to 34 vacuous
  (per-object memos) + 6 fold-breaking + exactly 1 viable.
- Fold-level diagnosis of the six verified exemplars: 4 admit a computed program whose colour
  map is single-valued AND fold-coverable; the engine never constructs it (search miss), 1 is
  correctly refused (not fold-coverable), 1 has a genuine language gap.

One sentence covers every successful repair: **replace stored output pixels with a procedure
that recomputes them from the input.** That is the hypothesis the meta-layer operationalizes.

## The loop

```
task -> reasoner K_t -> program search
   |-> solved
   `-> failed / LOO-failed
         -> near-solve compiler        (mechanistic residual; already built, Stage A)
         -> FAILURE EXPLANATION        (which typed slot is under-specified)
         -> PROGRAM HOLE               (typed hole + per-example observations)
         -> META-GRAMMAR SEARCH        (find F with F(input_i, entity_i) = observed_i)
         -> SEMANTIC DEDUP             (observational signature over train inputs)
         -> ANTI-UNIFICATION           (repairs across tasks -> reusable concept C)
         -> FALSIFICATION              (exact execution + unchanged LOO + regression probes)
         -> ConceptRecord (provisional)
         -> INDEPENDENT TRANSFER       (witness outside provenance, previously unsolved,
                                        winning program actually uses C)
         -> K_{t+1} = K_t U {C}
```

## Program holes

A hole is emitted when a slot's `ParameterClass` is CONSTANT *and* its value varies across
demonstrations: the precise signature of memorization. The hole records:

```
HoleSpec(
    slot_path,                 # e.g. rules[2].action.params["pattern"]
    slot_type,                 # PatternExpr / ColorExpr / VecExpr ...
    observations,              # [(pair_index, entity_id, observed_value), ...]
    invariants,                # measured, e.g. added cells are background;
                               # added cells lie in bounded regions
    baseline_program,          # the train-perfect, LOO-failing skeleton
)
```

The repair target is stated as a function to be discovered, never as a named mode:

```
find F such that  F(input_i, entity_i) = observed_i   for every demonstration i
```

## The meta-language (small and immutable)

Combinators only. Named productions must be DISCOVERED as compositions of these, so that
"FillRegion" is a learned macro rather than a DSL entry:

```
Partition(grid, criterion)   criterion in {connected_same_colour, enclosed_by_entity,
                                            between_separators, colour_layer}
Select(sets, predicate)      predicate over generic set descriptors
MapKey(sets, feature)        feature over a set and its enclosing entity
Lookup(keys, table)          induced table; certified only when fold-coverable
Paint(sets, colours)         cells -> colours
Transform(cells, d4)         the eight rigid motions
Compose(f, g)
```

Two disciplines are mandatory before ranking or budget spend:

1. **Semantic dedup**: signature = the rendered output on every train input; keep the
   lowest-MDL representative of each class. MDL counts grammar nodes and induced-map entries,
   never painted cells.
2. **Fold-local recomputation**: every trigger, hole, table and key must be re-derived from
   the remaining demonstrations inside each fold. Nothing crosses a fold boundary.

## FTES routing (why this cannot flood the ordinary search)

Measured harm from injecting expression candidates into ordinary GROW enumeration: 0ca9ddb6
went from solved in 66s to unsolved in 135s. Therefore:

```
baseline search (unchanged)
  -> baseline train-perfect?  -> baseline LOO fails?  -> failure signature says
     "constant slot varies across examples"           -> THEN and only then:
        isolated candidate pool + fixed budget slice
        -> independent complete LOO validation through the unchanged gate
```

Untriggered tasks keep the old candidate stream and runtime exactly. The baseline result is
preserved regardless; the expression result is only selected if it passes the unchanged gate.

## Concept records

A discovered repair is stored with its typed AST, provenance tasks, falsification record,
semantic-dedup statistics, search cost, promotion attempts and transfer witnesses. Status is
`provisional` until a witness outside provenance is certified with the concept actually used
in the winning program; `independent-transfer` only then.

## Success criteria for the mechanism (not for any one production)

- At least one previously unsolved Experience task certified through a DISCOVERED composition,
  with the concept serialized in the winning program.
- No previously certified task lost; untriggered runtime unchanged.
- The same mechanism, unmodified, then attempted on the template and lattice families: three
  independent test cases, one invention mechanism.
