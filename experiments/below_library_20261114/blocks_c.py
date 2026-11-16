"""The executable catalogue of C, the restricted language below the target operations (protocol section 3.2).
Author: Chimdi Walter Ndubuisi

C is NOT Python and is not claimed adequate for writing the library. It is eager, total on the examples in use,
immutable and without variables. This file is the frozen executable form of the protocol's table: one entry per
block, in the order of the table. Every block costs one node.

The values of C are Booleans, integers, tuples and frozensets, nested. A function is a value only as a leaf or as
the result of one of the seven retained library operations; it is accepted by a block only where a parameter is
typed Callable.

EVERY CALL IS CHECKED, WHOEVER MAKES IT. The function exported for a block (namespace(), ops(), the module
attribute of the same name) is the checked one; there is no unchecked form to call. Whether it is called by a
tree, as a function-valued leaf through a retained operation, by c_call1 or c_call2, by a comprehension block, as a
key or a predicate, or by a function that came in as an input, each call does, in this order:
  (a) validates every argument against the declared domain of its parameter: the runtime tag of the value
      (dslx.tag) must be among the accepted tags of the annotation (dslx.ACC); a parameter typed Callable needs
      callable(v); an Integer is a real int and never a Boolean; a value of unknown type (tag "U") is rejected; a
      Tuple must be a tuple and a FrozenSet a frozenset (the tag of an empty container alone does not tell).
      Where this rule is the same as a test of the value's type, the type is tested (see "domains" below);
  (b) checks the size of the result before building it, where that size follows from the arguments (a range,
      the pairs of two containers, a concatenation, a tuple of known length). Where only an upper bound of the
      size follows from the arguments (a union, a set made from a container, the elements kept by a condition),
      the result is built and then checked by step (d);
  (c) computes exactly what the Python form computes, in Python's own order of walking a container, with Python's
      ties for max and min and Python's errors inside the domain (a zero divisor, an index out of range, the
      maximum of an empty container, a missing element for c_index);
  (d) validates the result with check_value.
A wrong number of arguments or a value outside a domain is an ordinary error (TypeError or ValueError): the
expression does not exist in a search. That is the eager rule: every argument has been evaluated before the block
runs, c_if_else, c_and and c_or use both branches or operands, and c_keep applies its condition to every element.

check_value(v) accepts a value of C only: no function and nothing that is not a Boolean, an integer, a tuple or a
frozenset, at any depth (TypeError); no container with more than 3000 elements at any depth, no more than 8 levels
of nesting, no integer of more than 40 bits (ValueError). So no block of C returns a function or a value that
holds one. Every value returned by a function value that a block calls (c_call1, c_call2, c_map_tuple, c_map_set,
the condition of c_keep, the key of the max, min and sorted blocks) is validated by check_value at once, before
the block does anything else with it.

WHAT THE BOUNDS DO NOT COVER. A function value that a block calls is opaque: it may compute and allocate without
limit before it returns, and no check of this file can come before that. Such a call is bounded only from outside:
by the processor-time allowance and hard stop of the search, by the guard of a final check, and by the ceiling on
the memory of the process. Arguments are checked for their domain at the top level only.

Booleans and integers are distinct in every domain except c_int (a Boolean or an integer) and c_is_integer
(Python's isinstance(x, int), true of a Boolean). The condition of c_if_else, the operands of c_and, c_or and c_not
and every result of the condition of c_keep must be real Booleans; Python's truthiness is outside C. The one
departure from the Python form: c_first of an empty container raises ValueError where next(iter(c)) raises
StopIteration, and a StopIteration that leaves any block is turned into ValueError, because a StopIteration that
escapes into a caller's iteration would end that iteration silently.

A MemoryError anywhere inside a block is converted to guards_bl.ResourceStop, which is not an ordinary error. No
block touches a timer or a signal: a block called under an active guard leaves its deadline alone.
"""
import collections

import bl_frozen  # noqa: F401  (hash check, sys.path)
import dslx
import presets_bl as P
from guards_bl import ResourceStop

MAX_ELEMENTS = P.MAX_ELEMENTS      # 3000 elements of a container, at any depth
MAX_NESTING = P.MAX_NESTING        # 8 levels of nesting
MAX_INT_BITS = P.MAX_INT_BITS      # 40 bits
EMPTY_TUPLE = ()
EMPTY_SET = frozenset()
CONSTANTS = {"EMPTY_TUPLE": EMPTY_TUPLE, "EMPTY_SET": EMPTY_SET}

