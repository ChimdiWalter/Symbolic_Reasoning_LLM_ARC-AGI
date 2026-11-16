"""What one search is given: operations, leaves and target values for a block set, with neutral parameter names;
and the evaluator that runs a found tree later with the same operations.
Author: Chimdi Walter Ndubuisi

`build(block_set, hidden, examples)` returns (ops, leaves, Y, op_ns, leaf_ns, consts) for the enumerator (search_bl,
this experiment's copy of the frozen one) and for the later evaluation of a tree (`eval_tree_bl`):

  L    exactly what the operations study's core.build gives: every library operation outside `hidden`, in the
       library's own order, from the masked namespace dslx.library_namespace(hidden) (an operation that depends on a
       hidden one stays listed and fails when called); leaves: the parameters, the grammar's 28 named constants,
       the grammar's function-valued names that are not hidden. Only the parameter names differ: x0, x1, ...
  C    the blocks of the catalogue (blocks_c) in catalogue order, then those of the seven retained library
       operations that exist in the masked namespace, in the library's own order, as OPERATIONS; leaves: the
       parameters, the 28 named constants, EMPTY_TUPLE and EMPTY_SET, the blocks offered as function-valued leaves.
  LC   L's operations and leaves first, then the blocks and the two empty containers and the function-valued
       leaves of C (the seven retained operations are already among L's), so that at equal size an expression
       over the library is met before one over C.

A build never receives the target's name, source or body: it is given the set of names to hide and the runtime
values of the examples in use. Every call makes a fresh masked namespace and fresh lists; nothing is shared
between two searches.

THE WRAPPER. Every library operation handed to the enumerator, the seven retained ones included, goes through a
thin wrapper (`operation_wrapper`) that changes nothing but this (same name, same accepted tags, same makes_fn
flag, same value):
  - it turns a MemoryError into guards_bl.ResourceStop before the enumerator's own broad handler of ordinary errors
    can see it;
  - it applies the rule of this experiment that A CONTAINER NEVER HOLDS A FUNCTION, in every block set. A result
    that is itself a function is kept only from the seven retained operations (presets RETAINED); from any other
    operation it is an ordinary error (TypeError), so the expression does not exist. A result that is a tuple or a
    frozenset is walked at every depth for a function when at least one argument of that call is callable; if one
    is found, it is an ordinary error. (An operation that is given no function cannot return one: only the seven
    make functions and each takes one. A test runs whole searches with the walk made on every result and compares.)
  - when the switch presets ARITY_RULE is on, for the seven retained operations only and before the library
    function is called: the arity rule (ARITY_RULES below). A function argument is judged only when it has a
    fixed signature (a code object, no starred parameter, no default value, no keyword-only parameter); anything
    else (a function bound by lbind or rbind, which takes a variable number of arguments in the library text this
    study executes; a built-in) is never judged. Two reasons are kept apart:
      * a made function that could only ever fail on the number of arguments (compose, chain, matcher and fork
        with a function that does not have the one or two parameters it is called with; lbind and rbind of a
        function of exactly one parameter, which bound once could only be called with no argument, and nothing
        in these block sets calls a function with no argument): counted as function_making_refused_by_arity;
      * power(function, n) of a function that does not have exactly one parameter: counted apart, as
        power_of_a_function_without_one_parameter. For n above 1 the result fails on every call; for n = 1 the
        result is the function itself, a second entry for a leaf and not a failing function. This is a declared
        rule about duplicates, not about failures.
    The rule makes no value that did not exist.
The wrapper counts, per search, the applications it refused under each of these clauses.

THE RECORD OF FUNCTION-MAKING. In a search, the wrapper of each of the seven retained operations
(`function_making_wrapper`) also keeps, per operation and per size of the application, how many applications the
enumerator tried and what became of each: admitted to the bank, refused by the arity rule, refused as a power
duplicate, refused because the cap on function-valued entries was reached, or raised in the library's own
operation; and the point where the cap was reached. It changes nothing the enumerator sees. The size of the
application and the number of function-valued entries so far are READ from the enumerator's own frame (the local
copy search_bl, whose text is fixed by hash): the enumerator keeps both and returns neither.
A block of C is handed to the enumerator WITHOUT the wrapper (BLOCKS_WRAPPED is False): a block does both things
inside itself on every call, whoever calls it (it converts a memory failure, and its check_value refuses a
function at any depth), and none of the seven retained operations is a block. So the wrapper's counters count
library operations only; what a block refuses is an ordinary error of that block.

When leaves are built, a leaf value that is a container holding a function is refused (examples with such
arguments are unusable by protocol section 4).

EVALUATION OUTSIDE THE ENUMERATOR USES THE SAME OPERATIONS AS INSIDE IT. search.eval_tree is not used anywhere in
this experiment: it looks an applied operation and a function-valued leaf up in one namespace, so a tree evaluated
later would run without the wrapper's rule. `eval_tree_bl(tree, op_ns, leaf_ns, consts, params)` applies
op_ns[name] for an ("L", name, ...) node: the same kind of wrapped function as in the search, with its own
counters; and it takes leaf_ns[name] for an ("FN", name) leaf: the function itself, exactly the value the
enumerator's leaf holds (never a wrapper with a variable number of arguments).

makes_fn is set as core.build sets it: True for an operation whose declared result is a function (the seven
retained operations), False for every block of C. The enumerator uses the flag to skip a function-making operation
at a size where its result could not be consumed any more (a consumer of a function takes at least two arguments;
that holds for C as well: every block with a parameter typed Callable has at least two parameters), and to stop
making functions once the cap on function-valued entries is reached.

`assert_hidden_unreachable` checks that no hidden name can be reached from any operation, leaf or example value.
"""
import dis
import sys

