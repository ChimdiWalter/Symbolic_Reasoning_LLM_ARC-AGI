# Independent pre-run review of the construction test at scale (revision 4)

Bounded exact-byte re-review commissioned by the coordinator, 6 Nov 2026 (UTC, about 09:05Z to 09:50Z). Object:
revision 4 of the pre-registration, frozen in commit 7b393872, folder `experiments/construction_at_scale_20261105/`,
with the post-freeze checks of commit 57072260. Scope: whether revision 4 fixes the findings of this project's review
of revision 3 (`reviews/INDEPENDENT_PRE_RUN_REVIEW_REVISION_3.md`, commit c7bd34e0) and of the companion study's
re-review of revision 3 (its note 0487, report under
`<companion study folder>/construction_at_scale_revision3_independent_review_20261106/`, read only),
plus the freeze, the gate and exposure. Line numbers are those of commit 7b393872; every frozen file was read from, or
verified equal to, those bytes. The reviewer did not design the study.

**Verdict: PASS WITH FIXES.** Both revision 4 digests verify, every digest in `FREEZE.json` matches the committed
bytes, and revisions 1 to 3 are kept byte for byte. Every finding of both reviews of revision 3 is fixed in
substance, each confirmed in code and, where a check was possible, by a fixture or a test. The gate refuses without a
GO, enforces one use and now refuses a task set that is not the main pool's. No main-pool task exists, no growth arm
or matched search has run on any task of this study, and nothing reads the ARC evaluation set. There is no high or
medium finding. Three low findings need a decision or a pre-declaration before the GO, and each can be settled without new
frozen bytes (section 6): the strict verification's colour rule is stricter than the search that writes the predictions,
so a legitimate wrong prediction can make the whole study INVALID (Finding 1); the failure flag behind the
pre-declared "primary without failed matched searches" is taken from the results without reconciliation (Finding 2);
the operator-error rule is keyed on the INCOMPLETE label, while revision 4 labels many placement errors INVALID
(Finding 3). Finding 4 lists wording slips for the report.

