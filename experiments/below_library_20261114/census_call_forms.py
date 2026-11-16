"""The exact forms in which the library's source uses Python built-ins, subscripts and displays. Parsed only.

For a block set "one block for each construct the source uses", the constructs have to be listed exactly: a
built-in with its number of arguments and its keywords, each kind of subscript and slice, each kind of display.

    python3 -I census_call_forms.py <out.json>            Author: Chimdi Walter Ndubuisi
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
    forms, subs, disp, meth = (collections.Counter() for _ in range(4))
    detail = collections.defaultdict(collections.Counter)
    for fname, f in fns.items():
        params = {a.arg for a in f.args.args}
        for n in ast.walk(f):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                fn = n.func.id
                if fn == "isinstance":
                    detail["type tested by isinstance"][ast.unparse(n.args[1])] += 1
                if fn == "next":
                    inner = n.args[0]
                    detail["argument of next"]["iter(...)" if isinstance(inner, ast.Call) and getattr(inner.func, "id", "") == "iter"
                                               else ast.unparse(inner)[:60]] += 1
                if fn in ("max", "min", "sorted") and n.keywords:
                    detail["keywords of " + fn][", ".join("%s=%s" % (k.arg, ast.unparse(k.value)[:20]) for k in n.keywords)] += 1
                if fn == "type":
                    detail["operations that use type(...)"][fname] += 1
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
                detail["products"][ast.unparse(n)[:50]] += 1
            if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.BitOr, ast.BitAnd)):
                detail["set unions and intersections"][ast.unparse(n)[:50]] += 1
            if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice):
                detail["slices"][ast.unparse(n)[:44]] += 1
            if isinstance(n, ast.Lambda):
                detail["lambdas"][ast.unparse(n)[:70]] += 1
            if isinstance(n, ast.BoolOp):
                detail["Boolean operators"]["%s of %d" % (type(n.op).__name__, len(n.values))] += 1
            if isinstance(n, ast.Dict):
                detail["operations with a dict display"][fname] += 1
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and hasattr(builtins, n.func.id) and n.func.id not in fns and n.func.id not in params:
                star = any(isinstance(a, ast.Starred) for a in n.args)
                forms["%s(%d positional%s%s)" % (n.func.id, len(n.args), ", starred" if star else "", "".join(", %s=" % k.arg for k in n.keywords))] += 1
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                meth[n.func.attr] += 1
            if isinstance(n, ast.Subscript):
                sl = n.slice
                if isinstance(sl, ast.Slice):
                    subs["slice [%s:%s%s]" % ("a" if sl.lower else "", "b" if sl.upper else "", ":c" if sl.step else "")] += 1
                elif isinstance(sl, ast.Constant):
                    subs["index [%r]" % sl.value] += 1
                else:
                    subs["index [expression]"] += 1
            if isinstance(n, ast.Tuple) and isinstance(n.ctx, ast.Load):
                disp["tuple display of %d" % len(n.elts)] += 1
            if isinstance(n, ast.Set):
                disp["set display of %d" % len(n.elts)] += 1
            if isinstance(n, ast.Dict):
                disp["dict display"] += 1
    body = dict(author="Chimdi Walter Ndubuisi", what="exact forms of built-in calls, subscripts and displays in the library's source; parsed, not executed",
                source_sha256=hashlib.sha256(raw).hexdigest(), builtin_call_forms=dict(sorted(forms.items())), subscripts=dict(subs.most_common()),
                displays=dict(disp.most_common()), methods_called_on_values=dict(meth.most_common()),
                details={k: dict(v.most_common()) for k, v in sorted(detail.items())})
    if argv:
        with open(argv[0], "x") as fh:
            json.dump(body, fh, indent=1, sort_keys=True)
            fh.write("\n")
    print("built-in call forms: %d; kinds of subscript: %d; kinds of display: %d" % (len(forms), len(subs), len(disp)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
