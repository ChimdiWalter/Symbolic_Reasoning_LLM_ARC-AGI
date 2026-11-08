# A biological validation ladder, and from executable biological hypotheses to experimental tests

Section text, tables and an optional figure for the final paper push, 8 November 2026 (UTC). Research and
authorship: Chimdi Walter Ndubuisi. This file edits no paper. It covers the validation ladder (executable consistency,
then independent predictive validity, then intervention-based evidence, then mechanistic confirmation) and the section
"From Executable Biological Hypotheses to Experimental Tests" requested in the author's directive
(in the author's private notes). Evidence labels as in `ARC_TO_BIOLOGY_EXPLANATION.md`: synthetic demonstration,
published-model reconstruction, prediction on real measurements, new hypothesis, laboratory confirmation (none
exists).

**What Paper 2 already prints** (snapshot sha256 `008d53f8befe...`): the paragraph "Three levels of validity, and the
experiment that separates two rules" (snapshot line 2256) names computational, predictive and mechanistic validity and
one discriminating state, (A, B, C) = (0, 1, 1). The introduction (snapshot lines 146 to 161) reports the three-step
ladder from the author's discussions with Dr. Toni Kazic: reproduce what is known, generate plausible ideas that can be
verified, then verify them. There is no ladder table, no statement of what each rung rules out, no placement of CORA's
results on the ladder and no section on experimental tests. This file supplies them, aligned with the intervention
template in `BIOLOGICAL_HYPOTHESIS_FOR_FUTURE_LAB_REVIEW.md` (same folder), which uses the same rules and numbers.

---

## 1. The ladder, in plain words (paste-ready; Paper 2, new subsection)

A biological rule can be right in four senses, and each needs evidence that the one below cannot supply. It can be
*executably consistent*: it runs and reproduces the observations used to build it. It can have *independent
predictive validity*: predictions frozen in advance match measurements that played no part in building or choosing
it. It can be supported by *intervention-based evidence*: when competing rules predict different outcomes of a
feasible intervention, a controlled experiment agrees with one and contradicts the others. And it can reach
*mechanistic confirmation*: independent molecular measurements support the route by which the effect arises, under the
conditions tested. Each rung rules out an explanation the rung below leaves open. A consistent rule may be overfitted;
a predictive rule may name a variable that only travels with the true cause; an intervention can show that changing a
gene changes its target without showing that the effect is direct. A laboratory result that supports a predicted
response therefore does not by itself establish a direct regulatory interaction.

## 2. The four rungs (paste-ready table; Paper 2)

| Rung | The question | Evidence that answers it | What it does not establish | CORA so far |
|---|---|---|---|---|
| 1. Executable consistency | Does the rule run and reproduce the observations used to build it? For a published model, does it equal the reference rule on every input? | Execution on the construction data; for published models, whole-function equivalence and predictions of withheld simulated states | That the rule predicts new measurements; any mechanism | Reached for authored functions (synthetic demonstration) and published models (published-model reconstruction) |
| 2. Independent predictive validity | Do predictions, frozen before scoring, match measurements not used to build or select the rule? | Sealed predictions on held-out biological units (perturbations, donors, replicates), compared with strong native baselines | Causation: a variable that varies with the true cause can predict well | Attempted on measured data, with no robust success (Section 5) |
| 3. Intervention-based evidence | Do competing rules predict different outcomes of a feasible intervention, and which does a controlled experiment support? | A prediction frozen before an intervention chosen to separate the rules, with controls, independent reagents and biological replication | A direct molecular link: the effect may pass through intermediates | Not reached: no experiment, no qualified hypothesis |
| 4. Mechanistic confirmation | Do independent molecular measurements support the proposed route, its conditions and its limits? | Binding, intermediate-pathway or other orthogonal assays, designed and interpreted with experimental biologists | Generality across tissues, species or conditions | Not reached |

**Where published-model reconstruction sits.** It is rung 1 with a reference check: stronger than fitting, because the
whole rule is compared with an independent reference on every input, but the observations come from the model itself,
so it says nothing about living cells. Predictions of a published model's withheld states (for example 2,070 of 2,380
held inputs, or 2,200 of 2,380 after the completion vote) stay on rung 1 for the same reason: the model that is being
predicted also generated the training data.

