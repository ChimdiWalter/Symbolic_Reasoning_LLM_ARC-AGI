"""LAS-R1 group ablations, using the partitions frozen before any outcome.

Single-concept removal was too weak in LAS-v1 because the library is redundant.
The four partitions below were defined mechanically in the pre-outcome freeze:

    A  source-group        remove every concept from the top concept's group
    B  invariant-signature remove every concept sharing the top concept's
                           fixed-position signature
    C  family-origin       remove every concept originating from family (0,0)
    D  whole-LAS           remove the complete LAS prior

C and D both remove all eight concepts, because every LAS-v1 concept came from
family (0,0). Removing the whole prior reduces policy E to ordinary search, which
arm A_ordinary already measured on every target, so C and D are answered by a
row-by-row comparison and need no rerun. A and B are rerun.

Mechanics are IDENTICAL to the frozen runner: this file carries a verbatim copy
of its run_policy and asserts textual identity with scripts/run_las_r1.py, which
is not modified. Reruns cover ALL replication targets, not only the ones where
LAS differed, because that is computationally cheap here.

Reports, separately and never collapsed:
    fit lost, held-out correctness lost, cost increase,
    fallback solution changed, program identity changed.
"""
from __future__ import annotations

import hashlib
import inspect
import itertools
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

LAS_V1 = ROOT / "outputs" / "tti" / "las_v1"
OUT = ROOT / "outputs" / "tti" / "las_r1"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


FROZEN = json.loads((OUT / "frozen.json").read_text())
assert sha((OUT / "frozen.json").read_text()) == (OUT / "frozen_hash.txt").read_text().split()[0]
LASV1 = json.loads((LAS_V1 / "frozen.json").read_text())
assert sha((LAS_V1 / "frozen.json").read_text()) == FROZEN["las_v1_frozen_sha256"]
TARGET_BUDGET = FROZEN["pinned"]["target_budget"]
PARTITIONS = FROZEN["ablation_partitions"]


# ----------------------------------------------------------------------------
# verbatim mechanics from the frozen runner
# ----------------------------------------------------------------------------

def score_program(program, heldout) -> dict:
    correct = defined = 0
    for grid_in, grid_out in heldout:
        rendered = M.evaluate(program, np.asarray(grid_in), MI.descriptors)
        if rendered is None:
            continue
        defined += 1
        correct += int(np.array_equal(rendered, np.asarray(grid_out)))
    return {"heldout_defined": defined, "heldout_total": len(heldout),
            "heldout_correct": defined == len(heldout) and correct == len(heldout),
            "undefined": defined < len(heldout)}


def run_policy(prior, episode, budget: int) -> dict:
    started = time.perf_counter()
    attempted, used = set(), 0
    found = phase = source = None
    prior_started = time.perf_counter()

    def attempt(digest, schema):
        nonlocal used
        if digest in attempted:
            return None
        attempted.add(digest)
        used += 1
        outcome = SF.fit_outcome(schema, episode.pairs, require_exact_replay=True)
        return outcome if outcome["status"] == "EXACT_DEMONSTRATION_FIT" else None

    for label, items in prior:
        if found is not None or used >= budget:
            break
        for digest, schema in items:
            if used >= budget:
                break
            outcome = attempt(digest, schema)
            if outcome is not None:
                found, phase, source = (schema, outcome["program"]), "prior", label
                break
    prior_units, prior_seconds = used, time.perf_counter() - prior_started
    fallback_started = time.perf_counter()
    if found is None:
        for digest, schema in SPACE:
            if used >= budget:
                break
            outcome = attempt(digest, schema)
            if outcome is not None:
                found = (schema, outcome["program"])
                phase, source = "fallback", "ordinary"
                break
    fallback_seconds = time.perf_counter() - fallback_started
    result = {"solved": found is not None, "units": used, "prior_units": prior_units,
              "fallback_units": used - prior_units, "phase": phase, "source": source,
              "prior_seconds": round(prior_seconds, 3),
              "fallback_seconds": round(fallback_seconds, 3),
              "seconds": round(time.perf_counter() - started, 3)}
    if found is not None:
        schema, program = found
        result["found_digest"] = CV.digest(schema)
        result["exact_ast_recovered"] = result["found_digest"] == episode.target_digest
        result.update(score_program(program, episode.heldout))
        result["wrong_but_demo_consistent"] = not result["heldout_correct"]
    return result


def _source_of(fn) -> str:
    return re.sub(r"\s+", " ", inspect.getsource(fn)).strip()


runner_text = (ROOT / "scripts" / "run_las_r1.py").read_text()
for fn in (run_policy, score_program):
    start = runner_text.index(f"def {fn.__name__}(")
    end = runner_text.index("\n\n\n", start)
    frozen_body = re.sub(r"\s+", " ", runner_text[start:end]).strip()
    assert _source_of(fn) == frozen_body, f"{fn.__name__} differs from the frozen runner"
print("ablation mechanics verified textually identical to the frozen runner", flush=True)


# ----------------------------------------------------------------------------
# priors, exactly as the runner built them
# ----------------------------------------------------------------------------

