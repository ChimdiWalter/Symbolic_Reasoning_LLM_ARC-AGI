# CORA Capability-Growth Gate

**Protocol id:** `CORA_CAPABILITY_GROWTH_GATE:v2`
**Path:** `docs/CORA_CAPABILITY_GROWTH_GATE.md`, branch `cora-tti-dev`
**Supersedes:** `CORA_CAPABILITY_GROWTH_GATE:v1`, commit `da6c916`, same path. v1 stays in git history.
**Status:** FROZEN ON COMMIT. Written from the binding corrections C1 to C17 issued 2026-09-13. Written and committed while Step B is still running and before any Step-B output has been read. Repaired after two rounds of independent review; section 21 lists every change.

Two trees are referenced throughout.

```
MAIN = /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project
TTI  = /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
```

MAIN holds the live experiment and is authoritative for every Step-B artifact. TTI holds this gate. No gate stage writes into MAIN. No gate stage reads a TTI copy of a Step-B artifact.

Outcome codes are spelled exactly as written here. Codes carried over from v1 keep their hyphens. Codes introduced by the corrections keep their underscores.

---

## 1. Purpose, and what this is NOT

### 1.1 Purpose

This document is the only authority over everything that happens between the moment the Step-B freeze pin can be created and the moment Lockbox200 is either recorded as eligible for a separate, separately frozen evaluation or recorded as staying closed.

The scientific question is narrow. CORA has shown search and prior transfer. It has shown predictive-selection transfer narrowly, and abstraction information narrowly (32 of 32 matched nulls beaten). It has not shown that a learned abstraction beats concrete memory: the preregistered replication failed at +3, 95 percent paired bootstrap interval [-1, 8]. It has not shown bounded search-reach gain: zero witnesses, with every policy fitting the same 188 of 256 targets. Level 3A efficiency transfer is established. Level 3B capability transfer is not achieved. Level 4 semantic self-extension is pending, and Step B tests it.

The open question is whether failure can produce new operational capability: whether `K` becomes `K' = K union {e}` in a way that is verified, causally load-bearing, and not a renaming of something `K` already denotes.

The gate exists to stop a non-discovery from being recorded as a capability-growth witness. It also exists to make a negative result easy to reach, cheap to record, and impossible to turn into a positive by restatement.

### 1.2 What this is NOT

1. It is not a scoring exercise. No stage produces an ARC number. The sealed number stays 185/1000 (v23, artifact-backed) until a new sealed measurement exists.
2. It is not a proof of non-definability. Every separation result is relative to a bounded enumeration, a frozen probe set, one seed and one equality relation.
3. It is not a tuning loop. Nothing observed inside the gate justifies changing anything the gate measures.
4. It is not a promotion pipeline for near misses. There is no partial witness, no partial rung and no provisional promotion.
5. It is not a re-run mechanism. A negative result ends the gate. It does not license a second Step-B run with adjusted inventory, thresholds or bounds.
6. It does not open Lockbox200 or the 120 public evaluation tasks.
7. It does not treat a provenance failure as a scientific result, in either direction.
8. It does not treat the earlier DEV-60 test-time-invention arm as evidence about additive semantic extension (section 5).

---

## 2. Pre-registration, supersession of v1, and order of authority

### 2.1 Pre-registration statement

This document was written before the Step-B outcome exists. The project record shows the Step-B runner still live, no final output hash file, and no `STEP B FROZEN` marker. `TTI/outputs/tti/stepB_gate/` holds no pin. The pin tool has never created a pin against the live tree. Pre-freeze dry runs against the live tree are retired, and the tool refuses them.

Every decision rule, literal constant, outcome code and frozen interpretation below was fixed before any result was visible. Pre-freeze exposures that did occur are recorded in section 3, and their influence is removed by quarantine.

### 2.2 Supersession

v1 was committed before the Step-B outcome. v2 supersedes it, also before the outcome. v2 has a new protocol id and keeps the same path. Section 21 lists every change from v1 with its reason. A claim produced under v2 cites v2. No stage executes under v1 after v2 is committed.

### 2.3 Order of authority

| Rank | Document | Pin prefix |
|---|---|---|
| 1 | `docs/CORA_LEVEL4_MANIFEST.md`: criteria 1 to 6, input whitelist, standing prohibitions | `607ed54c305d` |
| 2 | `docs/CORA_LEVEL4_STEPB_DESIGN.md`: separation certificate, frozen Step-B interpretations | `28cc8734330345bf` |
| 3 | `docs/LOCKBOX_PROTOCOL.md`: split rules | `1d0b0a5af606` |
| 4 | `docs/CORA_DATA_ACCESS_DAG.md`: access edges and their order | recorded at P0 |
| 5 | `docs/CORA_STEPB_PREFREEZE_DEVIATIONS.md`: deviations D1 to D8, quarantine rules Q1 to Q6 | recorded at P0 |
| 6 | This document | recorded at P0 |

Where this document is stricter than a source above, this document governs. Where this document is looser, the source governs, this document is defective, and it is amended under 2.5. The quarantine rules of rank 5 bind every rule in this document.

The DAG classes the provenance firewall F4 as "never read by any new module". That rule governs the new packages. The gate reads the firewall only through the promotion-time edge the DAG itself defines, only in the G7 and G8 scripts, and only after the admitted set is frozen.

### 2.4 Declared tightenings and corrections

Each is declared before any outcome. Each is either strictly harder to pass than the source position or a correction of a demonstrated implementation error.

| Change | Source position | Position here | Direction |
|---|---|---|---|
| Separation baseline space | closed terms of the result type | open terms of the candidate's own interface, applied to the same argument tuple | harder |
| `MAX_CANDIDATES` truncation of the separation baseline | 8 | none | harder |
| Early stopping in the separation enumeration | stops at first fitting depth | none | harder |
| Separating-witness robustness | one probe | at least 3 probes over at least 2 contexts, and no baseline term agreeing on every jointly defined probe | harder |
| Criterion 6 endpoint | "transfers to at least one task outside its invention provenance" | a six-leg CAPABILITY-GROWTH WITNESS on E_transfer | harder |
| Gate arm budget | 8.0 s | 64.0 s, identical for every condition | harder for B and A, symmetric |
| Errors | collapsed to `None` by nested `except Exception` layers | instrumented evaluator recording the exception class | correction |
| Leave-one-out | program re-induced under a fixed extension | full adaptive leave-one-out (section 9) | harder |
| Comparison of K and K plus e | whatever the install path does | additive comparison with a preflight (section 7) | harder |
| Pin readiness | freeze marker | marker, final output hash file, and no live runner | harder |
| Leg B and leg A | K's first-ranked program | reach over K's complete bounded enumeration (8.1) | harder |
| Pin provenance | digest stored beside the pin | atomic pin bound to its commit; commit-bound module pin; both re-verified on every read | harder |
| Raw ARC training data | licensed at stage 7 | never read by any gate stage; per-split extracts only | harder |
| K-affecting code | hashed before G3b | completed before G2 and listed in the module pin | harder |
| Unlock events | a committed file byte-identical to HEAD | one-shot, hash-bound, chained events that require committed stage records | harder |
| Pin binding | a tracked record in the current branch's history | a tracked record, one distinct blob across all refs and the reflog, and an anchor outside both checkouts | harder |
| K_PLUS_E search | stops at the first fit | complete enumeration, accepted program pinned before any reference loads | harder |
| Repeats | aggregation undefined | every repeat must agree, otherwise `INCONCLUSIVE` | harder |
| De-collision | task identity | task identity and a content hash under a declared transform group | harder |

### 2.5 Amendment rule

After this document's sha256 is recorded in `gate_tool_manifest.json`, no sentence changes except by a dated amendment appended at the end, naming the pre-existing, outcome-blind evidence that forces it. An amendment may only tighten. A proposed change that would make a positive easier is refused, and the refusal is recorded. No amendment is permitted between pin creation and the completion of G8. An amendment written after any Step-B output record has been read is void for every claim that depends on that record.

An implementation defect justifies correcting a script so that it does what this document declares. It never justifies changing what this document declares.

### 2.6 Frozen constants

Every number the gate uses is fixed here. None is chosen later. No constant was set or moved using any observation from D1 to D5.

| Constant | Value | Applies to |
|---|---|---|
| `PYTHONHASHSEED` | `0` | every gate process |
| `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS` | `1` | every gate process |
| gate worker count | `1` | every gate process |
| `ARC_META_BUDGET_S` | `64.0` | every condition in G6, G7, G8, G10 |
| `GATE_REPEATS` | `3` | every condition execution in G6, G8, G10 |
| `WITNESS_SEED` | `424242` | frozen probe generator, unchanged |
| `SEP_CONTEXTS` | `6` | from the pinned witness generator bounds |
| `SEP_ARG_COMBOS` | `24` | frozen behaviour default, unchanged |
| `SEP_MAX_DEPTH` | `5` | separation enumeration |
| `SEP_PER_TYPE_CAP` | `4000` | separation enumeration |
| `SEP_MAX_CANDIDATES` | none | truncation removed |
| `SEP_ENUM_CEILING_S` | `3600` | per candidate, wall clock, measured outside the enumeration |
| `SEP_DEF_MIN` | `8` | non-vacuity floor, defined probes |
| `SEP_CTX_MIN` | `2` | non-vacuity floor, contexts |
| `SEP_MIN_SEPARATING_PROBES` | `3` | robustness floor |
| `SEP_MIN_SEPARATING_CONTEXTS` | `2` | robustness floor |
| `CE_SEED` | `828282` | criterion-5 counterexample generator |
| `CRIT3_MIN_TASKS` | `20` | minimum size of the union of both regression legs |
| `LOO_MIN_FOLDS` | `2` | below this, L is `INCONCLUSIVE` |
| `L2_MIN_SOURCES` | `2` | distinct pre-transfer source tokens for rung L2 |
| E_transfer size | resolved from the firewall and recorded; the record states 150 | G8 |

### 2.7 Pre-freeze obligations (P0)

P0 items are not gate stages. The P0 rule: a gate stage may execute only a script whose sha256 appears in `gate_tool_manifest.json` as attested by the committed event `g3b_open` (section 6), which precedes the first read of Step-B output content. Stages G1, G2 and G3a run before that event exists. Each of their stage records names the sha256 of every script it executed, and the final tool manifest lists every version that ran, so the attested record names the bytes that wrote the pin and the module pin. A script committed after that event may still run. Every artifact it produces carries the permanent stamp `POST-INSPECTION-TOOLING`, and every claim that consumes such an artifact is exploratory, never confirmatory. The stamp propagates.

| Id | Obligation | Deadline |
|---|---|---|
| P0.1 | `gate_tool_manifest.json` recording the sha256 of this document, of `docs/CORA_DATA_ACCESS_DAG.md` and `docs/CORA_STEPB_PREFREEZE_DEVIATIONS.md` (ranks 4 and 5 of 2.3), and of every gate script, with a per-stage table of the expected `config_digest` and `runtime_state_digest`. A draft may be committed at any time and unlocks nothing. The final form is committed at the end of G3a and attested by `g3b_open` | end of G3a, before `g3b_open` |
| P0.2 | `gate_capture_run_env.py` reads, from `/proc` only, the argv, executable, working directory, start time and environment of every process matched by `freeze_pin.runner_processes()`, and writes `stepB_run_env.json` once. Values are recorded only for allowlisted reproducibility variables; every other variable is counted, not named. If no runner remains, it records `ENV-RUN-UNKNOWN`. Built, and executed while the runner was live (22.3) | while the runner is live |
| P0.3 | `gate_regression_set_freeze.py` writes and hashes the criterion-3 regression set (G7) | G3a, before G3b |
| P0.4 | `.gitignore` carries `!outputs/tti/stepB_gate/**` and `!outputs/tti/stepB_gate/*.txt`; every gate script commits with `git add -f` and verifies with `git ls-files --error-unmatch` | before G1 commit |
| P0.5 | `tests/test_gate_isolation.py` per section 15.4 | before G3b |
| P0.6 | every gate script named in section 22.2 exists, is committed, and is hashed in the tool manifest | before G3b |
| P0.7 | the candidate-independent substrate predicates and the additivity preflight (sections 7 and 11) are run on synthetic fixtures and ledgered | G3a, before G3b |
| P0.8 | every candidate-independent engine change, additive wrapper or bridge, with its behaviour-preservation record for K on the frozen synthetic fixture set, is completed and listed in the module pin | before G2 |
| P0.9 | `gate_preflight.py` is built and committed. Built (22.1) | before G1 |
| P0.10 | `gate_extract_splits.py` (15.3) exists, is candidate-independent, reads the training challenges file, the training solutions file and the Lockbox manifest only through `GateGuard.extract`, and is hashed in the tool manifest. The filtering reader and `GateGuard.extract` are built (22.1) | before `g3b_open` |
| P0.11 | `gate_g1_record.py` writes `g1_record.json`: preflight, pin, binding and anchor outcomes, both commit hashes, the environment caveats derived by `run_env_caveats()` from the committed `stepB_run_env.json`, and the SA-10 classification | before G1 |
| P0.12 | `gate_module_pin.py` calls the built `freeze_pin.write_module_pin` with the roots, files and cross-tree pairs of G2 step 3 | before G2 |
| P0.13 | `gate_output_hash_recompute.py` recomputes the runner's final output hash from the pinned bytes with the formula resolved at G3a (SA-15) | end of G3a, before `g3b_open` |
| P0.14 | `gate_import_closure.py` resolves K's import closure from the pinned source and the module pin | end of G3a, before `g3b_open` |
| P0.15 | the `open()` audit hook of DR-11 is built, passes a synthetic positive control that records a forbidden read, and is hashed in the tool manifest | end of G3a, before `g3b_open` |

P0.4 exists because `TTI/.gitignore` ignores `outputs/`, `*.txt` and `RESUME*.md`. Without the negation, a plain `git add` of the pin, the tool manifest, the access ledger or the admitted set silently does nothing.

---

## 3. Pre-freeze deviations and quarantine (binding)

### 3.1 The record

`docs/CORA_STEPB_PREFREEZE_DEVIATIONS.md` records every pre-freeze access a mechanical scan of agent tool-call inputs could identify. It is binding on this document and on every gate script.

| id | what | against |
|---|---|---|
| D1 | one mechanism-input corpus row decoded in memory; keys and demonstration count printed | mechanism-input contents |
| D2 | every candidate inventory instance printed by name and typed signature | candidate contents, read broadly |
| D3 | runner and Step-B package source read, including output-record code | the gate guard's own seal |
| D4 | ARC evaluation inputs, holdout included, loaded into memory; no scoring | the spirit of the holdout rule |
| D5 | live-tree pin dry runs hashed sealed files and printed lane digests | retired by the 2026-09-13 directive |
| D6 | transfer split documentation read; checked, zero identifiers | not a deviation |
| D7 | Lockbox directory filenames listed | names only |
| D8 | guard misclassified worktree copies and the firewall | tooling defect, fixed; no access resulted |

None of these touched the running experiment. None exposed what the run proposed, kept or selected, any cluster convergence, any E_transfer identity, any Lockbox content, any sealed expectation or any token mapping. Step B is not invalidated by these facts alone. v1 encodes assumptions about Step-B output record fields that were learned from source (D3) rather than from outputs. v2 removes their standing as facts.

Two operations were performed under this protocol before the freeze. Both read `/proc` alone and neither read any experiment file: the runner identity check behind G1 step 4, and the P0.2 environment capture. The deviation record lists them as permitted operations.

### 3.2 Quarantine rules

**Q1.** No observation from D1 to D5 may be used to choose a witness substrate, choose or shape a witness procedure, set or move a threshold, define a task pool, or order candidates.

**Q2.** Every statement in this protocol about the field layout of a Step-B artifact or a task record is a declared ASSUMPTION. That covers field names, the presence of held-out test pairs, the presence of task identifiers, and record shapes. Each is checked mechanically at G3, or, for an artifact still sealed at G3, at its first licensed access (SA-11 to SA-15). A failed check emits `SCHEMA_ASSUMPTION_FAILED` and stops the gate as `TERM-HALTED`. Any tooling change made after it is `POST-INSPECTION-TOOLING`.

**Q3.** The protocol must be valid under either answer to each of these: whether the invention corpus carries held-out test pairs; whether it carries task identifiers; which instances the inventory contains. Where a stage depends on one, both branches are stated in advance.

**Q4.** The bridge shapes named in the failure branch come from the directive of 2026-09-09. They are not revised with any knowledge from D2.

**Q5.** These claims may not be premises anywhere in this protocol: that the blind runtime already carries a `Set[Region] -> Grid` bridge; that the Step-B corpus carries no test pair and no task identifier.

**Q6.** Any further pre-freeze agent work receives an explicit forbidden-path list, and its tool-call inputs are scanned against that list before its output is used.

### 3.3 How v2 complies

1. **Endpoint of T.** v1 section 5.4 justified its per-pool final-output endpoint by what the corpus writer emits. That reliance is removed. Whether a licensed held-out test input and reference output exist for a task is decided by a mechanical check at the stage where that data becomes licensed. Both branches are stated in section 8.4.
2. **Schema assumptions.** Every field name used below is listed in 3.4 as an assumption and is checked at G3.
3. **Implementation assumptions.** Every code-level identifier this protocol names (module, function, global, constant) was learned from design source (D3). Each is a declared implementation assumption, checked at G3a by resolving the name in the hash-verified pinned source. A missing or differently shaped name emits `SCHEMA_ASSUMPTION_FAILED` with category `IMPL`.
4. **Inventory independence.** No rule names a specific inventory instance, schema family member or terminal type as a premise. The constructor pre-pass and the separation test run over whatever the pinned inventory contains. Where v1 justified a rule by a specific instance, v2 gives a generic justification, and the rule stands only on that.
5. **Determinism lanes.** v1 G1 step 6 would halt when determinism-lane digests differ. That step is removed. The files in `level4_stepB_gate_outputs` are pre-run gate artifacts: the pin records their modification times, those times precede the pinned run manifest's, and the resume log records that the pre-run determinism gate passed on a MASKED comparison with deadline-hit masking. Raw digest inequality in those files is therefore not a defect. G1 defers to the recorded pre-run gates verdict. The justification is the pin's own mtime fields and the resume log. It is not D5.

### 3.4 Declared schema assumptions, checked at G3

| Id | Assumption | Branches | On failure |
|---|---|---|---|
| SA-01 | the pinned merged Step-B output holds one record per equivalence class, with fields `lane`, `label`, `signature`, `behaviour_fingerprint`, `members`, `representative`, `proposed_from`, `kept_for` | single | `SCHEMA_ASSUMPTION_FAILED` |
| SA-02 | classes are keyed by `(lane, signature, behaviour_fingerprint)` and `representative` equals `members[0]` | single | same |
| SA-03 | per (candidate, source) resolution rows carry a source token, `cluster_id`, `found`, `uses_candidate`, `loo_passed`, `loo_folds`, and a per-cluster `certified_sources` set | single | same |
| SA-04 | `independent_source_tokens` is a count, not a set | count, or set | same, if neither |
| SA-05 | the inventory carries per-schema `executable_semantics.function` and `executable_semantics.source_sha256` | single | same |
| SA-06 | `label` is a function of `lane` | single | same |
| SA-07 | the run manifest records a fingerprint of the witness generator's output | single | same |
| SA-08 | invention-corpus records carry a held-out test input and reference output | present, or absent | same, if neither describes the records uniformly |
| SA-09 | invention-corpus records carry a task identifier | present, or absent | same, if neither describes the records uniformly |
| SA-10 | every file in `level4_stepB_gate_outputs` has a pinned mtime earlier than the pinned run manifest mtime | single | recorded as `GATE_OUTPUT_MTIME_NOT_PRE_RUN`; no decision reads those files |
| SA-11 | the provenance firewall carries `source_token_to_task` and `within_stage_holdout.E_transfer`; checked at G7b immediately after `g7b_open`, before any value is used | single | `SCHEMA_ASSUMPTION_FAILED`; E_transfer stays unopened |
| SA-12 | the Lockbox manifest holds the Promotion id list at the key path `splits.promotion`; checked at G7b by `GateGuard.extract` with that key path | single | same; the extraction writes nothing |
| SA-13 | the training challenges and training solutions files are JSON objects keyed by task id; checked by the filtering reader at G7b | single | same |
| SA-14 | the training solutions file holds a reference output for every E_transfer test input; checked at G8 entry by key presence only | present, or absent | same, if neither describes the records uniformly; the branch that holds selects 8.4 branch 1 or 2 |
| SA-15 | the pinned runner source computes `level4_stepB_output_hash.txt` by a formula that can be recomputed from pinned artifact bytes; resolved at G3a | recoverable, or not | if not recoverable, `OUTPUT_HASH_FORMULA_UNRECOVERABLE` is recorded and the marker-to-pin window stays under G1 Claim NOT licensed; nothing halts |

A two-branch assumption does not fail when one branch holds. The checker records which branch holds, by field presence, without printing values. Under SA-09 "present", no identifier is used for any resolution before stage 7. Provenance always resolves through the firewall at G7, so the procedure is the same under both branches.

---

## 4. The claim ladder

This section is the canonical ladder. Rungs are strictly nested. `scripts/gate_rung.py` assigns rungs mechanically from recorded outcome codes. No person assigns a rung. The function takes no label argument.

### L1. Generation-lane candidate

**Predicate.** The class is present in the pinned merged Step-B output with `lane == "K2"` (SA-01).

**Claim licensed.** The K2 generation lane emitted this proposal.

**Claim NOT licensed.** Any statement containing the words new, novel, invented, semantic, extension or capability.

`label` is a function of `lane` (SA-06), so it carries nothing `lane` does not. `lane` is provenance about which vocabulary produced the term, not evidence of novelty. The label is copied into artifacts as `generation_lane_label` and is never read by any predicate. Novelty must not be inferred from the label `NEW_SEMANTIC_PRODUCTION`.

### L2. Operational language extension

**Predicate.** L1, and `kept_for` is non-empty, and at G6, on the selected substrate, legs B, P and U are all `PASS` on at least `L2_MIN_SOURCES = 2` distinct pre-transfer source tokens.

**Claim licensed.** Installed as an addition, `e` let the fixed-budget search return an accepted program that uses `e` on source tasks that the complete bounded baseline could not reach under the reach rule of 8.1. Where no baseline program fit the demonstrations, the claim is stated at level `DEMONSTRATION_FIT`. Where fitting baseline programs existed and none rendered a licensed reference, which on pre-transfer tasks exists only under 8.4 branch 1, it is stated at level `HELD_OUT_OUTPUT`. The set of solutions reachable under the fixed budget grew.

**Claim NOT licensed.** That the language denotes anything it could not denote before. A macro over `K_L4*` reaches L2 as easily as new semantics. Forbidden at L2: "new semantics", "not expressible", "outside the language". Step-B retention, which rests on a program-level fold check, never counts toward L2 by itself.

### L3. Semantic expressivity extension, bounded

**Predicate.** L2, and `separation_primary == SEP-SEPARATED` against `F(K_L4*)`, and `separation_secondary == SEP-SEPARATED` against `F(E_L4*)` (section 12), and the constructor pre-pass did not stamp the class `MACRO-OVER-K-L4STAR-STRUCTURAL`.

**Claim licensed.** Level `BOUNDED_ENUMERATION`: on the frozen, candidate-independent probe domain and under the declared bounds, `e` produces a behaviour that no open term of the bounded enumeration of `K_L4*` produces on the same inputs.

**Claim NOT licensed.** That `e` is undefinable in `K_L4*`; that `e` is useful; any sentence without its bounds. Permitted form: "no term of the bounded enumeration of `K_L4*` at depth at most 5 under a per-type cap of 4000, over the frozen witness set, reproduces this behaviour on the recorded probes". Forbidden: "e is not expressible in `K_L4*`".

### L4. Semantic invention, bounded

**Predicate.** L3, and at least one CAPABILITY-GROWTH-WITNESS with `pool == E_TRANSFER`, all six legs `PASS`, on a task outside `e`'s invention provenance by identity, under the single-pass rules of G8, and criteria 3, 4 and 5 all `PASS`, and criterion 6 `PASS` (`C6-PASS`).

