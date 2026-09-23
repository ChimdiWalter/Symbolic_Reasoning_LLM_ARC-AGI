"""Unit tests for object_reasoning.memory (near-solve store, failure
clustering, fragment mining/promotion, operator invention/validation, the
fragment library + engine hooks) and the serialization schemas it depends on
(NearSolveRecord, ProgramCertificate, LibraryOperator in types.py).

All fixtures are synthetic accepted-program dataclasses — no ARC data, no
task-ID-dependent behavior (explicitly asserted by the rename tests).

Run:  source ~/.venvs/lesegenv/bin/activate
      python -m pytest geocat_arc/object_reasoning/tests/test_memory.py -q
"""
from __future__ import annotations

import json

import pytest

from geocat_arc.object_reasoning.expressions import (
    ColorExpr,
    FreeSlotExpr,
    PredExpr,
    RefExpr,
    ScalarExpr,
    VecExpr,
)
from geocat_arc.object_reasoning.inducer import InductionConfig
from geocat_arc.object_reasoning.memory import (
    CLUSTER_MIN_RETRO_SOLVES,
    CLUSTER_MIN_TASKS,
    DEFAULT_LIBRARY_PATH,
    DEFAULT_NEAR_SOLVES_PATH,
    FailureCluster,
    FragmentLibrary,
    NearSolveStore,
    PROMOTION_MIN_OCCURRENCES,
    cluster_failures,
    fragment_schema_of,
    invent_from_cluster,
    load_library,
    promote_fragments,
    try_library_first,
    validate_operator,
)
from geocat_arc.object_reasoning.types import (
    ActionRule,
    DeltaType,
    FailureStage,
    InductionResult,
    LibraryOperator,
    NearSolveRecord,
    ObjectProgram,
    ObjectRule,
    OutputSpec,
    ParameterClass,
    ProgramCertificate,
    SegmentationVariant,
    SelectorRule,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

def make_recolor_program(threshold: int = 2, color: int = 3) -> ObjectProgram:
    """Accepted-program fixture: recolor objects with hole_count == threshold.

    Same fragment SCHEMA for any (threshold, color) — both are induced
    constants that abstraction must replace with free slots.
    """
    pred = PredExpr(op="test", args=("hole_count", "==", threshold))
    selector = SelectorRule(predicate=pred, literals=pred.literals)
    action = ActionRule(
        delta_type=DeltaType.RECOLOR,
        params={"color": ColorExpr(op="const", args=(color,))},
        parameter_class=ParameterClass.CONSTANT,
    )
    return ObjectProgram(
        segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
        rules=[ObjectRule(selector=selector, action=action)],
    )


def make_translate_program(dr: int = 1, dc: int = 0) -> ObjectProgram:
    """Different schema family: translate-all by a constant vector."""
    pred = PredExpr(op="true", args=())
    selector = SelectorRule(predicate=pred, literals=0)
    action = ActionRule(
        delta_type=DeltaType.TRANSLATE,
        params={"vector": VecExpr(op="const", args=(dr, dc))},
        parameter_class=ParameterClass.CONSTANT,
    )
    return ObjectProgram(
        segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
        rules=[ObjectRule(selector=selector, action=action)],
    )


def make_relational_recolor_program(marker_color: int = 2) -> ObjectProgram:
    """Relational params: recolor largest with color of nearest marker."""
    pred = PredExpr(op="test", args=("size_rank", "==", "@rank_min"))
    selector = SelectorRule(predicate=pred, literals=1)
    ref = RefExpr(op="nearest_object_of_color", args=(marker_color,))
    action = ActionRule(
        delta_type=DeltaType.RECOLOR,
        params={"color": ColorExpr(op="color_of", args=(ref,))},
        parameter_class=ParameterClass.RELATIONAL,
    )
    return ObjectProgram(
        segmentation_variant=SegmentationVariant.S2_SAME_COLOR_8,
        rules=[ObjectRule(selector=selector, action=action)],
    )


def make_trivial_program() -> ObjectProgram:
    """(true-selector, parameterless keep) — the identity rule; never mined."""
    pred = PredExpr(op="true", args=())
    return ObjectProgram(
        segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
        rules=[ObjectRule(selector=SelectorRule(predicate=pred, literals=0),
                          action=ActionRule(delta_type=DeltaType.KEEP))],
    )


def make_near_solve(task_id: str,
                    timestamp: str = "2026-07-02T00:00:00+00:00",
                    failure_stage: str = FailureStage.SELECTOR.value,
                    delta_histogram: dict | None = None,
                    residual_types: tuple[str, ...] = ("recolor",),
                    program: ObjectProgram | None = None,
                    explained_rules: list | None = None) -> NearSolveRecord:
    return NearSolveRecord(
        task_id=task_id,
        timestamp=timestamp,
        segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4.value,
        program_partial=program.to_dict() if program is not None else None,
        train_fit_pixels=0.8,
        train_fit_objects=0.75,
        explained_rules=explained_rules or [],
        residual={
            "unexplained_deltas": [{"delta_type": t, "count": 1,
                                    "example_features": {}}
                                   for t in residual_types],
            "conflict_report": {"selector_conflicts": 1,
                                "parameter_conflicts": 0},
            "loo_failures": [],
        },
        delta_histogram=delta_histogram or {"keep": 2, "recolor": 3},
        failure_stage=failure_stage,
    )


# ---------------------------------------------------------------------------
# Schema round-trips (types.py serialization ownership)
# ---------------------------------------------------------------------------

class TestSchemas:
    def test_near_solve_record_round_trip(self):
        rec = make_near_solve("t1", program=make_recolor_program())
        again = NearSolveRecord.from_dict(json.loads(json.dumps(rec.to_dict())))
        assert again == rec
        # failure_stage taxonomy is the Section-5.1 vocabulary
        assert {s.value for s in FailureStage} == {
            "segmentation", "matching", "selector", "parameter", "loo"}
        assert again.failure_stage in {s.value for s in FailureStage}

    def test_program_partial_reconstructs(self):
        rec = make_near_solve("t1", program=make_recolor_program(2, 3))
        program = ObjectProgram.from_dict(rec.program_partial)
        assert program.rules[0].action.delta_type is DeltaType.RECOLOR
        assert program.rules[0].action.params["color"].args == (3,)

    def test_program_certificate_round_trip(self):
        prog = make_relational_recolor_program()
        cert = ProgramCertificate(
            task_id="t1",
            program=prog.to_dict(),
            segmentation_variant=prog.segmentation_variant.value,
            train_fit=1.0,
            loo_score=1.0,
            loo_folds=3,
            parameter_class=prog.worst_parameter_class.value,
            selector_literals=1,
            program_depth=prog.program_depth,
            expression_size=prog.expression_size,
            library_operators_used=[],
            invented_from_cluster=None,
            hypotheses_enumerated=120,
            induction_time_s=1.5,
            harness_commit="abc123",
            run_id="run_1",
        )
        again = ProgramCertificate.from_dict(json.loads(json.dumps(cert.to_dict())))
        assert again == cert
        # bounded-claims fields present (Section 5.5) + A5 invariant shape
        d = cert.to_dict()
        for key in ("task_id", "program", "segmentation_variant", "train_fit",
                    "loo_score", "loo_folds", "parameter_class",
                    "selector_literals", "program_depth", "expression_size",
                    "library_operators_used", "invented_from_cluster",
                    "hypotheses_enumerated", "induction_time_s",
                    "harness_commit", "run_id"):
            assert key in d
        # induced-fraction flags: parameter_class + selector_literals
        assert d["parameter_class"] == "relational"
        assert d["selector_literals"] == 1

    def test_library_operator_round_trip(self):
        op = LibraryOperator(
            name="op_recolor_by_hole_count_abc123",
            fragment={"selector": {}, "action": {}},
            free_slots=[("slot_0", "scalar"), ("slot_1", "color")],
            provenance=["t1", "t2", "t3"],
            created_at="2026-07-02T00:00:00+00:00",
            loo_record={"retro_solved": ["t1", "t2"]},
            falsification_record={"passed": True},
        )
        again = LibraryOperator.from_dict(json.loads(json.dumps(op.to_dict())))
        assert again == op
        assert all(isinstance(s, tuple) for s in again.free_slots)


# ---------------------------------------------------------------------------
# NearSolveStore (JSONL, append-only)
# ---------------------------------------------------------------------------

class TestNearSolveStore:
    def test_append_and_load_all(self, tmp_path):
        store = NearSolveStore(tmp_path / "near_solves.jsonl")
        r1 = make_near_solve("t1")
        r2 = make_near_solve("t2", program=make_recolor_program())
        store.append(r1)
        store.append(r2)
        loaded = store.load_all()
        assert loaded == [r1, r2]

    def test_load_missing_file_is_empty(self, tmp_path):
        assert NearSolveStore(tmp_path / "nope.jsonl").load_all() == []

    def test_truncated_trailing_line_is_skipped(self, tmp_path):
        path = tmp_path / "near_solves.jsonl"
        store = NearSolveStore(path)
        store.append(make_near_solve("t1"))
        with path.open("a") as f:
            f.write('{"task_id": "t2", "trunc')  # interrupted write
        loaded = store.load_all()
        assert [r.task_id for r in loaded] == ["t1"]

    def test_default_path_is_canonical(self):
        assert str(DEFAULT_NEAR_SOLVES_PATH).endswith(
            "outputs/object_reasoning/near_solves.jsonl")
        assert str(DEFAULT_LIBRARY_PATH).endswith(
            "outputs/object_reasoning/library.json")

    def test_records_for_cluster(self, tmp_path):
        store = NearSolveStore(tmp_path / "ns.jsonl")
        for tid in ("a", "b", "c"):
            store.append(make_near_solve(tid, failure_stage="loo"))
        store.append(make_near_solve("d", failure_stage="parameter"))
        clusters = cluster_failures(store.load_all())
        loo_cluster = next(c for c in clusters if c.signature[0] == "loo")
        members = store.records_for_cluster(loo_cluster)
        assert sorted(r.task_id for r in members) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Failure clustering (Section 5.2)
# ---------------------------------------------------------------------------

class TestFailureClustering:
    def test_grouped_by_signature(self):
        records = [
            make_near_solve("t1", failure_stage="selector"),
            make_near_solve("t2", failure_stage="selector"),
            make_near_solve("t3", failure_stage="parameter"),
            make_near_solve("t4", failure_stage="selector",
                            delta_histogram={"translate": 4}),
        ]
        clusters = cluster_failures(records)
        assert len(clusters) == 3
        sizes = sorted(c.n_tasks for c in clusters)
        assert sizes == [1, 1, 2]

    def test_histogram_support_not_counts(self):
        # same delta TYPES with different counts must share a cluster
        r1 = make_near_solve("t1", delta_histogram={"keep": 1, "recolor": 9})
        r2 = make_near_solve("t2", delta_histogram={"keep": 5, "recolor": 2})
        clusters = cluster_failures([r1, r2])
        assert len(clusters) == 1 and clusters[0].n_tasks == 2

    def test_zero_count_delta_excluded_from_support(self):
        r1 = make_near_solve("t1", delta_histogram={"keep": 2, "recolor": 3})
        r2 = make_near_solve("t2", delta_histogram={"keep": 2, "recolor": 3,
                                                    "translate": 0})
        clusters = cluster_failures([r1, r2])
        assert len(clusters) == 1

    def test_invention_candidate_threshold(self):
        records = [make_near_solve(f"t{i}", failure_stage="loo")
                   for i in range(CLUSTER_MIN_TASKS)]
        cluster = cluster_failures(records)[0]
        assert cluster.is_invention_candidate
        smaller = cluster_failures(records[:-1])[0]
        assert not smaller.is_invention_candidate

    def test_cluster_id_independent_of_task_ids(self):
        # renaming tasks must not change the cluster identity (hard constraint 1)
        a = cluster_failures([make_near_solve("t1"), make_near_solve("t2")])[0]
        b = cluster_failures([make_near_solve("x9"), make_near_solve("y7")])[0]
        assert a.cluster_id == b.cluster_id
        assert a.signature == b.signature

    def test_duplicate_record_keys_not_double_counted(self):
        r = make_near_solve("t1")
        cluster = cluster_failures([r, r])[0]
        assert cluster.n_tasks == 1 and len(cluster.member_keys) == 1


# ---------------------------------------------------------------------------
# Fragment schemas (mining key)
# ---------------------------------------------------------------------------

class TestFragmentSchema:
    def test_constants_become_free_slots(self):
        frags = fragment_schema_of(make_recolor_program(threshold=2, color=3))
        # full (selector, action) schema + the coarser action schema
        assert len(frags) == 2
        frag = frags[0]
        # selector test value -> slot_0 (scalar), color const -> slot_1 (color)
        pred_value = frag["selector"]["predicate"]["args"][2]
        assert pred_value["expr_class"] == "FreeSlotExpr"
        assert pred_value["args"] == ["slot_0", "scalar"]
        color_expr = frag["action"]["params"]["color"]
        assert color_expr["expr_class"] == "FreeSlotExpr"
        assert color_expr["args"] == ["slot_1", "color"]

    def test_schema_invariant_to_constants(self):
        a = fragment_schema_of(make_recolor_program(threshold=2, color=3))
        b = fragment_schema_of(make_recolor_program(threshold=5, color=7))
        assert a == b

    def test_different_delta_types_have_different_schemas(self):
        a = fragment_schema_of(make_recolor_program())
        b = fragment_schema_of(make_translate_program())
        assert a != b

    def test_vector_const_becomes_vector_slot(self):
        frag = fragment_schema_of(make_translate_program(2, 0))[0]
        vec = frag["action"]["params"]["vector"]
        assert vec["expr_class"] == "FreeSlotExpr"
        assert vec["args"][1] == "vector"

    def test_ref_color_literal_becomes_color_slot(self):
        a = fragment_schema_of(make_relational_recolor_program(marker_color=2))
        b = fragment_schema_of(make_relational_recolor_program(marker_color=8))
        assert a == b
        ref = a[0]["action"]["params"]["color"]["args"][0]
        assert ref["op"] == "nearest_object_of_color"
        assert ref["args"][0]["expr_class"] == "FreeSlotExpr"
        assert ref["args"][0]["args"][1] == "color"

    def test_rank_sentinel_and_bool_stay_concrete(self):
        # "@rank_min" / booleans are structural, not induced constants
        rank_frag = fragment_schema_of(make_relational_recolor_program())[0]
        assert rank_frag["selector"]["predicate"]["args"][2] == "@rank_min"

        pred = PredExpr(op="test", args=("is_rectangle", "==", True))
        prog = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=SelectorRule(predicate=pred, literals=1),
                action=ActionRule(delta_type=DeltaType.DELETE))])
        frag = fragment_schema_of(prog)[0]
        assert frag["selector"]["predicate"]["args"][2] is True

    def test_color_feature_test_value_is_color_slot(self):
        pred = PredExpr(op="test", args=("color", "==", 4))
        prog = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=SelectorRule(predicate=pred, literals=1),
                action=ActionRule(delta_type=DeltaType.DELETE))])
        frag = fragment_schema_of(prog)[0]
        assert frag["selector"]["predicate"]["args"][2]["args"][1] == "color"

    def test_color_map_node_abstracted_whole(self):
        action = ActionRule(
            delta_type=DeltaType.RECOLOR,
            params={"color": ColorExpr(op="color_map", args=({1: 2, 3: 4},))},
            parameter_class=ParameterClass.INDUCED_MAP)
        prog = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=SelectorRule(predicate=PredExpr(op="true", args=()),
                                      literals=0),
                action=action)])
        frag = fragment_schema_of(prog)[0]
        color = frag["action"]["params"]["color"]
        assert color["expr_class"] == "FreeSlotExpr"
        assert color["args"][1] == "color"
        assert "color_map" not in json.dumps(frag)  # induced map fully removed

    def test_existing_free_slots_renumbered_stably(self):
        # a program built FROM a library fragment abstracts back to itself
        pred = PredExpr(
            op="test",
            args=("hole_count", "==",
                  FreeSlotExpr(op="free_slot", args=("weird_name", "scalar"))))
        prog = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=SelectorRule(predicate=pred, literals=1),
                action=ActionRule(delta_type=DeltaType.DELETE))])
        frag = fragment_schema_of(prog)[0]
        assert frag["selector"]["predicate"]["args"][2]["args"] == \
            ["slot_0", "scalar"]
        # and its selector schema keys identically to the constant-built one
        recolor_frag = fragment_schema_of(make_recolor_program())[0]
        assert frag["selector"] == recolor_frag["selector"]

    def test_scaled_unit_direction_slotted(self):
        vec = VecExpr(op="scaled_unit",
                      args=("down", ScalarExpr(op="feature",
                                               args=("bbox_height",))))
        prog = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=SelectorRule(predicate=PredExpr(op="true", args=()),
                                      literals=0),
                action=ActionRule(delta_type=DeltaType.TRANSLATE,
                                  params={"vector": vec},
                                  parameter_class=ParameterClass.FEATURE))])
        frag = fragment_schema_of(prog)[0]
        args = frag["action"]["params"]["vector"]["args"]
        assert args[0]["expr_class"] == "FreeSlotExpr"        # direction slot
        assert args[0]["args"][1] == "direction"
        assert args[1]["op"] == "feature"                     # feature name kept
        assert args[1]["args"] == ["bbox_height"]


