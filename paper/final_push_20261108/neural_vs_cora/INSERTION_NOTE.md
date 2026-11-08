# Insertion note: where neural and symbolic reasoning each fall short

For the single paper agent. Prepared on 8 November 2026 from three results in this folder: `gap_analysis.md`
(f5699dab), `explain_analysis.md` (3517e48a) and their adversarial check `CHECK.md` (755a42d6). Every correction in
`CHECK.md` is applied in the text below; Section 8 shows where each of its 23 items went. Where the two analyses and
this note differ, this note wins.

**Every number here is post hoc, on the exposed public evaluation set (120 tasks, 172 test outputs), and is not an
official score.** Nothing here changes an official score (0.83% for 57902131, 24.03% for 57867631, NVARC credited) or
attributes anything to a scored entry.

**How to apply.**
- Each item gives a phrase to find, the action, the exact text, a claim label and the sources.
- Every find phrase was checked to occur exactly once, ignoring line breaks, in Paper 2 `main.tex` 608fad32, Paper 1
  `cora_final.tex` 97f07a8f and the Writeup candidate `KAGGLE_DRAFT_PACKAGE/WRITEUP_BODY_v3_candidate.md` 3c433781.
- Apply `../INSERTION_BRIEF.md` first. None of its items touches these sentences, except the marker in Paper 1,
  Section 1, which it leaves to this note (its item P1-A10).
- "Must fix" means the current text is now stale or misleading. "New" is the requested material. "Optional" may be
  skipped for space.
- An item without a label line takes the label of the text around it: tested capability or measured diagnosis, post
  hoc, exposed public evaluation.

## 1. The story in four lines (orientation, not for pasting)

1. The neural comparison entry answers more (43 of 172 test outputs right) but returns grids, not programs. CORA can
   confirm or reject its attempts only where CORA's own language reaches, which is 3 test outputs.
2. CORA explains everything it answers: 3 of 172 answered, all right, all from two design-exposed tasks.
3. The 41 outputs between them form a list, made from the demonstrations alone, of what CORA's language lacks:
   - a missing action first, in 35 of 36 tasks;
   - object views that also fail, in 14 of them;
   - a missing guard, in 1 task;
   - budget, in none.
4. That list is the bridge from the broader question to learning what to change. The broader question is how to learn
   rules from a few observations, induce the grammar and carry the procedure to new domains. The list also answers the
   author's own open question about the gap on the outputs the neural method solved. That question appears as item 1
   of Paper 2's six open questions and comes from
   `records/author_inputs_20261108/EXTERNAL_CHAT_INPUTS.md`, part A, item 1.

## 2. Rules for this material (all three documents)

- **Label.** Put "post hoc, exposed public evaluation, not an official score" on every number from this material, in
  text, tables and captions.
- **Counts only.** Do not give percentages, intervals, "precision" or "100%" for these counts. Write "keeps 2 of the
  344 attempts, both right".
- **Names.**
  - Say "the neural comparison entry". Both papers already name and cite NVARC's method; do not name it again in
    this material.
  - Paper 2 calls CORA-CAST's three shipped modules symmetry completion, guarded rewriting and typed search. Use those
    names. The analyses call typed search "the whole-grid search" or "short operator programs".
  - Say "CORA-CAST's five modules" when the two research modules that no entry ran (legend binding and local growth)
    are included. Say "the shipped three modules" otherwise.
- **Units.**
  - In Paper 2 and in this note, use "test output". In Paper 1 and the Writeup, use "query output", their defined
    term.
  - Use "attempt" for each of the neural entry's two grids per output.
  - Say "first", "second" or "third test output", never an index counted from 0 or from 1.
- **Budget.** "Ten times the budget" means the execution budgets, kept-list budgets and CPU caps multiplied by ten,
  with CORA's language fixed.
  - The gap analysis's reruns also raised tenfold three bounds that CORA-CAST's code treats as part of its language:
    the actions considered per view (8), the object cap (120 objects summed over the demonstration inputs) and the
    size values offered as guards (12). Call those runs "the wider check"; they can only add programs.
  - State each CPU cap where it is used: 45 CPU-seconds per task for the CORA-only entry and the gap reruns; 15
    CPU-seconds per module call for the explanation search; 15 per task for the neural entry's CORA second attempt.
- **Exposure.** Say: "All of CORA's answers on this set, and both explained neural attempts, come from two
  design-exposed tasks (62593bfd and 981571dc); 0934a4d8 is design-exposed as well." Also say that the neural
  checkpoint is contaminated for this set.
- **The earlier zero.** The earlier neural-guesses test (3 November) aimed CORA's earlier construction grammar at the
  first attempts of the same neural run (SHA-256 558b6ab1). All 172 of its searches stopped at their execution budget.
  Its zero is bounded by budget in a different grammar. Never call that test "a separate neural run" or "a general
  program language".
- **Diagnostic labels.**
  - Use the automatic labels in tables, figures and counts. Mark any further explanation "on inspection".
  - The rules were refined on these same tasks, and the first-pass outputs were not saved; say so wherever the causes
    appear.

## 3. Paper 2, the master (`paper/v2_neural_cora/main.tex`)

### 3A. Must fix: stale or now incomplete text

**Paper 2, item 1. Introduction, paragraph "Where large language models and neural systems fall short, stated fairly."**
- **Find** (spans a line break): "and when bounded typed search tried to explain each of the 172 neural guesses with a
  verified CORA program, it verified none (Section~\ref{sec:dev})."
- **Replace with:**

```latex
and CORA-CAST's programs reproduce the demonstrations and give the answer for only 2 of the neural entry's 344
attempts, both right (Section~\ref{sec:neuralgap}; post hoc, not an official score).
```

- **Find** the marker that follows "The deeper problem is learning what to change.":
  "\PENDING{an analysis of why CORA cannot explain the outputs the neural entry solves, and what CORA must add; it will
  be inserted here after its audit}". **Replace it with:**

```latex
The comparison also says where to start. On the 41 outputs that the neural entry gets right and CORA does not answer,
ten times CORA's search budget finds no program, and automatic diagnostics, run on the demonstrations alone, name what
CORA's language lacks: an action in 35 of the 36 tasks, in 14 of them also a view of the objects, and a guard in 1. The
neural system's right answers thus mark, task by task, what a grammar learned from a few observations would have to
acquire (Section~\ref{sec:neuralgap}).
```

- **Label:** tested capability and interpretation; post hoc, exposed.

**Paper 2, item 2. Question 2, paragraph "The finished companion tests."**
- **Find** (spans a line break): "CORA turned 0 of 172 frozen neural first guesses into a program that passes every
  demonstration, as with no target, while the neural first attempt alone was right on 33 of 172."
- **Replace with:**

```latex
CORA's earlier construction grammar turned 0 of 172 frozen neural first guesses into a program that passes every
demonstration, as with no target, while the neural first attempt alone was right on 33 of 172; all 172 of its
searches stopped at their execution budget, so that zero is bounded by budget in that grammar. CORA-CAST's own modules
explain 2 of the neural entry's 344 attempts, both right, and on the other 41 right outputs they find no program at
ten times the budget (Section~\ref{sec:neuralgap}).
```

**Paper 2, item 3. Six open questions, item 1** (`sec:sixq`).
- **Find** the whole item, from "\item \emph{The gap on the outputs the neural method solved.}" to "if most of the 43
  have a program in CORA's current language that a larger budget finds."
- **Replace it with:**

