"""U5 scripts and tests must equal CODE_FREEZE.json before the evaluation run. Usage: python3 -I verify_code.py [--write]"""
import glob
import hashlib
import json
import os
import sys

E = "/path/to/repository/experiments/universality_bio_grammar_20261103"
F = os.path.join(E, "CODE_FREEZE.json")
cur = {os.path.relpath(p, E): hashlib.sha256(open(p, "rb").read()).hexdigest()
       for p in sorted(glob.glob(os.path.join(E, "scripts", "*")) + glob.glob(os.path.join(E, "tests", "*.py")))
       if os.path.isfile(p) and not p.endswith("verify_code.py")}
if sys.argv[1:] == ["--write"]:
    json.dump({"files": cur}, open(F, "w"), indent=1)
    print("written", len(cur))
    sys.exit(0)
want = json.load(open(F))["files"]
bad = sorted(k for k in set(want) | set(cur) if want.get(k) != cur.get(k))
print(json.dumps({"checked": len(want), "mismatches": bad}))
sys.exit(1 if bad else 0)
