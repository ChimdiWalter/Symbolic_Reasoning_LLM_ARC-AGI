"""Gate before any search (section 6 of the protocol): do the examples exercise the operation?
Author: Chimdi Walter Ndubuisi

For a set of examples of one consumer: the lesioned consumer must fail (NameError on the missing operation); the
intact consumer must pass; the true operation bound through the same mechanism must pass; and every trivial repair
must fail. A trivial repair replaces the call of X by one of its own arguments, or by a constant taken from the
examples' outputs (the required final outputs and X's own outputs); it "passes" when post(replacement) equals the
required final output on every example. The true operation is used here by the evaluator only.
"""
import frozen  # noqa: F401
import dslx
import consumers as C

L = dslx.load()


def required_outputs(X, post, argsets, env_full):
    """Final outputs of the intact consumer, by evaluating its text (the evaluator's job)."""
    text = C.consumer_text(X, post)
    params = L["sigs"][X]
    return [C.run_text(text, env_full, params, a) for a in argsets]


def run_lesioned(X, post, args, env_les):
    """Run the lesioned consumer on one example. Returns dict(failed, error_type, error_text, missing_name)."""
    text = C.consumer_text(X, post)
    try:
        v = C.run_text(text, env_les, L["sigs"][X], args)
        return dict(failed=False, value=v)
    except NameError as e:
        return dict(failed=True, error_type="NameError", error_text=str(e), missing_name=getattr(e, "name", None))
    except Exception as e:                                       # noqa: BLE001
        return dict(failed=True, error_type=type(e).__name__, error_text=str(e)[:300], missing_name=None)


def trivial_repairs(X, argsets, xouts, finals):
    """[(label, function args -> replacement value)] : own arguments and constants from the examples' outputs."""
    reps = []
    for j, (pn, _) in enumerate(L["sigs"][X]):
        reps.append(("arg:" + pn, (lambda a, j=j: a[j])))
    seen = set()
    for src, vals in (("final", finals), ("xout", xouts)):
        for v in vals:
            k = dslx.canon(v)
            if k not in seen:
                seen.add(k)
                reps.append(("const:%s:%d" % (src, len(seen)), (lambda a, v=v: v)))
    return reps


def check(X, post, argsets, env_les, env_full, post_fn_les):
    """Gate one set of examples. Returns dict(ok, failed=[reasons], trivial_passing=[labels], n)."""
    full = env_full[X]
    failed = []
    try:
        finals = required_outputs(X, post, argsets, env_full)
    except Exception as e:                                       # noqa: BLE001
        return dict(ok=False, failed=["intact consumer did not run: %s" % type(e).__name__], trivial_passing=[], n=len(argsets))
    xouts = [full(*a) for a in argsets]
    les = [run_lesioned(X, post, a, env_les) for a in argsets]
    if not all(r["failed"] and r["error_type"] == "NameError" and r["missing_name"] == X for r in les):
        failed.append("lesioned consumer does not fail on the missing operation on every example")
    env_true = dict(env_les)
    env_true[X] = full
    try:
        got = [C.run_text(C.consumer_text(X, post), env_true, L["sigs"][X], a) for a in argsets]
        if not all(C.same(g, f) for g, f in zip(got, finals)):
            failed.append("true operation bound in the lesioned library does not pass")
    except Exception as e:                                       # noqa: BLE001
        failed.append("true operation bound in the lesioned library raised %s" % type(e).__name__)
    passing = []
    for label, rep in trivial_repairs(X, argsets, xouts, finals):
        try:
            if all(C.same(C.apply_post(post_fn_les, rep(a)), f) for a, f in zip(argsets, finals)):
                passing.append(label)
        except Exception:                                        # noqa: BLE001
            pass
    if passing:
        failed.append("a trivial repair passes: " + ", ".join(passing))
    return dict(ok=not failed, failed=failed, trivial_passing=passing, n=len(argsets))
