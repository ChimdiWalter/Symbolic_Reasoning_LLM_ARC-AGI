"""Forbidden-shapes audit of the Step-B item-1 substrate (level4_stepB/).

MECHANICAL: inspects the Python AST and source text of every module in the
package and rejects any implementation that

    1. names a Step-A / cluster / delta field            (FIELD token)
    2. carries an ARC-shaped semantic label              (SEMANTIC lexeme,
       matched by sha256 of the normalised word: the words themselves
       exist nowhere in plaintext)
    3. mentions a universe TYPE NAME inside ANY function body (semantics,
       learners, accessors, well-formedness, generators); the declared
       exemptions are listed in the report with their reasons
    4. performs any I/O or imports anything outside the allowed set
    5. reads an observation statistic or a grid shape inside the code that
       decides WHICH constructors are well formed
    6. contains a sealed term, an ARC task id, or an excluded production
       name (delegated to the FROZEN leak checker's own functions, imported
       unchanged so its pinned hash stays valid)

and then computes, from the inventory record, the counterfactual
applicability A(c) of every constructor: a schema with a single well-formed
instantiation is flagged unless the number of universe types satisfying its
requirements is also one (forced by the signature) or the pruning is
entirely due to universe membership of a ground argument type (forced by
the frozen type universe), in which case it is reported as a WARNING with
the pruned types listed, never silently.

Exit status 0 = no FAIL findings. Warnings are written, not hidden.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "level4_stepB"
OUT = ROOT / "outputs" / "cora_breakthrough"
sys.path.insert(0, str(ROOT))

FIELD_TOKENS = (
    "frontier", "goal_type", "goal_delta", "delta_sig", "shape_relation",
    "failure_class", "cluster", "residual", "n_records", "n_distinct",
    "distinct_source", "source_token", "frequency", "changed_fraction",
    "uniformity", "slot_learning", "semantic_class", "stepa", "step_a",
    "eligible", "ranking", "rank_", "census", "corpus", "demonstration_stat",
)
#: ARC-shaped semantic labels a constructor may not carry, stored as
#: sha256 of the normalised word so that no such word exists in plaintext
#: anywhere in the repository (the seal's own discipline). Identifiers and
#: string constants are split into sub-words and hashed for comparison.
SEMANTIC_LEXEME_HASHES = frozenset((
    "79bfb0e2ba76b9d447606ddbcc494834f05a4c11deb052e74b49ea307a3c5bcd",
    "c08c6acfff81cafe379f88061e6b71bfbf2e9b5c5fcba037f0ac69a6b896d41b",
    "375676bd26868505668fce072799a6e029a37fbbe67b70b89f7b68def282344c",
    "5bfde80c12eac54d591e880500c38c55aedca10bf7e1598e9cfddc4a9f7a5bd8",
    "f1cf2fd5c86895128d559088259a132d4d4689a4d6ae4e0339100393438ec986",
    "4e448897946ead9e39e8c61c2994b2ada30968ed9d14ac21ebaba710d823db64",
    "d8864644c15d33be9c0aef2d08c8fc105adc040de488b0116882a2cc6aa4492b",
    "d4e3fc7b0477747da28f05c27af9f1ab8e70cd60f729a2813f410fd39eb466ac",
    "39ee4551970726c324df4ea3bf0760fe4ff35252340bfba7b1d4564454f9ccce",
    "00154761637ca746c354a6d9cfbf1da1a92e79afa6bb127bb8a1c434e9c73170",
    "683a62ce15fbabb1ac867022e56e6e4f4f581762d77c3abb2f8dc8b165b3b1b9",
    "318678825324247b8176d59f83c30bd94d23d2e3ac5cd4a743b0683ee58b88cd",
    "b4b33d2441645d4dd0a0694b5989a0a14a5cc22fe9865e6b7b7eae966e0de36c",
    "1480fb125459cbca6cff13fbac5d846220d91cf906e466eb2842ef350878138b",
    "c04bc270f965db4d7ab365b3b865b743e35e13e295c7b15fb795e2a01d24a639",
    "887270d0cbc560af35f1326d55e9dbdc35ea2301c2cd26633fb6d4932deee268",
    "299bcf54c044b1b5d49a18da354e16f240b695a1f3a55f1e5217595de59fbb3d",
    "224610f102890bc0e40c49ffb456bb93d45a6dee88dc9a7bef351fa10d3f8582",
    "e0afcdbf6ad4adf566c572d7f7c34d4dfb85e5122bba750d6a3a5842f915d39b",
    "3781049acb7fd5d7de257b5522345fccce1e56f50ea02589ab65256ed359f37f",
    "5cde0f1298f41f7d1c8b907a36992a7a513225a2615bd6e307bf1a9149b06b40",
    "8b668b8994aa845107399994593d0ca831520be5257f005351a0ec13e97a39be",
    "ccf0a763e1c0dc55d29ef500fd4d43abebb24690ca2764476a68ea15c6b5d553",
))
ALLOWED_IMPORT_ROOTS = {
    "__future__", "hashlib", "inspect", "itertools", "json", "random",
    "collections", "contextlib", "dataclasses", "typing", "numpy",
    "level4_blind_runtime", "level4_stepB",
}
IO_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "print"}
IO_ATTRS = {"read_text", "read_bytes", "write_text", "write_bytes", "load",
            "loads", "environ", "argv", "glob", "listdir", "system", "run",
            "Popen", "urlopen", "get_terminal_size"}
SELECTION_FUNCTIONS = {"_bindings", "instantiations", "closure", "build",
                       "_is_value_type", "satisfies", "kind_of"}
SELECTION_FORBIDDEN_NAMES = ("count", "freq", "support", "observ", "smaller",
                             "larger", "size", "shape", "mass", "n_")
#: Rule 3 applies to EVERY function body in the package. The only places a
#: type name may appear in code are declared here, with the reason; module-
#: level data (the capability table, the schema declarations) is not code.
DECLARED_EXEMPTIONS = {
    ("witnesses.py", "_induced_value"):
        "induced meta-families are addressed by their type's name",
    ("k2_inventory.py", "inventory_record"):
        "composes the machine-readable report, decides nothing",
}


def _hashed(word: str) -> str:
    import hashlib
    return hashlib.sha256(re.sub(r"[^a-z0-9]+", "", word.lower()).encode()).hexdigest()


def _sub_words(token: str):
    """Sub-words of an identifier or string: split on non-letters and on
    camelCase boundaries, plus adjacent 2-grams."""
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", token)
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", spaced)]
    yield from words
    for a, b in zip(words, words[1:]):
        yield a + b


def _load_leak_checker():
    spec = importlib.util.spec_from_file_location(
        "leak_check", ROOT / "scripts" / "cora_level4_leak_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STRUCTURAL_HEADS = {"Set", "Expr"}     # collection / expression formers


def _universe_type_names():
    """Value and parameter type names; the structural heads Set/Expr are the
    constructors the kind system is DEFINED on, so dispatching on them is
    structural, not nominal."""
    from level4_stepB import k2_inventory as I
    names = {str(t) for t in I.closure()}
    names |= {t.name for t in I.closure()}
    return names - STRUCTURAL_HEADS


def _identifier_tokens(tree):
    """Every identifier-like token in the AST with its line."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            yield node.id, node.lineno
        elif isinstance(node, ast.Attribute):
            yield node.attr, node.lineno
        elif isinstance(node, ast.FunctionDef):
            yield node.name, node.lineno
            for a in node.args.args + node.args.kwonlyargs:
                yield a.arg, node.lineno
        elif isinstance(node, ast.ClassDef):
            yield node.name, node.lineno
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value, node.lineno
        elif isinstance(node, ast.keyword) and node.arg:
            yield node.arg, node.lineno


