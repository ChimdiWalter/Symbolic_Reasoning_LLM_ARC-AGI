# Operations from blocks below the library: protocol

Author: Chimdi Walter Ndubuisi. Written on 14 November 2026 and frozen on 15 November 2026; the freeze pins this
file by hash. Draft 1 (af5f8235...) was read by the independent review before any code, as the author required; its
answers, the specifications of its static reviews and the amendments made on development evidence before the
freeze are written into this text (`PROTOCOL_DRAFT.md` keeps the history of the draft). The full run waits for the
review's check of the exact freeze. CPU only, no model.

## 0. What kind of study this is
A development comparison on a known constructed benchmark. Every operation of this library has been through the
operations study, stage A and the run of 14 November; their outcomes are known, and the whole library's source
informed this design. No number from this study is an untouched test. The examples are teacher examples of a known
missing operation, supplied by the evaluator; the system does not infer what a failure means. The study is about
finding programs. It does not test diagnosis of a failing step, autonomous growth, admission, retention, reuse or
transfer, and no result of it may be described as learned growth of a grammar.

## 1. The question
An operation X of the library is hidden with its whole family and is known only through examples of its own inputs
and outputs. Earlier, replacements were built out of the remaining library operations with at most four nodes: in
the operations study 25 of 145 operations had an expression equal on all 36 examples (21 after a stress check). In
the run of 14 November the implemented search often exhausted its four-node enumeration under the declared
demonstrations and presets without finding a fit; that is a practical limit of search coverage, not a proof that
those operations cannot be expressed.

**At a matched allocated search budget, counted in candidate combinations, does a fixed two-stage search that may also use blocks below the library
rebuild more of the hidden operations than a fixed two-stage search of the library alone that goes one node
deeper?**

## 2. What is already known, before any code
None of this is a result of this experiment.
1. **A configuration pilot** (development names only; `pilot_five_nodes.py`, `pilot_compare.json`; audited by the
   independent review, 1300 of 1300 checks). Size limit 5 instead of 4, bank cap 1,500,000 instead of 250,000 and
   allowance 60 processor seconds instead of 10, changed together, so no effect of depth alone is claimed. On the 15
   eligible development names: no right first fit gained in any arm; seven new first fits in three operations, all
   wrong; of the 51 fruitless searches 26 ended at the allowance and 25 completed the fifth level with the cap of
   300 function-valued entries reached; search time 15 to 17 times that at four nodes.
2. **A census of the library's source** (`census_source.py`, parsed, nothing executed). Sizes of the operations' own
   bodies, counted as the searches count nodes: quartiles 5, 12 and 26; with called operations inlined 8, 25, 128.
   The census read the downloaded source. The searches run a library text of 155 definitions; it equals the
   download, annotations and docstrings apart, for 153 of them and for every operation of the roster
   (`check_library_text_against_download.json`). The two that differ are `lbind` and `rbind`, hand-written
   equivalents that take any number of further arguments.
3. **A closure reading of the census** (`census_closure.py`): by the source's own decomposition, repeated cycles
   would add nothing up to steps of 10 nodes.
4. **What the earlier searches could not build** (read from the source of the frozen enumerator and measured on
   one development name, `diag_function_cap_by_block_set.json`). A function made by one of the library's seven
   function-making operations has at least three nodes, and its use takes two more. The enumerator therefore makes
   none when the size limit is four, the limit of the operations study and of every search for a missing call in
   stage A and in the run of 14 November: those searches used functions as leaves only. In a five-node search (the
   whole-program baseline of those two studies, and the configuration pilot) the cap on function-valued entries
   is reached inside `compose`, the first of the seven in library order, and the other six are never called
   (measured here with the cap at 1,000; the earlier searches had 300 and the same code path, not measured again).
   So no bank entry made by `lbind`, `rbind` or `matcher` as an applied operation existed in any earlier search.
   That is what the source proves; it is not "no partial application anywhere": as leaves the seven could be
   called inside a library operation that applies a function, as in `papply(lbind, a, b)`, and the earlier studies
   kept the resulting containers of functions in the bank. Section 6 says what this experiment does about it.

Source sizes are upper bounds on the descriptions available in the source language. They are not coverage
estimates, not lower bounds on the shortest program, and not node counts in the language C of section 3. Readings 2
and 3 are hypotheses that motivate the scope (one step, no cycles); they prove nothing about what cycles or other
blocks could do.

## 3. The block sets
### 3.1 L, the remaining library
Every library operation outside the hidden family, with the grammar's 28 named constants and its function-valued
names that are not hidden, as in the operations study. An operation that depends on a hidden one stays listed and
fails when called, as before. The hidden definitions do not exist in the namespace the searches run in.

### 3.2 C, a restricted language below the target operations
C is NOT Python and is NOT claimed adequate for writing the library. It is a restricted language: **eager, total
on the examples in use, immutable, and without variables.** It was chosen by reading which constructs the source of
the whole library uses (`census_syntax.json`, `census_call_forms.json`), the targets' bodies included, as an
aggregate inventory. It is "below-target primitives plus seven retained higher-order library operations", not a
library-free core. No block carries a target's name; several blocks are semantically equivalent to a target
operation (`c_len` and the target `size`, for example), which is why section 8 reads the primary on a stratum.

What the restriction means:
- **Eager and total.** Every argument of a block is evaluated on every example before the block is applied, left
  to right. An expression that raises on any example in use does not exist in the search. So `c_if_else`, `c_and`
  and `c_or` evaluate all their arguments: a program that needs a guard to avoid an error, a short circuit, or a
  comprehension whose condition protects its body is outside C.
