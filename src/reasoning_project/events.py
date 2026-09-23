"""Event-driven reasoning audit log.

Every reasoning action emits a ReasoningEvent. The ReasoningEventLog
stores them, supports querying by task/type, replaying task lineages,
and exporting to JSONL for paper-ready provenance chains.

Core chain the paper must demonstrate:
  task failed → near-solved stored → failure cluster formed →
  operator invented → counterexamples survived → task resumed →
  task solved → certificate emitted
"""
from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


# ── Event types ──────────────────────────────────────────────────────

EVENT_TYPES = frozenset([
    "TASK_OBSERVED",
    "TASK_PARSED",
    "STRUCTURAL_SIGNATURE_COMPUTED",
    "MEMORY_RETRIEVED",
    "HYPOTHESIS_PROPOSED",
    "HYPOTHESIS_SCORED",
    "HYPOTHESIS_FALSIFIED",
    "COUNTEREXAMPLE_GENERATED",
    "HYPOTHESIS_ACCEPTED",
    "HYPOTHESIS_REJECTED",
    "NEAR_SOLVED_STORED",
    "FAILURE_CLUSTER_CREATED",
    "CONCEPT_PROPOSED",
    "OPERATOR_PROPOSED",
    "CHART_PROPOSED",
    "INVENTION_VALIDATED",
    "INVENTION_REJECTED",
    "INVENTION_REGISTERED",
    "TASK_RESUMED",
    "TASK_PROMOTED_TO_SOLVED",
    "REASONING_CERTIFICATE_CREATED",
    "CROSS_DOMAIN_TRANSFER_ATTEMPTED",
    "CROSS_DOMAIN_TRANSFER_SUCCEEDED",
    "CROSS_DOMAIN_TRANSFER_FAILED",
    "REGRESSION_DETECTED",
    "FINAL_PREDICTION_EMITTED",
])


@dataclass
class ReasoningEvent:
    event_type: str
    task_id: Optional[str]
    payload: Dict[str, Any]
    module: str
    status: str = "ok"
    parent_event_ids: List[str] = field(default_factory=list)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for k, v in d["payload"].items():
            if hasattr(v, "tolist"):
                d["payload"][k] = v.tolist()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReasoningEvent":
        return cls(**d)


