"""Tests for adapter_schema_proposals.py — alternative object schema proposals."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adapter_schema_proposals import (
    AdapterSchemaProposer,
    ObjectSchemaProposal,
    extract_per_color_components,
    extract_monochrome_components,
    extract_majority_bg_components,
    enrich_objects,
    SCHEMA_EXTRACTORS,
)


def _make_grid():
    grid = np.zeros((5, 5), dtype=int)
    grid[0:2, 0:2] = 1
    grid[3:5, 3:5] = 2
    grid[0, 4] = 3
    return grid


class TestExtractors:
    def test_per_color_components(self):
        grid = _make_grid()
        objs = extract_per_color_components(grid)
        assert len(objs) == 3
        for o in objs:
            assert "mask" in o
            assert "primary_color" in o
            assert o["area"] > 0

    def test_monochrome_components(self):
        grid = _make_grid()
        objs = extract_monochrome_components(grid)
        assert len(objs) >= 1
        for o in objs:
            assert "mask" in o

    def test_majority_bg_components(self):
        grid = _make_grid()
        objs = extract_majority_bg_components(grid)
        assert len(objs) >= 1

    def test_enrich_objects(self):
        grid = _make_grid()
        objs = extract_per_color_components(grid)
        enriched = enrich_objects(objs, grid)
        assert len(enriched) == len(objs)
        for o in enriched:
            assert "is_largest" in o
            assert "is_smallest" in o
            assert "touches_boundary" in o

    def test_schema_extractors_registry(self):
        assert "connected_components" in SCHEMA_EXTRACTORS
        assert "per_color_components" in SCHEMA_EXTRACTORS
        assert "monochrome_components" in SCHEMA_EXTRACTORS
        assert "majority_bg_components" in SCHEMA_EXTRACTORS


class TestAdapterSchemaProposer:
    def test_should_activate_no_property(self):
        proposer = AdapterSchemaProposer()
        assert proposer.should_activate(
            property_trace={"has_discriminative_property": False},
            failure_trace={"failure_type": "no_discriminative_property"},
            object_trace={"pairs": [{"n_input_objects": 5}]},
        )

    def test_should_not_activate_strong_property(self):
        proposer = AdapterSchemaProposer()
        assert not proposer.should_activate(
            property_trace={"has_discriminative_property": True},
            failure_trace={"failure_type": "generation_failure"},
            object_trace={"pairs": [{"n_input_objects": 5}]},
        )

    def test_should_activate_on_all_proposals_failed(self):
        proposer = AdapterSchemaProposer()
        assert proposer.should_activate(
            property_trace={"has_discriminative_property": True},
            failure_trace={"failure_type": "generation_failure"},
            object_trace={"pairs": [{"n_input_objects": 5}]},
            all_proposals_failed=True,
        )

    def test_propose_schemas(self):
        proposer = AdapterSchemaProposer()
        inp = _make_grid()
        out = np.zeros((5, 5), dtype=int)
        out[0:2, 0:2] = 1
        train_pairs = [(inp, out)]
        schemas = proposer.propose_schemas(train_pairs)
        assert len(schemas) >= 1
        for s in schemas:
            assert isinstance(s, ObjectSchemaProposal)
            assert s.schema_name != "connected_components"
            assert len(s.objects) == 1  # one pair

    def test_propose_executable_selectors(self):
        proposer = AdapterSchemaProposer()
        inp = _make_grid()
        out = np.zeros((5, 5), dtype=int)
        out[0:2, 0:2] = 1
        train_pairs = [(inp, out)]
        results = proposer.propose_executable_selectors(train_pairs)
        # May or may not find selectors depending on task
        for r in results:
            assert "selector_expression" in r
            assert "schema_name" in r
            assert "extractor_name" in r
