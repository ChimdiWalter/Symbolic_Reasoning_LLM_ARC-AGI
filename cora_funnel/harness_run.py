"""The whole native v23 harness on dev60. DEVELOPMENT, real ARC.

  python -m cora_funnel.harness_run run    -> outputs/funnel_v0/harness_dev60/
  python -m cora_funnel.harness_run score  -> outputs/funnel_v0/eval_dev60_harness.json

The official 0.00 is a whole-harness outcome: pipeline, then geocat, then
object. In the Kaggle path, attempt_1 is the render of the first layer that
claims the task, and attempt_2 is the object layer's uncertified partial.

`run` executes the frozen native_v1 notebook, unchanged, as the C2-dev
ceiling test's arm A does. Its input is the 60 tasks under opaque keys,
with training pairs and test inputs only; no answer enters the tree.

`score` is evaluator-side. Per task it reads which layers claimed the task
(progress.jsonl) and scores attempt_1 and attempt_2 against the pinned
answers. It then reports precision by claiming layer and pipeline
sub-layer: claimed and right vs claimed and wrong.
"""
import collections
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
BASE = os.path.join(HERE, "outputs", "funnel_v0", "harness_dev60")


def run():
    from cora_funnel.run import load
    comp = os.path.join(BASE, "input", "arc-prize-2026-arc-agi-2")
    data = os.path.join(BASE, "input", "arc-native-baseline")
    work = os.path.join(BASE, "working")
    for d in (comp, data, work):
        os.makedirs(d, exist_ok=True)
    ch = {k: t for k, t in load("dev60")}                             # blind: train pairs + test inputs only
    json.dump(ch, open(os.path.join(comp, "arc-agi_test_challenges.json"), "w"))
    json.dump({k: [{"attempt_1": [[0]], "attempt_2": [[0]]} for _ in t["test"]] for k, t in ch.items()},
              open(os.path.join(comp, "sample_submission.json"), "w"))
    tar = os.path.join(data, "arc_native_baseline_v1.tar.gz")
    if not os.path.exists(tar):
        shutil.copy(os.path.join(HERE, "kaggle", "native_v1", "arc_native_baseline_v1.tar.gz"), data)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ARC_", "K_"))}
    env.update(K_INPUT=os.path.join(BASE, "input"), K_WORK=work, K_WORKERS=os.environ.get("CORA_FUNNEL_WORKERS", "4"))
    t0 = time.time()
    rc = subprocess.call([sys.executable, os.path.join(HERE, "kaggle", "native_v1", "notebook.py")], env=env, cwd=work,
                         stdout=open(os.path.join(BASE, "notebook.log"), "a"), stderr=subprocess.STDOUT)
    json.dump({"returncode": rc, "wall_s": round(time.time() - t0, 1)}, open(os.path.join(BASE, "run_meta.json"), "w"))
    return rc


def score():
    from cora_funnel.evaluate import answers
    ans = answers("dev60")
    sub = json.load(open(os.path.join(BASE, "working", "submission.json")))
    prog = [json.loads(l) for l in open(os.path.join(BASE, "working", "run", "progress.jsonl"))]
    tab, sub_layer, tasks = collections.Counter(), collections.Counter(), []
    for r in prog:
        k = r["task_id"]
        out = ans[k][0]
        e = sub[k]
        ok1 = all(e[i]["attempt_1"] == out[i] for i in range(len(out)))
        ok2 = all(e[i]["attempt_2"] == out[i] for i in range(len(out)))
        claims = "".join(c if bool((r.get(n) or {}).get("solved")) else "-" for c, n in (("P", "pipeline"), ("G", "geocat"), ("O", "object")))
        tab[claims, "a1_correct" if ok1 else "a1_wrong", "a2_correct" if ok2 else "a2_wrong"] += 1
        if (r.get("pipeline") or {}).get("solved"):
            sub_layer[r["pipeline"].get("layer"), ok1] += 1
        tasks.append({"key": k, "claims": claims, "attempt_1_correct": ok1, "attempt_2_correct": ok2, "stratum": ans[k][1],
                      "pipeline_layer": (r.get("pipeline") or {}).get("layer"), "object": r.get("object")})
    claimed = [t for t in tasks if t["claims"] != "---"]
    out = {"label": "DEVELOPMENT (real ARC-AGI-2 training tasks, the 60 authorized pilot development tasks); whole native v23 harness; evaluator-side",
           "tasks": len(tasks), "claimed": len(claimed),
           "claimed_correct_2attempt": sum(t["attempt_1_correct"] or t["attempt_2_correct"] for t in claimed),
           "claimed_wrong_2attempt": sum(not (t["attempt_1_correct"] or t["attempt_2_correct"]) for t in claimed),
           "unclaimed_correct_2attempt": sum(t["attempt_1_correct"] or t["attempt_2_correct"] for t in tasks if t["claims"] == "---"),
           "exact_2attempt": sum(t["attempt_1_correct"] or t["attempt_2_correct"] for t in tasks),
           "by_claims": {"|".join(k): v for k, v in sorted(tab.items())},
           "pipeline_sublayer_attempt1": {f"{k[0]}|{'correct' if k[1] else 'wrong'}": v for k, v in sorted(sub_layer.items(), key=str)},
           "per_task": tasks}
    json.dump(out, open(os.path.join(HERE, "outputs", "funnel_v0", "eval_dev60_harness.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "per_task"}, indent=1))
    return out


if __name__ == "__main__":
    {"run": run, "score": score}[sys.argv[1]]()
