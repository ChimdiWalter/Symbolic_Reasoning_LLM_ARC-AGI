"""Run reasoning v2 (reason + diagnose + decide) on an ENGINEERING corpus of exposed tasks, then score it separately.

  python -m cora_revision_v2.run_v2 --corpus standin58|dev60 [--workers 2] [--cpu 900] [--tag eng]
      -> outputs/cora_revision_v2/rows_<corpus>_<tag>.jsonl   (blind rows: no answer is read while reasoning)
      -> outputs/cora_revision_v2/eval_<corpus>_<tag>.json    (written afterwards by the evaluator)

Blindness: the parent writes a bundle holding only the training pairs and test INPUTS; each task runs in its own
child process that reads only that bundle, under an RLIMIT_CPU budget. A child killed by the budget becomes a
RESOURCE_LIMIT row. Only the evaluator, after every row is written, reads the answers.

Engineering corpora only (exposed tasks). The proposed Phase 2 cohort is deliberately NOT loadable here: it needs
the user's authorization and its own frozen protocol.
"""
import argparse
import json
import os
import resource
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "outputs", "cora_revision_v2")
ENGINEERING = ("standin58", "dev60")


def _pairs(xs):
    return [(p["input"], p["output"]) if isinstance(p, dict) else (p[0], p[1]) for p in xs]


def _inputs(xs):
    return [p["input"] if isinstance(p, dict) else p[0] for p in xs]


def blind_bundle(corpus):
    if corpus == "standin58":
        tasks = json.load(open(os.path.join(HERE, "outputs", "cora_fhr", "standin58.json")))["tasks"]
    elif corpus == "dev60":
        tasks = json.load(open(os.path.join(HERE, "records", "pilot_v1", "dev_bundle.json")))["tasks"]
    else:
        raise ValueError(f"{corpus} is not an engineering corpus")
    return {k: {"train": _pairs(t["train"]), "test_inputs": _inputs(t["test"])} for k, t in sorted(tasks.items())}


def one(bundle_path, key, out_path):
    from cora_funnel import run as FR                                  # noqa: F401  (sealed flags)
    from cora_revision_v2 import scene_reasoner as SR
    from cora_revision_v2 import diagnosis as DG
    t = json.load(open(bundle_path))[key]
    t0 = time.process_time()
    rec = SR.reason(t["train"], t["test_inputs"])
    t1 = time.process_time()
    diags = DG.diagnose(t["train"], t["test_inputs"], rec)
    dec = DG.decision(rec, diags)
    row = {"key": key, "diagnosis": rec.get("diagnosis"), "certified": bool(rec.get("certified")),
           "tier": dec["tier"], "attempts": dec["attempts"], "top": rec.get("top"), "folds": rec.get("folds"),
           "fold_detail": rec.get("fold_detail"), "test_table_support": rec.get("test_table_support"),
           "n_hypotheses": rec.get("n_hypotheses"), "n_positional": rec.get("n_positional"),
           "cap_hit_views": rec.get("cap_hit_views"), "distinct": rec.get("distinct"),
           "diagnoses": diags, "cpu_reason_s": round(t1 - t0, 1), "cpu_diagnose_s": round(time.process_time() - t1, 1)}
    json.dump(row, open(out_path, "w"))


