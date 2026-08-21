#!/usr/bin/env python
"""Build the frozen Experience/Promotion/Lockbox manifest (CORA Stage B).

Splits the 1000 ARC-AGI-2 training task ids into Experience=600, Promotion=200,
Lockbox=200, stratified BY STRUCTURAL FAMILY (never randomly across the pool).

Family label per task (deterministic, TRAIN pairs only -- hidden test outputs
are never read):
    meta | shape_rel | size_class | npairs_class | palette_class
where
    meta         = "cert:<origin_class>" for the currently-certified tasks
                   (union of outputs/unified_harness_v22/results.json and
                   outputs/v22_arbitration/results.json solved lists), else
                   "ns:<required_class>" from the near-solve compiler dataset
                   outputs/nearsolve_compiler/ns_dataset.jsonl, else the
                   fallback default "meta:none" (counted and listed).
    shape_rel    = same | grow | shrink | other | mixed  (per-pair input vs
                   output dims, aggregated over train pairs)
    size_class   = S (max train grid dim <=10) | M (<=20) | L (>20)
    npairs_class = n2 | n3 | n4 | n5+
    palette_class= p<=3 | p4-5 | p6+  (distinct colors over train inputs)

Assignment: tasks are grouped into strata = (family_label, certified?); strata
are processed in sorted order; within a stratum, task ids are sorted then
shuffled with a stratum-specific RNG derived from the fixed global seed via
sha256 (no Python hash randomization). Certified and uncertified tasks are
allocated against separate per-class targets (largest-remainder on 0.6/0.2/0.2
of 181 certified, remainder for uncertified), so the 181 certified tasks are
themselves spread proportionally across the three splits. Within each class a
D'Hondt highest-averages rule (assign to the non-full split maximizing
target/(assigned+1), ties broken experience > promotion > lockbox) keeps every
contiguous per-stratum run within ~1 task of exact 60/20/20 proportion while
hitting the global 600/200/200 exactly.

Determinism: fixed seed, fixed "created" date string, sorted iteration
everywhere, json sort_keys -- rerunning reproduces the manifest byte-
identically. The script only ever appends to logs/lockbox_manifest.log and
rewrites outputs/lockbox/manifest.json with identical bytes.

Usage:
    python scripts/build_lockbox_manifest.py            # write manifest + log
    python scripts/build_lockbox_manifest.py --out X    # write manifest to X
                                                        # (no log line; used
                                                        # for the rerun check)
"""

import argparse
import hashlib
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VERSION = "1.0.0"
CREATED = "2026-08-18"  # fixed by protocol; never read the wall clock
SEED = 20260818

CHALLENGES = os.path.join(ROOT, "data", "arc-agi_training_challenges.json")
NS_DATASET = os.path.join(ROOT, "outputs", "nearsolve_compiler", "ns_dataset.jsonl")
V22_RESULTS = os.path.join(ROOT, "outputs", "unified_harness_v22", "results.json")
V22_ARBITRATION = os.path.join(ROOT, "outputs", "v22_arbitration", "results.json")

OUT_MANIFEST = os.path.join(ROOT, "outputs", "lockbox", "manifest.json")
LOG_FILE = os.path.join(ROOT, "logs", "lockbox_manifest.log")

SPLITS = ("experience", "promotion", "lockbox")
SPLIT_TARGETS = {"experience": 600, "promotion": 200, "lockbox": 200}
PROPORTIONS = {"experience": 0.6, "promotion": 0.2, "lockbox": 0.2}
FALLBACK_META = "meta:none"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def structural_features(task):
    """Cheap structural features from TRAIN pairs only."""
    pairs = task["train"]
    rels = set()
    for p in pairs:
        ih, iw = len(p["input"]), len(p["input"][0])
        oh, ow = len(p["output"]), len(p["output"][0])
        if (ih, iw) == (oh, ow):
            rels.add("same")
        elif oh * ow > ih * iw:
            rels.add("grow")
        elif oh * ow < ih * iw:
            rels.add("shrink")
        else:
            rels.add("other")
    shape_rel = rels.pop() if len(rels) == 1 else "mixed"

    max_dim = max(
        max(len(p["input"]), len(p["input"][0]), len(p["output"]), len(p["output"][0]))
        for p in pairs
    )
    size_class = "S" if max_dim <= 10 else ("M" if max_dim <= 20 else "L")

    n = len(pairs)
    npairs_class = "n2" if n <= 2 else ("n3" if n == 3 else ("n4" if n == 4 else "n5+"))

    colors = set()
    for p in pairs:
        for row in p["input"]:
            colors.update(row)
    pc = len(colors)
    palette_class = "p<=3" if pc <= 3 else ("p4-5" if pc <= 5 else "p6+")

    return shape_rel, size_class, npairs_class, palette_class


