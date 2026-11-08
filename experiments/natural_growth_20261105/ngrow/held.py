"""Phase 2 only (refused without the GO): the arms on one benchmark's HELD half, reuse only (no construction).

    python -I run.py held GROW_DIR OUT_DIR BENCH ARM [--shard I/K]

ARM:
  G0          G0, base search (150,000 executions, 20 CPU-s), two attempts; also records the controller's partial-fit
              criterion (track_partial) that defines the primary population
  S-hole      G0 + the S-hole registry (growth from the system's own holes), base search
  S-shuffled  G0 + the S-shuffled registry, base search
  S-demo      G0 + the S-demo registry, base search
  S-enum      G0 + the S-enum registry, base search
  static      matched static search: G0 with no execution limit and a CPU-time cap of T_static CPU-s per task,
              T_static = (growth's total CPU on this benchmark) / (held tasks of this benchmark), where growth's total
              = the controller on every source task + S-hole's construction gates + its combined regression check +
              S-hole's base searches on the held half. Each static search runs in a child process with a 12 GB
              address-space limit; a child that fails gives no answer (recorded).
An arm whose registry is empty has exactly G0's grammar; its results are G0's (recorded as such, charged G0's CPU).
Writes OUT_DIR/<BENCH>/<ARM>.jsonl (one line per task, appended; resumable).
"""
import json
import os
import resource
import subprocess
import sys
import time

from ngrow import env as E, data as DT, plugin as PL, gate as GT, grow as GR
from cgrow import search as S                                                   # noqa: E402

GROWN = ("S-hole", "S-shuffled", "S-demo", "S-enum")
STATIC_MEM_GB = 12
STATIC_BUDGET = 10 ** 9


def registry(grow_dir, bench, arm):
    return E.load(os.path.join(grow_dir, bench, "registry.json"))["arms"][arm]["registry"]


def read_jsonl(path):
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    r = json.loads(x)
                    out[r["task"]] = r
    return out


def growth_total_cpu(grow_dir, out_dir, bench, ctrl_paths):
    recs = GR.load_records(ctrl_paths, bench)
    ctrl = sum(r["cpu_s"] for r in recs.values())
    reg = E.load(os.path.join(grow_dir, bench, "registry.json"))["arms"]["S-hole"]
    held_rows = read_jsonl(os.path.join(out_dir, bench, "S-hole.jsonl"))
    n_held = len(DT.half("held", (bench,)))
    if len(held_rows) != n_held:
        raise SystemExit("S-hole held runs incomplete: static search needs growth's total CPU")
    held = sum(r["cpu_s"] for r in held_rows.values())
    tot = ctrl + reg["construction_cpu_s"] + reg["combined_regression_cpu_s"] + held
    return {"controller_cpu_s": round(ctrl, 3), "construction_cpu_s": reg["construction_cpu_s"],
            "combined_regression_cpu_s": reg["combined_regression_cpu_s"], "held_search_cpu_s": round(held, 3),
            "total_cpu_s": round(tot, 3), "n_held": n_held, "t_static_cpu_s": round(tot / n_held, 3)}


def child_search(task, cpu_cap):
    """One static search in a child process (address space limited); returns the search record or a failure."""
    lim = STATIC_MEM_GB * (1 << 30)

    def pre():
        os.nice(0)
        resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    payload = json.dumps({"train": task["train"], "test_inputs": task["test_inputs"], "cpu_cap": cpu_cap})
    env = dict(os.environ)
    p = subprocess.run([sys.executable, "-I", os.path.join(E.STUDY, "run.py"), "held", "--child"], input=payload,
                       capture_output=True, text=True, preexec_fn=pre, env=env, timeout=cpu_cap * 20 + 600)
    line = [x for x in p.stdout.splitlines() if x.startswith("RESULT ")]
    if p.returncode != 0 or not line:
        return {"fit": False, "preds": None, "program": None, "cpu_s": None, "calls": None, "stop": "child_failed",
                "returncode": p.returncode, "stderr_tail": p.stderr[-300:]}
    return json.loads(line[0][7:])


