"""U2 scorer and budget (PROTOCOL.md sections 6-8). Run with python3 -I.
    score.py budget   exit 0 under the soft cap, 1 past the soft cap (24 CPU-h), 2 past the hard cap (30 CPU-h)
    score.py score    write results/RESULTS.json and results/SUMMARY.md (the only reader of the solutions)"""
import glob
import json
import math
import os
import sys

E = "/path/to/repository/experiments/universality_similar_problems_20261102"
DATA = "/path/to/benchmark_data"
RUNS = os.path.join(DATA, "runs")
SYS = {"a": "O+ v2 (CAST v1 core at 45/90 s, then R29)", "b": "H's CORA component (cast_selective_v2, rule B3)",
       "c": "O (cast_v1)"}
PKGS_A = ["cast_v1", "r29_cpu_package_20261101"]
BENCHES = ["concept_arc", "mini_arc", "1d_arc"]
ARMS = ["real", "shuffled"]
SOFT, HARD = 24 * 3600, 30 * 3600


def task_files(rd):
    return [p for p in glob.glob(os.path.join(rd, "**", "*.json"), recursive=True)
            if os.path.basename(p)[:2] in ("1d", "mi", "co") and "_ids" not in p]


def cpu_of(rd):
    tot = 0.0
    for p in task_files(rd):
        try:
            tot += float((json.load(open(p)).get("child") or {}).get("cpu_s") or 0)
        except (ValueError, OSError):
            pass
    return tot


def wilson(k, n, z=1.959964):
    if n == 0:
        return [None, None]
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [max(0.0, c - h), min(1.0, c + h)]


def load(p, default=None):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return default


def pkg_answers(r, n):
    if not isinstance(r, dict) or r.get("status") != "OK":
        return [None] * n
    g = r.get("grids")
    return [x for x in g] if isinstance(g, list) and len(g) == n else [None] * n


def outcomes(sy, rd, ch, sol):
    """Per (tid, j): dict(answered, correct, pass2, module, status)."""
    out = {}
    if sy == "b":
        sub = load(os.path.join(rd, "submission_B.json"), {})
    else:
        sub = load(os.path.join(rd, "submission.json"), {})
    for tid, t in ch.items():
        n = len(t["test"])
        if sy == "a":
            per = [pkg_answers(load(os.path.join(rd, "run", f"pkg{k}_{nm}", "shard_0", f"{tid}.json")), n)
                   for k, nm in enumerate(PKGS_A)]
            st = (load(os.path.join(rd, "run", f"pkg0_{PKGS_A[0]}", "shard_0", f"{tid}.json"), {}) or {}).get("status")
        else:
            rf = os.path.join(rd, "side" if sy == "b" else os.path.join("run", "shard_0"), f"{tid}.json")
            res = load(rf, {}) or {}
            st = res.get("status")
        for j, x in enumerate(t["test"]):
            e = (sub.get(tid) or [{}] * n)[j] if isinstance(sub, dict) else {}
            a1, a2, s = e.get("attempt_1"), e.get("attempt_2"), sol[tid][j]
            if sy == "a":
                got = [p[j] for p in per if p[j] is not None]
                pa1 = got[0] if got else None
                pa2 = next((g for g in got[1:] if g != pa1), None)
                answered = bool(got)
                correct = answered and (pa1 == s or pa2 == s)
                mod = "cast_v1" if per[0][j] is not None else ("r29" if per[1][j] is not None else None)
            elif sy == "b":
                answered = a2 is not None and a2 != x["input"]
                correct = answered and a2 == s
                ev = ((res.get("evidence") or {}).get("queries") or [])
                q = ev[j] if j < len(ev) and isinstance(ev[j], dict) else {}
                mod = (q.get("accepted_module") or {}).get("B3") if answered else None
            else:
                answered = a1 is not None and a1 != x["input"]
                correct = answered and a1 == s
                mod = (res.get("module") or [None] * n)[j] if answered else None
            out[(tid, j)] = {"answered": answered, "correct": bool(correct), "pass2": (a1 == s or a2 == s),
                             "module": mod, "status": st, "copy": x["input"] == s}
    return out


def summarize(rows, tids_of, boot=True):
    n = len(rows)
    ans = sum(r["answered"] for r in rows.values())
    cor = sum(r["correct"] for r in rows.values())
    p2 = sum(r["pass2"] for r in rows.values())
    d = {"test_outputs": n, "answered": ans, "correct": cor, "coverage": ans / n if n else None,
         "coverage_ci95": wilson(ans, n), "precision": cor / ans if ans else None, "precision_ci95": wilson(cor, ans),
         "cora_accuracy": cor / n if n else None, "cora_accuracy_ci95": wilson(cor, n),
         "pass2_accuracy": p2 / n if n else None, "pass2_ci95": wilson(p2, n),
         "copy_baseline": sum(r["copy"] for r in rows.values()) / n if n else None}
    per_task = {}
    for (tid, j), r in rows.items():
        per_task.setdefault(tid, []).append(r["pass2"])
    sc = [sum(v) / len(v) for v in per_task.values()]
    d["task_score"] = sum(sc) / len(sc) if sc else None
    if sc and boot:
        import numpy as np                                     # protocol: percentile bootstrap, default_rng(0)
        a = np.asarray(sc, float)
        m = a[np.random.default_rng(0).integers(0, len(a), (10000, len(a)))].mean(axis=1)
        d["task_score_ci95"] = [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]
    mods, sts = {}, {}
    for r in rows.values():
        if r["answered"]:
            mods[str(r["module"])] = mods.get(str(r["module"]), 0) + 1
    for tid in tids_of:
        s = str(next((r["status"] for (t, j), r in rows.items() if t == tid), None))
        sts[s] = sts.get(s, 0) + 1
    d["answers_per_module"], d["task_statuses"] = mods, sts
    return d


def fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def ci(c):
    return "" if not c or c[0] is None else f"[{c[0]:.3f}, {c[1]:.3f}]"


def score():
    res = {"systems": SYS, "benchmarks": {}, "labels": {}, "not_run": [], "cpu_s": {}}
    for B in BENCHES:
        ch = {"real": load(os.path.join(DATA, "prepared", B, "real.json")),
              "shuffled": load(os.path.join(DATA, "prepared", B, "shuffled.json"))}
        sol = load(os.path.join(DATA, "prepared", B, "solutions_scorer_only", "solutions.json"))
        meta = load(os.path.join(DATA, "prepared", B, "meta.json"))
        res["benchmarks"][B] = {}
        for sy in SYS:
            for arm in ARMS:
                rd = os.path.join(RUNS, f"{sy}_{B}_{arm}")
                if not os.path.exists(os.path.join(rd, "DONE")):
                    res["not_run"].append(f"{sy}_{B}_{arm}")
                    continue
                rows = outcomes(sy, rd, ch[arm], sol)
                s = summarize(rows, list(ch[arm]))
                s["cpu_s"] = round(cpu_of(rd), 1)
                groups = sorted({m["group"] for m in meta.values() if m["group"]})
                s["per_group"] = {g: summarize({k: v for k, v in rows.items() if meta[k[0]]["group"] == g},
                                               [t for t in ch[arm] if meta[t]["group"] == g], boot=False)
                                  for g in groups}
                res["benchmarks"][B][f"{sy}_{arm}"] = s
            r, sh = res["benchmarks"][B].get(f"{sy}_real"), res["benchmarks"][B].get(f"{sy}_shuffled")
            if r and sh:
                lb = r["precision_ci95"][0]
                ub_s = sh["precision_ci95"][1]
                collapse = sh["answered"] <= 0.5 * r["answered"] and (sh["answered"] == 0 or
                                                                      (ub_s is not None and lb is not None and ub_s < lb))
                ok = r["correct"] >= 10 and lb is not None and lb >= 0.5 and collapse
                res["labels"][f"{sy}_{B}"] = {"label": "VERIFIED_TRANSFER" if ok else "NOT_ESTABLISHED",
                                              "correct_real": r["correct"], "precision_lb_real": lb,
                                              "answered_real": r["answered"], "answered_shuffled": sh["answered"],
                                              "precision_ub_shuffled": ub_s, "shuffled_collapses": collapse}
            else:
                res["labels"][f"{sy}_{B}"] = {"label": "NOT_RUN"}
    res["cpu_s"]["total"] = round(sum(cpu_of(d) for d in glob.glob(os.path.join(RUNS, "*_*_*")) if os.path.isdir(d)), 1)
    os.makedirs(os.path.join(E, "results"), exist_ok=True)
    json.dump(res, open(os.path.join(E, "results", "RESULTS.json"), "w"), indent=1)
    L = ["# U2 results: the submitted CORA systems on ARC-style benchmarks (written by score.py)", "",
         f"Systems: a = {SYS['a']}; b = {SYS['b']}; c = {SYS['c']}. Not run: {res['not_run'] or 'none'}. "
         f"Total CPU: {res['cpu_s']['total'] / 3600:.2f} CPU-h.", ""]
    for B in BENCHES:
        L += [f"## {B}", "", "| system, arm | outputs | answered (coverage, 95% CI) | correct | precision (95% CI) | "
              "CORA accuracy | pass@2 (95% CI) | task score (95% CI) | copy baseline | CPU-h | statuses |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, s in res["benchmarks"][B].items():
            L.append(f"| {k} | {s['test_outputs']} | {s['answered']} ({fmt(s['coverage'])}, {ci(s['coverage_ci95'])}) | "
                     f"{s['correct']} | {fmt(s['precision'])} {ci(s['precision_ci95'])} | {fmt(s['cora_accuracy'])} | "
                     f"{fmt(s['pass2_accuracy'])} {ci(s['pass2_ci95'])} | {fmt(s['task_score'])} "
                     f"{ci(s.get('task_score_ci95'))} | {fmt(s['copy_baseline'])} | {s['cpu_s'] / 3600:.2f} | "
                     f"{s['task_statuses']} |")
        L += ["", "Labels: " + "; ".join(f"{sy}: {res['labels'][f'{sy}_{B}']['label']}" for sy in SYS), ""]
        groups = sorted({g for s in res["benchmarks"][B].values() for g in s.get("per_group", {})})
        if groups:
            L += ["Per group, REAL arm, correct/answered/outputs for systems a, b, c:", "",
                  "| group | a | b | c |", "|---|---|---|---|"]
            for g in groups:
                cells = []
                for sy in SYS:
                    s = res["benchmarks"][B].get(f"{sy}_real", {}).get("per_group", {}).get(g)
                    cells.append(f"{s['correct']}/{s['answered']}/{s['test_outputs']}" if s else "n/a")
                L.append(f"| {g} | " + " | ".join(cells) + " |")
            L.append("")
    open(os.path.join(E, "results", "SUMMARY.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    if sys.argv[1:] == ["budget"]:
        tot = sum(cpu_of(d) for d in glob.glob(os.path.join(RUNS, "*_*_*")) if os.path.isdir(d))
        print(f"cpu_s={tot:.0f}")
        sys.exit(2 if tot > HARD else (1 if tot > SOFT else 0))
    elif sys.argv[1:] == ["score"]:
        score()
