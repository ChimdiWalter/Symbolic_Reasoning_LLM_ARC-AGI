# Source and attribution ledger for "Learning What to Change" (discussion draft v0.2, 19 October 2026)

Every attributed statement in `Learning_What_to_Change_Discussion_DRAFT.md` (and its Org twin) is listed here with its
source and status.
- **Transcript:** `Reasoning_Project_arc2026/voice_note/arc_conversatn.md`. Whisper turbo, 01:20:33, 73 segments;
  each segment has a start time only and no speaker label. `.txt` is the same text.
- **Times** are segment start times. Line numbers (L) are in the `.md` file.
- **Not found:** the excerpt file `ARC_Focused_Conversation_Transcript_2026-10-17.md` is not on Athe.
- **Speaker attribution** follows the user's account of who said what. There is no diarization, so any quotation
  attributed to Toni should be confirmed by Toni before circulation.

## A. Statements drawn from the conversation

| draft § | statement (as used) | transcript | status |
|---|---|---|---|
| 2.1 | inducing representations of data with very different syntax and semantics | 00:00:03, L10: "is there a way of inducing a representation of data, of very different syntax and semantics" | VERIFIED |
| 2.2 | reasoning systems hand-built for specific domains | 00:07:14, L34: "people built, of course, by hand, reasoning systems about specific domains"; 00:09:23 region, L42: "everything is handcrafted … customized for specific domains" | VERIFIED |
| 2.2 | earlier work on inducing grammars from data | 00:08:15, L38 | VERIFIED |
| 2.2 | grammars need not be deterministic; stochastic and probabilistic grammars; grammars for molecules | 00:17:39, L74; 00:18:44, L78 | VERIFIED |
| 2.2 | biological rules may be context-dependent | — | **MY INTERPRETATION**, marked as such. "Context-dependent", "DSL" and "domain-specific language" do not occur in the transcript |
| 2.3 | learning from few instances and from failures | 00:00:03, L10: "can a reasoner, given just a few instances of data … can it learn from failures?" | VERIFIED |
| 2.4 | generalizing over the reasoning, not only the data | 00:01:35, L14; 00:04:01, L22 | VERIFIED |
| 2 (validation) | reproduce what is known → plausible ideas that could be verified → verification | 00:27:58, L110 | VERIFIED. "Independent" is **my addition**, marked |
| 6 | Pierce: numerical data on molecular species under different conditions; code written to decide displacement or dispersion; tests run | 00:02:37, L18 | VERIFIED. The word "statistical" does not occur, and the code is credited to "you" (Chimdi) |
| 7 | maize lesions: Mendelian but complex, influenced by modifier genes and the weather | 00:33:26, L130; 00:34:28, L134 | VERIFIED in substance. "Maize" and "lesion-mimic" are not said in that range; "corn and lesions" appears at 00:17:39 |
| 7 | biology's molecular, physiological and genetic levels remain separate; no "grand synthesis" | 00:40:43, L158 (also 00:38:35, L150) | VERIFIED. An earlier draft called this "cross-disciplinary biology", which is a looser description |
| header, 11 | circulate the main points in an Org file to Chris, Pierce and Toni before the poster | 00:12:32, L54: "put it in the channel for Chris and Pierce and I"; 00:15:35, L66: "draft the main points in the org"; 00:16:37, L70: before turning it "into the form of a poster, get the discussion" | VERIFIED. At L66 the word "Don't" before "slam the images into the org file" may be a transcription error; unresolved |
| 12 | authorship touched on informally; left dependent on content | 00:13:34, L58; 00:14:35, L62: "It depends on what the content is." | VERIFIED. **No author order is stated or assigned in the draft** |

## B. Statements about the 2025 ARC work with Chris

Full detail is in `ARC_2025_CHRIS_SOURCE_NOTES.md`.

