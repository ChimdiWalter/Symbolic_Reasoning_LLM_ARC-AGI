# What changed: poster_qwen_architecture_review.pdf → poster_science_first_review.pdf (19 October 2026)

**Side by side:** `SCIENCE_FIRST_CHANGES_comparison.png`, with the Qwen-architecture review on the left and the
science-first poster on the right.

| aspect | before (Qwen-architecture review) | after (science-first review) |
|---|---|---|
| source | hand-written `.tex` | **Emacs Org** `.org`, exported and compiled by `scripts/build_summit_org.sh`; self-test PASS |
| opening | "Can a reasoner recognize when its explanation is inadequate…?", one subproblem | the **general scientific question**: learning objects, relationships and rules in unfamiliar data, and knowing what to reconsider; a one-line biology bridge |
| attribution | "A question shaped in discussions with Toni Kazic" | **removed**, not replaced. A factual acknowledgment is in the explainer, section 11 |
| biology | one text line in a small "From ARC to science" block | a small **ILLUSTRATIVE SCHEMATIC** of a lesion-mimic leaf: "Observed pattern ≠ identified mechanism". No photograph, no omics plot, no pathway |
| main figure | two small parallel Qwen and CORA answer lanes plus a dashed loop | **one large reasoning loop**, from a question to a tested revision. The two bottlenecks are shaded on it. The learned prior is a dashed box *inside* the loop |
| bottlenecks | implicit | **BOTTLENECK 1 (measured):** CORA often cannot propose a usable rule. **BOTTLENECK 2 (unproven):** can it learn which part to revise? Plus "visible evidence only: no hidden answer" |
| ARC evidence | 00dbd492, three tall failure panels, ka95aa62f67d9, 6/26, 0/58, CORA-v2 | 00dbd492; a compact row of three illustrated causes; ka95aa62f67d9; 0/58 with its 58 squares; CORA-v2 as "visible doubt". The 6/26 audit moved to the explainer |
| NVARC | a large lane with 27.64% | one attributed baseline line: "NVARC (published Qwen3-4B method), reproduced: 27.64% public…" |
| Neural-CORA | a dashed loop under two lanes | the dashed box inside the main loop, plus a small dashed loop marked [PROPOSED]; "no result yet" |
| future | "From ARC to science" diagram | one bottom line: "If revision selection works on ARC, test the reasoning procedure… [UNTESTED]" |
| words (pdftotext, body) | about 400, after the earlier trim from about 600 | **361**, including all diagram labels and titles (sentences about 205) |
| explainer | 15 pages, dense | **11 pages**, one column, larger figures, science-first sequence, Org source |

**Unchanged:**
- the real figures' data and provenance. Every poster figure is pixel-identical to its pinned PNG;
- the fonts: body 30 pt, figures ≥ 20 pt;
- the author line;
- the review banner;
- the A0 review assumption.

**Not changed:** any experiment, Step B, VDCG, sealed data, Kaggle or GitHub.
