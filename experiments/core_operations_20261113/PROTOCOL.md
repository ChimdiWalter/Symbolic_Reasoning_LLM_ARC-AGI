# Core operations: can a hidden library operation be rebuilt from the rest?

Author: Chimdi Walter Ndubuisi

Written and frozen before any full run. Folder: `experiments/core_operations_20261113/`. Model-free, CPU only. The pilot
in section 11 was used to set the size limit and the budgets and is development only.

## 1. Question

The library has 155 grid operations (arc-dsl by Michael Hodel, MIT licence; the library text used here is the one
in `experiments/proposer_20261109/selflesion/library/LIBRARY.json`). An earlier experiment hid whole families of
them and asked a language model to rebuild what was missing; it failed. Before any more model work, a plain number:

If one operation X is hidden and is known only through examples of its own inputs and outputs, can a short
expression over the remaining library operations reproduce it? And how many examples are needed before the first
expression that fits them is actually right?

Two hiding conditions for every X. Condition (a): only X is hidden. Condition (b): X's whole family is hidden
(`experiments/proposer_20261109/selflesion/families/FAMILIES.json`, rule in `FAMILY_RULE.md`). For an operation whose
family has one member, (b) is the same search as (a) and is copied from it (marked `same_as_a`).

## 2. Credit

Bottom-up enumerative synthesis with observational equivalence is a standard technique (for example TRANSIT,
PLDI 2013, and Escher, CAV 2013). Nothing new is claimed about the method. The library is arc-dsl by Michael Hodel
(MIT licence, copyright 2023). Restoring an operation that existed is not a new capability.

## 3. Hiding is real

