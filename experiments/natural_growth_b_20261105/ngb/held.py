"""Phase 2 only (refused without the GO): the arms on one benchmark's HELD half (amendment 2).

    python -I run.py held LIB_DIR OUT_DIR BENCH ARM [--shard I/K]
    python -I run.py held --child                        (one static search, stdin -> stdout; used by this module)

ARM (code label: arm):
  G0              arm 1: G0, base search (150,000 executions, 20 CPU-s), two attempts; records the partial fit
  lib             arm 2: G0 + the benchmark's frozen library (LIB_DIR/<bench>/library.json), base search
  shuf            arm 3: G0 + the frozen shuffled library (LIB_DIR/shuffled.json), base search
  obj             arm 5: the builder's reuse answers: G0 + the frozen object registry (own holes), base search
  obj_shuf        arm 6: the same with the shuffled object registry (other benchmarks' operations, same count)
  construct       arm 7: the builder's construction answers on the task's own demonstrations (G0 + the registry,
                  then the holes, the constructor and at most 3 retries); never a test output
  construct_shuf  arm 8: the same with donor demonstrations (another family's held task) and the task's test inputs
  static_lib      arm 4a: G0, no execution limit, CPU cap T(b, lib) per task
  static_obj      arm 4b: G0, no execution limit, CPU cap T(b, obj) per task
  static_construct arm 4c: G0, no execution limit, CPU cap T(b, construct) per task
Binding: LIB_DIR's library.json and shuffled.json, and the object registries, must have the digests recorded in
FREEZE.json; otherwise the run is refused. G0 is study A's grammar with the seed-independent enumeration order
(ngb.ops.G0Builder), passed to the builder's functions too.
T(b, arm) = [the arm's whole source-half cost (Athe-measured, scaled by NGB_CPU_SCALE) + the arm's CPU on the held
half of b] / (held tasks of b). Static searches run in child processes with a 12 GB address-space limit; a child
that fails, times out or returns nothing gives a durable failure row (no answer), never a missing row; a failure row
is charged the child's own CPU as the parent measures it (RUSAGE_CHILDREN; it includes the child's start-up and
grammar build, and a killed or timed-out child is charged what it used); a non-static failure row is charged the CPU
this process spent on the task. A child
killed by a signal (for example the kernel's memory) gives a "child_killed" row, and after the stage that task is
run once more alone (`--retry-killed`, <arm>.retry.jsonl), whose result stands (amendment 3). Arm 8 with no task of
another family in the benchmark gives a durable "no_donor" row (a defect on the real held halves: the report treats
it, like "arm_error", as INVALID).
Every row carries its provenance: bench, family, task, arm, the GO's sha256, the registry's digest (sha256 over the
operations' identifiers), the frozen library digests, the G0 digest, the CPU scale and the stop reason or stage. Any
exception while a task is processed produces a failure row with the error text. Writes OUT_DIR/<bench>/<ARM>.jsonl
(or a shard file), one line per task, appended; resumable (a task already in the file is skipped).
"""
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
import traceback

from ngb import env as E, gate as GT, ops as OP, object_arm as OA
from ngrow import data as DT
from cgrow import search as S
from a2 import arcdsl as D

GROWN = {"lib": 2, "shuf": 3, "obj": 5, "obj_shuf": 6}
CONSTRUCT = {"construct": 7, "construct_shuf": 8}
STATIC = {"static_lib": "lib", "static_obj": "obj", "static_construct": "construct"}
STATIC_MEM_GB = 12
STATIC_BUDGET = 10 ** 9
RUN = os.path.join(E.STUDY, "run.py")
REL = os.path.relpath(E.STUDY, E.REPO)
ROW_KEYS = ("fit", "preds", "program", "cpu_s", "calls", "stop", "level_complete")
BUILDER_KEYS = ("stage", "candidates", "candidates_loo", "construction_cpu_s", "base_cpu_s", "op", "counts")


def read_rows(path):
    """Every row of a jsonl file, in order (duplicates are kept for the validator to see)."""
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    out.append(json.loads(x))
    return out


def rows_by_task(path):
    """{task: row}; raises on a duplicate task."""
    out = {}
    for r in read_rows(path):
        if r["task"] in out:
            raise RuntimeError(f"duplicate row for task {r['task']} in {path}")
        out[r["task"]] = r
    return out