Labels used below. S1 is the original construction test (`experiments/capability_growth_20261027/`); A2 is the
project's bottom-up program search over arc-dsl, and G0 the starting language of a world (A2's grammar minus the
world's removed operations). The worlds are W1, W2 and W3. Task partitions: M (motivating), V (validation), E
(excluded, evaluator-only), D (search-level decoys) and U (previously solved tasks, the regression set; a real U task
is an ARC training task that A2 solved, kept with its real output). Methods: S-hole (growth from CORA's typed holes),
S-demo, S-shuffled, S-enum (blind enumeration) and C7m (matched static search over G0 alone). "The commitment" is
`runs/cas_commit/COMMITTED_PREDICTIONS.json`, the at most two predictions per unit, matched search and grown-grammar
search, frozen before any label is read; "the results" is `runs/cas_eval/world_results.json`. "Rule 6" is
`PROTOCOL.md` section 4, rule 6 (motivating sources and other worlds). The companion's two revision 3 findings are
its R1 (duplicate rows) and R2 (saved-prediction schema). The GO is the coordinator's token file `GO_CAS`; the
claim is `runs/RUN_CLAIM.json`, which the gate writes when the GO is first used. VmPeak is a process's peak virtual
memory, the quantity an address-space limit bounds.

## 1. Hashes and freeze (verified)

| check | result |
|---|---|
| `PROTOCOL.md` at 7b393872 | 01d12e10fd512c832296093a5d3b5e4ebd61dc3a4b207278d76259759c920ee0, as stated; equals `FREEZE.json` "protocol_sha256" |
| `FREEZE.json` at 7b393872 | b17f28d025a81c18f0578b1076e6ea72f73a58ea62af82295ce7397b4bdc9cd8, as stated |
| 104 study files in "files_sha256" | all equal the bytes committed at 7b393872 and the live bytes |
| 44 dependencies | 37 equal the committed bytes; the 7 untracked in git (`a2/out/corpus.json`, `a2/out/traces.jsonl`, five arc-dsl files) equal the live bytes; all 44 identical to revision 3's record |
| 2 ARC training data files, seeds and salts | equal the live bytes; identical to revision 3 |
| revisions kept | `PROTOCOL_REVISION_3.md` (6a30ac31...) and `FREEZE_REVISION_3.json` (9d56be8b...) equal `PROTOCOL.md` and `FREEZE.json` of 67322f40; revision 2 (885bbcc8..., c7c586fa...) equals ecafd841, revision 1 (b3759bfc..., 260ee753...) equals 6b5fb6f8; "supersedes" lists all six, the header prints them (lines 12 to 17) |
| changed from revision 3 | `PROTOCOL.md`, `cas/analysis.py`, `equivalence.py`, `freeze.py`, `gate.py`, `generate.py`, `kaggle_main.py`, `run_world.py`, the plumbing, smoke and dry-run records, two launch scripts, the revision 3 copies and review; `env.py`, `bench.py`, `kaggle_build.py`, the configuration, pools and power files unchanged |
| after the freeze | 57072260 added only `checks/STRICT_FIXTURE_REVISION_4.json`, `checks/PACKAGE_SMOKE_REVISION_4.json` and `PROGRESS.md` lines; no later commit (to HEAD 299441e2) touches the study; working tree clean |

## 2. This project's review of revision 3: each finding

**(1) Matched-search memory. Fixed.** The first attempt keeps the 8 GB limit; a search stopped by memory, a
MemoryError or a child killed with return code -9 (`cas/run_world.py` lines 350 to 353), is run once more by
`c7m_rerun` (lines 356 to 390) with a 20 GB limit (line 60), the same cap, its own child and the same wall-time guard;
that result stands, the first attempt is kept beside it (line 384), and `rerun_alone` stops a second rerun. A child
stopped by the guard is recorded as timed out without a return code (lines 322 to 325), so it is not rerun, as
declared. The rerun is a kernel stage of its own between the last matched searches and the commit
(`cas/kaggle_main.py` line 106); stages run one after another (lines 110 to 128), so nothing else runs beside it. The
analysis requires the stage and its pin record (`cas/analysis.py` lines 65 and 66). Every child that reaches its
result line records its limit, VmPeak and peak resident memory (`run_world.py` lines 297 to 299). The primary
without the tasks whose matched search failed is pre-declared (`PROTOCOL.md` lines 430 to 431, 501 to 502) and
computed (`analysis.py` lines 657 to 662). Checks: the rerun smoke record (S1's task t83286f67, a simulated memory
failure, rerun alone at 20 GB, VmPeak 5.97 GiB, first attempt kept); a fixture case with one motivating matched search
failed consistently in the commitment and the results passes and reports that primary over 10 tasks with 1 excluded.
One gap remains (Finding 2); a residual risk is noted in section 5.

**(2) Three verification boundaries. Fixed.**
- Duplicated row: the results' rows must be a list of records with unique task ids (INVALID otherwise) and exactly as
  many as expected (`analysis.py` lines 330 to 342), each with exactly seeds 0 to 2 and the four growth arms (lines
  343 to 346), before any statistic (lines 584 to 590).
- Controller summary: its task set must equal the keys of the hashed `TASKS_SYSTEM.json`, every decision must be one
  of the controller's five (lines 67 to 68, which are exactly the values `cgrow/controller.py` assigns, lines 121 and
  160 to 165), and the results' controller decisions must equal the summary's (lines 452 to 466).
- Endpoints: `_rescore` (lines 218 to 262) re-derives every unit, motivating and excluded matched-search, reuse,
  transfer and per-structure endpoint from the commitment and the labels of the hashed `TASKS_EVAL.json`, with at
  most two predictions, and any disagreement is INVALID. The two minor cases are closed too: three predictions fail
  the bounded schema (lines 108 to 112), and an excluded task's matched search needs its failure flag (lines 376 to
  377).
- Checks: the author's fixture (`checks/strict_fixture.py` of 7b393872), run unchanged in this reviewer's mirror,
  reproduces its committed record exactly: the complete fixture passes and all 24 defects return INCOMPLETE or
  INVALID with the same first problems. The reviewer's own cases on the same base: a matched-search endpoint, a
  per-structure endpoint and a reuse endpoint flipped in the results, and a controller decision changed in the
  summary alone, are all INVALID.

