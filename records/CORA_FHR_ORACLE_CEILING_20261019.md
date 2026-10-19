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

## CORRECTION after the claim audit (2026-10-19; `outputs/cora_fhr/oracle_colour_audit_standin58.json`)

**The defect.** The first colour refinement tested only the **first** fitting expression per view. The
audit rechecked **every** fitting single expression in every view.

| task | fitting expressions examined | one colour per object | verdict |
|---|---|---|---|
| 070dd51e, 17b80ad2, 29c11459, 2e65ae53, 3bd67248 | 75, 25, 10,310, 427, 42 | 0 | colour-limited (exhaustive) |
| 3aa6fb7a | 760 | 760 (constant colour) | passes |
| 22eb0ac0 | 22 | 22 (each object's own colour) | passes |
| 00dbd492 | 483 | 455 (the colour varies by object and is not the object's own) | passes per object; needs a colour-choice rule |

**Corrected counts:** 50 position-inexpressible, **5** colour-limited (not 6), **3** passing (not 2).

**Precise scope of every number above.** The hypothesis class is one **single unguarded** G-grow v1
expression: depth 1, depth 2, or a same-source union, enumerated exhaustively over all 37,750. It is applied
uniformly to every object of one of native's 7 segmentation views.

**Not tested:**
- guarded programs at scene level;
- compositions beyond depth 2;
- multiple operations;
- other representations;
- generating the exact output colour.

**Wording to use:** "In an evaluator-only analysis, 50 of the 58 exposed development tasks could not be
explained by a single uniformly applied G-grow expression in any of seven segmentation views. Of the
remaining 8, 5 need a colour behaviour that no single expression gives, and 3 pass the necessary checks."

**Wording not to use:** "56 of 58 need operations outside the grammar", or any claim that the tasks need
fundamentally new semantics.

**The answers stay evaluator-only.** No forensic class or answer is exposed to any solver arm or policy.
