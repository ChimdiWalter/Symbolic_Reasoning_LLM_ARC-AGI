# CORA Capability-Growth Gate

**Protocol id:** `CORA_CAPABILITY_GROWTH_GATE:v1`
**Path:** `docs/CORA_CAPABILITY_GROWTH_GATE.md`, branch `cora-tti-dev`
**Status:** FROZEN ON COMMIT. Written and committed while Step B is still running and before any Step-B output has been read.

Two trees are referenced throughout.

```
MAIN = /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project
TTI  = /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
```

MAIN holds the live experiment. TTI holds this gate. No gate stage writes into MAIN.

---

## 1. Purpose, and what this is NOT

### 1.1 Purpose

This document is the sole authority over everything that happens between the moment the Step-B run log prints `STEP B FROZEN` and the moment Lockbox200 is either opened or recorded as staying closed.

The scientific question is narrow. CORA has demonstrated search and prior transfer, and narrow predictive-selection transfer, and narrow abstraction information. It has failed to demonstrate that a learned abstraction beats concrete memory, and failed to demonstrate bounded search-reach gain. What is unproven is whether failure can produce genuinely new operational capability: whether `K` becomes `K' = K union {e}` in a way that is verifiable, causally load-bearing, and not a renaming of something `K` already denotes.

The gate exists to stop a non-discovery from being recorded as a capability-growth witness, and to make a negative result easy to reach, cheap to record, and impossible to convert into a positive by restatement.

### 1.2 What this is NOT

1. It is not a scoring exercise. No stage produces an ARC number. The sealed number stays 185/1000 (v23, artifact-backed) until a new sealed measurement exists.
2. It is not a proof of non-definability. Every separation result is relative to a bounded enumeration, a frozen probe set, one seed, and one equality relation. Global non-definability is not provable here and is never claimed.
3. It is not a tuning loop. Nothing observed inside the gate justifies changing anything the gate measures.
4. It is not a promotion pipeline for near misses. There is no partial witness, no partial rung, no provisional promotion.
5. It is not a re-run mechanism. A negative result terminates the gate. It does not license a second Step-B run with adjusted inventory, thresholds, or bounds.
6. It does not open Lockbox200 or the 120 public evaluation tasks. That decision belongs to a separate, separately frozen document.

---

## 2. Pre-registration statement

This document was written before the Step-B outcome exists. At the time of writing, `MAIN/RESUME_STAGE1.md` records pid 106593 still running, no final output hash, and no `STEP B FROZEN` marker. `TTI/outputs/tti/stepB_gate/` is empty. `scripts/pin_stepB_freeze.py` exists and has never been run. No sealed Step-B artifact has been opened by any author of this document.

Every decision rule, every literal constant, every outcome code, and every frozen interpretation below was fixed before any result was visible. That timing is the point.

### 2.1 Order of authority

| Rank | Document | Pin prefix |
|---|---|---|
| 1 | `docs/CORA_LEVEL4_MANIFEST.md`, criteria 1 to 6 and the standing prohibitions | `607ed54c305d` |
| 2 | `docs/CORA_LEVEL4_STEPB_DESIGN.md`, the separation certificate and the frozen Step-B interpretations | `28cc8734330345bf` |
| 3 | `docs/LOCKBOX_PROTOCOL.md`, split rules | `1d0b0a5af606` |
| 4 | `docs/CORA_DATA_ACCESS_DAG.md`, access edges and their order | recorded at P0 |
| 5 | This document | recorded at P0 |

Where this document is stricter than a source above, this document governs. Where this document appears looser, the source above governs and this document is defective and is amended under 2.3.

### 2.2 Additive changes declared here

Each is declared now, before any outcome, and each is either strictly harder to pass than the source position or is a correction of a demonstrated implementation error.

| Change | Source position | Position taken here | Direction |
|---|---|---|---|
| Separation baseline space | closed terms of the result type | open terms of the candidate's own interface, applied to the same argument tuple | harder |
| MAX_CANDIDATES truncation of the baseline | 8 | no truncation; the whole enumeration | harder |
| Early stopping in the baseline enumeration | `search()` stops at the first fitting depth | no early stopping | harder |
| Wall clock in the baseline enumeration | 8 s search budget | no clock inside the enumeration; a declared per-candidate ceiling instead | harder |
| Separating witness robustness | one probe | at least 3 probes spanning at least 2 contexts, and no baseline term agreeing on every jointly defined probe | harder |
| Criterion 6 endpoint | "transfers to at least one task outside its invention provenance" | that transfer instance must itself be a full six-part witness | harder |
| Gate arm budget | 8.0 s | 64.0 s, applied identically to every arm | harder for W1 and W6, symmetric |
| Errors | collapsed to `None` by three separate `except Exception` layers | instrumented evaluator recording the exception class, pinned as part of the config digest | correction |

### 2.3 Amendment rule

After this document's sha256 is recorded in `gate_tool_manifest.json`, no sentence may be changed except by a dated amendment appended at the end, naming the pre-existing, outcome-blind evidence that forces it. An amendment may only tighten: it may make a positive result harder to obtain and never easier. Any proposed change that would make a positive easier is refused and the refusal is recorded. No amendment at all is permitted between the appearance of `STEP B FROZEN` and the completion of stage G8. An amendment written after any Step-B record has been read is void for every claim depending on that record.

An implementation defect in a gate script justifies correcting the script so that it performs what this document declares. It never justifies changing what this document declares.

### 2.4 The frozen constants

Every number the gate uses is fixed here. None is chosen later.

| Constant | Value | Applies to |
|---|---|---|
| `PYTHONHASHSEED` | `0` | every gate process |
| `OMP_NUM_THREADS`, `MKL_NUM_THREADS` | `1` | every gate process |
| gate worker count | `1` | every gate process |
| `ARC_META_BUDGET_S` for all gate arms | `64.0` | G6, G8, G9, G10 |
| `GATE_REPEATS` | `3` | every arm in G6, G8, G10 |
| `WITNESS_SEED` | `424242` | frozen probe generator, unchanged |
| `SEP_CONTEXTS` | `6` | from `witnesses.BOUNDS`, unchanged |
| `SEP_ARG_COMBOS` | `24` | `witnesses.behaviour` default, unchanged |
| `SEP_MAX_DEPTH` | `5` | separation enumeration |
| `SEP_PER_TYPE_CAP` | `4000` | separation enumeration |
| `SEP_MAX_CANDIDATES` | none | truncation removed |
| `SEP_ENUM_CEILING_S` | `3600` | per candidate, wall clock |
| `SEP_DEF_MIN` | `8` | non-vacuity floor, defined probes |
| `SEP_CTX_MIN` | `2` | non-vacuity floor, distinct contexts |
| `SEP_MIN_SEPARATING_PROBES` | `3` | robustness floor |
| `SEP_MIN_SEPARATING_CONTEXTS` | `2` | robustness floor |
| `CE_SEED` | `828282` | criterion-5 counterexample generator |
| `CRIT3_MIN_TASKS` | `20` | minimum regression-set size |
| `LOO_MIN_FOLDS` | `2` | below this, W4 is inconclusive |
| `E_transfer` size | resolved from the split manifest and recorded; the record states 150 | G8 |

### 2.5 Pre-freeze obligations (P0)

These must be complete and committed BEFORE the first content-bearing read at G3. They are not gate stages.

| Id | Obligation | Status at drafting |
|---|---|---|
| P0.1 | `gate_tool_manifest.json` recording the sha256 of this document and of every gate script | not written |
| P0.2 | `scripts/gate_capture_run_env.py` runs while pid 106593 is alive, recording `/proc/106593/environ` and `/proc/106593/cmdline` into `stepB_run_env.json` | not written, time critical |
| P0.3 | `scripts/gate_regression_set_freeze.py` writes and hashes the criterion-3 regression set from `level4_stepA_fold_summary.json`, `v21_level3a_certification.json` and `v21_promotion_results.json` | not written |
| P0.4 | `.gitignore` carries `!outputs/tti/stepB_gate/**` and `!outputs/tti/stepB_gate/*.txt`, and every gate script commits its artifact with `git add -f` and verifies with `git ls-files --error-unmatch` | not done |
| P0.5 | `tests/test_gate_isolation.py` extends isolation to the gate scripts by resolved-path allowlist plus AST check, and adds `withheld_expectation` to the forbidden markers | not written |
| P0.6 | every gate script listed in section 4 exists, is committed, and is hashed in the tool manifest | one of twenty-two exists |

**P0 rule.** A gate stage may execute only a script whose sha256 appears in `gate_tool_manifest.json` as committed before the G3 access-ledger opening event. A script committed after that point may still be used, but every artifact it produces carries the permanent stamp `POST-INSPECTION-TOOLING` and every claim consuming that artifact is reported as exploratory, never confirmatory. The stamp propagates.

The stamp binds to the first content-bearing read, not to the freeze marker, because what makes tooling confirmatory is that it was written without knowledge of the outcome, and the outcome becomes knowable at G3.

**P0.4 exists because `TTI/.gitignore` ignores `outputs/`, `*.txt` and `RESUME*.md`.** Verified. Without the negation, a plain `git add` of the pin, the tool manifest, the access ledger, the eligible set, or the pin hash file silently does nothing, and the entire anti-restatement architecture rests on commits that never happened.

---

## 3. The claim ladder

The project record contains three overlapping formulations of this ladder and no canonical one. This section is the canonical one. Rungs are strictly nested. A rung is assigned mechanically by `scripts/gate_rung.py` from recorded outcome codes. No person assigns a rung.

### L1. Generation-lane candidate

**Predicate:** the class is present in the pinned Step-B merged output with `lane == "K2"`.

**Licenses:** that the K2 vocabulary emitted this proposal.

**Does not license:** any statement containing the words new, novel, invented, semantic, extension, or capability.

`candidates.LABELS` is a bijection with `lane`, so `label` carries no information `lane` does not. `lane` itself is provenance about which vocabulary generated the term, not evidence of novelty. The rung predicate reads `lane`; the label is copied into artifacts under the field name `generation_lane_label` and is never read by any predicate.

### L2. Operational language extension

**Predicate:** L1, and `kept_for` is non-empty with at least two certified source tokens in at least one cluster, and criterion 2 (complete leave-one-out by rediscovery under the unchanged verifier) holds on each certifying source, and the class carries at least one `PROVENANCE-CERTIFIED` six-part record at G6.

**Licenses:** the set of solutions reachable under the fixed budget grew when `e` was installed.

**Does not license:** any statement that the language denotes something it could not denote before. A macro over `K_L4*` reaches L2 exactly as easily as a genuine new semantics. L2 is where a re-expression result lands. Permitted phrasing: "reachable under the fixed budget", "the bounded search reached". Forbidden at L2: "new semantics", "not expressible", "outside the language".

### L3. Semantic expressivity extension, bounded

**Predicate:** L2, and `SEP-SEPARATED` under section 6 against `F(K_L4*)` as the primary baseline, and the constructor pre-pass of 6.3 did not stamp the class `MACRO-OVER-K-L4STAR-STRUCTURAL`.

**Licenses:** on a bounded, frozen, candidate-independent probe domain, and under the declared enumeration bounds, `e` produces a behaviour that no open term of the prior production set produces on the same inputs.

**Does not license:** that `e` is undefinable in `K_L4*`; that `e` is useful; any sentence without its bounds attached. Permitted phrasing: "no term of the bounded enumeration of `K_L4*` at depth at most 5 under a per-type cap of 4000, over the frozen witness set, reproduces this behaviour on the recorded probes". Forbidden: "e is not expressible in `K_L4*`".

### L4. Semantic invention, bounded

**Predicate:** L3, and at least one CAPABILITY-GROWTH WITNESS whose `pool` field is `E_TRANSFER`, on a task outside `e`'s invention provenance by identity, under the single-pass rules of G8, and criteria 3, 4 and 5 all `PASS`.

**Licenses:** the conjunction, stated only in this form and only with the caveats of section 13 attached: an operator generated from certified failures under a frozen blind proposal language, accepted only through complete leave-one-out re-induction, separated from the bounded enumeration of the prior language, causally necessary for a correct held-out output on a task that took no part in inventing it.

**Does not license:** priority claims; ARC score claims; generality claims; the word "general"; any claim that the extension itself was re-invented from held-out demonstrations.

### Ladder rules

**LR1.** A report sentence naming a candidate carries its rung code in the same sentence. The strings `NEW_SEMANTIC_PRODUCTION`, "new production", "invented", "extension" may not appear in a claim sentence without the rung code.

**LR2.** A rung is never described as essentially, effectively, or nearly the next rung. The report states the achieved rung and names the exact predicate that failed.

**LR3.** There is no partial rung and no partial witness. The phrases "partial witness", "near witness", "near miss", "would have passed but for" are forbidden in every gate artifact and every downstream document.

