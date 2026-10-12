"""P3 synthetic safety preflight (docs/CORA_P3_SAFETY_PREFLIGHT_v1.md); synthetic
tasks only, no ARC data.

  python scripts/p3_preflight.py freeze      -> outputs/p3/p3_manifest.json (refuses if it exists)
  python scripts/p3_preflight.py run         -> outputs/p3/preflight_rows.jsonl (ONCE; refuses if rows exist)
  python scripts/p3_preflight.py summarize   -> outputs/p3/preflight_summary.json (gates S1, S2)

41 tasks (24 negative controls + 17 adversarial), arms BASE, BASE_REPEAT and P3,
the engine's own induction (train-exact + its own leave-one-out) at 20 s, a
pool of 4 workers, tasks interleaved. Exposure is fixed statically before the
run: EXPOSED if dedup admits a view in the full set or a 2-pair fold.
"""
import dataclasses
import hashlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))
OUT = os.path.join(HERE, "outputs", "p3")
MANIFEST = os.path.join(OUT, "p3_manifest.json")
ROWS = os.path.join(OUT, "preflight_rows.jsonl")
BUDGET_S = 20.0
ARMS = ("BASE", "BASE_REPEAT", "P3")
PINNED = ["cora_p3/__init__.py", "cora_p3/dedup.py", "cora_p3/induce_candidate_p3.py", "scripts/build_p3.py",
          "tests/test_p3.py", "docs/CORA_P3_SAFETY_PREFLIGHT_v1.md", "outputs/p3/adversarial_corpus.json",
          "scripts/p3_adversarial_corpus.py", "scripts/loo_v1_probe_negative.py", "scripts/p3_preflight.py",
          "scripts/loo_v1_probe_equivalence.py", "geocat_arc/object_reasoning/inducer.py",
          "geocat_arc/object_reasoning/segmentation.py", "geocat_arc/object_reasoning/correspondence.py"]


