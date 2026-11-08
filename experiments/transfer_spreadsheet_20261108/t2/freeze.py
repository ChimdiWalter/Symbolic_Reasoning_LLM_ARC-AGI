"""Write FREEZE.json: the sha256 of the code, the configuration, the split, the data manifest, the prepared task file,
the launcher and the protocol. Usage: python3 -I t2/freeze.py <study>"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from t2.run import FROZEN  # noqa: E402


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(study):
    split = json.load(open(os.path.join(study, "split", "DEV_SPLIT.json")))
    src = json.load(open(os.path.join(study, "data", "SOURCE_FILES_SHA256.json")))
    out = {"study": "experiments/transfer_spreadsheet_20261108", "test": "T2 spreadsheet string transformations",
           "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "files_sha256": {f: sha(os.path.join(study, f)) for f in FROZEN},
           "data_source": {"repository": src["source"], "commit": src["commit"],
                           "tarball_sha256": src["tarball_sha256"], "files_used": len(src["files_used"])},
           "held_tasks": len(split["held_pool_tasks"]), "development_tasks": len(split["dev_tasks"]),
           "salt_rule": "salt = the full 40-hex hash of the git commit that first contains this FREEZE.json; "
                        "the coordinator writes it into runs/GO_T2 with the sha256 of PROTOCOL.md and of this file",
           "config": json.load(open(os.path.join(study, "config", "CONFIG.json")))}
    with open(os.path.join(study, "FREEZE.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print(sha(os.path.join(study, "FREEZE.json")))


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]))
