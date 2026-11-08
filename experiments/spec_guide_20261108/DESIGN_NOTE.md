# Specification-reading guide test: design note before development

Written 8 Nov 2026, 05:04Z. It was committed before any data of this test existed. It fixes what development may
touch and what stays held. The protocol (`PROTOCOL.md`) comes later and is committed and frozen before the GO;
where it is more specific, it governs.

## The question

The object-level step searches blocks (a view, and an edit or a form) in an order. In the learned search-order test
(`experiments/guided_construction_20261106/`) a small guide was trained on coarse features of each block. On the
held tasks at 500 counted operations it scored 320, a static frequency table 318 and a linear model 323: the learned
order was no better than simple statistics.

This test asks whether a **learned, specification-reading guide** does better than the frequency table at a binding
budget, and whether it generalises to families it was not trained on. Such a guide reads a failure's full
specification: the input and target grid pairs that the missing operation must map. It predicts which operation
family to try first.

This is a step toward the question of neural guidance for program synthesis, not an answer to it. The precedents
are:
- DeepCoder: learned attribute prediction steering enumerative search;
- RobustFill: neural program induction and synthesis from examples;
- BUSTLE: learned bottom-up search guidance;
- CrossBeam and LambdaBeam: neural search policies over a bottom-up search;
- neural-guided deductive search (NGDS).

## Families and partitions

A generated task applies one operation of the object step's own language to the input grids of one public training
task. The operation is a paint rule (a predicate and an edit, in one of the 12 views) or a crop.

- **Its family** is the string `edit type | edit parameters | predicate kind | view`. The predicate kind is the
  atom's name, without its value, and "not:" for a negation.
- **Family partition:** the family's partition is `int(sha256("spec-family:" + family)[:8], 16) % 10`:
  - 0 to 5 is training;
  - 6 and 7 is validation (development only);
  - 8 and 9 is **held**.
- **Grid pools:** each ARC-AGI-2 public training task (`outputs/score_first/data/arc-agi_training_challenges.json`,
  sha256 779eaba8...) goes to the **development pool** when `int(sha256("spec-pool:" + id)[:8], 16) % 2 == 0`, and
  to the **held pool** otherwise. Only input grids are used, and their solutions are never read.
- **Held tasks** come only from held families on held-pool grids. They are generated after the GO, from a seed taken
  from the GO file's sha256. Before the GO, no operation of a held family and no grid of the held pool is generated or
  used.
- **Natural tasks:**
  - The 425 source units of the earlier tests are used for training and validation only.
  - They are split by benchmark family: `int(sha256("spec-natural:" + family)[:8], 16) % 5 == 0` is validation.
  - Mini-ARC has a single family, so its units are split by task id with the same rule.
  - The held halves of ConceptARC, Mini-ARC and 1D-ARC are consumed and are not used.

## Development

- Development trains on the training partitions and the development pool only. It is judged on the validation
  partitions and the validation natural units, never on held data.
- It iterates on the inputs, augmentation, data scale, heads and training until the specification-reading guide
  clearly beats the frequency table on validation, or development ends at about 18:00Z.
- Validation measures are:
  - the operation family's top-1 and top-k accuracy;
  - simulated correct outputs at 125 and 500 counted operations, from traces of the frozen step.
- Development reports are sent at about 12:00Z and 16:00Z.
- If development cannot beat the frequency table, no test that expects a win is frozen. What the model learned, and
  what is missing from the specification, is reported instead.

## Compute and custody

- **Compute:** CPU through `scripts/with_cpu_slot.sh` at nice 19, or GPU 0 only, under the project's lock
  (`outputs/locks/gpu0.lock`) and `CUDA_VISIBLE_DEVICES=0`. Never GPU 1. Step B and other projects' job folders are never touched.
- **Custody, in order:**
  1. the protocol and the freeze;
  2. our reviewer's pre-run review;
  3. a GO written by the coordinator;
  4. the held run, detached;
  5. predictions sealed before scoring;
  6. one scoring;
  7. a post-score audit.
