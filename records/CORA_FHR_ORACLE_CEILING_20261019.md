# FORENSIC expressibility ceiling for the 58-task pool (2026-10-19; evaluator-only; uses answers; DEVELOPMENT)

**What this is.** A diagnostic of why construction scored 0 of 58 in the frozen generalization test. The
true answers are read **only here**, never by any arm.
- Script: `cora_fhr/oracle_expressibility.py`.
- Output: `outputs/cora_fhr/oracle_expressibility_standin58.json` and the colour refinement in
  `outputs/cora_fhr/oracle_expressible8_colour.json`.

**Question.** Can one G-grow v1 expression, applied to every object of any of native's 7 segmentation
views, reproduce every training pair **and** the true test answer?

| class | tasks |
|---|---|
| inexpressible: no single expression fits all pairs in any view, even with the answer | **50** |
| position-expressible, but the growth needs several colours within one object (beyond G-grow's single-colour additions) | **6** |
| expressible: positions plus one colour per object | **2** |
| expressible but not determined by the training pairs | 0 |

**The 2 expressible tasks, and why construction still failed:**
- **3aa6fb7a** (`reflect(H)[self]`, one colour). EG and C2G proposed it, but LOO failed, because the
  evidence disappears when a demonstration is withheld (the same failure as in the rehearsal).
- **22eb0ac0** (`hull[edge:N]`, the object's own colour). EG had no failure evidence (native recorded no
  memorized growth). C2G's proposal was rejected by the engine.

**Verdict.** **56 of 58 (97%)** need operations outside the declared grammar, so the language's reach is
the dominant bottleneck. Revision selection is not. This is consistent with the root-cause re-extraction
(18 of 25 evidence cases inexpressible).

**Implication.** Better choice of revisions cannot help until the system can **extend its language**.
That is grammar induction, Toni's question, and what the separate Step B experiment studies (no verdict
yet).

**Limits:**
- These are necessary conditions only: positions plus a single colour per object. Whether the colour
  itself is derivable was not checked.
- Single expressions only, no guards.
- Exposed training tasks.
