"""Item-2 v1.8: the exact prospective exclusion set.

Every generator target digest the program has used before: the v1.6
exclusion set (which contains the v1.5 set), the v1.6 test corpus, the v1.7
development fixtures and acceptance tasks, and the v1.8 development corpus.
The prospective corpus law skips any task whose target digest is in it.
Writes outputs/tti/v18_prospective_exclusion.json.
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v15_sel as S                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402

OUT = os.path.join(HERE, "outputs", "tti", "v18_prospective_exclusion.json")


def collect(value, out):
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "target_digest" and isinstance(v, str):
                out.add(v)
            elif k == "target_digests" and isinstance(v, list):
                out.update(x for x in v if isinstance(x, str))
            else:
                collect(v, out)
    elif isinstance(value, list):
        for v in value:
            collect(v, out)


def main():
    from cora_tti import constructive_dataset as CD
    M, _ = X._meta()
    sources = {}
    with open(os.path.join(HERE, "outputs", "tti", "v16_exclusion_digests.json")) as handle:
        v16 = set(json.load(handle)["target_digests"])
    sources["v1.6 exclusion set (contains v1.5)"] = v16
    corpus = set()
    for path in sorted(glob.glob(os.path.join(HERE, "outputs", "tti", "v16_test_corpus", "*.json"))):
        with open(path) as handle:
            collect(json.load(handle), corpus)
    sources["v1.6 test corpus"] = corpus
    with open(os.path.join(HERE, "logs", "v17", "fixtures.json")) as handle:
        sources["v1.7 development fixtures"] = {S.CV.digest(M.ast_from_json(f["schema"]))
                                                for f in json.load(handle)}
    acc = set()
    with open(os.path.join(HERE, "outputs", "tti", "v17_acceptance_rows.jsonl")) as handle:
        for line in handle:
            row = json.loads(line)
            acc.add(S.CV.digest(CD.sample_target(row["seed"], S.G.parse_family(row["family"]))))
    sources["v1.7 acceptance tasks"] = acc
    with open(os.path.join(HERE, "outputs", "tti", "v18_dev_audit.json")) as handle:
        sources["v1.8 development corpus"] = set(json.load(handle)["digests"])
    allset = set().union(*sources.values())
    out = {"target_digests": sorted(allset),
           "sources": {k: len(v) for k, v in sources.items()},
           "total": len(allset)}
    with open(OUT, "w") as handle:
        handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"sources": out["sources"], "total": out["total"]}, indent=1))


if __name__ == "__main__":
    main()
