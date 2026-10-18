"""Poster figures for the ARC Prize Research Summit (and the paper), drawn
ONLY from recorded outputs whose sha256 is checked before anything is drawn
(no generated pictures).

  python scripts/summit_figures.py   -> docs/summit_poster/figures/*.png + PROVENANCE.json

Printed size: every figure is 9.50 in wide, the measured text width of one
poster block (686.8 pt), and is placed at that width, so a 22 pt label prints
at 22 pt on the A0 sheet. Text: 20 pt minimum, 22 pt labels, 24 pt values.
The top line of each figure states its evidence tier and its denominator.
Palette: the dataviz reference palette (validated blue/orange pair, neutral,
status good/critical used only for outcomes and always labelled); ARC grids
use the standard ARC colours, which are the data itself.
"""
import hashlib
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle     # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(HERE, "docs", "summit_poster", "figures")
W, DPI = 9.50, 200
FS_MIN, FS_LAB, FS_VAL = 20, 22, 24
INK, INK2, MUTED, GRID, BASE, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE, ORANGE, NEUTRAL = "#2a78d6", "#eb6834", "#f0efec"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
ARC = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00", "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": FS_LAB, "axes.edgecolor": BASE,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK, "xtick.labelsize": FS_MIN,
                     "ytick.labelsize": FS_LAB, "figure.facecolor": SURF, "axes.facecolor": SURF,
                     "savefig.facecolor": SURF})

#: Every input, pinned. A mismatch stops the script before anything is drawn.
SOURCES = {
    "v19_report": ("outputs/tti/v19_prospective_report.json",
                   "987ab9ea074ac82bf72cc70ac109168534c61693e813656e83880783c4ddaf6c"),
    "v19_rows": ("outputs/tti/v19_prospective_rows.jsonl",
                 "aad86def227a6c50e4d1c7e0e7e2819654385c40286e35102004bcf0985e8e48"),
    "funnel": ("outputs/reach_v1/measure_funnel.json",
               "77fbac13cbe2150ce007c5df85ff05c8ca40dbe674f3a63c18538c1510ae55a1"),
    "dev_bundle": ("records/pilot_v1/dev_bundle.json",
                   "6eb7323652115ab88d4a9013d3b2bd073661136fa429eeb7bbc97125a4702180"),
    "eligibility": ("outputs/loo_v1/probe_eligibility.json",
                    "922151e2bd4a527adc10a616eb373f29bd16f1ed134503beb5e54fae5682ae02"),
    "probe_kf89": ("outputs/loo_v1/probe_kf892487f1049.json",
                   "9bdff08ad451030d0c3247c59a6d6b1cd6bd6b7bf478448a3882da2666585828"),
    "diagnose_rows": ("outputs/loo_v1/diagnose_rows.jsonl",
                      "31ddf9af1db3c7224e42f61fd20b9c787c31b429465ba0bbec9bc7780eec60b6"),
    "negative": ("outputs/loo_v1/probe_negative.json",
                 "2f1003509235d3f397385172ed77d44b488572c1fd732a4d7669108d41ca1687"),
    "funnel_dev60": ("outputs/funnel_v0/eval_dev60_native.json",
                     "3fb8c0e3b3f896668cf718db820878a86c5252b95e77d6c8e14069245fd6f595"),
    "c4_dev_v2": ("outputs/cora_fhr/c4_dev_v2.json", "d5bab8e40f55af1926e3bd98ea59b7999ca54fe3a6c261da0aa9032da5533653"),
    "fhr_witness": ("docs/summit_demo_20261023/data/witness.json", "ab525368012278b85fb1bd3d19aef4d249ae6e2363546b837382e799c76f30a0"),
    "real_task": ("docs/summit_demo_20261023/data/real_task.json", "b06073a7fd35d203875e673aaec4b550d0069cdc43631afd2cafdb9d3b362f45"),
    "real_witness": ("docs/summit_demo_20261023/data/real_witness.json", "f0da3a8df23bbab61b9a39360480651bebda765ec302ede1b2d842a1a190b73f"),
}
USED, DRAWN = {}, {}


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def src(name):
    rel, want = SOURCES[name]
    got = _sha(os.path.join(HERE, rel))
    if got != want:
        raise SystemExit(f"{rel}: sha256 {got} != pinned {want}; not drawing from an unrecorded input")
    USED[name] = {"path": rel, "sha256": got}
    return os.path.join(HERE, rel)


