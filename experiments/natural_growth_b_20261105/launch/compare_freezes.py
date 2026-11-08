"""Compare two freeze records of study B: every frozen digest that differs, and whether the file is packaged.

    python3 -I launch/compare_freezes.py OLD_FREEZE.json NEW_FREEZE.json

A file is packaged unless the newer record lists it as Athe-only. Prints JSON; exit 0 always (the caller judges).
"""
import json
import sys

a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
ath = set(b["athe_only"])
out = {"version": [a.get("version"), b.get("version")], "scalars_changed": {}, "files": {}}
for k in ("protocol_sha256", "config_sha256", "split_sha256", "data_root", "study"):
    if a.get(k) != b.get(k):
        out["scalars_changed"][k] = [a.get(k), b.get(k)]
for k in ("files_sha256", "amendments_sha256", "data_sha256", "arc_agi_2_sha256", "scorer_only_sha256"):
    da, db = a.get(k, {}), b.get(k, {})
    out["files"][k] = {"changed": sorted(x for x in da if x in db and da[x] != db[x]),
                       "added": sorted(set(db) - set(da)), "removed": sorted(set(da) - set(db))}
fa, fb = a["object_growth"], b["object_growth"]
out["object_growth_changed"] = sorted(x for x in set(fa) | set(fb) if fa.get(x) != fb.get(x))
diff = [x for k in ("files_sha256", "amendments_sha256") for v in out["files"][k].values() for x in v]
out["packaged_files_differing"] = sorted({x for x in diff if x not in ath})
out["athe_only_files_differing"] = sorted({x for x in diff if x in ath})
out["athe_only_list_changed"] = {"added": sorted(ath - set(a["athe_only"])), "removed": sorted(set(a["athe_only"]) - ath)}
print(json.dumps(out, indent=1))
