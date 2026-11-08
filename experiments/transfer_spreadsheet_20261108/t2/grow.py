"""The adapter's loop (CORA's six steps) for string programs.

1. propose: bottom-up search over the current language (t2/dsl.py);
2. check: the program must reproduce every training output exactly;
3. on failure, describe what is missing: rank the base search's string programs by how much of every wanted output
   they explain as a prefix, a suffix or an inner part; the gap left by each of the best partial programs (and the
   whole output) is a typed hole, a list of (source string, wanted string) pairs, one per training example;
4. build the missing piece: a piece of the structure space (t2/pieces.py) consistent with every pair of a hole, or a
   constant when the hole is the same string on every example;
5. check again: search again with the piece added to the language, at the base budget;
6. keep the piece only if leave-one-out rebuilding predicts each training example: for each example, rebuild the
   piece from the other examples' pairs (first consistent piece in canonical order), put it in place of the piece
   in the program found in step 5, and require that program to reproduce the left-out example exactly.
"""
import hashlib
import json

from t2 import dsl, pieces as P


def view_of(task, train_idx):
    exs = task["examples"]
    return {"arg_types": task["arg_types"], "inputs": [exs[i][0] for i in train_idx],
            "outputs": [exs[i][1] for i in train_idx], "str_consts": list(task["str_consts"]),
            "int_consts": list(task["int_consts"])}


def split_examples(task, salt):
    """Hash order of the task's examples under the salt: the first k_train are training, the rest held checks."""
    n = len(task["examples"])
    key = [hashlib.sha256(f"{salt}|{task['id']}|{json.dumps(task['examples'][e])}".encode()).hexdigest()
           for e in range(n)]
    order = sorted(range(n), key=lambda e: key[e])
    return order[:task["k_train"]], order[task["k_train"]:]


# ------------------------------------------------------------------ step 3: failure description
def failure_description(view, bank, n_partial):
    ys = view["outputs"]
    sketches = [{"form": "whole", "partial": None, "partial_size": None, "holes": [list(ys)]}]
    ranked, seen = [], set()
    for idx, (vals, tree, sz) in enumerate(bank):
        expl = sum(len(v) for v in vals)
        if expl == 0 or vals in seen:
            continue
        if all(y.startswith(v) for v, y in zip(vals, ys)):
            form = "prefix"
        elif all(y.endswith(v) for v, y in zip(vals, ys)):
            form = "suffix"
        elif all(v in y for v, y in zip(vals, ys)):
            form = "inner"
        else:
            continue
        seen.add(vals)
        ranked.append((-expl, sz, idx, form, vals, tree))
    ranked.sort(key=lambda r: r[:3])
    for _, sz, _, form, vals, tree in ranked[:n_partial]:
        if form == "prefix":
            holes = [[y[len(v):] for v, y in zip(vals, ys)]]
        elif form == "suffix":
            holes = [[y[:len(y) - len(v)] for v, y in zip(vals, ys)]]
        else:
            pos = [y.find(v) for v, y in zip(vals, ys)]
            holes = [[y[:p] for p, y in zip(pos, ys)], [y[p + len(v):] for p, v, y in zip(pos, vals, ys)]]
        sketches.append({"form": form, "partial": tree, "partial_size": sz, "holes": holes})
    return sketches


# ------------------------------------------------------------------ step 4: build the piece
def build_for_hole(sources, hole, D, limit):
    """Pieces for one hole: a constant when the hole is one non-empty string everywhere, otherwise up to `limit`
    consistent pieces per source argument (sources = list of per-example source strings, one list per argument)."""
    if all(h == hole[0] for h in hole):
        return [] if hole[0] == "" else [{"kind": "const", "value": hole[0], "source": None,
                                          "pairs": [[None, h] for h in hole]}]
    out = []
    for j, src in sources:
        pairs = list(zip(src, hole))
        for pc in P.consistent(pairs, D, limit=limit):
            out.append({"kind": "piece", "piece": pc, "source": j, "pairs": [list(p) for p in pairs]})
    return out


