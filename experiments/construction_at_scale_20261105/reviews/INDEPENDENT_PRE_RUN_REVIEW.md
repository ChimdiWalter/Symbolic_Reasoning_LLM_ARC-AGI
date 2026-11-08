# Independent pre-run review of the construction test at scale (revision 1)

Review commissioned by the coordinator, 5 Nov 2026 (completed about 22:00Z). Object reviewed: the pre-registration
frozen in commit 6b5fb6f8, folder `experiments/construction_at_scale_20261105/`. Every statement below about code
cites the line numbers of that commit. The reviewer did not design the study.

**Verdict: HOLD.** The freeze itself is sound and the two hashes verify, but revision 1 cannot be the object of the
GO: (a) its primary outcome measure is not matched between the two arms (finding 1), the reuse and transfer
secondaries are not matched (finding 2), the CPU accounting leaves out part of growth's cost (finding 3) and the
executable configuration disagrees with the pre-registered salt (finding 4); (b) the working tree already carries
an uncommitted "revision 2" that rewrites the protocol and six code files to answer those four points, so the live
`PROTOCOL.md` no longer hashes to the frozen value. Revision 2 must be frozen, committed and given its own
exact-byte review before any GO. Section 9 lists what that review must check and which of this review's results
carry over unchanged. Findings 5 to 8 are new in this review and are not addressed by revision 2 as it stands;
finding 5 should be fixed before the GO.

Labels used below. S1 is the original construction test (`experiments/capability_growth_20261027/`); Test I-b is
the earlier neural test from which S1 took its matched-search budget. A2 is the project's bottom-up program search
over arc-dsl. G0 is the starting language (A2's grammar minus the removed operations). The three worlds are W1
(S1's four operations), W2 (the quarter turns and diagonal reflections) and W3 (the stretches and the colour
exchange). The five methods are S-hole (growth from
CORA's own typed holes), S-demo (the identity hole only), S-shuffled (another task's holes), S-enum (blind
enumeration of the structure space) and C7m (matched static search over G0 alone). A "motivating task" is a task on
which the controller decides to construct a new operation. "Reach" is the revision 1 outcome rule: any retried
candidate's prediction correct. "Committed outputs" is the revision 2 rule: at most two predictions per query.

## 1. Hashes and freeze integrity (verified)

| check | result |
|---|---|
| sha256 of `PROTOCOL.md` at commit 6b5fb6f8 | b3759bfca67aecc6db51b6c6a8a280be9bc7ce828c01e336772acc3e319af7c6 (as stated) |
| sha256 of `FREEZE.json` at commit 6b5fb6f8 | 260ee7533e5ce50ca754dc1f72481bcdbe9a8bba700b159b58b3fff2540cf3b8 (as stated) |
| `FREEZE.json` `protocol_sha256` field | equals the `PROTOCOL.md` digest |
| 74 study files in `files_sha256` | all equal to the committed bytes (`git archive 6b5fb6f8`, re-hashed) |
| 44 dependencies in `dependencies_sha256` | 37 equal to the committed bytes; 7 are not tracked in git (`a2/out/corpus.json`, `a2/out/traces.jsonl`, the five arc-dsl files) and equal the live bytes |
| 2 training data files in `data_sha256` | equal to the live bytes |
| live working tree at review time | `PROTOCOL.md` hashes to 9b6f66b9…; `cas/analysis.py`, `cas/equivalence.py`, `cas/freeze.py`, `cas/kaggle_main.py`, `cas/power.py`, `cas/run_world.py` differ from the freeze; `checks/EQUIVALENCE.json` and `checks/ANALYSIS.json` are deleted (`git status`: the uncommitted revision 2; `PROTOCOL_REVISION_1.md` and `FREEZE_REVISION_1.json` hold revision 1 byte for byte) |

**The gate** (`cas/gate.py`, unchanged in revision 2) was exercised on a scratch copy of the committed tree with
`CAS_STUDY` pointing at the copy (the real folder was never touched; no `GO_CAS` or `runs/` exists there):

| step | outcome |
|---|---|
| no GO file, stage generate | `FAIL generate: no GO_CAS` |
| GO present, stage package before any generation | refused (no claim, no task set) |
| GO present, stage generate, first use | `ok generate`, writes `runs/RUN_CLAIM.json` with the GO's sha256 |
| stage generate, second use | `FAIL generate: the GO was already used (runs/RUN_CLAIM.json exists)` |
| stage analyse, same GO | ok |
| one line appended to the GO | `FAIL analyse: RUN_CLAIM.json names other GO bytes` |
| wrong freeze line in the GO | `FAIL analyse: GO_CAS does not bind the live PROTOCOL.md and FREEZE.json` |
| one byte appended to `cas/analysis.py` | `FAIL analyse: frozen file changed or missing: cas/analysis.py` |

So the gate refuses without the GO, binds the GO to the live protocol and freeze bytes, re-checks every digest, and
enforces one use through the claim file (`cas/gate.py` lines 44 to 51, 55 to 64, 69 to 70, 96). Two limits, stated
for the record: the claim file is the only token of use (deleting it would allow a second generation; see finding
12), and the gate is not invoked by the kernels or by `run_world.py`; the package stage is what fixes the task set
before any method runs.

## 2. Pre-registration integrity (verified)

- **No main task exists.** `runs/` and `GO_CAS` are absent from the study folder. The only task files are the
  pilot's (`pilot/`, `pilot_v1_superseded/`, `pilot_v2_superseded/`) and the generator dry run's
  (`checks/generator_dry_run_pilot/`); all 197 source entries of those sets (33, 42, 42 and 80; a source may recur
  across sets) are pilot-pool ids, none is a main-pool id and none is one of S1's 61 sources. The dry-run manifests' digests equal the FREEZE entries.
- **Pools.** `config/POOLS.json`: pilot 100, main 535, disjoint; the sorted lists hash to the two values printed in
  the protocol (d321d802…, a740f6a3…). Recomputed from the split manifest: the 696 S_train and S_select ids minus
  S1's 61 distinct sources (recomputed from S1's `evaluator_only/TASKS_EVAL.json`, equal to the excluded list)
  give 635 candidates; the first 100 in sha256("cas-pools-20261105|" + id) order are exactly the pilot pool.
