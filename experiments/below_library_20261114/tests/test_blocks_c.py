"""Tests of the catalogue of C (blocks_c.py) on invented values and invented functions. No library operation is
searched here. Author: Chimdi Walter Ndubuisi
Run: env PYTHONHASHSEED=0 sh scripts/with_cpu_slot.sh python3 -s -B -m pytest -q -p no:cacheprovider experiments/below_library_20261114/tests
"""
import dis
import itertools
import os
import re
import signal
import time

import pytest

import bl_frozen  # noqa: F401
import dslx
import blocks_c as B
import guards_bl as G
import presets_bl as P

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = B.namespace()
LIB = dslx.load()


def typed_equal(a, b):
    """Equal typed canonical text, and for two frozensets the same order of walking as well."""
    if dslx.canon(a) != dslx.canon(b) or type(a) is not type(b):
        return False
    return list(a) == list(b) if isinstance(a, frozenset) else True


def has_callable(v):
    if callable(v):
        return True
    return isinstance(v, (tuple, frozenset)) and any(has_callable(e) for e in v)


def nested(levels):
    """A tuple nested `levels` deep: nested(1) == (1,), nested(2) == ((1,),)."""
    v = (1,)
    for _ in range(levels - 1):
        v = (v,)
    return v


# ---------------------------------------------------------------- the reference: the Python form of every block
REF = {
    "c_len": lambda c: len(c), "c_abs": lambda a: abs(a), "c_tuple": lambda c: tuple(c),
    "c_frozenset": lambda c: frozenset(c), "c_enumerate": lambda c: tuple(enumerate(c)),
    "c_zip": lambda a, b: tuple(zip(a, b)), "c_zip_star": lambda c: tuple(zip(*c)),
    "c_range1": lambda a: tuple(range(a)), "c_range2": lambda a, b: tuple(range(a, b)),
    "c_range3": lambda a, b, step: tuple(range(a, b, step)), "c_int": lambda x: int(x),
    "c_first": lambda c: next(iter(c)), "c_max": lambda c: max(c), "c_min": lambda c: min(c),
    "c_max_default0": lambda c: max(c, default=0), "c_min_default0": lambda c: min(c, default=0),
    "c_max_key": lambda c, f: max(c, key=f), "c_min_key": lambda c, f: min(c, key=f),
    "c_max_key_default0": lambda c, f: max(c, key=f, default=0),
    "c_min_key_default0": lambda c, f: min(c, key=f, default=0),
    "c_max2": lambda a, b: max(a, b), "c_min2": lambda a, b: min(a, b),
    "c_sorted_key": lambda c, f: tuple(sorted(c, key=f)), "c_sum": lambda c: sum(c),
    "c_is_integer": lambda x: isinstance(x, int), "c_is_tuple": lambda x: isinstance(x, tuple),
    "c_like": lambda c, items: type(c)(items),
    "c_add": lambda a, b: a + b, "c_sub": lambda a, b: a - b, "c_mul": lambda a, b: a * b,
    "c_floordiv": lambda a, b: a // b, "c_mod": lambda a, b: a % b, "c_neg": lambda a: -a,
    "c_concat": lambda a, b: a + b, "c_set_difference": lambda a, b: a - b, "c_union": lambda a, b: a | b,
    "c_intersection": lambda a, b: a & b, "c_eq": lambda a, b: a == b, "c_ne": lambda a, b: a != b,
    "c_lt": lambda a, b: a < b, "c_le": lambda a, b: a <= b, "c_gt": lambda a, b: a > b, "c_ge": lambda a, b: a >= b,
    "c_in": lambda x, c: x in c, "c_not_in": lambda x, c: x not in c,
    "c_and": lambda a, b: a and b, "c_or": lambda a, b: a or b, "c_not": lambda a: not a,
    "c_pair": lambda a, b: (a, b), "c_single": lambda a: (a,), "c_set1": lambda a: frozenset({a}),
    "c_item0": lambda x: x[0], "c_item1": lambda x: x[1], "c_item": lambda x, i: x[i],
    "c_reverse": lambda x: x[::-1], "c_slice": lambda x, a, b: x[a:b], "c_slice_to": lambda x, b: x[:b],
    "c_slice_from": lambda x, a: x[a:], "c_if_else": lambda c, a, b: a if c else b,
    "c_call1": lambda f, x: f(x), "c_call2": lambda f, x, y: f(x, y),
    "c_map_tuple": lambda f, c: tuple(f(e) for e in c), "c_map_set": lambda f, c: frozenset(f(e) for e in c),
    "c_keep": lambda p, c: tuple(e for e in c if p(e)),
    "c_pairs": lambda a, b: tuple((i, j) for i in a for j in b),
    "c_issubset": lambda a, b: a.issubset(b), "c_count": lambda c, x: c.count(x), "c_index": lambda c, x: c.index(x),
}
INTS = [0, 1, -1, 2, 5, -7]
BOOLS = [True, False]
TUPLES = [(), (3, 1, 2, 3), (5,), ((1, 2), (3, 4)), ((1, 2, 3), (4, 5, 6)), (True, False), ((), (1,)), (1, (2,)),
          (frozenset({1}), frozenset({2, 3}))]
SETS = [frozenset(), frozenset({4, 1, 9}), frozenset({(0, 1), (2, 3)}), frozenset({frozenset({1}), frozenset({2, 3})}),
        frozenset({(3, (0, 1)), (3, (1, 1))}), frozenset({1, 5})]
SAMPLES = {
    "Integer": INTS, "Boolean": BOOLS, "Boolean|Integer": BOOLS + [0, 3, -2], "Tuple": TUPLES, "FrozenSet": SETS,
    "Container": TUPLES + SETS, "ContainerContainer": [t for t in TUPLES + SETS if dslx.tag(t) in dslx.ACC["ContainerContainer"]],
    "Any": INTS[:4] + BOOLS + TUPLES[:6] + SETS[:4],
}


def double(e):
    return (e, e)


def itself(e):
    return e


def is_big_int(e):
    return type(e) is int and e > 1


def boom(e):
    return 1 // 0


def zero(e):
    return 0


def negated_if_int(e):
    return -e if type(e) is int else 0


def tuple_length(e):
    return len(e)


def plus(x, y):
    return x + y


def pair(x, y):
    return (x, y)