def candidates(view, sketches, D, per_hole, max_cands):
    """Candidates in order: sketches in order; a one-hole sketch gives each of its pieces; a two-hole sketch gives
    one candidate made of the first piece of each hole. Duplicate piece sets are dropped."""
    sources = [(j, [x[j] for x in view["inputs"]]) for j, t in enumerate(view["arg_types"]) if t == "String"]
    out, seen = [], set()
    for si, sk in enumerate(sketches):
        if len(sk["holes"]) == 1:
            combos = [[b] for b in build_for_hole(sources, sk["holes"][0], D, per_hole)]
        else:
            firsts = []
            for hole in sk["holes"]:
                if all(h == "" for h in hole):
                    continue
                b = build_for_hole(sources, hole, D, 1)
                if not b:
                    firsts = None
                    break
                firsts.append(b[0])
            combos = [firsts] if firsts else []
        for combo in combos:
            key = tuple(sorted(_label(b) for b in combo))
            if key in seen:
                continue
            seen.add(key)
            out.append({"sketch": si, "form": sk["form"], "built": combo})
            if len(out) >= max_cands:
                return out
    return out


def _label(b):
    return ("const", b["value"]) if b["kind"] == "const" else (P.name_of(b["piece"]), b["source"])


def language_of(built):
    ps, cs = [], []
    for b in built:
        if b["kind"] == "const":
            cs.append(b["value"])
        else:
            ps.append((P.name_of(b["piece"]), P.fn_of(b["piece"])))
    return dsl.Language(pieces=ps, consts=cs)


# ------------------------------------------------------------------ step 6: leave-one-out rebuilding
def rebuild(b, drop, D):
    """The piece rebuilt from the construction pairs without pair `drop` (first consistent piece in canonical
    order), or None."""
    pairs = [p for i, p in enumerate(b["pairs"]) if i != drop]
    if b["kind"] == "const":
        vals = {t for _, t in pairs}
        return b if len(vals) == 1 else None
    found = P.consistent([tuple(p) for p in pairs], D, limit=1)
    return {"kind": "piece", "piece": found[0], "source": b["source"], "pairs": pairs} if found else None


def loo_accept(program, built, view, D):
    """For each training example i: rebuild every piece without pair (i mod number of pairs), substitute it into
    the program and require the program to reproduce example i."""
    k = len(view["outputs"])
    folds = []
    for i in range(k):
        tree, extra, ok = program, [], True
        for b in built:
            if b["kind"] == "const":
                if rebuild(b, i % len(b["pairs"]), D) is None:
                    ok = False
                continue
            rb = rebuild(b, i % len(b["pairs"]), D)
            if rb is None:
                ok = False
                break
            old, new = P.name_of(b["piece"]), P.name_of(rb["piece"])
            if new != old:
                tree = dsl.substitute(tree, old, "__loo__" + new)
                extra.append(("__loo__" + new, P.fn_of(rb["piece"])))
        pred = None
        if ok:
            lang = language_of(built)
            lang.fn.update(dict(extra))
            try:
                pred = dsl.evaluate(tree, view["inputs"][i], lang)
            except dsl.Undefined:
                pred = None
            ok = pred == view["outputs"][i]
        folds.append(bool(ok))
        if not ok:
            break
    return all(folds) and len(folds) == k, folds


# ------------------------------------------------------------------ arms
def predict(program, lang, inputs):
    out = []
    for x in inputs:
        try:
            out.append(dsl.evaluate(program, x, lang))
        except dsl.Undefined:
            out.append(None)
    return out


def try_candidates(view, cands, D, cfg, budget):
    """Steps 5 and 6 over the candidates, each search at `budget` executions. Returns the accepted attempt and the
    first fitting one (for the secondary without leave-one-out acceptance)."""
    rows, accepted, first_fit, calls, cpu = [], None, None, 0, 0.0
    for c in cands[:cfg["max_candidates"]]:
        lang = language_of(c["built"])
        r = dsl.search(view, lang, budget, cfg["search_cpu_cap"], cfg["max_size"])
        calls += r["calls"]
        cpu += r["cpu_s"]
        row = {"sketch": c["sketch"], "form": c["form"], "built": [_label(b) for b in c["built"]],
               "fit": r["fit"], "calls": r["calls"], "stop": r["stop"]}
        if r["fit"]:
            ok, folds = loo_accept(r["program"], c["built"], view, D)
            row.update(program=dsl.show(r["program"]), loo=folds, accepted=ok)
            att = {"program": r["program"], "lang": lang, "candidate": len(rows)}
            if first_fit is None:
                first_fit = att
            if ok:
                accepted = att
                rows.append(row)
                break
        rows.append(row)
    return accepted, first_fit, rows, calls, round(cpu, 4)
