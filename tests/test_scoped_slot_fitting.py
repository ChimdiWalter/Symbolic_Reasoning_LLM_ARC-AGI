"""Occurrence-scoped fitter: positive and negative controls (v2 sections 24-25).

Hand-built controls validate mechanisms. They are disposable fixtures and are
never pilot admissions or model data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402


def table(keys, colour):
    return tuple(sorted(((k, colour) for k in keys), key=lambda kv: repr(kv[0])))


AREAS = (1, 2, 3, 4)
HW = ((1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 3), (9, 9), (10, 10),
      (9, 10), (10, 9), (11, 11), (9, 11), (11, 9), (10, 11), (11, 10))


def render(blocks, tables, seed_base, n=10, keep=5):
    schema = CV.ast_from_blocks(blocks)
    concrete = schema
    for index, tbl in enumerate(tables):
        concrete = M.instantiate(concrete, {f"?{index}": tbl})
    pairs = []
    for step in range(n):
        grid = CD.generate_grid(seed_base + step)
        out = M.evaluate(concrete, grid, MI.descriptors)
        if out is not None and not np.array_equal(out, grid):
            pairs.append((grid, out))
    return schema, pairs[:keep]


TWO_BLOCK = ([("colour_components", ("rectangular",), "area"),
              ("background_components", (), "hw")],
             [table(AREAS, 5), table(HW, 8)], 81000)


# --------------------------------------------------------------------------
# positive controls
# --------------------------------------------------------------------------

def test_positive_two_block_independent_maps():
    schema, pairs = render(*TWO_BLOCK)
    assert len(pairs) >= 3
    fitted, evidence = SF.fit_induced_occurrences(schema, pairs)
    assert fitted is not None, evidence.get("failure")
    assert evidence["exact_replay"] is True
    assert set(evidence["slots"]) == {"?0", "?1"}
    assert evidence["slots"]["?0"]["block_index"] == 0
    assert evidence["slots"]["?1"]["block_index"] == 1


def test_positive_multi_block_contains_zero_select_block():
    schema, pairs = render(*TWO_BLOCK)
    blocks = CV.blocks_from_ast(schema)
    assert blocks[1][1] == (), "second block must have zero Select stages"
    fitted, evidence = SF.fit_induced_occurrences(schema, pairs)
    assert fitted is not None
    #  the zero-Select block is executed as an empty filter sequence, not as a
    #  hidden `all` predicate: its occurrence records an empty prefix
    occ = [o for o in SF.occurrences(schema) if o.block_index == 1][0]
    assert occ.local_prefix[1] == ()


def test_positive_target_evades_base_search_with_same_fitter():
    schema, pairs = render(*TWO_BLOCK)
    fitted, _ = SF.fit_induced_occurrences(schema, pairs)
    assert fitted is not None
    report = SF.base_search_with_scoped_fitter(pairs)
    assert report["enumerated"] == 200
    assert report["exact"] == 0, "baseline must not reach this target"


def test_positive_same_type_slots_are_not_collapsed():
    """Two Map[FeatureValue,Colour] occurrences fitted to DIFFERENT tables."""
    schema, pairs = render(*TWO_BLOCK)
    fitted, _ = SF.fit_induced_occurrences(schema, pairs)
    assert fitted is not None
    #  read the fitted Lookup tables straight from the instantiated AST
    #  (blocks_from_ast validates canonical OPEN slots, so it rejects an
    #  instantiated schema by design)
    tables = [stage[1][1][1][0] for stage in fitted[1] if stage[0] == "Map"]
    assert len(tables) == 2
    assert tables[0] != tables[1], "occurrences collapsed onto one table"
    #  the v1.1 learner cannot do this: it collapses by declared type
    assert MI.fit_induced_slots(schema, pairs) is None


# --------------------------------------------------------------------------
# negative controls
# --------------------------------------------------------------------------

def test_negative_unobservable_block_rejected():
    """A block whose predicate selects nothing on these grids has no visible
    constraint and must be rejected, not silently dropped."""
    schema, pairs = render(
        [("colour_components", ("rectangular",), "area"),
         ("colour_components", ("not_rectangular",), "area")],
        [table(AREAS, 5), table(AREAS, 8)], 80000)
    if len(pairs) < 3:
        pytest.skip("fixture produced too few demonstrations")
    fitted, evidence = SF.fit_induced_occurrences(schema, pairs)
    assert fitted is None
    assert evidence["failure"] in ("slot_unobservable", "slot_key_unobserved")


def test_negative_conflicting_key_colour_demands():
    """Demonstrations that demand two colours for one (slot, key)."""
    schema, pairs = render(*TWO_BLOCK)
    assert len(pairs) >= 3
    corrupted = list(pairs)
    grid_in, grid_out = corrupted[0]
    mutated = grid_out.copy()
    cells = np.argwhere(mutated == 5)
    if len(cells):
        mutated[tuple(cells[0])] = 9          # one region now demands 9, not 5
        corrupted[0] = (grid_in, mutated)
    fitted, evidence = SF.fit_induced_occurrences(schema, corrupted)
    assert fitted is None
    assert evidence["failure"] in ("region_colour_conflict", "slot_nonfunctional",
                                   "scoped_fit_failed")


def test_negative_wrong_schema_rejected():
    _, pairs = render(*TWO_BLOCK)
    wrong = CV.ast_from_blocks([("separator_panels", ("square",), "row_band")])
    fitted, evidence = SF.fit_induced_occurrences(wrong, pairs)
    assert fitted is None and "failure" in evidence


def test_negative_no_fit_without_exact_replay():
    """Every successful fit must have replayed exactly; the flag is present
    only on success and never set on a failure path."""
    schema, pairs = render(*TWO_BLOCK)
    fitted, evidence = SF.fit_induced_occurrences(schema, pairs)
    assert fitted is not None and evidence.get("exact_replay") is True
    _, bad = SF.fit_induced_occurrences(
        CV.ast_from_blocks([("enclosed_regions", ("square",), "shape")]), pairs)
    assert "exact_replay" not in bad


# --------------------------------------------------------------------------
# structural and hygiene properties
# --------------------------------------------------------------------------

def test_determinism_of_bindings():
    schema, pairs = render(*TWO_BLOCK)
    a, _ = SF.fit_induced_occurrences(schema, pairs)
    b, _ = SF.fit_induced_occurrences(schema, pairs)
    assert a == b


def test_occurrence_paths_are_unique_and_structural():
    schema = CV.ast_from_blocks([("colour_components", (), "area"),
                                 ("background_components", ("all",), "hw"),
                                 ("enclosed_regions", (), "shape")])
    occs = SF.occurrences(schema)
    assert len(occs) == 3
    assert len({o.ast_path for o in occs}) == 3
    assert [o.block_index for o in occs] == [0, 1, 2]
    assert [o.slot_name for o in occs] == ["?0", "?1", "?2"]


def test_no_global_registry_mutation():
    before = dict(MI.SLOT_LEARNERS)
    schema, pairs = render(*TWO_BLOCK)
    SF.fit_induced_occurrences(schema, pairs)
    SF.base_search_with_scoped_fitter(pairs)
    assert MI.SLOT_LEARNERS == before
    assert MI.SLOT_LEARNERS["Map[FeatureValue,Colour]"] is \
        MI.induce_feature_colour_map


def test_fitter_takes_no_target_metadata():
    import inspect
    params = set(inspect.signature(SF.fit_induced_occurrences).parameters)
    assert params == {"schema", "pairs"}
    for name, fn in vars(SF).items():
        if inspect.isfunction(fn) and not name.startswith("_"):
            p = set(inspect.signature(fn).parameters)
            assert not p & {"target", "digest", "family", "split", "task_id",
                            "concrete", "tables"}, name
