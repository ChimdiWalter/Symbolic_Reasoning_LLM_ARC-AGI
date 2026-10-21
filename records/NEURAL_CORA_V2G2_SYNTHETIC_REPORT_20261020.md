# ncv2-g2 synthetic coverage study: FINAL, GO_ENGINEERING (20 October 2026)

**The frozen decision** (protocol `records/NEURAL_CORA_V2G2_SYNTHETIC_PROTOCOL_20261020.md`, frozen at `6b6dc37`):
**GO_ENGINEERING**. It was computed by the frozen `score` stage, with every threshold unchanged.

**What it licenses:** only *proposing* the permitted real-ARC evaluation in protocol section 7, which needs separate
authorization. It is **not** evidence about real ARC, unseen tasks or the 27.64% comparison: the held-out families
were written by the generator's own author, inside its own grammar.

## 1. The run

| item | value |
|---|---|
| authorization | the author's message "I authorize the synthetic study", one run |
| start | 18:12:00Z from HEAD `3618af9`; the runner's lock (protocol and manifest committed unchanged, code hashes) verified and recorded in `run_manifest.json` |
| end | EXIT 0 at 18:37:13Z, 25 min of wall time |
| tasks | 200 HELDOUT tasks (sha `976f2a33`): 10 families × 20 seeds |
| resources | 2 workers at nice 10, CPU only. CPU: ncv2-g1 455 s, ncv2-g2 1,702 s, **0.60 CPU-hours in all** |
| integrity | 0 errors in the logs; 0 CPU truncations in either arm; 200/200 rows. Solving saw demonstrations and test inputs only; scoring regenerated answers from (family, seed) |

## 2. The frozen rule, at 3,000 candidates

| criterion | threshold | result |
|---|---|---|
| pooled pass@2 gain | ≥ 20 points | **+59.5 points** (ncv2-g1 43/200 = 21.5%; ncv2-g2 162/200 = 81.0%) |
| families improved | ≥ 6 of 10 | **8 of 10** |
| paired losses | ≤ 2% | **1/200 (0.5%)** |
| ncv2-g2 median CPU | ≤ 60 s | **3.8 s** (ncv2-g1: 2.5 s) |

**At 1,000 candidates:** ncv2-g1 39/200, ncv2-g2 147/200.

**Other pooled numbers:**
- Correct-candidate coverage equals pass@2 in every arm and budget. Whenever a correct candidate was found, it was
  one of the two attempts.
- Paired gains: 120. Paired losses: 1.
- Generator coverage (evaluator side): ncv2-g1 18/200, ncv2-g2 198/200.
- Tasks with wrong attempts at 3,000: ncv2-g1 10, ncv2-g2 14.

## 3. All ten families

| family | ncv2-g1 pass@2 at 1000 / 3000 | ncv2-g2 pass@2 at 1000 / 3000 | new | lost | generator coverage g1 / g2 | g2 first fit (median; tasks with no fit) | median CPU g1 / g2 (s) | g2 tasks with wrong attempts |
|---|---|---|---|---|---|---|---|---|
| h_rect_relational_recolour | 0 / 0 | 20 / 20 | 20 | 0 | 0 / 20 | 94; 0 | 2.4 / 20.4 | 0 |
| h_border_relational_move | 0 / 0 | 0 / 15 | 15 | 0 | 0 / 20 | 1,620; 5 | 2.7 / 19.8 | 0 |
| h_two_rule_features | 3 / 4 | 3 / 3 | 0 | **1** | 18 / 18 | 141; 14 | 2.6 / 4.6 | 3 |
| h_least_common_recolour | 2 / 2 | 4 / 4 | 2 | 0 | 0 / 20 | 72; 4 | 2.7 / 7.2 | 11 |
| h_symmetry_lr | 0 / 0 | 20 / 20 | 20 | 0 | 0 / 20 | 4; 0 | 2.0 / 21.2 | 0 |
| h_pixel_color_swap | 20 / 20 | 20 / 20 | 0 | 0 | 0 / 20 | 7; 0 | 2.6 / 4.1 | 0 |
| h_counting_unique | 0 / 0 | 20 / 20 | 20 | 0 | 0 / 20 | 2; 0 | 1.4 / 1.8 | 0 |
| h_generative_row_line | 12 / 12 | 20 / 20 | 8 | 0 | 0 / 20 | 51; 0 | 2.2 / 2.4 | 0 |
| h_panel_select_most | 2 / 5 | 20 / 20 | 15 | 0 | 0 / 20 | 6; 0 | 1.6 / 1.9 | 0 |
| h_bind_unique | 0 / 0 | 20 / 20 | 20 | 0 | 0 / 20 | 393; 0 | 2.6 / 7.4 | 0 |

