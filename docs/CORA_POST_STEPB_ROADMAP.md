# CORA post-Step-B roadmap: from invention to capability transfer

Written 2026-08-25, while the Step-B invention run is in flight (pid 46975, manifest
8476b211400f1c3f, git 783568d). This document records the SEQUENCE and the CLAIM
DISCIPLINE agreed for everything downstream of that run. It pins nothing and is cited
by nothing: the frozen design document (28cc8734...) remains the only authority over
the run itself. Nothing here may be used to reinterpret results after seeing them.

## 0. Where the project actually stands

- Level 1 discovery: **YES** (meta-layer found programs the base search did not, through
  the ordinary gate).
- Level 2 abstraction invention: **YES** (concept_0001 by anti-unification of two
  independent discoveries, typed slots, generated name, persisted with provenance).
- Level 3 capability transfer: **NOT ACHIEVED** — 0 causal witnesses. Diagnosed cause:
  the concept could only EXPRESS 3 of 598 non-provenance tasks. The transfer machinery
  was not the limit; the REACH of the meta-language was.
- Level 4 semantic self-extension: **RUNNING NOW** (Step B).
- Sealed ARC score: **185/1000** (v23, 2026-08-19; artifact-backed: unified_harness_v23
  results.json total_solved 183 + v23_arbitration 2/2 recovered). Eval: 0/120 honest.

Level 3 is therefore not superseded by Level 4. Level 3 is BLOCKED ON reach, and Level 4
is the principled way to buy reach: the system extends its own language instead of a human
widening the DSL.

## 1. The order after the run completes (no step skipped, no reordering)

1. **Pin before looking.** Record the runner's output hash in RESUME_STAGE1.md and
   RUN_HISTORY.md. Only then inspect candidate names, schemas, per-cluster proposals,
   fingerprints or source tokens. The checkpoint journal falls under the same discipline
   and is deleted by the runner at completion.
2. **Semantic separation certificate.** For every KEPT K2 candidate, decide whether its
   behaviour is available in the frozen pre-extension language K_L4*. `NEW_SEMANTIC_
   PRODUCTION` is the GENERATION-LANE LABEL ONLY and establishes nothing on its own —
   item 1 already showed generic constructors can reproduce baseline behaviour. A
   candidate that merely re-expresses K_L4* behaviour is a re-expression result, not an
   invention result, and must be reported as such.
3. **Held-out transfer of the PRODUCTION.** Test surviving candidates on E_transfer (the
   25% split the invention never saw). This is the first genuine Level-4 claim: an
   operator invented from failures helps on tasks that had no part in inventing it.
4. **Promotion.** K_{t+1} = K_t ∪ {e} for each e that survives 2 and 3, recorded with
   provenance and hashes.
5. **Re-discovery under the enlarged language.** Run the ordinary unguided discovery over
   the experience families again. Let anti-unification produce concept_0002/0003
   automatically — do not author them.
6. **Level 3 rerun.** scripts/cora_level3_transfer.py under fixed budgets, K vs K + C_i
   vs ablation, on non-provenance tasks. 3A (efficiency) and 3B (capability) reported
   separately, as already specified.

### The Level-3 witness (unchanged, keep exactly)

A causal witness requires ALL of: baseline fails; K + C_i succeeds; the winning program
actually USES C_i; every leave-one-out fold passes; the rendered test output is correct;
and removing C_i makes it fail again. Anything less is not a witness.

### Dependency chain in one line

failure frontier → blind clustering → candidate extension → multi-source LOO certification
→ semantic separation → held-out production transfer → promotion → re-discovery →
anti-unified concepts → Level-3 causal transfer.

## 2. Outcome ladder for the run in flight (decide the wording BEFORE seeing results)

- **Outcome 1 — candidates proposed.** Proposal generation works. Engineering result.
  Not a scientific claim.
