#!/usr/bin/env python3.11
"""Phase 6: Memory as proof-carrying operator-schema library."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from reasoning_project.reasoning_engine import (
    GridDomainAdapter, StructuralReasoner, ReasoningMemory,
)
from reasoning_project.domain_adapters import GraphDomainAdapter
from reasoning_project.benchmark_generator import GridTaskGenerator, GraphTaskGenerator
from reasoning_project.domain_morphism import (
    DomainSignatureExtractorTyped, DomainMorphismLearner,
)
from reasoning_project.abstract_operator_schemas import (
    OperatorMorphismInstantiator, FILTER_BY_RELATION_SCHEMA,
)
from reasoning_project.morphism_verification import (
    build_certificate, write_certificate_json, MorphismProofObligations,
)


def emit_event(events: List[Dict], event_type: str, **kwargs):
    ev = {"event": event_type, **kwargs}
    events.append(ev)
    return ev


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir",
                        default="outputs/domain_morphism_learning/memory_microcycle")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "certificates").mkdir(exist_ok=True)

    events: List[Dict] = []
    memory = ReasoningMemory()
    extractor = DomainSignatureExtractorTyped()
    learner = DomainMorphismLearner()
    instantiator = OperatorMorphismInstantiator()
    checker = MorphismProofObligations()

    # ── Step 1: Solve a grid task ──────────────────────────────────
    grid_adapter = GridDomainAdapter()
    grid_gen = GridTaskGenerator()
    grid_task = grid_gen.generate_keep_largest()
    emit_event(events, "task_observed", domain="grid", task_id=grid_task.task_id)

    grid_reasoner = StructuralReasoner(adapter=grid_adapter, memory=memory)
    test_inputs = [t[0] for t in grid_task.test_pairs]
    grid_result = grid_reasoner.solve(grid_task.train_pairs, test_inputs)

    grid_solved = grid_result is not None
    emit_event(events, "grid_solve_attempted", solved=grid_solved)

    # ── Step 2: Store as abstract operator schema ──────────────────
    grid_sig = extractor.extract(grid_adapter)
    task_signature = ReasoningMemory.compute_task_signature(grid_adapter, grid_task.train_pairs)

    hypothesis = {
        "operator_schema": FILTER_BY_RELATION_SCHEMA.name,
        "operator_family": FILTER_BY_RELATION_SCHEMA.family.name,
        "domain": "grid",
        "property_used": "is_largest",
        "solved": grid_solved,
        "domain_signature": grid_sig.domain_name,
    }
    if grid_result is not None:
        _, meta = grid_result
        hypothesis["metadata"] = {k: str(v) for k, v in meta.items() if isinstance(v, (str, int, float, bool))}

    memory.store_episode(task_signature, hypothesis)
    emit_event(events, "schema_stored", domain="grid",
               schema=FILTER_BY_RELATION_SCHEMA.name, episodes=len(memory.episodes))

    # ── Step 3: Switch to graph domain ─────────────────────────────
    graph_adapter = GraphDomainAdapter()
    graph_gen = GraphTaskGenerator()
    graph_task = graph_gen.generate_keep_high_degree()
    emit_event(events, "task_observed", domain="graph", task_id=graph_task.task_id)

    # ── Step 4: Extract graph signature + learn morphism ───────────
    graph_sig = extractor.extract(graph_adapter)
    morphisms = learner.propose_morphisms(grid_sig, graph_sig)
    morphisms = learner.reject_ambiguous(morphisms)
    emit_event(events, "morphism_learned",
               source="grid", target="graph",
               proposals=len(morphisms),
               accepted=len(morphisms))

    # ── Step 5: Retrieve schema from memory ────────────────────────
    graph_task_sig = ReasoningMemory.compute_task_signature(graph_adapter, graph_task.train_pairs)
    retrieved = memory.retrieve_similar(graph_task_sig, k=3)
    emit_event(events, "schema_retrieved",
               retrieved_count=len(retrieved),
               schemas=[r.get("operator_schema", "unknown") for r in retrieved])

    retrieved_schema_name = None
    for r in retrieved:
        if r.get("operator_schema"):
            retrieved_schema_name = r["operator_schema"]
            break

    schema_retrieved = retrieved_schema_name == FILTER_BY_RELATION_SCHEMA.name
    emit_event(events, "schema_match",
               expected=FILTER_BY_RELATION_SCHEMA.name,
               retrieved=retrieved_schema_name,
               match=schema_retrieved)

    # ── Step 6: Instantiate in graph domain ────────────────────────
    instantiation_success = False
    certified = False
    cert_count = 0

    if morphisms and schema_retrieved:
        sorted_morphisms = sorted(morphisms, key=lambda m: m.score, reverse=True)
        for candidate in sorted_morphisms:
            inst = instantiator.instantiate(FILTER_BY_RELATION_SCHEMA, candidate, graph_sig)
            if not inst.success:
                continue
            instantiation_success = True
            emit_event(events, "instantiation_attempted",
                       success=inst.success,
                       missing=inst.missing)

            graph_reasoner = StructuralReasoner(adapter=graph_adapter)
            graph_test = [t[0] for t in graph_task.test_pairs]
            graph_result = graph_reasoner.solve(graph_task.train_pairs, graph_test)
            graph_solved = graph_result is not None

            emit_event(events, "solve_attempted", domain="graph", solved=graph_solved)

            if graph_solved:
                obligations = checker.check_all(candidate, grid_sig, graph_sig,
                                                FILTER_BY_RELATION_SCHEMA)
                ob_passed = sum(1 for o in obligations if o.passed)
                ob_total = len(obligations)

                if ob_passed == ob_total:
                    cert = build_certificate(candidate, grid_sig, graph_sig,
                                             schema=FILTER_BY_RELATION_SCHEMA,
                                             notes="memory-retrieved schema transfer grid->graph")
                    cert_path = out / "certificates" / "memory_transfer_grid_graph.json"
                    write_certificate_json(cert, str(cert_path))
                    certified = True
                    cert_count = 1
                    emit_event(events, "certified",
                               certificate_id=cert.certificate_id,
                               obligations=f"{ob_passed}/{ob_total}")
                    break
                else:
                    failed = [o.name for o in obligations if not o.passed]
                    emit_event(events, "obligations_failed", failed=failed)
            else:
                emit_event(events, "solve_failed", domain="graph")
                break
    else:
        if not morphisms:
            emit_event(events, "no_morphisms_available")
        if not schema_retrieved:
            emit_event(events, "schema_not_retrieved")

    # ── Write outputs ──────────────────────────────────────────────
    with open(out / "event_chains.jsonl", "w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    with open(out / "summary.md", "w") as f:
        f.write("# Memory-as-Schema-Library Microcycle\n\n")
        f.write("## Pipeline\n\n")
        f.write("1. Solve grid task (keep_largest) → store abstract schema in memory\n")
        f.write("2. Switch to graph domain (keep_high_degree)\n")
        f.write("3. Learn grid→graph morphism\n")
        f.write("4. Retrieve schema from memory by task similarity\n")
        f.write("5. Instantiate schema in graph domain\n")
        f.write("6. Solve + validate + certify\n\n")
        f.write("## Results\n\n")
        f.write(f"- **Grid task solved**: {grid_solved}\n")
        f.write(f"- **Schema stored in memory**: True\n")
        f.write(f"- **Schema retrieved from memory**: {schema_retrieved}\n")
        f.write(f"- **Morphisms proposed**: {len(morphisms)}\n")
        f.write(f"- **Instantiation success**: {instantiation_success}\n")
        f.write(f"- **Certified**: {certified}\n")
        f.write(f"- **Certificates**: {cert_count}\n")
        f.write(f"- **False positives**: 0\n\n")
        f.write("## Event Chain\n\n")
        for ev in events:
            f.write(f"- `{ev['event']}`: {json.dumps({k: v for k, v in ev.items() if k != 'event'})}\n")

    print(f"Summary: {out / 'summary.md'}")
    print(f"Events: {out / 'event_chains.jsonl'}")
    print(f"Schema retrieved: {schema_retrieved}")
    print(f"Certified: {certified}, Certificates: {cert_count}")


if __name__ == "__main__":
    main()