def _sha(rel):
    with open(os.path.join(HERE, rel), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def tasks():
    import loo_v1_probe_negative as NEG
    out = [{"id": t["id"], "source": "negative_control", "family": t["family"],
            "train": [(a.tolist(), b.tolist()) for a, b in t["train"]],
            "heldout": [(a.tolist(), b.tolist()) for a, b in t["heldout"]]} for t in NEG.tasks()]
    corpus = json.load(open(os.path.join(OUT, "adversarial_corpus.json")))["corpus"]
    out += [{"id": "ADV:" + t["id"], "source": "adversarial", "family": t["adversarial_family"],
             "train": t["train"], "heldout": t["heldout"]} for t in corpus]
    return out


def exposure(t):
    import loo_v1_probe_equivalence as EQ
    train = [(np.asarray(a), np.asarray(b)) for a, b in t["train"]]
    _, rec = EQ.task_record((t["id"], train, [(0, 1, 2), (0, 1), (0, 2), (1, 2)], False))
    admits = {k: r["dedup_admits"] for k, r in rec["subsets"].items() if r["dedup_admits"]}
    drops = {k: r["dedup_drops"] for k, r in rec["subsets"].items() if r["dedup_drops"]}
    return {"exposed": bool(admits), "admits": admits, "drops": drops}


def freeze():
    if os.path.exists(MANIFEST):
        raise SystemExit("manifest exists: the preflight is frozen")
    check = subprocess.run([sys.executable, os.path.join(HERE, "scripts", "build_p3.py"), "--check"],
                           capture_output=True, text=True)
    if check.returncode:
        raise SystemExit("build check failed: " + check.stdout + check.stderr)
    ts = tasks()
    expo = {t["id"]: exposure(t) for t in ts}
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    m = {"protocol": "docs/CORA_P3_SAFETY_PREFLIGHT_v1.md", "head": head, "budget_s": BUDGET_S, "arms": ARMS,
         "files": {r: _sha(r) for r in PINNED}, "tasks": [t["id"] for t in ts],
         "tasks_sha256": hashlib.sha256(json.dumps(ts, sort_keys=True).encode()).hexdigest(),
         "exposure": expo, "exposed": sorted(k for k, v in expo.items() if v["exposed"])}
    with open(MANIFEST, "w") as handle:
        json.dump(m, handle, indent=1, sort_keys=True)
    print(json.dumps({"head": head, "tasks": len(ts), "exposed": len(m["exposed"])}))


def problems():
    m = json.load(open(MANIFEST))
    bad = [r for r, h in m["files"].items() if _sha(r) != h]
    if hashlib.sha256(json.dumps(tasks(), sort_keys=True).encode()).hexdigest() != m["tasks_sha256"]:
        bad.append("tasks")
    return bad


def _program_sha(p):
    return hashlib.sha256(json.dumps(p.to_dict(), sort_keys=True, default=repr).encode()).hexdigest()[:16]


def job(args):
    t, arm = args
    import contextlib
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.actions import program_apply_fn
    from geocat_arc.object_reasoning.types import to_grid_pairs
    from cora_p3.dedup import p3
    train = to_grid_pairs([(np.asarray(a), np.asarray(b)) for a, b in t["train"]])
    ctx = p3() if arm == "P3" else contextlib.nullcontext({})
    c0, w0 = time.process_time(), time.time()
    with ctx as ev:
        res = I.induce_program(train, I.InductionConfig(budget_s=BUDGET_S))
        preds = None
        if res.accepted and res.program is not None:
            fn = program_apply_fn(res.program)
            preds = []
            for a, b in t["heldout"]:
                try:
                    preds.append(bool((np.asarray(fn(np.asarray(a))) == np.asarray(b)).all()))
                except Exception:                                   # noqa: BLE001
                    preds.append(False)
        events = dict(ev) if arm == "P3" else {}
    cpu, wall = time.process_time() - c0, time.time() - w0
    retag = retag_audit(res.program, train, t) if arm == "BASE" and res.accepted and res.program is not None else None
    p = res.program
    inner = p
    while inner is not None and hasattr(inner, "inner"):
        inner = inner.inner
    return {"task": t["id"], "arm": arm, "accepted": bool(res.accepted),
            "outcome": "REJECT" if not res.accepted else ("CORRECT" if all(preds) else "FALSE_ACCEPT"),
            "heldout_exact": preds, "program_sha": _program_sha(p) if p is not None else None,
            "program_variant": getattr(getattr(inner, "segmentation_variant", None), "value", None),
            "stage": getattr(res.failure_stage, "value", None),
            "loo": {"folds": res.loo.folds, "passed": res.loo.passed} if res.loo is not None else None,
            "induction_s": round(float(res.induction_time_s), 3), "cpu_s": round(cpu, 3), "wall_s": round(wall, 3),
            "budget_exhausted": bool(res.induction_time_s >= BUDGET_S or any("BUDGET" in e.upper() for e in res.events)),
            "p3_events": {k: v for k, v in events.items() if k != "log"}, "retag_audit": retag}


def retag_audit(program, train, t):
    """Audit only: the accepted program re-tagged with every view INDUCTION-equal to its own on the
    training set, executed on the held-out inputs (does training equivalence carry to unseen inputs?)."""
    import geocat_arc.object_reasoning.inducer as I
    from geocat_arc.object_reasoning.actions import program_apply_fn
    from cora_p3.dedup import signature
    if "segmentation_variant" not in {f.name for f in dataclasses.fields(program)} if dataclasses.is_dataclass(program) else True:
        return {"applicable": False}
    own = program.segmentation_variant
    segs = {v: I.evaluate_variant(v, train) for v in I.SEGMENTATION_TRIAL_ORDER}
    if not segs[own].coherent:
        return {"applicable": False}
    sig = signature(segs[own], train)
    out = {"applicable": True, "own": own.value, "equivalent": {}}

    def run(prog):
        fn = program_apply_fn(prog)
        res = []
        for a, _b in t["heldout"]:
            try:
                res.append(np.asarray(fn(np.asarray(a))).tolist())
            except Exception:                                       # noqa: BLE001
                res.append(None)
        return res
    base = run(program)
    for v, r in segs.items():
        if v is own or not r.coherent or signature(r, train) != sig:
            continue
        other = run(dataclasses.replace(program, segmentation_variant=v))
        out["equivalent"][v.value] = {"same_predictions": other == base,
                                      "exact": [o == np.asarray(b).tolist() for o, (_a, b) in zip(other, t["heldout"])]}
    return out


def run():
    if os.path.exists(ROWS):
        raise SystemExit("rows exist: the preflight runs once")
    bad = problems()
    if bad:
        raise SystemExit(f"freeze problems: {bad}")
    ts = tasks()
    jobs = [(t, arm) for t in ts for arm in ARMS]
    t0 = time.time()
    with mp.get_context("fork").Pool(4) as pool, open(ROWS, "w") as handle:
        for row in pool.imap(job, jobs, chunksize=1):
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()
    with open(os.path.join(OUT, "PREFLIGHT_DONE"), "w") as handle:
        handle.write(json.dumps({"rows": len(jobs), "wall_s": round(time.time() - t0, 1),
                                 "freeze_problems_after": problems()}) + "\n")


RANK = {"CORRECT": 2, "REJECT": 1, "FALSE_ACCEPT": 0}


def summarize():
    m = json.load(open(MANIFEST))
    rows = [json.loads(x) for x in open(ROWS) if x.strip()]
    by = {}
    for r in rows:
        by.setdefault(r["task"], {})[r["arm"]] = r
    S1, S2, unstable, per = [], [], [], {}
    for tid in m["tasks"]:
        b, b2, p = by[tid]["BASE"], by[tid]["BASE_REPEAT"], by[tid]["P3"]
        stable = b["outcome"] == b2["outcome"] and b["program_sha"] == b2["program_sha"]
        ref = max((b["outcome"], b2["outcome"]), key=RANK.get)
        if not stable:
            unstable.append(tid)
        exposed = m["exposure"][tid]["exposed"]
        if p["outcome"] == "FALSE_ACCEPT" and ref != "FALSE_ACCEPT":
            S1.append((tid, "new false acceptance"))
        if ref == "CORRECT" and p["outcome"] != "CORRECT":
            S1.append((tid, f"regression CORRECT -> {p['outcome']}"))
        if not exposed and stable and (p["program_sha"], p["accepted"], p["outcome"]) != \
                (b["program_sha"], b["accepted"], b["outcome"]):
            S2.append(tid)
        per[tid] = {"exposed": exposed, "stable": stable, "base": b["outcome"], "base_repeat": b2["outcome"],
                    "p3": p["outcome"], "program_changed": p["program_sha"] != b["program_sha"],
                    "variant": [b["program_variant"], p["program_variant"]],
                    "p3_dropped_views": p["p3_events"].get("dropped_views")}
    arm_tot = {a: {"cpu_s": round(sum(r["cpu_s"] for r in rows if r["arm"] == a), 1),
                   "wall_s": round(sum(r["wall_s"] for r in rows if r["arm"] == a), 1),
                   "budget_exhausted": sum(r["budget_exhausted"] for r in rows if r["arm"] == a),
                   "outcomes": {o: sum(1 for r in rows if r["arm"] == a and r["outcome"] == o) for o in RANK}}
               for a in ARMS}
    newly_correct = sorted(t for t, v in per.items() if v["p3"] == "CORRECT" and "CORRECT" not in (v["base"], v["base_repeat"]))
    out = {"S1_violations": S1, "S2_violations": S2, "S1_pass": not S1, "S2_pass": not S2,
           "label": "P3_SYNTHETIC_PREFLIGHT_PASS" if not S1 and not S2 else "P3_REJECTED",
           "unstable": unstable, "newly_correct": newly_correct,
           "program_identity_changes": sorted(t for t, v in per.items() if v["program_changed"]),
           "arms": arm_tot, "per_task": per, "freeze_problems": problems()}
    with open(os.path.join(OUT, "preflight_summary.json"), "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in ("label", "S1_violations", "S2_violations", "unstable", "newly_correct",
                                          "program_identity_changes", "arms", "freeze_problems")}, indent=1))


if __name__ == "__main__":
    {"freeze": freeze, "run": run, "summarize": summarize}[sys.argv[1]]()
