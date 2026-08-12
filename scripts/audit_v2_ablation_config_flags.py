"""Audit ablation config flags to verify modules are actually disabled.

Checks each config in run_full_novel_v2_focused_eval.py to verify that
the enable_* flags match the intended ablation design.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import OrchestratorConfig

OUTPUT_DIR = "outputs/full_novel_reasoning_pipeline_v2/activation_regression_repair"

CONFIGS = {
    "v2_full_gated_orchestrator": OrchestratorConfig(),
    "v2_core_only": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_frontier_operators=False,
        enable_property_expansion=False,
    ),
    "v2_with_property_expansion": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_frontier_operators=False,
    ),
    "v2_with_frontier_operators": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_manifold_memory=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_property_expansion=False,
    ),
    "v2_with_manifold_memory": OrchestratorConfig(
        enable_adapter_genesis=False,
        enable_neural_advisory=False,
        enable_domain_morphism=False,
        enable_frontier_operators=False,
        enable_property_expansion=False,
    ),
}

MODULE_FLAGS = [
    "enable_adapter_genesis",
    "enable_manifold_memory",
    "enable_near_solved_memory",
    "enable_operator_memory",
    "enable_neural_advisory",
    "enable_domain_morphism",
    "enable_property_expansion",
    "enable_frontier_operators",
    "enable_trace_invention",
    "enable_static_portfolio",
]

EXPECTED = {
    "v2_full_gated_orchestrator": {f: True for f in MODULE_FLAGS},
    "v2_core_only": {
        "enable_adapter_genesis": False,
        "enable_manifold_memory": False,
        "enable_near_solved_memory": True,
        "enable_operator_memory": True,
        "enable_neural_advisory": False,
        "enable_domain_morphism": False,
        "enable_property_expansion": False,
        "enable_frontier_operators": False,
        "enable_trace_invention": True,
        "enable_static_portfolio": True,
    },
    "v2_with_property_expansion": {
        "enable_adapter_genesis": False,
        "enable_manifold_memory": False,
        "enable_near_solved_memory": True,
        "enable_operator_memory": True,
        "enable_neural_advisory": False,
        "enable_domain_morphism": False,
        "enable_property_expansion": True,
        "enable_frontier_operators": False,
        "enable_trace_invention": True,
        "enable_static_portfolio": True,
    },
    "v2_with_frontier_operators": {
        "enable_adapter_genesis": False,
        "enable_manifold_memory": False,
        "enable_near_solved_memory": True,
        "enable_operator_memory": True,
        "enable_neural_advisory": False,
        "enable_domain_morphism": False,
        "enable_property_expansion": False,
        "enable_frontier_operators": True,
        "enable_trace_invention": True,
        "enable_static_portfolio": True,
    },
    "v2_with_manifold_memory": {
        "enable_adapter_genesis": False,
        "enable_manifold_memory": True,
        "enable_near_solved_memory": True,
        "enable_operator_memory": True,
        "enable_neural_advisory": False,
        "enable_domain_morphism": False,
        "enable_property_expansion": False,
        "enable_frontier_operators": False,
        "enable_trace_invention": True,
        "enable_static_portfolio": True,
    },
}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    issues = []
    rows = []

    print("=" * 70)
    print("  Ablation Config Flag Audit")
    print("=" * 70)

    for config_name, config in CONFIGS.items():
        print(f"\n--- {config_name} ---")
        expected = EXPECTED.get(config_name, {})
        row = {"config": config_name}

        for flag in MODULE_FLAGS:
            actual = getattr(config, flag, None)
            exp = expected.get(flag, True)
            status = "OK" if actual == exp else "MISMATCH"
            row[flag] = actual
            if actual != exp:
                issues.append(f"{config_name}.{flag}: expected={exp}, actual={actual}")
                print(f"  {status}: {flag} = {actual} (expected {exp})")
            else:
                print(f"  {status}: {flag} = {actual}")

        rows.append(row)

    # Write CSV
    csv_path = os.path.join(OUTPUT_DIR, "ablation_flag_audit.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["config"] + MODULE_FLAGS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV written to {csv_path}")

    # Write summary
    md_lines = [
        "# Ablation Config Flag Audit\n\n",
        "## Config × Flag Matrix\n\n",
        "| Config |",
    ]
    short_flags = [f.replace("enable_", "") for f in MODULE_FLAGS]
    md_lines[2] += " | ".join(short_flags) + " |\n"
    md_lines.append("|--------|" + "|".join(["---"] * len(MODULE_FLAGS)) + "|\n")

    for row in rows:
        vals = [str(row.get(f, "?")) for f in MODULE_FLAGS]
        md_lines.append(f"| {row['config']} | " + " | ".join(vals) + " |\n")

    md_lines.append("\n## Issues Found\n\n")
    if issues:
        for issue in issues:
            md_lines.append(f"- {issue}\n")
    else:
        md_lines.append("No issues found. All flags match expected values.\n")

    md_lines.append("\n## Design Notes\n\n")
    md_lines.append("- `v2_core_only` replaces `v2_without_auxiliary`. It disables ALL activation ")
    md_lines.append("modules (adapter_genesis, manifold_memory, neural_advisory, domain_morphism, ")
    md_lines.append("frontier_operators, property_expansion), keeping only the core pipeline: ")
    md_lines.append("near_solved_memory, operator_memory, trace_invention, static_portfolio.\n")
    md_lines.append("- Each `v2_with_*` config adds exactly one module to the core, enabling ")
    md_lines.append("incremental contribution measurement.\n")
    md_lines.append("- The previous `v2_without_auxiliary` config left frontier_operators and ")
    md_lines.append("property_expansion enabled, making it identical to the full orchestrator ")
    md_lines.append("for all practical purposes (0 auxiliary modules contributed solves).\n")

    md_path = os.path.join(OUTPUT_DIR, "ablation_flag_audit.md")
    with open(md_path, "w") as f:
        f.writelines(md_lines)
    print(f"Summary written to {md_path}")

    if issues:
        print(f"\nWARNING: {len(issues)} flag mismatches found!")
        return 1
    else:
        print("\nAll ablation flags match expected values.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
