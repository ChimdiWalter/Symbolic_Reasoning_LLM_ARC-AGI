# Publication Plan: Certified Program Induction

**Working title:** *The Learner Must Re-Derive: Procedure-Level Generalization
Certificates for Abstract Reasoning*
(alt: *Certified Program Induction: Solving ARC with Proofs, Not Just Answers*)

**One-line pitch:** Every other ARC system reports how many answers were
right. This system reports how many solutions come with a machine-checkable
certificate that the *learning procedure itself* re-derives them from fewer
examples — and proposes that certificate as the missing evaluation standard
for reasoning claims.

---

## 1. The breakthrough framing (what excites, and why it's honest)

The field's problem, stated plainly: ARC leaderboard numbers are
unfalsifiable as *reasoning* claims. A test-time-trained LLM that scores 55%
and a lookup table that scores 55% are indistinguishable by the metric.
ARC-AGI-2 sharpened the compute rules but not the epistemics.

**Our counter-position — three moves, each concrete in the codebase:**

1. **The certificate.** A task counts as solved only if re-running the
   ENTIRE induction from N−1 training pairs re-derives a program that solves
   the held-out pair, for every fold (LOO-by-reinduction). This validates
   the *learner*, not the artifact — the difference between "the answer
   checks out" and "the process provably generalizes." No hand-coded
   task solvers, no task IDs, submission mode throughout.

2. **The honest decomposition.** Induced fraction (learned programs vs
   fixed transforms), the parameter-class lattice (relational > feature >
   induced-map > constant) stamped into every certificate, origin classes
   per solve. The system quantifies how much of its own score is reasoning.

3. **The self-audit, demonstrated.** Twice during development the gate
   caught the system's own plausible-but-wrong programs (the PatternExpr
   MDL memorizer; the moved+pattern matching artifact) — found *by the
   acceptance machinery*, not by eyeballing outputs. A reasoning system
   that polices itself is the excitement hook: this is what "the model
   can't fool the benchmark" looks like mechanically.

