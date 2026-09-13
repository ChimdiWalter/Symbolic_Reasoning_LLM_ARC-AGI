# Step-B pre-freeze deviations, and the quarantine the gate must obey

Recorded 2026-09-13, before the Step-B freeze marker exists. This is the formal
record of every pre-freeze access to Step-B material, protected material or
evaluation data that a mechanical audit could identify. It supersedes the
narrower disclosure in `docs/CORA_SELF_EXTENSION_LOOP_AUDIT.md`, which is kept
unchanged as written.

## How the record was built

The tool-call INPUTS of every agent in the four workflow runs of this session
were scanned for sealed path patterns: 526 calls in the self-extension loop
audit, 237 in the gate protocol drafting run, 1108 in an earlier census review,
and 147 in an earlier fitter design run. Only inputs were examined, meaning the
commands and paths each agent issued. No tool result was printed or re-read to
build this record, so building it exposed nothing new.

## The rules these are measured against

- The resume log: the journal holds proposal records and is not inspected
  before the pin; monitoring is quantitative only, with no inspection of
  winning candidate names, schemas, per-cluster proposals, source tokens,
  fingerprints or convergence until the runner prints `STEP B FROZEN` with the
  output hash; no E_transfer, promotion, Lockbox or sealed expectation before
  the pin; the runner and `candidates.py` are never edited.
- The restart script's own comment: the journal is not inspected before
  `STEP B FROZEN` and the pinned hash.
- The directive of 2026-09-13: no access to E_transfer, Lockbox, sealed
  expectations, protected mappings, Step-B journal contents, candidate
  contents, mechanism-input contents or gate-output contents.
- The CORA-TTI split rule: the holdout is scored only at gates C3 to C5.

## Deviations

| id | what | against |
| --- | --- | --- |
| D1 | one mechanism-input corpus row decoded; keys and demonstration count printed | mechanism-input contents |
| D2 | every candidate inventory instance printed by name and typed signature | candidate contents, read broadly |
| D3 | runner and Step-B package source read, including output-record code | the gate guard's own seal, not a standing rule |
| D4 | ARC evaluation inputs, holdout included, loaded into memory | the spirit of the holdout rule; no scoring |
| D5 | live-tree dry runs hashed sealed files and printed lane digests | retired by the 2026-09-13 directive |
| D6 | transfer split documentation read | checked, no identifiers; not a deviation |
| D7 | Lockbox directory filenames listed | names only |
| D8 | guard misclassified worktree copies and the firewall | tooling defect; no access resulted |

**D1. Mechanism-input corpus, one row decoded.** Self-extension loop audit. The
agent located the dev worktree's copy of
`outputs/cora_breakthrough/level4_mechanism_inputs/invention_corpus.jsonl`,
which is a separate file from the main checkout's, read its first line, and
decoded that whole row in process memory. It printed the file path, the row's
sorted top-level keys, and the number of demonstrations in that row. It did not
print the token value or any demonstration grid. The earlier disclosure said
"row structure, two keys" and omitted both the full decode and the printed
count.

**D2. Candidate inventory listed.** Same workflow, a different agent. It decoded
the dev worktree's copy of `outputs/cora_breakthrough/level4_stepB_inventory.json`
and printed: the top-level keys; the instance count; the type universe; the
terminal and induced types; the family and meta-family descriptors, truncated
at 800 characters; the well-formedness rule; the first instance record,
truncated at 800 characters; and then the name and typed signature of every
instance. This is the frozen pre-run candidate space fixed by the manifest. It
is not a record of what the run proposed, kept or selected, and it reveals no
cluster, token, fingerprint or convergence. It was not previously disclosed.

**D3. Design source read.** Agents in both the audit and the drafting workflows
read the Step-B runner source, including the code that writes output records,
and the Step-B package source: the witness generator, the install module, the
K2 inventory and slot modules. They also read the blind runtime's search module.
These files are frozen by the manifest and were read, not modified. The scan
found no read of the journal, the witnesses file, the gate outputs or the
expectation seal by the drafting workflow. As a result, protocol v1 encodes
assumptions about Step-B output record fields that were learned from source
rather than from outputs.