- **The evaluation set is never read.** The 120 `ARC_eval_dev` ids overlap neither pool nor the training splits.
  All 635 pool ids are keys of `arc-agi_training_challenges.json`. In the code, the only evaluation reference is
  `cas/pools.py` line 28, which reads the id list from the split manifest to assert the overlap is zero; the loader
  (`harness/data.py`) opens the evaluation file only for the split name `ARC_eval_dev`, which no study code passes.
  `grep` over `cas/`, `cgrow/` and the harness finds no other path to evaluation data.
- **Real previously solved tasks.** 15 training tasks were solved by A2; 0 are in the pilot pool, 8 in the main
  pool, 7 among S1's excluded tasks, consistent with the protocol's dry-run note.

## 3. Boundary compliance (verified)

- No family selects an object by an attribute: the 11 removed operations (compress, downscale, trim, upscale;
  dmirror, cmirror, rot90, rot270; hupscale, vupscale, switch) are whole-grid operations, and the composite
  operations A and B come from the kept unary list (`cas/generate.py` lines 45, 84). In the dry run every A or B is
  one of hmirror, vmirror, rot180, the four halves, compress, trim (W2) or the full list (W1, W3).
- hmirror, vmirror and rot180 are in no removed set (`config/STUDY_CONFIG.json` lines 12 to 17, 52 to 57, 83 to 87);
  `build_g0` removes only the listed names (`cgrow/lang0.py` lines 37 to 46).
- Nothing in `cas/` or the launch scripts reads `<companion study folder>`, ConceptARC, Mini-ARC or 1D-ARC;
  the only mentions are the boundary rules in the protocol, the configuration and the progress log.

## 4. Fairness of the arms

