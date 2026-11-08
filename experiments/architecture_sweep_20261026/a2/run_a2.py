"""A2 staged runner (each stage resumable; launch detached through the CPU slot, see PROGRESS.md).

    python -m a2.run_a2 traces      base-grammar search on S_train programmed tasks -> reachability traces
    python -m a2.run_a2 pools       candidate pools (compression, authentic, shuffled, blind) + fold pools
    python -m a2.run_a2 labels      held-out-fold labels and features for the ranker
    python -m a2.run_a2 ranker      train the abstraction ranker (GPU 0 under flock; 3 seeds)
    python -m a2.run_a2 libraries   select K definitions per arm, gate, matched control
    python -m a2.run_a2 eval COHORT search every arm on a cohort (S_select_A, S_select_B, E_trainU, ARC_eval_dev)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP]
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
from harness import data as HD          # noqa: E402
from a2 import arcdsl as D              # noqa: E402
from a2 import bus as B                 # noqa: E402
from a2 import corpus as C              # noqa: E402
from a2 import grammars as GR           # noqa: E402
from a2 import runlog as RL             # noqa: E402

OUT = os.environ.get("A2_OUT", os.path.join(HERE, "out"))          # A2_OUT: isolated test folder
STATUS = os.path.join(OUT, "status")
CFG = {"budget": 150000, "cpu_cap": 20.0, "max_fn": 400, "K": 20, "seed": 20261027, "folds": 4}
if os.environ.get("A2_DL") == "dag":                       # v2: DAG description length + reuse >= 2 (see library.py)
    CFG.update(dl="dag", min_reuse=2)
PY = "python3"


def resume_cmd(*args):
    if os.environ.get("A2_DL") == "dag":
        return (f"cd {EXP} && setsid nohup sh ../../scripts/with_cpu_slot.sh sh a2/pipeline_v2.sh "
                f"> a2/out_v2/logs/pipeline_v2.log 2>&1 &")
    return (f"cd {EXP} && setsid nohup sh ../../scripts/with_cpu_slot.sh {PY} -m a2.run_a2 {' '.join(args)} "
            f"> a2/out/logs/{'_'.join(args)}.log 2>&1 &")


def corpus():
    with open(os.path.join(OUT, "corpus.json")) as f:
        doc = json.load(f)
    trees = {t: C.tree_from_json(v["tree"]) for t, v in doc["tasks"].items() if v["verified"]}
    split = {t: v["split"] for t, v in doc["tasks"].items()}
    return trees, split


def correct(preds, truths):
    """Strict all-query success with two attempts: every query output matched by attempt 1 or 2."""
    if not preds:
        return False
    a1, a2 = preds
    return all(D.to_grid(y) in (p1, p2) for y, p1, p2 in zip(truths, a1, a2))


def per_output(preds, truths):
    if not preds:
        return [False] * len(truths)
    a1, a2 = preds
    return [D.to_grid(y) in (p1, p2) for y, p1, p2 in zip(truths, a1, a2)]


# ------------------------------------------------------------------ stage: traces
def stage_traces():
    trees, split = corpus()
    tr_ids = sorted(t for t in trees if split[t] == "S_train")
    g = GR.build([trees[t] for t in tr_ids])
    labels = HD.source_labels("S_train")
    dsl, consts, _, _ = D.load()
    ev = D.Evaluator(dsl, consts)
    path = os.path.join(OUT, "traces.jsonl")
    done = {r["task_id"] for r in RL.read_jsonl(path)}
    run = RL.Run("a2", "traces", STATUS, dict(CFG, n_tasks=len(tr_ids), grammar="base"), resume_cmd("traces")).start()
    n_new = 0
    for tid in tr_ids:
        if tid in done:
            continue
        task = HD.task_record(tid, "S_train")
        r = B.search(g, task["train"], task["test_inputs"], CFG["budget"], keep_seen=True, want=1,
                     cpu_cap=CFG["cpu_cap"], max_fn=CFG["max_fn"])
        ok = correct(r.preds, labels[tid])
        xs = tuple(D.to_grid(x) for x, _ in task["train"]) + tuple(D.to_grid(x) for x in task["test_inputs"])
        keys = B.node_keys(trees[tid], xs, ev)
        flags = "".join("1" if (keys.get(s) is not None and keys[s] in r.seen) else "0"
                        for s in B.subtrees(trees[tid]))
        rec = {"task_id": tid, "solved_demo": r.solved, "correct": ok, "calls": r.calls,
               "first_fit_calls": r.first_fit_calls, "cpu_s": round(r.cpu_s, 2), "level": r.level, "bank": r.bank,
               "stop": r.stop, "program": D.show(r.program) if r.program else None, "reached": flags}
        RL.append_jsonl(path, rec)
        n_new += 1
    recs = RL.read_jsonl(path)
    run.extra = {"tasks": len(recs), "new": n_new, "correct": sum(r["correct"] for r in recs),
                 "search_cpu_s": round(sum(r["cpu_s"] for r in recs), 1)}
    run.finish("OK")


def main():
    os.makedirs(os.path.join(OUT, "logs"), exist_ok=True)
    stage = sys.argv[1]
    if stage == "traces":
        stage_traces()
    else:
        import importlib
        mod = importlib.import_module("a2.stages")
        getattr(mod, "stage_" + stage)(*sys.argv[2:])


if __name__ == "__main__":
    main()
