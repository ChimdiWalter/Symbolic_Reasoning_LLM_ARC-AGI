# Independent pre-run review of study B, freeze version 3 (amendment 2)

Bounded re-review commissioned by the coordinator, 6 Nov 2026. Object reviewed: commit 4d18bb4b of
`experiments/natural_growth_b_20261105/` (the series e14b5dc1, 4ac32bbf, e0965d91, c10a283f, 4d18bb4b). Line
numbers cite that commit. No held task, held test output or ARC-AGI-2 solution was opened; no GO was written in the
study; every execution ran in a scratch copy of the committed tree or in the extracted kernel package.

**Verdict: HOLD, on one finding that is cheap to fix.** Every correction claimed for my eight version 2 findings and
for the companion study's version 2 blockers (its note 0477) is in the code and verified, mostly by re-running it
(sections 3, 4 and 6). But the kernel cannot compute the CPU allowance of the primary's comparator (finding 1): the
object arms' source cost reads two study A files that are neither frozen nor packaged, and in the extracted package
that cost raises `FileNotFoundError`. Under a GO, kernels A and B would run arms 1, 2, 3, 4a and 5 to 8 on the held
halves and then fail at arm 4b, and the protocol forbids re-running with changed code. Fix it, together with findings
2 to 4, in a dated amendment 3 (freeze version 4) with a bounded re-check; findings 5 to 9 are small and can go in
the same amendment.

Labels. G0 is the starting language (A2's whole arc-dsl grammar; A2 is the project's bottom-up program search). The
held arms: arm 1 G0; arm 2 library; arm 3 shuffled library; arm 5 object reuse (the builder's registry); arm 6 reuse
with a shuffled registry; arm 7 task-local object construction; arm 8 construction on another family's
demonstrations; arms 4a, 4b and 4c are matched static search at the library's, the reuse arm's and the
construction arm's CPU allowance. "The builder" is the object-level growth study `experiments/object_growth_20261105/`.
The "allowance" T(b, arm) is the matched static search's CPU per held task.

## 1. Hashes (verified)

| item | result |
|---|---|
| `FREEZE.json` version 3, live and at 4d18bb4b | a06af3fc6826ff68f1362962b8cd08d79872396d6d95bf333080bb5781517a76 (as stated) |
| `PROTOCOL_AMENDMENT_2.md`, live and committed | a362205a5a69288a913b3a4be3522ae703a7adc68d6dae6d35d003f96ff2a872 (as stated); listed in `amendments_sha256` with amendment 1 |
| `PROTOCOL.md`, `PROTOCOL_AMENDMENT_1.md`, `FREEZE_V1.json` | unchanged (76023877…, 3004c5d6…, 2e46511e…) |
| builder's `FREEZE_V2.json`, live and at d5ac3f1d | f6218c3eaca22e808870e8542eba48b82e74f0563f37cdbedc05097b1cefbd9e = the slot's `code_sha256` |
| builder's `CONTRACT_AMENDMENT_1.md`, live and at d5ac3f1d | d6181a1e682d0f1d29bb003d551193c5b635eaf6ababcb1359ee62f83251462a |
| incident log `logs/dry.log` | sha256 718e1dbb… and 140 lines, as the incident record now pins (not read) |
| working tree | no tracked change under the study; untracked dry-run row folders only; `runs/` empty |

## 2. The object slot against the builder's freeze (verified)

All 25 files pinned in `FREEZE.json` `object_growth.files_sha256` equal the files on disk and equal the digests the
builder's own `FREEZE_V2.json` records (its `files_sha256`, 115 entries); the 25th, `FREEZE_V2.json` itself, is
pinned by its own digest, which is the slot's `code_sha256`. The pins cover every `objgrow/` module, the three
registries (ConceptARC 2 operations, Mini-ARC 0, 1D-ARC 19), the three reuse records, the funnel, the development
report, the contract amendment and both builder freezes. The configuration names the contract
(`config/STUDY_CONFIG.json` lines 45 to 75). The builder's operations take no parameter (`objgrow/edits.py` lines 405
and 408 to 409), so this study's integer-parameter rule does not apply to them. The builder's contract functions
see demonstrations and test inputs only (`objgrow/arm.py` lines 37 to 69).

## 3. My version 2 findings, each verified

