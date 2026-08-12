"""Unified harness orchestrator.

Per task: run the cortical pipeline first (60 s budget), then GeoCat ALWAYS
(~0.1 s).  Accept any exact train-verified solve; if both systems solve,
prefer pipeline provenance for continuity but record both origins.

SOLVED definitions (kept identical to failure_landscape_2026_07_02.json so
the ground truth reproduces):
  * pipeline solved — evaluate_arc_unified submission mode: program
    synthesized/verified on train pairs only, then reproduced ALL test
    outputs (scored offline).  Test outputs never reach solver code.
  * geocat solved   — engine returned an exact train-verified (+LOO)
    solution (``result.solution.is_exact``).  We additionally score it on
    the test pairs offline and store ``geocat_test_correct`` for honesty;
    it does not change solved-ness (the landscape's definition).

Multiprocessing: spawn context, ~20 workers, each worker imports the heavy
reasoning stacks lazily inside the task function.  Hard SIGALRM caps guard
against non-cooperative hangs (pipeline 150 s, geocat 120 s).

Resumable: every finished task appends one line to
``outputs/unified_harness_v1/progress.jsonl``; on restart completed
task_ids are skipped.  Near-solves append to ``near_solves.jsonl`` (see
near_solve_store.py).  Final aggregate goes to ``results.json``.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import signal
import time
from collections import Counter
from typing import Any, Dict, List, Optional

PIPELINE_HARD_CAP_S = 150   # cooperative budget is 60 s; cap runaway layers
GEOCAT_HARD_CAP_S = 120
OBJECT_HARD_CAP_S = 105     # cooperative budget is 90 s (object_layer.py); raised from
                            # 60/50 after round 3: the wider tier search needs ~63 s on
                            # relational tasks (8ee62060) and worker contention shrinks
                            # effective wall-clock budgets


class _HardTimeout(BaseException):
    """Raised by SIGALRM.  Derives from BaseException ON PURPOSE: the solver
    stacks are full of ``except Exception`` blocks that would otherwise
    swallow the (one-shot) alarm and let a runaway layer keep running —
    verified empirically 2026-07-02 (alarm(1) fired inside the pipeline and
    was absorbed; the task ran to completion with no timeout recorded)."""
    pass


def _alarm_handler(signum, frame):  # noqa: ARG001
    raise _HardTimeout()


def _set_worker_env() -> None:
    """Pin BLAS threads so 20 workers don't oversubscribe 24 cores."""
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[var] = "1"
    signal.signal(signal.SIGALRM, _alarm_handler)


