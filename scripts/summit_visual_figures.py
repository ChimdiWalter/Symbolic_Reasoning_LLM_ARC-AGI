"""Figures for the VISUAL-FIRST summit review poster and its explainer (2026-10-19).

  python scripts/summit_visual_figures.py
      -> docs/summit_20261023_reframe/figures/*.png
      -> docs/summit_20261023_reframe/figures/PROVENANCE.json and docs/summit_20261023_reframe/POSTER_FIGURE_PROVENANCE.json

**Real figures** are drawn ONLY from recorded, hash-pinned inputs. A sha256 mismatch stops the script before
anything is drawn. Real grids are drawn cell for cell with the standard ARC colours; nothing is edited.

**The ILLUSTRATIVE figures** (four reasons an explanation can be inadequate; the three-failure version for the
Qwen-architecture review poster) are drawn by hand for explanation. Each says so on its face, and neither is ever
presented as a CORA result.

**Printed size.** Every figure is 9.37 in wide, the measured text width of one block of the visual review poster
(677.3 pt), and is placed at that width. Text is at least 20 pt at that size.
"""
import hashlib
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle   # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "docs", "summit_20261023_reframe", "figures")
W, DPI = 9.37, 200                       # the measured block text width (677.3 pt) of the visual review poster
FS_MIN, FS_LAB, FS_BIG = 20, 23, 27
INK, INK2, MUTED, SURF = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
GOOD, CRITICAL, ACCENT, NEUTRAL = "#0ca30c", "#d03b3b", "#2a78d6", "#f0efec"
ARC = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00", "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
ARC_NAME = {1: "blue", 2: "red", 3: "green", 4: "yellow", 8: "azure"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": FS_LAB, "figure.facecolor": SURF,
                     "savefig.facecolor": SURF})

SOURCES = {
    "v2_witness": ("docs/summit_demo_20261023/data/v2_witness_00dbd492.json",
                   "bc25278203700e28bdf429ceaf97ac33cf3fec504a1f8d0b7a3c29b4f9fac283"),
    "real_task": ("docs/summit_demo_20261023/data/real_task.json",
                  "b06073a7fd35d203875e673aaec4b550d0069cdc43631afd2cafdb9d3b362f45"),
    "real_witness": ("docs/summit_demo_20261023/data/real_witness.json",
                     "f0da3a8df23bbab61b9a39360480651bebda765ec302ede1b2d842a1a190b73f"),
    "dev60_assets": ("outputs/funnel_v0/eval_dev60_native_assets.json",
                     "54d8d744cc8cbd6bb905ee7fda34f5f9ed5005bda770bb4b206b392d97d9c42f"),
    "gen58": ("outputs/cora_fhr/rows_standin58_gen.jsonl",
              "0ff69e04490a0b208dc843e2175f44a294c8fe7ee4c2824df4739b059e519e71"),
    # ISIC Archive, CC-0 (see CANCER_LESION_IMAGE_PROVENANCE.md): the image, its own archive record, and the matching
    # ISIC 2018 Task 1 ground-truth mask (same image ID, CC-0)
    "isic_image": ("docs/summit_20261023_reframe/figures/ISIC_0000013.jpg",
                   "087a955305a31cf5c6d197c9aa8848bb23822201b656d47f89fe4020a4b78650"),
    "isic_mask": ("docs/summit_20261023_reframe/figures/ISIC_0000013_segmentation.png",
                  "79d220455e70bf325e3e19a7e4c029a6fe9133637d8798b864d026bf3706bf9c"),
    "isic_record": ("docs/summit_20261023_reframe/figures/ISIC_0000013.isic_metadata.json",
                    "e68c4eba323690a73f0f90e96b448204ccb3ee5ab1b4bd81690fe18de2e39cf9"),
    # the author's annotated maize leaf (unpublished; read in place, never copied or modified): leaf 1 of the ID-gated
    # cohort of segmentors_backbones/projects/real_leaf_gallery_20261018 (see CANCER_LESION_IMAGE_PROVENANCE.md)
    "maize_photo": ("/deltos/e/lesion_phes/code/python/pipeline/segmentors_backbones/maize_lesion_study_v1/derived/"
                    "normalized_leaves/DSC_0042_segment_1_segmented_smoothed.png",
                    "c8d56405812fd9e50f55ae97d0fec8390d8b96df8019aebb406843f8b8b22954"),
    "maize_mask": ("/deltos/e/lesion_phes/code/python/pipeline/segmentors_backbones/maize_lesion_study_v1/derived/"
                   "pseudo_labels/DSC_0042_segment_1_segmented_smoothed_corrected.png",
                   "0f4b4d72ce0651a800c39d434be2bb4489871df0593cf2f6f9e2ba1b52cd381d"),
}
USED, DRAWN = {}, {}


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def src(name):
    rel, want = SOURCES[name]
    got = _sha(os.path.join(HERE, rel))
    if got != want:
        raise SystemExit(f"{rel}: sha256 {got} != pinned {want}; not drawing from an unrecorded input")
    USED[name] = {"path": rel, "sha256": got}
    return os.path.join(HERE, rel)


def _new(h):
    return plt.figure(figsize=(W, h), dpi=DPI)


def _ax(fig, x, y, w, h):
    H = fig.get_figheight()
    return fig.add_axes((x / W, y / H, w / W, h / H))


def _text(fig, x, y, s, **kw):
    kw.setdefault("fontsize", FS_LAB)
    kw.setdefault("color", INK)
    fig.text(x / W, y / fig.get_figheight(), s, **kw)


