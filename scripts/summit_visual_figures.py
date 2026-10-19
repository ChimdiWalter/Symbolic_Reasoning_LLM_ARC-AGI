"""Figures for the VISUAL-FIRST summit review poster and its explainer (2026-10-19).

  python scripts/summit_visual_figures.py
      -> docs/summit_20261023_reframe/figures/*.png
      -> docs/summit_20261023_reframe/figures/PROVENANCE.json and docs/summit_20261023_reframe/POSTER_FIGURE_PROVENANCE.json

**Real figures** are drawn ONLY from recorded, hash-pinned inputs. A sha256 mismatch stops the script before
anything is drawn. Real grids are drawn cell for cell with the standard ARC colours; nothing is edited.

**The one ILLUSTRATIVE figure** (four reasons an explanation can be inadequate) is drawn by hand for explanation. It
says so on its face, and it is never presented as a CORA result.

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
def arc_intro():
    w = json.load(open(src("v2_witness")))
    assert w["key"] == "00dbd492"
    H = 9.45
    fig = _new(H)
    _tag(fig, "REAL ARC-AGI-2 TRAINING TASK 00dbd492 (public)")
    box, xin, xout = 2.25, 0.85, 5.35
    rows = [("Training example 1", w["train"][0][0], w["train"][0][1]),
            ("Training example 2", w["train"][1][0], w["train"][1][1]),
            ("New input", w["test_input"], None)]
    for i, (name, gin, gout) in enumerate(rows):
        y = H - 0.62 - (i + 1) * 2.95 + 0.12
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
    _save(fig, "fig_arc_intro_00dbd492.png", "REAL", ("v2_witness",), "00dbd492",
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


# ---------------------------------------------------------------- column 2: the real constructed rule (REAL)
def real_rule():
    t = json.load(open(src("real_task")))
    w = json.load(open(src("real_witness")))
    assert w["committed"] == t["evaluator_answer"] and all(f["class"] == "SUCCESS" for f in w["folds"])
    assert w["rule"] == "if colours == (1,): ray(NW,border)[centre] else ray(SE,border)[centre]"
    assert w["controls"]["C2G_same_rule"] is True and not w["controls"]["A_frozen_native_certified"]
    H = 7.2
    fig = _new(H)
    _tag(fig, f"REAL ARC-AGI-2 TRAINING TASK {t['key']} · recorded run")
    box, xin, xout = 2.62, 0.85, 5.35
    rows = [("Training example", t["train"][0][0], t["train"][0][1], "target output"),
            ("New input", t["test_input"], w["committed"], "CORA's output ✓ correct")]
    for i, (name, gin, gout, olab) in enumerate(rows):
        y = H - 0.75 - (i + 1) * 3.20 + 0.30
        _text(fig, xin, y + box + 0.12, name, fontsize=FS_BIG, fontweight="bold")
        _text(fig, xout, y + box + 0.12, olab, fontsize=FS_MIN, color=GOOD if i else INK2,
              fontweight="bold" if i else "normal")
        _grid(fig, gin, xin, y, box)
        _arrow(fig, xin + box + 0.30, y + box / 2, xout - 0.30)
        _grid(fig, gout, xout, y, box)
    _save(fig, "fig_real_rule_ka95aa62f67d9.png", "REAL", ("real_task", "real_witness"), t["key"],
          "development probe (guard probe, arm EG), recorded run; evaluator answer read only in the evaluator step",
          "Exposed training task selected by the development autopsy; a failure-blind constructor found the same rule; "
          "not part of any Kaggle entry; not evidence of generalization.")


# ---------------------------------------------------------------- column 3: v2's correct but uncertified prediction (REAL)
def v2_uncertified():
    w = json.load(open(src("v2_witness")))
    assert w["evaluator_correct"] and w["tier_v2"] == "EXPLORATORY" and not any(w["controls"].values())
    H = 4.2
    fig = _new(H)
    _tag(fig, "REAL TASK 00dbd492 · CORA-v2 development run\nCORRECT DEVELOPMENT PREDICTION — NOT CERTIFIED", color=INK2)
    box, xin, xout, y = 2.30, 0.35, 3.20, 0.58
    _grid(fig, w["test_input"], xin, y, box)
    _arrow(fig, xin + box + 0.08, y + box / 2, xout - 0.08)
    _grid(fig, w["v2_prediction"], xout, y, box)
    _text(fig, xin + box / 2, y - 0.40, "new input", fontsize=FS_MIN, color=INK2, ha="center")
    _text(fig, xout + box / 2, y - 0.40, "v2's guess (correct)", fontsize=FS_MIN, color=INK2, ha="center")
    sup, tab = w["test_table_support"], w["size_to_colour"]
    xt, yt = 6.00, y + box + 0.05
    _text(fig, xt, yt, "fill colour, by size:", fontsize=FS_MIN, color=INK2, va="top")
    for j, k in enumerate(sorted(sup, key=int)):
        n = sup[k]
        _text(fig, xt, yt - 0.44 * (j + 1), f"{ARC_NAME[tab[k]]}: {n} example{'s' if n > 1 else ''}", fontsize=FS_MIN,
              color=CRITICAL if n == 1 else INK, fontweight="bold" if n == 1 else "normal", va="top")
    _text(fig, xt, yt - 0.44 * 4 - 0.10, "hide that example:", fontsize=FS_MIN, color=CRITICAL, va="top")
    _text(fig, xt, yt - 0.44 * 5 - 0.10, "the check fails", fontsize=FS_MIN, color=CRITICAL, va="top", fontweight="bold")
    _save(fig, "fig_v2_uncertified_00dbd492_poster.png", "REAL", ("v2_witness",), "00dbd492",
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
    v2_uncertified()
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
