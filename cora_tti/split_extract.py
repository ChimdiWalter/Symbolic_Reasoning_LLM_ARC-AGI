"""Filtered extraction from JSON files that mix licensed and sealed entries.

The raw ARC training files hold Experience, Promotion and Lockbox200 tasks side
by side, and the Lockbox manifest lists every split. A gate stage licensed to
see Promotion or E_transfer tasks must get those tasks without decoding anything
else. json.load cannot do that: it decodes the whole file into Python objects.

This module scans the bytes of a JSON object for structure only. For each
member it finds where the key ends and where the value ends, tracking string
state and nesting depth, and compares the raw key bytes with the JSON encoding
of each licensed key. Only a licensed member's value is ever passed to
json.loads.

INVARIANT. Bytes of unlicensed keys and values are read transiently and scanned
only for string boundaries and nesting. They are never decoded into Python
objects, retained, printed or returned. Callers receive the licensed members,
the licensed keys that were not found, and a count of skipped members.
"""
from __future__ import annotations

import json
from pathlib import Path

_WHITESPACE = b" \t\r\n"
_QUOTE, _BACKSLASH = 0x22, 0x5C
_OPENERS, _CLOSERS = (0x7B, 0x5B), (0x7D, 0x5D)
_COLON, _COMMA, _OBJECT_OPEN, _OBJECT_CLOSE = 0x3A, 0x2C, 0x7B, 0x7D


class ExtractionError(ValueError):
    """The file does not have the declared structure."""


def _skip_whitespace(buf: bytes, i: int) -> int:
    n = len(buf)
    while i < n and buf[i] in _WHITESPACE:
        i += 1
    return i


def _string_end(buf: bytes, i: int) -> int:
    """Index just past the string that starts at i, scanning escapes without decoding."""
    if i >= len(buf) or buf[i] != _QUOTE:
        raise ExtractionError("expected a string")
    i, n = i + 1, len(buf)
    while i < n:
        c = buf[i]
        if c == _BACKSLASH:
            i += 2
            continue
        if c == _QUOTE:
            return i + 1
        i += 1
    raise ExtractionError("unterminated string")


def _value_end(buf: bytes, i: int) -> int:
    """Index just past the JSON value that starts at i, without decoding it."""
    i = _skip_whitespace(buf, i)
    if i >= len(buf):
        raise ExtractionError("expected a value")
    c = buf[i]
    if c == _QUOTE:
        return _string_end(buf, i)
    if c in _OPENERS:
        expected, n = [], len(buf)
        while i < n:
            c = buf[i]
            if c == _QUOTE:
                i = _string_end(buf, i)
                continue
            if c in _OPENERS:
                expected.append(_CLOSERS[_OPENERS.index(c)])
            elif c in _CLOSERS:
                if not expected or expected.pop() != c:
                    raise ExtractionError("mismatched brackets")
                if not expected:
                    return i + 1
            i += 1
        raise ExtractionError("unterminated container")
    n, start = len(buf), i
    while i < n and buf[i] not in b",}] \t\r\n":
        i += 1
    if i == start:
        raise ExtractionError("expected a value")
    return i


def _members(buf: bytes, i: int):
    """Yield (raw key bytes, value start, value end) for the object at i. Nothing is decoded."""
    i = _skip_whitespace(buf, i)
    if i >= len(buf) or buf[i] != _OBJECT_OPEN:
        raise ExtractionError("expected an object")
    i = _skip_whitespace(buf, i + 1)
    if i < len(buf) and buf[i] == _OBJECT_CLOSE:
        return
    while True:
        i = _skip_whitespace(buf, i)
        key_end = _string_end(buf, i)
        raw_key = buf[i:key_end]
        i = _skip_whitespace(buf, key_end)
        if i >= len(buf) or buf[i] != _COLON:
            raise ExtractionError("expected ':'")
        value_start = _skip_whitespace(buf, i + 1)
        value_end = _value_end(buf, value_start)
        yield raw_key, value_start, value_end
        i = _skip_whitespace(buf, value_end)
        if i < len(buf) and buf[i] == _COMMA:
            i += 1
            continue
        if i < len(buf) and buf[i] == _OBJECT_CLOSE:
            return
        raise ExtractionError("expected ',' or '}'")


def _decode(fragment: bytes):
    """Decode one licensed value. A malformed value is a structure error, reported without content."""
    try:
        return json.loads(fragment)
    except ValueError:
        raise ExtractionError("a licensed member is not valid JSON") from None


def _encoded(key: str) -> bytes:
    return json.dumps(key, ensure_ascii=False).encode()


def extract_members(path, keys) -> tuple:
    """Top-level members whose keys are licensed: (found, skipped_count, missing_keys)."""
    wanted = {_encoded(k): k for k in keys}
    buf = Path(path).read_bytes()
    found, skipped = {}, 0
    for raw_key, start, end in _members(buf, 0):
        key = wanted.get(raw_key)
        if key is None:
            skipped += 1
            continue
        found[key] = _decode(buf[start:end])
    missing = sorted(set(keys) - set(found))
    return found, skipped, missing


def extract_path(path, key_path) -> tuple:
    """The single value at a declared path of object keys: (value, skipped_count).

    Sibling members at every level are skipped undecoded. A path that is not
    present raises ExtractionError, which a gate stage records as
    SCHEMA_ASSUMPTION_FAILED.
    """
    if not key_path:
        raise ValueError("key_path must name at least one key")
    buf = Path(path).read_bytes()
    start, skipped = 0, 0
    for key in key_path:
        target = _encoded(key)
        for raw_key, value_start, _value_stop in _members(buf, start):
            if raw_key == target:
                start = value_start
                break
            skipped += 1
        else:
            raise ExtractionError("the declared key path is not present")
    end = _value_end(buf, start)
    return _decode(buf[start:end]), skipped