def _grid(fig, g, x0, y0, box, outlines=()):
    """A real or illustrative grid, scaled into a box x box square (centred); outlines: [(r0, c0, r1, c1, colour)]."""
    H, Wg = len(g), len(g[0])
    cell = box / max(H, Wg)
    gx, gy = x0 + (box - Wg * cell) / 2, y0 + (box - H * cell) / 2
    ax = _ax(fig, gx, gy, Wg * cell, H * cell)
    lw = 0.6 if max(H, Wg) <= 12 else 0.35
    for r in range(H):
        for c in range(Wg):
            ax.add_patch(Rectangle((c, H - 1 - r), 1, 1, facecolor=ARC[g[r][c]], edgecolor="#555555", linewidth=lw))
    for r0, c0, r1, c1, col in outlines:
        ax.add_patch(Rectangle((c0 + 0.12, H - 1 - r1 + 0.12), c1 - c0 + 0.76, r1 - r0 + 0.76, fill=False,
                               edgecolor=col, linewidth=3.4, linestyle="-"))
    ax.set_xlim(-0.2, Wg + 0.2)
    ax.set_ylim(-0.2, H + 0.2)
    ax.axis("off")


def _arrow(fig, x0, y, x1, color=INK2):
    H = fig.get_figheight()
    fig.patches.append(FancyArrowPatch((x0 / W, y / H), (x1 / W, y / H), transform=fig.transFigure,
                                       arrowstyle="-|>", mutation_scale=34, linewidth=3.0, color=color))


def _tag(fig, text, color=INK2):
    fig.text(0.10 / W, 1 - 0.10 / fig.get_figheight(), text, ha="left", va="top", fontsize=FS_MIN, color=color,
             linespacing=1.25)


def _save(fig, name, kind, sources, task, mode, limits):
    fig.savefig(os.path.join(FIG, name), dpi=DPI, metadata={"Software": None})
    h = fig.get_figheight()
    DRAWN[name] = {"kind": kind, "width_in": W, "height_in": round(h, 3), "dpi": DPI, "min_font_pt": FS_MIN,
                   "sources": {k: USED[k] for k in sources}, "source_task_id": task, "source_evaluation_mode": mode,
                   "generation_command": "python scripts/summit_visual_figures.py", "evidence_limitations": limits}
    plt.close(fig)


# ---------------------------------------------------------------- column 1: what an ARC task is (REAL)
def arc_intro(box=2.25, H=9.45, fname="fig_arc_intro_00dbd492.png", xin=0.85, xout=5.35, step=2.95):
    w = json.load(open(src("v2_witness")))
    assert w["key"] == "00dbd492"
    fig = _new(H)
    _tag(fig, "REAL ARC-AGI-2 TRAINING TASK 00dbd492 (public)")
    rows = [("Training example 1", w["train"][0][0], w["train"][0][1]),
            ("Training example 2", w["train"][1][0], w["train"][1][1]),
            ("New input", w["test_input"], None)]
    for i, (name, gin, gout) in enumerate(rows):
        y = H - 0.62 - (i + 1) * step + 0.12
        _text(fig, xin, y + box + 0.12, name, fontsize=FS_BIG, fontweight="bold")
        _grid(fig, gin, xin, y, box)
        _arrow(fig, xin + box + 0.25, y + box / 2, xout - 0.25)
        if gout is not None:
            _grid(fig, gout, xout, y, box)
        else:
            ax = _ax(fig, xout, y, box, box)
            ax.add_patch(FancyBboxPatch((0.02, 0.02), 0.96, 0.96, boxstyle="round,pad=0,rounding_size=0.05",
                                        facecolor=NEUTRAL, edgecolor=MUTED, linewidth=2.5, linestyle="--"))
            ax.text(0.5, 0.5, "?", ha="center", va="center", fontsize=96, color=INK2, fontweight="bold")
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
    _save(fig, fname, "REAL", ("v2_witness",), "00dbd492",
          "public ARC-AGI-2 training task (training pairs and test input as recorded)",
          "An exposed public training task used in CORA-v2 development; shown only to explain what an ARC task is.")


# ---------------------------------------------------------------- column 1: four reasons (ILLUSTRATIVE)
def _blank(n=6):
    return [[0] * n for _ in range(n)]


def _put(g, cells, v):
    for r, c in cells:
        g[r][c] = v
    return g