# ---------------------------------------------------------------------------
# Promotion (Section 5.3: >= 3 accepted programs)
# ---------------------------------------------------------------------------

class TestPromotion:
    def test_promotes_at_three_occurrences(self):
        accepted = {
            "t1": make_recolor_program(2, 3),
            "t2": make_recolor_program(1, 8),
            "t3": make_recolor_program(4, 5),
        }
        ops = promote_fragments(accepted)
        # two granularities recur in all 3 programs: the full
        # (selector, action) schema and the coarser action schema
        assert len(ops) == 2
        full = [op for op in ops
                if op.name.startswith("op_recolor_by_hole_count_")]
        assert len(full) == 1
        op = full[0]
        assert op.provenance == ["t1", "t2", "t3"]
        assert ("slot_0", "scalar") in op.free_slots
        assert ("slot_1", "color") in op.free_slots
        schema = [op for op in ops if op.name.startswith("op_recolor_by_slot_")]
        assert len(schema) == 1
        assert schema[0].provenance == ["t1", "t2", "t3"]
        assert ("slot_0", "predicate") in schema[0].free_slots
        assert ("slot_1", "color") in schema[0].free_slots

    def test_two_occurrences_not_promoted(self):
        accepted = {"t1": make_recolor_program(2, 3),
                    "t2": make_recolor_program(1, 8),
                    "t3": make_translate_program()}
        assert promote_fragments(accepted) == []
        assert PROMOTION_MIN_OCCURRENCES == 3

    def test_min_occurrences_override(self):
        accepted = {"t1": make_recolor_program(2, 3),
                    "t2": make_recolor_program(1, 8)}
        ops = promote_fragments(accepted, min_occurrences=2)
        assert len(ops) == 2  # full schema + action schema
        assert all(op.provenance == ["t1", "t2"] for op in ops)

    def test_trivial_keep_all_never_mined(self):
        accepted = {f"t{i}": make_trivial_program() for i in range(5)}
        assert promote_fragments(accepted) == []

    def test_distinct_schemas_promoted_separately(self):
        accepted = {}
        for i in range(3):
            accepted[f"r{i}"] = make_recolor_program(i, i + 1)
            accepted[f"m{i}"] = make_translate_program(i + 1, 0)
        ops = promote_fragments(accepted)
        # (full + action schema) per family; the translate family's full
        # schema (true-selector) and action schema stay distinct keys
        assert len(ops) == 4
        deltas = {op.fragment["action"]["delta_type"] for op in ops}
        assert deltas == {"recolor", "translate"}

    def test_deterministic_names_and_order(self):
        accepted = {f"t{i}": make_recolor_program(i, i) for i in range(3)}
        first = promote_fragments(accepted)
        second = promote_fragments(accepted)
        assert [op.name for op in first] == [op.name for op in second]

    def test_fragment_serializes_and_reconstructs(self):
        accepted = {f"t{i}": make_relational_recolor_program(i + 1)
                    for i in range(3)}
        ops = promote_fragments(accepted)
        full = [op for op in ops
                if op.fragment["selector"]["predicate"].get("expr_class")
                != "FreeSlotExpr"]
        assert len(full) == 1
        op = full[0]
        # the fragment must be a valid serialized ObjectRule with holes:
        rule = ObjectRule.from_dict(json.loads(json.dumps(op.fragment)))
        assert rule.action.delta_type is DeltaType.RECOLOR
        holes = [a for a in [rule.action.params["color"].args[0].args[0]]
                 if isinstance(a, FreeSlotExpr)]
        assert holes and holes[0].args[1] == "color"

    def test_action_schema_unifies_across_selectors(self):
        # Three programs with the SAME action but three DIFFERENT selector
        # predicates: no full schema recurs, but the action schema promotes.
        p1 = make_recolor_program(2, 3)          # hole_count == k
        p2 = make_relational_recolor_program(4)  # size_rank == @rank_min ...
        pred = PredExpr(op="test", args=("color", "==", 6))
        p3 = ObjectProgram(
            segmentation_variant=SegmentationVariant.S1_SAME_COLOR_4,
            rules=[ObjectRule(
                selector=SelectorRule(predicate=pred, literals=pred.literals),
                action=ActionRule(
                    delta_type=DeltaType.RECOLOR,
                    params={"color": ColorExpr(op="const", args=(7,))},
                    parameter_class=ParameterClass.CONSTANT))])
        # p1 and p3 share the constant-recolor action schema; p2's relational
        # action schema differs -> only with a third constant-recolor member
        # does the schema reach 3 occurrences.
        pred4 = PredExpr(op="test", args=("is_contained", "==", True))
        p4 = ObjectProgram(
            segmentation_variant=SegmentationVariant.S2_SAME_COLOR_8,
            rules=[ObjectRule(
                selector=SelectorRule(predicate=pred4, literals=pred4.literals),
                action=ActionRule(
                    delta_type=DeltaType.RECOLOR,
                    params={"color": ColorExpr(op="const", args=(1,))},
                    parameter_class=ParameterClass.CONSTANT))])
        ops = promote_fragments({"a": p1, "b": p2, "c": p3, "d": p4})
        assert len(ops) == 1
        op = ops[0]
        sel = op.fragment["selector"]["predicate"]
        assert sel["expr_class"] == "FreeSlotExpr" and sel["args"][1] == "predicate"
        assert op.fragment["action"]["delta_type"] == "recolor"
        assert sorted(op.provenance) == ["a", "c", "d"]
        # round-trips as a valid ObjectRule with the predicate hole intact
        rule = ObjectRule.from_dict(json.loads(json.dumps(op.fragment)))
        assert isinstance(rule.selector.predicate, FreeSlotExpr)

    def test_trivial_keep_has_no_action_schema(self):
        # identity keep never yields an action schema even across 5 programs
        accepted = {f"t{i}": make_trivial_program() for i in range(5)}
        assert promote_fragments(accepted, min_occurrences=2) == []