def child_main():
    req = json.loads(sys.stdin.read())
    g0b = PL.G0Builder()
    train = [(DT.grid(a), DT.grid(b)) for a, b in req["train"]]
    qs = [DT.grid(q) for q in req["test_inputs"]]
    r = S.run(g0b(), train, qs, budget=STATIC_BUDGET, cpu_cap=req["cpu_cap"], want=2)
    out = {k: r[k] for k in ("fit", "preds", "program", "cpu_s", "calls", "stop", "level_complete")}
    print("RESULT " + json.dumps(out, default=list), flush=True)


def run(grow_dir, out_dir, bench, arm, shard=None, ctrl_paths=None):
    GT.require_phase2()
    rows = DT.half("held", (bench,))
    if shard:
        i, k = (int(x) for x in shard.split("/"))
        rows = [r for n, r in enumerate(rows) if n % k == i]
    tasks = DT.tasks(bench)
    path = os.path.join(out_dir, bench, f"{arm}.jsonl" if not shard else f"{arm}.shard{shard.replace('/', 'of')}.jsonl")
    done = read_jsonl(path)
    g0b = PL.G0Builder()
    info = {}
    if arm in GROWN:
        reg = registry(grow_dir, bench, arm)
        info["registry"] = reg
        if not reg:
            g0_rows = read_jsonl(os.path.join(out_dir, bench, "G0.jsonl"))
            if len(g0_rows) != len(DT.half("held", (bench,))):
                raise SystemExit("G0 held runs incomplete")
        grammar = PL.grammar_with(g0b, reg) if reg else None
    elif arm == "static":
        info = growth_total_cpu(grow_dir, out_dir, bench, ctrl_paths)
        E.dump(os.path.join(out_dir, bench, "STATIC_ALLOWANCE.json"), info)
    for b, fam, tid in rows:
        if tid in done:
            continue
        t = tasks[tid]
        t0 = time.process_time()
        row = {"bench": b, "family": fam, "task": tid, "arm": arm}
        if arm == "G0":
            r = S.run(g0b(), t["train"], t["test_inputs"], budget=S.BASE_BUDGET, cpu_cap=S.BASE_CPU,
                      want=2, track_partial=True)
            part = r.get("partial")
            row["partial_fit"] = None if not part else {"program": part["program"],
                                                        "cells_correct": part["cells_correct"],
                                                        "cells_total": sum(len(y) * len(y[0]) for _, y in t["train"])}
        elif arm in GROWN and grammar is None:
            r = dict(g0_rows[tid])
            row["same_grammar_as"] = "G0"
        elif arm in GROWN:
            r = S.run(grammar, t["train"], t["test_inputs"], budget=S.BASE_BUDGET, cpu_cap=S.BASE_CPU,
                      want=2)
        else:
            r = child_search(t, info["t_static_cpu_s"])
        for k in ("fit", "preds", "program", "cpu_s", "calls", "stop", "level_complete"):
            row[k] = r.get(k)
        row["wall_cpu_s"] = round(time.process_time() - t0, 3)
        with E.open_write(path, "a") as f:
            f.write(json.dumps(row, default=list) + "\n")
        print(json.dumps({"task": tid, "arm": arm, "fit": row["fit"], "cpu_s": row["cpu_s"]}), flush=True)


def main(*args):
    if args and args[0] == "--child":
        return child_main()
    grow_dir, out_dir, bench, arm = (os.path.abspath(args[0]), os.path.abspath(args[1]), args[2], args[3])
    shard, ctrl = None, None
    rest = iter(args[4:])
    for a in rest:
        if a == "--shard":
            shard = next(rest)
        elif a == "--controller":
            ctrl = next(rest)
    run(grow_dir, out_dir, bench, arm, shard, ctrl)


if __name__ == "__main__":
    main(*sys.argv[1:])
