"""How many function-valued entries of at most three nodes can a search of this experiment hold? An upper count.

Nothing is searched and no example is generated. The count uses only: the function-valued leaf names of the library
and their numbers of parameters (read from the code objects of the loaded library text), the blocks of C offered
as function-valued leaves, the 28 named constants and their tags, and the annotations of each target's parameters.

A function made by one of the seven retained operations has at least three nodes. At three nodes its arguments are
leaves. With the arity rule of the protocol, the applications that can be made are:
    compose(outer, inner)      both leaves with exactly one parameter
    lbind(function, fixed)     a leaf with at least two parameters, any data leaf
    rbind(function, fixed)     the same
    matcher(function, target)  a leaf with exactly one parameter, any data leaf
    power(function, n)         a leaf with exactly one parameter, an integer-tagged leaf
(chain and fork take three function arguments and have four nodes.)

Two counts are given for every target, each of which can only be larger than the truth.
Under the annotation premise:
  - no name is hidden (hiding a family removes leaves);
  - a parameter of the target annotated as a function is counted as a one-parameter leaf AND as a two-parameter leaf;
  - every other parameter counts as a data leaf and as an integer-tagged leaf.
Unconditional (asked for by the independent review, so that nothing rests on where a function value can appear):
  - no name is hidden;
  - EVERY parameter of the target is counted at once as a function leaf of one parameter, as one of two or more,
    as a data leaf and as an integer-tagged leaf.
The protocol uses the unconditional count.

    python structural_function_bound.py <out.json>          Author: Chimdi Walter Ndubuisi
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blocks_c as B          # noqa: E402  (also runs the hash check of the frozen files)
import dslx                   # noqa: E402
import presets_bl as P        # noqa: E402


def fixed_arity(f):
    """Number of positional parameters of a function with a fixed signature; None otherwise."""
    code = getattr(f, "__code__", None)
    if code is None or code.co_flags & 0x0C or f.__defaults__ or code.co_kwonlyargcount:
        return None
    return code.co_argcount


def count(one, two_or_more, data, integers, leaves):
    made = dict(compose=one * one, lbind=two_or_more * data, rbind=two_or_more * data, matcher=one * data,
                power=one * integers)
    return dict(function_valued_leaves=leaves, made_at_three_nodes=made, total=leaves + sum(made.values()))


def main(argv):
    lib = dslx.load()
    ns = dslx.full_ns()
    names = list(lib["fn_leaf_names"])
    ar = collections.Counter(fixed_arity(ns[n]) for n in names)
    if None in ar:
        raise SystemExit("a function-valued leaf of the library has no fixed signature")
    lib_one, lib_more = ar[1], sum(v for k, v in ar.items() if k >= 2)
    blocks = B.namespace()
    bar = collections.Counter(fixed_arity(blocks[b]) for b in B.function_leaf_names())
    if None in bar:
        raise SystemExit("a block offered as a function-valued leaf has no fixed signature")
    c_one, c_more = bar[1], sum(v for k, v in bar.items() if k >= 2)
    consts = [lib["consts"][c] for c in lib["const_names"]]
    n_const, n_int = len(consts), sum(dslx.tag(v) == "I" for v in consts)
    roster = list(P.STRATUM_SHORT) + list(P.STRATUM_LONGER)
    rows, worst = {}, dict(L=(0, None), C=(0, None), L_unconditional=(0, None), C_unconditional=(0, None))
    for name in roster:
        anns = [a for _, a in lib["sigs"][name]]
        fn = sum(a in ("Callable", "?") for a in anns)
        dat = len(anns) - fn
        l_row = count(lib_one + fn, lib_more + fn, n_const + dat, n_int + dat, len(names) + fn)
        c_row = count(c_one + fn, c_more + fn, n_const + len(B.CONSTANTS) + dat, n_int + dat, len(B.function_leaf_names()) + fn)
        k = len(anns)
        l_all = count(lib_one + k, lib_more + k, n_const + k, n_int + k, len(names) + k)
        c_all = count(c_one + k, c_more + k, n_const + len(B.CONSTANTS) + k, n_int + k, len(B.function_leaf_names()) + k)
        rows[name] = dict(parameters=anns, L=l_row, C=c_row, L_unconditional=l_all, C_unconditional=c_all)
        for key, r in (("L", l_row), ("C", c_row), ("L_unconditional", l_all), ("C_unconditional", c_all)):
            if r["total"] > worst[key][0]:
                worst[key] = (r["total"], name)
    body = dict(author="Chimdi Walter Ndubuisi", what="upper count from signatures and leaf lists; nothing searched; not a result",
                library_function_valued_leaves=dict(names=len(names), by_parameters={str(k): v for k, v in sorted(ar.items())}),
                blocks_offered_as_leaves=dict(names=len(B.function_leaf_names()), by_parameters={str(k): v for k, v in sorted(bar.items())}),
                named_constants=n_const, integer_constants=n_int, roster=len(roster),
                largest_total_over_L=dict(total=worst["L"][0], target=worst["L"][1]),
                largest_total_over_C=dict(total=worst["C"][0], target=worst["C"][1]),
                largest_unconditional_total_over_L=dict(total=worst["L_unconditional"][0], target=worst["L_unconditional"][1]),
                largest_unconditional_total_over_C=dict(total=worst["C_unconditional"][0], target=worst["C_unconditional"][1]),
                cap_proposed=16000,
                cap_in_presets=P.MAX_FN, per_target=rows)
    print(json.dumps({k: v for k, v in body.items() if k != "per_target"}, indent=1))
    print("worst L row:", json.dumps(rows[worst["L"][1]]["L"]), rows[worst["L"][1]]["parameters"])
    print("worst C row:", json.dumps(rows[worst["C"][1]]["C"]), rows[worst["C"][1]]["parameters"])
    if argv:
        with open(argv[0], "x") as fh:
            json.dump(body, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
