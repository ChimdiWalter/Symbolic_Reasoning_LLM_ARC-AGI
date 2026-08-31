"""CORA-PARENT: interface stubs for certified cognitive architecture plasticity.

STUBS ONLY (docs/CORA_PARENT_ARCHITECTURE.md deliverable 5). Nothing here is wired
into any running system, performs I/O at import, or references any frozen artifact.
The isolation test (tests/test_cora_parent_isolation.py) mechanically bans this
package from naming or reading every sealed artifact of the running experiment;
see docs/CORA_DATA_ACCESS_DAG.md for the full access contract.
"""
from cora_parent.interfaces import (  # noqa: F401
    Extension,
    FailureLocalizer,
    GrammarProposalNetwork,
    MetaExtensionEngine,
    MicroLanguage,
    ReasoningWorldModel,
    SemanticArchive,
    TypedFailureGraph,
)
