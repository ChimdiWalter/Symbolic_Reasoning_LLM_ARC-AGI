# 90-second script (visual-first review poster)

Speak while pointing; each paragraph matches one area of the poster. These are only claims the ledger supports.

**Banner, about 15 s.** My question is whether a reasoner can recognize when its own explanation is inadequate, and
work out what needs to change. Solving a puzzle is not the same as knowing why the answer works. Toni Kazic and I have
been asking this as a broader question about reasoning.

**Column 1, about 20 s.** ARC is a clean place to test it. You get two or three examples and a new input. Here the
frames are filled with a colour that depends on their size. An explanation can fail for different reasons:
- it memorized the examples;
- it saw the wrong objects;
- its language had no rule for the change;
- or the examples simply don't decide between two rules.

Telling those apart is the hard part.

**Column 2, about 30 s.** CORA is my executable system for this.
- On 60 exposed training tasks, its checker accepted 6 answers, all correct. But on 26 tasks every rule that fit the
  examples was wrong on the test: memorization.
- On this real task, CORA built a new conditional rule: blue objects send a line up-left, red ones down-right. It
  rebuilt that rule 3 out of 3 times with an example held out, and it was correct.
- But a version that ignored the failure record found the same rule. On 58 further tasks, construction added zero
  verified solves.

**Column 3, about 25 s.** So the next step is this loop.
- CORA can already notice some inadequacy: competing hypotheses disagree, or a check fails when an example is hidden,
  as on this task, where one colour is seen only once.
- What isn't shown yet is the dashed part: choosing which revision will actually help.

**Close.** Building a rule is not the same as learning which revision improves an unseen prediction. That is what I am
testing next, and later, whether the same revision policy helps with scientific data.