**(3) Rule 6 and the real U reservation. Fixed in the generator, verified by the analysis, text corrected.** Every
world's real U sources are reserved first and their union is excluded while any motivating task is built
(`cas/generate.py` lines 388 to 396, through `next_source`, lines 185 to 189); the build asserts the rule for every
partition (lines 407 to 413); the strict analysis refuses any task of another world that shares a motivating source
(`analysis.py` lines 470 to 484); `PROTOCOL.md` lines 253 to 260 state the rule as enforced. Checks: the real
`build()` with stubbed filters and synthetic source ids (no grid read, no search, nothing written; the revision 3
review's test) gave no link from any motivating source to any task of another world, of any partition, in 12 of 12
trials, and with revision 3's filter restored the new assertion fired in 12 of 12; the committed dry run has no
violation of the full rule (37 sources); fixture cases in which a second world's excluded task, or its previously
solved task, takes a first-world motivating source are INVALID, while the same two-world fixture without that link
passes.

**(4) Report corrections. Done.** The S-enum cap rule is stated exactly (`PROTOCOL.md` lines 336 to 343), and the
compute table and stop rule no longer read 60 s as a bound (lines 626, 637 to 638). The overshoot figure (lines 441
to 443) matches `checks/s1_world/runs/cas_arms/units_enum_s0.json`: overshoots 0.88, 1.95 and 15.93 s, mean 6.25 s
over those 3 and 1.71 s over the 11 recorded units, seeds 1 and 2 without a record; the evaluator now reports both
means (`run_world.py` lines 685 to 692). The matched-search bullet gives 8 GB (lines 344 to 347). The regression rule
is S1's (lines 328 to 329; `cgrow/s1.py` lines 167 to 172). The clip comment reads [1, 3] (`run_world.py` line 62).
The S-hole CPU figures (lines 449 to 451) match the plumbing results (mean 14.15, diagnosis 4.41, gates 9.71,
enumeration 0.023, maximum 23.1, actual 3.29 CPU-s).

**(5) Main pool at packaging. Fixed.** The package stage refuses a build summary that does not name the main pool
with the rule asserted, any task source outside the main pool of `config/POOLS.json`, and any world built before the
claim (`cas/gate.py` lines 96 to 104, 114 to 119; `PROTOCOL.md` lines 717 to 719). Tested in section 4.

**(6) Smaller items. Done.** `struct_scores.json` is written even when nothing was promoted (`run_world.py` line
671) and a failed end benchmark leaves a failure record (`kaggle_main.py` lines 129 to 135). Dependence within W1 and
W3 is stated with the primary, with per-world and leave-one-world-out primaries (`PROTOCOL.md` lines 493 to 502;
`analysis.py` lines 663 to 671). The plumbing check's run files are committed (19 under `checks/s1_world/`, 6 under
`checks/s1_world_controller/`). The fixture builds every case under its scratch argument and writes nothing in the
study except its record. The operator-error rule is declared (`PROTOCOL.md` lines 726 to 729; see Finding 3). The
package manifest and notebooks are to be committed before any push, each printed archive digest recorded, and each
kernel's `runs/` placed at `runs/generated/<world>/runs` (lines 719 to 722; `PROGRESS.md` next steps).

## 3. The companion's re-review of revision 3

**R1, duplicate motivating rows. Fixed.** As in item (2): unique ids and exact cardinality (`analysis.py` lines 330
to 342) and exact seeds and arms (lines 343 to 346), all before any statistic; the statistics iterate the rows only
after an empty problem list (lines 584 to 611). Fixture: a duplicated row is INVALID.

