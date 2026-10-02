# Related work and the novelty matrix

Started 2026-10-02. Kept current as the paper is written. Every row must be
checked against the cited paper before the paper is submitted; rows marked
VERIFY were added from a search summary and have not yet been read by us.

## The claim this matrix protects

We do not frame the contribution as self-improvement, feedback, program
repair, tool creation, library learning, execution-guided search, test-time
adaptation or candidate testing. Each has substantial prior work.

The candidate contribution is the conjunction:
1. a task-local internal failure frontier from a symbolic reasoner;
2. the failure identifies a missing semantic capability, not only a bad
   program;
3. candidate semantic productions are constructed without hidden answers;
4. candidates are probed causally by temporary intervention in the same
   failed reasoner;
5. the winning extension is compiled into that reasoner's language;
6. the same reasoner reruns;
7. the winning program uses the extension;
8. the extension is fully re-discovered under adaptive leave-one-out;
9. the final ARC output is exactly correct;
10. removing the extension destroys the solve.

Narrowest defensible sentence (use this):

> We are not aware of prior work that uses a reasoner's own task-local
> failure frontier to construct a new semantic grammar production at
> inference time, probes the candidate by temporary intervention in the same
> reasoner, and then establishes its necessity through rediscovery-based
> leave-one-out verification and ablation in that reasoner.

Sentence that must not be used:

> The first self-improving reasoner that learns new skills from its own
> failures.

Every clause of that sentence has prior work (see below).

## Columns

A what is adapted; B when adaptation occurs; C source of feedback; D does
the DSL or grammar change; E do parameters change; F is a hidden answer or
an external evaluator required; G is the new capability executable; H does
it persist; I is causal ablation shown; J is full rediscovery leave-one-out
shown; K evaluated on ARC.

## Matrix

