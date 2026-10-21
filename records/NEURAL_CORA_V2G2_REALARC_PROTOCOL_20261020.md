# ncv2-g2 real-ARC engineering check: protocol (20 October 2026)

**Status: FROZEN** in the commit that adds this file and `records/NEURAL_CORA_V2G2_REALARC_FREEZE_MANIFEST.json`.
**NOT RUN. Running it needs the user's authorization.**

Runner: `scripts/neural_cora_v2g2_realarc_eval.py`. Its `solve` and `native` stages refuse to run unless:
- this protocol and the manifest are committed unchanged;
- the code, cohort inputs and native CORA hashes match;
- `--authorized` is given.

**Licensed by:** the synthetic study's GO_ENGINEERING (`records/NEURAL_CORA_V2G2_SYNTHETIC_REPORT_20261020.md`). Its
protocol, section 7, proposed this check. The user authorized the eligibility check and this protocol ("go ahead",
20 October).

## 1. Question

Does ncv2-g2, the capability-recovery version, reach more correct programs **on real ARC tasks** than ncv2-g1, and
how does it compare with native CORA? On exposed dev60, G2 found ncv2-g1 at 1/60. The synthetic gain (162 vs 43 of
200) is designer-made; this check measures whether it transfers to real tasks.

**It is development evidence, not unseen performance.** The tasks are public ARC-AGI-2 training tasks. The sealed v23
baseline saw them, and NVARC's checkpoint was trained on this file. No Qwen component is used here.

## 2. Cohort (fixed before any run)

| stratum | tasks | how chosen |
|---|---|---|
| **PRIMARY** | 40 | Candidates: `scripts/neural_cora_v2g2_realarc_cohort.py` takes the next 100 in-scope tasks in the pilot's published order. It excludes dev60, the frozen 120, the 240 stand-ins, every ID in any CORA-FHR / v2 / Neural-CORA output or record, and the 100 checked on 19 October. The candidates (sha `af6e402c…`) went through the frozen, metadata-only Step B eligibility checker in one authorized run: PASS, 40 of 100 eligible (sha `56239eef…`). The decision is taken on this stratum |
| **LEFTOVER** | 4 | The eligible tasks of the 19 October check that Phase 2a did not use. They are additions-only (growth) tasks, reported **descriptively**, outside the decision |

**Scope** (the pilot's published rule): at least 3 demonstrations, grid shape kept, every demonstration changes a cell.
Size-changing tasks are therefore absent, and ncv2-g2's counting and panel classes cannot help here. That is a known
limitation.

**Never used:**
- dev60;
- Phase 2a's 40;
- the v1 395 pool;
- the synthetic families;
- any protected or sealed split;
- hidden Kaggle data.

## 3. Arms

| arm | what runs | budget |
|---|---|---|
| ncv2-g1 | `cora_neural_v2.search.search` | 3000 candidates; CPU cap 120 s per task |
| ncv2-g2 | `cora_neural_v2g2.search.search`, **byte-identical to the version that passed GO_ENGINEERING** (the freeze checks this against the synthetic manifest) | 3000 candidates; CPU cap 120 s per task |
| native CORA v23 (reference) | the unchanged funnel harness (`cora_funnel.run.job`, `native` mode: the sealed v23 flags, the CPU clock, the 90 s cooperative budget, 8 dihedral frames) | native defaults |

**Resources:** CPU only, 2 workers at nice 10.
- ncv2 arms: about 0.3 CPU-hours;
- native: at most about 5.5 CPU-hours (dev60 averaged 294 CPU-s per task);
- in all, about 3 hours of wall time.

## 4. Measures

The ncv2 arms score the **first test output**, as G2 did.
- **fits:** a demonstration-consistent program within the budget;
- **correct-candidate coverage:** some kept prediction is correct;
- **pass@2:** the first two distinct predictions;
- **wrong attempts;**
- **first-fit position;**
- the program behind each correct prediction (g2);
- CPU and truncations.

Native is scored with its own `cora_funnel.evaluate.task_record` (all test outputs; its categories) and on the first
test output: fits, correct-candidate coverage and certified-correct, for pairing.

Paired: ncv2-g2 vs ncv2-g1 gains and losses on pass@2; ncv2-g2 vs native on first-test correctness.

## 5. Decision rule (frozen, PRIMARY stratum)

**GO_REAL_COVERAGE** if all three hold:
1. ncv2-g2 pass@2 − ncv2-g1 pass@2 ≥ **3** tasks;
2. ncv2-g2 correct-candidate coverage − ncv2-g1 ≥ **3** tasks;
3. paired pass@2 losses vs ncv2-g1 ≤ **1**.

Anything else is **NO_REAL_GAIN**. Native is a reference with no gate; its paired gains and losses are reported.

**What follows:**
- **GO_REAL_COVERAGE:** design and freeze, but do not run, the next experiment: a joint composition and binding
  proposer built on C+H, with Qwen object states as one arm, targeted at the observed real failures. The
  composition and selection fixes would be measured under it. Separate authorization is needed.
- **NO_REAL_GAIN:** no neural training. A failure audit of the real tasks (which constructs native uses that ncv2-g2
  lacks), then one targeted increment.

## 6. Stop rules

- One run.
- If more than 5 tasks raise errors in a stage, stop and report.
- No change to the cohort, code, budgets or thresholds after the freeze. A change makes a new version, labelled post
  hoc.
- `score` is the only stage that reads test outputs, from the sha-pinned solutions file.