**R2, saved-prediction schema. Fixed.** `_check_commitments` (lines 119 to 215) requires exact unit and
matched-search key sets (lines 126 to 133) and the exact grown key set: reuse and transfer for every excluded task and
one key per promoted structure per excluded task, the promoted structures read from the committed units (lines 135
to 158, 187 to 191). It recomputes the grown grammars from the committed S-hole promotions and compares them with the
commitment (lines 172 to 186). Every record must have exactly its fields (lines 146, 163 to 164, 207 to 209); a
prediction list holds at most two attempts of one grid per query (lines 108 to 112); a search that did not fit must
commit an explicit empty list, distinct from an absent one (lines 169, 213); a unit commits nothing explicitly as
null predictions with no kind (lines 149 to 151). Fixture cases: transfer predictions removed, an extra malformed
per-structure key, three predictions, absent matched-search predictions and a fit with an empty list are all INVALID.
The intact writer passes: the complete fixture is S1's world as the revision 4 code wrote it (132 unit, 35
matched-search and 288 grown records). The verifier's grown grammar equals the writer's because both of S1's unit
loops stop at the first promotion (`cgrow/s1.py` lines 236 to 238, 263 to 265).

The companion's three wording points (the resource table's "at most 60", section 5's "therefore at least 60", and
the primary's scope and denominator) are fixed (`PROTOCOL.md` lines 626, 336 to 343, 493 to 502; the denominator in
`analysis.py` lines 641 to 656).

## 4. Gate, exposure and state (verified)

The gate (changed in revision 4) was exercised on the scratch mirror with `CAS_STUDY` pointing at it and its GO path
pointed at a token file of another name; no file named `GO_CAS` was written anywhere.

| step | outcome |
|---|---|
| no token, generate / analyse | `FAIL ...: no GO_CAS` |
| token, generate; again | ok, claim written in exclusive mode; then `FAIL generate: the GO was already used` |
| analyse; token with one more line; wrong freeze line | ok; `FAIL analyse: RUN_CLAIM.json names other GO bytes`; also `does not bind the live PROTOCOL.md and FREEZE.json` |
| claim removed with `runs/generated/` present; both removed | `FAIL generate: runs/generated/ exists ...`; ok (the recovery path) |
| package, the committed pilot dry run | `FAIL`: not the main pool with the rule asserted; 22, 22 and 17 sources outside the main pool; built before the claim |
| package, a stand-in: dry-run files with every source id replaced by a main-pool id (ids only), the summary naming the main pool, built in the claim's second | ok |
| the stand-in with one source outside the main pool / built one second before the claim / without the rule flag / naming the pilot pool | each `FAIL` with the matching message |
| a task file changed after its manifest; a world missing; restored | `FAIL`; `FAIL`; ok |
| one byte appended to `cas/analysis.py`, `cas/gate.py` or S1's `cgrow/s1.py`; restored | `FAIL ... changed or missing`; ok |

Exposure and state:
- **No main task, no run.** The study has no `runs/`, no `GO_CAS` and no claim. Of 192 text files, only
  `config/POOLS.json` names main-pool ids; the 98 distinct task sources in the study's records are 37 pilot-pool ids
  and 61 of S1's own, none from the main pool.
- **No arm on any study task.** The only arm outputs are the plumbing check on S1's world; the matched-search smokes
  ran on S1's task t83286f67; the post-freeze package smoke ran the controller stage only, on pilot dry-run tasks.
- **ARC evaluation set.** Still read only as ids, to assert that no pool overlaps it (`cas/pools.py` line 28,
  unchanged).
- **Held outputs.** The new label reads are the analysis re-scoring (after the kernels) and the package stage, which
  uses only the source fields of `TASKS_EVAL.json`. `c7m_rerun` loads the evaluator file into an unused variable
  (`run_world.py` line 367); its child, like every search, receives demonstrations and query inputs only
  (`X.as_task`). As noted for revision 3, this is a property of the code, not a process boundary.
- **Dry run.** 22, 22 and 17 tasks (8, 8 and 6 motivating), two excluded-task slots of W3 (vupscale and hupscale)
  unfilled, pool "pilot", rule flag true, as stated (`PROTOCOL.md` line 288).

## 5. Findings, with exact fixes

### Low

