"""Fit the Stage-B scorer and run the five preregistered evidence conditions.

Preregistration version 3: docs/SCORER_FIT_PREREGISTRATION_v1.md.
Every split, condition, metric and threshold comes from that document.
Nothing is chosen here, and control performance is never consulted during
training.
"""
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import constructive_proposer as CP              # noqa: E402
from cora_arc2026 import leak_scan_v12 as LEAK                    # noqa: E402
from cora_arc2026 import scorer_fit as SF                         # noqa: E402

CORPUS = os.path.join(HERE, "outputs", "tti", "v12_corpus")
OUT = os.path.join(HERE, "outputs", "tti", "scorer_fit_v1.json")
WEIGHTS = os.path.join(HERE, "outputs", "tti", "scorer_weights_v1.json")
PREREG = os.path.join(HERE, "docs", "SCORER_FIT_PREREGISTRATION_v1.md")
INTERFACE = ("Set[Region]", "Grid")
TOP_K = 5


def load_admitted():
    out = []
    for name in sorted(os.listdir(CORPUS)):
        if name.startswith("slot") and name.endswith(".json"):
            with open(os.path.join(CORPUS, name)) as handle:
                d = json.load(handle)
            if d["admitted"] and d.get("episode"):
                out.append(d["episode"])
    return out


def parts(ep):
    return (SF.FeatureVector(ep["model_view"]["features"]),
            [tuple(t) for t in ep["target_tokens"]], ep["target_digest"])


def propose(scorer, evidence):
    return CP.propose_ast(None, INTERFACE, k=TOP_K, scorer=scorer,
                          evidence=evidence)


def measure(scorer, items, evidence_for=None):
    hits5 = hits1 = 0
    rank_one, top5_sets = [], []
    per_episode = []
    for i, (fv, _tokens, digest) in enumerate(items):
        ev = fv if evidence_for is None else evidence_for(i)
        cands = propose(scorer, ev)
        digests = [c.digest for c in cands]
        fams = [c.family_text for c in cands]
        got5 = digest in digests
        got1 = bool(digests) and digests[0] == digest
        hits5 += got5
        hits1 += got1
        if digests:
            rank_one.append(digests[0])
            top5_sets.append(tuple(digests))
        per_episode.append({"index": i, "hit_at_5": got5, "hit_at_1": got1,
                            "rank_one": digests[0] if digests else None,
                            "rank_one_family": fams[0] if fams else None})
    n = len(items) or 1
    counts = Counter(rank_one)
    entropy = -sum((c / len(rank_one)) * math.log(c / len(rank_one))
                   for c in counts.values()) if rank_one else 0.0
    return {
        "exact_at_5": round(hits5 / n, 4), "exact_at_1": round(hits1 / n, 4),
        "hits_at_5": hits5, "hits_at_1": hits1, "n": len(items),
        "distinct_rank_one": len(counts),
        "distinct_top5_lists": len(set(top5_sets)),
        "distinct_rank_one_families": len({p["rank_one_family"]
                                           for p in per_episode}),
        "modal_rank_one_share": round(max(counts.values()) / len(rank_one), 4)
        if rank_one else 0.0,
        "rank_one_entropy": round(entropy, 4),
        "per_episode": per_episode,
    }


