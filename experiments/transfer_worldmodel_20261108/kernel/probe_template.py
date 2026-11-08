"""T4 world-model probe, collection kernel (private Kaggle CPU kernel; development games only).

The kernel:
1. builds an isolated Python 3.12 environment in /tmp;
2. installs the MIT toolkit and engine (arc-agi 0.9.9, arcengine 0.9.3);
3. lists the public ARC-AGI-3 games through the toolkit's anonymous route, with logging silenced so that no key is
   ever printed;
4. splits the games by the hash rule fixed in DESIGN_NOTE.md (the salt is the design-note commit);
5. records random-action transitions for the DEVELOPMENT games only.

Version 2 adds the analysis stage: the study's own code (wm/*.py, embedded below by kernel/build.py) runs the five
arms on the development items inside the kernel, so every number is tied to this kernel's slug and version.
It writes only data (npz arrays and JSON summaries) to /kaggle/working/t4_out. Game code stays in /tmp. Before
exiting, every output file is checked for the key string. No competition data source is attached, no rules are
accepted and nothing is submitted.
"""
import os
import re
import subprocess
import sys
import textwrap

SALT = "989cb0ca9c21811144356d83955cae5ca76ec6c6"
MODE = "dev"          # "dev": collect and analyse development games; "held": held games (only after the GO)
OUT = "/kaggle/working/t4_out"
VENV = "/tmp/t4venv"

WM_SOURCES = {}

ANALYSIS = textwrap.dedent(r'''
import json, os, sys, time
sys.path.insert(0, "/tmp/t4work")
from multiprocessing import Pool
from math import comb
from wm import arc3


def r0(it):
    return (it["game"], it["episode"]), arc3.rank0_of(it)


ITEM_LIMIT = 300      # wall seconds per item; an item over the limit is dropped from every arm (reported)


class Slow(Exception):
    pass


def _alarm(*_):
    raise Slow()


def one(args):
    import signal
    it, partner = args
    t = time.process_time()
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(ITEM_LIMIT)
    try:
        r = arc3.item_row(it, partner)
    except Slow:
        r = {"game": it["game"], "episode": it["episode"], "timeout": True}
    finally:
        signal.alarm(0)
    r["cpu_item"] = round(time.process_time() - t, 2)
    return r


def sign_p(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


if __name__ == "__main__":
    OUT = sys.argv[1]
    t0 = time.time()
    items = arc3.load_items(OUT)
    live = [it for it in items if "excluded" not in it]
    with Pool(4) as p:
        rank0 = dict(p.map(r0, live))
    games = sorted({it["game"] for it in live})
    with Pool(4) as p:
        allrows = p.map(one, [(it, arc3.partner_ranking(it, games, rank0)) for it in live])
    rows = [r for r in allrows if not r.get("timeout")]
    keys = [k for k in rows[0]["grown"] if k != "flags"] if rows else []
    summ = {"label": ("development probe" if sys.argv[2] == "dev" else "held run") + " on public ARC-AGI-3 games; not a score",
            "mode": sys.argv[2], "items": len(rows),
            "excluded": [(it["game"], it["episode"], it["excluded"]) for it in items if "excluded" in it],
            "arms": {a: {k: sum(r[a][k] for r in rows) for k in keys} for a in arc3.ARMS},
            "per_game": {g: {a: {k: sum(r[a][k] for r in rows if r["game"] == g) for k in ("n", "exact", "changed", "changed_ok")}
                             for a in arc3.ARMS} for g in games},
            "timeouts": [(r["game"], r["episode"]) for r in allrows if r.get("timeout")],
            "cpu_seconds_items": round(sum(r["cpu_item"] for r in allrows), 1), "wall_seconds": round(time.time() - t0, 1)}
    import numpy as np
    rng = np.random.default_rng(0)
    gl = sorted({r["game"] for r in rows})
    for x, y in (("grown", "static"), ("grown", "shuffled"), ("grown", "tabular"), ("grown", "copy_previous")):
        fx = [f for r in rows for f in r[x]["flags"]]
        fy = [f for r in rows for f in r[y]["flags"]]
        b = sum(1 for u, v in zip(fx, fy) if u and not v)
        c = sum(1 for u, v in zip(fx, fy) if v and not u)
        per = {g: (sum(sum(r[x]["flags"]) for r in rows if r["game"] == g), sum(sum(r[y]["flags"]) for r in rows if r["game"] == g),
                   sum(r[x]["n"] for r in rows if r["game"] == g)) for g in gl}
        boots = []
        for _ in range(10000):
            pick = rng.integers(len(gl), size=len(gl))
            ex = sum(per[gl[i]][0] for i in pick); ey = sum(per[gl[i]][1] for i in pick); nn = sum(per[gl[i]][2] for i in pick)
            boots.append((ex - ey) / nn if nn else 0.0)
        n_all = len(fx)
        summ[f"transitions_{x}_vs_{y}"] = {"rate_" + x: round(sum(fx) / n_all, 4), "rate_" + y: round(sum(fy) / n_all, 4),
                                           "difference": round((sum(fx) - sum(fy)) / n_all, 4),
                                           "ci95_game_bootstrap": [round(float(np.percentile(boots, 2.5)), 4),
                                                                   round(float(np.percentile(boots, 97.5)), 4)],
                                           "only_" + x: b, "only_" + y: c, "exact_mcnemar_p": sign_p(b, c),
                                           "transitions": n_all, "games": len(gl)}
    for x, y in (("grown", "static"), ("grown", "shuffled"), ("grown", "tabular"), ("grown", "copy_previous"),
                 ("static", "copy_previous")):
        for k in ("exact", "changed_ok"):
            b = sum(r[x][k] > r[y][k] for r in rows)
            c = sum(r[y][k] > r[x][k] for r in rows)
            summ[f"{x}_vs_{y}_{k}"] = {"items_" + x + "_higher": b, "items_" + y + "_higher": c, "sign_test_p": sign_p(b, c)}
    with open(os.path.join(OUT, "analysis.json"), "w") as fh:
        json.dump({"summary": summ, "rows": rows}, fh, indent=1, default=str)
    print(json.dumps({"items": summ["items"], "timeouts": summ["timeouts"], "excluded": summ["excluded"],
                      "arms": summ["arms"], "cpu_seconds_items": summ["cpu_seconds_items"],
                      "wall_seconds": summ["wall_seconds"]}))
    for k, v in summ.items():
        if "_vs_" in k:
            print(k, v)
    for g, v in summ["per_game"].items():
        print(g, {a: (v[a]["exact"], v[a]["n"], v[a]["changed_ok"], v[a]["changed"]) for a in arc3.ARMS})
''')