**Finding 1 (high). The primary compares growth's reach with matched search's two predictions.**
`cas/run_world.py` line 232: a growth unit is "recovered" when *any* retried candidate fits the demonstrations and
its two-prediction query answer is right (`any(row.get("fit") and EV.correct(...) for row in r["rows"])`), over up
to three retries (`cgrow/s1.py` lines 222 to 225), so up to six query predictions; C7m is scored on the two
predictions of one search (`cas/run_world.py` line 180). `PROTOCOL.md` lines 65 to 66 define "recovered" this way.
In S1's own record this did not matter: no unit held more than one fitting candidate (verified over all 165 S1
units), which is also why the equivalence check reproduces S1. At scale it can matter wherever two structures fit
the demonstrations (for example in W2, where the four removed symmetries compose into one another). Fix: score every
method on at most two predictions chosen by a label-blind rule (revision 2's "committed outputs": the promoted
structure's retry, else the first quarantined one, `run_world.committed_outputs` in the working tree does this) and
keep reach as a descriptive count. Revision 2 addresses this; its rule must be checked to be label-blind (it is: it
uses only promotion status and candidate order) and its equivalence record must still reproduce S1.

**Finding 2 (medium). Reuse and transfer union over promoted structures.** `cas/analysis.py` lines 93 to 98: an
excluded task counts for S-hole if *any* promoted structure of the family (tried alone, each with two predictions)
solves it, against C7m's two predictions. Fix: one base search with G0 plus all promoted structures of the family,
two predictions (revision 2's `grown_search` does this).

**Finding 3 (medium). Growth's charged CPU omits the diagnosis and the specification enumeration, and C7m's
budget is not what "matched" suggests.** A unit's `cpu_s` (`cgrow/s1.py` line 242) sums gate charges only; the
controller's analysis (about 5 CPU-s per task in the pilot) and `spec_candidates` are not charged. C7m gets 150
reference CPU-s per task (`cas/run_world.py` line 157), which S1 inherited from Test I-b; S1's S-hole units charged
9.6 CPU-s on average (maximum 17.5), so matched search has roughly ten times growth's CPU. That is conservative for
the "S-hole beats matched search" outcome and not for the reversed or refuted outcomes, and the protocol does not
say so. Fix: charge diagnosis plus enumeration plus gates, report actual CPU separately, state the ratio in the
protocol, and give C7m at least growth's complete charged total (revision 2 does all three; its rule
`c7m_budget` compares machine seconds with machine seconds, which is right).

**Finding 4 (medium). The W2 generator salt is pre-registered as `cas-W2-20261105` but the executable
configuration uses `cas-W2b-20261105`.** `PROTOCOL.md` line 254 and `FREEZE.json` line 140 (written from
`cas/freeze.py` line 40) say `cas-W2-20261105`; `config/STUDY_CONFIG.json` line 78, `checks/DRY_RUN_CONFIG.json`
line 78 and the dry-run manifest `checks/generator_dry_run_pilot/W2/partitions/PARTITIONS_MANIFEST.json` line 79
say `cas-W2b-20261105`, and `cas/generate.py` line 82 reads the configuration. The main build would therefore use a
salt the pre-registration does not name. Fix: name `cas-W2b-20261105` in the protocol and in `freeze.py`, re-freeze
(revision 2 does this).

**Finding 5 (medium, new, not in revision 2). The machine factor is measured by a lone benchmark but applied to
CPU-time stops that run under concurrency.** `cas/kaggle_main.py` lines 61 to 70 run `cas/bench.py` once, alone,
before the stages; lines 71 to 75 then run the specification process beside two matched-search children (three
CPU-bound processes), and three S-enum seeds in parallel. Revision 2's plan runs four processes at a time. Kaggle's
CPU kernels offer four virtual processors, which on the usual cloud machines are two physical cores with two
hardware threads each, so each process gets markedly fewer executions per CPU-second than the lone benchmark
measured. The two stops scaled by the factor are C7m's 150 s and S-enum's 60 s
(`cas/run_world.py` lines 133, 157); the specification methods stop on execution counts. The error therefore
shortens only the comparator and the blind-enumeration control, never S-hole: it is anti-conservative for the
primary. The S1 replay that produced the 1.40 factor ran matched search sequentially (its summary shows wall time
equal to CPU time), so it gives no evidence about the concurrent case. S1's own matched searches on Athe reached
113,000 to 354,000 executions per CPU-second and stopped on the cap on 10 of 11 tasks at cost levels 13 to 16, where
the known G0 routes sit (levels 10 to 14), so a 30 percent loss of executions can change C7m outcomes on the route
families. Fix, before the GO, one of: (a) run the benchmark with the same number of concurrent copies as the
busiest stage (four) and take the median per-process time as the factor; or (b) stop C7m and S-enum on execution
counts fixed from S1's record (the executions S1's matched search reached in 150 s on Athe, median over the capped
tasks), keeping the CPU cap only as a safety limit; and in either case report executions per CPU-second achieved
by every C7m task (already recorded as `calls` and `cpu_s`) against the benchmark. The clip to [1, 2] (`cas/bench.py`
line 40) is also one-sided: a faster machine gives the search methods more executions than the reference, a machine
slower than twice Athe gives them fewer; state this in section 10.

