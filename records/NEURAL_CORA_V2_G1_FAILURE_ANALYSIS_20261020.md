# Why the Neural-CORA v1 learned guide failed G1, and where C+H gets its advantage (20 October 2026)

**Status:** the v1 G1 pilot is FINISHED and NO-GO.
- Protocol 081c1d3; results in commit 109fcfa; `records/NEURAL_CORA_V1_PILOT_REPORT.md`.
- This record is a **post-hoc, evaluator-side analysis of that closed experiment**:
  - no training, no new arm run, no retuning;
  - the 395-task held-out pool is not re-tested;
  - it reads only saved artifacts (the models, features, rows, and the evaluator's answers file).
- Numbers: `outputs/neural_cora_v2/g1_failure_analysis/component_ranks.json` and the commands below.

## 1. The closed result (primary held-out set, 395 tasks, exact pass@2)

| arm | pass@2 |
|---|---|
| C+H@1000 (hand-designed search) | 358 |
| L1h@500 (learned, 103 hand features) | 235 |
| L1@500 (learned, frozen Qwen features) | 198 |
| C+@1000 (plain search) | 104 |
| L0s@500 (shuffled labels) | 51 |
| L0@500 (untrained) | 30 |
| native C0 | 65 |

## 2. The learned heads were not bad at single components

For each primary held-out task, the analysis took each rule of the generating program. It measured the rank of its
true selector and action under each arm's component scores, and the probability given to the right number of rules.

| arm | P(two rules), one-rule tasks | P(two rules), two-rule tasks | median rank, true selector | median rank, true action |
|---|---|---|---|---|
| C+H | 0.33 | 0.98 | 4 | 2 |
| L1 (Qwen) | 0.12 | 0.92 | 3 | 2 |
| L1h (hand) | 0.12 | 0.82 | 2 | 2 |

The learned heads predict the number of rules well, and rank the true components about as well as C+H. So the
failure is **not** that Qwen's features could not identify the parts.

## 3. They failed at composing the parts

This is the position in each arm's enumeration at which the correct test output first appeared. It comes from the
saved `pred_at` and the answers.

| arm (run to) | one-rule tasks found / 215 | median position | two-rule tasks found / 180 | median position |
|---|---|---|---|---|
| C+H (3000) | 215 | 59 | **179** | 216 |
| L1 (3000) | 201 | 72 | **91** | 844 |
| L1h (1000) | 160 | 22 | 101 | 93 |

On one-rule tasks, L1 is close to C+H. On **two-rule compositions**, L1 finds the correct program for only half the
tasks, even with 3000 candidates, and late when it does.

**The cause is structural.**
- The v1 guide scores each component *independently*: view, number of rules, a bag of selectors, a bag of actions.
- The enumerator orders a program by the *sum* of its component scores.
- So the guide cannot express:
  - which selector belongs with which action;
  - which rule comes first (native rules are first-match, so order changes meaning);
  - that "recolour" goes with "colour a" and "line" with "colour b".
- Every pairing of high-scoring parts is tried before the right one. Competitors multiply as the square of the bag
  sizes. A small error in one component's tail ranks pushes the joint program past the budget.

## 4. Where C+H gets its advantage

C+H (`cora_neural_v1/space.py`, `change_kinds` and `heuristic_scores`) reads the demonstrations by **explicit
object correspondence**. Every input object is matched to the output:
- unchanged;
- recoloured, recording the target colour;
- moved, recording the exact displacement vector;
- deleted;
- full-row or full-column added lines.

It then:
- adds bonuses to exactly the observed recolour targets, vectors and source colours and sizes;
- switches to two-rule programs first when two kinds of change are observed.

That is per-task, demonstration-specific **inverse reasoning**. It is computed fresh for each task and never
learned, so it transfers to new pairings by construction. The held-out families are exactly new pairings.

**Two further facts:**
- C+H was designed by the same researcher as the generator. It was refined after one held-out-family smoke test
  (seeds 5000–5002, logged). It has a home advantage on this synthetic data.
- L1h beats L1 because its 103 hand features already contain much of this delta information: colours added, removed
  and recoloured per colour; a displacement histogram; change kinds. Mean-pooled hidden states of a grid-emitting
  model do not expose it as directly. L1 also overfits: best validation epoch 6, with 13.7 M parameters on 3,300
  tasks.

## 5. What this implies for v2

1. **Predict joint structure, not bags.**
   - Score whole rules: selector, the action bound to it, its parameters, and its slot.
   - Condition each rule on the earlier rules.
   - Train with execution-generated hard negatives that swap pairings and order.
2. **Keep C+H's correspondence evidence as a first-class input and baseline.**
   - A learned model should take the explicit correspondence evidence as input (displacements, recolour maps,
     added cells per object) and learn a residual over C+H.
   - It must beat C+H alone, and C+H plus a simple non-neural residual.
3. **Measure Qwen's incremental value honestly.** Compare a joint guide on hand features alone with the same guide
   on hand features plus Qwen token-level features.
4. **Expressivity comes first for real tasks.**
   - All of the above is about ordering a language that already covers 394 of 395 synthetic tasks.
   - On 60 exposed real ARC tasks, the v1 language fitted 1. That is an observed result at the tested budget, not a
     proof that the other 59 cannot be expressed.
   - Hence G2 (`records/NEURAL_CORA_V2_G2_PROTOCOL_20261020.md`) before any further learning.

## Reproduction

The analysis code is in the commit that adds this record. Its inputs:
- `outputs/neural_cora_v1/models/{L1,L1h}.pt`;
- `features/eval_heldout_{qwen,hand}.npy`;
- `rows/eval_heldout.jsonl`;
- `evaluator/eval_heldout_answers.jsonl`;
- `audit/eval_heldout_primary.json`.

It is written in `scripts/neural_cora_v2_g1_failure_analysis.py`.
