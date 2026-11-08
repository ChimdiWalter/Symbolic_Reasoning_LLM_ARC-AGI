# Failure-guided choice test, revision 2: delta check after the amendment

Reviewer: the independent review session that wrote `reviews/PRE_RUN_REVIEW.md` (PASS-WITH-NOTES, final commit
cf62f59b). Written 8 November 2026, before any GO.

**Scope.** The changes a94ed58c..d9b7ffc6 in this folder, and nothing else; everything else was checked in the
pre-run review and is unchanged. The amendment was swept into the autosave commit 71fd6f3f. d9b7ffc6 adds only the
`PROGRESS.md` entry, and both commits hold the same `PROTOCOL.md` and `FREEZE.json`.

**What I did not do.** I wrote no GO, generated or opened no held task, pushed or queried nothing on Kaggle, and
scored nothing. Every rerun used a scratch copy extracted from d9b7ffc6, plus the six git-ignored dependencies copied
byte for byte.

## Verdict: PASS

- The amendment does what it says, and nothing else changed.
- No held task exists or was generated.
- The view-fill estimate uses source-side information only, reproduces, and is a sound planning estimate.
- The primary (F, the fixed router, against C, the static full bank) and C's pre-registered order are untouched.
- Section 10 carries my four conditions.

The notes in section 6 are not blocking. The GO file I would accept is in section 7.

## 1. Hashes at d9b7ffc6

- **The two digests:**
  - `PROTOCOL.md` is a649691170e43c712c8e383475af69457598b1b91a0553695c6694e0993a71bd;
  - `FREEZE.json` is fae62f8842bebc68baee8927051bcceb89fb75bef30ac7a3715df7fb7ee53e92.

  Both hold in d9b7ffc6, in 71fd6f3f and in the working tree. No later commit touches the folder, and its working
  tree is clean.
- **Every frozen digest matches.**
  - The 96 study files and 35 tracked dependencies match both the d9b7ffc6 blobs and the working tree.
  - The six git-ignored dependencies and the ARC training challenges file match by digest.
- **Against a94ed58c's freeze record:**
  - no file was added or removed;
  - dependencies and data are unchanged;
  - exactly four study digests changed: `PROTOCOL.md`, `config/STUDY_CONFIG.json`, `fgc/develop.py` and
    `fgc/generate.py`.
- **The live gate refuses only for want of `GO_FGC`.**

## 2. Only the intended changes; nothing held

- **Files changed in the folder:**
  - the four frozen files above;
  - `FREEZE.json`;
  - `PROGRESS.md`, append-only: the viewfill job's two lines and the amendment entry;
  - three new unfrozen files: my `reviews/PRE_RUN_REVIEW.md`, `runs/dev/VIEW_FILL_ESTIMATE.json` and
    `runs/status/viewfill.status`.
- **`config/STUDY_CONFIG.json`:** `n_view_test_per_op` goes from 2 to 5, and the mix note is rewritten. Nothing else
  changed: families, the 6 missing-operation tasks per family, the 8 depth tasks per world, size caps, the 150 tries,
  salts and pools.
- **`fgc/generate.py`:**
  - The held view loop moves, unchanged in content, into a new `test_view_rows`. It now runs before the
    missing-operation and depth tasks.
  - On the Kaggle path (`test_world_rows`), it runs after the world's share filter is installed.
  - On the local `test()` path, it now also uses the configured 150 tries.
  - The exclusions, the merge's refusals and the source paths are unchanged.
- **`fgc/develop.py`:** additions only, the `viewfill` function and its command. `constants`, `learn` and `power` are
  unchanged.
- **Unchanged, and re-verified at d9b7ffc6:**
  - the contract, pipeline, arms, gate and router files;
  - the contract checks, which rerun byte-identical;
  - `runs/dev/CONSTANTS_EVIDENCE.json` and the source seal, which reproduce byte for byte.
- **The four reused source grids.** They were already outside the held set in a94ed58c: revision 1's held labels and
  this revision's source labels are both exclusions. The amendment corrects the protocol's text, which is all that
  was needed.
