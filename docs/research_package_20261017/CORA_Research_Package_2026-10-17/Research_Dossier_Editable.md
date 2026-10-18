# Learning What to Change
## From ARC-AGI-2 to evidence-backed scientific reasoning

**Research dossier and experimental roadmap for Chimdi Walter Ndubuisi**  
University of Missouri · Prepared October 17, 2026  
For discussion with Toni Kazic, collaborators, and the ARC Prize Research Summit community

**Central proposition.** A useful reasoner should not merely produce another answer after failure. It should determine whether to change its representation, program, executable vocabulary, or evidence—and justify that revision with tests it cannot manipulate.

**Evidence boundary.** This is a researched proposal, not a report of new CORA experiments. Published findings, company-reported capabilities, supplied CORA records, and proposed experiments are distinguished throughout. The strongest new research claim remains to be earned.

# Executive decision

**Keep ARC as the testbed, not the ceiling of the research.** Toni’s question is about learning meaningful representations and reasoning rules from limited observations, recognizing their inadequacy, and transferring the process of revision to semantically different data. That is broader than a Kaggle score, but it should be pursued through a smaller, better-controlled experiment—not by announcing a universal architecture. [L01]

**Retain CORA-FHR as a testable construction-and-verification core.** Its useful engineering contribution is a bounded executable patch, temporary installation into an unchanged reasoner, fold-local reconstruction, and removal controls. The current evidence does not establish a causal advantage from authentic failure information, a new real ARC solve from FHR, or biological transfer. The October 15 audit supersedes earlier “pilot still running” descriptions: the mixed pilot failed its criterion and the real 60-task FHR application added no extension certificate. [L02, L04]

**Do not pitch against an obsolete picture of frontier AI.** Current systems use tools, executable programs, scientific models, persistent artifacts, and external checks. EMET and Quine already occupy parts of the scientific-research workflow; contemporary coding and formalization systems already revise programs. This search therefore rejects “we are the first system to learn from failure” as a defensible claim. [R16, R17, R21, R22]

**The closest new comparison is Model Discovery Agent, not merely a chatbot.** Kevin Murphy’s MDA explicitly connects model inadequacy, hypothesis-space expansion, Bayesian inference, and informative experiments. CORA must be positioned as a possible extension or rigorous comparison, not as the first proposal of that loop. The advertised summit program includes this work. [R28, R42]

**The near-term research bet.** Test whether structured failure evidence improves *which bounded revision is selected*, relative to a strong failure-blind system given the same observations, tools, candidate opportunities, and total budget. Then separately test whether the resulting selection policy transfers to a numerical scientific task. These are different experiments; neither is established by a large diagram.

**The competition bet.** Preserve the recorded 27.64% NVARC reproduction as an incumbent. Do not repeat the unsuccessful native-output fill strategy. A better score requires new correct candidates or better selection among existing candidates, with every displaced answer and additional runtime measured. No evidence supports a promised next score. [L02]

**The startup bet.** Begin with research infrastructure for deciding whether a proposed model correction is justified, harmful, or insufficiently evidenced. Do not claim an autonomous biology engine. A credible first product requires an independently evaluated biological decision, a user with a costly validation problem, and a measurable improvement over their existing workflow.

# 1. What Toni actually asked

## 1.1 Four questions, not one benchmark

The opening of the supplied conversation distinguishes representations of data with different syntax and semantics, an automated reasoner operating on those representations, learning from failures with few examples, and generalizing the reasoning to data of different meaning. Its most important distinction is between transfer of predictions within a familiar problem and transfer of the procedure used to formulate and revise explanations. [L01, 00:00:03–00:03:59]

| Toni’s question | Operational research question |
|---|---|
| Can representations be induced? | Can a system choose or construct entities and relations that improve an independent prediction, rather than receive all useful groupings from a developer? |
| How would the reasoner work? | What executable hypotheses can it form, which assumptions do they encode, and how does it decide among explanations that fit equally well? |
| Can it learn from failure? | Does evidence about unsuccessful attempts improve the next action beyond what equally equipped search can achieve? |
| Can reasoning generalize? | Does a policy or abstraction learned in one setting improve a second domain without being re-engineered or retrained on its evaluation answers? |

The conversation also mentions molecular-species measurements under different conditions and manually written displacement-versus-dispersion tests in work with Pierce. That supplies a candidate scientific context, **not an identified dataset or an established CORA application**. The transcript gives no sample sizes, exact target definition, independent validation outcome, or permission to access that project. Chris is the lab collaborator in this discussion; this report does not equate that person with Kris Bouchard in the separate LBNL collaboration. [L01, 00:02:37; 00:12:32–00:16:37]

## 1.2 A precise version of the problem

Given observations D, a question q, limited computation B, and possibly a budget for new measurements, learn a representation R and an executable hypothesis h. When the pair does not support q, choose a justified revision a rather than merely increasing search indefinitely. The revision may change grouping, a program parameter, the operation library, an observation model, or the evidence collection plan. Evaluate the revised system on information not used to choose the revision.

The ambition is not “no human choices.” Every experiment specifies inputs, available actions, measurement procedures, and success criteria. The important questions are **which choices remain fixed, which choices are learned, and how much work and prior knowledge are required when the domain changes**. ARC’s original research framing makes accounting for priors and experience important; removing every initial inductive bias is not its standard. [R01]

## 1.3 Keep the speaker’s suggestions separate from established facts

Toni’s discussion is intellectually useful but informal. It includes speculation about frontier-model internals, mathematical verification, historical researchers, and model failures on specific images. Those remarks are not treated here as verified literature results. The voice transcript was supplied as a Whisper transcription; original audio and speaker diarization were not independently checked. Historical digressions and sensitive personal anecdotes are excluded.

The practical poster advice is clear: circulate a content outline to Toni, Chris, and Pierce before final layout; place completed work in the context of the broader questions; decide authorship from actual contributions. The proposed author ordering is not a finalized authorship agreement. This collaborative framing must remain distinct from the single-student SAC candidate-selection submission. [L01, 00:12:32–00:16:37]

# 2. Why the problem persists

## 2.1 Correct syntax is not a correct explanation

A grammar specifies legal constructions. An executable language gives those constructions meaning. A program instantiates a particular computation. A scientific interpretation additionally connects its variables and outputs to measurements. A syntactically valid instruction can execute successfully while using the wrong object, the wrong units, the wrong causal assumption, or a misleading observation model.

The historical symbol-grounding question concerns that gap between manipulating symbols and connecting them to meaning. Modern causal-representation research studies the related difficulty of recovering useful high-level variables rather than assuming them to be given. These are research traditions, not arguments that neural models lack meaningful representations. [R03, R13]

For example, grouping cells by proximity and grouping them by colour may produce different ARC objects. In a molecular matrix, a cluster may represent a cell state, batch, tissue mixture, or measurement artifact. A system needs evidence for the interpretation relevant to the question, not merely a visually convincing embedding. The appropriate abstraction can change when the question changes.

## 2.2 Few observations often do not identify a unique rule

Suppose two hypotheses reproduce every demonstration. One recolours the red object; the other recolours the largest object. When the red object is always largest in the demonstrations, the evidence does not distinguish the rules. Removing one demonstration may leave the same ambiguity. A preference for a shorter program is a prior, not an observation proving which rule is true.

This is a logical limitation of the information supplied, not just a shortage of model parameters. The system must preserve uncertainty, use defensible priors, or acquire a discriminating observation when permitted. Underspecification research documents how equally successful training/evaluation solutions can behave differently in deployment. A favorable score on one sample is not enough to resolve the ambiguity. [R14]

For biological inference, two mechanisms can yield similar observational distributions but different responses to an intervention. More repeated measurements of the same non-discriminating condition may reduce measurement noise without resolving the mechanistic uncertainty. The proposed architecture must recognize this difference rather than turn every failure into another grammar expansion.

## 2.3 A failure identifies a symptom before it identifies a cause

A failed prediction can arise from an incomplete candidate language, poor search allocation, the wrong representation, a coding defect, a wrong likelihood, or insufficient evidence. Several can coexist. “No program found” means no program was found under the actual search and budget; it does not prove inexpressibility. A crash is not evidence of missing conceptual knowledge.

Model-based diagnosis has long studied inconsistencies between expected and observed behavior. CORA should build on this tradition rather than rebrand a generic error log as a novel theory of failure. The new question is whether its diagnostic information improves a bounded decision about changing a learned reasoning system. [R02]

A reliable diagnosis therefore needs interventions on the *solver*: hold most of the pipeline constant, change one component, and observe what changes. Even then, interacting failures may prevent a single intervention from working. The diagnosis should remain a set of supported alternatives when the evidence does not isolate one cause.

## 2.4 The representation and the rule depend on each other

An apparently simple rule under one representation may be impossible or expensive under another. Conversely, a useful representation is often identifiable only after a candidate rule explains multiple examples. A one-pass sequence of “discover objects, then discover grammar, then reason” is an organizational diagram, not an adequate learning algorithm.

The proposed system should revisit representation and hypothesis jointly, under a budget. It needs a way to say “this grouping simplifies the explanations but introduces an unsupported assumption” rather than selecting the grouping with the easiest training fit. This is especially important when the representation learner itself can exploit withheld labels through preprocessing or shared state.

## 2.5 Search spaces grow, while evidence does not grow automatically

Giving a constructor more primitives or deeper compositions expands what it can express, but also increases the number of accidental fits. Reusable abstractions may reduce future search cost; they can also encode shortcuts and flood later search with irrelevant options. DreamCoder and LILO provide precedents for library learning, while CORA’s question is how to measure the additional value of failure-guided revision. [R06, R07]

A fixed grammar is not inherently unscientific. It makes hypotheses and bounds inspectable. The mistake is equating enumeration of a larger grammar with learned intelligence, or claiming that a composition unavailable in a small baseline is semantically impossible in a richer baseline. Report expressiveness, accessibility under a budget, and reusable utility separately.

