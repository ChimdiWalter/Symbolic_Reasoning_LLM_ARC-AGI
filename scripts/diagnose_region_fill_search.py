"""Fold-level REGION_FILL diagnosis (CORA expression round).

Decides, per Experience exemplar and per LOO fold, whether a FillRegion
program is even expressible before asking why the generic search misses it.
Region sources are the three the trace itemizes -- object-enclosed holes,
separator panels, background components -- and the colour key is drawn from
a generic feature set defined on the region and its enclosing entity.

Outcome vocabulary (one per task):
    DIRECT_GRAMMAR_LOO_PASS_SEARCH_MISS  region program holds on every fold
    FEATURE_MAP_NOT_FOLD_COVERABLE       holds on train, a fold cannot re-derive a key
    DIRECT_GRAMMAR_LOO_FAIL_LANGUAGE_GAP no feature makes the colour a function
    SEGMENTATION_OR_DOMAIN_MISMATCH      changed cells are not a union of regions

Analysis only: no engine state is touched and only Experience-split tasks
are opened.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning.growth import enclosed_hole_regions  # noqa: E402
from geocat_arc.object_reasoning.segmentation import (  # noqa: E402
    SEGMENTATION_TRIAL_ORDER,
    background_for,
    segment,
)
from geocat_arc.object_reasoning.types import to_grid_pairs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_region_diagnosis"


class _Holder:
    """Carries the single attribute the region helpers read."""

    def __init__(self, cells):
        self.cells = frozenset(cells)


# --------------------------------------------------------------- region sources
def regions_object_holes(arr, variant):
    from geocat_arc.object_reasoning.types import Grid
    grid = Grid(arr)
    bg = background_for(grid, variant)
    out = []
    for obj in segment(grid, variant, bg):
        host = _Holder(obj.cells)
        for reg in enclosed_hole_regions(host):
            out.append((reg, {"host_area": len(obj.cells),
                              "host_color": int(obj.color),
                              "host_hw": _hw(obj.cells)}))
    return out


def _components(mask, arr):
    """4-connected components of the cells in ``mask``."""
    seen, comps = set(), []
    for cell in sorted(mask):
        if cell in seen:
            continue
        comp, stack = {cell}, [cell]
        seen.add(cell)
        while stack:
            r, c = stack.pop()
            for nb in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if nb in mask and nb not in seen:
                    seen.add(nb)
                    comp.add(nb)
                    stack.append(nb)
        comps.append(frozenset(comp))
    return comps


def regions_background_components(arr, variant):
    """Background-coloured components, with their structural descriptors."""
    vals, counts = np.unique(arr, return_counts=True)
    bg = int(vals[int(np.argmax(counts))])
    h, w = arr.shape
    mask = {(r, c) for r in range(h) for c in range(w) if int(arr[r, c]) == bg}
    out = []
    for comp in _components(mask, arr):
        rows = [r for r, _ in comp]
        cols = [c for _, c in comp]
        touches = (min(rows) == 0 or min(cols) == 0
                   or max(rows) == h - 1 or max(cols) == w - 1)
        bh, bw = max(rows) - min(rows) + 1, max(cols) - min(cols) + 1
        out.append((comp, {"touches_border": touches,
                           "is_rect": len(comp) == bh * bw,
                           "region_hw": (bh, bw)}))
    return out


def regions_panels(arr, variant):
    """Cells between full separator rows/columns of one colour."""
    h, w = arr.shape
    sep_rows, sep_cols = [], []
    for r in range(h):
        if len(set(int(x) for x in arr[r, :])) == 1:
            sep_rows.append(r)
    for c in range(w):
        if len(set(int(x) for x in arr[:, c])) == 1:
            sep_cols.append(c)
    if not sep_rows and not sep_cols:
        return []
    row_bands, cur = [], []
    for r in range(h):
        if r in sep_rows:
            if cur:
                row_bands.append(cur)
            cur = []
        else:
            cur.append(r)
    if cur:
        row_bands.append(cur)
    col_bands, cur = [], []
    for c in range(w):
        if c in sep_cols:
            if cur:
                col_bands.append(cur)
            cur = []
        else:
            cur.append(c)
    if cur:
        col_bands.append(cur)
    out = []
    for i, rb in enumerate(row_bands):
        for j, cb in enumerate(col_bands):
            cells = frozenset((r, c) for r in rb for c in cb)
            if cells:
                out.append((cells, {"panel_index": (i, j),
                                    "panel_row": i, "panel_col": j,
                                    "region_hw": (len(rb), len(cb))}))
    return out


SOURCES = {
    "object_holes": regions_object_holes,
    "background_components": regions_background_components,
    "panels": regions_panels,
}


def _hw(cells):
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return (max(rows) - min(rows) + 1, max(cols) - min(cols) + 1)


# --------------------------------------------------------------- colour keys
def feature_keys(region, meta):
    """Generic, coordinate-free descriptors of one region."""
    rows = [r for r, _ in region]
    cols = [c for _, c in region]
    r0, c0 = min(rows), min(cols)
    keys = {
        "region_area": len(region),
        "region_hw": _hw(region),
        "region_shape": tuple(sorted((r - r0, c - c0) for r, c in region)),
    }
    for name, val in meta.items():
        keys[name] = val
    return keys


# --------------------------------------------------------------- the analysis
def analyse_task(task, variant, source_name):
    """Return per-feature verdicts for one (task, segmentation, source)."""
    build = SOURCES[source_name]
    gp = to_grid_pairs([(np.array(p["input"]), np.array(p["output"]))
                        for p in task["train"]])
    obs = defaultdict(dict)          # feature -> key -> colour
    seen_in = defaultdict(lambda: defaultdict(set))   # feature -> key -> pairs
    conflict = set()
    for pi, (gi, go) in enumerate(gp):
        ain, aout = gi.to_numpy(), go.to_numpy()
        if ain.shape != aout.shape:
            return {"outcome": "SEGMENTATION_OR_DOMAIN_MISMATCH",
                    "why": "output shape differs"}
        changed = {(r, c): int(aout[r, c])
                   for r in range(ain.shape[0]) for c in range(ain.shape[1])
                   if int(ain[r, c]) != int(aout[r, c])}
        if not changed:
            return {"outcome": "SEGMENTATION_OR_DOMAIN_MISMATCH",
                    "why": f"pair {pi} unchanged"}
        try:
            regions = build(ain, variant)
        except Exception as exc:                       # pragma: no cover
            return {"outcome": "SEGMENTATION_OR_DOMAIN_MISMATCH",
                    "why": f"region build failed: {exc}"}
        if not regions:
            return {"outcome": "SEGMENTATION_OR_DOMAIN_MISMATCH",
                    "why": f"no regions on pair {pi}"}
        covered = set()
        for region, meta in regions:
            got = {cell: changed[cell] for cell in region if cell in changed}
            if not got:
                continue                       # region left alone: a no-op key
            if len(got) != len(region) or len(set(got.values())) != 1:
                return {"outcome": "SEGMENTATION_OR_DOMAIN_MISMATCH",
                        "why": f"region partly/multi-coloured on pair {pi}"}
            colour = int(next(iter(got.values())))
            covered |= set(region)
            for feat, key in feature_keys(region, meta).items():
                if feat in conflict:
                    continue
                if obs[feat].get(key, colour) != colour:
                    conflict.add(feat)
                    continue
                obs[feat][key] = colour
                seen_in[feat][key].add(pi)
        if covered != set(changed):
            return {"outcome": "SEGMENTATION_OR_DOMAIN_MISMATCH",
                    "why": (f"changed cells outside regions on pair {pi} "
                            f"(+{len(set(changed) - covered)})")}
    usable = {f: t for f, t in obs.items() if f not in conflict and t}
    if not usable:
        return {"outcome": "DIRECT_GRAMMAR_LOO_FAIL_LANGUAGE_GAP",
                "why": "no feature makes the colour single-valued"}
    coverable = {f: t for f, t in usable.items()
                 if all(len(seen_in[f][k]) >= 2 for k in t)}
    if coverable:
        best = min(coverable, key=lambda f: (len(coverable[f]), f))
        return {"outcome": "DIRECT_GRAMMAR_LOO_PASS_SEARCH_MISS",
                "feature": best, "n_keys": len(coverable[best]),
                "n_pairs": len(gp)}
    best = min(usable, key=lambda f: (len(usable[f]), f))
    return {"outcome": "FEATURE_MAP_NOT_FOLD_COVERABLE",
            "feature": best, "n_keys": len(usable[best]),
            "key_pair_counts": sorted(len(seen_in[best][k])
                                      for k in usable[best]),
            "n_pairs": len(gp)}


RANK = {"DIRECT_GRAMMAR_LOO_PASS_SEARCH_MISS": 0,
        "FEATURE_MAP_NOT_FOLD_COVERABLE": 1,
        "DIRECT_GRAMMAR_LOO_FAIL_LANGUAGE_GAP": 2,
        "SEGMENTATION_OR_DOMAIN_MISMATCH": 3}


def main(task_ids):
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    manifest = json.loads((ROOT / "outputs" / "lockbox" / "manifest.json").read_text())
    tasks = manifest["tasks"]
    split = ({t["task_id"]: t["split"] for t in tasks} if isinstance(tasks, list)
             else {k: v["split"] for k, v in tasks.items()})
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for tid in task_ids:
        if split.get(tid) != "experience":
            results[tid] = {"outcome": "SKIPPED_NOT_EXPERIENCE"}
            continue
        best = None
        for source in SOURCES:
            for variant in SEGMENTATION_TRIAL_ORDER:
                verdict = analyse_task(challenges[tid], variant, source)
                verdict["source"] = source
                verdict["variant"] = str(variant).split(".")[-1]
                key = RANK[verdict["outcome"]]
                if best is None or key < RANK[best["outcome"]]:
                    best = verdict
                if key == 0:
                    break
            if best is not None and RANK[best["outcome"]] == 0:
                break
        results[tid] = best
        print(f"{tid}: {best['outcome']} "
              f"[{best.get('source')}/{best.get('variant')}] "
              f"{ {k: v for k, v in best.items()
                   if k not in ('outcome', 'source', 'variant')} }",
              flush=True)
    (OUT / "region_fill_diagnosis.json").write_text(
        json.dumps(results, indent=1, default=str))
    counts = defaultdict(int)
    for v in results.values():
        counts[v["outcome"]] += 1
    print("\nsummary:", dict(counts))
    return results


if __name__ == "__main__":
    ids = sys.argv[1:] or ["00dbd492", "272f95fa", "e9c9d9a1",
                           "7b6016b9", "83302e8f", "e73095fd"]
    main(ids)