| finding (V2 review) | evidence in version 3 |
|---|---|
| 1 slot empty; registries not frozen; object arms never dry-run | slot filled (section 2); `feasibility/object_registries.json` freezes each arm's operations and digest, and `ngb/report.py` lines 121 to 129 reject a row whose G0, library or registry digest differs from the frozen value; dry run v7 ran arms 5 to 8 and 4a to 4c with the real registries (`checks/dry_run_v7/REPORT.md`) |
| 2 Holm family shrank | `ngb/report.py` lines 39 to 51: thirteen fixed secondaries, all always computed (lines 267 to 282); dry run v7: family 13 |
| 3 speed factor measured alone | `ngb/phase2.py` lines 49 to 58 (WORKERS copies at once) and 39 to 46 (every stage chunked to WORKERS processes) |
| 4 a second report refused by its own outputs | `ngb/report.py` lines 54 and 85 |
| 5 two-attempt contract unchecked | `ngb/report.py` lines 62 to 73 and 133 to 143; admission test `report_row_validation` |
| 6 pooled ARC-AGI-2 allowance not rescaled | `ngb/arc2.py` `pooled_allowance` re-expresses each benchmark's allowance in kernel C's seconds |
| 7 incident residue | the incident record pins the log by digest and line count; both verified |
| 8 `FREEZE.json` absent from the package | `ngb/kaggle_build.py` `entries_for` adds it in every mode; `check` verifies membership and runs the extracted smoke test; re-run below finds it in the archive |

## 4. The companion study's version 2 blockers (note 0477), each verified

| blocker | evidence |
|---|---|
| 1 package closure (freeze and `ngb/library.py`) | `FREEZE.json` packaged (above); the frozen-library loader moved to `ngb/ops.py`, `held.library_ops` no longer imports `ngb.library`; extracted-package smoke test passes (re-run, section 6) |
| 2 pass@2 and shape validation before solutions | as my finding 5 |
| 3 a missing arm 4b exempted | every one of the ten held arms and seven ARC-AGI-2 arms is required (`ngb/report.py` lines 203 to 229); admission test `report_requires_every_arm` |
| 4 Holm family varies with availability | as my finding 2; the ARC-AGI-2 folder is a required argument (line 186) |
| held loader read before its gate | `ngb/score.py` asks the gate before `_read_checked` for any held id; re-run gate fixture: zero reads |
| failure-row CPU null | `ngb/held.py` and `ngb/arc2.py` charge the process CPU and flag `child_cpu_unknown` |
| partial provenance | G0, library and frozen registry digests checked per row (above); `cpu_scale` and the resume path's identity are not checked, but a stale row from another GO is INVALID at scoring (fail-closed) |
| one-shot claims | scoring exclusive through `runs/SCORED_<GO digest>` (`ngb/report.py` lines 189 to 191, 320 to 321); execution one-shot remains procedural (see finding 7) |

## 5. Design checks

- **The arms.** Ten held arm labels (arms 1, 2, 3, 4a, 4b, 4c, 5, 6, 7, 8) and seven ARC-AGI-2 arms, as amendment 2
  section B tabulates (`ngb/report.py` lines 29 to 31, `ngb/held.py`, `ngb/arc2.py`).
- **The primary** is arm 5 vs arm 4b (`ngb/report.py` line 264). The pre-registered rule selects it: the builder's
  registries hold promoted operations (2 on ConceptARC, 19 on 1D-ARC) and both builder freezes were committed before
  6 Nov 12:00Z (69fb8415 at 00:18Z, d5ac3f1d at 01:25Z). The gate admits that primary now (re-run, section 6).
- **The Holm family** is the fixed list of thirteen (S0, S1, S2, S3, S4, S5 for each of the three benchmarks, S6 to
  S10).
- **Multi-pair wording.** Amendment 2 section E and the code describe the builder's criterion as multi-pair, not
  leave-one-out; the only "leave-one-out" strings in the frozen text are the corrections themselves. One residual
  inaccuracy, finding 8.
- **ARC-AGI-2** stays a secondary (S6, S7, S10) with its exposure stated in the protocol, both amendments and the
  report text (`ngb/report.py` lines 261 to 263).

## 6. The reviewer's re-runs (scratch copy of 4d18bb4b; one CPU slot, nice 19)

1. **Admission tests:** eleven of eleven pass; the re-run record is identical to the committed
   `checks/ADMISSION_TESTS.json`.
2. **Package check with the in-archive smoke test:** 91 required files, 98 members, no problem, archive sha256
   9b1ad2fa7b5c732f20b59ebfb59ff250339597504437b80cf6a5893926408b01, 43 modules loaded, all identical to the committed
   `checks/PACKAGE_CHECK.json`; smoke test clean, no solution file in the package.