**LR4.** Counts are reported per rung, never as one total. The permitted summary form is "n K2-lane kept classes, of which a at L2, b at L3, c at L4". A summary line reading "n new semantic productions" is prohibited.

**LR5.** Any output that prints `NEW_SEMANTIC_PRODUCTION` prints the class's separation outcome code in the same table row.

**LR6.** K1-lane classes are repairs. They may reach L2 and no higher. Their separation code is `SEP-NOT-APPLICABLE-K1-LANE`, they are refused admission to E_transfer, and they are reported under their own heading with their own claim limit. In `resolve()` the `uses` field short-circuits to true for lane K1, so a K1 class can never satisfy W3 and can never be part of a witness.

---

## 4. The eleven stages

Stages G1 to G11 correspond one to one and in order with the user's eleven steps. No stage is reordered, skipped, merged, or run ahead of its predecessor. Every stage writes one artifact to `TTI/outputs/tti/stepB_gate/` with a sibling `<name>_hash.txt`. Every artifact is immutable: a stage finding its own artifact present exits `REFUSE-ALREADY-RUN` and changes nothing.

### 4.0 The common artifact header

Every artifact begins with the same header. A stage that cannot fill every field refuses to run.

```json
{
  "artifact": "stepB_gate/<name>.json",
  "stage": "G4b",
  "protocol_sha256": "<sha256 of this document>",
  "tool_manifest_sha256": "...",
  "pin_sha256": "...",
  "config_digest": "<see DR-04>",
  "runtime_state_digest": "<see DR-05>",
  "git_at_launch": {"tree": "...", "head": "...", "dirty_file_count": 0},
  "git_at_write":  {"tree": "...", "head": "...", "dirty_file_count": 0},
  "environment": {"python": "...", "pythonhashseed": "0",
                  "arc_meta_budget_s": 64.0, "omp_num_threads": "1",
                  "workers": 1, "platform": "..."},
  "started_utc": "...", "finished_utc": "...",
  "stage_outcome": "STAGE-OK",
  "guards": {"<name>": {"evaluated": 0, "fired": 0}},
  "inert_guards": [],
  "counts": {}, "records": []
}
```

`git_at_launch` is read in the first action of the process, before any input file is opened. `git_at_write` is read immediately before serialization. A difference in `head` sets `STAGE-PROVENANCE-DRIFT` and the artifact is unusable downstream.

### 4.1 Gate scripts

| Stage | Script | Exists |
|---|---|---|
| P0 | `scripts/gate_preflight.py` | no |
| P0 | `scripts/gate_capture_run_env.py` | no |
| P0 | `scripts/gate_regression_set_freeze.py` | no |
| G1 | `scripts/pin_stepB_freeze.py` | yes, never run |
| G1 | `scripts/gate_pin_verify.py` | no |
| G2 | `scripts/gate_module_pin.py` | no |
| G3 | `scripts/gate_inspect.py` | no |
| G4 | `scripts/gate_dossier.py` | no |
| G4 | `scripts/gate_constructor_prepass.py` | no |
| G4 | `scripts/gate_separation_certificate.py` | no |
| G5 | `scripts/gate_rung.py` | no |
| G6 | `scripts/gate_witness.py` | no |
| G7 | `scripts/gate_criteria_345.py` | no |
| G7 | `scripts/gate_admit.py` | no |
| G8 | `scripts/gate_etransfer_runner.py` | no |
| G9 | `scripts/gate_promotion_freeze.py` | no |
| G9 | `scripts/gate_promote.py` | no |
| G10 | `scripts/gate_level3_rerun.py` | no |
| G10 | `scripts/gate_post_promotion.py` | no |
| G11 | `scripts/gate_lockbox_closure.py` | no |
| report | `scripts/gate_report.py`, `scripts/gate_report_check.py` | no |
| isolation | `tests/test_gate_isolation.py` | no |

---

### G1. Record and pin the final Step-B output hash before semantic inspection

**Entry condition.** The string `STEP B FROZEN` occurs at least once in `MAIN/logs/level4_stepB_run.log`, counted by streaming. `scripts/gate_preflight.py` has passed: `PYTHONHASHSEED` is set, both trees are porcelain clean, and P0.2 has produced `stepB_run_env.json` or recorded `ENV-RUN-UNKNOWN`.

**Exact procedure.**

1. Run `scripts/gate_preflight.py`. It ENFORCES the hash seed and the clean-tree condition and refuses otherwise. `pin_stepB_freeze.py` only RECORDS these values; it does not enforce them, and it is not edited by this gate.
2. Run `PYTHONHASHSEED=0 python3 scripts/pin_stepB_freeze.py` exactly once. It refuses before the marker, refuses to overwrite an existing pin, records sha256, bytes, mtime and line counts only, reads no content, and writes nothing into MAIN.
3. Commit the pin with `git add -f`, verify with `git ls-files --error-unmatch`, and record the commit hash in `RUN_HISTORY.md`. `RESUME_STAGE1.md` is not the record of record: it exists only in MAIN and is gitignored in both trees.
4. Verify the protocol binding: `git cat-file blob <head>:docs/CORA_CAPABILITY_GROWTH_GATE.md` must hash to the value in `gate_tool_manifest.json`.
5. Run `scripts/gate_pin_verify.py`. It invokes `pin_stepB_freeze.py --verify`, and additionally requires `appeared since pin: 0`. The pin script's own `verify()` fails only on drift or missing files and prints `PIN VERIFIED` even when new files have appeared under a pinned glob; the wrapper makes a new file blocking.
6. Read the determinism-lane output hashes (`ckpt`, `deta`, `detb`) as integrity metadata only. If lanes the run declares must agree do not agree, emit `PIN-NONDETERMINISTIC-LANES` and halt.

**Output artifact.** `stepB_freeze_pin.json`, `stepB_freeze_pin_hash.txt`, `gate_pin_verify.json`.

**Closed outcome vocabulary.** `PIN-OK`, `PIN-REFUSED-NO-MARKER`, `PIN-EXISTS`, `PIN-DRIFT`, `PIN-NEW-FILES`, `PIN-DIRTY-TREE`, `PIN-NONDETERMINISTIC-LANES`, `ENV-RUN-UNKNOWN`, `ENV-HASHSEED-UNSET-AT-RUN`.

**Refusal condition.** No marker, unset hash seed, dirty tree, or an existing pin.

**This stage does not license.** Any statement about what Step B produced. A pin is a statement about bytes.

---

### G2. Pin runner, manifest, candidate inventory and environment hashes

**Entry condition.** `PIN-OK` and the pin commit exists.

**Exact procedure.**

1. Confirm the G1 pin contains a record for each of: `scripts/cora_level4_stepB_run.py`, `level4_stepB/candidates.py`, the Step-B run manifest, the candidate inventory, `level4_blind_runtime_manifest.json`, `concept_registry.json`, the run log. Absence of any one emits `PIN2-INCOMPLETE` and halts.
2. Run `scripts/gate_module_pin.py`. It records sha256 for every file in `level4_stepB/` and `level4_blind_runtime/` in BOTH trees excluding `__pycache__`, for the four `geocat_arc/object_reasoning/meta_v21*` modules, for `MAIN/outputs/cora_breakthrough/level4_baseline_admissibility_v2.json`, for `MAIN/outputs/lockbox/manifest.json`, for the frozen split manifest, and for every gate script.
3. Cross-tree identity: for every file present in both trees under `level4_blind_runtime/` and `level4_stepB/`, the sha256 must be identical. Divergence emits `PIN2-DIVERGENT-COPIES` and halts.
4. Record the inventory's per-schema `executable_semantics.source_sha256`.

**Notes fixed here, not later.** The artifact that defines `K_L4*` is `level4_baseline_admissibility_v2.json`, which declares `supersedes`. `CORA_LEVEL4_MANIFEST.md` cites the v1 file; that citation is superseded by this sentence. Both files record `K_L4_star = 11` and `E_L4_star = 12`, so membership is not in dispute, but baseline size is the lever that controls separation difficulty and the exact file is therefore named and hashed. `MAIN/outputs/lockbox/manifest.json` is resolved against MAIN; it does not exist under TTI, and a null pin would let G11 assert closure against an absent file.

**Output artifact.** `stepB_gate_module_pin.json`.

**Closed outcome vocabulary.** `PIN2-OK`, `PIN2-INCOMPLETE`, `PIN2-DIVERGENT-COPIES`, `PIN2-TOOL-MISSING`, `PIN2-ARTIFACT-ABSENT`, `SEM-DRIFT`.

**Refusal condition.** Any pinned identity absent; any cross-tree divergence; the lockbox manifest or the admissibility artifact not found.

**This stage does not license.** Anything about content. G1 and G2 together establish only that the objects under discussion are fixed and identifiable.

---

### G3. Only then inspect the retained productions

**Entry condition.** `PIN-OK`, `PIN2-OK`, tool manifest committed, `gate_pin_verify.py` clean.

**Exact procedure.**

1. Run `gate_pin_verify.py` immediately before opening the first content-bearing file, and record the result.
2. Open `gate_access_ledger.jsonl`, append-only, and record this opening event. Every gate script installs an `open()` audit hook that appends every content-bearing read to the ledger. A claim depending on a file absent from the ledger is void.
3. Read the pinned Step-B merged outputs. Copy, into a gate-local immutable file, every class with `kept_for` non-empty, carrying `class_id`, `representative`, `members`, `lane`, `generation_lane_label`, `signature`, `behaviour_fingerprint`, `proposed_from`, `kept_for`, `independent_source_tokens`, `certified_sources` per cluster, and the per (candidate, source) resolution rows.
4. Record `N_retained`, the total class count, counts by lane, and the count with `kept_for` empty, BEFORE any per-class field is analysed.
5. Run `gate_pin_verify.py` again at session end. Drift emits `INSPECT-DRIFT` and halts.

**Retention rule.** The retained set is exactly the set of classes with non-empty `kept_for`. The gate does not add, drop, merge or re-rank classes. Every later table has exactly `N_retained` rows. A row is never omitted for being uninteresting.

**Processing order.** The frozen order already written by the runner, `(-len(kept_for), -len(proposed_from), mdl, class_id)`. No candidate is reordered because of what it turns out to be.

**Output artifact.** `retained_classes.json`, `gate_access_ledger.jsonl`.

**Closed outcome vocabulary.** `INSPECT-OPENED`, `INSPECT-DRIFT`, `INSPECT-OUT-OF-ORDER`.

**Refusal condition.** Pin not verified; ledger not writable and committable.

**This stage does not license.** Any interpretation. G3 is enumeration.

**Refutation condition.** `N_retained == 0` sets `TERM-NO-CANDIDATE` and the gate proceeds to the failure branch. E_transfer is not opened.

---

### G4. Per-candidate determination: interface, sources, semantics, separation

For each retained class, all five determinations are recorded, even when the first already disqualifies the class.

**The object under test.** `e` is the class representative, `members[0]`, with no substitution at any later stage. If the representative fails a part and another member would pass, the class fails.

**G4.1 Typed interface.** From the inventory record: `signature`, arity, ordered argument roles with declared type expression and evaluation mode (port, terminal, induced), result-type rule, declared type variables. Codes `IFACE-OK`, `IFACE-MISSING`.

**G4.2 Proposing source set.** Record `proposed_from`, `kept_for`, per-cluster `certified_sources`, and `independent_source_tokens`. Criterion 1 evidence is `kept_for` non-empty with `len(certified_sources) >= 2` in at least one cluster. `independent_source_tokens` counts sources that PROPOSED, not sources that CERTIFIED, and is reported under that name only. Task identities are not resolved here. Codes `SRC-OK`, `SRC-UNDER-THRESHOLD`.

**G4.3 Exact executable semantics.** Record the schema's canonical serialization, the full elaboration into vocabulary members, and for EVERY inventory instance appearing in the representative's schema a record `{instance_name, schema_id, family, function, source_sha256}`. A single semantics function per class is not sufficient: a candidate is a term over possibly several instances. Verify each `source_sha256` against the live source before any execution. Codes `SEM-OK`, `SEM-DRIFT`, `SEM-SOURCE-MISSING`.

**G4.4 Induction surface.** Record every slot type of `e` that resolves through `k2_slots.TERMINALS` (`SetOp`, `Extremum`) or `k2_slots.INDUCED` (`Colour`, `IndexMap`, `Frame`), with the learner name. `install.installed()` adds these terminals, these induced types and these slot learners to the process globals. An extension carrying such a slot extends the language AND its induction machinery, and this gate does not separate the two contributions. Every report at L2 and above carries that sentence verbatim. Codes `IND-SURFACE-RECORDED`, `IND-SURFACE-EMPTY`.

**G4.5 Lane audit.** Compute the vocabulary of the declared lane from `FROZEN_BASE`, not from the live `V.REGISTRY`. In `_init_worker` the install context is entered before `candidates_for` runs and is deliberately never exited, so the live registry at proposal time contains the K2 instances and a K1-lane schema is not guaranteed by construction to be free of them. Assert that a K1 schema references no inventory instance and that a K2 schema references only names in `vocabulary("K2", instances)`. Codes `LANE-OK`, `LANE-VOCAB-MISMATCH`.