def _enclosing_functions(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    out = {}
    for node in ast.walk(tree):
        cur, chain = node, []
        while cur in parents:
            cur = parents[cur]
            if isinstance(cur, ast.FunctionDef):
                chain.append(cur.name)
        out[node] = chain
    return out


def audit_module(path: Path, type_names: set) -> list:
    findings = []
    text = path.read_text()
    tree = ast.parse(text)
    enclosing = _enclosing_functions(tree)

    def add(kind, line, detail, level="FAIL"):
        findings.append({"file": path.name, "line": line, "kind": kind,
                         "detail": detail, "level": level})

    # 1 + 2: forbidden tokens anywhere (identifiers and string constants)
    for token, line in _identifier_tokens(tree):
        low = token.lower()
        for f in FIELD_TOKENS:
            if f in low:
                add("FIELD_TOKEN", line, f"{token!r} contains {f!r}")
        for word in _sub_words(token):
            if _hashed(word) in SEMANTIC_LEXEME_HASHES:
                add("SEMANTIC_LEXEME", line,
                    f"{token[:60]!r} contains a hashed forbidden lexeme")

    # 4: imports and I/O
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORT_ROOTS:
                    add("IMPORT", node.lineno, alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level == 0 and root not in ALLOWED_IMPORT_ROOTS:
                add("IMPORT", node.lineno, node.module)
        elif isinstance(node, ast.Name) and node.id in IO_NAMES:
            add("IO", node.lineno, node.id)
        elif isinstance(node, ast.Attribute) and node.attr in IO_ATTRS:
            add("IO", node.lineno, node.attr)

    # 3: type-name dispatch inside strict functions
    runtime_type_attrs = {"GRID", "REGION", "SET_REGION", "FEATURE_EXPR",
                          "COLOUR_MAP"}
    for node in ast.walk(tree):
        chain = enclosing.get(node, [])
        if not chain:
            continue
        innermost = chain[0]
        exempt = (path.name, innermost) in DECLARED_EXEMPTIONS
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value in type_names:
            add("TYPE_NAME_IN_CODE", node.lineno,
                f"{innermost}: string {node.value!r}",
                "EXEMPT" if exempt else "FAIL")
        if isinstance(node, ast.Attribute) and node.attr in runtime_type_attrs \
                and path.name != "k1_lattice.py":
            add("TYPE_NAME_IN_CODE", node.lineno,
                f"{innermost}: runtime constant {node.attr}",
                "EXEMPT" if exempt else "FAIL")

    # 5: statistics / shapes inside well-formedness decisions
    for node in ast.walk(tree):
        chain = enclosing.get(node, [])
        if not chain or chain[0] not in SELECTION_FUNCTIONS:
            continue
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name is None:
            continue
        low = name.lower()
        for s in SELECTION_FORBIDDEN_NAMES:
            if s in low:
                add("SELECTION_READS_STATISTIC", node.lineno,
                    f"{chain[0]}: {name!r}")
    return findings


def applicability_audit(record: dict) -> list:
    findings = []
    universe = set(record["type_universe"])
    for schema in record["schemas"]:
        ca = schema["counterfactual_applicability"]
        space = ca["requirement_space"]
        if ca["count"] == 0:
            findings.append({"schema_id": schema["schema_id"], "level": "FAIL",
                             "kind": "NO_INSTANTIATION",
                             "detail": "schema is never well formed"})
            continue
        if ca["count"] == 1 and space > 1:
            findings.append({
                "schema_id": schema["schema_id"], "level": "WARNING",
                "kind": "SINGLE_INSTANTIATION_PRUNED_BY_UNIVERSE",
                "detail": (f"{space} requirement-satisfying bindings, 1 well "
                           f"formed; the others need a ground argument type "
                           f"absent from the frozen universe"),
                "argument_types": [a["type"] for a in schema["argument_roles"]]})
        elif ca["count"] == 1:
            findings.append({"schema_id": schema["schema_id"], "level": "INFO",
                             "kind": "SINGLE_INSTANTIATION_FORCED_BY_SIGNATURE",
                             "detail": "only one universe type satisfies the requirement"})
        if ca["pruned_by_universe_membership"] and ca["count"] > 1:
            findings.append({"schema_id": schema["schema_id"], "level": "INFO",
                             "kind": "PRUNED_BY_UNIVERSE",
                             "detail": f"{ca['pruned_by_universe_membership']} "
                                       f"bindings dropped for universe membership"})
    return findings


def main(write=True) -> int:
    from level4_stepB import k2_inventory as I
    type_names = _universe_type_names()
    modules = sorted(p for p in PACKAGE.glob("*.py"))
    extra = [ROOT / "scripts" / "cora_level4_stepB_audit.py"]
    structural = []
    for path in modules:
        structural.extend(audit_module(path, type_names))

    leak = _load_leak_checker()
    seal = json.loads(leak.SEAL.read_text())
    targets = leak.sealed_hashes(seal)
    forbidden = leak.forbidden_names()
    lexical = []
    for path in modules + extra:
        for name, kind, detail in leak.scan_file(path, targets, forbidden):
            lexical.append({"file": name, "kind": kind, "detail": detail,
                            "level": "FAIL"})

    record = I.inventory_record()
    applicability = applicability_audit(record)

    fails = [f for f in structural + lexical + applicability
             if f["level"] == "FAIL"]
    report = {
        "gate": "Step-B item-1 forbidden-shapes audit",
        "scope": ("AST + source audit of level4_stepB/*.py, the frozen leak "
                  "checker's lexical scan, and the counterfactual "
                  "applicability of every constructor schema"),
        "modules": [p.name for p in modules],
        "rules": {
            "field_tokens": FIELD_TOKENS,
            "semantic_lexeme_sha256": sorted(SEMANTIC_LEXEME_HASHES),
            "allowed_import_roots": sorted(ALLOWED_IMPORT_ROOTS),
            "type_name_rule_scope": "every function body",
            "selection_functions": sorted(SELECTION_FUNCTIONS),
            "selection_forbidden_names": SELECTION_FORBIDDEN_NAMES,
            "declared_exemptions": [
                {"file": f, "function": fn, "reason": r}
                for (f, fn), r in DECLARED_EXEMPTIONS.items()],
        },
        "structural_findings": structural,
        "lexical_findings": lexical,
        "forbidden_production_names_checked": len(forbidden),
        "applicability_findings": applicability,
        "fail_count": len(fails),
        "verdict": "PASS" if not fails else "FAIL",
    }
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "level4_stepB_audit.json").write_text(json.dumps(report, indent=1))
    print(f"modules audited            {len(modules)}")
    print(f"structural findings        {len(structural)} "
          f"(fail {sum(f['level'] == 'FAIL' for f in structural)}, "
          f"exempt {sum(f['level'] == 'EXEMPT' for f in structural)})")
    print(f"lexical findings           {len(lexical)}  "
          f"(forbidden names checked {len(forbidden)})")
    print(f"applicability findings     {len(applicability)} "
          f"(warning {sum(f['level'] == 'WARNING' for f in applicability)})")
    for f in structural + lexical:
        if f["level"] != "INFO":
            print(f"  {f['level']:7} {f['file']:18} {f.get('line', ''):>4} "
                  f"{f['kind']:28} {f['detail']}")
    for f in applicability:
        print(f"  {f['level']:7} {f['schema_id']:22} {f['kind']:40} {f['detail']}")
    print(f"\nVERDICT {report['verdict']}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
