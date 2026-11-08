"""Tree interpreter of the grid-function language (gridfn-1).

`Machine(checked)` turns the checked, normalized syntax tree (lang.check) into closures of this module's own code,
once; `Machine.run(grid)` then executes `transform(grid)` with fresh state and returns the validated output grid,
or raises a typed error. No Python code is generated, compiled or executed from the program text: every node kind
of the subset has an implementation here, and anything else was rejected by the check.

Semantics follow Python for the subset (values are ints, floats, bools, None, short strings, lists, tuples, dicts,
sets and generators; functions are the program's own, the safe builtins and the primitives), with these bounds:
- a step counter: every statement charges its static size in nodes, every loop iteration, comprehension element
  and call charges, and so do container copies and primitive work (by the cells they touch); more than max_steps
  steps raises StepLimit (deterministic: the same program on the same grid takes the same steps);
- a call-depth limit (max_depth user calls, 1000 as in Python), a container-size limit (max_seq elements per list, tuple, set or
  dict built), an integer-size limit (|x| <= 2**63), string arithmetic refused;
- only whitelisted container methods (lang.METHODS) on exact list, dict, set and tuple values;
- output validation: a rectangular list (or tuple) of 1..30 rows of 1..30 ints in 0..9.
Errors: StepLimit, Timeout (raised by the worker's CPU timer), Fault (RuntimeFault: any runtime failure, with the
line), ShapeError and ValueError (bad output). The worker (worker.py) runs machines inside a resource-limited
process; `Machine` alone is not a sandbox for hostile CPU or memory use beyond these bounds.
"""
import ast
import sys
import types

from . import lang as L
from . import prims as P

MAX_OUT = 30


class StepLimit(BaseException):
    """More steps than the limit (BaseException: no handler in the interpreter can swallow it)."""


class Timeout(BaseException):
    """CPU time limit (raised by the worker's timer signal)."""


