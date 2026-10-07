"""v1.9 engine acceptance stability audit: the DEVELOPMENT diagnosis.

  prepare            freeze checks, the development exclusion set, the corpus
  worker <wid>       phase 1: pull tasks in corpus order (stop rule, protocol
                     section 12): proposer -> compile -> paired audit ->
                     repeat A -> selection-quality proxy; one row per task
  plan2              phase 2 job list: repeat B (fresh process) and the
                     clock diagnosis (protocol sections 8 and 9)
  repeat <wid>       phase 2 worker
  analyze            the diagnosis report

Development data only (seeds 870,000,000 + 100k). The future prospective
range 880,000,000 + 100k is never generated here.
"""
import base64
import fcntl
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

import v18_corpus as CORPUS                                       # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_arc2026 import v18_proposer as P                        # noqa: E402
from cora_v19 import v19_audit as A                           # noqa: E402

DEV_BASE = 870_000_000
PROSPECTIVE_BASE_RESERVED = 880_000_000
MAX_TASKS = 60
MIN_AUDITED, MIN_A, MIN_B = 30, 12, 6
LOAD_REJECTED, LOAD_ACCEPTED = 12, 6
IDENTITY_N = 6

OUT = os.path.join(HERE, "outputs", "tti")
LOG = os.path.join(HERE, "logs", "v19")
CORPUS_FILE = os.path.join(OUT, "v19_dev_corpus.json")
EXCL_FILE = os.path.join(OUT, "v19_dev_exclusion.json")
ROWS = os.path.join(OUT, "v19_dev_rows.jsonl")
JOBS2 = os.path.join(OUT, "v19_dev_phase2_jobs.json")
ROWS2 = os.path.join(OUT, "v19_dev_phase2_rows.jsonl")
REPORT = os.path.join(OUT, "v19_audit_report.json")
PREFREEZE = os.path.join(OUT, "v19_audit_prefreeze_manifest.json")
LOCK = os.path.join(LOG, "queue.lock")
CLAIMS = os.path.join(LOG, "claims.json")
V18_MANIFEST_SHA = "d64732cf54f91f70ce6f7be041956850d6cc85ca3986e4e08199401278db8731"
K_IDENTITY = "b009a9fb13402348a73c3e1ef187a82c2d42fb5175e5fed806e8d33d6b73e729"


def sha_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def freeze_problems():
    problems = []
    if sha_file(os.path.join(OUT, "no_oracle_proposer_v18_manifest.json")) != V18_MANIFEST_SHA:
        problems.append("v1.8 manifest changed")
    if X.k_identity() != K_IDENTITY:
        problems.append("K* identity changed")
    problems += X.kstar_environment_problems()
    if os.path.exists(PREFREEZE):
        man = json.load(open(PREFREEZE))
        for rel, digest in man["files"].items():
            if sha_file(os.path.join(HERE, rel)) != digest:
                problems.append(f"pre-freeze file changed: {rel}")
    else:
        problems.append("no pre-freeze manifest")
    return problems


def grids(pair):
    return [[list(map(int, r)) for r in pair[0]], [list(map(int, r)) for r in pair[1]]]


def ungrid(pair):
    import numpy as np
    return (np.asarray(pair[0], dtype=int), np.asarray(pair[1], dtype=int))


@__import__("contextlib").contextmanager
def locked():
    os.makedirs(LOG, exist_ok=True)
    with open(LOCK, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def append(path, row):
    with locked():
        with open(path, "a") as fh:
            fh.write(json.dumps(row, default=str) + "\n")


def read_rows(path):
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path) if line.strip()]


# --------------------------------------------------------------------------
# prepare
# --------------------------------------------------------------------------

