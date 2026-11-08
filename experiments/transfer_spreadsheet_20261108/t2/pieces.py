"""The structure space from which a missing piece is built: spreadsheet text operations in the style of the published
FlashFill and BlinkFill position and token language (field of a split, k-th token of a character class, text before
or after a delimiter, text between two delimiters, keeping or deleting a character class, replacing every
occurrence, case changes, initials), each a unary operation S -> S once its parameters are fixed.

A piece is one structure with all parameters fixed. consistent(pairs, delims) lists, in the canonical order below,
every piece that maps each source string of the hole pairs to its target string exactly. A constant hole (the same
non-empty target on every example) is filled by a constructed constant instead.

Canonical order (fixed in development, before the freeze): structures in the order of STRUCTURES; within one, the
parameters in the order of their value lists; delimiters in the order of delims(task) (the fixed list, then the
task's own one- to four-character constants not already in it).
"""
import re

from t2.dsl import Undefined

FIXED_DELIMS = (" ", ",", ".", "-", "/", "_", "@", ":", ";", "(", ")", "|", "=", "+", "#", "&", "*", "'", '"',
                "<", ">", "[", "]", "$", "%")
CLASSES = (("Alpha", r"[A-Za-z]+"), ("Digits", r"[0-9]+"), ("AlphaNum", r"[A-Za-z0-9]+"), ("Upper", r"[A-Z]+"),
           ("Lower", r"[a-z]+"), ("NonSpace", r"\S+"), ("Punct", r"[^A-Za-z0-9\s]+"))
CRE = {name: re.compile(rx) for name, rx in CLASSES}
FIELD_K = (1, 2, 3, 4, -1, -2, -3)
TOK_K = (1, 2, 3, -1, -2, -3)
OCC_K = (1, 2, -1)
CASES = ("upper", "lower", "title", "capitalize")
INIT_CLASSES = ("Alpha", "Upper", "NonSpace", "AlphaNum")
INIT_SEPS = ("", ".", " ", ". ", "-")


def delims(task_str_consts):
    extra = [c for c in task_str_consts if 1 <= len(c) <= 4 and c not in FIXED_DELIMS]
    return list(FIXED_DELIMS) + sorted(set(extra), key=lambda c: (len(c), c))


def _pick(items, k):
    i = k - 1 if k > 0 else len(items) + k
    if not 0 <= i < len(items):
        raise Undefined()
    return items[i]


def _occ(x, d, k):
    """Start index of the k-th occurrence of d (k = -1: last)."""
    if k == -1:
        i = x.rfind(d)
    else:
        i, start = -1, 0
        for _ in range(k):
            i = x.find(d, start)
            if i < 0:
                break
            start = i + len(d)
    if i < 0:
        raise Undefined()
    return i


def _case(s, m):
    if m == "upper":
        return s.upper()
    if m == "lower":
        return s.lower()
    if m == "title":
        return s.title()
    return s[:1].upper() + s[1:].lower()


def f_field(x, d, k):
    return _pick(x.split(d), k)


def f_tok(x, c, k):
    return _pick(CRE[c].findall(x), k)


def f_before(x, d, k):
    return x[:_occ(x, d, k)]


def f_after(x, d, k):
    return x[_occ(x, d, k) + len(d):]


def f_between(x, d1, d2):
    i = x.find(d1)
    if i < 0:
        raise Undefined()
    j = x.find(d2, i + len(d1))
    if j < 0:
        raise Undefined()
    return x[i + len(d1):j]


def f_keep(x, c):
    return "".join(CRE[c].findall(x))


def f_drop(x, c):
    return CRE[c].sub("", x)


def f_replace_all(x, d, e):
    return x.replace(d, e)


def f_case(x, m):
    return _case(x, m)


def f_initials(x, c, s, trail):
    toks = CRE[c].findall(x)
    if not toks:
        raise Undefined()
    return s.join(t[0] for t in toks) + (s if trail else "")


def f_trim(x):
    return x.strip()


def f_collapse(x):
    return " ".join(x.split())


INNER = {"field": f_field, "tok": f_tok, "before": f_before, "after": f_after, "between": f_between}


def f_casewrap(x, m, inner, *p):
    return _case(INNER[inner](x, *p), m)


def _inner_params(D):
    for k in FIELD_K:
        for d in D:
            yield ("field", d, k)
    for c, _ in CLASSES:
        for k in TOK_K:
            yield ("tok", c, k)
    for k in OCC_K:
        for d in D:
            yield ("before", d, k)
    for k in OCC_K:
        for d in D:
            yield ("after", d, k)
    for d1 in D:
        for d2 in D:
            yield ("between", d1, d2)


STRUCTURES = ("field", "tok", "before", "after", "between", "keep", "drop", "replace_all", "case", "initials",
              "trim", "collapse", "casewrap")
FN = {"field": f_field, "tok": f_tok, "before": f_before, "after": f_after, "between": f_between, "keep": f_keep,
      "drop": f_drop, "replace_all": f_replace_all, "case": f_case, "initials": f_initials, "trim": f_trim,
      "collapse": f_collapse, "casewrap": f_casewrap}


def all_pieces(D):
    """Every piece in canonical order, as (structure, params)."""
    for p in _inner_params(D):
        yield (p[0], p[1:])
    for c, _ in CLASSES:
        yield ("keep", (c,))
    for c, _ in CLASSES:
        yield ("drop", (c,))
    for d in D:
        for e in [""] + list(D):
            if e != d:
                yield ("replace_all", (d, e))
    for m in CASES:
        yield ("case", (m,))
    for c in INIT_CLASSES:
        for s in INIT_SEPS:
            for trail in (False, True):
                yield ("initials", (c, s, trail))
    yield ("trim", ())
    yield ("collapse", ())
    for m in CASES:
        for p in _inner_params(D):
            yield ("casewrap", (m,) + p)


def name_of(piece):
    st, params = piece
    return st + "(" + ",".join(repr(p) for p in params) + ")"


def fn_of(piece):
    st, params = piece
    f = FN[st]

    def g(x, f=f, params=params):
        if not isinstance(x, str):
            raise Undefined()
        try:
            return f(x, *params)
        except IndexError as e:
            raise Undefined() from e
    return g


def apply(piece, x):
    return fn_of(piece)(x)


def consistent(pairs, D, limit=None):
    """Pieces mapping every (source, target) pair exactly, in canonical order."""
    out = []
    if not pairs:
        return out
    for piece in all_pieces(D):
        f = fn_of(piece)
        ok = True
        for s, t in pairs:
            try:
                if f(s) != t:
                    ok = False
                    break
            except Undefined:
                ok = False
                break
        if ok:
            out.append(piece)
            if limit and len(out) >= limit:
                break
    return out