# invented functions for the parameters typed Callable (by block)
FUNCTIONS = {
    "c_max_key": [itself, zero, negated_if_int, tuple_length, boom], "c_min_key": [itself, zero, negated_if_int, tuple_length, boom],
    "c_max_key_default0": [itself, zero, negated_if_int, boom], "c_min_key_default0": [itself, zero, negated_if_int, boom],
    "c_sorted_key": [itself, zero, negated_if_int, tuple_length, boom],
    "c_call1": [itself, double, tuple_length, boom, is_big_int], "c_call2": [plus, pair, boom],
    "c_map_tuple": [itself, double, tuple_length, boom, is_big_int], "c_map_set": [itself, double, tuple_length, boom, is_big_int],
    "c_keep": [is_big_int, lambda e: True, lambda e: False, boom, lambda e: e > 1],
}


def cases(b):
    """In-domain argument tuples of a block: the product of the samples of its parameters."""
    pools = [FUNCTIONS[b.id] if ann == "Callable" else SAMPLES[ann] for _, ann in b.params]
    return list(itertools.product(*pools))


def outcome(fn, args):
    try:
        return "ok", fn(*args)
    except Exception as e:                                       # noqa: BLE001 (the reference and the block may raise)
        return "raises", e


# ---------------------------------------------------------------- the catalogue itself
def protocol_table_ids():
    for name in ("PROTOCOL.md", "PROTOCOL_DRAFT.md"):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            ids = []
            for line in open(p, encoding="utf-8"):
                if line.startswith("| `c_"):
                    ids += re.findall(r"`(c_[a-z0-9_]+)`", line.split("|")[1])
            return ids
    return None


def test_the_catalogue_is_the_protocols_table_in_its_order():
    ids = [b.id for b in B.CATALOGUE]
    assert len(ids) == 68 == len(set(ids)) and set(ids) == set(REF)
    table = protocol_table_ids()
    if table is None:
        pytest.skip("no protocol text in this folder")
    assert table == ids
    assert ids[ids.index("c_if_else") + 1:ids.index("c_map_tuple")] == ["c_call1", "c_call2"]


def test_entries_are_complete_and_typed_from_the_frozen_annotations():
    names = set(LIB["lib_order"]) | set(LIB["const_names"]) | set(LIB["fn_leaf_names"])
    for b in B.CATALOGUE:
        assert b.nodes == 1 and b.id.startswith("c_") and b.id not in names and b.python
        assert 1 <= len(b.params) <= 3
        for _, ann in b.params:
            assert all(part in dslx.ACC for part in ann.split("|"))
        assert b.result in dslx.ACC and b.result != "Callable"          # no block of C makes a function
        assert b.fn_leaf == (len(b.params) in (1, 2))
    leaves = B.function_leaf_names()
    assert "c_call1" in leaves and "c_call2" not in leaves and len(leaves) == 64
    assert [x for x in (b.id for b in B.CATALOGUE) if x not in leaves] == ["c_range3", "c_slice", "c_if_else", "c_call2"]
    assert B.BY_ID["c_int"].params == (("x", "Boolean|Integer"),) and B.acc_of("Boolean|Integer") == frozenset("BI")
    assert B.BY_ID["c_call1"].params == (("f", "Callable"), ("x", "Any")) and B.BY_ID["c_call1"].result == "Any"
    assert B.BY_ID["c_call2"].params == (("f", "Callable"), ("x", "Any"), ("y", "Any"))
    assert B.BY_ID["c_if_else"].params == (("c", "Boolean"), ("a", "Any"), ("b", "Any"))
    assert B.EMPTY_TUPLE == () and B.EMPTY_SET == frozenset() and B.CONSTANTS == {"EMPTY_TUPLE": (), "EMPTY_SET": frozenset()}
    assert (B.MAX_ELEMENTS, B.MAX_NESTING, B.MAX_INT_BITS) == (3000, 8, 40) == (P.MAX_ELEMENTS, P.MAX_NESTING, P.MAX_INT_BITS)


def test_the_exported_function_of_a_block_is_the_checked_one():
    ops = B.ops()
    assert [o[0] for o in ops] == [b.id for b in B.CATALOGUE]
    for b, (name, fn, acc, makes_fn) in zip(B.CATALOGUE, ops):
        assert fn is b.fn is NS[b.id] is getattr(B, b.id)           # one function per block, everywhere
        assert fn.__name__ == b.id and dslx.canon(fn) == "f:" + b.id
        assert fn.__code__.co_argcount == len(b.params) and not fn.__code__.co_flags & 0x0C
        assert makes_fn is False and acc == tuple(B.acc_of(a) for _, a in b.params)
        with pytest.raises(TypeError):
            fn(*([0] * (len(b.params) + 1)))                        # a wrong number of arguments: an ordinary error
        with pytest.raises(TypeError):
            fn(*([0] * (len(b.params) - 1)))
    assert B.namespace() is not B.namespace()


# ---------------------------------------------------------------- every block against its Python form
@pytest.mark.parametrize("b", B.CATALOGUE, ids=lambda b: b.id)
def test_block_against_python_on_invented_values(b):
    ref, n_ok, n_raise = REF[b.id], 0, 0
    for args in cases(b):
        r_kind, r = outcome(ref, args)
        kind, got = outcome(b.fn, args)
        if b.id == "c_keep" and r_kind == "ok":
            p, c = args
            if any(type(p(e)) is not bool for e in c):               # truthiness of a value that is not a Boolean: outside C
                assert kind == "raises" and isinstance(got, TypeError), args
                continue
        if r_kind == "raises":
            assert kind == "raises", (b.id, args, got)               # Python raises inside the domain: so does the block
            n_raise += 1
            continue
        if has_callable(r):
            assert kind == "raises" and isinstance(got, TypeError), (b.id, args)
            continue
        assert kind == "ok", (b.id, args, got)
        assert typed_equal(got, r), (b.id, args, got, r)
        n_ok += 1
    assert n_ok >= 2, b.id                                           # the comparison is never empty


def test_errors_inside_the_domain_are_pythons_own():
    with pytest.raises(ZeroDivisionError):
        B.c_floordiv(1, 0)
    with pytest.raises(ZeroDivisionError):
        B.c_mod(1, 0)
    with pytest.raises(IndexError):
        B.c_item((1, 2), 2)
    with pytest.raises(IndexError):
        B.c_item0(())
    with pytest.raises(IndexError):
        B.c_item1((1,))
    for f in (B.c_max, B.c_min):
        with pytest.raises(ValueError):
            f(())
        with pytest.raises(TypeError):
            f((1, (2,)))                                             # values Python cannot order
    with pytest.raises(ValueError):
        B.c_max_key((), itself)
    assert B.c_max_default0(()) == 0 and B.c_min_default0(frozenset()) == 0 and B.c_max_key_default0((), itself) == 0
    with pytest.raises(ValueError):
        B.c_index((1, 2), 3)
    with pytest.raises(ValueError):
        B.c_range3(0, 5, 0)
    with pytest.raises(ValueError):
        B.c_first(())                                                # ValueError where next(iter(())) raises StopIteration
    with pytest.raises(ValueError):
        B.c_first(frozenset())
    assert B.c_item((1, 2, 3), -1) == 3 and B.c_slice((1, 2, 3, 4), -3, -1) == (2, 3) and B.c_range3(5, 0, -2) == (5, 3, 1)
    assert B.c_floordiv(-7, 2) == -4 and B.c_mod(-7, 2) == 1 and B.c_mod(7, -2) == -1


