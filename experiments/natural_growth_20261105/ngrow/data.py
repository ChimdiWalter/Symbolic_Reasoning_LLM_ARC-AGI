"""Benchmarks, families and the source/held split of the natural-task growth test.

Data: the prepared files of the public ARC-style benchmarks downloaded for the universality study
(`experiments/universality_similar_problems_20261102/DATA_MANIFEST.json` holds their provenance and sha256):
`<DATA>/<benchmark>/real.json` (demonstrations and test inputs, what the system sees) and `meta.json` (original
file path and group). Test outputs live in `solutions_scorer_only/solutions.json` and are read only by the scorer
(`score.py`), never by a search.

Family: a 1D-ARC task type or a ConceptARC concept (the folder the authors put the task in); Mini-ARC has no
groups and is one pool. Split: within each family, tasks are ordered by sha256(SALT|benchmark|original file path);
the first floor(n/2) form the SOURCE half, the rest the HELD half (the held half takes the extra task of an odd
family). The split uses task identities only; it was written before any search ran on any task.
"""
import hashlib
import json
import os

from ngrow import env as E

BENCHMARKS = ("concept_arc", "mini_arc", "1d_arc")
SALT = "natural-growth-20261105|split"
SPLIT_PATH = os.path.join(E.STUDY, "split", "SPLIT.json")


def _load(bench, name):
    with open(os.path.join(E.DATA, bench, name), encoding="utf-8") as f:
        return json.load(f)


def family_of(bench, meta_row):
    return meta_row["group"] if meta_row["group"] is not None else bench


def split_key(bench, meta_row):
    return hashlib.sha256(f"{SALT}|{bench}|{meta_row['file']}".encode()).hexdigest()


def make_split():
    out = {"salt": SALT, "rule": "within each family: order by sha256(salt|benchmark|file); first floor(n/2) = "
                                 "source, the rest = held", "benchmarks": {}}
    for b in BENCHMARKS:
        meta = _load(b, "meta.json")
        fams = {}
        for tid, m in meta.items():
            fams.setdefault(family_of(b, m), []).append(tid)
        rows = {}
        for f, ids in sorted(fams.items()):
            ids = sorted(ids, key=lambda t: split_key(b, meta[t]))
            k = len(ids) // 2
            rows[f] = {"source": sorted(ids[:k]), "held": sorted(ids[k:])}
        out["benchmarks"][b] = {
            "families": rows,
            "n_source": sum(len(r["source"]) for r in rows.values()),
            "n_held": sum(len(r["held"]) for r in rows.values()),
            "n_source_outputs": sum(meta[t]["n_test"] for r in rows.values() for t in r["source"]),
            "n_held_outputs": sum(meta[t]["n_test"] for r in rows.values() for t in r["held"]),
            "meta_sha256": E.sha_file(os.path.join(E.DATA, b, "meta.json")),
            "real_sha256": E.sha_file(os.path.join(E.DATA, b, "real.json"))}
    return out


def split():
    return E.load(SPLIT_PATH)


def half(name, benches=BENCHMARKS):
    """[(benchmark, family, task id)] of one half, in a fixed order (benchmark, family, id)."""
    sp = split()
    return [(b, f, t) for b in benches for f, r in sorted(sp["benchmarks"][b]["families"].items()) for t in r[name]]


def tasks(bench):
    """System view of every task of a benchmark: demonstrations and test inputs as tuple grids."""
    real = _load(bench, "real.json")
    return {tid: {"train": [(grid(p["input"]), grid(p["output"])) for p in t["train"]],
                  "test_inputs": [grid(p["input"]) for p in t["test"]]} for tid, t in real.items()}


def grid(g):
    return tuple(tuple(r) for r in g)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["write"]:
        if os.path.exists(SPLIT_PATH):
            raise SystemExit("split exists; it is never rewritten")
        sp = make_split()
        E.dump(SPLIT_PATH, sp)
        print(json.dumps({b: {k: v for k, v in r.items() if k.startswith("n_")} for b, r in sp["benchmarks"].items()}))
        print(E.sha_file(SPLIT_PATH))