**Stop rules.** Every stop is CPU time or a count: `a2/bus.py` lines 143 and 232 measure `time.process_time()`;
`cas/kaggle_main.py` line 80 caps on children's CPU time; the only wall-clock quantities are logged, never used.

## 5. Power (verified)

- The `simulate` and `cluster_ci` functions of the committed `cas/power.py` were copied verbatim and re-run with
  the frozen seeds (F = 11 families, m = 9 motivating-task slots per family, 4,000 simulated studies, 2,000
  bootstrap draws each): scenario A 0.970 positive, 0.018 refuted,
  0.013 inconclusive; scenario B 0.300, 0.073, 0.626; scenario N 0.019 positive, 0.939 refuted, 0.028 inconclusive.
  All equal the frozen file and the protocol's table.
- An independent implementation (vectorised, different seeds, numpy's quantile rule) gives A 0.969 / 0.021 / 0.010,
  B 0.300 / 0.068 / 0.630, N 0.015 / 0.940 / 0.032: the same within Monte Carlo error.
- The per-family inputs equal S1's record: compress +0.667, downscale +0.667, upscale 0, trim -0.5 (mean paired
  difference per family), pooled 3/11. Scenario B resamples these four family types with replacement; it is a
  reasonable sensitivity model given that only four families exist, and it is honest about its consequence (power
  near 0.30 under that much heterogeneity, stated in section 8 of the protocol). Scenario N exchanges the two
  methods' outcomes within each task, which is the right null for a paired exact test.