**D4. Evaluation data in memory.** Two audit agents decoded
`outputs/tti/eval_split_v1.json` and printed its keys, list lengths and scalar
fields, plus its hash file. One of them decoded the whole
`data/arc/arc-agi_evaluation_challenges.json`, which holds the inputs of all 120
evaluation tasks, development and holdout, but no solutions. It derived the 60
development identifiers by the frozen keyed ordering, confirmed they equal the
stored development set, and evaluated the `trigger_fires` predicate on the
demonstration pairs of those 60 development tasks only. It printed counts and
development identifiers. No holdout task was selected, printed, evaluated or
scored, and no solutions file was opened. The holdout rule concerns scoring and
was not breached, but holdout inputs were in process memory.

**D5. Live-tree dry runs, main session, 2026-09-09.** Three pre-freeze dry runs
of the pin tool hashed files in the live tree, including the journal, the gate
outputs and the mechanism inputs. Bytes were read transiently for sha256 and
newline counts and were not decoded. The printout showed digest prefixes, byte
sizes and line counts, and so exposed which determinism-lane files have equal
digests. File modification times place every lane file at 2026-08-25, 12:40 and
13:19, which is before the pre-run gates report at 13:19:27, before the run
manifest at 14:51:44, and before the live runner started on 2026-08-26 at 23:09.
The lane files are therefore pre-run gate artifacts, and the observation concerns
the pre-run determinism check that the resume log already reports as passing on
a masked comparison. Nothing about the live run was exposed. The directive of
2026-09-13 retires such dry runs, and the tool now refuses them on the live tree
before reading anything.

**D6. Transfer split documentation.** A drafting agent read the run-history
entry that describes how the Experience set splits into invention and transfer
sets. On 2026-09-13 that range was checked by counting: it contains zero task
identifiers. It describes the mechanism and names the firewall file that holds
the identifiers. This is recorded as checked and is not a deviation.

**D7. Lockbox directory listing.** Two drafting agents listed the filenames in
`outputs/lockbox/`. Names only, no file opened.

**D8. Guard defect.** The earlier access guard classified paths relative to the
main checkout only, so the dev worktree's separate copies of sealed artifacts
were treated as open. It also placed the provenance firewall, which holds the
transfer identifiers and the forbidden-name map, in the class that unlocks at
stage 3 instead of stage 7. No gate stage ever ran, so no access resulted. Both
are fixed in `cora_tti/gate_guard.py` and covered by tests.

**Permitted reads, for completeness.** On 2026-09-13 the main session read the
run manifest's key paths filtered for output, hash and freeze terms, which the
guard classifies as a protocol artifact; the matching lines of the restart
script, which is the one Step-B script whose use is permitted; ranges of the
resume log; and the modification times of the lane files. On 2026-09-09 it
listed filenames and sizes in the breakthrough directory and classified real
artifact paths by name without opening them.

## Assessment

None of these touched the running experiment. The run was not modified,
restarted, accelerated or delayed, and nothing was written into the main
checkout. None exposed what the run proposed, kept or selected, how any cluster
converged, any E_transfer identity, any Lockbox content, any sealed expectation
or any token mapping. Step B is not invalidated by these facts alone. They are
recorded as protocol deviations, and their influence on the gate is removed by
the quarantine below.

## Quarantine rules, binding on protocol v2 and every gate script

**Q1.** No observation from D1 to D5 may be used to choose a witness substrate,
choose or shape a witness procedure, set or move a threshold, define a task
pool, or order candidates.

**Q2.** Every protocol statement about the field layout of a Step-B artifact or
a task record is a declared ASSUMPTION. That covers field names, the presence of
held-out test pairs, the presence of task identifiers, and record shapes. Each
assumption is checked mechanically at G3. A failed check emits
`SCHEMA_ASSUMPTION_FAILED` and halts the stage, and any tooling change made
after it is `POST-INSPECTION-TOOLING`.

**Q3.** The protocol must be valid under either answer to each of these: whether
the invention corpus carries held-out test pairs; whether it carries task
identifiers; which instances the inventory contains. Where a stage depends on
one, both branches are stated in advance.

**Q4.** The bridge shapes named for the failure branch come from the directive
of 2026-09-09 and are not revised with any knowledge from D2.

**Q5.** Two claims in the self-extension loop audit derive from D1 to D3 and may
not be premises in any gate rule: that the blind runtime already carries a
`Set[Region] -> Grid` bridge, and that the Step-B corpus carries no test pair
and no task identifier.

**Q6.** Any further pre-freeze agent work receives an explicit forbidden-path
list, and its tool-call inputs are scanned against that list afterwards, before
its output is used.