import bl_frozen  # noqa: F401  (hash check, sys.path)
import dslx
import blocks_c as B
import guards_bl as G
import presets_bl as P
import search_bl

BLOCK_SETS = ("L", "C", "LC")
BLOCKS_WRAPPED = False
REFUSAL_COUNTS = ("function_results_refused", "containers_holding_a_function_refused", "function_making_refused_by_arity",
                  "power_of_a_function_without_one_parameter")
# The arity rule (applied only when presets ARITY_RULE is on). For each retained operation: the counter of its
# refusals, and for each function-typed parameter (by position) the test of the declared number of parameters:
# ("only", numbers): refused unless the number is one of them; ("not", numbers): refused when it is one of them.
ARITY_RULES = {
    "compose": ("function_making_refused_by_arity", ((0, "only", (1,)), (1, "only", (1,)))),                  # lambda x: outer(inner(x))
    "chain": ("function_making_refused_by_arity", ((0, "only", (1,)), (1, "only", (1,)), (2, "only", (1,)))),   # lambda x: h(g(f(x)))
    "matcher": ("function_making_refused_by_arity", ((0, "only", (1,)),)),                                   # lambda x: function(x) == target
    "fork": ("function_making_refused_by_arity", ((0, "only", (2,)), (1, "only", (1,)), (2, "only", (1,)))),    # lambda x: outer(a(x), b(x))
    "rbind": ("function_making_refused_by_arity", ((0, "not", (1,)),)),                                      # the last argument fixed
    "lbind": ("function_making_refused_by_arity", ((0, "not", (1,)),)),                                      # the first argument fixed
    "power": ("power_of_a_function_without_one_parameter", ((0, "only", (1,)),)),                            # the function applied n times
}


def new_counts():
    """The per-search counters of the wrapper, all zero."""
    return {k: 0 for k in REFUSAL_COUNTS}


def holds_function(v):
    """True when the tuple or frozenset v holds a function at any depth."""
    for e in v:
        if callable(e):
            return True
        t = type(e)
        if (t is tuple or t is frozenset) and holds_function(e):
            return True
    return False


def declared_parameters(f):
    """The number of parameters of a function value with a fixed signature, or None when it is not judged: a value
    without a code object (a built-in, a value that is not a function), or a function with a starred parameter, a
    keyword-only parameter or a default value."""
    code = getattr(f, "__code__", None)
    if code is None or code.co_flags & 0x0C or code.co_kwonlyargcount or getattr(f, "__defaults__", None):
        return None
    return code.co_argcount