def prepare():
    problems = freeze_problems()
    if problems:
        sys.exit("refusing: " + "; ".join(problems))
    if os.path.exists(CORPUS_FILE):
        sys.exit("refusing: the development corpus already exists")
    excl = set(json.load(open(os.path.join(OUT, "v18_prospective_exclusion.json")))["target_digests"])
    v18p = [json.loads(line)["digest"] for line in open(os.path.join(OUT, "v18_prospective_rows.jsonl"))]
    e_dev = sorted(excl | set(v18p))
    json.dump({"sources": ["outputs/tti/v18_prospective_exclusion.json (3,817)",
                           "outputs/tti/v18_prospective_rows.jsonl digests (30)"],
               "total": len(e_dev), "target_digests": e_dev}, open(EXCL_FILE, "w"), indent=0)
    tasks = CORPUS.tasks(DEV_BASE, MAX_TASKS, exclude_digests=frozenset(e_dev), distinct=True)
    #  descriptive split only (never read by the worker): is the normalized
    #  target structure among the v1.8 development structures?
    import v18_prospective as PR
    dev_structures = {json.loads(line)["target_normalized"]
                      for line in open(os.path.join(OUT, "v18_dev_rows.jsonl"))}
    body = [{"index": i, "k": t["k"], "seed": t["seed"], "family": t["family"], "digest": t["digest"],
             "seen_v18_dev": PR.normalized_canonical(t["schema"]) in dev_structures,
             "train": [grids(p) for p in t["train"]], "held": grids(t["held"])}
            for i, t in enumerate(tasks)]
    json.dump({"seed_base": DEV_BASE, "n": len(body), "exclusion_sha256": sha_file(EXCL_FILE),
               "tasks": body}, open(CORPUS_FILE, "w"))
    print(json.dumps({"tasks": len(body), "exclusion": len(e_dev),
                      "seeds": [body[0]["seed"], body[-1]["seed"]] if body else None}))


# --------------------------------------------------------------------------
# phase 1
# --------------------------------------------------------------------------

def category(row):
    if row.get("status") != "AUDITED":
        return None
    full = row["audit"]["FULL"]["accepted"]
    folds = [f["accepted"] for f in row["audit"]["FOLDS"]]
    return "R" if not full else ("B" if all(folds) else "A")


def stop_prefix(rows, n_total):
    """The shortest complete corpus prefix satisfying the stop rule, or None."""
    done = {r["index"]: r for r in rows}
    audited = a = b = 0
    for i in range(n_total):
        if i not in done:
            return None
        cat = category(done[i])
        if cat is not None:
            audited += 1
            a += cat == "A"
            b += cat == "B"
        if audited >= MAX_TASKS or (audited >= MIN_AUDITED and a >= MIN_A and b >= MIN_B):
            return i + 1
    return n_total


def claim(n_total):
    with locked():
        claims = json.load(open(CLAIMS)) if os.path.exists(CLAIMS) else []
        rows = [json.loads(line) for line in open(ROWS)] if os.path.exists(ROWS) else []
        if stop_prefix(rows, n_total) is not None:
            return None
        for i in range(n_total):
            if i not in claims:
                claims.append(i)
                json.dump(claims, open(CLAIMS, "w"))
                return i
    return None


def selection_quality(train, rec):
    """H4: the frozen proposer's verified, deduplicated pool on the seven
    pairs, each candidate with the fitter-level nested proxy."""
    sem = P.Semantics(train)
    inp = P.build_input(train, sem)
    deadline = time.time() + P.LIMITS["wall_s"]
    verified = []
    for depth in P.LIMITS["depths"]:
        gen = P.propose(inp, depth, sem, deadline)
        verified = P.verify(gen["proposals"], sem, deadline)
        if verified:
            break
    pool = P.dedupe(verified, deadline)
    sel = rec["selected"]["canonical"]
    out = []
    for c in pool:
        out.append({"canonical_sha": hashlib.sha256(c["canonical"].encode()).hexdigest()[:16],
                    "selected": c["canonical"] == sel, "entries": c["entries"],
                    "proxy": A.nested_proxy(c["schema"], train)})
    s = next((c for c in out if c["selected"]), None)
    alt_full = [c for c in out if not c["selected"] and all(c["proxy"])]
    return {"pool": len(out), "candidates": out,
            "selected_in_pool": s is not None,
            "selected_proxy": s["proxy"] if s else None,
            "alternative_full_proxy": len(alt_full),
            "H4": bool(s is not None and not all(s["proxy"]) and alt_full)}


