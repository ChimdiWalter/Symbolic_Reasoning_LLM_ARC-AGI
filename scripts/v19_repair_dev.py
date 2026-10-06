"""v1.9 repair K*-4: the DEVELOPMENT ablation (protocol section 15).

  worker <wid>     phase 1: per audited development task (the 30 of the
                   diagnosis prefix, same byte-identical e): C, D, E, the
                   clause-only runs, adaptive leave-one-out under K* and K*',
                   the false-acceptance control and the safety checks
  repeat <wid>     phase 2: C (FULL and same-e folds) again in a fresh process
  reset_claims     drop claims that produced no row (after an interruption)
  analyze          outputs/tti/v19_repair_dev_report.json

Development data only (seeds 870,000,000 + 100k). Never generates the
reserved prospective range.
"""
import base64
import collections
import fcntl
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_arc2026 import v18_proposer as P                        # noqa: E402
from cora_arc2026 import v19_audit as A                           # noqa: E402
from cora_arc2026 import v19_repair as R                          # noqa: E402

OUT = os.path.join(HERE, "outputs", "tti")
LOG = os.path.join(HERE, "logs", "v19")
CORPUS_FILE = os.path.join(OUT, "v19_dev_corpus.json")
DIAG_ROWS = os.path.join(OUT, "v19_dev_rows.jsonl")
ROWS = os.path.join(OUT, "v19_repair_dev_rows.jsonl")
ROWS2 = os.path.join(OUT, "v19_repair_dev_phase2_rows.jsonl")
REPORT = os.path.join(OUT, "v19_repair_dev_report.json")
LOCK = os.path.join(LOG, "repair_queue.lock")
CLAIMS = os.path.join(LOG, "repair_claims.json")
CLAIMS2 = os.path.join(LOG, "repair_claims2.json")
PREFIX = 30
BUDGET_3X = 24.0


def _lock():
    os.makedirs(LOG, exist_ok=True)
    fh = open(LOCK, "w")
    fcntl.flock(fh, fcntl.LOCK_EX)
    return fh


def append(path, row):
    fh = _lock()
    try:
        with open(path, "a") as out:
            out.write(json.dumps(row, default=str) + "\n")
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def read_rows(path):
    return [json.loads(line) for line in open(path)] if os.path.exists(path) else []


def claim(path, n):
    fh = _lock()
    try:
        claims = json.load(open(path)) if os.path.exists(path) else []
        for i in range(n):
            if i not in claims:
                claims.append(i)
                json.dump(claims, open(path, "w"))
                return i
        return None
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def ungrid(p):
    return (np.asarray(p[0], dtype=int), np.asarray(p[1], dtype=int))


def psha(program):
    return (hashlib.sha256(json.dumps(program, sort_keys=True, default=str).encode()).hexdigest()[:16]
            if program else None)


def tasks():
    corpus = json.load(open(CORPUS_FILE))["tasks"]
    diag = {r["index"]: r for r in read_rows(DIAG_ROWS)}
    out = []
    for i in range(PREFIX):
        r = diag[i]
        if r.get("status") != "AUDITED":
            continue
        out.append((corpus[i], r))
    return out


def summarize(run, held, prod=None, pairs=None):
    """Untraced run -> decisions plus the safety checks of section 15."""
    out = {"accepted": run["accepted"], "events": run["events"], "program_sha": psha(run["program"]),
           "seconds": run["seconds"], "heldout_exact": X.predict_exact(run, *held)}
    if prod is not None:
        out["uses"] = bool(run["accepted"] and X.uses_extension(run["program"], prod))
    if run["accepted"] and pairs is not None:
        out["replays_training"] = all(X.predict_exact(run, a, b) for a, b in pairs)
        d = run["program"]
        if d.get("program_class") == "computed_pattern":
            M, MI = X._meta()
            try:
                direct = M.evaluate(M.ast_from_json(d["ast"]), np.asarray(held[0]), MI.descriptors)
                out["direct_equals_engine"] = bool(np.array_equal(direct, run["apply_fn"](np.asarray(held[0]))))
            except Exception as exc:                          # noqa: BLE001
                out["direct_equals_engine"] = f"error {type(exc).__name__}"
    out["restored"] = R.restored()
    return out


