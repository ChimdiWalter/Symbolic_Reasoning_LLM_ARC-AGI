# P3 synthetic safety preflight: result (2026-10-12)

**Verdict: P3_REJECTED.** S1 failed. The kill rule applies:
- the negative result is preserved;
- the mechanism is not tuned;
- the native-success regression check (step 8) and the kf892487f1049
  mechanistic check (step 9) are NOT run;
- no real-development comparison is requested for P3.

## Identity

| item | identity |
|---|---|
| protocol | `docs/CORA_P3_SAFETY_PREFLIGHT_v1.md` (7997679; section 8 clarification in 884d147) |
| implementation | `cora_p3/` (884d147): two marked `# P3` lines in a generated copy of `inducer._induce_candidate`; 6 tests pass |
| frozen | b594223 (`outputs/p3/p3_manifest.json`) |
| corpus | 24 negative-control tasks + 17 adversarial tasks (`outputs/p3/adversarial_corpus.json`, sha256 `226dc3ba...`) = 41 synthetic tasks |
| arms | BASE, BASE_REPEAT, P3, at 20 s each |
| run | ONCE, 2026-10-12T18:57Z, 406 s wall, 123 rows |
| rows | `outputs/p3/preflight_rows.jsonl`, sha256 `30fab64f...` |
| summary | `outputs/p3/preflight_summary.json`, sha256 `8f10bd3e...` |
| evidence commit | 98c9bed |

Freeze problems were 0 before and after the run, and the six historical
freezes were 0 before it.

## Results

**Native noise.** BASE and BASE_REPEAT agree on all 41 tasks, so no task is
UNSTABLE.

| task | BASE | P3 | how |
|---|---|---|---|
| translate_down_0 | CORRECT (S1) | REJECT | P3 admitted S6 and S7; rejected at the engine's own leave-one-out (2 of 3 folds) |
| translate_down_1 | CORRECT (S1) | REJECT | same |
| translate_down_2 | REJECT | FALSE_ACCEPT | an S7 program passes every engine gate and is wrong on held-out demonstrations |
| ADV:translate_down_505 | REJECT | FALSE_ACCEPT | same, S7 |
| ADV:translate_down_500 | REJECT | CORRECT | an S7 program; the only gain |

- **S1 (safety): FAIL.** 2 regressions and 2 new false acceptances. In both
  regressions, a program from an admitted view displaced the native S1
  program at full data. Which admitted view it was is not recorded.
- **Gains:** 1.
- **S2 (exposure integrity): PASS.** The 7 unexposed tasks are byte-identical:
  program, acceptance and outcome. That includes the drop-only tasks, so
  dropping duplicates was neutral to selection wherever no view was
  admitted.

**Outcomes over the 41 tasks:**

| arm | CORRECT | REJECT | FALSE_ACCEPT |
|---|---|---|---|
| BASE | 15 | 23 | 3 |
| P3 | 14 | 22 | 5 |

**Where the changes fell.**
- Program identity changed on 5 tasks, all translate_down, all exposed.
- No family D fixture, and no native success other than translate_down_0
  and translate_down_1, was displaced.

**Compute.**

| arm | CPU s | wall s | budget exhausted (runs) |
|---|---|---|---|
| BASE | 490 | 510 | 11 |
| P3 | 566 (+15.5%) | 589 | 15 |

**Re-tag audit.** 10 BASE-accepted programs were re-run with each of their 15
INDUCTION-equivalent views on the held-out inputs. Predictions diverged 0
times. The static audit's unseen segmentation divergences (9 of 231 synthetic
pairs) did not reach these programs' predictions. That is a property of this
corpus, not a guarantee.

## Interpretation, kept apart

| question | answer |
|---|---|
| A. representation availability | improved by construction on exposed tasks |
| B. program recovery | 1 task gained |
| C. independent leave-one-out stability | not improved: 2 natively stable tasks lost acceptance |
| D. unseen correctness | worse, net: 1 gained, 4 harmed (2 correct answers lost, 2 false acceptances) |
| E. constructed semantic capability | not addressed: P3 is a representation correction |

**Mechanism.** It is the same channel the negative controls exposed. Freeing
cap slots lets the coarse proximity view S7 (and S6) be searched. The winner
key breaks ties toward fewer objects. A coarse view's program can then win
and either fail the engine's leave-one-out or pass it while wrong.

**What this shows.** Redundancy in the cap is real, but the cap, the trial
order and the tie-break also act as an inductive bias that keeps the
last-resort view out. Removing duplicates is not neutral once it admits
views.

## Claim ceiling

Synthetic preflight only, 41 tasks, with correlated families (all the harm
came from one family). No real ARC evidence. No change to the frozen pilot,
reach v1, the diagnosis or the stopped reach v2 recheck.
