# Neural candidates as failure evidence, and neural-symbolic complementarity: plan v0 (2026-10-13)

**Status: PLAN v0.** Nothing is generated or run.

This plan covers directive sections 9 and 12 of 2026-10-13 ("Strong second
Kaggle submission"): Track C and the scientific experiment. It is separate
from every competition notebook. Nothing here touches native_v1, the
neural_v1 package, the frozen pilot, Step B or VDCG.

## 1. Why a fresh synthetic corpus is the only clean fixture

- NVARC's checkpoint trained on ARC-AGI-2 training data, and the
  evaluation answers drove its checkpoint selection
  (`records/CORA_ARC_LEADER_METHOD_AUDIT_20261013.md`, section 4).
- CORA was developed on ARC-AGI-2 training. Its evaluation set is protected
  in this project.
- So no public ARC-AGI-2 split is clean for both systems. A freshly
  generated, private corpus is clean for both: neither model has seen it.
- **Claims from this corpus are synthetic-tier only.**

## 2. Corpus C2 (new generator module, new seeds)

The families mix two kinds:
- rules CORA's native engine is expected to solve: object recolouring,
  translation, bounding-box fill, symmetry, colour mapping;
- rules it is expected to miss: the colour-layer, diagonal and proximity
  families of the CORA-NVG generator, with new seeds, and new "global" rules
  (row or column propagation, pattern completion, counting into a strip).

Each task has 3 training demonstrations and 1 or 2 test inputs. Test
outputs are held only by the evaluator.

**Seeds:**
- 9000 and up, never used before;
- 12 families x 10 seeds = 120 tasks.

**Neither guide nor solver sees:** the family name, the design target, or
any test output. The corpus file given to the solvers holds inputs and
training pairs only, in competition format.

## 3. Track C: complementarity (diagnosis only; no Kaggle entry follows from it automatically)

**Arms:**
- **NEURAL_ONLY.** neural_v1's exact pipeline on C2, as a separate private
  Kaggle kernel with C2 attached as a private dataset (no answers). Its own
  two attempts.
- **CORA_ONLY.** native_v1's exact harness on C2 (on Athe, CPU, the same
  flags), with its two attempts.
- **NEURAL_PLUS_CORA.** The policy is fixed now, before any data. CORA's
  certified attempt_1 replaces neural attempt_2 only when all hold:
  - CORA certified a program (train-exact plus its leave-one-out);
  - its prediction is unchanged under the 8 dihedral transforms applied
    consistently to demonstrations and test input. This is computed by
    CORA, at inference time, from permitted data only;
  - it differs from both neural attempts.

  Otherwise the two neural attempts stay.

**Metrics** (the evaluator only, per test output):
- symbolic-only, neural-only, both and neither exact;
- pass@2 of each arm;
- wrong output size;
- duplicate attempts;
- false replacement: CORA displaces a correct neural attempt_2;
- CPU and GPU time.

**Decision rule.** NEURAL_PLUS_CORA is justified for a Kaggle candidate
only if, on C2:
- it adds exact outputs over NEURAL_ONLY;
- it has zero false replacements;
- CORA's added compute fits the Kaggle budget (directive section 10).

Otherwise HYBRID_NOT_JUSTIFIED.

## 4. The section-12 experiment: can a neural candidate expose a missing capability?

**Units:** C2 tasks where CORA_ONLY fails (no certified program) and the
neural arm produced a candidate.

**Mechanism** (CORA side; the neural candidate is untrusted):
1. **Disagreement evidence.** Compare the cells of the neural candidate for
   the test input with CORA's best near-solve render for that input. The
   regions where they differ, and their object-level summary under CORA's
   views, are permitted evidence: no test output is involved.
2. **Diagnosis.** cora_diag's typed reading of CORA's failure trace, plus
   the disagreement summary, yields a capability-gap hypothesis.
3. **Construction.** The existing typed repair constructor (cora_reach
   families) searches for an extension. It is constrained to programs that
   (a) reproduce all training demonstrations and (b) map the test input to
   the neural candidate.

   (b) is used only to *propose*, never to accept.
4. **Verification.** The unchanged native adaptive leave-one-out on the
   training demonstrations alone, with each fold rebuilt independently. In
   each fold the neural candidate is regenerated from that fold's
   demonstrations only, by a TTT run on the fold. No parent-fold
   information is used.
5. **Commitment.** The program's test prediction is committed before the
   evaluator scores it.
6. **Ablation.** Removing the extension must remove the gain.

**Controls** (the same constructor and budget):
- **demonstrations only:** no neural candidate;
- **shuffled candidate:** another C2 task's neural candidate, size-adapted
  by crop or pad;
- **random candidate:** the same size and colour histogram as the neural
  one.

**Primary measure:** certified-and-correct test outputs. Harm measure:
certified-and-wrong outputs.

**H1.** Authentic neural candidates yield more certified-correct outputs
than all three controls, with no more certified-wrong outputs.

**Claim ceiling.**
- If H1 holds: "neural transductive candidates, used only as proposal
  evidence, let CORA's unchanged verifier certify more correct programs on a
  clean synthetic corpus".
- That is not invention, unless the extension also passes the bounded
  language-absence test (plan section 12 of the leader audit).

## 5. Compute and order

1. **C2 corpus and its CORA_ONLY run:** on Athe, CPU, nice 19, now.
2. **NEURAL_ONLY on C2:** one private Kaggle kernel, about 120 tasks at
   about 3-10 min per GPU-task across 4 GPUs, so about 2-5 h. That is about
   4-10 quota hours, after the full committed run, and so most likely after
   the 2026-10-17 quota reset.
3. **The section-12 per-fold neural regeneration:** the costliest step. Its
   own budget is set before it runs.

**Freezes:** the corpus, the policy and the controls are frozen before the
neural outputs are opened.
