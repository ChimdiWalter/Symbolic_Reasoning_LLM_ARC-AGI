#!/usr/bin/env python3.11
"""Generate publication figures for the manuscript.

Produces:
1. Solver growth trajectory (coverage vs. number of families)
2. Solver contribution bar chart
3. Consensus statistics
4. External baseline comparison bar chart
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("matplotlib not available — generating text summaries only")


def growth_trajectory():
    """Historical coverage as families were added."""
    data = [
        (3, 53, "DSL + local_rule + rule_induction"),
        (5, 56, "+ object_graph + cegis"),
        (7, 66, "+ crop_extract + color_solver"),
        (8, 68, "+ abstract_program"),
        (9, 85, "+ separator_decompose"),
        (10, 84, "+ fill_solver (−1 from routing fix)"),
        (11, "~100", "+ world_model (with DSL)"),
    ]

    if HAS_MPL:
        fig, ax = plt.subplots(figsize=(8, 5))
        xs = [d[0] for d in data[:-1]]
        ys = [d[1] for d in data[:-1]]
        ax.plot(xs, ys, "o-", color="#2563eb", linewidth=2, markersize=8)
        for x, y, label in data[:-1]:
            ax.annotate(f"{y}", (x, y), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=9)
        ax.set_xlabel("Number of Solver Families", fontsize=12)
        ax.set_ylabel("ARC Tasks Solved (no DSL)", fontsize=12)
        ax.set_title("Coverage Growth with Solver Additions", fontsize=13)
        ax.set_xlim(2, 11)
        ax.set_ylim(40, 100)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        outpath = REPO / "paper" / "fig_growth_trajectory.png"
        fig.savefig(outpath, dpi=150)
        print(f"Saved {outpath}")
        plt.close()

    print("\n=== Solver Growth Trajectory ===")
    for n_families, solved, desc in data:
        print(f"  {n_families:>2} families: {solved:>4} solved  {desc}")


def solver_contributions():
    """Bar chart of solver contributions."""
    nodsl = REPO / "outputs" / "portfolio_v10_full" / "summary.json"
    if not nodsl.exists():
        print("No portfolio summary found")
        return

    with open(nodsl) as f:
        d = json.load(f)

    contribs = d.get("solver_contributions", {})
    solvers = sorted(contribs, key=lambda s: -contribs[s])
    counts = [contribs[s] for s in solvers]

    if HAS_MPL:
        colors = ["#2563eb", "#059669", "#d97706", "#dc2626",
                  "#7c3aed", "#0891b2", "#be185d", "#65a30d"]
        fig, ax = plt.subplots(figsize=(10, 5))
        bars = ax.bar(range(len(solvers)), counts, color=colors[:len(solvers)])
        ax.set_xticks(range(len(solvers)))
        ax.set_xticklabels(solvers, rotation=30, ha="right", fontsize=10)
        ax.set_ylabel("Tasks Solved", fontsize=12)
        ax.set_title(f"Solver Family Contributions (ARC no-DSL, {d['solved']} total)", fontsize=13)
        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    str(count), ha="center", fontsize=10, fontweight="bold")
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        outpath = REPO / "paper" / "fig_solver_contributions.png"
        fig.savefig(outpath, dpi=150)
        print(f"Saved {outpath}")
        plt.close()

    print("\n=== Solver Contributions ===")
    for s, c in zip(solvers, counts):
        pct = c / d["solved"] * 100
        bar = "█" * int(pct / 2)
        print(f"  {s:<25} {c:>3} ({pct:>5.1f}%) {bar}")


def consensus_stats():
    """Consensus statistics from per_task.json."""
    per_task_path = REPO / "outputs" / "portfolio_v10_full" / "per_task.json"
    if not per_task_path.exists():
        print("No per_task.json found")
        return

    with open(per_task_path) as f:
        tasks = json.load(f)

    solved = [t for t in tasks if t.get("solved")]
    single = [t for t in solved if t.get("reranker", {}).get("n_proposers", 1) == 1]
    consensus = [t for t in solved if t.get("reranker", {}).get("n_proposers", 1) > 1
                 and t.get("reranker", {}).get("n_distinct", 1) == 1]
    tiebreak = [t for t in solved if t.get("reranker", {}).get("n_distinct", 1) > 1]

    print("\n=== Consensus Statistics ===")
    print(f"  Total solved: {len(solved)}")
    print(f"  Single proposer (unique solver): {len(single)} ({len(single)/len(solved)*100:.0f}%)")
    print(f"  Multi-proposer, full consensus:  {len(consensus)} ({len(consensus)/len(solved)*100:.0f}%)")
    print(f"  Multi-proposer, tiebreak needed: {len(tiebreak)} ({len(tiebreak)/len(solved)*100:.0f}%)")

    from collections import Counter
    dist = Counter(t.get("reranker", {}).get("n_proposers", 1) for t in solved)
    print(f"\n  Proposer distribution:")
    for k in sorted(dist):
        print(f"    {k} proposers: {dist[k]} tasks")

    if HAS_MPL:
        fig, ax = plt.subplots(figsize=(6, 6))
        sizes = [len(single), len(consensus), len(tiebreak)]
        labels = [f"Single proposer\n({len(single)})",
                  f"Multi, consensus\n({len(consensus)})",
                  f"Multi, tiebreak\n({len(tiebreak)})"]
        colors_pie = ["#93c5fd", "#34d399", "#fbbf24"]
        ax.pie(sizes, labels=labels, colors=colors_pie, autopct="%1.0f%%",
               startangle=90, textprops={"fontsize": 11})
        ax.set_title(f"Consensus Breakdown ({len(solved)} solved tasks)", fontsize=13)
        fig.tight_layout()
        outpath = REPO / "paper" / "fig_consensus.png"
        fig.savefig(outpath, dpi=150)
        print(f"  Saved {outpath}")
        plt.close()


def baseline_comparison():
    """External baseline comparison bar chart."""
    baselines = [
        ("DSL only", 31),
        ("GPT-4", 50),
        ("ARGA", 53),
        ("Ours\n(no DSL)", 84),
        ("GPT-4o", 90),
    ]

    if HAS_MPL:
        fig, ax = plt.subplots(figsize=(8, 5))
        names = [b[0] for b in baselines]
        values = [b[1] for b in baselines]
        colors_bar = ["#94a3b8", "#94a3b8", "#94a3b8", "#2563eb", "#94a3b8"]
        bars = ax.bar(range(len(baselines)), values, color=colors_bar, edgecolor="white", linewidth=0.5)
        ax.set_xticks(range(len(baselines)))
        ax.set_xticklabels(names, fontsize=11)
        ax.set_ylabel("ARC Tasks Solved (/1000)", fontsize=12)
        ax.set_title("External Baseline Comparison", fontsize=13)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    str(val), ha="center", fontsize=11, fontweight="bold")
        ax.set_ylim(0, 110)
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        outpath = REPO / "paper" / "fig_baseline_comparison.png"
        fig.savefig(outpath, dpi=150)
        print(f"\nSaved {outpath}")
        plt.close()


def main():
    growth_trajectory()
    solver_contributions()
    consensus_stats()
    baseline_comparison()
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
