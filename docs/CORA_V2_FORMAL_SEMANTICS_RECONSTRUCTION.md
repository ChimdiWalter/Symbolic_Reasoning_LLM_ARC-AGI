# CORA V2 formal semantics: reconstruction from pre-freeze evidence

Stage 2A. This document does not design a type system. It asks a narrower question:

> What did the project demonstrably require and intend BEFORE the V2 freeze (2026-08-20)?

Every decision below cites evidence that predates the freeze and carries one of five grades
(OBSERVED, LOGICALLY_REQUIRED, SPEC_INTENDED, COMPATIBLE, UNRESOLVED). Nothing is inferred from the five template and lattice tasks that
failed afterwards, unless the same requirement was already documented before the freeze.
No solver code, grammar, router, learner, budget or experiment is changed by this document.

## Evidence provenance

A content hash proves identity, not age. Provenance and hash are therefore reported
separately, and no artifact here was git-committed before the freeze: the first commit
containing any of them is `5db9a3e`, dated 2026-08-21, after the 2026-08-20 freeze. The
strongest available provenance is machine-written output with a pre-freeze filesystem
timestamp, corroborated by the contemporaneous `RUN_HISTORY.md` ledger.

| Source | Provenance | Content hash (16) |
|---|---|---|
| `logs/nearsolve_compiler.log` | filesystem 2026-08-18T17:34, machine-written, pre-freeze | n/a |
| `outputs/expr_round_trace/trace_summary.json` | filesystem 2026-08-20T12:18, machine-written, pre-freeze | `d4850c01cce7e161` |
| `logs/expr_trace.log` | filesystem 2026-08-20T12:34, machine-written, pre-freeze | n/a |
| `outputs/cora_breakthrough/concept_registry.json` | filesystem 2026-08-20T23:08, machine-written, pre-freeze | `fe3f01a974e07282` |
| `docs/EXPR_ROUND_TRACE.md` | **mtime unusable**: reset to 2026-08-21T16:52 by a later punctuation edit. Internally dated pre-freeze and corroborated by `logs/expr_trace.log` and `trace_summary.json` | `75d00a77445c4d7a` |
| `docs/NS_FAILURE_FAMILIES.md` | mtime unusable, same reason; corroborated by `logs/nearsolve_compiler.log` | `4a0c8dde577e304a` |
| `docs/CORA_META_INDUCTION_DESIGN.md` | mtime unusable, same reason; internally dated 2026-08-20 | `34917dc69a8eaedf` |

### Freeze ordering

No exact wall-clock freeze time is recoverable: the specification records only "FROZEN
2026-08-20", and its own mtime was later reset by the punctuation edit. What is available is
**ledger order**. `RUN_HISTORY.md` is append-only, and the entry recording `concept_0001`
("LEVEL 2 ACHIEVED, concept persisted") appears at line 10191, before the entry recording the
freeze at line 10276. The Level-3 run that produced the concept is logged at 2026-08-20T22:57;
the registry file's 23:08 mtime is a later re-registration when the typed signature was added,
not its creation.

Provenance grade for the concept artefact is therefore
**PRE_FREEZE_ORDER_SUPPORTED_BY_INTERNAL_LEDGER**, not PRE_FREEZE_TIMESTAMP_VERIFIED. For the
eventual paper the correct phrase is "internally pre-specified and frozen before
implementation", never "preregistered", which would imply external timestamping.

So the correct wording throughout is "project artifact internally dated before the freeze,
current content hash X", never "cryptographically preregistered".

The load-bearing artefact is the **pre-freeze computed-set program**, discovered, certified
through the unchanged gate and anti-unified before the V2 document existed:

```
Compose( Partition(background_components),
         Select(all),
         Map( Key(?feature), Lookup(?table) ),
         Paint() )
signature: (?0 : FeatureExpr, ?1 : Map[FeatureValue, Colour]) -> GridTransform
```

Whatever the formal semantics are, they must type this term, because this term already ran.

**One structural detail decides several questions below**: the node that combines `Key` with
`Lookup` is **`Map`, not `Compose`**. `Compose` sits at the top level over whole stages. Any
claim that `Compose` constructs function terms is therefore an interpretation, not a reading.

## Evidence grades

