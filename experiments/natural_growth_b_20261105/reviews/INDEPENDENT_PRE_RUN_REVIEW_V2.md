# Independent pre-run review of study B, freeze version 2 (amendment 1)

Review commissioned by the coordinator, 6 Nov 2026. Object reviewed: commit 9ed05245 of
`experiments/natural_growth_b_20261105/` (the library-transfer test, "study B"). Line numbers cite that commit.
The reviewer did not design the study. No held task, held test output or ARC-AGI-2 solution file was opened; no GO
was written; nothing was run on a held half; every check ran in a scratch copy of the committed tree.

**Verdict: PASS WITH FIXES.** The six blocking findings of the companion study's review (note 0472) are corrected in
the committed code, and each correction is verified below with the code and with the admission tests and package
check re-run by this reviewer (section 2; the re-run results are in section 10). Version 2 cannot, however, be the
object of a GO that names arm 5 against arm 4b: its object-growth slot is still empty and its own gate refuses that
primary (finding 1). Since the builder has reported promoted operations, the pre-registered rule makes arm 5 vs
arm 4b the primary, so a dated amendment 2 (slot, contract, frozen registries, a dry run of the object arms, a new
freeze and its review) is a precondition of any GO. Findings 2 and 3 should be fixed in that amendment; findings 4
to 7 are small and may be fixed with it.

Labels used below. G0 is the starting language (A2's whole arc-dsl grammar; A2 is the project's bottom-up program
search). The arms are: arm 1 G0 alone; arm 2 "lib", G0 plus the benchmark's promoted library; arm 3 "shuf", G0 plus
a shuffled library; arm 4a "static_lib" and arm 4b "static_obj", matched static search at the library's or the
object arm's CPU allowance; arm 5 "obj", G0 plus the object-level growth registry; arm 6 "obj_shuf", the same with
shuffled holes. "Source half" and "held half" are study A's split of each benchmark. The "slot" is the
`object_growth` entry of FREEZE.json that must carry the builder's code digests before arm 5 can be a primary.

## 1. Hashes and freeze integrity (verified)