## 2.6 Verification has a boundary

A proof assistant can check a formal statement relative to axioms and a trusted kernel. An ARC evaluator can compare a prediction with a withheld grid. A biological experiment can test an observable consequence with measurement error and confounding controls. These are different forms of assurance. Success in one does not automatically provide the guarantees of another. [R43]

Leave-one-out reconstruction is a useful stress test of dependence on examples. It is not a proof of correctness on every future input, and its folds are not independent discoveries. Repeatedly adapting a system to a small development set also turns that set into part of the engineering process. Independent procedure, independent data, and independent replication are three different requirements.

## 2.7 Biological difficulty is not “biology has no rules”

A useful working model is that the relevant processes operate across scales, contexts, times, and measurement systems. Observations are partial; interventions may alter the population being measured; genetic background, environment, dose, timing, and technical preparation can change what a model needs to represent. A universal representation of all biology is not a realistic first milestone. The virtual-cell literature presents a multiscale research agenda, not a finished replacement for experimental science. [R31]

The uncertainty creates a design requirement: explicitly record what the data can and cannot identify. Do not infer dynamics from a single static matrix without additional assumptions. Do not infer that a fitted latent variable is a physical mechanism because it received a biological name. Prioritize an observable decision for which independent controls are available.

# 3. What prior work already answers

## 3.1 The relevant history is a set of partial solutions

| Research line | What it already contributes | What CORA must still establish |
|---|---|---|
| Model-based diagnosis | Locate candidate faults from inconsistent observations and a model. [R02] | A useful, tested decision about revising representations or executable rules. |
| Counterexample-guided synthesis | Alternate candidate construction and checking against a specification. [R04] | Advantages when no complete specification exists and observed examples are sparse. |
| Popper | Learn programs by using failed hypotheses to constrain search. [R05] | A benefit beyond generate-test-constrain with the same effective resources. |
| DreamCoder / LILO | Learn reusable program abstractions and improve synthesis. [R06, R07] | Evidence that diagnosis adds value beyond ordinary library construction. |
| HtT | Induce and validate rule libraries for later reasoning. [R08] | Executable, independently evaluated transfer in CORA’s setting. |
| Reflexion / Voyager | Use feedback and memory; accumulate and revise executable skills. [R09, R10] | A controlled improvement over a strong feedback-and-memory baseline. |
| SCoRe | Train useful self-correction through multi-turn reinforcement learning. [R12] | Better selective revision under matched training and inference budgets. |

These precedents answer Toni’s question about whether rule induction exists: **yes**. The unresolved issue is the scope, reliability, data efficiency, and transportability of the induced rules—not whether researchers have ever attempted induction.

## 3.2 Why “LLMs cannot self-correct” is no longer a suitable premise

Earlier work found that asking the evaluated language models to correct themselves without adequate external feedback could fail or degrade answers. That is a scoped empirical result. SCoRe subsequently demonstrated improved self-correction through a different training procedure. The lesson for CORA is to measure both wrong-to-right and right-to-wrong changes and to specify where the feedback comes from. It is not to assume that symbolic methods own self-correction. [R11, R12]

## 3.3 The closest scientific comparator: Model Discovery Agent

MDA uses an LLM to propose mechanisms, Bayesian inference to fit and compare them, predictive inadequacy to trigger hypothesis expansion, and value-of-information to select experiments. Its paper evaluates scientific benchmarks and discusses learned summaries and observation-model selection. It therefore overlaps substantially with Toni’s proposed loop, including the case where the current model class is inadequate. [R28]

**Research judgment.** A broad CORA claim of “detect failure, expand a model, test it” is not novel against this comparator. A more precise investigation would compare revision policies over an explicit set of component-level patches, measure their causal value and cost, and test frozen policy transfer under independently implemented domain contracts. Whether that constitutes publishable novelty depends on results and a deeper comparison with the exact MDA implementation. This dossier does not certify priority.

# 4. What current frontier systems are doing

## 4.1 EMET is a scientific platform, not just a base model

EMET is BenchSci’s Evidence Mapping and Exploratory Tool. BenchSci describes planning, specialized models and skills, code execution, knowledge-graph grounding, and lab connectivity. Its platform comparisons include proprietary knowledge and workflows absent from the general-model baseline, so they should be treated as whole-system comparisons rather than isolated proof of superior reasoning. [R15, R16]

**Implication for CORA.** Citation-backed answers and orchestrated research workflows are not an unoccupied market. The proposed differentiator is a measured decision about when an executable model revision is warranted, with adverse revisions and validation burden reported. Public product descriptions do not establish whether EMET internally already implements any particular CORA-like control; absence of disclosure is not absence of capability.

## 4.2 Quine already connects models and experiments

Microsoft describes Quine as a multimodal biological world model coupled to a research harness, integrating scientific tools and researchers. It reports computational proposals followed by experimental investigation in a pancreatic-cancer application with the Broad Institute. This is bounded biological evidence, not just a conversational demonstration, and not a general proof of all biological reasoning. [R17]

**Implication for CORA.** Do not claim to introduce biological world models or the computational-to-experimental loop. A viable complementary direction is to audit alternative revisions across different upstream predictors. The evaluation must distinguish useful experimental prioritization from an attractive explanation. Quine’s research journey also explicitly discusses data, context, and evaluation limitations; the field is already aware of these problems. [R18]

## 4.3 “Argon4” is treated here as Gemini 4 Argon

Google’s October 13 announcement identifies Gemini 4 Argon as a frontier multimodal model for complex, multi-step work. A separate October research preprint reports a team of Argon agents completing Minecraft through generated code and environmental interaction. These are evidence that program creation and iterative feedback are already within the frontier landscape; they are not a matched demonstration of Toni’s complete semantic-transfer question. [R19, R20]

**Implication for CORA.** The appropriate comparison is an agent with equivalent tools, feedback, memory, and budget—not a single unassisted prompt. A CORA controller should be compatible with a stronger proposer rather than depend on pretending the proposer cannot reason.

## 4.4 Claude: distinguish general agents from formal assurance

Anthropic positions Opus 5.5 for sustained coding and agentic work. In a separate report, it describes a Claude-driven formalization of an existing proof of Fermat’s Last Theorem, checked by Lean and supported by Prove2Me. This is important formal-verification work; it is not the original discovery of Fermat’s theorem’s proof, nor an experiment on biological model validity. [R21, R22]

The linked Prove2Me work emphasizes shared formal artifacts and coordination. **Design lesson:** reliable long-horizon reasoning needs state, dependencies, and checking infrastructure, not only a better textual critique. CORA can adopt that engineering lesson without claiming an equivalent level of formal assurance for finite-example generalization. [R23]

## 4.5 OpenAI and the broader tool-using frontier

The official GPT-6 Astra and GPT-6.1 Sol announcements report strong agentic and scientific capabilities. Their benchmark results, inference configurations, and access to tools are not equivalent to an offline Kaggle ARC-AGI-2 notebook. This dossier does not turn a cross-benchmark percentage into a ranking against CORA’s 27.64% reproduced baseline. [R24, R25]

**Implication for CORA.** Use such systems as candidate generators and serious experimental baselines where access, cost, and competition rules permit. Keep the checker independent. A model’s fluent self-explanation is not the evidence for its own correction; the evidence is the executed prediction and the outcome of the agreed test.

## 4.6 Algorithm search and scientific agents are already hybrid

AlphaEvolve combines model-generated code with executable evaluation and evolutionary search. Google’s co-scientist work describes multi-agent scientific hypothesis development and experimental follow-up. These examples make the binary “neural guessing versus symbolic reasoning” framing unhelpful. [R26, R27]

WoFT studies formal decoding and learned use of grammar structure. It addresses important syntactic and representational issues, but syntactic validity does not establish a scientific hypothesis’s meaning or truth. It is especially relevant to Toni’s grammar question and to compiling untrusted candidate programs safely. [R29]

## 4.7 A capability audit, not a winner table

For every comparator, ask the same questions: What is learned? What is fixed? What feedback is available? What is actually executed? Who supplies the specification? What cost is counted? Which domains are independently evaluated? Are incorrect repairs and losses reported? Can the result be reproduced outside the developer’s chosen examples?

Published evidence supports substantial progress. It does **not** justify a universal conclusion that the entire problem is solved, nor a universal assertion that frontier models lack reasoning. The defensible research gap is an explicit experimental target with meaningful controls. The exact competitors, software versions, and reporting standards will keep changing.

# 5. Biological reasoning: where the hard evidence lies

## 5.1 What advances should be acknowledged

ESM3 jointly models protein sequence, structure, and function; its authors experimentally produced a divergent fluorescent protein. That is a concrete example of learned biological regularities supporting an experimentally tested design. It does not establish that the model has induced an explicit, transferable grammar of organismal biology. [R30]

A 2025 perturbation benchmark found that the evaluated deep models did not outperform simple linear baselines. Later work such as STATE reports improvements under its own perturbation protocols; STRAND studies sequence-conditioned transfer, and VCLMU proposes latent mechanism-centered modeling. These findings should not be collapsed into either “foundation models do not work” or “cell prediction is solved.” Dataset, intervention, context, baseline, and output metric determine what each result establishes. [R32, R33, R35, R36]

The Mechanisms Matter preprint focuses on transportability of perturbation effects across contexts. It makes a useful target for the proposed research: similarity of measured distributions is not itself a sufficient guarantee that an intervention behaves the same way elsewhere. Treat the preprint as evidence about its tested settings, not a definitive law covering all cell models. [R34]

## 5.2 Six persistent scientific issues and how to test them

