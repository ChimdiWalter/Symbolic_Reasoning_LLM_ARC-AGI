"""Round-10 panel/reduction family: induction + rendering.

Motivation (outputs/eval_framing_census.json): 26/84 uncovered eval tasks
and ~196 unsolved training tasks are shrink tasks whose small output is
COMPUTED from the input's panel structure — cellwise panel combination
(AND/OR/XOR-like with task colors) or panel selection ("pick the odd
one").  The object-preserving delta vocabulary cannot express these.

Design contract (same discipline as everything else in this engine):
  - candidate discovery is DETERMINISTIC and fold-convergent: split
    configs are enumerated in canonical order, tables/criteria are
    zero-conflict over ALL train pairs or rejected;
  - programs are JSON-serializable ReductionPrograms ranked in the same
    canonical pool as object programs;
  - the ONLY acceptance path remains LOO-by-reinduction: the whole
    reduction search re-runs per fold inside _induce_composed.

BG is fixed to color 0 (the ARC background convention); a panel cell "on"
means != 0.
"""
from __future__ import annotations

from typing import Optional

from geocat_arc.perception.grid import Grid

from .types import ReductionProgram

BG = 0
MAX_PANELS = 9


class ReductionError(Exception):
    pass


# ---------------------------------------------------------------------------
# Panel splitting
# ---------------------------------------------------------------------------

def _full_lines(cells, color):
    """Rows / cols entirely of `color` -> (row_idx_list, col_idx_list)."""
    h, w = len(cells), len(cells[0])
    rows = [r for r in range(h) if all(cells[r][c] == color
                                       for c in range(w))]
    cols = [c for c in range(w) if all(cells[r][c] == color
                                       for r in range(h))]
    return rows, cols


def _segments(n, lines):
    """Contiguous index ranges left after removing separator lines."""
    segs = []
    start = 0
    for i in sorted(lines):
        if i > start:
            segs.append((start, i))
        start = i + 1
    if start < n:
        segs.append((start, n))
    return segs


def split_panels(cells, spec) -> list[tuple[tuple[int, int], ...]]:
    """Apply a split spec to one grid -> list of panels (each a tuple of
    row tuples).  Raises ReductionError when the spec does not apply."""
    h, w = len(cells), len(cells[0])
    if spec["kind"] == "separator":
        rows, cols = _full_lines(cells, spec["color"])
        rsegs = _segments(h, rows) if rows else [(0, h)]
        csegs = _segments(w, cols) if cols else [(0, w)]
        if not rows and not cols:
            raise ReductionError("no separator lines")
    else:                                   # equal split
        pr, pc = spec["rows"], spec["cols"]
        if h % pr or w % pc:
            raise ReductionError("equal split does not divide grid")
        sh, sw = h // pr, w // pc
        rsegs = [(i * sh, (i + 1) * sh) for i in range(pr)]
        csegs = [(j * sw, (j + 1) * sw) for j in range(pc)]
    panels = []
    for (r0, r1) in rsegs:
        for (c0, c1) in csegs:
            panels.append(tuple(tuple(cells[r][c0:c1])
                                for r in range(r0, r1)))
    if not 2 <= len(panels) <= MAX_PANELS:
        raise ReductionError(f"panel count {len(panels)}")
    dims = {(len(p), len(p[0])) for p in panels}
    if len(dims) != 1:
        raise ReductionError("unequal panel dims")
    return panels


def candidate_splits(pairs) -> list[dict]:
    """Split specs valid in EVERY train pair with panel dims == output dims,
    in canonical order (separator colors ascending, then equal splits by
    (rows, cols)).  `pairs` are (input_cells, output_cells) lists."""
    out = []
    in_colors = set.intersection(*({c for row in gi for c in row}
                                   for gi, _ in pairs)) - {BG}
    for color in sorted(in_colors):
        spec = {"kind": "separator", "color": int(color)}
        if _spec_valid(spec, pairs):
            out.append(spec)
    hi, wi = len(pairs[0][0]), len(pairs[0][0][0])
    ho, wo = len(pairs[0][1]), len(pairs[0][1][0])
    for pr in (1, 2, 3, 4):
        for pc in (1, 2, 3, 4):
            if pr * pc < 2 or pr * pc > MAX_PANELS:
                continue
            spec = {"kind": "equal", "rows": pr, "cols": pc}
            if _spec_valid(spec, pairs):
                out.append(spec)
    return out


