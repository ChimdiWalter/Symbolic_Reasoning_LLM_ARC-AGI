"""Growth extensions: the reach v1 successor to the v1.7 compiler for the
native engine (v1.7 compiles meta-AST block schemas for the K* expression
phase and is not edited or reused here).

An extension e is one growth relation from cora_reach.relations with fixed
parameters, in a closed canonical form, named by its content. It is
human-designed generic machinery instantiated at task time; its parameters
are chosen from failure evidence by cora_reach.construct.
"""
from __future__ import annotations

import hashlib
import json
import os

from cora_reach import relations as REL

FORMAT = "cora-growth-extension/1"
VERSION = "reach-v1"
KEYS = frozenset({"format", "version", "family", "params", "name"})


class ExtensionError(Exception):
    pass


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def identity() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for name in ("relations.py", "growth_ext.py"):
        with open(os.path.join(here, name), "rb") as handle:
            h.update(name.encode() + b"\0" + handle.read())
    return h.hexdigest()


def _check(family, params):
    if family not in REL.FAMILIES:
        raise ExtensionError(f"unknown family {family!r}")
    domain, _fn = REL.FAMILIES[family]
    if set(params) != set(domain):
        raise ExtensionError(f"{family}: parameters {sorted(params)} != {sorted(domain)}")
    for k, v in params.items():
        if v not in domain[k]:
            raise ExtensionError(f"{family}: {k}={v!r} outside its finite domain")


def make(family: str, params: dict) -> dict:
    _check(family, params)
    body = {"format": FORMAT, "version": VERSION, "family": family,
            "params": {k: params[k] for k in sorted(params)}}
    body["name"] = "gx_" + hashlib.sha256(canonical_json(body)).hexdigest()[:16]
    return body


def serialize(ext) -> bytes:
    return canonical_json(ext)


def load(data: bytes) -> dict:
    """Rebuild from the family and parameters; the bytes must be identical."""
    try:
        d = json.loads(data)
    except ValueError as exc:
        raise ExtensionError(f"unparsable: {exc}")
    if not isinstance(d, dict) or set(d) != KEYS or d["format"] != FORMAT or d["version"] != VERSION:
        raise ExtensionError("not a reach-v1 growth extension")
    rebuilt = make(d["family"], d["params"])
    if serialize(rebuilt) != data:
        raise ExtensionError("bytes differ from the canonical form of this body")
    return rebuilt


def render(ext, cells, grid) -> set:
    """The added cells of the relation for an object (cells) in a scene (2-D array)."""
    return REL.apply(ext["family"], ext["params"], set(cells), grid)
