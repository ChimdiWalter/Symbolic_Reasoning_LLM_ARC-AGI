"""Configuration B: the CAST side process. It runs on CPU next to the neural GPU workers. It calls the CAST package
named in the build manifest once per puzzle, in a freshly forked child, and writes one result file per puzzle.

  python -m sfb.cast_side --challenges C --out DIR --package NAME --entry FUNC --deadline UNIX_TS
      [--mode grids|evidence] [--task-ids a,b,...] [--cpu-s 15] [--wall-s 30] [--grace-s 10] [--nice 10]

Modes:
- grids: the entry returns one grid or None per test input, or a details dict with "grids" (cast_v1's
  cast_candidates and the constructor-package contract).
- evidence: the entry is cast_selective_v2's evaluate(task, cpu_s, wall_s). The child turns its report into plain
  JSON: status, and per query the first complete candidate and each policy's accepted grid. The parent re-validates
  every grid. The merge later applies the package's own insert_attempt2 to that report.

What it guarantees (each item is tested in configs/tests/test_cfg_b.py):
- State resets between puzzles. CAST code runs only inside a child forked for that puzzle, and the parent never calls
  it. So nothing a call leaves behind reaches the next puzzle: module caches, globals, timers, signal handlers or
  memory.
- Caps are enforced at process level, not only configured.
  - The package's own caps are passed through: `cpu_s` and `wall_s`.
  - Backstop 1: the child gets RLIMIT_CPU of cpu_s + grace_s seconds, enforced by the kernel.
  - Backstop 2: the parent SIGKILLs the child at wall_s + grace_s seconds of wall time.
  - The child is always reaped (wait4), and its CPU time is recorded.
- Total budget: a puzzle starts only if it can finish (wall_s + grace_s) before --deadline. The notebook additionally
  kills this whole process group at the deadline.
- Output is re-validated here: one entry per test input, each None or a rectangular grid of 1..30 x 1..30 ints in
  0..9. Anything else becomes None and is counted as malformed. Result files are written atomically.
- Fail-safe: no exception leaves this process. A failure leaves that puzzle without a CAST answer, so it keeps
  configuration A's attempts.
- Only the puzzle's demonstrations and test inputs are passed to CAST (the task dict is rebuilt from those fields).
"""
import argparse
import json
import os
import select
import signal
import sys
import time

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")                    # one core for CAST; set before numpy is imported

MAX_PAYLOAD = 4 << 20                                  # bytes; a larger reply is treated as malformed


def valid_grid(g):
    """A valid ARC grid: a non-empty rectangular list of lists of ints 0..9, at most 30 x 30 (bools rejected)."""
    if not isinstance(g, list) or not 1 <= len(g) <= 30:
        return False
    w = None
    for row in g:
        if not isinstance(row, list) or not 1 <= len(row) <= 30:
            return False
        if w is None:
            w = len(row)
        elif len(row) != w:
            return False
        for v in row:
            if type(v) is not int or not 0 <= v <= 9:
                return False
    return True


def clean_task(t):
    """Only what the solver may see: demonstration pairs and test inputs."""
    return {"train": [{"input": p["input"], "output": p["output"]} for p in t["train"]],
            "test": [{"input": x["input"]} for x in t["test"]]}


def atomic_json(path, obj):
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _to_grid(g):
    """A grid as a list of lists of ints, None, or the marker "MALFORMED"."""
    if g is None:
        return None
    try:
        import numpy as np
        a = np.asarray(g)
        if a.ndim != 2 or a.dtype.kind not in "iub":
            return "MALFORMED"
        return [[int(v) for v in row] for row in a.tolist()]
    except Exception:                                  # noqa: BLE001
        return "MALFORMED"


def compact_evidence(rep):
    """The parts of an evaluate() report that the merge needs, as plain JSON (computed in the child)."""
    if not isinstance(rep, dict):
        return {"status": "MALFORMED_REPORT", "queries": None}
    out = {"status": str(rep.get("status"))[:60], "version": str(rep.get("version"))[:60],
           "n_demos": rep.get("n_demos") if isinstance(rep.get("n_demos"), int) else None,
           "cpu_s": rep.get("cpu_s") if isinstance(rep.get("cpu_s"), (int, float)) else None,
           "wall_s": rep.get("wall_s") if isinstance(rep.get("wall_s"), (int, float)) else None, "queries": []}
    qs = rep.get("queries")
    if not isinstance(qs, list):
        out.update(status="MALFORMED_REPORT", queries=None)
        return out
    for q in qs:
        if not isinstance(q, dict):
            out["queries"].append(None)
            continue
        acc = q.get("accepted") if isinstance(q.get("accepted"), dict) else {}
        accm = q.get("accepted_module") if isinstance(q.get("accepted_module"), dict) else {}
        cm = q.get("candidate_module")
        out["queries"].append({"candidate": _to_grid(q.get("candidate")),
                               "candidate_module": None if cm is None else str(cm)[:20],
                               "accepted": {str(k)[:10]: _to_grid(v) for k, v in acc.items()},
                               "accepted_module": {str(k)[:10]: (None if v is None else str(v)[:20])
                                                   for k, v in accm.items()}})
    return out


