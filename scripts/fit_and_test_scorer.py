"""Fit the Stage-B scorer and run the five preregistered controls.

Preregistration: docs/SCORER_FIT_PREREGISTRATION_v1.md
sha256 ed4ac9d2109e499aed0311b86e553db804ba597316a5dee17f3ad7be207dc860

Every split, control, metric and threshold comes from that document. Nothing
is chosen here. The discrimination test set is touched only at the end.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import constructive_proposer as CP              # noqa: E402
from cora_arc2026 import scorer_fit as SF                         # noqa: E402

CORPUS = os.path.join(HERE, "outputs", "tti", "v12_corpus")
OUT = os.path.join(HERE, "outputs", "tti", "scorer_fit_v1.json")
WEIGHTS = os.path.join(HERE, "outputs", "tti", "scorer_weights_v1.json")
INTERFACE = ("Set[Region]", "Grid")
TOP_K = 5


def load_admitted():
    rows = []
    for name in sorted(os.listdir(CORPUS)):
        if not (name.startswith("slot") and name.endswith(".json")):
            continue
        with open(os.path.join(CORPUS, name)) as handle:
            d = json.load(handle)
        if d["admitted"] and d.get("episode"):
            rows.append(d["episode"])
    return rows


def episode_parts(ep):
    fv = SF.FeatureVector(ep["model_view"]["features"])
    tokens = [tuple(t) for t in ep["target_tokens"]]
    return fv, tokens, ep["target_digest"]


def exact_at_k(scorer, items, k=TOP_K, evidence_for=None):
    """Fraction of items whose target digest appears in the top k proposals."""
    hits1 = hits = 0
    rank_one = []
    for index, (fv, tokens, digest) in enumerate(items):
        ev = fv if evidence_for is None else evidence_for(index)
        cands = CP.propose_ast(None, INTERFACE, k=k, scorer=scorer, evidence=ev)
        digests = [c.digest for c in cands]
        if digests:
            rank_one.append(digests[0])
        if digest in digests:
            hits += 1
        if digests and digests[0] == digest:
            hits1 += 1
    n = len(items) or 1
    return {"exact_at_5": round(hits / n, 4), "exact_at_1": round(hits1 / n, 4),
            "hits_at_5": hits, "n": len(items),
            "distinct_rank_one": len(set(rank_one))}


def main():
    started = time.monotonic()
    episodes = load_admitted()
    train = sorted([e for e in episodes if e["split"] == "train"],
                   key=lambda e: e["target_digest"])
    val = sorted([e for e in episodes if e["split"] == "val"],
                 key=lambda e: e["target_digest"])
    holdout = sorted([e for e in episodes if e["split"] == "test"],
                     key=lambda e: e["target_digest"])

    #  preregistered split, amended 2026-09-24 before any fit: the corpus
    #  validation episodes are the held-out discrimination set, and early
    #  stopping comes from an inner split of the training episodes
    test_set = [episode_parts(e) for e in val]
    stop_set = [episode_parts(e) for i, e in enumerate(train) if i % 5 == 0]
    fit_set = [episode_parts(e) for i, e in enumerate(train) if i % 5 != 0]
    hold_set = [episode_parts(e) for e in holdout]
    print(f"fit {len(fit_set)}  early-stop {len(stop_set)}  "
          f"discrimination test {len(test_set)}  structural holdout {len(hold_set)}")

    fit_digests = {d for _, _, d in fit_set}
    test_digests = {d for _, _, d in test_set}
    assert not (fit_digests & test_digests), "fit and test must be disjoint"

    standardizer = SF.Standardizer().fit([fv.vector() for fv, _, _ in fit_set])

    def early_stop(scorer):
        return exact_at_k(scorer, stop_set)["exact_at_5"]

    print("fitting...")
    scorer, info = SF.fit([(fv, tokens) for fv, tokens, _ in fit_set],
                          standardizer, evaluate=early_stop)
    print(f"best early-stop exact@5 {info['best_early_stop_exact_at_5']:.4f} "
          f"at epoch {info['best_epoch']}")

    with open(WEIGHTS, "w") as handle:
        json.dump(scorer.to_dict(), handle)

    #  the five preregistered controls, on the held-out discrimination set
    n_test, n_fit = len(test_set), len(fit_set)

    def associated(i):
        return test_set[i][0]

    def shuffled(i):
        return test_set[(i + 1) % n_test][0]

    def irrelevant(i):
        return fit_set[(i * 7) % n_fit][0]

    def aggregate_only(i):
        features = dict(test_set[i][0].features)
        for name in SF.CANDIDATE_ASSOCIATED:
            features[name] = 0
        features["empty_frontier"] = True
        return SF.FeatureVector(features)

    def none(i):
        return SF.FeatureVector({name: 0 for name in SF.FEATURE_ORDER})

    controls = {"associated": associated, "shuffled": shuffled,
                "irrelevant": irrelevant, "aggregate_only": aggregate_only,
                "none": none}
    results = {}
    print("\ncontrols on the held-out discrimination set:")
    for name, fn in controls.items():
        results[name] = exact_at_k(scorer, test_set, evidence_for=fn)
        r = results[name]
        print(f"  {name:15s} exact@5 {r['exact_at_5']:.4f}  "
              f"exact@1 {r['exact_at_1']:.4f}  "
              f"hits {r['hits_at_5']}/{r['n']}  "
              f"distinct rank-1 {r['distinct_rank_one']}")

    a5 = results["associated"]["exact_at_5"]
    passes = {"associated_beats_shuffled": a5 > results["shuffled"]["exact_at_5"],
              "associated_beats_aggregate_only":
                  a5 > results["aggregate_only"]["exact_at_5"]}
    diagnostic = results["associated"]["distinct_rank_one"] >= 5
    verdict = "PASS" if all(passes.values()) else "FAIL"

    secondary = exact_at_k(scorer, hold_set) if hold_set else None

    report = {
        "preregistration_sha256":
            open(os.path.join(HERE, "docs", "SCORER_FIT_PREREGISTRATION_v1.md.sha256")).read().split()[0],
        "sizes": {"fit": len(fit_set), "early_stop": len(stop_set),
                  "discrimination_test": len(test_set),
                  "structural_holdout": len(hold_set)},
        "training": info,
        "controls": results,
        "success_rule": passes,
        "secondary_diagnostic_distinct_rank_one_at_least_5": diagnostic,
        "structural_holdout_secondary_underpowered": secondary,
        "verdict": verdict,
        "wall_seconds": round(time.monotonic() - started, 1),
    }
    with open(OUT, "w") as handle:
        json.dump(report, handle, indent=1)
    print(f"\nassociated beats shuffled:        {passes['associated_beats_shuffled']}")
    print(f"associated beats aggregate-only:  {passes['associated_beats_aggregate_only']}")
    print(f"distinct rank-1 >= 5 (diagnostic): {diagnostic}")
    print(f"\nVERDICT: {verdict}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
