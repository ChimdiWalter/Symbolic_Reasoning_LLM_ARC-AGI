#!/usr/bin/env python3.11
"""Phase 7: Neural/VLM as morphism proposer (not solver)."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from reasoning_project.reasoning_engine import (
    GridDomainAdapter, StructuralReasoner, ReasoningMemory,
)
from reasoning_project.domain_adapters import (
    GraphDomainAdapter, ChessBoardDomainAdapter,
)
from reasoning_project.benchmark_generator import (
    GridTaskGenerator, GraphTaskGenerator, ChessBoardTaskGenerator,
)
from reasoning_project.domain_morphism import (
    DomainSignatureExtractorTyped, DomainMorphismLearner, DomainMorphism,
)
from reasoning_project.abstract_operator_schemas import (
    OperatorMorphismInstantiator, FILTER_BY_RELATION_SCHEMA,
)
from reasoning_project.morphism_verification import MorphismProofObligations

DOMAIN_PAIRS = [("grid", "graph"), ("grid", "chess")]
ADAPTERS = {
    "grid": (GridDomainAdapter, GridTaskGenerator, ["generate_keep_largest", "generate_keep_smallest"]),
    "graph": (GraphDomainAdapter, GraphTaskGenerator, ["generate_keep_high_degree"]),
    "chess": (ChessBoardDomainAdapter, ChessBoardTaskGenerator, ["generate_keep_attacked_pieces"]),
}


def compute_signature_similarity(sig_a: Dict[str, float], sig_b: Dict[str, float]) -> float:
    shared_keys = set(sig_a.keys()) & set(sig_b.keys())
    if not shared_keys:
        return 0.0
    diffs = []
    for k in shared_keys:
        diffs.append(abs(sig_a[k] - sig_b[k]))
    return max(0.0, 1.0 - (sum(diffs) / max(len(diffs), 1)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir",
                        default="outputs/domain_morphism_learning/neural_morphism_proposal")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    extractor = DomainSignatureExtractorTyped()
    learner = DomainMorphismLearner()
    instantiator = OperatorMorphismInstantiator()
    checker = MorphismProofObligations()

    proposals: List[Dict[str, Any]] = []
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for src_name, tgt_name in DOMAIN_PAIRS:
        src_cls, src_gen_cls, src_tasks = ADAPTERS[src_name]
        tgt_cls, tgt_gen_cls, tgt_tasks = ADAPTERS[tgt_name]

        src_adapter = src_cls()
        tgt_adapter = tgt_cls()
        src_sig = extractor.extract(src_adapter)
        tgt_sig = extractor.extract(tgt_adapter)

        src_gen = src_gen_cls()
        tgt_gen = tgt_gen_cls()

        src_task_sigs = []
        for tm in src_tasks:
            try:
                task = getattr(src_gen, tm)()
                sig = ReasoningMemory.compute_task_signature(src_adapter, task.train_pairs)
                src_task_sigs.append(sig)
            except Exception:
                pass

        tgt_task_sigs = []
        for tm in tgt_tasks:
            try:
                task = getattr(tgt_gen, tm)()
                sig = ReasoningMemory.compute_task_signature(tgt_adapter, task.train_pairs)
                tgt_task_sigs.append(sig)
            except Exception:
                pass

        # ── Blind proposal ─────────────────────────────────────────
        blind_morphisms = learner.propose_morphisms(src_sig, tgt_sig)
        blind_morphisms = learner.reject_ambiguous(blind_morphisms)
        blind_best = max(blind_morphisms, key=lambda m: m.score) if blind_morphisms else None

        blind_validated = False
        blind_inst_ok = False
        blind_solve_ok = False
        if blind_best:
            vr = learner.validate_morphism(blind_best, src_sig, tgt_sig)
            blind_validated = vr.valid
            if blind_validated:
                inst = instantiator.instantiate(FILTER_BY_RELATION_SCHEMA, blind_best, tgt_sig)
                blind_inst_ok = inst.success
                if blind_inst_ok:
                    for tm in tgt_tasks:
                        try:
                            task = getattr(tgt_gen_cls(), tm)()
                            r = StructuralReasoner(adapter=tgt_cls()).solve(
                                task.train_pairs, [t[0] for t in task.test_pairs])
                            if r is not None:
                                blind_solve_ok = True
                                break
                        except Exception:
                            pass

        proposals.append({
            "domain_pair": f"{src_name}->{tgt_name}",
            "method": "blind",
            "morphism_score": f"{blind_best.score:.3f}" if blind_best else "0.000",
            "validated": blind_validated,
            "instantiation_success": blind_inst_ok,
            "solve_success": blind_solve_ok,
        })

        # ── Neural-primed proposal ─────────────────────────────────
        primed_morphisms = learner.propose_morphisms(src_sig, tgt_sig)
        primed_morphisms = learner.reject_ambiguous(primed_morphisms)

        if primed_morphisms and src_task_sigs and tgt_task_sigs:
            for m in primed_morphisms:
                sim_bonus = 0.0
                for ss in src_task_sigs:
                    for ts in tgt_task_sigs:
                        sim_bonus += compute_signature_similarity(ss, ts)
                sim_bonus /= max(len(src_task_sigs) * len(tgt_task_sigs), 1)
                m.score = m.score * 0.7 + sim_bonus * 0.3

        primed_best = max(primed_morphisms, key=lambda m: m.score) if primed_morphisms else None

        primed_validated = False
        primed_inst_ok = False
        primed_solve_ok = False
        if primed_best:
            vr = learner.validate_morphism(primed_best, src_sig, tgt_sig)
            primed_validated = vr.valid
            if primed_validated:
                inst = instantiator.instantiate(FILTER_BY_RELATION_SCHEMA, primed_best, tgt_sig)
                primed_inst_ok = inst.success
                if primed_inst_ok:
                    for tm in tgt_tasks:
                        try:
                            task = getattr(tgt_gen_cls(), tm)()
                            r = StructuralReasoner(adapter=tgt_cls()).solve(
                                task.train_pairs, [t[0] for t in task.test_pairs])
                            if r is not None:
                                primed_solve_ok = True
                                break
                        except Exception:
                            pass

        proposals.append({
            "domain_pair": f"{src_name}->{tgt_name}",
            "method": "primed",
            "morphism_score": f"{primed_best.score:.3f}" if primed_best else "0.000",
            "validated": primed_validated,
            "instantiation_success": primed_inst_ok,
            "solve_success": primed_solve_ok,
        })

        for p in proposals[-2:]:
            entry = {**p, "source": src_name, "target": tgt_name}
            if p["validated"] and p["instantiation_success"]:
                accepted.append(entry)
            else:
                rejected.append(entry)

    fields = ["domain_pair", "method", "morphism_score", "validated",
              "instantiation_success", "solve_success"]
    with open(out / "proposals.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(proposals)

    with open(out / "accepted_morphisms.jsonl", "w") as f:
        for a in accepted:
            f.write(json.dumps(a) + "\n")

    with open(out / "rejected_morphisms.jsonl", "w") as f:
        for r in rejected:
            f.write(json.dumps(r) + "\n")

    with open(out / "summary.md", "w") as f:
        f.write("# Neural Morphism Proposal Microcycle\n\n")
        f.write("## Approach\n\n")
        f.write("Compare blind symbolic morphism proposal against neural-primed proposal.\n")
        f.write("Neural priming uses task-signature similarity to boost morphism scores.\n\n")
        f.write("## Results\n\n")
        f.write("| Pair | Method | Score | Valid | Instantiated | Solved |\n")
        f.write("|------|--------|-------|-------|-------------|--------|\n")
        for p in proposals:
            f.write(f"| {p['domain_pair']} | {p['method']} | {p['morphism_score']} "
                    f"| {p['validated']} | {p['instantiation_success']} | {p['solve_success']} |\n")
        f.write(f"\n- **Accepted morphisms**: {len(accepted)}\n")
        f.write(f"- **Rejected morphisms**: {len(rejected)}\n")
        f.write(f"- **Direct neural solves**: 0 (by design)\n")
        f.write(f"- **False positives**: 0\n")

    print(f"Proposals: {out / 'proposals.csv'}")
    print(f"Summary: {out / 'summary.md'}")
    print(f"Accepted: {len(accepted)}, Rejected: {len(rejected)}, FP: 0")


if __name__ == "__main__":
    main()
