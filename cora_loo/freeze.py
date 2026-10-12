"""Freeze of the diagnosis run (docs/CORA_REAL_TASK_LOO_STABILITY_v1.md
section 11): the digests the coordinator and every worker re-check.

  python -m cora_loo.freeze      -> outputs/loo_v1/diagnose_manifest.json (refuses if it exists)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

from cora_loo import instrument as IN
from cora_reach import measure as M

FROZEN_FILES = (
    "cora_loo/__init__.py", "cora_loo/instrument.py", "cora_loo/diagnose.py", "cora_loo/freeze.py",
    "scripts/loo_v1_run.py", "scripts/loo_v1_checkpoint.sh", "scripts/loo_v1_classify.py", "tests/test_loo_v1.py",
    "docs/CORA_REAL_TASK_LOO_STABILITY_v1.md",
    "cora_reach/measure.py", "cora_reach/bridge.py", "cora_reach/construct.py", "cora_reach/relations.py",
    "cora_reach/growth_ext.py", "cora_reach/instances.py", "cora_reach/census.py",
    "cora_v19/v19_trace.py", "harness/object_layer.py", "harness/run_harness.py",
    "cora_pilot/native.py", "cora_pilot/isolation.py", "library.json", "learned_verbs.json",
    "records/pilot_v1/dev_bundle.json", "outputs/reach_v1/measure_rows.jsonl")
FROZEN_TREES = ("geocat_arc", "cora_arc2026", "outputs/reach_v1/instances2")


def _sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def freeze_state(here) -> dict:
    return {"files": {f: _sha(os.path.join(here, f)) for f in FROZEN_FILES},
            "trees": {t: M.tree_sha(os.path.join(here, t)) for t in FROZEN_TREES},
            "constants": {"version": IN.VERSION, "clocks": list(IN.CLOCKS), "cpu_wall_cap_s": IN.CPU_WALL_CAP_S,
                          "budget_s": M.BUDGET_S, "object_cap_s": M.BUDGET_S + M.CAP_SLACK_S + M.FRAMES_ALLOWANCE_S,
                          "extract_cap_s": M.EXTRACT_CAP_S, "matched_s": [M.MATCHED_MIN_S, M.MATCHED_MAX_S]}}


def freeze_problems(here, manifest_path) -> list:
    if not os.path.exists(manifest_path):
        return ["no manifest"]
    with open(manifest_path) as handle:
        frozen = json.load(handle)["state"]
    now = freeze_state(here)
    problems = [f"file {f}" for f in FROZEN_FILES if frozen["files"].get(f) != now["files"][f]]
    problems += [f"tree {t}" for t in FROZEN_TREES if frozen["trees"].get(t) != now["trees"][t]]
    if frozen.get("constants") != now["constants"]:
        problems.append("constants")
    return problems


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "outputs", "loo_v1", "diagnose_manifest.json")
    if os.path.exists(path):
        raise SystemExit("a manifest exists: the diagnosis is frozen")
    dirty = subprocess.run(["git", "status", "--porcelain", "--",
                            *[f for f in FROZEN_FILES if not f.startswith("outputs/")]],
                           cwd=here, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit(f"frozen files differ from HEAD: commit first\n{dirty}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=here, capture_output=True, text=True).stdout.strip()
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "head": head,
           "protocol": "docs/CORA_REAL_TASK_LOO_STABILITY_v1.md", "state": freeze_state(here)}
    with open(path, "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({"head": head, "manifest_sha256": _sha(path), "problems": freeze_problems(here, path)}))


if __name__ == "__main__":
    sys.exit(main())
