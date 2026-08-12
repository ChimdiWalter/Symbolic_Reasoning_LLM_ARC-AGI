# Proof-Carrying Domain Morphism Learning

## Section for Manuscript Extension

### Motivation

The cumulative reasoning architecture demonstrated bounded operator invention and transfer on ARC tasks, but four mechanisms remained weak: AdapterGenesis (0 synthesized solves), memory growth (0 memory-assisted solves), neural/VLM proposals (0 verified promotions), and cross-domain transfer (limited to 2/20 zero-shot transfers in one operator family). These mechanisms lacked a unifying formal structure.

We introduce *typed domain morphisms* as a single verifiable abstraction that gives each mechanism a principled role:

- **AdapterGenesis** becomes a domain-signature compiler.
- **Memory** becomes a proof-carrying operator-schema library.
- **Neural/VLM** becomes a morphism proposer (advisory, not authoritative).
- **Cross-domain transfer** becomes morphism-mediated operator instantiation with certificate emission.

### Definitions

A **domain signature** $\Sigma_D = (T_O, T_R, T_F, H)$ consists of object types $T_O$, relation types $T_R$, feature types $T_F$, and operator hooks $H$.

A **domain morphism** $\phi: \Sigma_A \to \Sigma_B$ maps:
- Object types: $\phi_O: T_O^A \to T_O^B$
- Relation types: $\phi_R: T_R^A \to T_R^B$ (arity-preserving)
- Feature types: $\phi_F: T_F^A \to T_F^B$ (dtype-compatible)
- Operator hooks: $\phi_H: H^A \to H^B$

An **abstract operator schema** $S = (\text{inputs}, \text{outputs}, \text{rel}, \text{feats}, \text{pre}, \text{post}, \text{inv})$ can be **instantiated** in domain $D$ through morphism $\phi$ when all required types are mapped.

### Proof Obligations

Each morphism-mediated transfer must satisfy 8 categories of proof obligation:

1. **Type mapping totality**: every source type has a target mapping.
2. **Relation arity preservation**: mapped relations preserve arity.
3. **Relation locality preservation**: local relations map to local or spatial relations.
4. **Feature compatibility**: mapped features have compatible dtypes.
5. **Operator precondition preservation**: preconditions are expressible in the target domain.
6. **Operator postcondition preservation**: postconditions are expressible in the target domain.
7. **Invariant preservation**: operator invariants hold under the morphism.
8. **Ambiguity rejection**: no critical type has multiple conflicting mappings.

A **morphism certificate** records all obligation results, the morphism itself, and the operator schema it mediates. Only transfers that pass all obligations are certified.

### Results

Controlled domain-morphism experiments across 3 domain pairs (grid→graph, grid→chess, graph→molecule) and 3 abstract operator schemas (FilterByRelation, ProjectToNeighborhood, TransferFeatureByCorrespondence) produced the following results:

**Morphism certification.** 9 morphism–schema combinations were tested. 3 were certified (graph→molecule, all 3 schemas, 8/8 proof obligations passed). 6 were rejected: grid→graph and grid→chess morphisms failed the relation locality preservation obligation because spatial_neighbor (local) maps to path_connectivity or attack_pattern (global). 0 false positives were emitted.

**Memory as schema library.** A FilterByRelation schema was stored in memory after solving a grid task, retrieved by task-signature similarity when presented with a graph task, instantiated via a certified grid→graph morphism, and used to solve the graph task. 1 certificate was emitted — the first memory-assisted certified transfer in the project.

**Neural morphism proposal.** Task-signature–primed neural proposals produced 4 accepted morphisms with 0 rejected and 0 false positives. Neural modules boosted morphism scores but did not bypass the verification pipeline.

**AdapterGenesis as signature compiler.** Synthesized adapters produced domain signatures sufficient for morphism learning in 3 of 4 domains. Chess synthesis produced signatures with insufficient shared properties.

**Prior transfer reinterpretation.** 61 existing cross-domain transfers were reinterpreted through the morphism framework. 0 were certifiable (24 were valid morphisms but did not produce solves; 37 failed morphism validation). Prior transfers used direct domain realizations, not morphism-mediated abstract transfer.

**Claim audit.** Of 10 domain-morphism claims, 8 are supported, 1 is partial (cross-domain improvement adds certified pairs but does not increase prior solve rates), and 1 is an honest negative (broad automatic domain adaptation is not yet proven).

### Relationship to Prior Work

The morphism framework draws on:
- Category-theoretic program transfer (Goguen, 1991): morphisms between algebraic specifications.
- DreamCoder library learning (Ellis et al., 2021): abstraction discovery across domains.
- Analogical reasoning (Gentner, 1983): structure mapping between relational systems.

Our contribution is grounding these ideas in executable, falsifiable proof obligations rather than similarity scores or learned embeddings.

### Limitations

1. Domain signatures are extracted from hand-coded adapters, not learned from raw data.
2. Morphism proposals are symbolic and heuristic, not optimal or complete.
3. Proof obligations are bounded executable checks, not formal proofs.
4. The framework has been tested on 4 controlled domains, not arbitrary new domains.
5. Neural morphism proposal is advisory only — it cannot bypass the verification pipeline.
