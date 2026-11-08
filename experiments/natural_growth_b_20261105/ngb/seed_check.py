"""Hash-seed check: the enumeration order of the study's grammar does not depend on the interpreter's hash seed.

    python -I run.py seed_check OUT_JSON            (the probes themselves run without -I, see below)
    python -s -B run.py seed_probe MODE TASK...     one probe process (MODE: sorted or plain)

`python -I` implies -E, which ignores PYTHONHASHSEED, so a seed cannot be fixed under -I. This check runs each probe
in a child interpreter started with `-s -B` (no -E) and PYTHONHASHSEED set to 0, 1 and 2, on the study's own
trusted code only. For three probe tasks of the source halves it runs the base search and, on failure, the search
at 4x, and records the fit, the program text, the two attempts' digest, the executions, the completed level and the
closest program:
  sorted   this study's grammar (ngb.ops.G0Builder: every production's argument tags iterate in sorted order);
  plain    study A's grammar as it stands (a frozenset's iteration order depends on the seed).
Pass: under "sorted" every recorded field is identical across the three seeds (the order is seed-independent);
"plain" is reported for contrast (the program text may differ; fits and predictions are compared too). Each child
also reports hash("seed-check") so that the seeds are seen to differ.
Construction probes (amendment 2): the builder's construction answers (arm 7's call, with this study's sorted
builder and the benchmark's frozen registry) on three source tasks that reach the constructor (ConceptARC co0003,
Mini-ARC mi0002, and the first 1D-ARC 1d_mirror source task the builder's reuse record does not fit), under seeds 0,
1 and 2; pass when fit, stage, the constructed operation, the predictions' digest and the candidate counts are
identical across the seeds.
"""
import hashlib
import json
import os
import subprocess
import sys

from ngb import env as E
from ngrow import data as DT, plugin as PL
from cgrow import search as S
from a2 import arcdsl as D

RUN = os.path.join(E.STUDY, "run.py")
PROBES = (("mini_arc", "mi0048"), ("concept_arc", "co0126"), ("1d_arc", "1d0053"))
SEEDS = ("0", "1", "2")


def probe(mode, pairs):
    from ngb import ops as OP
    g0b = OP.G0Builder() if mode == "sorted" else PL.G0Builder()
    out = {"mode": mode, "hash_seed_witness": hash("seed-check") & 0xFFFFFFFF, "ignore_environment":
           sys.flags.ignore_environment, "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"), "tasks": {}}
    for b, t in pairs:
        task = DT.tasks(b)[t]
        r = S.run(g0b(), task["train"], task["test_inputs"], track_partial=True)
        found = "base"
        if not r["fit"]:
            r2 = S.run(g0b(), task["train"], task["test_inputs"], budget=S.BASE_BUDGET * 4, cpu_cap=S.BASE_CPU * 4)
            found = "x4" if r2["fit"] else None
            part = r.get("partial")
            r = r2 if r2["fit"] else r
            if part and not r2["fit"]:
                r["partial"] = part
        out["tasks"][t] = {"found_at": found, "fit": r["fit"], "program": r["program"],
                           "preds_sha256": hashlib.sha256(repr(r["preds"]).encode()).hexdigest() if r["preds"] else None,
                           "calls": r["calls"], "level_complete": r["level_complete"], "stop": r["stop"],
                           "closest": (D.show(r["partial"]["tree"]) if r.get("partial") else None)}
    print("PROBE " + json.dumps(out, sort_keys=True), flush=True)


def construction_tasks():
    from ngb import object_arm as OA
    reuse = E.load(os.path.join(OA.folder(), "runs", "v2", "1d_arc", "reuse.json"))["tasks"]
    mirror = sorted(t for t, v in reuse.items() if v["family"] == "1d_mirror" and not v["grown_fit"])
    return [("concept_arc", "co0003"), ("mini_arc", "mi0002"), ("1d_arc", mirror[0])]


