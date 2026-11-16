"""Tests of build_bl.py and of the frozen enumerator over the three block sets, on INVENTED targets (functions
written here; no library operation is searched). Author: Chimdi Walter Ndubuisi
Run: env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B -m pytest -q -p no:cacheprovider experiments/below_library_20261114/tests
"""
import signal

import pytest

import bl_frozen  # noqa: F401
import core                      # the operations study's build and evaluator: for comparison only
import dslx
import search as frozen_search   # the frozen enumerator module: for comparison only
import gen_bl as gen             # this experiment's copy of the generator
import search_bl as S            # this experiment's copy of the enumerator
import blocks_c as B
import build_bl as BB
import guards_bl as G
import presets_bl as P

LIB = dslx.load()
LIBRARY_ORDER_OF_THE_SEVEN = ["compose", "chain", "matcher", "rbind", "lbind", "power", "fork"]


def examples_of(target, argsets):
    return [(tuple(a), target(*a)) for a in argsets]


def find(target, argsets, block_set="C", size=4, hidden=(), keep_ops=None, keep_fn=None, max_fn=None, allowance=60.0, **build_options):
    """One search for an invented target. keep_ops / keep_fn restrict the REAL build to some of its operations and
    function-valued leaves (in their own order). The record of function-making and the wrappers' counts come back
    with the enumerator's result."""
    counts, book = BB.new_counts(), BB.new_function_book(len(argsets))
    ops, leaves, Y, op_ns, leaf_ns, consts = BB.build(block_set, hidden, examples_of(target, argsets), counts=counts, book=book, **build_options)
    if keep_ops is not None:
        ops = [o for o in ops if o[0] in keep_ops]
        leaves = [leaf for leaf in leaves if leaf[0][0] != "FN" or leaf[0][1] in keep_fn]
    r = S.search(ops, leaves, Y, allowance, size, P.MAX_FN if max_fn is None else max_fn, P.MAX_BANK)
    r.update(text=r["found"][0] if r["found"] else None, counts=counts, book=book,
             function_valued_leaves=sum(1 for _, v in leaves if dslx.tagset(v) == frozenset("F")))
    if r["found"]:                                                   # the found tree gives the outputs again in a later evaluation
        for args, out in examples_of(target, argsets):
            v = BB.eval_tree_bl(r["found"][2], op_ns, leaf_ns, consts, {"x%d" % i: a for i, a in enumerate(args)})
            assert dslx.canon(v) == dslx.canon(out)
    return r


# ---------------------------------------------------------------- the three block sets
@pytest.fixture(scope="module")
def rot180_examples():
    g = gen.gen_examples("rot180", n_total=36)                       # the generator of a development name; no search
    assert g["status"] == "ok"
    return g["examples"]


def test_L_is_core_build_with_neutral_names_and_the_memory_wrapper(rot180_examples):
    hidden = list(LIB["fam_of"]["rot180"])
    ns = dslx.library_namespace(hidden)
    theirs_ops, theirs_leaves, theirs_Y = core.build("rot180", hidden, rot180_examples, ns)
    ops, leaves, Y, op_ns, leaf_ns, consts = BB.build("L", hidden, rot180_examples, ns=ns)
    assert [(o[0], o[2], o[3]) for o in ops] == [(o[0], o[2], o[3]) for o in theirs_ops]
    assert all(mine[1].__wrapped__ is theirs[1] and mine[1].__name__ == theirs[0] for mine, theirs in zip(ops, theirs_ops))
    assert Y == theirs_Y and type(Y) is tuple and consts == LIB["consts"] and consts is not LIB["consts"]
    # the two namespaces of a later evaluation: an applied operation is wrapped as in the search (another wrapper
    # object over the same function, with its own counters); a function-valued leaf is the function itself
    assert list(op_ns) == [o[0] for o in ops] and all(op_ns[o[0]].__wrapped__ is o[1].__wrapped__ and op_ns[o[0]] is not o[1] for o in ops)
    # the same wrapper for both, except the seven retained operations: in the search their wrapper also keeps the
    # record of function-making; the refusals are the same (a test of the arity rule compares the two)
    plain = BB.operation_wrapper(len).__code__
    assert all(op_ns[o[0]].__code__ is plain for o in ops)
    assert all((o[1].__code__ is plain) == (o[0] not in P.RETAINED) for o in ops)
    making = {o[1].__code__ for o in ops if o[0] in P.RETAINED}
    assert len(making) == 1 and making == {BB.function_making_wrapper(len, "compose", BB.new_counts(), BB.new_function_book(1), True).__code__}
    assert leaf_ns == {t[1]: v[0] for t, v in leaves if t[0] == "FN"} and all(leaf_ns[f] is ns[f] for f in leaf_ns)
    names = [p for p, _ in LIB["sigs"]["rot180"]]
    renamed = [(("P", "x%d" % names.index(t[1])) if t[0] == "P" else t, v) for t, v in theirs_leaves]
    assert [t for t, _ in leaves] == [t for t, _ in renamed]
    assert all(a is b or a == b for (_, va), (_, vb) in zip(leaves, renamed) for a, b in zip(va, vb))
    assert all(a is b for (t, va), (_, vb) in zip(leaves, renamed) if t[0] == "FN" for a, b in zip(va, vb))
    assert [t for t, _ in leaves if t[0] == "P"] == [("P", "x0")] and not any(t == ("P", n) for t, _ in leaves for n in names)
    assert len(ops) == 155 - len(hidden) and len([t for t, _ in leaves if t[0] == "C"]) == 28
    assert not set(hidden) & {o[0] for o in ops} and not set(hidden) & {t[1] for t, _ in leaves}
    fresh = BB.build("L", hidden, rot180_examples)                   # without ns: a fresh masked namespace every time
    again = BB.build("L", hidden, rot180_examples)
    assert fresh[4]["size"] is not ns["size"] and fresh[4]["size"] is not again[4]["size"]
    assert fresh[0][0][1].__wrapped__ is not ops[0][1].__wrapped__ and fresh[0] is not again[0] and fresh[3] is not again[3]


def test_C_is_the_catalogue_then_the_retained_operations(rot180_examples):
    hidden = list(LIB["fam_of"]["rot180"])
    ops, leaves, Y, op_ns, leaf_ns, consts = BB.build("C", hidden, rot180_examples)
    ids = [b.id for b in B.CATALOGUE]
    assert [o[0] for o in ops] == ids + LIBRARY_ORDER_OF_THE_SEVEN and BB.retained_present(hidden) == LIBRARY_ORDER_OF_THE_SEVEN
    assert sorted(LIBRARY_ORDER_OF_THE_SEVEN) == sorted(P.RETAINED)
    assert [o[3] for o in ops] == [False] * 68 + [True] * 7          # makes_fn as core.build sets it
    assert all((o[1].__wrapped__ if BB.BLOCKS_WRAPPED else o[1]) is B.BY_ID[o[0]].fn for o in ops[:68])
    assert all(o[2] == tuple(B.acc_of(a) for _, a in B.BY_ID[o[0]].params) for o in ops[:68])
    assert all(o[2] == tuple(dslx.ACC[a] for _, a in LIB["sigs"][o[0]]) and LIB["rets"][o[0]] == "Callable" for o in ops[68:])
    trees = [t for t, _ in leaves]
    assert trees == [("P", "x0")] + [("C", c) for c in LIB["const_names"]] + [("C", "EMPTY_TUPLE"), ("C", "EMPTY_SET")] + \
        [("FN", b) for b in B.function_leaf_names()]
    assert all(len(v) == 36 for _, v in leaves) and dict(leaves)[("C", "EMPTY_SET")] == (frozenset(),) * 36
    assert all(v[0] is B.BY_ID[t[1]].fn for t, v in leaves if t[0] == "FN")           # the leaves are the checked blocks themselves
    assert set(op_ns) == set(ids) | set(P.RETAINED) and consts == dict(LIB["consts"], EMPTY_TUPLE=(), EMPTY_SET=frozenset())
    assert leaf_ns == {b: B.BY_ID[b].fn for b in B.function_leaf_names()} and not set(P.RETAINED) & set(leaf_ns)
    assert all(op_ns[n].__wrapped__.__name__ == n and op_ns[n].__wrapped__ is ops[68 + i][1].__wrapped__ for i, n in enumerate(LIBRARY_ORDER_OF_THE_SEVEN))
    # every block that takes a function has at least two parameters (the enumerator's pruning of function-making
    # operations relies on it: a function of size s is consumed only by an expression of size s + 2 or more)
    for b in B.CATALOGUE:
        if any(a == "Callable" for _, a in b.params):
            assert len(b.params) >= 2
    for nm in ops:
        if frozenset("F") in nm[2]:
            assert len(nm[2]) >= 2