def test_ties_of_max_and_min_follow_python():
    c = ((1, 2), (3, 0), (0, 3), (2, 1))
    total = lambda e: e[0] + e[1]                                     # noqa: E731  (every element has the same key)
    assert B.c_max_key(c, total) == max(c, key=total) == (1, 2) and B.c_min_key(c, total) == (1, 2)
    assert B.c_sorted_key(c, total) == c                              # a stable sort keeps the order of ties
    s = frozenset(c)
    assert B.c_max_key(s, total) == max(s, key=total) == next(iter(s)) and B.c_first(s) == next(iter(s))
    assert B.c_max2(3, 3) == 3 and B.c_min((2, 1, 1)) == 1


# ---------------------------------------------------------------- order and duplicates of conversions
def test_order_and_duplicates_of_tuple_and_frozenset_conversions():
    t = (3, 1, 3, 2, 1)
    s = frozenset({9, 4, 1, 16, 25})
    assert B.c_tuple(t) == t and B.c_tuple(s) == tuple(s) and list(B.c_tuple(s)) == list(s)     # Python's own order
    assert B.c_frozenset(t) == frozenset({1, 2, 3}) and len(B.c_frozenset(t)) == 3              # duplicates go
    assert B.c_like(t, s) == tuple(s) and B.c_like(s, t) == frozenset(t) and type(B.c_like(s, t)) is frozenset
    assert B.c_like((), t) == t and B.c_like(frozenset(), s) == s
    assert B.c_map_tuple(itself, t) == t and B.c_map_tuple(itself, s) == tuple(s)               # order and duplicates kept
    assert B.c_map_set(zero, t) == frozenset({0}) and B.c_keep(is_big_int, t) == (3, 3, 2)
    assert B.c_enumerate(s) == tuple(enumerate(s)) and B.c_zip(s, t) == tuple(zip(s, t))
    assert B.c_pairs((1, 2), (5, 6)) == ((1, 5), (1, 6), (2, 5), (2, 6)) and B.c_reverse(t) == (1, 2, 3, 1, 3)
    assert B.c_zip_star(((1, 2, 3), (4, 5, 6))) == ((1, 4), (2, 5), (3, 6)) and B.c_zip_star(()) == ()
    assert B.c_concat(t, (3,)) == t + (3,) and B.c_count(t, 3) == 2 and B.c_index(t, 1) == 1
    two = frozenset({(0, 1)}) | frozenset({(5, 5)})
    assert B.c_union(frozenset({(0, 1)}), frozenset({(5, 5)})) == two and B.c_sorted_key(s, itself) == (1, 4, 9, 16, 25)


# ---------------------------------------------------------------- Booleans, integers, the eager rule
def test_booleans_and_integers_are_distinct_domains():
    for f in (B.c_add, B.c_sub, B.c_mul, B.c_floordiv, B.c_mod, B.c_lt, B.c_le, B.c_gt, B.c_ge, B.c_max2, B.c_min2, B.c_range2):
        with pytest.raises(TypeError):
            f(True, 1)
        with pytest.raises(TypeError):
            f(1, False)
    for f in (B.c_abs, B.c_neg, B.c_range1):
        with pytest.raises(TypeError):
            f(True)
    for f in (B.c_and, B.c_or):
        with pytest.raises(TypeError):
            f(1, True)
        with pytest.raises(TypeError):
            f(True, 0)
        with pytest.raises(TypeError):
            f((), True)
    for bad in (0, 1, (), (True,), frozenset()):
        with pytest.raises(TypeError):
            B.c_not(bad)
        with pytest.raises(TypeError):
            B.c_if_else(bad, 1, 2)
    assert B.c_and(True, False) is False and B.c_or(False, True) is True and B.c_not(False) is True
    assert B.c_int(True) == 1 and type(B.c_int(True)) is int and B.c_int(False) == 0 and B.c_int(7) == 7
    with pytest.raises(TypeError):
        B.c_int((1,))
    assert B.c_is_integer(True) is True and B.c_is_integer(3) is True and B.c_is_integer((3,)) is False   # isinstance(x, int)
    assert B.c_is_tuple(()) is True and B.c_is_tuple(frozenset()) is False and B.c_is_tuple(1) is False
    assert B.c_eq(True, 1) is True and B.c_eq((1, 2), (1, 2)) is True and B.c_ne((1,), frozenset({1})) is True   # Python's ==
    with pytest.raises(TypeError):
        B.c_item((1, 2), True)
    with pytest.raises(TypeError):
        B.c_sum(((1,), (2,)))
    assert B.c_sum((True, True, 3)) == 5 and type(B.c_sum((True,))) is int


def test_the_condition_of_keep_must_give_a_boolean_for_every_element():
    assert B.c_keep(is_big_int, (1, 2, 3)) == (2, 3)
    for truthy in (itself, tuple_length, zero, lambda e: None, lambda e: "yes"):
        with pytest.raises(TypeError):
            B.c_keep(truthy, (1, (2,)) if truthy is not tuple_length else ((1,), (2, 3)))
    seen = []

    def first_two_true_then_not_boolean(e):
        seen.append(e)
        return True if len(seen) < 3 else 1
    with pytest.raises(TypeError):
        B.c_keep(first_two_true_then_not_boolean, (5, 6, 7, 8))
    assert seen == [5, 6, 7]


