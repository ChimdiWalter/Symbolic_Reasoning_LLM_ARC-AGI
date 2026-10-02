"""Item-2 v1.6: build the frozen exclusion set for the prospective corpus.

Union of
- the frozen v1.5 exclusion set (every v1.2, v1.3, v1.4, v1.4-smoke and
  v1.5-pilot target and group digest), and
- every target and group digest in the v1.5 test corpus, which serves as
  v1.6 development data (admitted groups and the digests in skip records).
Written once, hashed, frozen before generation.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V15_EXCLUSION = os.path.join(HERE, "outputs", "tti", "v15_exclusion_digests.json")
V15_CORPUS = os.path.join(HERE, "outputs", "tti", "v15_test_corpus")
OUT = os.path.join(HERE, "outputs", "tti", "v16_exclusion_digests.json")


def build():
    with open(V15_EXCLUSION) as handle:
        v15 = json.load(handle)
    targets, groups = set(v15["target_digests"]), set(v15["group_digests"])
    dev_t, dev_g = set(), set()
    names = sorted(n for n in os.listdir(V15_CORPUS) if re.match(r"^full\d{5}\.json$", n))
    for n in names:
        with open(os.path.join(V15_CORPUS, n)) as handle:
            rec = json.load(handle)
        if rec.get("admitted"):
            dev_g.add(rec["group"]["group_digest"])
            dev_t.update(rec["group"]["target_digests"])
        for skip in rec.get("skips", []):
            dev_g.add(skip["group_digest"])
            dev_t.update(skip["target_digests"])
    with open(V15_EXCLUSION, "rb") as handle:
        v15_sha = hashlib.sha256(handle.read()).hexdigest()
    return {"sources": {
                "v1.5 exclusion set": {"sha256": v15_sha,
                                       "target_digests": len(v15["target_digests"]),
                                       "group_digests": len(v15["group_digests"])},
                "v1.5 test corpus (v1.6 development data)": {
                    "records": len(names), "target_digests": len(dev_t),
                    "group_digests": len(dev_g)}},
            "target_digests": sorted(targets | dev_t),
            "group_digests": sorted(groups | dev_g)}


def main():
    out = build()
    path = sys.argv[1] if len(sys.argv) > 1 else OUT
    with open(path, "w") as handle:
        handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"targets": len(out["target_digests"]),
                      "groups": len(out["group_digests"]), "sources": out["sources"]}))


if __name__ == "__main__":
    main()