def probe_construct(pairs):
    from ngb import object_arm as OA
    out = {"hash_seed_witness": hash("seed-check") & 0xFFFFFFFF, "ignore_environment": sys.flags.ignore_environment,
           "tasks": {}}
    for b, t in pairs:
        task = DT.tasks(b)[t]
        r = OA.construct(task, OA.ops(b))
        op = r.get("op")
        out["tasks"][t] = {"fit": r.get("fit"), "stage": r.get("stage"),
                           "op": op.get("sid") if isinstance(op, dict) else op,
                           "preds_sha256": hashlib.sha256(repr(r.get("preds")).encode()).hexdigest() if r.get("preds") else None,
                           "candidates": r.get("candidates"), "candidates_loo": r.get("candidates_loo"),
                           "retries": [x.get("sid") for x in r.get("retries", [])]}
    print("CPROBE " + json.dumps(out, sort_keys=True), flush=True)


def main(out_path):
    results = {}
    for mode in ("sorted", "plain"):
        for seed in SEEDS:
            env = dict(os.environ, PYTHONHASHSEED=seed)
            p = subprocess.run([sys.executable, "-s", "-B", RUN, "seed_probe", mode] + [f"{b}:{t}" for b, t in PROBES],
                               capture_output=True, text=True, env=env, cwd=E.STUDY)
            line = [x for x in p.stdout.splitlines() if x.startswith("PROBE ")]
            if p.returncode != 0 or not line:
                raise SystemExit(f"probe failed ({mode}, seed {seed}): {p.stderr[-500:]}")
            results[f"{mode}/seed{seed}"] = json.loads(line[-1][6:])
    def same(mode, field):
        vals = [json.dumps({t: v.get(field) for t, v in results[f"{mode}/seed{s}"]["tasks"].items()}, sort_keys=True)
                for s in SEEDS]
        return len(set(vals)) == 1
    fields = ("found_at", "fit", "program", "preds_sha256", "calls", "level_complete", "stop", "closest")
    summary = {"seeds_differ": len({results[f"sorted/seed{s}"]["hash_seed_witness"] for s in SEEDS}) == 3,
               "ignore_environment_in_probes": [results[f"sorted/seed{s}"]["ignore_environment"] for s in SEEDS],
               "sorted_identical_across_seeds": {f: same("sorted", f) for f in fields},
               "plain_identical_across_seeds": {f: same("plain", f) for f in fields},
               "sorted_vs_plain_fits_and_predictions_agree": all(
                   results[f"sorted/seed{s}"]["tasks"][t][f] == results[f"plain/seed{s}"]["tasks"][t][f]
                   for s in SEEDS for t in results["sorted/seed0"]["tasks"] for f in ("found_at", "fit", "preds_sha256"))}
    cpairs = construction_tasks()
    cres = {}
    for seed in SEEDS:
        env = dict(os.environ, PYTHONHASHSEED=seed)
        p = subprocess.run([sys.executable, "-s", "-B", RUN, "seed_probe_construct"] + [f"{b}:{t}" for b, t in cpairs],
                           capture_output=True, text=True, env=env, cwd=E.STUDY)
        line = [x for x in p.stdout.splitlines() if x.startswith("CPROBE ")]
        if p.returncode != 0 or not line:
            raise SystemExit(f"construction probe failed (seed {seed}): {p.stderr[-500:]}")
        cres[f"seed{seed}"] = json.loads(line[-1][7:])
    cvals = [json.dumps(cres[f"seed{s}"]["tasks"], sort_keys=True) for s in SEEDS]
    summary["construction_probes"] = [f"{b}:{t}" for b, t in cpairs]
    summary["construction_seeds_differ"] = len({cres[f"seed{s}"]["hash_seed_witness"] for s in SEEDS}) == 3
    summary["construction_identical_across_seeds"] = len(set(cvals)) == 1
    summary["construction_reached"] = {t: v["stage"] for t, v in cres["seed0"]["tasks"].items()}
    summary["pass"] = summary["seeds_differ"] and all(summary["sorted_identical_across_seeds"].values()) and \
        summary["construction_identical_across_seeds"]
    E.dump(os.path.abspath(out_path), {"summary": summary, "probes": [f"{b}:{t}" for b, t in PROBES],
                                       "results": results, "construction_results": cres})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