def run(corpus, workers, cpu, tag):
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, f"tmp_{corpus}_{tag}")
    os.makedirs(tmp, exist_ok=True)
    bundle = blind_bundle(corpus)
    bpath = os.path.join(tmp, "blind_bundle.json")
    json.dump(bundle, open(bpath, "w"))
    rows_path = os.path.join(OUT, f"rows_{corpus}_{tag}.jsonl")
    done = set()
    if os.path.exists(rows_path):
        done = {json.loads(line)["key"] for line in open(rows_path) if line.strip()}
    todo = [k for k in bundle if k not in done]

    def limit():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 10))
        os.nice(10)
    running = {}
    with open(rows_path, "a") as fo:
        while todo or running:
            while todo and len(running) < workers:
                k = todo.pop(0)
                op = os.path.join(tmp, f"{k}.json")
                ep = open(os.path.join(tmp, f"{k}.err"), "w")
                p = subprocess.Popen([sys.executable, "-m", "cora_revision_v2.run_v2", "--one", bpath, k, op],
                                     cwd=HERE, preexec_fn=limit, stdout=subprocess.DEVNULL, stderr=ep)
                ep.close()
                running[k] = (p, op, time.time())
            for k, (p, op, ts) in list(running.items()):
                if p.poll() is None:
                    continue
                err = open(os.path.join(tmp, f"{k}.err")).read()[-400:]
                if p.returncode == 0 and os.path.exists(op):
                    row = json.load(open(op))
                else:
                    row = {"key": k, "diagnosis": "RESOURCE_LIMIT" if p.returncode in (-24, -9) else "ERROR",
                           "returncode": p.returncode, "stderr_tail": err, "certified": False, "tier": "NONE",
                           "attempts": None,
                           "diagnoses": [{"label": "RESOURCE_LIMIT", "observed": f"CPU budget {cpu} s exhausted",
                                          "next_action": "WIDEN_SEARCH"}] if p.returncode in (-24, -9) else []}
                row["wall_s"] = round(time.time() - ts, 1)
                fo.write(json.dumps(row) + "\n")
                fo.flush()
                del running[k]
                print(k, row["diagnosis"], row["tier"], row.get("cpu_reason_s"), flush=True)
            time.sleep(1)
    rows = [json.loads(line) for line in open(rows_path) if line.strip()]
    keys = {r["key"] for r in rows}
    print(json.dumps({"rows": len(rows), "coverage_complete": keys == set(bundle)}))


def evaluate(corpus, tag):
    """After every row is written: score certified and exploratory predictions separately (reads the answers)."""
    import collections
    from cora_fhr.evaluate import answers
    ans = answers(corpus)
    rows = [json.loads(line) for line in open(os.path.join(OUT, f"rows_{corpus}_{tag}.jsonl")) if line.strip()]
    per, tally = {}, collections.Counter()
    for r in rows:
        outs = ans[r["key"]][0]
        att = r.get("attempts")
        first = bool(att) and all(a and a[0] == o for a, o in zip(att, outs)) and len(att) == len(outs)
        either = bool(att) and len(att) == len(outs) and all(any(x == o for x in a) for a, o in zip(att, outs))
        per[r["key"]] = {"tier": r["tier"], "diagnosis": r["diagnosis"], "first_correct": first, "either_correct": either}
        tally[f"{r['tier']}:{'correct' if either else 'wrong'}"] += 1
    labels = collections.Counter(d["label"] for r in rows for d in r.get("diagnoses", []))
    actions = collections.Counter(d["next_action"] for r in rows for d in r.get("diagnoses", []))
    res = {"label": "ENGINEERING (exposed tasks; in-sample; not a generalization result)", "corpus": corpus,
           "n": len(rows), "tiers": dict(tally), "diagnosis_labels": dict(labels), "next_actions": dict(actions),
           "certified_correct": sum(p["tier"] == "CERTIFIED" and p["either_correct"] for p in per.values()),
           "certified_wrong": sum(p["tier"] == "CERTIFIED" and not p["either_correct"] for p in per.values()),
           "exploratory_correct_either": sum(p["tier"] == "EXPLORATORY" and p["either_correct"] for p in per.values()),
           "per_task": per}
    json.dump(res, open(os.path.join(OUT, f"eval_{corpus}_{tag}.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "per_task"}, indent=1))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--one":
        return one(*argv[1:4])
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, choices=ENGINEERING)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--cpu", type=int, default=900)
    ap.add_argument("--tag", default="eng")
    ap.add_argument("--evaluate", action="store_true")
    a = ap.parse_args(argv)
    if a.evaluate:
        return evaluate(a.corpus, a.tag)
    run(a.corpus, min(a.workers, 2), a.cpu, a.tag)


if __name__ == "__main__":
    main()