| Grade | Meaning |
|---|---|
| OBSERVED | literally executed or explicitly represented before the freeze |
| LOGICALLY_REQUIRED | necessary for an observed artifact to type or execute |
| SPEC_INTENDED | stated by the frozen design, not independently demonstrated |
| COMPATIBLE | consistent with the evidence but not uniquely implied |
| UNRESOLVED | evidence insufficient to choose semantics |

## Term categories the evidence implies

Four categories, not three. The fourth is what the frozen table collapsed into the third.

1. **Value terms**: `Grid`, `Region`, `Entity`, `Colour`, `Placement`, `FeatureValue`
2. **Collection values**: `Set[T]`, `Sequence[T]`, `Pair[T,U]`
3. **Function terms** `A -> B`
4. **Higher-order combinators** that consume function terms: `MapOver`, `Fold`, `Repeat`

## Clarifications

### C01 Value terms — OBSERVED
`Grid`, `Region` and `Colour` are produced and consumed concretely by the executed program;
`FeatureValue` and `Colour` are named in `concept_0001`'s stored signature. Not implied: any
value-level polymorphism beyond collections.

### C02a Element-dependent evaluation exists — LOGICALLY_REQUIRED
For the observed term to execute there must be some mechanism by which `Key(?feature)` is
evaluated relative to the current region, and `Lookup(?table)` relative to the feature value
the previous stage produced. Something threads an element and an intermediate value.

### C02b Those expressions are first-class FunctionTerm[A,B] values — SPEC_INTENDED and COMPATIBLE
The V1 AST does not force this. An equally faithful reading is an implicit evaluation context
`G = {current_element, current_value, grid}` with contextual judgements

```
G[current_element : Region]  |-  Key(f)      : FeatureValue
G[current_value  : FeatureValue] |- Lookup(M) : Colour
```

under which `Map` is the operator that installs the context and threads the value, and
`Key(f)` is a **contextual expression**, not a value of type `Region -> FeatureValue`. Both
models explain the executed artefact, so first-class function values are design intent, not a
historical fact about V1.

### C03a Terminal parameters bind an expression's behaviour — LOGICALLY_REQUIRED
`Key` is given a `FeatureExpr` and still needs an element before it yields anything; the
binding of the terminal argument is separate from the supply of the element. That much the
artefact requires.

### C03b That mechanism is formal partial application or currying — COMPATIBLE
A contextual-expression evaluator achieves the same behaviour without currying, so the formal
reading is consistent but not forced.

### C04a Compose threads pipeline stages — OBSERVED
`Compose` is used at the top level over `Partition / Select / Map / Paint`, sequentially
threading compatible stages through one larger transformation. This is what the artefact shows.

### C04b Compose constructs arbitrary FunctionTerm[A,B] — COMPATIBLE, not established
The witnessed function-application site is **`Map(Key(f), Lookup(M))`**, not `Compose`. Two
readings type the observed program equally well: either `Compose` is a general function
combinator `(A->B) x (B->C) -> (A->C)`, or `Map` itself is the witnessed constructor and
`Compose` only chains whole stages. No pre-freeze artefact uses `Compose` in function
position, so the choice is not determined. **Do not retrofit the higher-order semantics we now
want onto an older pipeline combinator.** Promote C04b only if such an artefact is found.

### C05a V1 `Map` performed elementwise region-to-colour behaviour — OBSERVED
The executed node is **`Map`**, and what it did was apply an element-dependent expression
across a set of regions to obtain a colour per region. Recorded under its historical name: the
V2 operator `MapOver` is a later generalisation and the V1 node must not be called `MapOver`
retroactively, exactly as `Compose` must not be called a function combinator retroactively.

### C05b Fully polymorphic MapOver[A,B] — SPEC_INTENDED and COMPATIBLE
The pre-freeze trace records many instances of one operation per template task (39e1d7f9
id+recolour x17 and id x3; 7e0986d6 x28; fe45cba4 x2 and x2), which establishes a requirement
for **reusable iteration over a collection**. It does not uniquely imply `MapOver`: a
broadcasting renderer, an `ApplyEach`, or a collection-level transformation would also satisfy
it. The frozen document selects `MapOver`, which is design intent rather than independent
demonstration. This is strong enough to justify implementing parametric polymorphism, provided
the chain is stated accurately.

