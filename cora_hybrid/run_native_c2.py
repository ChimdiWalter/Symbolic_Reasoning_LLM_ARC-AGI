"""CORA_ONLY arm on corpus C2: the frozen native_v1 notebook, unchanged, on
Athe.

  python -m cora_hybrid.run_native_c2   -> outputs/hybrid_c2/native_run/

It builds a Kaggle-style tree, the same way kaggle/native_v1/emulate.py does:
- input/arc-prize-2026-arc-agi-2/ holds C2's challenges as
  arc-agi_test_challenges.json, with no solutions;
- input/arc-native-baseline/ holds the frozen tarball.

It then runs kaggle/native_v1/notebook.py with K_INPUT/K_WORK pointing into
the tree. The C2 solutions file is never placed in the tree.
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C2 = os.path.join(HERE, "outputs", "hybrid_c2")
BASE = os.path.join(C2, "native_run")


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    comp = os.path.join(BASE, "input", "arc-prize-2026-arc-agi-2")
    data = os.path.join(BASE, "input", "arc-native-baseline")
    work = os.path.join(BASE, "working")
    for d in (comp, data, work):
        os.makedirs(d)
    ch = json.load(open(os.path.join(C2, "challenges.json")))
    assert all(set(c) == {"input"} for t in ch.values() for c in t["test"]), "a test output is present: refusing"
    shutil.copy(os.path.join(C2, "challenges.json"), os.path.join(comp, "arc-agi_test_challenges.json"))
    json.dump({k: [{"attempt_1": [[0]], "attempt_2": [[0]]} for _ in v["test"]] for k, v in ch.items()},
              open(os.path.join(comp, "sample_submission.json"), "w"))
    shutil.copy(os.path.join(HERE, "kaggle", "native_v1", "arc_native_baseline_v1.tar.gz"), data)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ARC_", "K_"))}
    env.update(K_INPUT=os.path.join(BASE, "input"), K_WORK=work, K_WORKERS=os.environ.get("C2_WORKERS", "4"))
    t0 = time.time()
    rc = subprocess.call([sys.executable, os.path.join(HERE, "kaggle", "native_v1", "notebook.py")], env=env, cwd=work,
                         stdout=open(os.path.join(BASE, "notebook.log"), "w"), stderr=subprocess.STDOUT)
    json.dump({"returncode": rc, "wall_s": round(time.time() - t0, 1)}, open(os.path.join(BASE, "run_meta.json"), "w"))
    print("native C2 run done", rc, round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