COLLECT = textwrap.dedent(r'''
import hashlib, json, logging, os, sys, time, platform
logging.disable(logging.CRITICAL)
import numpy as np
SALT, OUT = sys.argv[1], sys.argv[2]
E, L = 6, 80
os.makedirs(OUT, exist_ok=True)
t0 = time.process_time()
silent = logging.getLogger("t4_silent")
silent.handlers.clear()
silent.addHandler(logging.NullHandler())
silent.setLevel(logging.CRITICAL + 10)
silent.propagate = False
import arc_agi
from arc_agi import OperationMode
from arcengine import GameAction
from importlib.metadata import version as pkgver
arc = arc_agi.Arcade(operation_mode=OperationMode.NORMAL, environments_dir="/tmp/t4_envs",
                     recordings_dir="/tmp/t4_rec", logger=silent)
KEY = str(getattr(arc, "arc_api_key", "") or "")
full = {}
for e in arc.available_environments:
    full.setdefault(e.game_id.split("-")[0], e.game_id)
order = sorted(full, key=lambda g: hashlib.sha256((SALT + "|" + g).encode()).hexdigest())
n = len(order)
held, dev = order[: n // 2], order[n // 2:]
summary = {"label": "probe on public ARC-AGI-3 games; not a score", "salt": SALT,
           "python": platform.python_version(), "arc_agi": pkgver("arc-agi"), "arcengine": pkgver("arcengine"),
           "n_games": n, "order_by_hash": order, "held_games": held, "dev_games": dev,
           "dev_full_ids": {g: full[g] for g in dev}, "episodes": {}, "errors": []}
MODE = sys.argv[3]
summary["mode"] = MODE
for g in (dev if MODE == "dev" else held):
    gseed = int(hashlib.sha256(g.encode()).hexdigest()[:8], 16)
    for ep in range(E):
        rec = {"length": 0, "end": None}
        try:
            try:
                env = arc.make(full[g], seed=ep)
            except TypeError:
                env = arc.make(full[g])
            fd = env.reset() if env is not None else None
            if fd is None or not len(fd.frame):
                rec["end"] = "no_reset_frame"
                summary["episodes"][f"{g}_e{ep}"] = rec
                continue
            rng = np.random.default_rng([ep, gseed])
            frames = [np.asarray(fd.frame[-1], dtype=np.uint8)]
            states, levels, acts, nfr, avails = [str(fd.state.value)], [int(fd.levels_completed)], [], [], []
            for t in range(L):
                avail = sorted(int(a) for a in fd.available_actions if int(a) != 0)
                avails.append(avail)
                if not avail:
                    rec["end"] = "no_actions"
                    break
                a = avail[int(rng.integers(len(avail)))]
                x = y = -1
                data = {}
                if a == 6:
                    cur = frames[-1]
                    if rng.random() < 0.5:
                        y, x = (int(v) for v in rng.integers(64, size=2))
                    else:
                        vals, cnt = np.unique(cur, return_counts=True)
                        ys, xs = np.nonzero(cur != vals[np.argmax(cnt)])
                        if len(ys):
                            i = int(rng.integers(len(ys)))
                            y, x = int(ys[i]), int(xs[i])
                        else:
                            y, x = (int(v) for v in rng.integers(64, size=2))
                    data = {"x": x, "y": y}
                fd2 = env.step(GameAction.from_id(a), data=data)
                if fd2 is None or not len(fd2.frame):
                    rec["end"] = "step_failed"
                    break
                frames.append(np.asarray(fd2.frame[-1], dtype=np.uint8))
                acts.append((a, x, y))
                nfr.append(len(fd2.frame))
                states.append(str(fd2.state.value))
                levels.append(int(fd2.levels_completed))
                fd = fd2
                if states[-1] in ("GAME_OVER", "WIN"):
                    rec["end"] = states[-1]
                    break
            rec["length"] = len(acts)
            rec["end"] = rec["end"] or "max_steps"
            rec["actions_available_union"] = sorted({a for s in avails for a in s})
            np.savez_compressed(os.path.join(OUT, f"{g}_e{ep}.npz"), frames=np.stack(frames),
                                actions=np.array(acts, dtype=np.int16).reshape(-1, 3),
                                nframes=np.array(nfr, dtype=np.int16), states=np.array(states),
                                levels=np.array(levels, dtype=np.int16))
        except Exception as ex:
            rec["end"] = "error"
            summary["errors"].append(f"{g}_e{ep}: {type(ex).__name__}: {str(ex)[:200]}")
        summary["episodes"][f"{g}_e{ep}"] = rec
summary["cpu_seconds_collect"] = round(time.process_time() - t0, 1)
with open(os.path.join(OUT, "summary.json"), "w") as fh:
    json.dump(summary, fh, indent=1)
redacted = 0
if KEY:
    for root, _, files in os.walk(os.path.dirname(OUT)):
        for f in files:
            p = os.path.join(root, f)
            b = open(p, "rb").read()
            if KEY.encode() in b:
                open(p, "wb").write(b.replace(KEY.encode(), b"REDACTED"))
                redacted += 1
print("key-scan:", "clean" if redacted == 0 else f"redacted {redacted} files")
print("games:", n, "held:", held, "dev:", dev)
print("episodes:", {k: (v["length"], v["end"]) for k, v in summary["episodes"].items()})
print("errors:", len(summary["errors"]), "cpu_s:", summary["cpu_seconds_collect"])
''')