class ReasoningEventLog:
    """Append-only event log with indexing by task and type."""

    def __init__(self) -> None:
        self._events: List[ReasoningEvent] = []
        self._by_task: Dict[str, List[int]] = defaultdict(list)
        self._by_type: Dict[str, List[int]] = defaultdict(list)
        self._by_id: Dict[str, int] = {}

    @property
    def events(self) -> List[ReasoningEvent]:
        return self._events

    def __len__(self) -> int:
        return len(self._events)

    def append(self, event: ReasoningEvent) -> ReasoningEvent:
        idx = len(self._events)
        self._events.append(event)
        if event.task_id:
            self._by_task[event.task_id].append(idx)
        self._by_type[event.event_type].append(idx)
        self._by_id[event.event_id] = idx
        return event

    def emit(
        self,
        event_type: str,
        task_id: Optional[str],
        payload: Dict[str, Any],
        module: str,
        status: str = "ok",
        parent_event_ids: Optional[List[str]] = None,
    ) -> ReasoningEvent:
        event = ReasoningEvent(
            event_type=event_type,
            task_id=task_id,
            payload=payload,
            module=module,
            status=status,
            parent_event_ids=parent_event_ids or [],
        )
        return self.append(event)

    def query(
        self,
        task_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[ReasoningEvent]:
        if task_id is not None and event_type is not None:
            task_set = set(self._by_task.get(task_id, []))
            type_set = set(self._by_type.get(event_type, []))
            indices = sorted(task_set & type_set)
        elif task_id is not None:
            indices = self._by_task.get(task_id, [])
        elif event_type is not None:
            indices = self._by_type.get(event_type, [])
        else:
            indices = list(range(len(self._events)))
        return [self._events[i] for i in indices]

    def replay(self, task_id: str) -> List[ReasoningEvent]:
        """Return all events for a task in chronological order."""
        return self.query(task_id=task_id)

    def lineage(self, event_id: str) -> List[ReasoningEvent]:
        """Walk parent chain to build full derivation lineage."""
        visited = set()
        result = []
        stack = [event_id]
        while stack:
            eid = stack.pop()
            if eid in visited:
                continue
            visited.add(eid)
            idx = self._by_id.get(eid)
            if idx is None:
                continue
            ev = self._events[idx]
            result.append(ev)
            stack.extend(ev.parent_event_ids)
        result.sort(key=lambda e: e.timestamp)
        return result

    def has_chain(self, task_id: str, chain: Sequence[str]) -> bool:
        """Check if a task has events matching the given type sequence."""
        events = self.replay(task_id)
        types = [e.event_type for e in events]
        ci = 0
        for t in types:
            if ci < len(chain) and t == chain[ci]:
                ci += 1
        return ci == len(chain)

    def promotion_chains(self) -> List[str]:
        """Find tasks that went through the full promotion chain."""
        full_chain = [
            "TASK_OBSERVED",
            "NEAR_SOLVED_STORED",
            "TASK_RESUMED",
            "TASK_PROMOTED_TO_SOLVED",
        ]
        result = []
        for task_id in self._by_task:
            if self.has_chain(task_id, full_chain):
                result.append(task_id)
        return result

    def summary(self) -> Dict[str, Any]:
        """Summary statistics for the event log."""
        type_counts = {t: len(idxs) for t, idxs in self._by_type.items()}
        n_tasks = len(self._by_task)
        promoted = self.promotion_chains()
        return {
            "total_events": len(self._events),
            "unique_tasks": n_tasks,
            "event_type_counts": type_counts,
            "promoted_tasks": promoted,
            "n_promoted": len(promoted),
        }

    def export_jsonl(self, path: str) -> int:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            for event in self._events:
                json.dump(event.to_dict(), f, default=str)
                f.write("\n")
        return len(self._events)

    def export_summary_md(self, path: str) -> None:
        s = self.summary()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        lines = [
            "# Reasoning Event Summary\n",
            f"Total events: {s['total_events']}",
            f"Unique tasks: {s['unique_tasks']}",
            f"Promoted tasks: {s['n_promoted']}",
            "",
            "## Event Type Counts\n",
        ]
        for t, c in sorted(s["event_type_counts"].items(), key=lambda x: -x[1]):
            lines.append(f"- {t}: {c}")
        if s["promoted_tasks"]:
            lines.append("\n## Promoted Tasks\n")
            for tid in s["promoted_tasks"]:
                lines.append(f"- {tid}")
        lines.append("")
        with open(path, "w") as f:
            f.write("\n".join(lines))

    def export_task_lineages(self, directory: str) -> int:
        os.makedirs(directory, exist_ok=True)
        count = 0
        for task_id in self._by_task:
            events = self.replay(task_id)
            path = os.path.join(directory, f"{task_id}.jsonl")
            with open(path, "w") as f:
                for ev in events:
                    json.dump(ev.to_dict(), f, default=str)
                    f.write("\n")
            count += 1
        return count

    @classmethod
    def load_jsonl(cls, path: str) -> "ReasoningEventLog":
        log = cls()
        with open(path) as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    log.append(ReasoningEvent.from_dict(d))
        return log


# ── Global singleton (optional convenience) ──────────────────────────

_GLOBAL_LOG: Optional[ReasoningEventLog] = None


def get_global_log() -> ReasoningEventLog:
    global _GLOBAL_LOG
    if _GLOBAL_LOG is None:
        _GLOBAL_LOG = ReasoningEventLog()
    return _GLOBAL_LOG


def reset_global_log() -> None:
    global _GLOBAL_LOG
    _GLOBAL_LOG = ReasoningEventLog()
