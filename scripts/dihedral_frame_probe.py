#!/usr/bin/env python3
"""Idea 1 (docs/EXTERNAL_IDEAS_2026_07.md): dihedral-frame induction.

For each unsolved task, run the FULL induction (gate included) on the 7
non-identity dihedral transforms of its train pairs.  A program certified
in frame T solves the task: prediction = T_inv(render(program, T(test))).
Pure geometry — no task-specific code; every frame is an independent
complete run of the LOO gate.  Deterministic frame order; first certified
frame wins.

Usage: dihedral_frame_probe.py [budget_per_frame=45] [workers=8]
Writes outputs/dihedral_frame_probe.json (resumable via done-file).
"""
import json, os, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, ".")

BUDGET = float(sys.argv[1]) if len(sys.argv) > 1 else 45.0
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
OUT = "outputs/dihedral_frame_probe.json"
DONE = "outputs/dihedral_frame_done.jsonl"

# dihedral group as (k_rot90, flip) pairs applied as: flip then rot
FRAMES = [(1, False), (2, False), (3, False),
          (0, True), (1, True), (2, True), (3, True)]


def _tf(grid_list, k, flip):
    import numpy as np
    a = np.array(grid_list)
    if flip:
        a = np.fliplr(a)
    return np.rot90(a, k).tolist()


def _tf_inv(grid_list, k, flip):
    import numpy as np
    a = np.array(grid_list)
    a = np.rot90(a, -k)
    if flip:
        a = np.fliplr(a)
    return a.tolist()


def run_one(tid):
    from geocat_arc.perception.grid import Grid
    from geocat_arc.object_reasoning.inducer import induce_program, InductionConfig
    from geocat_arc.object_reasoning.actions import render_program
    from geocat_arc.object_reasoning import correspondence as C
    from geocat_arc.object_reasoning.synth_verbs import LearnedVerbRegistry
    try:
        C.set_learned_verbs(LearnedVerbRegistry(
            json.load(open("outputs/learned_verbs/learned_verbs.json"))))
    except Exception:
        pass
    chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
    sols = json.load(open("data/arc/arc-agi_training_solutions.json"))
    task = chal[tid]
    for (k, flip) in FRAMES:
        pairs = [(Grid.from_list(_tf(p["input"], k, flip)),
                  Grid.from_list(_tf(p["output"], k, flip)))
                 for p in task["train"]]
        try:
            res = induce_program(pairs, InductionConfig(budget_s=BUDGET))
        except Exception:
            continue
        if res.accepted:
            try:
                oks = []
                for ti, tc in enumerate(task["test"]):
                    pred_t = render_program(
                        res.program,
                        Grid.from_list(_tf(tc["input"], k, flip)))
                    pred = _tf_inv(pred_t.to_list(), k, flip)
                    oks.append(pred == sols[tid][ti])
                return tid, f"rot{90*k}{'+flip' if flip else ''}", all(oks)
            except Exception:
                return tid, f"rot{90*k}{'+flip' if flip else ''}", False
    return tid, None, None


def main():
    chal = json.load(open("data/arc/arc-agi_training_challenges.json"))
    v16 = {r["task_id"] for r in
           json.load(open("outputs/unified_harness_v16/results.json"))["solved"]}
    done = set()
    if os.path.exists(DONE):
        for line in open(DONE):
            done.add(json.loads(line)["tid"])
    tids = [t for t in sorted(chal) if t not in v16 and t not in done]
    print(f"dihedral probe: {len(tids)} tasks x 7 frames x {BUDGET}s "
          f"({len(done)} already done)", flush=True)
    flips = []
    n = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run_one, t): t for t in tids}
        for fut in as_completed(futs):
            n += 1
            try:
                tid, frame, ok = fut.result()
            except Exception as e:
                print(f"[{n}/{len(tids)}] {futs[fut]} CRASH {e}", flush=True)
                continue
            with open(DONE, "a") as f:
                f.write(json.dumps({"tid": tid, "frame": frame, "ok": ok}) + "\n")
            if frame is not None:
                flips.append((tid, frame, ok))
                print(f"[{n}/{len(tids)}] {tid} CERTIFIED frame={frame} "
                      f"test={ok}", flush=True)
            elif n % 50 == 0:
                print(f"[{n}/{len(tids)}] ...", flush=True)
    json.dump({"flips": flips}, open(OUT, "w"), indent=1)
    print(f"PROBE COMPLETE: {len(flips)} certified: {flips}", flush=True)


if __name__ == "__main__":
    main()