def scrub(text):
    """Belt and braces: hide any long key-like token before anything from a child process is printed."""
    return re.sub(r"[A-Za-z0-9_-]{24,}", "[token hidden]", text)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("FAILED:", " ".join(cmd[:5]), scrub(r.stderr[-800:]))
        sys.exit(1)
    return r


run([sys.executable, "-m", "pip", "install", "-q", "uv"])
run([sys.executable, "-m", "uv", "venv", VENV, "--python", "3.12"])
run([sys.executable, "-m", "uv", "pip", "install", "--python", f"{VENV}/bin/python", "-q", "arc-agi==0.9.9",
     "arcengine==0.9.3", "numpy"])
os.makedirs("/tmp/t4work", exist_ok=True)
with open("/tmp/t4work/collect.py", "w") as fh:
    fh.write(COLLECT)
r = subprocess.run([f"{VENV}/bin/python", "-I", "/tmp/t4work/collect.py", SALT, OUT, MODE], cwd="/tmp/t4work",
                   capture_output=True, text=True)
print(scrub(r.stdout[-6000:]))
print("collector exit code:", r.returncode)
if r.returncode != 0:
    print("collector stderr tail, scrubbed:", scrub(r.stderr[-1500:]))
if r.returncode == 0 and WM_SOURCES:
    os.makedirs("/tmp/t4work/wm", exist_ok=True)
    for name, src in WM_SOURCES.items():
        with open(f"/tmp/t4work/wm/{name}", "w") as fh:
            fh.write(src)
    with open("/tmp/t4work/analysis.py", "w") as fh:
        fh.write(ANALYSIS)
    a = subprocess.run([f"{VENV}/bin/python", "-I", "/tmp/t4work/analysis.py", OUT, MODE], cwd="/tmp/t4work",
                       capture_output=True, text=True)
    print(scrub(a.stdout[-8000:]))
    print("analysis exit code:", a.returncode)
    if a.returncode != 0:
        print("analysis stderr tail:", scrub(a.stderr[-2500:]))
print("working dir contents:", sorted(os.listdir("/kaggle/working")))