_INT_LIMIT = (1 << MAX_INT_BITS) - 1          # an integer of at most 40 bits lies in [-_INT_LIMIT, _INT_LIMIT]
_NOT_A_VALUE = "not a value of C (a Boolean, an integer, a tuple or a frozenset; never a function)"
_TOO_MANY = "a container of more than %d elements" % MAX_ELEMENTS
_TOO_DEEP = "more than %d levels of nesting" % MAX_NESTING
_TOO_LONG = "an integer of more than %d bits" % MAX_INT_BITS


# ---------------------------------------------------------------- validation of values
def check_value(v):
    """Return v when it is a value of C within the bounds at every depth; raise otherwise.

    TypeError: v is, or holds anywhere inside it, a function or anything else that is not a Boolean, an integer, a
    tuple or a frozenset. ValueError: a container of more than 3000 elements at any depth, more than 8 levels of
    nesting, or an integer of more than 40 bits."""
    t = type(v)
    if t is int:
        if v > _INT_LIMIT or v < -_INT_LIMIT:
            raise ValueError(_TOO_LONG)
    elif t is tuple or t is frozenset:
        _check_container(v, 1)
    elif t is not bool:
        raise TypeError(_NOT_A_VALUE)
    return v


def _check_container(c, level):
    if level > MAX_NESTING:
        raise ValueError(_TOO_DEEP)
    if len(c) > MAX_ELEMENTS:
        raise ValueError(_TOO_MANY)
    for e in c:
        t = type(e)
        if t is int:
            if e > _INT_LIMIT or e < -_INT_LIMIT:
                raise ValueError(_TOO_LONG)
        elif t is tuple or t is frozenset:
            _check_container(e, level + 1)
        elif t is not bool:
            raise TypeError(_NOT_A_VALUE)


def _size(n):
    """Check, before a result is built, a size that follows from the arguments."""
    if n > MAX_ELEMENTS:
        raise ValueError("the result would have more than %d elements" % MAX_ELEMENTS)
    return n


def _validated(f):
    """The function value f, with every value it returns validated at once (used for keys)."""
    def call(e):
        return check_value(f(e))
    return call


# ---------------------------------------------------------------- domains of parameters (top level)
# The domain of a parameter is its annotation's set of accepted runtime tags (dslx.tag in dslx.ACC), with the two
# additions named in the module's text: a Tuple must be a tuple and a FrozenSet a frozenset. For every annotation
# but ContainerContainer that rule is the same as a test of the value's type, and the type is what is tested here
# (a test compares the two forms on a large invented set of values):
#   Integer            tag I                    <=>  type is int (never bool)
#   Boolean            tag B                    <=>  type is bool
#   Container          a container tag          <=>  type is tuple or frozenset
#   Tuple, FrozenSet   a tag of that kind       <=>  type is tuple, type is frozenset
#   Any                every tag but F and U    <=>  type is bool, int, tuple or frozenset
# ContainerContainer leaves out the tags of a pair of integers and of a set of integers: it keeps the tag.
def acc_of(annotation):
    """The accepted runtime tags (dslx.ACC) of an annotation; 'A|B' is the union of A and B."""
    out = frozenset()
    for part in annotation.split("|"):
        out = out | dslx.ACC[part]
    return out


_tag = dslx.tag
_ACC_CONTAINER_CONTAINER = acc_of("ContainerContainer")


def _d_integer(v):
    if type(v) is not int:
        raise TypeError("an Integer is needed (a real int, never a Boolean)")


def _d_boolean(v):
    if type(v) is not bool:
        raise TypeError("a Boolean is needed")


def _d_boolean_or_integer(v):
    t = type(v)
    if t is not int and t is not bool:
        raise TypeError("a Boolean or an Integer is needed")


def _d_container(v):
    t = type(v)
    if t is not tuple and t is not frozenset:
        raise TypeError("a Container (a tuple or a frozenset) is needed")


def _d_container_container(v):
    if _tag(v) not in _ACC_CONTAINER_CONTAINER:
        raise TypeError("a container of containers is needed")


def _d_tuple(v):
    if type(v) is not tuple:
        raise TypeError("a Tuple is needed")


def _d_frozenset(v):
    if type(v) is not frozenset:
        raise TypeError("a FrozenSet is needed")


def _d_any(v):
    t = type(v)
    if t is not int and t is not tuple and t is not frozenset and t is not bool:
        raise TypeError("a value of C is needed here (a function is accepted only where a function is asked for)")


