# Guided-construction test: protocol amendment 3

Dated 6 Nov 2026, 12:00Z. This amendment follows the companion study's third-round review of version 3, recorded in
its notes 0522 and 0523 and its report `cage/guided_construction_c_independent_review_20261106_v3/REPORT.md` (sha256
bba3a271...). Our own re-check of version 3 found the same three points.

It was made before any GO. This study has run no held task, and has opened no held test output and no solution file.

Version 3 of the freeze is kept byte-identical as `FREEZE_V3.json` (sha256
29ca65634f03e58673b2d93c92ef84366d0a1191152731c1ea30e97f2fca376b). `FREEZE.json` version 4 pins this amendment
together with amendments 1 and 2. `PROTOCOL.md` is unchanged.

The review raised three narrow points, each a gap in a record's completeness or in reporting. None of them is a
wrong decision.

## 1. Every row must carry its demonstration count

Version 3 compared a row's demonstration count (`n_demos`) with the trusted count but accepted a row that had no
`n_demos` at all.

**Fix** (`gcon/verify.py`): every row must now carry `n_demos`, an integer equal to the trusted count. A row without
it makes the run INVALID.

The trusted count still decides which branch a task belongs to. That count comes from the task data behind the GO,
whose digests the freeze pins. The branch checks of amendment 2 are unchanged.

## 2. The returned driver record is bound to its digest

Version 3 bound each row file to the digest its kernel returned, but did not do the same for the kernel driver's
record (`kernel_run.json`).

**Fix** (`gcon/verify.py`): the copy of `kernel_run.json` used in verification must have the same sha256 as that
file's entry in the fetch receipt (`files_sha256["kernel_run.json"]`). A missing entry or a different digest makes the
run INVALID.

This completes the byte binding of the returned files. Nothing beyond this file was added.

## 3. The donor comparison total is reported

The held rows record `donor_feature_comparisons`, but version 3 of the scorer did not add it to the reported totals.

**Fix** (`gcon/score.py`): the scorer now reports `donor_feature_comparisons`, summed over the rows, beside
`donor_feature_cpu_s`. Both carry a "cache delta" scope label. A donor's hole setup is computed once and cached, and
its work is recorded only on the task that first computes it, so each sum is the total new donor work.

## 4. New regression cases (`launch/score_guard_test.py`; record `checks/SCORE_GUARD_TESTS.json`)

- A row without `n_demos`: verify gives INVALID. With a forged PASS receipt that carries every current digest, the
  scorer refuses before the marker.
- An edited `kernel_run.json` whose fetch digest is now stale: the kernel-receipt check fails. The same holds when the
  file's entry is missing from the fetch receipt.
- The scorer fed fake outputs, in a scratch copy with a scratch marker, reports the donor comparison total together
  with its scope label.

## 5. What did not change

The primary, the budget and the stop rule, the weights, the arms, the configuration, the engine, the features and
every development record are unchanged. So are the held tasks and the kernels' code, data and layout.

The package changes only because it carries `FREEZE.json`. Every packaged code and data file keeps its version 3
digest.

## 6. Files changed

`gcon/verify.py`, `gcon/score.py`, `gcon/freeze.py`, `launch/score_guard_test.py` and `launch/smoke_test.py`, which
now prints the new case's outcome. The new files are this amendment and `FREEZE_V3.json`.
