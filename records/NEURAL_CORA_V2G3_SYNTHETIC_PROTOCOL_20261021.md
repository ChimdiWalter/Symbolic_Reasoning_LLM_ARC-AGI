# ncv2-g3 synthetic mechanism study (syn-v3): protocol (21 October 2026)

**Status: FROZEN, NOT RUN.** It is frozen by `python scripts/neural_cora_v2g3_synthetic_eval.py freeze` in the
commit that adds `records/NEURAL_CORA_V2G3_SYNTHETIC_FREEZE_MANIFEST.json`. Running it needs the user's explicit
authorization of this exact study and budget.

## 1. Question

Does ncv2-g3 (joint, execution-guided construction and evidence-aware selection) reach and choose more correct
programs than ncv2-g2 as scored, on new syn-v3 families held out by semantics? Which part, construction or
selection, accounts for any difference?

**It is not evidence about real ARC tasks.** The families are designed by the author of the generator and the
solver, inside the ncv2-g2 language.

## 2. Tasks

- **HELDOUT syn-v3 families** (`cora_neural_v2g3/families_v3.py`), seeds 1–20, 3 demonstrations and 1 test input
  each:

  | group | families | what it measures |
  |---|---|---|
  | composition | 4 (2- and 3-rule programs) | multi-rule binding and composition; search reach |
  | binding | 3 (nearest / unique / largest references, a bound composite) | relational references |
  | trap | 2 | selection against overfitting: a memorizing candidate also fits and mispredicts |
  | ambiguity | 2 | candidate diversity: an alternative simple program also fits and disagrees |
  | additive | 2 (a copy composed with a recolour; a fill line) | construction when the change adds cells (descriptive; no gate) |
  | control | 2 | single-rule wrong-answer regressions |

- **Separation before augmentation:** the DEV/HELDOUT split is by generating program. Augmentation (scenes, counts,
  placement) is inside a family.
- **Certification at generation:** trap tasks are kept only if a memorizer from ncv2-g2's own generators (an
  induced feature map, the colour map, native's pixel rule) fits and mispredicts. Ambiguity tasks are kept only if
  the family's alternative program fits and disagrees. This deliberately targets a known ncv2-g2 weakness, so trap
  results measure selection under that trap, not a neutral sample.
- **Never used:** the v1 395-task evaluation, the finished 200-task ncv2-g2 synthetic study, dev60 as independent
  evidence, the finished real-ARC cohort, and any protected or sealed split. The freeze refuses if any task's grids
  match an ncv2-g2 family task (seeds 1–20).
- **Every rule necessary:** a multi-rule task is kept only if dropping any one rule breaks the fit, so a composition
  task is never secretly single-rule.
- A seed that cannot produce a certified task within the generator's tries is recorded as missing at freeze. It is
  never replaced.

## 3. Arms (paired, equal budgets)

| arm | what runs | budget |
|---|---|---|
| `g2` | `cora_neural_v2g2.search.search`, byte-identical to the GO_ENGINEERING version (checked at freeze) | 3,000 candidates; 120 CPU-s |
| `g3_find` | ncv2-g3, joint + ncv2-g2 streams; the first two distinct fits in find order | the same |
| `g3` | the same ncv2-g3 run; the selection module's two attempts | the same |
| `g3_g2stream` | ncv2-g3 with `use_joint=False`; selected attempts | the same |

`g3_find` vs `g2` isolates construction. `g3` vs `g3_find` isolates selection. `g3_g2stream` vs `g2` isolates
selection on the unchanged candidate stream. CPU only, 2 workers at nice 10.

## 4. Measures

- pass@2 (exact match within two attempts), top-1, and wrong attempts;
- correct-candidate coverage at 300, 1,000 and 3,000 candidates (search reach), and first-fit position;
- ambiguity: whether both readings (the generating and the alternative program's predictions) are in the attempts;
- paired gains and losses (`g3` vs `g2`), and selection gains and losses (`g3` vs `g3_find`);
- CPU (median, 95th percentile) and peak resident memory per task.

## 5. Decision rule (frozen, HELDOUT, decision budget 3,000)

**GO_ENGINEERING** only if all of these hold, otherwise **NO_GAIN** (each criterion is reported):

1. pooled pass@2: `g3` − `g2` ≥ 15 points;
2. composition group, correct coverage at 3,000: `g3` − `g2` ≥ 25 points;
3. trap group, top-1: `g3` − `g2` ≥ 20 points;
4. paired losses (`g2` right, `g3` wrong) ≤ 2% of tasks;
5. control group: `g3` pass@2 ≥ `g2` pass@2;
6. median `g3` CPU ≤ 60 s and peak memory ≤ 4 GB.

The thresholds are set before any HELDOUT task is solved. They require a gain in each targeted mechanism, not only
a pooled gain.

**What a GO licenses:** only proposing a real-task check of ncv2-g3 on a fresh eligible cohort, which needs its own
protocol and authorization. Never a claim about real ARC or the leaderboard.

## 6. Relation to the real-ARC failure taxonomy

The finished real-ARC check (`records/NEURAL_CORA_V2G2_REALARC_REPORT_20261020.md`, NO_REAL_GAIN) classified its 40
primary tasks as follows:
- **representation, 21:** object mismatch 13, additive change 7, mixed 1;
- **object-explainable change that no rule reached, 15:** 12 without a native certificate, 2 generator gaps, 1 beyond
  the budget;
- **fit_wrong, 2;** solved, 2.

This study tests the mechanisms aimed at the second class (the composition, binding and additive groups: joint
construction and search reach) and at selection (the trap and ambiguity groups). **It cannot test representation**,
the largest real failure class, because ncv2-g3 has no new object or relational representation yet. A GO here would
therefore address at most the 15 + 2 real tasks of those classes, and only a fresh real cohort can show that.

**Pre-freeze engineering on DEV families only** (not evidence):
- a scheduling fix gives predicted-exact combinations priority and caps inexact ones at half of the joint
  evaluations;
- attempt 2 now maximizes prediction spread among close candidates;
- unsupported table entries are penalized per entry.

At 3,000 candidates on the DEV families, g3 covered 3 of 4 composition tasks (g2: 0). DEV trap results were mixed:
2 of 4 not covered, and selection unsettled on the rest.

## 7. Stop rules

- If more than 5 tasks raise errors in `solve`, stop and report.
- No change to families, seeds, code, budgets or thresholds after the freeze. A change makes a new, labelled version.
- `score` is the only stage that regenerates answers and reads alternative programs.

## 8. Resources

Up to 300 tasks (15 families × 20 seeds), three searches each at 3,000 candidates. The DEV selftest at 600 candidates
measured median CPU of 5.2 s (g2) and 6.9 s (g3), with peak memory 77 MB. At 3,000 the DEV checks took about 7–28 s
per g3 search. That is roughly 300 × (10 + 25 + 15) s ≈ 4 CPU-hours, or 2–3 hours of wall time with 2 workers at
nice 10 under the usual load. Step B is not touched.