def run_one_task(args: tuple) -> Dict[str, Any]:
    """Worker entry: run both layers on one task, return the full record.

    Lazy-imports everything so the spawn'd worker only pays import cost
    once, and the parent never needs the heavy stacks.
    """
    task_id, task, solution, config = args
    import harness  # noqa: F401  (sys.path bootstrap)
    from harness.near_solve_store import build_near_solve_record
    from harness.origin_classes import classify_record

    t0 = time.time()

    # ---- 1. pipeline layer (hard-capped) ----
    pipeline: Dict[str, Any] = {"solved": False, "error": None}
    if not config.get("skip_pipeline", False):
        signal.alarm(int(config.get("pipeline_hard_cap_s", PIPELINE_HARD_CAP_S)))
        try:
            from harness.pipeline_layer import run_pipeline_task
            pipeline = run_pipeline_task(
                task_id, task, solution,
                timeout_per_task=config.get("timeout_per_task", 60.0),
                per_layer_timeout=config.get("per_layer_timeout", 8.0),
            )
        except _HardTimeout:
            pipeline = {"solved": False, "error": "pipeline_hard_timeout"}
        except Exception as exc:  # noqa: BLE001
            pipeline = {"solved": False, "error": repr(exc)}
        finally:
            signal.alarm(0)

    # ---- 2. geocat layer (ALWAYS, hard-capped) ----
    signal.alarm(int(config.get("geocat_hard_cap_s", GEOCAT_HARD_CAP_S)))
    try:
        from harness.geocat_layer import run_geocat_task
        geocat = run_geocat_task(task_id, task, solution)
    except _HardTimeout:
        geocat = {"solved": False, "error": "geocat_hard_timeout",
                  "best_accuracy": 0.0, "near_solve": None}
    except Exception as exc:  # noqa: BLE001
        geocat = {"solved": False, "error": repr(exc),
                  "best_accuracy": 0.0, "near_solve": None}
    finally:
        signal.alarm(0)

    # ---- 3. object layer (ALWAYS like geocat, so overlap is measurable) ----
    _cap = int(config.get("object_hard_cap_s", OBJECT_HARD_CAP_S))
    _frames = float(os.environ.get("ARC_DIHEDRAL_FRAMES", 0))
    if _frames > 0:   # round-13: room for the 7-frame fallback loop
        _cap += int(7 * _frames + 30)
    signal.alarm(_cap)
    try:
        from harness.object_layer import run_object_task
        obj = run_object_task(task_id, task, solution,
                              out_dir=config.get("object_out_dir"),
                              budget_s=config.get("object_budget_s"))
    except _HardTimeout:
        obj = {"solved": False, "error": "object_hard_timeout",
               "best_accuracy": 0.0, "near_solve": None}
    except Exception as exc:  # noqa: BLE001
        obj = {"solved": False, "error": repr(exc),
               "best_accuracy": 0.0, "near_solve": None}
    finally:
        signal.alarm(0)

    # ---- 4. merge ----
    p_solved = bool(pipeline.get("solved"))
    g_solved = bool(geocat.get("solved"))
    o_solved = bool(obj.get("solved"))
    solved = p_solved or g_solved or o_solved
    # origin semantics kept from v1 for the pipeline/geocat pair ("both" means
    # pipeline+geocat, continuity with failure_landscape); object-layer solves
    # get origin "object" only when it is the sole solver — overlap with the
    # other layers is read from record["object"]["solved"].
    origin = ("both" if (p_solved and g_solved)
              else "pipeline" if p_solved
              else "geocat" if g_solved
              else "object" if o_solved
              else None)

    record: Dict[str, Any] = {
        "task_id": task_id,
        "solved": solved,
        "origin": origin,
        # canonical provenance: pipeline wins for continuity when both solve
        "layer": (pipeline.get("layer") if p_solved
                  else ("geocat" if g_solved
                        else ("object" if o_solved else None))),
        "family_or_strategy": (pipeline.get("family") if p_solved
                               else (geocat.get("strategy") if g_solved
                                     else (obj.get("strategy") if o_solved
                                           else None))),
        "iteration": pipeline.get("iteration") if p_solved else None,
        # per-system detail
        "pipeline": {k: pipeline.get(k) for k in
                     ("solved", "layer", "family", "iteration",
                      "delta_type", "elapsed_s", "error")},
        "geocat": {k: geocat.get(k) for k in
                   ("solved", "strategy", "train_accuracy", "loo_score",
                    "test_correct", "best_accuracy", "apply_fn_qualname",
                    "elapsed_s", "error")},
        "object": {k: obj.get(k) for k in
                   ("solved", "strategy", "train_accuracy", "loo_score",
                    "loo_folds", "test_correct", "parameter_class",
                    "seg_variant", "failure_stage", "best_accuracy",
                    "elapsed_s", "error")},
        "elapsed_s": round(time.time() - t0, 3),
    }
    # emit-predictions (Kaggle path): persist test renders captured at solve
    # time — attempt_1 = the solving layer's render; attempt_2 material = the
    # object layer's best uncertified partial render + its parameter class.
    if config and config.get("emit_predictions"):
        a1 = None
        src = None
        for name, layer in (("pipeline", pipeline), ("geocat", geocat),
                            ("object", obj)):
            if layer.get("solved") and layer.get("predictions"):
                a1, src = layer["predictions"], name
                break
        record["predictions"] = {
            "attempt_1": a1, "attempt_1_source": src,
            "attempt_2": obj.get("partial_predictions"),
            "attempt_2_class": obj.get("partial_parameter_class"),
            "attempt_2_stage": obj.get("partial_failure_stage"),
        }
    if solved:
        record.update(classify_record(origin, record["layer"],
                                      record["family_or_strategy"],
                                      geocat.get("strategy"),
                                      geocat.get("apply_fn_qualname"),
                                      object_certificate=obj.get("certificate")))
    else:
        record["near_solve"] = build_near_solve_record(
            task_id, task, geocat,
            run_timestamp=config.get("run_id", "unknown"),
            pipeline_error=pipeline.get("error"),
        )
        # An object-layer partial with a REAL typed program beats the
        # identity-accuracy floor as training data for the memory loop.
        if record["near_solve"].get("source") == "identity_fallback":
            from harness.object_layer import object_near_solve_row
            obj_row = object_near_solve_row(
                task_id, obj,
                run_timestamp=config.get("run_id", "unknown"),
                pipeline_error=pipeline.get("error"),
                geocat_error=geocat.get("error"),
            )
            if obj_row is not None:
                record["near_solve"] = obj_row
    return record


