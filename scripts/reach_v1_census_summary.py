"""Aggregate the native failure census by mechanism (never by task id).

  python scripts/reach_v1_census_summary.py   -> outputs/reach_v1/census_summary.json
"""
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "outputs", "reach_v1")


def main():
    rows = [json.loads(l) for l in open(os.path.join(OUT, "census_rows.jsonl")) if l.strip()]
    diag = Counter()
    for r in rows:
        d = r.get("diagnosis") or {}
        diag[d.get("class", "?") + (":" + d["sub"] if d.get("sub") else "") + (":" + d["stage"] if d.get("stage") else "")] += 1
    ns = [r["near_solve"] for r in rows if r.get("near_solve")]
    unexplained, actions = Counter(), Counter()
    for n in ns:
        for u in n.get("unexplained") or []:
            unexplained[u.get("delta_type")] += 1
        for a in n.get("explained_actions") or []:
            actions[str(a)] += 1
    loo = [r["identity_induction"]["loo"] for r in rows
           if isinstance(r.get("identity_induction"), dict) and r["identity_induction"].get("loo")]
    summary = {
        "tasks": len(rows), "diagnosis": dict(diag.most_common()),
        "usable_trace": sum(1 for r in rows if r.get("usable_trace")),
        "exact_demo_fit": sum(1 for r in rows if r.get("exact_demo_fit")),
        "object_accepted": sum(1 for r in rows if r.get("object_accepted")),
        "claim_source": dict(Counter(str((r.get("claim") or {}).get("attempt_1_source")) for r in rows)),
        "near_solves": len(ns),
        "near_solve_explained_rules": dict(Counter(n.get("explained_rules") for n in ns)),
        "near_solve_fit_pixels_ge_0_9": sum(1 for n in ns if (n.get("train_fit_pixels") or 0) >= 0.9),
        "unexplained_delta_types": dict(unexplained.most_common()),
        "explained_actions": dict(actions.most_common()),
        "loo_reports": len(loo), "loo_failed_folds": dict(Counter(len(x.get("failed") or []) for x in loo)),
        "by_n_train": {str(k): v for k, v in Counter(r.get("n_train") for r in rows).items()},
        "usable_by_class": dict(Counter((r.get("diagnosis") or {}).get("class") for r in rows if r.get("usable_trace"))),
        "run_errors": sum(1 for r in rows if (r.get("diagnosis") or {}).get("class") == "RUN_ERROR"),
        "seconds": {"mean": round(sum(r.get("seconds") or 0 for r in rows) / max(1, len(rows)), 1),
                    "max": max((r.get("seconds") or 0) for r in rows) if rows else 0},
    }
    with open(os.path.join(OUT, "census_summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1, sort_keys=True)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
