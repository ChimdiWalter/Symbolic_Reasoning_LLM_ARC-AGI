# Real-task check: native CORA, ncv2-g2, ncv2-g3 and ncv2-g4 on a fresh eligible cohort (21 October 2026)

**Status: FROZEN** in the commit that adds `records/NEURAL_CORA_REALARC_G2G3G4_FREEZE_MANIFEST.json`. **NOT RUN.**
Runner: `scripts/neural_cora_realarc_g2g3g4_eval.py`. Its `solve` stage refuses unless this protocol and the manifest
are committed unchanged, every code, cohort and native hash matches, `--authorized` is given, and the flag
`outputs/neural_cora_realarc_g2g3g4/READY_TO_RUN` exists. Only the lead creates that flag, after syn-v4 has finished,
so that no more than 2 workers run at a time.

**Authorized** by the user in their own words ("do this all", then "the experiments", 21 October 2026), in reply to
the recommendation to run one real-task check comparing ncv2-g2, ncv2-g3 and ncv2-g4 on a fresh eligible cohort,
whose steps were: authorize the metadata-only eligibility check; prepare and freeze the protocol; run it.
**Licensed by** syn-v3's GO_ENGINEERING (`records/NEURAL_CORA_V2G3_SYNTHETIC_REPORT_20261021.md`: it licenses only
proposing a real-task check of ncv2-g3 on a fresh eligible cohort) and by the frozen g4 protocol, section 9
(`records/NEURAL_CORA_V2G4_PROTOCOL_20261021.md`), which specified how a real cohort judges ncv2-g4.

## 1. Question

On real ARC-AGI-2 tasks, does joint rule construction (ncv2-g3) find more correct programs than the recovered native
classes alone (ncv2-g2), and does representation-aware construction (ncv2-g4: parts of objects, regions, lines) add
correct programs on top of ncv2-g3, at equal candidate budget and against a CPU-matched ncv2-g3? Native CORA v23 is
the reference. On 20 October, ncv2-g2 gained 1 task over ncv2-g1 on 40 such tasks (NO_REAL_GAIN); the failure
analysis then pointed at representation.

**It is development evidence, not unseen performance.** The tasks are public ARC-AGI-2 training tasks: the sealed v23
1000-task baseline saw them, and NVARC's checkpoint was trained on this file (no Qwen component is used here).

## 2. Cohort (fixed before any run)

