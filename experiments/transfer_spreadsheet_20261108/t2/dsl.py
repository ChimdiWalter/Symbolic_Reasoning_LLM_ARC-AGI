"""The static language: the SyGuS-Comp string grammar (SLIA track) without conditionals, and its bottom-up
enumerator with observational equivalence (the conventions of the list study's enumerator,
experiments/capability_growth_20261027/cgrow/u3/listdsl.py).

Types: S = string, I = integer. Leaves (cost 1): the task's arguments, the string and integer constants of the
task's own SyGuS grammar, and any constructed constant. Operations (cost 1 each; SMT-LIB 2.6 semantics):
  concat(S,S)->S; replace(S,S,S)->S (first occurrence; empty pattern prefixes); at(S,I)->S; itos(I)->S;
  substr(S,I,I)->S (start, length); add(I,I)->I; sub(I,I)->I; len(S)->I; stoi(S)->I; indexof(S,S,I)->I
  plus any constructed piece, a unary operation S->S (t2/pieces.py).
The grammar's ite and Boolean operations are left out in every arm: with two or three examples, a conditional can
memorise each example.

search(): programs are enumerated by size. A bank value is the tuple of a program's values on the training
examples; programs with identical value tuples are merged (observational equivalence). Budget = operation
executions (one per example, or one when every argument is constant). A value is valid when strings have at most
LMAX characters and integers at most IMAX in absolute value (search only; evaluation of a found program on new
inputs has no length limit). The answer is the first program whose values equal the training outputs.
"""
import itertools
import time

IMAX = 10 ** 9


class Undefined(Exception):
    pass


def _substr(s, i, n):
    if i < 0 or i >= len(s) or n <= 0:
        return ""
    return s[i:i + n]


def _replace(s, t, u):
    if t == "":
        return u + s
    return s.replace(t, u, 1)


def _at(s, i):
    return s[i] if 0 <= i < len(s) else ""


def _itos(i):
    return str(i) if i >= 0 else ""


def _stoi(s):
    return int(s) if s and s.isascii() and s.isdigit() else -1


def _indexof(s, t, i):
    if i < 0 or i > len(s):
        return -1
    return s.find(t, i)


BASE_OPS = (
    ("concat", ("S", "S"), "S", lambda a, b: a + b),
    ("replace", ("S", "S", "S"), "S", _replace),
    ("at", ("S", "I"), "S", _at),
    ("itos", ("I",), "S", _itos),
    ("substr", ("S", "I", "I"), "S", _substr),
    ("add", ("I", "I"), "I", lambda a, b: a + b),
    ("sub", ("I", "I"), "I", lambda a, b: a - b),
    ("len", ("S",), "I", len),
    ("stoi", ("S",), "I", _stoi),
    ("indexof", ("S", "S", "I"), "I", _indexof),
)
OPFN = {name: fn for name, _, _, fn in BASE_OPS}


def _compositions(total, k):
    if k == 1:
        yield (total,)
        return
    for first in range(1, total - k + 2):
        for rest in _compositions(total - first, k - 1):
            yield (first,) + rest


class Language:
    """Base operations plus constructed pieces (unary S->S callables) and constructed constants."""

    def __init__(self, pieces=(), consts=()):
        self.pieces = list(pieces)          # [(name, callable)]
        self.consts = list(consts)          # constructed string constants
        self.ops = list(BASE_OPS) + [(name, ("S",), "S", fn) for name, fn in self.pieces]
        self.fn = dict(OPFN)
        self.fn.update({name: fn for name, fn in self.pieces})


def leaves(task_view):
    """(type, label, per-example values, constant?) for the task's arguments and grammar constants."""
    out = []
    for j, t in enumerate(task_view["arg_types"]):
        out.append(("S" if t == "String" else "I", ("arg", j), tuple(x[j] for x in task_view["inputs"]), False))
    return out