def test_a_retained_operation_that_is_hidden_is_absent():
    ex = [((1,), 1), ((2,), 2)]
    ops, leaves, Y, op_ns, leaf_ns, consts = BB.build("C", ["fork", "lbind", "rbind"], ex)
    assert [o[0] for o in ops][68:] == ["compose", "chain", "matcher", "power"] and "fork" not in op_ns and "lbind" not in op_ns
    assert BB.retained_present(["compose", "chain", "power"]) == ["matcher", "rbind", "lbind", "fork"]
    assert BB.retained_present(()) == LIBRARY_ORDER_OF_THE_SEVEN
    BB.assert_hidden_unreachable(["fork", "lbind", "rbind"], ops, leaves, (op_ns, leaf_ns))


def test_LC_is_L_first_then_C_without_duplicates(rot180_examples):
    hidden = list(LIB["fam_of"]["rot180"])
    l_ops, l_leaves = BB.build("L", hidden, rot180_examples)[:2]
    c_ops, c_leaves = BB.build("C", hidden, rot180_examples)[:2]
    ops, leaves, Y, op_ns, leaf_ns, consts = BB.build("LC", hidden, rot180_examples)
    assert [o[0] for o in ops] == [o[0] for o in l_ops] + [b.id for b in B.CATALOGUE]
    assert len({o[0] for o in ops}) == len(ops) and [o[3] for o in ops] == [o[3] for o in l_ops] + [False] * 68
    c_only = [t for t, _ in c_leaves if t not in {t2 for t2, _ in l_leaves}]
    assert [t for t, _ in leaves] == [t for t, _ in l_leaves] + c_only and len({t for t, _ in leaves}) == len(leaves)
    assert c_only == [("C", "EMPTY_TUPLE"), ("C", "EMPTY_SET")] + [("FN", b) for b in B.function_leaf_names()]
    assert set(op_ns) == ({n for n in LIB["lib_order"] if n not in hidden} | {b.id for b in B.CATALOGUE})
    assert set(leaf_ns) == {f for f in LIB["fn_leaf_names"] if f not in hidden} | set(B.function_leaf_names())
    assert not set(hidden) & (set(op_ns) | set(leaf_ns)) and consts["EMPTY_TUPLE"] == () and len(consts) == 30
    assert "c_len" not in leaf_ns["size"].__globals__                # the library's own namespace is not touched


def test_build_refuses_what_it_cannot_build():
    with pytest.raises(ValueError):
        BB.build("X", (), [((1,), 1)])
    with pytest.raises(ValueError):
        BB.build("C", (), [])
    with pytest.raises(ValueError):
        BB.build("C", (), [((1,), 1), ((1, 2), 1)])


# ---------------------------------------------------------------- the thin wrapper
def test_the_wrapper_changes_nothing_but_a_memory_failure():
    def sample(a, b=2):
        return (a, b)

    def fails(a):
        raise KeyError(a)

    def out_of_memory(*a):
        raise MemoryError()
    w = BB.operation_wrapper(sample)
    assert w(1) == (1, 2) and w(1, 3) == (1, 3) and w.__name__ == "sample" and w.__wrapped__ is sample
    with pytest.raises(KeyError):
        BB.operation_wrapper(fails)(1)                                   # an ordinary error passes unchanged
    with pytest.raises(TypeError):
        w()                                                          # so does a wrong number of arguments
    with pytest.raises(G.ResourceStop):
        BB.operation_wrapper(out_of_memory)(1)
    for block_set in BB.BLOCK_SETS:
        ops = BB.build(block_set, (), [((1,), 1)])[0]
        assert all(o[1].__name__ == o[0] for o in ops)
        for o in ops:                                                # every library operation is wrapped; a block is handed over bare
            if o[0] in B.BY_ID and not BB.BLOCKS_WRAPPED:
                assert o[1] is B.BY_ID[o[0]].fn
            elif o[0] in P.RETAINED:
                assert o[1].__wrapped__.__name__ == o[0] and o[1].__code__ is not w.__code__      # the function-making wrapper
            else:
                assert o[1].__code__ is w.__code__


def test_a_memory_failure_stops_the_search_and_is_never_skipped():
    """An invented library-style operation, and an invented block reached through a function-valued leaf, raise
    MemoryError inside the enumerator: the search ends with ResourceStop (the caller records an infrastructure
    stop). Without the wrapper the enumerator's own handler would skip the expression and go on."""
    def library_style(x):
        raise MemoryError()
    ex = [((i,), i + 100) for i in range(4)]
    before = signal.getsignal(signal.SIGVTALRM)
    ops, leaves, Y = BB.build("C", (), ex)[:3]
    bare = ops + [("invented_op", library_style, (dslx.ACC["Integer"],), False)]
    r = frozen_search.search(bare, leaves, Y, 5.0, 2, P.MAX_FN, P.MAX_BANK)
    assert r["stop"] == "size_exhausted" and r["found"] is None      # the frozen enumerator with a bare operation: silently skipped
    wrapped = ops + [("invented_op", BB.operation_wrapper(library_style), (dslx.ACC["Integer"],), False)]
    with pytest.raises(G.ResourceStop):
        frozen_search.search(wrapped, leaves, Y, 5.0, 2, P.MAX_FN, P.MAX_BANK)       # the wrapper alone stops it
    with pytest.raises(G.ResourceStop):
        S.search(bare, leaves, Y, 5.0, 2, P.MAX_FN, P.MAX_BANK)                      # so does this experiment's enumerator alone
    with pytest.raises(G.ResourceStop):
        S.search(wrapped, leaves, Y, 5.0, 2, P.MAX_FN, P.MAX_BANK)
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and signal.getsignal(signal.SIGVTALRM) == before
    # an invented block: checked like every block, its body runs out of memory; it is offered as a function-valued leaf
    def c_invented(a):
        raise MemoryError()
    block = B._checked1(c_invented, "c_invented", B._d_any)
    with pytest.raises(G.ResourceStop):
        block(1)
    leaves2 = leaves + [(("FN", "c_invented"), (block,) * len(ex))]
    with pytest.raises(G.ResourceStop):
        S.search(ops, leaves2, Y, 5.0, 3, P.MAX_FN, P.MAX_BANK)       # reached through c_call1(c_invented, x0) or a comprehension
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and signal.getsignal(signal.SIGVTALRM) == before
    # the same through a function that came in as an input
    def came_in(v):
        raise MemoryError()
    ex3 = [((i, came_in), i) for i in range(4)]
    ops3, leaves3 = BB.build("C", (), ex3)[:2]
    with pytest.raises(G.ResourceStop):
        S.search(ops3, leaves3, tuple(i + 7 for i in range(4)), 5.0, 3, P.MAX_FN, P.MAX_BANK)


# ---------------------------------------------------------------- hidden names are not reachable
def test_hidden_names_are_unreachable_in_every_block_set(rot180_examples):
    hidden = list(LIB["fam_of"]["rot180"])
    for block_set in BB.BLOCK_SETS:
        ops, leaves, Y, op_ns, leaf_ns, consts = BB.build(block_set, hidden, rot180_examples)
        assert BB.assert_hidden_unreachable(hidden, ops, leaves, (op_ns, leaf_ns)) > 60
    # an operation that depends on a hidden one stays listed and fails when called: that is not "reachable"
    dependants = sorted(BB.dslx.reverse_closure(hidden) - set(hidden))
    assert dependants
    ops = BB.build("L", hidden, rot180_examples)[0]
    assert set(dependants) <= {o[0] for o in ops}