def wrong_extension(train, held):
    """The first verified, deduplicated candidate in MDL order whose fitter
    prediction of the held-out pair is wrong (section 15)."""
    sem = P.Semantics(train)
    inp = P.build_input(train, sem)
    deadline = time.time() + P.LIMITS["wall_s"]
    verified = []
    for depth in P.LIMITS["depths"]:
        gen = P.propose(inp, depth, sem, deadline)
        verified = P.verify(gen["proposals"], sem, deadline)
        if verified:
            break
    for rank, c in enumerate(P.dedupe(verified, deadline)):
        pred = P._evaluate(c["fitted"], held[0])
        if pred is None or not np.array_equal(pred, held[1]):
            return rank, c
    return None, None


def process(task, diag):
    t0 = time.time()
    train = [ungrid(p) for p in task["train"]]
    held = ungrid(task["held"])
    prod = X.load(base64.b64decode(diag["production"]))
    row = {"index": task["index"], "seed": task["seed"], "family": task["family"],
           "category": diag["category"], "level": (diag["proposer"].get("selection") or {}).get("level"),
           "production_sha256": hashlib.sha256(X.serialize(prod)).hexdigest(), "pid": os.getpid(),
           "repair_identity": R.repair_identity()}
    folds = [([train[k] for k in range(7) if k != i], train[i]) for i in range(7)]
    #  C: K*' + e, FULL and the seven same-e folds (untraced, with the checks)
    row["C_full"] = summarize(R.run_reasoner(train, (prod,)), held, prod, train)
    row["C_folds"] = [summarize(R.run_reasoner(sub, (prod,)), h, prod, sub) for sub, h in folds]
    #  residual failures under K*': traced, for their codes
    resid = []
    for name, (pairs, h), res in [("FULL", (train, held), row["C_full"])] + \
            [(f"FOLD_{i}", folds[i], row["C_folds"][i]) for i in range(7)]:
        if not res["accepted"]:
            with R.repaired():
                tr = A.traced_run(pairs, prod, "WALL", h)
            resid.append({"run": name, "codes": (tr["reason"] or {}).get("codes"),
                          "folds": [(f["hold"], f["code"], f["mechanism"]["class"])
                                    for f in (tr["reason"] or {}).get("folds", [])]})
    row["C_residual"] = resid
    #  D and E: K*' without the extension
    row["D"] = summarize(R.run_reasoner(train, ()), held)
    row["E"] = summarize(R.run_reasoner(train, (), budget_s=BUDGET_3X), held)
    #  supplementary: clause-only on category A and R tasks
    if diag["category"] in ("A", "R"):
        for clause in ("fit", "rank"):
            row[f"C_{clause}_only"] = {
                "full": summarize(R.run_reasoner(train, (prod,), clauses=(clause,)), held, prod),
                "folds": [summarize(R.run_reasoner(sub, (prod,), clauses=(clause,)), h, prod)
                          for sub, h in folds]}
    #  adaptive leave-one-out: proposer, compiler, installation and reasoner per fold
    row["loo_old"] = P.real_loo(train)
    with R.repaired():
        row["loo_new"] = P.real_loo(train)
    for k in ("loo_old", "loo_new"):
        for f in row[k]["folds"]:
            f.pop("events", None)
    #  false-acceptance control
    rank, cw = wrong_extension(train, held)
    if cw is None:
        row["wrong"] = None
    else:
        pw = X.compile_extension(X.make_input(cw["schema"]))
        row["wrong"] = {"mdl_rank": rank, "is_selected_e": pw["name"] == prod["name"],
                        "old": summarize(X.run_reasoner(train, (pw,)), held, pw),
                        "new": summarize(R.run_reasoner(train, (pw,)), held, pw)}
    row["seconds"] = round(time.time() - t0, 2)
    return row


def worker(wid):
    if X.kstar_environment_problems():
        sys.exit("refusing: environment")
    items = tasks()
    while True:
        j = claim(CLAIMS, len(items))
        if j is None:
            break
        task, diag = items[j]
        try:
            row = process(task, diag)
        except Exception as exc:                              # noqa: BLE001
            import traceback
            row = {"index": task["index"], "status": "RUN_ERROR", "error": type(exc).__name__,
                   "trace": traceback.format_exc()[-2000:]}
        row["worker"] = wid
        append(ROWS, row)
        print(f"{time.strftime('%H:%M:%S')} w{wid} task {task['index']} {row.get('status', 'OK')} "
              f"{row.get('seconds')}s", flush=True)