def four_reasons():
    """Four reasons an explanation can be inadequate (ILLUSTRATIVE, drawn for explanation). Per panel: a title, a
    caption line, then the grids across the full width."""
    H = 11.3
    fig = _new(H)
    _tag(fig, "ILLUSTRATIVE — drawn to explain, not a CORA result", color=CRITICAL)
    white = "#ffffff"
    ex_in, ex_out = _put(_blank(), [(2, 1)], 1), _put(_blank(), [(2, 4)], 1)
    new_in, guess = _put(_blank(), [(4, 0)], 1), _put(_blank(), [(2, 4)], 1)
    rep = _put(_put(_put(_blank(), [(1, 1), (1, 2), (2, 1), (2, 2)], 2), [(1, 3), (2, 3)], 1), [(4, 4), (4, 5)], 2)
    c_in = _put(_blank(), [(2, 0), (2, 5)], 8)
    c_out = _put(_put(_blank(), [(2, 0), (2, 5)], 8), [(2, 1), (2, 2), (2, 3), (2, 4)], 5)
    d_in, d_out = _put(_blank(), [(0, 0), (0, 1)], 5), _put(_blank(), [(0, 0), (0, 1)], 2)
    d_new = _put(_put(_blank(), [(4, 2), (4, 3)], 5), [(1, 2), (1, 3), (1, 4)], 5)
    d_h1 = _put(_put(_blank(), [(4, 2), (4, 3)], 2), [(1, 2), (1, 3), (1, 4)], 5)
    d_h2 = _put(_put(_blank(), [(4, 2), (4, 3)], 5), [(1, 2), (1, 3), (1, 4)], 2)
    box = 1.0
    tops = [H - 0.55 - 2.60 * k for k in range(4)]

    def panel(top, title, caps):
        _text(fig, 0.15, top - 0.05, title, fontsize=FS_BIG, fontweight="bold", va="top")
        for k, cap in enumerate(caps):
            _text(fig, 0.15, top - 0.50 - 0.34 * k, cap, fontsize=FS_MIN, color=INK2, va="top")
        return top - 0.93 - 0.34 * (len(caps) - 1) - box

    def row(y, grids, xs, labels, b=box, colours=None):
        for i, ((g, outl), x, lab) in enumerate(zip(grids, xs, labels)):
            _grid(fig, g, x, y, b, outlines=outl)
            if lab:
                col = (colours or {}).get(i, INK2)
                _text(fig, x + b / 2, y - 0.34, lab, fontsize=FS_MIN, color=col, ha="center",
                      fontweight="bold" if i in (colours or {}) else "normal")
    # A memorization
    y = panel(tops[0], "A  Memorization", ["A rule that copies the example fits it, then fails a new input."])
    xs = [0.40, 2.30, 4.95, 6.85]
    row(y, [(ex_in, ()), (ex_out, ()), (new_in, ()), (guess, ())], xs, ["example", "✓ fits", "new input", "✗ its guess"],
        colours={1: GOOD, 3: CRITICAL})
    _arrow(fig, xs[0] + box + 0.08, y + box / 2, xs[1] - 0.08)
    _arrow(fig, xs[2] + box + 0.08, y + box / 2, xs[3] - 0.08)
    # B representation
    y = panel(tops[1], "B  Wrong objects", ["The same grid can be split into objects in more than one way."])
    xs = [0.40, 2.30]
    row(y, [(rep, [(1, 1, 2, 3, white), (4, 4, 4, 5, white)]),
            (rep, [(1, 1, 2, 2, white), (1, 3, 2, 3, white), (4, 4, 4, 5, white)])], xs, ["2 objects", "3 objects"])
    _text(fig, 4.25, y + box - 0.20, "A rule written for one split", fontsize=FS_MIN, color=INK2, va="top")
    _text(fig, 4.25, y + box - 0.56, "can fail on the other.", fontsize=FS_MIN, color=INK2, va="top")
    # C rule language
    y = panel(tops[2], "C  Missing rule", ["The right objects, but no operation describes the change."])
    xs = [0.40, 2.30]
    row(y, [(c_in, ()), (c_out, ())], xs, ["input", "output"])
    _arrow(fig, xs[0] + box + 0.08, y + box / 2, xs[1] - 0.08)
    _text(fig, 4.25, y + box - 0.20, "operations: move, recolour", fontsize=FS_MIN, color=INK, va="top")
    _text(fig, 4.25, y + box - 0.62, "✗ neither can draw the line", fontsize=FS_MIN, color=CRITICAL, va="top",
          fontweight="bold")
    # D evidence
    y = panel(tops[3], "D  Not enough evidence", ["Rule 1: bars of 2 turn red.  Rule 2: top bars turn red.",
                                                  "Both fit the example; they disagree on a new input."])
    b = 0.95
    xs = [0.40, 1.95, 4.30, 5.85, 7.40]
    row(y, [(d_in, ()), (d_out, ()), (d_new, ()), (d_h1, ()), (d_h2, ())], xs,
        ["example", "", "new input", "rule 1", "rule 2"], b=b)
    _arrow(fig, xs[0] + b + 0.08, y + b / 2, xs[1] - 0.08)
    _arrow(fig, xs[2] + b + 0.08, y + b / 2, xs[3] - 0.08)
    _save(fig, "fig_four_reasons_ILLUSTRATIVE.png", "ILLUSTRATIVE", (), None, "hand-drawn illustration",
          "Not an ARC task and not a CORA result. Drawn only to explain memorization, representation, rule-language "
          "and evidence failures.")


