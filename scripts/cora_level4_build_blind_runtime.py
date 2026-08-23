"""Project the frozen operational baseline into an executable blind surface.

The four sanitized JSON files are not sufficient on their own. Step A must
execute Python, and if the extractor imports the ordinary ``meta_v21`` it can
read the names and the implementations of every capability the redacted
contract deliberately hides: ``LEVEL4_REGISTRY`` carries the excluded
grounded productions, ``EVALUATORS`` carries their bodies, and A0.1 recorded
that the current runtime also holds Level-4 additions that did not exist
before the freeze. Blindness enforced only by a coding convention is not
blindness.

So the blind process gets its own package, containing E_L4* and generic
machinery and nothing else. Absence is then an environmental fact: the
excluded names are not importable, not introspectable, and not present in
the source at all.

This is a PROJECTION, not a reimplementation. Evaluator bodies are copied
verbatim out of ``meta_v21.py`` by source segment, and the reachable set is
computed as a dependency closure rather than chosen by hand, so no evaluator
behaviour, search policy, terminal vocabulary, slot learner, cost or budget
can drift while the projection is made. What is rewritten is only the parts
that would otherwise read the raw contract: the registry is baked from the
admitted grounded instantiations, and the terminal and induced type tables
are restricted to the types those productions actually use.

Everything here runs BEHIND the firewall. It may read anything; only its
output must be blind.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
SRC = ROOT / "geocat_arc" / "object_reasoning"
BLIND_PKG = ROOT / "level4_blind_runtime"

A01 = OUT / "level4_baseline_admissibility_v2.json"
A01_PIN = OUT / "level4_a01_frozen_hash.txt"

#: Names the projection supplies itself, restricted to E_L4*. They are never
#: extracted from the source module, because the originals are exactly the
#: tables that would leak: EVALUATORS holds excluded bodies, TERMINAL_VALUES
#: and INDUCED_TYPES hold types belonging to excluded capabilities, and both
#: registries are compiled from the raw contract.
PROVIDED = {"REGISTRY", "LEVEL4_REGISTRY", "EVALUATORS", "TERMINAL_VALUES",
            "INDUCED_TYPES", "CONTRACT", "INACTIVE", "CONTEXT_IMPLICIT",
            "GROUND_TYPES", "CONTRACT_PATH", "FROZEN_HASH_PATH", "ROOT",
            "load_contract", "ContractDrift", "compile_registry",
            "compile_level4_registry", "contract_inactive", "_contract_rules",
            "parse_signature", "instantiate_signature", "is_type_variable"}

#: Generic machinery the interpreter needs regardless of which productions
#: exist. Seeded explicitly so the closure starts from the whole interpreter,
#: not only from the evaluator bodies.
MACHINERY = ["Type", "T", "type_equal", "Production", "Ctx", "descriptors",
             "is_ast", "_eval", "evaluate", "type_of", "free_slots",
             "instantiate", "ast_nodes", "value_bound_count", "ast_depth",
             "to_json", "from_json", "_tuplify", "concepts_used"]

#: Type constants the search module reaches for by name.
SEARCH_TYPES = ["GRID", "SET_REGION", "FEATURE_EXPR", "COLOUR_MAP"]

#: ``Concept`` is the abstraction MECHANISM, not a withheld capability, and
#: C1 is itself part of E_L4*. The contract already exposes it as a
#: non-runtime judgement, so its name carries no information about what the
#: baseline lacks.
LEXEME_EXEMPT = {"Concept"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------
# source-level dependency closure
# --------------------------------------------------------------------------

def bound_names(node) -> set:
    """Module-level names a top-level statement binds."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    out = set()
    if isinstance(node, ast.Assign):
        for target in node.targets:
            out |= {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        out.add(node.target.id)
    return out


def referenced_names(node) -> set:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def source_segment(source: str, lines: list, node) -> str:
    """Verbatim source of a top-level statement, decorators included.

    ``ast.get_source_segment`` starts at the ``def`` or ``class`` line, which
    silently drops ``@dataclass`` and would change the semantics of what is
    supposed to be a byte-faithful projection.
    """
    start = node.lineno
    for decorator in getattr(node, "decorator_list", []):
        start = min(start, decorator.lineno)
    return "\n".join(lines[start - 1:node.end_lineno])


def closure(seeds, binders, deps) -> set:
    """Everything the seeds transitively need, minus what we supply."""
    need, seen = list(seeds), set()
    while need:
        name = need.pop()
        if name in seen or name in PROVIDED or name not in binders:
            continue
        seen.add(name)
        need.extend(deps.get(name, set()))
    return seen


#: Prose-only substitutions. A docstring that names an excluded type is still
#: a leak: ``type_equal``'s explanation happened to illustrate itself with
#: Set[Placement], which would tell the mechanism that a Placement type
#: exists somewhere it cannot see. Only comments and docstrings are touched,
#: never an expression, so behaviour is untouched and every substitution is
#: recorded in the manifest rather than made silently.
PROSE_REDACTIONS = {
    "type_equal": [("Set[Region] and Set[Placement]",
                    "Set[Region] and Set[Colour]")],
}


def redact_prose(segment: str, name: str) -> tuple:
    """Apply the recorded prose substitutions for one definition."""
    applied = []
    for old, new in PROSE_REDACTIONS.get(name, []):
        if old in segment:
            segment = segment.replace(old, new)
            applied.append({"definition": name, "from": old, "to": new})
    return segment, (applied or None)


def type_expr(t) -> str:
    """A Type term as the source that rebuilds it."""
    if not t.args:
        return f'T("{t.name}")'
    inner = ", ".join(type_expr(a) for a in t.args)
    return f'T("{t.name}", {inner})'


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------

def build_runtime(admitted: list) -> tuple:
    source = (SRC / "meta_v21.py").read_text()
    lines = source.splitlines()
    tree = ast.parse(source)

    binders, deps, order = {}, {}, []
    for node in tree.body:
        names = bound_names(node)
        if not names:
            continue
        segment = source_segment(source, lines, node)
        for name in names:
            binders[name] = segment
            deps[name] = referenced_names(node) - names
            order.append(name)

    productions = {}
    for name in admitted:
        production = V.LEVEL4_REGISTRY[name]
        productions[name] = {
            "arg_types": tuple(production.arg_types),
            "result_type": production.result_type,
            "evaluator": production.evaluate.__name__,
            "signature_text": production.contract_grades.get("signature_text", ""),
        }

    seeds = [p["evaluator"] for p in productions.values()]
    seeds += MACHINERY + SEARCH_TYPES
    keep = closure(seeds, binders, deps)

    # the type tables, restricted to what E_L4* actually uses
    used_types = set()
    for spec in productions.values():
        used_types |= {str(t) for t in spec["arg_types"]}
        used_types.add(str(spec["result_type"]))

    terminals = {k: v for k, v in V.TERMINAL_VALUES.items() if k in used_types}
    induced = sorted(t for t in V.INDUCED_TYPES if t in used_types)

    emitted, seen, redacted = [], set(), []
    for name in order:
        if name in keep and name not in seen:
            seen.add(name)
            segment, note = redact_prose(binders[name], name)
            if note:
                redacted.append(note)
            emitted.append(segment)

    registry_lines = []
    for name in sorted(productions):
        spec = productions[name]
        args = ", ".join(type_expr(t) for t in spec["arg_types"])
        args = f"({args},)" if len(spec["arg_types"]) == 1 else f"({args})"
        registry_lines.append(
            f'    "{name}": Production(\n'
            f'        "{name}", {args},\n'
            f'        {type_expr(spec["result_type"])}, {spec["evaluator"]},\n'
            f'        {{"signature_text": "{spec["signature_text"]}"}}),')

    header = f'''"""The executable surface of E_L4*, mechanically projected.

GENERATED by scripts/cora_level4_build_blind_runtime.py. Do not edit.

Every evaluator body below is a verbatim source segment of the frozen
runtime, and the set of definitions present is the dependency closure of the
{len(admitted)} admitted grounded productions. Nothing was rewritten by hand, so no
behaviour can have drifted in the projection.

What differs from the frozen runtime, and only this:

    the registry is baked from the admitted grounded instantiations rather
    than compiled from the contract, so every signature is ground and no
    type variable survives;

    the terminal and induced type tables hold only the types these
    productions use, so no type belonging to an excluded capability appears;

    definitions reachable only from excluded capabilities are absent, which
    is why blindness here is a property of the environment and not a rule
    someone has to remember to follow.

This module reads no contract and no manifest, and it has no knowledge of
what was excluded or why.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np

'''

    body = "\n\n\n".join(emitted)
    tables = (
        "\n\n\n# -- type tables, restricted to the types E_L4* uses ---------"
        "-------------\n\n"
        f"TERMINAL_VALUES = {json.dumps(terminals, indent=4)}\n\n"
        f"INDUCED_TYPES = {json.dumps(induced)}\n\n\n"
        "# -- the registry, baked from the admitted grounded instantiations "
        "----------\n\n"
        "REGISTRY = {\n" + "\n".join(registry_lines) + "\n}\n")

    text = header + body + tables
    # tuple() rather than list() for the terminal vocabularies, matching the
    # frozen runtime's own types exactly
    text = re.sub(r"TERMINAL_VALUES = \{(.*?)\n\}",
                  lambda m: "TERMINAL_VALUES = {" + m.group(1).replace(
                      "[", "(").replace("]", ")") + "\n}",
                  text, flags=re.S)
    return text, productions, terminals, induced, sorted(keep), redacted


def port(name: str, out_name: str) -> str:
    """Copy a module that contains no capability names, rewiring imports."""
    text = (SRC / name).read_text()
    text = text.replace("from . import meta_v21_concept as C",
                        "from . import concept as C")
    text = text.replace("from . import meta_v21_env as E",
                        "from . import env as E")
    text = text.replace("from . import meta_v21 as V",
                        "from . import runtime as V")
    banner = (f"\nPROJECTED from {name} for the Level-4 blind environment by\n"
              f"scripts/cora_level4_build_blind_runtime.py. The body is "
              f"unchanged except\nfor its imports, which are rewired to the "
              f"blind runtime, so search policy,\nslot learners, costs and "
              f"budgets are identical to the frozen runtime.\n")
    # appended INSIDE the existing module docstring: a second docstring would
    # displace ``from __future__`` and stop the module importing at all
    closing = text.index('"""', text.index('"""') + 3)
    return text[:closing] + banner + text[closing:]


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------

def type_names(t) -> set:
    """Every type name inside a type term, head and arguments alike."""
    out = {t.name}
    for arg in t.args:
        out |= type_names(arg)
    return out


def forbidden_lexemes(admitted: list) -> set:
    """Every production or rule name that is NOT part of E_L4*.

    Types are allowed exactly when E_L4* uses them: ``Region`` is part of the
    baseline's own vocabulary, while ``Placement`` or ``Lattice`` would tell
    the mechanism that some capability it cannot see deals in them.
    """
    admitted_bases = {V.LEVEL4_REGISTRY[n].contract_grades.get(
        "instantiated_from", n) for n in admitted}
    allowed = set(admitted) | admitted_bases | LEXEME_EXEMPT
    for name in admitted:
        production = V.LEVEL4_REGISTRY[name]
        for t in tuple(production.arg_types) + (production.result_type,):
            allowed |= type_names(t)

    names = set(V.EVALUATORS) | set(V.LEVEL4_REGISTRY) | set(V.REGISTRY)
    names |= set(V.INACTIVE)
    for section in ("active_productions", "inactive_unresolved"):
        names |= {r["rule"] for r in V.CONTRACT.get(section, [])}
    for section in ("layer_A_evidence_minimal", "layer_B_frozen_design"):
        block = V.CONTRACT.get(section, {})
        for key in ("judgements", "rules"):
            names |= {r["rule"] for r in block.get(key, [])}
    # types belonging to excluded capabilities
    names |= set(V.CONTRACT["terminals"]["types"])
    return {n for n in names if n not in allowed}


def scan(text: str, forbidden: set) -> list:
    hits = []
    for name in sorted(forbidden):
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
                     text):
            hits.append(name)
    return hits