def _d_callable(v):
    if not callable(v):
        raise TypeError("a function is needed")


_DOMAIN = {"Integer": _d_integer, "Boolean": _d_boolean, "Boolean|Integer": _d_boolean_or_integer,
           "Container": _d_container, "ContainerContainer": _d_container_container, "Tuple": _d_tuple,
           "FrozenSet": _d_frozenset, "Any": _d_any, "Callable": _d_callable}


# ---------------------------------------------------------------- the checked function of a block, by arity
def _checked1(body, name, d0):
    def block(a):
        try:
            d0(a)
            return check_value(body(a))
        except MemoryError:
            raise ResourceStop("memory failure inside block " + name) from None
        except StopIteration:
            raise ValueError(name + ": an iteration ended inside the block") from None
    block.__name__ = block.__qualname__ = name
    return block


def _checked2(body, name, d0, d1):
    def block(a, b):
        try:
            d0(a)
            d1(b)
            return check_value(body(a, b))
        except MemoryError:
            raise ResourceStop("memory failure inside block " + name) from None
        except StopIteration:
            raise ValueError(name + ": an iteration ended inside the block") from None
    block.__name__ = block.__qualname__ = name
    return block


def _checked3(body, name, d0, d1, d2):
    def block(a, b, c):
        try:
            d0(a)
            d1(b)
            d2(c)
            return check_value(body(a, b, c))
        except MemoryError:
            raise ResourceStop("memory failure inside block " + name) from None
        except StopIteration:
            raise ValueError(name + ": an iteration ended inside the block") from None
    block.__name__ = block.__qualname__ = name
    return block


_CHECKED = {1: _checked1, 2: _checked2, 3: _checked3}
Block = collections.namedtuple("Block", "id python params result nodes fn_leaf fn")
_ENTRIES = []


def _block(python, result, **annotations):
    """Declare a block: its Python form, the annotation of its result and of each parameter (in order; a key of
    dslx.ACC, or several joined by '|'). The decorated body holds steps (b) and (c) only; the name of the block is
    bound to the checked function, which adds steps (a) and (d) and the conversion of a memory failure. A block is
    offered as a function-valued leaf when it has one or two parameters and its result is not a function."""
    def register(body):
        name = body.__name__
        params = tuple(annotations.items())
        code = body.__code__
        if code.co_varnames[:code.co_argcount] != tuple(annotations) or code.co_flags & 0x0C:
            raise AssertionError("block %s: the annotations do not match its parameters" % name)
        acc_of(result)
        fn = _CHECKED[len(params)](body, name, *[_DOMAIN[a] for _, a in params])
        _ENTRIES.append(Block(id=name, python=python, params=params, result=result, nodes=1,
                              fn_leaf=len(params) in (1, 2) and result != "Callable", fn=fn))
        return fn
    return register


# ---------------------------------------------------------------- the blocks, in the order of the protocol's table
@_block("len(c)", "Integer", c="Container")
def c_len(c):
    return len(c)


@_block("abs(a)", "Integer", a="Integer")
def c_abs(a):
    return abs(a)


@_block("tuple(c)", "Tuple", c="Container")
def c_tuple(c):
    _size(len(c))
    return tuple(c)


@_block("frozenset(c)", "FrozenSet", c="Container")
def c_frozenset(c):
    return frozenset(c)


@_block("tuple(enumerate(c))", "Tuple", c="Container")
def c_enumerate(c):
    _size(len(c))
    return tuple(enumerate(c))


@_block("tuple(zip(a, b))", "Tuple", a="Container", b="Container")
def c_zip(a, b):
    _size(min(len(a), len(b)))
    return tuple(zip(a, b))


@_block("tuple(zip(*c))", "Tuple", c="ContainerContainer")
def c_zip_star(c):
    shortest = None
    for e in c:
        t = type(e)
        if t is not tuple and t is not frozenset:
            raise TypeError("c_zip_star needs a container of containers")
        if shortest is None or len(e) < shortest:
            shortest = len(e)
    if shortest:
        _size(shortest)
        _size(len(c))
    return tuple(zip(*c))


@_block("tuple(range(a))", "Tuple", a="Integer")
def c_range1(a):
    _size(a)
    return tuple(range(a))


@_block("tuple(range(a, b))", "Tuple", a="Integer", b="Integer")
def c_range2(a, b):
    _size(b - a)
    return tuple(range(a, b))