# ---------------------------------------------------------------------------
# Orchestrator (parent process; the ONLY writer of the output files)
# ---------------------------------------------------------------------------

def _load_progress(path: str) -> Dict[str, Dict[str, Any]]:
    done: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    done[rec["task_id"]] = rec
                except Exception:  # noqa: BLE001 — tolerate a torn last line
                    continue
    return done


def aggregate(records: List[Dict[str, Any]], config: Dict[str, Any],
              elapsed_s: float) -> Dict[str, Any]:
    solved_records = [r for r in records if r.get("solved")]
    by_layer = Counter(r.get("layer") or "unknown" for r in solved_records)
    by_origin = Counter(r.get("origin") for r in solved_records)
    by_class = Counter(r.get("origin_class", "unknown") for r in solved_records)
    unmapped = sorted({r.get("origin_class_key") for r in solved_records
                       if not r.get("origin_class_mapped", True)})
    n_solved = len(solved_records)
    # object-layer overlap: it runs on every task, so its solves split into
    # overlap (another layer also solved) vs unique (origin == "object").
    obj_solved = [r for r in records if (r.get("object") or {}).get("solved")]
    obj_overlap = [r["task_id"] for r in obj_solved
                   if r.get("origin") in ("pipeline", "geocat", "both")]
    obj_unique = [r["task_id"] for r in obj_solved if r.get("origin") == "object"]
    return {
        "config": config,
        "total_tested": len(records),
        "total_solved": n_solved,
        "solved": [
            {
                "task_id": r["task_id"],
                "origin": r["origin"],
                "layer": r["layer"],
                "family_or_strategy": r["family_or_strategy"],
                "iteration": r["iteration"],
                "origin_class": r.get("origin_class"),
                "geocat_strategy": r["geocat"].get("strategy"),
                "geocat_test_correct": r["geocat"].get("test_correct"),
                "object_solved": (r.get("object") or {}).get("solved"),
                "object_test_correct": (r.get("object") or {}).get("test_correct"),
            }
            for r in sorted(solved_records, key=lambda x: x["task_id"])
        ],
        "by_layer": dict(by_layer),
        "by_origin": dict(by_origin),
        "by_origin_class": dict(by_class),
        "object_layer": {
            "solved_total": len(obj_solved),
            "overlap_with_other_layers": sorted(obj_overlap),
            "unique_solves": sorted(obj_unique),
            "mean_elapsed_s": (round(sum((r.get("object") or {}).get("elapsed_s") or 0.0
                                         for r in records) / len(records), 3)
                               if records else None),
        },
        "induced_fraction": (by_class.get("induced", 0) / n_solved
                             if n_solved else 0.0),
        "unmapped_origin_names": unmapped,
        "elapsed_s": round(elapsed_s, 1),
    }