```latex
\item \emph{Inducing the operations that the neural gap names.} A task-by-task post-mortem of the outputs the neural
  method solved has now been run (Section~\ref{sec:neuralgap}; post hoc, exposed public evaluation, not an official
  score). None of the 41 test outputs that the neural comparison entry gets right and CORA does not answer gains a
  program at ten times the budget; the first gap is a missing action in 35 of the 36 tasks (in 14 of them the object
  views also fail), a missing guard in 1, and never depth or budget. The hypothesis that the gap is mostly
  representation and language therefore survived the test that could have disproved it, and neural guidance would
  help most by proposing new actions and views. The open question is whether the named operations (drawing on the
  background, editing parts of objects, assembling new output grids, panel and pattern views, guards that relate one
  object to another) can be built from each task's few demonstrations, with or without the neural attempt as one more
  observation, and then reused. \emph{Disproved} if operations built from these failures add no right answers on held
  tasks over static access to a library of the same size at matched counted work, or are admitted from shuffled
  failures as often as from the real ones.
```

- **Label:** open direction, with a measured first step.

**Paper 2, item 4. Results-by-dataset table** (`tab:bydataset`).
- **Find** "neural guesses turned into verified programs & the neural-guesses test: 0 of 172 frozen neural first
  guesses" and **replace** "the neural-guesses test:" with "the neural-guesses test, in CORA's earlier construction
  grammar:".
- **Add a row** directly after that row, which ends "a development diagnosis with its own denominator \\":

```latex
neural attempts explained by CORA-CAST (post hoc; Section~\ref{sec:neuralgap}) & 2 of the neural comparison entry's 344 attempts explained, both right, none of the 301 wrong; on the 41 test outputs it gets right and CORA does not answer, no program at ten times the budget; first gap a missing action in 35 of 36 tasks (14 also a view), a missing guard in 1 & kept only when explained: 1 of 172 first attempts kept, and it is right (unfiltered: 33 of 172 right); 15 CPU-seconds per module call, 150 at ten times & \\
```

**Paper 2, item 5. Appendix paragraph "The finished companion tests: the measured coverage and representation limit".**
- **Find** "CORA turned 0 of 172 frozen neural first guesses into a program that passes every demonstration, as with no
  target (0 of 172), while the neural first attempt alone was right on 33 of 172;". **Replace** "CORA turned" with
  "CORA's earlier construction grammar turned"; the rest is unchanged.
- **Find** "so the effect is not shown and inexpressibility is not proven
  (\rec{experiments/neural_to_program_b_20261103/runs/score/SCORE_REPORT.md})." **Insert after it:**

```latex
The same neural file (SHA-256 \texttt{558b6ab1}) was later searched with CORA-CAST's five modules, which explain 2 of
its 344 attempts, both right (Section~\ref{sec:neuralgap}).
```

**Paper 2, item 6. Appendix "Representation growth and neural-to-program verification"** (`app:repgrowth`).
- **Find** "A control search without the guess as a target reached none of the 172 outputs." **Insert after it:**

```latex
That test searched CORA's earlier construction grammar, first attempts only, and every search stopped at its execution
budget; Appendix~\ref{app:neuralgap} records the later search of the same file with CORA-CAST's modules.
```

### 3B. New: the section, its table and two figures

**Placement.** Insert a new subsection directly after Question 2. The place is after the sentence ending "and the claim
is falsified if a better ranker over the same candidates raises exact answers where no correct candidate was
generated." and before "\subsection{Question 3: can a failure specify what is missing?}". The new subsection is
Question 2 asked of the outputs that a neural system gets right. It is about 1,280 words, plus one table and two
figures; the details sit in the appendix (Section 3D).

**Labels:**
- tested capability, post hoc: the explanation counts;
- measured diagnosis, post hoc: the causes;
- interpretation and open direction: what CORA must learn.

All numbers were re-derived by our own check.

```latex
\subsection{Where neural and symbolic reasoning each fall short}
\label{sec:neuralgap}
\emph{In terms of the core idea:} an output that a neural system gets right and CORA cannot explain is a failure with
a known answer, and the failure says what CORA's language is missing.

The neural comparison entry, a language model specialized for grids and trained briefly on each task
(Appendix~\ref{app:system}), and CORA fail in opposite ways, and reading them side by side on the same outputs shows
what each lacks. Every number here is post hoc, on the exposed public evaluation set (120 tasks, 172 test outputs),
and not an official score: both entries and the held-back-half study had scored these tasks, CORA-CAST was designed
with them in view, and the neural checkpoint is contaminated for them (Section~\ref{sec:results}).
Table~\ref{tab:neuralgap} gives the counts, and Appendix~\ref{app:neuralgap} the definitions, budgets and controls.

\paragraph{The neural entry answers more, but gives no explanation that can be checked (tested capability, post hoc).}
With two attempts per test output, the neural entry was right on 43 of the 172 test outputs, and the CORA-only entry
answered 3, all right. The neural entry returns grids, not programs. We call a neural attempt \emph{explained} when a
CORA-CAST program reproduces every demonstration exactly and outputs that attempt; explained means consistent with the
demonstrations, not right. CORA-CAST's five modules, the three that both entries ship and two research modules,
explain 2 of the neural entry's 344 attempts, both right and both among CORA's own 3 answers: the first attempt on task
981571dc, by symmetry completion (Figure~\ref{fig:neuralexplained}), and the second attempt on the second test output
of task 62593bfd, by guarded rewriting. None of the 301 wrong attempts is explained, and ten times the execution
budgets, kept-list budgets and CPU caps, with CORA's language fixed, explains nothing more. Inside the neural
comparison entry, CORA's checked second attempt answered only 981571dc, with the neural first attempt's grid, so it
replaced nothing.

\paragraph{CORA explains everything it answers, but answers little (tested capability, post hoc).} Each of CORA's 3
answers comes from a program that reproduces every demonstration and is rebuilt without each one, and on no other test
output does CORA have a complete answer of its own. On those 3 its check accepts both right neural attempts and
rejects all 4 wrong ones, and on the first test output of 62593bfd, where both neural attempts are wrong, CORA's own
answer is right. On the other 169 it can neither confirm nor reject a neural attempt, so for CORA most neural answers
remain guesses. As a filter, explanation is exact but narrow: keeping only explained attempts would cut the entry from
43 right outputs to 2. The limit is reach, not judgement, so the filter becomes useful only as the language grows. A
partial program can already help: on 0934a4d8 a symmetry completion program fixes 19 of the 27 test cells, and both
neural attempts are wrong only in the 8 it leaves open. All of CORA's answers here, and both explained neural
attempts, come from two design-exposed tasks (62593bfd and 981571dc), and 0934a4d8 is design-exposed as well.

\paragraph{Why CORA missed what the neural entry got right (measured diagnosis, post hoc).} That leaves 41 test
outputs, in 36 tasks, that the neural entry got right and CORA did not answer. Automatic diagnostics, which read only
the demonstrations and test inputs and use CORA-CAST's own object views, guards, actions and move rules, sorted them
by cause.
\begin{itemize}[leftmargin=*]
\item \emph{Not the budget.} No CORA-CAST program reproduces the demonstrations of any of the 36 tasks, at the
  CORA-only entry's budget (45 CPU-seconds per task) or at ten times it, even in a wider check that also raised three
  bounds that CORA-CAST's code treats as part of its language. No task used more than 9.4 CPU-seconds, and typed
  search, given more executions, exhausted every two-step program.
\item \emph{The language.} Guarded rewriting's actions write only an object's own cells, its holes, a one-cell ring of
  background around it, or a straight slide. In 35 of the 36 tasks CORA's language (all three shipped modules) has no
  operation that produces the change: some changed cells cannot be written by any action (21 tasks), the output of a
  size-changing task is built rather than cut out of the input (13), or objects move by distances that CORA's
  stopping rules do not produce (1). In the last task (d35bdbdc) every change can be written, but no rule list over
  CORA's guards assigns the actions.
\item \emph{Scene parsing, in 14 of those tasks:} no CORA-CAST object view makes the objects correspond in every
  demonstration; on inspection, these tasks act on panels, repeating patterns or parts of objects.
\item \emph{Depth is never the first gap,} though in 3 tasks an object needs two actions at once even on the part of
  the change that CORA can already write.
\end{itemize}
Figure~\ref{fig:neuralgap} shows the most common cause on one task.

\paragraph{What the gap says CORA must learn (interpretation and open direction).} \emph{Observation:} the neural
entry was right on 41 test outputs for which CORA has no program at any budget we tried. \emph{Explanation:} what is
missing is operations, not search: mostly drawing on the background, editing part of an object and building a new
output grid (Appendix~\ref{app:neuralgap} lists each task), then views of panels, patterns and parts, guards that
relate one object to another, and several actions per object. \emph{Research implication:} CORA must acquire actions
first, then views, guards and depth. More budget alone closes none of the 41, and neural guidance would help most by
proposing new actions and views, not by ranking what the language already has (Proposition~\ref{prop:nest}). Each of
these outputs is a fully specified failure: a few demonstrations, a right answer (known here only post hoc) and a
record that the language has no program for it. Building the missing operations from such failures, keeping one only
when a program using it reproduces every demonstration, and judging it on held tasks against static access to the
same operations and against shuffled failures, is the test of learning what to change on real tasks
(Section~\ref{sec:realarc}); it has not been run. In the terms of the central question (Section~\ref{sec:question}),
the neural entry holds whatever rules it uses, or has absorbed from exposure, in a form that cannot be run or checked,
while CORA states its rules exactly but has too few. Inducing the missing rules from a few demonstrations, and
carrying the same procedure to new domains, is where the two must meet.

\paragraph{Why this differs from the earlier zero.} The earlier neural-guesses test (Appendix~\ref{app:repgrowth})
aimed CORA's earlier construction grammar at the first attempts of the same neural run and explained none of the 172,
but all 172 of its searches stopped at their budget of 150{,}000 executions, so that zero is bounded by budget in a
different grammar. It searched first attempts only, so of the two attempts explained here only 981571dc's was within
its scope. CORA-CAST's symmetry completion and guarded rewriting express both programs directly and find them in a
few CPU-seconds.

\paragraph{Limits.} Counts only, post hoc, on exposed tasks; no accuracy, generalisation or hidden-set claim follows.
The diagnostic rules were refined while they ran on these same tasks (the move check and the guard test were corrected
after a first pass misread b5ca7ac4 and d35bdbdc, and the line and border labels were tightened), and the first-pass
outputs were not saved. Each task gets one verdict, so a missing action can hide a guard or depth gap; readings marked
``on inspection'' are not diagnostic output; and finding no program within these bounds does not prove that none
exists in a larger language. Every count was re-derived by our own check
(\rec{paper/final_push_20261108/neural_vs_cora/CHECK.md}).
```

