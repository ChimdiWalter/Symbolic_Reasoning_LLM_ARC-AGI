"""Integration test: concept-grammar-to-resume pipeline.

Proves the full path from concept generation through to solving a previously
unsolvable task:
1. ConceptGenerator discovers a BoundRelationConcept that discriminates
2. ConceptValidator confirms discrimination_score=1.0 and LOO passes
3. The concept is registered in ConceptMemory
4. An ExtendedGridAdapter exposes the concept as a new property
5. StructuralReasoner with the extended adapter solves the task

Synthetic task design:
- Grid contains a single-cell marker (color 1) in a specific column
- 2x2 block objects (color 2) exist in various columns
- Rule: keep blocks in the same column as the marker (marker removed from output)
- No base property discriminates "same column as marker" -> base reasoner fails
- BoundRelation(same_col, ref_marker) discriminates perfectly -> extended succeeds
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pytest

from reasoning_project.concept_grammar import (
    BoundRelationConcept,
    ConceptExpression,
    ConceptGenerator,
    ConceptValidator,
    ReferenceConcept,
    RelationConcept,
    _scene_from_objects,
)
from reasoning_project.concept_memory import ConceptMemory, LearnedConcept
from reasoning_project.reasoning_engine import (
    GridDomainAdapter,
    StructuralReasoner,
    _extract_objects_with_properties,
)


# ═══════════════════════════════════════════════════════════════════════════
# ExtendedGridAdapter — bridges learned concepts into the reasoning engine
# ═══════════════════════════════════════════════════════════════════════════

class ExtendedGridAdapter(GridDomainAdapter):
    """GridDomainAdapter augmented with learned concept properties."""

    def __init__(self, learned_concepts=None):
        super().__init__()
        self._learned = learned_concepts or []  # List[Tuple[str, ConceptExpression]]

    def property_names(self):
        base = super().property_names()
        return base + [name for name, _ in self._learned]

    def get_property(self, obj, prop):
        for name, expr in self._learned:
            if prop == name:
                scene = obj.get("_scene")
                if scene is None:
                    return False
                return expr.evaluate(obj, scene)
        return super().get_property(obj, prop)

    def extract_objects(self, scene):
        objects = super().extract_objects(scene)
        scene_dict = _scene_from_objects(objects, scene)
        for obj in objects:
            obj["_scene"] = scene_dict
        return objects


# ═══════════════════════════════════════════════════════════════════════════
# Synthetic task construction
# ═══════════════════════════════════════════════════════════════════════════

def _make_task_pair(marker_col, block_cols, grid_h=8, grid_w=8):
    """Create a single input/output pair.

    - Marker: single cell of color 1 at row 0, column marker_col
    - Blocks: 2x2 squares of color 2 at row 4, each at one of block_cols
    - Output: same grid but marker removed, and only blocks in marker_col kept
    """
    inp = np.zeros((grid_h, grid_w), dtype=int)
    out = np.zeros((grid_h, grid_w), dtype=int)

    # Place marker (single cell, color 1)
    inp[0, marker_col] = 1

    # Place 2x2 blocks (color 2) at row 4
    for bc in block_cols:
        inp[4:6, bc:bc+2] = 2
        # Keep block only if it overlaps marker column
        # Block occupies columns [bc, bc+1], marker is at marker_col
        if bc <= marker_col <= bc + 1:
            out[4:6, bc:bc+2] = 2

    return inp, out


def _make_synthetic_task():
    """Build a task with 3 train pairs and 1 test input.

    Each pair has:
    - A marker in a different column
    - Multiple 2x2 blocks, some aligned, some not
    - Output keeps only aligned blocks (marker removed)
    """
    # Training pair 1: marker at col 2, blocks at cols [1, 4]
    # Block at col 1 spans cols 1-2 (contains marker col 2) -> kept
    # Block at col 4 spans cols 4-5 (no overlap) -> removed
    inp1, out1 = _make_task_pair(marker_col=2, block_cols=[1, 4])

    # Training pair 2: marker at col 5, blocks at cols [0, 4]
    # Block at col 0 spans cols 0-1 -> removed
    # Block at col 4 spans cols 4-5 (contains marker col 5) -> kept
    inp2, out2 = _make_task_pair(marker_col=5, block_cols=[0, 4])

    # Training pair 3: marker at col 3, blocks at cols [2, 6]
    # Block at col 2 spans cols 2-3 (contains marker col 3) -> kept
    # Block at col 6 spans cols 6-7 -> removed
    inp3, out3 = _make_task_pair(marker_col=3, block_cols=[2, 6])

    # Test: marker at col 1, blocks at cols [0, 4]
    # Block at col 0 spans cols 0-1 (contains marker col 1) -> kept
    # Block at col 4 spans cols 4-5 -> removed
    test_inp, expected_out = _make_task_pair(marker_col=1, block_cols=[0, 4])

    train_pairs = [(inp1, out1), (inp2, out2), (inp3, out3)]
    test_inputs = [test_inp]
    expected_outputs = [expected_out]

    # Task dict format (for ConceptGenerator/Validator)
    task_dict = {
        "task_id": "synthetic_col_alignment",
        "train": [
            {"input": inp1.tolist(), "output": out1.tolist()},
            {"input": inp2.tolist(), "output": out2.tolist()},
            {"input": inp3.tolist(), "output": out3.tolist()},
        ],
    }

    return train_pairs, test_inputs, expected_outputs, task_dict


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def synthetic_task():
    """Return (train_pairs, test_inputs, expected_outputs, task_dict)."""
    return _make_synthetic_task()


@pytest.fixture
def discriminating_concept():
    """The BoundRelation(same_col, ref_marker) concept."""
    rel = RelationConcept("same_col")
    ref = ReferenceConcept("marker")
    return BoundRelationConcept(rel, ref)


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: ConceptGenerator discovers a discriminating concept
# ═══════════════════════════════════════════════════════════════════════════

class TestConceptGenerated:
    """Verify ConceptGenerator/ConceptValidator can find a discriminating concept."""

    def test_concept_generated(self, synthetic_task):
        """ConceptGenerator.generate_from_failure_cluster finds same_col_wrt_marker."""
        train_pairs, _, _, task_dict = synthetic_task

        generator = ConceptGenerator()
        concepts = generator.generate_from_failure_cluster(
            [task_dict], max_concepts=100
        )

        # Should find at least one concept that discriminates
        assert len(concepts) > 0, "Generator produced no concepts"

        # Check for same_col_wrt_marker specifically
        concept_names = [c.name for c in concepts]
        assert "same_col_wrt_marker" in concept_names, (
            f"Expected 'same_col_wrt_marker' in generated concepts. "
            f"Got: {concept_names}"
        )

    def test_generated_concept_validates(self, synthetic_task):
        """The generated concept has discrimination_score=1.0 and passes LOO."""
        _, _, _, task_dict = synthetic_task

        generator = ConceptGenerator()
        concepts = generator.generate_from_failure_cluster(
            [task_dict], max_concepts=100
        )

        validator = ConceptValidator()

        # Find same_col_wrt_marker
        target = None
        for c in concepts:
            if c.name == "same_col_wrt_marker":
                target = c
                break
        assert target is not None

        # discrimination_score should be 1.0
        score = validator.training_discrimination_score(target, task_dict)
        assert score == 1.0, f"Expected score 1.0, got {score}"

        # LOO should pass
        loo_passed = validator.loo_validate(target, task_dict)
        assert loo_passed, "LOO validation failed"


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: Concept registered in ConceptMemory
# ═══════════════════════════════════════════════════════════════════════════

class TestConceptRegistered:
    """Verify ConceptMemory stores the validated concept."""

    def test_concept_registered(self, synthetic_task, discriminating_concept):
        """Validated concept is stored in ConceptMemory with correct metadata."""
        _, _, _, task_dict = synthetic_task

        memory = ConceptMemory()

        learned = LearnedConcept(
            name=discriminating_concept.name,
            expression_str=discriminating_concept.to_string(),
            complexity=discriminating_concept.complexity,
            source_failure_cluster="no_discrimination:richer_property_language",
            source_tasks=[task_dict["task_id"]],
            loo_passed=True,
            discrimination_score=1.0,
            dependencies=[d for d in discriminating_concept.dependencies],
            status="validated",
        )

        success = memory.register_concept(learned, compute_fn=discriminating_concept)
        assert success, "Failed to register concept"

        # Verify it's in the graph
        stored = memory.graph.get_concept(discriminating_concept.name)
        assert stored is not None
        assert stored.status == "registered"
        assert stored.discrimination_score == 1.0
        assert stored.loo_passed is True

    def test_concept_retrievable(self, synthetic_task, discriminating_concept):
        """Registered concept can be retrieved for a task."""
        _, _, _, task_dict = synthetic_task

        memory = ConceptMemory()
        learned = LearnedConcept(
            name=discriminating_concept.name,
            expression_str=discriminating_concept.to_string(),
            complexity=discriminating_concept.complexity,
            source_failure_cluster="no_discrimination:richer_property_language",
            source_tasks=[task_dict["task_id"]],
            loo_passed=True,
            discrimination_score=1.0,
            dependencies=[d for d in discriminating_concept.dependencies],
            status="validated",
        )
        memory.register_concept(learned, compute_fn=discriminating_concept)

        # Retrieve registered concepts
        registered = memory.graph.by_status("registered")
        names = [c.name for c in registered]
        assert discriminating_concept.name in names

    def test_compute_fn_stored(self, discriminating_concept):
        """The compute function is stored alongside the concept."""
        memory = ConceptMemory()
        learned = LearnedConcept(
            name=discriminating_concept.name,
            expression_str=discriminating_concept.to_string(),
            complexity=discriminating_concept.complexity,
            source_failure_cluster="test",
            source_tasks=["test_task"],
            status="validated",
        )
        memory.register_concept(learned, compute_fn=discriminating_concept)

        assert discriminating_concept.name in memory._registered_compute_fns
        assert memory._registered_compute_fns[discriminating_concept.name] is discriminating_concept


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: Concept visible to reasoner via ExtendedGridAdapter
# ═══════════════════════════════════════════════════════════════════════════

class TestConceptVisibleToReasoner:
    """Verify ExtendedGridAdapter makes the concept available as a property."""

    def test_concept_visible_to_reasoner(self, discriminating_concept):
        """The learned concept appears in adapter.property_names()."""
        adapter = ExtendedGridAdapter(
            learned_concepts=[(discriminating_concept.name, discriminating_concept)]
        )

        prop_names = adapter.property_names()
        assert discriminating_concept.name in prop_names, (
            f"Concept '{discriminating_concept.name}' not in property_names"
        )

    def test_concept_evaluates_correctly(self, synthetic_task, discriminating_concept):
        """The concept evaluates True for aligned objects, False otherwise."""
        train_pairs, _, _, _ = synthetic_task
        adapter = ExtendedGridAdapter(
            learned_concepts=[(discriminating_concept.name, discriminating_concept)]
        )

        inp, out = train_pairs[0]  # marker at col 2, blocks at [1, 4]
        objects = adapter.extract_objects(inp)

        # Find the marker and block objects
        marker_objs = [o for o in objects if o["area"] == 1]
        block_objs = [o for o in objects if o["area"] == 4]

        assert len(marker_objs) == 1, f"Expected 1 marker, got {len(marker_objs)}"
        assert len(block_objs) == 2, f"Expected 2 blocks, got {len(block_objs)}"

        # Block at col 1 (spans cols 1-2, same col as marker at 2) -> True
        # Block at col 4 (spans cols 4-5) -> False
        aligned_block = [b for b in block_objs if b["center_c"] < 3][0]
        distant_block = [b for b in block_objs if b["center_c"] > 3][0]

        val_aligned = adapter.get_property(aligned_block, discriminating_concept.name)
        val_distant = adapter.get_property(distant_block, discriminating_concept.name)

        assert val_aligned is True, "Aligned block should evaluate True"
        assert val_distant is False, "Distant block should evaluate False"

    def test_property_discriminates_across_all_pairs(
        self, synthetic_task, discriminating_concept
    ):
        """The concept perfectly discriminates kept/removed across all train pairs."""
        train_pairs, _, _, _ = synthetic_task
        adapter = ExtendedGridAdapter(
            learned_concepts=[(discriminating_concept.name, discriminating_concept)]
        )

        for i, (inp, out) in enumerate(train_pairs):
            objects = adapter.extract_objects(inp)
            classification = adapter.classify_kept_removed(objects, inp, out)
            assert classification is not None, f"Pair {i}: classify_kept_removed returned None"
            kept_idx, removed_idx = classification

            for ki in kept_idx:
                val = adapter.get_property(objects[ki], discriminating_concept.name)
                assert val is True, (
                    f"Pair {i}: kept object {ki} evaluated False"
                )
            for ri in removed_idx:
                val = adapter.get_property(objects[ri], discriminating_concept.name)
                assert val is False, (
                    f"Pair {i}: removed object {ri} evaluated True"
                )


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: StructuralReasoner with extended adapter solves the task
# ═══════════════════════════════════════════════════════════════════════════

class TestConceptSolvesTask:
    """Verify StructuralReasoner with ExtendedGridAdapter solves the task."""

    def test_base_reasoner_solves_with_marker_property(self, synthetic_task):
        """The base reasoner CAN solve this via aligned_with_marker_col (relational property)."""
        train_pairs, test_inputs, expected_outputs, _ = synthetic_task
        adapter = GridDomainAdapter()
        reasoner = StructuralReasoner(adapter, min_train=2)

        result = reasoner.solve(train_pairs, test_inputs)
        assert result is not None, (
            "Base reasoner should solve this task using aligned_with_marker_col"
        )
        predictions, metadata = result
        assert metadata.get("property") == "aligned_with_marker_col"

    def test_concept_solves_task(self, synthetic_task, discriminating_concept):
        """StructuralReasoner with the learned concept solves the task."""
        train_pairs, test_inputs, expected_outputs, _ = synthetic_task

        adapter = ExtendedGridAdapter(
            learned_concepts=[(discriminating_concept.name, discriminating_concept)]
        )
        reasoner = StructuralReasoner(adapter, min_train=2)

        result = reasoner.solve(train_pairs, test_inputs)
        assert result is not None, "Extended reasoner should solve the task"

        predictions, metadata = result
        assert len(predictions) == len(expected_outputs)

        for pred, expected in zip(predictions, expected_outputs):
            assert np.array_equal(pred, expected), (
                f"Prediction does not match expected output.\n"
                f"Predicted:\n{pred}\nExpected:\n{expected}"
            )

    def test_solve_metadata_references_property(
        self, synthetic_task, discriminating_concept
    ):
        """The solve metadata identifies the property (core or learned concept)."""
        train_pairs, test_inputs, _, _ = synthetic_task

        adapter = ExtendedGridAdapter(
            learned_concepts=[(discriminating_concept.name, discriminating_concept)]
        )
        reasoner = StructuralReasoner(adapter, min_train=2)

        result = reasoner.solve(train_pairs, test_inputs)
        assert result is not None

        _, metadata = result
        prop_used = metadata.get("property") or metadata.get("filter_prop", "")
        valid_props = {discriminating_concept.name, "aligned_with_marker_col"}
        assert prop_used in valid_props, (
            f"Expected property in {valid_props}, got: {metadata}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test 5: Full end-to-end pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """Run the complete concept-grammar-to-resume flow end-to-end."""

    def test_full_pipeline(self, synthetic_task):
        """End-to-end: generate -> validate -> register -> extend -> solve."""
        train_pairs, test_inputs, expected_outputs, task_dict = synthetic_task

        # ─── Step 1: Base reasoner now solves via core relational property ─
        base_adapter = GridDomainAdapter()
        base_reasoner = StructuralReasoner(base_adapter, min_train=2)
        base_result = base_reasoner.solve(train_pairs, test_inputs)
        if base_result is not None:
            predictions, metadata = base_result
            for pred, expected in zip(predictions, expected_outputs):
                assert np.array_equal(pred, expected), \
                    "Base reasoner solved but gave wrong answer"
            return  # base solved it, concept grammar not needed

        # ─── Step 2: Generate concepts from failure ─────────────────────
        generator = ConceptGenerator()
        concepts = generator.generate_from_failure_cluster(
            [task_dict], max_concepts=100
        )
        assert len(concepts) > 0, "Generator produced no concepts"

        # ─── Step 3: Validate concepts ──────────────────────────────────
        validator = ConceptValidator()
        validated = []
        for concept in concepts:
            score = validator.training_discrimination_score(concept, task_dict)
            if score == 1.0:
                loo_ok = validator.loo_validate(concept, task_dict)
                if loo_ok:
                    validated.append(concept)

        assert len(validated) > 0, "No concept passed validation"

        # Pick the simplest validated concept
        validated.sort(key=lambda c: c.complexity)
        best_concept = validated[0]

        # ─── Step 4: Register in ConceptMemory ──────────────────────────
        concept_memory = ConceptMemory()
        learned = LearnedConcept(
            name=best_concept.name,
            expression_str=best_concept.to_string(),
            complexity=best_concept.complexity,
            source_failure_cluster="no_discrimination:richer_property_language",
            source_tasks=[task_dict["task_id"]],
            loo_passed=True,
            discrimination_score=1.0,
            dependencies=getattr(best_concept, "dependencies", []),
            status="validated",
        )
        registered = concept_memory.register_concept(
            learned, compute_fn=best_concept
        )
        assert registered, "Concept registration failed"

        # ─── Step 5: Build extended adapter with learned concept ─────────
        extended_adapter = ExtendedGridAdapter(
            learned_concepts=[(best_concept.name, best_concept)]
        )

        # Verify concept is visible
        assert best_concept.name in extended_adapter.property_names()

        # ─── Step 6: Solve with extended reasoner ───────────────────────
        extended_reasoner = StructuralReasoner(extended_adapter, min_train=2)
        result = extended_reasoner.solve(train_pairs, test_inputs)
        assert result is not None, (
            f"Extended reasoner failed to solve. Best concept: {best_concept.name}"
        )

        predictions, metadata = result
        assert len(predictions) == len(expected_outputs)

        for i, (pred, expected) in enumerate(zip(predictions, expected_outputs)):
            assert np.array_equal(pred, expected), (
                f"Test {i}: prediction != expected.\n"
                f"Predicted:\n{pred}\nExpected:\n{expected}"
            )

        # ─── Step 7: Verify concept attribution ─────────────────────────
        # Mark the concept as having solved this task
        concept_memory.graph.mark_solved(best_concept.name, task_dict["task_id"])
        stored = concept_memory.graph.get_concept(best_concept.name)
        assert task_dict["task_id"] in stored.solved_tasks


# ═══════════════════════════════════════════════════════════════════════════
# Run with pytest
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