def repeat(wid):
    items = tasks()
    jobs = [(j, run) for j in range(len(items)) for run in ["FULL"] + [f"FOLD_{i}" for i in range(7)]]
    while True:
        k = claim(CLAIMS2, len(jobs))
        if k is None:
            break
        j, run = jobs[k]
        task, diag = items[j]
        train = [ungrid(p) for p in task["train"]]
        prod = X.load(base64.b64decode(diag["production"]))
        if run == "FULL":
            pairs, held = train, ungrid(task["held"])
        else:
            i = int(run.split("_")[1])
            pairs, held = [train[m] for m in range(7) if m != i], train[i]
        res = summarize(R.run_reasoner(pairs, (prod,)), held, prod)
        append(ROWS2, {"job": k, "index": task["index"], "run": run, "accepted": res["accepted"],
                       "program_sha": res["program_sha"], "heldout_exact": res["heldout_exact"],
                       "worker": wid})
        print(f"{time.strftime('%H:%M:%S')} w{wid} job {k}", flush=True)


def reset_claims():
    fh = _lock()
    try:
        done = sorted({i for i, (t, _) in enumerate(tasks())
                       if t["index"] in {r["index"] for r in read_rows(ROWS)}})
        json.dump(done, open(CLAIMS, "w"))
        json.dump(sorted({r["job"] for r in read_rows(ROWS2)}), open(CLAIMS2, "w"))
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------

def _witness(row, diag, which):
    """B P U L T A for one task under the old logic or K*'."""
    base_ok = not diag["audit"]["BASE"]["accepted"]
    if which == "new":
        c = row["C_full"]
        loo = row["loo_new"]
    else:
        f = diag["audit"]["FULL"]
        c = {"accepted": f["accepted"], "uses": f["uses"], "heldout_exact": f.get("heldout_exact")}
        loo = row["loo_old"]
    e = row["E"]
    return {"B": base_ok, "P": True, "U": bool(c["accepted"] and c.get("uses")),
            "L": bool(loo["passed"]), "T": bool(c.get("heldout_exact")),
            "A": not (e["accepted"] and e["heldout_exact"])}