**The table** (place it near the subsection's first paragraph):

```latex
\begin{table}[t]
\centering\small
\begin{tabularx}{\textwidth}{@{}YL{5.6cm}@{}}
\toprule
on the public evaluation (120 tasks, 172 test outputs) & count \\
\midrule
neural comparison entry right, either of two attempts & 43 test outputs (33 on the first attempt); every output right in 27 tasks \\
CORA-only entry answered, all right & 3 test outputs in 2 tasks \\
right in both entries; CORA right where both neural attempts are wrong & 2; 1 \\
right in neither entry & 128 test outputs \\
neural attempts that a CORA-CAST program explains & 2 of 344, both right; none of the 301 wrong \\
\midrule
neural entry right, CORA no answer & 41 test outputs in 36 tasks \\
\quad a CORA-CAST program at ten times the budget, or in the wider check & none \\
\quad first gap a missing action: no operation in CORA's language produces the change & 35 tasks (40 test outputs) \\
\quad object views also fail (scene parsing) & 14 of those tasks (18 test outputs) \\
\quad first gap a missing guard: no rule list over CORA's guards assigns the actions & 1 task (1 test output) \\
\quad depth as the first gap & none; in 3 tasks an object needs two actions on the part CORA can write \\
\bottomrule
\end{tabularx}
\caption[]{Where the neural comparison entry and CORA each fall short. Post hoc, exposed public evaluation, not an
official score. The neural checkpoint is contaminated for these tasks, and all of CORA's answers come from two
design-exposed tasks. \emph{Explained}: a CORA-CAST program reproduces every demonstration and outputs the attempt; it
does not mean right. \emph{Ten times the budget}: the execution budgets, kept-list budgets and CPU caps multiplied by
ten, with CORA's language fixed; the \emph{wider check} also raised tenfold three bounds that CORA-CAST's code treats
as part of its language. The diagnostics read only the demonstrations and test inputs, and their rules were refined
while being run on these tasks. Counts re-derived by our own check
(\rec{paper/final_push_20261108/neural_vs_cora/CHECK.md}).}
\label{tab:neuralgap}
\end{table}
```

**The two figures** (copy the files first; Section 7):

```latex
\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{explain_example_explained.pdf}
\caption[]{A neural attempt that CORA explains. Task 981571dc of the public evaluation set: the neural comparison
entry's first attempt is right, and one symmetry completion program, found from the four demonstrations alone,
reproduces every demonstration and outputs exactly that attempt. Outlined cells are the black cells it filled from
their symmetric partners. The program line, in CORA's own syntax, reads in words: fill colour 0 (black) from the
grid's own symmetries, without cropping. CORA's demonstration-consistent programs give one distinct output here, so
the demonstrations and CORA's language pin the answer down. The task is design-exposed. Post hoc, exposed public
evaluation, not an official score. Puzzle data: ARC Prize Foundation.}
\label{fig:neuralexplained}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=0.62\linewidth]{gap_example_6e453dd6.png}
\caption[]{A right neural attempt that CORA cannot explain: a missing action. Task 6e453dd6 of the public evaluation
set: two demonstrations, the test input and the neural comparison entry's right second attempt. White outlines mark
changed demonstration cells that no CORA action can write (42 of 178); the diagnostics' label is drawing lines or
filling regions on the background. On inspection, shapes slide right until they touch the grey wall, which CORA can
write as a move until blocked, and shapes with an enclosed gap also get red cells on the far side of the wall, in the
rows of the gap, which no CORA action draws; the move and the drawing would also have to combine in one program. No
CORA-CAST program reproduces the demonstrations at the entry's budget or in the wider check at four or ten times it
(labelled 1x, 4x and 10x in the figure). Post hoc, exposed public evaluation, not an official score. Puzzle data: ARC
Prize Foundation.}
\label{fig:neuralgap}
\end{figure}
```

### 3C. New, short: cross-references elsewhere in Paper 2

**Paper 2, item 7. Section intro of "CORA as an empirical investigation"** (optional).
- **Find** "Are acquired capabilities reused (Section~\ref{sec:reuse})?" and **insert after it:** "Between Questions 2
  and 3, Section~\ref{sec:neuralgap} reads the neural comparison entry and CORA side by side on the same outputs."

**Paper 2, item 8. "Real ARC-AGI-2: the missing causal evidence"** (`sec:realarc`).
- **Find** "a correct committed answer, and a win over strong full-bank, static and shuffled-failure controls
  (Section~\ref{sec:revise})." **Insert after it:**

```latex
On the 36 exposed tasks of Section~\ref{sec:neuralgap} the first link exists in a limited form: a diagnosis from the
demonstrations alone names the missing kind of change for each task, though its rules were refined on those tasks;
the revision, the fit and the controls are still missing.
```

**Paper 2, item 9. "What the evidence says, in order"** (`sec:progress`; optional).
- **Find** "own pool no selector can add more than 3 of 172 outputs." and **insert after it**, before "It opens broader
  grammars": "On the 41 outputs the neural comparison entry gets right and CORA does not answer, ten times CORA-CAST's
  budget finds no program, and the first gap is a missing action in 35 of the 36 tasks (Section~\ref{sec:neuralgap})."

**Paper 2, item 10. Six open questions, item 3 (minimum-residual projection).**
- **Find** "\emph{Disproved} if, at matched work on held tasks, such projections add no correct output over the
  unrepaired neural guesses, or lower precision." **Insert before it:**

```latex
A first observation, on one design-exposed task: on 0934a4d8 a symmetry completion program fixes 19 of the 27 test
cells, and both neural attempts are wrong only in the 8 it leaves open (Section~\ref{sec:neuralgap}), so a partial
program can locate a neural error that it cannot repair.
```

**Paper 2, item 11. Status table** (`tab:status`). **Find** "open direction & capability selection:" and **insert
these two rows before that row:**

```latex
tested capability & on the exposed public evaluation (post hoc), CORA-CAST programs explain 2 of the neural comparison entry's 344 attempts, both right, and none of the 301 wrong ones; where CORA has its own answer (3 test outputs) its check accepts both right attempts and rejects all 4 wrong ones & Section~\ref{sec:neuralgap} \\
supported interpretation & on the 41 test outputs the neural entry gets right and CORA does not answer, the language falls short, not the budget: no program at ten times the budget; a missing action first in 35 of 36 tasks, a missing guard in 1; diagnostic rules refined on these tasks & Section~\ref{sec:neuralgap} \\
```

**Paper 2, item 12. Numbers table** (`tab:numbers`). **Insert after the row that begins** "2 of 172 & public ARC-AGI-2
evaluation outputs right by task-local construction":

```latex
2 of 344 & neural comparison entry attempts on the public evaluation that a CORA-CAST program reproduces from the demonstrations & none of its 301 wrong attempts & CORA can check a neural answer only where its language reaches; there it separated right from wrong & exposed public tasks, post hoc \\
41 in 36 tasks & public evaluation test outputs the neural entry got right and CORA did not answer & no CORA-CAST program at ten times the budget & the language, not the budget, falls short: a missing action first in 35 of the 36 tasks & exposed public tasks, post hoc \\
```

**Paper 2, item 13. Claim-to-code table** (`app:claims`). **Insert after the row that begins** "62593bfd: exact new
executed-program prediction":

```latex
CORA-CAST explains 2 of the neural comparison entry's 344 public-evaluation attempts, both right; 0 of 301 wrong & \path{paper/final_push_20261108/neural_vs_cora/scripts/explain_01_search.py} & \path{paper/final_push_20261108/neural_vs_cora/data/explain/explain_rows.csv}; \path{paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json} & supported; post hoc, exposed \\
the 41-output gap: no program at ten times the budget; a missing action first in 35 of 36 tasks, a missing guard in 1 & \path{paper/final_push_20261108/neural_vs_cora/scripts/03_diagnose.py} & \path{paper/final_push_20261108/neural_vs_cora/gap_table.csv}; \path{paper/final_push_20261108/neural_vs_cora/data/gap_summary.json} & supported; post hoc, exposed; rules refined on these tasks \\
```

**Paper 2, item 14. Conclusion** (optional). **Find** "produced the correct answer. That argument stands even if" and
insert after "produced the correct answer.": "Beside a strong neural system, CORA explains the few answers its language
reaches and, for the rest, names from the demonstrations alone what its language lacks; that list is where learning
what to change must start on real tasks."

**Paper 2, item 15. Exact commands** (`sec:repro`). **Find** "The companion study's pilots record no command lines in
this repository;" and **insert before it:**

```latex
The neural-versus-CORA analyses (Section~\ref{sec:neuralgap}), from the repository root, each through the CPU-slot
wrapper at the lowest priority:
\begin{Verbatim}[breaklines,fontsize=\scriptsize]
D=paper/final_push_20261108/neural_vs_cora/scripts; P="python3 -B"; S="sh scripts/with_cpu_slot.sh nice -n 19"
$S $P $D/01_score_entries.py; $S $P $D/02_budget_runs.py --k 1 4 10; $S $P $D/03_diagnose.py
$S $P $D/04_build_table.py; $S $P $D/05_figures.py 6e453dd6 aa4ec2a5 38007db0
$S $P $D/explain_01_search.py driver --phases 1x:own,1x:a1,1x:a2,10x:own,10x:a1,10x:a2 --cpu-limit 6200
$S $P $D/explain_02_score.py; $S $P $D/explain_04_partial.py; $S $P $D/explain_03_figures.py; $S $P $D/explain_05_controls.py
$S $P $D/check_01_counts.py; $S $P $D/check_02_cast_own.py; $S $P $D/check_03_join.py
\end{Verbatim}
```

### 3D. Appendix (include it: the new section and item 6 point to it; only its extra figures are optional)

**Placement.** Add a new subsection in "ARC experiment records in detail". Put it after "Representation growth and
neural-to-program verification" (`app:repgrowth`) and before "Where construction stalls" (`app:bottleneck`).

```latex
\subsection{Neural attempts and the CORA gap: definitions and records}
\label{app:neuralgap}
Post hoc, exposed public evaluation, not an official score. Records:
\rec{paper/final_push_20261108/neural_vs_cora/} (the two analyses, their check, the gap table and the data folder).

\paragraph{Terms.} An \emph{object view} is how CORA-CAST cuts a grid into objects on its majority-colour background:
one-colour cells joined through edges, one-colour cells joined through edges or corners, or cells of any
non-background colour joined through edges or corners. A guarded-rewriting rule pairs a \emph{guard}, which picks the
objects it acts on, with an \emph{action}: keep, erase, recolour, recolour to the colour of a touching or enclosed
object, fill holes, draw a one-cell outline on the background around the object, or move it in one direction until
blocked or to the border. A program has at most two guarded rules and a default and gives each object at most one
action; guarded rewriting also has recolour tables keyed by one feature and, when the size changes, a crop to the box
of one object that a guard picks. Typed search chains at most two whole-grid operations (turns and flips, colour
swaps, crops, scaling, tiling, joining with a transformed copy, filling enclosed areas, outlines, gravity), and
symmetry completion fills the cells under a mask colour from the grid's symmetries. \emph{Depth} is how much a program
may chain. A program \emph{fits} when it reproduces every demonstration exactly.

\paragraph{How each cause was diagnosed.} The diagnostics read only the demonstrations and test inputs, never an
answer, and their code names no task. \emph{Scene parsing:} under each view, every demonstration input and output is
cut into objects and matched; a view is consistent when every input object is kept, changed as a whole or found again
with the same shape, and every changed output object is a recoloured or moved input object or new cells on the
background. A task passes when one view is consistent in every demonstration. \emph{Language:} every program that
CORA's modules build from one demonstration is run on all of them. On same-size tasks, CORA's own evidence step lists
the single actions that fit each object's change, and changed cells that no action of any object can write mean a
missing action. If every changed cell can be written, a program that gives each object the action it needs is
replayed with CORA's own rules, and a rule list over CORA's guards is built one rule at a time; no list, or a list
that does not carry over between demonstrations, means a missing guard, while an object that needs two actions at
once, or a list longer than two rules, means depth. On size-changing tasks, an output that is not a window of its
input is built, not cut out, which is a missing action. Each task gets one verdict, from the view that comes closest. \emph{Budget:} the shipped three modules were rerun on each task, in a fresh process, at the CORA-only
entry's budget and at four and ten times it (Table~\ref{tab:gapbudget}). The largest of the 36 tasks took 9.4
CPU-seconds at the entry's budget and 8.7 in the wider check at ten times (cap 450); typed search stopped at its
1{,}000-execution cap on 4 of the tasks at the entry's budget and, given four or ten times its executions, finished its
whole space of two-step programs on all 36 (at most 1{,}480 executions). Of the 36 tasks, 23 keep the grid size and 13
change it; in none does a program that CORA builds from one demonstration reproduce even that demonstration; and in 3
(aa4ec2a5, d8e07eb2 and de809cff) an object needs two actions at once even on the part of the change that CORA can
already write.

\begin{table}[h]
\centering\small
\begin{tabular}{@{}lrrr@{}}
\toprule
bound & entry & four times & ten times \\
\midrule
CPU-seconds per task & 45 & 180 & 450 \\
typed-search executions & 1{,}000 & 4{,}000 & 10{,}000 \\
typed-search fitting programs kept & 32 & 128 & 320 \\
rewriting rule lists kept (move rule lists) & 64 (16) & 256 (64) & 640 (160) \\
\midrule
\multicolumn{4}{@{}l}{raised only in the wider check (bounds the code treats as part of the language):} \\
actions considered per view & 8 & 32 & 80 \\
objects, summed over the demonstration inputs & 120 & 480 & 1{,}200 \\
size values offered as guards & 12 & 48 & 120 \\
\bottomrule
\end{tabular}
\caption[]{Bounds of the gap reruns of the shipped three modules. The explanation search used CORA-CAST's five modules
at 15 CPU-seconds per module call, then ten times every execution budget, kept-list budget and CPU cap, with the three
language bounds fixed. The neural entry's CORA second attempt had 15 CPU-seconds per task. Post hoc, exposed public
evaluation, not an official score.}
\label{tab:gapbudget}
\end{table}

\paragraph{The main missing piece, by task.} By the diagnostics' labels:
\begin{itemize}[leftmargin=*]
\item drawing lines or filling regions on the background, 11 tasks: 1ae2feb7, 36a08778, 6e453dd6, 7666fa5d, 7b80bb43,
  8b9c3697, 8f3a5a89, a395ee82, b6f77b65, d8e07eb2 and db0c5428;
\item a tie between that and erasing part of an object, 1 task: 31f7f899, 16 cells each;
\item recolouring part of an object, 4: 1818057f, 4c3d4a41, 71e489b6 and 7c66cb00; erasing part of an object, 2:
  135a2760 and de809cff;
\item copying a shape to a new place, 2: 7ed72f31 and 9aaea919; new cells bordering an object, 1: aa4ec2a5; moves by
  distances that CORA's stopping rules do not produce, 1: b5ca7ac4;
\item size changes, the output built from pieces of the input that are not objects, 9: 20270e3b, 2d0172a1, 38007db0,
  3a25b0d8, 45a5af55, 4c7dc4dd, 58f5dbd5, 78332cb0 and a251c730; copies of input objects arranged in a new grid, 2:
  2ba387bc and e8686506; input objects arranged with new content, 2: 65b59efc and bf45cf4b;
\item a missing guard, 1: d35bdbdc.
\end{itemize}
Some tasks are close. The changed demonstration cells that no CORA action can write number 2 of 66 in 4c3d4a41, 3 of 31
in 7b80bb43, 36 of 174 in b6f77b65, 42 of 178 in 6e453dd6, 44 of 162 in 9aaea919 and 128 of 449 in aa4ec2a5; they are
half or more in 12 of the 21 same-size tasks that have such cells. In none of the 13 size-changing tasks is every
demonstration output a window of its input, even after a turn, a flip or a recolouring, so the crop rule cannot apply.
At the entry's budget guarded rewriting skipped some views of 3 tasks (4c7dc4dd, a251c730 and d8e07eb2) for having more
than 120 objects summed over the demonstration inputs; the wider check searched them, with no fit.

\paragraph{The explanation search.} Each module first searches the demonstrations with no target; every fitting
program is kept with its outputs on the test inputs, and a neural attempt is explained when one of those outputs equals
it. Programs that reproduce every demonstration exist for 4 of the 120 tasks: 62593bfd and 981571dc, e3721c99 (whose
program returns the test inputs unchanged) and 0934a4d8 (whose program leaves 8 test cells open). A second route adds
the attempt as an extra worked example and searches again, as the earlier test did; it explained nothing more. Every
counted program was run again outside the module that proposed it, on every demonstration and on the test input; none
failed, and no module raised an error. At the starting budget (1{,}000 typed-search executions, 15 CPU-seconds per
module call), 40 searches aimed at a neural attempt were cut short, 39 in typed search and 1 in local growth; at ten
times the budget all of them finished. As a filter, keeping a first attempt only when it is explained keeps 1 of the
172 outputs, which is right, against 33 of 172 right first attempts without the filter. Controls: aimed at CORA's own
answer, the search recovers it on all 3 test outputs where CORA has one and rejects it with one cell changed; on 3
tasks whose demonstration outputs were replaced by a planted two-step program (flip upside down, then let cells fall),
it finds that program and rejects the same target turned a quarter. Without a target, typed search stopped at its 1{,}000-execution cap on 11 tasks, 4 of them in the
gap; rerun with 10{,}000 executions, all 11 finished within 1{,}480 executions, and none fitted. The search code never
opens the answer file; the answers were joined afterwards.

\paragraph{Checks on the diagnostics.} The rerun at the entry's budget reproduces the CORA-only entry's 3 answers
exactly. On 62593bfd (Figure~\ref{fig:samefailure}), which CORA solves, the diagnostics' rule-list learner recovers
CORA's own two-rule program from the demonstrations. 981571dc fails the object diagnostics yet is solved by symmetry
completion, so those diagnostics speak only for guarded rewriting. The two analyses and our check used about 2.1
CPU-hours of local CPU, with no GPU and no neural inference.
```

**Appendix figures** (each optional; the gap matrix is the most useful):

```latex
\begin{figure}[p]
\centering
\includegraphics[width=0.92\linewidth]{gap_matrix.png}
\caption[]{The 36 tasks of the gap, by cause. Each row is a public evaluation task on which the neural comparison
entry was right and CORA did not answer, with the number of such test outputs. Filled dot: the cause applies; light
dot under program depth: the part of the change that CORA can already write needs two actions on one object. The
right-hand column is the diagnostics' main missing piece in plain words; for aa4ec2a5 the diagnostic records new cells
that border an object, and on 31f7f899 erased object cells and new line or fill cells tie at 16 cells each, so the
label shown is the first of the two in alphabetical order. In none of these tasks does a program that CORA builds from
one demonstration reproduce even that demonstration. The diagnostic rules were refined while being run on these tasks.
Post hoc, exposed public evaluation, not an official score.}
\label{fig:gapmatrix}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=0.62\linewidth]{gap_example_aa4ec2a5.png}
\caption[]{A near miss. Task aa4ec2a5 (the neural first attempt is right). Every blue shape gets a red border; shapes
with holes also turn light blue and their holes turn magenta. White outlines: 128 of the 449 changed demonstration
cells, all of them new cells bordering an object, which no CORA action writes. On inspection, CORA's outline action
writes every background cell next to an object, holes included, so it cannot draw the border of a shape with holes,
and such a shape also needs two actions at once (recolour and fill its holes), which one action per object does not
allow. No CORA-CAST program reproduces the demonstrations at the entry's budget or in the wider check. Post hoc,
exposed public evaluation, not an official score. Puzzle data: ARC Prize Foundation.}
\label{fig:gapnearmiss}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=0.62\linewidth]{gap_example_38007db0.png}
\caption[]{Building a new grid. Task 38007db0 (both test outputs right on the neural first attempt). The diagnostics
find that the output is built, not cut out of the input, and that no object view gives consistent correspondences: the
output's pieces are not objects under any view. On inspection, separator lines cut the grid into panels; in each row
of panels one panel differs from the others, and the output is the column of those odd panels, so a panel view, a
guard that compares a panel with its row and an action that assembles the chosen panels would all be needed. Post
hoc, exposed public evaluation, not an official score. Puzzle data: ARC Prize Foundation.}
\label{fig:gappanels}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{explain_example_not_explained.pdf}
\caption[]{A missing guard. Task d35bdbdc, third test output (the neural first attempt is right). Every change can be
written by CORA's actions, but no rule list over CORA's guards assigns them, and no program in CORA-CAST's five
modules reproduces the three demonstrations, at the starting budget or at ten times it; the one search that had
stopped at its execution cap, typed search without a target, finished without a fit when rerun with 10{,}000
executions. On inspection, which box's centre colour names which other box's frame colour decides the output, while
CORA's guards test an object's own features and the colours touching or enclosing it. Post hoc, exposed public evaluation, not an official score. Puzzle data: ARC Prize
Foundation.}
\label{fig:gapguard}
\end{figure}
```

## 4. Paper 1, the ARC paper (`paper/final_20261108/cora_final.tex`)

This is a compact version of the same contribution: one sentence in Section 1, and one paragraph and one table in
Section 5. The main text gains about 0.4 pages.

**Paper 1, item 1 (must fix; this fills the marker the brief leaves to this note). Section 1, "The broader question".**
- **Find** "right; and bounded typed search turned none of the 172 neural guesses into a checked CORA program." and
  the marker after it, "\PENDING{an analysis of why CORA cannot explain the outputs the neural entry solves, and what
  CORA must add; it will be inserted after its audit}".
