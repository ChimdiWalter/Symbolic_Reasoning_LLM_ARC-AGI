"""One complete acquisition-and-transfer cycle, measured.

The question this answers, in the terms set for it:

    After a failure, what can the system now do that it could not do before,
    what did the system itself construct to make that possible, and does the
    benefit survive an honest test on new evidence?

Structure, following the three declared parts.

A. CONSTRUCT WITHOUT BEING GIVEN THE ANSWER STRUCTURE
   The identified baseline K0 is the single-block meta-language: the complete
   200-hypothesis product of the frozen terminals. For every SOURCE episode
   where K0 completed and failed, the system searched the two-block
   constructive space and found a program that fits every demonstration. It was
   never given the generating target schema, its tables, its digest or its
   family. The constructed extension e is that program's STRUCTURE, with its
   induced tables removed, so e is an open schema whose tables must be refitted
   per task from that task's own demonstrations.

B. SHOW THE EXTENSION DOES USEFUL WORK
   On each TARGET episode, three systems are compared on the same measure, one
   candidate fit per unit:
       K0            the baseline alone
       K0 + E        the baseline plus the frozen library, library tried first
       unlearned     smallest-first search over the whole two-block space
   The library's acquisition cost is reported and amortized explicitly.

C. TEST REUSE BEYOND THE SOURCE TASK
   A library entry is never applied to the episode it came from. Leave-one-out
   is at the level of the SOURCE EPISODE: when episode j is the target, every
   entry acquired from j is withheld. Held-out output correctness on j's fresh
   grids is measured for whatever the library recovers.

ABLATION
   When the library solves a target, the specific entry that solved it is
   removed and the target is retried with the remainder. If the remainder still
   solves it, the benefit is not attributable to that entry.

CLAIM LEVEL. A success here is OPERATIONAL: a constructed schema becomes
reusable and reduces search on tasks that did not create it. It is NOT semantic
expressivity growth, because a two-block composition is expressible in the
evaluator language; K0 simply does not enumerate it. Nothing here is a
full-pipeline leave-one-out certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_v2c as V2C                     # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--study",
                    default=str(ROOT / "outputs" / "tti" / "failure_signal_study" / "results.json"))
parser.add_argument("--out",
                    default=str(ROOT / "outputs" / "tti" / "acquisition_transfer"))
args = parser.parse_args()

OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
CONFIG = MB.BaselineConfig()
study = json.loads(Path(args.study).read_text())
rows = study["rows"]

#  ---- rebuild the episodes exactly as the study built them -----------------
episodes = {}
for row in rows:
    if row["arm"] != "none":
        continue
    family = tuple(int(x) for x in row["family"].strip("()").split(",") if x != "")
    episode = FS.build_episode(row["seed"], family)
    if episode is None:
        raise SystemExit(f"episode {row['episode']} did not rebuild")
    episodes[row["episode"]] = {
        "episode": row["episode"], "seed": row["seed"], "family": row["family"],
        "obj": episode, "baseline_solved_it": row["baseline_solved_it"],
        "baseline_complete": row["baseline_complete"],
        "target_digest": episode.target_digest}
ids = sorted(episodes)
print(f"rebuilt {len(ids)} episodes", flush=True)

#  K0 fails, by measurement, on these
k0_failed = [e for e in ids if not episodes[e]["baseline_solved_it"]
             and episodes[e]["baseline_complete"]]
print(f"episodes where K0 completed and FAILED: {len(k0_failed)}", flush=True)


def open_schema_of(found_schema_json) -> tuple:
    """The constructed extension: the found program's structure, tables removed."""
    blocks = CV.blocks_from_ast(M.ast_from_json(found_schema_json))
    return CV.ast_from_blocks(blocks)


