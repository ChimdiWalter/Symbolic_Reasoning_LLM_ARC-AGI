# Neural-CORA v2: prior art, mechanism-to-module matrix, and the gap (20 October 2026)

## How this record was made

- A source-first audit subagent fetched every source listed in section F on 20 October. I reviewed its draft,
  corrected it, and re-fetched the one code claim about third-party code (B6) myself.
- **Every factual claim cites an opened source** [Ln].
- **Inference:** marks reasoning that no source states.
- Quotes are verbatim from the fetched page or the extracted text.
- PDFs were converted locally with `pdftotext`. No downloaded code was run.
- Kaggle pages render only titles without JavaScript, so Kaggle facts come from its public API [L14, L15].
- CORA's numbers come from this repository's records.

## A. The CORA modules, and where each one stands in code

| module | what it is | CORA code | status, 20 October |
|---|---|---|---|
| **M1** representation | views; the typed relational AST; binding | `cora_neural_v2/rast.py`, `bridge.py`, native segmentation views S1–S7 | **IMPLEMENTED** (ncv2-g1, parity tested) |
| **M2** constraints | sound prunes; Occam filter | `cora_neural_v2/constraints.py`, `search.fires` | **PARTIAL**: two provable prunes (P1, P2) plus the firing filter. Others proved unsound (constraints.py docstring) |
| **M3** proposal | an order over whole rules | `search.symbolic_scores` (G1-CH); `rule_scores` hook | symbolic **IMPLEMENTED**; learned joint guide **PROPOSED** (`records/NEURAL_CORA_V2_QWEN_JOINT_PROGRAM_ADAPTER_DESIGN.md`) |
| **M4** revision | diagnosis → edit → re-execute | spec in `docs/NEURAL_CORA_V2_RELATIONAL_AST_AND_LOOP.md` §4 | **PROPOSED** (diagnosis labels exist; no executed revisions) |
| **M5** library | reusable abstractions | `cora_neural_v2/macros.py` (typed, hygienic, researcher-written) | mechanism **IMPLEMENTED**; learned library **PROPOSED** |
| **M6** equivalence | merging programs that behave identically | `search.distinct_views` (exact); distinct-prediction selection | view collapse **IMPLEMENTED**; program-level (e-graph) **PROPOSED** |

## B. Mechanism-to-module matrix

The last column is a falsifiable test separating CORA from the source. None of these tests has been run.

