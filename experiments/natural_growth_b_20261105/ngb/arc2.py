"""Phase 2 only (refused without the GO): the one-shot check on the ARC-AGI-2 public evaluation set (amendment 2).

    python -I run.py arc2 LIB_DIR HELD_DIR OUT_DIR ARM
    ARM in G0, lib, obj, construct, static_lib, static_obj, static_construct

Data: study A's pinned `outputs/score_first/data/arc-agi_evaluation_challenges.json` (sha256 e7c62a4b..., 120 tasks,
172 test inputs); solutions opened by the scorer only, after every arm. Exposure: this set was used in earlier
development and gates of the project, and the first dry run of this study touched 95 of its tasks' inputs
(records/INCIDENT_20261105_DRY_RUN.md); it is not a fresh test.
Arms, each applied once: G0 (base search); lib: G0 plus the union of the three frozen libraries; obj: the builder's
reuse answers with the union of the three frozen object registries; construct: the builder's construction answers
on each task's own demonstrations with that union; static_lib, static_obj and static_construct: G0 at the pooled
held-half allowance of the matching arm (the three benchmarks' totals summed over their 464 held tasks). An empty
union means the arm's grammar is G0. Rows carry the same provenance as the held rows; every failure is a durable
row.
"""
import json
import os
import sys
import time
import traceback

from ngb import env as E, gate as GT, ops as OP, held as HB, object_arm as OA
from ngrow import data as DT
from cgrow import search as S

ARMS = ("G0", "lib", "obj", "construct", "static_lib", "static_obj", "static_construct")


def challenges():
    """The 120 evaluation tasks (demonstrations and test inputs), behind the GO; the dry run replaces this single
    entry point with source tasks. In rehearsal mode: the stand-in file of source tasks shipped in the rehearsal
    package (its digest checked by the gate)."""
    GT.require_go()
    if E.REHEARSAL:
        with open(os.path.join(E.STUDY, "rehearsal", "arc2_standin_challenges.json"), encoding="utf-8") as f:
            ch = json.load(f)
        return {t: {"train": [(DT.grid(p["input"]), DT.grid(p["output"])) for p in v["train"]],
                    "test_inputs": [DT.grid(p["input"]) for p in v["test"]]} for t, v in sorted(ch.items())}
    from ngrow import score as SA
    if E.sha_file(SA.ARC2_CHALLENGES) != SA.ARC2_SHA256["arc-agi_evaluation_challenges.json"]:
        raise RuntimeError("ARC-AGI-2 evaluation challenges changed")
    with open(SA.ARC2_CHALLENGES, encoding="utf-8") as f:
        ch = json.load(f)
    return {t: {"train": [(DT.grid(p["input"]), DT.grid(p["output"])) for p in v["train"]],
                "test_inputs": [DT.grid(p["input"]) for p in v["test"]]} for t, v in sorted(ch.items())}


def union_library(lib_dir, g0b):
    out, seen = [], set()
    for b in DT.BENCHMARKS:
        for o in HB.library_ops(lib_dir, b, "lib", g0b):
            if o.text not in seen:
                seen.add(o.text)
                out.append(o)
    return out


def pooled_allowance(held_dir, static_arm):
    """The three benchmarks' allowances, re-expressed in this kernel's CPU-seconds: each benchmark's source cost is
    unscaled from the kernel that measured its held CPU (its recorded factor) and rescaled by this kernel's factor
    (NGB_CPU_SCALE); the held CPU, measured on that kernel, is scaled by the ratio of the factors."""
    here = float(os.environ.get("NGB_CPU_SCALE", "1.0"))
    tot, n, parts = 0.0, 0, {}
    for b in DT.BENCHMARKS:
        a = E.load(os.path.join(held_dir, b, f"ALLOWANCE_{static_arm}.json"))
        there = float(a.get("cpu_scale", 1.0))
        src_athe = a["source_cost_cpu_s_scaled"] / there
        held_here = a["held_cpu_s"] * here / there
        parts[b] = {"source_cost_cpu_s_athe": round(src_athe, 3), "held_cpu_s_measured": a["held_cpu_s"],
                    "measured_on_factor": there, "n_held": a["n_held"]}
        tot += src_athe * here + held_here
        n += a["n_held"]
    return {"total_cpu_s_here": round(tot, 3), "n_held": n, "t_pooled_cpu_s": round(tot / n, 3),
            "cpu_scale_here": here, "parts": parts}


