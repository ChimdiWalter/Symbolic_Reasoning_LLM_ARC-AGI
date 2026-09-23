"""Command line entry points."""

from __future__ import annotations

import argparse
from pathlib import Path

from .experiment import run_experiment
from .generators import generate_suite, save_suite
from .reporting import write_manuscript, write_reports
from .sweep import run_seed_sweep
from .utils import read_json


def generate_main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic reasoning benchmark.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config = read_json(args.config)
    suite = generate_suite(config)
    save_suite(suite, args.output)
    print(f"wrote {len(suite.tasks)} tasks to {args.output}")


def run_main() -> None:
    parser = argparse.ArgumentParser(description="Run a resumable reasoning experiment.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config = read_json(args.config)
    result = run_experiment(config, output_dir=args.output_dir, resume=args.resume)
    print(f"run_dir={result['run_dir']}")
    print(f"rows={len(result['rows'])}")


def analyze_main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate reports from an experiment run directory.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    rows = read_json(run_dir / "results.json")
    config = read_json(run_dir / "config.json")
    write_reports(run_dir, rows, config)
    write_manuscript(Path("paper"))
    print(f"analyzed {len(rows)} rows in {run_dir}")


def sweep_main() -> None:
    parser = argparse.ArgumentParser(description="Run an experiment config across repeated seeds.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--sweep-name", default=None)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    config = read_json(args.config)
    result = run_seed_sweep(
        config,
        seeds=args.seeds,
        output_dir=args.output_dir,
        sweep_name=args.sweep_name,
        resume=not args.no_resume,
    )
    print(f"sweep_dir={result['sweep_dir']}")
    print(f"seeds={','.join(str(seed) for seed in result['seeds'])}")
    print(f"seed_model_records={len(result['seed_model_records'])}")


if __name__ == "__main__":
    run_main()
