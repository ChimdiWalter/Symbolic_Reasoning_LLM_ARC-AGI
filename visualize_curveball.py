# visualize_curveball.py
import json, os, argparse, glob
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

def to_np(x): return np.array(x, dtype=int)

def load_json(p):
    with open(p) as f: return json.load(f)

def show(ax, A, title):
    ax.imshow(A, interpolation="nearest")  # default colors (tool rule: no custom colors)
    ax.set_title(title, fontsize=9); ax.axis("off")

def fig_rows(rows, title, savepath):
    nrows = len(rows); ncols = max(len(r) for r in rows) if rows else 1
    fig, axs = plt.subplots(nrows, ncols, figsize=(3*ncols, 3*nrows))
    if nrows==1 and ncols==1: axs = np.array([[axs]])
    elif nrows==1:            axs = np.array([axs])
    elif ncols==1:            axs = np.array([[a] for a in axs])
    fig.suptitle(title, fontsize=12)
    for r,row in enumerate(rows):
        for c in range(ncols):
            ax = axs[r,c]
            if c < len(row): show(ax, row[c][1], row[c][0])
            else: ax.axis("off")
    fig.tight_layout()
    fig.savefig(savepath, bbox_inches="tight", dpi=160)
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--curveball_dir", required=True)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    sub = load_json(args.submission) if os.path.isfile(args.submission) else {}

    paths = sorted(glob.glob(os.path.join(args.curveball_dir, "example*.json")))
    exported=[]
    for p in paths:
        tid = Path(p).stem
        task = load_json(p)
        rows=[]
        for i,pr in enumerate(task.get("train", [])):
            xin = to_np(pr["input"]); yout = to_np(pr["output"])
            rows.append([(f"train{i+1} in {xin.shape}", xin), (f"train{i+1} out {yout.shape}", yout)])
        # test + prediction
        tests = task.get("test", [])
        block = sub.get(tid, {})
        # support both {"test":[{"input","output"}]} or a list already under task_id
        pred_list = []
        if isinstance(block, dict) and "test" in block: pred_list = block["test"]
        elif isinstance(block, list): pred_list = block

        for j,rec in enumerate(tests):
            xin = to_np(rec["input"])
            ypred = None
            if j < len(pred_list) and isinstance(pred_list[j], dict) and "output" in pred_list[j]:
                ypred = to_np(pred_list[j]["output"])
            rows.append([(f"test{j+1} in {xin.shape}", xin),
                         (f"prediction {ypred.shape if ypred is not None else '(missing)'}",
                          ypred if ypred is not None else np.zeros_like(xin))])
        sp = outdir / f"{tid}.png"
        fig_rows(rows, tid, sp); exported.append(sp)

    with open(outdir / "README.txt", "w") as f:
        for p in exported: f.write(str(p)+"\n")
    print("Exported:", *map(str,exported), sep="\n")

if __name__ == "__main__":
    main()
