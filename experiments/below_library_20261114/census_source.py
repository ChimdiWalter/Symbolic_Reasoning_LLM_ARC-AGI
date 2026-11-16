"""How large is each library operation's own definition? A census of the library's source. Nothing is executed.

The operation library (arc-dsl by Michael Hodel, MIT licence) is written in Python. This script PARSES its source
with the `ast` module and counts, for every operation, how much program its own definition is: the number of
expression nodes of its body, the number of statements, whether it needs loops or branches, how many comprehensions
and lambdas it has, which Python built-ins it uses and which other library operations it calls. "Inlined" size adds
the size of every library operation it calls, at each call, down to operations that call none: an upper bound on
the size of the operation when no library operation is available as a building block.

Two sizes are given. `expression_nodes` counts every expression node of the Python syntax tree. `nodes` counts as
the searches of this project count: an application is one node whatever it applies, so the name of a called function
is not a node of its own (`next(iter(container))` is 3 nodes, `not b` is 2).

These sizes are upper bounds on description length in the language the library is written in. They say nothing
about whether a shorter program exists, and nothing was searched.

    python3 -I census_source.py <out.json>          (-I: the source is a download and is only parsed)

Author: Chimdi Walter Ndubuisi
"""
import ast
import builtins
import hashlib
import json
import sys

SRC = "/path/to/repository/outputs/search_components/resources_20261026/github/arc-dsl/dsl.py"


def body_without_docstring(f):
    b = f.body
    if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) and isinstance(b[0].value.value, str):
        b = b[1:]
    return b


def main(argv):
    raw = open(SRC, "rb").read()
    mod = ast.parse(raw.decode("utf-8"))
    fns = {n.name: n for n in mod.body if isinstance(n, ast.FunctionDef)}
    rows = {}
    for name, f in fns.items():
        body = body_without_docstring(f)
        nodes = [n for s in body for n in ast.walk(s)]
        exprs = [n for n in nodes if isinstance(n, ast.expr)]
        stmts = [n for n in nodes if isinstance(n, ast.stmt)]
        names = [n.id for n in nodes if isinstance(n, ast.Name)]
        params = {a.arg for a in f.args.args}
        lib_calls = [x for x in names if x in fns and x != name and x not in params]
        called_names = sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) for n in nodes)
        rows[name] = dict(
            parameters=len(f.args.args), statements=len(stmts), expression_nodes=len(exprs) + sum(isinstance(n, ast.comprehension) for n in nodes),
            nodes=len(exprs) + sum(isinstance(n, ast.comprehension) for n in nodes) - called_names,
            one_return_expression=len(body) == 1 and isinstance(body[0], ast.Return),
            loops=sum(isinstance(n, (ast.For, ast.While)) for n in nodes), branches=sum(isinstance(n, ast.If) for n in nodes),
            conditional_expressions=sum(isinstance(n, ast.IfExp) for n in nodes),
            comprehensions=sum(isinstance(n, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)) for n in nodes),
            lambdas=sum(isinstance(n, ast.Lambda) for n in nodes), type_tests=names.count("isinstance"),
            calls_itself=name in names and name not in params,
            library_operations_called=sorted(set(lib_calls)), library_calls=len(lib_calls),
            builtins_used=sorted({x for x in names if hasattr(builtins, x) and x not in fns and x not in params}),
            returns=ast.unparse(f.returns) if f.returns is not None else None)
    memo = {}

    def inlined(name, key, stack=()):
        if (name, key) in memo:
            return memo[(name, key)]
        if name in stack:
            return rows[name][key]                               # recursion: counted once
        r = rows[name]
        body = body_without_docstring(fns[name])
        params = {a.arg for a in fns[name].args.args}
        calls = [n.id for s in body for n in ast.walk(s) if isinstance(n, ast.Name) and n.id in fns and n.id != name and n.id not in params]
        total = r[key] + sum(inlined(c, key, stack + (name,)) for c in calls)
        memo[(name, key)] = total
        return total
    for name in rows:
        rows[name]["expression_nodes_inlined"] = inlined(name, "expression_nodes")
        rows[name]["nodes_inlined"] = inlined(name, "nodes")
    sizes = sorted(r["expression_nodes"] for r in rows.values())
    inl = sorted(r["expression_nodes_inlined"] for r in rows.values())
    nd = sorted(r["nodes"] for r in rows.values())
    ndi = sorted(r["nodes_inlined"] for r in rows.values())
    q = lambda xs, p: xs[min(len(xs) - 1, int(p * len(xs)))]
    body = dict(author="Chimdi Walter Ndubuisi", what="census of the operation library's source; parsed, not executed; sizes are upper bounds on description length",
                source=SRC, source_sha256=hashlib.sha256(raw).hexdigest(), operations=len(rows),
                one_return_expression=sum(r["one_return_expression"] for r in rows.values()),
                with_a_loop=sum(r["loops"] > 0 for r in rows.values()), with_a_branch_statement=sum(r["branches"] > 0 for r in rows.values()),
                with_a_type_test=sum(r["type_tests"] > 0 for r in rows.values()),
                with_a_comprehension=sum(r["comprehensions"] > 0 for r in rows.values()), with_a_lambda=sum(r["lambdas"] > 0 for r in rows.values()),
                calling_other_library_operations=sum(r["library_calls"] > 0 for r in rows.values()),
                expression_nodes=dict(least=sizes[0], quartile_1=q(sizes, 0.25), median=q(sizes, 0.5), quartile_3=q(sizes, 0.75), most=sizes[-1]),
                expression_nodes_inlined=dict(least=inl[0], quartile_1=q(inl, 0.25), median=q(inl, 0.5), quartile_3=q(inl, 0.75), most=inl[-1]),
                nodes=dict(least=nd[0], quartile_1=q(nd, 0.25), median=q(nd, 0.5), quartile_3=q(nd, 0.75), most=nd[-1]),
                nodes_inlined=dict(least=ndi[0], quartile_1=q(ndi, 0.25), median=q(ndi, 0.5), quartile_3=q(ndi, 0.75), most=ndi[-1]),
                operations_with_at_most_n_nodes={str(n): sum(s <= n for s in nd) for n in (2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 30, 50)},
                operations_with_at_most_n_nodes_inlined={str(n): sum(s <= n for s in ndi) for n in (2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 30, 50)},
                operations_with_at_most_n_expression_nodes={str(n): sum(s <= n for s in sizes) for n in (3, 4, 5, 6, 8, 10, 12, 15, 20, 30, 50)},
                operations_with_at_most_n_inlined_nodes={str(n): sum(s <= n for s in inl) for n in (3, 4, 5, 6, 8, 10, 12, 15, 20, 30, 50)},
                builtins_used_by_how_many={b: sum(b in r["builtins_used"] for r in rows.values())
                                           for b in sorted({b for r in rows.values() for b in r["builtins_used"]})},
                per_operation=rows)
    if argv:
        with open(argv[0], "x") as fh:
            json.dump(body, fh, indent=1, sort_keys=True)
            fh.write("\n")
    print(json.dumps({k: v for k, v in body.items() if k not in ("per_operation", "author", "what", "source")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
