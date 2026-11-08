# Addendum 1 to the pre-registration of the construction test at scale

Written on 6 November 2026, after revision 4 was frozen and reviewed and before any GO. No main task has been
generated and no method has run on any pilot or main task. This addendum changes no frozen byte: `PROTOCOL.md`
(sha256 01d12e10fd512c832296093a5d3b5e4ebd61dc3a4b207278d76259759c920ee0), `FREEZE.json` (sha256
b17f28d025a81c18f0578b1076e6ea72f73a58ea62af82295ce7397b4bdc9cd8) and every file `FREEZE.json` lists stay as they
are. It answers findings 1 to 3 of the independent pre-run review of revision 4
(`reviews/INDEPENDENT_PRE_RUN_REVIEW_REVISION_4.md`) by the routes that need no new frozen bytes, and lists that
review's wording slips (its finding 4) and notes for the report.

Terms as in `PROTOCOL.md`: S1 is the original test this study scales up; S-hole is growth of a new operation from a
typed hole; C7m is the matched static program search over the base grammar G0 (A2's arc-dsl grammar without the
world's removed operations); W1, W2 and W3 are the three worlds; INCOMPLETE and INVALID are the analysis's two
refusal labels (something missing; something malformed or inconsistent). Section and line numbers refer to
`PROTOCOL.md` unless they name this addendum.

## Binding

The coordinator's one-use GO file, `GO_CAS`, has three lines:

    protocol_sha256 01d12e10fd512c832296093a5d3b5e4ebd61dc3a4b207278d76259759c920ee0
    freeze_sha256 b17f28d025a81c18f0578b1076e6ea72f73a58ea62af82295ce7397b4bdc9cd8
    addendum_1_sha256 <sha256 of this file, ADDENDUM_1.md>

The gate (`cas/gate.py`) checks the first two lines against the live files. The claim it writes at generation
(`runs/RUN_CLAIM.json`) records the sha256 of all of the GO's bytes, and every later stage requires that claim, so
this addendum is fixed from the claim on. This file fixes the recomputation script in turn:

    addendum_1_recompute.py sha256 ce1ffe392e3df06077d25f7be345ea11ebd06a168fc514db3a3b7c3ca783c4cd

In phase 2 the script runs only if the gate's analyse stage passes, the GO's third line names the live digest of
this file, and this file names the script's live digest. Neither file is listed in `FREEZE.json` or packed into the
kernels; the script runs on this machine after the kernels, as the analysis does.

## 1. Committed predictions with a cell outside 0 to 9

**The problem.** The strict verification requires every cell of every committed grid to be an integer from 0 to 9
(`cas/analysis.py` lines 102 to 105). A record that fails it is malformed, so the study would be INVALID before any
statistic, and final under section 11. The search that writes these grids does not guarantee the range: A2's value
check (`experiments/architecture_sweep_20261026/a2/arcdsl.py` lines 146 to 159) checks a grid's size, its
rectangular shape and the type of its first cell only, and G0 holds the constants TEN, NEG_ONE and NEG_TWO and
integer arithmetic. A program can therefore fit every demonstration and still put 10, -1 or -2 in a query's
prediction, or True, which Python's equality treats as 1. Such a prediction is a legitimate wrong answer, not a
defect of the outputs, and one of them among the several thousand committed predictions of phase 2 would end the
study.

**The rule.** A committed prediction (one attempt: one grid for each query input) with a cell that is not an integer
from 0 to 9 is scored as incorrect, whatever Python's equality gives: a cell holding True, or 1.0, where the output
has 1 is incorrect. The other prediction of the same unit, matched search or grown-grammar search is scored as
before, so a unit with one such prediction and one correct prediction is still correct.

**When it applies.** If the frozen analysis returns INVALID solely for that reason, the recomputation script
produces the reported analysis. "Solely for that reason" is decided by running the frozen strict verification
(`verify_complete`, unchanged) twice: as frozen, and with its grid check reduced to the shape (a non-empty
rectangular list of non-empty lists, any cell values), everything else identical. The rule applies when the frozen
run has problems, the reduced run has none, and at least one committed prediction holds such a cell. Problems that
follow from the cell check alone (for example a promoted structure that the frozen check stops counting once its
record fails) vanish with it and are covered. The script then re-scores in memory every endpoint that rests on such
a prediction, by the frozen re-scoring rule (`_rescore`: at most two predictions, `cgrow/evaluate.py`'s `correct`,
the matched search's failure flag, the grown search's fit) with that prediction counted incorrect, and runs the
frozen analysis code (`cas/analysis.main`, unchanged) on the worlds so verified and corrected. Its
`runs/analysis_addendum_1/ANALYSIS.json` is then the reported analysis, decision included, and the report lists
every prediction outside the range and every endpoint the rule changed.

**Any other INVALID stands.** When the reduced verification still has any problem, the frozen INVALID or
INCOMPLETE is the result and the script computes nothing; the operator-error correction of this addendum's
section 3 is the only other route.

**Unchanged.** The decision rule, the statistics, every custody check, and the scoring of every prediction whose
cells are integers from 0 to 9. A passing frozen verification means that no committed prediction holds such a
cell; the frozen `runs/analysis/ANALYSIS.json` is then the reported analysis and this section has no effect.

## 2. The failure status of the matched searches

**The problem.** Beside the decision, the analysis reports the primary recomputed without the tasks whose matched
search failed (section 6, descriptive). It reads each search's failure flag from the results file
(`cas/analysis.py` lines 603 and 658), and no check compares that flag with the commitment; the per-world failure
counts (lines 712 to 713) read it too. A wrong flag in the results would change these descriptive outputs
undetected. The decision is not affected, since the matched search's endpoint is re-derived from the commitment's
predictions and failure flag (lines 242 to 250).

**The rule.** The recomputation script derives each matched search's failure status from the commit-stage record
(`runs/cas_commit/COMMITTED_PREDICTIONS.json`, the field "failed") and checks it against the matched-search stages'
own records:
- the stage result files `runs/cas_c7m/c7m_M.json` and `c7m_E.json`: each search's final record, after the rerun
  stage, is a failure when it timed out, its child failed or it was stopped by memory (the rule the commit stage
  applies, `cas/run_world.py` lines 451 to 460);
- the kernel log `runs/kaggle_main.log`: the last line each search's stage printed. A finished search always prints
  a stop reason and a failed one prints none, so that line decides; a rerun's line prints no stop reason and
  decides nothing.

The descriptive "primary without failed matched searches" and the failure counts are computed by the script from
that status, with the frozen statistics code (`contrast`) on the same rows, and are reported from its record
`runs/analysis_addendum_1/ADDENDUM_1_RECOMPUTATION.json` only, never from the fields of the same meaning in
`ANALYSIS.json`. If these sources disagree for any search, both outputs are reported as unavailable, with the
disagreements listed. Every mismatch between this status and the results' own flags is listed in the report. The
decision-bearing primary is unaffected, and so are the study's status and every other output.

## 3. Operator errors

**The problem.** Section 11, step 5, allows one correction of "an INCOMPLETE caused only by an argument or placement
error". But the analysis labels the study INVALID whenever any of its problems is INVALID, and a placement error
produces INVALID problems too: a world folder under another world's name, or the wrong downloaded archive, gives
endpoints that differ from the re-scored commitment, missing rows and the like. Read literally, that INVALID would
be final although the kernel outputs are intact.

**The rule.** The one-time correction covers an INCOMPLETE or an INVALID caused only by operator error, that is an
argument or placement error such as a world folder under the wrong name, the wrong downloaded archive, or the wrong
folder given to the analysis. Operator error is shown by the archive and output-manifest digests:
- each world's outputs, as placed after the correction, come from the archive whose sha256 equals the digest its own
  kernel's notebook printed (recorded beside the downloaded archive, section 11, step 4), and the archive's top
  folder (`<world>/runs`) names the world folder they are placed in;
- after the correction, each world's `runs/OUTPUT_MANIFEST.json` verifies (every file under `runs/` has its recorded
  digest, and no other file is there), and its `runs/STAGES.json` names that world and the package's digest;
