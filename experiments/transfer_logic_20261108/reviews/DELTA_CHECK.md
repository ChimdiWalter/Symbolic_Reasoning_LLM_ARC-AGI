# Delta check after Amendment 1: logic recovery transfer study (transfer_logic_20261108)

- **Reviewer.** The same independent reviewer as `reviews/PRE_RUN_REVIEW.md`, which is commit 99ec4245 (file sha256 `d730e7af...f498`).
- **First freeze, failed:** `cb4369883501797581ff201a102923cefc2f43ef`.
- **Amended freeze, checked here:** `73e11d26f54ac203ce79744cc46e6f1c25257879`.
- **FREEZE.json sha256:** `853a603e91660afaf517f098c08166cc55b813dcbe3ebe0f619824c20d05bc8a`, both at the commit and in the working tree.
- **Date:** 8 November 2026.

## Verdict: PASS

The amended freeze fixes both blocking findings of the pre-run review, and it changes nothing else that the scored run uses. The coordinator may write GO in the format given at the end of this file.

## Scope and method

**What was checked.** The changed lines only, against the four checks the coordinator asked for.

**How.**
- Hashes and diffs were read with git, limited to the study folder and the reused statistics module.
- All test code ran in a scratch folder outside the repository, with `python -I -B` and a scratch bytecode cache.
- The checks were tested on throwaway git repositories rebuilt from the two freeze commits with path-limited `git archive`.

**What was not done.**
- `score_held.main()` was never called, because it would select held items.
- No held item was selected or scored.
- Nothing was written in the repository except this file.

## 1. Every FREEZE.json hash at 73e11d26: PASS

- All 19 listed hashes match the working tree. The list of files is the same as at the first freeze.
- The 17 tracked files also match their blobs at `73e11d26`. The two data archives are gitignored by design, and they match.
- Five hashes changed: `tlogic/data.py`, `score_held.py`, `DATA_MANIFEST.md`, `PROTOCOL.md` and `ADAPTER_CARD.md`.
- Fourteen are unchanged:
  - every arm, learner and statistics file (`core.py`, `arms.py`, `classical.py`, `pla.py`, `policy.py`, `stats.py` and `__init__.py`);
  - `config.json`;
  - the unit tests;
  - `fetch_data.sh`;
  - both data archives;
  - both files of the reused statistics module.
- The recorded environment is unchanged: Python 3.12.3, numpy 2.4.3 and scikit-learn 1.8.0.
- The working tree equals `73e11d26` for this folder. The only untracked paths are the ignored `data/` and bytecode caches.

## 2. The diff from cb436988 to 73e11d26 holds only the intended changes, and no held item was chosen: PASS

**Commits.** Two commits touch the folder between the freezes: the review (99ec4245) and the amended freeze (73e11d26). The first freeze is an ancestor of the amended one, and the amended one is an ancestor of HEAD.

**What 73e11d26 changes** (seven files in the folder):

| File | Change | Matches the review's fix and PROTOCOL.md section 10 |
|---|---|---|
| `tlogic/data.py` | `held_items` now accepts only a 64-character lowercase hex salt; the docstrings are updated | yes; nothing else in the file changed |
| `score_held.py` | the review's `checks()`, verbatim, plus two additions (below) | yes |
| `PROTOCOL.md` | header note, section 2 salt rule, section 7 rewritten, four caveats added to section 9, new section 10 | yes |
| `DATA_MANIFEST.md` | Berkeley notice, the salt rule, the held policy stream, `index.html` marked as provenance only | yes |
| `ADAPTER_CARD.md` | line counts | yes: `data.py` 73, `score_held.py` 179, total 1,281 |
| `PROGRESS.md` | narrative only; not hashed | yes |
| `FREEZE.json` | five new hashes | yes |

**The two additions to `checks()`:**
- **First-commit rule.** `git log --format=%H HEAD -- <absolute path of GO>` must list exactly one commit, so a GO replaced after its first commit is refused.
- **Version check.** The run refuses when the Python, numpy or scikit-learn version differs from FREEZE.json.

**The rest of `score_held.py`:**
- `--salt` and `argparse` are removed.
- `main()` creates `results/` before the checks.
- The salt and the freeze commit are written to `run.status`, on both the STARTED line and the DONE line.
- They are also written to `summary.json`, together with a `salt_rule` field.
- The docstring's launch line is the `run_detached.sh` command the review gave.

**Unchanged between the freezes:**
- `scripts/run_detached.sh` and `scripts/with_cpu_slot.sh`;
- the reused statistics module;
- the development results, the development and helper scripts, the tests and `config.json`.

**No held item chosen:**
- There is no `GO` and no `results/` in the working tree.
- Neither path has ever been committed on any branch: `git log --all` on both lists nothing.
- HEAD has no commit touching GO.
- The last commit on HEAD that changed FREEZE.json is `73e11d26`, which is exactly what GO must name.

## 3. The checks accept and refuse as intended: PASS

**Setup.** The throwaway history reproduces both freezes: first the files at `cb436988`, then the files at `73e11d26`. The FREEZE.json sha256 in the copy is `853a603e...`, the same as the real one. Each scenario ran on a fresh clone. GO was written in the protocol's format with a fresh nonce, and only `checks()` was called.

