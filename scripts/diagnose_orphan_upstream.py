#!/usr/bin/env python3
"""ORPHAN-CLASS UPSTREAM CENSUS — segmentation/matching diagnostic.

For every task in the orphan battery (meta_m2_orphan_battery.json), run
the real engine induction path and record where it dies.  For tasks that
die at SEGMENTATION or MATCHING, enumerate ALL segmentation variants and
check whether ANY variant produces a coherent correspondence, recording
why the engine's chosen variant loses.

Outputs: outputs/orphan_upstream_census.json  (per-task + aggregates)

Budget: 60s soft per task, ~2.5h total cap.  Priority labels run first
(input_subshape, line_between, grid_motif), then all remaining tasks.
"""
import json
import os
import shutil
import signal
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, ".")
os.environ["ARC_EXTRACT_PART"] = "1"

from geocat_arc.perception.grid import Grid
from geocat_arc.object_reasoning.inducer import (
    InductionConfig,
    induce_program,
    enumerate_labeled_tables,
    register_builtin_features,
)
from geocat_arc.object_reasoning.segmentation import (
    evaluate_variant,
    SEGMENTERS,
    COHERENCE_PIXEL_THRESHOLD,
)
from geocat_arc.object_reasoning.correspondence import (
    match_pair,
    extract_deltas,
    WEIGHT_PROFILES,
)
from geocat_arc.object_reasoning.types import (
    DeltaType,
    FailureStage,
    GridPair,
    SegmentationResult,
    SegmentationVariant,
    SEGMENTATION_TRIAL_ORDER,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT = Path(".")
DATA_TRAIN = json.load(open(PROJECT / "data/arc/arc-agi_training_challenges.json"))
DATA_EVAL = json.load(open(PROJECT / "data/arc/arc-agi_evaluation_challenges.json"))
BATTERY = json.load(open(PROJECT / "outputs/meta_m2_orphan_battery.json"))
LIBRARY_SRC = PROJECT / "outputs/object_reasoning_promotion_v3/library.json"
VERBS_SRC = PROJECT / "outputs/learned_verbs/learned_verbs.json"
OUTPUT_PATH = PROJECT / "outputs/orphan_upstream_census.json"

BUDGET_PER_TASK = 60.0          # seconds
TOTAL_BUDGET = 2.5 * 3600       # 2.5 hours
ALL_VARIANTS = list(SEGMENTATION_TRIAL_ORDER)

# Priority labels (run these first)
PRIORITY_LABELS = {"input_subshape", "line_between", "grid_motif",
                   "scaled_input", "pair_union", "bbox_outline"}


def load_task(tid):
    """Load task JSON from train or eval set."""
    if tid in DATA_TRAIN:
        return DATA_TRAIN[tid]
    return DATA_EVAL[tid]


def make_pairs(task_json):
    """Create GridPair list from task JSON."""
    return [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
            for p in task_json["train"]]


def get_battery_labels(tid):
    """Return dict of label -> count for this task."""
    return BATTERY["per_task"].get(tid, {})


# ---------------------------------------------------------------------------
# Phase 1: run real induction and record failure stage
# ---------------------------------------------------------------------------

def run_induction(pairs, work_dir):
    """Run real engine induction and return InductionResult."""
    register_builtin_features()
    cfg = InductionConfig(budget_s=BUDGET_PER_TASK)

    # Copy library + learned_verbs into working dir (engine loads from dir)
    if LIBRARY_SRC.exists():
        shutil.copy2(LIBRARY_SRC, work_dir / "library.json")
    if VERBS_SRC.exists():
        (work_dir / "learned_verbs.json").parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(VERBS_SRC, work_dir / "learned_verbs.json")

    # Use the engine's induce_program directly
    result = induce_program(pairs, cfg)
    return result


# ---------------------------------------------------------------------------
# Phase 2: variant-level analysis for upstream-blocked tasks
# ---------------------------------------------------------------------------

def analyse_variants(pairs, tid):
    """For a task blocked at SEGMENTATION or MATCHING, evaluate ALL
    segmentation variants and check correspondence quality for each.
    Returns a dict with per-variant analysis."""
    register_builtin_features()
    variant_analysis = {}

    for variant in ALL_VARIANTS:
        vname = variant.value
        try:
            seg = evaluate_variant(variant, pairs)
        except Exception as e:
            variant_analysis[vname] = {"error": f"seg_eval: {e}"}
            continue

        rec = {
            "coherent": seg.coherent,
            "coherence": round(seg.coherence, 3),
            "pixel_coverage": round(seg.pixel_coverage, 3),
            "object_counts": seg.object_counts,
            "granularity_mismatch": seg.granularity_mismatch,
        }

        # Count total objects (complexity signal)
        total_objs = sum(len(objs) for objs in seg.input_objects) + \
                     sum(len(objs) for objs in seg.output_objects)
        rec["total_objects"] = total_objs

        # Try correspondence on each pair
        n_lossy = 0
        n_orphans = 0
        total_orphan_objects = 0
        n_object_preserving = 0
        corr_error = False

        for pi, (gi, go) in enumerate(pairs):
            if pi >= len(seg.input_objects) or pi >= len(seg.output_objects):
                corr_error = True
                break
            in_objs = seg.input_objects[pi]
            out_objs = seg.output_objects[pi]
            if not in_objs:
                corr_error = True
                break
            try:
                alts = match_pair(in_objs, out_objs, gi, go, pair_index=pi)
                if not alts:
                    corr_error = True
                    break
                best = alts[0]
                if not best.is_object_preserving:
                    n_lossy += 1
                if best.created_output_ids:
                    n_orphans += 1
                    total_orphan_objects += len(best.created_output_ids)
                else:
                    n_object_preserving += 1
            except Exception as e:
                corr_error = True
                break

        rec["corr_error"] = corr_error
        rec["n_lossy_pairs"] = n_lossy
        rec["n_orphan_pairs"] = n_orphans
        rec["total_orphan_objects"] = total_orphan_objects
        rec["n_object_preserving_pairs"] = n_object_preserving

        # Check if labeled table can be built (enumeration succeeds)
        can_build_table = False
        has_train_perfect_alt = False
        if not corr_error:
            try:
                for table, report in enumerate_labeled_tables(
                        seg, pairs, max_alternatives=2):
                    can_build_table = True
                    break
            except Exception:
                pass

        rec["can_build_table"] = can_build_table
        variant_analysis[vname] = rec

    return variant_analysis


def classify_variant_blocker(va):
    """Given variant analysis dict, classify why this variant fails upstream."""
    if va.get("error"):
        return "seg_error"
    if va.get("corr_error"):
        return "corr_error"
    if not va["coherent"]:
        if va["pixel_coverage"] < COHERENCE_PIXEL_THRESHOLD:
            return "low_coverage"
        else:
            return "count_inconsistent"
    if va["n_lossy_pairs"] > 0:
        return "lossy_correspondence"
    if va["n_orphan_pairs"] > 0:
        return "orphan_correspondence_ok"  # coherent but has orphans (normal for these tasks)
    return "fully_matched"  # should be solvable


def find_best_variant(variant_analysis):
    """Find the variant most likely to support the orphan-battery task.
    Prefers: coherent > high coverage > fewer orphans > fewer objects."""
    candidates = []
    for vname, va in variant_analysis.items():
        if va.get("error") or va.get("corr_error"):
            continue
        score = (
            int(va["coherent"]) * 1000,
            va["pixel_coverage"] * 100,
            -va.get("total_orphan_objects", 999),
            -va.get("total_objects", 999),
        )
        candidates.append((score, vname, va))

    if not candidates:
        return None, None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1], candidates[0][2]


