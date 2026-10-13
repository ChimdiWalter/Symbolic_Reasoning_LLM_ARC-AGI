"""Blind solver-side funnel run on the frozen native object layer.

  python -m cora_funnel.run --corpus dev60 [--mode native] [--workers 3]
      -> outputs/funnel_v0/rows_<corpus>_<mode>.jsonl   (resumable)

The solver sees training pairs and test INPUTS only. Answers stored in a
corpus file are stripped by the loader, and family labels are never passed.
Per task it runs `harness.object_layer.run_object_task` exactly as the
native harness does:
- the sealed v23 flags;
- the default 90 s cooperative budget;
- the harness SIGALRM cap with room for the 7-frame fallback,
  105 + 7 x 45 + 30 s.

It runs inside `cora_funnel.instrument.probe`. No verifier, flag or asset is
changed.

Corpora:
- dev60: DEVELOPMENT, real ARC. The 60 authorized pilot development tasks,
  records/pilot_v1/dev_bundle.json, under opaque keys; the answers sit in an
  evaluator-only file.
- c2dev: SYNTHETIC, C2-dev (outputs/hybrid_c2_dev/dev_tasks.json).
- c3dev: SYNTHETIC, C3 v0 dev split (outputs/rep_growth_v0/corpus.json).

Modes:
- native: as above;
- budget3: the cooperative and frame budgets x3, the cap scaled to match.
  This is the matched-search intervention.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
for _k in [k for k in os.environ if k.startswith("ARC_")]:
    del os.environ[_k]
os.environ.update({"ARC_DIHEDRAL_FRAMES": "45", "ARC_GENERATIVE": "1", "ARC_PATTERN_DERIVE": "1",
                   "ARC_VARIANT_BUDGET": "1", "ARC_RAY_EXT": "1"})
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
OUT = os.path.join(HERE, "outputs", "funnel_v0")
MODES = {"native": (90.0, 45.0), "budget3": (270.0, 135.0)}


def _pair(p):
    return (p["input"], p["output"]) if isinstance(p, dict) else (p[0], p[1])


def _inp(p):
    return p["input"] if isinstance(p, dict) else p[0]


def load(corpus):
    """[(key, task)] with task = {"train": [{input, output}], "test": [{input}]}: no answers, no family."""
    if corpus == "dev60":
        src = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))["tasks"]
        items = sorted(src.items())
    elif corpus == "c2dev":
        items = sorted(json.load(open(os.path.join(HERE, "outputs", "hybrid_c2_dev", "dev_tasks.json"))).items())
    elif corpus == "c3dev":
        items = [(t["id"], {"train": t["train"], "test": t["heldout"]})
                 for t in json.load(open(os.path.join(HERE, "outputs", "rep_growth_v0", "corpus.json")))["tasks"] if t["split"] == "dev"]
    else:
        raise ValueError(corpus)
    return [(k, {"train": [dict(zip(("input", "output"), _pair(p))) for p in t["train"]],
                 "test": [{"input": _inp(p)} for p in t["test"]]}) for k, t in items]


class _HardTimeout(BaseException):
    """BaseException on purpose, as in harness/run_harness.py: native code is full of `except Exception`."""


def _alarm(signum, frame):                                             # noqa: ARG001
    raise _HardTimeout()


def job(args):
    key, task, corpus, mode = args
    import signal
    if os.nice(0) < 19:
        os.nice(19 - os.nice(0))
    budget, frames = MODES[mode]
    os.environ["ARC_DIHEDRAL_FRAMES"] = str(int(frames))
    signal.signal(signal.SIGALRM, _alarm)
    import numpy as np
    from geocat_arc.object_reasoning.types import to_grid_pairs
    from harness.object_layer import run_object_task
    from cora_funnel.instrument import finalize, perception, probe
    tests = [p["input"] for p in task["test"]]
    pairs = to_grid_pairs([(np.asarray(p["input"]), np.asarray(p["output"])) for p in task["train"]])
    try:
        perc = perception(pairs)
    except Exception as e:                                              # noqa: BLE001
        perc = {"error": repr(e)}
    cap = int(budget + 15 + 7 * frames + 30)
    t0, c0 = time.time(), time.process_time()
    with probe(len(task["train"]), tests) as rec:
        signal.alarm(cap)
        try:
            out = run_object_task(key, task, None, out_dir=os.path.join(OUT, f"engine_{corpus}_{mode}"), budget_s=budget)
        except _HardTimeout:
            out = {"solved": False, "error": "object_hard_timeout"}
        finally:
            signal.alarm(0)
    finalize(rec, tests)
    return {"key": key, "corpus": corpus, "mode": mode, "n_train": len(task["train"]), "n_test": len(tests),
            "perception": perc, "solved": bool(out.get("solved")), "predictions": out.get("predictions"),
            "partial_predictions": out.get("partial_predictions"), "failure_stage": out.get("failure_stage"),
            "seg_variant": out.get("seg_variant"), "parameter_class": out.get("parameter_class"), "error": out.get("error"),
            "wall_s": round(time.time() - t0, 2), "cpu_s": round(time.process_time() - c0, 2), "cap_s": cap,
            "frames": rec["frames"], "events": rec["events"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, choices=("dev60", "c2dev", "c3dev"))
    ap.add_argument("--mode", default="native", choices=tuple(MODES))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--keys", default="", help="comma-separated subset (intervention runs)")
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"rows_{a.corpus}_{a.mode}.jsonl")
    done = {json.loads(l)["key"] for l in open(path)} if os.path.exists(path) else set()
    want = set(a.keys.split(",")) if a.keys else None
    todo = [(k, t, a.corpus, a.mode) for k, t in load(a.corpus) if k not in done and (want is None or k in want)]
    print(f"{a.corpus}/{a.mode}: {len(todo)} to run, {len(done)} done", flush=True)
    t0 = time.time()
    with mp.get_context("fork").Pool(a.workers, maxtasksperchild=1) as pool, open(path, "a") as fh:
        for i, row in enumerate(pool.imap_unordered(job, todo), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {row['key']} solved={row['solved']} wall={row['wall_s']}s "
                  f"searches={sum(e['type'] == 'search' for e in row['events'])} elapsed={time.time() - t0:.0f}s", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