def _child(fn, task, kwargs, w, cpu_limit, mode="grids"):
    """Runs in the forked child: never returns."""
    code = 0
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))      # a CPU-limit kill leaves no core file
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 5))
        res = fn(task, **kwargs)
        if mode == "evidence":
            res = compact_evidence(res)
        payload = json.dumps({"ok": True, "res": res}, default=str).encode()
    except BaseException as e:                         # noqa: BLE001  fail-safe by contract
        payload = json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}).encode()
        code = 3
    try:
        view = memoryview(payload)
        while view:
            n = os.write(w, view)
            view = view[n:]
    except BaseException:                              # noqa: BLE001
        code = 4
    os._exit(code)


def run_one(fn, task, kwargs, wall_limit, cpu_limit, mode="grids"):
    """Fork, run, collect. Returns (reply dict or None, child record)."""
    r, w = os.pipe()
    t0 = time.time()
    pid = os.fork()
    if pid == 0:                                       # child
        os.close(r)
        _child(fn, task, kwargs, w, cpu_limit, mode)
    os.close(w)
    buf, killed, too_big = bytearray(), False, False
    end = t0 + wall_limit
    while True:
        left = end - time.time()
        if left <= 0:
            os.kill(pid, signal.SIGKILL)
            killed = True
            break
        ready, _, _ = select.select([r], [], [], min(left, 1.0))
        if not ready:
            continue
        chunk = os.read(r, 1 << 16)
        if not chunk:                                  # end of file: the child has finished writing
            break
        buf += chunk
        if len(buf) > MAX_PAYLOAD:
            os.kill(pid, signal.SIGKILL)
            killed = too_big = True
            break
    os.close(r)
    _, status, ru = os.wait4(pid, 0)                   # always reap
    rec = {"wall_s": round(time.time() - t0, 3), "cpu_s": round(ru.ru_utime + ru.ru_stime, 3),
           "exit": os.WEXITSTATUS(status) if os.WIFEXITED(status) else None,
           "signal": os.WTERMSIG(status) if os.WIFSIGNALED(status) else None,
           "killed_by_parent": killed, "too_big": too_big}
    reply = None
    if not killed and buf:
        try:
            reply = json.loads(bytes(buf))
        except ValueError:
            reply = None
    return reply, rec


def interpret(reply, rec, n_test):
    """The reply as {grids, status, module, program, ...}; malformed parts become None."""
    out = {"grids": [None] * n_test, "module": [None] * n_test, "program": [None] * n_test, "malformed": 0}
    if rec["killed_by_parent"]:
        out["status"] = "KILLED_TOO_BIG" if rec["too_big"] else "KILLED_WALL"
        return out
    if rec["signal"] is not None:
        out["status"] = "KILLED_CPU" if rec["signal"] in (signal.SIGXCPU, signal.SIGKILL) else f"SIGNAL_{rec['signal']}"
        return out
    if not isinstance(reply, dict) or not reply.get("ok"):
        out["status"] = "ERROR_CHILD" if isinstance(reply, dict) else "ERROR_NO_REPLY"
        out["error"] = reply.get("error") if isinstance(reply, dict) else None
        return out
    res = reply.get("res")
    grids = res.get("grids") if isinstance(res, dict) else res
    out["status"] = str(res.get("status", "OK"))[:60] if isinstance(res, dict) else "OK"
    if isinstance(res, dict):
        out["version"] = str(res.get("version"))[:60]
        out["cast_cpu_s"] = res.get("cpu_s") if isinstance(res.get("cpu_s"), (int, float)) else None
    if not isinstance(grids, list) or len(grids) != n_test:
        out["malformed"] = n_test
        out["status"] = "MALFORMED_SHAPE"
        return out
    for j, g in enumerate(grids):
        if g is None:
            continue
        if valid_grid(g):
            out["grids"][j] = g
            if isinstance(res, dict):
                for k in ("module", "program"):
                    v = res.get(k)
                    if isinstance(v, list) and j < len(v):
                        out[k][j] = str(v[j])[:300] if v[j] is not None else None
        else:
            out["malformed"] += 1
    return out