def run_harness(
    challenges: Dict[str, Any],
    solutions: Dict[str, Any],
    task_ids: List[str],
    out_dir: str,
    workers: int = 20,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from harness.near_solve_store import NearSolveStore

    config = dict(config or {})
    config.setdefault("run_id", time.strftime("%Y-%m-%dT%H:%M:%S"))
    config.setdefault("timeout_per_task", 60.0)
    config.setdefault("per_layer_timeout", 8.0)
    # object layer artifacts (programs/, certificates/, near_solve_parts/)
    config.setdefault("object_out_dir", os.path.join(out_dir, "object"))
    config["workers"] = workers
    config["n_tasks_requested"] = len(task_ids)

    os.makedirs(out_dir, exist_ok=True)
    progress_path = os.path.join(out_dir, "progress.jsonl")
    results_path = os.path.join(out_dir, "results.json")
    store = NearSolveStore(os.path.join(out_dir, "near_solves.jsonl"))
    ns_seen = store.existing_task_ids()

    done = _load_progress(progress_path)
    todo = [t for t in task_ids if t not in done]
    print(f"[harness] {len(task_ids)} tasks requested, "
          f"{len(task_ids) - len(todo)} already complete, {len(todo)} to run, "
          f"workers={workers}", flush=True)

    t_start = time.time()
    # BUDGET GOVERNOR (Kaggle 12h notebooks; docs/KAGGLE_PIPELINE.md): when
    # config["global_budget_s"] is set, dispatch in worker-sized chunks and
    # rescale per-task budgets to the REMAINING wall clock before each chunk
    # (never above the configured defaults, never below a floor) — the run
    # degrades gracefully to cheaper searches instead of dying mid-list.
    global_budget = config.get("global_budget_s")
    governor_t0 = time.time()

    def _chunked_jobs():
        chunk = max(1, workers)
        base_obj = config.get("object_budget_s") or 90.0
        for i in range(0, len(todo), chunk):
            cfg = dict(config)
            if global_budget:
                remaining = global_budget - (time.time() - governor_t0)
                tasks_left = max(1, len(todo) - i)
                # effective parallel wall budget per task in this chunk
                allow = max(10.0, (remaining / tasks_left) * workers * 0.85)
                cfg["object_budget_s"] = min(base_obj, allow)
                cfg["object_hard_cap_s"] = min(
                    OBJECT_HARD_CAP_S, cfg["object_budget_s"] + 15)
                cfg["pipeline_hard_cap_s"] = min(
                    PIPELINE_HARD_CAP_S, max(20.0, allow))
                cfg["geocat_hard_cap_s"] = min(
                    GEOCAT_HARD_CAP_S, max(20.0, allow))
            for tid in todo[i:i + chunk]:
                yield (tid, challenges[tid], solutions[tid], cfg)

    jobs = None  # governed runs stream chunks; plain runs materialize below
    if not global_budget:
        jobs = list(_chunked_jobs())

    n_jobs = len(todo)
    if todo:
        ctx = mp.get_context("spawn")
        n_done = 0
        with ctx.Pool(processes=workers, initializer=_set_worker_env,
                      maxtasksperchild=32) as pool:
            with open(progress_path, "a") as pf:
                for rec in pool.imap_unordered(run_one_task,
                                               jobs if jobs is not None
                                               else _chunked_jobs(),
                                               chunksize=1):
                    # near-solve row FIRST: if we crash between the two writes
                    # the task reruns (not yet in progress.jsonl) and the
                    # ns_seen guard suppresses the duplicate row on resume.
                    if (not rec["solved"] and rec.get("near_solve")
                            and rec["task_id"] not in ns_seen):
                        store.append(rec["near_solve"])
                        ns_seen.add(rec["task_id"])
                    pf.write(json.dumps(rec) + "\n")
                    pf.flush()
                    n_done += 1
                    done[rec["task_id"]] = rec
                    tag = rec["origin"] if rec["solved"] else "unsolved"
                    print(f"[harness] {n_done}/{n_jobs} {rec['task_id']} "
                          f"{tag} ({rec['elapsed_s']:.1f}s)", flush=True)

    elapsed = time.time() - t_start
    records = [done[t] for t in task_ids if t in done]
    results = aggregate(records, config, elapsed)
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[harness] solved {results['total_solved']}/{results['total_tested']} "
          f"| by_origin={results['by_origin']} "
          f"| induced_fraction={results['induced_fraction']:.3f} "
          f"| elapsed={elapsed:.0f}s | results -> {results_path}", flush=True)
    return results
