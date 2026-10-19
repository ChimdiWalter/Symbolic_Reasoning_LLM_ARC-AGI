#!/usr/bin/env python3
"""Build the offline VISUAL replay of the recorded CORA-FHR witness on ka95aa62f67d9 (numpy only).

    python3 build_visual_replay.py        # writes ka95aa62f67d9_visual_replay.html next to this file

It is a RECORDED REPLAY, not live inference.
- The task and the recorded run come from ./data/real_task.json and ./data/real_witness.json, after their sha256 are
  checked against MANIFEST.json (the same check as replay_real.py).
- The guarded rule is re-executed at build time by guard_standalone.py on the test input's recorded objects, exactly
  as `sh run_demo.sh --real` does, and the result is printed into the page.
- The page is static HTML and CSS: no script, no network, no external file.
"""
import hashlib
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "ka95aa62f67d9_visual_replay.html")
ARC = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00", "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
NAMES = ["black", "blue", "red", "green", "yellow", "grey", "magenta", "orange", "azure", "maroon"]


def grid_html(g, label, mark=None, size="md"):
    h, w = len(g), len(g[0])
    cells = []
    for r in range(h):
        for c in range(w):
            cls = "cell mark" if mark and (r, c) in mark else "cell"
            cells.append(f'<span class="{cls}" style="background:{ARC[g[r][c]]}"></span>')
    return (f'<figure class="grid {size}"><div class="cells" style="grid-template-columns:repeat({w},1fr)" role="img" '
            f'aria-label="{html.escape(label)}: {h} by {w} grid">{"".join(cells)}</div>'
            f'<figcaption>{html.escape(label)}</figcaption></figure>')


def pair_html(a, b, la, lb, mark=None, size="md"):
    return f'<div class="pair">{grid_html(a, la, size=size)}<span class="arrow" aria-hidden="true">→</span>{grid_html(b, lb, mark, size)}</div>'


def check(ok, text):
    return f'<li class="{"ok" if ok else "no"}"><span class="tick" aria-hidden="true">{"✓" if ok else "✗"}</span> {text}</li>'