| Source | URL | Mechanism (from source) | Code / licence (as stated) | Module | Falsifiable test |
|---|---|---|---|---|---|
| NVARC | [repo](https://github.com/1ytic/NVARC) | Generates output grids directly: full SFT of Qwen3-4B on 3.2M augmented samples, per-task LoRA test-time fine-tuning, batch DFS, augmentation re-scoring (C) | Repo: `license: null`. Model: Apache 2.0 | M3, selection | Solved-set overlap with NVARC's notebook at an equal budget. CORA adds value only on tasks it solves, LOO passed, that NVARC misses. Report Qwen-feature results separately for ARC-AGI-2 public eval, which seeded NVARC's data (C2) |
| ARChitects PoE (ICML 2025) | [2505.07859](https://arxiv.org/abs/2505.07859) | The LLM "not only as a generator but also as a scorer"; augmentations in "training, generation, and scoring"; DFS; "71.6% (286.5/400 solved tasks)" on public ARC-AGI(-1) eval | No code link | selection | Prefer fitting programs whose test output is equivariant under demonstration-consistent augmentations; keep only if pass@2 rises (paired) |
| ARC Prize 2025 analysis | [blog](https://arcprize.org/blog/arc-prize-2025-results-analysis) | "a refinement loop iteratively transforms one program into another" | n/a | M4 | Diagnosis-directed edits must reach demonstration-fitting, LOO-passing programs in fewer evaluations than undirected mutation at equal CPU time |
| Knoop & Chollet | [blog](https://arcprize.org/blog/beat-arc-agi-deep-learning-and-program-synthesis) | "Use DL as a perception layer"; "Deep learning models that inform discrete search and improve its efficiency" | n/a | M3 framing | The thesis is prior work. A learned order must beat hand-designed search (C+H 358/395); v1 did not (L1h 235, L1 198) |
| **ARGA** (AAAI-23) | [2210.09880](https://arxiv.org/abs/2210.09880) | Object graph abstractions; a DSL of "object-based selection filters" and "transformations (e.g., recoloring, moving, etc.)"; "constraint acquisition, state hashing, and Tabu search"; "57 of 160" object-centric tasks vs the Kaggle winner's 64 | ARGA-AAAI23, MIT | M1, M2, M6 | **Closest prior work to CORA's symbolic side.** Run both on ARGA's 160 tasks and on ARC-AGI-2 at matched CPU. CORA must fit significantly more, or fit binding, part or sequencing tasks ARGA cannot express |
| **NSA** (ESANN 2026) | [2501.04424](https://arxiv.org/abs/2501.04424) | A transformer predicts up to 3 per-step primitives (top-5/4/3) to restrict best-first search in ARGAe (27 primitives); 31,125 synthetic tasks, "Input images ... from both the train and eval set"; per-task TTA; 75/400 ARC-AGI-1 eval (1 attempt, 30 min) vs CodeIt 59; 63 without TTA | Batorskq/NSA, licence null | M3 | **Closest prior work to Neural-CORA v1**: independent per-step predictions guiding search. Swap M3 for an NSA-style per-step classifier with the same features and budget; joint selector-action-binding proposals must win |
| DreamCoder | [2006.08381](https://arxiv.org/abs/2006.08381) | Wake: enumerate "in decreasing order of their probability under the recognition model"; abstraction sleep: compress refactorings (version spaces, "equivalence graphs"); dreaming: "50/50 mix of replays and fantasies"; MAP breaks symmetry among "semantically equivalent expressions" | ellisk42/ec, MIT | M5, M3, M6 | CORA macros must cut nodes-to-solution on held-out real tasks more than DreamCoder or Stitch abstractions from the same solved corpus |
| Stitch (POPL 2023) | [2211.16605](https://arxiv.org/abs/2211.16605) | Top-down abstraction search pruned by "syntactic pattern matching of intermediate abstractions"; "3-4 orders of magnitude faster" than DreamCoder, compressivity comparable or better | mlb2251/stitch, MIT | M5 | Stitch on CORA ASTs is the baseline. M5 must beat it on held-out solve rate at equal library size |
| LILO (ICLR 2024) | [ICLR](https://proceedings.iclr.cc/paper_files/paper/2024/hash/819cebb05f993840e8a52d7564c5c282-Abstract-Conference.html) | LLM synthesis + Stitch + AutoDoc, which "infers natural language names and docstrings"; AutoDoc "boosts performance" | gabegrand/lilo: README states MIT; API licence field null | M5 | Replace macro names with random identifiers. Names matter only if an LM proposer's solve rate drops |
| Popper (MLJ 2021) | [Springer](https://link.springer.com/article/10.1007/s10994-020-05934-z) | Generate (ASP), test (Prolog), constrain: an entailed negative prunes generalisations; a missed positive prunes specialisations; smallest program; definite programs; "cannot handle noise" | Popper, MIT | M2, M4 | **Inference:** first-match rule lists depend on order, so Popper's soundness argument does not transfer. Measure false prunes against known synthetic solutions; CORA's M2 needs 0 false prunes |
| R3NN (NSPS) | [1611.01855](https://arxiv.org/abs/1611.01855) | "sequentially constructs a parse tree by selecting which non-terminal symbol to expand" from I/O encodings; 63% unseen tasks (94% with 100 samples); "38% of 238 real-world FlashFill benchmarks" | None seen | M3 | R3NN-style expansion over the ncv2-g1 grammar is the baseline; the joint proposer must beat it at matched budget |
| NS-CL (ICLR 2019) | [site](https://nscl.csail.mit.edu/) | Object proposals; a parser emits an "executable program"; executor of "deterministic functional modules"; curriculum | NSCL-PyTorch-Release, MIT | M1 | Label real-task failures as segmentation vs program. If segmentation dominates, the fixed views, not M3, are the bottleneck |
| Weave of Formal Thought (2026) | [2606.25987](https://arxiv.org/abs/2606.25987) | A GLR decoder "sound and complete with respect to the full Tree-sitter specification"; trains the model "to interleave non-terminal grammar symbols" as an "adaptive structural scratchpad"; "up to a 14.9% relative reduction in surface-token cross-entropy" | alexbouayad/formal, Apache-2.0 | M3 | Type-validity and solve rate with and without grammar constraints; a gain counts only if solve rate rises |
| Scheme macros; Racket quote | [Scheme](https://docs.scheme.org/guide/macros/), [Racket](https://docs.racket-lang.org/guide/quote.html) | `syntax-rules`: "hygienic macro system based on pattern-matching and rewriting"; non-hygienic macros must avoid capture; quote "produces a constant" | Docs | M1, M5 | Null test: S-expression and JSON forms compile to identical programs, so results must match. Any gain must appear in M5 |
| SWI-Prolog CLP; miniKanren | [CLP](https://www.swi-prolog.org/pldoc/man?section=clp), [mK](http://minikanren.org/) | CLP(FD/B/Q/R), CHR; "constraint propagation ... performed automatically"; labelling. miniKanren: "a family of Domain Specific Languages for logic programming"; relational quine generation; Barliman | Docs | M2 | Run one CORA action relationally backwards from demonstration outputs. It helps only if it shrinks parameter candidates vs enumeration at equal CPU, with identical solutions |
| Z3; Sketch/CEGIS | [Z3](https://microsoft.github.io/z3guide/docs/logic/basiccommands/), [TR](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-177.html) | Z3: sat/unsat, models, "may also return `unknown`". Sketch: holes in "a partial program"; "SAT-based inductive synthesis" plus a validator (CEGIS); "can not replace the human insight" | Docs / TR | M2, M4 | SMT vs enumeration for parameter holes: time to first fit, same solutions. **Inference:** in ARC the validator can only check demonstrations |
| egg (POPL 2021) | [POPL](https://popl21.sigplan.org/details/POPL-2021-research-papers/23/egg-Fast-and-Extensible-Equality-Saturation) | An e-graph "efficiently represents a congruence relation over many expressions"; equality saturation; "rebuilding"; "e-class analyses" | egg, MIT | M6 | Count candidates equal on the demonstrations that differ on the test input. If any exist, demonstration-only merging would discard valid pass@2 alternatives |
| Model Discovery Agent (2026) | [2608.09696](https://arxiv.org/abs/2608.09696) | "M-open": after a misfit, "MDA expands the hypothesis space by prompting the LLM to suggest one or more novel models" with "residual diagnostics"; SMC/BIC over a finite pool; "model-discrimination information gain"; the pool "does not account for unproposed model mass" | CC BY 4.0; no code seen | M4, selection | **Inference:** ARC has no oracle to query. Choose the 2 attempts covering the most posterior mass over distinct test outputs; this must beat top-2 by score |
| Quine (2026) | [blog](https://www.microsoft.com/en-us/research/blog/introducing-quine-an-ai-research-system-designed-for-the-complexity-of-biology/) | A world model plus a harness of "scientific tools, literature, the wet lab, and the researchers"; ranked "thousands of compounds", tested in wet-lab assays | Fellows programme; no code or licence stated | M4 (contrast) | CORA has no external oracle; hash-log file access to prove test outputs are never read |
| Co-Scientist (Nature 2026) | [blog](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/), [Nature](https://www.nature.com/articles/s41586-026-10644-y) | Generation; Reflection ("virtual peer reviewer"); Elo tournament with "simulated scientific debates"; Evolution "refines, combines, and builds upon the top-ranked hypotheses"; Meta-review | Tool rollout; enterprise preview | M4, selection | Rank fitting programs by a pairwise tournament instead of a scalar score; keep only if pass@2 rises |
| AlphaEvolve; FunSearch | [AE](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/), [FS](https://deepmind.google/blog/funsearch-making-new-discoveries-in-mathematical-sciences-using-large-language-models/) | LLM proposals; an evaluator "verifies, runs and scores"; evolutionary database ("The best ones are added back to the pool"); scope: problems that can be "automatically verified" | AE: early access planned. FunSearch: Apache-2.0, without LLM or sandbox | M4, M5 | **Inference:** demonstration fit is CORA's evaluator but does not verify the test answer. Diagnosis-guided revision vs a FunSearch-style loop at matched CPU, scored on held-out test correctness |
| SOAR (ICML 2025) | [PMLR](https://proceedings.mlr.press/v267/pourcel25a.html) | Integrates "language models into a self-improving evolutionary loop": evolutionary search alternates with hindsight fine-tuning on its own search attempts; "52% of the public test set" (the ARC version is not stated on the PMLR page) | No code link on the PMLR page | M3, M4, M5 | CORA's learned proposer must beat a SOAR-style loop (fine-tune on CORA's own hindsight-relabelled attempts) at matched compute on held-out families; a gain from failure *diagnosis* must exceed hindsight relabelling alone |

Added 20 October, after the addendum named SOAR [L57].

### B2. Lisp and Prolog mechanisms, mapped to code

| mechanism | origin | in CORA | status |
|---|---|---|---|
| programs as data (S-expressions; homoiconicity) | Lisp | `rast.to_sexpr` / `parse_sexpr`, with a JSON twin | IMPLEMENTED |
| `quote`: data that is never evaluated | Lisp / Racket | programs are typechecked and compiled to native dicts; no eval, no generated Python | IMPLEMENTED |
| hygienic macros (`syntax-rules`) | Scheme | `macros.py`: typed, gensym renaming, depth ≤ 8 | IMPLEMENTED (researcher-written macros only) |
| lexical binding (`let`) | Lisp | `rule_with` bindings, compiled by substitution | IMPLEMENTED |
| `eval` of generated code | Lisp | not used; the directive forbids it | EXCLUDED |
| unification | Prolog | no; types are checked against a signature table | NOT IMPLEMENTED |
| backtracking search | Prolog | best-first enumeration with exact truncation (a different strategy) | IMPLEMENTED |
| constraint propagation (CLP(FD)) | Prolog CLP | only the provable prunes P1 and P2 | PARTIAL |
| generate–test–constrain | Popper (ILP) | enumerate, execute, check. The first failing demonstration is recorded but not turned into a prune, since soundness fails for order-dependent rule lists | PARTIAL |
| relational (backwards) execution | miniKanren | — | PROPOSED test (B, row SWI-Prolog CLP; miniKanren) |
| closed-world assumption | Prolog negation as failure | the Occam firing filter: a rule that fires on no demonstration is dropped, labelled as not sound | IMPLEMENTED, labelled |

**Inference:** Lisp contributes a safe representation; Prolog-style systems contribute solvers. Neither one reasons
by itself. A solver also needs a faithful encoding of CORA's semantics. No gain from either one is claimed until its
row's test in B is run.

## C. NVARC audit

**C1. Ranking.**
- Team per the README: Ivan Sorokin and Jean-François Puget (NVIDIA KGMoN) [L2].
- ARC Prize 2025: 1st place, "ARC-AGI-2 Private Eval Score" 24.03%, ahead of the ARChitects (16.53%). Described as
  "A synthetic-data-driven ensemble of an improved Architects-style test-time-trained model" [L18].
- Paper: 27.64% on the public leaderboard; 29.72% for a post-deadline variant [L10].
- CORA separately reproduced NVARC's 27.64% notebook. That is NVARC's result, not CORA's.

**C2. Synthetic data and the checkpoint.**
- README: "103k synthetic puzzles" and "3.2M augmented puzzles" as Kaggle datasets. No checkpoint is named [L2].
- Paper pipeline (mostly gpt-oss-120b, plus two commercial language models): 3,268 summaries → 266,593 mixed summaries →
  126,901 input programs → "After filtering we had 103253 puzzles", each with about 30 pairs [L10].
- Table 1: 3,255,481 samples from 104,539 puzzles [L10].
- **Seeding** [L10]:
  - 29 evaluation puzzles were hand-described, then "the remaining 91 evaluation puzzles" by an LLM.
  - "NVARC full subset uses both training and evaluation puzzles from ARC-AGI-2"; the authors "'leaked' the
    descriptions".
  - Public eval has 120 tasks [L21]. **Inference:** all 120 public-eval tasks seeded the synthetic data.
- **The checkpoint we use** (CORA's v1 freeze manifest, group `nvarc_qwen3_4b_checkpoint`):
  - It is `sorokin/qwen3_4b_grids15_sft139` [L14], Apache 2.0, updated 2025-11-02T23:48Z, with empty
    training-data and provenance fields [L15].
  - `run_sft_4b.sh` has `EXP_NAME="qwen3_4b_grids15_sft139"`, 1 epoch, 12,716 steps, batch 256 [L6]. Its config
    trains on grids_v15, including nvarc_training and nvarc_full [L5].
  - **Inference:** 12,716 × 256 = 3,255,296 ≈ 3,255,481, so roughly one epoch over the 3.2M set. No source states
    this.
- **Consequence for CORA:** any Qwen-derived feature is contaminated for ARC-AGI-2 public eval. It is reported
  separately there, and never as independent evidence.

**C3. Objective.**
- Full fine-tuning: "to do a full fine-tuning of the 4B model we used 4 nodes of 8xH100 for 27 hours" [L10].
- SFT loss masking is not stated [L7].
- Test-time training masks the loss to assistant tokens [L14].

**C4. Test-time training.**
- LoRA "for each puzzle independently with r = 256 and alpha = 32", bf16, Unsloth [L10].
- Notebook [L14]:
  - rsLoRA, dropout 0;
  - targets q/k/v/o/gate/up/down, `embed_tokens`, `lm_head`;
  - lr 5e-5, 1 epoch, `max_seq_length = 8192`, `augment(n=16)`;
  - the adapter is reset per task;
  - decoding ≤ 1,200 s per puzzle within 12 h.
- 2025 limit: "12 hours with 4 L4 GPUs for solving 240 tasks" [L10].

**C5. Format.** The Qwen3 dialog template; "requires only 16 tokens" [L10, L8]. This is why the checkpoint cannot
emit program text (`records/NEURAL_CORA_V2_QWEN_JOINT_PROGRAM_ADAPTER_DESIGN.md` §1).

**C6. Augmentations: a code finding, verified on 20 October.**
- `SDG/scripts/build_datasets.py` [L9]:
  - draws one dihedral transform (tid 0–7) per sample;
  - shuffles **all ten** colours (`colors = list(range(0, 10)); random.shuffle(colors)`, so 0 is not fixed);
  - shuffles pair order.
- Its `color_mapping` is:

  ```
  for old_color, new_color in enumerate(mapping):
      grid[grid == old_color] = new_color
  ```

  This runs in place, in order 0 to 9. When a colour c maps to a higher colour σ(c), its cells are remapped again
  at step σ(c) and **merge** with σ(c)'s original cells. Every non-identity shuffle has such a c. So the function is
  a non-injective colour map whenever both colours are present.
- **Not known:**
  - whether this script built the released checkpoint's training data;
  - what effect it had.
- This is not a claim about NVARC's score and does not go on the poster.
- Test-time training and inference use transpose/rot90 plus `np.random.permutation(10)`, with 16 test variants
  decoded [L14].

**C7. Selection.**
- Batched DFS is nondeterministic. The batch-invariant fix was "About 17% slower" and was not used [L10].
- Re-scoring uses the same 8 augmentations for every candidate: score_agg(s) = Σ_c[c=s] + (1/m)Σ_j log P̂_j(s)
  [L10].
- `score_kgmon` takes the top 2 [L14].
- With TRM: 20.28% vs 21.53% without [L10].

**C8. Licences.**
- Repo: `license: null`, and no LICENSE among its 56 paths [L11, L12].
- Model: Apache 2.0 [L15].
- Notebook and dataset licences: NOT VERIFIED [L14, L16].
- **Inference:** the 2026 rules require third-party code "available under, at least, an open source license which
  allows public sharing" [L25]. Nothing found clears NVARC's repository code for reuse. CORA reads it for
  understanding only and copies none of it.
- NVARC's synthetic completion text is not used (licence unresolved, and contaminated for public eval).

## D. The "interpolation gap" claims, checked against primary sources

The PDF the directive names (co_scientist_quine_vs_agi_gap) was not found locally. These are its three claims as the
directive summarizes them.

**1. "Fundamentally limited to interpolation."** The sources neither support nor refute it, because none defines or
measures interpolation.
- Co-Scientist claims "demonstrably novel research hypotheses". It also says validation "remains preliminary" and
  that its "knowledge is constrained by its reliance on open-access scientific literature" [L54b].
- Quine reports "compounds with unexpected mechanisms of action" in a blog post, citing no peer-reviewed paper
  [L53].
- A categorical claim needs an operational test, and no source offers one. The same discipline applies to CORA's
  own "learning from failure" claims.

**2. "Cannot make first-principles conceptual breakthroughs."** Nobody claims the capability. Quine says "Nature
cannot be rushed, nor can it be derived from first principles" [L53]. The criticism is unsupported either way.

**3. "Cannot revise models."** The described mechanisms **contradict** it:
- Co-Scientist's Evolution agent "refines, combines, and builds upon the top-ranked hypotheses", and scientists can
  refine goals "at any time" [L54, L54b];
- MDA expands its hypotheses from residual diagnostics [L52];
- Quine's researchers "use results from the lab to decide what to explore next" [L53b].

**What the sources do support, more narrowly:**
- Co-Scientist does not automatically take in lab results; "reinforcement learning from human and experimental
  feedback" is future work [L54b].
- MDA can only revise to models the LLM proposes [L52].

**For CORA:** "revision" is prior art. CORA's possible contribution is narrower and testable:
- revision chosen from an **observable, logged diagnosis** of why an executable explanation failed;
- executed and checked by one native interpreter;
- under a blind evaluator;
- compared with failure-blind and matched-compute controls (G3).

## E. Design note: what to build first (1–2 pages)

**Constraints.**
- "November 2, 2026 - Submissions due" and "November 8, 2026 - Papers due" [L25]. The time zone is not stated on
  arcprize.org.
- Papers "must be linked to a Kaggle code submission", which "need not achieve a high score" [L27].
- No internet during evaluation [L25].
- The 2026 hardware limits "will be announced" [L26]: NOT VERIFIED.
- The poster print freeze is 21 October.

**Evidence that sets the order.**
1. v1's learned heads lost to hand-designed ordering (235 and 198 vs 358 of 395). The language fit 1 of 60 real
   tasks. Native CORA's own object layer fits 30 of the same 60 (`records/NEURAL_CORA_V2_G2_PROTOCOL_20261020.md`
   §2). **Inference:** coverage of the *language*, not ordering, binds first.
2. DreamCoder says programs need "not only a hand-designed DSL but also a search algorithm hand-designed to exploit
   that DSL" [L31]. ARGA credits the Kaggle winner's lead to "a much larger body of transformations" [L41].
3. Neural guidance of DSL search [L23, L30, L39, L43] and object views, filters and constraints [L41] are not novel
   in themselves. CORA's claims rest on the tests in section B, not on the architecture's description.

**The order.**
1. **M1 coverage, measured first.** The ncv2-g1 AST is built and parity-tested. G2 measures g1 against g0 on dev60,
   with native as a reference, plus an exhaustive single-rule diagnostic that separates search misses from
   language gaps. Then extend the AST where the failures cluster. S-expressions vs JSON is serialization only.
2. **M2:** only provably sound conditions from demonstrations (ARGA-style "should not do" invariants), with 0 false
   prunes on known synthetic solutions. Hash-log that test outputs are never read.
3. **M6:** merge on outputs over the demonstrations *and* the test input. Keep demonstration-equal,
   test-different programs as the pass@2 pair.
4. **M4:** repair near misses from demonstration diffs, then re-test with LOO. This follows MDA's pattern of
   proposals conditioned on "residual diagnostics" [L52], with demonstration diffs as the residuals. Compare with a
   FunSearch-style loop [L56] and with failure-blind controls (G3).
5. **M3 and M5 are deferred** until a learned proposer beats the symbolic order on the frozen protocol.
   - When M3 is revisited:
     - decode over the M1 grammar [L45];
     - benchmark against NSA- and R3NN-style proposers [L39, L43];
     - keep C+H / G1-CH as a first-class baseline.
   - Per-task adaptation is costly: NSA reports about 22 minutes per task [L39]; NVARC fit LoRA test-time training
     into 12 h on 4 L4s for 240 tasks [L10].
   - Compressing CORA's own synthetic solutions risks rediscovering its generator. Stitch is the M5 baseline [L35].

**Limitations.**
- Lisp is a representation; hygiene matters only for macros that bind variables [L46].
- Prolog, CLP and SMT are solvers that need a faithful encoding of CORA's semantics, and Z3 can return `unknown`
  [L49].
- With 2–4 demonstrations, "verified" means "fits the demonstrations". LOO narrows the gap but does not close it.
- Qwen features are contaminated for ARC-AGI-2 public eval [L10, L21].
- Submitted code must be under "a permissive public domain license" [L25].

**The honest gap.** What is not new:
- neural-guided DSL search;
- object-graph abstraction with constraints;
- typed ASTs and hygienic macros;
- refinement loops;
- LLM hypothesis revision.

What CORA could add, each still a hypothesis with a test above:
1. a joint, conditional rule scorer bound to CORA's objects, using a grid-pretrained LM's representations (M3);
2. revision chosen from observable failure diagnoses (M4);
3. one native interpreter that both executes and certifies, under a blind evaluator, with frozen protocols.

## F. Sources

L1 https://github.com/1ytic/NVARC · L2 https://raw.githubusercontent.com/1ytic/NVARC/main/README.md · L3 https://github.com/1ytic/NVARC/tree/main/ARChitects · L4 https://raw.githubusercontent.com/1ytic/NVARC/main/ARChitects/README.md · L5 https://raw.githubusercontent.com/1ytic/NVARC/main/ARChitects/sft_mg.yaml · L6 https://raw.githubusercontent.com/1ytic/NVARC/main/ARChitects/run_sft_4b.sh · L7 https://raw.githubusercontent.com/1ytic/NVARC/main/ARChitects/run_sft.py · L8 https://raw.githubusercontent.com/1ytic/NVARC/main/ARChitects/qwen3_configs/chat_template.j2 · L9 https://raw.githubusercontent.com/1ytic/NVARC/main/SDG/scripts/build_datasets.py · L10 https://raw.githubusercontent.com/1ytic/NVARC/main/nvarc_2025.pdf · L11 https://api.github.com/repos/1ytic/NVARC · L12 https://api.github.com/repos/1ytic/NVARC/git/trees/main?recursive=1 · L13 https://www.kaggle.com/code/sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue · L14 https://www.kaggle.com/api/v1/kernels/pull?userName=sorokin&kernelSlug=arc2-qwen3-unsloth-flash-lora-batch4-queue · L15 https://www.kaggle.com/api/v1/models/sorokin/qwen3_4b_grids15_sft139/get · L16 https://www.kaggle.com/datasets/sorokin/nvarc-synthetic-puzzles · L17 https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507 · L18 https://arcprize.org/blog/arc-prize-2025-results-analysis · L19 https://arcprize.org/competitions/2025 · L20 https://arcprize.org/competitions/2025/archive · L21 https://arcprize.org/arc-agi/2 · L22 https://arxiv.org/abs/2505.07859 · L23 https://arcprize.org/blog/beat-arc-agi-deep-learning-and-program-synthesis · L24 https://arcprize.org/events/research-summit-2026 · L25 https://arcprize.org/competitions/2026 · L26 https://arcprize.org/competitions/2026/arc-agi-2 · L27 https://arcprize.org/competitions/2026/paper · L28 https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview · L29 https://www.kaggle.com/api/v1/competitions/list?search=arc-prize-2026 · L30 https://arxiv.org/abs/2006.08381 · L31 https://arxiv.org/pdf/2006.08381 · L32 https://github.com/ellisk42/ec · L33 https://proceedings.iclr.cc/paper_files/paper/2024/hash/819cebb05f993840e8a52d7564c5c282-Abstract-Conference.html · L34 https://github.com/gabegrand/lilo · L35 https://arxiv.org/abs/2211.16605 · L36 https://api.github.com/repos/mlb2251/stitch · L37 https://link.springer.com/article/10.1007/s10994-020-05934-z · L38 https://api.github.com/repos/logic-and-learning-lab/Popper · L39 https://arxiv.org/abs/2501.04424 (+ /html/) · L40 https://api.github.com/repos/Batorskq/NSA · L41 https://arxiv.org/abs/2210.09880 (+ PDF; https://api.github.com/repos/khalil-research/ARGA-AAAI23) · L43 https://arxiv.org/abs/1611.01855 (+ PDF) · L44 https://nscl.csail.mit.edu/ (+ https://api.github.com/repos/vacancy/NSCL-PyTorch-Release) · L45 https://arxiv.org/abs/2606.25987 (+ https://api.github.com/repos/alexbouayad/formal) · L46 https://docs.scheme.org/guide/macros/ (+ https://docs.racket-lang.org/guide/quote.html) · L47 https://www.swi-prolog.org/pldoc/man?section=clp · L48 http://minikanren.org/ · L49 https://microsoft.github.io/z3guide/docs/logic/intro/ (+ /basiccommands/) · L50 https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-177.html · L51 https://popl21.sigplan.org/details/POPL-2021-research-papers/23/egg-Fast-and-Extensible-Equality-Saturation (+ https://api.github.com/repos/egraphs-good/egg) · L52 https://arxiv.org/abs/2608.09696 (+ /html/) · L53 https://www.microsoft.com/en-us/research/blog/introducing-quine-an-ai-research-system-designed-for-the-complexity-of-biology/ · L53b https://microsoft.github.io/quine · L54 https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/ · L54b https://www.nature.com/articles/s41586-026-10644-y · L55 https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ · L56 https://deepmind.google/blog/funsearch-making-new-discoveries-in-mathematical-sciences-using-large-language-models/ (+ https://github.com/google-deepmind/funsearch) · L57 https://proceedings.mlr.press/v267/pourcel25a.html · L58 https://api.github.com/repos/arcprize/ARC-AGI-2 (licence Apache-2.0)

## G. Verification log (20 October 2026)

| ID | status | note |
|---|---|---|
| L1, L3–L12, L14, L15, L17–L27, L30–L41, L43–L56 | FETCHED by the audit subagent | L10, L31, L41 and L43 are PDFs converted locally. L37 and L54b were reached after cookie redirects; only the first 100k characters were read. L52 HTML: characters 0–200k of 278k |
| L9 | **RE-FETCHED by me** | `color_mapping`, the ten-colour shuffle and the dihedral transforms quoted verbatim (C6) |
| L57, L58 | FETCHED by me (20 Oct, after the addendum) | SOAR's title, authors, abstract excerpts and the 52% figure; ARC-AGI-2 repository licence |
| L2 | FETCHED | The tool summarised the README but would not reproduce it verbatim |
| L13, L16, L28 | FETCHED (title only) | Kaggle pages need JavaScript |
| L29 | NOT FETCHED | HTTP 401 |
| L42 | REMOVED | Wrong arXiv ID in the draft (an unrelated physics paper). ARGA is L41 |
| FunSearch Nature paper (s41586-023-06924-6) | NOT FETCHED | Only seen as a link on L56 |
| deadline time zone | NOT VERIFIED | Not stated on arcprize.org |
| co_scientist_quine_vs_agi_gap.pdf | NOT FOUND locally | Section D checks the claims as the directive summarizes them |