- "S1-sized advantage refuted" (family interval's upper end below 3/11 when neither significant outcome holds) is
  conclusive under the null: 0.94 of null studies end there, 0.019 are false positives. Two consequences should be
  read correctly and are implied by the pre-registered text: a significant but small advantage (McNemar p < 0.05,
  interval containing 0, upper end below 0.273) is called "refuted", which is consistent with the label's meaning
  (smaller than S1's); and under scenario B the refutation is a wrong call in 7 percent of studies.
- Revision 2 changes the outcome rule; `power/COMMITTED_POLICY_S1_CHECK.json` in the working tree shows the rule
  leaves S1's counts unchanged, which this review confirms independently (no S1 unit had two fitting candidates), so
  the power model carries over.

## 6. Equivalence check (verified on the committed record)

`checks/EQUIVALENCE.json` at commit 6b5fb6f8: controller 38 of 38 decisions and 38 of 38 hole sets identical; the
specification methods 99 of 99 units identical; S-enum seed 0, 10 of 11 promotions identical, the other unit
(t83286f67) stopped on its charged-CPU limit one structure earlier, as the protocol explains; the 10 promoted
structures identical in family, excluded-task fits, kind and contract verdict; primary 8 against 5 of 11,
discordant 4 : 1, p = 0.375, family interval [-0.2, 0.667], decision "inconclusive".

Recomputed here from the committed `checks/ANALYSIS.json` task table with S1's code copied verbatim: McNemar p =
0.375; unit bootstrap (seed 1) [-0.091, 0.636]; family bootstrap (seed 7) [-0.2, 0.667]; an independent family
bootstrap with another seed gives the same interval. The doubled-tail exact McNemar convention
(`cgrow/evaluate.py` lines 96 to 103) coincides with the minimum-likelihood convention for every discordant pair up
to 24, as expected for a symmetric binomial. The Holm step-down in `cas/analysis.py` lines 69 to 75 is correct
(checked on a four-value example). This record was deleted from the working tree by revision 2's re-run; the
revision-2 record must be checked again.

## 7. Expressibility and novelty (verified)

- Every removed operation equals a structure of the schema language at every parameter value used, by the
  membership check on 80 probe grids (`feasibility/W1_s1.json`, `W2_quarter_turn.json`, `W3_stretch_swap.json`):
  compress SEL:multi:multi; downscale SEL:mod:mod, MAP:sample:sample:0, BLOCK:first; trim SEL:inner:inner,
  MAP:core:core:0; upscale MAP:spread:spread:0; dmirror MAP:same:same:1; cmirror MAP:flip:flip:1; rot90
  MAP:same:flip:1; rot270 MAP:flip:same:1; hupscale MAP:same:spread:0; vupscale MAP:spread:same:0; switch
  COLOUR:a:b:1 for all 45 pairs.
- The novelty gate (200,000 executions) completed cost level 9 for every admitted structure without a G0 witness,
  stronger than the "cost 7 or less" claim. G0 sizes 136, 136, 137 as stated. vupscale at k = 2 is reproduced by
  merge(pair(I, I)) at cost 7 and is correctly excluded.
- The five route families are pre-declared with their witnesses and levels (`feasibility/deep_macro_search*.json`:
  trim 10, upscale 12, dmirror 13, vupscale k = 3 at 13, hupscale k = 2 at 14); no route within level 14 for
  compress, downscale, cmirror, rot90, rot270, hupscale k = 3. They are reported per family and do not change the
  analysis; that is adequate because the analysis never excludes them.

**Finding 6 (low). The deep check for switch is confounded.** Its 10 probe grids contain no colour 0, so
`replace(I, ONE, ZERO)` matched at level 5 (the protocol says so, lines 151 to 153). Three nested `replace` calls
through a spare colour would express switch at about level 12, within matched search's reach, so switch may be a
sixth route family. Fix: re-run the evaluator-only deep check for switch on probes that contain both colours
(about 2 x 150 CPU-s) and list the result; no analysis change.

**Finding 7 (low). Reuse for switch needs pre-declaration.** A COLOUR structure carries fixed colours
(`cgrow/schema.py` lines 152 to 156), and switch's colours come from each source, so an excluded task is solvable
by reuse only when its pair was promoted on some motivating task. State in section 7 that switch's reuse and
transfer rows are expected to fail for that reason and are also reported separately. The descriptive agreement
table has the same limit (`cas/run_world.py` lines 259 to 275 compare a COLOUR structure with the reference at the
excluded tasks' pairs, not at the structure's own pair).

## 8. Risks to reportability

- **Hole specification leakage: none found.** The controller sees only demonstrations, query inputs and the built
  grammar (`cgrow/controller.py` lines 111 to 138); hole targets are B⁻¹(output) or A(input) with A, B invertible
  G0 operations, which is the mechanism under test, not a leak. The arms read the evaluator file only for partition
  and family labels (`cgrow/s1.py` lines 37 to 51) and never the references. The evaluator-only files travel in the
  kernel package as in the S1 replay; that is a convention, not an isolation, and is unchanged from S1.
- **Seeds.** Structure orders `random.Random("s1-order-" + seed)`, bootstraps seeds 1 and 7, generator and pool
  orders by salted sha256, power seeds 1000 F + 10 m + ord(scenario): all fixed. The CPU-time stops are the only
  non-deterministic element, which is why finding 5 matters.
- **Kaggle settings.** `cas/kaggle_build.py` lines 114 to 117: private, internet off, no GPU, no data sources; the
  archive digest is asserted in the notebook (line 73); the package manifest records every file's sha256.
- **Finding 8 (medium, new, not in revision 2). Nothing verifies the downloaded outputs.** `PROTOCOL.md` line 483
  says outputs "are checked against their manifest before the analysis", but no script does it: the analyse stage
  of the gate checks only the GO, the frozen files and the claim (`cas/gate.py` lines 68 to 78), and
  `OUTPUT_MANIFEST.json` (`cas/kaggle_main.py` lines 41 to 52, 97) has no reader. Fix: add to the analyse stage (or
  a small `verify_outputs.py` run before it) a check that every file under each downloaded `runs/` has the sha256
  in its `OUTPUT_MANIFEST.json`, that the world's `TASKS_SYSTEM.json` and `TASKS_EVAL.json` digests equal the
  committed `PARTITIONS_MANIFEST.json`, and that the kernel log's package digest equals `PACKAGE_MANIFEST.json`;
  commit `runs/RUN_CLAIM.json` together with the task digests at step 3 of section 11.
- **Finding 9 (medium, new). Kernel memory.** Each matched-search child is limited to 12 GB of address space
  (`cas/run_world.py` line 152); revision 1 runs two beside the specification process, revision 2 runs three. Three
  children can reach 36 GB on a kernel with about 30 GB, and a kernel-level kill is not the `MemoryError` the
  "run once more alone" rule handles. Fix: at most two matched-search children when other processes run, or 8 GB
  per child with three; keep the rerun-alone rule.
- **Finding 10 (low). No failure guard on a matched-search child, and outputs are packed only at the end.**
  `cas/run_world.py` line 176 waits without a timeout (S1 used six times the cap, `cgrow/testib_rest.py` line 76);
  the notebook packs `runs/` only after the run cell (`cas/kaggle_build.py` lines 84 to 88), so a hang or the
  12-hour session limit loses the world. Fix: `communicate(timeout=6 * cap)` recording "timed out" as not
  recovered (a failure guard, not a budget), and pack the outputs after every stage.
- **Finding 11 (low).** `cas/run_world.py` lines 236 to 238 turn a missing C7m result into "not recovered". It can
  only happen after a stage failure, but it would bias against the comparator silently. Fix: record `None` and let
  `_compare` skip the task; print the number of tasks with both results.
- **Finding 12 (low).** A build failure after the claim is written leaves no sanctioned path (`cas/gate.py` lines 69
  to 70, 96). Generation is deterministic, so pre-declare the recovery (the coordinator may remove the partial
  `runs/generated/` and the claim once, logged in `PROGRESS.md`), or write the claim after a successful build and
  refuse when `runs/generated/` exists.

## 9. For the revision-2 review

Revision 2 (uncommitted in the working tree at review time: `PROTOCOL.md`, `cas/run_world.py`, `cas/analysis.py`,
`cas/kaggle_main.py`, `cas/power.py`, `cas/equivalence.py`, `cas/freeze.py`, new `launch/run_equiv3.sh`,
`launch/run_c7m_smoke.sh`, `power/COMMITTED_POLICY_S1_CHECK.json`) answers findings 1 to 4. It was read, not
reviewed. What its exact-byte review must do:
1. Confirm the new `PROTOCOL.md` and `FREEZE.json` digests and that `FREEZE.json` lists `PROTOCOL_REVISION_1.md`
   and `FREEZE_REVISION_1.json` with the digests above.
2. Re-run the equivalence replication on the new `checks/EQUIVALENCE.json` (controller 38 of 38, units 99 of 99,
   primary 8 against 5, p = 0.375, interval [-0.2, 0.667]) and confirm committed outputs equal reach on S1's units.
3. Check `committed_outputs` (promoted, else first quarantined, in candidate order) and `c7m_budget`
   (max of 150 reference CPU-s times the factor and S-hole's largest charged total, both in machine seconds).
4. Decide finding 5 (benchmark under concurrency or execution-count stops) and finding 9 (memory) against the new
   four-process stage plan, and findings 8, 10, 11, 12 (custody and robustness).
5. Confirm the S1 code (`cgrow/*.py`), A2, CAST, arc-dsl and the training data digests are unchanged.

Results of this review that carry over unchanged to revision 2 because the files are unchanged: the pools and their
hashes, the exclusion of S1's 61 sources, the evaluation-set check, the pilot and dry-run sources, the feasibility
and novelty records, the power rows (the `simulate` function is unchanged in the working tree), the benchmark
reference, the kernel settings and the gate's behaviour.

## 10. Method of this review

Read-only. Scripts ran as single processes under `scripts/with_cpu_slot.sh` at nice 19: a standard-library
verification script (hashes, pools, S1 cross-checks), a second one against the committed tree extracted with
`git archive 6b5fb6f8` (equivalence replication, statistics, feasibility, package settings), a gate fixture on a
scratch copy of that tree, and the power re-derivation with the project's Python (numpy). No arm ran, no task was
generated, no GO was written, nothing public or under Step B was touched. The scripts and outputs are in the
reviewer's scratch folder; the key numbers are quoted above.
