# Item-2 protocol errata (naming only; the frozen artifacts are unchanged)

E1 (2026-09-03). Regime B is correctly named a STRUCTURAL-FAMILY HOLDOUT,
not a "root-constructor-family holdout": every complete program in this
grammar is rooted at Compose, and the family is defined by the tuple of
per-block selection counts, e.g. (2,) and (2,1). This is a naming erratum.
No split, seed, requirement, metric, budget, or ranking coefficient changes;
the protocol document and manifest retain their frozen hashes
(doc b9587eab..., manifest c5cfe088...).

E1 addendum (same date, same scope): typed-interface holdout (regime C)
remains DECLARED INFEASIBLE in v1 because Grid -> Grid is the only grounded
interface in this constructor language; this restates the frozen protocol's
section 3 and changes nothing.

E2 (2026-09-03, manifest v1.1 supersedes v1). The v1 machine manifest's
terminal lists (partitions, predicates, key features) serialized EMPTY: its
generator imported meta_ast without meta_induction, so register_vocabulary
had never run. The protocol DOCUMENT always specified the correct terminals
(4 partitions, 5 predicates, 10 key features); this was a mechanical
omission in the machine manifest only, discovered by the constructive
vocabulary module's own manifest-consuming validation before any dataset
row, model, or evaluation existed. Manifest v1.1 restores the terminals and
records the superseded v1 hash inside itself. No seed, split, family,
grammar rule, budget, ranking coefficient, metric, or requirement changed.