def test_every_way_of_reaching_a_hidden_name_is_refused(rot180_examples):
    hidden = list(LIB["fam_of"]["rot180"])
    full = dslx.full_ns()
    h = full["rot180"]
    ops, leaves, Y, op_ns, leaf_ns, consts = BB.build("LC", hidden, rot180_examples)
    namespace = (op_ns, leaf_ns)

    def refused(o=ops, lv=leaves, ns=namespace, extra=()):
        with pytest.raises(RuntimeError) as e:
            BB.assert_hidden_unreachable(hidden, o, lv, ns, extra)
        assert "reachable" in str(e.value)
    acc = (dslx.ACC["Grid"],)
    refused(o=ops + [("rot180", BB.operation_wrapper(h), acc, False)])                       # listed under its own name
    refused(o=ops + [("alias", BB.operation_wrapper(h), acc, False)])                        # listed under another name
    refused(o=ops + [("alias", h, acc, False)])
    refused(lv=leaves + [(("FN", "rot180"), (h,) * 36)])                                 # a leaf with the hidden name
    refused(lv=leaves + [(("FN", "alias"), (h,) * 36)])                                  # a leaf that is the hidden definition
    refused(lv=leaves + [(("P", "x1"), (len,) * 35 + (h,))])                             # one example argument is the hidden definition
    refused(lv=leaves + [(("P", "x1"), ((1, (h,)),) * 36)])                              # ... or holds it
    refused(ns=(dict(op_ns, rot180=len), leaf_ns))                                       # the name exists in a namespace
    refused(ns=(op_ns, dict(leaf_ns, rot180=len)))
    refused(ns=(op_ns, dict(leaf_ns, alias=h)))
    refused(ns=dict(op_ns, alias=h))
    refused(extra=[h])
    refused(extra=[lambda g: h(g)])                                                      # through a closure
    refused(extra=[BB.operation_wrapper(BB.operation_wrapper(h))])                               # through wrappers
    dependant = full[sorted(dslx.reverse_closure(hidden) - set(hidden))[0]]
    refused(extra=[dependant])                                                           # a full-library function that calls a hidden one
    def with_default(g, f=h):
        return f(g)
    refused(extra=[with_default])
    # a function of the full library that does not depend on the hidden family is fine (the generator draws such arguments)
    clear = [full[n] for n in ("size", "first", "initset") if n not in dslx.reverse_closure(hidden)]
    assert clear and BB.assert_hidden_unreachable(hidden, ops, leaves, namespace, clear) > 0
    assert BB.reachable_hidden(hidden, clear) == [] and BB.reachable_hidden(hidden, [h]) != []
    assert BB.reachable_hidden(hidden, [b.fn for b in B.CATALOGUE]) == []


# ---------------------------------------------------------------- invented targets: leaves, comprehensions, calls
TT = [(((1, 2), (3,)),), (((), (4, 5, 6), (7,)),), (((8, 9, 1, 2),),), (((3, 4), (), (5,), (6, 7, 8)),), (((1,), (2, 3)),),
      (((9,), (), ()),), (((1, 2, 3), (4, 5)),), (((6,), (7, 8), (9, 1, 2, 3)),)]


def test_function_valued_leaf_in_a_comprehension_block():
    r = find(lambda x0: tuple(len(e) for e in x0), TT, size=3)
    assert r["text"] == "c_map_tuple(c_len, x0)" and r["found"][1] == 3 and r["stop"] == "found"


def test_each_comprehension_block_on_an_invented_target():
    assert find(lambda x0: frozenset(len(e) for e in x0), TT, size=3)["text"] == "c_map_set(c_len, x0)"
    mixed = [((1, (2,), 3),), (((4,), 5, (6,)),), ((7, 8),), (((9,),),), ((1, (2,), (3,), 4),), ((5,),)]
    assert find(lambda x0: tuple(e for e in x0 if isinstance(e, int)), mixed, size=3)["text"] == "c_keep(c_is_integer, x0)"
    two = [((1, 2), (5,)), ((3,), (6, 7)), ((4, 5, 6), (8, 9)), ((7,), (1,)), ((2, 3), (4, 5, 6)), ((8, 9), (2,))]
    assert find(lambda x0, x1: tuple((i, j) for i in x0 for j in x1), two, size=3)["text"] == "c_pairs(x0, x1)"


def test_a_function_typed_parameter_is_called_by_the_call_block():
    fns = [lambda v: v + 1, lambda v: v * 2, lambda v: -v, lambda v: (v, v), lambda v: v % 3]
    argsets = [(4, fns[0]), (-3, fns[1]), (7, fns[2]), (2, fns[3]), (8, fns[4]), (5, fns[1]), (0, fns[0]), (9, fns[3])]
    r = find(lambda x0, x1: x1(x0), argsets, size=3)
    assert r["text"] == "c_call1(x1, x0)" and r["found"][1] == 3
    two = [(4, 2, lambda a, b: a - b), (1, 5, lambda a, b: (b, a)), (3, 3, lambda a, b: a * b), (7, 1, lambda a, b: a - b),
           (2, 9, lambda a, b: (b, a)), (6, 4, lambda a, b: a * b)]
    r = find(lambda x0, x1, x2: x2(x0, x1), two, size=4)
    assert r["text"] == "c_call2(x2, x0, x1)" and r["found"][1] == 4


# ---------------------------------------------------------------- the eager rule
GUARD_NEVER_MATTERS = [(True, (True,)), (True, (False, True)), (False, (True, False)), (False, (False,)), (True, (True, False)),
                       (True, (False,)), (False, (True,)), (True, (False, False, True))]
GUARD_NEEDED = GUARD_NEVER_MATTERS + [(False, ()), (False, ())]


def short_circuit(x0, x1):
    return x0 and x1[0]                                              # Python never reads x1[0] when x0 is False


def test_the_eager_rule_a_program_that_needs_a_guard_is_not_found():
    """`x0 and x1[0]`. Where the second operand always exists, C finds it (as c_and over c_first). Where it must NOT
    be evaluated (x1 is empty and x0 is False), Python's short circuit protects the indexing; in C both operands are
    evaluated before c_and runs, the indexing raises on those examples, so the expression does not exist there and
    an exhaustive search of four nodes finds nothing."""
    r = find(short_circuit, GUARD_NEVER_MATTERS, size=4)
    assert r["text"] == "c_and(x0, c_first(x1))" and r["found"][1] == 4
    r2 = find(short_circuit, GUARD_NEEDED, size=4)
    assert r2["found"] is None and r2["stop"] == "size_exhausted" and r2["level"] == 4 and r2["function_cap_reached"] is False
    # why: the same tree is evaluated eagerly on the guard example and raises there
    op_ns, leaf_ns, consts = BB.build("C", (), examples_of(short_circuit, GUARD_NEEDED))[3:]
    tree = ("L", "c_and", ("P", "x0"), ("L", "c_first", ("P", "x1")))
    assert BB.eval_tree_bl(tree, op_ns, leaf_ns, consts, dict(x0=True, x1=(False,))) is False
    with pytest.raises(ValueError):
        BB.eval_tree_bl(tree, op_ns, leaf_ns, consts, dict(x0=False, x1=()))
    assert short_circuit(False, ()) is False
    # c_if_else is eager as well: a conditional whose unused branch would raise does not exist
    with pytest.raises(IndexError):
        BB.eval_tree_bl(("L", "c_if_else", ("P", "x0"), ("L", "c_item0", ("P", "x1")), ("C", "F")), op_ns, leaf_ns, consts, dict(x0=False, x1=()))


# ---------------------------------------------------------------- the seven retained operations with blocks of C
def ints(seed, lo, hi):
    import random
    r = random.Random(seed)
    return tuple(r.randint(0, 9) for _ in range(r.randint(lo, hi)))


DEEP = [(tuple(tuple(ints(100 * i + 10 * j + k, 1, 4) for k in range(1 + (i + j) % 3)) for j in range(2 + i % 3)),) for i in range(8)]
DEEPER = [(tuple(tuple(tuple(ints(1000 * i + 100 * j + 10 * k + m, 1, 4) for m in range(1 + (i + k) % 3)) for k in range(1 + j % 2))
                 for j in range(2 + i % 3)),) for i in range(8)]