**G4.6 Class heterogeneity.** Step-B classes are keyed on `(lane, signature, behaviour_fingerprint)` where the fingerprint comes from `witnesses.behaviour`, which collapses exceptions into `None`. The gate's semantics are three-valued and therefore strictly finer. Recompute the three-valued behaviour for every member. Disagreement records `CLASS-HETEROGENEOUS` with the member ids. The class is not re-split; all evidence from G6 onward attaches to the representative only, and that is stated.

**G4.7 Separation.** Section 6 in full.

**Output artifact.** `candidate_dossiers.jsonl`, `constructor_prepass.json`, `separation_certificates.jsonl`.

**Closed outcome vocabulary.** The G4 codes above, plus the separation codes of section 6.

**Refusal condition.** `SEM-DRIFT` or `LANE-VOCAB-MISMATCH` halts the gate pending an integrity investigation. `SRC-UNDER-THRESHOLD` is inconsistent with retention and halts likewise.

**This stage does not license.** Any usefulness claim.

**Refutation condition.** If every retained class ends at `SEP-EQUIVALENT`, `SEP-MACRO-OVER-CONCEPT`, `SEP-DEFINEDNESS-ONLY`, `SEP-TOTALIZATION-ONLY`, `SEP-VACUOUS`, or `MACRO-OVER-K-L4STAR-STRUCTURAL`, the terminal code is `TERM-ALL-EQUIVALENT`. If any class ends in an inconclusive separation code and no class reaches `SEP-SEPARATED`, the terminal code is `TERM-INCONCLUSIVE-G4`.

---

### G5. Keep the four levels distinct

**Entry condition.** Every retained class carries a dossier and a separation code.

**Exact procedure.** Run `scripts/gate_rung.py`. Its signature is

```
assign(lane, signature, behaviour_fingerprint, structural_result,
       l2_evidence, separation_result) -> rung
```

It receives no label argument. It reads only recorded outcome codes and applies the predicates of section 3. It writes one row per class with class id, lane, `generation_lane_label`, certified-source counts, criterion-2 result, structural code, separation code, rung, and the identifier of the first predicate that failed.

A class whose required codes are missing is `RUNG-UNASSIGNABLE`, which is a defect in the gate and halts it until the missing code is produced.

The report must contain, verbatim, adjacent to the first table in which the label appears:

> `NEW_SEMANTIC_PRODUCTION` is the generation-lane label fixed at proposal time. It establishes nothing about novelty. Novelty is established only by the structural test and the separation certificate at rung L3.

**Output artifact.** `ladder_assignment.json`.

**Closed outcome vocabulary.** `RUNG-L1`, `RUNG-L2`, `RUNG-L3`, `RUNG-L4-PENDING-TRANSFER`, `RUNG-UNASSIGNABLE`.

**Refusal condition.** Any missing upstream code.

**This stage does not license.** Promotion of any candidate. Rungs describe evidence held so far.

---

### G6. The six-part conjunction on the invention-provenance pool

**Entry condition.** `RUNG-L3` for at least one class, or `RUNG-L2` classes to be recorded as repairs.

**Exact procedure.** Section 5 in full, with `pool = INVENTION_PROVENANCE`. Every part is evaluated for every (class, task) pair regardless of earlier failures, so the record is complete.

Before any witness is scored:

1. **Reproduction control.** Recompute Step B's own `found`, `uses_candidate` and `loo_passed == loo_folds` verdicts for each retained class and each certified source under the pinned gate configuration. Report agreements and disagreements as counts. A disagreement in which either execution was incomplete is `REPRO-DIFFERS-INCOMPLETE`, a timing artifact, and does not block. A disagreement in which both executions were complete is `WITNESS-NONREPRODUCIBLE-CERTIFICATION` and blocks admission for that class.
2. **Degeneracy pre-check.** Verify `e` is present in the treatment environment, reachable at the goal type, and changes at least one enumerated program at depth 1. Verify the treatment arm's accepted program set is not byte-identical to the baseline's across all provenance sources. Failure is `WITNESS-DEGENERATE-TREATMENT-EQUALS-CONTROL` and the class is not admitted. The check is recorded whether or not it fires.

**Output artifact.** `witness_conjunction_provenance.json`.

**Closed outcome vocabulary.** The per-part codes of section 5, plus `PROVENANCE-CERTIFIED`, `PROVENANCE-REFUTED`, `PROVENANCE-INCONCLUSIVE`, `WITNESS-DEGENERATE-TREATMENT-EQUALS-CONTROL`, `WITNESS-NONREPRODUCIBLE-CERTIFICATION`, `WITNESS-ARM-DISAGREE-TIMING`, `WITNESS-ARM-DISAGREE-STRUCTURAL`.

**Refusal condition.** `WITNESS-ARM-DISAGREE-STRUCTURAL` halts the gate.

**This stage does not license.** Held-out transfer of any kind, or L4. A provenance-pool record is tagged `LOO_REDISCOVERY`, never `HELD_OUT_OUTPUT`. On this pool W5 is entailed by W4 and therefore carries no independent information; the record says so, and the object has five independent parts.

**Honest statement of what this stage adds.** A kept class already satisfies W2, W3 and W4 on its provenance by the Step-B selection rule. G6's evidential content is therefore the reproduction disagreement count, the W1 and W6 completeness results under the raised symmetric budget, and the degeneracy check. Admission at G7 is a bookkeeping act built on those, not a new finding.

**Refutation condition.** If no L3 class produces a `PROVENANCE-CERTIFIED` record and every pair is decided, `TERM-NO-WITNESS`. If any pair is inconclusive and none is certified, `TERM-INCONCLUSIVE-G6`.

---

### G7. Only surviving, causally useful extensions proceed to E_transfer

**Entry condition.** G6 complete.

**Exact procedure.** An extension `e` is admitted if and only if all of:

| # | Requirement | Evidence |
|---|---|---|
| 1 | rung is L3 | `gate_rung.py` |
| 2 | at least one `PROVENANCE-CERTIFIED` record | G6 |
| 3 | criterion 3, no regression | G7.1 |
| 4 | criterion 4, no identity leak | G7.2 |
| 5 | criterion 5, survives counterexamples | G7.3 |
| 6 | no code in `{SEM-DRIFT, CONFIG-MISMATCH, RUNTIME-STATE-MISMATCH, ENV-UNVERIFIABLE, WITNESS-ARM-DISAGREE-STRUCTURAL, WITNESS-NONREPRODUCIBLE-CERTIFICATION, LANE-VOCAB-MISMATCH}` | all stages |

**G7.1 Criterion 3, no regression.** The regression set was frozen and hashed at P0.3 and is the union of every `E_invent` task certified under `E_L4*` before any extension (from `level4_stepA_fold_summary.json`) and every Promotion task certified in the Level-3A confirmatory run. Its size must be at least `CRIT3_MIN_TASKS = 20`, otherwise `REFUSE-REGRESSION-SET-TOO-SMALL`. The set size is printed beside every criterion-3 result, so that a pass over a small or empty set is visible. A task regresses if it was certified before and is not certified under `K_t + e` with an identical config digest except for the production set. Any regression rejects the extension and does not license modifying the extension, the search, the cost table, or the regression set. Any incomplete arm on a regression-set task is `CRIT3-INCONCLUSIVE`, which blocks the pass and is not a fail.

**G7.2 Criterion 4, no identity leak.** Run the existing executable leak check over the class's canonical serialization and the source text of every instance in it. The firewall-side tool checks the serialization against the forbidden-name pool and returns a boolean and a count without disclosing the pool. Any hit is `CRIT4-FAIL`.

**G7.3 Criterion 5, synthetic counterexamples.** The suite is generated by the frozen witness generator with `CE_SEED = 828282` plus a declared stress list, parameterised only by the extension's declared type signature and its recorded constructor family. It is generated and hashed BEFORE any candidate is examined and is identical for every candidate.

Stress list, declared now: empty cellset; 1x1 grid; maximum-side grid within `witnesses.BOUNDS`; full-alphabet grid; duplicate map keys; out-of-range index; mismatched shape pair.

| Sub-test | Pass condition |
|---|---|
| C5.1 robustness | no uncaught exception escapes the runtime containment on a typed-valid input |
| C5.2 determinism | two executions under `PYTHONHASHSEED` 0 and 1 give identical canonical output |
| C5.3 slot degeneracy | if the fitted slots take one value on every task where `e` was used, re-run the section 6 separation with the slots frozen to that constant; failure under the constant drops the rung to L2 and refuses promotion |
| C5.4 result type | every output is a value of the declared result type or `None` |
| C5.5 family property | as in the table below, by recorded `family` |

| Family | Property asserted |
|---|---|
| select | result is a sub-collection of the input; reapplication is idempotent |
| project | result kind equals the declared target kind |
| reindex | cardinality preserved; bijective on addresses where the declared map is bijective |
| aggregate | permutation invariance of the input collection |
| combine | defined on both argument orders where the declared type is symmetric |
| embed | the embedded value is recoverable by the declared projection where one exists |
| reduce | result kind equals the declared target kind; deterministic |

`NOT-APPLICABLE` must be justified by the recorded family and declared type, never by inspecting the extension's observed behaviour.

**Freezing the admitted set.** The admitted set is written to `etransfer_admitted_set.json` and its sha256 is committed BEFORE any E_transfer path is opened. The G8 runner refuses to execute unless the committed hash matches. The set may not be extended after the split opens, and no extension is withdrawn from it after results are seen.

**Firewall opening.** `level4_provenance_firewall.json` is opened here for the first time, only to resolve `source_token_to_task` for the admitted extensions and to compute the identity exclusion of G8. The opening is ledgered.

**Invention provenance, defined once.** The invention provenance of a class is the union of `proposed_from` over all members, resolved to task ids. This is the broadest of the three available sets, so the exclusion is conservative. `certified_sources` is reported and is never used for exclusion. Because `independent_source_tokens` is stored as a count rather than a set, identities are recovered from the per-candidate selection rows via `cluster_id`, which yields a superset of the true proposing set; that is conservative and is stated in the artifact.

**Output artifact.** `criteria_345.json`, `etransfer_admitted_set.json`.

**Closed outcome vocabulary.** `ADMIT-OK`, `ADMIT-REFUSED-NOT-L3`, `ADMIT-REFUSED-NO-PROVENANCE-CERT`, `ADMIT-REFUSED-CRITERION`, `ADMIT-REFUSED-INCONCLUSIVE`, `ADMIT-REFUSED-K1-LANE`, `CRIT3-PASS`, `CRIT3-FAIL`, `CRIT3-INCONCLUSIVE`, `CRIT4-PASS`, `CRIT4-FAIL`, `CRIT5-PASS`, `CRIT5-FAIL`, `CRIT5-INCONCLUSIVE`, `DEGENERATE-SLOTS`, `REFUSE-REGRESSION-SET-TOO-SMALL`.

**Refusal condition.** An empty admitted set. E_transfer is then not opened at all, code `XFER-NOT-OPENED`, and the gate goes to the failure branch. There is no exploratory peek, no sanity check, and no single-candidate exception. An unopened E_transfer remains available to a future, differently designed experiment; an opened one does not.

**This stage does not license.** Opening Promotion or Lockbox.

---

### G8. The frozen E_transfer evaluation

**Entry condition.** A non-empty admitted set whose hash is committed; `gate_etransfer_runner.py` written, unit-tested on synthetic fixtures, hash-pinned in the tool manifest, and committed before any E_transfer record is read.

**Exact procedure.**

1. Resolve the E_transfer task list from the firewall's `within_stage_holdout.E_transfer` and record the resolved count and the split-manifest hash. The record states 150; the resolved number is what is reported.
2. De-collide by identity only. Any E_transfer task whose id appears in the extension's invention provenance is excluded with `XFER-SKIP-IDENTITY` and the identity is recorded. No exclusion is by outcome, cost, difficulty, runtime, family, or apparent suitability. A task that errors or times out is not excluded; it is recorded with its code and stays in the denominator. Pool overlaps are reported even when the count is zero.
3. Run three arms per task per extension: baseline, treatment, ablation, as defined in section 5, `GATE_REPEATS = 3`, `ARC_META_BUDGET_S = 64.0`, single process, threads pinned.
4. Compute the primary and the five secondaries below.
5. Append one line to `etransfer_ledger.jsonl` per execution: timestamp, operator, script hash, admitted-set hash, config digest, runtime-state digest, arms run, task count, exit code, and the sha256 of the teed stdout file.

**Primary endpoint, declared before the split opens.**

