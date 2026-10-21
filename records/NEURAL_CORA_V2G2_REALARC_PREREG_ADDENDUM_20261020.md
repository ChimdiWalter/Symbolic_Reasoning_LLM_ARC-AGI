# ncv2-g2 real-ARC check: pre-registered addendum (20 October 2026)

**Status:** committed **before** the scored run. It changes nothing in the frozen protocol
(`records/NEURAL_CORA_V2G2_REALARC_PROTOCOL_20261020.md`, freeze `8bb377d`): not the cohort, code, budgets,
thresholds, measures or decision. It adds disclosures and descriptive analyses. The analyses run on the evaluator
side after `score`, via `scripts/neural_cora_v2g2_realarc_analysis.py`, and **cannot change the frozen decision**.

## 1. Disclosures

1. **Recovered, not invented.** ncv2-g2's program-class candidates come from three sources:
   - native CORA's own inducers, run under the sealed v23 flags: pixel rules, panel reductions, generative programs;
   - enumerated symmetry-completion and counting forms;
   - a bounded single-generator enumeration.

   A correct answer produced this way is **recovered native capability**: it is neither learned nor new program
   semantics. The report attributes every correct ncv2-g2 prediction to its program form (§2A).
2. **Why the thresholds (+3, ≤ 1 loss on 40 paired tasks).** The exact one-sided sign test on discordant pairs gives
   p = 0.125 for 3 gains / 0 losses, 0.0625 for 4/0 and 0.031 for 5/0. The frozen rule is therefore an
   **engineering gate**, to direct development effort. It is **not a significance claim**, and the report will give
   the sign-test p. The expected ncv2-g1 baseline is about 0–2 of 40 (it found 1/60 on dev60).
3. **Caveats** the report must carry prominently:
   - **Same-shape scope.** The cohort keeps grid shape, so ncv2-g2's counting and panel classes cannot help. These
     produced 35 of the 120 new solves in the synthetic study.
   - **Multi-test tasks.** 3 tasks have several test inputs. The ncv2 arms score the first test output only; native
     is also reported on all outputs.
   - **Coverage is among retained predictions.** Correct-candidate coverage counts only the at most 50 distinct
     predictions kept.
   - **Development evidence.** These are public training tasks, seen by v23's run and in NVARC's training mix.
     A NO_REAL_GAIN would not show that ncv2-g2 fails across real ARC, especially on size-changing tasks.
4. **Exposure so far.** The freeze step loaded the cohort's demonstrations and test inputs (what the solver sees)
   only to count multi-test tasks. No test output has been read and nothing was printed.

## 2. Descriptive analyses (evaluator side, after `score`)

**A. Program-class contributions.** For every correct ncv2-g2 prediction, the form of the program behind it:
- an object program (its selector and action ops);
- an enumerated symmetry or counting form;
- a native-induced pixel, panel or generative form;
- an enumerated generator.

**B. The failure sources, per primary task.** Native's own certified programs for these tasks are the only available
ground-truth programs.

| source | how it is judged |
|---|---|
| *semantic expressivity* | A native certificate that decompiles into ncv2-g2 is **expressible**. One that fails to decompile is a **language gap**. With no native certificate, it is **unknown** |
| *generator coverage* | for expressible certificates: is the decompiled program structurally in ncv2-g2's candidate set, for its own task's demonstrations (no answers)? |
| *budgeted search reach* | did ncv2-g2 fit within 3000 candidates, and at which first-fit position? |
| *hypothesis selection* | is a correct candidate retained but not among the two attempts; are there wrong attempts? |
| *prediction correctness* | pass@2 |

**C. Wrong predictions.** Per arm, the demonstration-fitting attempts that are wrong.

**D. Paired statistics.** The sign-test p for ncv2-g2 vs ncv2-g1 on pass@2. Paired ncv2-g2 vs native on
first-test correctness.

**E. Multi-test tasks,** listed with native's per-output correctness.

The same analyses are reported separately for the 4 LEFTOVER tasks.