FLAT1 = [(ints(i, 2, 6), 1 + (3 * i) % 9) for i in range(8)]
PAIRS = [(tuple((ints(50 * i + j, 1, 1)[0], ints(77 * i + j, 1, 1)[0]) for j in range(2 + i % 4)),) for i in range(8)]
LENGTHS = [(tuple(ints(31 * i + j, 0, 4) for j in range(2 + i % 4)), i % 4) for i in range(8)]
RETAINED_TARGETS = {
    # name: (invented target, argument tuples, size limit, operations kept, function-valued leaves kept, expected first fit)
    "compose": (lambda x0: max(x0, key=lambda e: len(e[0])), DEEP, 5, {"c_max_key", "c_len", "c_item0", "compose"}, {"c_len", "c_item0"},
                "c_max_key(x0, compose(c_len, c_item0))"),
    "lbind": (lambda x0, x1: tuple(x1 - e for e in x0), FLAT1, 5, {"c_map_tuple", "c_sub", "c_add", "lbind", "rbind"}, {"c_sub", "c_add"},
              "c_map_tuple(lbind(c_sub, x1), x0)"),
    "rbind": (lambda x0, x1: tuple(e - x1 for e in x0), FLAT1, 5, {"c_map_tuple", "c_sub", "c_add", "lbind", "rbind"}, {"c_sub", "c_add"},
              "c_map_tuple(rbind(c_sub, x1), x0)"),
    "matcher": (lambda x0, x1: tuple(e for e in x0 if len(e) == x1), LENGTHS, 5, {"c_keep", "c_len", "c_eq", "matcher", "c_map_tuple"},
                {"c_len", "c_first"}, "c_keep(matcher(c_len, x1), x0)"),
    "fork": (lambda x0: tuple(e[0] - e[1] for e in x0), PAIRS, 6, {"c_map_tuple", "c_sub", "c_item0", "c_item1", "fork", "compose"},
             {"c_sub", "c_item0", "c_item1"}, "c_map_tuple(fork(c_sub, c_item0, c_item1), x0)"),
    "chain": (lambda x0: max(x0, key=lambda e: len(e[0][0])), DEEPER, 6, {"c_max_key", "c_len", "c_item0", "chain", "compose"},
              {"c_len", "c_item0"}, "c_max_key(x0, chain(c_len, c_item0, c_item0))"),
    "power": (lambda x0: tuple((((e,),),) for e in x0), [(a[0],) for a in FLAT1], 5, {"c_map_tuple", "c_single", "power", "compose", "chain"},
              {"c_single"}, "c_map_tuple(power(c_single, THREE), x0)"),
}


@pytest.mark.parametrize("name", sorted(RETAINED_TARGETS))
def test_each_retained_operation_composes_with_blocks_of_C(name):
    """The build is the real one for C (the real blocks, the library's own retained operation from the masked
    namespace, the frozen enumerator and the frozen cap); only the choice of operations and function-valued leaves
    offered is narrowed to a handful, so that the cap on function-valued entries does not decide the outcome."""
    target, argsets, size, keep_ops, keep_fn, want = RETAINED_TARGETS[name]
    assert name in keep_ops and set(P.RETAINED) >= {name}
    r = find(target, argsets, size=size, keep_ops=keep_ops, keep_fn=keep_fn)
    assert r["text"] == want and name in S.names_used(r["found"][2]) and r["function_cap_reached"] is False


def test_the_first_record_one_cap_of_1000_and_no_rule_starves_six_of_the_seven():
    """Why the arity rule and the cap of 16,000 were decided (the first record, kept in
    diag_function_cap_by_block_set.json). With the cap at 1,000 and no rule, the 64 function-valued leaves of C
    count towards the cap and compose, the first function-making operation in the library's order, alone offers
    64 * 64 applications at three nodes: the cap is reached inside compose and the other six are never called. A
    target that needs lbind is not found with the full build."""
    target, argsets, size, _, _, want = RETAINED_TARGETS["lbind"]
    r = find(target, argsets[:4], size=size, max_fn=1000, arity_rule=False)
    assert r["found"] is None and r["function_cap_reached"] is True and r["stop"] == "size_exhausted_function_cap"
    assert set(r["book"]["by_operation"]) == {"compose"} and set(r["book"]["by_operation"]["compose"]) == {3}
    row = r["book"]["by_operation"]["compose"][3]
    assert row == dict(offered=64 * 64, admitted=1000 - 64, refused_by_arity=0, refused_as_power_duplicate=0, refused_by_cap=64 * 64 - 936,
                       raised_in_the_library=0)
    assert r["book"]["cap_reached_at"] == dict(operation="compose", size=3, function_valued_entries=1000)
    assert r["book"]["first_refused_by_cap"] == dict(operation="compose", size=3, function_valued_entries=1000)


def test_with_the_declared_rule_and_cap_all_five_two_argument_makers_get_their_entries():
    """The same full build under the presets in force (arity rule on, cap 16,000): at three nodes compose, matcher,
    rbind, lbind and power each get every application the rule admits, the cap is not reached, and the target that
    needs lbind is found. chain and fork take three functions (four nodes) and cannot be used at a size limit of 5."""
    assert P.ARITY_RULE is True and P.MAX_FN == 16000
    target, argsets, size, _, _, want = RETAINED_TARGETS["lbind"]
    r = find(target, argsets[:4], size=size)
    assert r["text"] == want and r["function_cap_reached"] is False and r["book"]["cap_reached_at"] is None
    leaves = [B.BY_ID[b] for b in B.function_leaf_names()]
    one, two = sum(len(b.params) == 1 for b in leaves), sum(len(b.params) == 2 for b in leaves)
    assert (one, two) == (23, 41)
    values, integers, bad_powers = 2 + 28 + 2, 13 + 1, 3            # leaves that are not functions; integer leaves; ZERO, NEG_ONE, NEG_TWO
    by = r["book"]["by_operation"]
    assert set(by) == {"compose", "matcher", "rbind", "lbind", "power"} and all(set(rows) == {3} for rows in by.values())
    zero = dict.fromkeys(BB.FUNCTION_ROW, 0)
    assert by["compose"][3] == dict(zero, offered=64 * 64, admitted=one * one, refused_by_arity=64 * 64 - one * one)
    assert by["matcher"][3] == dict(zero, offered=64 * values, admitted=one * values, refused_by_arity=two * values)
    for binder in ("rbind", "lbind"):
        assert by[binder][3] == dict(zero, offered=64 * values, admitted=two * values, refused_by_arity=one * values)
    assert by["power"][3] == dict(zero, offered=64 * integers, admitted=one * (integers - bad_powers), refused_as_power_duplicate=two * integers,
                                  raised_in_the_library=one * bad_powers)
    for rows in by.values():
        for row in rows.values():
            assert row["offered"] == sum(row[k] for k in BB.FUNCTION_ROW[1:])
    admitted = sum(row["admitted"] for rows in by.values() for row in rows.values())
    assert admitted == r["book"]["admitted"] == 529 + 736 + 1312 + 1312 + 253 and r["book"]["calls_outside_the_enumerator"] == 0
    assert r["counts"]["function_making_refused_by_arity"] == sum(row["refused_by_arity"] for rows in by.values() for row in rows.values())
    assert r["counts"]["power_of_a_function_without_one_parameter"] == by["power"][3]["refused_as_power_duplicate"]


def test_the_record_shows_where_the_cap_is_reached():
    target, argsets, size, keep_ops, keep_fn, want = RETAINED_TARGETS["fork"]
    r = find(target, argsets, size=6, keep_ops=keep_ops | {"chain"}, keep_fn=keep_fn | {"c_len", "c_neg", "c_abs"}, max_fn=40)
    by, book = r["book"]["by_operation"], r["book"]
    assert r["function_cap_reached"] is True and book["cap_reached_at"]["function_valued_entries"] == 40
    assert book["cap_reached_at"]["operation"] in by and book["cap_reached_at"]["size"] in by[book["cap_reached_at"]["operation"]]
    assert book["first_refused_by_cap"]["function_valued_entries"] == 40 and sum(row["refused_by_cap"] for rows in by.values() for row in rows.values()) >= 1
    assert r["function_valued_leaves"] + book["admitted"] == 40
    # a wrapper that is not called by the enumerator itself does not write sizes it cannot know
    counts, book2 = BB.new_counts(), BB.new_function_book(1)
    ops = BB.build("C", (), [((1,), 1)], counts=counts, book=book2)[0]
    compose = {o[0]: o[1] for o in ops}["compose"]
    assert callable(compose(B.c_len, B.c_tuple)) and book2["by_operation"] == {} and book2["calls_outside_the_enumerator"] == 1
    with pytest.raises(ValueError):
        BB.build("C", (), [((1,), 1), ((2,), 2)], book=BB.new_function_book(5))
    with pytest.raises(ValueError):
        BB.function_making_wrapper(len, "size", counts, book2, True)