**Claim licensed.** Level `HELD_OUT_OUTPUT`, stated only in this form and only with the section 19 limitations attached: an operator generated from certified failures under a frozen blind proposal language, installed as an addition to an unchanged baseline, separated from the bounded enumeration of the prior language, re-induced under full adaptive leave-one-out, and causally necessary for a correct held-out output on a task that took no part in inventing it.

**Claim NOT licensed.** Priority claims; ARC score claims; generality claims; the word "general"; any claim that the extension was re-invented from held-out demonstrations of an E_transfer task; that `e` is undefinable in `K_L4*`; the sentence "e is not expressible in `K_L4*`".

### Ladder rules

**LR1.** A report sentence naming a candidate carries its rung code in the same sentence. `NEW_SEMANTIC_PRODUCTION`, "new production", "invented" and "extension" may not appear in a claim sentence without the rung code.

**LR2.** A rung is never described as essentially, effectively or nearly the next rung. The report states the achieved rung and names the first predicate that is not `PASS`, with its status. A `NOT_MEASURED` predicate is named as unmeasured, never as failed.

**LR3.** There is no partial rung and no partial witness. "partial witness", "near witness", "near miss" and "would have passed but for" are forbidden in every gate artifact and every downstream document.

**LR4.** Counts are reported per rung, never as one total. Permitted form: "n K2-lane kept classes, of which a at L2, b at L3, c at L4". "n new semantic productions" is prohibited.

**LR5.** Any output that prints `NEW_SEMANTIC_PRODUCTION` prints the class's separation outcome code in the same table row.

**LR6.** K1-lane classes are repairs. Their ceiling is recorded as `RUNG-K1-REPAIR`, their separation code is `SEP-NOT-APPLICABLE-K1-LANE`, and they are refused admission to E_transfer. The Step-B `uses` field short-circuits to true for lane K1, so the use trace is not decidable for K1 and leg U is `NOT_MEASURED` with reason `USE_TRACE_UNDECIDABLE_K1_LANE`. A K1 class can never be part of a witness.

**LR7.** Rung assignment runs three times, and each run writes its own immutable artifact: at G5 (evidence through G4), at G7a step 2 (evidence through G6, with the statuses recoded by 8.8), and at the end of G8 (E_transfer evidence).

---

## 5. The prior real-engine result, and why it is not evidence about extension

The earlier DEV-60 test-time-invention arm is NOT a test of additive semantic extension. These source facts were verified directly and are unaffected by the quarantine, because they concern `geocat_arc/`, not Step B.

1. In `geocat_arc/object_reasoning/meta_induction.py`, `induce_computed_candidates` (line 550) checks `trigger_fires` before it consults installed concepts. On a task where the trigger does not fire, an installed extension is never consulted.
2. When a concept produces hits, the same function returns those hits before ordinary search runs. The ordinary `search(...)` call is unreachable in that branch.
3. `search_with_concepts` (line 378) omits the fold-coverability condition that `search` applies (line 455), and stops at the first productive concept.

The augmented arm therefore replaced the base hypothesis stream on a hit. It did not implement `K union {e}`. Its only possible differential reach was the set of tables whose keys were witnessed once, which the downstream leave-one-out gate is built to reject.

**Binding consequences.**

- The 49 activations with zero acceptances are infrastructure evidence only. They must never be cited as evidence that test-time semantic extension fails. Such a citation is on the forbidden list (DR-34).
- v1 section 15.3 is corrected. It implied that avoiding the `meta_induction` path settled the matter. It did not. The additivity of the `meta_v21` concept path and of the blind runtime concept path is NOT verified. The additivity preflight of section 7 decides both. Until it does, neither path may supply a B or A leg.
- The `meta_induction` concept path is used by the preflight only as a required negative control (7.4).

---

## 6. The eleven stages

Stages G1 to G11 correspond one to one, in order, with the eleven steps of the milestone. No stage is reordered, skipped, merged or run ahead of its predecessor. Every stage writes its artifacts to `TTI/outputs/tti/stepB_gate/`, each with a sibling `<name>_hash.txt`. Every artifact is immutable: a stage finding its own artifact present exits `REFUSE-ALREADY-RUN` and changes nothing.

Stage numbers match `cora_tti.gate_guard.Stage`:

| Gate | `Stage` | Integer |
|---|---|---|
| G1 | `PIN_OUTPUT_HASH` | 1 |
| G2 | `PIN_PROTOCOL_HASHES` | 2 |
| G3 | `INSPECT_RETAINED_PRODUCTIONS` | 3 |
| G4 | `CHARACTERIZE_CANDIDATES` | 4 |
| G5 | `CLASSIFY_CLAIM_LEVEL` | 5 |
| G6 | `CAPABILITY_GROWTH_WITNESS` | 6 |
| G7 | `E_TRANSFER_EVALUATION` | 7 |
| G8 | `E_TRANSFER_MEASUREMENT` | 8 |
| G9 | `PROMOTION` | 9 |
| G10 | `POST_PROMOTION_ANALYSIS` | 10 |
| G11 | `GATE_COMPLETE` | 11 |

Stages 3, 7 and 8 contain ordered parts that share a stage number, and the Lockbox class must stay closed until the gate is complete. `GateGuard` separates them by five events. Each is a small file, written once by `write_event()` at the step that owns it and then committed.

| Event | Written at | Attests | Requires, committed no later | Predecessor | Effect |
|---|---|---|---|---|---|
| `g3b_open` | end of G3a | `gate_tool_manifest.json` | `g3a_record.json` | none | unlocks Step-B outputs: G3b begins |
| `g7b_open` | end of G7a | `etransfer_admitted_set.json`, non-empty | `g6_record.json`, `g7a_record.json` | `g3b_open` | unlocks the firewall, the Promotion extract and Promotion extraction: G7b begins; E_transfer is spent from this commit on |
| `g8_open` | end of G7b | `etransfer_withdrawals.json`, admitted set non-empty after withdrawals | `g7b_record.json` | `g7b_open` | unlocks the E_transfer extract and E_transfer extraction: G8 begins |
| `g8_closed` | end of the single G8 pass | `etransfer_ledger.jsonl` | none | `g8_open` | closes E_transfer content and E_transfer extraction for good |
| `g11_complete` | G11, only when `lockbox_closure.json` records `LOCKBOX-ELIGIBLE` | `gate_completion_record.json` | `lockbox_closure.json` | `g8_closed` | permits Lockbox-class reads in code, for a separately pre-registered evaluation outside this gate; never written while the Lockbox stays closed |

An event counts only when it is committed exactly once, has one distinct blob across all refs and the reflog, and is byte-identical to HEAD; when its attested artifact is committed and still hashes to the attested value; when its required stage records were committed no later than the event; and when its predecessor is valid and was committed strictly earlier. An absent event keeps its classes sealed. A rewritten, drifted or broken event raises `PinProvenanceError` and stops the gate as `GATE_STOPPED_PROVENANCE_FAILURE`. A draft tool manifest, admitted set or withdrawal record committed early unlocks nothing. `write_event` refuses `g11_complete` with `EVENT_LOCKBOX_NOT_ELIGIBLE` unless the committed closure record says `LOCKBOX-ELIGIBLE`, and its predecessor is `g8_closed`, so a gate that ends before G8 can never open the Lockbox class. Gate results never carry a sealed name stem (15.5 item 5). Only the two extracts do, and every file under `extracts/` is sealed whatever its name. G8 therefore writes its results under names such as `etransfer_results.jsonl`.

### 6.0 Rules common to every stage

**Common header.** Every artifact begins with this header. A stage that cannot fill every field refuses to run.

```json
{
  "artifact": "stepB_gate/<name>.json",
  "stage": "G6",
  "protocol_id": "CORA_CAPABILITY_GROWTH_GATE:v2",
  "protocol_sha256": "...",
  "tool_manifest_sha256": "<null before g3b_open>",
  "events": {"g3b_open": "<commit or null>", "g7b_open": "<commit or null>", "g8_open": "<commit or null>", "g8_closed": "<commit or null>"},
  "pin_anchor_verified": true,
  "pin_sha256": "...",
  "pin_verification": "PIN_VERIFIED",
  "config_digest": "<DR-04, null before g3b_open>",
  "runtime_state_digest": "<DR-05, null before g3b_open>",
  "substrate": "<section 11, or null before G6>",
  "git_at_launch": {"tree": "...", "head": "...", "dirty_file_count": 0},
  "git_at_write":  {"tree": "...", "head": "...", "dirty_file_count": 0},
  "environment": {"python": "...", "pythonhashseed": "0", "arc_meta_budget_s": 64.0,
                  "omp_num_threads": "1", "workers": 1, "platform": "..."},
  "post_inspection_tooling": false,
  "started_utc": "...", "finished_utc": "...",
  "stage_outcome": "...",
  "guards": {"<name>": {"evaluated": 0, "fired": 0}},
  "inert_guards": [],
  "counts": {}, "records": []
}
```

`git_at_launch` is read as the first action of the process, before any input file is opened. `git_at_write` is read immediately before serialization. A difference in `head` sets `STAGE-PROVENANCE-DRIFT`, and the artifact is unusable downstream.

**Fail-closed verification after the pin.** Every stage after G2 requires, mechanically, that `verify_pin(require_binding=True)` returns `PIN_VERIFIED` and that `verify_module_pin()` returns `MODULE_PIN_VERIFIED`. The freeze pin must match its digest, every pinned artifact must exist with its pinned sha256, no previously unseen file may have appeared in any pinned scope (section 15.2), and the pin must be byte-identical to its blob at the commit named in the binding record. The pin and its binding must each have exactly one distinct blob across all refs and the reflog, and the anchor record outside both checkouts must name the same pin sha256 and commit. The module pin must be committed exactly once with one distinct blob across all refs and the reflog, list at least one artifact, keep every listed artifact at its recorded sha256, keep every pinned root at its recorded file list, and keep every cross-tree pair identical apart from its declared exemptions. `GateGuard` runs both verifications at construction. On every read it re-hashes the file against whichever pin covers it, and checks whether the path lies in a pinned scope without a pin record. Each stage also calls `reverify()` immediately before writing its artifact.

The complete provenance vocabulary is `PIN_VERIFIED`, `PIN_MISSING`, `PIN_HASH_RECORD_MISSING`, `PIN_JSON_ALTERED`, `PIN_ARTIFACT_MISSING`, `PIN_ARTIFACT_DRIFT`, `PIN_SCOPE_GREW_AFTER_FREEZE`, `PIN_BINDING_MISSING`, `PIN_BINDING_REWRITTEN`, `PIN_COMMIT_MISMATCH`, `MODULE_PIN_VERIFIED`, `MODULE_PIN_MISSING`, `MODULE_PIN_ALTERED`, `MODULE_ARTIFACT_MISSING`, `MODULE_ARTIFACT_DRIFT`, `PIN_WRITTEN_BUT_UNVERIFIED`, `PIN_RECREATED_IN_HISTORY`, `PIN_ANCHOR_MISSING`, `PIN_ANCHOR_MISMATCH`, `MODULE_PIN_EMPTY`, `MODULE_SCOPE_CHANGED`, `MODULE_TREE_MISMATCH`, `MODULE_CLOSURE_OUTSIDE_PIN`, `PIN_OUTPUT_HASH_MISMATCH`, and the event failures `EVENT_REWRITTEN`, `EVENT_ARTIFACT_DRIFT`, `EVENT_CHAIN_BROKEN` and `EVENT_MALFORMED`.

Any failure raises `PinProvenanceError`, which is deliberately not an access refusal. The gate STOPS with terminal code `GATE_STOPPED_PROVENANCE_FAILURE`. That is a provenance failure, never a scientific negative result, and it is never repaired by repinning or by overwriting either pin.

**Hash seed and environment.** Every gate process is preceded by `gate_preflight.py`, which enforces the hash seed and thread constants of 2.6, committed tooling and a clean dev worktree, and writes nothing. Tooling is every file matching the declared tooling globs, on disk or tracked, so a new or deleted gate script is caught. Git runs with `--no-optional-locks`, so reading status rewrites neither index. It records the main checkout's dirty count without requiring it to be zero, because the gate never writes into the main checkout. The pin tool records `PYTHONHASHSEED` but does not enforce it, so the preflight runs first.

---

### G1. Record and pin the final Step-B output hash before semantic inspection

**Entry condition.** `gate_preflight.py` returns `PREFLIGHT_OK`. The P0.2 record `stepB_run_env.json` exists. P0.4 is in place.

**Procedure.**

1. Run `PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 scripts/gate_preflight.py`. It requires, in order: the hash seed `0`; the three thread variables `1`; every gate tooling file committed at HEAD with identical bytes; a porcelain-clean dev worktree. It records the main checkout's dirty file count without requiring zero, because the gate never writes into MAIN and so cannot make it clean. It writes nothing.
2. Declared branches for a preflight failure, fixed now so that nothing is improvised at the marker. On `PREFLIGHT_HASHSEED` or `PREFLIGHT_THREADS`, rerun under the stated environment. On `PREFLIGHT_UNCOMMITTED_TOOLING` or `PREFLIGHT_DIRTY_WORKTREE`, commit or remove the offending dev-worktree change and rerun. Each repair touches only the dev worktree, reads no Step-B content, and is recorded in `g1_record.json`.
3. Run `python3 scripts/pin_stepB_freeze.py` under the same environment. The first output line is `OUTCOME <name>`, and each outcome has a fixed exit code.
4. The tool checks readiness before hashing anything. The single immutable pin may be created only when ALL hold:
   - the marker `STEP B FROZEN` occurs in `MAIN/logs/level4_stepB_run.log`, counted by streaming the log;
   - `level4_stepB_output_hash.txt` exists in `MAIN/outputs/cora_breakthrough`;
   - no live runner process remains for the main checkout.

   Runner identity: a Python interpreter, identified by `argv[0]` or by its executable link, running the runner as a script path or as a module through `-m`. A relative script path is resolved against the process working directory and must land inside MAIN. A module launch must run from inside MAIN. An absolute script path must lie inside MAIN. A matching process whose working directory cannot be read counts as live. Before the freeze this rule was checked against `/proc` alone and matched the live runner, including its parent process.

   The runner condition exists so the run log cannot grow after its digest is taken. Both file names come from the project record, not from assumption. The restart script refuses to run when that output hash file exists, and the resume log states that the runner prints `STEP B FROZEN` together with the output hash.
5. A not-ready outcome writes nothing. The tool may be invoked again later. Nothing is inspected to diagnose a not-ready state. A runner that does not exit after the marker and the output hash file appear is not a failure branch: each check returns `FREEZE_RUNNER_STILL_ACTIVE`, is recorded in `RUN_HISTORY.md`, and the gate waits. The gate never signals, interrupts or accelerates the runner.
6. When ready, the tool collects the pinned scopes twice and requires agreement. It writes the pin and its digest into a private staging directory, flushes both, and renames the directory into place as `outputs/tti/stepB_gate/pin/` in one step, so either both files exist or neither does. It never overwrites. Immediately before the write it re-checks readiness and collects a third time; any difference writes nothing and returns `PIN_SOURCE_UNSTABLE`, or the readiness outcome that now holds. It verifies the pin at once. A pin that exists but fails that immediate verification returns `PIN_WRITTEN_BUT_UNVERIFIED`, which is terminal: the gate stops as `GATE_STOPPED_PROVENANCE_FAILURE`, and the pin is never recreated. If the process dies between the rename and that verification, a later `create` returns `PIN_EXISTS_REFUSING_OVERWRITE` with no `PIN_CREATED` recorded in `RUN_HISTORY.md`. The declared branch is then `--verify`: `PIN_VERIFIED` continues at step 8, and any other outcome is terminal as `PIN_WRITTEN_BUT_UNVERIFIED`.
7. Content invariant. Artifact bytes may be read transiently only for cryptographic hashing and line counting. They are never parsed, deserialized, semantically interpreted, retained after hashing, printed, returned or serialized into the freeze pin. The run log is additionally streamed to count the freeze marker. The sentinel tests prove that no content leaks into the pin, the printed output or the returned result. They do not prove that bytes never entered a hash buffer. Byte sizes and line counts are recorded for the run log only; every other record carries path, sha256 and mtime, so reading the pin gives no hint of any result's size.
8. Commit the pin directory with `git add -f` and verify with `git ls-files --error-unmatch`.
9. Run `python3 scripts/pin_stepB_freeze.py --bind`. It refuses unless the pin verifies, both pin files are byte-identical to their blobs at HEAD with exactly one commit in history, and each has exactly one distinct blob across all refs and the reflog. With exclusive create it writes the tracked record `docs/stepB_gate/pin_binding.json`, naming the pin's sha256 and its commit, and the anchor record `CORA_reports/gate_anchor/stepB_freeze_pin_anchor.json` outside both checkouts, naming the same two values. Commit the binding, then verify with `--verify --require-binding`. `--bind` writes the binding first and the anchor second. If the anchor write fails, it removes the uncommitted binding and returns `PIN_WRITE_FAILED`, so a retry starts clean. If the process dies between the two writes, the uncommitted binding, which no commit references, is deleted and `--bind` is rerun. A binding committed without an anchor is terminal. Copy the anchor's two values into the resume log and the published field report, which together form the external review record. From then on a pin deleted and recreated fails as `PIN_COMMIT_MISMATCH`; a pin or binding recreated on another branch cannot be bound and fails as `PIN_RECREATED_IN_HISTORY`; a rewritten binding fails as `PIN_BINDING_REWRITTEN`; and a missing or disagreeing anchor fails as `PIN_ANCHOR_MISSING` or `PIN_ANCHOR_MISMATCH`. The anchor is a second copy, not a tamper-proof store. A rewrite that also removes every ref, the reflog and the anchor is detectable only against the external review record (section 19).
10. Record both commit hashes in `RUN_HISTORY.md`. `RESUME_STAGE1.md` is not the record of record: it exists only in MAIN and is gitignored.
11. Derive the standing environment caveats with `run_env_caveats()` from the committed `stepB_run_env.json`, never from the pin process's environment. The protocol binding check, that this document's blob hashes to the value in the tool manifest, runs at G3a, where the tool manifest becomes final.
12. Record, from the pin's own mtime fields, the SA-10 classification of every file in `level4_stepB_gate_outputs`. G1 does not compare, and does not halt on, determinism-lane digests (3.3 item 5).

**Output artifact.** `pin/stepB_freeze_pin.json`, `pin/stepB_freeze_pin_hash.txt`, `docs/stepB_gate/pin_binding.json`, the anchor record outside both checkouts, `g1_record.json`.

**Closed outcome vocabulary.** Preflight: `PREFLIGHT_OK`, `PREFLIGHT_HASHSEED`, `PREFLIGHT_THREADS`, `PREFLIGHT_UNCOMMITTED_TOOLING`, `PREFLIGHT_DIRTY_WORKTREE`. Pin: `PIN_CREATED`. Not ready, nothing written, retry later: `FREEZE_MARKER_ABSENT`, `FREEZE_OUTPUT_NOT_READY`, `FREEZE_RUNNER_STILL_ACTIVE`, `PIN_SOURCE_UNSTABLE`, `PIN_WRITE_FAILED`. Refusals that change nothing: `PIN_EXISTS_REFUSING_OVERWRITE`, `DRY_RUN_REFUSED_ON_LIVE_TREE`, `CLI_USAGE_ERROR`. Terminal: `PIN_WRITTEN_BUT_UNVERIFIED`. `DRY_RUN_OK` exists for synthetic fixture trees only. Binding: `PIN_BOUND`. Retry after the named repair: `PIN_NOT_COMMITTED`, `PIN_WRITE_FAILED`. Refusal that changes nothing: `PIN_BINDING_EXISTS_REFUSING_OVERWRITE`. Terminal: `PIN_COMMIT_MISMATCH`, `PIN_RECREATED_IN_HISTORY`, `PIN_ANCHOR_EXISTS_REFUSING_OVERWRITE`, and any 6.0 verification failure that `--bind` returns. Every terminal code stops the gate as `GATE_STOPPED_PROVENANCE_FAILURE`. Environment caveats, derived by `run_env_caveats()` from the committed capture and never from the pin process: `ENV-HASHSEED-UNSET-AT-RUN`, `ENV-THREADS-UNSET-AT-RUN`, `ENV_CAPTURE_PARTIAL`, `ENV-RUN-UNKNOWN`. The capture itself returned `ENV_CAPTURED` (22.3); its other outcomes are `ENV_CAPTURE_PARTIAL`, `ENV-RUN-UNKNOWN` and `ENV_CAPTURE_EXISTS`.

**Refusal conditions.** Preflight not `PREFLIGHT_OK`; any readiness condition unmet; an existing pin; any attempt at a dry run against the live tree, which is refused before anything is read; binding before the pin is committed.

**Claim licensed.** The bytes of the pinned scopes at pin time are fixed, identified by sha256, and bound to a commit.

**Claim NOT licensed.** Any statement about what Step B produced; any statement that the pin tool read no bytes; any statement that nothing changed between the freeze marker and the pin; a match at G3b establishes only consistency among the pinned outputs, the hash file and the run log (SA-15).

---

### G2. Pin runner, manifest, candidate inventory and environment hashes

**Entry condition.** `PIN_BOUND`, and both the pin commit and the binding commit are verified present in the index.

**Procedure.**

1. Confirm that the pin holds a record for each of: the runner script, the restart script, the run log, the Step-B run manifest, the candidate inventory, `level4_blind_runtime_manifest.json`, `level4_provenance_firewall.json`, `level4_withheld_expectation_seal.json`, `concept_registry.json`, and at least one file in each of the `level4_stepB/` and `level4_blind_runtime/` source trees. A missing record emits `PIN2-INCOMPLETE` and halts. This check reads only the pin JSON, and the reading is recorded in `g2_record.json` as an access event. The pin carries no size or line count for any Step-B output.
2. Every candidate-independent engine change, additive wrapper or bridge that any substrate will use, together with its behaviour-preservation record for K on the frozen synthetic fixture set, is complete before this step (P0.8). Nothing that affects K is created after G2.
3. Run `gate_module_pin.py`, which calls the built `freeze_pin.write_module_pin` under the C2 invariant. It pins only what affects K. Roots, each with its full file list and every file's sha256, bytecode caches excluded: the dev-worktree copies of `level4_stepB/` and `level4_blind_runtime/`, and every top-level Python package directory of the dev worktree except `cora_tti/`, `tests/`, `scripts/`, `docs/`, `outputs/` and `data/`, which includes `geocat_arc/`. `cora_tti/` holds gate tooling governed by the tool manifest; if K's import closure reaches it at G3a, the gate stops as `MODULE_CLOSURE_OUTSIDE_PIN`. Files, by sha256: every engine change, wrapper, bridge and behaviour-preservation record from step 2; `MAIN/outputs/cora_breakthrough/level4_baseline_admissibility_v2.json`; `MAIN/outputs/lockbox/manifest.json`; the frozen split manifest. Cross-tree pairs: `MAIN/level4_stepB/` with its dev-worktree copy, and `MAIN/level4_blind_runtime/` with its copy, each exempting only the P0.8 wrappers by relative path. Gate scripts are not in the module pin. The tool manifest attested at `g3b_open` governs them, so a committed fix to a gate script before `g3b_open` does not stop the gate, and a fix after it carries `POST-INSPECTION-TOOLING`. The writer refuses an empty pin as `MODULE_PIN_EMPTY`, never overwrites (`MODULE_PIN_EXISTS_REFUSING_OVERWRITE`), and refuses as `MODULE_TREE_MISMATCH` when a cross-tree pair differs.
4. Commit both files exactly once with `git add -f`. `verify_module_pin()` must return `MODULE_PIN_VERIFIED`. From then on every `GateGuard` construction re-verifies this set, and every read re-hashes a listed file. A changed file (`MODULE_ARTIFACT_DRIFT`), a new or removed file under a pinned root (`MODULE_SCOPE_CHANGED`) and a divergence inside a cross-tree pair (`MODULE_TREE_MISMATCH`) each stop the gate as `GATE_STOPPED_PROVENANCE_FAILURE`, even when the change would apply equally to both conditions. At G3a, `gate_import_closure.py` resolves K's import closure from the pinned source; any module K imports from a mutable checkout outside the pinned roots emits `MODULE_CLOSURE_OUTSIDE_PIN` and stops the gate as a provenance failure.
5. Cross-tree identity. Both trees must hold the same file set under `level4_blind_runtime/` and under `level4_stepB/`, with identical sha256 for every file, apart from the declared P0.8 wrappers. A file present in only one tree is divergence. Divergence emits `PIN2-DIVERGENT-COPIES` and halts. This check exists because gate processes import the dev-worktree copies while the freeze pin covers the main checkout's.
6. Record the environment capture `stepB_run_env.json` by hash.
7. Record by `GateGuard.hash_only` the digest of `level4_stepB_output_hash.txt` in `g2_record.json`. Its content is first read at G3b, where it is compared with the value `gate_output_hash_recompute.py` computes from the pinned bytes (SA-15). A mismatch emits `PIN_OUTPUT_HASH_MISMATCH` and stops the gate as a provenance failure.

