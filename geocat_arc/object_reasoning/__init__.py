"""Object-level program induction (Stage 1, STAGE1_REQUIREMENTS.md).

Layering (imports may only flow downward):

    types.py                          <- dependency root (no intra-package deps)
    features.py, segmentation.py      <- types
    expressions.py                    <- types, features
    correspondence.py                 <- types
    actions.py                        <- types, expressions
    inducer.py                        <- types (+ calls segmentation/features/
                                         expressions/correspondence/actions
                                         through their declared APIs)
    memory.py                         <- types
    engine.py                         <- types, inducer, memory (harness facade)

Hard constraints (Section 6): no task-ID branches; no hand-coded
task-specific solvers; LOO-by-reinduction is the only acceptance gate;
accepted programs serialize to inspectable JSON; near-solves are recorded.
"""
from .types import (
    SegmentationVariant,
    SEGMENTATION_TRIAL_ORDER,
    DeltaType,
    ParameterClass,
    FailureStage,
    FeatureKind,
    ExprType,
    Expr,
    MultiColorObject,
    GridContext,
    SegmentationResult,
    ObjectFeatures,
    FeatureTable,
    ObjectDelta,
    PairCorrespondence,
    SelectorRule,
    ActionRule,
    ObjectRule,
    OutputSpec,
    ObjectProgram,
    ComposedProgram,
    program_from_dict,
    LOOReport,
    InductionResult,
    NearSolveRecord,
    ProgramCertificate,
    LibraryOperator,
    to_grid_pairs,
)
from .engine import ObjectReasoningEngine, ObjectReasoningResult, ObjectSolution
from .inducer import InductionConfig, induce_program, loo_validate, certify
from .memory import FragmentLibrary, NearSolveStore, promote_fragments

__all__ = [
    # types
    "SegmentationVariant", "SEGMENTATION_TRIAL_ORDER", "DeltaType",
    "ParameterClass", "FailureStage", "FeatureKind", "ExprType", "Expr",
    "MultiColorObject", "GridContext", "SegmentationResult", "ObjectFeatures",
    "FeatureTable", "ObjectDelta", "PairCorrespondence", "SelectorRule",
    "ActionRule", "ObjectRule", "OutputSpec", "ObjectProgram",
    "ComposedProgram", "program_from_dict", "LOOReport",
    "InductionResult", "NearSolveRecord", "ProgramCertificate",
    "LibraryOperator", "to_grid_pairs",
    # engine
    "ObjectReasoningEngine", "ObjectReasoningResult", "ObjectSolution",
    # inducer
    "InductionConfig", "induce_program", "loo_validate", "certify",
    # memory
    "FragmentLibrary", "NearSolveStore", "promote_fragments",
]
