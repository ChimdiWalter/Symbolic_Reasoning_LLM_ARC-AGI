"""Generate Item-2 v1.4 counterfactual-twin groups.

    smoke   feasibility only: seeds from SMOKE_BASE, written under
            logs/v14_feasibility/, NEVER audited, used only to size the cap
    full    the frozen experiment: seeds from SEED_BASE, written under
            outputs/tti/v14_twin_corpus/, stops at the frozen target group
            count, the slot cap or the wall-clock cap, whichever comes first

One writer, resumable: an existing slot record is never recomputed. Nothing
is trained, and no distance between episodes is computed here.

Erratum 2: the target counts UNIQUE group digests. On resume the included
digests are rebuilt from the existing records in ascending slot order (the
first admission of a digest counts), and a candidate pair whose group digest
is already included is skipped before any engine run and recorded as
DUPLICATE_GROUP_DIGEST with its provenance. The rule uses the digest and the
slot order only.
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

G, CD, CV = L.G, L.CD, L.CV

PROTOCOL = os.path.join(HERE, "docs",
                        "CORA_TTI_MECHANISTIC_FRONTIER_LOCALIZATION_v1.4.md")
MANIFEST = os.path.join(HERE, "outputs", "tti",
                        "mechanistic_frontier_v14_manifest.json")
FAMILIES = ["(0,0)", "(1,0)", "(0,1)", "(1,1)", "(0,0,0)"]


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


def frozen_manifest():
    with open(MANIFEST) as handle:
        man = json.load(handle)
    problems = freeze_problems(man)
    if problems:
        raise SystemExit(f"freeze check failed: {problems}")
    return man


def settings(mode, args):
    v13 = G.manifest()
    common = {"budgets": v13["budgets"],
              "gate": {"require": "frontier_term_count >= 2"}}
    if mode == "full":
        man = frozen_manifest()
        caps = man["caps"]
        return dict(common, base=L.SEED_BASE, prefix="full", manifest=man,
                    out=os.path.join(HERE, "outputs", "tti", "v14_twin_corpus"),
                    engine=os.path.join(HERE, "outputs", "tti", "v14_engine"),
                    target=caps["target_groups"], slots=caps["slot_cap"],
                    wall=caps["wall_clock_s"],
                    run_end="full_run_end_erratum2.json")
    return dict(common, base=L.SMOKE_BASE, prefix="smoke", manifest=None,
                out=os.path.join(HERE, "logs", "v14_feasibility"),
                engine=os.path.join(HERE, "logs", "v14_feasibility", "engine"),
                target=args.target, slots=args.slots, wall=args.wall,
                run_end="smoke_run_end.json")


def run_slot(slot, fam, cfg, seen=frozenset()):
    record = {"slot": slot, "anchor_family": CV.family_text(fam),
              "contrast_type": "FEATURE", "admitted": False, "group": None,
              "pair_attempts": 0, "replicate_attempts": 0, "rejections": {}}

    def reject(code):
        record["rejections"][code] = record["rejections"].get(code, 0) + 1

    for attempt in range(L.ATTEMPTS_PER_SLOT):
        record["pair_attempts"] = attempt + 1
        pair_seed = cfg["base"] + slot * L.SLOT_STRIDE + attempt * L.ATTEMPT_STRIDE
        anchor = CD.sample_target(pair_seed, fam)
        contrast = G.contrast_target(anchor, "FEATURE", rotation=attempt)
        ok, why = L.twin_law(anchor, contrast)
        if not ok:
            reject(f"{L.R_TWIN_LAW}:{why}")
            continue
        #  erratum 2: an already-included group is skipped before any engine
        #  run; the decision uses the pair's digest only
        da0, db0 = CV.digest(anchor), CV.digest(contrast)
        digest = G.group_digest(da0, db0)
        if digest in seen:
            reject(L.R_DUPLICATE_GROUP)
            record.setdefault("duplicate_skips", []).append(
                {"slot": slot, "attempt": attempt, "pair_seed": pair_seed,
                 "target_digests": [da0, db0], "group_digest": digest})
            continue
        reps = []
        for k in range(L.SEEDS_PER_PAIR):
            if len(reps) + (L.SEEDS_PER_PAIR - k) < L.REPLICATES:
                break
            record["replicate_attempts"] += 1
            code, twin = L.make_twin_replicate(
                anchor, contrast, pair_seed + k, cfg["budgets"], cfg["gate"],
                (cfg["prefix"], slot, attempt, k), cfg["engine"])
            if code != L.ADMITTED:
                reject(code)
                continue
            reps.append(twin)
            if len(reps) == L.REPLICATES:
                break
        if len(reps) < L.REPLICATES:
            reject(L.R_PAIR_SHORT)
            continue
        episodes = []
        for r, twin in enumerate(reps):
            for t in (0, 1):
                ep = twin[t]
                ep["target_index"] = t
                ep["replicate_index"] = r
                episodes.append(ep)
        da, db = reps[0][0]["target_digest"], reps[0][1]["target_digest"]
        record["group"] = {"group_digest": G.group_digest(da, db),
                           "contrast_type": "FEATURE",
                           "anchor_family": CV.family_text(fam),
                           "target_digests": [da, db],
                           "pair_seed": pair_seed,
                           "episodes": episodes}
        record["admitted"] = True
        break
    return record


def write_atomic(path, obj, **kw):
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(obj, handle, default=str, **kw)
    os.replace(tmp, path)


def continue_run(cfg, families, first, run_slot_fn=None, clock=time.time):
    """Fill slots in ascending order. An existing record is read, never
    rewritten, and its admission is counted by the erratum-2 rule: the first
    admission of a group digest in slot order is included. Stops at the first
    of: the target of unique groups, the slot cap, or the wall clock counted
    from the first start."""
    run_slot_fn = run_slot_fn or run_slot
    seen, raw = set(), 0
    started, stop = time.monotonic(), "slot_cap"
    for slot in range(cfg["slots"]):
        path = os.path.join(cfg["out"], f"{cfg['prefix']}{slot:05d}.json")
        if os.path.exists(path):
            with open(path) as handle:
                existing = json.load(handle)
            if existing["admitted"]:
                raw += 1
                seen.add(existing["group"]["group_digest"])
            continue
        if len(seen) >= cfg["target"]:
            stop = "target_groups"
            break
        if clock() - first > cfg["wall"]:
            stop = "wall_clock"
            break
        slot_started = time.monotonic()
        started_since_first = round(clock() - first, 1)
        record = run_slot_fn(slot, families[slot % len(families)], cfg,
                             frozenset(seen))
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
            seen.add(record["group"]["group_digest"])
        print(f"  {cfg['prefix']}{slot:05d} {record['anchor_family']:8s} "
              f"admitted={record['admitted']} pairs={record['pair_attempts']} "
              f"replicates={record['replicate_attempts']} {record['elapsed_s']}s "
              f"unique_groups={len(seen)} total={round(time.monotonic() - started)}s",
              flush=True)
    else:
        stop = "target_groups" if len(seen) >= cfg["target"] else "slot_cap"
    return {"admitted_groups": len(seen), "admitted_records": raw,
            "stop_reason": stop,
            "seconds_this_start": round(time.monotonic() - started, 1),
            "seconds_since_first_start": round(clock() - first, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("smoke", "full"))
    ap.add_argument("--slots", type=int, default=40)
    ap.add_argument("--wall", type=float, default=2700.0)
    ap.add_argument("--target", type=int, default=L.TARGET_GROUPS)
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
    #  the wall clock counts from the FIRST start, across restarts
    state_path = os.path.join(cfg["out"], f"{cfg['prefix']}_run_state.json")
    if os.path.exists(state_path):
        with open(state_path) as handle:
            first = json.load(handle)["first_started_epoch"]
    else:
        first = time.time()
        write_atomic(state_path, {"first_started_epoch": first,
                                  "first_started_utc": time.strftime(
                                      "%Y-%m-%dT%H:%M:%SZ", time.gmtime(first))})

    families = [G.parse_family(f) for f in FAMILIES]
    summary = dict({"mode": args.mode}, **continue_run(cfg, families, first))
    write_atomic(os.path.join(cfg["out"], cfg["run_end"]), summary, indent=1)
    print("RUN_END", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