def interpret_evidence(reply, rec, n_test):
    """An evidence reply: kill and error handling as for grids; every grid in the report re-validated."""
    out = {"grids": [None] * n_test, "module": [None] * n_test, "program": [None] * n_test, "malformed": 0,
           "evidence": None}
    if rec["killed_by_parent"]:
        out["status"] = "KILLED_TOO_BIG" if rec["too_big"] else "KILLED_WALL"
        return out
    if rec["signal"] is not None:
        out["status"] = "KILLED_CPU" if rec["signal"] in (signal.SIGXCPU, signal.SIGKILL) else f"SIGNAL_{rec['signal']}"
        return out
    if not isinstance(reply, dict) or not reply.get("ok"):
        out["status"] = "ERROR_CHILD" if isinstance(reply, dict) else "ERROR_NO_REPLY"
        out["error"] = reply.get("error") if isinstance(reply, dict) else None
        return out
    ev = reply.get("res")
    if not isinstance(ev, dict) or not isinstance(ev.get("queries"), list) or len(ev["queries"]) != n_test:
        out.update(status="MALFORMED_SHAPE", malformed=n_test)
        return out
    clean_q = []
    for j, q in enumerate(ev["queries"]):
        if not isinstance(q, dict):
            clean_q.append({"candidate": None, "candidate_module": None, "accepted": {}, "accepted_module": {}})
            out["malformed"] += 1
            continue
        c = q.get("candidate")
        if c is not None and not valid_grid(c):
            out["malformed"] += 1
            c = None
        acc = {}
        for k, g in (q.get("accepted") or {}).items():
            if g is not None and not valid_grid(g):
                out["malformed"] += 1
                g = None
            acc[k] = g
        clean_q.append({"candidate": c, "candidate_module": q.get("candidate_module"), "accepted": acc,
                        "accepted_module": q.get("accepted_module") or {}})
        out["grids"][j] = c
        out["module"][j] = q.get("candidate_module") if c is not None else None
    out["status"] = str(ev.get("status"))[:60]
    out["version"] = ev.get("version")
    out["cast_cpu_s"] = ev.get("cpu_s")
    out["evidence"] = dict(ev, queries=clean_q)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenges", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--entry", required=True)
    ap.add_argument("--deadline", type=float, required=True)
    ap.add_argument("--task-ids", default="")
    ap.add_argument("--cpu-s", type=float, default=15.0)
    ap.add_argument("--wall-s", type=float, default=30.0)
    ap.add_argument("--grace-s", type=float, default=10.0)
    ap.add_argument("--nice", type=int, default=10)
    ap.add_argument("--details", type=int, default=1)
    ap.add_argument("--mode", default="grids", choices=["grids", "evidence"])
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    t_start = time.time()
    st = {"t_start": t_start, "deadline": a.deadline, "package": a.package, "entry": a.entry, "cpu_s": a.cpu_s,
          "wall_s": a.wall_s, "grace_s": a.grace_s, "done": 0, "answered_tasks": 0, "answered_outputs": 0,
          "malformed_outputs": 0, "statuses": {}, "child_cpu_s": 0.0, "stopped": None, "error": None,
          "python": sys.version.split()[0], "pid": os.getpid()}
    status_path = os.path.join(a.out, "status.json")
    try:
        try:
            os.nice(a.nice)
        except OSError:
            pass
        import importlib
        mod = importlib.import_module(a.package)
        fn = getattr(mod, a.entry)
        st["version"] = str(getattr(mod, "VERSION", None))
        try:
            import numpy
            st["numpy"] = numpy.__version__
        except Exception:                              # noqa: BLE001
            st["numpy"] = None
        ch = json.load(open(a.challenges))
        ids = [x for x in a.task_ids.split(",") if x in ch] if a.task_ids else list(ch)
        st["n_tasks"] = len(ids)
        atomic_json(status_path, st)
        kwargs = {"cpu_s": a.cpu_s, "wall_s": a.wall_s}
        if a.details and a.mode == "grids":
            kwargs["details"] = True
        st["mode"] = a.mode
        wall_limit = a.wall_s + a.grace_s
        cpu_limit = int(a.cpu_s + a.grace_s) + 1
        for tid in ids:
            if time.time() + wall_limit > a.deadline:
                st["stopped"] = "budget"
                break
            t = clean_task(ch[tid])
            n_test = len(t["test"])
            try:
                reply, rec = run_one(fn, t, kwargs, wall_limit, cpu_limit, a.mode)
                res = (interpret_evidence if a.mode == "evidence" else interpret)(reply, rec, n_test)
            except Exception as e:                     # noqa: BLE001  (e.g. fork failed): no answer for this task
                rec = {"error": f"{type(e).__name__}: {e}"[:200]}
                res = {"grids": [None] * n_test, "module": [None] * n_test, "program": [None] * n_test,
                       "malformed": 0, "status": "ERROR_PARENT"}
            res.update(task=tid, n_test=n_test, child=rec)
            atomic_json(os.path.join(a.out, f"{tid}.json"), res)
            st["done"] += 1
            k = sum(g is not None for g in res["grids"])
            st["answered_outputs"] += k
            st["answered_tasks"] += int(k > 0)
            st["malformed_outputs"] += res.get("malformed", 0)
            st["statuses"][res["status"]] = st["statuses"].get(res["status"], 0) + 1
            st["child_cpu_s"] = round(st["child_cpu_s"] + float(rec.get("cpu_s", 0.0) or 0.0), 3)
            st["t_now"] = time.time()
            atomic_json(status_path, st)
        else:
            st["stopped"] = "finished"
    except BaseException as e:                         # noqa: BLE001  fail-safe by contract
        st["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        st["stopped"] = st["stopped"] or "error"
    st["wall_s"] = round(time.time() - t_start, 2)
    try:
        atomic_json(status_path, st)
    except BaseException:                              # noqa: BLE001
        pass
    print(json.dumps({k: st.get(k) for k in ("done", "n_tasks", "answered_tasks", "answered_outputs", "stopped",
                                              "error", "wall_s")}), flush=True)


if __name__ == "__main__":
    main()