```
N_w = the number of (extension, task) pairs on E_transfer, task outside the
      extension's invention provenance by identity, for which all six parts
      of section 5 record PASS with pool = E_TRANSFER.

N_w >= 1  ->  RUNG-L4 for those extensions, C6-PASS
N_w == 0  and every pair decided  ->  C6-FAIL, TERM-NO-TRANSFER
N_w == 0  and any pair inconclusive  ->  C6-INCONCLUSIVE, TERM-INCONCLUSIVE-G8
```

This is criterion 6, operationalised here in advance as the full six-part conjunction rather than as a bare solve. The frozen manifest's own wording is "it transfers to at least one task outside its invention provenance"; the tightening is declared, not inherited.

**The five preregistered secondary measurements.** Descriptive only. None may be promoted to primary.

| Id | Measurement | Mechanical definition |
|---|---|---|
| M1 | source-independent reuse | count of tasks outside provenance whose accepted treatment program satisfies `uses_concept(program, env, e)` |
| M2 | rediscovery | count of tasks where the treatment arm passes `loo_by_rediscovery` on every fold with no fold deadline hit, plus per-task folds passed over folds attempted |
| M3 | correct held-out outputs | count of tasks where the rendered test prediction equals the reference output exactly, reported for all three arms together |
| M4 | search and compute change | paired per-task deltas, treatment minus baseline; primary resource `SearchStats.typed`; secondary resources wall seconds and surface cost; negative means the treatment used less |
| M5 | dependence on the extension | count of M3 successes lost when `e` is removed, same tasks, same seeds, same budget |

Every measurement is reported with its denominator, the counts of `ERROR`, `TIMEOUT` and `INCOMPLETE`, and the number of identity exclusions. Every M4 number is labelled `MEASURED-RETROSPECTIVE`. The words forecast, projected, deployment estimate and expected cost are forbidden for M4.

**Single pass.** E_transfer opens exactly once for the admitted set. A second execution against the same set is refused. If the run crashes with no per-task outcome written to disk and none displayed, adjudicated by the hash of the results file and the hash of the teed stdout, the fault is fixed, the fixed script is hash-recorded, and one re-run is permitted and ledgered without downgrade. If any per-task outcome was written or displayed, the re-run is `XFER-SECOND-ACCESS` and every downstream claim carries that stamp. The distinction is decided by artifact evidence, never by recollection.

**No tuning.** After E_transfer opens, nothing changes: no parameter, budget, depth, cap, cost, ranking rule, verifier, learner, extension definition, or task selection. An observed E_transfer failure never justifies a repair. It is the result. If a defect in the gate implementation is found during the pass, the whole pass is voided and recorded as void, the defect is fixed and committed, and the pass restarts from the beginning; partial passes are never merged.

**No substitution.** If the primary fails, the report states that the primary failed, and that sentence precedes any secondary number.

**Output artifact.** `etransfer_results.json`, `etransfer_ledger.jsonl`, `etransfer_stdout.log`.

**Closed outcome vocabulary.** `XFER-OPENED-ONCE`, `XFER-NOT-OPENED`, `XFER-SECOND-ACCESS`, `XFER-SKIP-IDENTITY`, `XFER-POOL-COLLISION`, `C6-PASS`, `C6-FAIL`, `C6-INCONCLUSIVE`, `TUNING-BREACH`, plus per-task `PASS`, `FAIL`, `ERROR`, `TIMEOUT`, `INCOMPLETE`.

**Refusal condition.** Admitted-set hash mismatch; pin not verified; runner hash not in the tool manifest.

**This stage does not license.** Any statement about the ARC evaluation set, Lockbox200, the 120 public evaluation tasks, or the 1000-task census. It does not license the word "general".

---

### G9. Promote only according to the existing protocol

**Entry condition.** `C6-PASS` for at least one extension.

**Exact procedure.** The promotion manifest is frozen first, with the promoting runner's own hash inside it, and only then does the runner examine a single promotion decision. This copies the order of operations recorded in `scripts/cora_v21_freeze_promotion.py`, which exists because an earlier study froze the criteria but not the runner and lost a baseline leave-one-out that way.

An extension is adopted, giving `K_{t+1} = K_t union {e}`, only when all hold:

| Criterion | Text | Evidence |
|---|---|---|
| 1 | resolves the failures of at least two independent source tasks | `kept_for` non-empty with `certified_sources >= 2` |
| 2 | every one survives full leave-one-out by complete rediscovery under the unchanged verifier | W4 on each certifying source |
| 3 | no previously certified task regresses | `CRIT3-PASS` |
| 4 | semantics compact, no task id, family name or literal answer | `CRIT4-PASS` |
| 5 | survives synthetic counterexamples | `CRIT5-PASS` |
| 6 | transfers to at least one task outside its invention provenance | `C6-PASS` |
| additive | semantic separation certificate | `SEP-SEPARATED` and not `MACRO-OVER-K-L4STAR-STRUCTURAL` |

`level4_promotion_manifest.json` pins: the G1 pin hash, the G2 module pin hash, this document's hash, the promotion runner hash, the config digest, the runtime-state digest, the environment block, the regression set hash, the counterexample suite hash, the split manifest hash, the ARC data hashes, the admitted-set hash, the per-extension criterion table with every code, `unchanged_from_stepB` listing the verifier, the bounds, the cost table, the ranking rule, the slot learners, the 3A definition and the 3B definition, `only_change` naming `K_t -> K_t + {e}`, `all_arms_symmetric`, and a `claim_limit` block containing verbatim:

> A 3B witness would show that the set of solutions REACHABLE UNDER THE FIXED BUDGET grew. It would NOT show that the language can denote anything new, because the concept expands into K.

> Separation is established on a bounded frozen witness domain under the declared enumeration bounds. Global non-definability is not proved and is not claimed.

and forbidding by name the words untouched, pristine, fully prospective, and lockbox validation.

Frozen interpretations, fixed here: zero witnesses means accept the null and do not repair and rerun; Lockbox stays closed regardless of the outcome; any inconclusive criterion refuses promotion and is not a refutation either.

The registry update is append-only and versioned. `K_t` is retained verbatim so that every earlier result stays replayable. Promotion never edits, renames, retypes or re-costs an existing production, and never changes the verifier, `MAX_DEPTH`, `PER_TYPE_CAP`, `MAX_CANDIDATES`, the budget, the cost table, or the ranking rule. Any such change emits `PROMOTION-VOID` and terminates the gate.

**Output artifact.** `promotion_manifest.json`, `promotion_record.json`, `knowledge_state_K_t1.json`.

**Closed outcome vocabulary.** `PROMOTED`, `NOT-PROMOTED-CRITERION`, `NOT-PROMOTED-INCONCLUSIVE`, `PROMOTION-VOID`.

**Refusal condition.** Any criterion not `PASS`. There is no provisional, conditional, investigative, or engineering-convenience promotion.

**This stage does not license.** The claim that the system now solves more. That is measured at G10. Promotion is bookkeeping and does not raise a rung.

---

### G10. Rediscovery, automatic abstraction, K versus K plus C, ablation

**Entry condition.** At least one `PROMOTED` extension.

**Exact procedure.**

1. **Harness differential.** `scripts/gate_level3_rerun.py` reuses the three-arm structure of `scripts/cora_v21_phase5.py`. Before it is used on any extension it must reproduce the frozen `concept_0001` 3A result exactly, arm for arm and witness for witness, ON THE SUBSTRATE THAT PRODUCED IT, which is `geocat_arc.object_reasoning.meta_v21`. It cannot reproduce that result on `level4_blind_runtime`, because the blind runtime is a projection carrying eleven admitted productions plus `concept_0001` and its baseline arm is a strictly smaller language. The blind-runtime port is validated separately by the existing interpreter-equivalence artifact `level4_blind_equivalence.json`, and the four `meta_v21*` module hashes are pinned at G2 so that the stage the digest governs is the stage that runs. `scripts/cora_level3_transfer.py` is superseded: it imports the older `meta_induction` stack and is not used. `CORA_POST_STEPB_ROADMAP.md` line 46 names it; that reference is corrected here, before the outcome.
2. **Ordinary rediscovery.** Re-run the unguided discovery over the Experience families under `K_{t+1}` with the same budget and the same verifier. Report new certified solves, lost solves and unchanged solves, under `K_t` and `K_{t+1}` together or not at all. Lost solves are reported as prominently as gains and never hidden inside a net figure.
3. **Automatic abstraction.** Run the existing anti-unifier over the newly certified programs. A concept whose provenance is not two or more independent certified discoveries is rejected. Counts proposed and rejected are both reported. A concept written or edited by a person is a protocol breach. If anti-unification produces nothing, that is the result.
4. **Three arms and ablation**, on tasks outside provenance, with 3A and 3B evaluated and reported separately, criteria copied verbatim from the frozen manifest:

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

The preregistered resource for 3A is typed candidates enumerated, `SearchStats.typed`. Wall seconds and surface cost are secondary and are reported alongside. A 3A witness on seconds alone is not a 3A witness. A 3B witness is scored under the same six-part discipline and the same completeness predicate as section 5.

3A and 3B counts are never added, never averaged, and never reported under a single word such as transfer. Every sentence naming a count names the letter. A 3A result is never described as capability. A 3B result is never described as efficiency.

**Output artifact.** `level3_rerun.json`, `rediscovery.json`, `abstraction.json`.

**Closed outcome vocabulary.** `HARNESS-DIFFERENTIAL-PASS`, `HARNESS-DIFFERENTIAL-FAIL`, `RD-NEW`, `RD-LOST`, `ABS-PROPOSED`, `ABS-REJECTED`, `3A-WITNESS`, `3A-NONE`, `3B-WITNESS`, `3B-NONE`, `MEASURE-INCONCLUSIVE`.

**Refusal condition.** `HARNESS-DIFFERENTIAL-FAIL`.

**This stage does not license.** Any statement about ARC score.

---

### G11. Lockbox200 stays closed until the entire gate is complete

**Entry condition.** Every prior stage has written its artifact.

**Exact procedure.** G11 asserts closure. It does not open anything. It verifies that `MAIN/outputs/lockbox/manifest.json` hashes to the value pinned at G2, that no gate artifact contains a Lockbox task id, that `tests/test_gate_isolation.py` and `tests/test_cora_parent_isolation.py` both pass with their test counts recorded, and that the completion predicate holds:

1. every retained class carries a terminal rung code;
2. every stage G1 to G10 has an artifact whose sha256 is in `gate_completion_record.json`;
3. either the promotion branch or the failure branch is recorded with its terminal code;
4. `gate_pin_verify.py` is clean at completion time;
5. the completion record is committed and verified present in the index.

Lockbox eligibility requires the completion predicate AND at least one `RUNG-L4` AND `C6-PASS` AND no frozen criterion recording `FAIL` AND a declared system freeze with a hash. Otherwise Lockbox stays closed and the gate terminates with its recorded terminal code. Opening the Lockbox is not part of this gate: under the Lockbox protocol it requires the system and the concept library to be declared frozen, then exactly one evaluation whose number is reported as is, with no second attempt, no post-hoc repair round, and no re-freeze and rerun against the same Lockbox. The 120 public evaluation tasks are not run until after that single evaluation.

**Output artifact.** `lockbox_closure.json`, `gate_completion_record.json`, `capability_growth_gate_report.json` and `.md`.

**Closed outcome vocabulary.** `LOCKBOX-CLOSED`, `LOCKBOX-ELIGIBLE`, `LOCKBOX-BREACH`.

**Refusal condition.** Completion predicate false.

**This stage does not license.** Opening the Lockbox. It is a prohibition.

---

## 5. The capability-growth witness

A CAPABILITY-GROWTH WITNESS is an (extension, task) pair for which all six parts record `PASS`. There is no other definition and no other spelling. Every witness record carries a mandatory `pool` field with value `INVENTION_PROVENANCE` or `E_TRANSFER`. Only an `E_TRANSFER` witness supports L4.

### 5.1 The three arms

All three are constructed explicitly. The `without_concepts()` API is forbidden, because it returns `concepts={}` and would strip `concept_0001` as well as `e`, making the ablation strictly weaker than the baseline and letting W6 pass for the wrong reason.

| Arm | Environment |
|---|---|
| baseline | `LanguageEnv(base=FROZEN_BASE, concepts={"concept_0001": concept_0001})` |
| treatment | `LanguageEnv(base=FROZEN_BASE, concepts={"concept_0001": concept_0001, e.name: e})` |
| ablation | `LanguageEnv(base=FROZEN_BASE, concepts={"concept_0001": concept_0001})` |

Before any arm runs, assert `set(treatment.names) - set(ablation.names) == {e.name}` and `set(baseline.names) == set(ablation.names)`. Assert that no enumerated term in the baseline or ablation arm references a name outside `FROZEN_BASE union {concept_0001}`. All three arms run under the same active `install.installed(...)` context, the same evaluator, the same budget, the same seeds, the same repeats, and the same config and runtime-state digests. The single declared difference is the concept overlay.

### 5.2 The six parts

