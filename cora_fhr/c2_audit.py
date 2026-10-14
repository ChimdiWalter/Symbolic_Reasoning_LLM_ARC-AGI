"""DEVELOPMENT audit of the E-versus-C' confound.

  python -m cora_fhr.c2_audit --corpus c4_dev_v2   -> outputs/cora_fhr/c2_audit_<corpus>.json

One identity-frame native induction per task records every growth correspondence with native's mode. From that
single observation:
- arm E's evidence is the subset whose mode is `pattern` (memorized);
- arm C''s evidence is all of them.

E carries information beyond native's correspondence only on tasks where native explains some growth and
memorizes the rest.
"""
import argparse
import collections
import json
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")


def job(args):
    key, view, fam = args
    os.nice(19)
    import numpy as np
    from cora_funnel import run as FR
    FR.cpu_clock()
    from cora_pilot import native as N
    from cora_fhr import construct as CS
    from cora_fhr.measure import cpu_cap, _Cap, EXTRACT_CAP_S, BUDGET_S
    train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in view["train"]]
    try:
        with cpu_cap(EXTRACT_CAP_S):
            raw = CS.native_all_records(train, N.prepare_object_dir(os.path.join(OUT, "engines_c2audit", key)), BUDGET_S)
    except _Cap:
        return {"key": key, "family": fam, "error": "extract_cap"}
    modes = collections.Counter(r.get("native_mode") for r in raw)
    return {"key": key, "family": fam, "growth_correspondences": len(raw), "modes": dict(modes),
            "pattern": modes.get("pattern", 0), "E_equals_Cprime": len(raw) == modes.get("pattern", 0)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="c4_dev_v2")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args(argv)
    from cora_fhr.measure import load_corpus
    d = json.load(open(os.path.join(OUT, f"{a.corpus}.json")))["tasks"]
    todo = [(k, v, d[k]["family"]) for k, v in load_corpus(a.corpus)]
    with mp.get_context("fork").Pool(a.workers, maxtasksperchild=1) as pool:
        rows = list(pool.imap_unordered(job, todo))
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[r["family"]]["tasks"] += 1
        by[r["family"]]["with_growth"] += bool(r.get("growth_correspondences"))
        by[r["family"]]["E_equals_Cprime"] += bool(r.get("E_equals_Cprime") and r.get("growth_correspondences"))
        by[r["family"]]["mixed_native_and_memorized"] += bool(r.get("pattern") and r.get("growth_correspondences", 0) > r.get("pattern", 0))
    out = {"corpus": a.corpus, "tier": "DEVELOPMENT", "by_family": {k: dict(v) for k, v in sorted(by.items())},
           "tasks": sorted(rows, key=lambda r: r["key"])}
    json.dump(out, open(os.path.join(OUT, f"c2_audit_{a.corpus}.json"), "w"), indent=1)
    print(json.dumps(out["by_family"], indent=1))


if __name__ == "__main__":
    main()
