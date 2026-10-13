"""Kaggle deployment checks for NATIVE_BASELINE native_v1. Never contacts Kaggle.

  python kaggle/native_v1_deploy/deploy_check.py stage
      Checks the frozen package against kaggle/native_v1/DELIVERY_MANIFEST.json,
      then writes the two upload folders under outputs/kaggle_deploy/native_v1/:
        dataset/  arc_native_baseline_v1.tar.gz + dataset-metadata.json
        kernel/   notebook.ipynb + kernel-metadata.json
      Nothing else goes in either folder. The kernel metadata must keep
      internet off: the Kaggle CLI enables internet when the field is absent.

  python kaggle/native_v1_deploy/deploy_check.py verify RUN_DIR TEST_CHALLENGES_JSON
      An independent check of a downloaded Kaggle run (submission.json,
      execution_manifest.json, run/progress.jsonl):
        - the submission is checked against the competition task file
          (inputs only, no solutions);
        - the manifest is checked against the frozen identities;
        - make_submission_v2's real and fallback counts are recomputed from
          the progress rows.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PKG = os.path.join(ROOT, "kaggle", "native_v1")
STAGE = os.path.join(ROOT, "outputs", "kaggle_deploy", "native_v1")
TARBALL = "arc_native_baseline_v1.tar.gz"


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _manifest():
    return json.load(open(os.path.join(PKG, "DELIVERY_MANIFEST.json")))


def frozen_problems():
    m = _manifest()
    bad = [f for f, h in m["files"].items()
           if not os.path.exists(os.path.join(PKG, f)) or _sha(os.path.join(PKG, f)) != h]
    km = json.load(open(os.path.join(HERE, "kernel-metadata.json")))
    if km.get("enable_internet") is not False or km.get("enable_gpu") or km.get("enable_tpu"):
        bad.append("kernel-metadata: internet must be false, no accelerator")
    if km.get("is_private") is not True or json.load(open(os.path.join(HERE, "dataset-metadata.json"))).get("isPrivate") is not True:
        bad.append("metadata: kernel and dataset must be private")
    return bad


def stage():
    bad = frozen_problems()
    if bad:
        sys.exit(f"refusing to stage: {bad}")
    m = _manifest()
    shutil.rmtree(STAGE, ignore_errors=True)
    plan = {"dataset": [(os.path.join(PKG, TARBALL), TARBALL), (os.path.join(HERE, "dataset-metadata.json"), "dataset-metadata.json")],
            "kernel": [(os.path.join(PKG, "notebook.ipynb"), "notebook.ipynb"), (os.path.join(HERE, "kernel-metadata.json"), "kernel-metadata.json")]}
    out = {}
    for sub, files in plan.items():
        d = os.path.join(STAGE, sub)
        os.makedirs(d)
        for src, name in files:
            shutil.copy(src, os.path.join(d, name))
        out[sub] = {n: _sha(os.path.join(d, n)) for n in sorted(os.listdir(d))}
    assert out["dataset"][TARBALL] == m["files"][TARBALL]
    assert out["kernel"]["notebook.ipynb"] == m["files"]["notebook.ipynb"]
    json.dump(out, open(os.path.join(STAGE, "staged.json"), "w"), indent=1)
    print(json.dumps({"staged": STAGE, **out}, indent=1))


def _load_validate():
    spec = importlib.util.spec_from_file_location("native_v1_emulate", os.path.join(PKG, "emulate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.validate


def counts(progress_path, challenges):
    """make_submission_v2's rule: real attempt_1 (or a promoted attempt_2), real attempt_2, fallback."""
    preds = {}
    if os.path.exists(progress_path):
        for line in open(progress_path):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("predictions"):
                preds[d["task_id"]] = d["predictions"]
    n1 = n2 = nf = 0
    for tid, task in challenges.items():
        p = preds.get(tid) or {}
        a1s, a2s = p.get("attempt_1"), p.get("attempt_2")
        for i in range(len(task["test"])):
            a1 = a1s[i] if a1s and i < len(a1s) and a1s[i] else None
            a2 = a2s[i] if a2s and i < len(a2s) and a2s[i] else None
            if a1 is None and a2 is None:
                nf += 1
            else:
                n1 += 1
            n2 += a2 is not None
    return {"attempt_1_real": n1, "attempt_2_real": n2, "fallback": nf, "tasks_with_predictions": len(preds)}


def verify(run_dir, test_path):
    m = _manifest()
    challenges = json.load(open(test_path))
    sub_path = os.path.join(run_dir, "submission.json")
    sub = json.load(open(sub_path))
    man = json.load(open(os.path.join(run_dir, "execution_manifest.json")))
    report = {
        "schema_problems": _load_validate()(sub, challenges),
        "order_ok": all(len(sub.get(t, [])) == len(task["test"]) for t, task in challenges.items()),
        "tasks": len(challenges), "positions": sum(len(t["test"]) for t in challenges.values()),
        "label_ok": (man.get("label"), man.get("version")) == ("NATIVE_BASELINE", "native_v1"),
        "flags_ok": man.get("flags") == m["chain_flags"],
        "assets_ok": man.get("assets") == m["assets"],
        "solver_tree_ok": man.get("solver_tree_sha256") == m["solver_tree_sha256_as_staged"],
        "task_file": man.get("task_file"),
        "task_file_sha_ok": man.get("task_file_sha256") == _sha(test_path),
        "submission_sha_ok": man.get("submission_sha256") == _sha(sub_path),
        "harness_status": man.get("harness_status"), "writer": man.get("writer"),
        "validation": man.get("validation"), "workers": man.get("workers"),
        "harness_s": man.get("harness_s"), "elapsed_s": man.get("elapsed_s"),
        **counts(os.path.join(run_dir, "run", "progress.jsonl"), challenges),
    }
    print(json.dumps(report, indent=1))
    return report


if __name__ == "__main__":
    if sys.argv[1:2] == ["stage"]:
        stage()
    elif sys.argv[1:2] == ["verify"] and len(sys.argv) == 4:
        verify(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
