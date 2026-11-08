# Failure-guided choice test, revision 2: independent pre-run review

Reviewer: an independent review session that did not build this test. Written 8 November 2026, before any GO.

What I reviewed:
- `PROTOCOL.md`, sha256 04392be15ce8086fcee564b34278698758f3e2483991af5db5f934e6ebff566b;
- `FREEZE.json`, sha256 beab330df3dcdbe38d20dd989147acdcdee3ccfc359d674b6430c4b70ec18583;
- the freeze commit a94ed58c. No later commit touches the study folder, and its 298 tracked files equal a94ed58c;
- `PROGRESS.md`, `runs/dev/`, `config/`, every module of `fgc/`, `launch/`, `checks/`, the development kernels'
  packages and fetch records, and revision 1's `RESULT.md` and pre-run review.

What I did not do: write a GO, generate or open a held task, push or query anything on Kaggle, or score. Every rerun
below used a scratch copy extracted from a94ed58c, plus the six git-ignored dependencies copied byte for byte, and
touched source data only.

Terms:
- **Arms**: A base only, B base plus extra search, C the static full bank, D a random order, E the shuffled
  diagnosis, F the fixed evidence-based router, G the learned router, H the oracle router.
- **Calls**: primitive executions, the study's only cost unit.
- **K_S and K_V**: the caps of deeper search and of the view search inside the bank (2,500,000 and 2,250,000 calls).
- **T\***: the binding budget, 3,000,000 calls.

## Verdict: PASS-WITH-NOTES

No finding requires a change to a frozen byte. Four procedural conditions are part of this verdict; section 8 gives
the exact steps.
1. **The GO file binds this review.** It has a third line naming this review's commit, and it is committed before
   the claim. Otherwise the held salt could have been computed at freeze time, and the gate never checks that the
   GO is committed.
2. **New Kaggle kernel names.** Revision 1's held measurement kernels already hold the names TEST_1, TEST_2 and TEST_3.
3. **New detached job names.** `outputs/detached/fgc_seal` and `fgc_score` are revision 1's records.
4. **Checks between stages.**
   - Before each push, check every kernel package against `FREEZE.json`.
   - After the merge, check the held set's isolation and record its view-task count.
   - Before sealing, check the measured task ids against the held set.
   - Commit before each next stage.

The GO file I would accept is in section 10.

## 1. The freeze