@pytest.mark.parametrize("name", ["backdrop", "mapply", "rot180"])
def test_the_structural_bound_on_function_valued_entries_holds_on_development_names(name):
    """With the rule on, at a size limit of 5 the number of function-valued entries never exceeds the count that
    follows from signatures and leaf lists (structural_function_bound_2.json: 12,556 over L and 5,234 over C), so
    the cap of 16,000 is not reached. Over C at a size limit of 6 the cap can be reached at four nodes; the record
    then says where."""
    ex, hidden = dev_examples(name)
    for block_set, bound in (("L", 12556), ("C", 5234)):
        counts, book = BB.new_counts(), BB.new_function_book(len(ex))
        ops, leaves, Y = BB.build(block_set, hidden, ex, counts=counts, book=book)[:3]
        r = S.search(ops, leaves, Y, 20.0, 5, P.MAX_FN, P.MAX_BANK)
        fn_leaves = sum(1 for _, v in leaves if dslx.tagset(v) == frozenset("F"))
        assert r["stop"] == "found" or r["level"] >= 3, (name, block_set, r["stop"], r["level"])      # every function of this size limit was made
        assert fn_leaves + book["admitted"] <= bound < P.MAX_FN and r["function_cap_reached"] is False
        assert book["cap_reached_at"] is None and book["first_refused_by_cap"] is None and book["calls_outside_the_enumerator"] == 0
        assert all(set(rows) <= {3} for rows in book["by_operation"].values())
    counts, book = BB.new_counts(), BB.new_function_book(len(ex))
    ops, leaves, Y = BB.build("C", hidden, ex, counts=counts, book=book)[:3]
    r = S.search(ops, leaves, Y, 40.0, 6, P.MAX_FN, P.MAX_BANK)
    if r["function_cap_reached"]:
        at = book["cap_reached_at"]
        assert at is not None and at["size"] == 4 and at["operation"] in ("chain", "fork") and at["function_valued_entries"] == P.MAX_FN
    else:
        assert r["stop"] == "found" or r["level"] < 4                # it did not get as far as the functions of four nodes


def test_a_block_handed_over_bare_gives_the_search_a_wrapped_block_gives(monkeypatch):
    """Speed change (ii): the blocks of C reach the enumerator without the wrapper. The same searches either way."""
    assert BB.BLOCKS_WRAPPED is False
    cases = [(RETAINED_TARGETS[n][0], RETAINED_TARGETS[n][1], RETAINED_TARGETS[n][2], RETAINED_TARGETS[n][3], RETAINED_TARGETS[n][4])
             for n in ("compose", "lbind", "matcher", "fork")]
    cases += [(lambda x0: tuple(len(e) for e in x0), TT, 3, None, None), (short_circuit, GUARD_NEEDED, 4, None, None),
              (short_circuit, GUARD_NEVER_MATTERS, 4, None, None), (lambda x0: (len(x0), 77, len(x0)), TT, 3, None, None)]
    for block_set in ("C", "LC"):
        for target, argsets, size, keep_ops, keep_fn in cases:
            if block_set == "LC" and size > 3:
                continue
            rows = []
            for wrapped in (False, True):
                monkeypatch.setattr(BB, "BLOCKS_WRAPPED", wrapped)
                r = find(target, argsets, block_set=block_set, size=size, keep_ops=keep_ops, keep_fn=keep_fn)
                rows.append((r["found"], r["stop"], r["level"], r["bank"], r["function_cap_reached"], r["book"]["by_operation"]))
            assert rows[0] == rows[1]
    monkeypatch.setattr(BB, "BLOCKS_WRAPPED", True)
    assert all(o[1].__wrapped__ is B.BY_ID[o[0]].fn for o in BB.build("C", (), [((1,), 1)])[0][:68])


# ---------------------------------------------------------------- LC: the library first at equal size
def test_in_LC_a_library_expression_is_met_before_one_over_C_at_equal_size():
    assert find(lambda x0: len(x0), TT, block_set="C", size=2)["text"] == "c_len(x0)"
    assert find(lambda x0: len(x0), TT, block_set="L", size=2)["text"] == "size(x0)"
    assert find(lambda x0: len(x0), TT, block_set="LC", size=2)["text"] == "size(x0)"
    one = [((3, 1, 2),), ((5, 5),), ((9, 0, 4, 4),), ((7,),), ((2, 8),), ((6, 1, 1),)]
    assert find(lambda x0: x0[::-1], one, block_set="C", size=2)["text"] == "c_reverse(x0)"
    # something only C can do within the size: LC finds it with a block
    r = find(lambda x0: tuple(enumerate(x0)), one, block_set="LC", size=2)
    assert r["text"] == "c_enumerate(x0)"
    assert find(lambda x0: tuple(enumerate(x0)), one, block_set="L", size=2)["found"] is None


# ---------------------------------------------------------------- the wrapper's rule: a container never holds a function
def test_the_wrapper_keeps_a_function_only_from_the_seven_retained_operations():
    lib = dslx.library_namespace(())
    counts = BB.new_counts()
    assert counts == {"function_results_refused": 0, "containers_holding_a_function_refused": 0, "function_making_refused_by_arity": 0,
                      "power_of_a_function_without_one_parameter": 0}
    for i, name in enumerate(("first", "identity", "branch", "invented")):
        gives_a_function = BB.operation_wrapper(lambda *a: len, name, counts)
        with pytest.raises(TypeError):
            gives_a_function(1)
        assert counts["function_results_refused"] == i + 1
    made = {
        "compose": (B.c_abs, B.c_len), "chain": (B.c_neg, B.c_abs, B.c_len), "matcher": (B.c_len, 2), "rbind": (B.c_sub, 2),
        "lbind": (B.c_sub, 10), "power": (B.c_neg, 3), "fork": (B.c_add, B.c_len, B.c_len)}
    assert set(made) == set(P.RETAINED)
    for name, args in made.items():
        f = BB.operation_wrapper(lib[name], name, counts)(*args)
        assert callable(f)
    assert counts["function_results_refused"] == 4 and counts["containers_holding_a_function_refused"] == 0


def test_the_wrapper_refuses_a_container_that_holds_a_function():
    lib = dslx.library_namespace(())
    counts = BB.new_counts()
    for depth_holder in (lambda f, x: (f,), lambda f, x: (x, (1, frozenset({f}))), lambda f, x: frozenset({(x, (f, 2))})):
        with pytest.raises(TypeError):
            BB.operation_wrapper(depth_holder, "invented", counts)(len, 1)
    assert counts["containers_holding_a_function_refused"] == 3
    assert BB.operation_wrapper(lambda f, x: (x, (1, 2)), "invented", counts)(len, 5) == (5, (1, 2))     # nothing held: untouched
    # the library's own way of making such a container: a function-making operation passed as a value
    for maker in ("lbind", "rbind", "matcher", "compose"):
        assert len(lib["papply"](lib[maker], (1, 2), (3, 4))) == 2                                        # bare: two functions in a tuple
        with pytest.raises(TypeError):
            BB.operation_wrapper(lib["papply"], "papply", counts)(lib[maker], (1, 2), (3, 4))
    assert counts["containers_holding_a_function_refused"] == 7 and counts["function_results_refused"] == 0
    # the condition of the walk. A result that holds a function although no argument is callable cannot come from
    # a library operation; an invented one shows what each mode does with it
    odd = lambda x: (x, len)                                          # noqa: E731
    assert BB.operation_wrapper(odd, "invented", counts)(1) == (1, len) and counts["containers_holding_a_function_refused"] == 7
    always = BB.new_counts()
    with pytest.raises(TypeError):
        BB.operation_wrapper(odd, "invented", always, always_walk=True)(1)
    assert always["containers_holding_a_function_refused"] == 1 and always["walked_without_a_callable_argument"] == 1
    assert BB.holds_function((1, (2, frozenset({(3, abs)})))) and not BB.holds_function((1, (2, frozenset({(3, 4)})), ()))