**Finding 1. The colour rule of the strict verification can turn a legitimate wrong prediction into a final
INVALID.** `_grid` (`analysis.py` lines 102 to 105) requires every cell of every committed grid to be an integer from
0 to 9, and a record that fails it is "malformed", so the study is INVALID with no statistic (lines 153 to 154, 169,
213, 587 to 590), and final under `PROTOCOL.md` lines 728 to 729. The code that writes those grids guarantees less.
A2 keeps any value whose first cell is an integer and whose rows are rectangular, at most 30 x 30 (`a2/arcdsl.py`
lines 146 to 159: no range check on the cells, although its docstring says "non-colour cells"), and a program fits
when its demonstration outputs are equal under Python equality (`a2/bus.py` lines 172 to 175); its query values are
committed unfiltered (`cgrow/search.py` line 34; `run_world.py` lines 294, 411, 498). G0 is built from the 194 verified
S_train solvers of `a2/out/corpus.json` (`cgrow/lang0.py` lines 37 to 46), which use the constants TEN (6 solvers),
NEG_TWO (3) and NEG_ONE (1) and integer arithmetic beside `fill` (85), `paint` (55), `replace` (26) and `canvas`
(24), so a fit such as a fill whose region is empty on every demonstration input but not on the
query, coloured 10, is legitimate and wrong; a cell holding True fits where the output has 1 and is even scored
correct by `EV.correct`. The author's fixture treats "invalid colour" as a defect by design. The rate is low: every
saved prediction in S1's records, the plumbing check and A2's two training-selection files (880 grids) has cells 0
to 9, and A2's cost prior makes such fits rare (TEN and the negative constants are rarer in the corpus than the colour
constants, so dearer, and a cheaper distinct fit is usually found first). But one such grid among the several thousand of phase 2 would
end the study. Fix, before the GO, one of: (a) a revision 5 limited to `analysis.py`, where `_grid` checks the shape only
(a non-empty rectangular list of non-empty lists) and leaves cell values to the scoring; (b) without new frozen bytes, pre-declare in the addendum
of section 6 that an INVALID whose only problems are committed grids failing the cell rule, with every digest
verified, is a verifier false positive, and that the independent recomputation then completes the analysis with the endpoints
as the frozen scoring rule gives them (`cgrow/evaluate.py` lines 46 to 48, the rule `_rescore` already applies) and
reports it; or (c) record before the GO that this risk is accepted.

**Finding 2. The failure flag behind the "primary without failed matched searches" is not reconciled with the
commitment.** `_rescore` compares each matched-search endpoint with the commitment's predictions and failure flag
(`analysis.py` lines 242 to 250), but never the results' own flag; `main` takes that flag from the results (lines
603, 658) for the pre-declared descriptive primary and for the failure counts (lines 712 to 713). Fixture case: the
results' flag set on one motivating task whose search did not fail (endpoint and commitment unchanged) passes, and
the analysis reports that primary over 10 tasks with 1 excluded, and one failure. The decision is not affected; this
output was added to answer this project's finding 1 on revision 3. Fix, one of: (a) in a revision 5, require
`u["C7m"]["failed"] == c["failed"]` for every motivating and excluded task in `_rescore`, or derive the failed set
from the commitment in `main`; (b) pre-declare in the addendum that the independent recomputation derives the failed
set from the commitment, checks it against the results, and reports the descriptive primary from it, a mismatch
making the study INVALID.

**Finding 3. The operator-error rule is keyed on the INCOMPLETE label.** `PROTOCOL.md` lines 726 to 729 allow one
correction of "an INCOMPLETE caused only by an argument or placement error", and lines 694 to 695 say that anything
missing makes the study INCOMPLETE. The code labels the study INVALID whenever any problem is INVALID (`analysis.py`
line 587), and the re-scoring flags absent rows and endpoints as disagreements: in the author's fixture a dropped
row, a missing endpoint and a missing grown key all come out INVALID. A world folder placed under another world's
name, or the wrong downloaded archive, would therefore be INVALID and, read literally, final, although the kernel
outputs are intact. Fix, before the GO: pre-declare in the addendum that the one-time correction applies to an
INCOMPLETE or INVALID whose only cause is an argument or placement error, shown by the digests (each downloaded
archive equals the digest its notebook printed, and each world's `OUTPUT_MANIFEST.json` verifies), and say in the
report that the label alone does not separate missing from malformed work.

**Finding 4. Wording slips for the report.** (a) Line 433 says the plumbing check was "re-run with revision 3's
code"; it was re-run with revision 4's (`launch/run_rev4_runs.sh`). (b) The VmPeak figures are in units of 10^6 kB
against limits in GiB: 6,359,552 kB is 6.06 GiB of the 8 GiB limit, and the rerun's 6,262,652 kB is 5.97 GiB (lines
461 to 463), so the headroom is 1.94 GiB, not 1.64. (c) Line 288 still describes the dry run's assertion as the
motivating-to-motivating one; the full rule was asserted. (d) The kernel stage list of section 10 (lines 658 to 667)
omits the rerun stage, which sits between the remaining matched searches and the commit. (e) Rule 6 cites "section
11, step 5" for the verification, which is listed in section 10, route step 5. (f) "Every child records its peak
virtual memory" (lines 422 to 423): a child killed by the operating system leaves no record.

