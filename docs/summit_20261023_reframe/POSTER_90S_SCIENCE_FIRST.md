# 90-second script: science-first poster (review draft, 19 October 2026)

*[Bracketed lines are cues, not speech. About 220 spoken words.]*

*[Point to the question at the top.]*

The question I care about is broad. How can a machine learn the objects, relationships and rules in unfamiliar data,
and know what to reconsider when its explanation is not enough?

*[Point to the leaf.]*

Biology shows why this is hard. An image of maize lesion mimics shows a pattern, not the process behind it. The right
entities and rules are part of what has to be inferred.

*[Trace the loop from left to right.]*

So I study one reasoning loop: find objects, propose rules as runnable programs, test them, ask whether the account is
really supported, and if not, choose what to revise and test the revision. It uses visible evidence only, never the
hidden answer.

*[Point to the two shaded areas.]*

There are two bottlenecks. The first is measured: my system, CORA, often cannot propose a usable rule at all. The
second is open: can it learn which part to revise?

*[Point to ka95aa62f67d9.]*

Here is real evidence. On this ARC task, CORA built a new rule (blue sends a line up-left, red down-right) and rebuilt it
three times with an example hidden. But a version that ignored its failures found the same rule.

*[Point to 0 / 58.]*

And on 58 more tasks, construction proposed no rule for 55 of them.

*[Point to the dashed box.]*

Next, a trained neural prior would order CORA's own search, inside the loop. It is proposed; there is no result yet.
