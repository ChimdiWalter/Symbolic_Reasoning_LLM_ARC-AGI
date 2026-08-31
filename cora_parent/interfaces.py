"""Abstract interfaces for the CORA-PARENT architecture (stubs; no implementations).

Design contract (docs/CORA_PARENT_ARCHITECTURE.md, docs/CORA_COGNITIVE_PLASTICITY_THEORY.md):

- The VERIFIER is immutable and lives OUTSIDE these interfaces: nothing here defines,
  wraps, or parameterizes certification. Implementations receive verifier *callables*
  owned by the frozen runtime and may only invoke them.
- Proposers and world models PRIORITIZE; only the immutable verifier CERTIFIES.
- No implementation may accept task identities, family labels, or hidden-corpus
  statistics as inputs (see docs/CORA_DATA_ACCESS_DAG.md).
- This module performs no file I/O and imports only the standard library.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Hashable, Mapping, Sequence, TypeVar

Obs = TypeVar("Obs")          # domain observation (e.g. a demonstration pair)
View = TypeVar("View")        # a representation/view over observations
Type_ = TypeVar("Type_")      # a domain type object
Expr = TypeVar("Expr")        # an expression/program in the domain language
Ext = TypeVar("Ext")          # a candidate extension (production/view/learner/...)

#: Latent failure causes for cognitive localization (frozen vocabulary).
FAILURE_CAUSES = ("PERCEPTION", "REPRESENTATION", "SEMANTICS", "PARAMETER_LEARNING",
                  "SEARCH", "CONTROL", "MEMORY", "COMPOSITION", "RESOURCE_LIMIT")


@dataclass(frozen=True)
class Extension:
    """A typed candidate self-modification, always certificate-carrying.

    kind is one of: "production", "view", "learner", "relation", "composition_rule".
    payload is a domain-plugin AST/sketch; provenance records how it was proposed
    (never a task identity).
    """
    kind: str
    signature: str
    payload: Any
    mdl: float
    provenance: Mapping[str, Any] = field(default_factory=dict)


class TypedFailureGraph(abc.ABC):
    """Domain-general mechanistic failure representation (a typed graph/hypergraph).

    Encodes only mechanism: frontier nodes, types, goal type, frontier values, delta
    signatures, shape/cardinality/palette changes, relation changes, repeated
    substructure, slot fit/fail, non-exact executions, type paths, causal dependencies,
    verifier failure class. NEVER task identity, family labels, or prose.
    """

    @abc.abstractmethod
    def nodes(self) -> Sequence[Hashable]: ...

    @abc.abstractmethod
    def edges(self) -> Sequence[tuple[Hashable, str, Hashable]]: ...

    @abc.abstractmethod
    def interface(self) -> tuple[str, str]:
        """(frontier type, goal type) — the only cluster-level generation input."""

    @abc.abstractmethod
    def canonical(self) -> str:
        """Deterministic serialization for hashing/dedup (sorted, stable)."""


class FailureLocalizer(abc.ABC):
    """Cognitive Failure Localization: q(z | F) over FAILURE_CAUSES.

    Trained ONLY on self-supervised cripple corpora (docs/CORA_DATA_ACCESS_DAG.md);
    the diagnosis routes which component of A may be modified. It never modifies
    anything itself.
    """

    @abc.abstractmethod
    def localize(self, failure: TypedFailureGraph) -> Mapping[str, float]:
        """Return a distribution over FAILURE_CAUSES (keys ⊆ FAILURE_CAUSES)."""


class GrammarProposalNetwork(abc.ABC):
    """Failure-conditioned semantic proposer: q(e | TFG, interface). Non-LLM.

    Must not predict answer grids, consume text corpora, or see task identities.
    Output order is a PRIORITY; certification authority stays with the verifier.
    """

    @abc.abstractmethod
    def propose(self, failure: TypedFailureGraph, top_k: int) -> Sequence[Extension]: ...


class ReasoningWorldModel(abc.ABC):
    """Semantic dynamics model W: (K, F, e) -> predicted next failure state.

    Predicts consequences of modifying the reasoning system — never domain answers.
    May rank and prune candidate extensions and plan multi-step language moves;
    may never certify (its scores are advisory)."""

    @abc.abstractmethod
    def predict(self, language_fingerprint: str, failure: TypedFailureGraph,
                extension: Extension) -> Mapping[str, float]:
        """Return advisory scores, e.g. {"p_failure_reduced": ..., "p_certifiable": ...}."""


class MicroLanguage(abc.ABC):
    """Ephemeral task-local language G_j (Certified Micro-Language Induction).

    Lifecycle contract: created from a frozen K_global fingerprint; extensions may be
    added ONLY with their certification artifacts attached; MUST be discarded at task
    end (reset rule) — implementations expose discard() and forbid persistence of any
    uncertified or unsanitized content."""

    @abc.abstractmethod
    def base_fingerprint(self) -> str: ...

    @abc.abstractmethod
    def extend(self, extension: Extension, certificate: Mapping[str, Any]) -> None: ...

    @abc.abstractmethod
    def extensions(self) -> Sequence[Extension]: ...

    @abc.abstractmethod
    def discard(self) -> None:
        """Destroy all task-local extensions; the next task starts from K_global."""


class SemanticArchive(abc.ABC):
    """Sanitized stepping-stone / grammar-variant archive (language-level near-solves).

    Stores ONLY: type signature, normalized semantics, proven local property, failure
    reduced, provenance, transfer/falsification history, MDL, behavioral fingerprint.
    NEVER answer grids or task identifiers. Admission requires a certified local
    property; retention follows the lifecycle ephemeral -> probationary -> global ->
    consolidated -> deprecated."""

    @abc.abstractmethod
    def admit(self, extension: Extension, certified_property: Mapping[str, Any]) -> str: ...

    @abc.abstractmethod
    def query(self, interface: tuple[str, str]) -> Sequence[Extension]: ...

    @abc.abstractmethod
    def consolidate(self) -> Mapping[str, Any]:
        """Anti-unify/compress related entries; report retirements. No deletions of
        evidence — deprecation is recorded, never silent."""


class MetaExtensionEngine(abc.ABC, Generic[Obs, View, Type_, Expr, Ext]):
    """Domain-independent certified self-extension engine (ARC is one plugin).

    The verifier/executor callables are supplied by the immutable runtime; the engine
    orchestrates and may never redefine them. Hooks mirror
    docs/CORA_PARENT_ARCHITECTURE.md Idea 11."""

    # -- domain hooks (plugin supplies) ------------------------------------
    @abc.abstractmethod
    def build_views(self, observations: Sequence[Obs]) -> Sequence[View]: ...

    @abc.abstractmethod
    def build_entities(self, view: View) -> Sequence[Any]: ...

    @abc.abstractmethod
    def search(self, observations: Sequence[Obs], language_fingerprint: str) -> Any: ...

    @abc.abstractmethod
    def execute(self, expression: Expr, observation: Obs) -> Any: ...

    @abc.abstractmethod
    def verify(self, expression: Expr, observations: Sequence[Obs]) -> Mapping[str, Any]:
        """Invoke the IMMUTABLE verifier; implementations must delegate, not decide."""

    @abc.abstractmethod
    def trace_failure(self, search_state: Any,
                      observations: Sequence[Obs]) -> TypedFailureGraph: ...

    # -- meta hooks (engine-level) -----------------------------------------
    @abc.abstractmethod
    def localize_failure(self, failure: TypedFailureGraph) -> Mapping[str, float]: ...

    @abc.abstractmethod
    def propose_extension(self, failure: TypedFailureGraph, cause: str,
                          top_k: int) -> Sequence[Ext]: ...

    @abc.abstractmethod
    def fit_extension(self, extension: Ext, observations: Sequence[Obs]) -> Ext | None: ...

    @abc.abstractmethod
    def falsify_extension(self, extension: Ext) -> Mapping[str, Any]:
        """Synthetic falsification battery (positives, near-misses, adversarial)."""

    @abc.abstractmethod
    def separate_extension(self, extension: Ext,
                           language_fingerprint: str) -> Mapping[str, Any]:
        """Separation certificate vs the pre-extension language."""

    @abc.abstractmethod
    def promote_extension(self, extension: Ext,
                          transfer_evidence: Mapping[str, Any]) -> bool:
        """Durable admission — only through held-out transfer + causal necessity."""

    @abc.abstractmethod
    def consolidate_memory(self) -> Mapping[str, Any]: ...


# Callable aliases documenting the immutable boundary: implementations receive these
# from the frozen runtime and may only call them.
VerifierFn = Callable[..., Mapping[str, Any]]
ExecutorFn = Callable[..., Any]
