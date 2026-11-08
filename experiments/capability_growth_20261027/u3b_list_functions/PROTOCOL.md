# Test U3b protocol: construction efficiency at matched compute (conditional follow-up on U3)

Frozen 2 Nov 2026 before any U3b run, and revised the same day, still before any run (revision 2). The sha256 of
this file and of every file it names is in `u3b_list_functions/PROTOCOL_FREEZE.json`. It addresses the independent
prefreeze review `<companion study folder>/u3b_blind_review_20261102/PREFREEZE_INDEPENDENT_REVIEW_V1.md`
(sha256 98e69a2d16cd1fe574ee08883d4560b4929551d2b7e80c63fe7b7c5222beb9c2) and the exact-byte re-review
`<companion study folder>/u3b_frozen_rereview_20261102/INDEPENDENT_REVIEW_V2.md`
(sha256 e91d07328c9a479bb2a1fabdb6a6f01e71d46897a1cb7ea6329eaa458e033c44). It runs only after the coordinator writes
`runs/GO_U3B` binding this file's sha256 and the freeze manifest's sha256 (section 7).

**Revision 2** replaces revision 1 (protocol sha256 f93d5dbb20b91495cca327c1c3559fb1a2b5a21ae91fefe5bb167b5305c2998d,
freeze manifest sha256 e3ebc844aead1b8f74b36f34406a04713690456142840d4228e79d21232d5240). It changes the provenance
gates and wording only (sections 6 and 7). The population, the arms and their order, the CPU accounting, the outcomes
and the statistical rules are unchanged.
1. The GO binds the freeze manifest as well as the protocol. Both lines are compared exactly at the chain start and
   before every stage, and the direct entry points run the same gate.
2. The generated build manifest must list exactly the required outputs, each matching, before the arms and before
   the evaluation, on resume as well. The arms and evaluation freezes record the manifest they verified.
3. A failed final commit ends as "EXIT 2 SAVE_FAILED", distinct from success.
4. Wording: the sketch content is demonstration-derived, overshoot work is reported as spent CPU, and any
   contextual attribution is stated beside each arm's measured CPU.

## 1. Question, ancestry, population, claim limit

**Question.** Does CORA's failure-triggered, demonstration-derived contextual hole specification construct a
useful schema member with less CPU than blind enumeration of the same schema space, when both get the same CPU
on every unit?
- S1 and U3 suggested an efficiency advantage, but neither compared at matched compute.
- **Ancestry.** This design, including the choice of the extended specification arm as primary, was made after
  seeing U3's outcomes.

**Population.** A conditional follow-up on the **same 250 BIG-bench list_functions concepts as U3** (same converted
file, sha256 15a98bf46e7c3db03c15e39d79f3c7e5533d4abf1cf7411f569f68b41cfb59ae).
- Query outputs are used to select the deleted operations and the eligible tasks, through the full DSL's
  query-correct programs and G0-plus-operation query correctness, and are scored later.
- U3b is not an independent dataset or an unbiased benchmark estimate, and gives no evidence of cross-domain
  universality.
- Task-level p-values are conditional and descriptive (families share sketch rules, donors and structures); seeds
  are within-task replicates.

**Claim limit.**
- A positive primary supports **construction efficiency within selected list functions only**.
- Constructed operations are members of the known 59-structure schema space: selection, not invention.
- Bounded G0 non-discovery is not proof of new expressivity.

## 2. Unchanged from U3

The DSL (`cgrow/u3/listdsl.py`), the schema language (`cgrow/u3/lschema.py`), the plug-in (`cgrow/u3/plugin.py`) and
the shared core's controller, candidate generation and admission gates (`cgrow/selfext_core.py`) are unchanged.
- **Base and novelty budgets:** as U3.
- **Demonstrations and queries:** 5 and 3.
- **Correct:** an attempt reproduces all three query outputs.
- **Seeds:** 0, 1, 2 (structure orders).

## 3. Construction (`cgrow/u3/run_u3b.py: build`, evaluator role)

1. **Full-DSL search** on all 250 concepts, as U3.
2. **Deletion.** U3's rule (usage order, greedy genuine-gap check, four operations), applied to the deletable
   operations **excluding U3's take, drop, remove, reverse**. G0 = the DSL minus the four new operations; U3's
   operations are back in G0.