Every expression is executed in a namespace built per condition from the library's own source text
(`entries[name]["source"]` in `LIBRARY.json`, in the library's `order`), leaving out the hidden names. A hidden
operation therefore does not exist: a remaining operation whose body calls it raises `NameError` when the call is
reached, and an expression that raises is discarded. This holds equally when an operation is used as a function
value (the function-valued leaves come from the same namespace). Dependencies, where used (function pools, section
5), are the `deps` of the same library text. The original `dsl.py` is read only for parameter types and return
types. A "names filtered only" variant is NOT run. The library's own hand-written equivalents of `lbind` and `rbind`
are used (the original reads a function's arity, which the library text cannot).

## 4. Targets, exclusions and roster

Targets: the 155 library operations. Excluded before searching, and counted: 7 whose result is a function (compose,
chain, matcher, rbind, lbind, power, fork) and 3 whose input domain is too small to give 36 distinct argument
tuples (flip with 2 possible inputs, both and either with 4): reason recorded in each file. Left: 145 targets, so up
to 145 searches for (a) and 119 for (b) (the 26 targets with a one-member family copy (a)). The exact lists are in
the appendix. The coverage table (section 6) is printed by `coverage.py` and stored in `coverage.json`; no claim is
made that every argument type is covered beyond that table.

Held-out roster of the earlier study: its table holds out 40 names in 12 families (of 155 names in 60 families),
by its own rule (FAMILY_RULE.md section 4: seed `self-lesion-20261110`, 20 percent). Reported separately in the
summary under `held_out_by_the_earlier_study`; the names are listed in the appendix.

## 5. Invented inputs (the generator)

Seed for X: the first 8 bytes of sha256 of `coreops:` plus X's name. Everything is invented; no puzzle or task data
is read. Per draw: one base grid, 2 to 12 rows and columns, 1 to 6 colours from 0 to 9: a background colour, up to 4
rectangles (sides up to 4), and up to a sixth of the cells recoloured at random. The other arguments:

- Grid: the base grid; a second grid has the same shape in 80 percent of draws.
- Integer: a colour parameter (`value`, `replacee`, `replacer`, `fallback`, and `a`, `b` of `switch`): a colour
  present in the grid 70 percent of the time, else 0 to 9; `n`, `factor`, `num` 1 to 4 (but -20 to 30 for even,
  invert, double, halve); `i`, `j` -20 to 20; `start` 0 to 4; `stop` 2 to 10; `step` one of 1, 2, 3, -1; any other -20 to 30.
- Boolean: fair coin. Numerical: an integer -4 to 6 or a pair of them, half each.
- IntegerTuple: `dims`, `dimensions` each 1 to 5; `directions`, `offset`, `direction` one of the 8 unit steps
  (60 percent) else each -3 to 3; `start`, `loc`, `location`, `a`, `b`, `source`, `destination` a cell of the grid
  (80 percent) else each -2 to 13; others each -3 to 9.
- Object: an object of the grid (objects with random flags) 80 percent, else the cells of random indices read from
  the grid. Objects: all objects of the grid 80 percent, else 1 to 3 objects. Indices: 60 percent 1 to 8 random cells,
  25 percent the cells of an object, 15 percent a line between two cells. Patch: object or indices, half each.
  Element: object or grid. Piece: grid, object or indices, a third each.
- IntegerSet: 1 to 6 integers 0 to 9. FrozenSet: one of integer set, indices, object, objects. Tuple: 40 percent
  1 to 6 integers, 20 percent a grid, 20 percent 1 to 4 cells, 20 percent 1 to 3 integer tuples. Container: one of
  integer tuple, integer set, indices, object, objects, grid, tuple of cells. ContainerContainer: 40 percent objects,
  20 percent a grid, 20 percent a set of 1 to 3 indices sets, 20 percent a tuple of 1 to 3 integer sets.
  Any: one of an integer, a pair, a boolean, a grid, an object, indices, an integer set, an integer tuple.
- For `contained`, `remove`, `other` the value is taken from the container half of the time.
- Function-typed parameters: a function drawn from a fixed set, kept only if the operation accepts it on the tuple
  drawn (functions are tried in a seeded random order). One-argument set (unary): `UNARY`; two-argument set
  (binary, used for papply, mpapply, prapply): `BINARY`. Both are listed in section 12. `rapply` takes a tuple of two
  unary functions that accept its value. The pools leave out X's whole family and every operation that depends on a
  family member (transitively, library-text `deps`), for BOTH conditions, since one example set serves both: a hidden
  implementation never enters through an argument. The excluded names are stored in each file.
- X's output is obtained by running X in the full library namespace (nothing hidden).

Exceptions and rejection. If X raises on a drawn tuple, the draw is rejected and counted (`target_raised`). Also
counted: no function of the set works (`no_function_works`), output a function or not representable or longer than
2000 (`output_unusable`), an input longer than 2000 (`input_too_large`), a duplicate argument tuple (`duplicate`).
Duplicate policy: a tuple equal to an earlier accepted one (typed canonical encoding) is dropped, never repeated; an
operation whose domain runs out is excluded as above. At most 4000 draws and 60 CPU seconds per operation. The first 6
accepted examples are the fit examples, the next 30 the validation examples. Constant-output rule: it reads the
outputs of ALL 36 drawn examples (fit and validation) and excludes X if they take fewer than 2 distinct values
(typed canonical encoding); no operation was excluded by it in the coverage run. Example files are identified by a
hash of a canonical typed encoding (bool distinct from int, tuple from frozenset, sets in sorted order, functions
by name); an empty tuple and an empty frozenset are distinct encodings.

## 6. Generator coverage (from `coverage.py`; 145 of 155 operations get 36 valid examples)

Rows: annotation in dsl.py; columns: parameters of that annotation across the 155 operations, operations that have
one, and how many of those get 36 valid examples. The shortfall in Callable, Any, Integer and Boolean rows is the
10 exclusions of section 4. Distinct output values are as low as 2 (for example `equality`, `contained`, `greater`
return booleans); K=1 and K=2 fit examples can then not tell many rules apart, which is part of what is measured.

| annotation | parameters | operations | with 36 valid examples |
|---|---|---|---|
| ? | 1 | 1 | 1 |
| Any | 15 | 13 | 10 |
| Boolean | 9 | 5 | 2 |
| Callable | 24 | 19 | 12 |
| Container | 24 | 21 | 21 |
| ContainerContainer | 2 | 2 | 2 |
| Element | 5 | 5 | 5 |
| FrozenSet | 6 | 4 | 4 |
| Grid | 38 | 35 | 35 |
| Integer | 30 | 24 | 23 |
| IntegerSet | 2 | 2 | 2 |
| IntegerTuple | 15 | 12 | 12 |
| Numerical | 15 | 11 | 11 |
| Object | 7 | 7 | 7 |
| Objects | 1 | 1 | 1 |
| Patch | 40 | 34 | 34 |
| Piece | 9 | 9 | 9 |
| Tuple | 7 | 4 | 4 |

Excluded: only 2 of 36 valid examples in 4000 draws (1): flip; only 4 of 36 valid examples in 4000 draws (2): both, either; result is a function (7): compose, chain, matcher, rbind, lbind, power, fork

## 7. Search

Typed bottom-up enumeration by expression size (size = number of nodes) with observational equivalence: a bank of
expressions, each with its value on every example in use; expressions with identical typed values on all of those
examples are merged (the first in enumeration order is kept). Leaves: the parameters of X, the 28 named constants of
`SYSTEM_GRAMMAR.json` (`const_names`; values from arc-dsl's constants), and the grammar's function-valued names
(`fn_leaves`) that are not hidden. Internal nodes: all library operations not hidden (a function-valued result is
kept, never merged by value, and capped at 300 entries). Types are runtime tags of the values (grid, object, indices,
integer, pair, boolean, containers, function and so on); an operation is applied only to bank entries whose tags
fit its annotation. The tag set per annotation is a stated rule written once (`dslx.ACC`): Piece, Patch, Container,
FrozenSet and the others accept the tags of the sets and tuples their name allows; and a parameter annotated
ContainerContainer accepts every container tag whose elements can themselves be containers (grids, sets of cells,
objects, sets of such), that is tags G, TT, GT, O, X, OS, XS, TU, FU and empty, while integers-only tags (T, Z) stay
out. The rule was widened once, to add O and X, after the pilot showed that the library's own definition of mapply
was filtered out; it was not tuned further. An expression is kept only if it runs on every example in use and gives one usable type; a
value whose top-level length exceeds 3000 is discarded; the bank is capped at 250000 entries. Enumeration order is
fixed: size, then the library's operation order, then the split of sizes among arguments, then discovery order, so a
run is reproducible (PYTHONHASHSEED=0). Merging in the bank uses Python equality of values together with the tag set (so True and 1 inside a container
compare equal there); ACCEPTANCE of an expression as equal to X additionally requires identical typed canonical
encodings (section 5), in the search and in the validation check. I wrote a
small purpose-built enumerator; the earlier enumerator of the architecture sweep was not reused because its loader
reads files this study may not open.

Size limit: 4 (an expression of up to 4 nodes, such as `first(vsplit(grid, TWO))`). Chosen from the pilot (section
11): every pilot search ended either by finding an expression or by exhausting size 4, none by the clock or the function
cap (largest 13.3 CPU seconds), so the limit, not the clock, ends a search and the result does not depend on machine
load. Size 5 was not affordable (about ten times the cost per level).

## 8. Arms: separate searches, validation never inside a search

For each (X, condition), five separate searches, each with its own bank (separate search states):

- K arms, K in (1, 2, 3, 6): a search that sees only the first K fit inputs and outputs. Equivalence, pruning of
  expressions that raise, order and stopping all use those K examples and nothing else; a candidate that would
  raise or mismatch on a later example stays eligible. The search stops at the first expression (smallest size,
  fixed tie order) equal to X on the K examples: the chosen expression is recorded first. Only then is it evaluated
  on the 30 validation examples, which no search saw. Right: equal on all 30. Fits but wrong: equal on the K examples
  but not on all 30; an exception on a validation input is a validation failure of the chosen expression and never
  removes or replaces it. None: no expression fits the K examples within the size limit and budget.
  Consistency check, not the primary reading: for K below 6 the chosen expression is also evaluated on the fit
  examples this arm did not see (K+1 to 6) and `later_fit_equal`, `later_fit_errors` are stored; the summary counts,
  per K, how many "right" expressions fail a later fit example. `equal_all_36` marks an expression that is right and
  also equal on those later fit examples.
- Oracle-assisted coverage arm: one search over all 36 examples, stopping at the first expression equal to X on all
  36 ("expressible within the limit and budget"). This arm uses the validation examples, so it answers only whether
  X is expressible at all; its numbers are never mixed with the K arms.

CPU budget per search (process CPU time, `time.process_time`, not wall time; a hard virtual-time alarm at budget
plus 30 s as a guard): K=1 5 s, K=2 6 s, K=3 8 s, K=6 10 s, oracle 40 s; 69 s per (X, condition). These are safety
nets set at about three times the largest time seen in the pilot (K arms at most 3.3 s, oracle at most 13.3 s). A
search that ends by `budget_cpu` or `budget_bank` is reported as such, and then its result depends on the machine.
Exact pruning: an operation that takes a function has at least 2 parameters, so a function-valued entry of size s can
be used only if s + 2 does not exceed the size limit, and a function is never the target; function-making
operations are therefore not applied at sizes where their result could not be used (nothing reachable is lost).
Function-valued entries are capped at 300 per search. If the cap is reached the enumeration is not exhaustive: the
stop reason is then `size_exhausted_function_cap` instead of `size_exhausted`, a flag `function_cap_reached` is
stored per arm, and the summary counts it per arm.
Planned total: at most 264 searches (145 + 119) of 69 s = 18216 s = 5.1 CPU hours as a worst case; expected about
1 CPU hour (the pilot averaged 11.5 s per search of all five arms). Under 6 CPU hours either way.

## 9. Outcome definitions and what is reported

Per (X, condition) one JSON file. `SUMMARY.json` reports, per condition: the oracle-assisted coverage counts
(expressible, not found within this size limit and CPU budget, excluded) and by size; for each K the number of
operations whose chosen expression is right, fits but wrong, or none; stop reasons per arm; the list of operations
expressible with their expressions; total CPU seconds. "Not found" always means not found within this size limit
and CPU budget, never "cannot be built".

Core estimate from condition (a), oracle-arm expressions: a GREEDY estimate (an upper bound within this witness graph
and budget, not a minimum). Operations not rebuilt are kept as given; names outside the operations in scope are
external basis nodes; when an operation is chosen as a primitive its obligation is removed; strict progress is
asserted in every round; a topological reconstruction order with the expressions is recorded. The check is a graph
check only: the expressions were not re-executed over the final basis.

Cross-arm consistency: the summary lists operations for which some K arm's chosen expression equals X on all 36
examples while the oracle arm found nothing (the search missed a known-good expression).

Known-answer control (condition a). From the library text with `ast`: the operations whose body is a single return
of nested calls of other library operations applied to their own parameters and named constants (function-valued
library names allowed as arguments), with at most 4 nodes (`core.known_definitions`). For each target among them:
(i) that definition, run through the same machinery, must equal X on all 36 examples; (ii) the oracle arm must find
some expression. `SUMMARY.json` has `known_short_definitions`: n, definitions equal to X, found, missed with the
reason (type filter, function cap, other). "Not found" means not found by THIS annotation-typed enumerator, and
this control measures how often it misses an answer that is known to exist. A miss is reported, not repaired by
adjusting the type table. Qualifying operations: mfilter, other, mapply, lefthalf, righthalf. Result of the
development control (pilot and control runs): on the five qualifying operations (control_out, 67.4 CPU s) the definition equalled X on all 36 examples for 5 of 5, the oracle arm found an expression for 5 of 5, missed 0 (by reason: none); in the pilot subset, which holds two of them (mapply, lefthalf): found 2 of 2, missed 0.

Comparison with the library's own source dependencies (`deps` in `LIBRARY.json`): how many operations whose source
calls other library operations were rebuilt, whether any operation written in raw Python (no library calls) was,
and whether a rebuilt expression uses one of the operation's own source dependencies.

Operations whose outcome was seen before the freeze carry `in_pilot_subset` and are also counted separately
(`without_pilot_subset`): the ten pilot operations and the three further operations of the known-answer control run
(mfilter, other, righthalf), thirteen in all (`presets.DEV_SEEN_OPS`).

## 10. What this does NOT show

Finite examples are not proof of equality. The inputs are invented, small and hand-set (the typed generator and the
budgets are hand-set), not drawn from any real puzzle; nothing was run on real puzzles. Restoring an operation that
existed is not a new capability. The size limit 4 only covers very short expressions; "not found" says nothing about
longer ones. The library text of an operation that calls a hidden one fails, which is the intended hiding but also
means that a rebuilt expression cannot use anything built on the hidden one. Function-typed arguments come from
a fixed set, so function-valued behaviour is sampled thinly (19 operations take a function). The type tags are
runtime guesses, so an expression whose type varies between examples is only usable when its tag set fits the
consumer. The oracle arm reads the validation examples. Pilot numbers are development only.

## 11. Pilot and control, development only

Declared pilot subset: hmirror, rot180, width, switch, objects, lefthalf, add, mapply, ofcolor, tophalf. Used to
measure the cost of size 4 and to set the budgets. Rehearsal of the exact full-run command on this subset into
`pilot_out/` (both conditions, the five arms and the final summary): 

    cd /path/to/repository && env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B experiments/core_operations_20261113/run_all.py experiments/core_operations_20261113/pilot_out --ops hmirror,rot180,width,switch,objects,lefthalf,add,mapply,ofcolor,tophalf

(212.5 CPU seconds.) Pilot table (pilot, development only). Columns: operation, condition, rebuilt in the oracle
arm (size and expression), then the chosen expression at K = 1, 2, 3, 6 as right (R), fits but wrong (W) or none (-):

| operation | cond | oracle arm | K=1 | K=2 | K=3 | K=6 |
|---|---|---|---|---|---|---|
| hmirror | a | size 4: vmirror(dmirror(cmirror(piece))) | W | R | R | R |
| hmirror | b | not found (size_exhausted) | - | - | - | - |
| rot180 | a | size 3: rot90(rot90(grid)) | R | R | R | R |
| rot180 | b | not found (size_exhausted) | - | - | - | - |
| width | a | not found (size_exhausted) | W | W | W | W |
| width | b | not found (size_exhausted) | W | W | - | - |
| switch | a | not found (size_exhausted) | W | - | - | - |
| switch | b | not found (size_exhausted) | - | - | - | - |
| objects | a | not found (size_exhausted) | W | - | - | - |
| objects | b | not found (size_exhausted) | W | - | - | - |
| lefthalf | a | size 3: apply(tophalf, grid) | R | R | R | R |
| lefthalf | b | not found (size_exhausted) | - | - | - | - |
| add | a | size 4: subtract(a, invert(b)) | W | R | R | R |
| add | b | not found (size_exhausted) | W | - | - | - |
| mapply | a | size 4: merge(apply(function, container)) | W | W | R | R |
| mapply | b | not found (size_exhausted) | W | W | - | - |
| ofcolor | a | not found (size_exhausted) | W | - | - | - |
| ofcolor | b | not found (size_exhausted) | W | - | - | - |
| tophalf | a | size 4: first(vsplit(grid, TWO)) | W | W | R | R |
| tophalf | b | not found (size_exhausted) | W | - | - | - |

Full run (not launched): the same command without `--ops`, into a fresh folder:

    cd /path/to/repository && env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B experiments/core_operations_20261113/run_all.py experiments/core_operations_20261113/full_out

## 12. Function sets for function-typed parameters

UNARY (57 functions): identity size first last increment decrement double halve invert even positive sign flip toindices color height width uppermost lowermost leftmost rightmost ulcorner center centerofmass numcolors palette normalize merge hmirror vmirror dmirror rot90 mostcolor leastcolor asindices shape portrait square vline hline dedupe totuple toivec tojvec crement initset box corners backdrop delta neighbors dneighbors minimum maximum leastcommon asobject partition

BINARY (22 functions): add subtract multiply astuple pair equality greater both either combine intersection difference contained manhattan adjacent hmatching vmatching position product insert remove other

## Appendix: targets, families and held-out names

TARGETS (145):
identity add subtract multiply divide invert even double halve equality contained combine intersection difference dedupe order repeat greater size merge maximum minimum valmax valmin argmax argmin leastcommon initset increment decrement crement sign positive toivec tojvec sfilter mfilter extract totuple first last insert remove other interval astuple product pair branch apply rapply mapply papply mpapply prapply mostcolor leastcolor toindices uppermost lowermost height leftmost rightmost width shape portrait colorcount colorfilter sizefilter asindices ofcolor ulcorner urcorner llcorner lrcorner crop recolor shift normalize dneighbors ineighbors neighbors objects palette partition fgpartition square vline hline hmatching vmatching manhattan adjacent bordering centerofmass numcolors color toobject asobject rot90 rot180 rot270 hmirror vmirror dmirror cmirror fill paint underfill underpaint hupscale vupscale hconcat vconcat subgrid hsplit vsplit cellwise replace switch center position index canvas corners connect cover move tophalf bottomhalf lefthalf righthalf vfrontier hfrontier backdrop delta gravitate inbox outbox box shoot occurrences frontiers hperiod vperiod

FAMILIES (label: members) [60]
- identity (1): identity
- arithmetic (11): add subtract multiply divide double halve increment decrement invert crement sign
- even (1): even
- flip (1): flip
- equality (1): equality
- contained (1): contained
- set building (7): combine intersection difference insert remove initset other
- dedupe (1): dedupe
- order (1): order
- repeat (1): repeat
- greater than (2): greater positive
- size (1): size
- merge (1): merge
- largest and smallest of a container (6): maximum minimum argmax argmin valmax valmin
- most and least frequent (4): mostcolor leastcolor leastcommon color
- and, or (2): both either
- pairs of integers (3): astuple toivec tojvec
- filtering (5): sfilter mfilter extract colorfilter sizefilter
- totuple (1): totuple
- first and last (2): first last
- interval (1): interval
- product (1): product
- pair (1): pair
- branch (1): branch
- function composition (3): compose chain power
- matcher (1): matcher
- argument binders (2): lbind rbind
- fork (1): fork
- mapping (6): apply rapply mapply papply mpapply prapply
- positions and objects (7): asindices ofcolor colorcount toindices toobject asobject recolor
- bounding box (16): uppermost lowermost leftmost rightmost ulcorner urcorner llcorner lrcorner corners height width shape portrait square hline vline
- cutting a rectangle (2): crop subgrid
- translations (2): shift normalize
- neighbourhoods (3): dneighbors ineighbors neighbors
- objects (1): objects
- set of colours (2): palette numcolors
- partitions by colour (2): partition fgpartition
- shared rows or columns (2): hmatching vmatching
- distance (2): manhattan adjacent
- bordering (1): bordering
- centerofmass (1): centerofmass
- mirrors and rotations (7): hmirror vmirror dmirror cmirror rot90 rot180 rot270
- fills and paints (5): fill underfill paint underpaint cover
- one-axis upscales (2): hupscale vupscale
- concatenations (2): hconcat vconcat
- halves and splits (6): tophalf bottomhalf lefthalf righthalf hsplit vsplit
- cellwise (1): cellwise
- colour substitution (2): replace switch
- center (1): center
- position (1): position
- index (1): index
- canvas (1): canvas
- straight lines (4): connect shoot hfrontier vfrontier
- move (1): move
- box area (2): backdrop delta
- gravitate (1): gravitate
- box outlines (3): box inbox outbox
- occurrences (1): occurrences
- frontiers (1): frontiers
- periods (2): hperiod vperiod

Held-out names of the earlier study (40, in 12 families): argmax, argmin, bottomhalf, center, corners, crop, flip, height, hline, hmatching, hsplit, identity, index, lefthalf, leftmost, llcorner, lowermost, lrcorner, maximum, minimum, move, objects, portrait, replace, righthalf, rightmost, shape, square, subgrid, switch, tophalf, ulcorner, uppermost, urcorner, valmax, valmin, vline, vmatching, vsplit, width
