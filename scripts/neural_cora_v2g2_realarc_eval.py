"""The ncv2-g2 real-ARC engineering check on an eligibility-checked cohort.
Protocol: records/NEURAL_CORA_V2G2_REALARC_PROTOCOL_20261020.md. The `solve` and `native` stages refuse to run until
that protocol and its manifest are committed unchanged and the user authorizes the run.

    python scripts/neural_cora_v2g2_realarc_eval.py freeze               # the manifest (code, cohort, inputs)
    python scripts/neural_cora_v2g2_realarc_eval.py solve --authorized   # ncv2-g1 and ncv2-g2: demonstrations + test inputs
    python scripts/neural_cora_v2g2_realarc_eval.py native --authorized  # native CORA v23, the unchanged funnel harness
    python scripts/neural_cora_v2g2_realarc_eval.py score                # evaluator: the sha-pinned solutions file

**Cohort:**
- PRIMARY: the 40 eligible tasks of the 2026-10-20 check
  (`outputs/neural_cora_v2g2/realarc/eligibility/eligible_ids_20261020.json`).
- LEFTOVER (descriptive only): the 4 eligible tasks of the 2026-10-19 check that Phase 2a did not use.

The ncv2 arms score the first test output, as G2 did. Native is scored with its own `cora_funnel.evaluate.task_record`
(all test outputs) and also on the first test output, for pairing.
"""
import argparse
import glob
import hashlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
OUT = os.path.join(HERE, "outputs", "neural_cora_v2g2", "realarc")
PROTOCOL = os.path.join("records", "NEURAL_CORA_V2G2_REALARC_PROTOCOL_20261020.md")
MANIFEST = os.path.join("records", "NEURAL_CORA_V2G2_REALARC_FREEZE_MANIFEST.json")
SYNTH_MANIFEST = os.path.join("records", "NEURAL_CORA_V2G2_SYNTHETIC_FREEZE_MANIFEST.json")
ELIG_NEW = os.path.join("outputs", "neural_cora_v2g2", "realarc", "eligibility", "eligible_ids_20261020.json")
ELIG_OLD = os.path.join("outputs", "cora_revision_v2", "eligibility", "eligible_ids_20261019.json")
BUDGET, CPU_CAP_S, WORKERS, NICE = 3000, 120.0, 2, 10
CODE = ["cora_neural_v2/*.py", "cora_neural_v2g2/*.py", "cora_funnel/*.py", "scripts/neural_cora_v2g2_realarc_eval.py"]
INPUTS = [ELIG_NEW, ELIG_OLD]


def sha(p):
    return hashlib.sha256(open(os.path.join(HERE, p), "rb").read()).hexdigest()


def code_hashes():
    return {os.path.relpath(f, HERE): sha(os.path.relpath(f, HERE)) for pat in CODE for f in sorted(glob.glob(os.path.join(HERE, pat)))}


def native_aggregate():
    files = sorted(os.path.relpath(f, HERE) for f in glob.glob(os.path.join(HERE, "geocat_arc/**/*.py"), recursive=True) if "__pycache__" not in f)
    return hashlib.sha256("".join(f"{f}:{sha(f)}\n" for f in files).encode()).hexdigest()


def cohort():
    new = json.load(open(os.path.join(HERE, ELIG_NEW)))
    old = json.load(open(os.path.join(HERE, ELIG_OLD)))
    assert new["attestation"]["status"] == "PASS" and old["attestation"]["status"] == "PASS"
    return [(t, "primary") for t in new["eligible_ids"]] + [(t, "leftover") for t in old["eligible_ids"][40:]]   # Phase 2a used the first 40


def tasks():
    from cora_pilot import bundle as B
    ch = B.load_challenges()                                       # sha-pinned; demonstrations and test inputs only
    out = []
    for t, stratum in cohort():
        c = ch[t]
        out.append({"task_id": t, "stratum": stratum, "train": [(p["input"], p["output"]) for p in c["train"]],
                    "test_inputs_all": [p["input"] for p in c["test"]], "test_inputs": [c["test"][0]["input"]]})
    return out


def freeze():
    syn = json.load(open(os.path.join(HERE, SYNTH_MANIFEST)))["code"]
    cur = code_hashes()
    gone = {k: v for k, v in syn.items() if k.startswith(("cora_neural_v2/", "cora_neural_v2g2/")) and cur.get(k) != v}
    if gone:
        sys.exit(f"not frozen: ncv2 code differs from the version that passed GO_ENGINEERING: {sorted(gone)}")
    v1 = json.load(open(os.path.join(HERE, "records", "NEURAL_CORA_V1_FREEZE_MANIFEST.json")))["groups"]["native_cora_v23_geocat_arc"]
    if native_aggregate() != v1["aggregate_sha256"]:
        sys.exit("not frozen: native CORA differs from the v1 freeze")
    T = tasks()
    man = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "code": cur, "native_aggregate_sha256": native_aggregate(),
           "inputs": {p: sha(p) for p in INPUTS}, "protocol_sha256": sha(PROTOCOL),
           "cohort": [[t["task_id"], t["stratum"]] for t in T], "n_primary": sum(t["stratum"] == "primary" for t in T),
           "n_leftover": sum(t["stratum"] == "leftover" for t in T), "n_multi_test": sum(len(t["test_inputs_all"]) > 1 for t in T),
           "settings": {"budget": BUDGET, "cpu_cap_s": CPU_CAP_S, "workers": WORKERS, "nice": NICE}}
    json.dump(man, open(os.path.join(HERE, MANIFEST), "w"), indent=1)
    print("frozen:", man["n_primary"], "primary +", man["n_leftover"], "leftover tasks;", man["n_multi_test"], "with several test inputs")