- **Immutable.** Values are Booleans, integers, tuples and frozensets, nested. A tuple keeps order and duplicates.
  A frozenset has no duplicates; two frozensets with the same elements are the same value whatever order they come
  in. The source's `list(...)` is read as a tuple with the same order and duplicates, its `set(...)` as a
  frozenset. Mutation, assignment, loops, statements and dict displays are outside C.
- **Order.** A block that walks through a container (`c_tuple`, `c_enumerate`, `c_zip`, `c_first`, `c_map_tuple`,
  `c_keep`, `c_pairs`, `c_max` and `c_min` on ties) takes the elements in the order Python gives for that object.
  For a frozenset that order is not part of its value.
- **Booleans and integers.** `c_is_integer` is Python's `isinstance(x, int)` and is therefore true of a Boolean, as
  in the source. `c_and`, `c_or`, `c_not` take Booleans only and return a Boolean (Python's `and` and `or` return
  an operand; that use is outside C). The condition of `c_if_else` and every result of the predicate of `c_keep`
  must be a Boolean; Python's truthiness of other values is outside C.
- **No variables.** There is no lambda and no binding. A function value is either a leaf or made by one of the
  seven retained library operations `compose`, `chain`, `fork`, `lbind`, `rbind`, `matcher`, `power`. These seven
  do not make every lambda or comprehension of the source expressible. A comprehension whose inner container
  depends on the outer variable is outside C; `c_pairs` is the product of two independent containers.
- **Function-valued leaves.** In C: every block of C with one or two parameters whose result is not a function,
  under its block name, and the function-typed parameters of the target. In L and LC also the grammar's
  function-valued names that are not hidden. A function made inside a search is never merged with another one and
  counts against the cap of section 6. No function value is ever compared for equality.
- **No block of C returns a function.** A block of C whose result would be a function, or a value that holds a
  function anywhere inside it, raises, and the expression does not exist. So inside C a function value is only ever
  a leaf or the result of one of the seven retained operations; the enumerator accounts for those by the identity
  of their expression tree and never by a name.
- **Every call is checked, whoever makes it.** Each block of C validates its own arguments against its declared
  domains and its own result against the bounds below every time it is called: by a tree, as a function-valued
  leaf through a retained operation, by a call block, a comprehension block, a key or a predicate, or by a
  function that came in as an input. A wrong number of arguments or a value outside a domain is an ordinary error
  and the expression does not exist.
- **Library operations** are not rewritten. One rule is added for every search of this experiment, whatever its
  block set: **a container never holds a function.** The wrapper around every library operation handed to the
  enumerator (section 10) treats a result that holds a function anywhere inside a container as an ordinary error,
  so that expression does not exist; a block of C refuses such a result itself. A result that is itself a function is kept only from the seven retained operations
  (the only operations of this library whose declared result is a function); from any other operation it is an
  ordinary error. So in every bank a function value is a leaf or the result of one of those seven; it is identified
  by its expression tree, never merged, never compared, and it counts against the cap of section 6. Canonical text
  writes a function by its name; it is never computed for a value that is or holds a function, and a final check
  rejects such a value before any comparison. (One other place writes a function by its name: the key that tells
  two input tuples apart writes a function-typed argument by its library name, as the generator's own keys do.
  No output and no bank value is written that way.)
  *This departs from the earlier studies* (amendment of 14 November after the independent review's note, made
  before any search was run with this experiment's code; the configuration pilot of section 2 used the earlier code
  and the earlier behaviour): there a container of functions could sit in a bank, was merged with another
  when Python found the two equal (for functions: the same object) and did not count against the cap. The saved
  records were read before the rule was written (`check_function_containers_in_records.json`, a reading of the
  text of expressions, nothing evaluated): among the 205, 937 and 668 distinct expressions recorded by the
  operations study, stage A and the run of 14 November, none passes a function-making operation as a value and
  none uses `rapply`, the operation that takes a container of functions. The rule also removes one known cause of
  differences between processes: the hash of a function is its identity, so the order in which a set of functions
  is walked can differ from one process to another.
- **What a block of C can be handed.** A block checks its arguments against their domains at the top level and
  validates what it returns, and what any function it calls returns, at every depth. Arguments are not walked
  through on every call: that would make a block such as `c_len` cost a full pass over its argument. The rule that
  a container never holds a function does not need it, for a reason that rests on the declared block sets and size
  limits. In a search over C no function-making operation is a leaf, and the functions that the generator passes
  in as arguments are drawn from two fixed lists of library operations that return data; so no function value
  returns a function, and no value that holds a function can arise anywhere, not even inside one call. In a search
  over LC, at four nodes, every function value that is called is a leaf (a function made by one of the seven needs
  three nodes and its use two more), and each of the thirteen library operations that call a function they are
  given calls it on elements of its container arguments, on pairs of them, or on the integer 0 (`valmax` and
  `valmin` of an empty container); none of these holds a function. What this shows is that no block of C is handed
  a value that holds a function. It does not say that no container of functions ever exists inside a search over
  L or LC: a library operation can build one within a single call (`papply(lbind, a, b)` does), and its wrapper
  refuses the result before it reaches the bank. A larger size limit for LC, a function from outside these lists,
  a wider `Any` domain or a new pool of functions would need the argument made again. Two checks stand beside it;
  neither is a proof. Every search counts the results that its wrappers refused
  because they held a function; in L and LC these are many (a function-making operation passed as a leaf to an
  operation that applies it, as in `papply(lbind, a, b)`). And a development test runs whole searches over C and
  LC with a walk through every argument of every block: it must find no argument that holds a function.
