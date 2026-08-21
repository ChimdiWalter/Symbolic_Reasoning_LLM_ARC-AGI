"""Stage B engine half (lockbox protocol): independent-transfer promotion.

The annotation must (1) be inert with the flag off, (2) mark an operator
independent-transfer only when an UNSOLVED non-provenance task becomes
solved by a program that actually uses it, (3) respect ARC_TRANSFER_POOL,
and (4) never gate registration.
"""
from __future__ import annotations

import json

import numpy as np

from geocat_arc.object_reasoning.engine import ObjectReasoningEngine
from geocat_arc.object_reasoning.inducer import InductionConfig
from geocat_arc.object_reasoning.types import LibraryOperator

CFG = InductionConfig(budget_s=25.0)


def delete_by_color_task_v(color: int, keep_color: int):
    pairs = []
    for shift in range(3):
        inp = np.zeros((8, 8), int)
        inp[1:3, 1 + shift:3 + shift] = color
        inp[5:7, 5:7] = keep_color
        out = np.zeros((8, 8), int)
        out[5:7, 5:7] = keep_color
        pairs.append((inp, out))
    return pairs


def _promote_after_three(engine):
    for i, (dead, kept) in enumerate([(5, 3), (7, 4), (6, 1)]):
        res = engine.solve(f"syn_del_{i}", delete_by_color_task_v(dead, kept))
        assert res.solution is not None, f"variant {i} unsolved"
    return engine.promote_and_validate()


class TestTransferPromotion:
    def test_flag_off_no_annotation(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ARC_TRANSFER_PROMOTION", raising=False)
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        registered = _promote_after_three(engine)
        assert registered
        for op in engine.library.operators():
            assert op.transfer_record == {}

    def test_flag_on_provisional_without_witness(self, tmp_path, monkeypatch):
        # no unsolved non-provenance tasks cached -> nothing to witness
        monkeypatch.setenv("ARC_TRANSFER_PROMOTION", "1")
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        registered = _promote_after_three(engine)
        assert registered  # annotation never gates registration
        for op in engine.library.operators():
            assert op.transfer_record.get("status") == "provisional"
            assert op.transfer_record.get("witnesses") == []

    def test_transfer_record_round_trips(self, tmp_path):
        op = LibraryOperator(name="op_x", fragment={}, free_slots=[],
                             transfer_record={"status": "provisional",
                                              "witnesses": []})
        assert LibraryOperator.from_dict(op.to_dict()).transfer_record \
            == op.transfer_record
        # old library JSON without the field still loads
        d = op.to_dict()
        del d["transfer_record"]
        assert LibraryOperator.from_dict(d).transfer_record == {}

    def test_pool_restriction_excludes_task(self, tmp_path, monkeypatch):
        # a pool that names no cached task -> no witnesses attempted
        pool = tmp_path / "pool.json"
        pool.write_text(json.dumps(["not_a_cached_task"]))
        monkeypatch.setenv("ARC_TRANSFER_PROMOTION", "1")
        monkeypatch.setenv("ARC_TRANSFER_POOL", str(pool))
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        registered = _promote_after_three(engine)
        assert registered
        for op in engine.library.operators():
            assert op.transfer_record.get("attempted") == []
            assert op.transfer_record.get("status") == "provisional"
            assert op.transfer_record.get("pool_restricted") is True

    def test_persisted_library_carries_record(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ARC_TRANSFER_PROMOTION", "1")
        engine = ObjectReasoningEngine(tmp_path, config=CFG)
        registered = _promote_after_three(engine)
        assert registered
        stored = json.loads((tmp_path / "library.json").read_text())
        vals = list(stored.values()) if isinstance(stored, dict) else stored
        assert any(o.get("transfer_record", {}).get("status") for o in vals)
