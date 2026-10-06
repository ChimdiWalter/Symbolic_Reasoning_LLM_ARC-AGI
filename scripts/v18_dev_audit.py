"""Item-2 v1.8 development audit. DEVELOPMENT ONLY: engineering evidence,
not a scientific result.

For the first N development tasks (scripts/v18_corpus.py, seed base
840,000,000): every arm at the proposer level, with post-hoc diagnostics
that use the generator's schema only after the proposer has run (was an
equivalent extension proposed, verified, selected; does the selection
predict the held-out pair at fitter level). For the first ENGINE_N tasks
also the engine stage (paired ablation), real leave-one-out and the S6 law.

Rows are appended to outputs/tti/v18_dev_rows.jsonl as each task finishes
and a rerun skips finished tasks; the summary goes to
outputs/tti/v18_dev_audit.json.
"""
from __future__ import annotations

import json
import os
import sys
import time

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v18_proposer as P                        # noqa: E402
import v18_corpus as CORPUS                                       # noqa: E402

N = 40
ENGINE_N = 8
ROWS = os.path.join(HERE, "outputs", "tti", "v18_dev_rows.jsonl")
OUT = os.path.join(HERE, "outputs", "tti", "v18_dev_audit.json")


def normalized_canonical(schema) -> str:
    """The generator's schema with every zero-Select block written as
    Select(all), the form K's blocks use."""
    blocks = [(p, sel if sel else ("all",), f) for p, sel, f in P.S.CV.blocks_from_ast(schema)]
    return P.canonical(P.S.CV.ast_from_blocks(blocks))


def diagnostics(rec, t, target_fp, target_canon):
    import numpy as np
    d = rec.get("diag", {})
    out = {"target_proposed": target_canon in d.get("proposals", []),
           "target_equivalent_verified": target_fp in d.get("verified_fingerprints", [])}
    if rec.get("selected"):
        out["selected_equivalent"] = rec["selected"]["fingerprint"] == target_fp
        pred = P._evaluate(rec["selected_fitted"], t["held"][0])
        out["selected_heldout_exact"] = bool(pred is not None and np.array_equal(pred, t["held"][1]))
    return out


def slim(rec):
    keep = ("arm", "class", "k_class", "partial_tops", "proposals", "capped", "verified_by_depth",
            "selection", "seconds", "detail")
    out = {k: rec.get(k) for k in keep}
    if rec.get("selected"):
        out["selected"] = {k: rec["selected"][k] for k in ("layers", "canonical", "origin", "entries")}
    return out


def run_task(i, t, donor_failure):
    from cora_tti import scoped_slot_fitting as SF
    fitted, _ = SF.fit_induced_occurrences(t["schema"], t["train"])
    target_fp = P.fingerprint(fitted)
    target_canon = normalized_canonical(t["schema"])
    row = {"i": i, "seed": t["seed"], "family": t["family"], "digest": t["digest"],
           "blocks": len(P.S.CV.blocks_from_ast(t["schema"])), "target_normalized": target_canon,
           "arms": {}}
    main = None
    for arm in P.ARMS:
        rec = P.solve(t["train"], arm, donor_failure=donor_failure if arm == "SHUFFLED_FRONTIER" else None,
                      keep=True)
        row["arms"][arm] = dict(slim(rec), **diagnostics(rec, t, target_fp, target_canon))
        if arm == "FAILURE_CONDITIONED":
            main = rec
    if i < ENGINE_N and main is not None and main["class"] == "SELECTED":
        st = P.engine_stage(t["train"], t["held"], main)
        for arm_key in ("with", "without"):
            if isinstance(st.get(arm_key), dict):
                st[arm_key].pop("program", None)
        row["engine"] = st
        row["s6"] = P.separation(main, t["train"])
        loo = P.real_loo(t["train"])
        row["real_loo"] = {"passed": loo["passed"], "folds_success": loo["folds_success"],
                           "folds": [{k: f.get(k) for k in ("fold", "class", "proposer_class", "selected",
                                                              "accepted", "uses", "heldout_exact",
                                                              "engine_seconds", "proposer_seconds",
                                                              "events", "selection")}
                                     for f in loo["folds"]]}
        row["real_loo"]["selected_same_as_full"] = sum(
            1 for f in loo["folds"] if f.get("selected") == main["selected"]["canonical"])
    return row


