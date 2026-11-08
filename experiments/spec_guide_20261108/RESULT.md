# Specification-reading guide test: result

Scored once on 8 Nov 2026 at 11:14Z (`runs/held/RESULTS.json`, sha256 3b7f832f...; scoring marker `runs/SCORED`).

**Custody.** Before any held task existed, the protocol was committed and frozen (FREEZE.json f397e0bb..., freeze
commit 4ba64f0c). It then passed its pre-run review (ab6e1378, PASS-WITH-NOTES). The GO was committed alone
(867d6096). Its salt is 0da6cb29..., the sha256 of the committed GO file. The held tasks were drawn from that salt
after the GO, from held families on held-pool grids; both had been reserved since the design note and were never
used in development.
During the run, the half-hourly autosave stored the growing tasks and solutions files in the private repository (from 08:26Z). The run's code never opens solutions, and the scorer opened them only after the seal check and the marker. An independent replay from the seed reproduced the first 1,051 held tasks exactly.

**The run.** Generation capped the held set at 60 admitted tasks per edit type:
- 1,128 tasks in all: 60 for each of 17 edit types and for crop, and 48 for connect, the 18th edit type, which was still short of 60 when the 10,800-second generation limit ended;
- 8,774 tasks traced.

The arms were run directly by the frozen step. The predictions were sealed (f0a05e1e...) before the scorer read any
solution.

**Exposure.** The tasks are made by applying the object step's own language to input grids of the public ARC-AGI-2
training set; its solutions file was never read. No pretrained model is used. The held halves of the natural
benchmarks were not used.

## 1. The measured result

**Correct test outputs** (pass at 2) of 1,128 held tasks at 125 / 500 / 2,000 counted operations. The frozen step in
the hand-set order answers all 1,128 at 20,000 operations, since that is the admission rule.