def main():
    started = time.monotonic()
    prereg_sha = hashlib.sha256(open(PREREG, "rb").read()).hexdigest()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip()

    episodes = load_admitted()
    train_eps = sorted([e for e in episodes if e["split"] == "train"],
                       key=lambda e: e["target_digest"])
    val_eps = sorted([e for e in episodes if e["split"] == "val"],
                     key=lambda e: e["episode_id"])
    hold_eps = sorted([e for e in episodes if e["split"] == "test"],
                      key=lambda e: e["target_digest"])

    #  leakage scan, zero violations required before fitting
    violations = []
    for ep in train_eps + val_eps + hold_eps:
        found = LEAK.scan(ep["model_view"], ep)
        if found:
            violations.append({"episode": ep["episode_id"], "findings": found})
    print(f"leak scan: {len(train_eps)+len(val_eps)+len(hold_eps)} views, "
          f"{len(violations)} violations")
    if violations:
        print("ABORTING: leakage violations", violations[:3])
        sys.exit(1)

    fit_set = [parts(e) for e in train_eps]
    val_set = [parts(e) for e in val_eps]
    hold_set = [parts(e) for e in hold_eps]
    assert not ({d for _, _, d in fit_set} & {d for _, _, d in val_set})
    print(f"fit {len(fit_set)}  validation {len(val_set)}  "
          f"structural holdout {len(hold_set)}")

    #  required baseline: the unfitted hand-designed prior
    unfitted = CP.EvidenceScorer()
    base = measure(unfitted, val_set,
                   evidence_for=lambda i: CP.Evidence(
                       frontier_terms=val_set[i][0].features["frontier_term_count"],
                       slot_failures=val_set[i][0].features["slot_fit_failed_count"],
                       executed_not_exact=val_set[i][0].features["executed_not_exact_count"],
                       distinct_frontier_ops=val_set[i][0].features["distinct_frontier_operator_count"],
                       palette_introduced=val_set[i][0].features["palette_introduced_mean"],
                       palette_removed=val_set[i][0].features["palette_removed_mean"],
                       shape_preserved=1.0 if val_set[i][0].features["same_shape_all"] else 0.0,
                       fraction_changed=val_set[i][0].features["mean_fraction_changed"],
                       fraction_wrong=val_set[i][0].features["fraction_wrong_mean"],
                       palette_extra=val_set[i][0].features["palette_extra_mean"],
                       defined_signatures=val_set[i][0].features["defined_value_signature_count"],
                       empty=val_set[i][0].features["empty_frontier"]))
    print(f"unfitted baseline: exact@5 {base['exact_at_5']}  "
          f"exact@1 {base['exact_at_1']}  distinct rank-1 {base['distinct_rank_one']}")

    standardizer = SF.Standardizer().fit([fv.vector() for fv, _, _ in fit_set])

    #  training: validation is evaluated with REAL ASSOCIATED evidence only
    def early_stop(scorer):
        return measure(scorer, val_set)["exact_at_5"]

    print("fitting...")
    selected, final, info = SF.fit([(fv, t) for fv, t, _ in fit_set],
                                   standardizer, evaluate=early_stop)
    print(f"selected checkpoint: epoch {info['best_epoch']}, "
          f"validation exact@5 {info['best_early_stop_exact_at_5']:.4f}; "
          f"epochs run {info['epochs_run']}")

    blob = json.dumps(selected.to_dict(), sort_keys=True)
    with open(WEIGHTS, "w") as handle:
        handle.write(blob)
    checkpoint_sha = hashlib.sha256(blob.encode()).hexdigest()

    #  the five frozen conditions, only now that the checkpoint is frozen
    n, nf = len(val_set), len(fit_set)
    shuffle_map = {i: (i + 1) % n for i in range(n)}
    assert all(shuffle_map[i] != i for i in range(n)), "shuffle must derange"

    conditions = {
        "real_associated": lambda i: val_set[i][0],
        "shuffled": lambda i: val_set[shuffle_map[i]][0],
        "irrelevant": lambda i: fit_set[(i * 7) % nf][0],
        "aggregate_only": lambda i: SF.FeatureVector(
            {**val_set[i][0].features,
             **{k: 0 for k in SF.CANDIDATE_ASSOCIATED},
             "empty_frontier": True}),
        "none": lambda i: SF.FeatureVector({k: 0 for k in SF.FEATURE_ORDER}),
    }

    def run_conditions(scorer, label):
        out = {}
        print(f"\n{label} checkpoint:")
        for name, fn in conditions.items():
            out[name] = measure(scorer, val_set, evidence_for=fn)
            r = out[name]
            print(f"  {name:16s} exact@5 {r['exact_at_5']:.4f} "
                  f"({r['hits_at_5']}/{r['n']})  exact@1 {r['exact_at_1']:.4f}  "
                  f"rank-1 distinct {r['distinct_rank_one']}  "
                  f"modal share {r['modal_rank_one_share']}")
        return out

    primary = run_conditions(selected, "SELECTED")
    secondary = run_conditions(final, "FINAL (no validation selection)")

    a5 = primary["real_associated"]["exact_at_5"]
    rule = {"associated_beats_shuffled": a5 > primary["shuffled"]["exact_at_5"],
            "associated_beats_aggregate_only":
                a5 > primary["aggregate_only"]["exact_at_5"]}
    collapse_ok = primary["real_associated"]["distinct_rank_one"] >= 5
    verdict = ("FAILURE_CONDITIONED_AST_SELECTION"
               if all(rule.values()) and collapse_ok
               else "FAILURE_CONDITIONING_NOT_ESTABLISHED")

    assoc = primary["real_associated"]["per_episode"]
    shuf = primary["shuffled"]["per_episode"]
    changed_rank_one = sum(1 for a, b in zip(assoc, shuf)
                           if a["rank_one"] != b["rank_one"])

    hold = measure(selected, hold_set) if hold_set else None

    report = {
        "preregistration_sha256": prereg_sha, "code_commit": commit,
        "corpus_protocol_sha256":
            "31a74764019c7ecef9d456258c9df3b6ee81d81a14c4703ee878d023bbe6bb98",
        "checkpoint_sha256": checkpoint_sha,
        "architecture": {"family": "log-linear conditional over grammar-legal tokens",
                         "terminals": len(SF.TERMINALS), "inputs": SF.DIM,
                         "parameters": len(SF.TERMINALS) * SF.DIM,
                         "hidden_layers": 0, "non_llm": True,
                         "optimizer": "full-batch gradient ascent",
                         "learning_rate": 0.1, "l2": 1e-3,
                         "init": "zeros, deterministic, no seed applicable",
                         "device": platform.machine()},
        "sizes": {"fit": len(fit_set), "validation": len(val_set),
                  "structural_holdout": len(hold_set)},
        "leak_scan": {"views_scanned": len(train_eps) + len(val_eps) + len(hold_eps),
                      "violations": 0},
        "training": info,
        "unfitted_baseline_real_associated": base,
        "conditions_selected_checkpoint": primary,
        "conditions_final_checkpoint": secondary,
        "shuffle_map": shuffle_map,
        "shuffle_is_derangement": True,
        "success_rule": rule,
        "collapse_check_distinct_rank_one_at_least_5": collapse_ok,
        "episodes_whose_rank_one_changes_associated_vs_shuffled": changed_rank_one,
        "structural_holdout_descriptive_n3": hold,
        "fit_digests": [d for _, _, d in fit_set],
        "validation_digests": [d for _, _, d in val_set],
        "verdict": verdict,
        "wall_seconds": round(time.monotonic() - started, 1),
    }
    with open(OUT, "w") as handle:
        json.dump(report, handle, indent=1)

    print(f"\nassociated > shuffled:        {rule['associated_beats_shuffled']}")
    print(f"associated > aggregate only:  {rule['associated_beats_aggregate_only']}")
    print(f"collapse check (>=5 rank-1):  {collapse_ok}")
    print(f"rank-1 changes associated vs shuffled: {changed_rank_one}/{n}")
    print(f"\nVERDICT: {verdict}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
