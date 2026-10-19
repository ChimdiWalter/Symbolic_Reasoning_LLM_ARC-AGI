# CORA reasoning v2, Phase 2a: execution record (2026-10-19)

- **Protocol:** `records/CORA_REASONING_V2_PHASE2_PROTOCOL_20261019.md`, unchanged (sha256 0172ec8d2bf12518).
- **Authorization:** the user, 2026-10-19 ("FINISH ENGINEERING AND TEST REAL-TASK GAINS"). It covers one isolated
  eligibility check and the one Phase 2a run.

## 1. Eligibility (one isolated metadata-only check)

- **Checker:** `tools/stepb_eligibility/check_eligibility.py` (commit 5c5401a, sha256 357fb6fe113d81ef).
  - It ran once, with `python3 -I`, standard library only.
  - A synthetic self-test passed first.
- **Read:**
  - the ordered candidate list (100; sha256 3649268c60b136ef);
  - Step B's split manifest v1.0.0, after its sha256 matched Step B's logged value
    (cc797ba80ad781ef). Only the `task_id` and `split` fields were used.
- **E_transfer:** derived by Step B's frozen public rule (`prepare_inputs.py` at Step B commit 533e735).
- **Not read:** the provenance firewall and its secret, task contents, answers, Step B results.
- **Step B:** not modified. The manifest hash was identical before and after.
- **Result:** PASS, **44 of 100 eligible** (in Experience and not in E_transfer);
  eligible-list sha256 6b4ce11f52ee7353.
  - Of the 40 proposed before the check, 22 were eligible.
  - The 18 others are in Lockbox, Promotion or E_transfer, which ones is not recorded. That is close to the
    expected 55% protected share.
- **Phase 2a cohort:** the first 40 eligible, in the published order:

  444801d8 52fd389e f8cc533f b7fb29bc d8c310e9 ac0c2ac3 753ea09b 99306f82 e7639916 90f3ed37 928ad970 6f8cd79b b527c5c6 6aa20dc0 e73095fd af726779 f3b10344 f8f52ecc 72207abc 4612dd53 760b3cac d037b0a7 d43fd935 a699fb00 e5c44e8f 7df24a62 8e5a5113 d968ffd4 642248e4 6d75e8bb 5af49b42 963f59bc bf89d739 62b74c02 770cc55f 623ea044 9f5f939b 9b2a60aa 95755ff2 e9c9d9a1

## 2. Freeze and preflight

- **Code:** commit 4b95e86, frozen at 2026-10-19T15:02:47Z.
- **Bundles:**
  - `outputs/cora_revision_v2/phase2a/bundle.json` (sha256 e6b145b671d697cb): training pairs and test inputs
    only, under opaque keys;
  - the V view `bundle_v.json` (7ffb904b8aca09d1);
  - the key map is in `phase2a_evaluator/`, which no arm is given.
- **Arms:**
  - A: frozen native object branch, 90 s CPU;
  - B: 90 s × f_B, with f_B = 1.053. Native A mean CPU on the 118 engineering tasks is 297.9 s and v2's is
    15.8 s, so (297.9 + 15.8) / 297.9 = 1.053;
  - V: v2 reason + diagnose + decide, families "grow" as frozen, 600 s CPU.
- **Limits:** at most 2 workers; 6 h wall cap.
  - The children ran at nice 19: the scheduler at nice 10, plus the declared +10 per job. That is a lower priority
    than declared. Budgets are CPU time, so outcomes are unaffected.
- **Preflight PASS** (`phase2a/freeze.json`):
  - eligibility PASS; the cohort is the first 40 eligible;
  - the bundle hash matches; the bundle has no test outputs; keys are opaque;
  - no rows existed before the run; no engineering job was running;
  - code committed and clean; tests pass (21 passed in 24.13s);
  - V reproduces two recorded engineering rows exactly; arm A reproduces a recorded certified engineering answer
    exactly.

## 3. Run

RUNNING (`python -m cora_revision_v2.phase2a run`; log `phase2a/run.log`). The evaluator reads the answers only
after every arm's rows are complete or the wall cap has passed.

## 4. Result

PENDING.
