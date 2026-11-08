# Test I: deliberately missing capabilities (capability recovery), 27 Oct 2026

Label: capability recovery (re-inventing deliberately removed operations), not invention of an unforeseen
capability. Protocol `PROTOCOL.md` (frozen b4e4f60; amendments 1 to 3 before any proposal was scored). Tables:
`reports/TEST_I_TABLES.md`; registry `CAPABILITY_REGISTRY.md`; results `runs/eval_v1/results.json`; every
proposal and failed attempt with stage and reason: `runs/process_v1/episodes.jsonl`.

## 1. Answer first

- **The complete cycle ran end to end and recovered two of the four removed capabilities, in fixed-parameter
  form.** Steps: failure detected, decision to invent, neural operator proposal in the sandbox, retry, regression
  check, validation, promotion, versioned registry, reuse on excluded tasks. The two: downscale by 2 and upscale by
  2 or by 3. compress and trim were never recovered, in any arm.
- **Authentic failure evidence (C5) recovered more motivating units than every control.**

  | arm | units recovered (of 22) |
  |---|---|
  | C5 | 6 |
  | C2, failure-blind | 2 |
  | C1, whole-program writing | 2 |
  | C3, shuffled evidence | 0 |
  | C7, 20x search | 0 |

  The paired differences against C3 and C7 are 6 to 0 (exact p = 0.031). Against C2 it is 4 to 0 (p = 0.125):
  directional, not established. All four C5 gains come from two families.
- **Positive control:** correct hand-written implementations pass every gate, with 6/6 reuse each. The pipeline is
  not the bottleneck.
- **The proposer is the bottleneck.** Given an exact input/output specification (diagnostic D0), it recovered only
  1 of 11 tasks.

## 2. Setup (short)

- **G0:** A2's arc-dsl grammar (A2's search and budget: 150,000 executions per task) minus
  R = {compress, downscale, trim, upscale}.
- **Expressibility in G0** (evaluator-only check):
  - compress, downscale and upscale: no G0 program within cost 12;
  - trim: a G0 macro at cost 10.
- **Families:** 11 tasks per capability, built from templates over real S_train / S_select input grids.
  - M: 3 motivating tasks;
  - V: 2 in the system's validation pool;
  - E: 6 excluded tasks, evaluator only.
- **Other tasks:** 4 search-level decoys and 14 previously solved tasks.
- **Baselines by construction:** C0 = 0 and the reference ceiling = 1 on every family task.
- **Proposer:** Qwen3-4B-Instruct-2507 (fp16, GPU 0), K = 4 proposals per episode, seeds 0 and 1. The prompt
  template, token cap (640) and sampling seeds are identical across arms.
- **Episodes:** 22 per arm (11 motivating tasks × 2 seeds). One trim motivating task was routed to deeper search
  instead (see 3.1).
- **Sandbox:** inventions run only in the gridfn-1 sandbox with the library refused, because the library already
  contains trim, upscale and downscale.

## 3. Results reported separately (safeguard order)

### 3.1 Autonomous diagnosis

- **Controller decisions:** INVENT_NEW_OPERATION on 19 of 20 family tasks (M and V). CONTINUE_PROGRAM_SEARCH on the
  4 decoys and on 1 trim task, where the 4x probe found the G0 macro. All match the evaluator's truth.
- **What the controller can distinguish:** v1 probes only "search vs operation". The proposer stated level
  "operation" in 243 of 243 parsed proposals, so it is uninformative.
- **Status of every failure:** "no fit among first-order programs of cost at most 9 or 10, plus 400 closures". Every
  failure hit A2's closure cap, so no fragment was exhausted and no inexpressibility is claimed.

### 3.2 Autonomous invention and executable validation

- **Proposals reaching execution** (passed the allowlist and substrate checks, returned grids):

  | arm | proposals |
  |---|---|
  | C2 | 71/88 |
  | C3 | 80/88 |
  | C5 | 73/88 |

- **Renames of an existing G0 program** (rejected by the novelty check):

  | arm | renames |
  |---|---|
  | C2 | 15 |
  | C3 | 15 |
  | C5 | 5 |

- **Leak scan:** 0 of 241 distinct codes are near-verbatim arc-dsl, and none uses a removed name.

### 3.3 Task-level recovery

Units: motivating task × seed.

| capability (G0 status) | C2 | C3 | C5 | C1 | C7 |
|---|---|---|---|---|---|
| compress (no G0 program) | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 |
| downscale (no G0 program) | 0/6 | 0/6 | 2/6 | 0/6 | 0/6 |
| trim (G0 macro at cost 10) | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 |
| upscale (none within cost 12) | 2/6 | 0/6 | 4/6 | 2/6 | 0/6 |
| total | 2/22 | 0/22 | 6/22 | 2/22 | 0/22 |

