# Neural-CORA v1 learning-data audit (19 October 2026)

**Command:** `python -m cora_neural_v1.pilot audit` (`cora_neural_v1/audit.py`).

**Output:** `outputs/neural_cora_v1/audit/data_audit.json`, sha256
`075e8b64309e956f86bf888af2560bd7a3bd86fefc8bde5874a2c4f9e054bdb2`.

**How it ran:** on the generator side, before any training or arm run. It regenerates every task deterministically
and reads no answers file. It took 204 CPU-seconds.

## 1. What the earlier 880 / 110 / 110 / 11 counts were

Those were the **engineering corpus** (`NEURAL_CORA_DEV=1`). It used training families only:

| split | seeds | families | tasks |
|---|---|---|---|
| train | 10000–10079 | 11 TRAIN | 880 |
| val | 11000–11009 | 11 TRAIN | 110 |
| eval_iid | 12000–12009 | 11 TRAIN | 110 |
| eval_heldout | 12100 | the 11 TRAIN families (no held-out family) | 11 |

- They had only 417 distinct program instances among the 880 training tasks.
- They were used only for engineering checks: timing, the code path, the smoke tests. They are not the pilot's data,
  and no result is claimed from them.

## 2. The pilot corpus (generator `ncv1-gen0`, CORA's own; no third-party data)

| split | families | seeds | tasks | distinct program instances | composition signatures |
|---|---|---|---|---|---|
| train | 11 TRAIN | 0–299 | 3300 | 998 | 11 |
| val | 11 TRAIN | 1000–1029 | 330 | 200 | 11 |
| eval_iid | 11 TRAIN | 2000–2019 | 220 | 144 | 11 |
| eval_heldout | 7 HELD-OUT | 3000–3059 | 420 | 302 | 7 |

- No seed failed to produce a task: missing = 0 in every split.
- A **program instance** is a canonical typed program, `Hypothesis.program_sha`. Families resample colours, sizes,
  vectors, directions and axes, so instances repeat inside a family.
- A **composition signature** is the selector type and action type of each rule, plus the default.

## 3. Execution validity and output semantics

The audit re-runs every generating program through the native interpreter on every demonstration and test.

**Results:**
- 0 execution problems in 4270 tasks: every stored output is reproduced, and no pair leaves the grid unchanged.
- No output changes the grid shape; every family preserves it.

**Generator rules that also hold:**
- Objects never touch, so all native connectivity views agree.
- Each non-trivial selector picks some objects but not all.
- In two-rule tasks, both rules fire in at least two demonstrations and in the test.
- Moved objects stay in the grid and overlap nothing.

## 4. Split disjointness and leakage

**Exact duplicate tasks** (identical demonstrations and test input): **0** across all six split pairs.

**Composition signatures:** **0** of the held-out signatures occur in training. The held-out families are new
selector–action pairings: line by size; slide by colour; delete the largest; recolour-then-line;
slide-then-recolour; delete-then-translate; line with the default delete. None uses a component value class that
training lacks.

**Program instances shared across splits:**
- train and eval_iid share 105, and train and val share 135. That is expected in-distribution: an IID task is a new
  random scene for a program the training set may contain.
- The held-out split shares **0** instances with any other split.

**Template aliases.** These are aliases that cross the train/held-out boundary. A held-out task is template-aliased if
a program with a TRAIN family's structure, under any parameters in the task's pruned domains, reproduces all of its
demonstrations. Such a task could be solved without composing anything new.
- 25 of 420 held-out tasks are aliased:
  - **H_delete_largest:** 16 of 60. A delete-by-size template fits, because the largest object is the only one of its
    size. 3 of these also fit recolour-then-delete.
  - **H_line_by_size:** 9 of 60. A line-by-colour template fits.
  - The other five families: 0.
- They are **excluded from the primary held-out set**, which is 395 tasks
  (`audit/eval_heldout_primary.json`, sha256 `8f647512d0ecaa72b567d28ae87e3b6ff29a921f4054a2eec73cc4f7433fa6f1`).
  They are reported separately.
- This was fixed before any arm ran (protocol 081c1d3).

## 5. Label aliasing inside training (component-level equivalence)

The targets are **extensional**. For each rule, every selector and every action that can be swapped into the
generating program while still reproducing every demonstration counts as correct. Every view that reproduces them
counts too. Syntactic aliases are grouped, not penalized.

The mean number of valid alternatives per task is recorded in `manifest.json` `targets`; see the addendum below. The
primary metric is exact output correctness, which no alias can game: an alias that predicts the same test output is
equally correct.

**Addendum (measured, `manifest.json` `targets`):**

| split | tasks | valid selectors per task | valid actions per task | valid views per task (of 7) | sha256 |
|---|---|---|---|---|---|
| train | 3300 | 1.496 | 1.678 | 5.429 | `157c7717…` |
| val | 330 | 1.506 | 1.776 | 5.418 | `b6fab326…` |

- Selector and action labels are close to unique.
- Views alias heavily (about 5.4 of 7 per task), because generated objects never touch and so most connectivity views
  agree. The view head therefore carries little signal. That is expected, and not a defect.

**Feature costs (measured):**
- Qwen3-4B on one RTX 2080 Ti: 0.30 s per task (train 985 s for 3300 tasks); about 795 tokens per task; peak GPU
  memory 7.51 GB.
- Hand features: 103 values per task, on CPU.

## 6. Exposure and licences

- **No ARC task.** No NVARC synthetic program text: it is unlicensed, and its seeds cover the public splits.
- **The encoder.** The NVARC Qwen3-4B checkpoint (Apache-2.0) was pretrained by NVARC on ARC-like data. Its features
  may encode general grid knowledge. The synthetic tasks here are new, CORA-generated, and never part of its training.
- **Development exposure:**
  - the engineering checks used TRAIN families only;
  - one earlier symbolic-arm smoke test touched held-out families at seeds 5000–5002 (9 tasks). Those seeds are not
    used, and that exposure could only favour the symbolic control C+H.

## 7. Limits of this data (the claim ceiling)

**What it covers:**
- a small typed language;
- simple scenes of non-touching single-colour objects;
- 3 demonstrations per task;
- shape-preserving transformations.

**What it does not test:**
- new primitives;
- part-level or relational structure;
- size changes;
- multicolour objects;
- real ARC difficulty.

A G1 result on this corpus is evidence about **learned search guidance within this language**, nothing more.