| Part | Statement | PASS condition | Other outcomes |
|---|---|---|---|
| W1 | baseline `K` fails | the baseline arm is COMPLETE per 5.3 and produced no correct held-out output | `FAIL` if it produced one; `INCOMPLETE`; `ERROR`; `TIMEOUT` |
| W2 | `K + e` succeeds | the treatment arm returned an accepted program | `FAIL`, `ERROR`, `TIMEOUT` |
| W3 | the accepted program uses `e` | `env.uses_concept(winning_surface_ast, env, e.name)` is true | `FAIL`; `USE-UNVERIFIABLE-LANE-K1` for any K1 class |
| W4 | the full required leave-one-out re-induction passes | `loo_by_rediscovery` passes on every fold in the treatment arm with no fold deadline hit and `loo_folds >= 2` | `FAIL` on a completed failing fold; `TIMEOUT` on a deadline fold; `INCONCLUSIVE` if `loo_folds < 2` |
| W5 | the final output is correct | see 5.4, endpoint declared per pool | `FAIL` on a non-equal or `None` output; `ERROR` only when evaluation raises |
| W6 | removing `e` destroys the gain | the ablation arm is COMPLETE and produced no correct held-out output | `FAIL`, `INCOMPLETE`, `ERROR`, `TIMEOUT` |

**Verdict.** `CAPABILITY-GROWTH-WITNESS` if and only if all six are `PASS`. `WITNESS-REFUTED` if no part is `ERROR`, `TIMEOUT` or `INCOMPLETE` and at least one is `FAIL`. `WITNESS-INCONCLUSIVE` in every other case, which is neither support nor refutation.

`ERROR`, `TIMEOUT` and `INCOMPLETE` are distinct from both `PASS` and `FAIL` everywhere and never substitute for either. An undefined output is a wrong answer and records `FAIL`; only a raised exception records `ERROR`. This direction matters: mapping `None` to `ERROR` would launder refutations into inconclusives and bias the record toward "we could not tell".

### 5.3 The completeness predicate

An arm is COMPLETE on a task only when all of:

| # | Condition | Source |
|---|---|---|
| 1 | the search returned without raising | try/except at the arm boundary |
| 2 | `stats.seconds < ARC_META_BUDGET_S - 0.01` | the runner's own `_deadline_hit` shape |
| 3 | no leave-one-out fold in that arm hit the deadline | per-fold `deadline_hit`, as `loo_with_stats` records it |
| 4 | zero `PER_TYPE_CAP` saturations in the arm's enumeration | new counter, mandatory |
| 5 | the arm reached `MAX_DEPTH`, or terminated earlier only by finding a fit | `stats.max_depth` |
| 6 | the arm's config digest and runtime-state digest equal the pinned values | header |

A comparison in which either arm is incomplete produces `INCOMPLETE` and therefore `WITNESS-INCONCLUSIVE`. Incompleteness never supports a positive.

Condition 4 is required because `search._asts_of_type` breaks out of both loops when the cap is reached, caches the truncated list, and reuses it, with no counter anywhere in `SearchStats`. Truncation is in alphabetical order of production name, so the very productions that would refute "K fails" can be silently dropped. The counter must be added to the gate's arm wrapper and reported per (type, depth) cell.

Conditions 2 and 3 are why `ARC_META_BUDGET_S` is raised to 64.0 for every arm. The treatment arm stops at the first fitting depth and is fast; the baseline arm runs all depths and is slow, so at 8 seconds the completeness predicate would systematically void exactly the failing baselines the gate needs. Raising the budget symmetrically makes "K fails" mean "K, given eight times the budget the treatment used, still fails", which is a tightening. The Step-B run itself used the default 8.0, so the gate's arm timings do not reproduce the run's; the reproduction control at G6 is therefore evaluated at the raised budget for both arms and disagreements in which either execution was incomplete are recorded as timing artifacts.

`GATE_REPEATS = 3` under a pinned single-process, single-thread configuration. A pair whose `found`, `uses` and per-fold verdicts are not identical across all three executions is `WITNESS-VOID-NONDETERMINISM`.

W1 and W6 are the same environment reached by two routes. Both are executed and both are recorded. Disagreement in which either run recorded a deadline hit is `WITNESS-ARM-DISAGREE-TIMING`, and the pre-declared response is one re-run of both arms at the same raised budget, ledgered. Disagreement with both runs complete is `WITNESS-ARM-DISAGREE-STRUCTURAL` and halts the gate, because it means the arms are not what this section says they are.

### 5.4 W5, declared per pool before the outcome

| Pool | W5 endpoint | Level tag | Data source |
|---|---|---|---|
| `INVENTION_PROVENANCE` | every leave-one-out fold prediction exact | `LOO_REDISCOVERY` | the blind demonstration corpus |
| `E_TRANSFER` | the rendered test prediction equals the ARC solution grid by exact array equality | `HELD_OUT_OUTPUT` | licensed at G8 only |

This split is required, not stylistic. `write_corpus` writes demonstrations only, with no task id, no test pair and no solution, so an ARC test output does not exist inside anything G6 may read, and importing one would break the firewall the manifest exists to maintain. On the provenance pool W5 is entailed by W4 and adds no independent information; the record states that and the object is described as having five independent parts.

### 5.5 What W4 means, decided before the outcome

`loo_by_rediscovery(pairs, env)` re-runs the whole discovery on N-1 pairs and predicts the held-out one, with `env` constructed once by the caller and held fixed across folds. What is re-induced per fold is the PROGRAM. What is fixed across folds is the LANGUAGE, including `e`.

In Step B the proposal is the first exact fit on ALL demonstrations, so on a provenance task every held-out demonstration participated in selecting which candidate `e` exists. The candidate's parameters are refit per fold, because a candidate is a slot-carrying macro; terminal-mode parameters are re-enumerated per fold from `TERMINAL_VALUES`. The dependence is therefore at the level of extension identity, not extension parameterisation.

W4 is satisfied by the existing frozen verifier, which is criterion 2 of the frozen manifest. This is declared now so that it cannot be chosen later. Any L4 claim carries this sentence verbatim:

> Leave-one-out re-induction was performed at the level of the program under a fixed extension. On invention-provenance tasks the extension's identity was selected using all demonstrations of those tasks. Re-invention of the extension inside folds was not tested.

Adaptive leave-one-out, re-proposing `e` inside each fold, is not implementable by configuring existing code and is not part of the witness definition. If it is ever built as a separately frozen script whose hash precedes its first sight of any candidate, its result is reported wherever L4 is claimed, whether it passes or fails, as a robustness annotation that changes no count in either direction. Fixing this in both directions now removes the option of running it only when the primary is unwelcome.

The fold's accepted program need not contain `e`. The gate records, per fold, whether the fold's accepted program uses `e`, and reports the count beside W4 without changing the pass rule, so the conjunction is not read as stronger than the evidence.

Because the gate cannot import `loo_with_stats` from MAIN's runner and must not modify it, the gate re-implements it and asserts per-task equality of its verdicts against `search.loo_by_rediscovery`. Agreements and disagreements are reported as counts.

On an E_transfer task the extension's identity is independent of that task by construction, since the task took no part in proposal generation. That is why only an `E_TRANSFER` witness supports L4.

---

## 6. The semantic-separation test

This implements the additive requirement of the frozen design. The requirement is declared there and has never been implemented: a grep for `semantic_separation`, `separation_certificate` and `EQUIVALENT_TO_BASELINE` across all Python in the tree returns zero hits.

### 6.1 What is being tested, and what would make it wrong

The design states the criterion as

```
exists x :  e(x)  not in  { p(x) : p in F(K_L4*) }
```

`p(x)`. Baseline programs are functions of the same `x`. The obvious implementation, `search._asts_of_type(B, ...)`, returns CLOSED terms of the result type: they take no argument and receive only the context grid. Comparing `e(a1..an ; g)` against `{ p(g) }` hands the candidate inputs the baseline is structurally incapable of receiving, and scores the difference as novelty. An exact re-spelling of a frozen production would separate on the first probe. That implementation is forbidden.

### 6.2 Baseline construction

For a candidate with declared interface `A -> B` and non-port parameter list `L` (the port slot is excluded from `L`; this is fixed here and not resolved later):

1. Capture `FROZEN_BASE`, the pre-Level-4 registry, BEFORE `install.installed()` runs. Primary baseline vocabulary is `K_L4*`, the eleven admitted grounded productions, read from `level4_baseline_admissibility_v2.json`. Secondary baseline vocabulary is `E_L4* = K_L4* + {concept_0001}`.
2. Enumerate open terms with `candidates.enumerate_terms(A, B, vocab, bounds)`, which enumerates port-bearing terms as functions `A -> B` over a given vocabulary and returns `(terms, dropped_by_cap)`. Its default `BOUNDS` are `max_depth 4, per_type_cap 4000`; the gate passes `bounds = {"max_depth": SEP_MAX_DEPTH = 5, "per_type_cap": SEP_PER_TYPE_CAP = 4000}` so that the baseline is at least as large as the design's declared bound.
3. No `MAX_CANDIDATES` truncation, no early stopping, no wall clock inside the enumeration. The only bound inside the enumeration is `per_type_cap`, plus the per-candidate ceiling `SEP_ENUM_CEILING_S = 3600` seconds measured outside the enumeration loop.
4. If `dropped_by_cap > 0`, record it per (type, depth) cell.
5. Both candidate and baseline terms are evaluated inside the same active `install.installed(...)` context, so the evaluator is identical for both, while the baseline vocabulary is restricted to the frozen names.

**Empty-baseline handling, split by cause.**

| Cause | Code | Reading |
|---|---|---|
| `K_L4*` has no term of result type `B` from a port of type `A` at any depth | `SEP-BASELINE-TYPE-UNREACHABLE` | a reachability fact, inconclusive, never separation |
| the enumeration is empty only because `L` contains parameter types absent from `K_L4*` (`SetOp`, `Extremum`, `Colour`, `IndexMap`, `Frame`) | `SEP-PARAM-TYPE-ABSENT`, then re-run per 6.2.6 | not a verdict on its own |

6. **Parameter-frozen re-run.** When `SEP-PARAM-TYPE-ABSENT` fires, freeze each of `e`'s non-port parameters at each witness value of its type in canonical order, producing a family of unary functions `A -> B`, and compare each against the same open-term enumeration of `K_L4*`. This is the well-posed question for a bridge operator. Without it the gate would automatically bar L3 for exactly the schemas it is looking for, including `embed.into_carrier`, the only schema producing a carrier from a non-carrier and the nearest thing in the inventory to the `Set[Region] -> Grid` bridge the failure branch nominates as the sole redesign target.

### 6.3 The constructor pre-pass, run once before any candidate

`candidates.vocabulary("K2", instances)` is the inventory instances plus registry productions whose result kind is `expr`, and `enumerate_terms` keeps only port-bearing terms of the goal type, so for most goal types the root of a K2 term must be an inventory instance. A structural test that asks only "does the elaboration contain an inventory constructor" is therefore satisfied by every K2 candidate by construction and is an inert guard.

The pre-pass fixes this. For every ground inventory instance used by any retained candidate, apply the section 6.4 comparison to that instance alone against the `K_L4*` open-term enumeration at its own interface. An instance whose result is `SEP-EQUIVALENT` or that has a term of `F(K_L4*)` agreeing with it on every jointly defined probe is stamped `CONSTRUCTOR-DEFINABLE-IN-K-L4STAR`. A candidate all of whose inventory instances carry that stamp is stamped `MACRO-OVER-K-L4STAR-STRUCTURAL`, is capped at L2 permanently, and cannot reach L3 whatever the behavioural test says.

This matters because the inventory and the frozen registry are not disjoint.

| K2 schema | Frozen twin |
|---|---|
| `select.by_predicate` | `Select` |
| `aggregate.unique` | `Unique@Entity` |
| `aggregate.extremum`, `select.extremal` | `ArgMax@Entity`, `ArgMin@Entity` |
| `project.feature` | `Key` composed under `Map_V1` |

The firing count of `MACRO-OVER-K-L4STAR-STRUCTURAL` is reported. If it is zero across the whole gate, it is listed by name under `INERT-GUARD` and the report says so in the same sentence as any claim resting on it.

### 6.4 Probes and behaviour