**Fixed now.** The artifact defining `K_L4*` is `level4_baseline_admissibility_v2.json`. The manifest cites the earlier file, and that citation is superseded by this sentence. The Lockbox manifest is resolved against MAIN. An absent file emits `PIN2-ARTIFACT-ABSENT`, never a null pin.

**Output artifact.** `stepB_gate_module_pin.json`, `stepB_gate_module_pin_hash.txt`, `g2_record.json`.

**Closed outcome vocabulary.** `PIN2-OK`, `PIN2-INCOMPLETE`, `PIN2-DIVERGENT-COPIES`, `PIN2-TOOL-MISSING`, `PIN2-ARTIFACT-ABSENT`, `MODULE_PIN_VERIFIED`, `MODULE_PIN_MISSING`, `MODULE_PIN_ALTERED`, `MODULE_ARTIFACT_MISSING`, `MODULE_ARTIFACT_DRIFT`, `MODULE_PIN_WRITTEN`, `MODULE_PIN_EXISTS_REFUSING_OVERWRITE`, `MODULE_PIN_EMPTY`, `MODULE_SCOPE_CHANGED`, `MODULE_TREE_MISMATCH`.

**Refusal conditions.** Any required record absent; any cross-tree divergence; the Lockbox manifest or the admissibility artifact absent; a module pin that does not verify.

**Claim licensed.** Every object the gate will reason about, including everything that defines K, is fixed, identified, and committed exactly once with one distinct blob across all refs and the reflog. The freeze pin is also bound to its commit and anchored.

**Claim NOT licensed.** Anything about content.

---

### G3. Only then inspect the retained productions

G3 has two ordered parts at stage 3, and `GateGuard` enforces their order. Frozen design source and pre-run records unlock at stage 3. Step-B outputs unlock only once the event `g3b_open` is valid (section 6), and that event requires the final tool manifest and `g3a_record.json` to be committed first. No G3a script can therefore read a Step-B output, and a manifest committed early unlocks nothing.

#### G3a. Candidate-independent preparation, before any Step-B output can be read

**Entry condition.** `PIN2-OK` and `MODULE_PIN_VERIFIED`. `GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)` constructs, which requires both pins to verify with their commit bindings and the anchor.

**Procedure.**

1. Resolve every implementation assumption (3.3 item 3) by name in the hash-verified pinned source, and resolve SA-15.
2. Run `gate_import_closure.py`. A module K imports from a mutable checkout outside the module pin's roots emits `MODULE_CLOSURE_OUTSIDE_PIN`.
3. Run the candidate-independent substrate predicates and the additivity preflight on synthetic fixtures (sections 7 and 11), including the negative control of 7.4, against exactly the files in the module pin. Commit `substrate_ledger_pre.json`.
4. Run P0.3 and commit the regression set.
5. Generate the criterion-5 suite (6.G7-C5) over the pinned source's type grammar: one suite for every signature shape the grammar admits up to arity 3 and type depth 2, each with its stress list, from `CE_SEED`. Commit `c5_suite.json`. At G7a each candidate selects its suite from this file by declared signature and recorded family. Nothing in the suite is generated after `g3b_open`.
6. Run the positive-control fixtures for every guard (DR-25), including the audit hook of P0.15.
7. Verify the protocol binding: this document's blob hashes to the value in the final tool manifest. Commit the tool manifest, then `g3a_record.json`. Write the event `g3b_open` and commit it. That commit unlocks Step-B outputs.

**Output artifact.** `substrate_ledger_pre.json`, `regression_set.json`, `c5_suite.json`, `guard_controls.json`, `gate_tool_manifest.json`, `g3a_record.json`, `event_g3b_open.json`.

**Closed outcome vocabulary.** `G3A-COMPLETE`, `SCHEMA_ASSUMPTION_FAILED` with category `IMPL`, `OUTPUT_HASH_FORMULA_UNRECOVERABLE`, `MODULE_CLOSURE_OUTSIDE_PIN`, `ADDITIVITY_PREFLIGHT_PASS`, `ADDITIVE_INSTALL_PATH_UNAVAILABLE`, `ADDITIVITY_PREFLIGHT_CONTROL_FAILED`, `GUARD-CONTROL-FAILED`, `PROTOCOL_BINDING_MISMATCH`, `REFUSE-REGRESSION-SET-TOO-SMALL`, `EVENT_WRITTEN`, `EVENT_REQUIREMENT_NOT_COMMITTED`, `EVENT_ARTIFACT_NOT_COMMITTED`, `GATE_STOPPED_PROVENANCE_FAILURE`. Routing: `MODULE_CLOSURE_OUTSIDE_PIN` stops the gate as `GATE_STOPPED_PROVENANCE_FAILURE`. `ADDITIVITY_PREFLIGHT_CONTROL_FAILED`, `GUARD-CONTROL-FAILED`, `PROTOCOL_BINDING_MISMATCH` and `SCHEMA_ASSUMPTION_FAILED` stop the gate as `TERM-HALTED` with that code as reason (14.1). `ADDITIVE_INSTALL_PATH_UNAVAILABLE` is a per-substrate result, not a halt.

**Refusal conditions.** Either pin not verified; a guard positive control that does not fire; the negative control of 7.4 classified additive; the protocol blob not matching the tool manifest; `g3b_open` attempted before every G3a step has committed its artifact; the audit hook of P0.15 absent or its control not firing.

**Claim licensed.** The fixtures, controls, regression set, criterion-5 suite and tool manifest were frozen before any Step-B output could be read. The substrate predicates and the additivity preflight have the recorded outcomes on synthetic fixtures.

**Claim NOT licensed.** Anything about Step-B outputs; any substrate property on a real task; additivity for any real candidate.

#### G3b. The access-ledger opening, after `g3b_open`

**Entry condition.** `g3b_open` is valid. `GateGuard(Stage.INSPECT_RETAINED_PRODUCTIONS)` constructs.

**Procedure.**

1. Open `gate_access_ledger.jsonl`, append-only, and record the opening event. Every gate script from here on installs an `open()` audit hook that appends every content-bearing read. A claim that depends on a file absent from the ledger is void.
2. Run `gate_output_hash_recompute.py` before any other Step-B output is read. It compares the value recomputed from the pinned bytes with `level4_stepB_output_hash.txt` and with the hash the runner printed beside `STEP B FROZEN` in the pinned run log, and all three must agree. A mismatch emits `PIN_OUTPUT_HASH_MISMATCH` and stops the gate as a provenance failure. A match establishes consistency among the pinned outputs, the hash file and the run log. It does not exclude an edit that rewrote all three consistently before the pin. Under SA-15 "not recoverable", it records `OUTPUT_HASH_FORMULA_UNRECOVERABLE` and the gate continues with the marker-to-pin window unclosed.
3. Run the schema-assumption checker over SA-01 to SA-10, reading only through `GateGuard`. Record which branch holds for SA-04, SA-08 and SA-09.
4. Record `N_retained` (classes with non-empty `kept_for`), the total class count, counts by lane, and the count with `kept_for` empty, BEFORE any per-class field is analysed.
5. Copy into `retained_classes.json` every retained class with the fields of SA-01 to SA-04 and its resolution rows.
6. Call `reverify()` at the end of the session.

**Retention rule.** The retained set is exactly the classes with non-empty `kept_for`. The gate never adds, drops, merges or re-ranks classes. Every later table has `N_retained` rows.

**Processing order.** The frozen order the runner already writes, `(-len(kept_for), -len(proposed_from), mdl, class_id)`. No candidate is reordered because of what it turns out to be.

**Output artifact.** `gate_access_ledger.jsonl`, `output_hash_check.json`, `schema_assumptions.json`, `retained_classes.json`.

**Closed outcome vocabulary.** `INSPECT-OPENED`, `INSPECT-OUT-OF-ORDER`, `OUTPUT_HASH_CHECK_PASS`, `OUTPUT_HASH_FORMULA_UNRECOVERABLE`, `PIN_OUTPUT_HASH_MISMATCH`, `SCHEMA_ASSUMPTION_FAILED`, `GATE_STOPPED_PROVENANCE_FAILURE`. Routing: `PIN_OUTPUT_HASH_MISMATCH` stops the gate as `GATE_STOPPED_PROVENANCE_FAILURE`. `SCHEMA_ASSUMPTION_FAILED` stops the gate as `TERM-HALTED`. `N_retained == 0` sets `TERM-NO-CANDIDATE`. All retained classes in lane K1 sets `TERM-ONLY-K1-REPAIRS`.

**Refusal conditions.** `g3b_open` not valid; either pin not verified; the ledger not writable and committable.

**Claim licensed.** An enumeration of retained classes and counts, with the schema branches and the output-hash check recorded.

**Claim NOT licensed.** Any interpretation of any class.

---

### G4. Per-candidate determination: interface, sources, semantics, separation

**Entry condition.** G3 complete with no halt. `GateGuard(Stage.CHARACTERIZE_CANDIDATES)` constructs.

**Procedure.** For each retained class, every determination below is recorded, even when an earlier one already disqualifies the class. The object under test, `e`, is the class representative with no substitution at any later stage. If the representative fails a leg and another member would pass, the class fails.

- **G4.1 Typed interface.** Signature, arity, ordered argument roles with declared type expression and evaluation mode (port, terminal, induced), result-type rule, declared type variables. Codes `IFACE-OK`, `IFACE-MISSING`.
- **G4.2 Proposing source set.** Record `proposed_from`, `kept_for`, per-cluster `certified_sources`, and `independent_source_tokens` under its true meaning (SA-04 branch). Criterion-1 evidence is `kept_for` non-empty with `len(certified_sources) >= 2` in at least one cluster. `independent_source_tokens` counts sources that proposed, not sources that certified. No task identity is resolved here. Codes `SRC-OK`, `SRC-UNDER-THRESHOLD`.
- **G4.3 Exact executable semantics.** The schema's canonical serialization, its full elaboration, and for EVERY inventory instance in the representative's schema a record `{instance_name, schema_id, family, function, source_sha256}`. Verify each `source_sha256` against the pinned source before any execution. Codes `SEM-OK`, `SEM-DRIFT`, `SEM-SOURCE-MISSING`.
- **G4.4 Induction surface.** Every slot type of `e` that resolves through a terminal table or induced-type table added by the install path, as read from the pinned source, with the learner name. An extension carrying such a slot extends the language AND its induction machinery, and this gate does not separate the two contributions. Every report at L2 and above carries that sentence verbatim. Codes `IND-SURFACE-RECORDED`, `IND-SURFACE-EMPTY`.
- **G4.5 Lane audit.** Compute each lane's vocabulary from `FROZEN_BASE`, the registry captured before any install, not from the live registry. The Step-B workers enter the install context before proposal and never exit it, so the live registry is not a sound reference. Assert that a K1 schema references no inventory instance and that a K2 schema references only its lane vocabulary. Codes `LANE-OK`, `LANE-VOCAB-MISMATCH`.
- **G4.6 Class heterogeneity.** Recompute three-valued behaviour (12.4) for every member. Disagreement records `CLASS-HETEROGENEOUS` with member ids. The class is not re-split. All evidence from G6 onward attaches to the representative only, and the report says so.
- **G4.7 Separation.** Section 12 in full, including the constructor pre-pass.

**Output artifact.** `candidate_dossiers.jsonl`, `constructor_prepass.json`, `separation_certificates.jsonl`.

**Closed outcome vocabulary.** The G4 codes above and the separation codes of 12.9. Terminal routing: if every retained K2 class ends at `SEP-EQUIVALENT`, `SEP-MACRO-OVER-CONCEPT`, `SEP-DEFINEDNESS-ONLY`, `SEP-TOTALIZATION-ONLY` or `MACRO-OVER-K-L4STAR-STRUCTURAL`, and no structural cap rests on a `CONSTRUCTOR-UNDECIDED` instance, the terminal code is `TERM-ALL-EQUIVALENT`. If no uncapped K2 class is `SEP-SEPARATED`, and at least one class ends in `SEP-VACUOUS`, `SEP-ERROR` or an inconclusive separation code, or carries a cap resting on a `CONSTRUCTOR-UNDECIDED` instance, the terminal code is `TERM-INCONCLUSIVE-G4`.

**Refusal conditions.** `SEM-DRIFT`, `LANE-VOCAB-MISMATCH` and `SRC-UNDER-THRESHOLD`, which contradicts retention, stop the gate as `TERM-HALTED` with that code as reason. The integrity investigation is recorded, and the gate does not resume.

**Claim licensed.** Per class: typed interface, proposing sources, exact semantics, induction surface, and a bounded separation code at level `BOUNDED_ENUMERATION`.

**Claim NOT licensed.** Any usefulness claim; any rung above L1.

---

### G5. Keep the four levels distinct

**Entry condition.** Every retained class carries a dossier and a separation code.

**Procedure.** Run `gate_rung.py` with signature

```
assign(lane, signature, behaviour_fingerprint, structural_result,
       separation_result, witness_evidence) -> rung
```

It receives no label argument. At G5 `witness_evidence` is empty, so the highest assignable rung is L1. Each row records class id, lane, `generation_lane_label`, certified-source counts, structural code, separation code, rung, the first failed or pending predicate, and `NEXT-PREDICATE-PENDING-G6` where L2 awaits G6. A class with a required code missing is `RUNG-UNASSIGNABLE`, which is a gate defect and stops the gate as `TERM-HALTED`.

The report contains, verbatim, adjacent to the first table in which the label appears:

> `NEW_SEMANTIC_PRODUCTION` is the generation-lane label fixed at proposal time. It establishes nothing about novelty. Novelty is established only by the structural pre-pass and the separation certificate at rung L3, and capability only by the six-leg witness.

**Output artifact.** `ladder_assignment_g5.json`.

**Closed outcome vocabulary.** `RUNG-L1`, `RUNG-K1-REPAIR`, `RUNG-BELOW-L1`, `RUNG-UNASSIGNABLE`, `NEXT-PREDICATE-PENDING-G6`.

**Refusal conditions.** Any missing upstream code.

**Claim licensed.** The rung held on evidence through G4, with the label and the separation code shown side by side.

**Claim NOT licensed.** Any rung above L1; promotion; admission.

---

### G6. The capability-growth witness on the pre-transfer pool

**Entry condition.** G5 complete. The substrate decision of section 11 is complete for each K2 class, and its ledger `substrate_ledger.json` is committed before any witness run. `GateGuard(Stage.CAPABILITY_GROWTH_WITNESS)` constructs.

**Procedure.**

1. **Pool.** For each retained K2 class, the pre-transfer tasks are every source token appearing in any resolution row attributed to the class (SA-03), in the frozen order. No row is dropped. Demonstrations come from the pinned invention corpus by token.
2. **Target dependence.** Every pre-transfer task is in `e`'s proposing source set by token identity, so `e` is target-dependent for it (section 9).
3. **Reproduction control.** Recompute Step B's `found`, `uses_candidate` and program-level fold verdict for each class and certified source under the pinned gate configuration. Record the fold verdict only as `DIAG_PROGRAM_LEVEL_LOO`, which enters no conjunction, admission rule or claim. Report agreements and disagreements as counts. A disagreement where either execution was incomplete is `REPRO-DIFFERS-INCOMPLETE`, a timing artifact that does not block. A disagreement where both executions were complete is `WITNESS-NONREPRODUCIBLE-CERTIFICATION` and blocks admission for that class.
4. **Degeneracy pre-check.** Verify that `e` is present in K_PLUS_E, reachable at the goal type, and changes at least one enumerated program at depth 1. Verify that K_PLUS_E's accepted-program set is not byte-identical to K's across all pre-transfer tasks. Failure is `WITNESS-DEGENERATE-TREATMENT-EQUALS-CONTROL` and the class is not admitted. The check is recorded whether or not it fires.
5. **Six legs.** Section 8 in full, `pool = PRE_TRANSFER`, for every (class, task) pair, every leg evaluated regardless of earlier legs.
6. **T on this pool.** Decided per 8.4.
7. **L on this pool.** Decided per section 9. The task is target-dependent, so L needs the adaptive proposal driver. Without it, L is `NOT_MEASURED` with reason `FULL_ADAPTIVE_LOO_UNAVAILABLE`.

**Output artifact.** `substrate_ledger.json`, `witness_pre_transfer.jsonl` (one evidence object per leg per pair), `witness_pre_transfer_summary.json`, `g6_record.json`.

**Closed outcome vocabulary.** Leg statuses of 8.2. Pair verdicts `CAPABILITY-GROWTH-WITNESS`, `WITNESS-REFUTED`, `WITNESS-INCONCLUSIVE`. Plus `REPRO-DIFFERS-INCOMPLETE`, `WITNESS-NONREPRODUCIBLE-CERTIFICATION`, `WITNESS-DEGENERATE-TREATMENT-EQUALS-CONTROL`, `WITNESS-VOID-NONDETERMINISM`, `WITNESS-ARM-DISAGREE-TIMING`, `WITNESS-ARM-DISAGREE-STRUCTURAL`, `WITNESS_SUBSTRATE_INCOMPLETE`, `WITNESS-RECORD-INVALID`, `DEPTH_COMPRESSION_ONLY`, `DEPTH_COMPRESSION_UNDECIDED`.

**Refusal conditions.** No committed substrate ledger; `WITNESS-ARM-DISAGREE-STRUCTURAL` halts the gate as `TERM-HALTED`; a leg record missing any field makes the pair `WITNESS-RECORD-INVALID` (8.3 rule 1).

**Claim licensed.** Per pair, the six leg statuses at their stated levels. A pre-transfer pair is never tagged `HELD_OUT_OUTPUT` unless T was measured under 8.4 branch 1.

**Claim NOT licensed.** Held-out transfer; L4; any conclusion from a leg that is not `PASS`. Honest statement: a kept class already met Step B's selection rule on some of these tasks, so G6's independent content is the additive-condition B and A results under the raised budget, the reproduction disagreement count, the degeneracy check, and any adaptive L results.

---

### G7. Only surviving, causally useful extensions proceed to E_transfer

G7 has two ordered parts at stage 7. The firewall, the Promotion extract and Promotion extraction unlock only once the event `g7b_open` is valid, which requires a non-empty committed admitted set, `g6_record.json` and `g7a_record.json`. The E_transfer extract unlocks only once `g8_open` is valid, at the end of G7b. E_transfer is spent from the commit of `g7b_open`.

#### G7a. Criteria and admission, before the firewall opens

**Entry condition.** G6 complete, with `g6_record.json` committed. `GateGuard(Stage.E_TRANSFER_EVALUATION)` constructs.

**Procedure.**

1. **Additivity on real tasks.** Run the check of 8.8 over every G6 execution. Violations and recoded statuses are written to `additivity_real_tasks.json`. Admission, rungs and criterion 3 read the recoded statuses from that artifact. The G6 artifacts are never rewritten.
2. **Rungs.** `gate_rung.py` runs on the statuses recoded by step 1 and writes `ladder_assignment_g7.json` with the final L2 and L3 rungs.
3. **Criterion 3, leg (a).** No regression on the pre-extension certified E_invent tasks of the regression set, run by token under condition K and condition K_PLUS_E. A task regresses if it was certified under K and is not certified under K_PLUS_E, with digests differing only in the extension field. Any regression is `CRIT3-FAIL`. An incomplete condition on any task is `CRIT3-INCONCLUSIVE`.
4. **Criterion 5.** Each candidate's suite is selected from the committed `c5_suite.json` by declared signature and recorded family (6.G7-C5). A signature shape absent from the suite records `CRIT5-INCONCLUSIVE` with reason `C5_SHAPE_NOT_IN_SUITE`.
5. **Admission.** Section 10.
6. **Freeze.** Write `etransfer_admitted_set.json` as `{"admitted": [class ids]}`, commit it, and verify it in the index. Commit `g7a_record.json`. If the set is non-empty, write the event `g7b_open` and commit it: that commit opens G7b and spends E_transfer. For an empty set `write_event` refuses with `EVENT_ADMITTED_SET_EMPTY`, E_transfer stays unopened and unspent, and 10.4 decides the terminal code.

**Output artifact.** `ladder_assignment_g7.json`, `additivity_real_tasks.json`, `criteria_g7a.json`, `etransfer_admitted_set.json`, `g7a_record.json`, `event_g7b_open.json`.

**Closed outcome vocabulary.** `ADMIT-OK`, `ADMIT-REFUSED-NOT-L3`, `ADMIT-REFUSED-LEGS`, `ADMIT-REFUSED-CRITERION`, `ADMIT-REFUSED-INTEGRITY`, `ADMIT-REFUSED-K1-LANE`, `ADMIT-REFUSED-NO-SUBSTRATE`, `ADDITIVITY_VIOLATED_ON_REAL_TASK`, `CRIT3-PASS`, `CRIT3-FAIL`, `CRIT3-INCONCLUSIVE`, `CRIT5-PASS`, `CRIT5-FAIL`, `CRIT5-INCONCLUSIVE`, `DEGENERATE-SLOTS`, `REFUSE-REGRESSION-SET-TOO-SMALL`, `EVENT_WRITTEN`, `EVENT_ADMITTED_SET_EMPTY`, `XFER-NOT-OPENED`. Routing: an empty admitted set routes by 10.4.

**Refusal conditions.** A regression set smaller than `CRIT3_MIN_TASKS` refuses with `REFUSE-REGRESSION-SET-TOO-SMALL`, and the set size is printed beside every criterion-3 result. `g7b_open` is never written for an empty admitted set, and there is no exploratory peek, sanity check or single-candidate exception.

**Claim licensed.** Which extensions met the admission rule before the firewall opened. Admission is not a witness.

**Claim NOT licensed.** Any capability-growth claim; anything about provenance, Promotion or E_transfer.

#### G7b. Provenance, criterion 4, criterion 3 leg (b), withdrawals

**Entry condition.** `g7b_open` is valid. `GateGuard(Stage.E_TRANSFER_EVALUATION)` constructs.

**Procedure.**

1. **Schema checks at first licensed access.** Check SA-11 on the firewall, SA-12 on the Lockbox manifest and SA-13 on the training challenges and solutions files, before any value is used.
2. **Provenance resolution.** Resolve `source_token_to_task` for the admitted extensions. Invention provenance of a class is the union of proposing sources over all members, resolved to task ids. This is the broadest available set, so the exclusion is conservative. Under SA-04 "count", identities come from the resolution rows via `cluster_id`, which gives a superset, and the artifact says so. `certified_sources` is reported and never used for exclusion.
3. **Criterion 4.** Run the executable leak check over the class's canonical serialization and the source text of every instance in it, against the forbidden-name pool. It returns a boolean and a count without disclosing the pool.
4. **Criterion 3, leg (b).** No regression on the Promotion tasks certified in the Level-3A confirmatory run. `gate_extract_splits.py` resolves the Promotion ids from the Lockbox manifest with `GateGuard.extract` and the key path of SA-12, then writes `extracts/promotion_tasks.json` from the training challenges and training solutions files with `GateGuard.extract` and those ids. Unlicensed members are never decoded; their count is ledgered. No gate stage reads a raw ARC data file in any other way.
5. **Withdrawal only.** An extension with criterion 4 or criterion 3 leg (b) not `PASS` is withdrawn with code `ADMIT-WITHDRAWN-POST-FREEZE-CRITERION`. Withdrawal can only shrink the set. No extension is added after the freeze, and none is withdrawn for any other reason.
6. **Split.** Resolve the E_transfer task list from `within_stage_holdout.E_transfer` and record the resolved count in `etransfer_task_list.json`. E_transfer task contents are not extracted here.
7. **Close G7b.** Commit `etransfer_withdrawals.json` as `{"withdrawn": [class ids]}`, then `g7b_record.json`. If any admitted extension remains, write the event `g8_open` and commit it. If none remains, `write_event` refuses with `EVENT_ADMITTED_SET_EMPTY`, no E_transfer extract is ever written, and E_transfer is recorded as spent and not measured.