# ---------------------------------------------------------------------------
# Operator invention from failure clusters (Sections 5.2/5.3)
# ---------------------------------------------------------------------------

def _cluster_and_store(tmp_path, n=3, program_factory=make_recolor_program):
    store = NearSolveStore(tmp_path / "ns.jsonl")
    for i in range(n):
        store.append(make_near_solve(
            f"t{i}", failure_stage="loo",
            program=program_factory(i, (i % 9) + 1)))
    clusters = cluster_failures(store.load_all())
    assert len(clusters) == 1
    return clusters[0], store


class TestInvention:
    def test_requires_retro_solve_fn(self, tmp_path):
        cluster, store = _cluster_and_store(tmp_path)
        assert invent_from_cluster(cluster, store) is None

    def test_invents_when_retro_solves_two(self, tmp_path):
        cluster, store = _cluster_and_store(tmp_path)
        solved = {"t0", "t2"}
        attempted = []

        def retro(task_id, candidate):
            attempted.append(task_id)
            assert isinstance(candidate, LibraryOperator)
            return task_id in solved

        op = invent_from_cluster(cluster, store, retro)
        assert op is not None
        assert set(op.loo_record["retro_solved"]) == solved
        assert op.loo_record["cluster_id"] == cluster.cluster_id
        assert set(attempted) == {"t0", "t1", "t2"}  # normal path on ALL members
        assert solved <= set(op.provenance)
        assert CLUSTER_MIN_RETRO_SOLVES == 2

    def test_rejected_when_only_one_retro_solve(self, tmp_path):
        cluster, store = _cluster_and_store(tmp_path)
        assert invent_from_cluster(cluster, store,
                                   lambda tid, cand: tid == "t0") is None

    def test_retro_solve_exceptions_do_not_crash(self, tmp_path):
        cluster, store = _cluster_and_store(tmp_path)

        def flaky(task_id, candidate):
            if task_id == "t1":
                raise RuntimeError("boom")
            return True

        op = invent_from_cluster(cluster, store, flaky)
        assert op is not None
        assert set(op.loo_record["retro_solved"]) == {"t0", "t2"}

    def test_mines_from_explained_rules_without_partial_program(self, tmp_path):
        store = NearSolveStore(tmp_path / "ns.jsonl")
        for i in range(3):
            explained = [{
                "selector_expr": PredExpr(
                    op="test", args=("hole_count", "==", i)).to_dict(),
                "action": "recolor",
                "param_exprs": {"color": ColorExpr(op="const",
                                                   args=(i + 1,)).to_dict()},
                "n_objects_explained": 2,
            }]
            store.append(make_near_solve(f"t{i}", failure_stage="loo",
                                         explained_rules=explained))
        cluster = cluster_failures(store.load_all())[0]
        op = invent_from_cluster(cluster, store, lambda tid, cand: True)
        assert op is not None
        assert op.name.startswith("op_recolor_by_hole_count_")

    def test_empty_cluster_returns_none(self, tmp_path):
        store = NearSolveStore(tmp_path / "empty.jsonl")
        cluster = FailureCluster(cluster_id="fc_x", signature=("loo", (), ()),
                                 member_keys=[("ghost", "ts")])
        assert invent_from_cluster(cluster, store, lambda t, c: True) is None