| check | result |
|---|---|
| `PROTOCOL_AMENDMENT_1.md`, live and at commit 9ed05245 | 3004c5d614a68f58f0b694ae88d1fae57e69b7fcc4eacf811d67aa0a290da603 (as stated) |
| `FREEZE.json` (version 2), live and at the commit | 37c36cb032a29369dd944c80a097d0d15112d360258f7a7a3d54bde0a0493828 (as stated); `version` 2; `amendments_sha256` names the amendment's digest |
| `FREEZE_V1.json` | 2e46511e07757ab18086e6654e153cdbbd8059e1794bac1f5d7beec34f55645c, byte-identical to `FREEZE.json` at the first-freeze commits 050b26ce and 819eaee8 |
| `PROTOCOL.md` | 7602387708c3ac3487fa96fde50c25c6b6f1d60fbc193cefc0fe2b9acda1e1ac, unchanged since the first freeze, as the amendment says |
| working tree | no uncommitted change under the study folder; no `runs/GO`; `runs/` empty |
| 86 repository-path entries of `files_sha256` and `arc_agi_2_sha256` | 78 equal to the committed blobs; 8 are not tracked in git (the ARC-AGI-2 challenges and solutions, A2's `out/corpus.json`, the five arc-dsl files) and are covered only by the gate's digest check at run time (the challenges file equals its frozen digest; the solutions file was not hashed by this reviewer) |
| `data_sha256` (six benchmark input files, demonstrations and test inputs only) | all six equal |
| `scorer_only_sha256` (three held-plus-source solution files) | not hashed by this reviewer (never opened); `ngb/score.py` lines 26 to 35 verify them before any use |

## 2. The six corrections, each verified

Evidence: the code at the commit; `checks/ADMISSION_TESTS.json` (frozen, all six tests `ok`); the reviewer's own
re-run of the admission tests and of the package check in a scratch copy (section 10).

**Correction 1, the gate and the empty slot.** `ngb/gate.py` line 82 runs the freeze check first, line 83 refuses
when the GO's third line is `arm5_vs_arm4` and `object_slot_filled` (lines 54 to 58) is false; the slot counts as
filled only when `code_sha256` and `files_sha256` are non-empty and the configuration names `module`, `function`
and `cost`. In the current freeze the slot is null (`FREEZE.json` lines 133 to 138) and the configuration's contract
is null (`config/STUDY_CONFIG.json` line 17). Admission test: a GO naming arm 5 refused, arm 2 passed, a wrong
freeze digest refused. Verified.

**Correction 2, the package.** `ngb/kaggle_build.py` lines 41 to 46 derive the required set from the freeze minus
the `athe_only` list (which `ngb/freeze.py` lines 31 to 33 and 68 to 69 make explicit); `check` (lines 116 to 142)
verifies presence, digest and archive membership, and `build` refuses a kernel unless the check passes (line 151).
`checks/PACKAGE_CHECK.json`: 63 required files, 69 archive members, no problem. The ten files the review named
(`ngb/run.py`, each benchmark's `candidates.json`, `discovery_summary.json`, `insample.json`) are in the required
set. Nothing kernel-side imports study A's `grow.py` or `held.py` (the two Athe-only study A modules). Verified;
the reviewer's own package-mode import and gate smoke test is in section 10.

**Correction 3, completeness before solutions.** `ngb/report.py`: `verify_run` (lines 38 to 57) checks every
manifest digest, refuses unlisted row files and requires `STAGES.json` to carry this GO's digest, the same primary
and status complete; `collect` (lines 60 to 95) requires exactly one row per held task and arm with matching
bench, arm, GO digest, frozen library digest and one registry digest per arm; any problem ends the run at line 175
with exit code 2 before the first solution file is opened at line 181. Admission tests: a duplicate row is INVALID
and a missing row INCOMPLETE; a run with a missing row exits 2 with the solution loader never called. Verified.

**Correction 4, Holm.** `ngb/report.py` lines 240 to 243 compute Holm over the secondary family first and apply the
pre-registered rule to the adjusted p; the primary keeps its raw p (line 208); descriptive comparisons carry no
decision (lines 254 to 257). `ngrow/analysis.py` lines 79 to 86 is the standard step-down. Admission test: six
discordant tasks give raw p 0.03125, Holm p 0.1875 over six tests, decision "inconclusive". Verified, with one
reservation (finding 2): tests that cannot be computed are dropped from the family rather than kept as ties.

**Correction 5, source outputs without materialising held values.** `ngb/score.py`: the file is read as text and
its digest checked against the freeze (lines 26 to 35); `_decode_ids` (lines 38 to 52) finds each requested id's
key, which must occur exactly once, and decodes only that value with `raw_decode`; any held id requires the GO
before `json.loads` of the whole text (lines 55 to 63); the ARC-AGI-2 solutions require the GO and a digest check
(lines 66 to 72). Admission test: only the two requested offsets were decoded, the held entry never, a duplicated
key refused. Verified. The boundary is the decoder, as the amendment states; the file's bytes are in memory as
text.

**Correction 6, time-outs and duplicates.** `ngb/held.py` `child_search` (lines 129 to 149) turns a time-out, a
failed child, an unreadable result or any exception into a durable failure row with the detail; `run` (lines 197 to
214) wraps every task so an exception yields an `arm_error` row; `rows_by_task` (lines 59 to 65) raises on a
duplicate and the report marks a duplicate INVALID; every row carries bench, family, task, arm, GO digest, registry
digest, library digests, G0 digest and CPU scale (lines 194 to 196). `ngb/phase2.py` keeps every attempt of a stage
(lines 96 to 109) and refuses a `STAGES.json` of another GO (line 67). Admission test: a time-out and a failed child
give `child_timeout` and `child_failed` rows with no answer. Verified. `ngb/arc2.py` has the same structure (lines
86 to 105).

## 3. The arms and the pre-registered primary rule

- The seven held rows implement the six arms (arm 4 split into 4a and 4b), `ngb/held.py` lines 39 to 40 and 197 to
  212; the five ARC-AGI-2 arms, `ngb/arc2.py`. An empty or unavailable registry copies G0's rows and marks them
  (`held.py` lines 181 to 184 and 205 to 208); arm 4b runs only when object growth is available (`phase2.py` lines
  89 to 92). Matched allowances follow the protocol's formula (`held.py` lines 107 to 121: Athe-measured source cost
  times the kernel's factor, plus the arm's held base-search CPU measured on the kernel, per held task).
- The primary rule (PROTOCOL.md lines 152 to 157) is read from the GO's third line (`gate.py` lines 61 to 73);
  `report.py` line 205 applies it with no discretion and refuses an arm-5 primary without arm 4b rows (line 207).

**Finding 1 (high, structural): version 2 cannot carry the GO the rule now requires.** The coordinator states that
the builder reported promoted operations, so the primary is arm 5 vs arm 4b; the gate refuses that primary while the
slot is empty (finding verified in section 2, correction 1). The arm-5, arm-6 and arm-4b code paths have never run
with a real registry: `checks/dry_run_v2` ran them as G0 copies, and `static_obj` was not run (`dry_run.py` lines
43 to 49). Fix, as a dated amendment 2 before any GO: (a) fill the slot with `run.py freeze <builder folder>`
(`ngb/freeze.py` lines 40 to 48) and the contract in the configuration; (b) freeze the two registries per benchmark
(their operations' programs and the digest `registry_digest` computes, `held.py` lines 83 to 84) so that the report
can check each row's `registry_sha256` against a frozen value (`report.py` lines 92 to 94 only check that an arm's
rows agree with one another); (c) check the contract against `ops.py` lines 112 to 123, which accept only integer
parameters in -2 to 10 and only one parameter; (d) re-run the dry run with the real registries so that arms 5, 6,
4b and the ARC-AGI-2 object arms execute end to end; (e) re-freeze and re-review.

## 4. Custody of the libraries and registries (verified, with the gap above)

The three libraries and the shuffled libraries are frozen (`FREEZE.json` lines 85 to 97); `bind_library`
(`held.py` lines 69 to 80) refuses a run unless the files given to it carry the frozen digests, and `phase2.py`
lines 58 to 59 binds them at the start; every row records the digests and the report rejects rows whose library
digest differs from the frozen one (`report.py` lines 81 to 84). The library contents match the protocol's table:
ConceptARC 5 operations, Mini-ARC 0, 1D-ARC 3 (the flip operation from 22 source tasks, the recolour operation and
its parametrised form); shuffled libraries ConceptARC 3 of 5 wanted (shortfall 2), 1D-ARC 3 of 3, Mini-ARC 0
(`feasibility/library/shuffled.json`). The object registries have no frozen record yet (finding 1 b).

## 5. The honest expectation and power (read, judged reasonable)

`power/POWER.json` (`ngb/power.py`): per family, the source-half leave-one-source-out and reach counts scaled by
held over source tasks; 300 simulated held tables with Poisson draws; the pre-registered comparison on each. Library
vs G0: "beats" 0.787, "inconclusive" 0.213; library vs matched static: "inconclusive" 0.847, "tie" 0.14, a decision
either way about 0.013; expected discordant tasks about 28 for library over G0 (22 of them the one 1D-ARC flip
family), 5 and 5 either way against matched static; the exact test needs 6 discordant tasks one way. The protocol
states before any held task that the gain, if any, is one homogeneous family and that against matched search the
expected verdict is efficiency, not reach. That is an honest expectation. Two caveats, both already visible in the
text: the estimate is in-sample (leave-one-source-out keeps an operation produced by 22 tasks), and the power
input `experiments/natural_growth_20261105/feasibility/FEASIBILITY.json` (study A's record, `power.py` line 53) is
not in this study's freeze, only its output is.

## 6. The ARC-AGI-2 check is a secondary with its exposure stated (verified)

S6 and S7 are in the Holm family (PROTOCOL.md lines 169 to 170; `report.py` lines 236 to 238). Exposure: the
protocol's section 8, the amendment's section B and the report's own text (`report.py` lines 233 to 235) state the
earlier development use and the phase 1 incident (95 tasks' inputs touched by the first dry run, no solution
opened). The incident record `records/INCIDENT_20261105_DRY_RUN.md` is frozen. This reviewer confirmed, by counts
only, that `checks/dry_run/arc2/*.jsonl` now hold two source stand-in rows each and that the unfrozen `logs/dry.log`
still contains 95 G0 lines for eight-character evaluation ids (finding 7).

## 7. The seed fix (verified in the record; re-run in section 10)

`ngb/ops.py` lines 161 to 185: `SortedTags` gives every production's argument tags a sorted iteration order, and
`G0Builder` applies it to the whole grammar; every search of study B goes through this builder (`held.py` lines
154 and 171, `arc2.py` line 65, `discover.py`, `library.py`). `checks/SEED_CHECK.json`: three probes under hash
seeds 0, 1 and 2 (the children run with `-s -B`, `ignore_environment` 0, witnesses differ); under the sorted builder
every recorded field is identical across seeds; under study A's plain builder the program text and execution
count differ while fits and predictions agree. The stage 1 and 2 records predate the fix; the amendment discloses
this and keeps the libraries as frozen, which is acceptable because phase 2 only reuses them. Remaining seed-free
elements: the bootstrap (`ngrow/analysis.py` line 20, `random.Random(20261105)`), the shuffle order (sha256), the
power simulation (`random.Random(20261105)`).

## 8. Other findings

**Finding 2 (medium): the Holm family shrinks when a test cannot be computed.** `report.py` line 239 drops `None`
entries; with object growth unavailable, S0 (arm 5 vs arm 4b) and S7 (ARC-AGI-2 object arm vs its static) are
`None`, so the family has 8 members instead of 10 and the other secondaries are adjusted less. PROTOCOL.md line
172 says a test whose arms are both G0 is an exact tie that stays in the family; S0 and S7 are the same case one
step further (one arm not run). Fix: when arm 4b is not run, enter S0 and S7 as exact ties with p = 1 and an
interval of [0, 0], keeping the family at 10; state the rule in amendment 2.

**Finding 3 (medium): the speed factor is measured alone but the stops it serves run under concurrency.**
`phase2.py` lines 70 to 74 run the benchmark once, alone; the plan then runs the four grown arms of every benchmark
at once (line 85: eight processes on kernel A, which carries two benchmarks) and the static arms in four shards
(lines 87 to 92) on a kernel with four virtual processors (two physical cores). The static arms' cap is process CPU
time (`held.py` line 157), so under hardware-thread contention they get fewer executions than the Athe-measured
source cost represents, while the held base-search CPU measured under contention inflates the allowance. The net
effect is unknown and it bears on S1 (reach against efficiency) and on an arm-5 primary. Fix: run the benchmark
under the stage's concurrency (four copies at once, median per process) or express the static cap in executions
from the benchmark's executions per CPU-second; and cap the grown-arm stage at four processes. Memory: four static
children each limited to 12 GB of address space (`held.py` line 41) on a kernel of about 30 GB is a kernel-level
risk at larger allowances; at the 4 to 10 CPU-s allowances expected here it is small.

**Finding 4 (low): a second report run on the same folder is refused.** `report.py` line 47 treats the
`RESULTS.json` and `REPORT.md` that the report itself wrote as unlisted files. A scoring interrupted after those
files exist cannot be repeated without deleting them by hand. Fix: exclude the report's own two outputs from the
unlisted check (or write them to a `report/` subfolder excluded from the manifest comparison).

**Finding 5 (low): the two-attempt contract is not validated.** `report.py` line 85 checks only that the row keys
exist, and `ngrow/score.py` line 48 counts any attempt. The search returns at most two (`held.py` line 157,
`want=2`), so only a corrupted row could carry three. Fix: in `collect`, mark a row INVALID when `preds` holds more
than two attempts.

**Finding 6 (low): the pooled ARC-AGI-2 allowance is not rescaled to kernel C.** `arc2.py` lines 50 to 56 sum the
allowances measured on kernels A and B in their CPU seconds and apply them on kernel C without C's factor. Kaggle
CPU kernels are alike, so the error is small; state it in amendment 2 or scale by the ratio of C's factor to A's
and B's.

**Finding 7 (low): the incident's residue.** `logs/dry.log` keeps 95 lines (fit, stop and CPU per evaluation
task under G0) from the first dry run; the incident record cites the log as its source but the log is not frozen
and could be read or lost. Fix: record the log's sha256 and line count in the incident record (amendment 2) and
keep the file unread; do not delete it (it is audit evidence).

**Noted, no action:** `ngrow/data.py` line 75 loads every task's demonstrations and test inputs of a benchmark,
and the phase 1 stages then select the source ids (`library.py` lines 106 to 107, `discover.py` line 45); inputs
only, outcome-free, as the companion review noted. `ngb/dry_run.py` stubs the gate in its own process (lines 24
to 25) and asserts the ARC-AGI-2 stand-in before any arm runs (line 36). The GO's "one execution" is procedural:
`phase2.py` resumes rather than repeats, and nothing in code prevents a second run folder.

## 9. Boundaries (verified)

No code reads `<companion study folder>`, the builder's folder (`object_arm.py` imports it only through the
configured module, which is null) or anything under Step B; `ngrow/env.py` lines 27 to 29 deny writes to the
evaluation solutions, the companion folder and the construction study. Searches see demonstrations and test inputs
only; the only readers of test outputs are `ngb/score.py` and `ngrow/score.py`, both behind the GO for held and
evaluation ids. The kernels are private, CPU only, internet off (`kaggle_build.py` lines 166 to 169).

