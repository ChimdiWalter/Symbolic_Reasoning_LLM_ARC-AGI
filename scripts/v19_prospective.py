"""Item-2 v1.9 prospective engine-stability test (protocol section 16).

Frozen in v1.9, run ONCE in the next session, after the review and any
errata. Refuses on any freeze or environment problem, refuses a second
start, and resumes only after a genuine interruption (start record present,
report and marker absent).

  python scripts/v19_prospective.py              coordinator: checks, start
                                                 record, corpus, workers,
                                                 aggregation, report, marker
  python scripts/v19_prospective.py --resume     the same after an interruption
  python scripts/v19_prospective.py --worker K   one worker (spawned by the
                                                 coordinator only)

Corpus: scripts/v18_corpus.py at seed base 880,000,000 (+100k), the v1.8
corpus law unchanged, distinct target digests, skipping every digest in
outputs/tti/v19_prospective_exclusion.json. Per task:
- proposer arms FAILURE_CONDITIONED, SHUFFLED_FRONTIER (fixed derangement)
  and BLIND, each with the fitter-level held-out check ("useful");
- for FAILURE_CONDITIONED: the paired ablation under K* (old logic) and
  under K*' (K* + K*-4), K* alone at 3x budget, the v1.8 adaptive
  leave-one-out under K* and under K*', and the false-acceptance control;
- the synthetic witness legs under K*' (primary) and under K*.
The generator's schema is never read here except by the corpus law.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import traceback

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_arc2026 import v18_proposer as P                        # noqa: E402
from cora_v19 import v19_repair as R                              # noqa: E402
import v18_corpus as CORPUS                                       # noqa: E402
import v18_prospective as PR18                                    # noqa: E402
import v19_repair_dev as RD                                       # noqa: E402

SEED_BASE = 880_000_000
N_TASKS = None          # set by records/ITEM2_V19_FEASIBILITY.md before any prospective data
W_MIN = None            # complete K*' witnesses required (same record)
DELTA_MIN = None        # minimum (new-only minus old-only) adaptive leave-one-out passes (same record)
WORKERS = 4
ALPHA = 0.05
BASELINE_3X_BUDGET_S = 24.0
ARMS = ("FAILURE_CONDITIONED", "SHUFFLED_FRONTIER", "BLIND")
G1_CONTROLS = ("SHUFFLED_FRONTIER", "BLIND")

OUTD = os.path.join(HERE, "outputs", "tti")
LOGD = os.path.join(HERE, "logs", "v19")
MANIFEST = os.path.join(OUTD, "engine_stability_v19_manifest.json")
EXCLUSION = os.path.join(OUTD, "v19_prospective_exclusion.json")
OUT = os.path.join(OUTD, "v19_prospective_report.json")
ROWS = os.path.join(OUTD, "v19_prospective_rows.jsonl")
TASKS = os.path.join(OUTD, "v19_prospective_tasks.json")
START = os.path.join(LOGD, "prospective_start.json")
MARKER = os.path.join(HERE, "logs", "V19_PROSPECTIVE_DONE")
LOCK = os.path.join(LOGD, "prospective.lock")
CLAIMS = os.path.join(LOGD, "prospective_claims.json")
OUTCOMES = ("ENGINE_STABILITY_REPAIR_ACCEPTED", "FAILURE_SPECIFICITY_LOST",
            "REPAIR_STABILIZES_BELOW_WITNESS_THRESHOLD", "REPAIR_NOT_MATERIAL", "REPAIR_UNSAFE",
            "PROPOSER_LEAKAGE", "NO_VERDICT_FIXTURE_SHORTFALL", "NO_VERDICT_RUN_ERROR")


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def freeze_problems():
    if not os.path.exists(MANIFEST):
        return ["no manifest"], None
    man = json.load(open(MANIFEST))
    p = []
    if open(MANIFEST + ".sha256").read().split()[0] != sha(MANIFEST):
        p.append("manifest")
    for rel, d in man["implementation_sha256"].items():
        if sha(os.path.join(HERE, rel)) != d:
            p.append(rel)
    for name, root in L.dependency_roots(HERE).items():
        if L.tree_digest(root) != man["dependency_tree_sha256"].get(name):
            p.append(f"dependency:{name}")
    if L.tree_digest(os.path.join(HERE, "cora_v19")) != man["dependency_tree_sha256"].get("cora_v19"):
        p.append("dependency:cora_v19")
    for path, d in man["external_file_sha256"].items():
        if not os.path.exists(path) or sha(path) != d:
            p.append(f"external:{os.path.basename(path)}")
    if L.runtime_versions() != man["runtime_versions"]:
        p.append("runtime_versions")
    if X.k_identity() != man["k_identity"]:
        p.append("k_identity")
    if R.repair_identity() != man["repair_identity"]:
        p.append("repair_identity")
    if sha(EXCLUSION) != man["prospective_exclusion_sha256"]:
        p.append("exclusion")
    if N_TASKS is None or W_MIN is None or DELTA_MIN is None:
        p.append("thresholds unset")
    if man.get("status") not in ("FROZEN_NOT_PROSPECTIVELY_TESTED", "FROZEN_AFTER_ERRATUM_01_NOT_PROSPECTIVELY_TESTED"):
        p.append(f"status {man.get('status')}")
    return p, man


def locked_append(path, row):
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        with open(path, "a") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def claim(n):
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        claims = json.load(open(CLAIMS)) if os.path.exists(CLAIMS) else []
        for i in range(n):
            if i not in claims:
                claims.append(i)
                json.dump(claims, open(CLAIMS, "w"))
                return i
    return None


def read_rows():
    return [json.loads(line) for line in open(ROWS)] if os.path.exists(ROWS) else []


def ungrid(p):
    import numpy as np
    return (np.asarray(p[0], dtype=int), np.asarray(p[1], dtype=int))


def _strip(ab):
    out = {"verdict": ab["verdict"], "uses": ab["with_uses_extension"]}
    for k in ("with", "without"):
        d = ab[k]
        out[k] = {"accepted": d["accepted"], "heldout_exact": d.get("heldout_exact"),
                  "events": d["events"], "seconds": d["seconds"],
                  "program_sha": RD.psha(d["program"])}
    return out


def _loo(loo):
    return {"passed": loo["passed"], "folds_success": loo["folds_success"],
            "folds": [{k: f.get(k) for k in ("fold", "class", "proposer_class", "selected", "accepted",
                                             "uses", "heldout_exact", "production")} for f in loo["folds"]]}


WRONG_FROM_POOL = 3


def wrong_extensions(train, held, selected_name, recs):
    """False-acceptance control (protocol section 16): wrong extensions,
    distinct by production name and never the selected e: up to
    WRONG_FROM_POOL candidates of the FAILURE_CONDITIONED proposer's
    verified, deduplicated pool in MDL order whose fitter prediction of the
    held-out pair is wrong, then the SHUFFLED_FRONTIER and BLIND selections
    when selected and not useful."""
    import numpy as np
    out, names = [], {selected_name}
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
        if len(out) >= WRONG_FROM_POOL:
            break
        pred = P._evaluate(c["fitted"], held[0])
        if pred is None or not np.array_equal(pred, held[1]):
            pw = X.compile_extension(X.make_input(c["schema"]))
            if pw["name"] not in names:
                names.add(pw["name"])
                out.append(("POOL", rank, pw))
    for arm in ("SHUFFLED_FRONTIER", "BLIND"):
        rec = recs[arm]
        if rec["class"] == "SELECTED" and not PR18.heldout_exact(rec, held):
            pw = P.compile_selected(rec)
            if pw["name"] not in names:
                names.add(pw["name"])
                out.append((arm, None, pw))
    return out


def run_task(t, donor):
    train = [ungrid(p) for p in t["train"]]
    held = ungrid(t["held"])
    row = {"i": t["i"], "seed": t["seed"], "family": t["family"], "digest": t["digest"],
           "donor_seed": t["donor_seed"], "arms": {}}
    recs = {}
    for arm in ARMS:
        rec = P.solve(train, arm, donor_failure=donor if arm == "SHUFFLED_FRONTIER" else None)
        recs[arm] = rec
        row["arms"][arm] = {"class": rec["class"], "selection": rec["selection"], "seconds": rec["seconds"],
                            "selected": rec["selected"]["canonical"] if rec.get("selected") else None,
                            "useful": PR18.heldout_exact(rec, held)}
    main = recs["FAILURE_CONDITIONED"]
    if main["class"] != "SELECTED":
        row["witness_new"] = row["witness_old"] = {"complete": False, "P": False}
        return row
    try:
        prod = P.compile_selected(main)
    except X.CompileError as exc:
        row["engine_class"] = "COMPILE_FAILURE"
        row["detail"] = exc.code
        row["witness_new"] = row["witness_old"] = {"complete": False, "P": True}
        return row
    row["production"] = prod["name"]
    row["load_start"] = [round(x, 2) for x in os.getloadavg()]
    old = X.paired_ablation(train, prod, heldout=held)
    with R.repaired():
        new_run = X.run_reasoner(train, (prod,))
        new_alone = X.run_reasoner(train, ())
    row["restored"] = R.restored()
    row["old"] = _strip(old)
    row["new_with"] = RD.summarize(new_run, held, prod, train)
    row["new_alone"] = {"accepted": new_alone["accepted"], "events": new_alone["events"],
                        "program_sha": RD.psha(new_alone["program"])}
    base3 = X.run_reasoner(train, (), budget_s=BASELINE_3X_BUDGET_S)
    row["baseline_3x"] = {"accepted": base3["accepted"], "heldout_exact": X.predict_exact(base3, *held),
                          "seconds": base3["seconds"]}
    row["loo_old"] = _loo(P.real_loo(train))
    with R.repaired():
        row["loo_new"] = _loo(P.real_loo(train))
    row["restored"] = row["restored"] and R.restored()
    row["wrong_trials"] = []
    for source, rank, pw in wrong_extensions(train, held, prod["name"], recs):
        row["wrong_trials"].append({"source": source, "mdl_rank": rank, "production": pw["name"],
                                    "old": RD.summarize(X.run_reasoner(train, (pw,)), held, pw),
                                    "new": RD.summarize(R.run_reasoner(train, (pw,)), held, pw)})
    row["load_end"] = [round(x, 2) for x in os.getloadavg()]
    a_leg = not (base3["accepted"] and row["baseline_3x"]["heldout_exact"])
    o = row["old"]
    wo = {"B": o["without"]["accepted"] is False, "P": True, "U": bool(o["uses"]),
          "L": row["loo_old"]["passed"], "T": bool(o["with"]["heldout_exact"]), "A": a_leg}
    n = row["new_with"]
    wn = {"B": row["new_alone"]["accepted"] is False, "P": True, "U": bool(n.get("uses")),
          "L": row["loo_new"]["passed"], "T": bool(n["heldout_exact"]), "A": a_leg}
    row["witness_old"] = dict(wo, complete=all(wo.values()))
    row["witness_new"] = dict(wn, complete=all(wn.values()))
    return row


def binom_upper_p(b, c) -> float:
    n = b + c
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n if n else 1.0


def compare_useful(rows, a, b):
    x = sum(1 for r in rows if r["arms"][a]["useful"] and not r["arms"][b]["useful"])
    y = sum(1 for r in rows if r["arms"][b]["useful"] and not r["arms"][a]["useful"])
    p = binom_upper_p(x, y)
    return {"a_only": x, "b_only": y, "p_one_sided": p, "pass": x > y and p < ALPHA}


def safety(rows):
    """G4: inertness, no regression, no false-acceptance increase, replay,
    attribution and restoration (protocol section 16)."""
    eng = [r for r in rows if "old" in r]
    checks = {
        "inert": all(r["new_alone"]["accepted"] == r["old"]["without"]["accepted"]
                     and r["new_alone"]["events"] == r["old"]["without"]["events"]
                     and r["new_alone"]["program_sha"] == r["old"]["without"]["program_sha"] for r in eng),
        "no_regression_full": all(r["new_with"]["accepted"] and r["new_with"]["heldout_exact"]
                                  and r["new_with"]["program_sha"] == r["old"]["with"]["program_sha"]
                                  for r in eng if r["old"]["with"]["accepted"] and r["old"]["with"]["heldout_exact"]),
        "no_regression_folds": all(fn["class"] == "SUCCESS"
                                   for r in eng for fo, fn in zip(r["loo_old"]["folds"], r["loo_new"]["folds"])
                                   if fo["class"] == "SUCCESS"),
        "replays_training": all(r["new_with"].get("replays_training") is True
                                for r in eng if r["new_with"]["accepted"]),
        "attribution": all(r["new_with"].get("direct_equals_engine") is True
                           for r in eng if r["new_with"]["accepted"] and r["new_with"].get("uses")),
        "restored": all(r.get("restored") for r in eng),
    }
    wrong = [w for r in eng for w in r.get("wrong_trials", [])]
    fa_old = sum(1 for w in wrong if w["old"]["accepted"] and not w["old"]["heldout_exact"])
    fa_new = sum(1 for w in wrong if w["new"]["accepted"] and not w["new"]["heldout_exact"])
    full_fa_old = sum(1 for r in eng if r["old"]["with"]["accepted"] and not r["old"]["with"]["heldout_exact"])
    full_fa_new = sum(1 for r in eng if r["new_with"]["accepted"] and not r["new_with"]["heldout_exact"])
    checks["false_acceptance_control"] = fa_new <= fa_old
    checks["false_acceptance_selected"] = full_fa_new <= full_fa_old
    return {"checks": checks, "control_trials": len(wrong), "control_fa_old": fa_old, "control_fa_new": fa_new,
            "selected_fa_old": full_fa_old, "selected_fa_new": full_fa_new, "pass": all(checks.values())}


def outcome(rows, unexpected, n_tasks, leakage):
    ok = [r for r in rows if "error" not in r]
    gates = {}
    if leakage:
        return "PROPOSER_LEAKAGE", gates
    if unexpected:
        return "NO_VERDICT_RUN_ERROR", gates
    if n_tasks < N_TASKS:
        return "NO_VERDICT_FIXTURE_SHORTFALL", gates
    gates = {f"G1_vs_{a.lower()}": compare_useful(ok, "FAILURE_CONDITIONED", a) for a in G1_CONTROLS}
    w = sum(1 for r in ok if r["witness_new"]["complete"])
    gates["G2_witnesses_new"] = {"complete": w, "required": W_MIN, "pass": w >= W_MIN,
                                 "complete_old": sum(1 for r in ok if r["witness_old"]["complete"])}
    b = sum(1 for r in ok if r.get("loo_new", {}).get("passed") and not r.get("loo_old", {}).get("passed"))
    c = sum(1 for r in ok if r.get("loo_old", {}).get("passed") and not r.get("loo_new", {}).get("passed"))
    p = binom_upper_p(b, c)
    gates["G3_loo_stability"] = {"new_only": b, "old_only": c, "p_one_sided": p, "delta_min": DELTA_MIN,
                                 "pass": b - c >= DELTA_MIN and p < ALPHA}
    gates["G4_safety"] = safety(ok)
    g1 = all(gates[f"G1_vs_{a.lower()}"]["pass"] for a in G1_CONTROLS)
    g2, g3, g4 = gates["G2_witnesses_new"]["pass"], gates["G3_loo_stability"]["pass"], gates["G4_safety"]["pass"]
    if not g4:
        return "REPAIR_UNSAFE", gates
    if g1 and g2 and g3:
        return "ENGINE_STABILITY_REPAIR_ACCEPTED", gates
    if g2 and g3:
        return "FAILURE_SPECIFICITY_LOST", gates
    if g3:
        return "REPAIR_STABILIZES_BELOW_WITNESS_THRESHOLD", gates
    return "REPAIR_NOT_MATERIAL", gates


def worker(k):
    tasks = json.load(open(TASKS))["tasks"]
    done = {r["i"] for r in read_rows()}
    while True:
        j = claim(len(tasks))
        if j is None:
            break
        t = tasks[j]
        if t["i"] in done:
            continue
        donor = P.build_input([ungrid(p) for p in tasks[t["donor_index"]]["train"]])["failure"]
        try:
            row = run_task(t, donor)
        except Exception as exc:                              # noqa: BLE001
            row = {"i": t["i"], "seed": t["seed"], "error": "UNEXPECTED", "exception": type(exc).__name__,
                   "traceback": traceback.format_exc()}
        row["worker"] = k
        locked_append(ROWS, row)


def main():
    if "--worker" in sys.argv:
        worker(int(sys.argv[sys.argv.index("--worker") + 1]))
        return
    resume = "--resume" in sys.argv[1:]
    os.makedirs(LOGD, exist_ok=True)
    if resume:
        if not os.path.exists(START) or os.path.exists(OUT) or os.path.exists(MARKER):
            raise SystemExit("refusing --resume: needs a start record and no report or marker")
    else:
        for path in (OUT, ROWS, START, MARKER, TASKS, CLAIMS):
            if os.path.exists(path):
                raise SystemExit(f"refusing: {os.path.relpath(path, HERE)} exists; the prospective test "
                                 "runs once (use --resume only after an interruption)")
    env = X.kstar_environment_problems()
    if env:
        raise SystemExit(f"environment problems, refusing: {env}")
    problems, man = freeze_problems()
    if problems:
        raise SystemExit(f"freeze problems, refusing: {problems}")
    started = time.time()
    resumes = []
    if resume:
        resumes.append({"resumed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pid": os.getpid()})
        done = sorted({r["i"] for r in read_rows()})
        json.dump(done, open(CLAIMS, "w"))
    else:
        with open(START, "w") as handle:
            handle.write(json.dumps({"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                     "pid": os.getpid(), "manifest_sha256": sha(MANIFEST),
                                     "environment": L.environment_snapshot(), "workers": WORKERS,
                                     "loadavg": list(os.getloadavg()), "cpus": os.cpu_count()},
                                    indent=1, sort_keys=True) + "\n")
    unexpected = []
    if not os.path.exists(TASKS):
        exclusion = set(json.load(open(EXCLUSION))["target_digests"])
        try:
            tasks = CORPUS.tasks(SEED_BASE, N_TASKS, exclude_digests=exclusion, distinct=True)
        except Exception:                                      # noqa: BLE001
            unexpected.append({"stage": "corpus", "traceback": traceback.format_exc()})
            tasks = []
        body = []
        for i, t in enumerate(tasks):
            j = (i + 1) % len(tasks)
            while tasks[j]["digest"] == t["digest"]:
                j = (j + 1) % len(tasks)
            body.append({"i": i, "seed": t["seed"], "family": t["family"], "digest": t["digest"],
                         "donor_index": j, "donor_seed": tasks[j]["seed"],
                         "train": [[p[0].tolist(), p[1].tolist()] for p in t["train"]],
                         "held": [t["held"][0].tolist(), t["held"][1].tolist()]})
        json.dump({"seed_base": SEED_BASE, "n": len(body), "tasks": body}, open(TASKS, "w"))
    tasks = json.load(open(TASKS))["tasks"]
    if not unexpected and len(tasks) == N_TASKS:
        procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "--worker", str(k)],
                                  stdout=open(os.path.join(LOGD, f"prospective_worker_{k}.log"), "a"),
                                  stderr=subprocess.STDOUT, cwd=HERE) for k in range(1, WORKERS + 1)]
        for pr in procs:
            pr.wait()
    rows = sorted(read_rows(), key=lambda r: r["i"])
    seen = set()
    dedup = []
    for r in rows:
        if r["i"] not in seen:
            seen.add(r["i"])
            dedup.append(r)
    duplicates = len(rows) - len(dedup)
    rows = dedup
    missing = sorted(set(range(len(tasks))) - {r["i"] for r in rows})
    unexpected += [{"stage": f"task {r['i']}", "exception": r.get("exception")} for r in rows if "error" in r]
    if missing and len(tasks) == N_TASKS:
        unexpected.append({"stage": "missing rows", "tasks": missing})
    ok = [r for r in rows if "error" not in r]
    leakage = (sum(1 for r in ok for a in r["arms"].values() if a["class"] == "LEAKAGE_FAILURE")
               + sum(1 for r in ok for k in ("loo_old", "loo_new") for f in r.get(k, {}).get("folds", [])
                     if f.get("proposer_class") == "LEAKAGE_FAILURE"))
    out, gates = outcome(rows, unexpected, len(tasks), leakage)
    report = {"outcome": out, "gates": gates, "tasks": len(tasks), "rows": len(rows),
              "duplicate_rows": duplicates, "unexpected": unexpected, "leakage": leakage,
              "resumes": resumes, "manifest_sha256": sha(MANIFEST), "repair_identity": R.repair_identity(),
              "seed_base": SEED_BASE, "seconds": round(time.time() - started, 1),
              "loadavg_end": list(os.getloadavg()),
              "supplementary": {
                  "useful_by_arm": {a: sum(1 for r in ok if r["arms"][a]["useful"]) for a in ARMS},
                  "legs_new": {k: sum(1 for r in ok if r.get("witness_new", {}).get(k)) for k in "BPULTA"},
                  "legs_old": {k: sum(1 for r in ok if r.get("witness_old", {}).get(k)) for k in "BPULTA"},
                  "selection_levels": {lv: sum(1 for r in ok if (r["arms"]["FAILURE_CONDITIONED"]["selection"]
                                                                 or {}).get("level") == lv)
                                       for lv in P.SELECTION_LEVELS},
                  "by_family": {f: {"tasks": sum(1 for r in ok if r["family"] == f),
                                    "witnesses_new": sum(1 for r in ok if r["family"] == f
                                                         and r.get("witness_new", {}).get("complete")),
                                    "witnesses_old": sum(1 for r in ok if r["family"] == f
                                                         and r.get("witness_old", {}).get("complete"))}
                                for f in sorted({r["family"] for r in ok})},
                  "loo_fold_classes_new": {c: sum(1 for r in ok for f in r.get("loo_new", {}).get("folds", [])
                                                  if f["class"] == c)
                                           for c in sorted({f["class"] for r in ok
                                                            for f in r.get("loo_new", {}).get("folds", [])})},
                  "loo_fold_classes_old": {c: sum(1 for r in ok for f in r.get("loo_old", {}).get("folds", [])
                                                  if f["class"] == c)
                                           for c in sorted({f["class"] for r in ok
                                                            for f in r.get("loo_old", {}).get("folds", [])})}}}
    json.dump(report, open(OUT, "w"), indent=1, sort_keys=True, default=str)
    with open(MARKER, "w") as handle:
        handle.write(out + "\n")
    print(json.dumps({"outcome": out, "gates": gates}, indent=1, default=str))


if __name__ == "__main__":
    main()
