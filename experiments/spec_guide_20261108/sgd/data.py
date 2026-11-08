"""Development data: generated tasks (cheap and traced) and the natural source units, with their family splits.

Natural units: the 425 source units of the earlier tests (their stored holes and block traces, pass 1 of the
learned search-order test), split by benchmark family: int(sha256("spec-natural:" + family)[:8], 16) % 5 == 0 is
validation; Mini-ARC (one family) is split by task id with the same rule.
"""
import gzip
import hashlib
import json
import math
import os

from sgd import env as E
from sgd import net as NT

GC_PASS1 = os.path.join(E.GC_STUDY, "dev", "pass1")


def h8(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


def natural_split(bench, family, task):
    key = task if bench == "mini_arc" else family
    return "val" if h8("spec-natural:" + key) % 5 == 0 else "train"


def grid(g):
    return tuple(tuple(int(v) for v in r) for r in g)


def read_jsonl_gz(path):
    with gzip.open(E.check_read(path), "rt", encoding="utf-8") as f:
        for x in f:
            if x.strip():
                yield json.loads(x)


def natural_holes():
    """[{bench, task, family, split, rank, pairs, hole (the pass 1 record)}] for every source unit's holes."""
    from objgrow import env as OE
    recs = {}
    for b in ("concept_arc", "mini_arc", "1d_arc"):
        recs[b] = OE.controller_records(b)
    out = []
    for fn in sorted(os.listdir(GC_PASS1)):
        if not (fn.startswith("units.") and fn.endswith(".jsonl")):
            continue
        with open(os.path.join(GC_PASS1, fn), encoding="utf-8") as f:
            for x in f:
                if not x.strip():
                    continue
                r = json.loads(x)
                sks = recs[r["bench"]][r["task"]]["record"]["sketches"]
                sp = natural_split(r["bench"], r["family"], r["task"])
                for h in r["holes"]:
                    sk = sks[h["rank"]]
                    pairs = [(grid(a), grid(c)) for a, c in sk["pairs"]]
                    out.append({"bench": r["bench"], "task": r["task"], "family": r["family"], "split": sp,
                                "rank": h["rank"], "pairs": pairs, "hole": h})
    return out


def block_good(tb, pk_true=None):
    """A traced block's label: it yielded a verified multi-pair candidate ("success"); with pk_true (generated
    training tasks only, whose test output the generator made), one whose test prediction is the true output
    ("correct")."""
    if pk_true is None:
        return any(c["loo"] for c in tb["cands"])
    return any(c["loo"] and c["pk"] == pk_true for c in tb["cands"])


def success_keys(hole, pk_true=None):
    """The block keys whose trace yielded a verified multi-pair candidate (or, with pk_true, a correct one)."""
    keys = {tuple(b["block"]): tuple(b["key"]) for b in hole["blocks"]}
    out = set()
    for t in hole["trace"]["blocks"]:
        if block_good(t, pk_true):
            out.add(keys[tuple(t["block"])])
    return out


def key_targets(keys):
    v = [0.0] * len(NT.KEYS)
    for k in keys:
        i = NT.KEY_INDEX.get(tuple(k))
        if i is not None:
            v[i] = 1.0
    return v


def edit_view_targets(keys):
    """Multi-label edit and view targets from successful keys (S keys give the edit; W keys count as crop)."""
    ev = [0.0] * len(NT.EDITS)
    vv = [0.0] * len(NT.VIEWS)
    for k in keys:
        if k[0] == "S" and k[2] in NT.EDITS:
            ev[NT.EDITS.index(k[2])] = 1.0
        if k[0] == "W":
            ev[NT.EDITS.index("crop")] = 1.0
        if k[0] in ("S", "W"):
            vv[NT.VIEWS.index(k[1])] = 1.0
    return ev, vv