@_block("tuple(range(a, b, step))", "Tuple", a="Integer", b="Integer", step="Integer")
def c_range3(a, b, step):
    if step == 0:
        raise ValueError("c_range3: the step is zero")
    try:
        n = len(range(a, b, step))
    except OverflowError:
        raise ValueError("the result would have more than %d elements" % MAX_ELEMENTS) from None
    _size(n)
    return tuple(range(a, b, step))


@_block("int(x)", "Integer", x="Boolean|Integer")
def c_int(x):
    return int(x)


@_block("next(iter(c))", "Any", c="Container")
def c_first(c):
    for e in c:
        return e
    raise ValueError("c_first: the container is empty")


@_block("max(c)", "Any", c="Container")
def c_max(c):
    return max(c)


@_block("min(c)", "Any", c="Container")
def c_min(c):
    return min(c)


@_block("max(c, default=0)", "Any", c="Container")
def c_max_default0(c):
    return max(c, default=0)


@_block("min(c, default=0)", "Any", c="Container")
def c_min_default0(c):
    return min(c, default=0)


@_block("max(c, key=f)", "Any", c="Container", f="Callable")
def c_max_key(c, f):
    return max(c, key=_validated(f))


@_block("min(c, key=f)", "Any", c="Container", f="Callable")
def c_min_key(c, f):
    return min(c, key=_validated(f))


@_block("max(c, key=f, default=0)", "Any", c="Container", f="Callable")
def c_max_key_default0(c, f):
    return max(c, key=_validated(f), default=0)


@_block("min(c, key=f, default=0)", "Any", c="Container", f="Callable")
def c_min_key_default0(c, f):
    return min(c, key=_validated(f), default=0)


@_block("max(a, b)", "Integer", a="Integer", b="Integer")
def c_max2(a, b):
    return max(a, b)


@_block("min(a, b)", "Integer", a="Integer", b="Integer")
def c_min2(a, b):
    return min(a, b)


@_block("tuple(sorted(c, key=f))", "Tuple", c="Container", f="Callable")
def c_sorted_key(c, f):
    _size(len(c))
    return tuple(sorted(c, key=_validated(f)))


@_block("sum(c)", "Integer", c="Container")
def c_sum(c):
    r = sum(c)
    if type(r) is not int:
        raise TypeError("c_sum: the sum is not an Integer")
    return r


@_block("isinstance(x, int)", "Boolean", x="Any")
def c_is_integer(x):
    return isinstance(x, int)


@_block("isinstance(x, tuple)", "Boolean", x="Any")
def c_is_tuple(x):
    return isinstance(x, tuple)


@_block("type(c)(items)", "Container", c="Container", items="Container")
def c_like(c, items):
    if type(c) is tuple:
        _size(len(items))
        return tuple(items)
    if type(c) is frozenset:
        return frozenset(items)
    raise TypeError("c_like needs a tuple or a frozenset to take the type from")


@_block("a + b", "Integer", a="Integer", b="Integer")
def c_add(a, b):
    return a + b


@_block("a - b", "Integer", a="Integer", b="Integer")
def c_sub(a, b):
    return a - b


@_block("a * b", "Integer", a="Integer", b="Integer")
def c_mul(a, b):
    # the product of two integers that are not zero has at least bits(a) + bits(b) - 1 bits
    if a and b and a.bit_length() + b.bit_length() - 1 > MAX_INT_BITS:
        raise ValueError("the product would have more than %d bits" % MAX_INT_BITS)
    return a * b


@_block("a // b", "Integer", a="Integer", b="Integer")
def c_floordiv(a, b):
    return a // b


@_block("a % b", "Integer", a="Integer", b="Integer")
def c_mod(a, b):
    return a % b


@_block("-a", "Integer", a="Integer")
def c_neg(a):
    return -a


@_block("a + b", "Tuple", a="Tuple", b="Tuple")
def c_concat(a, b):
    _size(len(a) + len(b))
    return a + b


@_block("a - b", "FrozenSet", a="FrozenSet", b="FrozenSet")
def c_set_difference(a, b):
    return a - b


@_block("a | b", "FrozenSet", a="FrozenSet", b="FrozenSet")
def c_union(a, b):
    return a | b


@_block("a & b", "FrozenSet", a="FrozenSet", b="FrozenSet")
def c_intersection(a, b):
    return a & b


@_block("a == b", "Boolean", a="Any", b="Any")
def c_eq(a, b):
    return a == b


