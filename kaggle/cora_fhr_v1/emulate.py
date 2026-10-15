"""Offline emulation of the CORA-FHR-v1 notebook (DEVELOPMENT; not a score).

  python kaggle/cora_fhr_v1/emulate.py   -> kaggle/cora_fhr_v1/emulation/ (summary.json)

The fake /kaggle/input holds:
- the unchanged native dataset, extracted;
- the FHR dataset, built by build_dataset.sh and extracted;
- a 6-task challenges file: 3 growth-shaped and 2 other stand-in (training) tasks, plus the synthetic
  witness dev_D3_04 as "fhrwitness" (training pairs and test input only).

A socket guard blocks every network call in the harness and FHR subprocesses. Afterwards the emulator
checks:
- schema;
- full coverage;
- provenance for every output;
- FHR counts;
- a clean guard log;
- for the witness only, a development answer read here and nowhere else: whether the FHR-committed
  answer is correct.
"""
import json
import os
import shutil
import subprocess
import sys
import tarfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASE = os.path.join(HERE, "emulation")
sys.path.insert(0, os.path.join(ROOT, "kaggle", "native_v1"))
from emulate import GUARD                                              # noqa: E402  the native emulator's guard
sys.path.insert(0, HERE)
from fhr_phase import growth_shaped                                    # noqa: E402


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    inp = os.path.join(BASE, "input")
    subprocess.run(["sh", os.path.join(HERE, "build_dataset.sh")], check=True, cwd=ROOT)
    for tar, name in ((os.path.join(ROOT, "kaggle", "native_v1", "arc_native_baseline_v1.tar.gz"), "arc-native-baseline-v1"),
                      (os.path.join(HERE, "arc_cora_fhr_v1.tar.gz"), "arc-cora-fhr-v1")):
        tarfile.open(tar).extractall(os.path.join(inp, name))
    st = json.load(open(os.path.join(ROOT, "outputs", "kaggle_deploy", "native_v1", "kaggle_run_v1", "comp",
                                     "arc-agi_test_challenges.json")))
    g = [k for k in sorted(st) if growth_shaped(st[k])][:3]
    n = [k for k in sorted(st) if not growth_shaped(st[k])][:2]
    c4 = json.load(open(os.path.join(ROOT, "outputs", "cora_fhr", "c4_dev_v2.json")))["tasks"]["dev_D3_04"]
    ch = {k: st[k] for k in g + n}
    ch["fhrwitness"] = {"train": [{"input": a, "output": b} for a, b in c4["train"]],
                        "test": [{"input": a} for a, _b in c4["test"]]}
    comp = os.path.join(inp, "arc-prize-2026-arc-agi-2")
    os.makedirs(comp)
    json.dump(ch, open(os.path.join(comp, "arc-agi_test_challenges.json"), "w"))
    guard = os.path.join(BASE, "guard")
    os.makedirs(guard)
    open(os.path.join(guard, "sitecustomize.py"), "w").write(GUARD)
    work = os.path.join(BASE, "working")
    os.makedirs(work)
    env = dict(os.environ, K_INPUT=inp, K_WORK=work, K_GUARD_DIR=guard, K_GUARD_LOG=os.path.join(BASE, "guard.log"),
               K_WORKERS="2", K_BUDGET_S="1200", K_FHR_START_H="3.0", K_FHR_HARD_H="4.0")
    r = subprocess.run(["nice", "-n", "19", sys.executable, os.path.join(HERE, "notebook.py")], env=env,
                       capture_output=True, text=True, cwd=work)
    open(os.path.join(BASE, "notebook.log"), "w").write(r.stdout + "\n--- stderr ---\n" + r.stderr)
    sub = json.load(open(os.path.join(work, "submission.json")))
    prov = json.load(open(os.path.join(work, "provenance.json")))
    man = json.load(open(os.path.join(work, "execution_manifest.json")))
    ok_schema = set(sub) == set(ch) and all(len(sub[k]) == len(ch[k]["test"]) and all(
        set(e) == {"attempt_1", "attempt_2"} for e in sub[k]) for k in ch)
    witness_ok = sub["fhrwitness"][0]["attempt_1"] == c4["test"][0][1]
    summary = {"returncode": r.returncode, "schema_ok": ok_schema, "tasks": len(sub),
               "provenance_complete": all(len(prov.get(k, [])) == len(ch[k]["test"]) for k in ch),
               "provenance": prov, "fhr_counts": man.get("fhr_counts"), "fhr_error": man.get("fhr_error"),
               "fhr_returncode": man.get("fhr_returncode"), "elapsed_s": man.get("elapsed_s"),
               "harness_s": man.get("harness_s"), "fhr_s": man.get("fhr_s"),
               "guard_log_empty": not os.path.exists(os.path.join(BASE, "guard.log")) or
                                  not open(os.path.join(BASE, "guard.log")).read().strip(),
               "witness_attempt_1_correct (dev answer, emulator only)": witness_ok,
               "native_tree_sha256": man.get("solver_tree_sha256"), "fhr_package_sha256": man.get("fhr_package_sha256")}
    json.dump(summary, open(os.path.join(BASE, "summary.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "provenance"}, indent=1))


if __name__ == "__main__":
    main()
