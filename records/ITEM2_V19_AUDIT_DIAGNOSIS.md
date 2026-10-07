# Item-2 v1.9: engine acceptance stability audit, development diagnosis

**DIAGNOSIS SUCCEEDED; DOMINANT MECHANISM H1 (re-induction instability),
145 of 145 rejection events.** Development data only (seeds 870,000,000 +
100k), run once on 2026-10-06 under the pre-frozen protocol
`docs/CORA_TTI_ENGINE_STABILITY_AUDIT_v1.9.md` sections 1 to 13 (81065a3,
manifest sha256 de7bca3d).

## Run

- Pipeline `logs/v19/run_audit.sh`, pid 1410140 (own session), 3 workers,
  launched 2026-10-06T21:44:22Z at load 58; phase 1 done 22:20:49Z, phase 2
  done 22:44:14Z, analysis exit 0. Launch record `logs/v19/audit_launch.json`.
- Corpus: 60 tasks requested, 54 qualified within the 2,000-seed limit (seeds
  870003200 to 870194700; `outputs/tti/v19_dev_corpus.json`), exclusion
  E_dev = 3,817 + 30 = 3,847 digests (`outputs/tti/v19_dev_exclusion.json`).
- Stop rule met at exactly 30 audited tasks (the first 30 in corpus order,
  all SELECTED and compiled). Two further tasks finished in flight (indices
  30, 31); they are outside the frozen prefix and are not analysed.
- Rows `outputs/tti/v19_dev_rows.jsonl`; phase 2 `outputs/tti/v19_dev_phase2_rows.jsonl`
  (154 jobs: 106 fresh-process repeats, 36 clock runs, 12 identity runs);
  report `outputs/tti/v19_audit_report.json`.

## Categories (protocol section 12)

| category | tasks |
|---|---|
| A: FULL accepted, some same-e FOLD rejected | 15 |
| B: FULL accepted, every same-e FOLD accepted | 12 |
| R: FULL rejected | 3 |

Selection level of e: MDL 26, D 2, VERIFICATION_UNIQUE 2. Families: (1,1)
13, (1,0) 10, (0,1) 6, (0,0,0) 1. All 30 structures are unseen relative to
the v1.8 development structures. 240 runs, 79 rejected.

## Success condition (protocol section 13): PASS

- Rejection events (failed internal leave-one-out folds of rejected runs):
  145. Mechanistic code and reproducing run: 145 (share 1.00 against 0.90).
- Repeat A (same process) and repeat B (fresh process): 106 of 106 runs
  each reproduce acceptance, codes and per-fold codes.
- Decision identity under tracing: 12 of 12 untraced runs equal the traced
  runs in acceptance, program, events and held-out prediction; the engine
  test also passes.
- OTHER_EXPLICIT_REASON: 0. No answer access beyond the synthetic held-out
  pairs, no task, family or seed branch, no generator schema in any engine
  input, no prospective tuning (the 880M range was never generated).

## Codes and mechanisms

| code | events | mechanism |
|---|---|---|
| SLOT_FIT_FAILED:witness | 86 | H1 fitting (permissive fit predicts: 86 of 86) |
| RANKED_BELOW_COMPETITOR | 59 | H1 ranking (permissive fit predicts: 59 of 59) |

H2 0, H3 0, H4 0 (selection quality, section 10: the selected extension
fails the fitter-level proxy on some outer fold in 11 tasks, but no other
verified candidate passes it on every outer fold in any task).

- Fitting: the K*-2 scoped fitter refuses the extension's table inside a
  five-pair re-induction because some key has a single witness among the
  five ("block 1 key 6 witnessed by 1 < 2 demonstrations"); in 82 of the 86
  the re-induction then has no program at all, in 4 a pixel rule.
- Ranking: every one of the 59 competitors is a pixel-rule reduction
  (`neighbor_count` 31, `neighbor_pattern` 28) that is train-perfect on the
  five pairs, carries a learned colour table, and is labelled RELATIONAL
  with 0 value-bound literals and expression size 2, so the canonical
  ranking puts it ahead of the extension (INDUCED_MAP, 2 to 6 value-bound
  literals, size 15 to 19); it mispredicts the held-out pair.
