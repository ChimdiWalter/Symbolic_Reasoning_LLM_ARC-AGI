#!/usr/bin/env python3
"""Check whether local ARC/ARC-AGI Kaggle files are present and readable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STANDARD_FILE_SETS = {
    "arc_agi_kaggle": [
        "arc-agi_training_challenges.json",
        "arc-agi_training_solutions.json",
        "arc-agi_evaluation_challenges.json",
        "arc-agi_evaluation_solutions.json",
    ],
    "arc_prize_kaggle_alt": [
        "training_challenges.json",
        "training_solutions.json",
        "evaluation_challenges.json",
        "evaluation_solutions.json",
    ],
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def inspect_json_task_file(path: Path) -> dict[str, Any]:
    data = read_json(path)
    if not isinstance(data, dict):
        return {"readable": True, "valid_task_mapping": False, "task_count": 0, "error": "top-level JSON is not an object"}
    task_count = len(data)
    sample_key = next(iter(data), None)
    sample = data.get(sample_key) if sample_key is not None else None
    valid_sample = isinstance(sample, dict) and "train" in sample and ("test" in sample or "eval" in sample)
    return {
        "readable": True,
        "valid_task_mapping": bool(valid_sample or task_count == 0),
        "task_count": task_count,
        "sample_key": sample_key,
    }


def check_directory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    result: dict[str, Any] = {
        "root": str(root),
        "exists": root.exists(),
        "is_dir": root.is_dir(),
        "recognized_layout": None,
        "files": {},
        "ready_for_adapter": False,
        "notes": [],
    }
    if not root.exists() or not root.is_dir():
        result["notes"].append("Root path does not exist or is not a directory.")
        return result

    for layout, names in STANDARD_FILE_SETS.items():
        paths = {name: root / name for name in names}
        if all(path.exists() for path in paths.values()):
            result["recognized_layout"] = layout
            for name, path in paths.items():
                try:
                    info = inspect_json_task_file(path) if "challenges" in name else {"readable": True}
                except Exception as exc:  # noqa: BLE001 - this is a diagnostic script.
                    info = {"readable": False, "error": f"{type(exc).__name__}: {exc}"}
                info["path"] = str(path)
                info["bytes"] = path.stat().st_size if path.exists() else 0
                result["files"][name] = info
            result["ready_for_adapter"] = all(info.get("readable", False) for info in result["files"].values())
            return result

    found_json = sorted(path.name for path in root.glob("*.json"))
    result["notes"].append("No standard ARC Kaggle file set found.")
    result["files_found"] = found_json
    return result


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def write_markdown(path: Path, status: dict[str, Any]) -> None:
    lines = [
        "# ARC Local Dataset Status",
        "",
        f"- Root: `{status['root']}`",
        f"- Exists: `{status['exists']}`",
        f"- Directory: `{status['is_dir']}`",
        f"- Recognized layout: `{status['recognized_layout']}`",
        f"- Ready for adapter: `{status['ready_for_adapter']}`",
        "",
    ]
    if status.get("files"):
        lines.append("## Files")
        lines.append("")
        for name, info in sorted(status["files"].items()):
            lines.append(
                f"- `{name}`: readable={info.get('readable')}, bytes={info.get('bytes')}, path=`{info.get('path')}`"
            )
    if status.get("notes"):
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        for note in status["notes"]:
            lines.append(f"- {note}")
    if status.get("files_found"):
        lines.append("")
        lines.append("## JSON Files Found")
        lines.append("")
        for name in status["files_found"]:
            lines.append(f"- `{name}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate local ARC Kaggle dataset files.")
    parser.add_argument("--root", default="data/arc")
    parser.add_argument("--output-json", default="outputs/arc_status/arc_local_status.json")
    parser.add_argument("--output-md", default="outputs/arc_status/arc_local_status.md")
    args = parser.parse_args()

    status = check_directory(Path(args.root))
    write_json(Path(args.output_json), status)
    write_markdown(Path(args.output_md), status)
    print(f"ready_for_adapter={status['ready_for_adapter']}")
    print(f"status_json={args.output_json}")
    print(f"status_md={args.output_md}")


if __name__ == "__main__":
    main()