def operation_wrapper(f, name=None, counts=None, always_walk=False, arity_rule=False):
    """The thin wrapper around an operation handed to the enumerator: f itself, except that
    (1) a MemoryError becomes ResourceStop;
    (2) a result that is a function is an ordinary error unless `name` is one of the seven retained operations;
    (3) a result that is a tuple or frozenset holding a function at any depth is an ordinary error; the walk is made
        when at least one argument of the call is callable (always_walk=True, used by a test, makes it on every
        result and counts in `walked_without_a_callable_argument` the refusals the condition would have missed);
    (4) with arity_rule=True and `name` one of the seven retained operations: before f is called, the arity
        rule (ARITY_RULES): an ordinary error, counted under the rule's own counter.
    counts: the per-search counters (new_counts()); refusals under (2), (3) and (4) are counted there."""
    name = getattr(f, "__name__", "?") if name is None else name
    keeps_functions = name in P.RETAINED
    arity_counter, tests = ARITY_RULES[name] if (arity_rule and keeps_functions) else (None, ())
    counts = new_counts() if counts is None else counts

    def op(*a):
        try:
            for position, kind, numbers in tests:
                if position < len(a):
                    declared = declared_parameters(a[position])
                    if declared is not None and (declared in numbers) == (kind == "not"):
                        counts[arity_counter] += 1
                        raise TypeError("%s is refused for a function of %d parameters (arity rule)" % (name, declared))
            r = f(*a)
            if callable(r):
                if keeps_functions:
                    return r
                counts["function_results_refused"] += 1
                raise TypeError("a function is the result of %s, which is not one of the seven retained operations" % name)
            t = type(r)
            if t is tuple or t is frozenset:
                given_a_function = False
                for x in a:
                    if callable(x):
                        given_a_function = True
                        break
                if (given_a_function or always_walk) and holds_function(r):
                    counts["containers_holding_a_function_refused"] += 1
                    if not given_a_function:
                        counts["walked_without_a_callable_argument"] = counts.get("walked_without_a_callable_argument", 0) + 1
                    raise TypeError("the result of %s is a container that holds a function" % name)
            return r
        except MemoryError:
            raise G.ResourceStop("memory failure in operation " + name) from None
    op.__name__ = op.__qualname__ = name
    op.__wrapped__ = f
    return op


FUNCTION_ROW = ("offered", "admitted", "refused_by_arity", "refused_as_power_duplicate", "refused_by_cap", "raised_in_the_library")


def new_function_book(n_examples):
    """The record of function-making of one search: by_operation[operation][size] holds, for the applications of
    that operation at that size, how many the enumerator tried (offered) and what became of each (the other five
    counts add up to it); cap_reached_at is the application that brought the number of function-valued entries to
    the cap, first_refused_by_cap the first one the cap refused (None when it was not reached)."""
    return dict(n_examples=n_examples, by_operation={}, admitted=0, cap_reached_at=None, first_refused_by_cap=None,
                calls_outside_the_enumerator=0)