- **Replace both with:**

```latex
right; and a \cast{} program reproduces the demonstrations and gives the answer for only 2 of the neural entry's 344
attempts, both right. On the other 41 query outputs that the neural entry got right, CORA's language, not its search
budget, falls short, and these failures say what CORA must learn to build (post hoc, not an official score;
Section~\ref{sec:arc}).
```

- **Label:** tested capability and interpretation; post hoc, exposed.

**Paper 1, item 2 (new). Section 5, "CORA and CORA-CAST work on ARC".**
- **Find** "CORA is rarely wrong when it answers, but it rarely answers: coverage, not precision, sets the official
  0.83\%." (the end of the paragraph "Checked answers are usually right").
- **Insert after it, as a new paragraph and table:**

```latex
\paragraph{Where the neural entry and CORA each fall short (post hoc; exposed public evaluation, not an official
score).} With two attempts per query output, the neural comparison entry was right on 43 of the 172 query outputs, but
it returns grids, not programs (Table~\ref{tab:neuralgap}). A \cast{} program that reproduces every demonstration and
outputs the neural attempt exists for 2 of its 344 attempts, both right and both among CORA's own 3 answers, and for
none of the 301 wrong ones. On those 3 query outputs, the only ones where CORA has an answer of its own, its check
accepted both right neural attempts and rejected all 4 wrong ones; on the other 169 it can neither confirm nor reject
a neural guess. On the 41 query outputs, in 36 tasks, that the neural entry got right and CORA did not answer, ten
times the search budget (executions, kept candidates and CPU) found no program, and automatic diagnostics on the
demonstrations place the gap in the language: an action is missing in 35 tasks, in 14 of them with object views that
also fail, and a guard in 1. So the failures say what to build next: actions that draw on the background, edit parts
of objects and assemble new output grids, then new object views. All of CORA's answers here come from two
design-exposed tasks, and the neural checkpoint is contaminated for this set.

\begin{table}[t]
\centering\footnotesize
\begin{tabularx}{\linewidth}{@{}YP{4.4cm}@{}}
\toprule
public evaluation, 172 query outputs & count \\
\midrule
neural comparison entry right, either of two attempts & 43 (33 on the first attempt) \\
CORA-only entry answered; right & 3; 3 \\
neural attempts that a \cast{} program explains & 2 of 344, both right; 0 of the 301 wrong \\
neural entry right, CORA no answer & 41 query outputs in 36 tasks \\
\quad a \cast{} program at ten times the budget & none \\
\quad first gap: a missing action & 35 tasks (in 14, object views also fail) \\
\quad first gap: a missing guard & 1 task \\
\bottomrule
\end{tabularx}
\caption{Where the neural comparison entry and CORA each fall short. Post hoc, exposed public evaluation, not an
official score. \emph{Explained}: a \cast{} program reproduces every demonstration and outputs the attempt. Ten times
the budget multiplies executions, kept candidates and CPU caps, with CORA's language fixed. The diagnostics read only
the demonstrations and query inputs, and their rules were refined while being run on these tasks. Both tasks CORA
answers shaped its design, and the neural checkpoint is contaminated for this set.}
\label{tab:neuralgap}
\end{table}
```