## 10. The reviewer's own re-runs (scratch copy of the committed tree; one CPU slot, nice 19)

1. **Admission tests**, re-run in the copy: all six pass, and the new `ADMISSION_TESTS.json` is identical to the
   frozen record.
2. **Package check**, re-run in the copy: 63 required files, 69 archive members, no problem, archive sha256
   9082f2570384698da0a1fabbf4363cae72eb98f752e363e463c0cf7de475e0b4, identical to `checks/PACKAGE_CHECK.json`.
3. **Package-mode smoke test** inside the extracted check archive: the first call, the gate's freeze check, failed
   with `GateRefused: no FREEZE.json`. See finding 8.
4. **Seed check**, re-run: PASS, the same pattern as the frozen record (sorted builder identical on every field
   across seeds 0, 1, 2; plain builder differs on mi0048's program text, `cover(I, asobject(I))` against
   `cover(I, asindices(I))`, and on execution counts; fits and predictions agree).
5. **Dry run**: not completed in the copy. It stopped at `bind_library` because the reviewer's copy pointed
   `NGB_REPO` at the real repository while `NGB_STUDY` pointed at the copy, so the frozen-path lookup failed. That
   is an artefact of the scratch setup, not a study defect; nothing was written (the refusal came first).

**Finding 8 (high, operational; found by the smoke test): the kernel package does not contain `FREEZE.json`.**
`FREEZE.json` cannot list itself in `files_sha256`, and `ngb/kaggle_build.py` lines 99 to 105 add only `runs/GO`
to the frozen-file list in build mode. The kernel's gate needs it (`ngb/gate.py` lines 38 to 39 and 79), so kernels
A and B would have refused at their first stage. This fails closed (no custody risk) but no version 2 kernel could
have run, and `PACKAGE_CHECK.json` "ok" did not show it because `check` tests only `files_sha256` entries. Fix:
add `FREEZE.json` to the archive entries in every mode, and make the package check extract the archive and run the
gate's freeze check inside it.

## 11. Method

Read-only. Hashes by `sha256sum` and `git show` against commit 9ed05245. Code read at the commit. The re-runs of
section 10 execute in a scratch copy made with `git archive` (dependencies reached through symbolic links), with
`NGB_STUDY` pointing at the copy, as one process under `scripts/with_cpu_slot.sh` at nice 19. The held solution
files, the held test outputs and the ARC-AGI-2 solutions were never opened or hashed by the reviewer. Nothing
public, nothing under Step B.