def test_a_leaf_value_that_is_a_container_holding_a_function_is_refused():
    for block_set in BB.BLOCK_SETS:
        with pytest.raises(AssertionError):
            BB.build(block_set, (), [(((len, 1),), 1), (((abs,),), 2)])
        with pytest.raises(AssertionError):
            BB.build(block_set, (), [((1, frozenset({(2, len)})), 1)])
        BB.build(block_set, (), [((len,), 1), ((abs,), 2)])           # an argument that IS a function is allowed


def dev_examples(name, n=9):
    g = gen.gen_examples(name, n_total=P.N_GEN)                      # the generator of a development name
    assert g["status"] == "ok" and name in P.DEV_ROSTER
    return g["examples"][:n], sorted(LIB["fam_of"][name])


@pytest.mark.parametrize("name", ["mapply", "backdrop", "rot180"])
def test_walking_every_result_refuses_exactly_what_the_condition_refuses(name):
    """Whole searches on development names (nine examples, L and LC at four nodes) with the walk made only when an
    argument is callable, and again with the walk made on every result: the same search and the same refusals."""
    ex, hidden = dev_examples(name)
    for block_set in ("L", "LC"):
        rows = []
        for always in (False, True):
            counts = BB.new_counts()
            ops, leaves, Y = BB.build(block_set, hidden, ex, counts=counts, always_walk=always)[:3]
            r = S.search(ops, leaves, Y, 240.0, 4, P.MAX_FN, P.MAX_BANK)
            assert r["stop"] in ("found", "size_exhausted", "size_exhausted_function_cap")          # a whole search, not cut by time
            rows.append((r["found"][0] if r["found"] else None, r["stop"], r["level"], r["bank"], counts))
        (f0, s0, l0, b0, c0), (f1, s1, l1, b1, c1) = rows
        assert (f0, s0, l0, b0) == (f1, s1, l1, b1)
        assert c1.get("walked_without_a_callable_argument", 0) == 0 and "walked_without_a_callable_argument" not in c0
        assert {k: c0[k] for k in BB.REFUSAL_COUNTS} == {k: c1[k] for k in BB.REFUSAL_COUNTS}
        assert c0["function_results_refused"] == 0


# ---------------------------------------------------------------- evaluation outside the enumerator
def test_a_tree_evaluated_later_runs_under_the_same_rule_as_inside_the_search():
    ex = [(((1, 2), (3, 4)), 2), (((5,), (6, 7)), 1), (((1, 2, 3), (4, 5, 6)), 3), (((), (8,)), 0)]
    counts, eval_counts = BB.new_counts(), BB.new_counts()
    ops, leaves, Y, op_ns, leaf_ns, consts = BB.build("LC", (), ex, counts=counts, eval_counts=eval_counts)
    tree = ("L", "size", ("L", "papply", ("FN", "lbind"), ("P", "x0"), ("P", "x1")))
    in_search = {o[0]: o[1] for o in ops}
    with pytest.raises(TypeError):
        in_search["papply"](leaf_ns["lbind"], (1, 2), (3, 4))         # inside the search the inner expression does not exist
    assert counts["containers_holding_a_function_refused"] == 1 and eval_counts["containers_holding_a_function_refused"] == 0
    for args, _ in ex[:3]:
        with pytest.raises(TypeError):
            BB.eval_tree_bl(tree, op_ns, leaf_ns, consts, dict(x0=args[0], x1=args[1]))      # nor does it outside
    assert eval_counts["containers_holding_a_function_refused"] == 3 and counts["containers_holding_a_function_refused"] == 1
    # the frozen evaluator over one namespace of bare functions would let it through and even agree with the target:
    # that is why it is not used anywhere in this experiment
    bare = {n: getattr(f, "__wrapped__", f) for n, f in op_ns.items()}
    assert [frozen_search.eval_tree(tree, bare, consts, dict(x0=a[0], x1=a[1])) for a, _ in ex] == [2, 1, 3, 0] == list(Y)
    r = S.search(ops, leaves, Y, 60.0, 5, P.MAX_FN, P.MAX_BANK)
    assert r["found"] and "papply" not in S.names_used(r["found"][2]) and "lbind" not in S.names_used(r["found"][2])
    for args, out in ex:
        assert BB.eval_tree_bl(r["found"][2], op_ns, leaf_ns, consts, dict(x0=args[0], x1=args[1])) == out
    # a memory failure in a later evaluation is translated as well
    def out_of_memory(*a):
        raise MemoryError()
    op_ns2 = dict(op_ns, hungry=BB.operation_wrapper(out_of_memory, "hungry", eval_counts))
    with pytest.raises(G.ResourceStop):
        BB.eval_tree_bl(("L", "size", ("L", "hungry", ("P", "x0"))), op_ns2, leaf_ns, consts, dict(x0=(1,)))
    with pytest.raises(G.ResourceStop):
        BB.eval_tree_bl(("L", "c_call1", ("P", "x1"), ("P", "x0")), op_ns, leaf_ns, consts, dict(x0=1, x1=out_of_memory))
    with pytest.raises(ValueError):
        BB.eval_tree_bl(("X", "x0"), op_ns, leaf_ns, consts, {})


def test_the_frozen_evaluator_is_not_used_by_this_experiment():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("bl_frozen.py", "guards_bl.py", "presets_bl.py", "blocks_c.py", "build_bl.py", "episode_bl.py", "summarize_bl.py", "run_bl.py"):
        path = os.path.join(here, name)
        if os.path.exists(path):
            src = open(path).read()
            assert "S.eval_tree(" not in src and "search.eval_tree(" not in src and "import eval_tree" not in src, name


def test_function_valued_leaves_are_the_functions_themselves_with_their_own_parameters():
    for block_set in BB.BLOCK_SETS:
        ops, leaves, Y, op_ns, leaf_ns, consts = BB.build(block_set, (), [((1,), 1)])
        n = 0
        for t, v in leaves:
            if t[0] == "FN":
                n += 1
                assert v[0] is leaf_ns[t[1]] and not hasattr(v[0], "__wrapped__")
                want = len(B.BY_ID[t[1]].params) if t[1] in B.BY_ID else len(LIB["sigs"][t[1]])
                assert BB.declared_parameters(v[0]) == want                    # never a wrapper with a variable number of arguments
        assert n == len(leaf_ns)
    ops, leaves, Y, op_ns, leaf_ns, consts = BB.build("LC", (), [((1,), 1)])
    # handed to rbind and lbind: a leaf of two parameters gives a function of one, a leaf of three a function of two
    r1, l1 = op_ns["rbind"](leaf_ns["c_sub"], 2), op_ns["lbind"](leaf_ns["c_sub"], 10)
    assert r1(7) == 5 and l1(7) == 3
    for f in (r1, l1):
        with pytest.raises(TypeError):
            f(7, 8)
        with pytest.raises(TypeError):
            f()
    assert BB.declared_parameters(leaf_ns["interval"]) == 3
    r2, l2 = op_ns["rbind"](leaf_ns["interval"], 1), op_ns["lbind"](leaf_ns["interval"], 0)
    assert r2(0, 3) == leaf_ns["interval"](0, 3, 1) and l2(3, 1) == leaf_ns["interval"](0, 3, 1)
    for f in (r2, l2):
        with pytest.raises(TypeError):
            f(3)
    # the library text this study executes binds with a variable number of arguments: what a bound function accepts
    # shows only when it is called, and called with the right number of arguments it gives the library's own result
    bare = dslx.library_namespace(())
    assert BB.declared_parameters(r1) is None and BB.declared_parameters(op_ns["compose"](leaf_ns["c_len"], leaf_ns["c_tuple"])) == 1
    assert r1(7) == bare["rbind"](B.c_sub, 2)(7) and l1(7) == bare["lbind"](B.c_sub, 10)(7)
    assert r2(0, 3) == bare["rbind"](bare["interval"], 1)(0, 3) and l2(3, 1) == bare["lbind"](bare["interval"], 0)(3, 1)