| Issue | Why it matters for a reasoner | Evidence required in the proposed pilot |
|---|---|---|
| Meaning of variables | A numerical feature need not correspond to a stable biological entity. | Assay metadata, units, measured-versus-latent distinction, and expert-approved target definitions. |
| Hidden context | Similar observations may arise through different mechanisms. | Held-out contexts and interventions; record assumptions about transport. |
| Population heterogeneity | A mean response can hide mixtures, variance changes, or differential survival. | Distribution-aware predictions and controls, not only average expression error. |
| Time and history | A static snapshot may not identify trajectories or adaptation. | Time-resolved or otherwise discriminating observations before temporal claims. |
| Measurement and batch | Technical variation can resemble a biological effect. | Independent batches, sham controls, randomized processing where feasible, and measurement-model tests. |
| Scale and validation | Molecular, cellular, tissue and organismal conclusions require different evidence. | A bounded endpoint, biological replicates, replication, and a clear limit on downstream extrapolation. |

This table is a proposed experimental checklist, not a claim that the supplied Pierce dataset has all these problems. The broader concerns are motivated by the transcript and the biological-modeling literature. [L01, R13, R18, R31, R34]

## 5.3 Two different causal claims must never be merged

**Algorithmic causality:** did using a particular trace, operator, or repair policy cause the algorithm’s measured improvement? This is tested through controlled software interventions and paired evaluations.

**Biological causality:** does an intervention on the biological system change an outcome through the proposed mechanism? This needs an appropriate experimental or identification design for the physical system.

Showing that deleting a code module lowers prediction accuracy establishes neither the biological mechanism encoded by that module nor the safety of a proposed real-world intervention. Similarly, a verified biological effect does not isolate which AI component was responsible for proposing it. The dossier’s pilots evaluate these claims separately.

## 5.4 A sensible first biological question

Start with the displacement-versus-dispersion context mentioned by Toni, **only after Pierce confirms its meaning and the available data**. A provisional toy interpretation is a change in location of a distribution versus a change in spread or mixture. That interpretation is not attributed as the actual completed method. It is a proposed way to make the abstract question testable.

A research system might first assume that a condition causes a uniform shift. It then detects structured residuals inconsistent with that model. Candidate revisions could introduce a variance term, a mixture, a batch adjustment, or a request for replication. The critical result would be selecting a revision that improves held-out observations without adding unsupported biological claims. A toy numerical success is an interface demonstration; only independent real data establish biological relevance.

# 6. What CORA actually establishes

## 6.1 Use the newest audit, not the most flattering old sentence

The supplied materials are a sequence of development records, not one synchronized experimental release. The October 15 verification report is the latest inspected summary for several outcomes. It records the failed mixed pilot, absence of a real60 FHR extension certificate, and a grouping-program representation adapter that exists but has no established benefit. A new Athe session must reconcile actual files and hashes before publishing updated claims. [L04]

| Component | Supported statement | Claim not established |
|---|---|---|
| Native object audit | Six correct, zero incorrect accepted predictions on 60 exposed training-development tasks. | Error-free generalization or full-pipeline precision. |
| Candidate availability | A correct candidate appeared on eight of those tasks; asset-loaded first-fit without the gate gives eight correct and 25 wrong. | That selection alone can solve tasks with no correct candidate. |
| Whole harness | Earlier development record gives 12/60; arbitration shadow gives 14/60 without losing those correct answers. | A submitted Kaggle improvement or new capability invention. |
| FHR | Typed construction, reversible installation, fold-local rebuilding, and a synthetic witness. | A causal correctness gain from authentic failure information. |
| Latest application | Mixed pilot fails; real60 FHR adds no extension certificate. | Real ARC transfer of the synthetic witness. |
| Selection study | 64.1% versus 58.0% on 657 supplied-candidate synthetic queries. | An integrated native solver score or biological result. |
| NVARC | Official public 27.64% in supplied submission records. | An original CORA neural algorithm. |

Sources: native/FHR status and corrected configuration counts [L04, L05]; older harness and NVARC deployment evidence [L02, L03]. These are reported local results, not computations rerun for this dossier.

## 6.2 The automatic trigger is a symptom detector

CORA-FHR reads the native solver’s recorded constant-growth `pattern` fallbacks. The retained objects, added cells, segmentation view, and demonstration identity define what the constructor attempts to explain. The programmed pathway looks for repeated support across demonstrations and tries a geometric expression. The mapping from that symptom to growth construction was designed by the researcher; it is not a learned general repair selector. [L02]

This distinction matters. “The solver used a pattern fallback” is observable. “The true cause is a missing geometric capability” is a stronger interpretation that can be wrong. Incorrect correspondence or insufficient demonstrations can produce the same symptom. The failure funnel also contains categories determined with an independent evaluator’s hidden answers; those categories cannot be silently reused as inference-time features.

## 6.3 The 37,750 expressions are neither 37,750 hand-written answers nor unrestricted invention

The recorded G-grow language has ten sources and fifty transforms. It enumerates 500 one-transform expressions, 25,000 two-transform expressions, and 12,250 same-source unions. These total 37,750 **syntactic expressions**; different expressions can have identical behavior on some or all inputs. The grammar and its constituent semantics are predefined. [L02]

Task-specific selection and construction are automatic, but there is no demonstrated invention of a new foundational primitive. An extension can still be valuable when it makes a useful composition accessible to a bounded native solver. That is an engineering and learning question about availability and cost, not a claim that the operation is uncomputable in any pre-existing language.

## 6.4 What the synthetic witness really shows

On `dev_D3_04`, the system constructed `ring(8)[part_minority]`, installed it in the unchanged native reasoner, independently rebuilt it in all three leave-one-out folds, and produced a correct held-out prediction. Removing the extension removed the certified gain. However, failure-blind construction reached the same result. The planted union with a hull was degenerate on the generator’s single-minority-cell objects; it did not require a nontrivial two-branch rule. [L02]

The three correct extension certificates in the 27-task comparison are not three new independent inventions. They include one D3 new-composition witness and two already-available reach-family cases. “Zero wrong extension certificates” is an incremental statement; native baseline errors on adversarial controls can remain in the final system through fallback. [L02, L04]

## 6.5 What the candidate-selection study adds—and does not add

The SAC study compares already-supplied programs by their behavior after lookup-parameter refitting and their fitted table sizes, with learned-selector fallback. Its reported gain of 6.1 percentage points is on synthetic program selection. The comparator decides 133 of 657 queries, with 115 correct decisions; 524 use the baseline. The donor-control analysis did not isolate the mechanism causally, and family concentration limits breadth. It is not a measured replacement for native CORA ranking. [L04, L05]

Keep this result because it provides a concrete, useful question: when candidates agree on demonstrations, can deliberate testing help choose? But do not treat this selection component, FHR construction, separate VDCG reuse, and NVARC as one already-evaluated autonomous learner.

## 6.6 The practical bottleneck suggested by the record

The record supports investigating the entire path from useful candidate to valid execution. A proposal may fail because it fits the wrong correspondences, cannot be routed to the right objects, does not survive reconstruction, or is simply wrong. The failed mixed pilot and the explainer’s description of proposed-but-unused operations make this worth inspecting. The exact failure stage must come from the retained run logs, not from extrapolating a summary. [L02, L03, L04]

**Priority:** first obtain one reproducible, end-to-end real-development gain from a bounded original CORA component, then test whether failure evidence was responsible. Do not enlarge the grammar to conceal an installation, routing, or grouping defect.

# 7. The research claim worth trying to earn

## 7.1 A narrower hypothesis is stronger

**Proposed hypothesis:** with a fixed budget and shared revision resources, an evidence-based policy over typed component changes achieves better independently evaluated predictions—or equivalent predictions at lower total cost—than a strong failure-blind policy, without increasing harmful revisions. A learned policy then retains a measurable advantage on a second semantic domain under a separately frozen transfer protocol.

This is deliberately conditional. The outcome may be that failure traces add no useful information beyond ordinary residuals and candidate features, or that a simpler selector is sufficient. That would be a valuable boundary result and a reason to simplify the system.

## 7.2 A trace is not free new evidence about the world

For a fixed engine and observations, a trace is a computation on information already available. It does not reveal a hidden test label. Its possible advantage is that it makes a useful constraint or conflict cheaper to access within a bounded budget. A fair blind comparator should therefore receive equivalent observations and allowed computation; it should not be crippled by withholding ordinary geometry, size, or correspondence information.

The most meaningful claim may be **efficient allocation of computation** rather than an information-theoretic discovery. A controller that avoids a thousand useless candidates or decides that one more observation is necessary could be valuable even without increasing representational expressiveness. Measure that possibility instead of forcing every success into “new primitive invention.”

## 7.3 Three things that could distinguish a future CORA study

| Candidate contribution | Required evidence | Failure condition |
|---|---|---|
| Typed, minimal revision selection | Same repair options; real, masked or shuffled trace; paired out-of-sample outcomes and compute. | Feature-only or blind search matches it at equal cost. |
| Evidence-conditioned applicability | A constructed operation is used on appropriate objects/contexts and withheld elsewhere. | Gain vanishes under colour/size shortcut controls or depends on target leakage. |
| Transferable revision policy | Frozen policy improves a second domain relative to fresh or domain-only alternatives. | Only wrappers transfer, or target-specific redesign accounts for all improvement. |

These are proposed contributions, not claims of historical novelty. Popper, library learning, agentic skill accumulation, and MDA must be explicitly discussed in any resulting paper. [R05–R10, R28]

## 7.4 A useful research artifact: the revision record

Export each candidate revision as an inspectable record with its parent system hash, evidence origin, changed component, typed inputs/outputs, executable semantics, applicability condition, tests, resource use, rejected alternatives, and rollback result. Add the scope of the claim: finite-example validation, theorem proof, simulated transfer, or real experimental support.

The record is not itself a moat or a scientific breakthrough. Its purpose is to make controlled comparison possible and to prevent a model from turning a plausible narrative into an accepted change. Adoption by independent users would be stronger evidence than a dashboard produced only by the developing lab.

# 8. Proposed architecture: a small kernel, several replaceable proposal sources

## 8.1 Keep the trusted core small