def test_eager_both_branches_and_both_operands_are_used():
    assert B.c_if_else(True, 1, 2) == 1 and B.c_if_else(False, 1, (2,)) == (2,)
    for unused in (len, "text", None, [1]):
        with pytest.raises(TypeError):
            B.c_if_else(True, 1, unused)                               # the domain of the branch that is not returned is checked too
        with pytest.raises(TypeError):
            B.c_if_else(False, unused, 1)
    # the bounds and the function rule are for the value a block returns: an argument is checked for its domain only
    assert B.c_if_else(True, 1, 2 ** 41) == 1 and B.c_if_else(False, (len,), 1) == 1
    with pytest.raises(ValueError):
        B.c_if_else(False, 1, 2 ** 41)
    with pytest.raises(TypeError):
        B.c_if_else(True, (len,), 1)
    with pytest.raises(TypeError):
        B.c_and(False, 5)                                              # no short circuit
    with pytest.raises(TypeError):
        B.c_or(True, 5)
    calls = []

    def positive(e):
        calls.append(e)
        return e > 0
    assert B.c_keep(positive, (1, -1, 2)) == (1, 2) and calls == [1, -1, 2]          # applied to every element
    with pytest.raises(TypeError):
        B.c_keep(positive, (1, 2, (3,)))                               # an error on a later element: no value at all


# ---------------------------------------------------------------- the domain of every argument is the tag rule
VALUES_OF_EVERY_TAG = [True, 0, -3, 2 ** 50, (), frozenset(), (1, 2), (1, 2, 3), ((1, 2), (3, 4)), (((1,),),), ((), ()),
                       (True, 1), frozenset({1, 2}), frozenset({(1, 2)}), frozenset({(1, (2, 3))}), frozenset({(1, 2, 3)}),
                       frozenset({frozenset()}), frozenset({frozenset({(1, 2)})}), frozenset({frozenset({(1, (2, 3))})}),
                       frozenset({frozenset({1})}), frozenset({True}), len, itself, B.c_len, None, "text", 1.5, [1], {1}, {1: 2}]


def test_values_cover_every_runtime_tag():
    assert {dslx.tag(v) for v in VALUES_OF_EVERY_TAG} == set("B I T G TU TT GT O X OS XS Z FU E F U".split())


@pytest.mark.parametrize("ann", sorted(B._DOMAIN))
def test_domain_validation_is_the_tag_rule(ann):
    check = B._DOMAIN[ann]
    for v in VALUES_OF_EVERY_TAG:
        if ann == "Callable":
            want = callable(v)
        else:
            want = dslx.tag(v) in B.acc_of(ann)
            if ann == "Tuple":
                want = want and type(v) is tuple
            if ann == "FrozenSet":
                want = want and type(v) is frozenset
        if want:
            check(v)
        else:
            with pytest.raises(TypeError):
                check(v)
    assert {a for b in B.CATALOGUE for _, a in b.params} == set(B._DOMAIN)


def large_invented_set(n=30000, seed=20261114):
    """Invented values of every kind: Booleans, integers (small and beyond the bounds), tuples and frozensets,
    empty and nested, holding functions or values of unknown type, and functions and unknown values themselves."""
    import random
    r = random.Random(seed)
    scalars = [True, False, 0, 1, -1, 7, 2 ** 40, -2 ** 63, len, itself, B.c_len, None, "text", 1.5]

    def value(depth):
        k = r.random()
        if depth >= 4 or k < 0.35:
            return r.choice(scalars) if r.random() < 0.6 else r.randint(-9, 9)
        items = [value(depth + 1) for _ in range(r.randint(0, 4))]
        if k < 0.7:
            return tuple(items)
        return frozenset(items)
    out = list(VALUES_OF_EVERY_TAG) + [(), frozenset(), ((),), (frozenset(),), frozenset({()}), frozenset({frozenset()}), [()], {1}]
    while len(out) < n:
        out.append(value(0))
    return out


def test_the_type_tests_of_the_domains_are_the_tag_rule_on_a_large_invented_set():
    """The domain of a parameter is the tag rule (dslx.tag in dslx.ACC, and a Tuple is a tuple, a FrozenSet a
    frozenset). The validators test the type where that is the same thing; here the two forms are compared."""
    values = large_invented_set()
    assert {dslx.tag(v) for v in values} == set("B I T G TU TT GT O X OS XS Z FU E F U".split())
    assert sum(type(v) is tuple and not v for v in values) > 50 and sum(type(v) is frozenset and not v for v in values) > 50
    seen = {ann: [0, 0] for ann in B._DOMAIN}
    for v in values:
        tag = dslx.tag(v)
        for ann, check in B._DOMAIN.items():
            if ann == "Callable":
                rule = callable(v)
            else:
                rule = tag in B.acc_of(ann) and (ann != "Tuple" or type(v) is tuple) and (ann != "FrozenSet" or type(v) is frozenset)
            try:
                check(v)
                accepted = True
            except TypeError:
                accepted = False
            assert accepted == rule, (ann, v)
            seen[ann][accepted] += 1
    assert all(no > 100 and yes > 100 for no, yes in seen.values()), seen


@pytest.mark.parametrize("b", B.CATALOGUE, ids=lambda b: b.id)
def test_each_parameter_is_validated_on_every_call(b):
    """For every parameter in turn: a value outside its domain is refused whatever the other arguments are."""
    good = [FUNCTIONS[b.id][0] if ann == "Callable" else SAMPLES[ann][1] for _, ann in b.params]
    for i, (_, ann) in enumerate(b.params):
        for v in VALUES_OF_EVERY_TAG:
            inside = callable(v) if ann == "Callable" else dslx.tag(v) in B.acc_of(ann) and (
                ann not in ("Tuple", "FrozenSet") or type(v) is (tuple if ann == "Tuple" else frozenset))
            if inside:
                continue
            args = list(good)
            args[i] = v
            with pytest.raises(TypeError):
                b.fn(*args)


def test_an_integer_is_never_a_boolean_and_unknown_types_are_refused():
    for v in (True, False):
        with pytest.raises(TypeError):
            B._d_integer(v)
    B._d_integer(2 ** 50)                                              # the domain is the type; the bounds are for results
    for v in (None, "text", 1.5, [1], {1}, {1: 2}):
        assert dslx.tag(v) == "U"
        for ann in sorted(B._DOMAIN):
            if ann != "Callable":
                with pytest.raises(TypeError):
                    B._DOMAIN[ann](v)
    with pytest.raises(TypeError):
        B.c_concat(frozenset(), ())                                    # an empty frozenset is not a Tuple
    with pytest.raises(TypeError):
        B.c_union((), frozenset())
    with pytest.raises(TypeError):
        B.c_count(frozenset(), 1)
    with pytest.raises(TypeError):
        B.c_zip_star((1, 2))                                           # a pair of integers is not a container of containers
    with pytest.raises(TypeError):
        B.c_zip_star(((1, 2), 3))