1. **Probe set.** The frozen generator `level4_stepB/witnesses.py`, `SEED = 424242`, `BOUNDS` as pinned, module hash as pinned at G2, `SEP_CONTEXTS = 6`, `SEP_ARG_COMBOS = 24`, giving at most 144 probes per candidate. The generator reads no cluster content and existed before any candidate. It is regenerated at gate time and must reproduce the fingerprint recorded in the Step-B run manifest; a mismatch is `SEP-WITNESS-GENERATION-ERROR` and halts. No candidate may influence probe selection, and no probe budget is adjusted after any candidate is seen.
2. **Identical inputs.** The candidate and every baseline term are applied to the SAME argument tuple in the same canonical order. Slot fitting is used on neither side. A separation obtained because the candidate's slots were fitted and the baseline's were not is void.
3. **Baseline-constructible arguments.** A probe is admissible only if every component of its argument tuple is in the image, on that context, of some `F(K_L4*)` term of that argument type, or is a frozen terminal value. Probes failing this are counted and reported under `SEP-ARG-NOT-CONSTRUCTIBLE`; that count is the honest measure of how much of the probe space is fiction. If no admissible probe remains, the outcome is `SEP-NO-CONSTRUCTIBLE-PROBE`, which is inconclusive.
4. **Three-valued behaviour.** The gate does not call `witnesses.behaviour` directly. It uses `behaviour_typed`, which records for every (context, argument tuple) exactly one of

```
DEFINED(canonical value)
UNDEFINED        returned None with no exception raised
ERROR(class)     raised, with the exception class recorded
```

Three separate layers currently swallow exceptions: `k2_inventory.build()` wraps every instance's semantics, `install._eval_extended` wraps the outer call, and `witnesses.behaviour` wraps evaluation. `behaviour_typed` installs a single instrumentation hook at the outermost call that records the exception class before returning `None`. That hook is a declared deviation from the Step-B evaluation path, its hash is part of the config digest, and it is a tightening because it can only remove cells from the set that would otherwise look like agreement or like undefinedness.

`ERROR` is never evidence of anything. It never contributes to separation, necessity, or equivalence.

5. **Non-vacuity floor.** The candidate must be `DEFINED` on at least `SEP_DEF_MIN = 8` admissible probes spanning at least `SEP_CTX_MIN = 2` contexts. Below the floor the outcome is `SEP-VACUOUS` and the class is additionally flagged as a possible vacuity collision in its Step-B dedup class.
6. **Equality.** Values are compared as `kinds.as_canonical` images serialized with `json.dumps(..., sort_keys=True)` and compared as strings. Any exception in canonicalization or comparison is `SEP-ERROR`, never a non-match. This is required because outputs include numpy grids, for which `==` returns an array and `bool()` raises, and an exception in the comparison would otherwise land in the "no term matches" branch, which is the positive branch.

### 6.5 The separation predicate

Comparison is per baseline PROGRAM over the whole admissible probe set, not per probe in isolation.

For each baseline term `p`, compute its behaviour vector over the admissible probes. Then:

```
SEP-SEPARATED  iff
  (a) there exist at least SEP_MIN_SEPARATING_PROBES = 3 admissible probes,
      spanning at least SEP_MIN_SEPARATING_CONTEXTS = 2 contexts, such that at
      each such probe x:
        e(x) is DEFINED, and
        at least one baseline term is DEFINED at x, and
        no baseline term DEFINED at x has value equal to e(x), and
        the count of baseline terms with ERROR at x is zero;
  and
  (b) no baseline term agrees with e at every probe where both are DEFINED;
  and
  (c) it is not the case that the only difference from some baseline term p is
      that e is DEFINED where p is UNDEFINED while agreeing wherever both are
      DEFINED;
  and
  (d) dropped_by_cap == 0 for every (type, depth) cell reachable in the
      candidate's interface, and the enumeration did not exceed
      SEP_ENUM_CEILING_S.
```

Clause (b) exists because a per-probe existential lets a boundary convention separate a clone: `sem_select_by_predicate` returns a collection on an empty selection where the frozen `_select` returns `None`, and the six random contexts will produce an empty selection.

Clause (c) exists because a per-probe rule silently drops baseline terms that are undefined at the separating probe, so a totalization of an existing operator separates. `runtime._extremum` returns `None` on ties while `sem_select_extremal` returns the whole winner set; that is a domain extension, not new denotable behaviour. Its code is `SEP-TOTALIZATION-ONLY`, recorded, not a pass at L3.

Clause (d) is asymmetric on purpose. Truncation can only remove terms that would refute separation; it can never create a match. So a match found under truncation is a valid `SEP-EQUIVALENT`, while an absence of match under truncation is `SEP-INCONCLUSIVE-ENUM-TRUNCATED` and never separation.

The zero-error condition in (a) is scoped per probe, not globally across the whole probe set. A global zero-error requirement over hundreds of thousands of executions would veto every probe; a per-probe requirement keeps the refuting set honest at the one point where the verdict is read.

### 6.6 Distinguishing bounded-search novelty from genuine separation

Three separate mechanisms are required, and each answers a different route by which a non-discovery can look like one.

| Route | Mechanism |
|---|---|
| the candidate is a composition of frozen pieces that the depth budget cannot reach | the constructor pre-pass of 6.3 and the structural cap: composition is a language fact, depth is a budget fact |
| the candidate is compared against programs that never received its inputs | open-term enumeration at the candidate's own interface, identical argument tuples, baseline-constructible arguments |
| the candidate differs only where the baseline is undefined, or only at one boundary | clauses (b), (c) and the robustness floor |

A macro reaching a goal that `MAX_DEPTH = 5` cannot reach is an L2 result and is reported as reachability under the fixed budget. It is never an L3 result.

### 6.7 The two baselines and the sentences they license

| Baseline | Code field | The one thing it decides |
|---|---|---|
| `F(K_L4*)` | `separation_primary` | the L3 rung |
| `F(E_L4*)` | `separation_secondary` | one permitted sentence, below |

`concept_0001` is a macro that expands into the kernel, so `F(E_L4*)` and `F(K_L4*)` denote the same functions and differ only in what is reachable at the declared depth under surface accounting. The secondary baseline therefore licenses exactly one sentence and it is a reachability sentence, not a denotational one:

> not reachable within the declared enumeration bounds from the frozen productions alone, but reachable once `concept_0001` is available as a one-node macro.

The sentence "unavailable in the system's operative language" is forbidden. A class separating from `F(K_L4*)` but not from `F(E_L4*)` is coded `SEP-MACRO-OVER-CONCEPT`, is capped at L2, and is reported as a macro over the previously learned abstraction.

### 6.8 Guard accounting

Every certificate records: admissible probes, probes discarded as non-constructible, baseline terms enumerated, `dropped_by_cap` per cell, comparisons performed, `DEFINED`, `UNDEFINED` and `ERROR` counts for candidate and baseline separately, duplicate-fingerprint collisions, per-member heterogeneity, and the fire count of every rejection code. Any guard whose fire count is zero across the entire gate is listed by name under `INERT-GUARD`, and any claim resting on a stage where a load-bearing guard never fired is reported with that code in the same sentence. An inert guard is not a pass.

### 6.9 Separation outcome vocabulary

`SEP-SEPARATED`, `SEP-EQUIVALENT` (reported with the frozen string `EQUIVALENT_TO_BASELINE_COMPOSITION`), `SEP-MACRO-OVER-CONCEPT`, `SEP-TOTALIZATION-ONLY`, `SEP-DEFINEDNESS-ONLY`, `SEP-VACUOUS`, `SEP-NO-CONSTRUCTIBLE-PROBE`, `SEP-ARG-NOT-CONSTRUCTIBLE`, `SEP-BASELINE-TYPE-UNREACHABLE`, `SEP-PARAM-TYPE-ABSENT`, `SEP-INCONCLUSIVE-ENUM-TRUNCATED`, `SEP-INCONCLUSIVE-BASELINE-ERRORS`, `SEP-INCONCLUSIVE-TIMEOUT`, `SEP-ERROR`, `SEP-WITNESS-GENERATION-ERROR`, `SEP-NOT-APPLICABLE-K1-LANE`, `MACRO-OVER-K-L4STAR-STRUCTURAL`, `CONSTRUCTOR-DEFINABLE-IN-K-L4STAR`.

---

## 7. Decision rules

Each rule below is final and non-restatable. Each was declared before the outcome existed. Each is embedded verbatim in `gate_tool_manifest.json`, and any stage finding the embedded text different from this document refuses with `REFUSE-PREREG-MISMATCH`.

**DR-01 Frozen tooling.** A stage may execute only a script hashed in the tool manifest as committed before the G3 access-ledger opening. A later script may be used, but its artifacts carry `POST-INSPECTION-TOOLING` permanently and every claim consuming them is exploratory, never confirmatory.

**DR-02 Launch-time provenance.** Every gate script records git HEAD, porcelain dirty counts, `PYTHONHASHSEED`, Python version, platform and UTC time at process start, before computing any result. A git hash read at report time is a protocol breach.

**DR-03 Hash seed.** Every gate process runs with `PYTHONHASHSEED=0`, enforced by `gate_preflight.py` before the immutable pin is created. A stage that finds it unset writes `ENV-UNVERIFIABLE` and its results support no claim.

**DR-04 One config digest.** `config_digest` is the sha256 over the ordered tuple: runtime module hashes, search module hash, `meta_v21*` module hashes, the admissibility artifact hash, `SEP_MAX_DEPTH`, `SEP_PER_TYPE_CAP`, budget, cost table, ranking rule, `K` identity hash, extension identity hash, and the instrumentation hook hash. Two records may be compared only if their digests differ in exactly the declared single field.

**DR-05 Runtime state digest.** Every arm and every evaluation records `runtime_state_digest`, the sha256 over `sorted(V.REGISTRY)`, `sorted(V.TERMINAL_VALUES)` with canonical value tuples, `list(V.INDUCED_TYPES)`, `sorted(SEARCH.SLOT_LEARNERS)`, `sorted(ARG_MODES)`, and `V._eval.__qualname__`. `install.installed()` mutates all of these process globals and the Step-B workers never exit the context, so identical files can produce different behaviour. Each stage declares its expected digest at P0 and asserts it at start. A mismatch is `RUNTIME-STATE-MISMATCH` and halts.

**DR-06 No wall clock primary.** Wall seconds are never a primary endpoint. The primary resource everywhere is typed candidates enumerated.

**DR-07 Retention fixed by the run.** The retained set is exactly the classes with non-empty `kept_for`. `N_retained` is recorded before any per-class field is read, and every later table has that many rows.

**DR-08 Label is not a certificate.** `gate_rung.py` takes no label argument. Novelty comes from the structural test and the separation certificate, never from `lane` and never from `generation_lane_label`.

**DR-09 One object per class.** `e` is the class representative with no substitution. Semantics are recorded as a list over every inventory instance in the representative's schema.

**DR-10 Pin before eyes.** No pinned file is opened for content before `gate_pin_verify.py` is clean and the pin commit exists and is verified present in the index.

**DR-11 Access ledger.** Every content-bearing read is appended to the ledger by an `open()` audit hook. A claim depending on a file absent from the ledger is void.

**DR-12 Errors have their own codes everywhere.** `ERROR`, `TIMEOUT` and `INCOMPLETE` are never merged into `PASS` or into `FAIL`, at any stage, in any artifact.

**DR-13 Completeness before comparison.** Section 5.3 in full. Incompleteness never supports a positive.

**DR-14 Arm symmetry.** Section 5.1 in full, with the explicit ablation construction and the assertions.

**DR-15 W4 primary is the frozen verifier.** Section 5.5, with the mandatory caveat sentence and the two-directional pre-commitment on adaptive leave-one-out.

**DR-16 Invention provenance is the union of `proposed_from`.** Resolved to task ids at G7, conservative by construction, and never redefined.

**DR-17 Identity-only de-collision.** Exclusion is by task identity alone. Every skip is recorded with its identity and its reason. Errors and timeouts are not excluded and stay in the denominator.

**DR-18 Eligible set frozen before the split opens.** Hash committed and verified present in the index before any E_transfer path is opened; the runner refuses on mismatch; the set is never extended or reduced afterwards.

**DR-19 Empty set closes the split.** No exploratory peek, no sanity check, no single-candidate exception.

**DR-20 One access, adjudicated by artifacts.** Section G8 in full, including the tee-to-file requirement so that "displayed" is decided by a hash and not by recollection.

**DR-21 Named primary, no substitution.** The primary for capability growth is the six-part conjunction. The primary for transfer is `N_w`. M1 to M5 are secondary, are reported, and can never be promoted.

**DR-22 No tuning surface.** Nothing changes after E_transfer opens. A defect voids the whole pass and the pass restarts; the void is recorded.

**DR-23 Retrospective costs are not forecasts.** Every M4 number is labelled `MEASURED-RETROSPECTIVE`.

**DR-24 Level of analysis on every claim.** Every claim sentence carries exactly one of `DEMONSTRATION_FIT`, `LOO_REDISCOVERY`, `HELD_OUT_OUTPUT`, `BOUNDED_ENUMERATION`, plus the rung code, the split, the denominator and the outcome code. A sentence missing any of these is void and does not ship.

**DR-25 Guards are counted.** Every guard reports `evaluated` and `fired`. Each has a synthetic positive-control fixture run at gate start; a control that does not fire its guard halts the gate. Zero-firing guards on real data are listed as `INERT-GUARD`.