```latex
\begin{table}[h]
\centering\small
\begin{tabularx}{\textwidth}{@{}L{2.3cm}YYL{3.0cm}@{}}
\toprule
rung & the question & what it does not establish & CORA so far \\
\midrule
1. executable consistency & does the rule run and reproduce the observations used to build it; for a published model, does it equal the reference rule on every input? & that it predicts new measurements; any mechanism & reached for authored functions and published models \\
2. independent predictive validity & do predictions frozen before scoring match measurements on held-out biological units, against strong native baselines? & causation: a variable that travels with the true cause can predict well & attempted on measured data; no robust success \\
3. intervention-based evidence & do competing rules predict different outcomes of a feasible intervention, and which does a controlled, replicated experiment support? & a direct link: the effect may pass through intermediates & not reached \\
4. mechanistic confirmation & do independent molecular measurements support the route, its conditions and its limits? & generality across tissues, species or conditions & not reached \\
\bottomrule
\end{tabularx}
\caption{The biological validation ladder. Each rung needs evidence the rung below cannot supply. Reconstructing a
published model is rung 1 with a reference check, because the observations come from the model itself; no CORA rule
has reached rung 3.}
\label{tab:ladder}
\end{table}
```

## 3. Why each rung needs more evidence

| Step | What the higher rung rules out | The example in this paper |
|---|---|---|
| 1 to 2 | Overfitting to the construction data, and rules that fit for the wrong reason | Eight complete three-input rules fit the five teaching-case observations; at 40 observations conditional construction kept 91 wrong fitted functions, at least 65 of which agree with the truth on all four held inputs (published-model reconstruction) |
| 2 to 3 | A predictor that only travels with the cause | A rule naming C can predict Y well when an unmeasured gene D varies with C and drives Y; observation cannot separate "C influences Y" from "C varies with whatever influences Y", and an intervention on C can |
| 3 to 4 | An indirect route | Activating C may raise Y through an intermediate gene; only binding or intermediate-pathway measurements address directness |
| Beyond 4 | Over-generalisation | A route confirmed in one cell type and time window need not hold in another |

## 4. How the ladder relates to the papers' existing terms

- **The author's three levels of validity** (Paper 2, snapshot line 2256): computational validity is rung 1;
  predictive validity is rung 2; mechanistic validity spans rungs 3 and 4, since the author's note asks both for causal
  intervention (rung 3) and for binding or intermediate-pathway evidence before claiming direct regulation (rung 4).
- **The ladder from the discussions with Dr. Toni Kazic** (Paper 2 introduction): "reproduce what is known" is rung 1
  with a reference check, which is what the published-model studies do; "generate plausible ideas that can be
  verified" is the step from rung 2 to rung 3, a new hypothesis whose competing versions make different predictions;
  "then verify them" is rungs 3 and 4.

## 5. Where CORA's biological results sit (paste-ready table; Paper 2, appendix or after the ladder)

| Result | Label | Rung | Outcome |
|---|---|---|---|
| Teaching case; bounded diagnosis loop (219 of 256 against 38); query-policy repair; sparse engine | Synthetic demonstration | 1 | Reached, on authored functions; ties with equally expressive methods |
| Inferred regulators (99 against 85 and 87 of 333; 101 against 66 of 595) | Published-model reconstruction | 1, reference-checked | Reached |
| Informative observations (320 against 291); completion vote (2,200 against 2,153 of 2,380, post hoc) | Published-model reconstruction, reused cohort | 1, reference-checked | Reached; held inputs are simulated states |
| Conditional construction (433 against 321; classical learner 433) | Published-model reconstruction, reused cohort | 1, reference-checked | Reached; no advantage over the classical learner |
| Perturb-seq construction and relational follow-up | Prediction on real measurements | 2, attempted | No rule admitted for any of 64 genes, twice; directional F1 zero in all 20 follow-up arms |
| Microscopy (three held-out datasets; follow-up) | Prediction on real measurements | 2, attempted | 0 edits; the follow-up failed technically and gives no result |
| Spatial transcriptomics, one exposed donor | Prediction on real measurements | 2, attempted | Original rule 58 corrections against 65 harms; follow-up primary failed its criterion; neighbour-only gate 36 against 12, exploratory |
| Single-cell lung atlas, 41 independent donors | Prediction on real measurements | 2, attempted | The predicted direction held, but so did every control's, so the design gets no credit |
| Drug response, 416 held compounds | Prediction on real measurements | 2, attempted | 0.5249 against 0.5295 for try-all |
| Any CORA rule tested by a designed intervention | | 3 | None |
| Any CORA rule with mechanistic support | | 4 | None |

Reading: CORA's biology is strong at rung 1, has been tried at rung 2 on real measurements without a robust success,
and has not been taken to rungs 3 or 4. That boundary is the honest summary for both papers.

