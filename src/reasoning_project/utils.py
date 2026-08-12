"""Small reproducibility and artifact helpers."""

from __future__ import annotations

import hashlib
import json
import os
import random
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def ensure_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def read_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_json_if_exists(path: str | Path, default: Any | None = None) -> Any:
    candidate = Path(path)
    if not candidate.exists():
        if default is None:
            return {}
        return default
    return read_json(candidate)


def write_json(path: str | Path, data: Any) -> None:
    out = Path(path)
    ensure_dir(out.parent)
    tmp = out.with_name(f".{out.name}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(out)


def write_text(path: str | Path, text: str) -> None:
    out = Path(path)
    ensure_dir(out.parent)
    with out.open("w", encoding="utf-8") as handle:
        handle.write(text)


def append_jsonl(path: str | Path, data: Any) -> None:
    out = Path(path)
    ensure_dir(out.parent)
    with out.open("a", encoding="utf-8") as handle:
        json.dump(data, handle, sort_keys=True, default=str)
        handle.write("\n")


def stable_json_dumps(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(data: Any, length: int = 12) -> str:
    return hashlib.sha256(stable_json_dumps(data).encode("utf-8")).hexdigest()[:length]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def runtime_context() -> Dict[str, Any]:
    return {
        "pid": int(os.getpid()),
        "hostname": socket.gethostname(),
        "cwd": str(Path.cwd()),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_array_job_id": os.environ.get("SLURM_ARRAY_JOB_ID"),
        "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
    }


def update_run_state(
    run_dir: str | Path,
    *,
    run_name: str | None = None,
    status: str | None = None,
    phase: str | None = None,
    message: str | None = None,
    progress: Dict[str, Any] | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    root = ensure_dir(run_dir)
    state_path = root / "run_state.json"
    state = read_json_if_exists(state_path, default={})
    if "started_at" not in state:
        state["started_at"] = utc_timestamp()
    if "context" not in state:
        state["context"] = runtime_context()
    if run_name is not None:
        state["run_name"] = run_name
    if status is not None:
        state["status"] = status
    if phase is not None:
        state["phase"] = phase
    if message is not None:
        state["message"] = message
    if progress is not None:
        state["progress"] = dict(progress)
    if extra:
        state.update(extra)
    state["updated_at"] = utc_timestamp()
    write_json(state_path, state)
    status_lines = [
        f"run_name={state.get('run_name', '')}",
        f"status={state.get('status', '')}",
        f"phase={state.get('phase', '')}",
        f"updated_at={state.get('updated_at', '')}",
    ]
    if state.get("message"):
        status_lines.append(f"message={state['message']}")
    if state.get("progress"):
        for key, value in sorted(dict(state["progress"]).items()):
            status_lines.append(f"{key}={value}")
    write_text(root / "status.txt", "\n".join(status_lines) + "\n")
    return state


def log_progress(
    run_dir: str | Path,
    *,
    event: str,
    phase: str | None = None,
    message: str | None = None,
    data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "timestamp": utc_timestamp(),
        "event": event,
        **runtime_context(),
    }
    if phase is not None:
        payload["phase"] = phase
    if message is not None:
        payload["message"] = message
    if data:
        payload.update(dict(data))
    append_jsonl(Path(run_dir) / "progress.jsonl", payload)
    return payload


def configure_matplotlib_cache(base_dir: str | Path) -> None:
    cache = ensure_dir(Path(base_dir) / ".mplconfig")
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