# ---------------------------------------------------------------- every call is checked, whoever makes it
def test_every_call_is_checked_whoever_makes_it():
    full = dslx.library_namespace(())                                  # the seven retained operations, as the library has them
    compose, chain, fork, lbind, rbind, matcher, power = (full[n] for n in ("compose", "chain", "fork", "lbind", "rbind", "matcher", "power"))
    # a tree calls the block directly
    with pytest.raises(TypeError):
        B.c_add(True, 1)
    # through a call block
    assert B.c_call1(B.c_len, (1, 2)) == 2
    with pytest.raises(TypeError):
        B.c_call1(B.c_len, 5)
    with pytest.raises(TypeError):
        B.c_call2(B.c_add, True, 1)
    # through a comprehension block, a key and a predicate
    with pytest.raises(TypeError):
        B.c_map_tuple(B.c_abs, (1, True))
    with pytest.raises(TypeError):
        B.c_map_set(B.c_neg, (1, (2,)))
    with pytest.raises(TypeError):
        B.c_max_key((1, True), B.c_abs)
    with pytest.raises(TypeError):
        B.c_sorted_key((2, False), B.c_neg)
    with pytest.raises(TypeError):
        B.c_keep(B.c_not, (True, 1))
    assert B.c_keep(B.c_not, (True, False)) == (False,)
    # as a function-valued leaf through each retained operation
    assert compose(B.c_abs, B.c_len)((1, 2)) == 2 and rbind(B.c_add, 2)(3) == 5 and lbind(B.c_sub, 10)(3) == 7
    assert chain(B.c_neg, B.c_abs, B.c_len)((1, 2)) == -2 and fork(B.c_add, B.c_len, B.c_len)((1, 2)) == 4
    assert matcher(B.c_len, 2)((1, 2)) is True and power(B.c_neg, 3)(5) == -5
    for bad in (lambda: compose(B.c_abs, B.c_len)(5), lambda: lbind(B.c_add, True)(1), lambda: rbind(B.c_add, True)(1),
                lambda: chain(B.c_neg, B.c_abs, B.c_len)(3), lambda: fork(B.c_add, B.c_len, B.c_first)(((1,), 2)),
                lambda: matcher(B.c_len, 2)(7), lambda: power(B.c_not, 2)(1)):
        with pytest.raises(TypeError):
            bad()
    # by a function that came in as an input
    came_in = lambda v: B.c_add(v, True)                               # noqa: E731
    with pytest.raises(TypeError):
        came_in(1)
    with pytest.raises(TypeError):
        B.c_call1(came_in, 1)
    # a wrong number of arguments is an ordinary error
    with pytest.raises(TypeError):
        B.c_call1(B.c_call1, 1)
    with pytest.raises(TypeError):
        B.c_call2(B.c_len, (1,), (2,))
    with pytest.raises(TypeError):
        B.c_map_tuple(B.c_add, (1, 2))
    with pytest.raises(TypeError):
        B.c_max_key((1, 2), B.c_add)


def test_call_blocks_against_python_on_invented_functions():
    assert B.c_call1(double, 3) == (3, 3) and B.c_call1(tuple_length, ((1, 2), (3, 4))) == 2 and B.c_call1(is_big_int, 5) is True
    assert B.c_call2(plus, 3, 4) == 7 and B.c_call2(plus, (1,), (2,)) == (1, 2) and B.c_call2(pair, True, ()) == (True, ())
    for f in (3, (1,), None):
        with pytest.raises(TypeError):
            B.c_call1(f, 1)                                            # TypeError if f is not callable
        with pytest.raises(TypeError):
            B.c_call2(f, 1, 2)
    with pytest.raises(ZeroDivisionError):
        B.c_call1(boom, 1)
    with pytest.raises(TypeError):
        B.c_call1(itself, len)                                         # a function is not a value for a parameter typed Any
    with pytest.raises(ValueError):
        B.c_call1(lambda x: 2 ** 40, 1)                                # the bounds apply to the result
    with pytest.raises(ValueError):
        B.c_call2(lambda x, y: tuple(range(3001)), 1, 2)


# ---------------------------------------------------------------- no block returns a function or a value holding one
def test_check_value_rejects_a_function_at_any_depth():
    for v in (len, itself, B.c_len, (len,), ((1, (2, len)),), frozenset({len}), (1, frozenset({(2, itself)})), None, "t", 1.5,
              (1, None), ([1],), (1.5,)):
        with pytest.raises(TypeError):
            B.check_value(v)
    for v in (True, 0, -5, (), frozenset(), ((1, 2), (3, 4)), frozenset({(1, (2, 3))}), (True, (False,))):
        assert B.check_value(v) is v


def test_named_blocks_never_return_a_function_or_a_value_that_holds_one():
    holds = (len,)                                                     # a tuple that holds a function (tag TU: inside "Tuple")
    returns_function = lambda *a: len                                  # noqa: E731
    returns_holder = lambda *a: (1, (2, len))                          # noqa: E731
    attempts = [
        lambda: B.c_call1(returns_function, 1), lambda: B.c_call1(returns_holder, 1),
        lambda: B.c_call2(returns_function, 1, 2), lambda: B.c_call2(returns_holder, 1, 2),
        lambda: B.c_first(holds), lambda: B.c_first(frozenset({len})), lambda: B.c_first((holds,)),
        lambda: B.c_item0(holds), lambda: B.c_item1((1, len)), lambda: B.c_item((1, 2, holds), 2),
        lambda: B.c_if_else(True, holds, 1), lambda: B.c_if_else(False, 1, holds),
        lambda: B.c_max(holds), lambda: B.c_min(holds), lambda: B.c_max((holds,)), lambda: B.c_min((holds,)),
        lambda: B.c_max_default0(holds), lambda: B.c_min_default0((holds,)),
        lambda: B.c_max_key(holds, zero), lambda: B.c_min_key((holds,), zero),
        lambda: B.c_max_key_default0(holds, zero), lambda: B.c_min_key_default0((holds,), zero),
        lambda: B.c_max_key((1, 2), returns_function), lambda: B.c_sorted_key((1, 2), returns_holder),
        lambda: B.c_like((), holds), lambda: B.c_like(frozenset(), holds), lambda: B.c_like(holds, (1,)) and B.c_like((1,), holds),
        lambda: B.c_map_tuple(returns_function, (1, 2)), lambda: B.c_map_tuple(returns_holder, (1,)),
        lambda: B.c_map_set(returns_function, (1, 2)), lambda: B.c_map_set(returns_holder, (1,)),
        lambda: B.c_keep(lambda e: True, holds), lambda: B.c_keep(returns_function, (1, 2)),
        lambda: B.c_tuple(holds), lambda: B.c_frozenset(holds), lambda: B.c_enumerate(holds), lambda: B.c_zip(holds, (1,)),
        lambda: B.c_zip_star((holds, (1,))), lambda: B.c_pair(holds, 1), lambda: B.c_single(holds), lambda: B.c_set1(holds),
        lambda: B.c_reverse(holds), lambda: B.c_slice(holds, 0, 1), lambda: B.c_slice_to(holds, 1), lambda: B.c_slice_from(holds, 0),
        lambda: B.c_concat(holds, (1,)), lambda: B.c_pairs(holds, (1,)), lambda: B.c_sorted_key(holds, zero),
        lambda: B.c_union(frozenset({len}), frozenset({1})), lambda: B.c_set_difference(frozenset({len, 1}), frozenset({1})),
        lambda: B.c_intersection(frozenset({len, 1}), frozenset({len})),
    ]
    for i, attempt in enumerate(attempts):
        with pytest.raises(TypeError):
            attempt()
            raise AssertionError("attempt %d returned a value" % i)
    # blocks that only read a holder and return a plain value may do so; nothing they return holds a function
    assert B.c_len(holds) == 1 and B.c_is_tuple(holds) is True and B.c_count(holds, 3) == 0