def bind_library(lib_dir, bench):
    """LIB_DIR must hold the frozen library files (sha256 as in FREEZE.json); returns their digests."""
    out = {}
    for name, rel in (("library", f"{REL}/feasibility/library/{bench}/library.json"),
                      ("shuffled", f"{REL}/feasibility/library/shuffled.json")):
        p = os.path.join(lib_dir, bench, "library.json") if name == "library" else os.path.join(lib_dir, "shuffled.json")
        want = GT.frozen_hash(rel)
        have = E.sha_file(p) if os.path.exists(p) else None
        if want is None or have != want:
            raise RuntimeError(f"{name} file for {bench} is not the frozen one ({p})")
        out[name] = have
    return out


def registry_digest(ops):
    return hashlib.sha256(json.dumps([getattr(o, "text", None) or o.sid for o in ops]).encode()).hexdigest()


def library_ops(lib_dir, bench, arm, g0b):
    ev = D.Evaluator(g0b.g.fns, g0b.g.consts)
    if arm == "lib":
        return OP.ops_from_json(E.load(os.path.join(lib_dir, bench, "library.json"))["library"], ev)
    if arm == "shuf":
        return OP.ops_from_json(E.load(os.path.join(lib_dir, "shuffled.json"))[bench]["library"], ev)
    if arm in ("obj", "construct"):
        return OA.ops(bench)
    if arm == "obj_shuf":
        return OA.shuffled_ops(bench)[0]
    raise ValueError(arm)


def source_cost(lib_dir, bench, arm):
    if arm == "lib":
        return E.load(os.path.join(lib_dir, bench, "library.json"))["cpu_s"]["total_charged"]
    return OA.source_cost(bench)


def allowance(lib_dir, out_dir, bench, arm):
    """T(b, arm): the arm's Athe-measured source-half cost, scaled by this machine's speed factor (NGB_CPU_SCALE,
    1.0 on Athe), plus its CPU on the held half measured here, per held task. Requires the arm's held rows to be
    complete and unique."""
    rows = rows_by_task(os.path.join(out_dir, bench, f"{arm}.jsonl"))
    ids = [t for _, _, t in DT.half("held", (bench,))]
    missing = [t for t in ids if t not in rows]
    if missing:
        raise RuntimeError(f"{arm} held rows incomplete ({len(missing)} missing): the static allowance needs them")
    held = sum((rows[t]["cpu_s"] or 0) for t in ids)
    scale = float(os.environ.get("NGB_CPU_SCALE", "1.0"))
    src = source_cost(lib_dir, bench, arm) * scale
    return {"arm": arm, "source_cost_cpu_s_scaled": round(src, 3), "cpu_scale": scale,
            "held_cpu_s": round(held, 3), "total_cpu_s": round(src + held, 3), "n_held": len(ids),
            "t_static_cpu_s": round((src + held) / len(ids), 3)}


def failure(stop, detail=""):
    return {"fit": False, "preds": None, "program": None, "cpu_s": None, "calls": None, "stop": stop,
            "level_complete": None, "failure_detail": detail[:400]}


def child_search(task, cpu_cap):
    """One static search in a child process (address space limited). Every failure mode is a durable row."""
    lim = STATIC_MEM_GB * (1 << 30)

    def pre():
        resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    payload = json.dumps({"train": task["train"], "test_inputs": task["test_inputs"], "cpu_cap": cpu_cap})
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)

    def measured(r):
        """The child's own CPU, measured by the parent (RUSAGE_CHILDREN delta: the children of one shard run one at
        a time). It includes the child's start-up and grammar build besides the search, and a killed or timed-out
        child is charged what it used before it ended."""
        ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        r["child_cpu_measured_s"] = round((ru1.ru_utime + ru1.ru_stime) - (ru0.ru_utime + ru0.ru_stime), 3)
        if r.get("cpu_s") is None:
            r["cpu_s"] = r["child_cpu_measured_s"]
            r["cpu_s_source"] = "child CPU measured by the parent"
        return r
    try:
        p = subprocess.run([sys.executable, "-I", RUN, "held", "--child"], input=payload, capture_output=True,
                           text=True, preexec_fn=pre, timeout=cpu_cap * 20 + 600, env=dict(os.environ))
    except subprocess.TimeoutExpired:
        return measured(failure("child_timeout", f"wall limit {cpu_cap * 20 + 600:.0f} s"))
    except Exception as e:                                                 # noqa: BLE001
        return measured(failure("child_error", f"{type(e).__name__}: {e}"))
    line = [x for x in p.stdout.splitlines() if x.startswith("RESULT ")]
    if p.returncode < 0:                                       # killed by a signal (for example the kernel's memory)
        return measured(failure("child_killed", f"signal {-p.returncode}; stderr: {p.stderr[-300:]}"))
    if p.returncode != 0 or not line:
        return measured(failure("child_failed", f"returncode {p.returncode}; stderr: {p.stderr[-300:]}"))
    try:
        return measured(json.loads(line[-1][7:]))
    except json.JSONDecodeError as e:
        return measured(failure("child_unreadable", str(e)))


