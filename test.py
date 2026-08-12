# Visualize Curve-Ball tasks and your predictions, and export per-task PNGs
import json, os, glob, math
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Tuple, Dict, Any

# ---------- Config ----------
curveball_dir = "data/curveball"
submission_path = "submission_curveball.json"  # change if you used a different name
out_dir = Path("curveball_viz")
out_dir.mkdir(exist_ok=True, parents=True)

# ---------- Helpers ----------
def to_np(m):
    return np.array(m, dtype=int)

def load_task(path:str)->Dict[str,Any]:
    with open(path) as f:
        return json.load(f)

def show_grid(ax, A:np.ndarray, title:str):
    # Display a grid as an image with nearest-neighbor pixels, no axes.
    ax.imshow(A, interpolation="nearest")
    ax.set_title(title, fontsize=10)
    ax.axis("off")

def make_fig(rows:List[List[Tuple[str,np.ndarray]]], fig_title:str, savepath:Path=None):
    # rows: list of rows; each row = list of (title, array)
    nrows = len(rows)
    ncols = max(len(r) for r in rows) if rows else 1
    fig, axs = plt.subplots(nrows, ncols, figsize=(3*ncols, 3*nrows))
    if nrows==1 and ncols==1:
        axs = np.array([[axs]])
    elif nrows==1:
        axs = np.array([axs])
    elif ncols==1:
        axs = np.array([[a] for a in axs])
    fig.suptitle(fig_title, fontsize=12)
    for r,row in enumerate(rows):
        for c in range(ncols):
            ax = axs[r, c]
            if c < len(row):
                title, A = row[c]
                show_grid(ax, A, title)
            else:
                ax.axis("off")
    fig.tight_layout()
    if savepath:
        fig.savefig(savepath, bbox_inches="tight", dpi=160)
    plt.show()

# ---------- Load submission (predictions) ----------
submission = {}
if os.path.isfile(submission_path):
    with open(submission_path) as f:
        submission = json.load(f)
else:
    print(f"[WARN] Submission file not found at {submission_path}. Prediction panels will be blank.")

# ---------- Iterate curveball tasks ----------
task_files = sorted(glob.glob(os.path.join(curveball_dir, "example*.json")))
export_paths = []

for tpath in task_files:
    task_id = Path(tpath).stem  # e.g., example01
    task = load_task(tpath)
    trains = task.get("train", [])
    tests  = task.get("test",  [])
    
    # Build rows to visualize: First show training pairs (input -> output), then test input and predicted output
    rows = []
    # Training pairs
    for i, pair in enumerate(trains):
        xin = to_np(pair["input"])
        yout= to_np(pair["output"])
        rows.append([(f"train{ i+1 } input {xin.shape}", xin),
                     (f"train{ i+1 } output {yout.shape}", yout)])
    
    # Test + prediction
    pred_block = submission.get(task_id, [])
    # In ARC-AGI style, test has only inputs; in this curve-ball, test has 1 input (per spec).
    for j, ti in enumerate(tests):
        x = to_np(ti["input"])
        # Try to get a predicted output grid from submission JSON
        y_guess = None
        if isinstance(pred_block, list) and j < len(pred_block):
            rec = pred_block[j]
            # The curve-ball submission format replicates ARC format and expects "test":[{"input":..,"output":..}]
            # But our submission_curveball.json we created stores exactly that per task_id.
            # If your builder stored as {"attempt_1":..}, adjust here:
            if isinstance(rec, dict) and "output" in rec:
                y_guess = to_np(rec["output"])
        # Fallback if a different structure:
        if y_guess is None and isinstance(pred_block, dict) and "test" in pred_block:
            try:
                y_guess = to_np(pred_block["test"][j]["output"])
            except Exception:
                y_guess = None
        
        if y_guess is not None:
            rows.append([(f"test{ j+1 } input {x.shape}", x),
                         (f"prediction {y_guess.shape}", y_guess)])
        else:
            rows.append([(f"test{ j+1 } input {x.shape}", x),
                         (f"prediction (missing)", np.zeros((max(1,x.shape[0]), max(1,x.shape[1])), dtype=int))])
    
    savepath = out_dir / f"{task_id}.png"
    export_paths.append(str(savepath))
    make_fig(rows, fig_title=f"{task_id}", savepath=savepath)

# ---------- Summary file ----------
with open(out_dir / "README.txt", "w") as f:
    f.write("Curve-Ball visualization exported PNGs:\n")
    for p in export_paths:
        f.write(f"{p}\n")

print("Exported PNGs:")
for p in export_paths:
    print(p)