@_block("a != b", "Boolean", a="Any", b="Any")
def c_ne(a, b):
    return a != b


@_block("a < b", "Boolean", a="Integer", b="Integer")
def c_lt(a, b):
    return a < b


@_block("a <= b", "Boolean", a="Integer", b="Integer")
def c_le(a, b):
    return a <= b


@_block("a > b", "Boolean", a="Integer", b="Integer")
def c_gt(a, b):
    return a > b


@_block("a >= b", "Boolean", a="Integer", b="Integer")
def c_ge(a, b):
    return a >= b


@_block("x in c", "Boolean", x="Any", c="Container")
def c_in(x, c):
    return x in c


@_block("x not in c", "Boolean", x="Any", c="Container")
def c_not_in(x, c):
    return x not in c


@_block("a and b", "Boolean", a="Boolean", b="Boolean")
def c_and(a, b):
    return a and b


@_block("a or b", "Boolean", a="Boolean", b="Boolean")
def c_or(a, b):
    return a or b


@_block("not a", "Boolean", a="Boolean")
def c_not(a):
    return not a


@_block("(a, b)", "Tuple", a="Any", b="Any")
def c_pair(a, b):
    return (a, b)


@_block("(a,)", "Tuple", a="Any")
def c_single(a):
    return (a,)


@_block("frozenset({a})", "FrozenSet", a="Any")
def c_set1(a):
    return frozenset((a,))


@_block("x[0]", "Any", x="Tuple")
def c_item0(x):
    return x[0]


@_block("x[1]", "Any", x="Tuple")
def c_item1(x):
    return x[1]


@_block("x[i]", "Any", x="Tuple", i="Integer")
def c_item(x, i):
    return x[i]


@_block("x[::-1]", "Tuple", x="Tuple")
def c_reverse(x):
    return x[::-1]


@_block("x[a:b]", "Tuple", x="Tuple", a="Integer", b="Integer")
def c_slice(x, a, b):
    return x[a:b]


@_block("x[:b]", "Tuple", x="Tuple", b="Integer")
def c_slice_to(x, b):
    return x[:b]


@_block("x[a:]", "Tuple", x="Tuple", a="Integer")
def c_slice_from(x, a):
    return x[a:]


@_block("a if c else b", "Any", c="Boolean", a="Any", b="Any")
def c_if_else(c, a, b):
    return a if c else b


@_block("f(x)", "Any", f="Callable", x="Any")
def c_call1(f, x):
    return check_value(f(x))


@_block("f(x, y)", "Any", f="Callable", x="Any", y="Any")
def c_call2(f, x, y):
    return check_value(f(x, y))


@_block("tuple(f(e) for e in c)", "Tuple", f="Callable", c="Container")
def c_map_tuple(f, c):
    _size(len(c))
    return tuple(check_value(f(e)) for e in c)


@_block("frozenset(f(e) for e in c)", "FrozenSet", f="Callable", c="Container")
def c_map_set(f, c):
    return frozenset(check_value(f(e)) for e in c)


@_block("tuple(e for e in c if p(e))", "Tuple", p="Callable", c="Container")
def c_keep(p, c):
    out = []
    for e in c:
        k = check_value(p(e))
        if type(k) is not bool:
            raise TypeError("c_keep: the condition must give a Boolean for every element")
        if k:
            out.append(e)
    return tuple(out)


@_block("tuple((i, j) for i in a for j in b)", "Tuple", a="Container", b="Container")
def c_pairs(a, b):
    _size(len(a) * len(b))
    return tuple((i, j) for i in a for j in b)


@_block("a.issubset(b)", "Boolean", a="FrozenSet", b="FrozenSet")
def c_issubset(a, b):
    return a.issubset(b)


@_block("c.count(x)", "Integer", c="Tuple", x="Any")
def c_count(c, x):
    return c.count(x)


@_block("c.index(x)", "Integer", c="Tuple", x="Any")
def c_index(c, x):
    return c.index(x)


# ---------------------------------------------------------------- the catalogue
CATALOGUE = tuple(_ENTRIES)
BY_ID = {b.id: b for b in CATALOGUE}
if len(BY_ID) != len(CATALOGUE):
    raise AssertionError("a block id is repeated in the catalogue")


def namespace():
    """{block id: checked function} (a new dict at every call)."""
    return {b.id: b.fn for b in CATALOGUE}