def child_main():
    req = json.loads(sys.stdin.read())
    g0b = OP.G0Builder()
    train = [(DT.grid(a), DT.grid(b)) for a, b in req["train"]]
    qs = [DT.grid(q) for q in req["test_inputs"]]
    r = S.run(g0b(), train, qs, budget=STATIC_BUDGET, cpu_cap=req["cpu_cap"], want=2)
    print("RESULT " + json.dumps({k: r[k] for k in ROW_KEYS}, default=list), flush=True)


def builder_row(r):
    """A builder result as a row fragment (the base keys plus the builder's own)."""
    out = {"fit": r.get("fit"), "preds": r.get("preds"), "program": r.get("program"), "cpu_s": r.get("cpu_s"),
           "calls": None, "stop": r.get("stage"), "level_complete": None}
    for k in BUILDER_KEYS:
        if k in r:
            out[k] = r[k] if k != "op" else (r[k].get("sid") if isinstance(r[k], dict) else r[k])
    if "retries" in r:
        out["retries"] = len(r["retries"])
    return out


def run(lib_dir, out_dir, bench, arm, shard=None):
    go_sha = GT.require_go()
    digests = bind_library(lib_dir, bench)
    rows = DT.half("held", (bench,))
    if shard:
        i, k = (int(x) for x in shard.split("/"))
        rows = [r for n, r in enumerate(rows) if n % k == i]
    tasks = DT.tasks(bench)
    path = os.path.join(out_dir, bench, f"{arm}.jsonl" if not shard else f"{arm}.shard{shard.replace('/', 'of')}.jsonl")
    done = rows_by_task(path)
    g0b = OP.G0Builder()
    info, grammar, g0_rows, reg_digest, op_list = {}, None, None, None, []
    if arm in GROWN or arm in CONSTRUCT:
        if arm in ("obj", "obj_shuf", "construct", "construct_shuf") and not OA.available():
            op_list, info = [], {"available": False}
        else:
            op_list = library_ops(lib_dir, bench, "construct" if arm == "construct_shuf" else arm, g0b)
            info = {"available": True}
            if arm == "obj_shuf":
                info["shuffle"] = OA.shuffled_ops(bench)[1]
        reg_digest = registry_digest(op_list)
        info["registry"] = [getattr(o, "sid", str(o)) for o in op_list]
        if arm in GROWN and arm in ("lib", "shuf") and op_list:
            grammar = OP.grammar_with(g0b, op_list)
        elif arm in GROWN and not op_list:
            g0_rows = rows_by_task(os.path.join(out_dir, bench, "G0.jsonl"))
            missing = [t for _, _, t in DT.half("held", (bench,)) if t not in g0_rows]
            if missing:
                raise RuntimeError(f"G0 held rows incomplete ({len(missing)} missing)")
    elif arm in STATIC:
        info = allowance(lib_dir, out_dir, bench, STATIC[arm])
        E.dump(os.path.join(out_dir, bench, f"ALLOWANCE_{arm}.json"), info)
    if arm in CONSTRUCT and not info.get("available"):
        raise RuntimeError("construction arms need the object-growth contract")
    scale = float(os.environ.get("NGB_CPU_SCALE", "1.0"))
    for b, fam, tid in rows:
        if tid in done:
            continue
        t = tasks[tid]
        t0 = time.process_time()
        row = {"bench": b, "family": fam, "task": tid, "arm": arm, "go_sha256": go_sha, "cpu_scale": scale,
               "library_sha256": digests["library"], "shuffled_sha256": digests["shuffled"],
               "registry_sha256": reg_digest, "g0_sha256": g0b.sha}
        try:
            if arm == "G0":
                r = S.run(g0b(), t["train"], t["test_inputs"], budget=S.BASE_BUDGET, cpu_cap=S.BASE_CPU, want=2,
                          track_partial=True)
                part = r.get("partial")
                row["partial_fit"] = None if not part else {
                    "program": part["program"], "cells_correct": part["cells_correct"],
                    "cells_total": sum(len(y) * len(y[0]) for _, y in t["train"])}
            elif arm in GROWN and g0_rows is not None:
                r = dict(g0_rows[tid])
                row["same_grammar_as"] = "G0"
                row["available"] = info.get("available", True)
            elif arm in ("lib", "shuf"):
                r = S.run(grammar, t["train"], t["test_inputs"], budget=S.BASE_BUDGET, cpu_cap=S.BASE_CPU, want=2)
            elif arm in ("obj", "obj_shuf"):
                r = builder_row(OA.reuse(t, op_list))
            elif arm == "construct":
                r = builder_row(OA.construct(t, op_list))
            elif arm == "construct_shuf":
                donor = OA.donor_of(b, tid)
                row["donor"] = donor
                if donor is None:                                  # no task of another family: a durable row
                    r = failure("no_donor", "no held task of another family in this benchmark")
                else:
                    r = builder_row(OA.construct({"train": tasks[donor]["train"], "test_inputs": t["test_inputs"]},
                                                 op_list))
            else:
                r = child_search(t, info["t_static_cpu_s"])
        except Exception as e:                                             # noqa: BLE001
            r = failure("arm_error", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-300:]}")
        for k in ROW_KEYS + ("failure_detail", "retries", "child_cpu_measured_s", "cpu_s_source") + BUILDER_KEYS:
            if k in r:
                row[k] = r[k]
        for k in ROW_KEYS:
            row.setdefault(k, None)
        row["wall_cpu_s"] = round(time.process_time() - t0, 3)
        if row["cpu_s"] is None:                                   # a failure row: charge the CPU this process spent
            row["cpu_s"] = row["wall_cpu_s"]
            row["child_cpu_unknown"] = str(row["stop"]).startswith("child_")
        with E.open_write(path, "a") as f:
            f.write(json.dumps(row, default=list) + "\n")
        print(json.dumps({"task": tid, "arm": arm, "fit": row["fit"], "stop": row["stop"], "cpu_s": row["cpu_s"]}),
              flush=True)


