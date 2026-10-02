"""Item-2 v1.6: compute CandidateFailureProbe responses for every admitted
episode of a corpus, deterministically, and write them with the identities of
the probe, the fitter and the corpus.

    v16_responses.py dev    v1.5 test corpus (development data only)
    v16_responses.py test   v1.6 prospective corpus (run by the evaluator chain)

Responses are a pure function of (candidate schema, demonstrations). Groups
are processed by a small worker pool; the output is ordered by group digest,
target index and replicate index, so it is byte-identical for any pool size.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v16_cfr as C                             # noqa: E402

CORPORA = {
    "dev": {"dir": os.path.join(HERE, "outputs", "tti", "v15_test_corpus"),
            "base": 300_000_000,
            "out": os.path.join(HERE, "outputs", "tti", "v16_dev_responses.json")},
    "test": {"dir": os.path.join(HERE, "outputs", "tti", "v16_test_corpus"),
             "base": 500_000_000,
             "out": os.path.join(HERE, "outputs", "tti", "v16_test_responses.json")},
}
RECORD = re.compile(r"^full(\d{5})\.json$")
WORKERS = int(os.environ.get("V16_WORKERS", "4"))


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def admitted_records(dirname):
    names = sorted(n for n in os.listdir(dirname) if RECORD.match(n))
    out = []
    for n in names:
        with open(os.path.join(dirname, n)) as handle:
            r = json.load(handle)
        if r.get("admitted"):
            out.append(r)
    return out


def _order_checked(g, e):
    """Erratum 1: episodes whose group digest starts with hex 0 are probed a
    second time in the opposite candidate order; the two must agree."""
    return g["group_digest"][0] == "0"


def _group_job(args):
    rec, base = args
    g = rec["group"]
    a, b = C.group_candidates(rec, base)
    rows, restored, order_ok, order_checked = [], True, True, 0
    for e in sorted(g["episodes"], key=lambda x: (x["target_index"], x["replicate_index"])):
        before = C.state_snapshot()
        er = C.episode_responses(a, b, e)
        restored = restored and C.state_snapshot() == before
        if _order_checked(g, e):
            pairs = C.episode_pairs(e)
            pb, pa = C.probe(b, pairs), C.probe(a, pairs)
            order_ok = order_ok and (json.dumps(pa, sort_keys=True) == json.dumps(er["anchor"], sort_keys=True)
                                     and json.dumps(pb, sort_keys=True) == json.dumps(er["contrast"], sort_keys=True))
            restored = restored and C.state_snapshot() == before
            order_checked += 1
        rows.append({"group_digest": g["group_digest"], "t": e["target_index"],
                     "r": e["replicate_index"], "responses": er})
    return g["group_digest"], rows, restored, order_ok, order_checked


def compute(which):
    cfg = CORPORA[which]
    recs = admitted_records(cfg["dir"])
    jobs = [(r, cfg["base"]) for r in recs]
    with Pool(WORKERS) as pool:
        results = pool.map(_group_job, jobs, chunksize=1)
    rows, restored, order_ok, checked = [], True, True, 0
    for _, rs, ok, oo, n_checked in sorted(results, key=lambda x: x[0]):
        rows.extend(rs)
        restored = restored and ok
        order_ok = order_ok and oo
        checked += n_checked
    corpus_hashes = hashlib.sha256("".join(
        sha256(os.path.join(cfg["dir"], f"full{r['slot']:05d}.json"))
        for r in sorted(recs, key=lambda r: r["slot"])).encode()).hexdigest()
    return {"which": which, "probe_identity": C.probe_identity(),
            "fitter_identity": C._sf().fitter_identity(),
            "admitted_records_sha256": corpus_hashes, "groups": len(recs),
            "episodes": len(rows), "state_restored_every_group": restored,
            "state_restored_every_episode": restored,
            "order_check_episodes": checked, "order_check_passed": order_ok,
            "fields": list(C.RESPONSE_FIELDS), "rows": rows}


def main():
    which = sys.argv[1]
    out = compute(which)
    path = sys.argv[2] if len(sys.argv) > 2 else CORPORA[which]["out"]
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        handle.write(json.dumps(out, sort_keys=True) + "\n")
    os.replace(tmp, path)
    print(json.dumps({k: out[k] for k in ("which", "groups", "episodes",
                                          "state_restored_every_episode",
                                          "order_check_episodes", "order_check_passed")}))


if __name__ == "__main__":
    main()
