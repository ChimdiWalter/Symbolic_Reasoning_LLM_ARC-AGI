"""Step 2: read-only all-arm transfer audit.

Phase 5 ran the baseline only where the treatment had already solved, so it
could not see tasks where K solves and K + C1 does not. That is negative
transfer, and a claim that learned knowledge improves future reasoning has
to know whether it also damages anything.

Both arms run on every task. Nothing is tuned or repaired from these
results.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_concept as C  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_env as E  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_concept():
    d = list(json.loads((OUT / "v21_concept_registry.json").read_text()).values())[0]
    return C.Concept(
        name=d["name"], schema=V.from_json(d["schema"]),
        slot_types={k: V.parse_type(v) for k, v in d["slot_types"].items()},
        provenance=tuple(d["provenance"]),
        source_hashes=tuple(d["source_program_sha256"]),
        result_type=V.parse_type(d["result_type"]), cost=d["cost"])


def main():
    manifest = json.loads((OUT / "v21_level3_manifest.json").read_text())
    for key, path in (("search", ROOT / "geocat_arc/object_reasoning/meta_v21_search.py"),
                      ("runtime", ROOT / "geocat_arc/object_reasoning/meta_v21.py"),
                      ("concept_registry", OUT / "v21_concept_registry.json")):
        if sha(path) != manifest["hashes"][key]:
            print(f"REFUSING TO RUN: {key} drifted")
            return
    concept = load_concept()
    baseline_env = E.BASE_ENV
    treatment_env = E.BASE_ENV.with_concept(concept)

    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    lockbox = json.loads((OUT.parent / "lockbox" / "manifest.json").read_text())
    tasks = lockbox["tasks"]
    split = ({t["task_id"]: t["split"] for t in tasks} if isinstance(tasks, list)
             else {k: v["split"] for k, v in tasks.items()})
    pool = sorted(t for t, s in split.items()
                  if s == "experience" and t not in concept.provenance)

    counts = Counter()
    interesting = []
    for task_id in pool:
        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in challenges[task_id]["train"]]
        if len(pairs) < 2:
            continue
        base, base_stats = S.search(pairs, env=baseline_env)
        treat, treat_stats = S.search(pairs, env=treatment_env)
        outcome = ("both" if base and treat else
                   "baseline_only" if base else
                   "treatment_only" if treat else "neither")
        counts[outcome] += 1
        if outcome in ("baseline_only", "treatment_only") or \
                (outcome == "both" and base_stats.typed != treat_stats.typed):
            row = {"task": task_id, "outcome": outcome,
                   "baseline_typed": base_stats.typed,
                   "treatment_typed": treat_stats.typed}
            if treat:
                row["uses_concept"] = E.uses_concept(treat[0][0], treatment_env,
                                                     concept.name)
            interesting.append(row)
            print(json.dumps(row), flush=True)

    report = {"pool_size": len(pool), "counts": dict(counts),
              "interesting": interesting,
              "note": ("read-only descriptive audit; nothing was tuned or "
                       "repaired from these results")}
    (OUT / "v21_transfer_audit.json").write_text(json.dumps(report, indent=1))
    print("\nOUTCOME COUNTS")
    for key in ("both", "baseline_only", "treatment_only", "neither"):
        print(f"  {key:16} {counts[key]}")
    print(f"\nNEGATIVE TRANSFER (K solves, K+C1 does not): {counts['baseline_only']}")
    print(f"POSITIVE CAPABILITY (K fails, K+C1 solves):   {counts['treatment_only']}")


if __name__ == "__main__":
    main()