- **Label:** tested capability (the explanation counts), measured diagnosis (the causes), interpretation (what to
  build); post hoc, exposed.

**Paper 1, item 3 (optional). Table `tab:negatives`.**
- **Insert after the row** "the official score is 0.83\% & coverage, not precision, limits CORA & grow coverage by
  construction under the CPU cap \\":

```latex
the neural entry was right on 41 query outputs that CORA did not answer, and ten times the budget found no program (post hoc, exposed) & the missing pieces are operations and views, not search & build actions that draw on the background, edit parts of objects and assemble grids, then new views \\
```

**Paper 1, item 4 (optional). Section 8, "The future".**
- **Find** "and then with a trained router on held tasks." **Insert after it:**

```latex
The 41 query outputs that the neural entry got right and CORA did not answer are natural development cases for it,
since for each the diagnostics name the missing kind of change from the demonstrations alone
(Table~\ref{tab:neuralgap}); being exposed, they cannot be its held test.
```

**Paper 1, item 5 (optional; appendix). Table `tab:numbers`.**
- **Insert after the row** "2 of 172 & public evaluation query outputs right by construction & 0 for every other arm &
  reaches a real puzzle; one task, inconclusive & exposed public set \\":

```latex
2 of 344 & neural attempts that a CORA program reproduces from the demonstrations & none of the 301 wrong attempts & CORA can check a neural answer only where its language reaches & exposed public set, post hoc \\
41 in 36 tasks & query outputs the neural entry got right and CORA did not answer & no program at ten times the budget & the language, not the budget, falls short & exposed public set, post hoc \\
```