- **Bounds, and what they do not cover.** Where the size of a result follows from the arguments (a range, the
  pairs of two containers, a concatenation) it is checked before the result is built. Where only an upper bound
  follows (a union of two sets, a set made from a container: at most the sum of the sizes of the arguments) the
  result is built and then checked. Every value that a block
  returns, and every value returned by a function that a block calls, is validated at once: no container with more
  than 3,000 elements at any depth, no more than 8 levels of nesting, no integer of more than 40 bits. A violation
  raises and the expression does not exist. This holds on every route by which a function value is called: a call
  block, a comprehension block, a key, a predicate, or inside the result of a retained operation. A called function
  is opaque: it may allocate before it returns, and no check can come before that. Such calls are bounded only by
  the enclosing limits: the processor-time safety limit and hard stop of the search, the guard of a final check, and a
  ceiling of 32 GB on the memory of the process. Reaching the memory ceiling is an infrastructure stop and is
  reported as incomplete. A nested call never starts, resets or disarms a deadline that is already active.

The catalogue (the frozen file `blocks_c.py` is the executable form; every block costs one node; a leaf costs one
node). Parameter domains are the type names of the earlier studies (`dslx.ACC`).

| block | Python form | parameters | result |
|---|---|---|---|
| `c_len` | `len(c)` | Container | Integer |
| `c_abs` | `abs(a)` | Integer | Integer |
| `c_tuple` | `tuple(c)` (also `list(c)`) | Container | Tuple |
| `c_frozenset` | `frozenset(c)` (also `set(c)`) | Container | FrozenSet |
| `c_enumerate` | `tuple(enumerate(c))` | Container | Tuple of pairs |
| `c_zip` | `tuple(zip(a, b))` | Container, Container | Tuple of pairs |
| `c_zip_star` | `tuple(zip(*c))` | ContainerContainer | Tuple |
| `c_range1`, `c_range2`, `c_range3` | `tuple(range(...))` | one, two, three Integers | Tuple |
| `c_int` | `int(x)` | Boolean or Integer | Integer |
| `c_first` | `next(iter(c))` | Container | Any |
| `c_max`, `c_min` | `max(c)`, `min(c)` | Container | Any |
| `c_max_default0`, `c_min_default0` | `max(c, default=0)` | Container | Any |
| `c_max_key`, `c_min_key` | `max(c, key=f)` | Container, Callable | Any |
| `c_max_key_default0`, `c_min_key_default0` | `max(c, key=f, default=0)` | Container, Callable | Any |
| `c_max2`, `c_min2` | `max(a, b)` | Integer, Integer | Integer |
| `c_sorted_key` | `tuple(sorted(c, key=f))` | Container, Callable | Tuple |
| `c_sum` | `sum(c)` | Container | Integer |
| `c_is_integer`, `c_is_tuple` | `isinstance(x, int)`, `isinstance(x, tuple)` | Any | Boolean |
| `c_like` | `type(c)(items)`, for a tuple or a frozenset `c` | Container, Container | Container |
| `c_add`, `c_sub`, `c_mul` | `a + b`, `a - b`, `a * b` | Integer, Integer | Integer |
| `c_floordiv`, `c_mod` | `a // b`, `a % b` (zero divisor raises) | Integer, Integer | Integer |
| `c_neg` | `-a` | Integer | Integer |
| `c_concat` | `a + b` | Tuple, Tuple | Tuple |
| `c_set_difference`, `c_union`, `c_intersection` | `a - b`, `a \| b`, `a & b` | FrozenSet, FrozenSet | FrozenSet |
| `c_eq`, `c_ne` | `a == b`, `a != b` | Any, Any | Boolean |
| `c_lt`, `c_le`, `c_gt`, `c_ge` | `a < b` and so on | Integer, Integer | Boolean |
| `c_in`, `c_not_in` | `x in c`, `x not in c` | Any, Container | Boolean |
| `c_and`, `c_or` | `a and b`, `a or b`, both evaluated | Boolean, Boolean | Boolean |
| `c_not` | `not a` | Boolean | Boolean |
| `c_pair`, `c_single` | `(a, b)`, `(a,)` | Any, Any; Any | Tuple |
| `c_set1` | `{a}` | Any | FrozenSet |
| `c_item0`, `c_item1` | `x[0]`, `x[1]` | Tuple | Any |
| `c_item` | `x[i]` | Tuple, Integer | Any |
| `c_reverse` | `x[::-1]` | Tuple | Tuple |
| `c_slice`, `c_slice_to`, `c_slice_from` | `x[a:b]`, `x[:b]`, `x[a:]` | Tuple and Integers | Tuple |
| `c_if_else` | `a if c else b`, both evaluated | Boolean, Any, Any | Any |
| `c_call1`, `c_call2` | `f(x)`, `f(x, y)`: a call of a function value | Callable and one or two of Any | Any |
| `c_map_tuple` | `tuple(f(e) for e in c)` (also `map`) | Callable, Container | Tuple |
| `c_map_set` | `frozenset(f(e) for e in c)` | Callable, Container | FrozenSet |
| `c_keep` | `tuple(e for e in c if p(e))` | Callable, Container | Tuple |
| `c_pairs` | `tuple((i, j) for i in a for j in b)` | Container, Container | Tuple of pairs |
| `c_issubset` | `a.issubset(b)` | FrozenSet, FrozenSet | Boolean |
| `c_count`, `c_index` | `c.count(x)`, `c.index(x)` | Tuple, Any | Integer |

*Amendment of 14 November, made before any block was run on a target:* `c_call1` and `c_call2` were added when
the controls' definitions were lowered into C (section 9) and one form of the source turned out to have no block.
The source calls a function-valued parameter directly 13 times with one argument and 5 times with two, outside
the seven retained operations in `valmax` and `valmin` (the other calls sit inside comprehensions, which have
their own blocks). No outcome existed when this was added.

Constants of C: the grammar's 28 named constants (the same as for L) and the two empty containers. The seven
retained library operations are listed in section 3.2 above; they are present for a target only if they survive
that target's own hiding (they are never exempted from it), and the setup pass records for every target that they
do.

