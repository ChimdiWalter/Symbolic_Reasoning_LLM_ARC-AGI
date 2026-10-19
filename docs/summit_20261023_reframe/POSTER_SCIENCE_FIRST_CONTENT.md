# Science-first review poster: exact text, layout and word count (19 October 2026)

**Source of truth.** `poster_science_first_review.org`. This file copies its text for review; if they differ, the
`.org` wins.

**Built PDF.** `poster_science_first_review.pdf`: one A0 portrait page (2383.94 × 3370.39 pt). A0 is a review
assumption until the organizers confirm a format.

## Layout and reading order

| band | share of the height (approx.) | content |
|---|---|---|
| title | 8 % | title, subtitle, author and affiliation, review banner |
| 1. question | 15 % | the general question (56 pt) and the one-line biology bridge, beside a small ILLUSTRATIVE leaf schematic: "Observed pattern ≠ identified mechanism" |
| 2. reasoning loop | 20 % | the big pipeline, with BOTTLENECK 1 (find objects / propose rules) and BOTTLENECK 2 (choose what to revise) shaded. The dashed learned-prior box sits inside the loop |
| 3. three columns | 50 % | ARC testbed and why rules fail · what CORA did and where it fails · visible doubt and the proposed next step |
| 4. ambition and sources | 7 % | the one-line transfer statement [UNTESTED]; prior work; numbers ledger; disclosure |

## Exact text by block

**Title block:**
- LEARNING WHAT TO CHANGE
- From Scientific Observations to Executable Reasoning and Hypothesis Revision
- Chimdi Walter Ndubuisi · University of Missouri · REVIEW DRAFT 19 October: for collaborator review, not for print

**1. Question and bridge:**
- How can a machine learn the objects, relationships and rules in unfamiliar data—and know what to reconsider when
  its explanation is not enough?
- Biology illustrates the difficulty: measurements do not arrive with the correct entities, mechanisms or reasoning
  rules already identified.

**1. Biology panel** (TikZ; labelled ILLUSTRATIVE SCHEMATIC, not data):
- leaf label: "maize lesion-mimic pattern" → ?
- "What process could explain these patterns?"
- "Observed pattern ≠ identified mechanism."

**2. "One reasoning loop"** (TikZ diagram):

| node | label | style |
|---|---|---|
| Scientific question | what explains an observation? | grey (context) |
| Observations | images · measurements · ARC grids | grey (context) |
| Find objects and relations | what counts as an object | solid |
| Propose executable rules | explanations as runnable programs | solid |
| Execute and test | on visible examples | solid |
| Supported, or not? | rival rules fit, or a held-out example fails | solid |
| Predict, then evaluate independently | — | solid |
| Choose what to revise | objects · rule · evidence · abstain | **dashed** |
| Test the revision | keep or reject | solid |
| Learned priors | Neural-CORA, proposed | **dashed** |

- **Arrows:** yes; no: incomplete, conflicting or fragile; retry (dashed); proposals (dashed); what to revise (dashed).
- **Note:** "visible evidence only: no hidden answer".
- **Bands:** "BOTTLENECK 1 · measured: CORA often cannot propose a usable rule" and "BOTTLENECK 2 · unproven: can it
  learn which part to revise?"
- **Caption:** Solid: implemented and tested. Dashed: proposed. Grey: context. A tested revision is not automatically a
  correct explanation.

**3a. "ARC is our controlled testbed":**
- "Few examples, a new input, one exact answer."
- REAL figure: 00dbd492.
- "Rule: each frame's fill colour depends on its size."

**3b. "Why rules fail":**
- ILLUSTRATIVE row: wrong objects, wrong rule, not enough evidence.
- "Memorization: fits the examples, fails the new input."

**3c. "Done: a rule CORA built [DONE, NARROW]":**
- REAL figure: ka95aa62f67d9.
- "Rule: blue objects send a line up-left; red ones, down-right."
- "Rebuilt 3 of 3 times with one example hidden; correct on an exposed training task, not a competition solve. Also
  found without the failure record."

**3d. "Where it fails [NEGATIVE]":**
- "0 / 58 new verified solutions from rule construction".
- REAL 58-square figure: 55 no rule proposed / 3 proposed but rejected / 0 new verified.
- "Every variant: 0; no wrong answers."

**3e. "Visible doubt [DEVELOPMENT]":**
- REAL figure: the CORA-v2 00dbd492 panel.
- "One example decides the green fill, so CORA-v2 keeps its correct guess uncertified."

**3f. "Next: learning inside CORA [PROPOSED]":**
- Small TikZ loop: trained prior (Qwen3-4B, dashed) → CORA rules → run and check → feedback (dashed) → trained prior;
  run and check → prediction.
- "A trained prior would only order CORA's own search. No result yet."
- "NVARC (published Qwen3-4B method), reproduced: 27.64% public. Native CORA and CORA with rule construction: 0.00%
  public."

**4. Ambition and sources:**
- "If revision selection works on ARC, test the reasoning procedure—not ARC grid operations—on independently
  validated biological questions. [UNTESTED]"
- Footer: prior work (Popper, DreamCoder, LILO, Model Discovery Agent); numbers ledger; AI coding assistance used;
  authorship pending collaborator review.

## Word count (`pdftotext` on the built PDF)

| part | words |
|---|---|
| everything on the page | 426 |
| excluded: title block (title, subtitle, author, affiliation, review banner) | 29 |
| excluded: compact source footer | 36 |
| **body (counted)** | **361** |
| of which diagram labels (loop, schematic, small loop) | about 126 |
| of which block titles and status chips | about 30 |
| of which sentences | about 205 |

**Target:** about 250–350 words of body prose. The 205 sentence words are well inside it. With every diagram label and
title counted, the poster is 361, just above. Text inside the PNG figures (grid labels, tags) is not counted.

**Visual balance** (estimated from `pdfimages -list` and the diagram extents):
- Embedded figures cover about 20 % of the page (2,003 cm² of 9,999 cm²).
- With the TikZ diagrams, about 42 % of the whole page, or about 55–60 % of the content area excluding the title band
  and white space.
- Nothing was shrunk to reach the count:
  - body text 30 pt; captions 26 pt; diagram labels 22–26 pt; figure text ≥ 20 pt;
  - real grids at full column width, the same size as in the Qwen-architecture review poster.
