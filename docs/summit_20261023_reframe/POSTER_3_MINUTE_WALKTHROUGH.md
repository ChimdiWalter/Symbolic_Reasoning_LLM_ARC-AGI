# Three-minute walkthrough (visual-first review poster)

Each step names what to point at and what to say, followed by the likely question and an honest answer.

## 1. The question (banner), about 25 s

**Point at** the central question.

**Say:** "When a reasoner's explanation of a problem is inadequate, can it tell whether it needs different objects, a
different rule or better evidence, and choose a change that improves predictions on new problems? This came out of
conversations with Toni Kazic. ARC is my laboratory. The longer-term question is whether that revision procedure, not
the grid operations, transfers to scientific data."

> **Q: Isn't this just program synthesis?** Building a program is one part. The question is choosing which part of an
> explanation to change, and showing that the choice beats doing everything blindly.

## 2. What an ARC task is (column 1, top), about 20 s

**Point at** the real 00dbd492 grids.

**Say:** "Two examples and a new input. Each frame gets filled with a colour that depends on its size. You have to infer
that from two examples."

## 3. Four reasons to revise (column 1, illustrative panels), about 30 s

**Point at** A to D.

**Say:** "These are drawn to explain, not results.
- A: a copied rule fits the examples and fails a new input.
- B: the same grid can be split into objects in two ways.
- C: the right objects, but no available operation draws this line.
- D: two rules both fit, and they disagree on a new input.

A system that fails doesn't know which of these happened. Telling them apart from the examples alone is the problem."

## 4. What CORA showed (column 2), about 50 s

**Point at** 6 and 26.

**Say:** "On 60 exposed training tasks, CORA's object reasoner accepted 6 answers, all right. But on 26 tasks every rule
that fit the examples was wrong on the test. Fitting is not explaining."

**Point at** the ka95aa62f67d9 grids.

**Say:** "Here CORA constructed a new conditional rule: blue objects get a line up-left, red down-right. It rebuilt it 3 of
3 times with an example hidden, and the answer is right. Two honest limits:
- the task was chosen during development;
- a version that ignored the failure record found the same rule.

So it shows construction, not that diagnosis caused the gain."

**Point at** 0 / 58.

**Say:** "On 58 separately chosen tasks, construction added no verified solve and made no wrong one."

> **Q: Why so low?** An evaluator-only check suggests that most of those tasks fall outside the single-rule language
> that construction used. That is a hypothesis about expressivity, not proof that they need new semantics.

## 5. The loop I am building (column 3), about 40 s

**Point at** the diagram. Solid boxes are built; dashed boxes are not validated.

**Say:** "CORA-v2 keeps every hypothesis that fits and notices when they disagree, or when a check fails with an example
hidden. On 00dbd492 it produced the right answer, but one colour appears in only one example, so it cannot certify it.
That is 'not enough evidence', detected from the examples alone. CORA never sees the hidden answer. What I have not
shown is the dashed part: that diagnosing the cause picks a better revision than trying everything. Adding more rules
everywhere can even turn a unique answer into a tie."

**Point at** Inventing new operations.

**Say:** "Separately, an automatic rule-language experiment asks whether the system can build new operations itself. It
is 475 of 497 proposal units in, with no verdict."

## 6. Benchmarks and science (bottom band and transfer box), about 15 s

**Say:** "On the official board, native CORA and CORA with rule construction score 0.00. My reproduction of NVARC, a
third-party neural method, scores 27.64. That is a baseline, not CORA. What might transfer to biology is the
revision policy: proteins, single-cell data, maize lesion phenotypes. That is future work, untested."

> **Q: Why not just use the neural model?** "I reproduced the NVARC Qwen3-4B approach and obtained 27.64 on the
> public ARC-AGI-2 board. That is not my algorithm, but it gives me a strong neural baseline. My own work, CORA, uses
> executable programs to investigate why hypotheses fail and what needs to change. My experiments point to limited
> representation and program expressivity as major obstacles. More search, or adding symbolic answers to the neural
> model's, has not fixed that. I am now interested in whether neural models can propose better representations and
> candidate rules, while the executable reasoner diagnoses what is inadequate and independently tests each revision.
> The combination is a question, not something I have built."

**Close:** "Building a rule is not the same as learning which revision improves an unseen prediction. That is what I am
testing."
