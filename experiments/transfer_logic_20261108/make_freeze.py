"""Write FREEZE.json: the sha256 of the code, the configuration, the data manifest, the protocol and the data archives.
Usage: python3 -I make_freeze.py"""
import hashlib
import json
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["tlogic/__init__.py", "tlogic/core.py", "tlogic/pla.py", "tlogic/policy.py", "tlogic/classical.py",
         "tlogic/arms.py", "tlogic/data.py", "tlogic/stats.py", "score_held.py", "tests/test_tlogic.py",
         "fetch_data.sh", "config.json", "DATA_MANIFEST.md", "PROTOCOL.md", "ADAPTER_CARD.md",
         "data/raw/espresso_logic/espresso-logic-85265139e9598852f9388d293658a1977a829a01.tar.gz",
         "data/raw/classbench/parameter_files.tar.gz",
         "../universality_boolean_bbm_20261103/u6/__init__.py",
         "../universality_boolean_bbm_20261103/u6/stats.py"]


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    import numpy
    import sklearn
    out = {"study": "transfer_logic_20261108",
           "note": "Frozen before any held item was chosen or scored. Held items are chosen with the freeze commit "
                   "hash as the salt (PROTOCOL.md section 2).",
           "sha256": {f: sha(os.path.normpath(os.path.join(HERE, f))) for f in FILES},
           "environment": {"python": platform.python_version(), "numpy": numpy.__version__,
                           "scikit_learn": sklearn.__version__, "interpreter": sys.executable}}
    with open(os.path.join(HERE, "FREEZE.json"), "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(sha(os.path.join(HERE, "FREEZE.json")))


if __name__ == "__main__":
    main()
