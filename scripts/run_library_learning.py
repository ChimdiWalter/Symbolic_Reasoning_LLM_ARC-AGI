"""Mine library fragments from portfolio solutions and evaluate transfer."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reasoning_project.library_learning import (
    build_library,
    evaluate_library_transfer,
    apply_library_compression,
)


def extract_solutions_from_portfolio(per_task_path: Path) -> dict:
    """Extract program step sequences from portfolio per_task results."""
    with open(per_task_path) as f:
        per_task = json.load(f)

    solutions = {}
    for entry in per_task:
        if not entry.get("solved"):
            continue
        task_id = entry["task_id"]
        solver = entry.get("solver_used", "")

        if "program" in (entry.get("metadata") or {}):
            solutions[task_id] = entry["metadata"]["program"]
        elif solver == "local_rule":
            strategy = (entry.get("metadata") or {}).get("strategy", solver)
            solutions[task_id] = [f"local_rule:{strategy}"]
        elif solver == "rule_induction":
            strategy = (entry.get("metadata") or {}).get("strategy", solver)
            solutions[task_id] = [f"rule_induction:{strategy}"]

    return solutions


def extract_dsl_solutions_from_diagnostic(rows_path: Path) -> dict:
    """Extract DSL program sequences from arc diagnostic rows."""
    with open(rows_path) as f:
        rows = json.load(f)

    solutions = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = row.get("arc_task_id", "")
        model = row.get("model_name", "")
        exact = row.get("test_exact_task_accuracy", 0)
        program = row.get("predicted_program", "")

        if model == "transformation_library" and exact == 1.0 and program:
            if isinstance(program, str):
                if " -> " in program:
                    steps = [s.strip() for s in program.split(" -> ") if s.strip()]
                elif "," in program and "(" not in program:
                    steps = [s.strip() for s in program.split(",") if s.strip()]
                else:
                    steps = [program.strip()]
            elif isinstance(program, list):
                steps = [str(s) for s in program]
            else:
                continue
            if steps:
                solutions[task_id] = steps

    return solutions


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio-dir", required=True)
    parser.add_argument("--diagnostic-dir", default=None, help="Arc diagnostic with DSL rows.json")
    parser.add_argument("--output-dir", default="outputs/library_learning")
    parser.add_argument("--min-frequency", type=int, default=2)
    parser.add_argument("--held-out-fraction", type=float, default=0.3)
    args = parser.parse_args()

    portfolio_dir = Path(args.portfolio_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    solutions = {}

    per_task_path = portfolio_dir / "per_task.json"
    if per_task_path.exists():
        solutions.update(extract_solutions_from_portfolio(per_task_path))
        print(f"Extracted {len(solutions)} solutions from portfolio")

    if args.diagnostic_dir:
        rows_path = Path(args.diagnostic_dir) / "rows.json"
        if rows_path.exists():
            dsl_solutions = extract_dsl_solutions_from_diagnostic(rows_path)
            solutions.update(dsl_solutions)
            print(f"Added {len(dsl_solutions)} DSL solutions from diagnostic")

    print(f"Total: {len(solutions)} solved task programs")

    if len(solutions) < 4:
        print("Too few solutions to mine meaningful fragments")
        report = {"status": "insufficient_data", "n_solutions": len(solutions)}
        with open(output_dir / "library_report.json", "w") as f:
            json.dump(report, f, indent=2)
        return

    task_ids = sorted(solutions.keys())
    split = int(len(task_ids) * (1 - args.held_out_fraction))
    train_ids = task_ids[:split]
    held_out_ids = task_ids[split:]

    train_solutions = {tid: solutions[tid] for tid in train_ids}
    held_out_solutions = {tid: solutions[tid] for tid in held_out_ids}

    library = build_library(train_solutions, min_frequency=args.min_frequency)
    print(f"Library: {library.size} fragments")

    for frag in library.fragments[:10]:
        print(f"  {frag.name}: freq={frag.frequency}, gain={frag.compression_gain}")

    transfer_metrics = evaluate_library_transfer(library, held_out_solutions)
    print(f"Transfer: {transfer_metrics}")

    report = {
        "n_train_solutions": len(train_solutions),
        "n_held_out_solutions": len(held_out_solutions),
        "library_size": library.size,
        "fragments": [
            {"name": f.name, "steps": f.steps, "frequency": f.frequency,
             "compression_gain": f.compression_gain, "n_source_tasks": len(f.source_tasks)}
            for f in library.fragments
        ],
        "transfer_metrics": transfer_metrics,
    }
    with open(output_dir / "library_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote {output_dir / 'library_report.json'}")


if __name__ == "__main__":
    main()