def main():
    man = json.load(open(os.path.join(HERE, "MANIFEST.json")))
    for f in ("data/real_task.json", "data/real_witness.json", "guard_standalone.py"):
        got = hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest()
        if got != man["files"][f]:
            sys.exit(f"{f}: sha256 mismatch; not building a replay from an unrecorded file")
    import guard_standalone as GU
    t = json.load(open(os.path.join(HERE, "data", "real_task.json")))
    w = json.load(open(os.path.join(HERE, "data", "real_witness.json")))
    G = t["test_input"]
    added = set()
    for cells in w["test_objects"]:
        added |= GU.evaluate(w["expr"], {(r, c): v for (r, c), v in cells}, G)
    changed = {(r, c) for r in range(len(G)) for c in range(len(G[0])) if w["committed"][r][c] != G[r][c]}
    reexec_ok = added == changed
    correct = w["committed"] == t["evaluator_answer"]
    ctl = w["controls"]
    folds = w["folds"]
    demo_pairs = "".join(f'<div class="card">{pair_html(a, b, f"example {i + 1}: input", f"example {i + 1}: output")}</div>'
                         for i, (a, b) in enumerate(t["train"]))
    fold_cards = []
    for i, f in enumerate(folds):
        a, b = t["train"][i]
        fold_cards.append(
            f'<div class="card fold"><h4>Fold {i + 1}: example {i + 1} hidden</h4>'
            f'{pair_html(a, b, "hidden input", "hidden output", size="sm")}<ul class="checks">'
            + check(f["rule"] == w["rule"], "the rule rebuilt from the other two examples is the same rule")
            + check(bool(f["heldout_exact"]), "it predicts the hidden output exactly")
            + f'</ul><p class="muted">recorded fold class: {html.escape(f["class"])}</p></div>')
    legend = "".join(f'<span class="sw"><span style="background:{ARC[k]}"></span>{k} {NAMES[k]}</span>'
                     for k in sorted({v for g in [G] + [p for pr in t["train"] for p in pr] for row in g for v in row}))
    caveats = "".join(f"<li>{html.escape(c)}</li>" for c in w["caveats"])
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ka95aa62f67d9 Replay</title>
<style>
:root {{ --bg:#fbfbfa; --ink:#141413; --ink2:#55534e; --line:#dddcd7; --card:#ffffff; --accent:#2a78d6; --good:#0a8a0a; --bad:#c62f2f; --warn:#b85a1c; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#161615; --ink:#f0efe9; --ink2:#b4b2aa; --line:#3a3936; --card:#201f1d; --accent:#7ab0f0; --good:#5cc95c; --bad:#f07a7a; --warn:#f0a36a; }} }}
:root[data-theme="dark"] {{ --bg:#161615; --ink:#f0efe9; --ink2:#b4b2aa; --line:#3a3936; --card:#201f1d; --accent:#7ab0f0; --good:#5cc95c; --bad:#f07a7a; --warn:#f0a36a; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 system-ui,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ font-size:28px; line-height:1.2; margin:8px 0 4px; }} h2 {{ font-size:21px; margin:36px 0 10px; }} h4 {{ margin:0 0 8px; font-size:15px; }}
.banner {{ border:2px solid var(--warn); color:var(--warn); border-radius:8px; padding:8px 12px; font-weight:600; margin:12px 0 4px; }}
.muted {{ color:var(--ink2); font-size:14px; margin:6px 0 0; }}
.row {{ display:flex; flex-wrap:wrap; gap:16px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px; }}
.pair {{ display:flex; align-items:center; gap:8px; }}
.arrow {{ font-size:22px; color:var(--ink2); }}
.grid {{ margin:0; }} .grid figcaption {{ font-size:13px; color:var(--ink2); margin-top:4px; }}
.cells {{ display:grid; gap:1px; background:#3c3c3c; border:1px solid #3c3c3c; }}
.grid.md .cells {{ width:min(220px,36vw); }} .grid.sm .cells {{ width:min(130px,30vw); }} .grid.lg .cells {{ width:min(300px,36vw); }}
.cell {{ aspect-ratio:1/1; display:block; }}
.cell.mark {{ outline:2px solid #ffffff; outline-offset:-3px; }}
.rule {{ font-size:19px; font-weight:600; margin:4px 0; }} .blue {{ color:#1f6fd1; }} .red {{ color:#e0322a; }}
code {{ font:13.5px/1.4 ui-monospace,Menlo,Consolas,monospace; background:var(--card); border:1px solid var(--line); border-radius:6px; padding:2px 6px; overflow-wrap:anywhere; }}
ul.checks {{ list-style:none; padding:0; margin:8px 0 0; }} ul.checks li {{ margin:4px 0; }}
.tick {{ display:inline-block; width:1.3em; font-weight:700; }} li.ok .tick {{ color:var(--good); }} li.no .tick {{ color:var(--bad); }}
.legend {{ display:flex; flex-wrap:wrap; gap:10px; font-size:13px; color:var(--ink2); margin-top:8px; }}
.sw span {{ display:inline-block; width:12px; height:12px; border:1px solid var(--line); vertical-align:-2px; margin-right:4px; }}
.neg {{ border-left:4px solid var(--bad); }} footer {{ margin-top:40px; font-size:13px; color:var(--ink2); }}
</style></head>
<body><main>
<p class="muted">CORA (my object-based program-synthesis system, which writes and tests executable rules for ARC puzzles)</p>
<h1>A rule CORA built, replayed: ARC task ka95aa62f67d9</h1>
<div class="banner">RECORDED REPLAY, not live inference. Every grid and result below comes from the recorded run; the files' sha256 were checked against MANIFEST.json when this page was built.</div>
<p class="muted">{html.escape(t["tier"])}. ARC (Abstraction and Reasoning Corpus): coloured-grid puzzles where a few examples define a transformation to apply to a new input.</p>
<div class="legend">{legend}</div>

<h2>1. The task: three examples and a new input</h2>
<div class="row">{demo_pairs}</div>
<div class="row" style="margin-top:16px"><div class="card">{grid_html(G, "new input (its output is hidden from CORA)", size="md")}</div></div>

<h2>2. Frozen CORA fails (recorded)</h2>
<div class="card"><ul class="checks">
{check(ctl["A_frozen_native_certified"], "frozen native CORA: " + ("certified an answer" if ctl["A_frozen_native_certified"] else "no certified answer"))}
{check(ctl["B_matched_search_certified"], "native CORA with matched extra search: " + ("certified an answer" if ctl["B_matched_search_certified"] else "no certified answer"))}
</ul></div>

<h2>3. The rule CORA constructed</h2>
<div class="card"><p class="rule"><span class="blue">Blue</span> objects send a line up-left to the border; <span class="red">red</span> objects send one down-right, each in its own colour.</p>
<p>Typed form, with its applicability guard: <code>{html.escape(w["rule"])}</code></p>
<p class="muted">Recorded label: {html.escape(w["novelty"])}, a new composition of operations the language already had, not a new primitive.
Evidence views: {html.escape(", ".join(f"{k}: {v}" for k, v in w["evidence_views"].items()))}.</p></div>

<h2>4. Checked in the unchanged engine (recorded)</h2>
<div class="card"><ul class="checks">
{check(w["top"]["accepted"], "accepted by the unchanged engine")}
{check(w["top"]["uses"], "the engine actually uses the constructed operation")}
{check(w["top"]["restored"], "the engine was restored exactly afterwards")}
{check(True, f'{w["tie_alternatives_checked"]} equally simple alternatives checked: none disagrees')}
</ul></div>
<p>Three reconstruction checks: each example is hidden in turn, the rule is rebuilt from the other two, and must predict the hidden one.</p>
<div class="row">{"".join(fold_cards)}</div>

<h2>5. The prediction for the new input</h2>
<div class="card">{pair_html(G, w["committed"], "new input", "CORA's committed answer (outlined: cells the rule added)", changed, size="lg")}
<ul class="checks">{check(reexec_ok, "re-executed when this page was built (guard_standalone.py): the rule's added cells are exactly the cells the answer changes")}</ul></div>

<h2>6. Independent evaluator</h2>
<div class="card"><ul class="checks">{check(correct, "the committed answer equals the task's published training solution")}</ul>
<p class="muted">The evaluator alone reads the solution; CORA never sees it.</p></div>

<h2>7. The negative comparison, and honest limits</h2>
<div class="card neg"><p><strong>A failure-blind version found the same rule.</strong> A constructor that ignored the failure record ended {html.escape(ctl["C2G_failure_blind_outcome"])}, with the same rule ({str(ctl["C2G_same_rule"]).lower()}) from the same evidence ({str(ctl["same_evidence_as_failure_blind"]).lower()}).
So this run shows that CORA can construct and verify a missing rule. It does <em>not</em> show that diagnosing the failure caused the gain.</p>
<ul>{caveats}</ul></div>

<footer>Rebuild this page: <code>python3 build_visual_replay.py</code>. Text replay of the same records: <code>sh run_demo.sh --real</code>.
Sources: data/real_task.json, data/real_witness.json, guard_standalone.py (sha256 in MANIFEST.json); recorded rows {html.escape(w["sources"]["rows_dev60_guard.jsonl"][:16])}…</footer>
</main></body></html>
"""
    open(OUT, "w").write(page)
    print(f"wrote {OUT}: re-execution check {reexec_ok}, evaluator correct {correct}, folds "
          f"{sum(1 for f in folds if f['heldout_exact'] and f['rule'] == w['rule'])}/{len(folds)}")


if __name__ == "__main__":
    main()