- Do not add figures to Paper 1's main text. If an appendix page is free, `gap_example_6e453dd6.png` with the Paper 2
  caption (query output for test output) is the one to use.

## 5. Writeup (limit 1,500 words)

Apply to the newest candidate and its copies. The sentence below occurs once in each of these five files:
- in `paper/final_20261108/`: `KAGGLE_DRAFT_PACKAGE/WRITEUP_BODY_v3_candidate.md`,
  `KAGGLE_DRAFT_PACKAGE/WRITEUP_BODY_v2_candidate.md`, `FINAL_PAPER_WRITEUP.md` and
  `FINAL_PAPER_WRITEUP_PASTE_READY.md`;
- `paper/writeup/WRITEUP_PASTE_READY.md`.

**Writeup, item 1 (must fix; Section 1, "The broader question").**
- **Find:** "Neural systems propose answers well but give no explanation that can be run and checked: on the 172 public
  evaluation query outputs the neural comparison entry was right on 43, and bounded typed search could explain none of
  its guesses."
- **Replace with one of two versions** (word counts by `wc -w`; the old sentence has 40 words):
  - **Full version, 56 words (+16):** "Neural systems propose answers well but give no explanation that can be run and
    checked: on the exposed public evaluation (post hoc, not an official score) the neural comparison entry was right
    on 43 of 172 query outputs, CORA's programs explain 2 of them, and for the other 41 its language, not its budget,
    falls short."
  - **Short version, 43 words (+3):** "Neural systems propose answers but give no explanation that can be run and
    checked: on the exposed public evaluation (post hoc, not an official score) the neural comparison entry was right
    on 43 of 172 query outputs, yet CORA's programs explain only 2."