**Output artifact.** `schema_assumptions_g7b.json`, `criteria_g7b.json`, `extracts/promotion_tasks.json`, `etransfer_withdrawals.json`, `etransfer_task_list.json`, `g7b_record.json`, `event_g8_open.json`.

**Closed outcome vocabulary.** `SCHEMA_ASSUMPTION_FAILED`, `CRIT4-PASS`, `CRIT4-FAIL`, `CRIT3-PASS`, `CRIT3-FAIL`, `CRIT3-INCONCLUSIVE`, `ADMIT-WITHDRAWN-POST-FREEZE-CRITERION`, `EVENT_WRITTEN`, `EVENT_ADMITTED_SET_EMPTY`. Routing: `SCHEMA_ASSUMPTION_FAILED` stops the gate as `TERM-HALTED`. Every admitted extension withdrawn gives `TERM-ALL-WITHDRAWN` (10.4).

**Refusal conditions.** `g7b_open` not valid; a failed schema check; a withdrawal for any reason other than criterion 4 or criterion 3 leg (b); any addition after the freeze.

**Claim licensed.** The provenance of each admitted extension, its criterion 4 and criterion 3 leg (b) results, and which extensions are licensed for measurement on E_transfer.

**Claim NOT licensed.** Any capability-growth claim; any E_transfer outcome; mining Promotion; opening Lockbox.

**6.G7-C5, criterion 5.** The suite is generated at G3a step 5 by the frozen witness generator with `CE_SEED = 828282` plus a declared stress list, over the pinned source's type grammar, before any Step-B output can be read. Each candidate selects its suite by declared type signature and recorded family, so every candidate with the same signature shape meets the identical suite. Stress list: empty cellset; 1x1 grid; maximum-side grid within the pinned generator bounds; full-alphabet grid; duplicate map keys; out-of-range index; mismatched shape pair.

| Sub-test | Pass condition |
|---|---|
| C5.1 robustness | no uncaught exception escapes runtime containment on a typed-valid input |
| C5.2 determinism | executions under `PYTHONHASHSEED` 0 and 1 give identical canonical output |
| C5.3 slot degeneracy | if fitted slots take one value on every task where `e` was used, re-run separation with the slots frozen to that constant; failure drops the rung to L2 and refuses admission |
| C5.4 result type | every output is a value of the declared result type or `None` |
| C5.5 family property | by recorded family: select, result is a sub-collection and reapplication is idempotent; project, result kind equals declared target kind; reindex, cardinality preserved; aggregate, permutation invariance; combine, defined on both orders where the declared type is symmetric; embed, recoverable by a declared projection where one exists; reduce, declared target kind and deterministic |

`NOT-APPLICABLE` is justified by recorded family and declared type only, never by observed behaviour.

---

### G8. The frozen E_transfer evaluation

**Entry condition.** The event `g8_open` is valid, which requires an admitted set that is non-empty after withdrawals. `gate_etransfer_runner.py` is written, unit-tested on synthetic fixtures, and hashed in the tool manifest attested by `g3b_open`. A runner not in that manifest is refused, with one exception: the crash re-run of the single-pass rule. `GateGuard(Stage.E_TRANSFER_MEASUREMENT)` constructs.

**Procedure.**

1. Load the task list committed at G7b. The extraction step (15.3) writes `extracts/etransfer_tasks.json` through `GateGuard.extract`, holding only the resolved E_transfer tasks: test inputs from the training challenges file and reference outputs from the training solutions file. SA-14 is checked here by key presence. `GateGuard` refuses the extract and the extraction until `g8_open` is committed, and for good once `g8_closed` is committed.
2. **De-collision by identity and content hash only.** An E_transfer task whose id is in the extension's invention provenance is excluded with `XFER-SKIP-IDENTITY`, and the identity is recorded. A task whose demonstrations match a proposing source under the content hash of 9.2 is excluded with `XFER-SKIP-CONTENT-DUPLICATE`, and the hash is recorded. No exclusion is by outcome, cost, difficulty, runtime, family or apparent suitability. A task that errors or exhausts resources stays in the denominator with its status. Pool overlaps are reported, including zero counts.
3. **Target dependence.** After both de-collisions, `e` is fixed cross-task knowledge for every remaining task (section 9).
4. **Conditions.** Per task per extension, on the selected substrate: condition K (the run feeding B), condition K_PLUS_E (feeding U, L, T), and an independent re-execution of condition K as the ablation (feeding A). `GATE_REPEATS = 3`, `ARC_META_BUDGET_S = 64.0`, single process, threads pinned.
5. **T.** Every test pair of the task with a licensed reference is used; T `PASS` requires exact equality on every one. A task with no licensed reference records T `NOT_MEASURED`, reason `T_NO_LICENSED_REFERENCE`. T is judged on the single accepted program in one attempt, and B, T and A are scored on the identical set of test inputs. References are read only from the E_transfer extract.
6. Run the additivity check of 8.8 over the G8 executions. Then compute the primary and the five secondaries from the recoded statuses.
7. Append one line to `etransfer_ledger.jsonl` per execution: timestamp, operator, script hash, admitted-set hash, config digest, runtime-state digest, conditions run, task count, exit code, and the sha256 of the teed stdout file, recorded at process start. When the single pass ends, commit the ledger, then write and commit `g8_closed`.

**Primary endpoint, declared before the split opens.**

```
N_w = the number of (extension, task) pairs on E_transfer, task outside the
      extension's invention provenance by identity and content hash, whose six legs are all
      PASS with pool = E_TRANSFER.

N_w >= 1                                              -> C6-PASS
N_w == 0, and every pair has a leg FAIL with a
         complete evidence object                     -> C6-FAIL, TERM-NO-TRANSFER
N_w == 0, and any pair is WITNESS-INCONCLUSIVE        -> C6-INCONCLUSIVE, TERM-INCONCLUSIVE-G8
```

This is criterion 6, operationalised in advance as the six-leg conjunction. The manifest's own wording is "it transfers to at least one task outside its invention provenance". The tightening is declared, not inherited.

**Five preregistered secondary measurements.** Descriptive only. None can be promoted to primary.

| Id | Measurement | Mechanical definition |
|---|---|---|
| M1 | source-independent reuse | count of tasks outside provenance whose K_PLUS_E accepted program uses `e` per the substrate's use trace |
| M2 | rediscovery | count of tasks with L `PASS`, plus per-task folds passed over folds attempted, plus per-fold counts of fold programs using `e` |
| M3 | correct held-out outputs | count of tasks with exact test-output equality, reported for K, K_PLUS_E and the ablation together |
| M4 | search and compute change | paired per-task deltas, K_PLUS_E minus K; primary resource typed candidates enumerated; secondary wall seconds and surface cost |
| M5 | dependence on the extension | count of K_PLUS_E M3 successes lost in the ablation, same tasks, same seeds, same budget |

Every measurement is reported with its denominator, the counts of each non-`PASS` status, and the number of identity exclusions. Every M4 number is labelled `MEASURED-RETROSPECTIVE`.

**Single pass.** E_transfer opens exactly once for the admitted set. A second execution is refused. If a run crashes with no per-task outcome written to disk and none displayed, adjudicated by the hash of the results file and the hash of the teed stdout, the fault is fixed, and one re-run is permitted. Before it runs, the fixed script's sha256 and the sha256 of its diff from the manifest version are committed in `etransfer_rerun_record.json`. The re-run is ledgered, and every E_transfer claim carries the stamp `XFER-CRASH-RERUN`. If any per-task outcome was written or displayed, a re-run is `XFER-SECOND-ACCESS`, and every downstream claim carries that stamp. E_transfer is spent from the commit of `g7b_open`, when the firewall first opens, whether or not G8 ever runs.

**No tuning.** After E_transfer opens nothing changes: no parameter, budget, depth, cap, cost, ranking rule, verifier, learner, extension definition or task selection. An observed failure never justifies a repair. If a gate implementation defect is found during the pass, the pass is voided and recorded as void, and the fix is committed. A restart is permitted only under the crash rule above. Any other restart is `XFER-SECOND-ACCESS`, and every artifact of the restarted pass carries `POST-INSPECTION-TOOLING`. Partial passes are never merged.

**No substitution.** If the primary fails, the report says so, and that sentence precedes any secondary number.

**Output artifact.** `extracts/etransfer_tasks.json`, `etransfer_results.jsonl` (evidence objects), `etransfer_summary.json`, `etransfer_ledger.jsonl`, `etransfer_stdout.log`, `ladder_assignment_g8.json`, `additivity_real_tasks_g8.json`, `event_g8_closed.json`.

**Closed outcome vocabulary.** `XFER-OPENED-ONCE`, `XFER-SECOND-ACCESS`, `XFER-CRASH-RERUN`, `XFER-SKIP-IDENTITY`, `XFER-SKIP-CONTENT-DUPLICATE`, `ADDITIVITY_VIOLATED_ON_REAL_TASK`, `XFER-POOL-COLLISION`, `XFER-PASS-VOID`, `C6-PASS`, `C6-FAIL`, `C6-INCONCLUSIVE`, `TUNING-BREACH`, leg statuses of 8.2, pair verdicts of 8.3, `RUNG-L4`.

**Refusal conditions.** `g8_open` not valid; `g8_closed` already committed; pin not verified; runner hash absent from the tool manifest attested by `g3b_open`, unless it is the one crash re-run recorded in a committed `etransfer_rerun_record.json`.

**Claim licensed.** Level `HELD_OUT_OUTPUT`: the primary `N_w` with denominator and status counts; L4 for extensions with at least one E_transfer witness.

**Claim NOT licensed.** Anything about the ARC evaluation set, Lockbox200, the 120 public tasks or the 1000-task census; the word "general"; any secondary number as a substitute for the primary.

---

### G9. Promote only according to the existing protocol

**Entry condition.** `C6-PASS` for at least one extension. `GateGuard(Stage.PROMOTION)` constructs.

**Procedure.** The promotion manifest is frozen first, with the promoting runner's own hash inside it. Only then does the runner examine a single decision. This copies the order in `scripts/cora_v21_freeze_promotion.py`, which exists because an earlier study froze the criteria but not the runner and lost a baseline leave-one-out that way.

An extension is adopted, giving `K_{t+1} = K_t union {e}`, only when all hold:

| Criterion | Text | Evidence |
|---|---|---|
| 1 | resolves the failures of at least two independent source tasks | L2 rung: B, P, U `PASS` on at least 2 distinct pre-transfer tokens |
| 2 | every one survives full leave-one-out by complete rediscovery under the unchanged verifier | L `PASS` under section 9 on the E_transfer witness task; on pre-transfer tasks L `PASS`, or `NOT_MEASURED` with `FULL_ADAPTIVE_LOO_UNAVAILABLE` recorded beside the criterion |
| 3 | no previously certified task regresses | `CRIT3-PASS`, both legs |
| 4 | semantics compact, no task id, family name or literal answer | `CRIT4-PASS` |
| 5 | survives synthetic counterexamples | `CRIT5-PASS` |
| 6 | transfers to at least one task outside its invention provenance | `C6-PASS` |
| additive | separation certificate | `SEP-SEPARATED`, not `MACRO-OVER-K-L4STAR-STRUCTURAL`, not `SEP-MACRO-OVER-CONCEPT` |

`level4_promotion_manifest.json` pins the G1 pin hash, the G2 module pin hash, this document's hash, the runner hash, the config and runtime-state digests, the environment block, the regression set hash, the counterexample suite hash, the substrate ledger hash, the admitted-set and withdrawal hashes, the sha256 of both extracts and of their extraction ledger entries (no raw ARC data file is hashed or read by this stage), the per-extension criterion table with every code, `unchanged_from_stepB` (verifier, bounds, cost table, ranking rule, slot learners, 3A and 3B definitions), `only_change` naming `K_t -> K_t + {e}`, `all_arms_symmetric`, and a `claim_limit` block containing verbatim:

> A 3B witness would show that the set of solutions REACHABLE UNDER THE FIXED BUDGET grew. It would NOT show that the language can denote anything new, because the concept expands into K.

> Separation is established on a bounded frozen witness domain under the declared enumeration bounds. Global non-definability is not proved and is not claimed.

It also forbids by name the words untouched, pristine, fully prospective and lockbox validation.

Frozen interpretations: zero witnesses means accept the null, with no repair and no rerun; Lockbox stays closed regardless of the outcome; any inconclusive criterion refuses promotion and is not a refutation.

The registry update is append-only and versioned. `K_t` is kept verbatim. Promotion never edits, renames, retypes or re-costs an existing production, and never changes the verifier, `MAX_DEPTH`, `PER_TYPE_CAP`, `MAX_CANDIDATES`, the budget, the cost table or the ranking rule. Any such change emits `PROMOTION-VOID` and ends the gate.

**Output artifact.** `level4_promotion_manifest.json`, `promotion_record.json`, `knowledge_state_K_t1.json`.

**Closed outcome vocabulary.** `PROMOTED`, `NOT-PROMOTED-CRITERION`, `NOT-PROMOTED-INCONCLUSIVE`, `PROMOTION-VOID`.

**Refusal conditions.** Any criterion not `PASS`, apart from the declared structural note on criterion 2 for pre-transfer tasks. There is no provisional, conditional, investigative or engineering-convenience promotion.

**Claim licensed.** `K_{t+1}` is recorded with provenance and hashes.

**Claim NOT licensed.** That the system now solves more; any rung change.

---

### G10. Rediscovery, automatic abstraction, K versus K plus C, ablation

**Entry condition.** At least one `PROMOTED` extension. `GateGuard(Stage.POST_PROMOTION_ANALYSIS)` constructs.

**Procedure.**

1. **Harness differential.** `gate_level3_rerun.py` reuses the three-arm structure of `scripts/cora_v21_phase5.py`. Before any use on an extension, it must reproduce the frozen `concept_0001` 3A result exactly, arm for arm and witness for witness, on the substrate that produced it, `geocat_arc.object_reasoning.meta_v21`. It runs only on the Promotion extract, the pool of that 3A result. If the frozen 3A result used any task outside the Promotion extract, step 1 records `NOT_MEASURED` with reason `NO_LICENSED_3A_POOL`, and steps 2 and 5 are `NOT_MEASURED` with the same reason. It cannot do so on the blind runtime, whose baseline is a strictly smaller language. The blind-runtime port is validated separately by the existing interpreter-equivalence artifact. `scripts/cora_level3_transfer.py` is superseded because it imports the older `meta_induction` stack. `CORA_POST_STEPB_ROADMAP.md` line 46 names it, and that reference is corrected here.
2. **Additivity on the G10 substrate.** The three-arm comparison is admissible for 3B only if its substrate passed the additivity preflight. Otherwise 3B is `NOT_MEASURED` with reason `ADDITIVE_INSTALL_PATH_UNAVAILABLE`, and every 3A number carries the preflight status in the same row.
3. **Ordinary rediscovery.** Re-run unguided discovery under `K_{t+1}` with the same budget and verifier over two licensed pools, reported separately: the pre-transfer pool of G6, licensed since G3b, and the Promotion extract, evaluated and never mined. No Experience-family extract is licensed in this gate, and no stage reads a raw ARC data file for Experience tasks. Report new, lost and unchanged certified solves under `K_t` and `K_{t+1}` together. Lost solves are reported as prominently as gains and never folded into a net figure.
4. **Automatic abstraction.** Run the existing anti-unifier over programs newly certified on the pre-transfer pool. Programs certified on Promotion tasks are never an input to abstraction (15.4 rule 2). Reject any concept whose provenance is not two or more independent certified discoveries. Report proposed and rejected counts. A concept written or edited by a person is a protocol breach. If nothing is produced, that is the result.
5. **K versus K plus C, and ablation**, on the Promotion extract, whose tasks lie outside provenance, evaluated and never mined. 3A and 3B are evaluated and reported separately, with criteria copied verbatim from the frozen manifest:

```
3A_efficiency:
  task outside concept provenance
  both arms solve
  treatment winning SURFACE program contains the concept
  both arms pass leave-one-out by complete rediscovery
  treatment test prediction exactly correct
  treatment reduces a preregistered resource: typed candidates, seconds, or surface cost

3B_capability:
  task outside concept provenance
  K fails
  K + concept solves
  concept explicitly present in the winning surface program
  leave-one-out by complete rediscovery passes
  test prediction exactly correct
  ablation returns to failure
```

The preregistered 3A resource is typed candidates enumerated. Wall seconds and surface cost are secondary. A 3A witness on seconds alone is not a 3A witness. A 3B witness is scored under the six-leg discipline, the completeness predicate, the additive comparison rule and section 9. 3A and 3B counts are never added, averaged or reported under one word such as transfer.

**Output artifact.** `level3_rerun.json`, `rediscovery.json`, `abstraction.json`.

**Closed outcome vocabulary.** `HARNESS-DIFFERENTIAL-PASS`, `HARNESS-DIFFERENTIAL-FAIL`, `RD-NEW`, `RD-LOST`, `ABS-PROPOSED`, `ABS-REJECTED`, `3A-WITNESS`, `3A-NONE`, `3B-WITNESS`, `3B-NONE`, `MEASURE-INCONCLUSIVE`, `ADDITIVE_INSTALL_PATH_UNAVAILABLE`, `NO_LICENSED_3A_POOL`.

**Refusal conditions.** `HARNESS-DIFFERENTIAL-FAIL`.

**Claim licensed.** Level 3A and Level 3B results, separately, each with its letter and its frozen claim limit.

**Claim NOT licensed.** Any ARC score statement; a 3A result described as capability; a 3B result described as efficiency.

---

### G11. Lockbox200 stays closed until the entire gate is complete

**Entry condition.** Every prior stage has written its artifact, or the gate ended early with a recorded terminal code.

**Procedure.** G11 asserts closure. It opens nothing. The guard permits Lockbox-class reads in code only once the event `g11_complete` is committed, which follows the completion record, so no G11 process can read Lockbox content. That permission is an upper bound on what code allows, not a license. G11 checks, through the hash-only access path, that `MAIN/outputs/lockbox/manifest.json` hashes to the value pinned at G2. It checks that no gate artifact contains an unlicensed task id: every task-id-shaped token in a gate artifact must belong to the pre-transfer tokens resolved at G7b, the Promotion ids or the E_transfer ids. Any other is counted as `LOCKBOX-CHECK-UNRESOLVED-ID`. The Lockbox id list is never read. It checks that `tests/test_gate_isolation.py` and `tests/test_cora_parent_isolation.py` pass, with test counts recorded. It then checks the completion predicate:

1. every retained class carries a terminal rung code;
2. every executed stage has an artifact whose sha256 is in `gate_completion_record.json`;
3. exactly one terminal code is recorded;
4. `verify_pin(require_binding=True)` returns `PIN_VERIFIED`, anchor included, and `verify_module_pin()` returns `MODULE_PIN_VERIFIED`, at completion time;
5. the completion record is committed and verified in the index. Only then, and only if `lockbox_closure.json` records `LOCKBOX-ELIGIBLE`, is `g11_complete` written and committed. When the Lockbox stays closed, no event is written.

Lockbox eligibility requires the completion predicate AND at least one `RUNG-L4` AND `C6-PASS` AND no frozen criterion recording `FAIL` AND a declared system freeze with a hash. Otherwise Lockbox stays closed. Opening the Lockbox is not part of this gate. Under the Lockbox protocol it requires the system and the concept library to be declared frozen, then exactly one evaluation whose number is reported as is, with no second attempt, no post-hoc repair round and no re-freeze and rerun. The 120 public tasks are not run until after that single evaluation.

**Output artifact.** `lockbox_closure.json`, `gate_completion_record.json`, `capability_growth_gate_report.json` and `.md`.

**Closed outcome vocabulary.** `LOCKBOX-CLOSED`, `LOCKBOX-ELIGIBLE`, `LOCKBOX-BREACH`, `LOCKBOX-CHECK-UNRESOLVED-ID`, `EVENT_LOCKBOX_NOT_ELIGIBLE`.

**Refusal conditions.** Completion predicate false.

**Claim licensed.** The gate is complete, with its single terminal code, and Lockbox200 was not accessed.

**Claim NOT licensed.** Opening the Lockbox; any Lockbox result.

---

## 7. The additive comparison rule and the additivity preflight

### 7.1 The rule

For any capability-growth witness, the two conditions differ ONLY in the presence of `e`. Same ordinary solver, same search budget, same ordering outside the extension, same fitter, same verifier, same demonstrations, same timeout rules, same environment.

- **CONDITION K.** `e` is unavailable. `K = E_L4* = K_L4* + {concept_0001}`.
- **CONDITION K_PLUS_E.** `e` is available as an ADDITION.

K_PLUS_E must never suppress an ordinary K candidate because an extension candidate fits, and must never lose K candidates through enumeration caps. The comparison is never weakened to fit a substrate.

### 7.2 Declared construction on the blind runtime

| Condition | Environment |
|---|---|
| K | `LanguageEnv(base=FROZEN_BASE, concepts={"concept_0001": concept_0001})` |
| K_PLUS_E | `LanguageEnv(base=FROZEN_BASE, concepts={"concept_0001": concept_0001, e.name: e})` |
| ablation | `LanguageEnv(base=FROZEN_BASE, concepts={"concept_0001": concept_0001})`, constructed and executed independently |

`without_concepts()` is forbidden, because it would strip `concept_0001` as well as `e`. Before any condition runs, assert that `set(K_PLUS_E.names) - set(ablation.names) == {e.name}`, that `set(K.names) == set(ablation.names)`, and that no enumerated term in K or the ablation references a name outside `FROZEN_BASE union {concept_0001}`. All conditions run under the same install state, evaluator, budget, seeds and repeats, with runtime-state digests recorded per condition. This construction is a declaration of what is built. Whether it is additive is decided only by 7.3.

### 7.3 The additivity preflight

The preflight runs at G3a, before any witness run, on synthetic fixtures with a synthetic control production. It reads no Step-B output and runs no candidate. Fixtures are declared by class now and generated candidate-independently.

| Fixture class | Construction |
|---|---|
| F-A | K solves; the control production cannot fit |
| F-B | K does not solve; the control production fits |
| F-C | K solves; the control production also fits |
| F-D | the goal type is reachable by K only near `PER_TYPE_CAP` |
| F-E | two K programs agree on every demonstration and differ on the test input, and only one renders the reference |

Checks, all required:

1. **K stream preserved.** Every candidate K enumerates is enumerated in K_PLUS_E, in the same relative order outside the extension.
2. **Same program.** Every fixture that K solves (F-A, F-C, F-D where solved) is solved in K_PLUS_E by the same program.
3. **Cap saturation zero** in both conditions on every fixture.
4. **Fitting set retained.** On F-E, every condition retains both programs in its fitting set, deduplicated as 8.5 condition 5 declares.

A substrate whose frozen ranking or early stopping would return a different program on F-C fails check 2. The fixtures are not chosen to make any substrate pass.

### 7.4 Negative control

The `meta_induction` concept path of section 5 is run through the same preflight. It must be classified non-additive. If the preflight classifies it additive, the preflight is defective: `ADDITIVITY_PREFLIGHT_CONTROL_FAILED` halts the gate.

### 7.5 Outcomes

