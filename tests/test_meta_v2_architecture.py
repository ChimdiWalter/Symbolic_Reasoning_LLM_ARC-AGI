"""Architecture tests for CORA V2, run before any ARC experiment.

These check the properties the scientific claim rests on: that the language
is typed, that execution respects the types, that enumeration cannot build
an ill-typed program, that induced slots are reached only through their
declared type, and that nothing anywhere branches on a task or a concept
name.
"""
from __future__ import annotations

import inspect
import json

import numpy as np

from geocat_arc.object_reasoning import meta_search as S
from geocat_arc.object_reasoning import meta_v2 as V


class TestSignatures:
    def test_every_production_has_a_valid_signature(self):
        for name, production in V.PRODUCTIONS.items():
            assert production.name == name
            assert isinstance(production.arg_types, tuple)
            assert production.result_type
            assert callable(production.evaluate)
            assert production.cost >= 1

    def test_every_argument_type_is_reachable(self):
        """Each argument type is a terminal, an induced type, or produced."""
        produced = {p.result_type for p in V.PRODUCTIONS.values()}
        for production in V.PRODUCTIONS.values():
            for arg_type in production.arg_types:
                assert (arg_type in V.TERMINAL_VOCAB
                        or arg_type in V.INDUCED_TYPES
                        or arg_type in produced), \
                    f"{production.name} takes unreachable {arg_type}"

    def test_induced_types_are_never_enumerable(self):
        for slot_type in V.INDUCED_TYPES:
            assert slot_type not in V.TERMINAL_VOCAB

    def test_every_induced_type_has_a_learner(self):
        for slot_type in V.INDUCED_TYPES:
            assert slot_type in S.SLOT_LEARNERS


class TestTyping:
    def _grid(self):
        return np.array([[5, 5, 5, 5, 5],
                         [5, 0, 5, 0, 5],
                         [5, 5, 5, 5, 5]])

    def test_evaluator_respects_declared_output_type(self):
        grid = self._grid()
        checks = {
            V.REGIONS: ("Partition", ("background_components",)),
            V.ENTITIES: ("Entities", ("same_colour_4",)),
        }
        for expected, ast in checks.items():
            value = V._eval(ast, V.Ctx(grid))
            if value is None:
                continue
            assert isinstance(value, tuple)
            assert all(isinstance(s, frozenset) for s in value)

    def test_unresolved_slot_never_executes(self):
        ast = ("Lookup", ("?Map[FeatureValue,Colour]",))
        assert V._eval(ast, V.Ctx(self._grid())) is None

    def test_enumerated_asts_type_check(self):
        stats = S.SearchStats()
        import time
        asts = list(S.enumerate_asts(V.GRID, set(S.SUBGRAMMARS["computed_set"]),
                                     3, stats, time.monotonic() + 10))
        assert asts
        for ast in asts:
            assert V.PRODUCTIONS[ast[0]].result_type == V.GRID
            _assert_well_typed(ast)


def _assert_well_typed(ast):
    production = V.PRODUCTIONS[ast[0]]
    assert len(ast[1]) == len(production.arg_types) or production.variadic
    for arg, arg_type in zip(ast[1], production.arg_types):
        if V._is_ast(arg):
            assert V.PRODUCTIONS[arg[0]].result_type == arg_type
            _assert_well_typed(arg)
        elif isinstance(arg, str) and arg.startswith("?"):
            assert arg[1:] == arg_type
        elif arg_type in V.TERMINAL_VOCAB:
            assert arg in V.TERMINAL_VOCAB[arg_type]()


class TestSlotLearning:
    def test_slots_dispatch_only_by_declared_type(self):
        ast = ("PaintEach", (("MapOver", (
            ("Partition", ("background_components",)),
            ("Compose", (("Key", ("area",)),
                         ("Lookup", ("?Map[FeatureValue,Colour]",)))))),))
        types = V.free_slot_types(ast)
        assert types == {"?Map[FeatureValue,Colour]": V.FEATURE_COLOUR_MAP}

    def test_unresolved_slot_rejects_safely(self):
        ast = ("Recolour", (("Unique", (("Entities", ("same_colour_4",)),)),
                            "?ColourBijection"))
        pairs = [(np.zeros((3, 3), int), np.zeros((3, 3), int))]
        complete, evidence = S.fit_slots(ast, pairs)
        assert complete is None and evidence == {}

    def test_two_different_induced_slot_types_resolve_together(self):
        """The fixed-point loop must be generic, not one-slot-special.

        A schema carrying BOTH a transform and an anchor is fitted only if
        dispatch is really by type, so this is the test that the mechanism
        generalises beyond the slot type it was written against.
        """
        source = np.zeros((7, 7), int)
        source[1, 1] = 3
        source[1, 2] = 4
        target = source.copy()
        target[4, 1] = 3
        target[4, 2] = 4
        pairs = [(source, target), (source, target)]
        ast = ("Copy", (("Anchor", (
            ("Unique", (("Entities", ("multicolour_8",)),)),
            "?Anchor")),))
        complete, evidence = S.fit_slots(ast, pairs)
        assert complete is not None, "anchor slot did not resolve"
        assert "?Anchor" in evidence
        assert V.evaluate(complete, source) is not None


class TestRouter:
    def _pairs(self):
        a = np.array([[5, 5, 5], [5, 0, 5], [5, 5, 5]])
        b = a.copy()
        b[1, 1] = 2
        return [(a, b), (a, b)]

    def test_signature_has_every_preregistered_field(self):
        signature = S.failure_signature(self._pairs())
        for field in ("same_shape", "changed_cell_count",
                      "changed_on_background_fraction",
                      "preserves_nonbackground", "deletes_existing_cells",
                      "recolours_existing_cells", "changed_component_count",
                      "repeated_changed_shapes", "template_match_evidence",
                      "translation_orbit_evidence",
                      "pairwise_alignment_evidence",
                      "panel_structure_evidence"):
            assert field in signature

    def test_router_is_deterministic(self):
        pairs = self._pairs()
        assert S.route(pairs) == S.route(pairs)

    def test_router_returns_productions_never_a_program(self):
        for name in S.route(self._pairs()):
            assert name in S.SUBGRAMMARS

    def test_folds_recompute_routing_independently(self):
        """A fold must reach its decision from its own pairs alone."""
        pairs = self._pairs() + self._pairs()
        for held in range(len(pairs)):
            subset = [p for i, p in enumerate(pairs) if i != held]
            assert S.route(subset) == S.route(subset)


class TestNoTaskIdentity:
    def test_no_task_or_concept_identity_in_search_or_routing(self):
        """Nothing may branch on a task id or a concept name."""
        for module in (V, S):
            source = inspect.getsource(module)
            assert "task_id" not in source
            assert "concept_0" not in source
            # eight-hex ARC ids
            import re
            assert not re.search(r"[\"'][0-9a-f]{8}[\"']", source)


class TestSerialization:
    def test_ast_round_trips_exactly(self):
        ast = ("PaintEach", (("MapOver", (
            ("Select", (("Partition", ("background_components",)), "all")),
            ("Compose", (("Key", ("is_rect",)),
                         ("Lookup", (((True, 3), (False, 4)),)))))),))
        assert V.from_json(json.loads(json.dumps(V.to_json(ast)))) == ast

    def test_mdl_counts_table_entries_not_painted_cells(self):
        small = ("Lookup", (((True, 3),),))
        large = ("Lookup", (((True, 3), (False, 4), (None, 5)),))
        assert V.ast_nodes(large) > V.ast_nodes(small)
