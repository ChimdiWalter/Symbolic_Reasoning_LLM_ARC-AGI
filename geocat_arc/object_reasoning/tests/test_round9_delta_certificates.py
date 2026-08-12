"""Round-9 lever 2: delta-level LOO certificates for verb registration.

The task-level registration gate starves correct verbs on multi-blocker
tasks (the sealed M3 honest negative).  The delta-level certificate applies
LOO-by-reinduction to the verb's own delta: placement laws are re-fit from
N-1 instance pairs and must exactly predict the held-out orphan cells.
These tests pin the law catalog and the fold logic on synthetic instances.
"""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "m3b", "scripts/meta_m3_delta_certificates.py")
# import module without running main()
m3b = importlib.util.module_from_spec(spec)
sys.modules["m3b"] = m3b
spec.loader.exec_module(m3b)

MIRROR_H = [("mirror_h", None)]


def _inst(src, orphan, grid_shape=(10, 10)):
    return {"src": frozenset(src), "orphan": frozenset(orphan),
            "grid_shape": grid_shape}


def _mirror_h(cells):
    """mirror_h combinator semantics on a normalized shape (flip rows)."""
    h = max(r for r, _ in cells)
    return frozenset((h - r, c) for (r, c) in cells)


def test_const_offset_law_certifies_mirrored_copy_at_fixed_offset():
    """Three pairs: an L-shape at varying positions, its mirrored copy
    always 4 rows below the source origin.  Every fold's re-fit law must
    predict the held-out orphan exactly."""
    shape = [(0, 0), (1, 0), (2, 0), (2, 1)]
    insts = []
    for (r0, c0) in ((1, 1), (2, 3), (0, 5)):
        src = [(r + r0, c + c0) for r, c in shape]
        mirrored = _mirror_h(frozenset(shape))
        orphan = [(r + r0 + 4, c + c0) for r, c in mirrored]
        insts.append(_inst(src, orphan))
    passed, folds, laws = m3b.delta_loo(insts, MIRROR_H)
    assert (passed, folds) == (3, 3)
    assert "const_offset" in laws


def test_grid_mirror_law_certifies_reflection_across_grid_axis():
    """Sources at varying positions, orphan = flip across the grid's
    horizontal center — const_offset cannot fit (offset varies), the
    grid_mirror_h law must."""
    shape = [(0, 0), (1, 0), (1, 1)]
    insts = []
    for (r0, c0) in ((0, 1), (1, 4), (2, 6)):
        src = [(r + r0, c + c0) for r, c in shape]
        H = 9
        orphan = [(H - 1 - r, c) for (r, c) in src]
        insts.append(_inst(src, orphan, grid_shape=(H, 12)))
    passed, folds, laws = m3b.delta_loo(insts, MIRROR_H)
    assert (passed, folds) == (3, 3)
    assert laws == ["grid_mirror_h"]


def test_inconsistent_placement_fails_every_fold():
    """Same shapes but orphan offsets differ per pair AND do not follow any
    catalog law: no fold may pass — the certificate must refuse."""
    shape = [(0, 0), (1, 0), (2, 0), (2, 1)]
    insts = []
    for (r0, c0), (dr, dc) in (((1, 1), (4, 0)), ((2, 3), (5, 2)),
                               ((0, 5), (3, 3))):
        src = [(r + r0, c + c0) for r, c in shape]
        mirrored = _mirror_h(frozenset(shape))
        orphan = [(r + r0 + dr, c + c0 + dc) for r, c in mirrored]
        insts.append(_inst(src, orphan, grid_shape=(20, 20)))
    passed, folds, _ = m3b.delta_loo(insts, MIRROR_H)
    assert folds == 3 and passed == 0


def test_single_instance_pair_cannot_certify():
    insts = [_inst([(0, 0), (1, 0)], [(5, 0), (6, 0)])]
    passed, folds, _ = m3b.delta_loo(insts, MIRROR_H)
    assert folds == 0 and passed == 0


def test_touch_law_certifies_abutting_mirror():
    """Mirrored copy directly below the source (offset = source height, so
    it varies with source size — const_offset cannot fit across sizes)."""
    insts = []
    for k, (r0, c0) in zip((2, 3, 4), ((1, 1), (0, 4), (2, 7))):
        shape = [(i, 0) for i in range(k)] + [(k - 1, 1)]
        src = [(r + r0, c + c0) for r, c in shape]
        mirrored = _mirror_h(frozenset(shape))
        orphan = [(r + r0 + k, c + c0) for r, c in mirrored]
        insts.append(_inst(src, orphan, grid_shape=(20, 20)))
    passed, folds, laws = m3b.delta_loo(insts, MIRROR_H)
    assert (passed, folds) == (3, 3)
    assert "touch" in laws


def test_reflect_line_law_certifies_marker_relational_placement():
    """The dc2e9a9d/7ed72f31 pattern: orphan = source reflected across an
    ADJACENT LINE OBJECT; the marker's side varies per pair, so no offset,
    grid-mirror, or touch law can fit — only the relational law may."""
    shape = [(0, 0), (1, 0), (2, 0), (2, 1)]  # height 3

    def inst_with_line(r0, c0, side):
        src = [(r + r0, c + c0) for r, c in shape]
        if side == "below":
            line_r = r0 + 3                       # max_r + 1
        else:
            line_r = r0 - 1                       # min_r - 1
        orphan = [(2 * line_r - r, c) for (r, c) in src]
        return {"src": frozenset(src), "orphan": frozenset(orphan),
                "grid_shape": (30, 30),
                "lines": (("h", line_r), ("v", 25))}

    insts = [inst_with_line(3, 2, "below"),
             inst_with_line(10, 5, "above"),      # side flips
             inst_with_line(5, 9, "below")]
    passed, folds, laws = m3b.delta_loo(insts, MIRROR_H)
    assert (passed, folds) == (3, 3)
    assert laws == ["reflect_line"]


def test_bounce_gap_law_certifies_edge_relational_mirror():
    """The dc2e9a9d pattern: mirrored copy with constant gap 1, on the side
    AWAY from the nearest grid edge — side flips per pair, so no absolute
    law can fit; bounce_gap must."""
    shape = [(0, 0), (1, 0), (2, 0), (2, 1)]  # height 3

    def inst_at(r0, c0, H):
        src = [(r + r0, c + c0) for r, c in shape]
        r1 = r0 + 2
        below = (H - 1 - r1) >= r0
        axis = (r1 + 1) if below else (r0 - 1)
        orphan = [(2 * axis - r, c) for (r, c) in src]
        return {"src": frozenset(src), "orphan": frozenset(orphan),
                "grid_shape": (H, 30), "lines": ()}

    insts = [inst_at(2, 3, 20),    # near top -> copy below
             inst_at(15, 6, 20),   # near bottom -> copy above
             inst_at(1, 9, 18)]    # near top -> copy below
    passed, folds, laws = m3b.delta_loo(insts, MIRROR_H)
    assert (passed, folds) == (3, 3)
    assert laws == ["bounce_gap"]
