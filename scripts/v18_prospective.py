"""Item-2 v1.8 prospective proposer test (protocol section 14). Frozen in
v1.8, run ONCE in the next stage, after the review and any errata. Refuses
on any freeze or environment problem and refuses a second start.

Corpus: scripts/v18_corpus.py at seed base 860,000,000, skipping every
digest in outputs/tti/v18_prospective_exclusion.json. For every task:
- every arm at the proposer level (FAILURE_CONDITIONED, DEMO_ONLY,
  SHUFFLED_FRONTIER with a fixed derangement, NO_RESPONSE, PURE), with the
  fitter-level held-out check of each arm's selection;
- for FAILURE_CONDITIONED: the engine stage (paired ablation with the
  held-out pair), real leave-one-out with the proposal inside every fold,
  and the S6 law; together the synthetic B/P/U/L/T/A witness.
The generator's schema is used only after the proposer has run, for the
seen/unseen structural audit and the target-recovery diagnostics.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
import traceback

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_arc2026 import v18_proposer as P                        # noqa: E402
import v18_corpus as CORPUS                                       # noqa: E402

N_TASKS = None          # set from the development feasibility record before the freeze
W_MIN = None            # minimum complete synthetic witnesses, same source
ALPHA = 0.05
MANIFEST = os.path.join(HERE, "outputs", "tti", "no_oracle_proposer_v18_manifest.json")
EXCLUSION = os.path.join(HERE, "outputs", "tti", "v18_prospective_exclusion.json")
DEV_ROWS = os.path.join(HERE, "outputs", "tti", "v18_dev_rows.jsonl")
OUT = os.path.join(HERE, "outputs", "tti", "v18_prospective_report.json")
ROWS = os.path.join(HERE, "outputs", "tti", "v18_prospective_rows.jsonl")
START = os.path.join(HERE, "logs", "v18", "prospective_start.json")
MARKER = os.path.join(HERE, "logs", "V18_PROSPECTIVE_DONE")
OUTCOMES = ("NO_ORACLE_PROPOSER_ACCEPTED", "PROPOSER_WORKS_BUT_NOT_FAILURE_SPECIFIC",
            "FAILURE_SPECIFIC_BUT_NOT_END_TO_END", "NO_ORACLE_PROPOSER_NOT_ESTABLISHED",
            "PROPOSER_LEAKAGE", "NO_VERDICT_FIXTURE_SHORTFALL", "NO_VERDICT_RUN_ERROR")


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def freeze_problems():
    with open(MANIFEST) as handle:
        man = json.load(handle)
    p = []
    with open(MANIFEST + ".sha256") as handle:
        if handle.read().split()[0] != sha(MANIFEST):
            p.append("manifest")
    if sha(os.path.join(HERE, man["protocol_doc"])) != man["protocol_doc_sha256"]:
        p.append("protocol")
    for rel, d in man["implementation_sha256"].items():
        if sha(os.path.join(HERE, rel)) != d:
            p.append(rel)
    for name, root in L.dependency_roots(HERE).items():
        if L.tree_digest(root) != man["dependency_tree_sha256"][name]:
            p.append(f"dependency:{name}")
    for path, d in man["external_file_sha256"].items():
        if not os.path.exists(path) or sha(path) != d:
            p.append(f"external:{os.path.basename(path)}")
    if L.runtime_versions() != man["runtime_versions"]:
        p.append("runtime_versions")
    if X.k_identity() != man["k_identity"]:
        p.append("k_identity")
    if N_TASKS is None or W_MIN is None:
        p.append("thresholds unset")
    return p, man


def normalized_canonical(schema) -> str:
    blocks = [(p, sel if sel else ("all",), f) for p, sel, f in P.S.CV.blocks_from_ast(schema)]
    return P.canonical(P.S.CV.ast_from_blocks(blocks))


def heldout_exact(rec, held) -> bool:
    import numpy as np
    if not rec.get("selected"):
        return False
    pred = P._evaluate(rec["selected_fitted"], held[0])
    return bool(pred is not None and np.array_equal(pred, held[1]))


def run_task(i, t, donor_failure, dev_structures):
    from cora_tti import scoped_slot_fitting as SF
    fitted, _ = SF.fit_induced_occurrences(t["schema"], t["train"])
    target_fp = P.behaviour(fitted)
    canon = normalized_canonical(t["schema"])
    row = {"i": i, "seed": t["seed"], "family": t["family"], "digest": t["digest"],
           "blocks": len(P.S.CV.blocks_from_ast(t["schema"])), "seen_structure": canon in dev_structures,
           "arms": {}}
    main = None
    for arm in P.ARMS:
        rec = P.solve(t["train"], arm, donor_failure=donor_failure if arm == "SHUFFLED_FRONTIER" else None,
                      keep=True)
        d = rec.get("diag", {})
        row["arms"][arm] = {
            "class": rec["class"], "proposals": rec["proposals"], "capped": rec["capped"],
            "verified_by_depth": rec.get("verified_by_depth"), "selection": rec["selection"],
            "seconds": rec["seconds"], "detail": rec.get("detail"),
            "selected": rec["selected"]["canonical"] if rec.get("selected") else None,
            "useful": heldout_exact(rec, t["held"]),
            "selected_equivalent": bool(rec.get("selected") and rec["selected"]["fingerprint"] == target_fp),
            "target_proposed": canon in d.get("proposals", []),
            "target_equivalent_verified": target_fp in d.get("verified_fingerprints", [])}
        if arm == "FAILURE_CONDITIONED":
            main = rec
    if main is not None and main["class"] == "SELECTED":
        st = P.engine_stage(t["train"], t["held"], main)
        for k in ("with", "without"):
            if isinstance(st.get(k), dict):
                st[k].pop("program", None)
        row["engine"] = st
        row["s6"] = P.separation(main, t["train"])
        loo = P.real_loo(t["train"])
        row["real_loo"] = {"passed": loo["passed"], "folds_success": loo["folds_success"],
                           "folds": [{k: f.get(k) for k in ("fold", "class", "proposer_class", "selected",
                                                              "accepted", "uses", "heldout_exact",
                                                              "events", "selection", "input_sha256")}
                                     for f in loo["folds"]]}
        eng = st if st.get("class") != "COMPILE_FAILURE" else {}
        witness = {"B": eng.get("without", {}).get("accepted") is False,
                   "P": True, "U": bool(eng.get("uses")), "L": loo["passed"],
                   "T": bool(eng.get("with", {}).get("heldout_exact")),
                   "A": eng.get("without", {}).get("accepted") is False
                   and not eng.get("without", {}).get("heldout_exact")}
        row["witness"] = dict(witness, complete=all(witness.values()))
    else:
        row["witness"] = {"complete": False, "P": False}
    return row


def binom_upper_p(b, c) -> float:
    """One-sided exact sign test on discordant tasks: P(X >= b) for X ~
    Binomial(b + c, 1/2)."""
    n = b + c
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(b, n + 1)) / 2 ** n


def compare(rows, arm_a, arm_b) -> dict:
    b = sum(1 for r in rows if r["arms"][arm_a]["useful"] and not r["arms"][arm_b]["useful"])
    c = sum(1 for r in rows if r["arms"][arm_b]["useful"] and not r["arms"][arm_a]["useful"])
    p = binom_upper_p(b, c)
    return {"a_only": b, "b_only": c, "p_one_sided": p, "pass": b > c and p < ALPHA}


def main():
    for path in (OUT, ROWS, START, MARKER):
        if os.path.exists(path):
            raise SystemExit(f"refusing: {os.path.relpath(path, HERE)} exists; the prospective test runs once")
    env = X.kstar_environment_problems()
    if env:
        raise SystemExit(f"environment problems, refusing: {env}")
    problems, man = freeze_problems()
    if problems:
        raise SystemExit(f"freeze problems, refusing: {problems}")
    started = time.time()
    with open(START, "w") as handle:
        handle.write(json.dumps({"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "pid": os.getpid(), "manifest_sha256": sha(MANIFEST),
                                 "environment": L.environment_snapshot(),
                                 "loadavg": list(os.getloadavg()), "cpus": os.cpu_count()},
                                indent=1, sort_keys=True) + "\n")
    with open(EXCLUSION) as handle:
        exclusion = set(json.load(handle)["target_digests"])
    dev_structures = set()
    with open(DEV_ROWS) as handle:
        for line in handle:
            dev_structures.add(json.loads(line)["target_normalized"])
    rows, unexpected, tasks = [], [], []
    try:
        tasks = CORPUS.tasks(CORPUS.PROSPECTIVE_BASE, N_TASKS, exclude_digests=exclusion)
    except Exception:                                          # noqa: BLE001
        unexpected.append({"stage": "corpus", "traceback": traceback.format_exc()})
    if not unexpected and len(tasks) == N_TASKS:
        for i, t in enumerate(tasks):
            j = (i + 1) % len(tasks)
            while tasks[j]["digest"] == t["digest"]:
                j = (j + 1) % len(tasks)
            try:
                donor = P.build_input(tasks[j]["train"])["failure"]
                row = run_task(i, t, donor, dev_structures)
                row["donor_seed"] = tasks[j]["seed"]
            except Exception as exc:                           # noqa: BLE001
                row = {"i": i, "seed": t["seed"], "error": "UNEXPECTED", "exception": type(exc).__name__,
                       "traceback": traceback.format_exc()}
                unexpected.append({"stage": f"task {i}", "exception": type(exc).__name__})
            rows.append(row)
            with open(ROWS, "a") as handle:
                handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
    ok = [r for r in rows if "error" not in r]
    leakage = sum(1 for r in ok for a in r["arms"].values() if a["class"] == "LEAKAGE_FAILURE")
    gates = {}
    if len(tasks) < N_TASKS and not unexpected:
        outcome = "NO_VERDICT_FIXTURE_SHORTFALL"
    elif unexpected:
        outcome = "NO_VERDICT_RUN_ERROR"
    elif leakage:
        outcome = "PROPOSER_LEAKAGE"
    else:
        witnesses = sum(1 for r in ok if r["witness"]["complete"])
        gates = {"G1_vs_shuffled_frontier": compare(ok, "FAILURE_CONDITIONED", "SHUFFLED_FRONTIER"),
                 "G1_vs_demo_only": compare(ok, "FAILURE_CONDITIONED", "DEMO_ONLY"),
                 "G2_witnesses": {"complete": witnesses, "required": W_MIN, "pass": witnesses >= W_MIN}}
        g1 = gates["G1_vs_shuffled_frontier"]["pass"] and gates["G1_vs_demo_only"]["pass"]
        g2 = gates["G2_witnesses"]["pass"]
        outcome = ("NO_ORACLE_PROPOSER_ACCEPTED" if g1 and g2 else
                   "PROPOSER_WORKS_BUT_NOT_FAILURE_SPECIFIC" if g2 else
                   "FAILURE_SPECIFIC_BUT_NOT_END_TO_END" if g1 else
                   "NO_ORACLE_PROPOSER_NOT_ESTABLISHED")
    supplementary = {}
    if ok:
        supplementary = {
            "useful_by_arm": {a: sum(1 for r in ok if r["arms"][a]["useful"]) for a in P.ARMS},
            "classes_by_arm": {a: {c: sum(1 for r in ok if r["arms"][a]["class"] == c)
                                   for c in sorted({r["arms"][a]["class"] for r in ok})} for a in P.ARMS},
            "selection_levels": {lv: sum(1 for r in ok if (r["arms"]["FAILURE_CONDITIONED"]["selection"] or {})
                                         .get("level") == lv) for lv in P.SELECTION_LEVELS},
            "pure_vs_hybrid": compare(ok, "FAILURE_CONDITIONED", "PURE"),
            "response_vs_no_response": compare(ok, "FAILURE_CONDITIONED", "NO_RESPONSE"),
            "witness_parts": {k: sum(1 for r in ok if r["witness"].get(k)) for k in "BPULTA"},
            "s6_new_capability": sum(1 for r in ok if r.get("s6", {}).get("new_capability")),
            "seen_unseen": {s: {"tasks": sum(1 for r in ok if r["seen_structure"] == (s == "seen")),
                                "witnesses": sum(1 for r in ok if r["seen_structure"] == (s == "seen")
                                                 and r["witness"]["complete"])}
                            for s in ("seen", "unseen")},
            "by_family": {f: {"tasks": sum(1 for r in ok if r["family"] == f),
                              "witnesses": sum(1 for r in ok if r["family"] == f and r["witness"]["complete"])}
                          for f in sorted({r["family"] for r in ok})}}
    report = {"outcome": outcome, "gates": gates, "supplementary": supplementary, "tasks": len(tasks),
              "unexpected": unexpected, "leakage": leakage, "seed_base": CORPUS.PROSPECTIVE_BASE,
              "manifest_sha256": sha(MANIFEST), "seconds": round(time.time() - started, 1),
              "environment_at_end": L.environment_snapshot(), "loadavg_end": list(os.getloadavg())}
    with open(OUT, "w") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    with open(MARKER, "w") as handle:
        handle.write(outcome + "\n")
    print(json.dumps({"outcome": outcome, "gates": gates}, indent=1, default=str))


if __name__ == "__main__":
    main()
