"""DEVELOPMENT what-if: re-run only the adaptive-LOO folds of construction arms whose top-level run native accepted
and that used the extension, under CORA_FHR_FOLD_GATE=ungated (proposed Amendment 2). Never a counted result.

  CORA_FHR_FOLD_GATE=ungated python -m cora_fhr.refold [--workers 4]
      -> outputs/cora_fhr/rows_<corpus>_refold_ungated.jsonl (same row format; evaluate with --tag _refold_ungated)
"""
import argparse
import copy
import json
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")


def job(args):
    key, row, view, donor_view = args
    import numpy as np
    from cora_fhr import measure as M
    from cora_funnel import run as FR
    FR.cpu_clock()
    from cora_pilot import native as N
    from cora_fhr import ggrow as GG
    assert M.FOLD_GATE == "ungated"
    base = os.path.join(OUT, "engines_refold", key)
    dirs = {a: N.prepare_object_dir(os.path.join(base, a)) for a in ("extract", "loo")}
    train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in view["train"]]
    donor_raw = None
    new = copy.deepcopy(row)
    a_cert = row["arms"]["A"]["certified"]
    for arm in ("C", "C2", "D", "E"):
        r = new["arms"].get(arm)
        if not r or not (r.get("top") or {}).get("accepted") or not (r.get("top") or {}).get("uses"):
            continue
        if r.get("outcome") == "ABSTAIN_TIE":
            continue
        if arm == "D" and donor_raw is None:
            dtrain = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in donor_view["train"]]
            donor_raw, _ = M.authentic_raw(dtrain, N.prepare_object_dir(os.path.join(base, "donor")))
        ext = GG.make(GG.from_str(r["proposals"][0]["expr"]))
        r["folds"] = M.loo(arm, key, train, ext, dirs, donor_raw)
        ok = all(f["class"] == "SUCCESS" for f in r["folds"])
        r["outcome"] = "CERTIFIED_WITH_EXTENSION" if ok else "LOO_FAILURE"
        r["committed"], r["certified_by"] = ((r["top"]["predictions"], f"{arm}+extension") if ok and not a_cert
                                             else ((row["arms"]["A"]["committed"], "A") if a_cert else (None, None)))
        r["fold_gate"] = "ungated"
    return new


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--corpus", default="c4_dev")
    a = ap.parse_args(argv)
    from cora_fhr.measure import load_corpus
    views = dict(load_corpus(a.corpus))
    rows = [json.loads(l) for l in open(os.path.join(OUT, f"rows_{a.corpus}.jsonl"))]
    todo = [(r["key"], r, views[r["key"]], views[r["donor"]]) for r in rows]
    path = os.path.join(OUT, f"rows_{a.corpus}_refold_ungated.jsonl")
    t0 = time.time()
    with mp.get_context("fork").Pool(a.workers, maxtasksperchild=1) as pool, open(path, "w") as fh:
        for i, row in enumerate(pool.imap_unordered(job, todo), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {row['key']} {({x: v.get('outcome') for x, v in row['arms'].items() if x != 'A'})} "
                  f"elapsed={time.time() - t0:.0f}s", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
