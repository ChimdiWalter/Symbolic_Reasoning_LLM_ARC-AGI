# draw_pipeline.py
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

def add_box(ax, x, y, w, h, text):
    ax.add_patch(Rectangle((x, y), w, h, fill=False, linewidth=1.5))
    ax.text(x + w/2, y + h/2, text, ha='center', va='center', wrap=True, fontsize=10)

def add_arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='->', mutation_scale=12, linewidth=1.2))

def main():
    fig, ax = plt.subplots(figsize=(12,10))
    W, H = 2.9, 0.95
    x0 = 0.5
    Y = {"load": 8.5, "per_task": 7.0, "priors": 5.8, "shape": 4.6,
         "fam": 3.4, "score": 2.2, "pred": 1.0, "out": -0.2, "eval": -1.4, "curve": -2.6}

    add_box(ax, x0, Y["load"], W, H, "Load data\n• ARC-AGI train/ eval\n• Curve-Ball tasks")
    add_box(ax, x0, Y["per_task"], W, H, "For each task:\nparse train/test")
    add_arrow(ax, x0+W/2, Y["load"], x0+W/2, Y["per_task"]+H)

    add_box(ax, x0, Y["priors"], W, H, "Load priors\n• llm_hints.json\n• llm_programs.json\n• policy_weights.npz\n• bandit_state.json")
    add_arrow(ax, x0+W/2, Y["per_task"], x0+W/2, Y["priors"]+H)

    add_box(ax, x0, Y["shape"], W, H, "Predict target shape (H×W)\n• LLM rule or tiny LS\n• Snap to train sizes")
    add_arrow(ax, x0+W/2, Y["priors"], x0+W/2, Y["shape"]+H)

    xG, xC, xL = x0-3.3, x0, x0+3.3
    add_box(ax, xG, Y["fam"], W, H, "Global family (G)\n• rotate/flip\n• center/bbox crop\n• palette restrict")
    add_box(ax, xC, Y["fam"], W, H, "Components (C)\n• CC pack\n• outline/fill\n• projections")
    add_box(ax, xL, Y["fam"], W, H, "LLM programs (opt)\n• parse steps\n• rotate→crop→recolor")

    add_arrow(ax, x0+W/2, Y["shape"], xG+W/2, Y["fam"]+H)
    add_arrow(ax, x0+W/2, Y["shape"], xC+W/2, Y["fam"]+H)
    add_arrow(ax, x0+W/2, Y["shape"], xL+W/2, Y["fam"]+H)

    add_box(ax, x0, Y["score"], W, H, "Score on train (L0)\n• policy/bandit reorder\n• one-step refine")
    add_arrow(ax, xG+W/2, Y["fam"], x0+W/2-1.1, Y["score"]+H)
    add_arrow(ax, xC+W/2, Y["fam"], x0+W/2,     Y["score"]+H)
    add_arrow(ax, xL+W/2, Y["fam"], x0+W/2+1.1, Y["score"]+H)

    add_box(ax, x0, Y["pred"], W, H, "Predict test\n• enforce H×W\n• two attempts")
    add_arrow(ax, x0+W/2, Y["score"], x0+W/2, Y["pred"]+H)

    add_box(ax, x0, Y["out"], W, H, "Write submission_eval.json\n(task_id → attempts[])")
    add_arrow(ax, x0+W/2, Y["pred"], x0+W/2, Y["out"]+H)

    add_box(ax, x0-3.6, Y["eval"], W, H, "Local eval (optional)\n• exact tasks\n• pixel accuracy")
    add_arrow(ax, x0+W/2-0.8, Y["out"], x0-3.6+W/2, Y["eval"]+H)

    add_box(ax, x0+3.6, Y["eval"], W, H, "Curve-Ball packaging\n• build_curveball_predictions.py\n• make_curveball_submission.py")
    add_arrow(ax, x0+W/2+0.8, Y["out"], x0+3.6+W/2, Y["eval"]+H+0.9)

    ax.set_xlim(-4.5, 8.5); ax.set_ylim(-3.5, 9.8); ax.axis('off')
    fig.tight_layout()
    fig.savefig("pipeline_arc_agi.png", dpi=200)
    print("Saved pipeline_arc_agi.png")

if __name__ == "__main__":
    main()

