"""The development recheck (docs/CORA_REAL_TASK_LOO_STABILITY_v1_AMENDMENT_1.md):
the same 60 development tasks, arm ORIGINAL (reach v1, cora_reach.measure)
and arm SUCCESSOR (reach v2, cora_reach2.measure2), as units of one run, and
the digests the coordinator and every worker re-check.

  python -m cora_loo.recheck freeze   -> outputs/loo_v1/recheck_manifest.json (refuses if it exists)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

from cora_reach import measure as M

VERSION = "loo-recheck-1"
ARMS = ("ORIGINAL", "SUCCESSOR")
FROZEN_FILES = (
    "cora_loo/recheck.py", "scripts/loo_v1_recheck_run.py", "scripts/loo_v1_recheck_summary.py",
    "scripts/loo_v1_checkpoint.sh", "scripts/build_measure2.py", "tests/test_reach2.py",
    "docs/CORA_REAL_TASK_LOO_STABILITY_v1.md", "docs/CORA_REAL_TASK_LOO_STABILITY_v1_AMENDMENT_1.md",
    "records/LOO_V1_DIAGNOSIS_20261012.md",
    "cora_reach2/__init__.py", "cora_reach2/variant.py", "cora_reach2/measure2.py",
    "cora_reach/measure.py", "cora_reach/bridge.py", "cora_reach/construct.py", "cora_reach/relations.py",
    "cora_reach/growth_ext.py", "cora_reach/instances.py", "harness/object_layer.py", "harness/run_harness.py",
    "cora_pilot/native.py", "cora_pilot/isolation.py", "library.json", "learned_verbs.json",
    "records/pilot_v1/dev_bundle.json", "outputs/reach_v1/instances2_rows.jsonl",
    "outputs/reach_v1/census_rows.jsonl")
FROZEN_TREES = ("geocat_arc", "cora_arc2026", "outputs/reach_v1/instances2")


def units(keys, fc_keys) -> list:
    """Every (task, arm) unit, the failure-conditioned tasks first."""
    order = sorted(keys, key=lambda k: (k not in fc_keys, k))
    return [f"{k}|{arm}" for k in order for arm in ARMS]


def fc_keys(here) -> set:
    out = set()
    for line in open(os.path.join(here, "outputs", "reach_v1", "measure_rows.jsonl")):
        if line.strip():
            r = json.loads(line)
            if (r.get("fc") or {}).get("proposals"):
                out.add(r["key"])
    return out


def run_unit(unit, tasks, dirs, here, seconds) -> dict:
    from cora_reach2 import measure2 as M2
    key, arm = unit.split("|")
    everyone = sorted(tasks)
    ctx = {"dirs": dirs[arm], "instances_dir": os.path.join(here, "outputs", "reach_v1", "instances2"),
           "donor": everyone[(everyone.index(key) + 1) % len(everyone)], "extract_seconds": seconds.get(key)}
    row = (M if arm == "ORIGINAL" else M2).run_task(key, tasks[key], ctx)
    row["key"], row["task"], row["arm"], row["recheck_version"] = unit, key, arm, VERSION
    return row


def engine_dirs(root) -> dict:
    return {arm: M.engine_dirs(os.path.join(root, arm.lower())) for arm in ARMS}


def _sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def freeze_state(here) -> dict:
    from cora_reach2 import measure2 as M2
    return {"files": {f: _sha(os.path.join(here, f)) for f in FROZEN_FILES},
            "trees": {t: M.tree_sha(os.path.join(here, t)) for t in FROZEN_TREES},
            "constants": {"version": VERSION, "arms": list(ARMS), "v1": "reach-v1-measure", "v2": M2.VERSION,
                          "budget_s": M.BUDGET_S, "extract_cap_s": M.EXTRACT_CAP_S,
                          "matched_s": [M.MATCHED_MIN_S, M.MATCHED_MAX_S]}}


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


def main(argv):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if argv[:1] != ["freeze"]:
        raise SystemExit(__doc__)
    path = os.path.join(here, "outputs", "loo_v1", "recheck_manifest.json")
    if os.path.exists(path):
        raise SystemExit("a manifest exists: the recheck is frozen")
    dirty = subprocess.run(["git", "status", "--porcelain", "--",
                            *[f for f in FROZEN_FILES if not f.startswith("outputs/")]],
                           cwd=here, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit(f"frozen files differ from HEAD: commit first\n{dirty}")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=here, capture_output=True, text=True).stdout.strip()
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "head": head,
           "protocol": "docs/CORA_REAL_TASK_LOO_STABILITY_v1_AMENDMENT_1.md", "state": freeze_state(here)}
    with open(path, "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({"head": head, "manifest_sha256": _sha(path), "problems": freeze_problems(here, path)}))


if __name__ == "__main__":
    main(sys.argv[1:])