def function_making_wrapper(f, name, counts, book, arity_rule):
    """The wrapper of one of the seven retained operations AS HANDED TO THE ENUMERATOR. For these operations it does
    what operation_wrapper does (a MemoryError becomes ResourceStop; the arity rule when it is on; the function they
    return is kept) and it writes the record of function-making into `book` (new_function_book()).

    One application is one combination of arguments, evaluated by the enumerator on every example in turn. It is
    refused by the arity rule at its first call, or raises in the library at some call, or completes all
    n_examples calls and is then offered to the bank, which admits it unless the cap on function-valued entries
    is reached. The size of the application and the number of function-valued entries so far are read from the
    enumerator's frame at that moment.

    The count of an application relies on the enumerator calling a function-making operation once per example,
    never once for all examples. That holds because a function-valued entry is never constant in the enumerator
    (its constant flag is False for the function tag), so an application with a function argument is always
    evaluated example by example; and each of the seven takes at least one function. A test compares the total
    admitted with the growth of function-valued entries inside the enumerator and fails if this stops holding."""
    if name not in P.RETAINED:
        raise ValueError("%s is not one of the seven retained operations" % name)
    arity_counter, tests = ARITY_RULES[name] if arity_rule else (None, ())
    refusal_row = "refused_as_power_duplicate" if arity_counter == "power_of_a_function_without_one_parameter" else "refused_by_arity"
    enumerator = search_bl.search.__code__
    n_examples = book["n_examples"]
    run = [0]                                                    # calls of the current application that have returned

    def note(kind):
        frame = sys._getframe(2)                                 # the caller of op
        if frame.f_code is not enumerator:
            book["calls_outside_the_enumerator"] += 1
            return
        local = frame.f_locals
        size = local["sz"]
        row = book["by_operation"].setdefault(name, {}).setdefault(size, dict.fromkeys(FUNCTION_ROW, 0))
        row["offered"] += 1
        if kind != "completed":
            row[kind] += 1
            return
        entries, cap = local["st"]["nfn"], local["max_fn"]
        if entries < cap:
            row["admitted"] += 1
            book["admitted"] += 1
            if entries + 1 == cap and book["cap_reached_at"] is None:
                book["cap_reached_at"] = dict(operation=name, size=size, function_valued_entries=entries + 1)
        else:
            row["refused_by_cap"] += 1
            if book["first_refused_by_cap"] is None:
                book["first_refused_by_cap"] = dict(operation=name, size=size, function_valued_entries=entries)

    def op(*a):
        try:
            for position, kind, numbers in tests:
                if position < len(a):
                    declared = declared_parameters(a[position])
                    if declared is not None and (declared in numbers) == (kind == "not"):
                        counts[arity_counter] += 1
                        run[0] = 0
                        note(refusal_row)
                        raise TypeError("%s is refused for a function of %d parameters (arity rule)" % (name, declared))
            try:
                r = f(*a)
            except MemoryError:
                raise
            except Exception:
                run[0] = 0
                note("raised_in_the_library")
                raise
            run[0] += 1
            if run[0] == n_examples:
                run[0] = 0
                note("completed")
            return r
        except MemoryError:
            raise G.ResourceStop("memory failure in operation " + name) from None
    op.__name__ = op.__qualname__ = name
    op.__wrapped__ = f
    return op


def retained_present(hidden):
    """Those of the seven retained operations that survive the hiding, in the library's own order."""
    lib = dslx.load()
    hidden = set(hidden)
    return [nm for nm in lib["lib_order"] if nm in P.RETAINED and nm not in hidden]


def _check_examples(examples):
    if not examples:
        raise ValueError("a build needs at least one example")
    k = len(examples[0][0])
    for args, _ in examples:
        if len(args) != k:
            raise ValueError("the examples do not have the same number of arguments")
    return k