### 3.3 LC
Both together: the library's operations first, in their own order, then the blocks of C in the order of the table,
so that at equal size an expression over the library is met before one over C.

### 3.4 What a search is given
Neutral parameter names (`x0`, `x1`, ...), the runtime values of the examples in use, the blocks and leaves of its
block set, and its limits. It is never given the target's name, source, body, any witness or size derived from the
source, an earlier outcome, or anything of the final panel. The blocks are plain functions that depend on nothing
but their arguments. (The parameter types and the set of missing blocks can themselves reveal something about the
target; "never given the name" is a statement about the interface, not a claim of statistical blindness.)

## 4. Targets, strata, cohort
- **Roster.** The 145 operations searched in the earlier studies, each hidden with its whole family. The 20
  development names of stage A are used for building, tests, pilots and the rule of section 6; they are reported
  apart and never enter the primary.
- **Strata, fixed now from `census_source.json` (sha256 587956cf...) and never changed.** Outside the development
  names there are 125 operations: 35 whose *source body has at most six census nodes* and 90 whose *source body has
  at least seven* (35 of 7 to 15, 55 of more than 15). These are strata of source complexity. They do not prove
  that a short one is a renaming or that a long one has no short equivalent in C.
- **Unsupported values (the same rule for both systems).** A value that is a function, or that holds a function
  anywhere inside it, is never compared. A generator example or pooled tuple in which a container argument holds a
  function, or whose output by X is or holds a function, is unusable for every role and is counted. An argument
  that is itself a function is allowed.
- **Eligibility, decided by a setup-only pass and committed before the run.** A target is eligible when (a) the
  generator gives 66 usable examples and (b) at least 30 tuples of the *usability slice* of its pooled sequence are
  usable (X runs on them and gives a supported value of at most 3,000 top-level elements). The usability slice is
  disjoint from the final slice, and the final slice is not read by the setup pass. Of the 30 final generator
  examples the setup pass uses two things and no value: a count of those in which an argument container or the
  output holds a function (condition (a) covers all 66), and the keys of their input tuples, used only so that no
  pooled tuple repeats a generator tuple. The setup pass reads the 36 fit examples
  (to draw the pooled sequence and to check the hiding); a search receives its nine or its 36 only when its stage
  opens. Every other target is excluded with its reason. Nothing is excluded later.
- **Committed denominators.** The setup record lists, for every one of the 145 operations: development or not,
  stratum, eligible or excluded with the reason, and whether it is a control (section 9). The run must leave a
  complete record for every committed eligible target. The original 90 and 35, the exclusions by reason and
  stratum, the committed eligible numbers and the terminal numbers are all reported.

## 5. Examples, roles and their order
The generator of the earlier studies gives 66 examples for a target. By position: 0 to 8 are the nine-example fit
set; 0 to 35 the 36-example fit set; 36 to 65 belong to the final panel. The pooled sequence of a target is drawn
as on 14 November under this experiment's own seed tag, with the input rule above, and cut into the usability slice
(for eligibility only) and the final slice. The final panel is the 30 final generator examples followed by the
usable tuples of the final slice. One panel for a target, the same for every search and both systems, formed by
the evaluator from X alone; discarded draws are counted; a candidate's error on a panel input counts against the
candidate. X runs over the final slice under one guard of 20 processor seconds; if that guard runs out the panel
would depend on timing, so the target's record is incomplete (an infrastructure stop). In the setup pass the same
guard runs over the usability slice: a target is eligible on the tuples evaluated before it ran out, the timeout is
part of the committed decision, and a run whose decision differs from the committed one makes the primary
provisional (section 8).

Access is enforced by the data interface, in this order, each record sealed (hash journalled) before the next role
opens: (1) setup and eligibility; (2) the two nine-example searches, their first fits sealed; (3) the four
36-example searches, their first fits sealed; (4) each system's selected candidate (section 6), sealed; (5) the
final panel, opened last, and every final check. A nine-example search is built on its nine examples alone: it
never uses a 36-example state, bank, leaf vector or equivalence table.

## 6. Searches, the two systems, and their budgets
The enumerator is the one of the operations study (typed, bottom-up, by size, merging expressions with equal
typed values on the examples in use, first fit in a fixed order). It is run from a copy kept in this folder,
`search_bl.py`, that differs from the frozen original in two listed respects: a memory failure is never taken for
an ordinary error (section 10), and the copy returns its count of offered argument tuples and can stop at a budget
in that count (below). The original is untouched and pinned by hash, the differences are listed line by
line, and tests compare the two on the same searches. The generator of examples is run from a copy of the same
kind, `gen_bl.py`. Six searches for a target, each with a fresh state; nothing is shared between searches, block
sets, stages or targets:

| search | blocks | examples | size limit |
|---|---|---|---|
| L4-9 | L | 9 | 4 |
| LC4-9 | LC | 9 | 4 |
| L4-36 | L | 36 | 4 |
| L5-36 | L | 36 | 5 |
| LC4-36 | LC | 36 | 4 |
| C-36 | C | 36 | s |