def three_failures():
    """Why reasoning fails (ILLUSTRATIVE, drawn for explanation): wrong objects, wrong transformation, not enough
    evidence. Per panel: a title, one short sentence, then large grids. The Qwen-architecture review poster, column 1."""
    H = 14.6
    fig = _new(H)
    _tag(fig, "ILLUSTRATIVE — drawn to explain, not a CORA result", color=CRITICAL)
    white = "#ffffff"
    rep = _put(_put(_put(_blank(), [(1, 1), (1, 2), (2, 1), (2, 2)], 2), [(1, 3), (2, 3)], 1), [(4, 4), (4, 5)], 2)
    c_in = _put(_blank(), [(2, 0), (2, 5)], 8)
    c_out = _put(_put(_blank(), [(2, 0), (2, 5)], 8), [(2, 1), (2, 2), (2, 3), (2, 4)], 5)
    d_in, d_out = _put(_blank(), [(0, 0), (0, 1)], 5), _put(_blank(), [(0, 0), (0, 1)], 2)
    d_new = _put(_put(_blank(), [(4, 2), (4, 3)], 5), [(1, 2), (1, 3), (1, 4)], 5)
    d_h1 = _put(_put(_blank(), [(4, 2), (4, 3)], 2), [(1, 2), (1, 3), (1, 4)], 5)
    d_h2 = _put(_put(_blank(), [(4, 2), (4, 3)], 5), [(1, 2), (1, 3), (1, 4)], 2)
    FS_SENT = 22

    def head(top, title, sentence):
        _text(fig, 0.15, top, title, fontsize=FS_BIG + 3, fontweight="bold", va="top")
        _text(fig, 0.15, top - 0.52, sentence, fontsize=FS_SENT, color=INK, va="top")
        return top - 1.02

    def lab(x, y, s, col=INK2, bold=False):
        _text(fig, x, y, s, fontsize=FS_MIN, color=col, ha="center", va="top", fontweight="bold" if bold else "normal")
    # 1 wrong objects: the same grid, split two ways
    b = 2.2
    y = head(H - 0.62, "Wrong objects", "The grid is split into the wrong pieces.") - b
    xa, xb = 1.20, 6.17
    _grid(fig, rep, xa, y, b, outlines=[(1, 1, 2, 3, white), (4, 4, 4, 5, white)])
    _grid(fig, rep, xb, y, b, outlines=[(1, 1, 2, 2, white), (1, 3, 2, 3, white), (4, 4, 4, 5, white)])
    _text(fig, (xa + b + xb) / 2, y + b / 2, "or", fontsize=FS_BIG, color=INK2, ha="center", va="center")
    lab(xa + b / 2, y - 0.10, "2 objects")
    lab(xb + b / 2, y - 0.10, "3 objects")
    # 2 wrong transformation: right pieces, no operation that draws the line
    y = head(y - 0.80, "Wrong transformation", "Right pieces, but no operation makes the change.") - b
    xa, xb = 0.60, 3.70
    _grid(fig, c_in, xa, y, b)
    _grid(fig, c_out, xb, y, b)
    _arrow(fig, xa + b + 0.15, y + b / 2, xb - 0.15)
    lab(xa + b / 2, y - 0.10, "input")
    lab(xb + b / 2, y - 0.10, "output")
    _text(fig, 6.20, y + b - 0.30, "tried:", fontsize=FS_MIN, color=INK2, va="top")
    _text(fig, 6.20, y + b - 0.78, "move  ✗", fontsize=FS_LAB, color=CRITICAL, va="top", fontweight="bold")
    _text(fig, 6.20, y + b - 1.26, "recolour  ✗", fontsize=FS_LAB, color=CRITICAL, va="top", fontweight="bold")
    # 3 not enough evidence: two rules fit one example and disagree on a new input
    b = 1.9
    y = head(y - 0.80, "Not enough evidence", "Two rules fit the example but give different answers.") - b
    xa, xb = 0.35, 2.95
    _grid(fig, d_in, xa, y, b)
    _grid(fig, d_out, xb, y, b)
    _arrow(fig, xa + b + 0.15, y + b / 2, xb - 0.15)
    lab(xa + b / 2, y - 0.10, "example")
    lab(xb + b / 2, y - 0.10, "its output")
    _text(fig, 5.10, y + b - 0.25, "rule 1: bars of 2 turn red", fontsize=FS_MIN, color=INK, va="top")
    _text(fig, 5.10, y + b - 0.72, "rule 2: the top bar turns red", fontsize=FS_MIN, color=INK, va="top")
    _text(fig, 5.10, y + b - 1.19, "both fit this example", fontsize=FS_MIN, color=GOOD, va="top", fontweight="bold")
    y = y - 0.55 - b
    xn, x1, x2 = 0.35, 2.95, 5.10
    _grid(fig, d_new, xn, y, b)
    _arrow(fig, xn + b + 0.15, y + b / 2, x1 - 0.15)
    _grid(fig, d_h1, x1, y, b)
    _grid(fig, d_h2, x2, y, b)
    lab(xn + b / 2, y - 0.10, "new input")
    lab(x1 + b / 2, y - 0.10, "rule 1 says")
    lab(x2 + b / 2, y - 0.10, "rule 2 says")
    _text(fig, 7.15, y + b / 2 + 0.22, "which one?", fontsize=FS_LAB, color=CRITICAL, va="center", fontweight="bold")
    assert y - 0.55 > 0, "three_failures: the last row is below the canvas"
    _save(fig, "fig_three_failures_ILLUSTRATIVE.png", "ILLUSTRATIVE", (), None, "hand-drawn illustration",
          "Not an ARC task and not a CORA result. Drawn only to explain representation (objects), transformation "
          "(rule-language) and evidence failures; used by the Qwen-architecture review poster.")