def build(block_set, hidden, examples, ns=None, counts=None, eval_counts=None, always_walk=False, arity_rule=None, book=None):
    """(ops, leaves, Y, op_ns, leaf_ns, consts) for one search.

    block_set: "L", "C" or "LC". hidden: the names that do not exist for this search (the target's whole family).
    examples: [(argument tuple, output)], the examples in use and nothing else.
    ns: a masked namespace to use instead of a fresh one (tests only; a search always gets a fresh one).
    counts / eval_counts: the dicts (new_counts()) in which the wrappers count the results they refuse, in the
    search and in later evaluations of a tree (two sets of wrappers over the same functions).
    always_walk: tests only (see operation_wrapper). arity_rule: None takes presets ARITY_RULE.
    book: the record of function-making of this search (new_function_book(len(examples))), filled by the wrappers
    of the seven retained operations handed to the enumerator; None makes one that is not kept.
    ops: [(name, function as the enumerator applies it, accepted tag sets per parameter, makes_fn)];
    leaves: [(tree, values per example)]; Y: the outputs, a tuple;
    op_ns: {name: function as eval_tree_bl applies it}; leaf_ns: {name: the function a function-valued leaf holds};
    consts: {name: value} of the constants."""
    if block_set not in BLOCK_SETS:
        raise ValueError("unknown block set %r" % (block_set,))
    lib = dslx.load()
    hidden = set(hidden)
    k = _check_examples(examples)
    n = len(examples)
    masked = dslx.library_namespace(hidden) if ns is None else ns
    counts = new_counts() if counts is None else counts
    eval_counts = new_counts() if eval_counts is None else eval_counts
    arity_rule = P.ARITY_RULE if arity_rule is None else arity_rule
    book = new_function_book(n) if book is None else book
    if book["n_examples"] != n:
        raise ValueError("the record of function-making was made for another number of examples")

    def wrap(name, fn, tally):
        if tally is counts and name in P.RETAINED:               # in the search: the seven keep the record of function-making
            return function_making_wrapper(fn, name, tally, book, arity_rule)
        return operation_wrapper(fn, name, tally, always_walk, arity_rule)

    def wrap_block(name, fn, tally):
        return wrap(name, fn, tally) if BLOCKS_WRAPPED else fn

    def signature(nm):
        return tuple(dslx.ACC[a] for _, a in lib["sigs"][nm]), lib["rets"][nm] == "Callable"

    params = [(("P", "x%d" % j), tuple(e[0][j] for e in examples)) for j in range(k)]
    named = [(("C", c), (lib["consts"][c],) * n) for c in lib["const_names"]]
    consts = dict(lib["consts"])
    blocks = B.namespace()
    library = [nm for nm in lib["lib_order"] if nm not in hidden] if block_set in ("L", "LC") else retained_present(hidden)
    library_ops = [(nm, wrap(nm, masked[nm], counts)) + signature(nm) for nm in library]
    block_ops = [(name, wrap_block(name, fn, counts), acc, makes_fn) for name, fn, acc, makes_fn in B.ops()]
    library_leaves = [(("FN", f), (masked[f],) * n) for f in lib["fn_leaf_names"] if f not in hidden]
    block_leaves = [(("C", c), (v,) * n) for c, v in B.CONSTANTS.items()] + [(("FN", b), (blocks[b],) * n) for b in B.function_leaf_names()]
    if block_set == "L":
        ops, leaves = library_ops, params + named + library_leaves
    elif block_set == "C":
        ops, leaves = block_ops + library_ops, params + named + block_leaves
    else:
        clash = sorted(set(blocks) & (set(lib["lib_order"]) | set(lib["const_names"])))
        if clash:
            raise AssertionError("a block of C has the name of a library operation or constant: %s" % clash)
        ops, leaves = library_ops + block_ops, params + named + library_leaves + block_leaves
    op_ns = {nm: wrap(nm, masked[nm], eval_counts) for nm in library}
    leaf_ns = {}
    if block_set in ("L", "LC"):
        leaf_ns.update({f: masked[f] for f in lib["fn_leaf_names"] if f not in hidden})
    if block_set in ("C", "LC"):
        op_ns.update({name: wrap_block(name, fn, eval_counts) for name, fn in blocks.items()})
        leaf_ns.update({b: blocks[b] for b in B.function_leaf_names()})
        consts.update(B.CONSTANTS)
    for tree, vals in leaves:
        for v in vals:
            t = type(v)
            if (t is tuple or t is frozenset) and holds_function(v):
                raise AssertionError("the leaf %s has a value that is a container holding a function" % tree[1])
    return ops, leaves, tuple(e[1] for e in examples), op_ns, leaf_ns, consts


def eval_tree_bl(tree, op_ns, leaf_ns, consts, params):
    """Value of an expression tree with parameter values `params` {neutral name: value}; raises what the
    expression raises. An applied operation is op_ns[name] (wrapped as in the search); a function-valued leaf is
    leaf_ns[name] (the function itself). Arguments are evaluated first, left to right."""
    kind = tree[0]
    if kind == "P":
        return params[tree[1]]
    if kind == "C":
        return consts[tree[1]]
    if kind == "FN":
        return leaf_ns[tree[1]]
    if kind != "L":
        raise ValueError("unknown node kind %r" % (kind,))
    return op_ns[tree[1]](*[eval_tree_bl(c, op_ns, leaf_ns, consts, params) for c in tree[2:]])


