"""Did sanitization remove hidden information, or did it remove semantics?

The blind runtime is meant to be a projection of the frozen baseline, not a
smaller language that merely looks similar. The way to tell the difference is
to run the already-frozen Level-3 source programs, unchanged, in both
environments and require identical behaviour on every demonstration grid of
their own tasks.

This is a direct interpreter-equivalence test, deliberately NOT a rediscovery
run. Rediscovery would put the blind environment in the experimental role it
is not yet allowed to occupy, and would also invite tuning. Equivalence
answers the only question being asked here: does C1's primitive substrate
still compute what it computed before?

Both P1 and P2 are executed, plus the concept C1 itself applied to its own
recorded arguments, so the macro path is covered and not only the kernel.

This script runs BEHIND the firewall: it reads task ids and the frozen source
programs. Its OUTPUT is a pass/fail record, and it is not an input to Step A.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_concept as C  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_env as E  # noqa: E402
from level4_blind_runtime import runtime as BV  # noqa: E402
from level4_blind_runtime import concept as BC  # noqa: E402
from level4_blind_runtime import env as BE  # noqa: E402

OUT = ROOT / "outputs" / "cora_breakthrough"
SOURCES = OUT / "v21_phase2_sources.json"
REGISTRY_FILE = OUT / "v21_concept_registry.json"


def from_json(module, node):
    """Rebuild an AST under a given runtime module."""
    if "lit" in node:
        return module._tuplify(json.loads(node["lit"]))
    return (node["op"], tuple(from_json(module, a) for a in node["args"]))


def load_concept(module, record):
    """Rebuild C1 as a macro under a given runtime module."""
    schema = from_json(module, record["schema"])
    slot_types = {k: module.parse_type_text(v) if hasattr(
        module, "parse_type_text") else _parse(module, v)
        for k, v in record["slot_types"].items()}
    return schema, slot_types


def _parse(module, text: str):
    """Minimal type parser, sufficient for the recorded slot types."""
    text = text.strip().replace("=>", ",")
    if "[" not in text:
        return module.T(text)
    head, rest = text.split("[", 1)
    parts, depth, current = [], 0, ""
    for ch in rest[:-1]:
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        current += ch
    if current:
        parts.append(current)
    return module.T(head.strip(), *[_parse(module, p) for p in parts])


def main():
    sources = json.loads(SOURCES.read_text())
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    registry = json.loads(REGISTRY_FILE.read_text())

    rows, failures = [], 0

    # -- kernel path: the two frozen source programs -----------------------
    for entry in sources:
        task_id = entry["task"]
        frozen = V.from_json(entry["ast"])
        blind = from_json(BV, entry["ast"])

        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in challenges[task_id]["train"]]
        pairs += [(np.array(p["input"]), None)
                  for p in challenges[task_id]["test"]]

        agree, checked, reproduced = True, 0, 0
        for grid_in, grid_out in pairs:
            a = V.evaluate(frozen, grid_in)
            b = BV.evaluate(blind, grid_in)
            checked += 1
            if (a is None) != (b is None):
                agree = False
            elif a is not None and not np.array_equal(a, b):
                agree = False
            if grid_out is not None and a is not None and \
                    np.array_equal(a, grid_out):
                reproduced += 1

        type_a = V.type_of(frozen)
        type_b = BV.type_of(blind)
        types_agree = str(type_a) == str(type_b)
        if not agree or not types_agree:
            failures += 1
        rows.append({
            "program": "P1" if entry is sources[0] else "P2",
            "grids_checked": checked,
            "outputs_identical": agree,
            "result_type_frozen": str(type_a),
            "result_type_blind": str(type_b),
            "result_types_identical": types_agree,
            "demonstrations_reproduced": reproduced,
            "pass": agree and types_agree})

    # -- macro path: C1 applied to its own recorded arguments --------------
    record = registry["concept_0001"]
    frozen_schema = V.from_json(record["schema"])
    blind_schema = from_json(BV, record["schema"])

    frozen_concept = C.Concept(
        name="concept_0001", schema=frozen_schema,
        slot_types={k: _parse(V, v) for k, v in record["slot_types"].items()},
        provenance=(), source_hashes=(),
        result_type=_parse(V, record["result_type"]), cost=record["cost"])
    blind_concept = BC.Concept(
        name="concept_0001", schema=blind_schema,
        slot_types={k: _parse(BV, v) for k, v in record["slot_types"].items()},
        provenance=(), source_hashes=(),
        result_type=_parse(BV, record["result_type"]), cost=record["cost"])

    frozen_env = E.BASE_ENV.with_concept(frozen_concept)
    blind_env = BE.LanguageEnv(base=dict(BV.REGISTRY),
                               label="K").with_concept(blind_concept)

    macro_rows = []
    for entry in sources:
        task_id = entry["task"]
        # recover the concept's arguments from the frozen source program
        frozen_program = V.from_json(entry["ast"])
        feature = frozen_program[1][0][1][1][1][0][1][0]
        table = frozen_program[1][0][1][1][1][1][1][0]
        surface = ("concept_0001", (feature, table))

        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in challenges[task_id]["train"]]
        agree, matched = True, 0
        for grid_in, grid_out in pairs:
            a = E.evaluate(surface, grid_in, frozen_env)
            b = BE.evaluate(surface, grid_in, blind_env)
            if (a is None) != (b is None):
                agree = False
            elif a is not None and not np.array_equal(a, b):
                agree = False
            if a is not None and np.array_equal(a, grid_out):
                matched += 1
        expanded_agree = json.dumps(
            E.to_json(E.expand(surface, frozen_env), frozen_env),
            sort_keys=True) == json.dumps(
            BE.to_json(BE.expand(surface, blind_env), blind_env),
            sort_keys=True)
        if not agree or not expanded_agree:
            failures += 1
        macro_rows.append({
            "applied_to": "P1 arguments" if entry is sources[0]
                          else "P2 arguments",
            "outputs_identical": agree,
            "elaboration_identical": expanded_agree,
            "demonstrations_reproduced": matched,
            "pass": agree and expanded_agree})

    report = {
        "gate": "Level-4 blind-environment interpreter equivalence",
        "question": ("does the sanitized environment compute what the frozen "
                     "baseline computed, on the already-frozen Level-3 source "
                     "programs"),
        "not_a_rediscovery_run": ("execution equivalence only; the blind "
                                  "environment is not placed in an "
                                  "experimental role and nothing is tuned"),
        "frozen_runtime_sha256": hashlib.sha256(
            (ROOT / "geocat_arc" / "object_reasoning"
             / "meta_v21.py").read_bytes()).hexdigest()[:16],
        "blind_runtime_sha256": hashlib.sha256(
            (ROOT / "level4_blind_runtime"
             / "runtime.py").read_bytes()).hexdigest()[:16],
        "kernel_path": rows,
        "macro_path": macro_rows,
        "failures": failures,
        "passed": failures == 0,
        "interpretation": ("Equivalence on these programs shows the "
                           "projection preserved the semantics C1 actually "
                           "rests on. It is not a claim that every excluded "
                           "capability was irrelevant, only that nothing the "
                           "certified Level-3 result depended on was removed."),
    }
    (OUT / "level4_blind_equivalence.json").write_text(
        json.dumps(report, indent=1))

    for row in rows:
        print(f"  {row['program']}  grids {row['grids_checked']:2}  "
              f"identical={row['outputs_identical']}  "
              f"type {row['result_type_blind']}  "
              f"reproduced {row['demonstrations_reproduced']}  "
              f"{'PASS' if row['pass'] else 'FAIL'}")
    for row in macro_rows:
        print(f"  C1 on {row['applied_to']:14} identical="
              f"{row['outputs_identical']}  elaboration="
              f"{row['elaboration_identical']}  reproduced "
              f"{row['demonstrations_reproduced']}  "
              f"{'PASS' if row['pass'] else 'FAIL'}")

    print(f"\n{'EQUIVALENCE PASSED' if failures == 0 else f'FAILED: {failures}'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
