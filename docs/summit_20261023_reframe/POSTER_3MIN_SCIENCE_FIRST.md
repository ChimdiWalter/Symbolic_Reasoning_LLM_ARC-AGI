# Three-minute walkthrough: science-first poster (review draft, 19 October 2026)

*[Bracketed lines are cues. Every number is in `records/CORA_SUMMIT_CLAIM_LEDGER_20261017.md`. About 520 spoken words,
then questions.]*

## 1. The question (about 30 s)

*[Top band.]*

How can a machine learn the objects, relationships and rules in unfamiliar data, and know what to reconsider when its
explanation is not enough?

That is the general problem. Solving one puzzle is not the same as knowing what the entities are, why a rule works, or
what to change when it fails.

*[Leaf; say "schematic".]*

Biology is the motivating case. This leaf is a schematic, not data. A lesion-mimic pattern shows where cells died, not
which process caused it. A machine reasoning about such data has to infer the entities and the rules too.

## 2. The loop and its two bottlenecks (about 45 s)

*[Trace the loop.]*

Observations go in. The system decides what counts as an object, proposes rules as programs it can run, and tests them
on the examples.

Then it asks whether the account is really supported:
- do rival rules also fit?
- does a rule break when one example is held out?

If not, it chooses what to revise (objects, rule or evidence) and tests the revision. It only ever uses the visible
evidence, never the hidden answer.

*[Orange band.]*

Bottleneck one is measured. CORA often cannot propose a usable rule at all.

*[Pink band.]*

Bottleneck two is open. Can a system learn *which part* to revise, better than strong blind alternatives?

## 3. ARC as the testbed (about 20 s)

*[00dbd492.]*

ARC is our controlled testbed. There are a few examples, a new input and one exact answer. Here each frame is filled with
a colour that depends on its size.

*[Three illustrated causes.]*

A rule can fail for three reasons:
- wrong objects;
- a missing operation;
- not enough evidence to choose between rules.

## 4. What CORA did, and where it fails (about 50 s)

*[ka95aa62f67d9.]*

On this real task, CORA constructed a new conditional rule: blue objects send a line up-left, red ones down-right. It
rebuilt the rule three times with one example hidden, and the prediction was correct.

But be careful with that result:
- this was an exposed training task, not a competition solve;
- a version that ignored the failure record found the same rule, so diagnosis did not cause the gain.

*[0 / 58.]*

On 58 separately selected tasks, construction verified nothing new. It proposed no rule for 55 of them, and its 3
proposals were rejected by CORA's own checks. There were no wrong answers.

*[Visible doubt.]*

Here is what a visible doubt looks like. CORA-v2's guess was right, but one example alone decides the green fill. So it
keeps the guess uncertified.

## 5. What comes next (about 30 s)

*[Small loop; dashed box in the big loop.]*

The next step is a trained neural prior *inside* CORA. It would only order CORA's own search. CORA still runs, checks and
selects every answer. It is proposed and in development; there is no result yet.

*[Baseline line.]*

For context: I reproduced the published NVARC method with Qwen3-4B. It scores 27.64% public. That is their method, not
mine. CORA itself scores 0.00%.

*[Bottom line.]*

If revision selection works on ARC, the reasoning procedure, not ARC's grid operations, could be tested on
independently validated biological questions. That is untested.

## Likely questions

**Why not just use the neural model?**
It already scores far higher. The question here is different: which part of an explanation to change, in a form that
can be inspected and tested. Combining answers added nothing: CORA had no correct answers that NVARC missed.

**Did failure diagnosis help?**
Not yet shown. In every controlled comparison so far, a failure-blind version did as well.

**Is ARC like biology?**
No. ARC is a controlled place to test the reasoning procedure. Any biological test would need its own data, its own
checks and collaborators' approval.