**Limits, the same for every search.** Budget: N = 1,900,000 candidate combinations. The unit is an offered
argument tuple: one combination of arguments across the example vector, as the enumerator counts it. The check
stands before a combination is counted and offered, so a search that ends by the budget has counted and offered
exactly N argument tuples. A tuple counted is not a successful call of an operation nor a measure of semantic work,
even when no safety limit fires. The same search reaches the same tuple, and so the same prefix of the
enumeration, only with the same data, source, order and caps and with no infrastructure stop; the setup and the
generation of examples keep their guards in processor time.
A combination is not a processor second. Over the 17 eligible development names in `pilot_s_2.json`, the median
number of offered tuples per processor second of the enumerator was about 36,000 in L5-36, 33,000 in LC4-36 and
60,000 in C-36 at four nodes (35,649, 33,153 and 60,252), so equal budgets are not equal time, and the consumed
processor time of every search is reported. Processor time is a safety limit only, on two clocks: the enumerator
compares the processor time of the process (user plus system, Python's process_time) with 600 seconds every 128
offered tuples, and its own hard stop is a virtual interval timer (ITIMER_VIRTUAL, user processor time only) set
to 630 seconds. Neither is an exact ceiling on total processor time or on wall time. Reaching either is an
infrastructure stop, reported as incomplete and never as "none".
Cap on bank entries: 1,500,000. Cap on function-valued entries: 16,000 (the leaves count towards it; a later
paragraph says why this number). Value bounds as in section 3.2. All four 36-example searches always run. An
unused budget is discarded, never moved to another search.

**Why the budget is counted in combinations, and how N was set** (amendment of 14 November on development
evidence, before the freeze, accepted by the independent review). The first pilot and development run used a
binding allowance of 60 processor seconds per search (`pilot_s.json`, `dev_out1`; kept as the record of that
budget). On this machine, which other jobs share, where a search ended at that allowance depended on the load, so
the same search could end at different points in two runs. The enumerator counts combinations the same way in
every run, so the budget was moved to that count. N was fixed by a rule written before it was applied
(`derive_n.py`, record `N_RECORD.json`): the median, over the 17 eligible development names, of the offered tuples
counted by L5-36 when it ended under the allowance of 60 processor seconds, including the two searches that ended
by finding a fit before the allowance (`ticks_measure.json`, median 1,931,904), rounded down to two significant
digits. It is the median of observed prefixes, not a rate of 60 seconds of throughput for every name; under that
allowance every fruitless L5-36 ended at the allowance. N is a constant from then on; the noise of that one
measurement is in its value, and no later run changes it. The local copy of the enumerator takes the budget as
one more listed change (`search_bl.py`); with the budget off it enumerates as before. A check under a different
concurrent load (`load_check.sh`, `load_check_compare.json`, development names): the development run was made
again, pinned to one hardware thread while a processor burner ran on the other thread of the same core. Each
search took 1.6 to 2.0 times the processor seconds of the first run, and every record and the summary were the
same in every field except times and memory readings (778 such fields differed, no other field). The fit of
L5-36 on other, for example, came after the same 1,774,436 combinations in both runs, after 49.8 processor seconds
in the first and 90.6 in the second: beyond the earlier allowance of 60.

**Function-making, one rule for every block set** (amendment of 14 November on development evidence, made before
the pilot for s was run; the first record, with the cap at 1,000 and no rule, is kept as
`diag_function_cap_by_block_set.json`). With a cap of 1,000 the first function-making operation in library order
used all of it at three nodes and the other six were never called (section 2, item 4); and most of what it made
could never be called, since `compose` of a function of two parameters fails on every call. Two things change.
- *An arity rule in the wrapper of the seven retained operations.* Under the size limits of this experiment every
  function argument of a function-making application is a leaf (a made function has three nodes and could become
  an argument only at a limit of seven), and every function-valued leaf has a fixed number of parameters (a test
  asserts it; an argument without a fixed signature is never judged, and no function is refused because it takes
  a variable number of arguments). An application that could only produce a function failing on its number of
  arguments is an ordinary error. `compose`, `chain` and `matcher` need functions of exactly one parameter; `fork`
  an outer function of exactly two and two of one. `lbind` and `rbind` (in the library text that runs:
  `lambda *rest: function(fixed, *rest)` and its mirror) refuse a function of one parameter, which once bound
  could only be called with no argument; nothing in these block sets calls a function with no argument. `power`
  needs a function of one parameter: for n above 1 anything else fails on every call; for n = 1 the result is the
  function itself, already present as a leaf, and refusing it is a declared rule against a duplicate, not against
  a failing function. This is a pruning policy that agrees with the numbers of parameters. It is not a proof
  that every function it admits can ever succeed: `compose(c_len, c_abs)` passes it and its declared domains
  conflict. The rule creates no value, and it is a change of the search: it can change which trees are met, the
  first fit and the use of time and memory. One visible effect: a consumer applied to a container that is empty
  on every example never calls its function, so such an expression could name a function that can never run;
  with the rule it names the first that can.
- *A cap set by a count, not by an outcome:* 16,000. From signatures and leaf lists alone
  (`structural_function_bound_2.json`; nothing searched), with no name hidden and every one of a target's
  parameters counted at once as a function leaf of one parameter, as one of two or more, as a data leaf and as an
  integer leaf, the function-valued leaves plus every application the rule allows at three nodes number at most
  12,556 in a search over L and 5,234 in a search over C, for any operation of the roster (the independent review
  derived the same two numbers). These are upper counts, not measured entries. In LC at four nodes no function
  is made. So at three nodes no function-making operation is cut by the cap or by the order of the seven, which
  stays the library's. That ends the starvation at three nodes and nothing more: at four nodes, reached only by C
  when s = 6, the cap can be reached in that order (arithmetic on available candidates for the development name
  `backdrop`, not a measurement: 64 leaves, 4,083 applications at three nodes and 12,167 of `chain` alone at four
  make 16,314), so `fork` and the applications of `lbind`,
  `rbind`, `matcher` and `power` to larger arguments can still be cut. Every search records, for each of the seven
  and each size, the applications admitted and refused by reason, and the point where the cap was reached. The
  bound holds for these block sets and limits only; it does not extend to LC at five nodes or to another pool of
  functions. What the added functions cost in time is measured by the pilot for s, which is run with the rule and
  the cap in force for all six searches, with the same budget, bank cap and rule for s.

**The size limit s of C, by a numeric rule on the development names before the freeze.** C-36 is run on every
eligible development name at s = 4, 5 and 6. s is the largest of these for which at least 80% of the searches that
find no fit end by completing level s (with or without the function cap reached) and not by the budget or the
bank cap; a size at which no development search is fruitless qualifies; if none qualifies, or no development name
is eligible, s = 4. The pilot's table gives levels completed without the function cap and with it apart. Counting a level
completed with the function cap reached is a bounded tuning policy; it does not make such a search exhaustive. The
pilot's table is published. The rule was first applied under the allowance of 60 processor seconds
(`pilot_s.json`). With N fixed it was applied again, unchanged, under the combination budget (`pilot_s_2.json`),
and only that second application sets s; s was not carried over from the first.

**The pilot, run again on 14 November under the combination budget, with the rule and the cap above in force**
(`pilot_s_2.json`; 17 of the 20 development names eligible; 36 fit examples; no final panel opened). C-36 at four
nodes: 2 fits, and all 15 fruitless searches completed the level with no cap reached. At five and at six nodes: 3
fits each, and all 14 fruitless searches ended by the budget, after exactly N offered tuples, with only four nodes
completed; at six nodes all 14 had also reached the function cap. **So s = 4 by the rule.** The first pilot, under
the allowance (`pilot_s.json`), had the same endings for C-36 at each size. Three things follow and are stated here
before any outcome on another operation. (1) At a limit of four no function is made in C or in LC, so the
function-making rule and its cap bear on one of the six searches only, L5-36. A sensitivity reading on the
development names under the allowance (`sensitivity_l5_rule.json`; the rule and cap on against off with a cap of
1,000) found no name with a right first fit under one setting and not under the other. (2) Every fruitless L5-36
of the pilot (15 of 15) ended by the budget with four nodes completed: the library-only system's second stage is a
bounded search of part of the fifth level, in library order, cut at the same combination in every run. (3) Under
the allowance LC4-36 ended with three nodes completed on 4 of the 17 names. Under the budget it completed four nodes
on all 15 fruitless development names (the largest used 1,585,719 combinations, below N). On another operation it
can still end by the budget before four nodes are complete, and then the smaller-blocks system can miss a
four-node expression over the library that L4-36 finds. That is a cost of the larger block set at the matched
budget and stays in the primary; the paired table LC4-36 against L4-36 and the list of such targets are published
(section 8).

**The two systems, each a fixed portfolio selected on fit alone.**
- *Library-only:* if L4-36 found an expression equal to X on all 36 fit examples, that expression is selected;
  otherwise the first such expression of L5-36, if any; otherwise nothing.
- *Smaller-blocks:* the same rule with LC4-36 first and C-36 second.

The selected expression of each system, its stage and the reason are sealed before the final panel is opened. The
final panel never changes a selection: a selected expression that is wrong on the final panel is the system's
answer, and no other stage, search or expression replaces it. Each system is allocated the same 2N = 3,800,000
combinations for a target, N to each of its two 36-example searches; that is a matched allocated budget of
combinations, not equal processor time and not equal consumed combinations. The library-only system is a
two-stage deeper-library portfolio, stronger than four nodes alone; it is not claimed to be the best possible use
of its budget, and a search that ends at a cap or by the budget is not exhaustive.

**How a search ended is kept apart:** found; size limit completed with no cap reached; size limit completed with
the function cap reached; combination budget used up; bank cap reached; processor-time safety limit, hard stop,
memory failure, address space near the ceiling (section 10) or another infrastructure failure (reported as incomplete, never as "none"). Only the second of these is an exhaustive search of its size
limit under the declared merging and types; every other fruitless ending is a bounded search.

## 7. Outcomes and the value contract
- **Agreement** of two values means equal typed canonical text: Booleans distinct from integers, tuples in order
  with duplicates, frozensets as sets. It is a statement about a finite panel. It is not identity of programs, not
  correctness on other inputs, and not substitutability under a consumer that reads the order of a set.
- **Found** (a 36-example search): its first expression that agrees with X on all 36 fit examples.
- **Right on the final panel** (any sealed expression): it agrees with X on every input of the complete final
  panel. An expression that raises on a panel input is wrong there.
- **Rebuilt by a system:** the system's selected expression is right on the final panel.
- **First fit at nine examples:** none, right or wrong on the final panel.
- **Order of sets, an interface reading kept apart:** for a selected expression that is right and whose output is
  a frozenset, the number of final inputs with at least two elements on which the top-level elements of the two
  outputs come in the same order, out of the number of such inputs. Nested sets are not compared for order. It
  does not change "right".
- **A final check that runs out of time.** Every batch of evaluations on the final panel runs under one guard of 30
  processor seconds. A timeout before any counterexample counts as wrong by convention, is listed, and the primary
  is also read without those targets; a positive reading needs both. A counterexample found before a timeout
  stays the counterexample and the record notes that later inputs were not checked. An input that was not
  evaluated is never called a counterexample.

## 8. The comparison, fixed before any outcome
**Primary (one decision).** On the committed eligible targets outside the development names whose source body has
at least seven census nodes, paired by target: rebuilt by the smaller-blocks system against rebuilt by the
library-only system. Let W be the targets rebuilt by the smaller-blocks system only, L the targets rebuilt by the
library-only system only; both and neither are ties. The exact two-sided sign test is
p = min(1, 2 * sum of C(W+L, k) for k = 0..min(W, L) / 2^(W+L)), and p = 1 when W + L = 0. (5 against 0 gives
0.0625; 6 against 0 gives 0.03125.) The criterion is met when all of these hold: W > L; p < 0.05; the calibration
of section 9 is valid and passed; the cohort is complete (not provisional). The full paired table, W, L, both tie
cells, W - L and each system's rebuilt count out of the number of targets in the paired table are published (that
number is a count of targets, not the budget N of section 6).