| Scenario | Outcome |
|---|---|
| no GO | refused: no GO file |
| well-formed GO, not committed | refused: not committed at HEAD |
| well-formed GO, committed once | **accepted**; the salt equals the sha256 of the GO bytes, and the freeze commit returned is the amended one |
| the same GO, then edited to NO-GO in the working tree | refused: first line is not GO |
| the same GO, then replaced by a second well-formed commit | refused: changed after its first commit |
| GO naming the first freeze commit | refused: not the last commit that changed FREEZE.json |
| GO naming a parentless commit that has the amended tree | refused: same reason |
| wrong FREEZE.json sha256 | refused |
| nonce of 6 characters | refused |
| nonce in upper-case hex | refused (the nonce must be lowercase) |
| committed GO reading NO-GO | refused |
| GO starting with a byte-order mark | refused |
| accepted GO, but `config.json` changed | refused: hash mismatch |
| accepted GO, but `results/held.jsonl` exists | refused: one scored run only |
| accepted GO, with a different numpy, scikit-learn or Python version reported after import | refused, naming the library and both versions |
| accepted GO, with the frozen versions | **accepted** |
| minimal GO: only the first line, `freeze_commit`, `freeze_json_sha256` and `nonce` | **accepted** (see note 3) |

`data.held_items` raises ValueError for a 40-character salt before it reads any item.

## 4. The development results are unchanged by the amendment: PASS

**The committed files are unchanged.** All four files in `dev_results/` are byte-identical between the freezes.

**Recomputed with the amended code.** I recomputed all 348 committed development rows, with the same arms and fractions. 312 are identical in every field, ignoring CPU timings:
- all 84 circuit rows at 25% (in `dev1.jsonl`);
- all 84 at 12.5%;
- all 84 at 50%;
- all 48 version 2 policy rows.

**The other 36 rows** are policy rows in `dev1.jsonl`, differing only in the grown, shuffled and active-probing arms.
- They were produced before the first freeze, by version 1 of the policy growth rule. That is the revision recorded in PROTOCOL.md section 9.
- Recomputed with the version 1 modes (`grown_arity` and `shuffled_arity`), every outcome field of all 48 of those rows matches.
- So they predate both freezes, and the amendment did not change them.
- The two freezes compute identical development results. The only code change that reaches item handling is the salt-length check in `held_items`, which development never calls.

## Non-blocking notes

1. **FREEZE.json's `note` field is stale.** It still says "Held items are chosen with the freeze commit hash as the salt". `make_freeze.py`, which is not hashed, writes that text and was not updated.
   - The run reads only the hashes and the environment from FREEZE.json, and PROTOCOL.md sections 2 and 10 govern.
   - A fix would need another re-freeze, which is not worth it.
   - RESULT.md should mention the stale note in one line, and `make_freeze.py`'s text should be fixed before any future freeze.
2. **Version 1 rows in `dev1.jsonl`.** Its policy arms named grown and shuffled are version 1 results. Anyone recomputing them must use `grown_arity` and `shuffled_arity`, as in check 4.
3. **The code checks only part of GO.** It checks the first line, `freeze_commit`, `freeze_json_sha256` and `nonce`. The other three lines (`study`, `pre_run_review` and `written_utc`) are for the record, but write all seven, as section 7 says.
4. **The first committed GO is final.** A mistake in it cannot be undone without another amendment. Run the self-check below before committing.

## The GO file this check accepts

**Path.** `experiments/transfer_logic_20261108/GO`.

**Encoding.**
- plain ASCII, with LF line endings and one final newline;
- no byte-order mark and no trailing spaces;
- each field is written `name: value`, with one space after the colon.

**Fields, in this order:**
```
GO
study: transfer_logic_20261108
freeze_commit: 73e11d26f54ac203ce79744cc46e6f1c25257879
freeze_json_sha256: 853a603e91660afaf517f098c08166cc55b813dcbe3ebe0f619824c20d05bc8a
pre_run_review: <the 40-character hash of the commit that adds this file>
nonce: <64 lowercase hex characters, drawn once, now>
written_utc: <YYYY-MM-DDTHH:MM:SSZ>
```

**Rules for the nonce.**
- Draw it once, after this check is committed: `python3 -c "import secrets; print(secrets.token_hex(32))"`.
- Never reuse it, show it to the designer before GO is committed, or redraw it.
- The salt is the sha256 of the exact committed bytes of GO. The run derives it and records it in `results/run.status` and `results/summary.json`.

**Self-check before committing.** Run this from the study folder:
```sh
python3 -I - <<'EOF'
import hashlib, os, subprocess
go = open("GO", "rb").read(); lines = go.decode("ascii").split("\n")
f = dict(l.split(": ", 1) for l in lines[1:] if ": " in l)
last = subprocess.run(["git", "log", "-n", "1", "--format=%H", "HEAD", "--", os.path.abspath("FREEZE.json")],
                      capture_output=True, text=True).stdout.strip()
ok = [lines[0] == "GO", go.endswith(b"\n"), b"\r" not in go,
      list(f) == ["study", "freeze_commit", "freeze_json_sha256", "pre_run_review", "nonce", "written_utc"],
      f.get("study") == "transfer_logic_20261108",
      f.get("freeze_commit") == last == "73e11d26f54ac203ce79744cc46e6f1c25257879",
      f.get("freeze_json_sha256") == hashlib.sha256(open("FREEZE.json", "rb").read()).hexdigest(),
      len(f.get("pre_run_review", "")) == 40,
      len(f.get("nonce", "")) == 64 and all(c in "0123456789abcdef" for c in f.get("nonce", ""))]
print("GO self-check:", "OK" if all(ok) else "PROBLEM " + str(ok))
EOF
```

**Then commit GO alone.** From the study folder: `git add GO; git commit -m "<message>" -- GO`, with no other file and no later edit.

**Then launch once,** from the study folder:
`sh ../../scripts/run_detached.sh transfer_logic_held --slot python3 -I score_held.py`