`ADDITIVITY_PREFLIGHT_PASS`; `ADDITIVE_INSTALL_PATH_UNAVAILABLE`, with reason `K_STREAM_NOT_PRESERVED`, `K_SOLVED_FIXTURE_CHANGED_PROGRAM`, `CAP_SATURATION_NONZERO` or `FITTING_SET_NOT_RETAINED`; `ADDITIVITY_PREFLIGHT_CONTROL_FAILED`.

If the substrate cannot satisfy the rule, the outcome is `ADDITIVE_INSTALL_PATH_UNAVAILABLE` for that substrate. A candidate-independent additive wrapper may be built before G2, shown behaviour-preserving for K on the frozen fixture set, and listed in the module pin. Nothing that affects K is created after G2. Anything built after G3b carries `POST-INSPECTION-TOOLING` for every Step-B extension permanently, under this or any later protocol, and cannot certify.

---

## 8. The capability-growth witness: six legs, evidence objects, statuses, verdict

### 8.1 Definition

```
W(e, t) = B and P and U and L and T and A
```

| Leg | Name | PASS condition |
|---|---|---|
| B | `baseline_K_fails` | condition K is COMPLETE (8.5) and does not reach `t` under the reach rule below |
| P | `production_proposed` | the pinned generation record shows `e` proposed by the declared mechanism: the class record exists in the verified pinned output with lane K2, non-empty proposing sources, and a canonical serialization equal to the installed `e`. Never a constant. |
| U | `winner_uses_production` | K_PLUS_E is COMPLETE, returned an accepted program, and the substrate's decidable use trace reports that the program uses `e` |
| L | `full_adaptive_LOO_passes` | section 9 |
| T | `final_output_correct` | the single accepted K_PLUS_E program, in one attempt, renders outputs equal to the licensed references exactly on every licensed held-out test input of `t` (8.4) |
| A | `ablation_without_e_fails` | an INDEPENDENT execution of condition K, constructed as in 7.2, is COMPLETE and does not reach `t` under the reach rule below |

**Accepted program.** K_PLUS_E enumerates to `MAX_DEPTH` with no early stop, exactly as B and A do, and retains every demonstration-fitting program. The accepted program is the first-ranked member of that fitting set under the frozen ranking rule. Its serialization sha256 is written into the evidence object before any test input or reference is loaded, and U, T and the 8.8 check read that pinned program only. The same definition applies at G6, G8 and G10.

**Input set.** B, T and A are scored on the identical set of licensed test inputs of `t`. No second attempt is made, and no attempt is selected afterwards.

**Reach rule for B and A.** The execution enumerates K's complete bounded program space for `t` to `MAX_DEPTH`, with no early stop at the first fit, and retains every program that fits every demonstration. That retained set is the fitting set.

1. The fitting set is empty. K cannot reach `t` even at demonstration-fit level. The leg is `PASS`, at level `DEMONSTRATION_FIT`.
2. The fitting set is non-empty and a licensed reference exists for `t`. For B and A a licensed reference means 8.4 branch 1 data on `PRE_TRANSFER` and the E_transfer extract on `E_TRANSFER`, and nothing else. If any program in the fitting set renders the reference exactly on every licensed test input, the leg is `FAIL`, with reason `K_SOLVED` when that program is K's accepted program and `K_REACHABLE_SELECTION_ONLY` otherwise. If none does, the leg is `PASS`, at level `HELD_OUT_OUTPUT`.
3. The fitting set is non-empty and no licensed reference exists in that sense, which includes every pre-transfer task under 8.4 branches 2 and 3. The leg is `INCONCLUSIVE`, reason `K_FITTING_PROGRAM_NO_REFERENCE`.

**Per-program exceptions and limits.** The tool manifest fixes, before `g3b_open`, the pinned evaluator's semantic domain errors, resolved at G3a as an implementation assumption. A program that raises a listed domain error while fitting a demonstration does not fit, and one that raises it while rendering a test input renders a wrong output; both are counted. Any other exception a program raises, and any per-program step or time limit it reaches, makes the leg `CHECKER_ERROR` or `RESOURCE_EXHAUSTED` respectively, identically in every condition, with the counts `program_exceptions` and `program_limit_hits` in the completeness block. A limit hit never counts as a program failing to render.

**Depth.** Every evidence object records `reach_bound = MAX_DEPTH` and `e_inlined_size`: the depth of `e`'s elaboration over `K_L4*` terms when every inventory instance in it carries `CONSTRUCTOR-DEFINABLE-IN-K-L4STAR`, and null otherwise. When it is not null, a diagnostic execution of condition K to depth `MAX_DEPTH + e_inlined_size - 1` runs on the same task. If that execution reaches `t` under the reach rule, the pair carries `DEPTH_COMPRESSION_ONLY`, reported beside its L2 reach claim. A diagnostic that exhausts its resources records `DEPTH_COMPRESSION_UNDECIDED`, reported the same way, and changes no rung. Because `e_inlined_size` is non-null only for classes the constructor pre-pass caps at L2, this diagnostic qualifies L2 claims only. Above L2 it is inert by construction, and every L3 or L4 claim lists it under `INERT-GUARD`. Depth compression beyond the bound for separated classes is a recorded limitation (19 item 1).

The reach rule exists because a task where K held a correct program but ranked a wrong one first is a selection effect. The evidence ladder records selection transfer as distinct from capability transfer, and judging B on K's first-ranked program alone would let a pure ranking effect pass all six legs. The count of pairs with reason `K_REACHABLE_SELECTION_ONLY` is reported as `DIAG_SELECTION_ONLY_COUNT`, which enters no conjunction, admission rule or claim.

The complete enumeration is harder to finish within the budget, so B and A reach `RESOURCE_EXHAUSTED` more often. That is the conservative direction.

B and A come from two separate process executions, never from one. `final_output_correct` and the ablation leg are NEW instrumentation. The audit verified that `test_output_correct` has never been populated anywhere in the tree and that `record_tti_ablation` has never had a production caller. Neither is assumed to work. Both are declared and not built (section 22).

### 8.2 Statuses

Each leg carries exactly one of `PASS`, `FAIL`, `INCONCLUSIVE`, `CHECKER_ERROR`, `RESOURCE_EXHAUSTED`, `NOT_MEASURED`. Only `PASS` counts toward the conjunction.

Mapping from v1 vocabulary, applied everywhere:

| v1 | v2 |
|---|---|
| `ERROR` | `CHECKER_ERROR` |
| `TIMEOUT`, cap saturation | `RESOURCE_EXHAUSTED` |
| `INCOMPLETE` | `INCONCLUSIVE`, with a reason code |

Rules:

1. An undefined program output (`None` with no exception) is a wrong answer and records `FAIL` for T. Only a raised exception records `CHECKER_ERROR`.
2. No missing field defaults to success. A record missing any leg, or any evidence field, is invalid and can never be a witness.
3. No `CHECKER_ERROR` counts as a failure of K or as evidence of necessity.
4. `NOT_MEASURED` always carries a reason code. Structural reason codes, the only ones permitted in admission: `FULL_ADAPTIVE_LOO_UNAVAILABLE`, `T_NO_LICENSED_REFERENCE_AT_STAGE`, `T_REFERENCE_NOT_HELD_OUT_FROM_MECHANISM`, `T_NO_LICENSED_REFERENCE`. Other reason codes: `USE_TRACE_UNDECIDABLE_K1_LANE`, `WITNESS_SUBSTRATE_INCOMPLETE`, `ADDITIVE_INSTALL_PATH_UNAVAILABLE`.

### 8.3 Verdict

The pair verdict is decided in this order, and the first rule that applies wins. A gate halt (14.1) leaves every undecided pair without a verdict.

1. A leg record missing any field, or an invalid evidence object, makes the pair `WITNESS-RECORD-INVALID`. It counts as `WITNESS-INCONCLUSIVE` everywhere, never as a witness or a refutation.
2. `WITNESS-VOID-NONDETERMINISM` (8.6), or `WITNESS-ARM-DISAGREE-TIMING` not resolved by its one re-run, gives `WITNESS-INCONCLUSIVE`.
3. `ADDITIVITY_VIOLATED_ON_REAL_TASK` (8.8) recodes every `PASS` leg on that substrate to `INCONCLUSIVE` before rules 4 to 6 apply. A recorded `FAIL` stays `FAIL`.
4. At least one leg `FAIL` with a complete evidence object gives `WITNESS-REFUTED`.
5. All six legs `PASS` gives `CAPABILITY-GROWTH-WITNESS`.
6. Otherwise `WITNESS-INCONCLUSIVE`, which is neither support nor refutation.

A witness is claimable only where all six legs were measured. Every witness record carries a mandatory `pool` field, `PRE_TRANSFER` or `E_TRANSFER`. Only an `E_TRANSFER` witness supports Level 4.

### 8.4 T, declared per pool, both branches

**Held-out** means unavailable to the proposal mechanism, the fitter and the search that produced the program.

On **`PRE_TRANSFER`** tasks, at G6 (stage 6), the mechanical check is:

1. **Branch 1.** A test input and reference output for `t` exist in an artifact licensed at stage 6 that is not a mechanism input under the manifest's input whitelist. T is measured, tagged `HELD_OUT_OUTPUT`.
2. **Branch 2.** A test input and reference output for `t` exist only inside a mechanism input (SA-08 "present"). T is `NOT_MEASURED`, reason `T_REFERENCE_NOT_HELD_OUT_FROM_MECHANISM`. The presence is recorded as `MECHANISM_INPUT_CARRIES_TEST_OUTPUT` and reported against the manifest's input declaration.
3. **Branch 3.** No test input and reference output exist in stage-6-licensed data (SA-08 "absent", and no other source). T is `NOT_MEASURED`, reason `T_NO_LICENSED_REFERENCE_AT_STAGE`.

Pre-transfer references are not consulted after admission, including once the extracts become licensed. A number with no decision role, produced after the decision, is a reinterpretation surface.

On **`E_TRANSFER`** tasks, at G8: the test inputs and reference outputs come from the E_transfer extract, licensed once the withdrawals are committed. No gate stage reads a raw ARC data file. Every test pair with a reference is used. A task with none records `NOT_MEASURED`, reason `T_NO_LICENSED_REFERENCE`.

### 8.5 Completeness predicate

A condition is COMPLETE on a task only when all hold:

| # | Condition |
|---|---|
| 1 | the search returned without raising |
| 2 | `stats.seconds < ARC_META_BUDGET_S - 0.01` |
| 3 | no fold in that condition's leave-one-out, where run, hit the deadline |
| 4 | zero `PER_TYPE_CAP` saturations, from a mandatory per (type, depth) counter in the gate's condition wrapper |
| 5 | in every condition the enumeration reached `MAX_DEPTH` with `early_stop == false`, enumerated every slot fill that fits the demonstrations rather than one per template, and retained every demonstration-fitting program; programs are deduplicated only by canonical serialization, never by outputs (`dedup_key = SERIALIZATION`); `fitting_set_size` and `fitting_set_sha256` are recorded before any test input is loaded |
| 6 | config digest and runtime-state digest equal the declared values |

Incompleteness produces `INCONCLUSIVE` (reason `CONDITION_INCOMPLETE`) or `RESOURCE_EXHAUSTED` (conditions 2 to 4), never `PASS`. Condition 4 exists because the frozen enumerator breaks out of its loops at the cap, caches the truncated list and reuses it, with no counter in its statistics. Truncation can then silently drop the very terms that would refute "K fails". `ARC_META_BUDGET_S = 64.0` is applied symmetrically so that "K fails" means K fails given eight times the budget Step B used.

### 8.6 Repeats and disagreement

`GATE_REPEATS = 3` under a pinned single-process, single-thread configuration. A leg takes a status only when every repeat, and any permitted re-run, records that same status with identical `fitting_set_sha256` (B, A, U), identical accepted-program sha256 (U, T), identical rendered-output sha256 (T) and identical per-fold verdicts (L). Any other combination, including `PASS` mixed with `RESOURCE_EXHAUSTED` or with `FAIL`, records the leg `INCONCLUSIVE` with reason `WITNESS-VOID-NONDETERMINISM`, and the pair is `WITNESS-VOID-NONDETERMINISM` with verdict `WITNESS-INCONCLUSIVE`. There is no majority rule and no best-of rule.

B and A are the same environment reached by two independent executions. Disagreement where either recorded a deadline hit is `WITNESS-ARM-DISAGREE-TIMING`. The declared response is one re-run of both at the same budget, ledgered. Disagreement with both complete is `WITNESS-ARM-DISAGREE-STRUCTURAL` and halts the gate as `TERM-HALTED` (14.1), because the conditions are then not what section 7 says they are.

### 8.7 Evidence object

One per leg per (extension, task, pool).

```json
{
  "leg": "B",
  "leg_name": "baseline_K_fails",
  "status": "PASS",
  "reason_code": null,
  "pool": "E_TRANSFER",
  "extension": {"class_id": "...", "representative": "...", "serialization_sha256": "..."},
  "task_ref": {"kind": "token|task_id", "value_sha256": "..."},
  "substrate": "SUB-BLIND",
  "condition": "K",
  "execution_ids": ["...", "...", "..."],
  "repeat_verdicts": ["...", "...", "..."],
  "completeness": {"raised": false, "seconds": 0.0, "deadline_hit": false,
                   "cap_saturations": {}, "max_depth": 5, "digests_match": true,
                   "early_stop": false, "dedup_key": "SERIALIZATION",
                   "fitting_set_size": 0, "fitting_set_sha256": "...",
                   "program_exceptions": 0, "program_limit_hits": 0},
  "reach_bound": 5,
  "e_inlined_size": null,
  "accepted_program_sha256": "...",
  "rendered_outputs_sha256": "...",
  "config_digest": "...",
  "runtime_state_digest": "...",
  "inputs_sha256": {},
  "outputs_sha256": {},
  "level_of_analysis": "HELD_OUT_OUTPUT",
  "script_sha256": "...",
  "post_inspection_tooling": false
}
```

A leg-specific payload is added: accepted-program serialization for U; per-fold records for L; rendered-output and reference hashes for T; the generation-record pointer into the pin for P.

### 8.8 Additivity on real tasks

The preflight decides additivity on fixtures. The same property is checked on every real execution, at G7a for the G6 executions and at the end of G8 for the G8 executions, from counters the condition wrapper records:

1. **K stream preserved.** In every (type, depth) cell, K_PLUS_E's candidate serializations with every `e`-using candidate removed have the same count and the same sha256 as K's.
2. **Same program where K solved.** On a task with a licensed reference where K's accepted program renders it exactly, K_PLUS_E's accepted program is that same program.

A violation records `ADDITIVITY_VIOLATED_ON_REAL_TASK` for that task, in `additivity_real_tasks.json` at G7a or `additivity_real_tasks_g8.json` at G8. On that substrate every `PASS` leg of every pair is recoded `INCONCLUSIVE` with that reason, in the same artifact. A recorded `FAIL` is never removed. The violation has no criterion-3 effect. Rungs, admission and `N_w` read the recoded statuses: a class barred from admission only by recoded legs routes by 10.4 row 6, and recoded G8 pairs count as inconclusive for criterion 6. Leg artifacts are never rewritten.

---

## 9. Full adaptive leave-one-out

### 9.1 What must be rebuilt

The protocol distinguishes fixed cross-task knowledge from target-dependent proposal state. Any proposal, extension choice, slot fitting or ordering conditioned on the current task's demonstrations is rebuilt inside every fold from N-1 demonstrations. Selecting `e` once from all demonstrations and then only refitting it in each fold is NOT full adaptive leave-one-out.

### 9.2 Dependence rule, mechanical

`e` is target-dependent for task `t` if any demonstration of `t` belongs to `e`'s proposing source set. Until that set can be resolved under the access schedule, `e` is treated as target-dependent. The rule fails closed.

- Pre-transfer tasks are in the proposing source set by token identity. `e` is target-dependent for them.
- E_transfer tasks are resolved at G7b through the firewall, by identity. At G8 entry, before any condition runs, each remaining task's demonstration grids are also compared with every proposing source's by a canonical content hash under a declared transform group: the eight grid symmetries, composed with relabelling colours in first-occurrence order with background 0 fixed. Only hashes are retained. A match, or a comparison that cannot be completed, excludes the task with `XFER-SKIP-CONTENT-DUPLICATE`, recorded with its hash. After both de-collisions, `e` is fixed cross-task knowledge for every remaining task.

### 9.3 L for a target-dependent `e`

L requires re-running the proposal mechanism inside each fold. For fold `i` of task `t`: rebuild the mechanism's inputs with `t`'s demonstrations replaced by the N-1 subset, all other sources unchanged; recompute from those inputs every state object the mechanism derives from demonstrations, namely clustering, cluster membership, class retention, candidate ordering and every global prior or count; re-run proposal and selection for the clusters `t` now belongs to; install the fold's own proposals additively; run the complete search on the N-1 demonstrations; predict the held-out demonstration. Every rebuilt state object is listed in the frozen driver manifest `loo_driver_manifest.json`, hashed in the tool manifest before `g3b_open`. Before each fold the driver asserts that its starting state digest equals the declared task-independent digest in that manifest; a mismatch records the fold `CHECKER_ERROR`.

- A fold passes iff that prediction is exact and the fold is complete.
- L is decided in this order: `INCONCLUSIVE` with reason `LOO_TOO_FEW_FOLDS` when `loo_folds < LOO_MIN_FOLDS`; `FAIL` when any complete fold fails; `CHECKER_ERROR` when any fold records a checker error; `RESOURCE_EXHAUSTED` when any fold hits a deadline or cap; `PASS` when every fold passes.
- Each fold records `fold_reproposes_e` (a proposal fingerprint-identical to `e` exists) and `fold_program_uses_e`. Both are reported beside L and change no pass rule.

If this cannot be implemented, L is `NOT_MEASURED` with reason `FULL_ADAPTIVE_LOO_UNAVAILABLE`. The proposal driver must be a separately frozen, candidate-independent script, hashed before G3b. The runner and `candidates.py` are never edited.

### 9.4 L for fixed cross-task knowledge

`e` stays fixed across folds, and everything conditioned on `t` is rebuilt: the whole discovery, slot fitting and ranking are re-run on N-1 demonstrations under K_PLUS_E. Before and after every fold, assert that the runtime-state digest is unchanged, so that no `t`-dependent state survives between folds. Fold pass, statuses and the fold-use counts are as in 9.3.

### 9.5 Diagnostic only

A program-level fold check under a fixed `e` on target-dependent tasks, which is what Step B's selection used, may be recorded only as `DIAG_PROGRAM_LEVEL_LOO`. It never enters any conjunction, admission rule or claim. The gate re-implements Step B's per-fold instrumentation, because it cannot import from MAIN's runner, and asserts per-task equality of its verdicts against the frozen verifier. Agreement and disagreement counts are reported under the diagnostic name.

### 9.6 What this replaces

This section replaces v1 section 5.5 and DR-15. v1 made the frozen program-level verifier the definition of W4. That is withdrawn. v1's caveat sentence is replaced by the requirement itself.

---

## 10. Admission to E_transfer

### 10.1 Order

The six-leg test runs first. Only surviving, causally useful extensions proceed to E_transfer.

### 10.2 Admission rule, predeclared

An extension `e` is admitted iff all hold:

1. its G7 rung is L3;
2. at least one pre-transfer task has B, P, U and A all `PASS`, and neither L nor T is `FAIL`, `CHECKER_ERROR`, `RESOURCE_EXHAUSTED` or `INCONCLUSIVE`. `NOT_MEASURED` is permitted for L and T only with a structural reason code from 8.2;
3. a substrate exists that passes every capability predicate applicable to E_transfer tasks (section 11). Otherwise `ADMIT-REFUSED-NO-SUBSTRATE`, since an E_transfer pass that could never yield a claimable witness would spend the split for nothing;
4. criterion 3 leg (a) `PASS` and criterion 5 `PASS`;
5. no per-class integrity code in `{ENV-UNVERIFIABLE, WITNESS-NONREPRODUCIBLE-CERTIFICATION, WITNESS-DEGENERATE-TREATMENT-EQUALS-CONTROL}`. Codes that halt the gate (14.1, `TERM-HALTED`) are never per-class admission bars, because the gate has stopped before admission;
6. lane K2.

After the freeze, criterion 4 and criterion 3 leg (b) may only withdraw (G7b step 5).

### 10.3 What admission licenses

Admission licenses measurement only. It is not a witness and licenses no capability-growth claim. The witness needs all six legs `PASS` and is claimable only where all six were measured. Only an E_transfer witness supports Level 4.

### 10.4 Nothing admitted

If nothing is admitted, E_transfer stays closed (`XFER-NOT-OPENED`). If every admitted extension is withdrawn, E_transfer is spent and not measured. The first row whose condition holds, in the order listed, gives the terminal code:

| Order | Terminal code | Condition |
|---|---|---|
| 1 | `WITNESS_SUBSTRATE_INCOMPLETE` | at least one retained K2 class is `SEP-SEPARATED` in `separation_primary`, is not capped by `MACRO-OVER-K-L4STAR-STRUCTURAL` or `SEP-MACRO-OVER-CONCEPT`, and either has no selected substrate (11.4) or had B, P, U or A `NOT_MEASURED` on every pre-transfer task |
| 2 | `TERM-NO-L2` | every class of row 1's kind had a selected substrate and measured legs, and none reached L2 because B, P or U recorded `FAIL` with a complete evidence object on enough tokens to bar `L2_MIN_SOURCES` |
| 3 | `TERM-NO-L3` | at least one class reached L2 and none reached L3 |
| 4 | `TERM-NO-WITNESS` | at least one L3 class had all relevant legs measured with a complete evidence object, and every L3 class has a leg `FAIL` that bars admission or a criterion `FAIL` |
| 5 | `TERM-ADMIT-REFUSED-INTEGRITY` | at least one L3 class had B, P, U and A `PASS` on a pre-transfer task, and every such class was refused only by a rule-5 code, which is named |
| 6 | `TERM-INCONCLUSIVE-G6` | no earlier row holds, and a leg of an L3 class, or a B, P or U leg of a class of row 1's kind with a selected substrate, is `INCONCLUSIVE`, `CHECKER_ERROR` or `RESOURCE_EXHAUSTED`, including a status recoded by 8.8 |
| 7 | `TERM-ALL-WITHDRAWN` | an admitted set was frozen and every admitted extension was withdrawn at G7b |
| 8 | `TERM-RESIDUAL` | no earlier row holds |

---

## 11. The substrate decision tree

### 11.1 Scope

Semantic separation is evaluated only in the frozen blind runtime, where the generated typed production exists. A six-leg witness is claimed only on a substrate that passes every capability predicate.

### 11.2 Candidate substrates, in declared order

1. **`SUB-BLIND`.** `level4_blind_runtime` with the `level4_stepB` install path, as pinned at G1 and identity-checked at G2, plus any candidate-independent additive wrapper built under 7.5.
2. **`SUB-V21-BRIDGE`.** `geocat_arc.object_reasoning.meta_v21` with a candidate-independent bridge that installs a typed production. It is a candidate only if the bridge was built, tested on synthetic fixtures, shown behaviour-preserving for K, and listed in the module pin at G2. Otherwise every predicate records `NOT_AVAILABLE`. Any bridge is a separate engineering stage and cannot retroactively certify the Step-B run. A witness on this substrate is a new measurement of `e`, not a validation of Step B's certification.

The `meta_induction` path is not a candidate. It is the negative control of 7.4.

### 11.3 Capability predicates, in declared order

No predicate runs `e` on any real task. All are ledgered for every candidate substrate before any witness run.

| Order | Predicate | Evaluated | Pass condition |
|---|---|---|---|
| S1 | additive install | G3a, fixtures | `ADDITIVITY_PREFLIGHT_PASS` (section 7) |
| S2 | installability of `e` | G6 entry, frozen probe set only | `e` installs and its behaviour fingerprint over the frozen probe set, computed by the same function Step B used, equals the pinned class fingerprint |
| S3a | adaptive proposal driver | G3a, fixtures | the 9.3 driver reproduces a synthetic control mechanism's per-fold proposals on fixtures |
| S3b | per-fold rebuild | G3a, fixtures | the 9.4 procedure rebuilds all `t`-conditioned state with an unchanged runtime-state digest across folds |
| S4 | licensed output reference path | G3a, fixtures | renders a program's output on a test input and compares exactly, with `None` giving FAIL and a raise giving `CHECKER_ERROR`, on fixtures with known answers |
| S5 | decidable use trace | G3a, fixtures | returns true on a fixture program containing the control production and false on one without it; never short-circuits |
| S6 | executable independent ablation | G3a, fixtures | constructs the 7.2 ablation in a separate execution with the name-set assertions passing |

