# Predeclared experiment: failure-conditioned construction of executable rules

Written 2026-09-23, before any measurement. Supersedes the earlier proposal of
relational parameter fitting as the headline intervention. That mechanism may remain
as a baseline component; it is not the architecture under test.

## The question

Does constructing a NEW executable production from failure evidence, installing it
task-locally, and reasoning again, produce correct held-out outputs that ordinary
search over the same building blocks does not produce under matched compute?

The object designed is a RULE, never an answer:

    failure -> e -> Execute(e, x) -> y        not        failure -> y

A mechanism that emits grids directly is out of scope. The construction must be
inspectable, executable, ablatable and reusable.

## The treatment

    demonstrations
      -> ordinary baseline K
      -> solved? yes -> baseline answer
      -> no
         -> failure trace from the real search, not a re-run stub
         -> Typed Failure Graph: frontier nodes, input/output/goal types, observed
            frontier values, delta signatures, cardinality/shape/palette changes,
            relation changes, slots that fit or fail, verifier failure class.
            No task ids, no family labels, no prose.
         -> failure localization: which capability is missing
         -> construct a typed executable production e from GENERIC constructors,
            type-directed so invalid ASTs get no budget
         -> ephemeral K' = K + {e}
         -> re-enter the SAME certified learner
         -> full leave-one-out certification
         -> prediction on the unseen input
         -> remove e, re-run, record the difference
         -> reset to K before the next task; nothing persists

## The prerequisite that invalidated the last attempt

The previous real-engine arm recorded 49 activations and zero acceptances, and the
audit showed the concept path RETURNED ITS OWN HITS BEFORE ordinary search ran. It
replaced K instead of adding to it, so its zero could not answer anything.

Therefore, before any number is recorded, the install path must satisfy, on synthetic
fixtures: every candidate K enumerates is still enumerated under K + {e}, in the same
relative order outside the extension; every fixture K solves is solved identically
under K + {e}; zero cap saturation in both. A path that fails this is reported as
unavailable, and no witness is claimed on it.

## Proposal without a trained network, for the first result

The Grammar Proposal Network decides WHERE to search. It is not required to decide
WHETHER construction works. Version one uses a type-directed enumerator over the
generic constructor language, conditioned on the Typed Failure Graph: goal type and
frontier types restrict the productions considered, and the failure class orders them.
This keeps the system non-LLM, removes a training project from the critical path, and
leaves the network as a later efficiency upgrade rather than a precondition.

## Routing, declared in advance

Failures are classified before construction runs, from the baseline record:

| Class | Signature | Construction routed? |
|---|---|---|
| NO-CANDIDATE | nothing fits the demonstrations | yes, primary |
| MATCHING | fails before fitting | yes |
| LOO-DEATH | fits every demonstration, fails a fold | measured separately, reported separately |
| RESOURCE | budget or cap exhausted | no, excluded with a count |

The 5-task probe of 2026-09-23 found 3 LOO-DEATH, 1 MATCHING, 1 with nothing recorded.
Construction is not expected to help LOO-DEATH and may worsen it. Mixing the classes
would hide that.

## Four outcome levels, reported as whichever is reached

1. Failure-conditioned construction: K fails; the system constructs an executable
   production that is not a stored named solver.
2. New operational reach: K fails, K + {e} returns a correct held-out output, and the
   accepted program uses e.
3. Semantic extension: e is not reproducible by the prior language under the frozen
   separation bounds, so the gain is not a macro that merely saved search.
4. Invention with transfer: e constructed from task A also yields a correct held-out
   output on task B, which took no part in constructing it, and removing e removes it.

Level 1 is interesting, 2 is a capability result, 3 and 4 are the scientific target.
Reaching only level 1 is reported as level 1.

## Measurement

Matched comparison, budget and schedule frozen before scoring: BASE; BASE plus
construction with ordinary fallback under the same total budget; MATCHED EXPANDED
SEARCH, ordinary search given the same enlarged grammar; ABLATION. Paired wins and
losses, never net. Counts for proposals generated, candidates expanded, fits,
verifications, failed construction attempts, fallbacks.

## Forbidden as the headline

Choosing among the existing solvers; another handcrafted ARC solver; deeper search in
the same language; more constant fitting; relational parameter fitting alone;
retrieving or selecting a stored operator or macro; more compute; any transformation a
person added after inspecting the task. Each may improve the score and may be reported
as a score result, under its own name.

## Relation to Step B

None. Step B asks whether a durable extension survives its own frozen gate. This asks
whether a throwaway extension helps within one task. No Step-B output enters this
experiment, and no result here is evidence about Step B.
