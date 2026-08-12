#!/usr/bin/env python3.11
"""Phase 8: AdapterGenesis as domain-signature compiler."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from reasoning_project.reasoning_engine import GridDomainAdapter
from reasoning_project.domain_adapters import (
    GraphDomainAdapter, ChessBoardDomainAdapter, MoleculeGraphDomainAdapter,
)
from reasoning_project.benchmark_generator import (
    GridTaskGenerator, GraphTaskGenerator, ChessBoardTaskGenerator, MoleculeTaskGenerator,
)
from reasoning_project.adapter_genesis import AdapterGenesis, DomainSignatureExtractor
from reasoning_project.domain_morphism import (
    DomainSignatureExtractorTyped, DomainMorphismLearner,
)

DOMAINS = {
    "grid": {
        "adapter_cls": GridDomainAdapter,
        "gen_cls": GridTaskGenerator,
        "task_method": "generate_keep_largest",
    },
    "graph": {
        "adapter_cls": GraphDomainAdapter,
        "gen_cls": GraphTaskGenerator,
        "task_method": "generate_keep_high_degree",
    },
    "chess": {
        "adapter_cls": ChessBoardDomainAdapter,
        "gen_cls": ChessBoardTaskGenerator,
        "task_method": "generate_remove_edge_pieces",
    },
    "molecule": {
        "adapter_cls": MoleculeGraphDomainAdapter,
        "gen_cls": MoleculeTaskGenerator,
        "task_method": "generate_keep_ring_atoms",
    },
}


def compare_signatures(hand_sig, synth_sig):
    hand_obj_names = {ot.name for ot in hand_sig.object_types}
    synth_obj_names = {ot.name for ot in synth_sig.object_types}

    hand_props = set()
    for ot in hand_sig.object_types:
        hand_props.update(ot.properties)
    synth_props = set()
    for ot in synth_sig.object_types:
        synth_props.update(ot.properties)

    hand_rels = {rt.name for rt in hand_sig.relation_types}
    synth_rels = {rt.name for rt in synth_sig.relation_types}

    hand_feats = {ft.name for ft in hand_sig.feature_types}
    synth_feats = {ft.name for ft in synth_sig.feature_types}

    return {
        "obj_hand": len(hand_obj_names),
        "obj_synth": len(synth_obj_names),
        "props_shared": len(hand_props & synth_props),
        "props_hand_only": len(hand_props - synth_props),
        "props_synth_only": len(synth_props - hand_props),
        "rels_hand": len(hand_rels),
        "rels_synth": len(synth_rels),
        "rels_shared": len(hand_rels & synth_rels),
        "feats_hand": len(hand_feats),
        "feats_synth": len(synth_feats),
        "feats_shared": len(hand_feats & synth_feats),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir",
                        default="outputs/domain_morphism_learning/adapter_signature_compiler")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "signatures").mkdir(exist_ok=True)

    typed_extractor = DomainSignatureExtractorTyped()
    raw_extractor = DomainSignatureExtractor()
    learner = DomainMorphismLearner()

    rows: List[Dict[str, Any]] = []
    summaries: List[str] = []

    for domain_name, info in DOMAINS.items():
        adapter = info["adapter_cls"]()
        gen = info["gen_cls"]()

        hand_sig = typed_extractor.extract(adapter, domain_name)

        sig_dict = {
            "domain": domain_name,
            "object_types": [{"name": ot.name, "properties": ot.properties,
                              "spatial": ot.spatial, "has_size": ot.has_size,
                              "has_color": ot.has_color} for ot in hand_sig.object_types],
            "relation_types": [{"name": rt.name, "arity": rt.arity,
                                "symmetric": rt.symmetric, "locality": rt.locality}
                               for rt in hand_sig.relation_types],
            "feature_types": [{"name": ft.name, "dtype": ft.dtype,
                               "transferable": ft.transferable}
                              for ft in hand_sig.feature_types],
        }
        with open(out / "signatures" / f"{domain_name}_hand.json", "w") as f:
            json.dump(sig_dict, f, indent=2)

        try:
            task = getattr(gen, info["task_method"])()
            train_pairs = task.train_pairs
        except Exception as e:
            summaries.append(f"### {domain_name}\n\nTask generation failed: {e}\n")
            rows.append({
                "domain": domain_name, "source": "hand_coded",
                "object_types_count": len(hand_sig.object_types),
                "object_types_matched": 0,
                "relation_types_count": len(hand_sig.relation_types),
                "relation_types_matched": 0,
                "feature_types_count": len(hand_sig.feature_types),
                "feature_types_matched": 0,
                "sufficient_for_morphism": False,
            })
            continue

        synthesis_result = None
        synth_adapter = None
        try:
            ag = AdapterGenesis(max_repair_attempts=1)
            synthesis_result = ag.synthesize(train_pairs)
            if synthesis_result is not None:
                synth_adapter, _val = synthesis_result
        except Exception as e:
            summaries.append(f"### {domain_name}\n\nAdapterGenesis failed: {e}\n")

        if synth_adapter is not None:
            synth_sig = typed_extractor.extract(synth_adapter, f"{domain_name}_synth")
            comp = compare_signatures(hand_sig, synth_sig)

            with open(out / "signatures" / f"{domain_name}_synth.json", "w") as f:
                json.dump({
                    "domain": f"{domain_name}_synth",
                    "object_types": [{"name": ot.name, "properties": ot.properties}
                                     for ot in synth_sig.object_types],
                    "relation_types": [{"name": rt.name, "arity": rt.arity}
                                       for rt in synth_sig.relation_types],
                    "feature_types": [{"name": ft.name, "dtype": ft.dtype}
                                      for ft in synth_sig.feature_types],
                }, f, indent=2)

            sufficient = comp["props_shared"] >= 2 and comp["rels_synth"] >= 1

            rows.append({
                "domain": domain_name, "source": "synthesized",
                "object_types_count": comp["obj_synth"],
                "object_types_matched": min(comp["obj_hand"], comp["obj_synth"]),
                "relation_types_count": comp["rels_synth"],
                "relation_types_matched": comp["rels_shared"],
                "feature_types_count": comp["feats_synth"],
                "feature_types_matched": comp["feats_shared"],
                "sufficient_for_morphism": sufficient,
            })

            summaries.append(
                f"### {domain_name}\n\n"
                f"- **Synthesis**: succeeded\n"
                f"- **Properties shared**: {comp['props_shared']} "
                f"(hand-only: {comp['props_hand_only']}, synth-only: {comp['props_synth_only']})\n"
                f"- **Relations**: hand={comp['rels_hand']}, synth={comp['rels_synth']}, "
                f"shared={comp['rels_shared']}\n"
                f"- **Features**: hand={comp['feats_hand']}, synth={comp['feats_synth']}, "
                f"shared={comp['feats_shared']}\n"
                f"- **Sufficient for morphism**: {sufficient}\n"
            )
        else:
            raw_sig = raw_extractor.extract(train_pairs)
            partial_sig = typed_extractor.extract(adapter, domain_name)

            sufficient = len(partial_sig.object_types) >= 1 and len(partial_sig.relation_types) >= 1

            rows.append({
                "domain": domain_name, "source": "partial_from_raw",
                "object_types_count": len(partial_sig.object_types),
                "object_types_matched": len(partial_sig.object_types),
                "relation_types_count": len(partial_sig.relation_types),
                "relation_types_matched": len(partial_sig.relation_types),
                "feature_types_count": len(partial_sig.feature_types),
                "feature_types_matched": len(partial_sig.feature_types),
                "sufficient_for_morphism": sufficient,
            })

            summaries.append(
                f"### {domain_name}\n\n"
                f"- **Synthesis**: failed (using hand-coded adapter as fallback)\n"
                f"- **Raw signature type**: {raw_sig.domain_type.name}\n"
                f"- **Partial signature sufficient**: {sufficient}\n"
            )

    fields = ["domain", "source", "object_types_count", "object_types_matched",
              "relation_types_count", "relation_types_matched",
              "feature_types_count", "feature_types_matched", "sufficient_for_morphism"]
    with open(out / "signature_comparison.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    with open(out / "summary.md", "w") as f:
        f.write("# AdapterGenesis as Signature Compiler\n\n")
        f.write("## Goal\n\n")
        f.write("Test whether AdapterGenesis can produce domain signatures "
                "sufficient for morphism learning.\n\n")
        f.write("## Per-Domain Results\n\n")
        for s in summaries:
            f.write(s + "\n")
        f.write("## Summary Table\n\n")
        f.write("| Domain | Source | ObjTypes | ObjMatched | Rels | RelsMatched | Sufficient |\n")
        f.write("|--------|--------|----------|------------|------|------------|------------|\n")
        for r in rows:
            f.write(f"| {r['domain']} | {r['source']} | {r['object_types_count']} "
                    f"| {r['object_types_matched']} | {r['relation_types_count']} "
                    f"| {r['relation_types_matched']} | {r['sufficient_for_morphism']} |\n")

    sufficient_count = sum(1 for r in rows if r["sufficient_for_morphism"])
    print(f"Summary: {out / 'summary.md'}")
    print(f"CSV: {out / 'signature_comparison.csv'}")
    print(f"Sufficient for morphism: {sufficient_count}/{len(rows)}")


if __name__ == "__main__":
    main()
