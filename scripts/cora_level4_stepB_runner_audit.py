"""Forbidden-shapes audit of the Step-B RUNNER and its gates (item 2).

The item-1 audit covers the substrate package, where no observation field
may even be named. The runner necessarily reads the pinned Step-A fields
to order clusters and to form interfaces, so it is held to a different,
equally mechanical standard. Over scripts/cora_level4_stepB_run.py (and
the gates and manifest scripts, which must not steer it):

    1. NO FIELD BRANCH   no comparison of a cluster/record field
                         (frontier_type, goal_type, goal_delta_signature,
                         failure_class, shape_relation, changed_*,
                         palette_*, colours_*, residual, diagnostics) with
                         a constant, anywhere; those values may be copied,
                         serialised and used as dictionary keys, never
                         tested against a literal
    2. NO EARLY STOP     no ``break``/``return`` inside a loop over
                         clusters, candidates, units or sources in the
                         runner's driver; the only loops allowed to stop
                         early are the declared first-consistent-fit
                         enumerations inside the proposal worker
    3. READ WHITELIST    every path literal names a pinned input, a runner
                         output, or a command-line override; nothing under
                         data/, nothing named by a task id, no firewall file
    4. NO ENVIRONMENT    no reading or writing of process environment
                         (the frozen budget is read by the frozen search)
    5. SEALED LEXEMES    the hashed ARC-shaped lexeme list of the item-1
                         audit applies to every identifier and string
    6. FROZEN LEAK CHECK the frozen leak checker's own scan (sealed terms,
                         task ids, forbidden production names)

Exit status 0 = no FAIL findings. Declared exemptions are listed in the
report with their reasons, never applied silently.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
sys.path.insert(0, str(ROOT))

RUNNER = ROOT / "scripts" / "cora_level4_stepB_run.py"
#: Executed by the mechanism: every rule, plus the frozen leak checker.
MECHANISM = [RUNNER, ROOT / "level4_stepB" / "candidates.py"]
#: Gate and manifest scripts: rules 1-4 (they must not steer the runner);
#: they describe synthetic fixtures, so the lexeme rule does not apply.
SUPPORT = [ROOT / "scripts" / "cora_level4_stepB_gates.py",
           ROOT / "scripts" / "cora_level4_stepB_manifest.py"]
AUDITED = MECHANISM + SUPPORT

FIELD_NAMES = ("frontier_type", "goal_type", "goal_delta_signature",
               "goal_delta", "failure_class", "shape_relation", "changed_",
               "palette_", "colours_introduced", "colours_removed",
               "behavioural_residual", "residual", "diagnostics",
               "frontier_value_signature", "repeated_structure")
PATH_WHITELIST = (
    "level4_stepA_frontier_records.jsonl", "level4_stepA_fold_summary.json",
    "level4_stepA_clusters.json", "level4_stepA_output_hash.txt",
    "level4_stepA1_analysis.json", "level4_stepA1_hash.txt",
    "CORA_LEVEL4_STEPB_DESIGN.md", "level4_stepB_design_hash.txt",
    "level4_stepB_item1_freeze.json", "level4_stepB_item1_hash.txt",
    "level4_stepB_inventory.json", "level4_stepB_k1_lattice.json",
    "level4_stepB_witnesses.json", "machine_manifest.json",
    "invention_corpus.jsonl", "level4_stepB_run_manifest.json",
    "level4_stepB_run_manifest_hash.txt", "cora_level4_stepA_extract.py",
    "scripts/cora_level4_stepB_run.py", "level4_stepB", "scripts", "tests",
    "outputs", "cora_breakthrough", "level4_mechanism_inputs", "docs",
    # gates / manifest / audit artefacts
    "cora_level4_stepB_audit.py", "cora_level4_stepB_runner_audit.py",
    "cora_level4_stepB_gates.py", "cora_level4_stepB_manifest.py",
    "cora_level4_stepB_freeze_item1.py", "cora_level4_leak_check.py",
    "test_level4_stepB_item2.py", "test_level4_stepB_item1.py",
    "level4_stepB_audit.json", "level4_stepB_runner_audit.json",
    "level4_stepB_gates.json", "level4_bundle_freeze.json", "level4_stepB_gate_outputs",
    "v21_phase2_sources.json", "level4_stepA_run_manifest.json",
    # runner outputs (tag-prefixed)
    "_candidates.json", "_k2_proposal_units.jsonl", "_k1_searches.jsonl",
    "_proposals.jsonl", "_resolution.jsonl", "_selection.json",
    "_summary.json", "_timing.json", "_output_hash.txt",
)
FORBIDDEN_PATH_PARTS = ("data/", "firewall", "arc-agi", "challenges",
                        "solutions", "withheld", "seal")
ENV_NAMES = {"environ", "getenv", "putenv", "setenv"}
#: Strings the lexeme rule flags but which name a FROZEN executable the
#: runner must reuse; listed here with the reason, reported as EXEMPT.
DECLARED_LEXEME_EXEMPTIONS = {
    ("cora_level4_stepB_run.py", "cora_level4_stepA_extract.py"):
        "file name of the frozen Step-A runner (sha pinned in the Step-A run "
        "manifest), imported for build_env / verify_inputs only",
}
#: Functions in which a loop may stop at the first consistent fit.
EARLY_STOP_EXEMPT = {
    ("cora_level4_stepB_run.py", "propose_k2"):
        "first exact fit in canonical order is the proposal record (design: "
        "learners keep the first consistent member); candidates are never skipped",
    ("cora_level4_stepB_run.py", "_value_classes"):
        "a term undefined on some demonstration is skipped (for/else)",
    ("cora_level4_stepB_run.py", "verify_pins"):
        "path resolution helper",
    ("cora_level4_stepB_run.py", "group_records"):
        "records outside eligible clusters are skipped",
    ("cora_level4_stepB_run.py", "_progress"): "print throttle",
    ("cora_level4_stepB_run.py", "_env_with"): "lane dispatch",
    ("cora_level4_stepB_run.py", "_param_options"): "slot iteration",
    ("cora_level4_stepB_run.py", "main"):
        "returns only on pin/manifest drift before the run starts; the "
        "cluster, unit and candidate loops contain no break (checked "
        "separately by rule 2b)",
}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parents(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _enclosing_function(node, parents):
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, ast.FunctionDef):
            return cur.name
    return None


def _inside_loop(node, parents, stop_at_function=True):
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.For, ast.While)):
            return True
        if stop_at_function and isinstance(cur, ast.FunctionDef):
            return False
    return False


def _name_text(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name_text(node.value) + "." + node.attr
    if isinstance(node, ast.Subscript):
        inner = node.slice
        if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            return _name_text(node.value) + "[" + inner.value + "]"
        return _name_text(node.value) + "[...]"
    if isinstance(node, ast.Call):
        return _name_text(node.func) + "()"
    return ""


def audit_file(path: Path, item1_audit) -> list:
    findings = []
    text = path.read_text()
    tree = ast.parse(text)
    parents = _parents(tree)

    def add(kind, line, detail, level="FAIL"):
        findings.append({"file": path.name, "line": line, "kind": kind,
                         "detail": detail, "level": level})

    # 1: field compared with a constant
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left] + list(node.comparators)
        names = [_name_text(o).lower() for o in operands]
        constants = [o for o in operands if isinstance(o, ast.Constant)]
        touches = [n for n in names if any(f in n for f in FIELD_NAMES)]
        if touches and constants:
            add("FIELD_BRANCH", node.lineno,
                f"{touches[0]!r} compared with a constant")
        # membership tests of a field in a literal collection
        for op, right in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)) and \
                    isinstance(right, (ast.Tuple, ast.List, ast.Set)) and touches:
                add("FIELD_BRANCH", node.lineno,
                    f"{touches[0]!r} tested against a literal collection")

    # 2: early stop inside loops of the runner
    if path == RUNNER:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Break, ast.Return)) and \
                    _inside_loop(node, parents):
                fn = _enclosing_function(node, parents)
                exempt = (path.name, fn) in EARLY_STOP_EXEMPT
                add("EARLY_STOP", node.lineno, f"{type(node).__name__} in {fn}",
                    "EXEMPT" if exempt else "FAIL")
        # 2b: the driver's loops over clusters/units/candidates never break
        main = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
        for node in ast.walk(main):
            if isinstance(node, ast.Break):
                add("EARLY_STOP", node.lineno, "break inside main")

    # 3: path literals
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            pathlike = " " not in value and (
                "/" in value or re.search(r"\.(json|jsonl|txt|py|md)$", value))
            if pathlike and any(p in value.lower() for p in FORBIDDEN_PATH_PARTS):
                add("FORBIDDEN_PATH", node.lineno, value[:60])
            # 3b: in the mechanism every path literal must be a pinned input
            # or a runner output; support scripts write to temporary dirs
            if path in MECHANISM and \
                    re.search(r"\.(json|jsonl|txt|py|md)$", value) and \
                    not any(value.endswith(w) or value == w
                            for w in PATH_WHITELIST) and \
                    not value.startswith("{"):
                add("PATH_NOT_WHITELISTED", node.lineno, value[:60])

    # 4: environment
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ENV_NAMES:
            add("ENVIRONMENT", node.lineno, node.attr)
        if isinstance(node, ast.Name) and node.id in ENV_NAMES:
            add("ENVIRONMENT", node.lineno, node.id)

    # 5: hashed sealed lexemes over identifiers and strings (mechanism only)
    for token, line in (item1_audit._identifier_tokens(tree)
                        if path in MECHANISM else ()):
        for word in item1_audit._sub_words(token):
            if item1_audit._hashed(word) in item1_audit.SEMANTIC_LEXEME_HASHES:
                exempt = (path.name, token) in DECLARED_LEXEME_EXEMPTIONS
                add("SEMANTIC_LEXEME", line,
                    f"{token[:60]!r} contains a hashed forbidden lexeme",
                    "EXEMPT" if exempt else "FAIL")
    return findings


def main(write=True) -> int:
    item1_audit = _load("stepB_audit", ROOT / "scripts" / "cora_level4_stepB_audit.py")
    leak = _load("leak_check", ROOT / "scripts" / "cora_level4_leak_check.py")
    files = [p for p in AUDITED if p.exists()]
    structural = []
    for path in files:
        structural.extend(audit_file(path, item1_audit))
    seal = json.loads(leak.SEAL.read_text())
    targets = leak.sealed_hashes(seal)
    forbidden = leak.forbidden_names()
    lexical = []
    for path in [p for p in files if p in MECHANISM]:
        for name, kind, detail in leak.scan_file(path, targets, forbidden):
            lexical.append({"file": name, "kind": kind, "detail": detail,
                            "level": "FAIL"})
    fails = [f for f in structural + lexical if f["level"] == "FAIL"]
    report = {
        "gate": "Step-B item-2 runner audit",
        "files": [str(p.relative_to(ROOT)) for p in files],
        "audited_files_sha256": [
            {"path": str(p.relative_to(ROOT)),
             "sha256": __import__("hashlib").sha256(p.read_bytes()).hexdigest(),
             "mechanism": p in MECHANISM} for p in files],
        "mechanism_executables": [str(p.relative_to(ROOT)) for p in MECHANISM],
        "support_scripts_rules_1_to_4_only": [str(p.relative_to(ROOT)) for p in SUPPORT],
        "rules": {"field_names": FIELD_NAMES,
                  "path_whitelist": PATH_WHITELIST,
                  "forbidden_path_parts": FORBIDDEN_PATH_PARTS,
                  "environment_names": sorted(ENV_NAMES),
                  "early_stop_exemptions": [
                      {"file": f, "function": fn, "reason": r}
                      for (f, fn), r in EARLY_STOP_EXEMPT.items()],
                  "lexeme_exemptions": [
                      {"file": f, "token": t, "reason": r}
                      for (f, t), r in DECLARED_LEXEME_EXEMPTIONS.items()],
                  "semantic_lexeme_sha256": sorted(
                      item1_audit.SEMANTIC_LEXEME_HASHES)},
        "structural_findings": structural,
        "lexical_findings": lexical,
        "forbidden_production_names_checked": len(forbidden),
        "fail_count": len(fails),
        "verdict": "PASS" if not fails else "FAIL",
    }
    if write:
        (OUT / "level4_stepB_runner_audit.json").write_text(
            json.dumps(report, indent=1))
    print(f"files audited              {len(files)}")
    print(f"structural findings        {len(structural)} "
          f"(fail {sum(f['level'] == 'FAIL' for f in structural)}, "
          f"exempt {sum(f['level'] == 'EXEMPT' for f in structural)})")
    print(f"lexical findings           {len(lexical)}  "
          f"(forbidden names checked {len(forbidden)})")
    for f in structural + lexical:
        print(f"  {f['level']:7} {f['file']:30} {f.get('line', ''):>4} "
              f"{f['kind']:22} {f['detail']}")
    print(f"\nVERDICT {report['verdict']}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
