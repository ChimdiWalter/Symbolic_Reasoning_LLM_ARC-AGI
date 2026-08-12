# log_to_charts.py
import re, sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

PAT_TASK = re.compile(r"^===\s+(example\d+)\s+===")
PAT_TOP  = re.compile(r"^\s*L0=\s*([0-9]+)\s+(\S.*)$")
PAT_CHOSEN = re.compile(r"^\s*Chosen family:\s+(\S.*)$")

def main(log_path, outdir):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    tasks = []
    l0_min = []
    chosen = []
    cur = None
    mins = []
    with open(log_path) as f:
        for line in f:
            m = PAT_TASK.match(line)
            if m:
                if cur is not None and mins:
                    l0_min.append(min(mins)); mins=[]
                cur = m.group(1); tasks.append(cur); continue
            m = PAT_TOP.match(line)
            if m:
                mins.append(int(m.group(1))); continue
            m = PAT_CHOSEN.match(line)
            if m:
                chosen.append(m.group(1))
        if cur is not None and mins:
            l0_min.append(min(mins))
    # Chart 1: L0 minima per task (bar)
    plt.figure(figsize=(10,4))
    x = np.arange(len(l0_min))
    plt.bar(x, l0_min)
    plt.title("Best train L0 per task (lower is better)")
    plt.xlabel("task index"); plt.ylabel("best L0")
    plt.tight_layout(); plt.savefig(out/"best_l0_per_task.png", dpi=160); plt.close()
    # Chart 2: family choice histogram
    from collections import Counter
    fams = [c.split(":")[0] for c in chosen]  # e.g., 'G', 'C', 'OF', 'P', 'LLM_PROG'
    cnt = Counter(fams)
    labels, vals = zip(*sorted(cnt.items()))
    plt.figure(figsize=(6,4))
    plt.bar(np.arange(len(labels)), vals)
    plt.xticks(np.arange(len(labels)), labels)
    plt.title("Chosen family frequency")
    plt.tight_layout(); plt.savefig(out/"family_hist.png", dpi=160); plt.close()
    print("Wrote:", out/"best_l0_per_task.png", out/"family_hist.png")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
