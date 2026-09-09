# Audit of the self-extension loop: what exists, what does not

Read-only audit run 2026-09-09 while the frozen Step-B experiment was live. No
code was changed, no experiment was launched, and nothing sealed by the
Capability-Growth Gate was opened. The purpose was to establish what the gate
and any later redesign can reuse, so that neither is planned from recollection.

## Disclosure

One audit agent read the ROW STRUCTURE of
`outputs/cora_breakthrough/level4_mechanism_inputs/invention_corpus.jsonl`. The
instructions given to that agent named the journal, the witnesses file, the
candidate inventory, sealed expectations and protected token mappings, and did
not name the mechanism-input corpus. What was returned is schema only: rows
carry exactly two keys, `source_token` and `demonstrations`. No token value, no
demonstration content and no expectation was read or reported.

`cora_tti/gate_guard.py`, written immediately afterwards, seals
`outputs/cora_breakthrough/level4_mechanism_inputs/*` until stage 3 and would
have refused the access. The finding is retained because it is structural and
because suppressing it would be worse than recording it, but it is marked here
as obtained outside the intended boundary.

## Component ledger

| component | verdict |
| --- | --- |
| failure localization | substrate only; no classifier exists |
| semantic extension constructor | exists in the blind runtime, absent behind the real engine |
| ephemeral install and reset | exists and is reusable |
| verification and leave-one-out | exists, needs the proposal moved inside the fold |
| reach-witness measurement | prototype; never called in production |
| promotion lifecycle | absent beyond a two-state annotation, never observed positive |
| real-engine integration | exists, ran once, both arms scored zero |

## Verified directly, with file and line

These four were re-checked against the source rather than accepted from the
audit, because the conclusion below rests on them.

**The concept hook is gated before it is consulted.**
`geocat_arc/object_reasoning/meta_induction.py:550`. `induce_computed_candidates`
executes `if not trigger_fires(pairs): return [], SearchStats(trigger=False)`
before it reaches `if concepts:`. On a task where the trigger does not fire, the
installed extension is never consulted at all.

**On a concept hit the ordinary search never runs.** Same function. When
`search_with_concepts` returns hits, the function returns those programs
immediately. The call to `search(...)` below it is unreachable in that branch.
So the augmented configuration REPLACES the baseline hypothesis stream rather
than adding to it.

**The concept path omits a filter the ordinary path applies.**
`search` takes `require_fold_coverable: bool = True` and applies it at
`meta_induction.py:455`, discarding tables with a key witnessed fewer than twice.
`search_with_concepts` at `meta_induction.py:378` enumerates the same slot
domains and never applies it. It also stops at the first productive concept via
`if found: break`.

**Two legs of the six-part conjunction have never been computed.**
`cora_tti/ablation_ledger.py:37` defines the conjunction as `baseline_fails`,
`production_proposed`, `winner_uses_production`, `loo_all_folds_pass`,
`test_output_correct`, `ablation_fails`. `test_output_correct` appears in exactly
two places in the tree: that tuple, and `cora_tti/tti_loop.py:174` where it is
set to `None` with the comment that callers fill it. No caller does.
`record_tti_ablation` has one definition and one caller, which is a test. There
is no `outputs/tti/ledger.jsonl`, so zero ablation rows exist.

`tti_dependent` counts a missing key as False, so an uncomputed leg cannot pass
by omission. That part is correct as written.

## What follows from those four facts

On a triggering task where an installed concept fits, the augmented
configuration searches the same hypothesis space as the baseline, minus the
fold-coverability filter, and does not fall back to the baseline stream. Its only
differential reach is therefore the set of tables whose keys were witnessed once,
which is precisely what the leave-one-out gate downstream is built to reject.

That is a mechanically sufficient explanation for the recorded outcome of 49
activations and zero gate acceptances, and it does not depend on the quality of
what was proposed. The earlier reading, that the proposal source was the gap, may
still be true, but the measurement cannot support it, because the arm could not
have exceeded the baseline on that path regardless of what was installed.

The consequence for evidence is narrow and should be stated narrowly. The
development-set null does not measure whether test-time extension helps. It
measures a configuration in which extension could not help. It is not evidence
against the research question, and it should not be cited as such.

## Reported by the audit and NOT independently verified here

Recorded so that the distinction survives, and so that anything built on these
is checked first.

- The blind runtime can install a genuinely new typed production by swapping the
  evaluator, and carries a `Set[Region] -> Grid` bridge, while the real engine's
  extensions are macro schemas over a frozen vocabulary.
- The Step-B corpus carries no test pair and no task identifier, so that lane
  cannot produce the correct-final-output leg without the token mapping.
- Certified precision is 40 of 42 on training tasks and 0 of 11 on the
  development split, which would mean the leave-one-out leg carries little
  information on the target distribution.
- The concept file is written once before the fold loop, from a proposal
  conditioned on all demonstrations, while fitting and search are rebuilt inside
  each fold.
- Every promotion mechanism in the repository has been measured null.

## What this changes for the Capability-Growth Gate

Nothing in the gate's order. Two things in how its sixth stage must be run.

First, the conjunction's second and sixth legs require a configuration that ADDS
to the baseline rather than replacing it. Measured against the current concept
hook, "K plus e succeeds" and "removing e destroys the gain" would be comparing
two different search procedures rather than one procedure with and without an
addition. The gate must state which configuration produced each leg.

Second, the correct-final-output leg has never been computed anywhere in this
tree. The gate cannot treat it as routine instrumentation. It is the leg that
keeps the conjunction from being vacuous on data where the certification gate is
poorly calibrated, and it needs a substrate that has task outputs at all.

## Boundaries respected

No file outside this worktree was modified. The live Step-B run was not touched,
inspected semantically, accelerated or delayed. No merge to main. No new
experiment. No LAS work of any kind.