# ---------------------------------------------------------------------------
# Main census loop
# ---------------------------------------------------------------------------

def main():
    started = time.monotonic()
    all_task_ids = list(BATTERY["per_task"].keys())

    # Sort: priority-labeled tasks first, then the rest
    def priority_key(tid):
        labels = get_battery_labels(tid)
        has_priority = any(l in PRIORITY_LABELS for l in labels)
        return (0 if has_priority else 1, tid)

    all_task_ids.sort(key=priority_key)

    # Filter to labeled tasks for budget management
    labeled_ids = [t for t in all_task_ids if get_battery_labels(t)]
    unlabeled_ids = [t for t in all_task_ids if not get_battery_labels(t)]
    ordered_ids = labeled_ids + unlabeled_ids

    print(f"ORPHAN UPSTREAM CENSUS: {len(ordered_ids)} tasks "
          f"({len(labeled_ids)} labeled, {len(unlabeled_ids)} unlabeled)")
    print(f"Budget: {BUDGET_PER_TASK}s/task, {TOTAL_BUDGET/3600:.1f}h total")
    print(f"Priority labels: {PRIORITY_LABELS}")
    sys.stdout.flush()

    per_task = {}
    stage_histogram = Counter()
    label_stage_histogram = defaultdict(Counter)  # label -> stage -> count
    fixable_count = 0
    true_gap_count = 0
    blocker_histogram = Counter()
    blocker_by_label = defaultdict(Counter)

    # Create a temporary working directory for engine
    work_dir = Path(tempfile.mkdtemp(prefix="orphan_census_"))

    milestone_count = 0

    for i, tid in enumerate(ordered_ids):
        elapsed = time.monotonic() - started
        if elapsed > TOTAL_BUDGET:
            print(f"\n[BUDGET] Total budget exhausted after {i} tasks "
                  f"({elapsed/3600:.2f}h)")
            break

        labels = get_battery_labels(tid)
        label_str = ",".join(f"{k}:{v}" for k, v in labels.items()) if labels else "unlabeled"

        try:
            task_json = load_task(tid)
        except KeyError:
            per_task[tid] = {"error": "task_not_found", "labels": labels}
            stage_histogram["error"] += 1
            continue

        pairs = make_pairs(task_json)
        task_start = time.monotonic()

        print(f"\n[{i+1}/{len(ordered_ids)}] {tid} ({label_str}) ...", end="", flush=True)

        # Phase 1: run real induction
        record = {"labels": labels, "n_pairs": len(pairs)}
        try:
            result = run_induction(pairs, work_dir)
            record["accepted"] = result.accepted
            record["train_fit_objects"] = round(result.train_fit_objects, 3)
            record["train_fit_pixels"] = round(result.train_fit_pixels, 3)
            record["induction_time_s"] = round(result.induction_time_s, 2)
            record["events"] = result.events[:10]  # cap for output size

            if result.accepted:
                stage = "SOLVED"
                record["failure_stage"] = None
                record["segmentation_variant"] = (
                    result.segmentation.variant.value
                    if result.segmentation else None)
            elif result.failure_stage is not None:
                stage = result.failure_stage.value
                record["failure_stage"] = stage
                record["segmentation_variant"] = (
                    result.segmentation.variant.value
                    if result.segmentation else None)
            else:
                stage = "unknown"
                record["failure_stage"] = stage

            print(f" stage={stage} fit={result.train_fit_objects:.2f}", end="")

        except Exception as e:
            stage = "crash"
            record["failure_stage"] = "crash"
            record["error"] = f"{type(e).__name__}: {str(e)[:100]}"
            print(f" CRASH: {record['error']}", end="")

        stage_histogram[stage] += 1
        for lbl in labels:
            label_stage_histogram[lbl][stage] += 1

        # Phase 2: variant analysis for upstream-blocked tasks
        if stage in ("segmentation", "matching", "crash"):
            try:
                va = analyse_variants(pairs, tid)
                record["variant_analysis"] = va

                # Find best variant and classify blocker
                best_vname, best_va = find_best_variant(va)
                record["best_possible_variant"] = best_vname

                if best_vname and best_va:
                    best_blocker = classify_variant_blocker(best_va)
                    record["best_variant_blocker"] = best_blocker

                    # Is this fixable? (a working variant EXISTS but isn't chosen)
                    chosen = record.get("segmentation_variant")
                    if best_va["coherent"] and best_va.get("can_build_table"):
                        record["fixable"] = True
                        fixable_count += 1
                        # Why wasn't it chosen?
                        if chosen and chosen != best_vname:
                            record["fix_reason"] = f"engine_chose_{chosen}_over_{best_vname}"
                        elif not chosen:
                            record["fix_reason"] = "no_variant_reached"
                        else:
                            record["fix_reason"] = "chosen_but_matching_died"
                        blocker_histogram[record["fix_reason"]] += 1
                        for lbl in labels:
                            blocker_by_label[lbl][record["fix_reason"]] += 1
                    else:
                        # Check more specifically WHY no variant works
                        all_blockers = {}
                        for vn, vd in va.items():
                            all_blockers[vn] = classify_variant_blocker(vd)
                        record["all_variant_blockers"] = all_blockers
                        record["fixable"] = False
                        true_gap_count += 1

                        # Classify the TRUE gap
                        blocker_types = Counter(all_blockers.values())
                        dominant = blocker_types.most_common(1)[0][0]
                        record["gap_type"] = dominant
                        blocker_histogram[f"true_gap:{dominant}"] += 1
                        for lbl in labels:
                            blocker_by_label[lbl][f"true_gap:{dominant}"] += 1
                else:
                    record["fixable"] = False
                    record["gap_type"] = "no_viable_variant"
                    true_gap_count += 1
                    blocker_histogram["true_gap:no_viable_variant"] += 1
                    for lbl in labels:
                        blocker_by_label[lbl]["true_gap:no_viable_variant"] += 1

                print(f" best={best_vname}"
                      f" fixable={record.get('fixable', '?')}", end="")

            except Exception as e:
                record["variant_analysis_error"] = f"{type(e).__name__}: {str(e)[:100]}"
                print(f" VA_ERR: {record['variant_analysis_error']}", end="")

        task_elapsed = time.monotonic() - task_start
        record["total_time_s"] = round(task_elapsed, 2)
        per_task[tid] = record
        print(f" [{task_elapsed:.1f}s]", flush=True)

        # Progress milestones: save intermediate results every 10 tasks
        milestone_count += 1
        if milestone_count % 10 == 0:
            _save_results(per_task, stage_histogram, label_stage_histogram,
                          fixable_count, true_gap_count, blocker_histogram,
                          blocker_by_label, i + 1, len(ordered_ids))
            print(f"  [SAVED milestone at {milestone_count} tasks]", flush=True)

    # Final save
    _save_results(per_task, stage_histogram, label_stage_histogram,
                  fixable_count, true_gap_count, blocker_histogram,
                  blocker_by_label, len(per_task), len(ordered_ids))

    # Cleanup
    shutil.rmtree(work_dir, ignore_errors=True)

    total_elapsed = time.monotonic() - started
    print(f"\n\n{'='*60}")
    print(f"ORPHAN UPSTREAM CENSUS COMPLETE")
    print(f"Tasks processed: {len(per_task)}/{len(ordered_ids)}")
    print(f"Total time: {total_elapsed/60:.1f}m")
    print(f"\nFAILURE STAGE HISTOGRAM:")
    for stage, count in stage_histogram.most_common():
        print(f"  {stage:20s}: {count}")
    print(f"\nFIXABLE vs TRUE GAP:")
    print(f"  Fixable (working variant exists but not chosen): {fixable_count}")
    print(f"  True gap (no variant produces needed structure): {true_gap_count}")
    print(f"\nBLOCKER HISTOGRAM:")
    for blocker, count in blocker_histogram.most_common():
        print(f"  {blocker:50s}: {count}")
    print(f"\nBLOCKERS BY LABEL:")
    for lbl in sorted(label_stage_histogram.keys()):
        print(f"  {lbl}:")
        for blocker, count in blocker_by_label.get(lbl, Counter()).most_common():
            print(f"    {blocker:48s}: {count}")

    # Rank top-3 engine changes
    _rank_fixes(per_task, blocker_histogram, label_stage_histogram)


