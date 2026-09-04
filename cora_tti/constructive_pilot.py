"""Deterministic pilot runner for the Item-2 Block-B constructive corpus.

Runs the frozen requested-slot schedule, one terminal outcome per attempt,
durable per-slot outputs so a crash never erases completed work, and a resume
path that verifies the generation-manifest hash before accepting prior
records. Never regenerates a finalized slot under new seeds.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from cora_tti import constructive_dataset as CD          # noqa: E402
from cora_tti import constructive_vocabulary as CV       # noqa: E402

OUT = ROOT / "outputs" / "tti"
SLOTS_DIR = OUT / "constructive_pilot_slots"
GEN_MANIFEST = OUT / "constructive_pilot_generation_manifest.json"
GEN_MANIFEST_HASH = OUT / "constructive_pilot_generation_manifest_hash.txt"

#: implementation parameter, frozen in the generation manifest before any row
MAX_ATTEMPTS_PER_SLOT = 25
BUDGETS = {"per_target_s": 90.0, "base_search_s": 8.0, "tfg_s": 2.0}

TRAIN_FAMILIES = ((0, 0), (1, 0), (0, 1), (1, 1), (0, 0, 0))
HOLDOUT_FAMILIES = ((2,), (2, 1))


def slot_schedule() -> list:
    """The frozen deterministic requested-slot schedule: 40 train, 8 val,
    6 complete-AST test, 6 structural-family test (3 per holdout family)."""
    slots = []
    index = 0
    for count, split, regime in ((40, "train", "train_pool"),
                                 (8, "val", "train_pool"),
                                 (6, "test", "ast_holdout")):
        for position in range(count):
            family = TRAIN_FAMILIES[position % len(TRAIN_FAMILIES)]
            slots.append({"slot": index, "split": split, "regime": regime,
                          "requested_family": list(family),
                          "seed_base": 11000 + index * 131,
                          "max_attempts": MAX_ATTEMPTS_PER_SLOT})
            index += 1
    for position in range(6):
        family = HOLDOUT_FAMILIES[position % len(HOLDOUT_FAMILIES)]
        slots.append({"slot": index, "split": "test",
                      "regime": "structural_holdout",
                      "requested_family": list(family),
                      "seed_base": 13000 + index * 131,
                      "max_attempts": MAX_ATTEMPTS_PER_SLOT})
        index += 1
    return slots


def _verify_generation_manifest() -> str:
    text = GEN_MANIFEST.read_text()
    digest = hashlib.sha256(text.encode()).hexdigest()
    pinned = GEN_MANIFEST_HASH.read_text().split()[0]
    if digest != pinned:
        raise SystemExit(f"generation manifest drift: {digest[:12]} != {pinned[:12]}")
    return digest


def run(limit: int | None = None) -> dict:
    manifest_hash = _verify_generation_manifest()
    SLOTS_DIR.mkdir(parents=True, exist_ok=True)
    schedule = slot_schedule()
    if limit:
        schedule = schedule[:limit]
    seen_digests, seen_train_digests = set(), set()
    #  reload finalized slots (resume path)
    for path in sorted(SLOTS_DIR.glob("slot*.json")):
        row = json.loads(path.read_text())
        if row.get("generation_manifest_hash") != manifest_hash:
            raise SystemExit(f"stale slot record {path.name}: manifest mismatch")
        if row.get("admitted"):
            seen_digests.add(row["episode"]["target_digest"])
            if row["split"] == "train":
                seen_train_digests.add(row["episode"]["target_digest"])

    for slot in schedule:
        out_path = SLOTS_DIR / f"slot{slot['slot']:03d}.json"
        if out_path.exists():
            continue
        family = tuple(slot["requested_family"])
        attempts, admitted_episode, outcome_counts = [], None, {}
        started = time.monotonic()
        for attempt in range(slot["max_attempts"]):
            seed = slot["seed_base"] + attempt * 7919
            schema = CD.sample_target(seed, family)
            try:
                outcome, episode, evidence = CD.evaluate_target(
                    schema, seed=seed, split=slot["split"],
                    regime=slot["regime"], allowed_families=[family],
                    seen_digests=seen_digests,
                    seen_train_digests=seen_train_digests,
                    train_families=set(TRAIN_FAMILIES), budgets=BUDGETS,
                    row_index=slot["slot"])
            except Exception as error:                    # noqa: BLE001
                outcome = f"infra_exception:{type(error).__name__}"
                episode, evidence = None, {"error": repr(error)[:200]}
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
            attempts.append({"attempt": attempt, "seed": seed,
                             "family": list(family), "outcome": outcome,
                             "stage_times": evidence.get("stage_times", {}),
                             "base_search": evidence.get("base_search"),
                             "baseline_audit_fitted":
                                 (evidence.get("baseline_shape_audit") or {}).get("fitted")})
            if outcome == CD.ADMITTED:
                admitted_episode = episode
                seen_digests.add(episode.target_digest)
                if slot["split"] == "train":
                    seen_train_digests.add(episode.target_digest)
                break
        record = {"slot": slot["slot"], "split": slot["split"],
                  "regime": slot["regime"],
                  "requested_family": slot["requested_family"],
                  "max_attempts": slot["max_attempts"],
                  "attempts_used": len(attempts),
                  "admitted": admitted_episode is not None,
                  "outcome_counts": dict(sorted(outcome_counts.items())),
                  "attempts": attempts,
                  "episode": admitted_episode.to_json() if admitted_episode else None,
                  "generation_manifest_hash": manifest_hash,
                  "elapsed_s": round(time.monotonic() - started, 2)}
        out_path.write_text(json.dumps(record, sort_keys=True))
        print(f"slot {slot['slot']:03d} {slot['split']:5} "
              f"{CV.family_text(family):8} admitted={record['admitted']} "
              f"attempts={record['attempts_used']} "
              f"{json.dumps(record['outcome_counts'])} {record['elapsed_s']}s",
              flush=True)
    return {"slots": len(schedule)}


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(limit)
    print("PILOT_RUN_COMPLETE", flush=True)
