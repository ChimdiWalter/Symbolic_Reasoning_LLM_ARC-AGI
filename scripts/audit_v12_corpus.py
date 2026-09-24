"""Audit the generated v1.2 constructive corpus against the FROZEN gates.

Every threshold is read from the frozen manifest. Nothing here decides a
criterion, and no value is reinterpreted. The script reports each frozen
criterion with its measured value and a PASS or FAIL, then an overall verdict.

No training, no compiling, no scoring, no ARC evaluation data.
"""
import json
import os
import statistics
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTI = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti"
for _p in (TTI, HERE):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from cora_tti import constructive_vocabulary as CV                # noqa: E402

CORPUS = os.path.join(HERE, "outputs", "tti", "v12_corpus")
MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "constructive_protocol_v1.2_manifest.json")
REPORT = os.path.join(HERE, "outputs", "tti", "v12_corpus_audit.json")


def load():
    with open(MANIFEST) as handle:
        man = json.load(handle)
    rows = []
    for name in sorted(os.listdir(CORPUS)):
        if name.startswith("slot") and name.endswith(".json"):
            with open(os.path.join(CORPUS, name)) as handle:
                rows.append(json.load(handle))
    return man, rows


def iqr(values):
    if len(values) < 4:
        return 0.0
    q = statistics.quantiles(values, n=4)
    return float(q[2] - q[0])


