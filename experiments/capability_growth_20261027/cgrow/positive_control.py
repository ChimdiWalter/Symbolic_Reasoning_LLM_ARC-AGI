"""Positive control (EVALUATOR SIDE): hand-written, correct gridfn-1 implementations of the four removed
capabilities go through exactly the system-side episode path (parse, allowlist and substrate check, self-tests,
novelty, retry, regression, validation, promotion) on each family's first motivating task, then through the
evaluator's scoring (E reuse, reference agreement, kind). They are HAND_WRITTEN controls: they show whether the
pipeline can accept a correct capability at all; they are never counted as inventions.

    python -m cgrow.positive_control RUN_ID PREP_ID
"""
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cgrow import paths as P, experiment as X, episode as EP, evaluate as EV, invent as IV   # noqa: E402

HEAD = "OBSERVATION: control\nLEVEL: operation\nNAME: control\nPARAMS: {params}\n"
CODES = {
    "compress": ("none", '''def new_op(grid):
    h, w = shape(grid)
    rows = [i for i in range(h) if len(set(grid[i])) > 1]
    cols = [j for j in range(w) if len(set(grid[i][j] for i in range(h))) > 1]
    return [[grid[i][j] for j in cols] for i in rows]
'''),
    "trim": ("none", '''def new_op(grid):
    h, w = shape(grid)
    return [list(grid[i][1:w - 1]) for i in range(1, h - 1)]
'''),
    "downscale": ("n: int 2..3", '''def new_op(grid, n):
    h, w = shape(grid)
    return [[grid[i][j] for j in range(0, w, n)] for i in range(0, h, n)]
'''),
    "upscale": ("n: int 2..3", '''def new_op(grid, n):
    out = []
    for row in grid:
        r = []
        for v in row:
            r.extend([v] * n)
        for _ in range(n):
            out.append(list(r))
    return out
'''),
}


def main(run_id, prep_id):
    ev = X.eval_tasks()
    rem = X.load_json(os.path.join(P.EVALUATOR_DIR, "REMOVED.json"))
    sys_t = X.system_tasks()
    g0b = X.G0Builder()
    with open(os.path.join(P.RUNS, prep_id, "records.pkl"), "rb") as f:
        recs = pickle.load(f)
    solved = {t: X.as_task(sys_t[t]) for t, r in recs.items() if r["status"] == "solved"}
    base_preds = {t: recs[t]["base_preds"][0] for t in solved}
    unsolved = sorted([t for t, r in recs.items() if r["status"] != "solved"], key=lambda i: X.h("pool:" + i))
    e_ids = sorted(i for i, t in ev.items() if t["partition"] == "E")
    out = {}
    for fam, (params, code) in CODES.items():
        text = HEAD.format(params=params) + "```python\n" + code + "```"
        mts = sorted([i for i, t in ev.items() if t["family"] == fam and t["partition"] == "M"
                      and recs[i]["decision"] == "INVENT_NEW_OPERATION"], key=lambda i: (ev[i]["template"], X.h(i)))
        tid = mts[0]
        pool = [(i, X.as_task(sys_t[i])) for i in unsolved if i != tid]
        res, promoted, fitting = EP.process(f"PC_{fam}", [{"text": text, "gen_tokens": 0, "finished": True}],
                                            X.as_task(sys_t[tid]), g0b, solved, pool, base_preds, {})
        row = res["rows"][0]
        rec = {"family": fam, "task": tid, "stage": row.get("stage"), "outcome": row.get("outcome"),
               "message": row.get("message"), "novelty": row.get("novelty"), "retry_program": (row.get("retry") or {})
               .get("program"), "recovered": bool(row.get("retry")) and EV.correct(row["retry"]["preds"],
                                                                                 ev[tid]["test_outputs"]),
               "promotion": row.get("promotion")}
        if row.get("outcome") == "fits_motivating_task":
            prop = IV.parse(text)
            rec["score"] = EV.score_op(prop, IV.SandboxOp(prop), ev, e_ids, fam, rem, g0b, transfer=False)
            rec["score"].pop("e", None)
        out[fam] = rec
        print(json.dumps({k: v for k, v in rec.items() if k != "score"} | {"score": {k: rec.get("score", {}).get(k)
              for k in ("e_correct_same_family", "ref_agreement", "kind")}}, default=list), flush=True)
    with P.open_write(os.path.join(P.RUNS, run_id, "positive_control.json")) as f:
        json.dump(out, f, indent=1, default=list)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
