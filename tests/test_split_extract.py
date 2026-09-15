"""Tests for filtered extraction: licensed members come back, nothing else is ever decoded."""
from __future__ import annotations

import json

import pytest

from cora_tti import split_extract as SX

SENTINEL = "LOCKBOX_SENTINEL_MUST_NEVER_BE_DECODED"


@pytest.fixture
def raw(tmp_path):
    tasks = {
        "aaaa1111": {"train": [{"input": [[1, 2]], "output": [[2, 1]]}], "test": [{"input": [[3]]}]},
        "bbbb2222": {"train": [{"input": [[0]], "output": [[0]]}], "note": SENTINEL + ' } ] " \\ {'},
        "cccc3333": {"train": [], "test": [{"input": [[4, 4]]}]},
    }
    path = tmp_path / "arc-agi_training_challenges.json"
    path.write_text(json.dumps(tasks, indent=2))
    return path


def test_only_licensed_members_are_returned(raw):
    found, skipped, missing = SX.extract_members(raw, ["aaaa1111", "zzzz9999"])
    assert list(found) == ["aaaa1111"]
    assert found["aaaa1111"]["test"] == [{"input": [[3]]}]
    assert skipped == 2
    assert missing == ["zzzz9999"]


def test_unlicensed_members_are_never_decoded(raw, monkeypatch):
    decoded, real = [], json.loads

    def recording(data, *args, **kwargs):
        decoded.append(bytes(data) if isinstance(data, (bytes, bytearray)) else data.encode())
        return real(data, *args, **kwargs)
    monkeypatch.setattr(SX.json, "loads", recording)
    SX.extract_members(raw, ["aaaa1111"])
    assert decoded, "the licensed member must have been decoded"
    for blob in decoded:
        assert SENTINEL.encode() not in blob
        assert b"bbbb2222" not in blob and b"cccc3333" not in blob


def test_strings_with_brackets_quotes_and_escapes_are_skipped_correctly(raw):
    found, _, _ = SX.extract_members(raw, ["cccc3333"])
    assert found["cccc3333"]["test"] == [{"input": [[4, 4]]}]


def test_a_key_that_needs_escaping_still_matches(tmp_path):
    path = tmp_path / "odd.json"
    path.write_text(json.dumps({'a"b': 1, "plain": 2}))
    found, skipped, _ = SX.extract_members(path, ['a"b'])
    assert found == {'a"b': 1} and skipped == 1


def test_a_declared_nested_path_is_extracted_and_siblings_skipped(tmp_path):
    path = tmp_path / "lockbox_manifest.json"
    path.write_text(json.dumps({"version": "1.0.0", "splits": {
        "experience": ["cccc3333"], "promotion": ["aaaa1111"], "lockbox": ["bbbb2222", SENTINEL]}}))
    value, skipped = SX.extract_path(path, ["splits", "promotion"])
    assert value == ["aaaa1111"]
    assert skipped == 2


def test_the_lockbox_list_is_never_decoded_on_the_way(tmp_path, monkeypatch):
    path = tmp_path / "lockbox_manifest.json"
    path.write_text(json.dumps({"splits": {"lockbox": ["bbbb2222", SENTINEL], "promotion": ["aaaa1111"]}}))
    decoded, real = [], json.loads

    def recording(data, *args, **kwargs):
        decoded.append(bytes(data) if isinstance(data, (bytes, bytearray)) else data.encode())
        return real(data, *args, **kwargs)
    monkeypatch.setattr(SX.json, "loads", recording)
    SX.extract_path(path, ["splits", "promotion"])
    assert all(SENTINEL.encode() not in blob and b"bbbb2222" not in blob for blob in decoded)


def test_a_missing_declared_path_raises(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"splits": {"experience": []}}))
    with pytest.raises(SX.ExtractionError):
        SX.extract_path(path, ["splits", "promotion"])


@pytest.mark.parametrize("text", ['{"a": [1, 2}', '{"a" 1}', '["not", "an", "object"]', '{"a": "unterminated}'])
def test_malformed_input_raises(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text)
    with pytest.raises(SX.ExtractionError):
        SX.extract_members(path, ["a"])


def test_an_empty_object_yields_nothing(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("{ }")
    assert SX.extract_members(path, ["a"]) == ({}, 0, ["a"])
