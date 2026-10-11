"""Freeze the reach v1 measurement (docs/CORA_REAL_TASK_REACH_DEV_v1.md,
section 5.1): write outputs/reach_v1/measure_manifest.json with the digests
the coordinator and every worker re-check before they start.

  python scripts/freeze_reach_measure.py           refuses if a manifest exists
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_reach import measure as M                                  # noqa: E402

MANIFEST = os.path.join(HERE, "outputs", "reach_v1", "measure_manifest.json")


def main():
    if os.path.exists(MANIFEST):
        raise SystemExit("a manifest exists: the measurement is frozen")
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *M.FROZEN_FILES], cwd=HERE,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit(f"frozen files differ from HEAD: commit first\n{dirty}")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "head": head,
           "protocol": "docs/CORA_REAL_TASK_REACH_DEV_v1.md sections 4.1 and 5.1", "state": M.freeze_state(HERE)}
    with open(MANIFEST, "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(json.dumps({"head": head, "manifest": os.path.relpath(MANIFEST, HERE),
                      "problems": M.freeze_problems(HERE, MANIFEST)}))


if __name__ == "__main__":
    main()