| work | A adapted | B when | C feedback | D grammar | E params | F hidden/external | G executable | H persists | I ablation | J rediscovery LOO | K ARC | difference from CORA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CEGIS (Solar-Lezama 2006 and later) | the candidate program | per query | counterexamples from a verifier or spec | no | no | spec or oracle | yes | no | n/a | no | no | repairs a program inside a fixed language against a spec; CORA has no spec and changes the language |
| Semantic program repair (Angelix, Mechtaev et al. 2016) | the patched program | per bug | failing tests | no | no | tests | yes | yes (patch) | no | no | no | tests supply the target; CORA's target output is never seen |
| DreamCoder (Ellis et al. 2021) | library of abstractions and a recognition model | between wake-sleep cycles | solved programs | yes, by abstraction | yes (recognition net) | task solutions | yes | yes | partial | no | no (other domains) | learns from successes across a corpus; CORA grows from one unsolved task's failure at inference time |
| Stitch (Bowers et al. 2023) | library abstractions | offline | corpus of programs | yes | no | corpus | yes | yes | no | no | no | compression of solved programs; no failure, no task-time growth |
| LILO (Grand et al. 2023), LAPS (Wong et al. 2021) | library plus language-guided naming or search | offline cycles | solved programs and language | yes | yes (LLM or translation model) | corpus | yes | yes | partial | no | no | same family as DreamCoder with language; not failure-driven, not inference-time |
| Execution-guided synthesis (Chen et al. 2019; Ellis et al. 2019 REPL) | search policy over partial programs | training then search | intermediate execution states | no | yes | task I/O during search; training targets | yes | model persists | no | no | partly (ARC variants exist, VERIFY) | fixed DSL; execution guides search inside it |
| SOAR (Pourcel et al. 2025, VERIFY details) | the LLM proposer weights and search | across iterations | hindsight-relabelled traces from evolutionary search | no | yes (fine-tuning) | task outputs for training | yes (programs) | weights persist | partial | no | yes | self-improvement by weight updates on generated data; CORA proposes no weight change and grows the grammar per task |
| Reflexion, Self-Refine, Self-Debugging (2023) | the next attempt's prompt or program | per episode | verbal self-critique, execution errors | no | no | often an external evaluator or tests | yes | memory text | no | no | no | revises outputs in a fixed language with a frozen model; no grammar change, no certification |
| Voyager (Wang et al. 2023) | a skill library of code | during play | environment feedback, errors | library grows | no | environment reward | yes | yes | partial | no | no | tool creation from environment feedback; CORA's feedback is the reasoner's internal frontier, with exact verification |
| CREATOR (Qian et al. 2023), ToolMaker/LATM (Cai et al. 2023) | created tools | per task class | execution errors, examples | tool set grows | no | demonstrations and tests | yes | yes | no | no | no | tools made by an LLM from examples; no failure-frontier representation, no rediscovery LOO, no ablation |
| FunSearch (Romera-Paredes et al. 2023), AlphaEvolve (2025) | programs under evolution | iterations | external scorer | no | no | external objective | yes | best program kept | no | no | no | the optimization signal is an external evaluator; CORA infers the missing capability from its own failed search |
| STOP (Zelikman et al. 2023) | the scaffold program | iterations | downstream utility | scaffold code | no | utility evaluator | yes | yes | no | no | no | self-modifying scaffold around a frozen model, judged by utility |
| Gödel Agent (Yin et al. 2024), Darwin Gödel Machine (Zhang et al. 2025) | the agent's own code | iterations | benchmark scores | agent code | no | benchmark evaluator | yes | yes | partial | no | no | whole-variant empirical selection by scores; CORA's unit is one typed production tied to one failure |
| Rule2DRC / SplitTester (ICML 2026, VERIFY) | test generation to split candidates | per query | execution feedback | no | VERIFY | execution of candidates; VERIFY whether an oracle labels the test | tests | no | no | no | VERIFY | active discrimination of ambiguous candidates; closest method to our probe; CORA probes inside the reasoner's failure with no external test oracle |
| CURE, TTCS, TTVS (2026 test-time self-improvement, VERIFY) | model policy at test time | test time | self-generated examples or verification | no | yes | VERIFY | n/a | VERIFY | no | no | VERIFY | adapts parameters at test time; CORA changes structure with no parameter update |
| Online or prospective library learning (2026, VERIFY) | library under future uncertainty | online | solved tasks | yes | VERIFY | solutions | yes | yes | VERIFY | no | VERIFY | weakens any broad "first online capability learning" claim; not failure-causal grammar growth |

## What CORA has shown so far (claim ladder)

| level | statement | status |
|---|---|---|
| 0 | the failure representation contains target information | established under shared-input twins (v1.4); not an incremental selection signal (v1.5 negative) |
| 1 | candidate-conditioned failure intervention predicts the better extension prospectively | the v1.6 bounded repair; not yet run |
| 2 | a novel semantic extension is constructed and certified | not shown |
| 3 | a real ARC task is causally rescued (B/P/U/L/T/A) | not shown |
| 4 | an invented extension transfers or is reused | not shown |
| 5 | extensions accumulate at controlled cost | not shown |

No level may be claimed from evidence belonging to a lower one.

## Ideas worth importing into the bounded repair without changing its question

- From Rule2DRC and CEGIS: separate ambiguous candidates by an active probe
  rather than a richer description. Imported as the CandidateFailureProbe:
  the held-out demonstration is the smallest legal internal probe, identical
  for both candidates, with a demonstration-visible comparison value.
- From the counterfactual-intervention methodology (e.g. Anthropic's 2026
  CHIVE work, VERIFY): infer relevance by intervening and observing a change
  in behaviour, not by correlation. Imported as the swapped-identity and
  replaced-frontier controls.

## Deadlines (official pages, per the user 2026-10-02)

Kaggle entry and team merger 26 October 2026; competition submission 2
November 2026; Paper Track 8 November 2026.
