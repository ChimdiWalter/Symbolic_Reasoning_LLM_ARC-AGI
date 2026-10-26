"""Engineering comparison for rule-language version 5 (NOT a frozen study; development evidence on generated tasks).

Tasks: for each version 5 capability, 10 newly generated DEV-style tasks (tests/g5_generators.py, seeds disjoint
from the tests); controls: 2 tasks per version 4 case (tests/test_neural_cora_v2g4.py). Arms: version 3, version 4,
version 5 at 3,000 candidates; version 4 given version 5's CPU time on the same task (budget 20,000, CPU cap = version
5's CPU); and, only where version 5 is right and neither version 4 arm generated the answer, version 4 with ten times
the candidates and CPU (30,000; 10 x version 5's CPU), used to classify the gain.

Metrics per arm: pass@2 (an attempt equals the generated answer); coverage (a kept prediction equals it); the first
correct candidate (its position in generation order, and the rank of the correct prediction in selection order);
changed-cell agreement (the share of the cells that must change that an attempt gets right: the better attempt, and
the first); fit-to-test generalization (of ALL programs that fit the demonstrations, how many predict the test
exactly); CPU, candidates and native executions. Every fitting program is counted by wrapping each version's
selection call: the wrapper records its arguments and ranking and returns the result unchanged.

Gains of version 5 over a version 4 arm are classified as selection (that arm generated the answer but did not choose
it), construction (version 4 generated it at some compute, or version 5's correct attempt uses only version 4's
vocabulary) or expressivity (operational: the correct attempt needs a version 5 rule type and no version 4 arm, up to
ten times the compute, generated the answer; this is not a proof that no version 4 program exists).
  python scripts/neural_cora_v2g5_engineering.py run      # 2 workers, nice 10; resumable (rows.jsonl)
  python scripts/neural_cora_v2g5_engineering.py summary  # summary.json and summary.md
"""
import json
import multiprocessing as mp
import os
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))
OUT = os.path.join(HERE, "outputs", "neural_cora_v2g5_engineering")
BUDGET = 3000
ARMS = ("g3", "g4", "g4_cpu", "g5")
V5_TEXT = ("(stamp_rule", "(ray2_rule", "(segment_rule", "(fill_rule")
LOG = []                                                    # (version, fitting programs, ranking) per selection call


def tasks():
    from g5_generators import CASES, make_task
    from test_neural_cora_v2g4 import G4_CASES, make_g4
    out = []
    for name, (prog, scene) in sorted(CASES.items()):
        for s in range(10):
            t, a = make_task(prog, scene, zlib.crc32(f"eng|{name}|{s}".encode()))
            if t is not None:
                out.append((f"{name}#{s}", "g5_target", t, a))
    for name, (prog, scene) in sorted(G4_CASES.items()):
        for s in (11, 12):
            try:
                t, a = make_g4(prog, scene, s)
            except AssertionError:
                continue
            out.append((f"{name}#{s}", "g4_control", t, a))
    return out


def _probe():
    """Wrap each version's selection call to record what it saw; the ranking and attempts are returned unchanged."""
    from cora_neural_v2g3 import select as A
    from cora_neural_v2g4 import select as B
    from cora_neural_v2g5 import select as C
    for tag, mod in (("g3", A), ("g4", B), ("g5", C)):
        if getattr(mod.choose, "probed", False):
            continue

        def choose(cands, task, cfg=None, search_fn=None, _orig=mod.choose, _tag=tag):
            ranked, attempts = _orig(cands, task, cfg, search_fn)
            LOG.append((_tag, list(cands), ranked))
            return ranked, attempts
        choose.probed = True
        mod.choose = choose


def _changed(attempts, ans, x):
    """(better, first) attempt's share of the cells that must change (answer differs from the test input) that it
    gets right; a size-changing task counts every answer cell; no attempt scores 0."""
    must = (x != ans) if x.shape == ans.shape else np.ones(ans.shape, bool)
    if not must.any():
        return 1.0, 1.0
    vals = [float((g[must] == ans[must]).mean()) if g.shape == ans.shape else 0.0 for g in map(np.asarray, attempts)]
    return (max(vals), vals[0]) if vals else (0.0, 0.0)