**Provisional:** a committed eligible target without a complete record, a target outside the committed cohort run
as eligible, or setup decisions in the run that differ from the committed record. A provisional primary is neither
met nor not met. **Not interpretable** is a different state: the cohort is complete and the calibration of section
9 is unavailable, invalid or failed. The two are reported in separate fields with their own reasons; when both
apply the status is provisional.

**Secondary, descriptive, uncorrected; none can replace the primary or carry a headline.** The same table on the
stratum of short source bodies and on the two halves of the longer stratum. Each of the four 36-example searches
alone, right on the final panel. LC4-36 against L4-36, with the targets where L4-36 is right and LC4-36 ended by
the budget without a right fit. An oracle union (any of a system's two found expressions right on the final
panel), labelled candidate-set coverage and never the system's result. L5-36 against L4-36. The nine-example
searches: none, right and wrong for L4-9 and LC4-9. Order of sets. Sizes of found expressions. Costs: processor
time of every search, of each system, of final checks and other overhead, and of the whole job with wall time and
peak memory from an outer record; nested subtotals are never added to the whole.

**How the result is worded.** Met: a net gain of rebuilt operations on this committed known benchmark at these
blocks, examples and limits, with the gains and losses named. Not met: the prespecified superiority criterion was
not met under these blocks, examples and limits. Not met does not mean "adds little", equivalence or no benefit.
The p-value is the declared decision rule for this finite benchmark; the operations of one library are related, so
it is not evidence about a population of operations.