def summarize(rows):
    s = {"tasks": len(rows), "by_family": {}, "arms": {}}
    for r in rows:
        s["by_family"][r["family"]] = s["by_family"].get(r["family"], 0) + 1
    for arm in P.ARMS:
        recs = [r["arms"][arm] for r in rows]
        classes = {}
        for x in recs:
            classes[x["class"]] = classes.get(x["class"], 0) + 1
        levels = {}
        for x in recs:
            lv = (x.get("selection") or {}).get("level")
            if lv:
                levels[lv] = levels.get(lv, 0) + 1
        secs = sorted(x["seconds"] for x in recs)
        s["arms"][arm] = {
            "classes": classes, "selection_levels": levels,
            "target_proposed": sum(1 for x in recs if x.get("target_proposed")),
            "target_equivalent_verified": sum(1 for x in recs if x.get("target_equivalent_verified")),
            "selected_equivalent": sum(1 for x in recs if x.get("selected_equivalent")),
            "selected_heldout_exact": sum(1 for x in recs if x.get("selected_heldout_exact")),
            "proposals_median": sorted(sum(x["proposals"].values()) for x in recs)[len(recs) // 2] if recs else None,
            "seconds_median": secs[len(secs) // 2] if secs else None,
            "seconds_max": secs[-1] if secs else None}
    eng = [r for r in rows if "engine" in r]
    s["engine"] = {"tasks": len(eng),
                   "success": sum(1 for r in eng if r["engine"]["class"] == "SUCCESS"),
                   "verdicts": {}, "real_loo_passed": sum(1 for r in eng if r["real_loo"]["passed"]),
                   "real_loo_folds_success": [r["real_loo"]["folds_success"] for r in eng],
                   "s6_new_capability": sum(1 for r in eng if r["s6"]["new_capability"]),
                   "s6_comparison_sizes": [r["s6"]["comparison_set"] for r in eng]}
    for r in eng:
        v = r["engine"].get("verdict", r["engine"]["class"])
        s["engine"]["verdicts"][v] = s["engine"]["verdicts"].get(v, 0) + 1
    structures = [r["target_normalized"] for r in rows]
    s["structures"] = {"distinct": len(set(structures)), "repeated": len(structures) - len(set(structures))}
    return s


def main():
    started = time.time()
    tasks = CORPUS.tasks(CORPUS.DEV_BASE, N)
    done = {}
    if os.path.exists(ROWS):
        for line in open(ROWS):
            r = json.loads(line)
            done[r["seed"]] = r
    donors = {}
    for i, t in enumerate(tasks):
        j = (i + 1) % len(tasks)
        while tasks[j]["digest"] == t["digest"]:
            j = (j + 1) % len(tasks)
        donors[i] = j
    for i, t in enumerate(tasks):
        if t["seed"] in done:
            continue
        donor = P.build_input(tasks[donors[i]]["train"])["failure"]
        row = run_task(i, t, donor)
        row["donor_seed"] = tasks[donors[i]]["seed"]
        with open(ROWS, "a") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        done[t["seed"]] = row
        print(f"task {i} seed {t['seed']} {row['arms']['FAILURE_CONDITIONED']['class']} "
              f"{time.time() - started:.0f}s", flush=True)
    rows = [done[t["seed"]] for t in tasks]
    summary = summarize(rows)
    summary.update(development_only=True, seed_base=CORPUS.DEV_BASE, seeds=[t["seed"] for t in tasks],
                   digests=[t["digest"] for t in tasks], seconds=round(time.time() - started, 1),
                   proposer_sha256=P.proposer_sha256())
    with open(OUT, "w") as handle:
        handle.write(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
