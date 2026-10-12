"""Figures for the ARC Prize Research Summit poster and the paper, drawn ONLY
from sealed outputs (no generated pictures).

  python scripts/summit_figures.py   -> docs/summit_poster/figures/*.png

Sources: outputs/reach_v1/measure_funnel.json (reach v1, frozen c8d8e3a),
records/ITEM2_V19_PROSPECTIVE_RESULT_20261007.md (v1.9 synthetic, 27 and 12 of
30), records/pilot_v1/dev_bundle.json (TRAINING demonstrations of one
development task; no test output exists in it), outputs/loo_v1/probe_*.json
(forensic probes) and outputs/loo_v1/probe_negative.json (synthetic negative
controls, when present). Palette: the dataviz reference palette (validated
blue/orange pair, neutral and status steps); ARC grids use the standard ARC
colours, which are the data itself.
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle     # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "docs", "summit_poster", "figures")
INK, INK2, MUTED, GRID, BASE, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE, ORANGE, NEUTRAL = "#2a78d6", "#eb6834", "#f0efec"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
ARC = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00", "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
                     "xtick.color": MUTED, "ytick.color": INK2, "axes.titlecolor": INK, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "savefig.facecolor": SURF})


def _bar(ax, y, w, color, height=0.56):
    """A thin horizontal bar, square at the baseline, rounded at the data end."""
    if w <= 0:
        return
    r = min(0.12 * height, w / 2)
    ax.add_patch(FancyBboxPatch((0, y - height / 2), w, height, boxstyle=f"round,pad=0,rounding_size={r}",
                                linewidth=0, facecolor=color, mutation_aspect=1))
    ax.add_patch(Rectangle((0, y - height / 2), min(w, 2 * r), height, linewidth=0, facecolor=color))


def _title(fig, main, sub, top=0.86):
    """A left-aligned title inside the canvas (never clipped), the plot below it."""
    fig.text(0.012, 0.985, main, ha="left", va="top", fontsize=12.5, color=INK, fontweight="bold")
    fig.text(0.012, 0.985 - 0.075 * (6.0 / fig.get_figheight()), sub, ha="left", va="top", fontsize=10, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, top))


def _clean(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def funnel():
    f = json.load(open(os.path.join(HERE, "outputs", "reach_v1", "measure_funnel.json")))["funnel"]
    stages = [("Development tasks", 60), ("Native object engine fails", f["A_native_baseline_failure"]),
              ("Usable failure evidence", f["B_usable_failure_evidence"]),
              ("Machine-generated proposal", f["C_proposal"]), ("Compiled (canonical)", f["E_compilation"]),
              ("Installed in native engine", f["F_installation"]), ("Accepted and used", f["H_uses_extension"]),
              ("Full adaptive LOO", f["K_adaptive_loo"]), ("Activated", f["N_activation"])]
    fig, ax = plt.subplots(figsize=(8.4, 4.6), dpi=200)
    for i, (name, v) in enumerate(stages):
        y = len(stages) - 1 - i
        _bar(ax, y, v, BLUE)
        ax.text(v + 0.8, y, str(v), va="center", ha="left", color=INK, fontsize=12, fontweight="bold")
    ax.set_yticks(range(len(stages)))
    ax.set_yticklabels([s for s, _ in stages][::-1], fontsize=11)
    ax.set_xlim(0, 66)
    ax.set_ylim(-0.6, len(stages) - 0.4)
    ax.set_xticks([0, 10, 20, 30, 40, 50, 60])
    _clean(ax)
    _title(fig, "Real ARC-AGI-2 training-development tasks: the repair funnel",
           "reach v1, run once (frozen c8d8e3a; verifier 0 problems); no test output read", top=0.87)
    fig.savefig(os.path.join(FIG, "fig_funnel_reach_v1.png"))
    plt.close(fig)


def synthetic():
    rows = [("Repaired engine K*' (v1.9)", 27, BLUE), ("Earlier engine K*", 12, BASE)]
    fig, ax = plt.subplots(figsize=(6.6, 2.4), dpi=200)
    for i, (name, v, c) in enumerate(rows):
        y = 1 - i
        _bar(ax, y, v, c, height=0.5)
        ax.text(v + 0.4, y, f"{v} / 30", va="center", ha="left", color=INK, fontsize=12, fontweight="bold")
    ax.set_yticks([1, 0])
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlim(0, 34)
    ax.set_xticks([0, 10, 20, 30])
    ax.set_ylim(-0.6, 1.6)
    _clean(ax)
    _title(fig, "SYNTHETIC tasks only: complete B/P/U/L/T/A witnesses",
           "v1.9 prospective test, run once (record 2885a04); not ARC performance", top=0.72)
    fig.savefig(os.path.join(FIG, "fig_synthetic_v19.png"))
    plt.close(fig)


def _grid(ax, g, title):
    H, W = len(g), len(g[0])
    for r in range(H):
        for c in range(W):
            ax.add_patch(Rectangle((c, H - 1 - r), 1, 1, facecolor=ARC[g[r][c]], edgecolor="#555555", linewidth=0.3))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=10, color=INK2)


def demos(key="kf892487f1049"):
    t = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))["tasks"][key]
    n = len(t["train"])
    fig, axes = plt.subplots(2, n, figsize=(2.3 * n, 4.8), dpi=200)
    for i, p in enumerate(t["train"]):
        _grid(axes[0][i], p["input"], f"demonstration {i}: input")
        _grid(axes[1][i], p["output"], f"demonstration {i}: output")
    fig.suptitle(f"Development task {key} (opaque key): its {n} TRAINING demonstrations\n"
                 "rendered from the development bundle; no test input or test output shown",
                 fontsize=11, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(os.path.join(FIG, "fig_kf89_training_demonstrations.png"))
    plt.close(fig)


def admission(key="kf892487f1049"):
    el = json.load(open(os.path.join(HERE, "outputs", "loo_v1", "probe_eligibility.json")))
    pr = json.load(open(os.path.join(HERE, "outputs", "loo_v1", "probe_kf892487f1049.json")))
    order = el["trial_order"]
    subsets = el["tasks"][key]["subsets"]
    names = ["0123", "012", "013", "023", "123", "01", "02", "03", "12", "13", "23"]
    g_found = {"0123": "G"}
    g_found.update({p: ("G" if r["engine"].get("top_is_G") else "no G") for p, r in pr["pairs"].items()})
    #  outer folds (3 demonstrations): the top-level program of the rebuilt run (diagnosis rows)
    rows = {}
    for line in open(os.path.join(HERE, "outputs", "loo_v1", "diagnose_rows.jsonl")):
        if line.strip():
            r = json.loads(line)
            rows[r["key"]] = r
    g_sha = rows[f"{key}:full"]["A_E_WALL"]["program"]["sha"]
    for i in range(4):
        r = rows[f"{key}:f{i}"]
        ind = r["B_WALL"]["engine"]["trace"]["inductions"][0]      # a rejected induction keeps its top
        top = (ind.get("program") or (ind.get("near_solve") or {}).get("partial") or {}).get("sha")  # candidate here
        rest = "".join(str(j) for j in range(4) if j != i)
        g_found[rest] = "G" if top == g_sha else "G*"
    fig, ax = plt.subplots(figsize=(7.6, 5.4), dpi=200)
    for i, s in enumerate(names):
        y = len(names) - 1 - i
        rec = {v["variant"]: v for v in subsets[s]["variants"]}
        for j, v in enumerate(order):
            x = rec[v]
            col = BLUE if x["searched"] else (ORANGE if x["coherent"] else NEUTRAL)
            ax.add_patch(Rectangle((j + 0.04, y + 0.06), 0.92, 0.88, facecolor=col, linewidth=0))
            if v == "S6" and s in g_found:
                ax.text(j + 0.5, y + 0.5, g_found[s], ha="center", va="center",
                        color="white" if col != NEUTRAL else INK, fontsize=10, fontweight="bold")
    ax.set_xlim(0, len(order))
    ax.set_ylim(0, len(names))
    ax.set_xticks([j + 0.5 for j in range(len(order))])
    ax.set_xticklabels(order)
    ax.xaxis.tick_top()
    ax.set_yticks([len(names) - 1 - i + 0.5 for i in range(len(names))])
    ax.set_yticklabels([("demos " + " ".join(s)) + ("  (full)" if s == "0123" else "") for s in names], fontsize=10)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.set_xlabel("segmentation variants in the engine's fixed trial order (cap: first 4 eligible are searched)",
                  color=INK2, fontsize=10)
    ax.legend(handles=[Patch(color=BLUE, label="searched"), Patch(color=ORANGE, label="eligible but cut by the cap"),
                       Patch(color=NEUTRAL, label="not eligible (count relation fails)")],
              loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=3, frameon=False, fontsize=9.5)
    _title(fig, f"{key}: which segmentations the engine searches",
           "per demonstration subset; G = the full-data general program found in S6; G* = the same one-rule\n"
           "program with that fold's window_fill extension; forensic, development only", top=0.80)
    fig.savefig(os.path.join(FIG, "fig_kf89_variant_admission.png"))
    plt.close(fig)


def negative():
    path = os.path.join(HERE, "outputs", "loo_v1", "probe_negative.json")
    if not os.path.exists(path):
        return False
    s = json.load(open(path))["summary"]
    rows = [("No overlay (engine as is)", s["BASE"]), ("PROMOTE: eligible variant first", s["PROMOTE"]["outcomes"]),
            ("ADMIT: ineligible variant first", s["ADMIT"]["outcomes"])]
    cats = [("CORRECT", "accepted, held-out exact", GOOD), ("FALSE_ACCEPT", "accepted, held-out wrong", CRITICAL),
            ("REJECT", "rejected", BASE)]
    fig, ax = plt.subplots(figsize=(8.4, 3.0), dpi=200)
    for i, (name, o) in enumerate(rows):
        y = len(rows) - 1 - i
        tot = sum(o[c] for c, _l, _k in cats)
        left = 0.0
        for c, _l, col in cats:
            w = o[c] / tot if tot else 0
            if w > 0:
                ax.add_patch(Rectangle((left, y - 0.28), w - 0.004, 0.56, facecolor=col, linewidth=0))
                if w > 0.07:
                    ax.text(left + w / 2, y, str(o[c]), ha="center", va="center",
                            color="white" if col != BASE else INK, fontsize=10, fontweight="bold")
            left += w
        ax.text(1.01, y, f"n = {tot}", va="center", ha="left", color=INK2, fontsize=10)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.set_xlim(0, 1.12)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    _clean(ax)
    ax.legend(handles=[Patch(color=k, label=f"{c.replace('_', ' ').lower()}: {l}") for c, l, k in cats],
              loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False, fontsize=9)
    _title(fig, "Negative controls on SYNTHETIC tasks: does forcing a variant first add false acceptances?",
           "engine's own induction (train-exact + its own LOO); 3 training + 2 held-out demonstrations per task", top=0.72)
    fig.savefig(os.path.join(FIG, "fig_negative_controls.png"))
    plt.close(fig)
    return True


def main():
    os.makedirs(FIG, exist_ok=True)
    funnel()
    synthetic()
    demos()
    admission()
    ok = negative()
    print("figures:", sorted(os.listdir(FIG)), "| negative controls:", "drawn" if ok else "pending")


if __name__ == "__main__":
    sys.exit(main())