def search(task_view, lang, budget, cpu_cap, max_size=30, keep_bank=False):
    """task_view: {"arg_types", "inputs" (training inputs), "outputs" (training outputs), "str_consts",
    "int_consts"}. Returns dict(fit, program, size, calls, cpu_s, stop, bank)."""
    t0 = time.process_time()
    ys = tuple(task_view["outputs"])
    n = len(ys)
    lens = [len(v) for x in task_view["inputs"] for v in x if isinstance(v, str)] + [len(y) for y in ys]
    lmax = 2 * max(lens + [1]) + 5
    seen, pools, order = set(), {}, []
    calls, tick, stop, fit = 0, 0, None, None

    def add(vals, tp, tree, sz, const):
        nonlocal fit
        key = (tp, vals)
        if key in seen:
            return False
        seen.add(key)
        pools.setdefault((sz, tp), []).append((vals, tree, const))
        if keep_bank and tp == "S":
            order.append((vals, tree, sz))
        if tp == "S" and vals == ys and fit is None:
            fit = (tree, sz)
            return True
        return False

    for tp, lab, vals, const in leaves(task_view):
        if add(vals, tp, lab, 1, const):
            stop = "fit"
    for c in task_view["str_consts"] + list(lang.consts):
        if add((c,) * n, "S", ("cs", c), 1, True):
            stop = "fit"
    for c in task_view["int_consts"]:
        add((c,) * n, "I", ("ci", c), 1, True)
    sz = 1
    for sz in range(2, max_size + 1):
        if stop:
            break
        for name, argtypes, rettype, fn in lang.ops:
            k = len(argtypes)
            if sz - 1 < k:
                continue
            for parts in _compositions(sz - 1, k):
                lists = [pools.get((si, tp), ()) for si, tp in zip(parts, argtypes)]
                if not all(lists):
                    continue
                for combo in itertools.product(*lists):
                    if calls >= budget:
                        stop = "budget"
                        break
                    tick += 1
                    if tick & 1023 == 0 and time.process_time() - t0 > cpu_cap:
                        stop = "cpu_cap"
                        break
                    const = all(c[2] for c in combo)
                    try:
                        if const:
                            calls += 1
                            v = fn(*[c[0][0] for c in combo])
                            vals = (v,) * n
                        else:
                            calls += n
                            vals = tuple(fn(*[c[0][i] for c in combo]) for i in range(n))
                    except (Undefined, ValueError, IndexError, OverflowError):
                        continue
                    if rettype == "S":
                        if any(len(v) > lmax for v in vals):
                            continue
                    elif any(abs(v) > IMAX for v in vals):
                        continue
                    if add(vals, rettype, (name,) + tuple(c[1] for c in combo), sz, const):
                        stop = "fit"
                        break
                if stop:
                    break
            if stop:
                break
    return {"fit": fit is not None, "program": fit[0] if fit else None, "size": fit[1] if fit else None,
            "calls": calls, "cpu_s": round(time.process_time() - t0, 4), "stop": stop or "max_size",
            "max_size_reached": sz, "bank": order if keep_bank else None}


def evaluate(tree, args, lang):
    """Value of a program tree on one input (list of argument values). Raises Undefined on failure."""
    head = tree[0]
    if head == "arg":
        return args[tree[1]]
    if head in ("cs", "ci"):
        return tree[1]
    fn = lang.fn[head]
    vals = [evaluate(t, args, lang) for t in tree[1:]]
    try:
        return fn(*vals)
    except (ValueError, IndexError, OverflowError) as e:
        raise Undefined() from e


def show(tree):
    head = tree[0]
    if head == "arg":
        return f"x{tree[1]}"
    if head in ("cs", "ci"):
        return repr(tree[1])
    return f"{head}(" + ", ".join(show(t) for t in tree[1:]) + ")"


def uses(tree, name):
    if tree[0] == name:
        return True
    if tree[0] in ("arg", "cs", "ci"):
        return False
    return any(uses(t, name) for t in tree[1:])


def substitute(tree, old, new):
    """Replace operation name old by new everywhere in the tree."""
    if tree[0] in ("arg", "cs", "ci"):
        return tree
    return ((new if tree[0] == old else tree[0]),) + tuple(substitute(t, old, new) for t in tree[1:])
