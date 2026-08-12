"""Tests for reasoning_project.events module."""
import sys
sys.path.insert(0, "src")

import json
import os
import pytest

from reasoning_project.events import (
    ReasoningEvent,
    ReasoningEventLog,
    get_global_log,
    reset_global_log,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _make_event(event_type="TASK_OBSERVED", task_id="t1", **kw):
    defaults = dict(
        payload={"info": "test"},
        module="test_mod",
        status="ok",
    )
    defaults.update(kw)
    return ReasoningEvent(event_type=event_type, task_id=task_id, **defaults)


def _build_promotion_log(task_id="t1"):
    """Return a log containing the full promotion chain for *task_id*."""
    log = ReasoningEventLog()
    chain_types = [
        "TASK_OBSERVED",
        "NEAR_SOLVED_STORED",
        "TASK_RESUMED",
        "TASK_PROMOTED_TO_SOLVED",
    ]
    prev_ids = []
    for etype in chain_types:
        ev = log.emit(etype, task_id, {"step": etype}, "engine",
                       parent_event_ids=list(prev_ids))
        prev_ids = [ev.event_id]
    return log


# ── 1. ReasoningEvent creation & serialization round-trip ─────────────

class TestReasoningEvent:
    def test_create_defaults(self):
        ev = _make_event()
        assert ev.event_type == "TASK_OBSERVED"
        assert ev.task_id == "t1"
        assert ev.status == "ok"
        assert isinstance(ev.event_id, str) and len(ev.event_id) == 12
        assert ev.timestamp  # non-empty ISO string
        assert ev.parent_event_ids == []

    def test_to_dict_keys(self):
        ev = _make_event()
        d = ev.to_dict()
        expected_keys = {
            "event_type", "task_id", "payload", "module",
            "status", "parent_event_ids", "event_id", "timestamp",
        }
        assert set(d.keys()) == expected_keys

    def test_round_trip(self):
        ev = _make_event(parent_event_ids=["abc123"])
        d = ev.to_dict()
        ev2 = ReasoningEvent.from_dict(d)
        assert ev2.event_type == ev.event_type
        assert ev2.task_id == ev.task_id
        assert ev2.payload == ev.payload
        assert ev2.module == ev.module
        assert ev2.status == ev.status
        assert ev2.parent_event_ids == ev.parent_event_ids
        assert ev2.event_id == ev.event_id
        assert ev2.timestamp == ev.timestamp

    def test_to_dict_converts_ndarray_like(self):
        """Objects with .tolist() in payload should be converted."""
        class FakeArray:
            def tolist(self):
                return [1, 2, 3]

        ev = _make_event(payload={"vec": FakeArray()})
        d = ev.to_dict()
        assert d["payload"]["vec"] == [1, 2, 3]


# ── 2. EventLog append and emit ───────────────────────────────────────

class TestAppendEmit:
    def test_append_returns_event(self):
        log = ReasoningEventLog()
        ev = _make_event()
        ret = log.append(ev)
        assert ret is ev
        assert len(log) == 1
        assert log.events[0] is ev

    def test_emit_creates_and_appends(self):
        log = ReasoningEventLog()
        ev = log.emit("TASK_PARSED", "t1", {"x": 1}, "parser")
        assert ev.event_type == "TASK_PARSED"
        assert ev.task_id == "t1"
        assert len(log) == 1

    def test_emit_with_parent_ids(self):
        log = ReasoningEventLog()
        ev1 = log.emit("TASK_OBSERVED", "t1", {}, "mod")
        ev2 = log.emit("TASK_PARSED", "t1", {}, "mod",
                        parent_event_ids=[ev1.event_id])
        assert ev2.parent_event_ids == [ev1.event_id]

    def test_emit_default_status_is_ok(self):
        log = ReasoningEventLog()
        ev = log.emit("TASK_OBSERVED", "t1", {}, "mod")
        assert ev.status == "ok"

    def test_append_multiple(self):
        log = ReasoningEventLog()
        for i in range(5):
            log.emit("TASK_OBSERVED", f"t{i}", {}, "mod")
        assert len(log) == 5


# ── 3. Query by task_id, by event_type, by both ──────────────────────

class TestQuery:
    @pytest.fixture()
    def populated_log(self):
        log = ReasoningEventLog()
        log.emit("TASK_OBSERVED", "t1", {}, "mod")
        log.emit("TASK_PARSED", "t1", {}, "mod")
        log.emit("TASK_OBSERVED", "t2", {}, "mod")
        log.emit("HYPOTHESIS_PROPOSED", "t2", {}, "mod")
        return log

    def test_query_by_task_id(self, populated_log):
        results = populated_log.query(task_id="t1")
        assert len(results) == 2
        assert all(e.task_id == "t1" for e in results)

    def test_query_by_event_type(self, populated_log):
        results = populated_log.query(event_type="TASK_OBSERVED")
        assert len(results) == 2
        assert all(e.event_type == "TASK_OBSERVED" for e in results)

    def test_query_by_both(self, populated_log):
        results = populated_log.query(task_id="t1", event_type="TASK_PARSED")
        assert len(results) == 1
        assert results[0].event_type == "TASK_PARSED"
        assert results[0].task_id == "t1"

    def test_query_no_match(self, populated_log):
        results = populated_log.query(task_id="nonexistent")
        assert results == []

    def test_query_no_filters(self, populated_log):
        results = populated_log.query()
        assert len(results) == 4


# ── 4. replay() returns chronological events for a task ───────────────

class TestReplay:
    def test_replay_order(self):
        log = ReasoningEventLog()
        log.emit("TASK_OBSERVED", "t1", {"seq": 0}, "mod")
        log.emit("TASK_PARSED", "t1", {"seq": 1}, "mod")
        log.emit("HYPOTHESIS_PROPOSED", "t1", {"seq": 2}, "mod")
        events = log.replay("t1")
        assert len(events) == 3
        assert [e.event_type for e in events] == [
            "TASK_OBSERVED", "TASK_PARSED", "HYPOTHESIS_PROPOSED",
        ]

    def test_replay_ignores_other_tasks(self):
        log = ReasoningEventLog()
        log.emit("TASK_OBSERVED", "t1", {}, "mod")
        log.emit("TASK_OBSERVED", "t2", {}, "mod")
        log.emit("TASK_PARSED", "t1", {}, "mod")
        events = log.replay("t1")
        assert len(events) == 2
        assert all(e.task_id == "t1" for e in events)

    def test_replay_empty(self):
        log = ReasoningEventLog()
        assert log.replay("nonexistent") == []


# ── 5. lineage() walks parent chain ──────────────────────────────────

class TestLineage:
    def test_lineage_single_event(self):
        log = ReasoningEventLog()
        ev = log.emit("TASK_OBSERVED", "t1", {}, "mod")
        lin = log.lineage(ev.event_id)
        assert len(lin) == 1
        assert lin[0].event_id == ev.event_id

    def test_lineage_chain(self):
        log = ReasoningEventLog()
        ev1 = log.emit("TASK_OBSERVED", "t1", {}, "mod")
        ev2 = log.emit("TASK_PARSED", "t1", {}, "mod",
                        parent_event_ids=[ev1.event_id])
        ev3 = log.emit("HYPOTHESIS_PROPOSED", "t1", {}, "mod",
                        parent_event_ids=[ev2.event_id])
        lin = log.lineage(ev3.event_id)
        assert len(lin) == 3
        ids = {e.event_id for e in lin}
        assert ids == {ev1.event_id, ev2.event_id, ev3.event_id}

    def test_lineage_missing_id(self):
        log = ReasoningEventLog()
        assert log.lineage("does_not_exist") == []

    def test_lineage_diamond(self):
        """Two parents converging to one child."""
        log = ReasoningEventLog()
        a = log.emit("TASK_OBSERVED", "t1", {}, "mod")
        b = log.emit("TASK_PARSED", "t1", {}, "mod")
        c = log.emit("HYPOTHESIS_PROPOSED", "t1", {}, "mod",
                      parent_event_ids=[a.event_id, b.event_id])
        lin = log.lineage(c.event_id)
        assert len(lin) == 3


# ── 6. has_chain() matches event type sequences ──────────────────────

class TestHasChain:
    def test_full_match(self):
        log = _build_promotion_log("t1")
        assert log.has_chain("t1", [
            "TASK_OBSERVED", "NEAR_SOLVED_STORED",
            "TASK_RESUMED", "TASK_PROMOTED_TO_SOLVED",
        ])

    def test_partial_match(self):
        log = _build_promotion_log("t1")
        assert log.has_chain("t1", ["TASK_OBSERVED", "TASK_RESUMED"])

    def test_no_match(self):
        log = ReasoningEventLog()
        log.emit("TASK_OBSERVED", "t1", {}, "mod")
        assert not log.has_chain("t1", [
            "TASK_OBSERVED", "TASK_PROMOTED_TO_SOLVED",
        ])

    def test_wrong_order(self):
        log = ReasoningEventLog()
        log.emit("TASK_RESUMED", "t1", {}, "mod")
        log.emit("TASK_OBSERVED", "t1", {}, "mod")
        assert not log.has_chain("t1", ["TASK_OBSERVED", "TASK_RESUMED"])

    def test_empty_chain(self):
        log = ReasoningEventLog()
        log.emit("TASK_OBSERVED", "t1", {}, "mod")
        assert log.has_chain("t1", [])


# ── 7. promotion_chains() finds tasks with full chain ─────────────────

class TestPromotionChains:
    def test_finds_promoted(self):
        log = _build_promotion_log("t1")
        assert log.promotion_chains() == ["t1"]

    def test_ignores_incomplete(self):
        log = ReasoningEventLog()
        log.emit("TASK_OBSERVED", "t1", {}, "mod")
        log.emit("NEAR_SOLVED_STORED", "t1", {}, "mod")
        # missing TASK_RESUMED and TASK_PROMOTED_TO_SOLVED
        assert log.promotion_chains() == []

    def test_multiple_tasks(self):
        log = _build_promotion_log("t1")
        # add another promoted task
        for etype in ["TASK_OBSERVED", "NEAR_SOLVED_STORED",
                       "TASK_RESUMED", "TASK_PROMOTED_TO_SOLVED"]:
            log.emit(etype, "t2", {}, "mod")
        # add an incomplete task
        log.emit("TASK_OBSERVED", "t3", {}, "mod")
        promoted = log.promotion_chains()
        assert set(promoted) == {"t1", "t2"}


# ── 8. summary() returns correct counts ──────────────────────────────

class TestSummary:
    def test_summary_structure(self):
        log = _build_promotion_log("t1")
        s = log.summary()
        assert s["total_events"] == 4
        assert s["unique_tasks"] == 1
        assert s["n_promoted"] == 1
        assert "t1" in s["promoted_tasks"]
        assert isinstance(s["event_type_counts"], dict)
        assert s["event_type_counts"]["TASK_OBSERVED"] == 1

    def test_summary_empty_log(self):
        log = ReasoningEventLog()
        s = log.summary()
        assert s["total_events"] == 0
        assert s["unique_tasks"] == 0
        assert s["promoted_tasks"] == []


# ── 9. export_jsonl & load_jsonl round-trip ───────────────────────────

class TestJsonlRoundTrip:
    def test_export_and_load(self, tmp_path):
        log = _build_promotion_log("t1")
        log.emit("TASK_OBSERVED", "t2", {"extra": 42}, "mod")
        path = str(tmp_path / "events.jsonl")
        n_written = log.export_jsonl(path)
        assert n_written == 5
        assert os.path.isfile(path)

        loaded = ReasoningEventLog.load_jsonl(path)
        assert len(loaded) == 5
        # verify content equality
        for orig, restored in zip(log.events, loaded.events):
            assert orig.to_dict() == restored.to_dict()

    def test_export_creates_parent_dirs(self, tmp_path):
        log = ReasoningEventLog()
        log.emit("TASK_OBSERVED", "t1", {}, "mod")
        path = str(tmp_path / "sub" / "dir" / "events.jsonl")
        log.export_jsonl(path)
        assert os.path.isfile(path)

    def test_load_preserves_indices(self, tmp_path):
        log = _build_promotion_log("t1")
        path = str(tmp_path / "events.jsonl")
        log.export_jsonl(path)
        loaded = ReasoningEventLog.load_jsonl(path)
        # query and replay should still work on loaded log
        assert len(loaded.query(task_id="t1")) == 4
        assert loaded.has_chain("t1", [
            "TASK_OBSERVED", "NEAR_SOLVED_STORED",
            "TASK_RESUMED", "TASK_PROMOTED_TO_SOLVED",
        ])


# ── 10. export_summary_md creates valid markdown ─────────────────────

class TestExportSummaryMd:
    def test_creates_file(self, tmp_path):
        log = _build_promotion_log("t1")
        path = str(tmp_path / "summary.md")
        log.export_summary_md(path)
        assert os.path.isfile(path)

    def test_content_is_markdown(self, tmp_path):
        log = _build_promotion_log("t1")
        path = str(tmp_path / "summary.md")
        log.export_summary_md(path)
        with open(path) as f:
            text = f.read()
        assert text.startswith("# Reasoning Event Summary")
        assert "Total events: 4" in text
        assert "Unique tasks: 1" in text
        assert "Promoted tasks: 1" in text
        assert "## Event Type Counts" in text
        assert "## Promoted Tasks" in text
        assert "- t1" in text

    def test_creates_parent_dirs(self, tmp_path):
        log = ReasoningEventLog()
        log.emit("TASK_OBSERVED", "t1", {}, "mod")
        path = str(tmp_path / "deep" / "nested" / "summary.md")
        log.export_summary_md(path)
        assert os.path.isfile(path)


# ── 11. export_task_lineages creates per-task files ───────────────────

class TestExportTaskLineages:
    def test_creates_per_task_files(self, tmp_path):
        log = _build_promotion_log("t1")
        log.emit("TASK_OBSERVED", "t2", {}, "mod")
        out_dir = str(tmp_path / "lineages")
        n = log.export_task_lineages(out_dir)
        assert n == 2
        assert os.path.isfile(os.path.join(out_dir, "t1.jsonl"))
        assert os.path.isfile(os.path.join(out_dir, "t2.jsonl"))

    def test_file_contents(self, tmp_path):
        log = _build_promotion_log("t1")
        out_dir = str(tmp_path / "lineages")
        log.export_task_lineages(out_dir)
        with open(os.path.join(out_dir, "t1.jsonl")) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 4
        first = json.loads(lines[0])
        assert first["event_type"] == "TASK_OBSERVED"

    def test_empty_log(self, tmp_path):
        log = ReasoningEventLog()
        out_dir = str(tmp_path / "lineages")
        n = log.export_task_lineages(out_dir)
        assert n == 0
        assert os.path.isdir(out_dir)


# ── 12. Global log singleton ─────────────────────────────────────────

class TestGlobalLog:
    def test_get_global_log_returns_same_instance(self):
        reset_global_log()
        a = get_global_log()
        b = get_global_log()
        assert a is b

    def test_reset_creates_new_instance(self):
        reset_global_log()
        a = get_global_log()
        a.emit("TASK_OBSERVED", "t1", {}, "mod")
        assert len(a) == 1
        reset_global_log()
        b = get_global_log()
        assert len(b) == 0
        assert a is not b

    def test_global_log_is_reasoning_event_log(self):
        reset_global_log()
        assert isinstance(get_global_log(), ReasoningEventLog)