@pytest.mark.parametrize("b", B.CATALOGUE, ids=lambda b: b.id)
def test_no_block_returns_a_value_that_holds_a_function(b):
    """Arguments that hold functions wherever a container is accepted, and functions that return functions: when
    the block returns at all, its value is a value of C at every depth."""
    holders = [(len,), ((len,), (1,)), frozenset({len}), (1, (2, (len,))), frozenset({(1, len)})]
    fns = [lambda *a: len, lambda *a: (len,), itself, zero, lambda *a: True]
    pools = []
    for _, ann in b.params:
        if ann == "Callable":
            pools.append(fns)
        elif ann in ("Integer", "Boolean", "Boolean|Integer"):
            pools.append(SAMPLES[ann][:2])
        else:
            pools.append([h for h in holders if dslx.tag(h) in B.acc_of(ann) and (ann != "Tuple" or type(h) is tuple)
                          and (ann != "FrozenSet" or type(h) is frozenset)] + SAMPLES[ann][:5])
    returned = 0
    for args in itertools.product(*pools):
        kind, got = outcome(b.fn, args)
        if kind == "ok":
            returned += 1
            assert not has_callable(got), (b.id, args)
            assert B.check_value(got) is got
    assert returned >= 1, b.id


def test_four_named_cases_of_validation():
    nested_function = (1, (2, frozenset({(3, len)})))
    with pytest.raises(TypeError):
        B.c_pair(nested_function, 1)                                   # c_pair with a nested function
    with pytest.raises(TypeError):
        B.c_pair(1, nested_function)
    with pytest.raises(TypeError):
        B.c_call1(lambda x: (x, (len,)), 1)                            # c_call1 returning a container that holds a function
    with pytest.raises(ValueError):
        B.c_map_tuple(lambda e: (e, (2 ** 40,)), (1, 2))               # c_map_tuple with an integer above 40 bits inside its output
    with pytest.raises(ValueError):
        B.c_map_tuple(lambda e: 2 ** 40, (1, 2))
    for key_block in (B.c_max_key, B.c_min_key, B.c_max_key_default0, B.c_min_key_default0, B.c_sorted_key):
        with pytest.raises(ValueError):
            key_block((1, 2), lambda e: tuple(range(3001)))            # a key result out of bounds
        with pytest.raises(ValueError):
            key_block((1, 2), lambda e: (e, 2 ** 40))
        with pytest.raises(ValueError):
            key_block((1, 2), lambda e: nested(9))
    # arguments are checked at the top level only: a block that does not return the nested part is not stopped by it
    assert B.c_len(nested_function) == 2 and B.c_is_tuple(nested_function) is True and B.c_item0(nested_function) == 1


# ---------------------------------------------------------------- bounds
def test_check_value_bounds_at_every_depth():
    lim = 2 ** 40
    for ok in (lim - 1, -(lim - 1), (lim - 1, (-(lim - 1),)), tuple(range(3000)), frozenset(range(3000)), (tuple(range(3000)),) * 3,
               nested(8), frozenset({nested(7)})):
        assert B.check_value(ok) is ok
    for bad in (lim, -lim, 2 ** 70, (1, lim), ((frozenset({-lim}),),), tuple(range(3001)), frozenset(range(3001)),
                (1, (2, tuple(range(3001)))), frozenset({tuple(range(3001))}), nested(9), frozenset({nested(8)}), (nested(9),)):
        with pytest.raises(ValueError):
            B.check_value(bad)


def test_result_bounds_of_blocks():
    lim = 2 ** 40
    assert B.c_add(lim - 2, 1) == lim - 1 and B.c_neg(lim - 1) == -(lim - 1) and B.c_mul(2 ** 20, 2 ** 19) == 2 ** 39
    for over in (lambda: B.c_add(lim - 1, 1), lambda: B.c_sub(-(lim - 1), 1), lambda: B.c_mul(2 ** 20, 2 ** 20), lambda: B.c_mul(-2 ** 39, 2),
                 lambda: B.c_sum((lim - 1, 1)), lambda: B.c_neg(lim), lambda: B.c_abs(-lim), lambda: B.c_max2(lim, 1),
                 lambda: B.c_first((lim,)), lambda: B.c_item0((lim, 1)), lambda: B.c_if_else(True, lim, 1), lambda: B.c_max((lim,)),
                 lambda: B.c_single(nested(8)), lambda: B.c_pair(nested(8), 1), lambda: B.c_set1(nested(8)),
                 lambda: B.c_union(frozenset(range(2000)), frozenset(range(2000, 4000))),
                 lambda: B.c_single((tuple(range(3001)),)), lambda: B.c_tuple((tuple(range(3001)),)),
                 lambda: B.c_frozenset(tuple(range(3001))), lambda: B.c_reverse(tuple(range(3001))),
                 lambda: B.c_slice_from(tuple(range(3002)), 1), lambda: B.c_like(frozenset(), tuple(range(3001)))):
        with pytest.raises(ValueError):
            over()
    assert len(B.c_union(frozenset(range(2000)), frozenset(range(1000, 3000)))) == 3000
    assert B.c_frozenset((1,) * 3001) == frozenset({1})                # the result is within the bounds: the argument is not validated
    assert B.c_len(tuple(range(5000))) == 5000 and B.c_slice_to(tuple(range(5000)), 3) == (0, 1, 2)
    assert B.c_mul(0, 2 ** 300) == 0 and B.c_mul(2 ** 300, 0) == 0     # a zero operand: the product is within the bounds