# ---------------------------------------------------------------- the arity rule (behind the switch presets ARITY_RULE)
def one_parameter(a):
    return (a,)


def two_parameters(a, b):
    return (a, b)


def three_parameters(a, b, c):
    return (a, b, c)


def four_parameters(a, b, c, d):
    return (a, b, c, d)


def five_parameters(a, b, c, d, e):
    return (a, b, c, d, e)


def test_the_arity_rule_is_on_as_decided_and_names_the_seven():
    assert P.ARITY_RULE is True and P.MAX_FN == 16000 and set(BB.ARITY_RULES) == set(P.RETAINED)
    assert {c for c, _ in BB.ARITY_RULES.values()} == {"function_making_refused_by_arity", "power_of_a_function_without_one_parameter"}
    assert BB.ARITY_RULES["power"][0] == "power_of_a_function_without_one_parameter"
    assert BB.declared_parameters(one_parameter) == 1 and BB.declared_parameters(five_parameters) == 5
    assert BB.declared_parameters(len) is None and BB.declared_parameters(3) is None
    assert BB.declared_parameters(lambda *a: 1) is None and BB.declared_parameters(lambda a, b=2: 1) is None
    assert BB.declared_parameters(lambda a, **k: 1) is None and BB.declared_parameters(lambda a, *, b: 1) is None
    assert BB.declared_parameters(B.c_sub) == 2 and BB.declared_parameters(B.c_if_else) == 3


def test_every_function_valued_leaf_has_a_fixed_signature():
    """Under the size limits of this experiment every function argument of a function-making application is a
    leaf, so the arity rule judges every one of them."""
    for name in ("backdrop", "mapply", "rot180"):
        ex, hidden = dev_examples(name)
        for block_set in BB.BLOCK_SETS:
            leaves = BB.build(block_set, hidden, ex)[1]
            functions = [v for t, vals in leaves for v in vals if callable(v)]
            assert len(functions) >= 9 * 64 and all(BB.declared_parameters(f) is not None for f in functions)
            assert {BB.declared_parameters(f) for f in functions} <= {1, 2, 3, 4}


def test_the_arity_rule_refuses_before_the_library_function_is_called():
    lib = dslx.library_namespace(())
    counts = BB.new_counts()
    called = []

    def spy(name):
        def f(*a):
            called.append(name)
            return lib[name](*a)
        return f
    w = {n: BB.operation_wrapper(spy(n), n, counts, arity_rule=True) for n in P.RETAINED}
    o, t, th, fo, fi = one_parameter, two_parameters, three_parameters, four_parameters, five_parameters
    refused = [("compose", (t, o)), ("compose", (o, t)), ("compose", (th, th)), ("chain", (o, o, t)), ("chain", (t, o, o)), ("chain", (o, th, o)),
               ("matcher", (t, 1)), ("matcher", (th, 1)), ("rbind", (o, 1)), ("lbind", (o, 1)),
               ("fork", (o, o, o)), ("fork", (th, o, o)), ("fork", (t, t, o)), ("fork", (t, o, t))]
    for i, (name, args) in enumerate(refused):
        with pytest.raises(TypeError):
            w[name](*args)
        assert counts["function_making_refused_by_arity"] == i + 1 and called == []          # refused before the call
    for i, args in enumerate([(t, 2), (th, 3), (t, 1), (fo, 1)]):                              # power: its own counter
        with pytest.raises(TypeError):
            w["power"](*args)
        assert counts["power_of_a_function_without_one_parameter"] == i + 1 and called == []
    assert counts["function_making_refused_by_arity"] == len(refused)
    # every accepted form gives what the library's own operation gives, on invented inputs
    accepted = [("compose", (o, o), (5,)), ("chain", (o, o, o), (5,)), ("matcher", (o, (5,)), (5,)), ("rbind", (t, 1), (5,)), ("lbind", (t, 1), (5,)),
                ("rbind", (th, 1), (5, 6)), ("lbind", (th, 1), (5, 6)), ("rbind", (fo, 1), (5, 6, 7)), ("lbind", (fo, 1), (5, 6, 7)),
                ("rbind", (fi, 1), (5, 6, 7, 8)), ("lbind", (fi, 1), (5, 6, 7, 8)),
                ("power", (o, 3), (5,)), ("power", (o, 1), (5,)), ("fork", (t, o, o), (5,))]
    for name, args, inputs in accepted:
        assert w[name](*args)(*inputs) == lib[name](*args)(*inputs)
    assert counts["function_making_refused_by_arity"] == len(refused) and len(called) == len(accepted)
    # what has no fixed signature is never judged and never refused on its account: a value without a code object,
    # a function bound by lbind or rbind (it takes a variable number of arguments), a function with a default
    bound = w["lbind"](t, 1)
    assert BB.declared_parameters(bound) is None and bound.__code__.co_argcount == 0
    assert w["compose"](bound, o)(5) == (1, (5,)) and w["chain"](o, bound, o)(5) == ((1, (5,)),) and callable(w["matcher"](7, 7))
    assert callable(w["compose"](len, o)) and callable(w["power"](bound, 2)) and callable(w["fork"](bound, bound, bound))
    assert callable(w["rbind"](bound, 1)) and callable(w["lbind"](lambda a, b=2: a, 1)) and callable(w["compose"](lambda a, b=2: a, o))
    assert counts["function_making_refused_by_arity"] == len(refused) and counts["power_of_a_function_without_one_parameter"] == 4
    assert counts["function_results_refused"] == 0 and counts["containers_holding_a_function_refused"] == 0
    # the wrapper of the seven in a search (it also keeps the record of function-making) refuses and admits the same
    c2, book = BB.new_counts(), BB.new_function_book(1)
    m = {n: BB.function_making_wrapper(lib[n], n, c2, book, True) for n in P.RETAINED}
    for name, args in refused + [("power", (t, 2)), ("power", (th, 3)), ("power", (t, 1)), ("power", (fo, 1))]:
        with pytest.raises(TypeError):
            m[name](*args)
    for name, args, inputs in accepted:
        assert m[name](*args)(*inputs) == lib[name](*args)(*inputs)
    assert c2["function_making_refused_by_arity"] == len(refused) and c2["power_of_a_function_without_one_parameter"] == 4
    assert book["by_operation"] == {} and book["calls_outside_the_enumerator"] == len(refused) + 4 + len(accepted)
    off = BB.function_making_wrapper(lib["compose"], "compose", BB.new_counts(), BB.new_function_book(1), False)
    assert callable(off(t, o))                                       # with the rule off nothing is refused

    def hungry(*a):
        raise MemoryError()
    with pytest.raises(G.ResourceStop):
        BB.function_making_wrapper(hungry, "compose", BB.new_counts(), BB.new_function_book(1), True)(o, o)


def test_what_the_arity_rule_removes():
    """Every form refused under the first reason, made by the library's own operation, fails on the number of
    arguments whenever it is called with one, two or three arguments. The second reason is kept apart: for n
    above 1 power of a function without exactly one parameter fails on every call, but power(function, 1) is the
    function itself, so there the rule refuses a second entry for that function, not a function that fails."""
    lib = dslx.library_namespace(())
    o, t, th = one_parameter, two_parameters, three_parameters
    always_failing = [("compose", (t, o)), ("compose", (o, t)), ("chain", (o, o, t)), ("chain", (t, o, o)), ("matcher", (t, 1)),
                      ("rbind", (o, 1)), ("lbind", (o, 1)), ("power", (t, 2)), ("power", (th, 3)),
                      ("fork", (o, o, o)), ("fork", (t, t, o)), ("fork", (t, o, t))]
    for name, args in always_failing:
        f = lib[name](*args)
        for inputs in ((5,), (5, 6), (5, 6, 7)):
            with pytest.raises(TypeError):
                f(*inputs)
    assert lib["rbind"](o, 1)() == (1,) and lib["lbind"](o, 1)() == (1,)          # bound once: callable with no argument only
    assert lib["power"](t, 1) is t and lib["power"](t, 1)(5, 6) == (5, 6)          # a duplicate, not a failing function
    off, c0 = BB.new_counts(), BB.new_counts()
    assert callable(BB.operation_wrapper(lib["compose"], "compose", off, arity_rule=False)(t, o)) and off["function_making_refused_by_arity"] == 0
    assert BB.operation_wrapper(lambda f, c: 1, "apply", c0, arity_rule=True)(t, ()) == 1 and c0["function_making_refused_by_arity"] == 0