def _new(h):
    return plt.figure(figsize=(W, h), dpi=DPI)


def _tag(fig, text):
    """Evidence tier and denominator, top left, 20 pt."""
    fig.text(0.10 / W, 1 - 0.12 / fig.get_figheight(), text, ha="left", va="top", fontsize=FS_MIN, color=INK2,
             linespacing=1.25)


def _ax(fig, left_in, bottom_in, width_in, height_in):
    H = fig.get_figheight()
    return fig.add_axes((left_in / W, bottom_in / H, width_in / W, height_in / H))


def _box(fig, x_in, y_in, w_in, h_in, **kw):
    H = fig.get_figheight()
    fig.patches.append(Rectangle((x_in / W, y_in / H), w_in / W, h_in / H, transform=fig.transFigure, **kw))


def _text(fig, x_in, y_in, s, **kw):
    fig.text(x_in / W, y_in / fig.get_figheight(), s, **kw)


def _bar(ax, y, w, color, height=0.6):
    """A thin horizontal bar, square at the baseline, rounded at the data end."""
    if w <= 0:
        return
    r = min(0.12 * height, w / 2)
    ax.add_patch(FancyBboxPatch((0, y - height / 2), w, height, boxstyle=f"round,pad=0,rounding_size={r}",
                                linewidth=0, facecolor=color, mutation_aspect=1))
    ax.add_patch(Rectangle((0, y - height / 2), min(w, 2 * r), height, linewidth=0, facecolor=color))