# ---------------------------------------------------------------------------
# Counterexample survival (Section 5.4)
# ---------------------------------------------------------------------------

def _promoted_op() -> LibraryOperator:
    accepted = {f"t{i}": make_recolor_program(i, i + 1) for i in range(3)}
    return promote_fragments(accepted)[0]


class TestValidateOperator:
    def test_passes_all_gates(self):
        op = _promoted_op()
        accepted = lambda tid: InductionResult(task_id=tid, accepted=True)  # noqa: E731
        passed, record = validate_operator(op, accepted, [lambda: True] * 10)
        assert passed
        assert record["provenance_passed"]
        assert record["probes"] == {"total": 10, "passed": 10, "regressions": 0}
        assert record["color_invariance"]["passed"]
        assert record["passed"]

    def test_provenance_reinduction_failure_blocks(self):
        op = _promoted_op()

        def reinduce(tid):
            return InductionResult(task_id=tid, accepted=(tid != "t1"))

        passed, record = validate_operator(op, reinduce, [lambda: True])
        assert not passed
        assert record["provenance_revalidation"]["t1"] is False

    def test_probe_regression_blocks(self):
        op = _promoted_op()
        accepted = lambda tid: InductionResult(task_id=tid, accepted=True)  # noqa: E731
        probes = [lambda: True, lambda: False, lambda: True]
        passed, record = validate_operator(op, accepted, probes)
        assert not passed
        assert record["probes"]["regressions"] == 1

    def test_probe_exception_counts_as_regression(self):
        op = _promoted_op()
        accepted = lambda tid: InductionResult(task_id=tid, accepted=True)  # noqa: E731

        def bad_probe():
            raise RuntimeError("probe crashed")

        passed, record = validate_operator(op, accepted, [bad_probe])
        assert not passed and record["probes"]["regressions"] == 1

    def test_concrete_color_constant_fails_color_invariance(self):
        # hand-assembled fragment claiming color genericity but hardcoding one
        frag = {
            "selector": {"predicate": PredExpr(op="true", args=()).to_dict(),
                         "literals": 0},
            "action": {"delta_type": "recolor",
                       "params": {"color": ColorExpr(op="const",
                                                     args=(3,)).to_dict()},
                       "parameter_class": "constant"},
        }
        op = LibraryOperator(name="op_bad", fragment=frag,
                             free_slots=[("slot_0", "color")],
                             provenance=["t1"])
        accepted = lambda tid: InductionResult(task_id=tid, accepted=True)  # noqa: E731
        passed, record = validate_operator(op, accepted, [])
        assert not passed
        assert not record["color_invariance"]["passed"]
        assert record["color_invariance"]["violations"]

    def test_mined_fragments_color_clean_by_construction(self):
        accepted = {f"t{i}": make_relational_recolor_program(i + 1)
                    for i in range(3)}
        op = promote_fragments(accepted)[0]
        assert any(t == "color" for _, t in op.free_slots)
        ok = lambda tid: InductionResult(task_id=tid, accepted=True)  # noqa: E731
        passed, record = validate_operator(op, ok, [])
        assert passed and record["color_invariance"]["violations"] == []


