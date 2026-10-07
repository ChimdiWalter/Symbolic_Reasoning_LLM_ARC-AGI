"""Reasoner-process isolation (protocol section 5).

install() adds a CPython audit hook, before any project import, that
REFUSES and records every attempt by the reasoner process to open or list a
forbidden path or to start another process. The reasoner's only task input
is its bundle; everything else it may read is code, the frozen library and
the frozen v1.8 selector artifact. The log written by dump() is checked by
the coordinator and by the terminal verifier.
"""
from __future__ import annotations

import json
import os
import sys

PIPELINE = "/deltos/e/lesion_phes/code/python/pipeline"
ARC2026 = os.path.join(PIPELINE, "Reasoning_Project_arc2026")
#: substrings (lower-cased path) the reasoner may never open or list
FORBIDDEN_SUBSTRINGS = (
    "/data/arc/", "arc-agi_", "solutions.json", "_solutions", "pilot_v1_evaluator", "keymap",
    "dev60_challenges", "holdout", "lockbox", "e_transfer", "/.git/",
    "/records/pilot_v1/selection.json",
)
#: whole trees the reasoner may never open or list (the main project: sealed
#: records, Step B; the separate VDCG project)
FORBIDDEN_TREES = (os.path.join(PIPELINE, "Reasoning_Project") + os.sep,
                   os.path.join(PIPELINE, "VDCG") + os.sep)
SPAWN_EVENTS = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn",
                "os.fork", "os.forkpty", "pty.spawn")
LIST_EVENTS = ("os.listdir", "os.scandir", "glob.glob")

_STATE = {"installed": False, "bundle": None, "denied": [], "opened_dirs": set(), "bundle_opened": False}


def _norm(path):
    if isinstance(path, int):
        return None
    if isinstance(path, bytes):
        path = os.fsdecode(path)
    try:
        path = os.fspath(path)
    except TypeError:
        return None
    if not isinstance(path, str):
        return None
    return os.path.normpath(os.path.join(os.getcwd(), path)) if not os.path.isabs(path) \
        else os.path.normpath(path)


def forbidden(path: str) -> str | None:
    """The rule a path breaks, or None."""
    low = path.lower()
    if _STATE["bundle"] is not None and path == _STATE["bundle"]:
        return None
    for tree in FORBIDDEN_TREES:
        if path.startswith(tree) or path + os.sep == tree:
            return f"tree {tree}"
    for s in FORBIDDEN_SUBSTRINGS:
        if s in low:
            return f"substring {s}"
    if path.startswith(os.path.join(ARC2026, "records") + os.sep):
        return "records outside the bundle"
    return None


def _hook(event, args):
    if event == "open":
        p = _norm(args[0]) if args else None
        if p is None:
            return
        rule = forbidden(p)
        if rule:
            _STATE["denied"].append({"event": event, "path": p, "rule": rule})
            raise PermissionError(f"pilot isolation: {p} ({rule})")
        if p == _STATE["bundle"]:
            _STATE["bundle_opened"] = True
        _STATE["opened_dirs"].add(os.path.dirname(p))
    elif event in LIST_EVENTS:
        p = _norm(args[0]) if args and args[0] is not None else _norm(".")
        if p is None:
            return
        rule = forbidden(p)
        if rule:
            _STATE["denied"].append({"event": event, "path": p, "rule": rule})
            raise PermissionError(f"pilot isolation: listing {p} ({rule})")
    elif event.startswith(SPAWN_EVENTS):
        _STATE["denied"].append({"event": event, "path": None, "rule": "process spawn"})
        raise PermissionError(f"pilot isolation: {event} refused in the reasoner")


def install(bundle_path: str) -> None:
    """Install once per process, before any project import."""
    if _STATE["installed"]:
        return
    _STATE["bundle"] = os.path.normpath(os.path.abspath(bundle_path))
    sys.addaudithook(_hook)
    _STATE["installed"] = True


def report() -> dict:
    return {"installed": _STATE["installed"], "bundle": _STATE["bundle"],
            "bundle_opened": _STATE["bundle_opened"], "denied": list(_STATE["denied"]),
            "opened_dirs": sorted(_STATE["opened_dirs"])}


def dump(path: str) -> None:
    """Write the isolation log (an allowed path chosen by the coordinator)."""
    data = json.dumps(report(), sort_keys=True).encode()
    with open(path, "wb") as handle:
        handle.write(data)


def audit_log(rep: dict) -> list:
    """Problems in an isolation log: hook missing, bundle not the input,
    any refused access, or any opened directory under a forbidden rule."""
    problems = []
    if not rep.get("installed"):
        problems.append("hook not installed")
    if not rep.get("bundle_opened"):
        problems.append("bundle never opened")
    for d in rep.get("denied", []):
        problems.append(f"refused {d['event']} {d['path']} ({d['rule']})")
    bundle_dir = os.path.dirname(rep.get("bundle") or "")
    for d in rep.get("opened_dirs", []):
        if d == bundle_dir:
            continue
        rule = forbidden(d + os.sep + "x")
        if rule:
            problems.append(f"opened under {d} ({rule})")
    return problems