def process(task):
    train = [ungrid(p) for p in task["train"]]
    held = ungrid(task["held"])
    t0 = time.time()
    row = {"index": task["index"], "seed": task["seed"], "family": task["family"],
           "digest": task["digest"], "pid": os.getpid()}
    rec = P.solve(train, "FAILURE_CONDITIONED")
    row["proposer"] = {"class": rec["class"], "selection": rec.get("selection"),
                       "selected": (rec["selected"] or {}).get("canonical"),
                       "seconds": rec["seconds"], "proposals": rec.get("proposals")}
    if rec["class"] != "SELECTED":
        row["status"] = "NOT_SELECTED"
        row["seconds"] = round(time.time() - t0, 2)
        return row
    try:
        prod = P.compile_selected(rec)
    except X.CompileError as exc:
        row["status"] = "COMPILE_FAILURE"
        row["detail"] = exc.code
        return row
    row["production"] = base64.b64encode(X.serialize(prod)).decode()
    row["production_sha256"] = hashlib.sha256(X.serialize(prod)).hexdigest()
    audit = A.paired_audit(train, held, prod)
    row["audit"] = audit
    rep = {"FULL": A.run_signature(A.traced_run(train, prod, "WALL", held))}
    for f in audit["FOLDS"]:
        if not f["accepted"]:
            i = f["fold"]
            sub = [train[j] for j in range(len(train)) if j != i]
            rep[f"FOLD_{i}"] = A.run_signature(A.traced_run(sub, prod, "WALL", train[i]))
    row["repeat_A"] = rep
    try:
        row["selection_quality"] = selection_quality(train, rec)
    except Exception as exc:                                  # noqa: BLE001
        row["selection_quality"] = {"error": type(exc).__name__}
    row["status"] = "AUDITED"
    row["category"] = category(row)
    row["seconds"] = round(time.time() - t0, 2)
    return row


def worker(wid):
    problems = freeze_problems()
    if problems:
        sys.exit("refusing: " + "; ".join(problems))
    corpus = json.load(open(CORPUS_FILE))["tasks"]
    while True:
        i = claim(len(corpus))
        if i is None:
            break
        try:
            row = process(corpus[i])
        except Exception as exc:                              # noqa: BLE001
            import traceback
            row = {"index": i, "seed": corpus[i]["seed"], "status": "RUN_ERROR",
                   "error": type(exc).__name__, "trace": traceback.format_exc()[-2000:]}
        row["worker"] = wid
        append(ROWS, row)
        print(f"{time.strftime('%H:%M:%S')} w{wid} task {i} {row.get('status')} "
              f"{row.get('category')} {row.get('seconds')}s", flush=True)


# --------------------------------------------------------------------------
# phase 2
# --------------------------------------------------------------------------

def plan2():
    corpus = json.load(open(CORPUS_FILE))["tasks"]
    rows = sorted(read_rows(ROWS), key=lambda r: r["index"])
    m = stop_prefix(rows, len(corpus))
    if m is None:
        sys.exit("refusing: phase 1 incomplete")
    inside = [r for r in rows if r["index"] < m and r.get("status") == "AUDITED"]
    jobs, rejected, accepted = [], [], []
    for r in inside:
        runs = [("FULL", r["audit"]["FULL"])] + [(f"FOLD_{f['fold']}", f) for f in r["audit"]["FOLDS"]]
        for name, run in runs:
            if name == "FULL" or not run["accepted"]:
                jobs.append({"kind": "repeat_B", "index": r["index"], "run": name, "clock": "WALL"})
            (accepted if run["accepted"] else rejected).append((r["index"], name))
    for idx, name in rejected[:LOAD_REJECTED] + accepted[:LOAD_ACCEPTED]:
        for clock in ("CPU1", "CPU10"):
            jobs.append({"kind": "load", "index": idx, "run": name, "clock": clock})
    #  decision identity under tracing: the same runs untraced
    for idx, name in rejected[:IDENTITY_N] + accepted[:IDENTITY_N]:
        jobs.append({"kind": "identity", "index": idx, "run": name, "clock": "WALL"})
    json.dump({"stop_prefix": m, "audited": len(inside), "jobs": jobs}, open(JOBS2, "w"), indent=0)
    print(json.dumps({"stop_prefix": m, "audited": len(inside), "jobs": len(jobs)}))


