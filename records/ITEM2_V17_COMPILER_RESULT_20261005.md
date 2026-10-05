# Item-2 v1.7: compiler acceptance result

**COMPILER_ACCEPTED** (S1 to S6 all hold), run once on 2026-10-05.

The result is an engineering capability, not a reasoning claim: an
oracle-selected constructive extension is compiled into a canonical
production that runs inside the real ARC engine, is necessary there and is
credited by exact attribution. The claim stays LEVEL 1 (from v1.6, hybrid).

## Identities

| object | value |
|---|---|
| frozen commit (re-freeze after erratum 01) | 4a9f7fa |
| manifest | `outputs/tti/constructive_extension_compiler_v17_manifest.json`, sha256 `a66e149cf7d971ae4166033c95cfe2567a9be5ea160c792b9abecca9d08b1f29` |
| protocol | `docs/CORA_TTI_CONSTRUCTIVE_EXTENSION_COMPILER_v1.7.md`, sha256 `e9bb1acc1f3547e692f3586e96b5969e9e2782a8db97dfe5f4589cce1b886d32` |
| compiler | `cora_arc2026/v17_compiler.py`, sha256 `04c6b3a19b9645cdfd983e2733e377b8b342e11a4c09b209f3dddb5868515152` |
| K* identity | `b009a9fb13402348a73c3e1ef187a82c2d42fb5175e5fed806e8d33d6b73e729` |
| report | `outputs/tti/v17_acceptance_report.json`, rows `outputs/tti/v17_acceptance_rows.jsonl` |
| first freeze, review, erratum | d5b5e1b (manifest 418ee5c2); `records/ITEM2_V17_REVIEW_RESULT.md` (9195641); `records/ITEM2_V17_ERRATUM_01.md` (6fc3a4d) |

## Run

- Launched once by `scripts/run_v17_acceptance.sh` at 2026-10-05T20:26:54Z,
  pid 3231530, one process at default priority. 882.9 s.
- Environment: PYTHONHASHSEED=0, hash randomization off, no ARC_* variable
  at start or end.
- Load average 40.1 at start, 42.4 at end, on 24 CPUs. Step B's 20 workers
  were running throughout and were not touched.
- No unexpected exception. No fixture shortfall: the first 6 qualifying
  seeds were found among the first 96 candidates.

## Per task

All six tasks are two-block. Families (0,1) and (0,0,0) did not occur
among the first six.

| seed | family | verdict | K* + {e} s | K* s | held-out exact | K* at 3x: accepted (s) | leave-one-out folds |
|---|---|---|---|---|---|---|---|
| 830000600 | (1,0) | EXTENSION_NECESSARY_AND_USED | 15.6 | 9.4 | yes | no (24.1) | 3 of 7 |
| 830001800 | (1,1) | EXTENSION_NECESSARY_AND_USED | 15.6 | 8.1 | yes | no (24.1) | 7 of 7 |
| 830002600 | (1,0) | EXTENSION_NECESSARY_AND_USED | 15.6 | 8.1 | yes | no (24.1) | 7 of 7 |
| 830008000 | (0,0) | EXTENSION_NECESSARY_AND_USED | 15.5 | 8.1 | yes | no (24.1) | 7 of 7 |
| 830008300 | (1,1) | EXTENSION_NECESSARY_AND_USED | 14.4 | 8.0 | yes | no (9.6) | 7 of 7 |
| 830009500 | (0,0) | EXTENSION_NECESSARY_AND_USED | 15.5 | 8.1 | yes | no (24.1) | 7 of 7 |

## Conditions

| condition | result |
|---|---|
| S1 compile, deterministic bytes, identical reload, fresh process (task 1) | all 6 |
| S2 no restoration failure, final snapshot equals initial | yes |
| S3 residue, direct-execution disagreements, label anomalies | 0, 0, 0 |
| S4 EXTENSION_NECESSARY_AND_USED with held-out exact (>= 5) | 6 of 6 |
| S5 adaptive leave-one-out (>= 5) | 5 of 6 |
| S6 witness SEPARATED on every task | 6 of 6, every comparison set empty |

Supplementary, not gating:
- K* at 3x budget (24 s) accepted none of the six, so necessity survived
  a generous baseline on every task. The 3x arm on seed 830008300 stopped
  at 9.6 s without a solution.
- Nested uses: 0.
- Engine directories: all removed.

## What fell short, and why

**S5 on seed 830000600.** The engine accepted nothing on 4 of the 7
six-pair folds (folds 0, 1, 3 and 6). No winner was produced, so there is no
misattribution. In the 3 accepted folds e won and direct execution agreed.
- Likely mechanism: the engine's re-induction gate refits inside each fold,
  so a six-pair fold is checked by five-pair refits. That is stricter than
  the filter's single leave-one-out with the scoped fitter, and keys seen
  in few demonstrations fail it. Development seed 800000000 failed the
  gate the same way with keys witnessed by only two demonstrations.
- This mechanism is not verified on this task: fold events were not
  recorded.

**S6 is weak evidence here.** All six comparison sets were empty (no K
single-block schema admitted even a loose fit), as protocol section 12
predicted. S6 therefore shows only that the compiled bodies kept their
multi-block semantics under the frozen fitter, not a probe-level
separation.

## Independent verification

`logs/v17/verify_acceptance.py` (output `logs/v17/verify_acceptance.log`)
was run after the marker. All 11 checks pass:
- the freeze is intact after the run;
- the rows file equals the report's tasks;
- the manifest hash in the report is the frozen one;
- the start and end environments are K*'s;
- S1 to S6, the outcome and the 3x count are recomputed identically by
  separate code (S4 on 6 tasks, S5 on 5);
- no restoration error rows; all engine directories removed;
- the fixture selection, re-derived under PYTHONHASHSEED=0, gives the same
  seeds and families, and the compiled production names are identical.

## What this does and does not show

It shows:
- oracle-selected two-block constructive extensions compile to canonical,
  content-named productions;
- they run inside the unchanged engine through its ordinary fitting,
  rendering, verification and leave-one-out gate;
- they are necessary there at equal budget and against a 3x baseline;
- attribution is exact under the checks of section 14;
- installation leaves no residue in the snapshot.

It does not show:
- any reasoning or invention: the extension is given by the oracle pair;
- out-of-sample prediction beyond S4's one held-out pair per task
  (protocol section 10: S5 tests the machinery at this stage);
- necessity under K: e also uses K*-1's expression slice and K*-2's fitter;
- probe-level separation from K (S6 comparison sets were empty);
- anything about ARC tasks: these are synthetic constructive tasks, all
  two-block, from four of the five families;
- robustness to load: one run at load 40 to 43 on 24 CPUs.

## Next

NEXT: DESIGN AND FREEZE THE NO-ORACLE EXTENSION PROPOSER. Not begun in this
block.