## 6. Rules that keep each rung honest (paste-ready list; Paper 2, after the ladder table)

- **Units.** Thousands of cells from one donor, well or perturbation are not thousands of independent cases. Hold out
  whole perturbations, donors, replicates or projects, and cluster intervals by them; in published models, cluster by
  lineage.
- **Leakage.** A final test set is never reused to choose thresholds, gene panels, candidate rules or the winning
  method.
- **Time.** A snapshot after a perturbation is not a trajectory; a transition model needs genuinely time-paired data.
- **Thresholds.** A Boolean threshold on continuous data must be justified by measurement variability and chosen on
  training data only; otherwise use a continuous or probabilistic response model.
- **Freezing.** Predictions, competing hypotheses and the decision rule are frozen and hashed before the outcome is
  read, and every outcome is reported, including those that contradict the favoured rule.

## 7. From executable biological hypotheses to experimental tests (paste-ready section; Paper 2, new subsection after the ladder)

### 7.1 The idea

The most useful prospective application of CORA in biology would not be one more prediction but a pair of competing
executable hypotheses together with the feasible intervention on which they disagree. Because every hypothesis is a
program, the disagreement is not a matter of interpretation: the system can list the conditions under which the
hypotheses predict different outcomes and rank them by how many surviving hypotheses each condition separates. A
laboratory collaborator can then judge whether an appropriate perturbation and measurement exist for those conditions,
what they would cost, and which controls they need. Any such design must be reviewed and run by an appropriate
biological collaborator; no experiment is initiated by the system.

### 7.2 A worked design (synthetic demonstration)

Take the teaching case: five hypothetical observations of genes A, B, C and a target Y, (0,0,0) giving 0, (0,1,0)
giving 0, (1,0,0) giving 1, (1,1,0) giving 0 and (0,1,1) giving 1. Eight complete three-input rules fit them, and so
does a ninth explanation that observation cannot exclude: C has no causal effect, and an unmeasured gene that varied
with C switched Y on. Four of these hypotheses predict, when C is switched on by intervention in each background
state of A and B:

| Background (A, B) with C switched on | C has no effect (Y follows A AND NOT B) | (A AND NOT B) OR C | (A AND NOT B) OR (B AND C) | (A AND NOT B) OR (NOT A AND C) |
|---|---|---|---|---|
| (0, 1) | Y off | Y on | Y on | Y on |
| (0, 0) | Y off | Y on | Y off | Y on |
| (1, 1) | Y off | Y on | Y on | Y off |
| (1, 0) | Y on | Y on | Y on | Y on |

The state named in Paper 2, (A, B, C) = (0, 1, 1), is the background (0, 1): it tests whether C acts at all, separating
the no-effect explanation from every rule in which C acts, but it cannot tell those rules apart. Adding the backgrounds
(0, 0) and (1, 1) gives the four hypotheses four different patterns of outcome (off, off, off; on, on, on; on, off, on;
on, on, off), so three intervention conditions separate them, while background (1, 0) checks only the A AND NOT B part.
The full four-background design in `BIOLOGICAL_HYPOTHESIS_FOR_FUTURE_LAB_REVIEW.md` separates all nine explanations
(the eight fitting rules and the no-effect explanation). The enumeration is printed by `check_abcy_toy_enumeration.py`
in this folder, which reads no data. The genes are hypothetical: nothing here is a discovered rule or a planned
experiment.

### 7.3 From a computational design to a laboratory test

A collaborator would turn such a design into an experiment in an appropriate model system, for example by switching
C on with CRISPR activation or off with CRISPR interference and reading out Y, alone or by single-cell sequencing in a
Perturb-seq design. The controls a qualified laboratory would consider include non-targeting guides; at least two
independent reagents per target; measurements confirming that C itself changed and that each background state of A
and B held; biological replicates (separate cultures or donors) as the units, rather than cells; more than one time
point; and checks for indirect effects through intermediate genes. Real responses are continuous, so "Y on" must be
defined in advance from the distribution of the controls, with an effect size and an interval. The predictions of
every competing hypothesis are frozen before any measurement is read.

### 7.4 What a result would and would not establish

If switching C on in background (0, 1) raises Y as predicted, that is evidence for a causal influence of C on Y under
the tested conditions (rung 3), not for direct transcriptional regulation, which would need binding or
intermediate-pathway evidence (rung 4). If Y does not change, the no-effect explanation is favoured and every
deterministic rule that fitted the observations is rejected under the toy's assumptions. Either way the result is not a
failure to hide. It is new evidence that returns to the diagnosis step, where it may point to a missing variable, a
different rule from the fitting set, or a context, noise or timing explanation. This return of external evidence is
where the biological loop goes beyond ARC-AGI-2, whose test answers are hidden and which offers no interactive source
of new evidence.