def test_the_arity_rule_reaches_a_search_through_build():
    target, argsets, size, keep_ops, keep_fn, want = RETAINED_TARGETS["lbind"]
    ex = examples_of(target, argsets)
    on, off = BB.new_counts(), BB.new_counts()
    for counts, rule in ((off, False), (on, True)):
        ops, leaves, Y = BB.build("C", (), ex, counts=counts, arity_rule=rule)[:3]
        ops = [x for x in ops if x[0] in keep_ops | {"compose"}]
        leaves = [leaf for leaf in leaves if leaf[0][0] != "FN" or leaf[0][1] in keep_fn | {"c_len", "c_neg"}]
        r = S.search(ops, leaves, Y, 60.0, size, P.MAX_FN, P.MAX_BANK)
        assert r["found"][0] == want
    assert off["function_making_refused_by_arity"] == 0 and on["function_making_refused_by_arity"] > 0


# ---------------------------------------------------------------- no block is handed an argument that holds a function
def counting1(f, book):
    def block(a):
        book["calls"] += 1
        if type(a) in (tuple, frozenset) and BB.holds_function(a):
            book["holding"] += 1
        return f(a)
    return block


def counting2(f, book):
    def block(a, b):
        book["calls"] += 1
        for v in (a, b):
            if type(v) in (tuple, frozenset) and BB.holds_function(v):
                book["holding"] += 1
        return f(a, b)
    return block


def counting3(f, book):
    def block(a, b, c):
        book["calls"] += 1
        for v in (a, b, c):
            if type(v) in (tuple, frozenset) and BB.holds_function(v):
                book["holding"] += 1
        return f(a, b, c)
    return block


def with_counting_blocks(ops, leaves, book):
    """The same build with every block of C replaced, as an operation AND as a function-valued leaf, by a function
    of the same number of parameters that walks each argument at every depth and then calls the block."""
    make = {1: counting1, 2: counting2, 3: counting3}
    counted = {b.id: make[len(b.params)](b.fn, book) for b in B.CATALOGUE}
    assert all(BB.declared_parameters(counted[b.id]) == len(b.params) for b in B.CATALOGUE)
    ops = [(n, counted[n] if n in counted else f, acc, mk) for n, f, acc, mk in ops]
    leaves = [(t, tuple(counted[t[1]] for _ in v) if t[0] == "FN" and t[1] in counted else v) for t, v in leaves]
    return ops, leaves


@pytest.mark.parametrize("name", ["mapply", "backdrop", "rot180"])
def test_no_block_is_ever_handed_an_argument_that_holds_a_function(name):
    """A development test of the protocol's argument (section 3.2, "What a block of C can be handed"). Test-only
    instrumentation: the run itself keeps the top-level checks of arguments. Whole searches over C (size limit 5)
    and over LC (size limit 4) on the nine fit examples of a development name, under the declared limits: every
    argument of every call of a block, by whatever route, is walked at every depth; none holds a function."""
    ex, hidden = dev_examples(name)
    for block_set, size in (("C", 5), ("LC", 4)):
        book = dict(calls=0, holding=0)
        ops, leaves, Y = BB.build(block_set, hidden, ex)[:3]
        ops, leaves = with_counting_blocks(ops, leaves, book)
        r = S.search(ops, leaves, Y, P.ALLOWANCE, size, P.MAX_FN, P.MAX_BANK)
        assert r["stop"] in ("found", "size_exhausted", "size_exhausted_function_cap", "budget_cpu", "budget_bank")
        assert book["holding"] == 0 and book["calls"] > 10000, (name, block_set, book, r["stop"])


# ---------------------------------------------------------------- the record of function-making counts what the enumerator did
def watching_the_enumerator(ops):
    """(ops, held): the same operations, the plain ones called through a function that, the first time the enumerator
    itself calls it, keeps the enumerator's own state: its counters (`st`, with the number of function-valued entries)
    and its bank by size (`pools`). Both are the enumerator's own objects, so after the search they hold its final
    state. The seven retained operations are left as they are (their wrapper reads the frame of its caller)."""
    import sys
    held = {}
    code = S.search.__code__

    def through(f):
        def call(*a):
            if not held:
                frame = sys._getframe(1)
                if frame.f_code is code:
                    held.update(st=frame.f_locals["st"], pools=frame.f_locals["pools"])
            return f(*a)
        return call
    return [(n, f if n in P.RETAINED else through(f), acc, mk) for n, f, acc, mk in ops], held


def enumerator_at_return(ops, run):
    """Run one call of the enumerator over `ops` and return (its result, what its own state held at the end: the
    number of function-valued entries and the constant flags of every function-valued entry)."""
    watched, held = watching_the_enumerator(ops)
    r = run(watched)
    flags = {e[2] for by_tags in held["pools"].values() for tags, entries in by_tags.items() if "F" in tags for e in entries}
    return r, dict(nfn=held["st"]["nfn"], constant_flags_of_function_entries=flags)


@pytest.mark.parametrize("name", ["lbind", "fork", "power", "chain"])
def test_the_record_agrees_with_the_enumerators_own_count_of_function_valued_entries(name):
    """The wrapper counts one application for every n_examples calls that return: that relies on the enumerator
    evaluating a function-making application example by example, never once for all examples. Here the total
    admitted is compared with the growth of function-valued entries inside the enumerator, and every application
    offered is accounted for. If the enumerator ever evaluated such an application once for all examples (or if a
    function-valued entry could be constant), these would differ."""
    target, argsets, size, keep_ops, keep_fn, want = RETAINED_TARGETS[name]
    for max_fn in (P.MAX_FN, 12):
        counts, book = BB.new_counts(), BB.new_function_book(len(argsets))
        ops, leaves, Y = BB.build("C", (), examples_of(target, argsets), counts=counts, book=book)[:3]
        ops = [o for o in ops if o[0] in keep_ops | set(P.RETAINED)]
        leaves = [leaf for leaf in leaves if leaf[0][0] != "FN" or leaf[0][1] in keep_fn]
        fn_leaves = sum(1 for _, v in leaves if dslx.tagset(v) == frozenset("F"))
        r, at_return = enumerator_at_return(ops, lambda watched: S.search(watched, leaves, Y, 120.0, size, max_fn, P.MAX_BANK))
        rows = [row for by_size in book["by_operation"].values() for row in by_size.values()]
        assert rows and all(row["offered"] == sum(row[k] for k in BB.FUNCTION_ROW[1:]) for row in rows)
        assert book["admitted"] == sum(row["admitted"] for row in rows) > 0
        assert at_return["nfn"] == fn_leaves + book["admitted"]      # the growth of function-valued entries inside the enumerator
        assert at_return["constant_flags_of_function_entries"] == {False}
        assert book["calls_outside_the_enumerator"] == 0
        if max_fn == 12:
            assert r["function_cap_reached"] is True and at_return["nfn"] == 12 and book["cap_reached_at"]["function_valued_entries"] == 12
            assert sum(row["refused_by_cap"] for row in rows) >= 1 and book["first_refused_by_cap"] is not None
        else:
            assert r["found"][0] == want and book["cap_reached_at"] is None and sum(row["refused_by_cap"] for row in rows) == 0
    # the count of calls is what makes one application: with a wrong number of examples the record would not add up
    wrong, book2 = BB.new_counts(), BB.new_function_book(len(argsets) + 1)
    ops2, leaves2, Y2 = BB.build("C", (), examples_of(target, argsets) + [examples_of(target, argsets)[0]], counts=wrong, book=book2)[:3]
    ops2 = [o for o in ops2 if o[0] in keep_ops | set(P.RETAINED)]
    leaves2 = [(t, v[:-1]) for t, v in leaves2 if t[0] != "FN" or t[1] in keep_fn]
    r2, at_return2 = enumerator_at_return(ops2, lambda watched: S.search(watched, leaves2, Y2[:-1], 120.0, size, P.MAX_FN, P.MAX_BANK))
    assert at_return2["nfn"] != sum(1 for _, v in leaves2 if dslx.tagset(v) == frozenset("F")) + book2["admitted"]