"Full adaptive LOO where required" is S3a for target-dependent rows and S3b for all rows.

### 11.4 Selection

For each extension, the substrate used is the first in 11.2 that passes S1, S2, S3b, S4, S5 and S6. S3a is recorded. Where it fails, target-dependent rows record L `NOT_MEASURED` with `FULL_ADAPTIVE_LOO_UNAVAILABLE`. If no substrate passes, the outcome for that extension is `WITNESS_SUBSTRATE_INCOMPLETE`. That is a result. It is not permission to improvise another test after seeing a candidate.

### 11.5 Tooling boundary

Candidate-independent gate scripts may be built between G1 and G3b under 2.7. Any change to an engine, wrapper or bridge that affects K is completed before G2, shown behaviour-preserving for K on a frozen synthetic fixture set, and listed in the module pin, which every later stage re-verifies. Any bridge, wrapper or engine change created after G3b carries `POST-INSPECTION-TOOLING` for every Step-B extension permanently, under this or any later protocol. No Step-B extension evaluated through it may be named a witness or reach L4.

### 11.6 Availability is fixed before the first witness run

Substrate availability is decided only by the ledgered predicates, before the first witness run. No witness outcome revises it (19 item 7).

---

## 12. The semantic-separation test

This implements the additive requirement of the frozen design, which has never been implemented.

### 12.1 What is tested, and the forbidden implementation

The design states:

```
exists x :  e(x)  not in  { p(x) : p in F(K_L4*) }
```

Baseline programs are functions of the same `x`. Enumerating CLOSED terms of the result type gives terms that receive only the context grid. Comparing `e(a1..an ; g)` against `{ p(g) }` hands the candidate inputs the baseline cannot receive, and an exact re-spelling of a frozen production would then separate on the first probe. That implementation is forbidden.

### 12.2 Baseline construction

For a candidate with interface `A -> B` and non-port parameter list `L`, the port slot is excluded from `L`.

1. Capture `FROZEN_BASE` before any install. The primary baseline vocabulary is `K_L4*`, the admitted productions read from `level4_baseline_admissibility_v2.json`. The secondary vocabulary is `E_L4* = K_L4* + {concept_0001}`.
2. Enumerate OPEN terms as functions `A -> B` over the vocabulary with the pinned port-bearing enumerator, passing `max_depth = SEP_MAX_DEPTH`, `per_type_cap = SEP_PER_TYPE_CAP`. Record `dropped_by_cap` per (type, depth) cell.
3. No `MAX_CANDIDATES` truncation, no early stopping, no wall clock inside the enumeration. The only external bound is `SEP_ENUM_CEILING_S`.
4. Candidate and baseline terms are evaluated under the same install state and evaluator, with the baseline vocabulary restricted to frozen names.
5. **Empty baseline, split by cause.**

| Cause | Code | Reading |
|---|---|---|
| `K_L4*` has no term of result type `B` from a port of type `A` at any depth | `SEP-BASELINE-TYPE-UNREACHABLE` | reachability fact; inconclusive; never separation |
| empty only because `L` contains parameter types absent from `K_L4*` | `SEP-PARAM-TYPE-ABSENT`, then step 6 | not a verdict alone |

6. **Parameter-frozen re-run.** Freeze each non-port parameter of `e` at each witness value of its type in canonical order, giving a family of unary functions `A -> B`, and compare each against the same open-term enumeration. The family is `SEP-SEPARATED` only if at least one member is `SEP-SEPARATED` and no member ends in an undecided code: `SEP-ERROR`, `SEP-INCONCLUSIVE-ENUM-TRUNCATED`, `SEP-INCONCLUSIVE-BASELINE-ERRORS`, `SEP-INCONCLUSIVE-TIMEOUT` or `SEP-NO-CONSTRUCTIBLE-PROBE`. A family with an undecided member takes the first such code in that list. A family with no separated and no undecided member takes `SEP-EQUIVALENT` if any member is equivalent, and otherwise the code of its first member. Every member's code is recorded. Without this, the gate would automatically bar L3 for every operator whose parameters have types the prior language lacks, which includes any genuine bridge between existing types.

### 12.3 Constructor pre-pass, run once before any candidate

A test that asks only "does the elaboration contain an inventory constructor" can be satisfied by every K2 candidate by construction, because the K2 lane vocabulary places inventory constructors at the root of most goal-typed terms. Such a test is inert.

For every ground inventory instance used by any retained candidate, apply the 12.4 and 12.5 comparison to that instance alone, at its own interface, against the `K_L4*` open-term enumeration. An instance that is `SEP-EQUIVALENT`, or that has a baseline term agreeing with it on every jointly defined probe, is stamped `CONSTRUCTOR-DEFINABLE-IN-K-L4STAR`. A candidate all of whose inventory instances carry that stamp is stamped `MACRO-OVER-K-L4STAR-STRUCTURAL` and is capped at L2 permanently. An instance whose comparison ends in any code other than `SEP-SEPARATED` or `SEP-BASELINE-TYPE-UNREACHABLE`, including `SEP-ERROR`, a timeout or truncation, is stamped `CONSTRUCTOR-UNDECIDED` and counts as definable for this cap. A candidate escapes `MACRO-OVER-K-L4STAR-STRUCTURAL` only if at least one of its instances is `SEP-SEPARATED` or `SEP-BASELINE-TYPE-UNREACHABLE`.

The pre-pass runs over whatever instances the pinned inventory contains. No instance is named here as a premise. The firing count is reported. If it is zero across the gate, it is listed under `INERT-GUARD` in the same sentence as any claim resting on it.

### 12.4 Probes and behaviour

1. **Probe set.** The frozen generator, `SEED = 424242`, pinned bounds and module hash, `SEP_CONTEXTS = 6`, `SEP_ARG_COMBOS = 24`, at most 144 probes per candidate. It reads no cluster content. It is regenerated at gate time and must reproduce the fingerprint recorded in the run manifest (SA-07). A mismatch is `SEP-WITNESS-GENERATION-ERROR` and stops the gate as `TERM-HALTED`. No candidate influences probe selection.
2. **Identical inputs.** Candidate and every baseline term receive the SAME argument tuple in the same order. No slot fitting on either side. A separation obtained because one side was fitted is void.
3. **Baseline-constructible arguments.** A probe is admissible only if every argument component is, on that context, in the image of some `F(K_L4*)` term of that type, or is a frozen terminal value. Discarded probes are counted under `SEP-ARG-NOT-CONSTRUCTIBLE`. If none remain, the outcome is `SEP-NO-CONSTRUCTIBLE-PROBE`, which is inconclusive.
4. **Three-valued behaviour.** `behaviour_typed` records exactly one of `DEFINED(canonical value)`, `UNDEFINED` (returned `None`, no exception) or `ERROR(class)`. Nested containment layers swallow exceptions, so a single instrumentation hook at the outermost call records the class before returning `None`. The hook is a declared deviation from the Step-B evaluation path, its hash is in the config digest, and it can only remove cells from apparent agreement or apparent undefinedness. `ERROR` is never evidence of separation, necessity or equivalence.
5. **Non-vacuity floor.** The candidate must be `DEFINED` on at least `SEP_DEF_MIN` admissible probes over at least `SEP_CTX_MIN` contexts. Below that, `SEP-VACUOUS`, and the class is flagged as a possible vacuity collision in its Step-B class.
6. **Equality.** Canonical images serialized with sorted keys and compared as strings. Any exception in canonicalization or comparison is `SEP-ERROR`, never a non-match.

### 12.5 Separation predicate

Comparison is per baseline PROGRAM over the admissible probe set.

```
SEP-SEPARATED  iff
  (a) at least SEP_MIN_SEPARATING_PROBES admissible probes, spanning at least
      SEP_MIN_SEPARATING_CONTEXTS contexts, where at each probe x:
        e(x) is DEFINED, and
        at least one baseline term is DEFINED at x, and
        no baseline term DEFINED at x equals e(x), and
        the count of baseline terms with ERROR at x is zero;
  and
  (b) no baseline term agrees with e at every probe where both are DEFINED;
  and
  (c) it is not the case that the only difference from some baseline term p is
      that e is DEFINED where p is UNDEFINED while agreeing wherever both are
      DEFINED;
  and
  (d) dropped_by_cap == 0 in every cell reachable in the candidate's interface,
      and the enumeration finished within SEP_ENUM_CEILING_S.
```

- Clause (b) exists because a per-probe existential lets a boundary convention separate a near-clone: an operator that differs from a baseline term only on an edge input such as an empty selection would otherwise separate.
- Clause (c) exists because a per-probe rule silently drops baseline terms that are undefined at the separating probe, so a totalization of an existing operator would separate. That case is `SEP-TOTALIZATION-ONLY`, recorded, not a pass.
- Clause (d) is asymmetric on purpose. Truncation can only remove refuting terms. A match found under truncation is a valid `SEP-EQUIVALENT`. An absence of match under truncation is `SEP-INCONCLUSIVE-ENUM-TRUNCATED`.
- The zero-error condition in (a) is per probe, with the per-probe error census reported. When no probe meets it, the outcome is `SEP-INCONCLUSIVE-BASELINE-ERRORS`.

### 12.6 Bounded-search novelty versus separation

| Route to a false positive | Mechanism that closes it |
|---|---|
| a composition of frozen pieces the depth budget cannot reach | constructor pre-pass and structural cap: composition is a language fact, depth is a budget fact |
| comparison against programs that never received the candidate's inputs | open-term enumeration, identical argument tuples, baseline-constructible arguments |
| difference only where the baseline is undefined, or at one boundary | clauses (b), (c) and the robustness floor |

A macro whose instances are definable in `K_L4*` within depth 5 is capped at L2 and reported as reachability. A composition definable only at greater depth is not excluded by this test (19 item 1).

### 12.7 Two baselines and the sentences they license

| Baseline | Field | Decides |
|---|---|---|
| `F(K_L4*)` | `separation_primary` | the L3 rung |
| `F(E_L4*)` | `separation_secondary` | one reachability sentence |

`concept_0001` expands into the kernel, so the two denote the same functions and differ only in reachability at the declared depth. The secondary licenses exactly: "not reachable within the declared enumeration bounds from the frozen productions alone, but reachable once `concept_0001` is available as a one-node macro". A class separating from `F(K_L4*)` but not from `F(E_L4*)` is `SEP-MACRO-OVER-CONCEPT` and is capped at L2. A class whose `separation_secondary` is any code other than `SEP-SEPARATED`, an inconclusive code included, is barred from L3, and that code is recorded.

### 12.8 Guard accounting

Every certificate records: admissible and discarded probes; baseline terms enumerated; `dropped_by_cap` per cell; comparisons performed; `DEFINED`, `UNDEFINED` and `ERROR` counts for candidate and baseline separately; duplicate-fingerprint collisions; per-member heterogeneity; and the firing count of every rejection code. A guard with zero firings across the gate is listed under `INERT-GUARD`. Any claim resting on a stage where a load-bearing guard never fired carries that code in the same sentence. An inert guard is not a pass.

### 12.9 Separation outcome vocabulary

`SEP-SEPARATED`, `SEP-EQUIVALENT` (reported with the frozen string `EQUIVALENT_TO_BASELINE_COMPOSITION`), `SEP-MACRO-OVER-CONCEPT`, `SEP-TOTALIZATION-ONLY`, `SEP-DEFINEDNESS-ONLY`, `SEP-VACUOUS`, `SEP-NO-CONSTRUCTIBLE-PROBE`, `SEP-ARG-NOT-CONSTRUCTIBLE`, `SEP-BASELINE-TYPE-UNREACHABLE`, `SEP-PARAM-TYPE-ABSENT`, `SEP-INCONCLUSIVE-ENUM-TRUNCATED`, `SEP-INCONCLUSIVE-BASELINE-ERRORS`, `SEP-INCONCLUSIVE-TIMEOUT`, `SEP-ERROR`, `SEP-WITNESS-GENERATION-ERROR`, `SEP-NOT-APPLICABLE-K1-LANE`, `MACRO-OVER-K-L4STAR-STRUCTURAL`, `CONSTRUCTOR-DEFINABLE-IN-K-L4STAR`, `CONSTRUCTOR-UNDECIDED`.

---

## 13. Decision rules

Each rule is final, declared before the outcome, and embedded verbatim in `gate_tool_manifest.json`. A stage finding the embedded text different from this document refuses with `REFUSE-PREREG-MISMATCH`.

**DR-01 Frozen tooling.** A stage executes only scripts hashed in the tool manifest attested by the event `g3b_open`. A later script's artifacts carry `POST-INSPECTION-TOOLING` permanently, and every claim consuming them is exploratory.

**DR-02 Launch-time provenance.** Every gate script records git HEAD, porcelain dirty counts, `PYTHONHASHSEED`, Python version, platform and UTC time at process start, before computing anything. A git hash read at report time is a protocol breach.

**DR-03 Hash seed.** Every gate process runs with `PYTHONHASHSEED=0`, enforced by `gate_preflight.py`. A stage that finds it unset writes `ENV-UNVERIFIABLE`, and its results support no claim.

**DR-04 One config digest.** `config_digest` is the sha256 over: runtime and search module hashes, `meta_v21*` module hashes, the admissibility artifact hash, `SEP_MAX_DEPTH`, `SEP_PER_TYPE_CAP`, budget, cost table, ranking rule, terminal table, induced-type list, slot-learner registry, `K` identity hash, extension identity hash, substrate id, and instrumentation hook hash. Two records are compared only if their digests differ in exactly the declared single field.

**DR-05 Runtime state digest.** Every condition and evaluation records the sha256 over the sorted registry names, the terminal values with canonical tuples, the induced-type list, the slot-learner names, the argument modes and the evaluator's qualified name. Install paths mutate these process globals, so identical files can behave differently. Each stage's expected digest is declared in the tool manifest (P0.1) and asserted at start from G3b onward. Stage records written before `g3b_open` carry null `config_digest` and `runtime_state_digest`. A mismatch is `RUNTIME-STATE-MISMATCH`, a halt declared in 14.1a.

**DR-06 No wall-clock primary.** The primary resource everywhere is typed candidates enumerated.

**DR-07 Retention fixed by the run.** The retained set is exactly the classes with non-empty `kept_for`. `N_retained` is recorded before any per-class field is read.

**DR-08 Label is not a certificate.** `gate_rung.py` takes no label argument. Novelty comes from the structural pre-pass and the separation certificate. Capability comes from the six-leg witness.

**DR-09 One object per class.** `e` is the class representative with no substitution. Semantics are recorded as a list over every inventory instance in its schema.

**DR-10 Pin before eyes.** No pinned file is opened for content before G3, except that the protocol artifacts of 15.1 are hashed, line-counted and marker-counted at G1 and G2 by the pin tool; their content opens at G3a. The single immutable pin is created only under the three readiness conditions of G1, written atomically, committed, and bound to its commit before G2.

**DR-11 Access ledger.** Every content-bearing read from G3b onward is appended by an `open()` audit hook. A claim depending on a file absent from the ledger is void.

**DR-12 Six statuses everywhere.** `PASS`, `FAIL`, `INCONCLUSIVE`, `CHECKER_ERROR`, `RESOURCE_EXHAUSTED`, `NOT_MEASURED`. Only `PASS` counts. No missing field defaults to success.

**DR-13 Completeness before comparison.** Section 8.5 in full.

**DR-14 Additive comparison.** Section 7 in full. No B or A leg is computed on a substrate without `ADDITIVITY_PREFLIGHT_PASS`.

**DR-15 Full adaptive leave-one-out.** Section 9 in full. A program-level fold check is only `DIAG_PROGRAM_LEVEL_LOO`.

**DR-16 Invention provenance is the union of proposing sources over all members,** resolved to task ids at G7b, conservative, never redefined.

**DR-17 De-collision by identity and content hash only.** Every skip is recorded with its identity or hash and its reason. Errors and exhausted resources stay in the denominator.

**DR-18 Admitted set frozen before the firewall opens.** Committed and verified in the index. After the freeze, only criterion 4 and criterion 3 leg (b) may withdraw, and the withdrawals are committed before any E_transfer input is read.

**DR-19 Empty set closes the split.** No exploratory peek, sanity check or single-candidate exception.

**DR-20 One access, adjudicated by artifacts.** G8 in full, including the stdout tee.

**DR-21 Named primary, no substitution.** The capability-growth primary is the six-leg conjunction. The transfer primary is `N_w`. M1 to M5 are secondary and never promoted.

**DR-22 No tuning surface.** Nothing changes after E_transfer opens. A defect voids the pass, the void is recorded, and any restart other than the crash rule of G8 is `XFER-SECOND-ACCESS`.

**DR-23 Retrospective costs are not forecasts.** Every M4 number is `MEASURED-RETROSPECTIVE`.

**DR-24 Level of analysis on every claim.** Every claim sentence carries exactly one of `DEMONSTRATION_FIT`, `LOO_REDISCOVERY`, `HELD_OUT_OUTPUT`, `BOUNDED_ENUMERATION`, plus rung code, split, denominator and outcome code. A sentence missing any of these is void.

**DR-25 Guards are counted.** Every guard reports `evaluated` and `fired`. Each has a synthetic positive-control fixture run at G3a. A control that does not fire halts the gate. Zero-firing guards on real data are listed as `INERT-GUARD`.

**DR-26 Append-only knowledge state.** `K_t` is kept verbatim.

**DR-27 No hand-authored concepts.**

**DR-28 3A and 3B never summed.**

**DR-29 Exactly one terminal code.** The precedence of 14.1 decides, and `GATE_STOPPED_PROVENANCE_FAILURE` overrides every other code. A negative terminal code requires every relevant record to be decided. Refutation conditions key on `FAIL` with a complete evidence object, never on the absence of `PASS`.

**DR-30 Provenance failure is not a result.** `PinProvenanceError` stops the gate. It is never recorded as a negative or a positive, and it is never repaired by repinning or overwriting.

**DR-31 Schema assumptions.** Section 3.4 and 3.3 item 3. `SCHEMA_ASSUMPTION_FAILED` stops the gate as `TERM-HALTED`, and any tooling change after it is `POST-INSPECTION-TOOLING`.

**DR-32 Quarantine.** Q1 to Q6 bind every rule. No quarantined observation is a premise.

**DR-33 Substrate by declared order.** Section 11 in full. `WITNESS_SUBSTRATE_INCOMPLETE` is a result, not permission to improvise.

**DR-34 Forbidden phrasings.** These may not appear in any gate artifact, README, manuscript, abstract or slide derived from this gate:
- "partial witness"; "near witness"; "would have passed"; "essentially", "effectively" or "nearly" applied to a rung;
- "vanish under ablation" unless the recorded code says the gain vanished;
- "solved nothing extra" without the level of analysis;
- "untouched", "pristine", "fully prospective", "lockbox validation";
- "no previous system invents concepts or predicates from failure";
- forecast, projected, deployment estimate or expected cost applied to a measured search cost;
- any claim of invention without `RUNG-L4`;
- "e is not expressible in K_L4*"; "unavailable in the system's operative language";
- "exhaustive" applied to any enumeration bounded by `per_type_cap`;
- any statement that the pin tool read no content;
- any citation of the DEV-60 arm as evidence that test-time semantic extension fails;
- any count of `NEW_SEMANTIC_PRODUCTION` labels presented as a count of inventions.

**DR-35 Numeric regeneration.** `gate_report_check.py` regenerates every number in any summary from the hashed artifacts and blocks the report on mismatch.

**DR-36 One sealed number.** 185/1000 (v23, artifact-backed) until a new sealed measurement exists. Historical manifest facts are exempt with their version attached: `LOCKBOX_PROTOCOL.md` correctly reports 181 as the certified composition under manifest v1.0.0.

**DR-37 No attribution.** No gate artifact, commit message, manuscript or document produced under this protocol carries any model or tool attribution.

**DR-38 Implementation fixes yes, protocol changes no.**

**DR-39 Reach, not selection.** B and A follow the reach rule of 8.1. A task where K held a demonstration-fitting program that renders the licensed reference is never a witness, whichever program K ranked first.

**DR-40 Extracts only.** No gate stage reads a raw ARC data file or the Lockbox manifest for content. The single exception is `GateGuard.extract` (15.3): at G7b after `g7b_open` for Promotion ids and tasks, and at G8 after `g8_open` and before `g8_closed` for E_transfer tasks, returning licensed members only. Every other step sees Promotion and E_transfer tasks only through the per-split extracts.

**DR-41 K is fixed at G2.** Nothing that affects K is created after G2. Anything built after G3b carries `POST-INSPECTION-TOOLING` for every Step-B extension permanently.

---

## 14. The failure branch

### 14.1 Triggers and frozen interpretations

If Step B produces no semantically separated, causally useful extension, the gate STOPS and records that result.

The gate records exactly one terminal code. When several triggers hold, the lowest order wins, and `GATE_STOPPED_PROVENANCE_FAILURE` overrides every other code.

| Order | Terminal code | Trigger | Interpretation, frozen now |
|---|---|---|---|
| 0 | `GATE_STOPPED_PROVENANCE_FAILURE` | `PinProvenanceError` at any stage, or a terminal G1 pin or binding outcome | No scientific result of any kind. The failure is described. |
| 1 | `TERM-VOID-PROTOCOL-BREACH` | breach of DR-10, DR-11, DR-20 or section 15 | No confirmatory evidence. The breach is described. |
| 2 | `TERM-HALTED` | a terminal halt of 14.1a | The gate stopped on a declared integrity condition before a verdict. Not a negative. The halt code is named. |
| 3 | `TERM-NO-CANDIDATE` | `N_retained == 0` | The K2 schema could not express what the failure clusters needed. A real negative about THIS schema. K2 is not widened after the fact. |
| 4 | `TERM-ONLY-K1-REPAIRS` | all retained classes are lane K1 | The located gap was an estimator gap. A real negative for Level 4. |
| 5 | `TERM-ALL-EQUIVALENT` | every retained K2 class ends at `SEP-EQUIVALENT`, `SEP-TOTALIZATION-ONLY`, `SEP-DEFINEDNESS-ONLY`, `SEP-MACRO-OVER-CONCEPT` or `MACRO-OVER-K-L4STAR-STRUCTURAL`, and no structural cap rests on a `CONSTRUCTOR-UNDECIDED` instance | Every retained K2 class was shown, under the bounds, to be a baseline composition, a totalization, a definedness variant or a macro. An L2-capped macro result, not a Level-4 result. |
| 6 | `TERM-INCONCLUSIVE-G4` | no uncapped K2 class is `SEP-SEPARATED`, and at least one class ends in `SEP-VACUOUS`, `SEP-ERROR` or an inconclusive separation code, or carries a structural cap resting on a `CONSTRUCTOR-UNDECIDED` instance | No separation verdict. Nothing was shown equivalent or separated beyond the listed codes. Not a negative. |
| 7 | `WITNESS_SUBSTRATE_INCOMPLETE` | 10.4 row 1 | The test could not be run as declared for at least one separated class. Not a negative about extension. E_transfer not opened. |
| 8 | `TERM-NO-L2` | 10.4 row 2 | No separated class met the L2 predicate on measured legs. The first barring leg is named per class. Nothing is said about reach beyond the measured tokens. |
| 9 | `TERM-NO-L3` | 10.4 row 3 | No class met the L3 predicate. Each L2 class is listed with its separation and structural codes and the level at which its reach grew. |
| 10 | `TERM-NO-WITNESS` | 10.4 row 4 | No admissible pre-transfer witness existed. The first barring predicate, leg or criterion, is named per class. Nothing is said about causal utility beyond that predicate. E_transfer not opened. |
| 11 | `TERM-ADMIT-REFUSED-INTEGRITY` | 10.4 row 5 | Admission was refused only for the named integrity code. Not a negative. E_transfer not opened. |
| 12 | `TERM-INCONCLUSIVE-G6` | 10.4 row 6 | No verdict at the witness stage. No claim in either direction. Not a negative. |
| 13 | `TERM-ALL-WITHDRAWN` | 10.4 row 7 | Criterion 4 or criterion 3 leg (b) barred every admitted extension. E_transfer is spent and was not measured. Not a transfer result. |
| 14 | `TERM-NO-TRANSFER` | `C6-FAIL` with every pair decided | No E_transfer witness. Causally useful, if at all, only on tasks that took part in invention: a retrofit by the frozen definition of criterion 6. |
| 15 | `TERM-INCONCLUSIVE-G8` | `C6-INCONCLUSIVE` | No transfer verdict. Not a negative. |
| 16 | `TERM-L4-NOT-PROMOTED` | `C6-PASS`, and G9 records `NOT-PROMOTED-CRITERION` or `NOT-PROMOTED-INCONCLUSIVE` for every extension | Level-4 witnesses exist under their stated bounds. Promotion was refused for the named criterion. `K_t` is unchanged. |
| 17 | `TERM-PROMOTED` | at least one extension `PROMOTED`, and G10 complete | `K_{t+1}` is recorded. Claims are limited to the recorded rung codes and to the separately reported 3A and 3B results. |
| 18 | `TERM-INCONCLUSIVE-<stage>` | any other stage that could not decide | No verdict. No claim in either direction. Not a negative. |
| 19 | `TERM-RESIDUAL` | 10.4 row 8, or no other trigger holds when the gate ends | No verdict. The unmatched end state is described. Not a negative. |