**The proposed metric (the paper's exportable idea):**
**Certified Solve Rate (CSR)** — the fraction of tasks solved *with* a
procedure-level certificate, reported alongside raw accuracy, with gate
precision P(test-correct | certified) as the metric's own calibration.
Anyone can adopt CSR; that is what makes the paper matter beyond our score.

**Positioning:** DreamCoder (library learning from solutions — we add
failure-driven learning + certificates); Hodel DSL / Icecuber (search
without procedure validation); LLM/TTT ARC solvers (high raw accuracy, zero
per-task generalization evidence). We do not claim SOTA accuracy; we claim
the first *fully certified* ARC corpus and show why raw accuracy overstates
reasoning.

---

## 2. The experiments — STATUS 2026-07-11 (numbers in RUN_HISTORY + outputs/)

| Exp | Status | Headline |
|---|---|---|
| E1 gate calibration | **DONE** | certified 0.952 (40/42) vs rejected train-perfect 0.184 (37/201) — outputs/paper_e1_e4/ |
| E2 gate-off ablation | **DONE, render-verified** | gate ON 43 acc/41 correct (0.953) vs OFF 229/76 (0.332); recall cost ~35 — outputs/paper_e2/ |
| E3 frozen transfer | **DONE** | 1/120 evaluation split (the ARC-AGI-2 cliff) — outputs/unified_harness_eval_frozen/ |
| E4 lattice predicts truth | **DONE** | rejected pop: constant 0.066 -> relational 0.83; gate-off: constant 0.15 -> relational 0.92 |
| E5 cumulative loop | promotion v4 pending | v3 loop closure + speed effect already banked |
| E6 case studies | **material banked** | PatternExpr MDL memorizer; moved+pattern artifact; single-valued-map guard; fold-invariance rule |
| 2-attempt policy | **DONE** | +18 best-of-2 on training (all loo rows); certification's leaderboard price |

METRIC SEMANTICS (paper wording): harness 'solved' = gate-ACCEPTED
("the landscape's definition"); pipeline solves are test-verified by
construction; report RENDER-VERIFIED CSR (v8: 141 verified + 11
gate-accepted-but-wrong of 152). Kaggle pipeline doc:
docs/KAGGLE_PIPELINE.md (emit-predictions shipped 2026-07-11).

## 2b. The experiments as originally planned

**E1 — Gate calibration (THE headline table; runnable today from disk).**
Over all harness runs v1–v7: P(test-correct | LOO-certified) vs
P(test-correct | train-perfect but LOO-rejected). We already know the
denominators are large (42 certified object programs; 236+ LOO-rejected
train-perfect near-solves with recorded partials). If certified precision
is ~0.9+ and rejected precision is low, the certificate is *measurably
load-bearing*. Artifact-only analysis; zero new compute.

**E2 — The gate-off ablation (the killer experiment).**
Re-run the object layer accepting any train-perfect program (skip LOO).
Prediction: raw "solved" count rises, test precision collapses. This single
plot — accuracy up, truth down — is the paper's argument in one figure and
directly indicts uncertified accuracy as a reasoning metric. One 1000-task
run + the existing pipeline: ~1 day compute.

**E3 — Frozen transfer to the ARC evaluation split (the credibility test).**
The frozen system (nothing tuned; library frozen) on the 400 evaluation
tasks: report CSR, induced fraction, and gate precision there. Whatever the
number is, it is *honest by construction* — and we predict gate precision
holds even where accuracy drops, which is itself a publishable finding.

**E4 — Parameter-class lattice predicts generalization.**
Test-correctness stratified by worst parameter class across all certified +
rejected programs. If relational ≻ constant in observed test precision, the
lattice is empirical, not aesthetic. Artifact-only.

**E5 — The cumulative loop, with provenance.**
Operators mined from accepted programs (D15 predicate slots), validated by
retro-solve, re-entering induction through the normal path: show loop
closure (b2862040 solves *through* a learned operator, LOO intact) +
promotion-v4 outcome + speed effects. Frames the system as *accumulating
certified concepts*, not just solving tasks.

**E6 — Case studies: the gate catching its own system.**
The two memorizer episodes as short forensic narratives with the MDL/ranking
mechanics. Reviewers remember stories; these two are true and documented in
RUN_HISTORY with artifacts.

**Ablations already in hand:** ranker on/off (identical — honest negative),
depth-1 vs depth-3, no-library, budget probes (300s: search-bound not
budget-bound). Honest negatives *strengthen* the epistemics claim.

---

## 3. What we do NOT claim (reviewer-proofing)

- No SOTA accuracy claim; 152/1000 training-split CSR is the floor, and the
  paper's value does not move with it.
- No neural/manifold components in the reasoning path (they exist, measured
  zero contribution, and are reported as such — evidence of the ablation
  discipline, not an omission).
- CSR is defined for program-induction systems; we discuss (not solve) how
  sampling-based LLM solvers could approximate it (e.g. resample-from-N−1
  consistency) — that discussion section is the bridge that makes the paper
  relevant to the LLM-ARC community instead of adversarial to it.

## 4. Venue + timeline

- **Target:** NeurIPS/ICLR main track (Datasets & Benchmarks also viable
  given the CSR-metric framing); fallback ICML; arXiv immediately after
  internal freeze. ARC Prize paper award track in parallel — the honest
  certified system is exactly their stated rubric ("conceptual progress").
- **Weeks 1–2:** E1 + E4 (artifact-only) → the two core tables; E2 run
  launched; E5 written from existing provenance + promotion v4.
- **Weeks 2–3:** E3 frozen transfer run (one command, already spec'd in the
  plan docs) + E2 analysis; figures (the accuracy-vs-precision plot; the
  architecture diagram already exists as an artifact).
- **Week 4:** draft assembly. Methods = STAGE1/STAGE2 requirement docs
  (binding specs already written like a paper's method section);
  claim-traceability file already exists (claim_traceability.md).

## 5. ARC Prize 2026 (ARC-AGI-2, Kaggle) track — the competition arm

Deadline Nov 2 2026 (~4 months). The system is compatible BY CONSTRUCTION:
pure Python/numpy symbolic code, no internet, no GPU, CPU-friendly — the
12h offline notebook constraint is trivially met (full 1000-task run takes
~25 min on 16 local cores; Kaggle CPU needs budget re-tuning, not redesign).

**Honest expectation setting:** ARC-AGI-2 evaluation tasks are much harder
than ARC-AGI-1 training (public SOTA is low). Our raw score will be modest.
The play is NOT the accuracy leaderboard — it is the **Grand Prize +
Paper Track rubric**, which scores Novelty / Theory / Universality /
Progress equally with Accuracy: certified induction + CSR is precisely a
"why it works" theory artifact, and the open-source requirement matches our
plan anyway.

Engineering checklist (after the current engine state is sealed):
1. **submission.json adapter**: 2 attempts per test output map naturally to
   our machinery — attempt_1 = the certified program's render; attempt_2 =
   the top-ranked LOO-REJECTED train-perfect program's render (the gate's
   second-best hypothesis). This "certified + best-uncertified" policy is
   itself a nice paper point (attempt_2 measures how much certification
   costs in leaderboard terms).
2. **ARC-AGI-2 data adapter** (task JSON schema identical; download once).
3. **Compute calibration**: per-task budgets vs Kaggle CPU cores; the
   harness is already resumable + budget-parameterized.
4. **Notebook packaging**: vendor geocat_arc + harness as a dataset;
   deterministic seeds; no filesystem writes outside /kaggle/working.
5. **Dry run on the ARC-AGI-2 public eval split locally** (this is also
   paper experiment E3', complementing the ARC-1 frozen transfer).

## 6. Immediate actions queued

1. E1 + E4 scripts over v1–v7 artifacts (no new compute) — launch now.
2. E2 gate-off ablation harness flag (--accept-train-perfect, clearly
   quarantined from real runs) — implement next session.
3. E3 frozen evaluation-split run — after E2, one detached chain.
4. Freeze: tag the code state (suite 365) + library used for all paper runs.
