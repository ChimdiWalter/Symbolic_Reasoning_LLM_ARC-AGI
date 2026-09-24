"""Fit the Stage-B scorer and run the five preregistered evidence conditions.

Preregistration version 4: docs/SCORER_FIT_PREREGISTRATION_v1.md.
Every split, condition, metric and threshold comes from that document.
Control performance is never consulted during training.
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


def measure(scorer, items, evidence_for=None, decode=True):
    """Primary metric is mean per-token target log-likelihood.

    exact@5 and the rank diagnostics are reported alongside it. The review
    measured that exact@5 is saturated near zero under this decoder even for a
    probe that knows the target's tokens, so it is reported and is not the
    gate.
    """
    logps, per_token, hits5, hits1 = [], [], 0, 0
    rank_one, top5, families, per_episode = [], [], [], []
    for i, (fv, tokens, digest) in enumerate(items):
        ev = fv if evidence_for is None else evidence_for(i)
        total, steps = scorer.sequence_logprob(ev, tokens)
        logps.append(total)
        per_token.append(total / max(steps, 1))
        row = {"index": i, "target_logprob": round(total, 5),
               "per_token_logprob": round(total / max(steps, 1), 5)}
        if decode:
            cands = CP.propose_ast(None, INTERFACE, k=TOP_K, scorer=scorer,
                                   evidence=ev)
            digests = [c.digest for c in cands]
            got5, got1 = digest in digests, bool(digests) and digests[0] == digest
            hits5 += got5
            hits1 += got1
            if digests:
                rank_one.append(digests[0])
                top5.append(tuple(digests))
                families.append(cands[0].family_text)
            row.update({"hit_at_5": got5, "hit_at_1": got1,
                        "rank_one": digests[0] if digests else None,
                        "rank_one_family": cands[0].family_text if cands else None})
        per_episode.append(row)
    n = len(items) or 1
    counts = Counter(rank_one)
    entropy = -sum((c / len(rank_one)) * math.log(c / len(rank_one))
                   for c in counts.values()) if rank_one else 0.0
    return {
        "mean_per_token_target_logprob": round(sum(per_token) / n, 6),
        "mean_target_logprob": round(sum(logps) / n, 6),
        "exact_at_5": round(hits5 / n, 4), "exact_at_1": round(hits1 / n, 4),
        "hits_at_5": hits5, "hits_at_1": hits1, "n": len(items),
        "distinct_rank_one": len(counts),
        "distinct_top5_lists": len(set(top5)),
        "distinct_rank_one_families": len(set(families)),
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

    violations = [{"episode": e["episode_id"], "findings": f}
                  for e in train_eps + val_eps + hold_eps
                  for f in [LEAK.scan(e["model_view"], e)] if f]
    print(f"leak scan: {len(train_eps)+len(val_eps)+len(hold_eps)} views, "
          f"{len(violations)} violations")
    if violations:
        print("ABORTING on leakage:", violations[:3])
        sys.exit(1)

    fit_set = [parts(e) for e in train_eps]
    val_set = [parts(e) for e in val_eps]
    hold_set = [parts(e) for e in hold_eps]
    assert not ({d for _, _, d in fit_set} & {d for _, _, d in val_set})
    print(f"fit {len(fit_set)}  validation {len(val_set)}  holdout {len(hold_set)}")

    standardizer = SF.Standardizer().fit(
        [fv.raw(SF.FEATURE_ORDER) for fv, _, _ in fit_set])
    print(f"live features {len(standardizer.order)}; "
          f"dropped constant {list(standardizer.dropped)}")

    def early_stop(scorer):
        return measure(scorer, val_set, decode=False)["mean_per_token_target_logprob"]

    print("fitting...")
    selected, final, info = SF.fit([(fv, t) for fv, t, _ in fit_set],
                                   standardizer, evaluate=early_stop)
    print(f"selected epoch {info['best_epoch']}, best validation metric "
          f"{info['best_validation_metric']}; epochs run {info['epochs_run']}")

    blob = json.dumps(selected.to_dict(), sort_keys=True)
    with open(WEIGHTS, "w") as handle:
        handle.write(blob)
    checkpoint_sha = hashlib.sha256(blob.encode()).hexdigest()

    n, nf = len(val_set), len(fit_set)
    shuffle_map = {i: (i + 1) % n for i in range(n)}
    assert all(shuffle_map[i] != i for i in range(n))
    mean_fv = standardizer.mean_vector()

    conditions = {
        "real_associated": lambda i: val_set[i][0],
        "shuffled": lambda i: val_set[shuffle_map[i]][0],
        "irrelevant": lambda i: fit_set[(i * 7) % nf][0],
        "aggregate_only": lambda i: standardizer.neutralize(
            val_set[i][0], set(SF.CANDIDATE_ASSOCIATED)),
        "none": lambda i: mean_fv,
    }

    def run(scorer, label):
        out = {}
        print(f"\n{label}:")
        for name, fn in conditions.items():
            out[name] = measure(scorer, val_set, evidence_for=fn)
            r = out[name]
            print(f"  {name:16s} per-token logprob {r['mean_per_token_target_logprob']:+.5f}"
                  f"   exact@5 {r['exact_at_5']:.4f}  rank-1 distinct "
                  f"{r['distinct_rank_one']}  modal {r['modal_rank_one_share']}")
        return out


    #  required baseline: the unfitted hand-designed prior. Disclosure: the
    #  old Evidence dataclass has no field for five features the fitted model
    #  receives, so this is not like for like and the baseline is structurally
    #  handicapped. Decode metrics only; its input space differs, so target
    #  log-likelihood is not comparable.
    def as_old_evidence(i):
        f = val_set[i][0].features
        return CP.Evidence(
            frontier_terms=f["frontier_term_count"],
            slot_failures=f["slot_fit_failed_count"],
            executed_not_exact=f["executed_not_exact_count"],
            distinct_frontier_ops=f["distinct_frontier_operator_count"],
            palette_introduced=f["palette_introduced_mean"],
            palette_removed=f["palette_removed_mean"],
            shape_preserved=1.0 if f["same_shape_all"] else 0.0,
            fraction_changed=f["mean_fraction_changed"],
            fraction_wrong=f["fraction_wrong_mean"],
            palette_extra=f["palette_extra_mean"],
            defined_signatures=f["defined_value_signature_count"],
            empty=f["empty_frontier"])

    unfitted = CP.EvidenceScorer()
    base_hits5 = base_hits1 = 0
    base_rank_one = []
    for i, (_fv, _t, digest) in enumerate(val_set):
        cands = CP.propose_ast(None, INTERFACE, k=TOP_K, scorer=unfitted,
                               evidence=as_old_evidence(i))
        ds = [c.digest for c in cands]
        base_hits5 += digest in ds
        base_hits1 += bool(ds) and ds[0] == digest
        if ds:
            base_rank_one.append(ds[0])
    baseline = {"exact_at_5": round(base_hits5 / len(val_set), 4),
                "exact_at_1": round(base_hits1 / len(val_set), 4),
                "hits_at_5": base_hits5, "n": len(val_set),
                "distinct_rank_one": len(set(base_rank_one)),
                "disclosure": "structurally handicapped: the old Evidence "
                              "dataclass has no field for n_demonstrations, "
                              "mean_cells_changed, exact_count, "
                              "slot_fit_ok_count or search_deadline_hit"}
    print(f"unfitted baseline: exact@5 {baseline['exact_at_5']} "
          f"exact@1 {baseline['exact_at_1']} "
          f"distinct rank-1 {baseline['distinct_rank_one']}")

    primary = run(selected, "SELECTED CHECKPOINT")
    secondary = run(final, "FINAL CHECKPOINT, no validation selection")

    a = primary["real_associated"]["mean_per_token_target_logprob"]
    rule = {"associated_beats_shuffled":
            a > primary["shuffled"]["mean_per_token_target_logprob"],
            "associated_beats_aggregate_only":
            a > primary["aggregate_only"]["mean_per_token_target_logprob"]}
    collapse_ok = primary["real_associated"]["distinct_rank_one"] >= 2
    verdict = ("FAILURE_CONDITIONED_AST_SELECTION"
               if all(rule.values()) and collapse_ok
               else "FAILURE_CONDITIONING_NOT_ESTABLISHED")

    assoc = primary["real_associated"]["per_episode"]
    shuf = primary["shuffled"]["per_episode"]
    changed = sum(1 for x, y in zip(assoc, shuf) if x["rank_one"] != y["rank_one"])
    paired_better = sum(1 for x, y in zip(assoc, shuf)
                        if x["per_token_logprob"] > y["per_token_logprob"])

    report = {
        "preregistration_sha256": prereg_sha, "code_commit": commit,
        "corpus_protocol_sha256":
            "31a74764019c7ecef9d456258c9df3b6ee81d81a14c4703ee878d023bbe6bb98",
        "checkpoint_sha256": checkpoint_sha,
        "architecture": {"family": "state-conditional log-linear over grammar-legal tokens",
                         "terminals": len(SF.TERMINALS),
                         "inputs": selected.dim,
                         "parameters": len(SF.TERMINALS) * selected.dim,
                         "live_evidence_features": len(standardizer.order),
                         "dropped_constant_features": list(standardizer.dropped),
                         "state_features": list(SF.STATE_FEATURES),
                         "hidden_layers": 0, "non_llm": True,
                         "optimizer": "full-batch gradient ascent",
                         "learning_rate": 0.5, "l2": 1e-3,
                         "init": "zeros, deterministic, no seed applicable",
                         "device": platform.machine()},
        "sizes": {"fit": len(fit_set), "validation": len(val_set),
                  "structural_holdout": len(hold_set)},
        "leak_scan": {"views_scanned": len(train_eps) + len(val_eps) + len(hold_eps),
                      "violations": 0},
        "training": info,
        "unfitted_baseline_decode_only": baseline,
        "conditions_selected_checkpoint": primary,
        "conditions_final_checkpoint": secondary,
        "shuffle_map": shuffle_map, "shuffle_is_derangement": True,
        "success_rule": rule,
        "collapse_check_distinct_rank_one_at_least_2": collapse_ok,
        "episodes_rank_one_changes_associated_vs_shuffled": changed,
        "episodes_associated_better_than_shuffled_paired": paired_better,
        "structural_holdout_descriptive_n3":
            measure(selected, hold_set) if hold_set else None,
        "fit_digests": [d for _, _, d in fit_set],
        "validation_digests": [d for _, _, d in val_set],
        "verdict": verdict,
        "wall_seconds": round(time.monotonic() - started, 1),
    }
    with open(OUT, "w") as handle:
        json.dump(report, handle, indent=1)

    print(f"\nassociated > shuffled:        {rule['associated_beats_shuffled']}")
    print(f"associated > aggregate only:  {rule['associated_beats_aggregate_only']}")
    print(f"paired better than shuffled:  {paired_better}/{n}")
    print(f"rank-1 changes vs shuffled:   {changed}/{n}")
    print(f"collapse check (>=2 rank-1):  {collapse_ok}")
    print(f"\nVERDICT: {verdict}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