### 7.5 What CORA has done toward this, and what it has not

The computational counterpart of choosing a discriminating experiment is choosing a discriminating observation from a
simulator, and CORA has measured it. In the reused 595-target cohort, active selection asked, at each step, for the
state that split the surviving candidate rules most evenly, from a pool of at most 64 states, and recovered 320 exact
rules against 291 for uniform selection; but it abstained more, answering fewer held inputs correctly (1,586 against
1,747 of 2,380) until a post hoc completion vote reversed the loss (2,200 against 2,153) (published-model
reconstruction). An invented-rule simulation, which is not biology evidence, showed the same logic at its best: with
ten variables and fifteen observations, choosing states where the surviving rules disagree most identified 97% of
three-input rules against 8% for random states (synthetic demonstration). A laboratory is harder in four ways: each
query is an experiment with a real cost; outcomes are noisy and continuous; not every state can be set; and controls
are required. No laboratory experiment has been run on any CORA output, and no data-derived hypothesis currently
qualifies for laboratory review: the companion study's dossier is marked unqualified, and
`BIOLOGICAL_HYPOTHESIS_FOR_FUTURE_LAB_REVIEW.md` reaches the same conclusion.

### 7.6 What a candidate must contain before laboratory review

| Field | Content required | Current status |
|---|---|---|
| Biological system | Organism, cell type or tissue, and context | None qualified |
| Candidate rule | The executable rule, with its inputs and conditions | Only the hypothetical teaching rule |
| Source evidence | The measured observations that support it, with units | None: the measured studies admitted no rule |
| Reasoning failure | What the earlier rule could not explain | Shown only in the teaching case |
| Capability revision | What CORA changed, and whether it chose the change | Fixed rules in authored settings |
| Predictions | Frozen predictions for independent conditions | None for real data |
| Competing explanations | Rival rules and non-causal accounts, with their predictions | Template only (Section 7.2) |
| Evidence needed | The measurement that separates them | Template only |
| Controls | High-level controls for a qualified laboratory | Listed in Section 7.3 |
| Uncertainty | Data limits and alternative causal readings | Not applicable yet |
| Literature | Supporting and conflicting prior work, and a novelty check | Not applicable yet |
| Status | Computationally proposed, independently tested, experimentally unverified, or other | No candidate |

## 8. Compressed text for Paper 1 and the Writeup

**Paper 1, Appendix F, new paragraph** (about 140 words):

> *A validation ladder.* A biological rule can be executably consistent (it runs and reproduces the observations used
> to build it), predictively valid (frozen predictions match independent measurements), supported by an intervention
> (competing rules predict different outcomes of a feasible experiment, and a controlled test agrees with one), and
> mechanistically confirmed (molecular evidence supports the route). Each rung rules out what the one below leaves
> open: overfitting, a predictor that only travels with the cause, and an indirect route. Reconstructing a published
> model is the first rung with a reference check, because the observations come from the model. CORA's biology reaches
> that rung, has been tried on measured data without a robust success, and has not reached the third or fourth. For
> the hypothetical rules Y = A AND NOT B and Y = (A AND NOT B) OR C, switching C on with A off and B on separates them;
> two more backgrounds separate the conditional rivals. No CORA rule has been tested in a laboratory.

**Paper 1, Section 9 (Limitations and next steps), one sentence:**

> Every biological result here reconstructs published models from simulated observations or tests predictions on
> measured data; none has been tested by a designed intervention, and no CORA hypothesis has been examined in a
> laboratory.

**Writeup** (optional clause, about 15 words): "no CORA rule has yet been tested by a laboratory intervention".

## 9. Optional illustrative figure (TikZ), and compile check

An illustrative diagram, not data: four rungs, what each adds, and where CORA's biology stands. It uses the colour
names `tested`, `partial` and `untested` that Paper 2's preamble already defines (for Paper 1, add the three
`\definecolor` lines shown in the comment). It and the three LaTeX tables in this folder's biology files compiled
without error in a minimal document with the papers' packages (pdflatex, 8 November 2026; see the end of this
section).

