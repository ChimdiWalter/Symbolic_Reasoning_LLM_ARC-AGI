# ncv2-g3: architecture proposal, with the failure taxonomy (20 October 2026)

**Status:** a proposal only. ncv2-g2 stays exactly as scored (the synthetic GO_ENGINEERING; the real-ARC check is
frozen at `8bb377d`). Nothing here is built.

**Sources:** the coverage matrix (`records/NEURAL_CORA_V2G2_COVERAGE_MATRIX.md`), the synthetic report and its saved
post-hoc diagnostics (`records/NEURAL_CORA_V2G2_SYNTHETIC_REPORT_20261020.md`;
`outputs/neural_cora_v2g2/synthetic_eval/posthoc_weak_families.json`), and the DEV families. No held-out family is
rerun, and no real task is opened.

## 1. Failure taxonomy (what the evidence shows)

| code | failure | evidence | example |
|---|---|---|---|
| **L** | language: native construct not compiled | 14 native constructs | grow, matched_template, the framed and overlay classes |
| **G** | generator: compiled, never proposed | 70 constructs | relations beyond adjacency/containment; 23 features as selectors; scalars; `and` / `in_set`; staged `seq` |
| **R** | reach: proposed, but beyond budget | h_two_rule_features: correct pair not within 40,000; h_border_relational_move: 5 tasks beyond 40,000; h_least_common: positions 4,028–5,947 | pairs of individually ranked rules; deep relational references |
| **S** | selection: a demonstration-fitting wrong program takes the attempts | h_least_common: 11 tasks with wrong attempts, from memorizing pixel tables and induced feature maps, which ncv2-g2 puts **first**; h_two_rule: a lone rule fits underdetermined demonstrations | literal-table programs ahead of relational ones |
| **P** | an inducer precondition | native's generative inducer needs fusion or emission (`_fusion_signature`), and symmetry is capped at 60 cells | same-colour rays are executable but never induced (patched in ncv2-g2 by enumeration) |

The real-ARC check, once authorized, will add a real-task column (L / G / R / S per task, from native certificates).
The design below waits for it.

## 2. ncv2-g3 components (each a separate, ablatable change)

1. **Joint symbolic rule-pair proposals (targets R).** Partition each demonstration's changed cells, through the
   matched-object evidence (`evidence2`), into *change groups*, e.g. "lines deleted" and "holed objects recoloured
   4".
   - For each group, propose rules whose selector separates the group's objects from the unchanged ones and whose
     action explains the group's change.
   - Compose rules with disjoint groups into pairs, ordered by the groups' first-match conflicts.
   - Pairs are *constructed* from evidence, not enumerated in score-sum order.
2. **Evidence-driven references and parameters (targets R and G).**
   - For moved or recoloured objects, test which typed reference (`nearest` / `unique` / `largest` × feature ×
     polarity × relation) explains every observed displacement or colour. Propose only those.
   - Extend the guard templates to the uncovered relations and features, but only through this test, so that
     branching stays bounded.
3. **Selection by description length and genuine leave-one-out (targets S).**
   - Rank demonstration-fitting candidates by description length (program size + bound literals; table entries
     count as literals) and by **fold-local reconstruction**: rerun the search without one demonstration, then
     check the held-out one.
   - Memorizing tables lose to relational programs unless they are fold-stable.
   - The two attempts are the two best distinct predictions under this score.
4. **Class-candidate interleaving (targets S).** Native-induced class candidates enter the agenda by that same score
   instead of all first.
5. **Staged `seq` proposals (targets G).** Stage 1 explains one change group, and stage 2 runs on stage 1's output.
   Bounded by group count.

## 3. Ablations (each gets its own frozen protocol before any score)

| arm | what it adds |
|---|---|
| a | ncv2-g2 as scored (C+H ordering) |
| b | a + joint symbolic pairs (1) |
| c | a + references and parameters (2) |
| d | a + description-length selection (3, without leave-one-out) |
| e | d + genuine leave-one-out reconstruction |
| f | a + class interleaving (4) |
| g | the best of b–f + task-adaptive Qwen evidence (`docs/NEURAL_CORA_JOINT_RULE_PROPOSER_SPEC.md`) |

**Data:** **new** synthetic held-out families, never used before (the ten used are now spent), plus a fresh eligible
real cohort. All paired against arm a, with gains and losses counted.

## 4. Order of work

1. The real-ARC check (needs authorization).
2. Its per-task taxonomy decides which of 1–5 comes first.
3. Then the ablation protocol.

No Qwen training before arm g's protocol is frozen and authorized.
