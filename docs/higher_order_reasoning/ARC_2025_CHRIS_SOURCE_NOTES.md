# Source notes: the October–November 2025 ARC-AGI-2 hackathon work with Chris (read-only archival check, 19 October 2026)

**Purpose.** Establish what the archive records about the 2025 ARC work with Chris before anything about it is put in
the discussion draft.
- **Method:** files were read only. Nothing was run, and protected CORA material was not touched.
- **Tags:** VERIFIED means found at the cited path. NOT FOUND means searched and absent.
- **Rule:** nothing here may be inflated into a result or into a statement about Chris's contributions.

## 1. What the archive records

| item | source | status |
|---|---|---|
| Hackathon slides, 27 pages, created 2025-11-18 (the `.pptx` was created 2025-11-16 and edited 2025-11-18; no author field, no speaker notes) | `/home/cnptp/Downloads/MMCV Lab ARC-AGI 2 HACKATHON.pdf` and `.pptx` | VERIFIED |
| Slide 1: "ARC-AGI 2 Hackathon: MMCV Lab Team"; "ARC Solver — Symbolic Family Search with LLM Priors"; "Chimdi Walter Ndubuisi (Electrical & Computer Engr)"; "Christian Fluharty (Computer Science)". Slide 15 repeats both names | same | VERIFIED |
| Approach options (slide 2): "Train or finetune some model to generate DSL solutions" or "Use an LLM with some clever prompting" | same | VERIFIED |
| Model choice (slides 5–7): DeepSeek R1, because it "made the list (with a non-zero result!)" | same | VERIFIED. The 1.3% shown is ARC Prize's published figure, **not** a team score |
| How R1 was run: Unsloth / Ollama, distilled checkpoints (`DeepSeek-R1-Distill-Qwen-32B`, `DeepSeek-R1-0528-Qwen3-8B`), temperature 0.6. "Due to time constraints … our set up was a single prompt system" | same | VERIFIED |
| Slides 8–10: "R1 on the other hand is blind"; text renderings of grids ("Color by Location", "Location by Color", "Grid with Labeled Contiguous Components") | same | VERIFIED |
| Slide 11 "Results?": R1 says it cannot see the data. Slide 14: "Gemini 2.5 For Comparison" | same | VERIFIED (screenshots, no numbers) |
| Slides 19–25: a neurosymbolic pipeline on an 11-task "Curve-Ball" folder, with LLM hints and programs, policy weights, a bandit state, L0 pixel-error scoring and two attempts per task | same | VERIFIED |
| Code: `llm_client.py` (Ollama, vLLM or stub; Llama 3.1 8B); `prompt_template.txt` (an LLM classifies a task as "global_geom_palette" or "component_mapping"); `dsl.py` (paint, translate, reflect, complete_mirror, snap_to_border, rect_outline); `llm_bridge.py` (phrases turned into DSL programs); a symbolic family search ranked by L0 pixel error on the training pairs | `/home/cnptp/ARC-AGI/` (files dated 2025-10-21 to 2025-11-28; one git commit, 2025-12-30, "Initial commit of Symbolic Reasoning LLM for ARC-AGI", author Chimdi Walter Ndubuisi) | VERIFIED |
| An ARC-AGI-2 evaluation commit to a fork of ARC-Game (2025-11-15) | `/home/cnptp/ARC-Game` (6514eb8) | VERIFIED |
| A planning document with a code scaffold (2025-10-21; its PDF metadata names ChatGPT as creator) | `/home/cnptp/Downloads/Arc‑agi‑2 Robust Solver • Project Plan + Code Scaffold.pdf` | VERIFIED (a plan, not a result) |

## 2. What the archive does NOT record

- **Scores:** no numeric team result, on any task set, in any text or log file. `results/` holds 172 images named
  `FAILED_*.png`; they were not opened, and no score is inferred from them.
- **Contributions:** no record of who did which part.
- **Chris in git:** no commit in any repository by an author named Chris, Christian or Fluharty.
- **A missing module:** `ascii_grid_rendering`, which the R1 code imports, is not on disk.

## 3. Who "Chris" is: identity, kept careful

- **The hackathon:** the co-presenter on the slides is **Christian Fluharty** (Computer Science). VERIFIED.
- **The lab:** the website lists Christian Fluharty, with a joint bio on segmenting leaves from drone video
  (`/home/cnptp/current_papers/lab_website/index.org`, L7–8 and L274–287). VERIFIED.
- **The conversation.** Its "Chris" is the collaborator: "Our Chris", and "the work that you and Chris did … stimulated
  by the ARC competition last year" (00:12:32, 00:14:35).
  - That this is Christian Fluharty is **likely but not verified**: no source states it.
  - **The user should confirm it** before his name appears in any circulated text.
- **Not our Chris:** the transcript's historical anecdote names a different person: "David Searles and Chris Overton
  wrote a very nice grammar" (00:18:44, spelling as transcribed). Do not conflate them.
- **Earlier guidance:** the CORA review guidance already says not to equate "Chris" with any other researcher
  (`docs/summit_20261023_reframe/REVIEW_OUTLINE.md`).

## 4. What may be said in the discussion draft

- **Safe:** in late 2025, Chimdi and Chris worked on ARC-AGI-2 for a hackathon. Their approaches were:
  - LLM priors (DeepSeek-R1 distills run locally, with text renderings of the grids);
  - a small DSL;
  - a symbolic search over transformation families scored by pixel error on the training pairs.

  The slides record a practical difficulty: the reasoning model could not use the grids as given ("R1 … is blind").
- **Not safe without Chris:** any result, success rate or division of labour, or any claim about what the approach
  showed.
