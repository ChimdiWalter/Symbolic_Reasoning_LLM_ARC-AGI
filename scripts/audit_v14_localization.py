"""Sealed nonlearned v1.4 stagewise localization audit.

Reads only full-run group records, checks the freeze, the calibration and
every group's integrity and leakage, then computes the frozen stage
descriptors from the allowlisted model view and applies the frozen
statistics and classification ladder. Nothing is trained. Deterministic: two
runs on the same corpus must produce byte-identical reports.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402

COR_DIR = os.path.join(HERE, "outputs", "tti", "v14_twin_corpus")
CAL_FILE = os.path.join(HERE, "outputs", "tti", "v13_calibration",
                        "calibration.json")
CAL_SHA256 = "ba82865e52cd9e025442ea73ee7ad83ee894b5ad8610a7753ce37a44051c7c02"
PROTOCOL = os.path.join(HERE, "docs",
                        "CORA_TTI_MECHANISTIC_FRONTIER_LOCALIZATION_v1.4.md")
MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "mechanistic_frontier_v14_manifest.json")
FULL_RECORD = re.compile(r"^full\d{5}\.json$")


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def verify_freeze():
    with open(MANIFEST) as handle:
        man = json.load(handle)
    problems = []
    if sha256(PROTOCOL) != man["protocol_doc_sha256"]:
        problems.append("protocol")
    with open(MANIFEST + ".sha256") as handle:
        if handle.read().split()[0] != sha256(MANIFEST):
            problems.append("manifest")
    for rel, digest in sorted(man["implementation_sha256"].items()):
        if sha256(os.path.join(HERE, rel)) != digest:
            problems.append(rel)
    for name, root in sorted(L.dependency_roots(HERE).items()):
        if L.tree_digest(root) != man["dependency_tree_sha256"][name]:
            problems.append(f"dependency:{name}")
    if sha256(CAL_FILE) != CAL_SHA256:
        problems.append("calibration")
    return man, problems


def load_records(cor_dir=COR_DIR):
    records = []
    for name in sorted(os.listdir(cor_dir)):
        if FULL_RECORD.match(name):
            with open(os.path.join(cor_dir, name)) as handle:
                records.append(json.load(handle))
    return records


def main():
    man, freeze_problems = verify_freeze()
    records = load_records()
    groups = sorted((r["group"] for r in records if r.get("admitted")),
                    key=lambda g: g["group_digest"])
    rejections = {}
    for r in records:
        for code, n in r.get("rejections", {}).items():
            rejections[code] = rejections.get(code, 0) + n
    integrity = {g["group_digest"]: L.integrity_problems(g) for g in groups}
    integrity = {k: v for k, v in integrity.items() if v}
    leaks = {}
    for g in groups:
        for e in g["episodes"]:
            found = L.view_leaks(e, g)
            if found:
                leaks.setdefault(g["group_digest"], []).append(
                    [e["target_index"], e["replicate_index"], found])
    engine_state = sorted({p for r in records
                           for p in r.get("engine_state_problems", [])})
    digests = {d for g in groups for d in g["target_digests"]}
    report = {
        "protocol_doc_sha256": man["protocol_doc_sha256"],
        "calibration_sha256": CAL_SHA256,
        "slots": len(records),
        "admitted_groups": len(groups),
        "episodes": sum(len(g["episodes"]) for g in groups),
        "distinct_targets": len(digests),
        "groups_by_anchor_family": {
            f: sum(1 for g in groups if g["anchor_family"] == f)
            for f in sorted({g["anchor_family"] for g in groups})},
        "rejections": dict(sorted(rejections.items())),
        "freeze_problems": freeze_problems,
        "integrity_problems": integrity,
        "leaks": leaks,
        "engine_state_problems": engine_state,
    }
    blocked = freeze_problems or integrity or leaks or engine_state
    if blocked:
        report["verdict"] = "AUDIT_BLOCKED"
    elif not groups:
        report["verdict"] = "NO_ADMITTED_GROUPS"
    else:
        with open(CAL_FILE) as handle:
            cal = json.load(handle)
        out = L.audit_groups(groups, cal)
        report["stages"] = out["stages"]
        report["sensitivity"] = out["sensitivity"]
        report["classification"] = out["classification"]
        report["verdict"] = out["classification"]["classification"]
    text = json.dumps(report, sort_keys=True, indent=1)
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        HERE, "outputs", "tti", "v14_localization_audit.json")
    with open(target, "w") as handle:
        handle.write(text + "\n")

    print(f"slots {report['slots']}  groups {report['admitted_groups']}  "
          f"episodes {report['episodes']}  targets {report['distinct_targets']}")
    if blocked:
        print("AUDIT BLOCKED", freeze_problems, integrity, leaks, engine_state)
        return
    if not groups:
        print("no admitted groups")
        return
    print(f"{'stage':6s} {'hits':>9s} {'rate':>7s} {'p_binom':>9s} "
          f"{'credit':>7s} {'p_rand':>9s} {'ties':>5s} {'mean s':>8s} "
          f"{'med s':>8s}  identifying")
    for s in L.ALL_STAGES:
        r = report["stages"][s]
        print(f"{s:6s} {r['strict_hits']:>4d}/{r['total']:<4d} "
              f"{r['strict_rate']:7.4f} {r['p_binomial']:9.2e} "
              f"{r['credit_rate']:7.4f} {r['p_randomization']:9.2e} "
              f"{r['tie_fraction']:5.2f} {r['separation_mean']:8.4f} "
              f"{r['separation_median']:8.4f}  "
              f"{'YES' if r['target_identifying'] else 'no'}")
    print("sensitivity: twin distance against the same-input rerun")
    for s in L.CORA_STAGES:
        r = report["sensitivity"][s]
        print(f"{s:6s} twin farther {r['twin_farther']:4d}  rerun farther "
              f"{r['rerun_farther']:4d}  ties {r['ties']:4d}  p {r['p_sign']:9.2e}  "
              f"{'REACTS' if r['reacts'] else 'no'}")
    c = report["classification"]
    print("CLASSIFICATION", c["classification"], "determining",
          c["determining_stage"], "reason", c["reason"])


if __name__ == "__main__":
    main()
