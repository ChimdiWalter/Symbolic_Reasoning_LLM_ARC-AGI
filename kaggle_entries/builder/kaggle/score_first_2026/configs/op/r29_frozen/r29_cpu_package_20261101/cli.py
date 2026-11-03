"""Offline input-only CLI; no dataset paths, answer lookup or submission hooks."""
import argparse
import json
from pathlib import Path
from .api import candidates_with_report


def main():
    parser = argparse.ArgumentParser(description='CORA R29 full-fit plus genuine LOO CPU candidates')
    parser.add_argument('task_json', type=Path)
    parser.add_argument('--cpu-s', type=float, required=True)
    parser.add_argument('--wall-s', type=float, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    task = json.loads(args.task_json.read_text())
    predictions, report = candidates_with_report(task, args.cpu_s, args.wall_s)
    with args.output.open('x') as stream:
        json.dump({'predictions': predictions, 'report': report}, stream, indent=2, allow_nan=False)
        stream.write('\n')

if __name__ == '__main__':
    main()
