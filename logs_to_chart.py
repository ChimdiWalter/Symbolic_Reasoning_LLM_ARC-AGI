# log_to_charts.py
# Usage:
#   python3 log_to_charts.py build_curveball_verbose.log out_dir
# This script:
#   - Parses "=== exampleXX ===" sections
#   - Reads "Top families by L0 on train:" 5 lines that follow
#   - Reads "Chosen family: <tag>"
#   - Reads "target_shape: (H,W)"
#   - Emits charts into out_dir/

import sys, os, re, json
import matplotlib.pyplot as plt
from collections import defaultdict, Counter

TASK_HDR_RE = re.compile(r"^===\s+(example\d+)\s+===")
TARGET_RE   = re.compile(r"target_shape:\s*\((\d+),\s*(\d+)\)")
TOP_RE      = re.compile(r"^\s*L0=\s*([0-9]+)\s+([A-Z]+:[^ ]+)")
CHOSEN_RE   = re.compile(r"^Chosen family:\s+([A-Z]+:[^\s]+)")

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def parse_log(lines):
    tasks = []
    cur = None
    for ln in lines:
        m = TASK_HDR_RE.search(ln)
        if m:
            if cur: tasks.append(cur)
            cur = {"name": m.group(1), "target_shape": None,
                   "top": [], "chosen": None}
            continue
        if cur is None:
            continue
        m = TARGET_RE.search(ln)
        if m:
            cur["target_shape"] = (int(m.group(1)), int(m.group(2)))
            continue
        m = TOP_RE.search(ln)
        if m:
            L0 = int(m.group(1))
            fam = m.group(2)
            cur["top"].append((L0, fam))
            continue
        m = CHOSEN_RE.search(ln)
        if m:
            cur["chosen"] = m.group(1)
            continue
    if cur: tasks.append(cur)
    return tasks

def family_bucket(fam_full):
    # fam_full like "G:G:r0:f0:cropcenter" → "G"
    if not fam_full: return "?"
    return fam_full.split(":")[0]

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 log_to_charts.py <verbose.log> <out_dir>")
        sys.exit(1)
    log_path, out_dir = sys.argv[1], sys.argv[2]
    ensure_dir(out_dir)
    lines = open(log_path, "r", encoding="utf-8", errors="ignore").read().splitlines()
    tasks = parse_log(lines)

    # 1) Top-5 L0 bar chart per task
    for rec in tasks:
        name = rec["name"]
        top5 = rec["top"][:5]
        if not top5: 
            continue
        xs = [f for _,f in top5]
        ys = [L0 for L0,_ in top5]
        plt.figure()
        plt.bar(range(len(xs)), ys)
        plt.xticks(range(len(xs)), xs, rotation=30, ha="right", fontsize=8)
        plt.ylabel("L0 on train")
        plt.title(f"Top-5 families on train — {name}")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"{name}_top5.png"), dpi=160)
        plt.close()

    # 2) Pie: chosen family buckets
    cnt = Counter(family_bucket(rec["chosen"]) for rec in tasks if rec["chosen"])
    if cnt:
        labels = list(cnt.keys())
        sizes  = [cnt[k] for k in labels]
        plt.figure()
        plt.pie(sizes, labels=labels, autopct="%d")
        plt.title("Chosen family (count across tasks)")
        plt.savefig(os.path.join(out_dir, "chosen_family_pie.png"), dpi=160)
        plt.close()

    # 3) Histogram of target shapes (area)
    areas = []
    for rec in tasks:
        if rec["target_shape"]:
            H,W = rec["target_shape"]
            areas.append(H*W)
    if areas:
        plt.figure()
        plt.hist(areas, bins=min(20, max(3, len(areas)//2)))
        plt.xlabel("Target area H*W")
        plt.ylabel("Count")
        plt.title("Distribution of predicted target areas")
        plt.savefig(os.path.join(out_dir, "target_area_hist.png"), dpi=160)
        plt.close()

    # Also drop a JSON summary you can reference from slides
    open(os.path.join(out_dir, "summary.json"), "w").write(
        json.dumps(tasks, indent=2)
    )
    print(f"wrote charts + summary.json to {out_dir}")

if __name__ == "__main__":
    main()

