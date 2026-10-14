"""End-to-end audit of one development capability-growth witness (DEVELOPMENT, SYNTHETIC).

  python -m cora_fhr.witness --key dev_D3_04 [--corpus c4_dev_v2]  -> outputs/cora_fhr/witness_<key>.json

1. Deterministic reproduction. A fresh engine directory; arms A, C, C' and E rerun; compared with the logged
   row (outcome, operator, fold classes, committed prediction).
2. Replay. Inside the installed overlay, the accepted program JSON is executed directly on every
   demonstration and on the test input. It must reproduce the demonstrations and equal the engine's own
   test prediction.
3. Ablation. The same task without the extension is arm A.
4. Novelty on perturbed geometry. On randomly generated objects, beyond the task's instances, it is checked
   whether a native growth mode (native detect_grow) or one cora_reach setting reproduces the operator's added
   cells. The operator is semantically available if one baseline operator matches on all perturbed objects.
5. Evaluator. The committed prediction is scored against the hidden test output; only this step reads it.
6. Provenance: git HEAD, the corpus sha, the grammar identity and the row's hash.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_fhr")


def perturbation_novelty(expr, n=300, seed=7):
    from cora_fhr import baseline as BL
    from cora_fhr import ggrow as GG
    from cora_reach import construct as CN
    from cora_reach import relations as REL
    rng = np.random.default_rng(seed)
    settings = list(REL.settings(CN.GRAMMAR))
    reach_hits = np.zeros(len(settings), dtype=int)
    native_hits, used = 0, 0
    for _ in range(n * 4):
        if used >= n:
            break
        H, W = (int(v) for v in rng.integers(9, 15, size=2))
        G = np.zeros((H, W), int)
        k = int(rng.integers(2, 7))
        cells = {(int(rng.integers(2, H - 2)), int(rng.integers(2, W - 2)))}
        while len(cells) < k:
            r, c = list(cells)[int(rng.integers(len(cells)))]
            dr, dc = ((-1, 0), (1, 0), (0, -1), (0, 1))[int(rng.integers(4))]
            if 1 <= r + dr < H - 1 and 1 <= c + dc < W - 1:
                cells.add((r + dr, c + dc))
        c1, c2 = (int(v) for v in rng.choice(np.arange(1, 10), 2, replace=False))
        O = {p: c1 for p in cells}
        O[sorted(cells)[int(rng.integers(len(cells)))]] = c2
        for p, v in O.items():
            G[p] = v
        A = GG.evaluate(expr, GG.Ctx(O, G))
        if not A:
            continue
        used += 1
        native_hits += BL.native_explains(O, A, 5, G)
        for i, (fam, params) in enumerate(settings):
            reach_hits[i] += REL.apply(fam, params, set(O), G) == A
    best = int(reach_hits.argmax()) if len(settings) else None
    return {"objects": used, "native_explains": int(native_hits),
            "best_reach_setting": {"setting": settings[best], "matches": int(reach_hits[best])} if best is not None else None,
            "semantically_available": bool(used and (native_hits == used or (best is not None and reach_hits[best] == used)))}


def job(args):
    key, corpus = args
    from cora_funnel import run as FR
    FR.cpu_clock()
    from cora_pilot import native as N
    from cora_fhr import bridge as BR
    from cora_fhr import ggrow as GG
    from cora_fhr import measure as M
    view = dict(M.load_corpus(corpus))[key]
    base = os.path.join(OUT, "engines_witness", key)
    dirs = {a: N.prepare_object_dir(os.path.join(base, a)) for a in ("A", "B", "C", "C2", "D", "E", "extract", "loo")}
    fresh = M.run_task(key, view, ("C", "C2", "E"), dirs, None, 1.0)
    train = [(np.asarray(p["input"], dtype=int), np.asarray(p["output"], dtype=int)) for p in view["train"]]
    tests = [np.asarray(p["input"], dtype=int) for p in view["test"]]
    replay = {}
    E = fresh["arms"]["E"]
    if E.get("outcome") == "CERTIFIED_WITH_EXTENSION":
        ext = GG.make(GG.from_str(E["proposals"][0]["expr"]))
        run, program = M.object_run(key + "_replay", train, tests, dirs["E"], ext=ext)
        import geocat_arc.object_reasoning.actions as AC
        from geocat_arc.object_reasoning.types import program_from_dict
        with BR.installed(ext):
            fn = AC.program_apply_fn(program_from_dict(json.loads(json.dumps(program))))
            demo_ok = [np.asarray(fn(a)).tolist() == b.tolist() for a, b in train]
            test_pred = [np.asarray(fn(t)).tolist() for t in tests]
        replay = {"program_sha": run["program_sha"], "replays_every_demonstration": all(demo_ok), "per_demo": demo_ok,
                  "direct_test_equals_engine": test_pred == run["predictions"], "restored": BR.restored(),
                  "uses_extension": run.get("uses"), "program_json": program}
    return fresh, replay


def main(argv=None):
    import multiprocessing as mp
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="dev_D3_04")
    ap.add_argument("--corpus", default="c4_dev_v2")
    a = ap.parse_args(argv)
    logged = next(json.loads(l) for l in open(os.path.join(OUT, f"rows_{a.corpus}.jsonl")) if json.loads(l)["key"] == a.key)
    with mp.get_context("fork").Pool(1, maxtasksperchild=1) as pool:
        fresh, replay = pool.apply(job, ((a.key, a.corpus),))
    from cora_fhr import ggrow as GG
    sel = logged["arms"]["E"]["proposals"][0]["expr"] if logged["arms"]["E"].get("proposals") else None
    nov = perturbation_novelty(GG.from_str(sel)) if sel else None

    def summary(r):
        return {arm: {"outcome": x.get("outcome") or ("certified" if x.get("certified") else None),
                      "operator": (x.get("selected") or {}).get("pretty"),
                      "folds": [f.get("class") for f in x.get("folds") or []],
                      "committed": x.get("committed")} for arm, x in r["arms"].items()}
    s_log, s_new = summary(logged), summary(fresh)
    corpus = json.load(open(os.path.join(OUT, f"{a.corpus}.json")))["tasks"][a.key]
    answer = [b for _a, b in corpus["test"]]                         # evaluator step: the only read of the answer
    out = {"key": a.key, "corpus": a.corpus, "tier": "DEVELOPMENT, SYNTHETIC", "truth_pretty": corpus["truth_pretty"],
           "reproduced": {arm: s_log.get(arm) == s_new.get(arm) for arm in s_new if arm in s_log},
           "logged": s_log, "fresh": s_new, "replay": replay, "perturbation_novelty": nov,
           "ablation": {"without_extension_certified": logged["arms"]["A"]["certified"]},
           "evaluator": {arm: (x.get("committed") == answer) if x.get("committed") else None for arm, x in fresh["arms"].items()},
           "provenance": {"git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip(),
                          "corpus_sha256": hashlib.sha256(open(os.path.join(OUT, f"{a.corpus}.json"), "rb").read()).hexdigest(),
                          "grammar_identity": GG.grammar_identity(),
                          "logged_row_sha256": hashlib.sha256(json.dumps(logged, sort_keys=True).encode()).hexdigest()}}
    json.dump(out, open(os.path.join(OUT, f"witness_{a.key}.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("key", "reproduced", "evaluator", "perturbation_novelty", "ablation")}, indent=1))
    print("replay:", {k: v for k, v in replay.items() if k != "program_json"})


if __name__ == "__main__":
    main()