| statement | source | status |
|---|---|---|
| an Oct–Nov 2025 ARC-AGI-2 hackathon; slides "ARC Solver — Symbolic Family Search with LLM Priors" | `~/Downloads/MMCV Lab ARC-AGI 2 HACKATHON.pdf`, p1 (created 2025-11-18) | VERIFIED |
| approaches: local LLM reasoning models (DeepSeek-R1 distills) with text renderings of grids; a small DSL; a family search scored by pixel error | slides pp. 5–10 and 19–25; `/home/cnptp/ARC-AGI/` code | VERIFIED |
| "R1 … is blind" | slide 8 | VERIFIED |
| results or scores | — | **NOT FOUND**, so none are stated |
| who did what | — | **NOT FOUND**, so nothing is stated |
| Chris's identity | slides list "Christian Fluharty (Computer Science)" as co-presenter; transcript: "Our Chris" (00:12:32), "the work that you and Chris did … stimulated by the ARC competition last year" (00:14:35) | **TO CONFIRM** with the user. The draft keeps "Chris" and flags the identification |
| the "Chris" of the molecular-grammar anecdote | 00:18:44, L78: "David Searles and Chris Overton wrote a very nice grammar" | a **different person**; not conflated |

## C. Statements about the Pierce project

| statement | source | status |
|---|---|---|
| project title and authors | `pipeline/sb_class_project/README.md` L1, L3: "Dispersion, Not Displacement: …", "Pierce Taylor, Chimdi Walter Ndubuisi, and Toni Kazic" | VERIFIED |
| the question: coherent displacement versus heterogeneous dispersion; single-nucleus RNA-seq of alveolar epithelial cells | README L9 | VERIFIED |
| limits: cross-sectional design limits causal claims; donor-level inference essential before submission; do not over-interpret pseudotime | `PROJECT_STATUS.md` L47; `project_plan_summary.md` L123, L170 | VERIFIED |
| that the transcript's Pierce project is this project | the user, 19 October 2026: "Pierce and I Project is `/deltos/e/lesion_phes/code/python/pipeline/sb_class_project` and you will see parts of it in `/deltos/e/lesion_phes/code/python/pipeline/_nature_program`" | **CONFIRMED BY THE USER** |
| the work continues in `pipeline/_nature_program` (DISPERSION) | `_nature_program/GROUND_RULES.md` (non-destructive, read-only inputs); `MASTER_PROGRESS.md` L64 (donor-aware variance decomposition → donor-level inference, planned), L87 (execution-depth audit OPEN) | VERIFIED (read-only). The draft states no finding, and treats the cells-versus-donors unit as an open methodological question |
| the project's findings | README L13–16 | **NOT USED** in detail: stated in the README, not checked against result files |
| the question and the conclusion, as the user tells it: the literature says displacement; after checks the conclusion was dispersion | the user, 19 October 2026, verbatim: "it was on covid if covid cell weere disolacement as literature says or dispersion---earlier thought dispersion but corrected to dispersion after checks" | **THE USER'S ACCOUNT**, used and marked in draft §6; to confirm with Pierce. The "earlier thought" part is ambiguous as typed and is not used |

## D. CORA statements (kept minimal on purpose)

| statement | source | status |
|---|---|---|
| a plausible hypothesis can fit the examples and still be unstable; adding rules can create ambiguity; equally equipped controls that ignored the diagnosis sometimes constructed the same operation | `records/CORA_SUMMIT_CLAIM_LEDGER_20261017.md` rows 9, 12c, 12f, 19, 22 | VERIFIED. No scores, task identifiers or Step B detail appear in the draft, as directed |

## E. Related work named in the draft

- Popper (Cropper and Morel 2021).
- DreamCoder (Ellis et al. 2021).
- LILO (Grand et al. 2024).
- Model Discovery Agent (Murphy 2026).

They are named as directions to read, with no claim about what they cannot do.

## F. Open confirmations before circulation

1. **Chris:** confirm his identity and how he wishes to be named. Ask him to correct or complete the hackathon summary.
2. **Pierce:** review the displacement-versus-dispersion description and its limits, and suggest a tractable
   question.
3. **Toni:** confirm the paraphrases in section 2 and the preferred wording of the central question.
4. ~~The user: confirm the Pierce project~~: done, `sb_class_project` (19 October). Pierce should still review how it is described.
