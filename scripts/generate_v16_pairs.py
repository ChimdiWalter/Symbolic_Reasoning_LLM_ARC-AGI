"""Generate the Item-2 v1.6 prospective bounded-repair test corpus.

    full    seeds from TEST_BASE_V16 (500,000,000), written under
            outputs/tti/v16_test_corpus/; stops at the frozen number of unique
            groups, the slot cap or the wall-clock cap from the first start

The admission law is v1.5's, unchanged: one FEATURE pair from the frozen
grammar per group, REPLICATES admitted episodes per target on independent
seeds, the same full-engine observation, and pairs skipped before any engine
run when their group or target digest is in the frozen v1.6 exclusion set
(every v1.2 to v1.5 digest, including the v1.5 test corpus that served as
v1.6 development data) or already in this corpus. One writer under flock,
resumable from the first missing slot, existing records never rewritten,
every slot re-verifies the v1.6 freeze. Nothing is fitted or scored here.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v15_sel as S                             # noqa: E402

G = S.G
PROTOCOL = os.path.join(HERE, "docs",
                        "CORA_TTI_CANDIDATE_FAILURE_RESPONSE_v1.6.md")
MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "candidate_failure_response_v16_manifest.json")
EXCLUSION_V16 = os.path.join(HERE, "outputs", "tti", "v16_exclusion_digests.json")
TEST_BASE_V16 = 500_000_000


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def freeze_problems(man):
    problems = []
    if sha256(PROTOCOL) != man["protocol_doc_sha256"]:
        problems.append("protocol")
    with open(MANIFEST + ".sha256") as handle:
        if handle.read().split()[0] != sha256(MANIFEST):
            problems.append("manifest")
    for rel, digest in man["implementation_sha256"].items():
        if sha256(os.path.join(HERE, rel)) != digest:
            problems.append(rel)
    for name, root in L.dependency_roots(HERE).items():
        if L.tree_digest(root) != man["dependency_tree_sha256"][name]:
            problems.append(f"dependency:{name}")
    for path, digest in man["external_file_sha256"].items():
        if sha256(path) != digest:
            problems.append(path)
    if L.runtime_versions() != man["runtime_versions"]:
        problems.append("runtime_versions")
    return problems


def settings(mode, args):
    if mode != "full":
        raise SystemExit("v1.6 has no pilot mode")
    v13 = G.manifest()
    with open(MANIFEST) as handle:
        man = json.load(handle)
    problems = freeze_problems(man)
    if problems:
        raise SystemExit(f"freeze check failed: {problems}")
    caps = man["caps"]
    return {"budgets": v13["budgets"],
            "gate": {"require": "frontier_term_count >= 2"},
            "exclusion": S.load_exclusion(EXCLUSION_V16),
            "base": TEST_BASE_V16, "prefix": "full", "manifest": man,
            "out": os.path.join(HERE, "outputs", "tti", "v16_test_corpus"),
            "engine": os.path.join(HERE, "outputs", "tti", "v16_engine"),
            "target": caps["test_groups"], "slots": caps["slot_cap"],
            "wall": caps["wall_clock_s"]}


def write_atomic(path, obj, **kw):
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(obj, handle, default=str, **kw)
    os.replace(tmp, path)


def continue_run(cfg, families, first, run_slot_fn=None, clock=time.time):
    """Fill slots in ascending order. Existing records are read, never
    rewritten; their first admissions rebuild the included group and target
    digests. Stops at the first of: the target of unique groups, the slot
    cap, or the wall clock counted from the first start."""
    run_slot_fn = run_slot_fn or S.run_slot
    seen_groups, seen_targets, raw = set(), set(), 0
    started, stop = time.monotonic(), "slot_cap"
    for slot in range(cfg["slots"]):
        path = os.path.join(cfg["out"], f"{cfg['prefix']}{slot:05d}.json")
        if os.path.exists(path):
            with open(path) as handle:
                existing = json.load(handle)
            if existing["admitted"]:
                raw += 1
                g = existing["group"]
                if g["group_digest"] not in seen_groups:
                    seen_groups.add(g["group_digest"])
                    seen_targets.update(g["target_digests"])
            continue
        if len(seen_groups) >= cfg["target"]:
            stop = "target_groups"
            break
        now = clock()
        if now - first > cfg["wall"]:
            stop = "wall_clock"
            break
        slot_started = time.monotonic()
        started_since_first = round(now - first, 1)
        record = run_slot_fn(slot, families[slot % len(families)], cfg,
                             frozenset(seen_groups), frozenset(seen_targets))
        record["started_since_first_start_s"] = started_since_first
        record["elapsed_s"] = round(time.monotonic() - slot_started, 2)
        record["engine_state_problems"] = L.engine_state_problems(cfg["engine"])
        record["environment"] = L.environment_snapshot()
        record["runtime_versions"] = L.runtime_versions()
        record["freeze_ok"] = (not freeze_problems(cfg["manifest"])
                               if cfg["manifest"] else None)
        record["manifest_sha256"] = sha256(MANIFEST) if cfg["manifest"] else None
        write_atomic(path, record)
        if record["admitted"]:
            raw += 1
            g = record["group"]
            if g["group_digest"] not in seen_groups:
                seen_groups.add(g["group_digest"])
                seen_targets.update(g["target_digests"])
        print(f"  {cfg['prefix']}{slot:05d} {record['anchor_family']:8s} "
              f"admitted={record['admitted']} pairs={record['pair_attempts']} "
              f"replicates={record['replicate_attempts']} skips={len(record['skips'])} "
              f"{record['elapsed_s']}s groups={len(seen_groups)} "
              f"total={round(time.monotonic() - started)}s", flush=True)
        #  erratum 1: a failed freeze check ends the run at once; the record
        #  that shows it is kept, and the evaluator will block
        if cfg["manifest"] and record["freeze_ok"] is not True:
            stop = "freeze_failed"
            break
    else:
        stop = "target_groups" if len(seen_groups) >= cfg["target"] else "slot_cap"
    return {"admitted_groups": len(seen_groups), "admitted_records": raw,
            "stop_reason": stop,
            "seconds_this_start": round(time.monotonic() - started, 1),
            "seconds_since_first_start": round(clock() - first, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("full",))
    ap.add_argument("--slots", type=int, default=60)
    ap.add_argument("--wall", type=float, default=2700.0)
    ap.add_argument("--target", type=int, default=10 ** 6)
    args = ap.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("PYTHONHASHSEED must be 0")
    cfg = settings(args.mode, args)
    os.makedirs(cfg["out"], exist_ok=True)
    os.makedirs(cfg["engine"], exist_ok=True)
    problems = L.engine_state_problems(cfg["engine"])
    if problems:
        raise SystemExit(f"engine state is not clean: {problems}")
    lock = open(os.path.join(cfg["out"], ".writer.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit("another writer holds the lock")
    state_path = os.path.join(cfg["out"], f"{cfg['prefix']}_run_state.json")
    if os.path.exists(state_path):
        with open(state_path) as handle:
            first = json.load(handle)["first_started_epoch"]
    else:
        first = time.time()
        write_atomic(state_path, {"first_started_epoch": first,
                                  "first_started_utc": time.strftime(
                                      "%Y-%m-%dT%H:%M:%SZ", time.gmtime(first))})
    families = [G.parse_family(f) for f in S.FAMILIES]
    summary = dict({"mode": args.mode}, **continue_run(cfg, families, first))
    write_atomic(os.path.join(cfg["out"], f"{cfg['prefix']}_run_end.json"),
                 summary, indent=1)
    print("RUN_END", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
