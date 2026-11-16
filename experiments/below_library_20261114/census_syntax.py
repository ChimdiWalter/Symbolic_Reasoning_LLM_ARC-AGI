"""Which Python constructs does the operation library's own source use? Parsed, nothing executed.

An inventory over all function bodies of arc-dsl's dsl.py: syntax node types, operators, built-in names, methods
called on values, and forms of comprehension. It is the factual basis for choosing building blocks "below the
library": a block set can be tied to what the source itself uses instead of to taste.

    python3 -I census_syntax.py <out.json>            Author: Chimdi Walter Ndubuisi
"""
import ast
import builtins
import collections
import hashlib
import json
import sys

SRC = "/path/to/repository/outputs/search_components/resources_20261026/github/arc-dsl/dsl.py"


def main(argv):
    raw = open(SRC, "rb").read()
    mod = ast.parse(raw.decode("utf-8"))
    fns = {n.name: n for n in mod.body if isinstance(n, ast.FunctionDef)}
    kinds, ops, methods, builtin_names, comp = (collections.Counter() for _ in range(5))
    users = collections.defaultdict(set)
    for name, f in fns.items():
        params = {a.arg for a in f.args.args}
        for n in ast.walk(f):
            k = type(n).__name__
            if isinstance(n, (ast.expr, ast.stmt, ast.comprehension)) and k not in ("Name", "Constant"):
                kinds[k] += 1
                users[k].add(name)
            if isinstance(n, (ast.BinOp, ast.UnaryOp)):
                ops[type(n.op).__name__] += 1
            if isinstance(n, ast.BoolOp):
                ops[type(n.op).__name__] += 1
            if isinstance(n, ast.Compare):
                for o in n.ops:
                    ops[type(o).__name__] += 1
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                methods[n.func.attr] += 1
            if isinstance(n, ast.Name) and hasattr(builtins, n.id) and n.id not in fns and n.id not in params:
                builtin_names[n.id] += 1
            if isinstance(n, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
                comp["%s, %d loop%s%s" % (type(n).__name__, len(n.generators), "" if len(n.generators) == 1 else "s",
                                          ", with a condition" if any(g.ifs for g in n.generators) else "")] += 1
    body = dict(author="Chimdi Walter Ndubuisi", what="syntax inventory of the operation library's source; parsed, not executed",
                source_sha256=hashlib.sha256(raw).hexdigest(), functions=len(fns),
                node_kinds={k: dict(uses=v, functions=len(users[k])) for k, v in kinds.most_common()},
                operators=dict(ops.most_common()), methods_called_on_values=dict(methods.most_common()),
                builtin_names=dict(builtin_names.most_common()), comprehension_forms=dict(comp.most_common()))
    if argv:
        with open(argv[0], "x") as fh:
            json.dump(body, fh, indent=1, sort_keys=True)
            fh.write("\n")
    for k in ("node_kinds", "operators", "methods_called_on_values", "builtin_names", "comprehension_forms"):
        print(k, body[k] if k != "node_kinds" else {a: (b["uses"], b["functions"]) for a, b in body[k].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