# --------------------------------------------------------------------------
# A. acquisition
# --------------------------------------------------------------------------
library = []
for row in rows:
    if not row["solved"] or row["episode"] not in k0_failed:
        continue
    schema = open_schema_of(row["found_schema_json"])
    library.append({
        "digest": CV.digest(schema), "schema": schema,
        "source_episode": row["episode"], "acquired_by_arm": row["arm"],
        "acquisition_units": row["total_units"],
        "source_family": episodes[row["episode"]]["family"],
        "structure_family": CV.family_text(CV.family(schema)),
    })
#  one entry per distinct structure, cheapest acquisition kept, but EVERY source
#  episode that produced it is remembered so leave-one-out can withhold them all
merged = {}
for entry in library:
    key = entry["digest"]
    if key not in merged:
        merged[key] = dict(entry, source_episodes={entry["source_episode"]},
                           acquired_by={entry["acquired_by_arm"]})
    else:
        merged[key]["source_episodes"].add(entry["source_episode"])
        merged[key]["acquired_by"].add(entry["acquired_by_arm"])
        merged[key]["acquisition_units"] = min(merged[key]["acquisition_units"],
                                               entry["acquisition_units"])
LIBRARY = sorted(merged.values(), key=lambda e: (e["acquisition_units"], e["digest"]))
print(f"library: {len(LIBRARY)} distinct constructed structures "
      f"from {len({e for x in LIBRARY for e in x['source_episodes']})} source episodes",
      flush=True)

# --------------------------------------------------------------------------
# B and C. transfer, with source-episode leave-one-out
# --------------------------------------------------------------------------

def try_library(target_id: int, entries) -> dict:
    """Fit each library entry against the target's demonstrations, in frozen
    order, stopping at the first exact fit. One unit per attempt."""
    episode = episodes[target_id]["obj"]
    used = 0
    for entry in entries:
        used += 1
        outcome = SF.fit_outcome(entry["schema"], episode.pairs, require_exact_replay=True)
        if outcome["status"] == "EXACT_DEMONSTRATION_FIT":
            correct = defined = 0
            for grid_in, grid_out in episode.heldout:
                rendered = M.evaluate(outcome["program"], np.asarray(grid_in), MI.descriptors)
                if rendered is None:
                    continue
                defined += 1
                correct += int(np.array_equal(rendered, np.asarray(grid_out)))
            return {"solved": True, "units": used, "entry": entry["digest"],
                    "entry_source_episodes": sorted(entry["source_episodes"]),
                    "entry_structure_family": entry["structure_family"],
                    "is_generator_schema": CV.digest(entry["schema"]) ==
                                           episodes[target_id]["target_digest"],
                    "heldout_defined": defined, "heldout_total": len(episode.heldout),
                    "heldout_correct": defined == len(episode.heldout)
                                       and correct == len(episode.heldout)}
    return {"solved": False, "units": used, "entry": None}


results = []
started = time.perf_counter()
for target in ids:
    withheld = [e for e in LIBRARY if target in e["source_episodes"]]
    usable = [e for e in LIBRARY if target not in e["source_episodes"]]
    attempt = try_library(target, usable)
    #  ablation: remove the entry that solved it, retry with the remainder
    ablation = None
    if attempt["solved"]:
        remainder = [e for e in usable if e["digest"] != attempt["entry"]]
        again = try_library(target, remainder)
        ablation = {"remainder_solves_it": again["solved"],
                    "remainder_units": again["units"],
                    "remainder_entry": again["entry"],
                    "benefit_attributable_to_this_entry": not again["solved"]}
    unlearned = next(r for r in rows if r["episode"] == target and r["arm"] == "none")
    results.append({
        "target_episode": target, "target_family": episodes[target]["family"],
        "k0_solved_it": episodes[target]["baseline_solved_it"],
        "k0_completed_and_failed": target in k0_failed,
        "library_entries_withheld": len(withheld),
        "library_entries_usable": len(usable),
        "library": attempt, "ablation": ablation,
        "unlearned_two_block_search": {
            "solved": unlearned["solved"], "total_units": unlearned["total_units"],
            "heldout_correct": unlearned["heldout_correct"]},
    })
    mark = "Y" if attempt["solved"] else "n"
    print(f"  ep{target:02d} {episodes[target]['family']:6} library={mark}/{attempt['units']:<3} "
          f"unlearned={'Y' if unlearned['solved'] else 'n'}/{unlearned['total_units']}", flush=True)