def claim2(n):
    path = os.path.join(LOG, "claims2.json")
    with locked():
        claims = json.load(open(path)) if os.path.exists(path) else []
        for i in range(n):
            if i not in claims:
                claims.append(i)
                json.dump(claims, open(path, "w"))
                return i
    return None


def repeat(wid):
    problems = freeze_problems()
    if problems:
        sys.exit("refusing: " + "; ".join(problems))
    corpus = json.load(open(CORPUS_FILE))["tasks"]
    rows = {r["index"]: r for r in read_rows(ROWS)}
    jobs = json.load(open(JOBS2))["jobs"]
    warmed = False
    while True:
        j = claim2(len(jobs))
        if j is None:
            break
        job = jobs[j]
        r = rows[job["index"]]
        prod = X.load(base64.b64decode(r["production"]))
        train = [ungrid(p) for p in corpus[job["index"]]["train"]]
        if job["run"] == "FULL":
            pairs, held = train, ungrid(corpus[job["index"]]["held"])
        else:
            i = int(job["run"].split("_")[1])
            pairs, held = [train[k] for k in range(len(train)) if k != i], train[i]
        if job["clock"] != "WALL" and not warmed:
            A.traced_run(pairs, prod, "WALL", held)               # imports every lazy module first
            warmed = True
        t0 = time.time()
        try:
            if job["kind"] == "identity":
                run = X.run_reasoner(pairs, (prod,))
                res = {"job": j, **job, "accepted": run["accepted"], "events": run["events"],
                       "program_sha": (hashlib.sha256(json.dumps(run["program"], sort_keys=True,
                                                                 default=str).encode()).hexdigest()[:16]
                                       if run["program"] else None),
                       "heldout_exact": X.predict_exact(run, *held)}
            else:
                out = A.traced_run(pairs, prod, job["clock"], held)
                res = {"job": j, **job, "signature": A.run_signature(out), "timing": out["timing"],
                       "heldout_exact": out.get("heldout_exact"), "uses": out["uses"],
                       "events": out["events"], "program_sha": out["program_sha"]}
        except Exception as exc:                              # noqa: BLE001
            res = {"job": j, **job, "error": type(exc).__name__}
        res["seconds"] = round(time.time() - t0, 2)
        res["worker"] = wid
        append(ROWS2, res)
        print(f"{time.strftime('%H:%M:%S')} w{wid} job {j} {job['kind']} {job['clock']} "
              f"{res.get('seconds')}s", flush=True)


def reset_claims():
    """After an interruption (no worker running): keep only claims that
    produced a row, so unfinished tasks and jobs are taken again."""
    with locked():
        done = sorted({r["index"] for r in read_rows(ROWS)})
        json.dump(done, open(CLAIMS, "w"))
        done2 = sorted({r["job"] for r in read_rows(ROWS2)})
        json.dump(done2, open(os.path.join(LOG, "claims2.json"), "w"))
    print(json.dumps({"rows": len(done), "phase2_rows": len(done2)}))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "reset_claims":
        reset_claims()
    elif cmd == "prepare":
        prepare()
    elif cmd == "worker":
        worker(int(sys.argv[2]))
    elif cmd == "plan2":
        plan2()
    elif cmd == "repeat":
        repeat(int(sys.argv[2]))
    elif cmd == "analyze":
        import v19_audit_analyze
        v19_audit_analyze.main()
    else:
        sys.exit(__doc__)
