# Adapter card: T1, circuit and access-control logic recovery

The adapter plugs logic recovery into CORA's reasoning loop by supplying the domain's building blocks, its checker and
its failure description. This card says what was reused and what was rebuilt.

## The adapter's parts

| Part | Circuits (real) | Policies (synthetic from real seeds) |
|---|---|---|
| Building blocks | constants, literals and every two-input gate (all 16 tables of every input pair) | field tests: address prefixes (lengths 1 to 3), one protocol code, port-code intervals; base rules test one field |
| Program | a cofactor tree: `IF x_v then A else B`, with blocks at the leaves | a first-match list of (rule, permit or deny) with a default |
| Checker | the program's truth table must equal every probe label; scoring then compares the full truth table with the target | the same |
| Failure description | the inputs implicated by the closest conflicting probe pairs: witness edges (two probes one input apart with different labels, which certify the input as essential), else pairs two or three inputs apart | the field implicated by the closest conflicting probe pairs (those differing in the fewest fields) |
| Missing piece | a Shannon cofactor split on the implicated input, with both halves solved by the same loop | the best pure rule over the fewest fields that include the implicated field; its field set joins the library as a template |
| Selection rule | smallest block first (constant, then literal, then gate), then the most witness evidence on its inputs, then canonical order. Unobserved cells and empty halves take the majority label of the nearest observed node | the pure rule covering the most remaining probes, then fewer fields, then canonical order |
| Step 6 (keep only if it helps on held checks) | a verify flag: four-fold rebuilding must predict every left-out probe. It is reported as a secondary measure and does not gate the primary | the same |
| Shuffled control | the described input is replaced by a seeded random permutation of the free inputs | the described field is replaced by a seeded random permutation of the fields |

## Reused

- **CORA U6 statistics module** (`experiments/universality_boolean_bbm_20261103/u6/stats.py`, 88 lines, frozen in
  the U6 code freeze). It is imported read only and supplies:
  - Wilson intervals;
  - the cluster bootstrap (10,000 resamples, default_rng(0));
  - Holm's procedure.
- **Design of the companion's sparse cofactor engine**
  (`<companion study folder>/cofactor_capability_growth_20261107_v1/engine.py`, 237 lines, read only).
  Three ideas come from it:
  - the two-input leaf bank;
  - witness edges as certificates of essential inputs;
  - Shannon cofactor growth on a certified input, with a shuffled-routing control.
- **CORA's Boolean-rule selection** (U6 arm W): the smallest fitting rule first.

## Rebuilt

The companion engine was re-implemented rather than imported:
- its fixture contract allows only 2 to 6 inputs and depth 2 at most;
- its leaf bank enumerates input tuples, which is too slow at 12 inputs.

The new core (`tlogic/core.py`, 227 lines) works on truth tables stored as integers. It adds:
- conflict pairs two and three inputs apart, for nodes with no witness edge;
- growth to any depth;
- majority filling of unobserved cells.

## Lines of code

| File | Lines | Role |
|---|---|---|
| tlogic/core.py | 227 | Boolean core: blocks, witness and conflict counts, cofactor growth |
| tlogic/policy.py | 373 | policy header space, seed parser and generator, decision-list learners |
| tlogic/pla.py | 123 | PLA reader and circuit items |
| tlogic/arms.py | 126 | arms, probes, exact check, verify flag, active probing |
| tlogic/classical.py | 83 | references: two-level minimisation with don't-cares, CART |
| tlogic/data.py | 73 | item pools and the development or held split |
| tlogic/stats.py | 57 | McNemar test and paired comparisons over the reused U6 module |
| score_held.py | 179 | the one scored run, with its GO, freeze, hash and version checks |
| make_freeze.py | 40 | writes FREEZE.json |
| **Adapter total** | **1,281** | |
| u6/stats.py | 88 | reused CORA core, imported |
| cofactor engine | 237 | companion core, design reused, not imported |

The domain-specific part is small:
- the PLA reader;
- the policy header space and generator;
- the two failure descriptions.

Most of the adapter's lines are custody, the references and the policy generator.
