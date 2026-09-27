# Item-2 v1.4 erratum 1: corrections from the pre-run adversarial review

Date 2026-09-27. Scope: protocol, implementation and tests of v1.4. No v1.4
experiment episode existed at any point; no stage statistic was computed on
real data. First freeze: commit 50841e3, protocol sha256 43e798fa...,
manifest sha256 dd481b31.... This erratum supersedes that freeze; the new
identities are in the manifest and in RESUME.md.

## The review

One reviewer, distinct from the author, read-only. Its tool calls were
scanned afterwards: file reads, hashing, `git diff`, and schema-level
inspection of two smoke records; no writes, no generator run, no distance on
any real or smoke episode, no access outside the allowed trees.

Confirmed sound: the exact null (expected credit 1/2 for any distance
matrix), exactness of the randomization test (simulated size 0.013 at 0.01
over 300 synthetic datasets, SE 0.006, unchanged under an injected
run-position effect), the S3 derivation against `_induce_rules`, the S7a
edge direction, `demonstrations_for` reproducing R2/R3, seed disjointness,
the abandonment rule, atomic slot writes, freeze coverage of every imported
project module, leakage, auditor determinism, 39 of 39 tests.

## Findings and corrections

1. **Blocking.** A stage whose exact randomization test passes but whose
   binomial fails did not stop a later stage from being called the first
   carrying signal. Root cause: ties counted as misses, so on coarse
   descriptors (S2 keys reduce to delta types, S4 failures to operator
   names) the strict rate can stay below 1/2 at any sample size; the reviewer
   built a case with credit 0.695, randomization p 4e-14 and strict rate
   0.402 that was then misclassified as LATE_EXECUTION_SIGNAL_ONLY or
   TFG_AGGREGATION_LOSS.
   Corrections: (a) the hit breaks ties by a sha256 hash of (stage, group
   position, query, companion), label independent, so its null probability
   stays exactly 1/2 (tested for arbitrary distance matrices); strict hits
   are kept as a descriptive figure; (b) the ladder returns
   MIXED_OR_INCONCLUSIVE when a stage before the first qualifying stage has
   randomization p < 0.01 but fails the binomial; (c) the loss point is
   reported (TFG construction, or the 42-field aggregation when S7a
   qualifies). Regression tests: the ladder cases, and a tie-dominated
   coarse signal (tie fraction above 0.9) that qualifies with hash-broken
   hits while strict hits undercount.
2. **Major.** S6, S7a and S7 score candidates against each target's own
   outputs, so they differ between twins even when the reasoner's trajectory
   is identical; the reaction qualifier would have been near-automatic.
   Correction: reactions are established only from S2 to S5, sign tests
   Holm-adjusted over those four; S6, S7a and S7 counts are reported as
   re-scoring stages. Regression test: identical trajectories with differing
   mismatch classes give no reacting stage.
3. **Major.** The engine reads 18 `ARC_*` switches; only two were refused and
   none recorded. `ARC_ANALOGY=1` would load programs persisted by earlier
   runs from `outputs/*/programs/`; `ARC_GUIDE=1` imports code outside the
   digests and caches by training pairs. None was set. Correction: every
   `ARC_*` other than `ARC_META_BUDGET_S=8` is refused, `PYTHONHASHSEED=0`
   required, the environment and Python, numpy and scipy versions recorded
   per slot and checked by the auditor against the manifest; the chain
   script unsets every `ARC_*` before exporting the budget.
4. **Minor.** Only target A ever followed an identical-input run, and two
   `lru_cache`s in `features.py` persist across runs; in a deadline-bound
   regime speed changes trajectory length. Correction: every engine memo
   cache is cleared before every engine run (tested on the real engine).
5. **Minor.** A rerun that solves biases the sign test. Correction:
   excluded and counted. The ungated rerun's residual bias is against
   finding a reaction and is disclosed.
6. **Minor, operational.** Freeze re-verified after every slot; the
   Reasoning_Project_tti grammar manifest and its hash file are hashed; the
   wall clock counts from the first start across restarts; a file lock
   enforces one writer; the auditor checks slot contiguity, unique group
   digests, the group count, and keys integrity by slot; the run-end record
   is written atomically.
7. **Minor, text.** The S3 limitation also applies when the deadline expires
   during action fitting. CPU time per engine run is now recorded. The
   earlier statement that v1.3's index tie-break "could only raise a hit
   rate" was wrong: it adds hits for target-0 queries and removes them for
   target-1 queries, so its net effect can have either sign. The number of
   tied queries in v1.3 was not measured.

## Not changed

Thresholds (alpha 0.01, null 1/2), the planned effect and sample size (42
groups), the floor (14), the caps, the stage definitions and distances, the
twin law, the admission law, the seeds and the classification labels.

No second review round was run, per the one-reviewer discipline. The
corrections are covered by regression tests.
