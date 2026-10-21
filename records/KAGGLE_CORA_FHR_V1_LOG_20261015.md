# CORA_FHR_V1 Kaggle research entry: gates and log (opened 2026-10-15, 00:40Z)

**Authorization.** The author's directive "BUILD AND SUBMIT OUR FIRST GENUINE CORA-FHR KAGGLE RESEARCH
ENTRY" (2026-10-14) authorizes ONE CORA-specific submission, if the real-development and notebook
integrity gates pass.

**Not allowed:**
- NVARC predictions;
- resubmitting NVARC;
- overwriting native_v1;
- automatic final selection.

## Method (what is submitted)

`kaggle/cora_fhr_v1/notebook.py` is built from `kaggle/native_v1/notebook.py` by asserted exact-string patches
(`make_notebook.py`).
1. **Native.** The unchanged native v23 harness runs from the unchanged dataset
   `chimdiwalter/arc-native-baseline-v1`, with the same 11.25 h budget (native_v1 needed 4.03 h).
   A lower budget was rejected because it could change native's per-task budgets. FHR starts tasks
   until 10.75 h and stops at 11.4 h.
2. **FHR** (`fhr_phase.py`). Each growth-shaped task that native's object layer did not certify runs
   `cora_fhr.measure.job(arm E)`, the development code path:
   - failure evidence (native's memorized-growth record);
   - G-grow construction;
   - reversible installation;
   - native gate;
   - tie abstention;
   - adaptive LOO;
   - the commit rule.
   Its modules come from dataset `chimdiwalter/arc-cora-fhr-v1`. The FHR import closure has 90 files;
   the 71 engine files among them are byte-identical to the native dataset.
3. **Answers.** Where FHR certifies, attempt_1 is its prediction and attempt_2 is native's attempt_1.
   Everywhere else, native's answers stand. `provenance.json` gives the origin of every output.

## Gates (declared before any result)

**G1, real development** (`followup_dev60.sh`: arms A, B, C′, E on the 60 dev tasks; ARC-AGI-2
**training** tasks, so contaminated for generalization):
- the pipeline completes; per-task errors are recorded;
- **0 wrong extension certificates by E**: a hard safety gate;
- **0 A-correct answers lost**: a hard safety gate;
- 0 restore failures;
- newly correct outputs and operator identities are reported. A gain is **not** required to submit
  (the directive). If there is none, it is reported as a limitation.

**G2, notebook integrity:**
- The offline emulation (`emulate.py`, network-guarded, 6 tasks including the synthetic witness)
  must show:
  - schema OK, full coverage, complete provenance;
  - an empty guard log and no FHR error;
  - the merge path exercised.
- The Kaggle committed run must:
  - complete in under 11.5 h, with all 240 stand-in tasks covered and 0 schema problems;
  - actually run the FHR phase, with not-reached tasks recorded;
  - have 0 restore failures;
  - produce native answers identical to native_v1's committed run: attempt_1 identical on at least
    95% of positions, with every difference listed. The native harness uses wall-clock deadlines, so
    it is not bit-deterministic. This threshold was set at 01:10Z, before any committed run.

**Submit only if G1's safety gates and G2 pass.** Any wrong certificate, lost answer, restore failure,
schema failure or overrun means no submission.

## Log

### 1. G2a offline emulation: PASSED (2026-10-15, 01:27Z)

- **All 11 checks pass:** notebook_rc0, schema, provenance, guard_clean, no_fhr_error, fhr_rc0, fhr_ran, merge_exercised, witness_correct, no_restore_failures, no_task_errors.
- **6 tasks:** 3 growth-shaped stand-in tasks, 2 others, and the synthetic witness.
- **FHR:**
  - skipped 1 (native object-certified) and 2 (not growth-shaped), and ran 3;
  - NO_PROPOSAL on 2;
  - CERTIFIED_WITH_EXTENSION on the witness with `ring(8)[part_minority]` (`fx_bd15c802b6bb4940`,
    NEW_COMPOSITION). It was merged as attempt_1 and is correct (development answer, read by the
    emulator only).
- 0 restore failures, 0 task errors, and an empty network-guard log.
- **Tested package sha256:** tarball 9910893f6decfe55, notebook.ipynb
  851fe2b1c2f3ebd7.

### 2. Deployment (2026-10-15, 01:28Z)

- Private dataset `chimdiwalter/arc-cora-fhr-v1` is ready.
- Kernel `chimdiwalter/cora-fhr-v1-arc-agi-2-research-entry` version 1 was pushed
  with internet disabled (checked from the pulled metadata: False).
- The committed run on the 240 stand-in tasks started at 2026-10-15T01:28:20Z.

### 3. Committed run, version 1 (Kaggle, 240 stand-in training tasks): G2b PASSED (checked 2026-10-18, 12:40Z)

| item | value |
|---|---|
| native harness | completed, rc 0, 4.01 h (native_v1: 4.03 h) |
| FHR phase | rc 0, 1.87 h, no error |
| total | 5.88 h (gate: < 11.5 h) |
| coverage and schema | 240 tasks, 259 outputs, 0 repairs, 0 schema problems |
| provenance | complete |
| native agreement with native_v1 | 258 of 259 attempt_1 identical (gate: 95%). The one difference, `28e73c20:0`, comes from the wall-clock deadlines |
| FHR | skipped 169 (not growth-shaped) and 9 (native object-certified); ran 62, reached all; 61 NO_PROPOSAL, 1 LOO_FAILURE; proposed 1, installed 1, used 1, verified 0, **committed 0**; 0 restore failures, 0 errors |

**Download incident.** The output includes the staged solver tree, so listing it pages many times.
- Default paging hit HTTP 429 and then 400 (2026-10-15).
- The pipeline failed safe (BLOCKED_OUTPUTS, nothing submitted).
- The two missing files were fetched on 2026-10-18 with `--page-size 200`, and the pipeline resumed.
- No gate was changed.

### 4. G1, real development (60 ARC-AGI-2 training tasks; contaminated): safety PASSED, NO GAIN

| arm | certified correct | wrong | lost | CPU |
|---|---|---|---|---|
| A frozen native | 6 | 0 | — | 4.87 h |
| B matched search (f_B 1.33) | 7 | 0 | — | 5.89 h |
| C′ failure-blind construction | 0 extension | 0 | 0 | 1.81 h |
| E authentic-failure FHR | 0 extension | 0 | 0 | 1.69 h |

E's outcomes: {"NO_PROPOSAL": 59, "LOO_FAILURE": 1}. Its single proposal was `hull[self]`, which is AVAILABLE_REACH
(not novel), and it failed LOO.

**No real-task gain from construction.** Matched search did one better than frozen native: 7 vs 6.

### 5. OFFICIAL SUBMISSION 57354496 (2026-10-18, 12:40:48Z)

- `kaggle competitions submit -k chimdiwalter/cora-fhr-v1-arc-agi-2-research-entry -v 1`, rc 0, "0
  submissions remaining today".
- Message: "CORA_FHR_V1: native CORA v23 + CORA-FHR failure-driven construction (G-grow, reversible install, adaptive LOO); notebook chimdiwalter/cora-fhr-v1-arc-agi-2-research-entry v1; no neural model, not NVARC".
- Status at submission: PENDING. The pipeline polls and writes
  `outputs/kaggle_deploy/cora_fhr_v1/official_score.json`.

**Limitation, stated before any score.**
- FHR committed no answer on the 240 stand-in tasks or on the 60 dev tasks.
- The submitted answers are therefore native's, except wherever FHR certifies on a hidden task.
- A score near native's 0.00 is expected.
- The entry documents a runnable implementation of the method, for the Paper Prize's code requirement.
  It is **not** evidence of unseen reasoning accuracy.

### 6. OFFICIAL SCORE (recorded by the pipeline at its 2026-10-18 18:31Z poll)

Submission **57354496**: `SubmissionStatus.COMPLETE`, **public score 0.00**.
- Row: "row, reversible install, adaptive LOO); notebook chimdiwalter/cora-fhr-v1-arc-agi-2-research-entry v1; no neural model, not NVARC SubmissionStatus.COMPLETE 0.00".
- This is exactly what the local evidence predicted. FHR committed no answer in the rehearsal, so the
  submitted answers were native's, and native v23 also scored 0.00.
- The entry documents a runnable implementation of the CORA-FHR loop on Kaggle. It shows no unseen
  accuracy.
- The guarded rule (18 October) is **not** part of this entry.
- Final selections are the author's; none was made automatically.