### 14.1a Halts

Every halt is declared now as terminal or resumable.

| Halt code | Kind | Effect |
|---|---|---|
| `SEM-DRIFT`, `LANE-VOCAB-MISMATCH`, `SRC-UNDER-THRESHOLD`, `SEP-WITNESS-GENERATION-ERROR` | terminal | `TERM-HALTED` |
| `SCHEMA_ASSUMPTION_FAILED` | terminal | `TERM-HALTED`; any later tooling is `POST-INSPECTION-TOOLING` |
| `RUNG-UNASSIGNABLE`, `WITNESS-ARM-DISAGREE-STRUCTURAL` | terminal | `TERM-HALTED` |
| `ADDITIVITY_PREFLIGHT_CONTROL_FAILED`, `GUARD-CONTROL-FAILED`, `PROTOCOL_BINDING_MISMATCH` | terminal | `TERM-HALTED` |
| `PIN2-INCOMPLETE`, `PIN2-DIVERGENT-COPIES`, `PIN2-ARTIFACT-ABSENT` | terminal | `TERM-HALTED` |
| `REFUSE-PREREG-MISMATCH`, `STAGE-PROVENANCE-DRIFT` | terminal | `TERM-HALTED` |
| `RUNTIME-STATE-MISMATCH`, `CONFIG-MISMATCH` or `ENV-UNVERIFIABLE` found at stage start, before any condition runs; `PIN2-TOOL-MISSING` | resumable | the stage writes `halt_record_<stage>.json` and no stage artifact; after the named environment or tooling repair, which reads no sealed content, the stage runs once more; the same halt again is terminal as `TERM-HALTED`; a repair after `g3b_open` carries `POST-INSPECTION-TOOLING` |
| any of those three found after a condition has run | terminal | `TERM-HALTED` |

### 14.2 What is recorded

1. The G1 pin, the G2 module pin, every verification outcome, the substrate ledgers and the complete access ledger.
2. The per-class table with all `N_retained` rows, every G4 field, every separation and structural code, all three rung assignments, and the first failing predicate per row.
3. Every witness record with all six evidence objects, including legs that passed, completeness flags and the pool field.
4. Reproduction disagreement counts, the degeneracy check result, and `DIAG_PROGRAM_LEVEL_LOO` counts under that name.
5. Guard counts, positive-control results and the `INERT-GUARD` list.
6. Counts of each non-`PASS` status at every stage, kept separate.
7. Enumeration sizes per candidate, `dropped_by_cap` per cell, non-constructible probe counts, and any candidate that reached `SEP_ENUM_CEILING_S`.
8. Every skip with its identity and reason, including zero counts.
9. The primary and the five secondary measurements, with denominators, if E_transfer was opened.
10. Standing environment caveats, including `ENV-HASHSEED-UNSET-AT-RUN`, `ENV-THREADS-UNSET-AT-RUN` and `ENV-RUN-UNKNOWN` where they apply.
11. The tool manifest, including any `POST-INSPECTION-TOOLING` stamps and any `SCHEMA_ASSUMPTION_FAILED` events.
12. The terminal code, with its frozen interpretation quoted verbatim.
13. The Level-4 row of `docs/CORA_EVIDENCE_LADDER.md`, moved from PENDING to the recorded outcome with its bound: a result about THIS schema under THESE bounds on THIS substrate, not about semantic self-extension in general.

The negative is published as a negative. It is not patched, not re-run with an adjusted inventory, and not retold as a positive about a secondary measurement.

### 14.3 What the failure branch does not license

No terminal code of 14.1, whether negative, inconclusive, halted, void, residual or provenance, is a reason to return to abstraction selection or memory work. These responses are forbidden after every one of them:

- a new ranking rule, scoring function or search prior;
- a library retrieval or concept routing mechanism;
- a re-run or extension of the LAS or abstraction-selection line;
- widening the K2 constructor inventory to cover what the clusters needed;
- repairing a specific failing candidate;
- a second Step-B run with an adjusted inventory, cluster threshold or eligibility rule;
- substituting a secondary measurement for the failed primary;
- relaxing the verifier, the bounds, the completeness predicate, the additive comparison rule or section 9.

The reason is the evidence already on record. Search and prior transfer are shown. Predictive-selection transfer is shown narrowly. Learned abstraction beating concrete memory failed its preregistered replication at +3, 95 percent paired bootstrap interval [-1, 8]. Bounded search-reach gain produced zero witnesses, with every policy fitting the same 188 of 256 targets. Further work in that direction has a documented ceiling.

`WITNESS_SUBSTRATE_INCOMPLETE` gets the same forbidden-response list. The one permitted engineering response is the separate stage named in 11.2: a candidate-independent bridge or additive wrapper, under its own frozen protocol. It cannot certify the Step-B run retroactively. Because it is necessarily built after G3b, it carries `POST-INSPECTION-TOOLING` for every Step-B extension permanently, under any protocol, and no Step-B extension evaluated through it may be named a witness or reach L4. It may serve only a new mechanism's own pre-registered experiment.

### 14.4 The single permitted redesign target

The target is the semantic-construction mechanism itself: a typed meta-constructor that proposes new BRIDGES between existing reasoning types, instead of selecting among whole programs that were already enumerated. The bridge shapes were declared by the directive of 2026-09-09 and are not revised with any knowledge from D2:

```
Set[Region]      -> Grid
Set[Entity]      -> Set[Placement]
Relation[A, B]   -> Mapping[A, B]
Collection[A]    -> Aggregate[B]
ObjectPair       -> Transform
```

No part of this protocol assumes that any existing runtime already carries any of these bridges.

No code for the bridge meta-constructor is written until a new pre-registered protocol document exists, is committed and is hashed in the same style. That document declares its own primary endpoint before any run, and its own separation test before its mechanism exists. The failure record of this gate is an input to it. It may be cited only under its terminal code's frozen interpretation, and an inconclusive, halted, void, residual or provenance code is never cited as evidence that the previous mechanism failed. It uses a fresh holdout drawn separately. E_transfer counts as spent once the provenance firewall has been read at G7b, whether or not G8 ran. An E_transfer never resolved through the firewall stays unspent, but it may not be used to evaluate any Step-B extension outside this gate. It inherits sections 4, 7, 8, 9, 12, 13 and 15 of this document unchanged, and it inherits 14.3.

---

## 15. Sealed-data discipline and guard facts

### 15.1 What may be touched at which stage

| Data class | Object | First licensed stage | Access permitted |
|---|---|---|---|
| pinned scopes | section 15.2 | G1 | bytes read transiently for sha256, and newline counts and the freeze-marker count for the run log only, under the C2 invariant |
| extra hashes | K-affecting module roots, admissibility v2, Lockbox manifest, frozen split manifest, engine changes and wrappers | G2 | hashing under the C2 invariant by `write_module_pin`, and `GateGuard.hash_only` (15.3) |
| protocol artifacts | the run manifest and its hash, the design hash, the final output hash, the run log | G1 and G2 for hashing and counts only; content from G3a | content, ledgered from G3b |
| frozen design source | runner, `level4_stepB/`, `level4_blind_runtime/` | G3a | content, ledgered |
| pre-run records | Step-A, admissibility, v21 and other records that existed before the run | G3a | content, ledgered |
| Step-B outputs | merged classes, inventory, `level4_stepB_witnesses.json`, gate outputs, mechanism inputs | G3b, once `g3b_open` is valid | content, ledgered |
| checkpoint journal | `level4_stepB_journal.jsonl` | never for content | pin record only |
| withheld expectation | `level4_withheld_expectation_seal.json` | never in this gate | pin record only |
| provenance firewall | `level4_provenance_firewall.json` | G7b, once `g7b_open` is valid | `source_token_to_task`, `within_stage_holdout.E_transfer`, and the forbidden-name check by count only |
| Promotion membership | the Promotion id list in the Lockbox manifest | G7b, once `g7b_open` is valid | ids only, through `GateGuard.extract` with the SA-12 key path; nothing else in the manifest is decoded |
| Promotion extract | `extracts/promotion_tasks.json` | G7b, once `g7b_open` is valid | evaluated, never mined |
| E_transfer data | `extracts/etransfer_tasks.json`, every other file under `extracts/` except the Promotion extract, and any file whose name carries an E_transfer stem | G8, once `g8_open` is valid, until `g8_closed` | one pass, ledgered; refused for good once `g8_closed` is valid |
| raw ARC data files | training and evaluation challenges and solutions, wherever they live | never for content | the training challenges and training solutions files only through `GateGuard.extract`, at G7b for Promotion tasks and at G8 for E_transfer tasks |
| gate results | files in `outputs/tti/stepB_gate/` without a sealed name stem, such as `etransfer_results.jsonl` | the stage that writes them | content |
| Lockbox200 tasks | any content | never in this gate | none; code permits Lockbox-class reads only after `g11_complete`, for a separately pre-registered evaluation |
| D3 and D4 TTI holdouts | `eval_split_v1`, holdout half | never in this gate | none, and never confused with Lockbox200 |

### 15.2 Pinned scopes and the module pin

The freeze pin covers exactly the scopes of `cora_tti/freeze_pin.py`:

- **Explicit.** `scripts/cora_level4_stepB_run.py`, `scripts/restart_stepB_after_reboot.sh`, `logs/level4_stepB_run.log`.
- **Globs under `outputs/cora_breakthrough`.** `level4_stepB*` top-level files, `level4_blind_runtime_manifest.json`, `level4_provenance_firewall.json`, `level4_withheld_expectation_seal.json`, `concept_registry.json`.
- **Trees, bytecode caches excluded.** `level4_stepB_gate_outputs/**`, `level4_mechanism_inputs/**`, `MAIN/level4_stepB/`, `MAIN/level4_blind_runtime/`.

A file that appears in any pinned scope after the pin is `PIN_SCOPE_GREW_AFTER_FREEZE`. Because `verify_pin()` returns that outcome and fails on it, v1's separate `gate_pin_verify.py` wrapper is no longer needed for the purpose of making new files blocking.

The pin lives in `outputs/tti/stepB_gate/pin/`, written as one atomic directory, and is bound to its commit by the tracked record `docs/stepB_gate/pin_binding.json` (G1 step 9). An anchor record outside both checkouts names the same sha256 and commit.

The G2 module pin is the second pinned set (G2 steps 3 to 5). It records whole K-affecting roots with their file lists, extra files and cross-tree pairs. It excludes gate scripts, which the tool manifest governs. It is committed exactly once, and every stage after G2 re-verifies it.

### 15.3 Hash-only access path, and the extraction step

`GateGuard.hash_only(path)` returns a digest and a byte count at stages 2 and 11, for any class except `NEVER`, and never for a dev-worktree copy of a Step-B artifact. It reads bytes only through `freeze_pin.digest_and_lines`, under the C2 invariant, and records a ledger entry with access mode `HASH_ONLY`. It is built.

`GateGuard.extract(path, purpose, keys or key_path)` is the filtered extraction path, and it is built. It applies only to raw ARC data files and the Lockbox manifest. Purpose `promotion` is licensed at stage 7 once `g7b_open` is valid; purpose `etransfer` at stage 8 once `g8_open` is valid and until `g8_closed`. It verifies the file against both pins, then calls `cora_tti/split_extract.py`, which scans the JSON bytes for structure only, tracking string state and bracket nesting, and passes only licensed members to the JSON decoder. Unlicensed keys and values are never decoded, retained, printed or returned. Only their count is ledgered, with access mode `FILTERED_EXTRACT`. Malformed structure raises and yields nothing.

The extraction step, `gate_extract_splits.py`, is candidate-independent, declared, and NOT built. At G7b it resolves the Promotion ids from the Lockbox manifest by the SA-12 key path and writes `extracts/promotion_tasks.json` from the training challenges and training solutions files. At G8 entry it writes `extracts/etransfer_tasks.json` for the ids resolved at G7b. Every read goes through `GateGuard.extract`. The step is hashed in the tool manifest before `g3b_open`.

### 15.4 Rules

1. E_transfer opens exactly once, at G8, for the frozen admitted set after withdrawals, in one scripted run, ledgered. It is spent from the commit of `g7b_open`, whether or not G8 runs. Any second E_transfer pass other than the crash rule of G8 is `XFER-SECOND-ACCESS`, and every artifact of that pass carries `POST-INSPECTION-TOOLING`.
2. Promotion tasks may be evaluated repeatedly and never mined. Anything learned by looking at a Promotion task disqualifies that task as transfer evidence.
3. Lockbox200 is not run, inspected, traced or analysed at any point in this gate. A negative verdict does not open it.
4. The 120 public evaluation tasks are not run until after the single Lockbox evaluation.
5. Any read, glob, import or listing of a sealed path outside its licensed stage sets `TERM-VOID-PROTOCOL-BREACH`.
6. `tests/test_gate_isolation.py` keeps the existing substring blacklist for `cora_parent` and `cora_tti` unchanged, adds `withheld_expectation` to the forbidden markers, and guards gate scripts by a resolved-path allowlist plus an AST check instead of filename substrings. The substring approach would force exemptions for exactly the scripts that touch sealed data. The runtime `open()` audit hook makes the ledger the detector. The test runs at every stage boundary, and its count is recorded.

### 15.5 Guard facts, recorded

1. `GateGuard` has eight classes. `STEP_B_SOURCE` and `PRE_RUN_RECORDS` unlock at stage 3. `STEP_B_OUTPUTS` unlocks at stage 3 once `g3b_open` is valid. `E_TRANSFER_PROVENANCE` and `PROMOTION_DATA` unlock at stage 7 once `g7b_open` is valid. `E_TRANSFER` unlocks at stage 8 once `g8_open` is valid and closes for good once `g8_closed` is valid. `LOCKBOX` unlocks at stage 11 once `g11_complete` is valid, which requires `g8_closed` and a committed `LOCKBOX-ELIGIBLE` closure record, in code only. `NEVER` never unlocks.
2. The checkpoint journal and the withheld expectation seal are `NEVER`.
3. Every raw ARC data file is `LOCKBOX` wherever it lives, and so are the Lockbox manifest and every file under `data/` in either checkout. The training file contains Lockbox200 and E_transfer, so it is mixed, and no gate stage reads it except through `GateGuard.extract`.
4. The dev worktree holds separate copies, on different inodes, of several sealed-name Step-B artifacts. The main checkout is authoritative. The guard refuses `tti:outputs/cora_breakthrough/*` at every stage, for content and for hash-only access.
5. Sealed name stems are matched anywhere in a path, inside or outside both checkouts, and the strictest matching class wins, so a copied or moved sealed artifact keeps its class. Root-anchored rules apply next, and an unrecognized file under `outputs` or `logs` fails closed as `STEP_B_OUTPUTS`. Inside a checkout, an ancestor directory name cannot decide a class. A copy renamed without its sealed stem is not recognized by name (19 item 17). Gate results never carry a sealed stem. Every file under `extracts/` is sealed whatever its name: the Promotion extract as `PROMOTION_DATA`, anything else there as `E_TRANSFER`.
6. Not sealed: the run manifest, its hash file, the design hash file, the final output hash file and the run log in the main checkout, whose content the guard refuses at stages 1 and 2; and `tti:outputs/tti/stepB_gate/*`, except `extracts/` and any file with a sealed stem, which stay sealed.
7. Events are one-shot files, committed once with one distinct blob across all refs and the reflog, bound to the sha256 of the artifact they attest, required to follow their stage records, and chained to their predecessors (section 6). A rewritten, drifted or broken event raises `PinProvenanceError`.
8. After G2, construction and every read re-verify the commit-bound, anchored freeze pin and the committed module pin. A failure raises `PinProvenanceError`.
9. The guard refuses every write mode against the experiment tree and ledgers every decision, refusals, hash-only reads and filtered extractions included.
10. The guard permits Lockbox-class reads only after `g11_complete`. That is code permission, not a license (G11).
11. The guard ledgers only reads that pass through it. DR-11 additionally requires an `open()` audit hook, which is declared, not built, and required before `g3b_open` by P0.15.

---

## 16. Defect-to-control map

| Defect | Control |
|---|---|
| 1. Non-reproducibility from an unset hash seed | DR-03 enforced by `gate_preflight.py`; C5.2; runner environment captured from the live process into `stepB_run_env.json`, never read from the pin process |
| 2. Inert guards | DR-25 counters and positive controls; constructor pre-pass replacing a structural test that was inert by construction; additivity preflight negative control (7.4); criterion-1 evidence from `certified_sources`; `INERT-GUARD` listing |
| 3. Wrong-reasoner provenance | DR-04 config digest including substrate id and learner tables; DR-05 runtime state digest; G2 cross-tree identity; name-set assertions in 7.2; G10 differential on the substrate that produced 3A |
| 4. Error and necessity conflated | DR-12 six statuses; three-valued behaviour with an instrumentation hook; `CHECKER_ERROR` never counts as K failing; undefined output is `FAIL`; section 5 forbids reading the DEV-60 null as necessity or failure |
| 5. Incomplete baseline admitting a positive | 8.5 completeness predicate with cap counter; the reach rule of 8.1 enumerates K completely and counts any fitting program with the correct output as K succeeding; B and A from separate executions; additive comparison rule; retention with serialization-only deduplication and fixture F-E; per-program exception rule; repeat agreement rule; 8.8 real-task additivity check |
| 6. Vacuous probes | 12.4 non-vacuity floor; joint definedness in 12.5; heterogeneity recomputation at G4.6 |
| 7. Provenance drift | DR-02 launch-time reads; clean-tree preflight; P0.4 commits; pin readiness requiring runner exit; fail-closed verification with `PIN_SCOPE_GREW_AFTER_FREEZE`; commit-bound freeze pin and module pin; anchor outside both checkouts; one distinct blob across all refs; chained, hash-bound events; output-hash recomputation at G3b |
| 8. Post-hoc reinterpretation | DR-21 named primaries; admission rule of section 10 declared in advance; substrate order of section 11; both T branches of 8.4; frozen interpretations of 14.1; `REFUSE-PREREG-MISMATCH` |
| 9. Inverted or under-reported summaries | DR-24 sentence shape; DR-34; DR-35 regeneration; lost solves reported as prominently as gains |
| 10. Retrospective costs presented as predictions | DR-23 |
| 11. Degenerate rule caught late | G6 degeneracy pre-check recorded whether or not it fires; C5.3 |
| 12. Identity collision between pools | DR-16; DR-17; the dependence rule of 9.2, which fails closed until identity is resolved |
| 13. Label mistaken for certificate | L1 definition; DR-08; LR5; constructor pre-pass; L2 requiring measured B, P, U; L4 requiring an E_transfer six-leg witness |
| Selection mistaken for reach | reach rule of 8.1; `K_REACHABLE_SELECTION_ONLY`; `DIAG_SELECTION_ONLY_COUNT`; DR-39 |
| Mixed-class data files | no gate stage reads raw ARC data except through `GateGuard.extract`, which decodes licensed members only; per-split extracts; `LOCKBOX` class for every raw ARC file and the Lockbox manifest; DR-40 |
| Pre-freeze exposure (D1 to D8) | section 3 quarantine; schema and implementation assumptions checked at G3; live-tree dry runs refused |

---

## 17. Execution order

```
P0   while the runner is live: runner environment captured (P0.2, done 2026-09-14)
     before G1: preflight and G1 record writer built and committed; gitignore negation
     before G2: module pin writer; candidate-independent engine changes, wrappers, bridges (P0.8)
     -- readiness: STEP B FROZEN + level4_stepB_output_hash.txt + no live runner --
G1   preflight; readiness; collect twice, re-check, collect a third time; write the
     pin once, atomically; commit; bind with anchor; commit binding; verify; copy the
     anchor into the review record; environment caveats; lane mtimes
G2   module pin over K-affecting roots, files and cross-tree pairs; commit once;
     output hash file hashed only
G3a  guard stage 3: design source and pre-run records only; implementation assumptions
     and SA-15; import closure; additivity preflight with F-A to F-E and the negative
     control; substrate predicates; regression set; C5 suite; guard positive controls;
     protocol binding; tool manifest, g3a_record, event g3b_open
G3b  access ledger opened; output hash recomputed and compared; schema assumptions
     checked; N_retained recorded
G4   dossiers, induction surface, lane audit, heterogeneity, constructor pre-pass,
     separation certificates
G5   rungs assigned, ceiling L1
G6   S2 per extension; substrate selected and committed; reproduction control;
     degeneracy check; six legs on the pre-transfer pool; g6_record
G7a  real-task additivity (8.8); rungs L2 and L3; criteria 3 leg (a) and 5; admission;
     admitted set and g7a_record committed; event g7b_open
G7b  SA-11 to SA-13; provenance resolved; Promotion ids and extract through
     GateGuard.extract; criterion 4 and criterion 3 leg (b), withdrawal only;
     E_transfer list; withdrawals and g7b_record committed; event g8_open
G8   E_transfer extract through GateGuard.extract; identity and content-hash
     de-collision; one pass; 8.8; primary N_w; five secondaries; rungs L4;
     ledger committed; event g8_closed
G9   promotion manifest frozen, then promotion
G10  harness differential; rediscovery on the pre-transfer pool and Promotion;
     abstraction on the pre-transfer pool; K versus K + C; 3A and 3B separate
G11  completion record; Lockbox asserted closed; event g11_complete; report checked
```

Any stage may end the sequence. Ending with a recorded negative is a result. Ending with an inconclusive or substrate-incomplete code is recorded as such. A provenance stop is neither.

---

## 18. Sign-off checklist