def _score(kind, r, ans, x):
    """One arm's row. `kind` names the selection call whose ranking is final (g3, g4 or g5); a version 4 or 5 run
    also contains its inner version 3 search, whose fitting programs are added (minus those the head already has)."""
    from cora_neural_v2g3 import select as SEL
    eq = lambda g: np.array_equal(np.asarray(g), ans)                     # noqa: E731
    last = [e for e in LOG if e[0] == kind]
    inner = [e for e in LOG if e[0] == "g3"]
    top, ranked = (last[-1][1], last[-1][2]) if last else ([], [])
    if kind == "g3":
        fits = [(c["at"], c) for c in top]
    else:
        head = [c for c in top if c["origin"] != "g3"]
        hp = {c["prog"] for c in head}
        off = r["head"]["evaluated"]
        fits = [(c["at"], c) for c in head] + \
            [(c["at"] + off, c) for c in (inner[-1][1] if inner else []) if c["prog"] not in hp]
    ok = [(at, c) for at, c in fits if eq(c["preds"][0])]
    distinct, seen = [], set()
    for c in ranked:
        k = SEL.pred_key(c["preds"])
        if k not in seen:
            seen.add(k)
            distinct.append(c)
    best, first = _changed(r["attempts"], ans, x)
    hit = [p for g, p in zip(r["attempts"], r.get("attempt_programs", [])) if eq(g)]
    row = {"pass2": any(eq(g) for g in r["attempts"]), "coverage": any(eq(g) for g in r["predictions"]),
           "cpu": r["cpu_s"], "n_candidates": r["n_candidates"], "fits": len(fits), "fits_correct": len(ok),
           "first_correct_at": min((at for at, _ in ok), default=None),
           "selection_rank": next((i + 1 for i, c in enumerate(distinct) if eq(c["preds"][0])), None),
           "changed_cell_best": round(best, 4), "changed_cell_first": round(first, 4),
           "correct_origins": sorted({c["origin"] for _, c in ok}),
           "attempt_uses_v5": any(any(t in p for t in V5_TEXT) for p in hit)}
    if "head" in r:
        row["native_runs"] = r["head"].get("construct_native_runs", 0) + r["head"].get("loo_native_runs", 0)
    LOG.clear()
    return row


def run_one(item):
    os.nice(10)
    tid, group, task, ans = item
    from cora_neural_v2g3 import search as S3
    from cora_neural_v2g4 import search as S4
    from cora_neural_v2g5 import search as S5
    _probe()
    LOG.clear()
    ans, x = np.asarray(ans), np.asarray(task["test_inputs"][0])
    row = {"task": tid, "group": group}
    r5 = S5.search(task, BUDGET)
    row["g5"] = _score("g5", r5, ans, x)
    row["g5_head"] = r5["head"]
    row["g4"] = _score("g4", S4.search(task, BUDGET), ans, x)
    row["g3"] = _score("g3", S3.search(task, BUDGET), ans, x)
    cap = max(1.0, r5["cpu_s"])
    row["g4_cpu"] = _score("g4", S4.search(task, 20000, cpu_cap_s=cap), ans, x)
    if row["g5"]["pass2"] and not (row["g4"]["fits_correct"] or row["g4_cpu"]["fits_correct"]):
        row["g4_x10"] = _score("g4", S4.search(task, 10 * BUDGET, cpu_cap_s=10 * cap), ans, x)
    return row


def run():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "rows.jsonl")
    done = {json.loads(l)["task"] for l in open(path)} if os.path.exists(path) else set()
    todo = [t for t in tasks() if t[0] not in done]
    with mp.get_context("fork").Pool(2, maxtasksperchild=1) as pool, open(path, "a") as f:
        for row in pool.imap_unordered(run_one, todo):
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(row["task"], {a: row[a]["pass2"] for a in ARMS}, flush=True)
    print("EXIT", flush=True)


def _classify(r, base):
    """Why version 5 is right where the version 4 arm `base` is not (see the module docstring)."""
    if r[base]["fits_correct"]:
        return "selection"
    if any(r[a]["fits_correct"] for a in ("g4", "g4_cpu", "g4_x10") if a in r) or not r["g5"]["attempt_uses_v5"]:
        return "construction"
    return "expressivity"


def _arm_stats(rs, arm):
    a = [r[arm] for r in rs]
    with_fits = [x for x in a if x["fits"]]
    found = [x["first_correct_at"] for x in a if x["first_correct_at"] is not None]
    ranks = [x["selection_rank"] for x in a]
    return {"pass2": sum(x["pass2"] for x in a), "coverage": sum(x["coverage"] for x in a),
            "generated": sum(x["fits_correct"] > 0 for x in a),
            "changed_cell_best": round(float(np.mean([x["changed_cell_best"] for x in a])), 3),
            "changed_cell_first": round(float(np.mean([x["changed_cell_first"] for x in a])), 3),
            "first_correct_at_median": float(np.median(found)) if found else None,
            "selection_rank": {"1": ranks.count(1), "2": ranks.count(2),
                               ">2": sum(k is not None and k > 2 for k in ranks), "none": ranks.count(None)},
            "fits": sum(x["fits"] for x in a), "fits_correct": sum(x["fits_correct"] for x in a),
            "fit_to_test_micro": round(sum(x["fits_correct"] for x in a) / max(1, sum(x["fits"] for x in a)), 3),
            "fit_to_test_macro": round(float(np.mean([x["fits_correct"] / x["fits"] for x in with_fits])), 3)
            if with_fits else None,
            "cpu_median": float(np.median([x["cpu"] for x in a])),
            "candidates_median": float(np.median([x["n_candidates"] for x in a])),
            "native_runs_median": float(np.median([x["native_runs"] for x in a])) if "native_runs" in a[0] else None}


