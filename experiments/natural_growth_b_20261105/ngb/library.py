"""Stage 2 (source halves only, phase 1): candidate extraction from the discovered solutions, promotion under the
gates, the per-benchmark library, and the in-sample estimates the honest expectation is built from. The library is
built once here, from the frozen stage 1 records, and frozen; phase 2 only reuses it.

    python -I run.py library OUT_DIR BENCH            candidates, gates, library, in-sample estimates
    python -I run.py library OUT_DIR shuffle          after all three benchmarks: the shuffled libraries

Inputs: stage 1's discovery records (`feasibility/discover_shard{0,1}.jsonl`, ngb/discover.py): for every source
task the base search (150,000 executions) and, on failure, the search at 4x (600,000); the first fitting tree, the
two attempts and the CPU. The discovery CPU charged to the library is the sum over EVERY source task of the
benchmark: finding the solutions cost the failed searches too. The records are checked against study A's frozen
controller records (which tasks fit at base and at 4x; disagreements are counted and reported).

Gates (the growth study's, unchanged code: cgrow/selfext_core.py through study A's CappedGates), per candidate in
order: novelty (rejected as a search shortcut when a G0 program found by the base search on the 12 probe grids within
200,000 executions reproduces it at every defined parameter value); redundancy (its behaviour on the probe grids and
its sources' inputs equals an already promoted operation's); regression on U, the benchmark's source tasks G0 solves
at base (a lost fit, or an old first prediction that is no longer among the two attempts, means rolled back). A
candidate that passes is PROMOTED. No
validation on other tasks is required: a library entry is admitted for being hard to express, not for proven reuse.
The library is the promoted operations in order; the combined regression check removes the most recent entry while
G0 plus the library loses a fit on U or no longer has an old first prediction among its two attempts.

In-sample estimates (source half; its test outputs are read by the scorer here): leave-one-source-out (for each
solved source task t, G0 plus the library without the operations whose only source is t, at base budget) and reach
beyond 4x (G0 plus the library at base budget on every source task not solved at 4x).
"""
import hashlib
import json
import os
import pickle
import sys
import time

from ngb import env as E, ops as OP, score as SC
from ngrow import data as DT, grow as GR
from cgrow import search as S
from a2 import arcdsl as D
from a2.corpus import tree_from_json

DISCOVERY = [os.path.join(E.STUDY, "feasibility", f"discover_shard{i}.jsonl") for i in (0, 1)]
CTRL_A = [os.path.join(E.STUDY_A, "feasibility", f"controller_source_shard{i}.jsonl") for i in (0, 1)]


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def jsonl(paths, bench):
    out = {}
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    if r["bench"] == bench:
                        out[r["task"]] = r
    return out


def signature(op, probes, inputs):
    xs = list(probes) + list(inputs)
    return repr([[op(x, *th) for x in xs] for th in op.thetas()])


ops_from_json = OP.ops_from_json                 # kept here for the phase 1 stage; the kernel uses ngb.ops


def combined_regression(g0b, lib, tasks, solved, base_preds):
    reg, rounds = list(lib), []
    while reg:
        t0 = time.process_time()
        g = OP.grammar_with(g0b, reg)
        lost, changed = [], []
        for tid in solved:
            t = tasks[tid]
            r = S.run(g, t["train"], t["test_inputs"])
            if not r["fit"]:
                lost.append(tid)
            elif base_preds.get(tid) is not None and (not r["preds"] or base_preds[tid] not in r["preds"]):
                changed.append(tid)
        rounds.append({"library": [o.sid for o in reg], "lost_fit": lost, "changed_prediction": changed,
                       "cpu_s": round(time.process_time() - t0, 3)})
        if not lost and not changed:
            break
        reg = reg[:-1]
    return reg, rounds


