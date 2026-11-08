"""U2b arms B and C (U2B_PROTOCOL.md section 3): blind enumeration in CAST's own L0 grammar (the frozen cast_selective_v2
package, imported unchanged from systems/h), with no contract pruning and no observational equivalence, iterative
deepening (depth 1, 2, 3), stopping at the first program that reproduces every demonstration and gives a valid grid for
every test input. Per-task CPU budget = system b's measured child CPU on the same task and variant in U2. Arm C adds
genuine top-1 leave-one-out with the same blind search per fold (same budget per fold).
Usage: python u2b_blind.py BENCH VARIANT      (one freshly forked child per task; results to runs/u2b_<bench>_<variant>/)"""
import json
import os
import resource
import signal
import sys
import time

E = "/path/to/repository/experiments/universality_similar_problems_20261102"
DATA = "/path/to/benchmark_data"
sys.path.insert(0, os.path.join(E, "systems", "h"))
import numpy as np  # noqa: E402
from cast_selective_v2 import ops as O  # noqa: E402
from cast_selective_v2 import search as SR  # noqa: E402

DEPTHS = (1, 2, 3)
GRACE_S = 10.0


def valid_grid(g):
    return (isinstance(g, list) and 1 <= len(g) <= 30 and all(isinstance(r, list) for r in g) and
            1 <= len(g[0]) <= 30 and all(len(r) == len(g[0]) for r in g) and
            all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


def acceptable(fit):
    return all(p is not None and valid_grid(p) for p in fit["preds"])


class EarlyBudget(SR.Budget):
    """CAST's own Budget, which also reports 'out' as soon as the searcher holds an acceptable fit."""

    def __init__(self, max_cpu_s, s):
        super().__init__(None, max_cpu_s)
        self.s = s

    def out(self):
        return super().out() or (bool(self.s.fits) and acceptable(self.s.fits[-1]))


def blind(train, queries, budget_s):
    """Iterative deepening; returns (first acceptable fit or None, cpu_s, depth reached)."""
    t0 = time.process_time()
    ctx = O.TaskCtx(train, queries)
    for d in DEPTHS:
        left = budget_s - (time.process_time() - t0)
        if left <= 0:
            return None, time.process_time() - t0, d
        s = SR.Searcher(ctx, O.L0, depth=d, mode="exact", oe=False, max_fits=1_000_000, max_cpu_s=left)
        s.budget = EarlyBudget(left, s)
        s.run()
        fit = next((f for f in s.fits if acceptable(f)), None)
        if fit is not None:
            return fit, time.process_time() - t0, d
    return None, time.process_time() - t0, DEPTHS[-1]


def solve(task, budget_s):
    train = [(p["input"], p["output"]) for p in task["train"]]
    tests = [x["input"] for x in task["test"]]
    fit, cpu, depth = blind(train, tests, budget_s)
    out = {"answer": fit["preds"] if fit else [None] * len(tests),
           "program": [f"{n}{th!r}" for n, th in fit["program"]] if fit else None,
           "main_cpu_s": round(cpu, 4), "depth": depth, "budget_s": budget_s, "folds": [], "loo_pass": False}
    if fit is None:
        return out
    if len(train) < 2:
        out["loo_status"] = "INSUFFICIENT_DEMONSTRATIONS"
        return out
    ok = True
    for i in range(len(train)):
        rest = [p for k, p in enumerate(train) if k != i]
        f2, c2, d2 = blind(rest, [train[i][0]], budget_s)
        hit = f2 is not None and f2["preds"][0] == [list(r) for r in train[i][1]]
        out["folds"].append({"held_out": i, "pass": bool(hit), "cpu_s": round(c2, 4), "depth": d2})
        if not hit:
            ok = False
            break                                              # genuine top-1 LOO fails at the first failed fold
    out["loo_pass"] = ok
    out["loo_status"] = "PASS" if ok else "FAIL"
    return out


def child(task, budget_s, w):
    try:
        lim = int(budget_s * (1 + len(task["train"])) + GRACE_S) + 1
        resource.setrlimit(resource.RLIMIT_CPU, (lim, lim + 5))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        res = {"ok": True, **solve(task, budget_s)}
    except BaseException as e:                                 # noqa: BLE001
        res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    os.write(w, json.dumps(res).encode())
    os._exit(0)


def main(bench, variant):
    ch = json.load(open(os.path.join(DATA, "prepared", bench, f"{variant}.json")))
    side = os.path.join(DATA, "runs", f"b_{bench}_{variant}", "side")
    out_dir = os.path.join(DATA, "runs", f"u2b_{bench}_{variant}")
    os.makedirs(out_dir, exist_ok=True)
    st = {"bench": bench, "variant": variant, "n_tasks": len(ch), "done": 0, "child_cpu_s": 0.0, "t0": time.time()}
    for tid, task in sorted(ch.items()):
        p = os.path.join(out_dir, f"{tid}.json")
        if os.path.exists(p):
            st["done"] += 1
            continue
        rb = json.load(open(os.path.join(side, f"{tid}.json")))
        budget_s = float((rb.get("child") or {}).get("cpu_s") or 0.0)
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            child(task, budget_s, w)
        os.close(w)
        buf = b""
        while True:
            chunk = os.read(r, 1 << 16)
            if not chunk:
                break
            buf += chunk
        os.close(r)
        _, status, ru = os.wait4(pid, 0)
        try:
            res = json.loads(buf) if buf else {"ok": False, "error": "no reply"}
        except ValueError:
            res = {"ok": False, "error": "malformed reply"}
        res.update(task=tid, child_cpu_s=round(ru.ru_utime + ru.ru_stime, 3),
                   signal=os.WTERMSIG(status) if os.WIFSIGNALED(status) else None)
        tmp = p + ".tmp"
        json.dump(res, open(tmp, "w"))
        os.replace(tmp, p)
        st["done"] += 1
        st["child_cpu_s"] = round(st["child_cpu_s"] + res["child_cpu_s"], 3)
    st["wall_s"] = round(time.time() - st["t0"], 1)
    json.dump(st, open(os.path.join(out_dir, "status.json"), "w"))
    print(json.dumps(st))


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main(sys.argv[1], sys.argv[2])
