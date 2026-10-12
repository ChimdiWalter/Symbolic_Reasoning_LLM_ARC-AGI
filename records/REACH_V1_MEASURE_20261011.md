# Real-task reach v1: measurement result (2026-10-11)

DEVELOPMENT, run once on the 60 training-development tasks
(`docs/CORA_REAL_TASK_REACH_DEV_v1.md` sections 4.1 and 5.1). No target was
read; leave-one-out scored held-out demonstrations only. Nothing here is a
causal witness or a certified solve.

## Run identity

- Frozen at c8d8e3a: `outputs/reach_v1/measure_manifest.json` sha256
  `2e567bce24d63342b2c38f302f58c36e1f15088bfbcb387a1e3205c0a6497b0d`
  (manifest head 4da98f6), 0 freeze problems before, during (workers) and
  after the run.
- Started 2026-10-11T20:23:11Z from c8d8e3a (coordinator pid 328950, boot
  5c543236, 4 workers); marker `logs/reach_v1/MEASURE_0_DONE`
  2026-10-11T21:34:26Z (71 min wall); exit codes 0 0 0 0; missing []; no
  resume; the boot id never changed.
- Rows `outputs/reach_v1/measure_rows.jsonl` sha256 `821a6556...05bedd`, 60
  unique keys equal to the bundle's, committed 60ddd04 by the checkpointer.