def build(out_dir, bench):
    bdir = os.path.join(out_dir, bench)
    os.makedirs(bdir, exist_ok=True)
    disc = jsonl(DISCOVERY, bench)
    recs_a = jsonl(CTRL_A, bench)
    src = DT.half("source", (bench,))
    fam = {t: f for _, f, t in src}
    ids = [t for _, _, t in src]
    missing = sorted(set(ids) - set(disc))
    if missing or set(disc) - set(ids):
        raise SystemExit(f"discovery records must cover exactly the source half ({len(missing)} missing)")
    all_tasks = DT.tasks(bench)
    tasks = {t: all_tasks[t] for t in ids}
    g0b = OP.G0Builder()
    ev = D.Evaluator(g0b.g.fns, g0b.g.consts)
    solved = {t: r for t, r in disc.items() if r["found_at"]}
    base_solved = sorted(t for t, r in disc.items() if r["found_at"] == "base")
    base_preds = {t: GR.as_preds(disc[t]["preds"])[0] for t in base_solved}
    discovery_cpu = sum(r["cpu_s"] for r in disc.values())
    # consistency with study A's frozen controller records (fit at base; fit at 4x)
    disagree = []
    for t in ids:
        ra = recs_a[t]["record"]
        a_at = "base" if ra["base"]["fit"] else ("x4" if (ra.get("probe_deeper_search") or {}).get("fit") else None)
        if a_at != disc[t]["found_at"]:
            disagree.append({"task": t, "study_a": a_at, "stage_1": disc[t]["found_at"]})
    E.dump(os.path.join(bdir, "discovery_summary.json"),
           {"bench": bench, "source_tasks": len(ids), "solved_base": len(base_solved), "solved_4x": len(solved),
            "discovery_cpu_s": round(discovery_cpu, 3), "disagreements_with_study_a": disagree,
            "solutions": {t: {"found_at": r["found_at"], "program": D.show(tree_from_json(r["tree"])),
                              "family": fam[t]} for t, r in sorted(solved.items())}})
    # candidates
    ops, by_tree = [], {}
    for t in sorted(solved, key=lambda t: (fam[t], t)):
        tree = tree_from_json(solved[t]["tree"])
        inputs = [a for a, _ in tasks[t]["train"]] + tasks[t]["test_inputs"]
        for kind, ct in OP.candidates_of(tree, inputs, g0b.g.consts, ev):
            if ct in by_tree:
                by_tree[ct].sources.append(t)
                continue
            o = OP.LibOp(f"lib_{bench}_{len(ops):03d}", ct, kind, t, fam[t], ev)
            by_tree[ct] = o
            ops.append(o)
    # gates
    plug = OP.LibraryPlugin(g0b, ops)
    cache_path = os.path.join(bdir, "gates.pkl")
    cache = pickle.load(open(cache_path, "rb")) if os.path.exists(cache_path) else None
    G = GR.CappedGates(plug, tasks, base_solved, base_preds, [], cache)
    G.solved_set = set(base_solved)
    rows, promoted, sigs = [], [], {}
    t_gates = time.process_time()
    for o in ops:
        row = o.describe()
        nov = G.novelty(o.sid)
        row["novelty"] = {"duplicate": nov["duplicate"], "witnesses": nov["witnesses"][:2], "cpu_s": nov["cpu_s"]}
        if nov["duplicate"]:
            row["outcome"] = "search_shortcut"
            rows.append(row)
            continue
        sig = signature(o, plug.probes, [a for s in o.sources for a, _ in tasks[s]["train"]])
        if sig in sigs:
            row["outcome"] = "redundant_with"
            row["redundant_with"] = sigs[sig]
            rows.append(row)
            continue
        reg = G.regression(o.sid)
        row["regression"] = {k: reg[k] for k in ("lost_fit", "changed_prediction", "checked", "cpu_s")}
        if reg["lost_fit"] or reg["changed_prediction"]:
            row["outcome"] = "rolled_back"
            rows.append(row)
            continue
        row["outcome"] = "promoted"
        sigs[sig] = o.sid
        promoted.append(o)
        rows.append(row)
    with open(E.check_write(cache_path), "wb") as f:
        pickle.dump(G.c, f)
    gate_cpu = G.charged(G.used)
    lib, rounds = combined_regression(g0b, promoted, tasks, base_solved, base_preds)
    construction_cpu = gate_cpu + sum(r["cpu_s"] for r in rounds)
    E.dump(os.path.join(bdir, "candidates.json"), rows)
    E.dump(os.path.join(bdir, "library.json"),
           {"bench": bench, "g0_sha256": g0b.sha, "library": [o.describe() for o in lib],
            "promoted_before_combined_check": [o.sid for o in promoted], "combined_regression": rounds,
            "counts": {"solutions": len(solved), "candidates": len(ops),
                       "search_shortcut": sum(r["outcome"] == "search_shortcut" for r in rows),
                       "redundant": sum(r["outcome"] == "redundant_with" for r in rows),
                       "rolled_back": sum(r["outcome"] == "rolled_back" for r in rows),
                       "promoted": len(promoted), "library": len(lib)},
            "cpu_s": {"discovery": round(discovery_cpu, 3), "gates_charged": gate_cpu,
                      "gates_process": round(time.process_time() - t_gates, 3),
                      "combined_regression": round(sum(r["cpu_s"] for r in rounds), 3),
                      "construction": round(construction_cpu, 3),
                      "total_charged": round(discovery_cpu + construction_cpu, 3)}})
    print(json.dumps({"bench": bench, "library": [o.text for o in lib], "counts": {"candidates": len(ops),
                      "promoted": len(promoted), "library": len(lib)}}), flush=True)
    # in-sample estimates
    sol = SC.solutions(bench, ids)
    loso, reach = {}, {}
    for t in sorted(solved):
        keep = [o for o in lib if any(s != t for s in o.sources)]
        r = S.run(OP.grammar_with(g0b, keep), tasks[t]["train"], tasks[t]["test_inputs"])
        sc = SC.score_row(r["preds"] if r["fit"] else None, sol[t])
        loso[t] = {"family": fam[t], "found_at": solved[t]["found_at"], "library_size": len(keep), "fit": r["fit"],
                   "correct": sc["correct"], "n_outputs": sc["n_outputs"], "program": r["program"],
                   "same_family_ops": sum(1 for o in keep if o.family == fam[t]), "cpu_s": r["cpu_s"]}
    g_full = OP.grammar_with(g0b, lib)
    for t in ids:
        if t in solved:
            continue
        r = S.run(g_full, tasks[t]["train"], tasks[t]["test_inputs"])
        sc = SC.score_row(r["preds"] if r["fit"] else None, sol[t])
        reach[t] = {"family": fam[t], "fit": r["fit"], "correct": sc["correct"], "n_outputs": sc["n_outputs"],
                    "program": r["program"], "cpu_s": r["cpu_s"]}
    per_family = {}
    for f in sorted({fam[t] for t in ids}):
        ts = [t for t in ids if fam[t] == f]
        per_family[f] = {"source_tasks": len(ts), "solved_base": sum(t in base_solved for t in ts),
                         "solved_4x": sum(t in solved for t in ts),
                         "library_ops_from_family": sum(1 for o in lib if o.family == f),
                         "loso_fit": sum(loso[t]["fit"] for t in ts if t in loso),
                         "loso_correct_tasks": sum(loso[t]["correct"] == loso[t]["n_outputs"] for t in ts if t in loso),
                         "reach_fit": sum(reach[t]["fit"] for t in ts if t in reach),
                         "reach_correct_tasks": sum(reach[t]["correct"] == reach[t]["n_outputs"] for t in ts
                                                    if t in reach)}
    summary = {"solved_4x": len(solved), "loso_fit": sum(v["fit"] for v in loso.values()),
               "loso_correct_tasks": sum(v["correct"] == v["n_outputs"] for v in loso.values()),
               "loso_correct_outputs": sum(v["correct"] for v in loso.values()),
               "reach_tried": len(reach), "reach_fit": sum(v["fit"] for v in reach.values()),
               "reach_correct_tasks": sum(v["correct"] == v["n_outputs"] for v in reach.values()),
               "reach_correct_outputs": sum(v["correct"] for v in reach.values()),
               "insample_cpu_s": round(sum(v["cpu_s"] for v in loso.values()) +
                                       sum(v["cpu_s"] for v in reach.values()), 3)}
    E.dump(os.path.join(bdir, "insample.json"),
           {"bench": bench, "loso": loso, "reach": reach, "per_family": per_family, "summary": summary})
    print(json.dumps({"bench": bench, "insample": summary}), flush=True)


def shuffle(out_dir):
    """S(b): the first |L(b)| operations of the other benchmarks' libraries in sha256('shuffle:'+b+'|'+sid) order."""
    libs = {b: E.load(os.path.join(out_dir, b, "library.json"))["library"] for b in DT.BENCHMARKS}
    out = {}
    for b in DT.BENCHMARKS:
        pool = [o for b2 in DT.BENCHMARKS if b2 != b for o in libs[b2]]
        pool.sort(key=lambda o: h(f"shuffle:{b}|{o['sid']}"))
        out[b] = {"library": pool[:len(libs[b])], "wanted": len(libs[b]), "available": len(pool),
                  "shortfall": max(0, len(libs[b]) - len(pool))}
    E.dump(os.path.join(out_dir, "shuffled.json"), out)
    print(json.dumps({b: {k: v for k, v in r.items() if k != "library"} for b, r in out.items()}))


def main(out_dir, bench):
    out_dir = os.path.abspath(out_dir)
    if bench == "shuffle":
        shuffle(out_dir)
    else:
        build(out_dir, bench)


if __name__ == "__main__":
    main(*sys.argv[1:])
