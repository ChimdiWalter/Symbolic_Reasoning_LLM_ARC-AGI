"""Ablations for the abstraction-transfer experiment.

Section 7 of the directive: for a useful learned entry or concept, remove it,
rerun the SAME target policy, and record the change in BOTH demonstration
fitting and held-out correctness. Also compare the whole learned-library policy
against ordinary search, since redundant entries can share responsibility even
when no single one is necessary.

Reads the frozen libraries and rebuilds the same pools. Changes nothing.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from cora_tti import abstraction_transfer as AT                  # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402

OUT = ROOT / "outputs" / "tti" / "abstraction_transfer"
result = json.loads((OUT / "results.json").read_text())
frozen = json.loads((OUT / "frozen_libraries.json").read_text())
pinned = result["pinned_before_measurement"]
BUDGET = pinned["target_budget_units"]
SPACE = FS.proposal_space()

#  rebuild the transfer pool exactly as pinned
TRANSFER = []
for family_index, family in enumerate(FS.STUDY_FAMILIES):
    found, attempt = 0, 0
    while found < pinned["transfer_per_family"] and attempt < 6000:
        seed = pinned["transfer_namespace"] + family_index * 3_000_017 + attempt * 7919
        attempt += 1
        episode = FS.build_episode(seed, family)
        if episode is None:
            continue
        TRANSFER.append(episode)
        found += 1
assert len(TRANSFER) == len(
    {r["transfer_index"] for r in result["rows"]}), "transfer pool did not rebuild"

CONCRETE = [{"digest": e["digest"], "schema": M.ast_from_json(json.loads(e["canonical"])),
             "structure_family": e["structure_family"], "sources": e["sources"]}
            for e in frozen["concrete"]]
print(f"rebuilt {len(TRANSFER)} transfer episodes, {len(CONCRETE)} concrete entries", flush=True)

rows = {(r["arm"], r["transfer_index"]): r for r in result["rows"]}
BASE_ARM = "B_concrete_then_ordinary"

#  which entries actually did work: targets solved in the prior phase
used_entries = defaultdict(list)
for index in range(len(TRANSFER)):
    row = rows[(BASE_ARM, index)]
    if row["solved"] and row["phase"] == "prior":
        used_entries[row["source"]].append(index)
print(f"entries that solved at least one target in the prior phase: {len(used_entries)}", flush=True)

ablations = []
started = time.perf_counter()
for digest, targets in sorted(used_entries.items()):
    remainder = [e for e in CONCRETE if e["digest"] != digest]
    for index in targets:
        before = rows[(BASE_ARM, index)]
        after = AT.run_policy(BASE_ARM, TRANSFER[index], BUDGET, remainder, [], SPACE)
        ablations.append({
            "removed_entry": digest[:16], "target": index,
            "family": before["family"],
            "before": {"solved": before["solved"], "units": before["units"],
                       "heldout_correct": before.get("heldout_correct"),
                       "found_digest": str(before.get("found_digest"))[:16],
                       "phase": before["phase"]},
            "after": {"solved": after["solved"], "units": after["units"],
                      "heldout_correct": after.get("heldout_correct"),
                      "found_digest": str(after.get("found_digest"))[:16],
                      "phase": after["phase"]},
            "fit_lost": before["solved"] and not after["solved"],
            "heldout_lost": bool(before.get("heldout_correct")) and not bool(after.get("heldout_correct")),
            "units_delta": after["units"] - before["units"],
        })
        a = ablations[-1]
        print(f"  remove {digest[:12]} -> tgt{index:02d}: fit {a['before']['solved']}->{a['after']['solved']} "
              f"heldout {a['before']['heldout_correct']}->{a['after']['heldout_correct']} "
              f"units {a['before']['units']}->{a['after']['units']}", flush=True)

#  the R2 concept ablation: that rule produced exactly one concept, so removing
#  it reduces policy C to ordinary search, which arm A already measures
concept_note = {}
for rule, concepts in frozen["concepts"].items():
    arm = f"C_concepts_then_ordinary[{rule}]"
    concept_note[rule] = {
        "concepts": len(concepts),
        "ablation": ("removing the single concept reduces policy C to ordinary search, "
                     "which arm A_ordinary already measures"
                     if len(concepts) == 1 else "per-concept ablation required"),
        "policy_total_units": sum(rows[(arm, i)]["units"] for i in range(len(TRANSFER))),
        "ordinary_total_units": sum(rows[("A_ordinary", i)]["units"] for i in range(len(TRANSFER))),
        "policy_heldout": sum(1 for i in range(len(TRANSFER))
                              if rows[(arm, i)].get("heldout_correct")),
        "ordinary_heldout": sum(1 for i in range(len(TRANSFER))
                                if rows[("A_ordinary", i)].get("heldout_correct")),
    }

summary = {
    "entry_ablations": len(ablations),
    "fits_lost": sum(1 for a in ablations if a["fit_lost"]),
    "heldout_lost": sum(1 for a in ablations if a["heldout_lost"]),
    "fits_that_persist": sum(1 for a in ablations if not a["fit_lost"]),
    "median_units_increase": (sorted(a["units_delta"] for a in ablations)[len(ablations) // 2]
                              if ablations else None),
    "necessary_entries": sorted({a["removed_entry"] for a in ablations if a["fit_lost"]}),
    "entries_whose_removal_changed_heldout": sorted(
        {a["removed_entry"] for a in ablations if a["heldout_lost"]}),
    "library_level": {
        "note": ("redundant entries can share responsibility even when no single one is "
                 "necessary, so the whole-library comparison is reported alongside"),
        "B_total_units": sum(rows[(BASE_ARM, i)]["units"] for i in range(len(TRANSFER))),
        "A_total_units": sum(rows[("A_ordinary", i)]["units"] for i in range(len(TRANSFER))),
        "B_heldout": sum(1 for i in range(len(TRANSFER))
                         if rows[(BASE_ARM, i)].get("heldout_correct")),
        "A_heldout": sum(1 for i in range(len(TRANSFER))
                         if rows[("A_ordinary", i)].get("heldout_correct")),
    },
    "concept_rules": concept_note,
    "seconds": round(time.perf_counter() - started, 1),
}
report = {"summary": summary, "ablations": ablations}
text = json.dumps(report, indent=1, sort_keys=True, default=str)
(OUT / "ablations.json").write_text(text)
(OUT / "ablations_hash.txt").write_text(hashlib.sha256(text.encode()).hexdigest() + "\n")
print("\n=== ABLATION SUMMARY ===")
print(json.dumps(summary, indent=1))
print("\nsha256:", hashlib.sha256(text.encode()).hexdigest())
print("ABLATIONS_DONE")