def ops():
    """The blocks in catalogue order, in the enumerator's format: (name, function, accepted tag sets, makes_fn).
    No block of C makes a function, so makes_fn is False for every one."""
    return [(b.id, b.fn, tuple(acc_of(a) for _, a in b.params), False) for b in CATALOGUE]


def function_leaf_names():
    """The ids of the blocks offered as function-valued leaves, in catalogue order."""
    return [b.id for b in CATALOGUE if b.fn_leaf]


# ---------------------------------------------------------------- static check of an expression tree over C
def _as_tree(t):
    """A tree given as nested lists (JSON) or tuples, as nested tuples."""
    if not isinstance(t, (list, tuple)) or len(t) < 2 or not isinstance(t[0], str) or not isinstance(t[1], str):
        raise ValueError("malformed tree node: %r" % (t,))
    if t[0] == "L":
        return ("L", t[1]) + tuple(_as_tree(c) for c in t[2:])
    if len(t) != 2:
        raise ValueError("a leaf has a kind and a name only: %r" % (t,))
    return (t[0], t[1])


def as_tree(t):
    """Public form of the conversion: nested lists (JSON) or tuples to nested tuples; ValueError when malformed."""
    return _as_tree(t)


def render(t):
    """Text of a tree (the same form the enumerator prints)."""
    if t[0] == "L":
        return t[1] + "(" + ", ".join(render(c) for c in t[2:]) + ")"
    return t[1]


def _overlap(possible, accepted):
    """Best-effort compatibility of a child's possible tags with a parameter's accepted tags. The tag of an empty
    container belongs to every container domain, so it decides only when it is all the child can be."""
    both = possible & accepted
    if possible == frozenset(["E"]):
        return bool(both)
    return bool(both - frozenset(["E"]))


def check_tree(tree, param_annotations):
    """Static check of an expression tree over C and the seven retained library operations. Nothing is run.

    tree: ("P", "x0") a parameter by its neutral name, ("C", name) one of the 28 named constants or EMPTY_TUPLE or
    EMPTY_SET, ("FN", id) a block of C offered as a function-valued leaf, ("L", name, child, ...) a block of C or
    one of the seven retained operations applied to children. Nested lists (JSON) are accepted.
    param_annotations: the annotations of the target's parameters, by position (a list) or by neutral name (a dict).

    Checks: every name exists, every application has the arity of its block, and, as far as annotations can tell,
    every child can lie in the domain of its parameter (a best-effort check: an annotation such as Any says little).
    Returns the number of nodes; raises ValueError with the reason otherwise."""
    lib = dslx.load()
    if isinstance(param_annotations, dict):
        anns = dict(param_annotations)
    else:
        anns = {"x%d" % i: a for i, a in enumerate(param_annotations)}
    for name, ann in anns.items():
        try:
            acc_of(ann)
        except (KeyError, AttributeError):
            raise ValueError("unknown annotation %r of parameter %s" % (ann, name)) from None
    leaf_names = set(function_leaf_names())

    def visit(t):
        """(number of nodes, possible tags of the value)."""
        kind, name = t[0], t[1]
        if kind == "P":
            if name not in anns:
                raise ValueError("unknown parameter %s" % name)
            return 1, acc_of(anns[name])
        if kind == "C":
            if name in CONSTANTS:
                return 1, frozenset([dslx.tag(CONSTANTS[name])])
            if name in lib["consts"]:
                return 1, frozenset([dslx.tag(lib["consts"][name])])
            raise ValueError("unknown constant %s" % name)
        if kind == "FN":
            if name not in leaf_names:
                raise ValueError("%s is not a function-valued leaf of C" % name)
            return 1, dslx.ACC["Callable"]
        if kind != "L":
            raise ValueError("unknown node kind %r" % kind)
        if name in BY_ID:
            params, result = BY_ID[name].params, BY_ID[name].result
        elif name in P.RETAINED:
            params, result = tuple(lib["sigs"][name]), lib["rets"][name]
        else:
            raise ValueError("%s is neither a block of C nor one of the seven retained operations" % name)
        kids = t[2:]
        if len(kids) != len(params):
            raise ValueError("%s takes %d arguments, %d given" % (name, len(params), len(kids)))
        nodes = 1
        for (pname, ann), kid in zip(params, kids):
            n, possible = visit(kid)
            nodes += n
            if not _overlap(possible, acc_of(ann)):
                raise ValueError("argument %s of %s (%s) cannot take %s" % (pname, name, ann, render(kid)))
        return nodes, acc_of(result)

    return visit(_as_tree(tree))[0]