def run(lib_dir, held_dir, out_dir, arm):
    go_sha = GT.require_go()
    digests = {b: HB.bind_library(lib_dir, b) for b in DT.BENCHMARKS}
    tasks = challenges()
    path = os.path.join(out_dir, "arc2", f"{arm}.jsonl")
    done = HB.rows_by_task(path)
    g0b = OP.G0Builder()
    grammar, g0_rows, allow, reg = None, None, None, []
    if arm == "lib":
        reg = union_library(lib_dir, g0b)
        grammar = OP.grammar_with(g0b, reg) if reg else None
    elif arm in ("obj", "construct"):
        if not OA.available():
            raise RuntimeError("the object arms need the object-growth contract")
        reg = OA.union_ops()
    elif arm.startswith("static_"):
        allow = pooled_allowance(held_dir, arm)
        E.dump(os.path.join(out_dir, "arc2", f"ALLOWANCE_{arm}.json"), allow)
    if arm == "lib" and grammar is None:
        g0_rows = HB.rows_by_task(os.path.join(out_dir, "arc2", "G0.jsonl"))
        if any(t not in g0_rows for t in tasks):
            raise RuntimeError("G0 runs incomplete")
    scale = float(os.environ.get("NGB_CPU_SCALE", "1.0"))
    for tid, t in tasks.items():
        if tid in done:
            continue
        t0 = time.process_time()
        row = {"bench": "arc_agi_2_eval", "family": None, "task": tid, "arm": arm, "go_sha256": go_sha,
               "cpu_scale": scale, "registry_sha256": HB.registry_digest(reg) if reg else None,
               "library_sha256": {b: d["library"] for b, d in digests.items()}, "g0_sha256": g0b.sha}
        try:
            if arm == "G0":
                r = S.run(g0b(), t["train"], t["test_inputs"], budget=S.BASE_BUDGET, cpu_cap=S.BASE_CPU, want=2)
            elif arm == "lib" and grammar is not None:
                r = S.run(grammar, t["train"], t["test_inputs"], budget=S.BASE_BUDGET, cpu_cap=S.BASE_CPU, want=2)
            elif arm == "lib":
                r = dict(g0_rows[tid])
                row["same_grammar_as"] = "G0"
            elif arm == "obj":
                r = HB.builder_row(OA.reuse(t, reg))
            elif arm == "construct":
                r = HB.builder_row(OA.construct(t, reg))
            else:
                r = HB.child_search(t, allow["t_pooled_cpu_s"])
        except Exception as e:                                             # noqa: BLE001
            r = HB.failure("arm_error", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-300:]}")
        for k in HB.ROW_KEYS + ("failure_detail", "retries", "child_cpu_measured_s", "cpu_s_source") + HB.BUILDER_KEYS:
            if k in r:
                row[k] = r[k]
        for k in HB.ROW_KEYS:
            row.setdefault(k, None)
        row["wall_cpu_s"] = round(time.process_time() - t0, 3)
        if row["cpu_s"] is None:
            row["cpu_s"] = row["wall_cpu_s"]
            row["child_cpu_unknown"] = str(row["stop"]).startswith("child_")
        with E.open_write(path, "a") as f:
            f.write(json.dumps(row, default=list) + "\n")
        print(json.dumps({"task": tid, "arm": arm, "fit": row["fit"], "stop": row["stop"], "cpu_s": row["cpu_s"]}),
              flush=True)


def main(lib_dir, held_dir, out_dir, arm):
    run(os.path.abspath(lib_dir), os.path.abspath(held_dir), os.path.abspath(out_dir), arm)


if __name__ == "__main__":
    main(*sys.argv[1:])