- the problems the first analysis reported are explained by the error (for example, the folder held another
  world's outputs, or an archive other than the one its kernel printed).

The correction is made once, logged in `PROGRESS.md` with the digests and the reason, and the analysis and this
addendum's recomputation are run again; that result stands. Any other INVALID is final, and so is any INCOMPLETE
about the kernel outputs themselves (section 11, step 5). The report says that the label alone does not separate
missing from malformed work.

## 4. For the report

**Wording slips in the frozen protocol** (the review's finding 4), stated correctly in the report:

- (a) Line 433: the plumbing check was re-run with revision 4's code (`launch/run_rev4_runs.sh`), not revision 3's.
- (b) Lines 461 to 463: the peak virtual memory was converted from kB by dividing by 10^6 and then compared with
  limits in GiB. The matched-search smoke's peak of 6,359,552 kB is 6.06 GiB of its 8 GiB limit, a headroom of 1.94
  GiB (not 1.64); the rerun smoke's 6,262,652 kB is 5.97 GiB of its 20 GiB limit; the "6.4 GB" of line 463 is
  6.1 GiB.
- (c) Line 288: the generator dry run asserted rule 6 in full (no source of a motivating task of one world is the
  source of any task of another world), not only between motivating tasks.
- (d) Section 10, route step 4 (lines 658 to 667): the kernel's stage list omits the rerun stage, which runs between
  the remaining matched searches and the commit (every matched search stopped by memory runs once more, alone, at
  20 GB; `cas/kaggle_main.py`).
- (e) Rule 6 (line 260) cites "section 11, step 5" for its verification; the verification is listed in section 10,
  route step 5 (and run by section 11, step 5). The change log's references of the same form (lines 868, 902 and
  928) read likewise.
- (f) Lines 422 to 423 ("Every child records its peak virtual memory"): a child killed by the operating system leaves
  no record of its own; its result is the parent's child-failed record with the return code and no peak.

**Also in the report** (the review's notes):

- A2's search catches every exception inside its primitive calls, MemoryError included
  (`experiments/architecture_sweep_20261026/a2/bus.py` lines 239 to 252), so a search near its memory limit
  can skip candidates and still end on its CPU cap as an ordinary search, which is not rerun. The report lists
  every matched search that stopped on its CPU cap with a peak virtual memory above 90% of its limit (from the
  script's record).
- A controller decision changed consistently in both kernel outputs that hold it (the controller summary and the
  results) cannot be detected: both are written from one record, and no hashed input holds the decision. The report
  gives the controller's exclusions with the primary's denominator.
- The gate's check that every world was built after the claim needs the claim's time ("claimed_utc", `cas/gate.py`
  line 118). The gate always writes it; the report states the committed claim's time.
- The status label alone does not separate missing from malformed work (this addendum's section 3).

## 5. Phase 2 with this addendum

The procedure of `PROTOCOL.md` section 11 and of `PROGRESS.md` is unchanged, with two additions: the GO's third line
(above), and, right after the frozen analysis of section 11, step 5, from this folder:

    PYTHONHASHSEED=0 sh ../../scripts/with_cpu_slot.sh python3 addendum_1_recompute.py \
        runs/analysis_addendum_1 runs/generated/W1 runs/generated/W2 runs/generated/W3

with the same world folders in the same order as the frozen analysis. The script first checks the binding, then
that its own run of the frozen verification agrees with the frozen analysis's latest output in `runs/analysis` (the
same status and problems, or a written `ANALYSIS.json`), and stops otherwise. It always writes
`runs/analysis_addendum_1/ADDENDUM_1_RECOMPUTATION.json`, and writes `runs/analysis_addendum_1/ANALYSIS.json` only
when this addendum's section 1 applies. The report takes the decision from the frozen
`runs/analysis/ANALYSIS.json`, or from the script's `ANALYSIS.json` when this addendum's section 1 applies, and the
descriptive outputs of this addendum's sections 2 and 4 from the script's record. The independent recomputation of
section 11, step 5, checks both.

## 6. Test (phase 1, after the freeze)

The script's self-test (`python addendum_1_recompute.py --self-test SCRATCH OUT.json`) ran on 6 November 2026 in
scratch mirrors of S1's own world, that is the original test's tasks and run records (the mirror builder of
`checks/strict_fixture.py`, with CAS_PACKAGE=1, so nothing is written in the real study; no method runs and no pilot
or main task is read). Each case runs the frozen analysis and then the script in test mode, which skips only the
binding check, there being no GO. In every case the script's own run of the frozen verification agreed with the
frozen analysis's output. Record: `checks/ADDENDUM_1_SELF_TEST.json` (for the script digest above); all 11 cases as
expected:

1. S1's world as recorded: the frozen analysis is written; the script agrees, and its primary without failed
   matched searches equals the frozen one (11 tasks, none excluded).
2. A matched search's wrong first attempt made out of range (every cell 10) beside its correct second attempt: the
   frozen analysis returns INVALID ("committed matched search ... malformed"); the colour rule applies and changes no
   endpoint (the search is still correct), and the analysis it writes is identical to the frozen analysis of case 1.
3. A matched search's two correct attempts replaced by out-of-range grids, the endpoint recorded as the scoring gives
   it (wrong): INVALID; the colour rule applies, and its analysis is identical to the frozen analysis of case 4.
4. Control for case 3: the same attempts replaced by wrong grids with cells 0 to 9: the frozen analysis is written.
5. One cell of a unit's only correct attempt set to True or False, which Python's equality still scores correct:
   INVALID; the colour rule applies and changes exactly that endpoint to incorrect, and its analysis is identical to
   the frozen analysis of case 6.
6. Control for case 5: that attempt replaced by a wrong grid with cells 0 to 9, the endpoint recorded wrong: the
   frozen analysis is written.
7. The results' failure flag set on a motivating task whose matched search did not fail: the frozen analysis is
   written and reports its primary without failed searches over 10 tasks with 1 excluded; the script lists the
   mismatch and reports 11 tasks with none excluded, as in case 1.
8. An out-of-range grid together with another defect (an excluded task's matched search without its failure flag):
   INVALID, and it stands; the script writes no analysis.
9. The stage result file says "timed out" where the commit says the search did not fail: the disagreement is
   listed, and the descriptive output is reported as unavailable.
10. A kernel log consistent with the records (with noise lines and one rerun line): no disagreement; the log decides
    every search except the rerun one; the descriptive output equals case 1's.
11. A kernel log whose line says a search failed where the commit says it did not: the disagreement is listed, and
    the descriptive output is unavailable.