- **Every digest matches.**
  - `FREEZE.json` lists 96 study files, 41 dependencies and 1 data file.
  - All 96 study files and the 35 tracked dependencies match both their blobs in a94ed58c and the working tree.
  - Six dependencies are git-ignored and pinned by digest only, as in revision 1: `out/corpus.json` of A2 (the
    project's arc-dsl program search) and five arc-dsl files. They match the working tree.
  - The data file `<ARC data folder>/arc-agi_training_challenges.json` matches.
- **The lists are complete.**
  - The freeze script's own enumeration (`fgc/freeze.py`) gives exactly these 96 files and 41 dependencies today.
  - Every path a generation or measurement kernel packs (`fgc/kaggle_build.py`) is covered by the freeze.
- **The frozen code made the frozen source measurements.**
  - The four source-measurement kernels (R2S_1 to R2S_4) packed `fgc/measure.py`, `fgc/views.py`, `fgc/common.py`
    and every dependency they carry at their frozen digests.
  - Only `config/STUDY_CONFIG.json` differed, and the measurement code does not read it. The difference is the held
    quotas: 4 rising to 6 per missing-operation family, and 4 rising to 8 depth tasks per world.
  - The first three kernels carried the 79-task source file. Its 79 tasks are byte-identical in the frozen 85-task
    file.
  - The frozen measurement files equal the fetched outputs, and each archive matches the digest its notebook printed.
- **Measurement is deterministic across kernels.** Base, search and construction records equal revision 1's on all 71
  shared source tasks.
- **Nothing held exists.**
  - There is no `GO_FGC`, `runs/RUN_CLAIM.json`, `runs/test/`, `runs/test_parts/` or held kernel folder, in the working
    tree or anywhere in the repository's history (all branches).
  - The held generator's smoke test (`outputs/detached/fgc2_gen_smoke`) used:
    - the pilot pool, which shares none of its 100 ids with the main pool;
    - the salt "smoke-salt", reduced quotas and one world.

    It wrote nothing.
- **The salt comes from the GO's digest only.**
  - `gate.claim_and_salt()` and `kaggle_build.py --generate-test` both form "fgc2-test-" plus the first 16 hex digits
    of the sha256 of the GO file's bytes.
  - The generator appends the world name and uses no other source of randomness.
  - Gap: a GO of exactly the two required lines has a digest anyone could compute from the frozen hashes. Its salt
    was therefore knowable at freeze time. Condition 1 closes this.
- **Development reproduces exactly.**
  - `fgc.develop constants` rebuilds `runs/dev/CONSTANTS_EVIDENCE.json` byte for byte:
    - K_S 2,500,000, K_V 2,250,000 and T\* 3,000,000;
    - static order construction, search, view;
    - the best fixed order 42 against the oracle 52 at T\*.
  - Retraining G gives bit-identical weights (25, 20 and 30 positives).
  - The development seal and score rebuild `runs/dev/source/SEALED_PREDICTIONS.json` (71e8d584...) and
    `ANALYSIS.json` byte for byte. At T\*: C 42, F 52, G 49, H 52, E 38, D 31, B 27 and A 0 of 85.

## 2. Held isolation

- **The families are disjoint.**
  - Missing operation: held compress, trim, cmirror, rot270, hupscale and switch, against source upscale, downscale,
    dmirror, rot90 and vupscale.
  - Depth: every held program has a crop outermost. The 27 source programs have cmirror, dmirror, hmirror, rot180,
    rot270, rot90 or vmirror outermost, never a crop.
  - Wrong view: held operations outbox, corners and inbox, against source box, backdrop and delta. The four
    alternative views are shared by design.
- **The sources are disjoint.**
  - `fgc/generate.py` `test_world_rows` excludes the sources of:
    - every world-copy task (176);
    - revision 1's source set (71);
    - revision 1's held set (50);
    - this revision's source set (85, which contains revision 1's).
  - That removes 263 of the main pool's 535 ids. The other 272 are split between the worlds by sha256 of the id
    modulo 3: 92, 108 and 72.
  - Within a world, the builder marks each source as used. `test_merge` refuses a task id or a source used twice.
- **No code refuses a source family.**
  - Disjointness rests on the frozen configuration (`test_families`, `view_test_ops`) and the hard-coded crop class
    for depth.
  - The freeze binds both and the gate re-checks them. That is sufficient. Condition 4 confirms it on the generated
    set.
- **Kaggle-side generation cannot run before the claim.**
  - `--generate-test` refuses without `runs/RUN_CLAIM.json`, when the claim names other GO bytes, and when
    `runs/test/` exists. I tested all three.
  - The kernel is private with internet off.
  - Its output holds the held labels; they stay in the private kernel and in `evaluator_only/`.
  - Measurement kernels pack only system files: `TEST_SYSTEM.json` (demonstrations and query inputs), the world
    copies' tasks, removed sets and controller records, and code.
  - The seal reads only measurement files and `config/ROUTERS.json`.
  - Gap: the build does not re-check the frozen digests after the claim. Condition 4 adds that check.
- **Correction for the write-up: four source grids are not fresh.**
  - Section 3 says the 14 source view tasks come "from sources used nowhere else". Four reuse input grids of revision
    1's held tasks: t6c9e5e1f, t8f2f6420, tad7c9c94 and tc0796ca0.
  - This happened because the source build deliberately left revision 1's held set out of its exclusions
    (`used_sources(include_r1_test=False)`).
  - It does not affect this revision's held set, which excludes those grids.

## 3. The contract

- **One bank, one function, the current task only.** `fgc/pipeline.py` seal calls `contract.run_arm` once per arm,
  task and budget, always on `ms[t]`. `contract.execute` is the only code that runs an intervention.
- **Arms differ only in order.**
  - A runs none.
  - B runs search only, with every remaining call (a named exception).
  - C runs the frozen static order.
  - D runs a sha256 permutation.
  - E runs F's rule on the donor's descriptor.
  - F runs the frozen rule on the task's own descriptor.
  - G runs the frozen regressions.