- **Nothing held exists.**
  - There is no `GO_FGC`, `runs/RUN_CLAIM.json`, `runs/test/`, `runs/test_parts/` or held kernel folder, in the
    working tree or in history.
  - `runs/kaggle/` holds only the eight development kernels, and the poll log names only them.
  - The only generator run since the freeze is `outputs/detached/fgc2_gen_smoke2`. It ran the same script as the
    first smoke test:
    - on the pilot pool, which is disjoint from the main pool;
    - with the salt "smoke-salt", one world, reduced quotas and 15 tries;
    - writing nothing.

    It built its view task first, as the amendment intends.

## 3. The view-fill estimate

- **It uses source-side information only.** `fgc.develop viewfill` reads four things:
  - three grid-only properties of the main pool's ARC training input grids: the number of inputs, the largest side,
    and whether some colour is absent from every input;
  - this revision's source labels, to see which source view slots filled;
  - the source salt, to recover each source slot's view;
  - the exclusion lists.

  It applies no held operation, uses no held salt, and generates no task.
- **It reproduces.** Rerun on the scratch copy, its output is byte-identical to the committed
  `runs/dev/VIEW_FILL_ESTIMATE.json`.
- **The fit is right.**
  - The 27 recovered source slots hold exactly the 14 source view tasks, each in a slot of its own view.
  - An independent maximum-likelihood fit on a 10-times finer grid gives the same pass rates per eligible source:
    0.0888 for box, 0.0278 for backdrop, 0.0055 for delta.
- **The method is sound for choosing a quota.**
  - Every source slot scanned its world's whole share: 96 to 128 sources, under the 150 tries. So a slot's fill is
    the smaller of its slot count and the number of passing sources. That is the likelihood used.
  - The choice rule is applied as written. Quota 4 gives an average of 20.1 held view tasks in the main scenario but
    16.6 in the half-rate scenario, below the target of 18. Quota 5 gives 24.1 and 19.7, so 5 is the smallest that
    reaches 18 in both.
- **Its assumptions are stated in sections 3 and 9.**
  - Held operations pass at the source operations' rates.
  - Sources larger than 16 x 16 pass at the same rate, at half the rate, or never. These are most of the held eligible
    sources; only 13 of 43, 18 of 50 and 12 of 37 are at most 16 x 16. The three cases give averages of 24.1, 19.7
    and 12.4.
  - Two operations never compete for the same source. This makes the held count slightly optimistic and the fit
    slightly conservative.
- **Calibration is a consistency check, not a validation.** A simulated source build gives 13.8 against 14 observed,
  but that is in-sample.
- **A weak outside check agrees.** Each pilot smoke test applied the held operations to about 30 eligible pilot
  candidates and kept one (the same task both times). That is roughly 0.03 per candidate, close to the source mean of
  0.041.
- **The power figures are upper bounds.** The amended power of 0.982 (0.956 at half rate, 0.785 if larger sources
  never pass) stays an upper bound for the reasons section 9 lists.

## 4. The primary is not biased, and C stays pre-registered

- **C is untouched.**
  - `config/ROUTERS.json` is unchanged, with static order construction, then search, then view.
  - The seal reads that order, and the contract and pipeline are unchanged.
  - So the primary, the ladder and the statistics are as pre-registered.
- **The mix change is legitimate.**
  - It was decided from source-side information only, before any held task existed.
  - It changes which tasks are drawn, not how any arm is run or scored.
  - It raises the expected number of discordant tasks, which is its purpose. It also shifts the held mix toward the
    view cause.
- **Section 3's claim checks out, and the mix alone cannot make F win.** I projected the source set's solve rates by
  cause onto 36 missing-operation, 24 depth and 24 view tasks:

  | order | projected correct |
  |---|---|
  | C (construction, search, view) | 38.7 |
  | construction, view, search | 40.8 (+2.1) |
  | F | 55.9 |

  So C is no longer the best fixed order on the expected held mix, by about 2 tasks. F's projected lead over the best
  fixed order is about 15 tasks.