The user’s proposed flow is a good research map. Implement it as an iterative process with an independent verifier, not as an unrestricted agent permitted to edit its own success criteria. Most new work should be adapters and experimental controls around the existing engine before any broad redesign.

```text
Observations + question + provenance
       |
Representation proposals <-----> executable hypotheses
       |                              |
       +------ structured failure evidence ------+
                                                  |
                                    bounded revision policy
                           search / representation / rule / evidence
                                                  |
                                 sandboxed executable candidate
                                                  |
                           independently controlled verifier
                                                  |
                              commit / abstain / rollback
                                                  |
                         retention only under a separate test
```

**Proposed architecture, not a completed integrated system.** The proposal agent cannot modify the checker. Representation and hypothesis search are iterative; the existing FHR implementation supplies only part of this pathway.

The diagram is a **proposal**. The existing FHR pathway supplies part of construction, temporary execution, and checking. Representation induction, general repair selection, learned grammar revision, long-term retention, and biological transfer are not all implemented or validated merely because the diagram connects them.

## 8.2 Observation and question contract

Each domain supplies observations, a query, units or coordinate conventions, permitted operations, measurement provenance, and constraints on what may be learned from each split. In ARC, demonstration outputs are permitted and final query outputs are forbidden. In a scientific task, distinguish measured quantities, latent hypotheses, intervention metadata, and future measurements.

An observation parser should not smuggle in task-family labels, generator state, specimen identities that leak the answer, or hidden test summaries. A frozen content-level test should confirm that changing withheld answers cannot alter solver-visible inputs, caches, filenames, logging features, or candidate order.

## 8.3 Representation proposals and grounded interfaces

Representations should be executable mappings from observations to entities, attributes, relations, or distributions. Begin with the existing grouping-program adapter, after auditing it. Permit a small declared family of revisions such as connectivity, part/whole grouping, or a distribution summary. Do not immediately train a universal latent-space model.

A proposed representation must state what it preserves and what it discards. A mean-only summary discards variation; grouping by colour discards cross-colour parts; a graph may discard coordinates. Evaluate whether the discarded information matters to the target prediction. In biology, an expert-approved measurement contract remains necessary even when the representation is learned.

## 8.4 Hypothesis construction and compilation

Native CORA, G-grow, learned library proposals, and optional neural systems can propose hypotheses. All return the same typed intermediate form. A compiler either translates the hypothesis into a supported executable object or rejects it. Reject unrestricted code that can access answers, network services, uncontrolled files, or change the evaluator.

For an operator to help the native solver, it needs more than correct output cells in isolation. It needs an **applicability condition**, compatible variables, and a route into the complete task program. Treat these as part of the candidate. In a new development branch, a guarded operator could pair “which objects this applies to” with “what transformation it performs.” This is a proposal, not a repair already justified by the failed pilot.

## 8.5 Failure evidence and controlled probes

Record stage, proposed representation, candidate structure, parameter dependence, residuals, rejected constraints, unresolved ambiguities, resource exhaustion, and software exceptions. Keep the software-error category distinct from semantic inadequacy.

The controller may use a bounded probe portfolio: increase search within the same language; change grouping while keeping transformation families fixed; change parameters; propose a new composition; or decline to commit. In scientific settings it may also propose a permitted measurement. Probes are interventions on hypotheses, not access to hidden answers. Their total cost is part of the method’s budget.

## 8.6 The revision policy

Start with a transparent policy trained or calibrated on separate development cases. It should output a ranked action set and an abstention condition, not a confident single diagnosis by default. A simple interpretable ranker is preferable to a large new policy network until there is enough independently grouped training data.

Two experiments must be separated. To study **selection**, hold a candidate revision pool fixed and vary the information used to choose. To study **construction**, let methods generate different revisions under equivalent capabilities and budgets. Requiring identical candidates in the construction experiment would prevent the proposed mechanism from changing what is built; allowing different candidate pools in the selection experiment would confound the selector.

## 8.7 Independent checking and commitment

Keep the existing full reconstruction and tie-abstention requirements unless a separately justified protocol changes them. Within each outer fold, reconstruct every adaptive component that used the omitted example—including grouping, extraction, proposed guards, operation choice, learned per-task parameters, and neural per-task adapters where applicable.

Checks should distinguish successful compilation, demonstration fit, exact omitted-example prediction, correct full query prediction, and absence of regression. A candidate can pass the first three and still fail later. Commit the prediction and its provenance before evaluator access. The checker’s implementation and thresholds are not writable by the proposal agent.

## 8.8 Retention and reuse

A task-local extension is not automatically a reusable skill. Keep a versioned candidate library with eligibility conditions and expiry or retraction. A promotion study must show usefulness on later, separately held-out tasks, with construction disabled to prove reuse, and with an equal-budget no-memory comparator. Measure both accelerated solving and errors introduced by inappropriate reuse.

The separate VDCG work may inform a future interface specification, but the current protected implementation is not authorized for integration by this report. Reuse verified summaries; do not inspect protected outcomes or present separate accomplishments as integrated CORA evidence. [L04]

# 9. A staged pilot that could answer part of Toni’s question

## 9.1 Stage 0 — repair the experimental pathway, not the theory

**Purpose:** identify whether the current blocker is construction, routing, applicability, verification, or a software defect. Read existing run rows before launching any experiment. Check actual exit codes, all expected arms and task rows, manifests, and exception records; a string such as `MIX DONE` is insufficient because a previous wrapper printed it after failure. [L02]

Use at most twelve declared integration cases built from already-permitted development material: successful replay, wrong operator, missing operator, inappropriate applicability, ambiguous evidence, and software-error handling. Preserve the original failed run and its verdict. A fix receives a new version and test; it does not convert the original run into a success.

**Exit gate:** deterministic executable behavior, restored native state, correct metadata, expected acceptance/rejection, and no leakage. This is engineering readiness, not scientific proof. If no plausible valid candidate ever reaches the full engine, stop before spending resources on a large comparison.

## 9.2 Stage 1 — component-level diagnosis under controlled ambiguity

**Proposed development size:** 48 tasks, eight in each of six intentionally different situations. The number is a feasibility budget, not a claim of adequate statistical power.

| Situation | Why it is included | Critical control |
|---|---|---|
| Search-limited | A useful native program is available but not reached within the base budget. | Same language, matched extra search, no oracle hints. |
| Representation mismatch | A declared alternative grouping supports the transformation. | Both methods may discover it; counterbalance colour, size, and position. |
| Parameter/program mismatch | Available structure is adequate but a parameter or selector is wrong. | Do not force an unnecessary language expansion. |
| Composition missing from native vocabulary | A useful bounded composition is unavailable to the native engine. | Strong blind constructor with the same construction language and compiler. |
| Insufficient evidence | Distinct explanations agree on all supplied examples. | Abstention or an evidence request must remain a legitimate outcome. |
| Measurement/software issue | A failure is not repaired by conceptual invention. | Detect invalid inputs or implementation errors; do not reward masking the error. |

Generate case definitions and seeds before running the comparison. Use counterbalanced nuisance features and negative controls. Do not select tasks because authentic-trace CORA wins. Generator-side knowledge may label a diagnostic test case but must not enter the solver or be confused with authentic inference-time diagnosis. These are stress tests, not a natural distribution of real ARC problems.

## 9.3 The necessary comparison arms

The baseline portfolio should be genuinely competitive. A weak colour-only clustering control on a size-separated task is not enough.

| Arm | Information and behavior |
|---|---|
| A — frozen | Existing reasoner and its documented output/abstention policy. |
| B — matched search | More computation within existing representations and operations. |
| C — strong failure-blind revision | Same observations, object information, representations, construction language, compiler, features such as size/colour, and total budget; no privileged authentic trace labels. |
| D — authentic-trace revision | Same resources; uses the structured trace and allowed probes to choose a revision. |
| E — masked/shuffled-trace revision | Matched records and dimensionality, with the informative correspondence between trace and task removed under a predeclared scheme. |
| O — diagnostic oracle | Receives a generator-side fault label for a separate ceiling analysis only; never a valid solving result. |

A frontier-agent baseline with the same tools is valuable where available. Its token and tool budget must be recorded; it is not enough to compare a carefully engineered CORA portfolio against an unassisted language-model response. Do not describe a from-scratch reproduction of a major external system as “matched MDA” unless the implemented scope really matches; label a restricted adaptation accordingly.

## 9.4 What to measure

Primary outcomes are exact task correctness on ARC-style tasks, paired gain over C, and harmful revision rate. Report the full matrix: wrong-to-right, right-to-wrong, unchanged-correct, unchanged-wrong, and abstentions. Add CPU/GPU time, model tokens, wall time, memory, proposals tested, and whether the selected revision was actually used.

Report agreement and disagreement in chosen repair class; validity of applicability guards; extension removal; and reversion to the original state. Use a fixed-program-pool subexperiment to isolate selection. Use a separate budget-matched generation experiment to test construction. Count task families or underlying generation mechanisms as dependency clusters, not every near-duplicate query or leave-one-out fold as an independent sample.

Do not require every task to receive one “true” cause if two repairs are equivalent. Record minimal sufficient repair sets and interactions. An oracle label can be useful for constructed cases, but prediction under independent conditions remains the primary criterion for naturally occurring tasks.

## 9.5 Development stop rules

Before execution, choose a modest resource cap and stopping rule. A suggested gate is at least two reproducible newly correct development tasks with actual extension use, no new wrong commitment in the pilot, and some measurable advantage over C in correctness or predeclared total-cost utility. Passing this gate is **not** significance or generalization evidence; it only justifies a larger test.

If the blind portfolio matches authentic-trace performance, report that. If the gain is solely a size shortcut, routing fix, larger effective search budget, or weaker verifier, label it accordingly. If the pilot fails, close that version and record the bottleneck; a redesigned experiment needs a new version and new claims, not changed thresholds on the old results.

## 9.6 Stage 2 — prospective real-task and family-held-out evaluation

