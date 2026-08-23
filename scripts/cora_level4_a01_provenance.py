"""Level-4 A0.1: provenance and semantic-evidence closure for the baseline.

A0 answered one of the three questions a claimed baseline capability must
answer, and answered it well: can the frozen search reach it? It left the
other two mostly asserted.

    defined before Level 4?   asserted from a hand-written table, then
                              "verified" with the hash of the CURRENT
                              meta_v21.py, which Level 4 had already edited,
                              so the check could not fail and proved nothing
    behaves correctly?        four fixtures existed, none of them covering an
                              admitted production; the rest were admitted with
                              synthetic_semantics_pass = None, which was read
                              as evidence when it is the absence of it
    reachable?                genuinely tested; consumed here unchanged

This stage closes the first two and changes NOTHING else. No evaluator, no
signature, no terminal vocabulary, no slot learner, no search parameter is
touched, and reachability is read from the A0 artifact rather than
recomputed, so A0.1 is strictly additive evidence.

The exact pre-Level-4 runtime was recovered. Both frozen pre-freeze
manifests pin its sha256, and a file with that hash survives, so provenance
is not an assertion here: the historical body of each evaluator is compared
against the current one, function by function. Authenticity is
content-addressed. It rests on the hash matching what two pre-Level-4
manifests pinned, never on where the copy was found.

Grades, frozen before the rows were computed:

    provenance   SOURCE_BODY_VERIFIED
                 PRE_LEVEL4_EXECUTION_HASH_PINNED
                 INTERNALLY_PRE_LEVEL4_NOT_HASH_VERIFIED
    semantics    CERTIFIED_PRE_LEVEL4_EXECUTION
                 PRE_LEVEL4_TEST
                 CURRENT_A0_SYNTHETIC_FIXTURE
                 NONE, which cannot pass

A body that diverges structurally from its historical form is excluded, not
repaired: the freeze forbids changing what the baseline denotes, so a
changed body is a changed baseline whatever its behaviour looks like now.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
CURRENT_RUNTIME = ROOT / "geocat_arc/object_reasoning/meta_v21.py"

#: Pinned by v21_level3_manifest.json and v21_promotion_manifest.json, both
#: written before the Level-4 freeze. The CURRENT runtime no longer hashes to
#: this, which is exactly why the current hash cannot serve as history.
PRE_LEVEL4_RUNTIME_SHA256 = (
    "57daa98455132b891625755a6228caa664f114d2b1d1c3b1a04c62ae3bfb5d89")
RECOVERED_RUNTIME = OUT / "level4_pre_level4_runtime_57daa984.py"

#: Secondary, version-controlled pre-Level-4 evidence: the prototype the V2.1
#: line grew out of, and the architecture tests that exercised it.
HISTORICAL_COMMIT = "5db9a3e"
HISTORICAL_PROTOTYPE = "geocat_arc/object_reasoning/meta_v2.py"
HISTORICAL_TESTS = ["tests/test_meta_v2_architecture.py"]

#: Artifacts written before the freeze, each traceable to a manifest that
#: pins the runtime hash above.
PRE_LEVEL4_RESULTS = {
    "v21_phase2_sources.json": "v21_level3_manifest.json",
    "v21_phase3_certificates.json": "v21_level3_manifest.json",
    "v21_level3_results.json": "v21_level3_manifest.json",
    "v21_promotion_results.json": "v21_promotion_manifest.json",
}


def sha(data) -> str:
    if isinstance(data, Path):
        data = data.read_bytes()
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def git(*args) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def load_historical_runtime():
    """Import the recovered pre-Level-4 runtime, refusing any other file.

    The hash is checked before the import, so a substituted or edited copy
    cannot be loaded and then reported as history.
    """
    if not RECOVERED_RUNTIME.exists():
        return None
    if sha(RECOVERED_RUNTIME) != PRE_LEVEL4_RUNTIME_SHA256:
        raise SystemExit("recovered runtime does not match the pinned hash")
    spec = importlib.util.spec_from_file_location(
        "meta_v21_pre_level4", RECOVERED_RUNTIME)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves field types through sys.modules, so the module
    # must be registered before its body runs
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def function_hashes(source: str, name: str) -> dict | None:
    """Text and structural hashes of one function definition.

    The structural hash is taken from the parsed body with the docstring
    dropped, so a reflowed line or an edited comment does not read as a
    semantic change, and a changed expression does.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = list(node.body)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                body = body[1:]
            segment = ast.get_source_segment(source, node) or ""
            return {"text_sha256": sha(segment)[:16],
                    "structural_sha256":
                        sha("\n".join(ast.dump(b) for b in body))[:16],
                    "lines": len(segment.splitlines())}
    return None


