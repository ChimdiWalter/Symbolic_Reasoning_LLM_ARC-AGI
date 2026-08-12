#!/usr/bin/env python3
"""Train a bounded neural DSL ranker on synthetic tasks and measure transfer."""

from __future__ import annotations

import argparse
import csv
import json
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reasoning_project.arc_adapter import arc_task_to_reasoning_task, load_arc_tasks
from reasoning_project.operators import apply_program, candidate_programs
from reasoning_project.neural.grid_encoder import build_grid_encoder, torch_available
from reasoning_project.neural.grid_jepa import load_grid_jepa_checkpoint
from reasoning_project.neural.program_ranker import ProgramRanker
from reasoning_project.generators import generate_suite
from reasoning_project.schemas import ReasoningTask, program_signature
from reasoning_project.utils import (
    ensure_dir,
    log_progress,
    set_global_seed,
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


def _candidate_target(task: ReasoningTask, program: Sequence[Any]) -> float:
    true_signature = program_signature(task.program)
    candidate_signature = program_signature(program)
    if candidate_signature == true_signature:
        return 1.0
    heldout_ok = True
    for split in ["val", "test", "ood"]:
        for example in task.examples.get(split, []):
            if not np.array_equal(apply_program(example.input_grid, program), example.output_grid):
                heldout_ok = False
                break
        if not heldout_ok:
            break
    if heldout_ok:
        return 0.75
    train_fit = all(
        np.array_equal(apply_program(example.input_grid, program), example.output_grid)
        for example in task.examples.get("train", [])
    )
    return 0.25 if train_fit else 0.0


def _safe_name(text: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in str(text))


def _dataset_chunk_path(chunks_dir: Path, task_index: int, task: ReasoningTask) -> Path:
    return chunks_dir / f"{task_index:05d}_{_safe_name(task.task_id)}.npz"


def _load_or_build_training_matrix(
    ranker: ProgramRanker,
    tasks: Sequence[ReasoningTask],
    programs: Sequence[Any],
    *,
    run_dir: Path,
    run_name: str,
    resume: bool,
    dsl_profile: str,
) -> tuple[np.ndarray, np.ndarray]:
    dataset_cache_path = run_dir / "dataset_cache.npz"
    if resume and dataset_cache_path.exists():
        cached = np.load(dataset_cache_path)
        feature_matrix = np.asarray(cached["feature_matrix"], dtype=np.float32)
        targets = np.asarray(cached["targets"], dtype=np.float32)
        update_run_state(
            run_dir,
            run_name=run_name,
            status="running",
            phase="building_dataset",
            message="loaded dataset cache",
            progress={
                "tasks_completed": int(len(tasks)),
                "tasks_total": int(len(tasks)),
                "feature_rows": int(feature_matrix.shape[0]),
            },
        )
        log_progress(
            run_dir,
            event="dataset_cache_loaded",
            phase="building_dataset",
            data={"tasks_total": int(len(tasks)), "feature_rows": int(feature_matrix.shape[0])},
        )
        return feature_matrix, targets

    chunks_dir = ensure_dir(run_dir / "dataset_chunks")
    feature_chunks: List[np.ndarray] = []
    target_chunks: List[np.ndarray] = []
    for task_index, task in enumerate(tasks):
        chunk_path = _dataset_chunk_path(chunks_dir, task_index, task)
        if resume and chunk_path.exists():
            cached = np.load(chunk_path)
            task_features = np.asarray(cached["feature_matrix"], dtype=np.float32)
            task_targets = np.asarray(cached["targets"], dtype=np.float32)
            source = "cached"
        else:
            task_embedding = ranker.task_embedding(task)
            task_features = np.asarray(
                [ranker.candidate_embedding(task, program, task_embedding=task_embedding) for program in programs],
                dtype=np.float32,
            )
            task_targets = np.asarray([_candidate_target(task, program) for program in programs], dtype=np.float32)
            np.savez_compressed(
                chunk_path,
                feature_matrix=task_features,
                targets=task_targets,
                task_id=str(task.task_id),
                family=str(task.family),
            )
            source = "built"
        feature_chunks.append(task_features)
        target_chunks.append(task_targets)
        update_run_state(
            run_dir,
            run_name=run_name,
            status="running",
            phase="building_dataset",
            message="building dataset chunks",
            progress={
                "tasks_completed": int(task_index + 1),
                "tasks_total": int(len(tasks)),
                "feature_rows": int(sum(chunk.shape[0] for chunk in feature_chunks)),
            },
        )
        log_progress(
            run_dir,
            event="dataset_chunk",
            phase="building_dataset",
            data={
                "task_index": int(task_index),
                "task_id": str(task.task_id),
                "chunk_source": source,
                "rows": int(task_features.shape[0]),
                "tasks_completed": int(task_index + 1),
                "tasks_total": int(len(tasks)),
            },
        )
    feature_matrix = np.concatenate(feature_chunks, axis=0) if feature_chunks else np.zeros((0, 0), dtype=np.float32)
    targets = np.concatenate(target_chunks, axis=0) if target_chunks else np.zeros((0,), dtype=np.float32)
    np.savez_compressed(dataset_cache_path, feature_matrix=feature_matrix, targets=targets)
    write_json(
        run_dir / "dataset_summary.json",
        {
            "tasks_total": int(len(tasks)),
            "programs_per_task": int(len(programs)),
            "feature_rows": int(feature_matrix.shape[0]),
            "feature_dim": int(feature_matrix.shape[1]) if feature_matrix.ndim == 2 else 0,
            "dataset_cache_path": str(dataset_cache_path),
            "dsl_profile": str(dsl_profile),
        },
    )
    return feature_matrix, targets


def _build_training_matrix(ranker: ProgramRanker, tasks: Sequence[ReasoningTask], programs: Sequence[Any]) -> tuple[np.ndarray, np.ndarray]:
    features: List[np.ndarray] = []
    targets: List[float] = []
    for task in tasks:
        task_embedding = ranker.task_embedding(task)
        for program in programs:
            features.append(ranker.candidate_embedding(task, program, task_embedding=task_embedding))
            targets.append(_candidate_target(task, program))
    return np.asarray(features, dtype=np.float32), np.asarray(targets, dtype=np.float32)


def _synthetic_eval(ranker: ProgramRanker, tasks: Sequence[ReasoningTask], programs: Sequence[Any]) -> Dict[str, float]:
    latent_top1 = []
    heldout_top1 = []
    heldout_top2 = []
    for task in tasks:
        ranked = ranker.rank_task(task, programs)
        top_programs = [item.program for item in ranked[:2]]
        top1 = top_programs[0]
        latent_top1.append(float(program_signature(top1) == program_signature(task.program)))
        def heldout_ok(program: Sequence[Any]) -> bool:
            for split in ["val", "test", "ood"]:
                for example in task.examples.get(split, []):
                    if not np.array_equal(apply_program(example.input_grid, program), example.output_grid):
                        return False
            return True
        heldout_top1.append(float(heldout_ok(top1)))
        heldout_top2.append(float(any(heldout_ok(program) for program in top_programs)))
    return {
        "latent_top1": float(np.mean(latent_top1)) if latent_top1 else 0.0,
        "heldout_top1": float(np.mean(heldout_top1)) if heldout_top1 else 0.0,
        "heldout_top2": float(np.mean(heldout_top2)) if heldout_top2 else 0.0,
    }


def _arc_eval_split(
    ranker: ProgramRanker,
    *,
    split: str,
    max_tasks: int,
    programs: Sequence[Any],
) -> Dict[str, float]:
    tasks = load_arc_tasks(ROOT / "data" / "arc", split=split, max_tasks=max_tasks)
    exact_scores = []
    pixel_scores = []
    pass2_scores = []
    for task in tasks:
        reasoning_task = arc_task_to_reasoning_task(task)
        ranked = ranker.rank_task(reasoning_task, programs)
        predictions = []
        for ranked_item in ranked[:2]:
            exact_train = all(
                np.array_equal(apply_program(example.input_grid, ranked_item.program), example.output_grid)
                for example in reasoning_task.examples.get("train", [])
            )
            if not exact_train:
                continue
            predictions.append(ranked_item.program)
        if not predictions:
            predictions = [ranked[0].program]
        top_predictions = []
        for program in predictions[:2]:
            grids = [apply_program(example.input_grid, program) for example in reasoning_task.examples.get("test", [])]
            top_predictions.append(grids)
        top1_grids = top_predictions[0]
        exact_scores.append(float(all(np.array_equal(pred, example.output_grid) for pred, example in zip(top1_grids, reasoning_task.examples["test"]))))
        pixel_scores.append(
            float(
                np.mean(
                    [
                        float(np.mean(pred == example.output_grid)) if pred.shape == example.output_grid.shape else 0.0
                        for pred, example in zip(top1_grids, reasoning_task.examples["test"])
                    ]
                )
            )
        )
        pass2_scores.append(
            float(
                any(
                    all(np.array_equal(pred, example.output_grid) for pred, example in zip(grids, reasoning_task.examples["test"]))
                    for grids in top_predictions[:2]
                )
            )
        )
    return {
        "arc_exact_top1": float(np.mean(exact_scores)) if exact_scores else 0.0,
        "arc_pass2": float(np.mean(pass2_scores)) if pass2_scores else 0.0,
        "arc_pixel_top1": float(np.mean(pixel_scores)) if pixel_scores else 0.0,
        "arc_tasks_evaluated": float(len(exact_scores)),
    }


def _arc_eval(ranker: ProgramRanker, config: Dict[str, Any], programs: Sequence[Any]) -> Dict[str, Any]:
    eval_splits = [str(split) for split in config.get("arc_eval_splits", ["evaluation"])]
    tasks_per_split = dict(config.get("arc_eval_tasks_per_split", {}))
    default_max_tasks = int(config.get("arc_eval_tasks", 12))
    by_split: Dict[str, Dict[str, float]] = {}
    for split in eval_splits:
        split_max_tasks = int(tasks_per_split.get(split, default_max_tasks))
        by_split[split] = _arc_eval_split(
            ranker,
            split=split,
            max_tasks=split_max_tasks,
            programs=programs,
        )
    aggregate = {
        "arc_exact_top1": float(np.mean([metrics["arc_exact_top1"] for metrics in by_split.values()])) if by_split else 0.0,
        "arc_pass2": float(np.mean([metrics["arc_pass2"] for metrics in by_split.values()])) if by_split else 0.0,
        "arc_pixel_top1": float(np.mean([metrics["arc_pixel_top1"] for metrics in by_split.values()])) if by_split else 0.0,
        "arc_tasks_evaluated": float(np.sum([metrics["arc_tasks_evaluated"] for metrics in by_split.values()])) if by_split else 0.0,
    }
    return {"aggregate": aggregate, "by_split": by_split}


def _train_ranker(
    ranker: ProgramRanker,
    feature_matrix: np.ndarray,
    targets: np.ndarray,
    *,
    epochs: int,
    batch_size: int,
    run_dir: Path,
    run_name: str,
    resume: bool,
) -> Dict[str, Any]:
    if not torch_available():
        return {"status": "skipped_no_torch", "epochs": 0, "final_loss": None}
    features = np.asarray(feature_matrix, dtype=np.float32)
    labels = np.asarray(targets, dtype=np.float32)
    checkpoint_path = run_dir / "ranker_training_checkpoint.pt"
    ranker._ensure_model(features.shape[1])
    assert ranker.model is not None
    optimizer = torch.optim.Adam(ranker.model.parameters(), lr=ranker.learning_rate)
    start_epoch = 0
    history: List[Dict[str, float]] = list(ranker.training_history)
    if resume and checkpoint_path.exists():
        package = torch.load(checkpoint_path, map_location=ranker.device)
        saved_input_dim = int(package.get("input_dim", features.shape[1]))
        if saved_input_dim == int(features.shape[1]):
            ranker._ensure_model(saved_input_dim)
            assert ranker.model is not None
            ranker.model.load_state_dict(package["model_state"])
            optimizer.load_state_dict(package["optimizer_state"])
            start_epoch = int(package.get("epoch", 0))
            history = list(package.get("training_history", []))
            ranker.training_history = list(history)
            log_progress(
                run_dir,
                event="resume",
                phase="training",
                message="loaded ranker training checkpoint",
                data={"start_epoch": int(start_epoch), "history_rows": int(len(history))},
            )
        else:
            log_progress(
                run_dir,
                event="resume_checkpoint_skipped",
                phase="training",
                message="checkpoint input dimension mismatch; restarting training",
                data={
                    "saved_input_dim": int(saved_input_dim),
                    "current_input_dim": int(features.shape[1]),
                },
            )
    if start_epoch >= int(epochs):
        update_run_state(
            run_dir,
            run_name=run_name,
            status="running",
            phase="training",
            message="ranker training already complete in checkpoint",
            progress={"completed_epochs": int(start_epoch), "max_epochs": int(epochs)},
        )
        return {
            "status": "already_complete",
            "epochs": int(start_epoch),
            "final_loss": history[-1]["loss"] if history else None,
        }
    weights = np.ones(labels.shape[0], dtype=np.float32)
    weights[labels >= 0.75] = 4.0
    weights[(labels > 0.0) & (labels < 0.75)] = 2.0
    loss_fn = torch.nn.BCEWithLogitsLoss(reduction="none")
    dataset_size = features.shape[0]
    for epoch in range(start_epoch, int(epochs)):
        order = np.arange(dataset_size)
        np.random.shuffle(order)
        epoch_losses: List[float] = []
        for start in range(0, dataset_size, int(batch_size)):
            batch_indices = order[start : start + int(batch_size)]
            batch_x = torch.as_tensor(features[batch_indices], device=ranker.device)
            batch_y = torch.as_tensor(labels[batch_indices], device=ranker.device)
            batch_w = torch.as_tensor(weights[batch_indices], device=ranker.device)
            logits = ranker.model(batch_x)
            loss = (loss_fn(logits, batch_y) * batch_w).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_losses.append(float(loss.detach().cpu()))
        history.append({"epoch": float(epoch + 1), "loss": float(np.mean(epoch_losses)) if epoch_losses else 0.0})
        ranker.training_history = list(history)
        torch.save(
            {
                "epoch": int(epoch + 1),
                "input_dim": int(ranker.input_dim or features.shape[1]),
                "model_state": ranker.model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "training_history": list(history),
            },
            checkpoint_path,
        )
        update_run_state(
            run_dir,
            run_name=run_name,
            status="running",
            phase="training",
            message="ranker training in progress",
            progress={
                "completed_epochs": int(epoch + 1),
                "max_epochs": int(epochs),
                "loss": float(history[-1]["loss"]),
            },
        )
        log_progress(
            run_dir,
            event="train_epoch",
            phase="training",
            data={
                "epoch": int(epoch + 1),
                "max_epochs": int(epochs),
                "loss": float(history[-1]["loss"]),
            },
        )
    return {
        "status": "trained",
        "epochs": int(epochs),
        "final_loss": history[-1]["loss"] if history else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "neural"))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    config = _load_config(args.config)
    run_name = str(config.get("run_name", "program_ranker_smoke"))
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

    set_global_seed(int(config.get("seed", 0)))
    write_json(run_dir / "config.json", config)
    write_text(run_dir / "command_log.txt", " ".join(sys.argv) + "\n")
    write_json(run_dir / "seed_list.json", {"seed": int(config.get("seed", 0))})
    write_json(
        run_dir / "resume_instructions.json",
        {
            "run_dir": str(run_dir),
            "rerun_command": f"python3.11 scripts/train_program_ranker.py --config {args.config} --output-dir {args.output_dir}",
            "resume_command": f"python3.11 scripts/train_program_ranker.py --config {args.config} --output-dir {args.output_dir} --resume",
            "checkpoint_path": str(run_dir / "ranker.pt"),
        },
    )
    update_run_state(
        run_dir,
        run_name=run_name,
        status="running",
        phase="setup",
        message="initialized program ranker run",
        progress={"resume_requested": bool(args.resume)},
    )
    log_progress(
        run_dir,
        event="start",
        phase="setup",
        message="initialized program ranker run",
        data={"resume_requested": bool(args.resume)},
    )

    try:
        encoder_mode = str(config.get("encoder_mode", "grid_encoder"))
        if encoder_mode == "jepa":
            jepa_checkpoint = config.get("encoder_checkpoint")
            if not jepa_checkpoint:
                raise ValueError("encoder_mode=jepa requires encoder_checkpoint")
            encoder = load_grid_jepa_checkpoint(jepa_checkpoint).context_encoder
        else:
            encoder = build_grid_encoder(use_torch=torch_available())
        ranker = ProgramRanker(
            encoder=encoder,
            hidden_dim=int(config.get("hidden_dim", 128)),
            learning_rate=float(config.get("learning_rate", 1e-3)),
            device=str(
                config.get(
                    "device",
                    "cuda" if torch_available() and torch.cuda.is_available() else "cpu",
                )
            ),
        )

        train_suite = generate_suite(dict(config["synthetic_train"]))
        eval_suite = generate_suite(dict(config["synthetic_eval"]))
        programs = candidate_programs(
            int(config.get("candidate_max_depth", 2)),
            colors=[int(color) for color in config.get("colors", list(range(1, 10)))],
            profile=str(config.get("dsl_profile", "core")),
        )
        phase_state["phase"] = "building_dataset"
        feature_matrix, targets = _load_or_build_training_matrix(
            ranker,
            train_suite.tasks,
            programs,
            run_dir=run_dir,
            run_name=run_name,
            resume=bool(args.resume),
            dsl_profile=str(config.get("dsl_profile", "core")),
        )
        phase_state["phase"] = "training"
        training = _train_ranker(
            ranker,
            feature_matrix,
            targets,
            epochs=int(config.get("epochs", 5)),
            batch_size=int(config.get("batch_size", 128)),
            run_dir=run_dir,
            run_name=run_name,
            resume=bool(args.resume),
        )
        phase_state["phase"] = "synthetic_eval"
        update_run_state(
            run_dir,
            run_name=run_name,
            status="running",
            phase=phase_state["phase"],
            message="running synthetic evaluation",
        )
        synthetic_metrics = _synthetic_eval(ranker, eval_suite.tasks, programs)
        log_progress(run_dir, event="synthetic_eval_complete", phase=phase_state["phase"], data=synthetic_metrics)
        phase_state["phase"] = "arc_eval"
        update_run_state(
            run_dir,
            run_name=run_name,
            status="running",
            phase=phase_state["phase"],
            message="running ARC evaluation",
        )
        arc_eval = _arc_eval(ranker, config=config, programs=programs)
        arc_metrics = dict(arc_eval["aggregate"])
        log_progress(run_dir, event="arc_eval_complete", phase=phase_state["phase"], data=arc_metrics)

        transfer_summary = {
            "generated_at": utc_timestamp(),
            "encoder_mode": encoder_mode,
            "dsl_profile": str(config.get("dsl_profile", "core")),
            "training": training,
            "synthetic_eval": synthetic_metrics,
            "arc_eval": arc_metrics,
            "arc_eval_by_split": dict(arc_eval["by_split"]),
            "transfer_gap_exact": synthetic_metrics["heldout_top1"] - arc_metrics["arc_exact_top1"],
            "transfer_gap_pass2": synthetic_metrics["heldout_top2"] - arc_metrics["arc_pass2"],
        }
        if torch_available() and ranker.model is not None:
            ranker.save(str(run_dir / "ranker.pt"), extra={"encoder_mode": encoder_mode})
        write_json(
            run_dir / "budget_log.json",
            {
                "device": ranker.device,
                "epochs": int(config.get("epochs", 5)),
                "batch_size": int(config.get("batch_size", 128)),
                "candidate_max_depth": int(config.get("candidate_max_depth", 2)),
                "dsl_profile": str(config.get("dsl_profile", "core")),
                "arc_eval_tasks": int(config.get("arc_eval_tasks", 12)),
                "arc_eval_splits": [str(split) for split in config.get("arc_eval_splits", ["evaluation"])],
                "encoder_mode": encoder_mode,
            },
        )
        write_json(run_dir / "metrics.json", transfer_summary)
        with (run_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
            writer.writeheader()
            for group_name, group in [("synthetic_eval", synthetic_metrics), ("arc_eval", arc_metrics)]:
                for key, value in group.items():
                    writer.writerow({"metric": f"{group_name}.{key}", "value": value})
            for split, split_metrics in sorted(arc_eval["by_split"].items()):
                for key, value in split_metrics.items():
                    writer.writerow({"metric": f"arc_eval_by_split.{split}.{key}", "value": value})
            writer.writerow({"metric": "transfer_gap_exact", "value": transfer_summary["transfer_gap_exact"]})
            writer.writerow({"metric": "transfer_gap_pass2", "value": transfer_summary["transfer_gap_pass2"]})
        write_text(
            run_dir / "summary.md",
            "\n".join(
                [
                    "# Program Ranker Summary",
                    "",
                    f"- encoder mode: `{encoder_mode}`",
                    f"- training status: `{training['status']}`",
                    f"- synthetic heldout top1: {synthetic_metrics['heldout_top1']}",
                    f"- synthetic heldout top2: {synthetic_metrics['heldout_top2']}",
                    f"- ARC exact top1: {arc_metrics['arc_exact_top1']}",
                    f"- ARC pass@2: {arc_metrics['arc_pass2']}",
                    f"- ARC pixel top1: {arc_metrics['arc_pixel_top1']}",
                    f"- ARC eval splits: {', '.join(sorted(arc_eval['by_split']))}",
                    f"- transfer gap exact: {transfer_summary['transfer_gap_exact']}",
                ]
            )
            + "\n",
        )
        write_json(
            run_dir / "manifest.json",
            {
                "run_dir": str(run_dir),
                "artifacts": [
                    "config.json",
                    "command_log.txt",
                    "seed_list.json",
                    "resume_instructions.json",
                    "run_state.json",
                    "status.txt",
                    "progress.jsonl",
                    "dataset_summary.json",
                    "dataset_cache.npz",
                    "ranker_training_checkpoint.pt",
                    "metrics.json",
                    "metrics.csv",
                    "summary.md",
                    "budget_log.json",
                    "ranker.pt",
                ],
            },
        )
        phase_state["phase"] = "completed"
        update_run_state(
            run_dir,
            run_name=run_name,
            status="completed",
            phase=phase_state["phase"],
            message="program ranker run completed",
            progress={"feature_rows": int(feature_matrix.shape[0]), "epochs": int(training.get("epochs", 0))},
            extra={"metrics_path": str(run_dir / "metrics.json"), "artifacts_ready": True},
        )
        log_progress(
            run_dir,
            event="completed",
            phase=phase_state["phase"],
            data={"metrics_path": str(run_dir / "metrics.json"), "training_status": training.get("status")},
        )
    except BaseException as exc:
        update_run_state(
            run_dir,
            run_name=run_name,
            status="failed",
            phase=phase_state["phase"],
            message=f"{type(exc).__name__}: {exc}",
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