What was recovered:
- **C5:**
  - downscale(I, 2) and downscale(hmirror(I), 2), seed 1. The inner sketch ?(hmirror(I)) gave the exact hole
    specification.
  - upscale(I, 2), both seeds.
  - upscale(hmirror(I), 3), both seeds.
- **C2 and C1:** only upscale(I, 2).

### 3.4 Cross-task reuse, promotion, kind

| arm | promoted operations | regressions | quarantined (task-local) |
|---|---|---|---|
| C2 | 2 | 0 of 14 | 0 |
| C3 | 0 | 0 of 14 | 0 |
| C5 | 4 | 0 of 14 | 3 |

- **Excluded-task reuse of promoted operations:**
  - downscale-by-2: 4/6 downscale E tasks;
  - upscale-by-2: 2/6 upscale E tasks;
  - the quarantined upscale-by-3 instances would solve the other 4/6.
- **Reference agreement:** every recovered operator agrees with the removed reference 1.0 at its own factor and
  0.0 at the other. Each one is a parameter-specialized instance of a parametric primitive.
- **Kind:** all are expansions; no G0 program reproduces them within 1M executions on probe grids.
- **Cross-family transfer:** 0.
- **Rollback:** never triggered.
- **Gate false negative:** the factor-3 instances were quarantined because the validation pool held only factor-2
  upscale tasks.

### 3.5 C5 against controls

Paired units, n = 22.

| comparison | C5 only | other only | exact McNemar p | difference, 95% bootstrap over units |
|---|---|---|---|---|
| recovered: C5 vs C2 | 4 | 0 | 0.125 | +0.18 [0.05, 0.36] |
| recovered: C5 vs C3 | 6 | 0 | 0.031 | +0.27 [0.09, 0.45] |
| recovered: C5 vs C7 | 6 | 0 | 0.031 | +0.27 [0.09, 0.45] |
| recovered: C5 vs C1 | 4 | 0 | 0.125 | +0.18 [0.05, 0.36] |
| promoted: C5 vs C2 | 2 | 0 | 0.5 | +0.09 [0, 0.23] |
| E reuse count: C5 vs C2 | | | | mean +0.36 [0, 0.91] |

The intervals ignore clustering by family (4 clusters; the gains sit in 2). Shuffled evidence hurt: C3 lost the
upscale(I, 2) recoveries that C2 made. That supports "the report's content steers the proposer". It also means the
C5 vs C3 gap combines a gain from true evidence with a loss from misleading evidence.

**On the excluded tasks, C7 (20x search) solved 4 of 24:**
- trim(I) twice, through the G0 macro;
- two others through coincidental programs that are correct on the query.

### 3.6 Ceiling probe D0 (evaluator-only, seed 0, not an arm)

- **Given the removed operation's exact input/output behaviour on the task's own grids, the proposer recovered 1 of
  11 tasks** (upscale(I, 2)).
- **Agreement with the reference was 0 to 0.1** for all its compress, downscale and trim proposals.
- **So the binding limit is the 4B proposer's ability to implement a grid operation**, not CORA's evidence or
  gates.

### 3.7 Cumulative growth and ARC accuracy

Not tested: no multi-cycle run, no real-ARC run.

## 4. Cost

Ledger family CGROW: **2.34 CPU-h and 1.64 GPU-h** in total, inside the 4 h and 4 h check-in.

| item | GPU-h | CPU-h |
|---|---|---|
| generation, including two stopped development runs and the benchmark (the decode loop holds one core) | 1.37 | 1.35 |
| repairs and ceiling probe | 0.27 | 0.28 |
| processing | | 0.13 |
| evaluation | | 0.23 |
| task construction, prep, controls | | rest of the CPU total |

## 5. Defects and limitations

1. **Every failure hit the closure cap.** So no inexpressibility is demonstrated, only "not found in the enumerated
   fragment".
2. **The sketch ranking is a heuristic.** On compress(I) it showed two misleading rotation sketches instead of the
   identity.
3. **Three protocol amendments came after watching the first generations:**
   - token cap and huge TESTS;
   - copied parameter anchoring;
   - a USE example naming a real card code, an accidental hint toward one family.

   The stopped runs are kept and nothing from them was scored. The prompt was still shaped on development
   observations.
4. **C7 got less compute than a C5 episode:** 8 to 29 CPU-s per task, against about 70 GPU-s plus decode CPU per
   episode. The search grows by about one cost level per 4x, so a matched C7 would likely still fail on the
   non-macro families. This is not measured.
5. **C1 was not run on E tasks** (amendment 1).
6. **Inventions are fixed-parameter.** The parametric primitive was never recovered, and nothing anti-unifies the
   factor-2 and factor-3 instances.