def _spec_valid(spec, pairs) -> bool:
    arity = None
    for gi, go in pairs:
        try:
            panels = split_panels(gi, spec)
        except ReductionError:
            return False
        if (len(panels[0]), len(panels[0][0])) != (len(go), len(go[0])):
            return False
        if arity is None:
            arity = len(panels)
        elif len(panels) != arity:
            return False
    return True


# ---------------------------------------------------------------------------
# Mode induction
# ---------------------------------------------------------------------------

def _build_table(panels_per_pair, outputs, key_fn, mode_tag):
    """Shared truth-table builder: key_fn(vals) -> hashable key per cell.
    Returns (table, mode_tag) or None on conflict."""
    table_lit = {}
    key_rows = {}
    for panels, go in zip(panels_per_pair, outputs):
        h, w = len(go), len(go[0])
        for r in range(h):
            for c in range(w):
                vals = tuple(p[r][c] for p in panels)
                key = str(key_fn(vals))
                tgt = go[r][c]
                key_rows.setdefault(key, []).append((vals, tgt))
                if table_lit.get(key, tgt) != tgt:
                    table_lit[key] = None
                else:
                    table_lit[key] = tgt
    table = {}
    for key, rows in key_rows.items():
        entry = None
        for i in range(len(rows[0][0])):
            if all(vals[i] == tgt for vals, tgt in rows):
                entry = f"@panel{i}"
                break
        if entry is None:
            lit = table_lit.get(key)
            if lit is None:
                return None
            entry = int(lit)
        table[key] = entry
    return table if table else None


def _induce_cellwise(spec, pairs) -> Optional[ReductionProgram]:
    """v1 truth table: keys = per-cell background flags (on/off)."""
    panels_per_pair = [split_panels(gi, spec) for gi, _ in pairs]
    outputs = [go for _, go in pairs]
    key_fn = lambda vals: tuple(v != BG for v in vals)
    table = _build_table(panels_per_pair, outputs, key_fn, "cellwise")
    if table is None:
        return None
    return ReductionProgram(split=dict(spec), mode="cellwise",
                            params={"table": table})


def _induce_cellwise_color(spec, pairs) -> Optional[ReductionProgram]:
    """v2: keys = the actual cell COLOR tuple — resolves tasks where
    different non-background colors require different combination rules
    (e.g. color 3 + color 5 -> color 7 but color 3 + color 3 -> color 3).
    More bound values than binary keying, but strictly more expressive."""
    panels_per_pair = [split_panels(gi, spec) for gi, _ in pairs]
    outputs = [go for _, go in pairs]
    key_fn = lambda vals: tuple(vals)
    table = _build_table(panels_per_pair, outputs, key_fn, "cellwise_color")
    if table is None:
        return None
    return ReductionProgram(split=dict(spec), mode="cellwise_color",
                            params={"table": table})


def _induce_overlay(spec, pairs) -> list[ReductionProgram]:
    """v2: generic overlay modes — first non-bg panel wins (painter's
    algorithm in panel order), or last non-bg wins, or majority color.
    These are structural; no bound values."""
    panels_per_pair = [split_panels(gi, spec) for gi, _ in pairs]
    outputs = [go for _, go in pairs]
    out = []
    for mode_name, combiner in [
        ("overlay_first", lambda vals: next((v for v in vals if v != BG), BG)),
        ("overlay_last", lambda vals: next((v for v in reversed(vals) if v != BG), BG)),
        ("overlay_max", lambda vals: max(vals)),
        ("overlay_min_nonbg",
         lambda vals: min((v for v in vals if v != BG), default=BG)),
    ]:
        ok = True
        for panels, go in zip(panels_per_pair, outputs):
            h, w = len(go), len(go[0])
            for r in range(h):
                for c in range(w):
                    vals = tuple(p[r][c] for p in panels)
                    if combiner(vals) != go[r][c]:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            out.append(ReductionProgram(split=dict(spec), mode=mode_name,
                                        params={}))
    return out


_CRITERIA = ("unique_pattern", "majority_pattern", "most_nonbg",
             "least_nonbg", "most_colors", "least_colors")


