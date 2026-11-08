"""System b's merge, exactly as entry H calls it (sfb.merge.merge_files_packages, policy tier1:B3), with a stand-in for
C4: both attempts are a copy of the test input. Usage: python h_merge.py CHALLENGES RUN_DIR"""
import json
import os
import sys

E = "/path/to/repository/experiments/universality_similar_problems_20261102"
sys.path.insert(0, os.path.join(E, "systems", "h"))
from sfb import merge as M  # noqa: E402

ch_path, d = sys.argv[1], sys.argv[2]
ch = json.load(open(ch_path))
standin = {tid: [{"attempt_1": x["input"], "attempt_2": x["input"]} for x in t["test"]] for tid, t in ch.items()}
sa = os.path.join(d, "standin.json")
json.dump(standin, open(sa, "w"))
rep = M.merge_files_packages(sa, ch_path, [{"name": "cast_selective_v2", "mode": "evidence", "policy": "tier1:B3",
                                            "dir": os.path.join(d, "side")}],
                             os.path.join(d, "submission_B.json"), os.path.join(d, "merge_report.json"),
                             code_dir=os.path.join(E, "systems", "h"))
print(json.dumps({k: rep.get(k) for k in ("ok", "tier", "replaced_tier0", "replaced_tier1", "problems")})[:600])
sys.exit(0 if rep.get("ok") else 1)