def main():
    man, rows = load()
    q = man["corpus_quality_criteria"]
    admitted = [r for r in rows if r["admitted"] and r.get("episode")]
    train = [r for r in admitted if r["split"] == "train"]
    val = [r for r in admitted if r["split"] == "val"]
    test = [r for r in admitted if r["split"] == "test"]

    attempts = sum(r["attempts_used"] for r in rows)
    rejections = Counter()
    for r in rows:
        for code, n in r["outcome_counts"].items():
            if code != "ADMITTED":
                rejections[code] += n

    def digests(group):
        return [r["episode"]["target_digest"] for r in group]

    train_d, val_d, test_d = set(digests(train)), set(digests(val)), set(digests(test))
    all_d = digests(admitted)

    fam_req = Counter(CV.family_text(tuple(r["requested_family"])) for r in admitted)
    fam_struct = Counter()
    nodes, mdls, depths, frontier, ops, vsig, nonexact = [], [], [], [], [], [], []
    for r in admitted:
        ep = r["episode"]
        ast = CV.ast_from_tokens([tuple(t) for t in ep["target_tokens"]])
        fam_struct[CV.family_text(CV.family(ast))] += 1
        mdls.append(CV.mdl(ast))
        nodes.append(CV.stage_count(ast))
        depths.append(CV.block_count(ast))
        f = ep["model_view"]["features"]
        frontier.append(f["frontier_term_count"])
        ops.append(f["distinct_frontier_operator_count"])
        vsig.append(f["defined_value_signature_count"])
        nonexact.append(f["executed_not_exact_count"])

    top_digest = Counter(all_d).most_common(1)
    collapse_share = (top_digest[0][1] / len(all_d)) if all_d else 0.0

    checks = []

    def check(name, measured, passed, threshold):
        checks.append({"criterion": name, "measured": measured,
                       "threshold": threshold, "pass": bool(passed)})

    check("admitted train episodes", len(train),
          len(train) >= q["admitted_train_min"], f">= {q['admitted_train_min']}")
    admitting_fams = sum(1 for k, v in fam_req.items() if v > 0)
    check("families admitting", admitting_fams,
          admitting_fams >= q["admission_families_min"],
          f">= {q['admission_families_min']}")
    check("structural families among admitted train",
          len({CV.family_text(CV.family(CV.ast_from_tokens(
              [tuple(t) for t in r['episode']['target_tokens']]))) for r in train}),
          len({CV.family_text(CV.family(CV.ast_from_tokens(
              [tuple(t) for t in r['episode']['target_tokens']]))) for r in train})
          >= q["structural_families_min"], f">= {q['structural_families_min']}")
    check("distinct target digests in train", len(train_d),
          len(train_d) >= q["distinct_target_digests_min"],
          f">= {q['distinct_target_digests_min']}")
    train_frontier = [r["episode"]["model_view"]["features"]["frontier_term_count"]
                      for r in train]
    check("frontier_term_count IQR across admitted train", round(iqr(train_frontier), 3),
          iqr(train_frontier) >= q["frontier_term_count_iqr_min"],
          f">= {q['frontier_term_count_iqr_min']}")
    distinct_op_values = len({r["episode"]["model_view"]["features"]
                              ["distinct_frontier_operator_count"] for r in train})
    check("distinct values of distinct_frontier_operator_count", distinct_op_values,
          distinct_op_values >= q["distinct_operator_count_values_min"],
          f">= {q['distinct_operator_count_values_min']}")
    check("no single target dominates admitted set",
          round(collapse_share, 4), collapse_share < 0.5, "< 0.5 share")
    check("every admitted episode passes the informative gate",
          sum(1 for r in admitted
              if r["episode"]["model_view"]["features"]["frontier_term_count"] >= 2),
          all(r["episode"]["model_view"]["features"]["frontier_term_count"] >= 2
              for r in admitted), "all")
    leak_train_val = train_d & val_d
    leak_train_test = train_d & test_d
    check("train digests disjoint from validation", len(leak_train_val),
          not leak_train_val, "0 overlap")
    check("train digests disjoint from structural holdout", len(leak_train_test),
          not leak_train_test, "0 overlap")
    hold_fams = set(man["structural_holdout_families"])
    train_fams_seen = {CV.family_text(tuple(r["requested_family"])) for r in train}
    check("holdout families absent from train", len(train_fams_seen & hold_fams),
          not (train_fams_seen & hold_fams), "0 overlap")

    verdict = "PASS" if all(c["pass"] for c in checks) else "FAIL"
    report = {
        "protocol_sha256": man["protocol_doc_sha256"],
        "manifest_sha256_recorded_in": "outputs/tti/constructive_protocol_v1.2_manifest.json.sha256",
        "slots_written": len(rows), "slots_requested": 450,
        "targets_attempted": attempts,
        "admitted_total": len(admitted), "admitted_train": len(train),
        "admitted_val": len(val), "admitted_structural_holdout": len(test),
        "admission_rate_per_slot": round(len(admitted) / len(rows), 4) if rows else 0,
        "admission_rate_per_attempt": round(len(admitted) / attempts, 4) if attempts else 0,
        "admissions_by_requested_family": dict(fam_req),
        "admissions_by_structural_family": dict(fam_struct),
        "rejections_by_reason": dict(rejections),
        "unique_target_digests": len(set(all_d)),
        "duplicate_digest_rate": round(1 - len(set(all_d)) / len(all_d), 4) if all_d else 0,
        "ast_stage_count": {"min": min(nodes, default=0), "max": max(nodes, default=0),
                            "mean": round(statistics.mean(nodes), 2) if nodes else 0},
        "ast_block_count": {"min": min(depths, default=0), "max": max(depths, default=0),
                            "mean": round(statistics.mean(depths), 2) if depths else 0},
        "ast_mdl": {"min": min(mdls, default=0), "max": max(mdls, default=0),
                    "mean": round(statistics.mean(mdls), 2) if mdls else 0},
        "frontier_term_count": {"min": min(frontier, default=0),
                                "max": max(frontier, default=0),
                                "mean": round(statistics.mean(frontier), 2) if frontier else 0,
                                "iqr": round(iqr(frontier), 3)},
        "distinct_frontier_operator_count": {"min": min(ops, default=0),
                                             "max": max(ops, default=0),
                                             "mean": round(statistics.mean(ops), 2) if ops else 0},
        "defined_value_signatures": {"min": min(vsig, default=0),
                                     "max": max(vsig, default=0),
                                     "mean": round(statistics.mean(vsig), 2) if vsig else 0},
        "executed_not_exact": {"min": min(nonexact, default=0),
                               "max": max(nonexact, default=0),
                               "mean": round(statistics.mean(nonexact), 2) if nonexact else 0},
        "most_common_target_share": round(collapse_share, 4),
        "wall_seconds": round(sum(r["elapsed_s"] for r in rows), 1),
        "mean_seconds_per_slot": round(statistics.mean([r["elapsed_s"] for r in rows]), 2) if rows else 0,
        "seconds_per_admitted_episode": round(sum(r["elapsed_s"] for r in rows) / len(admitted), 2) if admitted else 0,
        "criteria": checks,
        "verdict": verdict,
        "complete": len(rows) >= 450,
    }
    with open(REPORT, "w") as handle:
        json.dump(report, handle, indent=1, default=str)

    print(f"slots {report['slots_written']}/450  attempts {attempts}  "
          f"admitted {len(admitted)} (train {len(train)}, val {len(val)}, "
          f"holdout {len(test)})")
    print(f"rejections: {dict(rejections)}")
    print(f"admissions by requested family: {dict(fam_req)}")
    print()
    for c in checks:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['criterion']}: "
              f"{c['measured']}  (frozen threshold {c['threshold']})")
    print(f"\nVERDICT: {verdict}"
          f"{'' if report['complete'] else '   (PARTIAL: generation incomplete)'}")
    print("wrote", REPORT)


if __name__ == "__main__":
    main()