- **The six fixed orders are descriptive only (section 7).** `pipeline.decide`, which is unchanged, never sees them,
  and no frozen code computes them. They must be computed after `ANALYSIS.json` is committed, with these settings:
  - the frozen `contract.run_arm`, on the committed measurements;
  - at T\* (the binding budget, 3,000,000 calls), with no descriptor charge, as for C;
  - all six reported, not only the best.

  The script that computes them should be committed with its output.

## 5. Section 10 against my conditions

| my condition | section 10 | match |
|---|---|---|
| GO third line naming the final review; dry `gate.py measure`; GO committed before the claim, never edited | step 1 (the third line generalised to "<its verdict>") | yes |
| claim prints "ok generate" and is committed | step 2 | yes |
| new kernel names: R2_TEST_GEN, R2_TEST_1 to R2_TEST_4, never TEST_1 to TEST_3 | steps 3 and 5; a recovery uses a new kernel name | yes |
| new job names: fgc2_test_merge, fgc2_seal, fgc2_score, never fgc_seal or fgc_score | steps 4 and 6 | yes |
| salt in the notebook and package check "none" before each push; folder committed first | steps 3 and 5 | yes |
| isolation check (0 reused, 0 duplicates, no family outside the plan) and the view count recorded with its power | step 4 | yes |
| `gate.py measure` "ok" recorded; id check "missing 0 extra 0" before the seal | step 5 | yes |
| a commit before each stage; seal once; score once | preamble and step 6 | yes |

The check scripts are "the exact commands of `reviews/PRE_RUN_REVIEW.md` section 8". Its isolation check still fits
the amended plan, because the view families keep their names.

## 6. Notes (not blocking)

1. **Cost.** Generation is now estimated at up to about three hours. That is within a Kaggle CPU session's 12-hour
   limit. If generation fails, the recovery clause applies under a new kernel name.
2. **Generation may not repeat exactly.** Section 10 says generation is deterministic. That holds only if the
   construction test's builder does not hit its CPU caps (20 CPU-seconds per 150,000 calls) in the
   missing-operation filters. A repeat after a failure should be compared task by task with any earlier output.
3. **Power above 18 view tasks.** Section 10 step 4 points to the reviewer's table, which stops at 18 view tasks of 2
   per family. For a realised count above 18, quote the amended estimate at the realised count, labelled an upper
   bound.
4. **The local path stays unsanctioned.** The local `test()` path builds a different held set from the same salt,
   because it has no share split. It is not part of the procedure, and once the claim exists the gate refuses it.
5. **Smoke-test inputs live in scratch.** `fgc2_gen_smoke2` ran a script that sits in a scratch folder outside the
   repository. Its command line and output are kept in `outputs/detached/`, and it wrote no study file.

## 7. The GO file I would accept

This supersedes `reviews/PRE_RUN_REVIEW.md` section 10, whose first two lines named the old freeze. `GO_FGC` in the
study folder must be exactly the three lines below, and nothing else:
- ASCII text;
- each line ends with one LF, including the last;
- one space between fields;
- no trailing spaces.

```
protocol_sha256 a649691170e43c712c8e383475af69457598b1b91a0553695c6694e0993a71bd
freeze_sha256 fae62f8842bebc68baee8927051bcceb89fb75bef30ac7a3715df7fb7ee53e92
pre_run_review <the full 40-hex commit that last changed reviews/DELTA_CHECK.md> PASS
```

Write it from the study folder with:
```
printf 'protocol_sha256 %s\nfreeze_sha256 %s\npre_run_review %s PASS\n' \
  a649691170e43c712c8e383475af69457598b1b91a0553695c6694e0993a71bd \
  fae62f8842bebc68baee8927051bcceb89fb75bef30ac7a3715df7fb7ee53e92 \
  "$(git log -1 --format=%H -- reviews/DELTA_CHECK.md)" > GO_FGC
```

Then follow section 10 from step 1: run the dry gate check, commit the GO alone, and claim.