### C06 Fold reducer type — UNRESOLVED
No pre-freeze artefact contains a fold. `(T,T) -> T` is a textbook default, not project
evidence. Do not formalise `Fold`.

### C07 Repeat — UNRESOLVED
Appears in no pre-freeze artefact; the lattice trace speaks of orbit closure, not bounded
iteration of a function.

### C08 Domain — OBSERVED; Seed — UNRESOLVED
`EXPR_ROUND_TRACE` states, pre-freeze, `DomainExpr := whole grid | Region` and
`LatticeExpr := translation vectors derived per input`. `Seed` appears nowhere pre-freeze, and
the trace describes lattice extension as closure over the input's own content rather than
growth from a named seed. A lattice production may need no seed argument at all, but that must
be established rather than assumed.

### C09 Sequence participation — UNRESOLVED
The trace names a `SEQUENCE_EXTEND_1D` family (5 tasks) and says sequences live on 1D lines,
but specifies no operation over a `Sequence`. ROOT-03 stays open; `InferStep`, `Extend` and
`Render` are not invented here.

### C10 Collection of placements or grids to one Grid — UNRESOLVED
The crux of the template question. The pre-freeze material establishes the **need** for many
instances and never the **mechanism** for combining them. `MapOver` then `Fold(Overlay)`, or a
renderer taking a set, are both conceivable and the evidence prefers neither. Leaving this open
is deliberate: inventing `Fold(Overlay)` here would be exactly the retrofit this stage exists
to prevent. It also means the audit line "`Set[Placement]` is inhabited and reaches `Grid`"
remains PROVISIONAL.

### C11a A learned concept is a typed schema — OBSERVED
`concept_0001` is stored as a schema with typed free slots
`(?0 : FeatureExpr, ?1 : Map[FeatureValue,Colour]) -> GridTransform`, whose binding yields an
executable transformation. That much was produced and persisted before the freeze.

### C11b A learned concept re-enters the ordinary grammar as a production — SPEC_INTENDED, not demonstrated
Treating a concept identically to a primitive typed production is precisely what the future
Level-3 architecture is meant to demonstrate. Using that future mechanism as evidence for its
own pre-freeze semantics would be circular, so it is graded as intent. Keeping it separate
makes the eventual Level-3 result stronger, not weaker.

## Summary

| Id | Question | Grade |
|---|---|---|
| C01 | Value terms | OBSERVED |
| C02a | Element-dependent evaluation exists | LOGICALLY_REQUIRED |
| C02b | First-class FunctionTerm[A,B] | SPEC_INTENDED + COMPATIBLE |
| C03a | Terminal parameters bind behaviour | LOGICALLY_REQUIRED |
| C03b | Formal partial application / currying | COMPATIBLE |
| C04a | Compose threads stages | OBSERVED |
| C04b | Compose constructs FunctionTerm[A,B] | COMPATIBLE, not established |
| C05a | V1 `Map`, elementwise region to colour | OBSERVED |
| C05b | V2 `MapOver` : Set[A] x (A -> B) -> Set[B] | SPEC_INTENDED + COMPATIBLE |
| C06 | Fold reducer | UNRESOLVED |
| C07 | Repeat | UNRESOLVED |
| C08 | Domain / Seed | OBSERVED / UNRESOLVED |
| C09 | Sequence participation | UNRESOLVED |
| C10 | Collection to Grid | UNRESOLVED |
| C11a | Concept is a typed schema | OBSERVED |
| C11b | Concept re-enters the grammar | SPEC_INTENDED, future experiment |

ROOT-01 is **partly** resolved: function terms are LOGICALLY_REQUIRED (C02, C03), but their
constructor is not determined (C04b COMPATIBLE only). ROOT-02 is half resolved: `Domain`
OBSERVED, `Seed` UNRESOLVED. ROOT-03 is untouched by the evidence.

Stage 2B builds formal semantics from OBSERVED, LOGICALLY_REQUIRED and SPEC_INTENDED claims
only. COMPATIBLE readings do not become implementation requirements unless unavoidable, and
UNRESOLVED productions are carried as inactive declarations rather than guessed operations.