3. **Gate refusals** (instrumented so that any solution read would be counted): without `runs/GO` the gate, the held
   solution loader, the ARC-AGI-2 solutions and challenges, a held run, the phase 2 driver and the report all refuse;
   zero solution reads; no held row written. A GO with a wrong freeze digest or an invalid primary is refused; a
   frozen file changed by one byte is refused; a correct GO naming arm 5 passes (the slot is filled). The scratch GO
   existed only for those calls and was removed.
4. **Inside the extracted package** (package mode): the builder's functions run and reproduce dry run v7 exactly on
   three source tasks: 1d0001 reuse fits with `obj_a6c446ddb7(I)`, co0003 construction fits with
   `obj_8051f4c2b8(I)`, mi0002 construction does not fit; all 43 project modules load from inside the package.
5. **Allowance inputs inside the extracted package:** the library's source costs compute (679.5, 298.1 and 998.1
   CPU-s, as amendment 2 corrects them); every object and construction source cost raises `FileNotFoundError`
   (finding 1).

## 7. Findings

**Finding 1 (blocker): the primary's comparator cannot be computed in the kernel.** `ngb/object_arm.py` line 34
reads study A's `feasibility/controller_source_shard0.jsonl` and `shard1.jsonl` for the object arms' source cost
(lines 113 to 128). Those files are not in `FREEZE.json` and so not in the package (`ngb/kaggle_build.py` derives the
package from the freeze). `ngb/held.py` lines 209 to 210 compute the static allowance before the per-task loop, so
the exception is not turned into rows: the shard process exits with an error, `ngb/phase2.py` line 138 marks the
kernel FAILED at `held_static_obj_<benchmark>`, after arms 1, 2, 3, 4a and 5 to 8 have already run on the held half.
Arms 4b and 4c, and kernel C's pooled object allowances, are never produced. It fails closed (the report would be
INCOMPLETE), but the one-shot GO would be spent, and the protocol forbids resuming with changed code. Even on Athe,
the comparator's budget depends on files outside the freeze. The smoke test missed it because it never computes an
allowance input (`ngb/package_smoke.py` lines 53 to 62), and the dry runs ran on Athe, where the files exist. Fix:
(a) compute the three controller-CPU totals once on Athe (ConceptARC 540, Mini-ARC 247, 1D-ARC 797 CPU-s, as
amendment 2 states) and freeze them in a packaged record (for example in `feasibility/object_registries.json` or a
new `feasibility/object_costs.json`) that `object_arm.source_cost` reads, or freeze and package the two shards; (b)
make the smoke test call `held.source_cost` for every benchmark and matched arm, and call the builder's reuse and
construction functions on one source task per benchmark, inside the extracted package (as re-runs 4 and 5 above
did); (c) re-freeze (version 4) and re-run the package check.