Use an independently frozen cohort whose membership and answers have not guided the proposed controller. A design target such as 240 tasks in 60 families is a **planning proposal**, not an already available clean benchmark and not a substitute for a power calculation. The existing 60 ARC training-development tasks are exposed and cannot become a fresh test by renaming them. The existing protected 80- and 120-task studies must remain untouched.

Choose one primary comparison and analysis before testing. A useful target is a practically meaningful paired improvement with a confidence interval excluding zero, along with a separately bounded harmful-revision risk. Determine feasible sample size from development discordance and family dependence. “Zero errors in a small pilot” alone does not establish a low deployment error rate.

Where real ARC task availability is constrained, distinguish three datasets: exposed real development tasks, independently authored synthetic/ARC-style families, and the official hidden competition evaluation. They answer different questions. A model trained on ARC material also carries prior exposure; audit preprocessing, duplicate content, and upstream checkpoints rather than claiming all local public tasks are uncontaminated.

## 9.7 Stage 3 — transfer the revision policy, not just the Python wrapper

Freeze the repair-selection policy learned or calibrated in the first domain. Give a second domain only the declared observation adapter, executable primitives, measurement contract, and permitted few-shot calibration. Compare against a new policy trained from scratch, a domain-only baseline, a strong generic agent, and an ablated policy without source-domain experience.

Measure adaptation cost and resulting prediction quality. Using the same code framework in two domains demonstrates software reuse. Using an unchanged pretrained policy that measurably improves the second domain demonstrates policy transfer. Discovering a stable abstraction that enables new executable reasoning in the second domain is a stronger result. Do not call a numerical encoding of the same grid puzzles semantic transfer.

## 9.8 What would genuinely answer Toni’s question?

A convincing *partial* answer would show one end-to-end revision policy selecting useful representations or operations from limited observations, a causal contribution of its failure evidence under strong controls, and a benefit when the policy is frozen and applied to a different semantic setting. Independent biological replication would extend the claim further.

No finite pilot proves unrestricted reasoning across every domain. The correct output is a ladder of increasingly demanding claims with clear failure conditions. The architecture earns scientific content through those experiments, not through the breadth of its vocabulary.

# 10. Making ARC-AGI-2 progress and a better Kaggle entry

## 10.1 What the NVARC run taught us

The supplied record reports submission 57160429 completed with public score 27.64%; native CORA’s earlier submission scored 0.00%. The NVARC checkpoint and underlying Qwen test-time-adaptation approach were reproduced rather than newly invented. Compatibility, coverage checks, provenance, and deployment were the user’s engineering work. These results are not live account checks. [L02]

The official NVARC repository contains synthetic-data training, adaptation/search machinery, and multiple branches. The user’s notebook follows the Qwen3-4B branch; it should not be equated without a configuration audit to every component in the original winning system. The ARC Prize 2025 report supplies historical context, not a prediction of the current private score. [R37, R38]

Three lessons follow. First, a pretrained proposer and task-time adaptation can supply useful candidates that native CORA lacked. Second, a deployable pipeline needs strong engineering beyond an abstract mechanism. Third, a positive aggregate score does not say whether any new CORA component contributes. The next experiment must measure that component’s marginal value.

## 10.2 The attempted shortcut did not work

On the local stand-in there were 259 output positions: 112 distinct second candidates, 147 `[[0]]` placeholders, and zero duplicate first/second genuine predictions. NVARC solved 248 outputs; native CORA solved 47, all already covered by NVARC. Filling placeholders with native outputs gained zero and lost one, because `[[0]]` happened to be the correct one-cell answer in one task. Both systems had exposure to this training material, so the comparison is mechanical, not clean generalization evidence. [L02]

The general correction is important: **a default prediction is still a submitted answer, not a valueless empty slot**. Replacing a duplicate may preserve the set of existing answers; replacing a default or a distinct second answer may not. In this run there were no duplicate slots offering that narrow guarantee.

## 10.3 Two tracks, two scientific meanings

| Track | Goal | Interpretation |
|---|---|---|
| Original CORA method evaluation | Deploy the actual bounded construction/revision loop, without NVARC answer substitution. | A positive score would establish some unseen-task success for that submitted system; attribution to FHR still needs ablation. |
| Competitive hybrid | Use NVARC as a proposer, with a measured CORA contribution to candidate construction or selection. | A higher score establishes performance of the hybrid, not of CORA alone or the causal role of failure diagnosis. |

Do not hold the entire research direction hostage to beating 27.64% in the next submission. Equally, do not treat a zero-score mechanism deployment as proof of working generalization. A corresponding method submission can support a research-paper route, but the evidence ceiling remains the observed outcome. [R41]

## 10.4 The most plausible near-term hybrid experiment

Keep the incumbent notebook, checkpoint, generation settings, seeds, and candidate files pinned. On authorized development tasks, collect a richer **untrusted proposal pool**: native programs, FHR candidate operations and applicability conditions, and neural candidates. Measure an offline oracle coverage diagnostic using development labels only after candidates are committed. This determines whether failures are mostly missing candidates or poor ranking.

If correct candidates are absent, invest in construction or representation. If they are present but excluded from the two answers, invest in selection and calibration. If candidates fit demonstrations but fail independent reconstruction, improve the construction or its applicability rather than drop verification. A selector cannot choose an answer that no component generated.

Use the native/FHR trace to propose a bounded executable hypothesis, not to canonize a neural grid as a label. A neural answer can suggest “try a part-based transformation,” but the candidate must explain the allowed demonstrations and pass the independent procedure. A model-generated explanation is a proposal until checked.

## 10.5 Test-time training complicates leave-one-out

If a neural adapter was trained on all demonstrations, its proposals have seen the demonstration supposedly omitted by a subsequent fold. Reusing that adapter in leave-one-out construction invalidates a claim of full fold-local independence. Either reconstruct/adapt the proposer within each fold, use a proposer with a documented independent information boundary, or explicitly limit the certificate to the downstream symbolic component.

Fold-local adaptation can be expensive. Count it. Do not silently compare a cheap blind baseline with an authentic arm that receives additional neural training or previously computed oracle proposals. Pretrained weights may already contain public ARC exposure; fold-local fitting alone does not remove historical contamination.

## 10.6 Conservative integration and scoring accounting

For a fixed set of baseline candidates, define a gain as a formerly unsolved output becoming solved and a loss as a formerly solved output becoming unsolved. The hybrid’s net score change is the appropriately weighted gain minus loss. This identity does not predict the hidden score. Preserve the official task/output weighting and report per-output counts separately from averaged task scores.

Calibrate a replacement policy on independent development data. Consider expected exact-match utility and uncertainty, not an uncalibrated Boolean certificate. Keep baseline attempts when the evidence is insufficient. Report the full system’s error rate as well as incremental repair errors. A rule that preserves a baseline with false acceptances cannot honestly claim a globally error-free result.

## 10.7 Deployment gate

The official competition specifies two attempts and offline notebook execution under runtime limits, currently up to twelve hours in the published description. Recheck the exact competition page and authenticated submission allowance before action. [R39, R40]

Before a new submission, require correct schema on every output, real rather than fabricated prediction coverage, hard global and per-task budgets, graceful serialization, no uncontrolled access, and no regression in the incumbent neural computation. Allocate symbolic work from an explicitly reserved budget. Compare total hybrid resource use, not “neural time plus free CPU.” The recorded 4.34-hour stand-in run does not guarantee hidden-run timing. [L02]

Submit only a pinned version whose claimed contribution is actually executed. Record its ID, configuration, and result when available. A score-only experiment cannot identify which hidden tasks improved, and repeated leaderboard tuning can weaken the independence of the public result. Preserve the private evaluation as an unknown, not a promised increase.

## 10.8 Priority before the summit

The most useful short sprint is not retraining Qwen from scratch. It is auditing the current FHR failure stage, testing one bounded applicability/routing or construction change on allowed development cases, and measuring actual complementary predictions. If no real gain appears, retain the neural incumbent and present the honest methodological result. Kaggle scheduling uncertainty must not jeopardize the printed poster.

# 11. A biological pilot connected to the discussion

## 11.1 First obtain a collaborator-approved problem contract

Before implementation, ask Pierce and Toni to identify the actual data, the meaning of displacement and dispersion in their work, the observational unit, available replicates, known nuisance variables, the target scientific question, and the acceptable independent validation. Ask Chris which completed representation or image-analysis result belongs in the collaborative poster. Use their approved figures and source records, not reconstructed results from conversation.

Until those facts are supplied, label the biological work **proposed**, and any numerical example **synthetic**. The existence of separate biological projects does not authorize access to their protected repositories or establish integrated CORA transfer. [L01, L04]

## 11.2 A deliberately small first problem

A provisional pilot could ask: when a condition changes a measured distribution, should the system revise a location model, a spread model, a mixture representation, a context adjustment, or the evidence collection plan? These are alternative executable explanations and measurement decisions. They are not automatically cellular mechanisms.

Use a toy generator to test the software contract first. Include location-only change, spread-only change, mixture-weight change, no-effect controls, batch artifacts, and combinations. The observed sample size, noise and context should vary independently of the true change type. The generator’s condition labels must not leak through filenames or fixed nuisance features.

A shared mean does not distinguish unchanged distribution from a symmetric spread change. A shared variance does not identify a particular mixture. Construct paired examples where naive summaries fail, then test whether the policy chooses a discriminating representation or declines to decide. This is a proposed identifiability test, not a claim that more summary statistics always solve the problem.

## 11.3 Real-data stage

Select a limited, scientifically meaningful endpoint with a feasible independent cohort or held-out batch/condition. The initial study may use 16–40 independent condition–replicate units as a feasibility target, but the actual count and power must be determined with the collaborators. Thousands of cells from one preparation are not thousands of independent biological interventions.