## 9. Calibration and other controls
- **Known-answer controls (calibration).** The 28 operations outside the development names whose source body is a
  single return expression of at most six census nodes with no call of a library operation, no lambda and no
  comprehension (pinned by name in `presets_bl.py`). For each, the evaluator holds a *witness*: the source
  expression lowered by hand into C, with its node count, in a manifest that only the evaluator reads; the search
  code never opens it. Before the freeze a witness is checked statically against the catalogue (blocks exist,
  parameter domains, node count) and is not run. In the run, after all selections are sealed and the final panel
  is open, each witness is evaluated on the target's 36 fit examples and on the complete final panel, generator and
  pooled inputs, under the guard of a final check.
  K is the number of pinned controls that are eligible in the committed setup record and have a witness of at
  most s nodes; K is committed with the freeze and never changes afterwards. The calibration is *valid* when K is
  at least 19, every one of the K has a complete record, and every one of the K witnesses agrees with X on all 36
  fit examples and on the complete final panel; a mismatch, an unsupported result, a timeout or a missing
  validation of any witness makes it invalid, and the reason is reported. It is *passed* when it is valid and C-36
  is right on the final panel for at least ceil(0.9 * K) of them. A witness that agrees shows that the answer is
  within C at that size; whether the search finds it is the separate question the threshold asks. If it is not valid the primary is "not interpretable"; if it is valid and fails, the enumerator or its
  types are what was measured and the primary is "not interpretable". Controls without a witness within s nodes
  are listed with the reason (needs a guard or a short circuit, more than s nodes, a form without a block) and are
  not counted as failures. No block, type, limit, exclusion, control or witness is changed after any control
  outcome. At s = 4 the counted controls validate short expressions of plain blocks (one to four nodes; three of
  them, `order`, `argmax` and `argmin`, pass a function parameter to a key block). `leastcommon`, whose witness
  uses the retained operation `lbind`, has six nodes and is not counted, so no counted control uses a retained
  operation. They validate nothing about longer or higher-order programs.
  *Amendment of 15 November, by the author, before any outcome.* The minimum for K was 20 in the drafts. The setup
  pass over all names (`SETUP_RECORD_ALL.json`) then gave K = 19. Of the 28 controls, 4 are excluded by the
  generator, which finds only 41 to 51 distinct inputs where 66 examples are needed (`even`, `positive`, `toivec`,
  `tojvec`); 2 are excluded for too few usable pooled inputs (`maximum`, `minimum`); and 3 are eligible with
  witnesses of five or six nodes (`valmax`, `valmin`, `leastcommon`). With a minimum of 20 the calibration could
  not have been valid and the primary could only have read "not interpretable". The minimum was lowered to 19
  after that count was known and before any search outside the development names or any outcome on a control.
  The rule for K, the controls, the witnesses, the blocks, the exclusions and the share are unchanged. The
  calibration is then passed with 18 of 19 right: one failure is allowed where 20 controls would have allowed two.
  The breadth is one control smaller and the required fraction is higher. This is a limited procedural repair,
  not a claim that the two calibrations are statistically the same, and this text is the amended protocol, not
  the original one. The 19 controls calibrate short expressions; they are not evidence about the whole library.
  Every report of this experiment states this amendment, and the summary carries it.
- **Semantic tests on invented targets and development names** (they validate what the controls do not): the
  eager rule (a guarded program is not found and the test says why), function leaves and each of the seven
  retained operations composed with blocks of C, each comprehension block, the bounds, and a development witness
  (`color`). Invented targets are functions written in the tests, not library operations.
- **The earlier result as a check.** The expressions found by L4-36 are compared with the operations study's record
  for its second condition, and every difference is listed with its cause (66 against 36 generated examples, the
  input rule, the caps). `earlier_result_check.py` does this after the run, by rules fixed before it: expressions
  are compared as text with the earlier parameter names written x0, x1, ...; for each difference it records whether
  the first 36 of this experiment's 66 examples are the earlier 36 (the earlier study's own hash, recomputed on
  examples made again by the generator copy), whether the hidden names are the same, whether unusable generator
  examples were counted here, and whether either search ended without exhausting four nodes; a difference with
  none of these is called residual, a difference of the searches themselves (a container never holds a function,
  the arity rule and its cap, and the order of first fits that follows). Excluded and incomplete targets are listed
  apart. On the development names (`earlier_result_check_dev.json`) the examples and hidden names were the same
  for all 20, and there was no difference: the same expression for color, none for 16, and 3 excluded here.