# ---------------------------------------------------------------------------
# FragmentLibrary + engine hooks (load_library / try_library_first /
# --no-library ablation)
# ---------------------------------------------------------------------------

class TestLibrary:
    def test_register_save_reload(self, tmp_path):
        path = tmp_path / "library.json"
        lib = FragmentLibrary(path)
        op = _promoted_op()
        lib.register(op)
        assert len(lib) == 1
        reloaded = FragmentLibrary(path)
        assert len(reloaded) == 1
        assert reloaded.operators()[0] == op

    def test_duplicate_registration_raises(self, tmp_path):
        lib = FragmentLibrary(tmp_path / "library.json")
        op = _promoted_op()
        lib.register(op)
        with pytest.raises(ValueError):
            lib.register(op)

    def test_disabled_library_yields_no_operators(self, tmp_path):
        path = tmp_path / "library.json"
        FragmentLibrary(path).register(_promoted_op())
        ablated = FragmentLibrary(path, enabled=False)
        assert len(ablated) == 1          # file content intact
        assert ablated.operators() == []  # but nothing offered to the inducer

    def test_load_library_hook(self, tmp_path):
        path = tmp_path / "library.json"
        FragmentLibrary(path).register(_promoted_op())
        lib = load_library(path)
        assert len(lib.operators()) == 1
        no_lib = load_library(path, enabled=False)
        assert no_lib.operators() == []

    def test_load_library_default_path(self):
        lib = load_library()
        assert lib.path == DEFAULT_LIBRARY_PATH

    def test_try_library_first_injects_operators(self, tmp_path):
        path = tmp_path / "library.json"
        lib = FragmentLibrary(path)
        op = _promoted_op()
        lib.register(op)
        config = InductionConfig()
        new_config = try_library_first(lib, config)
        assert new_config.library == [op]
        assert new_config.use_library is True
        assert config.library == []          # input not mutated
        assert new_config.budget_s == config.budget_s

    def test_try_library_first_ablation(self, tmp_path):
        path = tmp_path / "library.json"
        FragmentLibrary(path).register(_promoted_op())
        ablated = FragmentLibrary(path, enabled=False)
        new_config = try_library_first(ablated, InductionConfig())
        assert new_config.library == []
        assert new_config.use_library is False