Baselines should include the existing human-authored analysis, no-change/mean predictors where meaningful, simple distributional or linear models, and an appropriate contemporary domain model. Compare at equal access to data and tuning. Do not insist on a huge foundation-model benchmark if it is irrelevant to the approved endpoint; do not omit a strong simple baseline because it is unimpressive.

## 11.4 Predictions, checks, and uncertainty

A biological output should be a defined quantity or distribution, with uncertainty and the assumptions needed to interpret it. Score point predictions and distributional calibration as appropriate; predefine the primary metric and clinically or scientifically relevant error costs. Assess changes in means, spread and other features only when they correspond to the approved question.

Validation may include held-out perturbations, contexts, batches, and independent experimental replication. The system must distinguish model inadequacy from noisy measurement and limited power. Avoid choosing validation subsets after seeing which one makes a revision successful. Freeze analysis plans and expose negative findings.

## 11.5 Active evidence as a possible differentiator

Sometimes the best revision is not a better function but a better experiment. Among safe, permitted measurements, choose one expected to distinguish competing hypotheses. Compare against random or standard experiment selection under the same number and cost of measurements. MDA is an essential comparator or source of methods here; do not present value-of-information as new. [R28]

Do not treat a proposed intervention as a validated therapeutic recommendation. This pilot is research decision support, with collaborator oversight and appropriate institutional permissions. Its success criterion is improved independent scientific inference, not autonomous clinical action.

## 11.6 A transfer claim ladder

| Achieved result | Accurate wording |
|---|---|
| Same code runs on grids and matrices | A portable software interface. |
| Same algorithm succeeds after independent domain-specific fitting | A method applicable in two settings. |
| Frozen source-domain policy improves the target over matched alternatives | Measured transfer of a revision policy. |
| A source-learned abstraction is discovered, mapped and useful in the target | Evidence of abstraction transfer under the tested conditions. |
| Real biological outcome replicated with the proposed decision support | Validated biological utility for the specified endpoint. |

Only the last three meaningfully test increasingly strong versions of Toni’s reasoning-transfer goal. None follows from renaming grid cells as molecules.

# 12. Broaden the summit poster without replacing evidence with aspiration

## 12.1 Recommended framing

**Proposed title:** Learning What to Change: From Visual Reasoning to Scientific Hypothesis Revision.

**Subtitle:** CORA experiments on ARC-AGI-2, a failure-conditioned construction prototype, and a proposed biological test of reasoning transfer.

This title places the big question first, as Toni suggested, while the subtitle prevents readers from mistaking a broad architecture for completed cross-domain learning. Keep the original CORA title as a documented earlier version. Get collaborators’ agreement on content, attribution, and any unpublished results before printing. [L01]

## 12.2 Three-column narrative

| Column | Content to show | What to avoid |
|---|---|---|
| 1 — The scientific question | Sparse observations, different representations, competing explanations; Toni’s reasoning-transfer question; a small illustrative ambiguity. | A catalogue of all projects or a claim to have solved general intelligence. |
| 2 — What CORA has established | Configuration-correct real-task failure audit; one real logged FHR synthetic witness; a compact control comparison and explicit negative result. | Mixing 25 and 26 wrong gate-off answers, three certificates with three new inventions, or synthetic selection with ARC accuracy. |
| 3 — The next falsifiable test | Proposed typed-revision architecture, matched-controller pilot, collaborator-approved biological question, and a clear evidence ladder. | Invented biological figures, a hypothetical demo presented as a completed transfer, or an unearned “first” claim. |

The NVARC 27.64% and native CORA 0.00% belong in a compact, separately labeled benchmark box. They provide context, not the visual centerpiece. The independent SAC selection result may appear only if its separate supplied-candidate setting is explicit and space permits. [L02–L05]

## 12.3 Correct the evidence language

Replace “the checks are not the problem” with “in this object-layer development audit, verification rejected many incorrect fits; improving candidate construction was the larger observed limitation.” Use “not adopted” rather than “not run” for a tested but rejected repair. Label zero errors as zero **observed new extension errors**, not an absolute system guarantee.

Update all stale “NVARC pending,” “FHR designed but not run,” and “mixed pilot running” passages from verified records. Show 27 without assets versus 26 with assets only when the configuration distinction is necessary; otherwise use one pinned headline configuration. The latest asset-loaded audit reports gate-off eight correct and 25 wrong, rather than the older poster’s 26 wrong. [L03, L04]

## 12.4 A demo that survives close questioning

Use the recorded `dev_D3_04` trace. Show the input, the unsupported memorized-growth explanation, the constructed operation, the three independently reconstructed folds, the committed query prediction, and the removal ablation. Then show that the matched failure-blind constructor also succeeds. This last screen is part of the demonstration, not a footnote to hide. [L02]

Clearly distinguish replaying recorded evidence, re-executing the standalone operation, and rerunning the entire original engine. A replay is useful and reproducible without being a live autonomous system. Keep local files and required packages on the laptop; do not depend on SSH or conference Wi-Fi. Use an optional separate synthetic numerical illustration for the transfer interface, clearly marked “proposed biological analogue; no biological result.”

## 12.5 Explainer structure

The explainer should answer in order: What question are we asking? What do grammar, representation and operation mean? What actually happens automatically? What was measured on real versus synthetic tasks? Why did the failure-blind control matter? Why can biological data require a different validator? What experiment would convince us next?

Include a 20-second introduction, a 90-second walkthrough, one deeper technical explanation, and a reproduction appendix. Move implementation paths and historical diagnostics to the appendix rather than crowd the spoken story. Cite current primaries to acknowledge frontier systems and the closest prior art.

## 12.6 What to discuss at the summit

With Chollet, focus on skill-acquisition efficiency, priors, and whether the proposed transfer protocol actually measures learned reasoning rather than supplied machinery. With Mike Knoop and Greg Kamradt, focus on a reproducible evaluator-ready method and a realistic route from the research experiment to an official benchmark. The event’s advertised scientific program makes MDA and grammar-structured reasoning especially relevant conversations. [R01, R42]

The most productive request is specific: help stress-test the cleanest experiment that could distinguish a useful revision policy from better generic search. Avoid asking an audience to accept novelty because the diagram spans ARC and biology.

# 13. A startup research lab pitch that can withstand diligence

## 13.1 The problem to own

**Working proposition:** help researchers decide whether to change a model, change its representation, or collect more evidence—and produce an executable record of why that decision was warranted.

This is narrower than building the next general biological world model. It could complement strong upstream predictors. The first customer problem should be a repeated, expensive scientific decision where unsupported corrections, hidden batch effects, or uninformative follow-up experiments waste real effort.

## 13.2 What is available today

There is a research prototype of bounded executable construction and checking, a failure audit, a separate supplied-candidate selection result, and a reproduced neural baseline. There is no validated biological product, no demonstrated cross-domain revision policy, and no established neural–CORA benefit. These limits belong in diligence materials. [L02, L04, L05]

A founder’s credible asset is the ability to build and evaluate the proposed system, not ownership of third-party Qwen/NVARC capabilities or claims from unrelated collaborators. Obtain written agreement for shared results and distinguish company work, university work, and independent research before presenting commercialization rights.

## 13.3 Why someone might care despite EMET, Quine and frontier agents

The proposed product is not “an AI that generates hypotheses.” It is a workflow that makes a narrower decision testable: **which revision should survive, under what conditions, and what evidence would reverse that decision?** Its value would be demonstrated by fewer harmful revisions, better experiment selection, faster reproducible adjudication, or lower cost for equivalent scientific confidence.

Large platforms may already supply parts of this functionality, and can add more. A defensible advantage would need independent evaluations, domain-specific validation partnerships, high-quality revision/outcome data with permission, reliable integration, and a workflow users actually adopt. A generic agent wrapper or a renamed verification log is not a durable differentiator.

## 13.4 A staged 90-day research-company test

| Period | Deliverable | Continue only if |
|---|---|---|
| First 30 days | Reproducible bounded ARC revision experiment and one signed biological problem/data contract. | The mechanism works end-to-end and the target problem has usable independent evidence. |
| Days 31–60 | A shadow biological pilot against the existing analysis and strong simple baselines. | At least one predeclared scientific or workflow metric improves without hidden regression. |
| Days 61–90 | Replication on a second context or independent collaborator, with total-cost accounting. | The result survives outside the original developer’s chosen cases and users see a concrete benefit. |

Stop or reposition if users only need a conventional statistical analysis, if data rights prevent validation, or if a generic frontier agent achieves the same outcome more cheaply. That is an efficient discovery of product boundaries, not an excuse to invent stronger claims.

## 13.5 Suggested spoken pitch

“Powerful models can already propose answers and write code. My question is how a scientific system decides what to change when those answers fail. CORA provides a small executable setting in which I can test that decision, including the cases where my preferred failure-based explanation does not beat a simpler control. I want to turn that into a rigorously evaluated revision layer—first on visual reasoning, then on a specific biological measurement problem. The goal is not another plausible answer. It is a justified next model or next experiment, with a record that another researcher can challenge.”

This is a research pitch, not a statement that the product is already built. The strongest immediate ask is an independent evaluation collaborator, relevant compute or tooling, and a biological design partner—not trust in a universal reasoning claim.

## 13.6 Rights and disclosure

Review licenses separately for code, model weights, training data, figures, and artifacts. A publicly visible GitHub repository does not by itself grant an appropriate commercialization license. Competition-specific sharing and prize obligations also need review. Obtain university technology-transfer and, where appropriate, legal guidance before promising exclusivity or assigning IP. This dossier is not a legal opinion. [R40, R44]

Disclose substantive generative-AI assistance accurately in scientific materials. Do not put AI systems in author lists or conflate assistance with independently verified experimental findings. Make human and collaborator contributions explicit.

# 14. Execution roadmap and decision gates

## 14.1 Now through October 23

**October 17–18:** read and reconcile the latest repository state; circulate a one-page content outline with Toni, Chris, and Pierce; audit the failed mixed pilot and real-task application; identify one bounded integration hypothesis. Do not restart completed experiments. Prepare the evidence-corrected poster draft in a new directory.