def three_causes_row():
    """The science-first poster's compact row of three possible causes (ILLUSTRATIVE): wrong objects, wrong rule, not
    enough evidence. The same hand-drawn grids as `three_failures`, one panel each."""
    H = 4.15
    fig = _new(H)
    _tag(fig, "ILLUSTRATIVE — drawn to explain, not a CORA result", color=CRITICAL)
    white = "#ffffff"
    rep = _put(_put(_put(_blank(), [(1, 1), (1, 2), (2, 1), (2, 2)], 2), [(1, 3), (2, 3)], 1), [(4, 4), (4, 5)], 2)
    c_in = _put(_blank(), [(2, 0), (2, 5)], 8)
    c_out = _put(_put(_blank(), [(2, 0), (2, 5)], 8), [(2, 1), (2, 2), (2, 3), (2, 4)], 5)
    d_h1 = _put(_put(_blank(), [(4, 2), (4, 3)], 2), [(1, 2), (1, 3), (1, 4)], 5)
    d_h2 = _put(_put(_blank(), [(4, 2), (4, 3)], 5), [(1, 2), (1, 3), (1, 4)], 2)
    b, top, y = 1.22, H - 0.55, 0.98

    def head(x, titles, l1, l2):
        for k, t in enumerate(titles):
            _text(fig, x + 1.48, top - 0.42 * k, t, fontsize=FS_BIG, fontweight="bold", ha="center", va="top")
        _text(fig, x + 1.48, 0.66, l1, fontsize=FS_MIN, color=INK2, ha="center", va="top")
        _text(fig, x + 1.48, 0.33, l2, fontsize=FS_MIN, color=INK2, ha="center", va="top")
    x = 0.12
    head(x, ("Wrong", "objects"), "the grid grouped", "the wrong way")
    _grid(fig, rep, x + 0.08, y, b, outlines=[(1, 1, 2, 3, white), (4, 4, 4, 5, white)])
    _text(fig, x + 1.48, y + b / 2, "or", fontsize=FS_LAB, color=INK2, ha="center", va="center")
    _grid(fig, rep, x + 1.66, y, b, outlines=[(1, 1, 2, 2, white), (1, 3, 2, 3, white), (4, 4, 4, 5, white)])
    x = 3.22
    head(x, ("Wrong", "rule"), "no operation", "draws the line")
    _grid(fig, c_in, x + 0.08, y, b)
    _arrow(fig, x + 0.08 + b + 0.08, y + b / 2, x + 1.66 - 0.08)
    _grid(fig, c_out, x + 1.66, y, b)
    x = 6.32
    head(x, ("Not enough", "evidence"), "both rules fit;", "they disagree here")
    _grid(fig, d_h1, x + 0.08, y, b)
    _text(fig, x + 1.48, y + b / 2, "≠", fontsize=FS_BIG, color=CRITICAL, ha="center", va="center", fontweight="bold")
    _grid(fig, d_h2, x + 1.66, y, b)
    _save(fig, "fig_three_causes_row_ILLUSTRATIVE.png", "ILLUSTRATIVE", (), None, "hand-drawn illustration",
          "Not an ARC task and not a CORA result. The science-first poster's compact row: wrong objects, wrong rule, "
          "not enough evidence (the same grids as fig_three_failures_ILLUSTRATIVE.png).")


def skin_lesion():
    """The cancer-lesion poster's opening pair (REAL MEDICAL IMAGE, motivation only; not CORA data):
    A, ISIC_0000013 as published (resized for display only); B, the same image with the outline of its own ISIC 2018
    Task 1 ground-truth mask (dermatologist-reviewed) drawn on top. Nothing else is changed."""
    import numpy as np
    from PIL import Image
    rec = json.load(open(src("isic_record")))
    cl = rec["metadata"]["clinical"]
    assert rec["isic_id"] == "ISIC_0000013" and rec["copyright_license"] == "CC-0"
    assert cl["diagnosis_1"] == "Malignant" and cl["diagnosis_3"] == "Melanoma Invasive"
    assert cl["diagnosis_confirm_type"] == "histopathology" and rec["metadata"]["acquisition"]["image_type"] == "dermoscopic"
    img = np.asarray(Image.open(src("isic_image")).convert("RGB"))
    mask = np.asarray(Image.open(src("isic_mask")))
    assert mask.shape == img.shape[:2], "the mask must have the image's own size (same ID, same geometry)"
    Wf, b = 6.60, 2.85                                   # each panel 2.85 in wide: smaller than the main ARC grids
    h = b * img.shape[0] / img.shape[1]
    H = h + 3.11
    fig = plt.figure(figsize=(Wf, H), dpi=DPI)
    for k, line in enumerate(("REAL MEDICAL IMAGE — ILLUSTRATIVE", "MOTIVATION, NOT CORA DATA")):
        fig.text(0.12 / Wf, 1 - (0.08 + 0.36 * k) / H, line, ha="left", va="top", fontsize=FS_MIN, color=CRITICAL,
                 fontweight="bold")
    y0 = 1.96
    for k, (label, outline) in enumerate((("A  observation", False), ("B  expert boundary", True))):
        x0 = 0.12 + k * (b + 0.50)
        ax = fig.add_axes((x0 / Wf, y0 / H, b / Wf, h / H))
        ax.imshow(img, interpolation="antialiased")
        if outline:
            ax.contour(mask > 127, levels=[0.5], colors=["#00e5ff"], linewidths=2.6)
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#888888")
        fig.text((x0 + b / 2) / Wf, (y0 + h + 0.08) / H, label, ha="center", va="bottom", fontsize=FS_MIN, color=INK)
    # the documented diagnosis is quoted from the ISIC record (asserted above), never inferred from the picture
    for k, line in enumerate(("ISIC_0000013 · ISIC Archive · CC-0", "attribution: Anonymous",
                              "ISIC record: invasive melanoma", "(histopathology-confirmed)",
                              "B: its own ISIC 2018 Task 1 mask (CC-0)")):
        fig.text(0.12 / Wf, (1.72 - 0.33 * k) / H, line, ha="left", va="top", fontsize=FS_MIN, color=INK2)
    fname = "fig_skin_lesion_ISIC_0000013_with_boundary.png"
    fig.savefig(os.path.join(FIG, fname), dpi=DPI, metadata={"Software": None})
    DRAWN[fname] = {"kind": "REAL_MEDICAL_IMAGE_MOTIVATION", "width_in": Wf, "height_in": round(H, 3), "dpi": DPI,
                    "min_font_pt": FS_MIN, "sources": {k: USED[k] for k in ("isic_record", "isic_image", "isic_mask")},
                    "source_task_id": "ISIC_0000013", "source_evaluation_mode": "ISIC Archive image record and ISIC 2018 "
                    "Task 1 training ground truth (both CC-0)", "generation_command": "python scripts/summit_visual_figures.py",
                    "transformations": "A: the original JPEG resized for display (no crop, no colour change). B: the same, "
                                       "plus the contour of its own binary mask (pixels > 127) drawn as a 2.6 pt cyan line.",
                    "evidence_limitations": "Motivation only; not CORA data. The ISIC record documents a histopathology-"
                    "confirmed invasive melanoma; the image itself does not establish that, and the boundary is a spatial "
                    "annotation, not a diagnosis or a mechanism."}
    plt.close(fig)