def _clean(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.tick_params(axis="y", length=0, pad=10)
    ax.tick_params(axis="x", length=4, color=BASE)
    ax.grid(axis="x", color=GRID, linewidth=1.0)
    ax.set_axisbelow(True)


def _save(fig, name, sources):
    fig.savefig(os.path.join(FIG, name), dpi=DPI, metadata={"Software": None})
    h = fig.get_figheight()
    DRAWN[name] = {"width_in": W, "height_in": round(h, 3), "printed_cm": [round(W * 2.54, 1), round(h * 2.54, 1)],
                   "dpi": DPI, "pixels": [int(round(W * DPI)), int(round(h * DPI))], "min_font_pt": FS_MIN,
                   "sources": {k: USED[k] for k in sources}}
    plt.close(fig)


def synthetic():
    rep = json.load(open(src("v19_report")))
    n = sum(1 for line in open(src("v19_rows")) if line.strip())
    g = rep["gates"]["G2_witnesses_new"]
    rows = [("repaired engine K*′", g["complete"], BLUE), ("earlier engine K*", g["complete_old"], BASE)]
    fig = _new(3.6)
    _tag(fig, f"SYNTHETIC · frozen v1.9 test, run once · n = {n} tasks")
    ax = _ax(fig, 3.25, 0.95, 6.0, 1.75)
    for i, (name, v, c) in enumerate(rows):
        y = 1 - i
        _bar(ax, y, v, c)
        ax.text(v + 0.5, y, f"{v} / {n}", va="center", ha="left", color=INK, fontsize=FS_VAL, fontweight="bold",
                zorder=5, bbox=dict(facecolor=SURF, edgecolor="none", pad=2))
    req = g["required"]
    ax.axvline(req, color=INK2, linewidth=1.6, linestyle=(0, (4, 3)), zorder=1)
    ax.text(req, 1.6, f"pre-registered pass line: {req}", ha="center", va="bottom", fontsize=FS_MIN, color=INK2)
    ax.set_yticks([1, 0])
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlim(0, n + 7)
    ax.set_xticks([0, 10, 20, 30])
    ax.set_ylim(-0.55, 1.55)
    ax.set_xlabel("tasks with a complete end-to-end witness", fontsize=FS_MIN, labelpad=6)
    _clean(ax)
    _save(fig, "fig_synthetic_v19.png", ("v19_report", "v19_rows"))


def funnel():
    f = json.load(open(src("funnel")))["funnel"]
    assert f["E_compilation"] == f["F_installation"], "compiled and installed differ: draw them apart"
    stages = [("development tasks", 60), ("native engine fails", f["A_native_baseline_failure"]),
              ("usable failure evidence", f["B_usable_failure_evidence"]), ("repair proposed", f["C_proposal"]),
              ("compiled and installed", f["F_installation"]), ("accepted and used", f["H_uses_extension"]),
              ("passes adaptive LOO", f["K_adaptive_loo"]), ("activated", f["N_activation"])]
    fig = _new(6.3)
    _tag(fig, "REAL DEVELOPMENT · 60 ARC-AGI-2 training tasks\nrun once · no test output read")
    ax = _ax(fig, 3.8, 0.95, 5.5, 4.55)
    for i, (name, v) in enumerate(stages):
        y = len(stages) - 1 - i
        _bar(ax, y, v, BLUE)
        label = str(v) + ("  (0 of 14 folds)" if name == "passes adaptive LOO" else "")
        ax.text(v + 1.2, y, label, va="center", ha="left", color=INK, fontsize=FS_VAL, fontweight="bold")
    ax.set_yticks(range(len(stages)))
    ax.set_yticklabels([s for s, _ in stages][::-1])
    ax.set_xlim(0, 75)
    ax.set_ylim(-0.6, len(stages) - 0.4)
    ax.set_xticks([0, 20, 40, 60])
    ax.set_xlabel("tasks (of 60)", fontsize=FS_MIN, labelpad=6)
    _clean(ax)
    _save(fig, "fig_funnel_reach_v1.png", ("funnel",))


def demos(key="kf892487f1049"):
    t = json.load(open(src("dev_bundle")))["tasks"][key]
    n = len(t["train"])
    cell, H_fig, left = 0.165, 5.35, 1.45
    fig = _new(H_fig)
    _tag(fig, f"REAL DEVELOPMENT · task {key} (opaque key)\n"
              f"its {n} training demonstrations only; no test grid shown")
    col_w = (W - left) / n
    for i, p in enumerate(t["train"]):
        for g, y0 in ((p["input"], 2.3), (p["output"], 0.15)):
            H, Wg = len(g), len(g[0])
            ax = _ax(fig, left + i * col_w + (col_w - Wg * cell) / 2, y0 + (1.8 - H * cell) / 2, Wg * cell, H * cell)
            for r in range(H):
                for c in range(Wg):
                    ax.add_patch(Rectangle((c, H - 1 - r), 1, 1, facecolor=ARC[g[r][c]], edgecolor="#555555",
                                           linewidth=0.4))
            ax.set_xlim(0, Wg)
            ax.set_ylim(0, H)
            ax.axis("off")
        _text(fig, left + i * col_w + col_w / 2, 4.2, f"demo {i}", ha="center", va="bottom", fontsize=FS_LAB, color=INK)
    for label, y in (("input", 3.2), ("output", 1.05)):
        _text(fig, 0.12, y, label, ha="left", va="center", fontsize=FS_LAB, color=INK)
    _save(fig, "fig_kf89_training_demonstrations.png", ("dev_bundle",))


def admission(key="kf892487f1049"):
    el = json.load(open(src("eligibility")))
    pr = json.load(open(src("probe_kf89")))
    order = el["trial_order"]
    subsets = el["tasks"][key]["subsets"]
    names = ["0123", "012", "013", "023", "123", "01", "02", "03", "12", "13", "23"]
    g_found = {"0123": "G"}
    g_found.update({p: ("G" if r["engine"].get("top_is_G") else "no G") for p, r in pr["pairs"].items()})
    rows = {}
    for line in open(src("diagnose_rows")):           # outer folds: the top-level program of the rebuilt run
        if line.strip():
            r = json.loads(line)
            rows[r["key"]] = r
    g_sha = rows[f"{key}:full"]["A_E_WALL"]["program"]["sha"]
    for i in range(4):
        ind = rows[f"{key}:f{i}"]["B_WALL"]["engine"]["trace"]["inductions"][0]
        top = (ind.get("program") or (ind.get("near_solve") or {}).get("partial") or {}).get("sha")
        rest = "".join(str(j) for j in range(4) if j != i)
        g_found[rest] = "G" if top == g_sha else "G*"
    H_fig = 8.6
    fig = _new(H_fig)
    _tag(fig, f"FORENSIC · task {key} · 11 subsets, chosen\n"
              "after the failure was seen (causal debugging)")
    ax = _ax(fig, 2.45, 2.05, 6.85, 5.25)
    for i, s in enumerate(names):
        y = len(names) - 1 - i
        rec = {v["variant"]: v for v in subsets[s]["variants"]}
        for j, v in enumerate(order):
            x = rec[v]
            col = BLUE if x["searched"] else (ORANGE if x["coherent"] else NEUTRAL)
            ax.add_patch(Rectangle((j + 0.05, y + 0.07), 0.9, 0.86, facecolor=col, linewidth=0))
            if v == "S6" and s in g_found:
                ax.text(j + 0.5, y + 0.5, g_found[s], ha="center", va="center", fontsize=FS_MIN,
                        color="white" if col != NEUTRAL else INK, fontweight="bold")
    ax.set_xlim(0, len(order))
    ax.set_ylim(0, len(names))
    ax.set_xticks([j + 0.5 for j in range(len(order))])
    ax.set_xticklabels(order, fontsize=FS_LAB)
    ax.xaxis.tick_top()
    ax.set_yticks([len(names) - 1 - i + 0.5 for i in range(len(names))])
    ax.set_yticklabels([("all 4 (full)" if s == "0123" else "demos " + " ".join(s)) for s in names], fontsize=FS_MIN)
    for lab, s in zip(ax.get_yticklabels(), names):
        if s in ("02", "13"):
            lab.set_fontweight("bold")
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    _text(fig, 2.30, 7.55, "trial order \u2192", ha="right", va="center", fontsize=FS_MIN, color=INK2)
    _text(fig, 0.10, 1.55, "G: the full-data one-rule program", ha="left", va="center", fontsize=FS_MIN, color=INK2)
    _text(fig, 0.10, 1.13, "G*: the same rule, with that fold's window_fill", ha="left", va="center", fontsize=FS_MIN,
          color=INK2)
    for x0, col, lab in ((0.10, BLUE, "searched"), (2.15, ORANGE, "eligible, cut by the cap"),
                         (6.55, NEUTRAL, "not eligible")):
        _box(fig, x0, 0.32, 0.36, 0.30, facecolor=col, linewidth=1.0, edgecolor=col if col != NEUTRAL else BASE)
        _text(fig, x0 + 0.48, 0.47, lab, ha="left", va="center", fontsize=FS_MIN, color=INK)
    _save(fig, "fig_kf89_variant_admission.png", ("eligibility", "probe_kf89", "diagnose_rows"))


def negative():
    d = json.load(open(src("negative")))
    order = ["S1", "S2", "S3", "S5", "S4", "S6", "S7"]
    res = {(r["task"], r["condition"], r["variant"]): r["outcome"] for r in d["results"]}
    fams = d["families"]
    family_label = {"recolor_by_size": "recolour\nby size", "halo": "halo", "bbox_fill_L": "bbox fill\n(L shapes)",
                    "translate_down": "translate\ndown", "multicolor_majority": "multicolour\nmajority",
                    "same_color_sizes": "same colour\nsizes"}
    word = {"CORRECT": "correct", "FALSE_ACCEPT": "false acc.", "REJECT": "rejected"}
    fill = {"CORRECT": GOOD, "FALSE_ACCEPT": CRITICAL, "REJECT": BASE}
    n_tasks = len(fams) * 4
    runs = sum(1 for r in d["results"] if r["condition"] != "BASE")
    row_h, gap, H_fig = 0.31, 0.07, 11.1
    top = H_fig - 1.55
    fig = _new(H_fig)
    _tag(fig, f"SYNTHETIC negative controls · {n_tasks} tasks, 6 families\n"
              "3 training + 2 held-out demonstrations per task\n"
              f"{runs} runs (up to 7 per task, correlated) vs native")
    harmed, gained = set(), set()
    x_fam, x_seed, x_base, x_var, cw = 0.10, 1.90, 2.32, 4.08, 0.76
    for fi, fam in enumerate(fams):
        for s in range(4):
            t = f"{fam}_{s}"
            y = top - (fi * 4 + s + 1) * row_h - fi * gap
            b0 = res[(t, "BASE", None)]
            _box(fig, x_base, y + 0.03, 1.62, row_h - 0.06, facecolor=fill[b0], linewidth=0)
            _text(fig, x_base + 0.81, y + row_h / 2, word[b0], ha="center", va="center", fontsize=FS_MIN,
                  color=INK if b0 == "REJECT" else "white")
            _text(fig, x_seed + 0.15, y + row_h / 2, str(s), ha="center", va="center", fontsize=FS_MIN, color=INK2)
            for j, v in enumerate(order):
                eligible = d["eligibility"][t][v]
                o = res[(t, "PROMOTE" if eligible else "ADMIT", v)]
                x = x_var + j * cw
                if o == b0:
                    _box(fig, x + 0.05, y + 0.04, cw - 0.10, row_h - 0.08, linewidth=1.3,
                         facecolor=NEUTRAL if eligible else SURF, edgecolor=NEUTRAL if eligible else BASE)
                else:
                    good = o == "CORRECT"
                    (gained if good else harmed).add(t)
                    _box(fig, x + 0.05, y + 0.04, cw - 0.10, row_h - 0.08, linewidth=0,
                         facecolor=GOOD if good else CRITICAL)
                    _text(fig, x + cw / 2, y + row_h / 2, {"CORRECT": "+", "FALSE_ACCEPT": "FA", "REJECT": "rej"}[o],
                          ha="center", va="center", fontsize=FS_MIN, color="white", fontweight="bold")
        _text(fig, x_fam, top - (fi * 4 + 2) * row_h - fi * gap, family_label[fam], ha="left", va="center",
              fontsize=FS_MIN, color=INK, linespacing=1.0)
    _text(fig, x_base + 0.81, top + 0.08, "native", ha="center", va="bottom", fontsize=FS_LAB, color=INK)
    _text(fig, x_seed + 0.15, top + 0.08, "seed", ha="center", va="bottom", fontsize=FS_MIN, color=INK2)
    for j, v in enumerate(order):
        _text(fig, x_var + j * cw + cw / 2, top + 0.08, v, ha="center", va="bottom", fontsize=FS_LAB, color=INK)
    legend = ((dict(facecolor=NEUTRAL, edgecolor=NEUTRAL), "eligible view forced first: unchanged"),
              (dict(facecolor=SURF, edgecolor=BASE), "ineligible view forced first and admitted: unchanged"),
              (dict(facecolor=CRITICAL, edgecolor=CRITICAL), "worse: rej = now rejected; FA = now a false acceptance"),
              (dict(facecolor=GOOD, edgecolor=GOOD), "changed to correct: none occurred"))
    for k, (style, lab) in enumerate(legend):
        y = 1.38 - k * 0.40
        _box(fig, 0.10, y - 0.14, 0.36, 0.28, linewidth=1.3, **style)
        _text(fig, 0.58, y, lab, ha="left", va="center", fontsize=FS_MIN, color=INK)
    assert not gained
    _save(fig, "fig_negative_controls.png", ("negative",))
    return {"tasks": n_tasks, "runs": runs, "tasks_harmed": len(harmed), "tasks_gained": len(gained)}


def failure_funnel_dev60():
    """Where the 60 development tasks end in the native object layer, and the committed answers with
    and without leave-one-out (records/CORA_FAILURE_FUNNEL_20261014.md)."""
    s = json.load(open(src("funnel_dev60")))["summary"]
    c = s["categories"]
    rows = [("certified, correct", c.get("CERTIFIED_CORRECT", 0), GOOD),
            ("certified, wrong", c.get("CERTIFIED_WRONG", 0), CRITICAL),
            ("correct, rejected by LOO", c.get("REJECTED_BUT_CORRECT", 0), BLUE),
            ("fits all demos, all wrong", c.get("FIT_BUT_ALL_WRONG", 0), BLUE),
            ("no program fits", c.get("NO_FIT_DEADLINE", 0) + c.get("NO_FIT_EXHAUSTED", 0), BLUE),
            ("native defect", c.get("NATIVE_ERROR", 0) + c.get("NO_SEARCH", 0), BASE)]
    n = s["tasks"]
    assert sum(v for _, v, _ in rows) == n == 60, "categories must partition the 60 tasks"
    fig = _new(7.6)
    _tag(fig, f"REAL DEVELOPMENT · {n} ARC-AGI-2 training tasks\n"
              "object layer · CPU-time budgets · evaluator-only answers")
    ax = _ax(fig, 4.05, 3.35, 5.25, 3.25)
    for i, (name, v, col) in enumerate(rows):
        y = len(rows) - 1 - i
        _bar(ax, y, v, col)
        ax.text(v + 0.8, y, str(v), va="center", ha="left", color=INK, fontsize=FS_VAL, fontweight="bold")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.set_xlim(0, 34)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xticks([0, 10, 20, 30])
    ax.set_xlabel("tasks (of 60)", fontsize=FS_MIN, labelpad=6)
    _clean(ax)
    # committed answers: with the native verifier, and the gate-off counterfactual (a measurement, not a policy)
    ok_on, bad_on = s["S6_correct"], s["incorrect_accepted"]
    ok_off, bad_off = s["gate_off_correct"], s["gate_off_wrong"]
    _text(fig, 0.10, 2.55, "committed answers", ha="left", va="center", fontsize=FS_LAB, color=INK, fontweight="bold")
    bx = _ax(fig, 4.05, 0.85, 5.25, 1.45)
    for y, (ok, bad) in ((1, (ok_on, bad_on)), (0, (ok_off, bad_off))):
        _bar(bx, y, ok + bad, CRITICAL if bad else GOOD, height=0.55)
        _bar(bx, y, ok, GOOD, height=0.55)
        if ok + bad + 12 <= 34:                                   # room outside: one label
            bx.text(ok + bad + 0.8, y, f"{ok} right · {bad} wrong", va="center", ha="left", color=INK,
                    fontsize=FS_VAL, fontweight="bold")
        else:                                                      # long bar: label each segment inside
            bx.text(ok / 2, y, str(ok), va="center", ha="center", color="white", fontsize=FS_VAL, fontweight="bold")
            bx.text(ok + bad / 2, y, f"{bad} wrong", va="center", ha="center", color="white", fontsize=FS_VAL,
                    fontweight="bold")
    bx.set_yticks([1, 0])
    bx.set_yticklabels(["with leave-one-out", "leave-one-out off"])
    bx.set_xlim(0, 34)
    bx.set_ylim(-0.55, 1.55)
    bx.set_xticks([0, 10, 20, 30])
    _clean(bx)
    _save(fig, "fig_failure_funnel_dev60.png", ("funnel_dev60",))


def _grid(fig, g, x0, y0, cell):
    H, Wg = len(g), len(g[0])
    ax = _ax(fig, x0, y0, Wg * cell, H * cell)
    for r in range(H):
        for c in range(Wg):
            ax.add_patch(Rectangle((c, H - 1 - r), 1, 1, facecolor=ARC[g[r][c]], edgecolor="#555555", linewidth=0.4))
    ax.set_xlim(0, Wg)
    ax.set_ylim(0, H)
    ax.axis("off")


def fhr_witness(key="dev_D3_04"):
    """The recorded CORA-FHR development witness: two demonstrations, the test input, and CORA's committed
    prediction (scored correct by the evaluator), from the pinned corpus and the pinned witness bundle."""
    t = json.load(open(src("c4_dev_v2")))["tasks"][key]
    w = json.load(open(src("fhr_witness")))
    assert w["key"] == key and w["evaluator"]["E"] is True
    cell = 0.155
    fig = _new(6.0)
    _tag(fig, f"SYNTHETIC DEVELOPMENT · task {key} · recorded run\n"
              f"operator {w['operator']['pretty']} · {w['operator']['novelty']}")
    cols = [(t["train"][0][0], t["train"][0][1], "demo 0"), (t["train"][1][0], t["train"][1][1], "demo 1"),
            (t["test"][0][0], w["committed"][0], "test")]
    for i, (gin, gout, name) in enumerate(cols):
        x = 0.35 + i * 3.1
        _grid(fig, gin, x, 2.85, cell)
        _grid(fig, gout, x, 0.55, cell)
        _text(fig, x + len(gin[0]) * cell / 2, 4.85, name, ha="center", va="bottom", fontsize=FS_LAB, color=INK)
    _text(fig, 0.35 + 2 * 3.1 + len(t["test"][0][0][0]) * cell, 0.15, "committed prediction: correct",
          ha="right", va="center", fontsize=FS_MIN, color=INK)
    for label, y in (("in", 3.8), ("out", 1.5)):
        _text(fig, 0.05, y, label, ha="left", va="center", fontsize=FS_MIN, color=INK2)
    _save(fig, "fig_fhr_witness_dev_D3_04.png", ("c4_dev_v2", "fhr_witness"))


def fhr_real_witness():
    """The recorded REAL-task witness (ka95aa62f67d9, an ARC-AGI-2 training task): two demonstrations, the test input
    and CORA's committed answer (scored correct by the evaluator), from the pinned demo bundle."""
    t = json.load(open(src("real_task")))
    w = json.load(open(src("real_witness")))
    assert w["committed"] == t["evaluator_answer"] and all(f["class"] == "SUCCESS" for f in w["folds"])
    cell = 0.155
    fig = _new(6.0)
    assert w["rule"] == "if colours == (1,): ray(NW,border)[centre] else ray(SE,border)[centre]"
    _tag(fig, f"REAL ARC-AGI-2 TRAINING TASK · {t['key']} · recorded run\n"
              "constructed rule: colour 1 → ray up-left · other → ray down-right")
    cols = [(t["train"][0][0], t["train"][0][1], "demo 0"), (t["train"][1][0], t["train"][1][1], "demo 1"),
            (t["test_input"], w["committed"], "test")]
    for i, (gin, gout, name) in enumerate(cols):
        x = 0.35 + i * 3.1
        _grid(fig, gin, x, 2.85, cell)
        _grid(fig, gout, x, 0.55, cell)
        _text(fig, x + len(gin[0]) * cell / 2, 4.85, name, ha="center", va="bottom", fontsize=FS_LAB, color=INK)
    _text(fig, 0.35 + 2 * 3.1 + len(t["test_input"][0]) * cell, 0.15, "committed answer: correct (failure-blind arm: same)",
          ha="right", va="center", fontsize=FS_MIN, color=INK)
    for label, y in (("in", 3.8), ("out", 1.5)):
        _text(fig, 0.05, y, label, ha="left", va="center", fontsize=FS_MIN, color=INK2)
    _save(fig, "fig_fhr_real_witness_ka95aa62f67d9.png", ("real_task", "real_witness"))


def main():
    os.makedirs(FIG, exist_ok=True)
    synthetic()
    funnel()
    demos()
    admission()
    neg = negative()
    failure_funnel_dev60()
    fhr_witness()
    fhr_real_witness()
    prov = {"script": "scripts/summit_figures.py", "script_sha256": _sha(os.path.abspath(__file__)),
            "printed_width_in": W, "block_text_width_pt": 686.80643, "negative_controls": neg, "figures": {}}
    for name, meta in sorted(DRAWN.items()):
        meta["sha256"] = _sha(os.path.join(FIG, name))
        prov["figures"][name] = meta
    with open(os.path.join(FIG, "PROVENANCE.json"), "w") as handle:
        json.dump(prov, handle, indent=1, sort_keys=True)
    print(json.dumps({"figures": sorted(DRAWN), "negative_controls": neg}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
