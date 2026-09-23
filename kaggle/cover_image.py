#!/usr/bin/env python3
"""
Cover image for ARC Prize 2026 Paper Track submission.

Left panel:  Calibration lattice — hidden-test precision by parameter class
             (E4: relational 0.92 -> constant 0.09, monotone in the
              syntactic lattice with zero test access).
Right panel: Three-way triangulation — certified 0.95 vs uncertified 0.18
             vs relift weak-gate 0.00 precision on hidden tests.

All numbers from paper/DRAFT.md and RUN_HISTORY.md (R2 SEALED 2026-08-12).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from pathlib import Path

# ── Data (every number from DRAFT.md / RUN_HISTORY) ──────────────────

# E4 calibration lattice
lattice_labels = ["Relational", "Feature", "Induced-map", "Constant"]
lattice_values = [0.92, 0.75, 0.40, 0.09]

# Three-way triangulation: E1 certified, E1 uncertified, R2 weak-gate
gate_labels = [
    "Certified\n(full reinduction)",
    "Uncertified\n(train-perfect)",
    "Weak gate\n(relift LOO)",
]
gate_values = [0.953, 0.184, 0.00]
gate_annotations = ["40/42", "37/201", "0/40"]

# ── Colors (colorblind-safe, sequential blue for lattice,
#    categorical for gate comparison) ──────────────────────────────────

# Sequential blue ramp (light to dark) for lattice — monotone encoding
lattice_colors = ["#1b4f72", "#2874a6", "#5dade2", "#d4e6f1"]

# Gate comparison: green (certified), amber (uncertified), red (weak gate)
gate_colors = ["#1a7a3a", "#c27a1a", "#b03030"]

# ── Figure ────────────────────────────────────────────────────────────

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.8), gridspec_kw={"wspace": 0.35})
fig.patch.set_facecolor("white")
fig.subplots_adjust(top=0.82)

# ── Left panel: calibration lattice ──────────────────────────────────

bars1 = ax1.bar(
    lattice_labels,
    lattice_values,
    color=lattice_colors,
    width=0.6,
    edgecolor="white",
    linewidth=1.5,
    zorder=3,
)

# Direct labels above bars
for bar, val in zip(bars1, lattice_values):
    ax1.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 0.025,
        f"{val:.2f}",
        ha="center",
        va="bottom",
        fontsize=13,
        fontweight="bold",
        color="#1a1a1a",
    )

ax1.set_ylabel("Hidden-test precision", fontsize=12, color="#333333")
ax1.set_title(
    "Calibration Lattice (E4)\nParameter class predicts correctness",
    fontsize=13,
    fontweight="bold",
    color="#1a1a1a",
    pad=12,
)
ax1.set_ylim(0, 1.12)
ax1.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))
ax1.spines["top"].set_visible(False)
ax1.spines["right"].set_visible(False)
ax1.spines["left"].set_color("#cccccc")
ax1.spines["bottom"].set_color("#cccccc")
ax1.tick_params(colors="#555555", labelsize=10.5)
ax1.yaxis.grid(True, color="#e8e8e8", linewidth=0.8, zorder=0)
ax1.set_axisbelow(True)

# ── Right panel: three-way triangulation ─────────────────────────────

bars2 = ax2.bar(
    gate_labels,
    gate_values,
    color=gate_colors,
    width=0.55,
    edgecolor="white",
    linewidth=1.5,
    zorder=3,
)

# Direct labels — precision values above bars (or at baseline for 0.00)
for bar, val, ann in zip(bars2, gate_values, gate_annotations):
    y_pos = max(bar.get_height(), 0.01) + 0.025
    ax2.text(
        bar.get_x() + bar.get_width() / 2,
        y_pos,
        f"{val:.2f}",
        ha="center",
        va="bottom",
        fontsize=13,
        fontweight="bold",
        color="#1a1a1a",
    )
    # Fraction annotation below the precision value
    ax2.text(
        bar.get_x() + bar.get_width() / 2,
        y_pos + 0.075,
        f"({ann})",
        ha="center",
        va="bottom",
        fontsize=10,
        color="#666666",
    )

ax2.set_ylabel("Hidden-test precision", fontsize=12, color="#333333")
ax2.set_title(
    "Three-Way Triangulation\nOnly full reinduction separates rule from coincidence",
    fontsize=13,
    fontweight="bold",
    color="#1a1a1a",
    pad=12,
)
ax2.set_ylim(0, 1.22)
ax2.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)
ax2.spines["left"].set_color("#cccccc")
ax2.spines["bottom"].set_color("#cccccc")
ax2.tick_params(colors="#555555", labelsize=10.5)
ax2.yaxis.grid(True, color="#e8e8e8", linewidth=0.8, zorder=0)
ax2.set_axisbelow(True)

# ── Suptitle ─────────────────────────────────────────────────────────

fig.suptitle(
    "Procedure-Level Generalization Certificates for ARC",
    fontsize=15,
    fontweight="bold",
    color="#0a0a0a",
    y=0.96,
)

# ── Save ─────────────────────────────────────────────────────────────

out_path = Path(__file__).parent / "cover_image.png"
fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white", pad_inches=0.3)
plt.close(fig)
print(f"Saved: {out_path}  ({out_path.stat().st_size / 1024:.0f} KB)")
