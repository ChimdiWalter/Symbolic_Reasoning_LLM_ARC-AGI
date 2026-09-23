"""Load ARC-AGI tasks from JSON files."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from .arc_task import ARCTask, GridPair

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "arc"


def load_tasks(
    split: str = "training",
    data_dir: Optional[Path] = None,
    task_ids: Optional[list[str]] = None,
) -> list[ARCTask]:
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

    challenges_file = data_dir / f"arc-agi_{split}_challenges.json"
    solutions_file = data_dir / f"arc-agi_{split}_solutions.json"

    with open(challenges_file) as f:
        challenges = json.load(f)

    solutions = {}
    if solutions_file.exists():
        with open(solutions_file) as f:
            solutions = json.load(f)

    tasks = []
    for tid, chal in challenges.items():
        if task_ids and tid not in task_ids:
            continue

        train_pairs = [
            GridPair(input=p["input"], output=p["output"])
            for p in chal["train"]
        ]

        test_pairs = []
        if "test" in chal:
            sol_list = solutions.get(tid, [])
            for i, tp in enumerate(chal["test"]):
                output = sol_list[i] if i < len(sol_list) else []
                test_pairs.append(GridPair(input=tp["input"], output=output))

        tasks.append(ARCTask(task_id=tid, train=train_pairs, test=test_pairs))

    return tasks


def load_task(task_id: str, split: str = "training", data_dir: Optional[Path] = None) -> ARCTask:
    tasks = load_tasks(split=split, data_dir=data_dir, task_ids=[task_id])
    if not tasks:
        raise KeyError(f"Task {task_id} not found in {split} split")
    return tasks[0]


def list_task_ids(split: str = "training", data_dir: Optional[Path] = None) -> list[str]:
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    challenges_file = data_dir / f"arc-agi_{split}_challenges.json"
    with open(challenges_file) as f:
        return list(json.load(f).keys())