- **Candidates:** `scripts/neural_cora_realarc_g2g3g4_eval.py prepare`
  (`outputs/neural_cora_realarc_g2g3g4/cohort_candidates_20261021.json`, sha `06f3bb8c...`). The rule continues the
  pilot's published order (`records/pilot_v1/selection.json`: ascending sha256('cora-real-arc-pilot-v1|' + id); scope:
  at least 3 demonstrations, grid shape kept, every demonstration changes a cell). Excluded: dev60, the frozen 120
  pilot, the 240 stand-ins, the 100 candidates of 19 October, the 100 candidates of 20 October (which include that
  check's 40 and its 4 leftover tasks), and every in-scope ID named in any of the 17,368 files scanned under `records/`
  and `outputs/` (no file named enough IDs to count as a catalogue). Of 548 in-scope tasks, 465 are excluded and **83
  remain: all 83 are candidates.** This is the whole remaining in-scope pool: after this check no unused in-scope public
  training task remains under the pilot's scope rule.
- **Eligibility:** the frozen, metadata-only Step B checker (`tools/stepb_eligibility/check_eligibility.py`, sha
  `357fb6fe`, unchanged since 5c5401a), ONE authorized run on 2026-10-21T22:37Z: **PASS, 34 of 83 eligible** (eligible
  sha `5d882c45...`; `outputs/neural_cora_realarc_g2g3g4/eligibility/`, with `RUN_LOG.txt`). It read only task IDs and
  split labels of Step B's sha-verified manifest; nothing of Step B was modified.
- **PRIMARY cohort: all 34 eligible tasks** (pre-registered n = 34). 1 of them has several test inputs. The decision
  is taken on this cohort; there is no leftover stratum.

## 3. Arms

Each (task, arm) runs in a fresh worker process. Budgets: 3,000 candidates and 120 CPU-s per task for every ncv2 arm.

| | arm | what runs |
|---|---|---|
| A | `native` | native CORA v23, the unchanged funnel harness (`cora_funnel.run.job`, native mode: sealed v23 flags, CPU clock, its own cooperative budget and hard cap); it submits its certified predictions (reference, no gate) |
| B | `g2` | `cora_neural_v2g2.search.search`, byte-identical to its GO_ENGINEERING version (checked at freeze against `records/NEURAL_CORA_V2G2_SYNTHETIC_FREEZE_MANIFEST.json`). It searches the first test input (its view deduplication sees every input); its two attempt programs are then executed on every other test input |
| C | `g3` | `cora_neural_v2g3.search.search`, byte-identical to the syn-v3 GO version (checked against `records/NEURAL_CORA_V2G3_SYNTHETIC_FREEZE_MANIFEST.json`), on every test input |
| D | `g4` | `cora_neural_v2g4.search.search` at 6baf61b (checked against `records/NEURAL_CORA_V2G4_FREEZE_MANIFEST.json`), on every test input |
| D-a | `g4_no_construct`, `g4_no_invert` | the g4 ablations, exactly as `scripts/neural_cora_v2g4_eval.py` `run_arm` defines them (imported unchanged; its hash is checked) |
| C-cpu | `g3_cpu` | ncv2-g3 with 9,000 candidates and the CPU that g4 used on the same task (at most 120 s): matched compute, as in the g4 protocol |
| E | hook | **the CORA-ONLY-G3 competition configuration from `kaggle/cora_original_2026/`, added by a frozen addendum (its own code hash) before the run starts; if no addendum is frozen before the run, E is not run.** The addendum is `records/NEURAL_CORA_REALARC_G2G3G4_ARM_E_MANIFEST.json` (committed, with an addendum document it names), giving `entry.path` (a module), `entry.function` (`fn(task, budget, cpu_cap_s)` returning `predictions` for the first test input and `attempts_by_test`) and the sha256 of every file E uses. `solve` checks it when it starts; a present but invalid addendum stops the run. E runs in phase 1 with the same budgets; it is reported descriptively, with no gate, and arms A to D never depend on it |

Order: phase 1 (B, C, D, the ablations, and E if frozen), phase 2 (C-cpu, paired with D), then A. 2 workers at nice 10.
Estimate: the ncv2 arms about 3 to 6 CPU-hours (g4 and its ablations can exceed 120 s because their leave-one-out
selection runs after the cap), native about 3 CPU-hours (20 October: 293 CPU-s per task on average); about 3 to 5 hours
of wall time.

## 4. Measures (PRIMARY cohort)

- **pass@2, all outputs (primary):** a task counts only if, for EVERY test input, one of its two attempts equals the
  expected output (Kaggle-like, strict). **pass@2, first output:** the first test input only, as on 20 October.
- **Correct-candidate coverage (first output):** some retained prediction (at most 50 distinct, within the budget)
  equals the first expected output. Native: any train-exact candidate output, first output and all outputs.
- **Fits** (a demonstration-consistent program), **wrong attempts** (attempts submitted, none correct on all outputs),
  **per-test results** for the task with several test inputs.
- **Gains and losses** (pass@2, all outputs): C vs B, D vs C, D vs B, D vs C-cpu, E vs C; and **every arm against
  native CORA (A)**, whose success is a certified prediction correct on every output.
- **Incorrect accepted certificates:** native certified-but-wrong tasks (category CERTIFIED_WRONG).
- **Candidate diversity:** retained distinct predictions per task (mean) and distinct predictions found.
- **Native executions per arm:** candidate evaluations (each a native execution of one program on the
  demonstrations, stopping at the first failure) plus, for g4 arms, construction's and leave-one-out's native runs
  (selector and local checks, counted per demonstration); both are reported separately and summed.
- **CPU** per arm (total and median), native hard timeouts, peak memory.
- **g4's correct attempts by origin** (inversion, construction, geometry, g3 stream).

## 5. Scope and comparability

The cohort keeps grid shape, so counting and panel classes cannot help. The 20 October check scored the first test
input only; this check's primary measure scores all outputs, and the first-output numbers are reported beside it.

## 6. Decision rules (frozen, PRIMARY cohort, pass@2 all outputs unless stated)

1. **GO_REAL_G3** if all hold, else **NO_REAL_GAIN_G3**: C pass@2 - B pass@2 ≥ **3** tasks; C coverage - B coverage
   ≥ **3** tasks; paired losses of C against B ≤ **1**.
2. **GO_REAL_G4** if all hold, else **NO_REAL_GAIN_G4** (representation on top of construction; condition 4 is the
   g4 protocol's section 9 compute control): D pass@2 - C pass@2 ≥ **3**; D coverage - C coverage ≥ **3**; paired
   losses of D against C ≤ **1**; D coverage - C-cpu coverage ≥ **2**.

D against B, the ablations, E and every comparison with native are descriptive (no gate). The exact one-sided sign
test on discordant pairs is reported (for 3 gains and 0 losses p = 0.125): the thresholds are engineering gates, not
significance claims.

**What follows:** GO_REAL_G3 and/or GO_REAL_G4: design and freeze (not run) a larger confirmation on a cohort that does
not share this scope rule (for example size-changing tasks), with its own authorization; never a claim about unseen
ARC. NO_REAL_GAIN on both: no neural training; the post hoc failure classes below decide the next single increment.

## 7. Errors and stop rules

- An **error** is a Python exception or crash in an arm (recorded as `exception`), or a native row whose `error` field
  is anything other than `object_hard_timeout`. A budget truncation (the CPU cap) and native's own hard timeout are
  NOT errors; they are reported separately.
- If more than **5 tasks** raise errors in a stage (phase 1, phase 2, native), the stage stops and the run is reported.
- One run. `solve` resumes only after an interruption (it skips finished (task, arm) pairs). No change to the cohort,
  code, budgets or thresholds after the freeze; a change makes a new version, labelled post hoc.
- `score` is the only stage that reads expected outputs, from the sha-pinned solutions file.

## 8. After the decision (descriptive; cannot change it)

- Failure classes of the unsolved tasks with the existing taxonomy (`scripts/neural_cora_v2g3_realarc_failure_taxonomy.py`
  rules, applied to this cohort's rows by a copy labelled post hoc).
- The program form behind every correct prediction (object program, class form, g4 part or ray rule).

## 9. Caveats to carry in the report

Public training tasks, exposed to v23 and contaminated for NVARC: development evidence only. n = 34 (small; the
remaining pool is exhausted). Same-shape scope. One multi-test task. g4's leave-one-out selection can exceed the CPU
cap (CPU is reported per arm and C-cpu matches g4's measured CPU). Synthetic GO results (syn-v3) do not by themselves
predict real gains: on 20 October they did not.
