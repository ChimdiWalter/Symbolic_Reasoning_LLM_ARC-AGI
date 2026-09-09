# CORA evidence ladder, and the manuscript statement it supports

Updated 2026-09-09 after LAS-R1 (commit `66afede`). The synthetic LAS branch is
closed. Entries are kept separate on purpose: each says what is established, by
what, and what it does not license.

## The ladder

| rung | status | evidence |
| --- | --- | --- |
| search / prior transfer | **YES** | source-derived concrete structures transfer to disjoint tasks; LAS-R1 shows lower marginal search cost on fresh targets, 243,503 units against ordinary search's 268,937 over 256 targets |
| predictive-selection transfer | **YES, narrowly** | frozen learned knowledge changes which demonstration-consistent explanation is selected; whole-prior ablation removes exactly 4 held-out successes |
| abstraction information | **YES, narrowly** | LAS beats 32 of 32 matched-space controls that share its masks, slot types and expansion cardinality and differ only in having pseudo-random rather than source-derived constants |
| robust LAS greater than CONCRETE | **NO** | the pre-declared replication gate failed: +3 with a 95 per cent paired bootstrap interval of [-1, 8] |
| bounded search-reach gain | **NO** | zero witnesses; every policy fit the identical 188 of 256 targets |
| Level 3A efficiency transfer | established independently, now additionally supported | LAS-R1 target-time efficiency |
| Level 3B capability transfer | **NOT achieved** | requires baseline failure, success with the addition, demonstrated use of it, passing leave-one-out folds, correct final output, and loss of the gain on removal |
| Level 4 semantic self-extension | **PENDING** | the separate frozen Step-B experiment |
| full-pipeline LOO for LAS | **NOT MEASURED** | no certification procedure was run and none is claimed |

## The central boundary

Learned abstractions changed **which** explanation was selected and **how
quickly** it was found. They did not make any new target reachable under the
declared 3,000-fit procedure. Predictive-selection transfer is not capability
transfer, and this is neither Level 3B nor Level 4.

## Descriptive analysis, explanatory only

Artifact-only, no new generation, and it cannot and does not alter the
replication verdict.

**One concept accounts for every held-out difference LAS has.** The concept
`(0,0)|pair(0,2)|m3:1011` produced all four LAS-versus-ordinary rescues, all
four LAS-versus-concrete wins, and the single LAS-versus-concrete loss.

**Most of the retained library is inert.** Of the eight frozen concepts, three
were ever selected in the prior phase across 256 targets and **five were never
selected at all**:

| concept | prior-phase selections | expansion |
| --- | --- | --- |
| `(0,0)\|pair(0,2)\|m3:1011` | 126 | 160 |
| `(0,0)\|pair(0,1)\|m3:1101` | 37 | 400 |
| `(0,0)\|pair(1,4)\|m3:1110` | 13 | 160 |
| the other five | 0 | - |

**Producing a selection is not the same as being necessary**, and the two
measurements disagree in an instructive way. The top concept produced all four
rescues, yet removing it alone loses only one held-out success, because on the
other three the remaining concepts or the ordinary fallback still find a correct
program. Removing the whole prior loses all four. So the effect is genuinely
library-level even though a single concept is the proximate cause of each
individual selection.

**Three of the four rescues cost the same as ordinary search.** On targets 141,
194 and 211 both LAS and ordinary search spent identical units, 15, 13 and 13
respectively, and simply arrived at different programs, where ordinary search's
fit the demonstrations and predicted wrongly. Only target 19 shows a speed
effect, 130 units against 375. So the rescue mechanism is selection, not search
efficiency.

**LAS ranks first on both axes**, held-out correctness and total cost, ahead of
concrete, R1, R2 and ordinary.

**The null distribution is wide and its top is close.** The 32 controls run
117, 117, 128, 129, 132, 132, 133, 136, 138, 138, 139, 142, 146, 148, 148, 148,
157, 158, 158, 158, 158, 159, 159, 160, 160, 160, 160, 160, 160, 161, 162, 162
against LAS's 164. LAS beats all of them, but the best control reaches 162, so
the margin over the strongest random-terminal assignment is two targets. On cost
LAS used 243,503 units against a null minimum of 248,550.

## The defensible manuscript statement

> In a synthetic compositional setting, source-derived programs supported
> automatically selected abstractions whose retained invariants affected
> predictive hypothesis selection and reduced marginal search cost on fresh
> tasks. A preregistered comparison against concrete memory did not robustly
> replicate, and no increase in task reach was observed.

This must be kept separate from Step-B semantic self-extension, from ARC
performance, and from Level 3B capability transfer. No em dashes in manuscript
prose, no AI attribution, and `cora-tti-dev` is not merged into main.

## What is now the bottleneck

The open question is no longer whether experience can be reused, nor whether
learned invariants carry information. Both have evidence. It is whether failure
can produce genuinely new operational capability, meaning a previously
unreachable transformation becomes reachable and the gain is causally verified.
LAS does not answer that, and no further search-prior experiment substitutes for
it. The frozen Step-B experiment is positioned to test it.

## Closed

LAS-v1 and LAS-R1 are completed evidence and are frozen prior results. No LAS-v2,
no retraining, no changes to masks, grouping, objective or expansion cap, no GPN,
no learned selector, no further matched-control study, no rerun at larger N, no
change of primary comparator, and no global promotion. No new statistic will be
sought that converts NOT ROBUSTLY REPLICATED into a positive primary conclusion.
