# Neural-CORA v2: the winning-path addendum — plan, implementation decisions, evidence (20 October 2026)

**The source.** The user's directive "CLAUDE CODE ADDENDUM — NEURAL-CORA: THE WINNING-PATH CORRECTION" (20 October),
with its summary.

**The authority it grants:**
- read-only architecture and failure audits;
- native-parity implementation in a new version;
- tests and bounded smoke runs on exposed or synthetic examples;
- protocol preparation.

**It requires a STOP before:**
- any new scored pilot;
- large training;
- protected evaluation;
- a Kaggle submission.

## 1. The state when the addendum arrived (step 0, checked)

**Repository and machine:**
- HEAD `74dee38`; the working tree is clean apart from the user's untracked ZIP and `voice_note/`. The addendum's
  "last commit 109fcfa" predates the v2 work.
- Running: only Step B (20 workers, not touched) and other users' jobs. Load 23–108.
- Memory: 48 GB available of 125.
- GPU 0 is free; GPU 1 belongs to another user. Both are RTX 2080 Ti, 11 GB, compute 7.5.

**v2 status:**
- ncv2-g1 is **already built** (the addendum's §1): the typed relational AST, the native bridge, macros, inventory,
  sound constraints and pairing-aware search (`cora_neural_v2/`).
- The **G2 protocol is frozen at `3677d0f`**, with G2a at 58 passed and 1 skipped. Its runner is locked behind the
  manifest and `--authorized`.
- **G2 has not run.** Neither of the two pastes authorizes it: the first states "I have not authorized"; the
  addendum says STOP before any scored pilot.

**Evidence, as recorded and not relabelled:**
- G1 NO-GO;
- 394/395 synthetic coverage at 3000 candidates (an ordering result);
- dev60 1/60 for the v1 language;
- native and FHR at 0.00% hidden;
- ka95aa62f67d9: the failure-blind arm also solved it;
- the 58-task construction comparison gained 0;
- Step B has no validated Level-4 verdict.

**The print candidate:** the cancer-lesion V2 poster and explainer (`docs/summit_20261023_reframe/`, built 19
October) are **unchanged**. The poster stays as it is for the 21 October freeze, as the pasted assessment
recommends.

## 2. Implementation decisions today, and why

1. **The frozen G2 code was not touched** (`cora_neural_v2/*.py`, the G2 runner, the two frozen test files). Any
   edit would break the freeze manifest. New work lives in new files:
   - `tests/test_neural_cora_v2_parity.py`;
   - `tests/test_neural_cora_v2_forensic.py`;
   - `scripts/neural_cora_v2_parity_bench.py`;
   - `scripts/neural_cora_v2_g2_forensic.py`.

   The lock was re-checked afterwards: still valid.
2. **Parity first, as §1 asks:**
   - 39 more hand-written native programs;
   - the semantics checklist: precedence, guard vs action, defaults, occlusion, composite order, multicolour,
     dimensions, stages, rejected constructs;
   - an inventory-coverage test;
   - a 60-task real-grid parity benchmark.

   Result: `records/NEURAL_CORA_G2_NATIVE_COVERAGE_INVENTORY.md`.
3. **The tokenizer was audited before designing object pooling**, as the pasted assessment asked. One token per cell
   is verified (`records/NEURAL_CORA_V2_LICENSE_AND_PRETRAINING_AUDIT.md` §2).
4. **An evaluator-only forensic analysis was pre-registered for G2 before the run**
   (`records/NEURAL_CORA_V2_CONTROLS_AND_GO_GATES.md` §0). It is descriptive and cannot change the frozen decision.
5. **Not done, on the addendum's schedule** (20–21 October: only cheap read-only G2 inventory and parity):
   - no GPU smoke test;
   - no repair controller;
   - no sketch decoder;
   - no grammar extension;
   - no package installation.

## 3. Evidence produced today

| what | result | where |
|---|---|---|
| parity of the remaining exposed ops + semantics | 61 tests pass | `tests/test_neural_cora_v2_parity.py` |
| real-grid parity, 71 programs × 200 dev60 demonstration inputs | 14,200 executions; **0 mismatches**; 4,247 changes; 1,582 identical EvalErrors; 25.8 CPU-s | `outputs/neural_cora_v2/parity_bench/dev60_demo_inputs_parity.json` |
| native semantics, characterized | occlusion follows object order; composite parts are sequential; first match; colour frequency counts objects | inventory §3 |
| tokenizer | 16-token WordLevel vocabulary, digits isolated, no BOS; 300 prompts, 0 misaligned | licence audit §2 |
| licences and rules | ARC-AGI-2 data Apache-2.0; the 2026 ARC-AGI-2 page: limits "will be announced"; Kaggle rules (12 Oct): notebooks ≤ 12 h; deadlines 2 Nov 23:59 (code), 9 Nov 23:59 (Kaggle paper track) | licence audit §5–6 |
| SOAR (ICML 2025) | an evolutionary search ↔ hindsight fine-tuning loop; "52% of the public test set" (the version is not stated on the PMLR page); no code link on that page | the prior-art record, row added |
| local ML stack | torch 2.11, transformers 4.57, accelerate 1.13; **no peft or bitsandbytes** | licence audit §5 |

## 4. The ten decisions

**(1) The present architecture and the missing arrows.**
- **Existing:** task state (partial) → C+H-style symbolic proposals (G1-CH) → typed AST → sound prunes and firing
  filter → native interpreter → consistent candidates and labels → two attempts → blind evaluator.
- **Missing:**
  - Qwen sketch and slot proposals;
  - one mixed agenda;
  - mismatch-cell traces, fold fragility and view sensitivity;
  - the revision decision and its execution;
  - calibrated selection.
- The box-by-box table is `docs/NEURAL_CORA_V2_JOINT_SKETCH_AND_FEEDBACK_SPEC.md` §1.

**(2) The actual failure of v1 G1.**
- v1 learned (198 > plain 104) but lost to hand features (235) and to C+H (358).
- Its heads ranked single components as well as C+H did, but they composed two-rule programs badly: 91/180 within
  3000, against 179/180 for C+H.
- It scored bags of components independently, with no pairing or binding
  (`records/NEURAL_CORA_V2_G1_FAILURE_ANALYSIS_20261020.md`).

**(3) Typed-language native parity.**
- 71 programs, each against a hand-written native dict.
- Every exposed native action and expression op is covered.
- Identical outputs on hand-built grids and on 14,200 real-grid executions.
- Not exposed: grow, synth_copy, matched_template, copy k/placement/keep_original, connect turn, crop_to tiling,
  the spec fill, and six program classes.

**(4) G2: search coverage vs expressibility.**
- On dev60, not yet measured, pending authorization.
- Known: native's object layer fits 30/60 and the v1 language 1/60.
- The frozen G2 measures g1 fit reach, correct coverage and pass@2. Its exhaustive single-rule check separates
  search misses from single-rule language gaps; the pre-registered forensic step adds single-rule *correct* reach.
- Multi-rule expressibility stays unproven either way.

**(5) The joint Qwen sketch design, compared with C+H.**
- N2-A is a joint head over frozen, exactly aligned Qwen object slots plus C+H features. It scores whole rules
  conditioned on earlier rules, or decodes grammar-constrained sketches whose holes C+H search fills.
- It is a residual on C+H (`score = C+H + r − cost`).
- Its value must beat both C+H alone and a hand-feature residual (controls record, arms 1–5).

**(6) Can NVARC's knowledge be used without a disguised second solver?**
- Possibly, through N2-B, where Qwen grids are **untrusted evidence** turned into sketch constraints. CORA builds,
  executes and checks every final answer.
- It is guarded by:
  - no fallback;
  - a program-dependence check;
  - a run with the neural evidence withheld;
  - a rationalization check;
  - separate reporting, credited as NVARC-model-assisted.
- It is not implemented. The licence limits reuse to the Apache-2.0 checkpoint with CORA's own decode code.

**(7) A real execution-feedback repair action, and its honest status.**
- ADD_GUARD from over-application on a *visible* demonstration: conjoin the feature test that separates changed from
  unchanged selected objects, then re-execute on every demonstration (spec §5.2, worked example).
- Status: **specified, not implemented**. G3 tests it against failure-blind, shuffled-trace, C+H-only and try-all
  controls.

**(8) Safety, licences, contamination, hardware.**
- No eval; typed AST; native interpreter only; evaluator separation; protocol locks.
- The checkpoint and ARC-AGI-2 data are Apache-2.0. The NVARC repo is unlicensed, and its notebook and data are
  unverified: they are not reused.
- dev60 and every cohort from the ARC-AGI-2 training file are contaminated for Qwen.
- Locally: fp16 only (no bf16); fp16 LoRA is marginal; NF4 needs bitsandbytes and peft, not installed. A 10-minute
  smoke test is proposed for after 21 October.

**(9) The frozen-proposed GO/NO-GO pilot, and the official timeline.**
- G2 is frozen at `3677d0f`.
- G1b-learned, G1b-Qwen, G1c-sketch, G3 and G5 are pre-registered in the controls record: exact McNemar with Holm
  correction, at least +3 points and +10 tasks, harms at most one third of the gains.
- Timeline: summit 23 Oct; entry 26 Oct; code 2 Nov 23:59; paper 8 Nov (Kaggle lists 9 Nov 23:59).
- No submission without G6 and the user's approval.

**(10) The single next experiment.**
- **The frozen G2 run on dev60:**
  - CPU only; 2 workers at nice 10;
  - at most 3.7 CPU-hours;
  - plus the pre-registered forensic step.
- It decides whether the larger language reaches real transformations at all. Without that, no neural proposer can
  help.
- **It needs the user's explicit authorization.**

## 5. Schedule (the addendum's §7, kept)

| dates | work |
|---|---|
| 20–21 Oct | poster unchanged for the print decision; only cheap read-only inventory and parity work (done) |
| 22–23 Oct | the summit, with current evidence. The guarded-rule demo is an OFFLINE RECORDED REPLAY |
| 24–27 Oct | the G2 run (once authorized); then one bounded exposure increment chosen by G2's diagnostics, under a new grammar version and protocol |
| 28–31 Oct | only if coverage merits it: one small N2-A proposer vs C+H and C+H + hand features (G1b) |
| 1–2 Nov | a Kaggle candidate only with: gains on a predeclared permitted cohort; a full offline rehearsal under 12 h; valid two-attempt outputs; licence checks; and the user's authorization |