def module_definitions(source: str) -> dict:
    """Every top-level definition, function or assignment, by structure.

    Assignments matter as much as functions here. An evaluator body can be
    byte-identical while the vocabulary dictionary it looks a name up in has
    changed underneath it, which would leave the production's behaviour
    changed with an unchanged body hash.
    """
    definitions = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return definitions
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            definitions[node.name] = sha(ast.dump(node))[:16]
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = sha(ast.dump(node.value))[:16]
    return definitions


def dependency_closure(source: str, name: str) -> set:
    """Module-level definitions a function transitively depends on.

    Both calls and bare name loads count: a dictionary is read, not called.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    bodies = {node.name: node for node in tree.body
              if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    module_level = set(module_definitions(source))
    seen, pending = set(), [name]
    while pending:
        current = pending.pop()
        if current in seen or current not in bodies:
            seen.add(current)
            continue
        seen.add(current)
        for child in ast.walk(bodies[current]):
            if isinstance(child, ast.Name) and child.id in module_level:
                if child.id not in seen:
                    pending.append(child.id)
    return {n for n in seen if n in module_level and n != name}


# --------------------------------------------------------------------------
# generic behavioural fixtures
# --------------------------------------------------------------------------

RECT = frozenset({(1, 1), (1, 2), (2, 1), (2, 2)})      # area 4, rectangular
ELL = frozenset({(5, 5), (5, 6), (6, 5)})               # area 3, L-shaped
AREA_TO_COLOUR = ((4, 7), (3, 8))


def fixture_grid():
    """One background colour, a filled rectangle and a non-rectangle.

    Nothing here is an ARC task or resembles one. It is the smallest grid on
    which a segmentation, a predicate, an extremum, a contextual expression,
    a per-element map and a per-region paint can each be checked against a
    hand-computed answer.
    """
    grid = np.zeros((8, 8), int)
    for cell in sorted(RECT) + sorted(ELL):
        grid[cell] = 3
    return grid


def run_fixtures(module) -> dict:
    """Behaviour of one implementation, as plain checkable facts."""
    grid = fixture_grid()
    evaluators = module.EVALUATORS
    out = {}

    def call(name, *args, **context):
        fn = evaluators.get(name)
        return None if fn is None else fn(module.Ctx(grid, **context), *args)

    entities = call("Entities", "same_colour_4")
    out["Entities_segments_two_components"] = bool(
        entities is not None and
        {frozenset(e) for e in entities} == {RECT, ELL})

    regions = call("Partition", "colour_components")
    out["Partition_returns_disjoint_nonempty_sets"] = bool(
        regions and all(regions) and
        sum(len(r) for r in regions) ==
        len({cell for r in regions for cell in r}))

    out["Select_all_keeps_every_set"] = bool(
        entities and {frozenset(s) for s in call("Select", entities, "all")
                      or ()} == {RECT, ELL})
    out["Select_predicate_actually_filters"] = bool(
        entities and {frozenset(s) for s in
                      call("Select", entities, "rectangular") or ()} == {RECT})

    out["Unique_accepts_singleton"] = bool(
        frozenset(call("Unique", (tuple(sorted(RECT)),)) or ()) == RECT)
    out["Unique_rejects_two"] = call(
        "Unique", (tuple(sorted(RECT)), tuple(sorted(ELL)))) is None

    out["ArgMax_returns_the_maximum"] = bool(
        entities and frozenset(call("ArgMax", entities, "area") or ()) == RECT)
    out["ArgMin_returns_the_minimum"] = bool(
        entities and frozenset(call("ArgMin", entities, "area") or ()) == ELL)

    out["Key_reads_the_current_element"] = (
        call("Key", "area", element=tuple(sorted(RECT))) == 4)
    out["Lookup_maps_the_current_value"] = (
        call("Lookup", AREA_TO_COLOUR, value=4) == 7)

    # the two higher-order productions, in the module's own grammar
    compose = ("Compose_V1", (("Key", ("area",)), ("Lookup", (AREA_TO_COLOUR,))))
    out["Compose_V1_threads_key_into_lookup"] = (
        module._eval(compose, module.Ctx(grid, element=tuple(sorted(RECT))))
        == 7)

    mapped = module._eval(
        ("Map_V1", (("Partition", ("colour_components",)), compose)),
        module.Ctx(grid))
    table = dict(AREA_TO_COLOUR)
    out["Map_V1_applies_the_expression_per_region"] = bool(
        mapped and len(mapped) >= 2 and
        all(colour == table.get(len(cells)) for cells, colour in mapped))

    painted = call("PaintEach", ((tuple(sorted(RECT)), 7),))
    out["PaintEach_paints_each_region"] = bool(
        painted is not None and
        all(painted[cell] == 7 for cell in RECT) and painted[5, 5] == 3)
    return out


#: Which fixture bears on which production, so a pass is attributed rather
#: than assumed. A production with no fixture here has no fixture evidence
#: and must earn its evidence elsewhere or be excluded.
FIXTURE_OF = {
    "Entities": ["Entities_segments_two_components"],
    "Partition": ["Partition_returns_disjoint_nonempty_sets"],
    "Select": ["Select_all_keeps_every_set",
               "Select_predicate_actually_filters"],
    "Unique": ["Unique_accepts_singleton", "Unique_rejects_two"],
    "ArgMax": ["ArgMax_returns_the_maximum"],
    "ArgMin": ["ArgMin_returns_the_minimum"],
    "Key": ["Key_reads_the_current_element"],
    "Lookup": ["Lookup_maps_the_current_value"],
    "Compose_V1": ["Compose_V1_threads_key_into_lookup"],
    "Map_V1": ["Map_V1_applies_the_expression_per_region"],
    "PaintEach": ["PaintEach_paints_each_region"],
}


# --------------------------------------------------------------------------
# evidence gathering
# --------------------------------------------------------------------------

def executed_pre_level4(base: str) -> list:
    """Frozen pre-Level-4 artifacts containing this production in a program.

    Each artifact's governing manifest is checked to pin the historical
    runtime hash, so this is evidence about a runtime demonstrably not the
    current one.
    """
    citations = []
    for artifact, manifest_name in PRE_LEVEL4_RESULTS.items():
        artifact_path, manifest_path = OUT / artifact, OUT / manifest_name
        if not artifact_path.exists() or not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("hashes", {}).get("runtime") != PRE_LEVEL4_RUNTIME_SHA256:
            continue
        if f'"{base}"' not in artifact_path.read_text():
            continue
        citations.append({
            "artifact": artifact, "artifact_sha256": sha(artifact_path)[:16],
            "governing_manifest": manifest_name,
            "manifest_sha256": sha(manifest_path)[:16],
            "pinned_runtime_sha256": PRE_LEVEL4_RUNTIME_SHA256[:16]})
    return citations


def tested_pre_level4(base: str) -> list:
    """Version-controlled pre-Level-4 tests that name this production."""
    citations = []
    for path in HISTORICAL_TESTS:
        source = git("show", f"{HISTORICAL_COMMIT}:{path}")
        if source is None or f'"{base}"' not in source:
            continue
        citations.append({
            "test_file": path, "commit": HISTORICAL_COMMIT,
            "blob_sha": git("rev-parse", f"{HISTORICAL_COMMIT}:{path}"),
            "targets_module": "meta_v2, the prototype the V2.1 line grew from",
            "weight": ("secondary: it exercises a different module, so it "
                       "supports the semantics of the operation, not the "
                       "identity of the current body")})
    return citations


def provenance_of(base: str, historical_source: str | None,
                  current_source: str, citations: list) -> dict:
    """One graded provenance record. Never the current runtime hash."""
    current_function = V.EVALUATORS[base].__name__ if base in V.EVALUATORS \
        else None
    record = {
        "current_implementation_sha256": sha(current_source)[:16],
        "current_function": current_function,
        "current_function_hashes": function_hashes(current_source,
                                                   current_function)
        if current_function else None,
        "historical_artifact": (
            {"file": RECOVERED_RUNTIME.name,
             "sha256": PRE_LEVEL4_RUNTIME_SHA256[:16],
             "verified_against": ["v21_level3_manifest.json",
                                  "v21_promotion_manifest.json"]}
            if historical_source else None),
        "historical_function": current_function if historical_source else None,
        "historical_function_hashes": None,
        "dependency_closure": [],
        "dependency_divergences": {},
        "body_equivalence": "NOT_APPLICABLE",
        "pre_level4_execution": citations,
    }
    if historical_source and current_function:
        record["historical_function_hashes"] = function_hashes(
            historical_source, current_function)
        here_defs = module_definitions(current_source)
        there_defs = module_definitions(historical_source)
        closure = sorted(dependency_closure(current_source, current_function))
        record["dependency_closure"] = closure
        for dependency in closure:
            if dependency not in there_defs:
                record["dependency_divergences"][dependency] = "ADDED_BY_LEVEL4"
            elif here_defs.get(dependency) != there_defs[dependency]:
                record["dependency_divergences"][dependency] = "DIVERGENT"

    historical, current = (record["historical_function_hashes"],
                           record["current_function_hashes"])
    if historical and current:
        if historical["text_sha256"] == current["text_sha256"]:
            record["body_equivalence"] = "IDENTICAL_TEXT"
        elif historical["structural_sha256"] == current["structural_sha256"]:
            record["body_equivalence"] = "IDENTICAL_STRUCTURE"
        else:
            record["body_equivalence"] = "DIVERGENT_STRUCTURE"

    if historical:
        record["grade"] = "SOURCE_BODY_VERIFIED"
    elif citations:
        record["grade"] = "PRE_LEVEL4_EXECUTION_HASH_PINNED"
    else:
        record["grade"] = "INTERNALLY_PRE_LEVEL4_NOT_HASH_VERIFIED"
    return record


def signature_equivalence(base: str, historical) -> dict:
    """Would the PRE-LEVEL-4 signature compiler produce the same signature?

    A body comparison cannot see this. Signatures are compiled from the
    contract by ``parse_signature``, and that compiler WAS edited during
    Level 4 to stop the context-implicit leading-Grid rule from deleting a
    real argument, so a signature could move with no evaluator changing.

    Membership of the pre-Level-4 REGISTRY is deliberately NOT the test.
    That registry is the six-production Level-3A kernel, minimised on
    purpose, and the Level-4 manifest defines K_L4 to be broader precisely
    so that the mechanism cannot appear to invent a capability that was
    merely amputated for the earlier experiment. Excluding a production for
    being outside the minimised kernel would reintroduce that error. What
    must hold is that the pre-Level-4 compiler, reading the same frozen
    contract, yields the signature the Level-4 grounding instantiates.
    """
    rules = V._contract_rules(V.CONTRACT)
    form = rules.get(base, {}).get("form", "")

    def render(signature):
        return (f"{[str(a) for a in signature[0]]} -> {signature[1]}"
                if signature else None)

    record = {
        "contract_form": form,
        "in_pre_level4_registry": bool(
            historical is not None and base in historical.REGISTRY),
        "in_pre_level4_registry_note": (
            "informational only: that registry is the minimised Level-3A "
            "kernel, and K_L4 is broader by design"),
        "level4_groundings": sorted(
            f"{name}: {[str(a) for a in p.arg_types]} -> {p.result_type}"
            for name, p in V.LEVEL4_REGISTRY.items()
            if p.contract_grades.get("instantiated_from", name) == base),
        "current_compiler": None, "pre_level4_compiler": None, "match": None}

    try:
        record["current_compiler"] = render(V.parse_signature(form, base))
    except Exception as error:                        # noqa: BLE001
        record["current_compiler"] = f"ERROR: {error}"
    if historical is None:
        record["match"] = "NOT_COMPARED"
        return record
    try:
        record["pre_level4_compiler"] = render(historical.parse_signature(form))
    except Exception as error:                        # noqa: BLE001
        record["pre_level4_compiler"] = f"ERROR: {error}"
    record["match"] = record["current_compiler"] == record["pre_level4_compiler"]
    return record


def module_level_equivalence(current_source: str,
                             historical_source: str | None) -> dict:
    """Every pre-Level-4 top-level definition, and what became of it."""
    if historical_source is None:
        return {"compared": False}
    here, there = (module_definitions(current_source),
                   module_definitions(historical_source))
    identical = sorted(n for n, h in there.items() if here.get(n) == h)
    divergent = sorted(n for n, h in there.items()
                       if n in here and here[n] != h)
    missing = sorted(n for n in there if n not in here)
    return {"compared": True,
            "pre_level4_definitions": len(there),
            "identical": len(identical),
            "divergent": divergent,
            "removed_by_level4": missing,
            "added_by_level4": sorted(set(here) - set(there)),
            "note": ("A divergent or removed definition matters only where an "
                     "admitted production depends on it; per-production "
                     "dependency closures are recorded on each row, and the "
                     "compiled signature is compared separately because the "
                     "signature compiler is not in any evaluator's closure.")}


def semantic_evidence_of(base: str, fixtures: dict, citations: list,
                         tests: list) -> dict:
    """Independent of provenance: does the thing behave as claimed?"""
    relevant = FIXTURE_OF.get(base, [])
    results = {k: fixtures[k] for k in relevant if k in fixtures}
    kinds = []
    if results and all(results.values()):
        kinds.append("CURRENT_A0_SYNTHETIC_FIXTURE")
    if citations:
        kinds.append("CERTIFIED_PRE_LEVEL4_EXECUTION")
    if tests:
        kinds.append("PRE_LEVEL4_TEST")
    return {"kinds": kinds or ["NONE"], "fixtures": results,
            "fixture_failures": sorted(k for k, v in results.items() if not v),
            "pre_level4_tests": tests}


def cascade(rows):
    """A0's fixed point, re-run over the survivors."""
    changed = True
    while changed:
        changed = False
        live = {r["production"] for r in rows if r["admitted"]}
        available = set(V.TERMINAL_VALUES) | {
            k for k in V.INDUCED_TYPES if S.SLOT_LEARNERS.get(k)}
        available |= {str(V.LEVEL4_REGISTRY[n].result_type) for n in live}
        for row in rows:
            if not row["admitted"]:
                continue
            for arg in V.LEVEL4_REGISTRY[row["production"]].arg_types:
                if str(arg) not in available:
                    row["admitted"] = False
                    row["exclusion_reason"] = (
                        f"cascade: its argument {arg} is produced only by "
                        f"excluded productions")
                    changed = True
                    break
    return rows


