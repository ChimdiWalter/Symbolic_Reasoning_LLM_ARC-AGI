#!/usr/bin/env python3
"""Standalone dev-eval runner for the Stage-1 ObjectReasoningEngine.

Submission mode (hard constraint 6.3): ``engine.solve()`` receives TRAIN
pairs only.  Test outputs are touched exclusively in the offline scoring
phase, AFTER solve has returned and the apply_fn is frozen.

Usage (from project root, lesegenv active):
    python3 scripts/run_object_dev_eval.py --tasks id1,id2,...
    python3 scripts/run_object_dev_eval.py --file <json list of ids>

Per-task line format (stdout + appended to --log):
    <task_id> train_exact=<0|1> test_correct=<0|1> loo_folds=<n> \
        failure_stage=<stage|-> seg=<S?|-> wall_s=<t>

Summary JSON (written to <out_dir>/eval_summary_<tag>.json, echoed to
stdout between SUMMARY_JSON_BEGIN/END markers): train_exact count,
test_correct count, failure-stage histogram, induced_fraction (from
certificate parameter_class flags, Section 6.6), mean LOO folds over
accepted programs, crash count, per-task records.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from geocat_arc.data.arc_loader import load_tasks  # noqa: E402
from geocat_arc.object_reasoning.engine import ObjectReasoningEngine  # noqa: E402
from geocat_arc.object_reasoning.inducer import InductionConfig  # noqa: E402

INDUCED_CLASSES = {"relational", "feature", "induced_map"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--tasks", type=str, default=None,
                     help="comma-separated task ids")
    grp.add_argument("--file", type=str, default=None,
                     help="path to a JSON file containing a list of task ids")
    ap.add_argument("--split", type=str, default="training",
                    help="ARC split (default: training)")
    ap.add_argument("--out-dir", type=str,
                    default=str(PROJECT_ROOT / "outputs" / "object_reasoning_dev"),
                    help="engine output dir (programs/, certificates/, "
                         "near_solves.jsonl, library.json, summary)")
    ap.add_argument("--log", type=str,
                    default=str(PROJECT_ROOT / "logs" / "object_engine_dev.log"),
                    help="append-mode log file")
    ap.add_argument("--tag", type=str, default="dev",
                    help="label for this run (summary filename + log stanza)")
    ap.add_argument("--budget-s", type=float, default=None,
                    help="override per-task induction budget (seconds)")
    ap.add_argument("--no-library", action="store_true",
                    help="Requirement 1.2 ablation: disable the fragment library")
    ap.add_argument("--no-ranker", action="store_true",
                    help="Stage-2 3.3 ablation: canonical-order search "
                         "instead of UCB-guided expansion")
    ap.add_argument("--depth-1", action="store_true",
                    help="Stage-2 3.3 ablation: disable composition "
                         "(Stage-1 flat behavior)")
    ap.add_argument("--promote", action="store_true",
                    help="run promote_and_validate() after the batch")
    return ap.parse_args(argv)


def load_ids(args: argparse.Namespace) -> list[str]:
    if args.tasks:
        return [t.strip() for t in args.tasks.split(",") if t.strip()]
    ids = json.loads(Path(args.file).read_text())
    if not isinstance(ids, list):
        raise ValueError(f"--file {args.file} must contain a JSON list of ids")
    return [str(t) for t in ids]


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    task_ids = load_ids(args)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "a")

    def emit(line: str) -> None:
        print(line, flush=True)
        log_f.write(line + "\n")
        log_f.flush()

    stamp = datetime.now(timezone.utc).isoformat()
    emit(f"=== run_object_dev_eval [{args.tag}] {stamp} ===")
    emit(f"cmd: {' '.join(sys.argv)}")
    emit(f"tasks ({len(task_ids)}): {','.join(task_ids)}")

    # keep the caller's ordering (load_tasks returns file order)
    tasks = {t.task_id: t
             for t in load_tasks(split=args.split, task_ids=task_ids)}
    missing = [t for t in task_ids if t not in tasks]
    if missing:
        emit(f"WARNING missing from split '{args.split}': {missing}")
    task_ids = [t for t in task_ids if t in tasks]

    config = InductionConfig()
    if args.budget_s is not None:
        config = InductionConfig(budget_s=args.budget_s)
    if args.no_ranker:
        config.use_ranker = False
    if args.depth_1:
        config.max_composition_depth = 1
    engine = ObjectReasoningEngine(out_dir, use_library=not args.no_library,
                                   config=config)

    # ---- phase 1: solve (train pairs only — submission mode) ----
    results = {}
    for tid in task_ids:
        task = tasks[tid]
        train_pairs = [(np.asarray(p.input), np.asarray(p.output))
                       for p in task.train]
        t0 = time.perf_counter()
        crashed = False
        try:
            res = engine.solve(tid, train_pairs)
        except Exception as exc:  # engine contract says never — belt & braces
            crashed = True
            res = None
            emit(f"CRASH solve({tid}): {type(exc).__name__}: {exc}")
        wall = time.perf_counter() - t0
        results[tid] = {"result": res, "wall_s": wall, "crashed": crashed}

    # ---- phase 2: offline scoring (test outputs first touched here) ----
    per_task: list[dict] = []
    stage_hist: Counter = Counter()
    accepted_folds: list[int] = []
    accepted_depths: list[int] = []
    accepted_induced: list[bool] = []
    n_train_exact = n_test_correct = n_crashes = 0

    for tid in task_ids:
        entry = results[tid]
        res, wall = entry["result"], entry["wall_s"]
        crashed = entry["crashed"]
        train_exact = bool(res and res.solution and res.solution.is_exact)
        ind = res.induction if res else None
        loo_folds = ind.loo.folds if (ind and ind.loo) else 0
        failure_stage = (ind.failure_stage.value
                         if (ind and ind.failure_stage) else None)
        seg = None
        if ind is not None:
            if ind.program is not None:
                sv = getattr(ind.program, "segmentation_variant", None)
                seg = sv.value if sv is not None else None
            elif ind.segmentation is not None:
                seg = ind.segmentation.variant.value

        test_correct = False
        n_test = len(tasks[tid].test)
        n_test_ok = 0
        if train_exact:
            for tp in tasks[tid].test:
                sol = np.asarray(tp.output)
                if sol.size == 0:
                    continue  # no ground truth available
                try:
                    pred = res.solution.apply_fn(np.asarray(tp.input))
                    if pred is not None and np.array_equal(np.asarray(pred), sol):
                        n_test_ok += 1
                except Exception as exc:
                    crashed = True
                    emit(f"CRASH apply({tid}): {type(exc).__name__}: {exc}")
            test_correct = (n_test > 0 and n_test_ok == n_test)

        comp_depth = None
        if train_exact and ind is not None and ind.program is not None:
            comp_depth = len(getattr(ind.program, "stages", [])) or 1
        if train_exact:
            n_train_exact += 1
            accepted_folds.append(loo_folds)
            accepted_depths.append(comp_depth or 1)
            cert = res.certificate
            pclass = cert.parameter_class if cert else None
            accepted_induced.append(pclass in INDUCED_CLASSES)
        elif failure_stage:
            stage_hist[failure_stage] += 1
        if test_correct:
            n_test_correct += 1
        if crashed:
            n_crashes += 1

        rec = {"task_id": tid,
               "train_exact": train_exact,
               "test_correct": test_correct,
               "n_test": n_test, "n_test_correct": n_test_ok,
               "loo_folds": loo_folds,
               "composition_depth": comp_depth,
               "failure_stage": failure_stage,
               "seg_variant": seg,
               "parameter_class": (res.certificate.parameter_class
                                   if (res and res.certificate) else None),
               "crashed": crashed,
               "wall_s": round(wall, 2)}
        per_task.append(rec)
        emit(f"{tid} train_exact={int(train_exact)} "
             f"test_correct={int(test_correct)} loo_folds={loo_folds} "
             f"failure_stage={failure_stage or '-'} seg={seg or '-'} "
             f"wall_s={wall:.1f}")

    registered: list[str] = []
    if args.promote:
        registered = engine.promote_and_validate()
        emit(f"promote_and_validate registered: {registered}")

    n_acc = len(accepted_folds)
    summary = {
        "tag": args.tag,
        "timestamp": stamp,
        "split": args.split,
        "n_tasks": len(task_ids),
        "train_exact": n_train_exact,
        "test_correct": n_test_correct,
        "failure_stage_hist": dict(stage_hist),
        "induced_fraction": (sum(accepted_induced) / n_acc) if n_acc else None,
        "mean_loo_folds": (sum(accepted_folds) / n_acc) if n_acc else None,
        "mean_composition_depth": (sum(accepted_depths) / n_acc)
                                  if n_acc else None,
        "crashes": n_crashes,
        "library_registered": registered,
        "out_dir": str(out_dir),
        "per_task": per_task,
    }
    summary_path = out_dir / f"eval_summary_{args.tag}.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    emit("SUMMARY_JSON_BEGIN")
    emit(json.dumps(summary, indent=2))
    emit("SUMMARY_JSON_END")
    emit(f"summary written: {summary_path}")
    log_f.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