**DR-26 Append-only knowledge state.** `K_t` retained verbatim; promotion never edits an existing production.

**DR-27 No hand-authored concepts.** Post-promotion abstraction is machine provenance only, with proposed and rejected counts reported.

**DR-28 3A and 3B never summed.** Every sentence naming a count names the letter.

**DR-29 Exactly one terminal code.** If several triggers fire, the earliest in gate order wins. A negative terminal code requires that every relevant record be decided; if any is inconclusive and none is positive, the terminal code is `TERM-INCONCLUSIVE-<stage>`, which licenses no claim in either direction. Refutation conditions key on `FAIL`, never on the mere absence of `PASS`.

**DR-30 Forbidden phrasings.** These may not appear in any gate artifact, README, manuscript, abstract or slide derived from this gate: "partial witness"; "near witness"; "would have passed"; "essentially", "effectively" or "nearly" applied to a rung; "vanish under ablation" unless the recorded code says the gain vanished; "solved nothing extra" without the level of analysis; "untouched", "pristine", "fully prospective", "lockbox validation"; "no previous system invents concepts or predicates from failure"; forecast, projected, deployment estimate or expected cost applied to a measured search cost; any claim of invention without `RUNG-L4`; "e is not expressible in K_L4*"; "exhaustive" applied to any enumeration bounded by `per_type_cap`.

**DR-31 Numeric regeneration.** `gate_report_check.py` regenerates every number in any summary directly from the hashed artifacts and blocks the report on mismatch.

**DR-32 One sealed number.** The sealed ARC number is 185/1000 (v23, artifact-backed) in every document until a new sealed measurement exists. Verification is against results artifacts, never transcript numbers. Historical manifest facts are exempt with their version attached: `LOCKBOX_PROTOCOL.md` correctly reports 181 as the certified composition of manifest v1.0.0, and that statement stands.

**DR-33 No attribution.** No gate artifact, commit message, manuscript or document produced under this protocol carries any model or tool attribution.

**DR-34 Implementation fixes yes, protocol changes no.** A gate failure justifies correcting an implementation so that it performs what this document declares. It never justifies changing what this document declares.

---

## 8. The failure branch

### 8.1 Triggers, each with its frozen interpretation

| Terminal code | Trigger | Interpretation, frozen now |
|---|---|---|
| `TERM-NO-CANDIDATE` | `N_retained == 0` | The K2 schema could not express what the failure clusters needed. A real negative about THIS schema. K2 is not widened after the fact. |
| `TERM-ONLY-K1-REPAIRS` | retained classes are all lane K1 | The located gap was an estimator gap. A real negative for Level 4. A relaxed slot learner is not an invention. |
| `TERM-ALL-EQUIVALENT` | every retained class fails separation or is structurally a macro | The mechanism produced re-expressions of the existing language. A macro result at Level 3, recorded, not a Level-4 result. |
| `TERM-NO-WITNESS` | at least one class at L3 but no provenance certification, or the admitted set is empty | The extension denotes something new on the bounded domain and does nothing. Denotational novelty without causal utility. E_transfer was not opened. |
| `TERM-NO-TRANSFER` | `C6-FAIL` on E_transfer with every pair decided | The extension is causally useful only where it was invented. A retrofit, not an invention, by the frozen definition of criterion 6. |
| `TERM-INCONCLUSIVE-<stage>` | the stage could not decide because of errors, timeouts, truncation or incompleteness | The gate did not run to a verdict. No claim in either direction is licensed. Not a negative result. |
| `TERM-VOID-PROTOCOL-BREACH` | any breach of DR-10, DR-11, DR-20 or section 9 | The gate produced no confirmatory evidence. The result is void and the breach is described. |

### 8.2 What is recorded, in full

1. The G1 pin, the G2 module pin, `gate_pin_verify` results, and the complete access ledger.
2. The complete per-class table with all `N_retained` rows, every G4 field, every separation code, every structural code, and the rung from G5, with the first failing predicate named per row.
3. Every witness attempt with its six per-part codes, including the parts that passed, the arm completeness flags, and the pool field.
4. The reproduction disagreement counts from G6 and the degeneracy check result whether or not it fired.
5. Guard fire counts, positive-control results, and the explicit list of `INERT-GUARD` names.
6. Counts of `ERROR`, `TIMEOUT` and `INCOMPLETE` at every stage, kept separate from `FAIL`.
7. Enumeration sizes per candidate, `dropped_by_cap` per cell, non-constructible probe counts, and whether any candidate hit `SEP_ENUM_CEILING_S`.
8. Every skip with its identity and its reason, including zero counts.
9. The five descriptive measurements if E_transfer was opened, with denominators.
10. Standing environment caveats, including `ENV-HASHSEED-UNSET-AT-RUN` and `ENV-RUN-UNKNOWN` if applicable.
11. The tool manifest, including any `POST-INSPECTION-TOOLING` stamps.
12. The terminal code and its frozen interpretation quoted verbatim.
13. The Level-4 row of `docs/CORA_EVIDENCE_LADDER.md` updated from PENDING to the measured negative, with its bound: a negative about THIS schema under THESE bounds, not about semantic self-extension in general.

The negative is published as a negative. It is not patched, not re-run with an adjusted inventory, and not retold as a positive about a secondary measurement.

### 8.3 What the failure branch does not license

A null result here is not a reason to return to abstraction selection, memory, retrieval, ranking, priors, or selector work. The following responses are forbidden, and naming them here is the point:

- no new ranking rule, scoring function, or search prior;
- no library retrieval or concept routing mechanism;
- no re-run or extension of the LAS or abstraction-selection line;
- no widening of the K2 constructor inventory to cover what the clusters needed;
- no repair of a specific failing candidate;
- no second Step-B run with an adjusted inventory, cluster threshold, or eligibility rule;
- no substitution of a secondary measurement for the failed primary;
- no relaxation of the verifier, the bounds, or the completeness predicate.

The reason is established evidence, not preference. Search and prior transfer are demonstrated. Predictive-selection transfer is demonstrated narrowly. Learned abstraction beating concrete memory failed its preregistered replication at +3 with a 95 percent paired bootstrap interval of [-1, 8]. Bounded search-reach gain produced zero witnesses, with every policy fitting the identical 188 of 256 targets. More work in that direction has a documented ceiling.

### 8.4 The single permitted redesign target

The semantic-construction mechanism itself: a typed meta-constructor that proposes new BRIDGES between existing reasoning types, rather than selecting among already-enumerated whole programs. Declared bridge shapes, named now so the redesign cannot be steered by what failed:

```
Set[Region]      -> Grid
Set[Entity]      -> Set[Placement]
Relation[A, B]   -> Mapping[A, B]
Collection[A]    -> Aggregate[B]
ObjectPair       -> Transform
```

No code for the bridge meta-constructor is written until a new pre-registered protocol document exists, is committed, and is hashed, in the same style as this one, with its own primary endpoint declared before any run and its own separation test written before its mechanism exists. The failure record of this gate is an input to that document. It may not reuse this gate's terminal code as evidence for anything except that the previous mechanism failed. It uses a fresh, separately drawn holdout: E_transfer has been spent by one pass and is not reused as a transfer set. It inherits sections 3, 5, 6, 7 and 9 of this document unchanged, and it inherits 8.3.

---

## 9. Sealed-data discipline

### 9.1 What may be touched at which stage

| Data class | Object | First licensed stage | Access permitted |
|---|---|---|---|
| pinned bytes | every path in `PINNED_PATHS`, `PINNED_GLOBS`, `PINNED_TREES` | G1 | stat and hash only, no content |
| Step-B outputs | merged classes, inventory, run manifest, gate outputs | G3 | full content, ledgered |
| checkpoint journal | `level4_stepB_journal.jsonl` | never | line counts from the pin only |
| withheld expectation | `level4_withheld_expectation_seal.json` | never in this gate | hash only |
| admissibility | `level4_baseline_admissibility_v2.json` | G2 hash, G4 content | full content, ledgered |
| provenance firewall | `level4_provenance_firewall.json` | G7 | `source_token_to_task` and `within_stage_holdout.E_transfer` only |
| E_transfer | the resolved task list and its ARC pairs | G8 | one pass, one execution, ledgered |
| Promotion split | Promotion tasks | G7 criterion 3, G10 | evaluated, never mined |
| Lockbox200 | `outputs/lockbox/*` | never in this gate | manifest hash only at G2 and G11 |
| public eval 120 | `data/arc-agi_evaluation_*` | never in this gate | none |
| D3 and D4 TTI holdouts | `eval_split_v1`, holdout half | never in this gate | none, and never confused with Lockbox200 |

### 9.2 Rules

1. `E_transfer` opens exactly once, at G8, for the frozen admitted set, in one scripted run, ledgered with timestamp, operator, script hash, admitted-set hash, config digest, runtime-state digest and task count.
2. Promotion tasks may be evaluated repeatedly but never mined. A failure on a Promotion task must not become a repair hypothesis, a primitive, or a parameter change. Anything learned by looking at a Promotion task disqualifies that task as transfer evidence.
3. Lockbox200 is not run, inspected, traced or analysed at any point in this gate. G11 asserts closure and opens nothing. A negative gate verdict does not open the Lockbox. Nothing opens the Lockbox except completion of this gate followed by a declared system freeze under a separate frozen document.
4. The 120 public evaluation tasks are not run until after the single Lockbox evaluation.
5. Any read, glob, import or listing of a sealed path outside its licensed stage sets `TERM-VOID-PROTOCOL-BREACH`, which voids the gate's confirmatory status permanently.

### 9.3 Detection, not exhortation

`tests/test_cora_parent_isolation.py` guards only `cora_parent` and `cora_tti` by case-insensitive substring blacklist. Every gate script lives in `scripts/`, which that test never reads, so for the code that could actually commit the breach it detects nothing. Its marker list also omits `withheld_expectation`, which is the sealed expectation's real filename.

`tests/test_gate_isolation.py` therefore does three things instead. It keeps the existing substring blacklist for `cora_parent` and `cora_tti` unchanged. It adds `withheld_expectation` to the forbidden markers. And it guards the gate scripts by resolved-path allowlist plus AST check rather than by filename substring, because `gate_etransfer_runner.py` and `gate_lockbox_closure.py` would fail a substring rule by their own names and would then have to be exempted, which is exactly the wrong scripts to exempt. Each gate script declares the resolved paths it may open; the test asserts the declaration; and the runtime `open()` audit hook makes the ledger, not a self-report, the detector. The isolation test runs at every stage boundary, and its test count is recorded.

---

## 10. Defect-to-control map

Every defect this program has actually suffered, and the control that makes it mechanically impossible or mechanically visible.

| Defect | Control |
|---|---|
| 1. Non-reproducibility from an unset hash seed | DR-03 with enforcement in `gate_preflight.py` before the immutable pin; C5.2; `stepB_run_env.json` capture from the live process rather than from the pin process |
| 2. Inert guards giving false assurance | DR-25 counters plus positive-control fixtures; the constructor pre-pass, which replaces a structural test that was inert by construction; the criterion-1 evidence field corrected from `independent_source_tokens` to `certified_sources` |
| 3. Wrong-reasoner provenance | DR-04 config digest; DR-05 runtime state digest; the G10 differential run on the substrate that produced the frozen 3A result; the explicit assertion that baseline and ablation arms enumerate no name outside `FROZEN_BASE union {concept_0001}` |
| 4. Error and necessity conflated | DR-12; three-valued `behaviour_typed` with an instrumentation hook that makes `ERROR` observable through three swallow layers; W5 records `FAIL` on `None` and `ERROR` only on a raise; W6 has an explicit `ERROR` code |
| 5. Incomplete baseline admitting a positive | Section 5.3, six conditions, including the new `PER_TYPE_CAP` saturation counter and the raised symmetric budget |
| 6. Vacuous probes colliding into one fingerprint | 6.4.5 non-vacuity floor; joint definedness in 6.5(a); per-member heterogeneity recomputation at G4.6 |
| 7. Provenance drift | DR-02 launch-time reads; `gate_preflight.py` clean-tree enforcement; P0.4, which makes the commits actually happen |
| 8. Post-hoc reinterpretation pressure | DR-21 named primary declared before the split opens; DR-22; the frozen interpretation table of 8.1; `REFUSE-PREREG-MISMATCH` |
| 9. Inverted or under-reported summaries | DR-24 mandatory sentence shape; DR-30 forbidden phrasings; DR-31 numeric regeneration; G10 reporting lost solves as prominently as gains |
| 10. Retrospective costs presented as predictions | DR-23 |
| 11. Degenerate rule caught late | G6 degeneracy pre-check run and recorded whether or not it fires; C5.3 slot degeneracy with its pre-declared consequence |
| 12. Identity collision between pools | DR-16 single definition of provenance; DR-17 identity-only de-collision with recorded reasons and zero counts reported |
| 13. Label mistaken for certificate | L1 rung definition; DR-08 function signature; LR5 label never printed without its separation code; the constructor pre-pass, which closes the vocabulary route that remained open once the label route was closed |