def maize_tile():
    """The cancer-lesion poster's panel C (REAL maize image, the author's annotated leaf; motivation only, not CORA
    data): a crop of DSC_0042 magnified x2 (nearest neighbour, pixel-exact) with the outline of its expert-corrected
    lesion annotation. The window comes from a rule fixed before rendering: 360 x 214 px, at least 99% leaf, the most
    complete 8-connected annotated lesions of >= 500 px (Project A's contract size); ties: more annotated pixels, then
    the smallest y, then the smallest x."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    rgb = np.asarray(Image.open(src("maize_photo")).convert("RGB"))
    m = np.asarray(Image.open(src("maize_mask")))
    gt = (m > 0) if m.ndim == 2 else (m[..., 2] > 0)    # Project A's gt_of: cv2 channel 0 (BGR) is PIL channel 2
    assert gt.shape == rgb.shape[:2]
    w, h = 360, 214
    leaf = rgb.astype(int).sum(2) > 30
    lab, n = ndimage.label(gt, structure=np.ones((3, 3)))
    area = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
    ny, nx = gt.shape[0] - h + 1, gt.shape[1] - w + 1
    cnt = np.zeros((ny + 1, nx + 1), int)
    for s_, ar in zip(ndimage.find_objects(lab), area):
        if ar < 500:
            continue
        ya, yb, xa, xb = max(s_[0].stop - h, 0), min(s_[0].start, ny - 1), max(s_[1].stop - w, 0), min(s_[1].start, nx - 1)
        if ya <= yb and xa <= xb:
            cnt[ya, xa] += 1; cnt[ya, xb + 1] -= 1; cnt[yb + 1, xa] -= 1; cnt[yb + 1, xb + 1] += 1
    cnt = cnt.cumsum(0).cumsum(1)[:ny, :nx]

    def box(mm):
        ii = np.pad(mm.astype(np.int64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
        return ii[h:h + ny, w:w + nx] - ii[:ny, w:w + nx] - ii[h:h + ny, :nx] + ii[:ny, :nx]
    ann, ok = box(gt), box(leaf) >= 0.99 * w * h
    score = np.where(ok, cnt, -1)
    y0w, x0w = min(map(tuple, np.argwhere(score == score.max())), key=lambda t: (-ann[t], t[0], t[1]))
    assert (y0w, x0w, score.max()) == (280, 459, 6), (y0w, x0w, score.max())
    crop = rgb[y0w:y0w + h, x0w:x0w + w].repeat(2, 0).repeat(2, 1)
    cgt = gt[y0w:y0w + h, x0w:x0w + w].repeat(2, 0).repeat(2, 1)
    hh = 2.85 * 767 / 1022                               # the skin panels' height, so A, B and C line up
    bm = hh * w / h
    Wm, H, y0 = bm + 0.30, hh + 3.11, 1.96               # same total height and panel baseline as skin_lesion()
    fig = plt.figure(figsize=(Wm, H), dpi=DPI)
    for k, line in enumerate(("REAL MAIZE LEAF,", "NOT CORA DATA")):
        fig.text(0.12 / Wm, 1 - (0.08 + 0.36 * k) / H, line, ha="left", va="top", fontsize=FS_MIN, color=CRITICAL,
                 fontweight="bold")
    ax = fig.add_axes((0.12 / Wm, y0 / H, bm / Wm, hh / H))
    ax.imshow(crop, interpolation="nearest")
    ax.contour(cgt, levels=[0.5], colors=["#00e5ff"], linewidths=2.0)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor("#888888")
    fig.text((0.12 + bm / 2) / Wm, (y0 + hh + 0.08) / H, "C  annotated lesions", ha="center", va="bottom",
             fontsize=FS_MIN, color=INK)
    for k, line in enumerate(("maize leaf DSC_0042", "author's study", "(unpublished data)", "cyan: annotation",
                              "crop magnified \u00d72")):
        fig.text(0.12 / Wm, (1.72 - 0.33 * k) / H, line, ha="left", va="top", fontsize=FS_MIN, color=INK2)
    fname = "fig_maize_annotated_DSC_0042_crop_x2.png"
    fig.savefig(os.path.join(FIG, fname), dpi=DPI, metadata={"Software": None})
    DRAWN[fname] = {"kind": "REAL_MAIZE_IMAGE_MOTIVATION", "width_in": round(Wm, 3), "height_in": round(H, 3), "dpi": DPI,
                    "min_font_pt": FS_MIN, "sources": {k: USED[k] for k in ("maize_photo", "maize_mask")},
                    "source_task_id": "DSC_0042_segment_1_segmented_smoothed",
                    "source_evaluation_mode": "leaf 1 of the ID-gated real_leaf_gallery_20261018 cohort (a Project A "
                    "validation leaf); expert-corrected annotation binarised as Project A's gt_of (mask > 0)",
                    "window": {"y": [int(y0w), int(y0w) + h], "x": [int(x0w), int(x0w) + w],
                               "complete_lesions_ge_500px": 6, "annotated_px": int(ann[y0w, x0w]),
                               "rule": "360x214 px, >= 99% leaf, most complete 8-connected annotated lesions >= 500 px; "
                                       "ties: more annotated px, then smallest y, then smallest x"},
                    "generation_command": "python scripts/summit_visual_figures.py",
                    "transformations": "Crop of the stored photograph, magnified x2 by nearest-neighbour repetition (no "
                                       "interpolation, no colour change), plus the 2.0 pt cyan contour of the annotation.",
                    "evidence_limitations": "Motivation only; not CORA data and not a Project A result. Unpublished "
                    "data from the author's study; an annotation marks where lesions are, not what caused them."}
    plt.close(fig)


def construction_58():
    """The 58-task generalization test of rule construction, one square per task (REAL, from the frozen rows)."""
    rows = [json.loads(l) for l in open(src("gen58"))]
    assert len(rows) == 58 and len({r["key"] for r in rows}) == 58
    for arm in ("EG", "C2G", "DG", "EGC"):
        assert not any(r["arms"][arm].get("outcome") == "CERTIFIED_WITH_EXTENSION" for r in rows), arm
    eg = [r["arms"]["EG"]["outcome"] for r in rows]
    n_none, n_fail = eg.count("NO_PROPOSAL"), eg.count("ENGINE_REJECTION") + eg.count("LOO_FAILURE")
    assert (n_none, n_fail) == (55, 3) and n_none + n_fail == 58
    H = 2.75
    fig = _new(H)
    _tag(fig, "REAL · 58 separately selected, exposed training tasks")
    cell, pitch, ncol = 0.31, 0.355, 10
    x0, ytop = 0.20, H - 0.55
    light, warm = "#d9d8d4", "#eb6834"
    colours = [light] * n_none + [warm] * n_fail
    for k, col in enumerate(colours):
        r, c = divmod(k, ncol)
        ax = _ax(fig, x0 + c * pitch, ytop - (r + 1) * pitch + (pitch - cell), cell, cell)
        ax.add_patch(FancyBboxPatch((0.04, 0.04), 0.92, 0.92, boxstyle="round,pad=0,rounding_size=0.12",
                                    facecolor=col, edgecolor="none"))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
    xl = x0 + ncol * pitch + 0.30
    entries = [(light, None, f"{n_none}", "no rule proposed"),
               (warm, None, f"{n_fail}", "rule proposed, but rejected\nby CORA's checks"),
               (SURF, GOOD, "0", "new verified solutions")]
    for j, (fc, ec, n, label) in enumerate(entries):
        yy = ytop - 0.22 - (0, 0.72, 1.60)[j]
        ax = _ax(fig, xl, yy - 0.18, cell, cell)
        ax.add_patch(FancyBboxPatch((0.06, 0.06), 0.88, 0.88, boxstyle="round,pad=0,rounding_size=0.12",
                                    facecolor=fc, edgecolor=ec or "none", linewidth=2.6))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        _text(fig, xl + cell + 0.18, yy, n, fontsize=FS_BIG, color=GOOD if ec else INK, fontweight="bold", va="center")
        _text(fig, xl + cell + 0.85, yy, label, fontsize=FS_MIN, color=INK, va="center", linespacing=1.15)
    _save(fig, "fig_construction_58_outcomes.png", "REAL", ("gen58",), "standin58 (58 exposed training tasks)",
          "frozen guard-generalization test (ad4127a), arm EG (authentic failure records + guard); outcome labels only",
          "Exposed training tasks; arm EG shown; the failure-blind (C2G), shuffled (DG) and contrast (EGC) arms also "
          "certified 0 (asserted); frozen native solved 1, which is not a construction result.")


# ---------------------------------------------------------------- column 2: the real constructed rule (REAL)
def real_rule(box=2.62, H=7.2, fname="fig_real_rule_ka95aa62f67d9.png", xout=5.35, label_right=False, xin=0.85):
    t = json.load(open(src("real_task")))
    w = json.load(open(src("real_witness")))
    assert w["committed"] == t["evaluator_answer"] and all(f["class"] == "SUCCESS" for f in w["folds"])
    assert w["rule"] == "if colours == (1,): ray(NW,border)[centre] else ray(SE,border)[centre]"
    assert w["controls"]["C2G_same_rule"] is True and not w["controls"]["A_frozen_native_certified"]
    fig = _new(H)
    _tag(fig, f"REAL ARC-AGI-2 TRAINING TASK {t['key']} · recorded run")
    rows = [("Training example", t["train"][0][0], t["train"][0][1], "target output"),
            ("New input", t["test_input"], w["committed"], "CORA's output ✓ correct")]
    for i, (name, gin, gout, olab) in enumerate(rows):
        y = H - 0.75 - (i + 1) * (box + 0.58) + 0.30
        _text(fig, xin, y + box + 0.12, name, fontsize=FS_BIG, fontweight="bold")
        _text(fig, xout + box if label_right else xout, y + box + 0.12, olab, fontsize=FS_MIN, color=GOOD if i else INK2,
              fontweight="bold" if i else "normal", ha="right" if label_right else "left")
        _grid(fig, gin, xin, y, box)
        _arrow(fig, xin + box + 0.30, y + box / 2, xout - 0.30)
        _grid(fig, gout, xout, y, box)
    _save(fig, fname, "REAL", ("real_task", "real_witness"), t["key"],
          "development probe (guard probe, arm EG), recorded run; evaluator answer read only in the evaluator step",
          "Exposed training task selected by the development autopsy; a failure-blind constructor found the same rule; "
          "not part of any Kaggle entry; not evidence of generalization.")


# ---------------------------------------------------------------- column 3: v2's correct but uncertified prediction (REAL)
def v2_uncertified(box=2.30, H=4.2, fname="fig_v2_uncertified_00dbd492_poster.png", xout=3.20, xt=6.00, xin=0.35):
    w = json.load(open(src("v2_witness")))
    assert w["evaluator_correct"] and w["tier_v2"] == "EXPLORATORY" and not any(w["controls"].values())
    fig = _new(H)
    _tag(fig, "REAL TASK 00dbd492 · CORA-v2 development run\nCORRECT DEVELOPMENT PREDICTION — NOT CERTIFIED", color=INK2)
    y = 0.58
    _grid(fig, w["test_input"], xin, y, box)
    _arrow(fig, xin + box + 0.08, y + box / 2, xout - 0.08)
    _grid(fig, w["v2_prediction"], xout, y, box)
    _text(fig, xin + box / 2, y - 0.40, "new input", fontsize=FS_MIN, color=INK2, ha="center")
    _text(fig, xout + box / 2, y - 0.40, "v2's guess (correct)", fontsize=FS_MIN, color=INK2, ha="center")
    sup, tab = w["test_table_support"], w["size_to_colour"]
    yt = y + box + 0.05
    _text(fig, xt, yt, "fill colour, by size:", fontsize=FS_MIN, color=INK2, va="top")
    for j, k in enumerate(sorted(sup, key=int)):
        n = sup[k]
        _text(fig, xt, yt - 0.44 * (j + 1), f"{ARC_NAME[tab[k]]}: {n} example{'s' if n > 1 else ''}", fontsize=FS_MIN,
              color=CRITICAL if n == 1 else INK, fontweight="bold" if n == 1 else "normal", va="top")
    _text(fig, xt, yt - 0.44 * 4 - 0.10, "hide that example:", fontsize=FS_MIN, color=CRITICAL, va="top")
    _text(fig, xt, yt - 0.44 * 5 - 0.10, "the check fails", fontsize=FS_MIN, color=CRITICAL, va="top", fontweight="bold")
    _save(fig, fname, "REAL", ("v2_witness",), "00dbd492",
          "CORA-v2 engineering run (blind rows; evaluator label recorded separately)",
          "Exposed training task examined in development; uncertified (fold fragility); in-sample; not evidence of "
          "generalization.")


# ---------------------------------------------------------------- explainer: the 60-task audit (REAL)
def dev60_audit():
    d = json.load(open(src("dev60_assets")))
    assert d["mode"] == "native_assets" and d["summary"]["tasks"] == 60
    cat = d["summary"]["categories"]
    assert sum(cat.values()) == 60 and d["summary"]["incorrect_accepted"] == 0
    order = [("CERTIFIED_CORRECT", "accepted, correct", GOOD), ("REJECTED_BUT_CORRECT", "correct, but rejected", ACCENT),
             ("FIT_BUT_ALL_WRONG", "fits examples, wrong on test", CRITICAL),
             ("NO_FIT_EXHAUSTED", "no rule fits (search done)", MUTED), ("NO_FIT_DEADLINE", "no rule fits (out of time)", MUTED),
             ("NO_SEARCH", "no usable objects", MUTED), ("NATIVE_ERROR", "engine error", MUTED)]
    fig = _new(6.6)
    _tag(fig, "REAL DEVELOPMENT · 60 exposed ARC-AGI-2 training tasks\nobject reasoner, frozen library and verbs (as submitted)")
    ax = _ax(fig, 5.55, 0.55, 3.55, 5.0)
    ys = list(range(len(order)))[::-1]
    for y, (k, lab, col) in zip(ys, order):
        ax.barh(y, cat[k], height=0.62, color=col)
        ax.text(cat[k] + 0.6, y, str(cat[k]), va="center", fontsize=FS_LAB, color=INK, fontweight="bold")
        fig.text(5.40 / W, (0.55 + (y + 0.5) * 5.0 / len(order)) / 6.6, lab, ha="right", va="center", fontsize=FS_MIN, color=INK)
    ax.set_xlim(0, 32)
    ax.set_ylim(-0.6, len(order) - 0.4)
    ax.axis("off")
    _save(fig, "fig_dev60_audit_assets.png", "REAL", ("dev60_assets",), "dev60 (60 opaque keys)",
          "instrumented failure funnel, native v23 object branch with frozen library cdacd018 and learned verbs b1f07ba5",
          "Exposed training-development tasks; one branch of CORA, not the whole harness (whole harness: 12 of 60 over two "
          "attempts); not evidence of generalization.")


def main():
    os.makedirs(FIG, exist_ok=True)
    arc_intro()
    four_reasons()
    real_rule()
    # the Qwen-architecture review poster: larger real grids, three failures, the 58 outcomes
    arc_intro(box=3.0, H=11.65, fname="fig_arc_intro_00dbd492_large.png", xin=0.45, xout=5.9, step=3.67)
    three_failures()
    three_causes_row()
    real_rule(box=3.7, H=9.3, fname="fig_real_rule_ka95aa62f67d9_large.png", xout=W - 0.25 - 3.7, label_right=True,
              xin=0.3)
    construction_58()
    skin_lesion()
    maize_tile()
    v2_uncertified()
    v2_uncertified(box=2.75, H=4.65, fname="fig_v2_uncertified_00dbd492_large.png", xout=3.45, xt=6.45, xin=0.3)
    dev60_audit()
    prov = {"script": "scripts/summit_visual_figures.py", "script_sha256": _sha(os.path.abspath(__file__)),
            "printed_width_in": W, "rule": "REAL figures come only from hash-pinned recorded inputs; ILLUSTRATIVE figures say so",
            "figures": {}}
    for name, meta in sorted(DRAWN.items()):
        meta["sha256"] = _sha(os.path.join(FIG, name))
        prov["figures"][name] = meta
    for p in (os.path.join(FIG, "PROVENANCE.json"),
              os.path.join(HERE, "docs", "summit_20261023_reframe", "POSTER_FIGURE_PROVENANCE.json")):
        json.dump(prov, open(p, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: v["kind"] for k, v in prov["figures"].items()}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