def test_predictable_sizes_are_checked_before_the_result_is_built():
    big = tuple(range(3000))
    t = time.process_time()
    for too_large in (lambda: B.c_range1(10 ** 12), lambda: B.c_range2(-10 ** 12, 10 ** 12), lambda: B.c_range3(0, 10 ** 30, 1),
                      lambda: B.c_range3(10 ** 30, 0, -3), lambda: B.c_range1(3001), lambda: B.c_range2(5, 3007),
                      lambda: B.c_pairs(big, big), lambda: B.c_pairs(tuple(range(61)), tuple(range(50))),
                      lambda: B.c_concat(big, (1,)), lambda: B.c_concat(tuple(range(2000)), tuple(range(1001))),
                      lambda: B.c_tuple(frozenset(range(3001))), lambda: B.c_enumerate(tuple(range(3001))),
                      lambda: B.c_zip(tuple(range(3001)), tuple(range(3001))), lambda: B.c_like((), frozenset(range(3001))),
                      lambda: B.c_zip_star((tuple(range(3001)), tuple(range(3001)))), lambda: B.c_zip_star(((1,),) * 3001),
                      lambda: B.c_mul(1 << 10 ** 6, 1 << 10 ** 6)):
        with pytest.raises(ValueError):
            too_large()
    assert time.process_time() - t < 5.0                               # nothing of 10**12 elements was ever built
    assert B.c_range1(3000) == big and B.c_range1(-5) == () and B.c_range2(7, 3) == () and len(B.c_pairs(tuple(range(60)), tuple(range(50)))) == 3000
    assert B.c_concat(tuple(range(2000)), tuple(range(1000)))[-1] == 999 and B.c_zip_star(((), tuple(range(5000)))) == ()
    calls = []

    def counted(e):
        calls.append(e)
        return e
    for f in (lambda: B.c_map_tuple(counted, tuple(range(3001))), lambda: B.c_sorted_key(tuple(range(3001)), counted)):
        with pytest.raises(ValueError):
            f()
    assert calls == []                                                 # the function value was never called


def test_values_returned_by_called_functions_are_validated_at_once():
    for bad_value, error in ((tuple(range(3001)), ValueError), (2 ** 40, ValueError), (nested(9), ValueError), (len, TypeError),
                             ((1, (len,)), TypeError), (None, TypeError)):
        calls = []

        def f(e, bad_value=bad_value, calls=calls):
            calls.append(e)
            return bad_value
        for use in (lambda: B.c_map_tuple(f, (1, 2, 3)), lambda: B.c_map_set(f, (1, 2, 3)), lambda: B.c_keep(f, (1, 2, 3)),
                    lambda: B.c_call1(f, 1), lambda: B.c_max_key((1, 2, 3), f), lambda: B.c_min_key((1, 2, 3), f),
                    lambda: B.c_max_key_default0((1, 2, 3), f), lambda: B.c_min_key_default0((1, 2, 3), f),
                    lambda: B.c_sorted_key((1, 2, 3), f), lambda: B.c_call2(lambda x, y: f(x), 1, 2)):
            del calls[:]
            with pytest.raises(error):
                use()
            assert calls == [1], "the first returned value must stop the block"


# ---------------------------------------------------------------- memory failures and iteration ends
def out_of_memory(*a):
    raise MemoryError()


def test_a_memory_failure_inside_a_block_is_a_resource_stop_not_an_ordinary_error():
    uses = [lambda: B.c_call1(out_of_memory, 1), lambda: B.c_call2(out_of_memory, 1, 2), lambda: B.c_map_tuple(out_of_memory, (1,)),
            lambda: B.c_map_set(out_of_memory, (1,)), lambda: B.c_keep(out_of_memory, (1,)), lambda: B.c_max_key((1, 2), out_of_memory),
            lambda: B.c_min_key((1, 2), out_of_memory), lambda: B.c_max_key_default0((1, 2), out_of_memory),
            lambda: B.c_min_key_default0((1, 2), out_of_memory), lambda: B.c_sorted_key((1, 2), out_of_memory),
            lambda: B.c_map_tuple(lambda e: B.c_call1(out_of_memory, e), (1,))]
    for use in uses:
        caught_as_ordinary = False
        try:
            try:
                use()
            except Exception:                                          # noqa: BLE001  (what the enumerator's own handler does)
                caught_as_ordinary = True
        except G.ResourceStop:
            pass
        else:
            raise AssertionError("no ResourceStop")
        assert not caught_as_ordinary
    assert not issubclass(G.ResourceStop, Exception) and not issubclass(G.GuardTimeout, Exception)


def test_an_iteration_end_inside_a_block_is_an_ordinary_error():
    def ends(*a):
        raise StopIteration()
    for use in (lambda: B.c_call1(ends, 1), lambda: B.c_keep(ends, (1, 2)), lambda: B.c_map_tuple(ends, (1, 2)),
                lambda: B.c_max_key((1, 2), ends)):
        with pytest.raises((ValueError, RuntimeError)):
            use()
    assert tuple(map(lambda e: B.c_abs(e), (1, -2))) == (1, 2)


# ---------------------------------------------------------------- a block never touches a deadline
def test_a_block_called_under_an_active_guard_does_not_touch_the_timer():
    before = signal.getsignal(signal.SIGVTALRM)
    with G.guard(50.0):
        handler = signal.getsignal(signal.SIGVTALRM)
        left = signal.getitimer(signal.ITIMER_VIRTUAL)[0]
        assert handler is G._on_timer and 0.0 < left <= 50.01 and G.active()      # the timer rounds up to its tick
        for b in B.CATALOGUE:
            for args in cases(b)[:40]:
                outcome(b.fn, args)
        with pytest.raises(G.ResourceStop):
            B.c_call1(out_of_memory, 1)
        assert signal.getsignal(signal.SIGVTALRM) is handler and G.active()
        now = signal.getitimer(signal.ITIMER_VIRTUAL)
        assert 0.0 < now[0] <= left and now[1] == 0.0                  # never reset, never disarmed
    assert signal.getitimer(signal.ITIMER_VIRTUAL) == (0.0, 0.0) and signal.getsignal(signal.SIGVTALRM) == before and not G.active()
    src = open(os.path.join(HERE, "blocks_c.py")).read()
    for word in ("import signal", "setitimer", "guard(", "import time", "witness_manifest"):
        assert word not in src