- **E, F and G pay for the probe, and E pays for the current task's probe.**
  - The charge is `feats[t]["descriptor_calls"]` for every arm in `{"E", "F", "G"}`.
  - The donor enters only as `feats[donor[t]]`, in E's order.
  - F's rule reads only `same_size`, so F pays for a probe it does not use: 10 to 309 calls per source task, median
    15. That is conservative for the primary.
  - A weakness in the checks, not in the contract: the property "descriptor_charged_alike" compares a value with
    itself. Only the literal check of the line `reads = {"E", "F", "G"}` tests the charge. I read the charging line
    directly.
- **The view search really has no cheap applicability check, in code or in data.**
  - `fgc/views.py` runs A2's search with the four views as leaves, wants one fit, and makes no pre-check.
  - `contract.execute` charges a search-like intervention that does not fit within its cap the whole cap,
    min(K_V, remaining).
  - On the source set, the view search fit no missing-operation task: on all 44 it stopped at its 4,000,000-call cap.
    It did the same on the 14 depth tasks it did not solve.
  - Construction stopped after 897 to 918 calls on every task it did not solve.
  - No source measurement stopped on CPU time, and none exhausted its search fragment early.
- **The oracle exists only at scoring.** H is absent from the seal. `score()` replays it from the generator's cause,
  and it pays no probe.
- **The contract checks pass.**
  - Rerun on the scratch copy, the output is byte-identical to `checks/CONTRACT_CHECKS.json`: 12 literal replays and
    12 properties, all pass.
  - I recomputed all 12 replays by hand.
  - Not covered: the branch where a search exhausts its fragment early. It never occurs in the source data.
  - Every committed prediction carries exactly two attempts.

## 4. Primary, ladder, disclosure and power

- **Pre-registered and implemented as written.**
  - The primary is F against C at T\*. `pipeline.score` implements it as an exact two-sided McNemar test and a
    family-clustered percentile bootstrap (10,000 draws, seed 7). Success needs p < 0.05 and the lower end above 0.
  - Secondaries: G against C, F against E and F against D, Holm-adjusted.
  - The budget curve runs at 0.25 to 4 times T\*.
  - `pipeline.decide` implements the ladder in the protocol's order. The efficiency threshold is 150,000 calls (5% of
    T\*).
- **F's origin is disclosed.** Sections 2, 5 and 9 say:
  - F was hand-written on the source set;
  - richer probe rules were tried there and did no better;
  - the source figure is optimistic.
- **The held test is a real test, but narrow, and the write-up must say how.**
  - F differs from C only on tasks whose demonstrations all keep their size. There it runs the view search before
    deeper search.
  - Every held view task keeps its size by construction, because the generator paints objects onto the input grid.
  - So the primary measures two things:
    - whether held view tasks need between about 350,000 calls (what C has left after construction and a failed
      2,500,000-call search) and K_V;
    - whether moving the view search earlier costs anything on held missing-operation or depth tasks that keep their
      size and that construction misses. These are switch, cmirror or rot270 on square grids, and rarely a crop that
      removes nothing.
  - The view operations are new to every held test.
  - The missing-operation and depth families are revision 1's held families. They were scored before this revision
    was designed: construction solved 14 of 32 held missing-operation tasks, and search after construction solved
    none. Only the sources are fresh.
  - Section 2 says these families are unchanged. The write-up should add that their held behaviour was already known.
- **The power claim of 0.996 reproduces, but only if every view slot fills.**
  - I reproduced 996 of 1,000 exactly (`fgc.develop power`, seed 3).
  - It is an upper bound for the reasons section 9 gives, and for two more:
    - it assumes every quota slot is filled;
    - it assumes held view tasks cost what source view tasks cost, although held inputs may be 20 x 20 rather than
      16 x 16.
  - The fill rate matters most, because all 10 discordant source tasks are view tasks. The same simulation with fewer
    held view tasks (one per family) gives:

    | held view tasks | 18 (the plan) | 9 | 7 | 6 | 4 |
    |---|---|---|---|---|---|
    | primary succeeds | 0.996 | 0.902 | 0.552 | 0.244 | 0.000 |

  - The exact test needs at least 6 discordant tasks, all for F: 6 against 0 gives p = 0.031, and 5 against 0 gives
    0.0625. F can gain only where it moves the view search earlier. So a held set with 5 or fewer view tasks cannot,
    in practice, show a selection advantage.
  - The fill is uncertain:
    - The source build filled 14 of its 27 view slots.
    - The held build makes view tasks last in each world, from the 72 to 108 sources that remain.
    - Held view tasks may need more than K_V (the generator accepts up to 4,000,000 calls). Every arm fails those,
      H included.