**October 18–19:** run only the approved development integration check and any genuinely new, predeclared small pilot that passes readiness. In parallel, complete the offline demo and biological problem-contract draft. Do not make success in a new experiment a prerequisite for having an honest presentation.

**October 20:** freeze the poster’s claim set and authorship with collaborators. Decide whether a pinned Kaggle entry is technically valid and scientifically worth the submission. No score is assumed to arrive before printing.

**October 21:** print the agreed poster, consistent with the conversation’s Wednesday target; verify laptop demo and local backup. **October 22:** travel and rehearse. **October 23:** present completed evidence and the specific next test. The summit date is confirmed by its official page. [L01, R42]

## 14.2 The research should remain reversible

Use separate branches or versioned development directories. Preserve all frozen baselines and prospective datasets. Save the manifest before any labels are exposed. Record every attempt, including generation rejection, crashes and incomplete jobs. Never treat a failed process as a completed negative experiment or a fixed bug as retroactive confirmation of a theory.

A new session should have a short `RESUME.md`, a machine-readable ledger, a precise active-job list, and the one next command with its expected outputs. Large logs and historical transcripts belong on disk, not in every model context. Avoid multiple independent agents editing the same repository concurrently.

## 14.3 Decisions after the first new pilot

If a valid candidate is proposed but not applied, investigate the typed applicability and routing interface. If it is applied but fails reconstruction, investigate whether the candidate or evidence is insufficient. If the blind control matches it, keep the construction result and reject the trace-causality claim. If no candidate helps real tasks, separate an engineering/candidate-coverage problem from a broader representation-learning ambition.

Only after an end-to-end mechanism shows a defensible advantage should the next prospective cohort be authorized. The original protected evaluations remain sealed. A redesign of the scientific question requires a new protocol, not repurposing old withheld tasks after seeing development outcomes.

# Appendix A. The claims ladder for discussions and manuscripts

| Evidence | Permitted claim | Not implied |
|---|---|---|
| Program compiles and runs | Executable candidate. | Correct interpretation or prediction. |
| Fits supplied demonstrations | Consistent with those examples. | Generalization. |
| Fold-local reconstruction succeeds | Survives the specified omitted-example procedure. | Universal correctness or independent replication. |
| New composition is useful | Extended capability under declared baseline bounds. | New primitive or unrestricted language invention. |
| Removal loses the gain | The extension is necessary under the tested configuration. | Authentic failure evidence was necessary. |
| Authentic policy beats matched blind controls | Measured value of that information/policy under the protocol. | General diagnosis of all failures. |
| Same policy helps a distinct target domain | Scoped reasoning-policy transfer. | A universal scientific reasoner. |
| Biological prediction independently replicated | Utility for the stated experiment and context. | A full causal theory of the organism or clinical efficacy. |

# Appendix B. Answers to the hardest likely questions

**“Is this just program synthesis?”** The current constructor is bounded program synthesis. The proposed study asks whether component-level failure evidence improves revision choice and transfer beyond equally equipped synthesis. That additional result is not yet established.

**“Isn’t MDA already doing this?”** It is very close prior art. The next paper must specify a concrete comparison and not claim the broad loop as new. The proposed distinction is an explicitly audited policy over typed component revisions and its independently measured transfer; that distinction may or may not survive experiments. [R28]

**“Why use handcrafted operations?”** To make the initial search and evidence bounds explicit. Human-defined primitives do not invalidate learning, but their contribution must be counted. A new composition can improve search accessibility without increasing fundamental expressiveness. [R01, L02]

**“What did the failure trace add?”** In the completed matched synthetic comparison, no correctness advantage. It supplied a useful engineering signal and suppressed some unnecessary proposals, but that is weaker than improved solving. [L02, L04]

**“What does 27.64% show?”** Successful deployment of the separately reproduced NVARC Qwen pipeline on the official public evaluation. It does not validate CORA-FHR. [L02]

**“How do you verify biology?”** Against a collaborator-approved observable endpoint, appropriate uncertainty and controls, independent contexts/replicates, and eventually experiment. A symbolic certificate alone cannot turn an assumed biological model into a verified mechanism.

**“What is learned across domains?”** That must be specified before testing: a policy, abstraction, prior over revisions, or library element. Reusing the same code is not sufficient evidence.

**“What do you need from us?”** Help define an independently implementable benchmark and a biological target where incorrect revisions are costly and genuine validation is feasible. This makes the collaboration falsifiable rather than purely conceptual.

# Appendix C. Reading order and source limitations

Read L01 first for Toni’s question, then L04 for the latest CORA claim ceiling. Read MDA, Popper and DreamCoder before writing a novelty paragraph. Read Quine and EMET to understand the scientific-platform landscape, and the perturbation benchmark papers to design a biological test. Read the current Kaggle rules only when preparing the actual notebook submission. [L01, L04, R05, R06, R16, R17, R28, R32–R40]

The search covered historical diagnosis and grounding, program and grammar induction, feedback-driven agents, current frontier releases, biological modeling and transportability, formal verification, and official ARC specifications. Primary research and official descriptions were prioritized. It was a targeted research review, not an exhaustive systematic review with a preregistered search protocol.

Some public pages provide only abstracts or indexed primary excerpts; vendor systems were not run, private implementations were not inspected, and no local CORA experiment was rerun. Commercial claims are attributed, preprints are labeled, and missing disclosure is not treated as proof of missing capability. Current model and competition details were checked as of October 17, 2026 and can change.

The supplied local records contain different dates/configurations. Their reported counts are preserved with scope, and the newer audit takes precedence where explicitly stated. The full original voice transcript is not redistributed in this package; it includes unrelated conversation and personal material not needed for the research pitch.

# Sources

**[R01] Chollet (2019). On the Measure of Intelligence.** Research paper. Skill-acquisition efficiency; explicit priors and experience. Not a claim that all tasks are solved.  
Source: https://arxiv.org/abs/1911.01547 (accessed October 17, 2026).

**[R02] Reiter (1987). A Theory of Diagnosis from First Principles. Artificial Intelligence.** Peer-reviewed research. Model-based diagnosis predates modern language models.  
Source: https://www.sciencedirect.com/science/article/pii/0004370287900622 (accessed October 17, 2026).

**[R03] Harnad (1990). The Symbol Grounding Problem.** Author-hosted research paper. Historical framing of syntax and grounded meaning.  
Source: https://www.southampton.ac.uk/~harnad/Papers/Harnad/harnad90.sgproblem.html (accessed October 17, 2026).

**[R04] Solar-Lezama et al. (2006). Combinatorial Sketching for Finite Programs.** Author/institution publication record. Program synthesis with specifications and counterexamples; not equivalent to finite-example validation.  
Source: https://research.ibm.com/publications/combinatorial-sketching-for-finite-programs (accessed October 17, 2026).

**[R05] Cropper and Morel (2021; preprint 2020). Learning Programs by Learning from Failures.** Research paper / Popper. Generate-test-constrain induction; direct prior art for learning from failure.  
Source: https://arxiv.org/abs/2005.02259 (accessed October 17, 2026).

**[R06] Ellis et al. (2021; preprint 2020). DreamCoder.** Research paper. Program-library learning and learned search; direct prior art for abstraction growth.  
Source: https://arxiv.org/abs/2006.08381 (accessed October 17, 2026).

**[R07] Grand et al. (2024; preprint 2023). LILO: Learning Interpretable Libraries by Compressing and Documenting Code.** Research paper. LLM-assisted synthesis, compression and reusable libraries.  
Source: https://arxiv.org/abs/2310.19791 (accessed October 17, 2026).

**[R08] Zhu et al. (2024; preprint 2023). Large Language Models Can Learn Rules.** Research paper / HtT. Induction and checking of rule libraries; rule learning already has substantial prior art.  
Source: https://arxiv.org/abs/2310.07064 (accessed October 17, 2026).

**[R09] Shinn et al. (2023). Reflexion: Language Agents with Verbal Reinforcement Learning.** Research paper. Feedback and episodic linguistic memory.  
Source: https://arxiv.org/abs/2303.11366 (accessed October 17, 2026).

**[R10] Wang et al. (2023). Voyager: An Open-Ended Embodied Agent with Large Language Models.** Research paper. Executable skill accumulation and feedback-driven code revision.  
Source: https://arxiv.org/abs/2305.16291 (accessed October 17, 2026).

**[R11] Huang et al. (2024; preprint 2023). Large Language Models Cannot Self-Correct Reasoning Yet.** Research paper. Conditional negative result for the evaluated models/settings, not a timeless impossibility claim.  
Source: https://arxiv.org/abs/2310.01798 (accessed October 17, 2026).

**[R12] Kumar et al. (2024). Training Language Models to Self-Correct via Reinforcement Learning.** Research paper / SCoRe. Positive trained self-correction results; read alongside R11.  
Source: https://arxiv.org/abs/2409.12917 (accessed October 17, 2026).

**[R13] Schölkopf et al. (2021). Toward Causal Representation Learning.** Research paper. Learning high-level causal variables and relations requires assumptions beyond generic prediction.  
Source: https://arxiv.org/abs/2102.11107 (accessed October 17, 2026).

**[R14] D’Amour et al. (2022). Underspecification Presents Challenges for Credibility in Modern Machine Learning.** Peer-reviewed research / JMLR. Comparable test performance can conceal materially different deployment behavior.  
Source: https://www.jmlr.org/papers/v23/20-1335.html (accessed October 17, 2026).

**[R15] BenchSci (2026). EMET announcement.** Company announcement. Identifies EMET as Evidence Mapping and Exploratory Tool; product claims require scoped evaluation.  
Source: https://www.benchsci.com/news/the-fragmented-nightmare-of-modern-drug-discovery-ends-here-we-ve-been-building-emet-for-a (accessed October 17, 2026).

