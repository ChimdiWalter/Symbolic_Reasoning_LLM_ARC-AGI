# Result U6: the submitted CORA entry on real biological Boolean networks (BBM), 3 Nov 2026

This is a fresh evaluation under a protocol pre-registered before any download. Four amendments were frozen before any
task or outcome existed, and every one passed independent review. It goes to independent audit before any use in the
paper.

**Names used here:**
- **O+ v2** is the submitted CORA-only entry. It runs the CAST v1 package, then the R29 package; R29 came from the
  independent lane.
- **System b** is the CORA component of entry H: `cast_selective_v2` under its strictest acceptance rule, B3.
- **System c** is `cast_v1` alone.
- **BBM** is the Biodivine Boolean Models repository.
- **Whole-network task:** predict every gene's next state.
- **Single-gene task:** predict one gene's next value.

## Provenance

| item | sha256 | commit | when (UTC) |
|---|---|---|---|
| protocol `PROTOCOL.md` | `0cfcf015…` | 27239ef3 | 2 Nov 16:58, before any download |
| Amendment 1: lane-split rule with the independent lane | `2a7f9874…` | 9198b6ac | 17:04, before the clone |
| Amendment 2: lineage exclusion, same-size donors, wording | `66443fa7…` | d54d2584 | 18:17, before any task |
| Amendment 3: seven-hash GO line, one-use claim, code | `d28eca13…` | 79446fb6 | 21:31 |
| Amendment 4: explicit portability ledger | `05c3fd60…` | 77c37953 | 22:26 |
| code freeze `CODE_FREEZE.json` (28 files) | `55ba6466…` | d680e184 | 23:26 |
| manifest freeze `MANIFEST_FREEZE.json` | `5d3a5f20…` | d680e184 | 23:26 |
| prepared manifest `PREPARED_MANIFEST.json` | `442f1eab…` | 60760512 | 3 Nov 02:02, built once |
| GO line (written by the coordinator) | `202245e3…` | | 02:23 |
| one-use claim `runs/GO_U6.claimed` (launch `91baf317ec16797c`) | `e60e4290…` | 212b2e92 (receipt) | 02:24:08 |
| results `results/RESULTS.json`, `SUMMARY.md` (scored once, by the chain) | `18730c08…`, `386e70cc…` | 46ddfa48 | 03:20:25 |

**Independent reviews,** in order:
1. protocol and Amendment 1: HOLD (`55f1e6f7…`);
2. Amendment 2: cohort PASS, execution HOLD (`4d10dea4…`);
3. code freeze: HOLD on the portability count (`cc38fcc4…`);
4. refreeze: HOLD on a missing worker status histogram (`f0ba3553…`);
5. refreeze: PASS (`5afac45d…`);
6. preparation audit: PASS (note 0270).

Every HOLD was answered by a frozen amendment or a code fix before any task or outcome existed.

**Data.**
- BBM was cloned at commit `314b2fed`. The sha256 of every one of its 3,866 files is in `DATA_MANIFEST.json`.
- The models are used for evaluation only, and no model content is committed.
- BBM citation: Pastva, Šafránek and others, "Repository of logically consistent real-world Boolean network models",
  bioRxiv 2023.06.12.544361.
- The source publication of every model used is in the table at the end.

**Compute and run state.**
- 2,475 child CPU-seconds (0.69 CPU-h), excluding the builders and the scorer. The soft cap was 24 CPU-h.
- No GPU was used.
- All 24 arms ended cleanly, and both chains exited 0.
- No arm was rerun, no claim was made twice, and the scorer ran once.

## What ran

**Models.** From BBM's 285 models:
1. 109 have 2 to 30 variables and at least one regulated variable.
2. The family split (Amendment 1) gave 55 of them to this study.
3. The lineage audit (Amendment 2) removed 11 that share a source publication with the other lane.
4. That left **44 models in five topical families**: development and differentiation 25, signalling 8, immunity and
   infection 6, microorganisms 4, plants 1. Ten are Booleanized versions of multi-valued models, as BBM marks them.

**Tasks.** Built once, with no attrition: no task unbuilt and no pair dropped.

| task type | tasks | query outputs | paired cohort P (30 models) | sensitivity cohort S (36 models) | real only (8 models) |
|---|---|---|---|---|---|
| whole network, 1 x N state to next state (3 or 10 demonstrations) | 440 | 1,760 | 300 tasks, 1,200 outputs | 360 tasks | 80 tasks |
| single gene, 1 x N state to that gene's next value (10 demonstrations) | 333 | 1,332 | 225 tasks, 900 outputs | 273 tasks | 60 tasks |

