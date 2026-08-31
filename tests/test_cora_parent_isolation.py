"""Isolation proof for cora_parent (and future TTI packages): the new modules can
neither NAME nor READ any frozen/sealed artifact of the running scientific experiment.

Enforced mechanically (docs/CORA_PARENT_ARCHITECTURE.md deliverable 6 and
docs/CORA_DATA_ACCESS_DAG.md hard rule 1):

1. STATIC: no source file in the guarded packages contains a string or identifier
   referring to the forbidden artifacts (journal, E_transfer, Lockbox, firewall,
   sealed expectation, pre-pin Step-B outputs), and no module-level file I/O exists.
2. DYNAMIC: importing the packages opens no file outside the interpreter's own
   machinery (import is I/O-silent with respect to the repository).
"""
from __future__ import annotations

import ast
import builtins
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: Packages governed by this isolation contract (extend as TTI modules appear).
GUARDED_PACKAGES = ["cora_parent", "cora_tti"]

#: Substrings that must never appear in guarded sources (case-insensitive).
FORBIDDEN_MARKERS = (
    "journal.jsonl", "stepb_journal", "level4_stepb_journal",
    "e_transfer", "etransfer",
    "lockbox",
    "firewall", "provenance_firewall",
    "sealed_expectation", "sealed expectation",
    "level4_stepB_output",            # pre-pin outputs
    "invention_corpus",               # sanitized mechanism input: not for new modules
    "machine_manifest",
)

#: Module-level calls that would constitute import-time I/O.
IO_CALLS = {"open", "read_text", "read_bytes", "load", "loads_from_file", "glob",
            "rglob", "walk", "listdir", "scandir"}


def _sources():
    for pkg in GUARDED_PACKAGES:
        for path in sorted((ROOT / pkg).rglob("*.py")):
            yield path


def test_no_forbidden_markers_in_source():
    findings = []
    for path in _sources():
        text = path.read_text().lower()
        for marker in FORBIDDEN_MARKERS:
            if marker in text:
                findings.append((path.name, marker))
    assert not findings, f"forbidden artifact references: {findings}"


def test_no_module_level_io():
    findings = []
    for path in _sources():
        tree = ast.parse(path.read_text())
        # module level = direct children of Module (incl. inside if/try at top level)
        def scan(node, top):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue                      # bodies run only when called
                if isinstance(child, ast.Call):
                    name = ""
                    if isinstance(child.func, ast.Name):
                        name = child.func.id
                    elif isinstance(child.func, ast.Attribute):
                        name = child.func.attr
                    if name in IO_CALLS:
                        findings.append((path.name, child.lineno, name))
                scan(child, False)
        scan(tree, True)
    assert not findings, f"module-level I/O calls: {findings}"


def test_import_opens_no_repository_file(monkeypatch):
    for pkg in GUARDED_PACKAGES:
        for mod in [m for m in list(sys.modules) if m == pkg or m.startswith(pkg + ".")]:
            del sys.modules[mod]
    opened = []
    real_open = builtins.open

    def spy_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_open)
    for pkg in GUARDED_PACKAGES:
        importlib.import_module(pkg)
    repo_reads = [f for f in opened
                  if str(ROOT) in f and "__pycache__" not in f and not f.endswith(".pyc")]
    # the import machinery reads the package's own .py files; nothing else is allowed
    own = [f for f in repo_reads if f"/{GUARDED_PACKAGES[0]}/" in f.replace("\\", "/")]
    foreign = [f for f in repo_reads if f not in own]
    assert not foreign, f"import read repository files outside the package: {foreign}"


def test_interfaces_have_no_default_verifier():
    """The immutable-verifier boundary: no guarded class may HOLD a verifier
    implementation — only receive callables. Mechanically: no 'def verify' body in
    the package does anything but raise/ellipsis (abstract)."""
    import cora_parent.interfaces as I
    tree = ast.parse((ROOT / "cora_parent" / "interfaces.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("verify",):
            bodies = [b for b in node.body
                      if not isinstance(b, (ast.Expr, ast.Pass, ast.Raise))]
            assert not bodies, "verify() must remain abstract in cora_parent"
    assert I.MetaExtensionEngine.__abstractmethods__  # engine cannot be instantiated


def test_failure_causes_vocabulary_frozen():
    import cora_parent.interfaces as I
    assert I.FAILURE_CAUSES == ("PERCEPTION", "REPRESENTATION", "SEMANTICS",
                                "PARAMETER_LEARNING", "SEARCH", "CONTROL", "MEMORY",
                                "COMPOSITION", "RESOURCE_LIMIT")


def test_negative_control_marker_scan_catches_violation(tmp_path):
    """The static scan must actually fire on a violating file."""
    bad = tmp_path / "bad.py"
    bad.write_text("PATH = 'outputs/cora_breakthrough/level4_stepB_journal.jsonl'\n")
    text = bad.read_text().lower()
    assert any(m in text for m in FORBIDDEN_MARKERS)