3. **Family tasks.** A family task's first full-DSL program uses exactly one new deleted operation; G0 has no fit
   at the base budget; G0 plus the operation fits and predicts at the base budget. **U3's M, V and E family tasks
   are excluded.**
4. **Partitions.** Salt "u3b-20261102", hash orders as U3.
   - Per family: M 3, V 2, E up to 6.
   - U: 14 previously solved.
   - D: 4 decoys solved at 4x.
5. **Controller, motivating tasks and donors:** as U3.
6. **Specification cost.** The CPU of building each task's plain and extended sketches is timed at construction.
7. **Flow.** `build/concept_flow.json` gives every concept's filter outcomes and reason.

## 4. Arms

Unit = motivating task x seed.

- **S-hole-ext (primary guided arm):** the extended sketch rule from U3 (inner contexts include non-invertible unary
  operations and (list, constant) operations).
- **S-enum-MATCHED (primary control):** blind enumeration of the schema structures in seed order, with a strict
  CPU cap equal to S-hole-ext's charged CPU on the same unit.
- **S-hole:** S1's plain rule.
- **S-demo:** the identity sketch, the demonstrations themselves. Same candidate filtering, retry cap and accounting.
- **S-shuffled:** the donor's plain sketches.
- **S-shuffled-ext (new):** the donor's extended sketches, with the same generator and accounting as S-hole-ext.
  It isolates task-specific context from the richer generator.
- **S-enum:** blind enumeration with a strict 60 CPU-s cap.
- **C7m:** G0 search, 150 CPU-s per task.

**Admission (shared core gates), identical for every arm:**
1. Novelty.
2. Retry, at most 3 for the specification arms.
3. Regression on U.
4. Validation on the pool; stop at the first promoted candidate.

The specification arms use `run_spec_unit_timed`. It is the core's specification unit (verified identical on
synthetic tasks) plus completion timing.

## 5. CPU accounting (the same for every arm)

