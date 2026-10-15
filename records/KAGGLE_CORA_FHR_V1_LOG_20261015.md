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

`kaggle/cora_fhr_v1/notebook.py` is built from `kaggle/native_v1/notebook.py` by 7 asserted patches
(`make_notebook.py`).
1. **Native.** The unchanged native v23 harness runs from the unchanged dataset
   `chimdiwalter/arc-native-baseline-v1`. Its budget is 6.5 h; native_v1 needed 4.03 h.
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
  - produce native answers identical to native_v1's committed run, apart from documented budget
    effects.

**Submit only if G1's safety gates and G2 pass.** Any wrong certificate, lost answer, restore failure,
schema failure or overrun means no submission.

## Log