# ---------------------------------------------------------------- hidden names must not be reachable
def _global_names(code, out=None):
    """The global names a code object loads, with those of the code objects nested in it."""
    out = set() if out is None else out
    for ins in dis.get_instructions(code):
        if ins.opname in ("LOAD_GLOBAL", "LOAD_NAME"):
            out.add(ins.argval)
    for const in code.co_consts:
        if hasattr(const, "co_code"):
            _global_names(const, out)
    return out


def _functions_in(v, depth=0):
    """The functions that are a value or sit inside it (tuples, frozensets, lists, sets, dict values)."""
    if callable(v):
        yield v
    elif isinstance(v, (tuple, frozenset, list, set)) and depth < 12:
        for e in v:
            yield from _functions_in(e, depth + 1)
    elif isinstance(v, dict) and depth < 12:
        for e in v.values():
            yield from _functions_in(e, depth + 1)


def reachable_hidden(hidden, functions):
    """The reasons, if any, why a hidden name can be reached from one of `functions`.

    Every function is followed through the global names its code loads (resolved in its own globals), the cells of
    its closure, its defaults and the function it wraps. A hidden name is reached when a followed function is a
    hidden definition (by the name of its code), or when a followed function loads a hidden global name that
    exists in its globals. A hidden name that is loaded but does not exist there is not reached: the call fails."""
    hidden = set(hidden)
    reasons, seen, stack = [], set(), [f for f in functions if callable(f)]
    while stack:
        f = stack.pop()
        if id(f) in seen:
            continue
        seen.add(id(f))
        code = getattr(f, "__code__", None)
        if code is None:
            inner = getattr(f, "__func__", None) or getattr(f, "__wrapped__", None)
            if inner is not None:
                stack.append(inner)
            continue                                              # a built-in: nothing of the library behind it
        if code.co_name in hidden or getattr(f, "__name__", None) in hidden:
            reasons.append("the hidden definition %s is reachable" % code.co_name)
            continue
        g = getattr(f, "__globals__", {})
        for name in _global_names(code):
            if name in hidden:
                if name in g:
                    reasons.append("%s loads the hidden name %s, which exists in its namespace" % (code.co_name, name))
                continue
            if name in g:
                stack.extend(_functions_in(g[name]))
        for cell in getattr(f, "__closure__", None) or ():
            try:
                stack.extend(_functions_in(cell.cell_contents))
            except ValueError:                                    # an empty cell
                pass
        for d in (getattr(f, "__defaults__", None) or ()) + tuple((getattr(f, "__kwdefaults__", None) or {}).values()):
            stack.extend(_functions_in(d))
        if getattr(f, "__wrapped__", None) is not None:
            stack.append(f.__wrapped__)
    return sorted(set(reasons))


def assert_hidden_unreachable(hidden, ops, leaves, namespaces, extra_values=()):
    """Raise RuntimeError when a hidden name is listed, exists in a namespace, or can be reached from an operation,
    a leaf (function-valued leaves and function-valued example arguments included), a function of a namespace
    (`namespaces`: one dict or several, such as op_ns and leaf_ns), or a function among `extra_values`.
    Returns the number of functions the check started from."""
    import builtins
    hidden = set(hidden)
    if isinstance(namespaces, dict):
        namespaces = (namespaces,)
    reasons = ["the hidden name %s is listed as an operation" % name for name, _, _, _ in ops if name in hidden]
    reasons += ["the hidden name %s is listed as a leaf" % t[1] for t, _ in leaves if t[1] in hidden]
    reasons += ["the hidden name %s exists in a namespace" % h for h in sorted(hidden) if any(h in ns for ns in namespaces)]
    reasons += ["the hidden name %s is a built-in name" % h for h in sorted(hidden) if hasattr(builtins, h)]
    roots = [fn for _, fn, _, _ in ops]
    for _, vals in leaves:
        for v in vals:
            roots.extend(_functions_in(v))
    for ns in namespaces:
        for key, v in ns.items():
            if key != "__builtins__":
                roots.extend(_functions_in(v))
    for v in extra_values:
        roots.extend(_functions_in(v))
    reasons += reachable_hidden(hidden, roots)
    if reasons:
        raise RuntimeError("hidden names are reachable: " + "; ".join(sorted(set(reasons))[:8]))
    return len(roots)