- **Which version.** The v3 body is 1,475 words, or 1,499 with the title lines. The brief's planned Writeup changes
  (its items W1, W2, W3, C1 and C2) are word-neutral together.
  - **If the title is a separate field,** as the brief reads the editor's note: use the full version (1,491). Skip the
    brief's optional item W5 (+8). Its optional item W4 (+5) still fits (1,496).
  - **If the platform counts the title lines:**
    - Use the short version and skip both optional items.
    - Also shorten the code paragraph's run-location sentence (-5): replace "Construction and search-order runs used
      private Kaggle CPU kernels, the held-back-half test local CPUs; receipts and hashes are in the release record."
      with "Runs used private Kaggle CPU kernels and local CPUs; receipts and hashes are in the release record."
    - The total is then 1,497.
  - Check the final count with the platform's own counter.
- **Label:** tested capability and interpretation; post hoc, exposed.

**Writeup, item 2 (optional; it does not fit at the current count).** Use it only if other text is cut. Section 7,
"The future".
- **Find** "Availability and discovery moved; selection is next."
- **Insert after it** (+25 words): "The 41 query outputs CORA misses name what to build first: actions that draw on the
  background, edit parts of objects and assemble new grids."

## 6. Registry rows to add (`paper/writeup/RESULTS_TO_SOURCE.md`)

All paths are relative to the repository root.

**Not yet reproducible from a tag.** This folder is not committed and is not in the public snapshot. Flag these rows
until the author's release step commits and tags it. Nothing here was committed.

| Claim | Number | Source | Field or receipt |
|---|---|---|---|
| neural comparison entry, public evaluation, two attempts | 43 of 172 (33 first attempt, 10 second only, none with both right; 27 tasks with every output right) | `paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json` (9668b1f8); saved `kaggle/score_first_2026/configs/results/h_rehearsal_v1/score.json` | `counts.neural_right`, `neural_first_attempt_right`, `neural_second_attempt_only`, `neural_tasks_every_output_right`; the saved-score block matches the recount |
| CORA-only entry, public evaluation | 3 answered, 3 right (both test outputs of 62593bfd, the one of 981571dc); every other output a copy of the test input | `paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json`; `kaggle/score_first_2026/configs/results/op2_rehearsal_v1/score.json` | `counts.cora_answered`, `counts.cora_right` |
| overlap | 2 right in both (981571dc; the second test output of 62593bfd); 1 CORA only (the first test output of 62593bfd); 44 in either; 128 in neither | `paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json`; `paper/final_push_20261108/neural_vs_cora/CHECK.md` reconciliation table | `counts.both_right`, `counts.cora_right_neural_wrong` |
| the gap | 41 test outputs in 36 tasks (32 on the neural first attempt, 9 on the second; 23 tasks same size, 13 size change) | `paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json`; `paper/final_push_20261108/neural_vs_cora/gap_table.csv` (a378f88b) | `counts.gap_outputs`, `gap_tasks`, `gap_first_attempt`, `gap_second_attempt_only`, `gap_tasks_same_size` |
| causes | missing action 40 outputs, 35 tasks; scene parsing 18, 14 (each also a missing action); missing guard 1, 1; depth first 0; budget 0 | `paper/final_push_20261108/neural_vs_cora/data/gap_summary.json` (c3aa00fe) | `per_cause`, `cause_combinations` (21, 14 and 1 tasks) |
| kinds of missing action | 21 with unwritable cells, 13 built outputs, 1 with moves (b5ca7ac4); guard: d35bdbdc | `paper/final_push_20261108/neural_vs_cora/data/gap_summary.json` | `language_details` |
| main missing piece | lines or fill 11, a tie 1 (31f7f899), recolour part 4, erase part 2, copy 2, bordering cells 1, moves 1, built from pieces 9, copies 2, objects with new content 2 | `paper/final_push_20261108/neural_vs_cora/data/gap_summary.json`; `paper/final_push_20261108/neural_vs_cora/data/diagnostics.json` (23d18f24) | `missing_pieces`; `31f7f899.language.uncovered_kinds`: 16 erased against 10 fill and 6 line cells |
| depth on the writable part; no partial fit | 3 tasks (aa4ec2a5, d8e07eb2, de809cff); 0 of 36 with a partial fit | `paper/final_push_20261108/neural_vs_cora/data/gap_summary.json` | `writable_part_needs_two_actions_tasks`, `partial_fit_tasks` |
| gap reruns (the wider check) | no fit at 1, 4 or 10 times; typed search stopped at 1,000 on 4 tasks at the entry's budget and finished on all 36 at 4 and 10 times (at most 1,480 executions); largest CPU 9.44, 8.31, 8.65 s; 613.5 CPU-s | `paper/final_push_20261108/neural_vs_cora/data/gap_summary.json`; `paper/final_push_20261108/neural_vs_cora/data/budget_runs.jsonl` (034da861) | `fit_any_budget`, `whole_grid_search`, `max_task_cpu_s`, `total_rerun_cpu_s` |
| object cap | 3 tasks with views skipped at 120 objects summed over the demonstration inputs (4c7dc4dd, a251c730, d8e07eb2); searched in the wider check, no fit | `paper/final_push_20261108/neural_vs_cora/data/gap_summary.json` | `object_cap_tasks` |
| near misses | unwritable changed cells 2 of 66, 3 of 31, 36 of 174, 42 of 178, 44 of 162, 128 of 449; half or more in 12 of 21 | `paper/final_push_20261108/neural_vs_cora/data/diagnostics.json` | `<task>.language.per_view[best_view].changed`, `uncovered` |
| explained attempts | 2 of 344, both right; 0 of 139 wrong first attempts, 0 of 162 wrong second attempts; the same at ten times | `paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json`; `paper/final_push_20261108/neural_vs_cora/data/explain/explain_summary.json` (6e4499f2); `paper/final_push_20261108/neural_vs_cora/data/explain/explain_rows.csv` (660c2500) | `explained.1x.table` and the ten-times block |
| searches cut short | at the starting budget, 40 aimed at an attempt (39 typed search, 1 local growth); at ten times, none | `paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json`; `paper/final_push_20261108/neural_vs_cora/explain_analysis.md` Table 4 | `explained.1x.target_status` |
| searches without a target | typed search stopped at 1,000 on 11 tasks; rerun at 10,000, all finish (at most 1,480), none fits | `paper/final_push_20261108/neural_vs_cora/data/check/check_join.json` (7d624e54) | `l0_rerun_at_10000` |
| CORA's reach | a complete answer of its own on 3 of 172 test outputs (2 tasks); a demonstration-consistent program on 4 of 120 tasks | `paper/final_push_20261108/neural_vs_cora/data/check/check_join.json` | `outputs_with_complete_consistent_output_not_the_test_input`, `fit_tasks` |
| CORA's check where it reaches | 2 right attempts accepted, 4 wrong rejected | `paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json` | `explained.1x.neural_answers_where_cora_has_output` |
| explanation as a filter, counts | first attempt kept only if explained: 1 kept, right (unfiltered first attempts 33 of 172); explained attempts only: 2 kept, both right; unexplained first attempts 32 of 171 right; explained second attempt moved first 34 of 172 | `paper/final_push_20261108/neural_vs_cora/data/explain/explain_tables.md` (6728200b) | count columns only; never the percentage columns |
| partial program | 0934a4d8: 19 of 27 cells fixed; both attempts agree on the 19 and are wrong on all 8 open cells | `paper/final_push_20261108/neural_vs_cora/data/explain/explain_partial.json` (893c3dd9); `paper/final_push_20261108/neural_vs_cora/data/check/check_join.json` | `cases[0]`; `partial_0934a4d8` |
| controls | aimed at CORA's own answer: recovered on 3 real test outputs, rejected with one cell changed; planted two-step program on 3 tasks: recovered, quarter-turned target rejected | `paper/final_push_20261108/neural_vs_cora/data/explain/explain_controls.json` (2fb73ee6) | `real` (the two e3721c99 rows return the unchanged input; do not count them), `synthetic` |
| neural entry's CORA side | 1 answer (981571dc), identical to the neural first attempt; nothing replaced | `paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json` | `neural_entry_cora_side_answers` |
| exposure | 62593bfd, 981571dc and 0934a4d8 design-exposed | `experiments/cora_cast_20261026/SOURCE_EXPOSURE_MANIFEST.json`; `experiments/cora_cast_20261026/FINAL_DECISION.md` | manifest lines 43 and 53; decision line 23 |
| contamination | the neural checkpoint is marked contaminated for the set | `outputs/score_first/runs/h_rehearsal_v1/run_info.json` (514a9747) | `rehearsal` |
| earlier zero | 0 of 172 first attempts; 0 reachable without a target; all 172 searches stopped at 150,000 executions; CORA's earlier construction grammar; the same neural file | `experiments/neural_to_program_b_20261103/runs/score/SCORE.json` (e58476b0); `paper/final_push_20261108/neural_vs_cora/data/check/check_counts.json` | `hashes.neural_submission` 558b6ab1 |
| compute | about 0.6 (gap) + 1.38 (explanation) + 0.1 (check) CPU-hours, about 2.1 in all; no GPU | `paper/final_push_20261108/neural_vs_cora/gap_analysis.md`; `paper/final_push_20261108/neural_vs_cora/explain_analysis.md`; `paper/final_push_20261108/neural_vs_cora/CHECK.md` | compute sections |

