"""Orchestrator and GPU workers: independent replicas (one per GPU) pull tasks from a shared queue, write each task's
candidate pool atomically, and the orchestrator keeps submission.json valid at all times (fallbacks first, then
updated atomically as pools arrive). The orchestrator is also the global watchdog: at its deadline it stops the
workers and writes the final file.

  python -m sf.runner orchestrate --challenges C --model M --out DIR --submission PATH [options]
  python -m sf.runner worker --rank R --challenges C --model M --out DIR --deadline UNIX_TS [options]
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import traceback

from . import select as S
from . import textfmt as F


def atomic_json(path, obj):
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def task_cost(t):
    n = sum(len(F.grid_ids(g)) for p in t["train"] for g in (p["input"], p["output"]))
    return len(t["test"]) * (n + max(len(F.grid_ids(x["input"])) for x in t["test"]))


def order_tasks(ch):
    """Largest first, so that the long tasks do not finish last."""
    return sorted(ch, key=lambda k: -task_cost(ch[k]))


# ----- worker ----------------------------------------------------------------------------------------------------
def claim(out, tid, rank):
    try:
        fd = os.open(os.path.join(out, "claims", tid), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, str(rank).encode())
    os.close(fd)
    return True


def peak_gb():
    import torch
    return round(torch.cuda.max_memory_allocated() / 1e9, 2) if torch.cuda.is_available() else 0.0


def preserve_query_results(current, incoming):
    """Retain the latest nonempty pool at each original query index.

    Do not mix scores across budgets or compact empty slots. A nonempty retry
    keeps the baseline choice; an empty/missing retry cannot erase a prior pool.
    """
    if not isinstance(incoming, list):
        return current
    if current is None:
        return incoming[:]
    kept = current[:]
    for index, result in enumerate(incoming):
        if index >= len(kept):
            kept.append(result)
        elif result.get("candidates"):
            kept[index] = result
    return kept


def selected_snapshot(task, outputs, method):
    selected = []
    for j, query in enumerate(task["test"]):
        pool = outputs[j].get("candidates", []) if outputs and j < len(outputs) else []
        selected.append(S.two_attempts(pool, query["input"], S.rank(pool, method)) if pool else None)
    return selected


def checkpoint_outputs(path, task_id):
    try:
        if os.path.getsize(path) > 64 * 1024 * 1024:
            return None
        with open(path) as f:
            value = json.load(f)
        if not isinstance(value, dict):
            return None
        outputs = value.get("outputs")
        if (value.get("task") == task_id and isinstance(outputs, list)
                and all(isinstance(o, dict) and isinstance(o.get("candidates"), list) for o in outputs)):
            return outputs
    except (OSError, ValueError, RecursionError):
        pass
    return None


def worker(a):
    import torch
    from .lm import LM
    from .predict import predict_task, task_seed
    ch = json.load(open(a.challenges))
    queue = json.load(open(os.path.join(a.out, "queue.json")))
    log = open(os.path.join(a.out, "workers", f"{a.rank}.log"), "a")

    def say(**kw):
        kw["t"] = round(time.time(), 1)
        log.write(json.dumps(kw) + "\n")
        log.flush()
    dev = os.environ.get("SF_DEVICE", "cuda:0")
    lm = LM(a.model, device=dev)
    say(event="loaded", load_s=round(lm.load_s, 1), dtype=str(lm.dtype),
        gpu=torch.cuda.get_device_name(0) if dev.startswith("cuda") else dev)
    ttt = None
    if a.ttt_steps > 0:
        from .ttt import TTT
        ttt = TTT(lm, rank=a.ttt_rank, alpha=a.ttt_alpha, lr=a.ttt_lr, max_tokens=a.ttt_max_tokens)
        import peft
        say(event="ttt", rank=a.ttt_rank, alpha=a.ttt_alpha, lr=a.ttt_lr, steps=a.ttt_steps, params=ttt.n_params,
            peft=peft.__version__, peft_file=peft.__file__)
    done = 0
    for tid in queue:
        if time.time() > a.deadline - 30:
            say(event="deadline")
            break
        pool_path = os.path.join(a.out, "pools", f"{tid}.json")
        if os.path.exists(pool_path) or not claim(a.out, tid, a.rank):
            continue
        left = sum(1 for k in queue if not os.path.exists(os.path.join(a.out, "claims", k)))
        share = (a.deadline - time.time() - a.reserve_s) / max(1.0, left / a.n_workers + 1)
        task_deadline = min(a.deadline, time.time() + max(20.0, min(a.task_cap_s, share)))
        t0 = time.time()
        progress_path = os.path.join(a.out, "progress", f"{tid}.json")
        res, err, tstats = checkpoint_outputs(progress_path, tid), None, None

        def save_query(index, outputs):
            nonlocal res
            res = preserve_query_results(res, outputs)
            try:
                atomic_json(progress_path, {"task": tid, "outputs": res,
                            "selected": selected_snapshot(ch[tid], res, a.method),
                            "query": index, "rank": a.rank, "stage": "QUERY_CHECKPOINT"})
            except OSError as error:
                say(event="checkpoint_error", error=type(error).__name__)

        if ttt is not None:                   # a fresh adapter per task, trained on its demonstrations only
            import numpy as np
            seed = task_seed(tid, 99)
            pairs = [(np.asarray(p["input"]), np.asarray(p["output"])) for p in ch[tid]["train"]]
            try:
                tstats = ttt.train(pairs, a.ttt_steps, seed, deadline=t0 + a.ttt_frac * (task_deadline - t0))
            except Exception as e:
                torch.cuda.empty_cache()
                ttt.reset(seed)                 # back to the base model for this task
                tstats = {"error": type(e).__name__}
        for attempt in range(2):
            try:
                kw = dict(n_gen=a.n_gen, n_score=a.n_score, max_prompt=a.max_prompt, deadline=task_deadline, on_query=save_query)
                if attempt:
                    kw.update(n_gen=max(1, a.n_gen // 2), n_score=max(1, a.n_score // 2),
                              max_prompt=a.max_prompt // 2)
                incoming = predict_task(lm, tid, ch[tid], **kw)
                res = preserve_query_results(res, incoming)
                break
            except torch.cuda.OutOfMemoryError as e:
                res = preserve_query_results(res, getattr(e, "partial_outputs", None))
                err = "oom"
                torch.cuda.empty_cache()
            except Exception as e:
                res = preserve_query_results(res, getattr(e, "partial_outputs", None))
                err = traceback.format_exc(limit=3)
                torch.cuda.empty_cache()
        atomic_json(pool_path, {"task": tid, "outputs": res, "selected": selected_snapshot(ch[tid], res, a.method), "error": None if res is not None and len(res) == len(ch[tid]["test"]) else err,
                                "rank": a.rank, "wall_s": round(time.time() - t0, 2), "ttt": tstats,
                                "peak_gb": peak_gb(), "static_cache": lm.use_static})
        done += 1
        say(event="task", task=tid, wall_s=round(time.time() - t0, 2), ok=res is not None and len(res) == len(ch[tid]["test"]), err=err,
            partial=res is not None and len(res) < len(ch[tid]["test"]),
            n_cands=[len(o["candidates"]) for o in res] if res else None)
    say(event="exit", done=done, stats=lm.stats, peak_gb=peak_gb(), static_cache=lm.use_static)


# ----- orchestrator ----------------------------------------------------------------------------------------------
def build_submission(ch, out, method, selector=None):
    sub, n_pool = {}, 0
    for tid, t in ch.items():
        p = os.path.join(out, "pools", f"{tid}.json")
        res = None
        if os.path.exists(p):
            try:
                res = json.load(open(p)).get("outputs")
            except (OSError, ValueError):
                res = None
        entry = []
        for j, x in enumerate(t["test"]):
            pool = res[j]["candidates"] if res and j < len(res) else []
            if pool:
                n_pool += 1
            order = selector(tid, j, pool) if selector else S.rank(pool, method)
            entry.append(S.two_attempts(pool, x["input"], order))
        sub[tid] = entry
    return sub, n_pool


def release_failed_worker_claims(out, queue, rank):
    """Release only unfinished claims owned by a worker already verified dead.

    Called by the sole orchestrator after poll() reports a nonzero exit, before
    its replacement starts. Completed pools and other workers' claims stay put.
    """
    released = []
    for tid in queue:
        if os.path.exists(os.path.join(out, "pools", f"{tid}.json")):
            continue
        path = os.path.join(out, "claims", tid)
        try:
            with open(path) as f:
                owner = f.read()
            if owner == str(rank):
                os.unlink(path)
                released.append(tid)
        except FileNotFoundError:
            pass
    return released


def orchestrate(a):
    t_start = time.time()
    ch = json.load(open(a.challenges))
    if a.task_ids:
        ids = [x for x in a.task_ids.split(",") if x in ch]
        ch = {k: ch[k] for k in ids}
    elif a.limit:
        ch = {k: ch[k] for k in list(ch)[:a.limit]}
    for d in ("claims", "pools", "workers", "progress"):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)
    sub_ch = os.path.join(a.out, "challenges_used.json")
    atomic_json(sub_ch, ch)
    atomic_json(os.path.join(a.out, "queue.json"), order_tasks(ch))
    sub, _ = build_submission(ch, a.out, a.method)
    atomic_json(a.submission, sub)                         # valid fallback file before any GPU work
    deadline = t_start + a.deadline_s
    worker_deadline = deadline - min(a.final_reserve_s, 0.1 * a.deadline_s)
    procs = {}

    def spawn(r):
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(r), PYTHONUNBUFFERED="1")
        cmd = [sys.executable, "-m", "sf.runner", "worker", "--rank", str(r), "--challenges", sub_ch,
               "--model", a.model, "--out", a.out, "--deadline", str(worker_deadline), "--n-gen", str(a.n_gen),
               "--n-score", str(a.n_score), "--max-prompt", str(a.max_prompt), "--task-cap-s", str(a.task_cap_s),
               "--reserve-s", str(a.reserve_s), "--n-workers", str(a.gpus), "--method", a.method, "--ttt-steps", str(a.ttt_steps),
               "--ttt-rank", str(a.ttt_rank), "--ttt-alpha", str(a.ttt_alpha), "--ttt-lr", str(a.ttt_lr),
               "--ttt-max-tokens", str(a.ttt_max_tokens), "--ttt-frac", str(a.ttt_frac)]
        errf = open(os.path.join(a.out, "workers", f"{r}.stderr"), "a")
        return subprocess.Popen(cmd, env=env, stdout=errf, stderr=errf, cwd=a.code_dir)
    for r in range(a.gpus):
        procs[r] = spawn(r)
    restarts = {r: 0 for r in procs}
    status = {"start": t_start, "deadline": deadline}
    while True:
        time.sleep(a.poll_s)
        n_done = sum(1 for f in os.listdir(os.path.join(a.out, "pools")) if f.endswith(".json"))
        sub, n_pool = build_submission(ch, a.out, a.method)
        atomic_json(a.submission, sub)
        alive = {r: p.poll() is None for r, p in procs.items()}
        for r, ok in alive.items():
            if not ok and procs[r].returncode != 0 and restarts[r] < 2 and time.time() < worker_deadline - 120:
                release_failed_worker_claims(a.out, order_tasks(ch), r)
                restarts[r] += 1
                procs[r] = spawn(r)
                alive[r] = True
        status.update(t=time.time(), pools=n_done, outputs_with_pool=n_pool, alive=alive, restarts=restarts)
        atomic_json(os.path.join(a.out, "status.json"), status)
        if n_done >= len(ch) or not any(alive.values()):
            break
        if time.time() > deadline:
            status["watchdog"] = "deadline reached; workers stopped"
            break
    for p in procs.values():
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
    for p in procs.values():
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
    sub, n_pool = build_submission(ch, a.out, a.method)
    atomic_json(a.submission, sub)
    problems = S.check_submission(sub, ch)
    status.update(t=time.time(), wall_s=round(time.time() - t_start, 1), final_outputs_with_pool=n_pool,
                  schema_problems=problems[:20], n_schema_problems=len(problems))
    atomic_json(os.path.join(a.out, "status.json"), status)
    print(json.dumps({k: status[k] for k in ("wall_s", "final_outputs_with_pool", "n_schema_problems")}))
    return status


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["orchestrate", "worker"])
    ap.add_argument("--challenges", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--submission")
    ap.add_argument("--gpus", type=int, default=4)
    ap.add_argument("--rank", type=int, default=0)
    ap.add_argument("--deadline", type=float)
    ap.add_argument("--deadline-s", type=float, default=11.5 * 3600)
    ap.add_argument("--final-reserve-s", type=float, default=600)
    ap.add_argument("--reserve-s", type=float, default=300)
    ap.add_argument("--task-cap-s", type=float, default=900)
    ap.add_argument("--n-gen", type=int, default=8)
    ap.add_argument("--n-score", type=int, default=16)
    ap.add_argument("--max-prompt", type=int, default=12000)
    ap.add_argument("--n-workers", type=int, default=4)
    ap.add_argument("--poll-s", type=float, default=20)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--task-ids", default="")
    ap.add_argument("--method", default="vote_score")
    ap.add_argument("--ttt-steps", type=int, default=0)
    ap.add_argument("--ttt-rank", type=int, default=64)
    ap.add_argument("--ttt-alpha", type=int, default=64)
    ap.add_argument("--ttt-lr", type=float, default=1e-4)
    ap.add_argument("--ttt-max-tokens", type=int, default=8192)
    ap.add_argument("--ttt-frac", type=float, default=0.7)
    ap.add_argument("--code-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args(argv)
    if a.mode == "worker":
        worker(a)
    else:
        orchestrate(a)


if __name__ == "__main__":
    main()