def check_lock():
    man = json.load(open(os.path.join(HERE, MANIFEST)))
    if man["code"] != code_hashes() or man["protocol_sha256"] != sha(PROTOCOL) or man["inputs"] != {p: sha(p) for p in INPUTS} \
            or man["native_aggregate_sha256"] != native_aggregate():
        sys.exit("locked: code, protocol, inputs or native CORA differ from the freeze manifest")
    for f in (PROTOCOL, MANIFEST):
        if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", f], cwd=HERE).returncode or \
                subprocess.run(["git", "ls-files", "--error-unmatch", f], cwd=HERE, capture_output=True).returncode:
            sys.exit(f"locked: {f} is not committed unchanged")
    return {"manifest_sha256": sha(MANIFEST),
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()}


def _job_g(task):
    if os.nice(0) < NICE:
        os.nice(NICE - os.nice(0))
    from cora_neural_v2 import search as S1
    from cora_neural_v2g2 import search as S2
    t = {k: task[k] for k in ("task_id", "train", "test_inputs")}
    keep = ("predictions", "pred_at", "attempts", "n_candidates", "n_consistent", "cpu_s", "state")
    r1, r2 = S1.search(t, BUDGET, cpu_cap_s=CPU_CAP_S), S2.search(t, BUDGET, cpu_cap_s=CPU_CAP_S)
    return {"task_id": task["task_id"], "stratum": task["stratum"], "g1": {k: r1[k] for k in keep},
            "g2": {**{k: r2[k] for k in keep}, "programs": r2["programs"], "first_fit_at": r2["first_fit_at"]}}


def _job_native(task):
    from cora_funnel import run as FR                               # the unchanged native harness (sealed v23 flags, CPU clock)
    t = {"train": [{"input": a, "output": b} for a, b in task["train"]], "test": [{"input": x} for x in task["test_inputs_all"]]}
    row = FR.job((task["task_id"], t, "realarc2x", "native"))
    row["stratum"] = task["stratum"]
    row["task_id"] = task["task_id"]
    return row


