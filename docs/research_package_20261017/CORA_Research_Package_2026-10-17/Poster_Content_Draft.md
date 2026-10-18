# Proposed summit content outline — collaborator review before layout

**Title:** Learning What to Change: From Visual Reasoning to Scientific Hypothesis Revision

**Scope line:** Completed ARC-AGI-2 development studies, a bounded executable-construction prototype, and a proposed biological test of reasoning transfer.

**Authorship:** To be confirmed from actual contributions with Toni, Chris and Pierce. Do not infer the final order from an informal conversation or change the separate SAC student submission.

## The big question

Can a reasoning system learn useful representations and executable rules from a few observations, identify which assumptions fail, and choose a revision that transfers to a different semantic domain?

Our starting point is not the claim that neural models cannot reason. It is the difficulty of deciding whether a failure calls for more search, a different representation, a new operation, or more evidence.

## What we measured in ARC

CORA’s object-reasoning branch was instrumented on 60 exposed ARC training-development tasks. With frozen assets, 6 correct answers passed its check and 26 tasks produced only incorrect demonstration-fitting candidates. A correct candidate existed on 8 tasks. The latest asset-loaded audit gives 8 correct and 25 wrong first-ranked outputs without that check. These results concern one branch, not a globally reliable solver.

## What we built

CORA-FHR can automatically synthesize a typed geometric expression from a predefined grammar, install it temporarily into an unchanged solver, and rebuild it independently during omitted-example checks. In one synthetic development witness, a minority-part ring operation passed all 3 folds and predicted the held-out query correctly; removing it removed the certified gain.

**Important negative result:** a strong failure-blind constructor recovered the same operator. The mixed pilot failed its criterion and the real 60 FHR application added no extension certificate. The result supports bounded executable construction—not a demonstrated causal gain from diagnosing failures.

**Figure request:** actual logged witness and actual paired-control result; no invented pipeline successes.

## Why this is a starting point, not the final architecture

The proposed next study asks whether a policy over typed revisions can outperform an equally equipped failure-blind policy under the same total computation. The strongest comparisons include program-synthesis/library-learning methods and Model Discovery Agent, not an unassisted chatbot.

## The biological bridge — proposed

Toni’s discussion identified molecular measurements and displacement-versus-dispersion analysis as a possible second domain. The exact scientific question, dataset, units, replicates and validation must be confirmed with Pierce. What might transfer is the policy for revising explanations and deciding what evidence is needed, not an ARC-specific geometric operation.

**Figure/data request to collaborators:** one approved completed analysis or representation example, its exact claim and provenance; otherwise use a clearly labeled synthetic illustration. No claim of integrated CORA biological transfer.

## Benchmark context

Native CORA’s recorded official public score is 0.00. A separately reproduced NVARC Qwen3-4B notebook scored 27.64. The neural result is not CORA-FHR performance. A new method submission requires an actual independently evaluated contribution and technical readiness.

## The next falsifiable question

Does authentic failure information improve the choice of revision relative to strong controls—and does an unchanged learned revision policy retain its benefit when the meaning of the observations changes?

## Reader takeaway

Fitting observations, diagnosing failure, constructing a useful correction and transferring that reasoning are different achievements. CORA makes some of these steps executable and testable. The next experiments must establish which can genuinely be learned rather than supplied by the developer.

## Review checklist

Agree scope and author contributions; confirm Chris/Pierce examples and permissions; reconcile claim hashes; use the actual organizer’s poster guide; distinguish proposed from implemented from evaluated; preserve source/figure provenance; freeze by October 20 for the planned Wednesday print target.