- 141 events sit in six-pair FOLD runs, 4 in seven-pair FULL runs (the
  three R tasks, all RANKED_BELOW_COMPETITOR).

## The same program with seven and with six pairs

55 rejected same-e FOLD runs in category A:
- production bytes identical in 55 of 55 (sha256 per run);
- top level identical in kind: in FULL and in FOLD the extension is the
  only candidate, rank 0, its fit succeeds (seven and six pairs), and only
  phase A of the leave-one-out runs (phase B never applies, phase C is
  never reached);
- the state transition that differs is inside the engine's own
  leave-one-out: with seven pairs every six-pair re-induction fits the
  extension and admits no competitor (7 of 7 pass); with six pairs, one to
  three five-pair re-inductions (two in 39 runs, one in 12, three in 4)
  either refuse its table (a key loses its second witness) or admit a
  train-perfect pixel rule that outranks it.

## Load and budget (protocol section 9)

The first 12 rejected and the first 6 accepted runs repeated under CPU1
(process CPU time; host contention cannot move a deadline) and CPU10 (ten
times the CPU budget; those runs took 100 to 147 s against about 15 s):
decisions changed 0 of 18 and 0 of 18; codes changed 0 and 0. Load is
eliminated as the primary hypothesis, and budget is eliminated for these
runs: the rejections are deterministic in the demonstrations.

## Descriptive splits

| split | tasks | same-e folds rejected | FULL rejected |
|---|---|---|---|
| level MDL | 26 | 69 of 182 | 3 |
| level D | 2 | 4 of 14 | 0 |
| level VERIFICATION_UNIQUE | 2 | 3 of 14 | 0 |
| family (1,1) | 13 | 39 of 91 | 2 |
| family (1,0) | 10 | 24 of 70 | 1 |
| family (0,1) | 6 | 10 of 42 | 0 |
| family (0,0,0) | 1 | 3 of 7 | 0 |

## Projection used to choose the repair (descriptive, development)

Rejected runs by the kinds of their failed folds: fitting only 38, ranking
only 38, both 3. Tasks whose FULL run and every same-e fold would be
accepted if each kind were repaired (assuming a repaired fold passes, as
its permissive fit predicts): neither 12 of 30, fitting only 21, ranking
only 19, both 30. Each kind alone leaves about a third of the tasks
unstable; the repair must address H1 as one rule. The repair's measured
effect is in its own development ablation, not in this projection.

## What this diagnosis does and does not establish

- Established on development data: why the same compiled extension is
  accepted with seven pairs and rejected with six. The engine's own
  leave-one-out re-induction applies two heuristics designed for native
  hypotheses, a pre-emptive single-witness refusal and a parameter-class
  ranking that does not price pixel-rule tables, and each displaces an
  extension whose fold-fitted semantics reproduce the held-out pair.
- Not established: that repairing them yields end-to-end witnesses
  (measured next, on development data, then prospectively on new data).
- Nothing here touches real ARC data, Step B, the protected holdout, VDCG,
  E_transfer or the lockbox. v1.8 is untouched.

## Addendum (2026-10-06, after the false-acceptance measurements)

- The H1/H2 split of the 86 fitting events depends on the identification
  standard frozen in protocol section 6 (one consistent witness suffices).
  Under the scoped fitter's own two-witness standard, a key seen once among
  the five pairs of a re-induction is not identified, and those 86 events
  would be H2. The 59 ranking events are H1 under either standard (the
  extension fits under the fitter's own rules; a pixel rule outranks it).
- Supplementary development measurements (protocol section 15a): with seven
  demonstrations no wrong verified extension exists on these 30 tasks; with
  four, the engine's own leave-one-out gate does not discriminate right
  from wrong installed extensions in any logic (K* accepts 8 of 24 right and
  6 of 19 wrong; K*' 24 of 24 and 19 of 19; each clause alone raises both).
  The old rejections diagnosed here were therefore indiscriminate: they cost
  recall and bought no measured safety against wrong extensions. They are
  still the rejections that blocked v1.8.