---

## 11. Execution order

```
P0  tool manifest, run-env capture, regression set, gitignore negation,
    isolation test, all gate scripts written and committed
    -- STEP B FROZEN appears --
G1  preflight, pin once, commit and verify present in index, verify strictly
G2  module pin, cross-tree identity, meta_v21 and admissibility and lockbox hashes
G3  first content read, access ledger opened, N_retained recorded
G4  dossiers, induction surface, lane audit, heterogeneity,
    constructor pre-pass, separation certificates
G5  rungs assigned mechanically
G6  six-part conjunction on the invention-provenance pool,
    reproduction control, degeneracy pre-check
G7  criteria 3, 4, 5; admitted set frozen and committed BEFORE the firewall opens
G8  E_transfer opened once, primary N_w decided, five secondaries recorded
G9  promotion manifest frozen, then promotion, K_{t+1} = K_t + {e}
G10 harness differential, rediscovery, automatic abstraction, three arms,
    3A and 3B separate
G11 completion record, Lockbox asserted closed, report generated and checked
```

Any stage may end the sequence. Ending early with a recorded negative is a result. Ending early with a recorded inconclusive is not a result, and is repaired by fixing the implementation to do what this document already says, never by changing what it says.

---

## 12. Sign-off checklist

```
[ ] P0 tool manifest committed and verified present in the index
[ ] P0 Step-B process environment captured while pid 106593 was alive, or ENV-RUN-UNKNOWN recorded
[ ] P0 regression set frozen, hashed, size >= 20
[ ] P0 gitignore negation in place; every artifact commit verified with git ls-files
[ ] P0 gate isolation test written and passing
[ ] G1 preflight enforced; pin created once; verify strict, appeared-since-pin 0
[ ] G2 cross-tree identity verified; meta_v21, admissibility v2, lockbox manifest all hashed
[ ] G3 access ledger opened; N_retained recorded before any per-class field
[ ] G4 every class has all five determinations and a separation code
[ ] G4 constructor pre-pass run; MACRO-OVER-K-L4STAR-STRUCTURAL fire count reported
[ ] G5 rungs assigned mechanically, label never read by a predicate
[ ] G6 reproduction disagreements reported; degeneracy check recorded; arms symmetric
[ ] G7 admitted set frozen and committed before the firewall opened
[ ] G8 E_transfer opened once, ledgered, stdout teed and hashed
[ ] G8 primary N_w reported before any secondary number
[ ] G9 promotion runner hashed inside its own manifest before any decision
[ ] G10 harness differential passed on meta_v21 before any extension was run
[ ] G10 3A and 3B reported separately with their frozen claim limits
[ ] every guard counter reported, zeros included, positive controls passed
[ ] every claim sentence carries rung, split, level, denominator and outcome code
[ ] no sentence claims non-definability in K_L4*
[ ] Lockbox200, the withheld expectation and the public eval untouched
[ ] exactly one terminal code recorded
[ ] gate_report_check.py regenerated every number and blocked nothing
```

---

## 13. Limitations recorded before the outcome

Written now so they cannot be presented later as newly discovered nuance, and so a reader of any positive result sees them in the document that declared the test.

1. Separation is relative to a bounded enumeration at depth at most 5 under a per-type cap of 4000, a frozen probe set of at most 144 probes per candidate, one seed, and one canonical equality relation. It refutes macro-hood on that domain. It never proves non-definability.
2. The leave-one-out verifier fixes the extension outside the folds. On provenance tasks the extension's identity was selected using every demonstration. Program re-induction is certified; extension re-invention is not.
3. A macro has cost 1 and surface depth 1, so any reach result is partly a statement about the depth and time budget. Only the constructor pre-pass and the separation certificate distinguish reach from expressivity.
4. An extension carrying an induced slot fitted by a learner absent from `K_L4*` extends the language and its induction machinery, and this gate does not separate the two contributions.
5. Lane K1 classes cannot supply W3, because the runner's `uses` field short-circuits to true for that lane. K1 outcomes are repairs and never extensions.
6. Step-B certification is at demonstration-fit plus leave-one-out level. Step B never saw a test output. Held-out correctness enters the record for the first time at G8.
7. E_transfer is spent by one pass. A future experiment needs a new holdout.
8. The gate runs its arms at a budget eight times the one Step B used. Arm timings are therefore not identical to the run's, and reproduction disagreements attributable to incompleteness are recorded as timing artifacts rather than as certification failures.
9. Evidence from G6 onward attaches to the class representative only. Class equivalence in Step B was computed with error and undefinedness conflated, and is coarser than the gate's own semantics.
10. The gate measures one system on one corpus. Nothing here supports a claim about ARC performance, which remains 185/1000 (v23, artifact-backed) until a sealed evaluation says otherwise.

---

## 14. Rejected defects

Every BLOCKING and SERIOUS finding raised in adversarial review is fixed above, with these five exceptions. Each is a specific proposed remedy that is rejected; in each case the defect it addressed is fixed by a different mechanism, named here.

**R1. Rejected: "the appearance of `STEP B FROZEN` starts no clock, and pinning may wait until the tooling is written."**
Rejected because the interval between the marker and the pin is the one window in which someone can look at the output while nothing is recorded, and the pin is cheap, reads no content, and requires no gate tooling beyond the preflight. The pin is created immediately at the marker. The genuine defect the proposal addressed, that binding the confirmatory stamp to the marker makes the whole gate exploratory when the tooling is unfinished, is fixed instead by binding `POST-INSPECTION-TOOLING` to the first content-bearing read at G3 (section 2.5). Tooling may therefore be finished between G1 and G3 without cost, and the pin still happens at once.

**R2. Rejected: "scope the hash-seed requirement to the stages whose outputs depend on set or dict iteration order."**
Rejected because deciding which stages are order-dependent is a judgement call made by the person under outcome pressure, and that is the class of decision this document exists to remove. The seed is required in every gate process without exception. The real problem the proposal addressed, that one careless invocation of the immutable pin script in a shell without the seed would produce an unrecoverable void, is fixed instead by `gate_preflight.py`, which enforces the seed and the clean tree BEFORE the pin script is invoked and is itself recoverable because it writes nothing.

**R3. Rejected: "drop the secondary separation baseline `F(E_L4*)`."**
Rejected because the secondary baseline carries real information that nothing else in the gate produces: whether a candidate is a macro over the previously learned abstraction rather than over the frozen productions, which is the difference between `SEP-SEPARATED` and `SEP-MACRO-OVER-CONCEPT`. The defect the proposal addressed was the sentence it licensed, not the measurement. That is fixed in 6.7: the secondary licenses exactly one sentence and that sentence is a reachability statement under the declared bounds, with "unavailable in the system's operative language" added to the forbidden phrasings in DR-30.

**R4. Rejected: "drop the provenance-pool conjunction at G6, since a kept class already satisfies W2, W3 and W4 by the Step-B selection rule and the stage carries no independent information."**
Rejected because the stage carries three things the selection rule does not: the reproduction disagreement count against Step B's stored verdicts, the W1 and W6 completeness results under the raised symmetric budget with the new cap-saturation counter, and the degeneracy pre-check. It also implements the user's step 6 in the user's order. The valid half of the objection, that the stage must not be presented as an independent finding, is honoured explicitly in G6 under "Honest statement of what this stage adds", and in 5.4, which records that W5 is entailed by W4 on that pool so the object has five independent parts, not six.

**R5. Rejected: "make the separating-probe zero-error condition global across the whole probe set."**
Rejected because with thousands of enumerated baseline terms across up to 144 probes, a global zero-error requirement is a veto that would plausibly void every certificate, which is an over-strict rule capable of destroying a real discovery. The defect it addressed, that a baseline term which raises is silently removed from the set that could refute separation and every such error therefore pushes toward a positive, is fixed instead by scoping the condition per probe in 6.5(a): a probe is admissible as a separating witness only if the count of baseline terms with `ERROR` at that probe is zero, with the per-probe error census reported and `SEP-INCONCLUSIVE-BASELINE-ERRORS` available when no probe satisfies it.

---

## 15. Implementation status, appendix

Recorded when this document was frozen, so that nobody reading it at the freeze
marker assumes the gate is executable end to end. This appendix states what
exists. It changes no rule above and is updated only by appending.

### 15.1 Built, tested and pushed

| artifact | state |
| --- | --- |
| `scripts/pin_stepB_freeze.py` | complete, never run against a frozen run, 13 tests |
| `cora_tti/gate_guard.py` | complete, 19 tests |

`pin_stepB_freeze.py` covers G1 and G2 for the artifact set it discovers: 53
files on the dry run, including the three determinism lanes `ckpt`, `deta` and
`detb` and the mechanism-input tree. No dry-run aggregate digest is quoted here.
The run is live, so its log and journal grow between invocations and the
aggregate is not stable until the run stops. The stable pre-freeze facts are the
artifact count and the run manifest digest `8476b211400f1c3f`, which matches the
manifest recorded at launch. The real aggregate is whatever the single permitted
post-marker invocation records, and that value is the pin. It
refuses before the marker, refuses to overwrite, and its test suite asserts that
no artifact content can reach the pin.

Two limitations are recorded above and are real. Section G1 step 5 is correct
that `--verify` prints `PIN VERIFIED` when a new file has appeared under a
pinned glob, so `gate_pin_verify.py` must make that blocking. Section G1 step 1
is correct that the script records `PYTHONHASHSEED` without enforcing it, so
`gate_preflight.py` must enforce it first.

`cora_tti/gate_guard.py` implements the access order of section 9 in code.
Step-B semantics unlock at stage 3, E_transfer at stage 7, and Lockbox only at
stage 11. It classifies paths relative to the project root so an ancestor
directory name cannot decide a file's class, fails closed on an unrecognized
artifact under a watched root, refuses every write mode against the experiment
tree, and appends every decision including refusals to a ledger. Checked against
the real tree it refuses 582 of 589 artifacts at stage 1.

It does not yet satisfy DR-11 on its own. DR-11 requires an `open()` audit hook
so that every content-bearing read is ledgered whether or not the reader
remembered to use the guard. The guard ledgers only reads that pass through it.
Closing that gap is part of building `gate_inspect.py`.

### 15.2 Declared above and NOT built

`gate_admit.py`, `gate_capture_run_env.py`, `gate_constructor_prepass.py`,
`gate_dossier.py`, `gate_etransfer_runner.py`, `gate_inspect.py`,
`gate_isolation.py`, `gate_lockbox_closure.py`, `gate_module_pin.py`,
`gate_pin_verify.py`, `gate_post_promotion.py`, `gate_preflight.py`,
`gate_promote.py`, `gate_promotion_freeze.py`, `gate_regression_set_freeze.py`,
`gate_report.py`, `gate_report_check.py`, `gate_rung.py`,
`gate_separation_certificate.py`, `gate_witness.py`, and
`gate_tool_manifest.json`.

Twenty one scripts and one manifest. Section 2.5 permits building them between
G1 and G3, because the confirmatory stamp binds to the first content-bearing
read at G3 rather than to the marker. So the correct sequence at the marker is
preflight, pin, then build the rest, then open anything.

The largest single item is `gate_separation_certificate.py`. Section 6 is the
only part of this protocol with no existing implementation to adapt. A search
for `semantic_separation`, `separation_certificate` and
`EQUIVALENT_TO_BASELINE` across every Python file in this tree returns zero
files. The witness half exists, in `level4_stepB/witnesses.py` with
`SEED = 424242`, and the nearest working analogue of the algorithm shape is the
frozen-probe witness separation in `cora_tti/constructive_v2_dataset.py`, which
runs against a different baseline space. Nothing enumerates `F(K_L4*)` and
compares fingerprints. The Step-B runner states in its own header that novelty
is decided later by a certificate it does not compute.

### 15.3 A related defect recorded elsewhere, and why it does not reach this gate

`docs/CORA_SELF_EXTENSION_LOOP_AUDIT.md` records four facts verified against
source, of which the load-bearing one is that in
`geocat_arc/object_reasoning/meta_induction.py` the concept path returns before
the ordinary search is reached, and omits the fold-coverability filter the
ordinary path applies. An augmented arm built on that path replaces the baseline
rather than adding to it, so it cannot support the second or the sixth conjunct.

This gate does not use that path. Section G7 step 1 pins the 3A rerun to
`geocat_arc.object_reasoning.meta_v21` and supersedes
`scripts/cora_level3_transfer.py` precisely because it imports the older
`meta_induction` stack. Section 5.1 forbids `without_concepts()` for the same
class of reason on the blind runtime, since it would strip `concept_0001`
alongside `e` and let W6 pass for the wrong reason.

The cross-reference is recorded here so that the exclusion is deliberate rather
than accidental, and so that any later stage tempted to reuse the
`meta_induction` path finds the reason it was excluded.