- **Cohort P** pairs each model with a donor of the same size from another family and another publication. The real
  and shuffled demonstrations are compared on the same tasks.
- **Cohort S** adds six models whose only same-size donors share their family.
- **Shuffled tasks** keep the task's queries and use the donor's demonstrations.

**Arms.**
- the three CORA systems on real and shuffled demonstrations, called exactly as in our earlier benchmark study U2;
- probes for every answered task;
- a matched blind search in CAST's own grammar, at system b's CPU, with and without leave-one-out (MS and MSL);
- native baselines tuned on nothing: COPY, MAJORITY, and two references that know each gene's documented regulators
  (ORACLE-FIT, ORACLE-LOOKUP);
- **arm W**, the one domain adaptation: a typed Boolean-rule language of up to three literals, with the same
  verify-or-abstain steps, run under four priors:
  - correct wiring (CW): each gene's documented regulators;
  - shuffled wiring of the same size (SW);
  - no wiring with the standard bar (NW0);
  - no wiring with the strict bar (NW1).

## Results

### Portability (the protocol's PORTABLE label, from Amendment 4's ledger)

All three systems are **PORTABLE**:
- O+ v2: 1,519 tasks started and 1,519 returned a result;
- systems b and c: 1,406 started and 1,406 returned a result each.

No task was incomplete and no task ended in an error, and every verification receipt (launch, and before and after each
arm) was present and ok. The systems ran byte-identical throughout: all 128 system bindings verified at launch, and 64
before and after every arm.

### Primary (pre-declared): O+ v2, whole-network tasks, real against shuffled precision, cohort P

**NOT_TESTABLE.**
- O+ v2 answered **0 of 1,200** paired whole-network outputs (0 of 1,760 overall).
- The pre-declared criterion requires at least 10 answered real outputs, so no claim about evidence dependence follows
  for whole-network tasks.
- This is the result the protocol predicted before any data (its §2). No primitive in CAST v1's or R29's grammar
  expresses a Boolean function of cells at fixed positions.

### Main lane, every system

| system | task | real: answered / outputs | correct | precision [Wilson 95%] | shuffled (cohort P): answered | correct |
|---|---|---|---|---|---|---|
| O+ v2 | whole network | 0 / 1,760 | 0 | n/a | 0 | 0 |
| O+ v2 | single gene | **167 / 1,332** (12.5%) | **150** | **0.898** [0.843, 0.935] | 82 | 49 |
| system b | both | 0 / 3,092 | 0 | n/a | 0 | 0 |
| system c | both | 0 / 3,092 | 0 | n/a | 0 | 0 |
| MS and MSL (matched search) | both | 0 / 3,092 | 0 | n/a | 0 | 0 |

**O+ v2 on single-gene tasks.**
- Every answer came from **R29**, its second package. CAST v1 answered nothing.
- 150 correct answers are 11.3% of all 1,332 single-gene outputs.
- The cluster bootstrap by model gives a precision interval of [0.819, 0.958].
- In cohort P: real 109 of 124 (0.879) against shuffled 49 of 82 (0.598).

**Secondary contrasts** (Holm over four):
- **S1, real minus shuffled precision on single-gene tasks: +0.281** [0.096, 0.433], Holm p = 0.011, significant.
  Clustered by publication lineage, [0.135, 0.410]. In the sensitivity cohort S, +0.313 [0.142, 0.456].
- **S2, precision minus MAJORITY's accuracy on the same answered queries: 0.000** [0.000, 0.000], p = 1. On every
  answered query, O+ v2 was right exactly when the majority-of-demonstrations rule was.
- **S3, O+ v2's accuracy minus the matched search's, paired per output, both task types: +0.049** [0.033, 0.066], Holm
  p = 0.001. The matched search found no program that fits, so it gave no answers.
- **S4, precision against the matched search with leave-one-out:** not estimable, because that search gave no answers.

**Labels.** VERIFIED_TRANSFER, the rule of our earlier study, is **not established** on single-gene tasks. Shuffled
answers did not fall to half: 82 against 124. USEFUL is **not shown**, because of S2.

**How O+ v2 answers** (post-hoc, not pre-registered; read from system outputs and demonstrations, never from solutions).
- 40 of its 42 answered single-gene tasks had all ten demonstrations giving the same value, and in each of the 40 its
  answer was that value.