| order | 125 | 500 | 2,000 | share at 125, each edit type weighted equally |
|---|---:|---:|---:|---:|
| hand-set order | 953 | 1,008 | 1,087 | 0.844 |
| frequency table | 881 | 908 | 994 | 0.781 |
| linear model | 1,018 | 1,036 | 1,072 | 0.902 |
| small guide (the step's own block features) | 1,076 | 1,085 | 1,103 | 0.954 |
| **specification-reading guide** | **1,083** | **1,095** | **1,112** | **0.959** |
| shuffled-specification control | 1,050 | 1,058 | 1,088 | 0.931 |

**Primary (pre-registered): met.** At 125 operations the guide beats each of the three simple orders.

| against | tasks only the guide gets | tasks only the other gets | difference | 95% interval (clustered by edit type) | exact sign test |
|---|---:|---:|---:|---|---|
| hand-set order | 147 | 17 | +130 | 78 to 188 | p < 0.000001 |
| frequency table | 207 | 5 | +202 | 99 to 316 | p < 0.000001 |
| linear model | 68 | 3 | +65 | 25 to 109 | p < 0.000001 |

At 500 operations, the second budget point, the guide again beats all three: +87 (interval 55 to 122), +187 (85 to
300) and +59 (19 to 103).

**Secondaries** (Holm over three; each decided by its Holm-adjusted p together with its interval, as fixed before the run in the pre-run review's condition 5, accepted in the GO):

| secondary | result | Holm p | interval | decision |
|---|---|---|---|---|
| Guide against the small guide | 1,083 against 1,076; 22 tasks gained, 15 lost | 0.32 | -12 to 27 | inconclusive: the expected tie |
| Guide against its shuffled-specification control | 1,083 against 1,050; 52 gained, 19 lost | 0.0002 | -6 to 81 | inconclusive: the interval crosses 0, so the pre-registered rule is not met |
| Linear probe of the encoder's summary (generating edit type, 5-fold cross-validated) | trained encoder 0.646 accuracy, the same architecture with random weights 0.461; most common type 0.053 | < 0.000001 | 134 to 291 tasks | trained encoder beats random weights |

**Predictions, scored once:**
- spec-1, the primary holds at 125: **held**.
- spec-2, the guide against the small guide is not significant: **held**.
- spec-3, the guide beats its shuffled control: **not met** under the pre-registered rule. The interval crosses 0, although the task counts favour the guide 52 to 19.
- spec-4, the probe's trained encoder beats random weights: **held**.

**The guide's own edit-type head**, the output trained to name the edit type that made the task (one of 20 classes),
names the true edit type first on 0.532 of the held tasks (600 of 1,128), and in its top three on 0.885 (998). This
figure is descriptive; it was not pre-registered.

**Work.** At the same budget of 125 counted operations per task, the guide used 106,010 counted operations in all and the hand-set order 101,878; 582 of the 1,128 tasks reach the budget under every order. Per-arm CPU is not comparable in this run: the arms ran in a fixed order on each task, the hand-set order first on cold caches (its 125-operation run took 131.8 CPU-s, more than its 2,000-operation run's 68.0), and the guide's encoder time is counted in the task total, not in its arm. The shared hole setup, meaning the pair analysis and the
features computed once per task, took 365 CPU-s in all.

**By edit type.** The gaps are largest where the hand-set and frequency orders waste budget:

| edit type | hand-set | frequency | linear | guide |
|---|---:|---:|---:|---:|
| fill_box | 35 | 7 | 35 | 51 |
| outbox | 42 | 30 | 45 | 58 |
| mirror_copy | 53 | 28 | 47 | 58 |
| shift | 40 | 53 | 53 | 54 |
| fill_holes | 38 | 30 | 53 | 60 |

The guide and the small guide differ by at most 5 tasks in any edit type.

**Erratum.** Section 1 of the frozen protocol states that the same learner scored 985 with the specification summary
and 979 without it. The order is reversed. On validation at 125 operations:
- without the summary (block features only): 985;
- with the summary: 979;
- the version with the summary gained 5 tasks and lost 11 (p = 0.21).

The protocol stays as frozen. The correction is recorded here and in PROGRESS.md.

**The oracle** is a development measure only: an order that tries the correct block first scored 999 of 1,000
validation tasks at 125 operations. No oracle comparison is made on held data.

## 2. What it taught us

1. **A learned order clearly beats each of the three simple orders tested (the hand-set order, the frequency table and the linear model) at a binding budget.** On fresh held
   families, at 125 operations, the guide answers 1,083 of the 1,128 tasks (96%) that the frozen step answers at
   20,000; the small guide answers 1,076 (95%).
   - Its 1,083 against the hand-set order's 953 is +130 at the same budget (106,010 against 101,878 counted operations in all).
   - It is not new reach: every held task is answered by the frozen step at 20,000 operations.
2. **Almost all of the ordering signal is in the step's own analysis of the specification, not in reading it again.**
   - The small guide, which reads only the step's block features, scores 1,076. The guide, which also reads the raw
     specification, scores 1,083. That difference (+7) is inconclusive.
   - A likely reason, not tested here, is that the step's pair analysis already reduces the specification to what ordering needs: which objects change, which
     edits explain every change, and in which view.
   - This agrees with the development finding, stated before the run.
3. **The encoder does learn the edit type.** A linear probe on its summary recovers the generating edit type with 64.6% cross-validated accuracy, against 46.1% for the same architecture with random weights and 5.3% for the most common type. The information is there, but it did not make the block order measurably better than the step's own features; a likely reason is that the step's deduction has already settled the choice.
4. **The shuffled control is suggestive but not decisive.** Fed another task's specification, the guide loses 33
   tasks (52 against 19), but the edit-type-clustered interval crosses 0. The guide uses what it reads in some edit
   types, not uniformly across them.
5. **A static prior did not carry over to the held set.** The frequency table, learned on the unbalanced training mix, falls below the hand-set order on the held set (881 against 953), although the two were level on validation (879 and 877). This comparison was not pre-registered and its cause is not established. The learned orders that condition on each task's own features stay above the hand-set order.
6. **The earlier tie on natural tasks was a ceiling effect.** On the natural validation units, every learned order
   fits 102 or 103 of 134 at 125 operations (development data), against 104, the most any order reaches at 2,000 operations; in the earlier held run the guide, the linear model and the frequency table scored 318 to 323 against the 329 that the step reaches at 20,000 operations.

## 3. The direction it opens

1. **Steer what the deduction does not settle.** A specification reader earns its place where the step's own
   analysis leaves the choice open:
   - which predicate selects the changed objects;
   - which parameter values to use;
   - operations outside the current language.
   The block order is not such a decision.
2. **Use the encoder to propose, not only to order.** The probe shows that it represents the edit type from raw
   pairs. A natural next test conditions candidate generation on it, for example proposing the edit and its parameters
   before the pair analysis, and measures reach rather than efficiency.
3. **Natural tasks need harder cases.** Every learned order sits near the ceiling there. Efficiency claims on natural
   data need tasks or languages where the budget binds.

*Label:* a learned, specification-reading guide, a step toward neural guidance for program synthesis, not "the
transformer for program synthesis". *Precedents:* DeepCoder, RobustFill, BUSTLE, CrossBeam and LambdaBeam, and
neural-guided deductive search.