- **Hiding.** For every target the setup pass records the hidden names, that none of them is reachable from any
  block or function leaf of any block set, and which of the seven retained operations are present.
- **Process dependence.** The setup pass and a development episode are compared across fresh processes with
  changed memory layouts and with address randomization on and off, values and not only counts.

## 10. Guards, resources, discipline
- A timeout of an evaluation guard and a memory failure are not ordinary errors. In the code of this experiment
  they are raised as exceptions that no handler of ordinary errors catches, on every path (building leaves and
  examples, the usability stream, canonical text and hashing, candidate evaluation, final and witness checks).
  Python's `MemoryError` is turned into that kind of exception at the place where it arises, before any handler of
  ordinary errors, and never only when a guard is left. Timers and handlers are restored on every exit; guards do
  not nest; a guard refuses a duration that is not a finite positive number. Every library operation handed to
  the enumerator goes through a thin wrapper that turns a memory failure into that kind of exception, applies the
  rule of section 3.2 that a container never holds a function and, for the seven retained operations, the arity
  rule of section 6; the wrapper changes nothing else. A block of C does the first two itself on every call and
  is handed to the enumerator as it is. Tests inject a timeout
  in the candidate, in X, in the comparison and outside the inner handler, an ordinary error as the control, a
  counterexample before a timeout, a real timer, and a memory failure on each of those paths.
- **The memory ceiling and the handlers of the inherited code.** The ceiling of 32 GiB is a limit on the address
  space of each process. The launcher sets it in every run mode and the tests read it back in a fresh process. It
  is a limit per process, not a measured peak of the machine. The enumerator and the generator of the operations
  study each have broad handlers of ordinary errors around evaluation; the enumerator's also encloses a few small
  allocations of its own. A memory failure caught there would be taken for an ordinary error, and no wrapper
  outside can undo that. So this experiment runs local copies, `search_bl.py` and `gen_bl.py`, in which a handler
  for `MemoryError` stands before every broad handler and raises the resource stop; nothing else differs. The
  frozen originals are untouched and pinned; the differences are listed; tests show equal results on the same
  invented and development streams, and injected memory failures at every handler, with the originals as the
  control. No other inherited function with a broad handler around evaluation is called.
  In addition the kernel's record of the largest address space the process ever had is read after every search,
  every setup stage of a target and every final or witness check, and stored. Within 1 GiB of the ceiling, or
  unreadable, the unit of work is an infrastructure stop and the process ends. That reading is conservative
  telemetry. It is not a proof that no memory failure occurred, because an allocation can fail for other reasons
  than this limit (`diag_address_space_peak.json` shows the one case of this limit).
- The stage A helper that streams usable inputs is not used (it treats its timeout as an ordinary error).
- Development names only until the freeze. Every command, the successful paths and the refusals (wrong freeze or
  setup record, an existing receipt, an output folder that is not empty, a second launch, an interrupted target, a
  missing record, a changed, missing or repeated seal, a malformed timing, a partial summary), is rehearsed in
  fresh processes on development names, on a copy for the one-launch path.
- Protocol, catalogue, sources, tests, strata, control names, witness manifest and setup record are frozen by
  hash. The independent review checks the exact freeze. One launch with an exclusive read-only receipt, never
  resumed or replayed; an interrupted run is kept and reported as incomplete.
- After the run: the frozen files are checked again, every committed target has a complete record or the primary
  is provisional, the bound on whether a guard can have fired is computed with rounding margins and unknown times
  are never taken as an all-clear, and the found expressions are read by a person before any count is reported.
  Post hoc diagnostics are labelled as such. `after_run_bl.py` makes these checks, in order: the freeze verifies;
  one read-only receipt names the freeze, the setup record and the output folder; the job started once and ended
  with exit 0; the run's manifest names the freeze, the setup record, the whole roster and the frozen policy; one
  record for every listed target and no other; every journal holds its path's events and its five seals in order,
  equal to the record; the summary equals one made again from the records, and K with its names equals what the
  freeze committed; the setup decisions and counts equal
  the committed record. A provisional primary means stop until the independent review has read the reason. It
  also reads, as information: searches within 20% of the processor-time safety limit, every guard that ran out
  and every guarded step without a mark, and the bound (a target's total processor time minus its searches, whose
  times are recorded before any guarded check, plus 0.010 s, against the shortest guard of 20 s).

## 11. Limits and level
At best this restores removed operations (level 2 of the project's plan, as restoration) from a source-informed
restricted language and seven retained library operations, on one library, with invented inputs, finite panels and
bounded search. A positive reading would be finite-panel evidence of more reconstructions under a declared
resource policy. It would not be an independently discovered core, a new primitive capability, source-independent
learning, localization of a failure, growth over cycles, retention or transfer. "Not rebuilt" always means not
rebuilt within these blocks, sizes, caps and budgets. Neither outcome shows that a guided search is the only next
method.

## 12. Prior work
Bottom-up enumerative synthesis with observational equivalence, typed component-based synthesis, and synthesis
over a general-purpose core with learned routines (DreamCoder and its successors, ledger entry A15) are standard
and are not claimed. The library is arc-dsl by Michael Hodel (MIT licence). Nothing new is claimed about the
method.

## 13. What each outcome leads to
The effect, the disagreeing targets and the practical limits of the searches are reported before a next direction
is chosen, whatever the outcome.
- **Met:** more operations are rebuilt on this benchmark with blocks below the library at the same allocated
  budget; the table by source complexity shows where.
- **Not met, calibration passed:** the specified gain was not demonstrated under these blocks, examples and limits.
- **Not interpretable:** the calibration was unavailable or failed; the result is about the tool. Types or the
  handling of functions are repaired in a new design, not after this freeze.
