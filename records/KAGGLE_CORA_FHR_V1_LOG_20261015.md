# CORA_FHR_V1 Kaggle research entry: gates and log (opened 2026-10-15, 00:40Z)

**Authorization.** The user's directive "BUILD AND SUBMIT OUR FIRST GENUINE CORA-FHR KAGGLE RESEARCH
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