ncv2-g1 solved `h_pixel_color_swap` and part of `h_generative_row_line` with execution-equivalent object programs
(for example a colour map) that its generator could express.

## 4. Where ncv2-g2 still fails (post hoc, evaluator side, after scoring; descriptive)

Source: `outputs/neural_cora_v2g2/synthetic_eval/posthoc_weak_families.json`. For up to 6 failed tasks per family, the
check finds where the generating program sits in ncv2-g2's own agenda (up to 40,000 programs), and records the
programs behind the wrong attempts.

| family | failure | diagnosis |
|---|---|---|
| **h_two_rule_features** (3/20, 1 loss) | 14 tasks have no fit within 3,000 | Both rules are in the candidate set (generator coverage 18/18), but the **correct two-rule pair is not reached within 40,000 programs**. **Composition ordering**, not language or generation. One wrong attempt is the lone rule "delete lines", which fits demonstrations that never show the second rule's trigger (underdetermined) |
| **h_border_relational_move** (15/20) | 5 tasks have no fit | The generating relational move is **not within the first 40,000** on those tasks. **Search depth** |
| **h_least_common_recolour** (4/20, 11 tasks with wrong attempts) | the generating program sits at positions **4,028–5,947**, beyond the budget | The wrong attempts come from **over-specific programs that fit by memorizing the demonstrations**: native-induced pixel tables (`color_swap`, `neighbor_pattern`) and induced `feature_map`s. ncv2-g2 puts program-class candidates **first** in its agenda, so they take the attempt slots. **Selection / underdetermination** |

## 5. What this does and does not show

**It shows:** on new families inside its grammar, ncv2-g2's recovered generator reaches far more correct programs than
ncv2-g1's at equal budgets (162 vs 43 of 200), with one loss and modest CPU.

**It does not show:**
- real-ARC coverage;
- unseen-task performance;
- anything about Qwen, learning or revision.

The families share the generator's author and grammar.

**The remaining failures match the predicted bottleneck:**
1. **Composition ordering:** pairs of rules and deep relational references are reachable but sit far down a
   hand-ordered agenda.
2. **A new selection problem:** memorizing class candidates placed first in the agenda.

## 6. Next steps (none started)

- **Licensed by this GO:** *proposing* the permitted real-ARC evaluation (protocol section 7). It needs the
  eligibility check and the author's separate authorization.
- **Indicated by the failures** (each needs its own frozen protocol):
  1. order compositions jointly: a learned or evidence-driven pair proposer, with C+H kept as the prior;
  2. rank memorizing class candidates by fold stability / description length instead of placing them first.

**Not done:** no Qwen training, no real-ARC evaluation, no Kaggle submission.

## 7. Output hashes (`outputs/neural_cora_v2g2/synthetic_eval/`, local)

| file | sha256 (first 16 hex characters) |
|---|---|
| `rows.jsonl` | `6cebdbfc21273251` |
| `score.json` | `dd7a8a76ddaf003d` |
| `run_manifest.json` | `87baf67282725a52` |
| `solve.log` | `15da77c7d9793991` |
| `score.log` | `ae553aeae822844f` |
| `posthoc_weak_families.json` | `96ce34b5090bddd3` |
