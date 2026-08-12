#!/usr/bin/env python3
"""Run bounded ARC refinement comparisons on labeled local subsets."""

from __future__ import annotations

import argparse
import csv
import json
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.arc_adapter import arc_task_to_reasoning_task, evaluate_arc_prediction, load_arc_tasks
from reasoning_project.models import CandidateResult, PredictionResult
from reasoning_project.neural.grid_encoder import build_grid_encoder, torch_available
from reasoning_project.neural.grid_jepa import load_grid_jepa_checkpoint
from reasoning_project.neural.program_ranker import ProgramRanker
from reasoning_project.refinement import (
    RefinementConfig,
    RefinementEngine,
    baseline_prediction_for_arc,
    evaluate_refinement_result,
)
from reasoning_project.schemas import program_signature
from reasoning_project.utils import (
    ensure_dir,
    log_progress,
    read_json_if_exists,
    utc_timestamp,
    update_run_state,
    write_json,
    write_text,
)

if torch_available():
    import torch
else:  # pragma: no cover
    torch = None


def _load_config(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _top1_prediction_from_refinement(result: Any) -> PredictionResult:
    top_candidate = result.top_candidates[0]
    predictions = {"test": result.predictions.get("test_top1", [])}
    candidate = CandidateResult(
        program=top_candidate.program,
        train_error=top_candidate.train_error,
        score=top_candidate.initial_score,
        diagnostics=dict(top_candidate.diagnostics),
    )
    return PredictionResult(
        model_name=result.method_name,
        task_id=result.task_id,
        family=result.family,
        predictions=predictions,
        candidate=candidate,
        diagnostics=dict(result.diagnostics),
    )


def _load_ranker(config: Dict[str, Any], key_prefix: str) -> ProgramRanker | None:
    checkpoint = config.get(f"{key_prefix}_checkpoint")
    if not checkpoint:
        return None
    encoder_mode = str(config.get(f"{key_prefix}_encoder_mode", "grid_encoder"))
    if encoder_mode == "jepa":
        encoder = load_grid_jepa_checkpoint(config[f"{key_prefix}_encoder_checkpoint"]).context_encoder
    else:
        encoder = build_grid_encoder(use_torch=torch_available())
    return ProgramRanker.load(str(checkpoint), encoder=encoder)


def _clone_ranker(ranker: ProgramRanker | None) -> ProgramRanker | None:
    if ranker is None:
        return None
    return ranker.clone()


def _record_with_eval(result: Any, row: Dict[str, Any]) -> Dict[str, Any]:
    record = result.to_dict()
    record["evaluation"] = {
        "test_exact_task_accuracy": float(row.get("test_exact_task_accuracy", 0.0)),
        "test_pixel_accuracy": float(row.get("test_pixel_accuracy", 0.0)),
        "pass_at_1": float(row.get("pass_at_1", 0.0)),
        "pass_at_2": float(row.get("pass_at_2", 0.0)),
    }
    return record


def _row_key(task_id: str, model_name: str) -> str:
    return f"{task_id}::{model_name}"


def _summarize_rows(rows: List[Dict[str, Any]], run_name: str, n_tasks: int, completed_keys: set[str]) -> Dict[str, Any]:
    by_model: Dict[str, Dict[str, float]] = {}
    for row in rows:
        model_name = str(row["model_name"])
        bucket = by_model.setdefault(model_name, {})
        for key in [
            "test_exact_task_accuracy",
            "test_pixel_accuracy",
            "runtime_seconds",
            "candidate_program_count",
            "pass_at_1",
            "pass_at_2",
            "gpu_memory_mb",
            "gpu_time_seconds",
        ]:
            bucket.setdefault(key, [])
            bucket[key].append(float(row.get(key, 0.0)))
    return {
        "generated_at": utc_timestamp(),
        "run_name": run_name,
        "n_tasks": int(n_tasks),
        "completed_row_count": int(len(completed_keys)),
        "by_model": {
            model: {f"{key}_mean": float(np.mean(values)) for key, values in metrics.items()}
            for model, metrics in sorted(by_model.items())
        },
    }


def _persist_partial(
    run_dir: Path,
    *,
    run_name: str,
    n_tasks: int,
    rows: List[Dict[str, Any]],
    refinement_records: List[Dict[str, Any]],
    qualitative_failures: List[Dict[str, Any]],
    completed_keys: set[str],
) -> Dict[str, Any]:
    summary = _summarize_rows(rows, run_name, n_tasks=n_tasks, completed_keys=completed_keys)
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "rows.json", rows)
    write_json(run_dir / "refinement_records.json", refinement_records)
    write_json(run_dir / "qualitative_failures.json", qualitative_failures)
    write_json(run_dir / "completed_rows.json", {"completed_rows": sorted(completed_keys)})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "arc_refinement"))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    config = _load_config(args.config)
    run_name = str(config.get("run_name", "arc_refinement_smoke"))
    run_dir = ensure_dir(Path(args.output_dir) / run_name)
    phase_state = {"phase": "setup"}

    def _handle_signal(signum: int, _frame: Any) -> None:
        update_run_state(
            run_dir,
            run_name=run_name,
            status="interrupted",
            phase=phase_state["phase"],
            message=f"received signal {signum}",
        )
        log_progress(
            run_dir,
            event="interrupted",
            phase=phase_state["phase"],
            message=f"received signal {signum}",
        )
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    write_json(run_dir / "config.json", config)
    write_text(run_dir / "command_log.txt", " ".join(sys.argv) + "\n")
    write_json(run_dir / "seed_list.json", {"seed": int(config.get("seed", 0))})
    write_json(
        run_dir / "resume_instructions.json",
        {
            "run_dir": str(run_dir),
            "rerun_command": f"python3.11 scripts/run_arc_refinement.py --config {args.config} --output-dir {args.output_dir}",
            "resume_command": f"python3.11 scripts/run_arc_refinement.py --config {args.config} --output-dir {args.output_dir} --resume",
        },
    )
    update_run_state(
        run_dir,
        run_name=run_name,
        status="running",
        phase="setup",
        message="initialized ARC refinement run",
        progress={"resume_requested": bool(args.resume)},
    )
    log_progress(
        run_dir,
        event="start",
        phase="setup",
        message="initialized ARC refinement run",
        data={"resume_requested": bool(args.resume)},
    )
    tasks = load_arc_tasks(
        config.get("arc_root", ROOT / "data" / "arc"),
        split=str(config.get("split", "evaluation")),
        max_tasks=int(config.get("max_tasks", 12)),
    )
    labeled_tasks = [task for task in tasks if task.has_test_solutions]
    whitelist = config.get("task_whitelist")
    if whitelist:
        whitelist_set = set(str(tid) for tid in whitelist)
        labeled_tasks = [t for t in labeled_tasks if t.task_id in whitelist_set]

    plain_ranker = _load_ranker(config, "plain_ranker")
    jepa_ranker = _load_ranker(config, "jepa_ranker")
    baseline_models = list(
        config.get(
            "baseline_models",
            ["direct_io_proxy", "transformation_library", "compression_selector", "proposer_falsifier"],
        )
    )
    refinement_cfg = RefinementConfig(
        candidate_max_depth=int(config.get("candidate_max_depth", 2)),
        colors=[int(color) for color in config.get("colors", list(range(1, 10)))],
        dsl_profile=str(config.get("dsl_profile", "core")),
        initial_top_k=int(config.get("initial_top_k", 24)),
        repair_top_k=int(config.get("repair_top_k", 6)),
        return_top_k=2,
        use_falsifier=bool(config.get("use_falsifier", False)),
        neural_guidance=True,
        test_time_adaptation_steps=0,
        device=str(
            config.get(
                "device",
                "cuda" if torch_available() and torch.cuda.is_available() else "cpu",
            )
        ),
    )
    tta_cfg = RefinementConfig(
        **{
            **refinement_cfg.__dict__,
            "test_time_adaptation_steps": int(config.get("test_time_adaptation_steps", 3)),
            "test_time_adaptation_lr": float(config.get("test_time_adaptation_lr", 5e-4)),
        }
    )

    rows: List[Dict[str, Any]] = list(read_json_if_exists(run_dir / "rows.json", default=[])) if args.resume else []
    refinement_records: List[Dict[str, Any]] = list(read_json_if_exists(run_dir / "refinement_records.json", default=[])) if args.resume else []
    qualitative_failures: List[Dict[str, Any]] = list(read_json_if_exists(run_dir / "qualitative_failures.json", default=[])) if args.resume else []
    completed_keys = set(read_json_if_exists(run_dir / "completed_rows.json", default={"completed_rows": []}).get("completed_rows", [])) if args.resume else set()
    expected_methods = list(baseline_models)
    if plain_ranker is not None:
        expected_methods.extend(
            [
                "neural_dsl_ranker",
                "refinement_loop",
                "refinement_loop_tta",
                "integrated_scientist_neural_proposer",
            ]
        )
    if jepa_ranker is not None:
        expected_methods.append("grid_jepa_dsl_ranker")

    try:
        phase_state["phase"] = "running_tasks"
        for task_index, task in enumerate(labeled_tasks):
            reasoning_task = arc_task_to_reasoning_task(task)
            for model_name in baseline_models:
                key = _row_key(task.task_id, model_name)
                if key in completed_keys:
                    continue
                prediction = baseline_prediction_for_arc(
                    reasoning_task,
                    model_name,
                    candidate_max_depth=int(config.get("baseline_candidate_max_depth", 1)),
                    dsl_profile=str(config.get("baseline_dsl_profile", config.get("dsl_profile", "core"))),
                )
                row = evaluate_arc_prediction(task, prediction)
                row["pass_at_1"] = row["test_exact_task_accuracy"]
                row["pass_at_2"] = row["test_exact_task_accuracy"]
                row["method_group"] = "baseline"
                rows.append(row)
                completed_keys.add(key)
                if float(row["test_exact_task_accuracy"]) == 0.0:
                    qualitative_failures.append(
                        {
                            "model_name": model_name,
                            "task_id": task.task_id,
                            "predicted_program": row.get("predicted_program"),
                            "failure_type": "exact_failure",
                        }
                    )
                _persist_partial(
                    run_dir,
                    run_name=run_name,
                    n_tasks=len(labeled_tasks),
                    rows=rows,
                    refinement_records=refinement_records,
                    qualitative_failures=qualitative_failures,
                    completed_keys=completed_keys,
                )
                update_run_state(
                    run_dir,
                    run_name=run_name,
                    status="running",
                    phase=phase_state["phase"],
                    message="completed ARC method row",
                    progress={
                        "task_index": int(task_index + 1),
                        "tasks_total": int(len(labeled_tasks)),
                        "completed_rows": int(len(completed_keys)),
                        "expected_rows": int(len(labeled_tasks) * len(expected_methods)),
                    },
                )
                log_progress(
                    run_dir,
                    event="row_complete",
                    phase=phase_state["phase"],
                    data={"task_id": str(task.task_id), "model_name": model_name, "completed_rows": int(len(completed_keys))},
                )

            if plain_ranker is not None:
                if _row_key(task.task_id, "neural_dsl_ranker") not in completed_keys:
                    engine = RefinementEngine(config=refinement_cfg, ranker=_clone_ranker(plain_ranker))
                    result = engine.run_task(reasoning_task, method_name="neural_dsl_ranker")
                    row = evaluate_arc_prediction(task, _top1_prediction_from_refinement(result))
                    row.update(evaluate_refinement_result(reasoning_task, result))
                    row["method_group"] = "neural_ranker"
                    refinement_records.append(_record_with_eval(result, row))
                    rows.append(row)
                    completed_keys.add(_row_key(task.task_id, "neural_dsl_ranker"))
                    _persist_partial(
                        run_dir,
                        run_name=run_name,
                        n_tasks=len(labeled_tasks),
                        rows=rows,
                        refinement_records=refinement_records,
                        qualitative_failures=qualitative_failures,
                        completed_keys=completed_keys,
                    )
                    log_progress(run_dir, event="row_complete", phase=phase_state["phase"], data={"task_id": str(task.task_id), "model_name": "neural_dsl_ranker"})

                if _row_key(task.task_id, "refinement_loop") not in completed_keys:
                    refine_result = RefinementEngine(config=refinement_cfg, ranker=_clone_ranker(plain_ranker)).run_task(
                        reasoning_task,
                        method_name="refinement_loop",
                    )
                    refine_row = evaluate_arc_prediction(task, _top1_prediction_from_refinement(refine_result))
                    refine_row.update(evaluate_refinement_result(reasoning_task, refine_result))
                    refine_row["method_group"] = "refinement"
                    refinement_records.append(_record_with_eval(refine_result, refine_row))
                    rows.append(refine_row)
                    completed_keys.add(_row_key(task.task_id, "refinement_loop"))
                    _persist_partial(
                        run_dir,
                        run_name=run_name,
                        n_tasks=len(labeled_tasks),
                        rows=rows,
                        refinement_records=refinement_records,
                        qualitative_failures=qualitative_failures,
                        completed_keys=completed_keys,
                    )
                    log_progress(run_dir, event="row_complete", phase=phase_state["phase"], data={"task_id": str(task.task_id), "model_name": "refinement_loop"})

                if _row_key(task.task_id, "refinement_loop_tta") not in completed_keys:
                    tta_engine = RefinementEngine(config=tta_cfg, ranker=_clone_ranker(plain_ranker))
                    tta_result = tta_engine.run_task(reasoning_task, method_name="refinement_loop_tta")
                    tta_row = evaluate_arc_prediction(task, _top1_prediction_from_refinement(tta_result))
                    tta_row.update(evaluate_refinement_result(reasoning_task, tta_result))
                    tta_row["method_group"] = "refinement_tta"
                    refinement_records.append(_record_with_eval(tta_result, tta_row))
                    rows.append(tta_row)
                    completed_keys.add(_row_key(task.task_id, "refinement_loop_tta"))
                    _persist_partial(
                        run_dir,
                        run_name=run_name,
                        n_tasks=len(labeled_tasks),
                        rows=rows,
                        refinement_records=refinement_records,
                        qualitative_failures=qualitative_failures,
                        completed_keys=completed_keys,
                    )
                    log_progress(run_dir, event="row_complete", phase=phase_state["phase"], data={"task_id": str(task.task_id), "model_name": "refinement_loop_tta"})

                if _row_key(task.task_id, "integrated_scientist_neural_proposer") not in completed_keys:
                    integrated_result = RefinementEngine(config=refinement_cfg, ranker=_clone_ranker(plain_ranker)).run_task(
                        reasoning_task,
                        method_name="integrated_scientist_neural_proposer",
                        use_integrated_rescoring=True,
                    )
                    integrated_row = evaluate_arc_prediction(task, _top1_prediction_from_refinement(integrated_result))
                    integrated_row.update(evaluate_refinement_result(reasoning_task, integrated_result))
                    integrated_row["method_group"] = "integrated_neural"
                    refinement_records.append(_record_with_eval(integrated_result, integrated_row))
                    rows.append(integrated_row)
                    completed_keys.add(_row_key(task.task_id, "integrated_scientist_neural_proposer"))
                    _persist_partial(
                        run_dir,
                        run_name=run_name,
                        n_tasks=len(labeled_tasks),
                        rows=rows,
                        refinement_records=refinement_records,
                        qualitative_failures=qualitative_failures,
                        completed_keys=completed_keys,
                    )
                    log_progress(run_dir, event="row_complete", phase=phase_state["phase"], data={"task_id": str(task.task_id), "model_name": "integrated_scientist_neural_proposer"})

            if jepa_ranker is not None and _row_key(task.task_id, "grid_jepa_dsl_ranker") not in completed_keys:
                jepa_result = RefinementEngine(config=refinement_cfg, ranker=_clone_ranker(jepa_ranker)).run_task(
                    reasoning_task,
                    method_name="grid_jepa_dsl_ranker",
                )
                jepa_row = evaluate_arc_prediction(task, _top1_prediction_from_refinement(jepa_result))
                jepa_row.update(evaluate_refinement_result(reasoning_task, jepa_result))
                jepa_row["method_group"] = "jepa_ranker"
                refinement_records.append(_record_with_eval(jepa_result, jepa_row))
                rows.append(jepa_row)
                completed_keys.add(_row_key(task.task_id, "grid_jepa_dsl_ranker"))
                _persist_partial(
                    run_dir,
                    run_name=run_name,
                    n_tasks=len(labeled_tasks),
                    rows=rows,
                    refinement_records=refinement_records,
                    qualitative_failures=qualitative_failures,
                    completed_keys=completed_keys,
                )
                log_progress(run_dir, event="row_complete", phase=phase_state["phase"], data={"task_id": str(task.task_id), "model_name": "grid_jepa_dsl_ranker"})

        summary = _persist_partial(
            run_dir,
            run_name=run_name,
            n_tasks=len(labeled_tasks),
            rows=rows,
            refinement_records=refinement_records,
            qualitative_failures=qualitative_failures,
            completed_keys=completed_keys,
        )
        write_json(
            run_dir / "budget_log.json",
            {
                "device": refinement_cfg.device,
                "max_tasks": len(labeled_tasks),
                "candidate_max_depth": refinement_cfg.candidate_max_depth,
                "dsl_profile": refinement_cfg.dsl_profile,
                "baseline_dsl_profile": str(config.get("baseline_dsl_profile", config.get("dsl_profile", "core"))),
                "initial_top_k": refinement_cfg.initial_top_k,
                "repair_top_k": refinement_cfg.repair_top_k,
                "test_time_adaptation_steps": tta_cfg.test_time_adaptation_steps,
            },
        )
        with (run_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        write_text(
            run_dir / "summary.md",
            "\n".join(
                ["# ARC Refinement Summary", ""]
                + [
                    f"- {model}: exact={metrics.get('test_exact_task_accuracy_mean', 0.0):.3f}, pass@2={metrics.get('pass_at_2_mean', 0.0):.3f}, pixel={metrics.get('test_pixel_accuracy_mean', 0.0):.3f}, runtime={metrics.get('runtime_seconds_mean', 0.0):.3f}"
                    for model, metrics in sorted(summary["by_model"].items())
                ]
            )
            + "\n",
        )
        write_json(
            run_dir / "manifest.json",
            {
                "run_dir": str(run_dir),
                "artifacts": [
                    "summary.json",
                    "rows.json",
                    "metrics.csv",
                    "summary.md",
                    "refinement_records.json",
                    "qualitative_failures.json",
                    "completed_rows.json",
                    "config.json",
                    "command_log.txt",
                    "seed_list.json",
                    "resume_instructions.json",
                    "run_state.json",
                    "status.txt",
                    "progress.jsonl",
                    "budget_log.json",
                ],
            },
        )
        phase_state["phase"] = "completed"
        update_run_state(
            run_dir,
            run_name=run_name,
            status="completed",
            phase=phase_state["phase"],
            message="ARC refinement run completed",
            progress={"completed_rows": int(len(completed_keys)), "expected_rows": int(len(labeled_tasks) * len(expected_methods))},
            extra={"artifacts_ready": True, "summary_path": str(run_dir / "summary.json")},
        )
        log_progress(
            run_dir,
            event="completed",
            phase=phase_state["phase"],
            data={"summary_path": str(run_dir / "summary.json"), "completed_rows": int(len(completed_keys))},
        )
    except BaseException as exc:
        update_run_state(
            run_dir,
            run_name=run_name,
            status="failed",
            phase=phase_state["phase"],
            message=f"{type(exc).__name__}: {exc}",
            progress={"completed_rows": int(len(completed_keys)), "expected_rows": int(len(labeled_tasks) * len(expected_methods))},
        )
        log_progress(
            run_dir,
            event="failed",
            phase=phase_state["phase"],
            message=f"{type(exc).__name__}: {exc}",
        )
        raise


if __name__ == "__main__":
    main()