**[R16] BenchSci (accessed October 17, 2026). Agentic Research Environment Platform.** Company technical/product description. Planning, tools, code execution, knowledge-graph grounding, lab connectivity; comparisons are not matched CORA experiments.  
Source: https://www.benchsci.com/platform (accessed October 17, 2026).

**[R17] Fusi and Carlson / Microsoft Research (September 29, 2026). Introducing Quine.** Institutional research announcement. Multimodal biological world model and harness; reported experimental follow-up in a bounded application.  
Source: https://www.microsoft.com/en-us/research/blog/introducing-quine-an-ai-research-system-designed-for-the-complexity-of-biology/ (accessed October 17, 2026).

**[R18] Microsoft Quine (2026). Our Research Journey.** Institutional research synthesis linking papers. Model/data limitations and links to primary biological evaluations.  
Source: https://microsoft.github.io/quine/blog/our-research-journey/index.html (accessed October 17, 2026).

**[R19] Google (October 13, 2026). Gemini 4 Argon: Built to Solve Your Hardest Problems.** Official model announcement. The user’s Argon4 is treated as Gemini 4 Argon; vendor benchmarks are not Kaggle-matched tests.  
Source: https://blog.google/intl/en-in/products/introducing-gemini-4-argon/ (accessed October 17, 2026).

**[R20] Faldor, Singh and Raileanu (October 2026). A Team of Gemini 4 Argon Agents Beats Minecraft.** Research preprint. Agentic code construction and environment feedback; scope is a reported game task.  
Source: https://arxiv.org/abs/2610.22319 (accessed October 17, 2026).

**[R21] Anthropic (September 22, 2026). Claude Opus 5.5.** Official model announcement. Long-horizon coding and agent capabilities; no direct CORA comparison.  
Source: https://www.anthropic.com/claude-opus-5-5 (accessed October 17, 2026).

**[R22] Anthropic (September 4, 2026). Formalizing Fermat’s Last Theorem.** Institutional technical report with linked artifacts. Formalization of an existing mathematical proof; Lean checking and Prove2Me scaffold; not a new discovery of FLT.  
Source: https://www.anthropic.com/research/formalizing-fermats-last-theorem (accessed October 17, 2026).

**[R23] Chen et al. (2026). Prove2Me: An Open Collaborative Platform for Scaling Math Formalization.** Research preprint. Shared formal artifacts and coordination infrastructure.  
Source: https://arxiv.org/abs/2608.28433 (accessed October 17, 2026).

**[R24] OpenAI (September 2026). GPT-6 Astra: A New Generation of Intelligence.** Official model announcement. Scientific and agentic capability reports; conditions differ from offline ARC-AGI-2 Kaggle.  
Source: https://openai.com/index/gpt-6-astra/ (accessed October 17, 2026).

**[R25] OpenAI (September 29, 2026). Introducing GPT-6.1 Sol.** Official model announcement. Current tool-using model context; no score projection for CORA.  
Source: https://openai.com/index/introducing-gpt-6-1-sol/ (accessed October 17, 2026).

**[R26] Google DeepMind (2025). AlphaEvolve.** Institutional research announcement. Model proposals plus executable evaluation and evolutionary search.  
Source: https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ (accessed October 17, 2026).

**[R27] Google DeepMind (2026). Co-scientist.** Institutional research announcement. Multi-agent scientific hypothesis generation and reported experimental follow-up.  
Source: https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/ (accessed October 17, 2026).

**[R28] Murphy (2026). Model Discovery Agent: LLM-assisted Bayesian Experiment Design for Data-efficient Discovery of Mechanistic World Models.** Research preprint; HTML methods inspected. Closest prior art; predictive inadequacy, hypothesis expansion, Bayesian inference/design, scientific benchmarks and observation-model adaptation.  
Source: https://arxiv.org/html/2608.09696v1 (accessed October 17, 2026).

**[R29] Bouayad (2026). Weave of Formal Thought.** Research preprint. Formal decoding and learned use of grammar structure; syntactic validity differs from semantic truth.  
Source: https://arxiv.org/abs/2606.25987 (accessed October 17, 2026).

**[R30] Hayes et al. (2025). Simulating 500 Million Years of Evolution with a Language Model. Science.** Peer-reviewed research. ESM3 multimodal protein generation with experimental fluorescent-protein validation.  
Source: https://pubmed.ncbi.nlm.nih.gov/39818825/ (accessed October 17, 2026).

**[R31] Bunne et al. (2024). How to Build the Virtual Cell with Artificial Intelligence: Priorities and Opportunities. Cell.** Research perspective. Research agenda across biological scales; not a completed universal cell.  
Source: https://arxiv.org/abs/2409.11654 (accessed October 17, 2026).

**[R32] Ahlmann-Eltze, Huber and Anders (2025). Deep-learning-based Gene Perturbation Effect Prediction Does Not Yet Outperform Simple Linear Baselines. Nature Methods.** Peer-reviewed benchmark study. Negative result restricted to evaluated methods and datasets; title is not a universal 2026 verdict.  
Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC12328236/ (accessed October 17, 2026).

**[R33] Adduri et al. (2026). STATE / cellular perturbation modeling and Cell-Eval. Cell.** Peer-reviewed research. Later evidence of progress under specific perturbation evaluation protocols; DOI 10.1016/j.cell.2026.07.052.  
Source: https://www.sciencedirect.com/science/article/pii/S0092867426009219 (accessed October 17, 2026).

**[R34] Qi et al. (2026). Mechanisms Matter: The Transportability of Cellular Perturbation Effects.** Research preprint, version 2. Mechanistic/context transportability and benchmark limitations; indexed primary text reviewed.  
Source: https://www.biorxiv.org/content/10.64898/2026.05.08.723625v2 (accessed October 17, 2026).

**[R35] Fu et al. (2026). STRAND.** Research preprint. Sequence-conditioned transport for perturbation generalization; not universal biological semantics.  
Source: https://arxiv.org/abs/2602.10156 (accessed October 17, 2026).

**[R36] VCLMU authors (October 2026). Mechanism-Centric Virtual Cell World Modeling.** Research preprint. Latent mechanism units and stochastic transitions; naming a unit is not causal identification.  
Source: https://arxiv.org/abs/2610.04475 (accessed October 17, 2026).

**[R37] Sorokin, Puget and collaborators (2025–2026). NVARC official repository.** Author code and documentation. Synthetic data, Qwen adaptation/search and other branches; the user reproduced the Qwen3-4B branch, not an original neural algorithm.  
Source: https://github.com/1ytic/NVARC (accessed October 17, 2026).

**[R38] Chollet et al. (2026). ARC Prize 2025 Technical Report.** Benchmark-organizer research report. Historical NVARC results and refinement-loop context; distinguish 2025 from current leaderboards.  
Source: https://arxiv.org/abs/2601.10904 (accessed October 17, 2026).

**[R39] Kaggle (2026). ARC Prize 2026, ARC-AGI-2 competition overview/evaluation.** Official competition specification. Two attempts; exact output match; offline evaluation and runtime conditions. Recheck before deployment.  
Source: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview/description (accessed October 17, 2026).

**[R40] Kaggle (2026). ARC Prize 2026, ARC-AGI-2 rules.** Official competition rules. Submission limits and sharing/licensing obligations require a fresh account-side check before action.  
Source: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/rules (accessed October 17, 2026).

**[R41] ARC Prize Foundation (2026). Paper Prize.** Official competition page. Corresponding Kaggle method implementation; high score not the sole scientific criterion.  
Source: https://arcprize.org/competitions/2026/paper (accessed October 17, 2026).

**[R42] ARC Prize Foundation (2026). Research Summit.** Official event page. October 23, Boston/MIT collaboration; includes MDA and WoFT in its advertised lineup.  
Source: https://arcprize.org/events/research-summit-2026 (accessed October 17, 2026).

**[R43] Lean documentation. Axioms and Computation.** Official formal-methods documentation. Formal assurance is relative to a statement, axioms and a trusted checking implementation.  
Source: https://lean-lang.org/theorem_proving_in_lean4/Axioms-and-Computation/ (accessed October 17, 2026).

**[R44] GitHub documentation. Licensing a Repository.** Official documentation. Public availability is not a substitute for a license; review code, weights and data separately.  
Source: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository (accessed October 17, 2026).

**[L01] Toni–Chimdi ARC conversation (supplied Whisper transcript, 80m33s).** User-provided transcript. 00:00–03:59 questions/semantic transfer; 00:12–16:59 poster/coauthor discussion; 00:17–21 grammar; 00:27:58 verification; later biological context. Audio was not independently reviewed; speaker identity follows the user’s attribution.  
Supplied record: `arc_conversatn.md`.

**[L02] CORA-FHR implementation and integrity transcript, October 14–15, 2026.** User-provided research record. Construction code, D3 degeneracy, controls, original mixed-run restart and Kaggle originality/complementarity records. Superseded on pilot completion by L04.  
Supplied record: `Pasted text(20261015-000455).txt`.

**[L03] Current Summit poster and accompanying explainer/abstract.** User-provided presentation artifacts. Communicated results, not independent replication. Contains older/inconsistent statements identified in this dossier.  
Supplied record: `poster-1.pdf; explainer.pdf; abstract.pdf`.

**[L04] CORA SRC rewrite: final verification, October 15, 2026.** User Library research-audit record. Latest inspected summary: mixed pilot failed; real60 no extension certificate; asset-loaded gate-off8correct25wrong; representation grouping adapter implemented/no established gain. Canonical SRC paths documented.  
Supplied record: `Pasted markdown (2)(20261015-182905).md`.

**[L05] Student Research Abstract: CORA: Testing Competing Programs for Visual Reasoning.** User-provided manuscript. 657-query supplied-candidate selection experiment; separate from FHR, native ranking, biological transfer and VDCG.  
Supplied record: `SAC_SRC2027_CORA_Submission_Ready.pdf`.