def run_pool(job, todo_tasks, path, init_env=None):
    done = {json.loads(l)["task_id"] for l in open(path)} if os.path.exists(path) else set()
    todo = [t for t in todo_tasks if t["task_id"] not in done]
    print(f"{os.path.basename(path)}: {len(todo)} to run, {len(done)} done", flush=True)
    with mp.get_context("fork").Pool(WORKERS, maxtasksperchild=1) as pool, open(path, "a") as fh:
        for i, row in enumerate(pool.imap_unordered(job, todo), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {row['task_id']}", flush=True)


def solve(a):
    lock = check_lock() if a.authorized else sys.exit("solve needs --authorized (see the protocol)")
    os.makedirs(OUT, exist_ok=True)
    json.dump({"lock": lock, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(os.path.join(OUT, "run_manifest_solve.json"), "w"), indent=1)
    run_pool(_job_g, tasks(), os.path.join(OUT, "rows_g.jsonl"))
    print("SOLVE_DONE", flush=True)


def native(a):
    lock = check_lock() if a.authorized else sys.exit("native needs --authorized (see the protocol)")
    os.environ["CORA_FUNNEL_NICE"] = str(NICE)                      # read by cora_funnel.run at import: workers at nice 10
    os.makedirs(OUT, exist_ok=True)
    json.dump({"lock": lock, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(os.path.join(OUT, "run_manifest_native.json"), "w"), indent=1)
    run_pool(_job_native, tasks(), os.path.join(OUT, "rows_native.jsonl"))
    print("NATIVE_DONE", flush=True)


def _eq(p, A):
    P = np.asarray(p)
    return P.shape == A.shape and bool((P == A).all())


def decide(s):
    """The frozen rule (protocol section 5), on the PRIMARY cohort."""
    g1, g2, pp = s["primary"]["g1"], s["primary"]["g2"], s["primary"]["paired_pass@2"]
    ok = (g2["pass@2"] - g1["pass@2"] >= 3 and g2["correct_coverage"] - g1["correct_coverage"] >= 3 and pp["losses"] <= 1)
    return "GO_REAL_COVERAGE" if ok else "NO_REAL_GAIN"


def score(a):
    from cora_funnel.evaluate import task_record
    from cora_pilot import bundle as B
    from cora_pilot import evaluator as EV
    sol = EV.load_pinned(B.SOLUTIONS, B.SOLUTIONS_SHA256)           # the only reader of test outputs
    man = json.load(open(os.path.join(HERE, MANIFEST)))
    if man["inputs"] != {p: sha(p) for p in INPUTS}:
        sys.exit("the cohort inputs differ from the freeze manifest")
    g = {json.loads(l)["task_id"]: json.loads(l) for l in open(os.path.join(OUT, "rows_g.jsonl"))}
    nat_path = os.path.join(OUT, "rows_native.jsonl")
    nat = {json.loads(l)["task_id"]: json.loads(l) for l in open(nat_path)} if os.path.exists(nat_path) else {}
    trains = {t["task_id"]: t["train"] for t in tasks()}
    per = []
    for t, stratum in man["cohort"]:
        ans_all = sol[t]
        A = np.asarray(ans_all[0])
        rec = {"task_id": t, "stratum": stratum, "n_test": len(ans_all)}
        for arm in ("g1", "g2"):
            r = g[t][arm]
            rec[arm] = {"fits": r["n_consistent"] > 0, "correct_coverage": any(_eq(p, A) for p in r["predictions"]),
                        "pass@2": any(_eq(p, A) for p in r["attempts"][:2]),
                        "wrong_attempts": bool(r["attempts"]) and not any(_eq(p, A) for p in r["attempts"][:2]),
                        "cpu_s": r["cpu_s"], "truncated": r["state"].get("cpu_truncated", False)}
        rec["g2"]["first_fit_at"] = g[t]["g2"]["first_fit_at"]
        rec["g2"]["correct_program"] = next((pr for p, pr in zip(g[t]["g2"]["predictions"], g[t]["g2"]["programs"]) if _eq(p, A)), None)
        if t in nat:
            n = nat[t]
            tr = task_record(n, ans_all, [{"input": x, "output": y} for x, y in trains[t]])
            sets = [e for e in n["events"] if e["type"] in ("search", "generative") and e["n_programs"] > 0]
            first_cov = any(o and _eq(o[0], A) for e in sets for o in (e["outputs"] or []))
            first_cert = bool(n["solved"]) and bool(n["predictions"]) and _eq(n["predictions"][0], A)
            rec["native"] = {"category": tr["category"], "fits": tr["train_exact_candidates"] > 0, "correct_coverage_first": first_cov,
                             "certified_correct_first": first_cert, "certified_correct_all": tr["correct"], "cpu_s": n["cpu_s"]}
        per.append(rec)

    def block(rows):
        out = {arm: {m: sum(r[arm][m] for r in rows) for m in ("fits", "correct_coverage", "pass@2", "wrong_attempts", "truncated")}
               for arm in ("g1", "g2")}
        gains = sorted(r["task_id"] for r in rows if r["g2"]["pass@2"] and not r["g1"]["pass@2"])
        losses = sorted(r["task_id"] for r in rows if r["g1"]["pass@2"] and not r["g2"]["pass@2"])
        out["paired_pass@2"] = {"gains": len(gains), "losses": len(losses), "gain_ids": gains, "loss_ids": losses}
        nr = [r for r in rows if "native" in r]
        if nr:
            out["native"] = {"n": len(nr), "fits": sum(r["native"]["fits"] for r in nr),
                             "correct_coverage_first": sum(r["native"]["correct_coverage_first"] for r in nr),
                             "certified_correct_first": sum(r["native"]["certified_correct_first"] for r in nr),
                             "certified_correct_all": sum(r["native"]["certified_correct_all"] for r in nr)}
            out["g2_vs_native_first"] = {"g2_only": sorted(r["task_id"] for r in nr if r["g2"]["pass@2"] and not r["native"]["certified_correct_first"]),
                                         "native_only": sorted(r["task_id"] for r in nr if r["native"]["certified_correct_first"] and not r["g2"]["pass@2"])}
        out["n"] = len(rows)
        out["cpu_s"] = {arm: round(sum(r[arm]["cpu_s"] for r in rows), 1) for arm in ("g1", "g2")}
        return out
    s = {"primary": block([r for r in per if r["stratum"] == "primary"]), "leftover": block([r for r in per if r["stratum"] == "leftover"]),
         "note": "public ARC-AGI-2 training tasks (seen by v23; in NVARC's training mix): development evidence, not unseen performance"}
    s["decision"] = decide(s)
    json.dump({"summary": s, "tasks": per}, open(os.path.join(OUT, "score.json"), "w"), indent=1)
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("freeze", "solve", "native", "score"))
    ap.add_argument("--authorized", action="store_true")
    args = ap.parse_args()
    {"freeze": lambda a: freeze(), "solve": solve, "native": native, "score": score}[args.stage](args)