class Fault(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message, self.line = message, line


class OutputError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind, self.message = kind, message


from . import npx as NPX                                   # noqa: E402 (gridfn-2 numpy subset)
_ND = NPX.ND
NPX.NPFault = Fault                                        # numpy-subset errors are the interpreter's typed faults


class Limits:
    __slots__ = ("max_steps", "max_depth", "max_seq", "max_int")

    def __init__(self, max_steps=4_000_000, max_depth=1000, max_seq=100_000, max_int=2 ** 63):
        self.max_steps, self.max_depth, self.max_seq, self.max_int = max_steps, max_depth, max_seq, max_int

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


class State:
    __slots__ = ("steps", "max_steps", "depth", "max_depth", "max_seq", "max_int", "line", "globals", "defaults")

    def __init__(self, limits):
        self.max_steps, self.max_depth = limits.max_steps, limits.max_depth
        self.max_seq, self.max_int = limits.max_seq, limits.max_int
        self.reset()

    def reset(self):
        self.steps, self.depth, self.line, self.globals = 0, 0, None, {}
        self.defaults = {}                     # gridfn-2 defaultdict factories: id(dict) -> (dict, factory)

    def charge(self, n):
        self.steps += n
        if self.steps > self.max_steps:
            raise StepLimit()


class Frame:
    __slots__ = ("vars", "parent")

    def __init__(self, parent):
        self.vars, self.parent = {}, parent


class Ret:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


BREAK, CONTINUE = object(), object()
GEN = types.GeneratorType
ITERABLE = frozenset((list, tuple, range, str, dict, set, GEN))
SIZED = frozenset((list, tuple, range, str, dict, set))
NUMBERS = frozenset((int, float, bool))


def a_(x):
    """'a list', 'an int', ... for messages."""
    n = tname(x)
    return ("an " if n[0] in "aeiou" else "a ") + n


def tname(x):
    t = type(x)
    if t in (UserFunction, Builtin, Primitive):
        return "function"
    return {list: "list", tuple: "tuple", int: "int", bool: "bool", float: "float", str: "string", dict: "dict",
            set: "set", range: "range", type(None): "None", GEN: "generator"}.get(t, "value")


# ------------------------------------------------------------------ callables
class UserFunction:
    __slots__ = ("name", "params", "defaults", "body", "closure", "st")

    def __init__(self, name, params, defaults, body, closure, st):
        self.name, self.params, self.defaults, self.body, self.closure, self.st = \
            name, params, defaults, body, closure, st

    def invoke(self, args, kw):
        st = self.st
        st.depth += 1
        try:
            if st.depth > st.max_depth:
                raise Fault(f"calls nested deeper than {st.max_depth} (unbounded recursion?)")
            params = self.params
            if len(args) > len(params):
                raise Fault(f"{self.name}() takes {len(params)} arguments but {len(args)} were given")
            fr = Frame(self.closure)
            v = fr.vars
            for name, val in zip(params, args):
                v[name] = val
            for k, val in kw.items():
                if k not in params:
                    raise Fault(f"{self.name}() has no parameter {k}")
                if k in v:
                    raise Fault(f"{self.name}() got two values for {k}")
                v[k] = val
            if len(v) < len(params):
                for name in params:
                    if name not in v:
                        if name not in self.defaults:
                            raise Fault(f"{self.name}() is missing the argument {name}")
                        v[name] = self.defaults[name]
            st.steps += 1 + len(params)
            r = self.body(fr)
            return r.value if type(r) is Ret else None
        finally:
            st.depth -= 1


class Builtin:
    __slots__ = ("name", "fn")

    def __init__(self, name, fn):
        self.name, self.fn = name, fn


class Primitive:
    __slots__ = ("name", "fn", "weight", "cost")

    def __init__(self, name, fn, weight, cost=None):
        self.name, self.fn, self.weight, self.cost = name, fn, weight, cost

    def invoke(self, st, args, kw):
        n = 0
        for a in args:
            n += _size(a)
        for a in kw.values():
            n += _size(a)
        extra = 0
        if self.cost is not None:
            try:
                extra = int(self.cost(args, kw))
            except Exception:                              # noqa: BLE001 (bad arguments: the primitive reports them)
                extra = 0
        st.charge(P.BASE_STEPS + (self.weight * n) // 4 + extra)
        try:
            r = self.fn(*args, **kw)
        except P.PrimError as e:
            raise Fault(f"{self.name}(): {e}") from None
        except TypeError as e:
            raise Fault(f"{self.name}(): {_type_msg(e)}") from None
        except RecursionError:
            raise Fault(f"{self.name}(): value nested too deeply") from None
        st.charge((self.weight * _size(r)) // 4)
        return r


def _type_msg(e):
    msg = str(e)
    for prefix in ("_grid() ", "_cells() "):
        msg = msg.replace(prefix, "")
    return msg[:200]


def _size(x):
    t = type(x)
    if t is list or t is tuple:
        n = len(x)
        if n:
            f = x[0]
            if type(f) is list or type(f) is tuple:
                return n * (len(f) or 1)
        return n
    if t is dict or t is set:
        return len(x)
    return 1


def call(st, f, args, kw):
    t = type(f)
    if t is UserFunction:
        return f.invoke(args, kw)
    if t is Primitive:
        return f.invoke(st, args, kw)
    if t is Builtin:
        st.steps += 1
        return f.fn(st, args, kw)
    if t is NPX.NPFunction:
        return f.invoke(st, args, kw)
    if t is BoundMethod:
        st.steps += 1
        return METHODS[(type(f.recv), f.name)](st, f.recv, args, kw)
    raise Fault(f"{a_(f)} is not a function")


class BoundMethod:
    """A container method used as a value (gridfn-2), for example key=counts.get."""
    __slots__ = ("recv", "name")

    def __init__(self, recv, name):
        self.recv, self.name = recv, name


# ------------------------------------------------------------------ value helpers
def _check_len(st, n):
    if n > st.max_seq:
        raise Fault(f"a list of {n} elements is larger than the limit ({st.max_seq})")


def materialize(st, x):
    """A new list of the elements of an iterable value, charged per element."""
    t = type(x)
    if t is list or t is tuple or t is str or t is set or t is dict:
        st.charge(len(x) // 4 + 1)
        return list(x)
    if t is range:
        n = len(x)
        _check_len(st, n)
        st.charge(n // 4 + 1)
        return list(x)
    if t is _ND:
        return NPX.rows(st, x)
    if t is GEN:
        out = []
        for v in x:
            st.steps += 1
            if st.steps > st.max_steps:
                raise StepLimit()
            out.append(v)
            if len(out) > st.max_seq:
                _check_len(st, len(out))
        return out
    raise Fault(f"{a_(x)} is not iterable")


def iterable(x):
    if type(x) in ITERABLE:
        return x
    if type(x) is _ND:
        if x.ndim == 0:
            raise Fault("a 0-d array is not iterable")
        return [NPX.to_py(v) for v in x] if x.ndim == 1 else [x[k] for k in range(x.shape[0])]
    raise Fault(f"{a_(x)} is not iterable")


def _int_ok(st, v):
    if -st.max_int <= v <= st.max_int:
        return v
    raise Fault("integer result too large")


def binop(st, op, a, b):
    ta, tb = type(a), type(b)
    if ta is _ND or tb is _ND:
        return NPX.binop(st, op, a, b)
    if ta in NUMBERS and tb in NUMBERS:
        if op is ast.Pow:
            if ta is not float and tb is not float and b > 64 and abs(a) > 1:
                raise Fault("integer result too large")
            if (ta is float or tb is float) and abs(b) > 4096:
                raise Fault("power too large")
            r = a ** b
        elif op is ast.LShift:
            if tb is float or ta is float:
                raise Fault("<< needs ints")
            if b > 64:
                raise Fault("integer result too large")
            r = a << b
        else:
            r = _NUM_OPS[op](a, b)
        if type(r) is int:
            return _int_ok(st, r)
        if type(r) is complex:
            raise Fault("complex numbers are not supported")
        return r
    if op is ast.Add:
        if (ta is list and tb is list) or (ta is tuple and tb is tuple):
            _check_len(st, len(a) + len(b))
            st.charge((len(a) + len(b)) // 4 + 1)
            return a + b
    elif op is ast.Mult:
        if ta in (list, tuple) and tb in (int, bool):
            seq, k = a, b
        elif tb in (list, tuple) and ta in (int, bool):
            seq, k = b, a
        else:
            seq = None
        if seq is not None:
            n = len(seq) * max(int(k), 0)
            _check_len(st, n)
            st.charge(n // 4 + 1)
            return seq * k
    elif ta is set and tb is set and op in _SET_OPS:
        st.charge((len(a) + len(b)) // 4 + 1)
        return _SET_OPS[op](a, b)
    elif ta is dict and tb is dict and op is ast.BitOr:
        _check_len(st, len(a) + len(b))
        st.charge((len(a) + len(b)) // 4 + 1)
        return {**a, **b}
    if ta is str or tb is str:
        raise Fault("strings support only == and != and in")
    raise Fault(f"unsupported operand types for {_OP_SYM.get(op, '?')}: {tname(a)} and {tname(b)}")


_NUM_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b, ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
            ast.RShift: lambda a, b: a >> b, ast.BitOr: lambda a, b: a | b, ast.BitXor: lambda a, b: a ^ b,
            ast.BitAnd: lambda a, b: a & b}
_SET_OPS = {ast.BitOr: lambda a, b: a | b, ast.BitAnd: lambda a, b: a & b, ast.Sub: lambda a, b: a - b,
            ast.BitXor: lambda a, b: a ^ b}
_OP_SYM = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%",
           ast.Pow: "**", ast.LShift: "<<", ast.RShift: ">>", ast.BitOr: "|", ast.BitXor: "^", ast.BitAnd: "&"}
_FAST = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
         ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b}


def inplace(st, op, cur, val):
    """Augmented assignment: in place for list += and set/dict |= (Python semantics), else binop."""
    t = type(cur)
    if t is list and op is ast.Add:
        items = materialize(st, val)
        _check_len(st, len(cur) + len(items))
        cur.extend(items)
        return cur
    if t is set and type(val) is set and op in _SET_OPS:
        st.charge((len(cur) + len(val)) // 4 + 1)
        {ast.BitOr: cur.__ior__, ast.BitAnd: cur.__iand__, ast.Sub: cur.__isub__,
         ast.BitXor: cur.__ixor__}[op](val)
        return cur
    if t is dict and type(val) is dict and op is ast.BitOr:
        _check_len(st, len(cur) + len(val))
        cur.update(val)
        return cur
    return binop(st, op, cur, val)


def compare(st, op, a, b):
    if type(a) is _ND or type(b) is _ND:
        return NPX.compare(st, op, a, b)
    if op is ast.Eq or op is ast.NotEq:
        if type(a) in (list, tuple) and type(b) in (list, tuple):
            st.charge(min(len(a), len(b)) // 16 + 1)
        r = a == b
        return r if op is ast.Eq else not r
    if op is ast.In or op is ast.NotIn:
        tb = type(b)
        if tb not in SIZED:
            raise Fault(f"'in' needs a list, tuple, set, dict, string or range, not {a_(b)}")
        if tb is list or tb is tuple:
            st.charge(len(b) // 16 + 1)
        if tb is str and type(a) is not str:
            raise Fault("'in' on a string needs a string")
        r = a in b
        return r if op is ast.In else not r
    if op is ast.Is:
        return a is b
    if op is ast.IsNot:
        return a is not b
    try:
        return _CMP[op](a, b)
    except TypeError:
        raise Fault(f"cannot compare {a_(a)} with {a_(b)}") from None


_CMP = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b}


def getitem(st, v, i):
    t = type(v)
    if t is _ND:
        return NPX.getitem(st, v, i)
    if t is list or t is tuple or t is str or t is range:
        ti = type(i)
        if ti is int or ti is bool:
            try:
                return v[i]
            except IndexError:
                raise Fault(f"index {i} is out of range for {a_(v)} of length {len(v)}") from None
        if ti is slice:
            r = v[i]
            st.charge(len(r) // 4 + 1)
            return r
        raise Fault(f"{a_(v)} index must be an int or a slice, not {a_(i)}")
    if t is dict:
        try:
            return v[i]
        except KeyError:
            ent = st.defaults.get(id(v))
            if ent is not None and ent[0] is v:
                x = call(st, ent[1], [], {})
                _check_len(st, len(v) + 1)
                v[i] = x
                return x
            raise Fault(f"key {_short(i)} is not in the dict") from None
        except TypeError:
            raise Fault(f"{a_(i)} cannot be a dict key") from None
    raise Fault(f"{a_(v)} cannot be indexed")


def setitem(st, v, i, x):
    t = type(v)
    if t is _ND:
        return NPX.setitem(st, v, i, x)
    if t is list:
        ti = type(i)
        if ti is int or ti is bool:
            try:
                v[i] = x
            except IndexError:
                raise Fault(f"index {i} is out of range for a list of length {len(v)}") from None
            return
        if ti is slice:
            items = materialize(st, x)
            _check_len(st, len(v) + len(items))
            try:
                v[i] = items
            except ValueError as e:
                raise Fault(str(e)[:120]) from None
            return
        raise Fault(f"a list index must be an int or a slice, not {a_(i)}")
    if t is dict:
        _check_len(st, len(v) + 1)
        try:
            v[i] = x
        except TypeError:
            raise Fault(f"{a_(i)} cannot be a dict key") from None
        return
    raise Fault(f"cannot assign into {a_(v)} (only lists and dicts can change)")


def _short(x):
    s = repr(x) if type(x) in (int, str, bool, tuple, float, type(None)) else tname(x)
    return s[:40]


def truth(x):
    if type(x) is _ND:
        return NPX.truth(x)
    return bool(x)


# ------------------------------------------------------------------ builtins
def _args(name, args, kw, lo, hi=None, kws=()):
    hi = lo if hi is None else hi
    if not lo <= len(args) <= hi:
        want = f"{lo}" if lo == hi else f"{lo} to {hi}"
        raise Fault(f"{name}() takes {want} arguments, {len(args)} given")
    for k in kw:
        if k not in kws:
            raise Fault(f"{name}() has no keyword {k}")


def _num(name, x):
    if type(x) not in NUMBERS:
        raise Fault(f"{name}() needs a number, not {a_(x)}")
    return x


def b_len(st, a, kw):
    _args("len", a, kw, 1)
    if type(a[0]) in SIZED:
        return len(a[0])
    if type(a[0]) is _ND and a[0].ndim:
        return int(a[0].shape[0])
    raise Fault(f"len() of {a_(a[0])}")


def b_range(st, a, kw):
    _args("range", a, kw, 1, 3)
    for x in a:
        if type(x) not in (int, bool):
            raise Fault(f"range() needs ints, not {a_(x)}")
    try:
        return range(*a)
    except ValueError as e:
        raise Fault(f"range(): {e}") from None


def _keys(st, key, items):
    if key is None:
        return items
    return [call(st, key, [x], {}) for x in items]


def _minmax(name, st, a, kw, want_max):
    _args(name, a, kw, 1, 1 << 30, ("key", "default"))
    key = kw.get("key")
    items = materialize(st, a[0]) if len(a) == 1 else list(a)
    if not items:
        if "default" in kw:
            return kw["default"]
        raise Fault(f"{name}() of an empty sequence")
    keys = _keys(st, key, items)
    st.charge(len(items) // 4 + 1)
    best = 0
    try:
        for i in range(1, len(items)):
            if (keys[i] > keys[best]) if want_max else (keys[i] < keys[best]):
                best = i
    except TypeError:
        raise Fault(f"{name}() cannot compare these values") from None
    return items[best]


def b_min(st, a, kw):
    return _minmax("min", st, a, kw, False)


def b_max(st, a, kw):
    return _minmax("max", st, a, kw, True)


def b_sum(st, a, kw):
    _args("sum", a, kw, 1, 2, ("start",))
    total = a[1] if len(a) > 1 else kw.get("start", 0)
    for x in iterable(a[0]):
        st.steps += 1
        if st.steps > st.max_steps:
            raise StepLimit()
        total = binop(st, ast.Add, total, x)
    return total


def b_abs(st, a, kw):
    _args("abs", a, kw, 1)
    return abs(_num("abs", a[0]))


def b_sorted(st, a, kw):
    _args("sorted", a, kw, 1, 1, ("key", "reverse"))
    items = materialize(st, a[0])
    return _sort(st, items, kw.get("key"), kw.get("reverse", False))


def _sort(st, items, key, reverse):
    n = len(items)
    st.charge(n * max(1, n.bit_length()) // 4 + 1)
    keys = _keys(st, key, items)
    order = list(range(n))
    try:
        order.sort(key=keys.__getitem__, reverse=bool(reverse))
    except TypeError:
        raise Fault("sorted() cannot compare these values") from None
    return [items[i] for i in order]


def b_enumerate(st, a, kw):
    _args("enumerate", a, kw, 1, 2, ("start",))
    start = a[1] if len(a) > 1 else kw.get("start", 0)
    if type(start) not in (int, bool):
        raise Fault("enumerate() start must be an int")
    items = materialize(st, a[0])
    return [(start + i, x) for i, x in enumerate(items)]


def b_zip(st, a, kw):
    _args("zip", a, kw, 0, 1 << 30)
    its = [iter(iterable(x)) for x in a]
    out = []
    if not its:
        return out
    while True:
        row = []
        for it in its:
            try:
                row.append(next(it))
            except StopIteration:
                return out
        st.steps += 1
        if st.steps > st.max_steps:
            raise StepLimit()
        out.append(tuple(row))
        if len(out) > st.max_seq:
            _check_len(st, len(out))


def b_list(st, a, kw):
    _args("list", a, kw, 0, 1)
    return materialize(st, a[0]) if a else []


def b_tuple(st, a, kw):
    _args("tuple", a, kw, 0, 1)
    return tuple(materialize(st, a[0])) if a else ()


def b_set(st, a, kw):
    _args("set", a, kw, 0, 1)
    try:
        return set(materialize(st, a[0])) if a else set()
    except TypeError:
        raise Fault("set elements must be ints, tuples or strings (not lists)") from None


def b_dict(st, a, kw):
    _args("dict", a, kw, 0, 1)
    if not a:
        return {}
    x = a[0]
    if type(x) is dict:
        st.charge(len(x) // 4 + 1)
        return dict(x)
    out = {}
    for p in materialize(st, x):
        if type(p) not in (list, tuple) or len(p) != 2:
            raise Fault("dict() needs (key, value) pairs")
        try:
            out[p[0]] = p[1]
        except TypeError:
            raise Fault("a dict key cannot be a list") from None
    return out


def _bool_iter(name, st, a, kw, want):
    _args(name, a, kw, 1)
    for x in iterable(a[0]):
        st.steps += 1
        if st.steps > st.max_steps:
            raise StepLimit()
        if bool(x) is want:
            return want
    return not want


def b_any(st, a, kw):
    return _bool_iter("any", st, a, kw, True)


def b_all(st, a, kw):
    return _bool_iter("all", st, a, kw, False)


def b_reversed(st, a, kw):
    _args("reversed", a, kw, 1)
    if type(a[0]) not in (list, tuple, range, str):
        raise Fault(f"reversed() needs a list, tuple, range or string, not {a_(a[0])}")
    return materialize(st, a[0])[::-1]


def b_int(st, a, kw):
    _args("int", a, kw, 0, 1)
    if not a:
        return 0
    x = a[0]
    if type(x) in NUMBERS:
        try:
            return _int_ok(st, int(x))
        except (OverflowError, ValueError):
            raise Fault("int() of an infinite or undefined number") from None
    if type(x) is str:
        try:
            return _int_ok(st, int(x))
        except ValueError:
            raise Fault(f"int() cannot read {x!r}") from None
    raise Fault(f"int() of {a_(x)}")


def b_bool(st, a, kw):
    _args("bool", a, kw, 0, 1)
    return bool(a[0]) if a else False


def b_round(st, a, kw):
    _args("round", a, kw, 1, 2)
    x = _num("round", a[0])
    if len(a) == 2:
        if type(a[1]) not in (int, bool) or abs(a[1]) > 20:
            raise Fault("round() digits must be an int from -20 to 20")
        return round(x, a[1])
    try:
        return round(x)
    except (OverflowError, ValueError):
        raise Fault("round() of an infinite or undefined number") from None


def b_divmod(st, a, kw):
    _args("divmod", a, kw, 2)
    return divmod(_num("divmod", a[0]), _num("divmod", a[1]))


def b_print(st, a, kw):
    return None


def b_map(st, a, kw):
    _args("map", a, kw, 2, 1 << 30)
    f = a[0]
    cols = [materialize(st, x) for x in a[1:]]
    n = min(len(c) for c in cols)
    return [call(st, f, [c[i] for c in cols], {}) for i in range(n)]


def b_filter(st, a, kw):
    _args("filter", a, kw, 2)
    f = a[0]
    items = materialize(st, a[1])
    if f is None:
        return [x for x in items if x]
    return [x for x in items if call(st, f, [x], {})]


def b_deepcopy(st, a, kw):
    _args("deepcopy", a, kw, 1)
    st.charge(_size(a[0]) // 4 + 1)
    try:
        return P.copy(a[0])
    except P.PrimError as e:
        raise Fault(f"deepcopy(): {e}") from None


BUILTINS = {n[2:]: Builtin(n[2:], f) for n, f in list(globals().items()) if n.startswith("b_")}
assert set(BUILTINS) == set(L.BUILTIN_NAMES), sorted(set(BUILTINS) ^ set(L.BUILTIN_NAMES))
PRIMITIVES = {name: Primitive(name, p.fn, p.weight, p.cost) for name, p in P.REGISTRY.items()}


# ------------------------------------------------------------------ methods
def _m(name, recv, a, kw, lo, hi=None, kws=()):
    _args(f"{tname(recv)}.{name}", a, kw, lo, hi, kws)


def m_list_append(st, v, a, kw):
    _m("append", v, a, kw, 1)
    _check_len(st, len(v) + 1)
    v.append(a[0])


def m_list_extend(st, v, a, kw):
    _m("extend", v, a, kw, 1)
    items = materialize(st, a[0])
    _check_len(st, len(v) + len(items))
    v.extend(items)


def m_list_insert(st, v, a, kw):
    _m("insert", v, a, kw, 2)
    if type(a[0]) not in (int, bool):
        raise Fault("list.insert() position must be an int")
    _check_len(st, len(v) + 1)
    st.charge(len(v) // 16 + 1)
    v.insert(a[0], a[1])


def m_list_pop(st, v, a, kw):
    _m("pop", v, a, kw, 0, 1)
    if not v:
        raise Fault("pop from an empty list")
    try:
        return v.pop(*a)
    except (IndexError, TypeError):
        raise Fault("list.pop() index out of range") from None


def m_list_remove(st, v, a, kw):
    _m("remove", v, a, kw, 1)
    st.charge(len(v) // 16 + 1)
    try:
        v.remove(a[0])
    except ValueError:
        raise Fault(f"list.remove(): {_short(a[0])} is not in the list") from None


def m_seq_index(st, v, a, kw):
    _m("index", v, a, kw, 1, 3)
    st.charge(len(v) // 16 + 1)
    try:
        return v.index(*a)
    except (ValueError, TypeError):
        raise Fault(f"{tname(v)}.index(): {_short(a[0])} is not in the {tname(v)}") from None


def m_seq_count(st, v, a, kw):
    _m("count", v, a, kw, 1)
    st.charge(len(v) // 16 + 1)
    return v.count(a[0])


def m_list_copy(st, v, a, kw):
    _m("copy", v, a, kw, 0)
    st.charge(len(v) // 4 + 1)
    return list(v)


def m_list_reverse(st, v, a, kw):
    _m("reverse", v, a, kw, 0)
    st.charge(len(v) // 4 + 1)
    v.reverse()


def m_list_sort(st, v, a, kw):
    _m("sort", v, a, kw, 0, 0, ("key", "reverse"))
    v[:] = _sort(st, list(v), kw.get("key"), kw.get("reverse", False))


def m_list_clear(st, v, a, kw):
    _m("clear", v, a, kw, 0)
    v.clear()


def _hashable(x):
    try:
        hash(x)
    except TypeError:
        raise Fault(f"{a_(x)} cannot be a dict key or set element") from None
    return x


def m_dict_get(st, v, a, kw):
    _m("get", v, a, kw, 1, 2)
    return v.get(_hashable(a[0]), a[1] if len(a) > 1 else None)


def m_dict_keys(st, v, a, kw):
    _m("keys", v, a, kw, 0)
    st.charge(len(v) // 4 + 1)
    return list(v.keys())


def m_dict_values(st, v, a, kw):
    _m("values", v, a, kw, 0)
    st.charge(len(v) // 4 + 1)
    return list(v.values())


def m_dict_items(st, v, a, kw):
    _m("items", v, a, kw, 0)
    st.charge(len(v) // 4 + 1)
    return list(v.items())


def m_dict_setdefault(st, v, a, kw):
    _m("setdefault", v, a, kw, 1, 2)
    k = _hashable(a[0])
    if k not in v:
        _check_len(st, len(v) + 1)
    return v.setdefault(k, a[1] if len(a) > 1 else None)


def m_dict_update(st, v, a, kw):
    _m("update", v, a, kw, 1)
    new = b_dict(st, [a[0]], {})
    _check_len(st, len(v) + len(new))
    v.update(new)


def m_dict_copy(st, v, a, kw):
    _m("copy", v, a, kw, 0)
    st.charge(len(v) // 4 + 1)
    return dict(v)


def m_dict_pop(st, v, a, kw):
    _m("pop", v, a, kw, 1, 2)
    k = _hashable(a[0])
    if k in v:
        return v.pop(k)
    if len(a) > 1:
        return a[1]
    raise Fault(f"dict.pop(): key {_short(k)} is not in the dict")


def m_set_add(st, v, a, kw):
    _m("add", v, a, kw, 1)
    _check_len(st, len(v) + 1)
    v.add(_hashable(a[0]))


def m_set_discard(st, v, a, kw):
    _m("discard", v, a, kw, 1)
    v.discard(_hashable(a[0]))


def m_set_remove(st, v, a, kw):
    _m("remove", v, a, kw, 1)
    if _hashable(a[0]) not in v:
        raise Fault(f"set.remove(): {_short(a[0])} is not in the set")
    v.remove(a[0])


def _set_args(st, a):
    out = []
    for x in a:
        try:
            out.append(set(materialize(st, x)))
        except TypeError:
            raise Fault("set elements must be ints, tuples or strings (not lists)") from None
    return out


def m_set_union(st, v, a, kw):
    _m("union", v, a, kw, 0, 1 << 30)
    r = set(v).union(*_set_args(st, a))
    _check_len(st, len(r))
    return r


def m_set_intersection(st, v, a, kw):
    _m("intersection", v, a, kw, 0, 1 << 30)
    return set(v).intersection(*_set_args(st, a))


def m_set_difference(st, v, a, kw):
    _m("difference", v, a, kw, 0, 1 << 30)
    return set(v).difference(*_set_args(st, a))


def m_set_issubset(st, v, a, kw):
    _m("issubset", v, a, kw, 1)
    return v.issubset(*_set_args(st, a))


def m_set_issuperset(st, v, a, kw):
    _m("issuperset", v, a, kw, 1)
    return v.issuperset(*_set_args(st, a))


def m_set_update(st, v, a, kw):
    _m("update", v, a, kw, 0, 1 << 30)
    for s in _set_args(st, a):
        _check_len(st, len(v) + len(s))
        v.update(s)


def m_set_copy(st, v, a, kw):
    _m("copy", v, a, kw, 0)
    st.charge(len(v) // 4 + 1)
    return set(v)


METHODS = {}
for _tn, _names in L.METHODS.items():
    _t = {"list": list, "dict": dict, "set": set, "tuple": tuple}[_tn]
    for _name in _names:
        _f = globals().get(f"m_{_tn}_{_name}") or globals().get(f"m_seq_{_name}")
        assert _f is not None, (_tn, _name)
        METHODS[(_t, _name)] = _f


# ------------------------------------------------------------------ gridfn-2: collections (lowered) and extra methods
def g_Counter(st, a, kw):
    _args("Counter", a, kw, 0, 1)
    out = {}
    if a:
        for v in materialize(st, a[0]):
            try:
                out[v] = out.get(v, 0) + 1
            except TypeError:
                raise Fault(f"{a_(v)} cannot be counted (unhashable)") from None
    return out


def g_defaultdict(st, a, kw):
    _args("defaultdict", a, kw, 0, 1)
    d = {}
    if a and a[0] is not None:
        st.defaults[id(d)] = (d, a[0])
    return d


def g_deque(st, a, kw):
    _args("deque", a, kw, 0, 1)
    return materialize(st, a[0]) if a else []


def m_list_popleft(st, v, a, kw):
    _m("popleft", v, a, kw, 0)
    if not v:
        raise Fault("pop from an empty deque")
    return v.pop(0)


def m_list_appendleft(st, v, a, kw):
    _m("appendleft", v, a, kw, 1)
    _check_len(st, len(v) + 1)
    v.insert(0, a[0])


def m_dict_most_common(st, v, a, kw):
    _m("most_common", v, a, kw, 0, 1)
    items = sorted(v.items(), key=lambda kv: kv[1], reverse=True)
    st.charge(len(items) // 4 + 1)
    return [tuple(x) for x in (items if not a or a[0] is None else items[:a[0]])]


METHODS[(list, "popleft")], METHODS[(list, "appendleft")] = m_list_popleft, m_list_appendleft
METHODS[(dict, "most_common")] = m_dict_most_common


def m_set_pop(st, v, a, kw):
    _m("pop", v, a, kw, 0)
    if not v:
        raise Fault("pop from an empty set")
    x = min(v, key=lambda e: (str(type(e)), e)) if all(isinstance(e, (int, float)) for e in v) else next(iter(v))
    v.discard(x)
    return x


METHODS[(set, "pop")] = m_set_pop
def g_float(st, a, kw):
    _args("float", a, kw, 1)
    x = a[0]
    if type(x) is str and x.strip().lower() in ("inf", "+inf", "-inf", "infinity", "-infinity", "nan"):
        return float(x)
    if type(x) in (int, float, bool):
        return float(x)
    raise Fault(f"float() of {a_(x)}")


GRIDFN2_BUILTINS = {"Counter": Builtin("Counter", g_Counter), "defaultdict": Builtin("defaultdict", g_defaultdict),
                    "deque": Builtin("deque", g_deque), "float": Builtin("float", g_float)}


# ------------------------------------------------------------------ compiler
def _cost(*nodes):
    n = 0
    for node in nodes:
        if node is None:
            continue
        for x in ast.walk(node):
            if not isinstance(x, L._UNCOUNTED):
                n += 1
    return n


class Compiler:
    """Closures for every node kind; `scopes` is the list of lexical scopes (sets of local names), innermost last,
    matching the runtime frame chain (function frames, comprehension frames)."""

    def __init__(self, st, module_names):
        self.st, self.module_names = st, module_names

    # ---------- names
    def resolve(self, name, scopes):
        for depth, s in enumerate(reversed(scopes)):
            if name in s:
                return ("frame", depth)
        if name in self.module_names:
            return ("global", None)
        if name in BUILTINS:
            return ("value", BUILTINS[name])
        if name in PRIMITIVES:
            return ("value", PRIMITIVES[name])
        if name in P.CONSTANTS:
            return ("value", P.CONSTANTS[name])
        if name in ("np", "numpy"):
            return ("value", NPX.NP)
        if name in GRIDFN2_BUILTINS:
            return ("value", GRIDFN2_BUILTINS[name])
        raise Fault(f"name '{name}' is not defined")

    def load(self, name, scopes):
        kind, x = self.resolve(name, scopes)
        st = self.st
        if kind == "value":
            return lambda fr: x
        if kind == "global":
            def get_global(fr):
                try:
                    return st.globals[name]
                except KeyError:
                    raise Fault(f"name '{name}' is used before it is defined") from None
            return get_global
        depth = x
        if depth == 0:
            def get0(fr):
                try:
                    return fr.vars[name]
                except KeyError:
                    raise Fault(f"variable '{name}' is used before it is assigned") from None
            return get0

        def get_up(fr):
            f = fr
            for _ in range(depth):
                f = f.parent
            try:
                return f.vars[name]
            except KeyError:
                raise Fault(f"variable '{name}' is used before it is assigned") from None
        return get_up

    def store_name(self, name, scopes):
        st = self.st
        if not scopes:
            def set_global(fr, v):
                st.globals[name] = v
            return set_global

        def set_local(fr, v):
            fr.vars[name] = v
        return set_local

    def store(self, t, scopes):
        st = self.st
        if isinstance(t, ast.Name):
            return self.store_name(t.id, scopes)
        if isinstance(t, (ast.Tuple, ast.List)):
            subs = [self.store(e, scopes) for e in t.elts]
            n = len(subs)

            def set_unpack(fr, v):
                items = v if type(v) is tuple or type(v) is list else materialize(st, v)
                if len(items) != n:
                    raise Fault(f"cannot unpack {len(items)} values into {n} names")
                for s, x in zip(subs, items):
                    s(fr, x)
            return set_unpack
        if isinstance(t, ast.Subscript):
            cont, idx = self.expr(t.value, scopes), self.expr(t.slice, scopes)

            def set_item(fr, v):
                setitem(st, cont(fr), idx(fr), v)
            return set_item
        raise Fault(f"cannot assign to {type(t).__name__}")

    # ---------- statements
    def block(self, stmts, scopes):
        fns = [self.stmt(s, scopes) for s in stmts]
        if len(fns) == 1:
            return fns[0]

        def run_block(fr):
            for f in fns:
                r = f(fr)
                if r is not None:
                    return r
            return None
        return run_block

    def stmt(self, node, scopes):
        return getattr(self, "s_" + type(node).__name__)(node, scopes)

    def s_FunctionDef(self, node, scopes):
        st = self.st
        params = [a.arg for a in node.args.args]
        local = set(params) | L._bound_names(node.body)
        body = self.block(node.body, scopes + [local])
        defaults = [self.expr(d, scopes) for d in node.args.defaults]
        dnames = params[len(params) - len(defaults):]
        setter = self.store_name(node.name, scopes)
        name, line, nested = node.name, node.lineno, bool(scopes)

        def run_def(fr):
            st.line = line
            st.charge(1 + len(defaults))
            fn = UserFunction(name, params, dict(zip(dnames, [d(fr) for d in defaults])), body,
                              fr if nested else None, st)
            setter(fr, fn)
        return run_def

    def s_Assign(self, node, scopes):
        st, line = self.st, node.lineno
        val = self.expr(node.value, scopes)
        setters = [self.store(t, scopes) for t in node.targets]
        cost = 1 + _cost(node.value, *node.targets)
        if len(setters) == 1:
            s1 = setters[0]

            def run_assign(fr):
                st.line = line
                st.steps += cost
                if st.steps > st.max_steps:
                    raise StepLimit()
                s1(fr, val(fr))
            return run_assign

        def run_assign_n(fr):
            st.line = line
            st.charge(cost)
            v = val(fr)
            for s in setters:
                s(fr, v)
        return run_assign_n

    def s_AugAssign(self, node, scopes):
        st, line, op = self.st, node.lineno, type(node.op)
        val = self.expr(node.value, scopes)
        cost = 2 + _cost(node.value, node.target)
        t = node.target
        if isinstance(t, ast.Name):
            get, put = self.load(t.id, scopes), self.store_name(t.id, scopes)

            def run_aug(fr):
                st.line = line
                st.charge(cost)
                cur = get(fr)
                v = val(fr)
                if type(cur) is int and type(v) is int and op in _FAST:
                    put(fr, _int_ok(st, _FAST[op](cur, v)))
                else:
                    put(fr, inplace(st, op, cur, v))
            return run_aug
        cont, idx = self.expr(t.value, scopes), self.expr(t.slice, scopes)

        def run_aug_item(fr):
            st.line = line
            st.charge(cost)
            c, i = cont(fr), idx(fr)
            cur = getitem(st, c, i)
            setitem(st, c, i, inplace(st, op, cur, val(fr)))
        return run_aug_item

    def s_Return(self, node, scopes):
        st, line = self.st, node.lineno
        if node.value is None:
            def run_ret_none(fr):
                st.line = line
                st.charge(1)
                return Ret(None)
            return run_ret_none
        val, cost = self.expr(node.value, scopes), 1 + _cost(node.value)

        def run_ret(fr):
            st.line = line
            st.steps += cost
            if st.steps > st.max_steps:
                raise StepLimit()
            return Ret(val(fr))
        return run_ret

    def s_If(self, node, scopes):
        st, line = self.st, node.lineno
        test, cost = self.expr(node.test, scopes), 1 + _cost(node.test)
        body = self.block(node.body, scopes)
        orelse = self.block(node.orelse, scopes) if node.orelse else None

        def run_if(fr):
            st.line = line
            st.steps += cost
            if st.steps > st.max_steps:
                raise StepLimit()
            if test(fr):
                return body(fr)
            if orelse is not None:
                return orelse(fr)
            return None
        return run_if

    def s_For(self, node, scopes):
        st, line = self.st, node.lineno
        it, setter = self.expr(node.iter, scopes), self.store(node.target, scopes)
        body = self.block(node.body, scopes)
        orelse = self.block(node.orelse, scopes) if node.orelse else None
        head, per = 1 + _cost(node.iter), 1 + _cost(node.target)

        def run_for(fr):
            st.line = line
            st.charge(head)
            seq = it(fr)
            if type(seq) not in ITERABLE:
                if type(seq) is not _ND:
                    raise Fault(f"cannot loop over {a_(seq)}")
                seq = iterable(seq)
            for x in seq:
                st.line = line
                st.steps += per
                if st.steps > st.max_steps:
                    raise StepLimit()
                setter(fr, x)
                r = body(fr)
                if r is not None:
                    if r is BREAK:
                        break
                    if r is CONTINUE:
                        continue
                    return r
            else:
                if orelse is not None:
                    return orelse(fr)
            return None
        return run_for

    def s_While(self, node, scopes):
        st, line = self.st, node.lineno
        test, cost = self.expr(node.test, scopes), 1 + _cost(node.test)
        body = self.block(node.body, scopes)
        orelse = self.block(node.orelse, scopes) if node.orelse else None

        def run_while(fr):
            while True:
                st.line = line
                st.steps += cost
                if st.steps > st.max_steps:
                    raise StepLimit()
                if not test(fr):
                    break
                r = body(fr)
                if r is not None:
                    if r is BREAK:
                        return None
                    if r is CONTINUE:
                        continue
                    return r
            if orelse is not None:
                return orelse(fr)
            return None
        return run_while

    def s_Expr(self, node, scopes):
        st, line = self.st, node.lineno
        val, cost = self.expr(node.value, scopes), 1 + _cost(node.value)

        def run_expr(fr):
            st.line = line
            st.charge(cost)
            val(fr)
        return run_expr

    def s_Pass(self, node, scopes):
        st = self.st

        def run_pass(fr):
            st.charge(1)
        return run_pass

    def s_Break(self, node, scopes):
        st = self.st

        def run_break(fr):
            st.charge(1)
            return BREAK
        return run_break

    def s_Continue(self, node, scopes):
        st = self.st

        def run_continue(fr):
            st.charge(1)
            return CONTINUE
        return run_continue

    # ---------- expressions
    def expr(self, node, scopes):
        return getattr(self, "e_" + type(node).__name__)(node, scopes)

    def e_Constant(self, node, scopes):
        v = node.value
        return lambda fr: v

    def e_Name(self, node, scopes):
        return self.load(node.id, scopes)

    def e_Lambda(self, node, scopes):
        st = self.st
        params = [a.arg for a in node.args.args]
        ret = ast.copy_location(ast.Return(node.body), node)
        body = self.block([ret], scopes + [set(params)])
        defaults = [self.expr(d, scopes) for d in node.args.defaults]
        dnames = params[len(params) - len(defaults):]

        def run_lambda(fr):
            st.charge(1 + len(defaults))
            return UserFunction("<lambda>", params, dict(zip(dnames, [d(fr) for d in defaults])), body, fr, st)
        return run_lambda

    def e_Attribute(self, node, scopes):
        st, name = self.st, node.attr
        vf = self.expr(node.value, scopes)

        def run_attr(fr):
            v = vf(fr)
            if (type(v), name) in METHODS:
                return BoundMethod(v, name)
            return NPX.attribute(st, v, name)
        return run_attr

    def e_BinOp(self, node, scopes):
        st, op = self.st, type(node.op)
        lf, rf = self.expr(node.left, scopes), self.expr(node.right, scopes)
        fast = _FAST.get(op)
        if fast is not None:
            mx = st.max_int

            def run_binop_fast(fr):
                a, b = lf(fr), rf(fr)
                if type(a) is int and type(b) is int:
                    r = fast(a, b)
                    if -mx <= r <= mx:
                        return r
                    raise Fault("integer result too large")
                return binop(st, op, a, b)
            return run_binop_fast

        def run_binop(fr):
            return binop(st, op, lf(fr), rf(fr))
        return run_binop

    def e_UnaryOp(self, node, scopes):
        st, op = self.st, type(node.op)
        vf = self.expr(node.operand, scopes)
        if op is ast.Not:
            return lambda fr: not vf(fr)

        def run_unary(fr):
            v = vf(fr)
            if type(v) not in NUMBERS:
                raise Fault(f"unary {'-' if op is ast.USub else '+' if op is ast.UAdd else '~'} needs a number, "
                            f"not {a_(v)}")
            if op is ast.USub:
                return -v
            if op is ast.UAdd:
                return +v
            if type(v) is float:
                raise Fault("~ needs an int")
            return ~v
        return run_unary

    def e_BoolOp(self, node, scopes):
        vals = [self.expr(v, scopes) for v in node.values]
        if isinstance(node.op, ast.And):
            def run_and(fr):
                v = True
                for f in vals:
                    v = f(fr)
                    if not v:
                        return v
                return v
            return run_and

        def run_or(fr):
            v = False
            for f in vals:
                v = f(fr)
                if v:
                    return v
            return v
        return run_or

    def e_Compare(self, node, scopes):
        st = self.st
        left = self.expr(node.left, scopes)
        pairs = [(type(op), self.expr(c, scopes)) for op, c in zip(node.ops, node.comparators)]
        if len(pairs) == 1:
            op, rf = pairs[0]
            if op in _CMP:
                cmpf = _CMP[op]

                def run_cmp1(fr):
                    a, b = left(fr), rf(fr)
                    if type(a) is int and type(b) is int:
                        return cmpf(a, b)
                    return compare(st, op, a, b)
                return run_cmp1

            def run_cmp_any(fr):
                return compare(st, op, left(fr), rf(fr))
            return run_cmp_any

        def run_chain(fr):
            a = left(fr)
            for op, rf in pairs:
                b = rf(fr)
                if not compare(st, op, a, b):
                    return False
                a = b
            return True
        return run_chain

    def e_IfExp(self, node, scopes):
        t, b, o = (self.expr(x, scopes) for x in (node.test, node.body, node.orelse))
        return lambda fr: b(fr) if t(fr) else o(fr)

    def e_Call(self, node, scopes):
        st = self.st
        if any(isinstance(a, ast.Starred) for a in node.args):     # gridfn-2: f(*seq) (checked by lang)
            parts = [(True, self.expr(a.value, scopes)) if isinstance(a, ast.Starred) else (False, self.expr(a, scopes))
                     for a in node.args]

            def star_args(fr):
                out = []
                for star, f in parts:
                    if star:
                        out.extend(materialize(st, f(fr)))
                    else:
                        out.append(f(fr))
                return out
            fnode = node.func
            kws = [(k.arg, self.expr(k.value, scopes)) for k in node.keywords]
            if isinstance(fnode, ast.Attribute):
                raise Fault("f(*args) is supported only for plain function names")
            fn = self.expr(fnode, scopes)
            return lambda fr: call(st, fn(fr), star_args(fr), {k: v(fr) for k, v in kws})
        args = [self.expr(a, scopes) for a in node.args]
        kws = [(k.arg, self.expr(k.value, scopes)) for k in node.keywords]
        if isinstance(node.func, ast.Attribute):
            recv, name = self.expr(node.func.value, scopes), node.func.attr

            def run_method(fr):
                r = recv(fr)
                m = METHODS.get((type(r), name))
                if m is None:
                    if r is NPX.NP:
                        f = NPX.MODULE_FUNCS.get(name)
                        if f is None:
                            raise Fault(f"np.{name}() is not part of the supported numpy subset")
                        st.steps += 1
                        return f(st, [a(fr) for a in args], {k: v(fr) for k, v in kws})
                    if type(r) is _ND:
                        return NPX.method(st, r, name, [a(fr) for a in args], {k: v(fr) for k, v in kws})
                    raise Fault(f"{a_(r)} has no method {name}()")
                st.steps += 1
                return m(st, r, [a(fr) for a in args], {k: v(fr) for k, v in kws})
            return run_method
        fn = self.expr(node.func, scopes)
        if not kws:
            def run_call(fr):
                return call(st, fn(fr), [a(fr) for a in args], {})
            return run_call

        def run_call_kw(fr):
            return call(st, fn(fr), [a(fr) for a in args], {k: v(fr) for k, v in kws})
        return run_call_kw

    def e_List(self, node, scopes):
        elts = [self.expr(e, scopes) for e in node.elts]
        return lambda fr: [e(fr) for e in elts]

    def e_Tuple(self, node, scopes):
        elts = [self.expr(e, scopes) for e in node.elts]
        return lambda fr: tuple([e(fr) for e in elts])

    def e_Set(self, node, scopes):
        elts = [self.expr(e, scopes) for e in node.elts]

        def run_set(fr):
            try:
                return {e(fr) for e in elts}
            except TypeError:
                raise Fault("set elements must be ints, tuples or strings (not lists)") from None
        return run_set

    def e_Dict(self, node, scopes):
        ks = [self.expr(k, scopes) for k in node.keys]
        vs = [self.expr(v, scopes) for v in node.values]

        def run_dict(fr):
            out = {}
            for k, v in zip(ks, vs):
                key = k(fr)
                try:
                    out[key] = v(fr)
                except TypeError:
                    raise Fault(f"{a_(key)} cannot be a dict key") from None
            return out
        return run_dict

    def e_Subscript(self, node, scopes):
        st = self.st
        vf, sf = self.expr(node.value, scopes), self.expr(node.slice, scopes)

        def run_sub(fr):
            v, i = vf(fr), sf(fr)
            if type(v) is list and type(i) is int:
                try:
                    return v[i]
                except IndexError:
                    raise Fault(f"index {i} is out of range for a list of length {len(v)}") from None
            return getitem(st, v, i)
        return run_sub

    def e_Slice(self, node, scopes):
        parts = [None if x is None else self.expr(x, scopes) for x in (node.lower, node.upper, node.step)]

        def run_slice(fr):
            vals = []
            for p in parts:
                v = None if p is None else p(fr)
                if v is not None and type(v) not in (int, bool):
                    raise Fault(f"slice bounds must be ints, not {a_(v)}")
                vals.append(v)
            if vals[2] == 0:
                raise Fault("slice step cannot be zero")
            return slice(*vals)
        return run_slice

    # ---------- comprehensions
    def _comp(self, node, scopes):
        """(driver, inner scopes): driver(fr, cf) yields once per combination that passes the conditions, with the
        targets bound in the comprehension frame cf."""
        st = self.st
        inner = scopes + [set().union(*(L._target_names(g.target) for g in node.generators))]
        levels = []
        for i, g in enumerate(node.generators):
            it = self.expr(g.iter, scopes if i == 0 else inner)
            setter = self.store(g.target, inner)
            conds = [self.expr(c, inner) for c in g.ifs]
            per = 1 + _cost(g.target, *g.ifs)
            levels.append((it, setter, conds, per))
        n = len(levels)

        def drive(fr, cf, first, i=0):
            it, setter, conds, per = levels[i]
            seq = first if i == 0 else it(cf)
            if type(seq) not in ITERABLE:
                if type(seq) is not _ND:
                    raise Fault(f"cannot loop over {a_(seq)}")
                seq = iterable(seq)
            for x in seq:
                st.steps += per
                if st.steps > st.max_steps:
                    raise StepLimit()
                setter(cf, x)
                ok = True
                for c in conds:
                    if not c(cf):
                        ok = False
                        break
                if not ok:
                    continue
                if i + 1 == n:
                    yield None
                else:
                    yield from drive(fr, cf, None, i + 1)
        return drive, levels[0][0], inner

    def e_ListComp(self, node, scopes):
        st = self.st
        drive, first, inner = self._comp(node, scopes)
        elt, cost = self.expr(node.elt, inner), 1 + _cost(node.elt)

        def run_listcomp(fr):
            cf = Frame(fr)
            out = []
            for _ in drive(fr, cf, first(fr)):
                st.steps += cost
                if st.steps > st.max_steps:
                    raise StepLimit()
                out.append(elt(cf))
                if len(out) > st.max_seq:
                    _check_len(st, len(out))
            return out
        return run_listcomp

    def e_SetComp(self, node, scopes):
        st = self.st
        drive, first, inner = self._comp(node, scopes)
        elt, cost = self.expr(node.elt, inner), 1 + _cost(node.elt)

        def run_setcomp(fr):
            cf = Frame(fr)
            out = set()
            for _ in drive(fr, cf, first(fr)):
                st.charge(cost)
                try:
                    out.add(elt(cf))
                except TypeError:
                    raise Fault("set elements must be ints, tuples or strings (not lists)") from None
                if len(out) > st.max_seq:
                    _check_len(st, len(out))
            return out
        return run_setcomp

    def e_DictComp(self, node, scopes):
        st = self.st
        drive, first, inner = self._comp(node, scopes)
        kf, vf = self.expr(node.key, inner), self.expr(node.value, inner)
        cost = 1 + _cost(node.key, node.value)

        def run_dictcomp(fr):
            cf = Frame(fr)
            out = {}
            for _ in drive(fr, cf, first(fr)):
                st.charge(cost)
                k = kf(cf)
                try:
                    out[k] = vf(cf)
                except TypeError:
                    raise Fault(f"{a_(k)} cannot be a dict key") from None
                if len(out) > st.max_seq:
                    _check_len(st, len(out))
            return out
        return run_dictcomp

    def e_GeneratorExp(self, node, scopes):
        st = self.st
        drive, first, inner = self._comp(node, scopes)
        elt, cost = self.expr(node.elt, inner), 1 + _cost(node.elt)

        def run_genexp(fr):
            cf = Frame(fr)
            src = first(fr)                     # Python evaluates the first iterable at once

            def gen():
                for _ in drive(fr, cf, src):
                    st.charge(cost)
                    yield elt(cf)
            return gen()
        return run_genexp


# ------------------------------------------------------------------ the machine
def validate_output(x):
    """The output as a list of lists of ints, or OutputError(kind ShapeError or ValueError)."""
    if type(x) is _ND or (type(x) in (list, tuple) and x and (type(x[0]) is _ND or (type(x[0]) in (list, tuple)
                                                                                   and x[0] and
                                                                                   isinstance(x[0][0], NPX.np.generic)))):
        x = NPX.output(x)
    if type(x) not in (list, tuple):
        raise OutputError("ShapeError", f"transform returned {a_(x)}, not a grid (a list of rows)")
    if not 1 <= len(x) <= MAX_OUT:
        raise OutputError("ShapeError", f"the output has {len(x)} rows; it must have 1 to {MAX_OUT}")
    w, rows = None, []
    for i, row in enumerate(x):
        if type(row) not in (list, tuple):
            raise OutputError("ShapeError", f"output row {i} is {a_(row)}, not a list of ints")
        if w is None:
            w = len(row)
            if not 1 <= w <= MAX_OUT:
                raise OutputError("ShapeError", f"the output has {w} columns; it must have 1 to {MAX_OUT}")
        elif len(row) != w:
            raise OutputError("ShapeError", f"output rows have different lengths ({w} and {len(row)}): not "
                              "rectangular")
        for j, v in enumerate(row):
            if type(v) is not int:
                raise OutputError("ValueError", f"output cell ({i}, {j}) is {a_(v)}, not an int 0-9")
            if not 0 <= v <= 9:
                raise OutputError("ValueError", f"output cell ({i}, {j}) is {v}, outside 0-9")
        rows.append(list(row))
    return rows


def check_input(grid):
    """The input grid as a fresh list of lists of ints (any ints), or ValueError."""
    if type(grid) not in (list, tuple) or not grid or len(grid) > P.MAX_DIM:
        raise ValueError("input must be a non-empty list of rows")
    out, w = [], None
    for row in grid:
        if type(row) not in (list, tuple) or not row or len(row) > P.MAX_DIM:
            raise ValueError("input rows must be non-empty lists")
        if w is None:
            w = len(row)
        elif len(row) != w:
            raise ValueError("input is not rectangular")
        r = [int(v) for v in row]
        if any(type(v) is bool for v in row):
            raise ValueError("input cells must be ints")
        out.append(r)
    return out


class Machine:
    """Compiles a checked program once; `run(grid)` executes transform(grid) with fresh state."""

    def __init__(self, checked, limits=None):
        self.checked = checked
        self.limits = limits or Limits()
        self.st = State(self.limits)
        tree = checked.tree
        names = set()
        for s in tree.body:
            if isinstance(s, ast.FunctionDef):
                names.add(s.name)
            elif isinstance(s, ast.Assign):
                for t in s.targets:
                    names |= L._target_names(t)
        self.module_names = names
        comp = Compiler(self.st, names)
        self.top = [comp.stmt(s, []) for s in tree.body]

    def set_limits(self, limits):
        self.limits = limits
        st = self.st
        st.max_steps, st.max_depth = limits.max_steps, limits.max_depth
        st.max_seq, st.max_int = limits.max_seq, limits.max_int

    def run(self, grid):
        """(output grid, steps). Raises StepLimit, Timeout, Fault or OutputError."""
        st = self.st
        st.reset()
        g = check_input(grid)
        module = Frame(None)
        try:
            for f in self.top:
                f(module)
            tf = st.globals.get("transform")
            if type(tf) is not UserFunction:
                raise Fault("transform is not a function")
            out = tf.invoke([g], {})
        except Fault as e:
            e.line = e.line or st.line
            raise
        except (StepLimit, Timeout):
            raise
        except RecursionError:
            raise Fault("calls or values nested too deeply", st.line) from None
        except MemoryError:
            raise Fault("out of memory (the program builds too much data)", st.line) from None
        except Exception as e:                            # noqa: BLE001 (any other runtime failure of the program)
            raise Fault(f"{type(e).__name__}: {str(e)[:160]}", st.line) from None
        return validate_output(out), st.steps


def ensure_recursion(limit=100000):
    if sys.getrecursionlimit() < limit:
        sys.setrecursionlimit(limit)