**Finding 2 (medium): the honest expectation for the primary contradicts its own simulation.**
`PROTOCOL_AMENDMENT_2.md` line 87 says that with static gains at the 4x search's level arm 5 is "ahead by about 80 to
180 tasks, 'arm 5 beats arm 4b' nearly certain", but line 114 and `power/POWER_OBJECT.json`
(`reuse_vs_static_at_4x_gains`: "A beats B" 0.003, "inconclusive" 0.997) say the opposite. The simulation sets the
four families without an out-of-sample estimate to zero gain (`ngb/power_object.py` line 59, `er = e_reuse or
0.0`), so it covers the 80-task end only. There the family-clustered interval crosses zero: the gain sits in four of
fourteen 1D-ARC families and 1d_flip goes the other way (matched search re-finds it), so resampling fourteen clusters
gives a lower bound below zero. A rough calculation with the four unmeasured families transferring at their
source-half fit (about 25 tasks each) gives a lower bound well above zero, so "beats" becomes likely; that case is
not simulated. Fix, in the amendment, before the GO: replace the sentence with what the record supports ("with the
measured families alone, the pre-registered primary is expected to be inconclusive even at an advantage of about 80
tasks, because the clustered interval crosses zero; 'beats' needs the four unmeasured families to transfer"); add the
simulation with those families at their source-half grown-fit rates; and say that the by-family table carries the
reading in either case.

**Finding 3 (medium): code errors are scored as abstentions.** `ngb/report.py` line 53 lists `arm_error` and
`no_donor` among the failure stops, but only counts them (line 179); `collect` (lines 98 to 148) accepts such rows,
and scoring treats them as "no answer". A systematic error in a growth arm (for example an import or data failure of
the builder's functions in the kernel, the kind finding 1 shows can escape the checks) would become a large loss in
the primary or in S8 and S9, not a failed run. Fix: in `collect`, a row with stop `arm_error` is INVALID (a defect of
the run, not an outcome), and so is a `no_donor` row on the real held half (the amendment says it cannot happen
there); the static children's `child_*` rows stay pre-registered no-answer outcomes, counted and reported.

**Finding 4 (medium): static children can be killed by the kernel's memory, not their own cap.** `ngb/phase2.py`
lines 112 to 118 run each static arm as four concurrent shards, each child limited to 12 GB of address space
(`ngb/held.py` lines 48 and 138 to 141), on a kernel with about 30 GB. At the object allowances (about 19 to 83 CPU-s
per held task, amendment 2 section B), four large searches can exceed the kernel's memory; the out-of-memory killer
then ends a child, which becomes `child_failed`, no answer, a loss for arm 4b or 4c and a win for the growth arm in
the primary. Amendment 2 section G accepts a child hitting its own 12 GB cap, but a kill caused by the concurrency is
an artefact. Fix: after each static stage, run once more alone every task whose child was killed (negative return
code) or failed on memory, and let that result stand, recording both (the construction test pre-registered this
rule); or run the static arms with two shards. Report the count per arm.

**Finding 5 (low to medium): kernels A and B's outputs are not verified before kernel C and the report use them.**
`ngb/kaggle_build.py` lines 118 to 126 package A's and B's `held/` trees into kernel C without checking their
`OUTPUT_MANIFEST.json` or `STAGES.json`; the report then verifies only C's folder (`ngb/report.py` lines 196 to 200),
whose manifest was computed over the copies. Row validation still catches missing, duplicate or mis-provenanced rows,
but not a changed prediction inside a well-formed row, nor a FAILED or INCOMPLETE status in A or B. Fix: in
`kaggle_build.py arc2`, verify each A and B folder's manifest (every digest, no unlisted file) and `STAGES.json` (this
GO, this primary, status complete) before packaging, record their manifest digests in the C package manifest, and
have the report check C's `held/` against them.

**Finding 6 (low): the S4 decision reads backwards.** S4 compares wrong answers (`ngb/report.py` lines 43 and 272):
d = the library's wrong answers minus matched search's, so the rule's "w_a beats w_b" means the library made more
wrong answers. Fix: give S4 explicit decision labels ("the library makes more wrong answers than matched static
search" and the reverse).

**Finding 7 (low): the scoring claim is written only at the end.** The marker that makes scoring exclusive is
checked at `ngb/report.py` lines 189 to 191 but written only after the report (lines 320 to 321), so a crash after the
solutions were opened leaves no claim. Fix: write a claim (`runs/SCORING_<GO digest>`) immediately before the first
solution file is opened and refuse when either it or the completion marker exists.

**Finding 8 (low): colour tables are misdescribed in two places.** `PROTOCOL_AMENDMENT_2.md` lines 26 to 27 and
`ngb/object_arm.py` line 11 say colour tables are "labelled by construction". The builder's contract amendment
(section 1) says a colour-table pair counts when some object in it is bound to any constant recolouring, and only
whole-output forms are labelled unconditionally; amendment 2's own section E (lines 147 to 150) says this correctly.
Fix: align section A and the docstring with section E.

**Finding 9 (low): custody notes.** (a) The version 2 freeze (37c36cb0…) is not kept as a byte copy in the folder,
unlike version 1 (`FREEZE_V1.json`); it survives only in commit 9ed05245. Keep it as `FREEZE_V2.json` or name the
commit in the amendment. (b) The expectations read study A's `feasibility/FEASIBILITY.json` (`ngb/power.py` line 53,
`ngb/power_object.py` line 26), which is outside this freeze; record its digest in the freeze (Athe-only).

## 8. Method

Hashes by `sha256sum` and `git show` against 4d18bb4b and d5ac3f1d. Code read at the commit; the builder's tree read
only for the pinned files and the contract. Executions: a scratch copy made with `git archive 4d18bb4b`
(dependencies by symbolic link, never written through) for the admission tests, the package check and an
instrumented gate fixture; the package archive built by the study's own `entries_for` and `archive`, extracted to the
scratch folder, for the package-mode probes on three source tasks and the allowance inputs; one process at a time
under `scripts/with_cpu_slot.sh` at nice 19. No held task, held test output, ARC-AGI-2 solution or held solution
file was opened or hashed by the reviewer; nothing public, nothing under Step B.