# ---------------------------------------------------------------------------
# End-to-end memory-loop smoke: promote -> validate -> register -> reload ->
# fragment usable for per-task re-induction (slots enumerable)
# ---------------------------------------------------------------------------

class TestMemoryLoopSmoke:
    def test_full_loop(self, tmp_path):
        # 1. three accepted programs -> promotion
        accepted = {"t1": make_recolor_program(1, 2),
                    "t2": make_recolor_program(2, 4),
                    "t3": make_recolor_program(3, 6)}
        ops = promote_fragments(accepted)
        assert len(ops) == 2  # full schema + action schema
        op = [o for o in ops
              if o.fragment["selector"]["predicate"].get("expr_class")
              != "FreeSlotExpr"][0]

        # 2. counterexample survival
        ok = lambda tid: InductionResult(task_id=tid, accepted=True)  # noqa: E731
        passed, record = validate_operator(op, ok, [lambda: True] * 10)
        assert passed
        op.falsification_record = record

        # 3. register + persist + reload
        lib_path = tmp_path / "library.json"
        lib = FragmentLibrary(lib_path)
        lib.register(op)
        reloaded = load_library(lib_path)
        assert [o.name for o in reloaded.operators()] == [op.name]

        # 4. offered to the inducer ahead of raw enumeration
        config = try_library_first(reloaded, InductionConfig())
        assert config.library[0].name == op.name

        # 5. fragment is a live, re-bindable typed sub-program
        rule = ObjectRule.from_dict(config.library[0].fragment)
        slot_names = {s for s, _ in config.library[0].free_slots}
        assert slot_names == {"slot_0", "slot_1"}
        assert rule.action.delta_type is DeltaType.RECOLOR
        # per-task induction re-binds every hole; here we just confirm the
        # holes are addressable by name+type (substitution itself is the
        # expressions team's substitute_free_slots)
        value = rule.selector.predicate.args[2]
        assert isinstance(value, FreeSlotExpr)
        assert tuple(value.args) in {("slot_0", "scalar"), ("slot_1", "scalar")}