def load_certified():
    """Union of v22 full-run solved + v22 arbitration solved (the sealed 181)."""
    cert = {}
    for path in (V22_RESULTS, V22_ARBITRATION):
        with open(path) as f:
            res = json.load(f)
        for rec in res["solved"]:
            cert[rec["task_id"]] = rec  # arbitration overrides are fine: same class of metadata
    return cert


def load_ns():
    ns = {}
    with open(NS_DATASET) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            ns[rec["task_id"]] = rec
    return ns


def stratum_rng(seed, family_label, certified):
    """RNG keyed by (seed, stratum) via sha256 -- independent of PYTHONHASHSEED."""
    key = "%d:%s:%d" % (seed, family_label, 1 if certified else 0)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def largest_remainder(total, proportions):
    """Integer allocation of `total` across SPLITS by largest remainder."""
    raw = {s: total * proportions[s] for s in SPLITS}
    alloc = {s: int(raw[s]) for s in SPLITS}
    short = total - sum(alloc.values())
    order = sorted(SPLITS, key=lambda s: (-(raw[s] - alloc[s]), SPLITS.index(s)))
    for s in order[:short]:
        alloc[s] += 1
    return alloc


def dhondt_assign(stream, targets):
    """Assign each task in `stream` (ordered) to a split by highest averages.

    Deterministic; fills `targets` exactly; any contiguous run in the stream
    lands within about one task of proportional.
    """
    assigned = {s: 0 for s in SPLITS}
    out = {}
    for task_id in stream:
        best, best_score = None, None
        for s in SPLITS:
            if assigned[s] >= targets[s]:
                continue
            score = targets[s] / float(assigned[s] + 1)
            if best is None or score > best_score:
                best, best_score = s, score
        if best is None:
            raise RuntimeError("targets exhausted before stream ended")
        assigned[best] += 1
        out[task_id] = best
    if assigned != targets:
        raise RuntimeError("assignment did not meet targets: %r vs %r" % (assigned, targets))
    return out


