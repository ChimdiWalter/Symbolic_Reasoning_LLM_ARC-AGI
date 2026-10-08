# Real-task reach v1: native failure census (2026-10-08)

The full native engine (sealed per-task entry, five chain flags, frozen
library and learned verbs, solution None) on the 60 training-development
tasks under the observation-only tracer. 60 of 60 rows, 0 run errors,
mean 300 s per task. Rows `outputs/reach_v1/census_rows.jsonl`, programs
`outputs/reach_v1/census_programs/`, summaries `census_summary.json`,
`divergence.json`. No target was read.

## Diagnosis (protocol section 3)

| class | tasks | usable native trace |
|---|---|---|
| DE_LOO: a demonstration-exact program whose leave-one-out fails | 27 | 27 |
| A_REPRESENTATION (matching 18, segmentation 3) | 21 | 10 |
| NATIVE_CERTIFIED | 6 | - |
| B_LANGUAGE (parameter 2, selector 1) | 3 | 0 |
| C_SEARCH | 1 | 1 |
| NO_INDUCTION | 2 | 0 |

Usable native traces 38; demonstration-exact fits 36. Native claims: the
pipeline layer emits a train-verified (uncertified) answer on 26 tasks.

## What the leave-one-out failures are

The demonstration-exact reference programs of the 27 DE_LOO tasks hold 62
rules: `grow` in the constant `pattern` mode 51, recolor 5, translate 5,
composed 3, halo 1, reduction 1. Parameter classes: constant 55,
induced map 3, feature 2, relational 2. Most rules explain one object,
with a selector on an object-specific literal (a shape hash, one colour).
Failed folds by structural signature: another signature 19, fewer rules 4,
same signature with other values 3, no fold program 1. Unexplained residual
deltas in near-solves: copy 10, keep 7, translate 3, grow 2.

Reading: when no growth mode reproduces an object's added cells, the engine
falls back to `pattern`, a constant per-object memorization (the honest
CONSTANT class); a fold without the memorized object cannot rebuild it, so
leave-one-out fails. The dominant cause is a construction-language limit in
the growth vocabulary (B), seen as leave-one-out failure; not a fitting or
adapter defect (D). Representation failures at matching (A) are the second
class. A bounded failure is not a proof of inexpressibility.

## Selected mechanism (protocol section 4 rule: largest usable class)

Growth-relation construction, native-program-grounded: keep the native
program's structure; for the objects the engine memorized with `pattern`,
construct one relation from a bounded, human-designed, generic grammar that
reproduces every memorized instance of the task from the object and the
input scene alone; verify it on the demonstrations; install it for the task
as a growth mode tried before the `pattern` fallback (context-scoped bridge,
geocat_arc unchanged); rerun the same engine; its unchanged gate decides.
The grammar and its finite limits are fixed in the protocol before the
measurement run. Representation failures are not addressed in this block.
