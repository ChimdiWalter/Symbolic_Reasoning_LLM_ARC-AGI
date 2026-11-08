# T3 adapter card: enzyme reaction rules from a few examples

Label: real data; reconstruction of known enzyme transformations on held substrates, not discovery.

## What the adapter supplies

| part of the loop | chemistry version | code |
|---|---|---|
| building blocks | forward reaction rules (main substrate to main product) written as RDKit reaction patterns; the static library is the 1,224 published generalized rules of Ni et al. 2021 (1,789 single-substrate variants) | `t3chem/library.py`, `t3chem/chem.py` |
| propose | the library rule with the most exact products on the k examples (then most products covered, then fewest outcomes, then name) | `arms.static_proposal` |
| checker | apply the rule to a substrate and compare canonical SMILES (stereo removed): a hit needs the true product and nothing else | `chem.apply_rule`, `arms.exact` |
| failure description | the reaction centre of each example: atoms whose bonds, charge, hydrogens or aromaticity change, bonds broken to atoms that leave, and atoms added from a co-substrate | `chem.reaction_centre`, `chem.describe_centre` |
| build | a rule cut from the observed centre at seven fixed specificity levels, from L0 (changed atoms, element and aromatic flag) to L6 (radius 2, element, aromaticity, charge, hydrogens, degree, ring); the first single example rule that reproduces every check example, else the union of the example rules | `chem.extract_rule`, `arms.build` |
| keep (selection rule) | among levels whose piece reproduces all k examples, the one with the most leave-one-out exact predictions (ties: the more general level, chosen on development: 85 of 155 development targets against 81 of 155 for the more specific level); kept only if that count is greater than the static rule's exact count on the k | `arms.grow` |

Hydrogens: a built rule carries the observed change in hydrogen count and charge of each centre atom and writes
added atoms in full; a library rule carries no hydrogens, so the hydrogens of its changed atoms follow valence.

## Arms

- **static:** propose and check only.
- **grown:** the whole loop. When the static rule already gives the exact product on all k examples it is kept
  and nothing is built.
- **shuffled control:** the grown arm, but the build step receives the observed change (examples) of another
  family with a different EnzymeMap rule id; the checks still use the family's own k examples.
- **nearest neighbour (classical reference):** for each held substrate, the L4 rule of the most similar example
  (Morgan radius 2, 2,048 bits, Tanimoto), backing off to the next most similar example when it does not match.

## What was reused and what was rebuilt

- **Reused:** the loop design of the transfer claim (propose, check, describe, build, check again, keep on held
  checks); the leave-one-out acceptance idea of T2; the salted-hash split and custody pattern of
  `experiments/natural_growth_20261105`; the shared CPU slots (`scripts/with_cpu_slot.sh`) and the ledger.
- **Rebuilt:** everything that touches molecules. The existing cores work on grids, one-row puzzles, lists and
  Boolean networks; none of their code applies to molecular graphs, so no core module is imported.
- **Lines of code:** adapter 569 (`chem.py` 348, `library.py` 68, `arms.py` 153); runner, pool builder and
  statistics 329 (`run.py` 160, `build_items.py` 106, `stats.py` 63); reused core code imported: 0 lines.
- **Dependencies:** RDKit 2026.03.2 from `<python environment>` only. No package was installed.