7. **The validation pool is narrow.** It produced the false-negative quarantine of the factor-3 operations.
8. **The proposer's stated level is always "operation".** Representation, relation and composition were never
   exercised; v1 only probes search vs operation.
9. **Real regression task a416b8f3 shares its input grids with one trim E task** (no outputs shared).
10. **The registry's kind field is "undetermined" for promoted entries.** Kind was computed in evaluation and is
    shown in `CAPABILITY_REGISTRY.md`.
11. **The study is small:** 22 units in 4 families, a single 4B model, 2 seeds.

## 6. Supported claim and limitation

**Claim.** On a controlled capability-recovery test with hidden removed primitives, CORA's full self-extension
cycle executed as real computations:
- detection;
- decision to invent;
- sandboxed neural operator proposal with neutral names;
- retry;
- regression check;
- validation;
- promotion into a versioned registry;
- reuse on excluded same-family tasks.

It recovered parameter-specialized versions of 2 of 4 removed capabilities, with exact agreement and real
expressivity gain. Its own failure reports gave more recoveries than shuffled reports or 20x search, and a
non-significant edge over failure-blind invention.

**Limitation.** This is recovery, not invention: four capabilities, two families carrying the gains, and a 4B
proposer that cannot implement compress or trim even from an exact specification. The comparison with the
failure-blind control is a tie by its exact test.

## 7. Decisive questions (as far as Test I supports)

1. **Can CORA recognize that ordinary search or local repair is insufficient?** Yes, coarsely. The controller
   invented on 19 of 19 family failures after a 4x deeper search failed, and correctly sent 5 tasks to more search.
2. **Can it distinguish that condition from a genuinely missing capability?** Only operationally (the probe). It
   never has a proof, because of the closure cap.
3. **Can it identify what kind of capability to add?** Not beyond "operation". Sketches localized the hole in most
   composite tasks.
4. **Can its neural engine propose a new operation?** Yes, executable in 73 to 80 of 88 proposals. It was correct
   for 2 of 4 capabilities, only as fixed-parameter instances.
5. **Can CORA compile and execute the invention safely?** Yes: sandbox only, library refused, no leaks found.
6. **Does the invention solve the failure that motivated it?** C5: 6/22 units; C2: 2/22; C3: 0/22.
7. **Does it generalize beyond the motivating examples?** Within family, to tasks with the same parameter: 4/6 E
   (downscale) and 2/6 E (upscale). No cross-family transfer.
8. **Can it become part of CORA's repertoire?** Yes. It is promoted persistently with no regression; rollback was
   never needed.
9. **Does CORA improve over successive cycles?** Not tested.
10. **Does authentic failure diagnosis beat matched controls?** Directionally. It is significant against shuffled
    evidence and against search, a tie by exact test against the failure-blind control.

## 8. Verdict: MODIFY

**Next experiment (Test I-b, same frozen tasks and code; no new data):**
1. **Power:** seeds 2 to 4 for C2 and C5.
2. **Attribution:** one ablation, C5 without unreachable sketches (search status, closest program and shape
   relation kept). It tests which evidence matters.
3. **Matched C7:** 150 CPU-s per task.
4. **A symbolic abstraction step** (no GPU): anti-unify promoted instances that differ only in a constant into one
   parametric operator, then re-validate. It tests whether specialized recoveries can be lifted to the parametric
   capability.

Resources: about 2.7 GPU-h and 3.5 CPU-h, with a check-in after the seeds.

**Not yet:**
- **Test II** (unanticipated combinations): wait until Test I-b shows the C5 vs C2 edge survives more seeds,
  because the proposer limit would dominate.
- **A stronger proposer:** a 7B coder model would need a download approval.

**Proposed, not launched:**
- **Test II, unanticipated invention.**
  - Families combine two source mechanisms whose joint abstraction is absent from G0 and never named; nothing is
    removed. Examples: a per-object operation conditioned on a marker, or row-wise selection by a predicate.
  - Held-out tasks come from the same relation.
  - Arms: C2, C3, C4 (A2's success-based compression), C5 and C7, at matched compute.
  - Size: about 4 families × 11 tasks.
  - Resources: about 3 GPU-h, 4 CPU-h.
- **Test III, cumulative growth.**
  - Three bounded cycles L0 → L1 → L2 → L3, each adding families that need new capabilities plus combinations of
    earlier ones.
  - Measures:
    - accepted, rejected and rolled-back capabilities;
    - search-cost change;
    - newly solved tasks;
    - retention of earlier solves;
    - whether each addition stays necessary (ablate it, retest);
    - C5 vs blind and vs library learning at equal compute.
  - Resources: about 4 GPU-h, 5 CPU-h.