## 7. Files to copy

| File (in this folder) | sha256 | To | Use |
|---|---|---|---|
| `figures/explain_example_explained.pdf` | 2b8092bc | `paper/v2_neural_cora/figures/` | Paper 2 main text |
| `figures/gap_example_6e453dd6.png` | 05e5f495 | `paper/v2_neural_cora/figures/` | Paper 2 main text |
| `figures/gap_matrix.png` | 52bf16de | `paper/v2_neural_cora/figures/` | Paper 2 appendix |
| `figures/gap_example_aa4ec2a5.png`, `figures/gap_example_38007db0.png` | 72576935, d412460a | `paper/v2_neural_cora/figures/` | Paper 2 appendix, optional |
| `figures/explain_example_not_explained.pdf` | a85d5d32 | `paper/v2_neural_cora/figures/` | Paper 2 appendix, optional |

**About the figures.**
- They are built from saved records and the public task file only. Every grid is a public evaluation grid, shown with
  its task id.
- The figures' own text already carries "Post hoc, exposed public evaluation, not an official score", plain colour
  names and no internal labels.
- `explain_example_explained` prints CORA's program in CORA's own syntax; its caption above gives the program in words.
- `gap_causes.png` is not used, because the table carries the same counts.

## 8. How each correction in `CHECK.md` is applied

| CHECK item | Where it is applied |
|---|---|
| 1. two meanings of "ten times"; CPU caps | Section 2 definition; "wider check" in the Paper 2 section, its table caption and the budget table; each CPU cap stated where used |
| 2. accuracy-style percentages | counts only everywhere; the filter is given as "43 right outputs to 2" (main text) and "1 kept, right, against 33 of 172" (appendix) |
| 3. CORA's reach is 3, not 5 | "on no other test output does CORA have a complete answer of its own"; "rejects all 4 wrong ones"; e3721c99 described separately in the appendix |
| 4. 981571dc design-exposed | the exposure sentence in the Paper 2 section, the Paper 1 paragraph and both table captions |
| 5. earlier test aimed at the same neural run | "Why this differs from the earlier zero"; Paper 2, item 5 (SHA-256 558b6ab1) |
| 6. output numbering | ordinal words only ("first", "second", "third test output") |
| 7. "budget does not explain it in either direction" | replaced by the bounded-by-budget wording in Paper 2, items 2 and 3 and the new section |
| 8. "every search finished" | "every search aimed at a neural attempt"; the no-target rerun at 10,000 executions in the appendix and the d35bdbdc caption |
| 9. object cap | "120 objects summed over the demonstration inputs" (Section 2, budget table, appendix) |
| 10. two module sets | "CORA-CAST's five modules" for explanation; "the shipped three modules" for the gap reruns |
| 11. "rewriting language" | "CORA's language (all three shipped modules)" |
| 12. labels beyond the diagnostics; the 31f7f899 tie | automatic labels in the tables and figures; "on inspection" for the aa4ec2a5, 38007db0, d35bdbdc and 6e453dd6 readings, and b5ca7ac4 keeps its automatic label only; the tie stated ("11 tasks, and 1 more tied"; the matrix caption gives the rule) |
| 13. rules refined on these tasks; first pass not saved | Paper 2 "Limits"; both table captions; the matrix caption; Paper 2, item 8 |
| 14. 39 against 40 cut short | "40 searches ... 39 in typed search and 1 in local growth" (appendix, explanation search) |
| 15. fall-through label | not used in any paper text |
| 16. the neural entry's CORA side | one sentence in the Paper 2 section; registry row |
| 17. naming the neural method | "the neural comparison entry" only; no new naming |
| 18. mixed budgets in one line | main text: "No task used more than 9.4 CPU-seconds" (the largest at any budget); appendix: 9.4 at the entry's budget and 8.7 in the wider check at ten times, stated separately |
| 19. 4 tasks against 3 outputs | "a demonstration-consistent program: 4 of 120 tasks" (appendix) and "a complete answer of its own: 3 test outputs" (main text) |
| 20. "new colours" | not used |
| 21. positive control on e3721c99 | "all 3 test outputs where CORA has one" plus the 3 planted tasks |
| 22. the earlier test's grammar | "CORA's earlier construction grammar" in every replacement |
| 23. combined compute | "about 2.1 CPU-hours" (appendix, "Checks on the diagnostics"; registry) |

## 9. Do not write

- "pushes precision to 100%", "100%", "19.2%", "25.0%", "0.267" or any interval for this material.
- "5 test outputs" or "8 wrong answers rejected" for CORA's reach.
- "CORA explained 0 of 172" or "bounded typed search verified none", unless the same sentence names CORA's earlier
  construction grammar and its budget-bound searches.
- "a separate neural run", "a general program language" or "budget does not explain it in either direction".
- "with its language unchanged" for the gap reruns, which raised three language bounds.
- "query 0", "output 1 of 1", "task:index", "1x" or "10x" in running text. The figures' 1x, 4x and 10x are explained
  in their caption.
- "120 objects per scene", "39 searches cut short" or "rewriting language" for the 35 tasks.
- As diagnostic findings: "a border that stays outside an object", "compound objects", "38007db0 needs a guard" or
  "links between boxes". Use these only as readings marked "on inspection".
- "unseen", "fresh", "held out", "discovered", "proved inexpressible" or "accuracy" for this material.
- Any claim that the neural entry's right answers reveal its reasoning. They may reflect exposure: the checkpoint is
  contaminated for this set.