```latex
% Paper 1 only: \definecolor{tested}{HTML}{2A78D6}\definecolor{partial}{HTML}{C77C02}\definecolor{untested}{HTML}{8C8C8C}
\begin{figure}[t]
\centering
\begin{tikzpicture}[font=\footnotesize,
  rung/.style={draw=black!60, rounded corners=2pt, align=left, text width=6.6cm, minimum height=1.05cm, inner sep=4pt},
  stat/.style={draw=#1, very thick, rounded corners=2pt, align=left, text width=5.4cm, minimum height=1.05cm, inner sep=4pt, text=black},
  up/.style={-{Latex[length=2mm]}, thick, draw=black!50}]
\node[rung] (r1) at (0,0) {\textbf{1. Executable consistency}\\ runs and reproduces its construction data};
\node[rung, above=4mm of r1] (r2) {\textbf{2. Independent predictive validity}\\ frozen predictions match held-out measurements};
\node[rung, above=4mm of r2] (r3) {\textbf{3. Intervention-based evidence}\\ a controlled intervention separates rival rules};
\node[rung, above=4mm of r3] (r4) {\textbf{4. Mechanistic confirmation}\\ molecular evidence supports the route};
\draw[up] (r1) -- (r2); \draw[up] (r2) -- (r3); \draw[up] (r3) -- (r4);
\node[stat=tested, right=5mm of r1] {reached: authored functions; published models (101 against 66; 433 against 321)};
\node[stat=partial, right=5mm of r2] {attempted on measured data: no rule for Perturb-seq; one exploratory spatial gain};
\node[stat=untested, right=5mm of r3] {not reached: no experiment, no qualified hypothesis};
\node[stat=untested, right=5mm of r4] {not reached};
\end{tikzpicture}
\caption{The biological validation ladder and where CORA's evidence stands (an illustrative diagram, not data). Each
rung needs evidence the rung below cannot supply; reconstructing a published model is rung 1 with a reference check.}
\label{fig:ladder}
\end{figure}
```

Compile check, 8 November 2026 (UTC): a scratch document with `article`, `booktabs`, `tabularx`, `array`, `xcolor`
and `tikz` (`positioning`, `arrows.meta`), the papers' `Y`, `L` and `P` column types and the three colours, containing
the figure above, `tab:ladder`, `tab:mapping`, `tab:biostages` and `tab:frontier` from
`ARC_TO_BIOLOGY_EXPLANATION.md`, built twice with pdflatex under `nice -n 19`: zero errors and zero overfull boxes;
the five pages were rendered and inspected. The paper agent should still rebuild each paper after insertion.

## 10. Sources (read only)

- Author's directive: in the author's private notes (the experimental-test
  section and the ladder, and the frontier gap). Author's note: `records/NOV8_AUTHOR_NOTE_ARC_TO_BIOLOGY_TRANSFER.md`,
  sections 4 and 5 (three levels of validity; the discriminating intervention).
- Paper 2 snapshot: `paper/v2_neural_cora/main.tex`, sha256 `008d53f8befec4a3697fbcfd518afac3ce3bde17dfcb9a76744d683ab0bc3a94`
  (introduction, discussion ladder; Section 6, three levels of validity).
- Teaching case and its enumeration: `<companion study folder>/biology_transfer_additions_20261107_v1/demo/EXECUTABLE_BIOLOGICAL_REASONING_DEMO.md`;
  `check_abcy_toy_enumeration.py` and `BIOLOGICAL_HYPOTHESIS_FOR_FUTURE_LAB_REVIEW.md` in this folder.
- Active selection rule and result: `cage/active_biology_frozen_design_20261107_v1/PROTOCOL.md`; outbox 0557;
  completion vote: `cage/biology_fallback_score_recovery_admission_20261107_v1/RESULT_AGGREGATE.json`.
- Design simulation: `experiments/boolean_design_simulation_20261106/sim/RESULTS.md` and its review (cited in Paper 2,
  Section 4).
- Wrong fitted functions at 40 observations: `cage/independent_sparse_biology_outcome_review_20261107_v1/REPORT.md`.
- Measured-data results: outbox 0582 and the three follow-up audits in this folder; Paper 2 appendix on cross-domain
  studies (single-cell lung, drug response).
- Unqualified dossier: `cage/biology_transfer_additions_20261107_v1/evidence/LABORATORY_HYPOTHESIS_DOSSIER.md`.
- Methods named in 7.3 (background, not CORA results): Gilbert et al. 2014 (CRISPR interference and activation),
  Dixit et al. 2016 and Replogle et al. 2022 (Perturb-seq), Norman et al. 2019 (combinatorial perturbation). Only
  Replogle et al. 2022 is in either paper's bibliography; the others must pass the reference check before they are
  cited.