def main():
    pinned = A01_PIN.read_text().strip()
    actual = sha(A01.read_bytes())
    if actual != pinned:
        print(f"REFUSING: A0.1 artifact {actual[:16]} does not match the "
              f"frozen pin {pinned[:16]}")
        return 1
    admissibility = json.loads(A01.read_text())
    admitted = admissibility["K_L4_star"]
    print(f"A0.1 verified {actual[:16]}; K_L4* = {len(admitted)} productions")

    (runtime_text, productions, terminals, induced, kept,
     redacted) = build_runtime(admitted)

    if BLIND_PKG.exists():
        shutil.rmtree(BLIND_PKG)
    BLIND_PKG.mkdir(parents=True)
    (BLIND_PKG / "__init__.py").write_text(
        '"""The Level-4 blind execution environment: E_L4* and nothing else.\n\n'
        'GENERATED by scripts/cora_level4_build_blind_runtime.py.\n"""\n')
    (BLIND_PKG / "runtime.py").write_text(runtime_text)
    (BLIND_PKG / "concept.py").write_text(
        port("meta_v21_concept.py", "concept.py"))
    (BLIND_PKG / "env.py").write_text(port("meta_v21_env.py", "env.py"))
    (BLIND_PKG / "search.py").write_text(port("meta_v21_search.py", "search.py"))

    # -- gate 1: the blind runtime exposes exactly K_L4* -------------------
    sys.path.insert(0, str(ROOT))
    import level4_blind_runtime.runtime as B  # noqa: E402

    if sorted(B.REGISTRY) != sorted(admitted):
        print("GATE FAILED: blind production set != K_L4*")
        print(f"  missing {sorted(set(admitted) - set(B.REGISTRY))}")
        print(f"  extra   {sorted(set(B.REGISTRY) - set(admitted))}")
        return 1

    # -- gate 2: signatures identical to the frozen instantiations ---------
    for name in admitted:
        want, got = V.LEVEL4_REGISTRY[name], B.REGISTRY[name]
        if len(want.arg_types) != len(got.arg_types) or \
                not all(V.type_equal(a, b) for a, b in
                        zip(want.arg_types, got.arg_types)) or \
                not V.type_equal(want.result_type, got.result_type):
            print(f"GATE FAILED: signature drift on {name}")
            print(f"  frozen {[str(t) for t in want.arg_types]} -> "
                  f"{want.result_type}")
            print(f"  blind  {[str(t) for t in got.arg_types]} -> "
                  f"{got.result_type}")
            return 1

    # -- gate 3: no unbound type variable survives -------------------------
    for name, production in B.REGISTRY.items():
        for t in tuple(production.arg_types) + (production.result_type,):
            for part in re.findall(r"[A-Za-z_]+", str(t)):
                if len(part) == 1 and part.isupper():
                    print(f"GATE FAILED: type variable {part} survives in "
                          f"{name}")
                    return 1

    # -- gate 4: no excluded name appears in any generated file ------------
    forbidden = forbidden_lexemes(admitted)
    findings = []
    for path in sorted(BLIND_PKG.glob("*.py")):
        for name in scan(path.read_text(), forbidden):
            findings.append((path.name, name))
    if findings:
        print(f"GATE FAILED: {len(findings)} excluded name(s) in the blind "
              f"package")
        for file_name, name in findings:
            print(f"  {file_name:14} {name}")
        return 1

    record = {
        "generated_by": "scripts/cora_level4_build_blind_runtime.py",
        "a01_artifact_sha256": actual,
        "source_runtime_sha256": sha((SRC / "meta_v21.py").read_bytes()),
        "K_L4_star": sorted(admitted),
        "production_count": len(admitted),
        "signatures": {n: (f"{' x '.join(str(t) for t in p.arg_types)} -> "
                           f"{p.result_type}")
                       for n, p in sorted(B.REGISTRY.items())},
        "terminal_types_exposed": sorted(terminals),
        "induced_types_exposed": induced,
        "definitions_projected": kept,
        "definitions_projected_count": len(kept),
        "prose_redactions": [r for group in redacted for r in group],
        "forbidden_lexemes_checked": len(forbidden),
        "files": {p.name: sha(p.read_bytes())
                  for p in sorted(BLIND_PKG.glob("*.py"))},
        "gates": ["production set == K_L4*", "signatures == frozen",
                  "no unbound type variable", "no excluded lexeme"],
        "note": ("Evaluator bodies are verbatim source segments of the frozen "
                 "runtime and the projected set is a dependency closure, so "
                 "no evaluator behaviour, search policy, terminal vocabulary, "
                 "slot learner, cost or budget was changed."),
    }
    (OUT / "level4_blind_runtime_manifest.json").write_text(
        json.dumps(record, indent=1))

    print(f"projected {len(kept)} definitions into {BLIND_PKG.name}/")
    print(f"terminal types exposed: {sorted(terminals)}")
    print(f"induced types exposed:  {induced}")
    print(f"forbidden lexemes checked: {len(forbidden)}, none present")
    for path in sorted(BLIND_PKG.glob("*.py")):
        print(f"  {path.name:14} sha256 {sha(path.read_bytes())[:16]}")
    print("\nALL GATES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
