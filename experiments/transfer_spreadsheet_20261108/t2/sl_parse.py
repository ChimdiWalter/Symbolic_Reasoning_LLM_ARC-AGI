"""Reader for SyGuS-IF programming-by-example files (string tracks, format versions 1 and 2).

Returns the function signature, the literals of its grammar (the task's own constants) and the examples given as
`(constraint (= (f a1 ... an) out))`. String literals use the SMT-LIB rule that "" inside a literal is one quote
character; no other escape is decoded, so training and held examples are read the same way.
"""


class Str(str):
    """A string literal (distinct from a symbol)."""


def tokenize(text):
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == ";":
            while i < n and text[i] != "\n":
                i += 1
        elif c in "()":
            out.append(c)
            i += 1
        elif c.isspace():
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while True:
                if j >= n:
                    raise ValueError("unterminated string literal")
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        buf.append('"')
                        j += 2
                        continue
                    break
                buf.append(text[j])
                j += 1
            out.append(Str("".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()";':
                j += 1
            out.append(text[i:j])
            i = j
    return out


def parse(tokens):
    stack, cur = [], []
    for t in tokens:
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t)
    if stack:
        raise ValueError("unbalanced parentheses")
    return cur


def literal(x):
    """A constant term: string, integer (also written (- k)) or boolean. Raises ValueError otherwise."""
    if isinstance(x, Str):
        return str(x)
    if isinstance(x, list) and len(x) == 2 and x[0] == "-" and isinstance(x[1], str) and x[1].isdigit():
        return -int(x[1])
    if isinstance(x, str):
        if x.isdigit():
            return int(x)
        if x in ("true", "false"):
            return x == "true"
    raise ValueError(f"not a literal: {x!r}")


def _walk_literals(node, strs, ints):
    if isinstance(node, Str):
        strs.add(str(node))
    elif isinstance(node, list):
        if len(node) == 2 and node[0] == "-" and isinstance(node[1], str) and node[1].isdigit():
            ints.add(-int(node[1]))
            return
        for x in node:
            _walk_literals(x, strs, ints)
    elif isinstance(node, str) and node.isdigit():
        ints.add(int(node))


def read_sl(text):
    forms = parse(tokenize(text))
    fun = None
    examples, other = [], 0
    for f in forms:
        if not isinstance(f, list) or not f:
            continue
        if f[0] == "synth-fun":
            name, params, ret = f[1], f[2], f[3]
            strs, ints = set(), set()
            _walk_literals(f[4:], strs, ints)
            fun = {"name": name, "args": [[p[0], p[1]] for p in params], "ret": ret,
                   "str_consts": sorted(strs), "int_consts": sorted(ints)}
        elif f[0] == "constraint":
            c = f[1]
            try:
                if not (isinstance(c, list) and len(c) == 3 and c[0] == "=" and fun is not None):
                    raise ValueError("constraint is not an input-output equation")
                lhs, rhs = c[1], c[2]
                if isinstance(lhs, list) and lhs and lhs[0] == fun["name"]:
                    call, out = lhs, rhs
                elif isinstance(rhs, list) and rhs and rhs[0] == fun["name"]:
                    call, out = rhs, lhs
                else:
                    raise ValueError("constraint does not call the function")
                examples.append([[literal(a) for a in call[1:]], literal(out)])
            except ValueError:
                other += 1
    if fun is None:
        raise ValueError("no synth-fun")
    fun["non_example_constraints"] = other
    return fun, examples
