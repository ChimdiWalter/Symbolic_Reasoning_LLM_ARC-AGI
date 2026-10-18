# Two-minute research pitch (REVIEW DRAFT, 18 October; for Toni, Chris and Pierce)

**About 290 words, roughly 2 minutes spoken.** Numbers as in `records/CORA_SUMMIT_CLAIM_LEDGER_20261017.md`.

---

I work on a question that matters beyond puzzles: when a reasoning system fails, how does it know **what to
change**? It might be seeing the objects wrongly, applying the wrong rule, or simply lacking evidence.
Fixing the wrong one can break what already worked.

ARC is my laboratory. Each puzzle gives a few examples, and the answer is checked exactly. My system,
CORA, solves puzzles by writing small executable programs.

The first thing I learned was sobering. On 60 real practice puzzles, CORA's careful check accepted only
6 answers, all correct. In 26 puzzles, though, it found programs that fitted every example and were all
wrong. It had memorized instead of understood, and more search did not fix that.

So I built a way for CORA to construct a missing rule, plug it into its unchanged solver, and check it by
rebuilding it with each example hidden. It now works on one practice puzzle and on one real ARC puzzle. On
the real one, it built a rule that says where an operation applies as well as what it does: blue objects
shoot a ray up-left, the others down-right.

Here is the honest part. A version that ignores the failure record finds the same rule. In a frozen
10-puzzle test, the failure record gave 2 correct answers against 1, which is not evidence. A simple rule
book that picks which fix to try missed the one puzzle that extra search had solved.

So building a rule and learning what to change are different capabilities, and only the first is shown.
The second is my research question. A 58-puzzle test is running now.

The longer goal is to see whether that skill, the policy for deciding what to revise, transfers to
science: deciding whether a molecular model needs a new representation, a revised hypothesis or a new
experiment. That is a proposal; nothing in biology has been tested.

---

*Benchmark line, if asked:* native CORA scores 0.00 on Kaggle. A reproduction of the published NVARC model
scores 27.64, and it is not CORA.