# --------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------
transfer = [r for r in results if r["k0_completed_and_failed"]]
solved = [r for r in transfer if r["library"]["solved"]]
heldout_ok = [r for r in solved if r["library"]["heldout_correct"]]
attributable = [r for r in solved if r["ablation"]["benefit_attributable_to_this_entry"]]
exact_ast = [r for r in solved if r["library"]["is_generator_schema"]]
unlearned_solved = [r for r in transfer if r["unlearned_two_block_search"]["solved"]]

acquisition_total = sum(e["acquisition_units"] for e in LIBRARY)
summary = {
    "claim_level": ("OPERATIONAL reuse of a constructed schema. NOT semantic expressivity "
                    "growth: a two-block composition is expressible in the evaluator "
                    "language, K0 merely does not enumerate it. NOT full-pipeline LOO."),
    "K0": "single-block meta-language, complete 200-hypothesis enumeration",
    "episodes": len(ids),
    "episodes_where_K0_completed_and_failed": len(transfer),
    "library_size": len(LIBRARY),
    "library_acquisition_units_total": acquisition_total,
    "library_acquisition_units_mean": round(acquisition_total / len(LIBRARY), 1) if LIBRARY else None,
    "transfer": {
        "targets": len(transfer),
        "solved_by_library": len(solved),
        "heldout_output_success": len(heldout_ok),
        "benefit_attributable_to_the_solving_entry": len(attributable),
        "entry_was_the_generator_schema": len(exact_ast),
        "median_library_units_when_solved": (
            statistics.median([r["library"]["units"] for r in solved]) if solved else None),
        "max_library_units": len(LIBRARY),
    },
    "unlearned_two_block_search_on_same_targets": {
        "solved": len(unlearned_solved),
        "mean_total_units_all_targets": round(
            sum(r["unlearned_two_block_search"]["total_units"] for r in transfer) / len(transfer), 1),
        "heldout_output_success": sum(1 for r in transfer
                                      if r["unlearned_two_block_search"]["heldout_correct"]),
    },
    "K0_alone_on_same_targets": {
        "solved": 0, "units_per_target": 200,
        "note": "K0 completed and failed on every one of these targets, by measurement"},
    "cost_note": ("library units are candidate fits against the target's demonstrations. "
                  "Acquisition cost is reported separately and is paid once, not per target. "
                  "A fit against a library entry and a fit during unlearned search are both "
                  "counted as one unit and are not established to cost the same wall time."),
}

by_arm_source = Counter(a for e in LIBRARY for a in e["acquired_by"])
summary["library_entries_by_acquiring_arm"] = dict(by_arm_source)

report = {"summary": summary,
          "library": [{k: v for k, v in e.items() if k != "schema"} |
                      {"source_episodes": sorted(e["source_episodes"]),
                       "acquired_by": sorted(e["acquired_by"]),
                       "canonical": CV.canonical(e["schema"])} for e in LIBRARY],
          "per_target": results,
          "seconds": round(time.perf_counter() - started, 1)}
text = json.dumps(report, indent=1, sort_keys=True, default=str)
(OUT / "results.json").write_text(text)
(OUT / "results_hash.txt").write_text(hashlib.sha256(text.encode()).hexdigest() + "\n")

print("\n=== ACQUISITION AND TRANSFER ===")
print(json.dumps(summary, indent=1))
print("\nsha256:", hashlib.sha256(text.encode()).hexdigest())
print("CYCLE_DONE")