**Charged CPU** = specification cost (sketch building timed at construction plus candidate filtering timed in the
arm; 0 for S-demo's identity sketch) + gate CPU (novelty, retry, promotion checks). Each cached result is charged
at the CPU of its first computation.

**Strict cap (blind arms, `run_enum_unit_strict`).**
- Each stage (novelty, retry, promotion checks) counts only if it completes within the cap.
- The first stage that would cross the cap ends the unit. It is recorded as overshoot and never counted.

**Completion-time timing, both arm types.** Every retried candidate records the cumulative charged CPU at its
retry's completion, at run time. A unit's recovery time is the completion CPU of the first retry that fits and
predicts every query.

**Anytime curve.** For budgets b in {0.25, 0.5, 1, 2, 4, 8, 16, 32, 60} CPU-s, a task counts as recovered at b if
its recovery time is at most b in at least 2 of 3 seeds:
- S-hole-ext: from its own units;
- S-enum: from its 60 CPU-s units.

No replay is used.

## 6. Outcomes, freezes, tests

**Outcomes, each reported separately at task level (majority of 3 seeds):**
- **trial recovery:** a retried candidate fits and predicts every query;
- **admitted:** a fitting candidate passed regression;
- **promoted:** it passed validation;
- **excluded-task reuse:** promoted structures on the E tasks (base search with G0 plus the structure);
- agreement with each deleted operation (evaluator diagnostic).

**Freezes before outputs.**
- The construction writes `build/BUILD_MANIFEST.json` with the sha256 of exactly its seven outputs
  (`concept_flow.json`, `full_dsl_search.json`, `g0_search.json`, `plan.json`, `records.pkl`, `tasks_eval.json`,
  `tasks_system.json`), never of itself.
- The arms stage verifies that manifest before reading any build output, and reads only the verified bytes. It
  writes `arms/ARMS_FREEZE.json` with the sha256 of `units.json`, `c7m.json` and the verified build manifest.
- The evaluation verifies the build manifest and the arms freeze, which must name that manifest, before reading any
  build or arms output. It reads task outputs (`tasks_eval.json`) only after these checks and only from the verified
  bytes. It writes `eval/EVAL_FREEZE.json` with the sha256 of `results.json`, the arms freeze and the build manifest.
- Agreement and reuse never feed admission or selection.

**Primary.** Trial recovery, S-hole-ext vs S-enum-MATCHED; exact two-sided McNemar over the motivating tasks,
alpha = 0.05.

| condition | decision |
|---|---|
| fewer than 6 motivating tasks | "underpowered" (not overridable by any secondary) |
| p < 0.05 with more S-hole-ext wins | "confirmed" |
| p < 0.05 the other way | "reversed" |
| otherwise | "not confirmed" |

**Secondary** (Holm-adjusted within these three):
- S-hole-ext vs S-demo (trial recovery, exact McNemar);
- S-hole-ext vs S-shuffled-ext (trial recovery, exact McNemar);
- area under the anytime curve, S-hole-ext vs S-enum. Per task: the mean over the grid of recovered at b; paired
  task differences; exact two-sided sign-flip permutation test.

**Descriptive:**
- per-family effects;
- S-hole-ext vs S-shuffled, vs S-hole, vs S-enum, vs C7m; S-enum vs C7m; S-demo vs S-shuffled-ext;
- mean charged CPU per arm;
- the number of S-enum-MATCHED overshoots, and the blind arms' mean charged CPU including each overshooting stage
  (work done, never counted).

**Causal reading, fixed now.** Task-specific demonstration context is credited only if the primary is confirmed
**and both** secondary McNemar tests (vs S-demo and vs S-shuffled-ext) are significant after Holm. Otherwise the
claim is construction efficiency only.
- The sketches are built from the demonstrations; the failed G0 search only triggers their construction. No claim
  is made that failed-program traces supply sketch content.
- The controls' charged CPU is not matched per unit. Any contextual attribution is stated beside each arm's
  measured charged CPU and is conditional on that work.

**Exploratory, post hoc.** U3's tasks are scored with the same contrasts, replayed from U3's frozen gate cache
only. A missing entry is "unavailable" and nothing is recomputed. U3 charged no specification CPU.

## 7. Gate, budget, outputs

**Hold and GO.**
- `runs/HOLD_U3B` marks the hold, as for U2b. There is no deadline fallback.
- The run needs the coordinator's `runs/GO_U3B`, whose first two lines are exactly
  `protocol_sha256 <sha256 of this file>` and `freeze_sha256 <sha256 of u3b_list_functions/PROTOCOL_FREEZE.json>`.

**Provenance gate** (`cgrow/u3/u3b_gate.py`, standard library only, run with `python3 -I`).
- At the chain start and before each stage (construction, arms, evaluation, save), it recomputes both digests from
  the live files, compares the two GO lines exactly and re-verifies every hash in `PROTOCOL_FREEZE.json`.
- Before the arms, the evaluation and the save, it also verifies the build manifest: exactly the seven required
  outputs, no missing or extra entry, never itself, each matching. Before the evaluation and the save it verifies
  the arms freeze, and before the save the evaluation freeze.
- The direct entry points (`python -m cgrow.u3.run_u3b build | arms | evaluate`) run the same gate first.
- `cgrow/u3/verify_freeze.py` remains as a stand-alone check of the freeze for reviewers.

**Resume and fail fast.**
- `sh resume_u3b.sh` launches the chain only when the gate passes.
- A stage whose freeze (build manifest, arms freeze, evaluation freeze) exists is verified, never rerun. The
  construction is never redone once arms outputs exist, nor the arms once evaluation outputs exist. A partial
  construction or arms stage resumes from its own outputs.
- A gate or stage failure writes "EXIT 1 <reason>" and stops, with no later stage.

**Save.**
- The chain commits only the U3b output paths, with three attempts.
- If all three fail, it writes "EXIT 2 SAVE_FAILED". The results stay frozen on disk and the research stages are not
  marked failed; `sh resume_u3b.sh` then verifies every freeze and retries only the save.
- "EXIT 0 chain done" means every stage passed and the results are committed.

**Budget.** CPU only, through `scripts/with_cpu_slot.sh` (nice 19), soft ceiling 2.5 CPU-h. No GPU, no Kaggle, no
Step B, VDCG or other projects' job folders.

**Outputs.**
- `u3b_list_functions/build/` (with `BUILD_MANIFEST.json`), `arms/` (with `ARMS_FREEZE.json`), `eval/results.json`
  and `eval/EVAL_FREEZE.json`;
- `reports/TEST_U3B_REPORT.md`, whose "Claim for the paper" section is written whichever way the result falls:
  - **primary confirmed:** "on a conditional operation-removal population of BIG-bench list functions, CORA's
    contextual hole specifications selected useful schema members with fewer CPU seconds than blind enumeration,
    under the declared budgets";
  - **otherwise:** the counts, plainly, with no efficiency claim.
