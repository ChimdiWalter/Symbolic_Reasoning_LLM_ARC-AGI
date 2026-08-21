"""ROUND 22 — TWO-OBJECT EMISSION MODES (ARC_RAY_EXT), generative.py side.

R22 added two falsification-verified renderer branches to _apply_generator
plus the induction plumbing that lets them win:

  line_periodic   (0a938d79) — the object emits its FULL row/col line
                  (axis = row if h >= w else col), repeated FORWARD-ONLY
                  at period 2*|separation to the nearest other object|
                  until the border; colour defaults to the source object,
                  overridable via rule["color"].
  path_two_anchor (992798f6) — canonical roles by pair colour (source =
                  HIGHER colour, independent of which object hosts the
                  rule): one diagonal step off the source, straight along
                  the dominant axis, then a 45-degree diagonal into the
                  target; endpoints excluded.

  Proposal block in _candidate_generators_for_object gated on
  all_objects with >= 2 objects AND _ray_ext_enabled(); exact-agreement
  admission only.

  _fusion_signature widened: n_out > n_in (EMISSION) qualifies only when
  the gate is on; n_out == n_in still rejects; n_out < n_in (the original
  fusion class) is unchanged.

These tests pin the exact rendered cells, the host-independence of the
canonical path, the gate discipline, the signature widening, and finish
with the two real census exemplars end-to-end (both < 1s each here).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from geocat_arc.object_reasoning.generative import (
    _apply_generator,
    _candidate_generators_for_object,
    _fusion_signature,
    induce_generative_candidates,
    render_generative,
)
from geocat_arc.object_reasoning.types import SegmentationVariant
from geocat_arc.perception.grid import Grid
from geocat_arc.perception.objects import ARCObject


@pytest.fixture
def ray_on(monkeypatch):
    monkeypatch.setenv("ARC_RAY_EXT", "1")
    # keep learned generators out of the proposal list so kind-membership
    # assertions below see exactly the built-in vocabulary
    monkeypatch.delenv("ARC_LEARNED_GENERATORS_DIR", raising=False)


@pytest.fixture
def ray_off(monkeypatch):
    monkeypatch.delenv("ARC_RAY_EXT", raising=False)
    monkeypatch.delenv("ARC_LEARNED_GENERATORS_DIR", raising=False)


def obj_of(oid, cells, color):
    """Construct an ARCObject from a cell set (bbox derived)."""
    cells = frozenset(cells)
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return ARCObject(id=oid, cells=cells, color=color,
                     bounding_box=(min(rs), min(cs), max(rs), max(cs)))


S1 = SegmentationVariant.S1_SAME_COLOR_4


# ---------------------------------------------------------------------------
# line_periodic renderer
# ---------------------------------------------------------------------------

def test_line_periodic_row_dominant_exact_cells():
    """9x5 grid (h >= w -> row axis), seeds at rows 1 and 3: sep=2,
    period=4, so the host at row 1 emits full rows 1 and 5 (forward only,
    row 9 is off-grid), its own cell excluded, in its own colour."""
    a = obj_of(0, [(1, 2)], 3)
    b = obj_of(1, [(3, 2)], 4)
    added = _apply_generator({"kind": "line_periodic"}, a, (9, 5),
                             all_objects=[a, b])
    expected = {(1, c): 3 for c in range(5) if c != 2}
    expected.update({(5, c): 3 for c in range(5)})
    assert added == expected


def test_line_periodic_is_forward_only_and_host_relative():
    """The row-3 host repeats at rows 3 and 7 — never backward to row -1,
    and in ITS colour (colour defaults to the SOURCE object)."""
    a = obj_of(0, [(1, 2)], 3)
    b = obj_of(1, [(3, 2)], 4)
    added = _apply_generator({"kind": "line_periodic"}, b, (9, 5),
                             all_objects=[a, b])
    expected = {(3, c): 4 for c in range(5) if c != 2}
    expected.update({(7, c): 4 for c in range(5)})
    assert added == expected
    assert not any(r < 3 for r, _ in added), "backward repeat emitted"


def test_line_periodic_col_dominant_exact_cells():
    """5x9 grid (h < w -> col axis), seeds at cols 1 and 3: period 4,
    full columns 1 and 5 from the col-1 host."""
    a = obj_of(0, [(2, 1)], 3)
    b = obj_of(1, [(2, 3)], 4)
    added = _apply_generator({"kind": "line_periodic"}, a, (5, 9),
                             all_objects=[a, b])
    expected = {(r, 1): 3 for r in range(5) if r != 2}
    expected.update({(r, 5): 3 for r in range(5)})
    assert added == expected


def test_line_periodic_square_grid_ties_to_row_axis():
    """The documented tie rule: axis = row IF h >= w, so a square grid is
    row-dominant."""
    a = obj_of(0, [(1, 2)], 3)
    b = obj_of(1, [(4, 2)], 3)
    added = _apply_generator({"kind": "line_periodic"}, a, (7, 7),
                             all_objects=[a, b])
    assert added, "square grid rendered nothing"
    assert {r for r, _ in added} == {1}, \
        "square grid did not use the row axis (sep=3 -> period 6 -> row 1 only)"


def test_line_periodic_color_override():
    a = obj_of(0, [(1, 2)], 3)
    b = obj_of(1, [(3, 2)], 4)
    added = _apply_generator({"kind": "line_periodic", "color": 7}, a, (9, 5),
                             all_objects=[a, b])
    assert added and set(added.values()) == {7}


def test_line_periodic_period_uses_nearest_other_object():
    """Three seeds at rows 1, 3, 8: the row-1 host pairs with row 3
    (sep 2), NOT row 8 — so lines land at rows 1 and 5, not 1 and 15."""
    a = obj_of(0, [(1, 2)], 3)
    b = obj_of(1, [(3, 2)], 4)
    c = obj_of(2, [(8, 2)], 5)
    added = _apply_generator({"kind": "line_periodic"}, a, (16, 5),
                             all_objects=[a, b, c])
    assert {r for r, _ in added} == {1, 5, 9, 13}


def test_line_periodic_undefined_without_a_second_object():
    a = obj_of(0, [(1, 2)], 3)
    assert _apply_generator({"kind": "line_periodic"}, a, (9, 5),
                            all_objects=[a]) == {}
    assert _apply_generator({"kind": "line_periodic"}, a, (9, 5),
                            all_objects=None) == {}


def test_line_periodic_undefined_at_zero_separation():
    """Both seeds on the same axis position -> sep 0 would loop forever;
    the renderer must decline instead."""
    a = obj_of(0, [(1, 1)], 3)
    b = obj_of(1, [(1, 4)], 4)   # same ROW on a row-dominant grid
    assert _apply_generator({"kind": "line_periodic"}, a, (9, 5),
                            all_objects=[a, b]) == {}


# ---------------------------------------------------------------------------
# path_two_anchor renderer
# ---------------------------------------------------------------------------

def _two_seeds():
    """Higher-colour seed at (1,1), lower at (6,4): vertical-dominant."""
    p = obj_of(0, [(1, 1)], 3)
    q = obj_of(1, [(6, 4)], 2)
    return p, q


def test_path_two_anchor_vertical_dominant_exact_cells():
    """dr=5, dc=3: one diagonal step to (2,2), straight down the dominant
    axis to (4,2), 45-degree diagonal toward the target; both endpoints
    excluded."""
    p, q = _two_seeds()
    added = _apply_generator({"kind": "path_two_anchor", "color": 5}, p,
                             (8, 8), all_objects=[p, q])
    assert added == {(2, 2): 5, (3, 2): 5, (4, 2): 5, (5, 3): 5}
    assert (1, 1) not in added and (6, 4) not in added, "endpoint painted"


def test_path_two_anchor_horizontal_dominant_exact_cells():
    """dr=2, dc=6: diagonal step to (3,2), straight ALONG COLUMNS to
    (3,6), then the final diagonal step lands ON the target and is
    excluded."""
    p = obj_of(0, [(2, 1)], 3)
    q = obj_of(1, [(4, 7)], 2)
    added = _apply_generator({"kind": "path_two_anchor", "color": 5}, p,
                             (8, 9), all_objects=[p, q])
    assert added == {(3, c): 5 for c in range(2, 7)}


def test_path_two_anchor_roles_are_canonical_not_host_bound():
    """THE R22 contract: roles come from pair.sort(key=-colour), computed
    from the scene — so the identical path renders no matter which object
    hosts the rule and no matter the all_objects ordering.  This is what
    lets a UNIFORM generator paint one path instead of two."""
    p, q = _two_seeds()
    renders = [
        _apply_generator({"kind": "path_two_anchor", "color": 5}, host,
                         (8, 8), all_objects=order)
        for host in (p, q)
        for order in ([p, q], [q, p])
    ]
    assert all(r == renders[0] for r in renders), \
        "path depends on the host object or the object-list order"
    assert renders[0], "canonical path rendered nothing"


def test_path_two_anchor_leaves_the_higher_color_seed():
    """Swap which POSITION carries the higher colour and the path must
    flip: the first diagonal step always leaves the higher-colour seed."""
    hi_top = _apply_generator(
        {"kind": "path_two_anchor", "color": 5},
        obj_of(0, [(1, 1)], 3), (8, 8),
        all_objects=[obj_of(0, [(1, 1)], 3), obj_of(1, [(6, 4)], 2)])
    hi_bot = _apply_generator(
        {"kind": "path_two_anchor", "color": 5},
        obj_of(0, [(1, 1)], 2), (8, 8),
        all_objects=[obj_of(0, [(1, 1)], 2), obj_of(1, [(6, 4)], 3)])
    # higher colour at (1,1): first step off the source is (2,2)
    assert (2, 2) in hi_top and (5, 3) in hi_top
    # higher colour at (6,4): the walk starts at (5,3) and runs UP col 3
    assert hi_bot == {(5, 3): 5, (4, 3): 5, (3, 3): 5, (2, 2): 5}
    assert hi_top != hi_bot


def test_path_two_anchor_default_color_is_host_color():
    """Without rule['color'] the renderer falls back to the HOST object's
    colour (rule.get('color', obj.color)) — the geometry stays canonical
    but the colour does not, which is why the inducer proposes explicit-
    colour variants as well."""
    p, q = _two_seeds()
    from_p = _apply_generator({"kind": "path_two_anchor"}, p, (8, 8),
                              all_objects=[p, q])
    from_q = _apply_generator({"kind": "path_two_anchor"}, q, (8, 8),
                              all_objects=[p, q])
    assert set(from_p) == set(from_q), "geometry must stay host-independent"
    assert set(from_p.values()) == {3}
    assert set(from_q.values()) == {2}


def test_path_two_anchor_undefined_without_a_second_object():
    p, _ = _two_seeds()
    assert _apply_generator({"kind": "path_two_anchor"}, p, (8, 8),
                            all_objects=[p]) == {}
    assert _apply_generator({"kind": "path_two_anchor"}, p, (8, 8),
                            all_objects=None) == {}


# ---------------------------------------------------------------------------
# Proposal gating in _candidate_generators_for_object
# ---------------------------------------------------------------------------

R22_KINDS = {"line_periodic", "path_two_anchor"}


def _line_periodic_scene():
    """9x5 scene where line_periodic (source colour) reproduces the target
    exactly — the R22 proposal should surface, and at the TOP (exact
    agreement over the most cells)."""
    a = obj_of(0, [(1, 2)], 3)
    b = obj_of(1, [(3, 2)], 4)
    grid = np.zeros((9, 5), dtype=int)
    grid[1, 2] = 3
    grid[3, 2] = 4
    target = grid.copy()
    for k in (1, 5):
        for c in range(5):
            if target[k, c] == 0:
                target[k, c] = 3
    return a, b, grid, target


def test_r22_kinds_proposed_when_gate_on(ray_on):
    a, b, grid, target = _line_periodic_scene()
    kinds = [r["kind"] for r in _candidate_generators_for_object(
        a, target, 0, (9, 5), grid_array=grid, all_objects=[a, b])]
    assert "line_periodic" in kinds
    assert kinds[0] == "line_periodic", \
        "the exact-match emission should outrank partial-agreement modes"


def test_no_r22_proposals_when_gate_off(ray_off):
    a, b, grid, target = _line_periodic_scene()
    kinds = {r["kind"] for r in _candidate_generators_for_object(
        a, target, 0, (9, 5), grid_array=grid, all_objects=[a, b])}
    assert not (kinds & R22_KINDS), f"gate off but proposed: {kinds & R22_KINDS}"


def test_no_r22_proposals_with_a_single_object(ray_on):
    """Gate on but only one scene object (or no scene at all): the block
    must not fire."""
    a, _, grid, target = _line_periodic_scene()
    for objs in ([a], None):
        kinds = {r["kind"] for r in _candidate_generators_for_object(
            a, target, 0, (9, 5), grid_array=grid, all_objects=objs)}
        assert not (kinds & R22_KINDS), \
            f"proposed with all_objects={objs}: {kinds & R22_KINDS}"


def test_r22_proposals_require_exact_agreement(ray_on):
    """One wrong cell on the emitted line and the mode may not be admitted
    in ANY colour variant — exact agreement is the admission rule."""
    a, b, grid, target = _line_periodic_scene()
    target = target.copy()
    target[5, 0] = 9                     # corrupt one line cell
    kinds = {r["kind"] for r in _candidate_generators_for_object(
        a, target, 0, (9, 5), grid_array=grid, all_objects=[a, b])}
    assert "line_periodic" not in kinds


# ---------------------------------------------------------------------------
# _fusion_signature: the EMISSION widening
# ---------------------------------------------------------------------------

def _grid(rows):
    return Grid.from_list(rows)


def _blank(h, w):
    return [[0] * w for _ in range(h)]


def _emission_pair():
    """n_in=1 -> n_out=2 under S1 (a second object appears)."""
    gi = _blank(5, 5)
    gi[1][1] = 3
    go = _blank(5, 5)
    go[1][1] = 3
    go[3][3] = 4
    return _grid(gi), _grid(go)


def _equal_count_pair():
    """n_in = n_out = 1 (the object merely moves)."""
    gi = _blank(5, 5)
    gi[1][1] = 3
    go = _blank(5, 5)
    go[2][2] = 3
    return _grid(gi), _grid(go)


def _fusion_pair():
    """The pre-R22 class: two dots fuse into one column, n_out < n_in."""
    gi = _blank(5, 5)
    gi[0][1] = 3
    gi[4][1] = 3
    go = _blank(5, 5)
    for r in range(5):
        go[r][1] = 3
    return _grid(gi), _grid(go)


def test_emission_signature_accepted_only_with_gate_on(ray_on):
    assert _fusion_signature([_emission_pair()], S1) is True


def test_emission_signature_rejected_with_gate_off(ray_off):
    assert _fusion_signature([_emission_pair()], S1) is False


def test_equal_object_count_rejected_regardless_of_gate(monkeypatch):
    monkeypatch.setenv("ARC_RAY_EXT", "1")
    assert _fusion_signature([_equal_count_pair()], S1) is False
    monkeypatch.delenv("ARC_RAY_EXT", raising=False)
    assert _fusion_signature([_equal_count_pair()], S1) is False


def test_fusion_class_unchanged_by_the_gate(monkeypatch):
    monkeypatch.delenv("ARC_RAY_EXT", raising=False)
    assert _fusion_signature([_fusion_pair()], S1) is True
    monkeypatch.setenv("ARC_RAY_EXT", "1")
    assert _fusion_signature([_fusion_pair()], S1) is True


def test_emission_must_hold_on_every_pair(ray_on):
    """One equal-count pair in the set sinks the signature even when the
    other pair emits."""
    assert _fusion_signature([_emission_pair(), _equal_count_pair()],
                             S1) is False


# ---------------------------------------------------------------------------
# End-to-end on the real census exemplars (both run < 1s each)
# ---------------------------------------------------------------------------

_ARC_JSON = (Path(__file__).resolve().parent.parent
             / "data" / "arc-agi_training_challenges.json")
_HAVE_DATA = _ARC_JSON.exists()


def _real_pairs(task_id):
    challenges = json.load(open(_ARC_JSON))
    task = challenges[task_id]
    return [(Grid.from_list(p["input"]), Grid.from_list(p["output"]))
            for p in task["train"]]


@pytest.mark.skipif(not _HAVE_DATA, reason="ARC training data not available")
@pytest.mark.parametrize("task_id,kind", [
    ("992798f6", "path_two_anchor"),
    ("0a938d79", "line_periodic"),
])
def test_real_task_certifies_with_its_r22_mode(monkeypatch, task_id, kind):
    monkeypatch.setenv("ARC_RAY_EXT", "1")
    monkeypatch.setenv("ARC_GENERATIVE", "1")
    monkeypatch.delenv("ARC_LEARNED_GENERATORS_DIR", raising=False)
    pairs = _real_pairs(task_id)
    candidates = induce_generative_candidates(pairs)
    assert candidates, f"{task_id}: no generative candidate found"

    winners = [prog for prog in candidates
               if any(rule.get("kind") == kind
                      for _, rule in prog.generators)]
    assert winners, (f"{task_id}: no candidate uses {kind}; got "
                     f"{[[r.get('kind') for _, r in p.generators] for p in candidates]}")

    prog = winners[0]
    for gi, go in pairs:
        rendered = render_generative(prog, gi)
        assert np.array_equal(rendered.to_numpy(), go.to_numpy()), \
            f"{task_id}: {kind} candidate is not train-perfect"


@pytest.mark.skipif(not _HAVE_DATA, reason="ARC training data not available")
def test_real_tasks_find_nothing_when_gate_off(monkeypatch):
    """Falsifiable counterpart: with ARC_RAY_EXT unset the emission
    signature rejects both exemplars, so the generative path proposes
    NOTHING for them — the seals genuinely ride on R22."""
    monkeypatch.delenv("ARC_RAY_EXT", raising=False)
    monkeypatch.setenv("ARC_GENERATIVE", "1")
    monkeypatch.delenv("ARC_LEARNED_GENERATORS_DIR", raising=False)
    for task_id in ("992798f6", "0a938d79"):
        assert induce_generative_candidates(_real_pairs(task_id)) == [], \
            f"{task_id} solved with the gate off"
