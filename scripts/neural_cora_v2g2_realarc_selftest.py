"""Selftest of the FROZEN real-ARC runner (`scripts/neural_cora_v2g2_realarc_eval.py`, left unchanged) on SYNTHETIC
fixtures only: DEV-family tasks, their generated answers and a scratch directory.

It reads no ARC task, no solutions file and no Step B file, and it writes nothing into the real output or native
engine directories. It exercises:
- `_job_g` (ncv2-g1 and ncv2-g2);
- `_job_native` (the unchanged native harness through `cora_funnel.run.job`);
- `score`;
- the pre-registered analysis.

    python scripts/neural_cora_v2g2_realarc_selftest.py [OUT_DIR]
"""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(out):
    os.environ["CORA_FUNNEL_NICE"] = "10"
    RA = load("ra", "scripts/neural_cora_v2g2_realarc_eval.py")
    AN = load("an", "scripts/neural_cora_v2g2_realarc_analysis.py")
    from cora_neural_v2g2 import families as F
    fixtures, answers = [], {}
    for name, seed, stratum in (("relational_feature_recolour", 3, "primary"), ("symmetry_completion", 3, "primary"),
                                ("negated_selector_delete", 3, "leftover")):
        task, ans = F.make_task(name, seed)
        tid = f"selftest_{name}"
        fixtures.append({"task_id": tid, "stratum": stratum, "train": task["train"], "test_inputs_all": task["test_inputs"],
                         "test_inputs": task["test_inputs"]})
        answers[tid] = [ans.tolist()]
    # every data source and output path redirected to synthetic fixtures and the scratch directory
    man = os.path.join(out, "manifest.json")
    json.dump({"cohort": [[t["task_id"], t["stratum"]] for t in fixtures], "inputs": {}}, open(man, "w"))
    RA.OUT, RA.MANIFEST, RA.INPUTS, RA.tasks = out, man, [], (lambda: fixtures)
    import cora_funnel.run as FR
    FR.OUT = out                                                    # native engine directories into the scratch directory
    import cora_pilot.evaluator as EV
    EV.load_pinned = lambda path, sha: answers
    with open(os.path.join(out, "rows_g.jsonl"), "w") as fh:
        for t in fixtures:
            fh.write(json.dumps(RA._job_g(t)) + "\n")
    with open(os.path.join(out, "rows_native.jsonl"), "w") as fh:
        for t in fixtures:
            fh.write(json.dumps(RA._job_native(t)) + "\n")
    RA.score(None)
    S = json.load(open(os.path.join(out, "score.json")))
    AN.main(out, os.path.join(out, "engine_realarc2x_native", "certificates"), {t["task_id"]: t for t in fixtures})
    A = json.load(open(os.path.join(out, "analysis.json")))
    ok = ("decision" in S["summary"] and len(S["tasks"]) == 3 and all("native" in t for t in S["tasks"])
          and S["summary"]["primary"]["n"] == 2 and S["summary"]["leftover"]["n"] == 1 and len(A["tasks"]) == 3)
    print("REALARC_RUNNER_SELFTEST", "PASS" if ok else "FAIL", out, flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="realarc_selftest_")
    os.makedirs(d, exist_ok=True)
    sys.exit(main(d))