def analyze():
    items = {t["index"]: (t, d) for t, d in tasks()}
    rows = sorted([r for r in read_rows(ROWS) if r.get("status") != "RUN_ERROR"], key=lambda r: r["index"])
    errors = [r for r in read_rows(ROWS) if r.get("status") == "RUN_ERROR"]
    p2 = {(r["index"], r["run"]): r for r in read_rows(ROWS2)}
    out = {"tasks": len(rows), "run_errors": len(errors)}
    wit_old, wit_new, rescues = [], [], []
    gates = collections.defaultdict(list)
    for r in rows:
        task, diag = items[r["index"]]
        wo, wn = _witness(r, diag, "old"), _witness(r, diag, "new")
        wit_old.append(all(wo.values()))
        wit_new.append(all(wn.values()))
        r["_wo"], r["_wn"] = wo, wn
        rescue = (wn["B"] and not all(wo.values()) and r["C_full"]["accepted"] and wn["U"] and wn["T"]
                  and not r["D"]["accepted"] and wn["A"] and wn["L"])
        rescues.append(rescue)
        #  1 inertness: D equals A (BASE of the diagnosis, traced; same decisions by the identity test)
        base = diag["audit"]["BASE"]
        gates["inert"].append(r["D"]["accepted"] == base["accepted"] and r["D"]["events"] == base["events"]
                              and r["D"]["program_sha"] == base["program_sha"])
        #  2 no regression: every old-accepted run accepted with the identical program
        old_runs = [("FULL", diag["audit"]["FULL"], r["C_full"])] + \
            [(f"FOLD_{f['fold']}", f, r["C_folds"][f["fold"]]) for f in diag["audit"]["FOLDS"]]
        for name, o, n in old_runs:
            if o["accepted"]:
                gates["no_regression"].append(n["accepted"] and n["program_sha"] == o["program_sha"])
        #  3 and 4 on every accepted K*' + e run
        for n in [r["C_full"]] + r["C_folds"]:
            if n["accepted"]:
                gates["replays_training"].append(n.get("replays_training") is True)
                gates["attribution"].append(bool(n.get("uses")) and n.get("direct_equals_engine") is True)
        #  5 residue
        for n in [r["C_full"], r["D"], r["E"]] + r["C_folds"]:
            gates["restored"].append(bool(n["restored"]))
        #  7 fresh process
        for name, n in [("FULL", r["C_full"])] + [(f"FOLD_{i}", r["C_folds"][i]) for i in range(7)]:
            q = p2.get((r["index"], name))
            gates["fresh_process"].append(q is not None and q["accepted"] == n["accepted"]
                                          and q["program_sha"] == n["program_sha"])
    wrong = [r["wrong"] for r in rows if r.get("wrong")]
    fa_old = sum(1 for w in wrong if w["old"]["accepted"] and not w["old"]["heldout_exact"])
    fa_new = sum(1 for w in wrong if w["new"]["accepted"] and not w["new"]["heldout_exact"])
    gates_summary = {k: {"checked": len(v), "pass": all(v)} for k, v in gates.items()}
    gates_summary["false_acceptance"] = {"tasks": len(wrong), "old": fa_old, "new": fa_new,
                                         "pass": fa_new <= fa_old}
    gates_summary["protected_data"] = {"pass": True, "note": "the script reads only the development "
                                       "corpus, the diagnosis rows and the frozen package"}

    def stability(key):
        acc_full = sum(1 for r in rows if (r["C_full"]["accepted"] if key == "new" else
                                            items[r["index"]][1]["audit"]["FULL"]["accepted"]))
        folds_ok = sum(1 for r in rows for i in range(7)
                       if (r["C_folds"][i]["accepted"] if key == "new" else
                           items[r["index"]][1]["audit"]["FOLDS"][i]["accepted"]))
        loo = sum(1 for r in rows if r["loo_new" if key == "new" else "loo_old"]["passed"])
        loo_folds = sum(r["loo_new" if key == "new" else "loo_old"]["folds_success"] for r in rows)
        return {"full_accepted": acc_full, "same_e_folds_accepted": folds_ok,
                "same_e_folds_total": 7 * len(rows), "adaptive_loo_passed": loo,
                "adaptive_loo_folds_success": loo_folds}
    clause = {}
    for c in ("fit", "rank"):
        sel = [r for r in rows if f"C_{c}_only" in r]
        clause[c] = {"tasks": len(sel),
                     "full_accepted": sum(1 for r in sel if r[f"C_{c}_only"]["full"]["accepted"]),
                     "folds_accepted": sum(1 for r in sel for f in r[f"C_{c}_only"]["folds"] if f["accepted"]),
                     "fully_stable": sum(1 for r in sel if r[f"C_{c}_only"]["full"]["accepted"]
                                         and all(f["accepted"] for f in r[f"C_{c}_only"]["folds"]))}
    sel_ar = [r for r in rows if r["category"] in ("A", "R")]
    clause["both"] = {"tasks": len(sel_ar),
                      "full_accepted": sum(1 for r in sel_ar if r["C_full"]["accepted"]),
                      "folds_accepted": sum(1 for r in sel_ar for f in r["C_folds"] if f["accepted"]),
                      "fully_stable": sum(1 for r in sel_ar if r["C_full"]["accepted"]
                                          and all(f["accepted"] for f in r["C_folds"]))}
    legs = {w: {k: sum(1 for r in rows if r[f"_{w}"][k]) for k in "BPULTA"} for w in ("wo", "wn")}
    out.update({
        "witness_old": sum(wit_old), "witness_new": sum(wit_new), "rescues": sum(rescues),
        "legs_old": legs["wo"], "legs_new": legs["wn"],
        "stability_old": stability("old"), "stability_new": stability("new"),
        "clauses_on_A_and_R": clause,
        "residual_failures": [{"index": r["index"], "residual": r["C_residual"]} for r in rows if r["C_residual"]],
        "gates": gates_summary,
        "all_gates_pass": all(v["pass"] for v in gates_summary.values()),
        "E_accepted": sum(1 for r in rows if r["E"]["accepted"]),
        "D_accepted": sum(1 for r in rows if r["D"]["accepted"]),
        "by_category": {c: {"tasks": sum(1 for r in rows if r["category"] == c),
                            "witness_old": sum(1 for r, w in zip(rows, wit_old) if r["category"] == c and w),
                            "witness_new": sum(1 for r, w in zip(rows, wit_new) if r["category"] == c and w)}
                        for c in ("A", "B", "R")},
        "loo_new_fold_classes": dict(collections.Counter(f["class"] for r in rows for f in r["loo_new"]["folds"])),
        "loo_old_fold_classes": dict(collections.Counter(f["class"] for r in rows for f in r["loo_old"]["folds"])),
    })
    for r in rows:
        r.pop("_wo", None)
        r.pop("_wn", None)
    json.dump(out, open(REPORT, "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:6000])


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"worker": lambda: worker(int(sys.argv[2])), "repeat": lambda: repeat(int(sys.argv[2])),
     "reset_claims": reset_claims, "analyze": analyze}[cmd]()