### Notes (no action required)

- **Memory errors inside A2's primitive calls are swallowed.** `a2/bus.py` lines 239 to 252 catch `Exception`, which
  includes MemoryError, so a search near its address-space limit can skip candidates and still end on the CPU cap as
  an ordinary search, which is not rerun. A MemoryError in the bank code soon follows in practice and is caught as
  `memory_capped`. Cheap mitigation in the report: list every matched search that stopped on the CPU cap with VmPeak
  above 90% of its limit (the records hold both).
- **A decision flipped consistently in two kernel outputs is undetectable.** A fixture in which one motivating task's
  decision is changed in both the controller summary and the results, with its rows and commitments removed and the
  digests refreshed, passes with 10 tasks. Both files are written from the same `records.pkl`, and no hashed input
  holds the decision, so this is inherent; the reported controller exclusions (`primary.denominator`) make the count
  visible.
- **A claim without its time disables the built-after-claim check** (`gate.py` line 118 fails open when "claimed_utc"
  is absent). The gate always writes the field, so this needs an edited claim.

## 6. Before a GO

1. **Required:** Findings 1, 2 and 3, each by one of the routes given; Finding 4 corrected in the report. The routes
   without new frozen bytes use one short addendum, committed before the GO and bound by its sha256 as a third line
   of `GO_CAS`: the gate compares only the first two lines (`gate.py` line 57), and the claim records the sha256 of
   all of the GO's bytes (line 134), so the addendum is fixed by the one-use claim.
2. **If a revision 5 is made** (Finding 1 or 2, route a), the check it needs is limited to the `analysis.py` diff and
   a re-run of the fixture with these cases; every other result here carries over while its bytes stay unchanged.

## 7. Method of this review

Read-only for the study. A scratch mirror was built with `git archive 7b393872` plus the 44 dependencies, every
frozen digest verified in the mirror. Scripts ran one at a time under `scripts/with_cpu_slot.sh` at nice 19 (about ten
sub-second JSON reads and greps ran directly, outside the slot, two of them at nice 19 while another job held both
slots): the digest check against
`git show`; the author's fixture, unchanged; ten fixture cases of the reviewer's on the fixture's base; the gate test
with a token not named `GO_CAS`; the stubbed generator test with synthetic ids; an exposure scan; a scan of saved
predictions. No task was generated, no arm or matched search ran, no `GO_CAS` was written, and nothing under Step B
or anything public was touched. Scripts and outputs are in
`/tmp/scratch/rev4/` (temporary); the key numbers
are quoted above.

## 8. Addendum 1 (commit 48cfb1b8), checked before the GO

Checked 6 Nov 2026, about 10:00Z to 10:25Z. Object: `ADDENDUM_1.md` (sha256
071c5bbb3324ca915ad85a193b3ba83341fc4e1def966b4ed55e7aa4884187bf) and `addendum_1_recompute.py` (sha256
ce1ffe392e3df06077d25f7be345ea11ebd06a168fc514db3a3b7c3ca783c4cd), both verified at 48cfb1b8 and live; the addendum
states the script's digest. No frozen byte changed (all 104 study files equal their `FREEZE.json` digests at
48cfb1b8), and neither file is frozen or packed into the kernels.

**Verdict for the addendum: PASS.**

