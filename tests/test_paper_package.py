from pathlib import Path

from reasoning_project.paper_package import build_submission_package
from reasoning_project.utils import write_json, write_text


def test_build_submission_package_writes_core_outputs(tmp_path: Path):
    root = tmp_path
    (root / "paper").mkdir()
    (root / "outputs" / "exactness").mkdir(parents=True)
    (root / "outputs" / "paper_breadth_validation_5seed_sweep").mkdir(parents=True)
    (root / "outputs" / "paper_breadth_validation_5seed_sweep" / "h4_bounded_alignment").mkdir(parents=True)
    (root / "outputs" / "h2_family_validation_10seed_sweep").mkdir(parents=True)
    (root / "outputs" / "arc_diagnostic_eval_6task_3seed").mkdir(parents=True)

    write_text(root / "paper" / "manuscript_draft.md", "# Draft\n")
    write_text(root / "paper" / "title_options.md", "# Titles\n")
    write_text(root / "paper" / "reproduce_paper_artifacts.md", "# Reproduce\n")
    write_text(root / "claim_traceability.md", "# Claims\n")
    write_text(root / "exactness_traceability.md", "# Exactness\n")
    write_text(root / "exact_vs_proxy_table.md", "# Exact vs Proxy\n")
    write_text(root / "results_summary.md", "# Results\n")
    write_text(root / "limitations.md", "# Limitations\n")
    write_text(root / "external_validity_summary.md", "# External\n")

    write_json(
        root / "outputs" / "exactness" / "exactness_report.json",
        {
            "description_length": {
                "domain": "tiny",
                "cases": {
                    "identity": {"minimum_code_length_units": 4},
                    "reflect_vertical": {"minimum_code_length_units": 20},
                },
            },
            "category": {
                "report": {
                    "identity_law_holds": True,
                    "associativity_holds": True,
                    "composition_well_defined_holds": True,
                    "closure_holds": True,
                }
            },
            "topology": {
                "classification_counts": {
                    "topology_preserving_under_support_mask_definition": 1,
                    "topology_preserving_for_component_and_hole_counts_only": 1,
                    "conditionally_topology_preserving_not_on_full_bounded_domain": 1,
                    "not_topology_preserving_on_bounded_domain": 1,
                }
            },
        },
    )
    write_json(root / "outputs" / "exactness" / "topology_operator_audit.json", [{"operator_signature": "identity"}])
    write_json(
        root / "outputs" / "paper_breadth_validation_5seed_sweep" / "sweep_summary.json",
        {
            "by_model": {
                "direct_io_proxy": {
                    "test_pair_accuracy_mean": 0.2,
                    "ood_pair_accuracy_mean": 0.1,
                    "latent_rule_recovered_mean": 0.0,
                    "recovery_after_corruption_mean": 0.0,
                },
                "transformation_library": {
                    "test_pair_accuracy_mean": 1.0,
                    "ood_pair_accuracy_mean": 1.0,
                    "latent_rule_recovered_mean": 0.8,
                    "recovery_after_corruption_mean": 0.0,
                },
                "compression_selector": {
                    "test_pair_accuracy_mean": 1.0,
                    "ood_pair_accuracy_mean": 1.0,
                    "latent_rule_recovered_mean": 0.85,
                    "recovery_after_corruption_mean": 0.0,
                },
                "path_repair": {
                    "test_pair_accuracy_mean": 1.0,
                    "ood_pair_accuracy_mean": 1.0,
                    "latent_rule_recovered_mean": 0.85,
                    "recovery_after_corruption_mean": 1.0,
                },
            }
        },
    )
    write_json(
        root / "outputs" / "paper_breadth_validation_5seed_sweep" / "paired_contrasts.json",
        {
            "transformation_library_minus_direct_io_proxy": {
                "test_pair_accuracy": {"mean_delta": 0.8},
                "ood_pair_accuracy": {"mean_delta": 0.9},
                "latent_rule_recovered": {"mean_delta": 0.8},
            },
            "path_repair_minus_compression_selector": {
                "test_pair_accuracy": {"mean_delta": 0.0},
                "ood_pair_accuracy": {"mean_delta": 0.0},
                "recovery_after_corruption": {"mean_delta": 1.0},
            },
            "integrated_scientist_minus_transformation_library": {
                "test_pair_accuracy": {"mean_delta": 0.0},
                "ood_pair_accuracy": {"mean_delta": 0.0},
                "latent_rule_recovered": {"mean_delta": 0.1},
                "recovery_after_corruption": {"mean_delta": 1.0},
                "runtime_seconds": {"mean_delta": 4.0},
                "oracle_probes_used": {"mean_delta": 10.0},
                "passive_checks_used": {"mean_delta": 20.0},
            },
        },
    )
    write_text(
        root / "outputs" / "paper_breadth_validation_5seed_sweep" / "seed_model_metrics.csv",
        "model_name,test_pair_accuracy\nx,1.0\n",
    )
    write_json(
        root / "outputs" / "paper_breadth_validation_5seed_sweep" / "h4_bounded_alignment" / "h4_sweep_summary.json",
        {
            "by_model": {
                "compression_selector": {
                    "selected_is_exact_min_rate": 1.0,
                    "mean_selected_minus_exact_min_units": 0.0,
                    "mean_causal_factor_recovery": 0.8,
                },
                "transformation_library": {
                    "selected_is_exact_min_rate": 1.0,
                    "mean_selected_minus_exact_min_units": 0.0,
                    "mean_causal_factor_recovery": 0.8,
                },
            }
        },
    )
    write_json(
        root / "outputs" / "paper_breadth_validation_5seed_sweep" / "h4_bounded_alignment" / "per_task_exact_mdl.json",
        [
            {
                "seed": 2030,
                "family": "paper_composition_reflect_count",
                "model_name": "compression_selector",
                "task_id": "task_a",
                "selected_is_exact_bounded_minimum": 1.0,
                "exact_min_program_signatures": "count_objects_emit_bar(color=1)",
                "selected_program": "count_objects_emit_bar(color=1)",
                "selected_minus_exact_min_units": 0.0,
                "true_program": "reflect_vertical -> count_objects_emit_bar(color=1)",
            },
            {
                "seed": 2030,
                "family": "paper_causal_spurious_largest",
                "model_name": "transformation_library",
                "task_id": "task_b",
                "selected_is_exact_bounded_minimum": 1.0,
                "exact_min_program_signatures": "keep_adjacent_to_color(target_color=1)",
                "selected_program": "keep_adjacent_to_color(target_color=1)",
                "selected_minus_exact_min_units": 0.0,
                "true_program": "select_by_relational_predicate(predicate=largest)",
            },
            {
                "seed": 2030,
                "family": "paper_causal_spurious_largest",
                "model_name": "integrated_scientist",
                "task_id": "task_b",
                "selected_is_exact_bounded_minimum": 0.0,
                "exact_min_program_signatures": "keep_adjacent_to_color(target_color=1)",
                "selected_program": "select_by_relational_predicate(predicate=largest)",
                "selected_minus_exact_min_units": 6.0,
                "true_program": "select_by_relational_predicate(predicate=largest)",
            }
        ],
    )
    write_json(
        root / "outputs" / "h2_family_validation_10seed_sweep" / "family_balanced_h2_analysis.json",
        {
            "summaries": {
                "h2_families_false_rule_accepted": {
                    "families": [
                        {"family": "h2_a", "mean_delta": -1.0, "win_rate": 1.0},
                        {"family": "h2_b", "mean_delta": 0.0, "win_rate": 0.0},
                    ]
                }
            }
        },
    )
    write_json(
        root / "outputs" / "h2_family_validation_10seed_sweep" / "failure_taxonomy.json",
        {"failure_taxonomy": [{"mode": "scope_limit", "evidence": "bounded"}]},
    )
    write_json(
        root / "outputs" / "h2_family_validation_10seed_sweep" / "accepted_false_rule_examples.json",
        [
            {
                "seed": 1300,
                "family": "h2_noncommuting_composition_probe",
                "task_id": "task_h2",
                "true_program": "translate(dc=0,dr=1) -> count_objects_emit_bar(color=1)",
                "proposer_only_program": "count_objects_emit_bar(color=1)",
                "test_acc": 0.0,
                "ood_acc": 0.0,
            }
        ],
    )
    write_json(
        root / "outputs" / "arc_diagnostic_eval_6task_3seed" / "summary.json",
        {
            "by_model": {
                "direct_io_proxy": {
                    "candidate_program_count_mean": 0.0,
                    "candidates_scored_mean": 0.0,
                    "test_exact_task_accuracy_mean": 0.0,
                    "test_pixel_accuracy_mean": 0.4,
                    "runtime_seconds_mean": 0.0,
                },
                "transformation_library": {
                    "candidate_program_count_mean": 60.0,
                    "candidates_scored_mean": 60.0,
                    "test_exact_task_accuracy_mean": 0.0,
                    "test_pixel_accuracy_mean": 0.55,
                    "runtime_seconds_mean": 1.0,
                },
            }
        },
    )
    write_json(
        root / "outputs" / "arc_diagnostic_eval_6task_3seed" / "qualitative_failures.json",
        [
            {"model": "direct_io_proxy", "task": "arc_task_a", "shape_bucket": "small", "predicted_program": "None"},
            {"model": "transformation_library", "task": "arc_task_b", "shape_bucket": "medium", "predicted_program": "identity"},
        ],
    )

    result = build_submission_package(root)
    out = Path(result["output_dir"])
    assert (out / "artifact_manifest.json").stat().st_size > 0
    assert (out / "tables" / "table_h2_family_balanced.md").stat().st_size > 0
    assert (out / "tables" / "table_h2_accepted_false_rules.md").stat().st_size > 0
    assert (out / "tables" / "table_arc_qualitative_failures.md").stat().st_size > 0
    assert (out / "tables" / "table_exact_semantics_model_difference.md").stat().st_size > 0
    assert (out / "appendix" / "claim_traceability_appendix.md").stat().st_size > 0
    assert (out / "figures" / "fig_arc_external_validity.png").stat().st_size > 0
