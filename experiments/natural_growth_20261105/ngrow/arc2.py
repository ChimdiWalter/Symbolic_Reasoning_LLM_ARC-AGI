"""Phase 2 only (refused without the GO): the one-shot check on the ARC-AGI-2 public evaluation set.

    python -I run.py arc2 GROW_DIR HELD_DIR OUT_DIR ARM          ARM in G0, growth, static

Data: `outputs/score_first/data/arc-agi_evaluation_challenges.json` (sha256 e7c62a4b..., 120 tasks, 172 test
inputs); its solutions are opened only by the scorer, after every arm has finished. Exposure: this set was used in
earlier development and gates of the project, so it is not a fresh test.
Arms, each applied once:
  G0      G0, base search (150,000 executions, 20 CPU-s), two attempts
  growth  G0 + the union of the three benchmarks' frozen S-hole registries (ConceptARC, Mini-ARC, 1D-ARC order; each
          in its own order; repeats dropped), base search
  static  G0 with no execution limit and a CPU-time cap of T_pooled CPU-s per task, T_pooled = the three benchmarks'
          growth totals summed / their held tasks summed (the held-half matched allowance, pooled)
If the union is empty, growth's grammar is G0 and its results are G0's.
"""
import json
import os
import sys
import time

from ngrow import env as E, data as DT, plugin as PL, gate as GT, held as HL, score as SC
from cgrow import search as S                                                   # noqa: E402


def challenges():
    GT.require_phase2()
    if E.sha_file(SC.ARC2_CHALLENGES) != SC.ARC2_SHA256["arc-agi_evaluation_challenges.json"]:
        raise RuntimeError("ARC-AGI-2 evaluation challenges changed")
    with open(SC.ARC2_CHALLENGES, encoding="utf-8") as f:
        ch = json.load(f)
    return {t: {"train": [(DT.grid(p["input"]), DT.grid(p["output"])) for p in v["train"]],
                "test_inputs": [DT.grid(p["input"]) for p in v["test"]]} for t, v in sorted(ch.items())}


def union_registry(grow_dir):
    out = []
    for b in DT.BENCHMARKS:
        for sid in HL.registry(grow_dir, b, "S-hole"):
            if sid not in out:
                out.append(sid)
    return out


def pooled_allowance(held_dir):
    tot, n = 0.0, 0
    for b in DT.BENCHMARKS:
        a = E.load(os.path.join(held_dir, b, "STATIC_ALLOWANCE.json"))
        tot += a["total_cpu_s"]
        n += a["n_held"]
    return {"total_cpu_s": round(tot, 3), "n_held": n, "t_pooled_cpu_s": round(tot / n, 3)}


def run(grow_dir, held_dir, out_dir, arm):
    tasks = challenges()
    path = os.path.join(out_dir, "arc2", f"{arm}.jsonl")
    done = HL.read_jsonl(path)
    g0b = PL.G0Builder()
    reg = union_registry(grow_dir)
    allowance = pooled_allowance(held_dir) if arm == "static" else None
    if allowance:
        E.dump(os.path.join(out_dir, "arc2", "STATIC_ALLOWANCE.json"), allowance)
    g0_rows = None
    if arm == "growth" and not reg:
        g0_rows = HL.read_jsonl(os.path.join(out_dir, "arc2", "G0.jsonl"))
        if len(g0_rows) != len(tasks):
            raise SystemExit("G0 runs incomplete")
    grammar = PL.grammar_with(g0b, reg) if arm == "growth" and reg else None
    for tid, t in tasks.items():
        if tid in done:
            continue
        t0 = time.process_time()
        row = {"task": tid, "arm": arm, "registry": reg if arm == "growth" else None}
        if arm == "G0":
            r = S.run(g0b(), t["train"], t["test_inputs"], budget=S.BASE_BUDGET, cpu_cap=S.BASE_CPU,
                      want=2)
        elif arm == "growth" and grammar is None:
            r = dict(g0_rows[tid])
            row["same_grammar_as"] = "G0"
        elif arm == "growth":
            r = S.run(grammar, t["train"], t["test_inputs"], budget=S.BASE_BUDGET, cpu_cap=S.BASE_CPU,
                      want=2)
        else:
            r = HL.child_search(t, allowance["t_pooled_cpu_s"])
        for k in ("fit", "preds", "program", "cpu_s", "calls", "stop", "level_complete"):
            row[k] = r.get(k)
        row["wall_cpu_s"] = round(time.process_time() - t0, 3)
        with E.open_write(path, "a") as f:
            f.write(json.dumps(row, default=list) + "\n")
        print(json.dumps({"task": tid, "arm": arm, "fit": row["fit"], "cpu_s": row["cpu_s"]}), flush=True)


def main(grow_dir, held_dir, out_dir, arm):
    run(os.path.abspath(grow_dir), os.path.abspath(held_dir), os.path.abspath(out_dir), arm)


if __name__ == "__main__":
    main(*sys.argv[1:])
