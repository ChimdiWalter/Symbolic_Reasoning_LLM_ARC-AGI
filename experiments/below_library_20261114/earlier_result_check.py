"""The earlier result as a check (protocol, section 9). Author: Chimdi Walter Ndubuisi.

After a run, for every target of the output folder, the expression found by L4-36 is compared with the record of
the operations study for its second condition (X's whole family hidden; its search over its 36 examples with at most
four nodes over the library; `core_operations_20261113/full_out/<X>__b.json`, read only, never changed). Every
difference is listed with the facts that bear on its cause, each read or tested by a rule fixed here before any
all-roster outcome exists:
  examples:   are the first 36 of this experiment's 66 generator examples the 36 of the earlier study? The earlier
              study's own hash (sha256 of canonical text, first 16 hex digits) is recomputed on this experiment's
              examples, made again by the generator copy exactly as the setup pass makes them;
  hidden:     are the hidden names the same?
  input rule: did this experiment exclude the target, or count unusable generator examples (a container argument
              that holds a function; an output that is or holds a function)?
  bounded:    did either search end without exhausting its four nodes (a cap, the budget, the time, or the earlier
              study's function cap)?
  residual:   none of the above: same examples, same hidden names, both searches exhaustive. What remains is a
              difference in the searches themselves, declared in the protocol: a container never holds a function,
              the arity rule and its cap, and the order of first fits that follows from them.
Expressions are compared as text after the earlier study's parameter names are written x0, x1, ... in the order of
X's signature, as this experiment writes them. Nothing is searched; the generator is run once per target, under the
guard the setup pass uses.

Usage (from this folder): PYTHONHASHSEED=0 python -s -B earlier_result_check.py <outdir> <record.json>
"""
import hashlib
import json
import os
import re
import sys

import bl_frozen  # noqa: F401  (hash check of the frozen files, sys.path)
import dslx
import gen_bl
import guards_bl as G
import presets_bl as P

HERE = os.path.dirname(os.path.abspath(__file__))
EARLIER = os.path.join(bl_frozen.ROOT, bl_frozen.CORE_REL, "full_out")      # absolute: the same from a copy of this folder
EXHAUSTIVE_HERE = ("found", "size_limit_completed")
EXHAUSTIVE_EARLIER = ("found", "size_exhausted")


def earlier_hash(examples):
    """The operations study's examples_hash (core.py), on the first 36 examples given."""
    return hashlib.sha256("|".join(dslx.canon(tuple(a)) + "->" + dslx.canon(o) for a, o in examples).encode()).hexdigest()[:16]


def normalize(expr, params):
    if expr is None:
        return None
    for i, p in enumerate(params):
        expr = re.sub(r"\b%s\b" % re.escape(p), "x%d" % i, expr)
    return expr


def compare(X, rec, sigs):
    e_path = os.path.join(EARLIER, "%s__b.json" % X)
    e = json.load(open(e_path)) if os.path.exists(e_path) else None
    row = dict(target=X, status_here=rec.get("status"), reason_here=rec.get("reason"))
    if e is None:
        return dict(row, category="not compared: no earlier record")
    params = [p for p, _ in sigs.get(X, [])]
    row.update(status_earlier=e.get("status"), expr_earlier_text=e.get("expr"), expr_earlier=normalize(e.get("expr"), params),
               stop_earlier=e.get("stop"), hidden_same=sorted(e.get("hidden") or []) == sorted(rec.get("hidden") or []))
    if e.get("status") != "searched":
        return dict(row, category="not compared: excluded earlier", reason_earlier=e.get("reason"))
    oracle = (e.get("arms") or {}).get("oracle") or {}
    bounded_earlier = e.get("stop") not in EXHAUSTIVE_EARLIER or bool(oracle.get("function_cap_reached"))
    unusable = ((rec.get("setup") or {}).get("unusable_generator_examples") or {})
    row.update(bounded_earlier=bounded_earlier, unusable_here=unusable)
    try:
        g = G.call_checked(gen_bl.gen_examples, X, n_total=P.N_GEN)
        row["examples_same"] = (g["status"] == "ok" and len(g["examples"]) >= 36
                                and earlier_hash(g["examples"][:36]) == e.get("examples_sha"))
    except Exception as ex:                      # an ordinary error: the fact is unknown, never taken as "same"
        row["examples_same"] = None
        row["examples_error"] = "%s: %s" % (type(ex).__name__, ex)
    if rec.get("status") == "excluded":
        found_e = e.get("expr") is not None
        return dict(row, category="not compared: excluded here" + (" (the earlier study found one)" if found_e else ""),
                    reason_kind_here=rec.get("reason_kind"))
    s = (rec.get("searches") or {}).get("L4-36")
    if rec.get("status") != "done" or not s:
        return dict(row, category="not compared: incomplete here")
    here = s.get("expr")
    bounded_here = s.get("stop_class") not in EXHAUSTIVE_HERE
    row.update(expr_here=here, stop_class_here=s.get("stop_class"), bounded_here=bounded_here)
    ea = row["expr_earlier"]
    if here == ea:
        return dict(row, category="agree: both found none" if here is None else "agree: the same expression")
    cat = ("differ: found here only" if ea is None else "differ: found earlier only" if here is None
           else "differ: different expressions")
    causes = []
    if row["examples_same"] is False:
        causes.append("examples")
    if row["examples_same"] is None:
        causes.append("examples unknown")
    if not row["hidden_same"]:
        causes.append("hidden")
    if any(unusable.values()):
        causes.append("input rule")
    if bounded_here or bounded_earlier:
        causes.append("bounded")
    if not causes:
        causes.append("residual")
    return dict(row, category=cat, causes=causes)


def main(outdir, record):
    sigs = dslx.load()["sigs"]
    tdir = os.path.join(outdir, "targets")
    rows = [compare(n[:-5], json.load(open(os.path.join(tdir, n))), sigs) for n in sorted(os.listdir(tdir)) if n.endswith(".json")]
    by = {}
    for r in rows:
        by.setdefault(r["category"], []).append(r["target"])
    res = dict(author="Chimdi Walter Ndubuisi", what="the earlier result as a check (protocol section 9): L4-36 against the "
               "operations study's second condition; descriptive, never part of the primary", outdir=outdir,
               earlier_folder=os.path.relpath(EARLIER, bl_frozen.ROOT), counts={k: len(v) for k, v in sorted(by.items())},
               by_category={k: v for k, v in sorted(by.items())}, rows=rows)
    with open(record, "w") as f:
        json.dump(res, f, indent=1, default=str)
    for k, v in sorted(by.items()):
        print("%-55s %3d  %s" % (k, len(v), " ".join(v[:12])))
    for r in rows:
        if r["category"].startswith("differ"):
            print("  %s: here %s | earlier %s | causes %s" % (r["target"], r.get("expr_here"), r.get("expr_earlier"), r.get("causes")))
    return 0


if __name__ == "__main__":
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("run with PYTHONHASHSEED=0")
    sys.exit(main(sys.argv[1], sys.argv[2]))
