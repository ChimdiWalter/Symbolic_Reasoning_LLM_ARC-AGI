# ncv2-g2 synthetic coverage study: protocol (20 October 2026)

**Status: FROZEN** in the commit that adds this file and `records/NEURAL_CORA_V2G2_SYNTHETIC_FREEZE_MANIFEST.json`.
**NOT RUN. Running it needs the user's authorization.**

Runner: `scripts/neural_cora_v2g2_synthetic_eval.py`. Its `solve` stage refuses to run unless:
- this protocol and the manifest are committed unchanged;
- the code hashes match;
- `--authorized` is given.

## 1. Question

After the G2 NO-GO, does ncv2-g2 (the capability-recovery version: native program classes, plus a candidate
generator completed over the constructs ncv2-g1 already compiles) reach more correct programs than ncv2-g1? The test
uses **new, held-out, execution-verified synthetic semantic families**, at equal candidate budgets.

A positive answer licenses **only** proposing a permitted real-ARC evaluation (section 7). It licenses no score claim.

## 2. Data

**Families:** the ten HELDOUT families in `cora_neural_v2g2/families.py` (prefix `h_`), seeds 1–20, giving up to 200
tasks. Fewer tasks result if a family's generator cannot produce a task, and that count is reported.

| family | what it is |
|---|---|
| `h_rect_relational_recolour` | feature-keyed relational recolour, on rectangles |
| `h_border_relational_move` | move toward the nearest border-touching object |
| `h_two_rule_features` | two rules keyed by features |
| `h_least_common_recolour` | recolour to the least common colour |
| `h_symmetry_lr` | left–right symmetry completion |
| `h_pixel_color_swap` | a colour-swap pixel rule |
| `h_counting_unique` | counting: the unique colour |
| `h_generative_row_line` | a row-line generator |
| `h_panel_select_most` | panel selection: most non-background |
| `h_bind_unique` | binding with a `unique` reference |

**How they relate to development:**
- They differ from the DEV families used in development: other features, modes, kinds and compositions.
- None was run, tuned on or inspected during development. This protocol is written before any held-out task is
  looked at.
- The freeze manifest pins the task set's sha256.

**A construction check before freezing:**
- At the first freeze attempt, `h_bind_unique` generated 0 tasks. Its scenes always held two lines, so
  `(unique (test is_line == #t))` was undefined.
- Its scene generator was changed to exactly one line before this freeze. The program is unchanged.
- No solver had run on any held-out task, and no held-out task content was viewed. Only per-family task counts were
  checked.

**Exposure and limits:**
- No real ARC data, no protected split, no NVARC data.
- **Known limitation:** the families were written by the same author as the generator, inside the same grammar. A
  gain is evidence of generator completeness within the designed grammar, **not** of real-ARC coverage.

## 3. Arms

| arm | search | budget |
|---|---|---|
| g1 | `cora_neural_v2.search.search`, unchanged | 3000 candidates; CPU cap 120 s per task |
| g2 | `cora_neural_v2g2.search.search` | the same |

Budget 1000 is read by exact truncation of the same runs (`pred_at`). CPU only; 2 workers at nice 10.

## 4. Measures

Pooled and per family:

| measure | definition |
|---|---|
| representable coverage | does the family's generating program compile in the arm's grammar? |
| generator coverage | evaluator side: are the generating program's rules (or an execution-equivalent class form that also predicts the test output) in the arm's candidate set? |
| first-fit position | candidate index of g2's first demonstration-fitting program |
| correct-candidate coverage | at 1000 and 3000 |
| exact pass@2 | at 1000 and 3000 |
| harmful predictions | tasks where an arm's two attempts are wrong; paired losses (g1 correct, g2 not) |
| CPU | per task: median and total |

## 5. Decision rule (frozen)

**GO_ENGINEERING** if all of the following hold at budget 3000:
1. pooled g2 pass@2 − g1 pass@2 is at least **20 percentage points** of the tasks;
2. g2 is better than g1 on at least **6 of the 10** families;
3. paired losses are at most **2%** of the tasks;
4. g2's median CPU is at most **60 s** per task.

Anything else is **NO_GAIN**: generator work continues, and there is no real-ARC proposal.

Exact paired sign-test p-values are reported descriptively.

## 6. Stop rules

- One run.
- If more than 5% of tasks raise errors, stop and report.
- No changes to families, seeds, code or thresholds after the freeze. A change makes a new version, labelled post
  hoc.

## 7. If GO_ENGINEERING (proposal only, needs separate authorization)

**A permitted real-ARC evaluation:**
- **Cohort:** the next 100 in-scope candidates of the ARC-AGI-2 training file, in the published hash order. They are
  checked for eligibility by the user-authorized, metadata-only checker (`tools/stepb_eligibility/`).
- **What is never used:**
  - dev60;
  - Phase 2a's 40;
  - the closed v1 395-task pool;
  - any protected or sealed split.
- **Measures:** representable / generator / reached / correct-candidate coverage, pass@2 and harmful predictions,
  ncv2-g2 vs ncv2-g1 vs native CORA.
- **Caveat:** these are exposed public training tasks. That makes it development evidence, never unseen performance.