- **The quotas match the stated mix.**
  - At most 36, 24 and 18 tasks (46%, 31%, 23%), against the source's 44, 27 and 14 (52%, 32%, 16%).
  - They were raised during development, after the source results and before any held task existed. Raising them
    lowers the view share, which makes the test harder for F, not easier.

## 5. The gate

I tested 25 cases on the scratch copy. All behaved as expected.
- **It refuses:**
  - with no GO;
  - with a wrong protocol or freeze digest, or the two lines swapped;
  - with a stale `FREEZE.json`;
  - when a frozen file was edited (K_V), a dependency was edited (`cas/generate.py`), or a dependency is missing
    (revision 1's held labels);
  - when the data file changed;
  - on a second claim, or a claim while `runs/test/` exists;
  - at measure, when the claim names other GO bytes or the held manifest is missing;
  - at score, without sealed predictions or with a digest mismatch;
  - at any stage, once a later line of the GO changes.
- **It passes:**
  - generate with a valid GO, writing the claim exclusively;
  - measure, seal and score with their prerequisites.
- **Two gaps, both closed by procedure:**
  - It never checks that `GO_FGC` is committed; it only reads the file. Condition 1 covers this.
  - Only the claim is one-use. Measure, seal and score all pass a second time.
    - Every later stage is deterministic in calls, so a repeat on the same inputs gives the same bytes.
    - `fgc/fetch.py` refuses to overwrite a fetched destination.
    - A repeat on changed inputs would show only in git history. Hence condition 4: commit before each next stage,
      seal once and score once.

## 6. Revision 1's held labels

- **Used for one thing only.**
  - `used_sources()` reads each task's "source" field from revision 1's `runs/test/evaluator_only/TEST_EVAL.json`, so
    that no held task reuses an input grid of revision 1's held set.
  - The file is the one revision 1 scored: its sha256, a59d8f5f..., equals the `eval_sha256` in revision 1's manifest.
  - It is frozen as a dependency and packed only into the private generation kernel.
- **No leakage into the held set.**
  - No other code in revision 2 reads the file, and development deliberately left it out.
  - The four reused grids in section 2 go the other way: revision 1's held grids appear in revision 2's source set.
    This revision's held set excludes them.

## 7. Detached execution and Kaggle privacy

- **The scripts are sound.**
  - `launch/run_job.sh` and the Kaggle scripts are hard-wired to this folder.
  - `run_job.sh` takes a CPU slot at nice 19, with PYTHONHASHSEED=0 and PYTHONPATH=.
  - `scripts/run_detached.sh` refuses a name that is still running, but it overwrites a finished record of the same
    name.
  - Every `kernel-metadata.json` says private, no GPU, internet off.
  - `push_when_free.sh` pushes only the folder's own metadata. It retries only on Kaggle's session-limit refusal.
- **Two names collide with revision 1 (conditions 2 and 3).**
  - `kaggle_build.py` names a kernel `chimdiwalter/cora-failure-choice-<name>`.
  - TEST_1, TEST_2 and TEST_3 are revision 1's held measurement kernels. Pushing under those names would add versions
    to revision 1's kernels.
  - A status read before the new version is queued could fetch revision 1's output. Its own printed digest would then
    pass the fetch check.
  - Separately, `fgc_seal` and `fgc_score` name revision 1's detached records.

## 8. Conditions: the exact steps

Run every command from `experiments/failure_choice_r2_20261108/`, with plain explicit-path commits and no trailers.
Append each step's outcome to `PROGRESS.md`.

1. **The GO.**
   - Write `GO_FGC` exactly as in section 10.
   - `python3 -I fgc/gate.py measure` is a dry check. It must fail with exactly "no RUN_CLAIM.json; no held test
     manifest" and nothing else.
   - `git add GO_FGC && git commit -m "GO for the failure-guided choice test, revision 2" -- GO_FGC`.
2. **The claim.**
   - `python3 -I fgc/gate.py generate` must print "ok generate".
   - Commit `runs/RUN_CLAIM.json`.
3. **The generation kernel, named R2_TEST_GEN.**
   - Build: `python3 -I fgc/kaggle_build.py --generate-test R2_TEST_GEN W1 W2 W3`.
   - Check the salt: `grep -c "fgc2-test-$(sha256sum GO_FGC | cut -c1-16)" runs/kaggle/R2_TEST_GEN/notebook.ipynb`
     must print at least 1.
   - Run the package check below with argument R2_TEST_GEN. It must print "none".
   - Commit `runs/kaggle/R2_TEST_GEN/`, then push:
     `setsid nohup sh launch/push_when_free.sh R2_TEST_GEN < /dev/null > /dev/null 2>&1 &`.
4. **Fetch, merge and the isolation check.**
   - `python3 -I fgc/fetch.py R2_TEST_GEN gen`.
   - Copy `test_W1.json`, `test_W2.json` and `test_W3.json` from `runs/gen/measure/R2_TEST_GEN/` into a new
     `runs/test_parts/`.
   - Merge, as one line:
     ```
     sh ../../scripts/run_detached.sh fgc2_test_merge sh launch/run_job.sh test_merge python3 -m fgc.generate test_merge
     ```
   - Run the isolation check below. It must print 0 reused, 0 duplicates and no family outside the plan.
   - Record the held count by cause, with the view-task count beside the power at that count from section 4.
   - Before any measurement, commit `runs/test/`, `runs/test_parts/`, `runs/gen/measure/R2_TEST_GEN/` and
     `runs/kaggle/FETCH_R2_TEST_GEN.json`.
5. **Measurement, in kernels named R2_TEST_1 to R2_TEST_4.** Never use TEST_1, TEST_2 or TEST_3.
   - Run `python3 -I fgc/gate.py measure` and record its "ok measure" line.
   - Build each kernel, k from 1 to 4, each with its share of the held ids by world:
     `python3 -I fgc/kaggle_build.py R2_TEST_k runs/test/TEST_SYSTEM.json 3 W1:<ids> W2:<ids> W3:<ids>`.
   - Run the package check on each kernel; it must print "none". Commit each kernel's folder before its push.
   - Fetch each output with `python3 -I fgc/fetch.py R2_TEST_k test`.
   - A failed kernel is re-measured under a new name, with the same `archive_sha256`.
   - Run the id check below; it must print "missing 0 extra 0".
   - Commit `runs/test/measure/` and the fetch records before sealing.
6. **Seal once**, as one line, then commit `runs/test/SEALED_PREDICTIONS.json` and `runs/test/SEALED_SHA256`:
   ```
   sh ../../scripts/run_detached.sh fgc2_seal sh launch/run_job.sh seal python3 -m fgc.pipeline seal runs/test/measure runs/test
   ```
7. **Score once**, as one line, then commit `runs/test/ANALYSIS.json`:
   ```
   sh ../../scripts/run_detached.sh fgc2_score sh launch/run_job.sh score python3 -m fgc.pipeline score runs/test runs/test/evaluator_only/TEST_EVAL.json runs/test/measure runs/test
   ```

The package check takes the kernel name as its argument and prints the packed files that do not match the freeze. After
the merge, the held system file must match the manifest:
```
python3 -I -c "
import json, os, sys
S = 'experiments/failure_choice_r2_20261108/'
fz = json.load(open('FREEZE.json'))
want = {S + k: v for k, v in fz['files_sha256'].items()}
want.update(fz['dependencies_sha256'])
want['data_arc/arc-agi_training_challenges.json'] = list(fz['data_sha256'].values())[0]
if os.path.exists('runs/test/TEST_MANIFEST.json'):
    want[S + 'runs/test/TEST_SYSTEM.json'] = json.load(open('runs/test/TEST_MANIFEST.json'))['system_sha256']
pk = json.load(open('runs/kaggle/' + sys.argv[1] + '/PACKAGE.json'))
print(sys.argv[1], len(pk['files_sha256']), 'files; not matching:', [p for p, h in pk['files_sha256'].items() if want.get(p) != h] or 'none')
" R2_TEST_GEN
```

The isolation check reads only each held task's source and family, and prints counts:
```
python3 -I -c "
import json
L = lambda p: json.load(open(p))
W = ('W1', 'W2', 'W3')
ex = set()
for w in W:
    ex |= {t['source'] for t in L(f'runs/worlds/{w}/evaluator_only/TASKS_EVAL.json').values()}
for p in ('runs/source/evaluator_only/SOURCE_EVAL_R1.json', 'runs/source/evaluator_only/SOURCE_EVAL.json',
          '../failure_choice_20261108/runs/test/evaluator_only/TEST_EVAL.json'):
    ex |= {t['source'] for t in L(p).values()}
cfg = L('config/STUDY_CONFIG.json')
plan = ({f'{w}:{x}' for w, xs in cfg['test_families'].items() for x in xs} | {f'{w}:depth-crop' for w in W}
        | {f'{w}:view-{x}' for w in W for x in cfg['view_test_ops']})
ev = L('runs/test/evaluator_only/TEST_EVAL.json')
src = [t['source'] for t in ev.values()]
print('held', len(ev), '| reused', len(set(src) & ex), '| duplicates', len(src) - len(set(src)),
      '| outside the plan', sorted({t['family'] for t in ev.values()} - plan))
"
```

The id check runs before the seal and reads system files only:
```
python3 -I -c "
import glob, json
ids = set(json.load(open('runs/test/TEST_SYSTEM.json')))
m = set()
for p in glob.glob('runs/test/measure/**/*.json', recursive=True):
    d = json.load(open(p))
    if isinstance(d, dict) and all(isinstance(v, dict) and 'construct' in v for v in d.values()):
        m |= set(d)
print('measured', len(m), 'held', len(ids), 'missing', len(ids - m), 'extra', len(m - ids))
"
```

## 9. Notes for the write-up (not blocking)

1. **Say how narrow the test is.** F's evidence is a size check that the generated view cause satisfies by
   construction. Report it that way, beside the "controlled generated tasks" label.
2. **Say what was known.** The held missing-operation and depth families are revision 1's, and their held behaviour
   was known. Only the view operations are new to a held test.
3. **Correct the source-set claim.** Replace "from sources used nowhere else" with the four reused grids (section 2).
4. **Report the realized counts.** Give the held count by cause and the power at the realized view count. With
   fewer than about 9 view tasks, a result short of success is underpowered, not evidence against selection. Report
   how many held view tasks need more than K_V.
5. **An option, decided before the GO only.** If the coordinator wants a likely decisive test, it can raise the view
   quota or the view tries and refreeze. The cost is a cause mix further from the source's, and a review of the diff.
   As frozen, the run is valid.
6. **Generation depends slightly on the machine.** The construction test's builder caps its base-grammar and
   reference searches at 20 CPU-seconds per 150,000 calls. This matters only if generation is repeated after a failure; any such
   repeat should be compared task by task.

## 10. The GO file I would accept

`GO_FGC` in the study folder must be exactly the three lines below, and nothing else:
- ASCII text;
- each line ends with one LF, including the last;
- one space between fields;
- no trailing spaces.

```
protocol_sha256 04392be15ce8086fcee564b34278698758f3e2483991af5db5f934e6ebff566b
freeze_sha256 beab330df3dcdbe38d20dd989147acdcdee3ccfc359d674b6430c4b70ec18583
pre_run_review <the full 40-hex commit that last changed reviews/PRE_RUN_REVIEW.md> PASS-WITH-NOTES
```

The third line names the reviewer's final commit of this file. Do not name the first commit that contains it: the
repository's autosave job swept an unfinished draft of this file into commit 2391db0c, 38 seconds before the
reviewer's own commit.

Write it with:
```
printf 'protocol_sha256 %s\nfreeze_sha256 %s\npre_run_review %s PASS-WITH-NOTES\n' \
  04392be15ce8086fcee564b34278698758f3e2483991af5db5f934e6ebff566b \
  beab330df3dcdbe38d20dd989147acdcdee3ccfc359d674b6430c4b70ec18583 \
  "$(git log -1 --format=%H -- reviews/PRE_RUN_REVIEW.md)" > GO_FGC
```

Why this format:
- **The gate checks only the first two lines.**
- **The third line makes the salt unknowable before this review existed.** Every byte is fixed, so the coordinator has
  no free choice that could change the salt.
- **Write it once, commit it before the claim, and never edit it.** Its exact bytes set the held salt, and every later
  stage requires the claim to name the same bytes.