- **Outcome 2 — candidates certified on ≥2 independent sources.** Stronger, still not
  enough: they may re-express K_L4* behaviour. Requires step 1.2 before any claim.
- **Outcome 3 — separation certificate + held-out transfer pass.** This is a serious
  research contribution: the system acquired a capability that provably was not in its
  language, from its own failures, blind.
- **Outcome 4 — the loop repeats.** K_0 → K_1 → K_2 → K_3, each cycle failures → new
  semantics → new solves → new abstractions → new failures, with the gains disappearing
  under ablation. This is where "open-ended abstraction growth" becomes defensible and
  where the word "groundbreaking" can be used without embarrassment.
- **Outcome 0 — nothing kept.** Explicitly accepted at design time (the template family
  may stay unsolvable with Collection_to_Grid inactive). A careful negative result about
  the limits of interface-directed invention. Publish it; do not patch it afterwards.

## 3. Claim discipline (binding)

**Never write** "no previous system invents concepts/predicates from failure." Prior art
exists and a reviewer will find it: the learning-from-failures ILP line includes predicate
invention (POPPI); ADVENT (2026) invents and accumulates predicates for reuse; DreamCoder
and LILO grow libraries by compressing programs they already synthesised, and DreamCoder
has been applied to ARC.

**The defensible claim is the CONJUNCTION**, stated in full:

> failure-frontier-triggered typed semantic self-extension in an ARC program-induction
> system, where candidate extensions are generated under a frozen blind proposal language,
> accepted only through complete leave-one-out re-induction, semantically separated from
> the pre-extension language, and subsequently tested for held-out cross-task transfer —
> with blinded task identity, deterministic all-cluster processing, multi-source
> certification, causal ablation, and provenance hashing that prevents retroactive DSL
> engineering.

The unusual pieces are: evidence drawn from FAILED certified rediscovery rather than
solved-program compression; semantic PRODUCTION invention rather than macros; a frozen
pre-invention language; blinded task identity; deterministic all-cluster processing; and
the hash chain that makes retroactive DSL engineering impossible to hide. A proper
related-work sweep is REQUIRED before any precedence sentence ships.

**One sealed number everywhere** — paper, README, abstract, slides: 185/1000 (v23,
artifact-backed). "181" is v22. The paper still carries 181 and its refresh is queued.
Verify against results.json artifacts, never against transcript numbers.

## 4. Two races — do not conflate them

- **Leaderboard race** (how many ARC tasks): frontier foundation models are far ahead;
  CORA is not close, and has no demonstrated eval solve. Do not frame this work as
  competing there. Check current ARC Prize reporting before quoting anyone's numbers.
- **Mechanism race** (can a system autonomously expand the language it reasons in, with
  a causal audit trail): this is where CORA can make a distinctive contribution, and it
  does not require beating anyone's percentage to matter.

The strongest eventual paper tells the mechanism story, not a score:

> a fixed symbolic reasoner reaches an expressivity barrier → the barrier is detected from
> certified failures → without task identities or human operator selection the system
> proposes new typed semantics → the capability is shown to be unavailable in the previous
> language → it survives complete leave-one-out re-induction → it transfers beyond the
> tasks that induced it → it enters the knowledge state → the enlarged system discovers
> further solutions and abstractions → removing the invented semantics destroys those gains.

## 5. Standing operational rules for this run

- Never edit scripts/cora_level4_stepB_run.py or level4_stepB/candidates.py: the manifest
  pin AND the checkpoint journal header would both reject the change.
- Resume after any crash or reboot with `bash scripts/restart_stepB_after_reboot.sh`
  (it reports how many completed units it will replay). Only in-flight units are lost.
- Monitor QUANTITATIVELY ONLY until "STEP B FROZEN" and the pinned hash.
- Gate failures from here justify implementation corrections restoring the declared
  protocol; they never justify changing the protocol.
- E_transfer, Promotion, the Lockbox and the sealed expectation remain closed.
