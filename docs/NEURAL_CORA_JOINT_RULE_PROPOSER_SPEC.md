# The joint rule proposer: a learned synthesis of complete conditional rules (specification, 20 October 2026)

**Status:** a specification. Nothing is trained, and Qwen is not fine-tuned. It refines interface A of
`docs/NEURAL_CORA_V2_QWEN_EVIDENCE_TO_PROGRAM_SPEC.md` into an explicit structured decoder.

## 1. What it must produce

**Complete conditional rules, jointly:**
- the selector (a predicate tree);
- the action (an op with typed arguments);
- parameters (colours, vectors, integers);
- object references;
- variable bindings;
- **rule order**.

v1 failed because it scored components independently (91/180 two-rule tasks vs C+H's 179/180). ncv2-g2's remaining
synthetic failures are rule *pairs* and deep references (`docs/NEURAL_CORA_V2G3_ARCHITECTURE_PROPOSAL.md`).

## 2. C+H stays the active prior

- The candidates are C+H's top-K (ncv2-g2's agenda) **∪** the decoder's beam samples.
- Every candidate is typechecked, compiled and executed by native CORA.
- **Score:** `C+H(h) + r_theta(h | state) − cost(h)`.
- The decoder adds candidates C+H never proposes, and r_theta reorders.

## 3. Inputs (inference-visible only)

- **The CORA task state:** objects per view, the 36 features, relations, and correspondence evidence (`evidence2`:
  displacements, recolours, deletions, copies, moved-and-recoloured).
- **Demonstration diff maps:** changed cells, attributed to objects.
- **Qwen object slots.** The checkpoint's per-cell token states, pooled per object. Alignment is verified (one token
  per cell). The model is causal, so slots come from the test-input segment or a tested re-read block.
- **Hand features** (the C+H features), always present, so that a hand-only model is a proper control.

## 4. The structured decoder

The checkpoint's vocabulary is 16 grid tokens and has no program vocabulary, so the decoder is a **separate head**.

**The encoder:** a set transformer (2–4 layers, d = 256) over object slots, correspondence tokens and diff tokens.

**The decoder:** autoregressive over typed AST tokens. A **grammar automaton** built from `rast.SIGNATURES` and the
`classes` schemas masks every ill-typed token, so every output is a well-typed (partial) ncv2-g2 program.

**Token types:**
- `RULE_START` / `RULE_END` / `PROGRAM_END` (order = sequence position);
- predicate ops and feature names;
- action ops;
- reference ops;
- **pointers:**
  - to object slots ("objects like this one"), resolved into a typed predicate through the slot's feature values;
  - to evidence values (observed colours, vectors, sizes), so parameters are copied, not guessed;
- `BIND` (names a reference subtree once; later uses point to it).

**Holes:** the decoder may stop at a typed hole, and C+H-ordered symbolic search fills it (sketch completion).

## 5. Training (when authorized)

- **Data:** CORA's own execution-verified generator, with **new** families split by family before augmentation.
  Aliases are deduplicated by execution signature on the demonstrations and the test input.
- **Hard negatives** come from execution: swapped pairings, wrong order, near-miss parameters, and misleading
  superficial cues.
- **Loss:** minimum NLL over the execution-equivalent target programs, plus a listwise rule-ranking term over C+H's
  candidates.
- **Size:** about 5–20 M trainable parameters; Qwen frozen. Qwen forward about 0.3 s per task (fp16, RTX 2080 Ti,
  measured in v1); training a few GPU-hours on GPU 0.

## 6. Arms and success (pre-registered later)

| arm | what it is |
|---|---|
| 1 | C+H alone (ncv2-g2) |
| 2 | C+H + a learned hand-feature joint model |
| 3 | C+H + the joint model with Qwen object slots |
| 4 | arm 3 with Qwen slots shuffled across tasks |
| 5 | an untrained head |

**Success** requires arm 3 to beat arms 1, 2 and 4, with paired tests and losses counted, on new held-out families
and then a fresh real cohort. It must also add **coverage**: correct programs that C+H does not reach even at 3× its
budget.