- Of the 43 tasks with uniform demonstrations, it answered 40. Under shuffled demonstrations, 24 of its 25 answered
  tasks had uniform donor demonstrations.
- So its single-gene answers repeat a constant. They depend on the task's own evidence (S1), but add nothing beyond the
  majority rule (S2).

**Probe-consistency.**
- **0 of the 42** answered single-gene tasks were probe-consistent. 36 were probed on every regulator assignment, each in
  one sampled background, and 6 on a sample. All 42 gave a wrong probe answer.
- This is expected: every single-gene task's gene is non-constant by construction, so no constant can be its rule.
- No whole-network task was answered, so none was probed.

**Diagnostics** (pre-declared):
- **Generation or verification.** System b's evidence shows **no complete fitting candidate** on any query: 0 of 1,760
  and 0 of 1,332. Its modules never produced a program consistent with the demonstrations, so verification never had
  anything to accept or reject.
- **Grammar reach.** The matched blind search in CAST's grammar found **no fitting program** within budget on any task.
- **Evidence.** ORACLE-LOOKUP's coverage is 8.75% of whole-network queries and 75.8% of single-gene queries: the share
  whose answer the demonstrations determine, given the true wiring.

### Native baselines (real, all 44 models)

| baseline | whole network: accuracy | single gene: accuracy |
|---|---|---|
| COPY (the query state) | 0.000 (non-fixed states only) | 0.519 |
| MAJORITY (per cell, over the demonstrations) | 0.016 | 0.664 |
| ORACLE-FIT (oracle-structure reference: documented regulators, nearest observed row) | 0.333 | 0.947 |
| ORACLE-LOOKUP (answers only when the regulators' row was observed) | coverage 0.0875, precision 1 | coverage 0.758, precision 1 |

ORACLE-FIT's learned function exactly recovers the published rule in **207 of 333** single-gene tasks (62.2%) and in
16 of 440 whole-network tasks (3.6%).

### Arm W: prior wiring with an asymmetric bar (the domain adaptation), single-gene tasks

| prior | exactly recovered | wrong accepts (share of accepts) | queries answered | precision [Wilson 95%] |
|---|---|---|---|---|
| CW, correct wiring | **148 / 333 (44.4%)** [39.2, 49.8] | 54 (26.7%) | 808 / 1,332 (60.7%) | 0.976 [0.964, 0.985] |
| SW, shuffled wiring | 87 (26.1%) | 59 (40.4%) | 575 (43.2%) | 0.958 [0.939, 0.972] |
| NW0, no wiring, standard bar | 85 (25.5%) | 58 (40.6%) | 563 (42.3%) | 0.964 [0.946, 0.977] |
| NW1, no wiring, strict bar | 85 (25.5%) | 58 (40.6%) | 563 (42.3%) | 0.964 [0.946, 0.977] |

**The pre-declared claim gate passes: WIRING_PRIOR_RAISES_EXACT_RECOVERY.** The protocol names this pass label
WIRING_PRIOR_RAISES_DISCOVERY, with the same thresholds (deviation 5). At matched work (the same 263,382 rules for 30
variables, in every condition), each contrast has a cluster-bootstrap lower bound above 0:
- **CW minus SW: +0.183** [0.139, 0.230];
- **CW minus NW0: +0.189** [0.145, 0.235];
- **CW minus NW1: +0.189** [0.145, 0.235].

**What these numbers mean.**
- **Power.** Amendment 2 expected to detect about 3.5 to 7 points. The observed gain is 18 to 19 points.
- **Wrong accepts.** Correct wiring raised exact recovery without raising them: 54 against 58 to 59.
- **Expressibility.** 236 of the 333 genes are expressible in the three-literal language, and correct wiring recovered
  148 of them.
- **Whole-network tasks** (a description): correct wiring recovered every gene in 1 of 440 tasks, and answered 12 of
  1,760 whole-state queries (8 correct). The other priors recovered none.
- **The two bars** (post-hoc).
  - On every single-gene (T2) task, 333 of 333, they gave the same acceptance and the same answers. Their chosen rule
    sets differ on 37.
  - On whole-network (T1) tasks, they differ in one gene-level acceptance and one gene-level answer (one gene of task
    u6-t1-0298, among 8,100 gene problems), and 168 of 440 tasks have different chosen sets.
  - So on single-gene tasks with ten demonstrations, leave-one-out already removed what the full-support bar would
    have removed.
- **Exact recovery** means the accepted rule equals the published update function on every input both can depend on. It
  was checked by truth tables, and no case was too large to check.

**By family**, exactly recovered with correct wiring, then shuffled wiring:
- development 87 and 57 of 182;
- signalling 30 and 15 of 64;
- immunity 16 and 7 of 48;
- microorganisms 11 and 5 of 31;
- plants 4 and 3 of 8.

## Claim for the paper

The scope below follows the independent postscore audit (`INDEPENDENT_U6_BBM_POSTSCORE_AUDIT_20261103.md`, sha256
`a0ac71af…`; notes 0276 and 0277).

> **Execution is portable.** We used 44 published Boolean-network models from BBM, in five families, disjoint from a
> parallel independent study and with shared-publication models excluded. On them the submitted CORA-only entry and
> two other CORA systems ran byte-identical on 3,092 real and 2,532 shuffled next-state queries. Every started task
> returned a result, none ended in error, and every verification receipt was in order.
>
> **No whole-network transfer.** On whole-network next-state tasks, none of the three systems answered any of 1,760
> queries, so the pre-declared primary comparison is not testable. We had predicted this before seeing data: their
> grammars have no primitive for a Boolean function of cells at fixed positions. Neither the systems nor a matched
> blind search in CAST's grammar generated any program consistent with the demonstrations.
>
> **A bounded evidence-sensitivity signal on single-gene tasks, from R29 alone.**
> - The entry answered 12.5% of single-gene queries, with 90% precision among its answers (11.3% of all outputs
>   correct). Every answer came from its second package, R29; CAST v1 supplied none.
> - Precision was higher with the task's own demonstrations than with another model's (+0.28, 95% interval +0.10 to
>   +0.43, significant after Holm correction). So these answers depend on the task's evidence.
> - It is not verified transfer, because shuffled answers did not fall to half.
> - It is not usefulness beyond the majority rule. In 40 of its 42 answered tasks the entry repeated the value that
>   all ten demonstrations shared, and on every answered query it was right exactly when the majority-of-demonstrations
>   rule was.
> - None of its answered tasks was probe-consistent, so the entry recovered no rule.
>
> **A supplied-wiring demonstration (arm W, a domain adaptation).** We supplied both a Boolean-rule language of up to
> three literals and each gene's published regulator set. With them, the same verify-or-abstain procedure exactly
> recovered the published update rule in 44% of single-gene tasks, against 26% with shuffled or no wiring (+18 to +19
> points; every 95% lower bound above +13 points), with no more wrong accepts. Neither the language nor the regulator
> sets were learned or discovered.
>
> **Not claimed:** whole-network transfer; usefulness beyond the majority rule; autonomous rule discovery; a learned
> cross-domain grammar. Recovering the rules of published computational models is not wet-lab biological discovery.

**Wording rules for the paper.**
- Say "probe-consistent" only for the CORA systems, and "exact recovery" only for arm W and ORACLE-FIT.
- Call the single-gene result "evidence sensitivity, attributable to R29". Never call it transfer or usefulness: it
  equals the majority rule.
- Call arm W "a supplied-wiring demonstration", with both the Boolean language and the regulator sets supplied. Never
  call it discovery or a learned grammar.

## Negatives, as diagnosed open questions

1. **No answers on whole-network tasks.** Measured cause: generation, not verification. There was no complete fitting
   candidate in 1,760 queries for system b, no answer from CAST v1 in either entry, and no fit in the matched search.
   - Next test: give the entry a package that can state positional Boolean rules, then rerun this frozen task set and
     its controls.
   - Arm W suggests what such a package could reach: 44% exact recovery per gene with correct wiring.
2. **O+ v2's single-gene answers are a constant rule.** Measured cause: R29 accepts the value that all demonstrations
   share (40 of 42 tasks). That passes its leave-one-out check, because every fold sees the same constant.
   - Next test: report constant-output acceptances separately, or require a non-constant rule when every demonstration
     agrees, and score on tasks with varied demonstrations.
3. **Shuffled answers do not collapse on single-gene tasks** (82 against 124). Measured cause: a donor's uniform
   demonstrations yield a constant that applies to any gene, and is right at about the chance rate.
   - Next test: report shuffled precision against the per-query base rate (deviation 1 below).
4. **Correct wiring still accepts wrong rules,** in 54 of 202 accepts. Measured cause: ten random demonstrations often
   leave several three-literal rules consistent. The exact-recovery check shows that the accepted set then contains a
   rule that differs from the published one on some unobserved input.
   - Next test: more demonstrations, or active choice of demonstrations, under the same procedure.
5. **The strict bar adds nothing on single-gene tasks at ten demonstrations** (NW0 equals NW1 in acceptance and
   answers on 333 of 333; on whole-network tasks one gene-level acceptance and one answer differ).
   - Next test: fewer demonstrations, or larger regulator sets, where full support and leave-one-out diverge.

## Deviations and limits

1. **No chance level for single-gene shuffled precision.** Protocol §8 says it is reported next to that precision, but
   the frozen scorer does not compute it.
   - The nearest reported reference is MAJORITY, 0.664 on all real single-gene outputs.
   - Computing the exact base rate needs the sealed solutions, which only the frozen scorer reads. It is left to the
     audit, or to a reviewed supplementary script.
2. **Empty probe arms.** Systems b and c answered nothing, so their probe arms ran on empty probe files. This is
   harmless, and is counted as such by the ledger.
3. **Post-hoc analyses** (the constant-answer mechanism, and the per-task comparison of the two bars) were not
   pre-registered. They read system outputs, demonstrations and metadata, never solutions.
4. **Earlier documented steps.**
   - Before the GO, one smoke test ran the three systems on two hand-made tasks (Amendment 3 §5).
   - The Amendment 1 inventory script had one fingerprint bug, fixed before the split.
   - Statistics computed from model files before the GO are listed in `EXPOSURE_DISCLOSURE.md`.
5. **Label name of the arm W gate.** Protocol §12 names the pass label WIRING_PRIOR_RAISES_DISCOVERY. Amendment 2 §3,
   frozen before any task existed, renamed it WIRING_PRIOR_RAISES_EXACT_RECOVERY, to keep "discovery" out of
   descriptions of black-box agreement. The frozen scorer reports the new name. The thresholds are identical: each of
   the three contrasts must have a 95% lower bound above 0.
6. **Scope.**
   - 44 models in five families, all with at most 30 variables, under synchronous updating, from random initial states.
   - Probe agreement covers non-fixed states, or one sampled background per regulator assignment. It is not
     equivalence over all states.
   - The whole-network results rest on zero answers, so they say nothing about precision when answering.

## Source publications of the 44 models used

| BBM id | model | variables | family | cohort | source DOI |
|---|---|---|---|---|---|
| bbm-007 | CORTICAL-AREA-DEVELOPMENT | 5 | development and differentiation | real only | 10.1371/journal.pcbi.1000936 |
| bbm-010 | CARDIAC-DEVELOPMENT | 15 | development and differentiation | sensitivity | 10.1371/journal.pone.0046798 |
| bbm-015 | NEUROTRANSMITTER-SIGNALING-PATHWAY | 16 | signalling | paired | 10.1016/j.jtbi.2006.08.014 |
| bbm-021 | BODY-SEGMENTATION-IN-DROSOPHILA-2013 | 17 | development and differentiation | sensitivity | 10.1371/journal.pone.0055946 |
| bbm-022 | B-CELL-DIFFERENTIATION | 22 | immunity and infection | real only | 10.1371/journal.pcbi.1004696 |
| bbm-027 | WG-PATHWAY-OF-DROSOPHILA | 26 | development and differentiation | sensitivity | 10.1039/c3mb70187e |
| bbm-028 | VEGF-PATHWAY-OF-DROSOPHILA | 18 | development and differentiation | paired | 10.1039/c3mb70187e |
| bbm-029 | TOLL-PATHWAY-OF-DROSOPHILA | 11 | development and differentiation | real only | 10.1039/c3mb70187e |
| bbm-030 | SPZ-NETWORK-OF-DROSOPHILA | 24 | development and differentiation | real only | 10.1039/c3mb70187e |
| bbm-040 | T-CELL-DIFFERENTIATION | 23 | immunity and infection | paired | 10.1186/1742-4682-3-13 |
| bbm-045 | HH-PATHWAY-OF-DROSOPHILA | 24 | development and differentiation | real only | 10.1039/c3mb70187e |
| bbm-047 | FGF-PATHWAY-OF-DROSOPHILA | 23 | development and differentiation | paired | 10.1039/c3mb70187e |
| bbm-055 | HUMAN-GONADAL-SEX-DETERMINATION | 19 | signalling | paired | 10.1186/s12976-015-0023-0 |
| bbm-062 | CD4-T-CELL-DIFFERENTIATION-AND-PLASTICITY | 18 | immunity and infection | paired | 10.1371/journal.pcbi.1004324 |
| bbm-068 | AURORA-KINASE-A-IN-NEUROBLASTOMA | 23 | signalling | paired | 10.1016/j.canlet.2015.11.025 |
| bbm-094 | MACROPHAGE-POLARIZATION-STATES | 30 | immunity and infection | paired | 10.3389/fphys.2018.01659 |
| bbm-095 | FISSION-YEAST-2008 | 10 | microorganisms | paired | 10.1371/journal.pone.0001672 |
| bbm-097 | DROSOPHILA-WINGS-AP | 10 | development and differentiation | paired | 10.1534/genetics.106.061218 |
| bbm-099 | YEAST-HYPHAL-TRANSITION | 19 | microorganisms | paired | 10.1371/journal.pcbi.1008690 |
| bbm-108 | GEROCONVERSION | 25 | signalling | real only | 10.1111/acel.12504 |
| bbm-133 | ROOT-STEM-CELL-2010 | 10 | plants | paired | 10.1186/1752-0509-4-134 |
| bbm-135 | SIGNAL-TRANSDUCTION | 30 | signalling | paired | 10.1088/1478-3975/9/4/045003 |
| bbm-136 | EGF-TNF-ALPHA-SIGNALLING-PATHWAY | 28 | signalling | real only | 10.1186/1752-0509-7-135 |
| bbm-139 | ACUTE-RESPONSES-DURING-HYPERINSULINEMIA | 19 | signalling | paired | 10.1186/s12918-017-0436-y |
| bbm-154 | CONTROL-OF-TH1-TH2-DIFFERENTIATION | 21 | immunity and infection | paired | 10.1016/j.biosystems.2005.10.004 |
| bbm-158 | LAMBDA-PHAGE-LYSOGENY | 7 | microorganisms | paired | 10.1007/bf02460619 |
| bbm-162 | DROSOPHILA-DPP-PATHWAY | 18 | development and differentiation | paired | 10.1039/c3mb70187e |
| bbm-166 | DROSOPHILA-JAK-STAT-PATHWAY | 19 | development and differentiation | paired | 10.1039/c3mb70187e |
| bbm-168 | DROSOPHILA-NOTCH-PATHWAY | 13 | development and differentiation | real only | 10.1039/c3mb70187e |
| bbm-169 | DROSOPHILA-GAP-A | 7 | development and differentiation | paired | 10.1006/jtbi.2001.2335 |
| bbm-170 | DROSOPHILA-GAP-B | 7 | development and differentiation | paired | 10.1006/jtbi.2001.2335 |
| bbm-171 | DROSOPHILA-GAP-C | 7 | development and differentiation | paired | 10.1006/jtbi.2001.2335 |
| bbm-172 | DROSOPHILA-GAP-D | 7 | development and differentiation | paired | 10.1006/jtbi.2001.2335 |
| bbm-191 | SEGMENT-POLARITY-1-CELL | 19 | development and differentiation | paired | 10.1387/ijdb.072439ls |
| bbm-208 | HEMATOPOIESIS-AGING | 15 | development and differentiation | sensitivity | 10.1101/2022.02.08.479548 |
| bbm-212 | ESCHERICHIA-COLI-TRYPTOPHAN | 16 | microorganisms | paired | 10.48550/arxiv.2202.11182 |
| bbm-245 | CARDIOMYOCYTE-DIFFERENTIATION | 21 | development and differentiation | paired | 10.1101/2024.12.19.629328 |
| bbm-264 | PREIMPLANTATION-EMBRYO-TROPHECTODERM-1 | 21 | development and differentiation | paired | 10.1038/s41540-025-00537-7 |
| bbm-265 | PREIMPLANTATION-EMBRYO-TROPHECTODERM-1-MATURE | 17 | development and differentiation | sensitivity | 10.1038/s41540-025-00537-7 |
| bbm-266 | PREIMPLANTATION-EMBRYO-TROPHECTODERM-2 | 26 | development and differentiation | sensitivity | 10.1038/s41540-025-00537-7 |
| bbm-267 | PREIMPLANTATION-EMBRYO-TROPHECTODERM-2-MATURE | 23 | development and differentiation | paired | 10.1038/s41540-025-00537-7 |
| bbm-270 | PREECLAMPSIA-PATHOGENESIS | 30 | immunity and infection | paired | 10.1101/2025.08.08.25333339 |
| bbm-272 | FLT3-ITD-AML-SIGNALING | 30 | signalling | paired | 10.7554/elife.90532.2 |
| bbm-278 | STOCHASTICITY-IN-HEMATOPOIESIS | 21 | development and differentiation | paired | 10.1038/s41540-024-00469-8 |