def _select(panels, criterion):
    def nonbg(p):
        return sum(1 for row in p for v in row if v != BG)

    def ncolors(p):
        return len({v for row in p for v in row if v != BG})

    if criterion in ("unique_pattern", "majority_pattern"):
        counts = {}
        for p in panels:
            counts[p] = counts.get(p, 0) + 1
        if criterion == "unique_pattern":
            uniq = [p for p in panels if counts[p] == 1]
            if len(uniq) != 1:
                raise ReductionError("no single unique panel")
            return uniq[0]
        best = max(counts.values())
        maj = [p for p in counts if counts[p] == best]
        if len(maj) != 1 or best < 2:
            raise ReductionError("no majority panel")
        return maj[0]
    keyf = nonbg if "nonbg" in criterion else ncolors
    scored = sorted(((keyf(p), i) for i, p in enumerate(panels)),
                    reverse=criterion.startswith("most"))
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        raise ReductionError("criterion tie")
    return panels[scored[0][1]]


def _induce_select(spec, pairs) -> list[ReductionProgram]:
    out = []
    for criterion in _CRITERIA:                 # fixed canonical order
        ok = True
        for gi, go in pairs:
            try:
                panels = split_panels(gi, spec)
                chosen = _select(panels, criterion)
            except ReductionError:
                ok = False
                break
            if [list(row) for row in chosen] != go:
                ok = False
                break
        if ok:
            out.append(ReductionProgram(split=dict(spec),
                                        mode="select_panel",
                                        params={"criterion": criterion}))
    return out


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def induce_reduction_candidates(train_pairs) -> list[ReductionProgram]:
    """All train-perfect reduction programs for this task, canonical order.
    `train_pairs` are (Grid, Grid) pairs.  Returns [] unless every pair
    STRICTLY shrinks (the regime the family exists for)."""
    pairs = []
    for gi, go in train_pairs:
        ci, co = gi.to_list(), go.to_list()
        if len(co) > len(ci) or len(co[0]) > len(ci[0]) or \
                (len(co), len(co[0])) == (len(ci), len(ci[0])):
            return []
        pairs.append((ci, co))
    out = []
    for spec in candidate_splits(pairs):
        prog = _induce_cellwise(spec, pairs)
        if prog is not None:
            out.append(prog)
        prog2 = _induce_cellwise_color(spec, pairs)
        if prog2 is not None and (prog is None or
                prog2.to_dict() != prog.to_dict()):
            out.append(prog2)
        out.extend(_induce_overlay(spec, pairs))
        out.extend(_induce_select(spec, pairs))
    return out


_OVERLAY_COMBINERS = {
    "overlay_first": lambda vals: next((v for v in vals if v != BG), BG),
    "overlay_last": lambda vals: next((v for v in reversed(vals) if v != BG), BG),
    "overlay_max": lambda vals: max(vals),
    "overlay_min_nonbg": lambda vals: min((v for v in vals if v != BG), default=BG),
}


def render_reduction(program: ReductionProgram, input_grid: Grid) -> Grid:
    """Execute a reduction program on one input grid."""
    cells = input_grid.to_list()
    panels = split_panels(cells, program.split)
    if program.mode == "select_panel":
        chosen = _select(panels, program.params["criterion"])
        return Grid.from_list([list(row) for row in chosen])
    if program.mode in _OVERLAY_COMBINERS:
        combiner = _OVERLAY_COMBINERS[program.mode]
        h, w = len(panels[0]), len(panels[0][0])
        out = [[BG] * w for _ in range(h)]
        for r in range(h):
            for c in range(w):
                out[r][c] = combiner(tuple(p[r][c] for p in panels))
        return Grid.from_list(out)
    if program.mode in ("cellwise", "cellwise_color"):
        table = program.params["table"]
        h, w = len(panels[0]), len(panels[0][0])
        out = [[BG] * w for _ in range(h)]
        for r in range(h):
            for c in range(w):
                vals = tuple(p[r][c] for p in panels)
                if program.mode == "cellwise_color":
                    key = str(tuple(vals))
                else:
                    key = str(tuple(v != BG for v in vals))
                if key not in table:
                    raise ReductionError(f"no table entry for {key}")
                entry = table[key]
                if isinstance(entry, str) and entry.startswith("@panel"):
                    out[r][c] = vals[int(entry[6:])]
                else:
                    out[r][c] = int(entry)
        return Grid.from_list(out)
    raise ReductionError(f"unknown mode {program.mode}")
