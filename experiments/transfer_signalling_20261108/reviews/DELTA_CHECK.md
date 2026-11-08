# Delta check: T5 amendment 1 (transfer_signalling_20261108)

- **Date:** 8 November 2026.
- **Reviewer:** the pre-run reviewer (`reviews/PRE_RUN_REVIEW.md`, commit ddd52d70), checking the changed lines only.
- **Freeze checked:** commit cdd06c763a82fd06d06250c54d65a4289d0b1f12; FREEZE.json sha256
  56640e776b5671c1d17d9028b51c93ed1ca0dab7f81df04a56471f4e630dd670, covering 25 files.
- **Compared with:** the first freeze, commit 72f31059f186d82947c78bc50c491fb6e3a87945.
- **Not done:** no held scoring was run, and no held task or held fold was generated. The dry run and the tests ran on
  a scratch copy and on throwaway repositories.

## Verdict: PASS

The blocking defect is fixed and has a regression test. The salt now comes from GO.json, and its refusal checks work.
The dry-run numbers are unchanged. The coordinator may write GO.json as set out at the end of this file.

## 1. The frozen hashes: pass

- **All 25 files.** For every file listed in FREEZE.json, the working copy and the blob at cdd06c76 both match the
  recorded sha256 (25 of 25).
- **FREEZE.json itself.** It is byte-identical to its committed copy, with sha256 56640e77...
- **What the script will expect.** The script finds the freeze commit as the last commit that changed FREEZE.json.
  That is cdd06c76.
- **Unchanged since the first freeze:** `t5/data.py`, `t5/search.py`, `t5/tasks.py`, both configurations,
  DATA_MANIFEST.md, the four data files and the three core files. Their hashes are the same as at 72f31059.

## 2. The diff from 72f31059 to cdd06c76: pass

- **Changed in the study folder:**
  - `t5/model.py`: the step fix, and the docstring;
  - `t5/grow.py`: the docstring only;
  - `scripts/score_held.py` and `scripts/make_freeze.py`;
  - PROTOCOL.md, ADAPTER_CARD.md and PROGRESS.md;
  - the dry-run outputs, including the new `results_dryrun/P1_RESULT.json`;
  - the new tests, `tests/test_checker.py` and `tests/test_go.py`.

  The pre-review commit is also between the two freezes.
- **One change outside the study.** `scripts/make_public_snapshot.py` changed in two separate commits (2a26901b and
  b40bf1ea). These concern the public release, and the T5 run does not import the script.
- **No later changes.** No commit after cdd06c76 touches the study folder, the core folder or the launchers. The
  working tree matches cdd06c76, with no untracked files.
- **Nothing held exists.** Neither `results_held/` nor `outputs/detached/t5_held_score/` exists, and there is no
  GO.json yet.
- **The protocol and card changes** match the review's findings. The numbers they quote check out:
  - only 6 removable edges;
  - mek12 to erk12 in 48 of 160 tasks, giving 43 of the 62 and 113 of the 134 net held conditions;
  - p = 4.8e-6 and 1.4e-8.

## 3. The tests and the dry run: pass

- **`tests/test_checker.py` passes.** On the three-node program that never settles, the simulator and the checker now
  agree, and `check_models` does not raise. The NA mask carries a readout bit in the column that does not settle.
  `Obs.errors` counts that bit as wrong for every possible observed row. So a held condition with such a readout is
  scored as a mismatch (`exact` = 0), not reported as a crash.
- **`tests/test_go.py` passes.** A valid GO is accepted, and 7 invalid cases are refused:
  - wrong salt;
  - frozen file edited;
  - GO.json edited after commit;
  - FREEZE.json edited after commit;
  - an old freeze commit;
  - a bad nonce;
  - a wrong FREEZE.json hash.
- **The dry-run numbers are unchanged.**
  - The old and the new committed dry runs agree on every family's arm counts, pairs, seeds and folds.
  - For all 11 tasks, they also agree on every held outcome, final program and training error.
  - Re-running the dry run from a scratch copy of the frozen files reproduces the committed results exactly, CPU
    fields aside.
  - `P1_RESULT.json` equals the primary block of `RESULT.json`.
  - The log no longer doubles, because tasks.jsonl is now opened in write mode.

## 4. The GO.json refusal logic: pass, with notes

**Checked by reading and by test.** The scored run refuses to start in each of these cases:
- `results_held/` exists. A refused launch creates nothing, so a corrected launch is not blocked.
- GO.json is missing, or is not committed.
- GO.json or FREEZE.json differs from its committed copy at HEAD.
- GO.json lacks a required key, or its nonce is not 64 lowercase hex characters.
- `freeze_json_sha256` differs from the sha256 of FREEZE.json.
- `freeze_commit` is not the last commit that changed FREEZE.json, or is not an ancestor of the GO commit. A change
  to FREEZE.json after GO is therefore refused.
- A frozen file differs from its hash.
- `--salt` is not the sha256 of the GO.json bytes.

An unrelated commit after GO does not cause a refusal. GO.json cannot name its own commit, so GO must come after the
freeze. Every git failure leads to a refusal. The run records the GO and freeze provenance in RESULT.json.

**Notes (not blocking).**
1. **More than one GO commit is accepted.** If GO.json is committed more than once, the script takes the last version.
   The script also does not check that the GO commit holds GO.json alone. Commit GO.json exactly once, on its own.
   The post-score audit should confirm that `git log -- experiments/transfer_signalling_20261108/GO.json` shows one
   commit, which changes only that file and comes after this check's commit.
2. **The review hashes are not checked.** The script does not check them (PROTOCOL.md section 9 allows "any further
   keys"). They are recorded for custody only.
3. **Who holds the nonce.** PROTOCOL.md section 9 says that no one can compute a held item before the GO commit. In
   fact, the coordinator holds the nonce between drawing it and committing. Draw it immediately before the commit,
   and launch right after.
4. **A small line count error.** ADAPTER_CARD.md gives 466 lines of scripts; the frozen scripts have 469. This is
   cosmetic. Correct it in PROGRESS.md or RESULT.md, not in the frozen card.

## The GO.json to write

The script requires `freeze_commit`, `freeze_json_sha256`, `utc` and `nonce`. The two review-hash keys follow
PROTOCOL.md section 9 and `tests/test_go.py`.

```json
{
 "freeze_commit": "cdd06c763a82fd06d06250c54d65a4289d0b1f12",
 "freeze_json_sha256": "56640e776b5671c1d17d9028b51c93ed1ca0dab7f81df04a56471f4e630dd670",
 "utc": "<UTC time at GO, for example 2026-11-08T07:00:00Z>",
 "nonce": "<secrets.token_hex(32), 64 lowercase hex characters>",
 "pre_run_review_sha256": "3f2a6d0a00c8480d28254f971554ffba1f25e3aba53db841e4d649ecfd191edc",
 "change_review_sha256": "<sha256 of reviews/DELTA_CHECK.md, as committed>"
}
```

**Then:**
1. Commit GO.json alone, after this check's commit.
2. Take the salt as `sha256sum experiments/transfer_signalling_20261108/GO.json` of the committed file, and do not
   reformat the file afterwards.
3. Launch right away from the repository root:

   `sh scripts/run_detached.sh t5_held_score --slot python3 -I
   experiments/transfer_signalling_20261108/scripts/score_held.py --salt <that sha256>`
