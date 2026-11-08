"""Write WORKED_EXAMPLE_t52073858_DEMOS.json: the four demonstration pairs of generated task t52073858 (world W1), for
Figure 3 of the ARC paper. It holds only the task id, the demonstrations (input and output grids) and the source
file's path and sha256. No query input, no other task and no answer is copied.

    python3 -I experiments/construction_at_scale_20261105/exports/make_demos_t52073858.py   (from the repository root)
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SRC = "experiments/construction_at_scale_20261105/runs/generated/W1/partitions/TASKS_SYSTEM.json"
TASK = "t52073858"
OUT = HERE / f"WORKED_EXAMPLE_{TASK}_DEMOS.json"


def main():
    raw = (REPO / SRC).read_bytes()
    task = json.loads(raw)[TASK]
    demos = [{"input": x, "output": y} for x, y in task["train"]]   # demonstrations only; "test_inputs" is not read
    out = {"task": TASK, "demonstrations": demos,
           "source": {"path": SRC, "sha256": hashlib.sha256(raw).hexdigest()}}
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(demos)} demonstrations of {TASK}; source sha256 {out['source']['sha256']}")


if __name__ == "__main__":
    main()
