"""Generate Item-2 v1.4 counterfactual-twin groups.

    smoke   feasibility only: seeds from SMOKE_BASE, written under
            logs/v14_feasibility/, NEVER audited, used only to size the cap
    full    the frozen experiment: seeds from SEED_BASE, written under
            outputs/tti/v14_twin_corpus/, stops at the frozen target group
            count, the slot cap or the wall-clock cap, whichever comes first

One writer, resumable: an existing slot record is never recomputed. Nothing
is trained, and no distance between episodes is computed here.
"""
from __future__ import annotations

import argparse
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


def frozen_manifest():
    with open(MANIFEST) as handle:
        man = json.load(handle)
    if sha256(PROTOCOL) != man["protocol_doc_sha256"]:
        raise SystemExit("protocol document does not match the manifest")
    with open(MANIFEST + ".sha256") as handle:
        if handle.read().split()[0] != sha256(MANIFEST):
            raise SystemExit("manifest does not match its recorded sha256")
    for rel, digest in man["implementation_sha256"].items():
        if sha256(os.path.join(HERE, rel)) != digest:
            raise SystemExit(f"implementation changed after freeze: {rel}")
    for name, root in L.dependency_roots(HERE).items():
        if L.tree_digest(root) != man["dependency_tree_sha256"][name]:
            raise SystemExit(f"reasoner dependency changed after freeze: {name}")
    return man


def settings(mode, args):
    v13 = G.manifest()
    common = {"budgets": v13["budgets"],
              "gate": {"require": "frontier_term_count >= 2"}}
    if mode == "full":
        man = frozen_manifest()
        caps = man["caps"]
        return dict(common, base=L.SEED_BASE, prefix="full",
                    out=os.path.join(HERE, "outputs", "tti", "v14_twin_corpus"),
                    engine=os.path.join(HERE, "outputs", "tti", "v14_engine"),
                    target=caps["target_groups"], slots=caps["slot_cap"],
                    wall=caps["wall_clock_s"])
    return dict(common, base=L.SMOKE_BASE, prefix="smoke",
                out=os.path.join(HERE, "logs", "v14_feasibility"),
                engine=os.path.join(HERE, "logs", "v14_feasibility", "engine"),
                target=args.target, slots=args.slots, wall=args.wall)


def run_slot(slot, fam, cfg):
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

    families = [G.parse_family(f) for f in FAMILIES]
    admitted, started, stop = 0, time.monotonic(), "slot_cap"
    for slot in range(cfg["slots"]):
        path = os.path.join(cfg["out"], f"{cfg['prefix']}{slot:05d}.json")
        if os.path.exists(path):
            with open(path) as handle:
                admitted += int(json.load(handle)["admitted"])
            continue
        if admitted >= cfg["target"]:
            stop = "target_groups"
            break
        if time.monotonic() - started > cfg["wall"]:
            stop = "wall_clock"
            break
        slot_started = time.monotonic()
        record = run_slot(slot, families[slot % len(families)], cfg)
        record["elapsed_s"] = round(time.monotonic() - slot_started, 2)
        record["engine_state_problems"] = L.engine_state_problems(cfg["engine"])
        tmp = path + ".tmp"
        with open(tmp, "w") as handle:
            json.dump(record, handle, default=str)
        os.replace(tmp, path)
        admitted += int(record["admitted"])
        print(f"  {cfg['prefix']}{slot:05d} {record['anchor_family']:8s} "
              f"admitted={record['admitted']} pairs={record['pair_attempts']} "
              f"replicates={record['replicate_attempts']} {record['elapsed_s']}s "
              f"groups={admitted} total={round(time.monotonic() - started)}s",
              flush=True)
    else:
        stop = "target_groups" if admitted >= cfg["target"] else "slot_cap"
    summary = {"mode": args.mode, "admitted_groups": admitted,
               "stop_reason": stop,
               "seconds": round(time.monotonic() - started, 1)}
    with open(os.path.join(cfg["out"], f"{cfg['prefix']}_run_end.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    print("RUN_END", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
