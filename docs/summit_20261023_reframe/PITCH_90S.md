# 90-second explanation for François Chollet and Mike Knoop (REVIEW DRAFT, 19 October)

**About 220 words.** Every number is in `records/CORA_SUMMIT_CLAIM_LEDGER_20261017.md`.

---

CORA is an executable reasoner for ARC. I instrumented where it fails. On 60 exposed training tasks, its
leave-one-out check accepted 6 answers, all correct. But on 26 tasks it found programs that fit every
demonstration and were all wrong. It memorizes.

So I built a loop that constructs a missing operation, installs it in the unchanged engine, and verifies it
by rebuilding it with each example held out. It worked once on a synthetic task and once on a real
training task, with a rule that says where it applies as well as what it does.

Then the negative results:
- a failure-blind constructor found the same rules;
- on 58 independently selected tasks, every construction variant scored 0, with 0 wrong;
- a hand-designed revision controller missed the one task extra search fixed.

An evaluator-only check suggests why: for 50 of the 58, no single expression in my grammar fits the changed
cells in any of seven object views. That is a hypothesis about the language's reach, not a proof.

So the question I'm bringing is: how does a reasoner tell whether to change its explanation, its
representation, or its language, and learn that? My next test is whether failure evidence can drive
**language** growth that survives held-out checks. A separate experiment on exactly that is running now.

---

*If asked about the leaderboard:* native CORA scores 0.00 and the CORA-FHR entry scores 0.00. The 27.64 is
a reproduction of NVARC, not CORA.
