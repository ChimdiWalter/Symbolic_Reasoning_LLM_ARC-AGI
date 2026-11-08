#!/usr/bin/env python3
"""Grid panels for the figure "one observed failure, four interventions" (public evaluation puzzle 62593bfd).

Reads only recorded files and writes text-free vector grids; every label of the figure is set in main.tex.
  python3 -I paper/v2_neural_cora/figures/make_same_failure_grids.py      # from the repository root
Inputs (read only):
  outputs/score_first/data/arc-agi_evaluation_challenges.json   the puzzle's demonstrations and test inputs
  outputs/score_first/data/arc-agi_evaluation_solutions.json    used only to check that CORA's recorded answer is exact
  experiments/cora_cast_20261026/runs/chain_v2/m2/ARC_eval_dev/decisions.jsonl
      CORA-CAST's recorded decisions for the puzzle: the joint guarded-rewriting arm and its two controls
Outputs: sf_*.pdf (one grid each) and same_failure_record.json (the recorded facts the figure states).
Puzzle data: ARC Prize Foundation.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TASK = "62593bfd"
ARC_COLOURS = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
               "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
CELL_CM = 0.085          # every grid is drawn at the same cell size, so the panels keep their true proportions


def grid_pdf(grid, name):
    g = np.array(grid)
    h, w = g.shape
    fig = plt.figure(figsize=(w * CELL_CM / 2.54, h * CELL_CM / 2.54))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.pcolormesh(np.arange(w + 1), np.arange(h + 1), g[::-1], cmap=ListedColormap(ARC_COLOURS),
                  vmin=-0.5, vmax=9.5, edgecolors="#3a3a3a", linewidth=0.07)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_axis_off()
    fig.savefig(HERE / name, metadata={"CreationDate": None, "Creator": None, "Producer": None})
    plt.close(fig)


def main():
    data = REPO / "outputs" / "score_first" / "data"
    task = json.loads((data / "arc-agi_evaluation_challenges.json").read_text())[TASK]
    answers = json.loads((data / "arc-agi_evaluation_solutions.json").read_text())[TASK]
    rec = REPO / "experiments/cora_cast_20261026/runs/chain_v2/m2/ARC_eval_dev/decisions.jsonl"
    arms = {d["arm"]: d for d in map(json.loads, rec.read_text().splitlines()) if d["task_id"] == TASK}
    joint = arms["rewrite_joint"]
    exact = [joint["attempts"][q][0] == answers[q] for q in range(len(answers))]
    assert all(exact), "the recorded first attempt is not exact"
    grids = {"sf_demo1_in.pdf": task["train"][0]["input"], "sf_demo1_out.pdf": task["train"][0]["output"],
             "sf_demo2_in.pdf": task["train"][1]["input"], "sf_demo2_out.pdf": task["train"][1]["output"],
             "sf_test1_in.pdf": task["test"][0]["input"], "sf_test1_cora.pdf": joint["attempts"][0][0]}
    for name, g in grids.items():
        grid_pdf(g, name)
    background = {k: int(np.bincount(np.array(v).ravel()).argmax()) for k, v in grids.items()}
    facts = {"task": TASK, "record": str(rec.relative_to(REPO)),
             "arms": {a: {k: d[k] for k in ("status", "n_fits", "n_behaviours", "cpu_s")} for a, d in arms.items()},
             "program": joint["programs"][0], "first_attempt_exact_per_query": exact,
             "majority_colour": background, "shapes": {k: list(np.array(v).shape) for k, v in grids.items()}}
    (HERE / "same_failure_record.json").write_text(json.dumps(facts, indent=1) + "\n")
    print(json.dumps(facts["arms"]), facts["majority_colour"], exact)


if __name__ == "__main__":
    main()