# ---------------------------------------------------------------- blocks depend on nothing but their arguments
def body_of(b):
    """The decorated body of a block, read from the closure of its checked function."""
    found = [c.cell_contents for c in b.fn.__closure__ if callable(c.cell_contents) and getattr(c.cell_contents, "__name__", "") == b.id]
    assert len(found) == 1
    return found[0]


def global_names(code, out=None):
    out = set() if out is None else out
    for ins in dis.get_instructions(code):
        if ins.opname in ("LOAD_GLOBAL", "LOAD_NAME", "STORE_GLOBAL", "DELETE_GLOBAL", "STORE_NAME"):
            out.add(ins.argval)
    for const in code.co_consts:
        if hasattr(const, "co_code"):
            global_names(const, out)
    return out


def test_blocks_depend_on_nothing_but_their_arguments():
    import builtins
    helpers = {"_size", "_validated", "check_value", "MAX_ELEMENTS", "MAX_INT_BITS"}
    library_names = set(LIB["lib_order"]) | set(LIB["const_names"])
    for b in B.CATALOGUE:
        body = body_of(b)
        assert body.__module__ == "blocks_c" and body.__closure__ is None and body.__defaults__ is None
        used = global_names(body.__code__)
        assert not any(op.opname.startswith(("STORE_GLOBAL", "DELETE_GLOBAL")) for op in dis.get_instructions(body.__code__))
        for name in used:
            assert name in helpers or hasattr(builtins, name), (b.id, name)
            assert name not in library_names, (b.id, name)
    for helper in (B.check_value, B._check_container, B._size, B._validated):
        for name in global_names(helper.__code__):
            assert name not in library_names and (hasattr(builtins, name) or name in vars(B)), name
    # the checked function closes over its body, its validators and its name, and nothing else
    for b in B.CATALOGUE:
        cells = [c.cell_contents for c in b.fn.__closure__]
        assert len(cells) == len(b.params) + 2 and b.id in cells and body_of(b) in cells
        assert sorted(id(c) for c in cells if c not in (b.id, body_of(b))) == sorted(id(B._DOMAIN[a]) for _, a in b.params)


# ---------------------------------------------------------------- the static check of a tree
def test_check_tree_counts_nodes_and_accepts_the_named_example():
    t = ("L", "c_call1", ("P", "x1"), ("L", "c_max_key_default0", ("P", "x0"), ("P", "x1")))
    assert B.check_tree(t, ["Container", "Callable"]) == 5 and B.check_tree(t, {"x0": "Container", "x1": "Callable"}) == 5
    as_json = ["L", "c_call1", ["P", "x1"], ["L", "c_max_key_default0", ["P", "x0"], ["P", "x1"]]]
    assert B.check_tree(as_json, ["Container", "Callable"]) == 5 and B.render(B.as_tree(as_json)) == "c_call1(x1, c_max_key_default0(x0, x1))"
    assert B.check_tree(("P", "x0"), ["Any"]) == 1 and B.check_tree(("L", "c_len", ("P", "x0")), ["Container"]) == 2
    assert B.check_tree(("L", "c_map_tuple", ("FN", "c_len"), ("P", "x0")), ["ContainerContainer"]) == 3
    with_retained = ("L", "c_min_key", ("L", "c_frozenset", ("P", "x0")), ("L", "lbind", ("FN", "c_count"), ("P", "x0")))
    assert B.check_tree(with_retained, ["Container"]) == 6
    assert B.check_tree(("L", "c_if_else", ("P", "x0"), ("P", "x1"), ("P", "x2")), ["Boolean", "Any", "Any"]) == 4
    assert B.check_tree(("L", "c_pair", ("C", "ZERO"), ("C", "EMPTY_SET")), []) == 3
    assert B.check_tree(("L", "c_concat", ("C", "EMPTY_TUPLE"), ("P", "x0")), ["Tuple"]) == 3
    assert B.check_tree(("L", "c_map_tuple", ("L", "compose", ("FN", "c_abs"), ("FN", "c_len")), ("P", "x0")), ["Container"]) == 5


def test_check_tree_refuses_with_a_reason():
    def refused(tree, anns, word):
        with pytest.raises(ValueError) as e:
            B.check_tree(tree, anns)
        assert word in str(e.value), str(e.value)
    refused(("L", "c_nothing", ("P", "x0")), ["Any"], "neither a block")
    refused(("L", "size", ("P", "x0")), ["Container"], "neither a block")              # a library operation is not in C
    refused(("L", "c_len", ("P", "x0"), ("P", "x0")), ["Container"], "takes 1 arguments")
    refused(("L", "c_add", ("P", "x0")), ["Integer"], "takes 2 arguments")
    refused(("L", "c_len", ("P", "x3")), ["Container"], "unknown parameter")
    refused(("L", "c_len", ("C", "NOPE")), [], "unknown constant")
    refused(("L", "c_map_tuple", ("FN", "c_call2"), ("P", "x0")), ["Container"], "not a function-valued leaf")
    refused(("L", "c_map_tuple", ("FN", "compose"), ("P", "x0")), ["Container"], "not a function-valued leaf")
    refused(("L", "c_map_tuple", ("FN", "size"), ("P", "x0")), ["Container"], "not a function-valued leaf")
    refused(("L", "c_add", ("P", "x0"), ("C", "ONE")), ["Container"], "cannot take")
    refused(("L", "c_len", ("C", "ONE")), [], "cannot take")
    refused(("L", "c_not", ("L", "c_len", ("P", "x0"))), ["Container"], "cannot take")
    refused(("L", "c_concat", ("L", "c_frozenset", ("P", "x0")), ("P", "x0")), ["Tuple"], "cannot take")
    refused(("L", "c_pair", ("FN", "c_len"), ("C", "ONE")), [], "cannot take")           # a function where a value is needed
    refused(("L", "c_map_tuple", ("P", "x0"), ("P", "x0")), ["Container"], "cannot take")  # a value where a function is needed
    refused(("X", "x0"), ["Any"], "unknown node kind")
    refused(("P",), ["Any"], "malformed")
    refused(("P", "x0", "x1"), ["Any", "Any"], "a leaf has")
    refused("c_len(x0)", ["Any"], "malformed")
    refused(("L", "c_len", ("P", "x0")), ["Containers"], "unknown annotation")
    assert B.check_tree(("L", "c_concat", ("C", "EMPTY_TUPLE"), ("C", "EMPTY_TUPLE")), []) == 3
    refused(("L", "c_add", ("C", "EMPTY_TUPLE"), ("C", "ONE")), [], "cannot take")
