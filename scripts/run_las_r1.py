"""LAS-R1: replication of the frozen LAS-v1 library on 256 new targets.

Learns nothing. Loads the LAS-v1 libraries exactly as frozen, verifies every
hash, and evaluates them against 256 targets from a namespace no earlier study
used. Restart-safe: each (target, policy) row is appended durably as it
completes and a restart skips completed rows without changing ordering.

Refuses to run if the LAS-v1 frozen library, the LAS-R1 pre-outcome freeze, or
any pinned code hash differs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import abstraction_lattice as AL                   # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import failure_signal_study as FS                  # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

LAS_V1 = ROOT / "outputs" / "tti" / "las_v1"
OUT = ROOT / "outputs" / "tti" / "las_r1"
ROWS = OUT / "rows.jsonl"

parser = argparse.ArgumentParser()
parser.add_argument("--nulls", action="store_true", help="also run the 32 matched nulls")
parser.add_argument("--limit", type=int, default=0, help="stop after N targets (0 = all)")
args = parser.parse_args()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                             # noqa: BLE001
        return "UNKNOWN"


# --------------------------------------------------- verification -----------
frozen_text = (OUT / "frozen.json").read_text()
if sha(frozen_text) != (OUT / "frozen_hash.txt").read_text().split()[0]:
    raise SystemExit("LAS-R1 pre-outcome freeze hash mismatch")
FROZEN = json.loads(frozen_text)

las_text = (LAS_V1 / "frozen.json").read_text()
if sha(las_text) != FROZEN["las_v1_frozen_sha256"]:
    raise SystemExit("LAS-v1 frozen library hash differs from the pinned value")
LASV1 = json.loads(las_text)

live_code = {"abstraction_lattice": AL.code_hash(),
             "scoped_slot_fitting": hashlib.sha256(
                 (ROOT / "cora_tti" / "scoped_slot_fitting.py").read_bytes()).hexdigest(),
             "failure_signal_study": hashlib.sha256(
                 (ROOT / "cora_tti" / "failure_signal_study.py").read_bytes()).hexdigest()}
for name, pinned in FROZEN["code_hashes"].items():
    if live_code[name] != pinned:
        raise SystemExit(f"code hash mismatch for {name}: refusing to run")
TARGET_BUDGET = FROZEN["pinned"]["target_budget"]
print(f"verified: LAS-v1 {FROZEN['las_v1_frozen_sha256'][:16]} | "
      f"LAS-R1 freeze {sha(frozen_text)[:16]} | budget {TARGET_BUDGET}", flush=True)

# --------------------------------------------------- priors -----------------
def schema_of_record(record):
    return M.ast_from_json(json.loads(record["canonical"]))


def instantiations_of(record):
    """Every legal binding of a stored abstraction's enumerable slots, in the
    same deterministic order the lattice used."""
    schema = schema_of_record(record)
    slot_types = record["slot_types"]
    slots = sorted(slot_types, key=lambda s: int(s[1:]))
    domains = [tuple(M.slot_domain(slot_types[s])) for s in slots]
    import itertools
    for binding in itertools.product(*domains):
        yield M.instantiate(schema, dict(zip(slots, binding)))


def prior_from(records, label_key="name"):
    out = []
    for record in records:
        schemas = list(instantiations_of(record))
        out.append((record.get(label_key) or record.get("mirrors"),
                    [(CV.digest(s), s) for s in schemas]))
    return out


print("precomputing priors and the ordinary enumeration", flush=True)
CONCRETE_PRIOR = [(r["digest"][:16], [(r["digest"], schema_of_record(r))])
                  for r in LASV1["concrete"]]
R1_PRIOR = prior_from(LASV1["R1"])
R2_PRIOR = prior_from(LASV1["R2"])
LAS_PRIOR = prior_from(LASV1["LAS"])
NULL_PRIORS = [prior_from(n["entries"], label_key="mirrors") for n in FROZEN["null_controls"]]
SPACE = [(CV.digest(s), s) for s in (FS.schema_of(c) for c in FS.proposal_space())]
print(f"  concrete {sum(len(p[1]) for p in CONCRETE_PRIOR)} | "
      f"R1 {sum(len(p[1]) for p in R1_PRIOR)} | R2 {sum(len(p[1]) for p in R2_PRIOR)} | "
      f"LAS {sum(len(p[1]) for p in LAS_PRIOR)} | ordinary {len(SPACE)}", flush=True)

POLICIES = [("A_ordinary", []), ("B_concrete", CONCRETE_PRIOR), ("C_R1", R1_PRIOR),
            ("D_R2", R2_PRIOR), ("E_LAS", LAS_PRIOR)]
if args.nulls:
    POLICIES += [(f"NULL_{i:02d}", NULL_PRIORS[i]) for i in range(len(NULL_PRIORS))]


# --------------------------------------------------- policy -----------------
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


# --------------------------------------------------- run -------------------
done = set()
if ROWS.exists():
    for line in ROWS.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            done.add((row["target"], row["policy"]))
print(f"resuming with {len(done)} rows already recorded", flush=True)

execution = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "git_head_at_launch": git_head(),
             "dirty_tree_count": len(subprocess.run(
                 ["git", "-C", str(ROOT), "status", "--porcelain"],
                 capture_output=True, text=True).stdout.strip().splitlines()),
             "runtime_code_hash": sha(json.dumps(live_code, sort_keys=True)),
             "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
             "python": platform.python_version(), "numpy": np.__version__,
             "policies": [p for p, _ in POLICIES], "resumed_rows": len(done)}
with (OUT / "execution_records.jsonl").open("a") as handle:
    handle.write(json.dumps(execution, sort_keys=True) + "\n")
print(f"launch HEAD {execution['git_head_at_launch'][:12]} | "
      f"dirty {execution['dirty_tree_count']} | "
      f"runtime code {execution['runtime_code_hash'][:16]}", flush=True)

targets = FROZEN["targets"]
if args.limit:
    targets = targets[:args.limit]
started_all = time.perf_counter()
for spec in targets:
    pending = [(name, prior) for name, prior in POLICIES
               if (spec["index"], name) not in done]
    if not pending:
        continue
    episode = FS.build_episode(spec["seed"], tuple(spec["family_tuple"]))
    if episode is None or episode.target_digest != spec["target_digest"]:
        raise SystemExit(f"target {spec['index']} did not rebuild to its frozen identity")
    for name, prior in pending:
        result = run_policy(prior, episode, TARGET_BUDGET)
        row = {"target": spec["index"], "seed": spec["seed"], "family": spec["family"],
               "policy": name, **result}
        with ROWS.open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        done.add((spec["index"], name))
    primary = [r for r in (json.loads(l) for l in ROWS.read_text().splitlines() if l.strip())
               if r["target"] == spec["index"] and not r["policy"].startswith("NULL")]
    print(f"  tgt{spec['index']:03d} {spec['family']:6} "
          + " ".join(f"{r['policy'][0]}{'Y' if r.get('heldout_correct') else 'n'}/{r['units']}"
                     for r in sorted(primary, key=lambda r: r["policy"]))
          + f"  [{round(time.perf_counter() - started_all)}s]", flush=True)

print(f"\nrows recorded: {len(done)}")
print("LAS_R1_RUN_DONE")
