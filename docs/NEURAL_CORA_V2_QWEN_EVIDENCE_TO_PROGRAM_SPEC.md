# Neural-CORA: how Qwen evidence becomes CORA programs (specification, 20 October 2026)

**Status:** a specification. Nothing here is implemented or trained, and no run is authorized. Any interface below
needs its own frozen protocol and the author's authorization.

## 1. What G2 changed

For a solver whose answers must come from demonstration-fitting executed programs:

**pass@2 ≤ correct-candidate coverage.**

On G2's dev60 the coverage was 1/60, so a perfect reranker over those candidates could not have added a single task
(`records/NEURAL_CORA_V2_G2_REPORT.md`). The binding constraint was **generation**, not ranking.

So Qwen's first job is to **propose** hypotheses that the symbolic generator does not contain:
- references;
- parameters;
- program classes;
- sketches.

Ranking comes second. Its gains are bounded by coverage.

## 2. One CORA-owned inference process

- CORA owns the task state, the agenda, execution, checking, revision and the final choice of two attempts.
- Qwen's outputs enter the agenda as **typed hypotheses with provenance `neural`**, through the same grammar
  (ncv2-g2) and the same native interpreter as symbolic ones.
- **The final answer is always the output of an executed CORA program that fits every demonstration.** There is no
  neural answer lane, no router and no fallback to a Qwen grid.

## 3. Interface A: joint, object-conditioned proposals (a residual over strong symbolic search)

**Inputs** (inference-visible only):
- **Qwen object slots.** Per-cell token states, pooled per CORA object. The alignment is verified: one token per
  cell, 300 prompts, 0 misaligned. Because the model is causal, slots come from the test-input segment (which follows
  every demonstration) or from a re-read block, which must be tested.
- **Correspondence evidence** (`cora_neural_v2g2.search.evidence2`): matched objects, displacements, recolours,
  deletions, copies, and moved-and-recoloured objects.
- **C+H features**, kept as inputs.

**Outputs, all typed:**
1. **Residual scores** over ncv2-g2's candidate rules, joint over selector, action, references, bindings and rule
   order: `score = C+H + r_theta − cost`.
2. **Reference and parameter proposals outside the symbolic candidate set.** For each selected object, a
   distribution over typed references (feature, polarity, relation) and parameter values. These add candidates; they
   are not reorderings.
3. **Program-class proposals:** a distribution over class forms (symmetry, pixel-rule mode, generative kind and
   parameters, panel split and combiner).

**Decoding:** a grammar automaton built from `rast.SIGNATURES` plus `classes` schemas; only well-typed tokens are
allowed. The checkpoint has no program vocabulary, so this is a separate head.

**Training:**
- CORA's own execution-verified ncv2-g2 families, split by family before augmentation;
- hard negatives;
- no NVARC text.

**Controls:**
- C+H alone;
- a hand-feature-only joint head;
- Qwen slots shuffled across tasks;
- an untrained head.

**The claim it can earn:** Qwen adds proposal coverage beyond C+H and hand features.

## 4. Interface B: neural-to-symbolic construction

1. **Neural evidence.** The checkpoint decodes candidate output grids for the test input. It may adapt on the
   visible demonstrations only, re-adapting per fold for any leave-one-out (LOO) claim. Alternatively it scores the
   likelihood of grids that CORA programs produce.
2. **The evidence is untrusted.** From a candidate grid, CORA derives:
   - edit regions (the diff against the test input);
   - implied object correspondences;
   - colour pairs and displacement vectors;
   - the output shape and its symmetries.
3. **Conversion to symbolic constraints and proposals:**
   - sketch constraints, e.g. "objects in region R are recoloured to c";
   - hole fills (parameter values);
   - class proposals: an output size suggests crop / constant_shape; a symmetric output suggests
     symmetry_completion; added lines suggest generator kinds.
4. **CORA completes, executes and keeps only programs that fit every demonstration.** The answer is the program's
   output.

**Causal-ablation requirements** (pre-registered with any B protocol; all reported):

| test | what is done | pass condition |
|---|---|---|
| program removal | delete the final program | the answer disappears (abstain or symbolic attempts). A surviving answer means the program was decorative |
| program perturbation | change one rule or parameter | the output changes on most affected tasks |
| neural-evidence ablation | withhold the Qwen evidence; shuffle it across tasks | gains attributed to Qwen = with − withheld and with − shuffled, as paired counts |
| rationalization | flag programs whose test output equals the Qwen grid through test-specific constants unsupported by any demonstration (description length; LOO) | flagged programs are reported apart and never counted as symbolic certificates |
| no answer lane | audit every output path | no output exists without a demonstration-fitting executed program |

## 5. Likelihood reranking: a separately attributed competition arm (Path A)

This arm scores CORA-executed candidate outputs under the (adapted) checkpoint. It must be compared, with gains and
**losses** counted, against:
- the C+H order;
- a non-neural reranker (description length + fold stability + augmentation invariance).

It is reported as **NVARC-checkpoint-assisted**. It cannot add correct answers that are absent from the candidates.

## 6. Feasibility and rights

- **Local inference:** fp16 on the RTX 2080 Ti (bf16 unsupported), 0.30 s per task measured.
- **Grid decoding with adaptation:** costly. NVARC's full pipeline took about 4.34 h for 240 tasks in CORA's
  rehearsal.
- **Kaggle:** L4x4 machines with 96 GB of GPU memory are available to this competition (quota at twice the old
  rate), with a 12 h limit and no internet. Source: the official rules pages saved on 12 October,
  `outputs/kaggle_deploy/rules_20261012/Upgraded_Accelerators.txt`.
- **Local 4-bit adaptation:** needs peft and bitsandbytes, which are not installed.
- **Rights:**
  - the checkpoint is Apache-2.0;
  - decoding and adaptation code must be CORA's own;
  - NVARC repository code (no licence) is not reused;
  - every Qwen-derived result on public ARC is contaminated.