```
[ ] P0.2 runner environment captured while the runner was live, or ENV-RUN-UNKNOWN recorded
[ ] P0.4 gitignore negation in place; every artifact commit verified with git ls-files
[ ] G1 readiness held: marker, output hash file, no live runner
[ ] G1 pin created once; committed; PIN_VERIFIED
[ ] G1 no digest comparison of determinism lanes; SA-10 mtimes recorded
[ ] G2 hash-only path used; cross-tree identity verified
[ ] G3a implementation assumptions resolved; guard positive controls fired
[ ] G3a additivity preflight run; negative control classified non-additive
[ ] G3a substrate predicates S1, S3a, S3b, S4, S5, S6 ledgered; regression set >= 20
[ ] G3a tool manifest committed before G3b
[ ] G3b schema assumptions checked; branches of SA-04, SA-08, SA-09 recorded
[ ] G3b N_retained recorded before any per-class field
[ ] G4 every class has all determinations and a separation code
[ ] G4 pre-pass firing count reported
[ ] G5 rungs assigned mechanically; label never read by a predicate
[ ] G6 S2 evaluated and substrate committed before any witness run
[ ] G6 every leg has an evidence object; B and A from separate executions
[ ] G6 program-level fold results only under DIAG_PROGRAM_LEVEL_LOO
[ ] G7 admission per section 10; admitted set committed before the firewall opened
[ ] G7 withdrawals committed before any E_transfer input was read
[ ] G8 E_transfer opened once; ledgered; stdout teed and hashed
[ ] G8 primary N_w reported before any secondary number
[ ] G9 promotion runner hashed inside its manifest before any decision
[ ] G10 harness differential passed on meta_v21; 3B only on an additive substrate
[ ] G10 3A and 3B reported separately
[ ] every guard counter reported, zeros included
[ ] every claim sentence carries rung, split, level, denominator and outcome code
[ ] no sentence claims non-definability, and none says the pin read no content
[ ] no citation of the DEV-60 arm as evidence against test-time extension
[ ] Lockbox200, the withheld expectation and the public eval untouched
[ ] exactly one terminal code recorded
[ ] G1 pin committed and bound; binding committed; both commits in RUN_HISTORY.md
[ ] G2 module pin committed once; nothing affecting K created after G2
[ ] B and A judged by the reach rule; DIAG_SELECTION_ONLY_COUNT reported
[ ] T judged on the single accepted program, one attempt, identical input set
[ ] no raw ARC data file read by any stage; extracts only
[ ] gate_report_check.py regenerated every number and blocked nothing
[ ] G1 anchor written outside both checkouts and copied into the review record
[ ] G1 pin and binding each have one distinct blob across all refs and the reflog
[ ] G2 module pin lists roots with file lists and cross-tree pairs; gate scripts excluded
[ ] G3a import closure inside the pinned roots; C5 suite committed before g3b_open
[ ] G3b output hash recomputed and matched, or OUTPUT_HASH_FORMULA_UNRECOVERABLE recorded
[ ] every event written once at its owning step, committed, chained and hash-bound
[ ] Promotion and E_transfer data read only through GateGuard.extract and the extracts
[ ] 8.8 real-task additivity checked at G7a and at the end of G8
[ ] every leg status agreed across all repeats, or the leg is INCONCLUSIVE
[ ] every halt handled per 14.1a; exactly one terminal code by the 14.1 precedence
```

---

## 19. Limitations recorded before the outcome

1. Separation is relative to a bounded enumeration (depth at most 5, per-type cap 4000), at most 144 frozen probes per candidate, one seed and one canonical equality. It rules out macro-hood only for compositions within that domain and depth. A composition definable only beyond depth 5 can separate. It never proves non-definability.
2. On pre-transfer tasks the proposal saw every demonstration. If the adaptive proposal driver is unavailable, L there is `NOT_MEASURED`, and no pre-transfer pair can be a claimable witness.
3. A macro has cost 1 and surface depth 1, so any reach result is partly about the depth and time budget. Only the pre-pass and the separation certificate separate reach from expressivity.
4. An extension with an induced slot fitted by a learner absent from `K_L4*` extends the language and its induction machinery, and this gate does not separate the two contributions.
5. K1-lane classes cannot supply U and are never extensions.
6. Held-out correctness may enter the record for the first time at G8. Whether it can enter earlier depends on the branch of 8.4 that holds.
7. The additive comparison rule may make a substrate unavailable when its ranking or early stopping changes the winner on a synthetic fixture K already solves. Substrate availability is decided only by the ledgered predicates, before the first witness run. A violation on real tasks is detected and handled by 8.8, and it never removes a recorded `FAIL`.
8. Arms run at a budget eight times Step B's. Reproduction disagreements caused by incompleteness are timing artifacts.
9. Evidence from G6 onward attaches to the class representative only. Step-B class equivalence conflated error with undefinedness.
10. De-collision is by task identity and by a content hash under one declared transform group. Near-duplicates outside that group, such as crops or added noise, are not detected.
11. Final-output and ablation instrumentation have never run anywhere in this tree before this gate.
12. E_transfer is spent by one pass.
13. The gate measures one system on one corpus. Nothing here supports a claim about ARC performance, which remains 185/1000 (v23, artifact-backed).
14. Implementation assumptions about pinned source were learned from pre-freeze reads (D3). They are checked at G3a but were not chosen blind.
15. B and A measure reach only within the bounded enumeration and the budget. A program outside those bounds is not considered.
16. The freeze pin's anchor is a second copy outside the repository, not a tamper-proof store. A rewrite that removes every ref, the reflog and the anchor is detectable only against the external review record.
17. Sealed names are matched anywhere in a path, but a copy renamed without its sealed stem cannot be recognized by name. The access ledger, the audit hook and the transcript scans are the controls for that case.
18. Nothing records the bytes between the freeze marker and the pin. The output-hash check at G3b detects an edit in that window only if SA-15 holds and the edit did not also rewrite the hash file and the run log consistently.
19. B, A and K_PLUS_E enumerate completely and deduplicate only by serialization, so they reach `RESOURCE_EXHAUSTED` more often than a pruned search would. That is the conservative direction.

---

## 20. Rejected defects

Every BLOCKING and SERIOUS finding from the three adversarial reviews of the original drafts remains fixed. These proposed remedies are rejected, and in each case the underlying defect is fixed by the mechanism named.

**R1. Rejected: "pinning may wait until the tooling is written."** The interval between readiness and the pin is the one window in which the output could be looked at while nothing is recorded. The pin needs no gate tooling beyond the preflight, so it is created at the first invocation after readiness holds. The real defect, that binding the confirmatory stamp to the marker would make an unfinished gate exploratory, is fixed by binding `POST-INSPECTION-TOOLING` to the event `g3b_open`. The pin reads bytes only under the C2 invariant.

**R2. Rejected: "scope the hash-seed requirement to order-dependent stages."** Deciding which stages are order-dependent is a judgement made under outcome pressure. The seed is required in every gate process. The pin's own bytes do not depend on the seed, because it is serialized with sorted keys; the seed matters for every stage after the pin. `gate_preflight.py` is built and committed before the freeze and enforces the seed before the pin tool runs, so there is no window in which readiness holds and enforcement is unavailable.

**R3. Rejected: "drop the secondary separation baseline."** It is the only measurement that tells `SEP-SEPARATED` apart from `SEP-MACRO-OVER-CONCEPT`. The sentence it licensed was the real defect, and 12.7 restricts it to one reachability sentence.

**R4. Rejected: "drop the pre-transfer witness stage because Step-B selection already implies it."** The stage carries the additive-condition B and A results, the reproduction disagreement count, the degeneracy check, adaptive L where available, and the L2 rung, which no longer rests on Step-B retention. Its limited independent content is stated in G6.

**R5. Rejected: "make the separating-probe zero-error condition global."** A global veto over thousands of executions would void every certificate. The real defect, baseline errors silently pushing toward separation, is fixed by the per-probe condition in 12.5(a) and `SEP-INCONCLUSIVE-BASELINE-ERRORS`.

---

## 21. Changes from v1

| # | Change | Reason |
|---|---|---|
| 1 | Protocol id `v2`, same path; supersession section; v1 kept in history | C1 |
| 2 | Every claim that the pin tool read no bytes removed; exact invariant stated in G1, 15.1 and R1; sentinel tests described as proving no leakage only | C2 |
| 3 | Pin readiness requires the marker, `level4_stepB_output_hash.txt`, and no live runner; freeze_pin outcome names adopted; nothing inspected when not ready | C3 |
| 4 | Fail-closed verification after G2 with seven outcomes; `GateGuard` verification at construction and on every read; `PinProvenanceError` stops the gate and is not a result; v1's `gate_pin_verify.py` wrapper declared unnecessary for making new files blocking | C4 |
| 5 | Live-tree dry runs retired; `DRY_RUN_REFUSED_ON_LIVE_TREE`; fixtures only | C5 |
| 6 | New section 3 with D1 to D8 and Q1 to Q6; schema assumptions SA-01 to SA-10 checked at G3; implementation assumptions checked at G3a; `SCHEMA_ASSUMPTION_FAILED` | C6(b), Q2 |
| 7 | v1 5.4 corpus-writer justification removed; T decided by a mechanical check with stated branches (8.4) | C6(a), Q3 |
| 8 | Quarantined premises removed, including v1 6.2.6's bridge sentence and v1 6.3's named inventory twins; rules restated generically | C6(c), Q1, Q5 |
| 9 | v1 G1 step 6 halt on lane digests removed; deferral to the recorded pre-run gates verdict, justified from pinned mtimes and the resume log | C6(d) |
| 10 | Section 5 records the DEV-60 real-engine finding in the body; v1 15.3 corrected: additivity of the meta_v21 and blind-runtime concept paths not verified | C7 |
| 11 | Section 7: additive comparison rule and additivity preflight with fixture classes and a negative control; `ADDITIVE_INSTALL_PATH_UNAVAILABLE` | C8 |
| 12 | W1 to W6 replaced by legs B, P, U, L, T, A with evidence objects and six statuses; v1 status words mapped; undefined output stays `FAIL`; "K plus e succeeds" absorbed into U and T; P added | C9 |
| 13 | v1 5.5 and DR-15 replaced by full adaptive leave-one-out; program-level check only as `DIAG_PROGRAM_LEVEL_LOO` | C10 |
| 14 | Section 10 admission rule; admission licenses measurement only; `WITNESS_SUBSTRATE_INCOMPLETE` terminal | C11 |
| 15 | Section 11 substrate decision tree with declared order and predicates | C12 |
| 16 | Guard facts recorded in 15.5; firewall and raw training data at stage 7; raw evaluation data in the Lockbox class; worktree copies never read | C13 |
| 17 | Every stage has the seven fields, including "Claim licensed" | C14 |
| 18 | Ladder restated so L2 rests on measured B, P, U instead of Step-B retention; rung assignment runs at G5, G7 and G8 | C9, C10: program-level LOO may not support a claim |
| 19 | Admitted set frozen before the firewall opens; criterion 4 and criterion 3 leg (b) moved after the freeze with withdrawal-only effect | C13: the firewall and raw training data unlock at stage 7, and v1 opened the firewall before its own freeze |
| 20 | G2 and G11 Lockbox and admissibility hashing routed through a declared hash-only path | the guard refuses those classes at stages 2 and 11 for content |
| 21 | P0.3 and the preflight moved into G3a | the guard seals Step-A, v21 and source paths until stage 3 |
| 22 | P0.2 identifies the runner by the freeze_pin identity rule, not a fixed pid | the restart script can change the pid |
| 23 | Implementation status appendix rewritten | C16 |
| 24 | Decision rules renumbered; DR-30 to DR-33 added; forbidden phrasings extended | C4, C6, C7, C12, C2 |
| 25 | Everything else in v1 kept, including decision rules, failure branch, rejected defects, and 185/1000 | C15 |
| 26 | B and A measure reach over the complete bounded enumeration, not K's first-ranked program; `K_REACHABLE_SELECTION_ONLY`; `DIAG_SELECTION_ONLY_COUNT` | review: a ranking effect could pass all six legs |
| 27 | T judged on the single accepted program in one attempt; B, T and A on the identical input set | review: a task can carry several test inputs |
| 28 | No gate stage reads a raw ARC data file; Promotion and E_transfer tasks reach stages only through per-split extracts | review, verified against `LOCKBOX_PROTOCOL.md`: the training file contains Lockbox200 and E_transfer |
| 29 | Guard classes split design source, pre-run records and run outputs; outputs gated on the committed tool manifest, the firewall and Promotion extract on the committed admitted set, the E_transfer extract on committed withdrawals; the journal and expectation seal never readable | review: guard stages were coarser than G3a, G3b, G7a and G7b |
| 30 | Pin written atomically and bound to its commit; G2 module pin commit-bound and re-verified at every construction and read | review: delete-and-repin was undetectable, and changes to K after G2 were unenforced |
| 31 | Nothing affecting K is created after G2; anything built after G3b is post-inspection for every Step-B extension permanently | review: a post-inspection bridge could support a later test chosen after seeing candidates |
| 32 | E_transfer counts as spent once the firewall is read at G7b | review: section 14.4 contradicted itself |
| 33 | Substrate availability decided only before the first witness run; a later winner change is handled by 8.8 (row 52) | review: section 19 item 7 allowed recoding a failure |
| 34 | Runner identity covers module, subdirectory and executable-link launches, and was checked against the live runner from `/proc` | review: some launch forms were invisible |
| 35 | `gate_preflight.py`, `gate_capture_run_env.py` and the hash-only path built; preflight failure branches declared | review: readiness could arrive before enforcement existed |
| 36 | Five one-shot, hash-bound, chained events replace HEAD-identity unlocks; stage records required; `LOCKBOX` needs `g11_complete`; E_transfer closes at `g8_closed` | round-2 review: events were satisfiable early, and a re-commit still unlocked |
| 37 | Sealed name stems matched anywhere in a path, strictest class winning | round-2 review: copies outside the checkout roots were unsealed |
| 38 | Built filtered extraction, `GateGuard.extract` over `split_extract.py`, for the training challenges and solutions files and the Lockbox manifest; DR-40 exception; solutions file named | round-2 review: the extraction step had no guarded path, and decoding the manifest exposed Lockbox ids |
| 39 | Freeze pin anchored outside both checkouts; one distinct blob across all refs and the reflog; `PIN_RECREATED_IN_HISTORY`, `PIN_ANCHOR_MISSING`, `PIN_ANCHOR_MISMATCH` | round-2 review: a pin recreated on another branch verified |
| 40 | Readiness re-checked and a third collection before the write; `PIN_WRITTEN_BUT_UNVERIFIED` terminal; a runner that never exits declared as a wait | round-2 review: failures after the write had no lawful branch |
| 41 | Module pin over whole K-affecting roots with file lists and cross-tree pairs; empty pin refused; gate scripts excluded; import closure checked at G3a | round-2 review: new files, one-tree files and outside imports went unchecked, and a script fix stopped the gate |
| 42 | No sizes or line counts in the pin except for the run log; the G2 pin reading ledgered | round-2 review: result sizes leaked before G3b |
| 43 | Tool manifest final at G3a; protocol binding check at G3a; header field null before `g3b_open`; G1 record writer declared | round-2 review: G1 needed an artifact that could not yet exist |
| 44 | Output hash recomputed from pinned bytes at G3b; SA-15 | round-2 review: changes between the marker and the pin went undetected |
| 45 | G3a, G3b, G7a and G7b each carry the seven fields; C5 suite generated at G3a over the type grammar | round-2 review: sub-stages lacked claims, and the C5 suite was shaped by sealed signatures |
| 46 | SA-11 to SA-15 checked at first licensed access; Q2 amended | round-2 review: firewall, manifest and E_transfer layouts could not be checked at G3 |
| 47 | Licensed reference for B and A limited to 8.4 branch 1 and the E_transfer extract; per-program exception and limit rule; depth fields and `DEPTH_COMPRESSION_ONLY` | round-2 review: branch-2 references, timeouts and depth compression could create witnesses |
| 48 | K_PLUS_E enumerates completely; accepted program pinned before references load; serialization-only deduplication; fixture F-E; retention fields | round-2 review: accepted-program ambiguity, and silent pruning of fitting programs |
| 49 | Repeat agreement rule; verdict precedence; `WITNESS-RECORD-INVALID`; L precedence with `LOO_MIN_FOLDS` | round-2 review: repeats had no aggregation, and verdicts had no total order |
| 50 | Leave-one-out rebuilds clustering, membership, retention, ordering and priors in every fold from a declared driver manifest | round-2 review: cluster-level leakage could pass L |
| 51 | Content-hash de-collision under a declared transform group at G8 entry; `XFER-SKIP-CONTENT-DUPLICATE` | round-2 review: recoloured or rotated duplicates passed identity de-collision |
| 52 | Real-task additivity check (8.8) with a recoding artifact; `ADDITIVITY_VIOLATED_ON_REAL_TASK` in stage vocabularies | round-2 review: the round-1 repair lived only in the limitations |
| 53 | Undecided constructor instances count as definable; secondary separation must be `SEP-SEPARATED` for L3; parameter-family quantifier declared; depth-5 wording limited | round-2 review: undecided instances escaped the structural cap |
| 54 | Terminal-code table with total precedence and reworded interpretations; `TERM-NO-L2`, `TERM-ADMIT-REFUSED-INTEGRITY`, `TERM-ALL-WITHDRAWN`, `TERM-L4-NOT-PROMOTED`, `TERM-PROMOTED`, `TERM-RESIDUAL`; `WITNESS_SUBSTRATE_INCOMPLETE` keyed on separated classes without a substrate | round-2 review: some end states matched no row, and interpretations claimed more than their triggers |
| 55 | Halts declared terminal or resumable (14.1a); gate-halting codes removed from per-class admission bars | round-2 review: halts had no terminal code or resume rule |
| 56 | L4 requires criterion 6; LR2 names unmeasured predicates as unmeasured; 14.3 and 14.4 apply to every terminal code | round-2 review: criterion 6 and the citation rules were incomplete |
| 57 | Protocol artifacts hashed only at G1 and G2, content from G3a, enforced by the guard; DR-10 exception | round-2 review: DR-10 contradicted 15.1 |
| 58 | E_transfer spent at `g7b_open`; restarts stamped; G8 runner hashed before `g3b_open` | round-2 review: nothing marked E_transfer spent |
| 59 | G9 pins extract hashes, not raw data hashes; G10 rediscovery limited to licensed pools; G11 counts unlicensed ids without reading the Lockbox list | round-2 review: raw-data references remained |
| 60 | Preflight covers tooling by glob and runs git without optional locks; usage errors reported as outcomes; environment caveats derived from the committed capture | round-2 review: tooling mismatches |
| 61 | `g11_complete` follows `g8_closed` and requires a committed `LOCKBOX-ELIGIBLE` closure record; every file under `extracts/` sealed; one G8 runner rule with the `XFER-CRASH-RERUN` stamp; the audit hook required by P0.15 | fix-verification review: the Lockbox event could be written at any stage, and the runner and hook rules conflicted |
| 62 | Digests null before `g3b_open`; stages before `g3b_open` record the scripts they ran; module pin roots declared; bind write order and crash branches declared; output-hash check also compares the run log and claims consistency only | fix-verification review: pins and preflight |
| 63 | G7 rungs assigned after the 8.8 recoding; 8.8 has no criterion-3 effect; `TERM-ALL-EQUIVALENT` excludes caps resting on undecided instances; depth diagnostic declared inert above L2; inconclusive L2 legs route to `TERM-INCONCLUSIVE-G6`; G10 pools named | fix-verification review: witness and ladder |

---

## 22. Implementation status

This appendix states what exists when v2 is frozen. It changes no rule above and is updated only by appending.

### 22.1 Built and tested

| Artifact | State |
|---|---|
| `cora_tti/freeze_pin.py` | pin version `stepB_capability_gate_pin:v3`; binding with anchor; module pin writer and verifier `stepB_gate_module_pin:v2` |
| `scripts/pin_stepB_freeze.py` | command line: create, `--bind`, `--verify`, `--verify --require-binding`, `--verify-modules`, and `--dry-run` on fixtures only; usage errors reported as `CLI_USAGE_ERROR` |
| `cora_tti/gate_guard.py` | eight classes; five one-shot, hash-bound, chained events; sealed stems matched anywhere; hash-only path; filtered extraction |
| `cora_tti/split_extract.py` | structure-only JSON scanner that decodes licensed members only |
| `scripts/gate_preflight.py` | enforces seed, thread limits, committed tooling by glob and a clean dev worktree; runs git without optional locks; writes nothing |
| `scripts/gate_capture_run_env.py` | P0.2 capture; values only for allowlisted variables, others counted; `run_env_caveats()` |
| `scripts/check_gate_protocol_v2.py` | mechanical checklist over this document; a floor, not a review |

Every suite ran under a CPython audit hook that recorded zero touches of the live experiment tree. A canary confirmed that the hook records a touch it is told to forbid.

| Suite | Tests |
|---|---|
| `tests/test_stepB_freeze_pin.py` | 65 |
| `tests/test_gate_guard.py` | 64 |
| `tests/test_gate_preflight.py` | 13 |
| `tests/test_gate_capture_run_env.py` | 8 |
| `tests/test_split_extract.py` | 12 |

What `freeze_pin.py` does:
- enforces the three readiness conditions before hashing anything, with runner identity covering script, module, subdirectory and executable-link launches;
- collects twice and refuses on disagreement, then re-checks readiness and collects a third time just before the write;
- records sizes and line counts for the run log only;
- writes the pin and its digest as one atomic directory, never overwriting;
- binds the committed pin to its commit through a tracked record and an anchor outside both checkouts, and detects a pin deleted and recreated, or recreated on another ref;
- writes and verifies the module pin over roots with file lists and cross-tree pairs, refusing an empty pin;
- fails closed on a missing, drifted or newly appeared file, and on an altered pin or binding;
- refuses dry runs on the live tree before reading anything.

What `freeze_pin.py` does not do: it records the pin process's `PYTHONHASHSEED` without enforcing it. The preflight enforces it.

What `gate_guard.py` does not do: it has no `open()` audit hook, so reads that bypass it are not ledgered, and it cannot recognize a sealed artifact renamed without its sealed stem.

### 22.2 Declared and NOT built

- **Execution infrastructure:** the `open()` audit hook; `gate_g1_record.py`; `gate_module_pin.py`, a thin caller of the built writer; `gate_extract_splits.py`, a thin caller of the built `GateGuard.extract`; `gate_output_hash_recompute.py`; `gate_import_closure.py`; `loo_driver_manifest.json`; `c5_suite.json` generation; `tests/test_gate_isolation.py`; `gate_tool_manifest.json`.
- **Checks at G3:** the implementation-assumption resolver and the schema-assumption checker; `gate_regression_set_freeze.py`; the guard positive-control fixtures.
- **Witness machinery:** the additivity preflight, with fixture classes F-A to F-D and the negative control; the substrate capability checks S1 to S6; any candidate-independent additive wrapper or `SUB-V21-BRIDGE`; the complete-enumeration reach check for B and A; the six-leg witness runner with evidence objects, `gate_witness.py`; the adaptive leave-one-out harness, including the per-fold proposal driver; the final-output instrumentation; the independent ablation runner.
- **Stage scripts:** `gate_inspect.py`; `gate_dossier.py`; `gate_constructor_prepass.py`; `gate_separation_certificate.py`, including `behaviour_typed`, the instrumentation hook and the open-term baseline; `gate_rung.py`; `gate_criteria_345.py`; `gate_admit.py`; `gate_etransfer_runner.py`; `gate_promotion_freeze.py`; `gate_promote.py`; `gate_level3_rerun.py`; `gate_post_promotion.py`; `gate_lockbox_closure.py`.
- **Reporting:** `gate_report.py`; `gate_report_check.py`.

The separation certificate has no existing implementation to adapt. Nothing in the tree enumerates `F(K_L4*)` and compares behaviours. The witness half exists in the pinned probe generator. `final_output_correct` and the ablation leg have never been computed anywhere in the tree. Under 2.7, candidate-independent gate scripts may be completed or fixed until `g3b_open`, and anything affecting K before G2. Anything built after G3b carries `POST-INSPECTION-TOOLING`.

### 22.3 Pre-freeze execution record

P0.2 ran on 2026-09-14 while the runner was live, reading `/proc` only. Outcome `ENV_CAPTURED`: 21 runner processes, all sharing one environment block. The runner identity rule of G1 step 4 matched the same 21 processes, including the parent.

Among the allowlisted reproducibility variables, the runner's environment sets `LANG` and `VIRTUAL_ENV`. It does not set `PYTHONHASHSEED`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS` or `OPENBLAS_NUM_THREADS`. The other 66 variables were counted, not named. The record is committed as `outputs/tti/stepB_gate/stepB_run_env.json`.

G1 therefore records `ENV-HASHSEED-UNSET-AT-RUN` as a standing environment caveat on the Step-B run. This is recorded before any outcome exists. The pre-run determinism gate's masked-identical verdict is the recorded mitigation, and no rule in this protocol is relaxed on account of the caveat.