def build_manifest():
    challenges_sha = sha256_file(CHALLENGES)
    with open(CHALLENGES) as f:
        challenges = json.load(f)
    if len(challenges) != 1000:
        raise RuntimeError("expected 1000 training tasks, got %d" % len(challenges))

    cert = load_certified()
    ns = load_ns()

    fallback_tasks = []
    labels = {}
    for task_id in sorted(challenges):
        shape_rel, size_class, npairs_class, palette_class = structural_features(
            challenges[task_id]
        )
        if task_id in cert:
            meta = "cert:%s" % cert[task_id].get("origin_class", "unknown")
        elif task_id in ns:
            meta = "ns:%s" % (ns[task_id].get("required_class") or "unknown")
        else:
            meta = FALLBACK_META
            fallback_tasks.append(task_id)
        labels[task_id] = "|".join(
            (meta, shape_rel, size_class, npairs_class, palette_class)
        )

    certified_ids = set(cert)
    n_cert = len(certified_ids)

    # Separate per-class targets so certified tasks are themselves spread
    # proportionally (largest remainder on 0.6/0.2/0.2 of n_cert).
    cert_targets = largest_remainder(n_cert, PROPORTIONS)
    uncert_targets = {s: SPLIT_TARGETS[s] - cert_targets[s] for s in SPLITS}

    # Build the two ordered streams: strata sorted by (family_label), tasks
    # within a stratum sorted then shuffled with a stratum-keyed RNG.
    def make_stream(want_certified):
        stream = []
        strata = {}
        for task_id, label in labels.items():
            if (task_id in certified_ids) != want_certified:
                continue
            strata.setdefault(label, []).append(task_id)
        for label in sorted(strata):
            ids = sorted(strata[label])
            stratum_rng(SEED, label, want_certified).shuffle(ids)
            stream.extend(ids)
        return stream

    assignment = {}
    assignment.update(dhondt_assign(make_stream(True), cert_targets))
    assignment.update(dhondt_assign(make_stream(False), uncert_targets))

    if len(assignment) != 1000:
        raise RuntimeError("assigned %d tasks, expected 1000" % len(assignment))

    per_split_counts = {s: 0 for s in SPLITS}
    per_split_family_hist = {s: {} for s in SPLITS}
    per_split_cert = {s: 0 for s in SPLITS}
    tasks = []
    for task_id in sorted(assignment):
        split = assignment[task_id]
        label = labels[task_id]
        certified = task_id in certified_ids
        per_split_counts[split] += 1
        per_split_family_hist[split][label] = per_split_family_hist[split].get(label, 0) + 1
        if certified:
            per_split_cert[split] += 1
        tasks.append(
            {
                "task_id": task_id,
                "family_label": label,
                "certified": certified,
                "split": split,
            }
        )

    if per_split_counts != SPLIT_TARGETS:
        raise RuntimeError("split counts wrong: %r" % per_split_counts)
    if per_split_cert != cert_targets:
        raise RuntimeError("certified spread wrong: %r" % per_split_cert)

    manifest = {
        "version": VERSION,
        "created": CREATED,
        "seed": SEED,
        "challenges_file": os.path.relpath(CHALLENGES, ROOT),
        "challenges_sha256": challenges_sha,
        "n_tasks": len(tasks),
        "split_targets": dict(SPLIT_TARGETS),
        "per_split_counts": per_split_counts,
        "per_split_family_histograms": per_split_family_hist,
        "certified_total": n_cert,
        "certified_per_split": per_split_cert,
        "certified_sources": [
            os.path.relpath(V22_RESULTS, ROOT),
            os.path.relpath(V22_ARBITRATION, ROOT),
        ],
        "ns_source": os.path.relpath(NS_DATASET, ROOT),
        "family_label_spec": (
            "meta|shape_rel|size_class|npairs_class|palette_class; meta is "
            "cert:<origin_class> for certified tasks, ns:<required_class> from "
            "the near-solve compiler otherwise, fallback meta:none; structural "
            "features computed from TRAIN pairs only (hidden test outputs never "
            "read)"
        ),
        "fallback_default_count": len(fallback_tasks),
        "fallback_default_tasks": fallback_tasks,
        "tasks": tasks,
    }
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--out",
        default=None,
        help="alternate output path (skips log append; for rerun verification)",
    )
    args = ap.parse_args()

    manifest = build_manifest()
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    out_path = args.out or OUT_MANIFEST
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(payload)

    manifest_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print("manifest: %s" % out_path)
    print("manifest_sha256: %s" % manifest_sha)
    print(
        "splits: %s certified: %s fallbacks: %d"
        % (
            manifest["per_split_counts"],
            manifest["certified_per_split"],
            manifest["fallback_default_count"],
        )
    )

    if args.out is None:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        line = (
            "%s lockbox manifest v%s seed=%d tasks=%d "
            "splits=%d/%d/%d certified=%d/%d/%d fallbacks=%d "
            "manifest_sha256=%s LOCKBOX_MANIFEST_DONE\n"
            % (
                CREATED,
                VERSION,
                SEED,
                manifest["n_tasks"],
                manifest["per_split_counts"]["experience"],
                manifest["per_split_counts"]["promotion"],
                manifest["per_split_counts"]["lockbox"],
                manifest["certified_per_split"]["experience"],
                manifest["certified_per_split"]["promotion"],
                manifest["certified_per_split"]["lockbox"],
                manifest["fallback_default_count"],
                manifest_sha,
            )
        )
        with open(LOG_FILE, "a") as f:
            f.write(line)
        print("log appended: %s" % LOG_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