def summary():
    rows = sorted((json.loads(l) for l in open(os.path.join(OUT, "rows.jsonl"))), key=lambda r: r["task"])
    out, md = {}, ["# Version 5 engineering comparison: generated summary (NOT frozen; development evidence)", ""]
    for group in sorted({r["group"] for r in rows}):
        rs = [r for r in rows if r["group"] == group]
        g = out[group] = {"n": len(rs), **{arm: _arm_stats(rs, arm) for arm in ARMS}}
        for base in ("g4", "g4_cpu", "g3"):
            gains = [r for r in rs if r["g5"]["pass2"] and not r[base]["pass2"]]
            losses = [r for r in rs if r[base]["pass2"] and not r["g5"]["pass2"]]
            g[f"g5_vs_{base}"] = {"gains": len(gains), "losses": len(losses),
                                  "gain_tasks": [r["task"] for r in gains], "loss_tasks": [r["task"] for r in losses],
                                  "loss_kind": {r["task"]: "selection" if r["g5"]["fits_correct"] else "generation"
                                                for r in losses}}
            if base != "g3":
                kinds = [_classify(r, base) for r in gains]
                g[f"g5_vs_{base}"]["gain_kind"] = {k: kinds.count(k) for k in ("expressivity", "construction",
                                                                               "selection")}
        x10 = [r["g4_x10"] for r in rs if "g4_x10" in r]
        g["g4_x10"] = {"n": len(x10), "generated": sum(x["fits_correct"] > 0 for x in x10),
                       "pass2": sum(x["pass2"] for x in x10),
                       "cpu_median": float(np.median([x["cpu"] for x in x10])) if x10 else None}
        md += [f"## {group} ({len(rs)} tasks)", "",
               "| arm | pass@2 | coverage | generated | changed-cell (better / first) | first correct (median) | "
               "rank 1 / 2 / >2 / none | fit-to-test (fits correct / fits) | CPU s (median) |",
               "|---|---|---|---|---|---|---|---|---|"]
        for arm in ARMS:
            s = g[arm]
            sr = s["selection_rank"]
            md.append(f"| {arm} | {s['pass2']} | {s['coverage']} | {s['generated']} | {s['changed_cell_best']:.3f} / "
                      f"{s['changed_cell_first']:.3f} | {s['first_correct_at_median']} | {sr['1']} / {sr['2']} / "
                      f"{sr['>2']} / {sr['none']} | {s['fit_to_test_micro']:.3f} ({s['fits_correct']} / {s['fits']}) | "
                      f"{s['cpu_median']:.1f} |")
        md += ["", f"- version 4 with ten times the candidates and CPU (run only where version 5 was right and no version 4 "
               f"arm generated the answer): {g['g4_x10']['n']} tasks, generated {g['g4_x10']['generated']}, "
               f"pass@2 {g['g4_x10']['pass2']}"]
        for base in ("g4", "g4_cpu", "g3"):
            c = g[f"g5_vs_{base}"]
            md.append(f"- version 5 vs {base}: +{c['gains']} / -{c['losses']}"
                      + (f"; gains by kind {c['gain_kind']}" if "gain_kind" in c else "")
                      + (f"; losses {c['loss_kind']}" if c["losses"] else ""))
        md.append("")
    per_cap = {}
    for r in rows:
        if r["group"] == "g5_target":
            d = per_cap.setdefault(r["task"].split("#")[0], {"n": 0, **{a: 0 for a in ARMS}, "gain_kind_vs_g4": {}})
            d["n"] += 1
            for a in ARMS:
                d[a] += r[a]["pass2"]
            if r["g5"]["pass2"] and not r["g4"]["pass2"]:
                k = _classify(r, "g4")
                d["gain_kind_vs_g4"][k] = d["gain_kind_vs_g4"].get(k, 0) + 1
    out["per_capability_pass2"] = per_cap
    md += ["## pass@2 per capability (g5_target)", "", "| capability | n | g3 | g4 | g4_cpu | g5 | gains over g4 by kind |",
           "|---|---|---|---|---|---|---|"]
    md += [f"| {k} | {d['n']} | {d['g3']} | {d['g4']} | {d['g4_cpu']} | {d['g5']} | {d['gain_kind_vs_g4'] or '-'} |"
           for k, d in sorted(per_cap.items())]
    json.dump(out, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    open(os.path.join(OUT, "summary.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    {"run": run, "summary": summary}[sys.argv[1]]()