def _save_results(per_task, stage_histogram, label_stage_histogram,
                  fixable_count, true_gap_count, blocker_histogram,
                  blocker_by_label, processed, total):
    """Save intermediate/final results."""
    # Compute top-3 fixes
    fix_ranking = _compute_fix_ranking(per_task, blocker_histogram)

    output = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tasks_processed": processed,
            "tasks_total": total,
        },
        "aggregate": {
            "stage_histogram": dict(stage_histogram.most_common()),
            "fixable_count": fixable_count,
            "true_gap_count": true_gap_count,
            "blocker_histogram": dict(blocker_histogram.most_common()),
            "label_stage_histogram": {
                lbl: dict(counts.most_common())
                for lbl, counts in label_stage_histogram.items()
            },
            "blocker_by_label": {
                lbl: dict(counts.most_common())
                for lbl, counts in blocker_by_label.items()
            },
            "fix_ranking": fix_ranking,
        },
        "per_task": per_task,
    }
    json.dump(output, open(OUTPUT_PATH, "w"), indent=1)


def _compute_fix_ranking(per_task, blocker_histogram):
    """Rank the top engine changes by number of tasks they would unblock."""
    fixes = []

    # Count tasks per fix category
    fix_categories = defaultdict(list)
    for tid, rec in per_task.items():
        if not rec.get("fixable"):
            continue
        reason = rec.get("fix_reason", "unknown")
        fix_categories[reason].append(tid)

    # Also count tasks where a specific variant would help
    variant_help = defaultdict(list)
    for tid, rec in per_task.items():
        stage = rec.get("failure_stage")
        if stage not in ("segmentation", "matching", "crash"):
            continue
        best = rec.get("best_possible_variant")
        chosen = rec.get("segmentation_variant")
        if best and best != chosen:
            variant_help[f"variant_{best}"].append(tid)

    # Count coherence-gate failures (fixable via relaxing coherence)
    coherence_blocked = []
    for tid, rec in per_task.items():
        va = rec.get("variant_analysis", {})
        for vname, vd in va.items():
            if isinstance(vd, dict) and not vd.get("error") \
                    and not vd.get("corr_error") \
                    and not vd.get("coherent") \
                    and vd.get("pixel_coverage", 0) > 0.6:
                coherence_blocked.append(tid)
                break

    # Count trial-order misses (coherent variant exists but tried after cap)
    trial_order_blocked = []
    for tid, rec in per_task.items():
        va = rec.get("variant_analysis", {})
        best = rec.get("best_possible_variant")
        if not best:
            continue
        best_va = va.get(best, {})
        if isinstance(best_va, dict) and best_va.get("coherent"):
            # Check if it's beyond MAX_SEG_VARIANTS_TRIED (4)
            variant_order = [v.value for v in ALL_VARIANTS]
            coherent_before = []
            for vn in variant_order:
                vd = va.get(vn, {})
                if isinstance(vd, dict) and vd.get("coherent"):
                    coherent_before.append(vn)
                if vn == best:
                    break
            if len(coherent_before) > 4:  # MAX_SEG_VARIANTS_TRIED
                trial_order_blocked.append(tid)

    # Count count-inconsistency blocks
    count_inconsistent = []
    for tid, rec in per_task.items():
        va = rec.get("variant_analysis", {})
        all_count_incon = True
        any_high_cov = False
        for vname, vd in va.items():
            if isinstance(vd, dict) and not vd.get("error"):
                blocker = classify_variant_blocker(vd)
                if blocker == "count_inconsistent":
                    if vd.get("pixel_coverage", 0) > 0.7:
                        any_high_cov = True
                elif blocker not in ("seg_error", "corr_error", "low_coverage"):
                    all_count_incon = False
        if all_count_incon and any_high_cov:
            count_inconsistent.append(tid)

    # Build ranked fixes
    fix_ideas = [
        {
            "rank": 1,
            "change": "Relax coherence gate or add orphan-aware count-relation "
                      "(n_out = n_in + k allows new objects)",
            "mechanism": "The count-consistency check in evaluate_variant rejects "
                         "variants where orphan creations make n_out != n_in+k "
                         "and the copy/grow relaxation doesn't apply. Relaxing "
                         "this for CREATE-content tasks would let those variants "
                         "pass the coherence gate.",
            "tasks_unblocked": len(set(coherence_blocked + count_inconsistent)),
            "task_ids": sorted(set(coherence_blocked + count_inconsistent))[:20],
        },
        {
            "rank": 2,
            "change": "Expand MAX_SEG_VARIANTS_TRIED or reorder trial order "
                      "for orphan-heavy tasks",
            "mechanism": "The engine tries at most 4 coherent variants "
                         "(MAX_SEG_VARIANTS_TRIED=4). When the needed variant "
                         "(often S3/S4/S7) is 5th+ in coherence order, it's "
                         "never tried. Raising the cap or deprioritizing S1 "
                         "(which is rarely right for multi-object creation "
                         "tasks) would unblock these.",
            "tasks_unblocked": len(trial_order_blocked),
            "task_ids": sorted(trial_order_blocked)[:20],
        },
        {
            "rank": 3,
            "change": "Add orphan-aware correspondence profiles "
                      "(weight_profiles that down-weight unmatched output count)",
            "mechanism": "match_pair's greedy matching under all WEIGHT_PROFILES "
                         "produces lossy correspondences when orphan objects "
                         "fragment the matching. A profile that tolerates "
                         "unmatched outputs (marking them as COPY/CREATE "
                         "candidates rather than penalizing) would preserve "
                         "object-preserving status.",
            "tasks_unblocked": len([t for t, r in per_task.items()
                                    if r.get("fixable") and
                                    "matching_died" in r.get("fix_reason", "")]),
            "task_ids": sorted([t for t, r in per_task.items()
                                if r.get("fixable") and
                                "matching_died" in r.get("fix_reason", "")])[:20],
        },
    ]

    # Re-rank by tasks_unblocked
    fix_ideas.sort(key=lambda f: -f["tasks_unblocked"])
    for i, f in enumerate(fix_ideas):
        f["rank"] = i + 1

    return fix_ideas


def _rank_fixes(per_task, blocker_histogram, label_stage_histogram):
    """Print the top-3 ranked fixes."""
    fix_ranking = _compute_fix_ranking(per_task, blocker_histogram)
    print(f"\n{'='*60}")
    print("TOP-3 RANKED ENGINE CHANGES:")
    for f in fix_ranking[:3]:
        print(f"\n  #{f['rank']}: {f['change']}")
        print(f"  Tasks unblocked: {f['tasks_unblocked']}")
        print(f"  Mechanism: {f['mechanism'][:120]}...")
        if f["task_ids"]:
            print(f"  Example tasks: {', '.join(f['task_ids'][:5])}")


if __name__ == "__main__":
    main()