def retry_killed(lib_dir, out_dir, bench, arm):
    """After a static stage: every task whose child was killed by a signal is run once more, alone (this single
    process, one child at a time, no other stage running), and that result stands. Rows go to <arm>.retry.jsonl with
    the original stop recorded; resumable."""
    go_sha = GT.require_go()
    if arm not in STATIC:
        raise SystemExit("retry applies to the static arms only")
    d = os.path.join(out_dir, bench)
    killed = {}
    for p in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if p == f"{arm}.jsonl" or p.startswith(f"{arm}.shard"):
            for r in read_rows(os.path.join(d, p)):
                if r.get("stop") == "child_killed":
                    killed[r["task"]] = r
    path = os.path.join(d, f"{arm}.retry.jsonl")
    done = rows_by_task(path)
    info = E.load(os.path.join(d, f"ALLOWANCE_{arm}.json"))
    tasks = DT.tasks(bench)
    for tid, orig in sorted(killed.items()):
        if tid in done:
            continue
        t0 = time.process_time()
        r = child_search(tasks[tid], info["t_static_cpu_s"])
        row = {k: orig[k] for k in ("bench", "family", "task", "arm", "go_sha256", "cpu_scale", "library_sha256",
                                    "shuffled_sha256", "registry_sha256", "g0_sha256")}
        row.update({k: r.get(k) for k in ROW_KEYS})
        for k in ("failure_detail", "child_cpu_measured_s", "cpu_s_source"):
            if k in r:
                row[k] = r[k]
        row["retry_of"] = {"stop": orig["stop"], "failure_detail": orig.get("failure_detail")}
        row["wall_cpu_s"] = round(time.process_time() - t0, 3)
        if row["cpu_s"] is None:
            row["cpu_s"] = row["wall_cpu_s"]
            row["child_cpu_unknown"] = True
        if row.get("go_sha256") != go_sha:
            raise RuntimeError("a killed row of another GO")
        with E.open_write(path, "a") as f:
            f.write(json.dumps(row, default=list) + "\n")
        print(json.dumps({"retry": tid, "arm": arm, "stop": row["stop"]}), flush=True)
    print(json.dumps({"bench": bench, "arm": arm, "killed": len(killed)}), flush=True)


def main(*args):
    if args and args[0] == "--child":
        return child_main()
    if "--retry-killed" in args:
        return retry_killed(os.path.abspath(args[0]), os.path.abspath(args[1]), args[2], args[3])
    lib_dir, out_dir, bench, arm = os.path.abspath(args[0]), os.path.abspath(args[1]), args[2], args[3]
    shard = None
    it = iter(args[4:])
    for a in it:
        if a == "--shard":
            shard = next(it)
    run(lib_dir, out_dir, bench, arm, shard)


if __name__ == "__main__":
    main(*sys.argv[1:])