def instantiations_of(record):
    schema = M.ast_from_json(json.loads(record["canonical"]))
    slot_types = record["slot_types"]
    slots = sorted(slot_types, key=lambda s: int(s[1:]))
    domains = [tuple(M.slot_domain(slot_types[s])) for s in slots]
    for binding in itertools.product(*domains):
        yield M.instantiate(schema, dict(zip(slots, binding)))


def prior_from(records):
    return [(r["name"], [(CV.digest(s), s) for s in instantiations_of(r)]) for r in records]


SPACE = [(CV.digest(s), s) for s in (FS.schema_of(c) for c in FS.proposal_space())]
FULL_LAS = prior_from(LASV1["LAS"])

# ----------------------------------------------------------------------------
# rows
# ----------------------------------------------------------------------------
rows = defaultdict(dict)
for line in (OUT / "rows.jsonl").read_text().splitlines():
    if line.strip():
        row = json.loads(line)
        rows[row["policy"]][row["target"]] = row
targets = FROZEN["targets"]
assert all(t["index"] in rows["E_LAS"] and t["index"] in rows["A_ordinary"] for t in targets), \
    "replication rows incomplete; run the main experiment first"


def outcome_delta(before: dict, after: dict) -> dict:
    return {"fit_lost": bool(before["solved"]) and not bool(after["solved"]),
            "heldout_correctness_lost": bool(before.get("heldout_correct"))
                                        and not bool(after.get("heldout_correct")),
            "heldout_correctness_gained": (not bool(before.get("heldout_correct")))
                                          and bool(after.get("heldout_correct")),
            "cost_increase": after["units"] - before["units"],
            "fallback_solution_changed": before.get("phase") != after.get("phase"),
            "program_identity_changed": before.get("found_digest") != after.get("found_digest")}


report = {"partitions": {}, "targets": len(targets)}
started_all = time.perf_counter()
for key, spec in PARTITIONS.items():
    remove = set(spec["remove"])
    kept = [(name, items) for name, items in FULL_LAS if name not in remove]
    entries = []
    if spec["equals_whole_prior"]:
        #  no rerun: whole-prior removal IS ordinary search, already measured
        for t in targets:
            before, after = rows["E_LAS"][t["index"]], rows["A_ordinary"][t["index"]]
            entries.append({"target": t["index"], "family": t["family"],
                            "rerun": False, **outcome_delta(before, after)})
    else:
        for t in targets:
            episode = FS.build_episode(t["seed"], tuple(t["family_tuple"]))
            assert episode is not None and episode.target_digest == t["target_digest"]
            before = rows["E_LAS"][t["index"]]
            after = run_policy(kept, episode, TARGET_BUDGET)
            entries.append({"target": t["index"], "family": t["family"], "rerun": True,
                            "after_units": after["units"],
                            "after_heldout": after.get("heldout_correct"),
                            **outcome_delta(before, after)})
    summary = {
        "description": spec["description"], "removes": sorted(remove),
        "removes_count": len(remove), "kept_count": len(kept),
        "equals_whole_prior": spec["equals_whole_prior"],
        "rerun_performed": not spec["equals_whole_prior"],
        "fit_lost": sum(e["fit_lost"] for e in entries),
        "heldout_correctness_lost": sum(e["heldout_correctness_lost"] for e in entries),
        "heldout_correctness_gained": sum(e["heldout_correctness_gained"] for e in entries),
        "net_heldout_change_on_removal": (sum(e["heldout_correctness_gained"] for e in entries)
                                          - sum(e["heldout_correctness_lost"] for e in entries)),
        "fallback_solution_changed": sum(e["fallback_solution_changed"] for e in entries),
        "program_identity_changed": sum(e["program_identity_changed"] for e in entries),
        "total_cost_increase": sum(e["cost_increase"] for e in entries),
        "median_cost_increase": sorted(e["cost_increase"] for e in entries)[len(entries) // 2],
        "targets_with_cost_increase": sum(1 for e in entries if e["cost_increase"] > 0),
        "targets_with_cost_decrease": sum(1 for e in entries if e["cost_increase"] < 0),
    }
    if key == "B_invariant_signature":
        summary["signature"] = spec["signature"]
    report["partitions"][key] = {"summary": summary, "entries": entries}
    print(f"  {key}: removes {len(remove)}/8 | fit_lost {summary['fit_lost']} | "
          f"heldout_lost {summary['heldout_lost'] if 'heldout_lost' in summary else summary['heldout_correctness_lost']} "
          f"| heldout_gained {summary['heldout_correctness_gained']} | "
          f"prog_changed {summary['program_identity_changed']} | "
          f"cost +{summary['total_cost_increase']}", flush=True)

report["seconds"] = round(time.perf_counter() - started_all, 1)
text = json.dumps(report, indent=1, sort_keys=True, default=str)
(OUT / "ablations.json").write_text(text)
(OUT / "ablations_hash.txt").write_text(sha(text) + "\n")
print("sha256:", sha(text))
print("LAS_R1_ABLATIONS_DONE")