def main():
    a0 = json.loads((OUT / "level4_baseline_admissibility.json").read_text())
    a0_rows = {r["production"]: r for r in a0["rows"]}

    historical = load_historical_runtime()
    historical_source = RECOVERED_RUNTIME.read_text() if historical else None
    current_source = CURRENT_RUNTIME.read_text()

    current_fixtures = run_fixtures(V)
    historical_fixtures = run_fixtures(historical) if historical else {}
    hunt = json.loads((OUT / "level4_runtime_hash_hunt.json").read_text()) \
        if (OUT / "level4_runtime_hash_hunt.json").exists() else None

    rows = []
    for name in a0["K_L4_star"]:
        base = V.LEVEL4_REGISTRY[name].contract_grades.get(
            "instantiated_from", name)
        citations = executed_pre_level4(base)
        tests = tested_pre_level4(base)
        provenance = provenance_of(base, historical_source, current_source,
                                   citations)
        semantics = semantic_evidence_of(base, current_fixtures, citations,
                                         tests)

        relevant = FIXTURE_OF.get(base, [])
        if historical and relevant:
            agree = all(current_fixtures.get(k) == historical_fixtures.get(k)
                        for k in relevant)
            behaviour = "EQUIVALENT_ON_FIXTURES" if agree else "DIVERGENT"
        else:
            behaviour = "NOT_COMPARED"

        divergent_helpers = sorted(provenance["dependency_divergences"])
        signature = signature_equivalence(base, historical)

        reasons = []
        if semantics["kinds"] == ["NONE"]:
            reasons.append("no semantic evidence of any kind")
        if semantics["fixture_failures"]:
            reasons.append("a synthetic fixture failed: " +
                           ", ".join(semantics["fixture_failures"]))
        if provenance["body_equivalence"] == "DIVERGENT_STRUCTURE":
            reasons.append("the current body diverges structurally from the "
                           "hash-verified pre-Level-4 body, so this is not "
                           "the baseline implementation")
        if divergent_helpers:
            reasons.append("something in its dependency closure changed since "
                           "the pre-Level-4 runtime: " +
                           ", ".join(divergent_helpers))
        if signature["match"] is False:
            reasons.append(
                "the pre-Level-4 signature compiler does not agree with the "
                f"current one: {signature['pre_level4_compiler']} became "
                f"{signature['current_compiler']}")
        if behaviour == "DIVERGENT":
            reasons.append("the current implementation disagrees with the "
                           "pre-Level-4 implementation on the fixtures")
        if not a0_rows[name]["search_reachable"]:
            reasons.append("A0: the frozen search cannot construct a term "
                           "using it")

        rows.append({
            "production": name, "base": base, "provenance": provenance,
            "signature_equivalence": signature,
            "semantic_evidence": semantics,
            "historical_behaviour": behaviour,
            "reachability": {
                "search_reachable": a0_rows[name]["search_reachable"],
                "argument_sources": a0_rows[name]["argument_sources"],
                "source": "A0 artifact, consumed not recomputed"},
            "admitted": not reasons,
            "exclusion_reason": "; ".join(reasons) or None})
        print(f"{name:16} {provenance['grade']:24} "
              f"sig={str(signature['match']):5} "
              f"body={provenance['body_equivalence']:20} "
              f"{'+'.join(semantics['kinds']):70} admitted={not reasons}",
              flush=True)

    rows = cascade(rows)
    admitted = sorted(r["production"] for r in rows if r["admitted"])
    excluded = sorted(r["production"] for r in rows if not r["admitted"])

    report = {
        "gate": "Level-4 A0.1 provenance and semantic-evidence closure",
        "supersedes": {
            "artifact": "level4_baseline_admissibility.json",
            "sha256": sha(OUT / "level4_baseline_admissibility.json")[:16]},
        "what_changed": (
            "A0 recorded the CURRENT meta_v21.py hash as every production's "
            "historical provenance, a check that could not fail, and admitted "
            "productions whose synthetic_semantics_pass was None. A0.1 "
            "replaces both with graded evidence against the recovered "
            "pre-Level-4 runtime. No evaluator, signature, vocabulary, "
            "learner or search parameter was changed, and reachability was "
            "consumed from A0 rather than recomputed."),
        "pre_level4_runtime_sha256": PRE_LEVEL4_RUNTIME_SHA256,
        "current_runtime_sha256": sha(CURRENT_RUNTIME),
        "current_runtime_differs_from_pinned":
            sha(CURRENT_RUNTIME) != PRE_LEVEL4_RUNTIME_SHA256,
        "historical_source_recovery": hunt,
        "secondary_historical_artifact": {
            "commit": HISTORICAL_COMMIT, "path": HISTORICAL_PROTOTYPE,
            "blob_sha": git("rev-parse",
                            f"{HISTORICAL_COMMIT}:{HISTORICAL_PROTOTYPE}"),
            "commit_date": git("log", "-1", "--format=%ad", "--date=iso",
                               HISTORICAL_COMMIT)},
        "module_level_equivalence": module_level_equivalence(
            current_source, historical_source),
        "fixtures_current_runtime": current_fixtures,
        "fixtures_pre_level4_runtime": historical_fixtures,
        "rows": rows,
        "K_L4_star": admitted,
        "excluded_at_a01": excluded,
        "E_L4_star": admitted + ["concept_0001"],
        "interpretation": (
            "A capability counts as part of the operational baseline only "
            "with hash-graded pre-Level-4 provenance, semantic evidence that "
            "is not the absence of evidence, and A0 reachability. Where any "
            "of the three could not be established the production is "
            "excluded and the reason recorded, never repaired."),
    }
    (OUT / "level4_baseline_admissibility_v2.json").write_text(
        json.dumps(report, indent=1, default=str))

    print(f"\ncurrent runtime {report['current_runtime_sha256'][:16]} != "
          f"pinned {PRE_LEVEL4_RUNTIME_SHA256[:16]}: "
          f"{report['current_runtime_differs_from_pinned']}")
    print(f"fixtures current:      {json.dumps(current_fixtures)}")
    print(f"fixtures pre-Level-4:  {json.dumps(historical_fixtures)}")
    print(f"\nK_L4* ({len(admitted)}): {admitted}")
    print(f"excluded at A0.1 ({len(excluded)}): {excluded}")
    print(f"E_L4* = K_L4* + concept_0001")
    return 0


if __name__ == "__main__":
    sys.exit(main())