- Load 54.7 to 73.7 on 24 cores (Step B's 20 workers and other jobs); the
  engine's budgets are wall-clock.

## Verification

- `scripts/reach_v1_measure_summary.py`: 0 verification problems
  (`outputs/reach_v1/measure_summary.json` sha256 `2a208155...a6e6f2`).
- Independent terminal verifier `scripts/reach_v1_verify_measure.py`
  (dab575d, dc459f8; written before the outcome was read; run in the
  workers' environment): VERIFIED, 0 problems
  (`logs/reach_v1/verify_measure.json` sha256 `e19b9ffa...2f196c5e`,
  funnel `outputs/reach_v1/measure_funnel.json` sha256 `77fbac13...ae55a1`).
  It re-checked: the manifest against the freeze commit, every frozen file
  and tree, the run's start commit, no resume, the coordinator record, 60
  unique rows, 4 isolation logs (0 refused accesses, no forbidden
  directory), a bundle that holds no test output, empty worker logs, 0
  RUN_ERROR, restoration of every row and every installed run, all three
  constructions re-executed on all 60 tasks (identical), every gate from its
  run records, the fold structure and classes, the controls, the REMOVED
  and MATCHED budgets, the separation legs (the renaming leg re-executed
  with the engine's own detect_grow) and the compute accounting.

## Repair funnel (60 tasks)

| stage | tasks |
|---|---|
| A native baseline failure (census not NATIVE_CERTIFIED; KALONE fails where run) | 54 |
| B usable failure evidence (memorized growth instances) | 31 |
| C machine-generated growth-relation proposal (FC) | 4 |
| D canonical executable extension | 4 |
| E compilation (canonical reload) | 4 |
| F installation into the native engine (run, removed, state restored) | 4 |
| G accepted native program (K + e) | 1 |
| H winning program uses the extension | 1 |
| I exact demonstration replay | 1 |
| J deterministic (second K + e run identical) | 4 |
| K full adaptive leave-one-out | 0 |
| L bounded semantic separation | 4 |
| M growth support contract | 1 |
| N activation | 0 |

Path classes: NO_PROPOSAL 56, ENGINE_REJECTION 3, LOO_FAILURE 1,
ACTIVATED 0. Against the preserved baseline (ce123e8): installed 0 -> 4,
accepted with an extension 0 -> 1, activated 0 -> 0. J counts the
determinism gate, which also holds for repeated rejections. L is reported
for every installed extension, but it only means something where K + e
succeeds (one task).

## The four proposed repairs

| task | census | extension (variant, instances, demos) | KALONE | K + e | adaptive LOO | class |
|---|---|---|---|---|---|---|
| k017955a77fc5 | DE_LOO STRUCT | window_fill k=3 (S2, 2, demos 0-1) | hard cap 450 s | hard cap 450 s, twice | 0/3: NO_PROPOSAL 2, LOO_FAILURE 1 (same e, cap) | ENGINE_REJECTION |
| k5991e227189e | DE_LOO STRUCT | connect (S6, 4, demos 0-3) | rejected at loo | hard cap 450 s, twice | 0/4: LOO_FAILURE 3 (same e; 2 at the cap), NO_PROPOSAL 1 | ENGINE_REJECTION |
| k5a49896251a2 | DE_LOO STRUCT | connect (S6, 3, demos 0-2) | rejected at loo | train-exact, rejected by the engine's own leave-one-out | 0/3: NO_PROPOSAL 2, LOO_FAILURE 1 (same e) | ENGINE_REJECTION |
| kf892487f1049 | A_REPRESENTATION matching | bbox_fill (S6, 6, demos 0-3) | rejected at matching | ACCEPTED in 22 s; uses e; replay, attribution, prediction, determinism, unanimity (pool 1), support (the one e rule witnessed in all 4 demonstrations; e adds 22 cells on the test input) | 0/4: same e in 3 folds, the engine accepts none of the 3-demonstration subsets; fold 1 selects window_fill first (grammar order) | LOO_FAILURE |

kf892487f1049 holds invariant conditions 1 to 4 on development data: K
fails; a machine-generated extension from the memorized-instance failure
trace; typed, canonical, installed and executed; bounded separation (not a
renaming: the engine's own detect_grow falls back to `pattern` on all 6
instances; not a cache: a 119-byte body against 83 memorized cells; not a
bounded composition: KALONE and MATCHED_COMPUTE (90 s) accept nothing,
REMOVED equal to KALONE). It fails condition 5. No task holds conditions 1
to 5 together.

## Leave-one-out

14 folds: SUCCESS 0, LOO_FAILURE 9, NO_PROPOSAL 5. Of the 9 failures, 8
rebuilt exactly the full task's extension and 1 selected another; 3 of the
9 hit the 450 s hard cap. The NO_PROPOSAL folds rebuilt evidence that no
single setting explains across two demonstrations. The fold records keep
acceptance, use and held-out exactness but not the engine's failure stage
(a recorded limitation), so where the engine stops inside a fold is not
established by this run.

## Controls and ablation (descriptive)

- DEMONSTRATION_ONLY: proposes on 1 task (kcf73bcf87919, band, not an FC
  task; K + e rejects it); on the other 59 tasks an input cell changes (36)
  or no setting explains the demonstrations (23). On the 4 FC tasks it
  proposes nothing.
- SHUFFLED_FAILURE: installed on 4 tasks (donors are the FC tasks); one
  acceptance, k553a7e98f13d, which is NATIVE_CERTIFIED and whose winner does
  not use e (K's own solution); never accepted with e used. On
  k5991e227189e the donor's extension is its own (connect).
- EXTENSION_REMOVED and MATCHED_COMPUTE: accept nothing on the 4 FC tasks;
  REMOVED equals KALONE on all 4 (acceptance, program, predictions).

## Readiness (pilot v1 section 12, unchanged)

Isolation clean; no RUN_ERROR; native readiness complete (census 60 of 60,
0 run errors, marker); loop operable: 4 tasks at the compiled-and-installed
stage. READY = PASS. Separately: accepted programs 1, adaptive
leave-one-out successes 0, activations a = 0, conditions 1 to 5 together 0.
By the unchanged N rule, a = 0 gives N = 120 for the successor pilot.

## Exact blockers (development)

1. Coverage: 4 proposals in 60 tasks; 27 tasks have usable evidence but no
   single setting reproduces every memorized instance of one variant; 29
   tasks memorize nothing.
2. Engine acceptance: 3 of 4 installed extensions are not accepted (2 at
   the 450 s hard cap, 1 train-exact but rejected by the engine's own
   leave-one-out).
3. Adaptive leave-one-out (binding): 0 of 4. On the one accepted task the
   rebuilt extension is the same in 3 of 4 folds, yet the engine accepts on
   no 3-demonstration subset.

## Compute

Task time 14,637 s (the 4 FC tasks 12,256 s). By arm: KALONE 2,630 s, K + e
1,343 s, repeat 1,342 s, leave-one-out extraction 1,132 s and engine
3,197 s, REMOVED 1,450 s, MATCHED 1,900 s, DEMO_ONLY 291 s, SHUFFLED
1,349 s. Wall 71 min with 4 workers.

## Claim ceiling

Engineering evidence on development tasks only. The growth mechanism
reaches the installed stage on real tasks (4 of 60, against 0 of 60
before), and on one real task it produced, from the engine's own failure,
an extension the unchanged engine accepted, used and needed within the
tested budgets. That extension did not survive the adaptive leave-one-out,
so no development candidate meets conditions 1 to 5. Conditions 6 to 8 are
untested; the sealed 185 of 1,000 is unchanged; no development activation
is a certified solve. The grammar is human-designed generic machinery.

## Next

READY passes, so (directive CASE A) the development result is recorded
here and the versioned successor, `docs/CORA_REAL_ARC_GROWTH_PILOT_v2.md`,
is frozen with N = 120 and NOT run.