- **Coverage.** Section 1 answers Finding 1 by route (b); section 2 answers Finding 2 by computing the descriptive
  outputs from the commitment, checked against the stage files and the kernel log; section 3 answers Finding 3 as
  intended (an INCOMPLETE or INVALID caused only by operator error, shown by the archive and output-manifest digests,
  corrected once and logged); section 4 lists all six wording slips of Finding 4 and the three notes.
- **The decision changes only through the colour rule.** When the frozen verification passes, the script writes no
  analysis and the frozen `ANALYSIS.json` is the reported one (script line 278). It writes an analysis only when the
  frozen verification has problems, the same verification with `_grid` reduced to the shape has none, and a committed
  prediction holds a cell outside 0 to 9 (lines 258 to 260). It then changes only endpoints whose committed record
  holds such an attempt, re-scored by the frozen rule with that attempt dropped (lines 124 to 173), and runs the frozen
  `main` with `verify_complete` returning those worlds (lines 267 to 272). Only `_grid` differs between the two
  verifications, and only `_attempts` in `_check_commitments` uses it, so the problems that vanish are exactly the
  cell-rule ones (with the promoted-structure keys that follow from them); any other problem keeps the frozen result.
  Both patches are in memory and restored, and the script writes only its own folder, never `runs/analysis` (lines
  228 to 231).
- **Binding and refusals,** tested in a scratch copy with opening `<study>/GO_CAS` redirected to a token of another
  name, so no file named GO_CAS was created. The binding refused with no GO, with a GO of two lines, with a third line
  naming another digest, with a claim made under other GO bytes, with an addendum that no longer states the script's
  digest, and with the script changed by one byte; it passed with a valid three-line GO. In bound mode the script
  refused `runs/analysis` as its folder, refused (exit 3) with no frozen output and with a frozen output listing other
  problems, and, run after the frozen analysis itself, agreed, kept the frozen INCOMPLETE and wrote only its record.
  The frozen files were unchanged afterwards.
- **Self-test rerun** in a scratch mirror, in one CPU slot: 11 of 11 cases as expected, every recorded field
  identical to `checks/ADDENDUM_1_SELF_TEST.json`. In the three cases where the rule applies, the analysis it writes
  equals the frozen analysis of the matching control world (an ordinary wrong attempt), which is the declared effect.

Rulings on the owner's four choices:
- **(a) A cell holding True or 1.0 is scored incorrect: accepted.** ARC colours are the integers 0 to 9, the frozen
  analysis cannot score such a record at all, and the rule applies alike to every method. The report should say that
  for these cells the rule departs from the Python equality of `EV.correct`.
- **(b) The rule applies per attempt: accepted.** This is the frozen pass@2 rule (either attempt reproduces every
  query output), so an invalid attempt is one wrong attempt; self-test case 2 changes no endpoint and reproduces the
  intact world's analysis.
- **(c) A disagreement makes the descriptive outputs unavailable, not the study INVALID: accepted.** Those outputs
  carry no decision. An intact run cannot disagree: the commit copies the final stage records by the same rule after
  the rerun stage, and nothing writes the matched-search files after the commit. INVALID would add a refusal route to
  the frozen decision for a descriptive output. When a listed disagreement concerns a motivating task, the report
  should state it beside the decision, since that search's committed failure flag enters the primary's
  matched-search endpoint.
- **(d) The script stops unless its own frozen verification matches the frozen output: accepted.** This ties the
  script to the inputs the frozen analysis judged. The verification is deterministic and its messages use real
  paths, so a faithful repeat agrees, and the later of the two possible outputs is taken by modification time, which
  also covers a corrected re-run after an operator error.

Before writing GO_CAS:
1. Write all three lines at once, before generation. The claim fixes all of the GO's bytes at the generate stage,
   so a third line added later would make every later stage refuse.
2. Keep `ADDENDUM_1.md` and the script exactly as at 48cfb1b8. Neither is frozen, and their binding is checked only
   when the script runs.
3. The script's `--test` switch skips the binding check, and its record then says "binding_checked": false. The
   report must use a record with "binding_checked": true and script_sha256 ce1ffe39....
4. Minor, for the report: if the rule ever applies, the motivating tasks' oracle reach (descriptive) stays as the
   kernel scored it with Python equality; only the excluded tasks' reach is recomputed.
